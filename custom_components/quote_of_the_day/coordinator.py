"""Data coordinator for the Quote of the Day integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import logging
import random
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import QuoteApiError, async_fetch_quotes
from .const import (
    CONF_CACHE_DAYS,
    CONF_LANGUAGE,
    CONF_SOURCE,
    DEFAULT_CACHE_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_SOURCE,
    DOMAIN,
    MAX_CACHED_QUOTES,
    ONLINE_SOURCES,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .quotes import Quote, daily_quote, random_quote

_LOGGER = logging.getLogger(__name__)

# Regular check: picks up a new day if the midnight trigger was missed and
# refreshes the cache when it is due. Cheap when nothing changed.
UPDATE_INTERVAL = timedelta(minutes=30)
# Wait this long before contacting an online source again after a failure.
RETRY_AFTER = timedelta(hours=1)

type QuoteConfigEntry = ConfigEntry[QuoteCoordinator]


@dataclass(slots=True)
class QuoteState:
    """The current quote and where it came from."""

    quote: Quote
    day: date
    source: str
    language: str
    fallback: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "quote": self.quote.as_dict(),
            "day": self.day.isoformat(),
            "source": self.source,
            "language": self.language,
            "fallback": self.fallback,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuoteState:
        """Deserialize from storage."""
        return cls(
            quote=Quote.from_dict(data["quote"]),
            day=date.fromisoformat(data["day"]),
            source=str(data["source"]),
            language=str(data["language"]),
            fallback=bool(data.get("fallback", False)),
        )


@dataclass(slots=True)
class QuoteCache:
    """Quotes fetched from an online source, kept for weeks."""

    source: str | None = None
    quotes: list[Quote] = field(default_factory=list)
    updated: datetime | None = None
    # Texts of quotes already shown, so they don't repeat until all were shown.
    history: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "source": self.source,
            "quotes": [q.as_dict() for q in self.quotes],
            "updated": self.updated.isoformat() if self.updated else None,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuoteCache:
        """Deserialize from storage."""
        updated = data.get("updated")
        return cls(
            source=data.get("source"),
            quotes=[Quote.from_dict(q) for q in data.get("quotes", [])],
            updated=dt_util.parse_datetime(updated) if updated else None,
            history=[str(t) for t in data.get("history", [])],
        )

    def merge(self, source: str, quotes: list[Quote], now: datetime) -> int:
        """Add new quotes to the cache; return how many were new."""
        if source != self.source:
            self.source = source
            self.quotes = []
            self.history = []
        known = {q.text for q in self.quotes}
        new = [q for q in quotes if q.text not in known and not known.add(q.text)]
        self.quotes.extend(new)
        del self.quotes[:-MAX_CACHED_QUOTES]
        self.updated = now
        return len(new)


class QuoteCoordinator(DataUpdateCoordinator[QuoteState]):
    """Keeps track of the quote of the day."""

    config_entry: QuoteConfigEntry

    def __init__(self, hass: HomeAssistant, entry: QuoteConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._session = async_get_clientsession(hass)
        self._unsub_midnight: CALLBACK_TYPE | None = None
        self._last_failure: datetime | None = None
        self.cache = QuoteCache()

    def _option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    @property
    def source(self) -> str:
        """Configured quote source."""
        return self._option(CONF_SOURCE, DEFAULT_SOURCE)

    @property
    def language(self) -> str:
        """Configured language (applies to the built-in collection)."""
        return self._option(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    @property
    def cache_duration(self) -> timedelta:
        """How long fetched quotes are used before the cache is refreshed."""
        return timedelta(days=int(self._option(CONF_CACHE_DAYS, DEFAULT_CACHE_DAYS)))

    @property
    def is_online(self) -> bool:
        """Whether the configured source is an online source."""
        return self.source in ONLINE_SOURCES

    async def async_setup(self) -> None:
        """Restore stored state and schedule the midnight refresh."""
        stored = await self._store.async_load() or {}
        try:
            if current := stored.get("current"):
                self.data = QuoteState.from_dict(current)
            if cache := stored.get("cache"):
                self.cache = QuoteCache.from_dict(cache)
        except (KeyError, TypeError, ValueError, AttributeError):
            _LOGGER.debug("Ignoring invalid stored data: %s", stored)

        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight, hour=0, minute=0, second=1
        )

    @callback
    def async_shutdown_listeners(self) -> None:
        """Stop the midnight trigger."""
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None

    async def _async_midnight(self, _now: datetime) -> None:
        await self.async_refresh()

    async def _async_save(self, state: QuoteState) -> None:
        await self._store.async_save(
            {"current": state.as_dict(), "cache": self.cache.as_dict()}
        )

    def _cache_usable(self) -> bool:
        return self.cache.source == self.source and bool(self.cache.quotes)

    def _cache_due(self, now: datetime) -> bool:
        if not self._cache_usable() or self.cache.updated is None:
            return True
        return now - self.cache.updated >= self.cache_duration

    async def _async_refresh_cache(self, now: datetime) -> bool:
        """Fetch a new batch of quotes if the cache is due; True if it changed."""
        if not self._cache_due(now):
            return False
        if self._last_failure and now - self._last_failure < RETRY_AFTER:
            return False
        try:
            quotes = await async_fetch_quotes(self._session, self.source)
        except QuoteApiError as err:
            self._last_failure = now
            if self._cache_usable():
                _LOGGER.info("Could not refresh quote cache, keeping cached quotes: %s", err)
            else:
                _LOGGER.warning(
                    "Could not fetch quotes from %s, using built-in quotes: %s",
                    self.source,
                    err,
                )
            return False
        self._last_failure = None
        added = self.cache.merge(self.source, quotes, now)
        _LOGGER.debug(
            "Fetched %d quotes from %s (%d new, %d cached)",
            len(quotes),
            self.source,
            added,
            len(self.cache.quotes),
        )
        return True

    def _is_current(self, state: QuoteState | None, today: date) -> bool:
        if state is None or state.day != today or state.source != self.source:
            return False
        if state.fallback:
            # Switch to a real quote as soon as the online source worked.
            return not self._cache_usable()
        return self.is_online or state.language == self.language

    async def _async_update_data(self) -> QuoteState:
        """Return today's quote, picking a new one when the day changed."""
        now = dt_util.now()
        cache_changed = self.is_online and await self._async_refresh_cache(now)

        if self._is_current(self.data, now.date()):
            if cache_changed:
                await self._async_save(self.data)
            return self.data

        state = self._pick(now.date(), new=False)
        await self._async_save(state)
        return state

    async def async_new_quote(self) -> None:
        """Replace the current quote with a random one."""
        now = dt_util.now()
        if self.is_online:
            await self._async_refresh_cache(now)
        state = self._pick(now.date(), new=True)
        await self._async_save(state)
        self.async_set_updated_data(state)

    def _pick(self, today: date, *, new: bool) -> QuoteState:
        current = self.data.quote if self.data else None

        if self.is_online and self._cache_usable():
            seen = set(self.cache.history)
            candidates = [
                q for q in self.cache.quotes if q.text not in seen and q != current
            ]
            if not candidates:
                # Everything was shown: start over.
                self.cache.history = []
                candidates = [q for q in self.cache.quotes if q != current]
                candidates = candidates or self.cache.quotes
            rng = random.Random() if new else random.Random(today.isoformat())
            quote = rng.choice(candidates)
            self.cache.history.append(quote.text)
            return QuoteState(quote, today, self.source, quote.language)

        language = self.language
        quote = random_quote(language, current) if new else daily_quote(today, language)
        return QuoteState(quote, today, self.source, language, fallback=self.is_online)

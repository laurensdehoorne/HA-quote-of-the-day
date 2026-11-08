"""Data coordinator for the Quote of the Day integration.

Quotes come from a pool that combines every selected source: the curated
built-in collection plus the quotes cached from each online source. Online
sources are only contacted when their part of the cache is older than the
configured cache duration (weeks by default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import logging
import random
from typing import Any

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
    CONF_SOURCES,
    CONF_THEME,
    DEFAULT_CACHE_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_SOURCES,
    DEFAULT_THEME,
    DOMAIN,
    LANGUAGE_ALL,
    LANGUAGE_EN,
    MAX_CACHED_QUOTES,
    ONLINE_SOURCES,
    SOURCE_BUILTIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    THEME_MOTIVATIONAL,
)
from .data import QuoteConfigEntry
from .quotes import Quote, is_good_quote, is_motivational, quotes_for_language

_LOGGER = logging.getLogger(__name__)

# Regular check: picks up a new day if the midnight trigger was missed and
# refreshes the cache when it is due. Cheap when nothing changed.
UPDATE_INTERVAL = timedelta(minutes=30)
# Wait this long before contacting an online source again after a failure.
RETRY_AFTER = timedelta(hours=1)
# All online sources currently deliver English quotes.
ONLINE_SOURCE_LANGUAGE = LANGUAGE_EN


@dataclass(slots=True)
class QuoteState:
    """The current quote and the settings it was picked with."""

    quote: Quote
    day: date
    settings: str
    fallback: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "quote": self.quote.as_dict(),
            "day": self.day.isoformat(),
            "settings": self.settings,
            "fallback": self.fallback,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuoteState:
        """Deserialize from storage."""
        return cls(
            quote=Quote.from_dict(data["quote"]),
            day=date.fromisoformat(data["day"]),
            settings=str(data["settings"]),
            fallback=bool(data.get("fallback", False)),
        )


@dataclass(slots=True)
class SourceCache:
    """Quotes fetched from one online source."""

    quotes: list[Quote] = field(default_factory=list)
    updated: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "quotes": [q.as_dict() for q in self.quotes],
            "updated": self.updated.isoformat() if self.updated else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceCache:
        """Deserialize from storage."""
        updated = data.get("updated")
        return cls(
            quotes=[Quote.from_dict(q) for q in data.get("quotes", [])],
            updated=dt_util.parse_datetime(updated) if updated else None,
        )

    def merge(self, quotes: list[Quote], now: datetime) -> int:
        """Add new quotes; return how many were new."""
        known = {q.key for q in self.quotes}
        added = 0
        for quote in quotes:
            if quote.key not in known:
                known.add(quote.key)
                self.quotes.append(quote)
                added += 1
        del self.quotes[:-MAX_CACHED_QUOTES]
        self.updated = now
        return added


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
        self._last_failure: dict[str, datetime] = {}
        self.caches: dict[str, SourceCache] = {}
        # Keys of quotes already shown, so none repeats until all were shown.
        self.history: list[str] = []
        # Quotes the user marked as "not good": never shown again.
        self.disliked: dict[str, dict[str, Any]] = {}

    # --- settings ---------------------------------------------------------

    def _option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    @property
    def sources(self) -> list[str]:
        """Selected quote sources."""
        return list(self._option(CONF_SOURCES, DEFAULT_SOURCES)) or [SOURCE_BUILTIN]

    @property
    def language(self) -> str:
        """Selected language."""
        return self._option(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    @property
    def theme(self) -> str:
        """Selected theme: only motivational quotes, or all of them."""
        return self._option(CONF_THEME, DEFAULT_THEME)

    @property
    def cache_duration(self) -> timedelta:
        """How long fetched quotes are used before a source is contacted again."""
        return timedelta(days=int(self._option(CONF_CACHE_DAYS, DEFAULT_CACHE_DAYS)))

    @property
    def online_sources(self) -> list[str]:
        """Selected online sources that can deliver quotes in the chosen language."""
        if self.language not in (LANGUAGE_ALL, ONLINE_SOURCE_LANGUAGE):
            return []
        return [s for s in self.sources if s in ONLINE_SOURCES]

    @property
    def _settings(self) -> str:
        return f"{','.join(sorted(self.sources))}|{self.language}|{self.theme}"

    # --- lifecycle --------------------------------------------------------

    async def async_setup(self) -> None:
        """Restore stored state and schedule the midnight refresh."""
        stored = await self._store.async_load() or {}
        try:
            if current := stored.get("current"):
                self.data = QuoteState.from_dict(current)
            self.caches = {
                source: SourceCache.from_dict(data)
                for source, data in stored.get("caches", {}).items()
            }
            self.history = [str(k) for k in stored.get("history", [])]
            self.disliked = dict(stored.get("disliked", {}))
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
            {
                "current": state.as_dict(),
                "caches": {s: c.as_dict() for s, c in self.caches.items()},
                "history": self.history,
                "disliked": self.disliked,
            }
        )

    # --- cache ------------------------------------------------------------

    def _cache_due(self, source: str, now: datetime) -> bool:
        cache = self.caches.get(source)
        if cache is None or not cache.quotes or cache.updated is None:
            return True
        return now - cache.updated >= self.cache_duration

    async def _async_refresh_caches(self, now: datetime) -> bool:
        """Fetch new quotes from every source that is due; True if any changed."""
        changed = False
        for source in self.online_sources:
            if not self._cache_due(source, now):
                continue
            failed = self._last_failure.get(source)
            if failed and now - failed < RETRY_AFTER:
                continue
            try:
                quotes = await async_fetch_quotes(self._session, source)
            except QuoteApiError as err:
                self._last_failure[source] = now
                _LOGGER.warning("Could not fetch quotes from %s: %s", source, err)
                continue
            self._last_failure.pop(source, None)
            cache = self.caches.setdefault(source, SourceCache())
            added = cache.merge(quotes, now)
            changed = True
            _LOGGER.debug(
                "Fetched %d good quotes from %s (%d new, %d cached)",
                len(quotes),
                source,
                added,
                len(cache.quotes),
            )
        return changed

    @property
    def cached_quotes(self) -> int:
        """Number of quotes cached from the selected online sources."""
        return sum(
            len(self.caches[s].quotes) for s in self.online_sources if s in self.caches
        )

    @property
    def cache_updated(self) -> datetime | None:
        """When the oldest part of the cache was refreshed."""
        dates = [
            updated
            for s in self.online_sources
            if s in self.caches and (updated := self.caches[s].updated)
        ]
        return min(dates) if dates else None

    # --- picking quotes ---------------------------------------------------

    def _online_pool(self) -> list[Quote]:
        return [
            q
            for s in self.online_sources
            if s in self.caches
            for q in self.caches[s].quotes
            # Re-check: the filter may have become stricter since caching.
            if is_good_quote(q)
        ]

    def _pool(self) -> tuple[list[Quote], bool]:
        """Return the quotes to choose from, and whether this is a fallback."""
        pool: list[Quote] = []
        if SOURCE_BUILTIN in self.sources:
            pool.extend(quotes_for_language(self.language))
        pool.extend(self._online_pool())
        if not pool:
            # Only online sources selected and none reachable yet.
            return list(quotes_for_language(self.language)), True
        seen: set[str] = set()
        unique = []
        for quote in pool:
            if quote.key not in seen:
                seen.add(quote.key)
                unique.append(quote)
        if self.theme == THEME_MOTIVATIONAL:
            # Without any motivational quote, any quote beats none.
            unique = [q for q in unique if is_motivational(q)] or unique
        liked = [q for q in unique if q.key not in self.disliked]
        # If everything was disliked, showing something beats showing nothing.
        return liked or unique, False

    def _is_current(self, state: QuoteState | None, today: date) -> bool:
        if state is None or state.day != today or state.settings != self._settings:
            return False
        if state.fallback:
            # Switch to a real quote as soon as an online source worked.
            return not self._online_pool()
        return True

    def _pick(self, today: date, *, new: bool) -> QuoteState:
        pool, fallback = self._pool()
        current = self.data.quote.key if self.data else None
        shown = set(self.history)
        candidates = [q for q in pool if q.key not in shown and q.key != current]
        if not candidates:
            # Everything was shown: start a new round.
            self.history = []
            candidates = [q for q in pool if q.key != current] or pool
        # The daily pick is reproducible for a given day and history.
        rng = random.Random() if new else random.Random(today.isoformat())
        quote = rng.choice(candidates)
        self.history.append(quote.key)
        del self.history[: -(MAX_CACHED_QUOTES * 2)]
        return QuoteState(quote, today, self._settings, fallback)

    # --- updates ----------------------------------------------------------

    async def _async_update_data(self) -> QuoteState:
        """Return today's quote, picking a new one when the day changed."""
        now = dt_util.now()
        cache_changed = await self._async_refresh_caches(now)

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
        await self._async_refresh_caches(now)
        state = self._pick(now.date(), new=True)
        await self._async_save(state)
        self.async_set_updated_data(state)

    async def async_dislike_quote(self) -> None:
        """Never show the current quote again and replace it."""
        if self.data is not None:
            quote = self.data.quote
            self.disliked[quote.key] = {"text": quote.text, "author": quote.author}
            _LOGGER.debug("Disliked quote: %s (%s)", quote.text, quote.author)
        await self.async_new_quote()

    async def async_restore_disliked(self) -> None:
        """Allow all disliked quotes again."""
        self.disliked = {}
        if self.data is not None:
            await self._async_save(self.data)
            self.async_set_updated_data(self.data)

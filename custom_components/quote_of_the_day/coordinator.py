"""Data coordinator for the Quote of the Day integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import QuoteApiError, ZenQuotesClient
from .const import (
    CONF_LANGUAGE,
    CONF_SOURCE,
    DEFAULT_LANGUAGE,
    DEFAULT_SOURCE,
    DOMAIN,
    SOURCE_BUILTIN,
    SOURCE_ZENQUOTES,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .quotes import Quote, daily_quote, random_quote

_LOGGER = logging.getLogger(__name__)

# Regular check: picks up a new day if the midnight trigger was missed and
# retries the online source after a fallback. Cheap when nothing changed.
UPDATE_INTERVAL = timedelta(minutes=30)

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
        self._client = ZenQuotesClient(async_get_clientsession(hass))
        self._unsub_midnight: CALLBACK_TYPE | None = None

    @property
    def source(self) -> str:
        """Configured quote source."""
        return self.config_entry.options.get(
            CONF_SOURCE, self.config_entry.data.get(CONF_SOURCE, DEFAULT_SOURCE)
        )

    @property
    def language(self) -> str:
        """Configured language (applies to the built-in collection)."""
        return self.config_entry.options.get(
            CONF_LANGUAGE, self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        )

    async def async_setup(self) -> None:
        """Restore the last quote and schedule the midnight refresh."""
        stored = await self._store.async_load()
        if stored:
            try:
                self.data = QuoteState.from_dict(stored)
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Ignoring invalid stored quote: %s", stored)

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

    def _is_current(self, state: QuoteState | None, today: date) -> bool:
        return (
            state is not None
            and state.day == today
            and state.source == self.source
            and (self.source != SOURCE_BUILTIN or state.language == self.language)
            and not state.fallback
        )

    async def _async_update_data(self) -> QuoteState:
        """Return today's quote, fetching a new one when the day changed."""
        today = dt_util.now().date()
        if self._is_current(self.data, today):
            return self.data

        state = await self._async_fetch(today, new=False)
        await self._store.async_save(state.as_dict())
        return state

    async def async_new_quote(self) -> None:
        """Replace the current quote with a random one."""
        state = await self._async_fetch(dt_util.now().date(), new=True)
        await self._store.async_save(state.as_dict())
        self.async_set_updated_data(state)

    async def _async_fetch(self, today: date, *, new: bool) -> QuoteState:
        source = self.source
        language = self.language

        if source == SOURCE_ZENQUOTES:
            try:
                quote = await (
                    self._client.async_get_random()
                    if new
                    else self._client.async_get_today()
                )
            except QuoteApiError as err:
                _LOGGER.warning(
                    "Could not fetch quote from ZenQuotes, using built-in quote: %s",
                    err,
                )
            else:
                return QuoteState(quote, today, source, quote.language)

        current = self.data.quote if self.data else None
        quote = random_quote(language, current) if new else daily_quote(today, language)
        return QuoteState(
            quote,
            today,
            source,
            language,
            fallback=source != SOURCE_BUILTIN,
        )

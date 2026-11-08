"""Coordinator for the famous birthday and the fact of the day."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LANGUAGE,
    DEFAULT_LANGUAGE,
    DOMAIN,
    LANGUAGE_ALL,
    STORAGE_KEY_ON_THIS_DAY,
    STORAGE_VERSION,
)
from .data import QuoteConfigEntry
from .onthisday import DayInfo, OnThisDayError, async_fetch_day

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=30)
RETRY_AFTER = timedelta(hours=1)
# Days are fetched ahead, so a few days without internet go unnoticed.
PREFETCH_DAYS = 7
# Spread the requests: at most this many days are fetched per update.
MAX_FETCHES_PER_UPDATE = 2
# A calendar day's data is re-fetched after a year (page views change).
MAX_AGE = timedelta(days=365)
# Raised when the way the fact is picked changes, so cached days are redone.
CACHE_VERSION = 2


def _key(day: date) -> str:
    return f"{day.month:02d}-{day.day:02d}"


class OnThisDayCoordinator(DataUpdateCoordinator[DayInfo | None]):
    """Provides today's famous birthday and fact, cached per calendar day."""

    config_entry: QuoteConfigEntry

    def __init__(self, hass: HomeAssistant, entry: QuoteConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_on_this_day",
            update_interval=UPDATE_INTERVAL,
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_ON_THIS_DAY
        )
        self._session = async_get_clientsession(hass)
        self._days: dict[str, dict[str, Any]] = {}
        self._failures: dict[str, datetime] = {}
        self._unsub_midnight: CALLBACK_TYPE | None = None

    @property
    def wiki_language(self) -> str:
        """Wikipedia edition to use: the chosen language or Home Assistant's."""
        language = self.config_entry.options.get(
            CONF_LANGUAGE, self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        )
        if language == LANGUAGE_ALL:
            language = (self.hass.config.language or "en").split("-")[0]
        return language

    async def async_setup(self) -> None:
        """Restore the cache and schedule the midnight refresh."""
        stored = await self._store.async_load() or {}
        days = stored.get("days")
        if isinstance(days, dict):
            self._days = days
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight, hour=0, minute=0, second=2
        )

    @callback
    def async_shutdown_listeners(self) -> None:
        """Stop the midnight trigger."""
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None

    async def _async_midnight(self, _now: datetime) -> None:
        await self.async_refresh()

    def _cached(self, day: date, now: datetime) -> DayInfo | None:
        entry = self._days.get(_key(day))
        if (
            not entry
            or entry.get("requested_language") != self.wiki_language
            or entry.get("version") != CACHE_VERSION
        ):
            return None
        fetched = dt_util.parse_datetime(str(entry.get("fetched", "")))
        if fetched is None or now - fetched > MAX_AGE:
            return None
        try:
            return DayInfo.from_dict(entry["info"])
        except (KeyError, TypeError, ValueError):
            return None

    async def _async_fetch(self, day: date, now: datetime) -> bool:
        key = _key(day)
        failed = self._failures.get(key)
        if failed and now - failed < RETRY_AFTER:
            return False
        try:
            info = await async_fetch_day(self._session, day, self.wiki_language)
        except OnThisDayError as err:
            self._failures[key] = now
            _LOGGER.warning("Could not fetch 'on this day' data for %s: %s", key, err)
            return False
        self._failures.pop(key, None)
        self._days[key] = {
            "fetched": now.isoformat(),
            "requested_language": self.wiki_language,
            "version": CACHE_VERSION,
            "info": info.as_dict(),
        }
        return True

    async def _async_update_data(self) -> DayInfo | None:
        now = dt_util.now()
        today = now.date()
        changed = False
        fetches = 0
        for offset in range(PREFETCH_DAYS):
            day = today + timedelta(days=offset)
            if self._cached(day, now) is not None:
                continue
            if fetches >= MAX_FETCHES_PER_UPDATE:
                break
            fetches += 1
            changed |= await self._async_fetch(day, now)
        if changed:
            await self._store.async_save({"days": self._days})

        info = self._cached(today, now)
        if info is None:
            # Better yesterday's language or an old entry than nothing.
            if entry := self._days.get(_key(today)):
                try:
                    return DayInfo.from_dict(entry["info"])
                except (KeyError, TypeError, ValueError):
                    pass
            raise UpdateFailed("No 'on this day' data available yet")
        return info

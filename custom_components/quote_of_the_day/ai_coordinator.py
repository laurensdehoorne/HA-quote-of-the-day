"""Coordinator for the daily motivational quote written by AI."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .ai_quote import AiQuote, AiQuoteError, async_generate, build_instructions
from .const import (
    AI_LANGUAGE_AUTO,
    CONF_AI_INSTRUCTIONS,
    CONF_AI_LANGUAGE,
    CONF_AI_TASK_ENTITY,
    CONF_LANGUAGE,
    DEFAULT_LANGUAGE,
    DOMAIN,
    LANGUAGE_ALL,
    STORAGE_KEY_AI_QUOTE,
    STORAGE_VERSION,
)
from .data import QuoteConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=30)
RETRY_AFTER = timedelta(hours=1)
MAX_HISTORY = 60


def ai_task_entity(entry: QuoteConfigEntry) -> str:
    """The AI Task entity chosen in the options ("" when AI is off)."""
    return str(
        entry.options.get(CONF_AI_TASK_ENTITY, entry.data.get(CONF_AI_TASK_ENTITY)) or ""
    )


class AiQuoteCoordinator(DataUpdateCoordinator[AiQuote | None]):
    """Asks the AI for a new motivational quote once a day."""

    config_entry: QuoteConfigEntry

    def __init__(self, hass: HomeAssistant, entry: QuoteConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_ai_quote",
            update_interval=UPDATE_INTERVAL,
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_AI_QUOTE
        )
        self._unsub_midnight: CALLBACK_TYPE | None = None
        self._last_failure: datetime | None = None
        # Earlier AI quotes, so the AI is asked not to repeat them.
        self.history: list[str] = []

    # --- settings ---------------------------------------------------------

    def _option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, self.config_entry.data.get(key, default))

    @property
    def entity_id(self) -> str:
        """The AI Task entity that writes the quote."""
        return ai_task_entity(self.config_entry)

    @property
    def language(self) -> str:
        """Language of the quote: its own setting, the quote language or HA's."""
        language = self._option(CONF_AI_LANGUAGE, AI_LANGUAGE_AUTO) or AI_LANGUAGE_AUTO
        if language != AI_LANGUAGE_AUTO:
            return language
        language = self._option(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        if language == LANGUAGE_ALL:
            language = (self.hass.config.language or "en").split("-")[0]
        return language

    @property
    def extra_instructions(self) -> str:
        """The user's own wishes for the quote."""
        return str(self._option(CONF_AI_INSTRUCTIONS, "") or "").strip()

    @property
    def _settings(self) -> str:
        return f"{self.entity_id}|{self.language}|{self.extra_instructions}"

    # --- lifecycle --------------------------------------------------------

    async def async_setup(self) -> None:
        """Restore the last quote and schedule the midnight refresh."""
        stored = await self._store.async_load() or {}
        try:
            if current := stored.get("current"):
                self.data = AiQuote.from_dict(current)
            self.history = [str(text) for text in stored.get("history", [])]
        except (KeyError, TypeError, ValueError, AttributeError):
            _LOGGER.debug("Ignoring invalid stored AI quote: %s", stored)
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight, hour=0, minute=0, second=3
        )

    @callback
    def async_shutdown_listeners(self) -> None:
        """Stop the midnight trigger."""
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None

    async def _async_midnight(self, _now: datetime) -> None:
        await self.async_refresh()

    # --- generating -------------------------------------------------------

    async def _async_generate(self, now: datetime) -> AiQuote:
        instructions = build_instructions(
            now.date(), self.language, self.history, self.extra_instructions
        )
        text = await async_generate(self.hass, self.entity_id, instructions)
        quote = AiQuote(text, now.date(), self.language, self.entity_id, self._settings)
        self.history.append(text)
        del self.history[:-MAX_HISTORY]
        await self._store.async_save(
            {"current": quote.as_dict(), "history": self.history}
        )
        _LOGGER.debug("AI quote for %s: %s", quote.day, text)
        return quote

    async def _async_update_data(self) -> AiQuote | None:
        """Return today's AI quote, asking the AI for one when needed."""
        now = dt_util.now()
        current = self.data
        if (
            current is not None
            and current.day == now.date()
            and current.settings == self._settings
        ):
            return current
        if self._last_failure and now - self._last_failure < RETRY_AFTER:
            return self._previous(current)
        try:
            quote = await self._async_generate(now)
        except AiQuoteError as err:
            self._last_failure = now
            _LOGGER.warning("Could not get a quote from AI: %s", err)
            return self._previous(current)
        self._last_failure = None
        return quote

    @staticmethod
    def _previous(current: AiQuote | None) -> AiQuote:
        # Yesterday's quote (see the "date" attribute) beats no quote.
        if current is None:
            raise UpdateFailed("No AI quote available yet")
        return current

    async def async_new_quote(self) -> None:
        """Ask the AI for a new quote right away."""
        try:
            quote = await self._async_generate(dt_util.now())
        except AiQuoteError as err:
            raise HomeAssistantError(f"Could not get a quote from AI: {err}") from err
        self._last_failure = None
        self.async_set_updated_data(quote)

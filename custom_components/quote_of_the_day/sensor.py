"""Sensors for Quote of the Day."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_AUTHOR,
    ATTR_CACHE_UPDATED,
    ATTR_CACHED_QUOTES,
    ATTR_DATE,
    ATTR_ENTRIES,
    ATTR_FALLBACK,
    ATTR_LANGUAGE,
    ATTR_QUOTE,
    ATTR_SOURCE,
)
from .coordinator import QuoteConfigEntry, QuoteCoordinator
from .entity import QuoteEntity

# Home Assistant limits a state to 255 characters; the full text is
# always available in the ``quote`` attribute.
MAX_STATE_LENGTH = 255


def truncate(text: str, limit: int = MAX_STATE_LENGTH) -> str:
    """Shorten text to fit in a state, ending with an ellipsis if cut."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [QuoteSensor(coordinator), AuthorSensor(coordinator)],
    )


class QuoteSensor(QuoteEntity, SensorEntity):
    """The quote of the day."""

    _attr_icon = "mdi:format-quote-close"

    def __init__(self, coordinator: QuoteCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "quote")

    @property
    def native_value(self) -> str:
        """Return the (possibly truncated) quote."""
        return truncate(self.coordinator.data.quote.text)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full quote and its details."""
        coordinator = self.coordinator
        state = coordinator.data
        attrs: dict[str, Any] = {
            ATTR_QUOTE: state.quote.text,
            ATTR_AUTHOR: state.quote.author,
            ATTR_DATE: state.day.isoformat(),
            ATTR_SOURCE: state.source,
            ATTR_LANGUAGE: state.quote.language,
            ATTR_FALLBACK: state.fallback,
            # Same shape as a Feedparser sensor, so feed-based Lovelace cards
            # (e.g. quote-of-the-day-card with `feed_attribute: entries`) work.
            ATTR_ENTRIES: [{"title": state.quote.author, "summary": state.quote.text}],
        }
        if coordinator.is_online:
            cache = coordinator.cache
            attrs[ATTR_CACHED_QUOTES] = len(cache.quotes)
            attrs[ATTR_CACHE_UPDATED] = (
                cache.updated.isoformat() if cache.updated else None
            )
        return attrs


class AuthorSensor(QuoteEntity, SensorEntity):
    """The author of the quote of the day."""

    _attr_icon = "mdi:account-voice"

    def __init__(self, coordinator: QuoteCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "author")

    @property
    def native_value(self) -> str:
        """Return the author."""
        return truncate(self.coordinator.data.quote.author)

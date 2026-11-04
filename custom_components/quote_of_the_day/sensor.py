"""Sensors for Quote of the Day."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AUTHOR,
    ATTR_CACHE_UPDATED,
    ATTR_CACHED_QUOTES,
    ATTR_DATE,
    ATTR_ENTRIES,
    ATTR_FALLBACK,
    ATTR_LANGUAGE,
    ATTR_QUOTE,
    ATTR_REFERENCE,
    ATTR_SOURCE,
)
from .coordinator import QuoteCoordinator
from .data import QuoteConfigEntry
from .entity import OnThisDayEntity, QuoteEntity
from .onthisday import Birthday, Fact
from .onthisday_coordinator import OnThisDayCoordinator

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
    data = entry.runtime_data
    entities: list[SensorEntity] = [QuoteSensor(data.quotes), AuthorSensor(data.quotes)]
    if data.on_this_day:
        entities += [BirthdaySensor(data.on_this_day), FactSensor(data.on_this_day)]
    async_add_entities(entities)


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
            ATTR_REFERENCE: state.quote.reference,
            ATTR_DATE: state.day.isoformat(),
            ATTR_SOURCE: state.quote.source,
            ATTR_LANGUAGE: state.quote.language,
            ATTR_FALLBACK: state.fallback,
            # Same shape as a Feedparser sensor, so feed-based Lovelace cards
            # (e.g. quote-of-the-day-card with `feed_attribute: entries`) work.
            ATTR_ENTRIES: [{"title": state.quote.author, "summary": state.quote.text}],
        }
        if coordinator.online_sources:
            updated = coordinator.cache_updated
            attrs[ATTR_CACHED_QUOTES] = coordinator.cached_quotes
            attrs[ATTR_CACHE_UPDATED] = updated.isoformat() if updated else None
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


def _years_ago(year: int) -> int:
    return dt_util.now().year - year


class BirthdaySensor(OnThisDayEntity, SensorEntity):
    """A famous person born on this day."""

    _attr_icon = "mdi:cake-variant"

    def __init__(self, coordinator: OnThisDayCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "birthday")

    @property
    def _birthday(self) -> Birthday | None:
        data = self.coordinator.data
        return data.birthday if data else None

    @property
    def available(self) -> bool:
        """Available when today has a birthday."""
        return super().available and self._birthday is not None

    @property
    def native_value(self) -> str | None:
        """Return the person's name."""
        return truncate(birthday.name) if (birthday := self._birthday) else None

    @property
    def entity_picture(self) -> str | None:
        """Return the person's photo from Wikipedia."""
        return birthday.image if (birthday := self._birthday) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details about the person."""
        if (birthday := self._birthday) is None:
            return None
        return {
            "name": birthday.name,
            "born": birthday.year,
            "years_ago": _years_ago(birthday.year),
            "description": birthday.description,
            "summary": birthday.summary,
            "url": birthday.url,
            ATTR_LANGUAGE: self.coordinator.data.language,
        }


class FactSensor(OnThisDayEntity, SensorEntity):
    """A historical or scientific event that happened on this day."""

    _attr_icon = "mdi:book-clock"

    def __init__(self, coordinator: OnThisDayCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "on_this_day")

    @property
    def _fact(self) -> Fact | None:
        data = self.coordinator.data
        return data.fact if data else None

    @property
    def available(self) -> bool:
        """Available when today has a fact."""
        return super().available and self._fact is not None

    @property
    def native_value(self) -> str | None:
        """Return "year: event"."""
        return truncate(f"{fact.year}: {fact.text}") if (fact := self._fact) else None

    @property
    def entity_picture(self) -> str | None:
        """Return a picture of the event from Wikipedia."""
        return fact.image if (fact := self._fact) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details about the event."""
        if (fact := self._fact) is None:
            return None
        return {
            "text": fact.text,
            "year": fact.year,
            "years_ago": _years_ago(fact.year),
            "category": fact.category,
            "title": fact.title,
            "url": fact.url,
            ATTR_LANGUAGE: self.coordinator.data.language,
        }

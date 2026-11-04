"""Button to get a new quote."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QuoteConfigEntry, QuoteCoordinator
from .entity import QuoteEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    async_add_entities([NewQuoteButton(entry.runtime_data)])


class NewQuoteButton(QuoteEntity, ButtonEntity):
    """Replace today's quote with a random new one."""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: QuoteCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "new_quote")

    async def async_press(self) -> None:
        """Fetch a new quote."""
        await self.coordinator.async_new_quote()

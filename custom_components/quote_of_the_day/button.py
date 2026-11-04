"""Button to get a new quote."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QuoteCoordinator
from .data import QuoteConfigEntry
from .entity import QuoteEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button."""
    coordinator = entry.runtime_data.quotes
    async_add_entities(
        [
            NewQuoteButton(coordinator),
            DislikeQuoteButton(coordinator),
            RestoreDislikedButton(coordinator),
        ]
    )


class NewQuoteButton(QuoteEntity, ButtonEntity):
    """Replace today's quote with a random new one."""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: QuoteCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "new_quote")

    async def async_press(self) -> None:
        """Fetch a new quote."""
        await self.coordinator.async_new_quote()


class DislikeQuoteButton(QuoteEntity, ButtonEntity):
    """Mark the current quote as not good: it is replaced and never shown again."""

    _attr_icon = "mdi:thumb-down-outline"

    def __init__(self, coordinator: QuoteCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "dislike_quote")

    async def async_press(self) -> None:
        """Dislike the current quote."""
        await self.coordinator.async_dislike_quote()


class RestoreDislikedButton(QuoteEntity, ButtonEntity):
    """Allow all disliked quotes again."""

    _attr_icon = "mdi:restore"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: QuoteCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "restore_disliked")

    async def async_press(self) -> None:
        """Restore the disliked quotes."""
        await self.coordinator.async_restore_disliked()

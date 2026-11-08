"""Buttons for the quote of the day and the AI quote."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .ai_coordinator import AiQuoteCoordinator
from .coordinator import QuoteCoordinator
from .data import QuoteConfigEntry
from .entity import AiQuoteEntity, QuoteEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    coordinator = entry.runtime_data.quotes
    entities: list[ButtonEntity] = [
        NewQuoteButton(coordinator),
        DislikeQuoteButton(coordinator),
        RestoreDislikedButton(coordinator),
    ]
    if ai_quote := entry.runtime_data.ai_quote:
        entities.append(NewAiQuoteButton(ai_quote))
    async_add_entities(entities)


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


class NewAiQuoteButton(AiQuoteEntity, ButtonEntity):
    """Ask the AI for a new motivational quote."""

    _attr_icon = "mdi:robot-happy-outline"

    def __init__(self, coordinator: AiQuoteCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, "new_ai_quote")

    @property
    def available(self) -> bool:
        """Always available: after a failed attempt, this is how to retry."""
        return True

    async def async_press(self) -> None:
        """Ask the AI for a new quote."""
        await self.coordinator.async_new_quote()

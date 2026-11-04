"""Base entity for Quote of the Day."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTIONS, DOMAIN, WIKIPEDIA_ATTRIBUTION
from .coordinator import QuoteCoordinator
from .onthisday_coordinator import OnThisDayCoordinator


class BaseEntity[CoordinatorT: DataUpdateCoordinator[Any]](
    CoordinatorEntity[CoordinatorT]
):
    """Common base: one service device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoordinatorT, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Quote of the Day",
            manufacturer="Quote of the Day",
            entry_type=DeviceEntryType.SERVICE,
        )


class QuoteEntity(BaseEntity[QuoteCoordinator]):
    """Base for the quote entities."""

    @property
    def attribution(self) -> str | None:
        """Credit the online source of the current quote, if any."""
        return ATTRIBUTIONS.get(self.coordinator.data.quote.source)


class OnThisDayEntity(BaseEntity[OnThisDayCoordinator]):
    """Base for the birthday and fact entities."""

    _attr_attribution = WIKIPEDIA_ATTRIBUTION

    @property
    def available(self) -> bool:
        """Available once there is data for today."""
        return super().available and self.coordinator.data is not None

"""Base entity for Quote of the Day."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTIONS, DOMAIN
from .coordinator import QuoteCoordinator


class QuoteEntity(CoordinatorEntity[QuoteCoordinator]):
    """Common base for all Quote of the Day entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: QuoteCoordinator, key: str) -> None:
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
        self._attr_attribution = ATTRIBUTIONS.get(coordinator.source)

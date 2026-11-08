"""The Quote of the Day integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.start import async_at_started

from .ai_coordinator import AiQuoteCoordinator, ai_task_entity
from .const import (
    CONF_ON_THIS_DAY,
    CONF_SOURCE,
    CONF_SOURCES,
    DEFAULT_ON_THIS_DAY,
    SOURCE_BUILTIN,
)
from .coordinator import QuoteCoordinator
from .data import QuoteConfigEntry, QuoteRuntimeData
from .onthisday_coordinator import OnThisDayCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: QuoteConfigEntry) -> bool:
    """Set up Quote of the Day from a config entry."""
    coordinator = QuoteCoordinator(hass, entry)
    await coordinator.async_setup()
    entry.async_on_unload(coordinator.async_shutdown_listeners)
    await coordinator.async_config_entry_first_refresh()

    on_this_day: OnThisDayCoordinator | None = None
    if entry.options.get(
        CONF_ON_THIS_DAY, entry.data.get(CONF_ON_THIS_DAY, DEFAULT_ON_THIS_DAY)
    ):
        on_this_day = OnThisDayCoordinator(hass, entry)
        await on_this_day.async_setup()
        entry.async_on_unload(on_this_day.async_shutdown_listeners)
        # Not "first_refresh": the quote must work even when Wikipedia doesn't.
        await on_this_day.async_refresh()

    ai_quote: AiQuoteCoordinator | None = None
    if ai_task_entity(entry):
        ai_quote = AiQuoteCoordinator(hass, entry)
        await ai_quote.async_setup()
        entry.async_on_unload(ai_quote.async_shutdown_listeners)

        # In the background, once Home Assistant (and the AI Task entity) has
        # started: the AI can take a while and must not hold up the quote.
        async def _async_first_ai_quote(_hass: HomeAssistant) -> None:
            await ai_quote.async_refresh()

        entry.async_on_unload(async_at_started(hass, _async_first_ai_quote))

    entry.runtime_data = QuoteRuntimeData(coordinator, on_this_day, ai_quote)
    _async_remove_unused_entities(
        hass,
        entry,
        ([] if on_this_day else ["birthday", "on_this_day"])
        + ([] if ai_quote else ["ai_quote", "new_ai_quote"]),
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_remove_unused_entities(
    hass: HomeAssistant, entry: QuoteConfigEntry, keys: list[str]
) -> None:
    """Remove entities of features that were switched off in the options."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id in {f"{entry.entry_id}_{key}" for key in keys}:
            registry.async_remove(entity.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: QuoteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: QuoteConfigEntry) -> None:
    """Reload when the options change, so the new source/language applies."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: QuoteConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        # Version 1 had a single "source"; version 2 combines several "sources".
        def _migrate(values: dict) -> dict:
            values = dict(values)
            if CONF_SOURCE in values:
                source = values.pop(CONF_SOURCE)
                values[CONF_SOURCES] = (
                    [source] if source == SOURCE_BUILTIN else [SOURCE_BUILTIN, source]
                )
            return values

        hass.config_entries.async_update_entry(
            entry,
            data=_migrate(entry.data),
            options=_migrate(entry.options),
            version=2,
        )
        _LOGGER.debug("Migrated config entry to version 2")
    return True

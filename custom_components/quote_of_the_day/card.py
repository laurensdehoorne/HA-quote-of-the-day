"""Serve the dashboard card (custom:daily-quote-card) and load it.

The card is loaded in two ways, so it shows up even when one of them fails:

* as an extra module of the Home Assistant frontend (all dashboards, also
  in YAML mode), which is part of the page itself;
* as a dashboard resource (dashboards in storage mode, the default), which
  the frontend fetches every time a dashboard is opened, also when the page
  itself still comes from the browser's cache.

The URL carries a hash of the file, so browsers fetch the card again after
every change instead of using an old copy.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CARD_URL_BASE = "/quote_of_the_day_static"
CARD_FILENAME = "daily-quote-card.js"
CARD_DIR = Path(__file__).parent / "frontend"
CARD_URL_PREFIX = f"{CARD_URL_BASE}/{CARD_FILENAME}"


def _file_hash() -> str:
    return hashlib.sha256((CARD_DIR / CARD_FILENAME).read_bytes()).hexdigest()[:12]


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and make the frontend load it."""
    if hass.http is None:  # e.g. tests without the http component
        return
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    url = f"{CARD_URL_PREFIX}?v={await hass.async_add_executor_job(_file_hash)}"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(CARD_DIR), True)]
    )
    if "frontend" in hass.config.components:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415

        add_extra_js_url(hass, url)
    await _async_set_resource(hass, url)


def _resources(hass: HomeAssistant) -> Any | None:
    """The dashboard resources, if they are managed in the UI (storage mode)."""
    data = hass.data.get("lovelace")
    if data is None:
        return None
    mode = getattr(data, "resource_mode", None)
    resources = getattr(data, "resources", None)
    if isinstance(data, dict):  # older Home Assistant versions
        mode = data.get("resource_mode", data.get("mode"))
        resources = data.get("resources")
    if mode != "storage" or not hasattr(resources, "async_create_item"):
        return None
    return resources


async def _async_set_resource(hass: HomeAssistant, url: str | None) -> None:
    """Add, update or (with url None) remove the card's dashboard resource."""
    if (resources := _resources(hass)) is None:
        return
    try:
        await resources.async_get_info()  # loads the resources
        ours = [
            item
            for item in resources.async_items()
            if str(item.get("url", "")).startswith(CARD_URL_PREFIX)
        ]
        if url is None:
            for item in ours:
                await resources.async_delete_item(item["id"])
            return
        if not ours:
            await resources.async_create_item({"res_type": "module", "url": url})
            return
        first, *duplicates = ours
        if first.get("url") != url:
            await resources.async_update_item(first["id"], {"url": url})
        for item in duplicates:
            await resources.async_delete_item(item["id"])
    except Exception:  # noqa: BLE001
        # The extra module still loads the card; never fail the setup for this.
        _LOGGER.warning("Could not register the dashboard card as a resource", exc_info=True)


async def async_unregister_card(hass: HomeAssistant) -> None:
    """Remove the card's dashboard resource (the integration is removed)."""
    await _async_set_resource(hass, None)

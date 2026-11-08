"""Tests for serving and loading the dashboard card."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.quote_of_the_day.card import (
    CARD_FILENAME,
    CARD_URL_BASE,
    CARD_URL_PREFIX,
    async_register_card,
    async_unregister_card,
)
from custom_components.quote_of_the_day.const import DOMAIN


def _mock_http(hass: HomeAssistant) -> None:
    hass.http = MagicMock(async_register_static_paths=AsyncMock())


async def _resources(hass: HomeAssistant):
    resources = hass.data["lovelace"].resources
    await resources.async_get_info()
    return resources


async def test_card_is_served_and_loaded(hass: HomeAssistant) -> None:
    _mock_http(hass)
    hass.config.components.add("frontend")
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await async_register_card(hass)

    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert paths[0].url_path == CARD_URL_BASE
    assert (Path(paths[0].path) / CARD_FILENAME).is_file()
    (_, url), _ = add_js.call_args
    assert url.startswith(f"{CARD_URL_PREFIX}?v=")
    assert len(url.split("?v=")[1]) == 12  # hash of the file


async def test_card_skipped_without_http(hass: HomeAssistant) -> None:
    hass.http = None
    await async_register_card(hass)  # must not raise


async def test_card_dashboard_resource(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    _mock_http(hass)
    resources = await _resources(hass)
    other = await resources.async_create_item(
        {"res_type": "module", "url": "/local/other-card.js"}
    )

    await async_register_card(hass)
    ours = [i for i in resources.async_items() if i["url"].startswith(CARD_URL_PREFIX)]
    assert len(ours) == 1
    assert ours[0]["type"] == "module"
    url = ours[0]["url"]

    # Registering again (restart) keeps one resource.
    await async_register_card(hass)
    assert [i["url"] for i in resources.async_items()] == [other["url"], url]

    # An old version and a duplicate are replaced by the current URL.
    await resources.async_update_item(ours[0]["id"], {"url": f"{CARD_URL_PREFIX}?v=old"})
    await resources.async_create_item(
        {"res_type": "module", "url": f"{CARD_URL_PREFIX}?v=older"}
    )
    await async_register_card(hass)
    assert [i["url"] for i in resources.async_items()] == [other["url"], url]

    # Removed with the integration; other resources stay.
    await async_unregister_card(hass)
    assert [i["url"] for i in resources.async_items()] == [other["url"]]


async def test_card_resource_yaml_mode(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"mode": "yaml"}})
    _mock_http(hass)
    await async_register_card(hass)  # YAML resources are not touched
    await async_unregister_card(hass)


async def test_removing_the_integration_removes_the_resource(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "lovelace", {})
    _mock_http(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"sources": ["builtin"], "language": "en", "on_this_day": False},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    resources = await _resources(hass)
    assert any(i["url"].startswith(CARD_URL_PREFIX) for i in resources.async_items())

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not any(i["url"].startswith(CARD_URL_PREFIX) for i in resources.async_items())

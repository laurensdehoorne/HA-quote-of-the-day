"""Tests for serving the dashboard card."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.quote_of_the_day import _async_register_card
from custom_components.quote_of_the_day.const import CARD_FILENAME, CARD_URL_BASE


async def test_card_is_served_and_loaded(hass: HomeAssistant) -> None:
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    hass.config.components.add("frontend")
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await _async_register_card(hass)

    (paths,), _ = hass.http.async_register_static_paths.call_args
    assert paths[0].url_path == CARD_URL_BASE
    assert (Path(paths[0].path) / CARD_FILENAME).is_file()
    (_, url), _ = add_js.call_args
    assert url.startswith(f"{CARD_URL_BASE}/{CARD_FILENAME}?v=")


async def test_card_skipped_without_http(hass: HomeAssistant) -> None:
    hass.http = None
    await _async_register_card(hass)  # must not raise

"""Integration tests for Quote of the Day."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.quote_of_the_day.const import (
    DOMAIN,
    ZENQUOTES_RANDOM_URL,
    ZENQUOTES_TODAY_URL,
)
from custom_components.quote_of_the_day.quotes import daily_quote

QUOTE_SENSOR = "sensor.quote_of_the_day_quote"
AUTHOR_SENSOR = "sensor.quote_of_the_day_author"
NEW_QUOTE_BUTTON = "button.quote_of_the_day_new_quote"


async def _setup(hass: HomeAssistant, **data) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quote of the Day",
        data={"source": "builtin", "language": "all", **data},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"source": "builtin", "language": "nl"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"source": "builtin", "language": "nl"}
    await hass.async_block_till_done()

    state = hass.states.get(QUOTE_SENSOR)
    assert state is not None
    assert state.attributes["language"] == "nl"

    # Only one instance allowed.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_builtin_sensors(hass: HomeAssistant) -> None:
    await _setup(hass)
    expected = daily_quote(dt_util.now().date(), "all")

    quote = hass.states.get(QUOTE_SENSOR)
    assert quote.state == expected.text
    assert quote.attributes["quote"] == expected.text
    assert quote.attributes["author"] == expected.author
    assert quote.attributes["source"] == "builtin"
    assert quote.attributes["fallback"] is False
    assert hass.states.get(AUTHOR_SENSOR).state == expected.author

    registry = er.async_get(hass)
    assert registry.async_get(QUOTE_SENSOR).unique_id.endswith("_quote")


async def test_new_quote_button(hass: HomeAssistant) -> None:
    await _setup(hass)
    before = hass.states.get(QUOTE_SENSOR).state

    await hass.services.async_call(
        "button", "press", {"entity_id": NEW_QUOTE_BUTTON}, blocking=True
    )
    assert hass.states.get(QUOTE_SENSOR).state != before


async def test_new_quote_survives_restart(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    await hass.services.async_call(
        "button", "press", {"entity_id": NEW_QUOTE_BUTTON}, blocking=True
    )
    pressed = hass.states.get(QUOTE_SENSOR).state

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).state == pressed


async def test_changes_at_midnight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-04 23:59:50+01:00")
    await hass.config.async_set_time_zone("Europe/Brussels")
    await _setup(hass)
    assert hass.states.get(QUOTE_SENSOR).attributes["date"] == "2026-11-04"

    freezer.move_to("2026-11-05 00:00:02+01:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["date"] == "2026-11-05"
    assert state.state == daily_quote(dt_util.now().date(), "all").text


async def test_zenquotes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        ZENQUOTES_TODAY_URL, json=[{"q": "Today quote.", "a": "Zen Author"}]
    )
    aioclient_mock.get(
        ZENQUOTES_RANDOM_URL, json=[{"q": "Random quote.", "a": "Other Author"}]
    )
    await _setup(hass, source="zenquotes")

    state = hass.states.get(QUOTE_SENSOR)
    assert state.state == "Today quote."
    assert state.attributes["author"] == "Zen Author"
    assert state.attributes["source"] == "zenquotes"
    assert "ZenQuotes" in state.attributes["attribution"]

    await hass.services.async_call(
        "button", "press", {"entity_id": NEW_QUOTE_BUTTON}, blocking=True
    )
    assert hass.states.get(QUOTE_SENSOR).state == "Random quote."


async def test_zenquotes_fallback(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(ZENQUOTES_TODAY_URL, status=500)
    await _setup(hass, source="zenquotes", language="nl")

    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["fallback"] is True
    assert state.attributes["language"] == "nl"
    assert state.state == daily_quote(dt_util.now().date(), "nl").text


async def test_options_and_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass, language="nl")
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "nl"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"source": "builtin", "language": "en"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "en"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

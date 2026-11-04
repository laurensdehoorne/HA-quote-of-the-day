"""Integration tests for Quote of the Day."""

from __future__ import annotations

from datetime import timedelta

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
    BRAINYQUOTE_RSS_URL,
    DOMAIN,
    ZENQUOTES_BATCH_URL,
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
        result["flow_id"], {"source": "builtin", "language": "nl", "cache_days": 14}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"source": "builtin", "language": "nl", "cache_days": 14}
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


ZEN_BATCH = [{"q": f"Zen quote {i}.", "a": f"Author {i}"} for i in range(5)]


async def test_zenquotes_cache(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    aioclient_mock.get(ZENQUOTES_BATCH_URL, json=ZEN_BATCH)
    await _setup(hass, source="zenquotes", cache_days=28)
    assert aioclient_mock.call_count == 1

    state = hass.states.get(QUOTE_SENSOR)
    texts = {q["q"] for q in ZEN_BATCH}
    assert state.state in texts
    assert state.attributes["source"] == "zenquotes"
    assert state.attributes["fallback"] is False
    assert state.attributes["cached_quotes"] == 5
    assert state.attributes["entries"] == [
        {"title": state.attributes["author"], "summary": state.state}
    ]
    assert "ZenQuotes" in state.attributes["attribution"]

    # The next days use the cache: no new requests, no repeats.
    shown = [state.state]
    for _ in range(4):
        freezer.tick(timedelta(days=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        shown.append(hass.states.get(QUOTE_SENSOR).state)
    assert sorted(shown) == sorted(texts)
    assert aioclient_mock.call_count == 1

    # The button picks from the cache too.
    await hass.services.async_call(
        "button", "press", {"entity_id": NEW_QUOTE_BUTTON}, blocking=True
    )
    assert hass.states.get(QUOTE_SENSOR).state in texts
    assert aioclient_mock.call_count == 1

    # After the cache duration, a new batch is fetched and merged.
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        ZENQUOTES_BATCH_URL, json=[*ZEN_BATCH, {"q": "Brand new.", "a": "New"}]
    )
    freezer.tick(timedelta(days=28))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert hass.states.get(QUOTE_SENSOR).attributes["cached_quotes"] == 6


async def test_cache_survives_restart(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(ZENQUOTES_BATCH_URL, json=ZEN_BATCH)
    entry = await _setup(hass, source="zenquotes")
    before = hass.states.get(QUOTE_SENSOR).state

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert hass.states.get(QUOTE_SENSOR).state == before


async def test_brainyquote(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        BRAINYQUOTE_RSS_URL,
        text=(
            "<rss><channel><item><title>Walt Disney</title>"
            "<description>&quot;Just start.&quot;</description></item>"
            "</channel></rss>"
        ),
    )
    await _setup(hass, source="brainyquote")
    state = hass.states.get(QUOTE_SENSOR)
    assert state.state == "Just start."
    assert hass.states.get(AUTHOR_SENSOR).state == "Walt Disney"
    assert "BrainyQuote" in state.attributes["attribution"]


async def test_online_fallback_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    aioclient_mock.get(ZENQUOTES_BATCH_URL, status=500)
    await _setup(hass, source="zenquotes", language="nl")

    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["fallback"] is True
    assert state.attributes["language"] == "nl"
    assert state.state == daily_quote(dt_util.now().date(), "nl").text

    # No retry within the hour.
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1

    # The source works again: switch to an online quote the same day.
    aioclient_mock.clear_requests()
    aioclient_mock.get(ZENQUOTES_BATCH_URL, json=ZEN_BATCH)
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["fallback"] is False
    assert state.state in {q["q"] for q in ZEN_BATCH}


async def test_options_and_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass, language="nl")
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "nl"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"source": "builtin", "language": "en", "cache_days": 28}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "en"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED

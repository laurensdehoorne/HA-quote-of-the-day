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

from custom_components.quote_of_the_day.const import (
    BRAINYQUOTE_RSS_URL,
    DOMAIN,
    FAVQS_QOTD_URL,
    ZENQUOTES_BATCH_URL,
)
from custom_components.quote_of_the_day.quotes import (
    is_motivational,
    quotes_for_language,
)

QUOTE_SENSOR = "sensor.quote_of_the_day_quote"
AUTHOR_SENSOR = "sensor.quote_of_the_day_author"
NEW_QUOTE_BUTTON = "button.quote_of_the_day_new_quote"

ZEN_BATCH = [{"q": f"Zen quote number {i}.", "a": f"Author {i}"} for i in range(5)]
BRAINY_RSS = (
    "<rss><channel><item><title>Walt Disney</title>"
    "<description>&quot;Brainy quote of the day.&quot;</description></item>"
    "</channel></rss>"
)
FAVQS_QOTD = {"quote": {"author": "Ada Lovelace", "body": "FavQs quote of the day."}}

ONLINE_TEXTS = {q["q"] for q in ZEN_BATCH} | {
    "Brainy quote of the day.",
    "FavQs quote of the day.",
}


def _mock_online(aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(ZENQUOTES_BATCH_URL, json=ZEN_BATCH)
    aioclient_mock.get(BRAINYQUOTE_RSS_URL, text=BRAINY_RSS)
    aioclient_mock.get(FAVQS_QOTD_URL, json=FAVQS_QOTD)


async def _setup(hass: HomeAssistant, **data) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quote of the Day",
        version=2,
        data={
            "sources": ["builtin"],
            "language": "all",
            "cache_days": 28,
            "on_this_day": False,
            "theme": "all",
            **data,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _next_day(hass: HomeAssistant, freezer: FrozenDateTimeFactory, days: int = 1):
    freezer.tick(timedelta(days=days))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    return hass.states.get(QUOTE_SENSOR)


async def test_config_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_online(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    user_input = {
        "theme": "motivational",
        "sources": ["builtin", "zenquotes", "brainyquote", "favqs"],
        "language": "all",
        "cache_days": 14,
        "on_this_day": False,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == user_input
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR) is not None

    # Only one instance allowed.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_builtin_only(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    await _setup(hass, language="nl")
    builtin = {q.text: q for q in quotes_for_language("nl")}

    state = hass.states.get(QUOTE_SENSOR)
    quote = builtin[state.state]
    assert state.attributes["quote"] == quote.text
    assert state.attributes["author"] == quote.author
    assert state.attributes["reference"] == quote.reference
    assert state.attributes["source"] == "builtin"
    assert state.attributes["fallback"] is False
    assert "cached_quotes" not in state.attributes
    assert "attribution" not in state.attributes
    assert hass.states.get(AUTHOR_SENSOR).state == quote.author

    # No repeats until every quote has been shown.
    shown = [state.state]
    for _ in range(len(builtin) - 1):
        shown.append((await _next_day(hass, freezer)).state)
    assert sorted(shown) == sorted(builtin)

    registry = er.async_get(hass)
    assert registry.async_get(QUOTE_SENSOR).unique_id.endswith("_quote")


async def test_combines_sources_and_caches(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    _mock_online(aioclient_mock)
    await _setup(
        hass,
        sources=["builtin", "zenquotes", "brainyquote", "favqs"],
        language="en",
        cache_days=28,
    )
    # Each online source is contacted exactly once.
    assert aioclient_mock.call_count == 3

    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["cached_quotes"] == 7
    assert state.attributes["entries"] == [
        {"title": state.attributes["author"], "summary": state.state}
    ]

    # Over the following weeks quotes from every source show up, all from cache.
    pool = ONLINE_TEXTS | {q.text for q in quotes_for_language("en")}
    shown = {state.state}
    sources = {state.attributes["source"]}
    for _ in range(len(pool) - 1):
        state = await _next_day(hass, freezer)
        shown.add(state.state)
        sources.add(state.attributes["source"])
        if state.attributes["source"] != "builtin":
            assert state.attributes["attribution"]
    assert shown == pool
    assert sources == {"builtin", "zenquotes", "brainyquote", "favqs"}

    # 28 days have long passed, so the cache was refreshed in between.
    assert aioclient_mock.call_count > 3


async def test_cache_is_not_refreshed_early(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    _mock_online(aioclient_mock)
    await _setup(hass, sources=["zenquotes"], cache_days=14)
    assert aioclient_mock.call_count == 1

    for _ in range(13):
        await _next_day(hass, freezer)
    assert aioclient_mock.call_count == 1

    # New batch: merged, duplicates skipped.
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        ZENQUOTES_BATCH_URL,
        json=[*ZEN_BATCH, {"q": "A brand new quote here.", "a": "New Author"}],
    )
    state = await _next_day(hass, freezer)
    assert aioclient_mock.call_count == 1
    assert state.attributes["cached_quotes"] == 6


async def test_bad_online_quotes_are_filtered(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        ZENQUOTES_BATCH_URL,
        json=[
            {"q": "A genuinely good quote to keep.", "a": "Good Author"},
            {"q": "Nobody knows who said this one.", "a": "Unknown"},
            {"q": "Too short", "a": "Someone"},
        ],
    )
    await _setup(hass, sources=["zenquotes"])
    state = hass.states.get(QUOTE_SENSOR)
    assert state.state == "A genuinely good quote to keep."
    assert state.attributes["cached_quotes"] == 1


async def test_new_quote_button_and_restart(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_online(aioclient_mock)
    entry = await _setup(hass, sources=["builtin", "zenquotes"])
    before = hass.states.get(QUOTE_SENSOR).state

    await hass.services.async_call(
        "button", "press", {"entity_id": NEW_QUOTE_BUTTON}, blocking=True
    )
    pressed = hass.states.get(QUOTE_SENSOR).state
    assert pressed != before

    calls = aioclient_mock.call_count
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).state == pressed
    # The cache survived the restart: no new requests.
    assert aioclient_mock.call_count == calls


async def test_online_fallback_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    aioclient_mock.get(ZENQUOTES_BATCH_URL, status=500)
    await _setup(hass, sources=["zenquotes"], language="en")

    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["fallback"] is True
    assert state.attributes["source"] == "builtin"

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
    assert state.state in ONLINE_TEXTS


async def test_one_source_down_others_still_used(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(ZENQUOTES_BATCH_URL, status=500)
    aioclient_mock.get(BRAINYQUOTE_RSS_URL, text=BRAINY_RSS)
    aioclient_mock.get(FAVQS_QOTD_URL, json=FAVQS_QOTD)
    await _setup(hass, sources=["zenquotes", "brainyquote", "favqs"])
    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["fallback"] is False
    assert state.attributes["cached_quotes"] == 2
    assert state.state in {"Brainy quote of the day.", "FavQs quote of the day."}


async def test_dutch_skips_english_online_sources(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    _mock_online(aioclient_mock)
    await _setup(hass, sources=["builtin", "zenquotes"], language="nl")
    assert aioclient_mock.call_count == 0
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "nl"


async def test_migrate_v1(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    _mock_online(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"source": "zenquotes", "language": "all"},
        options={"source": "builtin", "language": "en"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert entry.data == {"sources": ["builtin", "zenquotes"], "language": "all"}
    assert entry.options == {"sources": ["builtin"], "language": "en"}


async def test_options_and_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass, language="nl")
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "nl"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {
            "theme": "all",
            "sources": ["builtin"],
            "language": "en",
            "cache_days": 28,
            "on_this_day": False,
        }
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).attributes["language"] == "en"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


DISLIKE_BUTTON = "button.quote_of_the_day_dislike_quote"
RESTORE_BUTTON = "button.quote_of_the_day_restore_disliked_quotes"


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)


async def test_dislike_quote(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    entry = await _setup(hass, language="nl")
    disliked = hass.states.get(QUOTE_SENSOR).state

    await _press(hass, DISLIKE_BUTTON)
    state = hass.states.get(QUOTE_SENSOR)
    assert state.state != disliked
    assert state.attributes["disliked_quotes"] == 1

    # Never shown again: not in a whole round, and not after a restart.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).attributes["disliked_quotes"] == 1
    shown = set()
    for _ in range(len(quotes_for_language("nl")) * 2):
        shown.add((await _next_day(hass, freezer)).state)
    assert disliked not in shown
    assert len(shown) == len(quotes_for_language("nl")) - 1

    # Restore: allowed again.
    await _press(hass, RESTORE_BUTTON)
    assert hass.states.get(QUOTE_SENSOR).attributes["disliked_quotes"] == 0
    shown = set()
    for _ in range(len(quotes_for_language("nl"))):
        shown.add((await _next_day(hass, freezer)).state)
    assert disliked in shown


async def test_dislike_everything_still_shows_a_quote(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        ZENQUOTES_BATCH_URL, json=[{"q": "The one and only good quote.", "a": "Someone"}]
    )
    await _setup(hass, sources=["zenquotes"])
    await _press(hass, DISLIKE_BUTTON)
    assert hass.states.get(QUOTE_SENSOR).state == "The one and only good quote."


async def test_motivational_theme(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    aioclient_mock.get(
        ZENQUOTES_BATCH_URL,
        json=[
            {"q": "Keep going, every small step counts.", "a": "Coach"},
            {"q": "The cat sat quietly on the warm mat.", "a": "Poet"},
        ],
    )
    entry = await _setup(
        hass, sources=["builtin", "zenquotes"], language="all", theme="motivational"
    )
    pool = {q.text for q in quotes_for_language("all") if is_motivational(q)}
    pool.add("Keep going, every small step counts.")

    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["theme"] == "motivational"
    assert state.attributes["motivational"] is True
    shown = {state.state}
    for _ in range(len(pool) - 1):
        state = await _next_day(hass, freezer)
        assert state.attributes["motivational"] is True
        shown.add(state.state)
    # Every motivational quote, including the online one; nothing else.
    assert shown == pool

    # Switching the theme picks a quote from the whole collection again.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "theme": "all",
            "sources": ["builtin", "zenquotes"],
            "language": "all",
            "cache_days": 28,
            "on_this_day": False,
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get(QUOTE_SENSOR)
    assert state.attributes["theme"] == "all"


async def test_motivational_theme_without_matches_still_shows_a_quote(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        ZENQUOTES_BATCH_URL, json=[{"q": "The cat sat quietly on the warm mat.", "a": "Poet"}]
    )
    await _setup(hass, sources=["zenquotes"], theme="motivational")
    state = hass.states.get(QUOTE_SENSOR)
    assert state.state == "The cat sat quietly on the warm mat."
    assert state.attributes["motivational"] is False

"""Tests for the famous birthday and the fact of the day."""

from __future__ import annotations

from datetime import date, timedelta
import re

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_UNAVAILABLE

from custom_components.quote_of_the_day.const import DOMAIN
from custom_components.quote_of_the_day.onthisday import (
    OnThisDayError,
    parse_births,
    parse_events,
    parse_pageviews,
    pick_birthday,
    pick_fact,
)

BIRTHDAY_SENSOR = "sensor.quote_of_the_day_birthday"
FACT_SENSOR = "sensor.quote_of_the_day_on_this_day"
QUOTE_SENSOR = "sensor.quote_of_the_day_quote"


def _page(title: str, description: str = "", image: bool = True) -> dict:
    page = {
        "title": title.replace(" ", "_"),
        "titles": {"canonical": title.replace(" ", "_"), "normalized": title},
        "description": description,
        "extract": f"{title} is notable. " * 3,
        "content_urls": {
            "desktop": {"page": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}
        },
    }
    if image:
        page["thumbnail"] = {"source": f"https://upload.wikimedia.org/{title}.jpg"}
    return page


BIRTHS = {
    "births": [
        {
            "text": "Obscure Person, local politician",
            "year": 1990,
            "pages": [_page("Obscure Person", "politician", image=False)],
        },
        {
            "text": "Marie Curie, Polish-French physicist and chemist (d. 1934)",
            "year": 1867,
            "pages": [_page("Marie Curie", "physicist and chemist"), _page("Physics")],
        },
        {
            "text": "Somebody (footballer), English footballer",
            "year": 1980,
            "pages": [_page("Somebody (footballer)", "footballer")],
        },
        {"text": "No pages", "year": 1800, "pages": []},
    ]
}
PAGEVIEWS = {
    "query": {
        "pages": [
            {"title": "Obscure Person", "pageviews": {"2026-10-01": 3, "2026-10-02": None}},
            {"title": "Marie Curie", "pageviews": {"2026-10-01": 9000, "2026-10-02": 8000}},
            {"title": "Somebody (footballer)", "pageviews": {"2026-10-01": 400}},
        ]
    }
}
SELECTED = {
    "selected": [
        {
            "text": "A treaty is signed between two kingdoms.",
            "year": 1648,
            "pages": [_page("Peace of Westphalia", "series of peace treaties")],
        },
        {
            "text": "Sputnik 1 becomes the first artificial satellite to orbit Earth.",
            "year": 1957,
            "pages": [_page("Sputnik 1", "first artificial Earth satellite")],
        },
    ]
}


def test_parse_births_and_pick_most_viewed() -> None:
    candidates = parse_births(BIRTHS)
    assert [c.name for c in candidates] == [
        "Marie Curie",
        "Somebody",  # disambiguation removed, photo first
        "Obscure Person",
    ]
    birthday = pick_birthday(candidates, parse_pageviews(PAGEVIEWS))
    assert birthday.name == "Marie Curie"
    assert birthday.year == 1867
    assert birthday.description == "Polish-French physicist and chemist (d. 1934)"
    assert birthday.url.endswith("/Marie_Curie")
    assert birthday.image
    assert birthday.pageviews == 17000


def test_pick_birthday_without_pageviews() -> None:
    birthday = pick_birthday(parse_births(BIRTHS), {})
    assert birthday is not None
    assert birthday.image is not None


def test_parse_events_categories() -> None:
    facts = parse_events(SELECTED)
    assert [(f.year, f.category) for f in facts] == [(1648, "history"), (1957, "science")]
    assert facts[1].title == "Sputnik 1"


def test_pick_fact_is_deterministic_and_prefers_science() -> None:
    facts = parse_events(SELECTED)
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(400)]
    picks = [pick_fact(facts, d) for d in days]
    assert pick_fact(facts, days[0]) == picks[0]
    science = sum(p.category == "science" for p in picks)
    assert 250 < science < 350  # weight 3:1
    assert pick_fact([], days[0]) is None


@pytest.mark.parametrize("data", [[], {}, {"births": "x"}])
def test_parse_births_errors(data) -> None:
    with pytest.raises(OnThisDayError):
        parse_births(data)


@pytest.mark.parametrize("data", [[], {}, {"selected": None}])
def test_parse_events_errors(data) -> None:
    with pytest.raises(OnThisDayError):
        parse_events(data)


def _mock_wiki(aioclient_mock: AiohttpClientMocker, lang: str = "en") -> None:
    base = f"https://{lang}.wikipedia.org"
    for month_day in ("11/04", "11/05", "11/06", "11/07", "11/08", "11/09", "11/10"):
        aioclient_mock.get(f"{base}/api/rest_v1/feed/onthisday/births/{month_day}", json=BIRTHS)
        aioclient_mock.get(
            f"{base}/api/rest_v1/feed/onthisday/selected/{month_day}", json=SELECTED
        )
    aioclient_mock.get(f"{base}/w/api.php", json=PAGEVIEWS)


async def _setup(hass: HomeAssistant, language: str = "en") -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            "sources": ["builtin"],
            "language": language,
            "cache_days": 28,
            "on_this_day": True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _feed_calls(aioclient_mock: AiohttpClientMocker) -> list[str]:
    return [str(url) for _, url, _, _ in aioclient_mock.mock_calls if "onthisday" in str(url)]


async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    _mock_wiki(aioclient_mock)
    await _setup(hass)

    birthday = hass.states.get(BIRTHDAY_SENSOR)
    assert birthday.state == "Marie Curie"
    assert birthday.attributes["born"] == 1867
    assert birthday.attributes["years_ago"] == 159
    assert birthday.attributes["entity_picture"].endswith("Marie Curie.jpg")
    assert "Wikipedia" in birthday.attributes["attribution"]

    fact = hass.states.get(FACT_SENSOR)
    assert fact.attributes["year"] in (1648, 1957)
    assert fact.state == f"{fact.attributes['year']}: {fact.attributes['text']}"
    assert fact.attributes["category"] in ("science", "history")
    assert fact.attributes["years_ago"] == 2026 - fact.attributes["year"]

    # Today plus one day ahead were fetched (2 per update).
    assert len(_feed_calls(aioclient_mock)) == 4


async def test_prefetch_and_offline(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    _mock_wiki(aioclient_mock)
    entry = await _setup(hass)

    # Over a few updates the coming week is fetched ahead.
    for _ in range(3):
        freezer.tick(timedelta(minutes=31))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert len(_feed_calls(aioclient_mock)) == 14  # 7 days x (births + selected)

    # Internet gone: the next days still work from the cache, also after restart.
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r"https://en\.wikipedia\.org/.*"), status=503)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(days=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(BIRTHDAY_SENSOR).state == "Marie Curie"
    assert hass.states.get(FACT_SENSOR).state != STATE_UNAVAILABLE


async def test_wikipedia_down_does_not_break_quote(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(
        "https://en.wikipedia.org/api/rest_v1/feed/onthisday/births/11/04", status=503
    )
    aioclient_mock.get(
        "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/11/04", status=503
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"sources": ["builtin"], "language": "en", "cache_days": 28, "on_this_day": True},
    )
    entry.add_to_hass(hass)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "custom_components.quote_of_the_day.onthisday_coordinator.PREFETCH_DAYS", 1
        )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(QUOTE_SENSOR).state != STATE_UNAVAILABLE
    assert hass.states.get(BIRTHDAY_SENSOR).state == STATE_UNAVAILABLE
    assert hass.states.get(FACT_SENSOR).state == STATE_UNAVAILABLE


async def test_dutch_falls_back_to_english(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    for kind in ("births", "selected"):
        for md in ("11/04", "11/05"):
            aioclient_mock.get(
                f"https://nl.wikipedia.org/api/rest_v1/feed/onthisday/{kind}/{md}",
                status=404,
            )
    _mock_wiki(aioclient_mock)
    await _setup(hass, language="nl")
    state = hass.states.get(BIRTHDAY_SENSOR)
    assert state.state == "Marie Curie"
    assert state.attributes["language"] == "en"


async def test_disabled(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"sources": ["builtin"], "language": "en", "cache_days": 28, "on_this_day": False},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(BIRTHDAY_SENSOR) is None
    assert hass.states.get(FACT_SENSOR) is None

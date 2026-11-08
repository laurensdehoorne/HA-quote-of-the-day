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
    "events": [
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


def _fact(text: str, year: int) -> dict:
    return {"text": text, "year": year, "pages": [_page(text[:20])]}


EVENTS = {
    "events": [
        _fact("The first powered aircraft flight takes place.", 1903),
        _fact("A great battle is fought between two empires.", 2001),
        _fact("An earthquake strikes the capital, killing hundreds.", 2010),
        _fact("The new parliament is elected after a long campaign.", 2015),
        _fact("The James Webb Space Telescope sends its first images.", 2022),
        _fact("The band releases its debut album to wide acclaim.", 2019),
        _fact("The country adopts a new currency.", 2005),
    ]
}


def test_parse_events_categories() -> None:
    facts = parse_events(SELECTED)
    assert [(f.year, f.category) for f in facts] == [(1648, "history"), (1957, "science")]
    assert facts[1].title == "Sputnik 1"
    assert parse_events({"selected": SELECTED["events"]}) == facts
    categories = {f.text[:12]: f.category for f in parse_events(EVENTS)}
    assert categories["The band rel"] == "culture"
    assert categories["The James We"] == "science"
    assert categories["The country "] == "history"


def test_pick_fact_recent_and_upbeat() -> None:
    facts = parse_events(EVENTS)
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(600)]
    picks = [pick_fact(facts, d) for d in days]
    assert pick_fact(facts, days[0]) == picks[0]  # deterministic per day
    counts = {f.text[:12]: sum(p == f for p in picks) for f in facts}
    # Never war or disasters, never the event of more than 50 years ago.
    assert counts["A great batt"] == counts["An earthquak"] == 0
    assert counts["The first po"] == 0
    # Science and culture (4) > other (1) > politics (0.5).
    assert counts["The James We"] > 3 * counts["The country "]
    assert counts["The band rel"] > 3 * counts["The country "]
    assert counts["The country "] > counts["The new parl"] > 0
    assert pick_fact([], days[0]) is None


def test_pick_fact_falls_back_to_older_and_gloomy() -> None:
    old = parse_events({"events": [_fact("The first powered aircraft flight.", 1903)]})
    assert pick_fact(old, date(2026, 1, 1)) == old[0]
    gloomy = parse_events({"events": [_fact("A great battle is fought.", 2001)]})
    assert pick_fact(gloomy, date(2026, 1, 1)) == gloomy[0]


@pytest.mark.parametrize("data", [[], {}, {"births": "x"}])
def test_parse_births_errors(data) -> None:
    with pytest.raises(OnThisDayError):
        parse_births(data)


@pytest.mark.parametrize("data", [[], {}, {"events": None}])
def test_parse_events_errors(data) -> None:
    with pytest.raises(OnThisDayError):
        parse_events(data)


def _mock_wiki(aioclient_mock: AiohttpClientMocker, lang: str = "en") -> None:
    base = f"https://{lang}.wikipedia.org"
    for month_day in ("11/04", "11/05", "11/06", "11/07", "11/08", "11/09", "11/10"):
        aioclient_mock.get(f"{base}/api/rest_v1/feed/onthisday/births/{month_day}", json=BIRTHS)
        aioclient_mock.get(
            f"{base}/api/rest_v1/feed/onthisday/events/{month_day}", json=SELECTED
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
    assert len(_feed_calls(aioclient_mock)) == 14  # 7 days x (births + events)

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
        "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/11/04", status=503
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
    for kind in ("births", "events"):
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

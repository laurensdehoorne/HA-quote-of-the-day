"""Tests for the motivational quote written by AI."""

from __future__ import annotations

from datetime import date, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from custom_components.quote_of_the_day.ai_quote import (
    AiQuoteError,
    build_instructions,
    language_name,
    parse_response,
)
from custom_components.quote_of_the_day.const import DOMAIN

AI_SENSOR = "sensor.quote_of_the_day_ai_quote"
AI_BUTTON = "button.quote_of_the_day_new_ai_quote"
QUOTE_SENSOR = "sensor.quote_of_the_day_quote"
AI_ENTITY = "ai_task.test_ai"


class FakeAiTask:
    """Stands in for the ai_task.generate_data action."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.calls: list[dict] = []
        self.fail = False
        hass.services.async_register(
            "ai_task",
            "generate_data",
            self._generate,
            supports_response=SupportsResponse.ONLY,
        )

    async def _generate(self, call: ServiceCall) -> dict:
        self.calls.append(dict(call.data))
        if self.fail:
            raise HomeAssistantError("AI is down")
        return {
            "conversation_id": "x",
            "data": {"quote": f"“Small steps today build big things, number {len(self.calls)}.”"},
        }


async def _setup(hass: HomeAssistant, **data) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quote of the Day",
        version=2,
        data={
            "sources": ["builtin"],
            "language": "nl",
            "cache_days": 28,
            "on_this_day": False,
            "theme": "motivational",
            "ai_task_entity": AI_ENTITY,
            **data,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_ai_quote_daily(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    ai = FakeAiTask(hass)
    entry = await _setup(hass, ai_instructions="about running")

    state = hass.states.get(AI_SENSOR)
    assert state.state == "Small steps today build big things, number 1."
    assert state.attributes["quote"] == state.state
    assert state.attributes["date"] == "2026-11-04"
    assert state.attributes["language"] == "nl"
    assert state.attributes["ai_task_entity"] == AI_ENTITY

    (call,) = ai.calls
    assert call["entity_id"] == AI_ENTITY
    assert call["structure"]["quote"]["required"] is True
    assert "Dutch" in call["instructions"]
    assert "about running" in call["instructions"]

    # Same day, restart: no new call.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(ai.calls) == 1
    assert hass.states.get(AI_SENSOR).state.endswith("number 1.")

    # Next day: a new quote, and the AI is told about the earlier one.
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(ai.calls) == 2
    assert "number 1." in ai.calls[1]["instructions"]
    state = hass.states.get(AI_SENSOR)
    assert state.state.endswith("number 2.")
    assert state.attributes["date"] == "2026-11-05"

    # Button: a new one right away.
    await hass.services.async_call("button", "press", {"entity_id": AI_BUTTON}, blocking=True)
    assert hass.states.get(AI_SENSOR).state.endswith("number 3.")


@pytest.mark.parametrize(
    ("language", "ai_language", "expected"),
    [
        ("nl", "auto", "Dutch"),
        ("en", "auto", "English"),
        ("all", "auto", "English"),  # Home Assistant's language (en in tests)
        ("all", "nl", "Dutch"),
        ("en", "nl", "Dutch"),
        ("nl", "en", "English"),
    ],
)
async def test_ai_quote_language(
    hass: HomeAssistant, language: str, ai_language: str, expected: str
) -> None:
    ai = FakeAiTask(hass)
    await _setup(hass, language=language, ai_language=ai_language)
    assert f"Write it in {expected}." in ai.calls[0]["instructions"]
    lang = {"Dutch": "nl", "English": "en"}[expected]
    assert hass.states.get(AI_SENSOR).attributes["language"] == lang


async def test_ai_failure(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.move_to("2026-11-04 12:00:00+00:00")
    ai = FakeAiTask(hass)
    ai.fail = True
    await _setup(hass)

    # The AI quote is unavailable, the normal quote still works.
    assert hass.states.get(AI_SENSOR).state == "unavailable"
    assert hass.states.get(QUOTE_SENSOR).state not in ("unavailable", "unknown")
    assert len(ai.calls) == 1

    # No retry within the hour.
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(ai.calls) == 1

    # The button reports the error.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button", "press", {"entity_id": AI_BUTTON}, blocking=True
        )

    # Works again after the hour.
    ai.fail = False
    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(AI_SENSOR).state.endswith(".")
    assert hass.states.get(AI_SENSOR).state != "unavailable"

    # A failure the next day keeps yesterday's quote.
    ai.fail = True
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(AI_SENSOR)
    assert state.state != "unavailable"
    assert state.attributes["date"] == "2026-11-04"


async def test_ai_task_not_available(hass: HomeAssistant) -> None:
    # No ai_task integration at all (e.g. older Home Assistant).
    await _setup(hass)
    assert hass.states.get(AI_SENSOR).state == "unavailable"
    assert hass.states.get(QUOTE_SENSOR).state not in ("unavailable", "unknown")


async def test_no_ai_entity_no_ai_sensor(hass: HomeAssistant) -> None:
    await _setup(hass, ai_task_entity="")
    assert hass.states.get(AI_SENSOR) is None
    assert hass.states.get(AI_BUTTON) is None


async def test_options_turn_ai_off(hass: HomeAssistant) -> None:
    FakeAiTask(hass)
    entry = await _setup(hass)
    assert hass.states.get(AI_SENSOR) is not None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    schema_keys = {str(key) for key in result["data_schema"].schema}
    assert {"ai_task_entity", "ai_instructions"} <= schema_keys
    # The AI field is cleared: the value from setup must not come back.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "theme": "motivational",
            "sources": ["builtin"],
            "language": "nl",
            "cache_days": 28,
            "on_this_day": False,
        },
    )
    await hass.async_block_till_done()
    assert entry.options["ai_task_entity"] == ""
    assert hass.states.get(AI_SENSOR) is None


def test_build_instructions() -> None:
    text = build_instructions(
        date(2026, 11, 9), "nl", [f"old {i}" for i in range(20)], "  for my team  "
    )
    assert "Monday 2026-11-09" in text
    assert "Write it in Dutch." in text
    assert "Wishes of the reader: for my team" in text
    assert "- old 19" in text
    assert "- old 5" not in text  # only the most recent ones
    # Each day has its own angle.
    assert build_instructions(date(2026, 11, 9), "en", []) != build_instructions(
        date(2026, 11, 10), "en", []
    )


def test_language_name() -> None:
    assert language_name("nl") == "Dutch"
    assert language_name("en-GB") == "English"
    assert language_name("xx") == "the language with code 'xx'"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"data": {"quote": "Begin where you are, today."}}, "Begin where you are, today."),
        ({"data": "  “Begin where you are,\n today.”  "}, "Begin where you are, today."),
        ({"data": {"quote": '"Begin where you are." — Seneca'}}, "Begin where you are."),
        ({"data": {"quote": "Doorzetten loont – altijd weer."}}, "Doorzetten loont – altijd weer."),
    ],
)
def test_parse_response(response, expected: str) -> None:
    assert parse_response(response) == expected


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"data": {"other": "x"}},
        {"data": {"quote": "Too short"}},
        {"data": {"quote": "See https://example.com for more motivation."}},
        {"data": {"quote": "x" * 400}},
    ],
)
def test_parse_response_errors(response) -> None:
    with pytest.raises(AiQuoteError):
        parse_response(response)

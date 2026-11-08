"""Tests for the dashboard card in the README (built-in cards only)."""

from __future__ import annotations

from pathlib import Path
import re

import pytest
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

README = Path(__file__).parent.parent / "README.md"

QUOTE = "sensor.quote_of_the_day_quote"
AI = "sensor.quote_of_the_day_ai_quote"
BIRTHDAY = "sensor.quote_of_the_day_birthday"
FACT = "sensor.quote_of_the_day_on_this_day"
BUTTONS = {
    "button.quote_of_the_day_new_quote",
    "button.quote_of_the_day_dislike_quote",
    "button.quote_of_the_day_new_ai_quote",
}


def _card() -> dict:
    """The first YAML block of the "Dashboard card" section."""
    section = README.read_text(encoding="utf-8").split("## Dashboard card", 1)[1]
    block = re.search(r"```yaml\n(.*?)```", section, re.DOTALL)
    assert block
    return yaml.safe_load(block.group(1))


def _markdown(card: dict) -> str:
    (markdown,) = [c for c in card["cards"] if c["type"] == "markdown"]
    return markdown["content"]


def _set_states(hass: HomeAssistant, *, ai: bool, on_this_day: bool) -> None:
    hass.states.async_set(
        QUOTE,
        "x",
        {
            "quote": "Ever tried. Ever failed. No matter.",
            "author": "Samuel Beckett",
            "reference": "Worstward Ho (1983)",
        },
    )
    if ai:
        hass.states.async_set(AI, "x", {"quote": "Begin where you are, today."})
    if on_this_day:
        hass.states.async_set(
            BIRTHDAY,
            "Ada Lovelace",
            {
                "name": "Ada Lovelace",
                "description": "English mathematician",
                "born": 1815,
                "years_ago": 211,
                "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
                "entity_picture": "https://upload.wikimedia.org/ada.jpg",
            },
        )
        hass.states.async_set(
            FACT,
            "x",
            {
                "year": 1895,
                "text": "Wilhelm Röntgen discovers X-rays.",
                "years_ago": 131,
                "category": "science",
                "url": "https://en.wikipedia.org/wiki/X-ray",
            },
        )


def _check_markdown(text: str) -> None:
    # A "---" right under a line of text would turn that line into a heading.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "---":
            assert i == 0 or not lines[i - 1].strip(), text
    assert "None" not in text, text


async def test_card_everything(hass: HomeAssistant) -> None:
    _set_states(hass, ai=True, on_this_day=True)
    text = Template(_markdown(_card()), hass).async_render(parse_result=False)
    _check_markdown(text)
    assert "> *Ever tried. Ever failed. No matter.*" in text
    assert "**— Samuel Beckett**<br><small>Worstward Ho (1983)</small>" in text
    assert "**Begin where you are, today.**" in text
    assert '<img src="https://upload.wikimedia.org/ada.jpg" height="80">' in text
    assert "**Ada Lovelace**, English mathematician" in text
    assert "born 1815 · 211 years ago" in text
    assert "mdi:flask-outline" in text
    assert "**1895**: Wilhelm Röntgen discovers X-rays." in text


@pytest.mark.parametrize("nl", [False, True])
async def test_card_labels(hass: HomeAssistant, nl: bool) -> None:
    _set_states(hass, ai=True, on_this_day=True)
    content = _markdown(_card())
    if nl:
        content = content.replace("set nl = false", "set nl = true")
    text = Template(content, hass).async_render(parse_result=False)
    assert ("Citaat van de dag" in text) is nl
    assert ("Quote of the day" in text) is not nl
    assert ("211 jaar geleden" in text) is nl


async def test_card_without_ai_and_on_this_day(hass: HomeAssistant) -> None:
    _set_states(hass, ai=False, on_this_day=False)
    text = Template(_markdown(_card()), hass).async_render(parse_result=False)
    _check_markdown(text)
    assert "Ever tried" in text
    assert "motivation" not in text
    assert "Born today" not in text
    assert "On this day" not in text
    assert "---" not in text


def test_card_buttons() -> None:
    card = _card()
    assert card["type"] == "vertical-stack"
    (grid,) = [c for c in card["cards"] if c["type"] == "grid"]
    pressed = set()
    for button in grid["cards"]:
        action = button["tap_action"]
        assert action["action"] == "perform-action"
        assert action["perform_action"] == "button.press"
        pressed.add(action["target"]["entity_id"])
    assert pressed == BUTTONS

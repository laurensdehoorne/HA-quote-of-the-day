"""A motivational quote written by AI, through Home Assistant's AI Task.

The quote is generated with the ``ai_task.generate_data`` action, so any AI
Task entity works (OpenAI, Google Gemini, Anthropic, Ollama, ...). The AI is
asked for an original sentence of its own: it is never presented as a quote
by a real person, so it cannot be a misattributed one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

AI_TASK_DOMAIN = "ai_task"
SERVICE_GENERATE_DATA = "generate_data"
TASK_NAME = "Quote of the Day: motivational quote"

MIN_LENGTH = 10
MAX_LENGTH = 300
# Earlier AI quotes passed to the AI, so it does not repeat itself.
HISTORY_IN_PROMPT = 14

LANGUAGE_NAMES = {
    "en": "English",
    "nl": "Dutch",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "da": "Danish",
    "sv": "Swedish",
    "nb": "Norwegian",
    "fi": "Finnish",
    "pl": "Polish",
}

# A different angle each day, so the quotes don't all sound the same.
DAILY_ANGLES = (
    "perseverance when things get hard",
    "the courage to start something",
    "small steps and steady progress",
    "discipline and good habits",
    "learning from failure and trying again",
    "growing beyond your comfort zone",
    "focus on what you can control",
    "self-belief",
    "patience with yourself",
    "making today count",
    "kindness and helping others forward",
    "curiosity and learning something new",
    "rest as part of doing great work",
    "gratitude for how far you have come",
)

STRUCTURE = {
    "quote": {
        "description": "The motivational quote, without quotation marks or author.",
        "required": True,
        "selector": {"text": {}},
    }
}

_URL_RE = re.compile(r"https?://|www\.")
# "... — Seneca" at the end: the AI attributed its own sentence to someone.
# A name starts with a capital and does not end like a sentence.
_ATTRIBUTION_RE = re.compile(r"\s+(?:[—–]|--?)\s*[A-ZÀ-Þ][^!?—–]{0,40}(?<![.!?])$")
_WRAPPING_QUOTES = "\"'“”‘’„«»"


class AiQuoteError(Exception):
    """Raised when the AI could not write a usable quote."""


@dataclass(frozen=True, slots=True)
class AiQuote:
    """A quote written by AI for a day."""

    text: str
    day: date
    language: str
    entity_id: str
    settings: str

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {**asdict(self), "day": self.day.isoformat()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AiQuote:
        """Deserialize from storage."""
        return cls(
            text=str(data["text"]),
            day=date.fromisoformat(data["day"]),
            language=str(data.get("language") or "en"),
            entity_id=str(data.get("entity_id") or ""),
            settings=str(data.get("settings") or ""),
        )


def language_name(code: str) -> str:
    """Name of a language for the prompt, e.g. "nl" -> "Dutch"."""
    code = code.split("-")[0].lower()
    return LANGUAGE_NAMES.get(code, f"the language with code '{code}'")


def build_instructions(
    day: date, language: str, previous: list[str], extra: str = ""
) -> str:
    """Return the prompt for today's quote."""
    angle = DAILY_ANGLES[day.toordinal() % len(DAILY_ANGLES)]
    lines = [
        "Write one short, original motivational quote for today.",
        f"Today is {day.strftime('%A')} {day.isoformat()}. "
        f"Today's angle: {angle}.",
        "",
        "Rules:",
        f"- Write it in {language_name(language)}.",
        "- At most 25 words; one or two sentences that read well aloud.",
        "- Encouraging, warm and concrete; no clichés, no toxic positivity.",
        "- It must be your own new sentence: do not quote or paraphrase an "
        "existing quote, and do not attribute it to anyone.",
        "- No quotation marks, author, hashtags, emoji or links.",
    ]
    if extra.strip():
        lines += ["", f"Wishes of the reader: {extra.strip()}"]
    if previous:
        lines += ["", "Do not repeat or closely resemble these earlier quotes:"]
        lines += [f"- {text}" for text in previous[-HISTORY_IN_PROMPT:]]
    return "\n".join(lines)


def _unwrap(text: str) -> str:
    """Remove quotation marks around the whole text."""
    text = text.strip()
    while len(text) > 1 and text[0] in _WRAPPING_QUOTES and text[-1] in _WRAPPING_QUOTES:
        text = text[1:-1].strip()
    return text


def parse_response(response: Any) -> str:
    """Get the quote from the ``ai_task.generate_data`` response."""
    data = response.get("data") if isinstance(response, dict) else None
    if isinstance(data, dict):
        data = data.get("quote")
    if not isinstance(data, str):
        raise AiQuoteError(f"Unexpected AI response: {response!r:.200}")
    text = _unwrap(_ATTRIBUTION_RE.sub("", _unwrap(" ".join(data.split()))))
    if not MIN_LENGTH <= len(text) <= MAX_LENGTH or _URL_RE.search(text):
        raise AiQuoteError(f"Unusable AI quote: {text!r:.200}")
    return text


async def async_generate(
    hass: HomeAssistant, entity_id: str, instructions: str
) -> str:
    """Ask the AI Task entity for a quote."""
    try:
        response = await hass.services.async_call(
            AI_TASK_DOMAIN,
            SERVICE_GENERATE_DATA,
            {
                "task_name": TASK_NAME,
                "entity_id": entity_id,
                "instructions": instructions,
                "structure": STRUCTURE,
            },
            blocking=True,
            return_response=True,
        )
    except (HomeAssistantError, vol.Invalid, TimeoutError) as err:
        raise AiQuoteError(f"AI Task {entity_id} failed: {err}") from err
    return parse_response(response)

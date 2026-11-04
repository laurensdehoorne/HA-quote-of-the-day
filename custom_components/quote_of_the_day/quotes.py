"""Built-in quote collection and selection helpers.

The built-in collection works fully offline. The quote of the day is picked
deterministically from the date, so every restart on the same day gives the
same quote, and no quote is repeated until the whole list has been shown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import random
from typing import Any

from .const import LANGUAGE_ALL, LANGUAGE_EN, LANGUAGE_NL


@dataclass(frozen=True, slots=True)
class Quote:
    """A single quote."""

    text: str
    author: str
    language: str

    def as_dict(self) -> dict[str, Any]:
        """Return the quote as a dict (for storage)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Quote:
        """Create a quote from a stored dict."""
        return cls(
            text=str(data["text"]),
            author=str(data.get("author") or ""),
            language=str(data.get("language") or LANGUAGE_EN),
        )


def _en(text: str, author: str) -> Quote:
    return Quote(text, author, LANGUAGE_EN)


def _nl(text: str, author: str) -> Quote:
    return Quote(text, author, LANGUAGE_NL)


BUILTIN_QUOTES: tuple[Quote, ...] = (
    # English
    _en("The only way to do great work is to love what you do.", "Steve Jobs"),
    _en("The unexamined life is not worth living.", "Socrates"),
    _en("The journey of a thousand miles begins with one step.", "Lao Tzu"),
    _en(
        "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
        "Will Durant",
    ),
    _en(
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "Chinese proverb",
    ),
    _en(
        "Life is what happens to you while you're busy making other plans.",
        "John Lennon",
    ),
    _en("The only thing we have to fear is fear itself.", "Franklin D. Roosevelt"),
    _en("Imagination is more important than knowledge.", "Albert Einstein"),
    _en("Do what you can, with what you have, where you are.", "Theodore Roosevelt"),
    _en("Well done is better than well said.", "Benjamin Franklin"),
    _en("Happiness depends upon ourselves.", "Aristotle"),
    _en("You miss 100% of the shots you don't take.", "Wayne Gretzky"),
    _en("Not all those who wander are lost.", "J.R.R. Tolkien"),
    _en("It always seems impossible until it's done.", "Nelson Mandela"),
    _en("The secret of getting ahead is getting started.", "Mark Twain"),
    _en(
        "If you want to go fast, go alone. If you want to go far, go together.",
        "African proverb",
    ),
    _en(
        "Waste no more time arguing about what a good man should be. Be one.",
        "Marcus Aurelius",
    ),
    _en("We suffer more often in imagination than in reality.", "Seneca"),
    _en("Luck is what happens when preparation meets opportunity.", "Seneca"),
    _en("Strive not to be a success, but rather to be of value.", "Albert Einstein"),
    _en("Act as if what you do makes a difference. It does.", "William James"),
    _en("Talk is cheap. Show me the code.", "Linus Torvalds"),
    _en("First, solve the problem. Then, write the code.", "John Johnson"),
    _en(
        "Any sufficiently advanced technology is indistinguishable from magic.",
        "Arthur C. Clarke",
    ),
    _en("Done is better than perfect.", "Sheryl Sandberg"),
    _en("Knowledge speaks, but wisdom listens.", "Jimi Hendrix"),
    _en("Dwell on the beauty of life.", "Marcus Aurelius"),
    _en(
        "Keep your face always toward the sunshine, and shadows will fall behind you.",
        "Walt Whitman",
    ),
    _en("That which does not kill us makes us stronger.", "Friedrich Nietzsche"),
    _en("Whether you think you can, or you think you can't, you're right.", "Henry Ford"),
    _en("Stay hungry. Stay foolish.", "Steve Jobs"),
    _en("Turn your wounds into wisdom.", "Oprah Winfrey"),
    # Nederlands
    _nl("Elk nadeel heb z'n voordeel.", "Johan Cruijff"),
    _nl("Je gaat het pas zien als je het doorhebt.", "Johan Cruijff"),
    _nl(
        "Voetballen is heel simpel, maar het moeilijkste wat er is, is simpel voetballen.",
        "Johan Cruijff",
    ),
    _nl("In het land der blinden is eenoog koning.", "Desiderius Erasmus"),
    _nl(
        "Hoe heerlijk is het dat niemand ook maar één minuut hoeft te wachten "
        "om de wereld te verbeteren.",
        "Anne Frank",
    ),
    _nl(
        "Grote dingen worden niet impulsief gedaan, maar door een reeks kleine "
        "dingen die samengebracht worden.",
        "Vincent van Gogh",
    ),
    _nl("Ik denk, dus ik ben.", "René Descartes"),
    _nl("Ken uzelf.", "Socrates"),
    _nl(
        "Het leven is wat je overkomt terwijl je druk bezig bent andere plannen te maken.",
        "John Lennon",
    ),
    _nl("Wie niet waagt, die niet wint.", "Spreekwoord"),
    _nl("Al doende leert men.", "Spreekwoord"),
    _nl("Rome is niet in één dag gebouwd.", "Spreekwoord"),
    _nl("Beter een goede buur dan een verre vriend.", "Spreekwoord"),
    _nl("Oost west, thuis best.", "Spreekwoord"),
    _nl("Na regen komt zonneschijn.", "Spreekwoord"),
    _nl("Wie het kleine niet eert, is het grote niet weerd.", "Spreekwoord"),
    _nl("Doe maar gewoon, dan doe je al gek genoeg.", "Spreekwoord"),
    _nl("Zachte heelmeesters maken stinkende wonden.", "Spreekwoord"),
    _nl("Wie goed doet, goed ontmoet.", "Spreekwoord"),
    _nl("Eendracht maakt macht.", "Spreekwoord"),
    _nl("Geduld is een schone zaak.", "Spreekwoord"),
    _nl("Een goed begin is het halve werk.", "Spreekwoord"),
    _nl("Het geluk zit in een klein hoekje.", "Spreekwoord"),
    _nl("Wie zaait, zal oogsten.", "Spreekwoord"),
    _nl("Gedeelde vreugde is dubbele vreugde, gedeelde smart is halve smart.", "Spreekwoord"),
)


def quotes_for_language(language: str) -> tuple[Quote, ...]:
    """Return the built-in quotes for a language (or all of them)."""
    if language == LANGUAGE_ALL:
        return BUILTIN_QUOTES
    selected = tuple(q for q in BUILTIN_QUOTES if q.language == language)
    return selected or BUILTIN_QUOTES


def daily_quote(day: date, language: str) -> Quote:
    """Return the deterministic built-in quote for a given day.

    The list is shuffled once per "cycle" (as many days as there are quotes),
    so no quote repeats within a cycle and the order differs per cycle.
    """
    quotes = list(quotes_for_language(language))
    count = len(quotes)
    cycle, index = divmod(day.toordinal(), count)
    random.Random(f"{language}-{cycle}").shuffle(quotes)
    return quotes[index]


def random_quote(language: str, exclude: Quote | None = None) -> Quote:
    """Return a random built-in quote, different from ``exclude`` if possible."""
    quotes = [q for q in quotes_for_language(language) if q != exclude]
    if not quotes:
        quotes = list(quotes_for_language(language))
    return random.choice(quotes)  # noqa: S311 - not used for security

"""Famous birthday and historical/scientific fact for a calendar day.

Data comes from Wikipedia's "On this day" feed:

* births   -> every notable person born on that day; the most famous one is
              chosen by Wikipedia page views of the last 30 days.
* selected -> events picked by Wikipedia editors for the main page; events
              about science and discovery are preferred.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import random
import re
from typing import Any

import aiohttp

from .api import REQUEST_TIMEOUT, QuoteApiError

WIKI_FEED_URL = (
    "https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/{kind}/{month:02d}/{day:02d}"
)
WIKI_API_URL = "https://{lang}.wikipedia.org/w/api.php"
# Wikimedia asks API clients to identify themselves with a way to reach them.
WIKI_USER_AGENT = (
    "HomeAssistant-QuoteOfTheDay/1.3 "
    "(https://github.com/laurensdehoorne/HA-quote-of-the-day)"
)

PAGEVIEW_DAYS = 30
PAGEVIEW_BATCH = 50
MAX_BIRTH_CANDIDATES = 200

_SCIENCE_WORDS = (
    # English
    "scien", "physic", "chemi", "biolog", "astronom", "mathemat", "discover",
    "invent", "patent", "vaccin", "telescope", "satellite", "spacecraft",
    "space", "orbit", "lunar", "moon landing", "planet", "comet", "rocket", "nasa",
    "nobel", "element", "atom", "nuclear", "dna", "genom", "fossil", "dinosaur",
    "computer", "internet", "electric", "radio", "television", "x-ray",
    "medic", "surgery", "transplant", "antibiot", "theory", "experiment",
    "laborator", "engineer", "aircraft", "flight", "expedition",
    # Nederlands
    "wetenschap", "natuurkund", "scheikund", "wiskund", "sterrenkund",
    "ontdek", "uitvind", "octrooi", "ruimtevaart", "maanlanding", "planeet", "komeet",
    "raket", "kernenergie", "geneeskund", "vliegtu", "uitvinding",
)


class OnThisDayError(QuoteApiError):
    """Raised when on-this-day data could not be fetched."""


@dataclass(frozen=True, slots=True)
class Birthday:
    """A famous person born on this day."""

    name: str
    year: int
    description: str
    summary: str
    url: str
    image: str | None
    pageviews: int = 0


@dataclass(frozen=True, slots=True)
class Fact:
    """A historical or scientific event on this day."""

    text: str
    year: int
    category: str  # "science" or "history"
    title: str
    url: str
    image: str | None


@dataclass(slots=True)
class DayInfo:
    """Everything shown for one calendar day."""

    birthday: Birthday | None
    fact: Fact | None
    language: str

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "birthday": asdict(self.birthday) if self.birthday else None,
            "fact": asdict(self.fact) if self.fact else None,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DayInfo:
        """Deserialize from storage."""
        birthday = data.get("birthday")
        fact = data.get("fact")
        return cls(
            birthday=Birthday(**birthday) if birthday else None,
            fact=Fact(**fact) if fact else None,
            language=str(data.get("language") or "en"),
        )


# --- fetching -----------------------------------------------------------------


async def _get_json(
    session: aiohttp.ClientSession, url: str, params: dict[str, str] | None = None
) -> Any:
    try:
        async with session.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"},
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)
    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
        raise OnThisDayError(f"Error fetching {url}: {err}") from err


async def async_fetch_day(
    session: aiohttp.ClientSession, day: date, language: str
) -> DayInfo:
    """Fetch the famous birthday and the fact for a day.

    Uses the Wikipedia in the requested language and falls back to English
    when that edition has no "On this day" feed.
    """
    languages = [language] if language == "en" else [language, "en"]
    last_error: Exception | None = None
    for lang in languages:
        try:
            births = await _get_json(
                session,
                WIKI_FEED_URL.format(lang=lang, kind="births", month=day.month, day=day.day),
            )
            selected = await _get_json(
                session,
                WIKI_FEED_URL.format(lang=lang, kind="selected", month=day.month, day=day.day),
            )
        except OnThisDayError as err:
            last_error = err
            continue
        candidates = parse_births(births)
        fact = pick_fact(parse_events(selected), day)
        if not candidates and fact is None:
            last_error = OnThisDayError(f"No data for {day:%m-%d} on {lang}.wikipedia")
            continue
        try:
            views = await async_fetch_pageviews(
                session, lang, [c.url_title for c in candidates]
            )
        except OnThisDayError:
            views = {}
        return DayInfo(pick_birthday(candidates, views), fact, lang)
    raise last_error or OnThisDayError("No language to fetch")


async def async_fetch_pageviews(
    session: aiohttp.ClientSession, lang: str, titles: list[str]
) -> dict[str, int]:
    """Return the page views of the last 30 days per (normalized) title."""
    views: dict[str, int] = {}
    for start in range(0, len(titles), PAGEVIEW_BATCH):
        batch = titles[start : start + PAGEVIEW_BATCH]
        data = await _get_json(
            session,
            WIKI_API_URL.format(lang=lang),
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "pageviews",
                "pvipdays": str(PAGEVIEW_DAYS),
                "titles": "|".join(batch),
            },
        )
        views.update(parse_pageviews(data))
    return views


# --- parsing --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _BirthCandidate:
    name: str
    year: int
    description: str
    summary: str
    url: str
    url_title: str
    image: str | None


def _page_info(page: dict[str, Any]) -> tuple[str, str, str, str | None, str]:
    """Return (normalized title, url, extract, image, description) of a page."""
    titles = page.get("titles") or {}
    title = str(
        titles.get("normalized") or page.get("normalizedtitle") or page.get("title") or ""
    ).replace("_", " ")
    url = str(
        ((page.get("content_urls") or {}).get("desktop") or {}).get("page") or ""
    )
    image = (page.get("thumbnail") or {}).get("source")
    return (
        title,
        url,
        str(page.get("extract") or ""),
        str(image) if image else None,
        str(page.get("description") or ""),
    )


_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def parse_births(data: Any) -> list[_BirthCandidate]:
    """Parse the births feed into candidates (the person is the first page)."""
    items = data.get("births") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise OnThisDayError(f"Unexpected births response: {data!r:.200}")
    candidates: list[_BirthCandidate] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("pages"):
            continue
        try:
            year = int(item["year"])
        except (KeyError, TypeError, ValueError):
            continue
        title, url, extract, image, page_desc = _page_info(item["pages"][0])
        if not title:
            continue
        text = str(item.get("text") or "").strip()
        name = _PAREN_RE.sub("", title)
        # "Ada Lovelace, English mathematician (d. 1852)" -> description part.
        description = text.split(", ", 1)[1] if ", " in text else page_desc or text
        candidates.append(
            _BirthCandidate(name, year, description, extract, url, title, image)
        )
    # Limit the page-view lookups; people with a photo are more likely famous.
    candidates.sort(key=lambda c: c.image is None)
    return candidates[:MAX_BIRTH_CANDIDATES]


def parse_pageviews(data: Any) -> dict[str, int]:
    """Sum the daily page views per title from an action=query response."""
    pages = ((data or {}).get("query") or {}).get("pages") or []
    if isinstance(pages, dict):  # formatversion=1
        pages = list(pages.values())
    result: dict[str, int] = {}
    for page in pages:
        if not isinstance(page, dict) or "title" not in page:
            continue
        daily = page.get("pageviews") or {}
        result[str(page["title"])] = sum(v for v in daily.values() if isinstance(v, int))
    return result


def pick_birthday(
    candidates: list[_BirthCandidate], views: dict[str, int]
) -> Birthday | None:
    """Pick the most famous person: most page views, then longest article."""
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda c: (views.get(c.url_title, 0), c.image is not None, len(c.summary)),
    )
    return Birthday(
        name=best.name,
        year=best.year,
        description=best.description,
        summary=best.summary,
        url=best.url,
        image=best.image,
        pageviews=views.get(best.url_title, 0),
    )


def parse_events(data: Any) -> list[Fact]:
    """Parse the selected-events feed."""
    items = data.get("selected") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise OnThisDayError(f"Unexpected events response: {data!r:.200}")
    facts: list[Fact] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text") or "").split())
        try:
            year = int(item["year"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text:
            continue
        pages = [p for p in item.get("pages") or [] if isinstance(p, dict)]
        title, url, image = "", "", None
        if pages:
            title, url, _extract, image, _desc = _page_info(pages[0])
        haystack = " ".join(
            [text, *(str(p.get("description") or "") for p in pages)]
        ).lower()
        category = "science" if any(w in haystack for w in _SCIENCE_WORDS) else "history"
        facts.append(Fact(text, year, category, title, url, image))
    return facts


def pick_fact(facts: list[Fact], day: date) -> Fact | None:
    """Pick one event; science events weigh three times as much."""
    if not facts:
        return None
    weights = [3 if f.category == "science" else 1 for f in facts]
    return random.Random(day.isoformat()).choices(facts, weights=weights)[0]

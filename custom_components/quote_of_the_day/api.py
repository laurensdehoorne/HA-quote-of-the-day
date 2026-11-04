"""Clients for the online quote sources.

Online sources are only contacted when the local cache is refreshed (every
few weeks by default). Each call returns a batch of quotes, which is merged
into the cache.
"""

from __future__ import annotations

import html
from typing import Any
from xml.etree import ElementTree

import aiohttp

from .const import (
    BRAINYQUOTE_RSS_URL,
    FAVQS_QOTD_URL,
    LANGUAGE_EN,
    SOURCE_BRAINYQUOTE,
    SOURCE_FAVQS,
    SOURCE_ZENQUOTES,
    ZENQUOTES_BATCH_URL,
)
from .quotes import Quote, is_good_quote

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)
USER_AGENT = "HomeAssistant-QuoteOfTheDay/1.2"


class QuoteApiError(Exception):
    """Raised when quotes could not be fetched."""


async def async_fetch_quotes(session: aiohttp.ClientSession, source: str) -> list[Quote]:
    """Fetch quotes from an online source; only quotes that pass the filter."""
    if source == SOURCE_ZENQUOTES:
        quotes = parse_zenquotes(await _async_get(session, ZENQUOTES_BATCH_URL, json=True))
    elif source == SOURCE_BRAINYQUOTE:
        quotes = parse_brainyquote(
            await _async_get(session, BRAINYQUOTE_RSS_URL, json=False)
        )
    elif source == SOURCE_FAVQS:
        quotes = parse_favqs(await _async_get(session, FAVQS_QOTD_URL, json=True))
    else:
        raise QuoteApiError(f"Unknown online source: {source}")
    return [q for q in quotes if is_good_quote(q)]


async def _async_get(session: aiohttp.ClientSession, url: str, *, json: bool) -> Any:
    try:
        async with session.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as resp:
            resp.raise_for_status()
            if json:
                return await resp.json(content_type=None)
            return await resp.text()
    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
        raise QuoteApiError(f"Error fetching {url}: {err}") from err


def _clean(text: str) -> str:
    text = html.unescape(text).strip()
    # Feeds often wrap the quote in quotation marks.
    if len(text) > 1 and text[0] in "\"“'" and text[-1] in "\"”'":
        text = text[1:-1].strip()
    return " ".join(text.split())


def parse_zenquotes(data: Any) -> list[Quote]:
    """Parse ZenQuotes: ``[{"q": "...", "a": "...", "h": "..."}, ...]``."""
    if not isinstance(data, list):
        raise QuoteApiError(f"Unexpected ZenQuotes response: {data!r:.200}")
    quotes: list[Quote] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = _clean(str(item.get("q") or ""))
        author = _clean(str(item.get("a") or ""))
        # When rate limited, ZenQuotes answers with a "quote" that is a notice.
        if not text or author.lower() == "zenquotes.io":
            continue
        quotes.append(Quote(text, author, LANGUAGE_EN, source=SOURCE_ZENQUOTES))
    if not quotes:
        raise QuoteApiError(f"No usable quotes from ZenQuotes: {data!r:.200}")
    return quotes


def parse_brainyquote(xml_text: str) -> list[Quote]:
    """Parse the BrainyQuote RSS feed (title = author, description = quote)."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as err:
        raise QuoteApiError(f"Invalid BrainyQuote feed: {err}") from err
    quotes: list[Quote] = []
    for item in root.iter("item"):
        text = _clean(item.findtext("description") or "")
        author = _clean(item.findtext("title") or "")
        if text:
            quotes.append(Quote(text, author, LANGUAGE_EN, source=SOURCE_BRAINYQUOTE))
    if not quotes:
        raise QuoteApiError("BrainyQuote feed contains no quotes")
    return quotes


def parse_favqs(data: Any) -> list[Quote]:
    """Parse the FavQs quote of the day: ``{"quote": {"body": ..., "author": ...}}``."""
    item = data.get("quote") if isinstance(data, dict) else None
    if not isinstance(item, dict):
        raise QuoteApiError(f"Unexpected FavQs response: {data!r:.200}")
    text = _clean(str(item.get("body") or ""))
    author = _clean(str(item.get("author") or ""))
    if not text:
        raise QuoteApiError(f"FavQs response without quote: {data!r:.200}")
    return [Quote(text, author, LANGUAGE_EN, source=SOURCE_FAVQS)]

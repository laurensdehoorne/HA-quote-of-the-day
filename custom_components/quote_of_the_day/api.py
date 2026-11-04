"""Client for the ZenQuotes API."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import LANGUAGE_EN, ZENQUOTES_RANDOM_URL, ZENQUOTES_TODAY_URL
from .quotes import Quote

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


class QuoteApiError(Exception):
    """Raised when a quote could not be fetched."""


class ZenQuotesClient:
    """Minimal async client for https://zenquotes.io."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def async_get_today(self) -> Quote:
        """Return the ZenQuotes quote of the day."""
        return await self._async_fetch(ZENQUOTES_TODAY_URL)

    async def async_get_random(self) -> Quote:
        """Return a random ZenQuotes quote."""
        return await self._async_fetch(ZENQUOTES_RANDOM_URL)

    async def _async_fetch(self, url: str) -> Quote:
        try:
            async with self._session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                data: Any = await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise QuoteApiError(f"Error fetching {url}: {err}") from err
        return parse_zenquotes(data)


def parse_zenquotes(data: Any) -> Quote:
    """Parse a ZenQuotes response: ``[{"q": "...", "a": "...", "h": "..."}]``."""
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise QuoteApiError(f"Unexpected response: {data!r}")
    item = data[0]
    text = str(item.get("q") or "").strip()
    author = str(item.get("a") or "").strip()
    if not text:
        raise QuoteApiError(f"Response without quote: {data!r}")
    # When rate limited, ZenQuotes answers with a quote that is really a notice.
    if author.lower() == "zenquotes.io" or "too many requests" in text.lower():
        raise QuoteApiError(f"Rate limited by ZenQuotes: {text}")
    return Quote(text=text, author=author, language=LANGUAGE_EN)

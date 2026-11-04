"""Tests for the built-in quotes, the quality filter and the parsers."""

from __future__ import annotations

import pytest

from custom_components.quote_of_the_day.api import (
    QuoteApiError,
    parse_brainyquote,
    parse_favqs,
    parse_zenquotes,
)
from custom_components.quote_of_the_day.quotes import (
    BUILTIN_QUOTES,
    Quote,
    is_good_quote,
    normalize,
    quotes_for_language,
)
from custom_components.quote_of_the_day.sensor import truncate


def test_builtin_collection_is_clean() -> None:
    keys = [q.key for q in BUILTIN_QUOTES]
    assert len(set(keys)) == len(keys), "duplicate quotes"
    for quote in BUILTIN_QUOTES:
        assert quote.author, quote
        assert len(quote.text) <= 255, quote
        assert quote.language in ("en", "nl"), quote
        # Everything not a proverb carries a reference to where it comes from,
        # except a few well-known spoken quotes.
        if "proverb" not in quote.author.lower() and quote.author != "Spreekwoord":
            assert quote.reference or quote.author == "Johan Cruijff", quote


def test_language_filter() -> None:
    assert all(q.language == "nl" for q in quotes_for_language("nl"))
    assert all(q.language == "en" for q in quotes_for_language("en"))
    assert quotes_for_language("xx") == BUILTIN_QUOTES
    assert len(quotes_for_language("en")) >= 60
    assert len(quotes_for_language("nl")) >= 30


def test_normalize() -> None:
    assert normalize("Be kind!") == normalize("be  kind")


@pytest.mark.parametrize(
    ("text", "author", "good"),
    [
        ("The best way out is always through.", "Robert Frost", True),
        ("Short.", "Someone", False),
        ("A perfectly fine sentence about life.", "Unknown", False),
        ("A perfectly fine sentence about life.", "", False),
        ("Visit https://example.com for more wisdom today.", "Spammer", False),
        ("Follow us @quotes for daily wisdom every day.", "Spammer", False),
        ("THIS IS A VERY LOUD QUOTE ABOUT LIFE.", "Loud Person", False),
        ("word " * 60, "Long Winded", False),
    ],
)
def test_is_good_quote(text: str, author: str, good: bool) -> None:
    assert is_good_quote(Quote(text, author, "en", source="zenquotes")) is good


def test_parse_zenquotes() -> None:
    quotes = parse_zenquotes(
        [
            {"q": " Be kind. ", "a": "Someone", "h": "<b>x</b>"},
            {"q": "Too many requests.", "a": "zenquotes.io"},
            {"q": "Second &amp; last.", "a": "Other"},
        ]
    )
    assert [(q.text, q.author, q.source) for q in quotes] == [
        ("Be kind.", "Someone", "zenquotes"),
        ("Second & last.", "Other", "zenquotes"),
    ]


@pytest.mark.parametrize(
    "data",
    [{}, [], ["x"], [{"q": "", "a": "x"}], [{"q": "Too many requests.", "a": "zenquotes.io"}]],
)
def test_parse_zenquotes_errors(data) -> None:
    with pytest.raises(QuoteApiError):
        parse_zenquotes(data)


BRAINY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Quotes</title>
<item><title>Walt Disney</title>
<description>"The way to get started is to quit talking and begin doing."</description>
<link>https://www.brainyquote.com/x</link></item>
<item><title>Seneca</title><description>&quot;Luck is what happens.&quot;</description></item>
</channel></rss>"""


def test_parse_brainyquote() -> None:
    quotes = parse_brainyquote(BRAINY_RSS)
    assert [(q.text, q.author, q.source) for q in quotes] == [
        (
            "The way to get started is to quit talking and begin doing.",
            "Walt Disney",
            "brainyquote",
        ),
        ("Luck is what happens.", "Seneca", "brainyquote"),
    ]


@pytest.mark.parametrize("xml", ["not xml", "<rss><channel></channel></rss>"])
def test_parse_brainyquote_errors(xml: str) -> None:
    with pytest.raises(QuoteApiError):
        parse_brainyquote(xml)


def test_parse_favqs() -> None:
    quotes = parse_favqs(
        {
            "qotd_date": "2026-11-04T00:00:00.000+00:00",
            "quote": {
                "id": 1,
                "author": "Ada Lovelace",
                "body": "That brain of mine is more than merely mortal.",
            },
        }
    )
    assert [(q.text, q.author, q.source) for q in quotes] == [
        ("That brain of mine is more than merely mortal.", "Ada Lovelace", "favqs")
    ]


@pytest.mark.parametrize("data", [[], {}, {"quote": {"body": ""}}])
def test_parse_favqs_errors(data) -> None:
    with pytest.raises(QuoteApiError):
        parse_favqs(data)


def test_truncate() -> None:
    assert truncate("short") == "short"
    long = "a" * 300
    assert len(truncate(long)) == 255
    assert truncate(long).endswith("…")

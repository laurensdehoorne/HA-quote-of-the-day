"""Tests for the built-in quotes and the ZenQuotes parser."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from custom_components.quote_of_the_day.api import QuoteApiError, parse_zenquotes
from custom_components.quote_of_the_day.quotes import (
    BUILTIN_QUOTES,
    daily_quote,
    quotes_for_language,
    random_quote,
)
from custom_components.quote_of_the_day.sensor import truncate


def test_daily_quote_is_deterministic() -> None:
    day = date(2026, 11, 4)
    assert daily_quote(day, "all") == daily_quote(day, "all")


@pytest.mark.parametrize("language", ["all", "en", "nl"])
def test_no_repeats_within_a_cycle(language: str) -> None:
    quotes = quotes_for_language(language)
    count = len(quotes)
    start_ordinal = (date(2026, 1, 1).toordinal() // count + 1) * count
    start = date.fromordinal(start_ordinal)
    seen = {daily_quote(start + timedelta(days=i), language) for i in range(count)}
    assert seen == set(quotes)


def test_language_filter() -> None:
    assert all(q.language == "nl" for q in quotes_for_language("nl"))
    assert all(q.language == "en" for q in quotes_for_language("en"))
    assert quotes_for_language("xx") == BUILTIN_QUOTES


def test_random_quote_differs() -> None:
    current = BUILTIN_QUOTES[0]
    for _ in range(50):
        assert random_quote("all", current) != current


def test_quotes_are_unique_and_fit_state() -> None:
    assert len(set(BUILTIN_QUOTES)) == len(BUILTIN_QUOTES)
    assert all(len(q.text) <= 255 and q.author for q in BUILTIN_QUOTES)


def test_parse_zenquotes() -> None:
    quote = parse_zenquotes([{"q": " Be kind. ", "a": "Someone", "h": "<b>x</b>"}])
    assert quote.text == "Be kind."
    assert quote.author == "Someone"


@pytest.mark.parametrize(
    "data",
    [
        {},
        [],
        ["x"],
        [{"q": "", "a": "x"}],
        [{"q": "Too many requests. Obtain an auth key.", "a": "zenquotes.io"}],
    ],
)
def test_parse_zenquotes_errors(data) -> None:
    with pytest.raises(QuoteApiError):
        parse_zenquotes(data)


def test_truncate() -> None:
    assert truncate("short") == "short"
    long = "a" * 300
    assert len(truncate(long)) == 255
    assert truncate(long).endswith("…")

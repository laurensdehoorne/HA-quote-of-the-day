"""Constants for the Quote of the Day integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "quote_of_the_day"

CONF_SOURCE: Final = "source"
CONF_LANGUAGE: Final = "language"

SOURCE_BUILTIN: Final = "builtin"
SOURCE_ZENQUOTES: Final = "zenquotes"
SOURCES: Final = [SOURCE_BUILTIN, SOURCE_ZENQUOTES]

LANGUAGE_ALL: Final = "all"
LANGUAGE_EN: Final = "en"
LANGUAGE_NL: Final = "nl"
LANGUAGES: Final = [LANGUAGE_ALL, LANGUAGE_EN, LANGUAGE_NL]

DEFAULT_SOURCE: Final = SOURCE_BUILTIN
DEFAULT_LANGUAGE: Final = LANGUAGE_ALL

ZENQUOTES_TODAY_URL: Final = "https://zenquotes.io/api/today"
ZENQUOTES_RANDOM_URL: Final = "https://zenquotes.io/api/random"

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}.state"

ATTR_QUOTE: Final = "quote"
ATTR_AUTHOR: Final = "author"
ATTR_DATE: Final = "date"
ATTR_SOURCE: Final = "source"
ATTR_LANGUAGE: Final = "language"
ATTR_FALLBACK: Final = "fallback"

ZENQUOTES_ATTRIBUTION: Final = "Inspirational quotes provided by ZenQuotes API (https://zenquotes.io/)"

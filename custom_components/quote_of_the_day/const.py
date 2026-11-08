"""Constants for the Quote of the Day integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "quote_of_the_day"

CARD_URL_BASE: Final = "/quote_of_the_day_static"
CARD_FILENAME: Final = "daily-quote-card.js"

CONF_SOURCE: Final = "source"  # config entry version 1 (single source)
CONF_SOURCES: Final = "sources"
CONF_LANGUAGE: Final = "language"
CONF_CACHE_DAYS: Final = "cache_days"
CONF_ON_THIS_DAY: Final = "on_this_day"
CONF_THEME: Final = "theme"
CONF_AI_TASK_ENTITY: Final = "ai_task_entity"
CONF_AI_INSTRUCTIONS: Final = "ai_instructions"

SOURCE_BUILTIN: Final = "builtin"
SOURCE_ZENQUOTES: Final = "zenquotes"
SOURCE_BRAINYQUOTE: Final = "brainyquote"
SOURCE_FAVQS: Final = "favqs"
SOURCES: Final = [SOURCE_BUILTIN, SOURCE_ZENQUOTES, SOURCE_BRAINYQUOTE, SOURCE_FAVQS]
ONLINE_SOURCES: Final = [SOURCE_ZENQUOTES, SOURCE_BRAINYQUOTE, SOURCE_FAVQS]

LANGUAGE_ALL: Final = "all"
LANGUAGE_EN: Final = "en"
LANGUAGE_NL: Final = "nl"
LANGUAGES: Final = [LANGUAGE_ALL, LANGUAGE_EN, LANGUAGE_NL]

THEME_ALL: Final = "all"
THEME_MOTIVATIONAL: Final = "motivational"
THEMES: Final = [THEME_MOTIVATIONAL, THEME_ALL]

DEFAULT_SOURCES: Final = list(SOURCES)
DEFAULT_LANGUAGE: Final = LANGUAGE_ALL
DEFAULT_CACHE_DAYS: Final = 28
DEFAULT_ON_THIS_DAY: Final = True
DEFAULT_THEME: Final = THEME_MOTIVATIONAL
MIN_CACHE_DAYS: Final = 1
MAX_CACHE_DAYS: Final = 90

# Upper bound for the number of cached quotes (oldest are dropped first).
MAX_CACHED_QUOTES: Final = 1000

# Returns a batch of 50 random quotes.
ZENQUOTES_BATCH_URL: Final = "https://zenquotes.io/api/quotes"
BRAINYQUOTE_RSS_URL: Final = "https://www.brainyquote.com/link/quotebr.rss"
FAVQS_QOTD_URL: Final = "https://favqs.com/api/qotd"

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}.data"
STORAGE_KEY_ON_THIS_DAY: Final = f"{DOMAIN}.on_this_day"
STORAGE_KEY_AI_QUOTE: Final = f"{DOMAIN}.ai_quote"

ATTR_QUOTE: Final = "quote"
ATTR_AUTHOR: Final = "author"
ATTR_DATE: Final = "date"
ATTR_SOURCE: Final = "source"
ATTR_LANGUAGE: Final = "language"
ATTR_FALLBACK: Final = "fallback"
ATTR_REFERENCE: Final = "reference"
ATTR_ENTRIES: Final = "entries"
ATTR_CACHED_QUOTES: Final = "cached_quotes"
ATTR_CACHE_UPDATED: Final = "cache_updated"
ATTR_MOTIVATIONAL: Final = "motivational"
ATTR_THEME: Final = "theme"
ATTR_AI_TASK_ENTITY: Final = "ai_task_entity"

WIKIPEDIA_ATTRIBUTION: Final = "Data from Wikipedia (CC BY-SA 4.0)"

ATTRIBUTIONS: Final = {
    SOURCE_ZENQUOTES: "Inspirational quotes provided by ZenQuotes API (https://zenquotes.io/)",
    SOURCE_BRAINYQUOTE: "Quotes provided by BrainyQuote (https://www.brainyquote.com/)",
    SOURCE_FAVQS: "Quotes provided by FavQs (https://favqs.com/)",
}

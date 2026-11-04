# Quote of the Day for Home Assistant

A Home Assistant integration that gives you a new quote every day, ready for
your dashboard, a morning notification or a TTS announcement.

## Features

- **Daily quote** that changes at midnight (local time) and stays the same
  across restarts.
- **Combines several sources** into one pool (all enabled by default):

  | Source | Type | Language |
  | --- | --- | --- |
  | Built-in collection | offline, curated | English + Dutch |
  | [ZenQuotes](https://zenquotes.io/) | online, 50 quotes per request | English |
  | [BrainyQuote](https://www.brainyquote.com/) RSS | online, quotes of the day | English |
  | [FavQs](https://favqs.com/) | online, quote of the day | English |

  No quote repeats until the whole pool has been shown. If several sources
  return the same quote, it is only used once.
- **Good quotes only.**
  - The built-in collection (~110 quotes) is curated: every quote has the
    right author and a `reference` to the book, speech or letter it comes
    from. Popular but misattributed quotes (the "Mandela", "Twain" and
    "Ford" quotes that never were) are left out.
  - Online quotes pass a quality filter: a real author (no "Unknown" /
    "Anonymous"), between 15 and 250 characters, no links, hashtags,
    markup or ALL CAPS.
- **Long-lived cache.** Online quotes are downloaded in a batch and kept on
  disk; each source is only contacted again after the cache duration
  (default **28 days**, configurable 1–90). New quotes are merged in, so the
  pool grows over time.
- **Works offline.** If a source can't be reached, the others are still
  used and the failing one is retried after an hour. With no quotes at all,
  a built-in quote is shown (`fallback: true`).
- **Language:** all, English or Dutch. The online sources are English, so
  with Dutch only the built-in collection is used.
- **Famous birthday and fact of the day** (optional, on by default), from
  Wikipedia's "On this day":
  - *Birthday*: of everyone born on this day, the person whose Wikipedia
    page was read most in the last 30 days, with photo, description and
    age/years ago.
  - *On this day*: one of the events Wikipedia editors selected for this
    date; scientific events (space, discoveries, inventions, medicine…)
    are three times as likely to be picked as other historical ones.
  - Uses the Wikipedia of your language (Dutch with "Dutch", Home
    Assistant's language with "All"), falling back to English. The coming
    week is fetched ahead and cached, so a few days offline go unnoticed.
- **"New quote" button** to swap today's quote for a random one.
- Set up and configured from the UI, translated in English and Dutch.

## Installation

### HACS (recommended)

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/laurensdehoorne/HA-quote-of-the-day` with category
   **Integration**.
3. Install **Quote of the Day** and restart Home Assistant.

### Manual

Copy `custom_components/quote_of_the_day` into the `custom_components` folder
of your Home Assistant configuration and restart Home Assistant.

## Setup

**Settings → Devices & services → Add integration → Quote of the Day**, then
pick the sources, language and cache duration. All can be changed later via
**Configure**.

## Entities

| Entity | Description |
| --- | --- |
| `sensor.quote_of_the_day_quote` | The quote. Attributes: `quote` (full text), `author`, `reference`, `date`, `source` (where this quote came from), `language`, `fallback`, `entries` (for feed cards) and, for online sources, `cached_quotes` and `cache_updated`. |
| `sensor.quote_of_the_day_author` | The author of the quote. |
| `sensor.quote_of_the_day_birthday` | Famous person born on this day. Picture: their photo. Attributes: `name`, `born`, `years_ago`, `description`, `summary`, `url`. |
| `sensor.quote_of_the_day_on_this_day` | "year: event". Picture: from the article. Attributes: `text`, `year`, `years_ago`, `category` (`science`/`history`), `title`, `url`. |
| `button.quote_of_the_day_new_quote` | Replaces today's quote with a random one. |

The state of a sensor is limited to 255 characters; longer quotes are cut off
with "…" in the state, the full text is always in the `quote` attribute.

## Examples

### Dashboard card

```yaml
type: markdown
content: >
  > {{ state_attr('sensor.quote_of_the_day_quote', 'quote') }}

  — *{{ state_attr('sensor.quote_of_the_day_quote', 'author') }}*
```

### Quote, birthday and fact on one card

```yaml
type: markdown
content: >
  > {{ state_attr('sensor.quote_of_the_day_quote', 'quote') }}

  — *{{ state_attr('sensor.quote_of_the_day_quote', 'author') }}*


  🎂 **{{ states('sensor.quote_of_the_day_birthday') }}**
  (born {{ state_attr('sensor.quote_of_the_day_birthday', 'born') }}),
  {{ state_attr('sensor.quote_of_the_day_birthday', 'description') }}


  📜 **{{ state_attr('sensor.quote_of_the_day_on_this_day', 'year') }}**:
  {{ state_attr('sensor.quote_of_the_day_on_this_day', 'text') }}
```

### quote-of-the-day-card

The sensor has an `entries` attribute in the same format as a Feedparser
sensor, so [quote-of-the-day-card](https://github.com/dnguyen800/quote-of-the-day-card)
works without Feedparser:

```yaml
type: custom:quote-of-the-day-card
entity: sensor.quote_of_the_day_quote
feed_attribute: entries
```

### Morning notification

```yaml
automation:
  - alias: Quote of the day in the morning
    triggers:
      - trigger: time
        at: "07:30:00"
    actions:
      - action: notify.mobile_app_my_phone
        data:
          title: Quote of the day
          message: >
            {{ state_attr('sensor.quote_of_the_day_quote', 'quote') }}
            — {{ state_attr('sensor.quote_of_the_day_quote', 'author') }}
```

### Get a new quote from an automation

```yaml
actions:
  - action: button.press
    target:
      entity_id: button.quote_of_the_day_new_quote
```

## Development

```bash
pip install -r requirements_test.txt
pytest
```

---

Online quotes are provided by the [ZenQuotes API](https://zenquotes.io/),
[BrainyQuote](https://www.brainyquote.com/) and [FavQs](https://favqs.com/).
Birthdays and facts come from [Wikipedia](https://www.wikipedia.org/)
(CC BY-SA 4.0).

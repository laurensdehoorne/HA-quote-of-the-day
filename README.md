# Quote of the Day for Home Assistant

A Home Assistant integration that gives you a new motivational quote every
day, ready for your dashboard, a morning notification or a TTS announcement.
Optionally, an AI writes you a fresh motivational quote of its own as well.

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
- **Motivational by default.** The *Motivational* theme only shows quotes
  about perseverance, courage, effort and growth. The built-in quotes are
  labelled by hand (about 80 English and 35 Dutch ones); online quotes are
  recognized by their words. Choose *All quotes* for the whole collection.
- **AI quote (optional).** Pick an
  [AI Task](https://www.home-assistant.io/integrations/ai_task/) entity
  (OpenAI, Google Gemini, Anthropic, Ollama, ...) and get a second sensor
  with a new motivational quote written by AI every day, in your language.
  - The AI writes its own sentence and is told not to quote or name anyone,
    so it is never passed off as a quote by a real person.
  - Add your own wishes, e.g. "about running", "for a team of nurses" or
    "with a touch of humour".
  - Each day has a different angle (starting, discipline, failing and trying
    again, ...) and the AI is told not to repeat its earlier quotes.
  - One AI request per day, plus one per press of the **New AI quote**
    button. If the AI can't be reached, yesterday's quote stays and it is
    retried after an hour.
  - Needs Home Assistant 2025.8 or later with an AI Task entity set up.
- **Good quotes only.**
  - The built-in collection (~180 quotes, with a focus on motivational and
    personal growth ones) is curated: every quote has the right author and a
    `reference` to the book, speech or letter it comes from. Popular but
    misattributed quotes (the "Mandela", "Twain" and "Ford" quotes that
    never were) are left out.
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
- **"Dislike quote" button**: a quote you don't like is replaced right away
  and never shown again (also not after a cache refresh or restart). The
  "Restore disliked quotes" button (under the device's configuration) undoes
  this.
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
pick the theme, sources, language and cache duration, and optionally an AI
Task entity for the AI quote. All can be changed later via **Configure**;
clear the AI Task entity to turn the AI quote off.

## Entities

| Entity | Description |
| --- | --- |
| `sensor.quote_of_the_day_quote` | The quote. Attributes: `quote` (full text), `author`, `reference`, `date`, `source` (where this quote came from), `language`, `fallback`, `theme`, `motivational`, `entries` (for feed cards), `disliked_quotes` and, for online sources, `cached_quotes` and `cache_updated`. |
| `sensor.quote_of_the_day_author` | The author of the quote. |
| `sensor.quote_of_the_day_ai_quote` | The quote written by AI (only with an AI Task entity). Attributes: `quote`, `date`, `language`, `ai_task_entity`. |
| `sensor.quote_of_the_day_birthday` | Famous person born on this day. Picture: their photo. Attributes: `name`, `born`, `years_ago`, `description`, `summary`, `url`. |
| `sensor.quote_of_the_day_on_this_day` | "year: event". Picture: from the article. Attributes: `text`, `year`, `years_ago`, `category` (`science`/`history`), `title`, `url`. |
| `button.quote_of_the_day_new_quote` | Replaces today's quote with a random one. |
| `button.quote_of_the_day_dislike_quote` | Marks today's quote as not good: it is replaced and never shown again. |
| `button.quote_of_the_day_new_ai_quote` | Asks the AI for a new quote (only with an AI Task entity). |
| `button.quote_of_the_day_restore_disliked_quotes` | Allows all disliked quotes again (configuration entity). |

The state of a sensor is limited to 255 characters; longer quotes are cut off
with "…" in the state, the full text is always in the `quote` attribute.

## Dashboard card

The card below only uses cards that are built into Home Assistant (a
Markdown card and buttons), so there is nothing to install and nothing for
the browser to load: it works in every browser, on old tablets and in the
Companion app.

It shows the quote with author and source, the AI quote (when set up), the
famous birthday with photo and the fact of the day, with buttons for a new
quote, "not a good quote" (asks for confirmation) and a new AI quote.

**Edit dashboard → Add card → Manual**, and paste:

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      {%- set nl = false %}{# true: Dutch labels #}
      {%- set q = 'sensor.quote_of_the_day_quote' %}
      {%- set ai = 'sensor.quote_of_the_day_ai_quote' %}
      {%- set b = 'sensor.quote_of_the_day_birthday' %}
      {%- set f = 'sensor.quote_of_the_day_on_this_day' %}
      {%- if has_value(q) %}
      ### <ha-icon icon="mdi:format-quote-open"></ha-icon> {{ 'Citaat van de dag' if nl else 'Quote of the day' }}

      > *{{ state_attr(q, 'quote') }}*

      **— {{ state_attr(q, 'author') }}**
      {%- if state_attr(q, 'reference') %}<br><small>{{ state_attr(q, 'reference') }}</small>{% endif %}
      {% endif %}
      {%- if has_value(ai) %}

      ---
      ### <ha-icon icon="mdi:robot-happy-outline"></ha-icon> {{ 'Motivatie van vandaag' if nl else "Today's motivation" }}

      **{{ state_attr(ai, 'quote') }}**
      {% endif %}
      {%- if has_value(b) %}

      ---
      ### <ha-icon icon="mdi:cake-variant"></ha-icon> {{ 'Vandaag jarig' if nl else 'Born today' }}
      {% if state_attr(b, 'entity_picture') %}
      <img src="{{ state_attr(b, 'entity_picture') }}" height="80">
      {% endif %}
      **{{ state_attr(b, 'name') }}**, {{ state_attr(b, 'description') }}<br>
      <small>{{ 'geboren in' if nl else 'born' }} {{ state_attr(b, 'born') }} · {{ state_attr(b, 'years_ago') }} {{ 'jaar geleden' if nl else 'years ago' }} · [Wikipedia]({{ state_attr(b, 'url') }})</small>
      {% endif %}
      {%- if has_value(f) %}

      ---
      ### <ha-icon icon="mdi:{{ 'flask-outline' if state_attr(f, 'category') == 'science' else 'book-clock-outline' }}"></ha-icon> {{ 'Op deze dag' if nl else 'On this day' }}

      **{{ state_attr(f, 'year') }}**: {{ state_attr(f, 'text') }}<br>
      <small>{{ state_attr(f, 'years_ago') }} {{ 'jaar geleden' if nl else 'years ago' }} · [Wikipedia]({{ state_attr(f, 'url') }})</small>
      {% endif %}
  - type: grid
    columns: 3
    square: false
    cards:
      - type: button
        name: New quote
        icon: mdi:refresh
        show_state: false
        icon_height: 28px
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.quote_of_the_day_new_quote
      - type: button
        name: Not a good quote
        icon: mdi:thumb-down-outline
        show_state: false
        icon_height: 28px
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.quote_of_the_day_dislike_quote
          confirmation:
            text: Never show this quote again?
      # Only with the AI quote: remove this button if you don't use it.
      - type: button
        name: New AI quote
        icon: mdi:robot-happy-outline
        show_state: false
        icon_height: 28px
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.quote_of_the_day_new_ai_quote
```

- **Dutch labels:** change `set nl = false` to `set nl = true` (and translate
  the button names).
- **Leave out a part:** sections whose sensor doesn't exist (AI quote,
  birthday, fact) are skipped automatically. To hide one anyway, delete its
  block from `{%- if has_value(...) %}` to the matching `{% endif %}`.
- **Only the quote**, in its simplest form:

  ```yaml
  type: markdown
  content: |
    > *{{ state_attr('sensor.quote_of_the_day_quote', 'quote') }}*

    **— {{ state_attr('sensor.quote_of_the_day_quote', 'author') }}**
  ```

## Examples

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

### Motivation from AI, read out in the morning

```yaml
automation:
  - alias: Motivation in the morning
    triggers:
      - trigger: time
        at: "07:30:00"
    actions:
      - action: tts.speak
        target:
          entity_id: tts.home_assistant_cloud
        data:
          media_player_entity_id: media_player.kitchen
          message: "{{ state_attr('sensor.quote_of_the_day_ai_quote', 'quote') }}"
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

# Quote of the Day for Home Assistant

A Home Assistant integration that gives you a new quote every day, ready for
your dashboard, a morning notification or a TTS announcement.

## Features

- **Daily quote** that changes at midnight (local time) and stays the same
  across restarts.
- **Two sources**
  - *Built-in collection* – works fully offline, English and Dutch quotes and
    proverbs. No quote repeats until the whole collection has been shown.
  - *ZenQuotes* – an English quote of the day from [zenquotes.io](https://zenquotes.io/).
    When it is unreachable, the integration falls back to the built-in
    collection and retries automatically.
- **Language filter** for the built-in collection: all, English or Dutch.
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
pick a source and language. Both can be changed later via **Configure**.

## Entities

| Entity | Description |
| --- | --- |
| `sensor.quote_of_the_day_quote` | The quote. Attributes: `quote` (full text), `author`, `date`, `source`, `language`, `fallback`. |
| `sensor.quote_of_the_day_author` | The author of the quote. |
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

Quotes from the ZenQuotes source are provided by the
[ZenQuotes API](https://zenquotes.io/).

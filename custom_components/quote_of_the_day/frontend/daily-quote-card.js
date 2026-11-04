/**
 * Daily quote card (custom:daily-quote-card) for Home Assistant.
 *
 * Shows the quote of the day, a famous person born today and a historical or
 * scientific fact, from the Quote of the Day integration. Served and loaded
 * by the integration itself; no resource needs to be added by hand.
 */

const CARD_VERSION = "1.4.0";

const DEFAULTS = {
  quote_entity: "sensor.quote_of_the_day_quote",
  birthday_entity: "sensor.quote_of_the_day_birthday",
  fact_entity: "sensor.quote_of_the_day_on_this_day",
  button_entity: "button.quote_of_the_day_new_quote",
  show_quote: true,
  show_reference: true,
  show_birthday: true,
  show_fact: true,
  show_images: true,
  show_new_quote_button: true,
};

const TEXTS = {
  en: {
    title: "Quote of the day",
    birthday: "Born today",
    fact: "On this day",
    science: "Science",
    history: "History",
    born: "born {year}",
    yearsAgo: "{n} years ago",
    newQuote: "New quote",
    readMore: "Read more on Wikipedia",
    noData: "Not available",
    missing: "Entity not found: {entity}",
  },
  nl: {
    title: "Citaat van de dag",
    birthday: "Vandaag jarig",
    fact: "Op deze dag",
    science: "Wetenschap",
    history: "Geschiedenis",
    born: "geboren in {year}",
    yearsAgo: "{n} jaar geleden",
    newQuote: "Nieuw citaat",
    readMore: "Lees meer op Wikipedia",
    noData: "Niet beschikbaar",
    missing: "Entiteit niet gevonden: {entity}",
  },
};

const UNAVAILABLE = ["unavailable", "unknown"];

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function safeUrl(value) {
  const url = String(value ?? "");
  return /^https:\/\//i.test(url) ? url : "";
}

class QuoteOfTheDayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULTS };
    this._hass = undefined;
    this._lastStates = undefined;
    this._busy = false;
  }

  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    return {
      schema: [
        {
          type: "grid",
          name: "",
          schema: [
            { name: "show_quote", selector: { boolean: {} } },
            { name: "show_reference", selector: { boolean: {} } },
            { name: "show_birthday", selector: { boolean: {} } },
            { name: "show_fact", selector: { boolean: {} } },
            { name: "show_images", selector: { boolean: {} } },
            { name: "show_new_quote_button", selector: { boolean: {} } },
          ],
        },
        {
          type: "expandable",
          name: "",
          title: "Entities",
          schema: [
            { name: "quote_entity", selector: { entity: { domain: "sensor" } } },
            { name: "birthday_entity", selector: { entity: { domain: "sensor" } } },
            { name: "fact_entity", selector: { entity: { domain: "sensor" } } },
            { name: "button_entity", selector: { entity: { domain: "button" } } },
          ],
        },
      ],
      computeLabel: (schema) =>
        ({
          show_quote: "Quote",
          show_reference: "Source of the quote",
          show_birthday: "Birthday",
          show_fact: "Fact of the day",
          show_images: "Pictures",
          show_new_quote_button: "'New quote' button",
          quote_entity: "Quote sensor",
          birthday_entity: "Birthday sensor",
          fact_entity: "Fact sensor",
          button_entity: "New quote button",
        })[schema.name],
    };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid configuration");
    }
    this._config = { ...DEFAULTS, ...config };
    this._lastStates = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const states = this._watched().map((id) => hass.states[id]);
    const language = hass.locale?.language ?? hass.language;
    if (
      this._lastStates &&
      this._lastLanguage === language &&
      states.every((s, i) => s === this._lastStates[i])
    ) {
      return;
    }
    this._lastStates = states;
    this._lastLanguage = language;
    this._render();
  }

  getCardSize() {
    let size = 1;
    if (this._config.show_quote) size += 3;
    if (this._config.show_birthday) size += 2;
    if (this._config.show_fact) size += 2;
    return size;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _watched() {
    const c = this._config;
    return [c.quote_entity, c.birthday_entity, c.fact_entity, c.button_entity];
  }

  _t(key, vars = {}) {
    const lang = (this._hass?.locale?.language ?? this._hass?.language ?? "en").slice(0, 2);
    const texts = TEXTS[lang] ?? TEXTS.en;
    return (texts[key] ?? TEXTS.en[key]).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
  }

  _state(entityId) {
    const state = this._hass?.states?.[entityId];
    if (!state || UNAVAILABLE.includes(state.state)) return undefined;
    return state;
  }

  _image(state) {
    if (!this._config.show_images) return "";
    const url = safeUrl(state.attributes.entity_picture);
    return url
      ? `<img class="photo" src="${escapeHtml(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : "";
  }

  _link(url, label) {
    const href = safeUrl(url);
    return href
      ? `<a class="link" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} <ha-icon icon="mdi:open-in-new"></ha-icon></a>`
      : "";
  }

  _renderQuote() {
    const c = this._config;
    const state = this._state(c.quote_entity);
    if (!state) {
      return `<section class="quote"><p class="empty">${escapeHtml(
        this._hass?.states?.[c.quote_entity]
          ? this._t("noData")
          : this._t("missing", { entity: c.quote_entity }),
      )}</p></section>`;
    }
    const a = state.attributes;
    const text = a.quote || state.state;
    const reference = c.show_reference && a.reference
      ? `<span class="reference">${escapeHtml(a.reference)}</span>`
      : "";
    const button =
      c.show_new_quote_button && this._hass.states[c.button_entity]
        ? `<button class="new-quote" title="${escapeHtml(this._t("newQuote"))}" aria-label="${escapeHtml(
            this._t("newQuote"),
          )}" ${this._busy ? "disabled" : ""}><ha-icon icon="mdi:refresh"></ha-icon></button>`
        : "";
    const size = text.length > 180 ? "long" : text.length > 90 ? "medium" : "short";
    return `
      <section class="quote">
        <div class="header">
          <span class="label"><ha-icon icon="mdi:format-quote-open"></ha-icon>${escapeHtml(this._t("title"))}</span>
          ${button}
        </div>
        <blockquote class="${size}" lang="${escapeHtml(a.language || "")}">${escapeHtml(text)}</blockquote>
        <div class="author">
          ${a.author ? `<span class="name">— ${escapeHtml(a.author)}</span>` : ""}
          ${reference}
        </div>
      </section>`;
  }

  _renderBirthday() {
    const state = this._state(this._config.birthday_entity);
    if (!state) return "";
    const a = state.attributes;
    const meta = [
      a.born ? this._t("born", { year: a.born }) : "",
      a.years_ago ? this._t("yearsAgo", { n: a.years_ago }) : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return `
      <section class="item birthday">
        ${this._image(state) || `<div class="icon-box"><ha-icon icon="mdi:cake-variant"></ha-icon></div>`}
        <div class="body">
          <span class="label">${escapeHtml(this._t("birthday"))}</span>
          <span class="title">${escapeHtml(a.name || state.state)}</span>
          ${a.description ? `<span class="text">${escapeHtml(a.description)}</span>` : ""}
          ${meta ? `<span class="meta">${escapeHtml(meta)}</span>` : ""}
          ${this._link(a.url, this._t("readMore"))}
        </div>
      </section>`;
  }

  _renderFact() {
    const state = this._state(this._config.fact_entity);
    if (!state) return "";
    const a = state.attributes;
    const science = a.category === "science";
    const icon = science ? "mdi:flask-outline" : "mdi:book-clock-outline";
    return `
      <section class="item fact">
        ${this._image(state) || `<div class="icon-box"><ha-icon icon="${icon}"></ha-icon></div>`}
        <div class="body">
          <span class="label">${escapeHtml(this._t("fact"))}
            <span class="chip ${science ? "science" : "history"}"><ha-icon icon="${icon}"></ha-icon>${escapeHtml(
              this._t(science ? "science" : "history"),
            )}</span>
          </span>
          <span class="title">${escapeHtml(a.year ?? "")}</span>
          <span class="text">${escapeHtml(a.text || state.state)}</span>
          ${a.years_ago ? `<span class="meta">${escapeHtml(this._t("yearsAgo", { n: a.years_ago }))}</span>` : ""}
          ${this._link(a.url, this._t("readMore"))}
        </div>
      </section>`;
  }

  _render() {
    if (!this.shadowRoot) return;
    const c = this._config;
    const parts = [];
    if (this._hass) {
      if (c.show_quote) parts.push(this._renderQuote());
      if (c.show_birthday) parts.push(this._renderBirthday());
      if (c.show_fact) parts.push(this._renderFact());
    }
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>${parts.filter(Boolean).join('<div class="divider"></div>')}</ha-card>`;
    const button = this.shadowRoot.querySelector(".new-quote");
    if (button) button.addEventListener("click", () => this._newQuote());
  }

  async _newQuote() {
    if (this._busy || !this._hass) return;
    this._busy = true;
    this._render();
    try {
      await this._hass.callService("button", "press", {
        entity_id: this._config.button_entity,
      });
    } finally {
      this._busy = false;
      this._lastStates = undefined;
      this._render();
    }
  }
}

const STYLES = `
  :host { display: block; }
  ha-card { overflow: hidden; padding: 0; }
  section { padding: 16px; }
  .divider { height: 1px; background: var(--divider-color); margin: 0 16px; }
  .label {
    display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap;
    font-size: 12px; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .label ha-icon { --mdc-icon-size: 16px; }
  .header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .new-quote {
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 50%; border: none; cursor: pointer;
    background: transparent; color: var(--secondary-text-color);
  }
  .new-quote:hover { background: var(--secondary-background-color); color: var(--primary-color); }
  .new-quote:focus-visible { outline: 2px solid var(--primary-color); }
  .new-quote[disabled] { opacity: 0.5; cursor: default; }
  .new-quote[disabled] ha-icon { animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  blockquote {
    margin: 12px 0 10px; padding: 0 0 0 14px;
    border-left: 3px solid var(--primary-color);
    color: var(--primary-text-color); line-height: 1.4; font-style: italic;
    overflow-wrap: anywhere;
  }
  blockquote.short { font-size: 22px; }
  blockquote.medium { font-size: 18px; }
  blockquote.long { font-size: 16px; }
  .author { display: flex; flex-direction: column; gap: 2px; padding-left: 17px; }
  .author .name { font-weight: 500; color: var(--primary-text-color); }
  .reference { font-size: 13px; color: var(--secondary-text-color); }
  .item { display: flex; gap: 14px; align-items: flex-start; }
  .photo, .icon-box {
    flex: 0 0 64px; width: 64px; height: 64px; border-radius: 12px; object-fit: cover;
    background: var(--secondary-background-color);
  }
  .birthday .photo { border-radius: 50%; }
  .icon-box { display: flex; align-items: center; justify-content: center; color: var(--primary-color); }
  .icon-box ha-icon { --mdc-icon-size: 32px; }
  .body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .title { font-size: 17px; font-weight: 500; color: var(--primary-text-color); }
  .text { color: var(--primary-text-color); line-height: 1.4; overflow-wrap: anywhere; }
  .meta { font-size: 13px; color: var(--secondary-text-color); }
  .chip {
    display: inline-flex; align-items: center; gap: 3px; padding: 1px 8px; border-radius: 10px;
    font-size: 11px; letter-spacing: 0.03em;
    background: var(--secondary-background-color); color: var(--primary-text-color);
  }
  .chip ha-icon { --mdc-icon-size: 13px; }
  .chip.science { color: var(--info-color, #039be5); }
  .chip.history { color: var(--warning-color, #ff9800); }
  .link {
    display: inline-flex; align-items: center; gap: 3px; margin-top: 2px; width: fit-content;
    font-size: 13px; color: var(--primary-color); text-decoration: none;
  }
  .link:hover { text-decoration: underline; }
  .link ha-icon { --mdc-icon-size: 14px; }
  .empty { margin: 0; color: var(--secondary-text-color); }
`;

if (!customElements.get("daily-quote-card")) {
  customElements.define("daily-quote-card", QuoteOfTheDayCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "daily-quote-card",
    name: "Quote of the Day",
    description: "Quote of the day, a famous birthday and a fact of the day.",
    preview: true,
    documentationURL: "https://github.com/laurensdehoorne/HA-quote-of-the-day",
  });
  console.info(`%c DAILY-QUOTE-CARD %c ${CARD_VERSION} `, "color:white;background:#03a9f4", "");
}

/**
 * Daily quote card (custom:daily-quote-card) for Home Assistant.
 *
 * Shows the quote of the day, a motivational quote written by AI (when set
 * up), a famous person born today and a historical or scientific fact, from the Quote of the Day integration. Served and loaded
 * by the integration itself; no resource needs to be added by hand.
 */

const CARD_VERSION = "1.7.1";

const DEFAULTS = {
  quote_entity: "sensor.quote_of_the_day_quote",
  birthday_entity: "sensor.quote_of_the_day_birthday",
  fact_entity: "sensor.quote_of_the_day_on_this_day",
  button_entity: "button.quote_of_the_day_new_quote",
  dislike_entity: "button.quote_of_the_day_dislike_quote",
  ai_quote_entity: "sensor.quote_of_the_day_ai_quote",
  ai_button_entity: "button.quote_of_the_day_new_ai_quote",
  show_quote: true,
  show_ai_quote: true,
  show_reference: true,
  show_birthday: true,
  show_fact: true,
  show_images: true,
  show_new_quote_button: true,
  show_dislike_button: true,
};

const TEXTS = {
  en: {
    title: "Quote of the day",
    aiQuote: "Today's motivation",
    aiBadge: "Written by AI",
    newAiQuote: "New AI quote",
    birthday: "Born today",
    fact: "On this day",
    science: "Science",
    culture: "Culture",
    history: "History",
    born: "born {year}",
    yearsAgo: "{n} years ago",
    newQuote: "New quote",
    dislike: "Not a good quote: never show it again",
    confirmDislike: "Sure? Tap again",
    readMore: "Read more on Wikipedia",
    noData: "Not available",
    missing: "Entity not found: {entity}",
  },
  nl: {
    title: "Citaat van de dag",
    aiQuote: "Motivatie van vandaag",
    aiBadge: "Geschreven door AI",
    newAiQuote: "Nieuw AI-citaat",
    birthday: "Vandaag jarig",
    fact: "Op deze dag",
    science: "Wetenschap",
    culture: "Cultuur",
    history: "Geschiedenis",
    born: "geboren in {year}",
    yearsAgo: "{n} jaar geleden",
    newQuote: "Nieuw citaat",
    dislike: "Geen goed citaat: nooit meer tonen",
    confirmDislike: "Zeker? Tik nogmaals",
    readMore: "Lees meer op Wikipedia",
    noData: "Niet beschikbaar",
    missing: "Entiteit niet gevonden: {entity}",
  },
};

const EDITOR_LABELS = {
  en: {
    show_quote: "Quote",
    show_reference: "Source of the quote",
    show_ai_quote: "AI quote",
    show_birthday: "Birthday",
    show_fact: "Fact of the day",
    show_images: "Pictures",
    show_new_quote_button: "'New quote' button",
    show_dislike_button: "'Not a good quote' button",
    quote_entity: "Quote sensor",
    ai_quote_entity: "AI quote sensor",
    birthday_entity: "Birthday sensor",
    fact_entity: "Fact sensor",
    button_entity: "New quote button",
    dislike_entity: "Dislike button",
    ai_button_entity: "New AI quote button",
  },
  nl: {
    show_quote: "Citaat",
    show_reference: "Bron van het citaat",
    show_ai_quote: "AI-citaat",
    show_birthday: "Verjaardag",
    show_fact: "Weetje van de dag",
    show_images: "Foto's",
    show_new_quote_button: "Knop 'Nieuw citaat'",
    show_dislike_button: "Knop 'Geen goed citaat'",
    quote_entity: "Citaatsensor",
    ai_quote_entity: "AI-citaatsensor",
    birthday_entity: "Verjaardagsensor",
    fact_entity: "Weetjesensor",
    button_entity: "Knop nieuw citaat",
    dislike_entity: "Knop citaat afkeuren",
    ai_button_entity: "Knop nieuw AI-citaat",
  },
};

const FACT_ICONS = {
  science: "mdi:flask-outline",
  culture: "mdi:music-note-outline",
  history: "mdi:calendar-star",
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
    this._confirmDislike = false;
    this._confirmTimer = undefined;
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
            { name: "show_ai_quote", selector: { boolean: {} } },
            { name: "show_birthday", selector: { boolean: {} } },
            { name: "show_fact", selector: { boolean: {} } },
            { name: "show_images", selector: { boolean: {} } },
            { name: "show_new_quote_button", selector: { boolean: {} } },
            { name: "show_dislike_button", selector: { boolean: {} } },
          ],
        },
        {
          type: "expandable",
          name: "",
          title: (document.documentElement.lang || "").startsWith("nl") ? "Entiteiten" : "Entities",
          schema: [
            { name: "quote_entity", selector: { entity: { domain: "sensor" } } },
            { name: "birthday_entity", selector: { entity: { domain: "sensor" } } },
            { name: "fact_entity", selector: { entity: { domain: "sensor" } } },
            { name: "button_entity", selector: { entity: { domain: "button" } } },
            { name: "dislike_entity", selector: { entity: { domain: "button" } } },
            { name: "ai_quote_entity", selector: { entity: { domain: "sensor" } } },
            { name: "ai_button_entity", selector: { entity: { domain: "button" } } },
          ],
        },
      ],
      computeLabel: (schema) => {
        const lang = (document.documentElement.lang || "en").slice(0, 2);
        return (EDITOR_LABELS[lang] || EDITOR_LABELS.en)[schema.name];
      },
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
    const c = this._config;
    let size = 0;
    if (c.show_quote) size += 2;
    if (c.show_ai_quote && this._state(c.ai_quote_entity)) size += 1;
    if (c.show_birthday) size += 1;
    if (c.show_fact) size += 1;
    return Math.max(size, 1);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _watched() {
    const c = this._config;
    return [
      c.quote_entity,
      c.ai_quote_entity,
      c.birthday_entity,
      c.fact_entity,
      c.button_entity,
      c.dislike_entity,
      c.ai_button_entity,
    ];
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

  _image(state, fallbackIcon, round) {
    const url = this._config.show_images ? safeUrl(state.attributes.entity_picture) : "";
    return url
      ? `<img class="thumb${round ? " round" : ""}" src="${escapeHtml(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : `<span class="thumb icon"><ha-icon icon="${fallbackIcon}"></ha-icon></span>`;
  }

  _button(cls, icon, label) {
    return `<button class="${cls}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}" ${
      this._busy ? "disabled" : ""
    }><ha-icon icon="${icon}"></ha-icon></button>`;
  }

  _renderQuote() {
    const c = this._config;
    const state = this._state(c.quote_entity);
    if (!state) {
      return `<p class="empty">${escapeHtml(
        this._hass.states[c.quote_entity]
          ? this._t("noData")
          : this._t("missing", { entity: c.quote_entity }),
      )}</p>`;
    }
    const a = state.attributes;
    const text = a.quote || state.state;
    const confirm = this._confirmDislike;
    const actions = [
      c.show_dislike_button && this._hass.states[c.dislike_entity]
        ? this._button(
            `dislike${confirm ? " confirm" : ""}`,
            confirm ? "mdi:thumb-down" : "mdi:thumb-down-outline",
            this._t(confirm ? "confirmDislike" : "dislike"),
          )
        : "",
      c.show_new_quote_button && this._hass.states[c.button_entity]
        ? this._button("new-quote", "mdi:refresh", this._t("newQuote"))
        : "",
    ].join("");
    const by = [
      a.author ? `<span class="name">&mdash; ${escapeHtml(a.author)}</span>` : "",
      c.show_reference && a.reference
        ? `<span class="reference">${escapeHtml(a.reference)}</span>`
        : "",
    ]
      .filter(Boolean)
      .join('<span class="dot"> &middot; </span>');
    const size = text.length > 180 ? "long" : text.length > 90 ? "medium" : "short";
    return `
      <div class="quote">
        <blockquote class="${size}" lang="${escapeHtml(a.language || "")}" title="${escapeHtml(
          this._t("title"),
        )}">${escapeHtml(text)}</blockquote>
        ${actions ? `<span class="actions">${actions}</span>` : ""}
      </div>
      ${by ? `<div class="by">${by}</div>` : ""}`;
  }

  _renderAiQuote() {
    // Only when the AI quote is set up in the integration's options.
    const c = this._config;
    const state = this._state(c.ai_quote_entity);
    if (!state) return "";
    const a = state.attributes;
    const button = this._hass.states[c.ai_button_entity]
      ? this._button("new-ai-quote", "mdi:refresh", this._t("newAiQuote"))
      : "";
    return `
      <div class="ai" title="${escapeHtml(this._t("aiBadge"))}">
        <ha-icon class="ai-icon" icon="mdi:robot-happy-outline"></ha-icon>
        <p class="ai-text" lang="${escapeHtml(a.language || "")}">${escapeHtml(a.quote || state.state)}</p>
        ${button ? `<span class="actions">${button}</span>` : ""}
      </div>`;
  }

  _row(state, icon, round, line, meta, url) {
    const href = safeUrl(url);
    const tag = href ? "a" : "div";
    const attrs = href
      ? ` href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(
          this._t("readMore"),
        )}"`
      : "";
    return `
      <${tag} class="row"${attrs}>
        ${this._image(state, icon, round)}
        <span class="body">
          <span class="line">${line}</span>
          <span class="meta">${meta}</span>
        </span>
      </${tag}>`;
  }

  _renderBirthday() {
    const state = this._state(this._config.birthday_entity);
    if (!state) return "";
    const a = state.attributes;
    const line = `<b>${escapeHtml(a.name || state.state)}</b>${
      a.description ? `, ${escapeHtml(a.description)}` : ""
    }`;
    const meta = [
      this._t("birthday"),
      a.born ? this._t("born", { year: a.born }) : "",
      a.years_ago ? this._t("yearsAgo", { n: a.years_ago }) : "",
    ]
      .filter(Boolean)
      .map(escapeHtml)
      .join(" &middot; ");
    return this._row(state, "mdi:cake-variant", true, line, meta, a.url);
  }

  _renderFact() {
    const state = this._state(this._config.fact_entity);
    if (!state) return "";
    const a = state.attributes;
    const category = FACT_ICONS[a.category] ? a.category : "history";
    const line = `<b>${escapeHtml(a.year ?? "")}</b> ${escapeHtml(a.text || state.state)}`;
    const meta = [
      `<span class="tag ${category}">${escapeHtml(this._t(category))}</span>`,
      escapeHtml(this._t("fact")),
      a.years_ago ? escapeHtml(this._t("yearsAgo", { n: a.years_ago })) : "",
    ]
      .filter(Boolean)
      .join(" &middot; ");
    return this._row(state, FACT_ICONS[category], false, line, meta, a.url);
  }

  _render() {
    if (!this.shadowRoot) return;
    const c = this._config;
    let top = "";
    let rows = "";
    if (this._hass) {
      top = [c.show_quote ? this._renderQuote() : "", c.show_ai_quote ? this._renderAiQuote() : ""]
        .filter(Boolean)
        .join("");
      rows = [c.show_birthday ? this._renderBirthday() : "", c.show_fact ? this._renderFact() : ""]
        .filter(Boolean)
        .join("");
    }
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        ${top ? `<section class="top">${top}</section>` : ""}
        ${top && rows ? '<div class="divider"></div>' : ""}
        ${rows ? `<section class="rows">${rows}</section>` : ""}
      </ha-card>`;
    const on = (selector, handler) => {
      const element = this.shadowRoot.querySelector(selector);
      if (element) element.addEventListener("click", handler);
    };
    on(".new-quote", () => this._press(this._config.button_entity));
    on(".new-ai-quote", () => this._press(this._config.ai_button_entity));
    on(".dislike", () => this._dislike());
  }

  _dislike() {
    // Two taps: disliking hides a quote for good, so avoid accidental taps.
    clearTimeout(this._confirmTimer);
    if (!this._confirmDislike) {
      this._confirmDislike = true;
      this._render();
      this._confirmTimer = setTimeout(() => {
        this._confirmDislike = false;
        this._render();
      }, 4000);
      return;
    }
    this._confirmDislike = false;
    this._press(this._config.dislike_entity);
  }

  async _press(entityId) {
    if (this._busy || !this._hass) return;
    this._busy = true;
    this._render();
    try {
      await this._hass.callService("button", "press", { entity_id: entityId });
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
  section { padding: 10px 12px; }
  .divider { height: 1px; background: var(--divider-color); margin: 0 12px; }
  .quote, .ai { display: flex; align-items: flex-start; gap: 6px; }
  blockquote {
    flex: 1; min-width: 0; margin: 0; padding: 0 0 0 10px;
    border-left: 3px solid var(--primary-color);
    color: var(--primary-text-color); line-height: 1.35; font-style: italic;
    overflow-wrap: anywhere;
  }
  blockquote.short { font-size: 17px; }
  blockquote.medium { font-size: 15px; }
  blockquote.long { font-size: 14px; }
  .by {
    padding: 3px 0 0 13px; font-size: 12px; color: var(--secondary-text-color);
    overflow-wrap: anywhere;
  }
  .by .name { font-weight: 500; color: var(--primary-text-color); }
  .ai { margin-top: 8px; }
  .ai-icon { --mdc-icon-size: 18px; color: var(--accent-color, #ff9800); flex: 0 0 auto; margin-top: 1px; }
  .ai-text {
    flex: 1; min-width: 0; margin: 0; font-size: 14px; line-height: 1.35; font-weight: 500;
    color: var(--primary-text-color); overflow-wrap: anywhere;
  }
  .actions { display: inline-flex; flex: 0 0 auto; margin: -4px -6px 0 0; }
  .actions button {
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; padding: 0; border: none; border-radius: 15px;
    cursor: pointer; background: transparent; color: var(--secondary-text-color);
  }
  .actions button ha-icon { --mdc-icon-size: 18px; }
  .actions button:hover { background: var(--secondary-background-color); color: var(--primary-color); }
  .actions button:focus-visible { outline: 2px solid var(--primary-color); }
  .actions button[disabled] { opacity: 0.5; cursor: default; }
  .new-quote[disabled] ha-icon, .new-ai-quote[disabled] ha-icon { animation: spin 1s linear infinite; }
  .dislike.confirm, .dislike.confirm:hover {
    background: var(--error-color, #db4437); color: var(--text-primary-color, #fff);
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .rows { display: flex; flex-direction: column; gap: 8px; }
  .row {
    display: flex; align-items: flex-start; gap: 10px; color: inherit; text-decoration: none;
    border-radius: 8px;
  }
  a.row:hover .line { color: var(--primary-color); }
  a.row:focus-visible { outline: 2px solid var(--primary-color); }
  .thumb {
    flex: 0 0 36px; width: 36px; height: 36px; border-radius: 8px; object-fit: cover;
    background: var(--secondary-background-color);
  }
  .thumb.round { border-radius: 50%; }
  .thumb.icon { display: flex; align-items: center; justify-content: center; color: var(--primary-color); }
  .thumb.icon ha-icon { --mdc-icon-size: 20px; }
  .body { display: flex; flex-direction: column; min-width: 0; }
  .line { font-size: 13px; line-height: 1.3; color: var(--primary-text-color); overflow-wrap: anywhere; }
  .line b { font-weight: 500; }
  .meta {
    font-size: 11px; line-height: 1.4; color: var(--secondary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .tag { font-weight: 500; }
  .tag.science { color: var(--info-color, #039be5); }
  .tag.culture { color: var(--success-color, #43a047); }
  .tag.history { color: var(--warning-color, #ff9800); }
  .empty { margin: 0; color: var(--secondary-text-color); }
`;

if (!customElements.get("daily-quote-card")) {
  customElements.define("daily-quote-card", QuoteOfTheDayCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "daily-quote-card",
    name: "Quote of the Day",
    description: "Quote of the day, an AI-written motivation, a famous birthday and a fact of the day.",
    preview: true,
    documentationURL: "https://github.com/laurensdehoorne/HA-quote-of-the-day",
  });
  console.info(`%c DAILY-QUOTE-CARD %c ${CARD_VERSION} `, "color:white;background:#03a9f4", "");
}

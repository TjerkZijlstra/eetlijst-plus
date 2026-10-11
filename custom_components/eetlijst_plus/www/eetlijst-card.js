/* Eetlijst+ dashboard card — served by the eetlijst_plus integration. */

const DOMAIN = "eetlijst_plus";

const STATUS = {
  cook: { icon: "mdi:chef-hat", color: "#F7A93B" },
  eat_only: { icon: "mdi:check", color: "#3E9B41" },
  got_groceries: { icon: "mdi:cart", color: "#8CC8E6" },
  not_attending: { icon: "mdi:close", color: "#EF4B3C" },
  dont_know_yet: { icon: "mdi:help", color: "#9E9E9E" },
  no_status: { icon: "mdi:minus", color: "#CFCFCF" },
};
const PICK_ORDER = ["eat_only", "cook", "got_groceries", "not_attending", "dont_know_yet"];
const EATING = new Set(["cook", "eat_only", "got_groceries"]);

const TEXT = {
  nl: {
    total: "Totaal",
    you: "jij",
    choose: "Jouw status voor",
    guests: "Gasten",
    closed: "Inschrijving gesloten",
    none: "Geen Eetlijst+-entiteiten gevonden. Is de integratie geladen?",
    cook: "Koken",
    eat_only: "Mee-eten",
    got_groceries: "Boodschappen",
    not_attending: "Niet mee-eten",
    dont_know_yet: "Weet nog niet",
    no_status: "Geen status",
  },
  en: {
    total: "Total",
    you: "you",
    choose: "Your status for",
    guests: "Guests",
    closed: "Sign-up closed",
    none: "No Eetlijst+ entities found. Is the integration loaded?",
    cook: "Cooking",
    eat_only: "Eating",
    got_groceries: "Groceries",
    not_attending: "Not eating",
    dont_know_yet: "Don't know yet",
    no_status: "No status",
  },
};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class EetlijstCard extends HTMLElement {
  setConfig(config) {
    this._config = { days: 7, title: undefined, housemates: true, ...(config || {}) };
    this._picked = null; // date string of the open picker
    this._busy = false;
    this._error = null;
    this._sig = null;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const sig = this._signature();
    if (sig !== this._sig) {
      this._sig = sig;
      this._render();
    }
  }

  getCardSize() {
    return this._config?.housemates === false ? 3 : 3 + (this._members()?.length || 3);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  static getStubConfig() {
    return {};
  }

  // ---- data ------------------------------------------------------------
  _t(key) {
    const lang = (this._hass?.locale?.language || "nl").startsWith("nl") ? "nl" : "en";
    return TEXT[lang][key] ?? key;
  }

  _entities() {
    const hass = this._hass;
    if (!hass?.entities) return [];
    let ents = Object.values(hass.entities).filter((e) => e.platform === DOMAIN);
    const devices = [...new Set(ents.map((e) => e.device_id))];
    const device = this._config.device_id || devices[0];
    return ents.filter((e) => e.device_id === device);
  }

  _members() {
    if (!this._hass) return [];
    return this._entities()
      .filter((e) => e.translation_key === "member_status")
      .map((e) => this._hass.states[e.entity_id])
      .filter((s) => s && s.state !== "unavailable")
      .sort((a, b) => (a.attributes.order ?? 99) - (b.attributes.order ?? 99));
  }

  _days(members) {
    const set = new Set();
    for (const m of members) Object.keys(m.attributes.week || {}).forEach((d) => set.add(d));
    return [...set].sort().slice(0, this._config.days);
  }

  _signature() {
    const members = this._members();
    return JSON.stringify([
      this._hass?.locale?.language,
      members.map((m) => [m.entity_id, m.state, m.attributes.week, m.attributes.week_guests, m.attributes.week_open]),
    ]);
  }

  _groupName() {
    if (this._config.title) return this._config.title;
    const ent = this._entities()[0];
    const dev = ent && this._hass.devices?.[ent.device_id];
    return dev?.name_by_user || dev?.name || "Eetlijst";
  }

  _dayLabel(dateStr, long = false) {
    const d = new Date(`${dateStr}T12:00:00`);
    const lang = this._hass?.locale?.language || "nl";
    if (long) return d.toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long" });
    return {
      wd: d.toLocaleDateString(lang, { weekday: "short" }).replace(".", ""),
      day: d.getDate(),
    };
  }

  // ---- render ----------------------------------------------------------
  _bubble(status, guests = 0, size = "") {
    const s = STATUS[status] || STATUS.no_status;
    const g = guests > 0 ? `<span class="guests">+${guests}</span>` : "";
    return `<span class="bubble ${size}" style="background:${s.color}" title="${esc(this._t(status))}">
      <ha-icon icon="${s.icon}"></ha-icon>${g}</span>`;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    if (!this._hass) {
      this.shadowRoot.innerHTML = "";
      return;
    }
    const members = this._members();
    if (!members.length) {
      this.shadowRoot.innerHTML = `${STYLE}<ha-card><div class="empty">${esc(this._t("none"))}</div></ha-card>`;
      return;
    }
    const days = this._days(members);
    const today = days[0];
    const me = members.find((m) => m.attributes.is_me);

    const totals = days.map((d) =>
      members.reduce((sum, m) => {
        const st = m.attributes.week?.[d];
        return EATING.has(st) ? sum + 1 + (m.attributes.week_guests?.[d] || 0) : sum;
      }, 0)
    );
    const openOf = (d) => members[0]?.attributes.week_open?.[d] !== false;

    const cols = `grid-template-columns: minmax(70px, 1.4fr) repeat(${days.length}, minmax(0, 1fr));`;

    const head = days
      .map((d) => {
        const l = this._dayLabel(d);
        const lock = openOf(d) ? "" : `<ha-icon class="lock" icon="mdi:lock"></ha-icon>`;
        return `<div class="dh ${d === today ? "today" : ""}"><span class="wd">${esc(l.wd)}</span><span class="dn">${l.day}${lock}</span></div>`;
      })
      .join("");

    const shown = this._config.housemates === false ? members.filter((m) => m.attributes.is_me) : members;
    const rows = shown
      .map((m) => {
        const mine = m.attributes.is_me;
        const cells = days
          .map((d) => {
            const st = m.attributes.week?.[d] || "no_status";
            const guests = m.attributes.week_guests?.[d] || 0;
            const b = this._bubble(st, guests);
            if (!mine) return `<div class="cell">${b}</div>`;
            const sel = this._picked === d ? "picked" : "";
            return `<button class="cell mine ${sel}" data-day="${d}" aria-label="${esc(this._t("choose"))} ${esc(this._dayLabel(d, true))}">${b}</button>`;
          })
          .join("");
        const name = mine
          ? `${esc(m.attributes.name)} <span class="you">(${esc(this._t("you"))})</span>`
          : esc(m.attributes.name);
        return `<div class="row ${mine ? "me" : ""}" style="${cols}"><div class="name">${name}</div>${cells}</div>`;
      })
      .join("");

    const totalRow = `<div class="row total" style="${cols}"><div class="name">${esc(this._t("total"))}</div>${totals
      .map((n) => `<div class="cell"><span class="count">${n}</span></div>`)
      .join("")}</div>`;

    let picker = "";
    if (this._picked && me) {
      const d = this._picked;
      const cur = me.attributes.week?.[d];
      const guests = me.attributes.week_guests?.[d] || 0;
      const closed = openOf(d) ? "" : `<div class="closed"><ha-icon icon="mdi:lock"></ha-icon>${esc(this._t("closed"))}</div>`;
      picker = `<div class="picker ${this._busy ? "busy" : ""}">
        <div class="ptitle">${esc(this._t("choose"))} ${esc(this._dayLabel(d, true))}</div>
        ${closed}
        <div class="options">${PICK_ORDER.map(
          (st) => `<button class="opt ${st === cur ? "active" : ""}" data-status="${st}">
            ${this._bubble(st, 0, "big")}<span>${esc(this._t(st))}</span></button>`
        ).join("")}</div>
        <div class="guestrow"><span>${esc(this._t("guests"))}</span>
          <button class="step" data-guests="${Math.max(0, guests - 1)}" ${guests <= 0 ? "disabled" : ""}><ha-icon icon="mdi:minus"></ha-icon></button>
          <span class="gnum">${guests}</span>
          <button class="step" data-guests="${guests + 1}"><ha-icon icon="mdi:plus"></ha-icon></button>
        </div>
        ${this._error ? `<div class="error">${esc(this._error)}</div>` : ""}
      </div>`;
    }

    this.shadowRoot.innerHTML = `${STYLE}
      <ha-card>
        <div class="header">
          <div class="title"><ha-icon icon="mdi:silverware-fork-knife"></ha-icon>${esc(this._groupName())}</div>
          <div class="totalbadge"><span class="count big">${totals[0] ?? 0}</span><span>${esc(this._t("total"))}</span></div>
        </div>
        <div class="grid">
          <div class="row head" style="${cols}"><div></div>${head}</div>
          ${rows}
          ${totalRow}
        </div>
        ${picker}
      </ha-card>`;
  }

  // ---- actions ---------------------------------------------------------
  _onClick(ev) {
    const path = ev.composedPath();
    const find = (attr) => path.find((el) => el.dataset && el.dataset[attr] !== undefined);
    const day = find("day");
    if (day) {
      this._picked = this._picked === day.dataset.day ? null : day.dataset.day;
      this._error = null;
      this._render();
      return;
    }
    const opt = find("status");
    if (opt && this._picked) {
      this._set({ status: opt.dataset.status });
      return;
    }
    const step = find("guests");
    if (step && this._picked && !step.disabled) {
      this._set({ guests: Number(step.dataset.guests) });
    }
  }

  async _set(data) {
    if (this._busy) return;
    this._busy = true;
    this._error = null;
    this._render();
    try {
      await this._hass.callService(DOMAIN, "set_status", { date: this._picked, ...data });
      if (data.status) this._picked = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._busy = false;
    this._sig = null;
    this._render();
  }
}

const STYLE = `<style>
  ha-card { padding: 16px; overflow: hidden; }
  .empty { color: var(--secondary-text-color); }
  .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; gap: 12px; }
  .title { display: flex; align-items: center; gap: 8px; font-size: 1.15rem; font-weight: 500; min-width: 0; }
  .title ha-icon { color: #F7A93B; flex: none; }
  .totalbadge { display: flex; flex-direction: column; align-items: center; color: var(--secondary-text-color); font-size: 0.75rem; gap: 2px; flex: none; }
  .grid { display: flex; flex-direction: column; gap: 4px; }
  .row { display: grid; align-items: center; column-gap: 4px; }
  .row.me { background: color-mix(in srgb, var(--primary-color) 8%, transparent); border-radius: 12px; }
  .row.total { border-top: 1px solid var(--divider-color); padding-top: 6px; margin-top: 2px; }
  .name { font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-left: 6px; }
  .row.total .name { color: var(--secondary-text-color); }
  .you { color: var(--secondary-text-color); font-size: 0.8rem; }
  .dh { display: flex; flex-direction: column; align-items: center; font-size: 0.72rem; color: var(--secondary-text-color); line-height: 1.2; padding: 2px 0; border-radius: 8px; }
  .dh .wd { text-transform: lowercase; }
  .dh .dn { font-weight: 600; display: flex; align-items: center; }
  .dh.today { color: var(--primary-text-color); background: color-mix(in srgb, var(--primary-color) 12%, transparent); }
  .lock { --mdc-icon-size: 11px; margin-left: 1px; }
  .cell { display: flex; justify-content: center; align-items: center; padding: 3px 0; }
  button.cell { background: none; border: 0; cursor: pointer; font: inherit; border-radius: 50%; }
  button.cell:hover .bubble, button.cell.picked .bubble { box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color) 45%, transparent); }
  .bubble { --b: clamp(24px, 7.5vw, 34px); position: relative; width: var(--b); height: var(--b); border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center; color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.18); flex: none; }
  .bubble ha-icon { --mdc-icon-size: calc(var(--b) * 0.58); display: inline-flex; }
  .bubble.big { --b: 44px; }
  .guests { position: absolute; top: -5px; right: -7px; background: var(--card-background-color, #fff); color: var(--primary-text-color);
    font-size: 0.62rem; font-weight: 700; border-radius: 8px; padding: 0 3px; box-shadow: 0 1px 2px rgba(0,0,0,.25); }
  .count { display: inline-flex; align-items: center; justify-content: center; min-width: 26px; height: 26px; border-radius: 13px;
    background: #3E9B41; color: #fff; font-weight: 700; font-size: 0.85rem; padding: 0 4px; box-sizing: border-box; }
  .count.big { min-width: 40px; height: 40px; border-radius: 20px; font-size: 1.25rem; }
  .picker { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--divider-color); }
  .picker.busy { opacity: .55; pointer-events: none; }
  .ptitle { font-weight: 500; margin-bottom: 10px; }
  .ptitle::first-letter { text-transform: uppercase; }
  .closed { display: flex; align-items: center; gap: 6px; color: var(--warning-color, #F7A93B); font-size: 0.85rem; margin-bottom: 8px; }
  .closed ha-icon { --mdc-icon-size: 16px; }
  .options { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
  .opt { display: flex; flex-direction: column; align-items: center; gap: 6px; background: none; border: 0; cursor: pointer;
    color: var(--primary-text-color); font: inherit; font-size: 0.72rem; text-align: center; padding: 6px 2px; border-radius: 12px; }
  .opt:hover { background: var(--secondary-background-color); }
  .opt.active { background: color-mix(in srgb, var(--primary-color) 14%, transparent); font-weight: 600; }
  .guestrow { display: flex; align-items: center; gap: 10px; margin-top: 12px; font-size: 0.9rem; }
  .guestrow > span:first-child { flex: 1; }
  .step { width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--divider-color); background: none; cursor: pointer;
    color: var(--primary-text-color); display: inline-flex; align-items: center; justify-content: center; }
  .step:disabled { opacity: .4; cursor: default; }
  .step ha-icon { --mdc-icon-size: 18px; }
  .gnum { min-width: 18px; text-align: center; font-weight: 600; }
  .error { margin-top: 10px; color: var(--error-color, #db4437); font-size: 0.85rem; }
</style>`;

if (!customElements.get("eetlijst-card")) {
  customElements.define("eetlijst-card", EetlijstCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "eetlijst-card",
    name: "Eetlijst",
    description: "Weekoverzicht van je Eetlijst met inschrijven per dag.",
    preview: false,
  });
}

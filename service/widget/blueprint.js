// Сервис Blueprint: список диаграмм и «Создать» — инструкция для ИИ-агента.
// Диаграмма открывается отдельной страницей /blueprint/<эпик> в новой вкладке.
(() => {
  "use strict";
  const BASE = location.pathname.replace(/\/(index\.html)?$/, "").replace(/\/+$/, "") || "/blueprint";
  const $ = (id) => document.getElementById(id);
  let data = null, search = "";

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat(Infinity)) if (c !== undefined && c !== null && c !== false) el.append(c instanceof Node ? c : String(c));
    return el;
  }
  const date = (iso) => iso ? new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) : "";

  async function load() {
    const r = await fetch(BASE + "/api/list");
    if (r.status === 401 || r.status === 403) return login();
    const d = await r.json().catch(() => null);
    if (!d || !d.ok) { $("list").replaceChildren(h("p", { class: "bp-empty" }, (d && d.message) || "Сервис недоступен")); return; }
    data = d;
    render();
  }

  function login() {
    $("app").hidden = true; $("login").hidden = false;
    const f = $("loginFrame");
    f.src = BASE + "/login";
    f.onload = () => { try { if (/Вход выполнен/.test(f.contentDocument.title)) { $("login").hidden = true; $("app").hidden = false; load(); } } catch (_) { /* ещё на входе */ } };
  }

  function render() {
    const q = search.trim().toLowerCase();
    const rows = data.diagrams.filter((m) => !q || (m.title + " " + m.epic).toLowerCase().includes(q));
    $("list").replaceChildren(rows.length
      ? h("ul", { class: "bp-list" }, rows.map((m) => h("li", {},
          h("a", { class: "bp-row", href: `${BASE}/${encodeURIComponent(m.epic)}`, target: "_blank", rel: "noopener" },
            h("span", { class: "bp-row__main" }, h("b", {}, m.title), h("small", {}, `${m.epic} · ${date(m.updated)}`)),
            h("span", { class: "bp-row__end" }, m.next ? m.next.title : "Готово"),
            h("span", { class: "bp-row__go", "aria-hidden": "true" }, "↗")))))
      : h("p", { class: "bp-empty" }, data.diagrams.length ? "Ничего не найдено" : "Диаграмм пока нет"));
  }

  // ---------- «Создать» ----------
  function prompt(epic, via) {
    const e = epic || "<эпик>";
    return via === "mcp"
      ? `Собери Service Blueprint по БФТ эпика ${e}: MCP «Система Blueprint», промт blueprint_full_cycle.`
      : `/bft-blueprint ${e}`;
  }

  function createSheet() {
    const cands = data?.candidates || [];
    let epic = cands[0]?.epic || "", via = "mcp";
    const body = $("sheetBody");
    const draw = () => {
      const text = prompt(epic, via);
      body.replaceChildren(
        cands.length ? h("select", { class: "ds-input", "aria-label": "БФТ", onchange: (e) => { epic = e.target.value; draw(); } },
          cands.map((c) => h("option", { value: c.epic, selected: c.epic === epic }, c.title))) : null,
        h("div", { class: "bp-seg", role: "radiogroup" }, [["mcp", "Через MCP"], ["skill", "Навыком в чате"]].map(([k, l]) =>
          h("button", { type: "button", role: "radio", "aria-checked": String(via === k), onclick: () => { via = k; draw(); } }, l))),
        h("pre", { class: "bp-prompt" }, text),
        via === "mcp" ? h("p", { class: "bp-hint" }, "MCP: ", h("code", {}, `${location.origin}${BASE}/mcp`)) : null,
        h("button", { class: "ds-btn ds-btn--primary", type: "button", onclick: () => copy(text) }, "Копировать"));
    };
    draw();
    $("sheet").hidden = $("scrim").hidden = false;
  }
  const close = () => { $("sheet").hidden = $("scrim").hidden = true; };

  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast("Скопировано"); } catch (_) { window.prompt("Скопируйте:", text); }
  }
  function toast(text) {
    const t = h("div", { class: "bp-toast" }, text);
    $("toasts").append(t);
    setTimeout(() => t.remove(), 2000);
  }

  $("create").onclick = createSheet;
  $("sheetClose").onclick = close;
  $("scrim").onclick = close;
  addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  $("search").oninput = (e) => { search = e.target.value; if (data) render(); };
  load();
})();

// Сервис Blueprint — интерфейс. Без фреймворков и сборки: один файл, DOM строится функцией h() (без innerHTML).
//   ?epic=<слаг>   сразу страница диаграммы (вход из отчёта спринта и по ссылке)
//   ?tab=map|story|questions|jobs   вкладка правой панели
//   ?embed=1       внутри оболочки /sprints/ — без логотипа
(() => {
  "use strict";
  const BASE = location.pathname.replace(/\/(index\.html)?$/, "").replace(/\/+$/, "") || "/blueprint";
  const API = BASE + "/api/";
  const qs = new URLSearchParams(location.search);
  if (qs.get("embed") === "1") document.body.classList.add("embed");
  if (qs.get("theme") === "light" || qs.get("theme") === "dark") document.documentElement.dataset.theme = qs.get("theme");

  const $ = (id) => document.getElementById(id);
  const app = $("app");
  const state = { config: null, list: null, map: null, epic: qs.get("epic") || "", tab: qs.get("tab") || "map",
                  open: new Set(), outputs: {}, busy: new Set(), qFilter: "open", search: "", poll: null };

  const STATUS = {
    done: ["сделано", "success"], review: ["ждёт PO", "warning"], stale: ["пересобрать", "warning"], ready: ["можно делать", "accent"],
    blocked: ["рано", ""], skipped: ["не нужен", ""], optional: ["по желанию", ""],
  };

  // ---------- DOM ----------
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "data") for (const [dk, dv] of Object.entries(v)) el.dataset[dk] = dv;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === undefined || kid === null || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const chip = (text, tone) => h("span", { class: "ds-chip" + (tone ? " ds-chip--" + tone : "") }, text);
  const fmtDate = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) + " " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  };
  function toast(text, kind) {
    const t = h("div", { class: "bp-toast", data: { kind: kind || "" } }, text);
    $("toasts").append(t);
    setTimeout(() => t.remove(), kind === "err" ? 6000 : 2800);
  }

  // ---------- API ----------
  class NeedLogin extends Error {}
  async function api(name, params, body) {
    const url = API + name + (params ? "?" + new URLSearchParams(params) : "");
    const r = await fetch(url, body === undefined ? { credentials: "same-origin" } : {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-Blueprint": "1" }, body: JSON.stringify(body),
    });
    if (r.status === 401 || r.status === 403) {
      let msg = ""; try { msg = (await r.json()).message || ""; } catch (_) { /* пусто */ }
      if (r.status === 401 || /вход/.test(msg)) throw new NeedLogin(msg);
      throw new Error(msg || "доступ запрещён");
    }
    const data = await r.json().catch(() => ({ ok: false, message: "ответ не JSON (HTTP " + r.status + ")" }));
    if (!data.ok) throw new Error(data.message || data.error || "HTTP " + r.status);
    return data;
  }
  function showLogin() {
    app.hidden = true;
    $("login").hidden = false;
    const f = $("loginFrame");
    f.src = BASE + "/login";
    f.onload = () => {
      try { if (/Вход выполнен/.test(f.contentDocument.title)) { $("login").hidden = true; app.hidden = false; route(); } } catch (_) { /* чужой origin — ещё на входе */ }
    };
  }
  async function guarded(fn) {
    try { return await fn(); } catch (e) {
      if (e instanceof NeedLogin) { showLogin(); return undefined; }
      toast(e.message, "err");
      throw e;
    }
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); toast("Команда скопирована — вставьте в чат агента"); }
    catch (_) { prompt("Скопируйте команду:", text); }
  }

  // ---------- маршрут ----------
  function go(epic, tab) {
    state.epic = epic || "";
    if (tab) state.tab = tab;
    const p = new URLSearchParams(location.search);
    if (state.epic) { p.set("epic", state.epic); p.set("tab", state.tab); } else { p.delete("epic"); p.delete("tab"); }
    history.pushState(null, "", location.pathname + (p.toString() ? "?" + p : ""));
    route();
  }
  window.addEventListener("popstate", () => {
    const p = new URLSearchParams(location.search);
    state.epic = p.get("epic") || ""; state.tab = p.get("tab") || "map"; route();
  });
  $("back").addEventListener("click", () => go(""));
  $("mcpBtn").addEventListener("click", showMcp);
  $("sheetClose").addEventListener("click", closeSheet);
  $("scrim").addEventListener("click", closeSheet);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });

  async function route() {
    clearTimeout(state.poll);
    if (!state.config) {
      const c = await guarded(() => api("config")).catch(() => null);
      if (!c) return;
      state.config = c;
    }
    if (state.epic) return loadMap();
    return loadList();
  }

  // ---------- список диаграмм ----------
  async function loadList() {
    $("back").hidden = true;
    $("title").textContent = "Сервис Blueprint";
    $("subtitle").textContent = "Service Blueprint по БФТ";
    document.title = "Сервис Blueprint";
    if (!state.list) app.replaceChildren(h("div", { class: "bp-empty" }, h("span", { class: "bp-spin" }), " Загружаю диаграммы…"));
    const data = await guarded(() => api("list"));
    if (!data) return;
    state.list = data;
    renderList();
    if (data.running.length) state.poll = setTimeout(loadList, 5000);
  }

  function renderList() {
    const data = state.list, s = state.search.trim().toLowerCase();
    const match = (m) => !s || (m.title + " " + m.epic + " " + (m.teams || []).join(" ")).toLowerCase().includes(s);
    const maps = data.diagrams.filter(match), cands = data.candidates.filter(match);
    const running = new Set(data.running.map((j) => j.epic));
    const search = h("input", { class: "ds-input", type: "search", placeholder: "Поиск по названию, эпику, команде", value: state.search,
      oninput: (e) => { state.search = e.target.value; renderList(); $("search")?.focus(); }, id: "search" });
    app.replaceChildren(...[
      h("div", { class: "bp-toolbar" }, search,
        h("button", { class: "ds-btn ds-btn--primary", onclick: () => newDiagram() }, "+ Новая диаграмма")),
      h("div", { class: "bp-h" }, h("h2", {}, "Диаграммы"), h("span", { class: "ds-muted" }, `${data.diagrams.length} · документы: ${data.docs}`)),
      maps.length ? h("div", { class: "bp-grid" }, maps.map((m) => tile(m, running.has(m.epic))))
        : h("div", { class: "ds-card bp-empty" }, h("b", {}, data.diagrams.length ? "Ничего не нашлось" : "Диаграмм пока нет"),
          data.diagrams.length ? "Измените запрос поиска." : "Выберите БФТ ниже или нажмите «Новая диаграмма» — первая карта начнётся с истории через экраны."),
      cands.length ? [
        h("div", { class: "bp-h" }, h("h2", {}, "БФТ без диаграммы"), h("span", { class: "ds-muted" }, String(data.candidates.length))),
        h("div", { class: "ds-card" }, cands.map(candRow)),
      ] : null,
    ].flat(Infinity).filter(Boolean));
  }

  function tile(m, isRunning) {
    const c = m.counts || {};
    return h("button", { class: "ds-card bp-tile", type: "button", onclick: () => go(m.epic, "map") },
      h("div", { class: "bp-tile__meta" }, chip(m.epic), m.bft === "fast" ? chip("БФТ fast", "warning") : null,
        isRunning ? chip("агент работает", "accent") : null, h("span", {}, "изменено " + fmtDate(m.updated))),
      h("div", { class: "bp-tile__title" }, m.title),
      h("div", { class: "bp-rail", title: m.stages.map((s) => s.title + ": " + STATUS[s.status][0]).join("\n") },
        m.stages.map((s) => h("i", { data: { s: s.status } }))),
      h("div", { class: "bp-tile__next" },
        h("span", { class: "ds-muted" }, `${m.progress.done}/${m.progress.total}`),
        m.next ? [h("span", {}, "дальше:"), h("b", {}, m.next.title), chip(STATUS[m.next.status][0], STATUS[m.next.status][1])]
          : chip("карта готова", "success")),
      h("div", { class: "bp-tile__meta" },
        c.tasks ? h("span", {}, `${c.tasks} задач · ${c.cards} карточек`) : null,
        c.questions_open ? chip(`вопросов ${c.questions_open}`, c.blockers_open ? "danger" : "") : null,
        c.blockers_open ? chip(`блокеров ${c.blockers_open}`, "danger") : null,
        c.deviations ? chip(`расхождений ${c.deviations}`, "warning") : null,
        (m.teams || []).length ? h("span", {}, m.teams.slice(0, 4).join(", ") + (m.teams.length > 4 ? "…" : "")) : null));
  }

  function candRow(c) {
    return h("div", { class: "bp-cand" },
      h("div", { class: "bp-cand__main" }, h("b", {}, c.title), h("small", { class: "ds-muted" }, `${c.epic} · БФТ ${c.bft} · ${fmtDate(c.updated)}`)),
      h("button", { class: "ds-btn ds-btn--sm", onclick: () => newDiagram(c) }, "Начать карту"));
  }

  function newDiagram(cand) {
    const cands = state.list?.candidates || [];
    if (!cand && !cands.length) {
      openSheet("Новая диаграмма", [h("p", {}, "Диаграмма строится по готовому БФТ эпика. Свободных БФТ в каталоге нет."),
        h("p", { class: "ds-muted" }, "Сначала напишите БФТ (/bft-fast, затем /bft-deep) — или откройте существующую диаграмму, чтобы пересобрать её.")]);
      return;
    }
    const pick = cand || cands[0];
    const sel = h("select", { class: "ds-input", onchange: (e) => { const c = cands.find((x) => x.epic === e.target.value); render(c); } },
      cands.map((c) => h("option", { value: c.epic, selected: c.epic === pick.epic }, `${c.title} (${c.epic})`)));
    const box = h("div", { class: "bp-sheet__body", style: "padding:0;gap:12px;display:flex;flex-direction:column" });
    function render(c) {
      const step = `/bft-blueprint ${c.epic} --story`, auto = `/bft-blueprint ${c.epic} --auto`;
      box.replaceChildren(...[
        c.bft === "fast" ? h("p", { class: "ds-chip ds-chip--warning" }, "БФТ только fast — карта выйдет тонкой; лучше сначала /bft-deep") : null,
        option("Пошагово — рекомендуется", "Сначала история через экраны: агент задаст вопросы по пробелам БФТ, вы согласуете историю — затем карта.", step, c.epic, "story"),
        option("Автопилот", "История и карта за один заход без вопросов; всё неизвестное — открытыми вопросами на карте. История останется черновиком.", auto, c.epic, "auto"),
      ].filter(Boolean));
    }
    render(pick);
    openSheet("Новая диаграмма", [h("label", { class: "ds-label" }, "БФТ"), sel, box]);
  }

  function option(title, text, cmd, epic, stage) {
    return h("div", { class: "ds-card", style: "padding:14px;display:flex;flex-direction:column;gap:8px" },
      h("b", {}, title), h("span", { class: "ds-muted" }, text), cmdRow(cmd),
      h("div", { class: "bp-actions" }, agentBtn(epic, stage, () => { closeSheet(); go(epic, "jobs"); })));
  }

  // ---------- диаграмма ----------
  async function loadMap(quiet) {
    $("back").hidden = false;
    if (!quiet) app.replaceChildren(h("div", { class: "bp-empty" }, h("span", { class: "bp-spin" }), " Открываю диаграмму…"));
    const data = await guarded(() => api("map", { epic: state.epic }));
    if (!data) return;
    state.map = data.map; state.jobs = data.jobs;
    const nxt = data.map.next;
    if (!quiet && !state.open.size && nxt) state.open.add(nxt.key);
    renderMap();
    if (data.jobs.some((j) => j.state === "running")) state.poll = setTimeout(() => loadMap(true), 4000);
  }

  function renderMap() {
    const m = state.map, f = m.facts, c = m.counts;
    $("title").textContent = m.title;
    $("subtitle").textContent = `${m.epic} · ${m.progress.done}/${m.progress.total} этапов · изменено ${fmtDate(m.updated)}`;
    document.title = m.title + " — Blueprint";
    const running = state.jobs.find((j) => j.state === "running");
    const summary = h("div", { class: "ds-card bp-summary" },
      h("div", { class: "bp-rail" }, m.stages.map((s) => h("i", { data: { s: s.status }, title: s.title }))),
      h("div", { class: "bp-summary__row" },
        c.tasks ? chip(`${c.tasks} задач`) : null, c.cards ? chip(`${c.cards} карточек`) : null,
        c.contracts ? chip(`${c.contracts} контрактов`) : null,
        c.questions_open ? chip(`вопросов ${c.questions_open}`, c.blockers_open ? "danger" : "") : null,
        c.deviations ? chip(`расхождений ${c.deviations}`, "warning") : null,
        (f.project?.teams || []).map((t) => chip(t.name))),
      running ? h("div", { class: "bp-tile__next" }, h("span", { class: "bp-spin" }), `агент: ${stageTitle(running.stage)} · с ${fmtDate(running.started)}`,
        h("button", { class: "ds-btn ds-btn--sm", onclick: () => setTab("jobs") }, "Журнал")) : null,
      !f.project && !running ? h("div", { class: "bp-actions" },
        h("span", { class: "ds-muted" }, "Без остановок:"), cmdRow(m.auto_command), agentBtn(m.epic, "auto")) : null);
    const steps = h("ol", { class: "bp-steps" }, m.stages.map((s, i) => stepCard(s, i)));
    app.replaceChildren(h("div", { class: "bp-detail" }, h("div", {}, summary, steps), pane()));
  }
  const stageTitle = (key) => key === "auto" ? "автопилот" : (state.map?.stages.find((s) => s.key === key)?.title || key);

  function stepCard(s, i) {
    const open = state.open.has(s.key);
    const [label, tone] = STATUS[s.status];
    const body = open ? h("div", { class: "bp-step__body" },
      s.missing.length ? h("ul", { class: "bp-missing" }, h("span", {}, "Не хватает:"), s.missing.map((x) => h("li", {}, x))) : null,
      s.artifacts.length ? h("div", { class: "bp-art" }, s.artifacts.map(artifactChip)) : null,
      s.command ? [h("div", { class: "ds-label" }, "Агенту"), cmdRow(s.command), h("div", { class: "bp-actions" }, agentBtn(state.map.epic, s.key))] : null,
      s.actions.length ? [h("div", { class: "ds-label" }, "Сервис — без модели"), h("div", { class: "bp-actions" }, s.actions.map((a) => actionBtn(s, a)))] : null,
      state.outputs[s.key] ? h("pre", { class: "bp-out", data: { ok: state.outputs[s.key].ok ? "1" : "0" } }, state.outputs[s.key].text) : null,
    ) : null;
    return h("li", { class: "ds-card bp-step", data: { s: s.status, open: open ? "1" : "0" } },
      h("button", { class: "bp-step__head", type: "button", "aria-expanded": open ? "true" : "false",
        onclick: () => { open ? state.open.delete(s.key) : state.open.add(s.key); renderMap(); } },
        h("span", { class: "bp-num" }, s.status === "done" ? "✓" : String(i + 1)),
        h("span", { class: "bp-step__title" }, h("b", {}, s.title), h("small", {}, s.summary || "")),
        chip(label, tone)),
      body);
  }

  function artifactChip(a) {
    if (a.kind === "map" || a.kind === "story") return h("button", { class: "ds-chip ds-chip--accent", onclick: () => setTab(a.kind) }, "▸ " + a.label);
    if (a.kind === "url") return h("a", { class: "ds-chip ds-chip--accent", href: a.path, target: "_blank", rel: "noopener" }, "↗ " + a.label);
    return h("button", { class: "ds-chip", title: a.path, onclick: () => showFile(a) }, a.label);
  }

  function cmdRow(cmd) {
    return h("div", { class: "bp-cmd" }, h("code", { title: cmd }, cmd),
      h("button", { class: "ds-btn ds-btn--sm", onclick: () => copy(cmd), title: "Скопировать" }, "Копировать"));
  }

  function agentBtn(epic, stage, after) {
    if (!state.config?.agent) return h("span", { class: "ds-muted", style: "font-size:13px" }, "Вставьте команду в чат агента (харнесс, Claude Code) или ведите этап через MCP.");
    const running = (state.jobs || []).some((j) => j.state === "running" && j.epic === epic);
    return h("button", { class: "ds-btn ds-btn--primary ds-btn--sm", disabled: running || undefined, onclick: async (e) => {
      const note = prompt("Комментарий агенту (необязательно):", "");
      if (note === null) return;
      e.target.disabled = true;
      try {
        const r = await guarded(() => api("agent", null, { epic, stage, note }));
        if (r) { toast("Агент запущен"); state.tab = "jobs"; if (after) after(); else loadMap(true); }
      } catch (_) { e.target.disabled = false; }
    } }, running ? "Агент уже работает" : "Запустить агента");
  }

  function actionBtn(s, a) {
    const key = s.key + ":" + a.id, busy = state.busy.has(key);
    return h("button", { class: "ds-btn ds-btn--sm", disabled: busy || undefined, onclick: async () => {
      if (a.id === "story_approve" && !confirm("Согласовать историю? После этого можно строить карту.")) return;
      if (a.id === "auto") { newDiagram(state.list?.candidates?.find((c) => c.epic === state.map.epic)); return; }
      state.busy.add(key); renderMap();
      try {
        const r = await guarded(() => api("run", null, { epic: state.map.epic, action: a.id }));
        if (r) state.outputs[s.key] = { ok: r.result.ok, text: (r.result.ok ? "✓ " : "✗ код " + r.result.code + " · ") + a.label + "\n\n" + (r.result.output || "") };
      } catch (e) { state.outputs[s.key] = { ok: false, text: e.message }; }
      state.busy.delete(key);
      await loadMap(true);
    } }, busy ? [h("span", { class: "bp-spin" }), " " + a.label] : a.label);
  }

  // ---------- правая панель ----------
  function setTab(tab) {
    state.tab = tab;
    const p = new URLSearchParams(location.search); p.set("tab", tab);
    history.replaceState(null, "", location.pathname + "?" + p);
    renderMap();
  }

  function pane() {
    const m = state.map, f = m.facts, qOpen = m.counts.questions_open || 0;
    const tabs = [["map", "Карта"], ["story", "История"], ["questions", "Вопросы", qOpen], ["jobs", "Журнал", state.jobs.length || ""]];
    const body = h("div", { class: "bp-pane__body" });
    const tab = state.tab;
    if (tab === "map" || tab === "story") {
      const ready = tab === "map" ? f.map_html : f.story?.html;
      body.append(ready
        ? h("iframe", { class: "bp-frame", title: tab === "map" ? "Карта инициативы" : "История через экраны",
            sandbox: "allow-scripts allow-popups allow-downloads", src: API + "page?" + new URLSearchParams({ epic: m.epic, kind: tab, t: m.updated || "" }) })
        : h("div", { class: "bp-empty" }, h("b", {}, tab === "map" ? "Страница карты ещё не собрана" : "Страницы истории ещё нет"),
            tab === "map" ? "Пройдите этап «Карта инициативы» — после сборки она появится здесь." : "Пройдите этап «История через экраны»."));
    } else if (tab === "questions") {
      body.append(questionsPane());
    } else {
      body.append(jobsPane());
    }
    return h("div", { class: "ds-card bp-pane" },
      h("div", { class: "bp-tabs", role: "tablist" }, tabs.map(([k, label, n]) =>
        h("button", { role: "tab", "aria-selected": tab === k ? "true" : "false", onclick: () => setTab(k) }, label, n ? h("span", { class: "bp-count" }, n) : null))),
      body);
  }

  function questionsPane() {
    const pad = h("div", { class: "bp-pad" }, h("div", { class: "bp-empty" }, h("span", { class: "bp-spin" })));
    if (!state.map.facts.project) {
      pad.replaceChildren(h("div", { class: "bp-empty" }, h("b", {}, "Вопросы появятся с картой"), "Вопросы истории — в её разделе «Вопросы»."));
      return pad;
    }
    api("questions", { epic: state.map.epic }).then(({ questions }) => {
      const list = questions.filter((q) => state.qFilter === "all" || q.open);
      const filter = h("div", { class: "bp-filter" },
        [["open", `Открытые · ${questions.filter((q) => q.open).length}`], ["all", `Все · ${questions.length}`]].map(([k, l]) =>
          h("button", { class: "ds-btn ds-btn--sm" + (state.qFilter === k ? " ds-btn--primary" : ""), onclick: () => { state.qFilter = k; renderMap(); } }, l)));
      pad.replaceChildren(filter, ...(list.length ? list.map(questionRow) : [h("div", { class: "bp-empty" }, "Открытых вопросов нет")]));
    }).catch((e) => pad.replaceChildren(h("div", { class: "bp-empty" }, e.message)));
    return pad;
  }

  function questionRow(q) {
    const input = h("input", { class: "ds-input", placeholder: "Ответ (со слов адресата)", "aria-label": "Ответ на " + q.id });
    const save = async () => {
      if (!input.value.trim()) return;
      const r = await guarded(() => api("answer", null, { epic: state.map.epic, id: q.id, answer: input.value })).catch(() => null);
      if (r) { toast(`Ответ на ${q.id} записан — пересоберите карту`); state.open.add("map"); loadMap(true); }
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); });
    return h("div", { class: "bp-q" },
      h("div", { class: "bp-q__head" }, h("b", {}, q.id), chip(q.kind || "вопрос", /блок/.test(q.kind) ? "danger" : ""),
        h("span", {}, "кому: " + (q.to || "—")), q.where ? h("span", {}, "где: " + q.where) : null),
      h("div", {}, q.text),
      q.open ? h("div", { class: "bp-q__form" }, input, h("button", { class: "ds-btn ds-btn--sm", onclick: save }, "Записать"))
        : h("div", { class: "bp-q__ans" }, "✓ " + q.answer));
  }

  function jobsPane() {
    const jobs = state.jobs;
    if (!jobs.length) return h("div", { class: "bp-pad" }, h("div", { class: "bp-empty" }, h("b", {}, "Ходов агента ещё не было"),
      state.config?.agent ? "Нажмите «Запустить агента» у этапа." : "Фоновый агент сервиса не настроен: команды этапов выполняются в вашем чате или через MCP."));
    const pad = h("div", { class: "bp-pad" });
    for (const j of jobs) {
      const log = h("pre", { class: "bp-out", hidden: true });
      const toggle = async () => {
        if (!log.hidden) { log.hidden = true; return; }
        const r = await guarded(() => api("job", { id: j.id }));
        if (r) { log.textContent = r.job.log || "(журнал пуст)"; log.hidden = false; log.scrollTop = log.scrollHeight; }
      };
      const tone = { running: "accent", done: "success", failed: "danger", stopped: "", interrupted: "warning" }[j.state] || "";
      pad.append(h("div", { class: "bp-job" },
        h("div", { class: "bp-q__head" }, chip(j.state, tone), h("b", {}, stageTitle(j.stage)), h("span", {}, fmtDate(j.started)),
          j.finished ? h("span", {}, "→ " + fmtDate(j.finished)) : null),
        h("code", { class: "ds-muted", style: "display:block;margin:6px 0;white-space:pre-wrap" }, j.prompt),
        h("div", { class: "bp-actions" }, h("button", { class: "ds-btn ds-btn--sm", onclick: toggle }, "Журнал"),
          j.state === "running" ? h("button", { class: "ds-btn ds-btn--sm", onclick: async () => {
            if (confirm("Остановить ход агента?")) { await guarded(() => api("stop", null, { id: j.id })).catch(() => null); loadMap(true); }
          } }, "Остановить") : null),
        log));
    }
    return pad;
  }

  // ---------- листы ----------
  function openSheet(title, kids) {
    $("sheetTitle").textContent = title;
    $("sheetBody").replaceChildren(...[kids].flat(Infinity).filter(Boolean));
    $("sheet").hidden = false; $("scrim").hidden = false;
  }
  function closeSheet() { $("sheet").hidden = true; $("scrim").hidden = true; }

  async function showFile(a) {
    const what = a.path.endsWith("-story.md") ? "story" : null;
    openSheet(a.label, h("div", { class: "bp-empty" }, h("span", { class: "bp-spin" })));
    const m = state.map, f = m.facts;
    let w = what;
    if (!w && a.path === f.bft_path) w = "bft";
    if (!w) {
      const doc = Object.entries(f.project?.docs || {}).find(([, d]) => d.file === a.path);
      w = doc ? "doc:" + doc[0] : null;
    }
    if (!w) { openSheet(a.label, h("code", {}, a.path)); return; }
    const r = await guarded(() => api("file", { epic: m.epic, what: w })).catch(() => null);
    if (r) openSheet(a.label, [h("code", { class: "ds-muted" }, r.path), h("div", { class: "bp-md" }, r.markdown)]);
  }

  function showMcp() {
    const url = new URL(state.config?.mcp_url || BASE + "/mcp", location.origin).href;
    const claude = `claude mcp add --transport http blueprint ${url} --header "Authorization: Bearer <токен>"`;
    const local = `claude mcp add blueprint -- python3 <путь>/poh-blueprint-writer/service/server.py mcp`;
    openSheet("Управление через MCP", [
      h("p", {}, "«Система Blueprint» — те же диаграммы для любого ИИ-агента: список, этапы, чтение артефактов, запись истории, плана карты, документов этапов и контрактов с проверкой, сборка и вопросы."),
      h("div", { class: "ds-label" }, "Удалённо — Streamable HTTP"), cmdRow(claude),
      h("p", { class: "ds-muted" }, "Токен — строка в файле mcp_tokens_file сервиса (выдаёт владелец сервера)."),
      h("div", { class: "ds-label" }, "На той же машине — stdio"), cmdRow(local),
      h("div", { class: "ds-label" }, "Инструменты"),
      h("ul", { class: "bp-missing" }, ["blueprint_list", "blueprint_get", "blueprint_guide", "blueprint_read", "blueprint_submit_story", "blueprint_submit_plan",
        "blueprint_submit_doc", "blueprint_submit_contract", "blueprint_run", "blueprint_questions", "blueprint_answer"].map((t) => h("li", {}, h("code", {}, t)))),
      h("p", { class: "ds-muted" }, "Промт blueprint_full_cycle ведёт агента от БФТ до отгруженной карты."),
    ]);
  }

  route();
})();

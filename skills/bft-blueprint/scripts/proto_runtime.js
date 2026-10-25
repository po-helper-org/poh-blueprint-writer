/* Прототип по контрактам — собран ./blueprint.py prototype build, руками не правь.
   Шаги истории по этапам, экраны «Истории», вызовы — по контрактам contracts/C-N.md.
   MockAPI: сервер api/main.py (docker compose up) или, если он недоступен, — те же ответы прямо в браузере. */
(function () {
  "use strict";
  const S = window.SPEC;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const KEY = "proto-review:" + (S.epic || S.title);
  const store = {
    get() { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } },
    set(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* замечания живут до перезагрузки */ } },
  };
  let pins = store.get();
  let app = "all", idx = 0, scr = 0, phase = "before", review = false, apiBase = null, lastCall = [];
  const scenario = {};   // шаг → "ok" | КОД ошибки
  const values = {};     // шаг → {поле: значение}

  // --- MockAPI: сервер или браузер -------------------------------------------------------------------
  async function probe() {
    const q = new URLSearchParams(location.search).get("api");
    const base = q || (location.protocol.startsWith("http") ? `${location.protocol}//${location.hostname}:8000` : null);
    if (base) {
      try {
        const r = await fetch(base + "/__contracts", { signal: AbortSignal.timeout(1500) });
        if (r.ok) apiBase = base;
      } catch (e) { apiBase = null; }
    }
    const b = $("api");
    b.textContent = apiBase ? "MockAPI: сервер" : "MockAPI: в браузере";
    b.classList.toggle("live", !!apiBase);
    b.title = apiBase ? apiBase : "Сервер api не отвечает — ответы по тем же контрактам считаются в браузере";
  }

  function request(c, vals) {
    const [method, path0] = c.op.split(/\s+/, 2);
    let path = path0;
    const query = {}, body = {};
    for (const r of c.request) {
      const name = (r["Поле"] || "").replace(/`/g, "").trim();
      if (!(name in vals)) continue;
      const v = typed(vals[name], r["Тип"]);
      if (r["Где"] === "path") path = path.replace("{" + name + "}", encodeURIComponent(vals[name]));
      else if (r["Где"] === "query" || method === "GET") query[name] = vals[name];
      else body[name] = v;
    }
    const qs = Object.keys(query).length ? "?" + new URLSearchParams(query) : "";
    return { method, path: path + qs, body: method === "GET" ? null : body };
  }

  function typed(v, t) {
    if (t === "integer" || t === "number") { const n = Number(v); return isNaN(n) ? v : n; }
    if (t === "boolean") return v === "true" || v === "да";
    if (t === "array" || t === "object") { try { return JSON.parse(v); } catch (e) { return v; } }
    return v;
  }

  function mock(c, req, code) {
    if (code && code !== "ok") {
      const e = c.errors.find((x) => (x["Код"] || "").replace(/`/g, "") === code);
      return { status: Number(e ? e["Статус"] : 400), json: { code, message: e ? e["Когда"] : "" } };
    }
    const miss = c.request.filter((r) => r["Обяз."] === "да").map((r) => (r["Поле"] || "").replace(/`/g, "").trim())
      .filter((n) => !(n in (values[cur().id] || {})) || values[cur().id][n] === "");
    if (miss.length) return { status: 422, json: { code: "CONTRACT_FIELDS_MISSING", message: "нет обязательных полей контракта", fields: miss } };
    return { status: 200, json: c.example || {} };
  }

  async function call(c, vals, code) {
    const req = request(c, vals);
    if (apiBase) {
      try {
        const h = { "Content-Type": "application/json" };
        if (code && code !== "ok") h["X-Mock-Error"] = code;
        const r = await fetch(apiBase + req.path, { method: req.method, headers: h, body: req.body ? JSON.stringify(req.body) : undefined });
        return { req, status: r.status, json: await r.json().catch(() => ({})), via: "сервер" };
      } catch (e) { /* сервер пропал — браузер */ }
    }
    const m = mock(c, req, code);
    return { req, status: m.status, json: m.json, via: "браузер" };
  }

  // --- шаги ------------------------------------------------------------------------------------------
  const list = () => S.steps.filter((s) => app === "all" || s.app === app);
  const cur = () => list()[idx] || list()[0];
  const contract = (id) => S.contracts[id];

  function renderApps() {
    const used = new Set(S.steps.map((s) => s.app));
    const opts = [["all", "Весь путь"]].concat(Object.entries(S.apps).filter(([k]) => used.has(k)));
    $("apps").innerHTML = opts.map(([k, v]) => `<button data-app="${k}" class="${k === app ? "on" : ""}">${esc(cap(v))}</button>`).join("");
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  function renderSteps() {
    let stage = null, html = "";
    list().forEach((s, i) => {
      const st = s.stage ? `${s.stage} · ${s.stageName}` : "Внешняя сторона";
      if (st !== stage) { html += `<h3>${esc(st)}</h3>`; stage = st; }
      const tags = (s.calls.length ? `<span class="tag api">${s.calls.join(", ")}</span>` : "") + `<span class="tag">${esc(S.apps[s.app] || s.app)}</span>`;
      html += `<button data-i="${i}" class="${i === idx ? "on" : ""}">${esc(s.id)} · ${esc(s.title)}${tags}<small>${esc(s.persona)}</small></button>`;
    });
    $("steps").innerHTML = html || `<p class="muted">Шагов этого приложения нет</p>`;
  }

  function screenIds(s) {
    if (!s.calls.length) return s.screens;
    if (phase === "ok") return [s.ok || s.screens[s.screens.length - 1]].filter(Boolean);
    if (phase === "fail") return [s.fail.screen || s.screens[s.screens.length - 1]].filter(Boolean);
    return s.screens;
  }

  function el(e, s) {
    const [k, a, b, c] = e;
    const lab = (t) => ` data-block="${esc(t)}"`;
    switch (k) {
      case "hdr": return `<div class="el hdr"${lab(a)}>${esc(a)}</div>`;
      case "text": return `<div class="el text"${lab(a)}>${esc(a)}</div>`;
      case "offer": return `<div class="el offer"${lab(a)}>${esc(a)}</div>`;
      case "cta": return `<div class="el cta"${lab(a)}><button data-act="call">${esc(a)}</button></div>`;
      case "cta2": return `<div class="el cta2"${lab(a)}><button>${esc(a)}</button></div>`;
      case "link": return `<div class="el link"${lab(a)}><a href="#" onclick="return false">${esc(a)}</a></div>`;
      case "tiles": return `<div class="el tiles"${lab("плитки")}><div></div><div></div></div>`;
      case "rows": case "rowsOffer":
        return `<div class="el"${lab("список")}>` + Array.from({ length: a }, () => `<div class="row"><div class="pic"></div><div class="lines"><i></i><i></i></div>${k === "rowsOffer" ? '<span class="badge">−10%</span>' : ""}</div>`).join("") + "</div>";
      case "chips": return `<div class="el chips"${lab("фильтры")}>${a.map((x) => `<span>${esc(x)}</span>`).join("")}</div>`;
      case "kv": return `<div class="el kv"${lab(a)}><span>${esc(a)}</span><span>${esc(b)}</span></div>`;
      case "img": return `<div class="el img"${lab("картинка")}></div>`;
      case "camera": return `<div class="el camera"${lab("камера")}></div>`;
      case "ok": return `<div class="el ok"${lab(a)}>${esc(a)}</div>`;
      case "no": return `<div class="el no"${lab(a)}>${esc(a)}</div>`;
      case "notif": return `<div class="el notif"${lab(b)}><b>${esc(a)}</b><div><strong>${esc(b)}</strong></div><div>${esc(c)}</div></div>`;
      case "barcode": return `<div class="el barcode"${lab("штрихкод")}></div>`;
      case "from": return `<div class="el from"${lab(a)}>От: ${esc(a)}</div>`;
      default: return "";
    }
  }

  function form(s) {
    const v = values[s.id] || (values[s.id] = Object.assign({}, s.inputs));
    const keys = Object.keys(v);
    if (!keys.length) return "";
    const types = {};
    s.calls.forEach((id) => (contract(id) || { request: [] }).request.forEach((r) => (types[(r["Поле"] || "").replace(/`/g, "")] = r["Тип"])));
    return `<div class="form" data-block="данные запроса">` + keys.map((k) =>
      `<label>${esc(k)} <span class="muted">${esc(types[k] || "")}</span></label><input data-field="${esc(k)}" value="${esc(v[k])}">`).join("") + "</div>";
  }

  function pick(obj, path) {
    return path.split(".").reduce((o, k) => (o == null ? o : Array.isArray(o) ? (o[0] || {})[k] : o[k]), obj);
  }

  function result(s) {
    if (!lastCall.length || phase === "before") return "";
    const r = lastCall[lastCall.length - 1];
    if (phase === "fail" || r.status >= 400) {
      return `<div class="result fail" data-block="ответ: ошибка"><div><b>${r.status} ${esc(r.json.code || "")}</b></div><div>${esc(r.json.message || "")}</div></div>`;
    }
    const all = Object.assign({}, ...lastCall.map((x) => x.json));
    const rows = (s.show.length ? s.show : Object.keys(all)).map((f) => {
      const v = pick(all, f);
      return `<div><code>${esc(f)}</code><b>${esc(typeof v === "object" ? JSON.stringify(v) : v)}</b></div>`;
    });
    return `<div class="result" data-block="ответ">${rows.join("")}</div>`;
  }

  function renderScreen() {
    const s = cur();
    if (!s) { $("device").innerHTML = ""; return; }
    const ids = screenIds(s);
    const id = ids[Math.min(scr, ids.length - 1)];
    const sc = S.screens[id];
    const d = $("device");
    const dev = sc ? sc.device : "empty";
    d.className = "device " + dev;
    let html = sc ? `<div class="contour">${esc(sc.contour)}</div><div class="state">${esc(id)}${sc.view !== "основной" ? " · " + esc(sc.view) : ""}</div>` : "";
    const els = sc ? sc.elements : [];
    const ctaAt = els.findIndex((e) => e[0] === "cta");
    els.forEach((e, i) => {
      if (phase === "before" && s.calls.length && i === (ctaAt < 0 ? els.length : ctaAt)) html += form(s);
      html += el(e, s);
    });
    if (phase === "before" && s.calls.length && ctaAt < 0) html += form(s) + `<div class="el cta"><button data-act="call">Отправить запрос</button></div>`;
    const who = s.app === "external" ? "Внешняя система" : s.app === "backend" ? "За кадром" : (s.persona || "");
    const why = !s.calls.length ? "шаг происходит без экрана" : s.app === "external" ? "внешняя сторона вызывает наш сервис"
      : s.app === "backend" ? "наши системы обмениваются данными — человек увидит результат на следующем шаге" : "вызов идёт за кадром, экран результата — после ответа";
    const c0 = s.calls.length ? contract(s.calls[0]) : null;
    if (!sc) html += `<p><b>${esc(who)}</b>${c0 ? `<br><span class="muted">${esc(c0.caller)} → ${esc(c0.callee)}</span>` : ""}</p><p class="muted">Экрана нет: ${why}.</p>` +
      (phase === "before" ? form(s) + (s.calls.length ? `<div class="el cta"><button data-act="call">Отправить запрос</button></div>` : "") : "");
    html += result(s);
    d.innerHTML = html;
    d.dataset.screen = id || "";
    drawPins();
    $("stepHead").innerHTML = `<h2>${esc(s.id)} · ${esc(s.title)}</h2><p>${esc(s.text)}</p>` +
      (s.was && s.was !== "—" ? `<p class="muted">Раньше: ${esc(s.was)}</p>` : "") + (s.note ? `<p class="note">${esc(s.note)}</p>` : "");
    const total = list().length;
    $("pos").textContent = `шаг ${idx + 1} из ${total}` + (ids.length > 1 ? ` · экран ${Math.min(scr, ids.length - 1) + 1} из ${ids.length}` : "");
    $("prev").disabled = idx === 0 && scr === 0 && phase === "before";
    $("next").textContent = s.calls.length && phase === "before" && scr >= ids.length - 1 ? "Вызвать →" : "Далее →";
  }

  // --- «Как это работает» ----------------------------------------------------------------------------
  // Sequence — свой SVG: колонка на участника, строка на сообщение; вызов — сплошная стрелка, ответ — пунктир
  function seqSvg(c) {
    const parts = [];
    c.sequence.forEach((x) => [x.from, x.to].forEach((n) => { if (!parts.includes(n)) parts.push(n); }));
    const col = 128, top = 44, row = 34, W = Math.max(parts.length * col, 300), H = top + c.sequence.length * row + 50;
    const cx = (n) => col / 2 + parts.indexOf(n) * col;
    const lines = (t, max) => { const w = t.split(/\s+/), out = [""]; w.forEach((x) => { if ((out[out.length - 1] + " " + x).trim().length > max) out.push(x); else out[out.length - 1] = (out[out.length - 1] + " " + x).trim(); }); return out.slice(0, 2); };
    let g = `<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>`;
    parts.forEach((n) => {
      const x = cx(n);
      g += `<line x1="${x}" y1="${top}" x2="${x}" y2="${H - 30}" class="life"/>`;
      [[4, top - 4], [H - 34, H - 4]].forEach(([y1]) => {
        g += `<rect x="${x - col / 2 + 6}" y="${y1}" width="${col - 12}" height="32" rx="6" class="actor"/>` +
          lines(n, 15).map((t, i, a) => `<text x="${x}" y="${y1 + 16 + (i - (a.length - 1) / 2) * 12 + 4}" class="an">${esc(t)}</text>`).join("");
      });
    });
    c.sequence.forEach((m, i) => {
      const y = top + 26 + i * row, x1 = cx(m.from), x2 = cx(m.to);
      if (x1 === x2) {
        g += `<path d="M${x1},${y - 8} h26 v12 h-24" class="msg" marker-end="url(#ah)"/><text x="${x1 + 30}" y="${y - 2}" class="ml" text-anchor="start">${esc(m.msg)}</text>`;
        return;
      }
      g += `<line x1="${x1}" y1="${y}" x2="${x2 + (x2 > x1 ? -2 : 2)}" y2="${y}" class="msg${m.arrow === "-->" ? " ret" : ""}" marker-end="url(#ah)"/>` +
        `<text x="${(x1 + x2) / 2}" y="${y - 6}" class="ml">${esc(m.msg.length > 40 ? m.msg.slice(0, 39) + "…" : m.msg)}</text>`;
    });
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" role="img" aria-label="Sequence ${esc(c.id)}">${g}</svg>`;
  }

  function table(rows, cols) {
    if (!rows.length) return "";
    return `<table><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>` +
      rows.map((r) => `<tr>${cols.map((c) => `<td class="${c === "Источник" ? "src" : ""}">${c === "Поле" ? `<code>${esc(r[c])}</code>` : esc(r[c])}</td>`).join("")}</tr>`).join("") + "</table>";
  }

  function renderPanel() {
    const s = cur();
    if (!s) { $("panel").innerHTML = ""; return; }
    let h = "";
    if (!s.calls.length) {
      h += `<h4>Как это работает</h4><p class="muted">На этом шаге нет вызова между системами: экран из «Истории» показывает итог для человека.</p>`;
      h += `<p class="muted">Источник: ${esc(s.source)}</p>`;
    }
    s.calls.forEach((id) => {
      const c = contract(id);
      if (!c) return;
      const sel = scenario[s.id] || "ok";
      h += `<div class="call"><h5>${esc(c.id)} · ${esc(c.title)}</h5>
        <div class="who">${esc(c.caller)} → ${esc(c.callee)} · ${esc(c.boundary)}</div>
        <div class="op"><b>${esc(c.op.split(" ")[0])}</b> ${esc(c.op.split(" ").slice(1).join(" "))}</div>
        ${c.sequence.length ? `<h4>Sequence</h4><div class="seq">${seqSvg(c)}</div>` : ""}
        <h4>Запрос</h4>${table(c.request, ["Поле", "Тип", "Обяз.", "Где", "Источник"]) || '<p class="muted">без полей</p>'}
        <h4>Ответ</h4>${table(c.response, ["Поле", "Тип", "Источник"])}
        <h4>Сценарий показа</h4><div class="chips2">` +
        [["ok", "успех 200"]].concat(c.errors.map((e) => [(e["Код"] || "").replace(/`/g, ""), `${e["Статус"]} ${(e["Код"] || "").replace(/`/g, "")}`]))
          .map(([v, t]) => `<label title="${esc((c.errors.find((e) => (e["Код"] || "").replace(/`/g, "") === v) || {})["Когда"] || "пример ответа контракта")}"><input type="radio" name="sc-${esc(s.id)}" value="${esc(v)}" ${sel === v ? "checked" : ""}><span>${esc(t)}</span></label>`).join("") +
        `</div>${c.errors.length ? table(c.errors, ["Статус", "Код", "Когда"]) : ""}
        ${c.chain.length ? `<h4>За кадром — цепочка</h4>${table(c.chain, ["Шаг", "Кто", "Вход", "Что делает", "Выход"])}` : ""}</div>`;
    });
    s.data.forEach((id) => {
      const c = contract(id);
      if (c) h += `<div class="call"><h5>${esc(c.id)} · ${esc(c.title)}</h5><div class="who">${esc(c.caller)} → ${esc(c.callee)} · данные</div>${table(c.data, ["Хранилище", "Какие данные нужны", "Источник"])}</div>`;
    });
    if (lastCall.length && phase !== "before") {
      h += `<h4>Запрос и ответ · ${esc(lastCall[0].via)}</h4>` + lastCall.map((r) =>
        `<pre class="log">${esc(r.req.method + " " + r.req.path)}${r.req.body ? "\n" + esc(JSON.stringify(r.req.body, null, 1)) : ""}\n\n→ ${r.status}\n${esc(JSON.stringify(r.json, null, 1))}</pre>`).join("");
    }
    const mine = pins.filter((p) => p.step === s.id);
    if (mine.length) h += `<h4>Замечания шага</h4><div class="pinlist">` + mine.map((p) => `<div><b>${pins.indexOf(p) + 1}</b> ${esc(p.screen || "")} · ${esc(p.text)}</div>`).join("") + "</div>";
    $("panel").innerHTML = h;
  }

  function render() { renderApps(); renderSteps(); renderScreen(); renderPanel(); $("pins").textContent = pins.length; }

  // --- действия ----------------------------------------------------------------------------------------
  async function doCall() {
    const s = cur();
    document.querySelectorAll("#device [data-field]").forEach((i) => (values[s.id][i.dataset.field] = i.value));
    lastCall = [];
    const code = scenario[s.id] || "ok";
    for (const id of s.calls) {
      const c = contract(id);
      if (!c) continue;
      const has = c.errors.some((e) => (e["Код"] || "").replace(/`/g, "") === code);
      const r = await call(c, values[s.id] || {}, has ? code : "ok");   // ошибка — у того вызова, в чьих «Ошибках» она есть
      lastCall.push(r);
      if (r.status >= 400) break;
    }
    phase = lastCall.some((r) => r.status >= 400) ? "fail" : "ok";
    scr = 0;
    renderScreen(); renderPanel();
  }

  function go(i) { idx = Math.max(0, Math.min(list().length - 1, i)); scr = 0; phase = "before"; lastCall = []; render(); }

  function next() {
    const s = cur();
    const ids = screenIds(s);
    if (scr < ids.length - 1) { scr++; renderScreen(); return; }
    if (s.calls.length && phase === "before") { doCall(); return; }
    if (idx < list().length - 1) go(idx + 1);
  }

  function prev() {
    if (scr > 0) { scr--; renderScreen(); return; }
    if (phase !== "before") { phase = "before"; lastCall = []; renderScreen(); renderPanel(); return; }
    if (idx > 0) go(idx - 1);
  }

  // --- замечания ---------------------------------------------------------------------------------------
  function drawPins() {
    const s = cur(), d = $("device");
    pins.forEach((p, i) => {
      if (p.step !== s.id || p.screen !== (d.dataset.screen || "")) return;
      const m = document.createElement("div");
      m.className = "pin"; m.textContent = i + 1; m.title = p.text;
      m.style.left = p.x + "%"; m.style.top = p.y + "%";
      d.appendChild(m);
    });
  }

  let draft = null;
  function onDeviceClick(ev) {
    if (!review) {
      const b = ev.target.closest("[data-act=call]");
      if (b) { ev.preventDefault(); doCall(); }
      return;
    }
    if (ev.target.closest("input")) return;
    ev.preventDefault();
    const d = $("device"), r = d.getBoundingClientRect();
    const blk = ev.target.closest("[data-block]");
    draft = { step: cur().id, screen: d.dataset.screen || "", block: blk ? blk.dataset.block : "",
      x: Math.round((ev.clientX - r.left) / r.width * 1000) / 10, y: Math.round((ev.clientY - r.top) / r.height * 1000) / 10 };
    const pop = $("pop");
    pop.hidden = false;
    pop.style.left = Math.min(ev.clientX + 10, innerWidth - 300) + "px";
    pop.style.top = Math.min(ev.clientY + 10, innerHeight - 140) + "px";
    $("popText").value = ""; $("popText").focus();
  }

  function savePin() {
    const t = $("popText").value.trim();
    if (t && draft) { draft.text = t; draft.at = new Date().toISOString(); pins.push(draft); store.set(pins); }
    draft = null; $("pop").hidden = true; render();
  }

  function download(name, text, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }

  function exportPins() {
    const data = { title: S.title, epic: S.epic, pins };
    download("review.json", JSON.stringify(data, null, 1), "application/json");
    const md = [`# Замечания к прототипу «${S.title}»`, ""].concat(pins.map((p, i) =>
      `${i + 1}. **${p.step}**${p.screen ? " · экран " + p.screen : ""}${p.block ? " · «" + p.block + "»" : ""} — ${p.text}`));
    download("review.md", md.join("\n") + "\n", "text/markdown");
  }

  // --- запуск ------------------------------------------------------------------------------------------
  $("title").textContent = S.title;
  $("apps").addEventListener("click", (e) => { const b = e.target.closest("[data-app]"); if (b) { app = b.dataset.app; go(0); } });
  $("steps").addEventListener("click", (e) => { const b = e.target.closest("[data-i]"); if (b) go(Number(b.dataset.i)); });
  $("device").addEventListener("click", onDeviceClick);
  $("panel").addEventListener("change", (e) => {
    if (e.target.name && e.target.name.startsWith("sc-")) { scenario[cur().id] = e.target.value; phase = "before"; lastCall = []; renderScreen(); }
  });
  $("next").addEventListener("click", next);
  $("prev").addEventListener("click", prev);
  $("review").addEventListener("click", () => { review = !review; $("review").setAttribute("aria-pressed", review); document.body.classList.toggle("review", review); });
  $("export").addEventListener("click", exportPins);
  $("popSave").addEventListener("click", savePin);
  $("popCancel").addEventListener("click", () => { draft = null; $("pop").hidden = true; });
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea")) return;
    if (e.key === "ArrowRight") next();
    if (e.key === "ArrowLeft") prev();
  });
  render();
  probe();
})();

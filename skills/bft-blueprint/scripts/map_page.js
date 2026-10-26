/* bft-blueprint · карта инициативы. Данные — #map-data (собирает bft-backlog-build.py из проекта Backlog.md).
   Три слоя чтения: «Что видят» (история), «Что делаем» (задачи команд), «Как это работает»
   (Employee Actions, Technology, Backstage, Support). Подробности — по клику, в боковой панели. */
(function () {
  "use strict";
  const D = JSON.parse(document.getElementById("map-data").textContent);
  const { esc, chip } = BPK;
  /* слой «Архитектура»: данные ADR и системных требований — объявлены до первого
     использования (mstack ниже читает AR/SR при загрузке, экран — по клику) */
  const AR = D.adr || null, SR = D.sysreq || null;
  let arCur = "adr"; /* активная вкладка слоя «Архитектура» — тоже до первого использования */
  /* файлы проекта — от страницы: страница лежит в папке проекта (blueprint.html) или рядом с ней */
  const B = D.base || "", fileURL = p => /^(https?:|data:)/.test(p) ? p : B + p.split("/").map(encodeURIComponent).join("/");
  const body = document.body, grid = document.getElementById("grid");
  const MARK = "[УТОЧНИТЬ";
  const U = t => String(t || "").includes(MARK);

  /* ---------- справочники ---------- */
  const COLS = [...D.stages, { id: "стало", name: "Итог", when: "" }];
  const colOf = st => COLS.findIndex(c => c.id === st);
  const TEAM = {}; D.teams.forEach((t, i) => TEAM[t.id] = { name: t.name, c: `var(--t${i % 10})` });
  const teamC = t => t.team === "?" || !TEAM[t.team] ? "var(--red)" : TEAM[t.team].c;
  const teamN = t => t.team === "?" || !TEAM[t.team] ? "Команда?" : TEAM[t.team].name;
  const TASK = {}; D.tasks.forEach(t => TASK[t.id] = t);
  const PROC = {}; D.cards.forEach(p => PROC[p.id] = p);
  /* эпик (БФТ) → история (задача «Что делаем») → подзадачи по зонам; история в одном контуре — без подзадач */
  const ZONES = ["PO", "BA", "SA", "ADR", "Design", "BE", "DBA", "FE", "DevOps", "QA", "Delivery"];
  /* постановка подзадачи — в формате зоны; чеклист называется по смыслу зоны */
  const ZONE_SECS = { Design: ["UserStory", "JobStory", "UserFlow"], BE: ["ASIS", "GAP", "TOBE", "Данные"], DBA: ["ASIS", "GAP", "TOBE"], FE: ["ASIS", "GAP", "TOBE"], DevOps: ["ASIS", "GAP", "TOBE"] };
  const ZONE_CHECK = { PO: "Согласования", BA: "Вопросы по бизнес-логике", SA: "Вопросы по системной реализации", ADR: "Решения", Design: "На экране" };
  const SUBS = D.subs || [], SUB = {}; SUBS.forEach(z => SUB[z.id] = z);
  const subsOf = id => SUBS.filter(z => z.task === id).sort((a, b) => ZONES.indexOf(a.zone) - ZONES.indexOf(b.zone));
  /* MoSCoW: Must и Should — коммитмент заказчику, Would — за линией Out of scope */
  const PRIO = { must: "Must", should: "Should", would: "Would" }, PRIO_ORD = { must: 0, should: 1, "": 2, would: 3 };
  const oos = t => t && t.prio === "would";
  const byPrio = list => list.slice().sort((a, b) => PRIO_ORD[a.prio || ""] - PRIO_ORD[b.prio || ""]);
  const leadOf = t => t.team in TEAM && (D.teams.find(x => x.id === t.team) || {}).lead || "";
  const qOf = where => D.questions.filter(q => q.where === where && q.open);
  /* вопросы карты («Карта») и истории («История») — одним списком; ответ PO уходит в промпт агенту */
  const QS = [...D.questions.map(q => ({ ...q, key: "map:" + q.id, doc: "map" })), ...D.storyQuestions.map(q => ({ ...q, kind: "вопрос", key: "story:" + q.id, doc: "story" }))];
  const QK = {}; QS.forEach(q => QK[q.key] = q);
  const qsOf = ids => QS.filter(q => ids.includes(q.where));
  const asks = id => qOf(id).filter(q => q.kind === "вопрос").length;
  const blocks = id => qOf(id).filter(q => q.kind === "блокер");
  const scrOpen = id => D.storyQuestions.some(q => q.where === id);
  /* слои Service Blueprint: на виду у гостя — сотрудник и технологии; за линией видимости — Backstage; ниже — Support */
  const LAYER = { employee: ["Employee Actions", "действия сотрудника", "#a8541a"], technology: ["Technology", "что видит гость", "#0f8b8d"], backstage: ["Backstage", "за кадром", "#2563c9"], support: ["Support", "основа", "#6b5fb0"] };
  const PERSONA_ICON = ['<circle cx="8" cy="5.5" r="2.6"/><path d="M3 14c.6-3 2.6-4.5 5-4.5s4.4 1.5 5 4.5"/>', '<path d="M4 2v5a2 2 0 0 0 2 2v5M6 2v4M8 2v5a2 2 0 0 1-2 2M12 14V2c-1.5 1-2.5 3-2.5 5.5H12"/>'];
  const who = p => `<span class="who"><svg viewBox="0 0 16 16">${PERSONA_ICON[Math.min(1, D.personas.findIndex(x => x.id === p.id))]}</svg>${esc(p.name)}</span>`;
  /* экран — картинка из backlog/assets/screens: упрощённый SVG из «Истории» или свой макет */
  const screenImg = id => fileURL(D.screens[id].img);
  const scrPic = id => `<img src="${esc(screenImg(id))}" alt="${esc(D.screens[id].contour)}" loading="lazy" draggable="false">`;
  const mock = (id, w) => `<span class="scrw" style="position:relative;display:block${w ? `;width:${w}px` : ""}">${scrOpen(id) ? '<span class="dot" style="top:-4px;right:-5px"></span>' : ""}${scrPic(id)}</span>`;

  /* ---------- шапка ---------- */
  const uniqBlk = [...new Set(D.questions.filter(q => q.open && q.kind === "блокер").map(q => q.text))];
  document.getElementById("blk").innerHTML = uniqBlk.length ? `<button class="mi blk" data-guide="blk"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M3.5 12.5l9-9"/></svg>Блокеры<b class="cnt">${uniqBlk.length}</b></button>` : "";
  const used = {}; [...D.tasks, ...SUBS].forEach(t => used[t.team] = (used[t.team] || 0) + 1);
  const nTasks = n => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "задача" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "задачи" : "задач"}`;
  document.getElementById("teams").innerHTML = D.teams.filter(t => used[t.id]).map(t => `<button class="tchip" data-tf="${t.id}" style="--c:${TEAM[t.id].c}"><i></i>${esc(t.name)}<b>${nTasks(used[t.id])}</b></button>`).join("") +
    (used["?"] ? `<button class="tchip" data-tf="?" style="--c:var(--red)"><i class="u"></i>Команда не определена<b>${nTasks(used["?"])}</b></button>` : "");
  if (uniqBlk.length) document.getElementById("bdot").textContent = uniqBlk.length;
  /* стыки: кнопка меню видна, только если в проекте есть документ «Стыки» */
  if (D.seams && D.seams.items && D.seams.items.length) {
    const sb = document.querySelector("[data-seamspanel]"), sc = document.getElementById("seamcnt");
    sb.hidden = false; sc.hidden = false; sc.textContent = D.seams.items.length;
  }

  /* ---------- меню: всё, что раньше было в шапке, — поверх карты ---------- */
  const burger = document.getElementById("burger");
  const menu = open => { body.classList.toggle("mopen", open); burger.setAttribute("aria-expanded", open); if (open) document.querySelector("#menu .play").focus() };
  /* фильтр по команде: подсветить её работу, на кнопке меню — чип с крестиком */
  function teamFilter(id) {
    document.querySelectorAll(".tchip").forEach(x => x.classList.toggle("on", x.dataset.tf === id));
    document.querySelectorAll(".ui-story,.hw,.ui-card[data-sub]").forEach(x => x.classList.toggle("dim", !!id && !(x.dataset.teams || x.dataset.team).split(" ").includes(id)));
    const t = id && (id === "?" ? { name: "Команда не определена", c: "var(--red)" } : TEAM[id]);
    document.getElementById("fchip").innerHTML = t ? `<button class="fchip" data-tf-clear style="--c:${t.c}" aria-label="Снять фильтр"><i></i>${esc(t.name)}<span aria-hidden="true">×</span></button>` : "";
  }

  /* ---------- карточки ---------- */
  /* карточка «что видят» для ленты телефона: экран, персонаж, заголовок, две строки текста */
  const plural = (n, a, b, c) => n % 10 === 1 && n % 100 !== 11 ? a : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? b : c;
  function seenHTML(c) {
    return D.seen.filter(s => s.col === c).map(s => {
      const p = D.personas.find(x => x.id === s.persona), w = who(p);
      if (s.final) return `<div class="seen fin" data-seen="${s.key}" role="button" tabindex="0">${w}${s.big ? `<b class="big">${esc(s.big)}</b>` : ""}<b>${esc(s.title)}</b></div>`;
      const more = s.steps.length - 1;
      return `<div class="seen" data-seen="${s.key}" role="button" tabindex="0"><span class="th">${mock(s.steps[0].screens[0])}</span><div class="sx">${w}<b>${esc(s.steps[0].title)}</b><p>${esc(s.steps[0].text)}</p>${more ? `<span class="more">+${more} ${plural(more, "шаг", "шага", "шагов")}</span>` : ""}</div></div>`;
    }).join("");
  }
  /* компоненты слоя «Что делаем» — страница собирает их из данных Backlog.md, разметку не пишет никто:
     история — пунктирная группа (чип «История», название, приоритет, вопросы и блокер истории);
     работа — карточка (команда, зона, вопросы, блокер, название). Кроссфункциональная история —
     группа с карточками подзадач; история в одном контуре — группа со строкой команды. */
  const uiTeam = w => `<span class="ui-team${w.team === "?" ? " u" : ""}"><i style="--c:${teamC(w)}"></i>${esc(w.team === "?" && w.cand ? "Команда? " + w.cand : teamN(w))}</span>`;
  const uiTags = (id, zone, prio) => { const n = asks(id), b = blocks(id).length;
    return `<span class="ui-tags">${prio && prio !== "must" ? `<span class="ui-prio ${prio}">${PRIO[prio]}</span>` : ""}${zone ? `<span class="ui-zone">${esc(zone)}</span>` : ""}${n && !b ? `<span class="ui-q" title="Открытых вопросов: ${n}">${n}</span>` : ""}${b ? '<span class="ui-blk">Блокер</span>' : ""}</span>` };
  const uiCard = z => `<button class="ui-card${blocks(z.id).length ? " blk" : ""}" data-sub="${esc(z.id)}" data-team="${z.team}"><span class="ui-top">${uiTeam(z)}${uiTags(z.id, z.zone)}</span><span class="ui-title">${esc(z.text)}</span></button>`;
  function taskHTML(t) {
    const subs = subsOf(t.id), teams = [...new Set([t.team, ...subs.map(z => z.team)])].join(" ");
    const head = `<button class="ui-head" data-task="${t.id}"><span class="ui-chip">История</span><span class="ui-name">${esc(t.text)}</span>${subs.length ? uiTags(t.id, "", t.prio) : ""}</button>`;
    const body = subs.length ? subs.map(uiCard).join("")
      : `<button class="ui-card ui-own${blocks(t.id).length ? " blk" : ""}" data-task="${t.id}"><span class="ui-top">${uiTeam(t)}${uiTags(t.id, "", t.prio)}</span></button>`;
    return `<div class="ui-story${oos(t) ? " oos" : ""}" data-teams="${teams}">${head}${body}</div>`;
  }
  function procHTML(p) {
    const b = blocks(p.id).length + blocks(p.task).length;
    return `<button class="hw ${p.layer}${b ? " blk" : ""}${oos(TASK[p.task]) ? " oos" : ""}" data-proc="${p.id}" data-team="${p.team}" style="--c:${teamC(p)}"><span>${esc(p.text)}</span><i title="${esc(teamN(p))}"></i></button>`;
  }

  /* ---------- холст ---------- */
  grid.className = "map";
  grid.style.gridTemplateColumns = `96px repeat(${COLS.length}, minmax(272px, 1fr))`;
  grid.style.minWidth = `${96 + COLS.length * 284}px`;
  let h = `<div class="mh corner"></div>` + COLS.map((c, i) => `<div class="mh"><span class="n">${i === COLS.length - 1 ? "✓" : i + 1}</span><span class="hx"><b>${esc(c.name)}</b>${c.when ? `<small>${esc(c.when)}</small>` : ""}</span></div>`).join("");
  h += `<div class="ml do">Что делаем</div>` + COLS.map(col => `<div class="mc do">${byPrio(D.tasks.filter(t => t.stage === col.id && !oos(t))).map(taskHTML).join("")}</div>`).join("");
  /* линия Out of scope: под ней — истории Would, они к инициативе относятся, но коммитментом заказчику не обсуждались */
  if (D.tasks.some(oos)) h += `<div class="oosl do"></div><div class="ml do oosm">Out of scope<small>Would — не коммитмент заказчику</small></div>` +
    COLS.map(col => `<div class="mc do oosc">${D.tasks.filter(t => t.stage === col.id && oos(t)).map(taskHTML).join("")}</div>`).join("");
  /* все четыре ряда — даже пустой: «сотрудника на виду у гостя нет» — тоже ответ */
  /* User Actions — над слоями: точки входа клиента. Точка — страница, с которой персонаж начинает свой
     процесс на этапе: первый экран его шага и каждый переход в другой контур (письмо → витрина). Шаг на
     чужой поверхности (экран официанта, который видит гость) точкой не считается — это вход другого
     персонажа. Всё — из согласованной истории (шаги и таблица «Экраны»), без новых данных. */
  const ENTRY = COLS.map((_, c) => {
    const firsts = {};
    const per = D.seen.filter(s => s.col === c && !s.final).map(s => {
      const pts = []; let prev = null;
      s.steps.forEach(st => { const sid = st.screens[0]; if (!sid) return; const k = D.screens[sid].contour; if (prev === null || k !== prev) pts.push({ sid, contour: k, persona: s.persona, first: !pts.length }); prev = k });
      if (pts[0]) firsts[pts[0].contour] = s.persona;
      return pts;
    }).flat();
    const seenSid = new Set();
    return per.filter(e => (e.first || !(e.contour in firsts) || firsts[e.contour] === e.persona) && !seenSid.has(e.sid) && seenSid.add(e.sid));
  });
  const scrTitle = sid => { const d = Object.values(D.docs).find(x => x.screen === sid); return d ? d.title.replace(/^[^·]*·\s*/, "") : sid };
  const entryHTML = e => { const p = D.personas.find(x => x.id === e.persona) || { name: "" };
    return `<button class="ua" data-entry="${esc(e.sid)}" data-persona="${esc(e.persona)}" title="${esc(p.name)}: ${esc(scrTitle(e.sid))}"><i></i><span><b>${esc(e.sid)} · ${esc(scrTitle(e.sid))}</b><small>${esc(e.contour)} · ${esc(p.name.split(/[\s-]+/)[0])}</small></span></button>` };
  /* триггер — событие старта пути персонажа («Гость купил билет»): с него начинается чтение диаграммы */
  const trgHTML = tg => { const p = D.personas.find(x => x.id === tg.persona) || { name: tg.persona };
    return `<div class="uat" data-persona="${esc(tg.persona)}" title="Старт пути: ${esc(p.name)}"><i></i><span><em>Старт</em><b>${esc(tg.text)}</b><small>${esc(p.name.split(/[\s-]+/)[0])}</small></span></div>` };
  h += `<div class="ml hrow how l-user">User Actions<small>старт и точки входа клиента</small></div>` + COLS.map((col, c) => `<div class="mc how l-user">${(D.triggers || []).filter(tg => tg.stage === col.id).map(trgHTML).join("")}${ENTRY[c].map(entryHTML).join("")}</div>`).join("");
  Object.keys(LAYER).forEach(l => {
    h += `<div class="ml hrow how l-${l}">${LAYER[l][0]}<small>${LAYER[l][1]}</small></div>` + COLS.map(col => `<div class="mc how l-${l}">${D.cards.filter(p => p.layer === l && p.stage === col.id).map(procHTML).join("")}</div>`).join("");
  });
  grid.innerHTML = h;

  /* стрелки между карточками — из ссылок в «Параметрах»: вход от карточки, выход к карточке */
  function drawLinks() {
    grid.querySelector("svg.hwl")?.remove();
    if (body.dataset.view !== "how") return;
    const g = grid.getBoundingClientRect();
    const R = el => { const r = el.getBoundingClientRect(); return { l: r.left - g.left, r: r.right - g.left, t: r.top - g.top, b: r.bottom - g.top, cx: (r.left + r.right) / 2 - g.left, cy: (r.top + r.bottom) / 2 - g.top } };
    let s = `<svg class="hwl" width="${grid.scrollWidth}" height="${grid.scrollHeight}"><defs><marker id="mh" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="#8c877d"/></marker></defs>`;
    const path = pts => `<path d="M${pts.map(p => p.map(Math.round).join(",")).join(" L")}" fill="none" stroke="#8c877d" stroke-width="1.5" marker-end="url(#mh)"/>`;
    const seen = new Set();
    D.links.forEach(l => {
      if (!PROC[l.src] || !PROC[l.dst]) return;
      // на карте — только соседние шаги; полная цепочка живёт в карточке процесса
      if (Math.abs(colOf(PROC[l.src].stage) - colOf(PROC[l.dst].stage)) > 1) return;
      const key = [l.src, l.dst].sort().join(); if (seen.has(key)) return; seen.add(key);
      const ea = grid.querySelector(`[data-proc="${l.src}"]`), eb = grid.querySelector(`[data-proc="${l.dst}"]`); if (!ea || !eb) return;
      const A = R(ea), B = R(eb);
      if (Math.abs(A.cx - B.cx) < 40) s += B.t > A.b ? path([[A.cx, A.b], [A.cx, B.t]]) : path([[A.cx, A.t], [A.cx, B.b]]);
      else if (B.l > A.r) s += Math.abs(A.cy - B.cy) < 3 ? path([[A.r, A.cy], [B.l, B.cy]]) : path([[A.r, A.cy], [B.l - 12, A.cy], [B.l - 12, B.cy], [B.l, B.cy]]);
      else if (A.l > B.r) s += path([[A.l, A.cy], [B.r + 12, A.cy], [B.r + 12, B.cy], [B.r, B.cy]]);
    });
    grid.querySelectorAll(".uat").forEach(tg => {
      const dot = tg.parentElement.querySelector(`.ua[data-persona="${tg.dataset.persona}"]`); if (!dot) return;
      const A = R(tg.querySelector("i")), B = R(dot.querySelector("i"));
      s += Math.abs(A.cy - B.cy) < 4 ? path([[A.r, A.cy], [B.l, B.cy]]) : path([[A.cx, A.b], [A.cx, B.cy], [B.l, B.cy]]);
    });
    grid.querySelectorAll(".ua[data-entry]").forEach(dot => {
      const sid = dot.dataset.entry, key = Object.keys(D.docs).find(k => D.docs[k].screen === sid);
      const col = dot.closest(".mc"), idx = [...grid.children].indexOf(col) % (COLS.length + 1);
      const card = key && [...grid.querySelectorAll(".hw[data-proc]")].find(el => [...grid.children].indexOf(el.closest(".mc")) % (COLS.length + 1) === idx
        && PROC[el.dataset.proc].docs.some(d => String(d).toLowerCase().split(" ")[0] === key));
      if (!card) return;
      const A = R(dot.querySelector("i")), B = R(card);
      s += path([[A.cx, A.b], [A.cx, B.t]]);
    });
    grid.insertAdjacentHTML("beforeend", s + "</svg>");
  }
  window.addEventListener("load", drawLinks); window.addEventListener("resize", drawLinks);

  /* ---------- требования к экранам: документы «F3 · …» в backlog/docs/screens — вкладки и стек заметок ---------- */
  const IMG_MD = /^!\[(.*?)\]\((.+?)\)$/, SCR = {}, NOTE_OF = {};
  /* файл экрана: # заголовок, картинки до первой вкладки, ## вкладка, ### заметка, ниже — markdown */
  function parseNotes(text) {
    const doc = { title: "", images: [], tabs: [] }; let tab = null, note = null;
    text.split("\n").forEach(l => {
      let m;
      if (l.startsWith("### ")) { note = { title: l.slice(4).trim(), body: [] }; if (tab) tab.notes.push(note) }
      else if (l.startsWith("## ")) { tab = { name: l.slice(3).trim(), notes: [] }; doc.tabs.push(tab); note = null }
      else if (l.startsWith("# ")) doc.title = l.slice(2).trim();
      else if (note) note.body.push(l);
      else if (!tab && (m = l.trim().match(IMG_MD))) doc.images.push({ alt: m[1], src: m[2] });
    });
    doc.tabs.forEach(t => t.notes.forEach(n => n.md = n.body.join("\n").trim()));
    return doc;
  }
  const SCR_FILE = /assets\/screens\/([A-ZА-Я]\d{1,2})\.\w+$/;
  Object.keys(D.notes || {}).forEach(id => { SCR[id] = parseNotes(D.notes[id]); NOTE_OF[id] = id; SCR[id].images.forEach(im => { const m = im.src.match(SCR_FILE); if (m && !NOTE_OF[m[1]]) NOTE_OF[m[1]] = id }) });
  const imgSrc = s => fileURL(s);
  const mdInline = s => esc(s).replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>').replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/\[УТОЧНИТЬ у ([^\]]+)\]/g, '<mark>? $1</mark>');
  function mdHTML(text) {
    let k = -1;
    return text.split(/\n{2,}/).map(block => {
      const lines = block.split("\n"), im = block.trim().match(IMG_MD);
      if (im) { k++; return `<figure><img src="${esc(imgSrc(im[2]))}" alt="${esc(im[1])}" data-zoom="${k}"><figcaption>${esc(im[1])}</figcaption></figure>` }
      if (lines.every(l => /^\d+\.\s/.test(l))) return `<ol>${lines.map(l => `<li>${mdInline(l.replace(/^\d+\.\s+/, ""))}</li>`).join("")}</ol>`;
      if (lines.every(l => /^[-*] /.test(l))) return `<ul>${lines.map(l => `<li>${mdInline(l.slice(2))}</li>`).join("")}</ul>`;
      if (/^Источник:/.test(block)) return `<p class="snsrc">${mdInline(block)}</p>`;
      return `<p>${lines.map(mdInline).join("<br>")}</p>`;
    }).join("");
  }
  const notePreview = n => (n.md.split("\n").find(l => l.trim() && !IMG_MD.test(l.trim()) && !l.startsWith("Источник:")) || "").replace(/\*\*/g, "").replace(/\[УТОЧНИТЬ у ([^\]]+)\]/g, "? $1").replace(/^[-*] /, "");
  let snCur = null, snTab = 0, gallery = [];
  const snHead = (title, back) => head(title, "", back);
  function openScreen(id, tab) {
    snCur = NOTE_OF[id]; if (tab != null) snTab = tab; const d = SCR[snCur], t = d.tabs[snTab] || d.tabs[0];
    const sids = Object.keys(NOTE_OF).filter(s => NOTE_OF[s] === snCur); execPrep(sids);
    gallery = d.images.map(im => ({ alt: im.alt, src: imgSrc(im.src) }));
    side.innerHTML = snHead(d.title) + `<div class="snbody">${gallery.length ? `<div class="sngal${gallery.length > 1 ? " many" : ""}">${gallery.map((im, i) => `<img src="${esc(im.src)}" alt="${esc(im.alt)}" data-zoom="${i}">`).join("")}</div>` : ""}
      <nav class="snseg">${d.tabs.map((x, i) => `<button data-sntab="${i}"${x === t ? ' class="on"' : ""}>${esc(x.name)}</button>`).join("")}</nav>
      <ul class="snstack">${(t ? t.notes : []).map((n, i) => `<li data-snnote="${i}" tabindex="0"><b>${esc(n.title)}</b><span>${esc(notePreview(n))}</span>${n.md.includes(MARK) ? '<i class="q"></i>' : ""}</li>`).join("")}</ul>${execInline()}</div>`;
    body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "screen:" + snCur; side.dataset.note = "";
    execShow(sids, "screen:" + snCur);
  }
  function openNote(i) {
    const d = SCR[snCur], n = d.tabs[snTab].notes[i];
    gallery = n.md.split(/\n{2,}/).map(b => b.trim().match(IMG_MD)).filter(Boolean).map(m => ({ alt: m[1], src: imgSrc(m[2]) }));
    side.innerHTML = snHead(n.title, true) + `<div class="snbody"><div class="snmd">${mdHTML(n.md)}</div></div>`; side.scrollTop = 0;
    side.dataset.ctx = "screen:" + snCur; side.dataset.note = `${d.tabs[snTab].name} · заметка «${n.title}»`;
  }
  /* просмотр картинки: крупно, ‹ › если их несколько; Esc или клик мимо — закрыть */
  const LB = document.getElementById("lb"); let lbI = 0;
  function zoom(i) {
    lbI = (i + gallery.length) % gallery.length; const im = gallery[lbI], many = gallery.length > 1;
    LB.innerHTML = `<figure><img src="${esc(im.src)}" alt="${esc(im.alt)}"><figcaption>${esc(im.alt)}${many ? ` · ${lbI + 1} из ${gallery.length}` : ""}</figcaption></figure>${many ? '<button class="nv p" data-lb="-1" aria-label="Предыдущая">‹</button><button class="nv n" data-lb="1" aria-label="Следующая">›</button>' : ""}<button class="lx" aria-label="Закрыть">×</button>`;
    LB.hidden = false;
  }

  /* ---------- первый экран: «Что видят» раскадровкой, путь уходит вправо ----------
     Колонка — этап истории шириной во столько кадров, сколько шагов у самого занятого персонажа;
     ряд — персонаж; пустая клетка — персонаж на этапе не участвует. Кадр — экран картинкой
     и подпись; несколько экранов у шага — кадры листаются сами и стрелками. */
  const hero = document.getElementById("hero");
  (function buildHero() {
    const persons = D.personas.filter(p => D.seen.some(s => s.persona === p.id));
    const cell = (p, c) => D.seen.find(s => s.persona === p.id && s.col === c);
    const width = c => Math.max(1, ...persons.map(p => { const s = cell(p, c); return s ? s.steps.length : 0 }));
    const FW = 196, GAP = 18, PAD = 16;
    const frame = (s, st) => {
      const n = st.screens.length, q = st.screens.some(scrOpen) || D.storyQuestions.some(qq => qq.where === st.id);
      const pic = n ? `<span class="track">${st.screens.map(id => `<span class="sld">${scrPic(id)}</span>`).join("")}</span>
        ${n > 1 ? `<span class="sl prev" data-sl="-1" aria-hidden="true">‹</span><span class="sl next" data-sl="1" aria-hidden="true">›</span>` : ""}` : "";
      const dots = n > 1 ? `<span class="dots">${st.screens.map((_, i) => `<i data-dot="${i}"${i ? "" : ' class="on"'}></i>`).join("")}</span>` : "";
      const notes = st.screens.some(id => NOTE_OF[id]);
      return `<div class="fr" data-seen="${s.key}"${notes ? ` data-screens="${st.screens.join(",")}"` : ""} role="button" tabindex="0" title="${esc(st.text)}"><span class="pic" data-n="${n}" data-i="0">${pic}${q ? '<span class="dot"></span>' : ""}</span>${dots}<span class="cap">${esc(st.title)}</span></div>`;
    };
    let x = `<div class="hgrid" style="--p:${persons.length};grid-template-columns:var(--lw) ${COLS.map((_, c) => `${width(c) * FW + (width(c) - 1) * GAP + 2 * PAD}px`).join(" ")}">`;
    x += '<div class="hc0"></div>' + COLS.map((col, c) => `<div class="hh"><span class="hhs"><span class="n">${c === COLS.length - 1 ? "✓" : c + 1}</span><b>${esc(col.name)}</b>${col.when ? `<small>${esc(col.when)}</small>` : ""}</span></div>`).join("");
    persons.forEach((p, i) => {
      x += `<div class="hl"><svg viewBox="0 0 16 16" aria-hidden="true">${PERSONA_ICON[Math.min(1, i)]}</svg><b>${esc(p.name.split(/[\s-]+/)[0])}</b><small>${esc(p.name)}</small></div>`;
      COLS.forEach((_, c) => {
        const s = cell(p, c);
        if (!s) x += '<div class="hcell"></div>';
        else if (s.final) x += `<div class="hcell"><div class="fr fin" data-seen="${s.key}" role="button" tabindex="0"><span class="pic">${s.big ? `<span class="big">${esc(s.big)}</span>` : '<span class="big">✓</span>'}</span><span class="cap">${esc(s.title)}</span></div></div>`;
        else x += `<div class="hcell">${s.steps.map(st => frame(s, st)).join("")}</div>`;
      });
    });
    hero.innerHTML = `<div class="hscroll" id="hscroll">${x}</div></div><button class="hnav prev" aria-label="Назад по пути">‹</button><button class="hnav next" aria-label="Дальше по пути">›</button>`;
    const sc = document.getElementById("hscroll"), prev = hero.querySelector(".prev"), next = hero.querySelector(".next");
    const sync = () => { prev.hidden = sc.scrollLeft < 8; next.hidden = sc.scrollLeft + sc.clientWidth > sc.scrollWidth - 8 };
    sc.addEventListener("scroll", sync, { passive: true }); window.addEventListener("resize", sync); sync();
    prev.addEventListener("click", () => sc.scrollBy({ left: -sc.clientWidth * .8, behavior: "smooth" }));
    next.addEventListener("click", () => sc.scrollBy({ left: sc.clientWidth * .8, behavior: "smooth" }));
    /* вертикального содержимого у раскадровки нет: колесо мыши листает путь вправо-влево */
    sc.addEventListener("wheel", e => { if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && !e.ctrlKey) { e.preventDefault(); sc.scrollBy({ left: e.deltaY, behavior: "instant" }) } }, { passive: false });

    /* кадры внутри шага: сами листаются каждые 3 с, пока кадр на экране и под ним нет курсора */
    const multi = [...hero.querySelectorAll('.pic:not([data-n="0"]):not([data-n="1"])')].filter(el => el.dataset.n);
    const seen = new Set();
    if ("IntersectionObserver" in window) { const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting ? seen.add(e.target) : seen.delete(e.target)), { root: sc, threshold: .6 }); multi.forEach(el => io.observe(el)) }
    else multi.forEach(el => seen.add(el));
    const calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (multi.length && !calm) setInterval(() => seen.forEach(el => { if (!el.matches(":hover") && !body.classList.contains("open")) slide(el, 1) }), 3000);
  })();
  function slide(pic, d, to) {
    const n = +pic.dataset.n, i = to != null ? to : (+pic.dataset.i + d + n) % n;
    pic.dataset.i = i; pic.querySelector(".track").style.transform = `translateX(${-i * 100}%)`;
    pic.closest(".fr").querySelectorAll(".dots i").forEach((x, k) => x.classList.toggle("on", k === i));
  }

  /* ---------- слой «Релиз»: дорожки DEV/STAGE/PROD, шаги, ворота, правки в браузере ----------
     Данные — ключ «release» #map-data (появляется, когда в проекте есть документ «План релиза»).
     Правки хранятся в браузере (как «Исполнение» задач) и отдаются командой `backlog doc update`;
     пересобранная карта закрывает их — значения совпали с проектом. */
  const RL = D.release || null;
  const TRACK_C = { dev: "#0f8b8d", stage: "#d06a12", prod: "#c2338a" };
  const TRACK_T = { dev: "DEV", stage: "STAGE", prod: "PROD" };
  const RL_KINDS = { "согласование": "согл.", "задача devops": "devops", "предоставление доступа или данных": "доступ", "утверждение": "утв.", "проверка": "пров." };
  const RL_STATUS = { "не начат": "todo", "в работе": "run", "готово": "done", "требует ответа": "wait" };
  const RL_ST = { todo: "не начат", run: "в работе", done: "готово", wait: "требует ответа" };
  const rlKey = `bp-rl-${D.epic}`;
  const gridRel = document.getElementById("rel");
  let maxTrack = "";   /* дорожка, где работа сейчас: первая незакрытая, все закрыты — последняя */
  let RL_EDITS = {};
  try { RL_EDITS = JSON.parse(localStorage.getItem(rlKey) || "{}") } catch (e) { }
  const rlSave = () => { try { localStorage.setItem(rlKey, JSON.stringify(RL_EDITS)) } catch (e) { } };
  const rlStep = id => D.release.steps.find(s => s.id === id) || {};
  /* правка шага поверх данных проекта; пустое значение — как в проекте */
  const rlV = (s, f) => RL_EDITS[s] && RL_EDITS[s][f] != null && RL_EDITS[s][f] !== "" ? RL_EDITS[s][f] : rlStep(s)[f];
  /* следующий свободный ID: больше любого существующего числового R<n> */
  const rlNextId = () => "R" + (RL.steps.reduce((m, s) => Math.max(m, parseInt(s.id.slice(1), 10) || 0), 0) + 1);
  function rlEdit(id, f, v) {
    RL_EDITS[id] = RL_EDITS[id] || {};
    RL_EDITS[id][f] = v;
    rlSave(); rlBoard();
    if (side.dataset.ctx === "release:" + id) openRelease(id);
  }
  function rlCard(s, k, i) {
    const st = RL_STATUS[rlV(s.id, "status")] || "todo", deps = rlV(s.id, "deps") || [];
    const depHTML = deps.length ? `<span class="rldep">${deps.map(d => `<span class="rlref${rlV(d, "status") === "готово" ? " ok" : ""}" data-rlgo="${esc(d)}" role="button" tabindex="0">${esc(d)}</span>`).join("")}</span>` : "";
    return `<button class="rlcard${st === "done" ? " done" : ""}${st === "wait" ? " wait" : ""}${st === "run" ? " run" : ""}" data-rlstep="${esc(s.id)}" data-team="${s.track}" style="--c:${TRACK_C[s.track]}">
      <span class="rltop"><b class="rid">${esc(s.id)}</b><span class="rkind">${esc(RL_KINDS[s.kind] || s.kind)}</span>${depHTML}<i class="rst ${st}"></i></span>
      <span class="raction">${esc(rlV(s.id, "action"))}</span>
      <span class="rlwho">${esc(rlV(s.id, "owner"))}</span>
      <span class="rlready">${esc(s.ready)}</span></button>`;
  }
  function rlBoard() {
    if (!RL) return;
    const el = gridRel;
    if (!el) return;
    const tracks = RL.tracks;
    maxTrack = "";
    for (const t of tracks) {
      if (maxTrack) break;
      const steps = RL.steps.filter(s => s.track === t.id);
      if (steps.length && steps.every(s => rlV(s.id, "status") === "готово")) continue;
      maxTrack = t.id;
    }
    if (!maxTrack) maxTrack = tracks[tracks.length - 1].id;
    el.innerHTML = `<div class="rlscroll"><div class="rlboard" style="--tc:${tracks.length}">
      ${tracks.map((t, ti) => {
        const steps = RL.steps.filter(s => s.track === t.id);
        const gate = RL.gates.find(g => g.frm === t.id);
        const done = steps.filter(s => rlV(s.id, "status") === "готово").length;
        const trackSt = steps.length ? (done === steps.length ? "done" : "run") : "";
        return `<div class="rltrack${trackSt ? " " + trackSt : ""}" data-rltrack="${t.id}" style="--c:${TRACK_C[t.id]}">
          <div class="rlth"><b>${esc(t.title)}</b><span>${done} / ${steps.length}</span></div>
          <div class="rlcol">${steps.map((s, i) => rlCard(s, ti, i)).join("") || '<p class="rlempty">Шагов нет</p>'}</div>
          ${gate ? `<div class="rlgate" data-rlgate="${t.id}"><span class="rlgl">ВОРОТА · ${esc(TRACK_T[gate.frm])} → ${esc(TRACK_T[gate.to])}</span><span class="rlgw">${esc(gate.who)}</span><span class="rlgc">${esc(gate.criterion)}</span></div>`
            : ti === tracks.length - 1 ? '<div class="rlgate last"><span class="rlgl">Вышло в PROD — конец пути</span></div>' : ""}
        </div>`;
      }).join("")}</div></div>`;
  }
  const shq = x => `'${String(x == null ? "" : x).replace(/'/g, "'\\''")}'`;
  /* документ «План релиза» из полных строк таблиц: фронmatter + паспорт + «## Шаги» + «## Ворота» */
  function rlDocText() {
    const mk = (hdr, rows) => [`| ${hdr.join(" | ")} |`, `| ${hdr.map(() => "---").join(" | ")} |`, ...rows].join("\n");
    const step = s => { const deps = rlV(s.id, "deps") || [];
      return `| ${s.id} | ${s.track} | ${rlV(s.id, "action")} | ${rlV(s.id, "owner")} | ${s.kind} | ${deps.length ? deps.join(", ") : "—"} | ${rlV(s.id, "status")} | ${s.ready} |` };
    return ["---", `id: ${RL.doc}`, "title: План релиза", "type: specification", "created_date: '2026-01-01 00:00'", "---", "<!-- bft-release",
      `epic_slug: ${D.epic}`, `version: ${RL.version}`, "revised: 2026-01-01", `status: ${RL.status}`, "-->", "",
      `# План релиза: ${D.title}`, "", "## Шаги", "",
      mk(["ID", "Стенд", "Что сделать", "Ответственный", "Тип", "Зависимости", "Статус", "Критерий готовности"], RL.steps.map(step)), "",
      "## Ворота", "",
      mk(["Ворота", "Кто утверждает", "Критерий перехода"], RL.gates.map(g => `| ${g.frm} | ${g.who} | ${g.criterion} |`)), ""].join("\n");
  }
  function rlCmd() {
    return `backlog doc update ${RL.doc} --content $'${rlDocText().replace(/'/g, "'\\''")}'`;
  }
  /* панель шага: поля шага, статусы, зависимости, ворота дорожки, кнопка с командой для бэклога */
  function openRelease(id, added) {
    if (!RL) return;
    execHide();
    const s = rlStep(id), track = RL.tracks.find(t => t.id === s.track), gate = RL.gates.find(g => g.frm === s.track);
    const st = RL_STATUS[rlV(id, "status")] || "todo";
    const all = RL.steps.map(x => x.id);
    const deps = rlV(id, "deps") || [];
    const depBoxes = `<ul class="rldeps">${all.filter(x => x !== id).map(x => `<li><label><input type="checkbox" data-rldep="${esc(x)}"${deps.includes(x) ? " checked" : ""}>${esc(x)}${rlV(x, "status") === "готово" ? " ✓" : ""}</label></li>`).join("")}</ul>`;
    const gatesHTML = `<ul class="rlgates">${RL.gates.map(g => `<li><b>${esc(TRACK_T[g.frm])} → ${esc(TRACK_T[g.to])}</b><span class="rlgw">${esc(g.who)}</span><span class="rlgc">${esc(g.criterion)}</span></li>`).join("") || '<li class="rlempty">Ворот нет</li>'}</ul>`;
    const tracks = RL.tracks.map(t => `<button data-rltrack-btn="${t.id}" class="${t.id === s.track ? "on" : ""}">${esc(t.title)}</button>`).join("");
    const html = `
      <div class="rlform">
        <label>Что сделать<input data-rlf="action" value="${esc(rlV(id, "action"))}"></label>
        <label>Ответственный<input data-rlf="owner" value="${esc(rlV(id, "owner"))}"></label>
        <label>Статус<span class="rlsts">${Object.keys(RL_STATUS).map(x => `<button data-rlst="${esc(x)}" class="${x === rlV(id, "status") ? "on" : ""}">${esc(x)}</button>`).join("")}</span></label>
        <div class="rlsec"><h4>Зависимости</h4>${depBoxes}</div>
        <div class="rlsec"><h4>Критерий готовности</h4><p class="rlcr">${esc(s.ready)}</p></div>
        <div class="rlsec"><h4>Ворота переходов</h4>${gatesHTML}</div>
        <div class="rlsec rlcmd"><h4>Правки — в проект</h4><button class="tool pri" data-rlcopy>Скопировать команду для бэклога</button>
          <span class="dhint">Правки хранит браузер; команда перепишет документ «План релиза» (${esc(RL.doc)}) целиком, поле «Кто утверждает» ворот и тип шага меняются в файле.</span></div>
      </div>${added || ""}`;
    side.innerHTML = head(`${s.id} · ${esc(rlV(id, "action"))}`, `<span class="rltr" style="--c:${TRACK_C[s.track]}">${esc(track.title)}</span> · ${esc(RL_KINDS[s.kind] || s.kind)} · <span class="rst ${st} t"></span>${esc(rlV(id, "status"))}`) + `<div class="snbody">${html}</div>`;
    body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "release:" + id; side.dataset.note = "";
  }
  function rlOpenAdd() {
    execHide();
    const nid = rlNextId();
    const html = `<div class="rlform">
      <label>ID<input value="${esc(nid)}" readonly></label>
      <label>Стенд<span class="rlsts">${RL.tracks.map(t => `<button data-rltrack-add="${t.id}" class="${t.id === maxTrack ? "on" : ""}">${esc(t.title)}</button>`).join("")}</span></label>
      <label>Что сделать<input id="rl-new-action" placeholder="Например: Поднять стенд DEV с новой версией"></label>
      <label>Ответственный<input id="rl-new-owner" placeholder="Роль или команда"></label>
      <label>Тип<select id="rl-new-kind">${Object.keys(RL_KINDS).map(k => `<option>${esc(k)}</option>`).join("")}</select></label>
      <div class="rlsec"><h4>Зависимости</h4><ul class="rldeps">${RL.steps.map(x => `<li><label><input type="checkbox" data-rldepnew="${esc(x.id)}">${esc(x.id)} · ${esc(rlV(x.id, "action"))}</label></li>`).join("")}</ul></div>
      <label>Критерий готовности<input id="rl-new-ready" placeholder="По чему понять, что шаг готов"></label>
      <div class="cmrow"><button class="cmsave" data-rladd>Добавить шаг</button><button class="cmcancel" data-rlcancel>Отмена</button></div></div>`;
    side.innerHTML = head("Новый шаг плана релиза", "черновик шага — применится командой для бэклога") + `<div class="snbody">${html}</div>`;
    body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "release-add"; side.dataset.note = "";
    side.dataset.track = maxTrack;
  }
  function rlAddStep() {
    const action = side.querySelector("#rl-new-action").value.trim() || "Новый шаг";
    const owner = side.querySelector("#rl-new-owner").value.trim() || "—";
    const kind = side.querySelector("#rl-new-kind").value;
    const ready = side.querySelector("#rl-new-ready").value.trim() || "—";
    const track = side.dataset.track || RL.tracks[0].id;
    const nid = rlNextId();
    const deps = [...side.querySelectorAll("[data-rldepnew]")].filter(c => c.checked).map(c => c.dataset.rldepnew);
    RL.steps.push({ id: nid, track, action, owner, kind, deps, status: "не начат", ready, file: RL.steps[0] ? RL.steps[0].file : "" });
    RL_EDITS[nid] = { action, owner, kind, deps, status: "не начат", ready, track };
    rlSave(); rlBoard(); openRelease(nid);
  }
  function rlGo(id) { if (body.dataset.view === "rel") { openRelease(id); const c = gridRel.querySelector(`[data-rlstep="${id}"]`); if (c) c.scrollIntoView({ block: "center", behavior: "smooth" }) } }
  /* ---------- слой «Roadmap»: кто что делает по неделям, недели — в спринтах ----------
     Данные — документ «Roadmap» (ключ roadmap #map-data). Строка — команда-исполнитель (техлид рядом),
     полоса — история или подзадача по зоне, с какой недели по какую; пересекающиеся полосы команды —
     друг под другом. Шапка — спринты и недели с датами, текущая неделя подсвечена. Клик — постановка.
     Работы карты без строки в плане — списком «Вне плана». */
  const RM = D.roadmap || null, gridRoad = document.getElementById("road");
  function rmBoard() {
    if (!RM || !gridRoad) return;
    const W = RM.weeks, SW = RM.sprintWeeks, d0 = new Date(RM.start + "T00:00:00");
    const day = (w, k) => { const x = new Date(d0); x.setDate(x.getDate() + 7 * (w - 1) + k); return x };
    const dm = x => `${String(x.getDate()).padStart(2, "0")}.${String(x.getMonth() + 1).padStart(2, "0")}`;
    const now = new Date(), nowW = Math.floor((now - d0) / 864e5 / 7) + 1;
    const work = id => TASK[id] || SUB[id];
    const items = RM.items.filter(i => work(i.id));
    const teamIds = [...D.teams.map(t => t.id), "?"].filter(tm => items.some(i => work(i.id).team === tm));
    const cols = `grid-template-columns:var(--rmw) repeat(${W}, minmax(112px, 1fr))`;
    const wcol = (w, cls) => `<div class="rmc${w % SW === 0 && w < W ? " se" : ""}${w === nowW ? " now" : ""}${cls || ""}" style="grid-column:${w + 1}"></div>`;
    let h = `<div class="rmhd" style="${cols}"><div class="rmc0"></div>${Array.from({ length: W / SW }, (_, k) => `<div class="rmsp" style="grid-column:${k * SW + 2} / span ${SW}">Спринт ${k + 1}</div>`).join("")}
      ${Array.from({ length: W }, (_, k) => `<div class="rmwk${k + 1 === nowW ? " now" : ""}" style="grid-column:${k + 2}"><b>Неделя ${k + 1}</b>${dm(day(k + 1, 0))}–${dm(day(k + 1, 4))}</div>`).join("")}</div>`;
    teamIds.forEach(tm => {
      const mine = items.filter(i => work(i.id).team === tm).sort((a, b) => a.start - b.start || b.end - a.end);
      const lanes = []; mine.forEach(i => { let l = lanes.findIndex(end => end < i.start); if (l < 0) { l = lanes.length; lanes.push(0) } lanes[l] = i.end; i._lane = l + 1 });
      const t = tm === "?" ? { team: "?" } : { team: tm }, lead = tm in TEAM && (D.teams.find(x => x.id === tm) || {}).lead;
      h += `<div class="rmrow" style="${cols};--c:${teamC(t)}"><div class="rmtm" style="grid-row:1 / ${lanes.length + 1}"><i></i><b>${esc(tm === "?" ? "Команда не определена" : teamN(t))}</b>${lead ? `<small>${esc(lead)}</small>` : ""}<small>${mine.length} ${plural(mine.length, "работа", "работы", "работ")}</small></div>
        ${Array.from({ length: W }, (_, k) => wcol(k + 1).replace('style="', `style="grid-row:1 / ${lanes.length + 1};`)).join("")}
        ${mine.map(i => { const w = work(i.id), z = SUB[i.id];
          return `<button class="rmbar${blocks(i.id).length ? " blk" : ""}${oos(w) ? " oos" : ""}" ${z ? "data-sub" : "data-task"}="${esc(i.id)}" style="grid-column:${i.start + 1} / ${i.end + 2};grid-row:${i._lane}" title="${esc(i.id)} · ${esc(w.text)} · недели ${i.start}–${i.end}"><span class="rmid">${z ? `<i class="zt" style="--c:${teamC(z)}">${esc(z.zone)}</i>` : ""}${esc(i.id)}</span><span class="rmtx">${esc(w.text)}</span></button>` }).join("")}</div>`;
    });
    const planned = new Set(RM.items.map(i => i.id));
    const off = [...D.tasks.filter(t => !oos(t) && !subsOf(t.id).length && !planned.has(t.id)), ...SUBS.filter(z => !oos(z) && !planned.has(z.id))];
    const last = day(W, 4);
    gridRoad.innerHTML = `<div class="rmwrap"><div class="rmhead"><button class="rmback" data-view="see">← К карте</button><span class="arst">${esc(RM.status)}</span><h2>Roadmap</h2>
      <p>${W / SW} ${plural(W / SW, "спринт", "спринта", "спринтов")} по ${SW} ${plural(SW, "неделе", "недели", "недель")} · ${dm(day(1, 0))} — ${dm(last)}.${last.getFullYear()} · не больше ${RM.maxSprints} спринтов</p></div>
      <div class="rmscroll"><div class="rmboard">${h}</div></div>
      ${off.length ? `<div class="rmoff"><h4>Вне плана · ${off.length}</h4>${off.map(w => `<button class="ref" ${SUB[w.id] ? "data-sub" : "data-task"}="${esc(w.id)}" title="${esc(w.text)}">${esc(w.id)}</button>`).join(" ")}</div>` : ""}</div>`;
  }

  /* ---------- вкладка «Риски»: риски исполнения историй, согласуются с PO, на основной карте их нет ----------
     Данные — документ «Риски исполнения» (ключ risks.items) и кандидаты по данным карты (risks.auto):
     стык BE+FE, DevOps, интеграция систем. Сводка по типам, риски по историям со статусом согласования;
     кандидаты без строки в документе — блоком «Не записаны». */
  const RK = D.risks || null, gridRisk = document.getElementById("risk");
  const RK_KIND = { befe: ["Стык BE+FE", "в истории подзадачи BE и FE — детали реализации не собраны, бэкенд может не успеть отдать данные"], devops: ["DevOps", "в истории работы DevOps — CI/CD, сетевые доступы, загрузка команды"], integration: ["Интеграция систем", "история работает с внешней системой или заводит новый сервис — согласования и доступы"], other: ["Другое", ""] };
  const RK_ST = { "на согласовании": "wait", "согласован": "ok", "снят": "off" };
  function rkBoard() {
    if (!RK || !gridRisk) return;
    const items = RK.items, have = new Set(items.map(r => r.story + ":" + r.kind)), miss = RK.auto.filter(a => !have.has(a.story + ":" + a.kind));
    const kinds = Object.keys(RK_KIND).filter(k => items.some(r => r.kind === k) || miss.some(a => a.kind === k));
    const ok = items.filter(r => r.status === "согласован").length;
    const stories = [...new Set(items.map(r => r.story))].sort((a, b) => D.tasks.findIndex(t => t.id === a) - D.tasks.findIndex(t => t.id === b));
    const card = r => `<div class="rkcard ${RK_ST[r.status] || ""}"><div class="rktop"><span class="rkk">${esc(RK_KIND[r.kind][0])}</span><span class="rkid">${esc(r.id)}</span><span class="rkst ${RK_ST[r.status] || ""}">${esc(r.status)}</span></div>
      <p class="rktx">${mdInline(r.text)}</p><p class="rkm"><span>Митигация</span>${mdInline(r.mitigation)}</p><p class="rko">Владелец · ${esc(r.owner)}</p></div>`;
    gridRisk.innerHTML = `<div class="rkwrap"><div class="rmhead"><button class="rmback" data-view="see">← К карте</button>${RK.status ? `<span class="arst">${esc(RK.status)}</span>` : ""}<h2>Риски исполнения</h2>
      <p>Согласуются с PO инициативы · ${items.length} ${plural(items.length, "риск", "риска", "рисков")}, согласовано ${ok}${miss.length ? ` · не записано ${miss.length}` : ""}</p></div>
      <div class="rksum">${kinds.map(k => `<div class="rks"><b>${items.filter(r => r.kind === k).length + miss.filter(a => a.kind === k).length}</b><span>${esc(RK_KIND[k][0])}</span><small>${esc(RK_KIND[k][1])}</small></div>`).join("")}</div>
      ${stories.map(sid => { const t = TASK[sid] || { id: sid, text: sid };
        return `<section class="rkst-g"><button class="ui-head" data-task="${esc(sid)}"><span class="ui-chip">История</span><span class="ui-name">${esc(t.text)}</span><span class="ui-tags"><span class="ui-zone">${esc(sid)}</span></span></button>
          <div class="rkgrid">${items.filter(r => r.story === sid).map(card).join("")}</div></section>` }).join("")}
      ${miss.length ? `<section class="rkmiss"><h4>Не записаны — найдены по данным карты</h4>${miss.map(a => `<button class="rkm-i" data-task="${esc(a.story)}"><span class="rkk">${esc(RK_KIND[a.kind][0])}</span><b>${esc(a.story)}</b> ${esc((TASK[a.story] || {}).text || "")}<small>${esc(RK_KIND[a.kind][1])}</small></button>`).join("")}</section>` : ""}</div>`;
  }

  /* первый шаг дорожки — куда ведут её ворота */
  const rlStepOfTrack = tr => { const s = RL.steps.find(x => x.track === tr); return s ? s.id : (RL.steps[0] ? RL.steps[0].id : "") };


  /* ---------- три слоя: «Что видят», «Что делаем», «Как это работает» — переключатель, а не прокрутка страницы ----------
     «Что делаем» и «Как это работает» — одна сетка с общей строкой этапов, слой прячет чужие ряды.
     Четвёртый слой «Релиз» — доска дорожек DEV/STAGE/PROD, отдельная разметка (#rel). */
  const work = document.getElementById("work");
  function setView(v) {
    const was = body.dataset.view; if (was === v) return;
    const hs = document.getElementById("hscroll"), hh = [...hero.querySelectorAll(".hh")], mh = [...grid.querySelectorAll(".mh:not(.corner)")];
    const firstVisible = (els, box, pad) => Math.max(0, els.findIndex(el => el.getBoundingClientRect().right > box.getBoundingClientRect().left + pad + 24));
    body.dataset.view = v;
    document.querySelectorAll("button[data-view]").forEach(b => b.classList.toggle("on", b.dataset.view === v));
    if (v === "rel") { if (RL) { rlBoard(); gridRel.scrollIntoView({ block: "start" }) } return }
    if (v === "adr") { if (AR || SR) { adrBoard(); adrGrid.scrollIntoView({ block: "start" }) } return }
    if (v === "road") { if (RM) { rmBoard(); gridRoad.scrollTop = 0 } return }
    if (v === "risk") { if (RK) { rkBoard(); gridRisk.scrollTop = 0 } return }
    if (was === "rel" || was === "adr" || was === "road" || was === "risk") { window.scrollTo(0, 0) }
    const col = was === "see" ? firstVisible(hh, hs, 132) : was === "rel" || was === "road" || was === "risk" ? 0 : firstVisible(mh, work, 96);
    if (v === "see") hs.scrollLeft = hh[col] ? hh[col].offsetLeft - 132 : 0;
    else { work.scrollTop = 0; work.scrollLeft = mh[col] ? mh[col].offsetLeft - 96 : 0 }
    drawLinks();
  }
  body.dataset.view = "see";

  /* ---------- телефон: шаг за шагом сверху вниз; план релиза и архитектура — секциями в начале стека ---------- */
  document.getElementById("mstack").innerHTML = (RL ? `<section class="ms rlms"><div class="mh2"><span class="n">↗</span><div><b>План релиза</b><small>DEV → STAGE → PROD, ворота переходов</small></div></div><div class="wl" id="mrel"></div></section>` : "") + ((AR || SR) ? `<section class="ms arsms"><div class="mh2"><span class="n">A</span><div><b>Архитектура</b><small>ADR и системные требования: как реализуем</small></div></div><div id="madr"></div></section>` : "") + COLS.map((col, c) => {
    const tasks = byPrio(D.tasks.filter(t => t.stage === col.id)), procs = D.cards.filter(p => p.stage === col.id);
    return `<section class="ms"><div class="mh2"><span class="n">${c === COLS.length - 1 ? "✓" : c + 1}</span><div><b>${esc(col.name)}</b>${col.when ? `<small>${esc(col.when)}</small>` : ""}</div></div>
      <div class="wl">${seenHTML(c)}</div>${tasks.some(t => !oos(t)) ? `<span class="lb">Что делаем</span><div class="wl">${tasks.filter(t => !oos(t)).map(taskHTML).join("")}</div>` : ""}${tasks.some(oos) ? `<span class="lb oosb">Out of scope · Would</span><div class="wl">${tasks.filter(oos).map(taskHTML).join("")}</div>` : ""}
      ${procs.length ? `<span class="lb">Как это работает</span><div class="wl">${procs.map(procHTML).join("")}</div>` : ""}</section>`;
  }).join("");
  /* телефон: план релиза — дорожки по очереди, карточки те же, ворота строкой */
  if (RL) {
    const mr = document.getElementById("mrel");
    if (mr) mr.innerHTML = RL.tracks.map(t => {
      const steps = RL.steps.filter(s => s.track === t.id), gate = RL.gates.find(g => g.frm === t.id);
      return `<span class="lb">${esc(t.title)}</span>` + (steps.map((s, i) => rlCard(s, 0, i)).join("") || '<p class="rlempty">Шагов нет</p>') +
        (gate ? `<div class="rlgate" style="margin:4px -14px 8px"><span class="rlgl">ВОРОТА → ${esc(TRACK_T[gate.to])}</span><span class="rlgw">${esc(gate.who)}</span><span class="rlgc">${esc(gate.criterion)}</span></div>` : "");
    }).join("");
  }
  /* телефон: архитектура — те же вкладки и таблицы, диаграмма текстом mermaid;
     рендер отложен до конца файла (arInit) — adrOpen/sysOpen и табличные хелперы
     объявлены ниже по файлу, при загрузке сразу их звать нельзя (TDZ) */
  function arInit() {
    if (!(AR || SR)) return;
    const mr = document.getElementById("madr");
    if (!mr) return;
    {
      arCur = "adr";
      mr.innerHTML = `<div class="arwrap"><div class="arnav">${AR ? `<button data-artab="adr" class="on">ADR</button>` : ""}${SR ? `<button data-artab="sys">Системные требования</button>` : ""}</div>${AR ? adrOpen(true) : ""}${SR ? sysOpen() : ""}</div>`;
      mr.querySelectorAll("[data-artab]").forEach(b => b.addEventListener("click", () => {
        arCur = b.dataset.artab;
        mr.querySelectorAll("[data-artab]").forEach(x => x.classList.toggle("on", x === b));
        mr.innerHTML = `<div class="arwrap"><div class="arnav">${AR ? `<button data-artab="adr"${arCur === "adr" ? ' class="on"' : ""}>ADR</button>` : ""}${SR ? `<button data-artab="sys"${arCur === "sys" ? ' class="on"' : ""}>Системные требования</button>` : ""}</div>${arCur === "adr" && AR ? adrOpen(true) : ""}${arCur === "sys" && SR ? sysOpen() : ""}</div>`;
      }));
    }
  }

  /* ---------- боковая панель ---------- */
  const side = document.getElementById("side");
  function openSide(tag, color, title, meta, html, wide) {
    side.dataset.ctx = ""; side.dataset.note = ""; execHide();
    side.innerHTML = `<div class="stop"><span class="tag" style="--c:${color}">${esc(tag)}</span><h3>${esc(title)}</h3><div class="meta">${meta}</div><button class="x" aria-label="Закрыть">×</button></div><div class="sin">${html}</div>`;
    body.classList.toggle("wide", !!wide); body.classList.add("open"); side.scrollTop = 0;
  }
  const closeSide = () => { body.classList.remove("open", "wide"); execHide() };

  function openSeen(key) {
    const s = D.seen.find(x => x.key === key), p = D.personas.find(x => x.id === s.persona), col = COLS[s.col];
    const html = s.steps.map(st => `<div class="stp">${st.screens.length ? `<div class="chips2">${[...new Set(st.screens.map(id => D.screens[id].contour))].map(chip).join("")}</div><div class="vis">${st.screens.map(id => mock(id, 170)).join("")}</div>` : ""}
      <h5>${esc(st.title)}</h5><p>${esc(st.text)}</p>${st.was ? `<div class="was"><b>Раньше</b>${esc(st.was)}</div>` : ""}
      ${qList(qsOf([st.id, ...st.screens]))}<div class="src">Источник: ${esc(st.source)}</div></div>`).join("");
    execPrep(s.steps.flatMap(st => st.screens));
    side.innerHTML = head(col.name, `<span class="pteam" style="--c:#2f6b2a"><i></i>${esc(p.name)}</span> · ${esc(p.lane)} · ${s.steps.length} ${plural(s.steps.length, "шаг", "шага", "шагов")}`) + `<div class="snbody">${html}${execInline()}</div>`;
    body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "seen:" + key; side.dataset.note = "";
    execShow(s.steps.flatMap(st => st.screens), "seen:" + key);
  }

  /* ---------- «Исполнение»: вторая панель рядом с экраном — задачи «Что делаем», которые его делают ----------
     Связь — из проекта Backlog.md: documentation задачи или её карточки ссылается на документ экрана
     (строка «экраны: F3» плана, `./backlog.py task edit BP-16 --doc doc-12`). Задачи — по командам,
     клик открывает постановку, «←» возвращает к экрану. Узкий экран — тот же список внизу панели экрана. */
  const ex = document.getElementById("exec");
  const DOC_SCR = {}, SCR_DOC = {}, SCR_TASKS = {};
  Object.keys(D.docs).forEach(k => { const sid = D.docs[k].screen; if (sid) { DOC_SCR[k] = sid; SCR_DOC[sid] = SCR_DOC[sid] || k } });
  const docKey = x => String(x).toLowerCase().split(" ")[0];
  const linkScr = (doc, tid) => { const sid = DOC_SCR[docKey(doc)]; if (!sid || !TASK[tid]) return; const l = SCR_TASKS[sid] = SCR_TASKS[sid] || []; if (!l.includes(tid)) l.push(tid) };
  D.tasks.forEach(t => t.docs.forEach(d => linkScr(d, t.id)));
  D.cards.forEach(c => c.docs.forEach(d => linkScr(d, c.task)));
  let exFrom = "", exIds = [], exScr = [];
  function execPrep(sids) {
    exScr = [...new Set(sids)];
    exIds = [...new Set(exScr.flatMap(s => SCR_TASKS[s] || []))].sort((a, b) => colOf(TASK[a].stage) - colOf(TASK[b].stage));
  }
  function execList(cur) {
    const groups = [...D.teams.map(t => t.id), "?"].map(tm => [tm, exIds.filter(id => (TASK[id].team in TEAM ? TASK[id].team : "?") === tm)]).filter(g => g[1].length);
    const item = id => { const t = TASK[id], b = blocks(id).length;
      return `<li data-extask="${esc(id)}" tabindex="0"${id === cur ? ' class="on"' : ""}><b>${esc(t.text)}</b><span>${esc(id)} · ${esc(t.status)}</span>${b ? '<i class="q" title="Блокер"></i>' : ""}</li>` };
    const empty = `<p class="exno">Задач для экрана нет. Свяжите задачу с ним строкой «экраны: ${esc(exScr.join(", "))}» в плане.</p>`;
    return groups.length ? groups.map(([tm, ids]) => { const t = TASK[ids[0]];
      return `<section class="exg"><h4 style="--c:${teamC(t)}"><i></i>${esc(tm === "?" ? "Команда не определена" : teamN(t))}</h4><ul class="snstack exl">${ids.map(item).join("")}</ul></section>` }).join("") : empty;
  }
  const execInline = () => exScr.length ? `<div class="exin"><h4 class="exh">Исполнение · ${exIds.length}</h4>${execList("")}</div>` : "";
  function execShow(sids, from, cur) {
    if (from) { execPrep(sids); exFrom = from }
    if (!exScr.length) return execHide();
    body.classList.remove("how"); ex.dataset.task = "";
    ex.innerHTML = `<div class="snbar"><h3>Исполнение</h3><span class="excnt">${nTasks(exIds.length)}</span></div><div class="snbody">${execList(cur || "")}</div>`;
    body.classList.add("side2");
  }
  function execHide() { body.classList.remove("side2", "how"); exFrom = ""; ex.dataset.task = "" }
  /* «←»: из подзадачи и карточки «Как это работает» — к истории, из постановки — к экрану или этапу, откуда её открыли, иначе — к экрану */
  function goBack() {
    const [kind, id] = (side.dataset.ctx || ":").split(":");
    if (kind === "sub") return openTask(SUB[id].task, 0);
    if (kind === "proc" && TASK[PROC[id].task]) return openTask(PROC[id].task, 0);
    return kind === "task" && exFrom ? execBack() : openScreen(snCur);
  }
  /* назад из постановки — к экрану или этапу, откуда её открыли */
  function execBack() {
    const [kind, id] = exFrom.split(/:(.*)/);
    return kind === "seen" ? openSeen(id) : openScreen(kind === "screen" ? id : snCur);
  }
  /* ---------- HowToDemo: шаги списком, под ними — раскадровка, раскрывается вниз: картинка и краткое название ----------
     Экраны — те, на которые ведёт documentation задачи или карточки. Экран шага: ID в тексте шага «(F3)»,
     иначе экран, чьё название ближе к тексту шага, иначе экран прошлого шага. «Делаю — вижу» делит
     первое «→» или «—». Шаги не списком или экранов нет — HowToDemo текстом, как раньше. */
  const scrName = sid => SCR_DOC[sid] ? D.docs[SCR_DOC[sid]].title.replace(/^[^·]*·\s*/, "") : sid;
  const stems = x => new Set((String(x).toLowerCase().match(/[a-zа-яё0-9]{4,}/g) || []).map(w => w.slice(0, 5)));
  const SID_RE = /\s*\(([A-ZА-Я]\d{1,2}(?:\s*,\s*[A-ZА-Я]\d{1,2})*)\)/g;
  function demoHTML(md, docs) {
    const lines = String(md || "").trim().split("\n").filter(l => l.trim());
    const sids = [...new Set(docs.map(d => DOC_SCR[docKey(d)]).filter(Boolean))];
    if (!lines.length || !sids.length || !lines.every(l => /^\d+\.\s/.test(l))) return mdHTML(md || "");
    let prev = "";
    const steps = lines.map(l => {
      let text = l.replace(/^\d+\.\s+/, ""), sid = "";
      text = text.replace(SID_RE, (m, ids) => { sid = sid || ids.split(/\s*,\s*/).find(x => D.screens[x]) || ""; return sid ? "" : m });
      if (!sid) {
        const w = stems(text); let best = 0;
        sids.forEach(x => { const n = [...stems(scrName(x))].filter(y => w.has(y)).length; if (n > best || (n === best && n && x === prev)) { best = n; sid = x } });
      }
      sid = sid || prev || sids[0]; prev = sid;
      const m = text.match(/^(.+?)\s+[→—]\s+(.+)$/);
      return { sid, text, act: m ? m[1] : text, see: m ? m[2] : "" };
    });
    gallery = steps.map((st, i) => ({ alt: `Шаг ${i + 1} · ${st.sid} · ${scrName(st.sid)}`, src: screenImg(st.sid) }));
    return `<ol>${steps.map(st => `<li>${mdInline(st.text)}</li>`).join("")}</ol><details class="dmd"><summary>Раскадровка · ${steps.length} ${plural(steps.length, "шаг", "шага", "шагов")}</summary><ol class="demo">${steps.map((st, i) => `<li class="dm">
      <span class="dmpic"><img src="${esc(screenImg(st.sid))}" alt="${esc(scrName(st.sid))}" data-zoom="${i}" loading="lazy" draggable="false"></span>
      <span class="dmx"><b><span class="dmn">${i + 1}</span>${mdInline(st.act)}</b><small>${esc(st.sid)} · ${esc(scrName(st.sid))}</small></span></li>`).join("")}</ol></details>`;
  }
  /* ---------- «Как это работает» задачи: вторая панель слева от постановки ----------
     Карточка-превью: JobStory заголовком (нет — название карточки), под ней схема процесса (mermaid),
     панель листается. Клик — карточка целиком. Пришли из «Исполнения» экрана — слева остаётся оно. */
  function howShow(id) {
    const cards = D.cards.filter(c => c.task === id);
    if (!cards.length) return execHide();
    if (ex.dataset.task === id && body.classList.contains("how")) return;
    ex.dataset.task = id;
    ex.innerHTML = `<div class="snbar"><h3>Как это работает</h3><span class="excnt">${cards.length} ${plural(cards.length, "карточка", "карточки", "карточек")}</span></div><div class="snbody">${cards.map(c => { const L = LAYER[c.layer];
      return `<section class="hwc" data-proc="${esc(c.id)}" tabindex="0"><span class="hwm"><span class="lay" style="--c:${L[2]}">${L[0]}</span> · ${esc(c.id)}</span>
        <b>${mdInline((c.js || [])[0] || c.us || c.text)}</b>
        ${c.bpmn ? `<div class="bpmnw"><pre>${esc(c.bpmn)}</pre></div>` : ""}</section>` }).join("")}</div>`;
    body.classList.add("side2", "how"); ex.scrollTop = 0;
    ex.querySelectorAll(".bpmnw").forEach(drawMermaid);
  }
  /* подзадача истории по зоне: что сделать, исполнитель, критерии приемки; «←» — к истории */
  function openSub(id) {
    const z = SUB[id], t = TASK[z.task];
    const ac = z.ac.length ? `<ul class="zac">${z.ac.map(([, x]) => `<li>${mdInline(x)}</li>`).join("")}</ul>` : "";
    const brief = (ZONE_SECS[z.zone] || []).map(k => sec(k, mdHTML((z.brief || {})[k] || ""))).join("");
    const reqs = t && t.reqs.length ? `<p class="zreq"><span class="lk">Требования БФТ</span> ${t.reqs.map(esc).join(", ")}</p>` : "";
    side.innerHTML = head(z.text, `<b class="zt" style="--c:${teamC(z)}">${esc(z.zone)}</b> <span class="pteam" style="--c:${teamC(z)}"><i></i>${esc(z.team === "?" && z.cand ? "Команда? " + z.cand : teamN(z))}</span> · ${esc(id)} · ${esc(z.status)}`, true) + `<div class="snbody">
      ${z.lead ? `<p class="tklead">${mdInline(z.lead)}</p>` : ""}${brief}${sec(ZONE_CHECK[z.zone] || "Критерии приемки", ac)}${sec("Требования истории", t ? refList([`${idChip(t.id)} ${esc(t.text)}`]) + reqs : "")}${sec("Вопросы", qList(qsOf([id])))}</div>`;
    body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "sub:" + id; side.dataset.note = "";
  }
  function execOpen(id) {
    openTask(id, 0, true); execShow(null, "", id);
  }

  /* задача «Что делаем» — постановка для техлида, задача Backlog.md. «Требования»: зачем, ASIS, GAP, TOBE,
     HowToDemo, критерии приемки, дополнительно. «Исполнение»: ссылки на JIRA и Confluence (references) и
     заметка (Implementation Notes); правки — в браузере, в проект — командой `backlog task edit` */
  const dodKey = id => `bp-dod-${D.epic}-${id}`;
  let taskTab = 0;
  const execKey = id => `bp-exec-${D.epic}-${id}`;
  const isJira = u => /jira|\/browse\/[A-Z][A-Z0-9]+-\d+/i.test(u), isConf = u => !isJira(u) && /confluence|wiki|\/pages\//i.test(u);
  function execOf(t) {
    let v = null; try { v = JSON.parse(localStorage.getItem(execKey(t.id)) || "null") } catch (e) { }
    if (v) return v;
    const urls = t.refs.filter(u => /^https?:\/\//.test(u));
    return { jira: urls.filter(isJira).join(" "), conf: urls.filter(isConf).join(" "), note: t.notes || "" };
  }
  const links = s => (s || "").split(/[\s,]+/).filter(u => /^https?:\/\//.test(u)).map(u => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, "").slice(0, 48))}</a>`).join("");
  function execHTML(t) {
    const v = execOf(t);
    return `<div class="exec" data-exec="${esc(t.id)}">
      <label>JIRA<input data-ex="jira" value="${esc(v.jira)}" placeholder="Ссылка на задачу или эпик"></label><div class="exl">${links(v.jira)}</div>
      <label>Confluence<input data-ex="conf" value="${esc(v.conf)}" placeholder="Ссылка на страницу"></label><div class="exl">${links(v.conf)}</div>
      <label>Заметка<textarea data-ex="note" placeholder="Ход работ, решения, договорённости">${esc(v.note)}</textarea></label>
      <button class="tool" data-excopy="${esc(t.id)}">Скопировать команду для бэклога</button></div>`;
  }
  /* команда CLI Backlog.md: ссылки JIRA и Confluence заменяют прежние такие же, остальные references остаются */
  const sh = x => `'${String(x).replace(/'/g, "'\\''")}'`;
  function execCmd(id) {
    const t = TASK[id], v = execOf(t), split = s => (s || "").split(/[\s,]+/).filter(Boolean);
    const keep = t.refs.filter(u => !(/^https?:\/\//.test(u) && (isJira(u) || isConf(u))));
    const refs = [...keep, ...split(v.jira), ...split(v.conf)];
    return `backlog task edit ${id} ${refs.length ? refs.map(r => "--ref " + sh(r)).join(" ") : "--clear-refs"} --notes ${sh(v.note || "")}`;
  }
  document.addEventListener("input", e => {
    const f = e.target.closest && e.target.closest("[data-ex]"); if (f) {
      const id = f.closest("[data-exec]").dataset.exec, v = execOf(TASK[id]);
      v[f.dataset.ex] = f.value; try { localStorage.setItem(execKey(id), JSON.stringify(v)) } catch (er) { }
      if (f.dataset.ex !== "note") f.parentElement.nextElementSibling.innerHTML = links(f.value);
    }
    /* слой «Релиз»: правки полей шага — в браузер, командой для бэклога — в проект */
    const r = e.target.closest && e.target.closest("[data-rlf]");
    if (r && side.dataset.ctx.startsWith("release:")) {
      const id = side.dataset.ctx.split(":")[1];
      RL_EDITS[id] = RL_EDITS[id] || {}; RL_EDITS[id][r.dataset.rlf] = r.value; rlSave();
      const card = gridRel.querySelector(`[data-rlstep="${id}"]`);
      if (card) { const act = card.querySelector(".raction"), who = card.querySelector(".rlwho"); if (r.dataset.rlf === "action") act.textContent = r.value; if (r.dataset.rlf === "owner") who.textContent = r.value }
    }
  });
  document.addEventListener("change", e => {
    const c = e.target.closest && e.target.closest("[data-dod]");
    if (c) {
      const [id, k] = c.dataset.dod.split(":"); let d = {}; try { d = JSON.parse(localStorage.getItem(dodKey(id)) || "{}") } catch (er) { }
      d[k] = c.checked; try { localStorage.setItem(dodKey(id), JSON.stringify(d)) } catch (er) { }
    }
    /* слой «Релиз»: галочка зависимости шага */
    const rc = e.target.closest && e.target.closest("[data-rldep]");
    if (rc && side.dataset.ctx.startsWith("release:")) {
      const id = side.dataset.ctx.split(":")[1], deps = new Set(rlV(id, "deps") || []);
      rc.checked ? deps.add(rc.dataset.rldep) : deps.delete(rc.dataset.rldep);
      rlEdit(id, "deps", [...deps]);
    }
  });
  const sec = (name, html) => html ? `<section class="tk"><h4>${name}</h4>${html}</section>` : "";
  /* вопросы карточки и задачи — те же, что в «Уточнить»: клик — ответить */
  const qList = qs => qs.length ? `<ul class="tkq">${qs.map(q => { const st = qState(q);
    return `<li class="${q.kind === "блокер" ? "b " : ""}${st}" data-q="${esc(q.key)}" tabindex="0">${st === "done" || st === "past" ? '<i class="ok">✓</i>' : '<i class="qd"></i>'}<span>${q.kind === "блокер" ? "<b>Блокер.</b> " : ""}${esc(q.text)} <em>— ${esc(q.to)}</em></span></li>` }).join("")}</ul>` : "";
  /* ссылка на другую задачу или карточку, документ, страницу */
  const idChip = id => SUB[id] ? `<button class="ref" data-sub="${id}" title="${esc(SUB[id].text)}">${esc(id)}</button>` : PROC[id] ? `<button class="ref" data-proc="${id}" title="${esc(PROC[id].text)}">${esc(id)}</button>` : TASK[id] ? `<button class="ref" data-task="${id}" title="${esc(TASK[id].text)}">${esc(id)}</button>` : `<code>${esc(id)}</code>`;
  function refItem(r) {
    if (/^https?:\/\//.test(r)) return `<a href="${esc(r)}" target="_blank" rel="noopener">${esc(r.replace(/^https?:\/\//, "").slice(0, 60))}</a>`;
    const d = D.docs[r.toLowerCase().split(" ")[0]];
    if (d) return d.screen && NOTE_OF[d.screen] ? `<button class="lnk" data-screen-doc="${esc(d.screen)}">${esc(d.title)}</button>` : `<a href="${esc(fileURL(d.file))}" target="_blank">${esc(d.title)}</a>`;
    if (PROC[r] || TASK[r]) return `${idChip(r)} ${esc((PROC[r] || TASK[r]).text)}`;
    return `<code>${esc(r)}</code>`;
  }
  const refList = items => items.length ? `<ul class="lnks">${items.map(x => `<li>${x}</li>`).join("")}</ul>` : "";
  /* шапка панели: заголовок, «!» — файлы проекта, откуда всё это, крестик; ниже — одна строка сведений */
  const head = (title, meta, back) => `<div class="snbar">${back ? '<button class="snback" data-snback aria-label="Назад">←</button>' : ""}<h3 title="${esc(title)}">${esc(title)}</h3><button class="srcb" data-src aria-label="Откуда это: файлы проекта" title="Откуда это: файлы проекта">!</button><button class="x" aria-label="Закрыть">×</button></div>${meta ? `<div class="tkmeta">${meta}</div>` : ""}`;
  function openTask(id, tab, fromExec) {
    if (tab != null) taskTab = tab;
    const back = fromExec || (exFrom && side.dataset.ctx === "task:" + id);
    const t = TASK[id], br = t.brief || {}, cards = D.cards.filter(c => c.task === id), subs = subsOf(id);
    let done = {}; try { done = JSON.parse(localStorage.getItem(dodKey(id)) || "{}") } catch (e) { }
    const ac = t.ac.map(([d, x], k) => `<label class="dod"><input type="checkbox" data-dod="${id}:${k}"${(done[k] != null ? done[k] : d) ? " checked" : ""}><span>${mdInline(x)}</span></label>`).join("");
    const links = refList([...(t.reqs.length ? [`<span class="lk">Требования БФТ</span> ${t.reqs.map(esc).join(", ")}`] : []), ...t.docs.map(refItem), ...t.refs.filter(r => !/^https?:\/\//.test(r)).map(refItem)]);
    const html = (t.why ? `<p class="tklead">${mdInline(t.why)}</p>` : "") + sec(`Подзадачи по зонам · ${subs.length}`, subs.length ? `<ul class="zl">${subs.map(z => `<li data-sub="${esc(z.id)}" tabindex="0"><b class="zt" style="--c:${teamC(z)}">${esc(z.zone)}</b><span>${esc(z.text)}<small>${esc(z.team === "?" && z.cand ? "Команда? " + z.cand : teamN(z))} · ${esc(z.id)} · ${esc(z.status)}</small></span></li>`).join("")}</ul>` : "") + sec("ASIS", mdHTML(br.ASIS || "")) + sec("GAP", mdHTML(br.GAP || "")) + sec("TOBE", mdHTML(br.TOBE || "")) +
      sec("HowToDemo", demoHTML(br.HowToDemo, [...t.docs, ...cards.flatMap(c => c.docs)])) + sec("Чеклист приемки", ac) + sec("Дополнительно", mdHTML(br["Дополнительно"] || "")) +
      sec("Как это работает", refList(cards.map(c => `${idChip(c.id)} ${esc(c.text)}`))) + sec("Вопросы", qList(qsOf([id, ...cards.map(c => c.id)]))) + sec("Ссылки", links);
    const tabs = `<nav class="snseg tktabs">${["Требования", "Исполнение"].map((n, i) => `<button data-tktab="${i}"${i === taskTab ? ' class="on"' : ""}>${n}</button>`).join("")}</nav>`;
    side.innerHTML = head(t.text, `<span class="pteam" style="--c:${teamC(t)}"><i></i>${esc(t.team === "?" && t.cand ? "Команда? " + t.cand : teamN(t))}</span>${leadOf(t) ? " · техлид " + esc(leadOf(t)) : ""}${t.prio ? ` · <span class="pr ${t.prio}">${PRIO[t.prio]}${oos(t) ? " · Out of scope" : ""}</span>` : ""} · ${esc(COLS[colOf(t.stage)].name)} · ${esc(id)} · ${esc(t.status)}`, back) + `<div class="snbody">${tabs}${taskTab ? execHTML(t) : html}</div>`;
    body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "task:" + id; side.dataset.note = "";
    if (!back) { exFrom = ""; howShow(id) }
  }

  /* карточка «Как это работает» — техническая задача: UserStory, JobStory, процесс и его схема BPMN,
     параметры, HowToDemo, вопросы, ссылки. Схема — текст mermaid из файла карточки; рисует mermaid
     из папки проекта (.blueprint/vendor), без сети. Нет mermaid — видно сам текст схемы. */
  const PNAME = { in: "Вход", ctl: "Управление", out: "Выход", mech: "Механизм" };
  let MM = null, mmN = 0;
  function mermaidLib() {
    if (window.mermaid) return Promise.resolve(window.mermaid);
    return MM || (MM = new Promise((ok, no) => {
      const sc = document.createElement("script"); sc.src = fileURL(D.mermaid || ""); sc.onerror = () => { MM = null; no(new Error("mermaid")) };
      sc.onload = () => { window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral", fontFamily: "Inter,-apple-system,Segoe UI,Roboto,Arial,sans-serif", themeVariables: { fontSize: "12.5px" }, flowchart: { useMaxWidth: true, htmlLabels: true, padding: 6, nodeSpacing: 28, rankSpacing: 34, wrappingWidth: 140 } }); ok(window.mermaid) };
      document.head.appendChild(sc);
    }));
  }
  function drawMermaid(box) {
    const code = box.querySelector("pre").textContent;
    mermaidLib().then(m => m.render(`mm${++mmN}`, code)).then(r => { if (box.isConnected) { box.innerHTML = r.svg; box.classList.add("ok") } })
      .catch(() => box.classList.add("raw"));
  }

  /* ---------- слой «Архитектура»: ADR и Системные требования — как реализуем работу ----------
     Данные — ключи adr и sysreq #map-data (появляются, когда в проекте есть документы «ADR»
     и «Системные требования»). Слой: варианты и явный выбор TO-BE, узкие места, компромиссы
     по трём осям, ADR-диаграмма AS-IS/TO-BE (mermaid из проекта), контракты с тремя вопросами
     системной аналитики, AS-IS/изменения и открытые вопросы. AR/SR объявлены рядом с D вверху файла. */
  const adrGrid = document.getElementById("adr");
  const AR_KIND = { "нагрузка": "нагрузка", "надёжность": "надёжность", "данные": "данные" };
  const th = cols => `<tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr>`;
  const tr = cols => `<tr>${cols.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`;
  const arTable = (title, rows, cols) => `<details class="cmpast arsec"${title === "Решение TO-BE" ? " open" : ""}><summary>${esc(title)} · ${rows.length}</summary>`
    + `<div class="tbl"><table><thead>${th(cols)}</thead><tbody>${rows.join("")}</tbody></table></div></details>`;
  function adrOpen(d) {
    const chosen = new Set((AR.decisions || []).map(x => x.id));
    const opt = o => tr([o.id + (chosen.has(o.id) ? " ✓" : ""), o.text, o.rel, o.speed, o.fit, chosen.has(o.id) ? "ВЫБРАН: " + (AR.decisions.find(d => d.id === o.id) || {}).why : o.whyNot]);
    const parts = [];
    if (AR.asis) parts.push(`<div class="arlead"><h4>AS-IS · ландшафт</h4><p>${esc(AR.asis)}</p></div>`);
    if ((AR.decisions || []).length) parts.push(arTable("Решение TO-BE", AR.decisions.map(d => tr([d.id + " ✓", d.contract, d.text, d.why])), ["ID", "Контракт", "Суть решения", "Обоснование"]));
    if ((AR.options || []).length) parts.push(arTable("Варианты", AR.options.map(opt), ["ID", "Вариант", "Надёжность", "Скорость", "Соответствие", "Почему нет"]));
    if ((AR.bottlenecks || []).length) parts.push(arTable("Узкие места", AR.bottlenecks.map(n => tr([n.id, n.text, AR_KIND[n.kind] || n.kind, n.load, n.risk, n.probe])), ["ID", "Узкое место", "Тип", "Нагрузка", "Риск", "Прощупывание"]));
    if ((AR.components || []).length) parts.push(arTable("Компоненты", AR.components.map(c => tr([c.id, c.name, c.ctx, c.kind === "человек" ? "—" : c4TeamName(c.team), c.kind, c.change, c.tasks.join(", ") || "—"])), ["ID", "Компонент", "Контекст", "Контур", "Тип", "Изменение", "Задачи"]));
    if (d && (AR.flows || []).length) parts.push(arTable("Потоки", AR.flows.map((f, i) => tr([i + 1, `${f.src} → ${f.dst}`, f.data, f.how, f.contract || "—"])), ["№", "От → К", "Данные", "Способ", "Контракт"]));
    if ((AR.compromises || []).length) parts.push(arTable("Компромиссы", AR.compromises.map(c => tr([c.id, c.text, c.rel, c.speed, c.fit, c.cost])), ["ID", "Компромисс", "Надёжность", "Скорость", "Соответствие", "Чем платим"]));
    const openQ = (D.questions || []).filter(q => q.open && /^(?:V|C)\d+/.test(q.where));
    return parts.join("") + (openQ.length ? `<div class="qdiv">Открытые вопросы ADR · ${openQ.length}</div><ul class="qul">${openQ.map(qItem).join("")}</ul>` : "");
  }
  function sysOpen() {
    const parts = [];
    if ((SR.contracts || []).length) parts.push(arTable("Контракты · три вопроса на каждый", SR.contracts.map(c => tr([c.id, c.contract, c.consumer, c.data, c.source, c.transform])), ["ID", "Контракт", "Потребитель", "Данные контракту", "Источник параметров", "Преобразования"]));
    if ((SR.asis || []).length) parts.push(arTable("AS-IS", SR.asis.map(x => tr([x.id, x.text, x.change])), ["ID", "Как устроено сейчас", "Что меняется"]));
    if ((SR.changes || []).length) parts.push(arTable("Изменения", SR.changes.map(x => tr([x.id, x.text, x.why])), ["ID", "Изменение", "Причина"]));
    if ((SR.questions || []).length) parts.push(arTable("Открытые вопросы", SR.questions.map(q => tr([q.id, q.to, q.text, q.answer || "—"])), ["ID", "Кому", "Вопрос", "Ответ"]));
    return parts.join("");
  }
  function adrBoard() {
    if (!adrGrid) return;
    if (!AR && !SR) { adrGrid.innerHTML = ""; return }
    const status = AR ? AR.status : SR.status;
    const diag = AR && AR.diagram ? `<div class="ardiag"><h4>ADR-диаграмма AS-IS / TO-BE</h4><div class="bpmnw"><pre>${esc(AR.diagram)}</pre></div><details class="mmcode"><summary>Текст схемы</summary><pre>${esc(AR.diagram)}</pre></details></div>` : "";
    const tab = (id, on, label, n) => `<button data-artab="${id}"${on ? ' class="on"' : ""}>${esc(label)}${n != null ? ` · ${n}` : ""}</button>`;
    const nA = AR ? (AR.options || []).length + (AR.bottlenecks || []).length + (AR.compromises || []).length : 0;
    const nS = SR ? (SR.contracts || []).length + (SR.asis || []).length + (SR.changes || []).length : 0;
    adrGrid.innerHTML = `<div class="arwrap"><div class="arhead"><span class="arst">${esc(status)}</span><h2>ADR и Системные требования</h2>
      <p>Как реализуем работу на карте: варианты и выбор TO-BE, узкие места и компромиссы; по каждому контракту — данные, источники, преобразования.</p>
      <nav class="arnav">${AR ? tab("adr", arCur === "adr", "ADR", nA) : ""}${SR ? tab("sys", arCur === "sys", "Системные требования", nS) : ""}</nav></div>
      ${arCur === "adr" ? c4Block() : ""}${diag}${arCur === "adr" && AR ? adrOpen() : ""}${arCur === "sys" && SR ? sysOpen() : ""}</div>`;
    const c4b = adrGrid.querySelector(".c4box"); if (c4b) c4Draw(c4b);
    const box = adrGrid.querySelector(".bpmnw:not(.c4box)");
    if (box) drawMermaid(box);
  }
  /* ---------- C4 L3: компоненты по контурам и контекстам, потоки данных ----------
     Данные — таблицы «Компоненты» и «Потоки» ADR. Контур (команда) — цветная рамка, контекст (система) —
     пунктирная рамка внутри; форма узла — тип, заливка — изменение; поток — номер и данные, асинхронный —
     пунктиром. Клик по компоненту — панель: задачи, входящие и исходящие потоки; клик по контуру
     в легенде — подсветить его компоненты. На стрелке — только номер потока: подписи с данными
     раздвигают схему вдвое; данные — нумерованным списком под схемой. */
  const C4 = AR && (AR.components || []).length ? AR : null;
  const C4_SHAPE = { "человек": ['(["', '"])'], "интерфейс": ['("', '")'], "сервис": ['["', '"]'], "хранилище": ['[("', '")]'], "очередь": ['>"', '"]'], "внешняя система": ['[["', '"]]'] };
  const C4_CHG = { "новый": "nw", "доработка": "md", "без изменений": "kp" };
  const C4_ASYNC = /асинхрон|событ|очеред/i;
  const c4Comp = id => C4.components.find(c => c.id === id);
  const c4TeamName = tm => tm === "?" ? "Контур не определён" : TEAM[tm] ? TEAM[tm].name : tm;
  const cssVar = v => { const m = String(v).match(/var\((--[\w-]+)\)/); return m ? getComputedStyle(document.documentElement).getPropertyValue(m[1]).trim() || "#888" : v };
  const c4Color = tm => cssVar(tm === "?" ? "var(--red)" : TEAM[tm] ? TEAM[tm].c : "#888");
  function c4Code() {
    const q = x => String(x).replace(/"/g, "'").replace(/[<>]/g, " ");
    const node = c => { const [a, b] = C4_SHAPE[c.kind] || C4_SHAPE["сервис"];
      return `${c.id}${a}${q(c.name)}<br/><small>${q(c.kind)}${c.tasks.length ? " · " + c.tasks.join(", ") : ""}</small>${b}:::${c.kind === "человек" ? "pp" : C4_CHG[c.change] || "kp"}` };
    const L = ["flowchart LR", "classDef nw fill:#e8f4ea,stroke:#2f6b2a,stroke-width:2px,color:#1d1d1b", "classDef md fill:#fff3e3,stroke:#d06a12,stroke-width:2px,stroke-dasharray:6 3,color:#1d1d1b",
      "classDef kp fill:#f4f2ee,stroke:#b9b3a8,color:#55524c", "classDef pp fill:#ffffff,stroke:#55524c,color:#1d1d1b"];
    C4.components.filter(c => c.kind === "человек").forEach(c => L.push("  " + node(c)));
    const teams = [...new Set(C4.components.filter(c => c.kind !== "человек").map(c => c.team))];
    teams.forEach((tm, ti) => {
      L.push(`  subgraph T${ti}["${q(c4TeamName(tm))}"]`);
      const ctxs = [...new Set(C4.components.filter(c => c.kind !== "человек" && c.team === tm).map(c => c.ctx))];
      ctxs.forEach((cx, xi) => {
        L.push(`    subgraph T${ti}X${xi}["${q(cx)}"]`);
        C4.components.filter(c => c.kind !== "человек" && c.team === tm && c.ctx === cx).forEach(c => L.push("      " + node(c)));
        L.push("    end", `    style T${ti}X${xi} fill:#fbfaf8,stroke:#cfcac0,stroke-dasharray:4 3,color:#55524c`);
      });
      const col = c4Color(tm);
      L.push("  end", `  style T${ti} fill:transparent,stroke:${col},stroke-width:2px,color:${col}`);
    });
    C4.flows.forEach((f, i) => L.push(`  ${f.src} ${C4_ASYNC.test(f.how) ? "-.->" : "-->"}|"${i + 1}"| ${f.dst}`));
    return L.join("\n");
  }
  function c4Draw(box) {
    mermaidLib().then(m => m.render(`c4${++mmN}`, c4Code())).then(r => {
      if (!box.isConnected) return;
      box.innerHTML = r.svg; box.classList.add("ok");
      box.querySelectorAll("g.node").forEach(g => { const m = (g.id || "").match(/flowchart-(M\d+)-\d+$/); if (m) { g.dataset.c4 = m[1]; g.setAttribute("tabindex", "0") } });
    }).catch(() => { box.classList.add("raw"); box.innerHTML = `<pre>${esc(c4Code())}</pre>` });
  }
  function c4Block() {
    if (!C4) return "";
    const teams = [...new Set(C4.components.filter(c => c.kind !== "человек").map(c => c.team))];
    const work = tm => C4.components.filter(c => c.team === tm && c.change !== "без изменений").length;
    return `<div class="c4"><h4>Компоненты и потоки данных · C4 L3</h4>
      <div class="c4lg"><span class="c4k nw">новый</span><span class="c4k md">доработка</span><span class="c4k kp">без изменений</span><span class="c4k as">асинхронно</span>
      <span class="c4sep"></span>${teams.map(tm => `<button class="c4t" data-c4team="${esc(tm)}" style="--c:${c4Color(tm)}"><i></i>${esc(c4TeamName(tm))}${work(tm) ? `<b>${work(tm)}</b>` : ""}</button>`).join("")}</div>
      <div class="bpmnw c4box"><pre>${esc(c4Code())}</pre></div>
      <ol class="c4list">${C4.flows.map((f, i) => `<li><b>${i + 1}</b><span>${esc(c4Comp(f.src) ? c4Comp(f.src).name : f.src)} → ${esc(c4Comp(f.dst) ? c4Comp(f.dst).name : f.dst)}<em>${esc(f.data)}</em><small>${esc(f.how)}${/^[—–-]?$/.test(f.contract || "") ? "" : " · " + esc(f.contract)}</small></span></li>`).join("")}</ol></div>`;
  }
  function c4Focus(tm) {
    const on = adrGrid.querySelector(`[data-c4team="${tm}"].on`) ? "" : tm;
    adrGrid.querySelectorAll("[data-c4team]").forEach(b => b.classList.toggle("on", b.dataset.c4team === on));
    adrGrid.querySelectorAll(".c4box g.node[data-c4]").forEach(g => g.classList.toggle("dim", !!on && c4Comp(g.dataset.c4).team !== on));
  }
  function openC4(id) {
    const c = c4Comp(id), name = x => { const k = c4Comp(x); return k ? k.name : x };
    const fl = (list, dir) => list.length ? `<ul class="c4fl">${list.map(f => `<li><b>${C4.flows.indexOf(f) + 1}</b><span>${esc(dir === "in" ? name(f.src) + " →" : "→ " + name(f.dst))} <em>${esc(f.data)}</em><small>${esc(f.how)}${f.contract && !/^[—–-]?$/.test(f.contract) ? " · " + esc(f.contract) : ""}</small></span></li>`).join("")}</ul>` : "";
    const tasks = c.tasks.length ? refList(c.tasks.map(t => `${idChip(t)} ${esc((TASK[t] || PROC[t] || {}).text || "")}`)) : "";
    side.innerHTML = head(c.name, `${c.kind === "человек" ? "" : `<span class="pteam" style="--c:${c4Color(c.team)}"><i></i>${esc(c4TeamName(c.team))}</span> · `}${esc(c.ctx)} · ${esc(c.kind)} · ${esc(c.change)} · ${esc(c.id)}`) + `<div class="snbody">
      ${sec("Задачи", tasks)}${sec("Входящие потоки", fl(C4.flows.filter(f => f.dst === id), "in"))}${sec("Исходящие потоки", fl(C4.flows.filter(f => f.src === id), "out"))}</div>`;
    execHide(); body.classList.remove("wide"); body.classList.add("open"); side.scrollTop = 0;
    side.dataset.ctx = "c4:" + id; side.dataset.note = "";
  }
  function setArTab(t) { arCur = t; adrBoard(); adrGrid.scrollIntoView({ block: "start" }) }

  function openProc(id) {
    execHide();
    const c = PROC[id], t = TASK[c.task], L = LAYER[c.layer], P = c.params || {};
    const row = k => (P[k] || []).length ? `<div class="pp"><span>${PNAME[k]}</span><ul>${P[k].map(it => `<li>${mdInline(it.t)}${it.r.length ? " " + it.r.map(idChip).join(" ") : ""}</li>`).join("")}</ul></div>` : "";
    const lnk = refList([t ? `<span class="lk">Задача</span> ${idChip(t.id)} ${esc(t.text)}` : "", ...c.docs.map(refItem), ...c.refs.map(refItem)].filter(Boolean));
    const proc = (c.lead ? `<p class="tklead">${mdInline(c.lead)}</p>` : "") + (c.bpmn ? `<div class="bpmnw"><pre>${esc(c.bpmn)}</pre></div><details class="mmcode"><summary>Текст схемы</summary><pre>${esc(c.bpmn)}</pre></details>` : "");
    side.innerHTML = head(c.text, `<span class="lay" style="--c:${L[2]}">${L[0]}</span> · <span class="pteam" style="--c:${teamC(c)}"><i></i>${esc(teamN(c))}</span> · ${esc(COLS[colOf(c.stage)].name)} · ${esc(id)} · ${esc(c.status)}`, !!t) + `<div class="snbody">
      ${sec("UserStory", c.us ? `<p>${mdInline(c.us)}</p>` : "")}
      ${sec("JobStory", (c.js || []).length ? `<ul class="js">${c.js.map(x => `<li>${mdInline(x)}</li>`).join("")}</ul>` : "")}
      ${sec("Процесс", proc)}${sec("Параметры", ["in", "ctl", "out", "mech"].map(row).join(""))}
      ${sec("HowToDemo", demoHTML(c.demo, [...c.docs, ...(t ? t.docs : [])]))}${sec("Вопросы", qList(qsOf([id, c.task])))}${sec("Ссылки", lnk)}</div>`;
    body.classList.add("wide", "open"); side.scrollTop = 0;
    side.dataset.ctx = "proc:" + id; side.dataset.note = "";
    const box = side.querySelector(".bpmnw"); if (box) drawMermaid(box);
  }
  function copyText(txt, btn) {
    const lab = btn.textContent, done = () => { btn.textContent = "Скопировано ✓"; setTimeout(() => btn.textContent = lab, 1600) };
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(done).catch(() => { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done() } catch (er) { } ta.remove() });
  }

  /* ---------- стыки: панель «Контроль стыковочных работ» — из документа «Стыки» проекта ---------- */
  function seamsPanel() {
    const S = D.seams || null;
    if (!S) return;
    const TEAM_NAME = id => { const t = (D.teams || []).find(x => x.id === id); return t ? esc(t.name) : esc(id) };
    const th = cols => `<tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr>`;
    const td = cols => `<tr>${cols.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`;
    const table = (title, rows, cols) => `<details class="cmpast"${title === "Участники" ? " open" : ""}><summary>${esc(title)} · ${rows.length}</summary>`
      + `<div class="tbl"><table><thead>${th(cols)}</thead><tbody>${rows.join("")}</tbody></table></div></details>`;
    const KIND = { "fe-be": "FE↔BE", "be-be": "BE↔BE", "be-infra": "BE↔Infra", "внешний": "внешний сервис" };
    const parts = [];
    parts.push(table("Участники", S.items.map(s => td([s.id, KIND[s.kind] || s.kind, `${TEAM_NAME(s.supplier)} → ${TEAM_NAME(s.consumer)}`, s.owner])),
      ["ID", "Стык", "Поставщик → потребитель", "Ответственный за контракт"]));
    if (S.deliveries.length) parts.push(table("Обязательства · кто → что → кому → срок",
      S.deliveries.map(d => td([d.id, TEAM_NAME(d.who), d.what, TEAM_NAME(d.to), d.when, d.where])),
      ["ID", "Кто", "Что", "Кому", "Срок", "Формат/место"]));
    if (S.contracts.length) parts.push(table("Контракты по слоям",
      S.contracts.map(c => td([c.seam, c.aspect, c.req])), ["Стык", "Аспект", "Требование к фиксации"]));
    if (S.checkpoints.length) parts.push(table("Контрольные точки",
      S.checkpoints.map(k => td([k.id, k.name, k.when, k.what, k.who])), ["ID", "Точка", "Когда", "Что проверяется", "Кто проводит"]));
    if (S.risks.length) parts.push(table("Риски", S.risks.map(r => td([r.id, r.text, r.effect, r.owner, r.mitigation])),
      ["ID", "Риск", "Следствие", "Владелец", "Митигация"]));
    const openQ = (D.questions || []).filter(q => q.open && /^S\d+/.test(q.where));
    panel(`Стыки · ${S.items.length}`, parts.join("") + (openQ.length
      ? `<div class="qdiv">Открытые вопросы стыков · ${openQ.length}</div><ul class="qul">${openQ.map(qItem).join("")}</ul>` : ""),
      "seams");
    side.scrollTop = 0;
  }

  /* ---------- инструкции, легенда, блокеры ---------- */
  /* правила лежат в самом проекте (.blueprint/rules) — открываются без сети */
  const ARTICLES = [["story_line.md", "#2f6b2a", "PS", "История через экраны", "Как устроен сюжет «было → шаги → стало» и откуда берутся экраны."],
    ["backlog_rules.md", "#d06a12", "BL", "Карта в проекте Backlog.md", "Задачи, карточки, процесс и схема BPMN, вопросы, команды ./backlog.py и ./blueprint.py, коды проверки."],
    ["screen_notes.md", "#6b3fd4", "UX", "Требования к экранам", "Документы экранов: Product, Design, Functions и картинки в backlog/assets/screens."]];
  function openGuide(kind) {
    if (kind === "help") openSide("Инструкции", "#555", "Как работать с картой", "", ARTICLES.map(([f, c, ic, t, d], i) => `<a class="art" href="${esc(fileURL(".blueprint/rules/" + f))}" target="_blank"><span class="ic" style="background:${c}">${ic}</span><span><b>${i + 1}. ${esc(t)}</b><span>${esc(d)}</span><em>.blueprint/rules/${f}</em></span></a>`).join(""));
    else if (kind === "blk") openSide("Блокеры", "var(--red)", `Блокеров: ${uniqBlk.length}`, "", D.questions.filter(q => q.open && q.kind === "блокер").map(q => `<div class="bcard" data-${TASK[q.where] ? "task" : PROC[q.where] ? "proc" : "where"}="${q.where}"><b>${esc(q.text)}</b><small>${esc(q.to)} · ${esc((TASK[q.where] || PROC[q.where] || {}).text || q.where)}</small></div>`).join(""));
    else openSide("Легенда", "#555", "Условные обозначения", "", `<div class="lg"><h4>Колонки</h4><div class="row"><i><span class="mh" style="position:static;padding:0!important;background:none"><span class="n">1</span></span></i><span>Шаг пути<small>слева направо — от подготовки до итога</small></span></div>
      <h4>Что видят</h4><div class="row"><i><span class="box" style="background:#fff;border:1px solid var(--line)"></span></i><span>Экран и фраза гостя или ресторана<small>по клику — все шаги этапа, экраны, вопросы</small></span></div>
      <h4>Что делаем — цвет команды</h4>${D.teams.filter(t => used[t.id]).map(t => `<div class="row"><i><span class="sw" style="background:${TEAM[t.id].c}"></span></i><span>${esc(t.name)}</span></div>`).join("")}${used["?"] ? `<div class="row"><i><span class="sw" style="border:1.5px dashed var(--red)"></span></i><span>Команда не определена</span></div>` : ""}
      <div class="row"><i><span class="qn">2</span></i><span>Открытые вопросы</span></div><div class="row"><i><span class="bl" style="margin:0">Блокер</span></i><span>Без решения задача не стартует</span></div>
      <h4>Как это работает</h4><div class="row"><i><span class="box" style="background:#f7ece3"></span></i><span>Employee Actions<small>сотрудник на виду у гостя: официант, оператор</small></span></div><div class="row"><i><span class="box" style="background:#e5f3f4"></span></i><span>Technology<small>интерфейсы, которые видит гость</small></span></div><div class="row"><i><span class="box" style="background:#e7edf8"></span></i><span>Backstage<small>за кадром</small></span></div><div class="row"><i><span class="box" style="background:#efecf6"></span></i><span>Support<small>общие ресурсы и внешние каналы</small></span></div>
      <div class="row"><i><span class="ln2"></span></i><span>Линия видимости</span></div><div class="row"><i><span class="ln3"></span></i><span>Линия внутреннего взаимодействия</span></div>
      <div class="row"><i><span class="dot inl"></span></i><span>На экране есть вопрос</span></div></div>`);
  }

  /* ---------- история по шагам ---------- */
  let showP = D.personas[0].id, showI = 0; const show = document.getElementById("show");
  function scene() {
    const steps = D.story.filter(s => s.persona === showP), s = steps[showI], p = D.personas.find(x => x.id === showP);
    const vis = s.screens.length ? `<div class="vis2">${s.screens.map(scrPic).join("")}</div>` : s.big ? `<div class="big">${esc(s.big)}</div>` : "<div></div>";
    show.querySelector(".stage").innerHTML = `<div class="scene">${vis}<div><div class="n">${esc(s.label)}</div><h2>${esc(s.title)}</h2><p class="say">${esc(s.text)}</p>${s.was ? `<div class="was"><b>Раньше</b>${esc(s.was)}</div>` : ""}</div></div>`;
    show.querySelector(".whos").innerHTML = D.personas.map(x => `<button data-p="${x.id}" class="${x.id === showP ? "on" : ""}">${esc(x.lane)}</button>`).join("");
    show.querySelector(".prev").disabled = showI === 0; show.querySelector(".next").disabled = showI === steps.length - 1;
  }
  const stepShow = d => { const n = D.story.filter(s => s.persona === showP).length; showI = Math.max(0, Math.min(n - 1, showI + d)); scene() };
  document.getElementById("play").addEventListener("click", () => { showP = D.personas[0].id; showI = 0; body.classList.add("showing"); scene() });
  show.addEventListener("click", e => { if (e.target.closest(".x")) body.classList.remove("showing"); else if (e.target.closest(".prev")) stepShow(-1); else if (e.target.closest(".next")) stepShow(1); else { const b = e.target.closest("[data-p]"); if (b) { showP = b.dataset.p; showI = 0; scene() } } });

  /* ---------- клики и клавиатура ---------- */
  document.addEventListener("click", e => {
    const t = e.target;
    if (!LB.hidden) { const b = t.closest("[data-lb]"); if (b) return zoom(lbI + +b.dataset.lb); if (!t.closest("img")) LB.hidden = true; return }
    if (t.closest(".side .x") || t.closest(".scrim")) return closeSide();
    const zm = t.closest("[data-zoom]"); if (zm) return zoom(+zm.dataset.zoom);
    const st = t.closest("[data-sntab]"); if (st) return openScreen(snCur, +st.dataset.sntab);
    const nt = t.closest("[data-snnote]"); if (nt) return openNote(+nt.dataset.snnote);
    if (t.closest("[data-snback]")) return goBack();
    const sb = t.closest("[data-sub]"); if (sb) return openSub(sb.dataset.sub);
    const et = t.closest("[data-extask]"); if (et) return execOpen(et.dataset.extask);
    if (t.closest("#burger")) return menu(!body.classList.contains("mopen"));
    const vw = t.closest("button[data-view]"); if (vw) return setView(vw.dataset.view);
    if (t.closest('[data-menu="close"]') || t.closest(".mscrim")) return menu(false);
    if (t.closest("[data-tf-clear]")) return teamFilter("");
    /* слой «Архитектура»: вкладки ADR / Системные требования, пункт меню */
    const at = t.closest("[data-artab]"); if (at) return setArTab(at.dataset.artab);
    const c4t = t.closest("[data-c4team]"); if (c4t) return c4Focus(c4t.dataset.c4team);
    const c4n = t.closest("[data-c4]"); if (c4n) return openC4(c4n.dataset.c4);
    if (t.closest("[data-adrmenu]")) { menu(false); if (AR || SR) return setView("adr") }
    /* слой «Релиз»: шаг, ворота, статусы, дорожки, команда для бэклога */
    const rgo = t.closest("[data-rlgo]"); if (rgo) return rlGo(rgo.dataset.rlgo);
    const rgt = t.closest("[data-rlgate]"); if (rgt) return openRelease(rlStepOfTrack(rgt.dataset.rlgate));
    const rcs = t.closest("[data-rlstep]"); if (rcs) return openRelease(rcs.dataset.rlstep);
    const rst = t.closest("[data-rlst]"); if (rst) { const id = side.dataset.ctx.split(":")[1]; if (id) return rlEdit(id, "status", rst.dataset.rlst) }
    const rta = t.closest("[data-rltrack-add]"); if (rta) { side.dataset.track = rta.dataset.rltrackAdd; side.querySelectorAll("[data-rltrack-add]").forEach(b => b.classList.toggle("on", b === rta)); return }
    const raa = t.closest("[data-rladd]"); if (raa) return rlAddStep();
    const rcn = t.closest("[data-rlcancel]"); if (rcn) return closeSide();
    const rcp = t.closest("[data-rlcopy]"); if (rcp) return copyText(rlCmd(), rcp);
    if (t.closest("[data-rlmenu]")) { menu(false); if (RL) return setView("rel") }
    if (t.closest("[data-rmmenu]")) { menu(false); if (RM) return setView("road") }
    if (t.closest("#menu [data-guide]") || t.closest("#menu .play")) menu(false);
    const sl = t.closest("[data-sl]"); if (sl) return slide(sl.closest(".pic"), +sl.dataset.sl);
    const dd = t.closest("[data-dot]"); if (dd) return slide(dd.closest(".fr").querySelector(".pic"), 0, +dd.dataset.dot);
    const sd = t.closest("[data-screen-doc]"); if (sd) return openScreen(sd.dataset.screenDoc, 0);
    const ua = t.closest("[data-entry]"); if (ua) { const sid = ua.dataset.entry; if (NOTE_OF[sid]) return openScreen(sid, 0); const s = D.seen.find(x => x.steps.some(st => st.screens.includes(sid))); if (s) return openSeen(s.key) }
    const tf = t.closest("[data-tf]");
    if (tf) { teamFilter(tf.classList.contains("on") ? "" : tf.dataset.tf); return menu(false) }
    const g = t.closest("[data-guide]"); if (g) return openGuide(g.dataset.guide);
    const pr = t.closest("[data-proc]"); if (pr) return openProc(pr.dataset.proc);
    const tk = t.closest("[data-task]"); if (tk) return openTask(tk.dataset.task, 0);
    /* кадр с требованиями: открыть экран, который сейчас виден в кадре */
    const scr = t.closest("[data-screens]");
    if (scr) { const ids = scr.dataset.screens.split(","), pic = scr.querySelector(".pic"), now = ids[+(pic && pic.dataset.i) || 0]; return openScreen(NOTE_OF[now] ? now : ids.find(id => NOTE_OF[id]), 0) }
    const sn = t.closest("[data-seen]"); if (sn) return openSeen(sn.dataset.seen);
  });
  document.addEventListener("change", e => {
    const c = e.target.closest && e.target.closest("[data-dod]"); if (!c) return;
    const [id, k] = c.dataset.dod.split(":"); let d = {}; try { d = JSON.parse(localStorage.getItem(dodKey(id)) || "{}") } catch (er) { }
    d[k] = c.checked; try { localStorage.setItem(dodKey(id), JSON.stringify(d)) } catch (er) { }
  });
  document.addEventListener("keydown", e => {
    if (body.classList.contains("showing")) { if (e.key === "ArrowRight") stepShow(1); else if (e.key === "ArrowLeft") stepShow(-1); else if (e.key === "Escape") body.classList.remove("showing"); return }
    if (!LB.hidden) { if (e.key === "Escape") LB.hidden = true; else if (gallery.length > 1 && e.key === "ArrowRight") zoom(lbI + 1); else if (gallery.length > 1 && e.key === "ArrowLeft") zoom(lbI - 1); return }
    if (e.key === "Escape") { if (body.classList.contains("mopen")) { menu(false); burger.focus() } else if (side.querySelector("[data-snback]")) goBack(); else closeSide() }
    if (e.key === "Enter" && e.target.matches && e.target.matches("[data-snnote]")) openNote(+e.target.dataset.snnote);
    if (e.key === "Enter" && e.target.matches && e.target.matches("[data-extask]")) execOpen(e.target.dataset.extask);
    if (e.key === "Enter" && e.target.matches && e.target.matches("[data-sub]")) openSub(e.target.dataset.sub);
    if (e.key === "Enter" && e.target.matches && e.target.matches("[data-c4]")) openC4(e.target.dataset.c4);
    if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches("[data-seen]")) { e.preventDefault(); openSeen(e.target.dataset.seen) }
  });
  /* ---------- замечания и уточнения → промпт для ИИ-агента ----------
     Замечание — правой кнопкой по любой секции. Уточнение — ответ PO на открытый вопрос карты или
     истории (иконка «?» справа сверху или вопрос в карточке). Как в bft-writer: всё хранится в браузере;
     пересобранная карта (новая ревизия) закрывает открытые замечания и ответы — они ушли в доработку. */
  const CM_KEY = `bp-cm-${D.epic}`, ANS_KEY = `bp-ans-${D.epic}`, CM_REV = CM_KEY + "-rev", CM_ITER = CM_KEY + "-iter";
  const load = k => { try { return JSON.parse(localStorage.getItem(k) || "[]") } catch (e) { return [] } };
  const store = (k, list) => { try { localStorage.setItem(k, JSON.stringify(list)) } catch (e) { } };
  const cmLoad = () => load(CM_KEY), cmSave = list => store(CM_KEY, list), cmOpen = () => cmLoad().filter(c => !c.closedAt);
  const ansOpen = () => load(ANS_KEY).filter(a => !a.closedAt && QK[a.key]);
  const ansOf = key => ansOpen().find(a => a.key === key);
  /* состояние вопроса: ждёт ответа, отвечен сейчас (в промпт), отвечен в проекте */
  const qState = q => ansOf(q.key) ? "done" : q.open === false ? "past" : "todo";
  (function syncRevision() {
    let seen = null; try { seen = localStorage.getItem(CM_REV) } catch (e) { return }
    if (seen && seen !== D.rev) {
      const now = new Date().toISOString(), iter = +(localStorage.getItem(CM_ITER) || 1); let n = 0;
      [CM_KEY, ANS_KEY].forEach(k => { const list = load(k); list.forEach(c => { if (!c.closedAt) { c.closedAt = now; c.iteration = iter; n++ } }); store(k, list) });
      if (n) try { localStorage.setItem(CM_ITER, String(iter + 1)) } catch (e) { }
    }
    try { localStorage.setItem(CM_REV, D.rev) } catch (e) { }
  })();
  const F = D.files || {}, mapDoc = F.map || "backlog/docs", storyDoc = F.story || "backlog/docs";
  /* что именно под курсором: ключ для метки, подпись для промпта, файл проекта Backlog.md, который править */
  function cmTarget(el) {
    if (el.closest("#side")) {
      const [kind, id] = (side.dataset.ctx || ":").split(":"), note = side.dataset.note || "";
      if (kind === "task") { const s = el.closest(".tk"); return { key: "task:" + id, label: `Задача ${id} «${TASK[id].text}»${s ? " · раздел " + s.querySelector("h4").textContent : side.querySelector(".exec") ? " · исполнение" : ""}`, file: TASK[id].file } }
      if (kind === "screen") { const li = el.closest("[data-snnote]"), tab = side.querySelector(".snseg .on");
        const what = note || (li ? `${tab ? tab.textContent : ""} · заметка «${li.querySelector("b").textContent}»` : "");
        return { key: "screen:" + id, label: `Экран ${id} «${SCR[id].title}»${what ? " · " + what : ""}`, file: (D.noteFiles || {})[id] || storyDoc } }
      if (kind === "proc") { const s = el.closest(".tk"); return { key: "proc:" + id, label: `Карточка ${id} «${PROC[id].text}»${s ? " · раздел " + s.querySelector("h4").textContent : ""}`, file: PROC[id].file } }
      if (kind === "seen") return { key: "seen:" + id, label: `Шаги истории «${id}»`, file: storyDoc };
      if (kind === "sub") return { key: "sub:" + id, label: `Подзадача ${id} «${SUB[id].text}»`, file: SUB[id].file };
      return { key: "map", label: "Карта", file: mapDoc };
    }
    const fr = el.closest(".fr"); if (fr) { const cap = fr.querySelector(".cap").textContent, ids = (fr.dataset.screens || "").split(",").filter(Boolean);
      fr.dataset.cmk = "fr:" + cap; return { key: "fr:" + cap, label: `Что видят · шаг «${cap}»`, file: storyDoc + (ids.length && (D.noteFiles || {})[NOTE_OF[ids[0]]] ? `, ${D.noteFiles[NOTE_OF[ids[0]]]}` : "") } }
    const wk = el.closest("[data-task]"); if (wk) { const id = wk.dataset.task; wk.dataset.cmk = "task:" + id; return { key: "task:" + id, label: `Задача ${id} «${TASK[id].text}»`, file: TASK[id].file } }
    const hw = el.closest("[data-proc]"); if (hw) { const id = hw.dataset.proc; hw.dataset.cmk = "proc:" + id; return { key: "proc:" + id, label: `Карточка ${id} «${PROC[id].text}»`, file: PROC[id].file } }
    const hd = el.closest(".hh,.mh:not(.corner)"); if (hd) { const name = hd.querySelector("b").textContent; hd.dataset.cmk = "stage:" + name; return { key: "stage:" + name, label: `Этап «${name}»`, file: storyDoc } }
    const row = el.closest(".hl,.ml"); if (row) { const name = row.textContent.trim().split("\n")[0].slice(0, 40); return { key: "row:" + name, label: `Ряд «${name}»`, file: row.closest(".hero") ? storyDoc : mapDoc } }
    return { key: "map", label: "Карта", file: mapDoc };
  }
  /* счётчики на иконках справа сверху: «?» — вопросов без ответа, облачко — замечаний */
  function cmPaint() {
    const open = cmOpen(), keys = new Set(open.map(c => c.key));
    document.querySelectorAll("[data-cmk]").forEach(x => x.classList.toggle("cm-has", keys.has(x.dataset.cmk)));
    const n = open.length, cmn = document.getElementById("cmn"), todo = QS.filter(q => qState(q) === "todo").length;
    cmn.hidden = !n; cmn.textContent = n;
    document.getElementById("icm").innerHTML = n ? `<b>${n}</b>` : "";
    document.getElementById("iq").innerHTML = todo ? `<b>${todo}</b>` : "";
  }
  /* поле замечания у курсора */
  let cmPop = null;
  function cmClose() { if (cmPop) { cmPop.remove(); cmPop = null } }
  function cmAsk(x, y, tgt, quote) {
    cmClose();
    const had = cmOpen().filter(c => c.key === tgt.key);
    cmPop = document.createElement("div"); cmPop.className = "cmpop";
    cmPop.innerHTML = `<div class="cmwhere">${esc(tgt.label)}</div>${quote ? `<div class="cmq">«${esc(quote)}»</div>` : ""}${had.map(c => `<div class="cmold">${esc(c.text)}</div>`).join("")}
      <textarea placeholder="Замечание для доработки (Ctrl+Enter — сохранить)"></textarea><div class="cmrow"><button class="cmsave">Сохранить</button><button class="cmcancel">Отмена</button></div>`;
    document.body.appendChild(cmPop);
    cmPop.style.left = Math.max(8, Math.min(x, innerWidth - cmPop.offsetWidth - 8)) + "px";
    cmPop.style.top = Math.max(8, Math.min(y, innerHeight - cmPop.offsetHeight - 8)) + "px";
    const ta = cmPop.querySelector("textarea"); ta.focus();
    const save = () => { const text = ta.value.trim(); if (!text) return cmClose(); const list = cmLoad(); list.push({ ts: new Date().toISOString(), ...tgt, quote, text }); cmSave(list); cmClose(); cmPaint(); if (side.dataset.ctx === "cm") cmPanel() };
    cmPop.querySelector(".cmsave").addEventListener("click", save);
    cmPop.querySelector(".cmcancel").addEventListener("click", cmClose);
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) save(); if (e.key === "Escape") { e.stopPropagation(); cmClose() } });
  }
  document.addEventListener("contextmenu", e => {
    if (e.shiftKey || e.target.closest(".cmpop,.zoombox,textarea,input")) return;
    if (!e.target.closest(".hero,.wrap,#side,.mstack")) return;
    e.preventDefault();
    const sel = String(window.getSelection() || "").trim().replace(/\s+/g, " ").slice(0, 200);
    cmAsk(e.clientX, e.clientY, cmTarget(e.target), sel);
  });
  document.addEventListener("mousedown", e => { if (cmPop && !e.target.closest(".cmpop")) cmClose(); if (srcPop && !e.target.closest(".srcpop,[data-src]")) srcClose() });
  /* где вопрос: задача, карточка, экран или шаг истории */
  const whereOf = q => TASK[q.where] ? `Задача ${q.where} «${TASK[q.where].text}»` : PROC[q.where] ? `Карточка ${q.where} «${PROC[q.where].text}»`
    : D.screens[q.where] ? `Экран ${q.where} · ${D.screens[q.where].contour}` : `Шаг истории ${q.where}`;
  function cmPrompt(list, answers) {
    answers = answers || [];
    if (!list.length && !answers.length) return "";
    const files = [...new Set([...list.flatMap(c => c.file.split(", ")), ...answers.flatMap(a => { const q = QK[a.key], w = TASK[q.where] || PROC[q.where]; return [q.doc === "map" ? mapDoc : storyDoc, ...(w ? [w.file] : [])] })])], proj = F.project || "<epic>-blueprint";
    const out = [`Доработай Service Blueprint «${D.title}» (${D.epic}) по замечаниям и ответам PO с карты. Данные — проект Backlog.md ${proj}.`, ""];
    if (list.length) out.push("Замечания:", ...list.map((c, i) => `${i + 1}. [${c.label}]${c.quote ? ` (по фрагменту «${c.quote}»)` : ""} ${c.text}\n   Файл: ${c.file}`), "");
    if (answers.length) out.push("Ответы на вопросы:", ...answers.map((a, i) => { const q = QK[a.key];
      return `${i + 1}. ${q.id} · ${q.to} · ${whereOf(q)}\n   Вопрос: ${q.text}\n   Ответ: ${a.text}\n   Файл: ${q.doc === "map" ? mapDoc : storyDoc} — таблица «Вопросы», колонка «Ответ»` }), "",
      "Ответ впиши в колонку «Ответ» строки вопроса; затем перепиши затронутые задачи, карточки и экраны: [УТОЧНИТЬ у …] по этому вопросу замени ответом.", "");
    return [...out,
      "Правь только названное и только через встроенный CLI: `./backlog.py task edit <ID> …`, `./backlog.py doc update <doc-id> --content …`; файлы руками не правь.",
      `Источник фактов — БФТ ${F.source || ""} и ответы PO выше; чего нет — [УТОЧНИТЬ у {кого}] и строка в «Вопросах» документа «Карта». Схему процесса не рисуй: она собирается из раздела «Процесс».`,
      `Файлы к правке: ${files.join(", ")}.`, "",
      "После правок — обязательно, из папки проекта:",
      "1. ./blueprint.py lint   (0 ошибок)",
      "2. ./blueprint.py build   (пересобрать страницу и архив — без этого замечания придут повторно)"].join("\n");
  }
  const promptNow = () => cmPrompt(cmOpen(), ansOpen());
  const copyBar = () => { const n = cmOpen().length, a = ansOpen().length;
    return n || a ? `<div class="cpbar"><span>В промпт: ${[n ? `замечаний ${n}` : "", a ? `ответов ${a}` : ""].filter(Boolean).join(", ")}</span><button class="tool pri" data-cmcopy>Скопировать промпт</button></div>` : "" };
  function panel(title, html, ctx) {
    execHide();
    side.innerHTML = `<div class="snbar"><h3>${title}</h3><button class="x" aria-label="Закрыть">×</button></div><div class="snbody">${html}</div>${copyBar()}`;
    side.dataset.ctx = ctx; side.dataset.note = ""; body.classList.remove("wide"); body.classList.add("open");
  }
  function cmPanel() {
    const list = cmOpen(), past = cmLoad().filter(c => c.closedAt);
    panel(`Замечания${list.length ? " · " + list.length : ""}`, (list.length ? `<ul class="cmlist">${list.map(c => `<li><small>${esc(c.label)}</small>${c.quote ? `<i>«${esc(c.quote)}»</i>` : ""}<span>${esc(c.text)}</span><button data-cmdel="${esc(c.ts)}" aria-label="Удалить замечание">×</button></li>`).join("")}</ul>`
      : '<p class="cmempty">Замечаний нет. Правой кнопкой мыши по кадру, этапу, задаче, карточке или заметке — оставить замечание.</p>') +
      (past.length ? `<details class="cmpast"><summary>Учтено в прошлых кругах · ${past.length}</summary><ul class="cmlist">${past.map(c => `<li><small>${esc(c.label)} · круг ${c.iteration || 1}</small><span>${esc(c.text)}</span></li>`).join("")}</ul></details>` : ""), "cm");
    side.scrollTop = 0;
  }
  /* «Уточнить»: открытые вопросы сверху, отвеченные сейчас — с ответом и ✓, отвеченные в проекте — свёрнуты */
  let qEdit = "";
  function qItem(q) {
    const st = qState(q), a = ansOf(q.key), ed = qEdit === q.key;
    return `<li class="qi ${st}${ed ? " ed" : ""}" data-qkey="${esc(q.key)}"><button class="qh" data-q="${esc(q.key)}">${st === "todo" ? '<i class="qd"></i>' : '<i class="ok">✓</i>'}<span><small title="${esc(whereOf(q))}">${esc(q.id)} · ${esc(q.to)} · ${esc(whereOf(q))}</small>${q.kind === "блокер" ? "<b>Блокер.</b> " : ""}${esc(q.text)}</span></button>
      ${ed ? `<div class="qa"><textarea placeholder="Ответ — уйдёт агенту в промпт (Ctrl+Enter — сохранить)">${esc(a ? a.text : "")}</textarea><div class="cmrow"><button class="cmsave" data-qsave>Сохранить</button><button class="cmcancel" data-qcancel>Отмена</button>${a ? '<button class="cmcancel" data-qdel>Убрать ответ</button>' : ""}</div></div>`
        : a ? `<p class="said">${esc(a.text)}</p>` : st === "past" ? `<p class="said past">${esc(q.answer)}</p>` : ""}</li>`;
  }
  function qPanel(key) {
    if (key != null) qEdit = key;
    const todo = QS.filter(q => qState(q) === "todo"), done = QS.filter(q => qState(q) === "done"), past = QS.filter(q => qState(q) === "past");
    const closed = load(ANS_KEY).filter(a => a.closedAt && QK[a.key]);
    panel(`Уточнить · ${todo.length}`, (todo.length ? `<ul class="qul">${todo.map(qItem).join("")}</ul>` : '<p class="cmempty">Открытых вопросов нет.</p>') +
      (done.length ? `<div class="qdiv">Отвечено сейчас · ${done.length}</div><ul class="qul">${done.map(qItem).join("")}</ul>` : "") +
      (past.length || closed.length ? `<details class="cmpast"${past.some(q => q.key === qEdit) ? " open" : ""}><summary>Отвечено в проекте · ${past.length}${closed.length ? `, в прошлых кругах · ${closed.length}` : ""}</summary><ul class="qul">${past.map(qItem).join("")}${closed.map(a => `<li class="qi past"><span class="qh"><i class="ok">✓</i><span><small>${esc(QK[a.key].id)} · круг ${a.iteration || 1}</small>${esc(QK[a.key].text)}</span></span><p class="said past">${esc(a.text)}</p></li>`).join("")}</ul></details>` : ""), "q");
    const ta = side.querySelector(".qa textarea");
    if (ta) { ta.focus(); ta.closest(".qi").scrollIntoView({ block: "nearest" }) } else side.scrollTop = 0;
  }
  function qSave(key, text) {
    const list = load(ANS_KEY).filter(a => !(a.key === key && !a.closedAt));
    if (text) list.push({ key, text, ts: new Date().toISOString() });
    store(ANS_KEY, list); qEdit = ""; cmPaint(); qPanel();
  }
  document.addEventListener("keydown", e => {
    const ta = e.target.closest && e.target.closest(".qa textarea"); if (!ta) return;
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) qSave(ta.closest(".qi").dataset.qkey, ta.value.trim());
    if (e.key === "Escape") { e.stopPropagation(); qEdit = ""; qPanel() }
  }, true);

  /* «!» в шапке панели: из каких файлов проекта собрано то, что открыто, — ссылки и пути */
  let srcPop = null;
  const srcClose = () => { if (srcPop) { srcPop.remove(); srcPop = null } };
  function srcFiles() {
    const [kind, id] = (side.dataset.ctx || ":").split(":"), out = [], add = (what, file, note) => file && !out.some(x => x[1] === file) && out.push([what, file, note || ""]);
    const docs = ds => ds.forEach(d => { const x = D.docs[String(d).toLowerCase().split(" ")[0]]; if (x) add("Документ", x.file) });
    const qdoc = ids => { const qs = qsOf(ids); if (qs.some(q => q.doc === "map")) add("Вопросы", mapDoc, "таблица «Вопросы»"); if (qs.some(q => q.doc === "story")) add("Вопросы", storyDoc, "таблица «Вопросы»") };
    if (kind === "proc") { const c = PROC[id]; add("Карточка", c.file, "UserStory, JobStory, Параметры, Процесс, HowToDemo; схема — раздел «BPMN», текст mermaid"); if (TASK[c.task]) add("Задача", TASK[c.task].file); docs(c.docs); qdoc([id, c.task]) }
    else if (kind === "sub") { const z = SUB[id]; add("Подзадача", z.file, "что сделать, исполнитель, критерии приемки"); if (TASK[z.task]) add("История", TASK[z.task].file); docs(z.docs); qdoc([id]) }
    else if (kind === "task") { const t = TASK[id]; add("Задача", t.file, "постановка, чеклист, исполнение — references и Implementation Notes"); D.cards.filter(c => c.task === id).forEach(c => add("Карточка", c.file)); docs(t.docs); qdoc([id, ...D.cards.filter(c => c.task === id).map(c => c.id)]) }
    else if (kind === "screen") { add("Требования к экрану", (D.noteFiles || {})[id]); (SCR[id] ? SCR[id].images : []).forEach(im => add("Картинка", im.src)); add("История", storyDoc, "таблица «Экраны»: из неё собраны картинки") }
    else if (kind === "seen") { const s = D.seen.find(x => x.key === id); add("История", storyDoc, "таблица «Шаги»"); (s ? s.steps.flatMap(st => st.screens) : []).forEach(x => add("Картинка", D.screens[x].img)); qdoc((s ? s.steps.flatMap(st => [st.id, ...st.screens]) : [])) }
    return out;
  }
  function srcOpen(btn) {
    srcClose();
    const files = srcFiles(); if (!files.length) return;
    srcPop = document.createElement("div"); srcPop.className = "srcpop";
    srcPop.innerHTML = `<div class="srch">Источник — файлы проекта ${esc(F.project || "")}</div>${files.map(([what, f, note]) => `<div class="srci"><small>${esc(what)}</small><a href="${esc(fileURL(f))}" target="_blank">${esc(f)}</a>${note ? `<em>${esc(note)}</em>` : ""}</div>`).join("")}<button class="tool" data-srccopy>Скопировать пути</button>`;
    document.body.appendChild(srcPop);
    const r = btn.getBoundingClientRect();
    srcPop.style.top = r.bottom + 6 + "px"; srcPop.style.left = Math.max(8, Math.min(r.right - srcPop.offsetWidth, innerWidth - srcPop.offsetWidth - 8)) + "px";
    srcPop.dataset.paths = files.map(x => x[1]).join("\n");
  }
  document.addEventListener("click", e => {
    const p = e.target.closest("[data-cmpanel]"); if (p) { menu(false); return cmPanel() }
    if (e.target.closest("[data-qpanel]")) { menu(false); return qPanel("") }
    if (e.target.closest("[data-seamspanel]")) { menu(false); return seamsPanel() }
    const sb = e.target.closest("[data-src]"); if (sb) return srcPop ? srcClose() : srcOpen(sb);
    const sc = e.target.closest("[data-srccopy]"); if (sc) return copyText(srcPop.dataset.paths, sc);
    const qq = e.target.closest("[data-q]"); if (qq) { const k = qq.dataset.q; return qPanel(qEdit === k && side.dataset.ctx === "q" ? "" : k) }
    if (e.target.closest("[data-qsave]")) { const li = e.target.closest(".qi"); return qSave(li.dataset.qkey, li.querySelector("textarea").value.trim()) }
    if (e.target.closest("[data-qdel]")) return qSave(e.target.closest(".qi").dataset.qkey, "");
    if (e.target.closest("[data-qcancel]")) { qEdit = ""; return qPanel() }
    const tt = e.target.closest("[data-tktab]"); if (tt) return openTask(side.dataset.ctx.split(":")[1], +tt.dataset.tktab);
    const xc = e.target.closest("[data-excopy]"); if (xc) return copyText(execCmd(xc.dataset.excopy), xc);
    const d = e.target.closest("[data-cmdel]"); if (d) { cmSave(cmLoad().filter(c => c.ts !== d.dataset.cmdel)); cmPaint(); return cmPanel() }
    const c = e.target.closest("[data-cmcopy]"); if (c) return copyText(promptNow(), c);
  });
  /* метки на элементах с замечаниями: ключи проставляются заранее */
  hero.querySelectorAll(".fr").forEach(f => f.dataset.cmk = "fr:" + f.querySelector(".cap").textContent);
  grid.querySelectorAll("[data-task]").forEach(x => x.dataset.cmk = "task:" + x.dataset.task);
  grid.querySelectorAll("[data-proc]").forEach(x => x.dataset.cmk = "proc:" + x.dataset.proc);
  document.querySelectorAll(".hh,.mh:not(.corner)").forEach(x => x.dataset.cmk = "stage:" + x.querySelector("b").textContent);
  cmPaint();

  arInit(); /* телефон: секция «Архитектура» — после объявления всех хелперов */
  window.BPMAP = { setView, cmPanel, qPanel, qSave, cmTarget, cmPrompt, promptNow, execCmd, openProc, openTask, openSeen, openScreen, openNote, zoom, srcFiles, openRelease, rlBoard, rlCmd };
})();

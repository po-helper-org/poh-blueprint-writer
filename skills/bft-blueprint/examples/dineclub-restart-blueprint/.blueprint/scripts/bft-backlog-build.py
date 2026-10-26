

#!/usr/bin/env python3
"""bft-backlog-build — страница Service Blueprint и архив проекта из проекта Backlog.md.

Детерминированно, без ИИ:
1. проверка проекта (`bft-backlog-lint.py`); с ошибками ничего не собирается — код 1;
2. схема BPMN карточек «Как это работает» — mermaid из «Процесса» (блок `### BPMN` в файле карточки);
   картинки экранов — `backlog/assets/screens/<ID>.svg` из таблицы «Экраны» «Истории»;
3. `<epic>-map.html` — страница без CDN: «Что видят», «Что делаем», «Как это работает». Текст на ней —
   только из файлов проекта (BL032 — иначе не соберётся); картинки экранов и mermaid
   (`.blueprint/vendor/`) она берёт из папки проекта по относительному пути;
4. папка проекта автономна: `.blueprint/` (эти скрипты и правила), `./backlog.py` — встроенный CLI
   Backlog.md, `./blueprint.py` — проверка и сборка, CLAUDE.md, AGENTS.md, GEMINI.md, `.claude/settings.json`
   (`bft-backlog-init.py`, `install()`); сборка их обновляет;
5. `<epic>-blueprint.zip` — эта папка целиком и страница `blueprint.html`. Распаковал — отдаёшь любому
   харнессу: `./backlog.py …`, `./blueprint.py build`, ничего ставить не нужно, кроме python3.

Использование:
    python3 bft-backlog-build.py <проект> [--out-dir КАТАЛОГ] [--source БФТ.md | --no-source] [--check] [--no-zip]

--check — ничего не пишет: устаревшая схема BPMN, картинка экрана, скрипты или инструкции проекта — ошибка
(для CI и самотеста).
По умолчанию файлы ложатся рядом с папкой проекта.
"""

from __future__ import annotations

import argparse

import hashlib

import html

import importlib.util

import json

import os

import re

import sys

import zipfile

from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))

import bft_backlog as bl  # noqa: E402

import bft_story as bs  # noqa: E402

import bft_screens as bsn  # noqa: E402

import bft_mock as bm  # noqa: E402

def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

lint = _load("bl_lint", "bft-backlog-lint.py")

kit = _load("bl_init", "bft-backlog-init.py")

ZIP_DATE = (1980, 1, 1, 0, 0, 0)

PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="generator" content="bft-blueprint map">
<title>{title_tag}</title>
<style>
{css}</style></head>
<body>
<h1 class="ptitle">{h1}</h1>
<div class="fab"><button class="burger" id="burger" aria-label="Меню карты" aria-expanded="false" aria-controls="menu"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 4h11M2.5 8h11M2.5 12h11"/></svg><span class="bdot" id="bdot"></span></button><nav class="views" aria-label="Слой карты"><button data-view="see" class="on">Что видят</button><button data-view="do">Что делаем</button><button data-view="how">Как это работает</button>{adr_btn}{rel_btn}</nav><span id="fchip"></span></div>
<div class="tr"><button class="ib iq" data-qpanel title="Уточнить: ответить на открытые вопросы" aria-label="Уточнить"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M6.2 6.1a1.9 1.9 0 1 1 2.6 1.8c-.5.2-.8.6-.8 1.1v.6"/><circle cx="8" cy="11.6" r=".4"/></svg><span id="iq"></span></button><button class="ib icm" data-cmpanel title="Замечания" aria-label="Замечания"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 3.5h11v7.5H7l-3 2.5V11H2.5z"/></svg><span id="icm"></span></button></div>
<div class="mscrim"></div>
<nav class="menu" id="menu" aria-label="Меню карты"><div class="mtop"><div><span class="draft{status_cls}">{status}</span><h1>{h1}</h1></div><button class="x" data-menu="close" aria-label="Закрыть">×</button></div>
<button class="play" id="play">▶ Рассказать историю</button>
<div class="mlist"><span id="blk"></span>
<button class="mi" data-guide="help"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 3h4.5A1.5 1.5 0 0 1 8 4.5V14a1.5 1.5 0 0 0-1.5-1.5H2zM14 3H9.5A1.5 1.5 0 0 0 8 4.5V14a1.5 1.5 0 0 1 1.5-1.5H14z"/></svg>Инструкции</button>
<button class="mi" data-guide="legend"><svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="2.5" width="4" height="4" rx="1"/><path d="M8.5 4.5H14"/><circle cx="4" cy="11.5" r="2"/><path d="M8.5 11.5H14"/></svg>Легенда</button>{adr_menu}{rel_menu}
<button class="mi" data-qpanel><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M6.2 6.1a1.9 1.9 0 1 1 2.6 1.8c-.5.2-.8.6-.8 1.1v.6"/></svg>Уточнить</button>
<button class="mi" data-seamspanel hidden><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 4h5v8H2zM9 4h5v8H9z" fill="none"/><path d="M7 8h2"/></svg>Стыки<b class="cnt" id="seamcnt" hidden></b></button>
<button class="mi" data-cmpanel><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 3.5h11v7.5H7l-3 2.5V11H2.5z"/></svg>Замечания<b class="cnt cmn" id="cmn" hidden></b></button></div>
<div class="mlab">Команды — показать работу одной</div><div class="teams" id="teams"></div></nav>
<section class="hero" id="hero" aria-label="Что видят люди — путь слева направо"></section>
<div class="wrap" id="work"><div id="grid"></div></div>
<section class="adrscr" id="adr" aria-label="ADR и Системные требования — как реализуем работу"></section>
<section class="rel" id="rel" aria-label="План релиза — дорожки DEV, STAGE, PROD"></section>
<div class="mstack" id="mstack"></div>
<div class="scrim"></div><aside class="execp" id="exec" aria-label="Исполнение: задачи команд по экрану"></aside><aside class="side" id="side" aria-label="Подробности"></aside><div class="zoombox" id="lb" hidden></div>
<div class="show" id="show" role="dialog" aria-label="История по шагам"><div class="sbar"><div class="whos"></div><button class="x" aria-label="Закрыть">×</button></div>
<div class="stage"></div><div class="snav"><button class="prev">← Назад</button><button class="next">Дальше →</button></div></div>
<script type="application/json" id="map-data">{data}</script>
<script>
{kit}</script>
<script>
{js}</script>
</body></html>
"""

def step_json(s: bs.Step) -> dict:
    return {"id": s.id, "title": s.title, "text": s.text, "was": s.was, "screens": s.screens, "source": s.source}

def model(pr: bl.Project, base: str = "") -> dict:
    """Данные страницы — только из файлов проекта (проверяет `provenance`). `base` — путь от страницы
    до папки проекта: картинки экранов и mermaid страница берёт оттуда, а не из себя."""
    st = pr.story
    bdir = pr.bdir.relative_to(pr.root).as_posix()
    cols = [s.id for s in st.stages] + [bl.FINAL]
    names = {p.id: p.name for p in st.personas}

    # «Что видят»: по карточке на персонажа и этап; итог — карточки «стало»
    seen = []
    for p in st.personas:
        for ci, sid in enumerate(cols):
            if sid == bl.FINAL:
                fin = next((s for s in st.steps_of(p.id) if s.kind == "final"), None)
                if fin:
                    big = p.after.split("·")[0].strip()
                    seen.append({"key": f"{p.id}:{sid}", "persona": p.id, "col": ci, "final": True,
                                 "big": "" if big in bs.EMPTY else big, "title": fin.title, "steps": [step_json(fin)]})
                continue
            steps = [s for s in st.steps_of(p.id) if s.kind == "step" and s.stage_from == sid]
            if steps:
                seen.append({"key": f"{p.id}:{sid}", "persona": p.id, "col": ci, "final": False,
                             "steps": [step_json(s) for s in steps]})
    story = []
    stage_name = {s.id: s.name for s in st.stages}
    for p in st.personas:
        n = 0
        for s in st.steps_of(p.id):
            if s.kind in ("step", "band"):
                n += 1
                label = f"Шаг {n} · {stage_name.get(s.stage_from, '')}"
            else:
                label = "Знакомьтесь" if s.kind == "intro" else "И с тех пор"
            big = (p.before if s.kind == "intro" else p.after if s.kind == "final" else "").split("·")[0].strip()
            story.append({"persona": p.id, "label": label, "title": s.title, "text": s.text, "was": s.was,
                          "screens": s.screens, "big": "" if big in bs.EMPTY else big})

    doc_of = {d.path: k for k, d in pr.docs.items()}
    doc_screen = {doc_of[d.path]: sid for sid, d in pr.screens.items()}
    docs = {k: {"title": d.title, "file": d.rel, "screen": doc_screen.get(k, "")} for k, d in pr.docs.items()}
    common = lambda t: {"id": t.id, "stage": t.stage, "team": t.team, "text": t.title, "status": t.status,  # noqa: E731
                        "refs": [str(x) for x in t.refs], "docs": [str(x) for x in t.docs], "file": t.rel}
    tasks = [{**common(t), "cand": t.cand, "why": t.why, "reqs": t.reqs, "kind": t.kind, "notes": t.notes,
              "brief": {k: v[1] for k, v in t.sections.items()}, "ac": [[d, x] for d, x in t.ac]} for t in pr.tasks]
    cards = [{**common(c), "task": c.parent, "layer": c.layer, "lead": c.lead, "us": c.user_story, "js": c.job_stories, "bpmn": re.sub(r"^```mermaid\n|\n?```$", "", c.mermaid.strip()),
              "params": {k: [{"t": it.text, "r": it.refs} for it in v] for k, v in c.params.items()},
              "demo": c.sections.get("HowToDemo", (0, ""))[1]} for c in pr.cards]
    subs = [{**common(z), "task": z.parent, "zone": z.zone, "cand": z.cand, "lead": z.lead,
             "ac": [[d, x] for d, x in z.ac]} for z in pr.subtasks]
    return {
        "epic": pr.meta.get("epic_slug", ""), "title": pr.title, "prefix": pr.prefix,
        "stages": [{"id": s.id, "name": s.name, "when": s.when} for s in st.stages],
        "personas": [{"id": p.id, "name": names[p.id], "lane": p.lane} for p in st.personas],
        "seen": seen, "story": story,
        "screens": {sc.id: {"contour": sc.contour, "view": sc.view, "img": f"{bdir}/{bm.image_of(pr.bdir, sc.id)}"} for sc in st.screens},
        "notes": {sid: bsn.page_md(doc, pr.root) for sid, doc in sorted(pr.screens.items())},
        "noteFiles": {sid: doc.rel for sid, doc in sorted(pr.screens.items())},
        "docs": docs,
        "storyQuestions": [{"id": q.id, "to": q.to, "text": q.text, "where": q.where, "open": q.open, "answer": q.answer} for q in st.questions],
        "teams": [{"id": t.id, "name": t.name, **({"lead": t.lead} if t.lead else {})} for t in pr.teams],
        "tasks": tasks, "cards": cards, "subs": subs,
        "links": [{"src": a, "dst": b, "what": w} for a, b, w in pr.links()],
        "questions": [{"id": q.id, "to": q.to, "text": q.text, "where": q.where, "kind": q.kind,
                       "open": q.open, "answer": q.answer} for q in pr.questions],
        **({"adr": {"status": pr.adr.meta.get("status", ""), "version": pr.adr.meta.get("version", ""),
                    "options": [{"id": o.id, "text": o.text, "rel": o.reliability, "speed": o.speed,
                                 "fit": o.fit, "whyNot": o.why_not} for o in pr.adr.options],
                    "decisions": [{"id": d.id, "contract": d.contract, "text": d.text, "why": d.why} for d in pr.adr.decisions],
                    "bottlenecks": [{"id": n.id, "text": n.text, "kind": n.kind, "load": n.load,
                                     "risk": n.risk, "probe": n.probe} for n in pr.adr.bottlenecks],
                    "compromises": [{"id": c.id, "text": c.text, "rel": c.reliability, "speed": c.speed,
                                     "fit": c.fit, "cost": c.cost} for c in pr.adr.compromises],
                    "components": [{"id": c.id, "name": c.name, "ctx": c.context, "team": c.team, "kind": c.kind,
                                    "change": c.change, "tasks": c.tasks} for c in pr.adr.components],
                    "flows": [{"src": f.src, "dst": f.dst, "data": f.data, "how": f.how, "contract": f.contract} for f in pr.adr.flows],
                    "asis": pr.adr.asis, "context": pr.adr.context,
                    "diagram": re.sub(r"^```mermaid\n|\n?```$", "", pr.adr.diagram.strip()),
                    "file": pr.adr_doc.rel}}
           if pr.adr is not None and pr.adr_doc is not None else {}),
        **({"sysreq": {"status": pr.sysreq.meta.get("status", ""), "version": pr.sysreq.meta.get("version", ""),
                       "contracts": [{"id": c.id, "contract": c.contract, "consumer": c.consumer, "data": c.data,
                                      "source": c.source, "transform": c.transform} for c in pr.sysreq.contracts],
                       "asis": [{"id": x.id, "text": x.text, "change": x.change} for x in pr.sysreq.asis],
                       "changes": [{"id": x.id, "text": x.text, "why": x.why} for x in pr.sysreq.changes],
                       "questions": [{"id": q.id, "to": q.to, "text": q.text, "open": q.open, "answer": q.answer} for q in pr.sysreq.questions],
                       "file": pr.sysreq_doc.rel}}
           if pr.sysreq is not None and pr.sysreq_doc is not None else {}),
        **({"seams": {"status": pr.seams.meta.get("status", ""), "version": pr.seams.meta.get("version", ""),
                      "items": [{"id": s.id, "kind": s.kind, "supplier": s.supplier, "consumer": s.consumer,
                                 "owner": s.owner} for s in pr.seams.seams],
                      "deliveries": [{"id": d.id, "who": d.who, "what": d.what, "to": d.to, "when": d.when,
                                      "where": d.where, "seam": d.seam} for d in pr.seams.deliveries],
                      "contracts": [{"seam": c.seam, "aspect": c.aspect, "req": c.req} for c in pr.seams.contracts],
                      "checkpoints": [{"id": k.id, "name": k.name, "when": k.when, "what": k.what,
                                       "who": k.who} for k in pr.seams.checkpoints],
                      "risks": [{"id": r.id, "text": r.text, "effect": r.effect, "owner": r.owner,
                                 "mitigation": r.mitigation} for r in pr.seams.risks],
                      "file": pr.seams_doc.rel}}
           if pr.seams is not None and pr.seams_doc is not None else {}),
        **({"release": {"status": pr.release.meta.get("status", ""), "version": pr.release.meta.get("version", ""),
                        "doc": pr.release_doc.id,
                        "tracks": [{"id": t, "title": bl.RELEASE_TRACK_TITLE[t]} for t in bl.RELEASE_TRACKS],
                        "steps": [{"id": s.id, "track": s.track, "action": s.action, "owner": s.owner,
                                   "kind": s.kind, "deps": s.deps, "status": s.status, "ready": s.ready,
                                   "file": pr.release_doc.rel} for s in pr.release.steps],
                        "gates": [{"frm": g.frm, "to": bl.RELEASE_TRACKS[bl.RELEASE_TRACKS.index(g.frm) + 1],
                                   "who": g.who, "criterion": g.criterion} for g in pr.release.gates]}}
           if pr.release is not None and pr.release_doc is not None else {}),
        "files": {"map": pr.map_doc.rel, "story": pr.story_doc.rel, "source": pr.meta.get("source_doc", ""),
                  "project": f"{pr.meta.get('epic_slug', 'epic')}-blueprint"},
        "base": base, "mermaid": ".blueprint/vendor/mermaid.min.js",
    }

# ключи, которые страница считает сама: подписи шагов, ключи кадров, пути — их нет в тексте проекта
DERIVED = {"key", "label", "rev", "base", "mermaid", "file", "files", "img", "noteFiles", "col", "final", "open", "kind"}

BY_ID = {"notes", "noteFiles", "screens", "docs", "files"}   # словари «ID → значение»: ключ — не имя поля

def provenance(m: dict, pr: bl.Project) -> list[str]:
    """Каждая строка данных страницы есть в файлах проекта Backlog.md — дословно, построчно.
    Путь (файл, картинка) — существует. Возвращает строки, которых в проекте нет: так сборка
    не может показать на карте то, чего в бэклоге не написано."""
    corpus = "\n".join(f.read_text(encoding="utf-8") for f in sorted(pr.bdir.rglob("*.md")))
    norm = lambda s: " ".join(s.split())  # noqa: E731
    text = norm(corpus)
    # значение «Параметров» страница показывает без ссылок (BP-x.y): сверяем и с текстом без них
    refs = re.compile(rf"\s*\(\s*(?:[←→]\s*)?{re.escape(pr.prefix)}-\d+(?:\.\d+)*(?:\s*,\s*(?:[←→]\s*)?{re.escape(pr.prefix)}-\d+(?:\.\d+)*)*\s*\)")
    bare = norm(refs.sub("", corpus.replace("**", "")))
    miss: list[str] = []

    def walk(v, key: str) -> None:
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, "#" + key if key in BY_ID else k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and key.lstrip("#") not in DERIVED:
            # кандидаты «Витрина или UnitB» склеивает сама сборка — в проекте каждое имя по отдельности
            for line in (v.split(" или ") if key == "cand" else v.split("\n")):
                ln = norm(line)
                im = bsn.IMG_RE.match(ln)
                if im and not re.match(r"^(https?:|data:)", im.group(2)):
                    if not (pr.root / im.group(2)).is_file():
                        miss.append(f"картинка {im.group(2)}")
                    continue
                if len(ln) >= 3 and ln not in text and ln not in bare:
                    miss.append(ln)
    walk(m, "")
    paths = [x["file"] for x in m["tasks"] + m["cards"] + m["subs"]] + [d["file"] for d in m["docs"].values()] + [s["img"] for s in m["screens"].values()]
    miss += [f"файл {p}" for p in paths if not (pr.root / p).is_file()]
    return miss

def render(pr: bl.Project, base: str = "") -> str:
    m = model(pr, base)
    # ревизия страницы: пересобранная карта закрывает замечания прошлого круга
    m["rev"] = hashlib.sha1(json.dumps(m, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    data = json.dumps(m, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    status = pr.meta.get("status", "")
    has_adr = m.get("adr") is not None or m.get("sysreq") is not None
    adr_btn = '<button data-view="adr">Архитектура</button>' if has_adr else ""
    adr_menu = ('<button class="mi" data-adrmenu><svg viewBox="0 0 16 16" aria-hidden="true">'
                '<path d="M2 13.5L8 2l6 11.5M4.6 9h6.8" fill="none"/></svg>ADR и системные требования</button>') if has_adr else ""
    has_rel = pr.release is not None and pr.release_doc is not None
    rel_btn = '<button data-view="rel">Релиз</button>' if has_rel else ""
    rel_menu = ('<button class="mi" data-rlmenu><svg viewBox="0 0 16 16" aria-hidden="true">'
                '<path d="M2.5 13.5v-6M6.5 13.5V2.5M10.5 13.5v-8M14.5 13.5v-4"/></svg>План релиза</button>') if has_rel else ""
    return PAGE.format(
        title_tag=html.escape(f"Карта · {pr.meta.get('epic_slug', '')}"), h1=html.escape(pr.title),
        status=html.escape(status), status_cls=" ok" if status.lower() == "согласован" else "",
        adr_btn=adr_btn, adr_menu=adr_menu, rel_btn=rel_btn, rel_menu=rel_menu,
        css=(HERE / "map_page.css").read_text(encoding="utf-8"),
        kit=(HERE / "page_kit.js").read_text(encoding="utf-8"),
        js=(HERE / "map_page.js").read_text(encoding="utf-8"), data=data)

def build_zip(pr: bl.Project, page: str, out: Path) -> int:
    """Архив без дат и прав системы: тот же проект — тот же zip байт в байт."""
    name = f"{pr.meta.get('epic_slug', 'epic')}-blueprint"
    entries: dict[str, bytes] = {}
    for f in sorted(pr.root.rglob("*")):
        rel = f.relative_to(pr.root).as_posix()
        if not f.is_file() or rel.startswith(".git/") or "__pycache__" in rel or "/" not in rel and f.suffix in (".html", ".zip"):
            continue
        entries[rel] = f.read_bytes()
    entries["blueprint.html"] = page.encode("utf-8")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(entries):
            info = zipfile.ZipInfo(f"{name}/{rel}", date_time=ZIP_DATE)
            info.external_attr = (0o755 if rel.endswith(".py") or rel in ("backlog.py", "blueprint.py") else 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, entries[rel])
    return len(entries)

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", type=Path)
    ap.add_argument("--out-dir", type=Path, help="куда писать .html и .zip (по умолчанию — рядом с папкой проекта)")
    ap.add_argument("--source", help="путь к БФТ (по умолчанию — `source_doc` паспорта)")
    ap.add_argument("--no-source", action="store_true", help="не сверять с БФТ")
    ap.add_argument("--check", action="store_true", help="ничего не писать: проверка, устаревшие схемы и скрипты")
    ap.add_argument("--no-zip", action="store_true", help="только страница")
    args = ap.parse_args()
    root = args.project.resolve()
    pr = lint.run(root, args.source, args.no_source)
    stale = [i for i in pr.issues if i.code == "BL022"]
    if args.check and stale:
        for i in stale:
            i.level = "ERROR"
    if pr.errors:
        lint.report(pr, False, "backlog-build")
        print("backlog-build: проект с ошибками не собирается — исправь и запусти снова", file=sys.stderr)
        return 1
    meta = (pr.title, pr.meta.get("epic_slug", ""), pr.meta.get("source_doc", ""))
    if args.check:
        rc = lint.report(pr, False, "backlog-build")
        stale_kit = kit.install(root, *meta, write=False)
        for rel in stale_kit:
            print(f"{root / rel}:1: ERROR BL029 файл автономного проекта устарел — ./blueprint.py build обновит")
        stale_img = bm.sync(pr.bdir, pr.story.screens, write=False)
        for sid in stale_img:
            print(f"{pr.bdir / bm.ASSETS / (sid + '.svg')}:1: ERROR BL031 картинка экрана {sid} не совпадает с «Историей» — ./blueprint.py build перепишет")
        miss = [] if stale_img else provenance(model(pr), pr)
        for x in miss:
            print(f"{root}:1: ERROR BL032 на странице было бы то, чего нет в проекте: {x[:120]}")
        return 1 if rc or stale_kit or stale_img or miss else 0
    synced = bl.sync_schema(pr, write=True)
    if synced:
        print(f"backlog-build: схема BPMN пересобрана из «Процесса» — {', '.join(c.id for c in synced)}")
        pr = lint.run(root, args.source, args.no_source)
    imgs = bm.sync(pr.bdir, pr.story.screens, write=True)
    if imgs:
        print(f"backlog-build: картинки экранов пересобраны из «Истории» — {', '.join(imgs)}")
    lint.report(pr, False, "backlog-build")
    miss = provenance(model(pr), pr)
    if miss:
        for x in miss:
            print(f"{root}:1: ERROR BL032 на странице было бы то, чего нет в проекте: {x[:120]}")
        print("backlog-build: данные страницы должны браться только из проекта — исправь сборку или проект", file=sys.stderr)
        return 1
    kit_changed = kit.install(root, *meta)
    if kit_changed:
        print(f"backlog-build: обновлены скрипты, правила и инструкции проекта — {len(kit_changed)} файлов")
    out_dir = (args.out_dir or root.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    epic = pr.meta.get("epic_slug", "epic")
    base = Path(os.path.relpath(root, out_dir)).as_posix()
    base = "" if base == "." else base + "/"
    page = render(pr, base)
    (out_dir / f"{epic}-map.html").write_text(page, encoding="utf-8")
    print(f"backlog-build: {out_dir / f'{epic}-map.html'} — картинки и схемы берёт из {base or './'}")
    if not args.no_zip:
        n = build_zip(pr, page if not base else render(pr), out_dir / f"{epic}-blueprint.zip")
        print(f"backlog-build: {out_dir / f'{epic}-blueprint.zip'} — файлов {n}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())

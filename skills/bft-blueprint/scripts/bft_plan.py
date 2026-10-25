#!/usr/bin/env python3
"""План карты — один markdown вместо десятков команд CLI.

Агент пишет `plan/map.md` (команды, вопросы, задачи «Что делаем», карточки «Как это работает») и по файлу на
экран в `plan/screens/F3.md`. `./blueprint.py apply` раскладывает план в проект Backlog.md: создаёт и
обновляет задачи по их ID, документы экранов, таблицы «Команды» и «Вопросы» «Карты». Обратно —
`./blueprint.py export`: план из текущего бэклога. Формат — `resources/autopilot.md` §«План карты».

    ## Команды            таблица | ID | Команда |
    ## Вопросы            таблица | ID | Кому | Вопрос | Где | Тип | Ответ |
    ## BP-3 · Название    задача: строки «ключ: значение», пустая строка, описание, ### Критерии приемки
    ## BP-3.1 · Название  карточка: строки «ключ: значение», пустая строка, описание карточки

Ключи задачи: этап, вид, команда | кандидаты, экраны, документы, ссылки.
Ключи карточки: этап, слой, команда (по умолчанию — команда задачи), экраны, документы, ссылки.

  ОШИБКИ ПЛАНА
  PL001  нет plan/map.md или раздела
  PL002  заголовок блока не «## BP-3 · Название» или ID повторяется
  PL003  ключ неизвестен, значения нет или оно не из списка
  PL004  карточка без задачи-родителя в плане
  PL005  таблица «Команды» или «Вопросы» не той формы
  PL006  файл экрана: имя не F3.md или нет заголовка «# Название»
  PL007  в тексте остался шаблон: {{…}}

Только стандартная библиотека.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backlog_cli as cli  # noqa: E402
import bft_backlog as bl  # noqa: E402
import bft_blueprint as bb  # noqa: E402

PLAN_DIR = "plan"
HEAD = re.compile(r"^##\s+([A-Za-z]+-\d+(?:\.\d+)?)\s*·\s*(.+?)\s*$")
META = re.compile(r"^([а-яё]+)\s*:\s*(.*)$")
TASK_KEYS = {"этап", "вид", "команда", "кандидаты", "экраны", "документы", "ссылки"}
CARD_KEYS = {"этап", "слой", "команда", "экраны", "документы", "ссылки"}
AC_HEADS = ("### Критерии приемки", "### Критерии приёмки", "### Чеклист приемки", "### Чеклист приёмки")
STUB = re.compile(r"\{\{[^}]*\}\}")
SCREEN_FILE = re.compile(r"^([A-H]\d{1,2})\.md$")


@dataclass
class Block:
    id: str
    title: str
    line: int
    meta: dict = field(default_factory=dict)
    body: str = ""
    ac: list = field(default_factory=list)

    @property
    def card(self) -> bool:
        return "." in self.id

    @property
    def parent(self) -> str:
        return self.id.rsplit(".", 1)[0] if self.card else ""


@dataclass
class Plan:
    root: Path
    teams: str = ""          # таблица как текст
    questions: str = ""
    blocks: list[Block] = field(default_factory=list)
    screens: dict = field(default_factory=dict)   # {F3: (заголовок, текст, путь)}
    issues: list = field(default_factory=list)

    def err(self, rel: str, line: int, code: str, msg: str) -> None:
        self.issues.append(bb.Issue(line, "ERROR", code, msg, rel))


def split(v: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,;]", v or "") if x.strip()]


def parse(root: Path) -> Plan:
    """Разбор плана: блоки, таблицы, экраны; ошибки формы — PL."""
    pl = Plan(root)
    f = root / PLAN_DIR / "map.md"
    rel = f"{PLAN_DIR}/map.md"
    if not f.is_file():
        pl.err(rel, 1, "PL001", "нет plan/map.md — начни с шаблона .blueprint/templates/map.md")
        return pl
    lines = f.read_text(encoding="utf-8").split("\n")
    chunks: list[tuple[str, int, list[str]]] = []
    for n, ln in enumerate(lines, 1):
        if ln.startswith("## "):
            chunks.append((ln, n, []))
        elif chunks:
            chunks[-1][2].append(ln)
    for n, ln in enumerate(lines, 1):
        if STUB.search(ln):
            pl.err(rel, n, "PL007", f"шаблон не заполнен: {STUB.search(ln).group(0)}")
    seen: set[str] = set()
    for head, n, body in chunks:
        name = head[3:].strip()
        if name == "Команды":
            pl.teams = "\n".join(body).strip()
            continue
        if name == "Вопросы":
            pl.questions = "\n".join(body).strip()
            continue
        m = HEAD.match(head)
        if not m:
            pl.err(rel, n, "PL002", f"«{name}» — заголовок блока: «## BP-3 · Название задачи» (или «## Команды», «## Вопросы»)")
            continue
        b = Block(m.group(1).upper(), m.group(2), n)
        if b.id in seen:
            pl.err(rel, n, "PL002", f"{b.id} уже есть в плане")
            continue
        seen.add(b.id)
        i = 0
        while i < len(body) and not body[i].strip():
            i += 1
        while i < len(body) and body[i].strip():
            mm = META.match(body[i].strip())
            if not mm:
                break
            key, val = mm.group(1), mm.group(2).strip()
            if key == "команда" and val.startswith("кандидаты:"):   # «команда: кандидаты: a, b» — это кандидаты
                key, val = "кандидаты", val.split(":", 1)[1].strip()
            allowed = CARD_KEYS if b.card else TASK_KEYS
            if key not in allowed:
                pl.err(rel, n + 1 + i, "PL003", f"{b.id}: ключ «{key}» — нужен один из: {', '.join(sorted(allowed))}")
            b.meta[key] = val
            i += 1
        text = "\n".join(body[i:]).strip("\n")
        for h in AC_HEADS:
            if h in text and not b.card:
                text, _, tail = text.partition(h)
                rest = re.split(r"^### ", tail, maxsplit=1, flags=re.M)
                b.ac = [re.sub(r"^\s*(?:[-*]|\d+\.)\s+(?:\[[ xX]\]\s+)?", "", x).strip() for x in rest[0].split("\n") if x.strip()]
                if len(rest) > 1:
                    text = text.rstrip("\n") + "\n\n### " + rest[1]
                break
        b.body = text.strip("\n")
        _check_block(pl, b, rel)
        pl.blocks.append(b)
    ids = {b.id for b in pl.blocks}
    for b in pl.blocks:
        if b.card and b.parent not in ids:
            pl.err(rel, b.line, "PL004", f"{b.id}: задачи {b.parent} в плане нет — карточка живёт под своей задачей")
    if not pl.teams or "| ID | Команда |" not in pl.teams:
        pl.err(rel, 1, "PL005", "раздел «## Команды» с таблицей | ID | Команда |")
    if pl.questions and "| ID | Кому | Вопрос | Где | Тип | Ответ |" not in pl.questions:
        pl.err(rel, 1, "PL005", "«## Вопросы»: таблица | ID | Кому | Вопрос | Где | Тип | Ответ |")
    sdir = root / PLAN_DIR / "screens"
    for sf in sorted(sdir.glob("*.md")) if sdir.is_dir() else []:
        srel = f"{PLAN_DIR}/screens/{sf.name}"
        sm = SCREEN_FILE.match(sf.name)
        text = sf.read_text(encoding="utf-8")
        title = next((ln[2:].strip() for ln in text.split("\n") if ln.startswith("# ")), "")
        if not sm or not title:
            pl.err(srel, 1, "PL006", "файл экрана — F3.md (ID экрана истории) с заголовком «# Название экрана»")
            continue
        for k, ln in enumerate(text.split("\n"), 1):
            if STUB.search(ln):
                pl.err(srel, k, "PL007", f"шаблон не заполнен: {STUB.search(ln).group(0)}")
        pl.screens[sm.group(1)] = (title, text.strip("\n") + "\n", sf)
    return pl


def _check_block(pl: Plan, b: Block, rel: str) -> None:
    need = ("этап", "слой") if b.card else ("этап", "вид")
    for k in need:
        if not b.meta.get(k):
            pl.err(rel, b.line, "PL003", f"{b.id}: нет строки «{k}: …» сразу под заголовком")
    if b.card and b.meta.get("слой") and b.meta["слой"] not in bl.LAYERS:
        pl.err(rel, b.line, "PL003", f"{b.id}: слой «{b.meta['слой']}» — один из {', '.join(bl.LAYERS)}")
    if not b.card and b.meta.get("вид") and b.meta["вид"] not in bl.KINDS:
        pl.err(rel, b.line, "PL003", f"{b.id}: вид «{b.meta['вид']}» — один из {', '.join(bl.KINDS)}")
    if not b.card and not b.meta.get("команда") and not b.meta.get("кандидаты"):
        pl.err(rel, b.line, "PL003", f"{b.id}: «команда: id» или «кандидаты: id1, id2», если исполнитель не ясен")
    if not b.body.strip():
        pl.err(rel, b.line, "PL003", f"{b.id}: нет описания под строками ключей")


# --- запись в проект -------------------------------------------------------------------------------

def _replace_section(body: str, name: str, table: str) -> str:
    block = f"## {name}\n\n{table.strip()}\n"
    if re.search(rf"^## {name}\s*$", body, re.M):
        return re.sub(rf"^## {name}\s*\n.*?(?=^## |\Z)", lambda _: block + "\n", body, count=1, flags=re.S | re.M).rstrip("\n") + "\n"
    return body.rstrip("\n") + "\n\n" + block


APPLIED = "plan.applied"   # .blueprint/plan.applied — хэш плана, который последний раз ушёл в бэклог


def plan_hash(root: Path) -> str:
    import hashlib
    h = hashlib.sha1()
    d = root / PLAN_DIR
    for f in [d / "map.md"] + sorted((d / "screens").glob("*.md")):
        if f.is_file():
            h.update(f.name.encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:16]


def apply(pl: Plan, root: Path) -> list[str]:
    """План → проект. Возвращает строки отчёта; ошибки плана — в pl.issues, тогда ничего не пишется."""
    if any(i.level == "ERROR" for i in pl.issues):
        return []
    bdir = bl.find_backlog(root)
    pr = bl.parse(root)
    cfg = cli.config(bdir)
    prefix = pr.prefix
    out = []
    # «Карта»: команды и вопросы
    if pr.map_doc:
        f = pr.map_doc.path
        text = f.read_text(encoding="utf-8")
        fm_end = text.index("\n---", 3) + 4
        head, body = text[:fm_end], text[fm_end:]
        new = _replace_section(body, "Команды", pl.teams)
        if pl.questions:
            new = _replace_section(new, "Вопросы", pl.questions)
        if new != body:
            f.write_text(head + new, encoding="utf-8")
            out.append(f"«Карта»: команды и вопросы — {f.relative_to(root)}")
    # экраны → документы
    docs = {fm["id"]: (p, fm) for p, fm, _ in cli.load_docs(bdir)}
    screen_doc = {}
    for did, (p, fm) in docs.items():
        m = bl.SCREEN_TITLE.match(str(fm.get("title", "")))
        if m and "/docs/screens/" in "/" + p.relative_to(bdir).as_posix():
            screen_doc[m.group(1)] = did
    nums = [int(m.group(1)) for d in docs for m in [re.fullmatch(r"doc-(\d+)", d)] if m]
    for sid, (title, text, _) in sorted(pl.screens.items()):
        did = screen_doc.get(sid)
        full = f"{sid} · {title}"
        if not did:
            did = f"doc-{max(nums, default=0) + 1}"
            nums.append(int(did[4:]))
            fm = {"id": did, "title": full, "type": "specification", "created_date": cli.now()}
            p = bdir / "docs" / "screens" / f"{did} - {cli.slug(full)}.md"
            p.parent.mkdir(parents=True, exist_ok=True)
            out.append(f"экран {sid}: создан {did}")
        else:
            p, fm = docs[did]
            old = p.read_text(encoding="utf-8")
            if fm.get("title") == full and old.endswith(text) and old[:len(old) - len(text)].rstrip("\n").endswith("---"):
                continue
            fm["title"] = full
            fm["updated_date"] = cli.now()
            out.append(f"экран {sid}: обновлён {did}")
        p.write_text(cli.dump_front(fm) + text, encoding="utf-8")
        screen_doc[sid] = did
    # задачи и карточки — по порядку плана
    tasks = {t.id: t for t in cli.load_tasks(bdir, archived=True)}
    ords = [float(t.fm.get("ordinal")) for t in tasks.values() if str(t.fm.get("ordinal", "")).replace(".", "", 1).isdigit()]
    order = int(max(ords, default=0))
    for b in pl.blocks:
        t = tasks.get(b.id)
        created = t is None
        if created:
            t = cli.Task(None, {"id": b.id, "title": b.title, "status": cfg.get("default_status") or "To Do",
                                "assignee": [], "created_date": cli.now(), "labels": [], "dependencies": []})
        fm = t.fm
        fm["title"] = b.title
        if b.card:
            labels = [f"stage:{b.meta.get('этап', '')}", f"layer:{b.meta.get('слой', '')}"]
            team = b.meta.get("команда", "")
            fm["assignee"] = [f"@{team.lstrip('@')}"] if team else []
            fm["parent_task_id"] = b.parent
        else:
            cands = split(b.meta.get("кандидаты", ""))
            labels = [f"stage:{b.meta.get('этап', '')}", b.meta.get("вид", "")] + [f"кандидат:{c}" for c in cands]
            team = b.meta.get("команда", "")
            fm["assignee"] = [f"@{team.lstrip('@')}"] if team and not cands else []
            fm.pop("parent_task_id", None)
        keep = [x for x in fm.get("labels") or [] if not re.match(r"^(stage:|layer:|кандидат:)", str(x)) and x not in bl.KINDS]
        fm["labels"] = labels + keep
        docs_ids = [screen_doc.get(s, "") for s in split(b.meta.get("экраны", ""))] + split(b.meta.get("документы", ""))
        if "экраны" in b.meta or "документы" in b.meta:
            fm["documentation"] = [d for d in docs_ids if d]
        if "ссылки" in b.meta:
            fm["references"] = split(b.meta["ссылки"])
        if created:
            order += 1000
            fm["ordinal"] = order
        body = b.body
        if b.card and "### BPMN" not in body:
            old_bpmn = re.search(r"^### BPMN\n.*?(?=^### |\Z)", t.sections.get("DESCRIPTION", ""), re.S | re.M)
            if old_bpmn and "### HowToDemo" in body:
                body = body.replace("### HowToDemo", old_bpmn.group(0).rstrip("\n") + "\n\n### HowToDemo", 1)
        t.sections["DESCRIPTION"] = body
        if not b.card:
            done = {x: d for d, x in t.ac}
            t.ac = [[done.get(x, False), x] for x in b.ac]
        ordered = {k: fm[k] for k in cli.FM_ORDER if k in fm}
        ordered.update({k: v for k, v in fm.items() if k not in ordered})
        t.fm = ordered
        if not created and _same(t, t.path):
            continue
        if not created:
            t.fm["updated_date"] = cli.now()
        cli.save(t, bdir, prefix)
        out.append(f"{b.id}: {'создана' if created else 'обновлена'} — {t.path.relative_to(root)}")
    synced = bl.sync_schema(bl.parse(root), write=True)
    if synced:
        out.append(f"схемы BPMN из «Процесса»: {', '.join(c.id for c in synced)}")
    missing = sorted(set(tasks) - {b.id for b in pl.blocks})
    stray = [x for x in missing if any(re.match(r"^(stage:|layer:)", str(lb)) for lb in tasks[x].fm.get("labels") or [])]
    for x in stray:
        out.append(f"{x}: на карте, но не в плане — верни в план или убери метку stage: (./backlog.py task edit {x} --remove-label …)")
    (root / ".blueprint").mkdir(exist_ok=True)
    (root / ".blueprint" / APPLIED).write_text(plan_hash(root) + "\n", encoding="utf-8")   # next сверяет: план применён
    return out


def _same(t, path: Path) -> bool:
    """Задача в файле та же по смыслу: поля, описание, критерии (кавычки YAML и порядок не важны)."""
    old = cli.Task(path, bl.yaml_front(path.read_text(encoding="utf-8"))[0] or {}, path.read_text(encoding="utf-8"))
    norm = lambda fm: {k: [str(x) for x in v] if isinstance(v, list) else str(v) for k, v in fm.items() if k != "updated_date"}  # noqa: E731
    return norm(old.fm) == norm(t.fm) and old.sections == t.sections and old.ac == t.ac


# --- бэклог → план ---------------------------------------------------------------------------------

def export(root: Path) -> dict[str, str]:
    """План из бэклога: {путь от проекта: текст}. Тот же план, применённый к проекту, ничего не меняет."""
    pr = bl.parse(root)
    bdir = pr.bdir
    files: dict[str, str] = {}
    sid_of = {}
    for sid, sd in pr.screens.items():
        doc_id = next((k for k, d in pr.docs.items() if d.path == sd.path), "")
        sid_of[doc_id] = sid
        files[f"{PLAN_DIR}/screens/{sid}.md"] = sd.text.strip("\n") + "\n"
    body = pr.map_doc.body if pr.map_doc else ""

    def table(name: str) -> str:
        m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
        return m.group(1).strip() if m else ""
    o = [f"# План карты: {pr.title}", "", "## Команды", "", table("Команды"), "", "## Вопросы", "", table("Вопросы"), ""]
    raw = {t.id: t for t in cli.load_tasks(bdir)}
    for t in sorted(pr.tasks, key=lambda x: x.ordinal):
        r = raw[t.id]
        cands = [str(lb).split(":", 1)[1] for lb in r.fm.get("labels") or [] if str(lb).startswith("кандидат:")]
        meta = [f"этап: {t.stage}", f"вид: {t.kind}"]
        meta.append(f"кандидаты: {', '.join(cands)}" if cands else f"команда: {t.team}")
        o += _export_block(t, r, meta, sid_of)
        if r.ac:
            o += ["### Критерии приемки"] + [f"- {x}" for _, x in r.ac] + [""]
        for c in sorted([c for c in pr.cards if c.parent == t.id], key=lambda x: x.ordinal):
            rc = raw[c.id]
            cmeta = [f"этап: {c.stage}", f"слой: {c.layer}"]
            if rc.fm.get("assignee"):
                cmeta.append(f"команда: {str(rc.fm['assignee'][0]).lstrip('@')}")
            o += _export_block(c, rc, cmeta, sid_of)
    files[f"{PLAN_DIR}/map.md"] = "\n".join(o).rstrip("\n") + "\n"
    return files


def _export_block(t, raw, meta: list[str], sid_of: dict) -> list[str]:
    docs = [str(d) for d in raw.fm.get("documentation") or []]
    scr = [sid_of[d] for d in docs if d in sid_of]
    other = [d for d in docs if d not in sid_of]
    if scr:
        meta.append(f"экраны: {', '.join(scr)}")
    if other:
        meta.append(f"документы: {', '.join(other)}")
    if raw.fm.get("references"):
        meta.append(f"ссылки: {', '.join(str(x) for x in raw.fm['references'])}")
    desc = re.sub(r"^### BPMN\n.*?(?=^### |\Z)", "", raw.sections["DESCRIPTION"], flags=re.S | re.M)
    return [f"## {t.id} · {t.title}", *meta, "", desc.strip("\n"), ""]

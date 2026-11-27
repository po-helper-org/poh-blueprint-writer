"""Ядро сервиса Blueprint: какие диаграммы есть в воркспейсе и на каком они этапе.

Диаграмма — папка эпика `<docs_path>/<epic>/` с артефактами навыка `/bft-blueprint`:

  <epic>.md | <epic>-fast.md   БФТ — источник
  <epic>-story.md | .html       история через экраны (этап 1)
  <epic>-blueprint/             проект Backlog.md карты (этап 2 и всё дальше)
  <epic>-map.html, -blueprint.zip   собранная страница и архив
  <epic>-blueprint/contracts/   контракты стыков
  <epic>-blueprint/prototype/   прототип
  <epic>-blueprint/confluence/publish.json   отгрузка в Confluence

Этап считается по артефактам, а не по чьим-то отметкам: документ есть и собран — этап сделан.
Разделено на два слоя: `collect()` читает диск в словарь фактов, `stages()` — чистая функция
фактов → этапы. Тесты проверяют вторую без файлов, первую — на эталонном примере навыка.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")

# Документы проекта карты: вид маркера <!-- bft-… --> → ключ этапа
DOC_KINDS = {
    "bft-map": "map", "bft-story": "story", "bft-adr": "adr", "bft-sysreq": "sysreq",
    "bft-seams": "seams", "bft-release": "release", "bft-roadmap": "roadmap",
    "bft-risks": "risks", "bft-deviations": "deviations",
}
DOC_TITLES = {
    "adr": "ADR", "sysreq": "Системные требования", "seams": "Стыки", "release": "План релиза",
    "roadmap": "Roadmap", "risks": "Риски исполнения", "deviations": "Расхождения с требованиями",
}
EMPTY = {"", "—", "-", "–"}


class BlueprintError(Exception):
    """Ошибка с текстом для человека; `status` — HTTP-код ответа API."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def check_slug(epic: str) -> str:
    epic = (epic or "").strip()
    if not SLUG_RE.match(epic) or ".." in epic:
        raise BlueprintError(f"неверный слаг эпика: {epic!r}")
    return epic


# ---------------------------------------------------------------- рабочая область ----------

@dataclass
class Workspace:
    """Где лежат документы и навыки. Пути абсолютные."""
    root: Path
    docs: Path
    skills: Path

    @classmethod
    def from_config(cls, cfg: dict) -> "Workspace":
        root = Path(cfg.get("workspace") or ".").expanduser().resolve()
        docs_rel = cfg.get("docs_path") or ""
        if docs_rel:
            docs = (root / docs_rel).resolve()
        else:  # умолчание bft-config.md и прежняя раскладка
            docs = next((root / p for p in (".bft/documentation", "bft/documentation") if (root / p).is_dir()),
                        root / ".bft/documentation")
        skills = Path(cfg.get("skills_path") or Path(__file__).resolve().parents[2] / "skills").expanduser().resolve()
        return cls(root, docs.resolve(), skills)

    @property
    def scripts(self) -> Path:
        return self.skills / "bft-blueprint" / "scripts"

    def epic_dir(self, epic: str) -> Path:
        d = (self.docs / check_slug(epic)).resolve()
        if d.parent != self.docs:
            raise BlueprintError("путь вне каталога документов")
        return d

    def rel(self, p: Path) -> str:
        """Путь для команды агенту — от корня воркспейса, где он запускается."""
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(p)


def _load_parsers(ws: Workspace):
    """Разборщики навыка (bft_backlog, bft_story) — те же, что у сборки страницы карты."""
    path = str(ws.scripts)
    if path not in sys.path:
        sys.path.insert(0, path)
    import bft_backlog  # noqa: WPS433
    import bft_story  # noqa: WPS433
    return bft_backlog, bft_story


# ---------------------------------------------------------------- факты ----------

def _mtime(p: Path) -> float | None:
    try:
        return p.stat().st_mtime
    except OSError:
        return None


def _newest(d: Path) -> float | None:
    best = None
    if not d.is_dir():
        return None
    for sub in ("backlog", "contracts", "plan"):
        base = d / sub
        if not base.is_dir():
            continue
        for f in base.rglob("*.md"):
            m = _mtime(f)
            if m and (best is None or m > best):
                best = m
    return best


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    out = {}
    for line in text[3:end if end > 0 else 0].splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip():
            out[k.strip()] = v.strip().strip("'\"")
    return out


def _h1(text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if not m:
        return ""
    title = m.group(1).strip()
    title = re.sub(r"^\[[^\]]+\]\s*", "", title)          # [БФТ] / [История]
    title = re.sub(r"^[A-Za-z0-9._-]+:\s*", "", title)    # <slug>:
    return title


def _iso(ts: float | None) -> str | None:
    return dt.datetime.fromtimestamp(ts).isoformat(timespec="minutes") if ts else None


def collect(ws: Workspace, epic: str, deep: bool = True) -> dict:
    """Факты об эпике с диска. `deep=False` — без разбора проекта карты (для быстрого списка)."""
    d = ws.epic_dir(epic)
    f: dict = {"epic": epic, "dir": ws.rel(d), "title": "", "bft": None, "bft_path": None,
               "story": None, "project": None, "map_html": False, "zip": False, "map_stale": False,
               "prototype": False, "confluence": None, "updated": None}
    deep_doc, fast_doc = d / f"{epic}.md", d / f"{epic}-fast.md"
    if deep_doc.is_file():
        f["bft"], f["bft_path"] = "deep", ws.rel(deep_doc)
        f["title"] = _h1(deep_doc.read_text(encoding="utf-8", errors="replace")[:4000])
    elif fast_doc.is_file():
        f["bft"], f["bft_path"] = "fast", ws.rel(fast_doc)
        f["title"] = _h1(fast_doc.read_text(encoding="utf-8", errors="replace")[:4000])

    story = d / f"{epic}-story.md"
    if story.is_file():
        text = story.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        html = d / f"{epic}-story.html"
        f["story"] = {"path": ws.rel(story), "status": fm.get("status", ""), "version": fm.get("version", ""),
                      "revised": fm.get("revised", ""), "html": html.is_file(),
                      "html_stale": html.is_file() and (_mtime(html) or 0) < (_mtime(story) or 0)}
        f["title"] = _h1(text[:4000]) or f["title"]

    proj = d / f"{epic}-blueprint"
    map_html, zip_ = d / f"{epic}-map.html", d / f"{epic}-blueprint.zip"
    if not map_html.is_file() and (proj / f"{epic}-map.html").is_file():   # ./blueprint.py build пишет в проект
        map_html, zip_ = proj / f"{epic}-map.html", proj / f"{epic}-blueprint.zip"
    f["map_html"], f["zip"] = map_html.is_file(), zip_.is_file()
    f["map_html_path"] = ws.rel(map_html) if map_html.is_file() else None
    if (proj / "backlog").is_dir():
        f["project"] = _project_facts(ws, proj, deep)
        newest = _newest(proj)
        f["map_stale"] = bool(f["map_html"] and newest and newest > (_mtime(map_html) or 0) + 1)
        f["prototype"] = (proj / "prototype").is_dir() and any((proj / "prototype").iterdir())
        pub = proj / "confluence" / "publish.json"
        if pub.is_file():
            try:
                meta = json.loads(pub.read_text(encoding="utf-8"))
            except ValueError:
                meta = {}
            f["confluence"] = {"page_id": str(meta.get("page_id") or meta.get("id") or ""),
                               "url": meta.get("url") or meta.get("page_url") or "",
                               "parent": str(meta.get("parent") or ""), "prepared": (proj / "confluence" / "page.xhtml").is_file()}
        if (f["project"] or {}).get("title"):
            f["title"] = f["project"]["title"]   # у диаграммы имя карты — главное
    stamps = [m for m in (_mtime(story), _mtime(map_html), _newest(proj) if proj.is_dir() else None,
                          _mtime(deep_doc), _mtime(fast_doc)) if m]
    f["updated"] = _iso(max(stamps)) if stamps else None
    f["title"] = f["title"] or epic
    return f


def _project_facts(ws: Workspace, proj: Path, deep: bool) -> dict:
    out = {"path": ws.rel(proj), "docs": {}, "contracts": len(list((proj / "contracts").glob("C-*.md"))) if (proj / "contracts").is_dir() else 0}
    for doc in (proj / "backlog" / "docs").glob("*.md") if (proj / "backlog" / "docs").is_dir() else []:
        head = doc.read_text(encoding="utf-8", errors="replace")[:3000]
        m = re.search(r"<!--\s*(bft-[a-z]+)\s*\n(.*?)-->", head, re.S)
        if m and m.group(1) in DOC_KINDS:
            status = re.search(r"^status:\s*(.+)$", m.group(2), re.M)
            out["docs"][DOC_KINDS[m.group(1)]] = {"file": ws.rel(doc), "status": status.group(1).strip() if status else ""}
    tasks_dir = proj / "backlog" / "tasks"
    out["files"] = len(list(tasks_dir.glob("*.md"))) if tasks_dir.is_dir() else 0
    if not deep:
        return out
    try:
        bl, _ = _load_parsers(ws)
        pr = bl.parse(proj)
    except Exception as e:  # noqa: BLE001 — карта сломана, но список жив
        out["parse_error"] = f"{type(e).__name__}: {e}"
        return out
    teams = {t.team for t in pr.tasks + pr.subtasks if t.team and t.team != "?"}
    out.update({
        "title": pr.title or (pr.meta or {}).get("title", ""),
        "status": (pr.meta or {}).get("status", ""), "version": str((pr.meta or {}).get("version", "")),
        "tasks": len(pr.tasks), "cards": len(pr.cards), "subtasks": len(pr.subtasks),
        "teams": [{"id": t.id, "name": t.name} for t in pr.teams], "teams_on_map": len(teams),
        "technology": sum(1 for c in pr.cards if c.layer == "technology"),
        "questions": len(pr.questions), "questions_open": sum(1 for q in pr.questions if q.open),
        "blockers_open": sum(1 for q in pr.questions if q.open and "блок" in (q.kind or "").lower()),
        "deviations": len(pr.devs.items) if pr.devs else 0,
        "errors": len(pr.errors),
    })
    return out


# ---------------------------------------------------------------- этапы ----------

@dataclass
class Stage:
    key: str
    title: str
    status: str                     # done | review | ready | stale | blocked | skipped | optional
    summary: str = ""
    missing: list = field(default_factory=list)
    command: str = ""               # черновик для агента (чат, Claude Code, MCP-клиент)
    actions: list = field(default_factory=list)   # детерминированные действия сервиса без LLM
    artifacts: list = field(default_factory=list)  # [{label, kind, path}]

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("key", "title", "status", "summary", "missing", "command", "actions", "artifacts")}


STAGE_ORDER = ("bft", "story", "map", "adr", "seams", "reconcile", "release", "prototype", "confluence")
STAGE_TITLES = {
    "bft": "БФТ — источник", "story": "История через экраны", "map": "Карта инициативы",
    "adr": "ADR и системные требования", "seams": "Стыки и контракты", "reconcile": "Сверка с БФТ",
    "release": "План релиза / Delivery", "prototype": "Прототип", "confluence": "Отгрузка в Confluence",
}
ACTIVE = ("review", "stale", "ready")


def stages(f: dict) -> list[Stage]:
    """Факты → этапы по порядку работы. Чистая функция: никакого ввода-вывода."""
    epic, p = f["epic"], f.get("project") or {}
    proj = p.get("path") or f"{f['dir']}/{epic}-blueprint"
    docs = p.get("docs") or {}
    out: list[Stage] = []

    # 1. БФТ
    if f.get("bft") == "deep":
        out.append(Stage("bft", STAGE_TITLES["bft"], "done", "deep",
                         artifacts=[{"label": "БФТ", "kind": "md", "path": f["bft_path"]}]))
    elif f.get("bft") == "fast":
        out.append(Stage("bft", STAGE_TITLES["bft"], "done", "только fast — карта выйдет тонкой",
                         missing=["полный БФТ — /bft-deep"], command=f"/bft-deep {epic}",
                         artifacts=[{"label": "БФТ (fast)", "kind": "md", "path": f["bft_path"]}]))
    else:
        out.append(Stage("bft", STAGE_TITLES["bft"], "blocked", "нет БФТ",
                         missing=[f"{f['dir']}/{epic}.md"], command=f"/bft-fast {epic}"))
    has_bft = bool(f.get("bft"))

    # 2. История
    s = f.get("story")
    if not has_bft and not s:
        out.append(Stage("story", STAGE_TITLES["story"], "blocked", ""))
    elif not s:
        out.append(Stage("story", STAGE_TITLES["story"], "ready", "",
                         missing=[f"{epic}-story.md"], command=f"/bft-blueprint {epic} --story",
                         actions=[{"id": "auto", "label": "Автопилот"}]))
    else:
        art = [{"label": "История", "kind": "md", "path": s["path"]}]
        if s["html"]:
            art.append({"label": "Страница истории", "kind": "story", "path": s["path"].replace(".md", ".html")})
        approved = s["status"].lower().startswith("согласов")
        if not s["html"] or s["html_stale"]:
            out.append(Stage("story", STAGE_TITLES["story"], "stale", "страница устарела",
                             missing=[f"{epic}-story.html"], actions=[{"id": "story_render", "label": "Собрать"}], artifacts=art))
        elif not approved and not p:
            out.append(Stage("story", STAGE_TITLES["story"], "review", f"черновик v{s['version'] or '1'}",
                             missing=["status: Согласован"], command=f"/bft-blueprint {epic} --story <правки PO>",
                             actions=[{"id": "story_approve", "label": "Согласовать"}], artifacts=art))
        else:
            out.append(Stage("story", STAGE_TITLES["story"], "done",
                             f"v{s['version'] or '1'} · {s['status'] or 'без статуса'}", artifacts=art))
    story_ok = out[-1].status == "done"

    # 3. Карта
    map_art = []
    if f.get("map_html"):
        map_art.append({"label": "Страница карты", "kind": "map", "path": f.get("map_html_path")})
    if not p:
        st = "ready" if story_ok else "blocked"
        out.append(Stage("map", STAGE_TITLES["map"], st, "",
                         missing=[f"{epic}-blueprint/"], command=f"/bft-blueprint {epic} --map" if story_ok else ""))
    else:
        counts = f"{p.get('tasks', 0)} задач · {p.get('cards', 0)} карточек"
        if p.get("parse_error"):
            out.append(Stage("map", STAGE_TITLES["map"], "stale", f"карта не читается: {p['parse_error']}",
                             command=f"/bft-blueprint {epic} --map", actions=[{"id": "lint", "label": "Проверить карту"}]))
        elif not p.get("tasks") and p.get("files", 0) == 0:
            out.append(Stage("map", STAGE_TITLES["map"], "ready", "задач нет",
                             command=f"/bft-blueprint {epic} --map",
                             actions=[{"id": "skeleton", "label": "Каркас плана"}, {"id": "next", "label": "Что исправить"}]))
        elif not f.get("map_html") or f.get("map_stale") or p.get("errors"):
            why = (f"ошибок: {p['errors']}" if p.get("errors") else
                   "страница устарела" if f.get("map_stale") else "страница не собрана")
            out.append(Stage("map", STAGE_TITLES["map"], "stale", why,
                             missing=[why], command=f"/bft-blueprint {epic} --map" if p.get("errors") else "",
                             actions=[{"id": "build", "label": "Собрать"}, {"id": "lint", "label": "Проверить"}, {"id": "next", "label": "Что исправить"}],
                             artifacts=map_art))
        else:
            out.append(Stage("map", STAGE_TITLES["map"], "done",
                             counts,
                             actions=[{"id": "build", "label": "Пересобрать"}, {"id": "verify", "label": "Приёмка"}],
                             artifacts=map_art))
    map_ok = out[-1].status in ("done", "stale") and bool(p.get("tasks"))

    def gated(key: str, needed: bool, done: bool, summary_done: str, summary_todo: str, command: str,
              missing: list, actions=None, art=None, optional=False, skip_reason=""):
        if not map_ok:
            out.append(Stage(key, STAGE_TITLES[key], "blocked", ""))
        elif not needed:
            out.append(Stage(key, STAGE_TITLES[key], "skipped", skip_reason))
        elif done:
            out.append(Stage(key, STAGE_TITLES[key], "done", summary_done, actions=actions or [], artifacts=art or []))
        else:
            out.append(Stage(key, STAGE_TITLES[key], "optional" if optional else "ready", summary_todo,
                             missing=missing, command=command, actions=actions or []))

    def doc_art(*kinds):
        return [{"label": DOC_TITLES[k], "kind": "md", "path": docs[k]["file"]} for k in kinds if k in docs]

    bft_arg = f" --bft {f['bft_path']}" if f.get("bft_path") else ""
    # 4. ADR и системные требования — когда на карте есть слой Technology
    tech = p.get("technology", 0)
    have = [k for k in ("adr", "sysreq") if k in docs]
    gated("adr", tech > 0, len(have) == 2,
          "",
          ("нет: " + ", ".join(DOC_TITLES[k] for k in ("adr", "sysreq") if k not in docs)),
          (f"/system-requirements{bft_arg} --project {proj}" if "adr" in have else f"/adr{bft_arg} --project {proj}"),
          [DOC_TITLES[k] for k in ("adr", "sysreq") if k not in docs], art=doc_art("adr", "sysreq"),
          skip_reason="нет слоя Technology")

    # 5. Стыки и контракты — когда работа режется между командами
    teams = p.get("teams_on_map", 0)
    seams_done = "seams" in docs and p.get("contracts", 0) > 0
    gated("seams", teams >= 2, seams_done,
          f"контрактов: {p.get('contracts', 0)}",
          f"команд: {teams}",
          f"/bft-blueprint {epic} --map — шаги 7–8: документ «Стыки» и контракты стыков (./blueprint.py contracts до 0 ошибок)",
          (["документ «Стыки»"] if "seams" not in docs else []) + (["контракты contracts/C-N.md"] if not p.get("contracts") else []),
          actions=[{"id": "contracts", "label": "Проверить контракты"}], art=doc_art("seams"),
          skip_reason="одна команда")

    # 6. Сверка с БФТ
    gated("reconcile", True, "deviations" in docs,
          f"расхождений: {p.get('deviations', 0)}", "",
          f"/bft-reconcile {proj}" + (f" --source {f['bft_path']}" if f.get("bft_path") else ""),
          ["реестр «Расхождения с требованиями»"], actions=[{"id": "reconcile", "label": "Сверить скриптом"}],
          art=doc_art("deviations"))

    # 7. План релиза
    gated("release", True, "release" in docs, docs.get('release', {}).get('status', ''),
          "", f"/release-plan{bft_arg} --project {proj}", ["документ «План релиза»"],
          art=doc_art("release", "roadmap", "risks"))

    # 8. Прототип — по желанию
    gated("prototype", True, bool(f.get("prototype")), "", "",
          f"/bft-blueprint {epic} --prototype", [], optional=True)

    # 9. Confluence
    c = f.get("confluence") or {}
    gated("confluence", True, bool(c.get("page_id")),
          "",
          "страница подготовлена" if c.get("prepared") else "",
          f"/bft-confluence {proj} <ссылка на страницу БФТ>", ["страница в Confluence"],
          actions=[{"id": "confluence_page", "label": "Подготовить страницу"}],
          art=[{"label": "Confluence", "kind": "url", "path": c["url"]}] if c.get("url") else [])
    return out


def next_stage(st: list[Stage]) -> Stage | None:
    for s in st:
        if s.status in ACTIVE:
            return s
    return None


def progress(st: list[Stage]) -> dict:
    counted = [s for s in st if s.status not in ("skipped", "optional") and s.key != "prototype"]
    done = sum(1 for s in counted if s.status == "done")
    return {"done": done, "total": len(counted)}


# ---------------------------------------------------------------- список ----------

def list_epics(ws: Workspace) -> tuple[list[dict], list[dict]]:
    """(диаграммы, БФТ без диаграммы). Диаграмма — есть история или проект карты."""
    maps, candidates = [], []
    if not ws.docs.is_dir():
        return maps, candidates
    for d in sorted(p for p in ws.docs.iterdir() if p.is_dir() and SLUG_RE.match(p.name)):
        epic = d.name
        has_any = any((d / n).exists() for n in (f"{epic}.md", f"{epic}-fast.md", f"{epic}-story.md", f"{epic}-blueprint"))
        if not has_any:
            continue
        f = collect(ws, epic, deep=True)
        if f.get("story") or f.get("project"):
            maps.append(summary(f))
        elif f.get("bft"):
            candidates.append({"epic": epic, "title": f["title"], "bft": f["bft"], "bft_path": f["bft_path"], "updated": f["updated"]})
    maps.sort(key=lambda m: m.get("updated") or "", reverse=True)
    candidates.sort(key=lambda m: m.get("updated") or "", reverse=True)
    return maps, candidates


def summary(f: dict) -> dict:
    st = stages(f)
    nxt = next_stage(st)
    p = f.get("project") or {}
    return {
        "epic": f["epic"], "title": f["title"], "updated": f["updated"], "bft": f.get("bft"),
        "stages": [{"key": s.key, "title": s.title, "status": s.status} for s in st],
        "progress": progress(st),
        "next": {"key": nxt.key, "title": nxt.title, "status": nxt.status, "summary": nxt.summary} if nxt else None,
        "counts": {k: p.get(k, 0) for k in ("tasks", "cards", "questions_open", "blockers_open", "deviations", "contracts")},
        "teams": [t["name"] for t in p.get("teams") or []],
    }


def detail(ws: Workspace, epic: str) -> dict:
    d = ws.epic_dir(epic)
    if not d.is_dir():
        raise BlueprintError(f"эпика {epic} нет в {ws.rel(ws.docs)}", 404)
    f = collect(ws, epic, deep=True)
    st = stages(f)
    nxt = next_stage(st)
    return {**summary(f), "facts": f, "stages": [s.as_dict() for s in st], "next": nxt.as_dict() if nxt else None,
            "auto_command": f"/bft-blueprint {epic} --auto"}


# ---------------------------------------------------------------- вопросы карты ----------

def questions(ws: Workspace, epic: str) -> list[dict]:
    proj = ws.epic_dir(epic) / f"{epic}-blueprint"
    if not (proj / "backlog").is_dir():
        return []
    bl, _ = _load_parsers(ws)
    pr = bl.parse(proj)
    return [{"id": q.id, "to": q.to, "text": q.text, "where": q.where, "kind": q.kind,
             "answer": "" if q.open else q.answer, "open": q.open} for q in pr.questions]


def answer_question(ws: Workspace, epic: str, qid: str, answer: str, who: str = "PO") -> dict:
    """Ответ PO — в последнюю ячейку строки «Вопросов» паспорта «Карта». Остальное в строке не трогаем."""
    answer = " ".join((answer or "").split())
    if not answer:
        raise BlueprintError("пустой ответ")
    if "|" in answer:
        answer = answer.replace("|", "/")
    proj = ws.epic_dir(epic) / f"{epic}-blueprint"
    bl, _ = _load_parsers(ws)
    pr = bl.parse(proj)
    if not pr.map_doc:
        raise BlueprintError("в проекте нет паспорта «Карта»", 404)
    path = pr.map_doc.path
    lines = path.read_text(encoding="utf-8").split("\n")
    stamp = f"{answer} ({who}, {dt.date.today().isoformat()})"
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.lstrip().startswith("|") and cells and cells[0] == qid and len(cells) >= 6:
            cells[-1] = stamp
            lines[i] = "| " + " | ".join(cells) + " |"
            path.write_text("\n".join(lines), encoding="utf-8")
            return {"id": qid, "answer": stamp}
    raise BlueprintError(f"вопроса {qid} нет в «Карте»", 404)


def approve_story(ws: Workspace, epic: str) -> dict:
    story = ws.epic_dir(epic) / f"{epic}-story.md"
    if not story.is_file():
        raise BlueprintError("истории нет", 404)
    text = story.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise BlueprintError("у истории нет frontmatter")
    end = text.find("\n---", 3)
    head, rest = text[:end], text[end:]
    today = dt.date.today().isoformat()
    head = re.sub(r"^status:.*$", "status: Согласован", head, flags=re.M) if re.search(r"^status:", head, re.M) else head + "\nstatus: Согласован"
    head = re.sub(r"^revised:.*$", f"revised: {today}", head, flags=re.M) if re.search(r"^revised:", head, re.M) else head + f"\nrevised: {today}"
    story.write_text(head + rest, encoding="utf-8")
    return {"status": "Согласован", "revised": today}

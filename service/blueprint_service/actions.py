"""Действия над диаграммой: детерминированные скрипты навыка, запись текстов агента и фоновый агент.

Пишет текст модель (агент в чате, Claude Code, внешний MCP-клиент) — сервис проверяет, хранит и
собирает: линтеры и сборка — те же скрипты, что вызывает навык `/bft-blueprint`. Отсюда правило:
любой текст, пришедший от агента, ложится в файл и сразу проверяется, ответ несёт вывод проверки.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .core import DOC_KINDS, DOC_TITLES, BlueprintError, Workspace, check_slug, collect

PY = sys.executable or "python3"
MAX_OUT = 20000
TIMEOUT = 300


def _tail(text: str) -> str:
    text = text or ""
    if len(text) <= MAX_OUT:
        return text
    # начало — первые ошибки с адресами строк, конец — итог проверки
    return text[: MAX_OUT * 2 // 3] + f"\n… пропущено {len(text) - MAX_OUT} знаков …\n" + text[-MAX_OUT // 3:]


def _run(cmd: list, cwd: Path, timeout: int = TIMEOUT) -> dict:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env)
        code, out = r.returncode, (r.stdout or "") + (("\n" + r.stderr) if r.stderr.strip() else "")
    except subprocess.TimeoutExpired:
        code, out = -1, f"не уложилось в {timeout} с"
    except FileNotFoundError as e:
        code, out = -1, f"нет программы: {e.filename}"
    return {"ok": code == 0, "code": code, "output": _tail(out.strip()), "seconds": round(time.time() - t0, 1),
            "command": " ".join(str(c) for c in cmd)}


def _paths(ws: Workspace, epic: str) -> tuple[Path, Path, Path]:
    d = ws.epic_dir(epic)
    if not d.is_dir():
        raise BlueprintError(f"эпика {epic} нет", 404)
    return d, d / f"{epic}-story.md", d / f"{epic}-blueprint"


def _need_project(proj: Path) -> None:
    if not (proj / "backlog").is_dir():
        raise BlueprintError("проекта карты ещё нет — сначала согласованная история и blueprint_run init_map", 409)


ACTIONS = {
    "story_render": "проверить и собрать страницу истории",
    "story_approve": "согласовать историю (status: Согласован)",
    "init_map": "создать проект карты из истории",
    "init_map_auto": "создать проект карты по несогласованной истории (автопилот)",
    "skeleton": "каркас плана plan/map.md из БФТ",
    "apply": "план plan/map.md → задачи, карточки, документы и проверка",
    "next": "что исправить дальше",
    "lint": "проверить карту",
    "build": "собрать страницу карты и архив",
    "verify": "приёмка комплекта",
    "contracts": "проверить контракты стыков",
    "reconcile": "сверить БФТ с картой (скрипт)",
    "reqs": "инвентарь требований БФТ",
    "confluence_page": "подготовить страницу Confluence локально (без отправки)",
}


def run_action(ws: Workspace, epic: str, action: str) -> dict:
    """Детерминированное действие. Модель не вызывается; код 0 — без ошибок."""
    epic = check_slug(epic)
    if action not in ACTIONS:
        raise BlueprintError(f"нет действия {action}; есть: {', '.join(ACTIONS)}")
    d, story, proj = _paths(ws, epic)
    sc = ws.scripts
    if action == "story_approve":
        from .core import approve_story
        meta = approve_story(ws, epic)
        render = _run([PY, str(sc / "bft-story-render.py"), str(story)], d)   # страница несёт статус — пересобрать
        return {**render, "output": "история согласована\n" + render["output"], **meta}
    if action == "story_render":
        if not story.is_file():
            raise BlueprintError("истории нет — blueprint_submit_story", 409)
        lint = _run([PY, str(sc / "bft-story-lint.py"), str(story)], d)
        if not lint["ok"]:
            return {**lint, "output": "проверка истории:\n" + lint["output"]}
        render = _run([PY, str(sc / "bft-story-render.py"), str(story)], d)
        return {**render, "output": "проверка истории: 0 ошибок\n" + lint["output"] + "\n\nсборка:\n" + render["output"]}
    if action in ("init_map", "init_map_auto"):
        if not story.is_file():
            raise BlueprintError("истории нет", 409)
        if (proj / "backlog").is_dir():
            return _run([PY, str(sc / "bft-backlog-init.py"), "--guides", str(proj)], d)
        cmd = [PY, str(sc / "bft-backlog-init.py"), str(story)] + (["--auto"] if action == "init_map_auto" else [])
        return _run(cmd, d)
    _need_project(proj)
    bp = proj / "blueprint.py"
    runner = [PY, str(bp)] if bp.is_file() else None
    sub = {"skeleton": ["skeleton"], "apply": ["apply"], "next": ["next"], "lint": ["lint"], "build": ["build"],
           "contracts": ["contracts"], "reconcile": ["reconcile"], "reqs": ["reqs"], "confluence_page": ["confluence", "page"]}
    if action == "verify":
        return _run([PY, str(sc / "bft-blueprint-verify.py"), str(d)], d)
    if runner is None:
        raise BlueprintError("в проекте нет ./blueprint.py — blueprint_run init_map обновит скрипты", 409)
    timeout = 600 if action in ("build", "apply") else TIMEOUT
    return _run(runner + sub[action], proj, timeout)


# ---------------------------------------------------------------- тексты агента ----------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text.replace("\r\n", "\n").rstrip() + "\n", encoding="utf-8")
    tmp.replace(path)


def _text(arg: str, name: str = "markdown", limit: int = 600_000) -> str:
    if not isinstance(arg, str) or not arg.strip():
        raise BlueprintError(f"пустой {name}")
    if len(arg) > limit:
        raise BlueprintError(f"{name} больше {limit} знаков")
    return arg


def submit_story(ws: Workspace, epic: str, markdown: str) -> dict:
    """История от агента → <epic>-story.md, проверка и страница. Ошибки линтера — в ответе: исправь и пришли снова."""
    epic = check_slug(epic)
    d = ws.epic_dir(epic)
    if not d.is_dir():
        raise BlueprintError(f"эпика {epic} нет", 404)
    text = _text(markdown)
    if not text.lstrip().startswith("---"):
        raise BlueprintError("история начинается с frontmatter (templates/story.md: epic_slug, stage: story, source_doc, version, revised, status)")
    _write(d / f"{epic}-story.md", text)
    return run_action(ws, epic, "story_render")


def read_plan(ws: Workspace, epic: str) -> dict:
    _, _, proj = _paths(ws, epic)
    _need_project(proj)
    plan = proj / "plan" / "map.md"
    if not plan.is_file():
        exp = run_action(ws, epic, "skeleton") if not any((proj / "backlog" / "tasks").glob("*.md")) else _run([PY, str(proj / "blueprint.py"), "export"], proj)
        if not plan.is_file():
            return {"exists": False, "output": exp["output"]}
    return {"exists": True, "path": ws.rel(plan), "markdown": plan.read_text(encoding="utf-8")}


def submit_plan(ws: Workspace, epic: str, markdown: str, screens: dict | None = None) -> dict:
    """План карты (plan/map.md, экраны plan/screens/*.md) → ./blueprint.py apply: задачи, карточки, документы и проверка."""
    _, _, proj = _paths(ws, epic)
    _need_project(proj)
    _write(proj / "plan" / "map.md", _text(markdown))
    for name, body in (screens or {}).items():
        if not re.fullmatch(r"[A-Za-z0-9._ -]{1,80}\.md", name):
            raise BlueprintError(f"имя файла экрана {name!r}: латиница, цифры, .md")
        _write(proj / "plan" / "screens" / name, _text(body, name))
    return run_action(ws, epic, "apply")


def submit_doc(ws: Workspace, epic: str, kind: str, markdown: str) -> dict:
    """Документ этапа (ADR, Системные требования, Стыки, План релиза, Roadmap, Риски, Расхождения) в проект карты.

    Тело — markdown с маркером `<!-- bft-<вид> … -->` в начале (шаблоны templates/*.md навыка). Документ того же
    вида уже есть — тело заменяется, ID и frontmatter Backlog.md сохраняются. Затем проверка карты.
    """
    _, _, proj = _paths(ws, epic)
    _need_project(proj)
    kinds = {v: k for k, v in DOC_KINDS.items() if v in DOC_TITLES}
    if kind not in kinds:
        raise BlueprintError(f"вид документа: {', '.join(kinds)}")
    body = _text(markdown).lstrip()
    marker = kinds[kind]
    if not re.match(rf"<!--\s*{marker}\s*\n", body):
        raise BlueprintError(f"тело начинается с маркера <!-- {marker} … --> (шаблон навыка templates/)")
    f = collect(ws, epic, deep=False)
    existing = ((f.get("project") or {}).get("docs") or {}).get(kind)
    if existing:
        path = ws.root / existing["file"]
    else:
        r = _run([PY, str(proj / "backlog.py"), "doc", "create", DOC_TITLES[kind], "-t", "specification"], proj)
        if not r["ok"]:
            raise BlueprintError("backlog doc create: " + r["output"], 502)
        m = re.search(r"doc-\d+", r["output"])
        found = sorted((proj / "backlog" / "docs").glob(f"{m.group(0)} - *.md")) if m else []
        if not found:
            raise BlueprintError("документ создан, но файл не найден: " + r["output"], 502)
        path = found[0]
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3) if text.startswith("---") else -1
    head = text[: end + 4] if end > 0 else "---\n---"
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    head = re.sub(r"^updated_date:.*$", f"updated_date: '{now}'", head, flags=re.M) if "updated_date:" in head else head.replace("\n---", f"\nupdated_date: '{now}'\n---", 1)
    _write(path, head + "\n" + body)
    check = run_action(ws, epic, "lint")
    return {**check, "doc": ws.rel(path)}


def submit_contract(ws: Workspace, epic: str, contract_id: str, markdown: str) -> dict:
    _, _, proj = _paths(ws, epic)
    _need_project(proj)
    if not re.fullmatch(r"C-\d{1,3}", contract_id or ""):
        raise BlueprintError("ID контракта — C-N")
    _write(proj / "contracts" / f"{contract_id}.md", _text(markdown))
    return run_action(ws, epic, "contracts")


def read_artifact(ws: Workspace, epic: str, what: str) -> dict:
    """Текст артефакта для агента: bft, story, plan, map (паспорт), doc:<вид>, contract:C-N, file:<путь в проекте>."""
    d, story, proj = _paths(ws, epic)
    f = collect(ws, epic, deep=False)
    if what == "bft":
        if not f.get("bft_path"):
            raise BlueprintError("БФТ нет", 404)
        path = ws.root / f["bft_path"]
    elif what == "story":
        path = story
    elif what == "plan":
        return read_plan(ws, epic)
    elif what.startswith("doc:") or what == "map":
        kind = "map" if what == "map" else what[4:]
        doc = ((f.get("project") or {}).get("docs") or {}).get(kind)
        if not doc:
            raise BlueprintError(f"документа {kind} в проекте нет", 404)
        path = ws.root / doc["file"]
    elif what.startswith("contract:"):
        path = proj / "contracts" / f"{what[9:]}.md"
    elif what.startswith("file:"):
        path = (proj / what[5:]).resolve()
        if proj.resolve() not in path.parents:
            raise BlueprintError("путь вне проекта карты")
    else:
        raise BlueprintError("что читать: bft, story, plan, map, doc:<adr|sysreq|seams|release|roadmap|risks|deviations>, contract:C-N, file:<путь>")
    if not path.is_file():
        raise BlueprintError(f"{ws.rel(path)} нет", 404)
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"path": ws.rel(path), "markdown": text[:400_000], "truncated": len(text) > 400_000}


# ---------------------------------------------------------------- фоновый агент ----------

class Jobs:
    """Фоновые ходы агента по этапу. Команда — из настроек (`agent.command`), `{prompt}` подставляется.

    Без настройки агент выключен: интерфейс и MCP отдают черновик команды, а запускает её человек
    в своём чате. Один ход на эпик за раз — два агента над одним проектом карты перепишут друг друга.
    """

    def __init__(self, state_dir: Path, agent: dict | None, ws: Workspace):
        self.dir = Path(state_dir).expanduser() / "jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.agent = agent or {}
        self.ws = ws
        self.lock = threading.Lock()
        self.procs: dict[str, subprocess.Popen] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.agent.get("command"))

    def _meta(self, jid: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{12}", jid or ""):
            raise BlueprintError("неверный id хода")
        return self.dir / f"{jid}.json"

    def get(self, jid: str, tail: int = 8000) -> dict:
        p = self._meta(jid)
        if not p.is_file():
            raise BlueprintError("хода нет", 404)
        meta = json.loads(p.read_text(encoding="utf-8"))
        log = self.dir / f"{jid}.log"
        meta["log"] = log.read_text(encoding="utf-8", errors="replace")[-tail:] if log.is_file() else ""
        return meta

    def list(self, epic: str | None = None, limit: int = 20) -> list[dict]:
        out = []
        for p in sorted(self.dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if epic and m.get("epic") != epic:
                continue
            out.append(m)
            if len(out) >= limit:
                break
        return out

    def running(self, epic: str) -> dict | None:
        return next((j for j in self.list(epic, 5) if j.get("state") == "running"), None)

    def start(self, epic: str, stage: str, prompt: str, note: str = "") -> dict:
        if not self.enabled:
            raise BlueprintError("фоновый агент не настроен (agent.command) — отправьте команду в свой чат или через MCP", 409)
        epic = check_slug(epic)
        with self.lock:
            busy = self.running(epic)
            if busy:
                raise BlueprintError(f"по эпику уже идёт ход {busy['id']} ({busy['stage']})", 409)
            jid = uuid.uuid4().hex[:12]
            text = prompt + (f"\n\nКомментарий PO: {note.strip()}" if note and note.strip() else "")
            cmd = [str(a).replace("{prompt}", text) for a in self.agent["command"]]
            meta = {"id": jid, "epic": epic, "stage": stage, "prompt": text, "state": "running",
                    "started": dt.datetime.now().isoformat(timespec="seconds"), "finished": None, "code": None}
            self._meta(jid).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            log = open(self.dir / f"{jid}.log", "w", encoding="utf-8")
            try:
                proc = subprocess.Popen(cmd, cwd=str(self.ws.root), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        env={**os.environ, **{k: str(v) for k, v in (self.agent.get("env") or {}).items()}},
                                        start_new_session=True)
            except OSError as e:
                log.close()
                meta.update(state="failed", finished=meta["started"], code=-1)
                self._meta(jid).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                raise BlueprintError(f"агент не запустился: {e}", 502) from None
            self.procs[jid] = proc
        threading.Thread(target=self._wait, args=(jid, proc, log, meta), daemon=True).start()
        return meta

    def _wait(self, jid: str, proc: subprocess.Popen, log, meta: dict) -> None:
        try:
            code = proc.wait(timeout=int(self.agent.get("timeout", 3600)))
        except subprocess.TimeoutExpired:
            proc.kill()
            code = -9
        log.close()
        meta.update(state="done" if code == 0 else "failed", code=code, finished=dt.datetime.now().isoformat(timespec="seconds"))
        if meta.get("stopped"):
            meta["state"] = "stopped"
        self._meta(jid).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        self.procs.pop(jid, None)

    def stop(self, jid: str) -> dict:
        proc = self.procs.get(jid)
        if not proc:
            raise BlueprintError("ход не идёт", 409)
        meta = self.get(jid)
        meta.pop("log", None)
        meta["stopped"] = True
        self._meta(jid).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        proc.terminate()
        return {"id": jid, "state": "stopping"}

    def mark_interrupted(self) -> None:
        """После перезапуска сервиса ходы «running» оборвались — не держим эпик занятым навсегда."""
        for p in self.dir.glob("*.json"):
            try:
                m = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if m.get("state") == "running":
                m.update(state="interrupted", finished=dt.datetime.now().isoformat(timespec="seconds"))
                p.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

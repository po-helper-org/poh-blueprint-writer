"""MCP «Система Blueprint»: Service Blueprint по БФТ для внешнего ИИ-агента.

По образцу MCP «Система БФТ» портала: текст пишет модель агента (его токены), сервис даёт методологию,
шаблоны и правила навыка `/bft-blueprint`, проверки и сборку скриптами, хранит артефакты в воркспейсе —
тех же, что видит раздел Blueprint. Модель сервиса в цикле MCP не вызывается (кроме явного
`blueprint_start_agent`, если фоновый агент настроен).

Транспорты: Streamable HTTP без сессий (`POST /blueprint/mcp`, Bearer-токен) и stdio
(`python3 server.py mcp` — для Claude Code, харнесса, любого MCP-клиента на той же машине).
Протокол — минимум, который понимают клиенты: initialize, ping, tools/*, prompts/*, resources/*.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import actions, core
from .core import BlueprintError

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

INSTRUCTIONS = """«Система Blueprint» — Service Blueprint (карта инициативы) по готовому БФТ эпика по методологии /bft-blueprint.
Пишешь тексты ты (своей моделью); сервис хранит артефакты, проверяет их линтерами навыка и собирает страницы скриптами.
Цикл: blueprint_list → blueprint_get (этапы и следующий шаг) → blueprint_guide (что прочитать и как писать этап) →
история: blueprint_read bft → blueprint_submit_story (до 0 ошибок) → PO согласует (blueprint_run story_approve только по его слову) →
карта: blueprint_run init_map → blueprint_read plan (каркас) → blueprint_submit_plan (до 0 ошибок) → blueprint_run build →
ADR/СТ, Стыки, План релиза, Расхождения: blueprint_submit_doc; контракты — blueprint_submit_contract → blueprint_run reconcile/verify →
Confluence: blueprint_run confluence_page, публикация — своим Atlassian MCP.
Вопросы карты — blueprint_questions; ответ PO записывай blueprint_answer только с его слов. Неизвестное — открытым вопросом, не выдумывай.
Подробно — промт blueprint_full_cycle и ресурс blueprint://guide."""


def _epic(args: dict) -> str:
    return core.check_slug(str(args.get("epic") or ""))


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _result(r: dict) -> str:
    """Вывод скрипта — агенту как есть: там адреса строк и подсказки, как исправить."""
    head = "✅ без ошибок" if r.get("ok") else f"❌ код {r.get('code')}"
    extra = {k: v for k, v in r.items() if k not in ("ok", "code", "output", "command", "seconds")}
    tail = ("\n" + _dump(extra)) if extra else ""
    return f"{head} — {r.get('command', '')}\n\n{r.get('output', '')}{tail}"


EPIC = {"type": "string", "description": "слаг эпика — имя папки в каталоге документов БФТ"}
MD = {"type": "string", "description": "markdown целиком"}


def _schema(props: dict, required: list) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


GUIDE_BY_STAGE = {
    "bft": ("БФТ — источник карты. Карта строится по полному БФТ (stage: deep). Есть только fast — предупреди PO: ФТ/ИТ/НФТ скелет, карта выйдет тонкой.",
            ["blueprint://skills/bft-blueprint"]),
    "story": ("История через экраны: персонажи, этапы латиницей, шаги «Знакомьтесь» → … → «И с тех пор», на шаг 1–2 экрана с контуром. "
              "Прочитай БФТ (blueprint_read bft), стандарт и шаблон, напиши <epic>-story.md и пришли blueprint_submit_story — повторяй до 0 ошибок. "
              "Пробелы БФТ — до четырёх вопросов PO одним раундом, остальное — в «Вопросы». Согласование — только слово PO.",
              ["blueprint://rules/story_line", "blueprint://rules/story_interview", "blueprint://templates/story", "blueprint://examples/golden_story"]),
    "map": ("Карта — проект Backlog.md. blueprint_run init_map, затем blueprint_read plan (каркас из БФТ, текст — {{…}}), заполни план "
            "по правилам и пришли blueprint_submit_plan — ответ несёт ошибки с адресами строк плана; повторяй до 0. Затем blueprint_run build.",
            ["blueprint://rules/autopilot", "blueprint://rules/backlog_rules", "blueprint://rules/card_rules", "blueprint://templates/map", "blueprint://rules/screen_notes"]),
    "adr": ("ADR и Системные требования — когда на карте есть слой Technology. Два документа: blueprint_submit_doc kind=adr, затем kind=sysreq.",
            ["blueprint://templates/adr", "blueprint://templates/sysreq", "blueprint://skills/adr", "blueprint://skills/system-requirements"]),
    "seams": ("Стыки — когда команд на карте две и больше: документ kind=seams (участники S…, обязательства D…, контракты, точки K…, риски R…) "
              "и контракты contracts/C-N.md через blueprint_submit_contract (проверка CT001–CT020).",
              ["blueprint://templates/seams", "blueprint://templates/contract", "blueprint://rules/contracts"]),
    "reconcile": ("Сверка: blueprint_run reconcile покажет требования БФТ «нет на карте». Потерянную работу верни на карту (план), "
                  "отход от БФТ — строкой реестра kind=deviations с решением или эскалацией PO.", ["blueprint://skills/bft-reconcile"]),
    "release": ("План релиза: дорожки DEV/STAGE/PROD, шаги R…, ворота. Неизвестное — [УТОЧНИТЬ] и вопрос владельцу. blueprint_submit_doc kind=release.",
                ["blueprint://skills/release-plan"]),
    "prototype": ("Прототип по готовой карте — маршрут навыка --prototype (запускается в чате агента с доступом к файлам).", ["blueprint://rules/prototype"]),
    "confluence": ("blueprint_run confluence_page готовит confluence/page.xhtml локально; публикуешь ты своим Atlassian MCP дочерней страницей под страницей БФТ.",
                   ["blueprint://skills/bft-confluence"]),
}


class BlueprintMcp:
    def __init__(self, ws: core.Workspace, jobs: actions.Jobs | None = None, version: str = "1.0.0"):
        self.ws, self.jobs, self.version = ws, jobs, version
        self.tools = self._tools()
        self.resources = self._resources()

    # ---------------- инструменты ----------------
    def _tools(self) -> list[dict]:
        ws = self.ws
        T = []

        def tool(name, title, description, props, required, fn):
            T.append({"name": name, "title": title, "description": description, "inputSchema": _schema(props, required), "fn": fn})

        def t_list(a):
            maps, cands = core.list_epics(ws)
            return _dump({"diagrams": maps, "bft_without_diagram": cands})
        tool("blueprint_list", "Диаграммы", "Список Service Blueprint воркспейса: этап каждой, прогресс, следующий шаг, счётчики; и БФТ, по которым диаграммы ещё нет.",
             {}, [], t_list)

        tool("blueprint_get", "Диаграмма", "Диаграмма эпика: все этапы по порядку (done/review/ready/stale/blocked/skipped/optional), чего не хватает, команда навыка и детерминированные действия.",
             {"epic": EPIC}, ["epic"], lambda a: _dump(core.detail(ws, _epic(a))))

        def t_guide(a):
            d = core.detail(ws, _epic(a))
            key = a.get("stage") or (d["next"] or {}).get("key") or "map"
            if key not in GUIDE_BY_STAGE:
                raise BlueprintError(f"этап: {', '.join(GUIDE_BY_STAGE)}")
            st = next(s for s in d["stages"] if s["key"] == key)
            text, res = GUIDE_BY_STAGE[key]
            return _dump({"stage": st, "how": text, "read_resources": res, "skill_command": st["command"]})
        tool("blueprint_guide", "Как делать этап", "Инструкция этапа: что прочитать (ресурсы blueprint://), как писать и чем проверить. Без stage — следующий этап диаграммы.",
             {"epic": EPIC, "stage": {"type": "string", "enum": list(GUIDE_BY_STAGE)}}, ["epic"], t_guide)

        tool("blueprint_read", "Прочитать артефакт", "Текст артефакта: bft, story, plan (каркас создаётся, если плана нет), map (паспорт), doc:<adr|sysreq|seams|release|roadmap|risks|deviations>, contract:C-N, file:<путь в проекте карты>.",
             {"epic": EPIC, "what": {"type": "string"}}, ["epic", "what"], lambda a: _dump(actions.read_artifact(ws, _epic(a), str(a.get("what") or ""))))

        tool("blueprint_submit_story", "Записать историю", "История через экраны (<epic>-story.md целиком, с frontmatter) → проверка bft-story-lint и страница. Ошибки — в ответе: исправь и пришли снова.",
             {"epic": EPIC, "markdown": MD}, ["epic", "markdown"], lambda a: _result(actions.submit_story(ws, _epic(a), a.get("markdown"))))

        tool("blueprint_submit_plan", "Записать план карты", "План карты plan/map.md (и экраны plan/screens/<файл>.md) → ./blueprint.py apply: задачи, карточки, документы проекта и проверка с адресами строк плана.",
             {"epic": EPIC, "markdown": MD, "screens": {"type": "object", "additionalProperties": {"type": "string"}, "description": "{имя файла: markdown} — требования к экранам"}},
             ["epic", "markdown"], lambda a: _result(actions.submit_plan(ws, _epic(a), a.get("markdown"), a.get("screens"))))

        tool("blueprint_submit_doc", "Записать документ этапа", "Документ этапа в проект карты: adr, sysreq, seams, release, roadmap, risks, deviations. Тело начинается с маркера <!-- bft-<вид> … --> по шаблону навыка; повтор заменяет тело того же документа.",
             {"epic": EPIC, "kind": {"type": "string", "enum": ["adr", "sysreq", "seams", "release", "roadmap", "risks", "deviations"]}, "markdown": MD},
             ["epic", "kind", "markdown"], lambda a: _result(actions.submit_doc(ws, _epic(a), str(a.get("kind")), a.get("markdown"))))

        tool("blueprint_submit_contract", "Записать контракт стыка", "Контракт стыка contracts/C-N.md по шаблону навыка → ./blueprint.py contracts (CT001–CT020).",
             {"epic": EPIC, "id": {"type": "string", "description": "C-N"}, "markdown": MD}, ["epic", "id", "markdown"],
             lambda a: _result(actions.submit_contract(ws, _epic(a), str(a.get("id")), a.get("markdown"))))

        tool("blueprint_run", "Действие без модели", "Детерминированное действие скриптами навыка: " + "; ".join(f"{k} — {v}" for k, v in actions.ACTIONS.items())
             + ". story_approve — только по явному слову PO.",
             {"epic": EPIC, "action": {"type": "string", "enum": list(actions.ACTIONS)}}, ["epic", "action"],
             lambda a: _result(actions.run_action(ws, _epic(a), str(a.get("action")))))

        tool("blueprint_questions", "Вопросы карты", "Вопросы паспорта «Карта»: кому, что, где на карте, тип (блокер/вопрос), ответ.",
             {"epic": EPIC, "open_only": {"type": "boolean"}}, ["epic"],
             lambda a: _dump([q for q in core.questions(ws, _epic(a)) if q["open"] or not a.get("open_only")]))

        tool("blueprint_answer", "Ответ на вопрос", "Записать ответ на вопрос «Карты» (с пометкой кто и когда). Только со слов PO или адресата; затем blueprint_run build.",
             {"epic": EPIC, "id": {"type": "string", "description": "ID вопроса, например В3"}, "answer": {"type": "string"}, "who": {"type": "string", "description": "кто ответил, по умолчанию PO"}},
             ["epic", "id", "answer"], lambda a: _dump(core.answer_question(ws, _epic(a), str(a.get("id")), str(a.get("answer") or ""), str(a.get("who") or "PO"))))

        if self.jobs is not None:
            def t_start(a):
                epic = _epic(a)
                d = core.detail(ws, epic)
                key = a.get("stage") or (d["next"] or {}).get("key")
                st = next((s for s in d["stages"] if s["key"] == key), None)
                if not st or not st["command"]:
                    raise BlueprintError("у этапа нет команды для агента")
                return _dump(self.jobs.start(epic, key, st["command"], str(a.get("note") or "")))
            tool("blueprint_start_agent", "Запустить фоновый агент", "Фоновый ход агента сервиса по этапу (если настроен). Обычно не нужен: этап делаешь ты сам инструментами выше.",
                 {"epic": EPIC, "stage": {"type": "string"}, "note": {"type": "string"}}, ["epic"], t_start)
            tool("blueprint_job", "Ход агента", "Состояние фонового хода и хвост журнала.", {"id": {"type": "string"}}, ["id"],
                 lambda a: _dump(self.jobs.get(str(a.get("id")))))
        return T

    # ---------------- ресурсы ----------------
    def _resources(self) -> list[dict]:
        sk = self.ws.skills
        bp = sk / "bft-blueprint"
        res = [("blueprint://guide", "Путеводитель по циклу", None, lambda: GUIDE),
               ("blueprint://skills/bft-blueprint", "Навык bft-blueprint", bp / "SKILL.md", None)]
        for name in ("adr", "system-requirements", "bft-reconcile", "release-plan"):
            res.append((f"blueprint://skills/{name}", f"Навык {name}", sk / name / "SKILL.md", None))
        res.append(("blueprint://skills/bft-confluence", "Команда bft-confluence", sk.parent / "commands" / "bft-confluence.md", None))
        for f in sorted((bp / "resources").glob("*.md")):
            res.append((f"blueprint://rules/{f.stem}", f"Правила: {f.stem}", f, None))
        for f in sorted((bp / "templates").glob("*.md")):
            res.append((f"blueprint://templates/{f.stem}", f"Шаблон: {f.stem}", f, None))
        for stem in ("golden_story", "golden_blueprint"):
            res.append((f"blueprint://examples/{stem}", f"Эталон: {stem}", bp / "examples" / f"{stem}.md", None))
        out = []
        for uri, name, path, fn in res:
            if path is not None and not path.is_file():
                continue
            out.append({"uri": uri, "name": name, "mimeType": "text/markdown",
                        "read": fn or (lambda p=path: p.read_text(encoding="utf-8"))})
        return out

    # ---------------- протокол ----------------
    def handle(self, req: dict) -> dict | None:
        if not isinstance(req, dict) or not isinstance(req.get("method"), str):
            return _err(req.get("id") if isinstance(req, dict) else None, -32600, "нет method")
        if "id" not in req:
            return None   # уведомление
        rid, m, params = req["id"], req["method"], req.get("params") or {}
        try:
            if m == "initialize":
                asked = str(params.get("protocolVersion") or "")
                return _ok(rid, {"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                                 "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False},
                                                  "resources": {"listChanged": False, "subscribe": False}},
                                 "serverInfo": {"name": "blueprint-system", "version": self.version}, "instructions": INSTRUCTIONS})
            if m == "ping":
                return _ok(rid, {})
            if m == "tools/list":
                return _ok(rid, {"tools": [{k: t[k] for k in ("name", "title", "description", "inputSchema")} for t in self.tools]})
            if m == "tools/call":
                t = next((t for t in self.tools if t["name"] == params.get("name")), None)
                if not t:
                    return _err(rid, -32602, f"нет инструмента {params.get('name')}")
                args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
                try:
                    text, is_err = t["fn"](args), False
                except BlueprintError as e:
                    text, is_err = str(e), True
                except Exception as e:  # noqa: BLE001
                    text, is_err = f"ошибка сервиса: {type(e).__name__}: {e}", True
                return _ok(rid, {"content": [{"type": "text", "text": text}], "isError": is_err})
            if m == "prompts/list":
                return _ok(rid, {"prompts": [PROMPT_META]})
            if m == "prompts/get":
                if params.get("name") != PROMPT_META["name"]:
                    return _err(rid, -32602, f"нет промта {params.get('name')}")
                epic = (params.get("arguments") or {}).get("epic") or "<epic>"
                return _ok(rid, {"description": PROMPT_META["description"],
                                 "messages": [{"role": "user", "content": {"type": "text", "text": FULL_CYCLE.replace("<epic>", epic)}}]})
            if m == "resources/list":
                return _ok(rid, {"resources": [{k: r[k] for k in ("uri", "name", "mimeType")} for r in self.resources]})
            if m == "resources/read":
                r = next((r for r in self.resources if r["uri"] == params.get("uri")), None)
                if not r:
                    return _err(rid, -32602, f"нет ресурса {params.get('uri')}")
                return _ok(rid, {"contents": [{"uri": r["uri"], "mimeType": r["mimeType"], "text": r["read"]()}]})
            return _err(rid, -32601, f"метод {m} не поддерживается")
        except Exception as e:  # noqa: BLE001
            return _err(rid, -32603, f"{type(e).__name__}: {e}")

    def handle_body(self, body) -> object | None:
        """Тело POST: один запрос или пакет. None — ответа нет (только уведомления)."""
        if isinstance(body, list):
            if not 1 <= len(body) <= 20:
                return _err(None, -32600, "пакет — от 1 до 20 запросов")
            out = [r for r in (self.handle(x) for x in body) if r is not None]
            return out or None
        return self.handle(body)

    def serve_stdio(self, stdin=sys.stdin, stdout=sys.stdout) -> None:
        """MCP stdio: по JSON-сообщению на строку."""
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                body = json.loads(line)
            except ValueError:
                resp = _err(None, -32700, "не JSON")
            else:
                resp = self.handle_body(body)
            if resp is not None:
                stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                stdout.flush()


def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


PROMPT_META = {"name": "blueprint_full_cycle", "description": "Провести эпик от БФТ до отгруженной карты инициативы",
               "arguments": [{"name": "epic", "description": "слаг эпика", "required": False}]}

FULL_CYCLE = """Собери Service Blueprint эпика <epic> через «Систему Blueprint».

1. blueprint_get <epic> — этапы и следующий шаг. Нет эпика — blueprint_list: выбери БФТ из bft_without_diagram.
2. На каждом этапе: blueprint_guide (что читать) → ресурсы blueprint:// → пишешь текст → blueprint_submit_* →
   исправляешь по выводу проверки, пока не «✅ без ошибок».
3. История: после 0 ошибок покажи PO было → стало по персонажам и открытые вопросы. Согласование (blueprint_run story_approve) — только после его «да».
4. Карта: init_map → read plan → submit_plan до 0 ошибок → build. Вопросы, которые не закрыть по БФТ, — в «Вопросы» плана.
5. Дальше по blueprint_get: ADR/СТ (если есть Technology), Стыки и контракты (если команд ≥ 2), сверка reconcile, план релиза.
6. В конце — blueprint_run verify, затем confluence_page и публикация своим Atlassian MCP под страницей БФТ.
Ты — картограф: только то, что есть в БФТ и словах PO; неизвестное — открытым вопросом «кому — что»."""

GUIDE = FULL_CYCLE.replace("<epic>", "эпика") + "\n\n" + "\n".join(f"- **{k}** — {v[0]}" for k, v in GUIDE_BY_STAGE.items())

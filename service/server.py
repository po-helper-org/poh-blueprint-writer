#!/usr/bin/env python3
"""Сервис Blueprint: список Service Blueprint диаграмм, поэтапная работа над картой и MCP «Система Blueprint».

  GET  /blueprint/                         список диаграмм (статика, данных нет)
  GET  /blueprint/<эпик>                   диаграмма отдельной страницей: собранная карта, до неё — история
  GET  /blueprint/api/list|map|questions|file|jobs|job|config      ┐ за гейтом (corp: X-Corp-Gate от nginx,
  GET  /blueprint/api/page?epic=&kind=map|story — страница в песочнице │  basic: HTTP Basic, none: только 127.0.0.1)
  POST /blueprint/api/run|answer|agent|stop — заголовок X-Blueprint: 1 ┘
  POST /blueprint/mcp                      MCP Streamable HTTP, Authorization: Bearer <токен из mcp_tokens_file>

  python3 server.py            веб-сервис (настройки — POH_BLUEPRINT_CONFIG, по умолчанию ~/.config/poh-blueprint/config.json)
  python3 server.py mcp        MCP по stdio — для Claude Code, харнесса и любого MCP-клиента на этой машине
  python3 server.py list       список диаграмм в терминал (проверка настройки)

Только стандартная библиотека Python 3.10+, как и скрипты навыка.
"""
from __future__ import annotations

import base64
import hmac
import json
import mimetypes
import os
import re
import sys
import traceback
import urllib.parse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from blueprint_service import actions, core  # noqa: E402
from blueprint_service.core import BlueprintError  # noqa: E402
from blueprint_service.mcp import BlueprintMcp  # noqa: E402

WIDGET = HERE / "widget"
CONFIG = os.environ.get("POH_BLUEPRINT_CONFIG", "~/.config/poh-blueprint/config.json")
DEFAULTS = {
    "listen": "127.0.0.1:8662",
    "base": "/blueprint",
    "workspace": ".",                 # корень воркспейса: там агент запускается, от него пути в командах
    "docs_path": "",                  # пусто — .bft/documentation или bft/documentation
    "skills_path": "",                # пусто — skills/ этого репозитория
    "state_dir": "~/.local/state/poh-blueprint",
    "gate_mode": "none",              # corp | basic | none
    "gate_secret_file": "~/.config/corp-link/gate-secret",
    "mcp_tokens_file": "~/.config/poh-blueprint/mcp-tokens",
    "public_url": "",                 # внешний адрес сервиса — для подсказки «как подключить MCP»
    "agent": None,                    # {"command": ["claude", "-p", "{prompt}", ...], "timeout": 3600}
}
# Страницы карты и истории — самодостаточные, со своими скриптами: только в песочнице без same-origin.
PAGE_CSP = ("sandbox allow-scripts allow-popups allow-downloads; default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline' data:; img-src data: blob:; font-src data:; frame-ancestors 'self'")
UI_CSP = ("frame-ancestors 'self' vector:; default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
          "img-src 'self' data:; connect-src 'self'; frame-src 'self'; base-uri 'none'; form-action 'self'")


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    path = Path(CONFIG).expanduser()
    if path.is_file():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    for key, env in (("workspace", "BLUEPRINT_WORKSPACE"), ("docs_path", "BLUEPRINT_DOCS_PATH"), ("skills_path", "BLUEPRINT_SKILLS_PATH"),
                     ("listen", "BLUEPRINT_LISTEN"), ("gate_mode", "BLUEPRINT_GATE")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


def read_secret(path: str) -> str | None:
    try:
        return Path(path).expanduser().read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def same(got: str, want: str | None) -> bool:
    return bool(want) and len(got) == len(want) and hmac.compare_digest(got.encode(), want.encode())


def mcp_tokens(cfg: dict) -> list[str]:
    """Файл токенов MCP: строка — `имя:токен` или просто токен; # — комментарий."""
    raw = read_secret(cfg["mcp_tokens_file"]) or ""
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split(":", 1)[1].strip() if ":" in line else line)
    return out


IMG_RE = re.compile(r'"((?:[\w.\- ]+/)*[\w.\- ·]+\.(?:svg|png|jpe?g|webp|gif))"')
IMG_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


def inline_images(page: Path) -> bytes:
    """Картинки экранов страницы карты — data: URI прямо в данных страницы.

    Страница ссылается на `<base>backlog/assets/screens/F3.svg` относительно себя. В песочнице без same-origin
    браузер не понесёт куки гейта с подзапросами, и картинки не загрузятся — поэтому сервис встраивает их сам.
    Берутся только файлы внутри папки эпика.
    """
    html = page.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'"base"\s*:\s*"([^"]*)"', html)
    root = (page.parent / (m.group(1) if m else "")).resolve()
    top = page.parent.resolve()
    cache: dict[str, str] = {}

    def sub(mt: re.Match) -> str:
        rel = mt.group(1)
        if rel not in cache:
            cache[rel] = mt.group(0)
            for cand in (root / rel, top / rel):
                f = cand.resolve()
                if (f == top or top in f.parents) and f.is_file() and f.stat().st_size < 3_000_000:
                    data = base64.b64encode(f.read_bytes()).decode()
                    cache[rel] = f'"data:{IMG_TYPES[f.suffix.lower()]};base64,{data}"'
                    break
        return cache[rel]

    return IMG_RE.sub(sub, html).encode("utf-8")


class App:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ws = core.Workspace.from_config(cfg)
        self.jobs = actions.Jobs(Path(cfg["state_dir"]), cfg.get("agent"), self.ws)
        self.jobs.mark_interrupted()
        self.mcp = BlueprintMcp(self.ws, self.jobs)
        self.base = "/" + cfg["base"].strip("/")


def make_handler(app: App):
    base = app.base

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "poh-blueprint"

        def log_message(self, fmt, *args):
            pass   # содержимое карт в журнал не пишем; статусы видны в nginx

        # ---------- ответ ----------
        def _reply(self, status, body=b"", ctype="application/json; charset=utf-8", headers=(), cache="no-store"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            if isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            if body and self.command != "HEAD":
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _err(self, status, code, message=""):
            return self._reply(status, {"ok": False, "error": code, "message": message})

        def _do(self, fn):
            try:
                return self._reply(200, {"ok": True, **fn()})
            except BlueprintError as e:
                return self._err(e.status, "blueprint", str(e))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                return self._err(500, "internal", f"ошибка сервиса: {type(e).__name__}")

        # ---------- доступ ----------
        def _gate_ok(self) -> bool:
            mode = app.cfg["gate_mode"]
            if mode == "corp":
                return same(self.headers.get("X-Corp-Gate") or "", read_secret(app.cfg["gate_secret_file"]))
            if mode == "basic":
                user, password = os.environ.get("BLUEPRINT_USER", "po"), os.environ.get("BLUEPRINT_PASSWORD", "")
                kind, _, token = (self.headers.get("Authorization") or "").partition(" ")
                try:
                    got_user, _, got_pass = base64.b64decode(token).decode().partition(":") if kind.lower() == "basic" else ("", "", "")
                except ValueError:
                    return False
                return bool(password) and same(got_user, user) and same(got_pass, password)
            return self.client_address[0] in ("127.0.0.1", "::1")

        def _deny(self):
            if app.cfg["gate_mode"] == "basic":
                return self._reply(401, {"ok": False, "error": "unauthorized", "message": "нужен вход"},
                                   headers=[("WWW-Authenticate", 'Basic realm="poh-blueprint", charset="UTF-8"')])
            return self._err(403, "forbidden", "нужен вход")

        def _mcp_ok(self) -> bool:
            kind, _, token = (self.headers.get("Authorization") or "").partition(" ")
            if kind.lower() == "bearer" and any(same(token.strip(), t) for t in mcp_tokens(app.cfg)):
                return True
            return app.cfg["gate_mode"] == "none" and self.client_address[0] in ("127.0.0.1", "::1")

        def _body(self, limit=1_000_000):
            n = int(self.headers.get("Content-Length") or 0)
            if n > limit:
                raise BlueprintError("тело запроса слишком большое", 413)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                return json.loads(raw or b"{}")
            except ValueError:
                raise BlueprintError("тело запроса — не JSON") from None

        # ---------- GET ----------
        def do_HEAD(self):
            return self.do_GET()

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            path, q = u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            if path == base:
                return self._reply(301, headers=[("Location", base + "/")])
            if path == base + "/mcp":
                return self._reply(405, "SSE-поток не поддерживается: шлите JSON-RPC через POST", "text/plain; charset=utf-8",
                                   headers=[("Allow", "POST, DELETE")])
            if path.startswith(base + "/api/"):
                if not self._gate_ok():
                    return self._deny()
                return self._api_get(path[len(base) + 5:], q)
            if path.startswith(base + "/"):
                rel = urllib.parse.unquote(path[len(base) + 1:]) or "index.html"
                if (WIDGET / rel).is_file() or rel == "login" or "/" in rel:
                    return self._static(rel)
                if not self._gate_ok():   # /blueprint/<эпик> — сама карта; вход на неё делает nginx (edge-auth)
                    return self._deny()
                return self._diagram(rel)
            return self._err(404, "not-found")

        def _static(self, rel: str):
            if rel == "login":
                rel = "authed.html"
            f = (WIDGET / rel).resolve()
            if WIDGET.resolve() not in f.parents or not f.is_file():
                return self._err(404, "not-found")
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
                ctype += "; charset=utf-8"
            return self._reply(200, f.read_bytes(), ctype, headers=[("Content-Security-Policy", UI_CSP)], cache="no-cache")

        def _api_get(self, name: str, q: dict):
            ws = app.ws
            if name == "list":
                def fn():
                    maps, cands = core.list_epics(ws)
                    return {"diagrams": maps, "candidates": cands, "docs": ws.rel(ws.docs) or ".", "running": [j for j in app.jobs.list(limit=50) if j.get("state") == "running"]}
                return self._do(fn)
            if name == "map":
                return self._do(lambda: {"map": core.detail(ws, q.get("epic", "")), "jobs": app.jobs.list(q.get("epic"), 10)})
            if name == "questions":
                return self._do(lambda: {"questions": core.questions(ws, q.get("epic", ""))})
            if name == "file":
                return self._do(lambda: actions.read_artifact(ws, q.get("epic", ""), q.get("what", "")))
            if name == "jobs":
                return self._do(lambda: {"jobs": app.jobs.list(q.get("epic"), 20)})
            if name == "job":
                return self._do(lambda: {"job": app.jobs.get(q.get("id", ""))})
            if name == "config":
                url = (app.cfg.get("public_url") or "").rstrip("/")
                return self._do(lambda: {"agent": app.jobs.enabled, "mcp_url": (url + base + "/mcp") if url else base + "/mcp",
                                         "docs": ws.rel(ws.docs), "actions": actions.ACTIONS})
            if name == "page":
                return self._page(q.get("epic", ""), q.get("kind", "map"))
            return self._err(404, "not-found")

        def _diagram(self, epic: str):
            """Страница диаграммы: собранная карта, а пока её нет — история. Обе — шаблоны навыка."""
            try:
                f = core.collect(app.ws, core.check_slug(epic), deep=False)
            except BlueprintError as e:
                return self._err(e.status, "blueprint", str(e))
            has_story = (f.get("story") or {}).get("html")
            if f.get("map_html_path"):
                return self._page(epic, "map")
            if has_story:
                return self._page(epic, "story")
            html = (f"<!doctype html><meta charset=utf-8><title>{escape(f['title'])}</title>"
                    "<body style='font:16px system-ui;max-width:560px;margin:15vh auto;padding:0 16px;color:#1c1c1e'>"
                    f"<h1 style='font-size:22px'>{escape(f['title'])}</h1><p style='color:#6e6e73'>Карта ещё не собрана.</p>"
                    f"<pre style='background:#f2f2f5;padding:12px;border-radius:12px'>/bft-blueprint {escape(epic)}</pre>")
            return self._reply(404 if not f.get("bft") else 200, html, "text/html; charset=utf-8", headers=[("Content-Security-Policy", PAGE_CSP)])

        def _page(self, epic: str, kind: str):
            try:
                f = core.collect(app.ws, core.check_slug(epic), deep=False)
            except BlueprintError as e:
                return self._err(e.status, "blueprint", str(e))
            if kind == "map":
                rel = f.get("map_html_path")
            elif kind == "story":
                rel = (f.get("story") or {}).get("path", "").replace(".md", ".html") if (f.get("story") or {}).get("html") else None
            else:
                return self._err(400, "blueprint", "kind: map | story")
            if not rel:
                return self._err(404, "blueprint", "страница ещё не собрана")
            p = (app.ws.root / rel).resolve()
            if app.ws.docs not in p.parents or not p.is_file():
                return self._err(404, "blueprint", "страницы нет")
            return self._reply(200, inline_images(p), "text/html; charset=utf-8", headers=[("Content-Security-Policy", PAGE_CSP)])

        # ---------- POST ----------
        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == base + "/mcp":
                return self._mcp()
            if not path.startswith(base + "/api/"):
                return self._err(404, "not-found")
            if not self._gate_ok():
                return self._deny()
            if self.headers.get("X-Blueprint") != "1":
                return self._err(403, "forbidden", "нет заголовка X-Blueprint")
            name = path[len(base) + 5:]
            try:
                body = self._body()
            except BlueprintError as e:
                return self._err(e.status, "blueprint", str(e))
            ws = app.ws
            if name == "run":
                return self._do(lambda: {"result": actions.run_action(ws, body.get("epic", ""), body.get("action", ""))})
            if name == "answer":
                return self._do(lambda: {"answer": core.answer_question(ws, body.get("epic", ""), body.get("id", ""), body.get("answer", ""), body.get("who") or "PO")})
            if name == "agent":
                def fn():
                    d = core.detail(ws, body.get("epic", ""))
                    key = body.get("stage") or (d["next"] or {}).get("key")
                    cmd = d["auto_command"] if key == "auto" else next((s["command"] for s in d["stages"] if s["key"] == key), "")
                    if not cmd:
                        raise BlueprintError("у этапа нет команды для агента")
                    return {"job": app.jobs.start(d["epic"], key, cmd, body.get("note", ""))}
                return self._do(fn)
            if name == "stop":
                return self._do(lambda: {"job": app.jobs.stop(body.get("id", ""))})
            return self._err(404, "not-found")

        def _mcp(self):
            if not self._mcp_ok():
                return self._reply(401, {"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "нужен токен MCP: Authorization: Bearer <токен>"}},
                                   headers=[("WWW-Authenticate", 'Bearer realm="blueprint-mcp", error="invalid_token"')])
            try:
                body = self._body(4_000_000)
            except BlueprintError:
                return self._reply(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "тело — не JSON"}})
            out = app.mcp.handle_body(body)
            if out is None:
                return self._reply(202)
            return self._reply(200, out)

        def do_DELETE(self):
            if urllib.parse.urlsplit(self.path).path == base + "/mcp":
                return self._reply(204)
            return self._err(405, "method-not-allowed")

    return Handler


def main(argv: list[str]) -> int:
    cfg = load_config()
    cmd = argv[1] if len(argv) > 1 else "serve"
    if cmd == "mcp":
        app = App(cfg)
        app.mcp.serve_stdio()
        return 0
    if cmd == "list":
        ws = core.Workspace.from_config(cfg)
        maps, cands = core.list_epics(ws)
        print(f"документы: {ws.docs}")
        for m in maps:
            nxt = m["next"]
            print(f"  {m['epic']:<32} {m['progress']['done']}/{m['progress']['total']}  дальше: {nxt['title'] if nxt else '—'}")
        for c in cands:
            print(f"  {c['epic']:<32} БФТ {c['bft']} — диаграммы нет")
        return 0
    if cmd != "serve":
        print(__doc__)
        return 2
    app = App(cfg)
    if cfg["gate_mode"] not in ("corp", "basic", "none"):
        print(f"gate_mode: corp | basic | none, а не {cfg['gate_mode']}", file=sys.stderr)
        return 2
    host, _, port = cfg["listen"].rpartition(":")
    if cfg["gate_mode"] == "none" and host not in ("127.0.0.1", "localhost", "::1"):
        print("gate_mode=none разрешён только на 127.0.0.1", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer((host or "127.0.0.1", int(port)), make_handler(app))
    print(f"poh-blueprint: http://{cfg['listen']}{app.base}/ · документы {app.ws.docs} · агент {'вкл' if app.jobs.enabled else 'выкл'}", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

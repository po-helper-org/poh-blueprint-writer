"""Тесты сервиса Blueprint: этапы по фактам, разбор эталонной карты, MCP и HTTP.

    python3 -m unittest discover -s service/tests -t service
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
REPO = SERVICE.parent
sys.path.insert(0, str(SERVICE))

from blueprint_service import actions, core  # noqa: E402
from blueprint_service.mcp import BlueprintMcp  # noqa: E402

EX = REPO / "skills" / "bft-blueprint" / "examples"
FX = REPO / "skills" / "bft-blueprint" / "scripts" / "fixtures"


def make_workspace(tmp: Path) -> Path:
    """Воркспейс: готовая эталонная карта, история-черновик без карты и БФТ без диаграммы."""
    docs = tmp / "bft" / "documentation"
    d = docs / "dineclub-restart"
    d.mkdir(parents=True)
    shutil.copytree(EX / "dineclub-restart-blueprint", d / "dineclub-restart-blueprint")
    shutil.copy(EX / "golden_story.md", d / "dineclub-restart-story.md")
    shutil.copy(EX / "golden_story.html", d / "dineclub-restart-story.html")
    shutil.copy(EX / "dineclub-restart-map.html", d / "dineclub-restart-map.html")
    shutil.copy(FX / "golden_deep_document.md", d / "dineclub-restart.md")
    f = docs / "direct-faq"
    f.mkdir()
    shutil.copy(FX / "golden_deep_document.md", f / "direct-faq.md")
    (f / "direct-faq-story.md").write_text((FX / "faq_story.md").read_text(encoding="utf-8"), encoding="utf-8")
    c = docs / "car-booking"
    c.mkdir()
    shutil.copy(FX / "car_deep_document.md", c / "car-booking.md")
    # страницы новее исходников — карта «собрана»
    now = time.time() + 5
    for p in (d / "dineclub-restart-map.html", d / "dineclub-restart-story.html"):
        import os
        os.utime(p, (now, now))
    return tmp


def facts(**kw) -> dict:
    base = {"epic": "e", "dir": "docs/e", "title": "E", "bft": "deep", "bft_path": "docs/e/e.md", "story": None, "project": None,
            "map_html": False, "map_html_path": None, "zip": False, "map_stale": False, "prototype": False, "confluence": None, "updated": None}
    base.update(kw)
    return base


STORY_OK = {"path": "docs/e/e-story.md", "status": "Согласован", "version": "1", "revised": "", "html": True, "html_stale": False}
PROJECT = {"path": "docs/e/e-blueprint", "docs": {}, "contracts": 0, "files": 5, "tasks": 5, "cards": 6, "subtasks": 0, "teams": [],
           "teams_on_map": 1, "technology": 0, "questions": 2, "questions_open": 1, "blockers_open": 0, "deviations": 0, "errors": 0}


class StagesTest(unittest.TestCase):
    """Чистая функция фактов → этапы: порядок работы и ворота."""

    def st(self, f):
        return {s.key: s for s in core.stages(f)}

    def test_no_bft_blocks_everything(self):
        s = self.st(facts(bft=None, bft_path=None))
        self.assertEqual(s["bft"].status, "blocked")
        self.assertEqual(s["story"].status, "blocked")
        self.assertEqual(s["map"].status, "blocked")

    def test_bft_only_next_is_story(self):
        st = core.stages(facts())
        self.assertEqual(core.next_stage(st).key, "story")
        self.assertIn("--story", core.next_stage(st).command)

    def test_draft_story_waits_for_po(self):
        s = self.st(facts(story={**STORY_OK, "status": "Черновик"}))
        self.assertEqual(s["story"].status, "review")
        self.assertIn("story_approve", [a["id"] for a in s["story"].actions])
        self.assertEqual(s["map"].status, "blocked")

    def test_stale_story_page(self):
        s = self.st(facts(story={**STORY_OK, "html_stale": True}))
        self.assertEqual(s["story"].status, "stale")

    def test_approved_story_opens_map(self):
        s = self.st(facts(story=STORY_OK))
        self.assertEqual(s["map"].status, "ready")
        self.assertIn("--map", s["map"].command)

    def test_map_without_page_needs_build(self):
        s = self.st(facts(story=STORY_OK, project=PROJECT))
        self.assertEqual(s["map"].status, "stale")
        self.assertIn("build", [a["id"] for a in s["map"].actions])

    def test_gates_after_map(self):
        s = self.st(facts(story=STORY_OK, project=PROJECT, map_html=True, map_html_path="docs/e/e-map.html"))
        self.assertEqual(s["map"].status, "done")
        self.assertEqual(s["adr"].status, "skipped")        # нет Technology
        self.assertEqual(s["seams"].status, "skipped")      # одна команда
        self.assertEqual(s["reconcile"].status, "ready")
        self.assertEqual(s["prototype"].status, "optional")
        self.assertEqual(core.next_stage(core.stages(facts(story=STORY_OK, project=PROJECT, map_html=True))).key, "reconcile")

    def test_technology_and_teams_require_adr_and_seams(self):
        p = {**PROJECT, "technology": 2, "teams_on_map": 3, "docs": {"adr": {"file": "x", "status": "Предложено"}}}
        s = self.st(facts(story=STORY_OK, project=p, map_html=True))
        self.assertEqual(s["adr"].status, "ready")
        self.assertIn("/system-requirements", s["adr"].command)   # ADR есть — дальше СТ
        self.assertEqual(s["seams"].status, "ready")

    def test_confluence_done_by_publish(self):
        s = self.st(facts(story=STORY_OK, project=PROJECT, map_html=True, confluence={"page_id": "42", "url": "", "parent": "", "prepared": True}))
        self.assertEqual(s["confluence"].status, "done")

    def test_progress_ignores_skipped_and_optional(self):
        st = core.stages(facts(story=STORY_OK, project=PROJECT, map_html=True))
        self.assertEqual(core.progress(st), {"done": 3, "total": 6})


class WorkspaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        make_workspace(cls.tmp)
        cls.ws = core.Workspace.from_config({"workspace": str(cls.tmp), "docs_path": "bft/documentation"})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_list_splits_diagrams_and_candidates(self):
        maps, cands = core.list_epics(self.ws)
        self.assertEqual({m["epic"] for m in maps}, {"dineclub-restart", "direct-faq"})
        self.assertEqual([c["epic"] for c in cands], ["car-booking"])

    def test_reference_map_facts(self):
        d = core.detail(self.ws, "dineclub-restart")
        st = {s["key"]: s["status"] for s in d["stages"]}
        self.assertEqual(st["map"], "done")
        self.assertEqual(st["adr"], "done")
        self.assertEqual(st["seams"], "done")
        self.assertEqual(st["reconcile"], "done")
        self.assertEqual(d["next"]["key"], "release")
        self.assertGreater(d["counts"]["tasks"], 0)
        self.assertGreater(d["counts"]["contracts"], 0)

    def test_slug_guard(self):
        for bad in ("../etc", "a/b", "", ".."):
            with self.assertRaises(core.BlueprintError):
                self.ws.epic_dir(bad)

    def test_questions_and_answer(self):
        qs = core.questions(self.ws, "dineclub-restart")
        first = next(q for q in qs if q["open"])
        core.answer_question(self.ws, "dineclub-restart", first["id"], "передадим списком | до пятницы", "DineClub")
        again = {q["id"]: q for q in core.questions(self.ws, "dineclub-restart")}
        self.assertFalse(again[first["id"]]["open"])
        self.assertIn("передадим списком / до пятницы (DineClub,", again[first["id"]]["answer"])

    def test_story_render_and_approve(self):
        r = actions.run_action(self.ws, "direct-faq", "story_render")
        self.assertTrue(r["ok"], r["output"])
        self.assertIn("story-lint", r["output"])
        self.assertTrue((self.ws.epic_dir("direct-faq") / "direct-faq-story.html").is_file())
        actions.run_action(self.ws, "direct-faq", "story_approve")
        f = core.collect(self.ws, "direct-faq")
        self.assertEqual(f["story"]["status"], "Согласован")

    def test_read_artifacts(self):
        self.assertIn("markdown", actions.read_artifact(self.ws, "dineclub-restart", "doc:adr"))
        with self.assertRaises(core.BlueprintError):
            actions.read_artifact(self.ws, "dineclub-restart", "file:../../dineclub-restart.md")

    def test_lint_runs_skill_script(self):
        r = actions.run_action(self.ws, "dineclub-restart", "lint")
        self.assertIn("blueprint.py lint", r["command"])
        self.assertTrue(r["output"])


class McpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        make_workspace(cls.tmp)
        cls.ws = core.Workspace.from_config({"workspace": str(cls.tmp), "docs_path": "bft/documentation"})
        cls.mcp = BlueprintMcp(cls.ws, actions.Jobs(cls.tmp / "state", None, cls.ws))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, method, params=None, rid=1):
        return self.mcp.handle({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})

    def tool(self, name, **args):
        r = self.call("tools/call", {"name": name, "arguments": args})["result"]
        return r["content"][0]["text"], r["isError"]

    def test_initialize(self):
        r = self.call("initialize", {"protocolVersion": "2025-03-26"})["result"]
        self.assertEqual(r["protocolVersion"], "2025-03-26")
        self.assertIn("blueprint_get", r["instructions"])

    def test_tools_list(self):
        names = {t["name"] for t in self.call("tools/list")["result"]["tools"]}
        for n in ("blueprint_list", "blueprint_get", "blueprint_guide", "blueprint_read", "blueprint_submit_story", "blueprint_submit_plan",
                  "blueprint_submit_doc", "blueprint_submit_contract", "blueprint_run", "blueprint_questions", "blueprint_answer",
                  "blueprint_start_agent", "blueprint_job"):
            self.assertIn(n, names)

    def test_list_and_get(self):
        text, err = self.tool("blueprint_list")
        self.assertFalse(err)
        self.assertEqual(json.loads(text)["bft_without_diagram"][0]["epic"], "car-booking")
        text, err = self.tool("blueprint_get", epic="dineclub-restart")
        self.assertEqual(json.loads(text)["next"]["key"], "release")

    def test_guide_points_to_resources(self):
        text, _ = self.tool("blueprint_guide", epic="car-booking")
        g = json.loads(text)
        self.assertEqual(g["stage"]["key"], "story")
        uris = {r["uri"] for r in self.call("resources/list")["result"]["resources"]}
        for u in g["read_resources"]:
            self.assertIn(u, uris)

    def test_errors_are_tool_errors(self):
        text, err = self.tool("blueprint_get", epic="../x")
        self.assertTrue(err)
        text, err = self.tool("blueprint_submit_story", epic="car-booking", markdown="без frontmatter")
        self.assertTrue(err)
        self.assertIn("frontmatter", text)

    def test_submit_story_returns_lint(self):
        story = (EX / "golden_story.md").read_text(encoding="utf-8")
        text, err = self.tool("blueprint_submit_story", epic="car-booking", markdown=story)
        self.assertFalse(err)
        self.assertIn("story-lint", text)

    def test_resources_and_prompt(self):
        r = self.call("resources/read", {"uri": "blueprint://skills/bft-blueprint"})["result"]
        self.assertIn("bft-blueprint", r["contents"][0]["text"])
        p = self.call("prompts/get", {"name": "blueprint_full_cycle", "arguments": {"epic": "car-booking"}})["result"]
        self.assertIn("car-booking", p["messages"][0]["content"]["text"])

    def test_notification_and_batch(self):
        self.assertIsNone(self.mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        out = self.mcp.handle_body([{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "method": "x"}])
        self.assertEqual(len(out), 1)

    def test_stdio(self):
        inp = io.StringIO('{"jsonrpc":"2.0","id":7,"method":"ping"}\n\n{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        out = io.StringIO()
        self.mcp.serve_stdio(inp, out)
        self.assertEqual(json.loads(out.getvalue())["id"], 7)

    def test_agent_disabled_is_explained(self):
        text, err = self.tool("blueprint_start_agent", epic="car-booking")
        self.assertTrue(err)
        self.assertIn("не настроен", text)


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.tmp = Path(tempfile.mkdtemp())
        make_workspace(cls.tmp)
        tokens = cls.tmp / "tokens"
        tokens.write_text("test-agent:tok-123\n", encoding="utf-8")
        cfg = {**server.DEFAULTS, "workspace": str(cls.tmp), "docs_path": "bft/documentation", "state_dir": str(cls.tmp / "state"),
               "mcp_tokens_file": str(tokens), "gate_mode": "none",
               "agent": {"command": [sys.executable, "-c", "import sys; print('агент:', sys.argv[1])", "{prompt}"], "timeout": 30}}
        cls.app = server.App(cfg)
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(cls.app))
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/blueprint"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def req(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.url + path, data=data, headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def test_static_and_list(self):
        status, body, hdr = self.req("/")
        self.assertEqual(status, 200)
        self.assertIn("Сервис Blueprint", body.decode())
        self.assertIn("frame-ancestors", hdr["Content-Security-Policy"])
        status, body, _ = self.req("/api/list")
        self.assertEqual(len(json.loads(body)["diagrams"]), 2)

    def test_static_traversal(self):
        status, _, _ = self.req("/../server.py")
        self.assertEqual(status, 404)

    def test_post_needs_header(self):
        status, _, _ = self.req("/api/run", {"epic": "dineclub-restart", "action": "lint"})
        self.assertEqual(status, 403)

    def test_page_is_sandboxed_with_inline_images(self):
        status, body, hdr = self.req("/api/page?epic=dineclub-restart&kind=map")
        self.assertEqual(status, 200)
        self.assertIn("sandbox", hdr["Content-Security-Policy"])
        self.assertIn(b"data:image/svg+xml;base64,", body)

    def test_mcp_token(self):
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        # gate none + localhost — открыт; с неверным токеном на corp был бы 401 — проверяем сам токен
        status, body, _ = self.req("/mcp", ping, {"Authorization": "Bearer tok-123"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["id"], 1)
        self.app.cfg["gate_mode"] = "corp"
        try:
            status, _, hdr = self.req("/mcp", ping, {"Authorization": "Bearer wrong"})
            self.assertEqual(status, 401)
            self.assertIn("Bearer", hdr["WWW-Authenticate"])
            status, _, _ = self.req("/api/list")
            self.assertEqual(status, 403)
        finally:
            self.app.cfg["gate_mode"] = "none"

    def test_agent_job(self):
        status, body, _ = self.req("/api/agent", {"epic": "car-booking", "stage": "story", "note": "коротко"}, {"X-Blueprint": "1"})
        self.assertEqual(status, 200, body)
        jid = json.loads(body)["job"]["id"]
        for _ in range(50):
            job = json.loads(self.req(f"/api/job?id={jid}")[1])["job"]
            if job["state"] != "running":
                break
            time.sleep(0.1)
        self.assertEqual(job["state"], "done")
        self.assertIn("/bft-blueprint car-booking --story", job["log"])
        self.assertIn("Комментарий PO: коротко", job["log"])


if __name__ == "__main__":
    unittest.main()

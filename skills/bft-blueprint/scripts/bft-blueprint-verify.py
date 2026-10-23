#!/usr/bin/env python3
"""bft-blueprint-verify — приёмка комплекта: всё ли собрано скриптами навыка, а не написано от руки.

Проверяет папку эпика `<docs_path>/<epic>`:
1. `<epic>-story.md` и `<epic>-story.html` — страница с отпечатком `generator: bft-blueprint story`;
2. проект Backlog.md `<epic>-blueprint/` — есть задачи и документы, `./backlog.py`, `./blueprint.py`;
3. `<epic>-map.html` — отпечаток `generator: bft-blueprint map`, данные `map-data`;
4. `<epic>-blueprint.zip` — читается, внутри проект и `blueprint.html`;
5. `bft-backlog-build.py --check` — страница и схемы совпадают с проектом.

Использование:
    python3 bft-blueprint-verify.py <docs_path>/<epic> [--epic SLUG] [--no-story]

Код 1 — комплект не принят; под каждой ошибкой — команда, которая её исправляет.
Не принятый комплект отдавать нельзя: HTML, написанный от руки, и архив без проекта — не результат навыка.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fp(page: Path, kind: str) -> bool:
    return f'<meta name="generator" content="bft-blueprint {kind}">' in page.read_text(encoding="utf-8", errors="replace")[:4000]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("epic_dir", type=Path)
    ap.add_argument("--epic", help="слаг эпика (по умолчанию — имя папки)")
    ap.add_argument("--no-story", action="store_true", help="не требовать историю (режим --map на чужой истории)")
    a = ap.parse_args()
    d = a.epic_dir.resolve()
    epic = a.epic or d.name
    S = HERE
    errs: list[str] = []

    def err(msg: str, fix: str) -> None:
        errs.append(f"ERROR {msg}\n       исправь: {fix}")

    stray = [p.name for p in d.glob("*.html") if p.name not in (f"{epic}-story.html", f"{epic}-map.html")]
    story_md, story_html = d / f"{epic}-story.md", d / f"{epic}-story.html"
    if not a.no_story:
        if not story_md.is_file():
            err(f"нет {story_md.name}", f"написать историю по templates/story.md, затем python3 {S}/bft-story-lint.py {story_md}")
        elif not story_html.is_file() or not fp(story_html, "story"):
            err(f"{story_html.name} нет или собрана не скриптом (нет отпечатка generator)", f"python3 {S}/bft-story-render.py {story_md}")
    proj = d / f"{epic}-blueprint"
    tasks = list((proj / "backlog" / "tasks").glob("*.md")) if proj.is_dir() else []
    docs = list((proj / "backlog" / "docs").glob("*.md")) if proj.is_dir() else []
    if not proj.is_dir():
        err(f"нет проекта {proj.name}/", f"python3 {S}/bft-backlog-init.py {story_md}")
    else:
        if not (proj / "backlog.py").is_file() or not (proj / "blueprint.py").is_file():
            err("в проекте нет backlog.py/blueprint.py — он не создан bft-backlog-init.py", f"python3 {S}/bft-backlog-init.py {story_md}")
        if not tasks:
            err("в проекте нет задач Backlog.md (backlog/tasks/*.md) — бэклог не проработан", "cd проект && ./blueprint.py skeleton, затем план карты (resources/autopilot.md, шаг 4)")
        if not docs:
            err("в проекте нет документов (backlog/docs/*.md): «Карта», «История», экраны", f"python3 {S}/bft-backlog-init.py {story_md}")
    page = d / f"{epic}-map.html"
    if not page.is_file() or not fp(page, "map") or 'id="map-data"' not in page.read_text(encoding="utf-8", errors="replace"):
        err(f"{page.name} нет или собрана не скриптом", f"python3 {S}/bft-backlog-build.py {proj}")
    z = d / f"{epic}-blueprint.zip"
    if not z.is_file():
        err(f"нет {z.name}", f"python3 {S}/bft-backlog-build.py {proj}")
    else:
        try:
            names = zipfile.ZipFile(z).namelist()
            if not any(n.endswith("blueprint.html") for n in names) or not any("/backlog/tasks/" in n for n in names):
                err(f"{z.name}: внутри нет blueprint.html или задач проекта", f"python3 {S}/bft-backlog-build.py {proj}")
        except zipfile.BadZipFile:
            err(f"{z.name} — не zip", f"python3 {S}/bft-backlog-build.py {proj}")
    if proj.is_dir() and tasks and not errs:
        r = subprocess.run([sys.executable, str(S / "bft-backlog-build.py"), str(proj), "--check"], capture_output=True, text=True)
        if r.returncode:
            err("bft-backlog-build.py --check не прошёл:\n" + (r.stdout + r.stderr).strip()[:1500], f"python3 {S}/bft-backlog-build.py {proj}")
    for e in errs:
        print(f"{d}: {e}")
    if stray:
        print(f"{d}: WARN лишние html рядом: {', '.join(stray)} — это не результат навыка, удали или не отдавай")
    if errs:
        print(f"bft-blueprint-verify: комплект не принят, ошибок — {len(errs)}", file=sys.stderr)
        return 1
    print(f"bft-blueprint-verify: принято — {epic}: история, проект ({len(tasks)} задач, {len(docs)} документов), карта, архив")
    return 0


if __name__ == "__main__":
    sys.exit(main())

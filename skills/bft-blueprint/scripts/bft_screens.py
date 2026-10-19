#!/usr/bin/env python3
"""Требования к экранам — заметки для дизайнера: документ Backlog.md на экран истории.

Документ лежит в `backlog/docs/screens/`, его заголовок — «F3 · Название экрана» (ID экрана истории
и название). Тело — обычный markdown:

    # Заголовок экрана
    ![Подпись](../../assets/screens/F3.svg)   ← картинки экрана до первой вкладки: 0, 1 или несколько
    ## Product                   ← вкладки: Product, Design, Functions — по порядку
    ### Заголовок заметки        ← одна заметка — одно требование
    Текст заметки: абзацы, списки, **жирный**, картинки ![…](../../assets/screens/F4.svg) или свой файл.
    Источник: ФТ-1, ИТ-8

Product — job stories «Когда …, хочу …, чтобы …»; Design — где, в каком состоянии, что главное,
куда дальше, ограничения; Functions — сценарии Gherkin «**Дано** / **Когда** / **Тогда** / **И**».
Неизвестное — `[УТОЧНИТЬ у {кого}]`. Стандарт — `resources/screen_notes.md`.

  ОШИБКИ                                        ПРЕДУПРЕЖДЕНИЯ
  SN001  экрана из заголовка нет в истории       SN020  вкладка без заметок
  SN002  нет заголовка `# …`                    SN021  заметка без «Источник:» и без [УТОЧНИТЬ]
  SN003  вкладки не те, не по порядку,          SN022  Product: заметка не в форме «Когда …, хочу …»
         текст вне заметки                      SN023  экран истории без требований
  SN004  заметка без заголовка или текста,
         повтор заголовка во вкладке
  SN005  Functions: нет шага «**Тогда**»
  SN006  картинка: файла нет; `screen:F3` вместо пути

Только стандартная библиотека.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bft_blueprint as bb  # noqa: E402

DIR = "screens"
TABS = ("Product", "Design", "Functions")
IMG_RE = re.compile(r"^!\[(.*?)\]\((.+?)\)$")
INLINE_IMG = re.compile(r"!\[(.*?)\]\((.+?)\)")
SCREEN_ID = re.compile(r"^[A-ZА-Я]\d{1,2}$")
DOC_TO_ASSETS = "../../assets/screens"   # от backlog/docs/screens/ до картинок экранов
SCREEN_FILE = re.compile(r"assets/screens/([A-ZА-Я]\d{1,2})\.(?:svg|png|jpe?g|webp)$")


@dataclass
class Note:
    tab: str
    title: str
    md: str
    line: int


@dataclass
class ScreenDoc:
    id: str
    path: Path
    title: str = ""
    images: list[tuple[str, str, int]] = field(default_factory=list)  # (подпись, источник, строка)
    notes: list[Note] = field(default_factory=list)
    text: str = ""
    rel: str = ""    # путь документа от корня проекта


def parse(sid: str, path: Path, text: str, rel: str, off: int, issues: list) -> ScreenDoc:
    """Тело документа без frontmatter Backlog.md; `off` — строк до тела, номера строк — по файлу."""
    doc = ScreenDoc(sid, path, text=text, rel=rel)
    err = lambda n, code, msg: issues.append(bb.Issue(n + off, "ERROR", code, msg, rel))  # noqa: E731
    tabs: list[str] = []
    tab, note, body = None, None, []

    def close():
        if note is not None:
            note.md = "\n".join(body).strip()
            if not note.md:
                err(note.line, "SN004", f"заметка «{note.title}» без текста")

    for n, raw in enumerate(doc.text.split("\n"), start=1):
        line = raw.rstrip()
        if line.startswith("### "):
            close()
            title = line[4:].strip()
            if tab is None:
                err(n, "SN003", "заметка до первой вкладки `## Product`")
            if not title:
                err(n, "SN004", "заметка без заголовка")
            elif any(x.tab == tab and x.title == title for x in doc.notes):
                err(n, "SN004", f"заметка «{title}» уже есть во вкладке {tab}")
            note, body = Note(tab or "", title, "", n), []
            doc.notes.append(note)
        elif line.startswith("## "):
            close()
            note, body = None, []
            tab = line[3:].strip()
            if tab not in TABS:
                err(n, "SN003", f"вкладка «{tab}» — одна из {', '.join(TABS)}")
            elif tab in tabs:
                err(n, "SN003", f"вкладка {tab} уже была")
            tabs.append(tab)
        elif line.startswith("# "):
            if doc.title:
                err(n, "SN002", "второй заголовок `# …` — один на экран")
            doc.title = line[2:].strip()
        elif note is not None:
            body.append(line)
        elif line.strip():
            m = IMG_RE.match(line.strip())
            if m and tab is None:
                doc.images.append((m.group(1), m.group(2), n))
            else:
                err(n, "SN003", "текст вне заметки — под `### Заголовок заметки`")
    close()
    for x in doc.notes:
        x.line += off
    doc.images = [(alt, src, n + off) for alt, src, n in doc.images]
    if not doc.title:
        err(1, "SN002", "нет заголовка `# Название экрана`")
    known = [t for t in TABS if t in tabs]
    if [t for t in tabs if t in TABS] != known:
        err(1, "SN003", "вкладки по порядку: " + " → ".join(TABS))
    for t in TABS:
        if t not in tabs:
            err(1, "SN003", f"нет вкладки `## {t}`")
    return doc


def check(docs: list[ScreenDoc], screen_ids: set[str], issues: list) -> dict[str, ScreenDoc]:
    """Проверка разобранных документов экранов. Экран без требований — SN023."""
    out: dict[str, ScreenDoc] = {}
    for doc in docs:
        rel = doc.rel
        if doc.id not in screen_ids:
            issues.append(bb.Issue(1, "ERROR", "SN001", f"экрана {doc.id} нет в истории — заголовок документа «F3 · Название»", rel))
            continue
        if doc.id in out:
            issues.append(bb.Issue(1, "ERROR", "SN001", f"второй документ экрана {doc.id} — один документ на экран", rel))
            continue
        out[doc.id] = doc
        for alt, src, n in doc.images + [(m.group(1), m.group(2), x.line) for x in doc.notes for m in INLINE_IMG.finditer(x.md)]:
            if src.startswith("screen:"):
                issues.append(bb.Issue(n, "ERROR", "SN006", f"картинка «{alt}»: ссылка {src} — картинка экрана лежит файлом, `![{alt}]({DOC_TO_ASSETS}/{src[7:]}.svg)`", rel))
                continue
            if re.match(r"^(https?:|data:)", src):
                continue
            sid = screen_of(src)
            if sid and sid in screen_ids and src.endswith(".svg"):
                continue   # упрощённый экран — его пишет сборка из «Истории»
            if not (doc.path.parent / src).is_file():
                issues.append(bb.Issue(n, "ERROR", "SN006", f"картинка «{alt}»: файла {src} нет рядом с документом", rel))
        for t in TABS:
            if not any(x.tab == t for x in doc.notes):
                issues.append(bb.Issue(1, "WARN", "SN020", f"вкладка {t} без заметок", rel))
        for x in doc.notes:
            if x.tab == "Functions" and "**Тогда**" not in x.md:
                issues.append(bb.Issue(x.line, "ERROR", "SN005", f"«{x.title}»: сценарий без шага **Тогда**", rel))
            if "Источник:" not in x.md and bb.MARKER not in x.md and x.tab != "Design":
                issues.append(bb.Issue(x.line, "WARN", "SN021", f"«{x.title}»: нет строки «Источник:» с ID требований", rel))
            if x.tab == "Product" and not re.search(r"Когда .+хочу", x.md.replace("**", "")):
                issues.append(bb.Issue(x.line, "WARN", "SN022", f"«{x.title}»: история в форме «Когда …, хочу …, чтобы …»", rel))
    covered = set(out) | {screen_of(src) for d in out.values() for _, src, _ in d.images} - {""}
    missing = sorted(screen_ids - covered)
    if missing:
        issues.append(bb.Issue(1, "WARN", "SN023", f"экраны без требований для дизайнера (документ «F3 · …» в docs/{DIR}/): {', '.join(missing)}"))
    return out


def screen_of(src: str) -> str:
    """ID экрана по пути картинки `…/assets/screens/F3.svg` (или своему макету `F3.png`); иначе пусто."""
    m = SCREEN_FILE.search(src)
    return m.group(1) if m else ""


def page_md(doc: ScreenDoc, root: Path) -> str:
    """Текст файла для страницы: пути картинок — от корня проекта, файлы остаются в бэклоге."""
    def path(m: re.Match) -> str:
        alt, src = m.group(1), m.group(2)
        if re.match(r"^(https?:|data:)", src):
            return m.group(0)
        p = os.path.normpath(doc.path.parent / src)
        return f"![{alt}]({Path(os.path.relpath(p, root)).as_posix()})"
    return INLINE_IMG.sub(path, doc.text)

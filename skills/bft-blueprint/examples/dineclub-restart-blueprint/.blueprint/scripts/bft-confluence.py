#!/usr/bin/env python3
"""Отгрузить в Confluence: Service Blueprint дочерней страницей под страницей БФТ.

  bft-confluence.py page <project> [--date ГГГГ-ММ-ДД]          собрать страницу локально, без сети
  bft-confluence.py publish <project> [--parent URL|ID] [--date …] собрать и отгрузить (повтор — обновляет ту же страницу)

Страница — Confluence storage format (XHTML): этапы, «Что делаем» (истории и команды), «Как это работает»
(карточки по слоям), «Расхождения с требованиями», открытые вопросы; версия и дата сборки — в шапке.
Вложения — страница карты <epic>-map.html и архив <epic>-blueprint.zip (их пишет ./blueprint.py build).

Локально команда пишет в проект папку confluence/: page.xhtml (тело страницы), publish.json (заголовок,
родитель, вложения, ID отгруженной страницы — чтобы повтор обновил её, а не создал новую). Учётных данных
там нет никогда.

Доступ к Confluence — только из окружения: CONFLUENCE_URL (https://wiki.example.com), и либо
CONFLUENCE_TOKEN (Personal Access Token, Bearer), либо CONFLUENCE_USER + CONFLUENCE_TOKEN (Basic: e-mail и API token
Atlassian Cloud). Их нет — страница собрана локально, команда говорит, чего не хватает, и выходит с кодом 3:
загрузи confluence/page.xhtml вручную или через подключённый коннектор Confluence агента.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bft_backlog as bl  # noqa: E402

DIR = "confluence"
PAGE, META = "page.xhtml", "publish.json"
LAYER_TITLE = {"employee": "Employee Actions — действия сотрудников", "technology": "Technology — системы, которые видит человек",
               "backstage": "Backstage — работа за кадром", "support": "Support — поддержка работающего сервиса"}
NO_PUBLISH = 3   # страница собрана локально, но не отгружена: нет доступа


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=False)


def inline(s: str) -> str:
    """Markdown строки → XHTML: **жирный**, `код`; остальное — текст."""
    t = esc(s)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tbody><tr>{th}</tr>{trs}</tbody></table>"


def macro(name: str, body: str, title: str = "") -> str:
    p = f'<ac:parameter ac:name="title">{esc(title)}</ac:parameter>' if title else ""
    return f'<ac:structured-macro ac:name="{name}">{p}<ac:rich-text-body>{body}</ac:rich-text-body></ac:structured-macro>'


def title_of(pr: bl.Project) -> str:
    return f"Service Blueprint: {pr.title}"


def attachments(pr: bl.Project) -> list[Path]:
    epic = pr.meta.get("epic_slug", "epic")
    return [p for p in (pr.root / f"{epic}-map.html", pr.root / f"{epic}-blueprint.zip") if p.is_file()]


def render(pr: bl.Project, date: str) -> str:
    """Тело страницы в storage format — только из файлов проекта."""
    st, out = pr.story, []
    stage = {s.id: s.name for s in st.stages}
    team = {t.id: t.name for t in pr.teams}
    files = attachments(pr)
    ver = pr.meta.get("version", "")
    out.append(macro("info", f"<p>Версия карты <strong>{esc(ver or '—')}</strong> · статус {esc(pr.meta.get('status', '') or '—')}"
                             f" · собрано {esc(date)} командой <code>./blueprint.py confluence</code>. Источник — проект Backlog.md "
                             f"<code>{esc(pr.meta.get('epic_slug', ''))}-blueprint</code>; правки — в проекте, не на этой странице.</p>"
                             + (f"<p>Интерактивная карта и проект — во вложениях: {', '.join(f'<code>{esc(p.name)}</code>' for p in files)}.</p>" if files else "")))
    out.append("<h2>Этапы</h2>")
    out.append(table(["Этап", "Название", "Когда"], [[esc(s.id), esc(s.name), inline(s.when)] for s in st.stages]))

    out.append("<h2>Что делаем</h2>")
    for s in st.stages:
        tasks = [t for t in pr.tasks if t.stage == s.id]
        if not tasks:
            continue
        out.append(f"<h3>{esc(s.id)} · {esc(s.name)}</h3>")
        out.append(table(["ID", "История", "Команда", "Вид", "Приоритет", "Требования БФТ"],
                         [[esc(t.id), inline(t.title), esc(team.get(t.team, t.team) or ("кандидаты: " + ", ".join(t.cand) if t.cand else "—")),
                           esc(t.kind), esc(t.prio), esc(", ".join(t.reqs))] for t in tasks]))

    out.append("<h2>Как это работает</h2>")
    for layer in bl.LAYERS:
        cards = [c for c in pr.cards if c.layer == layer]
        if not cards:
            continue
        out.append(f"<h3>{esc(LAYER_TITLE[layer])}</h3>")
        out.append(table(["ID", "Этап", "Карточка", "История"],
                         [[esc(c.id), esc(stage.get(c.stage, c.stage)), inline(c.title), esc(c.parent)] for c in cards]))

    out.append("<h2>Расхождения с требованиями</h2>")
    devs = pr.devs.items if pr.devs else []
    if devs:
        out.append(table(["ID", "Требование", "Функционал", "Требуется в БФТ", "Изменения в процессе", "Решение"],
                         [[esc(x.id), esc(", ".join(x.reqs)), inline(x.feature), inline(x.bft), inline(x.change),
                           inline(x.decision) or "<strong>Эскалировать: решения нет</strong>"] for x in devs]))
    else:
        out.append("<p>Расхождений с БФТ не записано: карта делает всё, что требует БФТ.</p>")

    qs = [q for q in pr.questions if q.open]
    out.append(f"<h2>Открытые вопросы · {len(qs)}</h2>")
    out.append(table(["ID", "Кому", "Вопрос", "Где"], [[esc(q.id), esc(q.to), inline(q.text), esc(q.where)] for q in qs])
               if qs else "<p>Открытых вопросов нет.</p>")
    return "\n".join(out) + "\n"


def parent_id(ref: str) -> str:
    """ID страницы из ссылки Confluence (…?pageId=123, …/pages/123/…) или из самого ID."""
    ref = (ref or "").strip()
    for pat in (r"^(\d+)$", r"[?&]pageId=(\d+)", r"/pages/(\d+)(?:/|$)"):
        m = re.search(pat, ref)
        if m:
            return m.group(1)
    return ""


def prepare(pr: bl.Project, parent: str, date: str) -> dict:
    """Пишет confluence/page.xhtml и publish.json; ID отгруженной страницы из прошлого publish.json сохраняется."""
    d = pr.root / DIR
    d.mkdir(exist_ok=True)
    (d / PAGE).write_text(render(pr, date), encoding="utf-8")
    old = json.loads((d / META).read_text(encoding="utf-8")) if (d / META).is_file() else {}
    meta = {"title": title_of(pr), "parent": parent or old.get("parent", ""), "page_id": old.get("page_id", ""),
            "url": old.get("url", ""), "date": date, "body": f"{DIR}/{PAGE}",
            "attachments": [p.name for p in attachments(pr)]}
    if meta["parent"] != old.get("parent", meta["parent"]):
        meta["page_id"] = meta["url"] = ""      # другой родитель — другая страница
    (d / META).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


class Confluence:
    """REST API Confluence (Server/DC и Cloud, /rest/api). Токен живёт только в заголовке запроса."""

    def __init__(self, base: str, user: str, token: str):
        self.base = base.rstrip("/")
        self.auth = ("Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()) if user else f"Bearer {token}"

    def call(self, method: str, path: str, data: bytes | None = None, ctype: str = "application/json") -> dict:
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Authorization": self.auth, "Accept": "application/json",
                                              "X-Atlassian-Token": "no-check", **({"Content-Type": ctype} if data is not None else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"{method} {path}: HTTP {e.code} {msg}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"{method} {path}: {e.reason}") from None
        return json.loads(body) if body else {}

    def page(self, pid: str) -> dict | None:
        try:
            return self.call("GET", f"/rest/api/content/{pid}?expand=version,space")
        except RuntimeError as e:
            if "HTTP 404" in str(e):
                return None
            raise

    def child_by_title(self, parent: str, title: str) -> dict | None:
        res = self.call("GET", f"/rest/api/content/{parent}/child/page?limit=200&expand=version")
        return next((p for p in res.get("results", []) if p.get("title") == title), None)

    def save(self, meta: dict, body: str, space: str) -> dict:
        payload = {"type": "page", "title": meta["title"], "space": {"key": space},
                   "ancestors": [{"id": meta["parent"]}],
                   "body": {"storage": {"value": body, "representation": "storage"}}}
        cur = self.page(meta["page_id"]) if meta["page_id"] else None
        cur = cur or self.child_by_title(meta["parent"], meta["title"])
        if cur:
            payload["version"] = {"number": cur["version"]["number"] + 1, "message": f"bft-blueprint {meta['date']}"}
            return self.call("PUT", f"/rest/api/content/{cur['id']}", json.dumps(payload).encode())
        return self.call("POST", "/rest/api/content", json.dumps(payload).encode())

    def attach(self, pid: str, f: Path) -> None:
        """Вложение: есть с тем же именем — новая версия, нет — новое."""
        q = urllib.parse.quote(f.name)
        res = self.call("GET", f"/rest/api/content/{pid}/child/attachment?filename={q}")
        boundary = uuid.uuid4().hex
        ctype = "text/html" if f.suffix == ".html" else "application/zip"
        data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{f.name}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + f.read_bytes() + \
            (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"minorEdit\"\r\n\r\ntrue\r\n--{boundary}--\r\n").encode()
        hit = (res.get("results") or [None])[0]
        path = f"/rest/api/content/{pid}/child/attachment" + (f"/{hit['id']}/data" if hit else "")
        self.call("POST", path, data, f"multipart/form-data; boundary={boundary}")


def missing_env() -> list[str]:
    need = [k for k in ("CONFLUENCE_URL", "CONFLUENCE_TOKEN") if not os.environ.get(k)]
    return need


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("page", "publish"))
    ap.add_argument("project", type=Path, help="папка проекта Backlog.md (<epic>-blueprint)")
    ap.add_argument("--parent", default="", help="страница БФТ в Confluence: ссылка или ID (запоминается в confluence/publish.json)")
    ap.add_argument("--date", default="", help="дата сборки на странице (по умолчанию — сегодня)")
    args = ap.parse_args()
    if not (args.project / "backlog").is_dir():
        print(f"{args.project}: не папка проекта", file=sys.stderr)
        return 2
    pr = bl.parse(args.project)
    parent = parent_id(args.parent)
    if args.parent and not parent:
        print(f"confluence: «{args.parent}» — не ссылка на страницу Confluence и не ID", file=sys.stderr)
        return 2
    meta = prepare(pr, parent, args.date or dt.date.today().isoformat())
    print(f"confluence: страница «{meta['title']}» — {DIR}/{PAGE}, вложения: {', '.join(meta['attachments']) or 'нет — сначала ./blueprint.py build'}")
    if args.cmd == "page":
        return 0
    lack = missing_env() + ([] if meta["parent"] else ["--parent <ссылка на страницу БФТ>"])
    if lack:
        print("confluence: не отгружено — не хватает: " + ", ".join(lack) + ". Страница собрана локально: загрузи "
              f"{DIR}/{PAGE} дочерней страницей к БФТ вручную или коннектором Confluence (вложения — {', '.join(meta['attachments']) or 'нет'}); "
              "доступ — переменные окружения CONFLUENCE_URL и CONFLUENCE_TOKEN (Cloud — ещё CONFLUENCE_USER)", file=sys.stderr)
        return NO_PUBLISH
    cf = Confluence(os.environ["CONFLUENCE_URL"], os.environ.get("CONFLUENCE_USER", ""), os.environ["CONFLUENCE_TOKEN"])
    try:
        par = cf.page(meta["parent"])
        if not par:
            print(f"confluence: страницы БФТ {meta['parent']} нет или нет доступа", file=sys.stderr)
            return 1
        res = cf.save(meta, (pr.root / DIR / PAGE).read_text(encoding="utf-8"), par["space"]["key"])
        for name in meta["attachments"]:
            cf.attach(res["id"], pr.root / name)
    except RuntimeError as e:
        print(f"confluence: не отгружено — {e}", file=sys.stderr)
        return 1
    meta["page_id"] = res["id"]
    meta["url"] = cf.base + res.get("_links", {}).get("webui", f"/pages/viewpage.action?pageId={res['id']}")
    (pr.root / DIR / META).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"confluence: отгружено — {meta['url']} (версия {res.get('version', {}).get('number', 1)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

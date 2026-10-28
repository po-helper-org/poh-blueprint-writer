#!/usr/bin/env python3
"""Сверка БФТ ↔ Blueprint: по каждому требованию БФТ — где оно в итоговой карте и есть ли расхождение.

Требование БФТ (ФТ, ИТ, НФТ, ПТ, БТ) ищется в карте Backlog.md: задачи «Что делаем» (строка «Требования БФТ»
и текст), карточки «Как это работает», требования к экранам, контракты стыков. Отход от БФТ — строка реестра
«Расхождения с требованиями» (документ <!-- bft-deviations -->). Статусы:

  покрыто          требование есть на карте
  расхождение      требование в реестре расхождений (на карте его может и не быть — решение записано)
  нет на карте     требования нет ни на карте, ни в реестре — работа потеряна или отход не зафиксирован

ФТ, ИТ, НФТ «нет на карте» — ошибка сверки (код 1); БТ и ПТ — предупреждение: их несут роли и истории.

Использование:
  bft-reconcile.py <project> [--source БФТ.md] [--out сверка.md] [--strict]

Без БФТ рядом сверка неполная: требования берутся из самой карты, и «нет на карте» не найти.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bft_backlog as bl  # noqa: E402

import bft_blueprint as bb  # noqa: E402

import bft_contracts as bc  # noqa: E402

KIND_ORDER = ("БТ", "ФТ", "ИТ", "НФТ", "ПТ")
MUST = ("ФТ", "ИТ", "НФТ")   # без них карта не делает обещанного БФТ


def _kind(rid: str) -> str:
    return rid.split("-")[0]


def where(pr: bl.Project) -> dict[str, list[str]]:
    """{ID требования: [где на карте]} — задачи, карточки, экраны, контракты."""
    out: dict[str, list[str]] = {}
    add = lambda rid, place: out.setdefault(rid, []).append(place) if place not in out.get(rid, []) else None  # noqa: E731
    for t in pr.tasks:
        for rid in set(bb.REQ_RE.findall("\n".join([t.desc] + [x for _, x in t.ac]))):
            add(rid, f"задача {t.id}")
    for z in pr.subtasks:
        for rid in set(bb.REQ_RE.findall(z.desc)):
            add(rid, f"подзадача {z.id}")
    for c in pr.cards:
        for rid in set(bb.REQ_RE.findall(bl.MERMAID.sub("", c.desc))):
            add(rid, f"карточка {c.id}")
    for sid, d in pr.screens.items():
        for x in d.notes:
            for rid in set(bb.REQ_RE.findall(x.md)):
                add(rid, f"экран {sid}")
    keep = list(pr.issues)
    try:
        contracts = bc.parse(pr)
    finally:
        pr.issues[:] = keep
    for c in contracts:
        text = c.path.read_text(encoding="utf-8")
        for rid in set(bb.REQ_RE.findall(text)):
            add(rid, f"контракт {c.id}")
    return out


def reconcile(pr: bl.Project, reqs: dict[str, str] | None) -> list[dict]:
    """Строки сверки: требование, суть, где на карте, расхождения, статус."""
    places = where(pr)
    devs: dict[str, list[str]] = {}
    for x in (pr.devs.items if pr.devs else []):
        for rid in x.reqs:
            devs.setdefault(rid, []).append(x.id)
    ids = list(reqs) if reqs is not None else sorted(set(places) | set(devs))
    order = lambda r: (KIND_ORDER.index(_kind(r)) if _kind(r) in KIND_ORDER else 9,  # noqa: E731
                       int("".join(ch for ch in r.split("-", 1)[1] if ch.isdigit()) or 0), r)
    rows = []
    for rid in sorted(ids, key=order):
        at, dv = places.get(rid, []), devs.get(rid, [])
        status = "расхождение" if dv else "покрыто" if at else "нет на карте"
        rows.append({"id": rid, "name": (reqs or {}).get(rid, ""), "where": at, "devs": dv, "status": status})
    return rows


def report(rows: list[dict], title: str, full: bool) -> str:
    n = {s: sum(r["status"] == s for r in rows) for s in ("покрыто", "расхождение", "нет на карте")}
    out = [f"# Сверка БФТ ↔ Blueprint: {title}", "",
           f"Требований {len(rows)}: покрыто {n['покрыто']}, расхождение {n['расхождение']}, нет на карте {n['нет на карте']}."
           + ("" if full else " БФТ рядом нет — требования взяты из карты, «нет на карте» не найти."), "",
           "| Требование | Суть в БФТ | Где на карте | Расхождение | Статус |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        at = ", ".join(r["where"][:6]) + (f" и ещё {len(r['where']) - 6}" if len(r["where"]) > 6 else "")
        out.append(f"| {r['id']} | {r['name'] or '—'} | {at or '—'} | {', '.join(r['devs']) or '—'} | {r['status']} |")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", type=Path, help="папка проекта Backlog.md (<epic>-blueprint)")
    ap.add_argument("--source", type=Path, help="БФТ (по умолчанию — source_doc паспорта рядом с проектом)")
    ap.add_argument("--out", type=Path, help="записать отчёт в файл markdown")
    ap.add_argument("--strict", action="store_true", help="БТ и ПТ «нет на карте» тоже дают код 1")
    args = ap.parse_args()
    if not (args.project / "backlog").is_dir():
        print(f"{args.project}: не папка проекта", file=sys.stderr)
        return 2
    pr = bl.parse(args.project)
    src = args.source or (args.project.resolve().parent / pr.meta.get("source_doc", "") if pr.meta.get("source_doc") else None)
    reqs = bb.load_requirements(src)[0] if src and src.is_file() else None
    if args.source and reqs is None:
        print(f"{args.source}: БФТ не найден", file=sys.stderr)
        return 2
    rows = reconcile(pr, reqs)
    text = report(rows, pr.title, reqs is not None)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"reconcile: отчёт — {args.out}")
    else:
        print(text, end="")
    lost = [r for r in rows if r["status"] == "нет на карте" and (args.strict or _kind(r["id"]) in MUST)]
    for r in lost:
        print(f"{pr.root}:1: ERROR RC001 {r['id']} «{r['name']}» нет ни на карте, ни в «Расхождениях с требованиями» — "
              "верни работу на карту или запиши расхождение с решением", file=sys.stderr)
    if reqs is None:
        print("reconcile: БФТ рядом нет — сверка неполная: положи БФТ рядом с проектом или передай --source", file=sys.stderr)
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())

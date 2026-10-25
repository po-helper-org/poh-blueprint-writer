#!/usr/bin/env python3
"""bft-contracts — контракты стыков карты (Design First): `contracts/C-N.md` проекта Backlog.md.

Каждый стык между системами — один контракт: кто кого вызывает, поля запроса и ответа с источником
в БФТ, пример ответа, ошибки, Sequence, цепочка преобразований за кадром, какие данные нужны из
хранилища. Стандарт — `resources/contracts.md`, шаблон — `templates/contract.md`.

  ОШИБКИ (код выхода 1)
  CT001  файл не читается как контракт: frontmatter, id C-N = имя файла, повтор ID
  CT002  шапка: title, boundary, caller, callee, op «МЕТОД /путь», cards
  CT003  cards: ссылается на карточку, которой нет на карте
  CT004  разделы и таблицы шаблона; поле латиницей; пример ответа — JSON со всеми полями ответа; ошибки внешнего стыка
  CT005  у поля нет источника: ID требования или [УТОЧНИТЬ у …]
  CT006  требования из источника поля нет в БФТ
  CT007  Sequence: первая строка — вызов caller → callee, у вызова есть ответ, участники известны карте
  CT008  цепочка: вход шага не пришёл ни из запроса, ни из прошлого шага; поле ответа не собрано
  CT009  в «Данных» и «Цепочке» — устройство хранилища (таблицы, ключи, SQL)
  CT010  параметр пути op не описан в «Запросе»
  CT011  в контракте остались места {{…}} каркаса — остальные проверки после заполнения
  CT013  contracts/not-seams.md: строка не про стык карты или без причины
  CT012  пример ответа: значение не того типа, что в «Ответе», или пояснение вместо значения

  ПРЕДУПРЕЖДЕНИЯ (код выхода 1 только с --strict)
  CT020  стык на карте без контракта: экран ↔ Backstage, Backstage ↔ другая команда, внешняя система
  CT021  за вызываемой системой есть ещё участники, а «Цепочки» нет
  CT022  внутренний стык без единой ошибки

Использование:
    python3 bft-contracts.py lint <проект> [--source БФТ.md | --no-source] [--strict] [--hints]
    python3 bft-contracts.py skeleton <проект>   — каркас contracts/C-N.md на каждый стык карты без контракта
Формат вывода: <путь>:<строка>: <УРОВЕНЬ> <КОД> <сообщение>
Коды выхода: 0 — ошибок нет; 1 — ошибки (или предупреждения с --strict); 2 — проект не прочитан.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bft_blueprint as bb  # noqa: E402
import bft_backlog as bl  # noqa: E402
import bft_contracts as bc  # noqa: E402

_spec = importlib.util.spec_from_file_location("bl_lint", HERE / "bft-backlog-lint.py")
_bl_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bl_lint)


def run(root: Path, source: str | None, no_source: bool) -> tuple[bl.Project, list[bc.Contract]]:
    pr = bl.parse(root)
    if pr.errors:   # карта не читается — стыки сверять не с чем
        return pr, []
    pr.issues = []
    contracts = bc.parse(pr)
    reqs = None
    src = None if no_source else _bl_lint.resolve_source(pr, source)
    if src is not None and src.is_file():
        reqs, _ = bb.load_requirements(src)
    elif source:
        pr.err("", 1, "CT006", f"БФТ-источник не найден: {source}")
    bc.check(pr, contracts, reqs)
    return pr, contracts


def report(pr: bl.Project, contracts: list, strict: bool) -> int:
    for i in sorted(pr.issues, key=lambda i: (i.level != "ERROR", i.path, i.line)):
        print(f"{pr.root / i.path if i.path else pr.root}:{i.line}: {i.level} {i.code} {i.msg}")
    errors = len(pr.errors)
    warns = len(pr.issues) - errors
    by = {}
    for c in contracts:
        k = "не заполнено" if "{{" in c.boundary else c.boundary
        by[k] = by.get(k, 0) + 1
    kinds = ", ".join(f"{k} {v}" for k, v in sorted(by.items())) or "—"
    print(f"contracts-lint: {len(contracts)} контрактов ({kinds}), стыков на карте {len(pr.links())} — ошибок {errors}, предупреждений {warns}")
    return 1 if errors or (strict and warns) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["lint", "skeleton"], help="lint — проверить контракты; skeleton — каркас на стыки без контракта")
    ap.add_argument("project", type=Path, help="папка проекта Backlog.md (<epic>-blueprint)")
    ap.add_argument("--source", help="путь к БФТ (по умолчанию — `source_doc` паспорта рядом с проектом)")
    ap.add_argument("--no-source", action="store_true", help="не сверять источники полей с БФТ")
    ap.add_argument("--strict", action="store_true", help="предупреждения тоже дают код 1")
    ap.add_argument("--hints", action="store_true", help="под отчётом — как исправить каждый код")
    args = ap.parse_args()
    if not args.project.is_dir():
        print(f"{args.project}: не папка проекта", file=sys.stderr)
        return 2
    if args.cmd == "skeleton":
        pr = bl.parse(args.project)
        if pr.errors:
            _bl_lint.report(pr, False)
            print("contracts skeleton: сначала карта без ошибок — ./blueprint.py apply", file=sys.stderr)
            return 2
        pr.issues = []
        files = bc.skeleton(pr, bc.parse(pr))
        for rel, text in files:
            f = args.project / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
            print(f"contracts skeleton: {f}")
        print(f"contracts skeleton: стыков без контракта — {len(files)}; шаблон и правила — .blueprint/templates/contract.md, .blueprint/rules/contracts.md")
        print("дальше: заполни места {{…}} в каждом файле, затем ./blueprint.py contracts — до 0 ошибок")
        return 0
    try:
        pr, contracts = run(args.project, args.source, args.no_source)
    except OSError as e:
        print(f"{args.project}: не прочитан: {e}", file=sys.stderr)
        return 2
    if pr.errors and not contracts and any(not i.code.startswith("CT") for i in pr.errors):
        _bl_lint.report(pr, False)
        print("contracts-lint: сначала карта — ./blueprint.py lint", file=sys.stderr)
        return 2
    rc = report(pr, contracts, args.strict)
    if args.hints:
        codes = sorted({i.code for i in pr.issues if i.code in bc.HINTS})
        if codes:
            print("как исправить:")
            for c in codes:
                print(f"  {c} — {bc.HINTS[c]}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""bft-proto — прототип по контрактам: план показа prototype/spec.md → docker-compose с web и MockAPI.

Экраны — из «Истории», данные — из контрактов contracts/C-N.md. Стандарт — `resources/prototype.md`.

  ОШИБКИ (код выхода 1)
  PT001  форма плана: «## Ш7 · Название», строки «ключ: значение», ключи из списка, без повторов
  PT002  шаг не из «Истории» или внешний шаг C-N без контракта
  PT003  приложение — client | staff | admin | external | backend
  PT004  экрана нет в «Истории»
  PT005  вызов: контракта нет или это service-db
  PT006  ввод: поля нет в «Запросе», обязательное поле без значения
  PT007  показать: поля нет в «Ответе»
  PT008  отказ: кода нет в «Ошибках» контракта
  PT009  в плане остались места {{…}}

  ПРЕДУПРЕЖДЕНИЯ
  PT020  контракт ни на одном шаге — стык не показан
  PT021  вызов без «показать»

Использование:
    python3 bft-proto.py skeleton <проект> [--force]   — каркас prototype/spec.md из истории, карты и контрактов
    python3 bft-proto.py lint <проект> [--strict]       — проверка плана показа (и контрактов: CT)
    python3 bft-proto.py build <проект>                 — сборка prototype/: web, api, docker-compose.yml
    python3 bft-proto.py review <проект> <review.json>  — замечания прототипа → «Вопросы» плана карты
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bft_backlog as bl  # noqa: E402
import bft_contracts as bc  # noqa: E402
import bft_proto as bpt  # noqa: E402
import bft_plan as bp  # noqa: E402


def load(root: Path):
    pr = bl.parse(root)
    if pr.errors or not pr.story:
        for i in pr.errors:
            print(f"{root / i.path if i.path else root}:{i.line}: {i.level} {i.code} {i.msg}")
        print("prototype: сначала карта без ошибок и с «Историей» — ./blueprint.py lint", file=sys.stderr)
        return None, []
    pr.issues = []
    cs = bc.parse(pr)
    bc.check(pr, cs)
    return pr, cs


def report(pr: bl.Project, strict: bool, name: str) -> int:
    for i in sorted(pr.issues, key=lambda i: (i.level != "ERROR", i.path, i.line)):
        print(f"{pr.root / i.path if i.path else pr.root}:{i.line}: {i.level} {i.code} {i.msg}")
    errors = len(pr.errors)
    codes = sorted({i.code for i in pr.issues})
    hints = {**bc.HINTS, **bpt.HINTS}
    if codes:
        print("как исправить:")
        for c in codes:
            if c in hints:
                print(f"  {c} — {hints[c]}")
    print(f"{name}: ошибок {errors}, предупреждений {len(pr.issues) - errors}")
    return 1 if errors or (strict and len(pr.issues) > errors) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("skeleton", "lint", "build", "review"))
    ap.add_argument("project", type=Path)
    ap.add_argument("file", nargs="?", type=Path, help="review: review.json, выгруженный из прототипа")
    ap.add_argument("--force", action="store_true", help="skeleton: перезаписать prototype/spec.md")
    ap.add_argument("--strict", action="store_true", help="предупреждения тоже дают код 1")
    a = ap.parse_args()
    root = a.project.resolve()
    if bl.find_backlog(root) is None:
        print(f"{root}: не проект Backlog.md", file=sys.stderr)
        return 2
    pr, cs = load(root)
    if pr is None:
        return 2
    f = root / bpt.DIR / bpt.SPEC
    if a.cmd == "skeleton":
        if f.is_file() and not a.force:
            print(f"prototype skeleton: {f} уже есть — не перезаписываю (--force, если нужно с нуля)", file=sys.stderr)
            return 2
        if not cs:
            print("prototype skeleton: контрактов нет — сначала ./blueprint.py contracts skeleton (автопилот, шаг 7)", file=sys.stderr)
        f.parent.mkdir(parents=True, exist_ok=True)
        text = bpt.skeleton(pr, cs)
        f.write_text(text, encoding="utf-8")
        steps = text.count("\n## ")
        print(f"prototype skeleton: {f} — шагов {steps}, мест {{{{…}}}} {text.count('{{')}")
        print("дальше: заполни места {{…}} (правила — .blueprint/rules/prototype.md), затем ./blueprint.py prototype lint")
        return 0
    sp = bpt.parse(pr)
    if sp is None:
        print("prototype: плана показа нет — ./blueprint.py prototype skeleton", file=sys.stderr)
        return 2
    bpt.check(pr, sp, cs)
    if a.cmd == "lint":
        return report(pr, a.strict, "prototype-lint")
    if a.cmd == "build":
        if pr.errors:
            report(pr, False, "prototype-build")
            print("prototype build: план или контракты с ошибками — ничего не собрано", file=sys.stderr)
            return 1
        out = root / bpt.DIR
        written = bpt.build(pr, sp, cs, out)
        report(pr, False, "prototype-build")
        print(f"prototype build: {out} — обновлено файлов {len(written)}")
        print(f"  показ без сервера: {out / 'web' / 'index.html'}")
        print(f"  с MockAPI: cd {out} && docker compose up → http://localhost:8080")
        return 0
    # review: пины → «Вопросы» плана карты
    if not a.file or not a.file.is_file():
        print("prototype review: укажи review.json, выгруженный кнопкой «Выгрузить»", file=sys.stderr)
        return 2
    pins = json.loads(a.file.read_text(encoding="utf-8")).get("pins", [])
    rows = bpt.review_rows(pr, sp, cs, pins)
    pf = root / bp.PLAN_DIR / "map.md"
    if not pf.is_file():
        print("prototype review: плана карты нет — ./blueprint.py export, затем снова review", file=sys.stderr)
        return 2
    lines = pf.read_text(encoding="utf-8").split("\n")
    head = next((i for i, ln in enumerate(lines) if ln.strip() == "## Вопросы"), None)
    if head is None:
        print("prototype review: в плане нет «## Вопросы»", file=sys.stderr)
        return 2
    end = head + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    last = max((i for i in range(head, end) if lines[i].startswith("|")), default=head)
    nums = [int(x) for ln in lines[head:end] for x in __import__("re").findall(r"^\| В(\d+) \|", ln)]
    have = "\n".join(lines[head:end])
    new = []
    for where, q, who in rows:
        if q in have:
            continue
        n = max(nums + [0]) + 1
        nums.append(n)
        new.append(f"| В{n} | {who} | {q} | {where} | вопрос | — |")
    if new:
        if last == head:   # таблицы ещё нет
            new = ["", "| ID | Кому | Вопрос | Где | Тип | Ответ |", "| --- | --- | --- | --- | --- | --- |"] + new
        lines[last + 1:last + 1] = new
        pf.write_text("\n".join(lines), encoding="utf-8")
    print(f"prototype review: замечаний {len(pins)}, новых вопросов в {pf.relative_to(root)} — {len([x for x in new if x.startswith('| В')])}")
    print("дальше: ./blueprint.py apply — вопросы попадут в «Карту», красные точки — на карточки")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""bft-plan — план карты в проекте Backlog.md: apply, export, next.

    python3 bft-plan.py apply  <проект>   план plan/map.md и plan/screens/*.md → задачи, карточки, документы;
                                          затем проверка карты с адресами строк плана и подсказками
    python3 bft-plan.py export <проект> [--force]   бэклог → план (для правок одним файлом)
    python3 bft-plan.py next   <проект>   что исправить дальше: ошибки по плану, подсказки, итог

В проекте те же команды — `./blueprint.py apply | export | next`. Формат плана — `bft_plan.py`,
методология — `resources/autopilot.md`. Коды выхода: 0 — ошибок нет, 1 — есть, 2 — нет проекта.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bft_backlog as bl  # noqa: E402
import bft_plan as bp  # noqa: E402


def _lint():
    spec = importlib.util.spec_from_file_location("bl_lint", HERE / "bft-backlog-lint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def review(root: Path, source: str | None = None) -> int:
    """Проверка карты, адресованная плану: строка плана, код, сообщение; ниже — как исправить."""
    lint = _lint()
    pr = lint.run(root, source, False)
    if not pr.tasks and not (root / bp.PLAN_DIR / "map.md").is_file():
        # карты ещё нет: «потерянные требования» пустого бэклога — не ошибки, а работа шага 4
        print("карта: задач нет, плана plan/map.md нет — начни с каркаса")
        print("дальше: ./blueprint.py skeleton, затем ./blueprint.py groom fill (автопилот, шаг 4)")
        return 0
    pf = root / bp.PLAN_DIR / "map.md"
    stamp = root / ".blueprint" / bp.APPLIED
    if stamp.is_file():
        stale = stamp.read_text(encoding="utf-8").strip() != bp.plan_hash(root)
    else:   # проект до отметки .applied — по времени файлов
        tasks_dir = (pr.bdir or root / "backlog") / "tasks"
        newest = max([f.stat().st_mtime for f in tasks_dir.glob("*.md")] + [0]) if tasks_dir.is_dir() else 0
        stale = pf.is_file() and pf.stat().st_mtime > newest + 1
    if pf.is_file() and stale and "{{" not in pf.read_text(encoding="utf-8"):
        # план новее бэклога: проверка бэклога сказала бы про старую карту
        print(f"карта: план {bp.PLAN_DIR}/map.md новее бэклога — ещё не применён")
        print("дальше: ./blueprint.py apply — он применит план и проверит карту по строкам плана")
        return 0
    if pf.is_file() and "{{" in pf.read_text(encoding="utf-8"):
        print(f"карта: в {bp.PLAN_DIR}/map.md остались места {{{{…}}}} — ./blueprint.py groom fill или допиши сам, затем ./blueprint.py apply")
        return 0
    pl = bp.parse(root) if pf.is_file() else None
    where: dict[str, str] = {}
    if pl:
        for b in pl.blocks:
            where[b.id] = f"{bp.PLAN_DIR}/map.md:{b.line}"
        for sid, (_, _, f) in pl.screens.items():
            where[sid] = f"{bp.PLAN_DIR}/screens/{f.name}:1"
    by_rel = {t.rel: t.id for t in pr.tasks + pr.cards}
    by_rel.update({d.rel: sid for sid, d in pr.screens.items()})
    for i in sorted(pr.issues, key=lambda i: (i.level != "ERROR", i.path, i.line)):
        key = by_rel.get(i.path, "")
        loc = where.get(key) or (f"{root / i.path}:{i.line}" if i.path else str(root))
        if pr.map_doc and i.path == pr.map_doc.rel and pl:
            loc = f"{bp.PLAN_DIR}/map.md"
        print(f"{loc}: {i.level} {i.code} {key + ': ' if key else ''}{i.msg}")
    errors = len(pr.errors)
    open_q = sum(q.open for q in pr.questions)
    print(f"карта: {len(pr.tasks)} задач, {len(pr.cards)} карточек, {len(pr.screens)} экранов с требованиями, "
          f"открытых вопросов {open_q} — ошибок {errors}, предупреждений {len(pr.issues) - errors}")
    for line in quality(pr):
        print(line)
    lint.hints(pr)
    if errors:
        print("дальше: исправь план и снова ./blueprint.py apply")
    else:
        page = root / f"{pr.meta.get('epic_slug', '')}-map.html"
        built = page.is_file() and page.stat().st_mtime >= max(
            [f.stat().st_mtime for d in (bp.PLAN_DIR, "backlog") for f in (root / d).rglob("*.md")] + [0])
        if built:
            import bft_contracts as bc
            pr.issues = []
            cs = bc.parse(pr)
            bc.check(pr, cs)
            ct_err = sum(i.level == "ERROR" for i in pr.issues)
            ct_open = sum(i.code == "CT020" for i in pr.issues)
            if ct_err or ct_open:
                print(f"дальше: карта собрана — {page.name}; контракты стыков: ошибок {ct_err}, стыков без контракта {ct_open} — "
                      "./blueprint.py contracts skeleton, затем ./blueprint.py contracts")
            else:
                print(f"готово: карта {page.name} собрана, контрактов {len(cs)} без ошибок — итог по шагу 8 автопилота")
        else:
            print("дальше: ./blueprint.py build — схемы BPMN, картинки экранов, страница и архив")
    return 1 if errors else 0


def quality(pr) -> list[str]:
    """Сводка для рубрики качества (resources/autopilot.md, шаг 6): числа, по которым видно слабое место карты."""
    lanes = [len(bl.lanes_of(c.proc)) for c in pr.cards if c.proc]
    linked = {x for a, b, _ in pr.links() for x in (a, b)}
    layers = {lay: sum(c.layer == lay for c in pr.cards) for lay in bl.LAYERS}
    teams_used = {t.team for t in pr.tasks if t.team and t.team != "?"}
    stages = [s.id for s in pr.story.stages] if pr.story else []
    empty = [s for s in stages if not any(t.stage == s for t in pr.tasks)]
    out = ["качество:",
           f"  команд в работе {len(teams_used)} из {len(pr.teams)}; задач без исполнителя {sum(t.team == '?' for t in pr.tasks)}",
           "  слои: " + ", ".join(f"{k} {v}" for k, v in layers.items()),
           f"  карточек на задачу {len(pr.cards) / max(1, len(pr.tasks)):.1f}; без связей {sum(c.id not in linked for c in pr.cards)}; "
           f"процессов в одну дорожку {sum(n == 1 for n in lanes)} из {len(lanes)}",
           f"  этапов без задач {len(empty)}{' (' + ', '.join(empty) + ')' if empty else ''}; открытых вопросов {sum(q.open for q in pr.questions)}"]
    warn = []
    if len(teams_used) <= 1 and len(pr.tasks) >= 4:
        warn.append("одна команда на всю карту — раздели по системам-владельцам или задай вопрос, кто делает (рубрика, пункт 3)")
    if not layers["technology"]:
        warn.append("нет карточек technology — что видит пользователь? (пункт 4)")
    if lanes and sum(n == 1 for n in lanes) > len(lanes) / 2:
        warn.append("больше половины процессов в одну дорожку — кто передаёт и кто получает результат? (пункт 7)")
    out += [f"  ! {w}" for w in warn]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("apply", "export", "next"))
    ap.add_argument("project", type=Path)
    ap.add_argument("--force", action="store_true", help="export: переписать существующий план")
    ap.add_argument("--source", help="apply, next: путь к БФТ (по умолчанию — `source_doc` паспорта рядом с проектом)")
    a = ap.parse_args()
    root = a.project.resolve()
    if bl.find_backlog(root) is None:
        print(f"{root}: не проект Backlog.md — сначала bft-backlog-init.py <epic>-story.md", file=sys.stderr)
        return 2
    if a.cmd == "export":
        files = bp.export(root)
        if (root / bp.PLAN_DIR / "map.md").is_file() and not a.force:
            print(f"{root / bp.PLAN_DIR}: план уже есть — --force перепишет его из бэклога", file=sys.stderr)
            return 1
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        print(f"plan: {len(files)} файлов — {root / bp.PLAN_DIR}")
        return 0
    if a.cmd == "apply":
        pl = bp.parse(root)
        if pl.issues:
            for i in pl.issues:
                print(f"{i.path}:{i.line}: {i.level} {i.code} {i.msg}")
            print(f"plan: ошибок {len(pl.issues)} — в бэклог ничего не записано")
            return 1
        for line in bp.apply(pl, root):
            print(f"  {line}")
    return review(root, a.source)


if __name__ == "__main__":
    sys.exit(main())

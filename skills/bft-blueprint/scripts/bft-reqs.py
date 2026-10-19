#!/usr/bin/env python3
"""bft-reqs — инвентарь БФТ для карты: что взять из документа и куда это ложится.

Первый шаг автопилота (`resources/autopilot.md`). Читает БФТ и печатает рабочий лист:

  1. требования — ID, тип, наименование и место на карте; ФТ, ИТ, НФТ обязаны попасть в задачу
     или карточку (BL017), БТ и ПТ — в историю и UserStory;
  2. акторы «Плана демонстрации» → персонажи истории;
  3. How to demo и «Изменение в UJM» → этапы истории, «было → стало», HowToDemo задач;
  4. сценарий приёмки → шаги истории и «Процесс» карточек;
  5. зависимости → команды «Карты»;
  6. ограничения → «Управление» карточек;
  7. `[УТОЧНИТЬ]` документа → «Вопросы».

Ничего не придумывает и не пишет: только раскладывает текст БФТ по местам карты.

Использование:
    python3 bft-reqs.py <БФТ.md> [--out ФАЙЛ]
В проекте: ./blueprint.py reqs   (БФТ — `source_doc` паспорта рядом с проектом)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bft_blueprint as bb  # noqa: E402

# тип требования → где он живёт на карте
PLACE = {
    "БТ": "история: «было → стало» персонажа; зачем задач",
    "ПТ": "история: шаг персонажа; UserStory и JobStory карточек",
    "ИТ": "задача «Что делаем» + карточка Technology (что видит гость) + требования к экрану",
    "ФТ": "задача «Что делаем» + карточка Backstage (или Technology, если видно гостю)",
    "НФТ": "«Управление» карточки, которую ограничивает; своя задача — если это отдельная работа (Support)",
}
MUST = ("ФТ", "ИТ", "НФТ")
UNSURE = re.compile(r"\[УТОЧНИТЬ[^\]]*\]")


def sections(text: str) -> dict[str, list[str]]:
    """Разделы `##` и `###` → строки до следующего заголовка того же или старшего уровня."""
    out: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.*?)\*?\s*$", line)
        if m:
            cur = m.group(2).strip()
            out.setdefault(cur, [])
            continue
        if cur:
            out[cur].append(line)
    return out


def find(secs: dict, *keys: str) -> list[str]:
    for name, lines in secs.items():
        if any(k.lower() in name.lower() for k in keys):
            return lines
    return []


def table_rows(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    for header, rows in bb.tables(lines):
        return header, [cells for _, cells in rows]
    return [], []


def numbered(lines: list[str]) -> list[str]:
    return [re.sub(r"^\s*\d+\.\s*", "", ln).strip() for ln in lines if re.match(r"^\s*\d+\.\s", ln)]


def plantuml_steps(lines: list[str]) -> list[str]:
    """Шаги сценария из plantuml: «кто → кому: что», ветки alt/else — как есть."""
    out, inside, alias = [], False, {}
    for ln in lines:
        m = re.match(r'^\s*(?:actor|participant)\s+"?([^"]+?)"?\s+as\s+(\S+)', ln)
        if m:
            alias[m.group(2)] = m.group(1)
        s = ln.strip()
        if s.startswith("@startuml"):
            inside = True
            continue
        if s.startswith("@enduml"):
            inside = False
            continue
        if not inside or not s or s.startswith(("autonumber", "activate", "deactivate", "actor", "participant", "skinparam")):
            continue
        m = re.match(r"^(\S+)\s*-+>+\s*(\S+)\s*:\s*(.+)$", s)
        if m:
            out.append(f"{alias.get(m.group(1), m.group(1))} → {alias.get(m.group(2), m.group(2))}: {m.group(3)}")
        elif re.match(r"^(alt|else|end|opt|loop)\b", s):
            out.append(s)
    return out


def inventory(path: Path) -> str:
    reqs, text = bb.load_requirements(path)
    secs = sections(text)
    fm, _ = bb.frontmatter(text)
    epic = fm.get("epic_slug", path.stem)
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), epic)
    o = [f"# Инвентарь БФТ: {title}", "",
         f"Источник: `{path.name}`, ревизия `{bb.source_rev(path)}`, стадия `{fm.get('stage', '?')}`. "
         "Это рабочий лист: каждая строка ниже должна найти место в истории или на карте.", ""]

    # 1. требования
    by_type: dict[str, list[str]] = {}
    for rid in reqs:
        by_type.setdefault(rid.split("-")[0], []).append(rid)
    o += ["## 1. Требования", "",
          f"Всего {len(reqs)}: " + ", ".join(f"{t} — {len(v)}" for t, v in by_type.items()) + ". "
          f"ФТ, ИТ, НФТ ({sum(len(by_type.get(t, [])) for t in MUST)}) — каждое в «Требования БФТ:» задачи или в тексте карточки, иначе BL017.", "",
          "| ID | Наименование | Куда на карте | [ ] |", "| --- | --- | --- | --- |"]
    for rid, name in reqs.items():
        o.append(f"| {rid} | {name.replace('|', '/')} | {PLACE.get(rid.split('-')[0], '')} | [ ] |")
    o.append("")

    # 2. акторы
    head, rows = table_rows(find(secs, "Акторы"))
    o += ["## 2. Акторы → персонажи истории", "",
          "Персонаж — тот, кто пользуется результатом и что-то видит. Команда-исполнитель и внешняя система — не персонаж: "
          "они станут командами «Карты» и участниками «Процесса».", ""]
    o += [f"- **{r[0]}** — {r[1] if len(r) > 1 else ''}" for r in rows] or ["- в БФТ нет таблицы «Акторы» — возьми «Когда я (…)» из ПТ"]
    o.append("")

    # 3. How to demo и UJM
    demo = numbered(find(secs, "How to demo"))
    o += ["## 3. How to demo → этапы и HowToDemo", "",
          "Этапы истории — моменты пути по времени (A, B, C…); подготовка до старта — первым этапом. "
          "Шаги ниже — HowToDemo задач и проверка, что этапы ничего не потеряли.", ""]
    o += [f"{i}. {x}" for i, x in enumerate(demo, 1)] or ["- в БФТ нет How to demo"]
    o.append("")
    head, rows = table_rows(find(secs, "Изменение в UJM"))
    if rows:
        o += ["### Изменение в UJM → «было → стало»", "", "| Точка | Было | Стало |", "| --- | --- | --- |"]
        o += [f"| {r[0]} | {r[1] if len(r) > 1 else ''} | {r[2] if len(r) > 2 else ''} |" for r in rows]
        o.append("")

    # 4. сценарий
    scen = find(secs, "Сценарий приёмки", "Сценарий приемки")
    steps = plantuml_steps(scen) or numbered(scen)
    o += ["## 4. Сценарий приёмки → шаги истории и «Процесс» карточек", "",
          "Участник слева от стрелки — дорожка «Процесса» (`- Участник: действие`); `alt`/`else` — развилка `- ? вопрос`.", ""]
    o += [f"- {s}" for s in steps] or ["- сценария в БФТ нет"]
    head, rows = table_rows(scen)
    if rows and head and "What-if" in head[0]:
        o += ["", "Что если (alt-ветки, вопросы):", ""] + [f"- {r[0]} → {r[-1]}" for r in rows]
    o.append("")

    # 5. зависимости
    head, rows = table_rows(find(secs, "Зависимости"))
    o += ["## 5. Зависимости → команды «Карты»", "",
          "Каждая строка — кандидат в команду (ID латиницей: `vit`, `teama`). Исполнителя задачи бери отсюда; "
          "не ясно, кто делает, — задача без исполнителя с метками `кандидат:<id>`.", ""]
    o += [f"- **{r[0]}** — {' · '.join(c for c in r[1:] if c)}" for r in rows] or ["- раздела «Зависимости» нет — команды `[УТОЧНИТЬ у PO]`"]
    o.append("")

    # 6. ограничения
    lim = [ln.strip().lstrip("*-• ").strip() for ln in find(secs, "Ограничения") if ln.strip().lstrip("*-• ").strip()]
    o += ["## 6. Ограничения → «Управление» карточек", ""] + ([f"- {x}" for x in lim] or ["- нет"]) + [""]

    # 7. уточнить
    asks = []
    for ln in text.splitlines():
        for m in UNSURE.finditer(ln):
            ctx = re.sub(r"\s+", " ", ln.strip().strip("|"))[:140]
            asks.append(f"- {m.group(0)} — {ctx}")
    o += ["## 7. [УТОЧНИТЬ] в БФТ → «Вопросы» «Карты» и «Истории»", "",
          "Открытое в БФТ остаётся открытым на карте: строка «Вопросов» с «Кому» из метки, не ответ.", ""]
    o += list(dict.fromkeys(asks))[:60] or ["- нет"]
    o.append("")
    return "\n".join(o)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bft", type=Path, nargs="?")
    ap.add_argument("--project", type=Path, help="проект Backlog.md: БФТ — `source_doc` паспорта рядом с ним")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.project and not a.bft:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import bft_backlog as bl
        pr = bl.parse(a.project.resolve())
        doc = pr.meta.get("source_doc", "")
        a.bft = next((b / doc for b in (pr.root, pr.root.parent) if doc and (b / doc).is_file()), Path(doc or "—"))
    if not a.bft:
        ap.error("нужен путь к БФТ или --project")
    if not a.bft.is_file():
        print(f"bft-reqs: нет файла {a.bft}", file=sys.stderr)
        return 2
    page = inventory(a.bft)
    if a.out:
        a.out.write_text(page, encoding="utf-8")
        print(f"bft-reqs: {a.out}")
    else:
        print(page)
    return 0


if __name__ == "__main__":
    sys.exit(main())

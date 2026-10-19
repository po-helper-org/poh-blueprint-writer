#!/usr/bin/env python3
"""bft-groom — груминг карты роем агентов: аудит → доработка → слияние.

    python3 bft-groom.py audit  <проект>   волна 1: пакеты аудита в groom/1-audit/ — роли покрытия, выдумок,
                                           отказов, команд, вопросов и по пакету «поток» на каждый этап
    python3 bft-groom.py refine <проект>   волна 2: пакет на каждую задачу и карточку в groom/2-refine/,
                                           в пакете — находки аудита по этой цели
    python3 bft-groom.py merge  <проект>   замены блоков и новые вопросы — в plan/map.md, затем apply;
                                           отчёт — groom/report.md

Пакет — самодостаточный промпт: роль, чек-лист (`resources/grooming.md`), вырезка из БФТ и плана под цель,
формат ответа. Ответ агента — groom/<волна>/out/<имя пакета>. Слияние защищено: замена сначала
проходит apply и проверку карты в копии проекта; ломает план (PL), карту (BL) или теряет ID требования
своего блока — отклоняется, остальное применяется. В бэклог всё попадает
через план и `apply`. Методология — `resources/grooming.md`.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bft_backlog as bl  # noqa: E402
import bft_blueprint as bb  # noqa: E402
import bft_plan as bp  # noqa: E402

GROOM = "groom"
AUDIT, REFINE = "1-audit", "2-refine"
GLOBAL = (("coverage", "Аудитор покрытия"), ("fabrication", "Охотник за выдумками"), ("failures", "Архитектор надёжности"),
          ("teams", "Архитектор границ"), ("questions", "Куратор вопросов"))
FINDING = re.compile(r"^-\s*(критично|важно|мелочь)\s*·\s*([^·]+?)\s*·\s*(.+)$")
LEVELS = {"критично": 0, "важно": 1, "мелочь": 2}


def _mod(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rules_file(name: str) -> Path:
    for d in (HERE.parent / "resources", HERE.parent / "rules"):
        if (d / name).is_file():
            return d / name
    raise SystemExit(f"groom: нет {name} рядом со скриптами")


def guide() -> dict[str, str]:
    """Разделы grooming.md: общие правила, формат ответа, линзы по ключу."""
    text = rules_file("grooming.md").read_text(encoding="utf-8")
    out, cur, buf, code = {}, None, [], False
    for line in text.split("\n") + ["## конец"]:
        if line.startswith("```"):
            code = not code
        if line.startswith("## ") and not code:
            if cur:
                out[cur] = "\n".join(buf).strip()
            name = line[3:].strip()
            cur = name.split(":", 1)[1].strip() if name.startswith("Линза:") else name
            buf = []
        else:
            buf.append(line)
    return out


# --- БФТ: строки требований, «что если», ограничения ------------------------------------------------

def bft_parts(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {"text": "", "rows": {}, "whatif": [], "limits": [], "name": "—"}
    text = path.read_text(encoding="utf-8")
    rows, whatif = {}, []
    for header, body in bb.tables(text.splitlines()):
        for _, cells in body:
            if not cells:
                continue
            first = cells[0].strip()
            if re.fullmatch(bb.REQ_RE, first) and first not in rows:
                rows[first] = f"**{first}** — " + "; ".join(f"{h.strip()}: {c.strip()}" for h, c in zip(header[1:], cells[1:]) if c.strip())
            elif header and "what-if" in header[0].lower():
                whatif.append(" · ".join(c.strip() for c in cells if c.strip()))
    reqs = _mod("bft_reqs", "bft-reqs.py")
    lim = [ln.strip().lstrip("*-• ").strip() for ln in reqs.find(reqs.sections(text), "Ограничения") if ln.strip().lstrip("*-• ").strip()]
    return {"text": text, "rows": rows, "whatif": whatif, "limits": lim, "name": path.name}


def ids_in(text: str) -> list[str]:
    return list(dict.fromkeys(bb.REQ_RE.findall(text)))


# --- план: блоки как текст ---------------------------------------------------------------------------

def plan_lines(root: Path) -> list[str]:
    return (root / bp.PLAN_DIR / "map.md").read_text(encoding="utf-8").split("\n")


def block_spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """ID блока → (начало, конец) в строках плана; конец — следующий заголовок `## `."""
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    spans = {}
    for k, i in enumerate(heads):
        m = bp.HEAD.match(lines[i])
        if m:
            spans[m.group(1).upper()] = (i, heads[k + 1] if k + 1 < len(heads) else len(lines))
    return spans


def block_text(lines: list[str], spans: dict, bid: str) -> str:
    a, b = spans[bid]
    return "\n".join(lines[a:b]).strip("\n")


def section(lines: list[str], name: str) -> str:
    for i, ln in enumerate(lines):
        if ln.strip() == f"## {name}":
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
            return "\n".join(lines[i:j]).strip("\n")
    return ""


def links_of(pr: bl.Project, cid: str) -> set[str]:
    return {b for a, b, _ in pr.links() if a == cid} | {a for a, b, _ in pr.links() if b == cid}


# --- пакет ---------------------------------------------------------------------------------------------

def packet(g: dict, lens: str, title: str, target: str, out: str, context: list[str]) -> str:
    return "\n".join([
        f"# Пакет груминга · {title} · {target}", "",
        "Ты выполняешь один пакет груминга карты Service Blueprint. Читай только этот файл: всё нужное — в нём.",
        f"Ответ запиши в файл `{out}` (путь от папки проекта) строго в формате раздела «Формат ответа». Больше ничего не меняй.", "",
        "## Общие правила", "", g["Общие правила для всех ролей"], "",
        f"## Твоя роль и чек-лист", "", g[lens], "",
        "## Формат ответа", "", g["Формат ответа пакета"], "",
        "## Контекст", "", *context, ""])


def fence(text: str) -> list[str]:
    return ["```markdown", text.strip("\n"), "```"]


def req_context(parts: dict, ids: list[str]) -> list[str]:
    rows = [parts["rows"][i] for i in ids if i in parts["rows"]]
    wi = [w for w in parts["whatif"] if any(i in w for i in ids)]
    out = ["### Требования БФТ", ""] + ([f"- {r}" for r in rows] or ["- в блоках нет ID требований"])
    if wi:
        out += ["", "### «Что если» из БФТ по этим требованиям", ""] + [f"- {w}" for w in wi]
    if parts["limits"]:
        out += ["", "### Ограничения БФТ", ""] + [f"- {x}" for x in parts["limits"]]
    return out


def write_packets(root: Path, wave: str, packs: dict[str, str]) -> Path:
    d = root / GROOM / wave
    if d.is_dir():
        for f in d.glob("*.md"):
            f.unlink()
    (d / "out").mkdir(parents=True, exist_ok=True)
    for name, text in packs.items():
        (d / name).write_text(text, encoding="utf-8")
    return d


def audit(root: Path) -> int:
    pr = bl.parse(root)
    lint = _mod("bl_lint", "bft-backlog-lint.py")
    parts = bft_parts(lint.resolve_source(pr, None))
    lines = plan_lines(root)
    g = guide()
    plan_text = re.sub(r"^### BPMN\n```mermaid\n.*?```\n?", "", "\n".join(lines), flags=re.S | re.M)
    packs = {}
    for key, title in GLOBAL:
        name = f"a-{key}.md"
        ctx = ["### БФТ целиком", ""] + fence(parts["text"] or "БФТ не найден рядом с проектом — работай по плану") + \
              ["", "### План карты целиком", ""] + fence(plan_text)
        packs[name] = packet(g, key, title, "вся карта", f"{GROOM}/{AUDIT}/out/{name}", ctx)
    spans = block_spans(lines)
    story = pr.story
    for st in story.stages if story else []:
        blocks = [b for b in (pr.tasks + pr.cards) if b.stage == st.id]
        if not blocks:
            continue
        near = {x for c in pr.cards if c.stage == st.id for x in links_of(pr, c.id)} - {b.id for b in blocks}
        steps = [s for s in story.steps if s.stage_from == st.id]
        ctx = ["### Этап истории", "", f"**{st.id} · {st.name}** — {st.when}", ""]
        ctx += [f"- {s.id} · {next((p.name for p in story.personas if p.id == s.persona), s.persona)}: {s.title} — {s.text}"
                f"{' · экраны ' + ', '.join(s.screens) if s.screens else ''}" for s in steps] or ["- шагов на этапе нет"]
        ids = ids_in("\n".join(block_text(lines, spans, b.id) for b in blocks if b.id in spans))
        ctx += [""] + req_context(parts, ids) + ["", "### Задачи и карточки этапа", ""]
        ctx += fence("\n\n".join(block_text(lines, spans, b.id) for b in sorted(blocks, key=lambda x: x.ordinal) if b.id in spans))
        if near:
            ctx += ["", "### Связанные карточки других этапов", ""] + fence("\n\n".join(block_text(lines, spans, i) for i in sorted(near) if i in spans))
        name = f"a-flow-{st.id}.md"
        packs[name] = packet(g, "flow", "Архитектор потока", f"этап {st.id} · {st.name}", f"{GROOM}/{AUDIT}/out/{name}", ctx)
    d = write_packets(root, AUDIT, packs)
    print(f"groom audit: {len(packs)} пакетов — {d}")
    print(f"дальше: по агенту на каждый пакет (ответ — {GROOM}/{AUDIT}/out/<имя пакета>), затем ./blueprint.py groom refine")
    return 0


def findings(root: Path, wave: str) -> tuple[dict[str, list[str]], list[str], list[list[str]]]:
    """Находки по ID цели, общие находки, строки вопросов из ответов волны."""
    by_id: dict[str, list[str]] = {}
    general, questions = [], []
    for f in sorted((root / GROOM / wave / "out").glob("*.md")):
        mode = ""
        for ln in f.read_text(encoding="utf-8").split("\n"):
            if ln.startswith("## "):
                mode = ln[3:].strip()
                continue
            if mode == "Находки":
                m = FINDING.match(ln.strip())
                if not m:
                    continue
                item = f"{m.group(1)} · {m.group(3).strip()}  ← {f.stem}"
                targets = [x.upper() for x in re.findall(r"[A-Za-z]+-\d+(?:\.\d+)?", m.group(2))]
                for t in targets or ["—"]:
                    (by_id.setdefault(t, []) if targets else general).append(item)
            elif mode == "Вопросы" and ln.startswith("|") and "---" not in ln:
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if len(cells) >= 4 and cells[0] != "Кому":
                    questions.append(cells[:4])
    return by_id, general, questions


def refine(root: Path) -> int:
    pr = bl.parse(root)
    lint = _mod("bl_lint", "bft-backlog-lint.py")
    parts = bft_parts(lint.resolve_source(pr, None))
    lines = plan_lines(root)
    spans = block_spans(lines)
    g = guide()
    by_id, general, new_q = findings(root, AUDIT)
    qtable = section(lines, "Вопросы")
    packs = {}
    for t in pr.tasks:
        if t.id not in spans:
            continue
        cards = [c for c in pr.cards if c.parent == t.id and c.id in spans]
        own = block_text(lines, spans, t.id)
        ids = ids_in(own + "\n".join(block_text(lines, spans, c.id) for c in cards))
        fs = by_id.get(t.id, [])
        ctx = ["### Находки аудита по этой задаче", ""] + ([f"- {x}" for x in fs] or ["- нет"]) + [""]
        ctx += req_context(parts, ids) + ["", "### Задача — перепиши её блок целиком", ""] + fence(own)
        ctx += ["", "### Карточки задачи (для сверки TOBE; переписывает их другой агент)", ""] + \
            fence("\n\n".join(re.sub(r"^### BPMN\n```mermaid\n.*?```\n?", "", block_text(lines, spans, c.id), flags=re.S | re.M) for c in cards) or "карточек нет")
        nxt = max([int(c.id.rsplit(".", 1)[1]) for c in cards] + [0]) + 1
        ctx += ["", f"Новая карточка, если TOBE не сделано ни в одной: ID `{t.id}.{nxt}` и дальше по порядку."]
        name = f"r-{t.id}.md"
        packs[name] = packet(g, "task", "Техлид задачи", f"{t.id} · {t.title}", f"{GROOM}/{REFINE}/out/{name}", ctx)
    for c in pr.cards:
        if c.id not in spans:
            continue
        own = re.sub(r"^### BPMN\n```mermaid\n.*?```\n?", "", block_text(lines, spans, c.id), flags=re.S | re.M)
        parent = block_text(lines, spans, c.parent) if c.parent in spans else ""
        near = sorted(links_of(pr, c.id))
        ids = ids_in(own + parent)
        fs = by_id.get(c.id, []) + [f"{x}  (по задаче {c.parent})" for x in by_id.get(c.parent, []) if x.startswith("критично")]
        qs = [r for r in new_q if len(r) >= 3 and r[2].upper() in (c.id, c.parent)]
        ctx = ["### Находки аудита по этой карточке", ""] + ([f"- {x}" for x in fs] or ["- нет"]) + [""]
        if qs:
            ctx += ["### Новые вопросы аудита здесь (не дублируй их)", ""] + [f"- {r[0]}: {r[1]}" for r in qs] + [""]
        ctx += req_context(parts, ids) + ["", "### Карточка — перепиши её блок целиком", ""] + fence(own)
        ctx += ["", "### Задача-родитель (не переписывай)", ""] + fence(parent or "—")
        if near:
            ctx += ["", "### Связанные карточки: входы и выходы (не переписывай)", ""] + \
                fence("\n\n".join(re.sub(r"^### BPMN\n```mermaid\n.*?```\n?", "", block_text(lines, spans, i), flags=re.S | re.M) for i in near if i in spans))
        if qtable:
            ctx += ["", "### Вопросы карты", ""] + [ln for ln in qtable.split("\n")[1:] if c.id in ln or c.parent in ln or ln.startswith("| ID") or ln.startswith("| ---")]
        name = f"r-{c.id}.md"
        packs[name] = packet(g, "card", "Архитектор карточки", f"{c.id} · {c.title}", f"{GROOM}/{REFINE}/out/{name}", ctx)
    d = write_packets(root, REFINE, packs)
    print(f"groom refine: {len(packs)} пакетов ({len(pr.tasks)} задач, {len(pr.cards)} карточек), находок аудита — "
          f"{sum(len(v) for v in by_id.values())} по целям, общих {len(general)} — {d}")
    print(f"дальше: по агенту на каждый пакет (ответ — {GROOM}/{REFINE}/out/<имя пакета>), затем ./blueprint.py groom merge")
    return 0


# --- слияние -----------------------------------------------------------------------------------------

def replacements(text: str) -> list[tuple[str, str]]:
    """Блоки из раздела «Замены» ответа: (ID, текст блока)."""
    m = re.search(r"^## Замены\s*\n(.*)\Z", text, re.S | re.M)
    if not m:
        return []
    body = m.group(1)
    body = re.sub(r"^```(?:markdown)?\s*$", "", body, flags=re.M)
    out, cur, buf = [], None, []
    for ln in body.split("\n") + ["## конец"]:
        hm = bp.HEAD.match(ln)
        if hm or ln.startswith("## "):
            if cur:
                out.append((cur, "\n".join(buf).strip("\n")))
            cur, buf = (hm.group(1).upper(), [ln]) if hm else (None, [])
        elif cur:
            buf.append(ln)
    return out


def _map_errors(sand: Path, plan: str) -> tuple[list, set[str]] | None:
    """План в копии проекта → apply и полная проверка: (ошибки PL, ошибки карты «ID: код сообщение»)."""
    (sand / bp.PLAN_DIR / "map.md").write_text(plan, encoding="utf-8")
    pl = bp.parse(sand)
    if pl.issues:
        return pl.issues, set()
    bp.apply(pl, sand)
    pr = _mod("bft_lint", "bft-backlog-lint.py").run(sand, None, True)
    by_rel = {t.rel: t.id for t in pr.tasks + pr.cards}
    return [], {f"{by_rel.get(i.path, '—')}: {i.code} {i.msg}" for i in pr.errors}


def merge(root: Path) -> int:
    pf = root / bp.PLAN_DIR / "map.md"
    before = pf.read_text(encoding="utf-8")
    (root / GROOM).mkdir(exist_ok=True)
    (root / GROOM / "map.before.md").write_text(before, encoding="utf-8")
    lines = before.split("\n")
    # замену сначала применяем в копии проекта: план, apply и полная проверка карты — как у ведущего агента
    tmp = tempfile.TemporaryDirectory(prefix="groom-")
    sand = Path(tmp.name) / "p"
    shutil.copytree(root, sand, ignore=shutil.ignore_patterns(GROOM, ".git"))
    base_pl, base_map = _map_errors(sand, before)
    applied, rejected, skipped = [], [], []
    outs = sorted((root / GROOM / REFINE / "out").glob("*.md"))
    for f in outs:
        owner = f.stem[2:].upper() if f.stem.startswith("r-") else ""
        for bid, text in replacements(f.read_text(encoding="utf-8")):
            spans = block_spans(lines)
            own_task = owner and "." not in owner
            ok_target = bid == owner or (own_task and bid not in spans and bid.rsplit(".", 1)[0] == owner)
            if not ok_target:
                skipped.append(f"{bid} из {f.name}: пакет {owner or '?'} правит только свой блок" + (" и новые карточки задачи" if own_task else ""))
                continue
            trial = lines[:]
            old = ""
            if bid in spans:
                a, b = spans[bid]
                old = "\n".join(lines[a:b])
                trial[a:b] = text.split("\n") + [""]
            else:
                kids = [i for i in spans if i == owner or i.startswith(owner + ".")]
                end = max(spans[i][1] for i in kids)
                trial[end:end] = text.split("\n") + [""]
            lost = set(bb.REQ_RE.findall(old)) - set(bb.REQ_RE.findall(text))  # ID старого блока остаются в новом
            pl_errs, map_errs = _map_errors(sand, "\n".join(trial))
            new = map_errs - base_map
            if lost or len(pl_errs) > len(base_pl) or new:
                why = (f"теряет {', '.join(sorted(lost))}" if lost else
                       "; ".join(f"{i.code} {i.msg}" for i in pl_errs[len(base_pl):][:3]) if len(pl_errs) > len(base_pl) else
                       "; ".join(sorted(new)[:3]))
                rejected.append(f"{bid} из {f.name}: {why}")
                continue
            lines, base_map = trial, map_errs
            applied.append(f"{bid} ← {f.name}" + ("" if bid in spans else " (новая карточка)"))
    # вопросы обеих волн: без повторов, «Где» — существующий ID
    _, _, q1 = findings(root, AUDIT)
    _, _, q2 = findings(root, REFINE)
    text = "\n".join(lines)
    spans = block_spans(lines)
    qsec = section(lines, "Вопросы")
    have = {re.sub(r"\W+", " ", r.split("|")[3]).strip().lower() for r in qsec.split("\n") if r.startswith("| В")}
    nums = [int(m) for m in re.findall(r"^\| В(\d+) \|", qsec, re.M)]
    added = []
    for who, q, where, kind in q1 + q2:
        key = re.sub(r"\W+", " ", q).strip().lower()
        where = where.upper().strip()
        if not q or key in have or where not in spans:
            continue
        have.add(key)
        n = max(nums + [0]) + 1
        nums.append(n)
        added.append(f"| В{n} | {who} | {q} | {where} | {'блокер' if 'блок' in kind.lower() else 'вопрос'} | — |")
    if added:
        new_q = qsec.rstrip("\n") + "\n" + "\n".join(added)
        text = text.replace(qsec, new_q, 1) if qsec else text
    pf.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    tmp.cleanup()
    # находки, которые не стали заменой, — ведущему агенту
    f1, g1, _ = findings(root, AUDIT)
    f2, g2, _ = findings(root, REFINE)
    crit = sorted({f"{k}: {x}" for src in (f1, f2) for k, v in src.items() for x in v if x.startswith("критично")} |
                  {f"—: {x}" for x in g1 + g2 if x.startswith("критично")})
    pl = bp.parse(root)
    report = ["# Отчёт груминга", "",
              f"Ответов доработки: {len(outs)}. Замен применено: {len(applied)}, отклонено: {len(rejected)}, "
              f"не своих блоков: {len(skipped)}. Новых вопросов: {len(added)}. План до слияния — `{GROOM}/map.before.md`.", ""]
    report += ["## Применено", ""] + ([f"- {x}" for x in applied] or ["- нет"]) + [""]
    report += ["## Отклонено — исправь план руками", ""] + ([f"- {x}" for x in rejected] or ["- нет"]) + [""]
    if skipped:
        report += ["## Пропущено", ""] + [f"- {x}" for x in skipped] + [""]
    report += ["## Критичные находки — проверь, что закрыты", ""] + ([f"- {x}" for x in crit] or ["- нет"]) + [""]
    if added:
        report += ["## Новые вопросы", ""] + added + [""]
    (root / GROOM / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(f"groom merge: применено {len(applied)}, отклонено {len(rejected)}, пропущено {len(skipped)}, вопросов +{len(added)} — "
          f"{root / GROOM / 'report.md'}")
    if pl.issues:
        for i in pl.issues:
            print(f"{i.path}:{i.line}: {i.level} {i.code} {i.msg}")
        return 1
    plan_cli = _mod("bft_plan_cli", "bft-plan.py")
    for line in bp.apply(pl, root):
        print(f"  {line}")
    return plan_cli.review(root)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("audit", "refine", "merge"))
    ap.add_argument("project", type=Path)
    a = ap.parse_args()
    root = a.project.resolve()
    if bl.find_backlog(root) is None:
        print(f"{root}: не проект Backlog.md", file=sys.stderr)
        return 2
    if not (root / bp.PLAN_DIR / "map.md").is_file():
        files = bp.export(root)
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        print(f"groom: плана не было — выгружен из бэклога в {bp.PLAN_DIR}/")
    return {"audit": audit, "refine": refine, "merge": merge}[a.cmd](root)


if __name__ == "__main__":
    sys.exit(main())

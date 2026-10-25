"""Контракты стыков карты: разбор `contracts/C-N.md` и проверки CT (Design First).

Контракт — одна граница между системами: кто кого вызывает, каким методом, какие поля уходят и
приходят и откуда каждое поле в БФТ, пример ответа, ошибки, Sequence, цепочка преобразований
за кадром и «какие данные нужны» из хранилища. Стандарт — `resources/contracts.md`, шаблон —
`templates/contract.md`. Контракт ссылается на карточки «Как это работает» (`cards:`), карточки
о контрактах не знают: карта остаётся на высоте БФТ (BL018), а устройство стыка живёт здесь.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import bft_blueprint as bb
import bft_backlog as bl

DIR = "contracts"
BOUNDARIES = ("external", "frontend-backend", "service-service", "service-db")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
ID_RE = re.compile(r"^C-\d+$")
OP_RE = re.compile(rf"^({'|'.join(METHODS)})\s+(/\S*)$")
FAMILY_RE = re.compile(r"(?<![\w-])[A-Z]\d{1,2}(?![\w-])")   # параметр P5, инвариант I2, разрыв G1 из БФТ
TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
STUB_RE = re.compile(r"\{\{(.+?)\}\}")
FIELD_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
TOKEN_RE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")
GROUP_RE = re.compile(r"([A-Za-z_]\w*)\s*\{([^}]*)\}")       # ticket{event, used}
SEQ_RE = re.compile(r"^(.+?)\s*(-->|->)\s*(.+?)\s*:\s*(.+)$")  # A -> B: вызов · B --> A: ответ
WHERE = ("path", "query", "body", "header")
# высота стыка: в «Данных» — какие поля нужны, а не устройство хранилища (это работа СА)
DDL_RE = re.compile(r"\b(CREATE|ALTER|INDEX|PRIMARY\s+KEY|FOREIGN\s+KEY|VARCHAR|BIGINT|INTEGER|JOIN|SELECT|INSERT|UPDATE)\b|первичн\w* ключ|внешн\w* ключ|индекс", re.I)
SECTIONS = ("Запрос", "Ответ", "Пример ответа", "Ошибки", "Sequence", "Цепочка", "Данные")
COLUMNS = {
    "Запрос": ("Поле", "Тип", "Обяз.", "Где", "Источник"),
    "Ответ": ("Поле", "Тип", "Источник"),
    "Ошибки": ("Статус", "Код", "Когда"),
    "Цепочка": ("Шаг", "Кто", "Вход", "Что делает", "Выход"),
    "Данные": ("Хранилище", "Какие данные нужны", "Источник"),
}


@dataclass
class Row:
    line: int
    cells: dict


@dataclass
class Call:
    line: int
    src: str
    arrow: str        # -> вызов, --> ответ
    dst: str
    msg: str


@dataclass
class Contract:
    id: str
    path: Path
    rel: str
    fm: dict
    off: int
    sections: dict = field(default_factory=dict)   # {раздел: (строка, текст)}
    tables: dict = field(default_factory=dict)     # {раздел: [Row]}
    example: object = None
    sequence: list = field(default_factory=list)   # [Call]

    def get(self, key: str) -> str:
        v = self.fm.get(key, "")
        return ", ".join(v) if isinstance(v, list) else str(v or "").strip()

    @property
    def title(self) -> str:
        return self.get("title")

    @property
    def boundary(self) -> str:
        return self.get("boundary")

    @property
    def cards(self) -> list[str]:
        return [x.strip() for x in re.split(r"[,\s]+", self.get("cards")) if x.strip()]

    def rows(self, sec: str) -> list[Row]:
        return self.tables.get(sec, [])

    def fields(self, sec: str) -> list[str]:
        return [r.cells.get("Поле", "").strip("` ") for r in self.rows(sec)]


def _table(text: str, first: int, cols: tuple) -> tuple[list[Row], list[tuple[int, str]]]:
    """Строки markdown-таблицы раздела по заголовку; (строки, ошибки разбора)."""
    rows, errs, head = [], [], None
    for n, raw in enumerate(text.split("\n"), start=first):
        ln = raw.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if head is None:
            head = cells
            if tuple(head) != cols:
                errs.append((n, f"колонки таблицы — | {' | '.join(cols)} |, а не | {' | '.join(head)} |"))
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        rows.append(Row(n, dict(zip(head, cells + [""] * (len(head) - len(cells))))))
    return rows, errs


def read(pr: bl.Project, f: Path) -> Contract | None:
    rel = f.relative_to(pr.root).as_posix()
    text = f.read_text(encoding="utf-8")
    fm, off = bl.yaml_front(text)
    if fm is None:
        pr.err(rel, 1, "CT001", "контракт начинается с frontmatter --- id, title, boundary, caller, callee, op, cards ---")
        return None
    c = Contract(str(fm.get("id", "")).strip(), f, rel, fm, off)
    if STUB_RE.search(text):   # каркас не дописан — разбирать разделы рано, check скажет CT011
        return c
    lines = text.split("\n")
    cur, start, buf = None, 0, []
    for n, ln in enumerate(lines[off:] + ["## "], start=off + 1):
        m = re.match(r"^##\s+(.*?)\s*$", ln)
        if m:
            if cur:
                c.sections[cur] = (start, "\n".join(buf))
            cur, start, buf = (m.group(1) if m.group(1) in SECTIONS else None), n, []
            if m.group(1) and m.group(1) not in SECTIONS:
                pr.err(rel, n, "CT004", f"{c.id}: раздела «{m.group(1)}» нет в шаблоне — разделы: {', '.join(SECTIONS)}")
        elif cur:
            buf.append(ln)
    for sec, cols in COLUMNS.items():
        if sec in c.sections:
            first, body = c.sections[sec]
            c.tables[sec], errs = _table(body, first + 1, cols)
            for n, msg in errs:
                pr.err(rel, n, "CT004", f"{c.id}: «{sec}»: {msg}")
    if "Пример ответа" in c.sections:
        first, body = c.sections["Пример ответа"]
        m = re.search(r"```json\s*\n(.*?)\n```", body, re.S)
        try:
            c.example = json.loads(m.group(1)) if m else None
        except ValueError as e:
            pr.err(rel, first, "CT004", f"{c.id}: «Пример ответа» — не JSON: {e}")
        if m is None:
            pr.err(rel, first, "CT004", f"{c.id}: «Пример ответа» — блок ```json … ```")
    if "Sequence" in c.sections:
        first, body = c.sections["Sequence"]
        for n, raw in enumerate(body.split("\n"), start=first + 1):
            ln = raw.strip()
            if not ln:
                continue
            m = SEQ_RE.match(re.sub(r"^[-*]\s*", "", ln))
            if not m:
                pr.err(rel, n, "CT007", f"{c.id}: строка Sequence — «- Кто -> Кому: вызов» или «- Кто --> Кому: ответ», а не «{ln[:50]}»")
                continue
            c.sequence.append(Call(n, m.group(1).strip(), m.group(2), m.group(3).strip(), m.group(4).strip()))
    return c


def parse(pr: bl.Project) -> list[Contract]:
    d = pr.root / DIR
    out: list[Contract] = []
    if not d.is_dir():
        return out
    seen: dict[str, str] = {}
    for f in sorted(d.glob("*.md"), key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", p.name)]):
        c = read(pr, f)
        if c is None:
            continue
        if not ID_RE.match(c.id):
            pr.err(c.rel, 2, "CT001", f"id контракта — C-1, C-2 …, а не «{c.id}»")
            continue
        if f.stem != c.id:
            pr.err(c.rel, 2, "CT001", f"{c.id}: файл называется {c.id}.md, а не {f.name}")
        if c.id in seen:
            pr.err(c.rel, 2, "CT001", f"{c.id}: повтор ID — уже в {seen[c.id]}")
            continue
        seen[c.id] = c.rel
        out.append(c)
    return out


# --- проверки ---------------------------------------------------------------------------------------

def _has(obj, path: str) -> bool:
    for k in path.split("."):
        if isinstance(obj, list):
            obj = obj[0] if obj else {}
        if not isinstance(obj, dict) or k not in obj:
            return False
        obj = obj[k]
    return True


def _value(obj, path: str):
    for k in path.split("."):
        if isinstance(obj, list):
            obj = obj[0] if obj else {}
        obj = obj.get(k) if isinstance(obj, dict) else None
    return obj


def _tokens(text: str) -> set[str]:
    """Поля в ячейке цепочки: `ticket{event, used}` → ticket, ticket.event, ticket.used; русские слова — пояснение."""
    out: set[str] = set()
    for m in GROUP_RE.finditer(text):
        out.add(m.group(1))
        out |= {f"{m.group(1)}.{t}" for t in TOKEN_RE.findall(m.group(2))}
    out |= set(TOKEN_RE.findall(GROUP_RE.sub("", text.replace("`", ""))))
    return out


def _known(tok: str, avail: set[str]) -> bool:
    parts = tok.split(".")
    return any(".".join(parts[:i]) in avail for i in range(1, len(parts) + 1))


def _source(pr: bl.Project, c: Contract, r: Row, col: str, reqs: dict | None) -> None:
    src = r.cells.get(col, "")
    ids = bb.REQ_RE.findall(src)
    if not ids and not FAMILY_RE.search(src) and bb.MARKER not in src and "PO" not in src:
        pr.err(c.rel, r.line, "CT005", f"{c.id}: у поля нет источника — ID требования (ФТ-4) или [УТОЧНИТЬ у …]")
    for rid in ids if reqs is not None else ():
        if rid not in reqs:
            pr.err(c.rel, r.line, "CT006", f"{c.id}: {rid} нет в БФТ")


def check(pr: bl.Project, contracts: list[Contract], reqs: dict | None = None) -> None:
    card_ids = {x.id for x in pr.cards}
    systems = {t.name for t in pr.teams}
    for c in contracts:
        systems |= {c.get("caller"), c.get("callee")}
        systems |= {r.cells.get("Кто", "") for r in c.rows("Цепочка")}
    systems.discard("")
    for c in contracts:
        stubs = STUB_RE.findall(c.path.read_text(encoding="utf-8"))
        if stubs:   # каркас не дописан: остальные проверки — после того, как места {{…}} заполнены
            pr.err(c.rel, 1, "CT011", f"{c.id}: мест {{{{…}}}} не заполнено — {len(stubs)}; первое: {stubs[0][:80]}")
            continue
        b = c.boundary
        for key in ("title", "boundary", "caller", "callee", "cards"):
            if not c.get(key):
                pr.err(c.rel, 1, "CT002", f"{c.id}: в шапке нет «{key}:»")
        if b and b not in BOUNDARIES:
            pr.err(c.rel, 1, "CT002", f"{c.id}: boundary — {' | '.join(BOUNDARIES)}, а не «{b}»")
        op = c.get("op")
        m = OP_RE.match(op)
        if b != "service-db" and not m:
            pr.err(c.rel, 1, "CT002", f"{c.id}: op — «МЕТОД /путь» ({', '.join(METHODS)}), а не «{op or '—'}»")
        for cid in c.cards:
            if cid not in card_ids:
                pr.err(c.rel, 1, "CT003", f"{c.id}: карточки {cid} нет на карте — cards: ID карточек «Как это работает»")

        # поля стыка
        need = ("Данные",) if b == "service-db" else ("Запрос", "Ответ", "Пример ответа", "Sequence")
        for sec in need:
            if sec not in c.sections:
                pr.err(c.rel, 1, "CT004", f"{c.id}: нет раздела «## {sec}»")
        if b != "service-db" and "Ответ" in c.sections and not c.rows("Ответ"):
            pr.err(c.rel, c.sections["Ответ"][0], "CT004", f"{c.id}: «Ответ» без полей — что получает {c.get('caller')}?")
        if b == "external" and not c.rows("Ошибки"):
            pr.err(c.rel, c.sections.get("Ошибки", (1,))[0], "CT004", f"{c.id}: внешний стык без ошибок — хотя бы одна строка «Ошибки»")
        elif b in ("frontend-backend", "service-service") and not c.rows("Ошибки"):
            pr.warn(c.rel, c.sections.get("Ошибки", (1,))[0], "CT022", f"{c.id}: нет ни одной ошибки — что видит {c.get('caller')}, если {c.get('callee')} отказал?")
        for sec in ("Запрос", "Ответ"):
            for r in c.rows(sec):
                name = r.cells.get("Поле", "").strip("` ")
                if not FIELD_RE.match(name):
                    pr.err(c.rel, r.line, "CT004", f"{c.id}: имя поля — латиницей без пробелов (ticket_id, promo.discount), а не «{name}»")
                _source(pr, c, r, "Источник", reqs)
        for r in c.rows("Запрос"):
            if r.cells.get("Где") not in WHERE:
                pr.err(c.rel, r.line, "CT004", f"{c.id}: «Где» — {' | '.join(WHERE)}, а не «{r.cells.get('Где')}»")
            if r.cells.get("Обяз.") not in ("да", "нет"):
                pr.err(c.rel, r.line, "CT004", f"{c.id}: «Обяз.» — да | нет")
        if m:
            path_req = {r.cells.get("Поле", "").strip("` ") for r in c.rows("Запрос") if r.cells.get("Где") == "path"}
            for p in re.findall(r"\{(\w+)\}", m.group(2)):
                if p not in path_req:
                    pr.err(c.rel, 1, "CT010", f"{c.id}: {{{p}}} в пути op — строкой «Запроса» с «Где: path»")
        if c.example is not None:
            line = c.sections["Пример ответа"][0]
            types = {r.cells.get("Поле", "").strip("` "): r.cells.get("Тип", "").strip() for r in c.rows("Ответ")}
            for name in c.fields("Ответ"):
                if FIELD_RE.match(name) and not _has(c.example, name):
                    pr.err(c.rel, line, "CT004", f"{c.id}: поля «{name}» из «Ответа» нет в примере")
                    continue
                v = _value(c.example, name) if FIELD_RE.match(name) else None
                want = TYPES.get(types.get(name, ""))
                if want and v is not None and (not isinstance(v, want) or (want is not bool and isinstance(v, bool))):
                    pr.err(c.rel, line, "CT012", f"{c.id}: «{name}» — {types[name]}, а в примере {json.dumps(v, ensure_ascii=False)[:40]}")
                if isinstance(v, str) and (bb.REQ_RE.search(v) or bb.MARKER in v or len(v.split()) > 6):
                    pr.err(c.rel, line, "CT012", f"{c.id}: «{name}» в примере — пояснение, а не значение: «{v[:50]}»; пример — то, что вернёт система: \"accepted\", 10, \"2026-03-01\"")
        for r in c.rows("Ошибки"):
            if not re.fullmatch(r"[45]\d\d", r.cells.get("Статус", "")) or not re.fullmatch(r"[A-Z][A-Z0-9_]+", r.cells.get("Код", "").strip("` ")):
                pr.err(c.rel, r.line, "CT004", f"{c.id}: ошибка — статус 4xx/5xx и код ЗАГЛАВНЫМИ (TICKET_NOT_FOUND)")

        # Sequence: кто с кем говорит, каждый вызов получает ответ
        seq = c.sequence
        if seq and (seq[0].src, seq[0].dst, seq[0].arrow) != (c.get("caller"), c.get("callee"), "->"):
            pr.err(c.rel, seq[0].line, "CT007", f"{c.id}: Sequence начинается вызовом «{c.get('caller')} -> {c.get('callee')}»")
        for i, s in enumerate(seq):
            for who in (s.src, s.dst):
                if who not in systems:
                    pr.err(c.rel, s.line, "CT007", f"{c.id}: участника «{who}» нет ни в «Командах» карты, ни в caller/callee/«Кто» контрактов")
            if s.arrow == "->" and not any(t.arrow == "-->" and (t.src, t.dst) == (s.dst, s.src) for t in seq[i + 1:]):
                pr.err(c.rel, s.line, "CT007", f"{c.id}: вызов «{s.src} -> {s.dst}» без ответа «{s.dst} --> {s.src}: …»")
        parts = {x for s in seq for x in (s.src, s.dst)}
        if len(parts) > 2 and "Цепочка" not in c.sections:
            pr.warn(c.rel, c.sections["Sequence"][0], "CT021", f"{c.id}: за {c.get('callee')} стоят ещё {len(parts) - 2} участника — распиши «## Цепочка»: как данные превращаются в ответ")

        if "Цепочка" in c.sections and not c.rows("Цепочка"):
            pr.err(c.rel, c.sections["Цепочка"][0], "CT004", f"{c.id}: «Цепочка» без шагов — нет участников за {c.get('callee')}: удали раздел целиком")
        # Цепочка: каждый вход откуда-то пришёл, ответ собран из выходов
        avail = set(c.fields("Запрос"))
        for r in c.rows("Цепочка"):
            if r.cells.get("Кто") and seq and r.cells["Кто"] not in parts:
                pr.err(c.rel, r.line, "CT008", f"{c.id}: «{r.cells['Кто']}» в цепочке, но не в Sequence")
            for tok in sorted(_tokens(r.cells.get("Вход", ""))):
                if not _known(tok, avail):
                    pr.err(c.rel, r.line, "CT008", f"{c.id}: шаг {r.cells.get('Шаг')}: вход «{tok}» не пришёл ни из «Запроса», ни из выхода прошлого шага")
            outs = _tokens(r.cells.get("Выход", ""))
            if not outs:
                pr.err(c.rel, r.line, "CT008", f"{c.id}: шаг {r.cells.get('Шаг')}: «Выход» — поля, которые дальше идут в работу")
            avail |= outs
        if c.rows("Цепочка"):
            for name in c.fields("Ответ"):
                if FIELD_RE.match(name) and not _known(name, avail):
                    pr.err(c.rel, c.sections["Цепочка"][0], "CT008", f"{c.id}: поле ответа «{name}» не выходит ни из одного шага цепочки")

        # Данные: что нужно из хранилища, без устройства хранилища
        for r in c.rows("Данные"):
            _source(pr, c, r, "Источник", reqs)
        for sec in ("Данные", "Цепочка"):
            if sec in c.sections:
                first, body = c.sections[sec]
                for n, ln in enumerate(body.split("\n"), start=first + 1):
                    hit = DDL_RE.search(ln)
                    if hit:
                        pr.err(c.rel, n, "CT009", f"{c.id}: «{hit.group(0)}» — устройство хранилища; в контракте — только какие данные нужны")

    covered = [set(c.cards) for c in contracts]
    for a, b, what in seams(pr):
        if not any({a, b} <= x for x in covered):
            card = pr.task(b)
            pr.warn(card.rel if card else "", 1, "CT020", f"{a} → {b} «{what}»: стык без контракта — "
                    f"./blueprint.py contracts skeleton заведёт его, или добавь {a} и {b} в cards: одного контракта")


def seams(pr: bl.Project) -> list[tuple[str, str, str]]:
    """Стыки карты — связи карточек, по которым ходят данные между системами:
    экран (Technology) ↔ то, что за кадром (Backstage), даже если обе у одной команды;
    Backstage ↔ карточка другой команды; любая связь с внешней системой.
    Support (макеты, правила, каналы) передаёт договорённости, а не данные — не стык."""
    by_id = {x.id: x for x in pr.cards}
    ext = {t.id for t in pr.teams if re.search(r"внешн|^ext$", f"{t.id} {t.name}", re.I)}
    out = []
    for a, b, what in pr.links():
        ca, cb = by_id[a], by_id[b]
        layers = {ca.layer, cb.layer}
        if "support" in layers:
            continue
        screen = layers == {"technology", "backstage"}
        cross = "backstage" in layers and (ca.team != cb.team or ca.team == "?")
        if screen or cross or {ca.team, cb.team} & ext:
            out.append((a, b, what))
    return out


def _team_name(pr: bl.Project, tid: str) -> str:
    return next((t.name for t in pr.teams if t.id == tid), "")


def skeleton(pr: bl.Project, contracts: list[Contract]) -> list[tuple[str, str]]:
    """Каркас контрактов: по файлу на стык карты без контракта. Шапка, карточки и требования — из карты;
    поля, пример, ошибки, цепочка — места {{…}} с подсказкой, откуда брать. Возвращает [(путь, текст)]."""
    covered = [set(c.cards) for c in contracts]
    n = max([int(c.id[2:]) for c in contracts] + [0])
    pairs: dict[frozenset, list] = {}
    for a, b, what in seams(pr):
        if not any({a, b} <= x for x in covered):
            pairs.setdefault(frozenset((a, b)), []).append((a, b, what))
    out = []
    for links in pairs.values():
        a, b, _ = links[0]
        ca, cb = pr.task(a), pr.task(b)
        n += 1
        cid = f"C-{n}"
        caller, callee = _team_name(pr, ca.team), _team_name(pr, cb.team)
        ext = any(re.search(r"внешн|ext", x, re.I) for x in (caller, callee, ca.team, cb.team))
        reqs = sorted({r for c in (ca, cb) for r in bb.REQ_RE.findall(c.desc)}, key=lambda r: (r.split("-")[0], r))
        what = "; ".join(f"{x} → {y}: {w}" for x, y, w in links)
        lanes = sorted({ln for c in (ca, cb) for ln in bl.lanes_of(c.proc)})
        src = f"ID требования из {', '.join(reqs)} или [УТОЧНИТЬ у …]" if reqs else "ID требования или [УТОЧНИТЬ у …]"
        text = f"""---
id: {cid}
title: {{{{что происходит на стыке фразой для человека — по связи {what}}}}}
boundary: {'external' if ext else '{{frontend-backend — экран получает данные · service-service — две наши системы · external — внешняя сторона}}'}
caller: {{{{кто вызывает — {caller or ca.team} или система из «Процесса»: {', '.join(lanes)}}}}}
callee: {{{{кто отвечает — {callee or cb.team} или система из «Процесса»: {', '.join(lanes)}}}}}
op: {{{{МЕТОД /v1/<сущность>[/{{id}}][/<действие>] — GET прочитать, POST создать или выполнить, PATCH изменить}}}}
cards: {a}, {b}
---

## Запрос

| Поле | Тип | Обяз. | Где | Источник |
| --- | --- | --- | --- | --- |
| {{{{поле латиницей: что уходит от caller — из «Выхода» {a} и «Входа» {b}}}}} | {{{{string · integer · number · boolean · array · object}}}} | {{{{да или нет}}}} | {{{{path · query · body}}}} | {{{{{src}}}}} |

## Ответ

| Поле | Тип | Источник |
| --- | --- | --- |
| {{{{поле латиницей: что caller получает обратно и показывает или передаёт дальше}}}} | {{{{тип}}}} | {{{{{src}}}}} |

## Пример ответа

```json
{{{{JSON с каждым полем «Ответа» и значениями из БФТ}}}}
```

## Ошибки

| Статус | Код | Когда |
| --- | --- | --- |
| {{{{4xx}}}} | {{{{КОД_ЗАГЛАВНЫМИ}}}} | {{{{когда — по развилке «нет →» в «Процессе» {a} или {b}; нет развилки — [УТОЧНИТЬ у …]}}}} |

## Sequence

- {{{{caller}}}} -> {{{{callee}}}}: {{{{вызов(поля запроса)}}}}
- {{{{callee}}}} --> {{{{caller}}}}: {{{{поля ответа}}}}

## Цепочка

| Шаг | Кто | Вход | Что делает | Выход |
| --- | --- | --- | --- | --- |
| 1 | {{{{callee или система за ним}}}} | {{{{поля запроса}}}} | {{{{шаг «Процесса» {b}}}}} | {{{{поля, которые дальше идут в работу}}}} |
"""
        out.append((f"{DIR}/{cid}.md", text))
    return out


HINTS = {
    "CT001": "контракт — файл contracts/C-N.md, frontmatter id: C-N совпадает с именем файла; шаблон — .blueprint/templates/contract.md",
    "CT002": "шапка: title, boundary (external | frontend-backend | service-service | service-db), caller, callee, op «POST /v1/…», cards",
    "CT003": "cards: — ID карточек «Как это работает» (BP-16.1), которые этот стык обслуживает",
    "CT004": "разделы и таблицы — как в шаблоне; поле латиницей; пример ответа — JSON со всеми полями «Ответа»; ошибка — 409 | ALREADY_USED | когда",
    "CT005": "у каждого поля «Источник» — ID требования из БФТ (ФТ-4) или [УТОЧНИТЬ у …]: поле без требования — выдумка",
    "CT006": "ID требования копируй из БФТ, не набирай (./blueprint.py reqs — список)",
    "CT007": "Sequence: «- caller -> callee: вызов» первой строкой; на каждый «->» — ответ «-->»; участники — команды карты или caller/callee контрактов",
    "CT008": "Цепочка: вход шага — поля «Запроса» или выхода прошлого шага; поля «Ответа» собираются из выходов",
    "CT009": "в «Данных» — хранилище и список нужных полей; таблицы, ключи, индексы, SQL — работа СА",
    "CT010": "параметр пути {id} — строкой «Запроса»: | id | string | да | path | ФТ-… |",
    "CT011": "допиши места {{…}} каркаса: каждая подсказка говорит, откуда взять значение; «Цепочка» не нужна — удали раздел, «Данные» нужны — добавь по шаблону",
    "CT012": "пример ответа — значения, как их вернёт система, с типом из «Ответа»: 10, \"valid\", true, \"2026-03-01\"; пояснения и ID требований — в «Источнике», не в примере",
    "CT020": "стык на карте (экран ↔ Backstage, Backstage ↔ другая команда, внешняя система) — контракт, в cards: которого обе карточки связи; ./blueprint.py contracts skeleton заведёт его",
    "CT021": "за вызываемой системой есть ещё участники — «## Цепочка»: шаг, кто, вход, что делает, выход",
    "CT022": "добавь в «Ошибки» хотя бы отказ: что получает вызывающая сторона",
}

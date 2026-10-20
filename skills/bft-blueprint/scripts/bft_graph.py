"""bft_graph — граф требований БФТ: атомы, колонки, роли, связи, семейства ID и матрицы.

Модель не должна искать в БФТ, что в нём есть: граф перечисляет всё, а скелет карты
(`bft-skeleton.py`) и проверки (`BL036`–`BL038`) работают по нему.

- **Атом** — строка таблицы требований (БТ, ПТ, ИТ, ФТ, НФТ): все колонки как есть, «Критерий приёмки»,
  «Связанные требования», роль (подпись «Роль A. …» над таблицей или таблица ролей).
- **Семейство** — ID вида `P7`, `G2`, `I1` (латинская буква и номер): параметры, разрывы, инварианты.
  Определено таблицей с ID в первой колонке, строкой матрицы или диапазоном `P1–P8` в тексте.
- **Матрица** — таблица отметок (●, ○, –): строка — параметр, колонка — вариант (схема, тариф, канал).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import bft_blueprint as bb

MEMBER_RE = re.compile(r"(?<![A-Za-zА-Яа-яЁё\d-])([A-Z])(\d{1,2})(?![\d.,]?\d)(?![A-Za-zА-Яа-яЁё-])")
RANGE_RE = re.compile(r"(?<![A-Za-z])([A-Z])(\d{1,2})\s*(?:–|—|-|…|\.\.)\s*\1?(\d{1,2})(?!\d)")
REQ_RANGE_RE = re.compile(r"((?:НФТ|БТ|ПТ|ИТ|ФТ)-[A-Za-zА-Яа-яЁё]?)(\d+)\s*(?:–|—|…|\.\.)\s*(?:\1)?(\d+)")
ROLE_RE = re.compile(r"Роль\s+([A-ZА-ЯЁ])\.\s*([^*—:|]+)")
MARKS = {"●", "○", "–", "-", "—", "✓", "✗", "+", "да", "нет", "x", "х"}


@dataclass
class Atom:
    id: str
    kind: str
    name: str
    cols: dict[str, str]
    ac: str = ""
    story: str = ""
    related: list[str] = field(default_factory=list)
    role: str = ""
    families: list[str] = field(default_factory=list)
    caption: str = ""


@dataclass
class Member:
    id: str
    label: str
    source: str            # таблица, матрица или диапазон
    values: dict[str, str] = field(default_factory=dict)
    caption: str = ""


@dataclass
class Matrix:
    caption: str
    columns: list[str]
    rows: list[tuple[str, list[str], dict[str, str]]]   # подпись, ID семейства, {вариант: отметка}
    applies: list[str] = field(default_factory=list)      # ID требований из подписи


@dataclass
class Graph:
    path: Path
    atoms: dict[str, Atom] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)        # буква группы ПТ → роль
    members: dict[str, Member] = field(default_factory=dict)
    matrices: list[Matrix] = field(default_factory=list)
    external: dict[str, list[str]] = field(default_factory=dict)  # «G1–G17» в тексте, а списка в БФТ нет

    def families(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for mid in self.members:
            out.setdefault(mid[0], []).append(mid)
        return {k: sorted(v, key=lambda x: int(x[1:])) for k, v in out.items()}

    def by_kind(self, kind: str) -> list[Atom]:
        return [a for a in self.atoms.values() if a.kind == kind]

    def neighbours(self, rid: str) -> list[str]:
        """Связанные требования в обе стороны: «Связанные» атома и атомы, которые ссылаются на него."""
        a = self.atoms.get(rid)
        out = list(a.related) if a else []
        out += [x.id for x in self.atoms.values() if rid in x.related]
        return [x for x in dict.fromkeys(out) if x in self.atoms and x != rid]


def _col(header: list[str], *keys: str) -> int | None:
    for i, h in enumerate(header):
        low = h.lower().replace("ё", "е")
        if any(k in low for k in keys):
            return i
    return None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("**", "")).strip()


def expand_req_ranges(text: str) -> str:
    """«ПТ-А1…ПТ-А3» → «ПТ-А1, ПТ-А2, ПТ-А3»: диапазон в таблице ролей."""
    def one(m: re.Match) -> str:
        pre, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        return ", ".join(f"{pre}{i}" for i in range(a, b + 1)) if 0 < b - a < 50 else m.group(0)
    return REQ_RANGE_RE.sub(one, text)


def _captions(lines: list[str]) -> dict[int, str]:
    """Номер строки начала таблицы → подпись над ней (ближайший абзац или заголовок)."""
    out, last = {}, ""
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("|"):
            if i == 0 or not lines[i - 1].strip().startswith("|"):
                out[i] = last
            continue
        if s:
            last = s.lstrip("#").strip()
    return out


def _is_matrix(header: list[str], rows: list[list[str]]) -> bool:
    cells = [c.strip().lower() for r in rows for c in r[1:] if c.strip()]
    return len(header) >= 3 and len(cells) >= 4 and sum(c in MARKS or c.split(" ")[0] in MARKS for c in cells) >= 0.6 * len(cells)


def _member_label(text: str, mid: str) -> str:
    m = re.search(rf"(?<![A-Za-z]){mid}(?!\d)\s*([^;|]*)", text)
    return _clean(m.group(1)) if m else ""


def build(path: Path) -> Graph:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    g = Graph(path)
    caps = _captions(lines)
    # таблицы с позицией: bb.tables не отдаёт начало, ищем его по первой строке данных
    starts = sorted(caps)
    for header, rows in bb.tables(lines):
        first = rows[0][0] - 1 if rows else 0
        start = max([s for s in starts if s <= first - 1] or [0])
        cap = caps.get(start, "")
        body = [cells for _, cells in rows if any(c.strip() for c in cells)]
        if not header:
            continue
        role_m = ROLE_RE.search(cap)
        # таблица ролей: «A. Роль | ПТ-А1…ПТ-А3 | экраны»
        if header[0].strip().lower().startswith("роль"):
            for cells in body:
                m = re.match(r"^\s*([A-ZА-ЯЁ])\.\s*(.+)$", _clean(cells[0]))
                if m:
                    g.roles[bb.req_key(m.group(1))] = m.group(2).strip()
            continue
        if _is_matrix(header, body):
            mx = Matrix(_clean(cap), [_clean(h) for h in header[1:]], [], bb.REQ_RE.findall(cap))
            for cells in body:
                label = _clean(cells[0])
                vals = {mx.columns[i]: _clean(c) for i, c in enumerate(cells[1:len(mx.columns) + 1])}
                if not any(vals.values()):
                    continue   # строка-раздел матрицы
                ids = [f"{a}{b}" for a, b in MEMBER_RE.findall(label)]
                mx.rows.append((label, ids, vals))
                for mid in ids:
                    g.members.setdefault(mid, Member(mid, _member_label(label, mid) or label, "матрица", vals, mx.caption))
            g.matrices.append(mx)
            continue
        name_c = _col(header, "наименование")
        ac_c = _col(header, "критерий прием")
        rel_c = _col(header, "связанн")
        story_c = _col(header, "story")
        for cells in body:
            first_cell = cells[0].strip()
            if re.fullmatch(bb.REQ_RE, first_cell):
                if first_cell in g.atoms:
                    continue
                get = lambda c: _clean(cells[c]) if c is not None and c < len(cells) else ""  # noqa: E731
                row = " ".join(cells[1:])
                a = Atom(first_cell, first_cell.split("-")[0], get(name_c),
                         {_clean(h): _clean(c) for h, c in zip(header[1:], cells[1:]) if _clean(c) not in bb.EMPTY},
                         ac=get(ac_c), story=get(story_c),
                         related=[x for x in bb.REQ_RE.findall(get(rel_c)) if x != first_cell], caption=_clean(cap))
                if role_m:
                    g.roles.setdefault(bb.req_key(role_m.group(1)), role_m.group(2).strip())
                    a.role = role_m.group(2).strip()
                spans = [f"{x}{i}" for x, lo, hi in RANGE_RE.findall(row) if 0 < int(hi) - int(lo) <= 60 for i in range(int(lo), int(hi) + 1)]
                a.families = list(dict.fromkeys([f"{x}{y}" for x, y in MEMBER_RE.findall(row)] + spans))
                g.atoms[a.id] = a
            elif re.fullmatch(r"[A-Z]\d{1,2}", first_cell) and len(cells) > 1:
                g.members.setdefault(first_cell, Member(first_cell, _clean(cells[1]), "таблица",
                                                        {_clean(h): _clean(c) for h, c in zip(header[2:], cells[2:]) if _clean(c)},
                                                        _clean(cap)))
    # диапазоны «P1–P8»: семейство объявлено, даже если строк нет
    for m in RANGE_RE.finditer(text):
        letter, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        if 0 < b - a <= 60:
            for i in range(a, b + 1):
                g.members.setdefault(f"{letter}{i}", Member(f"{letter}{i}", "", "диапазон"))
    # семейство — только буква, у которой есть определения (не случайный «A1» в тексте)
    defined = {mid[0] for mid, x in g.members.items() if x.source != "диапазон"}
    for k in sorted(g.members, key=lambda x: (x[0], int(x[1:]))):
        if k[0] not in defined:
            g.external.setdefault(k[0], []).append(k)
    g.members = {k: v for k, v in g.members.items() if k[0] in defined}
    for a in g.atoms.values():
        a.families = [x for x in a.families if x in g.members]
        if a.kind == "ПТ" and not a.role:
            grp = re.match(r"ПТ-([A-Za-zА-Яа-яЁё])\d", a.id)
            if grp:
                a.role = g.roles.get(bb.req_key(grp.group(1)), "")
        if not a.role and a.story:
            m = re.search(r"\bя\s*\(([^)]+)\)", a.story)
            if m:
                a.role = m.group(1).strip()
    return g


def to_json(g: Graph) -> dict:
    return {
        "source": g.path.name,
        "atoms": [a.__dict__ for a in g.atoms.values()],
        "roles": g.roles,
        "families": {k: [g.members[m].__dict__ for m in v] for k, v in g.families().items()},
        "matrices": [{"caption": m.caption, "columns": m.columns, "applies": m.applies,
                      "rows": [{"label": r[0], "ids": r[1], "values": r[2]} for r in m.rows]} for m in g.matrices],
        "external": g.external,
    }

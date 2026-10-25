#!/usr/bin/env python3
"""bft-skeleton — каркас плана карты из графа требований БФТ: всё из документа уже на своём месте.

    python3 bft-skeleton.py <проект> [--source БФТ.md] [--force]
    В проекте: ./blueprint.py skeleton

Модель на большом БФТ теряет то, что не попало в её внимание: ролевые ПТ, параметры договора,
инварианты, критерии приёмки. Каркас раскладывает документ детерминированно, а модели остаётся текст:

- задача — на каждое ФТ; ИТ без ФТ — своя задача; ПТ — в задачу связанного ФТ или экрана;
- карточка backstage — правило ФТ: текст, параметры, связанные НФТ и ID семейств в «Управлении» дословно;
- карточка technology — экран ИТ или ПТ без экрана: UserStory от роли ПТ, JobStory — из Story БФТ;
- параметр матрицы — строка «Управления» с вариантами по колонкам; инвариант и разрыв — в карточку,
  чей текст ближе всего; открытый разрыв и внешний список (G1–G17 без строк) — вопрос;
- критерии приёмки требований — в «Критерии приемки» задачи дословно;
- этап — по «Источнику» шагов и экранов истории; команда — по «Зависимостям» БФТ;
- `[УТОЧНИТЬ у X]` из текста — строки «Вопросов».

Чего в БФТ нет, каркас не пишет: на этом месте `{{…}}` с подсказкой и цитатой источника. `apply` не примет
план, пока заполнено не всё (PL007), — заполняет рой (`./blueprint.py groom fill`) или ведущий агент.
Рядом — `plan/skeleton.md`: какой атом БФТ в какой блок лёг.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bft_backlog as bl  # noqa: E402
import bft_blueprint as bb  # noqa: E402
import bft_graph as bg  # noqa: E402
import bft_plan as bp  # noqa: E402

TRANSLIT = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
                          "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
                          "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
                          "э": "e", "ю": "yu", "я": "ya"})
STOP = {"команда", "система", "системы", "внешние", "внешняя", "отдел", "группа", "сервис", "департамент"}
UNSURE = re.compile(r"\[УТОЧНИТЬ(?:\s+у\s+([^\]—:]+?))?(?:\s*[—:][^\]]*)?\]")


def stem(w: str) -> str:
    return w.lower().replace("ё", "е")[:5]


def words(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[А-Яа-яЁёA-Za-z]{4,}", text)} - {stem(w) for w in STOP}


ENDING = re.compile(r"(?:иями|ями|ами|ого|его|ому|ему|ыми|ими|ией|ов|ев|ей|ам|ям|ах|ях|ой|ый|ий|ая|яя|ое|ее|ые|ие|ую|юю|ым|им|ом|ем|ия|ии|ию|ь|а|я|ы|и|у|ю|е|о)$")


def roots(text: str) -> set[str]:
    """Основы слов без окончаний: «слотов», «слота», «слоты» — одно «слот». Для подбора команды по «Зависимостям»."""
    out = set()
    for w in re.findall(r"[А-Яа-яЁёA-Za-z]{4,}", text.lower().replace("ё", "е")):
        if w in STOP:
            continue
        r = ENDING.sub("", w) if len(w) > 4 else w
        out.add(r[:6])
    return out


# короткие ID частых команд: агенты переименовывали «mobilnogo» и «integraciy» руками
SHORT = (("приложен", "app"), ("мобильн", "app"), ("платеж", "pay"), ("платёж", "pay"), ("интеграц", "int"), ("лояльн", "loy"),
         ("каталог", "cat"), ("продаж", "sales"), ("финанс", "fin"), ("бухгалт", "acc"), ("витрин", "vit"), ("сайт", "site"),
         ("дизайн", "des"), ("маркетинг", "mkt"), ("аналитик", "data"), ("разработ", "dev"), ("поддержк", "sup"), ("логистик", "log"),
         ("склад", "wh"), ("доставк", "dlv"), ("crm", "crm"), ("ext", "ext"))
ADJ = re.compile(r"(?:ого|его|ой|ей|ая|яя|ый|ий|ое|ее|ые|ие|ых|их)$")


def team_id(name: str, taken: set[str]) -> str:
    base = [w for w in re.findall(r"[А-Яа-яЁёA-Za-z]+", re.sub(r"\(.*?\)", "", name).lower()) if w not in STOP] or ["team"]
    short = next((sid for w in base for key, sid in SHORT if w.startswith(key)), None)
    noun = next((w for w in base if not ADJ.search(w)), base[0])
    tid = short or re.sub(r"[^a-z0-9]", "", noun.translate(TRANSLIT))[:8] or "team"
    k, out = 2, tid
    while out in taken:
        out, k = f"{tid}{k}", k + 1
    taken.add(out)
    return out


def jobstory(story: str) -> str:
    """«**Когда** X, **я хочу** Y, **чтобы** Z» → «Когда X, хочу Y, чтобы Z.»"""
    s = re.sub(r"\*\*", "", story)
    m = re.search(r"Когда\s+(.+?),?\s+[Яя]\s+хочу\s+(.+?),?\s+[Чч]тобы\s+(.+?)\.?$", s)
    if not m:
        return ""
    when = re.sub(r"^я\s*\([^)]*\)\s*", "я ", m.group(1).strip())
    return f"Когда {when}, хочу {m.group(2).strip()}, чтобы {m.group(3).strip()}."


def matrix_words(m, g) -> str:
    """Отметки матрицы словами из её легенды: «●» → «обязателен: агентская, комиссионная; не применяется: перепродажа»."""
    mx = next((x for x in g.matrices if any(m.id in r[1] for r in x.rows)), None)
    legend = dict(re.findall(r"([●○◐–\-✓✗×+])\s*—\s*([^,;:.()]+?)(?=\s*[,;:.)]|$)", (mx.caption if mx else "") + " " + m.caption))
    groups: dict[str, list[str]] = {}
    for k, v in m.values.items():
        groups.setdefault(legend.get(v.strip(), v.strip()).strip(), []).append(k.lower())
    return "; ".join(f"{mean}: {', '.join(ks)}" for mean, ks in groups.items())


def stub(hint: str) -> str:
    return "{{" + hint.replace("{", "(").replace("}", ")") + "}}"


class Skeleton:
    def __init__(self, g: bg.Graph, story, deps: list[list[str]], sure: bool = True):
        self.g, self.story, self.sure = g, story, sure
        self.tasks: list[dict] = []          # {id, anchor, atoms, cards: [{id, layer, atoms, rules, title}]}
        self.home: dict[str, str] = {}       # атом или ID семейства → блок
        self.teams: list[tuple[str, str, str]] = []
        taken: set[str] = set()
        for row in deps:
            # PO, СА, аналитик строят сервис, а не работают в нём (BL034): в «Команды» не идут
            if row and row[0].strip() and not BUILDER.match(re.sub(r"\s*\(.*\)\s*$", "", row[0].strip())):
                # внешняя система — `ext` (автопилот 4.1); вторая внешняя — ext2
                tid = team_id("ext", taken) if re.search(r"внешн", " ".join(row), re.I) else team_id(row[0], taken)
                self.teams.append((tid, row[0].strip(), " ".join(row[1:])))
        self.stage_of = self._stages()

    # --- этапы из истории ---------------------------------------------------------------------------
    def _stages(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if not self.story:
            return out
        order = [s.id for s in self.story.stages]
        scr_stage: dict[str, str] = {}
        for st in self.story.steps:
            if st.stage_from in order:
                for sid in st.screens:
                    scr_stage.setdefault(sid, st.stage_from)
                for rid in bb.REQ_RE.findall(st.source):
                    out.setdefault(rid, st.stage_from)
        for sc in self.story.screens:
            for rid in bb.REQ_RE.findall(sc.source):
                if sc.id in scr_stage:
                    out.setdefault(rid, scr_stage[sc.id])
        # соседи по графу: самый частый этап связанных требований; БТ — сквозные, этапа не задают
        for _ in range(3):
            for rid in self.g.atoms:
                if rid not in out:
                    near = [out[n] for n in self.g.neighbours(rid) if n in out and not n.startswith("БТ-")]
                    if near:
                        out[rid] = max(dict.fromkeys(sorted(near, key=order.index)), key=near.count)
        return out

    def first_stage(self) -> str:
        """Этап не нашёлся ни в истории, ни у соседей по графу: решает агент — первый этап по умолчанию ставил результат не туда."""
        ids = ", ".join(s.id for s in self.story.stages) if self.story and self.story.stages else "A, B…"
        return stub(f"этап истории, на котором результат виден человеку: {ids}")

    def stage(self, ids: list[str]) -> str:
        """Этап первого атома, у которого он известен: ids — по старшинству (якорь задачи первым)."""
        return next((self.stage_of[i] for i in ids if i in self.stage_of), self.first_stage())

    # --- раскладка атомов ---------------------------------------------------------------------------
    def layout(self) -> None:
        g = self.g
        fts = g.by_kind("ФТ")
        for a in fts:
            self.tasks.append({"anchor": a.id, "atoms": [a.id], "cards": [{"layer": "backstage", "atoms": [a.id], "rules": []}]})
        task_of = {t["anchor"]: t for t in self.tasks}

        def same_stage(rid: str, t: dict) -> bool:
            """Задача — один результат на одном этапе (автопилот 4.2): экран другого этапа — своя задача."""
            a, b = self.stage_of.get(rid), self.stage_of.get(t["anchor"])
            return not a or not b or a == b

        def attach_task(rid: str) -> dict | None:
            for n in g.atoms[rid].related + g.neighbours(rid):
                if n in task_of and same_stage(rid, task_of[n]):
                    return task_of[n]
            for n in g.neighbours(rid):          # через сосед-ПТ или ИТ
                for m in g.neighbours(n):
                    if m in task_of and same_stage(rid, task_of[m]):
                        return task_of[m]
            return None

        # экран ИТ — своя задача: результат команды, которая его делает (автопилот 4.2); правило за кадром —
        # задача ФТ рядом, связь между ними — «Вход»/«Выход» карточек. Экран под задачей правила агенты выносили руками
        for a in g.by_kind("ИТ"):
            t = {"anchor": a.id, "atoms": [a.id], "cards": [{"layer": "technology", "atoms": [a.id], "rules": []}]}
            self.tasks.append(t)
            task_of[a.id] = t
        screen_card = {c["atoms"][0]: c for t in self.tasks for c in t["cards"] if c["layer"] == "technology"}
        # ПТ: JobStory экрана, который его показывает; без экрана — своя карточка technology
        for a in g.by_kind("ПТ"):
            scr = next((screen_card[n] for n in g.neighbours(a.id) if n in screen_card), None)
            t = next((t for t in self.tasks if scr in t["cards"]), None) if scr else attach_task(a.id)
            if t is None:
                t = self.tasks[0] if self.tasks else None
            if t is None:
                continue
            t["atoms"].append(a.id)
            if scr:
                scr["atoms"].append(a.id)
            else:
                t["cards"].append({"layer": "technology", "atoms": [a.id], "rules": []})
        self._employee()
        # этап истории без задачи: шаги ссылаются на требование (НФТ-1 «изменения на сайте за сутки») — задача по нему,
        # иначе BL020 и агент дописывает её руками
        if self.story:
            busy = {self.stage([t["anchor"]] + t["atoms"]) for t in self.tasks}
            anchors = {t["anchor"] for t in self.tasks}
            for st in self.story.stages:
                if st.id in busy:
                    continue
                cand = [r for r, sid in self.stage_of.items() if sid == st.id and r in g.atoms and g.atoms[r].kind in ("ФТ", "НФТ", "ИТ")]
                cand.sort(key=lambda r: ("ФТ", "ИТ", "НФТ").index(g.atoms[r].kind))
                rid = next((r for r in cand if r not in anchors), None)
                if rid:
                    layer = "technology" if g.atoms[rid].kind == "ИТ" else "backstage"
                    self.tasks.append({"anchor": rid, "atoms": [rid], "cards": [{"layer": layer, "atoms": [rid], "rules": []}]})
                    task_of[rid] = self.tasks[-1]
                    anchors.add(rid)
        # НФТ: «Управление» карточек связанных требований; без связи — карточка support первой задачи
        for a in g.by_kind("НФТ"):
            cards = [c for t in self.tasks for c in t["cards"] if set(c["atoms"]) & set(g.neighbours(a.id) + a.related)]
            if not cards and self.tasks:
                self.tasks[0]["cards"].append({"layer": "support", "atoms": [], "rules": []})
                cards = [self.tasks[0]["cards"][-1]]
            for c in cards[:3]:
                c["rules"].append(a.id)
            for t in self.tasks:
                if any(c in t["cards"] for c in cards[:3]):
                    t["atoms"].append(a.id)
        # семейства: к карточке атома, который их называет; иначе — к ближайшей по тексту
        all_cards = [c for t in self.tasks for c in t["cards"]]
        text_of = {id(c): " ".join(self._atom_text(x) for x in c["atoms"]) for c in all_cards}
        df: dict[str, int] = {}   # в скольких карточках встречается слово: частое слово почти ничего не значит
        for c in all_cards:
            for w in words(text_of[id(c)]):
                df[w] = df.get(w, 0) + 1
        placed: set[str] = set()
        rule_card = {c["atoms"][0]: c for c in all_cards if c["layer"] == "backstage" and c["atoms"]}
        for mx in g.matrices:   # матрица — правила той ФТ, к которой она приложена
            home = next((rule_card[x] for x in mx.applies if x in rule_card), None)
            for _, ids, _ in mx.rows if home else []:
                for mid in ids:
                    if mid not in placed:
                        home["rules"].append(mid)
                        placed.add(mid)
        for c in [c for c in all_cards if c["layer"] == "backstage"] + all_cards:
            for x in c["atoms"]:
                for mid in g.atoms[x].families:
                    if mid not in placed and g.members[mid].source == "матрица":
                        c["rules"].append(mid)
                        placed.add(mid)
        for mid, m in g.members.items():
            if mid in placed:
                continue
            mx = next((x for x in g.matrices if any(mid in r[1] for r in x.rows)), None)
            pool = [c for c in all_cards if mx and set(c["atoms"]) & set(mx.applies)] or all_cards
            mw = words(m.label + " " + " ".join(m.values.values()))
            target = max(pool, key=lambda c: sum(1 / df[w] for w in mw & words(text_of[id(c)])))
            target["rules"].append(mid)
            placed.add(mid)

    def _employee(self) -> None:
        """Слой employee: экран или роль сотрудника, который действует на виду у клиента — на этапе, где у другого
        персонажа истории тоже есть шаг (официант сканирует билет гостя, мастер-приёмщик принимает машину)."""
        story = self.story
        if not story or len(story.personas) < 2:
            return
        order = [x.id for x in story.stages]
        idx = {sid: i for i, sid in enumerate(order)}

        def on_stage(pid: str, sid: str) -> bool:
            return any(st.persona == pid and st.stage_from in idx and idx[st.stage_from] <= idx[sid] <= idx.get(st.stage_to, idx[st.stage_from])
                       for st in story.steps)

        shown = {sc: st.persona for st in story.steps for sc in st.screens}
        for t in self.tasks:
            for c in t["cards"]:
                if c["layer"] != "technology":
                    continue
                stage = self.stage(c["atoms"] + [t["anchor"]] + t["atoms"])
                if stage not in idx:
                    continue
                who = {shown[s] for s in self.screens_of(c["atoms"]) if s in shown}
                if not who:   # нет экрана в истории — роль ПТ, совпавшая с именем персонажа
                    roles = " ".join(self.g.atoms[x].role for x in c["atoms"] if self.g.atoms[x].role)
                    who = {pz.id for pz in story.personas if roles and words(pz.name) & words(roles)}
                if len(who) == 1:
                    pid = next(iter(who))
                    me = next(pz for pz in story.personas if pz.id == pid)
                    if CUSTOMER.search(me.name):   # экран клиента — technology, даже если рядом работает сотрудник
                        continue
                    if on_stage(pid, stage) and any(pz.id != pid and CUSTOMER.search(pz.name) and on_stage(pz.id, stage) for pz in story.personas):
                        c["layer"] = "employee"

    def _atom_text(self, rid: str) -> str:
        a = self.g.atoms[rid]
        return a.name + " " + " ".join(a.cols.values())

    # --- текст плана --------------------------------------------------------------------------------
    def team_line(self, t: dict) -> str:
        if not self.teams or not self.sure:
            return stub("строка «команда: id» из «Команд» — кто делает, по «Зависимостям» БФТ; не ясно — «кандидаты: id1, id2»")
        # якорь задачи весит вдвое: задача — его результат, остальные атомы — контекст
        tw = roots(" ".join(self._atom_text(x) for x in t["atoms"]))
        aw = roots(self._atom_text(t["anchor"])) if t["anchor"] in self.g.atoms else set()
        inner = [x for x in self.teams if not re.search(r"внешн", x[1] + " " + x[2], re.I)] or self.teams  # внешняя система не исполнитель
        tw_of = {x[0]: roots(x[1] + " " + x[2]) for x in inner}
        df: dict[str, int] = {}
        for ws in tw_of.values():
            for w in ws:
                df[w] = df.get(w, 0) + 1

        nw = roots(self.g.atoms[t["anchor"]].name) if t["anchor"] in self.g.atoms else set()

        def score(x, pool: set) -> float:   # слово, которое есть в описании одной команды, говорит больше общего «банка»
            return sum((2 if w in aw else 1) / df[w] for w in tw_of[x[0]] & pool)

        # сначала название задачи — оно и есть результат («Акты и отчёты» — финансы), затем весь текст требований:
        # «из реестра продаж» в тексте — вход, а не владелец
        for pool in (nw, tw | aw):
            scored = sorted(inner, key=lambda x: -score(x, pool))
            best = [x for x in scored if score(x, pool) > 0]
            if len(best) == 1 or (len(best) > 1 and score(best[0], pool) >= 1.5 * score(best[1], pool)):
                return f"команда: {best[0][0]}"
        scored = sorted(inner, key=lambda x: -score(x, tw | aw))
        best = [x for x in scored if score(x, tw | aw) > 0]
        pick = (best or scored)[:2]
        return "кандидаты: " + ", ".join(x[0] for x in pick) if len(pick) > 1 else f"команда: {pick[0][0]}"

    def screens_of(self, ids: list[str]) -> list[str]:
        if not self.story:
            return []
        return [s.id for s in self.story.screens if set(bb.REQ_RE.findall(s.source)) & set(ids)]

    def rule_line(self, rid: str) -> str:
        g = self.g
        if rid in g.atoms:
            a = g.atoms[rid]
            body = a.cols.get("Описание") or a.cols.get("Функциональные требования") or a.name
            return f"{body} ({rid})"   # название требования — уже в «Требованиях БФТ» задачи; правило — его текст
        m = g.members[rid]
        if m.source == "матрица":
            return f"{rid} {m.label}: {matrix_words(m, g)}"
        extra = "; ".join(f"{k}: {v}" for k, v in m.values.items())
        return f"{rid} {m.label}" + (f" — {extra}" if extra else "")

    def card_block(self, cid: str, t: dict, c: dict) -> list[str]:
        g = self.g
        atoms = [g.atoms[x] for x in c["atoms"]]
        main = atoms[0] if atoms else None
        # название карточки — что происходит в работающем сервисе; копия названия задачи ничего не говорит (BL039)
        title = stub(f"что происходит, когда сервис работает: кто → что → результат, до 90 знаков; не повторяй задачу"
                     + (f"; из БФТ: {main.name}" if main else ""))
        pts = [a for a in atoms if a.kind == "ПТ"]
        role = next((a.role for a in pts if a.role), "")
        lines = [f"## {cid} · {title}", f"этап: {self.stage([a.id for a in atoms] + [t['anchor']] + t['atoms'])}", f"слой: {c['layer']}"]
        scr = self.screens_of([a.id for a in atoms])
        if scr and c["layer"] in ("technology", "employee"):
            lines.append(f"экраны: {', '.join(scr)}")
        src = "; ".join(f"{a.id}: {a.cols.get('Требование к пользовательскому интерфейсу') or a.cols.get('Функциональные требования') or a.name}" for a in atoms[:2])
        lines += ["", stub(f"Суть одной-двумя фразами: кто → что делает → какой результат. Из БФТ: {src}" if src else "Суть: что держит эта карточка"), ""]
        story_src = next((a for a in pts if a.story), None)
        lines += ["### UserStory",
                  f"Как {role or stub('кто пользуется результатом — человек, не команда')}, я хочу "
                  f"{stub('действие' + (' — из ' + story_src.id + ': ' + story_src.story if story_src else ''))}, чтобы {stub('ценность из БТ или ПТ')}.", ""]
        jobs = [f"- {j} ({a.id})" for a in pts if (j := jobstory(a.story))]
        lines += ["### JobStory"] + (jobs or [f"- Когда {stub('ситуация')}, хочу {stub('действие')}, чтобы {stub('результат')}."])
        if jobs:
            lines.append(f"- {stub('исключение или отказ из БФТ, если есть: Когда …, хочу …, чтобы …; нет — удали строку')}")
        rules = [self.rule_line(a.id) for a in atoms if a.kind in ("ФТ",)]
        rules += [f"{a.cols['Требование к пользовательскому интерфейсу']} ({a.id})" for a in atoms
                  if a.kind == "ИТ" and a.cols.get("Требование к пользовательскому интерфейсу")]
        rules += [f"{a.cols['Параметры, ограничения']}" for a in atoms if a.kind == "ФТ" and a.cols.get("Параметры, ограничения")]
        rules += [self.rule_line(x) for x in c["rules"]]
        rules += [f"{a.cols['Комментарий']} ({a.id})" for a in atoms if a.kind == "ПТ" and a.cols.get("Комментарий")]
        near = [x for x in dict.fromkeys(self.home.get(n) for a in atoms for n in self.g.neighbours(a.id)) if x and x != cid]
        hint = f" — по связям БФТ рядом: {', '.join(near[:4])}" if near else ""
        lines += ["", "### Параметры",
                  f"- **Вход:** {stub('что пришло и откуда: (BP-x.y) или внешняя система' + hint)}",
                  f"- **Управление:** " + ("; ".join(rules) if rules else stub("правило с ID требования; пороги — только из БФТ")),
                  f"- **Выход:** {stub('что меняется и кому уходит: (BP-x.y)' + hint)}",
                  f"- **Механизм:** {stub('кто исполняет: команда или система')}", "",
                  "### Процесс", f"- {stub('4–10 шагов «Участник: действие» от триггера до результата; развилка «- ? вопрос» с ветками «  - да → …» и «  - нет → …»')}", "",
                  "### HowToDemo", f"1. {stub('делаю → вижу: основной путь')}", f"2. {stub('делаю → вижу: ветка или отказ')}", ""]
        return lines

    def task_block(self, tid: str, t: dict) -> list[str]:
        g = self.g
        anchor = g.atoms.get(t["anchor"])
        ids = list(dict.fromkeys(t["atoms"]))
        title = anchor.name if anchor else "Экраны"
        bts = [b for b in g.by_kind("БТ") if set(b.related) & set(ids) or b.id in sum((g.atoms[x].related for x in ids), [])]
        why = "; ".join(f"{b.id}: {b.cols.get('Ценность разрабатываемого функционала для бизнес-заказчиков') or b.name}" for b in bts[:2])
        lines = [f"## {tid} · {title}", f"этап: {self.stage([t['anchor']] + ids)}", f"вид: {stub('создать | доработать | используем | уточнить')}", self.team_line(t)]
        scr = self.screens_of(ids)
        if scr:
            lines.append(f"экраны: {', '.join(scr)}")
        lines += ["", stub(f"Зачем одной фразой для бизнеса" + (f" — из {why}" if why else "")), "",
                  "Требования БФТ: " + ", ".join(x for x in ids + [b.id for b in bts] if x in g.atoms), "",
                  "### ASIS", stub("как сейчас — из «Изменение в UJM» и «Проблема»; не сказано — [УТОЧНИТЬ у PO]"), "",
                  "### GAP", stub("чего не хватает, по пунктам"), "",
                  "### TOBE", stub("как будет; каждое утверждение сделано в карточке задачи"), "",
                  "### HowToDemo", f"1. {stub('делаю → вижу')}", f"2. {stub('делаю → вижу: исключение')}", "",
                  "### Критерии приемки"]
        acs = [f"- {g.atoms[x].ac} ({x})" for x in ids if g.atoms[x].ac and g.atoms[x].kind != "БТ"]
        lines += acs or [f"- {stub('проверяемый пункт на каждое обещание TOBE')}"]
        lines.append("")
        return lines

    def render(self, title: str) -> tuple[str, list[str]]:
        out = [f"# План карты: {title}", "", "## Команды", "", "| ID | Команда |", "| --- | --- |"]
        out += [f"| {tid} | {name} |" for tid, name, _ in self.teams] or [f"| {stub('id латиницей')} | {stub('команда из «Зависимостей»')} |"]
        blocks: list[tuple[str, list[str]]] = []
        index = ["# Каркас: где лежит каждый атом БФТ", "", "| Атом | Блок |", "| --- | --- |"]
        order = [x.id for x in self.story.stages] if self.story else []
        rank = {id(t): (order.index(st) if (st := self.stage([t["anchor"]] + t["atoms"])) in order else len(order)) for t in self.tasks}
        self.tasks.sort(key=lambda t: rank[id(t)])   # карта читается слева направо: задачи по этапам, внутри этапа — порядок БФТ
        for n, t in enumerate(self.tasks, 1):       # сначала адреса: подсказки связей ссылаются на них
            for k, c in enumerate(t["cards"], 1):
                for x in c["atoms"] + c["rules"]:
                    self.home.setdefault(x, f"BP-{n}.{k}")
        for n, t in enumerate(self.tasks, 1):
            tid = f"BP-{n}"
            blocks.append((tid, self.task_block(tid, t)))
            for k, c in enumerate(t["cards"], 1):
                cid = f"{tid}.{k}"
                blocks.append((cid, self.card_block(cid, t, c)))
        for x in list(self.g.atoms) + list(self.g.members):
            index.append(f"| {x} | {self.home.get(x, '— только в «Требованиях БФТ» задачи' if x in self.g.atoms else '—')} |")
        # вопросы: [УТОЧНИТЬ] в тексте блоков, открытые разрывы, внешние списки семейств
        qs: list[tuple[str, str, str]] = []
        for bid, lines in blocks:
            for ln in lines:
                ln = bp.STUB.sub("", ln)
                for m in UNSURE.finditer(ln):
                    # контекст — та часть строки, где стоит [УТОЧНИТЬ], без разметки и ключа параметра
                    part = next((x for x in ln.split(";") if m.group(0) in x), ln)
                    part = re.sub(r"^\s*[-*]?\s*(\*\*)?[А-Яа-яЁё]+:\s*(\*\*)?\s*", "", part.replace("**", "") if part.lstrip("-* ").startswith("**") else part)
                    ctx = re.sub(r"\s+", " ", UNSURE.sub("…", part.replace("**", "")).strip("-* "))[:110]
                    qs.append(((m.group(1) or "PO").strip(), stub(f"вопрос одной фразой — по «{ctx}»"), bid))
        for mid, m in self.g.members.items():
            st = " ".join(m.values.values())
            if re.search(r"открыт", st, re.I) and mid in self.home:
                # [УТОЧНИТЬ] разрыва уже дал вопрос из текста блока — второй строкой тот же вопрос не нужен
                if any(where == self.home[mid] and re.search(rf"\b{re.escape(mid)}\b", q) for _, q, where in qs):
                    continue
                who = (UNSURE.search(st).group(1) if UNSURE.search(st) and UNSURE.search(st).group(1) else "PO").strip()
                qs.append((who, stub(f"вопрос по разрыву {mid}: «{m.label} — {st}»"), self.home[mid]))
        for fam, ids in self.g.external.items():
            qs.append(("PO", f"Где список {ids[0]}–{ids[-1]} и что из него должно попасть на карту?", "BP-1"))
        seen, rows = set(), []
        for who, q, where in qs:
            if (q, where) in seen:
                continue
            seen.add((q, where))
            rows.append(f"| В{len(rows) + 1} | {who} | {q} | {where} | вопрос | — |")
        out += ["", "## Вопросы", "", "| ID | Кому | Вопрос | Где | Тип | Ответ |", "| --- | --- | --- | --- | --- | --- |"] + rows + [""]
        for _, lines in blocks:
            out += lines
        return "\n".join(out).rstrip("\n") + "\n", index


# тот, кому служит сервис; сотрудник рядом с ним на том же этапе — слой employee
CUSTOMER = re.compile(r"клиент|гост[ьяи]|покупател|посетител|пользовател|абонент|пассажир|пациент|зрител|житель|студент|водител", re.I)
BUILDER = re.compile(r"^(?:PO|СА|PM|CPO|BA|SA|владелец продукта|продакт[\w-]*(?: менеджер)?|(?:системный |бизнес-)?аналитик\w*)(?:\s.*)?$", re.I)


def screen_stubs(d: Path, story, root: Path) -> list[str]:
    """Требования к экрану на каждый экран «Истории», которого ещё нет в plan/screens/: шаблон с ID, названием и источником."""
    tpl = next((p for p in (root / ".blueprint" / "templates" / "screen.md", HERE.parent / "templates" / "screen.md") if p.is_file()), None)
    if not story or not tpl:
        return []
    made = []
    for sc in story.screens:
        f = d / f"{sc.id}.md"
        if f.is_file():
            continue
        name = next((str(e[1]).lstrip("✓ ") for e in sc.elements if isinstance(e, (list, tuple)) and e and e[0] == "hdr"), "")
        src = ", ".join(bb.REQ_RE.findall(sc.source))
        text = tpl.read_text(encoding="utf-8").replace("{{ID}}", sc.id)
        text = text.replace("{{Название экрана — как в «Истории»}}", name or f"{{{{название экрана {sc.id} — {sc.contour}}}}}")
        if src:
            text = text.replace("{{ИТ-1}}", src).replace("{{ФТ-1}}", src)
        f.write_text(text, encoding="utf-8")
        made.append(sc.id)
    return made


def deps_rows(text: str) -> tuple[list[list[str]], bool]:
    """«Зависимости» БФТ: таблица «Команда / система | …» (команды надёжны) или список «- Кто: что» (только подсказка)."""
    for header, rows in bb.tables(text.splitlines()):
        if header and ("команда" in header[0].lower() or "систем" in header[0].lower()) and len(header) >= 2:
            return [c for _, c in rows if c and c[0].strip() and not c[0].strip().startswith("—")], True
    m = re.search(r"^##\s+Зависимости\s*$(.*?)(?=^##\s)", text, re.M | re.S)
    out = []
    for ln in (m.group(1) if m else "").splitlines():
        b = re.match(r"^\s*[-*•]\s+\**([^:*\[]{2,60}?)\**\s*:\s*(.+)$", ln)
        who = b.group(1).strip() if b else ""
        if b and not (bl.PROJECT_ROLE.match(who) and not who.lower().startswith("команда")):
            out.append([b.group(1).strip(), b.group(2).strip()])
    return out, False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", type=Path)
    ap.add_argument("--source", help="БФТ.md (по умолчанию — source_doc паспорта рядом с проектом)")
    ap.add_argument("--force", action="store_true", help="перезаписать существующий plan/map.md")
    a = ap.parse_args()
    root = a.project.resolve()
    if bl.find_backlog(root) is None:
        print(f"{root}: не проект Backlog.md", file=sys.stderr)
        return 2
    pf = root / bp.PLAN_DIR / "map.md"
    if pf.is_file() and not a.force:
        print(f"skeleton: {pf} уже есть — каркас не перезаписывает план (--force, если нужно с нуля)", file=sys.stderr)
        return 2
    pr = bl.parse(root)
    if pr.tasks:
        print(f"skeleton: в бэклоге уже {len(pr.tasks)} задач — каркас их не удаляет; apply покажет те, что не в плане", file=sys.stderr)
    import importlib.util
    spec = importlib.util.spec_from_file_location("bl_lint", HERE / "bft-backlog-lint.py")
    lint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lint)
    src = lint.resolve_source(pr, a.source)
    if not src or not src.is_file():
        print("skeleton: БФТ не найден — положи его рядом с проектом под именем из source_doc или передай --source", file=sys.stderr)
        return 2
    g = bg.build(src)
    sk = Skeleton(g, pr.story, *deps_rows(src.read_text(encoding="utf-8")))
    sk.layout()
    title = pr.story.title if pr.story and pr.story.title else src.stem
    plan, index = sk.render(re.sub(r"^\[История\]\s*", "", title))
    (pf.parent / "screens").mkdir(parents=True, exist_ok=True)
    made = screen_stubs(pf.parent / "screens", pr.story, root)
    pf.write_text(plan, encoding="utf-8")
    (pf.parent / "skeleton.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    stubs = len(bp.STUB.findall(plan))
    cards = sum(len(t["cards"]) for t in sk.tasks)
    print(f"skeleton: {len(sk.tasks)} задач, {cards} карточек, атомов БФТ {len(g.atoms)}, ID семейств {len(g.members)} — {pf}")
    print(f"skeleton: мест {{{{…}}}} для текста — {stubs}; где лежит каждый атом — {pf.parent / 'skeleton.md'}")
    if made:
        print(f"skeleton: требования к экранам — {', '.join(made)} в {pf.parent / 'screens'}: заполни места {{{{…}}}} сам по шаблону (resources/screen_notes.md)")
    print("дальше: ./blueprint.py groom fill — пакет на каждый блок; агенты заполняют; ./blueprint.py groom merge fill; затем ./blueprint.py apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())

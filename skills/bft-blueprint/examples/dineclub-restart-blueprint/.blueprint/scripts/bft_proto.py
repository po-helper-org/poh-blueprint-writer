"""Прототип по контрактам: план показа `prototype/spec.md`, каркас, проверки PT и сборка.

Прототип — история через экраны, которую можно пройти шаг за шагом: экраны берутся из «Истории» как есть
(закрытый словарь элементов), данные — из контрактов (`contracts/C-N.md`): что уходит, что приходит,
какие ошибки. Модель ничего не рисует и не выбирает компоненты — она связывает шаг с вызовом и вписывает
значения полей для демо. Сборка детерминирована: `prototype/` с web (пошаговый показ, клиент, сотрудник,
админка, внешняя сторона), api (FastAPI одним файлом, отвечает по контрактам) и docker-compose.yml.

Стандарт — `resources/prototype.md`, шаблон — `templates/prototype.md`.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import bft_blueprint as bb
import bft_backlog as bl
import bft_contracts as bc

HERE = Path(__file__).resolve().parent
DIR = "prototype"
SPEC = "spec.md"
APPS = {"client": "клиент", "staff": "сотрудник", "admin": "админка", "external": "внешняя сторона"}
KEYS = ("приложение", "экраны", "вызов", "ввод", "показать", "успех", "отказ", "заметка")
CUSTOMER = re.compile(r"клиент|гост[ьяи]|покупател|посетител|пользовател|абонент|пассажир|пациент|зрител|житель|студент|водител", re.I)
ADMIN = re.compile(r"админк|кабинет|консол|бэк-?офис|crm", re.I)
STEP_RE = re.compile(r"^##\s+((?:Ш\d+)|(?:C-\d+))\s*·\s*(.+?)\s*$")
EMPTY = {"", "—", "-", "–", "нет"}


@dataclass
class PStep:
    id: str
    title: str
    line: int
    vals: dict = field(default_factory=dict)      # {ключ: (строка, значение)}

    def get(self, key: str) -> str:
        return self.vals.get(key, (0, ""))[1].strip()

    def line_of(self, key: str) -> int:
        return self.vals.get(key, (self.line, ""))[0]

    def items(self, key: str) -> list[str]:
        v = self.get(key)
        return [] if v in EMPTY else [x.strip() for x in re.split(r"\s*[,;]\s*", v) if x.strip()]

    @property
    def calls(self) -> list[str]:
        return self.items("вызов")

    @property
    def inputs(self) -> dict[str, str]:
        out = {}
        v = self.get("ввод")
        for part in ([] if v in EMPTY else v.split(";")):
            k, sep, val = part.partition("=")
            if k.strip():
                out[k.strip()] = val.strip() if sep else ""
        return out

    @property
    def fail(self) -> tuple[str, str]:
        v = self.get("отказ")
        if v in EMPTY:
            return "", ""
        scr, _, code = v.partition("=")
        return scr.strip(), code.strip()


@dataclass
class Spec:
    path: Path
    rel: str
    title: str = ""
    steps: list[PStep] = field(default_factory=list)


def parse(pr: bl.Project) -> Spec | None:
    f = pr.root / DIR / SPEC
    if not f.is_file():
        return None
    sp = Spec(f, f"{DIR}/{SPEC}")
    cur = None
    for n, raw in enumerate(f.read_text(encoding="utf-8").split("\n"), start=1):
        ln = raw.rstrip()
        if ln.startswith("# ") and not sp.title:
            sp.title = re.sub(r"^#\s+(Прототип:\s*)?", "", ln).strip()
            continue
        m = STEP_RE.match(ln)
        if m:
            cur = PStep(m.group(1), m.group(2), n)
            sp.steps.append(cur)
            continue
        if ln.startswith("## "):
            pr.err(sp.rel, n, "PT001", f"шаг — «## Ш7 · Название» (шаг истории) или «## C-3 · Название» (вызов внешней стороны), а не «{ln[:50]}»")
            cur = None
            continue
        if cur is None or not ln.strip():
            continue
        k = re.match(r"^([а-яё]+):\s*(.*)$", ln.strip())
        if not k or k.group(1) not in KEYS:
            pr.err(sp.rel, n, "PT001", f"{cur.id}: строка «ключ: значение», ключи — {', '.join(KEYS)}; а не «{ln.strip()[:50]}»")
            continue
        if k.group(1) in cur.vals:
            pr.err(sp.rel, n, "PT001", f"{cur.id}: «{k.group(1)}» второй раз")
        cur.vals[k.group(1)] = (n, k.group(2))
    return sp


# --- связи истории, карты и контрактов -------------------------------------------------------------------

def _card_screens(pr: bl.Project) -> dict[str, set[str]]:
    """Экраны карточки: документы экранов в documentation карточки."""
    by_rel = {d.rel: sid for sid, d in pr.screens.items()}
    out = {}
    for c in pr.cards + pr.tasks:
        sids = set()
        for did in c.docs:
            d = pr.docs.get(str(did))
            if d and d.rel in by_rel:
                sids.add(by_rel[d.rel])
        out[c.id] = sids
    for c in pr.cards:   # экраны задачи — и её карточек
        if not out.get(c.id) and c.parent in out:
            out[c.id] = set(out[c.parent])
    return out


def _persona(pr: bl.Project, pid: str):
    return next((p for p in pr.story.personas if p.id == pid), None)


def app_of(pr: bl.Project, step) -> str:
    """Чьё приложение: клиент, сотрудник рядом с ним или админка — по персонажу и контуру экранов."""
    p = _persona(pr, step.persona)
    if p and CUSTOMER.search(p.name):
        return "client"
    contours = " ".join(sc.contour for sc in pr.story.screens if sc.id in step.screens)
    return "admin" if ADMIN.search(contours) else "staff"


def story_order(pr: bl.Project) -> list:
    """Шаги истории для показа: по этапам слева направо, внутри этапа — по персонажам; «было» и «стало» — нет."""
    order = {s.id: i for i, s in enumerate(pr.story.stages)}
    pidx = {p.id: i for i, p in enumerate(pr.story.personas)}
    steps = [s for s in pr.story.steps if s.stage_from in order]
    return sorted(steps, key=lambda s: (order[s.stage_from], pidx.get(s.persona, 99), s.line))


def leaf_fields(c: bc.Contract) -> list[str]:
    """Поля ответа без родителей: items.name — да, items (массив) — только если у него нет вложенных."""
    names = [x for x in c.fields("Ответ") if bc.FIELD_RE.match(x)]
    return [x for x in names if not any(y.startswith(x + ".") for y in names)]


# --- каркас ------------------------------------------------------------------------------------------------

def _words(t: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[а-яёa-z]{4,}", t.lower().replace("ё", "е"))}


def _inputs_line(c: bc.Contract) -> str:
    req = [r for r in c.rows("Запрос") if r.cells.get("Обяз.") == "да"]
    return "ввод: " + ("; ".join(f"{r.cells['Поле'].strip('` ')} = {{{{значение для демо, {r.cells.get('Тип', 'string')}}}}}" for r in req) or "—")


def plan_calls(pr: bl.Project, contracts: list[bc.Contract]) -> dict[str, list[dict]]:
    """Какой шаг какой контракт вызывает. Решение — таблица, а не модель:
    - кандидаты — шаги, чьи экраны показывает карточка контракта;
    - GET (прочитать) — на каждом кандидате, чей экран принадлежит вызывающей стороне: экран сам загружает данные;
    - остальное — один запускающий шаг: контур экрана = caller (+3), камера (+2), кнопка (+1), приложение сотрудника (+1);
      экран успеха и отказа — из экранов карточек того же контракта; нет кнопки ни у кого — вызов «за кадром»
      на каждом кандидате: сначала вызов, потом экран результата (оповещение, «Подключён»).
    {ID шага: [{contract, before, ok, fail, code}]}"""
    st = pr.story
    scr_of = _card_screens(pr)
    screens = {sc.id: sc for sc in st.screens}
    order = story_order(pr)
    plan: dict[str, list[dict]] = {}
    for c in contracts:
        if c.boundary == "service-db" or not c.get("op"):
            continue
        mine = set().union(*(scr_of.get(cid, set()) for cid in c.cards)) if c.cards else set()
        # экран шага рядом с экраном карточки — того же стыка (F4 «Отказ» в шаге с F3), даже если документа экрана нет
        mine |= {x for s in order if set(s.screens) & mine for x in s.screens if x in screens and screens[x].view == "альтернативный"}
        cand = [s for s in order if set(s.screens) & mine]
        if not cand:
            continue
        caller = _words(c.get("caller"))
        code = next((r.cells.get("Код", "").strip("` ") for r in c.rows("Ошибки")), "")
        own = lambda sid: bool(caller & _words(screens[sid].contour)) if sid in screens else False
        if c.get("op").split()[0] == "GET":
            for s in cand:
                shown = [x for x in s.screens if x in mine and own(x)] or [x for x in s.screens if x in mine]
                plan.setdefault(s.id, []).append({"contract": c, "before": s.screens, "ok": shown[-1], "fail": "", "code": code})
            continue

        def score(s) -> tuple:
            best = 0
            for x in s.screens:
                kinds = {e[0] for e in screens[x].elements} if x in screens else set()
                v = 3 * own(x) + 2 * ("camera" in kinds) + ("cta" in kinds) + (own(x) and app_of(pr, s) != "client")
                best = max(best, v)
            return best
        top = max(score(s) for s in cand)
        pool = [x for s in cand for x in s.screens if x in mine]
        alt = [x for x in pool if screens.get(x) and screens[x].view == "альтернативный"]
        if top <= 0:   # никто не нажимает: система вызывает сама, экран — уже результат
            for s in cand:
                res = [x for x in s.screens if x in mine]
                plan.setdefault(s.id, []).append({"contract": c, "before": [], "ok": res[0], "fail": "", "code": code})
            continue
        s = next(x for x in cand if score(x) == top)
        trig = next(x for x in s.screens if x in screens and 3 * own(x) + 2 * ("camera" in {e[0] for e in screens[x].elements})
                    + ("cta" in {e[0] for e in screens[x].elements}) + (own(x) and app_of(pr, s) != "client") == top)
        after = [x for x in pool if x != trig and x not in alt]
        later = [x for t in cand[cand.index(s):] for x in t.screens if x in mine and x != trig and x not in alt]
        ok = (later or after or [trig])[0]
        acts = {e[0] for e in screens[trig].elements} & {"cta", "camera"} if trig in screens else set()
        # экран без кнопки и камеры ничего не запускает: вызов за кадром, экран — уже результат
        plan.setdefault(s.id, []).append({"contract": c, "before": [trig] if acts else [], "ok": ok if acts else trig,
                                          "fail": alt[0] if alt else "", "code": code})
    return plan


def skeleton(pr: bl.Project, contracts: list[bc.Contract]) -> str:
    st = pr.story
    plan = plan_calls(pr, contracts)
    title = re.sub(r"^\[История\]\s*", "", st.title or pr.title)
    out = [f"# Прототип: {title}", "",
           "Показ — сверху вниз: шаги истории по этапам. Правила — `.blueprint/rules/prototype.md`.",
           "Места в двойных фигурных скобках заполни, остальное каркас взял из истории и контрактов — не меняй без причины.", ""]
    used: set[str] = set()
    for s in story_order(pr):
        lines = [f"## {s.id} · {s.title}", f"приложение: {app_of(pr, s)}"]
        calls = plan.get(s.id, [])
        if not calls:
            out += lines + [f"экраны: {', '.join(s.screens) if s.screens else '—'}", "вызов: —", ""]
            continue
        first = calls[0]
        before = first["before"]
        lines.append(f"экраны: {', '.join(before) if before else '—'}")
        lines.append(f"вызов: {', '.join(x['contract'].id for x in calls)}")
        merged: dict[str, str] = {}
        for x in calls:
            used.add(x["contract"].id)
            for part in _inputs_line(x["contract"])[6:].split("; "):
                if "=" in part:
                    k, v = part.split(" = ", 1)
                    merged.setdefault(k, v)
        lines.append("ввод: " + ("; ".join(f"{k} = {v}" for k, v in merged.items()) or "—"))
        lines.append(f"показать: {', '.join(dict.fromkeys(f for x in calls for f in leaf_fields(x['contract']))) or '—'}")
        lines.append(f"успех: {calls[-1]['ok'] or '—'}")
        lines.append(f"отказ: {(first['fail'] or '—') + (' = ' + first['code'] if first['code'] else '')}")
        out += lines + [""]
    # внешняя сторона вызывает нас: свой шаг на каждый external-контракт без экрана в истории
    for c in contracts:
        if c.boundary == "external" and c.get("op") and c.id not in used:
            code = next((r.cells.get("Код", "").strip("` ") for r in c.rows("Ошибки")), "")
            out += [f"## {c.id} · {c.title}", "приложение: external", "экраны: —", f"вызов: {c.id}", _inputs_line(c),
                    f"показать: {', '.join(leaf_fields(c)) or '—'}", "успех: —", f"отказ: —{' = ' + code if code else ''}", ""]
    return "\n".join(out).rstrip("\n") + "\n"


# --- проверки ----------------------------------------------------------------------------------------------

def check(pr: bl.Project, sp: Spec, contracts: list[bc.Contract]) -> None:
    rel = sp.rel
    by_id = {c.id: c for c in contracts}
    story_steps = {s.id: s for s in pr.story.steps} if pr.story else {}
    screens = {sc.id for sc in pr.story.screens} if pr.story else set()
    text = sp.path.read_text(encoding="utf-8")
    for m in re.finditer(r"\{\{(.+?)\}\}", text):
        n = text[:m.start()].count("\n") + 1
        pr.err(rel, n, "PT009", f"место {{{{…}}}} не заполнено: {m.group(1)[:80]}")
    seen = set()
    for s in sp.steps:
        if s.id in seen:
            pr.err(rel, s.line, "PT001", f"{s.id}: шаг второй раз")
        seen.add(s.id)
        if s.id.startswith("Ш") and s.id not in story_steps:
            pr.err(rel, s.line, "PT002", f"{s.id}: такого шага нет в «Истории»")
        if s.id.startswith("C-") and s.id not in by_id:
            pr.err(rel, s.line, "PT002", f"{s.id}: такого контракта нет в contracts/")
        app = s.get("приложение")
        if app not in APPS:
            pr.err(rel, s.line_of("приложение"), "PT003", f"{s.id}: приложение — {' | '.join(APPS)}, а не «{app or '—'}»")
        for sid in s.items("экраны") + [x for x in (s.get("успех"), s.fail[0]) if x not in EMPTY]:
            if "{{" not in sid and sid not in screens:
                pr.err(rel, s.line_of("экраны"), "PT004", f"{s.id}: экрана {sid} нет в «Истории»")
        if "{{" in s.get("вызов"):
            continue
        called = []
        for cid in s.calls:
            c = by_id.get(cid)
            if not c:
                pr.err(rel, s.line_of("вызов"), "PT005", f"{s.id}: контракта {cid} нет в contracts/")
            elif c.boundary == "service-db":
                pr.err(rel, s.line_of("вызов"), "PT005", f"{s.id}: {cid} — данные хранилища, его не вызывают с экрана; он покажется в панели шага сам")
            else:
                called.append(c)
        if called:   # несколько вызовов шага — один ввод и один ответ на всех: проверка по объединению полей
            names = ", ".join(c.id for c in called)
            req: dict = {}
            for c in called:
                for r in c.rows("Запрос"):
                    req.setdefault(r.cells.get("Поле", "").strip("` "), r)
            for k, v in s.inputs.items():
                if k not in req:
                    pr.err(rel, s.line_of("ввод"), "PT006", f"{s.id}: поля «{k}» нет в «Запросе» {names}")
                elif not v:
                    pr.err(rel, s.line_of("ввод"), "PT006", f"{s.id}: «{k} = значение» — что вводит пользователь в демо")
            for k, r in req.items():
                if r.cells.get("Обяз.") == "да" and k not in s.inputs:
                    pr.err(rel, s.line_of("ввод"), "PT006", f"{s.id}: обязательное поле «{k}» ({names}) — в «ввод: {k} = …»")
            resp = {f for c in called for f in c.fields("Ответ")}
            for k in s.items("показать"):
                if k not in resp:
                    pr.err(rel, s.line_of("показать"), "PT007", f"{s.id}: поля «{k}» нет в «Ответе» {names}")
            scr, code = s.fail
            codes = {r.cells.get("Код", "").strip("` ") for c in called for r in c.rows("Ошибки")}
            if code and code not in codes:
                pr.err(rel, s.line_of("отказ"), "PT008", f"{s.id}: кода {code} нет в «Ошибках» {names}: {', '.join(sorted(codes)) or '—'}")
        if s.calls and not s.items("показать"):
            pr.warn(rel, s.line_of("вызов"), "PT021", f"{s.id}: вызов без «показать» — что из ответа видит человек?")
    used = {cid for s in sp.steps for cid in s.calls}
    for c in contracts:
        if c.boundary != "service-db" and c.get("op") and c.id not in used:
            pr.warn(rel, 1, "PT020", f"{c.id} «{c.title}» не вызывается ни на одном шаге — стык не показан заказчику")


# --- сборка ------------------------------------------------------------------------------------------------

def _contract_json(c: bc.Contract) -> dict:
    rows = lambda sec: [dict(r.cells) for r in c.rows(sec)]
    return {"id": c.id, "title": c.title, "boundary": c.boundary, "caller": c.get("caller"), "callee": c.get("callee"),
            "op": c.get("op"), "cards": c.cards, "request": rows("Запрос"), "response": rows("Ответ"),
            "example": c.example, "errors": rows("Ошибки"), "chain": rows("Цепочка"), "data": rows("Данные"),
            "sequence": [{"from": x.src, "arrow": x.arrow, "to": x.dst, "msg": x.msg} for x in c.sequence]}


def compile_spec(pr: bl.Project, sp: Spec, contracts: list[bc.Contract]) -> dict:
    st = pr.story
    story_steps = {s.id: s for s in st.steps}
    stages = {s.id: s.name for s in st.stages}
    by_id = {c.id: c for c in contracts}
    db = [c for c in contracts if c.boundary == "service-db"]
    steps = []
    for s in sp.steps:
        ss = story_steps.get(s.id)
        called = [by_id[x] for x in s.calls if x in by_id]
        cards = {cid for c in called for cid in c.cards}
        p = _persona(pr, ss.persona) if ss else None
        steps.append({
            "id": s.id, "title": s.title, "app": s.get("приложение"),
            "stage": ss.stage_from if ss else "", "stageName": stages.get(ss.stage_from, "") if ss else "",
            "persona": p.name if p else (by_id[s.id].get("caller") if s.id in by_id else ""),
            "text": ss.text if ss else (by_id[s.id].title if s.id in by_id else ""),
            "was": ss.was if ss else "", "source": ss.source if ss else "",
            "screens": s.items("экраны"), "calls": s.calls, "inputs": s.inputs, "show": s.items("показать"),
            "ok": "" if s.get("успех") in EMPTY else s.get("успех"),
            "fail": {"screen": s.fail[0], "code": s.fail[1]}, "note": s.get("заметка"),
            "data": [c.id for c in db if cards & set(c.cards)],
        })
    screens = {sc.id: {"id": sc.id, "contour": sc.contour, "device": sc.device, "view": sc.view, "elements": sc.elements}
               for sc in st.screens}
    return {"title": sp.title or st.title, "epic": pr.meta.get("epic_slug", ""), "apps": APPS, "steps": steps,
            "screens": screens, "contracts": {c.id: _contract_json(c) for c in contracts}}


COMPOSE = """# Прототип «{title}» — собран ./blueprint.py prototype build, руками не правь
services:
  api:
    image: python:3.12-slim
    working_dir: /api
    volumes: ["./api:/api:ro"]
    command: sh -c "pip install --quiet --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0 && uvicorn main:app --host 0.0.0.0 --port 8000"
    ports: ["8000:8000"]
  web:
    image: python:3.12-slim
    working_dir: /web
    volumes: ["./web:/web:ro"]
    command: python -m http.server 8080
    ports: ["8080:8080"]
    depends_on: [api]
"""

README = """# Прототип «{title}»

Собран `./blueprint.py prototype build` из `prototype/spec.md`, «Истории» и `contracts/`. Руками не правь —
правь план показа и контракты, затем собери снова.

```bash
docker compose up        # показ — http://localhost:8080, MockAPI — http://localhost:8000/docs
```

Без Docker: открой `web/index.html` — MockAPI отвечает прямо в браузере по тем же контрактам.

- **Шаги** — слева: история по этапам; приложение шага — клиент, сотрудник, админка или внешняя сторона.
- **Экран** — по центру: экраны «Истории»; кнопка вызывает контракт, ответ подставляется в экран.
- **Как это работает** — справа: Sequence, метод, поля запроса и ответа с источником в БФТ, ошибки
  (переключатель «успех / ошибка»), цепочка за кадром, данные хранилища, живой запрос и ответ.
- **Замечания** — кнопка в шапке: клик по точке экрана ставит пин с текстом; «Выгрузить» — `review.json`.
  `./blueprint.py prototype review review.json` превращает пины в вопросы карты.
"""


def build(pr: bl.Project, sp: Spec, contracts: list[bc.Contract], out: Path) -> list[str]:
    data = compile_spec(pr, sp, contracts)
    blob = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    web, api = out / "web", out / "api"
    for d in (web, api, web / "vendor"):
        d.mkdir(parents=True, exist_ok=True)
    files = {
        web / "index.html": (HERE / "proto_page.html").read_text(encoding="utf-8").replace("{{TITLE}}", _esc(data["title"])),
        web / "runtime.js": (HERE / "proto_runtime.js").read_text(encoding="utf-8"),
        web / "runtime.css": (HERE / "proto_runtime.css").read_text(encoding="utf-8"),
        web / "spec.js": "window.SPEC = " + blob + ";\n",
        api / "spec.json": blob + "\n",
        api / "main.py": (HERE / "proto_api.py").read_text(encoding="utf-8"),
        out / "docker-compose.yml": COMPOSE.format(title=data["title"].replace('"', "'")),
        out / "README.md": README.format(title=data["title"]),
    }
    written = []
    for f, text in files.items():
        if not f.is_file() or f.read_text(encoding="utf-8") != text:
            f.write_text(text, encoding="utf-8")
            written.append(str(f.relative_to(out)))
    mm = next((p for p in (pr.root / ".blueprint" / "vendor" / "mermaid.min.js", HERE.parent / "vendor" / "mermaid.min.js") if p.is_file()), None)
    if mm and (not (web / "vendor" / "mermaid.min.js").is_file() or (web / "vendor" / "mermaid.min.js").stat().st_size != mm.stat().st_size):
        shutil.copyfile(mm, web / "vendor" / "mermaid.min.js")
        written.append("web/vendor/mermaid.min.js")
    return written


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- замечания ---------------------------------------------------------------------------------------------

def review_rows(pr: bl.Project, sp: Spec, contracts: list[bc.Contract], pins: list[dict]) -> list[tuple[str, str, str]]:
    """Пины прототипа → (Где, Вопрос, Кому) для «Вопросов» карты: «Где» — карточка, чей экран или вызов на шаге."""
    by_id = {c.id: c for c in contracts}
    scr_of = _card_screens(pr)
    steps = {s.id: s for s in sp.steps}
    rows = []
    for p in pins:
        s = steps.get(p.get("step", ""))
        text = re.sub(r"\s+", " ", str(p.get("text", ""))).strip().replace("|", "/")
        if not s or not text:
            continue
        scr = p.get("screen", "")
        card = next((cid for cid, sids in scr_of.items() if scr and scr in sids and "." in cid), "")
        if not card:
            card = next((cid for x in s.calls if x in by_id for cid in by_id[x].cards), "")
        if not card:
            stage = next((st.stage_from for st in pr.story.steps if st.id == s.id), "")
            card = next((c.id for c in pr.cards if c.stage == stage), pr.cards[0].id if pr.cards else "")
        where = f"прототип {s.id}" + (f", экран {scr}" if scr else "") + (f", «{p['block']}»" if p.get("block") else "")
        rows.append((card, f"{text} ({where})", str(p.get("who") or "PO")))
    return rows


HINTS = {
    "PT001": "шаг — «## Ш7 · Название» из «Истории» (или «## C-3 · Название» для вызова внешней стороны), под ним строки «ключ: значение»: "
             "приложение, экраны, вызов, ввод, показать, успех, отказ, заметка",
    "PT002": "ID шага — из «Истории» (Ш7) или ID внешнего контракта (C-3); каркас ./blueprint.py prototype skeleton раскладывает их сам",
    "PT003": "приложение: client — клиент; staff — сотрудник рядом с клиентом; admin — админка, кабинет; external — внешняя система",
    "PT004": "экраны, успех, отказ — ID экранов из таблицы «Экраны» «Истории» (B1, F3)",
    "PT005": "вызов: ID контракта, который этот экран вызывает (C-3), несколько — через запятую; ничего не вызывает — «вызов: —»; service-db не вызывается",
    "PT006": "ввод: каждое обязательное поле «Запроса» — «поле = значение» через «;», значение — правдоподобное для демо, того же типа",
    "PT007": "показать: поля из «Ответа» контракта, которые человек видит на экране после вызова",
    "PT008": "отказ: «экран = КОД» — экран альтернативного вида из «Истории» и код из «Ошибок» контракта; экрана нет — «отказ: — = КОД»",
    "PT009": "допиши места {{…}}: подсказка в месте говорит, откуда взять значение",
    "PT020": "стык есть, а заказчик его не увидит: добавь вызов на шаг, экран которого его показывает, или шаг «## C-N · …» с приложением external",
    "PT021": "«показать: поле, поле» — что из ответа видно на экране",
}

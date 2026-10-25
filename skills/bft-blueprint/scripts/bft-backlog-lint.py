#!/usr/bin/env python3
"""bft-backlog-lint — проверка Service Blueprint в проекте Backlog.md (гейт карты инициативы).

Карта — второй этап blueprint: на согласованную историю ложатся задачи команд («Что делаем») и
технические карточки («Как это работает»: Employee Actions, Technology, Backstage, Support).
Всё хранится в проекте Backlog.md. Стандарт — `resources/backlog_rules.md`.

  ОШИБКИ (код выхода 1)
  BL001  не проект Backlog.md
  BL002  документ «Карта»: паспорт <!-- bft-map -->, заголовок
  BL003  документ «История»: нет или с ошибками (ST — коды истории)
  BL004  «Команды» и «Вопросы» карты: таблицы, ID
  BL005  файл не читается как задача или документ Backlog.md; повтор ID
  BL006  задача «Что делаем»: этап, вид, команда, без родителя
  BL007  постановка: зачем, разделы ASIS, GAP, TOBE, HowToDemo, критерии приемки
  BL008  карточка «Как это работает»: родитель, слой, этап, команда
  BL009  карточка: разделы UserStory, JobStory, Параметры, Процесс, HowToDemo; параметры, шаги процесса, ссылки
  BL010  вопрос: ID, «Где», тип
  BL011  documentation ссылается на документ, которого нет
  BL014  задача длиннее 80 знаков или карточка длиннее 90 — карта читается за минуту
  BL015  БФТ-источник из `--source` не найден (без `--source` — предупреждение, сверка пропущена)
  BL016  требование из задачи, карточки или экрана не найдено в БФТ
  BL017  ФТ/ИТ/НФТ из БФТ не попало ни в одну задачу и ни в одну карточку
  BL018  технический язык в названии или сути: API, протоколы, БД
  SN0xx  требования к экранам — `bft_screens.py`, `resources/screen_notes.md`

  ПРЕДУПРЕЖДЕНИЯ (код выхода 1 только с --strict)
  BL015  БФТ (`source_doc` паспорта) не лежит рядом с проектом — сверка с БФТ пропущена
  BL020  этап истории без задач — что на нём делают команды?
  BL021  задача без карточки «Как это работает»
  BL022  схема BPMN карточки не совпадает с «Процессом» — пересоберёт `bft-backlog-build.py`
  BL023  у карточки нет управления или механизма
  BL030  UserStory не «Как …, я хочу …, чтобы …» или JobStory не «Когда …, хочу …, чтобы …»
  BL026  БФТ изменился после сборки (`source_rev` не совпадает)
  BL027  число не найдено ни в БФТ, ни в ответах на вопросы
  BL028  карточка без связей: ни один вход не пришёл от карточки, ни один выход не ушёл к карточке
  BL033  UserStory от лица команды-исполнителя, а не того, кто пользуется результатом
  BL034  в процессе карточки участвует PO, СА, разработка: карточка о работе над проектом, а не о сервисе
  BL035  у задачи один кандидат — это исполнитель
  BL036  ПТ из БФТ нет ни в одной задаче и ни в одной карточке: роль осталась без своей истории
  BL037  ID семейства из БФТ (параметр P7, инвариант I2, разрыв G1) нет на карте
  BL038  критерий приёмки требования из БФТ не перенесён в «Критерии приемки» задачи (предупреждение)
  BL039  карточка названа так же, как её задача: название не говорит, что происходит в сервисе
  BL040  участник процесса без имени: «Система», «Сервис», «Приложение»
  BL041  карточка technology от лица сотрудника, который на этом этапе на виду у клиента, — слой employee

  СБОРКА (`bft-backlog-build.py`)
  BL029  `--check`: скрипты, правила или инструкции проекта устарели
  BL031  `--check`: картинка экрана в backlog/assets/screens не совпадает с «Историей»
  BL032  на странице оказалась бы строка, которой нет в файлах проекта, — сборка не пишет ничего

Использование:
    python3 bft-backlog-lint.py <проект> [--source БФТ.md | --no-source] [--strict]
Формат вывода: <путь>:<строка>: <УРОВЕНЬ> <КОД> <сообщение>
Коды выхода: 0 — ошибок нет; 1 — ошибки (или предупреждения с --strict); 2 — проект не прочитан.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bft_blueprint as bb  # noqa: E402
import bft_backlog as bl  # noqa: E402
import bft_graph as bg  # noqa: E402

_spec = importlib.util.spec_from_file_location("bp_lint", HERE / "bft-blueprint-lint.py")
_bp_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bp_lint)
API_PATTERNS = _bp_lint.API_PATTERNS
NUM_RE = re.compile(r"\d[\d \u00a0.,:%]*\d|\d")   # число в одной строке: перенос строки его не склеивает


def check(pr: bl.Project, source: Path | None, no_source: bool, explicit: bool = False) -> None:
    # --- полнота и связность -----------------------------------------------------------------
    if pr.story:
        for st in pr.story.stages:
            if not any(t.stage == st.id for t in pr.tasks):
                pr.warn(pr.story_doc.rel, st.line + pr.story_doc.off, "BL020", f"этап {st.id} «{st.name}» без задач — что на нём делают команды?")
        employee_hint(pr)
    with_card = {c.parent for c in pr.cards}
    linked = {x for a, b, _ in pr.links() for x in (a, b)}
    for t in pr.tasks:
        if t.id not in with_card:
            pr.warn(t.rel, 1, "BL021", f"{t.id}: задача не показана в «Как это работает» — нет подзадачи с меткой layer:…")
        if len(t.title) > bl.MAX_TASK:
            pr.err(t.rel, 2, "BL014", f"{t.id}: задача {len(t.title)} знаков (больше {bl.MAX_TASK}) — один результат одной фразой")
        tech(pr, t, t.title + " " + t.why)
    for c in pr.cards:
        if c.params.get("out") and (not c.params.get("ctl") or not c.params.get("mech")):
            pr.warn(c.rel, c.off, "BL023", f"{c.id}: нет {'управления' if not c.params.get('ctl') else 'механизма'} — правила и исполнитель функции")
        if c.id not in linked:
            pr.warn(c.rel, c.off, "BL028", f"{c.id}: нет связей — сошлись на карточку во входе ({pr.prefix}-8.1) или выходе")
        if len(c.title) > bl.MAX_CARD:
            pr.err(c.rel, 2, "BL014", f"{c.id}: карточка {len(c.title)} знаков (больше {bl.MAX_CARD})")
        tech(pr, c, c.title + " " + c.lead)
    for c in bl.sync_schema(pr, write=False):
        pr.warn(c.rel, c.off, "BL022", f"{c.id}: схема BPMN не совпадает с «Процессом» — `./blueprint.py build` пересоберёт её")

    # --- сверка с БФТ ------------------------------------------------------------------------
    if no_source:
        return
    if source is None or not source.is_file():
        # явный --source обязан найтись; без него — проект без БФТ рядом (распакованный архив): сверка пропускается
        (pr.err if explicit else pr.warn)(pr.map_doc.rel if pr.map_doc else "", 1, "BL015",
                                          f"БФТ-источник не найден: {source or pr.meta.get('source_doc', '—')} — сверка с БФТ пропущена")
        return
    reqs, src_text = bb.load_requirements(source)
    if pr.meta.get("source_rev") and pr.meta["source_rev"] != bb.source_rev(source):
        pr.warn(pr.map_doc.rel, 1, "BL026", "БФТ изменился после сборки (source_rev не совпадает) — пересверь карту")
    by_key = {bb.req_key(r): r for r in reqs}

    def unknown(rid: str) -> str:
        twin = by_key.get(bb.req_key(rid))
        if twin:  # латинская буква вместо кириллической: связь с БФТ молча теряется
            return f"{rid} нет в БФТ {source.name} — в БФТ пишется {twin} (буква другого алфавита)"
        return f"{rid} нет в БФТ {source.name}"

    cited: set[str] = set()
    texts = []
    for t in pr.tasks + pr.cards:
        body = "\n".join([bl.MERMAID.sub("", t.desc)] + [x for _, x in t.ac])  # схема — копия параметров, не источник
        texts.append((t, body))
        for rid in sorted(set(bb.REQ_RE.findall(body))):
            if rid not in reqs:
                pr.err(t.rel, 1, "BL016", f"{t.id}: {unknown(rid)}")
            else:
                cited.add(rid)
    for d in pr.screens.values():
        for x in d.notes:
            for rid in bb.REQ_RE.findall(x.md):
                if rid not in reqs:
                    pr.err(d.rel, x.line, "BL016", f"«{x.title}»: {unknown(rid)}")
    for rid in reqs:
        if rid.split("-")[0] in ("ФТ", "ИТ", "НФТ") and rid not in cited:
            pr.err(pr.map_doc.rel, 1, "BL017", f"{rid} не попало ни в одну задачу и ни в одну карточку — где эта работа на карте?")
    graph_gates(pr, source, texts)
    answers = " ".join(q.answer for q in pr.questions if not q.open)
    for t, body in texts:
        clean = pr.id_re.sub("", bb.REQ_RE.sub("", body))
        for m in NUM_RE.finditer(clean):
            num = m.group(0).strip(" .,:")
            if num and num not in src_text and num not in answers:
                pr.warn(t.rel, 1, "BL027", f"{t.id}: число «{num}» не найдено ни в БФТ, ни в ответах")


CUSTOMER = re.compile(r"клиент|гост[ьяи]|покупател|посетител|пользовател|абонент|пассажир|пациент|зрител|житель|студент|водител", re.I)


def _stems(t: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[а-яёa-z]{4,}", t.lower())}


def employee_hint(pr: bl.Project) -> None:
    """BL041: карточка technology от лица сотрудника, который на этом этапе работает на виду у клиента, — это employee."""
    st = pr.story
    if not st or len(st.personas) < 2:
        return
    order = [x.id for x in st.stages]
    idx = {sid: i for i, sid in enumerate(order)}

    def on(pid: str, sid: str) -> bool:
        return any(s.persona == pid and s.stage_from in idx and idx[s.stage_from] <= idx[sid] <= idx.get(s.stage_to, idx[s.stage_from]) for s in st.steps)

    for c in pr.cards:
        if c.layer != "technology" or c.stage not in idx:
            continue
        role = re.match(r"^Как\s+(.+?),\s*я хочу", c.user_story.replace("**", ""))
        if not role or CUSTOMER.search(role.group(1)):
            continue
        me = [p for p in st.personas if not CUSTOMER.search(p.name) and _stems(p.name) & _stems(role.group(1)) and on(p.id, c.stage)]
        guest = [p for p in st.personas if CUSTOMER.search(p.name) and on(p.id, c.stage)]
        if me and guest:
            pr.warn(c.rel, 1, "BL041", f"{c.id}: {me[0].name} работает на этапе {c.stage} на виду у персонажа «{guest[0].name}» — это слой employee, "
                    "его экран (планшет, сканер) — внутри той же карточки")


def _norm(s: str) -> str:
    return re.sub(r"[^\w%]+", " ", s.lower().replace("ё", "е")).strip()


def graph_gates(pr: bl.Project, source: Path, texts: list) -> None:
    """Полнота по графу БФТ: роли (ПТ), семейства ID, критерии приёмки."""
    g = bg.build(source)
    alltext = "\n".join(body for _, body in texts)
    on_map = set(bb.REQ_RE.findall(alltext))
    for a in g.by_kind("ПТ"):
        if a.id not in on_map:
            who = f" — роль «{a.role}»" if a.role else ""
            pr.err(pr.map_doc.rel, 1, "BL036", f"{a.id} «{a.name}»{who}: нет ни в задаче, ни в карточке — чья это история на карте?")
    members = {f"{x}{y}" for x, y in bg.MEMBER_RE.findall(alltext)}   # «P1–P8» в тексте не исполняет P3: нужен каждый ID
    for mid, m in g.members.items():
        if mid not in members:
            pr.err(pr.map_doc.rel, 1, "BL037", f"{mid} «{m.label[:60]}» ({m.source} БФТ) нет на карте — правило «Управления» карточки, которую оно касается")
    acs = " ".join(_norm(x) for t in pr.tasks for _, x in t.ac)
    for a in g.atoms.values():
        if a.ac and a.kind != "БТ" and _norm(a.ac)[:40] not in acs:
            pr.warn(pr.map_doc.rel, 1, "BL038", f"{a.id}: критерий приёмки из БФТ «{a.ac[:70]}» — нет в «Критериях приемки» задач; перенеси дословно")


def tech(pr: bl.Project, t: bl.BTask, text: str) -> None:
    for pat, what in API_PATTERNS:
        m = pat.search(text)
        if m:
            pr.err(t.rel, 2, "BL018", f"{t.id}: {what} «{m.group(0)}» — устройство API и БД живёт у СА, не на карте")
            return


def resolve_source(pr: bl.Project, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    doc = pr.meta.get("source_doc")
    if not doc:
        return None
    for base in (pr.root, pr.root.parent):
        if (base / doc).is_file():
            return base / doc
    return pr.root.parent / doc


def run(root: Path, source: str | None, no_source: bool) -> bl.Project:
    pr = bl.parse(root)
    if not pr.errors:
        check(pr, resolve_source(pr, source), no_source, explicit=bool(source))
    return pr


# как исправить — по строке на код: печатается под отчётом (`--hints`, ./blueprint.py next и apply)
HINTS = {
    "BL002": "«Карта»: паспорт <!-- bft-map --> в начале и заголовок «# Карта: …» — так их создаёт bft-backlog-init.py, не трогай",
    "BL003": "«История» с ошибками ST: исправь <epic>-story.md (bft-story-lint.py) и пересоздай проект или правь документ «История»",
    "BL004": "таблицы «## Команды» (| ID | Команда |, ID латиницей) и «## Вопросы» (| ID | Кому | Вопрос | Где | Тип | Ответ |) в плане",
    "BL006": "задача: «этап:» — буква этапа истории; «вид:» — создать | доработать | используем | уточнить; «команда:» — ID из «Команд»",
    "BL007": "задача: первая строка — зачем; строка «Требования БФТ: ФТ-1, ИТ-2»; ### ASIS, ### GAP, ### TOBE, ### HowToDemo (нумерованно); ### Критерии приемки — хотя бы один пункт",
    "BL008": "карточка: ID вида BP-3.1 под задачей BP-3; «слой:» — employee | technology | backstage | support; «этап:» как у истории",
    "BL009": "карточка: ### UserStory, ### JobStory, ### Параметры (- **Вход:** …, - **Управление:** …, - **Выход:** …, - **Механизм:** …), ### Процесс (- Участник: действие), ### HowToDemo; (BP-8.1) в параметрах — только на карточки",
    "BL010": "вопрос: ID В1…, «Где» — ID задачи или карточки (BP-3, BP-3.1), «Тип» — вопрос или блокер",
    "BL011": "документы: — ID существующего документа (doc-5); экраны: — ID экрана, для которого есть plan/screens/F3.md",
    "BL014": "сократи название: задача до 80 знаков, карточка до 90 — детали в описание",
    "BL015": "положи БФТ рядом с папкой проекта под именем из source_doc паспорта или передай --source",
    "BL036": "ПТ — история роли: карточка с UserStory от этой роли и ID ПТ в тексте; ./blueprint.py skeleton раскладывает ПТ сам",
    "BL037": "ID из БФТ (P7, I2, G1) — строкой в «Управлении» карточки: «P7 эксклюзив тарифа: …»; разрыв — ещё и вопрос",
    "BL038": "критерий приёмки требования из БФТ — строкой в «Критерии приемки» задачи, дословно и с ID: «- … (ФТ-3)»",
    "BL016": "этого ID нет в БФТ — убери его или исправь опечатку (ФТ-1, ИТ-2, ПТ-А1); ID копируй из БФТ, не набирай",
    "BL017": "требование БФТ не попало на карту — допиши его в «Требования БФТ:» подходящей задачи или в текст карточки (./blueprint.py reqs — список)",
    "BL018": "убери из названия и сути API, протоколы, таблицы БД — это высота СА, не карты",
    "BL020": "у этапа истории нет задач — что на нём делают команды? добавь задачу с «этап: X» или объясни в итоге",
    "BL021": "у задачи нет карточки — добавь «## BP-N.1 · …» под ней",
    "BL022": "схема BPMN устарела — ./blueprint.py build пересоберёт её из «Процесса», руками не правь",
    "BL023": "в «Параметрах» карточки нет «Управление» или «Механизм» — правило с ID требования и кто исполняет",
    "BL026": "БФТ изменился после сборки — сверь карту с новыми требованиями и обнови source_rev (bft-backlog-init.py пишет его)",
    "BL027": "число без источника — поставь рядом ID требования (ФТ-1) или вынеси в «Вопросы» с [УТОЧНИТЬ у …]",
    "BL028": "карточка ни с кем не связана — во «Вход» укажи (BP-x.y), откуда пришло, или в «Выход» — куда ушло",
    "BL030": "UserStory: «Как <роль>, я хочу <действие>, чтобы <ценность>»; JobStory: «- Когда <ситуация>, хочу <мотивация>, чтобы <результат>». После «хочу» — действие, не «хочу, чтобы …»",
    "BL034": "«Как это работает» — сервис после запуска. Участники процесса — пользователь, сотрудник на линии, система; PO, СА и разработка строят сервис: их работа — задача «Что делаем» или вопрос",
    "BL039": "название карточки — что происходит, когда сервис работает: кто → что → результат («Реестр принимает продажу один раз на номер чека»), а не название задачи",
    "BL041": "сотрудник на виду у клиента (официант при госте, мастер-приёмщик при клиенте) — «слой: employee»; его планшет или сканер — в этой же карточке, не отдельной technology",
    "BL040": "участник процесса — система с именем из БФТ или «Механизма»: «Реестр продаж», «Приложение-сканер», а не «Система»",
    "BL035": "один кандидат — это исполнитель: «команда: id»; сомнение — строкой «Вопросов»",
    "BL033": "UserStory пишется от лица того, кто пользуется результатом карточки (гость, официант, контент-менеджер, PO), а не команды, которая её делает",
    "SN001": "файл экрана — plan/screens/<ID>.md, ID из таблицы «Экраны» «Истории»",
    "SN003": "экран: «# Название», картинки, затем ## Product, ## Design, ## Functions — по порядку, заметки — ### под вкладкой",
    "SN004": "у заметки ### нужен заголовок и текст; заголовки во вкладке не повторяются",
    "SN005": "сценарий Functions: строки **Дано** / **Когда** / **Тогда** — без **Тогда** не сценарий",
    "SN006": "картинка: ![подпись](../../assets/screens/F3.svg) — ID экрана из «Истории»",
    "SN021": "под заметкой строка «Источник: ФТ-1» или [УТОЧНИТЬ у …]",
    "SN022": "Product: «Когда …, хочу …, чтобы …»",
    "SN023": "у экрана истории нет требований — добавь plan/screens/<ID>.md (можно коротко: по заметке во вкладке)",
}


def hints(pr: bl.Project) -> None:
    codes = sorted({i.code for i in pr.issues if i.code in HINTS}, key=lambda c: (c[:2], c))
    if codes:
        print("как исправить:")
        for c in codes:
            print(f"  {c} — {HINTS[c]}")


def report(pr: bl.Project, strict: bool, name: str = "backlog-lint") -> int:
    for i in sorted(pr.issues, key=lambda i: (i.level != "ERROR", i.path, i.line)):
        print(f"{pr.root / i.path if i.path else pr.root}:{i.line}: {i.level} {i.code} {i.msg}")
    errors = len(pr.errors)
    warns = len(pr.issues) - errors
    blockers = [q for q in pr.questions if q.open and q.kind == "блокер"]
    for q in blockers:
        print(f"  блокер {q.id} → {q.to}: {q.text}")
    print(f"{name}: {len(pr.tasks)} задач, {len(pr.cards)} карточек «Как это работает», {len(pr.screens)} экранов с требованиями, "
          f"задач вне карты {pr.other}, открытых вопросов {sum(q.open for q in pr.questions)} (блокеров {len(blockers)}) — "
          f"ошибок {errors}, предупреждений {warns}")
    return 1 if errors or (strict and warns) else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", type=Path, help="папка проекта Backlog.md (<epic>-blueprint)")
    ap.add_argument("--source", help="путь к БФТ (по умолчанию — `source_doc` паспорта рядом с проектом)")
    ap.add_argument("--no-source", action="store_true", help="не сверять с БФТ (только форма карты)")
    ap.add_argument("--strict", action="store_true", help="предупреждения тоже дают код 1")
    ap.add_argument("--hints", action="store_true", help="под отчётом — как исправить каждый код")
    args = ap.parse_args()
    if not args.project.is_dir():
        print(f"{args.project}: не папка проекта", file=sys.stderr)
        return 2
    try:
        pr = run(args.project, args.source, args.no_source)
    except OSError as e:
        print(f"{args.project}: не прочитан: {e}", file=sys.stderr)
        return 2
    rc = report(pr, args.strict)
    if args.hints:
        hints(pr)
    return rc


if __name__ == "__main__":
    sys.exit(main())

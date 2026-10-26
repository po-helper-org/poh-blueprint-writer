

#!/usr/bin/env python3
"""bft-backlog-lint — проверка Service Blueprint в проекте Backlog.md (гейт карты инициативы).

Карта — второй этап blueprint: на согласованную историю ложатся задачи команд («Что делаем») и
технические карточки («Как это работает»: Employee Actions, Technology, Backstage, Support).
Всё хранится в проекте Backlog.md. Стандарт — `resources/backlog_rules.md`.

  ОШИБКИ (код выхода 1)
  BL049  «Триггеры» «Карты»: | Персонаж | Триггер | Этап |, персонаж и этап — из «Истории»
  BL047  подзадача: требования БФТ — у истории; постановка в формате зоны (Design — UserStory, JobStory, UserFlow; BE — ASIS, GAP, TOBE, Данные; DBA, FE, DevOps — ASIS, GAP, TOBE); чеклист у PO, BA, SA, ADR, Design, QA, Delivery
  BL043  подзадача истории: одна зона zone: (PO, SA, Design, FE, BE, QA, DevOps, Delivery), родитель — история, этап истории, команда, описание
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
  AR001  документы «ADR» (<!-- bft-adr -->) и «Системные требования» (<!-- bft-sysreq -->): паспорт, таблицы вариантов, решения, узких мест, компромиссов, контрактов
  AR002  второй документ «ADR» или «Системные требования»
  AR003  смысл этапа: ≥2 вариантов и явный выбор TO-BE, узкие места, компромиссы по трём осям, контракты совпадают с ADR, три вопроса системной аналитики
  AR005  предупреждения: нет узких мест/компромиссов, на карте есть слой Technology, а документов нет — этап включён не был
  AR006  C4 L3 ADR: контур — команда из «Команд», задачи есть на карте, потоки — между компонентами, контракт — из «Решения TO-BE»
  SM001  документ «Стыки» (<!-- bft-seams -->): паспорт, таблицы участников, обязательств, контрактов, точек, рисков
  SM002  второй документ «Стыки»
  SM003  стыки: команды-участники из «Команд», обязательства и контракты привязаны к стыкам
  SM005  стыки: предупреждения — стык без обязательств, условие включения этапа (≥2 команд, а документа нет)
  RL001  документ «План релиза» (<!-- bft-release -->): паспорт, дорожки DEV/STAGE/PROD, шаги, ворота
  RL002  второй документ «План релиза»
  RL003  план релиза: зависимости шагов, ворота между стендами
  RL005  план релиза: предупреждения — шаг без зависимостей, дорожка без ворот
  RK001  документ «Риски исполнения» (<!-- bft-risks -->): паспорт, «## Риски» | ID | История | Тип | Риск | Митигация | Владелец | Статус |
  RK002  второй документ «Риски исполнения»
  RK003  риск исполнения: «История» — история карты
  RK005  риск исполнения по данным карты (стык BE+FE, DevOps, интеграция систем) не записан — его не согласовать с PO
  RM001  документ «Roadmap» (<!-- bft-roadmap -->): паспорт (start — понедельник, sprint_weeks 1|2), «## План» | ID | Неделя с | Неделя по |, не больше 6 спринтов
  RM002  второй документ «Roadmap»
  RM003  Roadmap: строка плана — история или подзадача карты
  RM005  Roadmap: предупреждения — работа не в плане, у кроссфункциональной истории в плане не подзадачи, начало раньше конца зависимости
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
  BL051  карточка Support — не сценарий поддержки: проектная работа (макет, дизайнер, настройка) или нет признаков нештатной ситуации
  BL054  карточка «Как это работает» с командой или дубль (тот же экран, этап и слой) — команд на этой карте нет
  BL053  карточка «Как это работает» — разовая задача команды (переключает, переверстывает, настраивает), а не регулярный процесс; в Backstage — команда в участниках или механизме
  BL052  карточка Backstage: UserStory, JobStory, HowToDemo не нужны; «### Данные» — строки «- что — откуда»
  BL041  карточка technology от лица сотрудника, который на этом этапе на виду у клиента, — слой employee
  BL042  экран без исполнения: ни задача, ни её карточка не ссылаются на документ экрана — панель «Исполнение» пуста
  BL044  кроссфункциональная история (в работе две команды и больше) без подзадач по зонам: кто что делает?
  BL045  один экран делают истории разных команд — это один результат: одна история с подзадачами по зонам
  BL046  у истории нет приоритета Must / Should / Would (метка moscow:) — что коммитим заказчику?
  BL050  у персонажа истории нет триггера — с какого события начинается его путь на «Как это работает»?
  BL048  Design — не одна точка касания (экран) на задачу; BE берёт данные «нет в хранилище», а DBA в истории нет
  AR005  ADR без узких мест или компромиссов; на карте есть слой Technology (устройство систем), а документов «ADR»/«Системные требования» нет — этап включён не был
  AR007  C4 L3 ADR: нет «Компонентов»; компонент меняется, а задачи нет; компонент без потоков; контракт TO-BE не идёт ни по одному потоку
  SM005  стык без обязательств; команд 2 и больше, а документа «Стыки» нет — этап включён не был

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

sys.path.insert(0, str(HERE))

import bft_blueprint as bb  # noqa: E402

import bft_backlog as bl  # noqa: E402

import bft_graph as bg  # noqa: E402

_spec = importlib.util.spec_from_file_location("bp_lint", HERE / "bft-blueprint-lint.py")

_bp_lint = importlib.util.module_from_spec(_spec)

_spec.loader.exec_module(_bp_lint)

_spec.loader.exec_module(_bp_lint)

API_PATTERNS = _bp_lint.API_PATTERNS

NUM_RE = re.compile(r"\d[\d \u00a0.,:%]*\d|\d")   # число в одной строке: перенос строки его не склеивает

# Support — поддержка работающего сервиса в нештатной ситуации; проектная работа — не карточка вовсе
SUPPORT_SIGN = re.compile(r"обращени|возврат|модерац|провер|ручн|поддержк|жалоб|претензи|апелляц|инцидент|спор|нештат|ошибк|сбо[йя]|восстанов|разбира|помощ|реквизит|застрял", re.I)
PROJECT_WORK = re.compile(r"макет|дизайнер|айдентик|вёрстк|верстк|разработчик|готовит|настраива|подготав|рассыльщик|шаблон", re.I)

# BL053: «Как это работает» — только регулярный процесс работающего сервиса. Разовое изменение
# («переключает отправку на другой сервис», «переверстывает шаблоны») — задача команды, а не карточка;
# в Backstage участники и механизм — технологические компоненты, не команды
ONE_OFF = re.compile(r"(?<![а-яё])(?:доработанн|переработанн|обновлённ|обновленн|переключа|переверст|перенос|переезжа|перестраива|переделыва|мигрир|настраива|настро[ий]|внедря|подготав|готовит|верста|разрабатыва|дорабатыва)\w*", re.I)

def regular_hint(pr: bl.Project, c) -> None:
    """BL053: карточка — регулярный процесс; в Backstage — компоненты, а не команды."""
    steps = [x.get("text", "") for x in c.proc if x.get("t") == "task"] + [b.get("text", "") for x in c.proc for b in x.get("br", [])]
    m = ONE_OFF.search(c.title) or next((m for s in steps if (m := ONE_OFF.search(s))), None)
    if m:
        pr.warn(c.rel, c.off, "BL053", f"{c.id}: «{m.group(0)}» — разовая задача команды, а «Как это работает» — регулярный процесс работающего сервиса: "
                "«Рассыльщик отправляет письмо», «Сервис акций проверяет условия»; переключение, перевёрстка, настройка — задача «Что делаем»")
    if c.layer != "backstage":
        return
    contours = {s.contour.strip().lower() for s in (pr.story.screens if pr.story else [])}
    teams = {x.strip().lower() for t in pr.teams for x in (t.id, t.name)} - contours
    who = [ln for ln in bl.lanes_of(c.proc) if ln.strip().lower() in teams or bl.PROJECT_ROLE.match(ln.strip())]
    who += [it.text for it in c.params.get("mech", []) if it.text.strip().lower() in teams]
    if who:
        pr.err(c.rel, c.off, "BL053", f"{c.id}: в Backstage участвует команда «{who[0]}» — участники и механизм только технологические компоненты, "
               "которые обеспечивают регулярный процесс: «Сервис проверки билетов», «Триггеры касаний», «Каталог ресторанов»")

def teamless(pr: bl.Project) -> None:
    """BL054: «Как это работает» — целевая картинка глазами пользователя: команд и командных зон на ней нет,
    одно событие сервиса — одна карточка, даже если его делят несколько команд."""
    for c in pr.cards:
        if c.fm.get("assignee"):
            pr.warn(c.rel, 1, "BL054", f"{c.id}: у карточки «Как это работает» есть команда — убери её: здесь только компоненты и процессы, исполнители — в «Что делаем»")
    seen: dict = {}
    for c in pr.cards:
        for d in c.docs:
            k = (c.stage, c.layer, str(d).split()[0].lower())
            if k in seen and seen[k].id != c.id:
                pr.warn(c.rel, 1, "BL054", f"{c.id}: тот же экран, этап и слой, что у {seen[k].id} — одно событие сервиса описано дважды (по командам?): объедини в одну карточку")
            seen.setdefault(k, c)

def support_hint(pr: bl.Project, c) -> None:
    """BL051: карточка Support — сценарий поддержки, а не работа команды над проектом."""
    if c.layer != "support":
        return
    text = f"{c.title} {c.lead}"
    if PROJECT_WORK.search(text):
        pr.warn(c.rel, c.off, "BL051", f"{c.id}: в Support — проектная работа («{PROJECT_WORK.search(text).group(0)}»): это задача «Что делаем» или подзадача по зоне, не карточка")
    elif not SUPPORT_SIGN.search(text):
        pr.warn(c.rel, c.off, "BL051", f"{c.id}: Support — поддержка в нештатной ситуации (обращение, возврат, модерация, ручная обработка); внешняя система или канал — backstage")

def check(pr: bl.Project, source: Path | None, no_source: bool, explicit: bool = False) -> None:
    # --- ADR и Системные требования -------------------------------------------------------------
    check_adr(pr)
    # --- контроль стыковочных работ -----------------------------------------------------------
    check_seams(pr)
    # --- план релиза / Delivery ----------------------------------------------------------------
    check_release(pr)
    # --- Roadmap: сроки по неделям и спринтам --------------------------------------------------
    check_roadmap(pr)
    # --- риски исполнения: стык BE+FE, DevOps, интеграция систем --------------------------------
    check_risks(pr)

    # --- полнота и связность -----------------------------------------------------------------
    if pr.story:
        for st in pr.story.stages:
            if not any(t.stage == st.id for t in pr.tasks):
                pr.warn(pr.story_doc.rel, st.line + pr.story_doc.off, "BL020", f"этап {st.id} «{st.name}» без задач — что на нём делают команды?")
        employee_hint(pr)
    # эпик → история → подзадачи по зонам: история, в работе которой две команды и больше, без подзадач
    # не скажет техлидам, кто что делает; история в одном контуре — двухуровневая, подзадачи не нужны
    for t in pr.tasks:
        subs = [z for z in pr.subtasks if z.parent == t.id]
        teams = ({t.team} | {c.team for c in pr.cards if c.parent == t.id} | {z.team for z in subs}) - {"?", ""}
        if len(teams) > 1 and not subs:
            names = {x.id: x.name for x in pr.teams}
            pr.warn(t.rel, 1, "BL044", f"{t.id}: в работе {len(teams)} команды ({', '.join(names.get(x, x) for x in sorted(teams))}), а подзадач по зонам нет — кто что делает?")
    # триггеры: старт пути каждого персонажа — событие на своём этапе
    if pr.story and pr.map_doc:
        pids, sids = {p.id for p in pr.story.personas}, {s.id for s in pr.story.stages}
        for tg in pr.triggers:
            if tg.persona not in pids or tg.stage not in sids:
                pr.err(pr.map_doc.rel, tg.line, "BL049", f"триггер «{tg.text}»: персонаж {tg.persona} и этап {tg.stage} — ID из «Истории»")
        for p in pr.story.personas:
            if any(s.kind == "step" for s in pr.story.steps_of(p.id)) and not any(t.persona == p.id for t in pr.triggers):
                pr.warn(pr.map_doc.rel, 1, "BL050", f"у персонажа {p.id} нет триггера — с какого события начинается его путь? («## Триггеры» плана)")
    # формат зон: Design — одна точка касания на задачу; данных BE нет в хранилище — нужна DBA
    scr_doc = {k.lower() for k, d in pr.docs.items() for sd in pr.screens.values() if sd.path == d.path}
    for z in pr.subtasks:
        if z.zone == "Design":
            n = len({str(d).split()[0].lower() for d in z.docs} & scr_doc)
            if n != 1:
                pr.warn(z.rel, 1, "BL048", f"{z.id}: Design — {'ни одного экрана' if not n else f'{n} экрана'}; одна точка касания клиента — одна задача (экраны: F3)")
        if z.zone == "BE" and re.search(r"нет в хранилище", z.sections.get("Данные", (0, ""))[1], re.I) \
                and not any(x.zone == "DBA" and x.parent == z.parent for x in pr.subtasks):
            pr.warn(z.rel, 1, "BL048", f"{z.id}: данных «нет в хранилище», а подзадачи DBA в истории {z.parent} нет — кто доработает схему?")
    by_doc: dict = {}
    for t in pr.tasks:
        for d in t.docs:
            by_doc.setdefault(str(d).split()[0].lower(), []).append(t)
    doc_sid = {k.lower(): sid for k, d in pr.docs.items() for sid, sd in pr.screens.items() if sd.path == d.path}
    for k, ts in sorted(by_doc.items()):
        teams = {t.team for t in ts} - {"?"}
        if k in doc_sid and len(ts) > 1 and len(teams) > 1:
            pr.warn(ts[1].rel, 1, "BL045", f"экран {doc_sid[k]} делают {', '.join(t.id for t in ts)} разных команд — это один результат: одна история, их работа — подзадачи по зонам")
    for t in pr.tasks:
        if not t.prio and not any(str(x).lower().startswith("moscow:") for x in t.labels):
            pr.warn(t.rel, 1, "BL046", f"{t.id}: нет приоритета — must, should или would (would — за линией Out of scope)")
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
        support_hint(pr, c)
        regular_hint(pr, c)
    teamless(pr)
    # экран → задачи «Исполнения»: documentation задачи или её карточки ссылается на документ экрана
    doc_of = {d.path: k.lower() for k, d in pr.docs.items()}
    used_docs = {str(x).split()[0].lower() for t in pr.tasks + pr.cards for x in t.docs}
    for sid, sd in sorted(pr.screens.items()):
        k = doc_of.get(sd.path, "")
        if k and k not in used_docs:
            pr.warn(sd.rel, 1, "BL042", f"экран {sid}: ни одна задача не ссылается на {k} — панель «Исполнение» экрана пуста")
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

RISK_TITLE = {"befe": "стык BE+FE", "devops": "DevOps", "integration": "интеграция"}

def check_risks(pr: bl.Project) -> None:
    """Риски исполнения: «История» — история карты (RK003). Каждый кандидат из данных карты
    (bl.auto_risks) записан в документ с митигацией, владельцем и статусом — RK005."""
    rk = pr.risks
    found = bl.auto_risks(pr)
    rel = rk.doc.rel if rk and rk.doc else (pr.map_doc.rel if pr.map_doc else "")
    if rk and rk.doc:
        stories = {t.id for t in pr.tasks}
        for r in rk.items:
            if r.story not in stories:
                pr.err(rel, r.line, "RK003", f"{r.id}: истории {r.story} на карте нет")
    have = {(r.story, r.kind) for r in (rk.items if rk else [])}
    for sid, kind in found:
        if (sid, kind) not in have:
            pr.warn(rel, 1, "RK005", f"{sid}: риск «{RISK_TITLE[kind]}» по данным карты не записан в «Риски исполнения» — митигация, владелец, согласование с PO")

def check_roadmap(pr: bl.Project) -> None:
    """Roadmap: строки — истории и подзадачи карты (RM003). Полнота и порядок — предупреждения RM005:
    каждая работа в плане; у кроссфункциональной истории в плане подзадачи, а не она сама (у них свои
    исполнители); работа не начинается раньше, чем кончится её зависимость (dependencies Backlog.md)."""
    rm = pr.roadmap
    if rm is None or rm.doc is None:
        return
    rel = rm.doc.rel
    stories = {t.id: t for t in pr.tasks}
    subs = {z.id: z for z in pr.subtasks}
    plan = {i.id: i for i in rm.items}
    for i in rm.items:
        if i.id not in stories and i.id not in subs:
            pr.err(rel, i.line, "RM003", f"{i.id}: в Roadmap — история или подзадача карты, такой нет")
    for t in pr.tasks:
        mine = [z for z in pr.subtasks if z.parent == t.id]
        if mine:
            if t.id in plan:
                pr.warn(rel, plan[t.id].line, "RM005", f"{t.id}: у истории подзадачи по зонам — в план ставь их, у них свои исполнители и сроки")
            for z in mine:
                if z.id not in plan and t.prio != "would":
                    pr.warn(rel, 1, "RM005", f"{z.id} ({z.zone}) не в Roadmap — когда её делают?")
        elif t.id not in plan and t.prio != "would":
            pr.warn(rel, 1, "RM005", f"{t.id} «{t.title}» не в Roadmap — когда её делают?")
    for i in rm.items:
        w = stories.get(i.id) or subs.get(i.id)
        if not w:
            continue
        for dep in [str(x).upper() for x in (w.fm.get("dependencies") or [])]:
            d = plan.get(dep)
            if d and i.start <= d.end:
                pr.warn(rel, i.line, "RM005", f"{i.id} начинается на неделе {i.start}, а его зависимость {dep} кончается на неделе {d.end}")

def check_c4(pr: bl.Project, a) -> None:
    """C4 L3 ADR: компоненты и потоки. Ссылки — ошибки AR006: контур — команда из «Команд»
    («—» у человека, «?» — не определён), задачи — на карте, потоки — между компонентами,
    контракт — из «Решения TO-BE». Полнота — предупреждения AR007: без неё схема не отвечает,
    кто что меняет и где идут данные."""
    rel = a.doc.rel
    if not a.components:
        pr.warn(rel, 1, "AR007", "нет C4 L3 («## Компоненты» и «## Потоки») — техлид не увидит, какие компоненты участвуют и как идут данные")
        return
    teams = {t.id for t in pr.teams}
    work = {t.id.upper() for t in pr.tasks + pr.cards + pr.subtasks}
    comps = {c.id: c for c in a.components}
    for c in a.components:
        if c.kind == "человек" and c.team in bl.EMPTY_CELL:
            pass
        elif c.team not in teams and c.team != "?":
            pr.err(rel, c.line, "AR006", f"{c.id}: контур «{c.team}» — ID команды из «Команд» ({', '.join(sorted(teams))}), «?» — не определён")
        for t in c.tasks:
            if t not in work:
                pr.err(rel, c.line, "AR006", f"{c.id}: задачи {t} на карте нет")
        if c.change != "без изменений" and not c.tasks:
            pr.warn(rel, c.line, "AR007", f"{c.id} «{c.name}»: {c.change}, а задачи нет — кто и где это делает?")
    decided = {d.contract.strip().lower() for d in a.decisions}
    for f in a.flows:
        for x in (f.src, f.dst):
            if x not in comps:
                pr.err(rel, f.line, "AR006", f"поток {f.src} → {f.dst}: компонента {x} нет в «Компонентах»")
        if f.contract not in bl.EMPTY_CELL and f.contract.strip().lower() not in decided:
            pr.err(rel, f.line, "AR006", f"поток {f.src} → {f.dst}: контракт «{f.contract}» — из «Решения TO-BE» или «—»")
    linked = {x for f in a.flows for x in (f.src, f.dst)}
    for c in a.components:
        if c.id not in linked:
            pr.warn(rel, c.line, "AR007", f"{c.id} «{c.name}»: ни одного потока — с кем он обменивается данными?")
    on_flows = {f.contract.strip().lower() for f in a.flows}
    for d in a.decisions:
        if d.contract.strip().lower() not in on_flows:
            pr.warn(rel, d.line, "AR007", f"контракт «{d.contract}» решён, но ни один поток C4 по нему не идёт")

def check_adr(pr: bl.Project) -> None:
    """Смысл этапа «ADR и Системные требования»: ≥2 вариантов и явный выбор TO-BE, узкие места
    по нагрузке/надёжности, компромиссы по трём осям, контракты «Системных требований» совпадают
    с решением ADR и отвечают на три вопроса системной аналитики. Условие включения этапа —
    на карте есть карточки слоя Technology: работа затрагивает устройство систем."""
    # условие включения: слой Technology на карте — работа режется по системам; документы
    # «ADR»/«Системные требования» создаются только для таких инициатив, для остальных их нет
    tech_cards = [c for c in pr.cards if c.layer == "technology"]
    if pr.adr is None and pr.sysreq is None and tech_cards:
        pr.warn(pr.map_doc.rel if pr.map_doc else "", 1, "AR005",
                f"на карте {len(tech_cards)} карточек слоя Technology, а документов «ADR»/«Системные требования» нет — "
                "как реализовывать работу, никто не выбрал; если устройство систем эта работа не трогает, ничего не делай")
    a, s = pr.adr, pr.sysreq
    if a is not None and a.doc is not None:
        doc = a.doc
        # выбор: вариантов ≥2 и решение ссылается на один из них
        if len(a.options) < 2:
            pr.err(doc.rel, 1, "AR003",
                   f"вариантов {len(a.options)} — ADR выбирает между вариантами, нужно не меньше двух")
        vids = {o.id for o in a.options}
        for d in a.decisions:
            if d.id not in vids:
                pr.err(doc.rel, d.line, "AR003", f"решение «{d.id}» — ID варианта из «Вариантов» (V1…), а не «{d.id}»")
        if a.options and not a.decisions:
            pr.err(doc.rel, 1, "AR003", "нет решения TO-BE — выбери вариант и обоснуй («## Решение TO-BE»)")
        # у невыбранных вариантов — почему нет; у выбранного — почему да (в «Решении»)
        chosen = {d.id for d in a.decisions}
        for o in a.options:
            if o.id not in chosen and o.why_not.strip().lower() in ("", "—", "-", "–", "выбран"):
                pr.err(doc.rel, 1, "AR003", f"{o.id}: «Почему нет» — явное обоснование отклонения варианта")
        # узкие места и компромиссы — не опция
        if not a.bottlenecks:
            pr.warn(doc.rel, 1, "AR005", "нет узких мест по нагрузке и надёжности — где TO-BE просядет под нагрузкой?")
        if not a.compromises:
            pr.warn(doc.rel, 1, "AR005", "нет компромиссов — надёжность vs скорость реализации vs соответствие требованиям платят друг другом, запиши чем")
        # диаграмма AS-IS/TO-BE
        if not a.diagram:
            pr.warn(doc.rel, 1, "AR005", "нет ADR-диаграммы AS-IS/TO-BE (mermaid-блок в «## Диаграмма AS-IS/TO-BE»)")
        check_c4(pr, a)
        # контракты «Системных требований» совпадают с решением ADR
        if s is not None and s.doc is not None and a.decisions:
            decided = {d.contract.strip().lower() for d in a.decisions}
            for c in s.contracts:
                if c.contract.strip().lower() not in decided:
                    pr.err(s.doc.rel, c.line, "AR003",
                           f"{c.id}: контракт «{c.contract}» — из «Решения TO-BE» ADR, такого контракта там нет")
    if s is not None and s.doc is not None:
        doc = s.doc
        decided = {d.contract.strip().lower() for d in a.decisions} if (a is not None and a.decisions) else set()
        if a is not None and a.decisions:
            listed = {c.contract.strip().lower() for c in s.contracts}
            for d in a.decisions:
                if d.contract.strip().lower() not in listed:
                    pr.err(doc.rel, 1, "AR003",
                           f"контракт «{d.contract}» решён в ADR, но его нет в «Контрактах» — где данные, источники и преобразования?")
        for c in s.contracts:
            if not (c.data.strip() and c.source.strip() and c.transform.strip()):
                pr.err(doc.rel, c.line, "AR003",
                       f"{c.id}: три вопроса контракта — «Данные контракту», «Источник параметров», «Преобразования» — пустых быть не должно")
        # открытые вопросы дублируются в «Вопросы» «Карты»
        if pr.map_doc is not None:
            kq = {(q.to.strip(), q.text.strip()) for q in pr.questions}
            for q in s.questions:
                if q.open and (q.to.strip(), q.text.strip()) not in kq:
                    pr.warn(doc.rel, q.line, "AR005",
                            f"{q.id}: нет в «Вопросах» «Карты» — продублируй («Где» — {next((c.id for c in s.contracts), 'K1')}), иначе ответ потеряется")

def check_seams(pr: bl.Project) -> None:
    """Смысл документа «Стыки»: участники из «Команд», обязательства и контракты привязаны
    к стыкам, у каждого стыка есть обязательства; условие включения этапа — ≥2 команд на карте."""
    # условие включения: этап нужен, когда работа режется между командами; документ «Стыки»
    # создаётся только для таких инициатив — для задач без стыков его нет, и это не ошибка
    teams_of_tasks = {t.team for t in pr.tasks if t.team and t.team != "?"}
    if pr.seams is None and len(teams_of_tasks) >= 2:
        pr.warn(pr.map_doc.rel if pr.map_doc else "", 1, "SM005",
                f"на карте {len(teams_of_tasks)} команд, а документа «Стыки» нет — про контроль стыковочных "
                "работ никто не договорился; если стыков в этой работе нет, ничего не делай")
    sm = pr.seams
    if sm is None or sm.doc is None:
        return
    doc = sm.doc
    team_ids = {t.id for t in pr.teams}

    def team_or_stub(ln: int, sid: str, val: str, label: str) -> None:
        v = val.strip()
        if bl.TEAM_OR_STUB.match(v):
            if v not in team_ids and not v.startswith("[УТОЧНИТЬ"):
                pr.err(doc.rel, ln, "SM003", f"{sid}: {label} «{v}» — ID команды из «Команд» или [УТОЧНИТЬ у кого]")
        else:
            pr.err(doc.rel, ln, "SM003", f"{sid}: {label} «{v}» — ID команды из «Команд» (латиницей-слагом) или [УТОЧНИТЬ …]")

    seam_ids = {s.id for s in sm.seams}
    for s in sm.seams:
        team_or_stub(s.line, s.id, s.supplier, "поставщик")
        team_or_stub(s.line, s.id, s.consumer, "потребитель")
    for d in sm.deliveries:
        team_or_stub(d.line, d.id, d.who, "кто")
        team_or_stub(d.line, d.id, d.to, "кому")
    for c in sm.contracts:
        if c.seam not in seam_ids:
            pr.err(doc.rel, c.line, "SM003", f"контракт: стык «{c.seam}» — ID стыка из «Участников» (S1…)")
    # обязательства и контракты привязаны к стыкам: строка «Стык: S1» в «Что»/«Требование»,
    # «Кто»+«Кому» совпадают с участниками — заполняет apply плана, здесь проверяем
    seam_by_pair = {(s.supplier, s.consumer): s.id for s in sm.seams}
    for d in sm.deliveries:
        sid = seam_by_pair.get((d.who, d.to))
        d.seam = sid or ""
        if not sid:
            pr.err(doc.rel, d.line, "SM003",
                   f"{d.id}: «Кто» + «Кому» ({d.who} → {d.to}) не совпадают ни с одним стыком из «Участников»")
    covered = {d.seam for d in sm.deliveries if d.seam}
    for s in sm.seams:
        if s.id not in covered:
            pr.warn(doc.rel, s.line, "SM005", f"{s.id}: стык без обязательств — кто и что предоставляет по контракту?")
    contract_seams = {c.seam for c in sm.contracts}
    for s in sm.seams:
        if s.id not in contract_seams:
            pr.warn(doc.rel, s.line, "SM005", f"{s.id}: стык без строки контракта — что фиксируем на стыке ({s.kind})?")
    if sm.meta.get("status", "").lower() not in ("черновик", "согласован"):
        pr.warn(doc.rel, 1, "SM005", f"статус стыков «{sm.meta.get('status')}» — Черновик или Согласован")

def check_release(pr: bl.Project) -> None:
    """Смысл плана релиза: зависимости указывают на существующие шаги, ворота закрыты, статусы честные."""
    rel = pr.release
    if rel is None or rel.doc is None:
        return
    doc = rel.doc
    ids = {s.id for s in rel.steps}
    for s in rel.steps:
        for d in s.deps:
            if d.upper() not in ids:
                pr.err(doc.rel, s.line, "RL003", f"{s.id}: зависимости «{d}» — ID шага R1… из «Шагов»")
        if not s.deps and s.id != next((x.id for x in rel.steps if x.track == s.track), ""):
            pr.warn(doc.rel, s.line, "RL005", f"{s.id}: без зависимостей — с чего начинается шаг?")
    gates_by_from: dict[str, int] = {}
    for g in rel.gates:
        nxt = bl.RELEASE_TRACKS[bl.RELEASE_TRACKS.index(g.frm) + 1]
        if not rel.by_track(g.frm):
            pr.err(doc.rel, g.line, "RL003", f"ворота {g.frm.upper()} → {nxt.upper()}: на дорожке {g.frm.upper()} нет шагов")
        gates_by_from[g.frm] = gates_by_from.get(g.frm, 0) + 1
    for frm, n in gates_by_from.items():
        if n > 1:
            nxt = bl.RELEASE_TRACKS[bl.RELEASE_TRACKS.index(frm) + 1]
            pr.err(doc.rel, rel.gates[0].line if n else 1, "RL003", f"ворот после {frm.upper()} — {n}: переход на {nxt.upper()} один")
    if rel.by_track("stage") and "dev" not in gates_by_from:
        pr.warn(doc.rel, 1, "RL005", "есть дорожка STAGE, но нет ворот dev → stage — кто утверждает переход?")
    if rel.by_track("prod") and "stage" not in gates_by_from:
        pr.warn(doc.rel, 1, "RL005", "есть дорожка PROD, но нет ворот stage → prod — кто утверждает переход?")
    if rel.meta.get("status", "").lower() not in ("черновик", "согласован"):
        pr.warn(doc.rel, 1, "RL005", f"статус плана релиза «{rel.meta.get('status')}» — Черновик или Согласован")

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
    else:
        check_adr(pr)   # «документы этапа потеряны» не должно глохнуть от чужих ошибок разбора
    return pr

# как исправить — по строке на код: печатается под отчётом (`--hints`, ./blueprint.py next и apply)
HINTS = {
    "AR001": "«ADR»: паспорт <!-- bft-adr --> (epic_slug, version, revised, status: Черновик/Предложено/Принято/Отклонено/Заменено), «## Контекст» | Участник | Роль в решении |, «## AS-IS» текстом, «## Варианты» | ID | Вариант | Надёжность | Скорость реализации | Соответствие требованиям | Почему нет |, «## Решение TO-BE» | ID | Контракт | Суть решения | Обоснование |, «## Узкие места» | ID | Узкое место | Тип | Нагрузка | Риск | Прощупывание |, «## Компромиссы» | ID | Компромисс | Надёжность | Скорость реализации | Соответствие требованиям | Чем платим |, «## Диаграмма AS-IS/TO-BE» mermaid; «Системные требования»: паспорт <!-- bft-sysreq -->, «## Контракты» | ID | Контракт | Потребитель | Данные контракту | Источник параметров | Преобразования |, «## AS-IS» | ID | Как устроено сейчас | Что меняется |, «## Изменения» | ID | Изменение | Причина |, «## Открытые вопросы» | ID | Кому | Вопрос | Ответ |",
    "AR002": "документы «ADR» и «Системные требования» — по одному: с паспортом <!-- bft-adr --> / <!-- bft-sysreq --> в проекте один",
    "AR003": "ADR: вариантов ≥2, у каждого явное «Почему нет», решение TO-BE ссылается на ID варианта; узкие места и компромиссы по трём осям «надёжность vs скорость реализации vs соответствие требованиям»; контракты «Системных требований» — те же, что в «Решении TO-BE», и по каждому три вопроса: данные, источники, преобразования",
    "AR006": "C4: «Контур» — ID команды из «Команд» («—» у человека, «?» — не определён); «Задачи» — ID с карты; «От»/«К» — ID из «Компонентов»; «Контракт» — из «Решения TO-BE» или «—»",
    "AR007": "C4 L3: «## Компоненты» | ID | Компонент | Контекст | Контур | Тип | Изменение | Задачи | и «## Потоки» | От | К | Данные | Способ | Контракт |; у меняемого компонента — задача, у каждого — поток, у каждого контракта TO-BE — поток",
    "AR005": "нет узких мест/компромиссов/диаграммы — допиши разделы; слой Technology на карте без документов «ADR»/«Системные требования» — этап не проводился, создай документы или оставь как есть, если устройство систем не трогается",
    "SM001": "«Стыки»: паспорт <!-- bft-seams --> (epic_slug, version, revised, status) и таблицы «## Участники» | ID | Стык | Поставщик | Потребитель | Ответственный за контракт |, «## Обязательства» | ID | Кто | Что | Кому | Срок | Формат/место |, «## Контракты» | Стык | Аспект | Требование к фиксации |, «## Контрольные точки» | ID | Точка | Когда | Что проверяется | Кто проводит |, «## Риски» | ID | Риск | Следствие | Владелец | Митигация |",
    "SM002": "документ «Стыки» один: с паспортом <!-- bft-seams --> в проекте один",
    "SM003": "участники стыков и обязательств — ID команд из «Команд» (латиницей-слагом) или [УТОЧНИТЬ у кого]; «Кто» + «Кому» обязательства — пара поставщик → потребитель одного из стыков; контракт — ID стыка из «Участников»",
    "SM005": "стык без обязательств или контракта — допиши строки; команд 2 и больше без документа «Стыки» — этап «Контроль стыковочных работ» не проводился, создай документ или оставь как есть, если стыков нет",
    "BL002": "«Карта»: паспорт <!-- bft-map --> в начале и заголовок «# Карта: …» — так их создаёт bft-backlog-init.py, не трогай",
    "BL003": "«История» с ошибками ST: исправь <epic>-story.md (bft-story-lint.py) и пересоздай проект или правь документ «История»",
    "BL004": "таблицы «## Команды» (| ID | Команда |, ID латиницей) и «## Вопросы» (| ID | Кому | Вопрос | Где | Тип | Ответ |) в плане",
    "BL006": "задача: «этап:» — буква этапа истории; «вид:» — создать | доработать | используем | уточнить; «команда:» — ID из «Команд»",
    "BL007": "задача: первая строка — зачем; строка «Требования БФТ: ФТ-1, ИТ-2»; ### ASIS, ### GAP, ### TOBE, ### HowToDemo (нумерованно); ### Критерии приемки — хотя бы один пункт",
    "BL008": "карточка: ID вида BP-3.1 под задачей BP-3; «слой:» — employee | technology | backstage | support; «этап:» как у истории",
    "BL009": "карточка: ### UserStory, ### JobStory, ### Параметры (- **Вход:** …, - **Управление:** …, - **Выход:** …, - **Механизм:** …), ### Процесс (- Участник: действие), ### HowToDemo; у Backstage — только ### Параметры, ### Процесс и по желанию ### Данные; (BP-8.1) в параметрах — только на карточки",
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
    "BL043": "подзадача: `./backlog.py task create … -p BP-5 -l \"stage:B,zone:FE\" -a @vit` — родитель история, этап её, зона из PO, SA, Design, FE, BE, QA, DevOps, Delivery; в плане — блок «## BP-5.2 · …» с «зона: FE»",
    "BL044": "кроссфункциональная история: под ней подзадачи по зонам — «## BP-5.2 · …» с «зона: FE» и «команда: vit»; история в одном контуре остаётся без подзадач",
    "BL045": "одно и то же делают истории разных команд: слей их в одну историю по результату, работу каждой команды — подзадачей по зоне",
    "BL047": "подзадача: требования БФТ перенеси в историю; разделы по зоне — Design: ### UserStory, ### JobStory, ### UserFlow; BE: ### ASIS, ### GAP, ### TOBE, ### Данные; DBA, FE, DevOps: ### ASIS, ### GAP, ### TOBE; у PO, BA, SA, ADR, Design, QA, Delivery — «### Критерии приемки» (согласования, вопросы, решения, что на экране)",
    "BL048": "Design: одна точка касания клиента — одна задача, «экраны: F3»; BE с данными «нет в хранилище» — подзадача DBA в той же истории",
    "BL049": "«## Триггеры» плана: | Персонаж | Триггер | Этап |, персонаж — ID из «Персонажей» «Истории», этап — ID этапа, где событие происходит",
    "BL050": "в плане — «## Триггеры»: по строке на персонажа, событие старта его пути: «Гость купил билет на оффлайн-мероприятие»",
    "BL046": "приоритет истории: в плане строка «приоритет: must | should | would», в проекте — метка moscow:must; would — за линией Out of scope, не коммитмент заказчику",
    "BL042": "экран делает задача: строка «экраны: F3» в задаче (и карточке) плана, в проекте — ./backlog.py task edit BP-N --doc doc-N",
    "BL054": "«Как это работает» — целевая картинка глазами пользователя: только компоненты и бизнес-процессы, без команд (не ставь исполнителя карточке). Одно событие сервиса — одна карточка; работы команд над ним — задачи «Что делаем» и подзадачи по зонам",
    "BL053": "«Как это работает» — только регулярный процесс работающего сервиса. Разовое (переключить, переверстать, настроить, перенести) — задача «Что делаем» или подзадача по зоне. В Backstage участники и «Механизм» — компоненты: «Сервис проверки билетов», «Триггеры касаний», не «TeamA» и не «Маркетинг»",
    "BL052": "Backstage: суть одной фразой, ### Параметры, ### Процесс и, если процессу нужны данные, ### Данные — «- Статус билета — Acme Tickets (BP-15.1)»; UserStory, JobStory и HowToDemo убери — их несёт карточка, которую видит человек",
    "BL051": "Support — регулярная поддержка, когда человек застрял: «Поддержка разбирает обращение по возврату», «Обработка заявки в ручном режиме». Внешний канал или система — «слой: backstage»; макеты, настройка, подготовка — задача «Что делаем» или подзадача по зоне",
    "BL041": "сотрудник на виду у клиента (официант при госте, мастер-приёмщик при клиенте) — «слой: employee»; его планшет или сканер — в этой же карточке, не отдельной technology",
    "BL040": "участник процесса — система с именем из БФТ или «Механизма»: «Реестр продаж», «Приложение-сканер», а не «Система»",
    "BL035": "один кандидат — это исполнитель: «команда: id»; сомнение — строкой «Вопросов»",
    "BL033": "UserStory пишется от лица того, кто пользуется результатом карточки (гость, официант, контент-менеджер, PO), а не команды, которая её делает",
    "SN001": "файл экрана — plan/screens/<ID>.md, ID из таблицы «Экраны» «Истории»",
    "RK001": "«Риски исполнения»: паспорт <!-- bft-risks --> (epic_slug, version, revised, status), «## Риски» | ID | История | Тип | Риск | Митигация | Владелец | Статус |; ID X1…, тип — стык BE+FE, DevOps, интеграция, другое; статус — на согласовании, согласован, снят",
    "RK002": "«Риски исполнения» одни: документ с <!-- bft-risks --> в проекте один",
    "RK003": "«История» риска — ID истории карты (BP-5), не подзадачи",
    "RK005": "в плане — «## Риски исполнения»: строка на риск истории с митигацией, владельцем и статусом «на согласовании», пока PO не согласовал",
    "RM001": "Roadmap: паспорт <!-- bft-roadmap --> (epic_slug, version, revised, status, start — понедельник ГГГГ-ММ-ДД, sprint_weeks — 1 или 2), «## План» | ID | Неделя с | Неделя по |, недели с 1, не больше 6 спринтов",
    "RM002": "Roadmap один: документ с <!-- bft-roadmap --> в проекте один",
    "RM003": "строка Roadmap — ID истории (BP-5) или подзадачи по зоне (BP-5.3); карточки «Как это работает» в план не ставят",
    "RM005": "в Roadmap — каждая история; у кроссфункциональной — её подзадачи; работа начинается после конца зависимости",
    "RL001": "«План релиза»: паспорт <!-- bft-release --> (epic_slug, version, revised, status), «## Шаги» | ID | Стенд | Что сделать | Ответственный | Тип | Зависимости | Статус | Критерий готовности |, «## Ворота» | Ворота | Кто утверждает | Критерий перехода |",
    "RL002": "план релиза один: документ с <!-- bft-release --> в проекте один",
    "RL003": "шаг: зависимости — ID шагов R1… из «Шагов»; ворота — по одному на переход dev → stage и stage → prod",
    "RL005": "дорожка без ворот: кто утверждает переход на следующий стенд? шаг без зависимостей: с чего начинается?",
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
    print(f"{name}: {len(pr.tasks)} задач, " + (f"{len(pr.subtasks)} подзадач по зонам, " if pr.subtasks else "") + f"{len(pr.cards)} карточек «Как это работает», {len(pr.screens)} экранов с требованиями, "
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

if __name__ == "__main__":
    sys.exit(main())

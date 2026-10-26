

#!/usr/bin/env python3
"""Service Blueprint в проекте Backlog.md — разбор и проверка формы.

Карта инициативы живёт в обычном проекте Backlog.md (`backlog init`): задачи, подзадачи и документы —
markdown-файлы, которыми ИИ-агент управляет через CLI `backlog`. Отсюда страница карты собирается
детерминированно (`bft-backlog-build.py`).

  backlog/config.yml                         task_prefix — префикс ID (bp → BP-12)
  backlog/docs/doc-… - Карта.md               паспорт <!-- bft-map … -->, «Команды», «Вопросы»
  backlog/docs/doc-… - История.md             история через экраны <!-- bft-story … -->
  backlog/docs/doc-… - ADR.md                 этап «ADR и Системные требования» <!-- bft-adr … -->:
                                             контекст, AS-IS, варианты, решение TO-BE, узкие места, компромиссы
  backlog/docs/doc-… - Системные требования.md  та же ступень, системная аналитика <!-- bft-sysreq … -->:
                                             контракты → параметры → источники → преобразования → AS-IS → изменения
  backlog/docs/doc-… - Стыки.md               этап «Контроль стыковочных работ» <!-- bft-seams … -->:
                                             участники стыков, обязательства, контракты, точки, риски
  backlog/docs/doc-… - План-релиза.md         этап «План релиза / Delivery» <!-- bft-release … -->:
                                             дорожки DEV/STAGE/PROD, шаги и ворота между стендами
  backlog/docs/screens/doc-… - F3 · ….md      требования к экрану для дизайнера
  backlog/tasks/bp-12 - ….md                  «Что делаем»: задача команды — постановка для техлида
  backlog/tasks/bp-12.1 - ….md                «Как это работает»: подзадача — техническая карточка

На карте — задачи с меткой `stage:<этап>`. Остальные задачи проекта (план работ, баги) карте не мешают.

Задача «Что делаем»: исполнитель — команда (`@teama`) или метки `кандидат:<команда>`, метки этапа
и вида (создать, доработать, используем, уточнить). Описание: зачем; «Требования БФТ: …»;
### ASIS, GAP, TOBE, HowToDemo, Дополнительно. Чеклист приемки — Acceptance Criteria.
Исполнение — references (JIRA, Confluence) и Implementation Notes.

Карточка «Как это работает»: подзадача задачи «Что делаем», метки `layer:<слой>` и `stage:<этап>`.
Подзадача по зоне: подзадача истории (задачи «Что делаем»), метки `zone:<зона>` и `stage:<этап>`,
исполнитель — команда зоны. Эпик (БФТ) → история → подзадачи по зонам; история в одном контуре —
без подзадач.
Описание: суть одной-двумя фразами; ### UserStory «Как …, я хочу …, чтобы …»; ### JobStory — ситуации
«Когда …, хочу …, чтобы …»; ### Параметры (вход, управление, выход, механизм); ### Процесс — шаги
«Участник: действие» и развилки «? вопрос» с ветками «ответ → Участник: действие»; ### BPMN — mermaid,
собирается из процесса; ### HowToDemo. Ссылки — documentation, references.
Ссылка `(BP-8.1)` во входе или управлении — откуда пришло, в выходе — куда уходит: это стрелки карты.

Стандарт — `resources/backlog_rules.md`. Только стандартная библиотека.
"""

from __future__ import annotations

import json

import re

import sys

from dataclasses import dataclass, field

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bft_blueprint as bb  # noqa: E402

import bft_story as bs  # noqa: E402

import bft_screens as bsn  # noqa: E402

FINAL = bs.FINAL

KINDS = ("создать", "доработать", "используем", "уточнить")

LAYERS = ("employee", "technology", "backstage", "support")

# функциональные зоны подзадач истории: кто делает свою часть результата (в JIRA — подзадача с исполнителем)
ZONES = ("PO", "SA", "Design", "FE", "BE", "QA", "DevOps", "Delivery")

# Этап «План релиза / Delivery»: дорожки-стенды, шаги, ворота между стендами.
RELEASE_META = ("epic_slug", "version", "revised", "status")

RELEASE_TRACKS = ("dev", "stage", "prod")

RELEASE_TRACK_TITLE = {"dev": "DEV", "stage": "STAGE", "prod": "PROD"}

RELEASE_STEP_TYPES = ("согласование", "задача devops", "предоставление доступа или данных",
                      "утверждение", "проверка")

RELEASE_STATUSES = ("не начат", "в работе", "готово", "требует ответа")

RELEASE_GATE_KEYS = ("с", "кто", "критерий")

GATE_HEADER = ("Ворота", "Кто утверждает", "Критерий перехода")

STEP_HEADER = ("ID", "Стенд", "Что сделать", "Ответственный", "Тип", "Зависимости",
               "Статус", "Критерий готовности")

GATE_ID = re.compile(r"^G-?(?P<num>\d+)$", re.I)

STEP_ID = re.compile(r"^R-?(?P<num>\d+)$", re.I)

BRIEF = ("ASIS", "GAP", "TOBE", "HowToDemo", "Дополнительно")

BRIEF_OPTIONAL = {"Дополнительно"}

CARD = ("UserStory", "JobStory", "Параметры", "Процесс", "BPMN", "HowToDemo")

CARD_REQUIRED = ("UserStory", "JobStory", "Параметры", "Процесс", "HowToDemo")

# участники процесса, которые строят сервис, а не работают в нём: такая карточка — о проекте, а не о сервисе
PROJECT_ROLE = re.compile(r"^(?:PO|СА|PM|PO .+|СА .+|продакт.*|владелец продукта|(?:системный |бизнес-)?аналитик|разработ\w*|команда.*|архитектор)$", re.I)

MAX_STEPS = 12          # шагов процесса — дальше схема не читается, карточку делят на две

MAX_LANES = 6

PARAM_KEYS = {"вход": "in", "входы": "in", "управление": "ctl", "выход": "out", "выходы": "out",
              "механизм": "mech", "механизмы": "mech"}

PARAM_NAME = {"in": "Вход", "ctl": "Управление", "out": "Выход", "mech": "Механизм"}

MAP_META = ("epic_slug", "source_doc", "source_stage", "source_rev", "version", "revised", "status")

TEAMS_HEADER = ("ID", "Команда")

TEAMS_HEADER_LEAD = ("ID", "Команда", "Техлид")      # техлид — исполнитель историй контура

QUESTIONS_HEADER = ("ID", "Кому", "Вопрос", "Где", "Тип", "Ответ")

Q_TYPES = ("вопрос", "блокер")

MAX_TASK = 80

MAX_CARD = 90

# Этап «ADR и Системные требования»: после раскладки задач — как их реализовать. Два документа проекта:
# «ADR» (<!-- bft-adr … --> — системный дизайн: контекст, ландшафт AS-IS, варианты, решение TO-BE,
# узкие места, компромиссы, диаграмма AS-IS/TO-BE mermaid) и «Системные требования»
# (<!-- bft-sysreq … --> — системная аналитика: контракты → параметры → источники → преобразования
# → AS-IS → изменения → открытые вопросы). Включается, когда работа затрагивает устройство систем —
# на карте есть карточки слоя Technology (вход этапа: БФТ, «История», задачи и карточки карты).
ADR_META = ("epic_slug", "version", "revised", "status")

ADR_STATUSES = ("черновик", "предложено", "принято", "отклонено", "заменено")

ADR_CONTEXT_HEADER = ("Участник", "Роль в решении")            # кто и зачем участвует в решении

ADR_DECISION_HEADER = ("ID", "Контракт", "Суть решения", "Обоснование")

ADR_OPTION_HEADER = ("ID", "Вариант", "Надёжность", "Скорость реализации", "Соответствие требованиям", "Почему нет")

BOTTLENECK_HEADER = ("ID", "Узкое место", "Тип", "Нагрузка", "Риск", "Прощупывание")

COMPROMISE_HEADER = ("ID", "Компромисс", "Надёжность", "Скорость реализации", "Соответствие требованиям", "Чем платим")

VARIANT_ID = re.compile(r"^V-?(?P<num>\d+)$", re.I)

BOTTLENECK_ID = re.compile(r"^N-?(?P<num>\d+)$", re.I)

COMPROMISE_ID = re.compile(r"^C-?(?P<num>\d+)$", re.I)

# C4 L3 в ADR: компоненты и потоки данных между ними. Компонент живёт в контексте (система —
# граница C4) и в контуре ответственности (команда из «Команд»); «Задачи» — где на карте
# запланированы работы над ним. Схему страница рисует сама из этих двух таблиц.
C4_COMPONENT_HEADER = ("ID", "Компонент", "Контекст", "Контур", "Тип", "Изменение", "Задачи")

C4_FLOW_HEADER = ("От", "К", "Данные", "Способ", "Контракт")

COMPONENT_ID = re.compile(r"^M-?(?P<num>\d+)$", re.I)

C4_KINDS = ("человек", "интерфейс", "сервис", "хранилище", "очередь", "внешняя система")

C4_CHANGES = ("новый", "доработка", "без изменений")

EMPTY_CELL = ("", "—", "-", "–")

# Системные требования: три вопроса на КАЖДЫЙ контракт — (1) какие данные нужны контракту,
# (2) источник каждого параметра (система/сервис/поле/справочник), (3) какие преобразования
# над данными нужны для контрактов и бизнес-логики.
SYSREQ_META = ("epic_slug", "version", "revised", "status")

SYSREQ_STATUSES = ("черновик", "согласован")

CONTRACTS_HEADER = ("ID", "Контракт", "Потребитель", "Данные контракту", "Источник параметров", "Преобразования")

SYSREQ_ASIS_HEADER = ("ID", "Как устроено сейчас", "Что меняется")

SYSREQ_CHANGE_HEADER = ("ID", "Изменение", "Причина")

SYSREQ_Q_HEADER = ("ID", "Кому", "Вопрос", "Ответ")

CONTRACT_ID = re.compile(r"^K-?(?P<num>\d+)$", re.I)

SYSROW_ID = re.compile(r"^(?:A|I)-?(?P<num>\d+)$", re.I)

SYSQ_ID = re.compile(r"^Q-?(?P<num>\d+)$", re.I)

# ADR-контракт в «Системных требованиях» — имя латиницей-слагом или [УТОЧНИТЬ …]
SYS_CONTRACT_NAME = re.compile(r"^(?:[a-z][a-z0-9-]*|[А-Яа-яЁё][А-Яа-яЁё0-9 .,()-]*|\[УТОЧНИТЬ[^\]]*\])$")

# Этап «Контроль стыковочных работ»: участники стыков, обязательства «кто → что → кому → срок»,
# контракты по слоям (FE↔BE, BE↔BE, Infra), контрольные точки и риски. Документ проекта —
# «Стыки» (<!-- bft-seams … -->); включается, когда задача режется между командами/сервисами.
SEAMS_META = ("epic_slug", "version", "revised", "status")

SEAM_HEADER = ("ID", "Стык", "Поставщик", "Потребитель", "Ответственный за контракт")

SEAM_KINDS = ("fe-be", "be-be", "be-infra", "внешний")

DELIVERY_HEADER = ("ID", "Кто", "Что", "Кому", "Срок", "Формат/место")

SEAM_CONTRACT_HEADER = ("Стык", "Аспект", "Требование к фиксации")

CHECKPOINT_HEADER = ("ID", "Точка", "Когда", "Что проверяется", "Кто проводит")

RISK_HEADER = ("ID", "Риск", "Следствие", "Владелец", "Митигация")

SEAM_ID = re.compile(r"^S-?(?P<num>\d+)$", re.I)

DELIVERY_ID = re.compile(r"^D-?(?P<num>\d+)$", re.I)

CHECKPOINT_ID = re.compile(r"^K-?(?P<num>\d+)$", re.I)

RISK_ID = re.compile(r"^R-?(?P<num>\d+)$", re.I)

# «Кто»/«Кому» в матрице обязательств и «Поставщик»/«Потребитель» — ID команд из «Команд» или [УТОЧНИТЬ …]
TEAM_OR_STUB = re.compile(r"^(?:[a-z][a-z0-9-]*|\[УТОЧНИТЬ[^\]]*\])$")

TEAM_RE = re.compile(r"^[a-z][a-z0-9-]*$")

SCREEN_TITLE = re.compile(r"^([A-H]\d{1,2})\s*·\s*(.+)$")

SECTION_RE = re.compile(r"<!-- SECTION:([A-Z_]+):BEGIN -->\n?(.*?)\n?<!-- SECTION:\1:END -->", re.S)

LIST_RE = {k: re.compile(rf"<!-- {k}:BEGIN -->\n?(.*?)\n?<!-- {k}:END -->", re.S) for k in ("AC", "DOD")}

CHECK_ITEM = re.compile(r"^- \[([ xX])\] (?:#\d+ )?(.*)$")

REQS_LINE = re.compile(r"^Требования(?: БФТ)?\s*:\s*(.*)$")

STEP_RE = re.compile(r"^\d+\.\s+\S")

META_OPEN = re.compile(r"^<!--\s*(bft-map|bft-story|bft-adr|bft-sysreq|bft-seams|bft-release)\s*$")

MERMAID = re.compile(r"```mermaid\n(.*?)\n```", re.S)

@dataclass
class Item:
    """Значение параметра карточки: текст и ссылки на другие карточки."""
    text: str
    refs: list[str]

@dataclass
class Doc:
    id: str
    title: str
    path: Path
    rel: str
    meta: dict
    body: str
    off: int        # строк файла до тела

@dataclass
class BTask:
    id: str
    title: str
    path: Path
    rel: str
    fm: dict
    off: int                  # строка, с которой начинается описание
    desc: str = ""
    notes: str = ""
    ac: list = field(default_factory=list)       # [(сделано, текст)]
    labels: list = field(default_factory=list)
    parent: str = ""
    stage: str = ""
    layer: str = ""
    zone: str = ""            # функциональная зона подзадачи истории: FE, BE, Design…
    team: str = ""            # ID команды или «?»
    cand: str = ""
    kind: str = ""
    why: str = ""
    reqs: list = field(default_factory=list)
    lead: str = ""
    sections: dict = field(default_factory=dict)  # {раздел: (строка, текст)}
    params: dict = field(default_factory=dict)    # {in|ctl|out|mech: [Item]}
    mermaid: str = ""                             # блок BPMN в файле
    user_story: str = ""
    job_stories: list = field(default_factory=list)
    proc: list = field(default_factory=list)      # шаги процесса: {t: task|xor, …}

    @property
    def status(self) -> str:
        return self.fm.get("status", "")

    @property
    def refs(self) -> list:
        return self.fm.get("references") or []

    @property
    def docs(self) -> list:
        return self.fm.get("documentation") or []

    @property
    def ordinal(self) -> float:
        try:
            return float(self.fm.get("ordinal", "") or 1e9)
        except ValueError:
            return 1e9

@dataclass
class Team:
    id: str
    name: str
    line: int
    lead: str = ""            # техлид контура: исполнитель его историй

@dataclass
class Question:
    id: str
    to: str
    text: str
    where: str
    kind: str
    answer: str
    line: int

    @property
    def open(self) -> bool:
        return self.answer.strip() in bb.EMPTY

@dataclass
class Option:
    """Вариант реализации ADR: как выглядит по трём осям и почему не выбран (для TO-BE — почему да)."""
    id: str
    text: str
    reliability: str      # надёжность: высокая/средняя/низкая или оценка словами
    speed: str            # скорость реализации
    fit: str              # соответствие требованиям
    why_not: str          # почему нет (у выбранного — почему да)

@dataclass
class Decision:
    """Решение TO-BE по контракту: суть и обоснование."""
    id: str               # ID выбранного варианта V1…
    contract: str
    text: str
    why: str
    line: int

@dataclass
class Seam:
    """Стык: кто поставщик, кто потребитель и кто отвечает за контракт."""
    id: str
    kind: str                      # fe-be | be-be | be-infra | внешний
    supplier: str                  # ID команды из «Команд» или [УТОЧНИТЬ …]
    consumer: str
    owner: str                     # ответственный за контракт (роль/техлид; может быть [УТОЧНИТЬ …])
    line: int

@dataclass
class Delivery:
    """Обязательство стыка: кто, что и к какому сроку предоставляет кому."""
    id: str
    who: str                       # поставщик — ID команды или [УТОЧНИТЬ …]
    what: str                      # артефакт: API-спека, мок, окружение, доступы…
    to: str                        # потребитель — ID команды или [УТОЧНИТЬ …]
    when: str                      # срок: рабочие дни от старта / привязка к спринту / [УТОЧНИТЬ …]
    where: str                     # формат/место хранения
    seam: str = ""                 # ID стыка S1… (заполняет проверка смысла)
    line: int = 0

@dataclass
class ContractRow:
    """Строка контракта по слою стыка: аспект и требование к фиксации."""
    seam: str                      # ID стыка S1…
    aspect: str
    req: str
    line: int

@dataclass
class Checkpoint:
    """Контрольная точка стыка: что и когда проверяется, кто проводит."""
    id: str
    name: str
    when: str
    what: str
    who: str
    line: int

@dataclass
class Risk:
    """Риск стыка и его владелец."""
    id: str
    text: str
    effect: str
    owner: str
    mitigation: str
    line: int

@dataclass
class Bottleneck:
    """Узкое место TO-BE по нагрузке и надёжности."""
    id: str
    text: str
    kind: str             # нагрузка | надёжность | данные
    load: str             # оценка нагрузки: RPS, объём, пики
    risk: str
    probe: str            # как прощупать до релиза
    line: int

@dataclass
class Compromise:
    """Компромисс по трём осям: надёжность vs скорость реализации vs соответствие требованиям."""
    id: str
    text: str
    reliability: str      # что получили по оси
    speed: str
    fit: str
    cost: str             # чем платим
    line: int

@dataclass
class Component:
    """Компонент C4 L3: где живёт (контекст), чей (контур — команда), что это и что с ним делаем."""
    id: str
    name: str
    context: str          # система / граница C4: «Витрина Acme Tickets»
    team: str             # контур ответственности — ID команды; «—» у человека, «?» — не определён
    kind: str             # C4_KINDS
    change: str           # C4_CHANGES
    tasks: list           # ID задач и карточек карты, где запланированы работы
    line: int

@dataclass
class Flow:
    """Поток данных C4 L3: от компонента к компоненту — что передаётся, как и по какому контракту."""
    src: str
    dst: str
    data: str
    how: str              # способ: «HTTP, синхронно», «событие», «интерфейс»
    contract: str         # контракт из «Решения TO-BE» или «—»
    line: int

@dataclass
class ADR:
    """Документ «ADR» (<!-- bft-adr … -->): этап «ADR и Системные требования», часть системного дизайна.

    Разделы: «## Контекст» | Участник | Роль в решении |, «## AS-IS» — ландшафт систем текстом,
    «## Варианты» | ID | Вариант | Надёжность | Скорость реализации | Соответствие требованиям | Почему нет |,
    «## Решение TO-BE» | ID | Контракт | Суть решения | Обоснование |, «## Узкие места»
    | ID | Узкое место | Тип | Нагрузка | Риск | Прощупывание |, «## Компромиссы»
    | ID | Компромисс | Надёжность | Скорость реализации | Соответствие требованиям | Чем платим |.
    ADR-диаграмма AS-IS/TO-BE — блок mermaid «## Диаграмма AS-IS/TO-BE». Открытые вопросы —
    в «Вопросах» «Карты» («Где» — ID варианта/компромисса V1, C1)."""
    meta: dict = field(default_factory=dict)
    context: str = ""                                     # «## Контекст» таблица как текст
    asis: str = ""                                        # «## AS-IS»: ландшафт систем текстом
    options: list = field(default_factory=list)           # [Option]
    decisions: list = field(default_factory=list)         # [Decision]
    bottlenecks: list = field(default_factory=list)       # [Bottleneck]
    compromises: list = field(default_factory=list)       # [Compromise]
    diagram: str = ""                                     # mermaid-диаграмма AS-IS/TO-BE
    components: list = field(default_factory=list)        # [Component] — C4 L3
    flows: list = field(default_factory=list)             # [Flow] — потоки данных C4 L3
    doc: Doc | None = None

    def by_id(self, vid: str) -> Option | None:
        return next((o for o in self.options if o.id == vid), None)

@dataclass
class SysContract:
    """Контракт «Системных требований»: три вопроса системной аналитики в одной строке."""
    id: str
    contract: str         # имя контракта — совпадает с ADR «Решение TO-BE» (проверяет AR003)
    consumer: str         # кто потребляет: команда/система/роль
    data: str             # (1) какие данные нужны контракту
    source: str           # (2) источник каждого параметра: система/сервис/поле/справочник
    transform: str        # (3) преобразования для контрактов и бизнес-логики
    line: int

@dataclass
class SysAsIs:
    """Строка AS-IS системных требований: как устроено сейчас."""
    id: str               # A1…
    text: str
    change: str           # что меняется
    line: int

@dataclass
class SysChange:
    """Изменение системных требований: что и почему."""
    id: str               # I1…
    text: str
    why: str
    line: int

@dataclass
class SysQ:
    """Открытый вопрос системных требований. Дублируется в «Вопросы» «Карты» («Где» — ID контракта K1)."""
    id: str               # Q1…
    to: str
    text: str
    answer: str
    line: int

    @property
    def open(self) -> bool:
        return self.answer.strip() in bb.EMPTY

@dataclass
class SysReq:
    """Документ «Системные требования» (<!-- bft-sysreq … -->): этап «ADR и Системные требования»,
    часть системной аналитики. Структура: контракты → параметры → источники → преобразования
    → AS-IS → изменения → открытые вопросы — таблица контрактов отвечает на три вопроса по каждому
    контракту, остальное — AS-IS, изменения и вопросы. Совпадение контрактов с ADR — AR003."""
    meta: dict = field(default_factory=dict)
    contracts: list = field(default_factory=list)         # [SysContract]
    asis: list = field(default_factory=list)              # [SysAsIs]
    changes: list = field(default_factory=list)           # [SysChange]
    questions: list = field(default_factory=list)         # [SysQ]
    doc: Doc | None = None

    def by_id(self, cid: str) -> SysContract | None:
        return next((c for c in self.contracts if c.id == cid), None)

@dataclass
class Seams:
    """Этап «Контроль стыковочных работ»: документ проекта со стыками, обязательствами,
    контрактами по слоям, контрольными точками и рисками. Открытые вопросы и блокеры —
    в таблице «Вопросы» «Карты» («Где» — ID стыка S1…), параллельной структуры нет."""
    meta: dict = field(default_factory=dict)
    seams: list = field(default_factory=list)          # [Seam]
    deliveries: list = field(default_factory=list)     # [Delivery]
    contracts: list = field(default_factory=list)      # [ContractRow]
    checkpoints: list = field(default_factory=list)    # [Checkpoint]
    risks: list = field(default_factory=list)          # [Risk]
    doc: Doc | None = None

    def by_id(self, sid: str) -> Seam | None:
        return next((s for s in self.seams if s.id == sid), None)

@dataclass
class ReleaseStep:
    """Шаг дорожки «План релиза»: что сделать на стенде, чтобы задача прошла дальше."""
    id: str
    track: str                      # dev | stage | prod
    action: str                     # что сделать
    owner: str                      # роль или команда
    kind: str                       # тип шага из RELEASE_STEP_TYPES
    deps: list
    status: str                     # статус из RELEASE_STATUSES
    ready: str                      # критерий готовности
    line: int

@dataclass
class ReleaseGate:
    """Ворота между стендами: кто утверждает переход на следующий стенд и по какому критерию."""
    frm: str                        # dev | stage (ворота после стендов, кроме последнего)
    who: str                        # кто утверждает
    criterion: str
    line: int

@dataclass
class Release:
    """Этап «План релиза / Delivery»: дорожки DEV/STAGE/PROD, шаги и ворота между ними."""
    meta: dict = field(default_factory=dict)
    steps: list = field(default_factory=list)    # [ReleaseStep]
    gates: list = field(default_factory=list)    # [ReleaseGate]
    doc: Doc | None = None

    @property
    def errors(self) -> list:
        return [i for i in self.meta.get("_issues", []) if i.level == "ERROR"]

    def by_track(self, track: str) -> list:
        return [s for s in self.steps if s.track == track]

@dataclass
class Project:
    root: Path
    bdir: Path | None = None
    prefix: str = "BP"
    meta: dict = field(default_factory=dict)
    title: str = ""
    map_doc: Doc | None = None
    story_doc: Doc | None = None
    adr_doc: Doc | None = None
    adr: ADR | None = None
    sysreq_doc: Doc | None = None
    sysreq: SysReq | None = None
    seams_doc: Doc | None = None
    seams: Seams | None = None
    release_doc: Doc | None = None
    release: Release | None = None
    story: bs.Story | None = None
    teams: list[Team] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    docs: dict = field(default_factory=dict)       # {doc-id: Doc}
    screens: dict = field(default_factory=dict)    # {ID экрана: bsn.ScreenDoc}
    tasks: list[BTask] = field(default_factory=list)   # «Что делаем»
    cards: list[BTask] = field(default_factory=list)   # «Как это работает»
    subtasks: list[BTask] = field(default_factory=list)  # подзадачи историй по зонам: FE, BE, Design…
    other: int = 0                                     # задачи проекта вне карты
    issues: list[bb.Issue] = field(default_factory=list)

    def err(self, rel: str, line: int, code: str, msg: str) -> None:
        self.issues.append(bb.Issue(line, "ERROR", code, msg, rel))

    def warn(self, rel: str, line: int, code: str, msg: str) -> None:
        self.issues.append(bb.Issue(line, "WARN", code, msg, rel))

    @property
    def errors(self) -> list[bb.Issue]:
        return [i for i in self.issues if i.level == "ERROR"]

    def task(self, tid: str) -> BTask | None:
        return next((t for t in self.tasks + self.cards + self.subtasks if t.id == tid), None)

    @property
    def id_re(self) -> re.Pattern:
        return re.compile(rf"\b{re.escape(self.prefix)}-\d+(?:\.\d+)*\b")

    def links(self) -> list[tuple[str, str, str]]:
        """Стрелки между карточками: (откуда, куда, что передаётся) — из ссылок в параметрах."""
        ids = {c.id for c in self.cards}
        out, seen = [], set()
        for c in self.cards:
            for key in ("in", "ctl", "out"):
                for it in c.params.get(key, []):
                    for r in it.refs:
                        if r not in ids or r == c.id:
                            continue
                        a, b = (c.id, r) if key == "out" else (r, c.id)
                        if (a, b) not in seen:
                            seen.add((a, b))
                            out.append((a, b, it.text))
        return out


# --- frontmatter Backlog.md: подмножество YAML, которое пишет CLI ---------------------------------

def _scalar(v: str):
    v = v.strip()
    if v in ("", "~", "null"):
        return ""
    if v == "[]":
        return []
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in re.findall(r"""'(?:[^']|'')*'|"(?:[^"\\]|\\.)*"|[^,\s][^,]*""", v[1:-1])]
    return v

def yaml_front(text: str) -> tuple[dict | None, int]:
    """(ключи, число строк frontmatter вместе с ---). Не YAML-frontmatter — (None, 0)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, 0
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, 0
    out: dict = {}
    i, body = 0, lines[1:end]
    while i < len(body):
        ln = body[i]
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        i += 1
        if rest in (">", ">-", ">+", "|", "|-", "|+"):
            block = []
            while i < len(body) and (body[i].startswith(" ") or not body[i].strip()):
                block.append(body[i].strip())
                i += 1
            out[key] = (" " if rest[0] == ">" else "\n").join(block).strip()
        elif rest == "":
            items = []
            while i < len(body) and re.match(r"^\s*- ", body[i]):
                items.append(_scalar(re.sub(r"^\s*- ", "", body[i])))
                i += 1
            out[key] = items
        else:
            out[key] = _scalar(rest)
    return out, end + 1


# --- разбор ---------------------------------------------------------------------------------------

def find_backlog(root: Path) -> Path | None:
    cfg = root / "backlog.config.yml"
    if cfg.is_file():
        m = re.search(r"^backlog_directory:\s*[\"']?([^\"'\n]+)", cfg.read_text(encoding="utf-8"), re.M)
        if m and (root / m.group(1).strip()).is_dir():
            return root / m.group(1).strip()
    for name in ("backlog", ".backlog"):
        if (root / name / "config.yml").is_file():
            return root / name
    return None

def _meta_comment(body: str, kind: str) -> tuple[dict, str] | None:
    """Метаданные в HTML-комментарии <!-- bft-map … --> в начале тела: в Backlog.md они не видны."""
    lines = body.split("\n")
    k = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if k is None or not META_OPEN.match(lines[k].strip()) or lines[k].strip()[4:].strip() != kind:
        return None
    end = next((i for i in range(k + 1, len(lines)) if lines[i].strip() == "-->"), None)
    if end is None:
        return None
    meta = {}
    for ln in lines[k + 1:end]:
        if ":" in ln:
            a, _, b = ln.partition(":")
            meta[a.strip()] = b.strip().strip("\"'")
    # тот же текст с frontmatter вместо комментария — номера строк совпадают
    as_front = "\n".join(lines[:k] + ["---"] + lines[k + 1:end] + ["---"] + lines[end + 1:])
    return meta, as_front

def _read_doc(pr: Project, f: Path) -> Doc | None:
    rel = f.relative_to(pr.root).as_posix()
    text = f.read_text(encoding="utf-8")
    fm, off = yaml_front(text)
    if fm is None or not fm.get("id") or not fm.get("title"):
        pr.err(rel, 1, "BL005", "документ без frontmatter Backlog.md (id, title) — создавай через `backlog doc create`")
        return None
    return Doc(str(fm["id"]), str(fm["title"]), f, rel, fm, "\n".join(text.split("\n")[off:]), off)

def _table(d: Doc, secs: dict, name: str, header: tuple, err, code: str = "AR001") -> list[tuple[int, list[str]]]:
    """Таблица раздела «## name» с заголовком header: [(строка, колонки)]; форма — кодом err."""
    if name not in secs:
        err(d.off + 1, code, f"нет раздела «## {name}» с таблицей")
        return []
    ln0, tbody = secs[name]
    found = bb.tables(tbody, first_lineno=d.off + ln0 + 1)
    if not found:
        err(d.off + ln0, code, f"«{name}»: нет таблицы")
        return []
    hdr, rows = found[0]
    if tuple(hdr) != header:
        err(d.off + ln0, code, f"«{name}»: заголовок таблицы — {' | '.join(header)}")
        return []
    out = []
    for ln, c in rows:
        if len(c) != len(header):
            err(ln, code, f"«{name}»: в строке {len(c)} колонок, нужно {len(header)}")
            continue
        out.append((ln, c))
    return out

def _norm_id(raw: str, pat: re.Pattern, tag: str) -> str:
    m = pat.match(raw.strip())
    return f"{tag}{int(m.group('num'))}" if m else ""

def parse_adr(pr: Project, d: Doc) -> ADR:
    """Документ «ADR» (<!-- bft-adr … -->): этап «ADR и Системные требования», системный дизайн.

    Разделы: «## Контекст» | Участник | Роль в решении |, «## AS-IS» — ландшафт текстом,
    «## Варианты» | ID | Вариант | Надёжность | Скорость реализации | Соответствие требованиям |
    Почему нет |, «## Решение TO-BE» | ID | Контракт | Суть решения | Обоснование |,
    «## Узкие места» | ID | Узкое место | Тип | Нагрузка | Риск | Прощупывание |, «## Компромиссы»
    | ID | Компромисс | Надёжность | Скорость реализации | Соответствие требованиям | Чем платим |,
    «## Диаграмма AS-IS/TO-BE» — mermaid. Форма проверяется здесь; смысл (выбор, оси, диаграмма) —
    кодами AR в `bft-backlog-lint.py`."""
    a = ADR(meta={k: v for k, v in d.meta.items() if not k.startswith("_")})
    a.doc = d
    issues: list[bb.Issue] = []
    err = lambda ln, code, msg: issues.append(bb.Issue(ln, "ERROR", code, msg, d.rel))  # noqa: E731
    for key in ADR_META:
        if not a.meta.get(key):
            err(d.off + 1, "AR001", f"паспорт <!-- bft-adr -->: нет ключа `{key}`")
    lines = d.body.split("\n")
    h1 = next((ln for ln in lines if ln.startswith("# ")), "")
    if not h1:
        err(d.off + 1, "AR001", "нет заголовка `# ADR: <инициатива>`")
    if a.meta.get("status", "").lower() not in ADR_STATUSES:
        err(d.off + 1, "AR001", f"статус «{a.meta.get('status', '')}» — один из: {', '.join(ADR_STATUSES)}")
    secs = bb._sections(lines)
    if "Контекст" in secs:
        a.context = "\n".join(secs["Контекст"][1]).strip()
        rows = _table(d, secs, "Контекст", ADR_CONTEXT_HEADER, err)
        for ln, c in rows:
            if not all(x.strip() for x in c):
                err(ln, "AR001", "контексту нужны «Участник» и «Роль в решении»")
    else:
        err(d.off + 1, "AR001", "нет раздела «## Контекст» с таблицей")
    if "AS-IS" in secs:
        a.asis = "\n".join(secs["AS-IS"][1]).strip()
    else:
        err(d.off + 1, "AR001", "нет раздела «## AS-IS» — ландшафт систем как устроен сейчас")
    ids: set[str] = set()
    for ln, c in _table(d, secs, "Варианты", ADR_OPTION_HEADER, err):
        vid = _norm_id(c[0], VARIANT_ID, "V")
        if not vid or vid in ids:
            err(ln, "AR001", f"вариант: ID вида V1…, уникален — «{c[0]}»")
            continue
        if not all(x.strip() for x in c[1:]):
            err(ln, "AR001", f"{vid}: нужны «Вариант», оценки по трём осям и «Почему нет»")
            continue
        ids.add(vid)
        a.options.append(Option(vid, c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip(), c[5].strip()))
    if "Решение TO-BE" in secs:
        for ln, c in _table(d, secs, "Решение TO-BE", ADR_DECISION_HEADER, err):
            if not all(x.strip() for x in c):
                err(ln, "AR001", "решению нужны «ID» (вариант V1…), «Контракт», «Суть решения», «Обоснование»")
                continue
            a.decisions.append(Decision(c[0].strip().upper(), c[1].strip(), c[2].strip(), c[3].strip(), ln))
    else:
        err(d.off + 1, "AR001", "нет раздела «## Решение TO-BE» с таблицей")
    # «Узкие места» и «Компромиссы» — условные разделы: нет таблицы — AR005 в check_adr подскажет;
    # форма проверяется, только если раздел есть
    if "Узкие места" in secs:
        for ln, c in _table(d, secs, "Узкие места", BOTTLENECK_HEADER, err):
            nid = _norm_id(c[0], BOTTLENECK_ID, "N")
            if not nid or nid in {x.id for x in a.bottlenecks}:
                err(ln, "AR001", f"узкое место: ID вида N1…, уникален — «{c[0]}»")
                continue
            if not all(x.strip() for x in c[1:]):
                err(ln, "AR001", f"{nid}: нужны «Узкое место», «Тип», «Нагрузка», «Риск», «Прощупывание»")
                continue
            a.bottlenecks.append(Bottleneck(nid, c[1].strip(), c[2].strip().lower(), c[3].strip(), c[4].strip(), c[5].strip(), ln))
    if "Компромиссы" in secs:
        for ln, c in _table(d, secs, "Компромиссы", COMPROMISE_HEADER, err):
            cid = _norm_id(c[0], COMPROMISE_ID, "C")
            if not cid or cid in {x.id for x in a.compromises}:
                err(ln, "AR001", f"компромисс: ID вида C1…, уникален — «{c[0]}»")
                continue
            if not all(x.strip() for x in c[1:]):
                err(ln, "AR001", f"{cid}: нужны «Компромисс», оценки по трём осям и «Чем платим»")
                continue
            a.compromises.append(Compromise(cid, c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip(), c[5].strip(), ln))
    # C4 L3 — условные разделы: нет — AR007 в check_adr подскажет; форма — если раздел есть
    if "Компоненты" in secs:
        for ln, c in _table(d, secs, "Компоненты", C4_COMPONENT_HEADER, err):
            mid = _norm_id(c[0], COMPONENT_ID, "M")
            if not mid or mid in {x.id for x in a.components}:
                err(ln, "AR001", f"компонент: ID вида M1…, уникален — «{c[0]}»")
                continue
            name, ctx, team, kind, change = (x.strip() for x in c[1:6])
            if not (name and ctx and team and kind and change):
                err(ln, "AR001", f"{mid}: нужны «Компонент», «Контекст», «Контур», «Тип», «Изменение»")
                continue
            if kind.lower() not in C4_KINDS:
                err(ln, "AR001", f"{mid}: тип «{kind}» — один из: {', '.join(C4_KINDS)}")
                continue
            if change.lower() not in C4_CHANGES:
                err(ln, "AR001", f"{mid}: изменение «{change}» — одно из: {', '.join(C4_CHANGES)}")
                continue
            tasks = [] if c[6].strip() in EMPTY_CELL else [x.strip().upper() for x in re.split(r"[,;\s]+", c[6]) if x.strip()]
            a.components.append(Component(mid, name, ctx, team, kind.lower(), change.lower(), tasks, ln))
    if "Потоки" in secs:
        for ln, c in _table(d, secs, "Потоки", C4_FLOW_HEADER, err):
            src, dst = _norm_id(c[0], COMPONENT_ID, "M"), _norm_id(c[1], COMPONENT_ID, "M")
            if not src or not dst:
                err(ln, "AR001", f"поток: «От» и «К» — ID компонентов M1…, а не «{c[0]}» → «{c[1]}»")
                continue
            if not (c[2].strip() and c[3].strip()):
                err(ln, "AR001", f"поток {src} → {dst}: нужны «Данные» и «Способ»")
                continue
            a.flows.append(Flow(src, dst, c[2].strip(), c[3].strip(), c[4].strip(), ln))
    if "Диаграмма AS-IS/TO-BE" in secs:
        mm = MERMAID.search("\n".join(secs["Диаграмма AS-IS/TO-BE"][1]))
        a.diagram = f"```mermaid\n{mm.group(1)}\n```" if mm else ""
        if not mm:
            err(d.off + secs["Диаграмма AS-IS/TO-BE"][0], "AR001", "«Диаграмма AS-IS/TO-BE»: нет блока ```mermaid")
    else:
        err(d.off + 1, "AR001", "нет раздела «## Диаграмма AS-IS/TO-BE» с mermaid-схемой")
    if not a.options:
        err(d.off + 1, "AR001", "в «Вариантах» нет ни одного варианта — ADR выбирает между вариантами, а не описывает один")
    a.meta["_issues"] = issues
    return a

def parse_sysreq(pr: Project, d: Doc) -> SysReq:
    """Документ «Системные требования» (<!-- bft-sysreq … -->): этап «ADR и Системные требования»,
    системная аналитика. Разделы: «## Контракты» | ID | Контракт | Потребитель | Данные контракту |
    Источник параметров | Преобразования | — три вопроса на каждый контракт в одной строке;
    «## AS-IS» | ID | Как устроено сейчас | Что меняется |, «## Изменения»
    | ID | Изменение | Причина |, «## Открытые вопросы» | ID | Кому | Вопрос | Ответ |."""
    s = SysReq(meta={k: v for k, v in d.meta.items() if not k.startswith("_")})
    s.doc = d
    issues: list[bb.Issue] = []
    err = lambda ln, code, msg: issues.append(bb.Issue(ln, "ERROR", code, msg, d.rel))  # noqa: E731
    for key in SYSREQ_META:
        if not s.meta.get(key):
            err(d.off + 1, "AR001", f"паспорт <!-- bft-sysreq -->: нет ключа `{key}`")
    lines = d.body.split("\n")
    h1 = next((ln for ln in lines if ln.startswith("# ")), "")
    if not h1:
        err(d.off + 1, "AR001", "нет заголовка `# Системные требования: <инициатива>`")
    if s.meta.get("status", "").lower() not in SYSREQ_STATUSES:
        err(d.off + 1, "AR001", f"статус «{s.meta.get('status', '')}» — Черновик или Согласован")
    secs = bb._sections(lines)
    cids: set[str] = set()
    for ln, c in _table(d, secs, "Контракты", CONTRACTS_HEADER, err):
        kid = _norm_id(c[0], CONTRACT_ID, "K")
        if not kid or kid in cids:
            err(ln, "AR001", f"контракт: ID вида K1…, уникален — «{c[0]}»")
            continue
        if not all(x.strip() for x in c[1:]):
            err(ln, "AR001", f"{kid}: нужны «Контракт», «Потребитель», «Данные контракту», «Источник параметров», «Преобразования»")
            continue
        cids.add(kid)
        s.contracts.append(SysContract(kid, c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip(), c[5].strip(), ln))
    if not s.contracts:
        err(d.off + 1, "AR001", "в «Контрактах» нет ни одного контракта — для работ без контрактов документ не создаётся")
    if "AS-IS" in secs:
        aids: set[str] = set()
        for ln, c in _table(d, secs, "AS-IS", SYSREQ_ASIS_HEADER, err):
            aid = _norm_id(c[0], SYSROW_ID, "A")
            if not aid or aid in aids:
                err(ln, "AR001", f"AS-IS: ID вида A1…, уникален — «{c[0]}»")
                continue
            if not all(x.strip() for x in c[1:]):
                err(ln, "AR001", f"{aid}: нужны «Как устроено сейчас» и «Что меняется»")
                continue
            aids.add(aid)
            s.asis.append(SysAsIs(aid, c[1].strip(), c[2].strip(), ln))
    else:
        err(d.off + 1, "AR001", "нет раздела «## AS-IS» с таблицей")
    if "Изменения" in secs:
        iids: set[str] = set()
        IID = re.compile(r"^I-?(?P<num>\d+)$", re.I)
        for ln, c in _table(d, secs, "Изменения", SYSREQ_CHANGE_HEADER, err):
            iid = _norm_id(c[0], IID, "I")
            if not iid or iid in iids:
                err(ln, "AR001", f"изменение: ID вида I1…, уникален — «{c[0]}»")
                continue
            if not all(x.strip() for x in c[1:]):
                err(ln, "AR001", f"{iid}: нужны «Изменение» и «Причина»")
                continue
            iids.add(iid)
            s.changes.append(SysChange(iid, c[1].strip(), c[2].strip(), ln))
    else:
        err(d.off + 1, "AR001", "нет раздела «## Изменения» с таблицей")
    if "Открытые вопросы" in secs:
        qids: set[str] = set()
        for ln, c in _table(d, secs, "Открытые вопросы", SYSREQ_Q_HEADER, err):
            qid = _norm_id(c[0], SYSQ_ID, "Q")
            if not qid or qid in qids:
                err(ln, "AR001", f"вопрос: ID вида Q1…, уникален — «{c[0]}»")
                continue
            if not c[1].strip() or not c[2].strip():
                err(ln, "AR001", f"{qid}: нужны «Кому» и «Вопрос»")
                continue
            qids.add(qid)
            s.questions.append(SysQ(qid, c[1].strip(), c[2].strip(), c[3].strip(), ln))
    s.meta["_issues"] = issues
    return s

def parse_seams(pr: Project, d: Doc) -> Seams:
    """Документ «Стыки» (<!-- bft-seams … -->): этап «Контроль стыковочных работ».

    Разделы: «## Участники» | ID | Стык | Поставщик | Потребитель | Ответственный за контракт |
    «## Обязательства» | ID | Кто | Что | Кому | Срок | Формат/место |, «## Контракты стыков»
    | Стык | Аспект | Требование к фиксации |, «## Контрольные точки»
    | ID | Точка | Когда | Что проверяется | Кто проводит |, «## Риски»
    | ID | Риск | Следствие | Владелец | Митигация |. Открытые вопросы — в «Вопросах» «Карты»
    («Где» — ID стыка S1…). Форма проверяется здесь; смысл (команды, ссылки на стыки) — кодами SM
    в `bft-backlog-lint.py`.
    """
    sm = Seams(meta={k: v for k, v in d.meta.items() if not k.startswith("_")})
    sm.doc = d
    issues: list[bb.Issue] = []
    err = lambda ln, code, msg: issues.append(bb.Issue(ln, "ERROR", code, msg, d.rel))  # noqa: E731
    for key in SEAMS_META:
        if not sm.meta.get(key):
            err(d.off + 1, "SM001", f"паспорт <!-- bft-seams -->: нет ключа `{key}`")
    body = d.body
    lines = body.split("\n")
    h1 = next((ln for ln in lines if ln.startswith("# ")), "")
    if not h1:
        err(d.off + 1, "SM001", "нет заголовка `# Стыки: <инициатива>`")
    secs = bb._sections(lines)
    ids: dict[str, set[str]] = {"S": set(), "D": set(), "K": set(), "R": set()}
    for name, header, tag in (("Участники", SEAM_HEADER, "S"), ("Обязательства", DELIVERY_HEADER, "D"),
                              ("Контрольные точки", CHECKPOINT_HEADER, "K"), ("Риски", RISK_HEADER, "R")):
        if name not in secs:
            err(d.off + 1, "SM001", f"нет раздела «## {name}» с таблицей")
            continue
        ln0, tbody = secs[name]
        found = bb.tables(tbody, first_lineno=d.off + ln0 + 1)
        if not found:
            err(d.off + ln0, "SM001", f"«{name}»: нет таблицы")
            continue
        hdr, rows = found[0]
        if tuple(hdr) != header:
            err(d.off + ln0, "SM001", f"«{name}»: заголовок таблицы — {' | '.join(header)}")
            continue
        pat = {"S": SEAM_ID, "D": DELIVERY_ID, "K": CHECKPOINT_ID, "R": RISK_ID}[tag]
        for ln, c in rows:
            if len(c) != len(header):
                err(ln, "SM001", f"«{name}»: в строке {len(c)} колонок, нужно {len(header)}")
                continue
            if tag == "S":
                sid = _norm_id(c[0], pat, "S")
                if not sid or sid in ids["S"]:
                    err(ln, "SM001", f"стык: ID вида S1…, уникален — «{c[0]}»")
                    continue
                kind = c[1].strip().lower()
                if kind not in SEAM_KINDS:
                    err(ln, "SM001", f"{sid}: стык «{c[1]}» — один из: {', '.join(SEAM_KINDS)}")
                    continue
                if not all(x.strip() for x in c[2:]):
                    err(ln, "SM001", f"{sid}: нужны «Поставщик», «Потребитель», «Ответственный за контракт»")
                    continue
                ids["S"].add(sid)
                sm.seams.append(Seam(sid, kind, c[2].strip(), c[3].strip(), c[4].strip(), ln))
            elif tag == "D":
                did = _norm_id(c[0], pat, "D")
                if not did or did in ids["D"]:
                    err(ln, "SM001", f"обязательство: ID вида D1…, уникален — «{c[0]}»")
                    continue
                if not all(x.strip() for x in c[1:]):
                    err(ln, "SM001", f"{did}: нужны «Кто», «Что», «Кому», «Срок», «Формат/место»")
                    continue
                ids["D"].add(did)
                sm.deliveries.append(Delivery(did, c[1].strip(), c[2].strip(), c[3].strip(),
                                              c[4].strip(), c[5].strip(), "", ln))
            elif tag == "K":
                kid = _norm_id(c[0], pat, "K")
                if not kid or kid in ids["K"]:
                    err(ln, "SM001", f"контрольная точка: ID вида K1…, уникален — «{c[0]}»")
                    continue
                if not all(x.strip() for x in c[1:]):
                    err(ln, "SM001", f"{kid}: нужны «Точка», «Когда», «Что проверяется», «Кто проводит»")
                    continue
                ids["K"].add(kid)
                sm.checkpoints.append(Checkpoint(kid, c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip(), ln))
            else:
                rid = _norm_id(c[0], pat, "R")
                if not rid or rid in ids["R"]:
                    err(ln, "SM001", f"риск: ID вида R1…, уникален — «{c[0]}»")
                    continue
                if not all(x.strip() for x in c[1:]):
                    err(ln, "SM001", f"{rid}: нужны «Риск», «Следствие», «Владелец», «Митигация»")
                    continue
                ids["R"].add(rid)
                sm.risks.append(Risk(rid, c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip(), ln))
    # «Контракты стыков» — строки привязаны к стыку; без стыков таблица не читается
    if "Контракты стыков" in secs:
        ln0, tbody = secs["Контракты стыков"]
        found = bb.tables(tbody, first_lineno=d.off + ln0 + 1)
        if found:
            hdr, rows = found[0]
            if tuple(hdr) != SEAM_CONTRACT_HEADER:
                err(d.off + ln0, "SM001", f"«Контракты стыков»: заголовок таблицы — {' | '.join(SEAM_CONTRACT_HEADER)}")
            else:
                for ln, c in rows:
                    if len(c) != len(SEAM_CONTRACT_HEADER):
                        err(ln, "SM001", f"«Контракты стыков»: в строке {len(c)} колонок, нужно {len(SEAM_CONTRACT_HEADER)}")
                        continue
                    if not all(x.strip() for x in c):
                        err(ln, "SM001", "контракту нужны «Стык», «Аспект», «Требование к фиксации»")
                        continue
                    sm.contracts.append(ContractRow(c[0].strip().upper(), c[1].strip(), c[2].strip(), ln))
    elif sm.seams:
        err(d.off + 1, "SM001", "нет раздела «## Контракты стыков» с таблицей")
    if not sm.seams:
        err(d.off + 1, "SM001", "в «Участниках» нет ни одного стыка — для задач без стыков документ не создаётся")
    sm.meta["_issues"] = issues
    return sm

def _norm_release_id(raw: str, pat: re.Pattern, tag: str) -> str:
    m = pat.match(raw.strip())
    return f"{tag}{int(m.group('num'))}" if m else ""

def parse_release(pr: Project, d: Doc) -> Release:
    """Документ «План релиза» (<!-- bft-release … -->): дорожки DEV/STAGE/PROD, шаги, ворота.

    Разделы документа: «## Шаги» — таблица | ID | Стенд | Что сделать | Ответственный | Тип |
    Зависимости | Статус | Критерий готовности |; «## Ворота» — | Ворота | Кто утверждает |
    Критерий перехода |. Форма проверяется здесь; смысл (deps, статусы, чей переход) — гейтом BL.
    """
    rel = Release(meta={k: v for k, v in d.meta.items() if not k.startswith("_")})
    rel.doc = d
    issues: list[bb.Issue] = []
    err = lambda ln, code, msg: issues.append(bb.Issue(ln, "ERROR", code, msg, d.rel))  # noqa: E731
    for key in RELEASE_META:
        if not rel.meta.get(key):
            err(d.off + 1, "RL001", f"паспорт <!-- bft-release -->: нет ключа `{key}`")
    body = d.body
    lines = body.split("\n")
    h1 = next((ln for ln in lines if ln.startswith("# ")), "")
    if not h1:
        err(d.off + 1, "RL001", "нет заголовка `# План релиза: <инициатива>`")
    secs = bb._sections(lines)
    step_ids: set[str] = set()
    for name, header in (("Шаги", STEP_HEADER), ("Ворота", GATE_HEADER)):
        if name not in secs:
            if name == "Шаги":
                err(d.off + 1, "RL001", f"нет раздела «## {name}» с таблицей шагов")
            continue
        ln0, tbody = secs[name]
        found = bb.tables(tbody, first_lineno=d.off + ln0 + 1)
        if not found:
            err(d.off + ln0, "RL001", f"«{name}»: нет таблицы")
            continue
        hdr, rows = found[0]
        if tuple(hdr) != header:
            err(d.off + ln0, "RL001", f"«{name}»: заголовок таблицы — {' | '.join(header)}")
            continue
        for ln, c in rows:
            if len(c) != len(header):
                err(ln, "RL001", f"«{name}»: в строке {len(c)} колонок, нужно {len(header)}")
                continue
            if name == "Шаги":
                sid = _norm_release_id(c[0], STEP_ID, "R")
                if not sid or sid in step_ids:
                    err(ln, "RL001", f"шаг: ID вида R1…, уникален — «{c[0]}»")
                    continue
                step_ids.add(sid)
                track = c[1].strip().lower()
                if track not in RELEASE_TRACKS:
                    err(ln, "RL001", f"{sid}: стенд «{c[1]}» — один из dev, stage, prod")
                    continue
                if not c[2].strip() or not c[3].strip() or not c[4].strip():
                    err(ln, "RL001", f"{sid}: нужны «Что сделать», «Ответственный», «Тип»")
                    continue
                kind = c[4].strip().lower()
                if kind not in RELEASE_STEP_TYPES:
                    err(ln, "RL001", f"{sid}: тип «{c[4]}» — один из: {', '.join(RELEASE_STEP_TYPES)}")
                    continue
                deps = [x.strip() for x in re.split(r"[;,]", c[5]) if x.strip() and x.strip() not in bb.EMPTY]
                status = c[6].strip().lower()
                if status not in RELEASE_STATUSES:
                    err(ln, "RL001", f"{sid}: статус «{c[6]}» — один из: {', '.join(RELEASE_STATUSES)}")
                    continue
                if not c[7].strip():
                    err(ln, "RL001", f"{sid}: нет критерия готовности")
                    continue
                rel.steps.append(ReleaseStep(sid, track, c[2].strip(), c[3].strip(), kind,
                                             deps, status, c[7].strip(), ln))
            else:
                frm = c[0].strip().lower()
                if frm not in RELEASE_TRACKS[:-1]:
                    err(ln, "RL001", f"ворота «{c[0]}»: стенд — dev или stage (после PROD ворот нет)")
                    continue
                if not c[1].strip() or not c[2].strip():
                    err(ln, "RL001", "воротам нужны «Кто утверждает» и «Критерий перехода»")
                    continue
                rel.gates.append(ReleaseGate(frm, c[1].strip(), c[2].strip(), ln))
    if rel.steps and not any(s.track == "dev" for s in rel.steps):
        err(d.off + 1, "RL001", "нет шагов на дорожке dev — с неё начинается путь задачи")
    rel.meta["_issues"] = issues
    return rel

def _subsections(text: str, first: int) -> tuple[list[str], dict, list[tuple[int, str]]]:
    """Текст описания: (строки до первого ###, {раздел: (строка, текст)}, порядок [(строка, раздел)])."""
    pre, secs, order, cur, buf, start = [], {}, [], None, [], 0
    for n, ln in enumerate(text.split("\n"), start=first):
        if ln.startswith("### "):
            if cur is not None:
                secs[cur] = (start, "\n".join(buf).strip())
            cur, buf, start = ln[4:].strip(), [], n
            order.append((n, cur))
        elif cur is None:
            pre.append(ln)
        else:
            buf.append(ln)
    if cur is not None:
        secs[cur] = (start, "\n".join(buf).strip())
    return pre, secs, order

def split_items(raw: str) -> list[str]:
    """Значения через «;», точка с запятой внутри скобок значение не делит."""
    out, buf, depth = [], "", 0
    for ch in raw:
        depth += ch in "(«" and 1 or 0
        depth -= ch in ")»" and 1 or 0
        if ch == ";" and depth <= 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    out.append(buf)
    return [x.strip() for x in out if x.strip()]

def parse_params(pr: Project, t: BTask, line: int, text: str) -> None:
    ref_group = re.compile(rf"\s*\(\s*(?:[←→]\s*)?{re.escape(pr.prefix)}-\d+(?:\.\d+)*(?:\s*,\s*(?:[←→]\s*)?{re.escape(pr.prefix)}-\d+(?:\.\d+)*)*\s*\)")
    for n, raw in enumerate(text.split("\n"), start=line + 1):
        ln = raw.strip()
        if not ln:
            continue
        m = re.match(r"^[-*]\s*(?:\*\*)?([А-Яа-яЁё]+)\s*:\s*(?:\*\*)?\s*(.*)$", ln)
        key = PARAM_KEYS.get(m.group(1).lower()) if m else None
        if not key:
            pr.err(t.rel, n, "BL009", f"{t.id}: «Параметры» — строки `- **Вход:** …`, `- **Управление:** …`, `- **Выход:** …`, `- **Механизм:** …`, а не «{ln[:40]}»")
            continue
        for v in split_items(m.group(2).replace("**", "")):
            refs = pr.id_re.findall(v)
            txt = ref_group.sub("", v).strip() or v
            t.params.setdefault(key, []).append(Item(txt, refs))

STEP_TASK = re.compile(r"^([^:?→]{1,40}?)\s*:\s*(\S.*)$")

BRANCH = re.compile(r"^(.+?)\s*(?:→|->)\s*(.+)$")

def parse_process(pr: "Project", c: BTask, line: int, text: str) -> None:
    """### Процесс: «- Участник: действие», «- ? вопрос» и под ним «  - ответ → Участник: действие | конец»."""
    err = lambda n, msg: pr.err(c.rel, n, "BL009", f"{c.id}: «Процесс» — {msg}")  # noqa: E731
    gate = None
    for n, raw in enumerate(text.split("\n"), start=line + 1):
        if not raw.strip():
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", raw)
        if not m:
            err(n, f"строка списка «- …», а не «{raw.strip()[:40]}»")
            continue
        sub, body = len(m.group(1)) >= 2, m.group(2).strip()
        if sub:
            bm = BRANCH.match(body)
            if gate is None or not bm:
                err(n, "ветка — под развилкой «- ? вопрос», вида «  - да → Участник: действие» или «  - нет → конец»")
                continue
            label, tail = bm.group(1).strip(), bm.group(2).strip()
            if tail.lower() in ("конец", "end"):
                gate["br"].append({"label": label, "end": True})
                continue
            tm = STEP_TASK.match(tail)
            if not tm:
                err(n, f"ветка «{label}» — «Участник: действие» или «конец»")
                continue
            gate["br"].append({"label": label, "lane": tm.group(1).strip(), "text": tm.group(2).strip()})
            continue
        if body.startswith("?"):
            gate = {"t": "xor", "q": body[1:].strip(), "br": [], "line": n}
            c.proc.append(gate)
            continue
        gate = None
        tm = STEP_TASK.match(body)
        if not tm:
            err(n, f"шаг «Участник: действие», а не «{body[:40]}»")
            continue
        c.proc.append({"t": "task", "lane": tm.group(1).strip(), "text": tm.group(2).strip()})
    for g in [x for x in c.proc if x["t"] == "xor"]:
        if len(g["br"]) < 2:
            err(g["line"], f"у развилки «{g['q']}» нужно хотя бы две ветки")
        g.pop("line", None)
    tasks = [x for x in c.proc if x["t"] == "task"] + [b for g in c.proc if g["t"] == "xor" for b in g["br"] if not b.get("end")]
    if len(tasks) < 2:
        err(line, "хотя бы два шага")
    if len(tasks) > MAX_STEPS:
        err(line, f"{len(tasks)} шагов (больше {MAX_STEPS}) — раздели карточку на две")
    if len(lanes_of(c.proc)) > MAX_LANES:
        err(line, f"участников {len(lanes_of(c.proc))} (больше {MAX_LANES})")

def lanes_of(proc: list) -> list[str]:
    out: list[str] = []
    for x in proc:
        for lane in ([x["lane"]] if x["t"] == "task" else [b["lane"] for b in x["br"] if b.get("lane")]):
            if lane not in out:
                out.append(lane)
    return out

def bpmn_of(c: BTask) -> str:
    """Процесс карточки в mermaid: дорожка — участник, развилка — ромб; тот же процесс — тот же текст.
    Старт, развилка и конец лежат в дорожке того, кто на этом шаге действует; вид задан в самом
    тексте (`classDef`) — схема одинаково читается на карте, в браузере Backlog.md и на GitHub."""
    q = lambda s: s.replace('"', "#quot;")  # noqa: E731
    lanes = lanes_of(c.proc)
    lane_nodes: dict[str, list[str]] = {ln: [] for ln in lanes}
    edges: list[str] = []
    ask: list[str] = []
    n = ends = 0
    prev: list[tuple[str, str]] = [("S", "")]   # (узел, подпись ребра)
    last_lane = lanes[0] if lanes else ""
    lane_nodes.setdefault(last_lane, []).append('S((" "))')

    def node(nid: str, lane: str, shape: str, text: str) -> None:
        lane_nodes[lane].append(f'{nid}{shape[0]}"{q(text)}"{shape[1]}')
        if bb.MARKER in text:
            ask.append(nid)

    for x in c.proc:
        n += 1
        if x["t"] == "task":
            nid = f"N{n}"
            node(nid, x["lane"], "[]", x["text"])
            edges += [f"  {a} -- {lab} --> {nid}" if lab else f"  {a} --> {nid}" for a, lab in prev]
            prev, last_lane = [(nid, "")], x["lane"]
            continue
        gid = f"G{n}"
        node(gid, last_lane, "{}", x["q"])
        edges += [f"  {a} -- {lab} --> {gid}" if lab else f"  {a} --> {gid}" for a, lab in prev]
        prev = []
        for b in x["br"]:
            if b.get("end"):
                ends += 1
                lane_nodes[last_lane].append(f'E{ends}(((" ")))')
                edges.append(f'  {gid} -- {q(b["label"])} --> E{ends}')
                continue
            n += 1
            nid = f"N{n}"
            node(nid, b["lane"], "[]", b["text"])
            edges.append(f'  {gid} -- {q(b["label"])} --> {nid}')
            prev.append((nid, ""))
        if len(prev) == 1:
            last_lane = next(b["lane"] for b in x["br"] if not b.get("end"))
    if prev:
        lane_nodes[last_lane].append('E(((" ")))')
        edges += [f"  {a} --> E" for a, _ in prev]
    stops = (["E"] if prev else []) + [f"E{i}" for i in range(1, ends + 1)]
    out = ["```mermaid", "flowchart LR"]
    for i, ln in enumerate(lanes, 1):
        out.append(f'  subgraph L{i}["{q(ln)}"]')
        out += [f"    {x}" for x in lane_nodes[ln]]
        out.append("  end")
    out += edges
    out += ["  classDef start fill:#fff,stroke:#2f6b2a,stroke-width:2px",
            "  classDef stop fill:#fff,stroke:#1c1c1c,stroke-width:4px",
            "  classDef gw fill:#fff8e6,stroke:#b7791f",
            "  classDef ask color:#c0392b,stroke:#c0392b",
            "  class S start",
            f"  class {','.join(stops)} stop"]
    gws = [x.split("{")[0] for ln in lanes for x in lane_nodes[ln] if x.startswith("G")]
    if gws:
        out.append(f"  class {','.join(gws)} gw")
    if ask:
        out.append(f"  class {','.join(ask)} ask")
    for i in range(1, len(lanes) + 1):
        out.append(f"  style L{i} fill:{'#faf9f6' if i % 2 else '#ffffff'},stroke:#d8d4cb")
    out.append("```")
    return "\n".join(out)

def _read_task(pr: Project, f: Path) -> BTask | None:
    rel = f.relative_to(pr.root).as_posix()
    text = f.read_text(encoding="utf-8")
    fm, off = yaml_front(text)
    if fm is None or not fm.get("id") or not fm.get("title"):
        pr.err(rel, 1, "BL005", "задача без frontmatter Backlog.md (id, title, status) — создавай через `backlog task create`")
        return None
    t = BTask(str(fm["id"]).upper(), str(fm["title"]).strip(), f, rel, fm, 0)
    t.labels = [str(x) for x in (fm.get("labels") or [])]
    t.parent = str(fm.get("parent_task_id") or "").upper()
    sections = {k: v for k, v in SECTION_RE.findall(text)}
    if "DESCRIPTION" in sections:
        t.desc = sections["DESCRIPTION"]
        t.off = text[:text.index("<!-- SECTION:DESCRIPTION:BEGIN -->")].count("\n") + 2
    else:  # файл старого вида: «## Description» без маркеров
        dm = re.search(r"^## Description\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if dm:
            t.desc = dm.group(1).strip("\n")
            t.off = text[:dm.start(1)].count("\n") + 1
    t.notes = sections.get("NOTES", "").strip()
    am = LIST_RE["AC"].search(text)
    if am:
        for ln in am.group(1).split("\n"):
            cm = CHECK_ITEM.match(ln.strip())
            if cm:
                t.ac.append((cm.group(1) != " ", cm.group(2).strip()))
    return t

def _label(t: BTask, key: str) -> list[str]:
    return [x.split(":", 1)[1].strip() for x in t.labels if x.lower().startswith(key + ":")]

def parse(root: Path) -> Project:
    pr = Project(root=root)
    pr.bdir = find_backlog(root)
    if pr.bdir is None:
        pr.err("", 1, "BL001", "не проект Backlog.md: нет backlog/config.yml — `bft-backlog-init.py` или `backlog init`")
        return pr
    cfg = (pr.bdir / "config.yml").read_text(encoding="utf-8")
    m = re.search(r"^task_prefix:\s*[\"']?([A-Za-z]+)", cfg, re.M)
    pr.prefix = (m.group(1) if m else "task").upper()

    # --- документы: паспорт карты, история, экраны --------------------------------------------
    for f in sorted((pr.bdir / "docs").rglob("*.md")) if (pr.bdir / "docs").is_dir() else []:
        d = _read_doc(pr, f)
        if not d:
            continue
        if d.id in pr.docs:
            pr.err(d.rel, 1, "BL005", f"второй документ с ID {d.id} — `backlog doctor`")
            continue
        pr.docs[d.id] = d
        for kind in ("bft-map", "bft-story", "bft-adr", "bft-sysreq", "bft-seams", "bft-release"):
            mc = _meta_comment(d.body, kind)
            if mc:
                d.meta = {**d.meta, "_kind": kind, **mc[0]}
                if kind == "bft-map":
                    if pr.map_doc:
                        pr.err(d.rel, 1, "BL002", f"второй паспорт карты — уже есть {pr.map_doc.rel}")
                    pr.map_doc, pr.meta = d, mc[0]
                elif kind == "bft-adr":
                    if pr.adr_doc:
                        pr.err(d.rel, 1, "AR002", f"второй «ADR» — уже есть {pr.adr_doc.rel}")
                    d.meta = {**d.meta, **mc[0]}   # паспорт комментария — в мету документа
                    pr.adr_doc = d
                    pr.adr = parse_adr(pr, d)
                    pr.issues.extend(pr.adr.meta.pop("_issues"))
                elif kind == "bft-sysreq":
                    if pr.sysreq_doc:
                        pr.err(d.rel, 1, "AR002", f"вторые «Системные требования» — уже есть {pr.sysreq_doc.rel}")
                    d.meta = {**d.meta, **mc[0]}
                    pr.sysreq_doc = d
                    pr.sysreq = parse_sysreq(pr, d)
                    pr.issues.extend(pr.sysreq.meta.pop("_issues"))
                elif kind == "bft-seams":
                    if pr.seams_doc:
                        pr.err(d.rel, 1, "SM002", f"вторые «Стыки» — уже есть {pr.seams_doc.rel}")
                    d.meta = {**d.meta, **mc[0]}   # паспорт комментария — в мету документа
                    pr.seams_doc = d
                    pr.seams = parse_seams(pr, d)
                    pr.issues.extend(pr.seams.meta.pop("_issues"))
                elif kind == "bft-release":
                    if pr.release_doc:
                        pr.err(d.rel, 1, "RL002", f"второй план релиза — уже есть {pr.release_doc.rel}")
                    pr.release_doc = d
                    pr.release = parse_release(pr, d)
                    pr.issues.extend(pr.release.meta.pop("_issues"))
                else:
                    if pr.story_doc:
                        pr.err(d.rel, 1, "BL003", f"вторая история — уже есть {pr.story_doc.rel}")
                    pr.story_doc = d
                    pr.story = bs.parse(f, mc[1])
                    for i in pr.story.issues:
                        pr.issues.append(bb.Issue(i.line + d.off, i.level, i.code, i.msg, d.rel))

    if not pr.map_doc:
        pr.err("", 1, "BL002", "нет документа «Карта» с паспортом <!-- bft-map … --> — `bft-backlog-init.py`")
    else:
        md = pr.map_doc
        for key in MAP_META:
            if not pr.meta.get(key):
                pr.err(md.rel, md.off + 1, "BL002", f"паспорт <!-- bft-map -->: нет ключа `{key}`")
        lines = md.body.split("\n")
        h1 = next((ln for ln in lines if ln.startswith("# ")), "")
        pr.title = re.sub(r"^#\s*(Карта\s*[:·—-]\s*)?", "", h1).strip()
        if not h1:
            pr.err(md.rel, md.off + 1, "BL002", "нет заголовка `# Карта: <инициатива>`")
        secs = bb._sections(lines)
        for name, header in (("Команды", TEAMS_HEADER), ("Вопросы", QUESTIONS_HEADER)):
            if name not in secs:
                pr.err(md.rel, md.off + 1, "BL004", f"нет раздела «## {name}»")
                continue
            ln0, body = secs[name]
            found = bb.tables(body, first_lineno=md.off + ln0 + 1)
            if not found:
                if name == "Команды":
                    pr.err(md.rel, md.off + ln0, "BL004", "«Команды»: нет таблицы")
                continue
            hdr, rows = found[0]
            if name == "Команды" and tuple(hdr) == TEAMS_HEADER_LEAD:
                header = TEAMS_HEADER_LEAD
            if tuple(hdr) != header:
                pr.err(md.rel, md.off + ln0, "BL004", f"«{name}»: заголовок таблицы — {' | '.join(header)}")
                continue
            for ln, c in rows:
                if len(c) != len(header):
                    pr.err(md.rel, ln, "BL004", f"«{name}»: в строке {len(c)} колонок, нужно {len(header)}")
                    continue
                if name == "Команды":
                    tid = c[0].strip()
                    if not TEAM_RE.match(tid) or any(t.id == tid for t in pr.teams) or not c[1].strip():
                        pr.err(md.rel, ln, "BL004", f"команда: ID — латиница-слаг, уникален, название не пусто — «{tid}»")
                        continue
                    lead = c[2].strip() if len(c) > 2 and c[2].strip() not in bb.EMPTY else ""
                    pr.teams.append(Team(tid, c[1].strip(), ln, lead))
                else:
                    qid = bs.norm_question(c[0])
                    if not qid or any(q.id == qid for q in pr.questions):
                        pr.err(md.rel, ln, "BL010", f"вопрос: ID вида В1, уникален — «{c[0]}»")
                        continue
                    pr.questions.append(Question(qid, c[1].strip(), c[2].strip(), c[3].strip().upper(),
                                                 c[4].strip().lower(), c[5].strip(), ln))
    if not pr.story_doc:
        pr.err("", 1, "BL003", "нет документа «История» с <!-- bft-story … --> — `bft-backlog-init.py <epic>-story.md`")
    elif pr.story.errors:
        pr.err(pr.story_doc.rel, 1, "BL003", f"в истории ошибки ({len(pr.story.errors)}) — карта собирается на исправной истории")

    # --- экраны ------------------------------------------------------------------------------------
    sdocs = []
    for d in pr.docs.values():
        if d.meta.get("_kind"):
            continue
        sm = SCREEN_TITLE.match(d.title)
        in_screens = "/docs/screens/" in "/" + d.rel
        if sm:
            sdocs.append(bsn.parse(sm.group(1), d.path, d.body, d.rel, d.off, pr.issues))
        elif in_screens:
            pr.err(d.rel, 2, "SN001", f"документ экрана: заголовок «F3 · Название», а не «{d.title}»")
    if pr.story:
        pr.screens = bsn.check(sdocs, {sc.id for sc in pr.story.screens}, pr.issues)

    # --- задачи --------------------------------------------------------------------------------------
    files = []
    for sub in ("tasks", "completed"):
        if (pr.bdir / sub).is_dir():
            files += sorted((pr.bdir / sub).glob("*.md"))
    raw = [t for t in (_read_task(pr, f) for f in files) if t]
    seen_ids: set[str] = set()
    for t in raw:
        if t.id in seen_ids:
            pr.err(t.rel, 1, "BL005", f"второй файл задачи {t.id} — `backlog doctor`")
            continue
        seen_ids.add(t.id)
        st = _label(t, "stage")
        if not st:
            pr.other += 1
            continue
        t.stage = st[0].upper() if st[0].lower() != FINAL else FINAL
        t.layer = (_label(t, "layer") or [""])[0].lower()
        t.zone = (_label(t, "zone") or [""])[0]
        (pr.cards if _label(t, "layer") else pr.subtasks if _label(t, "zone") else pr.tasks).append(t)
        if len(st) > 1:
            pr.err(t.rel, 1, "BL006", f"{t.id}: меток этапа {len(st)} — одна `stage:<этап>`")
    key = lambda t: (t.ordinal, [int(x) for x in re.findall(r"\d+", t.id)])  # noqa: E731
    pr.tasks.sort(key=key)
    pr.cards.sort(key=key)
    pr.subtasks.sort(key=key)

    stages = ({s.id for s in pr.story.stages} if pr.story else set()) | {FINAL}
    team_ids = {t.id for t in pr.teams}
    task_ids = {t.id for t in pr.tasks}
    card_ids = {c.id for c in pr.cards}
    for t in pr.tasks:
        _check_task(pr, t, stages, team_ids)
    for c in pr.cards:
        _check_card(pr, c, stages, team_ids, task_ids, card_ids)
    for z in pr.subtasks:
        _check_subtask(pr, z, stages, team_ids, task_ids)
    sub_ids = {z.id for z in pr.subtasks}
    seam_ids = {s.id for s in pr.seams.seams} if pr.seams else set()
    for q in pr.questions:
        adr_ids = set()
        if pr.adr:
            adr_ids = {o.id for o in pr.adr.options} | {c.id for c in pr.adr.compromises}
        if pr.sysreq:
            adr_ids |= {c.id for c in pr.sysreq.contracts}
        if q.where not in task_ids | card_ids | sub_ids | adr_ids | seam_ids:
            pr.err(pr.map_doc.rel, q.line, "BL010", f"{q.id}: «Где» — ID задачи, карточки карты ({pr.prefix}-12, {pr.prefix}-12.1), стыка (S1) или этапа ADR (K1, V1, C1), а не «{q.where}»")
        if q.kind not in Q_TYPES:
            pr.err(pr.map_doc.rel, q.line, "BL010", f"{q.id}: тип «{q.kind}» — вопрос или блокер")
        if not q.to or not q.text:
            pr.err(pr.map_doc.rel, q.line, "BL010", f"{q.id}: нужны «Кому» и «Вопрос»")
    for t in pr.tasks + pr.cards + pr.subtasks:
        for d in t.docs:
            if re.match(r"^doc-\d+", str(d), re.I) and str(d).split()[0].lower() not in {k.lower() for k in pr.docs}:
                pr.err(t.rel, 1, "BL011", f"{t.id}: документа {d} нет в backlog/docs")
    return pr

def _check_task(pr: Project, t: BTask, stages: set, team_ids: set) -> None:
    rel = t.rel
    if pr.story and t.stage not in stages:
        pr.err(rel, 1, "BL006", f"{t.id}: этап «{t.stage}» — ID этапа истории или `стало` (метка stage:F)")
    if t.parent:
        pr.err(rel, 1, "BL006", f"{t.id}: задача «Что делаем» — без родителя; карточка «Как это работает» — с меткой layer:…")
    kinds = [x for x in t.labels if x.lower() in KINDS]
    if len(kinds) != 1:
        pr.err(rel, 1, "BL006", f"{t.id}: вид — одна метка из {', '.join(KINDS)}")
    t.kind = kinds[0].lower() if kinds else ""
    who = [str(a).lstrip("@") for a in (t.fm.get("assignee") or [])]
    cand = _label(t, "кандидат")
    if len(who) > 1:
        pr.err(rel, 1, "BL006", f"{t.id}: исполнителей {len(who)} — одна команда на задачу")
    if who:
        t.team = who[0]
        if t.team not in team_ids:
            pr.err(rel, 1, "BL006", f"{t.id}: команды @{t.team} нет в «Командах»; не известна — без исполнителя, метки кандидат:<команда>")
    else:
        t.team = "?"
        names = {x.id: x.name for x in pr.teams}
        t.cand = " или ".join(names.get(c, c) for c in cand)
    for c in cand:
        if c not in team_ids:
            pr.err(rel, 1, "BL006", f"{t.id}: кандидата {c} нет в «Командах»")
    if not who and len(cand) == 1:
        pr.warn(rel, 1, "BL035", f"{t.id}: один кандидат {cand[0]} — это и есть исполнитель: `команда: {cand[0]}`, сомнение — строкой «Вопросов»")
    pre, secs, order = _subsections(t.desc, t.off)
    t.sections = secs
    why = []
    for ln in pre:
        rm = REQS_LINE.match(ln.strip())
        if rm:
            t.reqs = bb.REQ_RE.findall(rm.group(1))
        else:
            why.append(ln)
    t.why = "\n".join(why).strip()
    if not t.why:
        pr.err(rel, t.off, "BL007", f"{t.id}: описание начинается с «зачем» — вклад задачи в цель, одна-две фразы")
    names = [n for _, n in order]
    for n, name in order:
        if name not in BRIEF:
            pr.err(rel, n, "BL007", f"{t.id}: раздел «{name}» — один из {', '.join(BRIEF)}")
    if names != [s for s in BRIEF if s in names] or len(set(names)) != len(names):
        pr.err(rel, t.off, "BL007", f"{t.id}: разделы по порядку, без повторов: " + " → ".join(BRIEF))
    for s in BRIEF:
        if s in BRIEF_OPTIONAL:
            continue
        if s not in secs:
            pr.err(rel, t.off, "BL007", f"{t.id}: нет раздела `### {s}`")
        elif not secs[s][1]:
            pr.err(rel, secs[s][0], "BL007", f"{t.id}: раздел {s} пустой")
    if "HowToDemo" in secs and sum(bool(STEP_RE.match(x.strip())) for x in secs["HowToDemo"][1].split("\n")) < 2:
        pr.err(rel, secs["HowToDemo"][0], "BL007", f"{t.id}: HowToDemo — нумерованный сценарий хотя бы из двух шагов «1. …»")
    if not t.ac:
        pr.err(rel, 1, "BL007", f"{t.id}: нет критериев приемки (Acceptance Criteria) — `backlog task edit {t.id} --ac …`")


def _check_subtask(pr: Project, z: BTask, stages: set, team_ids: set, task_ids: set) -> None:
    """Подзадача истории по зоне: родитель — история, одна зона из ZONES, этап истории,
    исполнитель — команда зоны (неизвестна — метки кандидат:, как у истории), описание — что сделать."""
    rel = z.rel
    zones = _label(z, "zone")
    canon = {x.lower(): x for x in ZONES}
    if len(zones) != 1 or zones[0].lower() not in canon:
        pr.err(rel, 1, "BL043", f"{z.id}: зона — одна метка zone: из {', '.join(ZONES)}")
    else:
        z.zone = canon[zones[0].lower()]
    if z.parent not in task_ids:
        pr.err(rel, 1, "BL043", f"{z.id}: родитель — история «Что делаем» (`backlog task create -p {pr.prefix}-12 …`), а не «{z.parent or '—'}»")
    par = pr.task(z.parent)
    if pr.story and z.stage not in stages:
        pr.err(rel, 1, "BL043", f"{z.id}: этап «{z.stage}» — ID этапа истории или `стало`")
    elif par and z.stage != par.stage:
        pr.err(rel, 1, "BL043", f"{z.id}: этап {z.stage}, а у истории {par.id} — {par.stage}: подзадача живёт на этапе своей истории")
    who = [str(a).lstrip("@") for a in (z.fm.get("assignee") or [])]
    cand = _label(z, "кандидат")
    if len(who) > 1:
        pr.err(rel, 1, "BL043", f"{z.id}: исполнителей {len(who)} — одна команда на подзадачу")
    if who:
        z.team = who[0]
        if z.team not in team_ids:
            pr.err(rel, 1, "BL043", f"{z.id}: команды @{z.team} нет в «Командах»")
    else:
        z.team = "?"
        names = {x.id: x.name for x in pr.teams}
        z.cand = " или ".join(names.get(c, c) for c in cand)
    for c in cand:
        if c not in team_ids:
            pr.err(rel, 1, "BL043", f"{z.id}: кандидата {c} нет в «Командах»")
    z.lead = z.desc.strip()
    if not z.lead:
        pr.err(rel, z.off or 1, "BL043", f"{z.id}: описание — что сделать в своей зоне, одна-две фразы")


VAGUE_LANE = re.compile(r"^(система|сервис|приложение|бэкенд|backend|фронтенд|frontend|платформа|модуль)$", re.I)


def _norm_title(t: str) -> str:
    return re.sub(r"[^\w]+", " ", t.lower().replace("ё", "е")).strip()


def _check_card(pr: Project, c: BTask, stages: set, team_ids: set, task_ids: set, card_ids: set) -> None:
    rel = c.rel
    if pr.story and c.stage not in stages:
        pr.err(rel, 1, "BL008", f"{c.id}: этап «{c.stage}» — ID этапа истории или `стало`")
    layers = _label(c, "layer")
    if len(layers) != 1 or c.layer not in LAYERS:
        pr.err(rel, 1, "BL008", f"{c.id}: слой — одна метка layer: из {', '.join(LAYERS)}")
    if c.parent not in task_ids:
        pr.err(rel, 1, "BL008", f"{c.id}: родитель — задача «Что делаем» (`backlog task create -p {pr.prefix}-12 …`), а не «{c.parent or '—'}»")
    who = [str(a).lstrip("@") for a in (c.fm.get("assignee") or [])]
    par = pr.task(c.parent)
    c.team = who[0] if who else (par.team if par else "?")
    if who and who[0] not in team_ids:
        pr.err(rel, 1, "BL008", f"{c.id}: команды @{who[0]} нет в «Командах»")
    pre, secs, order = _subsections(c.desc, c.off)
    c.sections = secs
    c.lead = "\n".join(pre).strip()
    names = [n for _, n in order]
    for n, name in order:
        if name not in CARD:
            pr.err(rel, n, "BL009", f"{c.id}: раздел «{name}» — один из {', '.join(CARD)}; ссылки — documentation и references задачи")
    if names != [x for x in CARD if x in names] or len(set(names)) != len(names):
        pr.err(rel, c.off, "BL009", f"{c.id}: разделы по порядку, без повторов: " + " → ".join(CARD))
    for name in CARD_REQUIRED:
        if name not in secs or not secs[name][1].strip():
            pr.err(rel, secs.get(name, (c.off,))[0], "BL009", f"{c.id}: нет раздела `### {name}`")
    if "UserStory" in secs:
        c.user_story = secs["UserStory"][1].strip()
        if c.user_story and not re.match(r"^Как .+,\s*я хочу .+,\s*чтобы .+", c.user_story.replace("**", ""), re.S):
            pr.warn(rel, secs["UserStory"][0], "BL030", f"{c.id}: UserStory — «Как <роль>, я хочу <действие>, чтобы <ценность>»")
        role = re.match(r"^Как\s+(.+?),\s*я хочу", c.user_story.replace("**", ""))
        if role:
            r = role.group(1).lower()
            teams = {t.id.lower() for t in pr.teams} | {t.name.lower() for t in pr.teams}
            if re.search(r"\bкоманд|разработ|исполнител", r) or r in teams:
                pr.warn(rel, secs["UserStory"][0], "BL033", f"{c.id}: UserStory от лица исполнителя «{role.group(1)}» — роль: тот, кто пользуется результатом (гость, официант, PO)")
    if "JobStory" in secs:
        c.job_stories = [re.sub(r"^[-*]\s+", "", x.strip()) for x in secs["JobStory"][1].split("\n") if re.match(r"^\s*[-*]\s+\S", x)]
        if secs["JobStory"][1].strip() and not c.job_stories:
            pr.err(rel, secs["JobStory"][0], "BL009", f"{c.id}: JobStory — список «- Когда …, хочу …, чтобы …»")
        for js in c.job_stories:
            if re.match(r"^Когда [А-ЯЁ][а-яё]", js.replace("**", "")):
                pr.warn(rel, secs["JobStory"][0], "BL030", f"{c.id}: JobStory «{js[:40]}…» — после «Когда» строчная буква: «Когда нужно …», «Когда распространитель …»")
            if not re.match(r"^Когда .+,\s*хочу .+,\s*чтобы .+", js.replace("**", "")):
                pr.warn(rel, secs["JobStory"][0], "BL030", f"{c.id}: JobStory «{js[:40]}…» — «Когда …, хочу …, чтобы …»")
    if "Параметры" in secs:
        parse_params(pr, c, *secs["Параметры"])
        if not c.params.get("out"):
            pr.err(rel, secs["Параметры"][0], "BL009", f"{c.id}: у функции нет выхода — `- **Выход:** …`")
    if "Процесс" in secs:
        parse_process(pr, c, *secs["Процесс"])
        builders = [ln for ln in lanes_of(c.proc) if PROJECT_ROLE.match(ln.strip())]
        if builders:
            pr.warn(rel, secs["Процесс"][0], "BL034", f"{c.id}: в процессе участвует {', '.join(builders)} — это работа над проектом, а карточка "
                    "показывает, как сервис работает после запуска: участники — пользователь, сотрудник, система")
        vague = [ln for ln in lanes_of(c.proc) if VAGUE_LANE.match(ln.strip())]
        if vague:
            pr.warn(rel, secs["Процесс"][0], "BL040", f"{c.id}: участник «{vague[0]}» без имени — назови систему, как её зовут в БФТ или в «Механизме»: «Реестр продаж», «Каталог UnitB»")
    if par and _norm_title(c.title) == _norm_title(par.title):
        pr.warn(rel, 1, "BL039", f"{c.id}: карточка названа как задача {par.id} — карточка говорит, что происходит в работающем сервисе: «Официант сканирует билет — сразу видит ответ»")
    if "HowToDemo" in secs and sum(bool(STEP_RE.match(x.strip())) for x in secs["HowToDemo"][1].split("\n")) < 2:
        pr.err(rel, secs["HowToDemo"][0], "BL009", f"{c.id}: HowToDemo — хотя бы два шага «1. …»")
    if "BPMN" in secs:
        mm = MERMAID.search(secs["BPMN"][1])
        c.mermaid = f"```mermaid\n{mm.group(1)}\n```" if mm else secs["BPMN"][1]
    for key, items in c.params.items():
        for it in items:
            for r in it.refs:
                if r == c.id or r not in card_ids:
                    pr.err(rel, secs["Параметры"][0], "BL009", f"{c.id}: ссылка {r} в «{PARAM_NAME[key]}» — на другую карточку «Как это работает»")

def sync_schema(pr: Project, write: bool) -> list[BTask]:
    """BPMN карточек — mermaid из «Процесса». Возвращает карточки, где блок устарел; write — переписать.
    Прежний блок `### IDEF0` при переписывании убирается: схему функции заменила схема процесса."""
    stale = []
    for c in pr.cards:
        if not c.proc:
            continue
        want = bpmn_of(c)
        if c.mermaid.strip() == want and "### IDEF0" not in c.desc:
            continue
        stale.append(c)
        if not write:
            continue
        text = c.path.read_text(encoding="utf-8")
        a = text.index("<!-- SECTION:DESCRIPTION:BEGIN -->") + len("<!-- SECTION:DESCRIPTION:BEGIN -->\n")
        b = text.index("<!-- SECTION:DESCRIPTION:END -->")
        desc = re.sub(r"^### IDEF0\n.*?(?=^### |\Z)", "", text[a:b], flags=re.S | re.M)
        block = f"### BPMN\n{want}\n"
        if re.search(r"^### BPMN\n", desc, re.M):
            desc = re.sub(r"^### BPMN\n.*?(?=^### |\Z)", lambda _: block + "\n", desc, count=1, flags=re.S | re.M)
        elif re.search(r"^### HowToDemo\n", desc, re.M):
            desc = re.sub(r"^### HowToDemo\n", lambda _: block + "\n### HowToDemo\n", desc, count=1, flags=re.M)
        else:
            desc = desc.rstrip("\n") + "\n\n" + block
        c.path.write_text(text[:a] + desc.rstrip("\n") + "\n" + text[b:], encoding="utf-8")
        c.mermaid = want
    return stale

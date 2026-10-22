# poh-blueprint-writer

Навыки `/bft-blueprint`, `/adr` и `/system-requirements` для Claude Code и других IDE-агентов.
По готовому БФТ они собирают общую картину кроссфункциональной инициативы — Service Blueprint —
в два согласуемых этапа и этап системной проработки. Все страницы — HTML без `npm` и CDN.

Навыки вынесены из [poh-bft-writer](https://github.com/po-helper-org/poh-bft-writer). Тот пишет БФТ,
а эти читают готовый БФТ и раскладывают его в карту. Ставятся рядом, в один `<skills_path>`.

## Что получается

**Этап 1 — история через экраны.** Простая нетехническая история: что инициатива меняет
для каждого, кто будет ей пользоваться. Каждый персонаж — ряд, который читается слева
направо: «Знакомьтесь» → шаги → «И с тех пор». Карточка шага — упрощённый экран, контур
(витрина, письмо, SMS, приложение), заголовок и пояснение; красная точка — открытый вопрос.
Где БФТ молчит, агент сам задаёт PO один раунд вопросов с вариантами из БФТ. Стандарт —
[`resources/story_line.md`](skills/bft-blueprint/resources/story_line.md).

**Этап 2 — карта инициативы**, после согласования истории. Карта живёт в проекте
[Backlog.md](https://github.com/MrLesk/Backlog.md) `<epic>-blueprint/`. Агент исследует БФТ и
раскладывает его в бэклог встроенным CLI `./backlog.py`:

- **«Что делаем»** — задачи: один результат одной команды, постановка для техлида
  (ASIS, GAP, TOBE, HowToDemo, критерии приемки);
- **«Как это работает»** — их подзадачи, технические карточки в слоях Employee Actions,
  Technology, Backstage, Support: UserStory, JobStory, «Параметры», «Процесс» и его схема BPMN
  (текст mermaid в файле карточки), HowToDemo, ссылки;
- **документы** — паспорт карты с командами и вопросами, история, требования к экранам для дизайнера.
  Картинки экранов лежат файлами в `backlog/assets/screens/`.

**Этап «ADR и Системные требования»** — после раскладки задач, когда работа затрагивает устройство
систем (на карте есть карточки слоя Technology). Два документа проекта:

- **«ADR»** (`<!-- bft-adr … -->`) — системный дизайн: контекст, ландшафт AS-IS, варианты
  реализации (не меньше двух, оценки по трём осям), решение TO-BE с явным обоснованием,
  узкие места по нагрузке и надёжности, компромиссы по оси «надёжность vs скорость реализации
  vs соответствие требованиям» и ADR-диаграмма AS-IS/TO-BE (mermaid);
- **«Системные требования»** (`<!-- bft-sysreq … -->`) — системная аналитика: по каждому
  контракту из решения TO-BE три вопроса — (1) какие данные нужны контракту, (2) источник
  каждого параметра (система/сервис/поле/справочник), (3) какие преобразования над данными
  нужны для контрактов и бизнес-логики; дальше AS-IS, изменения и открытые вопросы.

Оба документа видны на странице карты как слой «Архитектура» (кнопка в переключателе слоёв
и пункт меню — появляются только когда документы есть). Секции плана «Решение TO-BE»,
«Варианты», «Узкие места», «Компромиссы», «Контракты» раскладываются apply'ем и возвращаются
export'ом; проверки — коды AR001–AR005. Шаблоны — `templates/adr.md`, `templates/sysreq.md`.

Для этапа есть два отдельных навыка-промпта — ставятся вместе с `/bft-blueprint`:

- **`/adr`** ([`skills/adr/`](skills/adr/)) — системный дизайн: пишет документ «ADR» из БФТ
  и описания IT-ландшафта. Обязателен выбор из ≥2 вариантов по осям «надёжность / скорость
  реализации / соответствие требованиям», явные риски и компромиссы, узкие места
  с прощупыванием, диаграмма AS-IS/TO-BE. Контракты TO-BE — слагами латиницей;
- **`/system-requirements`** ([`skills/system-requirements/`](skills/system-requirements/)) —
  системная аналитика: документ «Системные требования» из контрактов решения TO-BE.
  По каждому контракту три обязательных вопроса: какие данные нужны, откуда взять каждый
  параметр (система/сервис/поле/справочник), какие преобразования нужны. Вопросы — с вариантами,
  а не выдумывание; неизвестное — `[УТОЧНИТЬ: …]` владельцу.

Живой пример этапа на реальном Blueprint — демо `basis-event-replace` (замена мероприятия
в БАЗИС: «Идиот» становится «Вишнёвым садом»): ADR с вариантами «правка сеанса /
отмена + перенос / как сейчас» и контрактами `session-replace`, `event-replace-notification`,
`session-sync`; системные требования к этим трём контрактам; слой «Архитектура» на странице
карты — вкладки ADR и «Системные требования», диаграмма AS-IS/TO-BE.

Страницу `<epic>-map.html` и архив `<epic>-blueprint.zip` скрипт собирает из проекта
детерминированно. Текст на странице берётся только из файлов проекта, иначе сборка падает.
Папка проекта и архив автономны. Внутри:

- `./backlog.py` — встроенный CLI Backlog.md;
- `./blueprint.py build` — сборка страницы и архива;
- скрипты, правила и mermaid;
- инструкции агенту: CLAUDE.md, AGENTS.md, GEMINI.md.

Любому харнессу хватает python3. Стандарт — [`resources/backlog_rules.md`](skills/bft-blueprint/resources/backlog_rules.md),
эталон — [`examples/dineclub-restart-blueprint/`](skills/bft-blueprint/examples/dineclub-restart-blueprint)
и его страница [`examples/dineclub-restart-map.html`](skills/bft-blueprint/examples/dineclub-restart-map.html).

Пошагово, от БФТ до карты, — [`docs/step-by-step.md`](docs/step-by-step.md).

## Автопилот: один промпт

`/bft-blueprint <epic> --auto` — история и карта за один заход без вопросов PO. Маршрут для агента —
[`resources/autopilot.md`](skills/bft-blueprint/resources/autopilot.md):

1. инвентарь БФТ — `bft-reqs.py`;
2. история по шаблону;
3. проект Backlog.md;
4. план карты одним файлом `plan/map.md`: каркас `./blueprint.py skeleton` раскладывает БФТ сам —
   задача на каждое ФТ, правила, параметры и критерии приёмки дословно; места для текста `{{…}}`
   заполняет рой агентов по пакету на блок (`groom fill`);
5. `./blueprint.py apply` — до нуля ошибок, с адресом строки плана и подсказкой к каждому коду;
6. рубрика качества и сводка `./blueprint.py next`; для глубины — груминг роем агентов
   `./blueprint.py groom audit|refine|merge` ([`resources/grooming.md`](skills/bft-blueprint/resources/grooming.md));
7. сборка.

Решения сведены в таблицы, форма — в шаблоны, проверки — в скрипты: маршрут рассчитан на модели
уровня Haiku и Sonnet.

## Установка

Из корня воркспейса, где уже стоит poh-bft-writer:

```bash
curl -fsSL https://raw.githubusercontent.com/po-helper-org/poh-blueprint-writer/main/install.sh | bash
```

Или из клона: `bash install.sh`. Агент выбирается так же, как в poh-bft-writer:
`BLUEPRINT_WRITER_AGENT=1..5` (по умолчанию 1 — Claude Code, `.claude/`).

## Запуск

```
/bft-blueprint <epic_slug|путь> [вводная] [--story | --map | --layers]
/adr [epic_slug|путь]            # документ «ADR»: варианты, TO-BE, узкие места, компромиссы
/system-requirements [epic_slug|путь]  # документ «Системные требования»: контракты → источники → преобразования
```

Скрипты вручную:

```bash
python3 <skills_path>/bft-blueprint/scripts/bft-story-lint.py .bft/documentation/<epic_slug>/<epic_slug>-story.md
python3 <skills_path>/bft-blueprint/scripts/bft-story-render.py .bft/documentation/<epic_slug>/<epic_slug>-story.md
python3 <skills_path>/bft-blueprint/scripts/bft-backlog-init.py .bft/documentation/<epic_slug>/<epic_slug>-story.md
python3 <skills_path>/bft-blueprint/scripts/bft-backlog-lint.py .bft/documentation/<epic_slug>/<epic_slug>-blueprint --source .bft/documentation/<epic_slug>/<epic_slug>.md
python3 <skills_path>/bft-blueprint/scripts/bft-backlog-build.py .bft/documentation/<epic_slug>/<epic_slug>-blueprint --source .bft/documentation/<epic_slug>/<epic_slug>.md
```

## Самотест

```bash
bash skills/bft-blueprint/scripts/test-bft-blueprint.sh
```

Тот же самотест идёт в CI на каждый PR.

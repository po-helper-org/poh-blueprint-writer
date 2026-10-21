# Команда «Прототип»: Design First демо из Blueprint

Статус: проект. Расширение `/bft-blueprint`: к истории и карте добавляются контракты и интерактивный прототип.

## Идея в одной строке

LLM не пишет код и не выбирает компоненты. Она заполняет **один декларативный файл `prototype/spec.yml`** по таблицам и шаблонам, а **скрипт детерминированно** собирает из него docker-compose с фронтом, админкой и MockAPI. Решений, которые надо «обдумывать», не остаётся: экран = список блоков из каталога, API = запись в контракте, поведение = пример ответа.

```
БФТ → story → карта (Backlog.md) → contracts/ → prototype/spec.yml → ./blueprint.py prototype → docker compose up
                                      ▲ Design First: контракты раньше экранов; экран не может сослаться на то, чего нет в контракте
```

## Команды

| Команда | Что делает | Кто решает |
|---|---|---|
| `./blueprint.py contracts` | каркас `contracts/` из карточек карты: интеграции, параметры «Вход/Выход», внешние вызовы | скрипт; LLM заполняет `{{…}}` |
| `./blueprint.py contracts lint` | проверка стыков (см. ниже) | скрипт |
| `./blueprint.py spec` | каркас `prototype/spec.yml`: по шагу истории — один шаг прототипа | скрипт; LLM заполняет |
| `./blueprint.py prototype` | сборка `prototype/` + `docker-compose.yml` | скрипт, без LLM |
| `/bft-blueprint <epic> --prototype` | весь маршрут выше + `prototype lint` | агент |

## 1. Контракты (`contracts/`) — главный артефакт Design First

Один файл на границу системы, формат фиксированный (OpenAPI-lite, YAML), шаблон `templates/contract.yml`:

```yaml
id: C-3                         # ссылка из карточек карты: (C-3)
title: Партнёр проверяет билет
boundary: external              # external | frontend-backend | service-service | service-db
caller: Партнёрское приложение  # кто вызывает
callee: Ticket Service          # кто отвечает
op: POST /v1/tickets/{id}/verify
request:                        # поле | тип | обяз. | откуда (источник в БФТ/ФТ)
  - {name: id,      type: string, req: true, in: path,  src: ФТ-4}
  - {name: partner, type: string, req: true, in: body,  src: ФТ-4}
response:
  ok:    {status: 200, example: {valid: true, discount: 10}}
  error: [{status: 404, code: TICKET_NOT_FOUND}, {status: 409, code: ALREADY_USED}]
sequence: [                     # обязательный вход для Sequence-диаграммы
  "Партнёр -> Ticket Service: verify(id, partner)",
  "Ticket Service -> Catalog: getPromo(ticket.event)",
  "Catalog --> Ticket Service: promo",
  "Ticket Service --> Партнёр: valid, discount"
]
chain:                          # трансформации для backend-вызовов, шаг за шагом
  - {step: 1, in: "id, partner", do: "найти билет", out: "ticket{event,used}"}
  - {step: 2, in: "ticket.event", do: "запросить акцию у Catalog", out: "promo{discount}"}
data: [{store: tickets, need: "id, event, used"}]   # БД: только «какие данные нужны»
```

Правила, которые проверяет `contracts lint`:

- **CT01** у каждой карточки карты с обращением к другой системе есть `(C-N)`; у каждого контракта есть карточка.
- **CT02** `external`-контракт обязан иметь `request`, `response.ok`, минимум одну ошибку, `example`.
- **CT03** каждое поле `request` и `response` имеет `src` — ссылку на ФТ/ИТ или `[УТОЧНИТЬ у …]`; полей «от фонаря» нет.
- **CT04** `sequence` ссылается только на системы, названные в карте; каждая стрелка вызова имеет ответную стрелку.
- **CT05** `chain`: `in` шага N ⊆ `out` шага N−1 или `request`; последний `out` покрывает `response.ok`. Так проверяется цепочка трансформаций данных.
- **CT06** `service-db`: только `store` и `need` (список полей). Таблицы, индексы, DDL — запрещены (высота БФТ, `BL018`).
- **CT07** каждое поле на экране прототипа привязано к полю ответа контракта (проверка в `prototype lint`).

## 2. Спецификация прототипа (`prototype/spec.yml`)

Шаг прототипа = шаг истории. Тип шага — из четырёх, ничего другого:

| kind | Что видит зритель | Откуда данные |
|---|---|---|
| `ui` | экран на готовых блоках | `screen:` |
| `api` | экран + панель: Sequence, метод, поля запроса/ответа | `contract: C-N` |
| `backend` | для фронта только вход/выход; в панели — `chain` по шагам, вход/выход каждого сервиса | `contract: C-N` |
| `data` | упрощённая схема «какие данные нужны из хранилища» | `data:` контракта |

```yaml
steps:
  - id: Ш3
    kind: api
    app: client                  # client | admin | external
    screen:
      layout: form-page          # из каталога, 6–8 раскладок
      blocks:
        - {c: heading,  text: "Проверка билета"}
        - {c: input,    label: "Номер билета", bind: request.id}
        - {c: button,   text: "Проверить", action: {call: C-3}}
        - {c: result,   show: response.ok, fields: [valid, discount]}
        - {c: error,    show: response.error}
    note: "Что видит гость и что хотим от этого шага"
```

**Каталог компонентов — закрытый** (`prototype/catalog.md`, ~14 блоков): `heading, text, input, select, button, table, card, list, stat, tabs, form, result, error, banner, steps`. Раскладки: `landing, form-page, list-detail, dashboard, wizard, confirm`. Агент выбирает **из таблицы «тип данных → блок»**, а не изобретает:

| Что показываем | Блок |
|---|---|
| один ввод | `input` / `select` |
| набор записей | `table` (админка) или `list` (клиент) |
| число/статус | `stat` |
| результат вызова | `result` + `error` |

Нет подходящего блока — агент пишет `{c: text, text: "[УТОЧНИТЬ дизайн]"}`, а не придумывает новый. Это и делает результат стабильным даже для Haiku: заполняются перечисления и короткие строки, а не код.

## 3. Что собирает `./blueprint.py prototype`

```
prototype/
  docker-compose.yml        # 3 сервиса: web, admin, api
  web/                      # статика: index.html + runtime.js + components.css (без npm, без CDN)
  admin/                    # тот же runtime, другой набор шагов (app: admin)
  api/main.py               # FastAPI в одном файле; роуты генерируются из contracts/
  spec.json                 # compiled spec — единственный вход рантайма
```

- **MockAPI** отдаёт `response.ok.example` по контракту; ошибки включаются переключателем в панели шага (покажем и 409). Состояния нет, БД нет, максимум — счётчик/список в памяти для «ощущения жизни».
- **runtime.js** (один файл, vanilla) рисует блоки по каталогу, ведёт StepByStep: слева шаги, по центру экран, справа панель контракта. Mermaid `sequence` берётся из `vendor/mermaid.min.js`, уже лежащего в проекте.
- **Панель контракта** для `api`: Sequence, метод, таблица полей «запрос / ответ / откуда в БФТ», живой запрос-ответ из MockAPI. Для `backend`: цепочка `chain` с входами/выходами. Для `data`: список «хранилище → нужные поля».
- Сторона `external` показывается как отдельная «приложение-заглушка» с кнопкой «Отправить запрос», чтобы был виден вызов нашей системы снаружи.

## 4. Замечания по клику (как в bft-writer)

- Режим «Замечания»: клик по любой точке экрана → пин с координатами `(x, y)`, `step`, ближайший блок (`block-id` из `data-block`), поле для текста.
- Пины сохраняются в `localStorage` и экспортируются в `prototype/review.md` + `review.json` (шаг, блок, контракт, текст).
- `./blueprint.py review import` превращает пины в вопросы карты (красные точки на нужной карточке/контракте) — замкнутый цикл «замечание → правка spec → пересборка».

## 5. Почему это сработает на Haiku

1. Вход агента — заполненный каркас с `{{…}}`: контракты и шаги уже разложены из карты скриптом (как `skeleton` для карты сегодня).
2. Свободный текст — только названия, подписи, `note`; остальное — выбор из перечислений.
3. Пакет на один шаг/контракт (`groom fill` уже умеет пакеты на блок) — маленький контекст.
4. Любая ошибка ловится `lint` с кодом и подсказкой; агент чинит до нуля ошибок.
5. Сборка прототипа вообще без LLM — одинаковый результат на любой модели.

## План реализации (по PR)

1. `templates/contract.yml`, `resources/contracts.md`, `contracts lint` (CT01–CT07) + фикстуры и пример в DineClub.
2. `skeleton` для контрактов и spec из карточек карты; `groom fill` для них.
3. `catalog.md`, `spec` lint, `runtime.js` + `components.css`, генерация статики.
4. Генерация `api/main.py` + `docker-compose.yml`; smoke-тест «compose up → все шаги отдают 200».
5. Панель контракта: Sequence, поля, chain, data.
6. Режим замечаний и `review import`.
7. `--prototype` в SKILL.md, README, `docs/step-by-step.md`.

## Открытые вопросы к PO

1. Источник схем: хватит ли OpenAPI-lite из нашего YAML, или нужен экспорт в настоящий `openapi.yaml` для передачи разработке (проще всего — генерировать его из `contracts/`)?
2. Админка: один общий набор блоков с клиентом или отдельная тема оформления?
3. Docker обязателен для показа заказчику, или нужен ещё вариант «один HTML без сервера» (MockAPI в браузере) как запасной?

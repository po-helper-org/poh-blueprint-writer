# Сервис Blueprint

Веб-раздел и MCP-сервер поверх навыков этого репозитория: **все Service Blueprint диаграммы воркспейса
в одном списке, поэтапная работа над каждой и управление из любого ИИ-агента**. Сделан по образцу
«Управления требованиями» (виджет БФТ и MCP «Система БФТ» портала): тот же визуал poh-ds, тот же гейт,
та же модель «текст пишет агент — сервис хранит, проверяет и собирает».

Вход — из меню **☰** оболочки отчётов по спринту `/sprints/` («Сервис Blueprint») или напрямую `/blueprint/`.

## Интерфейс

1. **Список** `/blueprint/` — диаграммы воркспейса: название, эпик, дата, следующий этап. Поиск.
2. **Создать** — окно с инструкцией для ИИ-агента: выбрать БФТ, способ (MCP или навык в чате), «Копировать».
3. **Диаграмма** `/blueprint/<эпик>` — открывается в новой вкладке: сама страница карты, собранная скриптами
   навыка по шаблонам методологии (пока карты нет — страница истории).

Этапы и следующий шаг сервис считает по артефактам на диске (БФТ → история → карта → ADR и СТ → стыки →
сверка → план релиза → прототип → Confluence); подробно они видны агенту через MCP.

## MCP «Система Blueprint»

Тот же источник данных для любого агента. Текст пишет модель агента, сервис проверяет и собирает.

| Инструмент | Что делает |
|---|---|
| `blueprint_list` | диаграммы с этапами и следующим шагом; БФТ без диаграммы |
| `blueprint_get` | все этапы эпика: статус, чего не хватает, команда, действия |
| `blueprint_guide` | как делать этап: что прочитать (ресурсы `blueprint://`), как писать, чем проверить |
| `blueprint_read` | `bft`, `story`, `plan` (каркас создаётся сам), `map`, `doc:<вид>`, `contract:C-N`, `file:<путь>` |
| `blueprint_submit_story` | история → `bft-story-lint` → страница; ошибки — в ответе |
| `blueprint_submit_plan` | план `plan/map.md` (+ экраны) → `./blueprint.py apply`: задачи, карточки, документы, ошибки по строкам плана |
| `blueprint_submit_doc` | ADR, Системные требования, Стыки, План релиза, Roadmap, Риски, Расхождения → проверка карты |
| `blueprint_submit_contract` | контракт `contracts/C-N.md` → `./blueprint.py contracts` |
| `blueprint_run` | `story_render`, `story_approve`, `init_map`, `skeleton`, `apply`, `next`, `lint`, `build`, `verify`, `contracts`, `reconcile`, `reqs`, `confluence_page` |
| `blueprint_questions`, `blueprint_answer` | вопросы «Карты» и запись ответа |
| `blueprint_start_agent`, `blueprint_job` | фоновый агент сервиса (если настроен) |

Ресурсы — навыки, правила (`resources/`), шаблоны (`templates/`) и эталоны `bft-blueprint`; промт
`blueprint_full_cycle` ведёт агента от БФТ до отгруженной карты. Согласование истории и ответы на вопросы —
только со слов PO: это записано в инструкциях сервера и описаниях инструментов.

Подключение:

```sh
# удалённо — Streamable HTTP, личный токен из mcp_tokens_file
claude mcp add --transport http blueprint https://<хост>/blueprint/mcp --header "Authorization: Bearer <токен>"
# на той же машине — stdio, без токена
claude mcp add blueprint -- python3 /путь/к/poh-blueprint-writer/service/server.py mcp
```

## Запуск

Только стандартная библиотека Python 3.10+ — как и скрипты навыка.

```sh
cp service/config.example.json ~/.config/poh-blueprint/config.json   # workspace, docs_path, gate_mode
python3 service/server.py list      # проверка: какие диаграммы видит сервис
python3 service/server.py           # http://127.0.0.1:8662/blueprint/
python3 -m unittest discover -s service/tests -t service
```

Без файла настроек: `BLUEPRINT_WORKSPACE=~/ws BLUEPRINT_GATE=none python3 service/server.py` — только на 127.0.0.1.

| Ключ | Умолчание | Что |
|---|---|---|
| `workspace` | `.` | корень воркспейса: там запускается агент, от него пути в командах |
| `docs_path` | `.bft/documentation` или `bft/documentation` | каталог эпиков |
| `skills_path` | `skills/` репозитория | откуда скрипты, правила и шаблоны навыков |
| `gate_mode` | `none` | `corp` — за nginx с гейтом (`X-Corp-Gate`), `basic` — HTTP Basic из `BLUEPRINT_USER`/`BLUEPRINT_PASSWORD`, `none` — только 127.0.0.1 |
| `mcp_tokens_file` | `~/.config/poh-blueprint/mcp-tokens` | строки `имя:токен`; файл 600, значения не печатаются |
| `agent` | нет | `{"command": [..., "{prompt}", ...], "timeout": 3600}` — фоновый агент; без него — только черновики |

## Сервер

`bash service/deploy/install.sh` (с `BLUEPRINT_WORKSPACE=…` при первой установке): тесты, настройки, токен MCP,
юнит `poh-blueprint.service` (127.0.0.1:8662). nginx — шаг владельца: сниппет `deploy/poh-blueprint.nginx.conf`
в `server{}` корп-браузера, рядом с `/sprints/`.

## Безопасность

- API — только за гейтом; POST — с заголовком `X-Blueprint: 1` (защита от CSRF).
- Страницы карты и истории отдаются в песочнице CSP `sandbox` без same-origin: их скрипты не видят ни куки, ни API.
  Картинки экранов сервис встраивает в страницу `data:` URI — из песочницы куки гейта не уходят. Цена песочницы:
  локальные отметки на странице карты (чек-листы, черновики замечаний) не сохраняются между открытиями.
- Слаг эпика проверяется, пути к файлам — только внутри каталога эпика или проекта карты.
- MCP по HTTP — только с личным токеном; по stdio — права того, кто запустил процесс.

# poh-blueprint-writer

Навык `/bft-blueprint` для Claude Code и других IDE-агентов. По готовому БФТ он собирает общую картину
кроссфункциональной инициативы — Service Blueprint — в два согласуемых этапа. Обе страницы —
HTML без `npm` и CDN.

Навык вынесен из [poh-bft-writer](https://github.com/po-helper-org/poh-bft-writer). Тот пишет БФТ,
а этот читает готовый БФТ и раскладывает его в карту. Ставятся рядом, в один `<skills_path>`.

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

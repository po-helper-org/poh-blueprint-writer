---
description: 'Отгрузить в Confluence: Service Blueprint дочерней страницей под страницей первичных БФТ — этапы, «Что делаем», «Как это работает», «Расхождения с требованиями», вопросы, карта и архив проекта вложениями; повтор обновляет ту же страницу. Используй когда — отгрузить в Confluence, опубликовать карту, выложить blueprint в вики, /bft-confluence'
---

## Использование

```
/bft-confluence <epic>-blueprint [ссылка или ID страницы БФТ в Confluence]
```

## Что делает

1. `./blueprint.py lint` → 0 ошибок, `./blueprint.py build` — страница карты и архив для вложений.
2. `./blueprint.py confluence --parent <ссылка на БФТ>` — дочерняя страница «Service Blueprint: <инициатива>» под БФТ;
   повтор — без `--parent`, обновляет ту же страницу (ID — в `confluence/publish.json`).
3. Доступ — только переменные окружения `CONFLUENCE_URL`, `CONFLUENCE_TOKEN` (Cloud — ещё `CONFLUENCE_USER`).
   Токен не пиши в файлы, не печатай и не проси вставить в чат.
4. Код 3 — доступа нет, страница собрана локально в `confluence/page.xhtml`. Есть коннектор Confluence — создай
   или обнови им дочернюю страницу БФТ с этим телом (формат storage) и приложи `<epic>-map.html` и `<epic>-blueprint.zip`;
   нет — отдай PO файл и скажи, каких переменных не хватает.
5. Итог — ссылка на страницу и её версия.

Правила — `../skills/bft-blueprint/resources/backlog_rules.md` §«Отгрузка в Confluence».

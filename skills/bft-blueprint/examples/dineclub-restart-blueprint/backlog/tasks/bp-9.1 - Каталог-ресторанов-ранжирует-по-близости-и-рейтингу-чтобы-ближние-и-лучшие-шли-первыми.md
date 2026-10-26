---
id: BP-9.1
title: Каталог ресторанов ранжирует по близости и рейтингу, чтобы ближние и лучшие шли первыми
status: To Do
assignee: []
created_date: '2026-10-19 19:07'
updated_date: '2026-10-26 19:57'
labels:
  - stage:D
  - layer:backstage
dependencies: []
parent_task_id: BP-9
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Для списка каталог ресторанов ставит первыми рестораны у площадки билета, дальше — по близости и рейтингу, с учётом фильтров гостя.

### Параметры
- **Вход:** Каталог участников (BP-2.1); Площадка билета; Выбранные фильтры
- **Управление:** Полный список без радиуса (ФТ-3); Ближние × высокий рейтинг (ФТ-3); Каталог выдерживает 300 ресторанов (НФТ-1)
- **Выход:** Список и данные ресторанов (BP-8.1)
- **Механизм:** Каталог ресторанов

### Процесс
- Витрина: Передаёт активный билет и фильтры
- Каталог UnitB: Ставит площадку билета первой
- Каталог UnitB: Сортирует: ближние × рейтинг
- Витрина: Показывает список

### Данные
- Каталог участников — Каталог UnitB (BP-2.1)
- Площадка билета и фильтры гостя — Витрина

### BPMN
```mermaid
flowchart LR
  subgraph L1["Витрина"]
    S((" "))
    N1["Передаёт активный билет и фильтры"]
    N4["Показывает список"]
    E(((" ")))
  end
  subgraph L2["Каталог UnitB"]
    N2["Ставит площадку билета первой"]
    N3["Сортирует: ближние × рейтинг"]
  end
  S --> N1
  N1 --> N2
  N2 --> N3
  N3 --> N4
  N4 --> E
  classDef start fill:#fff,stroke:#2f6b2a,stroke-width:2px
  classDef stop fill:#fff,stroke:#1c1c1c,stroke-width:4px
  classDef gw fill:#fff8e6,stroke:#b7791f
  classDef ask color:#c0392b,stroke:#c0392b
  class S start
  class E stop
  style L1 fill:#faf9f6,stroke:#d8d4cb
  style L2 fill:#ffffff,stroke:#d8d4cb
```
<!-- SECTION:DESCRIPTION:END -->

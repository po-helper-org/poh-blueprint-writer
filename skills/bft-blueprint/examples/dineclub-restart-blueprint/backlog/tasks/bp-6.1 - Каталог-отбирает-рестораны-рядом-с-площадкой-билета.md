---
id: BP-6.1
title: Каталог отбирает рестораны рядом с площадкой билета
status: To Do
assignee: []
created_date: '2026-10-19 19:07'
updated_date: '2026-10-25 08:20'
labels:
  - stage:B
  - layer:backstage
dependencies: []
parent_task_id: BP-6
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
По площадке активного билета UnitB подбирает рестораны для полки: ближние и с высоким рейтингом.

### UserStory
Как гость, я хочу видеть в полке рестораны рядом с моей площадкой, чтобы дойти пешком.

### JobStory
- Когда у меня билет в конкретный театр, хочу видеть рестораны рядом с ним, чтобы не ехать через город.

### Параметры
- **Вход:** Каталог участников (BP-2.1); Площадка активного билета
- **Управление:** Ближние × высокий рейтинг (ФТ-3); Первыми — у площадки активного билета (ФТ-3)
- **Выход:** Рестораны у площадки (BP-5.1)
- **Механизм:** UnitB; Каталог ресторанов

### Процесс
- Витрина: Передаёт площадку активного билета
- Каталог UnitB: Отбирает рестораны у площадки
- Каталог UnitB: Ранжирует: ближние × рейтинг
- Витрина: Показывает полку

### BPMN
```mermaid
flowchart LR
  subgraph L1["Витрина"]
    S((" "))
    N1["Передаёт площадку активного билета"]
    N4["Показывает полку"]
    E(((" ")))
  end
  subgraph L2["Каталог UnitB"]
    N2["Отбирает рестораны у площадки"]
    N3["Ранжирует: ближние × рейтинг"]
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

### HowToDemo
1. Покупаю билет в театр — полка показывает рестораны у этого театра
2. Ближние и с высоким рейтингом — первыми
<!-- SECTION:DESCRIPTION:END -->

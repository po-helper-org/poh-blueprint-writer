---
id: BP-1.1
title: Кабинет DineClub подключает ресторан без брони, чтобы ресторан попал в каталог
status: To Do
assignee: []
created_date: '2026-10-19 19:07'
updated_date: '2026-10-26 20:13'
labels:
  - stage:A
  - layer:backstage
dependencies: []
documentation:
  - doc-3
parent_task_id: BP-1
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ресторан подаёт заявку и подключается без брони и тяжёлой интеграции: получает доступ к сканеру, инструкцию и FAQ и попадает в каталог.

### Параметры
- **Вход:** Заявка ресторана на участие
- **Управление:** Без брони и тяжёлой интеграции (ФТ-19); Скидка 10%, окно 7 дней, один билет — одна скидка; Москва и Санкт-Петербург
- **Выход:** Ресторан подключён (BP-15.1); Список ресторанов (BP-2.1); Инструкция, FAQ, контакты поддержки
- **Механизм:** Кабинет DineClub; Путь подключения [УТОЧНИТЬ: борда FigJam]

### Процесс
- Ресторан: Подаёт заявку на участие
- Кабинет DineClub: Подключает без брони [УТОЧНИТЬ у DineClub]
- Кабинет DineClub: Выдаёт сканер, инструкцию и FAQ
- Каталог UnitB: Добавляет ресторан в участники

### Данные
- Заявка ресторана на участие — ресторан — подключить ресторан к акции

### BPMN
```mermaid
flowchart LR
  subgraph L1["Ресторан"]
    S((" "))
    N1["Подаёт заявку на участие"]
  end
  subgraph L2["Кабинет DineClub"]
    N2["Подключает без брони [УТОЧНИТЬ у DineClub]"]
    N3["Выдаёт сканер, инструкцию и FAQ"]
  end
  subgraph L3["Каталог UnitB"]
    N4["Добавляет ресторан в участники"]
    E(((" ")))
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
  class N2 ask
  style L1 fill:#faf9f6,stroke:#d8d4cb
  style L2 fill:#ffffff,stroke:#d8d4cb
  style L3 fill:#faf9f6,stroke:#d8d4cb
```
<!-- SECTION:DESCRIPTION:END -->

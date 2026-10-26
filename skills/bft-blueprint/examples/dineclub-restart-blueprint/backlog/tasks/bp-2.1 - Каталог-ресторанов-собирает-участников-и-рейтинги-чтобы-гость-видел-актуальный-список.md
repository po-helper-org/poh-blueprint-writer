---
id: BP-2.1
title: Каталог ресторанов собирает участников и рейтинги, чтобы гость видел актуальный список
status: To Do
assignee: []
created_date: '2026-10-19 19:07'
updated_date: '2026-10-26 19:57'
labels:
  - stage:A
  - layer:backstage
dependencies: []
parent_task_id: BP-2
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Каталог ресторанов собирает участников: список из кабинета DineClub, рейтинги из справочника не реже раза в квартал, часы работы и площадки рядом.

### Параметры
- **Вход:** Список ресторанов (BP-1.1); Рейтинги — выгрузка Яндекс.Карт
- **Управление:** Рейтинг — статичный справочник, не реже раза в квартал (НФТ-2); Часы работы у 100% участников (ФТ-4)
- **Выход:** Каталог участников (BP-6.1, BP-9.1, BP-11.1); Часы работы и площадки (BP-10.1)
- **Механизм:** Каталог ресторанов

### Процесс
- Кабинет DineClub: Передаёт список участников
- Справочник рейтингов: Отдаёт выгрузку рейтингов
- Каталог UnitB: Собирает часы работы и площадки рядом
- ? Часы работы есть у всех?
  - да → Каталог UnitB: Публикует каталог
  - нет → Каталог UnitB: Запрашивает часы [УТОЧНИТЬ у UnitB]

### Данные
- Список ресторанов-участников — DineClub (BP-1.1)
- Рейтинги — выгрузка Яндекс.Карт, не реже раза в квартал
- Часы работы и площадки рядом — Каталог UnitB

### BPMN
```mermaid
flowchart LR
  subgraph L1["Кабинет DineClub"]
    S((" "))
    N1["Передаёт список участников"]
  end
  subgraph L2["Справочник рейтингов"]
    N2["Отдаёт выгрузку рейтингов"]
  end
  subgraph L3["Каталог UnitB"]
    N3["Собирает часы работы и площадки рядом"]
    G4{"Часы работы есть у всех?"}
    N5["Публикует каталог"]
    N6["Запрашивает часы [УТОЧНИТЬ у UnitB]"]
    E(((" ")))
  end
  S --> N1
  N1 --> N2
  N2 --> N3
  N3 --> G4
  G4 -- да --> N5
  G4 -- нет --> N6
  N5 --> E
  N6 --> E
  classDef start fill:#fff,stroke:#2f6b2a,stroke-width:2px
  classDef stop fill:#fff,stroke:#1c1c1c,stroke-width:4px
  classDef gw fill:#fff8e6,stroke:#b7791f
  classDef ask color:#c0392b,stroke:#c0392b
  class S start
  class E stop
  class G4 gw
  class N6 ask
  style L1 fill:#faf9f6,stroke:#d8d4cb
  style L2 fill:#ffffff,stroke:#d8d4cb
  style L3 fill:#faf9f6,stroke:#d8d4cb
```
<!-- SECTION:DESCRIPTION:END -->

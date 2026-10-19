---
id: BP-7.1
title: Письмо с билетом приходит с одним офером
status: To Do
assignee: []
created_date: '2026-10-19 19:07'
updated_date: '2026-10-19 20:40'
labels:
  - stage:C
  - layer:technology
dependencies: []
documentation:
  - doc-5
parent_task_id: BP-7
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
После покупки TeamA отправляет письмо с билетом и одним акцентным офером — скидка 10%. Клик ведёт на страницу акционных ресторанов, UTM — в аналитику.

### UserStory
Как гость, я хочу видеть в письме с билетом одно понятное предложение скидки, чтобы не потерять его среди прочего.

### JobStory
- Когда я открываю письмо с билетом, хочу сразу увидеть скидку 10%, чтобы вспомнить о ней перед мероприятием.
- Когда я нажимаю «Выбрать ресторан», хочу попасть к акционным ресторанам, чтобы выбрать без поиска.

### Параметры
- **Вход:** Покупка билета; Плашка письма (BP-4.1)
- **Управление:** Один акцентный офер, «забронировать» — вторично (ФТ-5); Рендер ≤600px на мобильных, клики размечены (ИТ-2)
- **Выход:** Письмо с плашкой акции; Клик «Выбрать ресторан» (BP-8.1); UTM и клики (BP-19.1)
- **Механизм:** TeamA; Email-рассылка

### Процесс
- TeamA: Отправляет письмо с билетом
- Email: Показывает один офер «скидка 10%»
- Гость: Нажимает «Выбрать ресторан»
- Витрина: Открывает акционные рестораны
- Аналитика: Принимает UTM и клики

### BPMN
```mermaid
flowchart LR
  subgraph L1["TeamA"]
    S((" "))
    N1["Отправляет письмо с билетом"]
  end
  subgraph L2["Email"]
    N2["Показывает один офер «скидка 10%»"]
  end
  subgraph L3["Гость"]
    N3["Нажимает «Выбрать ресторан»"]
  end
  subgraph L4["Витрина"]
    N4["Открывает акционные рестораны"]
  end
  subgraph L5["Аналитика"]
    N5["Принимает UTM и клики"]
    E(((" ")))
  end
  S --> N1
  N1 --> N2
  N2 --> N3
  N3 --> N4
  N4 --> N5
  N5 --> E
  classDef start fill:#fff,stroke:#2f6b2a,stroke-width:2px
  classDef stop fill:#fff,stroke:#1c1c1c,stroke-width:4px
  classDef gw fill:#fff8e6,stroke:#b7791f
  classDef ask color:#c0392b,stroke:#c0392b
  class S start
  class E stop
  style L1 fill:#faf9f6,stroke:#d8d4cb
  style L2 fill:#ffffff,stroke:#d8d4cb
  style L3 fill:#faf9f6,stroke:#d8d4cb
  style L4 fill:#ffffff,stroke:#d8d4cb
  style L5 fill:#faf9f6,stroke:#d8d4cb
```

### HowToDemo
1. Покупаю билет — приходит письмо с билетом и одним офером «скидка 10%»
2. «Забронировать в DineClub» — вторичное действие
3. Нажимаю «Выбрать ресторан» — открывается страница акционных ресторанов
4. В аналитике видны UTM и клики по позициям
<!-- SECTION:DESCRIPTION:END -->

---
id: BP-4.1
title: Макеты блоков в одном стиле
status: To Do
assignee: []
created_date: '2026-10-19 19:07'
updated_date: '2026-10-19 20:40'
labels:
  - stage:A
  - layer:support
dependencies: []
parent_task_id: BP-4
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Дизайнер готовит блоки акции в одной фиолетовой айдентике: страница, письмо, экраны сканера.

### UserStory
Как дизайнер, я хочу собрать все блоки акции в одной айдентике, чтобы гость везде узнавал предложение.

### JobStory
- Когда гость видит акцию в письме и на странице, хочу показать её одинаково, чтобы он её узнал.

### Параметры
- **Вход:** Требования к интерфейсам ИТ-1…ИТ-7
- **Управление:** Один дизайнер, фиолетовая айдентика (НФТ-4)
- **Выход:** Макет блока (BP-5.1); Плашка письма (BP-7.1); Экраны сканера (BP-15.1)
- **Механизм:** Дизайн; Борда FigJam «Спецпроект Acme Tickets»

### Процесс
- Дизайнер: Готовит блок страницы и плашку письма
- Дизайнер: Готовит экраны сканера
- Витрина: Встраивает блок акции
- TeamA: Встраивает плашку в письмо

### BPMN
```mermaid
flowchart LR
  subgraph L1["Дизайнер"]
    S((" "))
    N1["Готовит блок страницы и плашку письма"]
    N2["Готовит экраны сканера"]
  end
  subgraph L2["Витрина"]
    N3["Встраивает блок акции"]
  end
  subgraph L3["TeamA"]
    N4["Встраивает плашку в письмо"]
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
  style L1 fill:#faf9f6,stroke:#d8d4cb
  style L2 fill:#ffffff,stroke:#d8d4cb
  style L3 fill:#faf9f6,stroke:#d8d4cb
```

### HowToDemo
1. Открываю макеты: блок на странице, плашка письма, экраны сканера
2. Все в одной фиолетовой айдентике, автор — один дизайнер
<!-- SECTION:DESCRIPTION:END -->

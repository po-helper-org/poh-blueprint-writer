---
id: BP-5.4
title: Полка ресторанов у площадки для страницы после оплаты
status: To Do
assignee:
  - '@unitb'
created_date: '2026-10-26 13:55'
updated_date: '2026-10-26 17:24'
labels:
  - stage:B
  - zone:BE
dependencies: []
parent_task_id: BP-5
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Отдать странице после оплаты рестораны у площадки билета по контракту restaurant-shelf — через кеш каталога.

### ASIS
Полку ресторанов у площадки менеджер собирает руками.

### GAP
Странице после оплаты неоткуда взять рестораны у площадки билета.

### TOBE
Рестораны у площадки билета отдаются по контракту restaurant-shelf через кеш каталога 10 минут.

### Данные
- Список ресторанов акции: Каталог UnitB, restaurants
- Рейтинг: Каталог UnitB, restaurants.rating
- Адрес площадки: Каталог UnitB, venues.address
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Полка собирается из каталога по площадке билета: ближние × высокий рейтинг
- [ ] #2 Кеш каталога — 10 минут
<!-- AC:END -->

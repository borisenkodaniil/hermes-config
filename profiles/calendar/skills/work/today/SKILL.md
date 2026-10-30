---
name: today
description: "Команда /today — события Google Calendar на сегодня."
---

# /today — календарь на сегодня

```bash
python3 /root/.hermes/scripts/today_events.py
```

`/today 2026-11-05` — конкретный день:

```bash
python3 /root/.hermes/scripts/today_events.py 2026-11-05
```

Ответ — по строке на событие:

```
10:00–10:30 Созвон
14:00–15:00 Врач · Clinic
```

Пусто → `сегодня пусто`. Ошибку скрипта отдать одной строкой `ошибка: <текст>`. Данные не додумывать.

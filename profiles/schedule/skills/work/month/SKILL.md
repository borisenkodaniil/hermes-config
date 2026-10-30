---
name: month
description: "Команда /month — график занятий из Google Таблицы на месяц."
---

# /month — график на месяц

ID таблицы уже лежит в `$HERMES_HOME/workspace/sheet_id.txt`.

Текущий месяц:

```bash
python3 /root/.hermes/scripts/show_schedule.py
```

`/month 11` — ноябрь:

```bash
python3 /root/.hermes/scripts/show_schedule.py 11
```

`/month 11 Лера` — по имени:

```bash
python3 /root/.hermes/scripts/show_schedule.py 11 Лера
```

Ответ: только строки скрипта, формат `ДД.ММ ЧЧ:ММ · занятие`. Пусто → `пусто`.
Ошибку отдать одной строкой `ошибка: <текст>`. Данные не додумывать.

---
name: week
description: "Команда /week — события Google Calendar на 7 дней."
---

# /week — календарь на неделю

```bash
for i in 0 1 2 3 4 5 6; do
  d=$(date -d "+$i day" +%Y-%m-%d)
  echo "— $d"
  python3 /root/.hermes/scripts/today_events.py "$d"
done
```

Ответ — по дням, по строке на событие, пустые дни пропускаются. Если неделя пуста → `неделя пуста`.
Ошибку скрипта отдать одной строкой `ошибка: <текст>`. Ничего не выдумывать.

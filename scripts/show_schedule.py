#!/usr/bin/env python3
"""show_schedule.py — занятия из листа «Месяц» Google Таблицы.

Использование:
  show_schedule.py                 # текущий месяц
  show_schedule.py 11              # ноябрь
  show_schedule.py 11 Лера         # только по имени
  show_schedule.py --today         # только сегодня

Структура «Месяц»: строка 3 — день недели, строка 4 — числа месяца,
столбец A — время (8:00, 9:00, …), ячейки вида «Лера З — Математика ○».
"""
import sys
from datetime import date

import _gcommon

RANGE = "Месяц!A1:AI90"
SKIP = ("обновиться", "данные", "ОБЕД", "перемена")


def main(argv):
    args = argv[1:]
    only_today = "--today" in args
    args = [a for a in args if not a.startswith("--")]
    today = date.today()
    month = int(args[0]) if args and args[0].isdigit() else today.month
    name = " ".join(args[1:]).strip().lower() if len(args) > 1 else ""

    rows = _gcommon.get_range(RANGE)
    if len(rows) < 5:
        print("пусто")
        return 0
    days, grid = rows[3], rows[4:]
    out = []
    for r in grid:
        if not r:
            continue
        t = str(r[0]).strip()
        if ":" not in t:
            continue
        for i, cell in enumerate(r[1:], start=1):
            v = str(cell).strip()
            if not v or any(s.lower() in v.lower() for s in SKIP):
                continue
            d = str(days[i]).strip() if i < len(days) else ""
            if not d.isdigit():
                continue
            day = int(d)
            if only_today and not (day == today.day and month == today.month):
                continue
            if name and name not in v.lower():
                continue
            out.append("%02d.%02d %s · %s" % (day, month, t, v))
    print("\n".join(out[:80]) if out else "пусто")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

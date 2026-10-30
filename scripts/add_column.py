#!/usr/bin/env python3
"""add_column.py — записать занятие в лист «Месяц» Google Таблицы.

Использование:
  add_column.py 5 10:00 "Лера З — Математика"
  add_column.py 5 10:00 "Лера З — Математика" --dry
  add_column.py 5 10:00 ""            # очистить ячейку

Аргументы: число месяца, время ЧЧ:ММ, значение.
Структура «Месяц»: строка 4 — числа месяца (колонки B..AI), столбец A — время.
"""
import sys

import _gcommon

RANGE = "Месяц!A1:AI90"


def col_letter(idx):
    s, idx = "", idx + 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    dry = "--dry" in argv
    if len(args) < 3:
        sys.exit('использование: add_column.py <число> <ЧЧ:ММ> "значение" [--dry]')
    try:
        day = int(args[0])
    except ValueError:
        sys.exit("число месяца должно быть числом")
    time, value = args[1], args[2]

    rows = _gcommon.get_range(RANGE)
    if len(rows) < 5:
        sys.exit("лист «Месяц» пуст")
    days = rows[3]
    col = None
    for i, c in enumerate(days):
        if str(c).strip().isdigit() and int(str(c).strip()) == day:
            col = i
            break
    if col is None:
        sys.exit("день %d не найден в строке 4 листа «Месяц»" % day)
    row = None
    for ri, r in enumerate(rows[4:], start=5):
        if r and str(r[0]).strip() == time:
            row = ri
            break
    if row is None:
        sys.exit("время %s не найдено в столбце A листа «Месяц»" % time)

    cell = "Месяц!%s%d" % (col_letter(col), row)
    if dry:
        print("[dry] %s (день %d, %s) <- %s" % (cell, day, time, value or "(пусто)"))
        return 0
    svc = _gcommon.service("sheets", "v4")
    svc.spreadsheets().values().update(
        spreadsheetId=_gcommon.sheet_id(), range=cell,
        valueInputOption="USER_ENTERED", body={"values": [[value]]},
    ).execute()
    print("день %d %s · %s записано (%s)" % (day, time, value or "очищено", cell))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

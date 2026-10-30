#!/usr/bin/env python3
"""calc_debts.py — кто сколько должен: проведённые уроки минус оплаты.

Данные только из таблицы:
  «Журнал»  A:Дата B:Время C:День D:Ученик E:Предмет F:Статус G:Цена H:Цена вручную
  «Оплаты»  A:Дата B:Ученик C:Сумма D:Месяц E:Комментарий

Использование:
  calc_debts.py            # текущий месяц
  calc_debts.py 11         # ноябрь
  calc_debts.py 11 Лера    # фильтр по имени
"""
import re
import sys
from datetime import date

import _gcommon

MON = ["", "ЯНВ", "ФЕВ", "МАР", "АПР", "МАЙ", "ИЮН", "ИЮЛ", "АВГ", "СЕН", "ОКТ", "НОЯ", "ДЕК"]


def num(s):
    s = str(s).replace("\u00a0", "").replace(" ", "").replace("₽", "").replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def money(v):
    return "{:,}".format(v).replace(",", "\u00a0") + " ₽"


def main(argv):
    args = argv[1:]
    month = int(args[0]) if args and args[0].isdigit() else date.today().month
    flt = " ".join(args[1:] if args and args[0].isdigit() else args).strip().lower()

    journal = _gcommon.get_range("Журнал!A1:H2000")
    pays = _gcommon.get_range("Оплаты!A1:E900")
    if not journal and not pays:
        print("пусто")
        return 0

    earned, paid = {}, {}
    for r in journal[1:]:
        if len(r) < 7:
            continue
        parts = re.split(r"[.]", str(r[0]).strip())
        if len(parts) < 3 or not parts[1].isdigit() or int(parts[1]) != month:
            continue
        status = str(r[5]).strip().lower()
        if "отмен" in status or "запланир" in status:
            continue
        who = str(r[3]).strip()
        manual = str(r[7]).strip() if len(r) > 7 else ""
        price = num(manual) if manual else num(r[6])
        if who and price:
            earned[who] = earned.get(who, 0) + price

    tag = MON[month]
    for r in pays[1:]:
        if len(r) < 3:
            continue
        who = str(r[1]).strip()
        mn = str(r[3]).strip().upper() if len(r) > 3 else ""
        if mn and not mn.startswith(tag[:3]):
            continue
        paid[who] = paid.get(who, 0) + num(r[2])

    out, total = [], 0
    for n in sorted(set(earned) | set(paid)):
        due = earned.get(n, 0) - paid.get(n, 0)
        if flt and flt not in n.lower():
            continue
        if due <= 0:
            continue
        out.append("%s · начислено %s · оплачено %s · долг %s" % (n, money(earned.get(n, 0)), money(paid.get(n, 0)), money(due)))
        total += due
    if not out:
        print("долгов нет за %s" % tag)
        return 0
    print("\n".join(out))
    print("итого к оплате: %s" % money(total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

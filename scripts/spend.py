#!/usr/bin/env python3
"""Статус бюджета: расход за месяц, остаток, последние ходы.

  python3 spend.py            # текущий месяц
  python3 spend.py 2026-10    # конкретный месяц
  python3 spend.py --json
"""
import json
import os
import sys
from pathlib import Path

STORE = Path(os.getenv("HERMES_SPEND_FILE", "/root/.hermes/spend.json"))
BUDGET = float(os.getenv("SPEND_BUDGET_RUB", "1500"))
MARK = "💰"


def money(v):
    v = abs(float(v))
    if v < 0.01:
        return f"{float(v):.3f}"
    return f"{float(v):.2f}" if v < 100 else f"{float(v):.0f}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    try:
        data = json.loads(STORE.read_text())
    except Exception:
        data = {"version": 1, "months": {}, "entries": []}
    months = data.get("months") or {}
    month = args[0] if args else (sorted(months)[-1] if months else "")
    m = months.get(month) or {}
    if as_json:
        print(json.dumps({"month": month, "totals": m, "budget": BUDGET,
                          "remain": BUDGET - float(m.get("cost_rub") or 0)}, ensure_ascii=False))
        return 0
    if not m:
        print(f"за {month or '—'} расходов нет · остаток {money(BUDGET)}₽")
        return 0
    rub = float(m.get("cost_rub") or 0)
    cny = float(m.get("cost_cny") or 0)
    print(f"месяц {month}: ходов {m.get('turns', 0)}, "
          f"токены {m.get('tokens_in', 0)} in / {m.get('tokens_out', 0)} out")
    print(f"{MARK} {money(rub)}₽ / {money(cny)}¥ · остаток {money(max(BUDGET - rub, 0))}₽")
    last = [e for e in data.get("entries", []) if e.get("date", "").startswith(month)][-5:]
    for e in last:
        print(f"  {e['date']} {e.get('profile','?'):<9} {e.get('tokens_in',0):>6} in "
              f"{e.get('tokens_out',0):>5} out → {money(e.get('cost_rub', 0))}₽")
    return 0


if __name__ == "__main__":
    sys.exit(main())

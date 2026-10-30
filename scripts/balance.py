#!/usr/bin/env python3
"""Баланс DeepSeek + локальный расход за месяц.

  python3 balance.py         # одна строка для бота
  python3 balance.py --json
"""
import json
import os
import subprocess
import sys
import urllib.request

SPEND = "/root/.hermes/scripts/spend.py"
BUDGET = float(os.getenv("SPEND_BUDGET_RUB", "1500"))


def _key() -> str:
    if os.getenv("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]
    for path in ("/root/.hermes/.env", "/root/.hermes/profiles/proxmox/.env"):
        try:
            for line in open(path):
                if line.startswith("DEEPSEEK_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def deepseek_balance() -> dict | None:
    """GET https://api.deepseek.com/user/balance → {'USD': 0.0, 'CNY': 32.69} или None."""
    key = _key()
    if not key:
        return None
    req = urllib.request.Request(
        "https://api.deepseek.com/user/balance",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return None
    out = {}
    for info in data.get("balance_infos") or []:
        cur = (info.get("currency") or "").upper()
        if cur:
            try:
                out[cur] = float(info.get("total_balance") or 0)
            except (TypeError, ValueError):
                pass
    return out or None


def local_spend() -> dict:
    try:
        raw = subprocess.run([sys.executable, SPEND, "--json"], capture_output=True, text=True, timeout=20)
        return json.loads(raw.stdout or "{}")
    except Exception:
        return {}


def main() -> int:
    bal = deepseek_balance()
    local = local_spend()
    rub = float((local.get("totals") or {}).get("cost_rub") or 0)
    remain = BUDGET - rub
    if "--json" in sys.argv:
        print(json.dumps({"deepseek": bal, "month": local.get("month"), "rub": rub,
                          "remain": remain, "budget": BUDGET}, ensure_ascii=False))
        return 0
    if bal is None:
        print(f"Баланс DeepSeek недоступен (нет ключа или API молчит) · локально: {rub:.2f}₽ / {int(remain)}₽ остаток")
        return 1
    usd = bal.get("USD")
    cny = bal.get("CNY")
    if usd is not None:
        ds = f"${usd:.2f}"
    else:
        ds = f"${(cny or 0) / 7.2:.2f}"
    extra = f" (¥{cny:.2f})" if cny is not None and usd is not None else ""
    print(f"DeepSeek: {ds}{extra} · локально: {rub:.2f}₽ / {int(remain)}₽ остаток")
    return 0


if __name__ == "__main__":
    sys.exit(main())

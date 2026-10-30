#!/usr/bin/env python3
"""ШАБЛОН плагина Hermes: счётчик расхода + футер со стоимостью и остатком бюджета.

Положить как ~/.hermes/plugins/spend/{plugin.yaml,__init__.py}, затем:
  hermes -p <profile> config set plugins.enabled '["spend"]'
  rm -rf ~/.hermes/plugins/spend/__pycache__
  touch ~/.hermes/gw-recycle-request     # worker перезапустит шлюз через 90с

plugin.yaml:
  name: spend
  version: "1.0"
  description: Стоимость ответа и остаток месячного бюджета одной строкой.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

RATE_IN = float(os.getenv("SPEND_RATE_IN", "0.14"))          # $ / 1M обычных входных
RATE_CACHE = float(os.getenv("SPEND_RATE_CACHE", "0.014"))   # $ / 1M попаданий в кэш
RATE_OUT = float(os.getenv("SPEND_RATE_OUT", "0.28"))        # $ / 1M выходных
USD_RUB = float(os.getenv("SPEND_USD_RUB", "95"))
USD_CNY = float(os.getenv("SPEND_USD_CNY", "7.2"))
BUDGET_RUB = float(os.getenv("SPEND_BUDGET_RUB", "1500"))

STORE = Path(os.getenv("HERMES_SPEND_FILE", os.path.expanduser("~/.hermes/spend.json")))
TICKETS_DB = Path(os.getenv("HERMES_TICKETS_DB", os.path.expanduser("~/.hermes/tickets.db")))

_MARK = "💰"
_FILE_LOCK = threading.Lock()
_MAX_ENTRIES = 5000


def _profile() -> str:
    p = (os.environ.get("HERMES_PROFILE") or "").strip()
    if p:
        return p
    home = (os.environ.get("HERMES_HOME") or "").strip()
    if "/profiles/" in home:
        return home.rstrip("/").split("/profiles/")[-1].split("/")[0]
    return "default"


def _month(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time()).strftime("%Y-%m")


def _empty() -> dict[str, Any]:
    return {"version": 1, "months": {}, "entries": []}


def _load() -> dict[str, Any]:
    try:
        data = json.loads(STORE.read_text())
        if not isinstance(data, dict):
            raise ValueError("not a dict")
    except FileNotFoundError:
        return _empty()
    except Exception as e:  # битый файл не должен ронять ответы
        log.warning("[spend] store unreadable (%s), starting fresh", e)
        return _empty()
    data.setdefault("months", {})
    data.setdefault("entries", [])
    return data


def _save(data: dict[str, Any]) -> None:
    data["entries"] = data["entries"][-_MAX_ENTRIES:]
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(STORE)


def _record(profile: str, tin: int, tout: int, cost_usd: float,
            session: str, model: str, platform: str):
    """Пишет запись; возвращает (rub хода, cny хода, rub за месяц, остаток)."""
    cost_rub, cost_cny = cost_usd * USD_RUB, cost_usd * USD_CNY
    ts = time.time()
    with _FILE_LOCK:
        data = _load()
        m = data["months"].setdefault(
            _month(ts),
            {"cost_usd": 0.0, "cost_rub": 0.0, "cost_cny": 0.0,
             "tokens_in": 0, "tokens_out": 0, "turns": 0},
        )
        m["cost_usd"] = round(m["cost_usd"] + cost_usd, 6)
        m["cost_rub"] = round(m["cost_rub"] + cost_rub, 6)
        m["cost_cny"] = round(m["cost_cny"] + cost_cny, 6)
        m["tokens_in"] += tin
        m["tokens_out"] += tout
        m["turns"] += 1
        data["entries"].append({
            "ts": round(ts, 3),
            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
            "profile": profile, "session": session, "model": model, "platform": platform,
            "tokens_in": tin, "tokens_out": tout,
            "cost_usd": round(cost_usd, 6), "cost_rub": round(cost_rub, 4), "cost_cny": round(cost_cny, 4),
        })
        _save(data)
        return cost_rub, cost_cny, m["cost_rub"], BUDGET_RUB - m["cost_rub"]


def _ticket_id(text: str) -> str | None:
    mm = re.search(r"\bT-\d{4}\b", text or "")
    return mm.group(0) if mm else None


def _add_ticket_cost(ticket_id: str, cost_rub: float) -> float | None:
    if not TICKETS_DB.exists():
        return None
    try:
        con = sqlite3.connect(str(TICKETS_DB), timeout=5)
        try:
            con.execute("UPDATE tickets SET cost = COALESCE(cost, 0) + ? WHERE id = ?",
                        (round(cost_rub, 4), ticket_id))
            con.commit()
            row = con.execute("SELECT cost FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return float(row[0] or 0) if row else None
        finally:
            con.close()
    except Exception as e:
        log.warning("[spend] ticket %s cost update failed: %s", ticket_id, e)
        return None


def _money(value: float) -> str:
    v = abs(value)
    if v < 0.01:
        return f"{value:.3f}"
    if v < 1:
        return f"{value:.2f}"
    return f"{value:.0f}" if v >= 100 else f"{value:.2f}"


def _line(rub: float, cny: float, remain: float, tail: str = "") -> str:
    # остаток целыми вниз: %.0f от 1499.9 даёт 1500 и «залипает» на полной сумме
    return f"{_MARK} {_money(rub)}₽ / {_money(cny)}¥ · остаток {int(max(remain, 0.0))}₽{tail}"


def register(ctx):
    profile = _profile()
    pending: dict[str, dict[str, float]] = {}
    lock = threading.Lock()

    def on_post_api_request(**kw) -> None:
        usage = kw.get("usage") or {}
        if not usage:
            return
        tin = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        tout = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        if tin <= 0 and tout <= 0:
            return
        cached = int(usage.get("cache_read_tokens") or 0)
        cost = (max(tin - cached, 0) * RATE_IN + cached * RATE_CACHE + tout * RATE_OUT) / 1_000_000
        key = kw.get("session_id") or kw.get("turn_id") or "_"
        with lock:
            slot = pending.setdefault(key, {"tin": 0.0, "tout": 0.0, "usd": 0.0, "model": ""})
            slot["tin"] += tin
            slot["tout"] += tout
            slot["usd"] += cost
            slot["model"] = kw.get("model") or slot.get("model") or ""

    def on_transform_llm_output(response_text: str, session_id: str = "",
                                model: str = "", platform: str = "", **_kw) -> str | None:
        text = response_text or ""
        if not text.strip() or _MARK in text:   # идемпотентность: не дублировать футер
            return None
        key = session_id or "_"
        with lock:
            slot = pending.pop(key, None)
        tin = int(slot["tin"]) if slot else 0
        tout = int(slot["tout"]) if slot else 0
        usd = slot["usd"] if slot else 0.0
        rub, cny, _m, remain = _record(profile, tin, tout, usd, session_id or "",
                                       model or (slot["model"] if slot else ""), platform or "")
        tail = ""
        tid = _ticket_id(text) if profile == "default" else None
        if tid:
            total = _add_ticket_cost(tid, rub)
            if total is not None:
                tail = f" · {tid} {_money(total)}₽"
        return text.rstrip() + "\n\n" + _line(rub, cny, remain, tail)

    ctx.register_hook("post_api_request", on_post_api_request)
    ctx.register_hook("transform_llm_output", on_transform_llm_output)

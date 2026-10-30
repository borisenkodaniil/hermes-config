#!/usr/bin/env python3
"""Общая библиотека реестра заявок (sqlite, stdlib only).

DB: /root/.hermes/tickets.db (переопределяется $TICKETS_DB).
Таблицы: tickets, events, drafts (TTL 30 мин), outbox (очередь уведомлений Boss).
"""
import os
import sqlite3
from datetime import datetime, timedelta

DB = os.environ.get("TICKETS_DB", "/root/.hermes/tickets.db")

STATUSES = ("new", "in_progress", "review", "done", "rejected")
OPEN_STATUSES = ("new", "in_progress", "review")
RU = {
    "new": "новая",
    "in_progress": "в работе",
    "review": "на проверке",
    "done": "закрыта",
    "rejected": "отклонена",
}
EMOJI = {
    "new": "🆕",
    "in_progress": "🔧",
    "review": "👀",
    "done": "✅",
    "rejected": "❌",
}
DRAFT_TTL_MIN = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    note TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT '',
    profile TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ticket_id INTEGER,
    kind TEXT NOT NULL DEFAULT 'new',
    body TEXT NOT NULL DEFAULT '',
    sent_at TEXT
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def now_s() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    ensure_schema(c)
    return c


def ensure_schema(c: sqlite3.Connection) -> None:
    c.executescript(SCHEMA)
    have = {r[1] for r in c.execute("PRAGMA table_info(tickets)")}
    for col, ddl in (
        ("user_id", "TEXT NOT NULL DEFAULT ''"),
        ("profile", "TEXT NOT NULL DEFAULT ''"),
        ("cost", "REAL NOT NULL DEFAULT 0"),
    ):
        if col not in have:
            c.execute("ALTER TABLE tickets ADD COLUMN %s %s" % (col, ddl))
    c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_profile ON tickets(profile)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_ticket ON events(ticket_id)")
    c.commit()


def tid(n: int) -> str:
    return "T-%04d" % n


def parse_tid(raw: str):
    s = (raw or "").strip().upper().replace("T-", "").lstrip("0")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def short(text: str, n: int = 90) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 3] + "..."


def line(row) -> str:
    return "%s %s %s · %s · %s" % (
        tid(row["id"]),
        EMOJI.get(row["status"], "•"),
        RU.get(row["status"], row["status"]),
        short(row["title"]),
        row["source"],
    )


def card(row, events=None) -> str:
    out = [
        "%s %s %s" % (tid(row["id"]), EMOJI.get(row["status"], "•"), RU.get(row["status"], row["status"])),
        short(row["title"], 400),
        "автор: %s · источник: %s · %s" % (row["user_id"] or "—", row["profile"] or row["source"], row["created_at"]),
    ]
    if row["cost"]:
        out.append("стоимость: %s" % row["cost"])
    if row["note"]:
        out.append("детали: %s" % short(row["note"], 400))
    for e in events or []:
        out.append("· %s %s: %s" % (e["ts"][:16], e["actor"], e["text"]))
    return "\n".join(out)


def enqueue(c, ticket_id, kind: str = "new", body: str = "") -> None:
    c.execute(
        "INSERT INTO outbox(ts, ticket_id, kind, body) VALUES (?,?,?,?)",
        (now_s(), ticket_id, kind, body),
    )
    c.commit()


def save_draft(c, user_id: str, profile: str, text: str) -> int:
    ts = datetime.now()
    cur = c.execute(
        "INSERT INTO drafts(user_id, profile, text, created_at, expires_at) VALUES (?,?,?,?,?)",
        (
            user_id,
            profile,
            text,
            ts.strftime("%Y-%m-%d %H:%M:%S"),
            (ts + timedelta(minutes=DRAFT_TTL_MIN)).strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    c.commit()
    return cur.lastrowid


def expire_drafts(c) -> int:
    cur = c.execute("DELETE FROM drafts WHERE expires_at < ?", (now_s(),))
    c.commit()
    return cur.rowcount

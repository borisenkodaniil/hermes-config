#!/usr/bin/env python3
"""patterns.py — реестр повторяющихся запросов (паттернов).

Хранилище: /root/.hermes/patterns.db (sqlite, stdlib only).
Поля: phrase (уникальная), count, script_path, last_used.

Использование:
  patterns.py bump "<фраза>" [--script PATH]   # +1 к счётчику, обновить last_used
  patterns.py get "<фраза>"                    # есть ли паттерн и сколько раз
  patterns.py list [--limit N] [--min N]       # топ паттернов
  patterns.py script "<фраза>" <PATH|->        # привязать/отвязать скрипт
  patterns.py clear "<фраза>"                  # удалить паттерн
Правило тандема: count >= 3 и нет script_path → предложить «Оформить как скрипт?»
"""
import os
import re
import sqlite3
import sys
from datetime import datetime

DB = os.environ.get("PATTERNS_DB", "/root/.hermes/patterns.db")


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS patterns(
            phrase TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            script_path TEXT DEFAULT '',
            last_used TEXT NOT NULL
        );
        """
    )
    return c


def norm(s):
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, phrase = argv[1], norm(argv[2])
    flags = {}
    i = 3
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            flags[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            flags.setdefault("_pos", argv[i])
            i += 1
    c = conn()

    if cmd == "bump":
        row = c.execute("SELECT count FROM patterns WHERE phrase = ?", (phrase,)).fetchone()
        if row:
            c.execute(
                "UPDATE patterns SET count = count + 1, last_used = ?, "
                "script_path = COALESCE(NULLIF(?, ''), script_path) WHERE phrase = ?",
                (now(), flags.get("script", ""), phrase),
            )
            n = row["count"] + 1
        else:
            c.execute(
                "INSERT INTO patterns(phrase, count, script_path, last_used) VALUES (?,?,?,?)",
                (phrase, 1, flags.get("script", ""), now()),
            )
            n = 1
        c.commit()
        sp = c.execute("SELECT script_path FROM patterns WHERE phrase = ?", (phrase,)).fetchone()["script_path"]
        print("%s × %d%s" % (phrase, n, " · скрипт: " + sp if sp else ""))
        if n >= 3 and not sp:
            print("повтор 3+ → предложить: оформить как скрипт?")
        return 0

    if cmd == "get":
        row = c.execute("SELECT * FROM patterns WHERE phrase = ?", (phrase,)).fetchone()
        if not row:
            print("нет паттерна")
            return 0
        print("%s × %d · %s%s" % (row["phrase"], row["count"], row["last_used"], " · скрипт: " + row["script_path"] if row["script_path"] else ""))
        return 0

    if cmd == "list":
        lim = int(flags.get("limit", 20))
        mn = int(flags.get("min", 1))
        rows = c.execute("SELECT * FROM patterns WHERE count >= ? ORDER BY count DESC, last_used DESC LIMIT ?", (mn, lim)).fetchall()
        if not rows:
            print("пусто")
            return 0
        for r in rows:
            print("%2d× %s%s" % (r["count"], r["phrase"][:70], " · скрипт: " + r["script_path"] if r["script_path"] else ""))
        return 0

    if cmd == "script":
        path = argv[3] if len(argv) > 3 else ""
        path = "" if path == "-" else path
        row = c.execute("SELECT count FROM patterns WHERE phrase = ?", (phrase,)).fetchone()
        if row:
            c.execute("UPDATE patterns SET script_path = ?, last_used = ? WHERE phrase = ?", (path, now(), phrase))
        else:
            c.execute("INSERT INTO patterns(phrase, count, script_path, last_used) VALUES (?,?,?,?)", (phrase, 0, path, now()))
        c.commit()
        print("%s · скрипт %s" % (phrase, "→ " + path if path else "отвязан"))
        return 0

    if cmd == "clear":
        c.execute("DELETE FROM patterns WHERE phrase = ?", (phrase,))
        c.commit()
        print("%s удалён" % phrase)
        return 0

    print("неизвестная команда: %s" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

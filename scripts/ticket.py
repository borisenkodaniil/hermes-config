#!/usr/bin/env python3
"""Тикет-стор для ботов Hermes (default/proxmox/calendar/schedule).

Хранилище: /root/.hermes/tickets.db (см. tickets_lib.py).

  ticket.py new "<title>" --confirmed [--from SRC] [--user UID] [--profile P] [--note TEXT] [--cost N] [--quiet]
  ticket.py list [--status S] [--from SRC] [--user UID] [--all] [--limit N]
  ticket.py show <T-0001>
  ticket.py card <T-0001>                                   # карточка для Boss
  ticket.py status <T-0001> <new|in_progress|review|done|rejected> [--from ACTOR]
  ticket.py comment <T-0001> "<text>" [--from ACTOR]
  ticket.py close <T-0001> ["comment"] [--from ACTOR]
  ticket.py draft "<text>" [--user UID] [--profile P]      # черновик, TTL 30 мин
  ticket.py drafts [--user UID]
  ticket.py draft-show <id>
  ticket.py draft-accept <id> [\"<новый текст>\"] [--note TEXT]   # черновик → заявка (+outbox)
  ticket.py draft-drop <id>
  ticket.py expire                                          # снести протухшие черновики

Вывод — компактный текст, готовый для Telegram.
"""
import os
import sys

import tickets_lib as L


def parse_args(args):
    flags, pos = {}, []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key = a[2:]
            if key in ("all", "quiet"):
                flags[key] = True
                i += 1
            else:
                flags[key] = args[i + 1] if i + 1 < len(args) else ""
                i += 2
        else:
            pos.append(a)
            i += 1
    return flags, pos


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, args = argv[1], argv[2:]
    flags, pos = parse_args(args)
    c = L.connect()
    src = flags.get("from") or os.environ.get("HERMES_PROFILE", "default")
    user_id = str(flags.get("user") or os.environ.get("TICKET_USER_ID", ""))
    profile = flags.get("profile") or src

    if cmd == "new":
        if not pos:
            print("нужен текст заявки")
            return 2
        if not flags.get("confirmed"):
            print("отказ: тикет создаётся только через черновик и подтверждение.")
            print("  ticket.py draft \"<текст>\" --user UID --profile P")
            print("  ticket.py draft-accept <id>        # после «Принять»")
            return 3
        title = pos[0].strip()
        try:
            cost = float(flags.get("cost") or 0)
        except ValueError:
            cost = 0.0
        ts = L.now()
        cur = c.execute(
            "INSERT INTO tickets(created_at, source, title, note, status, updated_at, user_id, profile, cost)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, src, title, flags.get("note", ""), "new", ts, user_id, profile, cost),
        )
        new_id = cur.lastrowid
        c.execute(
            "INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
            (new_id, ts, src, "создана"),
        )
        if not flags.get("quiet"):
            L.enqueue(c, new_id, "new", title[:400])
        c.commit()
        print("%s новая · %s" % (L.tid(new_id), L.short(title)))
        return 0

    if cmd == "list":
        sql, where, params = "SELECT * FROM tickets", [], []
        if flags.get("status"):
            where.append("status = ?")
            params.append(flags["status"])
        elif not flags.get("all"):
            where.append("status NOT IN ('done','rejected')")
        if flags.get("from"):
            where.append("source = ?")
            params.append(flags["from"])
        if flags.get("user"):
            where.append("user_id = ?")
            params.append(str(flags["user"]))
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT %d" % int(flags.get("limit", 30))
        rows = c.execute(sql, params).fetchall()
        if not rows:
            print("пусто")
            return 0
        for r in rows:
            print(L.line(r))
        return 0

    if cmd == "draft":
        if not pos:
            print("нужен текст черновика")
            return 2
        did = L.save_draft(c, user_id, profile, pos[0].strip())
        print("черновик #%d сохранён (30 мин)" % did)
        return 0

    if cmd == "drafts":
        L.expire_drafts(c)
        sql, params = "SELECT * FROM drafts", []
        if flags.get("user"):
            sql += " WHERE user_id = ?"
            params.append(str(flags["user"]))
        rows = c.execute(sql + " ORDER BY id DESC LIMIT 20", params).fetchall()
        if not rows:
            print("пусто")
            return 0
        for r in rows:
            print("#%d %s · %s · до %s" % (r["id"], r["profile"], L.short(r["text"]), r["expires_at"][11:16]))
        return 0

    if cmd == "draft-show":
        if not pos:
            print("нужен id черновика")
            return 2
        r = c.execute("SELECT * FROM drafts WHERE id = ?", (int(pos[0]),)).fetchone()
        if not r:
            print("черновик не найден или истёк")
            return 1
        if r["expires_at"] < L.now_s():
            c.execute("DELETE FROM drafts WHERE id = ?", (r["id"],))
            c.commit()
            print("черновик истёк")
            return 1
        print("#%d %s" % (r["id"], r["text"]))
        return 0

    if cmd == "draft-accept":
        if not pos:
            print("нужен id черновика")
            return 2
        r = c.execute("SELECT * FROM drafts WHERE id = ?", (int(pos[0]),)).fetchone()
        if not r:
            print("черновик не найден или истёк")
            return 1
        if r["expires_at"] < L.now_s():
            c.execute("DELETE FROM drafts WHERE id = ?", (r["id"],))
            c.commit()
            print("черновик истёк")
            return 1
        title = (pos[1].strip() if len(pos) > 1 and pos[1].strip() else r["text"]).strip()
        ts = L.now()
        cur = c.execute(
            "INSERT INTO tickets(created_at, source, title, note, status, updated_at, user_id, profile, cost)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, r["profile"] or src, title, flags.get("note", ""), "new", ts,
             r["user_id"] or user_id, r["profile"] or profile, 0.0),
        )
        new_id = cur.lastrowid
        c.execute("INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
                  (new_id, ts, r["profile"] or src, "создана из черновика #%d" % r["id"]))
        c.execute("DELETE FROM drafts WHERE id = ?", (r["id"],))
        if not flags.get("quiet"):
            L.enqueue(c, new_id, "new", title[:400])
        c.commit()
        print("%s новая · %s" % (L.tid(new_id), L.short(title)))
        return 0

    if cmd == "draft-drop":
        if not pos:
            print("нужен id черновика")
            return 2
        c.execute("DELETE FROM drafts WHERE id = ?", (int(pos[0]),))
        c.commit()
        print("черновик удалён")
        return 0

    if cmd == "expire":
        print("удалено черновиков: %d" % L.expire_drafts(c))
        return 0

    if cmd in ("show", "card", "status", "comment", "close"):
        if not pos:
            print("нужен номер, например T-0001")
            return 2
        n = L.parse_tid(pos[0])
        if not n:
            print("неверный номер: %s" % pos[0])
            return 2
        row = c.execute("SELECT * FROM tickets WHERE id = ?", (n,)).fetchone()
        if not row:
            print("тикет %s не найден" % L.tid(n))
            return 1
        events = c.execute("SELECT * FROM events WHERE ticket_id = ? ORDER BY id", (n,)).fetchall()
        if cmd == "show":
            print(L.line(row))
            if row["note"]:
                print("описание: %s" % row["note"])
            for e in events:
                print("  %s %s: %s" % (e["ts"][:16], e["actor"], e["text"]))
            return 0
        if cmd == "card":
            print(L.card(row, events))
            return 0
        actor = flags.get("from") or "boss"
        if cmd == "status":
            if len(pos) < 2 or pos[1] not in L.STATUSES:
                print("статусы: " + ", ".join(L.STATUSES))
                return 2
            c.execute("UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?", (pos[1], L.now(), n))
            c.execute(
                "INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
                (n, L.now(), actor, "статус → %s" % L.RU[pos[1]]),
            )
            c.commit()
            print("%s %s" % (L.tid(n), L.RU[pos[1]]))
            return 0
        if cmd == "comment":
            text = " ".join(pos[1:]).strip()
            if not text:
                print("нужен текст комментария")
                return 2
            c.execute(
                "INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
                (n, L.now(), actor, text),
            )
            c.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (L.now(), n))
            c.commit()
            print("%s комментарий добавлен" % L.tid(n))
            return 0
        if cmd == "close":
            text = " ".join(pos[1:]).strip() or "закрыта"
            c.execute("UPDATE tickets SET status = 'done', updated_at = ? WHERE id = ?", (L.now(), n))
            c.execute(
                "INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
                (n, L.now(), actor, text),
            )
            c.commit()
            print("%s закрыта" % L.tid(n))
            return 0

    print("неизвестная команда: %s" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

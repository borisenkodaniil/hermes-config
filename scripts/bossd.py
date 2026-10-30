#!/usr/bin/env python3
"""bossd — сервис Boss-заявок: отдельный Telegram-бот, который шлёт карточки заявок
с инлайн-кнопками и сам обрабатывает нажатия (long polling своего токена).

Конфиг: ~/.hermes/boss_tickets.env
  BOSS_BOT_TOKEN=123456:AA...        # токен ОТДЕЛЬНОГО бота (не токены профилей!)
  BOSS_OWNER_IDS=7997827598,902621045
  BOSS_CHAT_ID=7997827598            # необязательно: куда слать карточки

Режимы:
  bossd.py                 # демон: черновики → outbox → getUpdates
  bossd.py --once          # один цикл (разослать outbox + разобрать накопленные апдейты)
  bossd.py --flush         # только разослать очередь уведомлений
  bossd.py --update FILE   # обработать один update из JSON-файла (тест/отладка)
  bossd.py --dry-run       # ничего не отправлять в Telegram, только печать
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tickets_lib as L

ENV_FILE = os.path.expanduser("~/.hermes/boss_tickets.env")
MAX_LEN = 3800


def load_env(path=ENV_FILE):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Bot:
    def __init__(self, token, dry=False):
        self.token = token
        self.dry = dry

    def call(self, method, **params):
        if self.dry:
            print("[dry] %s %s" % (method, json.dumps(params, ensure_ascii=False)[:400]))
            return {"ok": True, "result": {"message_id": 0}}
        url = "https://api.telegram.org/bot%s/%s" % (self.token, method)
        data = urllib.parse.urlencode(
            {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in params.items()}
        ).encode()
        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=70) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            return {"ok": False, "error": body, "code": exc.code}
        except Exception as exc:  # network
            return {"ok": False, "error": str(exc)}


def kb(rows):
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


def buttons(ticket_id):
    return kb([
        [("Доработать", "tk:work:%d" % ticket_id), ("Отклонить", "tk:reject:%d" % ticket_id)],
        [("Закрыть", "tk:close:%d" % ticket_id), ("Комментарий", "tk:comment:%d" % ticket_id)],
    ])


def head(row):
    return "%s %s %s" % (L.tid(row["id"]), L.EMOJI.get(row["status"], "•"), L.RU.get(row["status"], row["status"]))


def notify_text(row):
    parts = [
        head(row),
        L.short(row["title"], 600),
        "автор: %s · источник: %s · %s" % (row["user_id"] or "—", row["profile"] or row["source"], row["created_at"]),
    ]
    if row["note"]:
        parts.append("детали: %s" % L.short(row["note"], 400))
    if row["cost"]:
        parts.append("стоимость: %s" % row["cost"])
    return "\n".join(parts)[:MAX_LEN]


class Bossd:
    def __init__(self, bot, owners, chat_id):
        self.bot = bot
        self.owners = {str(o).strip() for o in owners if str(o).strip()}
        self.chat_id = str(chat_id) if chat_id else None

    # ---------- хранилище ----------
    def ensure(self, c):
        c.execute(
            "CREATE TABLE IF NOT EXISTS cb_state("
            "chat_id TEXT NOT NULL, user_id TEXT NOT NULL, action TEXT NOT NULL,"
            " ticket_id INTEGER, ts TEXT NOT NULL, PRIMARY KEY(chat_id, user_id))"
        )
        c.commit()

    def target_chats(self, c):
        """Карточки получают только владельцы (Boss) — автор видит свои заявки через свой бот."""
        if self.chat_id:
            return [self.chat_id]
        return sorted(self.owners)

    # ---------- уведомления ----------
    def flush(self):
        c = L.connect()
        self.ensure(c)
        L.expire_drafts(c)
        rows = c.execute("SELECT * FROM outbox WHERE sent_at IS NULL ORDER BY id LIMIT 20").fetchall()
        sent = 0
        for r in rows:
            t = c.execute("SELECT * FROM tickets WHERE id = ?", (r["ticket_id"],)).fetchone()
            if not t:
                c.execute("UPDATE outbox SET sent_at = ? WHERE id = ?", (L.now_s(), r["id"]))
                c.commit()
                continue
            text = notify_text(t)
            if r["kind"] == "status":
                text = text + "\n\n" + (r["body"] or "")
            ok = False
            for chat in self.target_chats(c):
                res = self.bot.call("sendMessage", chat_id=chat, text=text, reply_markup=buttons(t["id"]))
                if res.get("ok"):
                    ok = True
            if ok:
                c.execute("UPDATE outbox SET sent_at = ? WHERE id = ?", (L.now_s(), r["id"]))
                c.commit()
                sent += 1
            else:
                print("outbox #%d: отправка не удалась: %s" % (r["id"], res.get("error")))
                break
        return sent

    # ---------- действия ----------
    def apply(self, ticket_id, action, actor):
        c = L.connect()
        row = c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if not row:
            return "не найдено", None
        if action == "work":
            c.execute("UPDATE tickets SET status='in_progress', updated_at=? WHERE id=?", (L.now(), ticket_id))
            ev = "взято в работу"
            toast = "в работе"
        elif action == "reject":
            c.execute("UPDATE tickets SET status='rejected', updated_at=? WHERE id=?", (L.now(), ticket_id))
            ev = "отклонена"
            toast = "отклонена"
        elif action == "close":
            c.execute("UPDATE tickets SET status='done', updated_at=? WHERE id=?", (L.now(), ticket_id))
            ev = "закрыта"
            toast = "закрыта"
        else:
            return "неизвестное действие", row
        c.execute(
            "INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
            (ticket_id, L.now(), "boss:%s" % actor, ev),
        )
        c.commit()
        row = c.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return toast, row

    # ---------- обработка updates ----------
    def handle(self, upd):
        if "callback_query" in upd:
            return self.on_callback(upd["callback_query"])
        if "message" in upd:
            return self.on_message(upd["message"])
        return None

    def authorized(self, uid):
        return str(uid) in self.owners

    def on_callback(self, q):
        data = q.get("data") or ""
        uid = str(q.get("from", {}).get("id", ""))
        cb_id = q.get("id")
        chat_id = str(q.get("message", {}).get("chat", {}).get("id", ""))
        msg_id = q.get("message", {}).get("message_id")
        if not self.authorized(uid):
            self.bot.call("answerCallbackQuery", callback_query_id=cb_id, text="нет доступа")
            return None
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "tk":
            self.bot.call("answerCallbackQuery", callback_query_id=cb_id, text="устаревшая кнопка")
            return None
        action, tid = parts[1], L.parse_tid(parts[2])
        if not tid:
            return None
        if action == "comment":
            c = L.connect()
            self.ensure(c)
            c.execute(
                "INSERT OR REPLACE INTO cb_state(chat_id, user_id, action, ticket_id, ts) VALUES (?,?,?,?,?)",
                (chat_id, uid, "comment", tid, L.now_s()),
            )
            c.commit()
            self.bot.call("answerCallbackQuery", callback_query_id=cb_id, text="напиши комментарий следующим сообщением")
            self.bot.call("sendMessage", chat_id=chat_id, text="💬 %s — жду текст комментария (или /cancel)" % L.tid(tid))
            return None
        toast, row = self.apply(tid, action, uid)
        if row is None:
            self.bot.call("answerCallbackQuery", callback_query_id=cb_id, text="заявка не найдена")
            return None
        self.bot.call("answerCallbackQuery", callback_query_id=cb_id, text=toast)
        c = L.connect()
        ev = c.execute(
            "SELECT ts, actor, text FROM events WHERE ticket_id = ? ORDER BY id DESC LIMIT 1", (tid,)
        ).fetchone()
        text = notify_text(row) + "\n\n" + ("· %s %s: %s" % (ev["ts"][:16], ev["actor"], ev["text"]) if ev else toast)
        if msg_id:
            self.bot.call("editMessageText", chat_id=chat_id, message_id=msg_id, text=text, reply_markup=kb([]))
        return row

    def on_message(self, m):
        uid = str(m.get("from", {}).get("id", ""))
        chat_id = str(m.get("chat", {}).get("id", ""))
        text = (m.get("text") or "").strip()
        if not text:
            return None
        if not self.authorized(uid):
            self.bot.call("sendMessage", chat_id=chat_id, text="нет доступа")
            return None
        c = L.connect()
        self.ensure(c)
        state = c.execute("SELECT * FROM cb_state WHERE chat_id=? AND user_id=?", (chat_id, uid)).fetchone()
        if state and state["action"] == "comment" and not text.startswith("/"):
            tid = state["ticket_id"]
            c.execute(
                "INSERT INTO events(ticket_id, ts, actor, text) VALUES (?,?,?,?)",
                (tid, L.now(), "boss:%s" % uid, text),
            )
            c.execute("UPDATE tickets SET updated_at=? WHERE id=?", (L.now(), tid))
            c.execute("DELETE FROM cb_state WHERE chat_id=? AND user_id=?", (chat_id, uid))
            c.commit()
            row = c.execute("SELECT * FROM tickets WHERE id = ?", (tid,)).fetchone()
            self.bot.call("sendMessage", chat_id=chat_id, text="💬 %s\n%s" % (L.tid(tid), notify_text(row)), reply_markup=buttons(tid))
            return row

        cmd = text.split()[0].split("@")[0]
        arg = text[len(cmd):].strip()
        if cmd == "/start" or cmd == "/help":
            body = "Boss — заявки.\n/mine — мои открытые\n/status — все открытые\n/ticket T-0007 — карточка\nПисать текстом нельзя — только кнопки."
            self.bot.call("sendMessage", chat_id=chat_id, text=body)
        elif cmd == "/mine":
            rows = c.execute(
                "SELECT * FROM tickets WHERE user_id=? AND status NOT IN ('done','rejected') ORDER BY id DESC LIMIT 10",
                (uid,),
            ).fetchall()
            body = "\n".join(L.line(r) for r in rows) if rows else "пусто"
            self.bot.call("sendMessage", chat_id=chat_id, text=("🆕 открытые\n" + body) if rows else "пусто")
        elif cmd == "/status":
            rows = c.execute(
                "SELECT * FROM tickets WHERE status NOT IN ('done','rejected') ORDER BY id DESC LIMIT 15"
            ).fetchall()
            body = "\n".join(L.line(r) for r in rows) if rows else "пусто"
            self.bot.call("sendMessage", chat_id=chat_id, text=("📋 все открытые\n" + body) if rows else "пусто")
        elif cmd == "/ticket":
            n = L.parse_tid(arg)
            row = c.execute("SELECT * FROM tickets WHERE id = ?", (n,)).fetchone() if n else None
            if not row:
                self.bot.call("sendMessage", chat_id=chat_id, text="не найдено")
                return None
            events = c.execute("SELECT * FROM events WHERE ticket_id = ? ORDER BY id", (n,)).fetchall()
            self.bot.call("sendMessage", chat_id=chat_id, text=L.card(row, events)[:MAX_LEN], reply_markup=buttons(n))
        elif cmd == "/cancel":
            c.execute("DELETE FROM cb_state WHERE chat_id=? AND user_id=?", (chat_id, uid))
            c.commit()
            self.bot.call("sendMessage", chat_id=chat_id, text="отменено")
        else:
            self.bot.call("sendMessage", chat_id=chat_id, text="это к профильному боту. здесь только /mine /status /ticket")
        return None

    # ---------- цикл ----------
    def poll_forever(self, timeout=25):
        offset = int(load_offset())
        while True:
            try:
                self.flush()
                res = self.bot.call("getUpdates", timeout=timeout, offset=offset, allowed_updates='["message","callback_query"]')
                if not res.get("ok"):
                    err = str(res.get("error", ""))
                    print("getUpdates: %s" % err[:300])
                    if "409" in err or "Conflict" in err:
                        print("ТОКЕН ЗАНЯТ ДРУГИМ ПОЛЛЕРОМ (шлюз?) — нужен отдельный бот для Boss-заявок.")
                        return 2
                    time.sleep(5)
                    continue
                for upd in res.get("result", []):
                    offset = max(offset, int(upd.get("update_id", 0)) + 1)
                    save_offset(offset)
                    try:
                        self.handle(upd)
                    except Exception as exc:
                        print("update %s: %s" % (upd.get("update_id"), exc))
            except KeyboardInterrupt:
                return 0
            except Exception as exc:
                print("loop: %s" % exc)
                time.sleep(5)


OFFSET_FILE = os.path.expanduser("~/.hermes/boss_tickets.offset")


def load_offset():
    try:
        with open(OFFSET_FILE) as fh:
            return fh.read().strip() or 0
    except OSError:
        return 0


def save_offset(v):
    try:
        with open(OFFSET_FILE, "w") as fh:
            fh.write(str(v))
    except OSError:
        pass


def main(argv):
    load_env()
    dry = "--dry-run" in argv
    token = os.environ.get("BOSS_BOT_TOKEN", "").strip()
    owners = [x for x in os.environ.get("BOSS_OWNER_IDS", "").replace(";", ",").split(",") if x.strip()]
    chat_id = os.environ.get("BOSS_CHAT_ID", "").strip()
    if not owners and os.environ.get("TELEGRAM_ALLOWED_USERS"):
        owners = [x for x in os.environ["TELEGRAM_ALLOWED_USERS"].split(",") if x.strip()]

    if "--update" in argv:
        path = argv[argv.index("--update") + 1]
        with open(path, encoding="utf-8") as fh:
            upd = json.load(fh)
        Bossd(Bot(token, dry=dry), owners, chat_id).handle(upd)
        return 0

    if not token:
        print("BOSS_BOT_TOKEN не задан в %s — сервису нужен токен отдельного бота." % ENV_FILE)
        return 2

    svc = Bossd(Bot(token, dry=dry), owners, chat_id)
    if "--flush" in argv:
        print("отправлено: %d" % svc.flush())
        return 0
    if "--once" in argv:
        print("отправлено: %d" % svc.flush())
        return 0
    return svc.poll_forever()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""ticket_status.py — сменить статус заявки (обёртка над ticket.py status).

Использование:
  ticket_status.py T-0001 in_progress
  ticket_status.py T-0001 done "сделано"
Статусы: new, in_progress, review, done, rejected.
"""
import subprocess
import sys

TICKET = "/root/.hermes/scripts/ticket.py"
STATUSES = ("new", "in_progress", "review", "done", "rejected")
RU = {"new": "новая", "in_progress": "в работе", "review": "на проверке", "done": "закрыта", "rejected": "отклонена"}


def main(argv):
    args = argv[1:]
    if len(args) < 2 or args[1] not in STATUSES:
        sys.exit("использование: ticket_status.py T-0001 <" + "|".join(STATUSES) + ">")
    tid, status = args[0], args[1]
    if status == "done":
        cmd = [sys.executable, TICKET, "close", tid] + args[2:]
    else:
        cmd = [sys.executable, TICKET, "status", tid, status, "--from", "boss"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        sys.exit("ошибка: %s" % ((r.stderr or out).strip()[:160]))
    print(out.splitlines()[0] if out else "готово")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

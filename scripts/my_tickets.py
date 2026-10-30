#!/usr/bin/env python3
"""my_tickets.py — открытые заявки этого бота (обёртка над ticket.py list --from).

Использование:
  my_tickets.py            # открытые, максимум 10
  my_tickets.py review     # фильтр по статусу
  my_tickets.py --all      # включая закрытые
Источник: $HERMES_PROFILE (имя профиля-бота).
"""
import os
import subprocess
import sys

TICKET = "/root/.hermes/scripts/ticket.py"
MAX = 10
STATUSES = ("new", "in_progress", "review", "done", "rejected")


def main(argv):
    src = os.environ.get("HERMES_PROFILE") or "default"
    cmd = [sys.executable, TICKET, "list", "--from", src, "--limit", str(MAX)]
    args = argv[1:]
    if "--all" in args:
        cmd.append("--all")
    elif args and args[0] in STATUSES:
        cmd += ["--status", args[0]]
    elif args:
        sys.exit("статусы: " + ", ".join(STATUSES))
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        sys.exit("ошибка: %s" % ((r.stderr or out).strip()[:160]))
    lines = [l for l in out.splitlines() if l.strip()][:MAX]
    print("\n".join(lines) if lines else "пусто")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

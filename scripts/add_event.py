#!/usr/bin/env python3
"""add_event.py — добавить событие в Google Calendar.

Использование:
  add_event.py "Созвон" 2026-11-05 10:00 30
  add_event.py "Врач" 2026-11-05 14:00 60 --where "Clinic" --desc "взять карту"

Аргументы: заголовок, дата ГГГГ-ММ-ДД, время ЧЧ:ММ, длительность в минутах.
"""
import sys
from datetime import datetime, timedelta

import _gcommon


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = {}
    i = 1
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            opts[argv[i][2:]] = argv[i + 1]
        i += 1
    # опции не должны попасть в позиционные
    pos = []
    skip = set()
    for k, v in opts.items():
        skip.add(v)
    pos = [a for a in args if a not in skip]
    if len(pos) < 3:
        sys.exit('использование: add_event.py "Заголовок" ГГГГ-ММ-ДД ЧЧ:ММ [минут]')
    title, d, t = pos[0], pos[1], pos[2]
    mins = int(pos[3]) if len(pos) > 3 else 60
    try:
        start = datetime.strptime("%s %s" % (d, t), "%Y-%m-%d %H:%M").astimezone()
    except ValueError:
        sys.exit("дата/время в формате ГГГГ-ММ-ДД ЧЧ:ММ")
    end = start + timedelta(minutes=mins)
    body = {
        "summary": title,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    if opts.get("where"):
        body["location"] = opts["where"]
    if opts.get("desc"):
        body["description"] = opts["desc"]
    svc = _gcommon.service("calendar", "v3")
    try:
        ev = svc.events().insert(calendarId=_gcommon.calendar_id(), body=body).execute()
    except Exception as e:
        sys.exit("ошибка Google Calendar: %s" % str(e).split("\n")[0][:200])
    print("добавлено: %s · %s–%s · %s" % (title, start.strftime("%d.%m %H:%M"), end.strftime("%H:%M"), ev.get("id", "")[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

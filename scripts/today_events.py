#!/usr/bin/env python3
"""today_events.py — события Google Calendar на сегодня (или на дату).

Использование:
  today_events.py              # сегодня
  today_events.py 2026-11-05   # конкретный день

Календарь: workspace/calendar_id.txt или $GCAL_ID, иначе "primary".
Service account видит только расшаренные ему календари — при пустом ответе
проверь, что календарь открыт на client_email из google.json.
"""
import sys
from datetime import date, datetime, timedelta

import _gcommon


def main(argv):
    day = date.today()
    if len(argv) > 1:
        try:
            day = datetime.strptime(argv[1], "%Y-%m-%d").date()
        except ValueError:
            sys.exit("дата в формате ГГГГ-ММ-ДД")
    start = datetime(day.year, day.month, day.day).astimezone()
    end = start + timedelta(days=1)
    svc = _gcommon.service("calendar", "v3")
    cid = _gcommon.calendar_id()
    try:
        res = svc.events().list(
            calendarId=cid,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        sys.exit("ошибка Google Calendar: %s" % str(e).split("\n")[0][:200])
    items = res.get("items", [])
    if not items:
        print("%s пусто" % ("сегодня" if day == date.today() else day.isoformat()))
        return 0
    for ev in items:
        s = ev.get("start", {})
        if "dateTime" in s:
            t1 = datetime.fromisoformat(s["dateTime"]).astimezone().strftime("%H:%M")
            e1 = ev.get("end", {}).get("dateTime")
            t2 = datetime.fromisoformat(e1).astimezone().strftime("%H:%M") if e1 else ""
            when = "%s–%s" % (t1, t2)
        else:
            when = "весь день"
        loc = ev.get("location")
        print("%s %s%s" % (when, ev.get("summary", "(без названия)"), " · " + loc if loc else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

# Bot scripts: Google service account, live-schema probing, Hermes python env

Condensed recipes for `~/.hermes/scripts/*.py` that talk to Google Sheets/Calendar or to Proxmox, on a host where system `python3` is bare.

## Installing Google client libs (no pip on system python)

`/usr/bin/python3 -m pip` is absent, and `uv pip install` into a venv would need every script shebang to change. Install into the interpreter the agent actually invokes:

```bash
UV=$(find /root/.hermes/tools -maxdepth 2 -name uv -type f | head -1)
$UV pip install --python /usr/bin/python3 --break-system-packages \
    google-api-python-client google-auth google-auth-httplib2
```

Verify with an import that cannot be confused with a real failure:

```bash
python3 -c "import googleapiclient.discovery, google.oauth2.service_account; print('OK')"
```

`googleapiclient.__version__` does not exist — an `AttributeError` on that attribute is a bad probe, not a failed install. Never conclude "install failed" from it.

## Service account client (google.json)

```python
import os, json
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/calendar"]

def hermes_home():
    return Path(os.environ.get("HERMES_HOME") or "/root/.hermes")

def creds_path():
    for p in [hermes_home()/"credentials"/"google.json",
              Path("/root/.hermes/credentials/google.json")]:
        if p.is_file():
            return p
    return None

def service(api, version):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    cp = creds_path()
    if cp is None:
        raise SystemExit("Google не подключён: нет credentials/google.json")
    creds = service_account.Credentials.from_service_account_file(str(cp), scopes=SCOPES)
    return build(api, version, credentials=creds, cache_discovery=False)
```

Layout: `~/.hermes/credentials/google.json` is the master copy; each profile that needs it gets `profiles/<p>/credentials/google.json` (`chmod 600`). Per-profile non-secret config lives in `profiles/<p>/workspace/`: `sheet_id.txt` (one line), `calendar_id.txt`, `pve_host.txt`.

## Probe before writing ranges

```python
svc = service("sheets", "v4")
meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
print(meta["properties"]["title"])
for s in meta["sheets"]:
    p = s["properties"]
    print(repr(p["title"]), p.get("gridProperties"))
```

Then dump the first rows of the tab you intend to touch (`values().get(range="<tab>!A1:H10")`) and write the parser against what came back: date formats, `\u00a0` inside amounts, absent status columns, header rows at 3–4 instead of 1 (a calendar-style "Месяц" tab puts days in one row, times in column A, entries as a grid).

Symptom to recognise: `HttpError 400 ... "Unable to parse range: <tab>!A1:AZ100"` means the tab name is wrong, **not** that credentials or sharing failed. Auth failures come back as 401/403 with a service-account/permission message.

## Script conventions

- Shebang `#!/usr/bin/env python3` + `chmod +x`; keep stdlib-only where Google is not involved.
- Read config from `$HERMES_HOME/workspace/*.txt`; exit with one human line (`sys.exit("нет sheet_id: …")`) when missing — never traceback into a Telegram reply.
- Ticket wrappers derive the source from `$HERMES_PROFILE` so one file serves all bots.
- Amounts: strip `\u00a0` and `₽`, accept both `,` and `.` decimals before parsing.
- `--dry` on anything that writes or reboots; print the exact target cell/CTID in dry mode.

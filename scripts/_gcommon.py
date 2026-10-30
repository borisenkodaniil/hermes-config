#!/usr/bin/env python3
"""Общие утилиты для скриптов Hermes (Google service account + sheet id).

Профиль-безопасно: пути берутся из $HERMES_HOME.
"""
import os
import sys
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or "/root/.hermes")


def creds_path():
    cands = [
        hermes_home() / "credentials" / "google.json",
        Path("/root/.hermes/credentials/google.json"),
    ]
    for p in cands:
        if p.is_file():
            return p
    return None


def service(api: str, version: str):
    """Google API клиент на service account (google.json)."""
    cp = creds_path()
    if cp is None:
        sys.exit("Google не подключён: нет credentials/google.json")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:  # pragma: no cover
        sys.exit("нет библиотек Google: %s" % e)
    creds = service_account.Credentials.from_service_account_file(str(cp), scopes=SCOPES)
    return build(api, version, credentials=creds, cache_discovery=False)


def sheet_id():
    p = hermes_home() / "workspace" / "sheet_id.txt"
    if not p.is_file():
        sys.exit("нет sheet_id: положи ID таблицы в %s" % p)
    v = p.read_text().strip()
    if not v:
        sys.exit("sheet_id пуст: %s" % p)
    return v


def calendar_id():
    p = hermes_home() / "workspace" / "calendar_id.txt"
    if p.is_file() and p.read_text().strip():
        return p.read_text().strip()
    return os.environ.get("GCAL_ID") or "primary"


def get_range(rng: str):
    svc = service("sheets", "v4")
    res = svc.spreadsheets().values().get(spreadsheetId=sheet_id(), range=rng).execute()
    return res.get("values", [])

#!/usr/bin/env python3
"""pct_restart.py — перезапуск LXC на Proxmox (по SSH).

Использование:
  pct_restart.py 101
  pct_restart.py 101 --dry     # только показать команду

Хост: $HERMES_HOME/workspace/pve_host.txt (или $PVE_HOST).
"""
import os
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or "/root/.hermes")


def pve_host():
    p = HOME / "workspace" / "pve_host.txt"
    if p.is_file() and p.read_text().strip():
        return p.read_text().strip()
    if os.environ.get("PVE_HOST"):
        return os.environ["PVE_HOST"]
    sys.exit("нет адреса PVE: положи IP в %s (или $PVE_HOST)" % p)


def main(argv):
    pos = [a for a in argv[1:] if not a.startswith("--")]
    if not pos:
        sys.exit("использование: pct_restart.py <CTID> [--dry]")
    ctid = pos[0]
    if not ctid.isdigit():
        sys.exit("CTID должен быть числом, получено: %s" % ctid)
    dry = "--dry" in argv
    cmd = "pct reboot %s" % ctid
    if dry:
        print("[dry] ssh root@%s '%s'" % (pve_host(), cmd))
        return 0
    host = pve_host()
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "root@" + host, cmd],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        sys.exit("ошибка reboot CT %s: %s" % (ctid, (r.stderr or r.stdout).strip()[:160]))
    st = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "root@" + host, "pct status %s" % ctid],
        capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    print("CT %s: reboot отправлен · %s" % (ctid, st or "статус ?"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

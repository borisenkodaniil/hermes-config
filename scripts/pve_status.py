#!/usr/bin/env python3
"""pve_status.py — состояние Proxmox-хоста и контейнеров (по SSH).

Хост: $HERMES_HOME/workspace/pve_host.txt (или $PVE_HOST).
Ключ: ~/.ssh/id_ed25519, BatchMode (без пароля).
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


def ssh(cmd, host):
    r = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
         "root@" + host, cmd],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        sys.exit("нет SSH-доступа к %s: %s" % (host, (r.stderr or "").strip()[:160]))
    return r.stdout


def main():
    host = pve_host()
    ver = ssh("pveversion | head -1", host).strip()
    load = ssh("awk '{print $1, $2, $3}' /proc/loadavg; free -m | awk 'NR==2{print $3\"/\"$2\" MB\"}'; df -h / | awk 'NR==2{print $5\" занято\"}'", host).strip().splitlines()
    print(ver or "pve: нет данных")
    print("load/cpu: %s" % (load[0] if load else "?"))
    print("ram: %s" % (load[1] if len(load) > 1 else "?"))
    print("disk /: %s" % (load[2] if len(load) > 2 else "?"))
    print("--- CT ---")
    print(ssh("pct list", host).strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())

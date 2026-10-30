#!/bin/bash
# Graceful recycle of the Hermes gateway, driven by gw-recycle.path.
# Trigger: touch /root/.hermes/gw-recycle-request
# Runs OUTSIDE the gateway's cgroup (system unit), so the restart cannot kill
# the restarter. Logs every step so the next session can verify the outcome.
set -u
FLAG=/root/.hermes/gw-recycle-request
LOG=/root/.hermes/logs/gw-recycle.log
DELAY="${GW_RECYCLE_DELAY:-90}"

rm -f "$FLAG"
echo "$(date '+%F %T') recycle requested; waiting ${DELAY}s before restart" >>"$LOG"
sleep "$DELAY"

export XDG_RUNTIME_DIR=/run/user/0
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/0/bus"

if ! systemctl --user restart hermes-gateway.service >>"$LOG" 2>&1; then
  echo "$(date '+%F %T') restart command failed" >>"$LOG"
fi

sleep 15
if systemctl --user is-active --quiet hermes-gateway.service; then
  echo "$(date '+%F %T') gateway is active after recycle" >>"$LOG"
else
  echo "$(date '+%F %T') gateway NOT active, starting it" >>"$LOG"
  systemctl --user start hermes-gateway.service >>"$LOG" 2>&1
  sleep 10
  systemctl --user is-active --quiet hermes-gateway.service \
    && echo "$(date '+%F %T') gateway recovered on retry" >>"$LOG" \
    || echo "$(date '+%F %T') gateway STILL DOWN - manual action needed" >>"$LOG"
fi

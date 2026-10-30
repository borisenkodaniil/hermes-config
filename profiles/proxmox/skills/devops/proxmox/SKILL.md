---
name: proxmox
description: "Proxmox VE: LXC-контейнеры, сеть, media-стек (jellyfin/radarr/sonarr)."
---

# Proxmox VE: контейнеры, сеть, медиа-стек

## Доступ

Этот хост — LXC `Hermes` (192.168.1.237), `pct/qm/pvesh` тут НЕТ. Работа с PVE — по SSH на хост.

Адрес хоста: `$HERMES_HOME/workspace/pve_host.txt`. Если файла нет — спросить один раз `IP или hostname Proxmox-хоста?`, записать в файл, дальше не спрашивать.

Путь читать только через `$HERMES_HOME`: здесь это `/root/.hermes/profiles/proxmox/workspace/pve_host.txt`. Литерал `/root/.hermes/workspace/pve_host.txt` пуст или принадлежит другому профилю — тогда `ssh` падает с `Could not resolve hostname :`, и это ошибка пути, а не отсутствие доступа.

```bash
PVE=$(cat $HERMES_HOME/workspace/pve_host.txt)
ssh -o BatchMode=yes -o ConnectTimeout=8 root@"$PVE" 'pveversion -v | head -1'
```

BatchMode падает → доложить `нет SSH-доступа к $PVE` и предложить заявку на доступ. Ключ: `~/.ssh/id_ed25519`, отдельный для OpenWRT: `~/.ssh/owrt_id_ed25519`.

## Контейнеры (LXC)

```bash
ssh root@"$PVE" 'pct list'                      # все CT + статус
ssh root@"$PVE" 'pct status 101'                # running/stopped
ssh root@"$PVE" 'pct start 101; pct stop 101'   # пуск/стоп
ssh root@"$PVE" 'pct exec 101 -- systemctl status jellyfin --no-pager'
ssh root@"$PVE" 'pct exec 101 -- df -h /'       # диск внутри CT
ssh root@"$PVE" 'pct config 101'                # сеть, rootfs, mp0
```

Правила: `pct stop` только после явного согласия (это даунтайм сервиса). Перед изменениями `pct config` → сохранить вывод в отчёт. ID контейнера не угадывать — брать из `pct list`.

**Перед reboot/start/stop всегда сверяй ID с `pct list`.** `pct reboot <id>` для несуществующего CT отдаёт `VM <id> not running` — это не «контейнер выключен», а отсутствие конфига: проверь `pct config <id>` (`Configuration file … does not exist`), затем доложи «CT <id> нет на хосте» и назови реальные ID из `pct list`. Не начинай `pct start` по такой ошибке — она не про статус.

Перезапуск — скриптом `python3 /root/.hermes/scripts/pct_restart.py <CTID>` (сначала `--dry` для показа команды); он же не сверяет ID, так что проверка `pct list` остаётся на тебе.

## Сеть

```bash
ssh root@"$PVE" 'cat /etc/network/interfaces'
ssh root@"$PVE" 'bridge link show; ip -br a'
```

Ориентиры: `vmbr0` — LAN-бридж, VLAN через `bridge-vids`/`tag=`; DHCP-адрес CT — `pct config <id> | grep net0`. Изменение `/etc/network/interfaces` → `ifreload -a`, и только с подтверждением: ошибка рубит сеть хоста.

## Media-стек

Обычно jellyfin / radarr / sonarr / qbittorrent в отдельных CT или одном docker-CT.

```bash
ssh root@"$PVE" 'pct exec <id> -- docker ps --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"'
ssh root@"$PVE" 'pct exec <id> -- docker restart sonarr'
ssh root@"$PVE" 'pct exec <id> -- du -sh /var/lib/docker/volumes 2>/dev/null'
```

Частые причины: диск заполнен (`df -h`), *arr не видит путь к медиа (проверить bind-mount в `pct config`, `mp0:`), VPN-контейнер лёг (qbittorrent без трафика). Логи: `docker logs --tail 50 <name>`.

## Ответ и заявки

Диагностика — коротко: `CT 101 jellyfin · running · диск 92%` → причина → что делать. Без лекций.

Нужны действия руками владельца (перезагрузка хоста, правка сети, замена диска) — НЕ создавай тикет сразу.
Сначала черновик + кнопки подтверждения:

```bash
python3 /root/.hermes/scripts/ticket.py draft "<что нужно>" --user "<uid>" --profile proxmox
```

→ один `clarify` с `choices=["Принять","Редактировать","Отмена"]`. Только после «Принять»:

```bash
python3 /root/.hermes/scripts/ticket.py draft-accept <id черновика>
```

и ответ `Заявка T-XXXX создана` (номер — из вывода команды). `ticket.py new` ботом не вызывается вообще (CLI его блокирует без `--confirmed`).

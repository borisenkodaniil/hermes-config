Hermes на этом хосте: LXC "Hermes" 192.168.1.237, systemd-user unit hermes-gateway.service (мультиплекс 4 профилей-ботов: default, proxmox, calendar, schedule; у каждого свой TELEGRAM_BOT_TOKEN в profiles/<p>/.env). pct/qm на хосте НЕТ — Proxmox только по SSH.
§
Заявки (тикеты) ботов: sqlite /root/.hermes/tickets.db + CLI /root/.hermes/scripts/ticket.py (new/list/show/status/comment/close, номера T-0001). Навыки-команды: skills/work/{tickets,mine,task,today,week,month,pay}, proxmox-навык в profiles/proxmox/skills/devops/proxmox.
§
Рестарт шлюза изнутри сессии заблокирован guard'ом (любая команда, ссылающаяся на скрипт с systemctl restart hermes-gateway). Рабочий путь: touch /root/.hermes/gw-recycle-request → gw-recycle.path → /root/.hermes/scripts/recycle_worker.sh (system unit, ждёт 90с, перезапускает, логирует в logs/gw-recycle.log).
§
Google ботов: service account lyubov@sincere-bay-513119-k5.iam.gserviceaccount.com, ключ ~/.hermes/credentials/google.json (+копии в profiles/{calendar,schedule}/credentials/). Таблица графика (schedule): 1twTaQsv5vihYs3GBGbqwKlwseFjmvdosCttO_WpOkH4, листы Месяц/Журнал/Оплаты (листа «График» нет).
§
Скрипты ~/.hermes/scripts/: show_schedule, add_column, calc_debts, today_events, add_event (Google, через _gcommon.py), pve_status, pct_restart (SSH, нужен workspace/pve_host.txt), my_tickets, ticket_status, ticket.py, patterns.py (реестр patterns.db).
§
Скрипты ботов: /root/.hermes/scripts/ — _gcommon.py (Google service account + sheet_id из $HERMES_HOME/workspace/), show_schedule.py/add_column.py/calc_debts.py (листы «Месяц»/«Журнал»/«Оплаты» таблицы 1twTaQsv5vihYs3GBGbqwKlwseFjmvdosCttO_WpOkH4), today_events.py/add_event.py (calendar_id в workspace/calendar_id.txt = demcenkol621@gmail.com), pve_status.py/pct_restart.py (workspace/pve_host.txt, SSH root), my_tickets.py/ticket_status.py, patterns.py (patterns.db). Google-библиотеки стоят в /usr/bin/python3 через uv --break-system-packages.
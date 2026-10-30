---
name: mine
description: "Команда /mine — мои открытые заявки (созданные этим ботом)."
---

# /mine — мои заявки

Показать открытые заявки, созданные этим ботом (источник = профиль бота).

```bash
python3 /root/.hermes/scripts/ticket.py list --from "$HERMES_PROFILE"
```

Аргумент после `/mine` (если есть): фильтр по статусу, например `/mine review`:

```bash
python3 /root/.hermes/scripts/ticket.py list --from "$HERMES_PROFILE" --status review
```

Ответ: только строки `T-XXXX [статус] текст · источник · дата`, максимум 10, без вступлений.
Если пусто — `пусто`. Ничего не выдумывать.

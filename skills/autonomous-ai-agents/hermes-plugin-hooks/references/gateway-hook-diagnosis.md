# Почему футер не появился в чате бота — порядок проверки

Проверять в этом порядке, каждый шаг даёт однозначный ответ. Не начинать со второго шага: «плагин не загрузился» — частая ошибка вывода.

## 1. Виден ли плагин каждому профилю

```bash
for p in proxmox calendar schedule; do printf "%-9s " $p; hermes -p $p plugins list | grep -c <name>; done
```

Пусто → discovery этого home не видит плагин (user-плагины ищутся в `$HERMES_HOME/plugins`, у профиля это `~/.hermes/profiles/<p>/plugins`). Симлинк на общий каталог, потом повторить.

## 2. Зарегистрировался ли `register()` в нужном процессе

Временная диагностика в самом плагине (в `plugin.yaml` не нужна, потом удалить):

```python
def _dbg(msg):
    try:
        with open(f"/root/.hermes/logs/{_NAME}-debug.log", "a") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} pid={os.getpid()} {msg}\n")
    except Exception:
        pass

def register(ctx):
    _dbg("register() called")
    def cb(**kw):
        _dbg(f"hook usage={kw.get('usage')!r}")
    ctx.register_hook("post_api_request", cb)
```

`pid` в строке `register()` — ответ на вопрос «в каком процессе»: один и тот же pid в `post_api_request` значит плагин живёт в шлюзе, а не только в одноразовом процессе CLI.

## 3. Где в коде применяется правка ответа (координаты, проверенные чтением исходников)

- `agent/turn_final_response.py` (`finish_text_response`) — единственная точка, где `transform_llm_output` применяется к готовому тексту, **до** записи в сессию; при `_transformed` обновляет `final_msg["content"]`.
- `agent/turn_finalizer.py` — `apply_llm_output_transform()` (идемпотентна по `turn_id`, результат кэшируется в `agent._llm_output_transform`), `_apply_output_hooks()` (звенит `post_llm_call` после трансформа).
- `hermes_cli/lifecycle.py::invoke_hook()` — перед диспетчеризацией делает `if safe_worker_enabled(): return []`; это первое, что надо исключить, если колбэк молчит.
- `hermes_cli/plugins.py::invoke_hook()` → `_delivery_manager().invoke_hook()`; хуки из `_HOOK_TIMEOUT_BOUNDED_HOOKS` и `pre_tool_call` исполняются на worker'е с таймаутом `plugins.hook_callback_timeout` и по таймауту **fail open** (тихо пропускаются).

## 4. Где искать доказательство вместо лога

- Записи в файле-счётчике (`spend.json`) и в `state.db` (`messages.content` с маркером футера) — только они доказывают, что хук дошёл до доставки.
- `grep -a '💰'` по сохранённому выводу одноразового запроса — быстрая проверка вне шлюза.
- Загрузка general-плагина в INFO почти не логируется; единственная надёжная строка — своя `_dbg`.

## Если transform в конкретном пути молчит

Не выдавать это за «хук сломан» и не переписывать ядро наугад. Рабочие варианты по возрастанию инвазивности:

1. `hold_stream=True` при регистрации — заставляет Hermes отдать ответ после переписывания (для редактуры/фильтрации; для футера не обязателен, но снимает гонку со стримингом).
2. Дописывать строку в gateway-адаптере после `post_llm_call`: `_apply_output_hooks()` уже держит `final_response` и `platform`.
3. Патч ядра — только с доказательством из шага 2 (pid + отсутствие строки от нужного хука).

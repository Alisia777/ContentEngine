# Инвентарь секретов и процедуры ротации

Дата: 2026-09-03. Значения ключей в этом документе НЕ приводятся.

## Инвентарь

| Секрет | Где живёт | Что даёт |
| --- | --- | --- |
| SUPABASE_SERVICE_ROLE_KEY | `.env` в корне репо на ПК Сергея (после переезда — и `/opt/contentengine/.env` на VPS); edge-функциям выдаётся платформой автоматически | Полный доступ к проду (god-mode) |
| FAL_KEY | `.env` (ПК/VPS) + env edge-функций | Платные генерации и TTS fal |
| SUPABASE_ACCESS_TOKEN + SUPABASE_PROJECT_REF | env деплой-сессии (шелл Сергея) | Management API: миграции, деплой edge, секреты |
| CONTENTENGINE_WORKER_SECRET | Supabase Vault + env edge | Авторизация внутреннего вызова background-worker (timing-safe) |
| HEALTHCHECKS_MEDIA_WORKER_URL / HEALTHCHECKS_BACKGROUND_WORKER_URL | `.env` (ПК/VPS) / секрет edge | Dead-man-switch пинги; малочувствительны (только ping) |
| Ключи площадок (HeyGen, Runway) | env edge-функций | Платные провайдеры |

**Резервная копия (полоса Сергея, 1 час):** SUPABASE_SERVICE_ROLE_KEY,
FAL_KEY, SUPABASE_ACCESS_TOKEN и CONTENTENGINE_WORKER_SECRET — в
оффлайн-менеджер паролей. Сейчас service-role ключ существует в
единственной копии на одном диске: умер диск = потерян доступ к проду.

## Ротация

### FAL_KEY (просто, простой ~1 мин)
1. Кабинет fal.ai → создать новый ключ.
2. Обновить `.env` на ПК (и VPS), `docker compose ... restart
   media-preparation-worker`.
3. Обновить секрет edge через Management API, передеплоить затронутые
   функции при необходимости.
4. Отозвать старый ключ. Во время простоя платный TTS падает в бесплатный
   edge-tts-фолбэк штатно.

### SUPABASE_SERVICE_ROLE_KEY (СНАЧАЛА выяснить тип ключей!)
- Если в проекте включены новые API-ключи (`sb_secret_*`): ротация
  независимая — создать новый secret key → обновить `.env` ПК/VPS →
  перезапустить воркеры → отозвать старый. Веб не затрагивается.
- Если проект на **legacy JWT-ключах**: ротация JWT-секрета меняет И
  anon/publishable-ключ, вшитый в сборку веба → обязательна пере-выкладка
  gh-pages сразу после ротации, иначе портал у всех отвалится.
  Не ротировать в пятницу вечером.

### CONTENTENGINE_WORKER_SECRET
Процедура описана в docs/BACKGROUND_WORKER_OPERATIONS.md (Vault + env
edge). Кратко: новое значение в Vault → обновить env функции → проверить
ближайший cron-ран succeeded.

### SUPABASE_ACCESS_TOKEN
Personal access token Supabase: отозвать в аккаунте → выпустить новый →
обновить env деплой-сессии. Ничего в проде не ломает.

## Правила

- `.env` в `.gitignore` — проверяется перед каждым коммитом сборки;
  build_pages_release.py дополнительно ловит секретоподобные строки.
- Ключи не выводятся в чат, логи и тесты.
- После ротации любого ключа — смоук: claim пустой очереди воркером,
  один cron-ран background-worker, вход в портал.

# VPS для воркера медиа-подготовки: runbook развёртывания

Дата: 2026-09-03. Цель: финализация и подготовка видео перестают зависеть
от включённого ПК Сергея. Ожидаемое время: ~1 час чистыми руками.

## 0. Заказ (полоса Сергея)

- Размер: **4 vCPU / 8 GB RAM / 40+ GB SSD** (с запасом под будущий
  publishing-воркер; ffmpeg на 1080p ест память).
- ОС: Ubuntu 22.04/24.04 LTS.
- Провайдер: RU — только после проверки egress (шаг 2) ДО оплаты месяца;
  иначе EU (Hetzner/аналог). Критичен исходящий доступ к supabase.co,
  queue.fal.run и Microsoft edge-tts.
- Решение: даёшь ли ssh-ключ Клоду (тогда обновления кода делаю я),
  или обновляешь по этому runbook сам.

## 1. Базовая подготовка

```bash
apt update && apt install -y git curl ca-certificates
curl -fsSL https://get.docker.com | sh
```

## 2. Проверка egress (ДО оплаты на RU-провайдере)

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://iyckwryrucqrxwlowxow.supabase.co/rest/v1/
curl -sS -o /dev/null -w "%{http_code}\n" https://queue.fal.run/
curl -sS -o /dev/null -w "%{http_code}\n" https://speech.platform.bing.com/
```

Ожидание: любые HTTP-коды (401/404/200) — важно отсутствие таймаутов и
connection refused. Таймаут на любом из трёх = менять провайдера.

## 3. Код и секреты

```bash
mkdir -p /opt/contentengine && cd /opt/contentengine
git clone <URL репозитория> .
```

Создать `/opt/contentengine/.env` (права 600) с тремя строками — значения
берутся из оффлайн-менеджера паролей (см. docs/SECRETS_AND_KEY_ROTATION.md):

```
SUPABASE_SERVICE_ROLE_KEY=...
FAL_KEY=...
HEALTHCHECKS_MEDIA_WORKER_URL=...
```

## 4. Запуск

```bash
cd /opt/contentengine
docker compose -f docker-compose.vps.yml up -d --build
docker compose -f docker-compose.vps.yml logs -f media-preparation-worker
```

Ожидание в логах: `started, poll=3s`, без ошибок сети. Первая сборка
образа идёт несколько минут (apt + pip, включая ffmpeg и edge-tts).

## 5. Параллельный прогон (24 часа)

Оба воркера (ПК + VPS) могут работать одновременно: claim атомарный
(`for update skip locked`), задание достаётся одному. Оба пингуют один
healthchecks-чек — это корректно: мониторим «очередь обслуживается»,
а не конкретную машину.

Проверка боем: поставить финализацию из портала → задание done → в логах
VPS виден его job_id (или ПК — не важно, очередь общая).

## 6. Cutover

1. На ПК: `docker compose -f docker-compose.local.yml stop
   media-preparation-worker`.
2. Поставить финализацию из портала → done силами VPS.
3. Негативный тест: `docker compose -f docker-compose.vps.yml stop` на
   20 минут → алерт healthchecks в Telegram + уведомление реапера в
   колокольчике портала → `up -d` → задание доехало.
4. Приёмка Алисией: «финализация работает при выключенном ПК Сергея».

## 7. Обновления кода дальше

- Правки python-кода воркера: `cd /opt/contentengine && git pull &&
  docker compose -f docker-compose.vps.yml restart media-preparation-worker`
  (код в бинд-монте, rebuild не нужен).
- Изменения requirements.txt / Dockerfile.local: `git pull && docker
  compose -f docker-compose.vps.yml up -d --build`.
- Ротация ключей: обновить `/opt/contentengine/.env` → restart.

# Забор видео v1 (контур №1)

Состояние на 27.08.2026, сборка `.31`. Один вход для исходников; реестр
источников один — research_exact_youtube_sources (второй не строится).

## Пользовательский путь

1. «Материалы» → карточка **«Забрать видео»**, три способа:
   - **Ссылка** (YouTube: watch / youtu.be / shorts / m. / embed / live) —
     нормализуется к `https://youtube.com/watch?v=<11>` и регистрируется
     источником проекта (идемпотентно; дубль — «уже зарегистрирован»).
     Другие платформы честно отклоняются до отдельного включения (ТЗ 3.2).
   - **Файл MP4** — переход к действующей форме загрузки с предвыбранной
     ролью «Исходное видео».
   - **Уже в проекте** — переход в файлы проекта.
2. **Intake v2 в «Копии»**: карточка «1. Исходный ролик» → свёрнутый блок
   «Оригинал по ссылке (необязательно)»: ссылка + галка «файл — этот же
   ролик, права есть» → «Привязать ссылку». Выбранный MP4 при загрузке
   получает несмываемый след происхождения.

## Границы

- Автоскачивание с платформ не выполняется (ТЗ 3.3): файл прикладывает
  человек; совпадение файла и ссылки подтверждает человек.
- Ссылка ≠ файл: регистрация ссылки доказывает происхождение идеи, не
  наличие файла.

## Сущности и RPC

- `research_exact_youtube_sources` — реестр (существующий, append-only).
- `contentengine_register_exact_youtube_source` — регистрация (существующий).
- `creator_stamp_media_origin_url` (202608270002) — несмываемый штамп
  `origin_url_canonical` / `origin_video_id` / `origin_source_id` в metadata
  медиа: только kind=source_video и artifact_class=source, ставится один раз,
  повтор с другим URL — отказ `media_origin_already_stamped`.

## Подготовка исходника (воркер, ТЗ 3.8–3.9)

Анализ и чистый мастер выполняет provider-free воркер на стенде — вне
браузера и вне edge (масштаб «20–50 человек» не тянется браузером).

- Очередь `media_preparation_jobs` (202608270003): kind `analyze` |
  `clean_master`, статусы queued/claimed/done/failed, lease heartbeat
  10 минут, до 5 попыток. Один активный джоб на (media, kind).
- Операторские RPC: `creator_enqueue_media_preparation`,
  `creator_media_preparation_status`. Системные (только service_role):
  `system_claim_…`, `system_heartbeat_…`, `system_complete_media_analysis`,
  `system_complete_media_clean_master`, `system_fail_…`.
- Воркер `scripts/media_preparation_worker.py` (stdlib + ffmpeg/ffprobe из
  докер-образа репо, сервис `media-preparation-worker` в
  docker-compose.local.yml; ключ — только из `.env`, в репозитории его нет):
  - **analyze**: длительность/размер/fps/звук, `cropdetect` (рамка),
    `freezedetect` (статичные интро/аутро), эвристика «похоже на запись
    экрана»; факты штампуются в metadata медиа ключами `prep_*`.
  - **clean_master**: трим статичных краёв (минимум 4 с остаётся), кроп
    рамки, апскейл до 720 (lanczos), H.264 CRF18 + faststart, звук aac или
    честное «без звука», потолок 50 МБ. Итог регистрируется НОВЫМ
    media_object: kind=source_video, role=`source_video_clean`,
    `derived_from_media_id` — исходник не перезаписывается, происхождение
    (origin_*) наследуется. Чистый файл можно выбирать в «Копии»/«Создании»
    как обычный исходник.
- Карточка «Материалов» (202608270004): у видео-исходника — кнопка
  «Проанализировать»; когда анализ увидел запись экрана — «Создать чистый
  мастер»; prep_-факты показываются строкой на карточке.

## Тесты

- `tests/test_media_video_intake_v1.py` — карточка, node-прогон нормализации
  (8 видов адресов), intake v2 и штамп происхождения.
- `tests/test_media_preparation_worker_v1.py` — очередь/ACL, воркер,
  compose, кнопки карточки; смоук ffmpeg-цепочки в докер-образе (SMOKE_OK).

## Не в этом этапе

Метаданные платформы (title/author/thumbnail), sha-дедуп на загрузке,
evidence-кадры воркером, TikTok/Instagram/VK.

# YouTube Analytics: официальный коннектор

Для YouTube production-путь использует официальный сетевой адаптер `youtube_oauth`.
Он вызывает YouTube Analytics API v2 `reports.query` через HTTPS. Mock-клиент,
`settings_json.mock_metrics` и тестовые строки в default-пути отсутствуют.

## Граница секрета

В `DestinationConnection.credential_ref` хранится только логическая ссылка,
например `env:YOUTUBE_ANALYTICS_ACCESS_TOKEN`. Сам access token находится во
внешнем secret backend и передаётся через injected `CredentialResolver`.
Default resolver читает `NAME` или `env:NAME` из окружения.

Токен:

- не сохраняется в БД;
- не попадает в query string — только в `Authorization: Bearer ...`;
- не возвращается в readiness/sync result;
- не записывается в audit и тексты ошибок;
- не находится в `settings_json`.

OAuth consent, code exchange и refresh token rotation не реализованы внутри
этого модуля. Их должен выполнять проверенный OAuth/secret service. YouTube
использует OAuth 2.0 для доступа к пользовательским данным, а `reports.query`
требует scope `https://www.googleapis.com/auth/youtube.readonly`:
[OAuth 2.0 для YouTube](https://developers.google.com/youtube/v3/guides/authentication),
[reports.query](https://developers.google.com/youtube/analytics/reference/reports/query).

## Настройка без секретов

Допустимый `settings_json`:

```json
{
  "channel_id": "MINE",
  "video_ids": ["AbCdEf12345"],
  "video_map": {
    "AbCdEf12345": {
      "final_url": "https://www.youtube.com/watch?v=AbCdEf12345",
      "publishing_task_id": 123
    }
  }
}
```

`video_ids` обязателен; максимум 200 видео на один атомарный pull. Такой лимит
не допускает молчаливо неполную выборку до появления pagination/batching.
`final_url` и `publishing_task_id` не считаются доверенными: ingestion повторно
проверяет организацию, платформу, опубликованный task и точную идентичность поста.

Запрос использует:

- `ids=channel==MINE` либо явно настроенный channel ID;
- `dimensions=video`;
- `filters=video==...` только для разрешённого списка;
- `metrics=views,likes,comments,shares,estimatedMinutesWatched,averageViewPercentage`;
- закрытый `startDate/endDate`.

Набор допустимых метрик и video dimension определён официальными
[channel reports](https://developers.google.com/youtube/analytics/channel_reports).
Порядок значений берётся из `columnHeaders`, как требует
[модель данных YouTube Analytics](https://developers.google.com/youtube/analytics/data_model).

Нормализация:

- `estimatedMinutesWatched * 60 -> watch_time_seconds`;
- `averageViewPercentage / 100 -> retention_rate`;
- неизвестные, отрицательные, нечисловые, дробные integer-метрики;
  незаказанные и повторные video IDs закрывают sync с ошибкой.

Клики, заказы и выручка не выдумываются: YouTube Analytics adapter их не
создаёт. Они приходят из tracking link или подтверждённого manual/CSV источника.

## Организация, retries и cumulative snapshots

`DestinationConnectorSyncService.sync` требует:

- `organization_id`;
- `destination_id`;
- `connection_id`;
- активного `actor_user_profile_id` в этой организации;
- `period_start`, `period_end`;
- timezone-aware `observed_at`;
- стабильный `sync_key` для повторов одного pull.

До сетевого вызова service проверяет ownership destination/connection и
membership. Один и тот же `sync_key + observed_at + response` становится
idempotent replay. Новый pull получает новый `sync_key` и более поздний
`observed_at`; cumulative-поля заменяются, а не суммируются. Неоднозначная или
чужая атрибуция идёт в quarantine через `SocialMetricIngestionService`.

Readiness считается `ready=true` только после успешного официального API-вызова,
который установил `oauth_verified`. Наличие строки `credential_ref` само по себе
не считается подтверждённой авторизацией.

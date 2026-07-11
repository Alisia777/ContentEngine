# Destination Connectors: безопасный production-контур

Контур метрик разделён на два явных пути:

```text
официальный API -> organization-scoped adapter -> quarantine/ingestion
ручной файл     -> explicit Manual/CSV import -> quarantine/ingestion
```

Ни один manual, CSV, stub или mock payload не проходит через кнопку/метод
«официальная синхронизация».

## Реальная готовность платформ

| Платформа | Production adapter | Поведение сейчас |
|---|---:|---|
| YouTube Analytics | Да | OAuth secret reference + официальный `reports.query` |
| Instagram Insights | Да | Instagram professional OAuth + owned `media_map` + официальный Media Insights |
| TikTok Display API | Да | OAuth `video.list` + owned `video_map` + официальный `/v2/video/query/` |
| Facebook | Нет | blocked; manual/CSV fallback |
| Telegram | Нет | blocked; manual/CSV fallback |
| VK | Нет | blocked; manual/CSV fallback |
| Wildberries / Ozon | Нет | blocked; authorized marketplace export fallback |

Legacy-строки `instagram_stub`, `tiktok_stub` и `telegram_bot` не возвращают fake
data и не становятся connected из-за заполненного поля или токена. Production
типы называются отдельно: `instagram_oauth` и `tiktok_oauth`.

## Запрещённые shortcuts

- `settings_json.mock_metrics` отклоняется при создании/обновлении connection;
- default YouTube, TikTok, Instagram и Telegram connector не создаёт mock client;
- manual/csv connection не исполняется через `DestinationConnectorSyncService`;
- readiness не доверяет произвольным `status=connected` для платформы без
  реализованного adapter;
- raw token, refresh token, password, cookie, client secret, credential_ref и
  credential-bearing/signed URL внутри settings отклоняются;
- секреты и сама ссылка `credential_ref` не отражаются в публичном view/result.

Старые строки БД с `mock_metrics` остаются инертными: production sync их не
читает. Их следует удалить операционной миграцией после резервной копии.

## Ownership и fail-closed

Официальный service API требует организацию и destination явно. Проверки
membership и `organization -> destination -> connection` происходят до вызова
внешнего API. Чужой или legacy-unscoped destination возвращается как not found,
не раскрывая наличие connection.

Ошибки транспорта/авторизации возвращают только стабильный error code. Response
body провайдера и token не пишутся в audit. Неизвестные строки ответа не
«подбираются» к похожему посту: они блокируются или попадают в quarantine.

Подробный контракт YouTube: [YOUTUBE_ANALYTICS_CONNECTOR.md](./YOUTUBE_ANALYTICS_CONNECTOR.md).
Контракты TikTok и Instagram: [OFFICIAL_SOCIAL_CONNECTORS.md](./OFFICIAL_SOCIAL_CONNECTORS.md).

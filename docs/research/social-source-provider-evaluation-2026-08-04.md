# Оценка источников Instagram и YouTube

Статус: verified research snapshot

Дата проверки: 2026-08-04

Область: наблюдение за публичными конкурентами и трендами для обучаемой контент-машины.

## Решение

Production-маршрут — **official-first**:

1. YouTube retrieval/display — официальный YouTube Data API v3 в controlled rollout. Derived competitor/trend classification включается отдельно и только после зафиксированного analytics-amendment approval.
2. Instagram — официальный Meta Instagram API: lookup известных Professional accounts и ограниченный Hashtag Search после OAuth/App Review. Произвольный поиск аккаунтов не поддерживается и остаётся `coverage_gap`.
3. Непокрытые данные отображаются как измеримый gap готовности категории. Система не заменяет их LLM-догадкой или скрытым scraping fallback.
4. Apify, Bright Data, Oxylabs и DataForSEO регистрируются только как технические кандидаты со статусом `disabled_by_policy`. Их наличие и собственные compliance-заявления не являются разрешением Meta или YouTube на автоматический сбор.
5. Scraper-adapter можно активировать только после отдельного документированного legal/compliance approval для конкретной платформы, набора полей, географии, retention и use case. По умолчанию он не вызывается, не планируется и не получает credentials.

Критичное ограничение: [Meta Terms](https://www.facebook.com/terms/) запрещают автоматизированный сбор без предварительного разрешения Meta. [YouTube Developer Policies](https://developers.google.com/youtube/terms/developer-policies) прямо запрещают API-клиентам scraping, cross-owner aggregation и derived data/metrics по умолчанию. Начиная с 1 июня 2026 года допустимые categorization/scoring use cases перечислены в [Additional policies for derived metrics](https://developers.google.com/youtube/terms/derived-metrics-policy), но только для audited developers, принявших amendment через quota-extension process. Условия агрегатора не отменяют эти правила.

## Проверенная матрица

| Провайдер | Покрытие и авторизация | Цена/квота на дату проверки | Автоматизация | Решение |
|---|---|---|---|---|
| **Meta Instagram API** | Bearer OAuth, Meta App и требуемые permissions/App Review. Facebook Login lane позволяет получать hashtag media и базовые данные/метрики известных Business/Creator accounts; consumer accounts и произвольный account search не покрываются. [Официальная Meta workspace](https://www.postman.com/meta/instagram/overview), [API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api), [Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/), [Hashtag Search](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search/) | Per-call тариф не опубликован; действуют Graph API и endpoint-specific limits. [Rate limiting](https://developers.facebook.com/docs/graph-api/overview/rate-limiting/) | Webhooks для событий подключённого Professional account; polling обновляет только заранее известные targets. Hashtag discovery ограничен endpoint policy, arbitrary competitor discovery недоступен. [Webhook examples](https://www.postman.com/meta/instagram/folder/23987686-5049585f-09b2-4775-a11a-debe5956e09a) | `enabled_official` только для явно разрешённых capabilities; остальное `unsupported_coverage_gap` |
| **YouTube Data API v3** | API key для публичных reads; OAuth для private/write и Analytics владельца. Публичные channels, videos, playlists, search, comments и доступные statistics. [API reference](https://developers.google.com/youtube/v3/docs), [Analytics authorization](https://developers.google.com/youtube/analytics/reference) | Default после изменения 2026 года: 100 `search.list` calls/day, 100 uploads/day и 10,000 units/day для остальных endpoints. [Quota overview](https://developers.google.com/youtube/v3/getting-started), [revision history](https://developers.google.com/youtube/v3/revision_history) | WebSub/PubSubHubbub для uploads и изменений title/description; polling для остальных наблюдений. [Push notifications](https://developers.google.com/youtube/v3/guides/push_notifications) | Retrieval/display: `enabled_official` в существующем controlled rollout. Cross-owner competitor/trend scoring: `approval_required` до принятого analytics amendment и `approval_ref`; затем только в одобренных границах. [Data policy](https://developers.google.com/youtube/terms/developer-policies#e.-handling-youtube-data-and-content), [derived metrics policy](https://developers.google.com/youtube/terms/derived-metrics-policy) |
| **Apify** | Bearer API token. Maintained Instagram Actor покрывает profiles, posts, Reels, comments, hashtags и mentions. Рассмотренный YouTube Actor — сторонний Store Actor и использует внутренний web API. [Instagram Actor](https://apify.com/apify/instagram-scraper), [YouTube Actor](https://apify.com/s-r/youtube-scraper), [API auth](https://docs.apify.com/api/v2) | Instagram: от $2.70/1k результатов на Free до $1.50/1k на Business. Рассмотренный YouTube Actor: $3.20/1k videos + $0.002/run. Platform plans: Free, $29 Starter, $199 Scale, $999 Business. [Pricing](https://apify.com/pricing) | Cron schedules и completion/failure webhooks. [Schedules](https://docs.apify.com/actors/running/schedules), [Webhooks](https://docs.apify.com/integrations/webhooks) | `disabled_by_policy`; [Terms](https://docs.apify.com/legal/general-terms-and-conditions) и [AUP](https://docs.apify.com/legal/acceptable-use-policy) возлагают правомерность use case на клиента |
| **Bright Data** | Bearer API key. Заявлены Instagram profiles/posts/comments/hashtags и YouTube channels/videos/comments/transcripts/discovery. [Instagram Scraper API](https://brightdata.com/products/web-scraper/instagram), [YouTube Scraper API](https://brightdata.com/products/web-scraper/youtube) | 5k free records/month; PAYG success-based $1.50/1k; Scale $499 с 384k records и $1.30/1k overage. [Web Scraper pricing](https://brightdata.com/pricing/web-scraper) | API/manual/schedule; webhook, S3, GCS, Azure, SFTP и Snowflake delivery. [Collection and delivery](https://docs.brightdata.com/datasets/scraper-studio/initiate-collection-and-delivery-options) | `disabled_by_policy`; [AUP](https://brightdata.com/acceptable-use-policy) и [License](https://brightdata.com/license) не заменяют разрешение target platform |
| **Oxylabs Web Scraper API** | Basic Auth. Есть отдельные YouTube sources для search, channel, metadata, transcript, subtitles и download. Отдельный Instagram target в проверенной официальной документации не найден. [YouTube sources](https://developers.oxylabs.io/scraping-solutions/web-scraper-api/targets/youtube), [API overview](https://developers.oxylabs.io/scraping-solutions/web-scraper-api) | Free trial до 2k results; планы от $49/month, success-based стоимость зависит от target/rendering. [Pricing](https://oxylabs.io/products/scraper-api/web/pricings) | Cron Scheduler, async Push-Pull, callback и cloud storage. [Scheduler](https://developers.oxylabs.io/scraping-solutions/web-scraper-api/features/scheduler), [Push-Pull](https://developers.oxylabs.io/scraping-solutions/web-scraper-api/integration-methods/push-pull) | `disabled_by_policy`; `youtube_download` особенно конфликтует с YouTube audiovisual-content restrictions. [Oxylabs AUP](https://oxylabs.io/legal/acceptable-use-terms) |
| **DataForSEO** | Basic Auth. YouTube Organic, Video Info, Comments и Subtitles; Instagram отсутствует — Social Media API сейчас поддерживает только Pinterest. [YouTube overview](https://docs.dataforseo.com/v3/serp-youtube-organic-overview/), [Social Media coverage](https://docs.dataforseo.com/v3/business_data-social_media-overview/) | YouTube Search/Comments: $0.0006 standard, $0.0012 priority, $0.002 live за базовый блок 20 результатов; Video Info/Subtitles — 3x. Минимальный платёж $50; общий лимит до 2,000 calls/min. [YouTube pricing](https://dataforseo.com/pricing/serp/youtube-serp-api), [limits](https://docs.dataforseo.com/v3/appendix-errors/) | Queue-based Standard mode, `pingback_url`/`postback_url`; расписание создаёт наша система. [Task POST](https://docs.dataforseo.com/v3/serp-youtube-organic-task_post/) | `disabled_by_policy` для YouTube; техническая доступность scraped SERP не доказывает допустимость использования. [Terms](https://dataforseo.com/terms-of-service) |

Цены — снимок на дату проверки и должны перепроверяться перед закупкой. Ни один ценовой план не является доказательством права собирать или обучаться на данных платформы.

## Provider-neutral adapter

```text
SocialObservationAdapter
  capabilities()
  discover(query, market, time_window, cursor)
  list_creator(external_id, cursor)
  fetch_content(ids)
  fetch_public_metrics(ids)
  subscribe(target, callback)
  normalize(raw) -> ObservationEnvelope
```

`capabilities()` обязан возвращать не только технические функции, но и policy boundary:

```text
platforms, modes, auth_kind, allowed_fields,
compliance_state, approval_ref, retention_days,
supports_schedule, supports_webhook, spend_limit
```

Разрешённые состояния: `enabled_official`, `approval_required`, `enabled_licensed`, `disabled_by_policy`, `paused`, `expired_approval`. Состояние задаётся отдельно для каждой capability; unknown всегда fail-closed.

## ObservationEnvelope

```json
{
  "provider": "youtube_official_v3",
  "adapter_version": "...",
  "platform": "youtube",
  "external_id": "...",
  "source_url": "...",
  "observed_at": "...",
  "published_at": "...",
  "retrieved_via": "official_api",
  "auth_scope": ["public_read"],
  "compliance_state": "enabled_official",
  "approval_ref": null,
  "allowed_uses": ["retrieval_display"],
  "raw_hash": "...",
  "raw_snapshot_ref": "...",
  "retention_until": "...",
  "facts": {},
  "metrics": {},
  "provenance": {}
}
```

Обязательные инварианты:

- raw payload не становится training corpus автоматически;
- YouTube-derived classification/scoring не запускается, пока capability не имеет состояния `approved` и точного `approval_ref` для analytics amendment;
- каждый факт и вывод сохраняет provider, locator, время наблюдения и hash источника;
- обновление создаёт новую immutable observation, а не переписывает историю;
- удаление/скрытие источника и истечение retention инвалидируют зависимые анализы;
- YouTube API Data и внешние trend signals не смешиваются без явной маркировки происхождения;
- readiness показывает недостающую платформу, capability, квоту, freshness или approval и предлагает безопасное следующее действие;
- переключение provider не происходит автоматически: оно требует новой policy-проверки и подтверждения оператора.

## Рекомендуемый rollout

1. Использовать `youtube_official_v3` только для разрешённого retrieval/display; derived analysis держать в `approval_required` до принятого amendment и точного `approval_ref`.
2. Подключить `instagram_meta_graph` по capability: known Professional lookup и hashtag discovery после OAuth/App Review; arbitrary account discovery показывать как gap.
3. Добавить scheduler/WebSub/webhook ingestion через единый envelope и idempotency key.
4. При недостаточном официальном покрытии показывать `coverage_gap`, а не запускать scraper fallback.
5. Хранить сторонние adapter definitions без credentials и execution permission в состоянии `disabled_by_policy`.
6. Любой будущий licensed provider активировать отдельной записью approval с точным сроком, полями, retention, бюджетом и kill switch.

# Выбор источников Instagram и YouTube для обучаемой контент-машины

Статус: proposed, 2026-08-03
Область: публичное исследование категории, конкурентов и трендов; данные
авторизованных авторов; автоматическое обновление источников.

## Решение

У машины не будет одного «универсального social scraper». Нужны два явно
разделённых контура:

1. **Официальные/авторизованные данные** — YouTube Data API v3, Meta Instagram
   API и при необходимости Phyllo. Этот контур используется для данных
   собственного или согласившегося автора и для тех публичных professional-
   метрик, которые официально доступны.
2. **Публичное наблюдение за конкурентами** — лицензированный коммерческий
   поставщик. Предпочтительный production-кандидат — Bright Data; Apify —
   ограниченный пилот; Data365 — enterprise-альтернатива. Подключение любого из
   них требует отдельного договора, проверки допустимого использования,
   retention/deletion-политики и жёсткого лимита расходов.

Для YouTube первым production-adapter остаётся уже подготовленный
`youtube_data_api_v3`. Для Instagram до завершения legal/procurement review
никакой внешний adapter автоматически не включается. Отсутствие поставщика
должно отображаться как измеримый пробел готовности категории, а не маскироваться
LLM-догадкой.

## Короткий список

| Вариант | Instagram | YouTube | Подходящий сценарий | Текущая цена/ограничение | Решение |
|---|---:|---:|---|---|---|
| YouTube Data API v3 | — | да | Поиск публичных видео и каналов, метаданные и счётчики | `search.list`: до 50 результатов, 100 вызовов/day и 1 unit в отдельном Search Queries bucket; `videos.list` — 1 unit | Основной YouTube provider |
| Meta Instagram API / Business Discovery | да | — | Собственный professional-аккаунт и базовые данные/метрики других professional-аккаунтов | Нужен токен professional-аккаунта; consumer-аккаунты не покрываются | Только официальный/owner lane |
| Bright Data Scraper API | да | да | Публичные профили, posts/reels/videos/comments, batch и регулярная доставка | 5 000 records/month free; pay-as-you-go $1.50 за 1 000 успешно доставленных records; spend limits | Предпочтительный коммерческий кандидат после review |
| Apify Actors | да | да | Быстрый технический пилот и редкие точечные сборы | Instagram maintained actor: от $2.70/1k на Free до $1.50/1k; YouTube Actor зависит от автора, пример — около $3.01/1k videos | Пилот, не единственная production-зависимость |
| Data365 | да | заявлена multi-social поддержка | Большой единый поток, search, profiles, posts/comments и исторические выборки | от €300/month за 1 сеть и 500 000 credits; 14-day trial; async обычно 1–5 минут | Enterprise benchmark / резервный кандидат |
| EnsembleData | да | да | Недорогой единый API для сравнительного canary | Free 50 units/day; от $100/month за 1 500 units/day | Проверить качество и legal posture до выбора |
| Phyllo | да | да | Данные автора, который явно подключил аккаунт | Коммерческий API, цена через sales | Только consented creator lane |
| Modash | да | да | Influencer discovery и campaign tracking | от $299/month при годовой оплате по опубликованному тарифу | Не использовать как основной raw-source pipeline |

Цены являются снимком на 2026-08-03 и должны перепроверяться перед закупкой.

## Почему Bright Data — первый коммерческий кандидат

- один контракт покрывает Instagram и YouTube;
- есть URL и discovery-входы, synchronous/asynchronous jobs, JSON/NDJSON/CSV,
  webhook и облачная доставка;
- оплата заявлена только за успешно доставленные записи;
- доступны batch/scheduled collection и месячные spend limits;
- provider публикует KYC, Acceptable Use и compliance-позицию.

Это не означает автоматического юридического разрешения. До canary владелец
системы должен письменно подтвердить:

- допустимость конкретного use case и географий;
- какие поля можно хранить и сколько дней;
- обработку удаления/скрытия исходного контента;
- права на коммерческий анализ и использование для ML;
- запрет сбора private, login-only и чувствительных данных;
- DPA, webhook signing, incident process и итоговый hard spend cap.

## Почему Apify остаётся пилотом

Apify удобен для быстрого запуска, расписаний и API, а Instagram Actor
поддерживается самим Apify. Но YouTube/часть специализированных Actors создают
сторонние разработчики: схема, цена и поведение могут меняться независимо. Для
production нужны pinned Actor version, recorded fixtures, schema validation,
health canary и право без потери lineage заменить Actor. Автоматический fallback
между Actors запрещён: он способен создать двойной расход и разные по смыслу
данные.

## Границы официальных API

YouTube `search.list` подходит для category query, channel filter, языка,
региона и временного окна. Результат поиска сам по себе не является доказанным
трендом: машине нужны несколько наблюдений во времени и независимые каналы.
YouTube API Data хранится и обновляется только в рамках действующих Developer
Policies; derived metrics и длительное хранение нельзя считать автоматически
разрешёнными.

Instagram Business Discovery возвращает базовые метаданные и метрики других
Instagram professional accounts, но запрос идёт от professional-аккаунта
пользователя. Он не превращает официальный API в полный parser всех consumer-
аккаунтов. Meta owner data, public professional discovery и коммерческий public
scraping — разные adapters и разные trust boundaries.

## Контракт подключения provider

Новый provider можно активировать только после того, как сохранены:

- `provider_key`, точная `adapter_version` и версия условий;
- разрешённые платформы, поля и режим discovery;
- credential reference только на сервере;
- max records/run, cadence и месячный hard budget;
- retention/deletion SLA;
- успешный recorded-fixture test и ручной canary;
- явное `automatic_collection_ack` пользователя;
- rollback/pause switch без automatic retry/fallback.

Readiness/status RPC ничего не собирает и не тратит. Scheduler может создать
только один durable job для due policy. Внешний transport получает отдельный
lease, максимум одну provider-попытку и immutable receipt. Неизвестный исход
замораживается для проверки, а не запускается повторно.

## Что разрешено «обучать»

Сохраняются source locator, provider, account/content identity, время
наблюдения, публичные метрики, content hash, structural tags, confidence,
человеческая корректировка и outcome собственных экспериментов. Raw captions,
чужие сценарии, слоганы и длинные тексты конкурентов не становятся prompt-
шаблонами или training corpus.

Процент в интерфейсе — **готовность доказательной базы категории**, а не
«интеллект ИИ». Каждое очко должно раскрываться до измерения, цели, недостающих
данных и следующего безопасного действия.

## Источники решения

- [YouTube Data API `search.list`](https://developers.google.com/youtube/v3/docs/search/list)
- [YouTube Data API `videos.list`](https://developers.google.com/youtube/v3/docs/videos/list)
- [YouTube API Services Terms](https://developers.google.com/youtube/terms/api-services-terms-of-service-emea)
- [YouTube Developer Policies guide](https://developers.google.com/youtube/terms/developer-policies-guide)
- [Meta Instagram Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery)
- [Meta Instagram API collection in Postman](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Bright Data Instagram Scraper API](https://brightdata.com/products/web-scraper/instagram)
- [Bright Data YouTube Scraper API](https://brightdata.com/products/web-scraper/youtube)
- [Bright Data Instagram API docs](https://docs.brightdata.com/datasets/scrapers/instagram/introduction)
- [Apify Instagram Scraper](https://apify.com/apify/instagram-scraper)
- [Apify YouTube Scraper example](https://apify.com/automation-lab/youtube-scraper)
- [Data365 pricing](https://data365.co/pricing)
- [EnsembleData pricing](https://ensembledata.com/pricing)
- [Phyllo API documentation](https://docs.getphyllo.com/)
- [Modash pricing](https://www.modash.io/pricing)

# Social source aggregators for the learning machine

Статус: решение по архитектуре и поставщикам
Проверено: 2026-08-04

## Что измеряет ContentEngine

Шкала `0–100%` в категории — это
`category_evidence_readiness_not_model_iq`, то есть покрытие категории
проверяемыми источниками и разборами. Это не IQ модели, не accuracy и не
гарантия качества контента.

В шкалу входят шесть объяснимых измерений:

- объём источников — 20%;
- разнообразие платформ — 15%;
- наблюдения за конкурентами — 20%;
- свежесть трендовых свидетельств — 15%;
- покрытие источников структурированным анализом — 15%;
- подтверждение человеком — 15%.

Интерфейс обязан показывать текущий балл, недостающие пункты, источник каждого
вывода, текущую версию разбора и append-only историю исправлений. Смена source
или analysis head делает зависимое поколение данных устаревшим; старое значение
не подставляется скрыто.

## Решение по поставщикам

Цены ниже — ориентир на дату проверки. Перед включением коннектора нужно заново
проверить тариф, лимиты, юрисдикцию и разрешённое использование данных.

| Поставщик | Что даёт | Цена / лимит на дату проверки | Решение |
|---|---|---|---|
| [Meta Instagram API — Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery) | Данные известного Professional Account: профиль, публикации и публичные счётчики. Произвольного поиска конкурентов по категории нет. | Нет публичной цены за вызов; нужны OAuth, permissions, App Review и соблюдение rate limits. | Основной production-источник Instagram для подтверждённых аккаунтов. Discovery решается отдельно. |
| [YouTube Data API](https://developers.google.com/youtube/v3/docs/search/list) | Поиск видео и каналов по запросу, времени, региону, языку и категории; метаданные и текущие счётчики. Транскрипты конкурентов официальный API не предоставляет. | Текущий отдельный лимит `search.list` — 100 запросов/день; для остальных endpoints действует квота 10 000 units/day. Увеличение требует compliance audit. | Основной production-discovery YouTube. Уже соответствует official-first архитектуре проекта. |
| [Bright Data Instagram/YouTube](https://brightdata.com/products/web-scraper/Instagram) | Instagram discovery, backfill; YouTube metadata, comments и transcripts; готовые datasets и регулярные обновления. | 5 000 records/month free; PAYG примерно $1.50/1 000; Scale от $499/month. Dataset-заказы имеют отдельные минимумы. | Лучший кандидат на управляемый пилот, но только после письменного подтверждения прав на конкретный dataset, AI/RAG use и retention. |
| [Apify Instagram Scraper](https://apify.com/apify/instagram-scraper) / [YouTube Scraper](https://apify.com/streamers/youtube-scraper) | Keyword/profile/hashtag discovery, posts/reels/comments, YouTube subtitles/transcripts; историю нужно собирать периодическими снимками. | Планы $0/$29/$199/$999 плюс usage; Instagram примерно $1.50–2.70/1 000 результатов, YouTube около $5/1 000 видео. | Только feature-flagged experiment. Условия возлагают проверку законности источника на клиента. |
| [Oxylabs YouTube Web Scraper API](https://developers.oxylabs.io/scraping-solutions/web-scraper-api/targets/youtube) | YouTube search/channel discovery, metadata, transcript/subtitles и scheduler. Поддерживаемого Instagram target в документации не найдено. | Trial 2 000 результатов; планы от $49/month, ориентир для other targets $1.15–1.35/1 000. | Только experiment после legal review; vendor-флаг `trainability` сам по себе не является лицензией. |
| [DataForSEO YouTube SERP API](https://docs.dataforseo.com/v3/serp/youtube/overview/) | YouTube keyword/location/language search, video info, top comments, subtitles. Instagram не поддерживается. | От $0.0006 за базовую SERP-задачу; отдельные YouTube endpoints имеют множители; minimum deposit $50. | Не использовать для команды или пользователя из РФ: [Terms](https://dataforseo.com/terms-of-service) запрещают такой доступ. В других юрисдикциях — только experiment. |

## Обязательные правовые границы

- [Meta Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)
  требуют отдельного письменного разрешения для автоматизированного сбора;
  договор с агрегатором сам по себе такого разрешения не создаёт.
- [Instagram Terms](https://www.facebook.com/help/instagram/581066165581870)
  запрещают неразрешённый автоматизированный сбор.
- [YouTube Terms](https://uk.youtube.com/t/terms) ограничивают bots и scraping без
  письменного разрешения. Поэтому scraper-агрегатор не становится production-safe
  только потому, что обрабатывает публичные страницы.
- Неавторизованные YouTube API Data нужно удалить или обновить не позднее чем
  через 30 дней. Для более долгого хранения статистики/derived analytics нужен
  отдельный одобренный use case по
  [Derived Metrics Policy](https://developers.google.com/youtube/terms/derived-metrics-policy).

## Рекомендуемый контур

1. YouTube: официальный Data API для discovery и текущих метрик.
2. Instagram: Meta Business Discovery для известных Professional Accounts.
3. Bright Data: ограниченный canary для discovery/backfill/transcripts только
   после письменного решения по лицензии, AI/RAG use и retention.
4. Apify и Oxylabs: адаптеры выключены по умолчанию, без fallback из официального
   API и без автоматического расхода.
5. В память попадает не сырой чужой контент, а проверяемый evidence record:
   `source URL → provider → captured_at → raw/parsed hash → legal basis →
   permitted_use → retention deadline → analysis version → human decision`.
6. Из подтверждённого анализа можно продвигать только абстрактные сигналы
   категории. Title, channel name, transcript, raw counters и provider payload не
   должны автоматически попадать в prompt или бессрочную память.

## Следующий технический срез

- editable query plan: ИИ предлагает поисковые запросы, пользователь может
  исправить и подтвердить их до вызова provider;
- longitudinal snapshots и честная velocity по значениям, а не только по наличию
  счётчиков;
- append-only promotion receipt
  `human decision → policy-safe category signal → generation policy`;
- автоматическое состояние `stale/revoked` при новой correction head, истечении
  retention или изменении разрешённого использования;
- точный экран lineage
  `source → analysis → decision → policy → generation specification`.

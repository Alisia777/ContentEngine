# Learning Content Machine v1

Статус: целевая архитектура и локально реализованный вертикальный срез P0/P1 до миграции `010`; live-rollout выключен
Дата: 2026-08-03

## 1. Цель

ContentEngine должен стать управляемой обучающейся машиной контента:

- система сама собирает доступные наблюдения, объясняет пробелы и предлагает
  следующий шаг;
- каждый этап создаёт отдельный проверяемый артефакт;
- пользователь может исправить, разветвить, утвердить, отклонить, вернуть или
  пересчитать любой этап без незаметной перезаписи истории;
- конкурентные и трендовые данные используются как источник гипотез, а не как
  разрешение копировать чужой контент или автоматически объявлять победителя;
- обучение активируется только на зрелых, атрибутированных и прошедших QA
  результатах.

Целевой цикл:

```text
наблюдение
→ профиль категории
→ конкуренты
→ трендовые сигналы
→ проверяемая гипотеза
→ генерация
→ QA
→ публикация
→ метрики
→ безопасная память обучения
→ следующая гипотеза
```

> Важная граница: миграция `202608030007_research_youtube_live_ingestion.sql`,
> Edge adapter и UI реализуют управляемые canary/refresh для официального YouTube
> Data API. Однако это не означает работающий production parser: provider catalog
> по умолчанию остаётся `planned/disabled`, отдельный global rollout gate —
> `disabled`; миграция и Edge не развёрнуты, API key не установлен, внешний
> runtime canary не выполнялся. Миграция `006` сама по себе не создаёт
> периодический refresh; локальный opt-in scheduler добавляется только в `010`
> и также default-disabled. Automatic fallback нет. Публичные YouTube API Data
> показываются только как отдельные
> наблюдения в порядке выдачи, удаляются в пределах retention и не используются
> в генерации; derived metrics, рейтинги, дельты и агрегации по ним запрещены.
> Миграция `007` добавляет read-only registry нескольких точных outcome scopes,
> а `008` — явную краткоживущую apply/control selection поверх активной advisory
> memory. Но binding selection к generation job намеренно закрыт, effectiveness
> остаётся `unknown`, `generation_binding_state=gated`, поэтому production
> generation consumption всё ещё `gated_not_wired`.
> Миграция `009` локально добавляет корректируемый stage graph: immutable branch
> и head events, точные текущие heads, `patch/reject/revert/fork/cancel` и
> подготовку `recompute` через отдельный дочерний research run. Каждая команда
> привязана к canonical hash точного snapshot всех семи heads; созданный `fork`
> остаётся read-only веткой сравнения без merge/promote. Свежая цепочка миграций и
> focused runtime fixtures проходят на PostgreSQL 17/PGlite, но контур не
> развёрнут в локальном Supabase или staging; browser E2E и реальный provider
> recompute не выполнялись. `recompute` требует отдельного подтверждения платного
> анализа, допускает одну provider-попытку и не запускается status RPC или
> фоновым worker. Queued-запрос можно отменить до provider claim, processing —
> только после истечения lease; cancel не вызывает provider/Edge, retry или
> spend. Наличие локального кода не означает production-доступность.
>
> Миграция `010` локально добавляет отдельный контур готовности доказательной
> базы категории: долговечный source ledger для источников product research,
> append-only историю структурированного разбора и человеческих исправлений,
> детерминированную шкалу 0–100 и bounded историю снимков. Это не «IQ ИИ», не
> accuracy и не гарантия качества. Временные наблюдения официального YouTube API
> учитываются только пока действует их retention и не копируются в бессрочную
> память; после purge их вклад обязан исчезнуть. Автоматический YouTube refresh
> может быть поставлен в очередь только после отдельных global, organization,
> retention, legal, terms, quota и hard-budget gates. Instagram остаётся
> fail-closed до выбора поставщика и юридического решения. Ни status RPC, ни
> рендер интерфейса не начинают внешний вызов.

### 1.1. Что реализовано в текущих P0, P1-A и P1-B foundation

- production Edge-схема теперь отдельно возвращает `category_analysis`,
  `competitor_analysis`, `trend_analysis` и `guidance`;
- каждый фактический вывод этих секций ссылается на provider-подтверждённые
  source IDs; недостаток данных допускает пустой результат и явное ограничение;
- time-based trend требует две разные даты и два независимых web-domain;
  пользовательское фото не считается publisher, snapshot обязан быть текущим,
  а model-extracted `published_at` ограничивает confidence уровнем `medium`;
- `coverage=sufficient` для конкурентов требует разные нормализованные названия,
  разные web sources и независимые publisher domains;
- конкурентные наблюдения ограничены короткими структурными паттернами, без raw
  captions, transcript и точной последовательности кадров;
- production UI показывает четыре управляемых этапа, следующий рекомендуемый
  шаг и отдельный человеческий слой правок, который попадает в новую версию ТЗ
  и задачи после approval;
- полные доказательства остаются неизменяемыми: человеческая правка не
  переписывает provider citations;
- миграция `202608030001_research_stage_control_ledger.sql` подготавливает
  immutable stage artifacts, per-stage evidence, dependency hashes и decision
  ledger; save/approve guards запрещают удалить v2 evidence, утвердить AI draft
  напрямую или скрыто обойти non-ready guidance;
- production validator покрыт исполняемыми Deno fixtures и включён в CI.
- миграция `202608030002_research_watchlist_memory.sql` добавляет RPC-only
  watchlist товара, immutable approved-v2 snapshots, точные source junctions,
  deterministic competitor/trend change set, contradiction marker, freshness
  и idempotent due proposals;
- существующий двухминутный background worker вызывает только provider-free
  proposal RPC. Он не создаёт `product_research_runs`, поэтому ни scheduler, ни
  watchlist не могут автоматически инициировать платный анализ;
- новый due proposal идемпотентно ставит tenant-scoped уведомление автору
  watchlist с exact deep link на исходный research run и явными признаками
  `paid_refresh_requires_confirmation=true`, `auto_spend=false`;
- production UI даёт явные `enable/update/pause/resume`, показывает историю и
  следующий шаг, а новый анализ открывает как предзаполненную форму с отдельным
  подтверждением стоимости.
- миграция `202608030003_research_provider_control_plane.sql` закрывает скрытый
  spend-path: `paid_analysis_ack` атомарно создаёт authorization вместе с run,
  claim без authorization запрещён, а Edge обязан неизменяемо связать ровно
  один allowlisted provider/adapter до внешнего HTTP-вызова;
- фактический ответ, отказ или неизвестный сетевой исход создаёт append-only
  passive health receipt. Status RPC сам не вызывает провайдера, не создаёт run,
  а automatic canary/fallback зафиксированы как `false`;
- каталог содержит production `openai_web_search` и disabled/planned
  `youtube_data_api_v3`: наличие записи YouTube не означает работающую загрузку
  данных или пройденный commercial/quota canary;
- миграция `202608030004_research_market_intelligence_identity.sql` отделяет
  динамическую рыночную категорию от закрытого compliance-контура: tenant-scoped
  registry, точные aliases и append-only product bindings меняются только через
  явные `bind/create/reclassify` решения с stale candidate hash;
- 14 structural signal IDs образуют immutable allowlist. Snapshot observations
  и source junctions сравниваются только внутри подтверждённой категории;
  переход legacy→canonical или смена категории начинает новую baseline без
  ложного роста, удаления или contradiction;
- production UI показывает authorization/adapter/health, предложение категории,
  текущую привязку и bounded trend timeline. Создание или переклассификация
  требуют отдельного checkbox и не меняют compliance category, не вызывают
  provider и не запускают новый анализ.
- миграция `202608030006_research_outcome_learning_control.sql` добавляет пять
  RPC-only append-only ledger: exact outcome lineage, candidate evidence,
  human decisions и versioned active/inactive memory с rollback target;
- refresh принимает только зрелые first-party cumulative metrics (не ранее 72
  часов после публикации) из точной цепочки approved research → scenario →
  generation signal/job → exact media → independent approved QA → placement;
- bounded evidence ограничено последними 10 000 outcome, не содержит raw prompt,
  competitor prose, captions или URL и требует минимум шесть наблюдений, два
  creative angle, по два продукта на angle и два общих продукта между группами;
- перед `activate` сервер повторно использует тот же exact live-source selector,
  что и refresh. Новая зрелая placement/metric/correction без captured lineage
  возвращает `research_outcome_refresh_required`; после явного refresh прежний
  кандидат становится superseded, а решение принимается только по новой версии;
- candidate никогда не активируется автоматически. Production UI показывает
  точный scope category/platform/model выбранного
  `recommended_scenario_position`, evidence, активную версию, rollback и
  immutable decision history; `activate/reject/quarantine/deactivate/revert`
  требуют отдельного подтверждения и причины и не вызывают provider, spend,
  generation, placement или publication actions;
- активированная версия остаётся рекомендацией и не подключена к auto-ТЗ,
  существующей generation-learning policy или платной генерации.
- миграция `202608030007_research_youtube_live_ingestion.sql` добавляет
  tenant-scoped request/lease/quota/retention ledger, ручные canary/refresh,
  transport receipts для `search.list` и `videos.list`, аварийную остановку и
  управляемые rollout/candidate решения. Edge и production UI поддерживают этот
  поток, но default global/provider gates не разрешают live-вызов до отдельного
  развёртывания, ключа и успешного runtime canary;
- YouTube API Data сохраняются с bounded retention как индивидуальные
  наблюдения. Они не создают outcome memory, generation signal или prompt input;
  производные метрики, ранжирование, сравнение и автоматический выбор кандидата
  по этим данным отсутствуют намеренно. После физической очистки неизменяемая
  контрольная запись ingestion остаётся в истории, но UI принимает её как
  штатно очищенную только при отдельном серверном доказательстве, что retention
  heartbeat пересёк 29-дневную границу этого запуска; без такого доказательства
  интерфейс остаётся fail-closed;
- миграция `202608030008_research_outcome_scope_registry.sql` добавляет
  read-only discovery до 50 точных category/platform/model scopes из approved
  scenario lineage и outcome ledgers. UI не угадывает scope при нескольких
  вариантах: пользователь выбирает точный контур, а status загружается только
  для него;
- миграция `202608030009_research_outcome_generation_consumption.sql` добавляет
  безопасный advisory и explicit apply/control selection с повторной проверкой
  category binding, active memory, candidate evidence и базовой policy. Эта
  foundation не записывает generation job и не может создать assignment:
  effectiveness пока `unknown`, binding `gated`, production consumption не
  подключён.
- миграция `202608030010_research_stage_control_loop.sql` добавляет точную
  идентичность входов stage artifact, tenant-scoped branches, append-only head
  events и защищённую текущую проекцию семи этапов. Каждая мутация требует
  совпадения `head_event_id`, `artifact_id`, `content_hash`, а также canonical
  `branch_revision_hash` ровно семи упорядоченных heads, явного confirmation и
  idempotency key;
- `patch` и `revert` создают новую версию/новый head без перезаписи истории,
  `reject` блокирует выбранный этап, а изменение upstream помечает downstream
  как `stale_dependency`. `fork` копирует точный snapshot heads только в
  read-only ветку сравнения: у неё нет patch/recompute/approval и нет
  merge/promote обратно в main;
- ручная корректировка сохраняется как отдельный `user_input` source. Approval
  повторно проверяет семь current heads, точные draft bindings, dependency hashes
  и отсутствие активного recompute; stale, rejected или несовпадающий snapshot
  fail-closed до generation handoff;
- `recompute` разрешён только для main-ветки и не для `sources`: после явного
  `paid_analysis_ack` создаётся дочерний `product_research_run` через существующий
  authorization/quota gate, максимум с одной provider-попыткой. Завершённый
  результат применяется только если branch не менялся; иначе он остаётся в
  аудите как `superseded`. Явный `cancel` закрывает queued request до provider
  claim либо processing request только после истечения его lease; активный
  processing lease отменить нельзя, а cancel не инициирует Edge, provider,
  retry или новый spend;
- если после prepare ветка независимо изменилась, request немедленно становится
  `superseded` даже при активном processing lease: текущая provider-попытка не
  повторяется и не прерывается небезопасно, а её поздний результат не применяется;
- bounded status RPC возвращает выбранную ветку, семь heads, ограниченную историю
  и один server-recommended next action без provider, spend, generation или
  publication side effects. Corrections UI загружает этот envelope отдельно от
  обычного polling research status и не повторяет provider-вызов автоматически.
- миграция `202608030011_research_category_learning_readiness.sql` добавляет
  category-level source registry, строгую схему
  `research-source-interpretation-v1`, exact-head correction chain и readiness
  из шести проверяемых измерений общим весом 100. Каждый пробел возвращает
  `current`, `target`, `missing` и следующий безопасный шаг;
- повторный URL/content hash не повышает шкалу второй раз, а исправление текущего
  разбора на `irrelevant` исключает источник из evidence coverage без удаления
  истории. Источники конкурентов считаются как дедуплицированные наблюдения, а
  не выдаются за доказанное число независимых конкурентов;
- retained YouTube observations и решения `confirm/exclude` остаются в
  ограниченном 29-дневном контуре миграции `006`. Они могут влиять только на
  текущую готовность и теряют этот вклад после физической очистки; raw captions,
  transcript и чужие сценарии в source analysis и learning memory запрещены;
- versioned collection policy требует точную версию YouTube Terms, явные
  automatic/quota/no-retry подтверждения, cadence и месячный hard limit.
  Service scheduler может материализовать только bounded `category_refresh`,
  а background worker перед единственной Edge-диспетчеризацией фиксирует
  provider claim. Потерянный сетевой ответ не превращается в автоматический
  повтор или fallback;
- Instagram policy можно сохранить только как `paused`: отсутствие выбранного
  provider contract отображается пользователю как конкретный пробел, а не
  заменяется скрытым scraper или LLM-догадкой. Кандидаты и условия выбора
  зафиксированы отдельно в `docs/SOCIAL_SOURCE_PROVIDER_DECISION.md`.

Дополнительно `app/category_intelligence` содержит pure in-memory reference-core
для recent-vs-baseline structural trends, coverage/readiness, безопасного
next-action и immutable revision graph. Это проверяемый доменный контракт, но
не production persistence и не provider ingestion.

Десять migrations этого среза проходят статический PostgreSQL parser, свежий
PostgreSQL 17/PGlite apply и focused runtime fixtures; pgTAP-контракты
подготовлены. Полный runtime Supabase/pgTAP и production rollout в этом окружении
недоступны. Stage-control loop реализован локально, но не применён в локальном
Supabase или staging и не прошёл реальный patch→stale→recompute→approve
round-trip. Пока также не реализованы работающий лицензированный social metadata
ingestion, развёрнутый YouTube adapter с ключом и успешным runtime canary,
метрическая trend velocity, production binding подготовленной selection к
generation job, причинный generation experiment и автоматический effectiveness
cooldown/revert. Поэтому текущий результат — управляемая
category/trend/provider/stage-control foundation, default-disabled YouTube
ingestion, exact multi-scope discovery и gated advisory selection; это ещё не
завершённая production learning machine.

## 2. Текущий production flow

Основной production-контур — статический кабинет из `web/app`, Supabase Auth,
PostgreSQL, Storage, RPC и узкие Edge Functions. Python/FastAPI-монолит остаётся
reference/regression-контуром и не доказывает наличие функции в production.

Текущий product-research flow:

1. Пользователь задаёт товар, SKU, публичную marketplace-ссылку или точные фото,
   целевые площадки, задачу и подтверждённые вводные.
2. `creator_start_product_research` требует `paid_analysis_ack=true`, атомарно
   создаёт durable run и server-side execution authorization с одним provider
   attempt и запрещённым automatic fallback.
3. `creator-product-research` получает run по lease только при наличии этой
   authorization, создаёт краткоживущие signed URLs и до внешнего HTTP-вызова
   фиксирует immutable provider/adapter/model binding.
4. Единственная разрешённая production-попытка вызывает OpenAI Responses API с
   `web_search`, image input, strict JSON schema и provider idempotency key.
5. Успех, отказ, деградация или неизвестный сетевой outcome сохраняются как
   passive health receipt. Ошибка не инициирует retry или fallback.
6. Edge Function принимает только интернет-ссылки, реально раскрытые provider
   citations, валидирует market/compliance identity и allowlisted structural
   signal IDs, затем сохраняет источники, AI draft и forecast.
7. Завершение исследования атомарно регистрирует его durable sources в точной
   рыночной категории. Edge без нового provider-вызова создаёт для них
   ограниченный структурированный разбор; ошибка этого спутникового контура не
   повторяет платный анализ и остаётся видимым пробелом готовности.
8. Пользователь редактирует ТЗ и три сценария. Каждое сохранение создаёт новую
   immutable-версию draft; утверждение создаёт задачи.
9. Отдельным бесплатным решением пользователь связывает предложенную рыночную
   категорию с существующим registry, создаёт новую или append-only
   переклассифицирует товар. Compliance category при этом не меняется.
10. Для утверждённого v2 пользователь может подключить watchlist. Snapshot
    сохраняет точные четыре research-секции, source IDs и change set относительно
    предыдущей утверждённой версии этого товара.
11. Для обычного платного product research background worker по-прежнему создаёт
    только due proposal: новый run требует отдельного подтверждения пользователя.
    Отдельно, после owner/admin opt-in и всех rollout/retention/terms/quota gates,
    он может preclaim и один раз передать bounded YouTube category refresh.
12. Утверждённый сценарий может быть подготовлен в генераторе. Платный запуск всё
    равно проходит отдельные readiness, budget, media-rights и spend gates.
13. Перед генерацией сервер вычисляет learning policy для точного товара,
    platform, model и одной из текущих compliance-категорий.
14. Generation signal хранит только ограниченные структурные признаки: угол,
    hook-patterns, источник сценария, hashes и lineage. Текст конкурента или
    произвольный прошлый prompt в память не попадает.
15. QA, публикация и зрелые метрики могут изменить следующую структурную
    рекомендацию. Пользователь может отключить рекомендацию и вернуться к
    базовому ТЗ.

Реальные сильные стороны текущего контура:

- server-only provider keys;
- строгая tenant isolation и role gates;
- provider-citation verification;
- immutable sources и versioned human drafts;
- human approval перед задачами и генерацией;
- fail-closed prompt/policy binding перед платным provider state;
- bounded learning вместо переноса сырого текста или claims.

Пробелы после текущего локального P0-среза:

- семь research stages теперь имеют отдельные immutable artifacts и versioned
  branch heads в миграции `009`; свежий PostgreSQL 17/PGlite apply проходит, но
  миграция не применена в локальном Supabase/staging, а
  production данные ещё не прошли backfill и tenant-isolation проверку;
- самостоятельные `patch`, `reject`, `revert`, `fork` и downstream-инвалидация
  реализованы локально. Полный browser round-trip, branch comparison, recovery
  после обрыва между prepare и Edge invoke и фактический selective recompute ещё
  не доказаны в живом Supabase;
- динамическая рыночная категория теперь отделена от compliance-категории и
  имеет append-only привязку, но merge/split lifecycle и перенос нескольких
  товаров между объединяемыми категориями ещё не реализованы;
- `app/category_intelligence` ранжирует уже готовые observations, но сам не
  вызывает provider API, не сохраняет observation history и не подключён к
  production product-research UI;
- базовый watchlist, immutable history и canonical trend timeline подготовлены,
  но scheduler пока создаёт только due proposal: нет provider cursor,
  first/last-seen у внешнего content entity и временных рядов внешних engagement
  metrics. Управляемый официальный YouTube ingestion и локальный auto-enqueue
  по cadence реализованы отдельно, но default gates закрыты, Edge/worker не
  развёрнуты и production runtime не проверен;
- восемь compliance-значений намеренно остаются закрытым allowlist; новая
  рыночная категория больше не обязана превращаться в `other`, однако решение
  compliance всё ещё требует отдельного bounded классификатора и проверки;
- provider catalog и passive receipts существуют; transport official YouTube
  реализован в SQL/Edge/UI, но запись `youtube_data_api_v3` остаётся
  disabled/planned, global gate закрыт, ключ и внешний canary отсутствуют.
  Licensed social vendor также ещё не подключён;
- production Supabase-портал пока опирается на ручные metric snapshots и
  first-party tracking clicks; reference Python connectors не означают, что
  production автоматически получает social/marketplace metrics. Локальный
  auto-enqueue YouTube остаётся default-disabled до применения миграций,
  deployment Edge/worker, установки API key, retention heartbeat и успешного
  ручного canary;
- нет доказательства, что текущие learned-рекомендации улучшают outcomes в
  production; наличие policy и тестов является необходимым, но не достаточным
  условием эффективности.

## 3. Целевая архитектура этапов

Каждый этап получает immutable входы и создаёт versioned artifact. Downstream
этап читает только конкретную утверждённую версию, а не «последнее значение».

| Этап | Основной артефакт | Автоматическая работа | Человеческий контроль |
| --- | --- | --- | --- |
| Observation | `observation_snapshot` | Получить и нормализовать доступное публичное наблюдение | Подтвердить источник, связь с товаром и допустимость использования |
| Category | `category_profile` | Предложить динамическую market category и широкую compliance category | Исправить, подтвердить или отклонить классификацию |
| Competitors | `competitor_snapshot` | Найти и сопоставить похожие предложения | Исключить ложного конкурента, исправить тип конкуренции |
| Trends | `trend_signal_set` | Выделить повторяющиеся, свежие и corroborated сигналы | Понизить уверенность, отметить сезонность или противоречие |
| Hypothesis | `content_hypothesis` | Предложить минимальный проверяемый creative experiment | Изменить angle, proof, platform, budget и критерий успеха |
| Generation | `generation_spec` и provider job | Собрать bounded prompt и выполнить разрешённую генерацию | Исправить spec, остановить spend, выбрать другую ветку |
| QA | `qa_assessment` | Технические проверки и ограниченная semantic assistance | Посмотреть точный файл, approve/reject/repair |
| Publication | `placement` | Подготовить package, tracking и инструкции | Подтвердить аккаунт, URL, дату и факт публикации |
| Metrics | `metric_observation` | Получить cumulative snapshot и проверить provenance | Разрешить конфликт, подтвердить ручной источник |
| Learning | `learning_memory_snapshot` | Обновить bounded priors и следующий эксперимент | Approve activation, disable, revert или quarantine memory |

Архитектурные инварианты:

1. У каждого вывода есть evidence lineage.
2. Рыночная категория отделена от compliance-категории.
3. Наблюдение, гипотеза и победитель — разные состояния.
4. Ни один stale или rejected artifact не используется молча.
5. Пересчёт не перезаписывает ручные правки.
6. Платный provider, публикация и обучение остаются отдельными gates.
7. Raw competitor prose никогда не становится системным prompt или learning
   memory.

## 4. Versioned stage graph

### 4.1. Базовая модель

Целевой граф состоит из четырёх сущностей:

- `workflow_run` — один управляемый цикл для товара и цели;
- `stage_artifact` — immutable версия результата этапа;
- `stage_edge` — явная зависимость версии от конкретных upstream-версий;
- `stage_decision` — append-only действие человека или автоматики.

Минимальный контракт `stage_artifact`:

```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "workflow_run_id": "uuid",
  "product_id": "uuid",
  "stage": "trend_signals",
  "schema_version": "trend-signals.v1",
  "version": 3,
  "branch_key": "main",
  "parent_artifact_ids": ["uuid"],
  "status": "draft",
  "payload": {},
  "evidence_ids": ["uuid"],
  "created_by_kind": "model",
  "provider": "openai_web_search",
  "model_version": "configured-server-model",
  "content_hash": "sha256",
  "created_at": "timestamp"
}
```

Допустимые состояния: `draft`, `approved`, `rejected`, `superseded`,
`quarantined`. Состояние не заменяет историю: переход фиксируется отдельным
`stage_decision` с actor, причиной, временем и предыдущим hash.

### 4.2. Операции пользователя

- `patch` — создаёт новую дочернюю версию с минимальным diff и ссылкой на
  исходную версию;
- `approve` — фиксирует версию как разрешённый вход downstream-этапа;
- `reject` — запрещает downstream-использование и требует причины;
- `fork` — в целевой архитектуре создаёт независимую ветку гипотезы. Локальный
  контур `009` намеренно ограничивает её read-only сравнением без merge/promote;
- `revert` — создаёт новый head, payload которого равен выбранной старой версии;
  история после неё не удаляется;
- `recompute` — запускает модель на выбранных upstream-версиях и создаёт новую
  версию рядом с ручной, а не поверх неё.

### 4.3. Инвалидация downstream

Patch или новая approved-версия upstream-этапа не удаляет downstream-артефакты.
Они получают вычисляемое состояние `stale_dependency`.

Пользователь видит три действия:

1. оставить существующую ветку как историческую;
2. пересчитать выбранные downstream-этапы;
3. fork новой ветки и сравнить её со старой.

Публикация, метрики и learning memory всегда сохраняют точные artifact IDs,
которые были фактически использованы. Поздняя правка исследования не меняет
происхождение уже опубликованного результата.

### 4.4. Локальный stage-control loop `009`

Текущая реализация использует четыре tenant-scoped сущности:

- `research_stage_branches` — immutable именованные ветки одного research run;
- `research_stage_head_events` — append-only команды и смены head;
- `research_stage_heads` — защищённая текущая проекция семи этапов;
- `research_stage_recompute_requests` — bounded связь root run с одним дочерним
  research run и его единственной provider-попыткой.

`research_stage_artifacts.input_dependencies` хранит точные evidence и upstream
artifact IDs, а `input_dependency_hash` входит в уникальную идентичность версии.
Одинаковый JSON на других входах не считается тем же артефактом и не может
случайно очистить stale-state.

Browser mutation обязана передать четыре exact token из только что прочитанного
snapshot: `expected_head_event_id`, `expected_artifact_id`,
`expected_content_hash` и `expected_branch_revision_hash`. Последний — SHA-256
canonical набора ровно семи упорядоченных `(stage, head_event_id, artifact_id,
dependency_hash, state)`. Сервер повторно проверяет head и весь branch под
advisory lock для каждой команды, включая `fork`, `recompute` и `cancel`.
Поэтому устаревшая вкладка получает `research_stage_head_stale` или
`research_stage_branch_revision_stale`, а не оплачивает и не изменяет уже другой
граф.

`recompute` — двухфазная операция. Первая транзакция после явного
`paid_analysis_ack` создаёт child run и durable request, но не вызывает Edge.
Browser вызывает существующий `creator-product-research` ровно один раз по
возвращённому child run ID; автоматического retry нет. После terminal child
service RPC либо применяет полный source-backed snapshot к root run, либо
фиксирует `failed/superseded`. Status read остаётся бесплатным и side-effect-free.

Активный recompute не разрешает создать новый. Явный `cancel` допустим для
`queued` до provider claim; для `processing` он становится доступен только после
`lease_expires_at`. Пока lease активен, отмена fail-closed. Cancel терминализует
сохранённый request/child без вызова Edge или provider, без автоматического
повтора и без нового списания.

Исключение из ожидания lease — уже доказанное независимое изменение root-ветки.
Такой request можно немедленно закрыть как `superseded`; активный child не
перезапускается, а его поздний результат отбрасывается без применения и нового spend.

`fork` в текущем `009` — только immutable snapshot для сравнения с main. Ветку
нельзя править, пересчитывать, утверждать или переносить обратно; merge/promote
контракт не реализован и не подразумевается интерфейсом.

SQL ограничивает сохранённый recompute input snapshot 76 800 байтами, а Edge
принимает весь проверенный recompute context не больше 98 304 байт. Применение
успешного child создаёт новую AI-версию, но не разрешает её сразу утвердить:
status возвращает `ai_revision_needs_human_snapshot` и направляет пользователя
сохранить точный human review snapshot. Только human draft с семью current heads
и совпадающими hashes может пройти approval.

Внутри recompute envelope `input_snapshot.branch_revision_hash` является
обязательным exact ключом и lowercase 64hex. Табличный constraint и claim RPC
сверяют его с `request.expected_branch_revision_hash` до передачи контекста в
Edge; Edge затем fail-closed проверяет форму и значение token, но не получает и
не выдумывает второй дублирующий request-token в своём envelope.

Это локальный контракт, а не подтверждённый rollout: в текущем окружении нет
доступного PostgreSQL/Docker runtime, поэтому реальная транзакционность,
concurrency и recovery должны быть проверены pgTAP и browser E2E в staging.

## 5. Dynamic category profiles

### 5.1. Два независимых измерения

`market_category` описывает, с чем покупатель сравнивает товар и какие рыночные
паттерны релевантны. Она динамическая и может быть новой.

`compliance_category` выбирает действующие QA, claims и disclosure rules. На
первом этапе она остаётся закрытым enum:

```text
cosmetics, baa, sports_food, food,
household, apparel, electronics, other
```

Пример: «автоматическая кормушка для кошек» может иметь
`market_category.key=pet_feeding_devices` и
`compliance_category=electronics`. Она не должна терять рыночную идентичность
только потому, что отдельного compliance enum для pet care нет.

### 5.2. Контракт профиля

```json
{
  "key": "pet_feeding_devices",
  "label": "Автоматические кормушки для домашних животных",
  "parent_key": "pet_care_devices",
  "synonyms": ["умная кормушка", "автокормушка"],
  "inclusion_rules": ["дозирует корм по времени или команде"],
  "exclusion_rules": ["обычная миска без механизма дозирования"],
  "region": "RU",
  "language": "ru",
  "compliance_category": "electronics",
  "confidence": 0.78,
  "source_ids": ["source-id"],
  "status": "human_confirmed"
}
```

Правила:

- key нормализуется детерминированно, но label может быть исправлен человеком;
- merge, alias или split категории создаёт новую versioned mapping, а не меняет
  прошлые observations;
- production learning использует category snapshot, действовавший при создании
  generation job;
- низкая уверенность не блокирует research, но блокирует перенос category prior
  без подтверждения;
- `other` допустим как compliance fallback, но не как молчаливая замена
  динамической market category.

## 6. Provider adapter roadmap

Все источники должны приводиться к единому `observation_snapshot`, сохраняя
provider, relationship, commercial-use boundary, fetched time, content hash и
source locator. Adapter не имеет права объявлять бизнес-победителя.

Минимальный интерфейс adapter:

```text
capabilities()
discover(query, scope, cursor)
fetch(locator)
normalize(provider_payload)
health()
estimate_cost(request)
```

### P0 — web и marketplace first

- расширить существующий OpenAI web-search research;
- обрабатывать публичную страницу товара, официальные страницы, доступные
  marketplace/review/editorial-источники и явно найденные похожие предложения;
- сохранять только provider-cited HTTPS URLs;
- маркировать источник, publisher, fetched/published time, trust и freshness;
- при недоступной или защищённой странице возвращать gap, а не выдуманный факт;
- разрешить пользователю добавить несколько известных competitor URLs как
  research hints, не превращая их автоматически в доверенные источники.

Это разовый research request. Автоматический polling в P0 отсутствует.

### P1 — YouTube Data API

- реализованный adapter использует только официальный YouTube Data API
  `search.list` + `videos.list` для публичных video metadata, доступных по
  условиям продукта;
- canary всегда ограничен одним результатом и двумя HTTP/quota calls; refresh
  допускает 1–25 результатов, но также ровно два вызова без автоматического
  retry. Quota учитывается по provider day в Pacific Time, есть tenant/user caps,
  короткая lease и fail-closed retention heartbeat;
- сохраняются индивидуальные observations с fetched/published time и точной
  video identity. API Data очищаются bounded retention-процедурой; UI показывает
  их в исходном search position order без derived metrics, дельт, рейтинга,
  сравнения или агрегации;
- observation может быть явно подтверждён или исключён человеком, но ни один
  такой сигнал не попадает в prompt, outcome memory или generation selection;
- owner YouTube Analytics не смешивается с public competitor discovery;
- production включение ещё не состоялось: provider catalog и global gate по
  умолчанию выключены, deployment/API key/runtime canary отсутствуют.

### P2 — licensed social data vendor

- подключить лицензированного поставщика публичных данных TikTok, Instagram и,
  при доступности, VK;
- зафиксировать commercial-use rights, разрешённые поля, retention и deletion;
- хранить ключи server-side, hard spend cap, provider health и audit receipts;
- нормализовать только разрешённые metadata и structural observations;
- исключить лица, музыку, captions, slogans и точные shot sequences из learning
  memory.

TikTok Display API и Instagram Insights для авторизованного владельца аккаунта
не должны использоваться как произвольный competitor scraper. Owner metrics и
public competitor discovery — разные adapters и разные trust boundaries.

## 7. Trend confidence, freshness и corroboration

### 7.1. Trend candidate, а не утверждение

Одна публикация или одна страница создаёт только `trend_candidate`. Статус
`emerging` или `corroborated` требует независимых наблюдений и изменения во
времени.

Контракт сигнала:

```json
{
  "id": "signal-id",
  "market_category_key": "pet_feeding_devices",
  "platform": "youtube",
  "region": "RU",
  "signal_type": "creative_structure",
  "feature": "demonstration_first",
  "direction": "rising",
  "window_start": "timestamp",
  "window_end": "timestamp",
  "first_seen_at": "timestamp",
  "last_seen_at": "timestamp",
  "observation_count": 8,
  "independent_source_count": 3,
  "confidence": 0.72,
  "freshness": "fresh",
  "supporting_observation_ids": ["uuid"],
  "contradicting_observation_ids": [],
  "status": "emerging"
}
```

### 7.2. Детерминированные ограничения v1

- один независимый источник: confidence не выше `0.35`;
- нет двух временных точек: direction не может быть `rising` или `falling`;
- `emerging`: минимум два независимых publisher/account и минимум три
  observations в окне;
- `corroborated`: минимум три независимых источника, две временные точки и
  отсутствие сильного противоречия;
- stale signal не применяется к новой гипотезе без refresh или явного override;
- contradictory signal остаётся видимым и переходит в `needs_review`, а не
  удаляется;
- views, engagement и velocity являются discovery signals, но не доказывают
  orders, revenue или causal uplift.

Независимость считается по provider + publisher/account identity. Несколько URL
одного аккаунта не являются несколькими независимыми источниками.

### 7.3. Базовые freshness windows

| Тип наблюдения | Fresh | Stale после | Комментарий |
| --- | --- | --- | --- |
| Цена/наличие marketplace | 24 часа | 72 часа | Нужен частый refresh, нельзя переносить старую цену в claim |
| Public video counters | 24 часа | 72 часа | Хранить cumulative snapshot, не суммировать повторно |
| Creative structural pattern | 7 дней | 21 день | Может жить дольше счётчика, но требует corroboration |
| Review/pain theme | 14 дней | 45 дней | Сохранять размер выборки и период |
| Seasonal signal | 30 дней | конец сезона | Всегда хранить region и calendar window |

Windows конфигурируются по adapter и категории, но их версия входит в hash
trend artifact.

## 8. Safe learning memory

Learning memory хранит не контент, а проверенные ограниченные признаки и
агрегаты.

Разрешённые признаки:

- market/compliance category snapshot;
- platform, model и generation mode;
- allowlisted `creative_angle`, `hook_pattern`, `proof_type`, `cta_style`,
  `pacing`, duration bucket;
- QA guard codes и их version;
- aggregate outcome metrics, maturity window и evidence count;
- hypothesis/artifact lineage, policy version и hash.

Запрещено помещать в активную память:

- raw captions, competitor copy, slogans и длинные quotes;
- raw prompt или reviewer prose;
- лица, голоса, музыку и точную последовательность чужих кадров;
- неподтверждённые product claims;
- URL как instruction;
- PII, access tokens и cross-tenant data.

Состояния memory entry:

- `candidate` — наблюдение существует, но activation gates не пройдены;
- `active` — допустимо для bounded recommendation;
- `deprecated` — заменено новой версией policy;
- `quarantined` — конфликт provenance, rights, attribution или schema;
- `reverted` — отключено решением человека или effectiveness gate.

Activation gates:

1. точный tenant, product и category snapshot;
2. права и QA подтверждены;
3. результат действительно опубликован;
4. метрика имеет provenance, зрелое окно и непротиворечивую cumulative semantics;
5. минимум независимых observations для сравнения;
6. остаётся control arm;
7. policy hash повторно проверен перед paid state;
8. пользователь может opt out или revert.

Приоритет памяти:

```text
точный SKU + category + platform + model
→ category prior с достаточной поддержкой
→ безопасный global control
```

Новая или sparse категория не получает winner другой категории. Competitor и
trend evidence предлагают hypotheses; winner появляется только после собственных
QA и business outcomes.

## 9. Proactive next-action UX

Каждый экран этапа должен отвечать на пять вопросов:

1. Что система уже знает?
2. На каких источниках это основано?
3. Что неизвестно, stale или противоречиво?
4. Какое действие рекомендуется сейчас и почему?
5. Что изменится, сколько это может стоить и требуется ли подтверждение?

Карточка следующего действия содержит:

- один рекомендуемый primary action;
- причину и evidence summary;
- confidence и freshness;
- ожидаемый downstream effect;
- стоимость или пометку «без provider call»;
- безопасную альтернативу;
- `patch`, `fork`, `approve`, `reject`, `recompute` или `revert`.

Примеры:

- нет точного фото: «Добавьте упаковку и этикетку; competitor search можно
  продолжить, но generation останется заблокированной»;
- category confidence низкая: показать 2–3 варианта и попросить подтверждение;
- найден только один конкурент: предложить добавить URL или начать bounded cold
  start без заявления о рынке;
- trend stale: предложить refresh с оценкой provider cost;
- источники противоречат: открыть evidence diff и остановить claim;
- hypothesis готова: предложить самый дешёвый experiment с наибольшим ожидаемым
  information gain;
- QA отклонил файл: patch generation spec и пересчитать только generation/QA,
  не повторять research;
- метрики созрели: предложить `exploit 60% / control 20% / explore 20%`, если
  activation gates пройдены.

Автоматика может бесплатно читать, нормализовать, оценивать stale-state и
предлагать план. Платный provider call, публикация, claims approval, category
override и learning activation требуют явного gate.

## 10. Phased migration

### P0 — управляемый research v2

Цель: превратить текущий одноразовый product research в корректируемый
source-backed анализ новой категории без создания social scraper.

Реализованный P0-A:

- Edge JSON schema содержит `category_analysis`, `competitor_analysis`,
  `trend_analysis`, `guidance` и строгую evidence validation;
- UI показывает эти блоки, пробелы и next actions, а ручные корректировки
  сохраняет отдельно от исходных evidence;
- используются существующие immutable sources, versioned creative drafts и
  публичный web/marketplace discovery через web search;
- исполняемые Deno fixtures проверяют валидный v2 result, duplicate/same-domain
  конкурентов, stale snapshot, publisher independence, confidence downgrade и
  missing refs; provider-free Python/Node contracts проверяют anti-copy,
  guidance и UI round-trip;
- подготовлена tenant-safe migration stage ledger с server-enforced
  preservation исходных research blocks и явным cold-start decision.

Реализованный P0-B foundation:

- dynamic market category и compliance category разделены в production DB;
- добавлены стабильные UUID category bindings и allowlisted structural trend
  IDs с exact source junctions;
- пользователь явно подтверждает создание, связывание или переклассификацию,
  а прежняя привязка остаётся в append-only истории;

Локально реализованный P0-C stage-control foundation:

- семь stages получают независимые immutable artifacts с exact input identity,
  append-only head history и tenant-scoped branch heads;
- public RPC поддерживает `patch/reject/revert/fork/recompute/cancel`, optimistic
  concurrency по exact event/artifact/content hashes и canonical hash всех семи
  branch heads, а также вычисляемую downstream-инвалидацию;
- fork остаётся read-only comparison snapshot без patch/recompute/approval и без
  merge/promote в main;
- approval и generation handoff закрыты для stale/rejected/mismatched snapshot;
- `recompute` сохраняет ручную correction как `user_input`, создаёт отдельный
  оплачиваемый child research run через существующий authorization gate и
  применяет его только при неизменившейся ветке; SQL snapshot ограничен 76 800
  байтами, полный Edge context — 98 304 байтами;
- применённый recompute остаётся AI draft и требует отдельного human review
  snapshot перед approval;
- queued recompute можно явно отменить до provider claim, processing — только
  после истечения lease; cancel не вызывает Edge/provider, retry или spend;
- отдельный bounded status envelope направляет пользователя к earliest problem
  stage и не выполняет внешних или платных действий.

P0-C остаётся default-disabled в практическом смысле: migration/Edge/UI-код не
развёрнут; свежий PostgreSQL 17/PGlite apply и focused runtime fixtures проходят,
но локальный Supabase/pgTAP и staging не проверены, provider request не выполнялся.

Следующее расширение P0:

- применить и проверить уже прошедшие PostgreSQL 17/PGlite migrations `001`–`010`
  в локальном Supabase и staging;
- пройти реальный `patch → stale → recompute → approve → generation handoff`
  round-trip и проверить recovery без повторного provider spend;
- определить отдельный проверяемый merge/promote либо new-run workflow; до этого
  fork остаётся только read-only comparison snapshot;
- добавить recorded provider-response fixtures и browser E2E с реальным
  save/approve round-trip.

### P1 — наблюдения во времени

Цель: получить честный watchlist для поддерживаемых источников.

- реализовано P1-A: product watchlist, immutable approved-v2 history,
  freshness, deterministic additions/removals/direction changes,
  contradiction marker, provider-free due proposal и полный пользовательский
  pause/resume/interval control;
- реализована P1-B control foundation: category registry с aliases и human
  confirmation, canonical trend observations, provider authorization/binding и
  passive health receipts без auto-spend;
- реализована P1-C advisory outcome foundation: exact approved lineage до зрелой
  first-party метрики, bounded cross-product comparison, immutable candidates,
  явные activate/reject/quarantine/deactivate/revert и rollback history без
  автоматического consumption;
- реализован default-disabled YouTube ingestion foundation: SQL control/retention
  plane, двухendpointный Edge adapter и ручной UI для canary/refresh/rollout;
  public API Data изолированы от generation и не используются для derived
  metrics. Deployment, API key и успешный runtime canary остаются rollout gate;
- реализован category evidence readiness foundation: versioned source ledger,
  append-only parser/human interpretation, шесть объяснимых измерений 0–100,
  retained YouTube evidence и bounded история снимков; процент не является IQ;
- реализован default-disabled opt-in scheduler для YouTube: latest-policy,
  owner/admin, terms, retention, rollout, quota и hard-budget gates, preclaim до
  Edge HTTP и отсутствие automatic retry/fallback;
- реализован exact multi-scope registry: bounded read-only discovery и явный
  выбор category/platform/model без эвристического выбора при нескольких scopes;
- реализован gated generation-selection foundation: explicit apply/control,
  повторная live-проверка evidence и immutable selection, но assignment к
  generation job заблокирован, effectiveness неизвестна и consumption не
  подключён;
- category merge/split lifecycle и bulk reclassification;
- multi-provider scheduler, cursors и first/last seen для внешних content
  entities за пределами ограниченного YouTube-контура;
- production deployment YouTube adapter, секрет и успешный внешний canary;
- повторные marketplace snapshots без суммирования cumulative values;
- trend corroboration и contradiction queue;
- hypothesis experiment allocation ledger и causal effectiveness windows;
- manager health: stale sources, quota, cost, failed refresh, reauthorization;
- безопасное подключение выбранной активной advisory memory к generation job
  после effectiveness gate и финальной revalidation.

### P2 — multi-provider learning machine

Цель: production-scale discovery и измеримое улучшение рекомендаций.

- licensed social vendor с commercial-use contract;
- multi-provider entity resolution и deduplication;
- category priors с minimum support и retained control;
- adaptive, но bounded allocation экспериментов;
- effectiveness ledger для каждой policy version;
- automatic cooldown/revert при ухудшении QA или business outcomes;
- graph UI для branch comparison и selective downstream recompute;
- cost ledger, provider canaries, incident alerts и retention controls.

## 11. Измеримые acceptance criteria

Ниже перечислены exit gates соответствующих фаз, а не заявление об их текущем
выполнении. P0-A закрывает структурированный source-backed snapshot, честный
insufficient-data state, базовый trend corroboration guard и передачу ручных
правок в versioned brief. P0-B/P1-B foundation добавляет отдельную рыночную
идентичность, canonical signal IDs, server-authorized provider attempt и
пассивные health receipts. Локальный P0-C добавляет exact versioned stage heads,
optimistic correction, stale propagation и bounded recompute child, но ещё не
доказывает Supabase/staging rollout. P1-A добавляет immutable cross-run snapshots,
freshness и provider-free proposals без auto-spend. P1-C добавляет exact outcome
lineage, bounded candidate evidence и явный versioned activation/rollback, но не
production consumption. Остальные критерии требуют runtime pgTAP, rollout и
следующих live-provider/effectiveness этапов.

### P0

1. Неизвестный ранее товар получает dynamic market category, не теряя отдельную
   compliance category.
2. Каждый competitor и trend candidate содержит provider-verified source IDs,
   fetched time, confidence и freshness.
3. Один источник никогда не отображается как подтверждённый rising trend.
4. Недостаток данных создаёт `research_gap` и безопасный next action, а не
   выдуманный вывод.
5. Patch категории или competitor interpretation создаёт новую версию; старая
   версия остаётся доступной.
6. Изменение upstream помечает downstream stale и не перезаписывает его.
7. Reject не позволяет использовать artifact в approved hypothesis.
8. Approved scenario сохраняет lineage до category, competitor/trend signals и
   точных sources.
9. Generation prompt не содержит raw competitor text, URL или неподтверждённый
   claim.
10. Deno fixture tests, browser round-trip tests и pgTAP tenant/version tests
    проходят в CI.

### P1

1. Не менее 95% успешных refresh создают idempotent snapshots без дублей.
2. Stale observation обнаруживается не позднее одного scheduler interval.
3. `rising/falling` появляется только при двух временных точках и заданной
   corroboration.
4. Cross-tenant и cross-category leakage покрыты отрицательными pgTAP tests.
5. YouTube canary ежедневно подтверждает auth/quota/normalize/persist path.
6. Для каждого active hypothesis можно пройти lineage до observations и версии
   category profile.

### P2

1. Для каждой active learning policy есть control, evidence count, maturity
   window, hash и revert decision.
2. Ни одна policy не активируется на raw competitor popularity или views-only.
3. Ухудшение agreed QA/business guard автоматически переводит policy в cooldown
   и предлагает revert.
4. A/B holdout показывает улучшение заранее выбранной метрики с доверительным
   интервалом; без такого доказательства policy остаётся экспериментальной.
5. Provider cost, freshness, quota и incident status видны owner/admin.
6. Удаление/retention у provider отражается в observations и не ломает audit
   lineage.

Сквозной demo acceptance:

```text
новая категория
→ 3 source-backed competitors или explicit insufficient-data state
→ 2 corroborated trend candidates либо gaps
→ human-approved hypothesis
→ generation с immutable lineage
→ independent QA
→ placement
→ mature metric snapshot
→ candidate memory
→ следующая bounded recommendation с control и revert
```

## 12. Non-goals

- обход login, robots, captcha, rate limits или anti-bot защиты;
- скрытый scraping TikTok, Instagram, VK или marketplace;
- использование owner OAuth API как произвольного competitor API;
- копирование чужого текста, лица, голоса, музыки, слогана или shot sequence;
- обещание вирусности, продаж или causal uplift по просмотрам;
- автономное юридическое решение или утверждение product claims;
- бесконтрольное обучение на raw prompts, reviewer comments или model prose;
- автоматический spend, публикация или learning activation без соответствующего
  human/server gate;
- перенос winner между tenant, несовместимыми категориями или неизвестными
  attribution scopes;
- замена полного просмотра файла и человеческого QA автоматической оценкой;
- объявление текущего provider-free watchlist постоянным social monitoring,
  live competitor parser или доказанным metric-velocity контуром до следующего
  live-provider/outcome среза P1/P2.

## 13. Решение для текущего вертикального среза v2

v2 должен расширять уже работающий production product-research Edge flow, а не
создавать параллельный «демо-анализатор». Он использует существующие web search,
provider citations, immutable sources, versioned draft, human approval и
generation lineage.

Результат v2 + P1-A + P1-B + P1-C foundation — управляемый snapshot категории,
конкурентов, canonical trend candidates, gaps и гипотез, долговременная история
утверждённых версий, отдельный реестр рыночных категорий и проверяемый контур
платного провайдера. Система сама считает freshness, сравнивает совместимые
версии, собирает точную цепочку зрелых first-party outcomes и предлагает bounded
candidate memory; обновление данных и каждое решение о памяти выполняются только
после отдельного подтверждения. Миграции `006`–`008` дополняют этот срез
управляемым официальным YouTube transport, exact multi-scope registry и
effectiveness-gated selection foundation. Но YouTube provider/global gates
остаются default disabled, код не развёрнут, ключ и runtime canary отсутствуют;
его API Data не питают генерацию и не образуют derived metrics. Подготовленная
outcome selection также не связана с generation job: binding закрыт,
effectiveness `unknown`, production consumption `gated_not_wired`. Поэтому live
licensed social collection, provider-driven periodic refresh, production canary
и доказанное улучшение генерации остаются следующими P1/P2 этапами.

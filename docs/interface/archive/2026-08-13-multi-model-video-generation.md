# Multi-model generation: интерфейс, authority и архив

Дата спецификации: 2026-08-13
Статус: release candidate `20260813.os4.39`; production deploy и paid smoke ещё не выполнены
Маршрут: `#/workspace/generation`

Этот документ — долговечный продуктовый контракт для расширения существующего
генератора. Он не является журналом разработки и не доказывает качество
провайдера без реального результата, AI-QA и независимого решения человека.

## Проблема пользователя

Сейчас оператор выбирает один из трёх технически связанных режимов
(`seedream5_lite`, `gen4_turbo`, `seedance2_fast`). Чтобы выбрать модель, ему
нужно заранее понимать внутренние названия, а архив не хранит достаточно
подробный неизменяемый снимок причины выбора модели.

Новый интерфейс должен помочь выбрать подходящую модель по задаче, входным
материалам, звуку, качеству, скорости и бюджету. Рекомендация ИИ всегда носит
совещательный характер:

- человек может принять рекомендацию или выбрать другую модель;
- первая рекомендация может заполнить выбор только до ручного действия;
- после ручного выбора никакая перерисовка, смена шага, route/reload,
  исследование или новая рекомендация не меняет модель автоматически;
- если выбор стал несовместимым, он остаётся видимым, запуск блокируется, а
  оператор получает причину и явные альтернативы;
- новая модель, длительность, звук или набор входов требуют нового preflight,
  новой оценки цены и нового подтверждения;
- никакой платный fallback не выполняется автоматически.

## Реализованный путь release candidate

```text
workspace form
  → recommendation
  → generation spec
  → provider preflight
  → budget reservation
  → generation job
  → provider submission
  → polling/reconciliation
  → durable output
  → QA/review
  → archive
```

| Этап | Текущий authoritative owner | Основные функции/контракты |
| --- | --- | --- |
| Форма | `web/app/app.js`; визуальная компоновка без клонирования контролов — `web/app/workspace-os-v4-generation-guided.js` | `renderGenerationSection`, `syncGenerationModeForm`, `submitGenerationBatch`; `createShell`, `organizeOriginalNodes`, `panelValidity` |
| Рекомендация | `web/app/generation-model-recommendation.js`; визуальный owner — `web/app/workspace-os-v4-generation-guided.js` | deterministic capability filter/ranking, explicit Apply, immutable manual lock; совет не даёт права на запуск |
| Generation spec | `web/app/generation-spec.js`, `web/app/app.js`, `202608130002_generation_multimodel_authority.sql` | exact scope v2: project/media/provider/model/input/duration/ratio/resolution/audio; old3 compatibility остаётся на зрелом пути |
| Provider preflight | `web/app/app.js`, `web/app/supabase-api.js`, `generation-provider-readiness.js`, `creator-generate/index.ts` | для new4: сначала бесплатная подготовка spec + одноразовая v4 receipt, затем отдельное подтверждение человека; client cost не authority |
| Бюджет и резерв | PostgreSQL `creator_start_real_generation` и service-role claim | Edge вызывает start RPC; затем `claimSystemJob` атомарно проверяет reservation, kill switch и лимиты непосредственно перед provider POST |
| Job | PostgreSQL generation batches/jobs; Edge parsing | `readStartJob`, `readStatusJob`, `safeJob`; idempotency и project/org scope уже обязательны |
| Provider submission | `supabase/functions/creator-generate/index.ts`; thin adapters — `_shared/generation-provider-adapters.js` | один `POST` после server claim; ambiguous create переводится только в reconciliation, без blind paid retry |
| Poll/reconcile | тот же Edge owner и background worker | `handleStatus`, `handleReconciliation`, exact provider task ID; неопределённый исход не повторяет платный POST |
| Durable output | тот же Edge owner + private Supabase Storage | provider URL проверяется, файл скачивается, валидируется, хешируется и загружается в `contentengine-private`; временный provider URL не становится артефактом |
| QA/review | `202608130004_generation_multimodel_acceptance_v4.sql` + существующие QA/evidence/human-decision owners | 10 exact provider:model; accepted только после real output, SHA, AI-QA и независимого watched human decision; 90-day freshness |
| Архив | `202608130003_generation_multimodel_archive_v1.sql`, `web/app/app.js`, `web/app/supabase-api.js` | immutable snapshot, provider/model/content/source/quality filters before keyset limit; legacy остаётся честным `null` |

### Единственные владельцы, которые нельзя размножать

- server catalog — `_shared/generation-model-catalog.js` и его безопасная
  projection; браузер не создаёт второй список моделей;
- recommendation reducer только советует, а существующая форма остаётся
  единственным владельцем выбора и paid confirmation;
- `creator-generate` остаётся единственным Edge orchestrator, provider adapters
  только строят/читают provider-specific envelopes;
- `creator_start_real_generation` и server receipt/spec/live claim остаются
  authority запуска и стоимости;
- `creator_generation_archive` остаётся единственным архивным reader;
- `creator_generation_model_acceptance` остаётся единственным quality reader.

Release candidate следует этому состоянию: один версионированный server-side
catalog, одна safe projection, один deterministic recommendation reducer, один
Edge orchestrator и тонкие provider/model adapters. Существующая форма остаётся
единственным владельцем native controls и paid confirmation.

## Структура первого шага «Режим и бюджет»

```text
1. Что создаём?
   [Видео] [Фото товара]

2. Рекомендация системы
   модель · короткая причина · компромисс · оценка цены

3. Выбор модели
   Экономно / Сбалансировано / Лучшее качество / Экспериментально

4. Кампания и бюджет
   существующие native controls, readiness и лимиты

5. Итог выбора
   provider · model · input · duration · ratio/resolution · audio · cost
```

Визуальные карточки используют нативную radio-группу существующей формы. В
DOM не появляется второй select/radio source of truth. Технический provider ID
вторичен; сначала пользователь видит задачу, ограничение, звук, входы и цену.

## Состояния карточки модели

Каждая карточка обязана показывать:

- публичное имя и provider вторичным текстом;
- `Рекомендуем`, если модель — текущий top candidate;
- качество, скорость и стоимость;
- одну понятную строку «лучше всего для» и одну строку ограничения;
- обязательные входы, количество референсов, звук/речь, длительность и формат;
- server-estimated price;
- provider readiness;
- отдельный human-evidence status: `Проверено`, `Нужна перепроверка`,
  `Экспериментально`, `Недоступно`;
- точную причину disabled/blocked state.

Provider availability, успешная отправка и непустой файл не переводят модель в
`Проверено`. Новая модель начинает без доказательства и проходит существующую
цепочку реальный output → AI-QA → независимое human acceptance.

## Поведение рекомендации и manual lock

Рекомендатор сначала выполняет жёсткую фильтрацию capabilities, затем
детерминированное ранжирование. Его результат — совет, не разрешение на оплату.

Состояние формы хранит отдельно:

```json
{
  "recommended_provider": "runway",
  "recommended_model": "veo3.1_fast",
  "selected_provider": "runway",
  "selected_model": "gen4_turbo",
  "selection_source": "manual_choice",
  "manual_lock": true,
  "selection_valid": false,
  "blocking_reason_codes": ["image_required"]
}
```

`manual_lock=true` может снять только явное действие человека: выбрать другую
карточку или нажать «Принять рекомендацию». Новая рекомендация обновляет
recommended-снимок и альтернативы, но не selected-снимок.

Ни один recommendation state не даёт права на paid launch. Право появляется
только после текущего generation spec, exact provider readiness receipt,
server-side cost confirmation, budget reservation и явного подтверждения
человека для того же immutable scope.

## «Очередь и архив»

Существующая секция и keyset pagination сохраняются. Каждая новая запись
должна читать server-projected immutable snapshot и показывать:

- content kind, provider и публичное имя модели;
- raw model ID только в раскрываемых технических деталях;
- lifecycle/quality state;
- duration, ratio/resolution, audio и input mode;
- reference count;
- selection source: system/research/performance/manual/alternative-after-block;
- короткую сохранённую причину;
- estimated и actual cost раздельно;
- catalog/pricing version в технических деталях;
- существующие status/progress, QA/output и soft archive actions.

Добавляются server-side фильтры provider/model/content kind/selection source и
необязательный quality status. Period/status/query и bounded keyset pagination
не меняются.

Старые строки без факта выбора честно показывают:

> Модель не зафиксирована · старый запуск

`Повторить настройки` создаёт только новый черновик, сбрасывает paid
confirmation/preflight, пересчитывает цену и никогда не отправляет job.

## Immutable launch snapshot

Минимальная серверная запись:

```json
{
  "provider": "runway",
  "model": "veo3.1_fast",
  "model_public_label": "Veo 3.1 Fast",
  "selection_source": "system_recommendation",
  "recommendation_reason_codes": [],
  "recommendation_warning_codes": [],
  "recommendation_catalog_version": "",
  "pricing_version": "",
  "estimated_cost_minor": 0,
  "requested_duration_seconds": 0,
  "requested_ratio": "",
  "requested_resolution": "",
  "requested_audio": true,
  "input_mode": "image",
  "reference_count": 0,
  "acceptance_status_at_launch": "",
  "provider_readiness_receipt_id": ""
}
```

Exact preflight/confirmation scope включает минимум organization, provider,
model, duration, ratio/resolution, audio, input mode и pricing version. Client
cost никогда не является authority. API keys, auth headers, expiring provider
URLs, private media URLs и oversized raw provider payload не сохраняются.

## Accessibility и responsive contract

- карточки имеют radio semantics, одно имя группы и видимый focus;
- стрелки перемещают выбор в группе, Tab проходит между решениями, а не каждой
  декоративной частью;
- reason/compromise доступны без hover;
- ошибки связаны с выбранной карточкой через `aria-describedby`;
- price/status updates используют сдержанный `aria-live`, без полного rebuild;
- reduced motion отключает декоративные transitions;
- ниже 820 px карточки складываются в одну колонку без page overflow;
- paid safeguards не прячутся в декоративной панели.

## Скриншоты

Browser-QA выполнен на реальном guided-модуле и единственной существующей
`#mock-batch-form`, а не на отдельном mock-компоненте. Артефакты release
candidate:

- `generation-overview-1280.png` и `generation-model-picker-1280.png`;
- `generation-overview-390.png` и `generation-model-picker-390.png`;
- `generation-overview-320.png` и `generation-model-picker-320.png`.

Они сохранены вне repository в Codex visualizations каталоге задачи. На всех
трёх ширинах подтверждены одна форма, не более четырёх карточек во вкладке
«Для вас», полный каталог во «Все модели», отсутствие page/descendant overflow,
минимальный читаемый шрифт 12 px и touch targets не меньше 44 px.

Это доказательство локального release candidate, а не production deployment.
Production screenshots и signed-in employee proof добавляются после deploy.

## Acceptance status

| Проверка | Статус на 2026-08-13 |
| --- | --- |
| Current-state dependency map | Зафиксирован выше |
| Один canonical model catalog | Реализован и статически проверен |
| Pure deterministic recommendation + manual lock | Реализован; явное Apply, human edits authoritative |
| First-step UI без второго form owner | Реализован на существующей `#mock-batch-form`; browser-green 1280/390/320 |
| Immutable provider/model snapshot | Реализован; v4 receipt/spec/single-use job binding |
| Runway expanded adapters | Old3 + четыре new4 связаны в коде; new4 только baseline context |
| Archive metadata/filters | Реализованы в `130003`; legacy без домысла |
| Model acceptance | Реализован в `130004`; exact evidence/pending/freshness для 10 identities |
| Direct Google Veo Lite flag | Adapter существует, launch остаётся server-disabled |
| Full regression | Focused/broad слои green; final immutable whole-tree run — release gate |
| Controlled paid smoke | Не выполнялся; требуется отдельное разрешение |
| Human acceptance | Не выполнялось |

## Известные ограничения и отложенный scope

- `runway:veo3.1` и `runway:seedance2` видимы для сравнения, но paid launch
  закрыт server policy.
- Прямой `google:veo-3.1-lite-generate-preview` имеет catalog/adapter code,
  однако SQL LRO authority и production secret/deploy proof ещё не завершены;
  поэтому карточка видима только при org flag и всегда launch-blocked.
- Kling, Luma, Wan/LTX и другие провайдеры не входят в этот контракт.
- Четыре new4 Runway модели (`gen4.5`, `seedance2_mini`, `veo3.1_fast`,
  `gemini_omni_flash`) допускают только baseline context. Research,
  performance-learning, repair/outcome, AI-bound и video-reference contexts
  fail closed, пока зрелая lineage authority не generalized.
- Миграции `130002`–`130004` разобраны `pglast`, но локальный PostgreSQL/
  Supabase/Docker runtime недоступен; runtime pgTAP обязан пройти в CI/target DB.
- Ни одна новая модель не называется production-accepted до controlled paid
  output, durable storage, AI-QA и независимого human decision.

## Нормативные источники на дату записи

- Runway: https://docs.dev.runwayml.com/guides/models/
- Runway pricing: https://docs.dev.runwayml.com/guides/pricing/
- Runway input/capability rules: https://docs.dev.runwayml.com/assets/inputs/
- Runway changelog: https://docs.dev.runwayml.com/api-details/api_changelog/
- Gemini video: https://ai.google.dev/gemini-api/docs/video
- Google Veo Lite: https://ai.google.dev/gemini-api/docs/models/veo-3.1-lite-generate-preview
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing

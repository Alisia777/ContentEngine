# Аудит перед внедрением: забор видео · паспорт ролика · папка «Гипотезы» (26.08.2026)

Анализ ТЗ трёх контуров против фактического состояния репозитория и прод-базы.
Реализация не начиналась: документ — выводы на согласование владельцу.

## 1. Главный вывод

ТЗ ложится на существующий фундамент лучше, чем предполагает его текст.
Целевая архитектура уже описана в `docs/LEARNING_CONTENT_MACHINE_V1.md` §3
(versioned artifacts, immutable входы, человеческий контроль, этап Hypothesis
с артефактом `content_hypothesis`) — новое ТЗ фактически реализует этапы
Hypothesis + read-модель паспорта + видео-ingest. Из трёх контуров один
(забор видео) наполовину построен, второй (паспорт) на 70% покрыт данными и
нуждается в корне и read-RPC, третий (гипотезы) строится с нуля по готовым
паттернам версий/решений.

## 2. Контур №1 «Забор видео» — расширение, не стройка

Уже есть (прод, работает: 42 привязанных MP4, 2 источника ждут медиа):

- Регистрация YouTube-URL: `research_exact_youtube_sources` — canonical URL
  (`https://youtube.com/watch?v=<11>`), `video_id`, `source_hash` (глобально
  уникален), идемпотентность, append-only, `unique(org, project, video_id)`.
  RPC `contentengine_register_exact_youtube_source`.
- Привязка MP4 к источнику: `research_exact_youtube_media_attachments` и
  `generation_direct_mp4_attachments` — sha256-снапшоты, `rights_confirmed`,
  `media_matches_registered_source` («это тот же ролик»), guard-триггер
  пересчитывает хеш и переджойнивает медиа при insert.
- Хэндофф URL→MP4 в вебе: `exact-youtube-media-handoff.js` (sessionStorage,
  TTL 4 ч, привязка org/user/project/source), `exact-youtube-research-capture.js`
  (sha256 в браузере, **5 evidence-кадров уже делаются на клиенте**).
- Загрузка в «Материалы»: `#media-upload-form`, `media-upload-queue.js`
  (whitelist MIME, батч 20, конкурентность 3), `media_objects` c sha256,
  `artifact_class`, `lifecycle_stage`.
- Выбор существующего медиа: `generation-strategy-source-picker.js`.

Зазоры:

- Три контура не сведены в одну точку — нет кнопки «Забрать видео» и единого
  окна с тремя способами (URL / MP4 / существующее).
- Статус источника физически заперт: `check (status='awaiting_media')`;
  жизненный цикл проецируется RPC, в базе не материализован.
- Canonical URL — только форма watch; `youtu.be`, `/shorts/`, `m.youtube.com`
  не нормализуются. Других платформ нет (ТЗ это допускает для v1).
- Нет метаданных источника (title/author/thumbnail/duration/published_at).
- Дедуп по sha256 на загрузке в «Материалы» отсутствует (только
  `name:size:lastModified` внутри одного выбора).
- `generation_direct_mp4_attachments` сделан `inherits(...)` — FK на родителя
  не видит потомка; единая ссылка «любой источник» через FK невозможна.
- Clean master (crop/trim записи экрана) — нет; тяжёлая обработка запрещена
  в браузере и в edge (боевой урок: Memory limit exceeded при приёмке MP4).

Решение на согласование (рекомендация — вариант A):

- **A. Проекция + тонкие надстройки.** Единый список источников — read-RPC
  поверх трёх существующих сущностей (youtube sources + mp4 attachments +
  media_objects kind=source_video); новых хранилищ v1 почти нет: одна
  надстроечная append-only таблица метаданных/назначения источника и связка
  clean-master (`derived_from`). Существующие append-only таблицы не трогаем.
- B. Полноценный новый реестр `content_video_sources` с собственными
  статусами — чище концептуально, но дублирует живой контур и противоречит
  правилу «не строить второй контур».

Отдельный вопрос владельцу: **где выполнять clean master** (ffmpeg). Кандидат —
существующий воркер-контур (`generation_strategy_worker_leases/requests`,
`docs/BACKGROUND_WORKER_OPERATIONS.md`), provider-free очередь. Если воркер-хост
не развёрнут постоянно, v1 может ограничиться ручной подготовкой (как сегодня:
чистые исходники режем локально) + кнопкой «приложить подготовленный файл»,
а crop-редактор перенести в M1.5.

## 3. Контур №2 «Паспорт ролика» — корень и read-RPC поверх готовых снапшотов

Уже есть:

- Снапшоты запуска: `generation_job_selection_snapshots` (spec_version,
  spec_hash, provider, model, pricing_version, estimated_cost, snapshot_hash),
  `generation_job_strategy_snapshots` (strategy_id, product_id, hash),
  `generation_spec_strategy_assets` (роль, ordinal, media_sha256_snapshot,
  rights_confirmed_snapshot), `generation_job_video_reference_bindings`.
- Версии ТЗ: `generation_spec_versions` (+head/approval events) и
  `creative_brief_drafts` (version, status, content_hash, approved_by/at,
  source_ids, task_blueprint) — раздел 4.7/5.12 ТЗ фактически покрыт.
- Таймлайн: `generation_strategy_status_events` (event_name,
  transition_ordinal, event_hash, occurred_at).
- Деньги: `generation_spend_ledger` (единственный, трогать нельзя).
- Публикации: `placements` (product_id, generation_job_id, platform,
  tracking_url, final_url, managed_account_id, project_id).
- Метрики: `metric_snapshots` (views/clicks/orders/revenue_minor, observed_at,
  source, is_correction, идемпотентность). **В проде 0 строк** — контур ручной
  (CSV/ручные снимки), автосбора нет; E2E — на фикстурах, как ТЗ и требует.
- UI-прото-паспорт: `generationBatchDetails()` + lineage-разметка видео-
  референса в архиве генераций; deep-link на job уже есть.
- Эталон сквозного lineage: `research_outcome_lineage_snapshots` (40 колонок,
  окно зрелости 72 ч захардкожено) — но пост-фактум и только для старого
  brief-пути; для `viral_*` стратегий не заполняется.

Зазоры:

- Нет корня-манифеста: паспорт сегодня = join шести таблиц без единого
  `manifest_hash`. Новая append-only `generation_provenance_manifests`
  (референсы + снапшоты, canonical hash, идемпотентный replay, конфликт
  ключа с другим payload — отказ) создаётся в момент bind существующего
  контура; сами снапшоты не дублируются.
- Нет `creator_content_result_passport` — единого read-RPC (ближайший —
  `creator_generation_archive`). Строим read-only, fail-closed, bounded.
- Нет окна паспорта; точка входа — кнопка в `generationActionsMarkup()`
  (покрывает все места архива) + карточки готовых роликов в «Материалах».
- Окно зрелости 72 ч не существует как правило метрик вне research-lineage;
  в паспорте вычисляется от `published_at` vs `observed_at` (предварительная/
  зрелая), без новой таблицы.
- Legacy: 61 наряд по 16 товарам без гипотез — паспорт обязан честно
  показывать «Гипотеза не была указана. Legacy-результат» (ТЗ 4.6).

## 4. Контур №3 «Гипотезы» — новостройка по готовым паттернам

- Таблиц гипотез нет. Модель: `content_hypotheses` (identity) +
  `content_hypothesis_versions` (append-only, statement по шаблону
  «Если X, то метрика Y, потому что Z», product/platform/metric/baseline/
  target snapshot, canonical hash, approval) + typed bindings
  (`hypothesis_source/research/media/brief/generation_bindings` — с точными
  FK, без полиморфизма) + `content_hypothesis_decisions` (append-only,
  только человек; никакой RPC не ставит confirmed автоматически).
- Паттерны копируются 1-в-1 из `research_stage_artifacts/heads/decisions`:
  `json_hash` + самопроверяющийся CHECK, `reject_*_mutation()` триггеры,
  составные FK с organization_id, optimistic `expected_parent_hash`.
- Legacy `DemandHypothesisRecord` (Python) — машинный креативный бриф без
  метрик/версий/решений; используем только как источник идей и семантику,
  как ТЗ и предписывает.
- Dock-приложение: route `/workspace/hypotheses` укладывается в
  `WORKSPACE_PATH_PATTERN`; правки — `workspace-os-v4.js` (ROUTES/DOCK_APPS/
  порядок), `workspace-dock-contract.js` (каталог + LEGACY_DEFAULT_ORDERS),
  `workspace-command-registry.js` (tabs), `catalog.js`, renderer в `app.js`,
  `workspace-os-v4-loader.js` (ROUTE_ASSETS), символ в SVG-спрайте.
  Монтаж — `registerAdapter` ядра (без собственного MutationObserver).
  Тесты-стражи дока/окон обновляются синхронно (список известен).
- Папка в «Материалах»: словарь `workspace_folders.system_role` заперт CHECK —
  системная папка «Гипотезы» потребует миграции словаря; для v1 достаточно
  приложения в Dock (вкладки Обзор…История), без системной папки Finder.

## 5. Красные линии (подтверждены AGENTS.md и аудитом)

- Единственный платный вход `creator-generate`; гипотезы только готовят ТЗ
  и передают в существующий контур. Никаких вторых леджеров/метрик.
- Реальный провайдер в рамках всего ТЗ не запускается (mock/fixtures).
- Append-only не редактируется; новые сущности — новыми миграциями,
  применение в прод — MCP apply_migration (CI Actions не включать).
- Тесты не ослабляются; доки-стражи дока/окон правятся вместе с фичей.
- Идемпотентный mount живых окон; запись в DOM — только по отпечатку.

## 6. Предлагаемые этапы (соответствуют M1–M4 ТЗ)

- **M1. Забор видео**: кнопка «Забрать видео» в «Материалах» + единое окно
  (URL / MP4 / существующее), нормализация youtu.be//shorts/, метаданные
  источника (надстройка), sha256-дедуп при загрузке, карточка источника со
  статусом и «где использован» (read-RPC проекция), evidence-кадры по
  существующему клиентскому пути. Clean master — по решению владельца
  (воркер или ручная подготовка v1).
- **M2. Провенанс и паспорт**: `generation_provenance_manifests` (append-only,
  на bind), `creator_content_result_passport` (read-only), окно «Паспорт
  ролика» с вкладками, формулы метрик с числителями/знаменателями, timeline
  из status_events, legacy-ветка для старых 61 наряда.
- **M3. Гипотезы**: таблицы identity/versions/bindings/decisions, Dock-
  приложение, вкладки, сравнение вариантов, ручной вывод.
- **M4. Сквозной mock-E2E**: H-001 «Товар в первые две секунды», fixture
  placements + fixture metric snapshots, полный путь до решения.

Каждый этап — свой набор pgTAP/JS/браузерных контрактов из раздела 8 ТЗ.

## 7. Вопросы владельцу до старта

1. Вариант A (проекция + надстройки) или B (новый реестр источников)?
   Рекомендация — A.
2. Clean master в M1: разворачиваем provider-free воркер (ffmpeg вне браузера
   и edge) или v1 обходится ручной подготовкой + «приложить готовый файл»?
3. Порядок этапов подтверждается как M1→M2→M3→M4? (альтернатива: начать с
   M2-паспорта, т.к. он даёт видимую ценность на уже существующих 61 наряде).
4. «Гипотезы» в Dock — removable-приложение (тесты дока обновляем синхронно) —
   ок?

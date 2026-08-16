# Аудит систем портала «Контент ИИ Завод» — 16.08.2026 (вечер)

Продолжение AUDIT_CONTENT_FACTORY_2026-08-16.md: после починки маршрута «Копия» той же глубиной проверены остальные системы портала. Метод: трассировка каждой кнопки до серверного контракта (фронт → supabase-api → Edge/RPC → облачная база «Sergey Project», только чтение) + верификация каждой серьёзной находки независимым проверяющим. Все 7 вынесенных на верификацию находок подтверждены.

## Резюме

| Система | Состояние | Блокеры |
|---|---|---|
| Сверка контрактов фронт↔облако | частично | миграция 202608160004 не применена → 8 RPC падают 25006 |
| Очередь стратегий и архив | частично | сверка недоступна; архив не отдаёт платный MP4 — **исправлено в этой ветке** |
| Ревью контента | частично | AI-проверка видео зависла в проде (нет категории товара) |
| ИИ-центр | частично | весь legacy-ввод знаний выключен намертво; обучение не влияет на промпты |
| Рекомендации | частично | happy path работает; залипания после конфликтов |
| Здоровье/бюджеты | частично | клики по действиям уведомлений падают (25006, чинится деплоем 160004) |
| Обучение сотрудников | **сломана** | практический проект исчез из bootstrap → экзамен и доступ навсегда закрыты |

**Главный вывод:** деньги и happy-path генерации в порядке, но почти каждый контур восстановления/доставки — тупик. Два системных корня: (1) деплой облака остановился между 202608160003 и 202608160004 — половина фикса в проде, половина нет; (2) фронт и сервер развивались без взаимной трассировки — сервер умеет (strategy_reconcile, практические проекты, teach-очередь), а фронт не может дотянуться, или наоборот.

## Что уже исправлено в этой ветке (17.08, локально, гейт dev-test)

1. Архив: для strategy-джобов «Проверить/Показать/Скачать» работают через strategy_status + подписанные storage-URL (раньше — всегда 503).
2. Поллинг: строки queued/starting больше не замирают навсегда на «Запускается».
3. Сверка: strategy_reconcile доступен из формы сверки архива; после решения очередь разблокируется.
4. Повтор старта: сетевой сбой strategy_start больше не оставляет строку в limbo — повтор с тем же idempotency key (сервер реплеит claim, второго списания нет).

Деплой ветки также закрывает 25006-семейство (миграция 202608160004 уедет штатным CI).

## Осталось починить (по приоритету)

1. **Обучение сотрудников** — вернуть слой practical_project в live bootstrap (или отключить гейт экзамена): сейчас новый сотрудник не может получить доступ к workspace вообще.
2. **Ревью: категория товара** — AI-проверка сгенерённого видео требует подтверждённую категорию, которую негде подтвердить из этого флоу; retry-кнопка крутится вечно (живой затык в проде).
3. **ИИ-центр** — либо включить путь ввода знаний (legacyReadOnly захардкожен), либо честно убрать мёртвые вкладки; обучение сейчас не влияет ни на один промпт (0 из 337 кейсов матчится advisory-политикой).
4. **Рекомендации** — retry после неудачной гидрации черновика; разморозка sync после конфликта ревизий.
5. Минорка по списку ниже (мёртвые кнопки, несогласованные сообщения, чистка).

---

## Сверка контрактов фронт ↔ облако — работает частично

Every RPC name the frontend calls exists in the cloud (129 distinct names: 109 in the frozen map at web/app/supabase-api.js:10-139, plus module-local contentengine_* names and 5 Trash calls aliased creator_*->workspace_* by workspace-os-v4-trash-rpc-alias.js, which the loader provably installs first). All 10 frontend-invoked Edge functions are deployed and ACTIVE, both cron jobs are active, and all 11 creator-generate actions the browser sends are handled by the Edge function. The system is nonetheless only partially functional for an employee today: the cloud database stops at migration 202608160003 while the repo's 202608160004 fix is unapplied, leaving 8 authenticated read RPCs declared STABLE while their shared auth guard unconditionally writes -- under PostgREST's read-only transaction rule for STABLE functions these calls fail with SQLSTATE 25006, breaking Trash browsing, project media/members/placement panels, notification action validation, strategy repeat/asset pickers, and video-reference lineage. No live-traffic evidence was obtainable because the only REST traffic in the last 24h is the background worker's system_* calls (zero browser RPC calls).

**[БЛОКЕР] Migration 202608160004 not applied: 8 authenticated read RPCs are STABLE in cloud but write via the auth guard, so PostgREST runs them in READ ONLY transactions and they fail with SQLSTATE 25006**

- Влияние: An employee opening Desktop v4 Trash, a project's media/members/placement panels, clicking a notification action, using the strategy Repeat/asset-candidate pickers, or viewing video-reference lineage gets a 500 (25006 cannot execute INSERT in a read-only transaction) with no retry path. No live 25006s appear in the 24h log window, but the only REST traffic in that window is worker system_* calls -- zero browser RPCs -- so the breakage is latent, waiting for the first employee session.
- Как чинить: Apply supabase/migrations/202608160004_writable_authenticated_read_rpcs.sql to the cloud project (it ALTERs the 8 functions to VOLATILE and issues notify pgrst,'reload schema'). Deployment is mid-flight: 202608160001-3 landed but the companion fix did not.
- Код: E:/ContentEngine-local-workbench-v1/supabase/migrations/202608160004_writable_authenticated_read_rpcs.sql:1-70; Cloud query: contentengine_deploy.schema_migrations top = 202608160003 -- 202608160004 and 202608160005; Cloud query pg_proc: provolatile='s' for all 8: creator_project_media, creator_project_members, creator_project_placement, creator_validate_notification_action, workspace_trash_browser, contentengine_generation_video_reference_lineage, creator_generation_strategy_repeat_data, creator_generation_strategy_asset_candidates

**[минорный] Legacy AI-research-receipt decision path still shipped in the browser while the cloud RPC is service_role-only and the capability is hard-coded false -- permanently disabled UI with no enable path**

- Влияние: Employees see a research-receipt inbox section whose decision buttons are always disabled with a hint suggesting a permission they can never obtain -- the replacement flow is the project-scoped contentengine_decide_ai_research_training queue (web/app/workspace-ai-research-training.js:11-12, both RPCs present and executable in cloud). If the capability flag were ever re-enabled server-side without re-granting, every click would 403.
- Как чинить: Remove decideAiResearchReceipt from the browser RPC map and drop the legacy inbox decision markup from ai-learning-control-room.js, or stop rendering the section when the capability is force-false.
- Код: web/app/supabase-api.js:33; web/app/app.js:19302-19371; web/app/ai-learning-control-room.js:884-898 renders per-receipt approve/reject buttons disabled by capabilities.canDecideResearchInbox with a capability hint

**[минорный] creator-generate handles action 'strategy_reconcile' that nothing sends -- strategy jobs have no manual reconciliation path from the UI, unlike legacy jobs**

- Влияние: If a strategy-mode paid job lands in an incident state that the worker watchdog cannot self-heal, an employee has no UI to attach a provider task id or confirm no-submission the way the legacy 'reconcile' flow allows -- the server contract for it exists but is unreachable dead code.
- Как чинить: Either wire a strategy incident reconciliation UI to the existing strategy_reconcile handler or delete the handler to keep the contract honest.
- Код: E:/ContentEngine-local-workbench-v1/supabase/functions/creator-generate/index.ts:811 and :2335; Grep of web/app: no occurrence of strategy_reconcile; the frontend's allowed Edge actions are model_catalog/preflight/start/status/reconcile; E:/ContentEngine-local-workbench-v1/supabase/functions/creator-background-worker/index.ts:1244,1278,1288 -- the worker reconciles via reconcileStaleStartingJobs and system_reconcile_background_leases RPCs, never via the strategy_reconcile Edge action

**[минорный] Repo migration 202608160005 (local mock product photo range) also unapplied in cloud -- low impact, worker/local-mock only**

- Влияние: None for cloud employees (local-mock path is env-gated off in production); matters only for parity if the mock env flags are ever enabled on the cloud function.
- Как чинить: Apply together with 202608160004 to keep the deploy ledger contiguous.
- Код: E:/ContentEngine-local-workbench-v1/supabase/migrations/202608160005_local_mock_product_photo_range_v1.sql:16; Cloud schema_migrations top = 202608160003

**[минорный] Cloud/worker status report (verification results, not a defect): both cron jobs active; all frontend-invoked Edge functions deployed; every frontend RPC name resolves in cloud**

- Влияние: Baseline inventory for the other portal-system audits: name-level contract is sound; the live risks are grant- and volatility-level (see blocker).
- Как чинить: None required; use as the contract baseline.
- Код: Cloud cron.job: contentengine-background-worker-v1 active=true, contentengine-youtube-retention-v1 active=true; 24h edge_logs show ~500 worker cycles of system_* RPCs all 200 except 2x500 on /rest/v1/rpc/system_begin_background_worker with no matching postgres error trace; Cloud edge functions ACTIVE: creator-generate v616, creator-product-research, creator-research-ingestion, creator-ai-case-import, creator-content-review, creator-access, creator-recovery, creator-set-password, creator-invite, creator-click; Name diff clean: all 109 RPC-map names


## Очередь стратегий, статусы и архив — работает частично

The exact-ten strategy queue's happy path is genuinely wired end-to-end (probe → bind → preflight → human confirm → sequential paid starts → status polling → archive listing), the pure queue/runtime/view modules are rigorously tested, and the server side (claims, dispatch results, worker recovery, strategy_reconcile RPC) is solid. But every recovery and delivery seam the FIRST PAID RUN depends on is a dead end: an ambiguous Runway dispatch freezes the queue forever because the frontend cannot call strategy_reconcile and the visible reconcile form dies on a model-validation wall; the finished MP4 cannot be previewed or downloaded from the archive because all result buttons route through the legacy status action that rejects strategy recipe models; a single dropped start response strands the row in start_once with no retry, and the post-F5 restart collides with a raw 23505 disguised as 'temporarily unavailable'. Cloud state confirms zero strategy claims/dispatches to date, so these are unexercised pre-launch traps rather than observed incidents.

**[БЛОКЕР] Strategy reconciliation is unreachable from the frontend — ambiguous paid dispatch permanently freezes the queue (audit bug 10 still true)**

- Влияние: If the very first paid Runway POST times out or returns an unclassifiable response, the dispatch is recorded 'ambiguous', the queue shows 'Нужна ручная сверка Runway' and blocks all further paid starts — and no employee, admin, or owner has any working control to resolve it. The paid job and the remaining 9 confirmed rows are stranded forever.
- Как чинить: Add strategy_reconcile to GENERATION_STRATEGY_EDGE_ACTIONS with request/response contracts, and render the reconciliation form for strategy rows using incident_id (already delivered in strategy_status reconciliation block, runtime.js:294-299) and dispatch.result_id (runtime.js:286-293).
- Код: web/app/supabase-api.js:285-292; supabase/functions/creator-generate/index.ts:2335; web/app/generation-strategy-queue.js:671-684

**[БЛОКЕР] Archive result actions (Показать видео / Скачать MP4 / Проверить сейчас) always fail for strategy jobs — the paid MP4 cannot be downloaded from the archive**

- Влияние: After the first paid strategy video succeeds, every advertised result button in the archive returns 'Сервис платной генерации временно недоступен' (supabase-api.js:8662). The employee cannot preview or download the MP4 they just paid for; the only possible route is the separate content-review portal, which the archive card never mentions.
- Как чинить: Either route check-real-generation for strategy jobs through strategy_status + a strategy-aware signed-output endpoint, or teach readGenerationSku/readStatusJob to accept strategy recipe jobs and sign their output the same way.
- Код: web/app/app.js:15237-15255; web/app/app.js:22692-22712; supabase/functions/creator-generate/index.ts:6669-6683

**[СЕРЬЁЗНЫЙ] Claim-then-fail limbo: a network/5xx failure of strategy_start strands the row in start_once with no retry, and the created job id is discarded (audit bug 12 still true client-side)**

- Влияние: One dropped response during the 10-video paid run freezes the whole queue with a toast that promises 'резерв сохранён' but offers no action. The job may still be dispatched and billed server-side (worker continues it), while the UI can neither track it nor start the remaining rows. Recovery requires F5 + redoing the whole flow, which then collides with the next finding.
- Как чинить: On start failure keep the reservation and offer an explicit 'Повторить этот старт' action that re-sends the identical request (same idempotency key — server replays safely); parse generation_job_id out of failed start responses so the row can transition to status/polling.
- Код: web/app/app.js:28482-28528; The server DOES create the job before dispatch and supports exact replay of the same idempotency key; When the edge fails after claiming, it returns {ok:false, code:'generation_dispatch_state_unavailable', generation_job_id}

**[СЕРЬЁЗНЫЙ] Post-refresh restart of an already-claimed binding raises raw 23505 surfaced as 'generation_unavailable — повторите позже' (audit bug 14 not fixed)**

- Влияние: The natural recovery from finding 3 (refresh and redo the flow) dead-ends: for every source whose start already claimed a job, the retry loop fails on a fake 'temporarily unavailable' error, the sequential loop aborts at the first such row, and the remaining unstarted rows can never be launched through the UI. The employee retries a request that can never succeed and cannot tell that a paid job already exists.
- Как чинить: In system_claim_generation_strategy_start, also match existing claims by spec_strategy_binding_id and replay them (or raise a typed generation_strategy_start_binding_already_claimed error the edge can map to 409 with the existing generation_job_id).
- Код: supabase/migrations/202608130007_generation_strategy_execution_v1.sql:331; Same migration :3615-3621; supabase/functions/creator-generate/index.ts:4672-4689

**[СЕРЬЁЗНЫЙ] Queue polling permanently stops for jobs returned as queued/starting — row frozen at 'Запускается' even after the job completes server-side**

- Влияние: A row accepted as 'starting' shows 'Платный старт отправляется/Запускается' forever; the employee cannot tell whether the paid video is progressing, and if the server flags reconciliation the queue silently becomes unstartable with no visible reason. Only F5 (losing the queue) reveals the real state via the archive.
- Как чинить: Poll rows in phase 'status' whose job.status is non-terminal regardless of poll_provider_allowed (the strategy_status action is free and allowed for any job state — index.ts LOCAL_MOCK_FREE_ACTIONS and handler accept it), or add a separate keepalive for queued/starting jobs.
- Код: web/app/generation-strategy-runtime.js:1786-1812; supabase/functions/creator-generate/index.ts:8117-8121 and 8234-8239; web/app/app.js:29928-29932

**[минорный] Queue rows never link to their result — succeeded rows dead-end at a text label**

- Влияние: After paying for 10 videos the employee sees ten 'Готово — нужна проверка' labels with nothing clickable; they must scroll to the separate archive card and match rows by guesswork (where the download buttons are themselves broken — see blocker 2).
- Как чинить: Render a per-row link to the archive job view and/or the created review task once phase is 'status'.
- Код: web/app/generation-strategy-queue-view.js:123-131,745-747; The runtime projection carries output.media_id

**[минорный] strategy_mock_preflight/start/status edge actions have no frontend caller**

- Влияние: None in production (test-only surface); noted because the prior audit's bug 10 listed them. The local-mock first-shift walkthrough in the app cannot drive the strategy mock path.
- Как чинить: Leave as test-only, or document that the mock strategy contour is exercised exclusively by the e2e suite.
- Код: supabase/functions/creator-generate/index.ts:9624-9627; web/app/supabase-api.js:285-292 allowlist blocks them from the app.


## Ревью готового контента — работает частично

The review portal's plumbing is genuinely deployed end-to-end: all 10 review RPCs the frontend names exist in the cloud, the creator-content-review edge function is ACTIVE, the background worker cron (*/2 min, 518 completed runs/24h) dispatches queued content_review_runs, the queue-health RPC returns every counter the manager dashboard renders, and one full cycle (evidence -> AI run -> human decision -> sound assessment -> placement) has completed in production. However, the flagship "AI-проверка запускается автоматически" flow for generated videos is live-stuck right now: for any product whose metadata lacks a confirmed review category the start RPC always throws, the card's only retry button re-runs the same doomed call, and cloud data shows an employee looping for 4 days (15 evidence uploads, zero review runs) on one video while 54 orphaned evidence sets accumulate. An operator-role employee has no path at all for such a product; a manager can escape only by discovering the full manual form.

**[БЛОКЕР] Generated-video AI review can never start for products without a confirmed category; retry button loops forever and the flow is live-stuck in production**

- Влияние: The employee generated a paid video 5 days ago and still cannot get it reviewed: the technical scan succeeds, then every 'Повторить AI-проверку' fails with a category error, and every return to the page silently re-uploads another evidence set. An operator-role employee is fully dead-ended; the owner can escape only by realizing the toast means 'run the whole manual review form once'.
- Как чинить: In the autopilot RPC, fall back to the generation job's own validated input->>'product_category' (it is 'household' for the stuck job and already validated at paid start) or to 'other', for all roles — not only via the operator training-waiver branch; alternatively surface an explicit 'Подтвердить категорию' one-click action on the generation card that opens the full form pre-filled at the category step.
- Код: Cloud RPC content_factory_private.creator_start_generated_video_review_pre_project_v47: category_value := resolved_content_review_category(product_row.metadata); raises 'generated_video_review_category_required' when the value is not in the allowed list; Cloud data: product 9d15d1f0-4dbe-4b9b-8f71-79fb1fa737ac has metadata {}; E:/ContentEngine-local-workbench-v1/web/app/app.js:15136

**[минорный] Successful review decision can surface a generic failure error when post-decision routing finds no repair/placement target**

- Влияние: After an irreversible decision, the employee sees a generic failure and mixed signals; the decision is actually saved (the refreshed record shows it), but the promised handoff to the next step is silently lost and the employee may not find the restore-placement path.
- Как чинить: Map both codes to honest messages ('Решение сохранено, но следующий шаг не открылся — откройте Публикации/Генерацию вручную') and render the restore-placement CTA whenever an approved review has no placement, not only under the route flag.
- Код: E:/ContentEngine-local-workbench-v1/web/app/app.js:35471-35472; app.js:36661-36700; Recovery for the missing-placement case exists but is hidden behind the restore-placement section that only renders with the ?action=restore-placement route flag

**[минорный] Expired review evidence sets are never transitioned or cleaned up — 54 of 64 sets sit 'ready' past their TTL and count toward the manager storage quota**

- Влияние: Storage fills with unusable frames the employee cannot see or delete; the manager dashboard's 'Хранилище видео' utilization creeps up with data that is written but never read, with no advertised purge path.
- Как чинить: Have the background worker (or the evidence-prepare RPC) transition ready sets past expires_at to 'expired' and enqueue their frames into generation_storage_cleanup_queue; stop re-capturing evidence client-side when the previous start failed with a non-evidence error such as the category gate.
- Код: Cloud query: 54 evidence sets with status='ready' and expires_at <= now(), only 1 ever marked 'expired', 9 consumed; Cloud public.creator_operational_health def sums frame.size_bytes of ALL evidence sets into evidence_bytes/accounted_bytes against the 100 GB quota; its retention counters; The blocker finding above generates these orphans continuously

**[минорный] Malformed closing tag in review media picker markup ('<\strong>')**

- Влияние: Every file option in step 1 of the review wizard shows stray '<\strong>' text and wrong typography; purely cosmetic but visible on the portal's most-used review screen.
- Как чинить: Replace '<\strong>' with '</strong>' in reviewMediaOptionMarkup.
- Код: E:/ContentEngine-local-workbench-v1/web/app/content-review-view.js:1825


## ИИ-центр (обучение) — работает частично

The ИИ-центр renders against a fully deployed cloud contract (all 10 RPCs exist, the creator-ai-case-import edge function is active, tables carry real usage: 337 case events, 30 case decisions, 23 teaching decisions) and its read paths, historical-case confirm/reject, and the project research-training queue work today. But as a learning system it is largely inert: every legacy intake (links, files, teaching decisions) is hard-disabled by an unconditional client flag with no enable path, and cloud data proves the only ИИ-центр→prompt mechanism (historical-case advisory requiring exact product binding) matches 0 of 337 cases, so none of the team's 53 recorded decisions influence any generation prompt. The advertised replacement (dynamic market categories) has zero rows in all of its tables, leaving the research-training receipt loop (used once) as the only live учёба→промпт path.</summary>
</invoke>

**[БЛОКЕР] All legacy learning intake (add link, upload file, teach decisions) is hard-disabled by an unconditional legacyReadOnly:true with no enable path**

- Влияние: An employee opening ИИ-центр → «База знаний» sees the advertised 'Добавить ссылку / Загрузить файл' forms fully greyed out with no explanation on the form and no alternative surface; the historical-case import pipeline (the only mechanism designed to feed generation advisory) can never receive new spreadsheets. Teaching card decisions ('Да, использовать' / 'Нет') are equally disabled for everyone.
- Как чинить: Either remove the knowledge/teach intake UI entirely (matching the audit-only stance) or make legacyReadOnly conditional on a real server flag; if intake is meant to live on, re-enable canUploadFile at least for spreadsheet import since the server side (RPC + edge function + batches ledger) is fully functional.
- Код: web/app/app.js:18832; web/app/ai-learning-control-room.js:758-769; web/app/ai-learning-control-room.js:1054-1070

**[СЕРЬЁЗНЫЙ] ИИ-центр learning has zero effect on any generation prompt today: historical-case advisory matches 0 of 337 cases and teaching decisions never contribute angles**

- Влияние: Employees made 30 historical-case decisions and 23 teaching decisions believing they train the AI; none of it reaches any prompt. The only bridge (exact product binding) has no direct UI — guidance says 'Привяжите внешний SKU к точному внутреннему товару' but no bind action exists anywhere; the only implicit path is registering a product whose SKU happens to equal the historical case SKU via media upload.
- Как чинить: Ship a product-binding action on the historical case card (pick an internal product for a case SKU), or bulk-map case SKUs during import; alternatively surface 'this decision currently affects nothing — 0 cases bound' honestly in the cases tab KPIs (the data for it, missing_exact_product_binding_count, is already returned).
- Код: Cloud fn content_factory_private.creator_generation_learning_policy_pre_advisory_v9; Cloud data: ai_historical_case_events = 337 rows, product_id IS NULL on 100%; cross-check against content_factory.products: 0 of 335 matched events have any SKU/WB-article match; Cloud fn creator_generation_learning_policy_pre_advisory_v9

**[СЕРЬЁЗНЫЙ] Teach tab advertises a permanent pending queue that can never be cleared — primary CTA is a dead end**

- Влияние: The overview's main call-to-action leads every manager to a card with two permanently disabled buttons; the badge count never goes down, reading as a broken to-do rather than an archive.
- Как чинить: When legacyReadOnly is set, stop routing the primary CTA to 'teach' and stop rendering the pending badge; render decided-history only.
- Код: Cloud: ai_teaching_card_catalog is a global 12-card catalog; web/app/ai-learning-control-room.js:975; web/app/ai-learning-control-room.js:833

**[минорный] Control-room research inbox is dead code: server hard-empties it and its decide RPC returns no snapshot; review works only via the separately-loaded training module**

- Влияние: No day-to-day breakage (the training queue serves the flow), but a module load failure silently hides all pending research reviews with no retry, and ~600 lines of inbox UI plus one deployed RPC are dead weight that will desync the snapshot if ever re-enabled.
- Как чинить: Delete researchInboxMarkup/decideAiResearchReceipt and the creator_decide_ai_research_receipt RPC, or make the bootstrap failure visible with a retry button on /workspace/ai.
- Код: Cloud fn public.creator_ai_learning_control_room; web/app/ai-learning-control-room.js:867-928; Live path: contentengine_ai_research_training_queue reads ai_research_evidence_receipts filtered to awaiting_human_review

**[минорный] Quarantined historical cases instruct an action that exists nowhere**

- Влияние: An employee following the tooltip searches for a mapping/un-quarantine control that does not exist in the product.
- Как чинить: Change the copy to state quarantine is permanent for this batch, or add the mapping action.
- Код: web/app/ai-learning-control-room.js:1366; Cloud: no function matching %quarantin% exists in public schema; Cloud data: 2 events with resolution_status='quarantined' are permanently stuck; the nominal workaround

**[минорный] Market-category learning panel (the advertised replacement for legacy learning) has never had data: 0 market categories, 0 bindings, 0 readiness snapshots despite 14 research runs**

- Влияние: The legacy panel deprecates itself in favor of a surface no one has ever populated; combined with the disabled legacy intake, the org currently has no operating category-learning loop at all.
- Как чинить: Verify the research portal's market-category resolution step is actually reachable in the operators' flow (it requires a completed run + explicit category confirmation) and consider prompting for it at research completion.
- Код: Cloud: research_market_categories=0, research_product_market_category_bindings=0, research_category_readiness_snapshots=0, product_research_runs=14, generation_spec_research_category_rule_bindings=0; web/app/ai-learning-control-room.js:823; The empty-state CTA works: aiLearningFreshResearchHref


## Рекомендации (research → «Замысел») — работает частично

The happy path works end-to-end today: all four RPCs (recommendations list, exact recommendation, working draft, spec AI-binding) exist in the cloud with response shapes matching the strict client normalizers (version strings, contract booleans, recommendation_hash, AIResearchSelection/v1 provider fragments 231-232 chars ≤ 240 cap), real data resolves (1 approved selection, snapshots valid for positions 1-3, working draft at revision 75), and all 37 local contract tests pass. The 40001 retry storm is confirmed resolved in production: postgres logs show ~1.98M revision-conflict errors/hour (SQLSTATE 40001, PostgREST-internal retry of one stale write with expected_revision=53 vs current 75) sustained until 2026-08-16 08:29 UTC, then exactly 2 terminal PT409 errors at the moment migration 202608160001 landed, and zero conflicts in the ~11.5 hours since; the deployed function body now contains only PT409. What keeps the subsystem at 'partial' is error-state recovery: a single failed working-draft hydration permanently dead-ends the entire «Вставить этот вариант в Замысел» flow until F5/route re-entry despite a status message telling the employee to retry, and a CAS conflict silently freezes shared-draft sync while later edits overwrite the only warning.

**[СЕРЬЁЗНЫЙ] Failed working-draft hydration permanently blocks the apply-recommendation flow with no retry path**

- Влияние: After one transient network/server error during the shared-draft read, an employee who clicks «Вставить этот вариант в Замысел» (or arrives via the AI-center deep link) is told the server must first confirm the draft and to retry after the connection recovers — but no retry ever happens while they stay on the page: re-clicking the button, changing fields, or waiting does nothing. Recovery requires F5 or navigating to another route and back, which nothing suggests. If a recommendation lineage is active, paid launch is also blocked (working_draft_unverified in generationSpecPreparationFailure, app.js:25692-25693).
- Как чинить: Treat authority "failed" as retryable: have the blocked branch in loadRecommendations (or requestExplicitRecommendation) call hydrateSharedWorkingDraft again before giving up, or include authority==="failed" in shouldHydrateGenerationResearchWorkingDraft with a backoff, and/or add an explicit «Повторить проверку» button to the blocker status.
- Код: E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:1851-1864; E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:2892-2904; E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:2509-2524

**[СЕРЬЁЗНЫЙ] After a revision conflict, shared-draft sync silently stays frozen and later edits overwrite the only warning**

- Влияние: The panel advertises «Другой участник увидит выбранный вариант и ваши правки». After one CAS conflict, every further edit in the tab is kept only locally while the UI keeps reporting normal per-field statuses — the employee believes their creative edits are shared, teammates never see them, and closing the tab loses them. This matches the by-design one-time warning, but the warning does not survive the very next keystroke and no persistent indicator exists.
- Как чинить: Render the conflict state persistently (e.g., a data attribute on the panel plus a pinned badge like «Синхронизация остановлена — обновите страницу») and make markHumanEdit append rather than replace the status while runtime.workingDraftConflict is true; optionally offer a one-click re-read that re-bases on the server revision.
- Код: E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:1296-1301; E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:1625-1631; E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:1602-1607

**[минорный] Transient recommendations-RPC failure is cached as a completed result; same context never reloads**

- Влияние: After one failed list request, the panel shows «временно недоступны» forever for that product/category; only changing a watched field (category, product, sku, platform, media) or leaving the route triggers a new request. Manual brief entry remains available, so the flow is degraded, not blocked.
- Как чинить: Do not assign runtime.response in the catch path (leave it null so the next scheduleLoad retries), or record a failure timestamp and allow reload after a short TTL.
- Код: E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:2756-2765; E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:2797-2803

**[минорный] Module-load failure of the recommendations adapter is announced by an event nobody listens to; deep links then silently do nothing**

- Влияние: If workspace-generation-research-recommendations.js fails to load (bad network, cache issue), the «Использовать этот вариант в Создать» deep link from the AI center lands on the generation form with its selection_id/recommendation_position parameters silently ignored — no panel, no error, only a console warning. The armed one-shot intent then expires unused after 5 minutes.
- Как чинить: Add a listener for contentengine:research-learning-failed on the generation route that renders a visible fallback notice with a reload action, or retry the import once.
- Код: E:/ContentEngine-local-workbench-v1/web/app/workspace-research-training-bootstrap.js:221-226; E:/ContentEngine-local-workbench-v1/web/app/workspace-research-training-bootstrap.js:80-85

**[минорный] Working-draft read RPC throws selection_stale with no client handling and no recovery path to clear the draft**

- Влияние: Currently near-unreachable (FK generation_ai_research_workin_organization_id_selection_id_fkey has no cascade, and ai_research_learning_selections are insert-only via contentengine_decide_ai_research_training_unscoped_v1), but if a selection row is ever removed or repositioned by an admin/migration, the project's «Создать» shared-draft hydration fails permanently with a generic «временно недоступен» message and the draft can never be cleared from the UI.
- Как чинить: In the snapshot function, return a cleared/tombstone response (or a draft with a stale marker) instead of raising on the read path, so the client can surface it and offer opt-out/clear.
- Код: Cloud content_factory_private.generation_ai_research_working_draft_snapshot; E:/ContentEngine-local-workbench-v1/web/app/workspace-generation-research-recommendations.js:1288-1294; E:/ContentEngine-local-workbench-v1/web/app/generation-ai-research-working-draft.js:449-460

**[минорный] Cloud schema is unversioned: list_migrations is empty, hotfixes reach production ad hoc**

- Влияние: The retry-storm fix itself is confirmed working in production (no conflicts in the ~11.5 hours since 08:29 UTC). But with no migration tracking, there is no guarantee the other local migrations in this branch match what is deployed, and future hotfixes depend on someone remembering to paste SQL — the same gap that let this storm burn roughly 24.8M errors in its final 24 hours after the fix already existed locally.
- Как чинить: Adopt supabase db push / apply_migration so schema_migrations tracks what production runs, and add an alert on postgres error-rate spikes for the working-draft RPC.
- Код: Supabase MCP list_migrations on project iyckwryrucqrxwlowxow returns [] while ~50 migration files exist under E:/ContentEngine-local-workbench-v1/supabase/migrations; Storm timeline from postgres_logs: SQLSTATE 40001 revision-conflict errors at ~1,980,000/hour continuously until 2026-08-16T08:29:38 UTC, then exactly 2 PT409 errors, then zero; Deployed function verified post-fix: pg_get_functiondef contains errcode PT409, zero occurrences of 40001, and the hotfix comment


## Операционное здоровье и бюджеты — работает частично

The money contour and operational health portals genuinely work end-to-end for an employee today: creator_generation_spend_overview / creator_update_generation_spend_policy / campaign RPCs all exist in the cloud with shapes matching the frontend normalizers, role gates align (owner/admin both sides), the spend ledger has real data (30 rows, $20.59 committed) that aggregates correctly into the day/month cards, version-conflict recovery reloads the overview, and the ops health card's scheduler/worker/generation/review/storage keys all exist with a fresh worker heartbeat. The one broken flow is notification actions v491: the cloud copy of creator_validate_notification_action is still STABLE while it writes a profile upsert on every call, so PostgREST runs it read-only and every notification action click fails — the committed fix migration (202608160004) was never applied to the cloud. Remaining findings are latent dead ends and unread server data, not blockers.

**[БЛОКЕР] Notification action validation RPC is STABLE in cloud but writes on every call — all v491 notification action clicks fail**

- Влияние: An employee clicking any action button on a v491 notification (open AI decision, open object, open review, open process) always gets a 'action no longer available' error; the deep-link flow is dead in the cloud deployment even though every local test passes.
- Как чинить: Apply migration 202608160004_writable_authenticated_read_rpcs.sql to the cloud project (ALTER FUNCTION ... VOLATILE for the 8 listed RPCs + notify pgrst 'reload schema').
- Код: Cloud pg_proc: public.creator_validate_notification_action provolatile='s'; supabase/migrations/202608160004_writable_authenticated_read_rpcs.sql:8-15; supabase/tests/notification_action_validation_v491_test.sql:19-25

**[минорный] Cloud ops-health computes billing-reconciliation / cleanup / retention metrics the portal never reads, and its storage numbers are mutually inconsistent on screen**

- Влияние: Manager sees slightly contradictory storage arithmetic and misses cleanup dead-letter / billing-reconciliation signals in the health portal; the reconciliation state is still enforced (paid runs blocked), so no money is at risk.
- Как чинить: Render the billing and cleanup/retention counters in managerOperationalHealthMarkup, and show 'Занято' from accounted_bytes (or list evidence/reservations separately).
- Код: Cloud public.creator_operational_health appends storage.evidence_bytes, accounted_bytes, retention_due_count/bytes, cleanup_pending/processing/dead_letter and a billing{unknown_failure_outcomes, requires_reconciliation} object; grep of web/app for unknown_failure_outcomes|requires_reconciliation|cleanup_dead_letter|retention_due|accounted_bytes|evidence_bytes returns zero matches; web/app/manager-dashboard-view.js:125-129,264-271; The billing.requires_reconciliation alarm

**[минорный] Platform kill-switch state is reported as 'paused by manager' with a resume button that cannot un-pause it; the dedicated platform-disabled messages are dead strings**

- Влияние: If the platform switch is ever turned off, an owner is told the pause is their own, clicks resume, gets a success toast, and paid launches remain blocked with no hint that a system-level switch is the cause.
- Как чинить: Emit distinct blocker codes for platform-missing/platform-disabled from the overview function (the frontend already has the strings), or suppress the resume button when the blocker is platform-level.
- Код: Cloud content_factory_private.generation_spend_organization_overview maps both a missing and a disabled generation_spend_platform_control row to blocker_code='paid_generation_paused'; web/app/generation-spend-view.js:2,17-18; Cloud content_factory_private.generation_spend_platform_control currently has runway_paid_generation=true, and only service-level public.system_update_generation_spend_control can change it, so the trap is latent today; if support flips the switch, the manager's 'resume' saves the org policy, shows the success toast 'Платные запуски включены...'

**[минорный] Campaign quota error tells the manager to archive campaigns, but no archive/complete action exists anywhere (UI or RPC)**

- Влияние: At 100 campaigns an owner is permanently blocked from creating new campaigns while being instructed to perform an action the product does not offer. Latent (1 campaign exists today).
- Как чинить: Add an archive action (RPC + button in the campaign editor), or change the error copy until one exists.
- Код: web/app/supabase-api.js:8559; Cloud creator_create_generation_campaign raises this at >=100 non-archived campaigns; the only campaign RPCs in cloud public schema are creator_create_generation_campaign and creator_update_generation_campaign_spend_policy; web/app/generation-spend-view.js:327-352

**[минорный] policy.present detection never fires against real cloud payloads, so the 'save team budget first' guidance and two fail-safes are dead code; a missing campaign policy is an unrecoverable edit loop**

- Влияние: Cosmetic today: misleading first-run guidance ordering and a latent stuck-forever campaign editor if a campaign policy row is ever lost.
- Как чинить: Derive policy.present from overview.blocker_code/policy.version>0 instead of key presence, and let the campaign update RPC upsert a missing policy at expected_version 0.
- Код: web/app/generation-spend-view.js:35-41; web/app/supabase-api.js:2697-2701


## Обучение сотрудников — сломана

The four courses (lessons, walkthroughs, server-graded course checks, platform simulators, completion) work end-to-end, but the journey dead-ends at the mandatory practical project: the live cloud bootstrap chain lost the layer that returns training.practical_project/practical_reviews/practical_upload, while both the front-end and creator_submit_exam still hard-gate the exam and workspace access on practical approval. As a result an employee can finish all courses but can never submit a gradeable practical, never take the exam, and never reach the workspace; the only functioning access path today is a service-role-granted waiver (live data confirms: all course certifications are 'revoked' and all 5 workspace-access holders have waivers). Walkthrough repeat/reset, drafts, and course-check restore-after-F5 are solidly built and show no dead ends.

**[БЛОКЕР] Live bootstrap lost the practical-project layer: exam and workspace are permanently gated on data the server never sends**

- Влияние: A new employee can complete all four courses (checks, walkthroughs, simulators all work) and then hits an unfinishable step: MP4 upload is refused, the exam page always says 'Сначала покажите навык на пробном ролике', creator_submit_exam rejects submissions, and /access-required never shows the request button. The advertised training-to-workspace journey cannot be completed by anyone without an ops-granted waiver.
- Как чинить: Rewire the bootstrap chain so the practical layer is live again: point content_factory_private.creator_bootstrap_pre_training_waiver's callee chain through creator_bootstrap_pre_assessment_v5_sanitize (which itself must call the current pre_auth_email_gate head instead of the orphaned pre_practical_gate), or fold the practical_project/practical_reviews/practical_upload emission plus practical state gate into a fresh migration that rebuilds public.creator_bootstrap deterministically.
- Код: Cloud: public.creator_bootstrap calls content_factory_private.creator_bootstrap_pre_training_waiver -> creator_bootstrap_pre_auth_email_gate; Cloud: content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize is the ONLY function that emits training.practical_* and the practical state gate, and a prosrc scan over public+content_factory_private found ZERO callers; Cloud: public.creator_submit_exam -> creator_submit_exam_pre_rationale_v2 -> creator_submit_exam_pre_result_sanitize raises 'practical_project_approval_required'

**[СЕРЬЁЗНЫЙ] Practical submissions and decisions are write-only: server accepts them but no read path exists, so success messages are misleading**

- Влияние: An employee's URL-evidence submission is stored in the database but appears lost after any refresh (looks like silent data loss); managers never see any submissions, so nothing can ever be approved or returned for changes from the portal.
- Как чинить: Same root fix as the blocker; additionally make refresh_scope='training_practical_reviews' either supported by the live bootstrap or switch the queue to a dedicated read RPC so manager review does not depend on the full bootstrap payload.
- Код: Cloud: public.creator_save_practical_project exists, requires courses complete, and accepts evidence_url/object_key writes into content_factory.training_practical_projects; E:/ContentEngine-local-workbench-v1/web/app/app.js:7089-7097; E:/ContentEngine-local-workbench-v1/web/app/app.js:7002-7004 and 7155-7189

**[СЕРЬЁЗНЫЙ] Waiver is the only functioning access path but has no portal surface and is silently voided by a role change**

- Влияние: Onboarding every employee requires an out-of-band service-role SQL call that managers cannot perform from the portal; and a routine admin role change (operator -> reviewer) instantly drops a working employee back into the uncompletable training loop with no warning shown in the admin UI.
- Как чинить: Until the blocker is fixed, expose waiver grant/revoke through creator_admin_mutate for owner/admin roles (with audit fields already present in training_access_waivers), and warn in the admin role-change flow when the change will deactivate an active waiver.
- Код: Cloud: system_set_training_access_waiver / system_grant_training_access_waiver_batch grant execute only to postgres+service_role; Cloud: content_factory_private.training_access_waiver_active requires membership.role = waiver.granted_role, and system_set_training_access_waiver hardcodes granted_role='operator'; E:/ContentEngine-local-workbench-v1/web/app/app.js:5042-5046

**[минорный] Orphaned/dead code around the training entry path invites regressions**

- Влияние: No direct employee impact, but the shuffled name-to-body mapping of the bootstrap layers is exactly what allowed the practical layer to fall out of the chain unnoticed; future migrations that rename/replace public.creator_bootstrap can silently repeat the failure.
- Как чинить: Drop the orphaned SQL functions after the chain is rebuilt, delete renderLearningHomeLegacy and the retired learning-premium assets, and add a SQL test that asserts the live public.creator_bootstrap output contains training.practical_project/practical_upload keys for a learning-state user.
- Код: Cloud: content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize and creator_bootstrap_pre_practical_gate remain deployed with zero callers; E:/ContentEngine-local-workbench-v1/web/app/app.js:6321; E:/ContentEngine-local-workbench-v1/web/app/learning-premium.js targets '.learning-page:not(.course-page)' on /learn


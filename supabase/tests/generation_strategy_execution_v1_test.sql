begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_table(
  'content_factory', 'generation_strategy_binding_selections',
  'full immutable selection and price have an execution ledger'
);
select has_table(
  'content_factory', 'generation_strategy_media_durations',
  'server MP4 duration probes have an append-only ledger'
);
select has_table(
  'content_factory', 'generation_strategy_readiness_receipts',
  'provider readiness has a dedicated short-lived receipt ledger'
);
select has_table(
  'content_factory', 'generation_strategy_start_claims',
  'one paid strategy start has an immutable claim ledger'
);
select has_table(
  'content_factory', 'generation_strategy_dispatch_attempts',
  'one provider POST slot has an immutable attempt ledger'
);
select has_table(
  'content_factory', 'generation_strategy_dispatch_results',
  'dispatch outcome has an immutable result ledger'
);
select has_table(
  'content_factory', 'generation_strategy_provider_status_events',
  'recipe provider status has an append-only journal'
);
select has_table(
  'content_factory', 'generation_strategy_dispatch_reconciliations',
  'ambiguous dispatch has a human-evidence reconciliation ledger'
);
select has_table(
  'content_factory', 'generation_strategy_worker_requests',
  'global exact-claim worker scans have an append-only request ledger'
);
select has_table(
  'content_factory', 'generation_strategy_worker_leases',
  'strategy recovery candidates have an append-only bounded lease ledger'
);

select is(
  (
    select count(*)::bigint
    from pg_catalog.pg_class relation
    join pg_catalog.pg_namespace namespace
      on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname in (
        'generation_strategy_binding_selections',
        'generation_strategy_media_durations',
        'generation_strategy_readiness_receipts',
        'generation_strategy_start_claims',
        'generation_strategy_dispatch_attempts',
        'generation_strategy_dispatch_results',
        'generation_strategy_provider_status_events',
        'generation_strategy_dispatch_reconciliations',
        'generation_strategy_worker_requests',
        'generation_strategy_worker_leases'
      )
      and relation.relrowsecurity
  ),
  10::bigint,
  'all ten execution ledgers have RLS enabled'
);

select is(
  (
    select count(*)::bigint
    from pg_catalog.pg_trigger trigger_row
    where trigger_row.tgrelid in (
      'content_factory.generation_strategy_binding_selections'::regclass,
      'content_factory.generation_strategy_media_durations'::regclass,
      'content_factory.generation_strategy_readiness_receipts'::regclass,
      'content_factory.generation_strategy_start_claims'::regclass,
      'content_factory.generation_strategy_dispatch_attempts'::regclass,
      'content_factory.generation_strategy_dispatch_results'::regclass,
      'content_factory.generation_strategy_provider_status_events'::regclass,
      'content_factory.generation_strategy_dispatch_reconciliations'::regclass,
      'content_factory.generation_strategy_worker_requests'::regclass,
      'content_factory.generation_strategy_worker_leases'::regclass
    )
      and trigger_row.tgname like 'generation_strategy_%_append_only'
      and not trigger_row.tgisinternal
  ),
  10::bigint,
  'all ten ledgers reject update and delete'
);

select is(
  (
    select count(*)::bigint
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.generation_strategy_start_claims'::regclass
      and constraint_row.contype = 'f'
      and constraint_row.condeferrable
      and constraint_row.condeferred
      and constraint_row.confrelid in (
        'content_factory.generation_batches'::regclass,
        'content_factory.generation_jobs'::regclass,
        'content_factory.creator_tasks'::regclass
      )
  ),
  3::bigint,
  'claim aggregate foreign keys are all deferred until transaction end'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_binding_selections', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_media_durations', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_readiness_receipts', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_start_claims', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_dispatch_attempts', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_dispatch_results', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_provider_status_events', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_dispatch_reconciliations', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_worker_requests', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_worker_leases', 'select'
  ),
  'authenticated clients cannot read private execution ledgers directly'
);

with rpc(function_name) as (
  values
    ('system_resolve_and_bind_generation_strategy'),
    ('system_generation_strategy_media_probe_context'),
    ('system_record_generation_strategy_media_duration'),
    ('system_generation_strategy_catalog_policy'),
    ('system_record_generation_strategy_readiness'),
    ('system_claim_generation_strategy_start'),
    ('system_mark_generation_strategy_dispatch_attempt'),
    ('system_record_generation_strategy_dispatch_result'),
    ('system_reconcile_generation_strategy_dispatch'),
    ('system_record_generation_strategy_provider_status'),
    ('system_generation_strategy_status'),
    ('system_claim_generation_strategy_worker_candidates'),
    ('system_generation_strategy_provider_policy')
)
select ok(
  to_regprocedure('public.' || function_name || '(jsonb)') is not null
  and has_function_privilege(
    'service_role', 'public.' || function_name || '(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated', 'public.' || function_name || '(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.' || function_name || '(jsonb)', 'execute'
  ),
  function_name || ' is installed service-only'
)
from rpc;

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_generation_strategy_asset_candidates(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_generation_strategy_asset_candidates(jsonb)', 'execute'
  ),
  'asset candidates are available only to authenticated ACL-scoped users'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_generation_strategy_repeat_data(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_generation_strategy_repeat_data(jsonb)', 'execute'
  ),
  'Repeat Settings remains an authenticated read-only projection'
);

select ok(
  content_factory_private.generation_strategy_execution_chain_installed(),
  'the complete bind/probe/readiness/claim/dispatch/status chain is installed'
);

select ok(
  position(
    'claim_row.id is not null' in pg_get_functiondef(
      'content_factory_private.generation_strategy_execution_input_current(uuid,uuid,uuid,uuid,jsonb,bigint)'
        ::regprocedure
    )
  ) > 0,
  'batch and job validation require a materialized exact claim'
);

select ok(
  position(
    'receipt_row.expires_at' in pg_get_functiondef(
      'content_factory_private.generation_strategy_execution_input_current(uuid,uuid,uuid,uuid,jsonb,bigint)'
        ::regprocedure
    )
  ) = 0,
  'historical exact claims do not become invalid when readiness expires'
);

select ok(
  position(
    'insert into content_factory.generation_strategy_start_claims' in
    pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )
  ) < position(
    'insert into content_factory.generation_batches' in
    pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )
  )
  and position(
    'insert into content_factory.generation_batches' in
    pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )
  ) < position(
    'insert into content_factory.generation_jobs' in
    pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )
  ),
  'claim is inserted before the deferred batch/job/task aggregate'
);

select is(
  (
    length(pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )) - length(replace(pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    ), '''price'', receipt_row.price_snapshot - ''spend_confirmation''', ''))
  ) / length('''price'', receipt_row.price_snapshot - ''spend_confirmation'''),
  2,
  'fresh and replay claim responses expose the exact same scrubbed price shape'
);

select is(
  (
    length(pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )) - length(replace(pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    ), '''productInfoHash''', ''))
  ) / length('''productInfoHash'''),
  2,
  'fresh and replay claim responses both include productInfoHash'
);

select is(
  (
    length(pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    )) - length(replace(pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    ), '''userConceptHash''', ''))
  ) / length('''userConceptHash'''),
  2,
  'fresh and replay claim responses both include nullable userConceptHash'
);

select ok(
  position(
    'into strict actor_role_value' in pg_get_functiondef(
      'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'generation_strategy_readiness_access_required' in pg_get_functiondef(
      'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
    )
  ) > 0,
  'missing readiness actor maps to the deliberate 42501 access error path'
);

select throws_ok(
  $$
    select public.system_record_generation_strategy_readiness(
      jsonb_build_object(
        'version', 'generation-strategy-readiness-record-request-v1',
        'organization_id', '00000000-0000-4000-8000-000000000101',
        'project_id', '00000000-0000-4000-8000-000000000102',
        'actor_id', '00000000-0000-4000-8000-000000000103',
        'binding_id', '00000000-0000-4000-8000-000000000104',
        'binding_hash', repeat('a', 64),
        'selection_hash', repeat('b', 64),
        'price_hash', repeat('c', 64),
        'spend_confirmation', 'CONFIRM-EXACT-STRATEGY-SPEND-TEST',
        'credential_configured', false,
        'provider_authentication_confirmed', false,
        'balance_sufficient', false,
        'provider_failure_code', 'provider_configuration_error',
        'confirmation', true,
        'idempotency_key', 'missing-actor-readiness-test'
      )
    )
  $$,
  '42501',
  'generation_strategy_readiness_access_required',
  'a missing or revoked readiness actor fails with the stable access code'
);

select throws_ok(
  $$
    select public.system_record_generation_strategy_dispatch_result(
      jsonb_build_object(
        'version', 'generation-strategy-dispatch-result-request-v1',
        'organization_id', '00000000-0000-4000-8000-000000000101',
        'project_id', '00000000-0000-4000-8000-000000000102',
        'actor_id', '00000000-0000-4000-8000-000000000103',
        'attempt_id', '00000000-0000-4000-8000-000000000104',
        'attempt_hash', repeat('a', 64),
        'dispatch_token', '00000000-0000-4000-8000-000000000105',
        'generation_job_id', '00000000-0000-4000-8000-000000000106',
        'outcome', 'submitted',
        'provider_post_started', true,
        'provider_http_status', null,
        'provider_task_id', null,
        'failure_code', null,
        'provider_evidence_hash', repeat('b', 64),
        'confirmation', true,
        'idempotency_key', 'null-submission-proof-test'
      )
    )
  $$,
  '22023',
  'generation_strategy_dispatch_result_payload_invalid',
  'submitted can never exploit SQL NULL semantics to omit HTTP/task proof'
);

with ambiguous_status(http_status, case_name) as (
  values
    (200, 'invalid 2xx body'),
    (408, '408 response'),
    (425, '425 response'),
    (500, '500 response'),
    (505, 'unrecognized 5xx response')
)
select throws_ok(
  format(
    'select public.system_record_generation_strategy_dispatch_result(%L::jsonb)',
    jsonb_build_object(
      'version', 'generation-strategy-dispatch-result-request-v1',
      'organization_id', '00000000-0000-4000-8000-000000000101',
      'project_id', '00000000-0000-4000-8000-000000000102',
      'actor_id', '00000000-0000-4000-8000-000000000103',
      'attempt_id', '00000000-0000-4000-8000-000000000104',
      'attempt_hash', repeat('a', 64),
      'dispatch_token', '00000000-0000-4000-8000-000000000105',
      'generation_job_id', '00000000-0000-4000-8000-000000000106',
      'outcome', 'ambiguous',
      'provider_post_started', true,
      'provider_http_status', http_status,
      'provider_task_id', null,
      'failure_code', 'provider_submission_ambiguous',
      'provider_evidence_hash', repeat('b', 64),
      'confirmation', true,
      'idempotency_key', 'ambiguous-totality-' || http_status::text
    )::text
  ),
  '55000',
  'generation_strategy_dispatch_result_not_current',
  case_name || ' is accepted as ambiguous before exact-attempt validation'
)
from ambiguous_status;

select ok(
  position(
    'input_signing_failed' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'input_asset_not_current' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'signed_url_invalid' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'set status = ''failed'', actual_cost_minor = 0' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'pre-dispatch input failures terminalize with zero provider cost'
);

select ok(
  position(
    '400, 401, 402, 403, 404, 405, 422, 429' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'provider_http_status_value between 100 and 599' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'provider_http_status_value not in (' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''second_post_allowed'', false' in pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'exhaustive deterministic/ambiguous HTTP matrix preserves one POST'
);

select ok(
  position(
    'membership.role in (''owner'', ''admin'')' in pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''second_post_allowed'', false' in pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'ambiguous reconciliation is owner/admin evidence-only and cannot repost'
);

select ok(
  position(
    'generation_strategy_media_durations duration' in pg_get_functiondef(
      'public.creator_generation_strategy_asset_candidates(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'server_duration_probe_required' in pg_get_functiondef(
      'public.creator_generation_strategy_asset_candidates(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'media.metadata ->> ''duration_seconds''' in pg_get_functiondef(
      'public.creator_generation_strategy_asset_candidates(jsonb)'::regprocedure
    )
  ) = 0,
  'Product Swap candidates use only the verified server duration ledger'
);

select ok(
  position(
    '''paid_start_authorized'', false' in pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''catalog_policy_is_not_paid_authority'', true' in pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    )
  ) > 0,
  'org catalog capability never acts as paid-start authority'
);

select ok(
  position(
    'receipt_unconsumed_value' in pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'generation_strategy_execution_chain_installed' in pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    )
  ) > 0,
  'context launch policy requires an unconsumed receipt and complete chain'
);

select ok(
  position(
    '''media_hashes_returned'', false' in pg_get_functiondef(
      'public.system_generation_strategy_status(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''signed_urls_returned'', false' in pg_get_functiondef(
      'public.system_generation_strategy_status(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'price_snapshot - ''spend_confirmation''' in pg_get_functiondef(
      'public.system_generation_strategy_status(jsonb)'::regprocedure
    )
  ) > 0,
  'recipe status exposes no object/hash/URL or one-shot confirmation authority'
);

select ok(
  has_table_privilege(
    'service_role',
    'content_factory.generation_strategy_worker_requests',
    'select,insert,update,delete'
  )
  and has_table_privilege(
    'service_role',
    'content_factory.generation_strategy_worker_leases',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_worker_requests', 'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_strategy_worker_leases', 'select'
  ),
  'worker request and lease ledgers remain private service-only tables'
);

select ok(
  position(
    'job.status = ''starting''' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'attempt.id is not null' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'result.id is null' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'interval ''90 seconds''' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''dispatch_unknown_never_reposts'', true' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'C-without-D crashes become a due dispatch_unknown lease and never repost'
);

select ok(
  position(
    'organization_id_value is null' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'from content_factory.generation_strategy_start_claims claim' in
    pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'for update of job skip locked' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'active_lease.leased_until > requested_at_value' in pg_get_functiondef(
      'public.system_claim_generation_strategy_worker_candidates(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'global discovery recovers sole queued claims with one active job lease'
);

select ok(
  position(
    'strategy_worker_owned' in pg_get_functiondef(
      'public.system_mark_real_generation_reconciliation_required(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''marked'', false' in pg_get_functiondef(
      'public.system_mark_real_generation_reconciliation_required(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'legacy starting watchdog returns safely without mutating strategy claims'
);

select ok(
  position(
    'elsif previous_status_value = provider_status_value then' in
    pg_get_functiondef(
      'public.system_record_generation_strategy_provider_status(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''current_status_reused'', current_status_reused_value' in
    pg_get_functiondef(
      'public.system_record_generation_strategy_provider_status(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''same_status_returns_current'', true' in pg_get_functiondef(
      'public.system_record_generation_strategy_provider_status(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'concurrent duplicate provider status returns the current immutable event'
);

select ok(
  position(
    'claim_actor_access_revoked' in pg_get_functiondef(
      'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'claim_organization_inactive' in pg_get_functiondef(
      'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''terminalized_before_provider_post''' in pg_get_functiondef(
      'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'generation_strategy_dispatch_result_access_required' in
    pg_get_functiondef(
      'public.system_record_generation_strategy_dispatch_result(jsonb)'
        ::regprocedure
    )
  ) = 0
  and position(
    'generation_strategy_provider_status_access_required' in
    pg_get_functiondef(
      'public.system_record_generation_strategy_provider_status(jsonb)'
        ::regprocedure
    )
  ) = 0,
  'pre-POST ACL/org drift releases; post-POST service completion survives drift'
);

select ok(
  position(
    '''attestations'', reset_attestations_value' in pg_get_functiondef(
      'public.creator_generation_strategy_repeat_data(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''generation_job_id'', generation_job_id_value' in pg_get_functiondef(
      'public.creator_generation_strategy_repeat_data(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''requires_fresh_price_confirmation'', true' in pg_get_functiondef(
      'public.creator_generation_strategy_repeat_data(jsonb)'::regprocedure
    )
  ) > 0,
  'Repeat Settings returns the full safe template with all authority reset'
);

select ok(
  position(
    '''generation_job_id'', claim_row.generation_job_id' in pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''generation_strategy_execution_selection''' in pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''generation_strategy_price_reference''' in pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) > 0,
  'archive rows expose job id plus safe immutable selection and display price'
);

select ok(
  position(
    '''generation_strategy_snapshot'',' in pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    '''generation_strategy_snapshot_hash'',' in pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    '''generation_strategy_snapshot'',' in pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''generation_strategy_snapshot_hash'',' in pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'archive v2 preserves the authoritative base strategy snapshot/hash bytes'
);

select ok(
  position(
    '''product_info_hash''' in pg_get_functiondef(
      'content_factory_private.generation_strategy_prompt_snapshot(uuid,uuid,jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''user_concept_hash''' in pg_get_functiondef(
      'content_factory_private.generation_strategy_prompt_snapshot(uuid,uuid,jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''size_bytes'', media.size_bytes' in pg_get_functiondef(
      'content_factory_private.generation_strategy_asset_context(uuid,uuid)'
        ::regprocedure
    )
  ) > 0,
  'service execution context pins prompt hashes and authoritative asset size'
);

select * from finish();
rollback;

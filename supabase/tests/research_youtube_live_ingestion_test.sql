begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select plan(61);

select is(
  content_factory_private.research_youtube_global_state(),
  'disabled',
  'the YouTube global kill switch is disabled by default'
);
select ok(
  not content_factory_private.research_youtube_global_gate('manual_canary')
  and not content_factory_private.research_youtube_global_gate('category_refresh'),
  'neither canary nor refresh transport opens in the default state'
);
select is(
  (select catalog.lifecycle_status || '/' || catalog.rollout_stage
   from content_factory.research_provider_catalog catalog
   where catalog.provider_key = 'youtube_data_api_v3'),
  'disabled/planned',
  'the generic provider catalog remains disabled and planned'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_youtube_global_rollout_decisions'::regclass),
     ('content_factory.research_youtube_rollout_decisions'::regclass),
     ('content_factory.research_youtube_ingestion_runs'::regclass),
     ('content_factory.research_youtube_transport_attempts'::regclass),
     ('content_factory.research_youtube_transport_receipts'::regclass),
     ('content_factory.research_youtube_video_observations'::regclass),
     ('content_factory.research_youtube_candidate_decisions'::regclass),
     ('content_factory.research_youtube_retention_receipts'::regclass),
     ('content_factory.research_youtube_derived_analysis_decisions'::regclass),
     ('content_factory.research_youtube_observation_analysis_jobs'::regclass),
     ('content_factory.research_youtube_observation_analysis_events'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  11,
  'all YouTube control, analysis and evidence tables have RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_youtube_global_rollout_decisions'::regclass),
     ('content_factory.research_youtube_rollout_decisions'::regclass),
     ('content_factory.research_youtube_ingestion_runs'::regclass),
     ('content_factory.research_youtube_transport_attempts'::regclass),
     ('content_factory.research_youtube_transport_receipts'::regclass),
     ('content_factory.research_youtube_video_observations'::regclass),
     ('content_factory.research_youtube_candidate_decisions'::regclass),
     ('content_factory.research_youtube_retention_receipts'::regclass),
     ('content_factory.research_youtube_derived_analysis_decisions'::regclass),
     ('content_factory.research_youtube_observation_analysis_jobs'::regclass),
     ('content_factory.research_youtube_observation_analysis_events'::regclass)
   ) protected(table_oid)
   cross join (values
     ('anon'), ('authenticated'), ('service_role')
   ) grantee(role_name)
   cross join (values
     ('select'), ('insert'), ('update'), ('delete')
   ) privilege(name)
   where has_table_privilege(
     grantee.role_name, protected.table_oid, privilege.name
   )),
  0,
  'anon, authenticated and service roles have no direct ledger privileges'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_claim_research_youtube_ingestion(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_claim_research_youtube_ingestion(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_claim_research_youtube_ingestion(jsonb)',
    'execute'
  ),
  'creator claim is callable only through the authenticated creator boundary'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_begin_research_youtube_transport(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_complete_research_youtube_ingestion(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_purge_expired_youtube_api_data(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_decide_research_youtube_derived_analysis(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_process_due_research_youtube_observation_analysis(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_begin_research_youtube_transport(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_complete_research_youtube_ingestion(jsonb)',
    'execute'
  ),
  'transport, completion and purge RPCs are service-only'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.claim_research_youtube_ingestion(uuid)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.claim_research_youtube_ingestion(uuid)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.research_youtube_retention_ready()',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.research_youtube_derived_analysis_approved()',
    'execute'
  ),
  'private claim and retention helpers have no direct application grants'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_claim_research_youtube_ingestion(jsonb)'::regprocedure
  )), 'requested_by_value <> user_id') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_claim_research_youtube_ingestion(jsonb)'::regprocedure
  )), '''owner''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_claim_research_youtube_ingestion(jsonb)'::regprocedure
  )), '''admin''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_claim_research_youtube_ingestion(jsonb)'::regprocedure
  )), '''producer''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_claim_research_youtube_ingestion(jsonb)'::regprocedure
  )), '''reviewer''') = 0,
  'creator claim requires the exact requester and the owner/admin/producer allowlist'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.claim_research_youtube_ingestion(uuid)'::regprocedure
  )), 'category_binding_stale') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.claim_research_youtube_ingestion(uuid)'::regprocedure
  )), 'rollout_gate_closed') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.claim_research_youtube_ingestion(uuid)'::regprocedure
  )), 'interval ''5 minutes''') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.expire_research_youtube_ingestion(uuid)'::regprocedure
  )), 'no provider retry was attempted') > 0,
  'claim terminalizes stale/gated work and leases expire without retry'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_complete_research_youtube_ingestion(jsonb)'::regprocedure
  )), 'detail_receipt.response_hash <> videos_response_hash_value') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_complete_research_youtube_ingestion(jsonb)'::regprocedure
  )), 'detail_receipt.item_count <> videos_item_count_value') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_complete_research_youtube_ingestion(jsonb)'::regprocedure
  )), 'canary_value ->> ''response_hash'' <> videos_response_hash_value') > 0,
  'videos summary and canary evidence bind to the videos.list receipt'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_begin_research_youtube_transport(jsonb)'::regprocedure
  )), 'global_started_value >= 90') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_begin_research_youtube_transport(jsonb)'::regprocedure
  )), 'organization_started_value >= 20') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_begin_research_youtube_transport(jsonb)'::regprocedure
  )), 'requester_started_value >= 10') > 0,
  'the transport boundary contains global, organization and requester caps'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.research_youtube_retention_ready_pre_analysis_v1()'::regprocedure
  )), 'order by receipt.purged_at desc, receipt.id desc') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_youtube_retention_ready_pre_analysis_v1()'::regprocedure
  )), 'receipt.overdue_remaining_count = 0') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_youtube_retention_ready_pre_analysis_v1()'::regprocedure
  )), 'interval ''2 hours''') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_youtube_retention_ready()'::regprocedure
  )), 'research_youtube_observation_analysis_jobs') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_youtube_retention_ready()'::regprocedure
  )), 'research_youtube_observation_analysis_events') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.research_youtube_retention_ready()'::regprocedure
  )), 'receipt.analysis_accounted') > 0,
  'retention readiness requires the latest zero-backlog heartbeat and no overdue analyses'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.system_purge_expired_youtube_api_data_pre_analysis_v1(jsonb)'::regprocedure
  )), 'delete from content_factory.research_youtube_candidate_decisions') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.system_purge_expired_youtube_api_data_pre_analysis_v1(jsonb)'::regprocedure
  )), 'delete from content_factory.research_youtube_video_observations') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.system_purge_expired_youtube_api_data_pre_analysis_v1(jsonb)'::regprocedure
  )), 'delete from content_factory.research_youtube_transport_receipts') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.system_purge_expired_youtube_api_data_pre_analysis_v1(jsonb)'::regprocedure
  )), 'delete from content_factory.research_youtube_transport_attempts') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_purge_expired_youtube_api_data(jsonb)'::regprocedure
  )), 'research_youtube_observation_analysis_jobs') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_purge_expired_youtube_api_data(jsonb)'::regprocedure
  )), 'research-youtube-retention-receipt-v2') > 0,
  'the physical purge covers analyses, decisions, observations, receipts and attempts'
);

select is(
  (select quota_day
   from content_factory_private.research_youtube_quota_window(
     '2026-03-08 07:59:59+00'::timestamptz
   )),
  '2026-03-07'::date,
  'the instant before the spring boundary remains on the prior Pacific day'
);
select is(
  (select starts_at
   from content_factory_private.research_youtube_quota_window(
     '2026-03-08 08:00:00+00'::timestamptz
   )),
  '2026-03-08 08:00:00+00'::timestamptz,
  'the spring quota day starts at Pacific midnight'
);
select is(
  (select ends_at
   from content_factory_private.research_youtube_quota_window(
     '2026-03-08 08:00:00+00'::timestamptz
   )),
  '2026-03-09 07:00:00+00'::timestamptz,
  'the spring DST quota window is exactly the local 23-hour day'
);
select is(
  (select ends_at - starts_at
   from content_factory_private.research_youtube_quota_window(
     '2026-11-01 07:00:00+00'::timestamptz
   )),
  interval '25 hours',
  'the autumn DST quota window is exactly the local 25-hour day'
);

select is(
  (select count(*)::integer
   from information_schema.columns column_entry
   where column_entry.table_schema = 'content_factory'
     and column_entry.table_name in (
       'research_youtube_video_observations',
       'research_youtube_candidate_decisions'
     )
     and column_entry.column_name = 'candidate_key_hash'),
  0,
  'YouTube observations and decisions expose no generic candidate key'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_research_youtube_status(jsonb)'::regprocedure
  )), 'view_delta') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_youtube_status(jsonb)'::regprocedure
  )), 'like_delta') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_youtube_status(jsonb)'::regprocedure
  )), 'comment_delta') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_youtube_candidate(jsonb)'::regprocedure
  )), 'begin_command') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_decide_research_youtube_candidate(jsonb)'::regprocedure
  )), 'candidate_key') = 0,
  'status has no synthetic deltas and decisions do not use a generic candidate command'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated', fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name), now(), now()
from (values
  ('f6000000-0000-4000-8000-000000000001', 'youtube-owner@example.test', 'YouTube Owner'),
  ('f6000000-0000-4000-8000-000000000002', 'youtube-admin@example.test', 'YouTube Admin'),
  ('f6000000-0000-4000-8000-000000000003', 'youtube-producer@example.test', 'YouTube Producer'),
  ('f6000000-0000-4000-8000-000000000004', 'youtube-reviewer@example.test', 'YouTube Reviewer'),
  ('f6000000-0000-4000-8000-000000000005', 'youtube-other-owner@example.test', 'Other YouTube Owner')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  'f6100000-0000-4000-8000-000000000001',
  'YouTube Ingestion Tenant', 'youtube-ingestion-test', 'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('f6100000-0000-4000-8000-000000000001', 'f6000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('f6100000-0000-4000-8000-000000000001', 'f6000000-0000-4000-8000-000000000002', 'admin', 'active'),
  ('f6100000-0000-4000-8000-000000000001', 'f6000000-0000-4000-8000-000000000003', 'producer', 'active'),
  ('f6100000-0000-4000-8000-000000000001', 'f6000000-0000-4000-8000-000000000004', 'reviewer', 'active'),
  ('f6100000-0000-4000-8000-000000000001', 'f6000000-0000-4000-8000-000000000005', 'owner', 'active');
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values (
  'f6200000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'YOUTUBE-INGESTION-1', 'YouTube Ingestion Product', 'active',
  'f6000000-0000-4000-8000-000000000001'
);
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at,
  created_at, updated_at
)
values (
  'f6300000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6200000-0000-4000-8000-000000000001',
  'f6000000-0000-4000-8000-000000000001',
  'completed', '{"fixture":true}'::jsonb, '{}', repeat('1', 64),
  repeat('2', 64), 'youtube-research-run-fixture', now() - interval '2 hours',
  now() - interval '3 hours', now() - interval '2 hours'
);
insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at
)
values (
  'f6f00000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6300000-0000-4000-8000-000000000001',
  'f6200000-0000-4000-8000-000000000001',
  'f6000000-0000-4000-8000-000000000001',
  'user_input', 'YouTube ingestion fixture source', repeat('f', 64),
  'first_party', '[]'::jsonb,
  '{"model_source_id":"fixture-source"}'::jsonb,
  now() - interval '2 hours'
);
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, created_by, origin, version,
  status, title, brief, source_ids, task_blueprint, content_hash, created_at
)
values (
  'f6400000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6300000-0000-4000-8000-000000000001',
  'f6200000-0000-4000-8000-000000000001',
  'f6000000-0000-4000-8000-000000000001',
  'human', 1, 'draft', 'YouTube ingestion fixture brief', '{}',
  jsonb_build_array('f6f00000-0000-4000-8000-000000000001'::text),
  '[{"title":"Fixture task"}]', repeat('3', 64),
  now() - interval '90 minutes'
);
insert into content_factory.research_market_categories (
  id, organization_id, canonical_name, normalized_name, definition,
  status, created_by
)
values (
  'f6500000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'YouTube fixture category',
  content_factory_private.research_market_identity_key(
    'YouTube fixture category'
  ),
  'A bounded category used only for YouTube live-ingestion tests.',
  'active', 'f6000000-0000-4000-8000-000000000001'
);
insert into content_factory.research_product_market_category_bindings (
  id, organization_id, product_id, category_id, previous_binding_id,
  binding_version, decision_action, source_run_id, source_draft_id,
  candidate_hash, reason, confirmed_by, idempotency_key
)
values
  (
    'f6600000-0000-4000-8000-000000000001',
    'f6100000-0000-4000-8000-000000000001',
    'f6200000-0000-4000-8000-000000000001',
    'f6500000-0000-4000-8000-000000000001', null,
    1, 'create_and_bind', 'f6300000-0000-4000-8000-000000000001',
    'f6400000-0000-4000-8000-000000000001', repeat('4', 64), null,
    'f6000000-0000-4000-8000-000000000001', 'youtube-binding-v1'
  ),
  (
    'f6600000-0000-4000-8000-000000000002',
    'f6100000-0000-4000-8000-000000000001',
    'f6200000-0000-4000-8000-000000000001',
    'f6500000-0000-4000-8000-000000000001',
    'f6600000-0000-4000-8000-000000000001',
    2, 'reclassify', 'f6300000-0000-4000-8000-000000000001',
    'f6400000-0000-4000-8000-000000000001', repeat('5', 64),
    'The exact binding was superseded for stale-claim coverage.',
    'f6000000-0000-4000-8000-000000000001', 'youtube-binding-v2'
  );

create or replace function pg_temp.make_youtube_ingestion(
  ingestion_id_value uuid,
  requester_id_value uuid,
  binding_id_value uuid,
  requested_at_value timestamptz default now()
)
returns void
language plpgsql
set search_path = ''
as $$
declare
  category_id_value uuid;
begin
  select binding.category_id into category_id_value
  from content_factory.research_product_market_category_bindings binding
  where binding.id = binding_id_value;
  insert into content_factory.research_youtube_ingestion_runs (
    id, organization_id, run_id, product_id, binding_id,
    market_category_id, requested_by, mode, status, provider_key,
    adapter_version, query_text, query_hash, max_results,
    max_http_requests, max_quota_units, request_hash, idempotency_key,
    terms_version, no_retry, requested_at
  ) values (
    ingestion_id_value,
    'f6100000-0000-4000-8000-000000000001',
    'f6300000-0000-4000-8000-000000000001',
    'f6200000-0000-4000-8000-000000000001',
    binding_id_value, category_id_value, requester_id_value,
    'manual_canary', 'queued', 'youtube_data_api_v3',
    'youtube-data-api-v3-public-metadata-v1',
    'bounded YouTube fixture query',
    content_factory_private.json_hash(jsonb_build_object(
      'query', ingestion_id_value
    )),
    1, 2, 2,
    content_factory_private.json_hash(jsonb_build_object(
      'request', ingestion_id_value
    )),
    'youtube-ingestion-' || ingestion_id_value::text,
    'youtube-developer-policies-2026-08-03-v1', true,
    requested_at_value
  );
end;
$$;

-- The following seam isolates claim/transport behavior from whether pg_cron is
-- available in a developer test database.  Static assertions above cover the
-- real scheduler and latest-heartbeat definition; ROLLBACK restores it.
create or replace function content_factory_private.research_youtube_retention_ready()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$ select true $$;

select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000001',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002'
);
select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000002',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000001'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select is(
  public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000001'
  )) #>> '{ingestion,error_code}',
  'rollout_gate_closed',
  'a queued current-binding ingestion becomes terminal when the gate is closed'
);
select is(
  public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000002'
  )) #>> '{ingestion,error_code}',
  'category_binding_stale',
  'a queued superseded-binding ingestion becomes terminal before transport'
);
reset role;
select is(
  (select jsonb_build_array(status, error_code)
   from content_factory.research_youtube_ingestion_runs
   where id = 'f6700000-0000-4000-8000-000000000001'),
  '["failed","rollout_gate_closed"]'::jsonb,
  'the gate failure is durable'
);
select is(
  (select jsonb_build_array(status, error_code)
   from content_factory.research_youtube_ingestion_runs
   where id = 'f6700000-0000-4000-8000-000000000002'),
  '["failed","category_binding_stale"]'::jsonb,
  'the stale binding failure is durable'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts
   where ingestion_id in (
     'f6700000-0000-4000-8000-000000000001',
     'f6700000-0000-4000-8000-000000000002'
   )),
  0,
  'stale and gate-closed claims consume no provider transport'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_ingestion_runs
   where id in (
     'f6700000-0000-4000-8000-000000000001',
     'f6700000-0000-4000-8000-000000000002'
   )
     and claimed_at is not null
     and lease_expires_at = claimed_at + interval '5 minutes'
     and completed_at is not null
     and completion_hash ~ '^[0-9a-f]{64}$'),
  2,
  'terminal queued claims retain a complete auditable five-minute lease record'
);

insert into content_factory.research_youtube_global_rollout_decisions (
  provider_key, adapter_version, decision, terms_version,
  terms_review_ack, retention_control_ack, reason, operator_reference,
  decided_at, idempotency_key, decision_hash
)
values (
  'youtube_data_api_v3', 'youtube-data-api-v3-public-metadata-v1',
  'canary_enabled', 'youtube-developer-policies-2026-08-03-v1',
  true, true, 'Enable bounded test canaries after fixture controls.',
  'test:youtube-canary-enabled', now() - interval '1 microsecond',
  'youtube-test-canary-enabled', repeat('6', 64)
);

select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000003',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002'
);
select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000004',
  'f6000000-0000-4000-8000-000000000002',
  'f6600000-0000-4000-8000-000000000002'
);
select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000005',
  'f6000000-0000-4000-8000-000000000003',
  'f6600000-0000-4000-8000-000000000002'
);
select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000006',
  'f6000000-0000-4000-8000-000000000004',
  'f6600000-0000-4000-8000-000000000002'
);
select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000007',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000004', true
  );
end $$;
set local role authenticated;
select throws_ok(
  $$select public.creator_claim_research_youtube_ingestion(
    '{"ingestion_id":"f6700000-0000-4000-8000-000000000006"}'::jsonb
  )$$,
  '42501', 'role_not_allowed',
  'a requester with reviewer role receives zero claim authority'
);
reset role;
select is(
  (select status
   from content_factory.research_youtube_ingestion_runs
   where id = 'f6700000-0000-4000-8000-000000000006'),
  'queued',
  'the reviewer denial leaves the ingestion unclaimed'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts
   where ingestion_id = 'f6700000-0000-4000-8000-000000000006'),
  0,
  'the reviewer denial creates zero provider attempts'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000005', true
  );
end $$;
set local role authenticated;
select throws_ok(
  $$select public.creator_claim_research_youtube_ingestion(
    '{"ingestion_id":"f6700000-0000-4000-8000-000000000007"}'::jsonb
  )$$,
  '42501', 'research_youtube_invoke_not_authorized',
  'a same-organization owner cannot claim another requesters ingestion'
);
reset role;

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select ok(
  (public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000003'
  )) ->> 'invoke_authorized')::boolean,
  'the exact owner requester may claim'
);
reset role;
do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000002', true
  );
end $$;
set local role authenticated;
select ok(
  (public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000004'
  )) ->> 'invoke_authorized')::boolean,
  'the exact admin requester may claim'
);
reset role;
do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000003', true
  );
end $$;
set local role authenticated;
select ok(
  (public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000005'
  )) ->> 'invoke_authorized')::boolean,
  'the exact producer requester may claim'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_youtube_ingestion_runs
   where id in (
     'f6700000-0000-4000-8000-000000000003',
     'f6700000-0000-4000-8000-000000000004',
     'f6700000-0000-4000-8000-000000000005'
   ) and status = 'processing'),
  3,
  'all three allowed requester roles receive processing claims'
);
select is(
  (select lease_expires_at - claimed_at
   from content_factory.research_youtube_ingestion_runs
   where id = 'f6700000-0000-4000-8000-000000000003'),
  interval '5 minutes',
  'a successful claim receives exactly one five-minute lease'
);

update content_factory.research_youtube_ingestion_runs
set claimed_at = clock_timestamp() - interval '10 minutes',
    lease_expires_at = clock_timestamp() - interval '5 minutes'
where id = 'f6700000-0000-4000-8000-000000000003';
do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'f6000000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select is(
  public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000003'
  )) #>> '{ingestion,error_code}',
  'ingestion_lease_expired',
  'an expired creator lease becomes terminal'
);
select is(
  public.creator_claim_research_youtube_ingestion(jsonb_build_object(
    'ingestion_id', 'f6700000-0000-4000-8000-000000000003'
  )) ->> 'claimed',
  'false',
  'a terminal expired ingestion is never claimed again'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts
   where ingestion_id = 'f6700000-0000-4000-8000-000000000003'),
  0,
  'lease expiry performs no provider retry'
);

select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000008',
  'f6000000-0000-4000-8000-000000000003',
  'f6600000-0000-4000-8000-000000000002'
);
update content_factory.research_youtube_ingestion_runs
set status = 'processing',
    claimed_at = clock_timestamp() - interval '10 minutes',
    lease_expires_at = clock_timestamp() - interval '5 minutes'
where id = 'f6700000-0000-4000-8000-000000000008';
do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  (select jsonb_build_array(
      invoked.result ->> 'external_call_allowed',
      invoked.result ->> 'ingestion_status',
      invoked.result ->> 'error_code'
    )
   from (select public.system_begin_research_youtube_transport(
     jsonb_build_object(
       'ingestion_id', 'f6700000-0000-4000-8000-000000000008',
       'request_ordinal', 1,
       'request_kind', 'search.list',
       'quota_bucket', 'search_queries',
       'quota_units', 1,
       'request_hash', repeat('7', 64)
     )
   ) result) invoked),
  '["false","failed","ingestion_lease_expired"]'::jsonb,
  'system begin persists an expired lease and never authorizes an external call'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts
   where ingestion_id = 'f6700000-0000-4000-8000-000000000008'),
  0,
  'the terminal system-begin path creates no retry attempt'
);

select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-000000000009',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002'
);
update content_factory.research_youtube_ingestion_runs
set status = 'completed',
    claimed_at = now() - interval '5 minutes',
    lease_expires_at = now() + interval '5 minutes',
    completed_at = now() - interval '1 minute',
    completion_hash = repeat('7', 64),
    quota_units_started = 2
where id = 'f6700000-0000-4000-8000-000000000009';
insert into content_factory.research_youtube_transport_attempts (
  id, organization_id, ingestion_id, request_ordinal, request_kind,
  quota_bucket, quota_units, request_hash, started_at
)
values (
  'f6800000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-000000000009',
  1, 'search.list', 'search_queries', 1, repeat('7', 64),
  now() - interval '3 minutes'
);
insert into content_factory.research_youtube_transport_receipts (
  id, organization_id, ingestion_id, transport_id, status, response_hash,
  item_count, checked_at, retention_expires_at, receipt_hash
)
values (
  'f6900000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-000000000009',
  'f6800000-0000-4000-8000-000000000001',
  'ready', repeat('7', 64), 1, now() - interval '2 minutes',
  now() - interval '2 minutes' + interval '29 days',
  content_factory_private.json_hash('{"receipt":"global-search"}'::jsonb)
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select throws_ok(
  $$select public.system_decide_research_youtube_global_rollout(
    jsonb_build_object(
      'decision', 'controlled_rollout',
      'terms_version', 'youtube-developer-policies-2026-08-03-v1',
      'terms_review_ack', true,
      'retention_control_ack', true,
      'reason', 'Require both exact canary endpoints before rollout.',
      'operator_reference', 'test:two-endpoint-canary',
      'idempotency_key', 'youtube-controlled-rollout-test'
    )
  )$$,
  '55000', 'research_youtube_global_canary_required',
  'a search-only canary cannot open global controlled rollout'
);
reset role;

insert into content_factory.research_youtube_transport_attempts (
  id, organization_id, ingestion_id, request_ordinal, request_kind,
  quota_bucket, quota_units, request_hash, started_at
)
values (
  'f6800000-0000-4000-8000-000000000002',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-000000000009',
  2, 'videos.list', 'default', 1, repeat('8', 64),
  now() - interval '90 seconds'
);
insert into content_factory.research_youtube_transport_receipts (
  id, organization_id, ingestion_id, transport_id, status, response_hash,
  item_count, checked_at, retention_expires_at, receipt_hash
)
values (
  'f6900000-0000-4000-8000-000000000002',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-000000000009',
  'f6800000-0000-4000-8000-000000000002',
  'ready', repeat('8', 64), 1, now() - interval '1 minute',
  now() - interval '1 minute' + interval '29 days',
  content_factory_private.json_hash('{"receipt":"global-videos"}'::jsonb)
);
do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  public.system_decide_research_youtube_global_rollout(
    jsonb_build_object(
      'decision', 'controlled_rollout',
      'terms_version', 'youtube-developer-policies-2026-08-03-v1',
      'terms_review_ack', true,
      'retention_control_ack', true,
      'reason', 'Require both exact canary endpoints before rollout.',
      'operator_reference', 'test:two-endpoint-canary',
      'idempotency_key', 'youtube-controlled-rollout-test'
    )
  ) ->> 'decision',
  'controlled_rollout',
  'both ready one-item endpoint receipts permit controlled rollout'
);
reset role;
select is(
  content_factory_private.research_youtube_global_state(),
  'controlled_rollout',
  'the successful two-endpoint decision becomes the current global state'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts attempt
   join content_factory.research_youtube_transport_receipts receipt
     on receipt.organization_id = attempt.organization_id
    and receipt.transport_id = attempt.id
    and receipt.status = 'ready'
    and receipt.item_count = 1
   where attempt.ingestion_id = 'f6700000-0000-4000-8000-000000000009'
     and (attempt.request_ordinal, attempt.request_kind) in (
       (1, 'search.list'), (2, 'videos.list')
     )),
  2,
  'the rollout canary has exactly two ready endpoint receipts'
);
select is(
  (select jsonb_build_array(max_results, max_http_requests, max_quota_units)
   from content_factory.research_youtube_ingestion_runs
   where id = 'f6700000-0000-4000-8000-000000000009'),
  '[1,2,2]'::jsonb,
  'the rollout canary uses the exact 1/2/2 plan'
);

select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-00000000000a',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002'
);
update content_factory.research_youtube_ingestion_runs
set status = 'processing',
    claimed_at = now() - interval '1 minute',
    lease_expires_at = now() + interval '4 minutes',
    quota_units_started = 2
where id = 'f6700000-0000-4000-8000-00000000000a';
insert into content_factory.research_youtube_transport_attempts (
  id, organization_id, ingestion_id, request_ordinal, request_kind,
  quota_bucket, quota_units, request_hash, started_at
)
values
  (
    'f6800000-0000-4000-8000-00000000000a',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000a',
    1, 'search.list', 'search_queries', 1, repeat('b', 64),
    now() - interval '50 seconds'
  ),
  (
    'f6800000-0000-4000-8000-00000000000b',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000a',
    2, 'videos.list', 'default', 1, repeat('c', 64),
    now() - interval '40 seconds'
  );
insert into content_factory.research_youtube_transport_receipts (
  id, organization_id, ingestion_id, transport_id, status, response_hash,
  item_count, checked_at, retention_expires_at, receipt_hash
)
values
  (
    'f6900000-0000-4000-8000-00000000000a',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000a',
    'f6800000-0000-4000-8000-00000000000a',
    'ready', repeat('b', 64), 1, now() - interval '30 seconds',
    now() - interval '30 seconds' + interval '29 days',
    content_factory_private.json_hash('{"receipt":"completion-search"}'::jsonb)
  ),
  (
    'f6900000-0000-4000-8000-00000000000b',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000a',
    'f6800000-0000-4000-8000-00000000000b',
    'ready', repeat('c', 64), 1, now() - interval '20 seconds',
    now() - interval '20 seconds' + interval '29 days',
    content_factory_private.json_hash('{"receipt":"completion-videos"}'::jsonb)
  );

create or replace function pg_temp.complete_youtube_canary(
  videos_hash_value text
)
returns jsonb
language sql
set search_path = ''
as $$
  select public.system_complete_research_youtube_ingestion(
    jsonb_build_object(
      'version', 'research-youtube-live-ingestion-v1',
      'ingestion_id', 'f6700000-0000-4000-8000-00000000000a',
      'status', 'completed',
      'provider_key', 'youtube_data_api_v3',
      'adapter_version', 'youtube-data-api-v3-public-metadata-v1',
      'observed_at', now(),
      'search', jsonb_build_object(
        'response_hash', repeat('b', 64), 'item_count', 1
      ),
      'videos', jsonb_build_object(
        'response_hash', videos_hash_value, 'item_count', 1
      ),
      'canary', jsonb_build_object(
        'request_kind', 'videos.list',
        'response_hash', videos_hash_value,
        'item_count', 1,
        -- now() is transaction-stable and exactly matches the seeded receipt.
        -- Keep the invoker helper from reading the private ledger directly:
        -- service_role must reach it only through the SECURITY DEFINER RPC.
        'checked_at', now() - interval '20 seconds'
      ),
      'observations', '[]'::jsonb
    )
  );
$$;

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select throws_ok(
  $$select pg_temp.complete_youtube_canary(repeat('b', 64))$$,
  '55000', 'research_youtube_video_receipt_mismatch',
  'a videos summary cannot substitute the search response hash'
);
select is(
  pg_temp.complete_youtube_canary(repeat('c', 64))
    #>> '{ingestion,status}',
  'completed'::text,
  'the exact videos receipt hash completes the canary'::text
);
select throws_ok(
  $$select pg_temp.complete_youtube_canary(repeat('d', 64))$$,
  '55000', 'research_youtube_video_receipt_mismatch',
  'a completed replay revalidates and rejects a changed videos hash'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_youtube_video_observations
   where ingestion_id = 'f6700000-0000-4000-8000-00000000000a'),
  0,
  'the exact manual canary persists no candidate observation'
);

insert into content_factory.research_youtube_retention_receipts (
  id, purged_at, cutoff_at, observation_deleted_count,
  candidate_decision_deleted_count, transport_receipt_deleted_count,
  transport_attempt_deleted_count, overdue_remaining_count, successful,
  receipt_hash
) values (
  'f6e00000-0000-4000-8000-000000000001',
  now() - interval '3 hours', now() - interval '3 hours',
  0, 0, 0, 0, 0, true,
  content_factory_private.json_hash(
    '{"fixture":"unfinalized-retention-receipt"}'::jsonb
  )
);
select throws_ok(
  $$
    update content_factory.research_youtube_retention_receipts
    set analysis_event_deleted_count = 0,
        analysis_job_deleted_count = 0,
        analysis_overdue_remaining_count = 0,
        analysis_accounted = true,
        overdue_remaining_count = 0,
        receipt_hash = content_factory_private.json_hash(
          '{"fixture":"forbidden-unflagged-finalization"}'::jsonb
        )
    where id = 'f6e00000-0000-4000-8000-000000000001'
  $$,
  '55000',
  'research_youtube_retention_receipts_append_only',
  'an unset purge GUC fails closed for an otherwise valid receipt finalization'
);

select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-00000000000b',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002',
  now() - interval '31 days'
);
update content_factory.research_youtube_ingestion_runs
set status = 'completed',
    claimed_at = now() - interval '30 days',
    lease_expires_at = now() - interval '30 days' + interval '5 minutes',
    completed_at = now() - interval '30 days' + interval '1 minute',
    completion_hash = repeat('e', 64),
    quota_units_started = 2
where id = 'f6700000-0000-4000-8000-00000000000b';
insert into content_factory.research_youtube_transport_attempts (
  id, organization_id, ingestion_id, request_ordinal, request_kind,
  quota_bucket, quota_units, request_hash, started_at
)
values
  (
    'f6800000-0000-4000-8000-00000000000c',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000b',
    1, 'search.list', 'search_queries', 1, repeat('d', 64),
    now() - interval '30 days'
  ),
  (
    'f6800000-0000-4000-8000-00000000000d',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000b',
    2, 'videos.list', 'default', 1, repeat('e', 64),
    now() - interval '30 days'
  );
insert into content_factory.research_youtube_transport_receipts (
  id, organization_id, ingestion_id, transport_id, status, response_hash,
  item_count, checked_at, retention_expires_at, receipt_hash
)
values
  (
    'f6900000-0000-4000-8000-00000000000c',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000b',
    'f6800000-0000-4000-8000-00000000000c',
    'ready', repeat('d', 64), 1, now() - interval '30 days',
    now() - interval '1 day',
    content_factory_private.json_hash('{"receipt":"expired-search"}'::jsonb)
  ),
  (
    'f6900000-0000-4000-8000-00000000000d',
    'f6100000-0000-4000-8000-000000000001',
    'f6700000-0000-4000-8000-00000000000b',
    'f6800000-0000-4000-8000-00000000000d',
    'ready', repeat('e', 64), 1, now() - interval '30 days',
    now() - interval '1 day',
    content_factory_private.json_hash('{"receipt":"expired-videos"}'::jsonb)
  );
insert into content_factory.research_youtube_video_observations (
  id, organization_id, ingestion_id, product_id, binding_id,
  market_category_id, search_position, video_id, channel_id, title,
  channel_title, youtube_category_id, published_at, duration_iso8601,
  privacy_status, embeddable, view_count, like_count, comment_count,
  observed_at, retention_expires_at, observation_hash
)
values (
  'f6a00000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-00000000000b',
  'f6200000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002',
  'f6500000-0000-4000-8000-000000000001',
  1, 'AbCdEf12345', 'UC' || repeat('A', 22),
  'Expired public video fixture', 'Fixture channel', '22',
  now() - interval '60 days', 'PT30S', 'public', true,
  '100', '10', '1', now() - interval '30 days',
  now() - interval '1 day', repeat('f', 64)
);
insert into content_factory.research_youtube_candidate_decisions (
  id, organization_id, ingestion_id, observation_id, observation_hash,
  decision, reason, decided_by, decided_at, retention_expires_at,
  idempotency_key, decision_hash
)
values (
  'f6b00000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-00000000000b',
  'f6a00000-0000-4000-8000-000000000001', repeat('f', 64),
  'exclude_candidate', 'Expired fixture decision for physical purge.',
  'f6000000-0000-4000-8000-000000000001',
  now() - interval '30 days', now() - interval '1 day',
  'youtube-expired-decision',
  content_factory_private.json_hash('{"decision":"expired"}'::jsonb)
);
insert into content_factory.research_youtube_observation_analysis_jobs (
  id, organization_id, ingestion_id, parser_key, parser_version, status,
  input_hash, attempt_count, parsed_count, claimed_at, completed_at,
  retention_expires_at, job_hash, created_at
) values (
  'f6c00000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6700000-0000-4000-8000-00000000000b',
  'youtube_observation_deterministic', '1.0.0', 'completed',
  content_factory_private.research_youtube_analysis_input_hash(
    'f6700000-0000-4000-8000-00000000000b'
  ),
  1, 1, now() - interval '2 days', now() - interval '2 days' + interval '1 minute',
  now() - interval '1 day',
  content_factory_private.json_hash(
    '{"fixture":"expired-analysis-job"}'::jsonb
  ),
  now() - interval '2 days'
);
insert into content_factory.research_youtube_observation_analysis_events (
  id, organization_id, observation_id, observation_hash, analysis_version,
  parent_event_id, expected_parent_hash, origin, actor_id, parser_key,
  parser_version, analysis, correction_reason, request_hash, event_hash,
  idempotency_key, retention_expires_at, created_at
) values (
  'f6d00000-0000-4000-8000-000000000001',
  'f6100000-0000-4000-8000-000000000001',
  'f6a00000-0000-4000-8000-000000000001', repeat('f', 64), 1,
  null, null, 'system_parser', null,
  'youtube_observation_deterministic', '1.0.0',
  content_factory_private.research_youtube_observation_analysis_payload(
    'f6a00000-0000-4000-8000-000000000001'
  ),
  null,
  content_factory_private.json_hash(
    '{"fixture":"expired-analysis-request"}'::jsonb
  ),
  content_factory_private.json_hash(
    '{"fixture":"expired-analysis-event"}'::jsonb
  ),
  'youtube-expired-analysis-event', now() - interval '1 day',
  now() - interval '2 days'
);
select pg_temp.make_youtube_ingestion(
  'f6700000-0000-4000-8000-00000000000c',
  'f6000000-0000-4000-8000-000000000001',
  'f6600000-0000-4000-8000-000000000002',
  now() - interval '1 hour'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
do $$
declare
  result_value jsonb;
begin
  result_value := public.system_purge_expired_youtube_api_data(
    '{"limit":1}'::jsonb
  );
  perform set_config(
    'content_factory.youtube_test_first_combined_purge',
    result_value::text,
    true
  );
end
$$;
select ok(
  (
    current_setting(
      'content_factory.youtube_test_first_combined_purge'
    )::jsonb ->> 'overdue_remaining_count'
  )::integer > 0,
  'a limit-one purge heartbeat reports the remaining overdue backlog'
);
reset role;
select is(
  (
    with invoked as (
      select current_setting(
        'content_factory.youtube_test_first_combined_purge'
      )::jsonb result
    ), receipt as (
      select stored.*
      from content_factory.research_youtube_retention_receipts stored
      cross join invoked
      where stored.id = (invoked.result ->> 'receipt_id')::uuid
    )
    select jsonb_build_array(
      receipt.analysis_event_deleted_count,
      receipt.analysis_job_deleted_count,
      receipt.analysis_overdue_remaining_count,
      receipt.analysis_accounted,
      receipt.receipt_hash = invoked.result ->> 'receipt_hash',
      receipt.receipt_hash = content_factory_private.json_hash(
        jsonb_build_object(
          'version', 'research-youtube-retention-receipt-v2',
          'cutoff_at', receipt.cutoff_at,
          'observation_deleted_count', receipt.observation_deleted_count,
          'candidate_decision_deleted_count',
            receipt.candidate_decision_deleted_count,
          'transport_receipt_deleted_count',
            receipt.transport_receipt_deleted_count,
          'transport_attempt_deleted_count',
            receipt.transport_attempt_deleted_count,
          'analysis_event_deleted_count',
            receipt.analysis_event_deleted_count,
          'analysis_job_deleted_count', receipt.analysis_job_deleted_count,
          'analysis_overdue_remaining_count',
            receipt.analysis_overdue_remaining_count,
          'overdue_remaining_count', receipt.overdue_remaining_count,
          'successful', receipt.successful,
          'analysis_accounted', receipt.analysis_accounted
        )
      )
    )
    from invoked
    cross join receipt
  ),
  '[1,1,0,true,true,true]'::jsonb,
  'the combined receipt exactly hashes its analysis deletions and remaining backlog'
);
set local role service_role;
select is(
  public.system_purge_expired_youtube_api_data(
    '{"limit":5000}'::jsonb
  ) ->> 'overdue_remaining_count',
  '0',
  'the follow-up purge clears the full overdue backlog'
);
select is(
  (with invoked as materialized (
     select public.system_purge_expired_youtube_api_data(
       '{"limit":5000}'::jsonb
     ) result
   )
   select jsonb_build_array(
     invoked.result ->> 'observation_deleted_count',
     invoked.result ->> 'candidate_decision_deleted_count',
     invoked.result ->> 'transport_receipt_deleted_count',
     invoked.result ->> 'transport_attempt_deleted_count',
     invoked.result ->> 'analysis_event_deleted_count',
     invoked.result ->> 'analysis_job_deleted_count',
     invoked.result ->> 'analysis_overdue_remaining_count',
     invoked.result ->> 'overdue_remaining_count',
     invoked.result ->> 'version',
     (invoked.result ->> 'analysis_accounted')::boolean,
     (invoked.result ->> 'receipt_hash') ~ '^[0-9a-f]{64}$',
     set_config(
       'content_factory.youtube_test_zero_receipt_id',
       invoked.result ->> 'receipt_id', true
     ) is not null
   )
   from invoked),
  '["0","0","0","0","0","0","0","0","research-youtube-retention-v2",true,true,true]'::jsonb,
  'an empty purge returns one finalized v2 receipt for legacy and analysis data'
);
reset role;
select is(
  (select jsonb_build_array(
      observation_deleted_count,
      candidate_decision_deleted_count,
      transport_receipt_deleted_count,
      transport_attempt_deleted_count,
      analysis_event_deleted_count,
      analysis_job_deleted_count,
      analysis_overdue_remaining_count,
      overdue_remaining_count,
      successful,
      analysis_accounted,
      receipt_hash ~ '^[0-9a-f]{64}$'
    )
   from content_factory.research_youtube_retention_receipts
   where id = current_setting(
     'content_factory.youtube_test_zero_receipt_id', true
   )::uuid),
  '[0,0,0,0,0,0,0,0,true,true,true]'::jsonb,
  'the returned receipt immutably accounts for the complete purge surface'
);
select throws_ok(
  format(
    'update content_factory.research_youtube_retention_receipts '
      || 'set analysis_event_deleted_count = 1 where id = %L::uuid',
    current_setting('content_factory.youtube_test_zero_receipt_id', true)
  ),
  '55000',
  'research_youtube_retention_receipts_append_only',
  'a finalized combined retention receipt cannot be rewritten'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_candidate_decisions
   where ingestion_id = 'f6700000-0000-4000-8000-00000000000b'),
  0,
  'expired candidate decisions are physically purged'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_video_observations
   where ingestion_id = 'f6700000-0000-4000-8000-00000000000b'),
  0,
  'expired video observations are physically purged'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_receipts
   where ingestion_id = 'f6700000-0000-4000-8000-00000000000b'),
  0,
  'expired transport receipts are physically purged'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts
   where ingestion_id = 'f6700000-0000-4000-8000-00000000000b'),
  0,
  'expired transport attempts are physically purged'
);
select is(
  (select jsonb_build_array(status, error_code)
   from content_factory.research_youtube_ingestion_runs
   where id = 'f6700000-0000-4000-8000-00000000000c'),
  '["failed","ingestion_lease_expired"]'::jsonb,
  'retention sweeping also terminalizes abandoned queued work without retry'
);

select * from finish();
rollback;

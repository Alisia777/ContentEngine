begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select plan(48);

-- This fixture exercises the automatic path without contacting YouTube.  The
-- two recorded transport receipts are bounded provider observations, not raw
-- provider responses.  ROLLBACK restores the production retention function.
create or replace function content_factory_private.research_youtube_retention_ready()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$ select true $$;

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'aa100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'youtube-automatic-integration@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"YouTube Automatic Integration Owner"}'::jsonb,
  now(), now()
);
insert into content_factory.organizations (id, name, slug, status)
values (
  'aa110000-0000-4000-8000-000000000001',
  'YouTube Automatic Integration', 'youtube-automatic-integration', 'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'aa110000-0000-4000-8000-000000000001',
  'aa100000-0000-4000-8000-000000000001', 'owner', 'active'
);
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'aa120000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'YOUTUBE-AUTO-INTEGRATION', 'YouTube Automatic Integration Product',
  'active', 'aa100000-0000-4000-8000-000000000001'
);
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at,
  created_at, updated_at
) values (
  'aa130000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'aa120000-0000-4000-8000-000000000001',
  'aa100000-0000-4000-8000-000000000001',
  'completed', '{"fixture":true}'::jsonb, '{}'::jsonb,
  repeat('1', 64), repeat('2', 64),
  'youtube-automatic-integration-run', now() - interval '2 hours',
  now() - interval '3 hours', now() - interval '2 hours'
);
insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at
) values (
  'aa1f0000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'aa130000-0000-4000-8000-000000000001',
  'aa120000-0000-4000-8000-000000000001',
  'aa100000-0000-4000-8000-000000000001',
  'user_input', 'YouTube automatic integration fixture source',
  repeat('3', 64), 'first_party', '[]'::jsonb,
  '{"model_source_id":"youtube-auto-fixture"}'::jsonb,
  now() - interval '2 hours'
);
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, created_by, origin, version,
  status, title, brief, source_ids, task_blueprint, content_hash, created_at
) values (
  'aa140000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'aa130000-0000-4000-8000-000000000001',
  'aa120000-0000-4000-8000-000000000001',
  'aa100000-0000-4000-8000-000000000001',
  'human', 1, 'draft', 'YouTube automatic integration fixture brief',
  '{}'::jsonb,
  jsonb_build_array('aa1f0000-0000-4000-8000-000000000001'::text),
  '[{"title":"Exercise automatic YouTube collection"}]'::jsonb,
  repeat('4', 64), now() - interval '90 minutes'
);
insert into content_factory.research_market_categories (
  id, organization_id, canonical_name, normalized_name, definition,
  status, created_by
) values (
  'aa150000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'Automatic YouTube integration category',
  content_factory_private.research_market_identity_key(
    'Automatic YouTube integration category'
  ),
  'A bounded category used to prove automatic YouTube evidence collection.',
  'active', 'aa100000-0000-4000-8000-000000000001'
);
insert into content_factory.research_product_market_category_bindings (
  id, organization_id, product_id, category_id, previous_binding_id,
  binding_version, decision_action, source_run_id, source_draft_id,
  candidate_hash, reason, confirmed_by, idempotency_key
) values (
  'aa160000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'aa120000-0000-4000-8000-000000000001',
  'aa150000-0000-4000-8000-000000000001', null,
  1, 'create_and_bind', 'aa130000-0000-4000-8000-000000000001',
  'aa140000-0000-4000-8000-000000000001', repeat('5', 64), null,
  'aa100000-0000-4000-8000-000000000001',
  'youtube-automatic-integration-binding'
);

-- A fresh completed 1/2/2 canary is the audited prerequisite for the global
-- and tenant rollout RPCs.  It has no observations and is excluded from the
-- readiness delta measured below.
insert into content_factory.research_youtube_ingestion_runs (
  id, organization_id, run_id, product_id, binding_id, market_category_id,
  requested_by, mode, status, provider_key, adapter_version, query_text,
  query_hash, max_results, max_http_requests, max_quota_units,
  quota_units_started, request_hash, idempotency_key, terms_version, no_retry,
  requested_at, claimed_at, lease_expires_at, completed_at, completion_hash
) values (
  'aa170000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'aa130000-0000-4000-8000-000000000001',
  'aa120000-0000-4000-8000-000000000001',
  'aa160000-0000-4000-8000-000000000001',
  'aa150000-0000-4000-8000-000000000001',
  'aa100000-0000-4000-8000-000000000001',
  'manual_canary', 'completed', 'youtube_data_api_v3',
  'youtube-data-api-v3-public-metadata-v1', 'automatic integration canary',
  repeat('6', 64), 1, 2, 2, 2, repeat('7', 64),
  'youtube-automatic-integration-canary',
  'youtube-developer-policies-2026-08-03-v1', true,
  now() - interval '6 minutes', now() - interval '5 minutes',
  now(), now() - interval '3 minutes', repeat('8', 64)
);
insert into content_factory.research_youtube_transport_attempts (
  id, organization_id, ingestion_id, request_ordinal, request_kind,
  quota_bucket, quota_units, request_hash, started_at
) values
  (
    'aa180000-0000-4000-8000-000000000001',
    'aa110000-0000-4000-8000-000000000001',
    'aa170000-0000-4000-8000-000000000001',
    1, 'search.list', 'search_queries', 1, repeat('9', 64),
    now() - interval '4 minutes'
  ),
  (
    'aa180000-0000-4000-8000-000000000002',
    'aa110000-0000-4000-8000-000000000001',
    'aa170000-0000-4000-8000-000000000001',
    2, 'videos.list', 'default', 1, repeat('a', 64),
    now() - interval '210 seconds'
  );
insert into content_factory.research_youtube_transport_receipts (
  id, organization_id, ingestion_id, transport_id, status, response_hash,
  item_count, checked_at, retention_expires_at, receipt_hash
) values
  (
    'aa190000-0000-4000-8000-000000000001',
    'aa110000-0000-4000-8000-000000000001',
    'aa170000-0000-4000-8000-000000000001',
    'aa180000-0000-4000-8000-000000000001',
    'ready', repeat('b', 64), 1, now() - interval '220 seconds',
    now() - interval '220 seconds' + interval '29 days', repeat('c', 64)
  ),
  (
    'aa190000-0000-4000-8000-000000000002',
    'aa110000-0000-4000-8000-000000000001',
    'aa170000-0000-4000-8000-000000000001',
    'aa180000-0000-4000-8000-000000000002',
    'ready', repeat('d', 64), 1, now() - interval '200 seconds',
    now() - interval '200 seconds' + interval '29 days', repeat('e', 64)
  );

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  public.system_decide_research_youtube_global_rollout(jsonb_build_object(
    'decision', 'controlled_rollout',
    'terms_version', 'youtube-developer-policies-2026-08-03-v1',
    'terms_review_ack', true,
    'retention_control_ack', true,
    'reason', 'Open the automatic integration fixture after a bounded canary.',
    'operator_reference', 'test:youtube-automatic-integration',
    'idempotency_key', 'youtube-automatic-global-rollout'
  )) ->> 'decision',
  'controlled_rollout',
  'the real global rollout RPC accepts the fresh two-endpoint canary'
);
reset role;

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'aa100000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select is(
  public.creator_decide_research_youtube_rollout(jsonb_build_object(
    'organization_id', 'aa110000-0000-4000-8000-000000000001',
    'decision', 'enable_category_refresh',
    'canary_ingestion_id', 'aa170000-0000-4000-8000-000000000001',
    'reason', 'Enable the bounded automatic integration fixture.',
    'terms_ack', true,
    'terms_version', 'youtube-developer-policies-2026-08-03-v1',
    'idempotency_key', 'youtube-automatic-tenant-rollout'
  )) #>> '{rollout,decision}',
  'enable_category_refresh',
  'the real tenant rollout RPC opens category refresh for this organization'
);
select is(
  public.creator_configure_research_source_collection_policy(
    jsonb_build_object(
      'organization_id', 'aa110000-0000-4000-8000-000000000001',
      'run_id', 'aa130000-0000-4000-8000-000000000001',
      'platform', 'youtube',
      'provider_key', 'youtube_data_api_v3',
      'status', 'enabled',
      'automatic_collection_ack', true,
      'terms_version', 'youtube-developer-policies-2026-08-03-v1',
      'terms_ack', true,
      'quota_ack', true,
      'no_retry_ack', true,
      'cadence_hours', 24,
      'max_records', 2,
      'monthly_hard_budget_units', 10,
      'legal_review_reference', 'test:recorded-fixture-review',
      'reason', 'Exercise one bounded automatic collection cycle.',
      'idempotency_key', 'youtube-automatic-policy-enable'
    )
  ) #>> '{policy,status}',
  'enabled',
  'an acknowledged YouTube policy enables automatic enqueue without transport'
);
select throws_ok(
  $instagram_enable$
    select public.creator_configure_research_source_collection_policy(
      jsonb_build_object(
        'organization_id', 'aa110000-0000-4000-8000-000000000001',
        'run_id', 'aa130000-0000-4000-8000-000000000001',
        'platform', 'instagram',
        'provider_key', 'bright_data',
        'status', 'enabled',
        'automatic_collection_ack', true,
        'terms_version', 'bright-data-review-required-v1',
        'terms_ack', true,
        'quota_ack', true,
        'no_retry_ack', true,
        'cadence_hours', 24,
        'max_records', 2,
        'monthly_hard_budget_units', 10,
        'legal_review_reference', 'test:instagram-legal-not-approved',
        'reason', 'Instagram must remain fail closed.',
        'idempotency_key', 'youtube-auto-instagram-enable'
      )
    )
  $instagram_enable$,
  '55000', 'research_instagram_provider_legal_choice_required',
  'Instagram automatic enablement fails closed before any policy is persisted'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_source_collection_policies policy
   where policy.organization_id = 'aa110000-0000-4000-8000-000000000001'
     and policy.platform = 'instagram'),
  0,
  'the rejected Instagram enablement leaves no policy history'
);

create temporary table automatic_readiness_before on commit drop as
select content_factory_private.research_category_evidence_readiness(
  'aa110000-0000-4000-8000-000000000001',
  'aa150000-0000-4000-8000-000000000001',
  clock_timestamp()
) value;

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  (
    with invoked as materialized (
      select public.system_claim_due_research_youtube_collection(
        jsonb_build_object('limit', 1)
      ) result
    )
    select jsonb_build_array(
      (result ->> 'selected')::integer,
      (result ->> 'claimed')::integer,
      (result ->> 'expired')::integer,
      result #>> '{items,0,status}',
      result #>> '{items,0,mode}',
      (result ->> 'external_call_started')::boolean,
      (result ->> 'automatic_retry_started')::boolean,
      set_config(
        'content_factory.test_auto_ingestion_id',
        result #>> '{items,0,ingestion_id}', true
      ) is not null
    )
    from invoked
  ),
  '[1,1,0,"processing","category_refresh",false,false,true]'::jsonb,
  'the first automatic scheduler tick proposes and claims exactly one ingestion'
);
select is(
  (
    select jsonb_build_array(
      (result ->> 'automatic_dispatch_authorized')::boolean,
      result #>> '{ingestion,status}',
      result #>> '{ingestion,mode}',
      result #>> '{ingestion,provider_key}',
      (result #>> '{ingestion,max_http_requests}')::integer,
      (result #>> '{ingestion,max_quota_units}')::integer
    )
    from (
      select public.system_read_automatic_research_youtube_ingestion(
        jsonb_build_object(
          'ingestion_id', current_setting(
            'content_factory.test_auto_ingestion_id'
          )
        )
      ) result
    ) invoked
  ),
  '[true,"processing","category_refresh","youtube_data_api_v3",2,2]'::jsonb,
  'the automatic reader exposes only the claimed bounded ingestion contract'
);
select is(
  (
    with invoked as materialized (
      select public.system_begin_automatic_research_youtube_transport(
        jsonb_build_object(
          'ingestion_id', current_setting(
            'content_factory.test_auto_ingestion_id'
          ),
          'request_ordinal', 1,
          'request_kind', 'search.list',
          'quota_bucket', 'search_queries',
          'quota_units', 1,
          'request_hash', repeat('a', 64)
        )
      ) result
    )
    select jsonb_build_array(
      (result ->> 'external_call_allowed')::boolean,
      result ->> 'request_kind',
      set_config(
        'content_factory.test_auto_search_transport_id',
        result ->> 'transport_id', true
      ) is not null
    )
    from invoked
  ),
  '[true,"search.list",true]'::jsonb,
  'the automatic wrapper authorizes the first and only search transport'
);
select ok(
  (
    public.system_record_research_youtube_transport(jsonb_build_object(
      'transport_id', current_setting(
        'content_factory.test_auto_search_transport_id'
      ),
      'status', 'ready',
      'failure_code', null,
      'response_hash', repeat('b', 64),
      'item_count', 2,
      'checked_at', clock_timestamp()
    )) ->> 'ok'
  )::boolean,
  'the search endpoint stores one sanitized ready receipt'
);
select is(
  (
    with invoked as materialized (
      select public.system_begin_automatic_research_youtube_transport(
        jsonb_build_object(
          'ingestion_id', current_setting(
            'content_factory.test_auto_ingestion_id'
          ),
          'request_ordinal', 2,
          'request_kind', 'videos.list',
          'quota_bucket', 'default',
          'quota_units', 1,
          'request_hash', repeat('c', 64)
        )
      ) result
    )
    select jsonb_build_array(
      (result ->> 'external_call_allowed')::boolean,
      result ->> 'request_kind',
      set_config(
        'content_factory.test_auto_videos_transport_id',
        result ->> 'transport_id', true
      ) is not null
    )
    from invoked
  ),
  '[true,"videos.list",true]'::jsonb,
  'the ready search receipt authorizes the one videos transport'
);
do $$ begin
  perform set_config(
    'content_factory.test_auto_observed_at',
    clock_timestamp()::text, true
  );
end $$;
select ok(
  (
    public.system_record_research_youtube_transport(jsonb_build_object(
      'transport_id', current_setting(
        'content_factory.test_auto_videos_transport_id'
      ),
      'status', 'ready',
      'failure_code', null,
      'response_hash', repeat('d', 64),
      'item_count', 2,
      'checked_at', current_setting(
        'content_factory.test_auto_observed_at'
      )
    )) ->> 'ok'
  )::boolean,
  'the videos endpoint stores one sanitized ready receipt'
);
select is(
  public.system_complete_research_youtube_ingestion(jsonb_build_object(
    'version', 'research-youtube-live-ingestion-v1',
    'ingestion_id', current_setting(
      'content_factory.test_auto_ingestion_id'
    ),
    'status', 'completed',
    'provider_key', 'youtube_data_api_v3',
    'adapter_version', 'youtube-data-api-v3-public-metadata-v1',
    'observed_at', current_setting('content_factory.test_auto_observed_at'),
    'search', jsonb_build_object(
      'response_hash', repeat('b', 64), 'item_count', 2
    ),
    'videos', jsonb_build_object(
      'response_hash', repeat('d', 64), 'item_count', 2
    ),
    'observations', jsonb_build_array(
      jsonb_build_object(
        'search_position', 1,
        'video_id', 'AutoVid0001',
        'channel_id', 'UC' || repeat('A', 22),
        'title', 'Recorded comparison format signal',
        'channel_title', 'Recorded Channel A',
        'youtube_category_id', '22',
        'published_at', (
          current_setting('content_factory.test_auto_observed_at')::timestamptz
            - interval '2 days'
        ),
        'duration_iso8601', 'PT30S',
        'privacy_status', 'public',
        'embeddable', true,
        'view_count', '1200',
        'like_count', '80',
        'comment_count', '9',
        'observed_at', current_setting(
          'content_factory.test_auto_observed_at'
        ),
        'retention_expires_at', (
          current_setting('content_factory.test_auto_observed_at')::timestamptz
            + interval '29 days'
        )
      ),
      jsonb_build_object(
        'search_position', 2,
        'video_id', 'AutoVid0002',
        'channel_id', 'UC' || repeat('B', 22),
        'title', 'Recorded short demonstration signal',
        'channel_title', 'Recorded Channel B',
        'youtube_category_id', '22',
        'published_at', (
          current_setting('content_factory.test_auto_observed_at')::timestamptz
            - interval '3 days'
        ),
        'duration_iso8601', 'PT45S',
        'privacy_status', 'public',
        'embeddable', true,
        'view_count', '900',
        'like_count', null,
        'comment_count', null,
        'observed_at', current_setting(
          'content_factory.test_auto_observed_at'
        ),
        'retention_expires_at', (
          current_setting('content_factory.test_auto_observed_at')::timestamptz
            + interval '29 days'
        )
      )
    )
  )) #>> '{ingestion,status}',
  'completed',
  'the real completion RPC persists both recorded observations'
);
reset role;

select is(
  (select count(*)::integer
   from content_factory.research_youtube_transport_attempts attempt
   join content_factory.research_youtube_transport_receipts receipt
     on receipt.organization_id = attempt.organization_id
    and receipt.transport_id = attempt.id
    and receipt.status = 'ready'
   where attempt.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  2,
  'the automatic ingestion has exactly two ready recorded receipts'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_video_observations observation
   where observation.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  2,
  'the automatic ingestion retains exactly two bounded observations'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_video_observations observation
   where observation.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid
     and to_jsonb(observation) ?| array[
       'description', 'captions', 'transcript', 'tags', 'raw_response'
     ]),
  0,
  'recorded observations contain no description, caption, transcript, tag or raw payload'
);
select is(
  (select jsonb_build_array(
     count(*)::integer,
     min(job.status),
     min(job.attempt_count),
     bool_and(job.no_retry),
     bool_or(job.external_call_started),
     min(job.parsed_count)
   )
   from content_factory.research_youtube_observation_analysis_jobs job
   where job.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  '[1,"approval_required",0,true,false,0]'::jsonb,
  'completion creates local analysis work but keeps it approval-gated'
);

create temporary table automatic_readiness_before_parser on commit drop as
select content_factory_private.research_category_evidence_readiness(
  'aa110000-0000-4000-8000-000000000001',
  'aa150000-0000-4000-8000-000000000001',
  clock_timestamp()
) value;

select is(
  (
    select (dimension ->> 'current')::integer
    from jsonb_array_elements(
      (select value -> 'dimensions' from automatic_readiness_before_parser)
    ) dimension
    where dimension ->> 'key' = 'analysis_coverage'
  ),
  (
    select (dimension ->> 'current')::integer
    from jsonb_array_elements(
      (select value -> 'dimensions' from automatic_readiness_before)
    ) dimension
    where dimension ->> 'key' = 'analysis_coverage'
  ),
  'retained metadata alone does not increase structured analysis coverage'
);

create temporary table automatic_source_ledger_before_parser on commit drop as
select count(*)::integer value
from content_factory.research_category_source_ledger ledger
where ledger.organization_id = 'aa110000-0000-4000-8000-000000000001'
  and ledger.market_category_id = 'aa150000-0000-4000-8000-000000000001';

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  (with processed as materialized (
     select public.system_process_due_research_youtube_observation_analysis(
       jsonb_build_object('limit', 1)
     ) result
   )
   select jsonb_build_array(
     (result ->> 'selected')::integer,
     (result ->> 'completed')::integer,
     (result ->> 'failed')::integer,
     (result ->> 'external_call_started')::boolean,
     (result ->> 'provider_attempt_count')::integer
   )
   from processed),
  '[0,0,0,false,0]'::jsonb,
  'derived analysis stays stopped before audited analytics approval'
);
select is(
  (with decided as materialized (
     select public.system_decide_research_youtube_derived_analysis(
       jsonb_build_object(
         'decision', 'approved',
         'terms_version',
           'youtube-derived-metrics-policy-2026-06-01-v1',
         'terms_review_ack', true,
         'analytics_amendment_ack', true,
         'approval_reference', 'YT-ANALYTICS-AUDIT-TEST-001',
         'reason', 'Test-only audited analytics approval fixture.',
         'idempotency_key', 'youtube-derived-analysis-approved-test-001'
       )
     ) result
   )
   select jsonb_build_array(
     result ->> 'decision',
     result ->> 'approval_reference',
     (result ->> 'external_call_started')::boolean,
     (result ->> 'automatic_retry_started')::boolean
   )
   from decided),
  '["approved","YT-ANALYTICS-AUDIT-TEST-001",false,false]'::jsonb,
  'service-role approval records the exact amendment reference without provider work'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_youtube_observation_analysis_events),
  0,
  'approval-gated processing creates no analysis events'
);
select is(
  (select min(job.status)
   from content_factory.research_youtube_observation_analysis_jobs job
   where job.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  'queued',
  'recorded approval releases still-retained local jobs'
);
set local role service_role;
select is(
  (
    with processed as materialized (
      select public.system_process_due_research_youtube_observation_analysis(
        jsonb_build_object('limit', 1)
      ) result
    )
    select jsonb_build_array(
      (result ->> 'selected')::integer,
      (result ->> 'completed')::integer,
      (result ->> 'failed')::integer,
      result #>> '{items,0,status}',
      (result #>> '{items,0,parsed_count}')::integer,
      (result ->> 'external_call_started')::boolean,
      (result ->> 'provider_attempt_count')::integer,
      (result ->> 'cost_minor')::integer,
      (result ->> 'automatic_retry_started')::boolean
    )
    from processed
  ),
  '[1,1,0,"completed",2,false,0,0,false]'::jsonb,
  'the local parser completes one job and two events with zero provider, cost or retry'
);
reset role;

select is(
  (select jsonb_build_array(
     count(*)::integer,
     min(job.status),
     min(job.attempt_count),
     min(job.parsed_count),
     bool_and(job.no_retry),
     bool_or(job.external_call_started)
   )
   from content_factory.research_youtube_observation_analysis_jobs job
   where job.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  '[1,"completed",1,2,true,false]'::jsonb,
  'the completed local job records its only attempt and cannot be retried'
);
select is(
  (select jsonb_build_array(
     count(*)::integer,
     count(distinct event.observation_id)::integer,
     min(event.analysis_version),
     max(event.analysis_version),
     bool_and(event.origin = 'system_parser'),
     bool_and(event.retention_expires_at = observation.retention_expires_at),
     bool_and(event.observation_hash = observation.observation_hash)
   )
   from content_factory.research_youtube_observation_analysis_events event
   join content_factory.research_youtube_video_observations observation
     on observation.organization_id = event.organization_id
    and observation.id = event.observation_id
    and observation.observation_hash = event.observation_hash
   where observation.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  '[2,2,1,1,true,true,true]'::jsonb,
  'two parser events remain bound to the exact retained observation versions'
);
select ok(
  not content_factory_private.research_youtube_observation_analysis_is_valid(
    jsonb_set(
      (select event.analysis
       from content_factory.research_youtube_observation_analysis_events event
       order by event.created_at, event.id
       limit 1),
      '{signals,search_position}',
      '"1"'::jsonb
    )
  ),
  'numeric strings cannot cross the SQL analysis schema boundary'
);
select ok(
  not content_factory_private.research_youtube_observation_analysis_is_valid(
    jsonb_set(
      (select event.analysis
       from content_factory.research_youtube_observation_analysis_events event
       order by event.created_at, event.id
       limit 1),
      '{signals,query_token_count}',
      '1000'::jsonb
    )
  ),
  'SQL and web share the bounded three-digit token-count contract'
);
select ok(
  (
    select (dimension ->> 'current')::integer
    from jsonb_array_elements(
      content_factory_private.research_category_evidence_readiness(
        'aa110000-0000-4000-8000-000000000001',
        'aa150000-0000-4000-8000-000000000001',
        clock_timestamp()
      ) -> 'dimensions'
    ) dimension
    where dimension ->> 'key' = 'analysis_coverage'
  ) > (
    select (dimension ->> 'current')::integer
    from jsonb_array_elements(
      (select value -> 'dimensions' from automatic_readiness_before_parser)
    ) dimension
    where dimension ->> 'key' = 'analysis_coverage'
  ),
  'analysis coverage increases only after the deterministic parser succeeds'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.organization_id = 'aa110000-0000-4000-8000-000000000001'
     and ledger.market_category_id = 'aa150000-0000-4000-8000-000000000001'),
  (select value from automatic_source_ledger_before_parser),
  'retention-bound analysis does not copy observations into the durable source ledger'
);
select ok(
  (
    content_factory_private.research_category_evidence_readiness(
      'aa110000-0000-4000-8000-000000000001',
      'aa150000-0000-4000-8000-000000000001',
      clock_timestamp()
    ) ->> 'score'
  )::integer
    > (select (value ->> 'score')::integer from automatic_readiness_before),
  'retained automatic observations increase the category readiness score'
);
select isnt(
  content_factory_private.research_category_evidence_readiness(
    'aa110000-0000-4000-8000-000000000001',
    'aa150000-0000-4000-8000-000000000001',
    clock_timestamp()
  ) ->> 'evidence_hash',
  (select value ->> 'evidence_hash' from automatic_readiness_before),
  'retained automatic observations change the readiness evidence hash'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'aa100000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select is(
  (
    with status_call as materialized (
      select public.creator_research_category_learning_status(
        jsonb_build_object(
          'organization_id', 'aa110000-0000-4000-8000-000000000001',
          'run_id', 'aa130000-0000-4000-8000-000000000001'
        )
      ) result
    )
    select jsonb_build_array(
      result ->> 'version',
      jsonb_array_length(result #> '{retained_youtube_evidence,items}'),
      (select count(*)::integer
       from jsonb_array_elements(
         result #> '{retained_youtube_evidence,items}'
       ) retained(item)
       where item #>> '{current_analysis,origin}' = 'system_parser'),
      (select count(*)::integer
       from jsonb_array_elements(
         result #> '{retained_youtube_evidence,items}'
       ) retained(item)
       where jsonb_array_length(item -> 'analysis_history') = 1
         and item #>> '{analysis_history,0,event_id}'
           = item #>> '{current_analysis,event_id}'),
      (select count(*)::integer
       from jsonb_array_elements(
         result #> '{retained_youtube_evidence,items}'
       ) retained(item)
       where item #>> '{analysis_job,status}' = 'completed'
         and (item #>> '{analysis_job,attempt_count}')::integer = 1
         and (item #>> '{analysis_job,parsed_count}')::integer = 2
         and (item #>> '{analysis_job,no_retry}')::boolean
         and not (item #>> '{analysis_job,external_call_started}')::boolean),
      (select count(*)::integer
       from jsonb_array_elements(
         result #> '{retained_youtube_evidence,items}'
       ) retained(item)
       where (item ->> 'can_correct_analysis')::boolean),
      jsonb_array_length(result #> '{collection,history}'),
      result #>> '{collection,history,0,ingestion_status}',
      (result #>> '{collection,history,0,transport_attempt_count}')::integer,
      result #>> '{collection,instagram_automatic_collection}'
    )
    from status_call
  ),
  '["research-category-learning-readiness-v2",2,2,2,2,2,1,"completed",2,"blocked_pending_provider_and_legal_choice"]'::jsonb,
  'creator status returns current analysis, history, completed job and collection audit'
);
reset role;

create temporary table automatic_analysis_correction_fixture on commit drop as
select
  observation.id as observation_id,
  observation.observation_hash,
  observation.retention_expires_at,
  event.id as system_event_id,
  event.event_hash as system_event_hash,
  jsonb_set(
    event.analysis,
    '{summary}',
    to_jsonb(
      'Human reviewer corrected the retained parser hypothesis without changing candidate truth.'::text
    )
  ) as correction_analysis
from content_factory.research_youtube_video_observations observation
join content_factory.research_youtube_observation_analysis_events event
  on event.organization_id = observation.organization_id
 and event.observation_id = observation.id
 and event.observation_hash = observation.observation_hash
where observation.ingestion_id = current_setting(
    'content_factory.test_auto_ingestion_id'
  )::uuid
  and observation.video_id = 'AutoVid0001'
  and event.analysis_version = 1;

create temporary table automatic_readiness_before_human on commit drop as
select content_factory_private.research_category_evidence_readiness(
  'aa110000-0000-4000-8000-000000000001',
  'aa150000-0000-4000-8000-000000000001',
  clock_timestamp()
) value;

do $$
declare
  payload_value jsonb;
begin
  select jsonb_build_object(
    'organization_id', 'aa110000-0000-4000-8000-000000000001',
    'observation_id', fixture.observation_id,
    'observation_hash', fixture.observation_hash,
    'expected_head_event_id', fixture.system_event_id,
    'expected_head_hash', fixture.system_event_hash,
    'analysis', fixture.correction_analysis,
    'correction_reason',
      'A human reviewer refined the local parser hypothesis.',
    'idempotency_key', 'youtube-analysis-human-correction-test-001'
  )
  into payload_value
  from automatic_analysis_correction_fixture fixture;
  perform set_config(
    'content_factory.test_analysis_correction_payload',
    payload_value::text,
    true
  );
end
$$;

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'aa100000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select is(
  (
    with corrected as materialized (
      select public.creator_correct_research_youtube_observation_analysis(
        current_setting(
          'content_factory.test_analysis_correction_payload'
        )::jsonb
      ) result
    )
    select jsonb_build_array(
      (result ->> 'ok')::boolean,
      result ->> 'origin',
      (result ->> 'analysis_version')::integer,
      (result ->> 'external_call_started')::boolean,
      (result ->> 'provider_attempt_count')::integer,
      (result ->> 'automatic_retry_started')::boolean,
      result ->> 'event_id' is not null,
      result ->> 'event_hash' is not null
    )
    from corrected
  ),
  '[true,"human_correction",2,false,0,false,true,true]'::jsonb,
  'an exact-head correction appends human v2 without provider work or retry'
);
reset role;

select is(
  (
    with head as (
      select event.*
      from content_factory.research_youtube_observation_analysis_events event
      join automatic_analysis_correction_fixture fixture
        on fixture.observation_id = event.observation_id
       and fixture.observation_hash = event.observation_hash
      order by event.analysis_version desc, event.id desc
      limit 1
    )
    select jsonb_build_array(
      (select count(*)::integer
       from content_factory.research_youtube_observation_analysis_events event
       where event.observation_id = fixture.observation_id),
      head.analysis_version,
      head.origin,
      head.parent_event_id = fixture.system_event_id,
      head.expected_parent_hash = fixture.system_event_hash,
      head.actor_id = 'aa100000-0000-4000-8000-000000000001'::uuid,
      head.analysis = fixture.correction_analysis,
      head.retention_expires_at = fixture.retention_expires_at,
      (select count(*)::integer
       from content_factory.research_youtube_candidate_decisions decision
       where decision.observation_id = fixture.observation_id)
    )
    from head
    cross join automatic_analysis_correction_fixture fixture
  ),
  '[2,2,"human_correction",true,true,true,true,true,0]'::jsonb,
  'the human head preserves the exact append-only parent chain and candidate truth'
);

set local role authenticated;
select is(
  (
    with replayed as materialized (
      select public.creator_correct_research_youtube_observation_analysis(
        current_setting(
          'content_factory.test_analysis_correction_payload'
        )::jsonb
      ) result
    ), status_call as materialized (
      select public.creator_research_category_learning_status(
        jsonb_build_object(
          'organization_id', 'aa110000-0000-4000-8000-000000000001',
          'run_id', 'aa130000-0000-4000-8000-000000000001'
        )
      ) result
    ), corrected_item as (
      select retained.item
      from status_call
      cross join lateral jsonb_array_elements(
        status_call.result #> '{retained_youtube_evidence,items}'
      ) retained(item)
      where retained.item ->> 'video_id' = 'AutoVid0001'
    )
    select jsonb_build_array(
      replayed.result ->> 'event_id'
        = corrected_item.item #>> '{current_analysis,event_id}',
      replayed.result ->> 'event_hash'
        = corrected_item.item #>> '{current_analysis,event_hash}',
      (replayed.result ->> 'analysis_version')::integer,
      replayed.result ->> 'origin'
    )
    from replayed
    cross join corrected_item
  ),
  '[true,true,2,"human_correction"]'::jsonb,
  'an exact idempotency replay returns the same human head'
);
select throws_ok(
  $stale_analysis_head$
    select public.creator_correct_research_youtube_observation_analysis(
      current_setting(
        'content_factory.test_analysis_correction_payload'
      )::jsonb || jsonb_build_object(
        'idempotency_key', 'youtube-analysis-human-correction-stale-001'
      )
    )
  $stale_analysis_head$,
  '40001',
  'research_youtube_observation_analysis_head_stale',
  'a second command cannot append from the superseded system head'
);
reset role;

select is(
  (select count(*)::integer
   from content_factory.research_youtube_observation_analysis_events event
   join automatic_analysis_correction_fixture fixture
     on fixture.observation_id = event.observation_id),
  2,
  'idempotency replay and stale CAS create no duplicate history'
);
select is(
  (
    with after_value as (
      select content_factory_private.research_category_evidence_readiness(
        'aa110000-0000-4000-8000-000000000001',
        'aa150000-0000-4000-8000-000000000001',
        clock_timestamp()
      ) value
    )
    select jsonb_build_array(
      (select (dimension ->> 'current')::integer
       from after_value,
         jsonb_array_elements(after_value.value -> 'dimensions') dimension
       where dimension ->> 'key' = 'human_validation')
        - (select (dimension ->> 'current')::integer
           from automatic_readiness_before_human before_value,
             jsonb_array_elements(before_value.value -> 'dimensions') dimension
           where dimension ->> 'key' = 'human_validation'),
      (select (dimension ->> 'current')::integer
       from after_value,
         jsonb_array_elements(after_value.value -> 'dimensions') dimension
       where dimension ->> 'key' = 'analysis_coverage')
        - (select (dimension ->> 'current')::integer
           from automatic_readiness_before_human before_value,
             jsonb_array_elements(before_value.value -> 'dimensions') dimension
           where dimension ->> 'key' = 'analysis_coverage'),
      (select (dimension ->> 'current')::integer
       from after_value,
         jsonb_array_elements(after_value.value -> 'dimensions') dimension
       where dimension ->> 'key' = 'competitor_observations')
        - (select (dimension ->> 'current')::integer
           from automatic_readiness_before_human before_value,
             jsonb_array_elements(before_value.value -> 'dimensions') dimension
           where dimension ->> 'key' = 'competitor_observations'),
      (select (dimension ->> 'current')::integer
       from after_value,
         jsonb_array_elements(after_value.value -> 'dimensions') dimension
       where dimension ->> 'key' = 'trend_recency')
        - (select (dimension ->> 'current')::integer
           from automatic_readiness_before_human before_value,
             jsonb_array_elements(before_value.value -> 'dimensions') dimension
           where dimension ->> 'key' = 'trend_recency')
    )
  ),
  '[1,0,0,0]'::jsonb,
  'human correction adds only human-validation readiness credit'
);

insert into content_factory.research_youtube_observation_analysis_jobs (
  id, organization_id, ingestion_id, parser_key, parser_version, status,
  input_hash, retention_expires_at, job_hash
) values (
  'aa1e0000-0000-4000-8000-000000000001',
  'aa110000-0000-4000-8000-000000000001',
  'aa170000-0000-4000-8000-000000000001',
  'youtube_observation_deterministic', '1.0.0', 'queued',
  content_factory_private.research_youtube_analysis_input_hash(
    'aa170000-0000-4000-8000-000000000001'
  ),
  clock_timestamp() + interval '29 days',
  content_factory_private.json_hash(
    '{"fixture":"historical-approval-replay"}'::jsonb
  )
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  public.system_decide_research_youtube_derived_analysis(
    jsonb_build_object(
      'decision', 'emergency_paused',
      'terms_version', 'youtube-derived-metrics-policy-2026-06-01-v1',
      'terms_review_ack', false,
      'analytics_amendment_ack', false,
      'approval_reference', null,
      'reason', 'Pause derived analysis in the runtime gate fixture.',
      'idempotency_key', 'youtube-derived-analysis-paused-test-001'
    )
  ) ->> 'decision',
  'emergency_paused',
  'the service gate records an append-only emergency pause'
);
reset role;

set local role service_role;
do $$ begin
  perform public.system_decide_research_youtube_derived_analysis(
    jsonb_build_object(
      'decision', 'approved',
      'terms_version', 'youtube-derived-metrics-policy-2026-06-01-v1',
      'terms_review_ack', true,
      'analytics_amendment_ack', true,
      'approval_reference', 'YT-ANALYTICS-AUDIT-TEST-001',
      'reason', 'Test-only audited analytics approval fixture.',
      'idempotency_key', 'youtube-derived-analysis-approved-test-001'
    )
  );
end $$;
reset role;
select is(
  (select jsonb_build_array(
     job.status,
     content_factory_private.research_youtube_derived_analysis_approved(),
     (select decision.decision
      from content_factory.research_youtube_derived_analysis_decisions decision
      order by decision.decided_at desc, decision.id desc
      limit 1),
     (select count(*)::integer
      from content_factory.research_youtube_derived_analysis_decisions)
   )
   from content_factory.research_youtube_observation_analysis_jobs job
   where job.id = 'aa1e0000-0000-4000-8000-000000000001'),
  '["approval_required",false,"emergency_paused",3]'::jsonb,
  'historical approval replay cannot diverge jobs from the latest paused gate'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'aa100000-0000-4000-8000-000000000001', true
  );
end $$;
set local role authenticated;
select is(
  (
    with status_call as materialized (
      select public.creator_research_category_learning_status(
        jsonb_build_object(
          'organization_id', 'aa110000-0000-4000-8000-000000000001',
          'run_id', 'aa130000-0000-4000-8000-000000000001'
        )
      ) result
    )
    select jsonb_build_array(
      result #>> '{provider_strategy,youtube_derived_analysis_state}',
      (select count(*)::integer
       from jsonb_array_elements(
         result #> '{retained_youtube_evidence,items}'
       ) retained(item)
       where item ->> 'video_id' = 'AutoVid0001'
         and item #>> '{current_analysis,origin}' = 'human_correction'
         and jsonb_array_length(item -> 'analysis_history') = 2
         and item #>> '{analysis_history,0,event_id}'
           = item #>> '{current_analysis,event_id}'),
      (select count(*)::integer
       from jsonb_array_elements(
         result #> '{retained_youtube_evidence,items}'
       ) retained(item)
       where (item ->> 'can_correct_analysis')::boolean)
    )
    from status_call
  ),
  '["emergency_paused",1,0]'::jsonb,
  'paused status preserves human history but exposes no correction affordance'
);
select throws_ok(
  $paused_analysis_correction$
    with status_call as materialized (
      select public.creator_research_category_learning_status(
        jsonb_build_object(
          'organization_id', 'aa110000-0000-4000-8000-000000000001',
          'run_id', 'aa130000-0000-4000-8000-000000000001'
        )
      ) result
    ), corrected_item as (
      select retained.item
      from status_call
      cross join lateral jsonb_array_elements(
        status_call.result #> '{retained_youtube_evidence,items}'
      ) retained(item)
      where retained.item ->> 'video_id' = 'AutoVid0001'
    )
    select public.creator_correct_research_youtube_observation_analysis(
      jsonb_build_object(
        'organization_id', 'aa110000-0000-4000-8000-000000000001',
        'observation_id', item ->> 'observation_id',
        'observation_hash', item ->> 'observation_hash',
        'expected_head_event_id', item #>> '{current_analysis,event_id}',
        'expected_head_hash', item #>> '{current_analysis,event_hash}',
        'analysis', item #> '{current_analysis,analysis}',
        'correction_reason', 'A paused gate must reject this correction.',
        'idempotency_key', 'youtube-analysis-paused-correction-test-001'
      )
    )
    from corrected_item
  $paused_analysis_correction$,
  '55000',
  'research_youtube_derived_analysis_approval_required',
  'the correction RPC fails closed while derived analysis is paused'
);
reset role;

select throws_ok(
  format(
    'update content_factory.research_youtube_observation_analysis_events '
      || 'set correction_reason = %L where id = %L::uuid',
    'Forbidden in-place rewrite',
    (select event.id
     from content_factory.research_youtube_observation_analysis_events event
     join automatic_analysis_correction_fixture fixture
       on fixture.observation_id = event.observation_id
     order by event.analysis_version desc
     limit 1)
  ),
  '55000',
  'research_youtube_observation_analysis_events_append_only',
  'a human v2 analysis event cannot be rewritten in place'
);
select throws_ok(
  format(
    'delete from content_factory.research_youtube_observation_analysis_events '
      || 'where id = %L::uuid',
    (select event.id
     from content_factory.research_youtube_observation_analysis_events event
     join automatic_analysis_correction_fixture fixture
       on fixture.observation_id = event.observation_id
     order by event.analysis_version desc
     limit 1)
  ),
  '55000',
  'research_youtube_observation_analysis_events_append_only',
  'a human v2 analysis event cannot be deleted outside retention purge'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'service_role', true);
end $$;
set local role service_role;
select is(
  (
    with second_scheduler_tick as materialized (
      select public.system_claim_due_research_youtube_collection(
        jsonb_build_object('limit', 1)
      ) result
    )
    select jsonb_build_array(
      (result ->> 'selected')::integer,
      (result ->> 'claimed')::integer,
      (result ->> 'expired')::integer,
      result -> 'items',
      (result ->> 'automatic_retry_started')::boolean
    )
    from second_scheduler_tick
  ),
  '[0,0,0,[],false]'::jsonb,
  'the second automatic scheduler tick starts no retry or duplicate ingestion'
);
reset role;
select is(
  (select count(*)::integer
   from content_factory.research_source_collection_intents intent
   where intent.organization_id = 'aa110000-0000-4000-8000-000000000001'),
  1,
  'the scheduler retains one append-only automatic intent after the second tick'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_ingestion_runs ingestion
   where ingestion.organization_id = 'aa110000-0000-4000-8000-000000000001'
     and ingestion.mode = 'category_refresh'),
  1,
  'the scheduler creates no duplicate category-refresh ingestion'
);
select is(
  (select jsonb_build_array(
     count(*)::integer,
     count(distinct attempt.request_ordinal)::integer
   )
   from content_factory.research_youtube_transport_attempts attempt
   where attempt.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  '[2,2]'::jsonb,
  'no duplicate or retry transport is recorded after the second tick'
);
select is(
  (select count(*)::integer
   from content_factory.research_youtube_video_observations observation
   where observation.ingestion_id = current_setting(
     'content_factory.test_auto_ingestion_id'
   )::uuid),
  2,
  'the recorded evidence remains stable after the second tick'
);

select * from finish();
rollback;

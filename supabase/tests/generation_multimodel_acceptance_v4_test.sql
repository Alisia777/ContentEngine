begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select ok(
  to_regprocedure('public.creator_generation_model_acceptance(jsonb)')
    is not null
  and to_regprocedure(
    'content_factory_private.creator_generation_model_acceptance_pre_multimodel_v49(jsonb)'
  ) is not null
  and has_function_privilege(
    'authenticated',
    'public.creator_generation_model_acceptance(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_generation_model_acceptance_pre_multimodel_v49(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon', 'public.creator_generation_model_acceptance(jsonb)', 'execute'
  ),
  'one authenticated public owner and one inaccessible legacy seam exist'
);

select is(
  (
    select jsonb_agg(
      jsonb_build_object('provider', catalog.provider, 'model', catalog.model)
      order by catalog.catalog_position
    )
    from content_factory_private.generation_acceptance_catalog_v49() catalog
  ),
  '[
    {"provider":"runway","model":"seedream5_lite"},
    {"provider":"runway","model":"gen4_turbo"},
    {"provider":"runway","model":"seedance2_fast"},
    {"provider":"runway","model":"gen4.5"},
    {"provider":"runway","model":"seedance2_mini"},
    {"provider":"runway","model":"veo3.1_fast"},
    {"provider":"runway","model":"gemini_omni_flash"},
    {"provider":"runway","model":"veo3.1"},
    {"provider":"runway","model":"seedance2"},
    {"provider":"google","model":"veo-3.1-lite-generate-preview"}
  ]'::jsonb,
  'acceptance uses all ten canonical provider plus model identities in order'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
  (
    'd4000000-0000-4000-8000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'acceptance-v4-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Acceptance v4 owner"}'::jsonb, now(), now()
  ),
  (
    'd4000000-0000-4000-8000-000000000002',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'acceptance-v4-reviewer@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Acceptance v4 reviewer"}'::jsonb, now(), now()
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  'd4100000-0000-4000-8000-000000000001',
  'Multi-model acceptance v4', 'multimodel-acceptance-v4', 'active'
);

update content_factory.profiles
set status = 'active'
where id in (
  'd4000000-0000-4000-8000-000000000001',
  'd4000000-0000-4000-8000-000000000002'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'd4100000-0000-4000-8000-000000000001',
    'd4000000-0000-4000-8000-000000000001', 'owner', 'active'
  ),
  (
    'd4100000-0000-4000-8000-000000000001',
    'd4000000-0000-4000-8000-000000000002', 'reviewer', 'active'
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'd4200000-0000-4000-8000-000000000001',
  'd4100000-0000-4000-8000-000000000001', null,
  'Acceptance v4 project', 'blue', 'project', null, 'active', 1024,
  'd4000000-0000-4000-8000-000000000001',
  'd4000000-0000-4000-8000-000000000001'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'd4300000-0000-4000-8000-000000000001',
  'd4100000-0000-4000-8000-000000000001',
  'ACCEPT-V4-1', 'Acceptance v4 product', 'active', '{}'::jsonb,
  'd4000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_campaigns (
  id, organization_id, name, kind, status, created_by, updated_by
) values (
  'd4700000-0000-4000-8000-000000000001',
  'd4100000-0000-4000-8000-000000000001',
  'Multi-model acceptance fixture', 'managed', 'active',
  'd4000000-0000-4000-8000-000000000001',
  'd4000000-0000-4000-8000-000000000001'
);

-- Fixture writes bypass workflow triggers only. Every table CHECK remains in
-- force, including canonical provider/model/SKU and paid-job constraints.
set local session_replication_role = replica;

create temporary table acceptance_v4_fixture (
  fixture_position integer primary key,
  model text not null,
  duration_seconds integer not null,
  resolution text not null,
  audio boolean not null,
  batch_id uuid not null,
  job_id uuid not null,
  media_id uuid not null,
  media_sha text not null,
  metadata_provider text not null,
  metadata_model text not null
) on commit drop;

insert into acceptance_v4_fixture values
  (1, 'gen4.5', 2, '720p', false,
   'd4400000-0000-4000-8000-000000000001',
   'd4500000-0000-4000-8000-000000000001',
   'd4600000-0000-4000-8000-000000000001', repeat('1',64),
   'runway', 'gen4.5'),
  -- A paid succeeded job whose output claims another provider and model.
  (2, 'gen4.5', 2, '720p', false,
   'd4400000-0000-4000-8000-000000000002',
   'd4500000-0000-4000-8000-000000000002',
   'd4600000-0000-4000-8000-000000000002', repeat('2',64),
   'google', 'seedance2_mini'),
  (3, 'seedance2_mini', 4, '720p', true,
   'd4400000-0000-4000-8000-000000000003',
   'd4500000-0000-4000-8000-000000000003',
   'd4600000-0000-4000-8000-000000000003', repeat('3',64),
   'runway', 'seedance2_mini'),
  (4, 'veo3.1_fast', 4, '720p', false,
   'd4400000-0000-4000-8000-000000000004',
   'd4500000-0000-4000-8000-000000000004',
   'd4600000-0000-4000-8000-000000000004', repeat('4',64),
   'runway', 'veo3.1_fast'),
  (5, 'gemini_omni_flash', 3, '720p', true,
   'd4400000-0000-4000-8000-000000000005',
   'd4500000-0000-4000-8000-000000000005',
   'd4600000-0000-4000-8000-000000000005', repeat('5',64),
   'runway', 'gemini_omni_flash');

insert into content_factory.generation_batches (
  id, organization_id, project_id, product_id, created_by, name, mode,
  allow_real_spend, status, total_requested, total_created, input,
  request_hash, idempotency_key, provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency, campaign_id
)
select
  fixture.batch_id,
  'd4100000-0000-4000-8000-000000000001',
  'd4200000-0000-4000-8000-000000000001',
  'd4300000-0000-4000-8000-000000000001',
  'd4000000-0000-4000-8000-000000000001',
  'Acceptance fixture ' || fixture.fixture_position,
  'real', true, 'succeeded', 1, 1,
  sku.sku || jsonb_build_object('provider', 'runway'),
  repeat(to_hex(fixture.fixture_position + 5), 64),
  'acceptance-v4-batch-' || fixture.fixture_position,
  'runway', fixture.model, fixture.duration_seconds, fixture.audio,
  (sku.sku ->> 'estimated_cost_minor')::bigint,
  (sku.sku ->> 'estimated_credits')::bigint,
  'USD', 'd4700000-0000-4000-8000-000000000001'
from acceptance_v4_fixture fixture
cross join lateral (
  select content_factory_private.real_generation_multimodel_sku(
    'runway', fixture.model, 'image', fixture.duration_seconds,
    '9:16', fixture.resolution, fixture.audio, false
  ) as sku
) sku;

insert into content_factory.generation_jobs (
  id, organization_id, project_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status, input, output,
  request_hash, idempotency_key, campaign_id
)
select
  fixture.job_id,
  'd4100000-0000-4000-8000-000000000001',
  'd4200000-0000-4000-8000-000000000001',
  'd4300000-0000-4000-8000-000000000001',
  fixture.batch_id, 1,
  'd4000000-0000-4000-8000-000000000001',
  'd4000000-0000-4000-8000-000000000001',
  'real', 'runway', true,
  (sku.sku ->> 'estimated_cost_minor')::bigint,
  (sku.sku ->> 'estimated_cost_minor')::bigint,
  'succeeded', sku.sku,
  jsonb_build_object(
    'provider_task_id', 'acceptance-task-' || fixture.fixture_position,
    'output_media_id', fixture.media_id,
    'sha256', fixture.media_sha
  ),
  repeat(to_hex(fixture.fixture_position + 10), 64),
  'acceptance-v4-job-' || fixture.fixture_position,
  'd4700000-0000-4000-8000-000000000001'
from acceptance_v4_fixture fixture
cross join lateral (
  select content_factory_private.real_generation_multimodel_sku(
    'runway', fixture.model, 'image', fixture.duration_seconds,
    '9:16', fixture.resolution, fixture.audio, false
  ) as sku
) sku;

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id,
  bucket_id, object_name, mime_type, size_bytes, sha256, status,
  metadata, idempotency_key
)
select
  fixture.media_id,
  'd4100000-0000-4000-8000-000000000001',
  'd4200000-0000-4000-8000-000000000001',
  'd4000000-0000-4000-8000-000000000001',
  'd4300000-0000-4000-8000-000000000001',
  'contentengine-private',
  'd4100000-0000-4000-8000-000000000001/' ||
    'd4000000-0000-4000-8000-000000000001/generated/' ||
    fixture.job_id::text || '.mp4',
  'video/mp4', 1024, fixture.media_sha, 'ready',
  jsonb_build_object(
    'kind', 'generated_video',
    'provider', fixture.metadata_provider,
    'model', fixture.metadata_model,
    'generation_job_id', fixture.job_id,
    'rights_confirmed', true
  ),
  'acceptance-v4-media-' || fixture.fixture_position
from acceptance_v4_fixture fixture;

-- Correct and stale scenarios each use a source AI review plus an immutable
-- context-bound child. The child is what the independent human watches.
insert into content_factory.content_review_runs (
  id, organization_id, project_id, media_object_id, requested_by,
  parent_review_id, status, media_sha256_snapshot, input, result,
  ruleset_version, model_provider, model_version, request_hash,
  completion_hash, idempotency_key, started_at, finished_at
) values
  (
    'd4700000-0000-4000-8000-000000000011',
    'd4100000-0000-4000-8000-000000000001',
    'd4200000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000001',
    'd4000000-0000-4000-8000-000000000001', null, 'completed', repeat('1',64),
    jsonb_build_object(
      'generation_job_id','d4500000-0000-4000-8000-000000000001',
      'ai_generated',true,'external_ai_processing_confirmed',true
    ),
    '{"overall_score":92,"blockers_count":0,"compliance_status":"pass"}',
    'acceptance-v4-rules', 'openai', 'qa-fixture-v1', repeat('a',64),
    repeat('a',64), 'acceptance-v4-review-source-1', now()-interval '1 day',
    now()-interval '1 day'
  ),
  (
    'd4700000-0000-4000-8000-000000000012',
    'd4100000-0000-4000-8000-000000000001',
    'd4200000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000001',
    'd4000000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000011', 'completed', repeat('1',64),
    jsonb_build_object(
      'generation_job_id','d4500000-0000-4000-8000-000000000001',
      'ai_generated',true,'external_ai_processing_confirmed',true,
      'context_amendment',jsonb_build_object(
        'source_review_id','d4700000-0000-4000-8000-000000000011',
        'source_completion_hash',repeat('a',64),
        'external_ai_invoked',false,'provider_analysis_reused',true
      )
    ),
    '{"overall_score":92,"blockers_count":0,"compliance_status":"pass"}',
    'acceptance-v4-rules', 'openai', 'qa-fixture-v1', repeat('b',64),
    repeat('b',64), 'acceptance-v4-review-child-1', now()-interval '1 day',
    now()-interval '1 day'
  ),
  (
    'd4700000-0000-4000-8000-000000000031',
    'd4100000-0000-4000-8000-000000000001',
    'd4200000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000003',
    'd4000000-0000-4000-8000-000000000001', null, 'completed', repeat('3',64),
    jsonb_build_object(
      'generation_job_id','d4500000-0000-4000-8000-000000000003',
      'ai_generated',true,'external_ai_processing_confirmed',true
    ),
    '{"overall_score":88,"blockers_count":0,"compliance_status":"pass"}',
    'acceptance-v4-rules', 'openai', 'qa-fixture-v1', repeat('c',64),
    repeat('c',64), 'acceptance-v4-review-source-3', now()-interval '91 days',
    now()-interval '91 days'
  ),
  (
    'd4700000-0000-4000-8000-000000000032',
    'd4100000-0000-4000-8000-000000000001',
    'd4200000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000003',
    'd4000000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000031', 'completed', repeat('3',64),
    jsonb_build_object(
      'generation_job_id','d4500000-0000-4000-8000-000000000003',
      'ai_generated',true,'external_ai_processing_confirmed',true,
      'context_amendment',jsonb_build_object(
        'source_review_id','d4700000-0000-4000-8000-000000000031',
        'source_completion_hash',repeat('c',64),
        'external_ai_invoked',false,'provider_analysis_reused',true
      )
    ),
    '{"overall_score":88,"blockers_count":0,"compliance_status":"pass"}',
    'acceptance-v4-rules', 'openai', 'qa-fixture-v1', repeat('d',64),
    repeat('d',64), 'acceptance-v4-review-child-3', now()-interval '91 days',
    now()-interval '91 days'
  ),
  -- Same-actor decision: exact review exists, acceptance evidence does not.
  (
    'd4700000-0000-4000-8000-000000000041',
    'd4100000-0000-4000-8000-000000000001',
    'd4200000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000004',
    'd4000000-0000-4000-8000-000000000001', null, 'completed', repeat('4',64),
    jsonb_build_object(
      'generation_job_id','d4500000-0000-4000-8000-000000000004',
      'ai_generated',true,'external_ai_processing_confirmed',true
    ),
    '{"overall_score":95,"blockers_count":0,"compliance_status":"pass"}',
    'acceptance-v4-rules', 'openai', 'qa-fixture-v1', repeat('e',64),
    repeat('e',64), 'acceptance-v4-review-same-actor-4', now(), now()
  ),
  -- Independent approval without a context amendment must fail closed.
  (
    'd4700000-0000-4000-8000-000000000051',
    'd4100000-0000-4000-8000-000000000001',
    'd4200000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000005',
    'd4000000-0000-4000-8000-000000000001', null, 'completed', repeat('5',64),
    jsonb_build_object(
      'generation_job_id','d4500000-0000-4000-8000-000000000005',
      'ai_generated',true,'external_ai_processing_confirmed',true
    ),
    '{"overall_score":93,"blockers_count":0,"compliance_status":"pass"}',
    'acceptance-v4-rules', 'openai', 'qa-fixture-v1', repeat('f',64),
    repeat('f',64), 'acceptance-v4-review-no-context-5', now(), now()
  );

insert into content_factory.content_review_decisions (
  id, organization_id, review_id, decided_by, decision, comment,
  media_watched_confirmed, review_completion_hash,
  media_sha256_snapshot, idempotency_key, created_at
) values
  (
    'd4800000-0000-4000-8000-000000000001',
    'd4100000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000012',
    'd4000000-0000-4000-8000-000000000002', 'approved',
    'Independent watched acceptance fixture.', true, repeat('b',64),
    repeat('1',64), 'acceptance-v4-decision-1', now()-interval '1 day'
  ),
  (
    'd4800000-0000-4000-8000-000000000003',
    'd4100000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000032',
    'd4000000-0000-4000-8000-000000000002', 'approved',
    'Independent watched stale fixture.', true, repeat('d',64),
    repeat('3',64), 'acceptance-v4-decision-3', now()-interval '91 days'
  ),
  (
    'd4800000-0000-4000-8000-000000000004',
    'd4100000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000041',
    'd4000000-0000-4000-8000-000000000001', 'approved',
    'Requester cannot independently accept.', true, repeat('e',64),
    repeat('4',64), 'acceptance-v4-decision-4', now()
  ),
  (
    'd4800000-0000-4000-8000-000000000005',
    'd4100000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000051',
    'd4000000-0000-4000-8000-000000000002', 'approved',
    'Independent but context-free approval.', true, repeat('f',64),
    repeat('5',64), 'acceptance-v4-decision-5', now()
  );

insert into content_factory.content_review_context_amendments (
  organization_id, source_review_id, amended_review_id,
  generation_job_id, media_object_id, product_id,
  source_completion_hash, amended_completion_hash,
  context_snapshot, created_by, created_at
) values
  (
    'd4100000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000011',
    'd4700000-0000-4000-8000-000000000012',
    'd4500000-0000-4000-8000-000000000001',
    'd4600000-0000-4000-8000-000000000001',
    'd4300000-0000-4000-8000-000000000001',
    repeat('a',64), repeat('b',64),
    '{"version":"generated-video-context-v1"}',
    'd4000000-0000-4000-8000-000000000002', now()-interval '1 day'
  ),
  (
    'd4100000-0000-4000-8000-000000000001',
    'd4700000-0000-4000-8000-000000000031',
    'd4700000-0000-4000-8000-000000000032',
    'd4500000-0000-4000-8000-000000000003',
    'd4600000-0000-4000-8000-000000000003',
    'd4300000-0000-4000-8000-000000000001',
    repeat('c',64), repeat('d',64),
    '{"version":"generated-video-context-v1"}',
    'd4000000-0000-4000-8000-000000000002', now()-interval '91 days'
  );

set local session_replication_role = origin;

create temporary table acceptance_v4_results (
  model text primary key,
  payload jsonb not null
) on commit drop;

insert into acceptance_v4_results (model, payload)
select catalog.model,
  content_factory_private.generation_model_acceptance_v49(
    'd4100000-0000-4000-8000-000000000001',
    catalog.provider, catalog.model, now()
  )
from content_factory_private.generation_acceptance_catalog_v49() catalog
where catalog.model in (
  'gen4.5', 'seedance2_mini', 'veo3.1_fast', 'gemini_omni_flash',
  'veo3.1', 'seedance2', 'veo-3.1-lite-generate-preview'
);

select is(
  (select payload ->> 'status' from acceptance_v4_results
   where model = 'gen4.5'),
  'accepted',
  'new Runway model accepts only exact paid output plus full independent QA'
);

select is(
  (select payload ->> 'successful_runs' from acceptance_v4_results
   where model = 'gen4.5'),
  '1',
  'wrong provider and model media identity is excluded from exact outputs'
);

select is(
  (select payload #>> '{evidence,media_id}' from acceptance_v4_results
   where model = 'gen4.5'),
  'd4600000-0000-4000-8000-000000000001',
  'accepted evidence preserves the exact media identity'
);

select ok(
  (select (payload #>> '{evidence,overall_score}')::integer >= 80
          and payload #>> '{evidence,blockers_count}' = '0'
          and payload #>> '{evidence,compliance_status}' = 'pass'
          and payload #>> '{evidence,context_bound}' = 'true'
          and payload #>> '{evidence,independent_reviewer}' = 'true'
          and payload #>> '{evidence,media_watched_confirmed}' = 'true'
   from acceptance_v4_results where model = 'gen4.5'),
  'accepted evidence exposes every quality and human authority fact'
);

select is(
  (select payload ->> 'status' from acceptance_v4_results
   where model = 'seedance2_mini'),
  'needs_revalidation',
  'evidence older than ninety days is never accepted'
);

select is(
  (select payload ->> 'reason_code' from acceptance_v4_results
   where model = 'seedance2_mini'),
  'acceptance_evidence_stale',
  'stale evidence uses the exact revalidation reason'
);

select is(
  (select payload ->> 'status' from acceptance_v4_results
   where model = 'veo3.1_fast'),
  'unproven',
  'same actor cannot independently accept their requested output'
);

select is(
  (select payload #>> '{pending_review,review_id}'
   from acceptance_v4_results where model = 'veo3.1_fast'),
  'd4700000-0000-4000-8000-000000000041',
  'same-actor rejection leaves the exact output and review pending for a teammate'
);

select is(
  (select payload ->> 'status' from acceptance_v4_results
   where model = 'gemini_omni_flash'),
  'needs_revalidation',
  'an independent approval without context binding fails closed'
);

select is(
  (select payload ->> 'reason_code' from acceptance_v4_results
   where model = 'gemini_omni_flash'),
  'approval_context_not_bound',
  'missing context amendment has an exact remediation reason'
);

select ok(
  (select payload ->> 'status' = 'unproven'
          and payload ->> 'successful_runs' = '0'
   from acceptance_v4_results
   where model = 'veo-3.1-lite-generate-preview'),
  'blocked direct Google stays visible and unproven without eligible evidence'
);

select ok(
  (select bool_and(
    payload ->> 'status' = 'unproven'
    and payload ->> 'successful_runs' = '0'
  ) from acceptance_v4_results where model in ('veo3.1', 'seedance2')),
  'premium catalog models remain honestly unproven without real eligible output'
);

create temporary table acceptance_v4_public_result (
  payload jsonb not null
) on commit drop;
grant select, insert on acceptance_v4_public_result to authenticated;

select set_config(
  'request.jwt.claim.sub',
  'd4000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);
set local role authenticated;

insert into acceptance_v4_public_result (payload)
values (public.creator_generation_model_acceptance(jsonb_build_object(
  'organization_id', 'd4100000-0000-4000-8000-000000000001'
)));

reset role;

select is(
  (select jsonb_array_length(payload -> 'models')
   from acceptance_v4_public_result),
  10,
  'the single public owner returns the complete canonical catalog'
);

select is(
  (select payload ->> 'version' from acceptance_v4_public_result),
  'generation-model-acceptance-v4',
  'the public all-catalog contract has an explicit v4 version'
);

select ok(
  (select payload -> 'automatic_generation' = 'false'::jsonb
          and payload -> 'automatic_spend' = 'false'::jsonb
          and payload ->> 'all_models_accepted' = 'false'
   from acceptance_v4_public_result),
  'acceptance never authorizes automatic generation or spend'
);

select ok(
  (
    select public_model.value - array[
      'provider','public_label','lifecycle','enabled_by_default','enabled',
      'launch_enabled','disabled_reason_code','feature_flag',
      'catalog_version','pricing_version','automatic_generation',
      'automatic_spend'
    ]::text[] = legacy_model.value
    from jsonb_array_elements(
      (select payload -> 'models' from acceptance_v4_public_result)
    ) public_model(value)
    join jsonb_array_elements(
      content_factory_private.generation_model_acceptance_freshness(
        content_factory_private.generation_model_acceptance(
          'd4100000-0000-4000-8000-000000000001'
        ),
        (select (payload ->> 'evaluated_at')::timestamptz
         from acceptance_v4_public_result)
      ) -> 'models'
    ) legacy_model(value)
      on legacy_model.value ->> 'model' = public_model.value ->> 'model'
    where public_model.value ->> 'model' = 'seedream5_lite'
  ),
  'legacy model evidence and pending fields remain byte-equivalent'
);

select ok(
  (
    select item.value ->> 'provider' = 'google'
      and item.value ->> 'public_label' = 'Veo 3.1 Lite'
      and item.value ->> 'lifecycle' = 'preview'
      and item.value ->> 'launch_enabled' = 'false'
      and item.value ->> 'disabled_reason_code' = 'direct_google_disabled'
      and item.value ->> 'status' = 'unproven'
    from jsonb_array_elements(
      (select payload -> 'models' from acceptance_v4_public_result)
    ) item(value)
    where item.value ->> 'model' = 'veo-3.1-lite-generate-preview'
  ),
  'catalog labels lifecycle launch state and disabled reason come from authority'
);

select * from finish();
rollback;

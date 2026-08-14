begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select ok(
  to_regprocedure('public.creator_generation_archive(jsonb)') is not null
  and has_function_privilege(
    'authenticated', 'public.creator_generation_archive(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.creator_generation_archive(jsonb)', 'execute'
  ),
  'one authenticated-only archive RPC remains public'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
  (
    'ac000000-0000-4000-8000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'archive-v1-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Archive v1 owner"}'::jsonb, now(), now()
  ),
  (
    'ac000000-0000-4000-8000-000000000002',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'archive-v1-operator@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Archive v1 operator"}'::jsonb, now(), now()
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  'ac100000-0000-4000-8000-000000000001',
  'Multi-model archive v1', 'multimodel-archive-v1', 'active'
);

update content_factory.profiles
set status = 'active'
where id in (
  'ac000000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000002'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'ac100000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000001', 'owner', 'active'
  ),
  (
    'ac100000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000002', 'operator', 'active'
  );

insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
) values
  (
    'ac100000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000001',
    'workspace_generation', 'active', 'owner', 'owner',
    'TEST-ONLY waiver for multi-model archive owner coverage.',
    'ac000000-0000-4000-8000-000000000001'
  ),
  (
    'ac100000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000002',
    'workspace_generation', 'active', 'trainee', 'operator',
    'TEST-ONLY waiver for multi-model archive operator coverage.',
    'ac000000-0000-4000-8000-000000000001'
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'ac200000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001', null,
  'Multi-model archive project', 'blue', 'project', null,
  'active', 1024,
  'ac000000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001'
);

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
) values (
  'ac100000-0000-4000-8000-000000000001',
  'ac200000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000002',
  'member', 'active',
  'ac000000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'ac300000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001',
  'ARCHIVE-MM-1', 'Multi-model archive product', 'active', '{}'::jsonb,
  'ac000000-0000-4000-8000-000000000001'
);

-- Four plain historical rows plus one recoverably archived row.  No snapshot
-- is fabricated for them, even when batch.input contains provider-like data.
insert into content_factory.generation_batches (
  id, organization_id, project_id, product_id, created_by, name, mode,
  allow_real_spend, status, total_requested, total_created, input,
  request_hash, idempotency_key, provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency, created_at, updated_at,
  archived_at, archived_by
) values
  (
    'ac400000-0000-4000-8000-000000000001',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac300000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000001',
    'Legacy forged parameters', 'mock', false, 'mock_ready', 1, 1,
    '{"provider":"runway","model":"gen4.5","generation_selection_snapshot":{"provider":"runway","model":"gen4.5"}}'::jsonb,
    repeat('a', 64), 'archive-mm-legacy-owner',
    'mock', 'mock', 0, false, 0, 0, 'USD',
    now() - interval '5 minutes', now() - interval '5 minutes', null, null
  ),
  (
    'ac400000-0000-4000-8000-000000000002',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac300000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000002',
    'Legacy operator row', 'mock', false, 'mock_ready', 1, 1,
    '{}'::jsonb, repeat('b', 64), 'archive-mm-legacy-operator',
    'mock', 'mock', 0, false, 0, 0, 'USD',
    now() - interval '4 minutes', now() - interval '4 minutes', null, null
  ),
  (
    'ac400000-0000-4000-8000-000000000003',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac300000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000001',
    'Snapshot Runway Gen 4.5', 'mock', false, 'mock_ready', 1, 1,
    '{}'::jsonb, repeat('c', 64), 'archive-mm-runway',
    'mock', 'mock', 0, false, 0, 0, 'USD',
    now() - interval '3 minutes', now() - interval '3 minutes', null, null
  ),
  (
    'ac400000-0000-4000-8000-000000000004',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac300000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000001',
    'Snapshot Google Veo Lite', 'mock', false, 'mock_ready', 1, 1,
    '{}'::jsonb, repeat('d', 64), 'archive-mm-google',
    'mock', 'mock', 0, false, 0, 0, 'USD',
    now() - interval '2 minutes', now() - interval '2 minutes', null, null
  ),
  (
    'ac400000-0000-4000-8000-000000000005',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac300000-0000-4000-8000-000000000001',
    'ac000000-0000-4000-8000-000000000001',
    'Soft archived snapshot row', 'mock', false, 'mock_ready', 1, 1,
    '{}'::jsonb, repeat('e', 64), 'archive-mm-hidden',
    'mock', 'mock', 0, false, 0, 0, 'USD',
    now() - interval '1 minute', now() - interval '1 minute',
    now(), 'ac000000-0000-4000-8000-000000000001'
  );

-- Archive read semantics can be exercised independently from the paid-start
-- binder.  Replica mode bypasses only fixture triggers/FKs while inserting
-- validator-clean immutable rows; the RPC still reads the exact table.
set local session_replication_role = replica;
insert into content_factory.generation_job_selection_snapshots (
  id, organization_id, project_id, batch_id, generation_job_id,
  spec_id, spec_version, spec_hash, scope_hash,
  readiness_receipt_id, readiness_receipt_hash,
  snapshot_version, selection_snapshot, snapshot_hash,
  live_claim_snapshot, live_claim_snapshot_hash,
  provider, model, content_kind, selection_source, quality_status,
  catalog_version, pricing_version, estimated_cost_minor,
  estimated_credits, bound_by, bound_at
) values
  (
    'ac500000-0000-4000-8000-000000000001',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac400000-0000-4000-8000-000000000003',
    'ac600000-0000-4000-8000-000000000001',
    'ac700000-0000-4000-8000-000000000001', 1, repeat('1', 64), repeat('2', 64),
    'ac800000-0000-4000-8000-000000000001', repeat('3', 64),
    'generation-selection-snapshot-v1',
    jsonb_build_object(
      'provider', 'runway', 'model', 'gen4.5',
      'model_public_label', 'Gen-4.5',
      'selection_source', 'manual_choice',
      'recommendation_reason_codes', jsonb_build_array('manual_override'),
      'recommendation_warning_codes', '[]'::jsonb,
      'recommendation_catalog_version', '2026-08-13.v1',
      'pricing_version', 'runway-credits-2026-08-13.v1',
      'estimated_cost_minor', 24,
      'requested_duration_seconds', 2,
      'requested_ratio', '9:16', 'requested_resolution', '720p',
      'requested_audio', false, 'input_mode', 'image', 'reference_count', 1,
      'acceptance_status_at_launch', 'accepted',
      'provider_readiness_receipt_id',
        'ac800000-0000-4000-8000-000000000001'
    ),
    content_factory_private.json_hash(jsonb_build_object(
      'provider', 'runway', 'model', 'gen4.5',
      'model_public_label', 'Gen-4.5',
      'selection_source', 'manual_choice',
      'recommendation_reason_codes', jsonb_build_array('manual_override'),
      'recommendation_warning_codes', '[]'::jsonb,
      'recommendation_catalog_version', '2026-08-13.v1',
      'pricing_version', 'runway-credits-2026-08-13.v1',
      'estimated_cost_minor', 24,
      'requested_duration_seconds', 2,
      'requested_ratio', '9:16', 'requested_resolution', '720p',
      'requested_audio', false, 'input_mode', 'image', 'reference_count', 1,
      'acceptance_status_at_launch', 'accepted',
      'provider_readiness_receipt_id',
        'ac800000-0000-4000-8000-000000000001'
    )),
    jsonb_build_object(
      'snapshot_hash', content_factory_private.json_hash('{}'::jsonb)
    ), content_factory_private.json_hash('{}'::jsonb),
    'runway', 'gen4.5', 'video', 'manual_choice', 'accepted',
    '2026-08-13.v1', 'runway-credits-2026-08-13.v1', 24, 24,
    'ac000000-0000-4000-8000-000000000001', now()
  ),
  (
    'ac500000-0000-4000-8000-000000000002',
    'ac100000-0000-4000-8000-000000000001',
    'ac200000-0000-4000-8000-000000000001',
    'ac400000-0000-4000-8000-000000000004',
    'ac600000-0000-4000-8000-000000000002',
    'ac700000-0000-4000-8000-000000000002', 1, repeat('5', 64), repeat('6', 64),
    'ac800000-0000-4000-8000-000000000002', repeat('7', 64),
    'generation-selection-snapshot-v1',
    jsonb_build_object(
      'provider', 'google', 'model', 'veo-3.1-lite-generate-preview',
      'model_public_label', 'Veo 3.1 Lite',
      'selection_source', 'system_recommendation',
      'recommendation_reason_codes', jsonb_build_array('lowest_cost'),
      'recommendation_warning_codes', jsonb_build_array('preview_model'),
      'recommendation_catalog_version', '2026-08-13.v1',
      'pricing_version', 'google-veo-2026-08-13.v1',
      'estimated_cost_minor', 10,
      'requested_duration_seconds', 4,
      'requested_ratio', '16:9', 'requested_resolution', '720p',
      'requested_audio', true, 'input_mode', 'text', 'reference_count', 0,
      'acceptance_status_at_launch', 'unproven',
      'provider_readiness_receipt_id',
        'ac800000-0000-4000-8000-000000000002'
    ),
    content_factory_private.json_hash(jsonb_build_object(
      'provider', 'google', 'model', 'veo-3.1-lite-generate-preview',
      'model_public_label', 'Veo 3.1 Lite',
      'selection_source', 'system_recommendation',
      'recommendation_reason_codes', jsonb_build_array('lowest_cost'),
      'recommendation_warning_codes', jsonb_build_array('preview_model'),
      'recommendation_catalog_version', '2026-08-13.v1',
      'pricing_version', 'google-veo-2026-08-13.v1',
      'estimated_cost_minor', 10,
      'requested_duration_seconds', 4,
      'requested_ratio', '16:9', 'requested_resolution', '720p',
      'requested_audio', true, 'input_mode', 'text', 'reference_count', 0,
      'acceptance_status_at_launch', 'unproven',
      'provider_readiness_receipt_id',
        'ac800000-0000-4000-8000-000000000002'
    )),
    jsonb_build_object(
      'snapshot_hash', content_factory_private.json_hash('{}'::jsonb)
    ), content_factory_private.json_hash('{}'::jsonb),
    'google', 'veo-3.1-lite-generate-preview', 'video',
    'system_recommendation', 'unproven',
    '2026-08-13.v1', 'google-veo-2026-08-13.v1', 10, null,
    'ac000000-0000-4000-8000-000000000001', now()
  );
set local session_replication_role = origin;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'ac000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;
set local role authenticated;

select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'page_size', 100
  )) -> 'batches'),
  4,
  'archive keeps legacy rows but hides the recoverably archived row'
);

select ok(
  (
    select item.value -> 'generation_selection_snapshot' = 'null'::jsonb
      and item.value -> 'provider' = 'null'::jsonb
      and item.value -> 'model' = 'null'::jsonb
    from jsonb_array_elements(public.creator_generation_archive(
      jsonb_build_object(
        'organization_id', 'ac100000-0000-4000-8000-000000000001',
        'project_id', 'ac200000-0000-4000-8000-000000000001',
        'period', 'all', 'query', 'Legacy forged parameters'
      )
    ) -> 'batches') item(value)
  ),
  'legacy provider-like parameters never become authoritative metadata'
);

select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'provider', 'runway'
  )) -> 'batches'),
  1,
  'provider filter excludes legacy and other-provider rows before paging'
);

select ok(
  public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'provider', 'runway', 'model', 'gen4.5',
    'content_kind', 'video', 'selection_source', 'manual_choice',
    'quality_status', 'accepted'
  )) #> '{_meta}' @> jsonb_build_object(
    'provider', 'runway', 'model', 'gen4.5', 'content_kind', 'video',
    'selection_source', 'manual_choice', 'quality_status', 'accepted'
  ),
  'archive metadata echoes every server-applied model filter'
);

select is(
  public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'model', 'gen4.5'
  )) #>> '{batches,0,generation_selection_snapshot,model_public_label}',
  'Gen-4.5',
  'model filter returns the exact immutable launch snapshot'
);

select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'content_kind', 'video',
    'selection_source', 'manual_choice', 'quality_status', 'accepted'
  )) -> 'batches'),
  1,
  'content/source/quality filters compose on immutable summaries'
);

select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'query', 'veo-3.1-lite-generate-preview'
  )) -> 'batches'),
  1,
  'query finds the raw immutable model identifier'
);

select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all', 'query', 'Veo 3.1 Lite'
  )) -> 'batches'),
  1,
  'query finds the immutable public model label'
);

select ok(
  (
    with first_page as (
      select public.creator_generation_archive(jsonb_build_object(
        'organization_id', 'ac100000-0000-4000-8000-000000000001',
        'project_id', 'ac200000-0000-4000-8000-000000000001',
        'period', 'all', 'page_size', 2
      )) as value
    ), second_page as (
      select public.creator_generation_archive(jsonb_build_object(
        'organization_id', 'ac100000-0000-4000-8000-000000000001',
        'project_id', 'ac200000-0000-4000-8000-000000000001',
        'period', 'all', 'page_size', 2,
        'cursor', first_page.value #> '{_meta,next_cursor}'
      )) as value
      from first_page
    )
    select (first_page.value #>> '{_meta,has_more}')::boolean
      and jsonb_array_length(first_page.value -> 'batches') = 2
      and jsonb_array_length(second_page.value -> 'batches') = 2
      and not exists (
        select 1
        from jsonb_array_elements(first_page.value -> 'batches') one(value)
        join jsonb_array_elements(second_page.value -> 'batches') two(value)
          on one.value ->> 'id' = two.value ->> 'id'
      )
    from first_page cross join second_page
  ),
  'keyset pagination remains stable and non-overlapping'
);

select set_config(
  'request.jwt.claim.sub',
  'ac000000-0000-4000-8000-000000000002',
  true
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'ac100000-0000-4000-8000-000000000001',
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'period', 'all'
  )) -> 'batches'),
  1,
  'operator scope still returns only the actor own batch'
);

select set_config(
  'request.jwt.claim.sub',
  'ac000000-0000-4000-8000-000000000001',
  true
);

select throws_ok(
  $$select public.creator_generation_archive(jsonb_build_object(
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'provider', 'unknown'
  ))$$,
  '22023', 'generation_archive_provider_invalid',
  'unknown provider filters fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive(jsonb_build_object(
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'model', 'bad model'
  ))$$,
  '22023', 'generation_archive_model_invalid',
  'malformed raw model filters fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive(jsonb_build_object(
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'content_kind', 'audio'
  ))$$,
  '22023', 'generation_archive_content_kind_invalid',
  'unknown content-kind filters fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive(jsonb_build_object(
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'selection_source', 'automatic'
  ))$$,
  '22023', 'generation_archive_selection_source_invalid',
  'unknown recommendation-source filters fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive(jsonb_build_object(
    'project_id', 'ac200000-0000-4000-8000-000000000001',
    'quality_status', 'available'
  ))$$,
  '22023', 'generation_archive_quality_status_invalid',
  'provider availability cannot masquerade as quality status'
);

reset role;

select * from finish();
rollback;

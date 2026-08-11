begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    'eb000000-0000-4000-8000-000000000001',
    'response-recovery-owner@example.test',
    'Response Recovery Owner'
  ),
  (
    'eb000000-0000-4000-8000-000000000002',
    'response-recovery-producer@example.test',
    'Response Recovery Producer'
  ),
  (
    'eb000000-0000-4000-8000-000000000003',
    'response-recovery-viewer@example.test',
    'Response Recovery Viewer'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  'eb100000-0000-4000-8000-000000000001',
  'Exact response recovery pgTAP',
  'exact-response-recovery-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'eb100000-0000-4000-8000-000000000001',
    'eb000000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    'eb100000-0000-4000-8000-000000000001',
    'eb000000-0000-4000-8000-000000000002',
    'producer', 'active'
  ),
  (
    'eb100000-0000-4000-8000-000000000001',
    'eb000000-0000-4000-8000-000000000003',
    'viewer', 'active'
  );

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'eb000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'eb200000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  null, 'Exact response recovery project', 'blue', 'project', null,
  'active', 1024,
  'eb000000-0000-4000-8000-000000000001',
  'eb000000-0000-4000-8000-000000000001'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'eb300000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  'EXACT-RECOVERY-SKU-1',
  'Exact recovery product',
  'active',
  '{"brand":"Fixture","description":"GET-only recovery fixture"}'::jsonb,
  'eb000000-0000-4000-8000-000000000001'
);

-- The fixture below begins at the already-audited terminal seam. Existing
-- migrations independently test exact-source creation, binding hashes and
-- provider-attempt creation. Replica mode is limited to synthetic INSERTs;
-- all recovery calls and assertions execute with ordinary triggers enabled.
set local session_replication_role = replica;

insert into content_factory.product_research_runs (
  id, organization_id, project_id, product_id, created_by, status, input,
  summary, error_code, error_message, request_hash, completion_hash,
  idempotency_key, started_at, lease_expires_at, finished_at
) values
  (
    'eb400000-0000-4000-8000-000000000001',
    'eb100000-0000-4000-8000-000000000001',
    'eb200000-0000-4000-8000-000000000001',
    'eb300000-0000-4000-8000-000000000001',
    'eb000000-0000-4000-8000-000000000001',
    'failed',
    '{"objective":"Recover the saved exact-video response","platforms":["youtube"],"source_media_ids":[]}'::jsonb,
    '{}'::jsonb,
    'provider_response_invalid',
    'The saved response needs corrected local validation.',
    repeat('1', 64), repeat('2', 64),
    'exact-response-recovery-run-0001',
    clock_timestamp() - interval '31 minutes', null,
    clock_timestamp() - interval '29 minutes'
  ),
  (
    'eb400000-0000-4000-8000-000000000002',
    'eb100000-0000-4000-8000-000000000001',
    'eb200000-0000-4000-8000-000000000001',
    'eb300000-0000-4000-8000-000000000001',
    'eb000000-0000-4000-8000-000000000001',
    'failed',
    '{"objective":"Missing exact binding","platforms":["youtube"],"source_media_ids":[]}'::jsonb,
    '{}'::jsonb,
    'provider_response_invalid',
    'This fixture deliberately has no exact-video binding.',
    repeat('3', 64), repeat('4', 64),
    'exact-response-recovery-run-0002',
    clock_timestamp() - interval '31 minutes', null,
    clock_timestamp() - interval '29 minutes'
  );

insert into content_factory.research_execution_authorizations (
  id, organization_id, run_id, authorized_by, authorization_kind,
  paid_analysis_ack, provider_key, adapter_version, run_request_hash,
  max_provider_attempts, automatic_fallback_allowed, reason_code,
  authorized_at, authorization_hash
) values (
  'eb500000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  'eb400000-0000-4000-8000-000000000001',
  'eb000000-0000-4000-8000-000000000001',
  'explicit_paid_analysis', true,
  'openai_web_search', 'openai-responses-web-search-v1',
  repeat('1', 64), 1, false, 'user_confirmed_paid_analysis',
  clock_timestamp() - interval '31 minutes', repeat('5', 64)
);

insert into content_factory.research_run_provider_bindings (
  id, organization_id, run_id, authorization_id, provider_key,
  adapter_version, model, attempt_number, binding_hash, bound_at
) values (
  'eb510000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  'eb400000-0000-4000-8000-000000000001',
  'eb500000-0000-4000-8000-000000000001',
  'openai_web_search', 'openai-responses-web-search-v1',
  'gpt-5.5', 1, repeat('6', 64),
  clock_timestamp() - interval '31 minutes'
);

insert into content_factory.research_provider_response_bindings (
  id, organization_id, run_id, attempt_id, provider_key, adapter_version,
  provider_response_id, initial_status, accepted_at, response_hash
) values (
  'eb520000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  'eb400000-0000-4000-8000-000000000001',
  'eb510000-0000-4000-8000-000000000001',
  'openai_web_search', 'openai-responses-web-search-v1',
  'resp_exact_recovery_fixture_001', 'completed',
  clock_timestamp() - interval '30 minutes', repeat('7', 64)
);

insert into content_factory.research_exact_youtube_research_bindings (
  id, organization_id, project_id, run_id, product_id,
  category_binding_id, product_category, product_sku_snapshot,
  product_title_snapshot, source_id, attachment_id, media_object_id,
  evidence_set_id, source_hash_snapshot, attachment_hash_snapshot,
  media_sha256_snapshot, evidence_manifest_hash_snapshot,
  evidence_frame_count_snapshot, evidence_total_size_bytes_snapshot,
  category_binding_hash_snapshot, media_matches_registered_source,
  source_match_basis, source_match_attested_by, source_match_attested_at,
  paid_analysis_ack_snapshot, analysis_scope, full_stream_access,
  transcript_available, bound_by, binding_hash, bound_at
) values (
  'eb530000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  'eb200000-0000-4000-8000-000000000001',
  'eb400000-0000-4000-8000-000000000001',
  'eb300000-0000-4000-8000-000000000001',
  'eb540000-0000-4000-8000-000000000001',
  'household', 'EXACT-RECOVERY-SKU-1', 'Exact recovery product',
  'eb550000-0000-4000-8000-000000000001',
  'eb560000-0000-4000-8000-000000000001',
  'eb570000-0000-4000-8000-000000000001',
  'eb580000-0000-4000-8000-000000000001',
  repeat('a', 64), repeat('b', 64), repeat('c', 64), repeat('d', 64),
  5, 2560, repeat('e', 64), true,
  'operator_compared_uploaded_media_to_registered_source',
  'eb000000-0000-4000-8000-000000000001',
  clock_timestamp() - interval '32 minutes', true,
  'sampled_frames_only', false, false,
  'eb000000-0000-4000-8000-000000000001',
  repeat('f', 64), clock_timestamp() - interval '31 minutes'
);

set local session_replication_role = origin;

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_authorize_product_research_response_recovery(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_authorize_product_research_response_recovery(jsonb)',
    'execute'
  ),
  'only authenticated users can request exact-project recovery authorization'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_claim_product_research_response_recovery(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_claim_product_research_response_recovery(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_read_product_research_response_recovery_reservation(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_read_product_research_response_recovery_reservation(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_record_product_research_response_recovery_outcome(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_record_product_research_response_recovery_outcome(jsonb)',
    'execute'
  ),
  'claim and outcome seams are service-only'
);

select is(
  (
    select count(*)::integer
    from (values
      ('content_factory.research_provider_response_recovery_authorizations'::regclass),
      ('content_factory.research_provider_response_recovery_get_reservations'::regclass),
      ('content_factory.research_provider_response_recovery_outcomes'::regclass)
    ) protected(table_oid)
    where has_table_privilege('authenticated', table_oid, 'select')
       or has_table_privilege('service_role', table_oid, 'insert')
  ),
  0,
  'recovery ledgers have no direct browser or service-role write surface'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'eb000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_authorize_product_research_response_recovery(
    jsonb_build_object(
      'organization_id', 'eb100000-0000-4000-8000-000000000001',
      'project_id', 'eb200000-0000-4000-8000-000000000001',
      'run_id', 'eb400000-0000-4000-8000-000000000001',
      'idempotency_key', 'viewer-recovery-denied-0001',
      'recovery_ack', true
    )
  )$$,
  '42501', 'role_not_allowed',
  'viewer cannot authorize saved-response recovery'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'eb000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_authorize_product_research_response_recovery(
    jsonb_build_object(
      'organization_id', 'eb100000-0000-4000-8000-000000000001',
      'project_id', 'eb200000-0000-4000-8000-000000000001',
      'run_id', 'eb400000-0000-4000-8000-000000000001',
      'idempotency_key', 'producer-recovery-no-project-0001',
      'recovery_ack', true
    )
  )$$,
  '42501', 'workspace_project_access_required',
  'producer without exact-project membership cannot authorize recovery'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'eb000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_authorize_product_research_response_recovery(
    jsonb_build_object(
      'organization_id', 'eb100000-0000-4000-8000-000000000001',
      'project_id', 'eb200000-0000-4000-8000-000000000001',
      'run_id', 'eb400000-0000-4000-8000-000000000002',
      'idempotency_key', 'missing-exact-binding-0001',
      'recovery_ack', true
    )
  )$$,
  '55000', 'research_response_recovery_exact_binding_required',
  'a failed ordinary research run without an exact-video binding is ineligible'
);

create temporary table exact_response_recovery_context (
  authorization_result jsonb,
  authorization_replay jsonb,
  rollback_claim_succeeded boolean,
  claim_result jsonb,
  claim_replay jsonb,
  completion_result jsonb,
  outcome_result jsonb,
  outcome_replay jsonb
) on commit drop;

insert into exact_response_recovery_context (authorization_result)
select public.creator_authorize_product_research_response_recovery(
  jsonb_build_object(
    'organization_id', 'eb100000-0000-4000-8000-000000000001',
    'project_id', 'eb200000-0000-4000-8000-000000000001',
    'run_id', 'eb400000-0000-4000-8000-000000000001',
    'idempotency_key', 'owner-response-recovery-0001',
    'recovery_ack', true
  )
);

update exact_response_recovery_context
set authorization_replay =
  public.creator_authorize_product_research_response_recovery(
    jsonb_build_object(
      'organization_id', 'eb100000-0000-4000-8000-000000000001',
      'project_id', 'eb200000-0000-4000-8000-000000000001',
      'run_id', 'eb400000-0000-4000-8000-000000000001',
      'idempotency_key', 'owner-response-recovery-0001',
      'recovery_ack', true
    )
  );

select ok(
  (
    select authorization_result ->> 'code' =
        'research_response_recovery_authorized'
      and authorization_replay ->> 'code' =
        'research_response_recovery_already_authorized'
      and authorization_result ->> 'authorization_id' =
        authorization_replay ->> 'authorization_id'
      and not (authorization_result ? 'provider_response_id')
    from exact_response_recovery_context
  ),
  'human authorization is idempotent and never exposes the provider response id'
);

select is(
  (
    select count(*)::integer
    from content_factory.research_provider_response_recovery_authorizations
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  ),
  1,
  'authorization replay cannot duplicate the append-only authorization'
);

select ok(
  (
    select guard -> 'get_reserved' = 'false'::jsonb
      and guard -> 'reservation_id' = 'null'::jsonb
      and not (guard ? 'provider_response_id')
    from (
      select public
        .system_read_product_research_response_recovery_reservation(
          jsonb_build_object(
            'run_id', 'eb400000-0000-4000-8000-000000000001'
          )
        ) as guard
    ) guarded
  ),
  'service guard reports no reservation without exposing the provider id'
);

insert into content_factory.research_provider_response_receipts (
  id, organization_id, run_id, response_binding_id, attempt_id,
  provider_key, adapter_version, provider_response_id, provider_status,
  checked_at, receipt_hash
) values (
  'eb590000-0000-4000-8000-000000000001',
  'eb100000-0000-4000-8000-000000000001',
  'eb400000-0000-4000-8000-000000000001',
  'eb520000-0000-4000-8000-000000000001',
  'eb510000-0000-4000-8000-000000000001',
  'openai_web_search', 'openai-responses-web-search-v1',
  'resp_exact_recovery_fixture_001', 'in_progress',
  clock_timestamp() + interval '1 second', repeat('9', 64)
);

select throws_ok(
  $$select public.system_claim_product_research_response_recovery(
    jsonb_build_object(
      'authorization_id', (
        select (authorization_result ->> 'authorization_id')::uuid
        from exact_response_recovery_context
      )
    )
  )$$,
  '55000', 'research_response_recovery_completed_response_required',
  'claim rechecks the latest completed provider status before reserving GET'
);

select ok(
  not exists (
    select 1
    from content_factory.research_provider_response_recovery_get_reservations
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  )
  and (
    select status = 'failed' and error_code = 'provider_response_invalid'
    from content_factory.product_research_runs
    where id = 'eb400000-0000-4000-8000-000000000001'
  ),
  'a rejected claim rolls back without a GET reservation or run transition'
);

insert into content_factory.research_provider_response_receipts (
  id, organization_id, run_id, response_binding_id, attempt_id,
  provider_key, adapter_version, provider_response_id, provider_status,
  checked_at, receipt_hash
) values (
  'eb590000-0000-4000-8000-000000000002',
  'eb100000-0000-4000-8000-000000000001',
  'eb400000-0000-4000-8000-000000000001',
  'eb520000-0000-4000-8000-000000000001',
  'eb510000-0000-4000-8000-000000000001',
  'openai_web_search', 'openai-responses-web-search-v1',
  'resp_exact_recovery_fixture_001', 'completed',
  clock_timestamp() + interval '2 seconds', repeat('8', 64)
);

do $rollback_successful_claim$
declare
  claim_result_value jsonb;
  claim_succeeded_value boolean := false;
begin
  begin
    select public.system_claim_product_research_response_recovery(
      jsonb_build_object(
        'authorization_id', context_row.authorization_result
          ->> 'authorization_id'
      )
    ) into claim_result_value
    from exact_response_recovery_context context_row;
    claim_succeeded_value :=
      claim_result_value ->> 'code' =
        'research_response_recovery_get_reserved'
      and claim_result_value -> 'get_allowed' = 'true'::jsonb
      and claim_result_value -> 'provider_post_allowed' = 'false'::jsonb;
    if not claim_succeeded_value then
      raise exception 'successful_recovery_claim_required';
    end if;
    -- The forced exception rolls back the successful reservation and the
    -- failed-to-processing transition as one subtransaction.
    raise exception 'rollback_successful_recovery_claim';
  exception when raise_exception then
    if sqlerrm <> 'rollback_successful_recovery_claim' then
      raise;
    end if;
  end;
  update exact_response_recovery_context
  set rollback_claim_succeeded = claim_succeeded_value;
end;
$rollback_successful_claim$;

select ok(
  (select rollback_claim_succeeded from exact_response_recovery_context)
  and not exists (
    select 1
    from content_factory.research_provider_response_recovery_get_reservations
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  )
  and (
    select status = 'failed' and error_code = 'provider_response_invalid'
    from content_factory.product_research_runs
    where id = 'eb400000-0000-4000-8000-000000000001'
  )
  and (
    select count(*) = 1
    from content_factory.research_run_provider_bindings
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  ),
  'a successful claim rolls back its reservation and transition atomically'
);

update exact_response_recovery_context context_row
set claim_result = public.system_claim_product_research_response_recovery(
  jsonb_build_object(
    'authorization_id', context_row.authorization_result ->> 'authorization_id'
  )
);

select ok(
  (
    select claim_result ->> 'code' =
        'research_response_recovery_get_reserved'
      and claim_result -> 'get_allowed' = 'true'::jsonb
      and claim_result -> 'provider_post_allowed' = 'false'::jsonb
      and claim_result -> 'include_web_search_sources' = 'true'::jsonb
      and claim_result ->> 'provider_response_id' =
        'resp_exact_recovery_fixture_001'
    from exact_response_recovery_context
  ),
  'the first claim returns the saved response id under one GET-only reservation'
);

select ok(
  (
    select status = 'processing'
      and error_code is null
      and error_message is null
      and completion_hash is null
      and finished_at is null
      and lease_expires_at > clock_timestamp()
      and lease_expires_at <= clock_timestamp() + interval '2 minutes'
    from content_factory.product_research_runs
    where id = 'eb400000-0000-4000-8000-000000000001'
  ),
  'claim opens only the existing bounded parser lease after the old cutoff'
);

select ok(
  (
    select maximum_provider_gets = 1
      and provider_get_allowed
      and not provider_post_allowed
      and include_web_search_sources
    from content_factory.research_provider_response_recovery_get_reservations
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  )
  and (
    select count(*) = 1
    from content_factory.research_run_provider_bindings
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  ),
  'recovery reserves one GET and preserves the single original provider attempt'
);

select ok(
  (
    select guard -> 'get_reserved' = 'true'::jsonb
      and guard ->> 'reservation_id' = context_row.claim_result ->> 'reservation_id'
      and guard -> 'outcome_recorded' = 'false'::jsonb
      and not (guard ? 'provider_response_id')
    from exact_response_recovery_context context_row
    cross join lateral (
      select public
        .system_read_product_research_response_recovery_reservation(
          jsonb_build_object(
            'run_id', 'eb400000-0000-4000-8000-000000000001'
          )
        ) as guard
    ) guarded
  ),
  'later requests can detect the reserved GET without receiving response inputs'
);

update exact_response_recovery_context context_row
set claim_replay = public.system_claim_product_research_response_recovery(
  jsonb_build_object(
    'authorization_id', context_row.authorization_result ->> 'authorization_id'
  )
);

select ok(
  (
    select claim_replay -> 'ok' = 'false'::jsonb
      and claim_replay ->> 'code' =
        'research_response_recovery_get_already_reserved'
      and claim_replay -> 'get_allowed' = 'false'::jsonb
      and not (claim_replay ? 'provider_response_id')
    from exact_response_recovery_context
  )
  and (
    select count(*) = 1
    from content_factory.research_provider_response_recovery_get_reservations
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  ),
  'claim replay cannot authorize or reveal inputs for a second provider GET'
);

select throws_ok(
  $$select public.system_record_product_research_response_recovery_outcome(
    jsonb_build_object(
      'reservation_id', (
        select (claim_result ->> 'reservation_id')::uuid
        from exact_response_recovery_context
      )
    )
  )$$,
  '55000', 'research_response_recovery_terminal_run_required',
  'outcome cannot be recorded before authoritative local completion'
);

update exact_response_recovery_context context_row
set completion_result = public.system_complete_product_research(
  jsonb_build_object(
    'run_id', 'eb400000-0000-4000-8000-000000000001',
    'status', 'failed',
    'error_code', 'provider_response_invalid',
    'error_message', 'The recovered response still failed strict validation.'
  )
);

select is(
  (
    select count(*)::integer
    from content_factory.research_provider_response_recovery_outcomes
    where run_id = 'eb400000-0000-4000-8000-000000000001'
      and terminal_status = 'failed'
      and terminal_error_code = 'provider_response_invalid'
  ),
  1,
  'terminal transition atomically records the recovery outcome'
);

select ok(
  (
    select guard -> 'get_reserved' = 'true'::jsonb
      and guard -> 'outcome_recorded' = 'true'::jsonb
      and not (guard ? 'provider_response_id')
    from (
      select public
        .system_read_product_research_response_recovery_reservation(
          jsonb_build_object(
            'run_id', 'eb400000-0000-4000-8000-000000000001'
          )
        ) as guard
    ) guarded
  ),
  'service guard exposes the atomic terminal receipt without response inputs'
);

update exact_response_recovery_context context_row
set outcome_result =
  public.system_record_product_research_response_recovery_outcome(
    jsonb_build_object(
      'reservation_id', context_row.claim_result ->> 'reservation_id'
    )
  );

update exact_response_recovery_context context_row
set outcome_replay =
  public.system_record_product_research_response_recovery_outcome(
    jsonb_build_object(
      'reservation_id', context_row.claim_result ->> 'reservation_id'
    )
  );

select ok(
  (
    select outcome_result ->> 'code' =
        'research_response_recovery_outcome_already_recorded'
      and outcome_replay ->> 'code' =
        'research_response_recovery_outcome_already_recorded'
      and outcome_result ->> 'outcome_id' = outcome_replay ->> 'outcome_id'
      and outcome_result ->> 'status' = 'failed'
      and outcome_result ->> 'error_code' = 'provider_response_invalid'
    from exact_response_recovery_context
  )
  and (
    select count(*) = 1
    from content_factory.research_provider_response_recovery_outcomes
    where run_id = 'eb400000-0000-4000-8000-000000000001'
  ),
  'terminal outcome is server-derived, append-only and idempotent'
);

select throws_ok(
  $$update content_factory.research_provider_response_recovery_authorizations
    set recovery_ack_snapshot = false
    where run_id = 'eb400000-0000-4000-8000-000000000001'$$,
  '55000',
  'research_provider_response_recovery_authorizations_append_only',
  'recovery authorization cannot be rewritten'
);

select throws_ok(
  $$delete from content_factory.research_provider_response_recovery_get_reservations
    where run_id = 'eb400000-0000-4000-8000-000000000001'$$,
  '55000',
  'research_provider_response_recovery_get_reservations_append_only',
  'one-GET reservation cannot be deleted for replay'
);

select throws_ok(
  $$update content_factory.research_provider_response_recovery_outcomes
    set terminal_error_code = 'provider_outcome_unknown'
    where run_id = 'eb400000-0000-4000-8000-000000000001'$$,
  '55000',
  'research_provider_response_recovery_outcomes_append_only',
  'recorded recovery outcome cannot be rewritten'
);

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
) values (
  'eb100000-0000-4000-8000-000000000001',
  'eb200000-0000-4000-8000-000000000001',
  'eb000000-0000-4000-8000-000000000002',
  'member', 'active',
  'eb000000-0000-4000-8000-000000000001',
  'eb000000-0000-4000-8000-000000000001'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'eb000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select ok(
  (
    public.creator_authorize_product_research_response_recovery(
      jsonb_build_object(
        'organization_id', 'eb100000-0000-4000-8000-000000000001',
        'project_id', 'eb200000-0000-4000-8000-000000000001',
        'run_id', 'eb400000-0000-4000-8000-000000000001',
        'idempotency_key', 'producer-recovery-with-project-0001',
        'recovery_ack', true
      )
    ) ->> 'code'
  ) = 'research_response_recovery_already_authorized',
  'producer with exact-project ACL can reuse the one existing authorization'
);

select * from finish();
rollback;

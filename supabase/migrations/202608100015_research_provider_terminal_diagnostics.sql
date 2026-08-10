begin;

-- Responses terminal failures used to collapse to provider_request_rejected.
-- Keep an append-only, bounded diagnostic without storing the provider body,
-- request payload, source URL, object names, response id, prompt or tokens.
-- This is intentionally future-only: immutable v1 receipts stay generic and
-- are never overwritten to invent a diagnostic after the provider body is gone.
alter table content_factory.research_provider_health_receipts
  add column if not exists provider_terminal_status text check (
    provider_terminal_status is null
    or provider_terminal_status in ('failed', 'cancelled', 'incomplete')
  ),
  add column if not exists provider_error_code text check (
    provider_error_code is null
    or provider_error_code in (
      'authentication_error', 'content_filter',
      'context_length_exceeded', 'insufficient_quota',
      'empty_image_file', 'failed_to_download_image',
      'image_content_policy_violation', 'image_file_not_found',
      'image_file_too_large', 'image_parse_error',
      'image_too_large', 'image_too_small',
      'invalid_base64_image', 'invalid_image', 'invalid_image_format',
      'invalid_image_mode', 'invalid_image_url',
      'internal_server_error', 'invalid_prompt',
      'invalid_request_error', 'model_not_found', 'overloaded_error',
      'permission_error', 'rate_limit_exceeded', 'request_timeout',
      'safety_violation', 'server_error', 'service_unavailable', 'timeout',
      'unsupported_image_media_type', 'vector_store_timeout',
      'responses_failed.unclassified',
      'responses_cancelled.unclassified',
      'responses_incomplete.unspecified',
      'responses_incomplete.content_filter',
      'responses_incomplete.max_output_tokens',
      'responses_incomplete.max_tool_calls'
    )
  ),
  add column if not exists provider_error_type text check (
    provider_error_type is null
    or provider_error_type in (
      'api_error', 'authentication_error', 'content_filter_error',
      'invalid_request_error', 'permission_error',
      'provider_internal_error', 'rate_limit_error', 'safety_error',
      'server_error', 'service_unavailable_error', 'timeout_error',
      'responses_terminal.failed', 'responses_terminal.cancelled',
      'responses_terminal.incomplete'
    )
  ),
  add column if not exists provider_error_message text check (
    provider_error_message is null
    or (
      char_length(provider_error_message) between 10 and 280
      and provider_error_message !~ '[[:cntrl:]]'
      and provider_error_message !~* '(https?://|www[.]|bearer|authorization|api[_ -]?key)'
      and provider_error_message !~* '(sk|sess|resp)_[A-Za-z0-9_-]{8,}'
      and position('@' in provider_error_message) = 0
    )
  ),
  add column if not exists provider_message_present boolean;

alter table content_factory.research_provider_health_receipts
  add constraint research_provider_health_terminal_diagnostic_consistent
  check (
    (
      provider_terminal_status is null
      and provider_error_code is null
      and provider_error_type is null
      and provider_error_message is null
      and provider_message_present is null
    )
    or (
      provider_terminal_status is not null
      and provider_error_code is not null
      and provider_error_type is not null
      and provider_error_message is not null
      and provider_message_present is not null
      and status <> 'ready'
      and (
        (
          provider_terminal_status = 'failed'
          and provider_error_message =
            'Provider accepted the response and ended processing with status failed.'
        )
        or (
          provider_terminal_status = 'cancelled'
          and provider_error_message =
            'Provider accepted the response and ended processing with status cancelled.'
        )
        or (
          provider_terminal_status = 'incomplete'
          and provider_error_message in (
            'Provider ended processing with status incomplete (unspecified).',
            'Provider ended processing with status incomplete (content_filter).',
            'Provider ended processing with status incomplete (max_output_tokens).',
            'Provider ended processing with status incomplete (max_tool_calls).'
          )
        )
      )
      and (
        provider_error_code not like 'responses_incomplete.%'
        or provider_error_message =
          'Provider ended processing with status incomplete ('
          || split_part(provider_error_code, '.', 2) || ').'
      )
    )
  ) not valid;

alter table content_factory.research_provider_health_receipts
  validate constraint research_provider_health_terminal_diagnostic_consistent;

create or replace function public.system_record_research_provider_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  attempt_id_value uuid;
  status_value text;
  failure_code_value text;
  citation_count_value integer;
  checked_at_value timestamptz;
  expires_at_value timestamptz;
  terminal_status_value text;
  provider_error_code_value text;
  provider_error_type_value text;
  provider_error_message_value text;
  provider_message_present_value boolean;
  diagnostic_present boolean;
  binding_row content_factory.research_run_provider_bindings%rowtype;
  catalog_row content_factory.research_provider_catalog%rowtype;
  receipt_row content_factory.research_provider_health_receipts%rowtype;
  receipt_payload_value jsonb;
  receipt_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'attempt_id', 'status', 'failure_code', 'citation_count', 'checked_at',
    'provider_terminal_status', 'provider_error_code',
    'provider_error_type', 'provider_error_message',
    'provider_message_present'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'attempt_id'
       and p_payload ? 'status'
       and p_payload ? 'checked_at'
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end if;

  attempt_id_value := content_factory_private.require_uuid(
    p_payload, 'attempt_id'
  );
  status_value := content_factory_private.require_text(
    p_payload, 'status', 5, 16
  );
  failure_code_value := nullif(
    btrim(coalesce(p_payload ->> 'failure_code', '')),
    ''
  );
  if status_value not in ('ready', 'degraded', 'blocked', 'unknown')
     or (
       p_payload ? 'failure_code'
       and jsonb_typeof(p_payload -> 'failure_code') not in ('string', 'null')
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end if;

  if p_payload ? 'citation_count'
     and jsonb_typeof(p_payload -> 'citation_count') <> 'null' then
    if jsonb_typeof(p_payload -> 'citation_count') <> 'number'
       or coalesce(p_payload ->> 'citation_count', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'research_provider_health_payload_invalid';
    end if;
    begin
      citation_count_value := (p_payload ->> 'citation_count')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'research_provider_health_payload_invalid';
    end;
  end if;
  if citation_count_value is not null
     and citation_count_value not between 0 and 1000 then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end if;

  diagnostic_present := p_payload ?| array[
    'provider_terminal_status', 'provider_error_code',
    'provider_error_type', 'provider_error_message',
    'provider_message_present'
  ];
  if diagnostic_present then
    if not p_payload ?& array[
         'provider_terminal_status', 'provider_error_code',
         'provider_error_type', 'provider_error_message',
         'provider_message_present'
       ]
       or jsonb_typeof(p_payload -> 'provider_message_present') <> 'boolean'
       or jsonb_typeof(p_payload -> 'provider_terminal_status') <> 'string'
       or jsonb_typeof(p_payload -> 'provider_error_code') <> 'string'
       or jsonb_typeof(p_payload -> 'provider_error_type') <> 'string'
       or jsonb_typeof(p_payload -> 'provider_error_message') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'research_provider_terminal_diagnostic_invalid';
    end if;
    terminal_status_value := content_factory_private.require_text(
      p_payload, 'provider_terminal_status', 6, 10
    );
    provider_error_code_value := content_factory_private.require_text(
      p_payload, 'provider_error_code', 1, 80
    );
    provider_error_type_value := content_factory_private.require_text(
      p_payload, 'provider_error_type', 1, 80
    );
    provider_error_message_value := content_factory_private.require_text(
      p_payload, 'provider_error_message', 10, 280
    );
    provider_message_present_value :=
      (p_payload ->> 'provider_message_present')::boolean;
    if terminal_status_value not in ('failed', 'cancelled', 'incomplete')
       or provider_error_code_value not in (
         'authentication_error', 'content_filter',
         'context_length_exceeded', 'insufficient_quota',
         'empty_image_file', 'failed_to_download_image',
         'image_content_policy_violation', 'image_file_not_found',
         'image_file_too_large', 'image_parse_error',
         'image_too_large', 'image_too_small',
         'invalid_base64_image', 'invalid_image', 'invalid_image_format',
         'invalid_image_mode', 'invalid_image_url',
         'internal_server_error', 'invalid_prompt',
         'invalid_request_error', 'model_not_found', 'overloaded_error',
         'permission_error', 'rate_limit_exceeded', 'request_timeout',
         'safety_violation', 'server_error', 'service_unavailable', 'timeout',
         'unsupported_image_media_type', 'vector_store_timeout',
         'responses_failed.unclassified',
         'responses_cancelled.unclassified',
         'responses_incomplete.unspecified',
         'responses_incomplete.content_filter',
         'responses_incomplete.max_output_tokens',
         'responses_incomplete.max_tool_calls'
       )
       or provider_error_type_value not in (
         'api_error', 'authentication_error', 'content_filter_error',
         'invalid_request_error', 'permission_error',
         'provider_internal_error', 'rate_limit_error', 'safety_error',
         'server_error', 'service_unavailable_error', 'timeout_error',
         'responses_terminal.failed', 'responses_terminal.cancelled',
         'responses_terminal.incomplete'
       )
       or (
         provider_error_code_value like 'responses_failed.%'
         and terminal_status_value <> 'failed'
       )
       or (
         provider_error_code_value like 'responses_cancelled.%'
         and terminal_status_value <> 'cancelled'
       )
       or (
         provider_error_code_value like 'responses_incomplete.%'
         and terminal_status_value <> 'incomplete'
       )
       or (
         provider_error_type_value like 'responses_terminal.%'
         and provider_error_type_value <>
           'responses_terminal.' || terminal_status_value
       )
       or (
         terminal_status_value = 'failed'
         and provider_error_message_value <>
           'Provider accepted the response and ended processing with status failed.'
       )
       or (
         terminal_status_value = 'cancelled'
         and provider_error_message_value <>
           'Provider accepted the response and ended processing with status cancelled.'
       )
       or (
         terminal_status_value = 'incomplete'
         and provider_error_message_value not in (
           'Provider ended processing with status incomplete (unspecified).',
           'Provider ended processing with status incomplete (content_filter).',
           'Provider ended processing with status incomplete (max_output_tokens).',
           'Provider ended processing with status incomplete (max_tool_calls).'
         )
       )
       or (
         provider_error_code_value like 'responses_incomplete.%'
         and provider_error_message_value <>
           'Provider ended processing with status incomplete ('
           || split_part(provider_error_code_value, '.', 2) || ').'
       )
       or status_value = 'ready' then
      raise exception using
        errcode = '22023',
        message = 'research_provider_terminal_diagnostic_invalid';
    end if;
  end if;

  begin
    checked_at_value := content_factory_private.require_text(
      p_payload, 'checked_at', 10, 64
    )::timestamptz;
  exception when invalid_datetime_format or datetime_field_overflow then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_payload_invalid';
  end;

  select binding.* into binding_row
  from content_factory.research_run_provider_bindings binding
  where binding.id = attempt_id_value;
  if binding_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'research_provider_attempt_not_found';
  end if;
  select catalog.* into catalog_row
  from content_factory.research_provider_catalog catalog
  where catalog.provider_key = binding_row.provider_key
    and catalog.adapter_version = binding_row.adapter_version;
  if catalog_row.provider_key is null then
    raise exception using
      errcode = '55000',
      message = 'research_provider_catalog_missing';
  end if;
  if checked_at_value < binding_row.bound_at - interval '1 minute'
     or checked_at_value > clock_timestamp() + interval '1 minute'
     or checked_at_value < clock_timestamp() - interval '24 hours' then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_checked_at_invalid';
  end if;
  if (status_value = 'ready' and (
        failure_code_value is not null
        or coalesce(citation_count_value, 0) < 1
      ))
     or (status_value <> 'ready' and failure_code_value is null)
     or failure_code_value is not null and failure_code_value not in (
       'provider_configuration_error',
       'provider_authentication_failed',
       'provider_rate_limited',
       'provider_request_rejected',
       'provider_response_invalid',
       'provider_outcome_unknown',
       'provider_unavailable',
       'citation_coverage_insufficient'
     ) then
    raise exception using
      errcode = '22023',
      message = 'research_provider_health_state_invalid';
  end if;

  expires_at_value := checked_at_value
    + make_interval(secs => catalog_row.passive_health_ttl_seconds);
  receipt_payload_value := jsonb_build_object(
    'version', case
      when diagnostic_present then 'research-provider-health-receipt-v2'
      else 'research-provider-health-receipt-v1'
    end,
    'organization_id', binding_row.organization_id,
    'run_id', binding_row.run_id,
    'attempt_id', binding_row.id,
    'provider_key', binding_row.provider_key,
    'adapter_version', binding_row.adapter_version,
    'status', status_value,
    'failure_code', failure_code_value,
    'citation_count', citation_count_value,
    'check_kind', 'passive_execution',
    'provider_request_created', false,
    'actual_cost_minor', 0,
    'checked_at', checked_at_value,
    'expires_at', expires_at_value
  );
  if diagnostic_present then
    receipt_payload_value := receipt_payload_value || jsonb_build_object(
      'provider_terminal_status', terminal_status_value,
      'provider_error_code', provider_error_code_value,
      'provider_error_type', provider_error_type_value,
      'provider_error_message', provider_error_message_value,
      'provider_message_present', provider_message_present_value
    );
  end if;
  receipt_hash_value := content_factory_private.json_hash(
    receipt_payload_value
  );

  perform pg_advisory_xact_lock(
    hashtext(binding_row.organization_id::text),
    hashtext(
      'research-provider-health:' || binding_row.id::text || ':' || status_value
    )
  );
  select receipt.* into receipt_row
  from content_factory.research_provider_health_receipts receipt
  where receipt.organization_id = binding_row.organization_id
    and receipt.attempt_id = binding_row.id
    and receipt.status = status_value;
  if receipt_row.id is not null then
    if receipt_row.receipt_hash <> receipt_hash_value then
      if not diagnostic_present
         or receipt_row.provider_terminal_status is distinct from
           terminal_status_value
         or receipt_row.provider_error_code is distinct from
           provider_error_code_value
         or receipt_row.provider_error_type is distinct from
           provider_error_type_value
         or receipt_row.provider_error_message is distinct from
           provider_error_message_value
         or receipt_row.provider_message_present is distinct from
           provider_message_present_value
         or receipt_row.failure_code is distinct from failure_code_value
         or receipt_row.citation_count is distinct from citation_count_value then
        raise exception using
          errcode = '23505',
          message = 'research_provider_health_conflict';
      end if;
      -- Concurrent/repeated GET observers can have a later checked_at. The
      -- already-inserted terminal diagnostic is byte-for-byte equivalent in
      -- every semantic field, so return it without UPDATE or a second insert.
    end if;
    return jsonb_build_object(
      'ok', true,
      'receipt_id', receipt_row.id,
      'failure_code', receipt_row.failure_code,
      'provider_terminal_status', receipt_row.provider_terminal_status,
      'provider_diagnostic_code', receipt_row.provider_error_code
    );
  end if;

  insert into content_factory.research_provider_health_receipts (
    organization_id, run_id, attempt_id, provider_key, adapter_version,
    status, failure_code, citation_count, check_kind,
    provider_request_created, actual_cost_minor, checked_at, expires_at,
    provider_terminal_status, provider_error_code, provider_error_type,
    provider_error_message, provider_message_present, receipt_hash
  ) values (
    binding_row.organization_id, binding_row.run_id, binding_row.id,
    binding_row.provider_key, binding_row.adapter_version, status_value,
    failure_code_value, citation_count_value, 'passive_execution', false, 0,
    checked_at_value, expires_at_value, terminal_status_value,
    provider_error_code_value, provider_error_type_value,
    provider_error_message_value, provider_message_present_value,
    receipt_hash_value
  )
  returning * into receipt_row;

  return jsonb_build_object(
    'ok', true,
    'receipt_id', receipt_row.id,
    'failure_code', receipt_row.failure_code,
    'provider_terminal_status', receipt_row.provider_terminal_status,
    'provider_diagnostic_code', receipt_row.provider_error_code
  );
end;
$$;

revoke all on function public.system_record_research_provider_health(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_record_research_provider_health(jsonb)
  to service_role;

-- Preserve whatever provider-control implementation migration 014 installed,
-- then add only a run-scoped terminal diagnostic from the append-only receipt.
do $preserve_provider_status_before_terminal_diagnostics_v1$
begin
  if to_regprocedure(
    'content_factory_private.creator_research_provider_status_pre_terminal_diagnostics_v1(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_research_provider_status(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'creator_research_provider_status_missing';
    end if;
    alter function public.creator_research_provider_status(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_research_provider_status(jsonb)
      rename to creator_research_provider_status_pre_terminal_diagnostics_v1;
  end if;
end;
$preserve_provider_status_before_terminal_diagnostics_v1$;

revoke all on function content_factory_private
  .creator_research_provider_status_pre_terminal_diagnostics_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_research_provider_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result_value jsonb;
  actor_id_value uuid;
  organization_id_value uuid;
  run_id_value uuid;
  project_id_value uuid;
  terminal_diagnostic_value jsonb;
begin
  result_value := content_factory_private
    .creator_research_provider_status_pre_terminal_diagnostics_v1(p_payload);
  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000',
      message = 'research_provider_status_result_invalid';
  end if;
  begin
    organization_id_value := (result_value ->> 'organization_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000',
      message = 'research_provider_status_result_invalid';
  end;
  if organization_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'research_provider_status_result_invalid';
  end if;
  if nullif(btrim(coalesce(p_payload ->> 'run_id', '')), '') is null then
    return result_value;
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  actor_id_value := auth.uid();
  if actor_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'authentication_required';
  end if;
  select run.project_id into project_id_value
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value;
  if project_id_value is null then
    -- Preserve the legacy no-project status shape without adding the new
    -- terminal diagnostic. Current project-scoped runs must pass exact access.
    return result_value;
  end if;
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );

  select jsonb_build_object(
    'terminal_status', receipt.provider_terminal_status,
    'failure_code', receipt.failure_code,
    'diagnostic_code', receipt.provider_error_code,
    'diagnostic_type', receipt.provider_error_type,
    'diagnostic_message', receipt.provider_error_message,
    'provider_message_present', receipt.provider_message_present,
    'receipt_id', receipt.id,
    'checked_at', receipt.checked_at
  ) into terminal_diagnostic_value
  from content_factory.research_provider_health_receipts receipt
  where receipt.organization_id = organization_id_value
    and receipt.run_id = run_id_value
    and receipt.provider_terminal_status is not null
  order by receipt.checked_at desc, receipt.id desc
  limit 1;

  if terminal_diagnostic_value is not null then
    result_value := jsonb_set(
      result_value,
      '{response_state}',
      coalesce(result_value -> 'response_state', '{}'::jsonb)
        || jsonb_build_object(
          'terminal_diagnostic', terminal_diagnostic_value
        ),
      true
    );
  end if;
  return result_value;
end;
$$;

revoke all on function public.creator_research_provider_status(jsonb)
  from public, anon;
grant execute on function public.creator_research_provider_status(jsonb)
  to authenticated;

-- The exact-video keys are deliberately removed before the legacy starter
-- writes run.input, so run.input alone cannot survive reload as evidence.
-- Add a server-derived marker from the immutable exact binding to every
-- project-scoped status response; no sessionStorage inference is trusted.
do $preserve_project_status_before_exact_failure_marker_v1$
begin
  if to_regprocedure(
    'content_factory_private.creator_project_research_status_pre_exact_failure_marker_v1(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_project_research_status(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'creator_project_research_status_missing';
    end if;
    alter function public.creator_project_research_status(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_project_research_status(jsonb)
      rename to creator_project_research_status_pre_exact_failure_marker_v1;
  end if;
end;
$preserve_project_status_before_exact_failure_marker_v1$;

revoke all on function content_factory_private
  .creator_project_research_status_pre_exact_failure_marker_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_project_research_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result_value jsonb;
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  run_id_value uuid;
  exact_video_value jsonb;
begin
  result_value := content_factory_private
    .creator_project_research_status_pre_exact_failure_marker_v1(p_payload);
  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000',
      message = 'project_research_result_invalid';
  end if;
  -- The preserved project wrapper already authenticated membership and checked
  -- these exact payload ids. Derive organization ownership from the authoritative
  -- run row after that ACL check; do not trust a browser organization_id or expect
  -- the legacy result to expose one.
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  select run.organization_id into organization_id_value
  from content_factory.product_research_runs run
  where run.id = run_id_value
    and run.project_id = project_id_value;
  if organization_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'project_research_result_mismatch';
  end if;
  actor_id_value := content_factory_private.current_profile_id();
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );

  select jsonb_build_object(
    'verified', true,
    'marker_source', 'server_exact_video_binding',
    'binding_id', binding.id,
    'source_id', binding.source_id,
    'attachment_id', binding.attachment_id,
    'media_id', binding.media_object_id,
    'evidence_id', binding.evidence_set_id,
    'frame_count', binding.evidence_frame_count_snapshot,
    'analysis_scope', binding.analysis_scope,
    'full_stream_access', binding.full_stream_access,
    'transcript_available', binding.transcript_available,
    'media_matches_registered_source',
      binding.media_matches_registered_source
  ) into exact_video_value
  from content_factory.research_exact_youtube_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.run_id = run_id_value;

  result_value := result_value - 'exact_video';
  if exact_video_value is not null then
    result_value := result_value || jsonb_build_object(
      'exact_video', exact_video_value
    );
  end if;
  return result_value;
end;
$$;

revoke all on function public.creator_project_research_status(jsonb)
  from public, anon;
grant execute on function public.creator_project_research_status(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

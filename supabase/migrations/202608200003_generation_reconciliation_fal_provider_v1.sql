begin;

-- 202608200003_generation_reconciliation_fal_provider_v1
--
-- A strategy reconciliation confirmation names the provider whose dashboard
-- the owner/admin checked.  Treating every non-Google job as Runway made a fal
-- no-request decision carry a false RUNWAY_NO_TASK_VERIFIED assertion.  It
-- also let nullable JSON comparisons evaluate to SQL NULL and skip the old
-- payload guard.  Bind the confirmation to the provider frozen in the signed
-- readiness receipt, keep Runway unchanged, and fail closed for every unknown
-- provider or cross-provider token.

create or replace function
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      p_provider text,
      p_resolution text,
      p_confirmation text
    )
returns boolean
language sql
immutable
parallel safe
set search_path = ''
as $$
  select coalesce(case
    when p_provider = 'runway' and p_resolution = 'provider_task_attached'
      then p_confirmation = 'RUNWAY_TASK_ID_VERIFIED'
    when p_provider = 'runway' and p_resolution = 'confirmed_not_submitted'
      then p_confirmation = 'RUNWAY_NO_TASK_VERIFIED'
    when p_provider = 'fal' and p_resolution = 'provider_task_attached'
      then p_confirmation = 'FAL_REQUEST_ID_VERIFIED'
    when p_provider = 'fal' and p_resolution = 'confirmed_not_submitted'
      then p_confirmation = 'FAL_NO_REQUEST_VERIFIED'
    else false
  end, false);
$$;

revoke all on function
  content_factory_private
    .generation_strategy_reconciliation_confirmation_allowed(
      text, text, text
    )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.migration_patch_reconciliation_once(
    p_source text,
    p_search text,
    p_replace text,
    p_tag text
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  hits integer;
begin
  if p_source is null or p_search is null or length(p_search) = 0 then
    raise exception using
      message = 'reconciliation_patch_arguments_invalid:' || p_tag;
  end if;
  hits := (length(p_source) - length(replace(p_source, p_search, '')))
    / length(p_search);
  -- Some replacements deliberately retain their old anchor (for example the
  -- job SELECT is preceded by a receipt SELECT).  Recognize the full patched
  -- form first so a local verification replay cannot duplicate that block.
  if position(p_replace in p_source) > 0 then
    return p_source;
  end if;
  if hits <> 1 then
    raise exception using
      message = 'reconciliation_patch_anchor_invalid:' || p_tag || ':'
        || hits::text;
  end if;
  return replace(p_source, p_search, p_replace);
end;
$$;

-- The project-scoped public wrapper calls this preserved authority.  Add the
-- provider to its safe response and admit fal to the same owner/admin,
-- unresolved-job checks.  No provider request is made by this reader.
do $patch_legacy_reconciliation_context$
declare
  definition_value text;
  patched_value text;
begin
  definition_value := pg_get_functiondef(
    'content_factory_private.creator_real_generation_reconciliation_context_pre_project_v47(jsonb)'
      ::regprocedure
  );
  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      definition_value,
      $s$and job.provider = 'runway'$s$,
      $r$and job.provider in ('runway','fal')$r$,
      'legacy_context.provider_filter'
    );
  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$      'status', job_row.status,$s$,
      $r$      'status', job_row.status,
      'provider', job_row.provider,$r$,
      'legacy_context.provider_projection'
    );
  execute patched_value;
end;
$patch_legacy_reconciliation_context$;

-- Patch only the current authority (202608170005).  Applied historical
-- migrations remain byte-for-byte append-only.
do $patch_strategy_reconciliation$
declare
  definition_value text;
  patched_value text;
begin
  definition_value := replace(
    pg_get_functiondef(
      'public.system_reconcile_generation_strategy_dispatch(jsonb)'
        ::regprocedure
    ),
    E'\r\n',
    E'\n'
  );

  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      definition_value,
      $s$  claim_row content_factory.generation_strategy_start_claims%rowtype;
  job_row content_factory.generation_jobs%rowtype;$s$,
      $r$  claim_row content_factory.generation_strategy_start_claims%rowtype;
  receipt_row
    content_factory.generation_strategy_readiness_receipts%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  fal_request_hex_value text;
  fal_request_index_value integer;
  fal_request_nibble_value integer;
  fal_request_epoch_ms_value bigint;
  fal_request_created_at_value timestamptz;$r$,
      'strategy_reconcile.provider_declarations'
    );

  -- Required JSON values must be strings.  In particular JSON null must not
  -- turn `<> token` or `not in (...)` into SQL NULL and bypass the IF.
  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$     or jsonb_typeof(p_payload -> 'provider_status')
          not in ('string', 'null') then$s$,
      $r$     or jsonb_typeof(p_payload -> 'provider_status')
          not in ('string', 'null')
     or jsonb_typeof(p_payload -> 'version') <> 'string'
     or jsonb_typeof(p_payload -> 'resolution') <> 'string'
     or jsonb_typeof(p_payload -> 'external_evidence_hash') <> 'string'
     or jsonb_typeof(p_payload -> 'confirmation') <> 'string'
     or jsonb_typeof(p_payload -> 'idempotency_key') <> 'string' then$r$,
      'strategy_reconcile.required_json_types'
    );

  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$         or provider_status_value not in (
           'submitted', 'processing', 'succeeded', 'failed', 'cancelled'
         )$s$,
      $r$         or provider_status_value is null
         or provider_status_value not in (
           'submitted', 'processing', 'succeeded', 'failed', 'cancelled'
         )$r$,
      'strategy_reconcile.attach_status_not_null'
    );

  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$         or confirmation_value <> 'RUNWAY_TASK_ID_VERIFIED'$s$,
      $r$         or confirmation_value is null
         or confirmation_value not in (
           'RUNWAY_TASK_ID_VERIFIED', 'FAL_REQUEST_ID_VERIFIED'
         )$r$,
      'strategy_reconcile.attach_tokens'
    );
  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$         or confirmation_value <> 'RUNWAY_NO_TASK_VERIFIED'$s$,
      $r$         or confirmation_value is null
         or confirmation_value not in (
           'RUNWAY_NO_TASK_VERIFIED', 'FAL_NO_REQUEST_VERIFIED'
         )$r$,
      'strategy_reconcile.no_request_tokens'
    );

  -- Resolve provider from the claim's signed receipt, then require it to
  -- match the paid job.  The browser token can never choose a provider.
  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$    select job.* into job_row
    from content_factory.generation_jobs job$s$,
      $r$    select receipt.* into receipt_row
    from content_factory.generation_strategy_readiness_receipts receipt
    where receipt.organization_id = organization_id_value
      and receipt.project_id = project_id_value
      and receipt.id = claim_row.readiness_receipt_id
      and receipt.receipt_hash = claim_row.receipt_hash;
    select job.* into job_row
    from content_factory.generation_jobs job$r$,
      'strategy_reconcile.signed_receipt_provider'
    );

  patched_value := content_factory_private
    .migration_patch_reconciliation_once(
      patched_value,
      $s$    for update;
    begin
      starting_at_value := (job_row.output ->> 'starting_at')::timestamptz;$s$,
      $r$    for update;
    if job_row.id is null
       or receipt_row.id is null
       or receipt_row.provider is distinct from job_row.provider
       or not content_factory_private
         .generation_strategy_reconciliation_confirmation_allowed(
           receipt_row.provider, resolution_value, confirmation_value
         ) then
      raise exception using errcode = '55000',
        message = 'generation_strategy_dispatch_reconciliation_not_current';
    end if;
    if receipt_row.provider = 'fal'
       and resolution_value = 'provider_task_attached' then
      if provider_task_id_value is null
         or provider_task_id_value !~
           '^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      then
        raise exception using errcode = '55000',
          message = 'generation_strategy_dispatch_reconciliation_not_current';
      end if;
      fal_request_hex_value := left(
        replace(provider_task_id_value, '-', ''), 12
      );
      fal_request_epoch_ms_value := 0;
      for fal_request_index_value in 1..12 loop
        fal_request_nibble_value := strpos(
          '0123456789abcdef',
          substr(fal_request_hex_value, fal_request_index_value, 1)
        ) - 1;
        if fal_request_nibble_value < 0 then
          raise exception using errcode = '55000',
            message =
              'generation_strategy_dispatch_reconciliation_not_current';
        end if;
        fal_request_epoch_ms_value := fal_request_epoch_ms_value * 16
          + fal_request_nibble_value;
      end loop;
      fal_request_created_at_value := timestamptz 'epoch'
        + fal_request_epoch_ms_value * interval '1 millisecond';
      if provider_task_created_at_value is null
         or provider_task_created_at_value <
           fal_request_created_at_value - interval '1 millisecond'
         or provider_task_created_at_value >
           fal_request_created_at_value + interval '1 millisecond' then
        raise exception using errcode = '55000',
          message = 'generation_strategy_dispatch_reconciliation_not_current';
      end if;
    end if;
    begin
      starting_at_value := (job_row.output ->> 'starting_at')::timestamptz;$r$,
      'strategy_reconcile.provider_binding'
    );

  execute patched_value;
end;
$patch_strategy_reconciliation$;

drop function
  content_factory_private.migration_patch_reconciliation_once(
    text, text, text, text
  );

revoke all on function
  public.system_reconcile_generation_strategy_dispatch(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_reconcile_generation_strategy_dispatch(jsonb)
  to service_role;

do $generation_reconciliation_fal_provider_verify$
declare
  definition_value text;
  context_definition_value text;
  legacy_definition_value text;
begin
  -- Runway remains exact; fal cannot resolve it and vice versa.  Unknown and
  -- nullable providers/tokens are denied rather than guessed.
  if not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'runway', 'provider_task_attached', 'RUNWAY_TASK_ID_VERIFIED'
       )
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'runway', 'confirmed_not_submitted', 'RUNWAY_NO_TASK_VERIFIED'
       )
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'fal', 'provider_task_attached', 'FAL_REQUEST_ID_VERIFIED'
       )
     or not content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'fal', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED'
       )
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'runway', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED'
       )
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'fal', 'confirmed_not_submitted', 'RUNWAY_NO_TASK_VERIFIED'
       )
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         'unknown', 'confirmed_not_submitted', 'FAL_NO_REQUEST_VERIFIED'
       )
     or content_factory_private
       .generation_strategy_reconciliation_confirmation_allowed(
         null, null, null
       ) then
    raise exception using message =
      'generation_reconciliation_confirmation_matrix_invalid';
  end if;

  definition_value := pg_get_functiondef(
    'public.system_reconcile_generation_strategy_dispatch(jsonb)'
      ::regprocedure
  );
  if position($v$jsonb_typeof(p_payload -> 'confirmation') <> 'string'$v$
       in definition_value) = 0
     or position($v$jsonb_typeof(p_payload -> 'version') <> 'string'$v$
       in definition_value) = 0
     or position('confirmation_value is null' in definition_value) = 0
     or position('provider_status_value is null' in definition_value) = 0
     or position('FAL_NO_REQUEST_VERIFIED' in definition_value) = 0
     or position('FAL_REQUEST_ID_VERIFIED' in definition_value) = 0
     or position('receipt.receipt_hash = claim_row.receipt_hash'
       in definition_value) = 0
     or position('receipt_row.provider is distinct from job_row.provider'
       in definition_value) = 0
     or position('generation_strategy_reconciliation_confirmation_allowed'
       in definition_value) = 0
     or position('fal_request_epoch_ms_value' in definition_value) = 0
     or position('starting_at_value - interval ''2 minutes'''
       in definition_value) = 0
     or position('starting_at_value + interval ''10 minutes'''
       in definition_value) = 0 then
    raise exception using message =
      'generation_reconciliation_provider_binding_missing';
  end if;

  context_definition_value := pg_get_functiondef(
    'content_factory_private.creator_real_generation_reconciliation_context_pre_project_v47(jsonb)'
      ::regprocedure
  );
  if position($v$job.provider in ('runway','fal')$v$
       in context_definition_value) = 0
     or position($v$'provider', job_row.provider$v$
       in context_definition_value) = 0 then
    raise exception using message =
      'legacy_reconciliation_fal_context_missing';
  end if;

  -- 202608190012 is the current legacy writer.  Keep both exact providers and
  -- do not weaken the rest of the legacy reconciliation transaction.
  legacy_definition_value := pg_get_functiondef(
    'public.system_reconcile_real_generation(jsonb)'::regprocedure
  );
  if position($v$job_row.provider not in ('runway','fal')$v$
       in legacy_definition_value) = 0
     or position($v$batch_row.provider not in ('runway','fal')$v$
       in legacy_definition_value) = 0
     or position('real_generation_reconciliation_task_time_mismatch'
       in legacy_definition_value) = 0 then
    raise exception using message =
      'legacy_reconciliation_provider_set_lost';
  end if;
end;
$generation_reconciliation_fal_provider_verify$;

commit;

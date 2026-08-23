begin;

-- 202608200004_generation_strategy_archive_provider_truth_v1
--
-- Strategy execution was originally Runway-only.  The archive projection and
-- its enrichment wrapper therefore wrote `runway` for every strategy row.
-- Once a signed fal route was introduced, that historical fallback made an
-- unresolved fal request render a Runway reconciliation form.  It also made a
-- provider=fal archive filter omit the paid row entirely.
--
-- The batch provider is the exact provider persisted by the paid claim and is
-- available inside the paginated base reader.  The wrapper has the stronger
-- signed readiness receipt, so its public projection uses that provider and
-- requires both authorities to agree.  Existing Runway rows remain Runway.
-- The base reader also projects the immutable job identity at the top level:
-- legacy launches get it from their selection snapshot and strategy launches
-- get it from their strategy snapshot.  The browser can therefore choose the
-- correct status contract without trusting client-authored parameters.

create or replace function
  content_factory_private.migration_patch_archive_provider_once(
    p_source text,
    p_search text,
    p_replace text,
    p_expected_hits integer,
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
  if p_source is null
     or p_search is null
     or length(p_search) = 0
     or p_expected_hits < 1 then
    raise exception using
      message = 'archive_provider_patch_arguments_invalid:' || p_tag;
  end if;
  hits := (length(p_source) - length(replace(p_source, p_search, '')))
    / length(p_search);
  if hits <> p_expected_hits then
    raise exception using
      message = 'archive_provider_patch_anchor_invalid:' || p_tag || ':'
        || hits::text;
  end if;
  return replace(p_source, p_search, p_replace);
end;
$$;

-- Patch the preserved, paginated archive reader.  Its strategy fallback is
-- used both in the projected provider and in the provider filter, hence the
-- exact two-hit assertion.  A third occurrence or a missing occurrence means
-- the authority changed and this migration must stop rather than guess.
do $patch_generation_archive_base_provider$
declare
  definition_value text;
  patched_value text;
begin
  definition_value := replace(
    pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    ),
    E'\r\n',
    E'\n'
  );
  patched_value := content_factory_private
    .migration_patch_archive_provider_once(
      definition_value,
      $old$coalesce(launch.provider, case when strategy_snapshot.id is not null then 'runway' end)$old$,
      $new$case when strategy_snapshot.id is not null then batch.provider else launch.provider end$new$,
      2,
      'archive_base.strategy_provider'
    );
  patched_value := content_factory_private
    .migration_patch_archive_provider_once(
      patched_value,
      $old$provider_value not in ('all', 'runway', 'google')$old$,
      $new$provider_value not in ('all', 'runway', 'google', 'fal')$new$,
      1,
      'archive_base.provider_input'
    );
  patched_value := content_factory_private
    .migration_patch_archive_provider_once(
      patched_value,
      $old$      batch.input,
      batch.created_at,$old$,
      $new$      batch.input,
      coalesce(
        launch.generation_job_id,
        strategy_snapshot.generation_job_id
      ) as generation_job_id,
      batch.created_at,$new$,
      1,
      'archive_base.generation_job_id_select'
    );
  patched_value := content_factory_private
    .migration_patch_archive_provider_once(
      patched_value,
      $old$        'parameters', page.input,$old$,
      $new$        'parameters', page.input,
        'generation_job_id', page.generation_job_id,$new$,
      1,
      'archive_base.generation_job_id_projection'
    );
  execute patched_value;
end;
$patch_generation_archive_base_provider$;

-- Patch the public enrichment wrapper.  The receipt is immutable, signed and
-- already tied to this claim.  Requiring it to equal the base batch provider
-- makes a corrupt or partially deployed route fail closed instead of showing
-- a reconciliation form for the wrong provider.
do $patch_generation_archive_receipt_provider$
declare
  definition_value text;
  patched_value text;
begin
  definition_value := replace(
    pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    ),
    E'\r\n',
    E'\n'
  );
  patched_value := content_factory_private
    .migration_patch_archive_provider_once(
      definition_value,
      $old$        and receipt.id = claim_row.readiness_receipt_id;
      select coalesce(jsonb_object_agg(key_value, false), '{}'::jsonb)$old$,
      $new$        and receipt.id = claim_row.readiness_receipt_id;
      if receipt_row.id is null
         or receipt_row.provider is distinct from batch_value ->> 'provider'
      then
        raise exception using errcode = '55000',
          message = 'generation_strategy_archive_provider_mismatch';
      end if;
      select coalesce(jsonb_object_agg(key_value, false), '{}'::jsonb)$new$,
      1,
      'archive_wrapper.provider_consistency'
    );
  patched_value := content_factory_private
    .migration_patch_archive_provider_once(
      patched_value,
      $old$        'provider', 'runway',$old$,
      $new$        'provider', receipt_row.provider,$new$,
      1,
      'archive_wrapper.provider_projection'
    );
  execute patched_value;
end;
$patch_generation_archive_receipt_provider$;

drop function
  content_factory_private.migration_patch_archive_provider_once(
    text, text, text, integer, text
  );

do $generation_strategy_archive_provider_truth_verify$
declare
  base_definition text;
  base_compact text;
  wrapper_definition text;
  wrapper_compact text;
  batch_provider_hits integer;
  generation_job_select_hits integer;
  generation_job_projection_hits integer;
begin
  base_definition := pg_get_functiondef(
    'public.creator_generation_archive_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  wrapper_definition := pg_get_functiondef(
    'public.creator_generation_archive(jsonb)'::regprocedure
  );
  -- pg_get_functiondef() is allowed to pretty-print parentheses and CASE
  -- expressions differently from the source text.  Verify the installed
  -- semantics after removing insignificant whitespace so a successful patch
  -- cannot be rejected merely because PostgreSQL formatted COALESCE as
  -- `coalesce( ... )`.
  base_compact := lower(regexp_replace(
    base_definition,
    '[[:space:]]+',
    '',
    'g'
  ));
  wrapper_compact := lower(regexp_replace(
    wrapper_definition,
    '[[:space:]]+',
    '',
    'g'
  ));
  batch_provider_hits := (
    length(base_compact) - length(replace(
      base_compact,
      'casewhenstrategy_snapshot.idisnotnullthenbatch.providerelselaunch.providerend',
      ''
    ))
  ) / length(
    'casewhenstrategy_snapshot.idisnotnullthenbatch.providerelselaunch.providerend'
  );
  generation_job_select_hits := (
    length(base_compact) - length(replace(
      base_compact,
      $v$coalesce(launch.generation_job_id,strategy_snapshot.generation_job_id)asgeneration_job_id$v$,
      ''
    ))
  ) / length(
    $v$coalesce(launch.generation_job_id,strategy_snapshot.generation_job_id)asgeneration_job_id$v$
  );
  generation_job_projection_hits := (
    length(base_compact) - length(replace(
      base_compact,
      $v$'generation_job_id',page.generation_job_id$v$,
      ''
    ))
  ) / length($v$'generation_job_id',page.generation_job_id$v$);
  if batch_provider_hits <> 2
     or generation_job_select_hits <> 1
     or generation_job_projection_hits <> 1
     or position(
       $v$provider_valuenotin('all','runway','google','fal')$v$
       in base_compact
     ) = 0
     or position(
       $v$coalesce(launch.provider,casewhenstrategy_snapshot.idisnotnullthen'runway'end)$v$
       in base_compact
     ) > 0 then
    raise exception using
      message = 'generation_strategy_archive_base_provider_truth_missing';
  end if;
  if position(
       $v$'provider',receipt_row.provider$v$ in wrapper_compact
     ) = 0
     or position(
       $v$receipt_row.providerisdistinctfrombatch_value->>'provider'$v$
       in wrapper_compact
     ) = 0
     or position(
       $v$'provider','runway'$v$ in wrapper_compact
     ) > 0 then
    raise exception using
      message = 'generation_strategy_archive_receipt_provider_truth_missing';
  end if;
end;
$generation_strategy_archive_provider_truth_verify$;

commit;

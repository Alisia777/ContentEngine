begin;

-- Repair the provider-control wrapper for already-installed databases.  The
-- original wrapper used a PL/pgSQL variable named organization_id together
-- with an inferred ON CONFLICT column list.  Under #variable_conflict
-- use_variable PostgreSQL interpreted one conflict target as the variable and
-- rejected every paid research start (including a saved stage recompute) with
-- SQLSTATE 42P10.  A named constraint and an unambiguous variable preserve the
-- one-authorization invariant on both upgraded and fresh databases.
create or replace function public.creator_start_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id_value uuid;
  delegated_payload jsonb;
  result_value jsonb;
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  authorized_at_value timestamptz;
  authorization_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'paid_analysis_ack')
     or jsonb_typeof(p_payload -> 'paid_analysis_ack') <> 'boolean'
     or p_payload -> 'paid_analysis_ack' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'paid_analysis_ack_required';
  end if;

  delegated_payload := p_payload - 'paid_analysis_ack';
  user_id := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(delegated_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer']
  );

  result_value := content_factory_private
    .creator_start_product_research_pre_provider_control(delegated_payload);
  begin
    run_id_value := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000',
      message = 'research_start_result_invalid';
  end;
  if run_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'research_start_result_invalid';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_start_result_invalid';
  end if;

  authorized_at_value := clock_timestamp();
  authorization_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'research-execution-authorization-v1',
      'organization_id', organization_id_value,
      'run_id', run_id_value,
      'authorized_by', user_id,
      'authorization_kind', 'explicit_paid_analysis',
      'paid_analysis_ack', true,
      'provider_key', 'openai_web_search',
      'adapter_version', 'openai-responses-web-search-v1',
      'run_request_hash', run_row.request_hash,
      'max_provider_attempts', 1,
      'automatic_fallback_allowed', false,
      'reason_code', 'user_confirmed_paid_analysis',
      'authorized_at', authorized_at_value
    )
  );

  insert into content_factory.research_execution_authorizations (
    organization_id, run_id, authorized_by, authorization_kind,
    paid_analysis_ack, provider_key, adapter_version, run_request_hash,
    max_provider_attempts, automatic_fallback_allowed, reason_code,
    authorized_at, authorization_hash
  ) values (
    organization_id_value, run_id_value, user_id, 'explicit_paid_analysis',
    true, 'openai_web_search', 'openai-responses-web-search-v1',
    run_row.request_hash, 1, false, 'user_confirmed_paid_analysis',
    authorized_at_value, authorization_hash_value
  )
  on conflict on constraint
    research_execution_authorizations_organization_id_run_id_key
  do nothing;

  if not exists (
    select 1
    from content_factory.research_execution_authorizations authorization_entry
    where authorization_entry.organization_id = organization_id_value
      and authorization_entry.run_id = run_id_value
      and authorization_entry.run_request_hash = run_row.request_hash
      and authorization_entry.provider_key = 'openai_web_search'
      and authorization_entry.adapter_version =
        'openai-responses-web-search-v1'
      and authorization_entry.max_provider_attempts = 1
      and not authorization_entry.automatic_fallback_allowed
  ) then
    raise exception using
      errcode = '55000',
      message = 'research_execution_authorization_conflict';
  end if;

  return result_value;
end;
$$;

-- A stage is correctable only when the exact inputs that produced an artifact
-- are durable.  Content equality alone is insufficient: the same JSON under a
-- different source/upstream set must be a distinct version and must not clear
-- a stale dependency by accident.

alter table content_factory.research_stage_artifacts
  add column if not exists input_dependencies jsonb;
alter table content_factory.research_stage_artifacts
  add column if not exists input_dependency_hash text;

drop trigger if exists reject_research_stage_artifact_mutation
  on content_factory.research_stage_artifacts;

do $research_stage_artifact_input_backfill$
declare
  artifact_row content_factory.research_stage_artifacts%rowtype;
  binding_row content_factory.research_stage_draft_bindings%rowtype;
  evidence_value jsonb;
  upstream_value jsonb;
  dependencies_value jsonb;
begin
  for artifact_row in
    select artifact.*
    from content_factory.research_stage_artifacts artifact
    where artifact.input_dependencies is null
       or artifact.input_dependency_hash is null
    order by artifact.organization_id, artifact.run_id,
      content_factory_private.research_stage_rank(artifact.stage),
      artifact.version, artifact.id
  loop
    select binding.* into binding_row
    from content_factory.research_stage_draft_bindings binding
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = binding.organization_id
     and draft.run_id = binding.run_id
     and draft.id = binding.draft_id
    where binding.organization_id = artifact_row.organization_id
      and binding.run_id = artifact_row.run_id
      and binding.stage = artifact_row.stage
      and binding.artifact_id = artifact_row.id
    order by draft.version, binding.bound_at, binding.draft_id
    limit 1;
    if binding_row.artifact_id is null then
      raise exception using
        errcode = '55000',
        message = 'research_stage_artifact_input_backfill_missing';
    end if;

    select coalesce(jsonb_agg(jsonb_build_object(
      'source_id', evidence.source_id,
      'content_hash', source.content_hash
    ) order by evidence.ordinal), '[]'::jsonb)
      into evidence_value
    from content_factory.research_stage_binding_evidence evidence
    join content_factory.product_research_sources source
      on source.organization_id = evidence.organization_id
     and source.run_id = evidence.run_id
     and source.id = evidence.source_id
    where evidence.organization_id = binding_row.organization_id
      and evidence.run_id = binding_row.run_id
      and evidence.draft_id = binding_row.draft_id
      and evidence.stage = binding_row.stage
      and evidence.artifact_id = binding_row.artifact_id;

    select coalesce(jsonb_agg(jsonb_build_object(
      'stage', upstream_binding.stage,
      'artifact_id', upstream_binding.artifact_id,
      'content_hash', upstream_artifact.content_hash,
      'input_dependency_hash', upstream_artifact.input_dependency_hash
    ) order by content_factory_private.research_stage_rank(
      upstream_binding.stage
    )), '[]'::jsonb)
      into upstream_value
    from content_factory.research_stage_draft_bindings upstream_binding
    join content_factory.research_stage_artifacts upstream_artifact
      on upstream_artifact.organization_id = upstream_binding.organization_id
     and upstream_artifact.run_id = upstream_binding.run_id
     and upstream_artifact.stage = upstream_binding.stage
     and upstream_artifact.id = upstream_binding.artifact_id
    where upstream_binding.organization_id = binding_row.organization_id
      and upstream_binding.run_id = binding_row.run_id
      and upstream_binding.draft_id = binding_row.draft_id
      and content_factory_private.research_stage_rank(upstream_binding.stage)
        < content_factory_private.research_stage_rank(binding_row.stage);

    -- Older upstream artifacts may be visited later in this backfill.  Their
    -- dependency hash is therefore intentionally excluded from the canonical
    -- v2 input envelope; exact artifact IDs and content hashes are sufficient
    -- and stable.
    upstream_value := coalesce((
      select jsonb_agg(
        upstream_entry.value - 'input_dependency_hash'
        order by content_factory_private.research_stage_rank(
          upstream_entry.value ->> 'stage'
        )
      )
      from jsonb_array_elements(upstream_value) upstream_entry(value)
    ), '[]'::jsonb);
    dependencies_value := jsonb_build_object(
      'schema_version', 'research-stage-input-v2',
      'evidence', evidence_value,
      'upstream_artifacts', upstream_value
    );

    update content_factory.research_stage_artifacts artifact
    set input_dependencies = dependencies_value,
        input_dependency_hash =
          content_factory_private.json_hash(jsonb_build_object(
            'evidence', evidence_value,
            'upstream_artifacts', upstream_value
          ))
    where artifact.organization_id = artifact_row.organization_id
      and artifact.id = artifact_row.id;
  end loop;
end;
$research_stage_artifact_input_backfill$;

alter table content_factory.research_stage_artifacts
  alter column input_dependencies set not null;
alter table content_factory.research_stage_artifacts
  alter column input_dependency_hash set not null;
alter table content_factory.research_stage_artifacts
  add constraint research_stage_artifact_input_dependencies_check
  check (
    jsonb_typeof(input_dependencies) = 'object'
    and input_dependencies ->> 'schema_version' = 'research-stage-input-v2'
    and jsonb_typeof(input_dependencies -> 'evidence') = 'array'
    and jsonb_typeof(input_dependencies -> 'upstream_artifacts') = 'array'
    and jsonb_array_length(input_dependencies -> 'evidence') between 1 and 100
    and jsonb_array_length(input_dependencies -> 'upstream_artifacts') between 0 and 6
    and length(input_dependencies::text) <= 262144
  );
alter table content_factory.research_stage_artifacts
  add constraint research_stage_artifact_input_dependency_hash_check
  check (input_dependency_hash ~ '^[0-9a-f]{64}$');

alter table content_factory.research_stage_artifacts
  drop constraint if exists research_stage_artifacts_run_stage_content_uq;
drop index if exists content_factory.research_stage_artifacts_run_stage_content_uq;
alter table content_factory.research_stage_artifacts
  add constraint research_stage_artifacts_run_stage_content_input_uq
  unique (
    organization_id, run_id, stage, content_hash, input_dependency_hash
  );

create trigger reject_research_stage_artifact_mutation
before update or delete on content_factory.research_stage_artifacts
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

-- Rebuild capture so input dependencies are known before artifact identity is
-- selected.  Existing immutable rows remain valid; new rows use content+input.
create or replace function content_factory_private.capture_research_stage_draft(
  draft_row content_factory.creative_brief_drafts
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  stage_value text;
  payload_value jsonb;
  content_hash_value text;
  dependency_hash_value text;
  dependencies_value jsonb;
  all_evidence_source_ids uuid[];
  evidence_source_ids uuid[];
  stage_source_refs text[];
  evidence_count integer;
  evidence_payload jsonb;
  upstream_payload jsonb;
  artifact_id_value uuid;
  parent_artifact_id_value uuid;
  previous_artifact_id_value uuid;
  previous_content_hash_value text;
  version_value integer;
  explicit_payload_change boolean;
  control_action_value text := coalesce(nullif(current_setting(
    'content_factory.research_stage_action', true
  ), ''), 'patch');
  target_stage_value text := nullif(current_setting(
    'content_factory.research_stage_target', true
  ), '');
begin
  perform pg_advisory_xact_lock(
    hashtext(draft_row.organization_id::text),
    hashtext('research-stage-ledger:' || draft_row.run_id::text)
  );

  select coalesce(
    array_agg(source_ref.source_id order by source_ref.source_id),
    '{}'::uuid[]
  ) into all_evidence_source_ids
  from (
    select distinct element.value::uuid as source_id
    from jsonb_array_elements_text(draft_row.source_ids) as element(value)
  ) source_ref;

  select count(*)::integer into evidence_count
  from content_factory.product_research_sources source
  where source.organization_id = draft_row.organization_id
    and source.run_id = draft_row.run_id
    and source.id = any(all_evidence_source_ids);
  if evidence_count <> cardinality(all_evidence_source_ids)
     or evidence_count < 1 then
    raise exception using
      errcode = '42501', message = 'research_stage_evidence_mismatch';
  end if;

  foreach stage_value in array array[
    'sources', 'category', 'competitors', 'trends',
    'guidance', 'brief', 'scenarios'
  ] loop
    payload_value := content_factory_private.research_stage_payload(
      draft_row, stage_value
    );
    if payload_value is null then
      raise exception using
        errcode = '22023', message = 'research_stage_payload_invalid';
    end if;

    stage_source_refs :=
      content_factory_private.research_stage_source_refs(payload_value);
    if stage_value = 'sources' or cardinality(stage_source_refs) = 0 then
      evidence_source_ids := all_evidence_source_ids;
    else
      if exists (
        select 1
        from unnest(stage_source_refs) source_ref(value)
        where (
          select count(*)
          from content_factory.product_research_sources source
          where source.organization_id = draft_row.organization_id
            and source.run_id = draft_row.run_id
            and source.id = any(all_evidence_source_ids)
            and (
              source.id::text = source_ref.value
              or source.metadata ->> 'model_source_id' = source_ref.value
            )
        ) <> 1
      ) then
        raise exception using
          errcode = '42501',
          message = 'research_stage_source_reference_mismatch';
      end if;
      select coalesce(
        array_agg(distinct source.id order by source.id), '{}'::uuid[]
      ) into evidence_source_ids
      from unnest(stage_source_refs) source_ref(value)
      join content_factory.product_research_sources source
        on source.organization_id = draft_row.organization_id
       and source.run_id = draft_row.run_id
       and source.id = any(all_evidence_source_ids)
       and (
         source.id::text = source_ref.value
         or source.metadata ->> 'model_source_id' = source_ref.value
       );
    end if;

    select count(*)::integer,
      coalesce(jsonb_agg(jsonb_build_object(
        'source_id', source.id,
        'content_hash', source.content_hash
      ) order by source.id), '[]'::jsonb)
      into evidence_count, evidence_payload
    from content_factory.product_research_sources source
    where source.organization_id = draft_row.organization_id
      and source.run_id = draft_row.run_id
      and source.id = any(evidence_source_ids);
    if evidence_count <> cardinality(evidence_source_ids)
       or evidence_count < 1 then
      raise exception using
        errcode = '42501', message = 'research_stage_evidence_mismatch';
    end if;

    select coalesce(jsonb_agg(jsonb_build_object(
      'stage', binding.stage,
      'artifact_id', binding.artifact_id,
      'content_hash', artifact.content_hash
    ) order by content_factory_private.research_stage_rank(binding.stage)),
      '[]'::jsonb)
      into upstream_payload
    from content_factory.research_stage_draft_bindings binding
    join content_factory.research_stage_artifacts artifact
      on artifact.organization_id = binding.organization_id
     and artifact.run_id = binding.run_id
     and artifact.stage = binding.stage
     and artifact.id = binding.artifact_id
    where binding.organization_id = draft_row.organization_id
      and binding.run_id = draft_row.run_id
      and binding.draft_id = draft_row.id
      and content_factory_private.research_stage_rank(binding.stage)
        < content_factory_private.research_stage_rank(stage_value);

    dependencies_value := jsonb_build_object(
      'schema_version', 'research-stage-input-v2',
      'evidence', evidence_payload,
      'upstream_artifacts', upstream_payload
    );
    -- Keep migration 001's public dependency-hash contract byte-for-byte;
    -- schema_version describes the stored envelope but is not part of the
    -- legacy/current binding hash.
    dependency_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'evidence', evidence_payload,
        'upstream_artifacts', upstream_payload
      )
    );
    content_hash_value := content_factory_private.json_hash(payload_value);
    artifact_id_value := null;
    parent_artifact_id_value := null;
    previous_artifact_id_value := null;
    previous_content_hash_value := null;
    if draft_row.previous_draft_id is not null then
      select binding.artifact_id, artifact.content_hash
        into previous_artifact_id_value, previous_content_hash_value
      from content_factory.research_stage_draft_bindings binding
      join content_factory.research_stage_artifacts artifact
        on artifact.organization_id = binding.organization_id
       and artifact.run_id = binding.run_id
       and artifact.stage = binding.stage
       and artifact.id = binding.artifact_id
      where binding.organization_id = draft_row.organization_id
        and binding.run_id = draft_row.run_id
        and binding.draft_id = draft_row.previous_draft_id
        and binding.stage = stage_value;
    end if;
    explicit_payload_change := previous_artifact_id_value is null
      or previous_content_hash_value is distinct from content_hash_value;

    -- A human patch/revert only rebinds its explicit target.  Every other
    -- unchanged stage keeps the exact previous artifact/input snapshot, even
    -- if it was already stale before this draft.  This prevents an unrelated
    -- later patch (for example, brief after category) from silently healing
    -- competitor/trend provenance merely by minting the same payload under a
    -- newer dependency hash.  An explicit target remains the sole exception,
    -- so patch/revert of identical JSON can deliberately repair that stage.
    if control_action_value <> 'recompute_completed'
       and previous_artifact_id_value is not null
       and not explicit_payload_change
       and stage_value is distinct from target_stage_value then
      artifact_id_value := previous_artifact_id_value;
    end if;

    if artifact_id_value is null then
      select artifact.id into artifact_id_value
      from content_factory.research_stage_artifacts artifact
      where artifact.organization_id = draft_row.organization_id
        and artifact.run_id = draft_row.run_id
        and artifact.stage = stage_value
        and artifact.content_hash = content_hash_value
        and artifact.input_dependency_hash = dependency_hash_value;
    end if;

    if artifact_id_value is null then
      parent_artifact_id_value := previous_artifact_id_value;
      if parent_artifact_id_value is null then
        select artifact.id into parent_artifact_id_value
        from content_factory.research_stage_artifacts artifact
        where artifact.organization_id = draft_row.organization_id
          and artifact.run_id = draft_row.run_id
          and artifact.stage = stage_value
        order by artifact.version desc, artifact.id desc
        limit 1;
      end if;
      select coalesce(max(artifact.version), 0) + 1 into version_value
      from content_factory.research_stage_artifacts artifact
      where artifact.organization_id = draft_row.organization_id
        and artifact.run_id = draft_row.run_id
        and artifact.stage = stage_value;

      insert into content_factory.research_stage_artifacts (
        organization_id, run_id, stage, version, parent_artifact_id,
        payload, content_hash, input_dependencies, input_dependency_hash,
        actor_id, origin, created_at
      ) values (
        draft_row.organization_id, draft_row.run_id, stage_value, version_value,
        parent_artifact_id_value, payload_value, content_hash_value,
        dependencies_value, dependency_hash_value, draft_row.created_by,
        draft_row.origin, draft_row.created_at
      )
      on conflict (
        organization_id, run_id, stage, content_hash, input_dependency_hash
      ) do nothing
      returning id into artifact_id_value;
      if artifact_id_value is null then
        select artifact.id into artifact_id_value
        from content_factory.research_stage_artifacts artifact
        where artifact.organization_id = draft_row.organization_id
          and artifact.run_id = draft_row.run_id
          and artifact.stage = stage_value
          and artifact.content_hash = content_hash_value
          and artifact.input_dependency_hash = dependency_hash_value;
      end if;
    end if;

    insert into content_factory.research_stage_draft_bindings (
      organization_id, run_id, draft_id, stage, artifact_id,
      dependency_hash, actor_id, origin, bound_at
    ) values (
      draft_row.organization_id, draft_row.run_id, draft_row.id, stage_value,
      artifact_id_value, dependency_hash_value, draft_row.created_by,
      draft_row.origin, draft_row.created_at
    )
    on conflict (organization_id, draft_id, stage) do nothing;

    insert into content_factory.research_stage_binding_evidence (
      organization_id, run_id, draft_id, stage, artifact_id,
      source_id, ordinal, created_at
    )
    select draft_row.organization_id, draft_row.run_id, draft_row.id,
      stage_value, artifact_id_value, source_ref.source_id,
      source_ref.ordinal::integer, draft_row.created_at
    from unnest(evidence_source_ids) with ordinality
      as source_ref(source_id, ordinal)
    on conflict (organization_id, draft_id, stage, source_id) do nothing;
  end loop;

  perform content_factory_private.record_research_stage_decisions(
    draft_row,
    case when draft_row.origin = 'ai' then 'generated' else 'patched' end,
    draft_row.created_by, draft_row.origin, draft_row.created_at
  );
  if draft_row.status = 'approved' then
    perform content_factory_private.record_research_stage_decisions(
      draft_row, 'approved', draft_row.approved_by, 'human',
      draft_row.approved_at
    );
  end if;
end;
$$;

-- Snapshot-backed drafts may contain corrected v2 sections.  Legacy drafts
-- retain migration 001's immutability contract byte-for-byte.
create or replace function content_factory_private.guard_research_guidance_approval()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  guidance_value jsonb;
  guidance_status_value text;
  decision_value jsonb;
  strategy_value text;
  reference_draft_id uuid;
  reference_brief jsonb;
  reference_source_ids jsonb;
  snapshot_backed boolean := false;
begin
  if old.status = 'draft' and new.status = 'approved' then
    snapshot_backed := exists (
      select 1
      from content_factory.research_stage_branches branch
      join content_factory.research_stage_heads head
        on head.organization_id = branch.organization_id
       and head.run_id = branch.run_id
       and head.branch_id = branch.id
      where branch.organization_id = new.organization_id
        and branch.run_id = new.run_id
        and branch.branch_key = 'main'
        and head.current_draft_id = new.id
    );
    select draft.id, draft.brief, draft.source_ids
      into reference_draft_id, reference_brief, reference_source_ids
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = new.organization_id
      and draft.run_id = new.run_id
      and draft.id <> new.id
      and draft.version < new.version
      and content_factory_private.research_brief_has_v2_sections(draft.brief)
    order by case when draft.origin = 'ai' then 0 else 1 end,
      draft.version desc, draft.id
    limit 1;

    if reference_draft_id is not null
       or content_factory_private.research_brief_has_v2_sections(new.brief) then
      if new.origin <> 'human' then
        raise exception using
          errcode = '55000', message = 'research_v2_human_draft_required';
      end if;
      if not snapshot_backed then
        if reference_draft_id is null then
          raise exception using
            errcode = '55000',
            message = 'research_v2_evidence_reference_missing';
        end if;
        if not content_factory_private.research_brief_has_v2_sections(new.brief)
           or content_factory_private.research_v2_sections(new.brief)
             is distinct from
           content_factory_private.research_v2_sections(reference_brief)
           or content_factory_private.canonical_research_source_ids(
             new.source_ids
           ) is distinct from
           content_factory_private.canonical_research_source_ids(
             reference_source_ids
           ) then
          raise exception using
            errcode = '55000', message = 'research_v2_evidence_immutable';
        end if;
      end if;
    end if;

    guidance_value := new.brief -> 'guidance';
    if jsonb_typeof(guidance_value) = 'object' then
      guidance_status_value := btrim(coalesce(
        guidance_value ->> 'status', ''
      ));
      if guidance_status_value <> 'ready_for_brief' then
        decision_value := new.brief -> 'human_research_decision';
        strategy_value := btrim(coalesce(decision_value ->> 'strategy', ''));
        if jsonb_typeof(decision_value) is distinct from 'object'
           or jsonb_typeof(decision_value -> 'guidance_status')
             is distinct from 'string'
           or btrim(coalesce(decision_value ->> 'guidance_status', ''))
             <> guidance_status_value
           or decision_value -> 'cold_start_override'
             is distinct from 'true'::jsonb
           or jsonb_typeof(decision_value -> 'strategy')
             is distinct from 'string'
           or length(strategy_value) not between 1 and 2000 then
          raise exception using
            errcode = '55000',
            message = 'research_guidance_approval_override_required';
        end if;
      end if;
    end if;
  end if;
  return new;
end;
$$;

create or replace function
  content_factory_private.assert_research_stage_draft_ready(
    organization_id_value uuid,
    draft_id_value uuid
  )
returns void
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  draft_row content_factory.creative_brief_drafts%rowtype;
  branch_id_value uuid;
  head_count integer;
  exact_count integer;
  rejected_count integer;
  stale_count integer;
begin
  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.id = draft_id_value;
  if draft_row.id is null then
    raise exception using
      errcode = '22023', message = 'creative_brief_not_found';
  end if;
  if not content_factory_private.research_brief_has_v2_sections(
    draft_row.brief
  ) then
    return;
  end if;
  select branch.id into branch_id_value
  from content_factory.research_stage_branches branch
  where branch.organization_id = organization_id_value
    and branch.run_id = draft_row.run_id
    and branch.branch_key = 'main';
  if branch_id_value is null then
    raise exception using
      errcode = '55000', message = 'research_stage_snapshot_missing';
  end if;
  select count(*)::integer,
    count(*) filter (where head.state = 'rejected')::integer,
    count(*) filter (where head.state <> 'current')::integer
    into head_count, rejected_count, stale_count
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = draft_row.run_id
    and head.branch_id = branch_id_value
    and head.current_draft_id = draft_id_value;
  if rejected_count > 0 then
    raise exception using
      errcode = '55000', message = 'research_stage_rejected';
  end if;
  if head_count <> 7 or stale_count > 0 then
    raise exception using
      errcode = '55000', message = 'research_stage_dependencies_stale';
  end if;
  select count(*)::integer into exact_count
  from content_factory.research_stage_heads head
  join content_factory.research_stage_draft_bindings binding
    on binding.organization_id = head.organization_id
   and binding.run_id = head.run_id
   and binding.draft_id = draft_id_value
   and binding.stage = head.stage
   and binding.artifact_id = head.artifact_id
   and binding.dependency_hash = head.dependency_hash
  join content_factory.research_stage_artifacts artifact
    on artifact.organization_id = head.organization_id
   and artifact.run_id = head.run_id
   and artifact.stage = head.stage
   and artifact.id = head.artifact_id
   and artifact.input_dependency_hash = binding.dependency_hash
  where head.organization_id = organization_id_value
    and head.run_id = draft_row.run_id
    and head.branch_id = branch_id_value
    and head.current_draft_id = draft_id_value
    and head.state = 'current';
  if exact_count <> 7 then
    raise exception using
      errcode = '55000', message = 'research_stage_snapshot_mismatch';
  end if;
  if exists (
    select 1
    from content_factory.research_stage_recompute_requests request
    where request.organization_id = organization_id_value
      and request.run_id = draft_row.run_id
      and request.branch_id = branch_id_value
      and request.status in ('queued', 'processing')
  ) then
    raise exception using
      errcode = '55000', message = 'research_stage_recompute_pending';
  end if;
end;
$$;

create or replace function
  content_factory_private.guard_research_stage_control_approval()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.status = 'draft' and new.status = 'approved' then
    perform content_factory_private.assert_research_stage_draft_ready(
      new.organization_id, new.id
    );
  end if;
  return new;
end;
$$;

drop trigger if exists guard_research_stage_control_approval
  on content_factory.creative_brief_drafts;
create trigger guard_research_stage_control_approval
before update of status on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.guard_research_stage_control_approval();

alter function public.creator_approve_creative_brief(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_approve_creative_brief(jsonb)
  rename to creator_approve_creative_brief_pre_stage_control_v2;
revoke all on function
  content_factory_private.creator_approve_creative_brief_pre_stage_control_v2(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_approve_creative_brief(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  draft_id_value uuid;
  draft_status_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.resolve_organization(
    p_payload
  );
  perform content_factory_private.membership_role(
    organization_id_value, true, array['owner', 'admin', 'producer']
  );
  draft_id_value := content_factory_private.require_uuid(p_payload, 'draft_id');
  select draft.status into draft_status_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.id = draft_id_value;
  if draft_status_value = 'draft' then
    perform content_factory_private.assert_research_stage_draft_ready(
      organization_id_value, draft_id_value
    );
  end if;
  return content_factory_private
    .creator_approve_creative_brief_pre_stage_control_v2(p_payload);
end;
$$;


create or replace function public.creator_control_research_stage(
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
  user_id uuid;
  actor_role text;
  organization_id_value uuid;
  run_id_value uuid;
  branch_id_value uuid;
  stage_value text;
  action_value text;
  expected_head_event_id_value uuid;
  expected_artifact_id_value uuid;
  expected_content_hash_value text;
  expected_branch_revision_hash_value text;
  current_branch_revision_hash_value text;
  target_artifact_id_value uuid;
  new_branch_key_value text;
  reason_value text;
  user_input_value text;
  idempotency_key_value text;
  request_payload jsonb;
  request_hash_value text;
  replay jsonb;
  command_id_value uuid := extensions.gen_random_uuid();
  branch_row record;
  head_row record;
  artifact_row record;
  target_artifact_row record;
  downstream_head record;
  source_head record;
  correction_source_id_value uuid;
  replacement_value jsonb;
  dependencies_value jsonb;
  dependency_hash_value text;
  content_hash_value text;
  artifact_id_value uuid;
  artifact_version_value integer;
  draft_id_value uuid;
  event_id_value uuid;
  state_value text;
  stale_due_value jsonb;
  new_branch_id_value uuid;
  recompute_request_id_value uuid;
  child_run_id_value uuid;
  child_result_value jsonb;
  root_run_input_value jsonb;
  child_objective_value text;
  input_snapshot_value jsonb;
  input_snapshot_hash_value text;
  active_request_row record;
  cancelled_request_id_value uuid;
  cancelled_child_run_id_value uuid;
  cancellation_reason_value text;
  cancellation_event_action_value text;
  cancellation_error_code_value text;
  cancellation_guidance_value text;
  independent_event_exists_value boolean := false;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 786432
     or p_payload - array[
       'organization_id', 'run_id', 'branch_id', 'stage', 'action',
       'expected_head_event_id', 'expected_artifact_id',
       'expected_content_hash', 'expected_branch_revision_hash',
       'replacement', 'target_artifact_id',
       'new_branch_key', 'paid_analysis_ack', 'confirmation',
       'user_input', 'reason', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_stage_control_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  actor_role := content_factory_private.membership_role(
    organization_id_value, true, array['owner', 'admin', 'producer']
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  branch_id_value := content_factory_private.require_uuid(
    p_payload, 'branch_id'
  );
  expected_head_event_id_value := content_factory_private.require_uuid(
    p_payload, 'expected_head_event_id'
  );
  expected_artifact_id_value := content_factory_private.require_uuid(
    p_payload, 'expected_artifact_id'
  );
  stage_value := lower(content_factory_private.require_text(
    p_payload, 'stage', 5, 20
  ));
  action_value := lower(content_factory_private.require_text(
    p_payload, 'action', 4, 12
  ));
  expected_content_hash_value := lower(
    content_factory_private.require_text(
      p_payload, 'expected_content_hash', 64, 64
    )
  );
  expected_branch_revision_hash_value := lower(
    content_factory_private.require_text(
      p_payload, 'expected_branch_revision_hash', 64, 64
    )
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  user_input_value := btrim(coalesce(p_payload ->> 'user_input', ''));
  if stage_value not in (
       'sources', 'category', 'competitors', 'trends',
       'guidance', 'brief', 'scenarios'
     )
     or action_value not in (
       'patch', 'reject', 'revert', 'fork', 'recompute', 'cancel'
     )
     or expected_content_hash_value !~ '^[0-9a-f]{64}$'
     or expected_branch_revision_hash_value !~ '^[0-9a-f]{64}$'
     or jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_stage_control_invalid';
  end if;

  if action_value = 'patch' then
    replacement_value := p_payload -> 'replacement';
    if jsonb_typeof(replacement_value) <> 'object'
       or length(replacement_value::text) > 524288
       or length(user_input_value) not between 3 and 4000
       or p_payload ? 'target_artifact_id'
       or p_payload ? 'new_branch_key'
       or p_payload ? 'paid_analysis_ack' then
      raise exception using
        errcode = '22023', message = 'research_stage_patch_invalid';
    end if;
  elsif action_value = 'reject' then
    if p_payload ? 'replacement' or p_payload ? 'target_artifact_id'
       or p_payload ? 'new_branch_key' or p_payload ? 'paid_analysis_ack'
       or p_payload ? 'user_input' then
      raise exception using
        errcode = '22023', message = 'research_stage_reject_invalid';
    end if;
  elsif action_value = 'revert' then
    target_artifact_id_value := content_factory_private.require_uuid(
      p_payload, 'target_artifact_id'
    );
    if p_payload ? 'replacement' or p_payload ? 'new_branch_key'
       or p_payload ? 'paid_analysis_ack' or p_payload ? 'user_input' then
      raise exception using
        errcode = '22023', message = 'research_stage_revert_invalid';
    end if;
  elsif action_value = 'fork' then
    new_branch_key_value := lower(content_factory_private.require_text(
      p_payload, 'new_branch_key', 3, 64
    ));
    if new_branch_key_value = 'main'
       or new_branch_key_value !~ '^[a-z0-9][a-z0-9_-]{0,63}$'
       or p_payload ? 'replacement' or p_payload ? 'target_artifact_id'
       or p_payload ? 'paid_analysis_ack' or p_payload ? 'user_input' then
      raise exception using
        errcode = '22023', message = 'research_stage_fork_invalid';
    end if;
  elsif action_value = 'recompute' then
    if stage_value = 'sources'
       or jsonb_typeof(p_payload -> 'paid_analysis_ack') <> 'boolean'
       or p_payload -> 'paid_analysis_ack' is distinct from 'true'::jsonb
       or length(user_input_value) not between 3 and 4000
       or p_payload ? 'replacement' or p_payload ? 'target_artifact_id'
       or p_payload ? 'new_branch_key' then
      raise exception using
        errcode = '22023', message = 'research_stage_recompute_invalid';
    end if;
  else
    if p_payload ? 'replacement' or p_payload ? 'target_artifact_id'
       or p_payload ? 'new_branch_key' or p_payload ? 'paid_analysis_ack'
       or p_payload ? 'user_input' then
      raise exception using
        errcode = '22023', message = 'research_stage_cancel_invalid';
    end if;
  end if;

  request_payload := p_payload - 'idempotency_key';
  request_hash_value := content_factory_private.json_hash(request_payload);
  replay := content_factory_private.begin_command(
    organization_id_value, 'creator_control_research_stage',
    idempotency_key_value, request_payload
  );
  if replay is not null then
    return replay;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-stage-control:' || run_id_value::text)
  );
  -- Serialize stage commands with the existing manual-draft/approval path.
  -- Without the shared brief lock, two valid commands can both derive a new
  -- version from the same head and race after their optimistic check.
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('brief:' || run_id_value::text)
  );
  select branch.* into branch_row
  from content_factory.research_stage_branches branch
  where branch.organization_id = organization_id_value
    and branch.run_id = run_id_value
    and branch.id = branch_id_value
  for share;
  if branch_row.id is null then
    raise exception using
      errcode = '42501', message = 'research_stage_branch_not_found';
  end if;
  if (
    select count(*)
    from content_factory.research_stage_heads head
    where head.organization_id = organization_id_value
      and head.run_id = run_id_value
      and head.branch_id = branch_id_value
  ) <> 7 then
    raise exception using
      errcode = '55000', message = 'research_stage_head_set_incomplete';
  end if;
  current_branch_revision_hash_value :=
    content_factory_private.research_stage_branch_revision_hash(
      organization_id_value, run_id_value, branch_id_value
    );
  if current_branch_revision_hash_value
       <> expected_branch_revision_hash_value then
    raise exception using
      errcode = '55000', message = 'research_stage_branch_revision_stale';
  end if;
  if action_value = 'recompute' and branch_row.branch_key <> 'main' then
    raise exception using
      errcode = '55000',
      message = 'research_stage_recompute_main_branch_required';
  end if;
  if branch_row.branch_key <> 'main' then
    raise exception using
      errcode = '55000',
      message = 'research_stage_comparison_branch_read_only';
  end if;
  select head.* into head_row
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
    and head.stage = stage_value
  for update;
  if head_row.head_event_id is null then
    raise exception using
      errcode = '55000', message = 'research_stage_head_missing';
  end if;
  select artifact.* into artifact_row
  from content_factory.research_stage_artifacts artifact
  where artifact.organization_id = organization_id_value
    and artifact.run_id = run_id_value
    and artifact.stage = stage_value
    and artifact.id = head_row.artifact_id;
  if head_row.head_event_id <> expected_head_event_id_value
     or head_row.artifact_id <> expected_artifact_id_value
     or artifact_row.content_hash <> expected_content_hash_value then
    raise exception using
      errcode = '55000', message = 'research_stage_head_stale';
  end if;
  if action_value not in ('fork', 'cancel')
     and branch_row.branch_key = 'main'
     and exists (
       select 1
       from content_factory.creative_brief_drafts draft
       where draft.organization_id = organization_id_value
         and draft.run_id = run_id_value
         and draft.status = 'approved'
     ) then
    raise exception using
      errcode = '55000', message = 'research_stage_run_locked';
  end if;

  select request.* into active_request_row
  from content_factory.research_stage_recompute_requests request
  where request.organization_id = organization_id_value
    and request.run_id = run_id_value
    and request.branch_id = branch_id_value
    and request.status in ('queued', 'processing')
  order by request.created_at desc, request.id desc
  limit 1
  for update;
  if action_value = 'cancel' then
    if active_request_row.id is null
       or active_request_row.stage <> stage_value then
      raise exception using
        errcode = '55000', message = 'research_stage_recompute_not_active';
    end if;
    select exists (
      select 1
      from content_factory.research_stage_head_events event
      where event.organization_id = organization_id_value
        and event.run_id = run_id_value
        and event.branch_id = branch_id_value
        and event.created_at >= active_request_row.created_at
        and event.request_hash <> active_request_row.request_hash
    ) into independent_event_exists_value;
    if active_request_row.status = 'processing'
       and active_request_row.lease_expires_at > clock_timestamp()
       and not independent_event_exists_value then
      raise exception using
        errcode = '55000',
        message = 'research_stage_recompute_lease_active';
    end if;
  elsif active_request_row.id is not null then
    raise exception using
      errcode = '55000', message = 'research_stage_recompute_active';
  end if;

  if action_value = 'patch' then
    correction_source_id_value :=
      content_factory_private.create_research_stage_user_input(
        organization_id_value, run_id_value, branch_id_value,
        stage_value, user_input_value, user_id
      );
    if branch_row.branch_key = 'main' then
      draft_id_value :=
        content_factory_private.materialize_research_stage_main_draft(
          organization_id_value, run_id_value, branch_id_value,
          stage_value, replacement_value, user_id, 'human',
          command_id_value, 'patch', reason_value, request_hash_value,
          correction_source_id_value
        );
    else
      dependencies_value :=
        content_factory_private.research_stage_branch_dependencies(
          organization_id_value, run_id_value, branch_id_value,
          stage_value, replacement_value
        );
      dependency_hash_value := content_factory_private.json_hash(
        jsonb_build_object(
          'evidence', dependencies_value -> 'evidence',
          'upstream_artifacts', dependencies_value -> 'upstream_artifacts'
        )
      );
      content_hash_value := content_factory_private.json_hash(replacement_value);
      select artifact.id into artifact_id_value
      from content_factory.research_stage_artifacts artifact
      where artifact.organization_id = organization_id_value
        and artifact.run_id = run_id_value
        and artifact.stage = stage_value
        and artifact.content_hash = content_hash_value
        and artifact.input_dependency_hash = dependency_hash_value;
      if artifact_id_value is null then
        select coalesce(max(artifact.version), 0) + 1
          into artifact_version_value
        from content_factory.research_stage_artifacts artifact
        where artifact.organization_id = organization_id_value
          and artifact.run_id = run_id_value
          and artifact.stage = stage_value;
        insert into content_factory.research_stage_artifacts (
          organization_id, run_id, stage, version, parent_artifact_id,
          payload, content_hash, input_dependencies, input_dependency_hash,
          actor_id, origin, created_at
        ) values (
          organization_id_value, run_id_value, stage_value,
          artifact_version_value, head_row.artifact_id, replacement_value,
          content_hash_value, dependencies_value, dependency_hash_value,
          user_id, 'human', clock_timestamp()
        ) on conflict (
          organization_id, run_id, stage, content_hash,
          input_dependency_hash
        ) do nothing returning id into artifact_id_value;
        if artifact_id_value is null then
          select artifact.id into artifact_id_value
          from content_factory.research_stage_artifacts artifact
          where artifact.organization_id = organization_id_value
            and artifact.run_id = run_id_value
            and artifact.stage = stage_value
            and artifact.content_hash = content_hash_value
            and artifact.input_dependency_hash = dependency_hash_value;
        end if;
      end if;
      select case when count(*) = 0 then 'current' else 'stale_dependency' end,
        coalesce(jsonb_agg(head.artifact_id
          order by content_factory_private.research_stage_rank(head.stage)),
          '[]'::jsonb)
        into state_value, stale_due_value
      from content_factory.research_stage_heads head
      where head.organization_id = organization_id_value
        and head.run_id = run_id_value
        and head.branch_id = branch_id_value
        and content_factory_private.research_stage_rank(head.stage)
          < content_factory_private.research_stage_rank(stage_value)
        and head.state <> 'current';
      event_id_value := content_factory_private.write_research_stage_head_event(
        organization_id_value, run_id_value, branch_id_value,
        command_id_value, stage_value, 'patch', state_value,
        artifact_id_value, dependency_hash_value, stale_due_value,
        head_row.current_draft_id, correction_source_id_value,
        reason_value, user_id, 'human', request_hash_value
      );
      for downstream_head in
        select head.*
        from content_factory.research_stage_heads head
        where head.organization_id = organization_id_value
          and head.run_id = run_id_value
          and head.branch_id = branch_id_value
          and content_factory_private.research_stage_rank(head.stage)
            > content_factory_private.research_stage_rank(stage_value)
        order by content_factory_private.research_stage_rank(head.stage)
      loop
        dependencies_value :=
          content_factory_private.research_stage_current_dependency_state(
            organization_id_value, run_id_value, branch_id_value,
            downstream_head.stage
          );
        state_value := dependencies_value ->> 'state';
        stale_due_value :=
          dependencies_value -> 'stale_due_to_artifact_ids';
        perform content_factory_private.write_research_stage_head_event(
          organization_id_value, run_id_value, branch_id_value,
          command_id_value, downstream_head.stage, 'dependency_refresh',
          state_value, downstream_head.artifact_id,
          downstream_head.dependency_hash, stale_due_value,
          downstream_head.current_draft_id, correction_source_id_value,
          reason_value, user_id, 'system', request_hash_value
        );
      end loop;
    end if;

  elsif action_value = 'reject' then
    event_id_value := content_factory_private.write_research_stage_head_event(
      organization_id_value, run_id_value, branch_id_value,
      command_id_value, stage_value, 'reject', 'rejected',
      head_row.artifact_id, head_row.dependency_hash, '[]'::jsonb,
      head_row.current_draft_id, null, reason_value, user_id, 'human',
      request_hash_value
    );
    -- Keep migration 001's decision ledger useful when this head is backed by
    -- a materialized draft. Branch-only artifacts remain fully represented by
    -- the immutable head event even when no draft binding exists for them.
    insert into content_factory.research_stage_decisions (
      organization_id, run_id, draft_id, stage, artifact_id,
      decision, actor_id, origin, decision_hash, created_at
    )
    select binding.organization_id, binding.run_id, binding.draft_id,
      binding.stage, binding.artifact_id, 'rejected', user_id, 'human',
      content_factory_private.json_hash(jsonb_build_object(
        'organization_id', binding.organization_id,
        'run_id', binding.run_id,
        'draft_id', binding.draft_id,
        'stage', binding.stage,
        'artifact_id', binding.artifact_id,
        'decision', 'rejected',
        'actor_id', user_id,
        'origin', 'human'
      )), clock_timestamp()
    from content_factory.research_stage_draft_bindings binding
    where binding.organization_id = organization_id_value
      and binding.run_id = run_id_value
      and binding.draft_id = head_row.current_draft_id
      and binding.stage = stage_value
      and binding.artifact_id = head_row.artifact_id
    on conflict (organization_id, decision_hash) do nothing;
    for downstream_head in
      select head.*
      from content_factory.research_stage_heads head
      where head.organization_id = organization_id_value
        and head.run_id = run_id_value
        and head.branch_id = branch_id_value
        and content_factory_private.research_stage_rank(head.stage)
          > content_factory_private.research_stage_rank(stage_value)
      order by content_factory_private.research_stage_rank(head.stage)
    loop
      dependencies_value :=
        content_factory_private.research_stage_current_dependency_state(
          organization_id_value, run_id_value, branch_id_value,
          downstream_head.stage
        );
      state_value := dependencies_value ->> 'state';
      stale_due_value :=
        dependencies_value -> 'stale_due_to_artifact_ids';
      perform content_factory_private.write_research_stage_head_event(
        organization_id_value, run_id_value, branch_id_value,
        command_id_value, downstream_head.stage, 'dependency_refresh',
        state_value, downstream_head.artifact_id,
        downstream_head.dependency_hash, stale_due_value,
        downstream_head.current_draft_id, null, reason_value, user_id,
        'system', request_hash_value
      );
    end loop;

  elsif action_value = 'revert' then
    select artifact.* into target_artifact_row
    from content_factory.research_stage_artifacts artifact
    where artifact.organization_id = organization_id_value
      and artifact.run_id = run_id_value
      and artifact.stage = stage_value
      and artifact.id = target_artifact_id_value;
    if target_artifact_row.id is null
       or target_artifact_row.id = head_row.artifact_id then
      raise exception using
        errcode = '55000', message = 'research_stage_revert_target_invalid';
    end if;
    replacement_value :=
      content_factory_private.research_stage_effective_payload(
        stage_value, target_artifact_row.payload
      );
    if branch_row.branch_key = 'main' then
      draft_id_value :=
        content_factory_private.materialize_research_stage_main_draft(
          organization_id_value, run_id_value, branch_id_value,
          stage_value, replacement_value, user_id, 'human',
          command_id_value, 'revert', reason_value, request_hash_value, null
        );
      insert into content_factory.research_stage_decisions (
        organization_id, run_id, draft_id, stage, artifact_id,
        decision, actor_id, origin, decision_hash, created_at
      )
      select binding.organization_id, binding.run_id, binding.draft_id,
        binding.stage, binding.artifact_id, 'reverted', user_id, 'human',
        content_factory_private.json_hash(jsonb_build_object(
          'organization_id', binding.organization_id,
          'run_id', binding.run_id,
          'draft_id', binding.draft_id,
          'stage', binding.stage,
          'artifact_id', binding.artifact_id,
          'decision', 'reverted',
          'actor_id', user_id,
          'origin', 'human'
        )), clock_timestamp()
      from content_factory.research_stage_draft_bindings binding
      where binding.organization_id = organization_id_value
        and binding.run_id = run_id_value
        and binding.draft_id = draft_id_value
        and binding.stage = stage_value
      on conflict (organization_id, decision_hash) do nothing;
    else
      dependencies_value :=
        content_factory_private.research_stage_branch_dependencies(
          organization_id_value, run_id_value, branch_id_value,
          stage_value, replacement_value
        );
      dependency_hash_value := content_factory_private.json_hash(
        jsonb_build_object(
          'evidence', dependencies_value -> 'evidence',
          'upstream_artifacts', dependencies_value -> 'upstream_artifacts'
        )
      );
      select case when count(*) = 0
        and dependency_hash_value = target_artifact_row.input_dependency_hash
        then 'current' else 'stale_dependency' end,
        coalesce(jsonb_agg(head.artifact_id
          order by content_factory_private.research_stage_rank(head.stage)),
          '[]'::jsonb)
        into state_value, stale_due_value
      from content_factory.research_stage_heads head
      where head.organization_id = organization_id_value
        and head.run_id = run_id_value
        and head.branch_id = branch_id_value
        and content_factory_private.research_stage_rank(head.stage)
          < content_factory_private.research_stage_rank(stage_value)
        and (
          head.state <> 'current'
          or not exists (
            select 1
            from jsonb_array_elements(
              target_artifact_row.input_dependencies -> 'upstream_artifacts'
            ) expected(value)
            where expected.value ->> 'stage' = head.stage
              and expected.value ->> 'artifact_id' = head.artifact_id::text
          )
        );
      event_id_value := content_factory_private.write_research_stage_head_event(
        organization_id_value, run_id_value, branch_id_value,
        command_id_value, stage_value, 'revert', state_value,
        target_artifact_row.id, dependency_hash_value,
        stale_due_value, head_row.current_draft_id, null, reason_value,
        user_id, 'human', request_hash_value
      );
      for downstream_head in
        select head.*
        from content_factory.research_stage_heads head
        where head.organization_id = organization_id_value
          and head.run_id = run_id_value
          and head.branch_id = branch_id_value
          and content_factory_private.research_stage_rank(head.stage)
            > content_factory_private.research_stage_rank(stage_value)
        order by content_factory_private.research_stage_rank(head.stage)
      loop
        dependencies_value :=
          content_factory_private.research_stage_current_dependency_state(
            organization_id_value, run_id_value, branch_id_value,
            downstream_head.stage
          );
        state_value := dependencies_value ->> 'state';
        stale_due_value :=
          dependencies_value -> 'stale_due_to_artifact_ids';
        perform content_factory_private.write_research_stage_head_event(
          organization_id_value, run_id_value, branch_id_value,
          command_id_value, downstream_head.stage, 'dependency_refresh',
          state_value, downstream_head.artifact_id,
          downstream_head.dependency_hash, stale_due_value,
          downstream_head.current_draft_id, null, reason_value, user_id,
          'system', request_hash_value
        );
      end loop;
    end if;

  elsif action_value = 'fork' then
    if (
      select count(*)
      from content_factory.research_stage_branches existing_branch
      where existing_branch.organization_id = organization_id_value
        and existing_branch.run_id = run_id_value
    ) >= 50 then
      raise exception using
        errcode = '54000', message = 'research_stage_branch_limit_reached';
    end if;
    new_branch_id_value := extensions.gen_random_uuid();
    insert into content_factory.research_stage_branches (
      id, organization_id, run_id, branch_key, parent_branch_id,
      created_by, reason, branch_hash, created_at
    ) values (
      new_branch_id_value, organization_id_value, run_id_value,
      new_branch_key_value, branch_id_value, user_id, reason_value,
      content_factory_private.json_hash(jsonb_build_object(
        'branch_id', new_branch_id_value,
        'organization_id', organization_id_value,
        'run_id', run_id_value,
        'branch_key', new_branch_key_value,
        'parent_branch_id', branch_id_value,
        'created_by', user_id
      )), clock_timestamp()
    );
    for source_head in
      select head.*
      from content_factory.research_stage_heads head
      where head.organization_id = organization_id_value
        and head.run_id = run_id_value
        and head.branch_id = branch_id_value
      order by content_factory_private.research_stage_rank(head.stage)
    loop
      perform content_factory_private.write_research_stage_head_event(
        organization_id_value, run_id_value, new_branch_id_value,
        command_id_value, source_head.stage, 'fork', source_head.state,
        source_head.artifact_id, source_head.dependency_hash,
        source_head.stale_due_to_artifact_ids, source_head.current_draft_id,
        null, reason_value, user_id, 'human', request_hash_value
      );
    end loop;

  elsif action_value = 'cancel' then
    cancellation_event_action_value := case
      when independent_event_exists_value then 'recompute_superseded'
      else 'recompute_cancelled'
    end;
    cancellation_error_code_value := case
      when independent_event_exists_value
        then 'head_changed_during_recompute'
      else 'cancelled_by_user'
    end;
    cancellation_guidance_value := case
      when independent_event_exists_value
        then 'recompute_superseded'
      else 'recompute_cancelled'
    end;
    cancellation_reason_value := case
      when independent_event_exists_value
        then 'Saved stage recompute superseded by a later root branch command'
      when active_request_row.status = 'queued'
        then 'Saved stage recompute cancelled before provider claim'
      else 'Expired stage recompute lease cancelled without provider retry'
    end;
    update content_factory.product_research_runs run
    set status = 'cancelled',
        lease_expires_at = null,
        finished_at = clock_timestamp(),
        updated_at = clock_timestamp(),
        error_code = case when independent_event_exists_value
          then 'stage_recompute_superseded'
          else 'stage_recompute_cancelled' end,
        error_message = cancellation_reason_value
    where run.organization_id = organization_id_value
      and run.id = active_request_row.child_run_id
      and (
        run.status = 'queued'
        or (
          run.status = 'processing'
          and run.lease_expires_at <= clock_timestamp()
        )
      );
    perform set_config(
      'content_factory.research_stage_control_write', 'on', true
    );
    update content_factory.research_stage_recompute_requests request
    set status = 'superseded',
        error_code = cancellation_error_code_value,
        error_message = cancellation_reason_value,
        lease_expires_at = null,
        finished_at = clock_timestamp()
    where request.organization_id = organization_id_value
      and request.id = active_request_row.id
      and request.status in ('queued', 'processing');
    perform content_factory_private.refresh_research_stage_branch_states(
      organization_id_value, run_id_value, branch_id_value, stage_value,
      command_id_value, cancellation_event_action_value,
      cancellation_reason_value,
      user_id, active_request_row.correction_source_id,
      active_request_row.expected_head_event_id,
      request_hash_value
    );
    cancelled_request_id_value := active_request_row.id;
    cancelled_child_run_id_value := active_request_row.child_run_id;

  else
    correction_source_id_value :=
      content_factory_private.create_research_stage_user_input(
        organization_id_value, run_id_value, branch_id_value,
        stage_value, user_input_value, user_id
      );
    select jsonb_build_object(
      'schema_version', 'research-stage-recompute-input-v1',
      'organization_id', organization_id_value,
      'run_id', run_id_value,
      'branch_id', branch_id_value,
      'branch_revision_hash', current_branch_revision_hash_value,
      'requested_stage', stage_value,
      'requested_head_event_id', head_row.head_event_id,
      'correction_source_id', correction_source_id_value,
      'heads', coalesce(jsonb_agg(jsonb_build_object(
        'stage', current_head.stage,
        'head_event_id', current_head.head_event_id,
        'state', current_head.state,
        'artifact_id', current_head.artifact_id,
        'content_hash', current_artifact.content_hash,
        'dependency_hash', current_head.dependency_hash,
        'payload', current_artifact.payload
      ) order by content_factory_private.research_stage_rank(
        current_head.stage
      )), '[]'::jsonb)
    ) into input_snapshot_value
    from content_factory.research_stage_heads current_head
    join content_factory.research_stage_artifacts current_artifact
      on current_artifact.organization_id = current_head.organization_id
     and current_artifact.run_id = current_head.run_id
     and current_artifact.stage = current_head.stage
     and current_artifact.id = current_head.artifact_id
    where current_head.organization_id = organization_id_value
      and current_head.run_id = run_id_value
      and current_head.branch_id = branch_id_value;
    if jsonb_array_length(input_snapshot_value -> 'heads') <> 7
       or octet_length(input_snapshot_value::text) > 76800 then
      raise exception using
        errcode = '55000', message = 'research_stage_recompute_snapshot_invalid';
    end if;
    input_snapshot_hash_value :=
      content_factory_private.json_hash(input_snapshot_value);
    recompute_request_id_value := extensions.gen_random_uuid();
    select run.input into root_run_input_value
    from content_factory.product_research_runs run
    where run.organization_id = organization_id_value
      and run.id = run_id_value;
    child_objective_value := left(
      btrim(coalesce(root_run_input_value ->> 'objective', ''))
      || E'\n\nControlled stage recompute. Requested stage: '
      || stage_value
      || E'. Apply the separately authenticated stage-control envelope.',
      2000
    );
    child_result_value := public.creator_start_product_research(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'idempotency_key',
          'stage-recompute-child:' || left(request_hash_value, 64),
        'product_id', (
          select run.product_id
          from content_factory.product_research_runs run
          where run.organization_id = organization_id_value
            and run.id = run_id_value
        ),
        'objective', child_objective_value,
        'marketplace_url', root_run_input_value -> 'marketplace_url',
        'source_media_ids', root_run_input_value -> 'source_media_ids',
        'platforms', root_run_input_value -> 'platforms',
        'paid_analysis_ack', true
      )
    );
    begin
      child_run_id_value := (child_result_value #>> '{run,id}')::uuid;
    exception when invalid_text_representation then
      child_run_id_value := null;
    end;
    if child_run_id_value is null or child_run_id_value = run_id_value then
      raise exception using
        errcode = '55000',
        message = 'research_stage_recompute_child_run_invalid';
    end if;
    perform set_config(
      'content_factory.research_stage_control_write', 'on', true
    );
    insert into content_factory.research_stage_recompute_requests (
      id, organization_id, run_id, branch_id, child_run_id, stage,
      expected_head_event_id, expected_artifact_id,
      expected_content_hash, expected_branch_revision_hash,
      status, paid_analysis_ack,
      provider_key, adapter_version, max_provider_attempts,
      provider_attempt_count, input_snapshot, input_snapshot_hash,
      correction_source_id, requested_by, idempotency_key,
      request_hash, created_at
    ) values (
      recompute_request_id_value, organization_id_value, run_id_value,
      branch_id_value, child_run_id_value, stage_value,
      head_row.head_event_id,
      head_row.artifact_id, artifact_row.content_hash,
      current_branch_revision_hash_value, 'queued', true,
      'openai_web_search', 'research-stage-recompute-v1', 1, 0,
      input_snapshot_value, input_snapshot_hash_value,
      correction_source_id_value, user_id,
      'stage-recompute:' || left(request_hash_value, 64),
      request_hash_value, clock_timestamp()
    );
    event_id_value := content_factory_private.write_research_stage_head_event(
      organization_id_value, run_id_value, branch_id_value,
      command_id_value, stage_value, 'recompute_queued',
      'recompute_queued', head_row.artifact_id, head_row.dependency_hash,
      head_row.stale_due_to_artifact_ids, head_row.current_draft_id,
      correction_source_id_value, reason_value, user_id, 'human',
      request_hash_value
    );
    for downstream_head in
      select head.*
      from content_factory.research_stage_heads head
      where head.organization_id = organization_id_value
        and head.run_id = run_id_value
        and head.branch_id = branch_id_value
        and content_factory_private.research_stage_rank(head.stage)
          > content_factory_private.research_stage_rank(stage_value)
      order by content_factory_private.research_stage_rank(head.stage)
    loop
      dependencies_value :=
        content_factory_private.research_stage_current_dependency_state(
          organization_id_value, run_id_value, branch_id_value,
          downstream_head.stage
        );
      state_value := dependencies_value ->> 'state';
      stale_due_value :=
        dependencies_value -> 'stale_due_to_artifact_ids';
      perform content_factory_private.write_research_stage_head_event(
        organization_id_value, run_id_value, branch_id_value,
        command_id_value, downstream_head.stage, 'dependency_refresh',
        state_value, downstream_head.artifact_id,
        downstream_head.dependency_hash, stale_due_value,
        downstream_head.current_draft_id, correction_source_id_value,
        reason_value, user_id, 'system', request_hash_value
      );
    end loop;
  end if;

  select head.* into head_row
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = coalesce(new_branch_id_value, branch_id_value)
    and head.stage = stage_value;
  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-stage-control-v2',
    'action', action_value,
    'run_id', run_id_value,
    'branch_id', coalesce(new_branch_id_value, branch_id_value),
    'branch_key', coalesce(new_branch_key_value, branch_row.branch_key),
    'branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        organization_id_value, run_id_value,
        coalesce(new_branch_id_value, branch_id_value)
      ),
    'draft_id', draft_id_value,
    'head', jsonb_build_object(
      'stage', stage_value,
      'head_event_id', head_row.head_event_id,
      'artifact_id', head_row.artifact_id,
      'state', head_row.state,
      'dependency_hash', head_row.dependency_hash,
      'stale_due_to_artifact_ids', head_row.stale_due_to_artifact_ids
    ),
    'recompute_request', case
      when cancelled_request_id_value is not null then jsonb_build_object(
        'request_id', cancelled_request_id_value,
        'child_run_id', cancelled_child_run_id_value,
        'status', 'superseded',
        'error_code', cancellation_error_code_value,
        'automatic_provider_action', false
      )
      when recompute_request_id_value is null then null
      else jsonb_build_object(
        'request_id', recompute_request_id_value,
        'child_run_id', child_run_id_value,
        'status', 'queued',
        'paid_analysis_ack', true,
        'provider_key', 'openai_web_search',
        'adapter_version', 'research-stage-recompute-v1',
        'max_provider_attempts', 1,
        'automatic_provider_action', false,
        'invoke', jsonb_build_object(
          'action', 'analyze',
          'research_id', child_run_id_value
        )
      ) end,
    'guidance', jsonb_build_object(
      'status', case
        when cancelled_request_id_value is not null
          then cancellation_guidance_value
        when recompute_request_id_value is not null then 'recompute_prepared'
        when head_row.state = 'current' then 'stage_updated'
        else head_row.state
      end,
      'server_refresh_required', true,
      'automatic_provider_action', false,
      'automatic_spend', false,
      'automatic_generation', false,
      'automatic_publication', false
    )
  );
  return content_factory_private.finish_command(
    organization_id_value, user_id, 'creator_control_research_stage',
    idempotency_key_value, request_payload, result_value
  );
end;
$$;


create or replace function
  content_factory_private.research_stage_branch_dependencies(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid,
    stage_value text,
    payload_value jsonb
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  sources_payload jsonb;
  source_ids_value jsonb;
  stage_source_refs text[];
  evidence_value jsonb;
  upstream_value jsonb;
  evidence_count integer;
begin
  if stage_value not in (
       'sources', 'category', 'competitors', 'trends',
       'guidance', 'brief', 'scenarios'
     ) then
    raise exception using
      errcode = '22023', message = 'research_stage_control_stage_invalid';
  end if;
  if stage_value = 'sources' then
    sources_payload := content_factory_private.research_stage_effective_payload(
      'sources', payload_value
    );
  else
    select content_factory_private.research_stage_effective_payload(
      'sources', artifact.payload
    ) into sources_payload
    from content_factory.research_stage_heads head
    join content_factory.research_stage_artifacts artifact
      on artifact.organization_id = head.organization_id
     and artifact.run_id = head.run_id
     and artifact.stage = head.stage
     and artifact.id = head.artifact_id
    where head.organization_id = organization_id_value
      and head.run_id = run_id_value
      and head.branch_id = branch_id_value
      and head.stage = 'sources';
  end if;
  source_ids_value := content_factory_private.canonical_research_source_ids(
    sources_payload -> 'source_ids'
  );
  if source_ids_value is null
     or jsonb_array_length(source_ids_value) not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'research_stage_source_set_invalid';
  end if;
  stage_source_refs :=
    content_factory_private.research_stage_source_refs(payload_value);
  if stage_value = 'sources' or cardinality(stage_source_refs) = 0 then
    select count(*)::integer,
      coalesce(jsonb_agg(jsonb_build_object(
        'source_id', source.id,
        'content_hash', source.content_hash
      ) order by source.id), '[]'::jsonb)
      into evidence_count, evidence_value
    from content_factory.product_research_sources source
    where source.organization_id = organization_id_value
      and source.run_id = run_id_value
      and source.id in (
        select source_ref.value::uuid
        from jsonb_array_elements_text(source_ids_value) source_ref(value)
      );
    if evidence_count <> jsonb_array_length(source_ids_value) then
      raise exception using
        errcode = '42501', message = 'research_stage_evidence_mismatch';
    end if;
  else
    if exists (
      select 1
      from unnest(stage_source_refs) source_ref(value)
      where (
        select count(*)
        from content_factory.product_research_sources source
        where source.organization_id = organization_id_value
          and source.run_id = run_id_value
          and source.id in (
            select selected.value::uuid
            from jsonb_array_elements_text(source_ids_value) selected(value)
          )
          and (
            source.id::text = source_ref.value
            or source.metadata ->> 'model_source_id' = source_ref.value
          )
      ) <> 1
    ) then
      raise exception using
        errcode = '42501',
        message = 'research_stage_source_reference_mismatch';
    end if;
    select count(*)::integer,
      coalesce(jsonb_agg(jsonb_build_object(
        'source_id', source.id,
        'content_hash', source.content_hash
      ) order by source.id), '[]'::jsonb)
      into evidence_count, evidence_value
    from content_factory.product_research_sources source
    where source.organization_id = organization_id_value
      and source.run_id = run_id_value
      and source.id in (
        select selected.value::uuid
        from jsonb_array_elements_text(source_ids_value) selected(value)
      )
      and exists (
        select 1
        from unnest(stage_source_refs) source_ref(value)
        where source.id::text = source_ref.value
           or source.metadata ->> 'model_source_id' = source_ref.value
      );
    if evidence_count < 1 then
      raise exception using
        errcode = '42501', message = 'research_stage_evidence_mismatch';
    end if;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'stage', head.stage,
    'artifact_id', head.artifact_id,
    'content_hash', artifact.content_hash
  ) order by content_factory_private.research_stage_rank(head.stage)),
    '[]'::jsonb)
    into upstream_value
  from content_factory.research_stage_heads head
  join content_factory.research_stage_artifacts artifact
    on artifact.organization_id = head.organization_id
   and artifact.run_id = head.run_id
   and artifact.stage = head.stage
   and artifact.id = head.artifact_id
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
    and content_factory_private.research_stage_rank(head.stage)
      < content_factory_private.research_stage_rank(stage_value);
  return jsonb_build_object(
    'schema_version', 'research-stage-input-v2',
    'evidence', evidence_value,
    'upstream_artifacts', upstream_value
  );
end;
$$;

create or replace function
  content_factory_private.write_research_stage_head_event(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid,
    command_id_value uuid,
    stage_value text,
    action_value text,
    state_value text,
    artifact_id_value uuid,
    dependency_hash_value text,
    stale_due_value jsonb,
    draft_id_value uuid,
    correction_source_id_value uuid,
    reason_value text,
    actor_id_value uuid,
    origin_value text,
    request_hash_value text
  )
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  prior_event_id_value uuid;
  prior_artifact_id_value uuid;
  event_id_value uuid := extensions.gen_random_uuid();
  event_hash_value text;
begin
  if action_value not in (
       'baseline', 'patch', 'reject', 'revert', 'fork',
       'dependency_refresh', 'recompute_queued',
       'recompute_processing', 'recompute_completed',
       'recompute_propagated', 'recompute_failed',
       'recompute_superseded', 'recompute_cancelled'
     )
     or state_value not in (
       'current', 'stale_dependency', 'rejected',
       'recompute_queued', 'recompute_processing', 'recompute_failed'
     )
     or dependency_hash_value !~ '^[0-9a-f]{64}$'
     or jsonb_typeof(stale_due_value) <> 'array'
     or jsonb_array_length(stale_due_value) > 7
     or origin_value not in ('ai', 'human', 'system')
     or request_hash_value !~ '^[0-9a-f]{64}$'
     or length(btrim(reason_value)) not between 3 and 500 then
    raise exception using
      errcode = '22023', message = 'research_stage_head_event_invalid';
  end if;
  select head.head_event_id, head.artifact_id
    into prior_event_id_value, prior_artifact_id_value
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
    and head.stage = stage_value
  for update;
  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'event_id', event_id_value,
    'organization_id', organization_id_value,
    'run_id', run_id_value,
    'branch_id', branch_id_value,
    'command_id', command_id_value,
    'stage', stage_value,
    'action', action_value,
    'state', state_value,
    'artifact_id', artifact_id_value,
    'prior_event_id', prior_event_id_value,
    'dependency_hash', dependency_hash_value,
    'stale_due_to_artifact_ids', stale_due_value,
    'draft_id', draft_id_value,
    'correction_source_id', correction_source_id_value,
    'reason', reason_value,
    'actor_id', actor_id_value,
    'origin', origin_value,
    'request_hash', request_hash_value
  ));
  insert into content_factory.research_stage_head_events (
    id, organization_id, run_id, branch_id, command_id, stage,
    action, state, artifact_id, prior_event_id, prior_artifact_id,
    dependency_hash, stale_due_to_artifact_ids, draft_id,
    correction_source_id, reason, actor_id, origin, request_hash,
    event_hash, created_at
  ) values (
    event_id_value, organization_id_value, run_id_value, branch_id_value,
    command_id_value, stage_value, action_value, state_value,
    artifact_id_value, prior_event_id_value, prior_artifact_id_value,
    dependency_hash_value, stale_due_value, draft_id_value,
    correction_source_id_value, reason_value, actor_id_value, origin_value,
    request_hash_value, event_hash_value, clock_timestamp()
  );
  perform set_config(
    'content_factory.research_stage_control_write', 'on', true
  );
  insert into content_factory.research_stage_heads (
    organization_id, run_id, branch_id, stage, artifact_id,
    head_event_id, dependency_hash, state, stale_due_to_artifact_ids,
    current_draft_id, updated_by, updated_at
  ) values (
    organization_id_value, run_id_value, branch_id_value, stage_value,
    artifact_id_value, event_id_value, dependency_hash_value, state_value,
    stale_due_value, draft_id_value, actor_id_value, clock_timestamp()
  ) on conflict (organization_id, run_id, branch_id, stage) do update
  set artifact_id = excluded.artifact_id,
      head_event_id = excluded.head_event_id,
      dependency_hash = excluded.dependency_hash,
      state = excluded.state,
      stale_due_to_artifact_ids = excluded.stale_due_to_artifact_ids,
      current_draft_id = excluded.current_draft_id,
      updated_by = excluded.updated_by,
      updated_at = excluded.updated_at;
  return event_id_value;
end;
$$;


create table if not exists content_factory.research_stage_branches (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    branch_key text not null check (
      branch_key ~ '^[a-z0-9][a-z0-9_-]{0,63}$'
    ),
    parent_branch_id uuid,
    created_by uuid not null,
    reason text not null check (length(btrim(reason)) between 3 and 500),
    branch_hash text not null check (branch_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    constraint research_stage_branches_org_run_id_uq
      unique (organization_id, run_id, id),
    constraint research_stage_branches_org_run_key_uq
      unique (organization_id, run_id, branch_key),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, run_id, parent_branch_id)
      references content_factory.research_stage_branches(
        organization_id, run_id, id
      ),
    check (
      (branch_key = 'main' and parent_branch_id is null)
      or branch_key <> 'main'
    )
);

create table if not exists content_factory.research_stage_head_events (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    branch_id uuid not null,
    command_id uuid not null,
    stage text not null check (stage in (
      'sources', 'category', 'competitors', 'trends',
      'guidance', 'brief', 'scenarios'
    )),
    action text not null check (action in (
      'baseline', 'patch', 'reject', 'revert', 'fork',
      'dependency_refresh', 'recompute_queued',
      'recompute_processing', 'recompute_completed',
      'recompute_propagated', 'recompute_failed',
      'recompute_superseded', 'recompute_cancelled'
    )),
    state text not null check (state in (
      'current', 'stale_dependency', 'rejected',
      'recompute_queued', 'recompute_processing', 'recompute_failed'
    )),
    artifact_id uuid not null,
    prior_event_id uuid,
    prior_artifact_id uuid,
    dependency_hash text not null check (dependency_hash ~ '^[0-9a-f]{64}$'),
    stale_due_to_artifact_ids jsonb not null default '[]'::jsonb check (
      jsonb_typeof(stale_due_to_artifact_ids) = 'array'
      and jsonb_array_length(stale_due_to_artifact_ids) <= 7
    ),
    draft_id uuid,
    correction_source_id uuid,
    reason text not null check (length(btrim(reason)) between 3 and 500),
    actor_id uuid not null,
    origin text not null check (origin in ('ai', 'human', 'system')),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    constraint research_stage_head_events_org_id_uq
      unique (organization_id, id),
    constraint research_stage_head_events_scope_id_uq
      unique (organization_id, run_id, branch_id, stage, id),
    constraint research_stage_head_events_org_hash_uq
      unique (organization_id, event_hash),
    constraint research_stage_head_events_command_stage_uq
      unique (organization_id, run_id, branch_id, command_id, stage),
    foreign key (organization_id, run_id, branch_id)
      references content_factory.research_stage_branches(
        organization_id, run_id, id
      ),
    foreign key (organization_id, run_id, stage, artifact_id)
      references content_factory.research_stage_artifacts(
        organization_id, run_id, stage, id
      ),
    foreign key (organization_id, prior_event_id)
      references content_factory.research_stage_head_events(organization_id, id),
    foreign key (
      organization_id, run_id, branch_id, stage, prior_event_id
    ) references content_factory.research_stage_head_events(
      organization_id, run_id, branch_id, stage, id
    ),
    foreign key (organization_id, run_id, stage, prior_artifact_id)
      references content_factory.research_stage_artifacts(
        organization_id, run_id, stage, id
      ),
    foreign key (organization_id, run_id, draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    foreign key (organization_id, run_id, correction_source_id)
      references content_factory.product_research_sources(
        organization_id, run_id, id
      ),
    foreign key (organization_id, actor_id)
      references content_factory.memberships(organization_id, profile_id),
    check ((prior_event_id is null) = (prior_artifact_id is null))
);

create index if not exists research_stage_head_events_timeline_idx
  on content_factory.research_stage_head_events (
    organization_id, run_id, branch_id, created_at, id
  );
create index if not exists research_stage_head_events_stage_idx
  on content_factory.research_stage_head_events (
    organization_id, run_id, branch_id, stage, created_at desc, id desc
  );

create table if not exists content_factory.research_stage_heads (
    organization_id uuid not null,
    run_id uuid not null,
    branch_id uuid not null,
    stage text not null check (stage in (
      'sources', 'category', 'competitors', 'trends',
      'guidance', 'brief', 'scenarios'
    )),
    artifact_id uuid not null,
    head_event_id uuid not null,
    dependency_hash text not null check (dependency_hash ~ '^[0-9a-f]{64}$'),
    state text not null check (state in (
      'current', 'stale_dependency', 'rejected',
      'recompute_queued', 'recompute_processing', 'recompute_failed'
    )),
    stale_due_to_artifact_ids jsonb not null default '[]'::jsonb check (
      jsonb_typeof(stale_due_to_artifact_ids) = 'array'
      and jsonb_array_length(stale_due_to_artifact_ids) <= 7
    ),
    current_draft_id uuid,
    updated_by uuid not null,
    updated_at timestamptz not null default now(),
    primary key (organization_id, run_id, branch_id, stage),
    foreign key (organization_id, run_id, branch_id)
      references content_factory.research_stage_branches(
        organization_id, run_id, id
      ),
    foreign key (organization_id, run_id, stage, artifact_id)
      references content_factory.research_stage_artifacts(
        organization_id, run_id, stage, id
      ),
    foreign key (organization_id, head_event_id)
      references content_factory.research_stage_head_events(organization_id, id),
    foreign key (
      organization_id, run_id, branch_id, stage, head_event_id
    ) references content_factory.research_stage_head_events(
      organization_id, run_id, branch_id, stage, id
    ),
    foreign key (organization_id, run_id, current_draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    foreign key (organization_id, updated_by)
      references content_factory.memberships(organization_id, profile_id)
);

create table if not exists content_factory.research_stage_recompute_requests (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    branch_id uuid not null,
    child_run_id uuid not null,
    stage text not null check (stage in (
      'category', 'competitors', 'trends', 'guidance', 'brief', 'scenarios'
    )),
    expected_head_event_id uuid not null,
    expected_artifact_id uuid not null,
    expected_content_hash text not null
      check (expected_content_hash ~ '^[0-9a-f]{64}$'),
    expected_branch_revision_hash text not null
      check (expected_branch_revision_hash ~ '^[0-9a-f]{64}$'),
    status text not null default 'queued' check (status in (
      'queued', 'processing', 'completed', 'failed', 'superseded'
    )),
    paid_analysis_ack boolean not null check (paid_analysis_ack),
    provider_key text not null default 'openai_web_search'
      check (provider_key = 'openai_web_search'),
    adapter_version text not null default 'research-stage-recompute-v1'
      check (adapter_version = 'research-stage-recompute-v1'),
    max_provider_attempts integer not null default 1
      check (max_provider_attempts = 1),
    provider_attempt_count integer not null default 0
      check (provider_attempt_count between 0 and 1),
    input_snapshot jsonb not null check (
      jsonb_typeof(input_snapshot) = 'object'
      and input_snapshot ->> 'schema_version'
        = 'research-stage-recompute-input-v1'
      and input_snapshot - array[
        'schema_version', 'organization_id', 'run_id', 'branch_id',
        'branch_revision_hash',
        'requested_stage', 'requested_head_event_id',
        'correction_source_id', 'heads'
      ]::text[] = '{}'::jsonb
      and input_snapshot ?& array[
        'schema_version', 'organization_id', 'run_id', 'branch_id',
        'branch_revision_hash', 'requested_stage',
        'requested_head_event_id', 'correction_source_id', 'heads'
      ]::text[]
      and jsonb_typeof(input_snapshot -> 'heads') = 'array'
      and jsonb_array_length(input_snapshot -> 'heads') = 7
      and input_snapshot ->> 'organization_id' = organization_id::text
      and input_snapshot ->> 'run_id' = run_id::text
      and input_snapshot ->> 'branch_id' = branch_id::text
      and input_snapshot ->> 'branch_revision_hash'
        = expected_branch_revision_hash
      and input_snapshot ->> 'requested_stage' = stage
      and input_snapshot ->> 'requested_head_event_id'
        = expected_head_event_id::text
      and input_snapshot ->> 'correction_source_id'
        = correction_source_id::text
      and octet_length(input_snapshot::text) <= 76800
    ),
    input_snapshot_hash text not null
      check (input_snapshot_hash ~ '^[0-9a-f]{64}$'),
    correction_source_id uuid not null,
    requested_by uuid not null,
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    lease_expires_at timestamptz,
    completion_hash text check (
      completion_hash is null or completion_hash ~ '^[0-9a-f]{64}$'
    ),
    error_code text check (
      error_code is null or length(error_code) between 3 and 100
    ),
    error_message text check (
      error_message is null or length(error_message) between 3 and 2000
    ),
    created_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz,
    constraint research_stage_recompute_requests_org_id_uq
      unique (organization_id, id),
    constraint research_stage_recompute_requests_org_key_uq
      unique (organization_id, idempotency_key),
    constraint research_stage_recompute_requests_org_hash_uq
      unique (organization_id, request_hash),
    constraint research_stage_recompute_requests_org_child_uq
      unique (organization_id, child_run_id),
    foreign key (organization_id, run_id, branch_id)
      references content_factory.research_stage_branches(
        organization_id, run_id, id
      ),
    foreign key (organization_id, child_run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, expected_head_event_id)
      references content_factory.research_stage_head_events(organization_id, id),
    foreign key (
      organization_id, run_id, branch_id, stage, expected_head_event_id
    ) references content_factory.research_stage_head_events(
      organization_id, run_id, branch_id, stage, id
    ),
    foreign key (organization_id, run_id, stage, expected_artifact_id)
      references content_factory.research_stage_artifacts(
        organization_id, run_id, stage, id
      ),
    foreign key (organization_id, run_id, correction_source_id)
      references content_factory.product_research_sources(
        organization_id, run_id, id
      ),
    foreign key (organization_id, requested_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (status = 'queued' and started_at is null and finished_at is null
       and lease_expires_at is null and provider_attempt_count = 0)
      or (status = 'processing' and started_at is not null
       and finished_at is null and lease_expires_at is not null
       and provider_attempt_count = 1)
      or (status in ('completed', 'failed', 'superseded')
       and finished_at is not null and lease_expires_at is null)
    ),
    check (status <> 'completed' or (
      completion_hash is not null and error_code is null
    )),
    check (status not in ('failed', 'superseded') or error_code is not null)
);

create unique index if not exists research_stage_recompute_one_active_idx
  on content_factory.research_stage_recompute_requests (
    organization_id, run_id, branch_id
  ) where status in ('queued', 'processing');
create index if not exists research_stage_recompute_queue_idx
  on content_factory.research_stage_recompute_requests (
    status, created_at, id
  ) where status in ('queued', 'processing');

alter table content_factory.research_stage_branches enable row level security;
alter table content_factory.research_stage_head_events enable row level security;
alter table content_factory.research_stage_heads enable row level security;
alter table content_factory.research_stage_recompute_requests
  enable row level security;

revoke all on content_factory.research_stage_branches
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_stage_head_events
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_stage_heads
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_stage_recompute_requests
  from public, anon, authenticated, service_role;
grant all on content_factory.research_stage_branches to service_role;
grant all on content_factory.research_stage_head_events to service_role;
grant all on content_factory.research_stage_heads to service_role;
grant all on content_factory.research_stage_recompute_requests to service_role;

drop trigger if exists reject_research_stage_branch_mutation
  on content_factory.research_stage_branches;
create trigger reject_research_stage_branch_mutation
before update or delete on content_factory.research_stage_branches
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

drop trigger if exists reject_research_stage_head_event_mutation
  on content_factory.research_stage_head_events;
create trigger reject_research_stage_head_event_mutation
before update or delete on content_factory.research_stage_head_events
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

create or replace function
  content_factory_private.research_stage_branch_revision_hash(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid
  )
returns text
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  revision_hash_value text;
begin
  select content_factory_private.json_hash(jsonb_build_object(
      'schema_version', 'research-stage-branch-revision-v1',
      'heads', coalesce(jsonb_agg(jsonb_build_object(
        'stage', head.stage,
        'head_event_id', head.head_event_id,
        'artifact_id', head.artifact_id,
        'dependency_hash', head.dependency_hash,
        'state', head.state
      ) order by content_factory_private.research_stage_rank(head.stage)),
      '[]'::jsonb)
    ))
    into revision_hash_value
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value;
  return revision_hash_value;
end;
$$;

create or replace function
  content_factory_private.research_stage_current_dependency_state(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid,
    stage_value text
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  target_head content_factory.research_stage_heads%rowtype;
  target_artifact content_factory.research_stage_artifacts%rowtype;
  stale_due_value jsonb;
  state_value text;
begin
  select head.* into target_head
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
    and head.stage = stage_value;
  if target_head.head_event_id is null then
    raise exception using
      errcode = '55000', message = 'research_stage_head_missing';
  end if;
  select artifact.* into target_artifact
  from content_factory.research_stage_artifacts artifact
  where artifact.organization_id = organization_id_value
    and artifact.run_id = run_id_value
    and artifact.stage = stage_value
    and artifact.id = target_head.artifact_id;
  if target_artifact.id is null then
    raise exception using
      errcode = '55000', message = 'research_stage_artifact_missing';
  end if;
  select coalesce(jsonb_agg(upstream.artifact_id
    order by content_factory_private.research_stage_rank(upstream.stage)),
    '[]'::jsonb)
    into stale_due_value
  from content_factory.research_stage_heads upstream
  where upstream.organization_id = organization_id_value
    and upstream.run_id = run_id_value
    and upstream.branch_id = branch_id_value
    and content_factory_private.research_stage_rank(upstream.stage)
      < content_factory_private.research_stage_rank(stage_value)
    and (
      upstream.state <> 'current'
      or not exists (
        select 1
        from jsonb_array_elements(
          target_artifact.input_dependencies -> 'upstream_artifacts'
        ) expected(value)
        where expected.value ->> 'stage' = upstream.stage
          and expected.value ->> 'artifact_id' = upstream.artifact_id::text
      )
    );
  state_value := case
    when target_head.dependency_hash = target_artifact.input_dependency_hash
     and jsonb_array_length(stale_due_value) = 0
      then 'current'
    else 'stale_dependency'
  end;
  return jsonb_build_object(
    'state', state_value,
    'stale_due_to_artifact_ids', stale_due_value
  );
end;
$$;

create or replace function
  content_factory_private.refresh_research_stage_branch_states(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid,
    stage_value text,
    command_id_value uuid,
    target_action_value text,
    reason_value text,
    actor_id_value uuid,
    correction_source_id_value uuid,
    expected_head_event_id_value uuid,
    request_hash_value text
  )
returns void
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  head_row content_factory.research_stage_heads%rowtype;
  expected_event_row content_factory.research_stage_head_events%rowtype;
  dependency_state_value jsonb;
  next_state_value text;
  next_stale_due_value jsonb;
  next_artifact_id_value uuid;
  next_dependency_hash_value text;
  next_draft_id_value uuid;
begin
  if target_action_value not in (
       'recompute_superseded', 'recompute_cancelled'
     ) then
    raise exception using
      errcode = '22023', message = 'research_stage_refresh_action_invalid';
  end if;
  select event.* into expected_event_row
  from content_factory.research_stage_head_events event
  where event.organization_id = organization_id_value
    and event.run_id = run_id_value
    and event.branch_id = branch_id_value
    and event.stage = stage_value
    and event.id = expected_head_event_id_value;
  if expected_event_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'research_stage_refresh_expected_event_invalid';
  end if;
  for head_row in
    select head.*
    from content_factory.research_stage_heads head
    where head.organization_id = organization_id_value
      and head.run_id = run_id_value
      and head.branch_id = branch_id_value
      and content_factory_private.research_stage_rank(head.stage)
        >= content_factory_private.research_stage_rank(stage_value)
    order by content_factory_private.research_stage_rank(head.stage)
    for update
  loop
    if head_row.stage <> stage_value
       and head_row.state in ('rejected', 'recompute_failed') then
      continue;
    end if;
    if head_row.stage = stage_value
       and head_row.state not in (
         'recompute_queued', 'recompute_processing'
       ) then
      -- A later human action on the requested stage is authoritative. Record
      -- terminalization without erasing its explicit rejected/current state.
      next_state_value := head_row.state;
      next_stale_due_value := head_row.stale_due_to_artifact_ids;
      next_artifact_id_value := head_row.artifact_id;
      next_dependency_hash_value := head_row.dependency_hash;
      next_draft_id_value := head_row.current_draft_id;
    elsif head_row.stage = stage_value
          and target_action_value = 'recompute_cancelled' then
      -- Queue/processing markers are transient. Cancellation restores the
      -- exact semantic head that existed before prepare, including rejection
      -- or a prior failed recompute, instead of inferring only dependency
      -- freshness.
      next_state_value := expected_event_row.state;
      next_stale_due_value :=
        expected_event_row.stale_due_to_artifact_ids;
      next_artifact_id_value := expected_event_row.artifact_id;
      next_dependency_hash_value := expected_event_row.dependency_hash;
      next_draft_id_value := expected_event_row.draft_id;
    elsif head_row.stage = stage_value
          and target_action_value = 'recompute_superseded'
          and head_row.artifact_id = expected_event_row.artifact_id
          and expected_event_row.state in (
            'rejected', 'recompute_failed'
          ) then
      -- A downstream-only legacy save may move all heads to a newer draft
      -- while preserving this transient queue marker. Keep the newer draft
      -- binding, but never erase the rejection/failure that existed before
      -- prepare merely because the paid result was superseded.
      next_state_value := expected_event_row.state;
      next_stale_due_value :=
        expected_event_row.stale_due_to_artifact_ids;
      next_artifact_id_value := expected_event_row.artifact_id;
      next_dependency_hash_value := expected_event_row.dependency_hash;
      next_draft_id_value := head_row.current_draft_id;
    else
      -- Supersession keeps the current draft/artifact graph. This matters when
      -- a legacy human save changed a downstream stage while the requested
      -- head still carried a transient queue marker.
      dependency_state_value :=
        content_factory_private.research_stage_current_dependency_state(
          organization_id_value, run_id_value, branch_id_value, head_row.stage
        );
      next_state_value := dependency_state_value ->> 'state';
      next_stale_due_value :=
        dependency_state_value -> 'stale_due_to_artifact_ids';
      next_artifact_id_value := head_row.artifact_id;
      next_dependency_hash_value := head_row.dependency_hash;
      next_draft_id_value := head_row.current_draft_id;
    end if;
    if head_row.stage = stage_value
       or head_row.state <> next_state_value
       or head_row.stale_due_to_artifact_ids <> next_stale_due_value then
      perform content_factory_private.write_research_stage_head_event(
        organization_id_value, run_id_value, branch_id_value,
        command_id_value, head_row.stage,
        case when head_row.stage = stage_value
          then target_action_value else 'dependency_refresh' end,
        next_state_value, next_artifact_id_value,
        next_dependency_hash_value, next_stale_due_value,
        next_draft_id_value,
        correction_source_id_value, reason_value, actor_id_value,
        'system', request_hash_value
      );
    end if;
  end loop;
end;
$$;

create or replace function
  content_factory_private.guard_research_stage_control_state_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if current_setting(
       'content_factory.research_stage_control_write', true
     ) is distinct from 'on' then
    raise exception using
      errcode = '55000',
      message = tg_table_name || '_controlled_mutation_only';
  end if;
  return coalesce(new, old);
end;
$$;

drop trigger if exists guard_research_stage_head_mutation
  on content_factory.research_stage_heads;
create trigger guard_research_stage_head_mutation
before insert or update or delete on content_factory.research_stage_heads
for each row execute function
  content_factory_private.guard_research_stage_control_state_mutation();

drop trigger if exists guard_research_stage_recompute_mutation
  on content_factory.research_stage_recompute_requests;
create trigger guard_research_stage_recompute_mutation
before insert or update or delete
on content_factory.research_stage_recompute_requests
for each row execute function
  content_factory_private.guard_research_stage_control_state_mutation();

create or replace function content_factory_private.research_stage_effective_payload(
  stage_value text,
  payload_value jsonb
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select case
    when $1 in ('sources', 'category', 'competitors', 'trends', 'guidance')
     and jsonb_typeof($2) = 'object'
     and $2 ? 'base'
     and $2 - array[
       'base', 'human_correction', 'human_research_decision'
     ]::text[] = '{}'::jsonb
      then $2 -> 'base'
    else $2
  end
$$;

create or replace function
  content_factory_private.research_stage_stale_due_from_draft(
    organization_id_value uuid,
    run_id_value uuid,
    draft_id_value uuid,
    stage_value text,
    artifact_id_value uuid
  )
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with target as (
    select artifact.input_dependencies
    from content_factory.research_stage_artifacts artifact
    where artifact.organization_id = $1
      and artifact.run_id = $2
      and artifact.stage = $4
      and artifact.id = $5
  ), current_upstream as (
    select binding.stage, binding.artifact_id
    from content_factory.research_stage_draft_bindings binding
    where binding.organization_id = $1
      and binding.run_id = $2
      and binding.draft_id = $3
      and content_factory_private.research_stage_rank(binding.stage)
        < content_factory_private.research_stage_rank($4)
  )
  select coalesce(jsonb_agg(current_upstream.artifact_id
    order by content_factory_private.research_stage_rank(
      current_upstream.stage
    )), '[]'::jsonb)
  from current_upstream
  cross join target
  where not exists (
    select 1
    from jsonb_array_elements(
      target.input_dependencies -> 'upstream_artifacts'
    ) expected(value)
    where expected.value ->> 'stage' = current_upstream.stage
      and expected.value ->> 'artifact_id' = current_upstream.artifact_id::text
  )
$$;

create or replace function
  content_factory_private.sync_research_stage_main_heads(
    draft_row content_factory.creative_brief_drafts,
    command_id_value uuid,
    target_stage_value text,
    target_action_value text,
    actor_id_value uuid,
    origin_value text,
    reason_value text,
    request_hash_value text,
    correction_source_id_value uuid
  )
returns void
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  branch_row content_factory.research_stage_branches%rowtype;
  binding_row content_factory.research_stage_draft_bindings%rowtype;
  artifact_row content_factory.research_stage_artifacts%rowtype;
  prior_head content_factory.research_stage_heads%rowtype;
  event_id_value uuid;
  action_value text;
  state_value text;
  stale_due_value jsonb;
  noncurrent_upstream_value jsonb;
  event_hash_value text;
begin
  if target_stage_value is not null
     and target_stage_value not in (
       'sources', 'category', 'competitors', 'trends',
       'guidance', 'brief', 'scenarios'
     ) then
    raise exception using
      errcode = '22023', message = 'research_stage_control_stage_invalid';
  end if;
  if target_action_value not in (
       'baseline', 'patch', 'revert', 'recompute_completed'
     )
     or origin_value not in ('ai', 'human', 'system')
     or actor_id_value is null
     or request_hash_value !~ '^[0-9a-f]{64}$'
     or length(btrim(reason_value)) not between 3 and 500 then
    raise exception using
      errcode = '22023', message = 'research_stage_head_sync_invalid';
  end if;

  select branch.* into branch_row
  from content_factory.research_stage_branches branch
  where branch.organization_id = draft_row.organization_id
    and branch.run_id = draft_row.run_id
    and branch.branch_key = 'main'
  for share;
  if branch_row.id is null then
    return;
  end if;
  perform set_config(
    'content_factory.research_stage_control_write', 'on', true
  );
  for binding_row in
    select binding.*
    from content_factory.research_stage_draft_bindings binding
    where binding.organization_id = draft_row.organization_id
      and binding.run_id = draft_row.run_id
      and binding.draft_id = draft_row.id
    order by content_factory_private.research_stage_rank(binding.stage)
  loop
    select artifact.* into artifact_row
    from content_factory.research_stage_artifacts artifact
    where artifact.organization_id = binding_row.organization_id
      and artifact.run_id = binding_row.run_id
      and artifact.stage = binding_row.stage
      and artifact.id = binding_row.artifact_id;
    select head.* into prior_head
    from content_factory.research_stage_heads head
    where head.organization_id = binding_row.organization_id
      and head.run_id = binding_row.run_id
      and head.branch_id = branch_row.id
      and head.stage = binding_row.stage
    for update;

    state_value := case
      when binding_row.dependency_hash = artifact_row.input_dependency_hash
        then 'current'
      else 'stale_dependency'
    end;
    stale_due_value :=
      content_factory_private.research_stage_stale_due_from_draft(
        binding_row.organization_id, binding_row.run_id,
        binding_row.draft_id, binding_row.stage, binding_row.artifact_id
      );
    select coalesce(jsonb_agg(head.artifact_id
      order by content_factory_private.research_stage_rank(head.stage)),
      '[]'::jsonb)
      into noncurrent_upstream_value
    from content_factory.research_stage_heads head
    where head.organization_id = binding_row.organization_id
      and head.run_id = binding_row.run_id
      and head.branch_id = branch_row.id
      and content_factory_private.research_stage_rank(head.stage)
        < content_factory_private.research_stage_rank(binding_row.stage)
      and head.state <> 'current';
    if jsonb_array_length(noncurrent_upstream_value) > 0 then
      state_value := 'stale_dependency';
      select coalesce(jsonb_agg(distinct stale_id.value order by stale_id.value),
        '[]'::jsonb)
        into stale_due_value
      from jsonb_array_elements_text(
        stale_due_value || noncurrent_upstream_value
      ) stale_id(value);
    end if;

    if prior_head.head_event_id is not null
       and target_action_value <> 'recompute_completed'
       and prior_head.state in (
         'rejected', 'recompute_queued', 'recompute_processing',
         'recompute_failed'
       )
       and binding_row.stage is distinct from target_stage_value
       and prior_head.artifact_id = binding_row.artifact_id then
      state_value := prior_head.state;
      stale_due_value := prior_head.stale_due_to_artifact_ids;
    end if;

    action_value := case
      when prior_head.head_event_id is null then 'baseline'
      when binding_row.stage = target_stage_value then target_action_value
      when target_action_value = 'recompute_completed'
       and prior_head.artifact_id is distinct from binding_row.artifact_id
        then 'recompute_propagated'
      when prior_head.artifact_id is distinct from binding_row.artifact_id
        then 'patch'
      else 'dependency_refresh'
    end;
    event_id_value := extensions.gen_random_uuid();
    event_hash_value := content_factory_private.json_hash(jsonb_build_object(
      'event_id', event_id_value,
      'organization_id', binding_row.organization_id,
      'run_id', binding_row.run_id,
      'branch_id', branch_row.id,
      'command_id', command_id_value,
      'stage', binding_row.stage,
      'action', action_value,
      'state', state_value,
      'artifact_id', binding_row.artifact_id,
      'prior_event_id', prior_head.head_event_id,
      'dependency_hash', binding_row.dependency_hash,
      'stale_due_to_artifact_ids', stale_due_value,
      'draft_id', binding_row.draft_id,
      'correction_source_id', correction_source_id_value,
      'actor_id', actor_id_value,
      'origin', origin_value,
      'request_hash', request_hash_value
    ));
    insert into content_factory.research_stage_head_events (
      id, organization_id, run_id, branch_id, command_id, stage,
      action, state, artifact_id, prior_event_id, prior_artifact_id,
      dependency_hash, stale_due_to_artifact_ids, draft_id,
      correction_source_id, reason, actor_id, origin, request_hash,
      event_hash, created_at
    ) values (
      event_id_value, binding_row.organization_id, binding_row.run_id,
      branch_row.id, command_id_value, binding_row.stage, action_value,
      state_value, binding_row.artifact_id, prior_head.head_event_id,
      prior_head.artifact_id, binding_row.dependency_hash, stale_due_value,
      binding_row.draft_id, correction_source_id_value, reason_value,
      actor_id_value, origin_value, request_hash_value, event_hash_value,
      clock_timestamp()
    );
    insert into content_factory.research_stage_heads (
      organization_id, run_id, branch_id, stage, artifact_id,
      head_event_id, dependency_hash, state,
      stale_due_to_artifact_ids, current_draft_id, updated_by, updated_at
    ) values (
      binding_row.organization_id, binding_row.run_id, branch_row.id,
      binding_row.stage, binding_row.artifact_id, event_id_value,
      binding_row.dependency_hash, state_value, stale_due_value,
      binding_row.draft_id, actor_id_value, clock_timestamp()
    ) on conflict (organization_id, run_id, branch_id, stage) do update
    set artifact_id = excluded.artifact_id,
        head_event_id = excluded.head_event_id,
        dependency_hash = excluded.dependency_hash,
        state = excluded.state,
        stale_due_to_artifact_ids = excluded.stale_due_to_artifact_ids,
        current_draft_id = excluded.current_draft_id,
        updated_by = excluded.updated_by,
        updated_at = excluded.updated_at;
  end loop;
  if (
    select count(*)
    from content_factory.research_stage_heads head
    where head.organization_id = draft_row.organization_id
      and head.run_id = draft_row.run_id
      and head.branch_id = branch_row.id
  ) <> 7 then
    raise exception using
      errcode = '55000', message = 'research_stage_head_set_incomplete';
  end if;
end;
$$;

create or replace function
  content_factory_private.capture_research_stage_draft_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  command_id_value uuid;
  target_stage_value text := nullif(current_setting(
    'content_factory.research_stage_target', true
  ), '');
  target_action_value text := coalesce(nullif(current_setting(
    'content_factory.research_stage_action', true
  ), ''), 'patch');
  reason_value text := coalesce(nullif(current_setting(
    'content_factory.research_stage_reason', true
  ), ''), 'Draft stage synchronization');
  request_hash_value text := nullif(current_setting(
    'content_factory.research_stage_request_hash', true
  ), '');
  correction_source_id_value uuid;
begin
  perform content_factory_private.capture_research_stage_draft(new);
  begin
    command_id_value := nullif(current_setting(
      'content_factory.research_stage_command_id', true
    ), '')::uuid;
  exception when invalid_text_representation then
    command_id_value := null;
  end;
  command_id_value := coalesce(command_id_value, extensions.gen_random_uuid());
  if request_hash_value is null
     or request_hash_value !~ '^[0-9a-f]{64}$' then
    request_hash_value := content_factory_private.json_hash(
      jsonb_build_object('draft_id', new.id, 'content_hash', new.content_hash)
    );
  end if;
  begin
    correction_source_id_value := nullif(current_setting(
      'content_factory.research_stage_correction_source_id', true
    ), '')::uuid;
  exception when invalid_text_representation then
    correction_source_id_value := null;
  end;
  insert into content_factory.research_stage_branches (
    id, organization_id, run_id, branch_key, parent_branch_id,
    created_by, reason, branch_hash, created_at
  )
  select extensions.gen_random_uuid(), new.organization_id, new.run_id,
    'main', null, new.created_by, 'Initial main branch',
    content_factory_private.json_hash(jsonb_build_object(
      'organization_id', new.organization_id,
      'run_id', new.run_id,
      'branch_key', 'main',
      'created_by', new.created_by
    )), new.created_at
  where not exists (
    select 1
    from content_factory.research_stage_branches branch
    where branch.organization_id = new.organization_id
      and branch.run_id = new.run_id
      and branch.branch_key = 'main'
  )
  on conflict (organization_id, run_id, branch_key) do nothing;
  perform content_factory_private.sync_research_stage_main_heads(
    new, command_id_value, target_stage_value, target_action_value,
    new.created_by, new.origin, left(reason_value, 500), request_hash_value,
    correction_source_id_value
  );
  return new;
end;
$$;

drop trigger if exists capture_research_stage_draft
  on content_factory.creative_brief_drafts;
create trigger capture_research_stage_draft
after insert on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.capture_research_stage_draft_trigger();

insert into content_factory.research_stage_branches (
  id, organization_id, run_id, branch_key, parent_branch_id,
  created_by, reason, branch_hash, created_at
)
select extensions.gen_random_uuid(), draft.organization_id, draft.run_id,
  'main', null, draft.created_by, 'Initial main branch backfill',
  content_factory_private.json_hash(jsonb_build_object(
    'organization_id', draft.organization_id,
    'run_id', draft.run_id,
    'branch_key', 'main',
    'created_by', draft.created_by
  )), draft.created_at
from (
  select distinct on (candidate.organization_id, candidate.run_id)
    candidate.*
  from content_factory.creative_brief_drafts candidate
  where exists (
    select 1
    from content_factory.research_stage_draft_bindings binding
    where binding.organization_id = candidate.organization_id
      and binding.run_id = candidate.run_id
      and binding.draft_id = candidate.id
  )
  order by candidate.organization_id, candidate.run_id,
    candidate.version, candidate.id
) draft
on conflict (organization_id, run_id, branch_key) do nothing;

do $research_stage_main_head_backfill$
declare
  draft_row content_factory.creative_brief_drafts%rowtype;
begin
  for draft_row in
    select distinct on (candidate.organization_id, candidate.run_id)
      candidate.*
    from content_factory.creative_brief_drafts candidate
    join content_factory.research_stage_branches branch
      on branch.organization_id = candidate.organization_id
     and branch.run_id = candidate.run_id
     and branch.branch_key = 'main'
    where exists (
      select 1
      from content_factory.research_stage_draft_bindings binding
      where binding.organization_id = candidate.organization_id
        and binding.run_id = candidate.run_id
        and binding.draft_id = candidate.id
    )
    order by candidate.organization_id, candidate.run_id,
      candidate.version desc, candidate.id desc
  loop
    perform content_factory_private.sync_research_stage_main_heads(
      draft_row, extensions.gen_random_uuid(), null, 'baseline',
      draft_row.created_by, 'system', 'Initial main head backfill',
      content_factory_private.json_hash(jsonb_build_object(
        'kind', 'research-stage-main-head-backfill-v1',
        'organization_id', draft_row.organization_id,
        'run_id', draft_row.run_id,
        'draft_id', draft_row.id
      )), null
    );
  end loop;
end;
$research_stage_main_head_backfill$;

create or replace function
  content_factory_private.create_research_stage_user_input(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid,
    stage_value text,
    input_text_value text,
    actor_id_value uuid
  )
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  product_id_value uuid;
  source_id_value uuid;
  source_hash_value text;
begin
  input_text_value := btrim(coalesce(input_text_value, ''));
  if length(input_text_value) not between 3 and 4000
     or stage_value not in (
       'sources', 'category', 'competitors', 'trends',
       'guidance', 'brief', 'scenarios'
     ) then
    raise exception using
      errcode = '22023', message = 'research_stage_user_input_invalid';
  end if;
  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = run_id_value;
  if product_id_value is null or not exists (
    select 1
    from content_factory.research_stage_branches branch
    where branch.organization_id = organization_id_value
      and branch.run_id = run_id_value
      and branch.id = branch_id_value
  ) then
    raise exception using
      errcode = '42501', message = 'research_stage_user_input_scope_invalid';
  end if;
  source_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'kind', 'research-stage-user-input-v1',
    'branch_id', branch_id_value,
    'stage', stage_value,
    'text', input_text_value,
    'actor_id', actor_id_value
  ));
  insert into content_factory.product_research_sources (
    organization_id, run_id, product_id, created_by, source_type,
    source_url, media_object_id, title, content_hash, trust_level,
    extracted_facts, metadata, fetched_at, published_at, created_at
  ) values (
    organization_id_value, run_id_value, product_id_value, actor_id_value,
    'user_input', null, null, 'Human stage correction: ' || stage_value,
    source_hash_value, 'first_party', jsonb_build_array(jsonb_build_object(
      'kind', 'human_stage_correction', 'stage', stage_value,
      'text', input_text_value
    )), jsonb_build_object(
      'kind', 'research_stage_control_user_input',
      'schema_version', 'research-stage-user-input-v1',
      'branch_id', branch_id_value,
      'stage', stage_value
    ), clock_timestamp(), null, clock_timestamp()
  ) on conflict (run_id, content_hash) do nothing
  returning id into source_id_value;
  if source_id_value is null then
    select source.id into source_id_value
    from content_factory.product_research_sources source
    where source.organization_id = organization_id_value
      and source.run_id = run_id_value
      and source.content_hash = source_hash_value;
  end if;
  if source_id_value is null then
    raise exception using
      errcode = '55000', message = 'research_stage_user_input_not_persisted';
  end if;
  return source_id_value;
end;
$$;

create or replace function
  content_factory_private.materialize_research_stage_main_draft(
    organization_id_value uuid,
    run_id_value uuid,
    branch_id_value uuid,
    stage_value text,
    replacement_value jsonb,
    actor_id_value uuid,
    origin_value text,
    command_id_value uuid,
    action_value text,
    reason_value text,
    request_hash_value text,
    correction_source_id_value uuid
  )
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  current_draft_id_value uuid;
  current_draft content_factory.creative_brief_drafts%rowtype;
  payloads_value jsonb;
  sources_payload jsonb;
  category_payload jsonb;
  competitors_payload jsonb;
  trends_payload jsonb;
  guidance_payload jsonb;
  guidance_raw_payload jsonb;
  brief_payload jsonb;
  scenarios_payload jsonb;
  title_value text;
  brief_value jsonb;
  source_ids_value jsonb;
  task_blueprint_value jsonb;
  version_value integer;
  draft_id_value uuid;
  distinct_draft_count integer;
  source_count integer;
begin
  if stage_value not in (
       'sources', 'category', 'competitors', 'trends',
       'guidance', 'brief', 'scenarios'
     )
     or jsonb_typeof(replacement_value) <> 'object'
     or origin_value not in ('ai', 'human')
     or action_value not in ('patch', 'revert', 'recompute_completed') then
    raise exception using
      errcode = '22023', message = 'research_stage_materialization_invalid';
  end if;
  if not exists (
    select 1
    from content_factory.research_stage_branches branch
    where branch.organization_id = organization_id_value
      and branch.run_id = run_id_value
      and branch.id = branch_id_value
      and branch.branch_key = 'main'
  ) then
    raise exception using
      errcode = '55000', message = 'research_stage_main_branch_required';
  end if;
  select count(distinct head.current_draft_id)
    into distinct_draft_count
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value;
  select head.current_draft_id into current_draft_id_value
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
  order by content_factory_private.research_stage_rank(head.stage)
  limit 1;
  if distinct_draft_count <> 1 or current_draft_id_value is null
     or (
       select count(*)
       from content_factory.research_stage_heads head
       where head.organization_id = organization_id_value
         and head.run_id = run_id_value
         and head.branch_id = branch_id_value
     ) <> 7 then
    raise exception using
      errcode = '55000', message = 'research_stage_main_snapshot_invalid';
  end if;
  select draft.* into current_draft
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.id = current_draft_id_value
  for share;
  if current_draft.id is null or current_draft.status <> 'draft' then
    raise exception using
      errcode = '55000', message = 'research_stage_run_locked';
  end if;

  select jsonb_object_agg(head.stage, artifact.payload)
    into payloads_value
  from content_factory.research_stage_heads head
  join content_factory.research_stage_artifacts artifact
    on artifact.organization_id = head.organization_id
   and artifact.run_id = head.run_id
   and artifact.stage = head.stage
   and artifact.id = head.artifact_id
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value;
  sources_payload := payloads_value -> 'sources';
  category_payload := payloads_value -> 'category';
  competitors_payload := payloads_value -> 'competitors';
  trends_payload := payloads_value -> 'trends';
  guidance_raw_payload := payloads_value -> 'guidance';
  brief_payload := payloads_value -> 'brief';
  scenarios_payload := payloads_value -> 'scenarios';

  case stage_value
    when 'sources' then sources_payload := replacement_value;
    when 'category' then category_payload := replacement_value;
    when 'competitors' then competitors_payload := replacement_value;
    when 'trends' then trends_payload := replacement_value;
    when 'guidance' then guidance_raw_payload := replacement_value;
    when 'brief' then brief_payload := replacement_value;
    when 'scenarios' then scenarios_payload := replacement_value;
  end case;
  sources_payload := content_factory_private.research_stage_effective_payload(
    'sources', sources_payload
  );
  category_payload := content_factory_private.research_stage_effective_payload(
    'category', category_payload
  );
  competitors_payload :=
    content_factory_private.research_stage_effective_payload(
      'competitors', competitors_payload
    );
  trends_payload := content_factory_private.research_stage_effective_payload(
    'trends', trends_payload
  );
  guidance_payload := content_factory_private.research_stage_effective_payload(
    'guidance', guidance_raw_payload
  );

  if jsonb_typeof(sources_payload) <> 'object'
     or sources_payload - 'source_ids' <> '{}'::jsonb
     or jsonb_typeof(sources_payload -> 'source_ids') <> 'array'
     or jsonb_array_length(sources_payload -> 'source_ids') not between 1 and 100
     or jsonb_typeof(category_payload) <> 'object'
     or jsonb_typeof(competitors_payload) <> 'object'
     or jsonb_typeof(trends_payload) <> 'object'
     or jsonb_typeof(guidance_payload) <> 'object'
     or jsonb_typeof(brief_payload) <> 'object'
     or brief_payload - array['title', 'brief']::text[] <> '{}'::jsonb
     or jsonb_typeof(brief_payload -> 'title') <> 'string'
     or jsonb_typeof(brief_payload -> 'brief') <> 'object'
     or jsonb_typeof(scenarios_payload) <> 'object'
     or scenarios_payload - array[
       'scenarios', 'task_blueprint', 'research_task_blueprint'
     ]::text[] <> '{}'::jsonb
     or jsonb_typeof(scenarios_payload -> 'scenarios') <> 'array'
     or jsonb_typeof(scenarios_payload -> 'task_blueprint') <> 'array' then
    raise exception using
      errcode = '22023', message = 'research_stage_replacement_schema_invalid';
  end if;
  title_value := btrim(brief_payload ->> 'title');
  if length(title_value) not between 3 and 240 then
    raise exception using
      errcode = '22023', message = 'research_stage_replacement_schema_invalid';
  end if;
  source_ids_value := content_factory_private.canonical_research_source_ids(
    sources_payload -> 'source_ids'
  );
  if source_ids_value is null
     or jsonb_array_length(source_ids_value)
       <> jsonb_array_length(sources_payload -> 'source_ids') then
    raise exception using
      errcode = '22023', message = 'research_stage_source_set_invalid';
  end if;
  select count(*)::integer into source_count
  from content_factory.product_research_sources source
  where source.organization_id = organization_id_value
    and source.run_id = run_id_value
    and source.id in (
      select source_id.value::uuid
      from jsonb_array_elements_text(source_ids_value) source_id(value)
    );
  if source_count <> jsonb_array_length(source_ids_value) then
    raise exception using
      errcode = '42501', message = 'research_stage_source_set_invalid';
  end if;
  task_blueprint_value := scenarios_payload -> 'task_blueprint';
  perform content_factory_private.validate_research_task_blueprint(
    task_blueprint_value
  );

  brief_value := (
    (brief_payload -> 'brief') - array[
      'category_analysis', 'competitor_analysis', 'trend_analysis',
      'guidance', 'scenarios', 'task_blueprint',
      'human_stage_corrections', 'human_research_decision'
    ]::text[]
  ) || jsonb_build_object(
    'category_analysis', category_payload,
    'competitor_analysis', competitors_payload,
    'trend_analysis', trends_payload,
    'guidance', guidance_payload,
    'scenarios', scenarios_payload -> 'scenarios'
  );
  if scenarios_payload -> 'research_task_blueprint' <> 'null'::jsonb then
    brief_value := brief_value || jsonb_build_object(
      'task_blueprint', scenarios_payload -> 'research_task_blueprint'
    );
  end if;
  if jsonb_typeof(guidance_raw_payload) = 'object'
     and jsonb_typeof(
       guidance_raw_payload -> 'human_research_decision'
     ) = 'object' then
    brief_value := brief_value || jsonb_build_object(
      'human_research_decision',
      guidance_raw_payload -> 'human_research_decision'
    );
  end if;
  if length(brief_value::text) > 131072 then
    raise exception using
      errcode = '22023', message = 'research_stage_materialized_brief_too_large';
  end if;

  select coalesce(max(draft.version), 0) + 1 into version_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value;
  perform set_config(
    'content_factory.research_stage_command_id', command_id_value::text, true
  );
  perform set_config(
    'content_factory.research_stage_target', stage_value, true
  );
  perform set_config(
    'content_factory.research_stage_action', action_value, true
  );
  perform set_config(
    'content_factory.research_stage_reason', reason_value, true
  );
  perform set_config(
    'content_factory.research_stage_request_hash', request_hash_value, true
  );
  perform set_config(
    'content_factory.research_stage_correction_source_id',
    coalesce(correction_source_id_value::text, ''), true
  );
  insert into content_factory.creative_brief_drafts (
    organization_id, run_id, product_id, previous_draft_id, created_by,
    origin, version, status, title, brief, source_ids, task_blueprint,
    content_hash, created_at
  ) values (
    organization_id_value, run_id_value, current_draft.product_id,
    current_draft.id, actor_id_value, origin_value, version_value, 'draft',
    title_value, brief_value, source_ids_value, task_blueprint_value,
    content_factory_private.json_hash(jsonb_build_object(
      'title', title_value,
      'brief', brief_value,
      'source_ids', source_ids_value,
      'task_blueprint', task_blueprint_value
    )), clock_timestamp()
  ) returning id into draft_id_value;
  return draft_id_value;
end;
$$;

create or replace function public.creator_research_stage_control_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  run_id_value uuid;
  branch_id_value uuid;
  branch_row content_factory.research_stage_branches%rowtype;
  branch_revision_hash_value text;
  history_limit_value integer := 30;
  branch_count integer;
  head_count integer;
  noncurrent_count integer;
  current_draft_count integer;
  exact_snapshot_count integer := 0;
  current_draft_id_value uuid;
  current_draft_origin_value text;
  current_draft_status_value text;
  approved_draft_id_value uuid;
  earliest_problem_stage text;
  earliest_problem_state text;
  run_locked boolean;
  generation_handoff_allowed boolean := false;
  active_recompute jsonb;
  branches_value jsonb;
  heads_value jsonb;
  history_value jsonb;
  affected_stages_value jsonb;
  status_value text;
  next_action_value text;
  approval_allowed boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'run_id', 'branch_id', 'history_limit'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_stage_control_status_payload_invalid';
  end if;
  organization_id_value := content_factory_private.resolve_organization(
    p_payload
  );
  perform content_factory_private.membership_role(
    organization_id_value, false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if p_payload ? 'branch_id' then
    branch_id_value := content_factory_private.require_uuid(
      p_payload, 'branch_id'
    );
  end if;
  if p_payload ? 'history_limit' then
    begin
      history_limit_value := (p_payload ->> 'history_limit')::integer;
    exception when invalid_text_representation or numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'research_stage_control_history_limit_invalid';
    end;
  end if;
  if history_limit_value not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'research_stage_control_history_limit_invalid';
  end if;
  if not exists (
    select 1
    from content_factory.product_research_runs run
    where run.organization_id = organization_id_value
      and run.id = run_id_value
  ) then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  select count(*)::integer into branch_count
  from content_factory.research_stage_branches branch
  where branch.organization_id = organization_id_value
    and branch.run_id = run_id_value;
  if branch_id_value is null then
    select branch.id into branch_id_value
    from content_factory.research_stage_branches branch
    where branch.organization_id = organization_id_value
      and branch.run_id = run_id_value
      and branch.branch_key = 'main';
  end if;
  select branch.* into branch_row
  from content_factory.research_stage_branches branch
  where branch.organization_id = organization_id_value
    and branch.run_id = run_id_value
    and branch.id = branch_id_value;
  if branch_row.id is null then
    raise exception using
      errcode = '42501', message = 'research_stage_branch_not_found';
  end if;
  branch_revision_hash_value :=
    content_factory_private.research_stage_branch_revision_hash(
      organization_id_value, run_id_value, branch_id_value
    );

  select count(*)::integer,
    count(*) filter (where head.state <> 'current')::integer,
    count(distinct head.current_draft_id)::integer
    into head_count, noncurrent_count, current_draft_count
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value;
  if current_draft_count = 1 then
    select head.current_draft_id into current_draft_id_value
    from content_factory.research_stage_heads head
    where head.organization_id = organization_id_value
      and head.run_id = run_id_value
      and head.branch_id = branch_id_value
    order by content_factory_private.research_stage_rank(head.stage)
    limit 1;
    select draft.origin, draft.status
      into current_draft_origin_value, current_draft_status_value
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id_value
      and draft.run_id = run_id_value
      and draft.id = current_draft_id_value;
    select count(*)::integer into exact_snapshot_count
    from content_factory.research_stage_heads head
    join content_factory.research_stage_draft_bindings binding
      on binding.organization_id = head.organization_id
     and binding.run_id = head.run_id
     and binding.draft_id = current_draft_id_value
     and binding.stage = head.stage
     and binding.artifact_id = head.artifact_id
     and binding.dependency_hash = head.dependency_hash
    join content_factory.research_stage_artifacts artifact
      on artifact.organization_id = head.organization_id
     and artifact.run_id = head.run_id
     and artifact.stage = head.stage
     and artifact.id = head.artifact_id
     and artifact.input_dependency_hash = binding.dependency_hash
    where head.organization_id = organization_id_value
      and head.run_id = run_id_value
      and head.branch_id = branch_id_value
      and head.state = 'current';
  end if;
  select head.stage, head.state
    into earliest_problem_stage, earliest_problem_state
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
    and head.state <> 'current'
  order by content_factory_private.research_stage_rank(head.stage)
  limit 1;
  select draft.id into approved_draft_id_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.status = 'approved'
  order by draft.version desc, draft.id desc
  limit 1;
  run_locked := approved_draft_id_value is not null;
  generation_handoff_allowed := run_locked
    and branch_row.branch_key = 'main'
    and head_count = 7
    and noncurrent_count = 0
    and current_draft_count = 1
    and current_draft_id_value = approved_draft_id_value
    and exact_snapshot_count = 7;
  select jsonb_build_object(
    'request_id', request.id,
    'child_run_id', request.child_run_id,
    'stage', request.stage,
    'status', request.status,
    'paid_analysis_ack', request.paid_analysis_ack,
    'provider_key', request.provider_key,
    'adapter_version', request.adapter_version,
    'max_provider_attempts', request.max_provider_attempts,
    'provider_attempt_count', request.provider_attempt_count,
    'expected_branch_revision_hash',
      request.expected_branch_revision_hash,
    'created_at', request.created_at,
    'started_at', request.started_at,
    'lease_expires_at', request.lease_expires_at,
    'finished_at', request.finished_at,
    'error_code', request.error_code,
    'error_message', request.error_message,
    'can_cancel', request.status = 'queued' or (
      request.status = 'processing'
      and request.lease_expires_at <= now()
    ) or exists (
      select 1
      from content_factory.research_stage_head_events later_event
      where later_event.organization_id = request.organization_id
        and later_event.run_id = request.run_id
        and later_event.branch_id = request.branch_id
        and later_event.created_at >= request.created_at
        and later_event.request_hash <> request.request_hash
    ),
    'cancel_reason', case
      when exists (
        select 1
        from content_factory.research_stage_head_events later_event
        where later_event.organization_id = request.organization_id
          and later_event.run_id = request.run_id
          and later_event.branch_id = request.branch_id
          and later_event.created_at >= request.created_at
          and later_event.request_hash <> request.request_hash
      ) then 'branch_changed_after_prepare'
      when request.status = 'queued'
        then 'saved_before_provider_claim'
      when request.lease_expires_at <= now()
        then 'processing_lease_expired'
      else 'provider_attempt_lease_active'
    end,
    'automatic_provider_action', false,
    'invoke', case
      when request.status = 'queued'
       and not exists (
        select 1
        from content_factory.research_stage_head_events later_event
        where later_event.organization_id = request.organization_id
          and later_event.run_id = request.run_id
          and later_event.branch_id = request.branch_id
          and later_event.created_at >= request.created_at
          and later_event.request_hash <> request.request_hash
      ) then jsonb_build_object(
        'action', 'analyze', 'research_id', request.child_run_id
      )
      else null
    end
  ) into active_recompute
  from content_factory.research_stage_recompute_requests request
  where request.organization_id = organization_id_value
    and request.run_id = run_id_value
    and request.branch_id = branch_id_value
    and request.status in ('queued', 'processing')
  order by request.created_at desc, request.id desc
  limit 1;

  approval_allowed := branch_row.branch_key = 'main'
    and not run_locked
    and head_count = 7
    and noncurrent_count = 0
    and current_draft_count = 1
    and current_draft_status_value = 'draft'
    and current_draft_origin_value = 'human'
    and exact_snapshot_count = 7
    and active_recompute is null;
  if run_locked and branch_row.branch_key = 'main'
     and not generation_handoff_allowed then
    status_value := 'approved_snapshot_mismatch';
    next_action_value := 'start_new_research_and_preserve_approved_snapshot';
  elsif run_locked and branch_row.branch_key = 'main' then
    status_value := 'approved_locked';
    next_action_value := 'fork_read_only_snapshot_or_start_new_research';
  elsif head_count <> 7 then
    status_value := 'missing_stage_heads';
    next_action_value := 'restore_missing_stage_lineage';
  elsif branch_row.branch_key <> 'main' then
    status_value := 'branch_comparison';
    next_action_value := 'compare_read_only_branch_with_main';
  elsif active_recompute is not null then
    status_value := 'recompute_pending';
    next_action_value := case
      when (active_recompute ->> 'cancel_reason')
             = 'branch_changed_after_prepare'
        then 'discard_superseded_recompute_without_retry'
      when (active_recompute ->> 'status') = 'queued'
        then 'invoke_saved_recompute_or_cancel'
      when (active_recompute ->> 'can_cancel')::boolean
        then 'cancel_expired_recompute_without_retry'
      else 'wait_for_active_provider_lease_without_retry'
    end;
  elsif earliest_problem_state = 'rejected' then
    status_value := 'rejected_stage';
    next_action_value := 'patch_or_revert_rejected_stage';
  elsif earliest_problem_state in (
      'recompute_queued', 'recompute_processing'
    ) then
    status_value := 'recompute_pending';
    next_action_value := 'check_saved_recompute_without_retry';
  elsif noncurrent_count > 0 then
    status_value := 'stale_dependencies';
    next_action_value := 'patch_or_recompute_earliest_stale_stage';
  elsif current_draft_count <> 1 or exact_snapshot_count <> 7 then
    status_value := 'stage_snapshot_mismatch';
    next_action_value := 'restore_exact_stage_snapshot';
  elsif current_draft_status_value <> 'draft' then
    status_value := 'current_draft_not_editable';
    next_action_value := 'start_new_research_or_fork_read_only_snapshot';
  elsif branch_row.branch_key = 'main'
        and current_draft_origin_value <> 'human' then
    status_value := 'ai_revision_needs_human_snapshot';
    next_action_value := 'save_human_review_snapshot';
  elsif branch_row.branch_key = 'main' then
    status_value := 'ready_for_review';
    next_action_value := 'review_and_approve_current_draft';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'branch_id', branch.id,
    'branch_key', branch.branch_key,
    'parent_branch_id', branch.parent_branch_id,
    'reason', branch.reason,
    'created_by', branch.created_by,
    'created_at', branch.created_at,
    'is_selected', branch.id = branch_id_value,
    'head_count', (
      select count(*)
      from content_factory.research_stage_heads branch_head
      where branch_head.organization_id = branch.organization_id
        and branch_head.run_id = branch.run_id
        and branch_head.branch_id = branch.id
    ),
    'problem_count', (
      select count(*)
      from content_factory.research_stage_heads branch_head
      where branch_head.organization_id = branch.organization_id
        and branch_head.run_id = branch.run_id
        and branch_head.branch_id = branch.id
        and branch_head.state <> 'current'
    )
  ) order by case when branch.branch_key = 'main' then 0 else 1 end,
    branch.created_at, branch.id), '[]'::jsonb)
    into branches_value
  from (
    select candidate_branch.*
    from content_factory.research_stage_branches candidate_branch
    where candidate_branch.organization_id = organization_id_value
      and candidate_branch.run_id = run_id_value
    order by case when candidate_branch.branch_key = 'main'
      then 0 else 1 end, candidate_branch.created_at, candidate_branch.id
    limit 50
  ) branch;

  select coalesce(jsonb_agg(jsonb_build_object(
    'stage', head.stage,
    'state', head.state,
    'head_event_id', head.head_event_id,
    'artifact_id', head.artifact_id,
    'artifact_version', artifact.version,
    'parent_artifact_id', artifact.parent_artifact_id,
    'content_hash', artifact.content_hash,
    'dependency_hash', head.dependency_hash,
    'artifact_input_dependency_hash', artifact.input_dependency_hash,
    'stale_due_to_artifact_ids', head.stale_due_to_artifact_ids,
    'current_draft_id', head.current_draft_id,
    'payload', artifact.payload,
    'evidence_count', jsonb_array_length(
      artifact.input_dependencies -> 'evidence'
    ),
    'artifact_origin', artifact.origin,
    'artifact_actor_id', artifact.actor_id,
    'artifact_created_at', artifact.created_at,
    'updated_at', head.updated_at,
    'revert_candidates', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'artifact_id', candidate.id,
        'version', candidate.version,
        'content_hash', candidate.content_hash,
        'input_dependency_hash', candidate.input_dependency_hash,
        'origin', candidate.origin,
        'created_at', candidate.created_at,
        'payload_preview', left(candidate.payload::text, 500)
      ) order by candidate.version desc, candidate.id desc), '[]'::jsonb)
      from (
        select candidate_artifact.*
        from content_factory.research_stage_artifacts candidate_artifact
        where candidate_artifact.organization_id = head.organization_id
          and candidate_artifact.run_id = head.run_id
          and candidate_artifact.stage = head.stage
          and candidate_artifact.id <> head.artifact_id
        order by candidate_artifact.version desc, candidate_artifact.id desc
        limit 10
      ) candidate
    ),
    'allowed_actions', case
      when branch.branch_key <> 'main' then '[]'::jsonb
      when active_recompute is not null then case
        when head.stage = active_recompute ->> 'stage'
         and (active_recompute ->> 'can_cancel')::boolean
          then jsonb_build_array('cancel')
        else '[]'::jsonb
      end
      when run_locked and branch.branch_key = 'main'
        then jsonb_build_array('fork')
      when head.stage = 'sources'
        then jsonb_build_array('patch', 'reject', 'revert', 'fork')
      else jsonb_build_array(
        'patch', 'reject', 'revert', 'fork', 'recompute'
      )
    end
  ) order by content_factory_private.research_stage_rank(head.stage)),
    '[]'::jsonb)
    into heads_value
  from content_factory.research_stage_heads head
  join content_factory.research_stage_branches branch
    on branch.organization_id = head.organization_id
   and branch.run_id = head.run_id
   and branch.id = head.branch_id
  join content_factory.research_stage_artifacts artifact
    on artifact.organization_id = head.organization_id
   and artifact.run_id = head.run_id
   and artifact.stage = head.stage
   and artifact.id = head.artifact_id
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value;

  select coalesce(jsonb_agg(history_entry.value
    order by history_entry.created_at desc, history_entry.id desc),
    '[]'::jsonb) into history_value
  from (
    select event.id, event.created_at, jsonb_build_object(
      'event_id', event.id,
      'command_id', event.command_id,
      'stage', event.stage,
      'action', event.action,
      'state', event.state,
      'artifact_id', event.artifact_id,
      'prior_artifact_id', event.prior_artifact_id,
      'draft_id', event.draft_id,
      'correction_source_id', event.correction_source_id,
      'reason', event.reason,
      'actor_id', event.actor_id,
      'origin', event.origin,
      'created_at', event.created_at
    ) as value
    from content_factory.research_stage_head_events event
    where event.organization_id = organization_id_value
      and event.run_id = run_id_value
      and event.branch_id = branch_id_value
    order by event.created_at desc, event.id desc
    limit history_limit_value
  ) history_entry;
  select coalesce(jsonb_agg(head.stage
    order by content_factory_private.research_stage_rank(head.stage)),
    '[]'::jsonb) into affected_stages_value
  from content_factory.research_stage_heads head
  where head.organization_id = organization_id_value
    and head.run_id = run_id_value
    and head.branch_id = branch_id_value
    and head.state <> 'current';

  return jsonb_build_object(
    'ok', true,
    'version', 'research-stage-control-v2',
    'organization_id', organization_id_value,
    'run_id', run_id_value,
    'selected_branch', jsonb_build_object(
      'branch_id', branch_row.id,
      'branch_key', branch_row.branch_key,
      'branch_revision_hash', branch_revision_hash_value,
      'parent_branch_id', branch_row.parent_branch_id,
      'reason', branch_row.reason,
      'created_at', branch_row.created_at
    ),
    'branches', branches_value,
    'heads', heads_value,
    'history', history_value,
    'history_limit', history_limit_value,
    'history_has_more', (
      select count(*) > history_limit_value
      from content_factory.research_stage_head_events event
      where event.organization_id = organization_id_value
        and event.run_id = run_id_value
        and event.branch_id = branch_id_value
    ),
    'active_recompute', active_recompute,
    'guidance', jsonb_build_object(
      'status', status_value,
      'recommended_next_action', next_action_value,
      'earliest_problem_stage', earliest_problem_stage,
      'earliest_problem_state', earliest_problem_state,
      'affected_stages', affected_stages_value,
      'approval_allowed', approval_allowed,
      'current_draft_id', current_draft_id_value,
      'current_draft_origin', current_draft_origin_value,
      'current_draft_status', current_draft_status_value,
      'exact_snapshot_stage_count', exact_snapshot_count,
      'approved_draft_id', approved_draft_id_value,
      'generation_handoff_allowed', generation_handoff_allowed,
      'recompute_requires_paid_confirmation', true,
      'automatic_provider_action', false,
      'automatic_spend', false,
      'automatic_generation', false,
      'automatic_publication', false,
      'branch_count', branch_count
    )
  );
end;
$$;

alter function public.system_claim_product_research(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_claim_product_research(jsonb)
  rename to system_claim_product_research_pre_stage_recompute_v3;
revoke all on function
  content_factory_private
    .system_claim_product_research_pre_stage_recompute_v3(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.system_claim_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result_value jsonb;
  run_id_value uuid;
  request_row content_factory.research_stage_recompute_requests%rowtype;
  correction_text_value text;
  context_value jsonb;
  lease_expires_at_value timestamptz;
  supersede_command_id_value uuid := extensions.gen_random_uuid();
begin
  p_payload := content_factory_private.require_payload(p_payload);
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  select request.* into request_row
  from content_factory.research_stage_recompute_requests request
  where request.child_run_id = run_id_value;
  if request_row.id is null then
    return content_factory_private
      .system_claim_product_research_pre_stage_recompute_v3(p_payload);
  end if;
  perform pg_advisory_xact_lock(
    hashtext(request_row.organization_id::text),
    hashtext('research-stage-control:' || request_row.run_id::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(request_row.organization_id::text),
    hashtext('brief:' || request_row.run_id::text)
  );
  select request.* into request_row
  from content_factory.research_stage_recompute_requests request
  where request.child_run_id = run_id_value
  for update;
  if request_row.status <> 'queued' then
    raise exception using
      errcode = '55000',
      message = 'research_stage_recompute_not_claimable';
  end if;
  select source.extracted_facts #>> '{0,text}' into correction_text_value
  from content_factory.product_research_sources source
  where source.organization_id = request_row.organization_id
    and source.run_id = request_row.run_id
    and source.id = request_row.correction_source_id;
  if length(btrim(coalesce(correction_text_value, ''))) not between 3 and 4000
     or content_factory_private.json_hash(request_row.input_snapshot)
       <> request_row.input_snapshot_hash
     or request_row.input_snapshot ->> 'branch_revision_hash'
       <> request_row.expected_branch_revision_hash then
    raise exception using
      errcode = '55000',
      message = 'research_stage_recompute_context_integrity_invalid';
  end if;
  if exists (
    select 1
    from content_factory.research_stage_head_events event
    where event.organization_id = request_row.organization_id
      and event.run_id = request_row.run_id
      and event.branch_id = request_row.branch_id
      and event.created_at >= request_row.created_at
      and event.request_hash <> request_row.request_hash
  ) then
    perform set_config(
      'content_factory.research_stage_control_write', 'on', true
    );
    update content_factory.product_research_runs run
    set status = 'cancelled',
        lease_expires_at = null,
        finished_at = clock_timestamp(),
        updated_at = clock_timestamp(),
        error_code = 'stage_recompute_superseded',
        error_message =
          'The root branch changed before the saved provider claim.'
    where run.organization_id = request_row.organization_id
      and run.id = request_row.child_run_id
      and (
        run.status = 'queued'
        or (
          run.status = 'processing'
          and run.lease_expires_at <= clock_timestamp()
        )
      );
    perform content_factory_private.refresh_research_stage_branch_states(
      request_row.organization_id, request_row.run_id,
      request_row.branch_id, request_row.stage,
      supersede_command_id_value, 'recompute_superseded',
      'Saved recompute superseded before provider claim',
      request_row.requested_by, request_row.correction_source_id,
      request_row.expected_head_event_id, request_row.request_hash
    );
    update content_factory.research_stage_recompute_requests request
    set status = 'superseded',
        error_code = 'head_changed_before_provider_claim',
        error_message =
          'The branch changed after prepare; no provider claim was made.',
        lease_expires_at = null,
        finished_at = clock_timestamp()
    where request.organization_id = request_row.organization_id
      and request.id = request_row.id;
    return content_factory_private
      .system_claim_product_research_pre_stage_recompute_v3(p_payload);
  end if;
  result_value := content_factory_private
    .system_claim_product_research_pre_stage_recompute_v3(p_payload);
  if result_value -> 'claimed' = 'true'::jsonb
     and result_value #>> '{run,status}' = 'processing'
     and request_row.status = 'queued' then
    begin
      lease_expires_at_value :=
        (result_value #>> '{run,lease_expires_at}')::timestamptz;
    exception when invalid_text_representation or datetime_field_overflow then
      lease_expires_at_value := null;
    end;
    lease_expires_at_value := coalesce(
      lease_expires_at_value, clock_timestamp() + interval '5 minutes'
    );
    perform set_config(
      'content_factory.research_stage_control_write', 'on', true
    );
    update content_factory.research_stage_recompute_requests request
    set status = 'processing',
        provider_attempt_count = 1,
        started_at = clock_timestamp(),
        lease_expires_at = lease_expires_at_value
    where request.organization_id = request_row.organization_id
      and request.id = request_row.id
      and request.status = 'queued';
    select request.* into request_row
    from content_factory.research_stage_recompute_requests request
    where request.organization_id = request_row.organization_id
      and request.id = request_row.id;
    perform content_factory_private.write_research_stage_head_event(
      request_row.organization_id, request_row.run_id,
      request_row.branch_id, request_row.id, request_row.stage,
      'recompute_processing', 'recompute_processing', head.artifact_id,
      head.dependency_hash, head.stale_due_to_artifact_ids,
      head.current_draft_id, request_row.correction_source_id,
      'Claimed the saved child run for one provider attempt',
      request_row.requested_by, 'system', request_row.request_hash
    )
    from content_factory.research_stage_heads head
    where head.organization_id = request_row.organization_id
      and head.run_id = request_row.run_id
      and head.branch_id = request_row.branch_id
      and head.stage = request_row.stage
      and head.artifact_id = request_row.expected_artifact_id
      and head.state = 'recompute_queued';
  end if;
  context_value := jsonb_build_object(
    'schema_version', 'research-stage-recompute-context-v1',
    'request_id', request_row.id,
    'root_run_id', request_row.run_id,
    'branch_id', request_row.branch_id,
    'requested_stage', request_row.stage,
    'correction', correction_text_value,
    'input_snapshot_hash', request_row.input_snapshot_hash,
    'input_snapshot', request_row.input_snapshot
  );
  if octet_length(context_value::text) > 98304 then
    raise exception using
      errcode = '54000',
      message = 'research_stage_recompute_context_too_large';
  end if;
  return jsonb_set(
    result_value, '{run,recompute_context}', context_value, true
  );
end;
$$;

create or replace function
  content_factory_private.fail_research_stage_recompute(
    request_id_value uuid,
    error_code_value text,
    error_message_value text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  request_row content_factory.research_stage_recompute_requests%rowtype;
  head_row content_factory.research_stage_heads%rowtype;
begin
  error_code_value := left(btrim(coalesce(error_code_value, '')), 100);
  error_message_value := left(
    btrim(coalesce(error_message_value, '')), 2000
  );
  if length(error_code_value) not between 3 and 100 then
    error_code_value := 'stage_recompute_failed';
  end if;
  if length(error_message_value) not between 3 and 2000 then
    error_message_value := 'Stage recompute did not complete safely.';
  end if;
  select request.* into request_row
  from content_factory.research_stage_recompute_requests request
  where request.id = request_id_value
  for update;
  if request_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_stage_recompute_request_missing';
  end if;
  if request_row.status in ('completed', 'failed', 'superseded') then
    return jsonb_build_object(
      'ok', true, 'applied', request_row.status = 'completed',
      'recompute_request', true, 'request_id', request_row.id,
      'status', request_row.status,
      'completion_hash', request_row.completion_hash,
      'error_code', request_row.error_code
    );
  end if;
  perform set_config(
    'content_factory.research_stage_control_write', 'on', true
  );
  update content_factory.research_stage_recompute_requests request
  set status = 'failed', error_code = error_code_value,
      error_message = error_message_value, lease_expires_at = null,
      finished_at = clock_timestamp()
  where request.organization_id = request_row.organization_id
    and request.id = request_row.id;
  select head.* into head_row
  from content_factory.research_stage_heads head
  where head.organization_id = request_row.organization_id
    and head.run_id = request_row.run_id
    and head.branch_id = request_row.branch_id
    and head.stage = request_row.stage
  for update;
  if head_row.state in ('recompute_queued', 'recompute_processing')
     and head_row.artifact_id = request_row.expected_artifact_id then
    perform content_factory_private.write_research_stage_head_event(
      request_row.organization_id, request_row.run_id,
      request_row.branch_id, extensions.gen_random_uuid(),
      request_row.stage, 'recompute_failed', 'recompute_failed',
      head_row.artifact_id, head_row.dependency_hash,
      head_row.stale_due_to_artifact_ids, head_row.current_draft_id,
      request_row.correction_source_id,
      'Stage recompute failed: ' || left(error_code_value, 450),
      request_row.requested_by, 'system',
      content_factory_private.json_hash(jsonb_build_object(
        'request_id', request_row.id,
        'child_run_id', request_row.child_run_id,
        'status', 'failed',
        'error_code', error_code_value
      ))
    );
  end if;
  return jsonb_build_object(
    'ok', true, 'applied', false, 'recompute_request', true,
    'request_id', request_row.id, 'status', 'failed',
    'error_code', error_code_value
  );
end;
$$;

create or replace function public.system_apply_research_stage_recompute(
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
  child_run_id_value uuid;
  request_row content_factory.research_stage_recompute_requests%rowtype;
  child_run_row content_factory.product_research_runs%rowtype;
  child_draft content_factory.creative_brief_drafts%rowtype;
  root_draft content_factory.creative_brief_drafts%rowtype;
  root_draft_id_value uuid;
  root_source_ids_value jsonb;
  root_source_count integer;
  version_value integer;
  apply_hash_value text;
  apply_command_id_value uuid := extensions.gen_random_uuid();
  child_error_code_value text;
  apply_phase_value text;
  apply_failure_code_value text;
  apply_failure_message_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'child_run_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_stage_recompute_apply_payload_invalid';
  end if;
  child_run_id_value := content_factory_private.require_uuid(
    p_payload, 'child_run_id'
  );
  select request.* into request_row
  from content_factory.research_stage_recompute_requests request
  where request.child_run_id = child_run_id_value;
  if request_row.id is null then
    return jsonb_build_object(
      'ok', true, 'applied', false, 'recompute_request', false
    );
  end if;
  -- Use the same lock order as the public controller. This also serializes
  -- apply with the legacy human draft editor and approval transaction.
  perform pg_advisory_xact_lock(
    hashtext(request_row.organization_id::text),
    hashtext('research-stage-control:' || request_row.run_id::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(request_row.organization_id::text),
    hashtext('brief:' || request_row.run_id::text)
  );
  select request.* into request_row
  from content_factory.research_stage_recompute_requests request
  where request.child_run_id = child_run_id_value
  for update;
  if request_row.status in ('completed', 'failed', 'superseded') then
    return jsonb_build_object(
      'ok', true,
      'applied', request_row.status = 'completed',
      'recompute_request', true,
      'request_id', request_row.id,
      'status', request_row.status,
      'completion_hash', request_row.completion_hash,
      'error_code', request_row.error_code
    );
  end if;
  if content_factory_private.json_hash(request_row.input_snapshot)
       <> request_row.input_snapshot_hash
     or request_row.input_snapshot ->> 'branch_revision_hash'
       <> request_row.expected_branch_revision_hash then
    raise exception using
      errcode = '55000',
      message = 'research_stage_recompute_snapshot_integrity_invalid';
  end if;
  -- Supersession is checked before the child status. A later root command must
  -- release the active branch slot even while the child is still queued or
  -- processing; the paid provider is never retried automatically.
  if exists (
    select 1
    from content_factory.research_stage_head_events event
    where event.organization_id = request_row.organization_id
      and event.run_id = request_row.run_id
      and event.branch_id = request_row.branch_id
      and event.created_at >= request_row.created_at
      and event.request_hash <> request_row.request_hash
  ) then
    perform set_config(
      'content_factory.research_stage_control_write', 'on', true
    );
    update content_factory.product_research_runs run
    set status = 'cancelled',
        lease_expires_at = null,
        finished_at = clock_timestamp(),
        updated_at = clock_timestamp(),
        error_code = 'stage_recompute_superseded',
        error_message =
          'The root branch changed after recompute preparation.'
    where run.organization_id = request_row.organization_id
      and run.id = request_row.child_run_id
      and (
        run.status = 'queued'
        or (
          run.status = 'processing'
          and run.lease_expires_at <= clock_timestamp()
        )
      );
    perform content_factory_private.refresh_research_stage_branch_states(
      request_row.organization_id, request_row.run_id,
      request_row.branch_id, request_row.stage, apply_command_id_value,
      'recompute_superseded',
      'Saved recompute superseded by a later root branch command',
      request_row.requested_by, request_row.correction_source_id,
      request_row.expected_head_event_id,
      request_row.request_hash
    );
    update content_factory.research_stage_recompute_requests request
    set status = 'superseded',
        error_code = 'head_changed_during_recompute',
        error_message =
          'The branch changed after recompute preparation; output was not applied.',
        lease_expires_at = null,
        finished_at = clock_timestamp()
    where request.organization_id = request_row.organization_id
      and request.id = request_row.id;
    return jsonb_build_object(
      'ok', true, 'applied', false, 'recompute_request', true,
      'request_id', request_row.id, 'status', 'superseded',
      'error_code', 'head_changed_during_recompute'
    );
  end if;
  select run.* into child_run_row
  from content_factory.product_research_runs run
  where run.organization_id = request_row.organization_id
    and run.id = request_row.child_run_id
  for share;
  if child_run_row.id is null
     or child_run_row.status in ('queued', 'processing') then
    return jsonb_build_object(
      'ok', true, 'applied', false, 'recompute_request', true,
      'request_id', request_row.id, 'status', request_row.status
    );
  end if;
  perform set_config(
    'content_factory.research_stage_control_write', 'on', true
  );
  if child_run_row.status <> 'completed' then
    child_error_code_value := coalesce(
      child_run_row.error_code, 'child_research_failed'
    );
    return content_factory_private.fail_research_stage_recompute(
      request_row.id, child_error_code_value, coalesce(
        child_run_row.error_message,
        'Child research did not complete successfully.'
      )
    );
  end if;

  select draft.* into child_draft
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = request_row.organization_id
    and draft.run_id = request_row.child_run_id
    and draft.origin = 'ai'
  order by draft.version desc, draft.id desc
  limit 1;
  if child_draft.id is null
     or child_run_row.completion_hash is null
     or not content_factory_private.research_brief_has_v2_sections(
       child_draft.brief
     ) then
    return content_factory_private.fail_research_stage_recompute(
      request_row.id, 'child_output_invalid',
      'The terminal child run did not contain a complete v2 research draft.'
    );
  end if;

  begin
    apply_phase_value := 'source_copy';
    insert into content_factory.product_research_sources (
    organization_id, run_id, product_id, created_by, source_type,
    source_url, media_object_id, title, content_hash, trust_level,
    extracted_facts, metadata, fetched_at, published_at, created_at
    )
    select source.organization_id, request_row.run_id, source.product_id,
    request_row.requested_by, source.source_type, source.source_url,
    source.media_object_id, source.title, source.content_hash,
    source.trust_level, source.extracted_facts,
    source.metadata || jsonb_build_object(
      'recompute_child_run_id', request_row.child_run_id,
      'recompute_request_id', request_row.id
    ), source.fetched_at, source.published_at, clock_timestamp()
  from content_factory.product_research_sources source
  where source.organization_id = request_row.organization_id
    and source.run_id = request_row.child_run_id
    and source.id in (
      select selected.value::uuid
      from jsonb_array_elements_text(child_draft.source_ids) selected(value)
    )
    on conflict (run_id, content_hash) do nothing;

    apply_phase_value := 'source_map';
    select count(*)::integer,
      coalesce(jsonb_agg(root_source.id order by selected.ordinal), '[]'::jsonb)
      into root_source_count, root_source_ids_value
    from jsonb_array_elements_text(child_draft.source_ids)
      with ordinality selected(value, ordinal)
    join content_factory.product_research_sources child_source
      on child_source.organization_id = request_row.organization_id
     and child_source.run_id = request_row.child_run_id
     and child_source.id = selected.value::uuid
    join content_factory.product_research_sources root_source
      on root_source.organization_id = request_row.organization_id
     and root_source.run_id = request_row.run_id
     and root_source.content_hash = child_source.content_hash;
    if root_source_count <> jsonb_array_length(child_draft.source_ids)
       or root_source_count < 1 then
      raise exception using
        errcode = 'P0001', message = 'child_source_copy_invalid';
    end if;

    apply_phase_value := 'root_lock';
    select draft.* into root_draft
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = request_row.organization_id
      and draft.run_id = request_row.run_id
    order by draft.version desc, draft.id desc
    limit 1
    for share;
    if root_draft.id is null or root_draft.status <> 'draft' then
      raise exception using
        errcode = 'P0001', message = 'root_run_locked_during_recompute';
    end if;
    select coalesce(max(draft.version), 0) + 1 into version_value
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = request_row.organization_id
      and draft.run_id = request_row.run_id;
    perform set_config(
      'content_factory.research_stage_command_id',
      apply_command_id_value::text, true
    );
    perform set_config(
      'content_factory.research_stage_target', request_row.stage, true
    );
    perform set_config(
      'content_factory.research_stage_action', 'recompute_completed', true
    );
    perform set_config(
      'content_factory.research_stage_reason',
      'Applied exact completed child research recompute', true
    );
    perform set_config(
      'content_factory.research_stage_request_hash',
      request_row.request_hash, true
    );
    perform set_config(
      'content_factory.research_stage_correction_source_id',
      request_row.correction_source_id::text, true
    );
    apply_phase_value := 'root_draft_insert';
    insert into content_factory.creative_brief_drafts (
      organization_id, run_id, product_id, previous_draft_id, created_by,
      origin, version, status, title, brief, source_ids, task_blueprint,
      content_hash, created_at
    ) values (
      request_row.organization_id, request_row.run_id, root_draft.product_id,
      root_draft.id, request_row.requested_by, 'ai', version_value, 'draft',
      child_draft.title, child_draft.brief, root_source_ids_value,
      child_draft.task_blueprint,
      content_factory_private.json_hash(jsonb_build_object(
        'title', child_draft.title,
        'brief', child_draft.brief,
        'source_ids', root_source_ids_value,
        'task_blueprint', child_draft.task_blueprint
      )), clock_timestamp()
    ) returning id into root_draft_id_value;
  exception when others then
    if apply_phase_value in ('source_copy', 'source_map') then
      apply_failure_code_value := 'child_source_copy_invalid';
      apply_failure_message_value :=
        'Not every selected child source could be atomically mapped to the root run.';
    elsif apply_phase_value = 'root_lock' then
      apply_failure_code_value := 'root_run_locked_during_recompute';
      apply_failure_message_value :=
        'The root draft was no longer editable when recompute completed.';
    else
      apply_failure_code_value := 'root_draft_apply_failed';
      apply_failure_message_value :=
        'The child result passed terminal checks but could not be materialized.';
    end if;
  end;
  if apply_failure_code_value is not null then
    return content_factory_private.fail_research_stage_recompute(
      request_row.id, apply_failure_code_value, apply_failure_message_value
    );
  end if;

  apply_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'request_id', request_row.id,
    'child_run_id', request_row.child_run_id,
    'child_completion_hash', child_run_row.completion_hash,
    'root_draft_id', root_draft_id_value
  ));
  update content_factory.research_stage_recompute_requests request
  set status = 'completed', completion_hash = apply_hash_value,
      error_code = null, error_message = null,
      lease_expires_at = null, finished_at = clock_timestamp()
  where request.organization_id = request_row.organization_id
    and request.id = request_row.id;
  return jsonb_build_object(
    'ok', true, 'applied', true, 'recompute_request', true,
    'request_id', request_row.id, 'status', 'completed',
    'root_run_id', request_row.run_id,
    'root_draft_id', root_draft_id_value,
    'child_run_id', request_row.child_run_id,
    'completion_hash', apply_hash_value
  );
end;
$$;

revoke all on function public.creator_control_research_stage(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_research_stage_control_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_approve_creative_brief(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_control_research_stage(jsonb)
  to authenticated;
grant execute on function public.creator_research_stage_control_status(jsonb)
  to authenticated;
grant execute on function public.creator_approve_creative_brief(jsonb)
  to authenticated;

revoke all on function public.system_claim_product_research(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_apply_research_stage_recompute(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_claim_product_research(jsonb)
  to service_role;
grant execute on function public.system_apply_research_stage_recompute(jsonb)
  to service_role;

-- Internal graph mutation remains owner-only. Public and worker entrypoints
-- must pass through the narrow SECURITY DEFINER contracts above.
revoke all on function content_factory_private.capture_research_stage_draft(
  content_factory.creative_brief_drafts
) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_research_guidance_approval()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.assert_research_stage_draft_ready(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_research_stage_control_approval()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_stage_branch_dependencies(
    uuid, uuid, uuid, text, jsonb
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.write_research_stage_head_event(
    uuid, uuid, uuid, uuid, text, text, text, uuid, text, jsonb,
    uuid, uuid, text, uuid, text, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_research_stage_control_state_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_stage_branch_revision_hash(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_stage_current_dependency_state(
    uuid, uuid, uuid, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.refresh_research_stage_branch_states(
    uuid, uuid, uuid, text, uuid, text, text, uuid, uuid, uuid, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_stage_effective_payload(text, jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_stage_stale_due_from_draft(
    uuid, uuid, uuid, text, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.sync_research_stage_main_heads(
    content_factory.creative_brief_drafts, uuid, text, text, uuid,
    text, text, text, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_stage_draft_trigger()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.create_research_stage_user_input(
    uuid, uuid, uuid, text, text, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.materialize_research_stage_main_draft(
    uuid, uuid, uuid, text, jsonb, uuid, text, uuid, text, text, text, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.fail_research_stage_recompute(uuid, text, text)
  from public, anon, authenticated, service_role;

select pg_notify('pgrst', 'reload schema');

commit;

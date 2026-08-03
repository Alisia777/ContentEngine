begin;

-- Research stage control is an audit/control plane only. It neither calls live
-- providers nor activates generation or learning policies.

create unique index if not exists creative_brief_drafts_org_run_id_uq
  on content_factory.creative_brief_drafts (organization_id, run_id, id);
create unique index if not exists product_research_sources_org_run_id_uq
  on content_factory.product_research_sources (organization_id, run_id, id);

create table if not exists content_factory.research_stage_artifacts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    stage text not null check (stage in (
      'sources', 'category', 'competitors', 'trends',
      'guidance', 'brief', 'scenarios'
    )),
    version integer not null check (version between 1 and 100000),
    parent_artifact_id uuid,
    payload jsonb not null,
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    actor_id uuid not null,
    origin text not null check (origin in ('ai', 'human')),
    created_at timestamptz not null default now(),
    constraint research_stage_artifacts_org_id_uq
      unique (organization_id, id),
    constraint research_stage_artifacts_org_run_stage_id_uq
      unique (organization_id, run_id, stage, id),
    constraint research_stage_artifacts_run_stage_version_uq
      unique (organization_id, run_id, stage, version),
    constraint research_stage_artifacts_run_stage_content_uq
      unique (organization_id, run_id, stage, content_hash),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, actor_id)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, run_id, stage, parent_artifact_id)
      references content_factory.research_stage_artifacts(
        organization_id, run_id, stage, id
      ),
    check (jsonb_typeof(payload) in ('object', 'array', 'null')),
    -- A scenarios artifact can contain both independently bounded brief and
    -- task-blueprint JSON values, so leave safe wrapper headroom.
    check (length(payload::text) <= 524288),
    check (
      (version = 1 and parent_artifact_id is null)
      or (version > 1 and parent_artifact_id is not null)
    )
);

create index if not exists research_stage_artifacts_run_stage_idx
  on content_factory.research_stage_artifacts
  (organization_id, run_id, stage, version desc);

create table if not exists content_factory.research_stage_draft_bindings (
    organization_id uuid not null,
    run_id uuid not null,
    draft_id uuid not null,
    stage text not null check (stage in (
      'sources', 'category', 'competitors', 'trends',
      'guidance', 'brief', 'scenarios'
    )),
    artifact_id uuid not null,
    dependency_hash text not null check (dependency_hash ~ '^[0-9a-f]{64}$'),
    actor_id uuid not null,
    origin text not null check (origin in ('ai', 'human')),
    bound_at timestamptz not null default now(),
    primary key (organization_id, draft_id, stage),
    constraint research_stage_bindings_exact_uq
      unique (organization_id, run_id, draft_id, stage, artifact_id),
    foreign key (organization_id, run_id, draft_id)
      references content_factory.creative_brief_drafts(organization_id, run_id, id),
    foreign key (organization_id, run_id, stage, artifact_id)
      references content_factory.research_stage_artifacts(
        organization_id, run_id, stage, id
      ),
    foreign key (organization_id, actor_id)
      references content_factory.memberships(organization_id, profile_id)
);

create index if not exists research_stage_bindings_artifact_idx
  on content_factory.research_stage_draft_bindings
  (organization_id, run_id, artifact_id, draft_id);

create table if not exists content_factory.research_stage_binding_evidence (
    organization_id uuid not null,
    run_id uuid not null,
    draft_id uuid not null,
    stage text not null check (stage in (
      'sources', 'category', 'competitors', 'trends',
      'guidance', 'brief', 'scenarios'
    )),
    artifact_id uuid not null,
    source_id uuid not null,
    ordinal integer not null check (ordinal between 1 and 100),
    created_at timestamptz not null default now(),
    primary key (organization_id, draft_id, stage, source_id),
    unique (organization_id, draft_id, stage, ordinal),
    foreign key (organization_id, run_id, draft_id, stage, artifact_id)
      references content_factory.research_stage_draft_bindings(
        organization_id, run_id, draft_id, stage, artifact_id
      ),
    foreign key (organization_id, run_id, source_id)
      references content_factory.product_research_sources(organization_id, run_id, id)
);

create index if not exists research_stage_binding_evidence_source_idx
  on content_factory.research_stage_binding_evidence
  (organization_id, run_id, source_id, draft_id, stage);

create table if not exists content_factory.research_stage_decisions (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    draft_id uuid not null,
    stage text not null check (stage in (
      'sources', 'category', 'competitors', 'trends',
      'guidance', 'brief', 'scenarios'
    )),
    artifact_id uuid not null,
    decision text not null check (decision in (
      'generated', 'patched', 'approved', 'rejected', 'reverted'
    )),
    actor_id uuid not null,
    origin text not null check (origin in ('ai', 'human', 'system')),
    decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    unique (organization_id, id),
    unique (organization_id, decision_hash),
    unique (organization_id, draft_id, stage, artifact_id, decision),
    foreign key (organization_id, run_id, draft_id, stage, artifact_id)
      references content_factory.research_stage_draft_bindings(
        organization_id, run_id, draft_id, stage, artifact_id
      ),
    foreign key (organization_id, actor_id)
      references content_factory.memberships(organization_id, profile_id)
);

create index if not exists research_stage_decisions_timeline_idx
  on content_factory.research_stage_decisions
  (organization_id, run_id, draft_id, created_at, id);

alter table content_factory.research_stage_artifacts enable row level security;
alter table content_factory.research_stage_draft_bindings enable row level security;
alter table content_factory.research_stage_binding_evidence enable row level security;
alter table content_factory.research_stage_decisions enable row level security;

revoke all on content_factory.research_stage_artifacts
  from public, anon, authenticated;
revoke all on content_factory.research_stage_draft_bindings
  from public, anon, authenticated;
revoke all on content_factory.research_stage_binding_evidence
  from public, anon, authenticated;
revoke all on content_factory.research_stage_decisions
  from public, anon, authenticated;

grant all on content_factory.research_stage_artifacts to service_role;
grant all on content_factory.research_stage_draft_bindings to service_role;
grant all on content_factory.research_stage_binding_evidence to service_role;
grant all on content_factory.research_stage_decisions to service_role;

create or replace function content_factory_private.reject_research_stage_ledger_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_append_only';
end;
$$;

drop trigger if exists reject_research_stage_artifact_mutation
  on content_factory.research_stage_artifacts;
create trigger reject_research_stage_artifact_mutation
before update or delete on content_factory.research_stage_artifacts
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

drop trigger if exists reject_research_stage_binding_mutation
  on content_factory.research_stage_draft_bindings;
create trigger reject_research_stage_binding_mutation
before update or delete on content_factory.research_stage_draft_bindings
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

drop trigger if exists reject_research_stage_evidence_mutation
  on content_factory.research_stage_binding_evidence;
create trigger reject_research_stage_evidence_mutation
before update or delete on content_factory.research_stage_binding_evidence
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

drop trigger if exists reject_research_stage_decision_mutation
  on content_factory.research_stage_decisions;
create trigger reject_research_stage_decision_mutation
before update or delete on content_factory.research_stage_decisions
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

create or replace function content_factory_private.research_stage_rank(stage_value text)
returns integer
language sql
immutable
set search_path = ''
as $$
  select case $1
    when 'sources' then 1
    when 'category' then 2
    when 'competitors' then 3
    when 'trends' then 4
    when 'guidance' then 5
    when 'brief' then 6
    when 'scenarios' then 7
    else null
  end
$$;

create or replace function content_factory_private.canonical_research_source_ids(
  source_ids_value jsonb
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select case
    when jsonb_typeof($1) <> 'array' then null
    else (
      select coalesce(jsonb_agg(source_ref.value order by source_ref.value), '[]'::jsonb)
      from (
        select distinct element.value
        from jsonb_array_elements_text($1) as element(value)
      ) source_ref
    )
  end
$$;

create or replace function content_factory_private.research_brief_has_v2_sections(
  brief_value jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select jsonb_typeof($1) = 'object'
    and jsonb_typeof($1 -> 'category_analysis') = 'object'
    and jsonb_typeof($1 -> 'competitor_analysis') = 'object'
    and jsonb_typeof($1 -> 'trend_analysis') = 'object'
    and jsonb_typeof($1 -> 'guidance') = 'object'
$$;

create or replace function content_factory_private.research_v2_sections(
  brief_value jsonb
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select jsonb_build_object(
    'category_analysis', $1 -> 'category_analysis',
    'competitor_analysis', $1 -> 'competitor_analysis',
    'trend_analysis', $1 -> 'trend_analysis',
    'guidance', $1 -> 'guidance'
  )
$$;

create or replace function content_factory_private.research_stage_source_refs(
  payload_value jsonb
)
returns text[]
language sql
immutable
set search_path = ''
as $$
  with recursive payload_nodes(node) as (
    values ($1)
    union all
    select child.node
    from payload_nodes parent
    cross join lateral (
      select object_child.value as node
      from jsonb_each(
        case when jsonb_typeof(parent.node) = 'object'
          then parent.node else '{}'::jsonb end
      ) object_child
      union all
      select array_child.value as node
      from jsonb_array_elements(
        case when jsonb_typeof(parent.node) = 'array'
          then parent.node else '[]'::jsonb end
      ) array_child
    ) child
  )
  select coalesce(
    array_agg(distinct source_ref.value order by source_ref.value),
    '{}'::text[]
  )
  from payload_nodes payload_node
  cross join lateral jsonb_array_elements_text(
    case
      when jsonb_typeof(payload_node.node) = 'object'
       and jsonb_typeof(payload_node.node -> 'source_ids') = 'array'
        then payload_node.node -> 'source_ids'
      else '[]'::jsonb
    end
  ) source_ref(value)
  where length(btrim(source_ref.value)) > 0
$$;

create or replace function content_factory_private.research_stage_payload(
  draft_row content_factory.creative_brief_drafts,
  stage_value text
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  normalized_source_ids jsonb;
  base_payload jsonb;
  correction_payload jsonb;
  decision_payload jsonb;
  base_key text;
  correction_key text;
begin
  normalized_source_ids :=
    content_factory_private.canonical_research_source_ids(draft_row.source_ids);

  correction_key := case stage_value
    when 'sources' then 'sources'
    when 'category' then 'category'
    when 'competitors' then 'competitors'
    when 'trends' then 'trends'
    when 'guidance' then 'strategy'
    else null
  end;
  if correction_key is not null
     and jsonb_typeof(draft_row.brief -> 'human_stage_corrections') = 'object' then
    correction_payload :=
      draft_row.brief -> 'human_stage_corrections' -> correction_key;
    if jsonb_typeof(correction_payload) = 'string'
       and length(btrim(coalesce(correction_payload #>> '{}', ''))) = 0 then
      correction_payload := null;
    end if;
  end if;

  if stage_value = 'sources' then
    base_payload := jsonb_build_object('source_ids', normalized_source_ids);
    if correction_payload is not null then
      return jsonb_build_object(
        'base', base_payload,
        'human_correction', correction_payload
      );
    end if;
    return base_payload;
  end if;

  if stage_value in ('category', 'competitors', 'trends', 'guidance') then
    base_key := case stage_value
      when 'category' then 'category_analysis'
      when 'competitors' then 'competitor_analysis'
      when 'trends' then 'trend_analysis'
      else 'guidance'
    end;
    base_payload := coalesce(draft_row.brief -> base_key, 'null'::jsonb);
    if stage_value = 'guidance'
       and jsonb_typeof(draft_row.brief -> 'human_research_decision') = 'object'
       and (
         draft_row.brief #>> '{human_research_decision,cold_start_override}' = 'true'
         or length(btrim(coalesce(
           draft_row.brief #>> '{human_research_decision,strategy}', ''
         ))) > 0
       ) then
      decision_payload := draft_row.brief -> 'human_research_decision';
    end if;
    if correction_payload is not null or decision_payload is not null then
      return jsonb_strip_nulls(jsonb_build_object(
        'base', base_payload,
        'human_correction', correction_payload,
        'human_research_decision', decision_payload
      ));
    end if;
    return base_payload;
  end if;

  return case stage_value
    when 'brief' then jsonb_build_object(
      'title', draft_row.title,
      'brief', draft_row.brief - array[
        'category_analysis', 'competitor_analysis', 'trend_analysis',
        'guidance', 'scenarios', 'task_blueprint',
        'human_stage_corrections', 'human_research_decision'
      ]::text[]
    )
    when 'scenarios' then jsonb_build_object(
      'scenarios', coalesce(draft_row.brief -> 'scenarios', '[]'::jsonb),
      'task_blueprint', draft_row.task_blueprint,
      'research_task_blueprint', coalesce(
        draft_row.brief -> 'task_blueprint', 'null'::jsonb
      )
    )
    else null
  end;
end;
$$;

create or replace function content_factory_private.record_research_stage_decisions(
  draft_row content_factory.creative_brief_drafts,
  decision_value text,
  actor_id_value uuid,
  origin_value text,
  decided_at_value timestamptz
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
begin
  if decision_value not in ('generated', 'patched', 'approved', 'rejected', 'reverted')
     or origin_value not in ('ai', 'human', 'system')
     or actor_id_value is null then
    raise exception using errcode = '22023', message = 'research_stage_decision_invalid';
  end if;
  if not exists (
    select 1
    from content_factory.memberships membership
    where membership.organization_id = draft_row.organization_id
      and membership.profile_id = actor_id_value
  ) then
    raise exception using errcode = '42501', message = 'research_stage_actor_not_member';
  end if;

  insert into content_factory.research_stage_decisions (
    organization_id, run_id, draft_id, stage, artifact_id,
    decision, actor_id, origin, decision_hash, created_at
  )
  select
    binding.organization_id,
    binding.run_id,
    binding.draft_id,
    binding.stage,
    binding.artifact_id,
    decision_value,
    actor_id_value,
    origin_value,
    content_factory_private.json_hash(jsonb_build_object(
      'organization_id', binding.organization_id,
      'run_id', binding.run_id,
      'draft_id', binding.draft_id,
      'stage', binding.stage,
      'artifact_id', binding.artifact_id,
      'decision', decision_value,
      'actor_id', actor_id_value,
      'origin', origin_value
    )),
    coalesce(decided_at_value, now())
  from content_factory.research_stage_draft_bindings binding
  where binding.organization_id = draft_row.organization_id
    and binding.run_id = draft_row.run_id
    and binding.draft_id = draft_row.id
    and (
      decision_value <> 'patched'
      or draft_row.previous_draft_id is null
      or not exists (
        select 1
        from content_factory.research_stage_draft_bindings previous_binding
        where previous_binding.organization_id = binding.organization_id
          and previous_binding.run_id = binding.run_id
          and previous_binding.draft_id = draft_row.previous_draft_id
          and previous_binding.stage = binding.stage
          and previous_binding.artifact_id = binding.artifact_id
      )
    )
  order by content_factory_private.research_stage_rank(binding.stage)
  on conflict (organization_id, decision_hash) do nothing;
end;
$$;

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
  all_evidence_source_ids uuid[];
  evidence_source_ids uuid[];
  stage_source_refs text[];
  evidence_count integer;
  evidence_payload jsonb;
  upstream_payload jsonb;
  artifact_id_value uuid;
  parent_artifact_id_value uuid;
  version_value integer;
begin
  perform pg_advisory_xact_lock(
    hashtext(draft_row.organization_id::text),
    hashtext('research-stage-ledger:' || draft_row.run_id::text)
  );

  select coalesce(array_agg(source_ref.source_id order by source_ref.source_id), '{}'::uuid[])
    into all_evidence_source_ids
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
    raise exception using errcode = '42501', message = 'research_stage_evidence_mismatch';
  end if;

  foreach stage_value in array array[
    'sources', 'category', 'competitors', 'trends',
    'guidance', 'brief', 'scenarios'
  ] loop
    payload_value := content_factory_private.research_stage_payload(
      draft_row, stage_value
    );
    if payload_value is null then
      raise exception using errcode = '22023', message = 'research_stage_payload_invalid';
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
        array_agg(distinct source.id order by source.id),
        '{}'::uuid[]
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
        errcode = '42501',
        message = 'research_stage_evidence_mismatch';
    end if;

    content_hash_value := content_factory_private.json_hash(payload_value);
    artifact_id_value := null;
    parent_artifact_id_value := null;

    select artifact.id into artifact_id_value
    from content_factory.research_stage_artifacts artifact
    where artifact.organization_id = draft_row.organization_id
      and artifact.run_id = draft_row.run_id
      and artifact.stage = stage_value
      and artifact.content_hash = content_hash_value;

    if artifact_id_value is null then
      if draft_row.previous_draft_id is not null then
        select binding.artifact_id into parent_artifact_id_value
        from content_factory.research_stage_draft_bindings binding
        where binding.organization_id = draft_row.organization_id
          and binding.run_id = draft_row.run_id
          and binding.draft_id = draft_row.previous_draft_id
          and binding.stage = stage_value;
      end if;
      if parent_artifact_id_value is null then
        select artifact.id into parent_artifact_id_value
        from content_factory.research_stage_artifacts artifact
        where artifact.organization_id = draft_row.organization_id
          and artifact.run_id = draft_row.run_id
          and artifact.stage = stage_value
        order by artifact.version desc
        limit 1;
      end if;
      select coalesce(max(artifact.version), 0) + 1 into version_value
      from content_factory.research_stage_artifacts artifact
      where artifact.organization_id = draft_row.organization_id
        and artifact.run_id = draft_row.run_id
        and artifact.stage = stage_value;

      insert into content_factory.research_stage_artifacts (
        organization_id, run_id, stage, version, parent_artifact_id,
        payload, content_hash, actor_id, origin, created_at
      ) values (
        draft_row.organization_id, draft_row.run_id, stage_value, version_value,
        parent_artifact_id_value, payload_value, content_hash_value,
        draft_row.created_by, draft_row.origin, draft_row.created_at
      )
      on conflict (organization_id, run_id, stage, content_hash) do nothing
      returning id into artifact_id_value;

      if artifact_id_value is null then
        select artifact.id into artifact_id_value
        from content_factory.research_stage_artifacts artifact
        where artifact.organization_id = draft_row.organization_id
          and artifact.run_id = draft_row.run_id
          and artifact.stage = stage_value
          and artifact.content_hash = content_hash_value;
      end if;
    end if;

    select coalesce(jsonb_agg(jsonb_build_object(
      'stage', binding.stage,
      'artifact_id', binding.artifact_id,
      'content_hash', artifact.content_hash
    ) order by content_factory_private.research_stage_rank(binding.stage)), '[]'::jsonb)
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

    dependency_hash_value := content_factory_private.json_hash(jsonb_build_object(
      'evidence', evidence_payload,
      'upstream_artifacts', upstream_payload
    ));

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
    select
      draft_row.organization_id,
      draft_row.run_id,
      draft_row.id,
      stage_value,
      artifact_id_value,
      source_ref.source_id,
      source_ref.ordinal::integer,
      draft_row.created_at
    from unnest(evidence_source_ids) with ordinality
      as source_ref(source_id, ordinal)
    on conflict (organization_id, draft_id, stage, source_id) do nothing;
  end loop;

  perform content_factory_private.record_research_stage_decisions(
    draft_row,
    case when draft_row.origin = 'ai' then 'generated' else 'patched' end,
    draft_row.created_by,
    draft_row.origin,
    draft_row.created_at
  );
  if draft_row.status = 'approved' then
    perform content_factory_private.record_research_stage_decisions(
      draft_row, 'approved', draft_row.approved_by, 'human', draft_row.approved_at
    );
  end if;
end;
$$;

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
begin
  if old.status = 'draft' and new.status = 'approved' then
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
          errcode = '55000',
          message = 'research_v2_human_draft_required';
      end if;

      if reference_draft_id is null then
        raise exception using
          errcode = '55000',
          message = 'research_v2_evidence_reference_missing';
      end if;
      if not content_factory_private.research_brief_has_v2_sections(new.brief)
         or content_factory_private.research_v2_sections(new.brief)
           is distinct from
         content_factory_private.research_v2_sections(reference_brief)
         or content_factory_private.canonical_research_source_ids(new.source_ids)
           is distinct from
         content_factory_private.canonical_research_source_ids(reference_source_ids) then
        raise exception using
          errcode = '55000',
          message = 'research_v2_evidence_immutable';
      end if;
    end if;

    guidance_value := new.brief -> 'guidance';
    if jsonb_typeof(guidance_value) = 'object' then
      guidance_status_value := btrim(coalesce(guidance_value ->> 'status', ''));
      if guidance_status_value <> 'ready_for_brief' then
        decision_value := new.brief -> 'human_research_decision';
        strategy_value := btrim(coalesce(decision_value ->> 'strategy', ''));
        if jsonb_typeof(decision_value) is distinct from 'object'
           or jsonb_typeof(decision_value -> 'guidance_status') is distinct from 'string'
           or btrim(coalesce(decision_value ->> 'guidance_status', ''))
             <> guidance_status_value
           or decision_value -> 'cold_start_override' is distinct from 'true'::jsonb
           or jsonb_typeof(decision_value -> 'strategy') is distinct from 'string'
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

create or replace function content_factory_private.capture_research_stage_draft_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform content_factory_private.capture_research_stage_draft(new);
  return new;
end;
$$;

create or replace function content_factory_private.capture_research_stage_approval_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if old.status is distinct from new.status and new.status = 'approved' then
    perform content_factory_private.record_research_stage_decisions(
      new, 'approved', new.approved_by, 'human', new.approved_at
    );
  end if;
  return new;
end;
$$;

drop trigger if exists guard_research_guidance_approval
  on content_factory.creative_brief_drafts;
create trigger guard_research_guidance_approval
before update of status on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.guard_research_guidance_approval();

drop trigger if exists capture_research_stage_draft
  on content_factory.creative_brief_drafts;
create trigger capture_research_stage_draft
after insert on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.capture_research_stage_draft_trigger();

drop trigger if exists capture_research_stage_approval
  on content_factory.creative_brief_drafts;
create trigger capture_research_stage_approval
after update of status on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.capture_research_stage_approval_trigger();

-- Idempotent backfill gives already-created research drafts the same ledger.
do $backfill$
declare
  draft_row content_factory.creative_brief_drafts%rowtype;
begin
  for draft_row in
    select draft.*
    from content_factory.creative_brief_drafts draft
    order by draft.organization_id, draft.run_id, draft.version, draft.id
  loop
    perform content_factory_private.capture_research_stage_draft(draft_row);
  end loop;
end;
$backfill$;

-- Preserve the original command implementation and put the v2 immutability
-- contract in a narrow wrapper. The original function remains the single
-- implementation of validation, idempotency, versioning, and forecast writes.
do $preserve_save_rpc$
begin
  if to_regprocedure(
    'public.creator_save_creative_brief_draft_pre_stage_control(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_save_creative_brief_draft(jsonb)') is null then
      raise exception using
        errcode = '42883',
        message = 'creator_save_creative_brief_draft_missing';
    end if;
    execute 'alter function public.creator_save_creative_brief_draft(jsonb) '
      || 'rename to creator_save_creative_brief_draft_pre_stage_control';
  end if;
end;
$preserve_save_rpc$;

create or replace function public.creator_save_creative_brief_draft(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  run_id_value uuid;
  brief_value jsonb;
  source_ids_value jsonb;
  reference_draft_id uuid;
  reference_brief jsonb;
  reference_source_ids jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  brief_value := p_payload -> 'brief';
  source_ids_value := p_payload -> 'source_ids';

  if jsonb_typeof(brief_value) = 'object'
     and jsonb_typeof(source_ids_value) = 'array' then
    select draft.id, draft.brief, draft.source_ids
      into reference_draft_id, reference_brief, reference_source_ids
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id
      and draft.run_id = run_id_value
      and content_factory_private.research_brief_has_v2_sections(draft.brief)
    order by case when draft.origin = 'ai' then 0 else 1 end,
      draft.version desc, draft.id
    limit 1;

    if reference_draft_id is not null then
      if content_factory_private.research_v2_sections(brief_value)
           is distinct from
         content_factory_private.research_v2_sections(reference_brief)
         or content_factory_private.canonical_research_source_ids(source_ids_value)
           is distinct from
         content_factory_private.canonical_research_source_ids(reference_source_ids) then
        raise exception using
          errcode = '55000',
          message = 'research_v2_evidence_immutable';
      end if;
      if (brief_value ? 'human_stage_corrections'
          and jsonb_typeof(brief_value -> 'human_stage_corrections') <> 'object')
         or (brief_value ? 'human_research_decision'
          and jsonb_typeof(brief_value -> 'human_research_decision') <> 'object') then
        raise exception using
          errcode = '22023',
          message = 'research_human_overlay_invalid';
      end if;
    end if;
  end if;

  return public.creator_save_creative_brief_draft_pre_stage_control(p_payload);
end;
$$;

revoke all on function
  public.creator_save_creative_brief_draft_pre_stage_control(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_save_creative_brief_draft(jsonb)
  from public, anon, authenticated;
grant execute on function public.creator_save_creative_brief_draft(jsonb)
  to authenticated;

create or replace function public.creator_research_stage_ledger(
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
  organization_id uuid;
  run_id_value uuid;
  drafts_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'research_stage_ledger_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  if not exists (
    select 1
    from content_factory.product_research_runs run
    where run.organization_id = organization_id
      and run.id = run_id_value
  ) then
    raise exception using errcode = '22023', message = 'research_run_not_found';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'draft_id', draft.id,
    'draft_version', draft.version,
    'draft_origin', draft.origin,
    'draft_status', draft.status,
    'stages', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'stage', binding.stage,
        'artifact_id', artifact.id,
        'artifact_version', artifact.version,
        'parent_artifact_id', artifact.parent_artifact_id,
        'payload', artifact.payload,
        'content_hash', artifact.content_hash,
        'dependency_hash', binding.dependency_hash,
        'artifact_actor_id', artifact.actor_id,
        'artifact_origin', artifact.origin,
        'binding_actor_id', binding.actor_id,
        'binding_origin', binding.origin,
        'artifact_created_at', artifact.created_at,
        'bound_at', binding.bound_at,
        'evidence_source_ids', (
          select coalesce(jsonb_agg(evidence.source_id order by evidence.ordinal), '[]'::jsonb)
          from content_factory.research_stage_binding_evidence evidence
          where evidence.organization_id = organization_id
            and evidence.run_id = run_id_value
            and evidence.draft_id = draft.id
            and evidence.stage = binding.stage
            and evidence.artifact_id = binding.artifact_id
        ),
        'decisions', (
          select coalesce(jsonb_agg(jsonb_build_object(
            'id', decision.id,
            'decision', decision.decision,
            'actor_id', decision.actor_id,
            'origin', decision.origin,
            'created_at', decision.created_at
          ) order by decision.created_at, decision.id), '[]'::jsonb)
          from content_factory.research_stage_decisions decision
          where decision.organization_id = organization_id
            and decision.run_id = run_id_value
            and decision.draft_id = draft.id
            and decision.stage = binding.stage
            and decision.artifact_id = binding.artifact_id
        )
      ) order by content_factory_private.research_stage_rank(binding.stage)), '[]'::jsonb)
      from content_factory.research_stage_draft_bindings binding
      join content_factory.research_stage_artifacts artifact
        on artifact.organization_id = binding.organization_id
       and artifact.run_id = binding.run_id
       and artifact.stage = binding.stage
       and artifact.id = binding.artifact_id
      where binding.organization_id = organization_id
        and binding.run_id = run_id_value
        and binding.draft_id = draft.id
    )
  ) order by draft.version, draft.id), '[]'::jsonb)
    into drafts_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id
    and draft.run_id = run_id_value;

  return jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'run_id', run_id_value,
    'drafts', drafts_value
  );
end;
$$;

revoke all on function public.creator_research_stage_ledger(jsonb)
  from public, anon, authenticated;
grant execute on function public.creator_research_stage_ledger(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.reject_research_stage_ledger_mutation()
  from public, anon, authenticated;
revoke all on function content_factory_private.research_stage_rank(text)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.canonical_research_source_ids(jsonb)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.research_brief_has_v2_sections(jsonb)
  from public, anon, authenticated;
revoke all on function content_factory_private.research_v2_sections(jsonb)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.research_stage_source_refs(jsonb)
  from public, anon, authenticated;
revoke all on function content_factory_private.research_stage_payload(
  content_factory.creative_brief_drafts, text
) from public, anon, authenticated;
revoke all on function content_factory_private.record_research_stage_decisions(
  content_factory.creative_brief_drafts, text, uuid, text, timestamptz
) from public, anon, authenticated;
revoke all on function content_factory_private.capture_research_stage_draft(
  content_factory.creative_brief_drafts
) from public, anon, authenticated;
revoke all on function
  content_factory_private.guard_research_guidance_approval()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.capture_research_stage_draft_trigger()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.capture_research_stage_approval_trigger()
  from public, anon, authenticated;

commit;

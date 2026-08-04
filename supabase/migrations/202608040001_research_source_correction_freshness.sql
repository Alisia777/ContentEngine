begin;

-- A source-analysis correction changes the evidence, not only the readiness
-- score. Bind every research draft to the exact latest human correction head
-- that existed for each source when the draft was created. Later corrections
-- can then invalidate dependent stage heads and generation specifications
-- without mutating any historical artifact.

create unique index if not exists
  research_category_source_ledger_exact_source_uq
  on content_factory.research_category_source_ledger (
    organization_id, run_id, source_id, id
  );
create unique index if not exists
  product_research_sources_exact_content_occurrence_uq
  on content_factory.product_research_sources (
    organization_id, run_id, id, content_hash
  );
create unique index if not exists
  research_category_source_ledger_exact_canonical_uq
  on content_factory.research_category_source_ledger (
    organization_id, market_category_id, source_content_hash, id
  );

create table if not exists
  content_factory.research_draft_source_analysis_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    draft_id uuid not null,
    source_id uuid not null,
    source_ledger_id uuid not null,
    market_category_id uuid not null,
    source_content_hash text not null check (
      source_content_hash ~ '^[0-9a-f]{64}$'
    ),
    binding_version integer not null check (
      binding_version between 1 and 100000
    ),
    parent_binding_id uuid,
    analysis_event_id uuid,
    analysis_event_hash text check (
      analysis_event_hash is null
      or analysis_event_hash ~ '^[0-9a-f]{64}$'
    ),
    binding_kind text not null check (binding_kind in (
      'draft_capture', 'ledger_capture', 'baseline_adoption', 'backfill'
    )),
    binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
    bound_at timestamptz not null default clock_timestamp(),
    constraint research_draft_source_analysis_bindings_org_id_uq
      unique (organization_id, id),
    constraint research_draft_source_analysis_bindings_scope_version_uq
      unique (
        organization_id, run_id, draft_id, source_id, binding_version
      ),
    constraint research_draft_source_analysis_bindings_hash_uq
      unique (organization_id, binding_hash),
    foreign key (organization_id, run_id, draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    -- A category source is canonical across research runs. Keep the local
    -- source occurrence and the canonical ledger identity as two explicit
    -- foreign keys instead of pretending that the ledger belongs to every
    -- run in which the same content was observed.
    foreign key (
      organization_id, run_id, source_id, source_content_hash
    )
      references content_factory.product_research_sources(
        organization_id, run_id, id, content_hash
      ),
    foreign key (
      organization_id, market_category_id, source_content_hash,
      source_ledger_id
    )
      references content_factory.research_category_source_ledger(
        organization_id, market_category_id, source_content_hash, id
      ),
    foreign key (organization_id, parent_binding_id)
      references content_factory.research_draft_source_analysis_bindings(
        organization_id, id
      ),
    foreign key (
      organization_id, source_ledger_id, analysis_event_id
    ) references content_factory.research_source_analysis_events(
      organization_id, source_ledger_id, id
    ),
    check (
      (binding_version = 1 and parent_binding_id is null)
      or (binding_version > 1 and parent_binding_id is not null)
    ),
    check (
      (analysis_event_id is null) = (analysis_event_hash is null)
    ),
    check (
      binding_hash = content_factory_private.json_hash(jsonb_build_object(
        'schema_version', 'research-draft-source-analysis-binding-v2',
        'organization_id', organization_id,
        'run_id', run_id,
        'draft_id', draft_id,
        'source_id', source_id,
        'source_ledger_id', source_ledger_id,
        'market_category_id', market_category_id,
        'source_content_hash', source_content_hash,
        'binding_version', binding_version,
        'parent_binding_id', parent_binding_id,
        'analysis_event_id', analysis_event_id,
        'analysis_event_hash', analysis_event_hash,
        'binding_kind', binding_kind
      ))
    )
  );

create index if not exists research_draft_source_analysis_bindings_draft_idx
  on content_factory.research_draft_source_analysis_bindings (
    organization_id, run_id, draft_id, source_id, binding_version desc
  );
create index if not exists research_draft_source_analysis_bindings_ledger_idx
  on content_factory.research_draft_source_analysis_bindings (
    organization_id, source_ledger_id, draft_id, binding_version desc
  );

alter table content_factory.research_draft_source_analysis_bindings
  enable row level security;
revoke all on content_factory.research_draft_source_analysis_bindings
  from public, anon, authenticated, service_role;

drop trigger if exists reject_research_draft_source_analysis_binding_mutation
  on content_factory.research_draft_source_analysis_bindings;
create trigger reject_research_draft_source_analysis_binding_mutation
before update or delete
on content_factory.research_draft_source_analysis_bindings
for each row execute function
  content_factory_private.reject_research_stage_ledger_mutation();

create or replace function
  content_factory_private.research_draft_market_category_id(
    organization_id_value uuid,
    run_id_value uuid,
    draft_id_value uuid
  )
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select category_binding.category_id
  from content_factory.creative_brief_drafts draft
  join content_factory.research_product_market_category_bindings
    category_binding
    on category_binding.organization_id = draft.organization_id
   and category_binding.product_id = draft.product_id
   and (
     category_binding.confirmed_at <= draft.created_at
     or (
       category_binding.source_run_id = draft.run_id
       and category_binding.source_draft_id = draft.id
     )
   )
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.id = draft_id_value
  order by
    case when category_binding.confirmed_at <= draft.created_at
      then 0 else 1 end,
    case when category_binding.confirmed_at <= draft.created_at
      then category_binding.binding_version end desc,
    case when category_binding.confirmed_at > draft.created_at
      then category_binding.binding_version end asc,
    category_binding.id
  limit 1;
$$;

create or replace function
  content_factory_private.append_research_draft_source_analysis_binding(
    organization_id_value uuid,
    run_id_value uuid,
    draft_id_value uuid,
    source_id_value uuid,
    analysis_event_id_value uuid,
    binding_kind_value text
  )
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  ledger_row content_factory.research_category_source_ledger%rowtype;
  analysis_row content_factory.research_source_analysis_events%rowtype;
  prior_binding content_factory.research_draft_source_analysis_bindings%rowtype;
  binding_id_value uuid := extensions.gen_random_uuid();
  binding_version_value integer;
  binding_hash_value text;
begin
  if binding_kind_value not in (
    'draft_capture', 'ledger_capture', 'baseline_adoption', 'backfill'
  ) then
    raise exception using
      errcode = '22023', message = 'research_source_binding_kind_invalid';
  end if;
  -- Binding versions have their own lock domain. Category resolution already
  -- owns the product-category lock when its INSERT triggers source capture;
  -- taking stage locks here would create product -> stage while correction and
  -- provider paths use stage -> generation-spec -> product. The exact
  -- draft/source lock serializes append-only versions without joining that
  -- controller cycle. Freshness guards remain fail-closed if a correction
  -- commits between the head read and a later consumer action.
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext(
      'research-draft-source-binding:' || draft_id_value::text
      || ':' || source_id_value::text
    )
  );
  select ledger.* into ledger_row
  from content_factory.creative_brief_drafts draft
  join content_factory.product_research_sources source
    on source.organization_id = draft.organization_id
   and source.run_id = draft.run_id
   and source.id = source_id_value
  join lateral (
    select content_factory_private.research_draft_market_category_id(
      draft.organization_id, draft.run_id, draft.id
    ) as category_id
  ) current_category on current_category.category_id is not null
  join content_factory.research_category_source_ledger ledger
    on ledger.organization_id = draft.organization_id
   and ledger.market_category_id = current_category.category_id
   and ledger.source_content_hash = source.content_hash
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.id = draft_id_value
    and draft.source_ids @> jsonb_build_array(source_id_value::text)
  order by ledger.registered_at desc, ledger.id desc
  limit 1;
  if ledger_row.id is null then
    return null;
  end if;
  if analysis_event_id_value is null and binding_kind_value <> 'backfill' then
    select event.* into analysis_row
    from content_factory.research_source_analysis_events event
    where event.organization_id = organization_id_value
      and event.source_ledger_id = ledger_row.id
    order by event.analysis_version desc, event.id desc
    limit 1;
  elsif analysis_event_id_value is not null then
    select event.* into analysis_row
    from content_factory.research_source_analysis_events event
    where event.organization_id = organization_id_value
      and event.source_ledger_id = ledger_row.id
      and event.id = analysis_event_id_value;
    if analysis_row.id is null then
      raise exception using
        errcode = '55000', message = 'research_source_binding_head_invalid';
    end if;
  end if;
  select binding.* into prior_binding
  from content_factory.research_draft_source_analysis_bindings binding
  where binding.organization_id = organization_id_value
    and binding.run_id = run_id_value
    and binding.draft_id = draft_id_value
    and binding.source_id = source_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if prior_binding.id is not null
     and prior_binding.source_ledger_id = ledger_row.id
     and prior_binding.analysis_event_id is not distinct from analysis_row.id
     and prior_binding.analysis_event_hash
       is not distinct from analysis_row.event_hash then
    return prior_binding.id;
  end if;
  binding_version_value := coalesce(prior_binding.binding_version, 0) + 1;
  binding_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'research-draft-source-analysis-binding-v2',
    'organization_id', organization_id_value,
    'run_id', run_id_value,
    'draft_id', draft_id_value,
    'source_id', source_id_value,
    'source_ledger_id', ledger_row.id,
    'market_category_id', ledger_row.market_category_id,
    'source_content_hash', ledger_row.source_content_hash,
    'binding_version', binding_version_value,
    'parent_binding_id', prior_binding.id,
    'analysis_event_id', analysis_row.id,
    'analysis_event_hash', analysis_row.event_hash,
    'binding_kind', binding_kind_value
  ));
  insert into content_factory.research_draft_source_analysis_bindings (
    id, organization_id, run_id, draft_id, source_id, source_ledger_id,
    market_category_id, source_content_hash,
    binding_version, parent_binding_id, analysis_event_id,
    analysis_event_hash, binding_kind, binding_hash
  ) values (
    binding_id_value, organization_id_value, run_id_value, draft_id_value,
    source_id_value, ledger_row.id, ledger_row.market_category_id,
    ledger_row.source_content_hash, binding_version_value, prior_binding.id,
    analysis_row.id, analysis_row.event_hash, binding_kind_value,
    binding_hash_value
  );
  return binding_id_value;
end;
$$;

create or replace function
  content_factory_private.capture_research_draft_source_analysis_bindings()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  source_id_value uuid;
begin
  for source_id_value in
    select distinct source_ref.value::uuid
    from jsonb_array_elements_text(new.source_ids) source_ref(value)
    order by source_ref.value::uuid
  loop
    perform content_factory_private
      .append_research_draft_source_analysis_binding(
        new.organization_id, new.run_id, new.id, source_id_value,
        null, 'draft_capture'
      );
  end loop;
  return new;
end;
$$;

create or replace function
  content_factory_private.capture_research_source_ledger_draft_bindings()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  occurrence record;
begin
  for occurrence in
    select draft.*, source.id as occurrence_source_id
    from content_factory.creative_brief_drafts draft
    join content_factory.product_research_sources source
      on source.organization_id = draft.organization_id
     and source.run_id = draft.run_id
     and draft.source_ids @> jsonb_build_array(source.id::text)
     and source.content_hash = new.source_content_hash
    join lateral (
      select content_factory_private.research_draft_market_category_id(
        draft.organization_id, draft.run_id, draft.id
      ) as category_id
    ) current_category on current_category.category_id = new.market_category_id
    where draft.organization_id = new.organization_id
    order by draft.run_id, draft.version, draft.id, source.id
  loop
    perform content_factory_private
      .append_research_draft_source_analysis_binding(
        occurrence.organization_id, occurrence.run_id,
        occurrence.id, occurrence.occurrence_source_id, null, 'ledger_capture'
      );
  end loop;
  return new;
end;
$$;

create or replace function
  content_factory_private.capture_research_category_binding_draft_bindings()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  occurrence record;
begin
  -- An ON CONFLICT category-ledger registration creates no ledger row for a
  -- source already learned in another run. Binding insertion is therefore the
  -- event that must attach those local occurrences to the canonical ledger.
  for occurrence in
    select draft.organization_id, draft.run_id, draft.id as draft_id,
      source.id as source_id
    from content_factory.creative_brief_drafts draft
    join content_factory.product_research_sources source
      on source.organization_id = draft.organization_id
     and source.run_id = draft.run_id
     and draft.source_ids @> jsonb_build_array(source.id::text)
    where draft.organization_id = new.organization_id
      and draft.product_id = new.product_id
    order by draft.run_id, draft.version, draft.id, source.id
  loop
    perform content_factory_private
      .append_research_draft_source_analysis_binding(
        occurrence.organization_id, occurrence.run_id,
        occurrence.draft_id, occurrence.source_id, null, 'ledger_capture'
      );
  end loop;
  return new;
end;
$$;

drop trigger if exists capture_research_draft_source_analysis_bindings
  on content_factory.creative_brief_drafts;
create trigger capture_research_draft_source_analysis_bindings
after insert on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.capture_research_draft_source_analysis_bindings();

drop trigger if exists capture_research_source_ledger_draft_bindings
  on content_factory.research_category_source_ledger;
create trigger capture_research_source_ledger_draft_bindings
after insert on content_factory.research_category_source_ledger
for each row execute function
  content_factory_private.capture_research_source_ledger_draft_bindings();

drop trigger if exists capture_research_category_binding_draft_bindings
  on content_factory.research_product_market_category_bindings;
create trigger capture_research_category_binding_draft_bindings
after insert on content_factory.research_product_market_category_bindings
for each row execute function
  content_factory_private.capture_research_category_binding_draft_bindings();

-- Bind historical drafts to the semantic head that actually existed when the
-- draft was created. The deterministic v1 persisted-result fallback is the
-- sole compatibility baseline allowed after draft creation. A later human or
-- parser v2 head remains different and is invalidated by the sweep below.
do $research_draft_source_analysis_binding_backfill$
declare
  draft_row content_factory.creative_brief_drafts%rowtype;
  source_id_value uuid;
  ledger_id_value uuid;
  analysis_event_id_value uuid;
begin
  for draft_row in
    select draft.*
    from content_factory.creative_brief_drafts draft
    order by draft.organization_id, draft.run_id, draft.version, draft.id
  loop
    for source_id_value in
      select distinct source_ref.value::uuid
      from jsonb_array_elements_text(draft_row.source_ids) source_ref(value)
      order by source_ref.value::uuid
    loop
      select ledger.id into ledger_id_value
      from content_factory.product_research_sources source
      join lateral (
        select content_factory_private.research_draft_market_category_id(
          draft_row.organization_id, draft_row.run_id, draft_row.id
        ) as category_id
      ) current_category on current_category.category_id is not null
      join content_factory.research_category_source_ledger ledger
        on ledger.organization_id = draft_row.organization_id
       and ledger.market_category_id = current_category.category_id
       and ledger.source_content_hash = source.content_hash
      where source.organization_id = draft_row.organization_id
        and source.run_id = draft_row.run_id
        and source.id = source_id_value
      order by ledger.registered_at desc, ledger.id desc
      limit 1;
      if ledger_id_value is null then
        continue;
      end if;
      select event.id into analysis_event_id_value
      from content_factory.research_source_analysis_events event
      where event.organization_id = draft_row.organization_id
        and event.source_ledger_id = ledger_id_value
        and (
          event.created_at <= draft_row.created_at
          or (
            event.analysis_version = 1
            and event.origin = 'system_parser'
            and event.parser_key = 'persisted_source_fallback'
            and event.parser_version = '1.0.0'
          )
        )
      order by case when event.created_at <= draft_row.created_at
        then 0 else 1 end,
        event.analysis_version desc, event.id desc
      limit 1;
      perform content_factory_private
        .append_research_draft_source_analysis_binding(
          draft_row.organization_id, draft_row.run_id,
          draft_row.id, source_id_value, analysis_event_id_value, 'backfill'
        );
    end loop;
  end loop;
end;
$research_draft_source_analysis_binding_backfill$;

create or replace function
  content_factory_private.research_draft_source_analysis_fresh(
    organization_id_value uuid,
    run_id_value uuid,
    draft_id_value uuid
  )
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  draft_row content_factory.creative_brief_drafts%rowtype;
  source_count integer;
  ledger_count integer;
  fresh_count integer;
  draft_category_id uuid;
begin
  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.id = draft_id_value;
  if draft_row.id is null then
    return false;
  end if;
  draft_category_id := content_factory_private.research_draft_market_category_id(
    organization_id_value, run_id_value, draft_id_value
  );
  select count(*)::integer,
    count(ledger.id)::integer,
    count(*) filter (
      where ledger.id is not null
        and binding.id is not null
        and binding.source_ledger_id = ledger.id
        and binding.analysis_event_id is not distinct from analysis.id
        and binding.analysis_event_hash
          is not distinct from analysis.event_hash
        and binding.binding_hash = content_factory_private.json_hash(
          jsonb_build_object(
            'schema_version', 'research-draft-source-analysis-binding-v2',
            'organization_id', binding.organization_id,
            'run_id', binding.run_id,
            'draft_id', binding.draft_id,
            'source_id', binding.source_id,
            'source_ledger_id', binding.source_ledger_id,
            'market_category_id', binding.market_category_id,
            'source_content_hash', binding.source_content_hash,
            'binding_version', binding.binding_version,
            'parent_binding_id', binding.parent_binding_id,
            'analysis_event_id', binding.analysis_event_id,
            'analysis_event_hash', binding.analysis_event_hash,
            'binding_kind', binding.binding_kind
          )
        )
    )::integer
    into source_count, ledger_count, fresh_count
  from (
    select distinct source_ref.value::uuid as source_id
    from jsonb_array_elements_text(draft_row.source_ids) source_ref(value)
  ) source_ref
  left join content_factory.product_research_sources source
    on source.organization_id = organization_id_value
   and source.run_id = run_id_value
   and source.id = source_ref.source_id
  left join lateral (
    select draft_category_id as category_id
  ) current_category on true
  left join lateral (
    select ledger.*
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = organization_id_value
      and ledger.market_category_id = current_category.category_id
      and ledger.source_content_hash = source.content_hash
    order by ledger.registered_at desc, ledger.id desc
    limit 1
  ) ledger on true
  left join lateral (
    select event.id, event.event_hash
    from content_factory.research_source_analysis_events event
    where event.organization_id = organization_id_value
      and event.source_ledger_id = ledger.id
    order by event.analysis_version desc, event.id desc
    limit 1
  ) analysis on true
  left join lateral (
    select exact_binding.*
    from content_factory.research_draft_source_analysis_bindings exact_binding
    where exact_binding.organization_id = organization_id_value
      and exact_binding.run_id = run_id_value
      and exact_binding.draft_id = draft_id_value
      and exact_binding.source_id = source_ref.source_id
    order by exact_binding.binding_version desc, exact_binding.id desc
    limit 1
  ) binding on true;
  -- A product may have been category-bound only after this immutable draft
  -- was created. Such historical drafts stay readable/compatible. Once this
  -- exact draft has a temporal category, every exact source must be mapped and
  -- fresh; partial and zero-ledger recovery drafts fail closed.
  if draft_category_id is null then
    return true;
  end if;
  return source_count = ledger_count and fresh_count = source_count;
end;
$$;

create or replace function
  content_factory_private.research_generation_spec_evidence_fresh(
    organization_id_value uuid,
    spec_id_value uuid,
    spec_version_value integer,
    spec_hash_value text
  )
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  spec_row content_factory.generation_spec_versions%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  head_count integer;
  current_count integer;
begin
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value;
  if spec_row.version_id is null then
    return false;
  end if;
  if spec_row.research_provenance is null then
    return true;
  end if;

  begin
    select draft.* into draft_row
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id_value
      and draft.run_id = (spec_row.research_provenance ->> 'research_id')::uuid
      and draft.id = (
        spec_row.research_provenance ->> 'creative_brief_draft_id'
      )::uuid
      and draft.product_id = spec_row.product_id
      and draft.status = 'approved';
  exception when invalid_text_representation then
    return false;
  end;
  if draft_row.id is null
     or not content_factory_private.research_draft_source_analysis_fresh(
       organization_id_value, draft_row.run_id, draft_row.id
     ) then
    return false;
  end if;

  select count(*)::integer,
    count(*) filter (
      where head.state = 'current'
        and head.current_draft_id = draft_row.id
    )::integer
    into head_count, current_count
  from content_factory.research_stage_branches branch
  join content_factory.research_stage_heads head
    on head.organization_id = branch.organization_id
   and head.run_id = branch.run_id
   and head.branch_id = branch.id
  where branch.organization_id = organization_id_value
    and branch.run_id = draft_row.run_id
    and branch.branch_key = 'main';
  return head_count = 7 and current_count = 7;
end;
$$;

-- Preserve the original envelope builder as a compatibility layer, then
-- replace its public private-schema name with freshness-aware guidance. The
-- immutable spec remains visible, but the UI must never recommend an approval
-- that the evidence guard below will reject.
alter function content_factory_private.generation_spec_envelope(uuid, uuid)
  rename to generation_spec_envelope_pre_source_freshness_v1;

create function content_factory_private.generation_spec_envelope(
  organization_id_value uuid,
  spec_id_value uuid
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  envelope_value jsonb;
  document_value jsonb;
begin
  envelope_value := content_factory_private
    .generation_spec_envelope_pre_source_freshness_v1(
      organization_id_value, spec_id_value
    );
  document_value := envelope_value -> 'generation_spec';
  if jsonb_typeof(document_value -> 'research_provenance') = 'object'
     and not content_factory_private
       .research_generation_spec_evidence_fresh(
         organization_id_value,
         spec_id_value,
         (document_value ->> 'spec_version')::integer,
         document_value ->> 'spec_hash'
       ) then
    envelope_value := jsonb_set(
      envelope_value,
      '{recommended_next_action}',
      jsonb_build_object(
        'code', 'start_new_research_after_source_change',
        'action', 'start_new_research',
        'label', 'Вернуться к исследованию',
        'reason',
          'Разбор источника изменён. Прежний утверждённый снимок сохранён. Начните отдельное исследование с предзаполненными данными, проверьте и утвердите новый черновик, затем подготовьте новую версию ТЗ.',
        'requires_confirmation', false,
        'provider_action', false,
        'spend_action', false
      ),
      true
    );
  end if;
  return envelope_value;
end;
$$;

create or replace function
  content_factory_private.invalidate_research_source_analysis_dependents_for_event(
    analysis_event_id_value uuid
  )
returns void
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  analysis_row content_factory.research_source_analysis_events%rowtype;
  ledger_row content_factory.research_category_source_ledger%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  branch_row content_factory.research_stage_branches%rowtype;
  head_row content_factory.research_stage_heads%rowtype;
  current_spec_head content_factory.generation_spec_head_events%rowtype;
  current_spec content_factory.generation_spec_versions%rowtype;
  active_request content_factory.research_stage_recompute_requests%rowtype;
  affected_artifact_ids uuid[];
  direct_dependency boolean;
  binding_stale boolean;
  stale_due_value jsonb;
  request_hash_value text;
  next_sequence_value integer;
  actor_id_value uuid;
  reason_value text;
begin
  select event.* into analysis_row
  from content_factory.research_source_analysis_events event
  where event.id = analysis_event_id_value;
  select ledger.* into ledger_row
  from content_factory.research_category_source_ledger ledger
  where ledger.organization_id = analysis_row.organization_id
    and ledger.id = analysis_row.source_ledger_id;
  if analysis_row.id is null or ledger_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_source_analysis_lineage_invalid';
  end if;
  actor_id_value := coalesce(analysis_row.actor_id, ledger_row.registered_by);
  reason_value := case analysis_row.origin
    when 'human_correction' then
      'A human source-analysis correction changed this evidence dependency.'
    else
      'A newer structured parser head changed this evidence dependency.'
  end;
  request_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'research-source-analysis-invalidation-v2',
    'organization_id', analysis_row.organization_id,
    'run_id', ledger_row.run_id,
    'source_id', ledger_row.source_id,
    'source_ledger_id', ledger_row.id,
    'analysis_event_id', analysis_row.id,
    'analysis_event_hash', analysis_row.event_hash
  ));

  -- Match the stage controller's global order before touching head rows. This
  -- prevents patch/revert from holding a head while waiting on the ledger lock
  -- that a simultaneous correction already owns.
  perform pg_advisory_xact_lock(
    hashtext(analysis_row.organization_id::text),
    hashtext('research-stage-control:' || ledger_row.run_id::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(analysis_row.organization_id::text),
    hashtext('brief:' || ledger_row.run_id::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(analysis_row.organization_id::text),
    hashtext('research-stage-ledger:' || ledger_row.run_id::text)
  );

  -- The deterministic persisted-result parser is the initial semantic
  -- baseline produced inside category registration. Adopt only that exact v1
  -- head append-only; every later parser or human head must invalidate.
  if analysis_row.analysis_version = 1
     and analysis_row.origin = 'system_parser'
     and analysis_row.parser_key = 'persisted_source_fallback'
     and analysis_row.parser_version = '1.0.0' then
    for draft_row in
      select draft.*
      from content_factory.creative_brief_drafts draft
      where draft.organization_id = analysis_row.organization_id
        and draft.run_id = ledger_row.run_id
        and draft.source_ids @> jsonb_build_array(ledger_row.source_id::text)
      order by draft.version, draft.id
    loop
      perform content_factory_private
        .append_research_draft_source_analysis_binding(
          draft_row.organization_id, draft_row.run_id, draft_row.id,
          ledger_row.source_id, analysis_row.id, 'baseline_adoption'
        );
    end loop;
  end if;

  -- Make queued recomputes immediately terminal in the UI. The shared locks
  -- also prevent a worker from claiming one between this decision and the
  -- append-only stale head events below. An already processing provider call
  -- is intentionally left for the installed supersession/apply guard.
  perform set_config(
    'content_factory.research_stage_control_write', 'on', true
  );
  for active_request in
    select request.*
    from content_factory.research_stage_recompute_requests request
    where request.organization_id = analysis_row.organization_id
      and request.run_id = ledger_row.run_id
      and request.status = 'queued'
    order by request.created_at, request.id
    for update
  loop
    update content_factory.product_research_runs run
    set status = 'cancelled', lease_expires_at = null,
        finished_at = clock_timestamp(), updated_at = clock_timestamp(),
        error_code = 'stage_recompute_source_analysis_superseded',
        error_message =
          'Source analysis changed before the saved provider claim.'
    where run.organization_id = active_request.organization_id
      and run.id = active_request.child_run_id
      and run.status = 'queued';
    update content_factory.research_stage_recompute_requests request
    set status = 'superseded',
        error_code = 'source_analysis_changed_before_provider_claim',
        error_message =
          'Source analysis changed; the saved recompute was not claimed.',
        lease_expires_at = null,
        finished_at = clock_timestamp()
    where request.organization_id = active_request.organization_id
      and request.id = active_request.id
      and request.status = 'queued';
  end loop;

  for branch_row in
    select branch.*
    from content_factory.research_stage_branches branch
    where branch.organization_id = analysis_row.organization_id
      and branch.run_id = ledger_row.run_id
    order by branch.created_at, branch.id
  loop
    if exists (
      select 1
      from content_factory.research_stage_head_events event
      where event.organization_id = branch_row.organization_id
        and event.run_id = branch_row.run_id
        and event.branch_id = branch_row.id
        and event.command_id = analysis_row.id
    ) then
      continue;
    end if;
    affected_artifact_ids := '{}'::uuid[];
    for head_row in
      select head.*
      from content_factory.research_stage_heads head
      where head.organization_id = branch_row.organization_id
        and head.run_id = branch_row.run_id
        and head.branch_id = branch_row.id
      order by content_factory_private.research_stage_rank(head.stage)
    loop
      select exists (
        select 1
        from content_factory.research_stage_artifacts artifact
        cross join lateral jsonb_array_elements(
          artifact.input_dependencies -> 'evidence'
        ) evidence(value)
        where artifact.organization_id = head_row.organization_id
          and artifact.run_id = head_row.run_id
          and artifact.stage = head_row.stage
          and artifact.id = head_row.artifact_id
          and evidence.value ->> 'source_id' = ledger_row.source_id::text
      ) into direct_dependency;
      binding_stale := direct_dependency and (
        head_row.current_draft_id is null
        or not exists (
          select 1
          from content_factory.research_draft_source_analysis_bindings binding
          where binding.organization_id = analysis_row.organization_id
            and binding.run_id = ledger_row.run_id
            and binding.draft_id = head_row.current_draft_id
            and binding.source_id = ledger_row.source_id
            and binding.source_ledger_id = ledger_row.id
            and binding.analysis_event_id = analysis_row.id
            and binding.analysis_event_hash = analysis_row.event_hash
            and binding.binding_version = (
              select max(latest.binding_version)
              from content_factory.research_draft_source_analysis_bindings latest
              where latest.organization_id = binding.organization_id
                and latest.run_id = binding.run_id
                and latest.draft_id = binding.draft_id
                and latest.source_id = binding.source_id
            )
        )
      );
      if binding_stale or cardinality(affected_artifact_ids) > 0 then
        if not head_row.artifact_id = any(affected_artifact_ids) then
          affected_artifact_ids :=
            array_append(affected_artifact_ids, head_row.artifact_id);
        end if;
        stale_due_value := to_jsonb(affected_artifact_ids);
        perform content_factory_private.write_research_stage_head_event(
          analysis_row.organization_id, ledger_row.run_id, branch_row.id,
          analysis_row.id, head_row.stage, 'dependency_refresh',
          'stale_dependency', head_row.artifact_id,
          head_row.dependency_hash, stale_due_value,
          head_row.current_draft_id, ledger_row.source_id,
          reason_value, actor_id_value, 'system', request_hash_value
        );
      end if;
    end loop;
  end loop;

  -- Turn every latest non-rejected generation spec that still references the
  -- corrected draft back into a draft. This is an append-only head event; the
  -- immutable specification and prior approval remain inspectable.
  for current_spec_head in
    select latest.*
    from (
      select distinct on (event.spec_id) event.*
      from content_factory.generation_spec_head_events event
      where event.organization_id = analysis_row.organization_id
      order by event.spec_id, event.event_sequence desc
    ) latest
    join content_factory.generation_spec_versions version
      on version.organization_id = latest.organization_id
     and version.spec_id = latest.spec_id
     and version.spec_version = latest.spec_version
     and version.spec_hash = latest.spec_hash
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = version.organization_id
     and draft.run_id = ledger_row.run_id
     and draft.id = (
       version.research_provenance ->> 'creative_brief_draft_id'
     )::uuid
     and draft.source_ids @> jsonb_build_array(ledger_row.source_id::text)
    where latest.state <> 'rejected'
      and version.research_provenance ->> 'research_id'
        = ledger_row.run_id::text
      and not exists (
        select 1
        from content_factory.research_draft_source_analysis_bindings binding
        where binding.organization_id = draft.organization_id
          and binding.run_id = draft.run_id
          and binding.draft_id = draft.id
          and binding.source_id = ledger_row.source_id
          and binding.source_ledger_id = ledger_row.id
          and binding.analysis_event_id = analysis_row.id
          and binding.analysis_event_hash = analysis_row.event_hash
          and binding.binding_version = (
            select max(latest_binding.binding_version)
            from content_factory.research_draft_source_analysis_bindings
              latest_binding
            where latest_binding.organization_id = binding.organization_id
              and latest_binding.run_id = binding.run_id
              and latest_binding.draft_id = binding.draft_id
              and latest_binding.source_id = binding.source_id
          )
      )
    order by latest.spec_id
  loop
    perform pg_advisory_xact_lock(
      hashtext(analysis_row.organization_id::text),
      hashtext('generation-spec:' || current_spec_head.spec_id::text)
    );
    select event.* into current_spec_head
    from content_factory.generation_spec_head_events event
    where event.organization_id = analysis_row.organization_id
      and event.spec_id = current_spec_head.spec_id
    order by event.event_sequence desc
    limit 1
    for update;
    select version.* into current_spec
    from content_factory.generation_spec_versions version
    where version.organization_id = current_spec_head.organization_id
      and version.spec_id = current_spec_head.spec_id
      and version.spec_version = current_spec_head.spec_version
      and version.spec_hash = current_spec_head.spec_hash;
    if current_spec.version_id is null
       or current_spec_head.state = 'rejected'
       or (
         current_spec_head.action = 'recompute'
         and current_spec_head.request_hash = request_hash_value
       )
       or current_spec.research_provenance ->> 'research_id'
            is distinct from ledger_row.run_id::text
       or not exists (
         select 1
         from content_factory.creative_brief_drafts draft
         where draft.organization_id = current_spec.organization_id
           and draft.run_id = ledger_row.run_id
           and draft.id = (
             current_spec.research_provenance ->> 'creative_brief_draft_id'
           )::uuid
           and draft.source_ids @> jsonb_build_array(ledger_row.source_id::text)
       ) then
      continue;
    end if;
    next_sequence_value := current_spec_head.event_sequence + 1;
    insert into content_factory.generation_spec_head_events (
      organization_id, spec_id, event_sequence, action, state,
      spec_version, spec_hash, prior_event_id, approval_event_id,
      reason, actor_id, request_hash, event_hash
    ) values (
      analysis_row.organization_id, current_spec_head.spec_id,
      next_sequence_value, 'recompute', 'draft',
      current_spec_head.spec_version, current_spec_head.spec_hash,
      current_spec_head.id, null, reason_value, actor_id_value,
      request_hash_value,
      content_factory_private.json_hash(jsonb_build_object(
        'schema_version', 'generation-spec-head-event-v1',
        'organization_id', analysis_row.organization_id,
        'spec_id', current_spec_head.spec_id,
        'event_sequence', next_sequence_value,
        'action', 'recompute',
        'state', 'draft',
        'spec_version', current_spec_head.spec_version,
        'spec_hash', current_spec_head.spec_hash,
        'prior_event_id', current_spec_head.id,
        'approval_event_id', null,
        'reason', reason_value,
        'actor_id', actor_id_value,
        'request_hash', request_hash_value
      ))
    );
  end loop;
end;
$$;

-- Replace the initial single-run invalidator with the canonical-ledger
-- implementation. A learned source is category-global, while each draft keeps
-- its own local source occurrence. One semantic event must therefore walk all
-- dependent runs in a deterministic lock order.
create or replace function
  content_factory_private.invalidate_research_source_analysis_dependents_for_event(
    analysis_event_id_value uuid
  )
returns void
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  analysis_row content_factory.research_source_analysis_events%rowtype;
  ledger_row content_factory.research_category_source_ledger%rowtype;
  occurrence record;
  affected_run record;
  branch_row content_factory.research_stage_branches%rowtype;
  head_row content_factory.research_stage_heads%rowtype;
  current_spec_head content_factory.generation_spec_head_events%rowtype;
  current_spec content_factory.generation_spec_versions%rowtype;
  active_request content_factory.research_stage_recompute_requests%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  affected_artifact_ids uuid[];
  direct_dependency boolean;
  stale_due_value jsonb;
  request_hash_value text;
  next_sequence_value integer;
  actor_id_value uuid;
  reason_value text;
begin
  select event.* into analysis_row
  from content_factory.research_source_analysis_events event
  where event.id = analysis_event_id_value;
  select ledger.* into ledger_row
  from content_factory.research_category_source_ledger ledger
  where ledger.organization_id = analysis_row.organization_id
    and ledger.id = analysis_row.source_ledger_id;
  if analysis_row.id is null or ledger_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_source_analysis_lineage_invalid';
  end if;
  actor_id_value := coalesce(analysis_row.actor_id, ledger_row.registered_by);
  reason_value := case analysis_row.origin
    when 'human_correction' then
      'A human source-analysis correction changed this evidence dependency.'
    else
      'A newer structured parser head changed this evidence dependency.'
  end;
  request_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'research-source-analysis-invalidation-v3',
    'organization_id', analysis_row.organization_id,
    'market_category_id', ledger_row.market_category_id,
    'source_ledger_id', ledger_row.id,
    'source_content_hash', ledger_row.source_content_hash,
    'analysis_event_id', analysis_row.id,
    'analysis_event_hash', analysis_row.event_hash
  ));

  -- This exact parser is the compatibility baseline created during category
  -- registration. Attach every occurrence currently classified into the same
  -- category, then stop: adoption is not a semantic change and must not cancel
  -- queued recomputes or stale stage/spec/task heads during deployment.
  if analysis_row.analysis_version = 1
     and analysis_row.origin = 'system_parser'
     and analysis_row.parser_key = 'persisted_source_fallback'
     and analysis_row.parser_version = '1.0.0' then
    for occurrence in
      select draft.organization_id, draft.run_id, draft.id as draft_id,
        source.id as source_id
      from content_factory.creative_brief_drafts draft
      join content_factory.product_research_sources source
        on source.organization_id = draft.organization_id
       and source.run_id = draft.run_id
       and draft.source_ids @> jsonb_build_array(source.id::text)
       and source.content_hash = ledger_row.source_content_hash
      join lateral (
        select content_factory_private.research_draft_market_category_id(
          draft.organization_id, draft.run_id, draft.id
        ) as category_id
      ) current_category
        on current_category.category_id = ledger_row.market_category_id
      where draft.organization_id = analysis_row.organization_id
      order by draft.run_id, draft.version, draft.id, source.id
    loop
      perform content_factory_private
        .append_research_draft_source_analysis_binding(
          occurrence.organization_id, occurrence.run_id,
          occurrence.draft_id, occurrence.source_id,
          analysis_row.id, 'baseline_adoption'
        );
    end loop;
    return;
  end if;

  for affected_run in
    with latest_bindings as (
      select distinct on (
        binding.run_id, binding.draft_id, binding.source_id
      ) binding.*
      from content_factory.research_draft_source_analysis_bindings binding
      where binding.organization_id = analysis_row.organization_id
      order by binding.run_id, binding.draft_id, binding.source_id,
        binding.binding_version desc, binding.id desc
    )
    select binding.run_id,
      (array_agg(binding.source_id order by binding.source_id))[1]
        as correction_source_id
    from latest_bindings binding
    where binding.source_ledger_id = ledger_row.id
      and (binding.analysis_event_id is distinct from analysis_row.id
       or binding.analysis_event_hash is distinct from analysis_row.event_hash
      )
    group by binding.run_id
    order by binding.run_id
  loop
    perform pg_advisory_xact_lock(
      hashtext(analysis_row.organization_id::text),
      hashtext('research-stage-control:' || affected_run.run_id::text)
    );
    perform pg_advisory_xact_lock(
      hashtext(analysis_row.organization_id::text),
      hashtext('brief:' || affected_run.run_id::text)
    );
    perform pg_advisory_xact_lock(
      hashtext(analysis_row.organization_id::text),
      hashtext('research-stage-ledger:' || affected_run.run_id::text)
    );

    -- A saved paid recompute that has not reached provider claim is made
    -- terminal immediately. A processing attempt remains governed by the
    -- installed supersession/apply guard and is never retried here.
    perform set_config(
      'content_factory.research_stage_control_write', 'on', true
    );
    for active_request in
      select request.*
      from content_factory.research_stage_recompute_requests request
      where request.organization_id = analysis_row.organization_id
        and request.run_id = affected_run.run_id
        and request.status = 'queued'
      order by request.created_at, request.id
      for update
    loop
      update content_factory.product_research_runs run
      set status = 'cancelled', lease_expires_at = null,
          finished_at = clock_timestamp(), updated_at = clock_timestamp(),
          error_code = 'stage_recompute_source_analysis_superseded',
          error_message =
            'Source analysis changed before the saved provider claim.'
      where run.organization_id = active_request.organization_id
        and run.id = active_request.child_run_id
        and run.status = 'queued';
      update content_factory.research_stage_recompute_requests request
      set status = 'superseded',
          error_code = 'source_analysis_changed_before_provider_claim',
          error_message =
            'Source analysis changed; the saved recompute was not claimed.',
          lease_expires_at = null,
          finished_at = clock_timestamp()
      where request.organization_id = active_request.organization_id
        and request.id = active_request.id
        and request.status = 'queued';
    end loop;

    for branch_row in
      select branch.*
      from content_factory.research_stage_branches branch
      where branch.organization_id = analysis_row.organization_id
        and branch.run_id = affected_run.run_id
      order by branch.created_at, branch.id
    loop
      if exists (
        select 1
        from content_factory.research_stage_head_events event
        where event.organization_id = branch_row.organization_id
          and event.run_id = branch_row.run_id
          and event.branch_id = branch_row.id
          and event.command_id = analysis_row.id
      ) then
        continue;
      end if;
      affected_artifact_ids := '{}'::uuid[];
      for head_row in
        select head.*
        from content_factory.research_stage_heads head
        where head.organization_id = branch_row.organization_id
          and head.run_id = branch_row.run_id
          and head.branch_id = branch_row.id
        order by content_factory_private.research_stage_rank(head.stage)
      loop
        select exists (
          select 1
          from content_factory.research_stage_artifacts artifact
          cross join lateral jsonb_array_elements(
            artifact.input_dependencies -> 'evidence'
          ) evidence(value)
          join lateral (
            select distinct on (binding.source_id)
              binding.source_id, binding.source_ledger_id,
              binding.analysis_event_id, binding.analysis_event_hash
            from content_factory.research_draft_source_analysis_bindings binding
            where binding.organization_id = head_row.organization_id
              and binding.run_id = head_row.run_id
              and binding.draft_id = head_row.current_draft_id
            order by binding.source_id, binding.binding_version desc,
              binding.id desc
          ) stale_occurrence
            on evidence.value ->> 'source_id'
              = stale_occurrence.source_id::text
           and stale_occurrence.source_ledger_id = ledger_row.id
           and (
             stale_occurrence.analysis_event_id is distinct from analysis_row.id
             or stale_occurrence.analysis_event_hash
               is distinct from analysis_row.event_hash
           )
          where artifact.organization_id = head_row.organization_id
            and artifact.run_id = head_row.run_id
            and artifact.stage = head_row.stage
            and artifact.id = head_row.artifact_id
        ) into direct_dependency;
        if direct_dependency or cardinality(affected_artifact_ids) > 0 then
          if not head_row.artifact_id = any(affected_artifact_ids) then
            affected_artifact_ids :=
              array_append(affected_artifact_ids, head_row.artifact_id);
          end if;
          stale_due_value := to_jsonb(affected_artifact_ids);
          perform content_factory_private.write_research_stage_head_event(
            analysis_row.organization_id, affected_run.run_id, branch_row.id,
            analysis_row.id, head_row.stage, 'dependency_refresh',
            'stale_dependency', head_row.artifact_id,
            head_row.dependency_hash, stale_due_value,
            head_row.current_draft_id, affected_run.correction_source_id,
            reason_value, actor_id_value, 'system', request_hash_value
          );
        end if;
      end loop;
    end loop;

    -- Research-created tasks are mutable lifecycle records, not the immutable
    -- approved brief. Cancel only still-actionable tasks and preserve the
    -- stale reason/event in their result history.
    for task_row in
      update content_factory.creator_tasks task
      set status = 'cancelled', completed_at = null,
          result = task.result || jsonb_build_object(
            'research_evidence_stale', jsonb_build_object(
              'source_ledger_id', ledger_row.id,
              'analysis_event_id', analysis_row.id,
              'analysis_event_hash', analysis_row.event_hash,
              'reason', reason_value
            )
          ),
          updated_at = clock_timestamp()
      where task.organization_id = analysis_row.organization_id
        and task.status in ('todo', 'in_progress', 'submitted', 'review', 'blocked')
        and exists (
          select 1
          from (
            select distinct on (binding.draft_id, binding.source_id) binding.*
            from content_factory.research_draft_source_analysis_bindings binding
            where binding.organization_id = analysis_row.organization_id
              and binding.run_id = affected_run.run_id
            order by binding.draft_id, binding.source_id,
              binding.binding_version desc, binding.id desc
          ) stale_binding
          where stale_binding.draft_id = task.creative_brief_draft_id
            and stale_binding.source_ledger_id = ledger_row.id
            and (
              stale_binding.analysis_event_id is distinct from analysis_row.id
              or stale_binding.analysis_event_hash
                is distinct from analysis_row.event_hash
            )
        )
      returning task.*
    loop
      perform content_factory_private.emit_event(
        analysis_row.organization_id, actor_id_value,
        'research_task_cancelled_source_analysis_stale',
        'creator_task', task_row.id::text,
        jsonb_build_object(
          'analysis_event_id', analysis_row.id,
          'source_ledger_id', ledger_row.id
        ),
        'research-source-stale-task:' || analysis_row.id::text
          || ':' || task_row.id::text
      );
    end loop;

    for current_spec_head in
      select latest.*
      from (
        select distinct on (event.spec_id) event.*
        from content_factory.generation_spec_head_events event
        where event.organization_id = analysis_row.organization_id
        order by event.spec_id, event.event_sequence desc
      ) latest
      join content_factory.generation_spec_versions version
        on version.organization_id = latest.organization_id
       and version.spec_id = latest.spec_id
       and version.spec_version = latest.spec_version
       and version.spec_hash = latest.spec_hash
      join content_factory.creative_brief_drafts draft
        on draft.organization_id = version.organization_id
       and draft.run_id = affected_run.run_id
       and draft.id = (
         version.research_provenance ->> 'creative_brief_draft_id'
       )::uuid
      where latest.state <> 'rejected'
        and version.research_provenance ->> 'research_id'
          = affected_run.run_id::text
        and exists (
          select 1
          from (
            select distinct on (binding.source_id) binding.*
            from content_factory.research_draft_source_analysis_bindings binding
            where binding.organization_id = draft.organization_id
              and binding.run_id = draft.run_id
              and binding.draft_id = draft.id
            order by binding.source_id, binding.binding_version desc,
              binding.id desc
          ) stale_binding
          where stale_binding.source_ledger_id = ledger_row.id
            and (stale_binding.analysis_event_id is distinct from analysis_row.id
             or stale_binding.analysis_event_hash
               is distinct from analysis_row.event_hash
            )
        )
      order by latest.spec_id
    loop
      perform pg_advisory_xact_lock(
        hashtext(analysis_row.organization_id::text),
        hashtext('generation-spec:' || current_spec_head.spec_id::text)
      );
      select event.* into current_spec_head
      from content_factory.generation_spec_head_events event
      where event.organization_id = analysis_row.organization_id
        and event.spec_id = current_spec_head.spec_id
      order by event.event_sequence desc
      limit 1
      for update;
      select version.* into current_spec
      from content_factory.generation_spec_versions version
      where version.organization_id = current_spec_head.organization_id
        and version.spec_id = current_spec_head.spec_id
        and version.spec_version = current_spec_head.spec_version
        and version.spec_hash = current_spec_head.spec_hash;
      if current_spec.version_id is null
         or current_spec_head.state = 'rejected'
         or (
           current_spec_head.action = 'recompute'
           and current_spec_head.request_hash = request_hash_value
         )
         or current_spec.research_provenance ->> 'research_id'
              is distinct from affected_run.run_id::text
         or not exists (
           select 1
           from content_factory.creative_brief_drafts draft
           where draft.organization_id = current_spec.organization_id
             and draft.run_id = affected_run.run_id
             and draft.id = (
               current_spec.research_provenance ->> 'creative_brief_draft_id'
             )::uuid
             and exists (
               select 1
               from (
                 select distinct on (binding.source_id) binding.*
                 from content_factory.research_draft_source_analysis_bindings
                   binding
                 where binding.organization_id = draft.organization_id
                   and binding.run_id = draft.run_id
                   and binding.draft_id = draft.id
                 order by binding.source_id, binding.binding_version desc,
                   binding.id desc
               ) stale_binding
               where stale_binding.source_ledger_id = ledger_row.id
                 and (stale_binding.analysis_event_id
                       is distinct from analysis_row.id
                  or stale_binding.analysis_event_hash
                       is distinct from analysis_row.event_hash
                 )
             )
         ) then
        continue;
      end if;
      next_sequence_value := current_spec_head.event_sequence + 1;
      insert into content_factory.generation_spec_head_events (
        organization_id, spec_id, event_sequence, action, state,
        spec_version, spec_hash, prior_event_id, approval_event_id,
        reason, actor_id, request_hash, event_hash
      ) values (
        analysis_row.organization_id, current_spec_head.spec_id,
        next_sequence_value, 'recompute', 'draft',
        current_spec_head.spec_version, current_spec_head.spec_hash,
        current_spec_head.id, null, reason_value, actor_id_value,
        request_hash_value,
        content_factory_private.json_hash(jsonb_build_object(
          'schema_version', 'generation-spec-head-event-v1',
          'organization_id', analysis_row.organization_id,
          'spec_id', current_spec_head.spec_id,
          'event_sequence', next_sequence_value,
          'action', 'recompute',
          'state', 'draft',
          'spec_version', current_spec_head.spec_version,
          'spec_hash', current_spec_head.spec_hash,
          'prior_event_id', current_spec_head.id,
          'approval_event_id', null,
          'reason', reason_value,
          'actor_id', actor_id_value,
          'request_hash', request_hash_value
        ))
      );
    end loop;
  end loop;
end;
$$;

create or replace function
  content_factory_private.invalidate_research_source_analysis_dependents()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  perform content_factory_private
    .invalidate_research_source_analysis_dependents_for_event(new.id);
  return new;
end;
$$;

drop trigger if exists invalidate_research_source_analysis_dependents
  on content_factory.research_source_analysis_events;
create trigger invalidate_research_source_analysis_dependents
after insert on content_factory.research_source_analysis_events
for each row execute function
  content_factory_private.invalidate_research_source_analysis_dependents();

-- Existing events never pass through the new trigger. Reconcile their exact
-- latest heads now: post-draft human corrections and parser v2 heads become
-- stale, while the v1 persisted-result compatibility baseline remains fresh.
do $research_source_analysis_freshness_backfill$
declare
  analysis_event_id_value uuid;
begin
  for analysis_event_id_value in
    select current_event.id
    from (
      select distinct on (event.organization_id, event.source_ledger_id)
        event.id, event.organization_id, event.source_ledger_id
      from content_factory.research_source_analysis_events event
      order by event.organization_id, event.source_ledger_id,
        event.analysis_version desc, event.id desc
    ) current_event
    order by current_event.organization_id,
      current_event.source_ledger_id, current_event.id
  loop
    perform content_factory_private
      .invalidate_research_source_analysis_dependents_for_event(
        analysis_event_id_value
      );
  end loop;
end;
$research_source_analysis_freshness_backfill$;

create or replace function
  content_factory_private.guard_research_draft_source_analysis_approval()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  if old.status = 'draft' and new.status = 'approved'
     and not content_factory_private.research_draft_source_analysis_fresh(
       new.organization_id, new.run_id, new.id
     ) then
    raise exception using
      errcode = '55000',
      message = 'research_draft_source_analysis_incomplete_or_stale';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_research_draft_source_analysis_approval
  on content_factory.creative_brief_drafts;
create trigger guard_research_draft_source_analysis_approval
before update of status on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.guard_research_draft_source_analysis_approval();

create or replace function
  content_factory_private.guard_generation_spec_research_evidence_approval()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  if new.action = 'approve'
     and not content_factory_private.research_generation_spec_evidence_fresh(
       new.organization_id, new.spec_id, new.spec_version, new.spec_hash
     ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_provenance_stale';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_generation_spec_research_evidence_approval
  on content_factory.generation_spec_approval_events;
create trigger guard_generation_spec_research_evidence_approval
before insert on content_factory.generation_spec_approval_events
for each row execute function
  content_factory_private.guard_generation_spec_research_evidence_approval();

create or replace function
  content_factory_private.guard_generation_job_research_evidence()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  research_run_id_value uuid;
begin
  if new.mode <> 'real' or new.provider <> 'runway'
     or not new.allow_real_spend or new.generation_spec_id is null then
    return new;
  end if;
  if tg_op = 'UPDATE'
     and not (old.status = 'queued' and new.status = 'starting') then
    return new;
  end if;
  -- Provider start and correction use the same stage->spec lock order. This
  -- closes the race where a correction is committed while a worker is doing
  -- its last pre-provider evidence check. Paid insert remains unlocked here;
  -- even if it races, the queued->starting edge serializes and fails closed.
  if tg_op = 'UPDATE' then
    begin
      select nullif(
        version.research_provenance ->> 'research_id', ''
      )::uuid into research_run_id_value
      from content_factory.generation_spec_versions version
      where version.organization_id = new.organization_id
        and version.spec_id = new.generation_spec_id
        and version.spec_version = new.generation_spec_version
        and version.spec_hash = new.generation_spec_hash;
    exception when invalid_text_representation then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_provider_start_stale';
    end;
    if research_run_id_value is not null then
      perform pg_advisory_xact_lock(
        hashtext(new.organization_id::text),
        hashtext('research-stage-ledger:' || research_run_id_value::text)
      );
    end if;
  end if;
  if not content_factory_private.research_generation_spec_evidence_fresh(
       new.organization_id, new.generation_spec_id,
       new.generation_spec_version, new.generation_spec_hash
     ) then
    raise exception using
      errcode = '55000',
      message = case when tg_op = 'UPDATE'
        then 'generation_spec_provider_start_stale'
        else 'generation_spec_research_provenance_stale'
      end;
  end if;
  return new;
end;
$$;

drop trigger if exists a_research_source_analysis_generation_guard
  on content_factory.generation_jobs;
create trigger a_research_source_analysis_generation_guard
before insert or update of status on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_generation_job_research_evidence();

revoke all on function
  content_factory_private.research_draft_market_category_id(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.append_research_draft_source_analysis_binding(
    uuid, uuid, uuid, uuid, uuid, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_draft_source_analysis_bindings()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_source_ledger_draft_bindings()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_category_binding_draft_bindings()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_draft_source_analysis_fresh(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_generation_spec_evidence_fresh(
    uuid, uuid, integer, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_spec_envelope_pre_source_freshness_v1(
    uuid, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_spec_envelope(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.invalidate_research_source_analysis_dependents_for_event(
    uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.invalidate_research_source_analysis_dependents()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_research_draft_source_analysis_approval()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_generation_spec_research_evidence_approval()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_generation_job_research_evidence()
  from public, anon, authenticated, service_role;

notify pgrst, 'reload schema';

commit;

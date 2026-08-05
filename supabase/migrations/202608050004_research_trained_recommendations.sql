begin;

-- Human-approved research becomes a recommendation source, never an opaque
-- prompt mutation. The operator chooses the useful analyses and scenario
-- candidates; generation can then propose an editable brief with exact
-- research lineage. Raw captions/transcripts and unreviewed receipts never
-- enter this bridge.

create or replace function content_factory_private.ai_research_insight_keys_valid(
  value text[]
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select value is not null
    and cardinality(value) between 0 and 4
    and array_position(value, null) is null
    and value <@ array['category', 'competitors', 'trends', 'brief']::text[]
    and cardinality(value) = (
      select count(distinct item.entry)
      from unnest(value) item(entry)
    )
$$;

create or replace function content_factory_private.ai_research_scenario_positions_valid(
  value smallint[]
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select value is not null
    and cardinality(value) between 0 and 3
    and array_position(value, null) is null
    and coalesce((select bool_and(item.entry between 1 and 3) from unnest(value) item(entry)), true)
    and cardinality(value) = (
      select count(distinct item.entry)
      from unnest(value) item(entry)
    )
$$;

create table if not exists content_factory.ai_research_learning_selections (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  receipt_id uuid not null,
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  run_id uuid not null,
  draft_id uuid not null,
  product_id uuid not null,
  product_category text not null check (product_category in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  )),
  product_name text not null check (length(btrim(product_name)) between 1 and 300),
  product_sku text not null default '' check (length(product_sku) <= 160),
  decision text not null check (decision in ('approve', 'reject')),
  selected_insight_keys text[] not null default array[]::text[] check (
    content_factory_private.ai_research_insight_keys_valid(
      selected_insight_keys
    )
  ),
  selected_scenario_positions smallint[] not null default array[]::smallint[] check (
    content_factory_private.ai_research_scenario_positions_valid(
      selected_scenario_positions
    )
  ),
  analysis_snapshot jsonb not null check (
    jsonb_typeof(analysis_snapshot) = 'object'
    and length(analysis_snapshot::text) <= 131072
    and not content_factory_private.research_analysis_has_forbidden_keys(
      analysis_snapshot
    )
  ),
  source_snapshot jsonb not null check (
    jsonb_typeof(source_snapshot) = 'array'
    and jsonb_array_length(source_snapshot) <= 100
    and length(source_snapshot::text) <= 131072
    and not content_factory_private.research_analysis_has_forbidden_keys(
      source_snapshot
    )
  ),
  recommendations jsonb not null check (
    jsonb_typeof(recommendations) = 'array'
    and jsonb_array_length(recommendations) <= 3
    and length(recommendations::text) <= 131072
    and not content_factory_private.research_analysis_has_forbidden_keys(
      recommendations
    )
  ),
  operator_notes text check (
    operator_notes is null
    or length(btrim(operator_notes)) between 3 and 1000
  ),
  selected_by uuid not null,
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  selection_hash text not null check (selection_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (length(idempotency_key) between 8 and 180),
  event_cursor bigint not null default nextval(
    'content_factory.ai_learning_event_cursor_seq'::regclass
  ) check (event_cursor > 0),
  selected_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, receipt_id),
  unique (organization_id, idempotency_key),
  unique (selection_hash),
  unique (event_cursor),
  foreign key (
    organization_id, receipt_id, product_category, receipt_hash
  ) references content_factory.ai_research_evidence_receipts(
    organization_id, id, product_category, receipt_hash
  ),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, draft_id)
    references content_factory.creative_brief_drafts(organization_id, id),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, selected_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (decision = 'approve'
      and cardinality(selected_insight_keys) between 1 and 4
      and cardinality(selected_scenario_positions) between 1 and 3
      and jsonb_array_length(recommendations)
        = cardinality(selected_scenario_positions))
    or (decision = 'reject'
      and cardinality(selected_insight_keys) = 0
      and cardinality(selected_scenario_positions) = 0
      and recommendations = '[]'::jsonb)
  )
);

create index if not exists ai_research_learning_project_category_idx
  on content_factory.ai_research_learning_selections (
    organization_id, project_id, product_category,
    selected_at desc, id desc
  ) where decision = 'approve';
create index if not exists ai_research_learning_product_idx
  on content_factory.ai_research_learning_selections (
    organization_id, project_id, product_id,
    selected_at desc, id desc
  ) where decision = 'approve';

alter table content_factory.ai_research_learning_selections
  enable row level security;
revoke all on content_factory.ai_research_learning_selections
  from public, anon, authenticated, service_role;
grant all on content_factory.ai_research_learning_selections to service_role;

drop trigger if exists ai_research_learning_selection_append_only
  on content_factory.ai_research_learning_selections;
create trigger ai_research_learning_selection_append_only
before update or delete on content_factory.ai_research_learning_selections
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

create or replace function content_factory_private.ai_research_source_snapshot(
  p_organization_id uuid,
  p_run_id uuid
)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(jsonb_agg(
    jsonb_strip_nulls(jsonb_build_object(
      'source_id', source.id,
      'source_type', source.source_type,
      'title', source.title,
      'source_url', source.source_url,
      'trust_level', source.trust_level,
      'published_at', source.published_at,
      'fetched_at', source.fetched_at,
      'analysis', analysis_event.analysis,
      'analysis_version', analysis_event.analysis_version,
      'analysis_origin', analysis_event.origin,
      'analysis_created_at', analysis_event.created_at
    )) order by source.created_at, source.id
  ), '[]'::jsonb)
  from content_factory.product_research_sources source
  left join lateral (
    select ledger.id
    from content_factory.research_category_source_ledger ledger
    where ledger.organization_id = source.organization_id
      and ledger.run_id = source.run_id
      and ledger.source_id = source.id
    order by ledger.registered_at desc, ledger.id desc
    limit 1
  ) ledger on true
  left join lateral (
    select event.analysis, event.analysis_version, event.origin, event.created_at
    from content_factory.research_source_analysis_events event
    where event.organization_id = source.organization_id
      and event.source_ledger_id = ledger.id
    order by event.analysis_version desc, event.id desc
    limit 1
  ) analysis_event on true
  where source.organization_id = p_organization_id
    and source.run_id = p_run_id
$$;

revoke all on function
  content_factory_private.ai_research_source_snapshot(uuid, uuid)
  from public, anon, authenticated, service_role;

create or replace function public.creator_ai_research_training_queue(
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
  user_id uuid;
  organization_id_value uuid;
  category_value text;
  limit_value integer := 20;
  queue_value jsonb := '[]'::jsonb;
  learned_value jsonb := '[]'::jsonb;
  actor_role_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'product_category', 'limit'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_research_training_queue_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  actor_role_value := content_factory_private.membership_role(
    organization_id_value, true, null
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]{1,2}$'
       or (p_payload ->> 'limit')::integer not between 1 and 50 then
      raise exception using
        errcode = '22023',
        message = 'ai_research_training_queue_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into queue_value
  from (
    select receipt.event_cursor, jsonb_strip_nulls(jsonb_build_object(
      'receipt_id', receipt.id,
      'receipt_hash', receipt.receipt_hash,
      'project_id', receipt.project_id,
      'project_name', project.name,
      'run_id', receipt.run_id,
      'draft_id', receipt.draft_id,
      'product_id', run.product_id,
      'product_category', receipt.product_category,
      'product_name', product.title,
      'product_sku', coalesce(run.input ->> 'sku', ''),
      'research_title', draft.title,
      'received_at', receipt.received_at,
      'source_count', receipt.source_count,
      'legacy_decision', disposition.decision,
      'review_state', case
        when disposition.decision = 'approve'
          then 'approved_waiting_for_learning_selection'
        else 'awaiting_human_review'
      end,
      'analysis', jsonb_build_object(
        'category_analysis', coalesce(
          draft.brief -> 'category_analysis', '{}'::jsonb
        ),
        'competitor_analysis', coalesce(
          draft.brief -> 'competitor_analysis', '{}'::jsonb
        ),
        'trend_analysis', coalesce(
          draft.brief -> 'trend_analysis', '{}'::jsonb
        ),
        'guidance', coalesce(draft.brief -> 'guidance', '{}'::jsonb)
      ),
      'creative_brief', jsonb_build_object(
        'audience', coalesce(draft.brief -> 'audience', '[]'::jsonb),
        'pains', coalesce(draft.brief -> 'pains', '[]'::jsonb),
        'objections', coalesce(draft.brief -> 'objections', '[]'::jsonb),
        'claims', coalesce(draft.brief -> 'claims', '[]'::jsonb),
        'facts', coalesce(draft.brief -> 'facts', '[]'::jsonb),
        'creative_potential', coalesce(
          draft.brief -> 'creative_potential', '{}'::jsonb
        )
      ),
      'scenarios', coalesce(draft.brief -> 'scenarios', '[]'::jsonb),
      'sources', content_factory_private.ai_research_source_snapshot(
        receipt.organization_id, receipt.run_id
      ),
      'deep_link', '#/workspace/research?project_id='
        || receipt.project_id::text || '&run=' || receipt.run_id::text,
      'requires_human_selection', true,
      'will_create_editable_recommendations', true
    )) as payload
    from content_factory.ai_research_evidence_receipts receipt
    join content_factory.product_research_runs run
      on run.organization_id = receipt.organization_id
     and run.id = receipt.run_id
     and run.project_id = receipt.project_id
     and run.status = 'completed'
    join content_factory.workspace_folders project
      on project.organization_id = receipt.organization_id
     and project.id = receipt.project_id
     and project.kind = 'project'
    join content_factory.products product
      on product.organization_id = run.organization_id
     and product.id = run.product_id
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = receipt.organization_id
     and draft.id = receipt.draft_id
     and draft.run_id = receipt.run_id
    left join content_factory.ai_research_evidence_dispositions disposition
      on disposition.organization_id = receipt.organization_id
     and disposition.receipt_id = receipt.id
    where receipt.organization_id = organization_id_value
      and receipt.product_category = category_value
      and receipt.status = 'awaiting_human_review'
      and coalesce(disposition.decision, 'approve') <> 'reject'
      and not exists (
        select 1
        from content_factory.ai_research_learning_selections selection
        where selection.organization_id = receipt.organization_id
          and selection.receipt_id = receipt.id
      )
    order by receipt.event_cursor desc, receipt.id desc
    limit limit_value
  ) item;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into learned_value
  from (
    select selection.event_cursor, jsonb_build_object(
      'selection_id', selection.id,
      'receipt_id', selection.receipt_id,
      'project_id', selection.project_id,
      'run_id', selection.run_id,
      'draft_id', selection.draft_id,
      'product_id', selection.product_id,
      'product_category', selection.product_category,
      'product_name', selection.product_name,
      'product_sku', selection.product_sku,
      'decision', selection.decision,
      'selected_insight_keys', to_jsonb(selection.selected_insight_keys),
      'selected_scenario_positions',
        to_jsonb(selection.selected_scenario_positions),
      'recommendations', selection.recommendations,
      'operator_notes', selection.operator_notes,
      'selected_by', selection.selected_by,
      'selected_at', selection.selected_at,
      'event_cursor', selection.event_cursor,
      'affects_recommendations', selection.decision = 'approve',
      'raw_research_enters_prompt_automatically', false
    ) as payload
    from content_factory.ai_research_learning_selections selection
    where selection.organization_id = organization_id_value
      and selection.product_category = category_value
    order by selection.event_cursor desc, selection.id desc
    limit limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    'version', 'ai-research-training-queue-v1',
    'organization_id', organization_id_value,
    'product_category', category_value,
    'queue', queue_value,
    'learned', learned_value,
    'capabilities', jsonb_build_object(
      'can_read', true,
      'can_decide', actor_role_value in ('owner', 'admin', 'producer'),
      'can_edit_recommendations',
        actor_role_value in ('owner', 'admin', 'producer')
    ),
    'contract', jsonb_build_object(
      'human_selection_required', true,
      'recommendations_are_editable', true,
      'unreviewed_research_affects_generation', false,
      'raw_research_enters_prompt_automatically', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function public.creator_ai_research_training_queue(jsonb)
  from public, anon;
grant execute on function public.creator_ai_research_training_queue(jsonb)
  to authenticated;

create or replace function public.creator_decide_ai_research_training(
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
  organization_id_value uuid;
  category_value text;
  receipt_id_value uuid;
  receipt_hash_value text;
  decision_value text;
  idempotency_key_value text;
  selected_insight_keys_value text[] := array[]::text[];
  selected_positions_value smallint[] := array[]::smallint[];
  edits_value jsonb := '[]'::jsonb;
  notes_value text;
  request_payload jsonb;
  replay_value jsonb;
  receipt_row content_factory.ai_research_evidence_receipts%rowtype;
  disposition_row content_factory.ai_research_evidence_dispositions%rowtype;
  selection_row content_factory.ai_research_learning_selections%rowtype;
  run_row content_factory.product_research_runs%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  product_name_value text;
  product_sku_value text;
  analysis_snapshot_value jsonb;
  source_snapshot_value jsonb;
  recommendations_value jsonb := '[]'::jsonb;
  scenario_value jsonb;
  edit_value jsonb;
  recommendation_value jsonb;
  position_value smallint;
  payload_key text;
  edit_item jsonb;
  edit_key text;
  existing_disposition text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  for payload_key in select jsonb_object_keys(p_payload)
  loop
    if payload_key <> all(array[
      'organization_id', 'product_category', 'receipt_id', 'receipt_hash',
      'decision', 'selected_insight_keys', 'selected_scenario_positions',
      'edits', 'operator_notes', 'confirmation', 'idempotency_key'
    ]) then
      raise exception using
        errcode = '22023',
        message = 'ai_research_training_decision_payload_invalid';
    end if;
  end loop;

  user_id := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer']
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  receipt_id_value := content_factory_private.require_uuid(
    p_payload, 'receipt_id'
  );
  receipt_hash_value := lower(content_factory_private.require_text(
    p_payload, 'receipt_hash', 64, 64
  ));
  decision_value := lower(content_factory_private.require_text(
    p_payload, 'decision', 6, 7
  ));
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if receipt_hash_value !~ '^[0-9a-f]{64}$'
     or decision_value not in ('approve', 'reject')
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_research_training_decision_invalid';
  end if;

  if p_payload ? 'selected_insight_keys' then
    if jsonb_typeof(p_payload -> 'selected_insight_keys') <> 'array' then
      raise exception using
        errcode = '22023', message = 'ai_research_training_insights_invalid';
    end if;
    select coalesce(array_agg(item.value order by item.ordinal), array[]::text[])
    into selected_insight_keys_value
    from jsonb_array_elements_text(p_payload -> 'selected_insight_keys')
      with ordinality item(value, ordinal);
  end if;
  if p_payload ? 'selected_scenario_positions' then
    if jsonb_typeof(p_payload -> 'selected_scenario_positions') <> 'array'
       or exists (
         select 1
         from jsonb_array_elements(p_payload -> 'selected_scenario_positions') item(value)
         where jsonb_typeof(item.value) <> 'number'
            or (item.value #>> '{}') !~ '^[1-3]$'
       ) then
      raise exception using
        errcode = '22023', message = 'ai_research_training_scenarios_invalid';
    end if;
    select coalesce(
      array_agg((item.value #>> '{}')::smallint order by item.ordinal),
      array[]::smallint[]
    )
    into selected_positions_value
    from jsonb_array_elements(p_payload -> 'selected_scenario_positions')
      with ordinality item(value, ordinal);
  end if;
  if p_payload ? 'edits' then
    if jsonb_typeof(p_payload -> 'edits') <> 'array'
       or jsonb_array_length(p_payload -> 'edits') > 3 then
      raise exception using
        errcode = '22023', message = 'ai_research_training_edits_invalid';
    end if;
    edits_value := p_payload -> 'edits';
  end if;
  notes_value := nullif(btrim(coalesce(p_payload ->> 'operator_notes', '')), '');
  if notes_value is not null and length(notes_value) not between 3 and 1000 then
    raise exception using
      errcode = '22023', message = 'ai_research_training_notes_invalid';
  end if;

  if decision_value = 'approve' then
    if not content_factory_private.ai_research_insight_keys_valid(
      selected_insight_keys_value
    ) or cardinality(selected_insight_keys_value) < 1
       or not content_factory_private.ai_research_scenario_positions_valid(
         selected_positions_value
       ) or cardinality(selected_positions_value) < 1 then
      raise exception using
        errcode = '22023', message = 'ai_research_training_selection_required';
    end if;
  elsif cardinality(selected_insight_keys_value) <> 0
     or cardinality(selected_positions_value) <> 0
     or edits_value <> '[]'::jsonb then
    raise exception using
      errcode = '22023', message = 'ai_research_training_reject_payload_invalid';
  end if;

  for edit_item in
    select item.value from jsonb_array_elements(edits_value) item(value)
  loop
    if jsonb_typeof(edit_item) <> 'object'
       or not (edit_item ? 'position')
       or jsonb_typeof(edit_item -> 'position') <> 'number'
       or (edit_item ->> 'position') !~ '^[1-3]$'
       or not ((edit_item ->> 'position')::smallint = any(
         selected_positions_value
       )) then
      raise exception using
        errcode = '22023', message = 'ai_research_training_edit_position_invalid';
    end if;
    for edit_key in select jsonb_object_keys(edit_item)
    loop
      if edit_key <> all(array[
        'position', 'title', 'hook', 'spoken_script', 'shot_list',
        'key_message', 'visual_direction', 'cta'
      ]) then
        raise exception using
          errcode = '22023', message = 'ai_research_training_edit_key_invalid';
      end if;
      if edit_key <> 'position' and (
        jsonb_typeof(edit_item -> edit_key) <> 'string'
        or length(btrim(edit_item ->> edit_key)) > case edit_key
          when 'title' then 240
          when 'hook' then 1000
          when 'spoken_script' then 3000
          when 'shot_list' then 5000
          when 'key_message' then 1500
          when 'visual_direction' then 2000
          when 'cta' then 1000
          else 0
        end
      ) then
        raise exception using
          errcode = '22023', message = 'ai_research_training_edit_value_invalid';
      end if;
    end loop;
  end loop;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id_value,
    'creator_decide_ai_research_training',
    idempotency_key_value,
    request_payload
  );
  if replay_value is not null then
    return replay_value;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('ai_research_training:' || receipt_id_value::text)
  );
  select receipt.* into receipt_row
  from content_factory.ai_research_evidence_receipts receipt
  where receipt.organization_id = organization_id_value
    and receipt.id = receipt_id_value
    and receipt.product_category = category_value
    and receipt.receipt_hash = receipt_hash_value
    and receipt.status = 'awaiting_human_review'
  for update;
  if receipt_row.id is null then
    raise exception using
      errcode = '40001', message = 'ai_research_training_receipt_stale';
  end if;
  if exists (
    select 1
    from content_factory.ai_research_learning_selections selection
    where selection.organization_id = organization_id_value
      and selection.receipt_id = receipt_id_value
  ) then
    raise exception using
      errcode = '40001', message = 'ai_research_training_already_decided';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.id = receipt_row.run_id
    and run.project_id = receipt_row.project_id
    and run.status = 'completed';
  if run_row.id is null then
    raise exception using
      errcode = '40001', message = 'ai_research_training_run_unavailable';
  end if;
  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.id = receipt_row.draft_id
    and draft.run_id = receipt_row.run_id;
  if draft_row.id is null
     or jsonb_typeof(draft_row.brief) <> 'object'
     or jsonb_typeof(coalesce(draft_row.brief -> 'scenarios', '[]'::jsonb))
       <> 'array' then
    raise exception using
      errcode = '40001', message = 'ai_research_training_draft_unavailable';
  end if;
  select product.title into product_name_value
  from content_factory.products product
  where product.organization_id = organization_id_value
    and product.id = run_row.product_id;
  if nullif(btrim(product_name_value), '') is null then
    raise exception using
      errcode = '40001', message = 'ai_research_training_product_unavailable';
  end if;
  product_sku_value := left(coalesce(run_row.input ->> 'sku', ''), 160);

  select disposition.decision into existing_disposition
  from content_factory.ai_research_evidence_dispositions disposition
  where disposition.organization_id = organization_id_value
    and disposition.receipt_id = receipt_row.id;
  if existing_disposition is not null
     and existing_disposition <> decision_value then
    raise exception using
      errcode = '40001', message = 'ai_research_training_legacy_decision_conflict';
  end if;
  if existing_disposition is null then
    insert into content_factory.ai_research_evidence_dispositions (
      organization_id, product_category, receipt_id, receipt_hash,
      decision, reason_code, confirmation, decided_by,
      request_hash, decision_hash, idempotency_key
    ) values (
      organization_id_value, category_value, receipt_row.id,
      receipt_row.receipt_hash, decision_value,
      case decision_value
        when 'approve' then 'operator_verified_research'
        else 'operator_rejected_research'
      end,
      true, user_id,
      content_factory_private.json_hash(request_payload),
      content_factory_private.json_hash(jsonb_build_object(
        'version', 'ai-research-evidence-disposition-v1',
        'receipt_id', receipt_row.id,
        'decision', decision_value,
        'created_by_training_bridge', true
      )),
      'training-receipt-' || substr(
        content_factory_private.json_hash(to_jsonb(idempotency_key_value)),
        1, 64
      )
    ) returning * into disposition_row;
  end if;

  analysis_snapshot_value := jsonb_build_object(
    'category_analysis', coalesce(
      draft_row.brief -> 'category_analysis', '{}'::jsonb
    ),
    'competitor_analysis', coalesce(
      draft_row.brief -> 'competitor_analysis', '{}'::jsonb
    ),
    'trend_analysis', coalesce(
      draft_row.brief -> 'trend_analysis', '{}'::jsonb
    ),
    'guidance', coalesce(draft_row.brief -> 'guidance', '{}'::jsonb),
    'creative_brief', jsonb_build_object(
      'audience', coalesce(draft_row.brief -> 'audience', '[]'::jsonb),
      'pains', coalesce(draft_row.brief -> 'pains', '[]'::jsonb),
      'objections', coalesce(
        draft_row.brief -> 'objections', '[]'::jsonb
      ),
      'claims', coalesce(draft_row.brief -> 'claims', '[]'::jsonb),
      'facts', coalesce(draft_row.brief -> 'facts', '[]'::jsonb),
      'creative_potential', coalesce(
        draft_row.brief -> 'creative_potential', '{}'::jsonb
      )
    )
  );
  source_snapshot_value := content_factory_private.ai_research_source_snapshot(
    organization_id_value, receipt_row.run_id
  );

  if decision_value = 'approve' then
    foreach position_value in array selected_positions_value
    loop
      scenario_value := draft_row.brief -> 'scenarios' -> (position_value - 1);
      if jsonb_typeof(scenario_value) <> 'object' then
        raise exception using
          errcode = '22023', message = 'ai_research_training_scenario_missing';
      end if;
      select item.value into edit_value
      from jsonb_array_elements(edits_value) item(value)
      where (item.value ->> 'position')::smallint = position_value
      limit 1;
      edit_value := coalesce(edit_value, '{}'::jsonb);

      recommendation_value := jsonb_strip_nulls(jsonb_build_object(
        'position', position_value,
        'title', coalesce(
          nullif(btrim(edit_value ->> 'title'), ''),
          nullif(btrim(scenario_value ->> 'title'), ''),
          'Рекомендация ' || position_value::text
        ),
        'platform', coalesce(
          nullif(btrim(scenario_value ->> 'platform'), ''), 'youtube'
        ),
        'recommended_generation_mode', coalesce(
          nullif(btrim(scenario_value ->> 'recommended_generation_mode'), ''),
          nullif(btrim(scenario_value ->> 'generation_mode'), '')
        ),
        'generation_mode_reason', coalesce(
          nullif(btrim(scenario_value ->> 'generation_mode_reason'), ''), ''
        ),
        'hook', coalesce(
          nullif(btrim(edit_value ->> 'hook'), ''),
          nullif(btrim(scenario_value ->> 'hook'), ''), ''
        ),
        'spoken_script', coalesce(
          nullif(btrim(edit_value ->> 'spoken_script'), ''),
          nullif(btrim(scenario_value ->> 'spoken_script'), ''),
          nullif(btrim(scenario_value ->> 'script'), ''), ''
        ),
        'shot_list', case
          when nullif(btrim(edit_value ->> 'shot_list'), '') is not null
            then to_jsonb(btrim(edit_value ->> 'shot_list'))
          else coalesce(
            scenario_value -> 'shot_list',
            scenario_value -> 'shots',
            '[]'::jsonb
          )
        end,
        'target_audience', coalesce(
          draft_row.brief -> 'audience', '[]'::jsonb
        ),
        'key_message', coalesce(
          nullif(btrim(edit_value ->> 'key_message'), ''),
          nullif(btrim(scenario_value ->> 'goal'), ''),
          nullif(btrim(scenario_value ->> 'angle'), ''), ''
        ),
        'proof_points', coalesce(
          scenario_value -> 'proof_points', '[]'::jsonb
        ),
        'avoid_claims', coalesce(
          scenario_value -> 'risks',
          draft_row.brief -> 'claims',
          '[]'::jsonb
        ),
        'visual_direction', coalesce(
          nullif(btrim(edit_value ->> 'visual_direction'), ''),
          nullif(btrim(scenario_value ->> 'angle'), ''), ''
        ),
        'cta', coalesce(
          nullif(btrim(edit_value ->> 'cta'), ''),
          nullif(btrim(scenario_value ->> 'cta'), ''), ''
        ),
        'learning_basis', jsonb_strip_nulls(jsonb_build_object(
          'selected_insight_keys', to_jsonb(selected_insight_keys_value),
          'category_analysis', case
            when 'category' = any(selected_insight_keys_value)
              then analysis_snapshot_value -> 'category_analysis'
            else null
          end,
          'competitor_analysis', case
            when 'competitors' = any(selected_insight_keys_value)
              then analysis_snapshot_value -> 'competitor_analysis'
            else null
          end,
          'trend_analysis', case
            when 'trends' = any(selected_insight_keys_value)
              then analysis_snapshot_value -> 'trend_analysis'
            else null
          end,
          'creative_brief', case
            when 'brief' = any(selected_insight_keys_value)
              then analysis_snapshot_value -> 'creative_brief'
            else null
          end
        )),
        'source_ids', draft_row.source_ids,
        'research_run_id', receipt_row.run_id,
        'research_draft_id', draft_row.id
      ));
      recommendations_value := recommendations_value
        || jsonb_build_array(recommendation_value);
    end loop;
  end if;

  insert into content_factory.ai_research_learning_selections (
    organization_id, project_id, receipt_id, receipt_hash, run_id,
    draft_id, product_id, product_category, product_name, product_sku,
    decision, selected_insight_keys, selected_scenario_positions,
    analysis_snapshot, source_snapshot, recommendations, operator_notes,
    selected_by, request_hash, selection_hash, idempotency_key
  ) values (
    organization_id_value, receipt_row.project_id, receipt_row.id,
    receipt_row.receipt_hash, receipt_row.run_id, draft_row.id,
    run_row.product_id, category_value, product_name_value,
    product_sku_value, decision_value, selected_insight_keys_value,
    selected_positions_value, analysis_snapshot_value, source_snapshot_value,
    recommendations_value, notes_value, user_id,
    content_factory_private.json_hash(request_payload),
    content_factory_private.json_hash(jsonb_build_object(
      'version', 'ai-research-learning-selection-v1',
      'organization_id', organization_id_value,
      'project_id', receipt_row.project_id,
      'receipt_id', receipt_row.id,
      'receipt_hash', receipt_row.receipt_hash,
      'decision', decision_value,
      'selected_insight_keys', to_jsonb(selected_insight_keys_value),
      'selected_scenario_positions', to_jsonb(selected_positions_value),
      'analysis_snapshot', analysis_snapshot_value,
      'source_snapshot', source_snapshot_value,
      'recommendations', recommendations_value
    )),
    idempotency_key_value
  ) returning * into selection_row;

  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'ai_research_learning_selected',
    'ai_research_learning_selection',
    selection_row.id::text,
    jsonb_build_object(
      'project_id', selection_row.project_id,
      'product_category', selection_row.product_category,
      'receipt_id', selection_row.receipt_id,
      'decision', selection_row.decision,
      'recommendation_count', jsonb_array_length(
        selection_row.recommendations
      ),
      'affects_recommendations', selection_row.decision = 'approve',
      'recommendations_are_editable', true,
      'raw_research_enters_prompt_automatically', false
    ),
    'ai-research-learning:' || idempotency_key_value
  );

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'ai-research-learning-selection-v1',
    'selection', jsonb_build_object(
      'selection_id', selection_row.id,
      'receipt_id', selection_row.receipt_id,
      'decision', selection_row.decision,
      'selected_insight_keys', to_jsonb(
        selection_row.selected_insight_keys
      ),
      'selected_scenario_positions', to_jsonb(
        selection_row.selected_scenario_positions
      ),
      'recommendations', selection_row.recommendations,
      'event_cursor', selection_row.event_cursor,
      'selected_at', selection_row.selected_at,
      'affects_recommendations', selection_row.decision = 'approve',
      'recommendations_are_editable', true,
      'raw_research_enters_prompt_automatically', false
    ),
    'snapshot', public.creator_ai_research_training_queue(
      jsonb_build_object(
        'organization_id', organization_id_value,
        'product_category', category_value
      )
    )
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_decide_ai_research_training',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_decide_ai_research_training(jsonb)
  from public, anon;
grant execute on function public.creator_decide_ai_research_training(jsonb)
  to authenticated;

create or replace function public.creator_generation_research_recommendations(
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
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
  category_value text;
  product_name_value text := '';
  sku_value text := '';
  platform_value text := '';
  limit_value integer := 3;
  recommendations_value jsonb := '[]'::jsonb;
  exact_match_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'product_category', 'product_name',
    'sku', 'platform', 'limit'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_research_recommendations_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  product_name_value := left(
    btrim(coalesce(p_payload ->> 'product_name', '')), 300
  );
  sku_value := left(btrim(coalesce(p_payload ->> 'sku', '')), 160);
  platform_value := lower(left(
    btrim(coalesce(p_payload ->> 'platform', '')), 40
  ));
  if platform_value <> '' and platform_value not in (
    'instagram', 'youtube', 'vk', 'wildberries', 'ozon',
    'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_research_recommendations_platform_invalid';
  end if;
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[1-3]$' then
      raise exception using
        errcode = '22023',
        message = 'generation_research_recommendations_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  with candidates as (
    select
      selection.id as selection_id,
      selection.receipt_id,
      selection.run_id,
      selection.draft_id,
      selection.product_id,
      selection.product_name as source_product_name,
      selection.product_sku as source_product_sku,
      selection.selected_at,
      selection.event_cursor,
      recommendation.value as recommendation,
      case
        when sku_value <> ''
         and lower(selection.product_sku) = lower(sku_value) then 3
        when product_name_value <> ''
         and lower(selection.product_name) = lower(product_name_value) then 2
        else 1
      end as match_rank
    from content_factory.ai_research_learning_selections selection
    cross join lateral jsonb_array_elements(
      selection.recommendations
    ) recommendation(value)
    where selection.organization_id = organization_id_value
      and selection.project_id = project_id_value
      and selection.product_category = category_value
      and selection.decision = 'approve'
      and (
        platform_value = ''
        or lower(coalesce(recommendation.value ->> 'platform', ''))
          = platform_value
        or lower(coalesce(
          recommendation.value ->> 'recommended_generation_mode', ''
        )) = platform_value
      )
  ), bounded as (
    select *
    from candidates
    order by match_rank desc, selected_at desc, event_cursor desc,
             selection_id desc
    limit limit_value
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'selection_id', candidate.selection_id,
    'receipt_id', candidate.receipt_id,
    'run_id', candidate.run_id,
    'draft_id', candidate.draft_id,
    'product_id', candidate.product_id,
    'source_product_name', candidate.source_product_name,
    'source_product_sku', candidate.source_product_sku,
    'scope_match', case candidate.match_rank
      when 3 then 'exact_sku'
      when 2 then 'exact_product'
      else 'category'
    end,
    'can_auto_apply', candidate.match_rank >= 2,
    'recommendation', candidate.recommendation,
    'selected_at', candidate.selected_at,
    'event_cursor', candidate.event_cursor
  ) order by candidate.match_rank desc, candidate.selected_at desc),
  '[]'::jsonb),
  count(*) filter (where candidate.match_rank >= 2)
  into recommendations_value, exact_match_count
  from bounded candidate;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-research-recommendations-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'product_category', category_value,
    'requested_product_name', product_name_value,
    'requested_sku', sku_value,
    'requested_platform', platform_value,
    'recommendations', recommendations_value,
    'auto_apply_available', exact_match_count > 0,
    'contract', jsonb_build_object(
      'recommendations_are_editable', true,
      'human_edits_are_preserved', true,
      'unreviewed_research_affects_generation', false,
      'raw_research_enters_prompt_automatically', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.creator_generation_research_recommendations(jsonb)
  from public, anon;
grant execute on function
  public.creator_generation_research_recommendations(jsonb)
  to authenticated;

comment on table content_factory.ai_research_learning_selections is
  'Append-only human selection of research analyses and scenario recommendations. Approved rows power editable recommendations; raw research never enters prompts automatically.';
comment on function public.creator_ai_research_training_queue(jsonb) is
  'Read-only rich AI-center queue: source analysis, market analysis, trends, creative brief and editable scenario candidates.';
comment on function public.creator_decide_ai_research_training(jsonb) is
  'Human approval/rejection of selected research insights and editable recommendation drafts. No provider call and no silent prompt mutation.';
comment on function public.creator_generation_research_recommendations(jsonb) is
  'Read-only project/category recommendations derived only from human-approved research selections. Exact-product matches may be auto-filled but remain editable.';

notify pgrst, 'reload schema';

commit;

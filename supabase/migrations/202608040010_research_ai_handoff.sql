begin;

-- A paid research run must carry one explicit AI category before any provider
-- transport can start.  The binding is immutable and belongs to the exact
-- project/run pair; no title, SKU or free-form category text is interpreted.
create table if not exists content_factory.research_ai_category_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  run_id uuid not null,
  product_category text not null check (product_category in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  )),
  bound_by uuid not null,
  binding_kind text not null default 'explicit_paid_start'
    check (binding_kind = 'explicit_paid_start'),
  binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
  bound_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, run_id),
  unique (
    organization_id, project_id, run_id, id, product_category, binding_hash
  ),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (organization_id, bound_by)
    references content_factory.memberships(organization_id, profile_id)
);

-- Completion contributes only a reviewable inbox receipt.  It never writes a
-- teaching-card decision or an effective generation policy.
create table if not exists content_factory.ai_research_evidence_receipts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  run_id uuid not null,
  category_binding_id uuid not null,
  product_category text not null check (product_category in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  )),
  draft_id uuid,
  created_by uuid not null,
  status text not null default 'awaiting_human_review'
    check (status = 'awaiting_human_review'),
  category_binding_hash text not null
    check (category_binding_hash ~ '^[0-9a-f]{64}$'),
  completion_hash text not null check (completion_hash ~ '^[0-9a-f]{64}$'),
  draft_content_hash text check (
    draft_content_hash is null or draft_content_hash ~ '^[0-9a-f]{64}$'
  ),
  source_count integer not null check (source_count between 0 and 1000),
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  event_cursor bigint not null default nextval(
    'content_factory.ai_learning_event_cursor_seq'::regclass
  ) check (event_cursor > 0),
  received_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, run_id),
  unique (organization_id, id, product_category, receipt_hash),
  unique (receipt_hash),
  unique (event_cursor),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, run_id)
    references content_factory.product_research_runs(organization_id, id),
  foreign key (
    organization_id, project_id, run_id, category_binding_id,
    product_category, category_binding_hash
  ) references content_factory.research_ai_category_bindings(
    organization_id, project_id, run_id, id, product_category, binding_hash
  ),
  foreign key (organization_id, draft_id)
    references content_factory.creative_brief_drafts(organization_id, id),
  foreign key (organization_id, created_by)
    references content_factory.memberships(organization_id, profile_id)
);

-- Human review closes the inbox with one immutable disposition.  Approval is
-- an evidence-review outcome only: it does not create a teaching decision,
-- write an effective policy or copy raw research into a generation prompt.
create table if not exists content_factory.ai_research_evidence_dispositions (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  product_category text not null check (product_category in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  )),
  receipt_id uuid not null,
  receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
  decision text not null check (decision in ('approve', 'reject')),
  reason_code text not null check (reason_code in (
    'operator_verified_research', 'operator_rejected_research'
  )),
  confirmation boolean not null check (confirmation),
  decided_by uuid not null,
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null
    check (length(idempotency_key) between 8 and 180),
  event_cursor bigint not null default nextval(
    'content_factory.ai_learning_event_cursor_seq'::regclass
  ) check (event_cursor > 0),
  decided_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, receipt_id),
  unique (organization_id, idempotency_key),
  unique (event_cursor),
  foreign key (
    organization_id, receipt_id, product_category, receipt_hash
  ) references content_factory.ai_research_evidence_receipts(
    organization_id, id, product_category, receipt_hash
  ),
  foreign key (organization_id, decided_by)
    references content_factory.memberships(organization_id, profile_id)
);

create index if not exists research_ai_category_project_idx
  on content_factory.research_ai_category_bindings (
    organization_id, project_id, bound_at desc, id desc
  );
create index if not exists ai_research_inbox_category_idx
  on content_factory.ai_research_evidence_receipts (
    organization_id, product_category, event_cursor desc, id desc
  );
create index if not exists ai_research_disposition_history_idx
  on content_factory.ai_research_evidence_dispositions (
    organization_id, product_category, event_cursor desc, id desc
  );

alter table content_factory.research_ai_category_bindings enable row level security;
alter table content_factory.ai_research_evidence_receipts enable row level security;
alter table content_factory.ai_research_evidence_dispositions enable row level security;

revoke all on content_factory.research_ai_category_bindings
  from public, anon, authenticated, service_role;
revoke all on content_factory.ai_research_evidence_receipts
  from public, anon, authenticated, service_role;
revoke all on content_factory.ai_research_evidence_dispositions
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.reject_research_ai_handoff_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_immutable';
end;
$$;

drop trigger if exists research_ai_category_binding_immutable
  on content_factory.research_ai_category_bindings;
create trigger research_ai_category_binding_immutable
before update or delete on content_factory.research_ai_category_bindings
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

drop trigger if exists ai_research_evidence_receipt_append_only
  on content_factory.ai_research_evidence_receipts;
create trigger ai_research_evidence_receipt_append_only
before update or delete on content_factory.ai_research_evidence_receipts
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

drop trigger if exists ai_research_evidence_disposition_append_only
  on content_factory.ai_research_evidence_dispositions;
create trigger ai_research_evidence_disposition_append_only
before update or delete on content_factory.ai_research_evidence_dispositions
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

-- Preserve the project-scoped start exactly, then require and record the fixed
-- category in the same transaction.  The delegated payload intentionally
-- removes product_category because the mature research RPC predates it.
do $preserve_project_research_start_for_ai_handoff$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_project_research_pre_ai_handoff_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_start_project_research(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_start_project_research_missing';
    end if;
    execute 'alter function public.creator_start_project_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.creator_start_project_research(jsonb) '
      || 'rename to creator_start_project_research_pre_ai_handoff_v1';
  end if;
end;
$preserve_project_research_start_for_ai_handoff$;

revoke all on function
  content_factory_private.creator_start_project_research_pre_ai_handoff_v1(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_start_project_research(
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
  category_value text;
  delegated_payload jsonb;
  result_value jsonb;
  run_id_value uuid;
  project_id_value uuid;
  organization_id_value uuid;
  bound_by_value uuid;
  binding_hash_value text;
  binding_row content_factory.research_ai_category_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'product_category')
     or jsonb_typeof(p_payload -> 'product_category') <> 'string'
     or nullif(btrim(p_payload ->> 'product_category'), '') is null then
    raise exception using
      errcode = '22023', message = 'product_research_ai_category_required';
  end if;
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  delegated_payload := p_payload - 'product_category';
  result_value := content_factory_private
    .creator_start_project_research_pre_ai_handoff_v1(delegated_payload);

  begin
    run_id_value := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'research_ai_binding_result_invalid';
  end;
  if run_id_value is null then
    raise exception using
      errcode = '55000', message = 'research_ai_binding_result_invalid';
  end if;

  select run.organization_id, run.created_by
  into organization_id_value, bound_by_value
  from content_factory.product_research_runs run
  where run.id = run_id_value
    and run.project_id = project_id_value;
  if organization_id_value is null or bound_by_value is null then
    raise exception using
      errcode = '42501', message = 'project_entity_mismatch';
  end if;
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  perform content_factory_private.require_project_entity(
    organization_id_value, project_id_value, 'research_run', run_id_value
  );

  binding_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'research-ai-category-binding-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'run_id', run_id_value,
    'product_category', category_value,
    'bound_by', bound_by_value,
    'binding_kind', 'explicit_paid_start'
  ));
  insert into content_factory.research_ai_category_bindings (
    organization_id, project_id, run_id, product_category, bound_by,
    binding_kind, binding_hash
  ) values (
    organization_id_value, project_id_value, run_id_value, category_value,
    bound_by_value, 'explicit_paid_start', binding_hash_value
  ) on conflict (organization_id, run_id) do nothing
  returning * into binding_row;

  if binding_row.id is null then
    select binding.* into binding_row
    from content_factory.research_ai_category_bindings binding
    where binding.organization_id = organization_id_value
      and binding.run_id = run_id_value;
  end if;
  if binding_row.id is null
     or binding_row.project_id <> project_id_value
     or binding_row.product_category <> category_value
     or binding_row.bound_by <> bound_by_value
     or binding_row.binding_hash <> binding_hash_value then
    raise exception using
      errcode = '23505', message = 'research_ai_category_binding_conflict';
  end if;

  return jsonb_set(
    result_value || jsonb_build_object(
      'product_category', category_value,
      'ai_category_binding', jsonb_build_object(
        'id', binding_row.id,
        'product_category', binding_row.product_category,
        'binding_kind', binding_row.binding_kind,
        'binding_hash', binding_row.binding_hash,
        'bound_at', binding_row.bound_at
      )
    ),
    '{run,product_category}',
    to_jsonb(category_value),
    true
  );
end;
$$;

revoke all on function public.creator_start_project_research(jsonb)
  from public, anon;
grant execute on function public.creator_start_project_research(jsonb)
  to authenticated;

-- Preserve all existing completion validation/category registration and append
-- one idempotent AI inbox receipt only after an authoritative completed result.
do $preserve_research_completion_for_ai_handoff$
begin
  if to_regprocedure(
    'content_factory_private.complete_product_research_pre_ai_handoff_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.system_complete_product_research(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'system_complete_product_research_missing';
    end if;
    execute 'alter function public.system_complete_product_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.system_complete_product_research(jsonb) '
      || 'rename to complete_product_research_pre_ai_handoff_v1';
  end if;
end;
$preserve_research_completion_for_ai_handoff$;

revoke all on function
  content_factory_private.complete_product_research_pre_ai_handoff_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.system_complete_product_research(
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
  completion_value jsonb;
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  binding_row content_factory.research_ai_category_bindings%rowtype;
  draft_id_value uuid;
  draft_hash_value text;
  source_count_value integer := 0;
  receipt_hash_value text;
  receipt_row content_factory.ai_research_evidence_receipts%rowtype;
begin
  completion_value := content_factory_private
    .complete_product_research_pre_ai_handoff_v1(p_payload);
  if completion_value ->> 'status' <> 'completed'
     or btrim(coalesce(p_payload ->> 'status', '')) <> 'completed' then
    return completion_value;
  end if;

  begin
    run_id_value := (completion_value ->> 'run_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'research_completion_response_invalid';
  end;
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
    and run.status = 'completed';
  if run_row.id is null then
    raise exception using
      errcode = '55000', message = 'completed_research_run_required';
  end if;

  select binding.* into binding_row
  from content_factory.research_ai_category_bindings binding
  where binding.organization_id = run_row.organization_id
    and binding.run_id = run_row.id;
  -- Runs already in flight before this migration have no trustworthy fixed
  -- category.  Completion stays available, but no category is guessed.
  if binding_row.id is null or run_row.project_id is null then
    return completion_value || jsonb_build_object(
      'ai_handoff', jsonb_build_object(
        'status', 'unmapped_legacy_run',
        'requires_explicit_category', true,
        'raw_research_enters_prompt_automatically', false
      )
    );
  end if;
  if binding_row.project_id <> run_row.project_id then
    raise exception using
      errcode = '55000', message = 'research_ai_category_binding_mismatch';
  end if;

  begin
    draft_id_value := nullif(completion_value ->> 'draft_id', '')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'research_completion_response_invalid';
  end;
  if draft_id_value is not null then
    select draft.content_hash into draft_hash_value
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = run_row.organization_id
      and draft.run_id = run_row.id
      and draft.id = draft_id_value;
    if draft_hash_value is null then
      raise exception using
        errcode = '55000', message = 'research_completion_draft_mismatch';
    end if;
  end if;
  select count(*)::integer into source_count_value
  from content_factory.product_research_sources source
  where source.organization_id = run_row.organization_id
    and source.run_id = run_row.id;

  receipt_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'ai-research-evidence-receipt-v1',
    'organization_id', run_row.organization_id,
    'project_id', run_row.project_id,
    'run_id', run_row.id,
    'category_binding_id', binding_row.id,
    'product_category', binding_row.product_category,
    'category_binding_hash', binding_row.binding_hash,
    'draft_id', draft_id_value,
    'draft_content_hash', draft_hash_value,
    'completion_hash', run_row.completion_hash,
    'source_count', source_count_value,
    'status', 'awaiting_human_review'
  ));
  insert into content_factory.ai_research_evidence_receipts (
    organization_id, project_id, run_id, category_binding_id,
    product_category, draft_id, created_by, status, category_binding_hash,
    completion_hash, draft_content_hash, source_count, receipt_hash
  ) values (
    run_row.organization_id, run_row.project_id, run_row.id, binding_row.id,
    binding_row.product_category, draft_id_value, run_row.created_by,
    'awaiting_human_review', binding_row.binding_hash,
    run_row.completion_hash, draft_hash_value, source_count_value,
    receipt_hash_value
  ) on conflict (organization_id, run_id) do nothing
  returning * into receipt_row;

  if receipt_row.id is null then
    select receipt.* into receipt_row
    from content_factory.ai_research_evidence_receipts receipt
    where receipt.organization_id = run_row.organization_id
      and receipt.run_id = run_row.id;
  end if;
  if receipt_row.id is null
     or receipt_row.project_id <> run_row.project_id
     or receipt_row.category_binding_id <> binding_row.id
     or receipt_row.product_category <> binding_row.product_category
     or receipt_row.category_binding_hash <> binding_row.binding_hash
     or receipt_row.completion_hash <> run_row.completion_hash
     or receipt_row.receipt_hash <> receipt_hash_value then
    raise exception using
      errcode = '23505', message = 'ai_research_evidence_receipt_conflict';
  end if;

  return completion_value || jsonb_build_object(
    'ai_handoff', jsonb_build_object(
      'receipt_id', receipt_row.id,
      'status', receipt_row.status,
      'product_category', receipt_row.product_category,
      'received_at', receipt_row.received_at,
      'deep_link', '#/workspace/research?project_id='
        || receipt_row.project_id::text || '&run=' || receipt_row.run_id::text,
      'raw_research_enters_prompt_automatically', false,
      'affects_effective_policy', false
    )
  );
end;
$$;

revoke all on function public.system_complete_product_research(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_complete_product_research(jsonb)
  to service_role;

-- Extend the public control room after every existing private snapshot layer.
-- Only the selected organization/category appears in the returned inbox.
do $preserve_ai_control_room_for_research_inbox$
begin
  if to_regprocedure(
    'content_factory_private.creator_ai_learning_control_room_pre_research_inbox_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_ai_learning_control_room(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_ai_learning_control_room_missing';
    end if;
    execute 'alter function public.creator_ai_learning_control_room(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.creator_ai_learning_control_room(jsonb) '
      || 'rename to creator_ai_learning_control_room_pre_research_inbox_v1';
  end if;
end;
$preserve_ai_control_room_for_research_inbox$;

revoke all on function
  content_factory_private.creator_ai_learning_control_room_pre_research_inbox_v1(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_ai_learning_control_room(
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
  base_value jsonb;
  organization_id_value uuid;
  category_value text;
  inbox_value jsonb := '[]'::jsonb;
  inbox_cursor_value bigint := 0;
  decision_history_value jsonb := '[]'::jsonb;
  decision_cursor_value bigint := 0;
  state_cursor_value bigint := 0;
  actor_role_value text;
  can_decide_research_value boolean := false;
begin
  base_value := content_factory_private
    .creator_ai_learning_control_room_pre_research_inbox_v1(p_payload);
  begin
    organization_id_value := (base_value ->> 'organization_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'ai_learning_control_room_response_invalid';
  end;
  category_value := content_factory_private.require_ai_product_category(
    base_value ->> 'selected_category'
  );
  actor_role_value := lower(coalesce(base_value #>> '{actor,role}', ''));
  can_decide_research_value := actor_role_value in (
    'owner', 'admin', 'producer'
  );

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb),
         coalesce(max(item.event_cursor), 0)
  into inbox_value, inbox_cursor_value
  from (
    select receipt.event_cursor, jsonb_strip_nulls(jsonb_build_object(
      'receipt_id', receipt.id,
      'project_id', receipt.project_id,
      'project_name', project.name,
      'run_id', receipt.run_id,
      'product_category', receipt.product_category,
      'product_name', product.title,
      'research_title', draft.title,
      'draft_id', receipt.draft_id,
      'status', receipt.status,
      'receipt_hash', receipt.receipt_hash,
      'source_count', receipt.source_count,
      'received_at', receipt.received_at,
      'event_cursor', receipt.event_cursor,
      'deep_link', '#/workspace/research?project_id='
        || receipt.project_id::text || '&run=' || receipt.run_id::text,
      'requires_human_review', true,
      'raw_research_enters_prompt_automatically', false,
      'affects_effective_policy', false
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
    left join content_factory.creative_brief_drafts draft
      on draft.organization_id = receipt.organization_id
     and draft.id = receipt.draft_id
     and draft.run_id = receipt.run_id
    where receipt.organization_id = organization_id_value
      and receipt.product_category = category_value
      and receipt.status = 'awaiting_human_review'
      and not exists (
        select 1
        from content_factory.ai_research_evidence_dispositions disposition
        where disposition.organization_id = receipt.organization_id
          and disposition.receipt_id = receipt.id
      )
    order by receipt.event_cursor desc, receipt.id desc
    limit 50
  ) item;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb),
         coalesce(max(item.event_cursor), 0)
  into decision_history_value, decision_cursor_value
  from (
    select disposition.event_cursor,
      jsonb_strip_nulls(jsonb_build_object(
        'disposition_id', disposition.id,
        'receipt_id', receipt.id,
        'receipt_hash', receipt.receipt_hash,
        'project_id', receipt.project_id,
        'project_name', project.name,
        'run_id', receipt.run_id,
        'product_category', receipt.product_category,
        'product_name', product.title,
        'research_title', draft.title,
        'decision', disposition.decision,
        'reason_code', disposition.reason_code,
        'decided_by', disposition.decided_by,
        'decided_by_name', coalesce(profile.display_name, profile.email),
        'decided_at', disposition.decided_at,
        'event_cursor', disposition.event_cursor,
        'deep_link', '#/workspace/research?project_id='
          || receipt.project_id::text || '&run=' || receipt.run_id::text,
        'human_review_completed', true,
        'raw_research_enters_prompt_automatically', false,
        'affects_effective_policy', false
      )) as payload
    from content_factory.ai_research_evidence_dispositions disposition
    join content_factory.ai_research_evidence_receipts receipt
      on receipt.organization_id = disposition.organization_id
     and receipt.id = disposition.receipt_id
     and receipt.product_category = disposition.product_category
     and receipt.receipt_hash = disposition.receipt_hash
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
    left join content_factory.creative_brief_drafts draft
      on draft.organization_id = receipt.organization_id
     and draft.id = receipt.draft_id
     and draft.run_id = receipt.run_id
    left join content_factory.profiles profile
      on profile.id = disposition.decided_by
    where disposition.organization_id = organization_id_value
      and disposition.product_category = category_value
    order by disposition.event_cursor desc, disposition.id desc
    limit 50
  ) item;

  state_cursor_value := greatest(
    coalesce((base_value ->> 'state_version')::bigint, 0),
    coalesce((base_value ->> 'event_cursor')::bigint, 0),
    inbox_cursor_value,
    decision_cursor_value
  );
  return base_value || jsonb_build_object(
    'state_version', state_cursor_value,
    'event_cursor', state_cursor_value,
    'research_inbox', inbox_value,
    'research_decisions', decision_history_value,
    'category_detail',
      coalesce(base_value -> 'category_detail', '{}'::jsonb)
      || jsonb_build_object(
        'research_inbox', inbox_value,
        'research_decisions', decision_history_value,
        'research_inbox_count', jsonb_array_length(inbox_value),
        'research_decision_count', jsonb_array_length(decision_history_value),
        'research_inbox_requires_human_review', true,
        'pending_research_inbox_affects_generation', false
      ),
    'capabilities', coalesce(base_value -> 'capabilities', '{}'::jsonb)
      || jsonb_build_object(
        'can_read_research_inbox', true,
        'can_decide_research_inbox', can_decide_research_value
      ),
    'guidance', coalesce(base_value -> 'guidance', '{}'::jsonb)
      || jsonb_build_object(
        'raw_research_enters_prompt_automatically', false,
        'pending_research_inbox_affects_generation', false,
        'research_decisions_affect_effective_policy', false,
        'research_inbox_next_action', case
          when jsonb_array_length(inbox_value) > 0
            then 'review_research_evidence'
          else null
        end
      )
  );
end;
$$;

revoke all on function public.creator_ai_learning_control_room(jsonb)
  from public, anon;
grant execute on function public.creator_ai_learning_control_room(jsonb)
  to authenticated;

-- Close one inbox item with one confirmed, idempotent human disposition.
-- This function deliberately does not touch teaching cards or category policy.
create or replace function public.creator_decide_ai_research_receipt(
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
  reason_code_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay_value jsonb;
  receipt_row content_factory.ai_research_evidence_receipts%rowtype;
  disposition_row content_factory.ai_research_evidence_dispositions%rowtype;
  snapshot_value jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'product_category', 'receipt_id', 'receipt_hash',
      'decision', 'confirmation', 'idempotency_key'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_research_receipt_decision_payload_invalid';
  end if;

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
  if receipt_hash_value !~ '^[0-9a-f]{64}$'
     or decision_value not in ('approve', 'reject')
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_research_receipt_decision_invalid';
  end if;
  reason_code_value := case decision_value
    when 'approve' then 'operator_verified_research'
    else 'operator_rejected_research'
  end;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id_value,
    'creator_decide_ai_research_receipt',
    idempotency_key_value,
    request_payload
  );
  if replay_value is not null then
    return replay_value;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('ai_research_receipt:' || receipt_id_value::text)
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
      errcode = '40001',
      message = 'ai_research_receipt_stale';
  end if;
  if exists (
    select 1
    from content_factory.ai_research_evidence_dispositions disposition
    where disposition.organization_id = organization_id_value
      and disposition.receipt_id = receipt_id_value
  ) then
    raise exception using
      errcode = '40001',
      message = 'ai_research_receipt_already_decided';
  end if;

  insert into content_factory.ai_research_evidence_dispositions (
    organization_id, product_category, receipt_id, receipt_hash,
    decision, reason_code, confirmation, decided_by,
    request_hash, decision_hash, idempotency_key
  ) values (
    organization_id_value, category_value, receipt_row.id,
    receipt_row.receipt_hash, decision_value, reason_code_value, true, user_id,
    content_factory_private.json_hash(request_payload),
    content_factory_private.json_hash(jsonb_build_object(
      'version', 'ai-research-evidence-disposition-v1',
      'organization_id', organization_id_value,
      'product_category', category_value,
      'receipt_id', receipt_row.id,
      'receipt_hash', receipt_row.receipt_hash,
      'decision', decision_value,
      'reason_code', reason_code_value,
      'affects_effective_policy', false,
      'raw_research_enters_prompt_automatically', false
    )),
    idempotency_key_value
  ) returning * into disposition_row;

  perform content_factory_private.emit_event(
    organization_id_value,
    user_id,
    'ai_research_evidence_decided',
    'ai_research_evidence_disposition',
    disposition_row.id::text,
    jsonb_build_object(
      'product_category', category_value,
      'receipt_id', receipt_row.id,
      'decision', decision_value,
      'event_cursor', disposition_row.event_cursor,
      'affects_effective_policy', false,
      'raw_research_enters_prompt_automatically', false
    ),
    'ai-research-review:' || idempotency_key_value
  );

  snapshot_value := public.creator_ai_learning_control_room(
    jsonb_build_object(
      'organization_id', organization_id_value,
      'product_category', category_value
    )
  );
  result_value := jsonb_build_object(
    'ok', true,
    'version', 'ai-research-evidence-disposition-v1',
    'decision', jsonb_build_object(
      'disposition_id', disposition_row.id,
      'receipt_id', disposition_row.receipt_id,
      'product_category', disposition_row.product_category,
      'decision', disposition_row.decision,
      'reason_code', disposition_row.reason_code,
      'event_cursor', disposition_row.event_cursor,
      'decided_at', disposition_row.decided_at,
      'affects_effective_policy', false,
      'raw_research_enters_prompt_automatically', false
    ),
    'snapshot', snapshot_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_decide_ai_research_receipt',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_decide_ai_research_receipt(jsonb)
  from public, anon;
grant execute on function public.creator_decide_ai_research_receipt(jsonb)
  to authenticated;

-- The original function was STABLE but called current_profile_id(), whose
-- profile UPSERT cannot run in PostgREST's read-only transaction.  Keep the
-- RPC genuinely read-only and authenticate with auth.uid(), like the AI room.
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
  user_id uuid;
  organization_id uuid;
  run_id_value uuid;
  providers_value jsonb;
  run_control_value jsonb;
  response_state_value jsonb := jsonb_build_object(
    'binding_state', 'not_bound',
    'provider_status', null,
    'accepted_at', null,
    'last_checked_at', null,
    'provider_response_suffix', null
  );
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_provider_status_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );

  if nullif(btrim(coalesce(p_payload ->> 'run_id', '')), '') is not null then
    run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
    if not exists (
      select 1
      from content_factory.product_research_runs run
      where run.organization_id = organization_id
        and run.id = run_id_value
    ) then
      raise exception using
        errcode = '22023', message = 'research_run_not_found';
    end if;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'provider_key', catalog.provider_key,
    'display_name', catalog.display_name,
    'adapter_version', catalog.adapter_version,
    'lifecycle_status', catalog.lifecycle_status,
    'rollout_stage', catalog.rollout_stage,
    'billing_mode', catalog.billing_mode,
    'health_mode', catalog.health_mode,
    'canary_mode', catalog.canary_mode,
    'automatic_canary_allowed', catalog.automatic_canary_allowed,
    'automatic_fallback_allowed', catalog.automatic_fallback_allowed,
    'commercial_use_allowed', catalog.commercial_use_allowed,
    'arbitrary_public_accounts_allowed',
      catalog.arbitrary_public_accounts_allowed,
    'subject_authorization_required',
      catalog.subject_authorization_required,
    'capabilities', catalog.capabilities,
    'platforms', catalog.platforms,
    'health', jsonb_strip_nulls(jsonb_build_object(
      'status', case
        when latest.id is null then 'unknown'
        when latest.expires_at <= now() then 'stale'
        else latest.status
      end,
      'fresh', coalesce(latest.expires_at > now(), false),
      'failure_code', latest.failure_code,
      'citation_count', latest.citation_count,
      'checked_at', latest.checked_at,
      'expires_at', latest.expires_at,
      'receipt_id', latest.id
    ))
  ) order by catalog.provider_key), '[]'::jsonb)
  into providers_value
  from content_factory.research_provider_catalog catalog
  left join lateral (
    select receipt.*
    from content_factory.research_provider_health_receipts receipt
    where receipt.organization_id = organization_id
      and receipt.provider_key = catalog.provider_key
      and receipt.adapter_version = catalog.adapter_version
    order by receipt.checked_at desc, receipt.id desc
    limit 1
  ) latest on true;

  if run_id_value is not null then
    select jsonb_build_object(
      'run_id', run.id,
      'run_status', run.status,
      'authorized', authorization_entry.id is not null,
      'authorization', case when authorization_entry.id is null then null else
        jsonb_build_object(
          'id', authorization_entry.id,
          'kind', authorization_entry.authorization_kind,
          'paid_analysis_ack', authorization_entry.paid_analysis_ack,
          'provider_key', authorization_entry.provider_key,
          'adapter_version', authorization_entry.adapter_version,
          'max_provider_attempts', authorization_entry.max_provider_attempts,
          'automatic_fallback_allowed',
            authorization_entry.automatic_fallback_allowed,
          'reason_code', authorization_entry.reason_code,
          'authorized_at', authorization_entry.authorized_at
        ) end,
      'attempt', case when binding.id is null then null else
        jsonb_build_object(
          'attempt_id', binding.id,
          'provider_key', binding.provider_key,
          'adapter_version', binding.adapter_version,
          'model', binding.model,
          'attempt_number', binding.attempt_number,
          'bound_at', binding.bound_at
        ) end
    ) into run_control_value
    from content_factory.product_research_runs run
    left join content_factory.research_execution_authorizations
      authorization_entry
      on authorization_entry.organization_id = run.organization_id
     and authorization_entry.run_id = run.id
    left join content_factory.research_run_provider_bindings binding
      on binding.organization_id = run.organization_id
     and binding.run_id = run.id
    where run.organization_id = organization_id
      and run.id = run_id_value;

    -- Migration 011 creates the background-response ledger after this
    -- migration. Dynamic SQL keeps 010 installable on a fresh database while
    -- exposing the ledger as soon as it exists. Only a short identifier
    -- suffix is returned; prompt, body, token and full response id stay hidden.
    if to_regclass(
      'content_factory.research_provider_response_bindings'
    ) is not null and to_regclass(
      'content_factory.research_provider_response_receipts'
    ) is not null then
      execute $response_state_query$
        select jsonb_build_object(
          'binding_state', 'bound',
          'provider_status', coalesce(
            latest.provider_status, response.initial_status
          ),
          'accepted_at', response.accepted_at,
          'last_checked_at', latest.checked_at,
          'provider_response_suffix', right(
            response.provider_response_id,
            least(8, length(response.provider_response_id))
          )
        )
        from content_factory.research_provider_response_bindings response
        left join lateral (
          select receipt.provider_status, receipt.checked_at
          from content_factory.research_provider_response_receipts receipt
          where receipt.organization_id = response.organization_id
            and receipt.response_binding_id = response.id
          order by receipt.checked_at desc, receipt.id desc
          limit 1
        ) latest on true
        where response.organization_id = $1
          and response.run_id = $2
      $response_state_query$
      into response_state_value
      using organization_id, run_id_value;
      response_state_value := coalesce(
        response_state_value,
        jsonb_build_object(
          'binding_state', 'not_bound',
          'provider_status', null,
          'accepted_at', null,
          'last_checked_at', null,
          'provider_response_suffix', null
        )
      );
    end if;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-provider-control-plane-v1',
    'organization_id', organization_id,
    'providers', providers_value,
    'run_control', run_control_value,
    'response_state', response_state_value,
    'controls', jsonb_build_object(
      'explicit_paid_analysis_required', true,
      'creates_research_runs', false,
      'automatic_canary', false,
      'automatic_fallback', false,
      'external_call_performed', false
    )
  );
end;
$$;

revoke all on function public.creator_research_provider_status(jsonb)
  from public, anon;
grant execute on function public.creator_research_provider_status(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.reject_research_ai_handoff_mutation()
  from public, anon, authenticated, service_role;

notify pgrst, 'reload schema';

commit;

begin;

-- One human-approved AI Center variant can be opened in Create without first
-- reproducing its category/product fields in the browser.  The selection and
-- recommendation position are server-resolved inside the exact project.  A
-- small project-shared working draft then keeps only editable creative fields;
-- campaign, destination, media, quantity, authorization and spend confirmation
-- never enter this contract.

create or replace function
  content_factory_private.ai_research_working_draft_fields_valid(
    p_value jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select jsonb_typeof(p_value) = 'object'
    and p_value ?& array[
      'product_category', 'platform', 'generation_mode',
      'duration_seconds', 'format', 'brief'
    ]::text[]
    and p_value - array[
      'product_category', 'platform', 'generation_mode',
      'duration_seconds', 'format', 'brief'
    ]::text[] = '{}'::jsonb
    and jsonb_typeof(p_value -> 'product_category') = 'string'
    and (p_value ->> 'product_category') in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )
    and jsonb_typeof(p_value -> 'platform') = 'string'
    and (p_value ->> 'platform') in (
      '', 'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
      'wildberries'
    )
    and jsonb_typeof(p_value -> 'generation_mode') = 'string'
    and (p_value ->> 'generation_mode') in (
      'mock', 'real_photo', 'real_gen4', 'real_seedance'
    )
    and case p_value ->> 'generation_mode'
      when 'real_gen4' then case
        when jsonb_typeof(p_value -> 'duration_seconds') = 'number'
         and coalesce(p_value ->> 'duration_seconds', '') ~ '^[0-9]{1,2}$'
          then (p_value ->> 'duration_seconds')::integer in (2, 5, 8, 10)
        else false
      end
      when 'real_seedance' then case
        when jsonb_typeof(p_value -> 'duration_seconds') = 'number'
         and coalesce(p_value ->> 'duration_seconds', '') ~ '^[0-9]{1,2}$'
          then (p_value ->> 'duration_seconds')::integer in (4, 8, 12, 15)
        else false
      end
      when 'mock' then p_value -> 'duration_seconds' = 'null'::jsonb
      when 'real_photo' then p_value -> 'duration_seconds' = 'null'::jsonb
      else false
    end
    and jsonb_typeof(p_value -> 'format') = 'string'
    and (p_value ->> 'format') in ('9:16', '1:1', '16:9')
    and jsonb_typeof(p_value -> 'brief') = 'string'
    and length(p_value ->> 'brief') <= 1200
$$;

revoke all on function
  content_factory_private.ai_research_working_draft_fields_valid(jsonb)
  from public, anon, authenticated;

create or replace function
  content_factory_private.ai_research_working_draft_field_names_valid(
    p_value text[]
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select p_value is not null
    and cardinality(p_value) between 0 and 6
    and array_position(p_value, null) is null
    and p_value <@ array[
      'product_category', 'platform', 'mode',
      'duration_seconds', 'format', 'brief'
    ]::text[]
    and cardinality(p_value) = (
      select count(distinct entry)
      from unnest(p_value) item(entry)
    )
$$;

revoke all on function
  content_factory_private.ai_research_working_draft_field_names_valid(text[])
  from public, anon, authenticated;

create or replace function
  content_factory_private.ai_research_working_draft_value_map_valid(
    p_value jsonb
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  item record;
begin
  if jsonb_typeof(p_value) is distinct from 'object'
     or p_value - array[
       'product_category', 'platform', 'mode',
       'duration_seconds', 'format', 'brief'
     ]::text[] <> '{}'::jsonb
     or length(p_value::text) > 8192 then
    return false;
  end if;
  for item in select key, value from jsonb_each(p_value)
  loop
    if jsonb_typeof(item.value) <> 'string'
       or length(item.value #>> '{}') > 1200 then
      return false;
    end if;
  end loop;
  return true;
end;
$$;

revoke all on function
  content_factory_private.ai_research_working_draft_value_map_valid(jsonb)
  from public, anon, authenticated;

create or replace function
  content_factory_private.ai_research_recommendation_snapshot(
    p_organization_id uuid,
    p_project_id uuid,
    p_selection_id uuid,
    p_recommendation_position smallint
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  selection_row content_factory.ai_research_learning_selections%rowtype;
  recommendation_value jsonb;
begin
  select selection.* into selection_row
  from content_factory.ai_research_learning_selections selection
  where selection.organization_id = p_organization_id
    and selection.project_id = p_project_id
    and selection.id = p_selection_id
    and selection.decision = 'approve'
    and p_recommendation_position = any(
      selection.selected_scenario_positions
    );
  if selection_row.id is null then
    return null;
  end if;

  select candidate.value into recommendation_value
  from jsonb_array_elements(selection_row.recommendations)
    with ordinality candidate(value, ordinality)
  where case
    when coalesce(candidate.value ->> 'position', '') ~ '^[1-3]$'
      then (candidate.value ->> 'position')::smallint
    else candidate.ordinality::smallint
  end = p_recommendation_position
  limit 1;
  if jsonb_typeof(recommendation_value) is distinct from 'object' then
    return null;
  end if;

  return jsonb_build_object(
    'selection_id', selection_row.id,
    'selection_hash', selection_row.selection_hash,
    'receipt_id', selection_row.receipt_id,
    'run_id', selection_row.run_id,
    'draft_id', selection_row.draft_id,
    'project_id', selection_row.project_id,
    'product_id', selection_row.product_id,
    'product_category', selection_row.product_category,
    'source_product_name', selection_row.product_name,
    'source_product_sku', selection_row.product_sku,
    'recommendation_position', p_recommendation_position,
    'recommendation_hash',
      content_factory_private.json_hash(recommendation_value),
    'scope_match', 'selected_product_advisory',
    'match_basis', 'server_verified_selection',
    'can_auto_apply', false,
    'preset', content_factory_private.ai_research_generation_preset(
      selection_row.product_category,
      recommendation_value
    ),
    'recommendation', recommendation_value,
    'selected_at', selection_row.selected_at,
    'event_cursor', selection_row.event_cursor
  );
end;
$$;

revoke all on function
  content_factory_private.ai_research_recommendation_snapshot(
    uuid, uuid, uuid, smallint
  ) from public, anon, authenticated;

create or replace function
  public.contentengine_generation_research_recommendation(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
  selection_id_value uuid;
  position_value smallint;
  recommendation_value jsonb;
  recommendation_variants_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'selection_id',
    'recommendation_position'
  ]::text[] <> '{}'::jsonb
     or not (p_payload ?& array[
       'project_id', 'selection_id', 'recommendation_position'
     ]::text[]) then
    raise exception using
      errcode = '22023',
      message = 'generation_research_recommendation_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    user_id
  );
  selection_id_value := content_factory_private.require_uuid(
    p_payload, 'selection_id'
  );
  if jsonb_typeof(p_payload -> 'recommendation_position') <> 'number'
     or coalesce(p_payload ->> 'recommendation_position', '')
       !~ '^[1-3]$' then
    raise exception using
      errcode = '22023',
      message = 'generation_research_recommendation_position_invalid';
  end if;
  position_value :=
    (p_payload ->> 'recommendation_position')::smallint;
  recommendation_value :=
    content_factory_private.ai_research_recommendation_snapshot(
      organization_id_value,
      project_id_value,
      selection_id_value,
      position_value
    );
  if recommendation_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_research_recommendation_scope_mismatch';
  end if;

  -- The requested position is the authority for application, but the UI must
  -- keep every approved sibling visible so only the human decides which one to
  -- use next. Each sibling is rebuilt through the same server-side verifier.
  select coalesce(jsonb_agg(candidate.snapshot order by candidate.position), '[]'::jsonb)
    into recommendation_variants_value
  from (
    select position.value as position,
      content_factory_private.ai_research_recommendation_snapshot(
        organization_id_value,
        project_id_value,
        selection_id_value,
        position.value
      ) as snapshot
    from unnest(array[1, 2, 3]::smallint[]) position(value)
  ) candidate
  where candidate.snapshot is not null;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-research-recommendation-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'authoritative_context', jsonb_build_object(
      'selection_id', selection_id_value,
      'recommendation_position', position_value,
      'product_id', recommendation_value -> 'product_id',
      'product_category', recommendation_value -> 'product_category',
      'product_name', recommendation_value -> 'source_product_name',
      'product_sku', recommendation_value -> 'source_product_sku'
    ),
    'recommendations', recommendation_variants_value,
    'auto_apply_available', false,
    'contract', jsonb_build_object(
      'selection_is_server_verified', true,
      'category_is_server_derived', true,
      'product_identity_is_server_derived', true,
      'url_category_is_not_authority', true,
      'explicit_deep_link_selection_required', true,
      'all_approved_variants_returned', true,
      'selection_does_not_prove_current_media_identity', true,
      'presets_are_advisory', true,
      'recommendations_are_editable', true,
      'spend_confirmation_is_never_applied', true,
      'campaign_is_never_applied', true,
      'media_is_never_applied', true,
      'destination_is_never_applied', true,
      'count_is_never_applied', true,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_generation_research_recommendation(jsonb)
  from public, anon;
grant execute on function
  public.contentengine_generation_research_recommendation(jsonb)
  to authenticated, service_role;

create table if not exists
  content_factory.generation_ai_research_working_drafts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    status text not null default 'active'
      check (status in ('active', 'cleared')),
    revision bigint not null default 1 check (revision > 0),
    selection_id uuid,
    recommendation_position smallint
      check (recommendation_position between 1 and 3),
    editable_fields jsonb not null default '{}'::jsonb,
    applied_fields text[] not null default array[]::text[],
    touched_fields text[] not null default array[]::text[],
    previous_values jsonb not null default '{}'::jsonb,
    last_applied_values jsonb not null default '{}'::jsonb,
    auto_apply_disabled boolean not null default false,
    created_by uuid not null,
    updated_by uuid not null,
    last_mutation_id uuid not null,
    created_at timestamptz not null default clock_timestamp(),
    updated_at timestamptz not null default clock_timestamp(),
    unique (organization_id, project_id),
    unique (organization_id, id),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, selection_id)
      references content_factory.ai_research_learning_selections(
        organization_id, id
      ),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, updated_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (status = 'active'
        and selection_id is not null
        and recommendation_position is not null
        and content_factory_private
          .ai_research_working_draft_fields_valid(editable_fields)
        and content_factory_private
          .ai_research_working_draft_field_names_valid(applied_fields)
        and cardinality(applied_fields) between 1 and 6
        and content_factory_private
          .ai_research_working_draft_field_names_valid(touched_fields)
        and content_factory_private
          .ai_research_working_draft_value_map_valid(previous_values)
        and content_factory_private
          .ai_research_working_draft_value_map_valid(last_applied_values))
      or (status = 'cleared'
        and selection_id is null
        and recommendation_position is null
        and editable_fields = '{}'::jsonb
        and applied_fields = array[]::text[]
        and touched_fields = array[]::text[]
        and previous_values = '{}'::jsonb
        and last_applied_values = '{}'::jsonb
        and auto_apply_disabled is false)
    )
  );

create index if not exists generation_ai_research_working_updated_idx
  on content_factory.generation_ai_research_working_drafts (
    organization_id, project_id, updated_at desc
  );

alter table content_factory.generation_ai_research_working_drafts
  enable row level security;
revoke all on content_factory.generation_ai_research_working_drafts
  from public, anon, authenticated;
grant all on content_factory.generation_ai_research_working_drafts
  to service_role;

create or replace function
  content_factory_private.generation_ai_research_working_draft_snapshot(
    p_organization_id uuid,
    p_project_id uuid
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  draft_row
    content_factory.generation_ai_research_working_drafts%rowtype;
  recommendation_value jsonb;
begin
  select draft.* into draft_row
  from content_factory.generation_ai_research_working_drafts draft
  where draft.organization_id = p_organization_id
    and draft.project_id = p_project_id;

  if draft_row.id is null then
    return jsonb_build_object(
      'ok', true,
      'version', 'generation-ai-research-working-draft-v1',
      'organization_id', p_organization_id,
      'project_id', p_project_id,
      'revision', 0,
      'draft', null,
      'contract', jsonb_build_object(
        'server_backed', true,
        'project_shared', true,
        'one_active_draft_per_project', true,
        'optimistic_concurrency', true,
        'financial_fields_stored', false,
        'spend_confirmation_stored', false,
        'authorization_stored', false,
        'media_or_blobs_stored', false,
        'external_call_started', false,
        'paid_call_started', false
      )
    );
  end if;

  if draft_row.status = 'cleared' then
    return jsonb_build_object(
      'ok', true,
      'version', 'generation-ai-research-working-draft-v1',
      'organization_id', p_organization_id,
      'project_id', p_project_id,
      'revision', draft_row.revision,
      'draft', null,
      'cleared_at', draft_row.updated_at,
      'updated_by', draft_row.updated_by,
      'contract', jsonb_build_object(
        'server_backed', true,
        'project_shared', true,
        'one_active_draft_per_project', true,
        'optimistic_concurrency', true,
        'financial_fields_stored', false,
        'spend_confirmation_stored', false,
        'authorization_stored', false,
        'media_or_blobs_stored', false,
        'external_call_started', false,
        'paid_call_started', false
      )
    );
  end if;

  recommendation_value :=
    content_factory_private.ai_research_recommendation_snapshot(
      p_organization_id,
      p_project_id,
      draft_row.selection_id,
      draft_row.recommendation_position
    );
  if recommendation_value is null then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_working_draft_selection_stale';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-ai-research-working-draft-v1',
    'organization_id', p_organization_id,
    'project_id', p_project_id,
    'revision', draft_row.revision,
    'draft', jsonb_build_object(
      'id', draft_row.id,
      'revision', draft_row.revision,
      'selection_id', draft_row.selection_id,
      'recommendation_position', draft_row.recommendation_position,
      'editable_fields', draft_row.editable_fields,
      'applied_fields', to_jsonb(draft_row.applied_fields),
      'touched_fields', to_jsonb(draft_row.touched_fields),
      'previous_values', draft_row.previous_values,
      'last_applied_values', draft_row.last_applied_values,
      'auto_apply_disabled', draft_row.auto_apply_disabled,
      'created_by', draft_row.created_by,
      'updated_by', draft_row.updated_by,
      'created_at', draft_row.created_at,
      'updated_at', draft_row.updated_at,
      'recommendation', recommendation_value
    ),
    'contract', jsonb_build_object(
      'server_backed', true,
      'project_shared', true,
      'one_active_draft_per_project', true,
      'optimistic_concurrency', true,
      'selected_variant_is_durable', true,
      'human_edits_are_durable', true,
      'financial_fields_stored', false,
      'authorization_stored', false,
      'media_or_blobs_stored', false,
      'spend_confirmation_stored', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  content_factory_private.generation_ai_research_working_draft_snapshot(
    uuid, uuid
  ) from public, anon, authenticated;

create or replace function
  public.contentengine_generation_ai_research_working_draft(
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
  project_id_value uuid;
  action_value text;
  expected_revision_value bigint;
  mutation_id_value uuid;
  selection_id_value uuid;
  position_value smallint;
  editable_fields_value jsonb;
  applied_fields_value text[];
  touched_fields_value text[];
  previous_values_value jsonb;
  last_applied_values_value jsonb;
  auto_apply_disabled_value boolean;
  recommendation_value jsonb;
  current_row
    content_factory.generation_ai_research_working_drafts%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_payload_invalid';
  end if;
  action_value := lower(btrim(coalesce(p_payload ->> 'action', 'read')));
  if action_value not in ('read', 'save', 'clear') then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_action_invalid';
  end if;
  if action_value = 'read' and p_payload - array[
    'organization_id', 'project_id', 'action'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_payload_invalid';
  elsif action_value = 'save' and (
    p_payload - array[
      'organization_id', 'project_id', 'action', 'expected_revision',
      'mutation_id', 'selection_id', 'recommendation_position',
      'editable_fields', 'applied_fields', 'touched_fields',
      'previous_values', 'last_applied_values', 'auto_apply_disabled'
    ]::text[] <> '{}'::jsonb
    or not (p_payload ?& array[
      'expected_revision', 'mutation_id', 'selection_id',
      'recommendation_position', 'editable_fields', 'applied_fields',
      'touched_fields', 'previous_values', 'last_applied_values',
      'auto_apply_disabled'
    ]::text[])
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_payload_invalid';
  elsif action_value = 'clear' and (
    p_payload - array[
      'organization_id', 'project_id', 'action', 'expected_revision',
      'mutation_id'
    ]::text[] <> '{}'::jsonb
    or not (p_payload ?& array[
      'expected_revision', 'mutation_id'
    ]::text[])
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_payload_invalid';
  end if;

  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    user_id
  );

  if action_value = 'read' then
    return content_factory_private
      .generation_ai_research_working_draft_snapshot(
        organization_id_value,
        project_id_value
      );
  end if;

  if jsonb_typeof(p_payload -> 'expected_revision') <> 'number'
     or coalesce(p_payload ->> 'expected_revision', '')
       !~ '^[0-9]{1,19}$'
     or (p_payload ->> 'expected_revision')::numeric > 9223372036854775806
  then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_revision_invalid';
  end if;
  expected_revision_value :=
    (p_payload ->> 'expected_revision')::bigint;
  mutation_id_value := content_factory_private.require_uuid(
    p_payload, 'mutation_id'
  );

  -- Lock the project row so two first-writers cannot both observe revision 0.
  perform 1
  from content_factory.workspace_folders project
  where project.organization_id = organization_id_value
    and project.id = project_id_value
    and project.kind = 'project'
  for update;

  select draft.* into current_row
  from content_factory.generation_ai_research_working_drafts draft
  where draft.organization_id = organization_id_value
    and draft.project_id = project_id_value
  for update;

  if current_row.id is not null
     and current_row.last_mutation_id = mutation_id_value then
    return content_factory_private
      .generation_ai_research_working_draft_snapshot(
        organization_id_value,
        project_id_value
      );
  end if;
  if coalesce(current_row.revision, 0) <> expected_revision_value then
    raise exception using
      -- 40001 is reserved for serialization failures and is retried by the
      -- PostgREST transaction runner. A stale optimistic-concurrency token is
      -- a terminal HTTP conflict, so it must never enter that retry loop.
      errcode = 'PT409',
      message = 'generation_ai_research_working_draft_revision_conflict',
      detail = jsonb_build_object(
        'expected_revision', expected_revision_value,
        'current_revision', coalesce(current_row.revision, 0)
      )::text;
  end if;

  if action_value = 'clear' then
    if current_row.id is null then
      return content_factory_private
        .generation_ai_research_working_draft_snapshot(
          organization_id_value,
          project_id_value
        );
    end if;
    update content_factory.generation_ai_research_working_drafts draft
    set status = 'cleared',
        revision = draft.revision + 1,
        selection_id = null,
        recommendation_position = null,
        editable_fields = '{}'::jsonb,
        applied_fields = array[]::text[],
        touched_fields = array[]::text[],
        previous_values = '{}'::jsonb,
        last_applied_values = '{}'::jsonb,
        auto_apply_disabled = false,
        updated_by = user_id,
        last_mutation_id = mutation_id_value,
        updated_at = clock_timestamp()
    where draft.organization_id = organization_id_value
      and draft.project_id = project_id_value;
    return content_factory_private
      .generation_ai_research_working_draft_snapshot(
        organization_id_value,
        project_id_value
      );
  end if;

  selection_id_value := content_factory_private.require_uuid(
    p_payload, 'selection_id'
  );
  if jsonb_typeof(p_payload -> 'recommendation_position') <> 'number'
     or coalesce(p_payload ->> 'recommendation_position', '')
       !~ '^[1-3]$' then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_position_invalid';
  end if;
  position_value :=
    (p_payload ->> 'recommendation_position')::smallint;
  recommendation_value :=
    content_factory_private.ai_research_recommendation_snapshot(
      organization_id_value,
      project_id_value,
      selection_id_value,
      position_value
    );
  if recommendation_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_ai_research_working_draft_scope_mismatch';
  end if;

  editable_fields_value := p_payload -> 'editable_fields';
  applied_fields_value := array(
    select jsonb_array_elements_text(p_payload -> 'applied_fields')
  );
  touched_fields_value := array(
    select jsonb_array_elements_text(p_payload -> 'touched_fields')
  );
  previous_values_value := p_payload -> 'previous_values';
  last_applied_values_value := p_payload -> 'last_applied_values';
  if jsonb_typeof(p_payload -> 'applied_fields') <> 'array'
     or jsonb_typeof(p_payload -> 'touched_fields') <> 'array'
     or not content_factory_private
       .ai_research_working_draft_fields_valid(editable_fields_value)
     or not content_factory_private
       .ai_research_working_draft_field_names_valid(applied_fields_value)
     or cardinality(applied_fields_value) < 1
     or not content_factory_private
       .ai_research_working_draft_field_names_valid(touched_fields_value)
     or not content_factory_private
       .ai_research_working_draft_value_map_valid(previous_values_value)
     or not content_factory_private
       .ai_research_working_draft_value_map_valid(
         last_applied_values_value
       )
     or jsonb_typeof(p_payload -> 'auto_apply_disabled') <> 'boolean'
  then
    raise exception using
      errcode = '22023',
      message = 'generation_ai_research_working_draft_fields_invalid';
  end if;
  auto_apply_disabled_value :=
    (p_payload ->> 'auto_apply_disabled')::boolean;

  if current_row.id is null then
    insert into content_factory.generation_ai_research_working_drafts (
      organization_id, project_id, status, revision,
      selection_id, recommendation_position, editable_fields,
      applied_fields, touched_fields, previous_values,
      last_applied_values, auto_apply_disabled,
      created_by, updated_by, last_mutation_id
    ) values (
      organization_id_value, project_id_value, 'active', 1,
      selection_id_value, position_value, editable_fields_value,
      applied_fields_value, touched_fields_value, previous_values_value,
      last_applied_values_value, auto_apply_disabled_value,
      user_id, user_id, mutation_id_value
    );
  else
    update content_factory.generation_ai_research_working_drafts draft
    set status = 'active',
        revision = draft.revision + 1,
        selection_id = selection_id_value,
        recommendation_position = position_value,
        editable_fields = editable_fields_value,
        applied_fields = applied_fields_value,
        touched_fields = touched_fields_value,
        previous_values = previous_values_value,
        last_applied_values = last_applied_values_value,
        auto_apply_disabled = auto_apply_disabled_value,
        updated_by = user_id,
        last_mutation_id = mutation_id_value,
        updated_at = clock_timestamp()
    where draft.organization_id = organization_id_value
      and draft.project_id = project_id_value;
  end if;

  return content_factory_private
    .generation_ai_research_working_draft_snapshot(
      organization_id_value,
      project_id_value
    );
end;
$$;

revoke all on function
  public.contentengine_generation_ai_research_working_draft(jsonb)
  from public, anon;
grant execute on function
  public.contentengine_generation_ai_research_working_draft(jsonb)
  to authenticated, service_role;

comment on function
  public.contentengine_generation_research_recommendation(jsonb) is
  'Resolves one human-approved AI Center recommendation from project + selection_id + position. Category and product identity are server-derived; no provider or paid call starts.';
comment on function
  public.contentengine_generation_ai_research_working_draft(jsonb) is
  'Project-shared optimistic working draft for one selected AI recommendation and six editable non-financial fields. It stores no media, destination, campaign, authorization, quantity or spend confirmation.';

notify pgrst, 'reload schema';

commit;

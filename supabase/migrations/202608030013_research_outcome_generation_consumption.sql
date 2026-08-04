begin;

-- This migration adds an explicit, short-lived apply/control decision for one
-- automatic brief.  It deliberately does not wrap generation policy or paid
-- start: a later migration must revalidate the same evidence at the final
-- prompt/job boundary before it may create an assignment row.

create unique index if not exists research_market_binding_exact_version_uq
  on content_factory.research_product_market_category_bindings (
    organization_id, product_id, id, category_id, binding_version
  );
create unique index if not exists research_outcome_candidate_exact_scope_uq
  on content_factory.research_outcome_learning_candidates (
    organization_id, id, market_category_id, platform, model,
    candidate_version, candidate_hash
  );
create unique index if not exists research_outcome_memory_exact_scope_uq
  on content_factory.research_outcome_learning_memory_versions (
    organization_id, id, market_category_id, platform, model,
    memory_version, candidate_id
  );
create unique index if not exists media_objects_org_id_product_uq
  on content_factory.media_objects (organization_id, id, product_id);

create table if not exists content_factory.research_outcome_generation_selections (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    input_media_id uuid not null,
    product_id uuid not null,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    market_category_id uuid not null,
    category_binding_id uuid not null,
    category_binding_version integer not null
      check (category_binding_version between 1 and 100000),
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    memory_version_id uuid not null,
    memory_version integer not null check (memory_version between 1 and 100000),
    candidate_id uuid not null,
    candidate_version integer not null
      check (candidate_version between 1 and 100000),
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    candidate_creative_angle text not null check (candidate_creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    selection_action text not null check (selection_action in ('apply', 'control')),
    selected_creative_angle text check (selected_creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    selected_hook_patterns jsonb not null default '[]'::jsonb
      check (selected_hook_patterns = '[]'::jsonb),
    structural_directive jsonb not null check (
      jsonb_typeof(structural_directive) = 'object'
      and structural_directive - array[
        'schema_version', 'creative_angle', 'hook_patterns'
      ]::text[] = '{}'::jsonb
      and structural_directive ->> 'schema_version' =
        'research-outcome-generation-structure-v1'
      and structural_directive -> 'hook_patterns' = '[]'::jsonb
    ),
    base_policy_version text not null check (length(base_policy_version) between 3 and 80),
    base_policy_hash text not null check (base_policy_hash ~ '^[0-9a-f]{64}$'),
    base_selection_mode text not null check (base_selection_mode in (
      'performance', 'quality', 'bounded_exploration'
    )),
    base_preferred_angle text not null check (base_preferred_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    guard_evidence jsonb not null check (
      jsonb_typeof(guard_evidence) = 'object'
      and guard_evidence - array[
        'explicit_per_auto_brief', 'exact_current_market_binding',
        'active_memory_current', 'candidate_hash_verified',
        'live_eligible_outcomes_revalidated', 'candidate_evidence_current',
        'base_policy_revalidated', 'existing_policy_precedence_preserved',
        'allowlisted_angle_only', 'hook_patterns_empty',
        'raw_competitor_content_excluded', 'claims_excluded',
        'human_approved_research_precedence',
        'live_evidence_consumption_revalidation',
        'final_policy_consumption_revalidation',
        'automatic_generation', 'automatic_spend', 'generation_binding'
      ]::text[] = '{}'::jsonb
      and guard_evidence -> 'explicit_per_auto_brief' = 'true'::jsonb
      and guard_evidence -> 'exact_current_market_binding' = 'true'::jsonb
      and guard_evidence -> 'active_memory_current' = 'true'::jsonb
      and guard_evidence -> 'candidate_hash_verified' = 'true'::jsonb
      and guard_evidence -> 'live_eligible_outcomes_revalidated' = 'true'::jsonb
      and guard_evidence -> 'candidate_evidence_current' = 'true'::jsonb
      and guard_evidence -> 'base_policy_revalidated' = 'true'::jsonb
      and guard_evidence -> 'existing_policy_precedence_preserved' = 'true'::jsonb
      and guard_evidence -> 'allowlisted_angle_only' = 'true'::jsonb
      and guard_evidence -> 'hook_patterns_empty' = 'true'::jsonb
      and guard_evidence -> 'raw_competitor_content_excluded' = 'true'::jsonb
      and guard_evidence -> 'claims_excluded' = 'true'::jsonb
      and guard_evidence ->> 'human_approved_research_precedence' =
        'required_at_consumption'
      and guard_evidence ->> 'live_evidence_consumption_revalidation' =
        'required_at_consumption'
      and guard_evidence ->> 'final_policy_consumption_revalidation' =
        'required_at_consumption'
      and guard_evidence -> 'automatic_generation' = 'false'::jsonb
      and guard_evidence -> 'automatic_spend' = 'false'::jsonb
      and guard_evidence ->> 'generation_binding' = 'gated'
    ),
    effectiveness_status text not null default 'unknown'
      check (effectiveness_status = 'unknown'),
    generation_binding_state text not null default 'gated'
      check (generation_binding_state = 'gated'),
    confirmation boolean not null check (confirmation),
    reason text not null check (length(btrim(reason)) between 3 and 500),
    selected_by uuid not null,
    selection_hash text not null check (selection_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    constraint research_outcome_generation_selections_org_id_uq
      unique (organization_id, id),
    constraint research_outcome_generation_selections_org_hash_uq
      unique (organization_id, selection_hash),
    constraint research_outcome_generation_selections_org_key_uq
      unique (organization_id, idempotency_key),
    foreign key (organization_id, input_media_id, product_id)
      references content_factory.media_objects(organization_id, id, product_id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (
      organization_id, product_id, category_binding_id, market_category_id,
      category_binding_version
    ) references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id, binding_version
    ),
    foreign key (organization_id, market_category_id)
      references content_factory.research_market_categories(organization_id, id),
    foreign key (
      organization_id, memory_version_id, market_category_id, platform, model,
      memory_version, candidate_id
    )
      references content_factory.research_outcome_learning_memory_versions(
        organization_id, id, market_category_id, platform, model,
        memory_version, candidate_id
      ),
    foreign key (
      organization_id, candidate_id, market_category_id, platform, model,
      candidate_version, candidate_hash
    )
      references content_factory.research_outcome_learning_candidates(
        organization_id, id, market_category_id, platform, model,
        candidate_version, candidate_hash
      ),
    foreign key (organization_id, selected_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (selection_action = 'apply'
       and selected_creative_angle = candidate_creative_angle
       and structural_directive ->> 'creative_angle' = candidate_creative_angle)
      or
      (selection_action = 'control'
       and selected_creative_angle is null
       and structural_directive -> 'creative_angle' = 'null'::jsonb)
    ),
    check (expires_at > created_at),
    check (expires_at <= created_at + interval '30 minutes')
);

create index if not exists research_outcome_generation_selections_scope_idx
  on content_factory.research_outcome_generation_selections (
    organization_id, product_id, platform, model, created_at desc, id desc
  );
create index if not exists research_outcome_generation_selections_candidate_idx
  on content_factory.research_outcome_generation_selections (
    organization_id, candidate_id, created_at desc, id desc
  );

-- This ledger is the append-only provenance target for a future, audited paid
-- start binding.  No RPC in this migration can insert it; effectiveness stays
-- unknown until an independent mature-outcome pipeline is added.
create table if not exists content_factory.research_outcome_generation_assignments (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    selection_id uuid not null,
    generation_job_id uuid not null,
    product_id uuid not null,
    market_category_id uuid not null,
    category_binding_id uuid not null,
    category_binding_version integer not null
      check (category_binding_version between 1 and 100000),
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    memory_version_id uuid not null,
    memory_version integer not null check (memory_version between 1 and 100000),
    candidate_id uuid not null,
    candidate_version integer not null
      check (candidate_version between 1 and 100000),
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    assignment_action text not null check (assignment_action in ('apply', 'control')),
    selected_creative_angle text check (selected_creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    selected_hook_patterns jsonb not null default '[]'::jsonb
      check (selected_hook_patterns = '[]'::jsonb),
    selection_hash text not null check (selection_hash ~ '^[0-9a-f]{64}$'),
    base_policy_hash text not null check (base_policy_hash ~ '^[0-9a-f]{64}$'),
    final_policy_hash text not null check (final_policy_hash ~ '^[0-9a-f]{64}$'),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    effectiveness_status text not null default 'unknown'
      check (effectiveness_status = 'unknown'),
    bound_by uuid not null,
    bound_at timestamptz not null default now(),
    constraint research_outcome_generation_assignments_org_id_uq
      unique (organization_id, id),
    constraint research_outcome_generation_assignments_org_selection_uq
      unique (organization_id, selection_id),
    constraint research_outcome_generation_assignments_org_job_uq
      unique (organization_id, generation_job_id),
    foreign key (organization_id, selection_id)
      references content_factory.research_outcome_generation_selections(
        organization_id, id
      ),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (
      organization_id, product_id, category_binding_id, market_category_id,
      category_binding_version
    ) references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id, binding_version
    ),
    foreign key (
      organization_id, memory_version_id, market_category_id, platform, model,
      memory_version, candidate_id
    )
      references content_factory.research_outcome_learning_memory_versions(
        organization_id, id, market_category_id, platform, model,
        memory_version, candidate_id
      ),
    foreign key (
      organization_id, candidate_id, market_category_id, platform, model,
      candidate_version, candidate_hash
    )
      references content_factory.research_outcome_learning_candidates(
        organization_id, id, market_category_id, platform, model,
        candidate_version, candidate_hash
      ),
    foreign key (organization_id, bound_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (assignment_action = 'apply' and selected_creative_angle is not null)
      or (assignment_action = 'control' and selected_creative_angle is null)
    )
);

create index if not exists research_outcome_generation_assignments_candidate_idx
  on content_factory.research_outcome_generation_assignments (
    organization_id, candidate_id, bound_at desc, id desc
  );

alter table content_factory.research_outcome_generation_selections
  enable row level security;
alter table content_factory.research_outcome_generation_assignments
  enable row level security;

revoke all on content_factory.research_outcome_generation_selections
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_outcome_generation_assignments
  from public, anon, authenticated, service_role;

drop trigger if exists research_outcome_generation_selection_append_only
  on content_factory.research_outcome_generation_selections;
create trigger research_outcome_generation_selection_append_only
before update or delete on content_factory.research_outcome_generation_selections
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();

drop trigger if exists research_outcome_generation_assignment_append_only
  on content_factory.research_outcome_generation_assignments;
create trigger research_outcome_generation_assignment_append_only
before update or delete on content_factory.research_outcome_generation_assignments
for each row execute function
  content_factory_private.reject_research_outcome_learning_mutation();

create or replace function
  content_factory_private.validate_research_outcome_generation_assignment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  selection_row content_factory.research_outcome_generation_selections%rowtype;
  job_row content_factory.generation_jobs%rowtype;
begin
  select selection.* into selection_row
  from content_factory.research_outcome_generation_selections selection
  where selection.organization_id = new.organization_id
    and selection.id = new.selection_id
  for share;
  if selection_row.id is null then
    raise exception using
      errcode = '23503', message = 'research_outcome_generation_selection_not_found';
  end if;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = new.generation_job_id
  for share;
  if job_row.id is null then
    raise exception using
      errcode = '23503', message = 'research_outcome_generation_job_not_found';
  end if;
  if new.bound_at > selection_row.expires_at
     or job_row.created_at < selection_row.created_at
     or job_row.created_at > selection_row.expires_at
     or job_row.mode <> 'real'
     or not job_row.allow_real_spend
     or job_row.product_id <> selection_row.product_id
     or job_row.input ->> 'platform' <> selection_row.platform
     or job_row.input ->> 'model' <> selection_row.model
     or job_row.input ->> 'product_category' <> selection_row.product_category
     or new.product_id <> selection_row.product_id
     or new.market_category_id <> selection_row.market_category_id
     or new.category_binding_id <> selection_row.category_binding_id
     or new.category_binding_version <> selection_row.category_binding_version
     or new.platform <> selection_row.platform
     or new.model <> selection_row.model
     or new.product_category <> selection_row.product_category
     or new.memory_version_id <> selection_row.memory_version_id
     or new.memory_version <> selection_row.memory_version
     or new.candidate_id <> selection_row.candidate_id
     or new.candidate_version <> selection_row.candidate_version
     or new.candidate_hash <> selection_row.candidate_hash
     or new.assignment_action <> selection_row.selection_action
     or new.selected_creative_angle is distinct from
        selection_row.selected_creative_angle
     or new.selected_hook_patterns <> '[]'::jsonb
     or new.selection_hash <> selection_row.selection_hash
     or new.base_policy_hash <> selection_row.base_policy_hash
     or new.effectiveness_status <> 'unknown' then
    raise exception using
      errcode = '55000', message = 'research_outcome_generation_assignment_invalid';
  end if;
  -- Deliberate hard gate.  A future migration may replace this trigger only
  -- when browser/Edge/paid-start prompt and human-approved research precedence
  -- can all be revalidated atomically.
  raise exception using
    errcode = '55000',
    message = 'research_outcome_generation_assignment_binding_not_wired';
end;
$$;

-- Define the typed seam before the public wrappers so PostgreSQL can validate
-- their static calls.  The complete fail-closed resolver replaces this body
-- later in the same transaction, before anything becomes visible.
create or replace function
  content_factory_private.research_outcome_generation_advisory(
    organization_id_value uuid,
    media_id_value uuid,
    platform_value text,
    model_value text,
    product_category_value text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'research_outcome_generation_advisory_not_initialized';
end;
$$;

create or replace function public.creator_research_outcome_generation_advisory(
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
  organization_id_value uuid;
  media_id_value uuid;
  platform_value text;
  model_value text;
  product_category_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'media_id', 'platform', 'model', 'product_category'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_outcome_generation_advisory_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  media_id_value := content_factory_private.require_uuid(p_payload, 'media_id');
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  ));
  model_value := lower(content_factory_private.require_text(
    p_payload, 'model', 2, 80
  ));
  product_category_value := lower(content_factory_private.require_text(
    p_payload, 'product_category', 2, 40
  ));
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) or model_value not in (
    'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
  ) or product_category_value not in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  ) then
    raise exception using
      errcode = '22023', message = 'research_outcome_generation_scope_invalid';
  end if;
  return content_factory_private.research_outcome_generation_advisory(
    organization_id_value,
    media_id_value,
    platform_value,
    model_value,
    product_category_value
  );
end;
$$;

create or replace function
  public.creator_prepare_research_outcome_generation_selection(
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
  media_id_value uuid;
  platform_value text;
  model_value text;
  product_category_value text;
  expected_market_category_id_value uuid;
  category_binding_id_value uuid;
  expected_category_binding_version_value integer;
  memory_version_id_value uuid;
  memory_version_value integer;
  candidate_id_value uuid;
  candidate_version_value integer;
  candidate_hash_value text;
  selection_action_value text;
  reason_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  advisory jsonb;
  product_id_value uuid;
  market_category_id_value uuid;
  category_binding_version_value integer;
  candidate_angle_value text;
  selected_angle_value text;
  structural_directive_value jsonb;
  base_policy_version_value text;
  base_policy_hash_value text;
  base_selection_mode_value text;
  base_preferred_angle_value text;
  guard_evidence_value jsonb;
  selection_id_value uuid := extensions.gen_random_uuid();
  selection_hash_value text;
  selected_at_value timestamptz := clock_timestamp();
  expires_at_value timestamptz;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'media_id', 'platform', 'model', 'product_category',
    'market_category_id', 'category_binding_id', 'category_binding_version',
    'memory_version_id', 'memory_version',
    'candidate_id', 'candidate_version', 'candidate_hash',
    'selection_action', 'confirmation', 'reason', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_outcome_generation_selection_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  media_id_value := content_factory_private.require_uuid(p_payload, 'media_id');
  expected_market_category_id_value := content_factory_private.require_uuid(
    p_payload, 'market_category_id'
  );
  category_binding_id_value := content_factory_private.require_uuid(
    p_payload, 'category_binding_id'
  );
  memory_version_id_value := content_factory_private.require_uuid(
    p_payload, 'memory_version_id'
  );
  candidate_id_value := content_factory_private.require_uuid(
    p_payload, 'candidate_id'
  );
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  ));
  model_value := lower(content_factory_private.require_text(
    p_payload, 'model', 2, 80
  ));
  product_category_value := lower(content_factory_private.require_text(
    p_payload, 'product_category', 2, 40
  ));
  selection_action_value := lower(content_factory_private.require_text(
    p_payload, 'selection_action', 5, 7
  ));
  candidate_hash_value := content_factory_private.require_text(
    p_payload, 'candidate_hash', 64, 64
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if jsonb_typeof(p_payload -> 'confirmation') is distinct from 'boolean'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_outcome_generation_selection_confirmation_required';
  end if;
  begin
    expected_category_binding_version_value :=
      (p_payload ->> 'category_binding_version')::integer;
    memory_version_value := (p_payload ->> 'memory_version')::integer;
    candidate_version_value := (p_payload ->> 'candidate_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'research_outcome_generation_selection_version_invalid';
  end;
  if expected_category_binding_version_value is null
     or memory_version_value is null
     or candidate_version_value is null
     or expected_category_binding_version_value not between 1 and 100000
     or memory_version_value not between 1 and 100000
     or candidate_version_value not between 1 and 100000
     or candidate_hash_value !~ '^[0-9a-f]{64}$'
     or selection_action_value not in ('apply', 'control')
     or platform_value not in (
       'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or model_value not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or product_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     ) then
    raise exception using
      errcode = '22023', message = 'research_outcome_generation_selection_invalid';
  end if;

  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id_value,
    'creator_prepare_research_outcome_generation_selection',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  -- Resolve once to identify the exact product/scope, lock both independent
  -- control planes, then resolve again.  Final generation consumption must do
  -- this once more and is intentionally absent from this migration.
  advisory := content_factory_private.research_outcome_generation_advisory(
    organization_id_value,
    media_id_value,
    platform_value,
    model_value,
    product_category_value
  );
  product_id_value := (advisory ->> 'product_id')::uuid;
  market_category_id_value :=
    (advisory #>> '{scope,market_category_id}')::uuid;
  if product_id_value is null or market_category_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'research_outcome_generation_selection_unavailable';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-market-product:' || product_id_value::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext(
      'research-outcome-learning:' || market_category_id_value::text || ':' ||
      platform_value || ':' || model_value
    )
  );
  advisory := content_factory_private.research_outcome_generation_advisory(
    organization_id_value,
    media_id_value,
    platform_value,
    model_value,
    product_category_value
  );

  if advisory #>> '{scope,market_category_id}' is distinct from
       expected_market_category_id_value::text
     or advisory #>> '{scope,category_binding_id}' is distinct from
       category_binding_id_value::text
     or advisory #>> '{scope,category_binding_version}' is distinct from
       expected_category_binding_version_value::text
     or advisory #>> '{memory,memory_version_id}' is distinct from
       memory_version_id_value::text
     or advisory #>> '{memory,memory_version}' is distinct from
       memory_version_value::text
     or advisory #>> '{candidate,candidate_id}' is distinct from
       candidate_id_value::text
     or advisory #>> '{candidate,candidate_version}' is distinct from
       candidate_version_value::text
     or advisory #>> '{candidate,candidate_hash}' is distinct from
       candidate_hash_value then
    raise exception using
      errcode = '55000',
      message = 'research_outcome_generation_selection_stale';
  end if;
  if selection_action_value = 'apply'
     and advisory #> '{permissions,apply_allowed}' is distinct from
       'true'::jsonb then
    raise exception using
      errcode = '55000',
      message = 'research_outcome_generation_apply_not_allowed';
  elsif selection_action_value = 'control'
        and advisory #> '{permissions,control_allowed}' is distinct from
          'true'::jsonb then
    raise exception using
      errcode = '55000',
      message = 'research_outcome_generation_control_not_allowed';
  end if;

  product_id_value := (advisory ->> 'product_id')::uuid;
  market_category_id_value :=
    (advisory #>> '{scope,market_category_id}')::uuid;
  category_binding_version_value :=
    (advisory #>> '{scope,category_binding_version}')::integer;
  candidate_angle_value := advisory #>> '{candidate,creative_angle}';
  selected_angle_value := case selection_action_value
    when 'apply' then candidate_angle_value else null end;
  structural_directive_value := jsonb_build_object(
    'schema_version', 'research-outcome-generation-structure-v1',
    'creative_angle', selected_angle_value,
    'hook_patterns', '[]'::jsonb
  );
  base_policy_version_value := advisory #>> '{base_policy,version}';
  base_policy_hash_value := advisory #>> '{base_policy,policy_hash}';
  base_selection_mode_value := advisory #>> '{base_policy,selection_mode}';
  base_preferred_angle_value := advisory #>> '{base_policy,preferred_angle}';
  guard_evidence_value := jsonb_build_object(
    'explicit_per_auto_brief', true,
    'exact_current_market_binding', true,
    'active_memory_current', true,
    'candidate_hash_verified', true,
    'live_eligible_outcomes_revalidated', true,
    'candidate_evidence_current', true,
    'base_policy_revalidated', true,
    'existing_policy_precedence_preserved', true,
    'allowlisted_angle_only', true,
    'hook_patterns_empty', true,
    'raw_competitor_content_excluded', true,
    'claims_excluded', true,
    'human_approved_research_precedence', 'required_at_consumption',
    'live_evidence_consumption_revalidation', 'required_at_consumption',
    'final_policy_consumption_revalidation', 'required_at_consumption',
    'automatic_generation', false,
    'automatic_spend', false,
    'generation_binding', 'gated'
  );
  expires_at_value := selected_at_value + interval '30 minutes';
  selection_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'selection_id', selection_id_value,
    'organization_id', organization_id_value,
    'input_media_id', media_id_value,
    'product_id', product_id_value,
    'product_category', product_category_value,
    'market_category_id', market_category_id_value,
    'category_binding_id', category_binding_id_value,
    'category_binding_version', category_binding_version_value,
    'platform', platform_value,
    'model', model_value,
    'memory_version_id', memory_version_id_value,
    'memory_version', memory_version_value,
    'candidate_id', candidate_id_value,
    'candidate_version', candidate_version_value,
    'candidate_hash', candidate_hash_value,
    'selection_action', selection_action_value,
    'structural_directive', structural_directive_value,
    'base_policy_hash', base_policy_hash_value,
    'selected_by', user_id,
    'selected_at', selected_at_value,
    'expires_at', expires_at_value
  ));

  insert into content_factory.research_outcome_generation_selections (
    id, organization_id, input_media_id, product_id, product_category,
    market_category_id, category_binding_id, category_binding_version,
    platform, model, memory_version_id, memory_version, candidate_id,
    candidate_version, candidate_hash, candidate_creative_angle,
    selection_action, selected_creative_angle, selected_hook_patterns,
    structural_directive, base_policy_version, base_policy_hash,
    base_selection_mode, base_preferred_angle, guard_evidence,
    effectiveness_status, generation_binding_state, confirmation, reason,
    selected_by, selection_hash, idempotency_key, created_at, expires_at
  ) values (
    selection_id_value, organization_id_value, media_id_value, product_id_value,
    product_category_value, market_category_id_value, category_binding_id_value,
    category_binding_version_value, platform_value, model_value,
    memory_version_id_value, memory_version_value, candidate_id_value,
    candidate_version_value, candidate_hash_value, candidate_angle_value,
    selection_action_value, selected_angle_value, '[]'::jsonb,
    structural_directive_value, base_policy_version_value,
    base_policy_hash_value, base_selection_mode_value,
    base_preferred_angle_value, guard_evidence_value, 'unknown', 'gated', true,
    reason_value, user_id, selection_hash_value, idempotency_key_value,
    selected_at_value, expires_at_value
  );

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-outcome-generation-consumption-v1',
    'selection', jsonb_build_object(
      'selection_id', selection_id_value,
      'selection_hash', selection_hash_value,
      'selection_action', selection_action_value,
      'input_media_id', media_id_value,
      'product_id', product_id_value,
      'scope', jsonb_build_object(
        'market_category_id', market_category_id_value,
        'category_binding_id', category_binding_id_value,
        'category_binding_version', category_binding_version_value,
        'platform', platform_value,
        'model', model_value,
        'product_category', product_category_value
      ),
      'memory_version_id', memory_version_id_value,
      'memory_version', memory_version_value,
      'candidate_id', candidate_id_value,
      'candidate_version', candidate_version_value,
      'candidate_hash', candidate_hash_value,
      'structural_directive', structural_directive_value,
      'base_policy_hash', base_policy_hash_value,
      'effectiveness_status', 'unknown',
      'generation_binding_state', 'gated',
      'created_at', selected_at_value,
      'expires_at', expires_at_value
    ),
    'guidance', jsonb_build_object(
      'status', 'selection_prepared_generation_binding_required',
      'recommended_next_step',
        'bind_and_revalidate_at_generation_policy_and_paid_start',
      'explicit_per_auto_brief', true,
      'automatic_selection', false,
      'generation_consumption_allowed', false,
      'generation_consumption', 'gated_not_wired',
      'effectiveness_status', 'unknown',
      'consumption_blockers', jsonb_build_array(
        'human_approved_research_precedence_unbound',
        'live_evidence_final_revalidation_unbound',
        'final_policy_and_prompt_hash_unbound',
        'paid_start_assignment_unbound'
      ),
      'provider_action', false,
      'spend_action', false,
      'generation_action', false,
      'publication_action', false
    )
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id,
    'creator_prepare_research_outcome_generation_selection',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function
  content_factory_private.validate_research_outcome_generation_assignment()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_outcome_generation_advisory(
    uuid, uuid, text, text, text
  )
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_research_outcome_generation_advisory(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.creator_prepare_research_outcome_generation_selection(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.creator_research_outcome_generation_advisory(jsonb)
  to authenticated;
grant execute on function
  public.creator_prepare_research_outcome_generation_selection(jsonb)
  to authenticated;

drop trigger if exists research_outcome_generation_assignment_validate
  on content_factory.research_outcome_generation_assignments;
create trigger research_outcome_generation_assignment_validate
before insert on content_factory.research_outcome_generation_assignments
for each row execute function
  content_factory_private.validate_research_outcome_generation_assignment();

create or replace function
  content_factory_private.research_outcome_generation_advisory(
    organization_id_value uuid,
    media_id_value uuid,
    platform_value text,
    model_value text,
    product_category_value text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  base_policy jsonb;
  product_id_value uuid;
  binding_row content_factory.research_product_market_category_bindings%rowtype;
  category_status_value text;
  memory_row content_factory.research_outcome_learning_memory_versions%rowtype;
  candidate_row content_factory.research_outcome_learning_candidates%rowtype;
  latest_candidate_version integer := 0;
  candidate_angle_value text;
  comparator_angle_value text;
  evidence_count integer := 0;
  evidence_angle_count integer := 0;
  evidence_product_count integer := 0;
  preferred_count integer := 0;
  comparator_count integer := 0;
  preferred_product_count integer := 0;
  comparator_product_count integer := 0;
  overlapping_product_count integer := 0;
  independent_approval_count integer := 0;
  memory_decision_valid boolean := false;
  candidate_hash_verified boolean := false;
  candidate_structure_valid boolean := false;
  candidate_qualification_current boolean := false;
  candidate_evidence_current boolean := false;
  live_evidence_current boolean := false;
  base_policy_valid boolean := false;
  hard_rejection_count integer := 0;
  hard_approval_count integer := 0;
  candidate_hard_rejected boolean := false;
  apply_allowed boolean := false;
  control_allowed boolean := false;
  status_value text := 'market_category_binding_required';
  next_step_value text := 'confirm_exact_market_category';
begin
  -- Calling the installed policy is intentional: it is the authoritative
  -- identity, membership, training, media-rights, exact-product, rejection,
  -- quality and effectiveness boundary.  This helper never replaces it.
  base_policy := public.creator_generation_learning_policy(
    jsonb_build_object(
      'organization_id', organization_id_value,
      'media_id', media_id_value,
      'platform', platform_value,
      'model', model_value,
      'product_category', product_category_value
    )
  );

  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.id = media_id_value;

  select binding.* into binding_row
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1;

  if binding_row.id is not null then
    select category.status into category_status_value
    from content_factory.research_market_categories category
    where category.organization_id = organization_id_value
      and category.id = binding_row.category_id;

    select memory.* into memory_row
    from content_factory.research_outcome_learning_memory_versions memory
    where memory.organization_id = organization_id_value
      and memory.market_category_id = binding_row.category_id
      and memory.platform = platform_value
      and memory.model = model_value
      and memory.candidate_kind = 'creative_angle_preference'
    order by memory.memory_version desc, memory.id desc
    limit 1;
  end if;

  if memory_row.id is not null
     and memory_row.state = 'active'
     and memory_row.action in ('activate', 'revert')
     and memory_row.candidate_id is not null then
    select candidate.* into candidate_row
    from content_factory.research_outcome_learning_candidates candidate
    where candidate.organization_id = organization_id_value
      and candidate.id = memory_row.candidate_id;
  end if;

  if candidate_row.id is not null then
    candidate_angle_value :=
      candidate_row.candidate_payload ->> 'preferred_creative_angle';
    comparator_angle_value :=
      candidate_row.effectiveness_evidence #>> '{comparator,creative_angle}';
    candidate_hash_verified := candidate_row.candidate_hash =
      content_factory_private.json_hash(jsonb_build_object(
        'candidate_payload', candidate_row.candidate_payload,
        'effectiveness_evidence', candidate_row.effectiveness_evidence,
        'guard_evidence', candidate_row.guard_evidence,
        'evidence_hash', candidate_row.evidence_hash
      ));
    select exists (
      select 1
      from content_factory.research_outcome_learning_decisions decision
      where decision.organization_id = organization_id_value
        and decision.id = memory_row.decision_id
        and decision.candidate_id = candidate_row.id
        and decision.action = memory_row.action
        and decision.action in ('activate', 'revert')
        and decision.candidate_version = candidate_row.candidate_version
        and decision.candidate_hash = candidate_row.candidate_hash
        and decision.expected_scope_version = memory_row.memory_version - 1
        and decision.confirmation
        and decision.confirmed_by = memory_row.activated_by
    ) into memory_decision_valid;
    candidate_structure_valid := coalesce((
      candidate_hash_verified
      and memory_decision_valid
      and candidate_row.organization_id = organization_id_value
      and candidate_row.market_category_id = binding_row.category_id
      and candidate_row.platform = platform_value
      and candidate_row.model = model_value
      and candidate_row.candidate_kind = 'creative_angle_preference'
      and jsonb_typeof(candidate_row.candidate_payload) = 'object'
      and candidate_row.candidate_payload - array[
        'schema_version', 'candidate_kind', 'scope',
        'preferred_creative_angle', 'avoid_creative_angle', 'ruleset_version'
      ]::text[] = '{}'::jsonb
      and candidate_row.candidate_payload ->> 'schema_version' =
        'research-outcome-learning-v1'
      and candidate_row.candidate_payload ->> 'candidate_kind' =
        'creative_angle_preference'
      and candidate_row.candidate_payload -> 'scope' = jsonb_build_object(
        'market_category_id', binding_row.category_id,
        'platform', platform_value,
        'model', model_value
      )
      and candidate_row.candidate_payload -> 'avoid_creative_angle' =
        'null'::jsonb
      and candidate_angle_value in (
        'product_focus', 'trust_builder', 'demonstration', 'comparison',
        'objection_handling', 'curiosity_gap'
      )
      and comparator_angle_value in (
        'product_focus', 'trust_builder', 'demonstration', 'comparison',
        'objection_handling', 'curiosity_gap'
      )
      and comparator_angle_value <> candidate_angle_value
      and candidate_row.guard_evidence -> 'market_category_exact' = 'true'::jsonb
      and candidate_row.guard_evidence -> 'tenant_scope_exact' = 'true'::jsonb
      and candidate_row.guard_evidence -> 'raw_competitor_content_excluded' =
        'true'::jsonb
      and candidate_row.guard_evidence -> 'raw_prompt_caption_url_excluded' =
        'true'::jsonb
      and candidate_row.guard_evidence -> 'automatic_activation' = 'false'::jsonb
      and candidate_row.guard_evidence -> 'advisory_only' = 'true'::jsonb
      and candidate_row.guard_evidence ->> 'generation_consumption' = 'not_wired'
    ), false);

    select coalesce(max(candidate.candidate_version), 0)
      into latest_candidate_version
    from content_factory.research_outcome_learning_candidates candidate
    where candidate.organization_id = organization_id_value
      and candidate.market_category_id = binding_row.category_id
      and candidate.platform = platform_value
      and candidate.model = model_value
      and candidate.candidate_kind = 'creative_angle_preference';

    with evidence as (
      select
        lineage.*,
        job.requested_by,
        job.assigned_to,
        decision.decided_by,
        decision.decision as review_decision,
        decision.media_watched_confirmed
      from content_factory.research_outcome_learning_candidate_evidence link
      join content_factory.research_outcome_lineage_snapshots lineage
        on lineage.organization_id = link.organization_id
       and lineage.id = link.lineage_snapshot_id
      join content_factory.generation_jobs job
        on job.organization_id = lineage.organization_id
       and job.id = lineage.generation_job_id
      join content_factory.content_review_decisions decision
        on decision.organization_id = lineage.organization_id
       and decision.review_id = lineage.review_id
       and decision.id = lineage.review_decision_id
      where link.organization_id = organization_id_value
        and link.candidate_id = candidate_row.id
    )
    select
      count(*)::integer,
      count(distinct evidence.creative_angle)::integer,
      count(distinct evidence.product_id)::integer,
      count(*) filter (
        where evidence.creative_angle = candidate_angle_value
      )::integer,
      count(*) filter (
        where evidence.creative_angle = comparator_angle_value
      )::integer,
      count(distinct evidence.product_id) filter (
        where evidence.creative_angle = candidate_angle_value
      )::integer,
      count(distinct evidence.product_id) filter (
        where evidence.creative_angle = comparator_angle_value
      )::integer,
      count(*) filter (
        where evidence.review_decision = 'approved'
          and evidence.media_watched_confirmed
          and evidence.decided_by is distinct from evidence.requested_by
          and evidence.decided_by is distinct from evidence.assigned_to
      )::integer
    into
      evidence_count,
      evidence_angle_count,
      evidence_product_count,
      preferred_count,
      comparator_count,
      preferred_product_count,
      comparator_product_count,
      independent_approval_count
    from evidence;

    with evidence as (
      select lineage.product_id, lineage.creative_angle
      from content_factory.research_outcome_learning_candidate_evidence link
      join content_factory.research_outcome_lineage_snapshots lineage
        on lineage.organization_id = link.organization_id
       and lineage.id = link.lineage_snapshot_id
      where link.organization_id = organization_id_value
        and link.candidate_id = candidate_row.id
        and lineage.creative_angle in (
          candidate_angle_value, comparator_angle_value
        )
    )
    select count(*)::integer into overlapping_product_count
    from (
      select evidence.product_id
      from evidence
      group by evidence.product_id
      having count(distinct evidence.creative_angle) = 2
    ) overlap;

    candidate_qualification_current := coalesce((
      candidate_structure_valid
      and evidence_count >= 6
      and evidence_angle_count >= 2
      and evidence_product_count >= 2
      and preferred_count >= 3
      and comparator_count >= 3
      and preferred_product_count >= 2
      and comparator_product_count >= 2
      and overlapping_product_count >= 2
      and independent_approval_count = evidence_count
      and candidate_row.effectiveness_evidence -> 'eligible_outcome_count' =
        to_jsonb(evidence_count)
      and candidate_row.effectiveness_evidence -> 'eligible_angle_count' =
        to_jsonb(evidence_angle_count)
      and candidate_row.effectiveness_evidence -> 'minimum_outcomes_per_angle' =
        '3'::jsonb
      and candidate_row.effectiveness_evidence -> 'minimum_views_per_outcome' =
        '100'::jsonb
      and candidate_row.effectiveness_evidence -> 'minimum_maturity_hours' =
        '72'::jsonb
      and candidate_row.effectiveness_evidence -> 'maximum_outcomes_considered' =
        '10000'::jsonb
      and candidate_row.effectiveness_evidence -> 'overlapping_product_count' =
        to_jsonb(overlapping_product_count)
      and candidate_row.effectiveness_evidence -> 'views_are_not_a_rank_signal' =
        'true'::jsonb
      and candidate_row.guard_evidence -> 'qa_approved_outcome_count' =
        to_jsonb(evidence_count)
      and candidate_row.guard_evidence -> 'first_party_metric_outcome_count' =
        to_jsonb(evidence_count)
      and candidate_row.guard_evidence -> 'distinct_product_count' =
        to_jsonb(evidence_product_count)
    ), false);

    with latest as (
      select lineage.id,
        row_number() over (
          partition by lineage.organization_id, lineage.placement_id
          order by lineage.metric_observed_at desc, lineage.captured_at desc,
                   lineage.id desc
        ) as placement_rank,
        lineage.metric_observed_at,
        lineage.captured_at
      from content_factory.research_outcome_lineage_snapshots lineage
      where lineage.organization_id = organization_id_value
        and lineage.market_category_id = binding_row.category_id
        and lineage.platform = platform_value
        and lineage.model = model_value
    ), current_outcomes as (
      select latest.id
      from latest
      where latest.placement_rank = 1
      order by latest.metric_observed_at desc, latest.captured_at desc,
               latest.id desc
      limit 10000
    ), candidate_evidence as (
      select evidence.lineage_snapshot_id as id
      from content_factory.research_outcome_learning_candidate_evidence evidence
      where evidence.organization_id = organization_id_value
        and evidence.candidate_id = candidate_row.id
    ), evidence_difference as (
      (select current_outcomes.id from current_outcomes
       except
       select candidate_evidence.id from candidate_evidence)
      union all
      (select candidate_evidence.id from candidate_evidence
       except
       select current_outcomes.id from current_outcomes)
    )
    select not exists (select 1 from evidence_difference)
      into candidate_evidence_current;

    with live as (
      select
        current_source.organization_id,
        current_source.product_id,
        current_source.market_category_id,
        current_source.category_binding_id,
        current_source.generation_job_id,
        current_source.creative_signal_id,
        current_source.placement_id,
        current_source.metric_snapshot_id
      from content_factory_private.research_current_eligible_outcomes(
        organization_id_value,
        binding_row.category_id,
        platform_value,
        model_value
      ) current_source
    ), evidence as (
      select
        lineage.organization_id,
        lineage.product_id,
        lineage.market_category_id,
        lineage.category_binding_id,
        lineage.generation_job_id,
        lineage.creative_signal_id,
        lineage.placement_id,
        lineage.metric_snapshot_id
      from content_factory.research_outcome_learning_candidate_evidence link
      join content_factory.research_outcome_lineage_snapshots lineage
        on lineage.organization_id = link.organization_id
       and lineage.id = link.lineage_snapshot_id
      where link.organization_id = organization_id_value
        and link.candidate_id = candidate_row.id
    )
    select
      not exists (
        select 1 from live
        where not exists (
          select 1 from evidence
          where evidence.organization_id = live.organization_id
            and evidence.product_id = live.product_id
            and evidence.market_category_id = live.market_category_id
            and evidence.category_binding_id = live.category_binding_id
            and evidence.generation_job_id = live.generation_job_id
            and evidence.creative_signal_id = live.creative_signal_id
            and evidence.placement_id = live.placement_id
            and evidence.metric_snapshot_id = live.metric_snapshot_id
        )
      )
      and not exists (
        select 1 from evidence
        where not exists (
          select 1 from live
          where live.organization_id = evidence.organization_id
            and live.product_id = evidence.product_id
            and live.market_category_id = evidence.market_category_id
            and live.category_binding_id = evidence.category_binding_id
            and live.generation_job_id = evidence.generation_job_id
            and live.creative_signal_id = evidence.creative_signal_id
            and live.placement_id = evidence.placement_id
            and live.metric_snapshot_id = evidence.metric_snapshot_id
        )
      )
    into live_evidence_current;
  end if;

  base_policy_valid := coalesce((
    base_policy -> 'applied' = 'true'::jsonb
    and base_policy -> 'generation_allowed' = 'true'::jsonb
    and base_policy ->> 'policy_hash' ~ '^[0-9a-f]{64}$'
    and base_policy ->> 'product_category' = product_category_value
    and base_policy ->> 'selection_mode' in (
      'performance', 'quality', 'bounded_exploration'
    )
    and base_policy ->> 'preferred_angle' in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )
  ), false);

  if candidate_structure_valid
     and candidate_qualification_current
     and candidate_evidence_current
     and live_evidence_current
     and latest_candidate_version = candidate_row.candidate_version then
    with exact_outcomes as (
      select quality.decision
      from content_factory.generation_creative_signals signal
      join content_factory.generation_jobs job
        on job.organization_id = signal.organization_id
       and job.id = signal.generation_job_id
       and job.product_id = signal.product_id
       and job.status = 'succeeded'
       and job.mode = 'real'
      join content_factory.media_objects media
        on media.organization_id = job.organization_id
       and media.id::text = job.output ->> 'output_media_id'
       and media.product_id = job.product_id
       and media.status = 'ready'
       and media.metadata ->> 'kind' in ('generated_video', 'generated_image')
      join lateral (
        select decision.decision
        from content_factory.content_review_runs review
        join content_factory.content_review_decisions decision
          on decision.organization_id = review.organization_id
         and decision.review_id = review.id
         and decision.review_completion_hash = review.completion_hash
         and decision.media_sha256_snapshot = review.media_sha256_snapshot
         and decision.decided_by is distinct from job.requested_by
         and decision.decided_by is distinct from job.assigned_to
        where review.organization_id = job.organization_id
          and review.media_object_id = media.id
          and review.status = 'completed'
          and review.media_sha256_snapshot = media.sha256
        order by decision.created_at desc, review.created_at desc
        limit 1
      ) quality on true
      where signal.organization_id = organization_id_value
        and signal.product_id = product_id_value
        and signal.product_category = product_category_value
        and signal.platform = platform_value
        and signal.model = model_value
        and signal.creative_angle = candidate_angle_value
        and (
          model_value = 'seedream5_lite'
          or signal.hook_patterns = '[]'::jsonb
        )
      order by signal.created_at desc, signal.generation_job_id
      limit 60
    )
    select
      count(*) filter (where decision = 'rejected')::integer,
      count(*) filter (where decision = 'approved')::integer
    into hard_rejection_count, hard_approval_count
    from exact_outcomes;
  end if;
  candidate_hard_rejected :=
    hard_rejection_count > 0 and hard_approval_count = 0;

  control_allowed :=
    binding_row.id is not null
    and category_status_value = 'active'
    and memory_row.id is not null
    and memory_row.state = 'active'
    and memory_row.candidate_id = candidate_row.id
    and memory_decision_valid
    and candidate_structure_valid
    and candidate_qualification_current
    and candidate_evidence_current
    and live_evidence_current
    and latest_candidate_version = candidate_row.candidate_version
    and base_policy_valid;
  apply_allowed :=
    control_allowed
    and base_policy ->> 'selection_mode' = 'bounded_exploration'
    and not candidate_hard_rejected;

  if binding_row.id is null then
    status_value := 'market_category_binding_required';
    next_step_value := 'confirm_exact_market_category';
  elsif category_status_value <> 'active' then
    status_value := 'market_category_retired';
    next_step_value := 'confirm_active_market_category';
  elsif memory_row.id is null or memory_row.state <> 'active' then
    status_value := 'no_active_advisory_memory';
    next_step_value := 'review_and_activate_outcome_candidate';
  elsif candidate_row.id is null
        or not candidate_structure_valid
        or not candidate_qualification_current then
    status_value := 'invalid_active_candidate';
    next_step_value := 'deactivate_and_refresh_candidate';
  elsif latest_candidate_version <> candidate_row.candidate_version then
    status_value := 'candidate_decision_required';
    next_step_value := 'review_latest_candidate_before_selection';
  elsif not candidate_evidence_current or not live_evidence_current then
    status_value := 'refresh_required';
    next_step_value := 'refresh_and_reapprove_outcome_candidate';
  elsif not base_policy_valid then
    status_value := 'base_policy_blocks_generation';
    next_step_value := 'resolve_existing_generation_policy_guard';
  elsif base_policy ->> 'selection_mode' <> 'bounded_exploration' then
    status_value := 'control_only_exact_product_policy_precedence';
    next_step_value := 'keep_exact_product_policy_or_choose_control';
  elsif candidate_hard_rejected then
    status_value := 'control_only_exact_product_angle_rejected';
    next_step_value := 'choose_control_and_review_rejected_structure';
  else
    status_value := 'ready_for_explicit_apply_or_control';
    next_step_value := 'choose_apply_or_control_for_this_auto_brief';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-outcome-generation-consumption-v1',
    'status', status_value,
    'product_id', product_id_value,
    'scope', case when binding_row.id is null then null else jsonb_build_object(
      'market_category_id', binding_row.category_id,
      'category_binding_id', binding_row.id,
      'category_binding_version', binding_row.binding_version,
      'category_status', category_status_value,
      'platform', platform_value,
      'model', model_value,
      'product_category', product_category_value
    ) end,
    'memory', case when memory_row.id is null then null else jsonb_build_object(
      'memory_version_id', memory_row.id,
      'memory_version', memory_row.memory_version,
      'state', memory_row.state,
      'candidate_id', memory_row.candidate_id,
      'decision_valid', memory_decision_valid
    ) end,
    'candidate', case when candidate_row.id is null then null else jsonb_build_object(
      'candidate_id', candidate_row.id,
      'candidate_version', candidate_row.candidate_version,
      'candidate_hash', candidate_row.candidate_hash,
      'creative_angle', candidate_angle_value,
      'hash_verified', candidate_hash_verified,
      'evidence_current', candidate_evidence_current,
      'live_evidence_current', live_evidence_current,
      'qualification_current', candidate_qualification_current
    ) end,
    'structural_directive', case when candidate_row.id is null then null else
      jsonb_build_object(
        'schema_version', 'research-outcome-generation-structure-v1',
        'creative_angle', candidate_angle_value,
        'hook_patterns', '[]'::jsonb
      ) end,
    'base_policy', jsonb_build_object(
      'version', base_policy ->> 'version',
      'policy_hash', base_policy ->> 'policy_hash',
      'applied', base_policy -> 'applied',
      'generation_allowed', base_policy -> 'generation_allowed',
      'selection_mode', base_policy ->> 'selection_mode',
      'preferred_angle', base_policy ->> 'preferred_angle',
      'product_category', base_policy ->> 'product_category'
    ),
    'permissions', jsonb_build_object(
      'apply_allowed', apply_allowed,
      'control_allowed', control_allowed,
      'generation_consumption_allowed', false
    ),
    'guidance', jsonb_build_object(
      'status', status_value,
      'recommended_next_step', next_step_value,
      'explicit_per_auto_brief', true,
      'automatic_selection', false,
      'generation_consumption_allowed', false,
      'generation_consumption', 'gated_not_wired',
      'effectiveness_status', 'unknown',
      'consumption_blockers', jsonb_build_array(
        'human_approved_research_precedence_unbound',
        'live_evidence_final_revalidation_unbound',
        'final_policy_and_prompt_hash_unbound',
        'paid_start_assignment_unbound'
      ),
      'provider_action', false,
      'spend_action', false,
      'generation_action', false,
      'publication_action', false
    )
  );
end;
$$;

notify pgrst, 'reload schema';

commit;

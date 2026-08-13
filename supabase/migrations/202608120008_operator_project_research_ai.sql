begin;

-- A trained/waived operator may work with research only inside an explicitly
-- granted project.  This is intentionally separate from manager role lists:
-- operators never become organization-wide research managers.
create or replace function
  content_factory_private.qualified_operator_project_research_allowed(
    p_organization_id uuid,
    p_project_id uuid,
    p_profile_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    p_organization_id is not null
    and p_project_id is not null
    and p_profile_id is not null
    and exists (
      select 1
      from content_factory.memberships membership
      join content_factory.organizations organization
        on organization.id = membership.organization_id
       and organization.status = 'active'
      join content_factory.profiles profile
        on profile.id = membership.profile_id
       and profile.status = 'active'
      where membership.organization_id = p_organization_id
        and membership.profile_id = p_profile_id
        and membership.status = 'active'
        and membership.role = 'operator'
    )
    and content_factory_private.generated_media_reviewer_access_allowed(
      p_organization_id,
      p_profile_id
    )
    and content_factory_private.workspace_project_access_allowed(
      p_organization_id,
      p_project_id,
      p_profile_id
    )
$$;

revoke all on function
  content_factory_private.qualified_operator_project_research_allowed(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;

-- Product-research internals predate project scoping.  The mature project
-- wrapper installs this transaction-local value immediately around the inner
-- call.  A direct browser call has no project context and therefore fails.
create or replace function
  content_factory_private.qualified_operator_project_research_context_allowed(
    p_organization_id uuid,
    p_profile_id uuid
  )
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  project_setting text := nullif(btrim(coalesce(
    current_setting('contentengine.project_id', true), ''
  )), '');
  project_id_value uuid;
begin
  if project_setting is null
     or project_setting !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    return false;
  end if;
  project_id_value := project_setting::uuid;
  return content_factory_private.qualified_operator_project_research_allowed(
    p_organization_id,
    project_id_value,
    p_profile_id
  );
exception when invalid_text_representation then
  return false;
end;
$$;

revoke all on function
  content_factory_private.qualified_operator_project_research_context_allowed(
    uuid, uuid
  ) from public, anon, authenticated, service_role;

-- An operator may see and decide only the immutable receipt produced by their
-- own completed run, own draft and own category binding in the exact project.
create or replace function
  content_factory_private.qualified_operator_own_ai_research_receipt_allowed(
    p_organization_id uuid,
    p_receipt_id uuid,
    p_profile_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from content_factory.ai_research_evidence_receipts receipt
    join content_factory.product_research_runs run
      on run.organization_id = receipt.organization_id
     and run.id = receipt.run_id
     and run.project_id = receipt.project_id
     and run.created_by = p_profile_id
     and run.status = 'completed'
     and run.completion_hash = receipt.completion_hash
    join content_factory.research_ai_category_bindings binding
      on binding.organization_id = receipt.organization_id
     and binding.project_id = receipt.project_id
     and binding.run_id = receipt.run_id
     and binding.id = receipt.category_binding_id
     and binding.product_category = receipt.product_category
     and binding.binding_hash = receipt.category_binding_hash
     and binding.bound_by = p_profile_id
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = receipt.organization_id
     and draft.id = receipt.draft_id
     and draft.run_id = receipt.run_id
     and draft.created_by = p_profile_id
     and draft.content_hash = receipt.draft_content_hash
    where receipt.organization_id = p_organization_id
      and receipt.id = p_receipt_id
      and receipt.created_by = p_profile_id
      and draft.product_id = run.product_id
      and content_factory_private.qualified_operator_project_research_allowed(
        receipt.organization_id,
        receipt.project_id,
        p_profile_id
      )
  )
$$;

revoke all on function
  content_factory_private.qualified_operator_own_ai_research_receipt_allowed(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;

-- The API is metered, so the honest action-time contract is an exact current
-- rate card, not a fabricated fixed total.  The request remains limited to one
-- provider POST and 18k output tokens; actual token/search usage determines the
-- final charge.  The snapshot includes both standard and >272k-input long-
-- context rates because GPT-5.5 applies the higher rates to the full session.
-- Rates are from the official OpenAI model/pricing pages checked 2026-08-13.
create or replace function content_factory_private.research_price_contract()
returns jsonb
language sql
immutable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'version', 'openai-api-2026-08-13-gpt-5.5-standard-context-v3',
    'provider', 'openai',
    'provider_key', 'openai_web_search',
    'adapter_version', 'openai-responses-web-search-v1',
    'model', 'gpt-5.5',
    'currency', 'USD',
    'billing_mode', 'metered_actual_usage',
    'service_tier', 'default',
    'input_usd_per_million_tokens', '5.00',
    'output_usd_per_million_tokens', '30.00',
    'long_context_threshold_input_tokens', 272000,
    'long_context_input_usd_per_million_tokens', '10.00',
    'long_context_output_usd_per_million_tokens', '45.00',
    'web_search_usd_per_call', '0.01',
    'max_output_tokens', 18000,
    'max_provider_attempts', 1,
    'fixed_total', false,
    'confirmation_value',
      'OPENAI_GPT_5_5_WEB_RESEARCH_20260813_DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000'
  )
$$;

revoke all on function content_factory_private.research_price_contract()
  from public, anon, authenticated, service_role;

create table if not exists
  content_factory.research_operator_price_confirmations (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    run_id uuid not null,
    confirmed_by uuid not null,
    pricing_version text not null check (
      pricing_version = 'openai-api-2026-08-13-gpt-5.5-standard-context-v3'
    ),
    provider_key text not null check (provider_key = 'openai_web_search'),
    adapter_version text not null check (
      adapter_version = 'openai-responses-web-search-v1'
    ),
    model text not null check (model = 'gpt-5.5'),
    billing_mode text not null check (billing_mode = 'metered_actual_usage'),
    service_tier text not null check (service_tier = 'default'),
    input_usd_micros_per_million_tokens bigint not null check (
      input_usd_micros_per_million_tokens = 5000000
    ),
    output_usd_micros_per_million_tokens bigint not null check (
      output_usd_micros_per_million_tokens = 30000000
    ),
    long_context_threshold_input_tokens integer not null check (
      long_context_threshold_input_tokens = 272000
    ),
    long_context_input_usd_micros_per_million_tokens bigint not null check (
      long_context_input_usd_micros_per_million_tokens = 10000000
    ),
    long_context_output_usd_micros_per_million_tokens bigint not null check (
      long_context_output_usd_micros_per_million_tokens = 45000000
    ),
    web_search_usd_micros_per_call bigint not null check (
      web_search_usd_micros_per_call = 10000
    ),
    max_output_tokens integer not null check (max_output_tokens = 18000),
    max_provider_attempts integer not null check (max_provider_attempts = 1),
    fixed_total boolean not null check (not fixed_total),
    confirmation_value text not null check (
      confirmation_value =
        'OPENAI_GPT_5_5_WEB_RESEARCH_20260813_DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000'
    ),
    price_snapshot_hash text not null check (
      price_snapshot_hash ~ '^[0-9a-f]{64}$'
    ),
    confirmed_at timestamptz not null default clock_timestamp(),
    unique (organization_id, id),
    unique (organization_id, run_id),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, confirmed_by)
      references content_factory.memberships(organization_id, profile_id)
  );

alter table content_factory.research_operator_price_confirmations
  enable row level security;
revoke all on content_factory.research_operator_price_confirmations
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.reject_research_operator_price_confirmation_mutation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'research_operator_price_confirmation_immutable';
end;
$$;

revoke all on function
  content_factory_private.reject_research_operator_price_confirmation_mutation()
  from public, anon, authenticated, service_role;

drop trigger if exists research_operator_price_confirmation_immutable
  on content_factory.research_operator_price_confirmations;
create trigger research_operator_price_confirmation_immutable
before update or delete on
  content_factory.research_operator_price_confirmations
for each row execute function
  content_factory_private.reject_research_operator_price_confirmation_mutation();

create or replace function
  content_factory_private.enforce_operator_research_price_confirmation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (
    select 1
    from content_factory.memberships membership
    where membership.organization_id = new.organization_id
      and membership.profile_id = new.created_by
      and membership.status = 'active'
      and membership.role = 'operator'
  ) and not exists (
    select 1
    from content_factory.research_operator_price_confirmations confirmation
    where confirmation.organization_id = new.organization_id
      and confirmation.project_id = new.project_id
      and confirmation.run_id = new.id
      and confirmation.confirmed_by = new.created_by
  ) then
    raise exception using
      errcode = '23514',
      message = 'operator_research_price_confirmation_required';
  end if;
  return null;
end;
$$;

revoke all on function
  content_factory_private.enforce_operator_research_price_confirmation()
  from public, anon, authenticated, service_role;

drop trigger if exists enforce_operator_research_price_confirmation
  on content_factory.product_research_runs;
create constraint trigger enforce_operator_research_price_confirmation
after insert on content_factory.product_research_runs
deferrable initially deferred
for each row execute function
  content_factory_private.enforce_operator_research_price_confirmation();

-- Allow the qualified operator through every mature start layer while keeping
-- all existing validation, idempotency, quota and media-ownership checks.
do $patch_project_research_start_layers$
declare
  signature_value regprocedure;
  definition_value text;
  patched_value text;
  old_value text;
  new_value text;
begin
  signature_value :=
    'content_factory_private.creator_start_project_research_pre_ai_handoff_v1(jsonb)'::regprocedure;
  definition_value := pg_catalog.pg_get_functiondef(signature_value);
  old_value := $old_base$
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );$old_base$;
  new_value := $new_base$
  organization_id := content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  if content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'operator']
  ) = 'operator' then
    if not content_factory_private.qualified_operator_project_research_allowed(
      organization_id, project_id_value, user_id
    ) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;
  else
    perform content_factory_private.membership_role(
      organization_id, true, array['owner', 'admin', 'producer']
    );
  end if;$new_base$;
  if strpos(definition_value, new_value) = 0 then
    if strpos(definition_value, old_value) = 0 then
      raise exception using
        errcode = '55000',
        message = 'project_research_start_base_topology_changed';
    end if;
    patched_value := replace(definition_value, old_value, new_value);
    if patched_value = definition_value then
      raise exception using
        errcode = '55000', message = 'project_research_start_base_patch_failed';
    end if;
    execute patched_value;
  end if;

  signature_value := 'public.creator_start_product_research(jsonb)'::regprocedure;
  definition_value := pg_catalog.pg_get_functiondef(signature_value);
  old_value := $old_provider_outer$
  user_id := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(delegated_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer']
  );$old_provider_outer$;
  new_value := $new_provider_outer$
  user_id := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(delegated_payload);
  if content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'operator']
  ) = 'operator' then
    if not content_factory_private
      .qualified_operator_project_research_context_allowed(
        organization_id_value, user_id
      ) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;
  else
    perform content_factory_private.membership_role(
      organization_id_value, true, array['owner', 'admin', 'producer']
    );
  end if;$new_provider_outer$;
  if strpos(definition_value, new_value) = 0 then
    if strpos(definition_value, old_value) = 0 then
      raise exception using
        errcode = '55000',
        message = 'product_research_provider_outer_topology_changed';
    end if;
    patched_value := replace(definition_value, old_value, new_value);
    if patched_value = definition_value then
      raise exception using
        errcode = '55000', message = 'product_research_provider_outer_patch_failed';
    end if;
    execute patched_value;
  end if;

  signature_value :=
    'content_factory_private.creator_start_product_research_pre_provider_control(jsonb)'::regprocedure;
  definition_value := pg_catalog.pg_get_functiondef(signature_value);
  old_value := $old_provider_inner$
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );$old_provider_inner$;
  new_value := $new_provider_inner$
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'operator']
  );
  if actor_role = 'operator' then
    if not content_factory_private
      .qualified_operator_project_research_context_allowed(
        organization_id, user_id
      ) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;
  else
    perform content_factory_private.membership_role(
      organization_id, true, array['owner', 'admin', 'producer']
    );
  end if;$new_provider_inner$;
  if strpos(definition_value, new_value) = 0 then
    if strpos(definition_value, old_value) = 0 then
      raise exception using
        errcode = '55000',
        message = 'product_research_provider_inner_topology_changed';
    end if;
    patched_value := replace(definition_value, old_value, new_value);
    if patched_value = definition_value then
      raise exception using
        errcode = '55000', message = 'product_research_provider_inner_patch_failed';
    end if;
    execute patched_value;
  end if;

  signature_value := 'public.creator_start_project_research(jsonb)'::regprocedure;
  definition_value := pg_catalog.pg_get_functiondef(signature_value);
  old_value := $old_exact_outer$
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );$old_exact_outer$;
  new_value := $new_exact_outer$
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );
  if content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'operator']
  ) = 'operator' then
    if not content_factory_private.qualified_operator_project_research_allowed(
      organization_id_value, project_id_value, actor_id_value
    ) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;
  else
    perform content_factory_private.membership_role(
      organization_id_value, true, array['owner', 'admin', 'producer']
    );
  end if;$new_exact_outer$;
  if strpos(definition_value, new_value) = 0 then
    if strpos(definition_value, old_value) = 0 then
      raise exception using
        errcode = '55000',
        message = 'exact_project_research_outer_topology_changed';
    end if;
    patched_value := replace(definition_value, old_value, new_value);
    if patched_value = definition_value then
      raise exception using
        errcode = '55000', message = 'exact_project_research_outer_patch_failed';
    end if;
    execute patched_value;
  end if;
end;
$patch_project_research_start_layers$;

-- Preserve the fully validated mature start and add the exact operator price
-- contract at the final public boundary.  The price-only key never reaches a
-- legacy payload allowlist.
do $preserve_project_research_before_operator_price$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_project_research_pre_operator_price_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_start_project_research(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_start_project_research_missing';
    end if;
    execute 'alter function public.creator_start_project_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.creator_start_project_research(jsonb) '
      || 'rename to creator_start_project_research_pre_operator_price_v1';
  end if;
end;
$preserve_project_research_before_operator_price$;

revoke all on function content_factory_private
  .creator_start_project_research_pre_operator_price_v1(jsonb)
  from public, anon, authenticated, service_role;

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
  actor_id_value uuid;
  actor_role_value text;
  organization_id_value uuid;
  project_id_value uuid;
  paid_authorization_value jsonb;
  raw_idempotency_key_value text;
  operator_idempotency_key_value text;
  exact_video_keys_present boolean := false;
  price_contract_value jsonb :=
    content_factory_private.research_price_contract();
  delegated_payload_value jsonb;
  result_value jsonb;
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  confirmation_hash_value text;
  stored_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );
  actor_role_value := content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer', 'operator']
  );
  if actor_role_value <> 'operator' then
    perform content_factory_private.membership_role(
      organization_id_value, true, array['owner', 'admin', 'producer']
    );
  end if;
  paid_authorization_value := p_payload -> 'paid_analysis_authorization';
  exact_video_keys_present := p_payload ?| array[
    'exact_youtube_source_id', 'exact_youtube_attachment_id',
    'exact_video_evidence_id', 'media_matches_registered_source',
    'source_match_basis'
  ];

  if actor_role_value = 'operator' then
    if not content_factory_private.qualified_operator_project_research_allowed(
      organization_id_value, project_id_value, actor_id_value
    ) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;
    if paid_authorization_value is distinct from price_contract_value then
      raise exception using
        errcode = '22023',
        message = 'research_price_confirmation_required';
    end if;
    raw_idempotency_key_value := content_factory_private.require_text(
      p_payload, 'idempotency_key', 8, 180
    );
    operator_idempotency_key_value := 'operator-research-v1:' ||
      content_factory_private.json_hash(jsonb_build_object(
        'operation', 'creator_start_project_research',
        'organization_id', organization_id_value,
        'project_id', project_id_value,
        'actor_id', actor_id_value,
        'raw_idempotency_key', raw_idempotency_key_value
      ));
  elsif not (actor_role_value = any(array[
    'owner', 'admin', 'producer'
  ])) then
    raise exception using errcode = '42501', message = 'role_not_allowed';
  elsif paid_authorization_value is not null
        and paid_authorization_value is distinct from price_contract_value then
    raise exception using
      errcode = '22023', message = 'research_price_confirmation_invalid';
  end if;

  delegated_payload_value := p_payload - 'paid_analysis_authorization';
  if actor_role_value = 'operator' then
    delegated_payload_value := delegated_payload_value || jsonb_build_object(
      'idempotency_key', operator_idempotency_key_value
    );
  end if;
  result_value := content_factory_private
    .creator_start_project_research_pre_operator_price_v1(
      delegated_payload_value
    );
  begin
    run_id_value := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end;
  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.project_id = project_id_value
    and run.id = run_id_value
    and (
      actor_role_value <> 'operator'
      or run.created_by = actor_id_value
    )
  for share;
  if run_row.id is null then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end if;

  if actor_role_value = 'operator' then
    if not exists (
      select 1
      from content_factory.research_execution_authorizations authorization_entry
      where authorization_entry.organization_id = organization_id_value
        and authorization_entry.run_id = run_id_value
        and authorization_entry.authorized_by = actor_id_value
        and authorization_entry.authorization_kind =
          'explicit_paid_analysis'
        and authorization_entry.paid_analysis_ack
        and authorization_entry.provider_key = 'openai_web_search'
        and authorization_entry.adapter_version =
          'openai-responses-web-search-v1'
        and authorization_entry.run_request_hash = run_row.request_hash
        and authorization_entry.max_provider_attempts = 1
        and not authorization_entry.automatic_fallback_allowed
        and authorization_entry.reason_code = 'user_confirmed_paid_analysis'
    ) or (
      exists (
        select 1
        from content_factory.research_run_provider_bindings provider_binding
        where provider_binding.organization_id = organization_id_value
          and provider_binding.run_id = run_id_value
      )
      and not exists (
        -- A committed exact replay may already have the single provider
        -- attempt created by the subsequent explicit Edge action.  It is safe
        -- only when the immutable action-time confirmation from the original
        -- start and the pinned provider/model binding both still match.
        select 1
        from content_factory.research_run_provider_bindings provider_binding
        join content_factory.research_operator_price_confirmations confirmation
          on confirmation.organization_id = provider_binding.organization_id
         and confirmation.project_id = project_id_value
         and confirmation.run_id = provider_binding.run_id
         and confirmation.confirmed_by = actor_id_value
        where provider_binding.organization_id = organization_id_value
          and provider_binding.run_id = run_id_value
          and provider_binding.provider_key = 'openai_web_search'
          and provider_binding.adapter_version =
            'openai-responses-web-search-v1'
          and provider_binding.model = 'gpt-5.5'
          and provider_binding.attempt_number = 1
          and confirmation.pricing_version =
            price_contract_value ->> 'version'
          and confirmation.confirmation_value =
            price_contract_value ->> 'confirmation_value'
      )
    ) or not exists (
      select 1
      from content_factory.research_ai_category_bindings binding
      where binding.organization_id = organization_id_value
        and binding.project_id = project_id_value
        and binding.run_id = run_id_value
        and binding.bound_by = actor_id_value
        and binding.binding_kind = 'explicit_paid_start'
    ) then
      raise exception using
        errcode = '55000',
        message = 'operator_project_research_lineage_invalid';
    end if;
    if exact_video_keys_present and not exists (
      select 1
      from content_factory.research_exact_youtube_research_bindings exact_binding
      join content_factory.research_exact_youtube_sources source
        on source.organization_id = exact_binding.organization_id
       and source.project_id = exact_binding.project_id
       and source.id = exact_binding.source_id
       and source.requested_by = actor_id_value
      join content_factory.research_exact_youtube_media_attachments attachment
        on attachment.organization_id = exact_binding.organization_id
       and attachment.project_id = exact_binding.project_id
       and attachment.id = exact_binding.attachment_id
       and attachment.source_id = exact_binding.source_id
       and attachment.attached_by = actor_id_value
      join content_factory.media_objects media
        on media.organization_id = exact_binding.organization_id
       and media.project_id = exact_binding.project_id
       and media.id = exact_binding.media_object_id
       and media.owner_id = actor_id_value
      where exact_binding.organization_id = organization_id_value
        and exact_binding.project_id = project_id_value
        and exact_binding.run_id = run_id_value
        and exact_binding.bound_by = actor_id_value
    ) then
      raise exception using
        errcode = '42501',
        message = 'operator_exact_research_lineage_not_allowed';
    end if;
    confirmation_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'operator-project-research-price-confirmation-v1',
        'organization_id', organization_id_value,
        'project_id', project_id_value,
        'run_id', run_id_value,
        'confirmed_by', actor_id_value,
        'pricing', price_contract_value
      )
    );
    insert into content_factory.research_operator_price_confirmations (
      organization_id, project_id, run_id, confirmed_by,
      pricing_version, provider_key, adapter_version, model,
      billing_mode, service_tier, input_usd_micros_per_million_tokens,
      output_usd_micros_per_million_tokens,
      long_context_threshold_input_tokens,
      long_context_input_usd_micros_per_million_tokens,
      long_context_output_usd_micros_per_million_tokens,
      web_search_usd_micros_per_call, max_output_tokens,
      max_provider_attempts, fixed_total, confirmation_value,
      price_snapshot_hash
    ) values (
      organization_id_value, project_id_value, run_id_value, actor_id_value,
      price_contract_value ->> 'version',
      price_contract_value ->> 'provider_key',
      price_contract_value ->> 'adapter_version',
      price_contract_value ->> 'model',
      price_contract_value ->> 'billing_mode',
      price_contract_value ->> 'service_tier',
      5000000, 30000000, 272000, 10000000, 45000000,
      10000, 18000, 1, false,
      price_contract_value ->> 'confirmation_value', confirmation_hash_value
    ) on conflict (organization_id, run_id) do nothing;

    select confirmation.price_snapshot_hash into stored_hash_value
    from content_factory.research_operator_price_confirmations confirmation
    where confirmation.organization_id = organization_id_value
      and confirmation.project_id = project_id_value
      and confirmation.run_id = run_id_value
      and confirmation.confirmed_by = actor_id_value
      and confirmation.confirmation_value =
        price_contract_value ->> 'confirmation_value';
    if stored_hash_value is distinct from confirmation_hash_value then
      raise exception using
        errcode = '23505',
        message = 'research_price_confirmation_conflict';
    end if;
  end if;

  return result_value || jsonb_build_object(
    'project_id', project_id_value,
    'research_price', price_contract_value,
    'price_confirmation_recorded', actor_role_value = 'operator'
  );
end;
$$;

revoke all on function public.creator_start_project_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_start_project_research(jsonb)
  to authenticated;

-- Status polling is also the authorization boundary used by the provider
-- worker.  Guard an operator's exact run before the preserved implementation
-- can claim or otherwise observe it; managers keep the mature path unchanged.
do $preserve_project_research_status_before_operator_own_v1$
begin
  if to_regprocedure(
    'content_factory_private.creator_project_research_status_pre_operator_own_v1(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.creator_project_research_status(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883', message = 'creator_project_research_status_missing';
    end if;
    execute 'alter function public.creator_project_research_status(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function content_factory_private'
      || '.creator_project_research_status(jsonb) rename to '
      || 'creator_project_research_status_pre_operator_own_v1';
  end if;
end;
$preserve_project_research_status_before_operator_own_v1$;

revoke all on function content_factory_private
  .creator_project_research_status_pre_operator_own_v1(jsonb)
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
  actor_id_value uuid;
  actor_role_value text;
  organization_id_value uuid;
  project_id_value uuid;
  run_id_value uuid;
  result_value jsonb;
  research_context_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  actor_role_value := content_factory_private.membership_role(
    organization_id_value, false, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  run_id_value := content_factory_private.require_uuid(
    p_payload, 'run_id'
  );

  if actor_role_value = 'operator' then
    perform content_factory_private.require_workspace_project_access(
      organization_id_value, project_id_value, actor_id_value
    );
    if not content_factory_private.qualified_operator_project_research_allowed(
      organization_id_value, project_id_value, actor_id_value
    ) or not exists (
      select 1
      from content_factory.product_research_runs run
      where run.organization_id = organization_id_value
        and run.project_id = project_id_value
        and run.id = run_id_value
        and run.created_by = actor_id_value
    ) then
      raise exception using
        errcode = '42501', message = 'research_run_not_allowed';
    end if;
  end if;

  result_value := content_factory_private
    .creator_project_research_status_pre_operator_own_v1(p_payload);

  -- The browser may open any exact own run from the durable Files projection,
  -- not only the newest one from project_flow.  Return a minimized,
  -- authoritative route context for the exact status row so the client can
  -- validate project/ownership and build the matching receipt link without
  -- treating a URL or sessionStorage value as authorization.
  select jsonb_strip_nulls(jsonb_build_object(
    'run_id', run.id,
    'project_id', run.project_id,
    'ownership', case
      when run.created_by = actor_id_value then 'own'
      else 'project'
    end,
    'product_category', coalesce(
      receipt.product_category, binding.product_category
    ),
    'ai_receipt', case when receipt.id is null then null else
      jsonb_build_object(
        'receipt_id', receipt.id,
        'status', receipt.status
      )
    end
  )) into research_context_value
  from content_factory.product_research_runs run
  left join content_factory.research_ai_category_bindings binding
    on binding.organization_id = run.organization_id
   and binding.project_id = run.project_id
   and binding.run_id = run.id
  left join content_factory.ai_research_evidence_receipts receipt
    on receipt.organization_id = run.organization_id
   and receipt.project_id = run.project_id
   and receipt.run_id = run.id
  where run.organization_id = organization_id_value
    and run.project_id = project_id_value
    and run.id = run_id_value;
  if research_context_value is null then
    raise exception using
      errcode = '55000', message = 'project_research_result_mismatch';
  end if;

  return result_value || jsonb_build_object(
    'research_context', research_context_value
  );
end;
$$;

revoke all on function public.creator_project_research_status(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_project_research_status(jsonb)
  to authenticated;

-- Apply exact own-receipt filtering before both LIMIT clauses and extend the
-- decision capability only for the same qualified operator/project boundary.
do $patch_ai_research_queue_for_operator$
declare
  signature_value constant regprocedure :=
    'public.creator_ai_research_training_queue(jsonb)'::regprocedure;
  definition_value text := pg_catalog.pg_get_functiondef(signature_value);
  patched_value text;
  old_value text;
  new_value text;
begin
  patched_value := definition_value;

  old_value := $old_queue_payload_allowlist$
    'organization_id', 'project_id', 'product_category', 'limit'
  ]::text[]$old_queue_payload_allowlist$;
  new_value := $new_queue_payload_allowlist$
    'organization_id', 'project_id', 'product_category', 'limit', 'receipt_id'
  ]::text[]$new_queue_payload_allowlist$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_payload_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_queue_receipt_declare$
  project_id_value uuid;
  category_value text;$old_queue_receipt_declare$;
  new_value := $new_queue_receipt_declare$
  project_id_value uuid;
  receipt_id_value uuid;
  category_value text;$new_queue_receipt_declare$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_declare_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  -- Operators must enter the queue through the same explicit project ACL and
  -- current qualification boundary used by the project flow.  The mature
  -- manager branch keeps its existing project-membership semantics.
  old_value := $old_queue_project_gate$
  if p_payload ? 'project_id' then
    project_id_value := content_factory_private.require_uuid(
      p_payload,
      'project_id'
    );
    perform content_factory_private.require_workspace_project(
      organization_id_value,
      project_id_value
    );
  end if;$old_queue_project_gate$;
  new_value := $new_queue_project_gate$
  if p_payload ? 'project_id' then
    project_id_value := content_factory_private.require_uuid(
      p_payload,
      'project_id'
    );
    if actor_role_value = 'operator' then
      perform content_factory_private.require_workspace_project_access(
        organization_id_value, project_id_value, user_id
      );
      if not content_factory_private
        .qualified_operator_project_research_allowed(
          organization_id_value, project_id_value, user_id
        ) then
        raise exception using errcode = '42501', message = 'role_not_allowed';
      end if;
    else
      perform content_factory_private.require_workspace_project(
        organization_id_value,
        project_id_value
      );
    end if;
  elsif actor_role_value = 'operator' then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;$new_queue_project_gate$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_project_gate_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_queue_receipt_parse$
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );$old_queue_receipt_parse$;
  new_value := $new_queue_receipt_parse$
  if p_payload ? 'receipt_id' then
    receipt_id_value := content_factory_private.require_uuid(
      p_payload, 'receipt_id'
    );
  end if;
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );$new_queue_receipt_parse$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_receipt_parse_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  -- The browser treats own-only mode as a row-level contract, not merely a
  -- top-level capability.  Mark each delivered operator row explicitly while
  -- leaving the mature manager payload byte-for-byte equivalent after
  -- jsonb_strip_nulls removes the null marker.
  old_value := $old_queue_ownership$
      'receipt_id', receipt.id,
      'receipt_hash', receipt.receipt_hash,$old_queue_ownership$;
  new_value := $new_queue_ownership$
      'receipt_id', receipt.id,
      'ownership', case
        when actor_role_value = 'operator' then 'own'
        else null
      end,
      'receipt_hash', receipt.receipt_hash,$new_queue_ownership$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_ownership_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_learned_ownership$
      'selection_id', selection.id,
      'selection_hash', selection.selection_hash,$old_learned_ownership$;
  new_value := $new_learned_ownership$
      'selection_id', selection.id,
      'ownership', case
        when actor_role_value = 'operator' then 'own'
        else null
      end,
      'selection_hash', selection.selection_hash,$new_learned_ownership$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_learned_ownership_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_queue_filter$
      and receipt.product_category = category_value
      and receipt.status = 'awaiting_human_review'$old_queue_filter$;
  new_value := $new_queue_filter$
      and receipt.product_category = category_value
      and (receipt_id_value is null or receipt.id = receipt_id_value)
      and (
        actor_role_value <> 'operator'
        or (
          receipt.created_by = user_id
          and run.created_by = user_id
          and content_factory_private
            .qualified_operator_own_ai_research_receipt_allowed(
              organization_id_value, receipt.id, user_id
            )
        )
      )
      and receipt.status = 'awaiting_human_review'$new_queue_filter$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_filter_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_learned_filter$
      and selection.product_category = category_value
    order by selection.event_cursor desc, selection.id desc$old_learned_filter$;
  new_value := $new_learned_filter$
      and selection.product_category = category_value
      and (
        receipt_id_value is null
        or selection.receipt_id = receipt_id_value
      )
      and (
        actor_role_value <> 'operator'
        or (
          selection.selected_by = user_id
          and run.created_by = user_id
          and content_factory_private
            .qualified_operator_own_ai_research_receipt_allowed(
              organization_id_value, selection.receipt_id, user_id
            )
        )
      )
    order by selection.event_cursor desc, selection.id desc$new_learned_filter$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_learned_filter_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_queue_caps$
      'can_read', true,
      'can_decide', actor_role_value in ('owner', 'admin', 'producer'),
      'can_edit_recommendations',
        actor_role_value in ('owner', 'admin', 'producer')$old_queue_caps$;
  new_value := $new_queue_caps$
      'can_read', true,
      'can_decide',
        actor_role_value in ('owner', 'admin', 'producer')
        or (
          actor_role_value = 'operator'
          and project_id_value is not null
          and content_factory_private
            .qualified_operator_project_research_allowed(
              organization_id_value, project_id_value, user_id
            )
        ),
      'can_edit_recommendations',
        actor_role_value in ('owner', 'admin', 'producer')
        or (
          actor_role_value = 'operator'
          and project_id_value is not null
          and content_factory_private
            .qualified_operator_project_research_allowed(
              organization_id_value, project_id_value, user_id
            )
        ),
      'operator_own_receipts_only', actor_role_value = 'operator'$new_queue_caps$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_capabilities_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  if patched_value = definition_value then
    if strpos(definition_value, 'operator_own_receipts_only') = 0
       or strpos(definition_value, '''ownership''') = 0
       or strpos(definition_value, 'receipt_id_value is null') = 0 then
      raise exception using
        errcode = '55000', message = 'ai_research_queue_operator_patch_failed';
    end if;
  else
    execute patched_value;
  end if;
end;
$patch_ai_research_queue_for_operator$;

-- The exact-source queue is a separate authenticated RPC loaded by the AI
-- bootstrap.  Keep its operator view actor-scoped before LIMIT as defence in
-- depth even though the operator UI does not mount the project-wide adapter.
do $patch_exact_youtube_source_queue_for_operator$
declare
  signature_value constant regprocedure :=
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure;
  definition_value text := pg_catalog.pg_get_functiondef(signature_value);
  patched_value text := definition_value;
  old_value text;
  new_value text;
begin
  old_value := $old_exact_declare$
  actor_id_value uuid;
  organization_id_value uuid;$old_exact_declare$;
  new_value := $new_exact_declare$
  actor_id_value uuid;
  actor_role_value text;
  organization_id_value uuid;$new_exact_declare$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_declare_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_exact_role$
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );$old_exact_role$;
  new_value := $new_exact_role$
  actor_role_value := content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );$new_exact_role$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_role_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_exact_project_gate$
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    actor_id_value
  );$old_exact_project_gate$;
  new_value := $new_exact_project_gate$
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    actor_id_value
  );
  if actor_role_value = 'operator'
     and not content_factory_private
       .qualified_operator_project_research_allowed(
         organization_id_value, project_id_value, actor_id_value
       ) then
    raise exception using errcode = '42501', message = 'role_not_allowed';
  end if;$new_exact_project_gate$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_project_gate_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_exact_latest$
        and binding.source_id = source.id
        and binding.attachment_id = attachment.id
      order by binding.bound_at desc, binding.id desc$old_exact_latest$;
  new_value := $new_exact_latest$
        and binding.source_id = source.id
        and binding.attachment_id = attachment.id
        and (
          actor_role_value <> 'operator'
          or (
            run.created_by = actor_id_value
            and (
              receipt.id is null
              or content_factory_private
                .qualified_operator_own_ai_research_receipt_allowed(
                  source.organization_id, receipt.id, actor_id_value
                )
            )
            and (
              selection.id is null
              or selection.selected_by = actor_id_value
            )
          )
        )
      order by binding.bound_at desc, binding.id desc$new_exact_latest$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_latest_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_exact_effective$
        and binding.source_id = source.id
        and binding.attachment_id = attachment.id
      order by selection.selected_at desc, selection.event_cursor desc,$old_exact_effective$;
  new_value := $new_exact_effective$
        and binding.source_id = source.id
        and binding.attachment_id = attachment.id
        and (
          actor_role_value <> 'operator'
          or (
            selection.selected_by = actor_id_value
            and content_factory_private
              .qualified_operator_own_ai_research_receipt_allowed(
                source.organization_id, receipt.id, actor_id_value
              )
          )
        )
      order by selection.selected_at desc, selection.event_cursor desc,$new_exact_effective$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_effective_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  old_value := $old_exact_source_filter$
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
    order by source.created_at desc, source.id desc
    limit limit_value$old_exact_source_filter$;
  new_value := $new_exact_source_filter$
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
      and (
        actor_role_value <> 'operator'
        or source.requested_by = actor_id_value
      )
    order by source.created_at desc, source.id desc
    limit limit_value$new_exact_source_filter$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_filter_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  -- Files resolves the immutable attached media id, never the source ledger
  -- id.  Keep the deep link absent until an attachment exists.
  old_value := $old_exact_files_link$
        'files_deep_link', '#/workspace/board?project_id='
          || source.project_id::text
          || '&youtube_source=' || source.id::text$old_exact_files_link$;
  new_value := $new_exact_files_link$
        'files_deep_link', case when media.id is null then null else
          '#/workspace/board?project_id=' || source.project_id::text
          || '&media=' || media.id::text
        end$new_exact_files_link$;
  if strpos(patched_value, new_value) = 0 then
    if strpos(patched_value, old_value) = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_files_link_changed';
    end if;
    patched_value := replace(patched_value, old_value, new_value);
  end if;

  if patched_value = definition_value then
    if strpos(definition_value, 'source.requested_by = actor_id_value') = 0
       or strpos(definition_value,
         'qualified_operator_own_ai_research_receipt_allowed') = 0 then
      raise exception using
        errcode = '55000', message = 'exact_source_queue_patch_failed';
    end if;
  else
    execute patched_value;
  end if;
end;
$patch_exact_youtube_source_queue_for_operator$;

-- The project wrapper already verifies exact project/receipt lineage.  Patch
-- the preserved append-only decision implementation so an operator must also
-- own that exact receipt before command replay or mutation can proceed.
do $patch_ai_research_decision_for_operator$
declare
  signature_value constant regprocedure :=
    'content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(jsonb)'::regprocedure;
  definition_value text := pg_catalog.pg_get_functiondef(signature_value);
  patched_value text;
  old_value constant text := $old_decision_role$
  perform content_factory_private.membership_role(
    organization_id_value,
    false,
    array['owner', 'admin', 'producer']
  );$old_decision_role$;
  new_value constant text := $new_decision_role$
  if not (
    content_factory_private.membership_role(
      organization_id_value, false, null
    ) = any(array['owner', 'admin', 'producer'])
  ) and not content_factory_private
    .qualified_operator_own_ai_research_receipt_allowed(
      organization_id_value,
      content_factory_private.require_uuid(p_payload, 'receipt_id'),
      user_id
    ) then
    raise exception using errcode = '42501', message = 'role_not_allowed';
  end if;$new_decision_role$;
begin
  if strpos(definition_value, new_value) > 0 then
    return;
  end if;
  if strpos(definition_value, old_value) = 0
     or strpos(definition_value, 'begin_command(') = 0 then
    raise exception using
      errcode = '55000', message = 'ai_research_decision_topology_changed';
  end if;
  patched_value := replace(definition_value, old_value, new_value);
  if patched_value = definition_value
     or strpos(patched_value, new_value) = 0 then
    raise exception using
      errcode = '55000', message = 'ai_research_decision_operator_patch_failed';
  end if;
  execute patched_value;
end;
$patch_ai_research_decision_for_operator$;

-- The mature project wrapper performs the exact receipt/project checks, but
-- its private delegate supports idempotent replay.  Put current operator
-- qualification and immutable own-receipt lineage in front of that replay.
do $preserve_ai_research_decision_before_operator_own_v1$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_decide_ai_research_training_pre_operator_own_v1(jsonb)'
  ) is null then
    if to_regprocedure(
      'public.contentengine_decide_ai_research_training(jsonb)'
    ) is null then
      raise exception using
        errcode = '42883',
        message = 'contentengine_ai_research_training_decision_missing';
    end if;
    execute 'alter function '
      || 'public.contentengine_decide_ai_research_training(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function content_factory_private'
      || '.contentengine_decide_ai_research_training(jsonb) rename to '
      || 'contentengine_decide_ai_research_training_pre_operator_own_v1';
  end if;
end;
$preserve_ai_research_decision_before_operator_own_v1$;

revoke all on function content_factory_private
  .contentengine_decide_ai_research_training_pre_operator_own_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.contentengine_decide_ai_research_training(
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
  actor_id_value uuid;
  actor_role_value text;
  organization_id_value uuid;
  project_id_value uuid;
  receipt_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  receipt_id_value := content_factory_private.require_uuid(
    p_payload, 'receipt_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );
  actor_role_value := content_factory_private.membership_role(
    organization_id_value, false, null
  );

  if actor_role_value = 'operator' then
    if not content_factory_private
      .qualified_operator_own_ai_research_receipt_allowed(
        organization_id_value, receipt_id_value, actor_id_value
      ) or not exists (
        select 1
        from content_factory.ai_research_evidence_receipts receipt
        where receipt.organization_id = organization_id_value
          and receipt.project_id = project_id_value
          and receipt.id = receipt_id_value
          and receipt.created_by = actor_id_value
      ) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;
  elsif not (actor_role_value = any(array[
    'owner', 'admin', 'producer'
  ])) then
    raise exception using errcode = '42501', message = 'role_not_allowed';
  end if;

  return content_factory_private
    .contentengine_decide_ai_research_training_pre_operator_own_v1(
      p_payload
    );
end;
$$;

revoke all on function
  public.contentengine_decide_ai_research_training(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_decide_ai_research_training(jsonb)
  to authenticated, service_role;

-- Project flow is the authoritative capability carrier already loaded on
-- project selection.  Add own-run recovery and the exact metered rate card
-- without changing the shared project snapshot itself.
do $preserve_project_flow_before_operator_research$
begin
  if to_regprocedure(
    'content_factory_private.creator_project_flow_pre_operator_research_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_project_flow(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_project_flow_missing';
    end if;
    execute 'alter function public.creator_project_flow(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function content_factory_private.creator_project_flow(jsonb) '
      || 'rename to creator_project_flow_pre_operator_research_v1';
  end if;
end;
$preserve_project_flow_before_operator_research$;

revoke all on function content_factory_private
  .creator_project_flow_pre_operator_research_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_project_flow(
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
  actor_id_value uuid;
  actor_role_value text;
  profile_status_value text;
  organization_id_value uuid;
  project_id_value uuid;
  snapshot_value jsonb;
  operator_allowed boolean := false;
  latest_run_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id_value := auth.uid();
  if actor_id_value is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  if not exists (
    select 1
    from auth.users auth_user
    where auth_user.id = actor_id_value
      and auth_user.email is not null
  ) then
    raise exception using
      errcode = '42501', message = 'verified_email_required';
  end if;
  select profile.status
    into profile_status_value
  from content_factory.profiles profile
  where profile.id = actor_id_value;
  if profile_status_value is not null
     and profile_status_value <> 'active' then
    raise exception using
      errcode = '42501', message = 'profile_not_active';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  actor_role_value := content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  if nullif(btrim(coalesce(p_payload ->> 'project_id', '')), '') is not null then
    project_id_value := content_factory_private.require_uuid(
      p_payload, 'project_id'
    );
  end if;

  snapshot_value := content_factory_private
    .creator_project_flow_pre_operator_research_v1(p_payload);
  if project_id_value is not null then
    perform content_factory_private.require_workspace_project_access(
      organization_id_value, project_id_value, actor_id_value
    );
    operator_allowed := actor_role_value = 'operator'
      and content_factory_private.qualified_operator_project_research_allowed(
        organization_id_value, project_id_value, actor_id_value
      );
    select jsonb_strip_nulls(jsonb_build_object(
      'run_id', run.id,
      'status', run.status,
      'product_category', binding.product_category,
      'created_at', run.created_at,
      'completed_at', run.finished_at,
      'ai_receipt', case when receipt.id is null then null else
        jsonb_build_object(
          'receipt_id', receipt.id,
          'status', receipt.status
        )
      end,
      'deep_link', '#/workspace/research?project_id='
        || run.project_id::text || '&run=' || run.id::text
    )) into latest_run_value
    from content_factory.product_research_runs run
    left join content_factory.research_ai_category_bindings binding
      on binding.organization_id = run.organization_id
     and binding.project_id = run.project_id
     and binding.run_id = run.id
     and binding.bound_by = run.created_by
    left join content_factory.ai_research_evidence_receipts receipt
      on receipt.organization_id = run.organization_id
     and receipt.project_id = run.project_id
     and receipt.run_id = run.id
     and receipt.created_by = run.created_by
     and receipt.category_binding_id = binding.id
     and receipt.product_category = binding.product_category
     and receipt.category_binding_hash = binding.binding_hash
     and receipt.completion_hash = run.completion_hash
    where run.organization_id = organization_id_value
      and run.project_id = project_id_value
      and run.created_by = actor_id_value
    order by run.created_at desc, run.id desc
    limit 1;
  end if;

  return snapshot_value || jsonb_build_object(
    'capabilities', coalesce(
      snapshot_value -> 'capabilities', '{}'::jsonb
    ) || jsonb_build_object(
      'product_research', jsonb_build_object(
        'can_open',
          actor_role_value in ('owner', 'admin', 'producer')
          or operator_allowed,
        'can_start_paid_own',
          actor_role_value in ('owner', 'admin', 'producer')
          or operator_allowed,
        'can_read_own',
          actor_role_value in ('owner', 'admin', 'producer')
          or operator_allowed,
        'can_manage', actor_role_value in ('owner', 'admin', 'producer'),
        'run_scope', case
          when actor_role_value in ('owner', 'admin', 'producer')
            then 'project'
          when operator_allowed then 'own'
          else 'none'
        end
      ),
      'ai_research', jsonb_build_object(
        'can_open',
          actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
          or operator_allowed,
        'can_read_receipt',
          actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
          or operator_allowed,
        'can_decide_own',
          actor_role_value in ('owner', 'admin', 'producer')
          or operator_allowed,
        'can_edit_own',
          actor_role_value in ('owner', 'admin', 'producer')
          or operator_allowed,
        'can_view_exact_youtube_sources',
          actor_role_value in ('owner', 'admin', 'producer', 'reviewer'),
        'receipt_scope', case
          when actor_role_value in ('owner', 'admin', 'producer', 'reviewer')
            then 'project'
          when operator_allowed then 'own'
          else 'none'
        end
      )
    ),
    'research_context', coalesce(
      snapshot_value -> 'research_context', '{}'::jsonb
    ) || jsonb_build_object(
      'latest_own_run', latest_run_value,
      'paid_tariff', case
        when actor_role_value in ('owner', 'admin', 'producer')
          or operator_allowed
        then content_factory_private.research_price_contract()
        else null
      end
    )
  );
end;
$$;

revoke all on function public.creator_project_flow(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_project_flow(jsonb)
  to authenticated;

-- Assert the installed topology, not just the migration text.  Every private
-- delegate stays private and both operator mutations are guarded before the
-- mature begin_command paths.
do $verify_operator_project_research_topology$
declare
  queue_definition text := pg_catalog.pg_get_functiondef(
    'public.creator_ai_research_training_queue(jsonb)'::regprocedure
  );
  exact_source_definition text := pg_catalog.pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  );
  decision_definition text := pg_catalog.pg_get_functiondef(
    'content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(jsonb)'::regprocedure
  );
  decision_outer_definition text := pg_catalog.pg_get_functiondef(
    'public.contentengine_decide_ai_research_training(jsonb)'::regprocedure
  );
  project_start_definition text := pg_catalog.pg_get_functiondef(
    'public.creator_start_project_research(jsonb)'::regprocedure
  );
  project_status_definition text := pg_catalog.pg_get_functiondef(
    'public.creator_project_research_status(jsonb)'::regprocedure
  );
begin
  if strpos(queue_definition,
       'qualified_operator_own_ai_research_receipt_allowed') = 0
     or strpos(queue_definition, 'operator_own_receipts_only') = 0
     or strpos(queue_definition, '''ownership''') = 0
     or strpos(queue_definition, '''ownership''') >
       strpos(queue_definition, 'limit limit_value')
     or strpos(queue_definition,
       'require_workspace_project_access') = 0
     or strpos(queue_definition,
       'require_workspace_project_access') >
       strpos(queue_definition, 'select coalesce(jsonb_agg')
     or strpos(queue_definition, 'selection.selected_by = user_id') = 0
     or strpos(exact_source_definition,
       'source.requested_by = actor_id_value') = 0
     or strpos(exact_source_definition,
       'source.requested_by = actor_id_value') >
       strpos(exact_source_definition, 'limit limit_value')
     or strpos(exact_source_definition,
       'qualified_operator_own_ai_research_receipt_allowed') = 0
     or strpos(exact_source_definition,
       'qualified_operator_project_research_allowed') = 0
     or strpos(exact_source_definition,
       'qualified_operator_project_research_allowed') >
       strpos(exact_source_definition,
         'select coalesce')
     or strpos(decision_definition,
       'qualified_operator_own_ai_research_receipt_allowed') = 0
     or strpos(decision_definition,
       'qualified_operator_own_ai_research_receipt_allowed') >
       strpos(decision_definition, 'begin_command(')
     or strpos(decision_outer_definition,
       'qualified_operator_own_ai_research_receipt_allowed') = 0
     or strpos(decision_outer_definition,
       'qualified_operator_own_ai_research_receipt_allowed') >
       strpos(decision_outer_definition,
         'contentengine_decide_ai_research_training_pre_operator_own_v1')
     or strpos(project_start_definition,
       'research_price_confirmation_required') = 0
     or strpos(project_start_definition,
       '''paid_analysis_authorization''') = 0
     or strpos(project_start_definition, '''actor_id''') = 0
     or strpos(project_start_definition,
       'creator_start_project_research_pre_operator_price_v1') = 0
     or strpos(project_status_definition,
       'qualified_operator_project_research_allowed') = 0
     or strpos(project_status_definition,
       'qualified_operator_project_research_allowed') >
       strpos(project_status_definition,
         'creator_project_research_status_pre_operator_own_v1')
     or has_function_privilege(
       'authenticated',
       'content_factory_private.creator_project_research_status_pre_operator_own_v1(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'authenticated',
       'content_factory_private.contentengine_decide_ai_research_training_pre_operator_own_v1(jsonb)',
       'execute'
     ) then
    raise exception using
      errcode = '55000',
      message = 'operator_project_research_topology_invalid';
  end if;
end;
$verify_operator_project_research_topology$;

notify pgrst, 'reload schema';

commit;

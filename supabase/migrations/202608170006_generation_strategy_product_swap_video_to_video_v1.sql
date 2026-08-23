begin;

-- Product Swap paid dispatch died on a fictional endpoint: Runway has no
-- /v1/recipes/* API (verified in the live Request History endpoint filter:
-- text_to_image, text_to_video, image_to_video, video_to_video,
-- character_performance, text_to_speech, organization).  Product Swap now
-- runs on the real video_to_video endpoint (Gen-4 Aleph): edit the confirmed
-- source MP4 by prompt with image references.  The edge catalog
-- (generation-strategy-catalog.js), the recipe adapter
-- (generation-recipe-adapters.js) and these SQL policy functions must all
-- return '/v1/video_to_video' for product_swap; the dispatch validates the
-- envelope path against all three.  Only the two policy functions embedding
-- the provider path are re-created here, with their latest 202608130007
-- bodies; product_ugc and product_ad keep their paths (Stage 2 scope).
-- Pricing is intentionally untouched: the internal 212+36/s price stays the
-- spend-contour authority until the first successful Aleph render is costed.

create or replace function public.system_generation_strategy_catalog_policy(
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
  organization_active_value boolean := false;
  sql_provider_gate_value boolean := false;
  chain_installed_value boolean := false;
  enabled_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['version', 'organization_id']::text[] <> '{}'::jsonb
     or not p_payload ?& array['version', 'organization_id']::text[]
     or p_payload ->> 'version' <>
       'generation-strategy-catalog-policy-request-v1' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_catalog_policy_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  select exists (
    select 1 from content_factory.organizations organization
    where organization.id = organization_id_value
      and organization.status = 'active'
  ) into organization_active_value;
  sql_provider_gate_value := organization_active_value
    and content_factory_private.generation_provider_launch_enabled(
      organization_id_value, 'runway', 'gen4_turbo'
    );
  chain_installed_value := content_factory_private
    .generation_strategy_execution_chain_installed();
  enabled_value := organization_active_value and sql_provider_gate_value
    and chain_installed_value;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-catalog-policy-response-v1',
    'execution_capabilities', jsonb_build_object(
      'viral_avatar_ugc', jsonb_build_object(
        'enabled', enabled_value,
        'catalog_version', '2026-08-14.v1',
        'strategy_id', 'viral_avatar_ugc',
        'provider', 'runway',
        'recipe', 'product_ugc',
        'recipe_version', '2026-06',
        'provider_path', '/v1/recipes/product_ugc',
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
      ),
      'viral_product_swap', jsonb_build_object(
        'enabled', enabled_value,
        'catalog_version', '2026-08-14.v1',
        'strategy_id', 'viral_product_swap',
        'provider', 'runway',
        'recipe', 'product_swap',
        'recipe_version', '2026-06',
        'provider_path', '/v1/video_to_video',
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
      ),
      'viral_rebuild', jsonb_build_object(
        'enabled', enabled_value,
        'catalog_version', '2026-08-14.v1',
        'strategy_id', 'viral_rebuild',
        'provider', 'runway',
        'recipe', 'product_ad',
        'recipe_version', '2026-06',
        'provider_path', '/v1/recipes/product_ad',
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
      )
    ),
    'checks', jsonb_build_object(
      'organization_active', organization_active_value,
      'sql_provider_configuration_enabled', sql_provider_gate_value,
      'execution_chain_installed', chain_installed_value,
      'edge_secret_check_required_at_preflight', true
    ),
    'select_enabled', enabled_value,
    'preflight_enabled', enabled_value,
    'paid_start_authorized', false,
    'contract', jsonb_build_object(
      'read_only', true,
      'server_authoritative', true,
      'provider_call_started', false,
      'receipt_required_for_paid_start', true,
      'catalog_policy_is_not_paid_authority', true
    )
  );
end;
$$;

revoke all on function
  public.system_generation_strategy_catalog_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_generation_strategy_catalog_policy(jsonb)
  to service_role;

create or replace function public.system_generation_strategy_provider_policy(
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
  project_id_value uuid;
  actor_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  strategy_id_value text;
  receipt_id_value uuid;
  receipt_hash_value text;
  actor_role_value text;
  recipe_value text;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  receipt_row
    content_factory.generation_strategy_readiness_receipts%rowtype;
  binding_current_value boolean := false;
  approved_spec_value boolean := false;
  receipt_current_value boolean := false;
  receipt_unconsumed_value boolean := false;
  start_path_integrated_value boolean := false;
  sql_provider_gate_value boolean := false;
  launch_enabled_value boolean := false;
  blockers_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'strategy_id',
       'provider_readiness_receipt_id',
       'provider_readiness_receipt_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'strategy_id',
       'provider_readiness_receipt_id',
       'provider_readiness_receipt_hash'
     ]::text[]
     or p_payload ->> 'version' <>
       'generation-strategy-provider-policy-request-v1'
     or jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[1-9][0-9]{0,5}$'
     or jsonb_typeof(p_payload -> 'provider_readiness_receipt_id')
          not in ('string', 'null')
     or jsonb_typeof(p_payload -> 'provider_readiness_receipt_hash')
          not in ('string', 'null')
     or (
       jsonb_typeof(p_payload -> 'provider_readiness_receipt_id') = 'null'
       and jsonb_typeof(p_payload -> 'provider_readiness_receipt_hash') <>
         'null'
     )
     or (
       jsonb_typeof(p_payload -> 'provider_readiness_receipt_id') = 'string'
       and jsonb_typeof(p_payload -> 'provider_readiness_receipt_hash') <>
         'string'
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_policy_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  strategy_id_value := lower(btrim(p_payload ->> 'strategy_id'));
  recipe_value := content_factory_private.generation_strategy_recipe(
    strategy_id_value
  );
  if spec_hash_value !~ '^[0-9a-f]{64}$' or recipe_value is null then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_policy_payload_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'provider_readiness_receipt_id') = 'string'
  then
    begin
      receipt_id_value :=
        (p_payload ->> 'provider_readiness_receipt_id')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023',
        message = 'generation_strategy_provider_policy_payload_invalid';
    end;
    receipt_hash_value := lower(btrim(
      p_payload ->> 'provider_readiness_receipt_hash'
    ));
    if receipt_hash_value !~ '^[0-9a-f]{64}$' then
      raise exception using errcode = '22023',
        message = 'generation_strategy_provider_policy_payload_invalid';
    end if;
  end if;
  select membership.role into actor_role_value
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id and profile.status = 'active'
  where membership.organization_id = organization_id_value
    and membership.profile_id = actor_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin', 'producer', 'operator');
  if actor_role_value is null
     or not content_factory_private.workspace_project_access_allowed(
       organization_id_value, project_id_value, actor_id_value
     ) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_provider_policy_access_required';
  end if;
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value
    and binding.strategy_id = strategy_id_value;
  binding_current_value := binding_row.id is not null
    and content_factory_private.generation_strategy_binding_current(
      organization_id_value, binding_row.id
    );
  select coalesce(
    head.state = 'approved'
      and head.spec_version = spec_version_value
      and head.spec_hash = spec_hash_value,
    false
  ) into approved_spec_value
  from content_factory.generation_spec_head_events head
  where head.organization_id = organization_id_value
    and head.spec_id = spec_id_value
  order by head.event_sequence desc
  limit 1;
  approved_spec_value := coalesce(approved_spec_value, false);
  if receipt_id_value is not null then
    select receipt.* into receipt_row
    from content_factory.generation_strategy_readiness_receipts receipt
    where receipt.organization_id = organization_id_value
      and receipt.id = receipt_id_value
      and receipt.receipt_hash = receipt_hash_value
      and receipt.checked_by = actor_id_value
      and receipt.project_id = project_id_value
      and receipt.spec_id = spec_id_value
      and receipt.spec_version = spec_version_value
      and receipt.spec_hash = spec_hash_value
      and receipt.spec_strategy_binding_id = binding_row.id
      and receipt.binding_hash = binding_row.binding_hash
      and receipt.strategy_id = strategy_id_value
      and receipt.recipe = recipe_value
      and receipt.catalog_version = '2026-08-14.v1'
      and receipt.recipe_version = '2026-06'
      and receipt.pricing_version =
        'runway-recipe-credits-2026-08-14.v1'
      and receipt.ready
      and receipt.expires_at > statement_timestamp();
    receipt_current_value := receipt_row.id is not null
      and content_factory_private.generation_strategy_selection_current(
        organization_id_value, binding_row.id,
        receipt_row.selection_snapshot
      )
      and content_factory_private.generation_strategy_prompt_snapshot(
        organization_id_value, binding_row.id,
        receipt_row.selection_snapshot
      ) is not distinct from receipt_row.strategy_prompt_snapshot;
    receipt_unconsumed_value := receipt_current_value and not exists (
      select 1
      from content_factory.generation_strategy_start_claims claim
      where claim.organization_id = organization_id_value
        and claim.readiness_receipt_id = receipt_row.id
    );
  end if;
  start_path_integrated_value := content_factory_private
    .generation_strategy_execution_chain_installed();
  sql_provider_gate_value :=
    content_factory_private.generation_provider_launch_enabled(
      organization_id_value, 'runway', 'gen4_turbo'
    );
  launch_enabled_value := binding_current_value and approved_spec_value
    and receipt_current_value and receipt_unconsumed_value
    and start_path_integrated_value and sql_provider_gate_value;
  if binding_row.id is null then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_strategy_binding_missing');
  elsif not binding_current_value then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_strategy_binding_not_current');
  end if;
  if not approved_spec_value then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_spec_not_approved');
  end if;
  if receipt_id_value is null then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_readiness_receipt_missing');
  elsif not receipt_current_value then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_readiness_receipt_not_current');
  elsif not receipt_unconsumed_value then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_readiness_receipt_consumed');
  end if;
  if not sql_provider_gate_value then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_configuration_disabled');
  end if;
  if not start_path_integrated_value then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_strategy_start_path_not_integrated');
  end if;
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-provider-policy-response-v1',
    'execution_capabilities', jsonb_build_object(
      strategy_id_value, jsonb_build_object(
        'enabled', launch_enabled_value,
        'catalog_version', '2026-08-14.v1',
        'strategy_id', strategy_id_value,
        'provider', 'runway',
        'recipe', recipe_value,
        'recipe_version', '2026-06',
        'provider_path', case when recipe_value = 'product_swap'
          then '/v1/video_to_video'
          else '/v1/recipes/' || recipe_value end,
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
      )
    ),
    'context', jsonb_build_object(
      'strategy_id', strategy_id_value,
      'provider', 'runway',
      'recipe', recipe_value,
      'binding_id', to_jsonb(binding_row.id),
      'binding_hash', to_jsonb(binding_row.binding_hash),
      'provider_readiness_receipt_id', to_jsonb(receipt_row.id),
      'provider_readiness_receipt_hash',
        to_jsonb(receipt_row.receipt_hash),
      'catalog_version', '2026-08-14.v1',
      'recipe_version', '2026-06',
      'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
    ),
    'checks', jsonb_build_object(
      'strategy_binding_current', binding_current_value,
      'generation_spec_approved', approved_spec_value,
      'provider_readiness_receipt_current', receipt_current_value,
      'provider_readiness_receipt_unconsumed', receipt_unconsumed_value,
      'sql_provider_configuration_enabled', sql_provider_gate_value,
      'start_path_integrated', start_path_integrated_value
    ),
    'blockers', blockers_value,
    'launch_enabled', launch_enabled_value,
    'contract', jsonb_build_object(
      'read_only', true,
      'server_authoritative', true,
      'provider_call_started', false,
      'paid_start_integrated', start_path_integrated_value,
      'receipt_single_use', true,
      'launch_enabled', launch_enabled_value
    )
  );
end;
$$;

revoke all on function
  public.system_generation_strategy_provider_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_generation_strategy_provider_policy(jsonb)
  to service_role;

do $generation_strategy_product_swap_video_to_video_verify$
declare
  catalog_def_value text;
  provider_def_value text;
begin
  catalog_def_value := pg_catalog.pg_get_functiondef(
    'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
  );
  provider_def_value := pg_catalog.pg_get_functiondef(
    'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
  );
  if position('''/v1/video_to_video''' in catalog_def_value) = 0
     or position('/v1/recipes/product_swap' in catalog_def_value) > 0
     or position('''/v1/recipes/product_ugc''' in catalog_def_value) = 0
     or position('''/v1/recipes/product_ad''' in catalog_def_value) = 0
     or position('''/v1/video_to_video''' in provider_def_value) = 0
     or position('/v1/recipes/product_swap' in provider_def_value) > 0
     or position('''product_swap''' in provider_def_value) = 0 then
    raise exception using errcode = 'P0001',
      message = 'generation_strategy_product_swap_video_to_video_invalid';
  end if;
end;
$generation_strategy_product_swap_video_to_video_verify$;

commit;

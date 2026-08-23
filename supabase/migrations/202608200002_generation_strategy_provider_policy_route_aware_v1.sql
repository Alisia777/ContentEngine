begin;

-- 202608200002_generation_strategy_provider_policy_route_aware_v1
--
-- The current authority before this migration is 202608190013: it makes the
-- provider-policy receipt lookup follow an enabled route pricing_version, but
-- the same function still calls generation_provider_launch_enabled with the
-- literal runway/gen4_turbo pair and returns provider = runway.  A valid Pika
-- or Kling receipt therefore reaches the final policy and is rejected there.
--
-- This migration keeps the append-only history intact and replaces only the
-- current policy boundary.  Provider/model/path/pricing tuples are an exact
-- allowlist shared in shape with the Edge reader.  The database route table
-- remains the authority for enablement and verified prices; an enabled row is
-- necessary but cannot make an unknown executable route valid.

create or replace function
  content_factory_private.generation_strategy_provider_route_allowed(
    p_strategy_id text,
    p_provider text,
    p_model_key text,
    p_provider_path text,
    p_poll_kind text,
    p_pricing_version text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select coalesce(case
    when p_strategy_id = 'viral_avatar_ugc'
     and p_provider = 'runway'
     and p_model_key = 'gen4_turbo'
      then p_provider_path = '/v1/recipes/product_ugc'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'runway'
     and p_model_key = 'aleph2'
      then p_provider_path = '/v1/video_to_video'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key = 'fal-ai/pika/v2/pikaswaps'
      then p_provider_path = 'fal-ai/pika/v2/pikaswaps'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-run-2026-08-18.v1'
    when p_strategy_id = 'viral_product_swap'
     and p_provider = 'fal'
     and p_model_key =
       'fal-ai/kling-video/o3/pro/video-to-video/edit'
      then p_provider_path =
        'fal-ai/kling-video/o3/pro/video-to-video/edit'
       and p_poll_kind = 'fal_request'
       and p_pricing_version = 'fal-usd-per-second-2026-08-18.v1'
    when p_strategy_id = 'viral_rebuild'
     and p_provider = 'runway'
     and p_model_key = 'gen4_turbo'
      then p_provider_path = '/v1/recipes/product_ad'
       and p_poll_kind = 'runway_task'
       and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    else false
  end, false);
$$;

comment on function
  content_factory_private.generation_strategy_provider_route_allowed(
    text, text, text, text, text, text
  ) is
  'Exact fail-closed executable strategy route allowlist. Database enablement and verified pricing remain independently required.';

revoke all on function
  content_factory_private.generation_strategy_provider_route_allowed(
    text, text, text, text, text, text
  ) from public, anon, authenticated, service_role;

-- The paid-start guards already call this helper.  Preserve that authority,
-- but require the enabled registry row to be one of the exact executable
-- routes rather than accepting any row with a matching provider/price pair.
create or replace function
  content_factory_private.generation_strategy_route_provider_current(
    p_strategy_id text,
    p_provider text,
    p_pricing_version text
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(case
    when not exists (
      select 1
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = p_strategy_id
    ) then (
      (p_strategy_id = 'viral_avatar_ugc'
       or p_strategy_id = 'viral_rebuild')
      and p_provider = 'runway'
      and p_pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    )
    else exists (
      select 1
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = p_strategy_id
        and route.provider = p_provider
        and route.pricing_version = p_pricing_version
        and route.enabled
        and content_factory_private
          .generation_strategy_provider_route_allowed(
            route.strategy_id,
            route.provider,
            route.model_key,
            route.provider_path,
            route.poll_kind,
            route.pricing_version
          )
    )
  end, false);
$$;

comment on function
  content_factory_private.generation_strategy_route_provider_current(
    text, text, text
  ) is
  'Paid strategy provider and pricing must resolve to one enabled, verified and exactly executable registry route; legacy Runway-only strategies retain their exact pricing contract.';

revoke all on function
  content_factory_private.generation_strategy_route_provider_current(
    text, text, text
  ) from public, anon, authenticated, service_role;

-- Product Swap uses Runway Aleph (`model: aleph2`), not gen4_turbo.  Pika and
-- Kling were added to this exact launch switch in 202608180007/009; add the
-- missing Runway route without weakening the default false branch.
do $launch_gate_aleph2$
declare
  definition_value text;
  anchor constant text := $f$when 'runway:gen4_turbo' then true$f$;
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'content_factory_private.generation_provider_launch_enabled(uuid,text,text)'
      ::regprocedure
  );
  if definition_value is null then
    raise exception using message = 'generation_provider_launch_gate_missing';
  end if;
  if position($f$'runway:aleph2'$f$ in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'generation_provider_launch_gate_anchor_invalid:' || anchor_hits::text;
  end if;
  execute replace(
    definition_value,
    anchor,
    $r$when 'runway:gen4_turbo' then true
    when 'runway:aleph2' then true$r$
  );
end;
$launch_gate_aleph2$;

-- Readiness must fail before it mints a receipt for an unknown enabled route.
-- Keep the legacy recipe-price fallback only for strategies which have no
-- route registry at all (Avatar UGC and Rebuild).  Product Swap has a registry,
-- so an unrecognized model/path/poll tuple produces the existing
-- generation_strategy_readiness_price_not_current refusal.
do $readiness_exact_route$
declare
  definition_value text;
  -- Do not anchor on the preceding localized comment. Some production
  -- definitions predate the UTF-8-safe migration pipeline and retain that
  -- comment as replacement glyphs even though the executable SQL is exact.
  anchor constant text := $f$  canonical_price_value := coalesce(
    (
      select content_factory_private.generation_strategy_route_price(
        binding_row.strategy_id,
        route.provider,
        route.model_key,
        (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
        selection_row.price_snapshot ->> 'resolution',
        selection_row.price_snapshot ->> 'ratio',
        (selection_row.selection_snapshot ->> 'audio')::boolean
      )
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = binding_row.strategy_id
        and route.provider = selection_row.price_snapshot ->> 'provider'
        and route.pricing_version =
          selection_row.price_snapshot ->> 'pricing_version'
        and route.enabled
    ),
    content_factory_private.generation_strategy_recipe_price(
      binding_row.strategy_id,
      (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
      selection_row.price_snapshot ->> 'resolution',
      selection_row.price_snapshot ->> 'ratio',
      (selection_row.selection_snapshot ->> 'audio')::boolean
    )
  );$f$;
  replacement constant text := $f$  -- engine_choice_v1: exact signed route, never an arbitrary enabled row.
  canonical_price_value := coalesce(
    (
      select content_factory_private.generation_strategy_route_price(
        binding_row.strategy_id,
        route.provider,
        route.model_key,
        (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
        selection_row.price_snapshot ->> 'resolution',
        selection_row.price_snapshot ->> 'ratio',
        (selection_row.selection_snapshot ->> 'audio')::boolean
      )
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = binding_row.strategy_id
        and route.provider = selection_row.price_snapshot ->> 'provider'
        and route.pricing_version =
          selection_row.price_snapshot ->> 'pricing_version'
        and route.enabled
        and content_factory_private
          .generation_strategy_provider_route_allowed(
            route.strategy_id,
            route.provider,
            route.model_key,
            route.provider_path,
            route.poll_kind,
            route.pricing_version
          )
    ),
    case when not exists (
      select 1
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = binding_row.strategy_id
    ) then content_factory_private.generation_strategy_recipe_price(
      binding_row.strategy_id,
      (selection_row.selection_snapshot ->> 'duration_seconds')::integer,
      selection_row.price_snapshot ->> 'resolution',
      selection_row.price_snapshot ->> 'ratio',
      (selection_row.selection_snapshot ->> 'audio')::boolean
    ) else null end
  );$f$;
  anchor_hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
  );
  if position('exact signed route' in definition_value) > 0 then
    return;
  end if;
  anchor_hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'strategy_readiness_route_anchor_invalid:' || anchor_hits::text;
  end if;
  execute replace(definition_value, anchor, replacement);
end;
$readiness_exact_route$;

revoke all on function
  public.system_record_generation_strategy_readiness(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_record_generation_strategy_readiness(jsonb)
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
  route_provider_value text;
  route_model_key_value text;
  route_provider_path_value text;
  route_poll_kind_value text;
  route_pricing_version_value text;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  receipt_row
    content_factory.generation_strategy_readiness_receipts%rowtype;
  binding_current_value boolean := false;
  approved_spec_value boolean := false;
  receipt_current_value boolean := false;
  receipt_unconsumed_value boolean := false;
  route_current_value boolean := false;
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
      and content_factory_private.generation_strategy_route_provider_current(
        receipt.strategy_id, receipt.provider, receipt.pricing_version
      )
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

  -- The receipt carries provider + pricing_version in the signed spend
  -- contour.  The partial unique signature index from 202608190006 guarantees
  -- that this pair resolves to at most one enabled route for the strategy.
  if receipt_row.id is not null then
    select
      route.provider,
      route.model_key,
      route.provider_path,
      route.poll_kind,
      route.pricing_version
    into
      route_provider_value,
      route_model_key_value,
      route_provider_path_value,
      route_poll_kind_value,
      route_pricing_version_value
    from content_factory.generation_strategy_provider_routes route
    where route.strategy_id = strategy_id_value
      and route.provider = receipt_row.provider
      and route.pricing_version = receipt_row.pricing_version
      and route.enabled
      and content_factory_private
        .generation_strategy_provider_route_allowed(
          route.strategy_id,
          route.provider,
          route.model_key,
          route.provider_path,
          route.poll_kind,
          route.pricing_version
        );

    -- Avatar UGC and Rebuild still have no registry rows.  Their old exact
    -- Runway recipe route remains available, but only with the signed Runway
    -- pricing version.
    if route_provider_value is null
       and not exists (
         select 1
         from content_factory.generation_strategy_provider_routes route
         where route.strategy_id = strategy_id_value
       )
       and receipt_row.provider = 'runway'
       and receipt_row.pricing_version =
         'runway-recipe-credits-2026-08-14.v1' then
      route_provider_value := 'runway';
      route_model_key_value := 'gen4_turbo';
      route_provider_path_value := case
        when recipe_value = 'product_ugc' then '/v1/recipes/product_ugc'
        when recipe_value = 'product_ad' then '/v1/recipes/product_ad'
        else null
      end;
      route_poll_kind_value := 'runway_task';
      route_pricing_version_value := receipt_row.pricing_version;
    end if;

    route_current_value := content_factory_private
      .generation_strategy_provider_route_allowed(
        strategy_id_value,
        route_provider_value,
        route_model_key_value,
        route_provider_path_value,
        route_poll_kind_value,
        route_pricing_version_value
      );
  end if;

  -- Preserve the useful read-only capability shape when no current receipt is
  -- available.  This fallback never authorizes launch: route_current remains
  -- false and the receipt checks below remain mandatory.
  if route_provider_value is null then
    select
      route.provider,
      route.model_key,
      route.provider_path,
      route.poll_kind,
      route.pricing_version
    into
      route_provider_value,
      route_model_key_value,
      route_provider_path_value,
      route_poll_kind_value,
      route_pricing_version_value
    from content_factory.generation_strategy_provider_routes route
    where route.strategy_id = strategy_id_value
      and route.recommended
      and route.enabled
      and content_factory_private
        .generation_strategy_provider_route_allowed(
          route.strategy_id,
          route.provider,
          route.model_key,
          route.provider_path,
          route.poll_kind,
          route.pricing_version
        );
    if route_provider_value is null then
      route_provider_value := 'runway';
      route_model_key_value := 'gen4_turbo';
      route_provider_path_value := case when recipe_value = 'product_swap'
        then '/v1/video_to_video'
        else '/v1/recipes/' || recipe_value end;
      route_poll_kind_value := 'runway_task';
      route_pricing_version_value :=
        'runway-recipe-credits-2026-08-14.v1';
    end if;
  end if;

  start_path_integrated_value := content_factory_private
    .generation_strategy_execution_chain_installed();
  sql_provider_gate_value := content_factory_private
    .generation_provider_launch_enabled(
      organization_id_value,
      route_provider_value,
      route_model_key_value
    );
  launch_enabled_value := binding_current_value and approved_spec_value
    and receipt_current_value and receipt_unconsumed_value
    and route_current_value
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
  if receipt_id_value is not null and not route_current_value then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_route_not_allowed');
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
    'version', 'generation-strategy-provider-policy-response-v2',
    'execution_capabilities', jsonb_build_object(
      strategy_id_value, jsonb_build_object(
        'enabled', launch_enabled_value,
        'catalog_version', '2026-08-14.v1',
        'strategy_id', strategy_id_value,
        'provider', route_provider_value,
        'model_key', route_model_key_value,
        'recipe', recipe_value,
        'recipe_version', '2026-06',
        'provider_path', route_provider_path_value,
        'poll_kind', route_poll_kind_value,
        'pricing_version', route_pricing_version_value
      )
    ),
    'context', jsonb_build_object(
      'strategy_id', strategy_id_value,
      'provider', route_provider_value,
      'model_key', route_model_key_value,
      'recipe', recipe_value,
      'provider_path', route_provider_path_value,
      'poll_kind', route_poll_kind_value,
      'binding_id', to_jsonb(binding_row.id),
      'binding_hash', to_jsonb(binding_row.binding_hash),
      'provider_readiness_receipt_id', to_jsonb(receipt_row.id),
      'provider_readiness_receipt_hash',
        to_jsonb(receipt_row.receipt_hash),
      'catalog_version', '2026-08-14.v1',
      'recipe_version', '2026-06',
      'pricing_version', route_pricing_version_value
    ),
    'checks', jsonb_build_object(
      'strategy_binding_current', binding_current_value,
      'generation_spec_approved', approved_spec_value,
      'provider_readiness_receipt_current', receipt_current_value,
      'provider_readiness_receipt_unconsumed', receipt_unconsumed_value,
      'provider_route_current', route_current_value,
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

do $generation_strategy_provider_policy_route_aware_verify$
declare
  policy_definition text;
  launch_definition text;
  readiness_definition text;
  spend_definition text;
begin
  -- Exact allowlist: the three Product Swap engines pass, any other model,
  -- path or pricing version fails closed.
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'runway', 'aleph2', '/v1/video_to_video',
       'runway_task',
       'runway-recipe-credits-2026-08-14.v1'
     )
     or not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       'fal-ai/pika/v2/pikaswaps', 'fal_request',
       'fal-usd-per-run-2026-08-18.v1'
     )
     or not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'fal',
       'fal-ai/kling-video/o3/pro/video-to-video/edit',
       'fal-ai/kling-video/o3/pro/video-to-video/edit',
       'fal_request',
       'fal-usd-per-second-2026-08-18.v1'
     )
     or content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'fal', 'fal-ai/unknown/video-to-video',
       'fal-ai/unknown/video-to-video', 'fal_request',
       'fal-usd-per-run-2026-08-18.v1'
     )
     or content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       'fal-ai/pika/v2/pikaswaps', 'runway_task',
       'fal-usd-per-run-2026-08-18.v1'
     ) then
    raise exception using message = 'strategy_route_allowlist_verify_failed';
  end if;

  policy_definition := pg_get_functiondef(
    'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
  );
  if position('generation-strategy-provider-policy-response-v2'
       in policy_definition) = 0
     or position('route.model_key' in policy_definition) = 0
     or position('generation_strategy_provider_route_allowed'
       in policy_definition) = 0
     or position($f$organization_id_value, 'runway', 'gen4_turbo'$f$
       in policy_definition) > 0
     or position('receipt.ready' in policy_definition) = 0
     or position('receipt.expires_at > statement_timestamp()'
       in policy_definition) = 0
     or position('generation_strategy_selection_current'
       in policy_definition) = 0
     or position('receipt_unconsumed_value' in policy_definition) = 0 then
    raise exception using message = 'strategy_provider_policy_verify_failed';
  end if;

  launch_definition := pg_get_functiondef(
    'content_factory_private.generation_provider_launch_enabled(uuid,text,text)'
      ::regprocedure
  );
  if position('runway:aleph2' in launch_definition) = 0
     or position('fal:fal-ai/pika/v2/pikaswaps' in launch_definition) = 0
     or position(
       'fal:fal-ai/kling-video/o3/pro/video-to-video/edit'
       in launch_definition
     ) = 0
     or position('else false' in launch_definition) = 0 then
    raise exception using message = 'strategy_launch_allowlist_verify_failed';
  end if;

  readiness_definition := pg_get_functiondef(
    'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
  );
  if position('exact signed route' in readiness_definition) = 0
     or position('generation_strategy_provider_route_allowed'
       in readiness_definition) = 0
     or position('case when not exists' in readiness_definition) = 0
     or position('generation_strategy_readiness_price_not_current'
       in readiness_definition) = 0 then
    raise exception using message = 'strategy_readiness_route_verify_failed';
  end if;

  -- The shared real-spend trigger remains the final budget authority for fal.
  spend_definition := pg_get_functiondef(
    'content_factory_private.reserve_real_generation_spend()'::regprocedure
  );
  if position($f$('runway','google','fal')$f$ in spend_definition) = 0
     or position('generation_spend_platform_control' in spend_definition) = 0
     or position('generation_spend_policies' in spend_definition) = 0 then
    raise exception using message = 'strategy_spend_authority_guard_lost';
  end if;
end;
$generation_strategy_provider_policy_route_aware_verify$;

commit;

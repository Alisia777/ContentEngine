begin;

-- 202608210003_generation_strategy_runway_product_swap_source_duration_v1
--
-- Aleph Product Swap edits the submitted MP4 and its real video_to_video body
-- has no duration field. The signed duration and price must therefore follow
-- the server-measured source duration exactly. This forward repair changes the
-- one Aleph Product Swap route; legacy routes keep operator_choice unless their
-- provider request shape was already marked source_video.

lock table content_factory.generation_strategy_provider_routes
  in share row exclusive mode;

select set_config(
  'contentengine.runway_source_duration_legacy_before',
  coalesce(
    (
      select jsonb_agg(
        jsonb_build_object(
          'id', route.id,
          'duration_source', route.duration_source
        ) order by route.id
      )::text
      from content_factory.generation_strategy_provider_routes as route
      where not (
        route.strategy_id = 'viral_product_swap'
        and route.provider = 'runway'
        and route.model_key = 'aleph2'
      )
    ),
    '[]'
  ),
  true
);

select set_config(
  'contentengine.runway_source_duration_price_before',
  jsonb_build_object(
    '12s', content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'runway', 'aleph2',
      12, '720p', 'source', false
    ),
    '15s', content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'runway', 'aleph2',
      15, '720p', 'source', false
    )
  )::text,
  true
);

do $runway_product_swap_route_exact$
declare
  exact_rows integer;
begin
  select count(*) into exact_rows
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.provider = 'runway'
    and route.model_key = 'aleph2'
    and route.provider_path = '/v1/video_to_video'
    and route.poll_kind = 'runway_task'
    and route.enabled = true
    and route.verified_rate_at is not null
    and route.price_kind = 'runway_credit_tiers'
    and route.price_rate_minor is null
    and route.pricing_version = 'runway-recipe-credits-2026-08-14.v1'
    and route.min_duration_seconds = 4
    and route.max_duration_seconds = 15;
  if exact_rows <> 1 then
    raise exception using message =
      'runway_product_swap_route_not_exact:' || exact_rows::text;
  end if;
end;
$runway_product_swap_route_exact$;

update content_factory.generation_strategy_provider_routes as route
set duration_source = 'source_video',
    updated_at = now()
where route.strategy_id = 'viral_product_swap'
  and route.provider = 'runway'
  and route.model_key = 'aleph2'
  and route.provider_path = '/v1/video_to_video'
  and route.poll_kind = 'runway_task';

-- One immutable predicate makes the fail-closed rule executable without a
-- provider call. The migration self-tests exact, ceil, mismatch, missing-probe
-- and legacy operator-choice cases below.
create or replace function
  content_factory_private.generation_strategy_source_duration_matches(
    p_duration_source text,
    p_selected_duration_seconds integer,
    p_measured_duration_seconds numeric
  )
returns boolean
language sql
immutable
set search_path = ''
as $function$
  select case p_duration_source
    when 'operator_choice' then true
    when 'source_video' then coalesce(
      p_measured_duration_seconds is not null
      and p_measured_duration_seconds > 0
      and p_selected_duration_seconds =
        ceil(p_measured_duration_seconds)::integer,
      false
    )
    else false
  end;
$function$;

revoke all on function
  content_factory_private.generation_strategy_source_duration_matches(
    text, integer, numeric
  )
  from public, anon, authenticated;
grant execute on function
  content_factory_private.generation_strategy_source_duration_matches(
    text, integer, numeric
  )
  to service_role;

-- 202608190008 injected a price-kind gate into the binding function. Replace
-- that implementation in place: source_video is a request-shape capability,
-- not a pricing kind. Pika, Kling and Aleph now share the same exact source
-- duration rule; all operator_choice routes retain their previous behaviour.
do $runway_source_duration_bind$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  -- ЯКОРЬ — ТОЛЬКО КОД, БЕЗ КОММЕНТАРИЯ. Комментарий над этим блоком в проде
  -- искажён (кириллица применена как «?» при выкладке 202608190008 через
  -- MCP), и якорь с русским текстом там не находится никогда. Код одинаков в
  -- обеих базах; прежний комментарий остаётся над новым блоком как след
  -- истории.
  block_anchor constant text := $f$  if p_payload ? 'engine' then
    declare
      route_price_kind text;
      measured_seconds numeric;
    begin
      select route.price_kind into route_price_kind
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = strategy_id_value
        and route.provider = p_payload #>> '{engine,provider}'
        and route.model_key = p_payload #>> '{engine,model_key}';
      if route_price_kind = 'usd_minor_per_second' then
        select duration.duration_seconds into measured_seconds
        from content_factory.generation_strategy_media_durations as duration
        where duration.organization_id = organization_id_value
          and duration.media_object_id = source_media_id_value
        order by duration.verified_at desc
        limit 1;
        if measured_seconds is null
           or measured_seconds <= 0
           or duration_seconds_value <> ceil(measured_seconds)::integer then
          raise exception using errcode = '22023',
            message = 'generation_strategy_source_duration_mismatch';
        end if;
      end if;
    end;
  end if;$f$;
  block_replacement constant text := $f$  -- source_duration_v2: provider request shape owns duration authority.
  -- An explicit engine resolves by its exact signed identity. A legacy request
  -- without engine resolves the one enabled recommended registry route. A
  -- strategy with no registry route keeps its legacy operator-owned duration.
  declare
    route_duration_source text;
    measured_seconds numeric;
  begin
    if p_payload ? 'engine' then
      select route.duration_source into route_duration_source
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = strategy_id_value
        and route.provider = p_payload #>> '{engine,provider}'
        and route.model_key = p_payload #>> '{engine,model_key}'
        and route.enabled
        and content_factory_private.generation_strategy_provider_route_allowed(
          route.strategy_id,
          route.provider,
          route.model_key,
          route.provider_path,
          route.poll_kind,
          route.pricing_version
        );
    else
      select route.duration_source into route_duration_source
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = strategy_id_value
        and route.recommended
        and route.enabled
        and content_factory_private.generation_strategy_provider_route_allowed(
          route.strategy_id,
          route.provider,
          route.model_key,
          route.provider_path,
          route.poll_kind,
          route.pricing_version
        );
    end if;
    if route_duration_source = 'source_video' then
      select duration.duration_seconds into measured_seconds
      from content_factory.generation_strategy_media_durations as duration
      where duration.organization_id = organization_id_value
        and duration.media_object_id = source_media_id_value
      order by duration.verified_at desc
      limit 1;
    end if;
    if (
         strategy_id_value = 'viral_product_swap'
         and route_duration_source is null
       ) or (
         route_duration_source is not null
         and not content_factory_private
           .generation_strategy_source_duration_matches(
             route_duration_source,
             duration_seconds_value,
             measured_seconds
           )
       ) then
      raise exception using errcode = '22023',
        message = 'generation_strategy_source_duration_mismatch';
    end if;
  end;$f$;
begin
  select replace(
    pg_get_functiondef(
      'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
        ::regprocedure
    ),
    E'\r\n',
    E'\n'
  ) into definition_value;
  if definition_value is null then
    raise exception using message = 'bind_pre_execution_missing';
  end if;
  if position('source_duration_v2' in definition_value) > 0 then
    if position(
         $guard$strategy_id_value = 'viral_product_swap'
         and route_duration_source is null$guard$ in definition_value
       ) > 0 then
      return;
    end if;
    raise exception using message = 'source_duration_v2_null_guard_missing';
  end if;
  if position('source_duration_v1' in definition_value) = 0 then
    raise exception using message = 'source_duration_v1_missing';
  end if;

  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, block_anchor, ''))
  ) / length(block_anchor);
  if anchor_hits <> 1 then
    raise exception using message =
      'runway_source_duration_anchor_not_unique:' || anchor_hits::text;
  end if;

  patched_value := replace(definition_value, block_anchor, block_replacement);
  if position('source_duration_v2' in patched_value) = 0
     or position('route_duration_source' in patched_value) = 0
     or position('route.recommended' in patched_value) = 0
     or position(
       'generation_strategy_source_duration_matches' in patched_value
     ) = 0
     or position(
       'generation_strategy_source_duration_mismatch' in patched_value
     ) = 0 then
    raise exception using message = 'runway_source_duration_patch_failed';
  end if;

  execute patched_value;
end;
$runway_source_duration_bind$;

-- A readiness receipt lives for fifteen minutes. A receipt minted immediately
-- before this migration therefore cannot be trusted to have passed v2. Patch
-- the authoritative claim RPC as well: every new claim re-resolves the exact
-- signed route and checks the current verified source duration before the
-- claim/job/reservation rows exist. Existing claims retain replay idempotency.
do $runway_source_duration_claim$
declare
  definition_value text;
  patched_value text;
  declaration_anchor constant text :=
    $f$  asset_context_value jsonb;$f$;
  declaration_replacement constant text := $f$  asset_context_value jsonb;
  route_duration_source text;
  source_media_id_value uuid;
  measured_seconds numeric;$f$;
  claim_anchor constant text :=
    $f$  claim_hash_value := content_factory_private.json_hash(jsonb_build_object($f$;
  claim_replacement constant text := $f$  -- source_duration_claim_v2: a receipt may predate the route capability.
  -- Resolve its signed provider + pricing version again at claim time. The
  -- partial unique route-signature index makes this at most one enabled row.
  select route.duration_source into route_duration_source
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = receipt_row.strategy_id
    and route.provider = receipt_row.provider
    and route.pricing_version = receipt_row.pricing_version
    and route.enabled
    and content_factory_private.generation_strategy_provider_route_allowed(
      route.strategy_id,
      route.provider,
      route.model_key,
      route.provider_path,
      route.poll_kind,
      route.pricing_version
    );
  if route_duration_source = 'source_video' then
    select (item.value ->> 'media_object_id')::uuid
      into source_media_id_value
    from jsonb_array_elements(asset_context_value) as item(value)
    where item.value ->> 'role' = 'source_video';
    select duration.duration_seconds into measured_seconds
    from content_factory.generation_strategy_media_durations as duration
    where duration.organization_id = organization_id_value
      and duration.media_object_id = source_media_id_value
    order by duration.verified_at desc
    limit 1;
  end if;
  if (
       receipt_row.strategy_id = 'viral_product_swap'
       and route_duration_source is null
     ) or (
       route_duration_source is not null
       and not content_factory_private
         .generation_strategy_source_duration_matches(
           route_duration_source,
           strategy_duration_value,
           measured_seconds
         )
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_source_duration_mismatch';
  end if;

  claim_hash_value := content_factory_private.json_hash(jsonb_build_object($f$;
  declaration_hits integer;
  claim_hits integer;
begin
  select replace(
    pg_get_functiondef(
      'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
    ),
    E'\r\n',
    E'\n'
  ) into definition_value;
  if definition_value is null then
    raise exception using message = 'claim_start_rpc_missing';
  end if;
  if position('source_duration_claim_v2' in definition_value) > 0 then
    if position(
         $guard$receipt_row.strategy_id = 'viral_product_swap'
       and route_duration_source is null$guard$ in definition_value
       ) > 0 then
      return;
    end if;
    raise exception using message =
      'source_duration_claim_v2_null_guard_missing';
  end if;
  if position(
       'generation_job_failure_proven_unpaid' in definition_value
     ) = 0 then
    raise exception using message = 'claim_start_lineage_not_current';
  end if;

  declaration_hits := (
    length(definition_value)
    - length(replace(definition_value, declaration_anchor, ''))
  ) / length(declaration_anchor);
  claim_hits := (
    length(definition_value)
    - length(replace(definition_value, claim_anchor, ''))
  ) / length(claim_anchor);
  if declaration_hits <> 1 or claim_hits <> 1 then
    raise exception using message =
      'runway_source_duration_claim_anchor_not_unique:'
      || declaration_hits::text || ':' || claim_hits::text;
  end if;

  patched_value := replace(
    definition_value, declaration_anchor, declaration_replacement
  );
  patched_value := replace(patched_value, claim_anchor, claim_replacement);
  if position('source_duration_claim_v2' in patched_value) = 0
     or position('route_duration_source' in patched_value) = 0
     or position('source_media_id_value' in patched_value) = 0
     or position(
       'generation_strategy_source_duration_matches' in patched_value
     ) = 0
     or position(
       'generation_strategy_source_duration_mismatch' in patched_value
     ) = 0
     or position('claim_hash_value :=' in patched_value) = 0 then
    raise exception using message = 'runway_source_duration_claim_patch_failed';
  end if;

  execute patched_value;
end;
$runway_source_duration_claim$;

-- Claims and queued jobs created before the migration also exist. The dispatch
-- reservation RPC is the last database authority before the edge may POST to a
-- provider. Recheck there and terminalize a mismatch as the existing safe
-- pre-dispatch input failure, which releases the reservation without a POST.
do $runway_source_duration_dispatch$
declare
  definition_value text;
  patched_value text;
  declaration_anchor constant text :=
    $f$  asset_context_value jsonb;$f$;
  declaration_replacement constant text := $f$  asset_context_value jsonb;
  route_duration_source text;
  source_media_id_value uuid;
  measured_seconds numeric;$f$;
  guard_anchor constant text := $f$      if jsonb_array_length(asset_context_value) <>
           expected_asset_count_value then
        pre_dispatch_failure_code_value := 'input_asset_not_current';
      end if;$f$;
  guard_replacement constant text := $f$      if jsonb_array_length(asset_context_value) <>
           expected_asset_count_value then
        pre_dispatch_failure_code_value := 'input_asset_not_current';
      else
        -- source_duration_dispatch_v2: final authority before provider POST.
        select (item.value ->> 'media_object_id')::uuid
          into source_media_id_value
        from jsonb_array_elements(asset_context_value) as item(value)
        where item.value ->> 'role' = 'source_video';
        select route.duration_source into route_duration_source
        from content_factory.generation_strategy_provider_routes as route
        where route.strategy_id = receipt_row.strategy_id
          and route.provider = receipt_row.provider
          and route.pricing_version = receipt_row.pricing_version
          and route.enabled
          and content_factory_private.generation_strategy_provider_route_allowed(
            route.strategy_id,
            route.provider,
            route.model_key,
            route.provider_path,
            route.poll_kind,
            route.pricing_version
          );
        if route_duration_source = 'source_video' then
          select duration.duration_seconds into measured_seconds
          from content_factory.generation_strategy_media_durations as duration
          where duration.organization_id = organization_id_value
            and duration.media_object_id = source_media_id_value
          order by duration.verified_at desc
          limit 1;
        end if;
        if (
             receipt_row.strategy_id = 'viral_product_swap'
             and route_duration_source is null
           ) or (
             route_duration_source is not null
             and not content_factory_private
               .generation_strategy_source_duration_matches(
                 route_duration_source,
                 (receipt_row.selection_snapshot ->> 'duration_seconds')::integer,
                 measured_seconds
               )
           ) then
          pre_dispatch_failure_code_value := 'input_asset_not_current';
        end if;
      end if;$f$;
  declaration_hits integer;
  guard_hits integer;
begin
  select replace(
    pg_get_functiondef(
      'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'
        ::regprocedure
    ),
    E'\r\n',
    E'\n'
  ) into definition_value;
  if definition_value is null then
    raise exception using message = 'dispatch_attempt_rpc_missing';
  end if;
  if position('source_duration_dispatch_v2' in definition_value) > 0 then
    if position(
         $guard$receipt_row.strategy_id = 'viral_product_swap'
             and route_duration_source is null$guard$ in definition_value
       ) > 0 then
      return;
    end if;
    raise exception using message =
      'source_duration_dispatch_v2_null_guard_missing';
  end if;
  if position($lineage$'provider', receipt_row.provider$lineage$
       in definition_value) = 0 then
    raise exception using message = 'dispatch_attempt_lineage_not_current';
  end if;

  declaration_hits := (
    length(definition_value)
    - length(replace(definition_value, declaration_anchor, ''))
  ) / length(declaration_anchor);
  guard_hits := (
    length(definition_value)
    - length(replace(definition_value, guard_anchor, ''))
  ) / length(guard_anchor);
  if declaration_hits <> 1 or guard_hits <> 1 then
    raise exception using message =
      'runway_source_duration_dispatch_anchor_not_unique:'
      || declaration_hits::text || ':' || guard_hits::text;
  end if;

  patched_value := replace(
    definition_value, declaration_anchor, declaration_replacement
  );
  patched_value := replace(patched_value, guard_anchor, guard_replacement);
  if position('source_duration_dispatch_v2' in patched_value) = 0
     or position('route_duration_source' in patched_value) = 0
     or position('source_media_id_value' in patched_value) = 0
     or position(
       'generation_strategy_source_duration_matches' in patched_value
     ) = 0
     or position(
       $safe$pre_dispatch_failure_code_value := 'input_asset_not_current'$safe$
       in patched_value
     ) = 0 then
    raise exception using message =
      'runway_source_duration_dispatch_patch_failed';
  end if;

  execute patched_value;
end;
$runway_source_duration_dispatch$;

revoke all on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  to service_role;

revoke all on function
  public.system_claim_generation_strategy_start(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_claim_generation_strategy_start(jsonb)
  to service_role;

revoke all on function
  public.system_mark_generation_strategy_dispatch_attempt(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_mark_generation_strategy_dispatch_attempt(jsonb)
  to service_role;

do $source_duration_semantic_proof$
begin
  if not content_factory_private.generation_strategy_source_duration_matches(
    'source_video', 12, 12
  ) then
    raise exception using message = 'source_duration_exact_match_broken';
  end if;
  if not content_factory_private.generation_strategy_source_duration_matches(
    'source_video', 13, 12.01
  ) then
    raise exception using message = 'source_duration_ceil_match_broken';
  end if;
  if content_factory_private.generation_strategy_source_duration_matches(
    'source_video', 12, 12.01
  ) then
    raise exception using message = 'source_duration_mismatch_not_closed';
  end if;
  if content_factory_private.generation_strategy_source_duration_matches(
    'source_video', 12, null
  ) then
    raise exception using message = 'source_duration_missing_probe_not_closed';
  end if;
  if not content_factory_private.generation_strategy_source_duration_matches(
    'operator_choice', 4, null
  ) then
    raise exception using message = 'operator_choice_legacy_broken';
  end if;
end;
$source_duration_semantic_proof$;

do $runway_source_duration_verify$
declare
  before_legacy text;
  after_legacy text;
  before_price jsonb;
  after_price jsonb;
  definition_value text;
  drifted_routes integer;
begin
  before_legacy := current_setting(
    'contentengine.runway_source_duration_legacy_before', true
  );
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', route.id,
        'duration_source', route.duration_source
      ) order by route.id
    )::text,
    '[]'
  ) into after_legacy
  from content_factory.generation_strategy_provider_routes as route
  where not (
    route.strategy_id = 'viral_product_swap'
    and route.provider = 'runway'
    and route.model_key = 'aleph2'
  );
  if before_legacy is null or before_legacy <> after_legacy then
    raise exception using message = 'legacy_route_duration_drifted';
  end if;

  select count(*) into drifted_routes
  from content_factory.generation_strategy_provider_routes as route
  where (
    (
      route.provider = 'fal'
      and route.poll_kind = 'fal_request'
    )
    or (
      route.strategy_id = 'viral_product_swap'
      and route.provider = 'runway'
      and route.model_key = 'aleph2'
      and route.provider_path = '/v1/video_to_video'
      and route.poll_kind = 'runway_task'
    )
  ) is distinct from (route.duration_source = 'source_video');
  if drifted_routes > 0 then
    raise exception using message =
      'runway_source_duration_route_drifted:' || drifted_routes::text;
  end if;

  before_price := current_setting(
    'contentengine.runway_source_duration_price_before', true
  )::jsonb;
  after_price := jsonb_build_object(
    '12s', content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'runway', 'aleph2',
      12, '720p', 'source', false
    ),
    '15s', content_factory_private.generation_strategy_route_price(
      'viral_product_swap', 'runway', 'aleph2',
      15, '720p', 'source', false
    )
  );
  if before_price is distinct from after_price
     or after_price #>> '{12s,estimated_credits}' is distinct from '500'
     or after_price #>> '{12s,estimated_pre_tax_usd_minor}'
       is distinct from '500'
     or after_price #>> '{12s,estimated_cost_minor}' is distinct from '500'
     or after_price #>> '{12s,spend_confirmation}' is distinct from
       'RUNWAY_PRODUCT_SWAP_12S_720P_SILENT_USD_5.00'
     or after_price #>> '{15s,estimated_credits}' is distinct from '608'
     or after_price #>> '{15s,estimated_pre_tax_usd_minor}'
       is distinct from '608'
     or after_price #>> '{15s,estimated_cost_minor}' is distinct from '608'
     or after_price #>> '{15s,spend_confirmation}' is distinct from
       'RUNWAY_PRODUCT_SWAP_15S_720P_SILENT_USD_6.08' then
    raise exception using message = 'runway_route_price_drifted';
  end if;

  select pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  ) into definition_value;
  if definition_value is null
     or position('source_duration_v2' in definition_value) = 0
     or position('route.duration_source' in definition_value) = 0
     or position('route.recommended' in definition_value) = 0
     or position(
       $guard$strategy_id_value = 'viral_product_swap'
         and route_duration_source is null$guard$ in definition_value
     ) = 0
     or position(
       'generation_strategy_source_duration_matches' in definition_value
     ) = 0
     or position(
       'generation_strategy_source_duration_mismatch' in definition_value
     ) = 0 then
    raise exception using message = 'runway_source_duration_bind_verify_failed';
  end if;

  select pg_get_functiondef(
    'public.system_claim_generation_strategy_start(jsonb)'::regprocedure
  ) into definition_value;
  if definition_value is null
     or position('source_duration_claim_v2' in definition_value) = 0
     or position('receipt_row.provider' in definition_value) = 0
     or position('receipt_row.pricing_version' in definition_value) = 0
     or position(
       $guard$receipt_row.strategy_id = 'viral_product_swap'
       and route_duration_source is null$guard$ in definition_value
     ) = 0
     or position($role$item.value ->> 'role' = 'source_video'$role$
          in definition_value) = 0
     or position(
       'generation_strategy_source_duration_matches' in definition_value
     ) = 0
     or position(
       'generation_strategy_source_duration_mismatch' in definition_value
     ) = 0 then
    raise exception using message =
      'runway_source_duration_claim_verify_failed';
  end if;

  select pg_get_functiondef(
    'public.system_mark_generation_strategy_dispatch_attempt(jsonb)'
      ::regprocedure
  ) into definition_value;
  if definition_value is null
     or position('source_duration_dispatch_v2' in definition_value) = 0
     or position('receipt_row.provider' in definition_value) = 0
     or position('receipt_row.pricing_version' in definition_value) = 0
     or position(
       $guard$receipt_row.strategy_id = 'viral_product_swap'
             and route_duration_source is null$guard$ in definition_value
     ) = 0
     or position($role$item.value ->> 'role' = 'source_video'$role$
          in definition_value) = 0
     or position(
       'generation_strategy_source_duration_matches' in definition_value
     ) = 0
     or position(
       $safe$pre_dispatch_failure_code_value := 'input_asset_not_current'$safe$
       in definition_value
     ) = 0 then
    raise exception using message =
      'runway_source_duration_dispatch_verify_failed';
  end if;
end;
$runway_source_duration_verify$;

commit;

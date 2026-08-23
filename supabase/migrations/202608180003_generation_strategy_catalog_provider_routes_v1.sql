begin;

-- 202608180003_generation_strategy_catalog_provider_routes_v1
--
-- Каталог стратегий начинает отдавать реестр движков (202608180002).
--
-- Поле provider_routes необязательное: edge-функция уже умеет и его наличие,
-- и его отсутствие, поэтому миграция и деплой не обязаны быть атомарными.
-- Тело функции повторяет 202608170006 без изменений, кроме одного нового
-- поля — чтобы правка читалась как добавление, а не как переписывание.

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
    -- Движки стратегии из реестра: форма показывает их как «Генератор 1/2/3».
    -- Выключенные маршруты тоже отдаются — экран должен честно показать, что
    -- движок существует, но пока недоступен, а не умалчивать о нём.
    'provider_routes', coalesce((
      select jsonb_object_agg(grouped.strategy_id, grouped.routes)
      from (
        select
          route.strategy_id,
          jsonb_agg(
            jsonb_build_object(
              'provider', route.provider,
              'model_key', route.model_key,
              'tier', route.tier,
              'price_kind', route.price_kind,
              'price_rate_minor', route.price_rate_minor,
              'recommended', route.recommended,
              'enabled', route.enabled
            )
            order by route.recommended desc, route.tier, route.model_key
          ) as routes
        from content_factory.generation_strategy_provider_routes as route
        group by route.strategy_id
      ) as grouped
    ), '{}'::jsonb),
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

-- Инварианты 202608170006 не должны пострадать: маршрут Копии остаётся
-- video_to_video, а старый несуществующий путь не возвращается.
do $catalog_provider_routes_verify$
declare
  definition_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null
     or position('/v1/video_to_video' in definition_value) = 0
     or position('provider_routes' in definition_value) = 0
     or position('/v1/recipes/product_swap' in definition_value) > 0 then
    raise exception using message = 'catalog_provider_routes_verify_failed';
  end if;
end;
$catalog_provider_routes_verify$;

commit;

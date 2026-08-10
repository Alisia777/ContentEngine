begin;

-- Product titles are presentation copy and may be duplicated or edited.  The
-- generation advisory may therefore auto-apply only when the selected media's
-- durable product_id matches an approved research selection, or (for legacy
-- media without product_id) when the requested SKU resolves to exactly one
-- product identity inside this project/category.  A title match remains a
-- category-ranked suggestion and never grants automatic application.

create or replace function
  public.contentengine_generation_research_recommendations(
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
  product_id_value uuid;
  category_value text;
  product_name_value text := '';
  sku_value text := '';
  platform_value text := '';
  requested_platform_value text := '';
  limit_value integer := 3;
  recommendations_value jsonb := '[]'::jsonb;
  exact_match_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'product_id', 'product_category',
    'product_name', 'sku', 'platform', 'limit'
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
  if nullif(btrim(coalesce(p_payload ->> 'product_id', '')), '') is not null then
    product_id_value := content_factory_private.require_uuid(
      p_payload, 'product_id'
    );
  end if;
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  product_name_value := left(
    btrim(coalesce(p_payload ->> 'product_name', '')), 300
  );
  sku_value := left(btrim(coalesce(p_payload ->> 'sku', '')), 160);
  requested_platform_value := lower(left(
    btrim(coalesce(p_payload ->> 'platform', '')), 40
  ));
  platform_value := case requested_platform_value
    when 'instagram_reels' then 'instagram'
    when 'youtube_shorts' then 'youtube'
    when 'vk_clips' then 'vk'
    when 'gen4_turbo' then ''
    when 'seedance2_fast' then ''
    when 'seedream5_lite' then ''
    else requested_platform_value
  end;
  if platform_value <> '' and platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk', 'telegram',
    'wildberries', 'ozon'
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

  with approved_selections as materialized (
    select selection.*
    from content_factory.ai_research_learning_selections selection
    where selection.organization_id = organization_id_value
      and selection.project_id = project_id_value
      and selection.product_category = category_value
      and selection.decision = 'approve'
  ), requested_sku_identity as materialized (
    select
      lower(selection.product_sku) as sku_key,
      count(distinct selection.product_id) as distinct_product_count
    from approved_selections selection
    where product_id_value is null
      and sku_value <> ''
      and lower(selection.product_sku) = lower(sku_value)
      and selection.product_id is not null
    group by lower(selection.product_sku)
  ), candidates as (
    select
      selection.id as selection_id,
      selection.selection_hash,
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
        when coalesce(recommendation.value ->> 'position', '') ~ '^[1-3]$'
          then (recommendation.value ->> 'position')::smallint
        else recommendation.ordinality::smallint
      end as recommendation_position,
      case
        when product_id_value is not null
         and selection.product_id = product_id_value then 4
        when product_id_value is null
         and sku_value <> ''
         and lower(selection.product_sku) = lower(sku_value)
         and coalesce(sku_identity.distinct_product_count, 0) = 1 then 3
        when product_name_value <> ''
         and lower(selection.product_name) = lower(product_name_value) then 2
        else 1
      end as match_rank,
      case when platform_value <> '' and lower(coalesce(
        recommendation.value ->> 'platform', ''
      )) = platform_value then 1 else 0 end as platform_rank
    from approved_selections selection
    left join requested_sku_identity sku_identity
      on sku_identity.sku_key = lower(selection.product_sku)
    cross join lateral jsonb_array_elements(
      selection.recommendations
    ) with ordinality recommendation(value, ordinality)
  ), bounded as (
    select *
    from candidates
    order by match_rank desc, platform_rank desc, selected_at desc,
             event_cursor desc, selection_id desc,
             recommendation_position asc
    limit limit_value
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'selection_id', candidate.selection_id,
    'selection_hash', candidate.selection_hash,
    'receipt_id', candidate.receipt_id,
    'run_id', candidate.run_id,
    'draft_id', candidate.draft_id,
    'product_id', candidate.product_id,
    'source_product_name', candidate.source_product_name,
    'source_product_sku', candidate.source_product_sku,
    'recommendation_position', candidate.recommendation_position,
    'scope_match', case candidate.match_rank
      when 4 then 'exact_product'
      when 3 then 'exact_sku'
      else 'category'
    end,
    'match_basis', case candidate.match_rank
      when 4 then 'product_id'
      when 3 then 'unique_sku'
      when 2 then 'title_advisory'
      else 'category'
    end,
    'platform_match', candidate.platform_rank = 1,
    'can_auto_apply', candidate.match_rank >= 3,
    'preset', content_factory_private.ai_research_generation_preset(
      category_value, candidate.recommendation
    ),
    'recommendation', candidate.recommendation,
    'selected_at', candidate.selected_at,
    'event_cursor', candidate.event_cursor
  ) order by candidate.match_rank desc, candidate.platform_rank desc,
             candidate.selected_at desc, candidate.recommendation_position),
  '[]'::jsonb),
  count(*) filter (where candidate.match_rank >= 3)
  into recommendations_value, exact_match_count
  from bounded candidate;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-research-recommendations-v3',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'requested_product_id', product_id_value,
    'product_category', category_value,
    'requested_product_name', product_name_value,
    'requested_sku', sku_value,
    'requested_platform', platform_value,
    'recommendations', recommendations_value,
    'auto_apply_available', exact_match_count > 0,
    'contract', jsonb_build_object(
      'recommendations_are_editable', true,
      'presets_are_advisory', true,
      'exact_product_id_or_unique_sku_required', true,
      'product_id_precedes_sku', true,
      'product_title_never_auto_applies', true,
      'cross_platform_fallback', true,
      'human_edits_are_preserved', true,
      'spend_confirmation_is_never_applied', true,
      'unreviewed_research_affects_generation', false,
      'raw_research_enters_prompt_automatically', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_generation_research_recommendations(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_generation_research_recommendations(jsonb)
  to authenticated, service_role;

comment on function
  public.contentengine_generation_research_recommendations(jsonb) is
  'Project-ACL recommendation lookup v3: advisory title matches never auto-apply; exact defaults require product_id or one-product SKU identity.';

notify pgrst, 'reload schema';

commit;

begin;

-- Multi-model authority is additive. Historical v1 generation specifications,
-- v2 readiness receipts and the three deployed Runway SKUs stay readable and
-- executable through their original contract. New UI launches use the exact
-- v2 spec + v4 receipt + immutable selection-snapshot path below.

create or replace function content_factory_private.generation_catalog_version()
returns text language sql immutable set search_path = '' as $$
  select '2026-08-13.v1'::text
$$;

create or replace function content_factory_private.generation_catalog_entry(
  p_provider text,
  p_model text
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select case lower(btrim(coalesce(p_provider, ''))) || ':' ||
                   lower(btrim(coalesce(p_model, '')))
    when 'runway:seedream5_lite' then jsonb_build_object(
      'provider','runway','model','seedream5_lite','public_label','Seedream 5 Lite',
      'content_kind','photo','lifecycle','production','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:gen4_turbo' then jsonb_build_object(
      'provider','runway','model','gen4_turbo','public_label','Gen-4 Turbo',
      'content_kind','video','lifecycle','production','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:seedance2_fast' then jsonb_build_object(
      'provider','runway','model','seedance2_fast','public_label','Seedance 2 Fast',
      'content_kind','video','lifecycle','production','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:gen4.5' then jsonb_build_object(
      'provider','runway','model','gen4.5','public_label','Gen-4.5',
      'content_kind','video','lifecycle','experimental','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:seedance2_mini' then jsonb_build_object(
      'provider','runway','model','seedance2_mini','public_label','Seedance 2 Mini',
      'content_kind','video','lifecycle','experimental','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:veo3.1_fast' then jsonb_build_object(
      'provider','runway','model','veo3.1_fast','public_label','Veo 3.1 Fast',
      'content_kind','video','lifecycle','experimental','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:gemini_omni_flash' then jsonb_build_object(
      'provider','runway','model','gemini_omni_flash','public_label','Gemini Omni Flash',
      'content_kind','video','lifecycle','experimental','enabled_by_default',true,
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:veo3.1' then jsonb_build_object(
      'provider','runway','model','veo3.1','public_label','Veo 3.1',
      'content_kind','video','lifecycle','experimental','enabled_by_default',false,
      'feature_flag','generation_runway_premium_v1',
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'runway:seedance2' then jsonb_build_object(
      'provider','runway','model','seedance2','public_label','Seedance 2',
      'content_kind','video','lifecycle','experimental','enabled_by_default',false,
      'feature_flag','generation_runway_premium_v1',
      'pricing_version','runway-credits-2026-08-13.v1')
    when 'google:veo-3.1-lite-generate-preview' then jsonb_build_object(
      'provider','google','model','veo-3.1-lite-generate-preview',
      'public_label','Veo 3.1 Lite','content_kind','video','lifecycle','preview',
      'enabled_by_default',false,'feature_flag','generation_google_veo_lite_v1',
      'pricing_version','google-veo-2026-08-13.v1')
    else null
  end
$$;

revoke all on function content_factory_private.generation_catalog_version()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.generation_catalog_entry(text,text)
  from public, anon, authenticated, service_role;

-- Direct Google remains fail-closed until this migration also owns the exact
-- provider-specific LRO attach/reconcile/completion chain.  The organization
-- feature flag is necessary, but never sufficient by itself.
create or replace function
  content_factory_private.generation_google_lro_sql_ready()
returns boolean
language sql
immutable
set search_path = ''
as $$
  select false
$$;

revoke all on function
  content_factory_private.generation_google_lro_sql_ready()
  from public, anon, authenticated, service_role;

-- The only organization flag owner for provider launch. Premium Runway stays
-- explicitly blocked in this freeze. Direct Google is false unless the exact
-- organization setting is true; browser-supplied flags are never consulted.
create or replace function content_factory_private.generation_provider_launch_enabled(
  p_organization_id uuid,
  p_provider text,
  p_model text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from content_factory.organizations organization
    where organization.id=p_organization_id
      and organization.status='active'
  ) and case lower(btrim(coalesce(p_provider,''))) || ':' ||
                 lower(btrim(coalesce(p_model,'')))
    when 'runway:seedream5_lite' then true
    when 'runway:gen4_turbo' then true
    when 'runway:seedance2_fast' then true
    -- New Runway launches are exact baseline-only: the public policy can
    -- expose them, while recorder/start/provider-claim independently require
    -- the current project/spec/media-bound v4 receipt and recomputed claim.
    when 'runway:gen4.5' then true
    when 'runway:seedance2_mini' then true
    when 'runway:veo3.1_fast' then true
    when 'runway:gemini_omni_flash' then true
    when 'google:veo-3.1-lite-generate-preview' then
      content_factory_private.generation_google_lro_sql_ready()
      and coalesce((
        select organization.settings -> 'generation_google_veo_lite_v1' =
               'true'::jsonb
        from content_factory.organizations organization
        where organization.id = p_organization_id
          and organization.status = 'active'
      ), false)
    else false
  end
$$;

revoke all on function
  content_factory_private.generation_provider_launch_enabled(uuid,text,text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_provider_disabled_reason(
    p_organization_id uuid,p_provider text,p_model text
  )
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select case
    when content_factory_private.generation_provider_launch_enabled(
      p_organization_id,p_provider,p_model
    ) then null
    when lower(btrim(coalesce(p_provider,'')))='runway'
     and lower(btrim(coalesce(p_model,''))) in (
       'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
     ) then 'sql_authority_parity_pending'
    when lower(btrim(coalesce(p_provider,'')))='runway'
     and lower(btrim(coalesce(p_model,''))) in ('veo3.1','seedance2')
      then 'premium_model_launch_unsupported'
    when lower(btrim(coalesce(p_provider,'')))='google'
     and lower(btrim(coalesce(p_model,'')))=
       'veo-3.1-lite-generate-preview'
     and not content_factory_private.generation_google_lro_sql_ready()
      then 'direct_google_disabled'
    when lower(btrim(coalesce(p_provider,'')))='google'
      then 'organization_feature_disabled'
    else 'model_launch_unsupported'
  end
$$;

revoke all on function
  content_factory_private.generation_provider_disabled_reason(uuid,text,text)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_provider_policy(
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
  provider_value text;
  model_value text;
  catalog_entry_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id','provider','model']::text[] <>
       '{}'::jsonb
     or not p_payload ?& array['organization_id','provider','model']::text[]
     or jsonb_typeof(p_payload -> 'provider') <> 'string'
     or jsonb_typeof(p_payload -> 'model') <> 'string' then
    raise exception using errcode='22023',
      message='generation_provider_policy_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, false,
    array['owner','admin','producer','reviewer','operator']
  );
  provider_value := lower(btrim(p_payload ->> 'provider'));
  model_value := lower(btrim(p_payload ->> 'model'));
  catalog_entry_value := content_factory_private.generation_catalog_entry(
    provider_value, model_value
  );
  if catalog_entry_value is null then
    raise exception using errcode='22023',
      message='generation_provider_policy_model_unknown';
  end if;
  return jsonb_build_object(
    'ok', true,
    'provider', provider_value,
    'model', model_value,
    'launch_enabled', content_factory_private
      .generation_provider_launch_enabled(
        organization_id_value, provider_value, model_value
      ),
    'disabled_reason_code',content_factory_private
      .generation_provider_disabled_reason(
        organization_id_value,provider_value,model_value
      ),
    'catalog_version', content_factory_private.generation_catalog_version(),
    'automatic_generation', false,
    'automatic_spend', false
  );
end;
$$;

revoke all on function public.creator_generation_provider_policy(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_generation_provider_policy(jsonb)
  to authenticated;

-- Service workers use the same policy owner with an exact organization. This
-- has no browser/session fallback and returns no organization settings.
create or replace function public.system_generation_provider_policy(
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
  provider_value text;
  model_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id','provider','model']::text[] <>
       '{}'::jsonb
     or not p_payload ?& array['organization_id','provider','model']::text[] then
    raise exception using errcode='22023',
      message='generation_provider_policy_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  provider_value := lower(btrim(coalesce(p_payload ->> 'provider','')));
  model_value := lower(btrim(coalesce(p_payload ->> 'model','')));
  if content_factory_private.generation_catalog_entry(
       provider_value, model_value
     ) is null then
    raise exception using errcode='22023',
      message='generation_provider_policy_model_unknown';
  end if;
  return jsonb_build_object(
    'ok', true,
    'provider', provider_value,
    'model', model_value,
    'launch_enabled', content_factory_private
      .generation_provider_launch_enabled(
        organization_id_value, provider_value, model_value
      ),
    'disabled_reason_code',content_factory_private
      .generation_provider_disabled_reason(
        organization_id_value,provider_value,model_value
      ),
    'catalog_version', content_factory_private.generation_catalog_version(),
    'automatic_generation', false,
    'automatic_spend', false
  );
end;
$$;

revoke all on function public.system_generation_provider_policy(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_generation_provider_policy(jsonb)
  to service_role;

-- Catalog visibility uses bounded server-derived feature booleans.  It is a
-- separate projection from launch policy: premium Runway can be visible to an
-- enabled organization while its unsupported paid start remains blocked.
create or replace function
  content_factory_private.generation_model_feature_flags(
    p_organization_id uuid
  )
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'ok',true,
    'catalog_version',content_factory_private.generation_catalog_version(),
    'google_veo_lite',coalesce(
      organization.settings -> 'generation_google_veo_lite_v1'='true'::jsonb,
      false
    ),
    'runway_premium',coalesce(
      organization.settings -> 'generation_runway_premium_v1'='true'::jsonb,
      false
    )
  )
  from content_factory.organizations organization
  where organization.id=p_organization_id
    and organization.status='active'
$$;

revoke all on function
  content_factory_private.generation_model_feature_flags(uuid)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_model_feature_flags(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare organization_id_value uuid; result_value jsonb;
begin
  p_payload:=content_factory_private.require_payload(p_payload);
  if p_payload-array['organization_id']::text[]<>'{}'::jsonb
     or not p_payload ? 'organization_id' then
    raise exception using errcode='22023',
      message='generation_model_feature_flags_payload_invalid';
  end if;
  organization_id_value:=content_factory_private.require_uuid(
    p_payload,'organization_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value,false,
    array['owner','admin','producer','reviewer','operator']
  );
  result_value:=content_factory_private.generation_model_feature_flags(
    organization_id_value
  );
  if result_value is null then
    raise exception using errcode='42501',message='organization_not_active';
  end if;
  return result_value;
end;
$$;

revoke all on function
  public.creator_generation_model_feature_flags(jsonb)
  from public, anon, service_role;
grant execute on function
  public.creator_generation_model_feature_flags(jsonb) to authenticated;

create or replace function public.system_generation_model_feature_flags(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare organization_id_value uuid; result_value jsonb;
begin
  p_payload:=content_factory_private.require_payload(p_payload);
  if p_payload-array['organization_id']::text[]<>'{}'::jsonb
     or not p_payload ? 'organization_id' then
    raise exception using errcode='22023',
      message='generation_model_feature_flags_payload_invalid';
  end if;
  organization_id_value:=content_factory_private.require_uuid(
    p_payload,'organization_id'
  );
  result_value:=content_factory_private.generation_model_feature_flags(
    organization_id_value
  );
  if result_value is null then
    raise exception using errcode='42501',message='organization_not_active';
  end if;
  return result_value;
end;
$$;

revoke all on function
  public.system_generation_model_feature_flags(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_generation_model_feature_flags(jsonb) to service_role;

-- Adapter-only provider dimensions. Public spec/snapshot `ratio` remains the
-- aspect literal (9:16 etc.); these dimensions must never leak into them.
create or replace function content_factory_private.generation_provider_ratio(
  p_provider text,p_model text,p_format text,p_resolution text
)
returns text
language sql
immutable
set search_path = ''
as $$
  select case
    when p_provider='google'
      and p_model='veo-3.1-lite-generate-preview'
      and p_resolution in ('720p','1080p')
      and p_format in ('9:16','16:9') then p_format
    when p_provider='runway' and p_model='seedream5_lite'
      and p_resolution='2K' then case p_format
        when '1:1' then '2048:2048' when '4:3' then '2304:1728'
        when '3:4' then '1728:2304' when '16:9' then '2848:1600'
        when '9:16' then '1600:2848' when '3:2' then '2496:1664'
        when '2:3' then '1664:2496' when '21:9' then '3136:1344' end
    when p_provider='runway' and p_model='gen4_turbo'
      and p_resolution='720p' then case p_format
        when '21:9' then '1584:672' when '16:9' then '1280:720'
        when '4:3' then '1104:832' when '1:1' then '960:960'
        when '3:4' then '832:1104' when '9:16' then '720:1280' end
    when p_provider='runway' and p_model='gen4.5'
      and p_resolution='720p' then case p_format
        when '21:9' then '1584:672' when '16:9' then '1280:720'
        when '4:3' then '1104:832' when '1:1' then '960:960'
        when '3:4' then '832:1104' when '9:16' then '720:1280' end
    when p_provider='runway'
      and p_model in ('seedance2_fast','seedance2_mini')
      and p_resolution='480p' then case p_format
        when '21:9' then '992:432' when '16:9' then '864:496'
        when '4:3' then '752:560' when '1:1' then '640:640'
        when '3:4' then '560:752' when '9:16' then '496:864' end
    when p_provider='runway'
      and p_model in ('seedance2_fast','seedance2_mini')
      and p_resolution='720p' then case p_format
        when '21:9' then '1470:630' when '16:9' then '1280:720'
        when '4:3' then '1112:834' when '1:1' then '960:960'
        when '3:4' then '834:1112' when '9:16' then '720:1280' end
    when p_provider='runway'
      and p_model in ('veo3.1_fast','gemini_omni_flash')
      and p_resolution='720p' and p_format in ('9:16','16:9') then
        case p_format when '9:16' then '720:1280' else '1280:720' end
    when p_provider='runway' and p_model='veo3.1_fast'
      and p_resolution='1080p' and p_format in ('9:16','16:9') then
        case p_format when '9:16' then '1080:1920' else '1920:1080' end
    else null
  end
$$;

revoke all on function content_factory_private.generation_provider_ratio(
  text,text,text,text
) from public, anon, authenticated, service_role;

-- Exact server pricing/capability function. `format` and public `ratio` are
-- the same aspect literal; `provider_ratio` is the adapter-only translation.
create or replace function content_factory_private.real_generation_multimodel_sku(
  p_provider text,
  p_model text,
  p_input_mode text,
  p_duration integer,
  p_format text,
  p_resolution text,
  p_audio boolean,
  p_last_frame boolean
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  provider_value text := lower(btrim(coalesce(p_provider,'')));
  model_value text := lower(btrim(coalesce(p_model,'')));
  input_mode_value text := lower(btrim(coalesce(p_input_mode,'')));
  format_value text := btrim(coalesce(p_format,''));
  resolution_value text := btrim(coalesce(p_resolution,''));
  credits_value integer;
  cost_value integer;
  confirmation_value text;
  provider_ratio_value text;
  catalog_entry_value jsonb;
begin
  catalog_entry_value := content_factory_private.generation_catalog_entry(
    provider_value, model_value
  );
  provider_ratio_value:=content_factory_private.generation_provider_ratio(
    provider_value,model_value,format_value,resolution_value
  );
  if catalog_entry_value is null or input_mode_value <> 'image'
     or provider_ratio_value is null then
    return null;
  end if;

  if provider_value = 'runway' and model_value = 'seedream5_lite'
     and p_duration = 0 and resolution_value = '2K'
     and format_value = '1:1'
     and not p_audio and not p_last_frame then
    credits_value := 4;
    confirmation_value := 'RUNWAY_SEEDREAM5_LITE_2K_USD_0.04';
  elsif provider_value = 'runway' and model_value = 'gen4_turbo'
     and p_duration between 2 and 10 and resolution_value = '720p'
     and not p_audio and not p_last_frame then
    credits_value := p_duration * 5;
    confirmation_value := format(
      'RUNWAY_GEN4_TURBO_%sS_USD_%s', p_duration,
      to_char(credits_value::numeric / 100,'FM999999990.00')
    );
  elsif provider_value = 'runway' and model_value = 'seedance2_fast'
     and p_duration between 4 and 15
     and resolution_value in ('480p','720p')
     and p_audio and not p_last_frame then
    credits_value := p_duration * 29;
    confirmation_value := format(
      'RUNWAY_SEEDANCE2_FAST_%sS_AUDIO_USD_%s', p_duration,
      to_char(credits_value::numeric / 100,'FM999999990.00')
    );
  elsif provider_value = 'runway' and model_value = 'gen4.5'
     and p_duration between 2 and 10 and resolution_value = '720p'
     and not p_audio and not p_last_frame then
    credits_value := p_duration * 12;
    confirmation_value := format(
      'RUNWAY_GEN4_5_%sS_%s_SILENT_USD_%s', p_duration, upper(resolution_value),
      to_char(credits_value::numeric / 100,'FM999999990.00')
    );
  elsif provider_value = 'runway' and model_value = 'seedance2_mini'
     and p_duration between 4 and 15
     and resolution_value in ('480p','720p')
     and p_audio and not p_last_frame then
    credits_value := greatest(64, p_duration * 16);
    confirmation_value := format(
      'RUNWAY_SEEDANCE2_MINI_%sS_%s_AUDIO_USD_%s', p_duration,
      upper(resolution_value),
      to_char(credits_value::numeric / 100,'FM999999990.00')
    );
  elsif provider_value = 'runway' and model_value = 'veo3.1_fast'
     and p_duration in (4,6,8) and resolution_value in ('720p','1080p')
     and format_value in ('9:16','16:9') then
    credits_value := p_duration * case when p_audio then 15 else 10 end;
    confirmation_value := format(
      'RUNWAY_VEO3_1_FAST_%sS_%s_%s_USD_%s', p_duration,
      upper(resolution_value), case when p_audio then 'AUDIO' else 'SILENT' end,
      to_char(credits_value::numeric / 100,'FM999999990.00')
    );
  elsif provider_value = 'runway' and model_value = 'gemini_omni_flash'
     and p_duration between 3 and 10 and resolution_value = '720p'
     and format_value in ('9:16','16:9') and p_audio and not p_last_frame then
    credits_value := p_duration * 10 + 1;
    confirmation_value := format(
      'RUNWAY_GEMINI_OMNI_FLASH_%sS_720P_AUDIO_USD_%s', p_duration,
      to_char(credits_value::numeric / 100,'FM999999990.00')
    );
  elsif provider_value = 'google'
     and model_value = 'veo-3.1-lite-generate-preview'
     and p_duration in (4,6,8) and format_value in ('9:16','16:9')
     and p_audio and (resolution_value = '720p' or
       (resolution_value = '1080p' and p_duration = 8))
     and (not p_last_frame or p_duration = 8) then
    cost_value := p_duration * case resolution_value
      when '720p' then 5 else 8 end;
    confirmation_value := format(
      'GOOGLE_VEO3_1_LITE_%sS_%s_AUDIO_USD_%s', p_duration,
      upper(resolution_value),
      to_char(cost_value::numeric / 100,'FM999999990.00')
    );
  else
    return null;
  end if;

  if provider_value = 'runway' then
    cost_value := credits_value;
  end if;
  return catalog_entry_value || jsonb_build_object(
    'input_mode', input_mode_value,
    'duration_seconds', p_duration,
    'format', format_value,
    'ratio', format_value,
    'provider_ratio', provider_ratio_value,
    'resolution', resolution_value,
    'audio', p_audio,
    'last_frame', p_last_frame,
    'estimated_cost_minor', cost_value,
    'estimated_credits', case when provider_value='runway'
      then to_jsonb(credits_value) else 'null'::jsonb end,
    'currency', 'USD',
    'spend_confirmation', confirmation_value,
    'catalog_version', content_factory_private.generation_catalog_version()
  );
end;
$$;

revoke all on function content_factory_private.real_generation_multimodel_sku(
  text,text,text,integer,text,text,boolean,boolean
) from public, anon, authenticated, service_role;

create or replace function content_factory_private.real_generation_sku_from_input(
  p_provider text,
  p_input jsonb
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  provider_value text := lower(btrim(coalesce(p_provider,'')));
  model_value text := lower(btrim(coalesce(p_input ->> 'model','')));
  input_mode_value text := lower(btrim(coalesce(p_input ->> 'input_mode','')));
  resolution_value text := btrim(coalesce(p_input ->> 'resolution',''));
  duration_value integer;
  audio_value boolean;
  last_frame_value boolean;
  sku_value jsonb;
  legacy_input boolean := false;
begin
  if jsonb_typeof(p_input)<>'object'
     or jsonb_typeof(p_input -> 'duration_seconds')<>'number'
     or p_input ->> 'duration_seconds' !~ '^[0-9]+$'
     or jsonb_typeof(coalesce(p_input -> 'audio','false'::jsonb))<>'boolean'
     or jsonb_typeof(coalesce(p_input -> 'last_frame','false'::jsonb))<>'boolean'
  then
    return null;
  end if;
  begin
    duration_value := (p_input ->> 'duration_seconds')::integer;
  exception when numeric_value_out_of_range then return null;
  end;
  audio_value := coalesce((p_input ->> 'audio')::boolean,false);
  last_frame_value := coalesce((p_input ->> 'last_frame')::boolean,false);

  -- Compatibility normalization is deliberately limited to the original
  -- three models. Canonical new models must persist every field explicitly.
  if model_value in ('seedream5_lite','gen4_turbo','seedance2_fast') then
    legacy_input := not (p_input ? 'input_mode' and p_input ? 'resolution');
    provider_value := coalesce(nullif(provider_value,''),'runway');
    input_mode_value := coalesce(nullif(input_mode_value,''),'image');
    resolution_value := coalesce(nullif(resolution_value,''),case model_value
      when 'seedream5_lite' then '2K' else '720p' end);
  elsif input_mode_value='' or resolution_value='' then
    return null;
  end if;
  sku_value := content_factory_private.real_generation_multimodel_sku(
    provider_value,model_value,input_mode_value,duration_value,
    btrim(coalesce(p_input ->> 'format','')),resolution_value,
    audio_value,last_frame_value
  );
  if sku_value is null or p_input ->> 'spend_confirmation'
       is distinct from sku_value ->> 'spend_confirmation' then
    return null;
  end if;
  if legacy_input then
    sku_value:=jsonb_set(
      sku_value,'{ratio}',sku_value -> 'provider_ratio',false
    );
  end if;
  return sku_value;
end;
$$;

revoke all on function
  content_factory_private.real_generation_sku_from_input(text,jsonb)
  from public, anon, authenticated, service_role;

-- Preserve the legacy five-argument API for all installed wrappers. It may
-- normalize only the original three Runway models.
create or replace function content_factory_private.real_generation_sku_config(
  p_model text,p_duration jsonb,p_audio jsonb,p_format text,p_confirmation text
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  model_value text := lower(btrim(coalesce(p_model,'')));
  duration_value integer;
  sku_value jsonb;
begin
  if model_value not in ('seedream5_lite','gen4_turbo','seedance2_fast')
     or jsonb_typeof(p_duration)<>'number'
     or p_duration #>> '{}' !~ '^[0-9]+$'
     or jsonb_typeof(coalesce(p_audio,'false'::jsonb))<>'boolean' then
    return null;
  end if;
  begin duration_value := (p_duration #>> '{}')::integer;
  exception when numeric_value_out_of_range then return null;
  end;
  sku_value := content_factory_private.real_generation_multimodel_sku(
    'runway',model_value,'image',duration_value,p_format,
    case model_value when 'seedream5_lite' then '2K' else '720p' end,
    coalesce((p_audio #>> '{}')::boolean,false),false
  );
  if sku_value is null or p_confirmation is distinct from
       sku_value ->> 'spend_confirmation' then
    return null;
  end if;
  return jsonb_set(sku_value,'{ratio}',sku_value -> 'provider_ratio',false);
end;
$$;

revoke all on function content_factory_private.real_generation_sku_config(
  text,jsonb,jsonb,text,text
) from public, anon, authenticated, service_role;


-- Readiness v4 extends the same append-only receipt ledger. Historical and v3
-- rows retain NULL scope fields and their original hashes; no metadata is
-- fabricated. A v4 receipt is pinned to one project and one exact spec scope.
drop trigger if exists generation_provider_readiness_receipt_append_only
  on content_factory.generation_provider_readiness_receipts;

alter table content_factory.generation_provider_readiness_receipts
  add column if not exists receipt_version text,
  add column if not exists input_mode text,
  add column if not exists format text,
  add column if not exists resolution text,
  add column if not exists audio boolean,
  add column if not exists last_frame boolean,
  add column if not exists estimated_cost_minor bigint,
  add column if not exists credential_configured boolean,
  add column if not exists catalog_version text,
  add column if not exists pricing_version text,
  add column if not exists spend_confirmation text,
  add column if not exists project_id uuid,
  add column if not exists spec_id uuid,
  add column if not exists spec_version integer,
  add column if not exists spec_hash text,
  add column if not exists scope_hash text;

alter table content_factory.generation_provider_readiness_receipts
  alter column estimated_credits drop not null,
  alter column balance_sufficient drop not null,
  alter column daily_quota_available drop not null;

do $$
declare
  constraint_name text;
begin
  for constraint_name in
    select constraint_row.conname
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.generation_provider_readiness_receipts'::regclass
      and constraint_row.contype = 'c'
  loop
    execute format(
      'alter table content_factory.generation_provider_readiness_receipts drop constraint %I',
      constraint_name
    );
  end loop;
end;
$$;

alter table content_factory.generation_provider_readiness_receipts
  add constraint generation_provider_readiness_v3_provider_check
    check (provider in ('runway','google')),
  add constraint generation_provider_readiness_v3_model_check
    check (content_factory_private.generation_catalog_entry(provider,model)
      is not null),
  add constraint generation_provider_readiness_v4_history_or_exact_check
    check (
      (receipt_version is null and input_mode is null and format is null
       and resolution is null and audio is null and last_frame is null
       and estimated_cost_minor is null and credential_configured is null
       and catalog_version is null and pricing_version is null
       and spend_confirmation is null and project_id is null
       and spec_id is null and spec_version is null and spec_hash is null
       and scope_hash is null)
      or
      (receipt_version = 'generation-provider-readiness-receipt-v3'
       and input_mode = 'image'
       and content_factory_private.generation_provider_ratio(
         provider,model,format,resolution
       ) is not null
       and audio is not null and last_frame is not null
       and estimated_cost_minor >= 0
       and credential_configured is not null
       and catalog_version = '2026-08-13.v1'
       and pricing_version in (
         'runway-credits-2026-08-13.v1','google-veo-2026-08-13.v1'
       )
       and length(spend_confirmation) between 16 and 180
       and project_id is null and spec_id is null and spec_version is null
       and spec_hash is null and scope_hash is null)
      or
      (receipt_version = 'generation-provider-readiness-receipt-v4'
       and input_mode = 'image'
       and content_factory_private.generation_provider_ratio(
         provider,model,format,resolution
       ) is not null
       and audio is not null and last_frame is not null
       and estimated_cost_minor >= 0
       and credential_configured is not null
       and catalog_version = '2026-08-13.v1'
       and pricing_version in (
         'runway-credits-2026-08-13.v1','google-veo-2026-08-13.v1'
       )
       and length(spend_confirmation) between 16 and 180
       and project_id is not null and spec_id is not null
       and spec_version between 1 and 100000
       and spec_hash ~ '^[0-9a-f]{64}$'
       and scope_hash ~ '^[0-9a-f]{64}$')
    ),
  add constraint generation_provider_readiness_v3_nullable_facts_check
    check (
      (provider='runway' and estimated_credits is not null
       and balance_sufficient is not null
       and daily_quota_available is not null)
      or
      (provider='google' and (receipt_version is null or
       (estimated_credits is null and balance_sufficient is null
        and daily_quota_available is null)))
    ),
  add constraint generation_provider_readiness_v3_state_check
    check (
      (ready and failure_code is null)
      or (not ready and failure_code is not null)
    ),
  add constraint generation_provider_readiness_v3_ready_facts_check
    check (
      receipt_version is null
      or ready = (
        credential_configured
        and model_available
        and case provider
          when 'runway' then balance_sufficient and daily_quota_available
          else true
        end
      )
    ),
  add constraint generation_provider_readiness_v3_failure_code_check
    check (
      failure_code is null
      or failure_code in (
        'provider_configuration_error','provider_authentication_failed',
        'provider_credits_unavailable','provider_rate_limited',
        'provider_request_rejected','provider_request_failed',
        'provider_response_invalid','model_disabled_by_organization'
      )
    ),
  add constraint generation_provider_readiness_v3_learning_gate_check
    check (
      learning_gate_version ~
        '^[0-9]{4}-[0-9]{2}-[0-9]{2}[.]v[0-9]+$'
    ),
  add constraint generation_provider_readiness_v3_hash_check
    check (receipt_hash ~ '^[0-9a-f]{64}$'),
  add constraint generation_provider_readiness_v3_expiry_check
    check (expires_at = checked_at + interval '15 minutes'),
  add constraint generation_provider_readiness_v2_cost_check
    check (
      receipt_version is not null
      or (
        provider='runway'
        and (
          (model='gen4_turbo' and duration_seconds between 2 and 10
            and estimated_credits=duration_seconds*5)
          or (model='seedance2_fast' and duration_seconds between 4 and 15
            and estimated_credits=duration_seconds*29)
          or (model='seedream5_lite' and duration_seconds=0
            and estimated_credits=4)
        )
        and ready=(balance_sufficient and model_available
          and daily_quota_available)
      )
    );

alter table content_factory.generation_provider_readiness_receipts
  add constraint generation_provider_readiness_v4_project_fk
    foreign key (organization_id,project_id)
      references content_factory.workspace_folders(organization_id,id),
  add constraint generation_provider_readiness_v4_spec_fk
    foreign key (organization_id,spec_id,spec_version,spec_hash)
      references content_factory.generation_spec_versions(
        organization_id,spec_id,spec_version,spec_hash
      );

drop index if exists
  content_factory.generation_provider_readiness_receipts_latest_idx;
create index generation_provider_readiness_receipts_latest_idx
  on content_factory.generation_provider_readiness_receipts (
    organization_id, project_id, spec_id, spec_version, scope_hash,
    provider, model, input_mode, duration_seconds,
    format, resolution, audio, last_frame, pricing_version,
    checked_at desc, id desc
  );

create trigger generation_provider_readiness_receipt_append_only
before update or delete on content_factory.generation_provider_readiness_receipts
for each row execute function content_factory_private
  .guard_generation_provider_readiness_receipt_append_only();

create or replace function public.system_record_generation_provider_readiness(
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
  project_id_value uuid;
  checked_by_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  provider_value text;
  model_value text;
  input_mode_value text;
  duration_value integer;
  format_value text;
  resolution_value text;
  audio_value boolean;
  last_frame_value boolean;
  ready_value boolean;
  estimated_cost_value bigint;
  estimated_credits_value bigint;
  credential_configured_value boolean;
  balance_sufficient_value boolean;
  model_available_value boolean;
  daily_quota_available_value boolean;
  failure_code_value text;
  catalog_version_value text;
  pricing_version_value text;
  learning_gate_version_value text;
  checked_at_value timestamptz;
  expires_at_value timestamptz;
  sku_value jsonb;
  receipt_body jsonb;
  receipt_hash_value text;
  receipt_id_value uuid;
  baseline_claim_value jsonb;
  spec_row content_factory.generation_spec_versions%rowtype;
  v4_required boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id','checked_by','provider','model','input_mode',
       'duration_seconds','format','resolution','audio','last_frame','ready',
       'estimated_cost_minor','estimated_credits','credential_configured',
       'balance_sufficient','model_available','daily_quota_available',
       'failure_code','catalog_version','pricing_version','learning_gate_version'
       ,'spend_confirmation','automatic_generation','automatic_spend',
       'project_id','spec_id','spec_version','spec_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id','checked_by','provider','model','input_mode',
       'duration_seconds','format','resolution','audio','last_frame','ready',
       'estimated_cost_minor','estimated_credits','credential_configured',
       'balance_sufficient','model_available','daily_quota_available',
        'failure_code','catalog_version','pricing_version','learning_gate_version',
        'spend_confirmation','automatic_generation','automatic_spend'
      ]::text[]
      or jsonb_typeof(p_payload -> 'duration_seconds') <> 'number'
      or p_payload ->> 'duration_seconds' !~ '^[0-9]+$'
      or (
        lower(btrim(coalesce(p_payload ->> 'provider','')))='runway'
        and lower(btrim(coalesce(p_payload ->> 'model',''))) in (
          'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
        )
        and (
          not p_payload ?& array[
            'project_id','spec_id','spec_version','spec_hash'
          ]::text[]
          or jsonb_typeof(p_payload -> 'spec_version') <> 'number'
          or p_payload ->> 'spec_version' !~ '^[1-9][0-9]{0,5}$'
        )
      )
      or (
        not (
          lower(btrim(coalesce(p_payload ->> 'provider','')))='runway'
          and lower(btrim(coalesce(p_payload ->> 'model',''))) in (
            'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
          )
        )
        and p_payload ?| array[
          'project_id','spec_id','spec_version','spec_hash'
        ]::text[]
      )
     or jsonb_typeof(p_payload -> 'audio') <> 'boolean'
     or jsonb_typeof(p_payload -> 'last_frame') <> 'boolean'
     or jsonb_typeof(p_payload -> 'ready') <> 'boolean'
     or jsonb_typeof(p_payload -> 'estimated_cost_minor') <> 'number'
     or p_payload ->> 'estimated_cost_minor' !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'estimated_credits')
          not in ('number','null')
     or (jsonb_typeof(p_payload -> 'estimated_credits')='number'
       and p_payload ->> 'estimated_credits' !~ '^[0-9]+$')
     or jsonb_typeof(p_payload -> 'credential_configured') <> 'boolean'
     or jsonb_typeof(p_payload -> 'balance_sufficient')
          not in ('boolean','null')
     or jsonb_typeof(p_payload -> 'model_available') <> 'boolean'
     or jsonb_typeof(p_payload -> 'daily_quota_available')
          not in ('boolean','null')
     or jsonb_typeof(p_payload -> 'failure_code') not in ('string','null')
     or p_payload -> 'automatic_generation' is distinct from 'false'::jsonb
     or p_payload -> 'automatic_spend' is distinct from 'false'::jsonb then
    raise exception using errcode='22023',
      message='generation_provider_readiness_receipt_invalid';
  end if;

  organization_id_value := content_factory_private.require_uuid(
    p_payload,'organization_id'
  );
  checked_by_value := content_factory_private.require_uuid(
    p_payload,'checked_by'
  );
  provider_value := lower(btrim(p_payload ->> 'provider'));
  model_value := lower(btrim(p_payload ->> 'model'));
  v4_required:=provider_value='runway' and model_value in (
    'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
  );
  if v4_required then
    project_id_value := content_factory_private.require_uuid(
      p_payload,'project_id'
    );
    spec_id_value := content_factory_private.require_uuid(p_payload,'spec_id');
    spec_hash_value := lower(btrim(coalesce(p_payload ->> 'spec_hash','')));
  end if;
  input_mode_value := lower(btrim(p_payload ->> 'input_mode'));
  format_value := btrim(p_payload ->> 'format');
  resolution_value := btrim(p_payload ->> 'resolution');
  audio_value := (p_payload ->> 'audio')::boolean;
  last_frame_value := (p_payload ->> 'last_frame')::boolean;
  ready_value := (p_payload ->> 'ready')::boolean;
  credential_configured_value :=
    (p_payload ->> 'credential_configured')::boolean;
  model_available_value := (p_payload ->> 'model_available')::boolean;
  balance_sufficient_value := case
    when p_payload -> 'balance_sufficient'='null'::jsonb then null
    else (p_payload ->> 'balance_sufficient')::boolean end;
  daily_quota_available_value := case
    when p_payload -> 'daily_quota_available'='null'::jsonb then null
    else (p_payload ->> 'daily_quota_available')::boolean end;
  failure_code_value := nullif(btrim(coalesce(
    p_payload ->> 'failure_code',''
  )), '');
  catalog_version_value := btrim(p_payload ->> 'catalog_version');
  pricing_version_value := btrim(p_payload ->> 'pricing_version');
  learning_gate_version_value := btrim(
    p_payload ->> 'learning_gate_version'
  );
  begin
    duration_value := (p_payload ->> 'duration_seconds')::integer;
    spec_version_value := case when v4_required then
      (p_payload ->> 'spec_version')::integer else null end;
    estimated_cost_value :=
      (p_payload ->> 'estimated_cost_minor')::bigint;
    estimated_credits_value := case
      when p_payload -> 'estimated_credits'='null'::jsonb then null
      else (p_payload ->> 'estimated_credits')::bigint end;
  exception when numeric_value_out_of_range then
    raise exception using errcode='22023',
      message='generation_provider_readiness_receipt_invalid';
  end;

  if v4_required and spec_hash_value!~'^[0-9a-f]{64}$' then
    raise exception using errcode='22023',
      message='generation_provider_readiness_receipt_invalid';
  end if;

  sku_value := content_factory_private.real_generation_multimodel_sku(
    provider_value,model_value,input_mode_value,duration_value,format_value,
    resolution_value,audio_value,last_frame_value
  );
  if sku_value is null
     or catalog_version_value is distinct from
          content_factory_private.generation_catalog_version()
     or pricing_version_value is distinct from sku_value ->> 'pricing_version'
     or p_payload ->> 'spend_confirmation' is distinct from
          sku_value ->> 'spend_confirmation'
     or estimated_cost_value::text is distinct from
          sku_value ->> 'estimated_cost_minor'
     or to_jsonb(estimated_credits_value) is distinct from
          sku_value -> 'estimated_credits'
     or learning_gate_version_value !~
          '^[0-9]{4}-[0-9]{2}-[0-9]{2}[.]v[0-9]+$'
     or (provider_value='runway' and (
       balance_sufficient_value is null or
       daily_quota_available_value is null))
     or (provider_value='google' and (
       estimated_credits_value is not null or
       balance_sufficient_value is not null or
       daily_quota_available_value is not null))
     or ready_value is distinct from (
       credential_configured_value and model_available_value and
       case provider_value when 'runway' then
         balance_sufficient_value and daily_quota_available_value
       else true end
     )
     or (ready_value and failure_code_value is not null)
     or (not ready_value and failure_code_value not in (
       'provider_configuration_error','provider_authentication_failed',
       'provider_credits_unavailable','provider_rate_limited',
       'provider_request_rejected','provider_request_failed',
       'provider_response_invalid','model_disabled_by_organization'
     ))
      then
    raise exception using errcode='22023',
      message='generation_provider_readiness_receipt_invalid';
  end if;

  if v4_required then
    baseline_claim_value:=content_factory_private
      .generation_multimodel_baseline_claim_v2(
        organization_id_value,project_id_value,checked_by_value,
        spec_id_value,spec_version_value,spec_hash_value
      );
    select version.* into spec_row
    from content_factory.generation_spec_versions version
    where version.organization_id=organization_id_value
      and version.spec_id=spec_id_value
      and version.spec_version=spec_version_value
      and version.spec_hash=spec_hash_value
    for share;
    if spec_row.version_id is null
       or spec_row.provider is distinct from provider_value
       or spec_row.model is distinct from model_value
       or spec_row.input_mode is distinct from input_mode_value
       or spec_row.duration_seconds is distinct from duration_value
       or spec_row.format is distinct from format_value
       or spec_row.resolution is distinct from resolution_value
       or spec_row.audio is distinct from audio_value
       or spec_row.last_frame is distinct from last_frame_value
       or baseline_claim_value ->> 'scope_hash' is distinct from
            content_factory_private.json_hash(spec_row.exact_scope) then
      raise exception using errcode='55000',
        message='generation_provider_readiness_scope_stale';
    end if;
  elsif not exists (
    select 1 from content_factory.memberships membership
    join content_factory.organizations organization
      on organization.id=membership.organization_id
     and organization.status='active'
    join content_factory.profiles profile
      on profile.id=membership.profile_id and profile.status='active'
    where membership.organization_id=organization_id_value
      and membership.profile_id=checked_by_value
      and membership.status='active'
  ) then
    raise exception using errcode='42501',message='role_not_allowed';
  end if;

  checked_at_value := clock_timestamp();
  expires_at_value := checked_at_value + interval '15 minutes';
  receipt_id_value := extensions.gen_random_uuid();
  receipt_body := jsonb_build_object(
    'version',case when v4_required then
      'generation-provider-readiness-receipt-v4'
      else 'generation-provider-readiness-receipt-v3' end,
    'receipt_id',receipt_id_value,
    'organization_id',organization_id_value,
    'checked_by',checked_by_value,
    'provider',provider_value,
    'model',model_value,
    'input_mode',input_mode_value,
    'duration_seconds',duration_value,
    'format',format_value,
    'resolution',resolution_value,
    'audio',audio_value,
    'last_frame',last_frame_value,
    'ready',ready_value,
    'estimated_cost_minor',estimated_cost_value,
    'estimated_credits',estimated_credits_value,
    'credential_configured',credential_configured_value,
    'balance_sufficient',balance_sufficient_value,
    'model_available',model_available_value,
    'daily_quota_available',daily_quota_available_value,
    'failure_code',failure_code_value,
    'catalog_version',catalog_version_value,
    'pricing_version',pricing_version_value,
    'learning_gate_version',learning_gate_version_value,
    'checked_at',checked_at_value,
    'expires_at',expires_at_value,
    'status',case when ready_value then 'ready' else 'blocked' end,
    'fresh',true,
    'spend_confirmation',sku_value ->> 'spend_confirmation',
    'automatic_generation',false,
    'automatic_spend',false
  );
  if v4_required then
    receipt_body:=receipt_body || jsonb_build_object(
      'project_id',project_id_value,'spec_id',spec_id_value,
      'spec_version',spec_version_value,'spec_hash',spec_hash_value,
      'scope_hash',baseline_claim_value ->> 'scope_hash'
    );
  end if;
  receipt_hash_value := content_factory_private.json_hash(receipt_body);

  insert into content_factory.generation_provider_readiness_receipts (
    id,organization_id,provider,model,duration_seconds,ready,estimated_credits,
    balance_sufficient,model_available,daily_quota_available,failure_code,
    learning_gate_version,checked_by,checked_at,expires_at,receipt_hash,
    receipt_version,input_mode,format,resolution,audio,last_frame,
    estimated_cost_minor,credential_configured,catalog_version,
    pricing_version,spend_confirmation,project_id,spec_id,spec_version,
    spec_hash,scope_hash
  ) values (
    receipt_id_value,organization_id_value,provider_value,model_value,duration_value,ready_value,
    estimated_credits_value,balance_sufficient_value,model_available_value,
    daily_quota_available_value,failure_code_value,learning_gate_version_value,
    checked_by_value,checked_at_value,expires_at_value,receipt_hash_value,
    case when v4_required then 'generation-provider-readiness-receipt-v4'
      else 'generation-provider-readiness-receipt-v3' end,
    input_mode_value,format_value,
    resolution_value,audio_value,last_frame_value,estimated_cost_value,
    credential_configured_value,catalog_version_value,pricing_version_value,
    sku_value ->> 'spend_confirmation',project_id_value,spec_id_value,
    spec_version_value,spec_hash_value,case when v4_required then
      baseline_claim_value ->> 'scope_hash' else null end
  );

  return receipt_body || jsonb_build_object('receipt_hash',receipt_hash_value);
end;
$$;

revoke all on function public.system_record_generation_provider_readiness(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_record_generation_provider_readiness(jsonb)
  to service_role;

-- Canonical v2 generation-spec scope. The 17 keys are intentionally exact:
-- provider output ratio (`ratio`) is never silently inferred from the legacy
-- publishing field (`format`). This freeze authorizes image-mode only.
create or replace function content_factory_private.generation_spec_scope_v2(
  p_scope jsonb
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  provider_value text;
  model_value text;
  input_mode_value text;
  duration_value integer;
  format_value text;
  ratio_value text;
  resolution_value text;
  audio_value boolean;
  spoken_dialogue_value boolean;
  reference_count_value integer;
  reference_video_value boolean;
  first_frame_value boolean;
  last_frame_value boolean;
  media_count_value integer;
  primary_media_id_value uuid;
  media_ids_value uuid[];
  sku_value jsonb;
begin
  if jsonb_typeof(p_scope) <> 'object'
     or p_scope - array[
       'primary_media_id','media_ids','platform','provider','model','input_mode',
       'duration_seconds','product_category','format','ratio','resolution','audio',
       'spoken_dialogue','reference_count','reference_video','first_frame',
       'last_frame'
     ]::text[] <> '{}'::jsonb
     or not p_scope ?& array[
       'primary_media_id','media_ids','platform','provider','model','input_mode',
       'duration_seconds','product_category','format','ratio','resolution','audio',
       'spoken_dialogue','reference_count','reference_video','first_frame',
       'last_frame'
     ]::text[]
     or jsonb_typeof(p_scope -> 'media_ids') <> 'array'
     or jsonb_array_length(p_scope -> 'media_ids') not between 1 and 5
     or jsonb_typeof(p_scope -> 'duration_seconds') <> 'number'
     or p_scope ->> 'duration_seconds' !~ '^[0-9]+$'
     or jsonb_typeof(p_scope -> 'audio') <> 'boolean'
     or jsonb_typeof(p_scope -> 'spoken_dialogue') <> 'boolean'
     or jsonb_typeof(p_scope -> 'reference_count') <> 'number'
     or p_scope ->> 'reference_count' !~ '^[0-9]+$'
     or jsonb_typeof(p_scope -> 'reference_video') <> 'boolean'
     or jsonb_typeof(p_scope -> 'first_frame') <> 'boolean'
     or jsonb_typeof(p_scope -> 'last_frame') <> 'boolean' then
    return null;
  end if;
  begin
    primary_media_id_value := (p_scope ->> 'primary_media_id')::uuid;
    select array_agg(item.value::uuid order by item.ordinality)
      into media_ids_value
    from jsonb_array_elements_text(p_scope -> 'media_ids')
      with ordinality item(value,ordinality);
    duration_value := (p_scope ->> 'duration_seconds')::integer;
    reference_count_value := (p_scope ->> 'reference_count')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    return null;
  end;
  media_count_value := cardinality(media_ids_value);
  if media_ids_value[1] is distinct from primary_media_id_value
     or media_count_value <> (
       select count(distinct media_id)
       from unnest(media_ids_value) selected(media_id)
     ) then
    return null;
  end if;
  provider_value := lower(btrim(p_scope ->> 'provider'));
  model_value := lower(btrim(p_scope ->> 'model'));
  input_mode_value := lower(btrim(p_scope ->> 'input_mode'));
  format_value := btrim(p_scope ->> 'format');
  ratio_value := btrim(p_scope ->> 'ratio');
  resolution_value := btrim(p_scope ->> 'resolution');
  audio_value := (p_scope ->> 'audio')::boolean;
  spoken_dialogue_value := (p_scope ->> 'spoken_dialogue')::boolean;
  reference_video_value := (p_scope ->> 'reference_video')::boolean;
  first_frame_value := (p_scope ->> 'first_frame')::boolean;
  last_frame_value := (p_scope ->> 'last_frame')::boolean;
  sku_value := content_factory_private.real_generation_multimodel_sku(
    provider_value,model_value,input_mode_value,duration_value,format_value,
    resolution_value,audio_value,last_frame_value
  );
  if sku_value is null
     or ratio_value is distinct from format_value
     or reference_video_value
     or spoken_dialogue_value is distinct from (case model_value
       when 'seedance2_fast' then audio_value
       when 'seedance2_mini' then audio_value
       when 'veo3.1_fast' then audio_value
       when 'gemini_omni_flash' then audio_value
       when 'veo-3.1-lite-generate-preview' then audio_value
       else false end)
     or (case model_value
       when 'seedream5_lite' then not (
         media_count_value between 1 and 5
         and reference_count_value=media_count_value
         and not first_frame_value and not last_frame_value
         and not spoken_dialogue_value)
       when 'gen4_turbo' then not (
         media_count_value=1 and reference_count_value=0
         and first_frame_value and not last_frame_value
         and not spoken_dialogue_value)
       when 'seedance2_fast' then not (
         media_count_value between 1 and 5
         and reference_count_value=media_count_value
         and not first_frame_value and not last_frame_value
       )
       when 'gen4.5' then not (
         media_count_value=1 and reference_count_value=0
         and first_frame_value and not last_frame_value
         and not spoken_dialogue_value)
       when 'seedance2_mini' then not (
         media_count_value between 1 and 5
         and reference_count_value=media_count_value
         and not first_frame_value and not last_frame_value)
       when 'veo3.1_fast' then not (
         media_count_value=case when last_frame_value then 2 else 1 end
         and reference_count_value=0 and first_frame_value)
       when 'gemini_omni_flash' then not (
         media_count_value=1 and reference_count_value=0
         and first_frame_value and not last_frame_value)
       when 'veo-3.1-lite-generate-preview' then not (
         provider_value='google'
         and media_count_value=case when last_frame_value then 2 else 1 end
         and reference_count_value=0 and first_frame_value)
       else true
     end) then
    return null;
  end if;
  return jsonb_build_object(
    'primary_media_id',primary_media_id_value,
    'media_ids',to_jsonb(media_ids_value),
    'platform',lower(btrim(p_scope ->> 'platform')),
    'provider',provider_value,
    'model',model_value,
    'input_mode',input_mode_value,
    'duration_seconds',duration_value,
    'product_category',lower(btrim(p_scope ->> 'product_category')),
    'format',format_value,
    'ratio',ratio_value,
    'resolution',resolution_value,
    'audio',audio_value,
    'spoken_dialogue',spoken_dialogue_value,
    'reference_count',reference_count_value,
    'reference_video',reference_video_value,
    'first_frame',first_frame_value,
    'last_frame',last_frame_value
  );
end;
$$;

revoke all on function content_factory_private.generation_spec_scope_v2(jsonb)
  from public, anon, authenticated, service_role;

alter table content_factory.generation_spec_versions
  add column if not exists spec_contract_version text,
  add column if not exists provider text,
  add column if not exists input_mode text,
  add column if not exists ratio text,
  add column if not exists resolution text,
  add column if not exists spoken_dialogue boolean,
  add column if not exists reference_count integer,
  add column if not exists reference_video boolean,
  add column if not exists first_frame boolean,
  add column if not exists last_frame boolean;

do $$
declare
  constraint_name text;
  constraint_definition text;
begin
  for constraint_name,constraint_definition in
    select constraint_row.conname,
           lower(pg_catalog.pg_get_constraintdef(constraint_row.oid))
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.generation_spec_versions'::regclass
      and constraint_row.contype='c'
  loop
    if position('exact_scope' in constraint_definition)>0
       or position('model = any' in constraint_definition)>0
       or position('(model =' in constraint_definition)>0
       or position('format' in constraint_definition)>0
       or position('duration_seconds' in constraint_definition)>0 then
      execute format(
        'alter table content_factory.generation_spec_versions drop constraint %I',
        constraint_name
      );
    end if;
  end loop;
end;
$$;

alter table content_factory.generation_spec_versions
  add constraint generation_spec_versions_v1_or_v2_scope_check
  check (
    (
      spec_contract_version is null and provider is null
      and input_mode is null and ratio is null and resolution is null
      and spoken_dialogue is null and reference_count is null
      and reference_video is null and first_frame is null and last_frame is null
      and model in ('gen4_turbo','seedance2_fast','seedream5_lite')
      and exact_scope = jsonb_build_object(
        'primary_media_id',primary_media_id,
        'media_ids',to_jsonb(media_ids),
        'platform',platform,'model',model,
        'duration_seconds',duration_seconds,
        'product_category',product_category,'format',format,'audio',audio
      )
    )
    or
    (
      spec_contract_version='generation-spec-scope-v2'
      and provider is not null and input_mode is not null
      and ratio is not null and resolution is not null
      and spoken_dialogue is not null and reference_count is not null
      and reference_video is not null and first_frame is not null
      and last_frame is not null
      and exact_scope = content_factory_private.generation_spec_scope_v2(
        exact_scope
      )
      and exact_scope = jsonb_build_object(
        'primary_media_id',primary_media_id,
        'media_ids',to_jsonb(media_ids),
        'platform',platform,'provider',provider,'model',model,
        'input_mode',input_mode,'duration_seconds',duration_seconds,
        'product_category',product_category,'format',format,'ratio',ratio,
        'resolution',resolution,'audio',audio,
        'spoken_dialogue',spoken_dialogue,'reference_count',reference_count,
        'reference_video',reference_video,'first_frame',first_frame,
        'last_frame',last_frame
      )
    )
  );

create index if not exists generation_spec_versions_provider_model_scope_idx
  on content_factory.generation_spec_versions(
    organization_id,provider,model,created_at desc,version_id desc
  ) where spec_contract_version='generation-spec-scope-v2';

create or replace function content_factory_private.bind_generation_spec_scope_v2()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  scope_value jsonb;
begin
  scope_value := content_factory_private.generation_spec_scope_v2(
    new.exact_scope
  );
  if scope_value is null then
    return new;
  end if;
  new.spec_contract_version := 'generation-spec-scope-v2';
  new.provider := scope_value ->> 'provider';
  new.input_mode := scope_value ->> 'input_mode';
  new.ratio := scope_value ->> 'ratio';
  new.resolution := scope_value ->> 'resolution';
  new.spoken_dialogue := (scope_value ->> 'spoken_dialogue')::boolean;
  new.reference_count := (scope_value ->> 'reference_count')::integer;
  new.reference_video := (scope_value ->> 'reference_video')::boolean;
  new.first_frame := (scope_value ->> 'first_frame')::boolean;
  new.last_frame := (scope_value ->> 'last_frame')::boolean;
  return new;
end;
$$;

drop trigger if exists a_generation_spec_scope_v2_bind
  on content_factory.generation_spec_versions;
create trigger a_generation_spec_scope_v2_bind
before insert on content_factory.generation_spec_versions
for each row execute function
  content_factory_private.bind_generation_spec_scope_v2();

revoke all on function content_factory_private.bind_generation_spec_scope_v2()
  from public, anon, authenticated, service_role;

-- Preserve the mature research/learning/repair compiler and replace only its
-- closed v1 scope seams. Every replacement is exact and installation aborts
-- if the expected historical owner is not present.
do $patch_generation_spec_v2$
declare
  function_definition text;
  patched_definition text;
  old_fragment text;
  new_fragment text;
begin
  select pg_catalog.pg_get_functiondef(
    'content_factory_private.create_generation_spec_version(uuid,uuid,uuid,jsonb,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,uuid,text,uuid)'::regprocedure
  ) into function_definition;
  patched_definition := function_definition;

  old_fragment := $old$
  if jsonb_typeof(exact_scope_value) <> 'object'
     or exact_scope_value - array[
       'primary_media_id', 'media_ids', 'platform', 'model',
       'duration_seconds', 'product_category', 'format', 'audio'
     ]::text[] <> '{}'::jsonb
     or not exact_scope_value ?& array[
       'primary_media_id', 'media_ids', 'platform', 'model',
       'duration_seconds', 'product_category', 'format', 'audio'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;$old$;
  new_fragment := $new$
  normalized_scope := content_factory_private.generation_spec_scope_v2(
    exact_scope_value
  );
  if normalized_scope is null and (
       jsonb_typeof(exact_scope_value) <> 'object'
       or exact_scope_value - array[
         'primary_media_id', 'media_ids', 'platform', 'model',
         'duration_seconds', 'product_category', 'format', 'audio'
       ]::text[] <> '{}'::jsonb
       or not exact_scope_value ?& array[
         'primary_media_id', 'media_ids', 'platform', 'model',
         'duration_seconds', 'product_category', 'format', 'audio'
       ]::text[]
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;$new$;
  if position(old_fragment in patched_definition)=0 then
    raise exception using errcode='55000',
      message='generation_spec_v2_patch_shape_target_invalid';
  end if;
  patched_definition := replace(
    patched_definition,old_fragment,new_fragment
  );

  old_fragment := $old$
  if platform_value not in (
       'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or model_value not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or product_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     )
     or format_value not in ('9:16', '16:9', '1:1')
     or not (
       (model_value = 'gen4_turbo'
        and duration_value in (2, 5, 8, 10) and not audio_value)
       or (model_value = 'seedance2_fast'
        and duration_value in (4, 8, 12, 15) and audio_value
        and format_value = '9:16')
       or (model_value = 'seedream5_lite'
        and duration_value = 0 and not audio_value
        and format_value = '1:1')
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;$old$;
  new_fragment := $new$
  if platform_value not in (
       'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or product_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     )
     or (
       normalized_scope is null and (
         format_value not in ('9:16', '16:9', '1:1')
         or not (
           (model_value = 'gen4_turbo'
            and duration_value in (2, 5, 8, 10) and not audio_value)
           or (model_value = 'seedance2_fast'
            and duration_value in (4, 8, 12, 15) and audio_value
            and format_value = '9:16')
           or (model_value = 'seedream5_lite'
            and duration_value = 0 and not audio_value
            and format_value = '1:1')
         )
       )
     )
     or (
       normalized_scope is not null and (
         normalized_scope ->> 'platform' is distinct from platform_value
         or normalized_scope ->> 'model' is distinct from model_value
         or normalized_scope ->> 'product_category'
              is distinct from product_category_value
         or normalized_scope ->> 'format' is distinct from format_value
         or normalized_scope -> 'duration_seconds'
              is distinct from to_jsonb(duration_value)
         or normalized_scope -> 'audio' is distinct from to_jsonb(audio_value)
       )
     ) then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;$new$;
  if position(old_fragment in patched_definition)=0 then
    raise exception using errcode='55000',
      message='generation_spec_v2_patch_sku_target_invalid';
  end if;
  patched_definition := replace(
    patched_definition,old_fragment,new_fragment
  );

  old_fragment := $old$
  normalized_scope := jsonb_build_object(
    'primary_media_id', primary_media_id_value,
    'media_ids', to_jsonb(media_ids_value),
    'platform', platform_value,
    'model', model_value,
    'duration_seconds', duration_value,
    'product_category', product_category_value,
    'format', format_value,
    'audio', audio_value
  );$old$;
  new_fragment := $new$
  normalized_scope := coalesce(normalized_scope, jsonb_build_object(
    'primary_media_id', primary_media_id_value,
    'media_ids', to_jsonb(media_ids_value),
    'platform', platform_value,
    'model', model_value,
    'duration_seconds', duration_value,
    'product_category', product_category_value,
    'format', format_value,
    'audio', audio_value
  ));$new$;
  if position(old_fragment in patched_definition)=0 then
    raise exception using errcode='55000',
      message='generation_spec_v2_patch_normalization_target_invalid';
  end if;
  patched_definition := replace(
    patched_definition,old_fragment,new_fragment
  );

  old_fragment := $old$or length(prompt_value) > (case model_value
       when 'gen4_turbo' then 1000 else 1200 end)$old$;
  new_fragment := $new$or length(prompt_value) > (case model_value
       when 'gen4_turbo' then 1000
       when 'gen4.5' then 1000
       when 'seedance2_mini' then 3500
       when 'veo3.1_fast' then 1000
       when 'gemini_omni_flash' then 4000
       when 'veo-3.1-lite-generate-preview' then 1024
       else 1200 end)$new$;
  if position(old_fragment in patched_definition)=0 then
    raise exception using errcode='55000',
      message='generation_spec_v2_patch_prompt_limit_target_invalid';
  end if;
  patched_definition := replace(
    patched_definition,old_fragment,new_fragment
  );

  old_fragment := $old$'schema_version', 'generation-spec-v1',$old$;
  new_fragment := $new$'schema_version', case
      when normalized_scope ? 'provider' then 'generation-spec-v2'
      else 'generation-spec-v1' end,$new$;
  if position(old_fragment in patched_definition)=0 then
    raise exception using errcode='55000',
      message='generation_spec_v2_patch_hash_target_invalid';
  end if;
  patched_definition := replace(
    patched_definition,old_fragment,new_fragment
  );
  execute patched_definition;
end;
$patch_generation_spec_v2$;

create or replace function content_factory_private.generation_selection_snapshot_valid(
  p_snapshot jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select coalesce(
    jsonb_typeof(p_snapshot)='object'
    and p_snapshot - array[
      'provider','model','model_public_label','selection_source',
      'recommendation_reason_codes','recommendation_warning_codes',
      'recommendation_catalog_version','pricing_version',
      'estimated_cost_minor','requested_duration_seconds','requested_ratio',
      'requested_resolution','requested_audio','input_mode','reference_count',
      'acceptance_status_at_launch','provider_readiness_receipt_id'
    ]::text[]='{}'::jsonb
    and p_snapshot ?& array[
      'provider','model','model_public_label','selection_source',
      'recommendation_reason_codes','recommendation_warning_codes',
      'recommendation_catalog_version','pricing_version',
      'estimated_cost_minor','requested_duration_seconds','requested_ratio',
      'requested_resolution','requested_audio','input_mode','reference_count',
      'acceptance_status_at_launch','provider_readiness_receipt_id'
    ]::text[]
    and jsonb_typeof(p_snapshot -> 'provider')='string'
    and p_snapshot ->> 'provider' = btrim(p_snapshot ->> 'provider')
    and p_snapshot ->> 'provider' ~ '^[a-z][a-z0-9_-]{0,31}$'
    and jsonb_typeof(p_snapshot -> 'model')='string'
    and p_snapshot ->> 'model' = btrim(p_snapshot ->> 'model')
    and p_snapshot ->> 'model' ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
    and content_factory_private.generation_catalog_entry(
      p_snapshot ->> 'provider',p_snapshot ->> 'model'
    ) is not null
    and jsonb_typeof(p_snapshot -> 'model_public_label')='string'
    and p_snapshot ->> 'model_public_label' =
      btrim(p_snapshot ->> 'model_public_label')
    and length(p_snapshot ->> 'model_public_label') between 1 and 96
    and p_snapshot ->> 'model_public_label' !~ '[[:cntrl:]]'
    and p_snapshot ->> 'model_public_label' =
      content_factory_private.generation_catalog_entry(
        p_snapshot ->> 'provider',p_snapshot ->> 'model'
      ) ->> 'public_label'
    and jsonb_typeof(p_snapshot -> 'selection_source')='string'
    and p_snapshot ->> 'selection_source' =
      btrim(p_snapshot ->> 'selection_source')
    and jsonb_typeof(p_snapshot -> 'recommendation_reason_codes')='array'
    and jsonb_array_length(p_snapshot -> 'recommendation_reason_codes')<=32
    and not exists (
      select 1
      from jsonb_array_elements(p_snapshot -> 'recommendation_reason_codes') item
      where jsonb_typeof(item.value)<>'string'
        or item.value #>> '{}' <> btrim(item.value #>> '{}')
        or item.value #>> '{}' !~ '^[a-z][a-z0-9_]{0,63}$'
    )
    and not exists (
      select 1
      from jsonb_array_elements_text(
        p_snapshot -> 'recommendation_reason_codes'
      ) item(value)
      group by item.value having count(*)>1
    )
    and (select coalesce(sum(length(item.value)),0)
      from jsonb_array_elements_text(
        p_snapshot -> 'recommendation_reason_codes'
      ) item(value))<=1024
    and jsonb_typeof(p_snapshot -> 'recommendation_warning_codes')='array'
    and jsonb_array_length(p_snapshot -> 'recommendation_warning_codes')<=32
    and not exists (
      select 1
      from jsonb_array_elements(p_snapshot -> 'recommendation_warning_codes') item
      where jsonb_typeof(item.value)<>'string'
        or item.value #>> '{}' <> btrim(item.value #>> '{}')
        or item.value #>> '{}' !~ '^[a-z][a-z0-9_]{0,63}$'
    )
    and not exists (
      select 1
      from jsonb_array_elements_text(
        p_snapshot -> 'recommendation_warning_codes'
      ) item(value)
      group by item.value having count(*)>1
    )
    and (select coalesce(sum(length(item.value)),0)
      from jsonb_array_elements_text(
        p_snapshot -> 'recommendation_warning_codes'
      ) item(value))<=1024
    and p_snapshot ->> 'selection_source' in (
      'system_recommendation','research_recommendation',
      'performance_recommendation','manual_choice','alternative_after_block'
    )
    and p_snapshot ->> 'acceptance_status_at_launch' in (
      'accepted','needs_revalidation','unproven'
    )
    and jsonb_typeof(p_snapshot -> 'estimated_cost_minor')='number'
    and p_snapshot ->> 'estimated_cost_minor' ~ '^[0-9]+$'
    and (p_snapshot ->> 'estimated_cost_minor')::numeric
      between 0 and 9007199254740991
    and jsonb_typeof(p_snapshot -> 'requested_duration_seconds')='number'
    and p_snapshot ->> 'requested_duration_seconds' ~ '^[0-9]+$'
    and (p_snapshot ->> 'requested_duration_seconds')::numeric
      between 0 and 3600
    and jsonb_typeof(p_snapshot -> 'requested_ratio')='string'
    and p_snapshot ->> 'requested_ratio' =
      btrim(p_snapshot ->> 'requested_ratio')
    and jsonb_typeof(p_snapshot -> 'requested_resolution')='string'
    and p_snapshot ->> 'requested_resolution' =
      btrim(p_snapshot ->> 'requested_resolution')
    and jsonb_typeof(p_snapshot -> 'requested_audio')='boolean'
    and jsonb_typeof(p_snapshot -> 'reference_count')='number'
    and p_snapshot ->> 'reference_count' ~ '^[0-9]+$'
    and (p_snapshot ->> 'reference_count')::numeric between 0 and 64
    and jsonb_typeof(p_snapshot -> 'input_mode')='string'
    and p_snapshot ->> 'input_mode' in ('text','image','video')
    and p_snapshot ->> 'requested_ratio' ~ '^[0-9]{1,4}:[0-9]{1,4}$'
    and p_snapshot ->> 'requested_resolution' ~ '^([0-9]{3,4}p|[1-9][0-9]?K)$'
    and p_snapshot ->> 'provider_readiness_receipt_id' ~
      '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
    and jsonb_typeof(p_snapshot -> 'provider_readiness_receipt_id')='string'
    and jsonb_typeof(p_snapshot -> 'recommendation_catalog_version')='string'
    and p_snapshot ->> 'recommendation_catalog_version' =
      btrim(p_snapshot ->> 'recommendation_catalog_version')
    and jsonb_typeof(p_snapshot -> 'pricing_version')='string'
    and p_snapshot ->> 'pricing_version' = btrim(p_snapshot ->> 'pricing_version')
    and p_snapshot ->> 'recommendation_catalog_version' ~
      '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
    and p_snapshot ->> 'pricing_version' ~
      '^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$'
    and p_snapshot ->> 'recommendation_catalog_version' =
      content_factory_private.generation_catalog_version()
    and p_snapshot ->> 'pricing_version' =
      content_factory_private.generation_catalog_entry(
        p_snapshot ->> 'provider',p_snapshot ->> 'model'
      ) ->> 'pricing_version',
    false
  )
$$;

revoke all on function
  content_factory_private.generation_selection_snapshot_valid(jsonb)
  from public, anon, authenticated, service_role;

create table if not exists content_factory.generation_job_selection_snapshots (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    batch_id uuid not null,
    generation_job_id uuid not null,
    spec_id uuid not null,
    spec_version integer not null,
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    scope_hash text not null check (scope_hash ~ '^[0-9a-f]{64}$'),
    readiness_receipt_id uuid not null,
    readiness_receipt_hash text not null check (
      readiness_receipt_hash ~ '^[0-9a-f]{64}$'
    ),
    snapshot_version text not null check (
      snapshot_version='generation-selection-snapshot-v1'
    ),
    selection_snapshot jsonb not null check (
      content_factory_private.generation_selection_snapshot_valid(
        selection_snapshot
      )
    ),
    snapshot_hash text not null check (snapshot_hash ~ '^[0-9a-f]{64}$'),
    live_claim_snapshot jsonb not null check (
      jsonb_typeof(live_claim_snapshot)='object'
      and length(live_claim_snapshot::text)<=131072
    ),
    live_claim_snapshot_hash text not null check (
      live_claim_snapshot_hash ~ '^[0-9a-f]{64}$'
    ),
    provider text not null,
    model text not null,
    content_kind text not null check (content_kind in ('photo','video')),
    selection_source text not null check (selection_source in (
      'system_recommendation','research_recommendation',
      'performance_recommendation','manual_choice','alternative_after_block'
    )),
    quality_status text not null check (quality_status in (
      'accepted','needs_revalidation','unproven'
    )),
    catalog_version text not null,
    pricing_version text not null,
    estimated_cost_minor bigint not null check (estimated_cost_minor>=0),
    estimated_credits bigint check (estimated_credits>=0),
    bound_by uuid not null,
    bound_at timestamptz not null default clock_timestamp(),
    unique (organization_id,batch_id),
    unique (organization_id,generation_job_id),
    unique (readiness_receipt_id),
    foreign key (organization_id,batch_id)
      references content_factory.generation_batches(organization_id,id),
    foreign key (organization_id,generation_job_id)
      references content_factory.generation_jobs(organization_id,id),
    foreign key (organization_id,spec_id,spec_version,spec_hash)
      references content_factory.generation_spec_versions(
        organization_id,spec_id,spec_version,spec_hash
      ),
    foreign key (readiness_receipt_id)
      references content_factory.generation_provider_readiness_receipts(id),
    foreign key (organization_id,bound_by)
      references content_factory.memberships(organization_id,profile_id),
    check (snapshot_hash=content_factory_private.json_hash(selection_snapshot)),
    check (
      live_claim_snapshot ? 'snapshot_hash'
      and live_claim_snapshot ->> 'snapshot_hash'=live_claim_snapshot_hash
      and live_claim_snapshot_hash=content_factory_private.json_hash(
        live_claim_snapshot-'snapshot_hash'
      )
    ),
    check (provider=selection_snapshot ->> 'provider'),
    check (model=selection_snapshot ->> 'model'),
    check (selection_source=selection_snapshot ->> 'selection_source'),
    check (quality_status=selection_snapshot ->> 'acceptance_status_at_launch'),
    check (catalog_version=
      selection_snapshot ->> 'recommendation_catalog_version'),
    check (pricing_version=selection_snapshot ->> 'pricing_version'),
    check (estimated_cost_minor::text=
      selection_snapshot ->> 'estimated_cost_minor'),
    check (readiness_receipt_id::text=
      selection_snapshot ->> 'provider_readiness_receipt_id')
);

create index if not exists generation_job_selection_snapshot_archive_idx
  on content_factory.generation_job_selection_snapshots(
    organization_id,project_id,provider,model,selection_source,quality_status,
    bound_at desc,id desc
  );

alter table content_factory.generation_job_selection_snapshots
  enable row level security;
revoke all on content_factory.generation_job_selection_snapshots
  from public, anon, authenticated, service_role;
grant all on content_factory.generation_job_selection_snapshots to service_role;

create or replace function content_factory_private.guard_generation_selection_snapshot_append_only()
returns trigger language plpgsql set search_path = '' as $$
begin
  raise exception using errcode='55000',
    message='generation_selection_snapshot_append_only';
end;
$$;

create trigger generation_selection_snapshot_append_only
before update or delete on content_factory.generation_job_selection_snapshots
for each row execute function content_factory_private
  .guard_generation_selection_snapshot_append_only();

revoke all on function content_factory_private
  .guard_generation_selection_snapshot_append_only()
  from public, anon, authenticated, service_role;

-- Batch/job facts remain one projection of the exact provider request.  New
-- Google rows honestly carry NULL credits; no synthetic credit balance is
-- introduced for a USD-billed provider.
alter table content_factory.generation_batches
  drop constraint if exists generation_batches_provider_check,
  drop constraint if exists generation_batches_model_check,
  drop constraint if exists generation_batches_model_v2_check,
  drop constraint if exists generation_batches_sku_contract_check,
  drop constraint if exists generation_batches_sku_contract_v2_check,
  alter column estimated_credits drop not null;

alter table content_factory.generation_batches
  add constraint generation_batches_provider_v48_check
    check (provider in ('mock','runway','google')),
  add constraint generation_batches_model_v48_check
    check (
      (provider='mock' and model='mock')
      or content_factory_private.generation_catalog_entry(provider,model)
           is not null
    ),
  add constraint generation_batches_sku_contract_v48_check
    check (
      (
        mode='mock' and provider='mock' and model='mock'
        and duration_seconds=0 and not audio
        and estimated_cost_minor=0 and estimated_credits=0
      )
      or (
        mode='real' and allow_real_spend
        and content_factory_private.real_generation_sku_from_input(
          provider,input
        ) is not null
        and model=content_factory_private.real_generation_sku_from_input(
          provider,input
        ) ->> 'model'
        and duration_seconds::text=content_factory_private
          .real_generation_sku_from_input(provider,input)
          ->> 'duration_seconds'
        and audio=(content_factory_private.real_generation_sku_from_input(
          provider,input
        ) ->> 'audio')::boolean
        and estimated_cost_minor::text=content_factory_private
          .real_generation_sku_from_input(provider,input)
          ->> 'estimated_cost_minor'
        and to_jsonb(estimated_credits)=content_factory_private
          .real_generation_sku_from_input(provider,input)
          -> 'estimated_credits'
      )
    );

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_provider_check,
  drop constraint if exists generation_jobs_spend_contract_check,
  drop constraint if exists generation_jobs_spend_contract_v2_check;

alter table content_factory.generation_jobs
  add constraint generation_jobs_provider_v48_check
    check (provider in ('mock','runway','google')),
  add constraint generation_jobs_spend_contract_v48_check
    check (
      (
        mode='mock' and provider='mock' and not allow_real_spend
        and estimated_cost_minor=0 and actual_cost_minor=0
        and status in ('mock_ready','cancelled')
      )
      or (
        mode='real' and provider in ('runway','google')
        and allow_real_spend
        and status in (
          'queued','starting','submitted','processing',
          'succeeded','failed','cancelled'
        )
        and content_factory_private.real_generation_sku_from_input(
          provider,input
        ) is not null
        and estimated_cost_minor::text=content_factory_private
          .real_generation_sku_from_input(provider,input)
          ->> 'estimated_cost_minor'
      )
    );

create or replace function content_factory_private.normalize_generation_batch_facts()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op='INSERT' and new.mode='mock' then
    new.provider:=coalesce(new.provider,'mock');
    new.model:=coalesce(new.model,'mock');
    new.duration_seconds:=coalesce(new.duration_seconds,0);
    new.audio:=coalesce(new.audio,false);
    new.estimated_cost_minor:=coalesce(new.estimated_cost_minor,0);
    new.estimated_credits:=coalesce(new.estimated_credits,0);
    new.currency:=coalesce(new.currency,'USD');
  elsif tg_op='INSERT' and new.mode='real' then
    new.provider:=coalesce(new.provider,new.input ->> 'provider');
    new.model:=coalesce(new.model,new.input ->> 'model');
    new.duration_seconds:=coalesce(
      new.duration_seconds,(new.input ->> 'duration_seconds')::integer
    );
    new.audio:=coalesce(new.audio,(new.input ->> 'audio')::boolean,false);
    new.estimated_cost_minor:=coalesce(
      new.estimated_cost_minor,
      (new.input #>> '{billing,estimated_cost_minor}')::bigint
    );
    new.estimated_credits:=coalesce(
      new.estimated_credits,
      (new.input #>> '{billing,estimated_credits}')::bigint
    );
    new.currency:=coalesce(new.currency,new.input #>> '{billing,currency}');
  end if;
  return new;
end;
$$;

revoke all on function content_factory_private.normalize_generation_batch_facts()
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.guard_generation_batch_contract()
returns trigger
language plpgsql
set search_path = ''
as $$
declare sku_config jsonb;
begin
  if new.mode='mock' then
    if new.allow_real_spend or new.status not in ('mock_ready','cancelled')
       or new.provider<>'mock' or new.model<>'mock'
       or new.duration_seconds<>0 or new.audio
       or new.estimated_cost_minor<>0 or new.estimated_credits<>0
       or new.currency<>'USD' then
      raise exception using errcode='42501',
        message='mock_generation_contract_invalid';
    end if;
    return new;
  end if;
  sku_config:=content_factory_private.real_generation_sku_from_input(
    new.provider,new.input
  );
  if new.mode<>'real' or not new.allow_real_spend
     or new.status not in (
       'queued','starting','submitted','processing','succeeded','failed','cancelled'
     )
     or new.total_requested<>1
     or new.total_created<>(case when new.status='succeeded' then 1 else 0 end)
     or sku_config is null
     or new.provider is distinct from sku_config ->> 'provider'
     or new.provider is distinct from new.input ->> 'provider'
     or new.model is distinct from sku_config ->> 'model'
     or new.duration_seconds::text is distinct from
          sku_config ->> 'duration_seconds'
     or new.audio is distinct from (sku_config ->> 'audio')::boolean
     or new.estimated_cost_minor::text is distinct from
          sku_config ->> 'estimated_cost_minor'
     or to_jsonb(new.estimated_credits) is distinct from
          sku_config -> 'estimated_credits'
     or new.currency is distinct from 'USD'
     or new.input ->> 'ratio' is distinct from sku_config ->> 'provider_ratio'
     or new.input #>> '{billing,currency}' is distinct from 'USD'
     or new.input #>> '{billing,estimated_cost_minor}' is distinct from
          sku_config ->> 'estimated_cost_minor'
     or new.input #> '{billing,estimated_credits}' is distinct from
          sku_config -> 'estimated_credits'
     or coalesce(new.input ->> 'job_id','') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  then
    raise exception using errcode='42501',
      message='real_generation_batch_contract_invalid';
  end if;
  return new;
end;
$$;

create or replace function content_factory_private.guard_generation_job_contract()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  provider_task_id_value text:=nullif(btrim(new.output ->> 'provider_task_id'),'');
  sku_config jsonb;
begin
  if new.mode='mock' then
    if new.provider<>'mock' or new.allow_real_spend
       or new.estimated_cost_minor<>0 or new.actual_cost_minor<>0
       or new.status not in ('mock_ready','cancelled') then
      raise exception using errcode='42501',
        message='mock_generation_contract_invalid';
    end if;
    return new;
  end if;
  sku_config:=content_factory_private.real_generation_sku_from_input(
    new.provider,new.input
  );
  if new.mode<>'real' or new.provider not in ('runway','google')
     or not new.allow_real_spend or sku_config is null
     or new.estimated_cost_minor::text is distinct from
          sku_config ->> 'estimated_cost_minor'
     or new.actual_cost_minor<0
     or new.status not in (
       'queued','starting','submitted','processing','succeeded','failed','cancelled'
     )
     or new.input ->> 'provider' is distinct from new.provider
     or new.input ->> 'ratio' is distinct from sku_config ->> 'provider_ratio'
     or new.input #>> '{billing,currency}' is distinct from 'USD'
     or new.input #>> '{billing,estimated_cost_minor}' is distinct from
          sku_config ->> 'estimated_cost_minor'
     or new.input #> '{billing,estimated_credits}' is distinct from
          sku_config -> 'estimated_credits'
     or length(coalesce(new.input ->> 'input_object_name',''))<10
     or length(coalesce(new.input ->> 'output_object_name',''))<10
  then
    raise exception using errcode='42501',
      message='real_generation_job_contract_invalid';
  end if;
  if new.status in ('queued','starting')
     and (provider_task_id_value is not null or new.actual_cost_minor<>0) then
    raise exception using errcode='42501',
      message='real_generation_unsubmitted_contract_invalid';
  end if;
  if new.status in ('submitted','processing','succeeded')
     and (provider_task_id_value is null
       or new.actual_cost_minor<>new.estimated_cost_minor) then
    raise exception using errcode='42501',
      message='real_generation_submitted_contract_invalid';
  end if;
  if new.status='failed'
     and new.actual_cost_minor not in (0,new.estimated_cost_minor) then
    raise exception using errcode='42501',
      message='real_generation_failure_cost_invalid';
  end if;
  if new.status='succeeded' and (
       new.output ->> 'output_object_name' is distinct from
         new.input ->> 'output_object_name'
       or coalesce(new.output ->> 'output_media_id','') !~
         '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
       or new.output ->> 'failure_code' is not null
     ) then
    raise exception using errcode='42501',
      message='real_generation_success_contract_invalid';
  end if;
  if new.status='failed' and (
       nullif(btrim(new.output ->> 'failure_code'),'') is null
       or new.output ->> 'output_media_id' is not null
     ) then
    raise exception using errcode='42501',
      message='real_generation_failure_contract_invalid';
  end if;
  return new;
end;
$$;

revoke all on function content_factory_private.guard_generation_batch_contract()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_generation_job_contract()
  from public, anon, authenticated, service_role;

-- Every installed monetary trigger remains the owner of its mature budget,
-- campaign, reservation, settlement and ambiguous-outcome rules. Extend only
-- the provider predicate so direct Google cannot bypass (or be rejected by)
-- those same authoritative ledgers.
do $patch_multimodel_spend_owners$
declare
  procedure_signature text;
  function_definition text;
  patched_definition text;
begin
  foreach procedure_signature in array array[
    'content_factory_private.reserve_real_generation_spend()',
    'content_factory_private.guard_real_generation_spend_start()',
    'content_factory_private.record_real_generation_spend_lifecycle()',
    'content_factory_private.reserve_generation_campaign_spend()',
    'content_factory_private.guard_generation_campaign_spend_start()'
  ] loop
    select pg_catalog.pg_get_functiondef(procedure_signature::regprocedure)
      into function_definition;
    patched_definition:=replace(
      function_definition,
      'new.provider <> ''runway''',
      'new.provider not in (''runway'',''google'')'
    );
    patched_definition:=replace(
      patched_definition,
      'old.provider = ''runway''',
      'old.provider in (''runway'',''google'')'
    );
    if patched_definition=function_definition then
      raise exception using errcode='55000',
        message='generation_multimodel_spend_patch_target_invalid';
    end if;
    execute patched_definition;
  end loop;
end;
$patch_multimodel_spend_owners$;

-- Keep the installed provider state machine as the sole starting/submitted/
-- processing/terminal owner.  Its historical five-argument SKU helper cannot
-- represent resolution or last-frame and therefore cannot validate new4.
-- Replace only that read with the exact persisted job input; all transition,
-- storage, spend, task and event logic remains in the mature state machine.
do $patch_multimodel_worker_sku$
declare
  function_definition text;
  patched_definition text;
  old_fragment constant text:=$old$
  sku_config := content_factory_private.real_generation_sku_config(
    job_row.input ->> 'model',
    job_row.input -> 'duration_seconds',
    job_row.input -> 'audio',
    job_row.input ->> 'format',
    job_row.input ->> 'spend_confirmation'
  );$old$;
  new_fragment constant text:=$new$
  sku_config := content_factory_private.real_generation_sku_from_input(
    job_row.provider,
    job_row.input
  );$new$;
begin
  function_definition:=pg_catalog.pg_get_functiondef(
    'content_factory_private.system_update_real_generation_v1(jsonb)'
      ::regprocedure
  );
  if position(new_fragment in function_definition)>0 then
    return;
  end if;
  if position(old_fragment in function_definition)=0 then
    raise exception using errcode='55000',
      message='generation_multimodel_worker_sku_patch_target_invalid';
  end if;
  patched_definition:=replace(
    function_definition,old_fragment,new_fragment
  );
  execute patched_definition;
end;
$patch_multimodel_worker_sku$;

-- Baseline launches still participate in the mature append-only QA lineage.
-- Only the model-domain constraint is widened; performance-learning policy
-- snapshots remain closed because this first executable slice permits the
-- exact baseline learning context only.
alter table content_factory.generation_quality_guard_lineage
  drop constraint if exists generation_quality_guard_lineage_model_check;
alter table content_factory.generation_quality_guard_lineage
  add constraint generation_quality_guard_lineage_model_v48_check check (
    model in (
      'gen4_turbo','seedance2_fast','seedream5_lite','gen4.5',
      'seedance2_mini','veo3.1_fast','gemini_omni_flash'
    )
  );

-- Newly created model signals use the same bounded, structural learning
-- ledger. No raw prompt or autonomous decision is added here.
do $$
declare constraint_name text;
begin
  for constraint_name in
    select constraint_row.conname
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid=
      'content_factory.generation_creative_signals'::regclass
      and constraint_row.contype='c'
      and position('model' in lower(pg_catalog.pg_get_constraintdef(
        constraint_row.oid
      )))>0
      and position('gen4_turbo' in lower(pg_catalog.pg_get_constraintdef(
        constraint_row.oid
      )))>0
  loop
    execute format(
      'alter table content_factory.generation_creative_signals drop constraint %I',
      constraint_name
    );
  end loop;
end;
$$;

alter table content_factory.generation_creative_signals
  add constraint generation_creative_signals_model_v48_check check (
    content_factory_private.generation_catalog_entry('runway',model)
      is not null
    or content_factory_private.generation_catalog_entry('google',model)
      is not null
  );

-- Keep one prompt-requirements owner. The three historical arrays are byte
-- compatible; new4 adds only requirements already emitted by the canonical
-- compiler. Dynamic duration/public-aspect and speech checks live in the exact
-- validator immediately below.
create or replace function
  content_factory_private.generation_mode_prompt_requirements(
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
declare
  model_value text:=lower(btrim(coalesce(p_model,'')));
  common_requirements text[]:=array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.'
  ]::text[];
begin
  if model_value not in (
    'seedream5_lite','gen4_turbo','seedance2_fast','gen4.5',
    'seedance2_mini','veo3.1_fast','gemini_omni_flash',
    'veo-3.1-lite-generate-preview'
  ) then
    return null;
  end if;
  return common_requirements || case model_value
    when 'seedream5_lite' then array[
      'Создай одно квадратное товарное фото 2048 × 2048.',
      'Используй @ProductReference как главный точный референс товара; остальные выбранные ракурсы уточняют форму и детали.',
      'Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса.'
    ]::text[]
    when 'gen4_turbo' then array[
      'Без речи, дикторского текста и сгенерированных надписей.'
    ]::text[]
    when 'seedance2_fast' then array[
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
    when 'gen4.5' then array[
      'Без речи, дикторского текста и сгенерированных надписей.'
    ]::text[]
    when 'seedance2_mini' then array[
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
    when 'veo3.1_fast' then array[]::text[]
    when 'gemini_omni_flash' then array[
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
    when 'veo-3.1-lite-generate-preview' then array[
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
  end;
end;
$$;

revoke all on function
  content_factory_private.generation_mode_prompt_requirements(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_multimodel_prompt_contract_valid(
    p_model text,
    p_duration integer,
    p_format text,
    p_audio boolean,
    p_product_name text,
    p_sku text,
    p_product_category text,
    p_prompt text
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  model_value text:=lower(btrim(coalesce(p_model,'')));
  prompt_value text:=btrim(coalesce(p_prompt,''));
  first_line_value text;
  expected_first_line text;
  requirement_value text;
  requirements_value text[];
  interaction_value text;
  spoken_count integer:=0;
  spoken_line text;
  spoken_words integer:=0;
  spoken_limit integer:=greatest(10,least(42,floor(p_duration*22.0/8.0)::integer));
begin
  if model_value not in (
       'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash',
       'veo-3.1-lite-generate-preview'
     )
     or p_duration is null or p_format is null or p_audio is null
     or length(prompt_value)<1 then
    return false;
  end if;
  first_line_value:=split_part(prompt_value,E'\n',1);
  expected_first_line:=case
    when model_value in ('gen4.5','veo3.1_fast') and not p_audio then format(
      'Создай один непрерывный ролик длительностью %s секунд с соотношением сторон %s.',
      p_duration,p_format
    )
    else format(
      'Создай один непрерывный UGC-ролик длительностью %s секунд с соотношением сторон %s.',
      p_duration,p_format
    )
  end;
  requirements_value:=content_factory_private
    .generation_mode_prompt_requirements(model_value);
  interaction_value:=content_factory_private
    .generation_product_interaction_requirement(
      p_product_name,p_product_category
    );
  if first_line_value is distinct from expected_first_line
     or position(format(
          'Точный товар: %s, артикул %s.',p_product_name,p_sku
        ) in prompt_value)=0
     or interaction_value is null
     or position(interaction_value in prompt_value)=0
     or position('AIResearchSelection/v1' in prompt_value)>0
     or position('AIResearchHumanIntent/v1' in prompt_value)>0
     or position('ResearchCategoryRule/v2' in prompt_value)>0
     or position('GenerationVideoReference/operator-summary:' in prompt_value)>0
  then
    return false;
  end if;
  foreach requirement_value in array requirements_value loop
    if position(requirement_value in prompt_value)=0 then
      return false;
    end if;
  end loop;
  if model_value='veo3.1_fast' then
    requirement_value:=case when p_audio then
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    else 'Без речи, дикторского текста и сгенерированных надписей.' end;
    if position(requirement_value in prompt_value)=0 then
      return false;
    end if;
  end if;
  select count(*)::integer,max(match_value[1])
    into spoken_count,spoken_line
  from regexp_matches(
    prompt_value,'Реплика героя дословно: «([^»]+)»','g'
  ) match_value;
  if p_audio then
    if spoken_count<>1 or btrim(coalesce(spoken_line,''))='' then
      return false;
    end if;
    spoken_words:=cardinality(regexp_split_to_array(
      btrim(spoken_line),E'\\s+'
    ));
    if spoken_words<1 or spoken_words>spoken_limit then
      return false;
    end if;
    if spoken_line~'[А-Яа-яЁё]' and position(
      'Русская дикция: чётко, без акцента/лишних гласных; все слова/окончания; числа/градусы/названия точно; чёткие паузы.'
      in prompt_value
    )=0 then
      return false;
    end if;
  elsif spoken_count<>0
     or position('Реплика героя дословно:' in prompt_value)>0 then
    return false;
  end if;
  return true;
end;
$$;

revoke all on function
  content_factory_private.generation_multimodel_prompt_contract_valid(
    text,integer,text,boolean,text,text,text,text
  ) from public, anon, authenticated, service_role;

-- Baseline-only claim for this first multi-model executable slice. It reuses
-- current-spec and project owners, then deliberately rejects every research,
-- performance, repair, outcome, AI-selection and video-reference marker until
-- those mature live proofs are generalized for the new model identities.
create or replace function
  content_factory_private.generation_multimodel_baseline_claim_v2(
    p_organization_id uuid,
    p_project_id uuid,
    p_actor_id uuid,
    p_spec_id uuid,
    p_spec_version integer,
    p_spec_hash text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_role_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  product_row content_factory.products%rowtype;
  resolved_category_value text;
  category_binding_required_value boolean:=false;
  media_snapshot_value jsonb;
  verified_media_count integer;
  claim_without_hash jsonb;
  claim_hash_value text;
begin
  if p_organization_id is null or p_project_id is null or p_actor_id is null
     or p_spec_id is null or p_spec_version is null
     or coalesce(p_spec_hash,'')!~'^[0-9a-f]{64}$' then
    raise exception using errcode='22023',
      message='generation_multimodel_claim_invalid';
  end if;
  select membership.role into actor_role_value
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id=membership.organization_id
   and organization.status='active'
  join content_factory.profiles profile
    on profile.id=membership.profile_id and profile.status='active'
  where membership.organization_id=p_organization_id
    and membership.profile_id=p_actor_id
    and membership.status='active'
    and membership.role in ('owner','admin','producer','operator')
  for share of membership;
  if actor_role_value is null
     or not content_factory_private.workspace_project_access_allowed(
       p_organization_id,p_project_id,p_actor_id
     )
     or not content_factory_private.generated_media_reviewer_access_allowed(
       p_organization_id,p_actor_id
     ) then
    raise exception using errcode='42501',message='role_not_allowed';
  end if;
  perform set_config('contentengine.project_id',p_project_id::text,true);
  spec_row:=content_factory_private.assert_generation_spec_current(
    p_organization_id,p_spec_id,p_spec_version,p_spec_hash,false,true
  );
  if content_factory_private.require_generation_spec_project_v49(
       p_organization_id,p_project_id,p_spec_id,p_spec_version,p_spec_hash,
       spec_row.product_id
     ) is distinct from spec_row.product_id
     or spec_row.spec_contract_version<>'generation-spec-scope-v2'
     or spec_row.provider<>'runway'
     or spec_row.model not in (
       'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
     )
     or spec_row.exact_scope is distinct from
          content_factory_private.generation_spec_scope_v2(spec_row.exact_scope)
     or spec_row.exact_scope ->> 'provider'<>'runway'
     or spec_row.research_provenance is not null
     or spec_row.research_snapshot_hash is not null
     or spec_row.performance_policy_provenance is not null
     or spec_row.repair_provenance is not null
     or spec_row.canonical_repair_context is not null
     or spec_row.outcome_selection_id is not null
     or spec_row.outcome_selection_hash is not null
     or spec_row.canonical_learning_context is distinct from jsonb_build_object(
       'creative_angle','product_focus','hook_patterns','[]'::jsonb,
       'source','baseline','compiler_version','safe-brief-v7',
       'product_category',spec_row.product_category
     )
     or spec_row.final_policy -> 'generation_allowed' is distinct from
          'true'::jsonb
     or spec_row.final_policy ->> 'final_policy_hash' is distinct from
          spec_row.final_policy_hash
     or spec_row.final_policy_hash is distinct from
          content_factory_private.json_hash(
            spec_row.final_policy-'final_policy_hash'
          )
     or not content_factory_private.generation_multimodel_prompt_contract_valid(
       spec_row.model,spec_row.duration_seconds,spec_row.format,spec_row.audio,
       (select product.title from content_factory.products product
        where product.organization_id=p_organization_id
          and product.id=spec_row.product_id),
       (select product.sku from content_factory.products product
        where product.organization_id=p_organization_id
          and product.id=spec_row.product_id),
       spec_row.product_category,spec_row.compiled_prompt
     )
     or exists (
       select 1 from content_factory.generation_spec_ai_research_bindings binding
       where binding.organization_id=p_organization_id
         and binding.spec_id=p_spec_id and binding.spec_version=p_spec_version
     )
     or exists (
       select 1
       from content_factory.generation_spec_ai_research_speech_bindings speech
       join content_factory.generation_spec_ai_research_bindings binding
         on binding.organization_id=speech.organization_id
        and binding.id=speech.binding_id
       where binding.organization_id=p_organization_id
         and binding.spec_id=p_spec_id and binding.spec_version=p_spec_version
     )
     or exists (
       select 1 from content_factory.generation_spec_video_reference_bindings binding
       where binding.organization_id=p_organization_id
         and binding.spec_id=p_spec_id and binding.spec_version=p_spec_version
     )
     or exists (
       select 1
       from content_factory.generation_spec_research_category_rule_bindings binding
       where binding.organization_id=p_organization_id
         and binding.spec_id=p_spec_id and binding.spec_version=p_spec_version
     ) then
    raise exception using errcode='55000',
      message='generation_multimodel_baseline_required';
  end if;
  select product.* into product_row
  from content_factory.products product
  where product.organization_id=p_organization_id
    and product.id=spec_row.product_id and product.status='active'
  for share;
  if product_row.id is null then
    raise exception using errcode='55000',
      message='generation_spec_product_binding_invalid';
  end if;
  resolved_category_value:=content_factory_private
    .resolved_content_review_category(product_row.metadata);
  if coalesce(resolved_category_value,'')='' then
    if actor_role_value='operator' then
      raise exception using errcode='42501',
        message='content_review_product_category_unverified';
    end if;
    category_binding_required_value:=true;
  elsif resolved_category_value is distinct from spec_row.product_category then
    raise exception using errcode='22023',
      message='content_review_product_category_mismatch';
  end if;
  select count(*)::integer,
         jsonb_agg(jsonb_build_object(
           'media_id',media.id,'sha256',media.sha256,
           'object_name',media.object_name,'mime_type',media.mime_type,
           'kind',media.metadata ->> 'kind','rights_confirmed',true
         ) order by selected.ordinality)
    into verified_media_count,media_snapshot_value
  from unnest(spec_row.media_ids) with ordinality selected(media_id,ordinality)
  join content_factory.media_objects media
    on media.organization_id=p_organization_id
   and media.project_id=p_project_id
   and media.id=selected.media_id
   and media.product_id=spec_row.product_id
   and media.status='ready'
   and media.mime_type in ('image/jpeg','image/png','image/webp')
   and coalesce(media.metadata ->> 'kind','') in ('product_photo','packshot')
   and media.metadata -> 'rights_confirmed'='true'::jsonb;
  if verified_media_count<>cardinality(spec_row.media_ids)
     or media_snapshot_value is null then
    raise exception using errcode='55000',message='generation_spec_media_stale';
  end if;
  claim_without_hash:=jsonb_build_object(
    'version','generation-multimodel-baseline-claim-v2',
    'organization_id',p_organization_id,'project_id',p_project_id,
    'actor_id',p_actor_id,'actor_role',actor_role_value,
    'spec_id',spec_row.spec_id,'spec_version',spec_row.spec_version,
    'spec_hash',spec_row.spec_hash,
    'scope_hash',content_factory_private.json_hash(spec_row.exact_scope),
    'product_id',spec_row.product_id,
    'product_identity_hash',content_factory_private.json_hash(
      jsonb_build_object('sku',product_row.sku,'title',product_row.title)
    ),
    'product_category',spec_row.product_category,
    'category_binding_required',category_binding_required_value,
    'prompt_hash',spec_row.prompt_hash,
    'final_policy_hash',spec_row.final_policy_hash,
    'learning_context_hash',content_factory_private.json_hash(
      spec_row.canonical_learning_context
    ),
    'media_snapshot_hash',content_factory_private.json_hash(media_snapshot_value)
  );
  claim_hash_value:=content_factory_private.json_hash(claim_without_hash);
  return claim_without_hash || jsonb_build_object('snapshot_hash',claim_hash_value);
end;
$$;

revoke all on function
  content_factory_private.generation_multimodel_baseline_claim_v2(
    uuid,uuid,uuid,uuid,integer,text
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_multimodel_live_claim_v2(
    p_organization_id uuid,
    p_project_id uuid,
    p_actor_id uuid,
    p_generation_job_id uuid,
    p_spec_id uuid,
    p_spec_version integer,
    p_spec_hash text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  baseline_claim jsonb;
  spec_row content_factory.generation_spec_versions%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  signal_row content_factory.generation_creative_signals%rowtype;
  quality_lineage_row
    content_factory.generation_quality_guard_lineage%rowtype;
  consent_row content_factory.generation_review_autostart_consents%rowtype;
  sku_value jsonb;
  claim_without_hash jsonb;
  claim_hash_value text;
  consent_expected boolean;
  caught_state text;
  caught_message text;
begin
  begin
    baseline_claim:=content_factory_private
      .generation_multimodel_baseline_claim_v2(
        p_organization_id,p_project_id,p_actor_id,p_spec_id,p_spec_version,
        p_spec_hash
      );
  exception when others then
    get stacked diagnostics
      caught_state=returned_sqlstate,caught_message=message_text;
    if (caught_state='42501' and caught_message in (
         'role_not_allowed','generation_spec_project_scope_mismatch',
         'content_review_product_category_unverified'
       ))
       or (caught_state='55000' and caught_message in (
         'generation_multimodel_baseline_required','generation_spec_stale',
         'generation_spec_media_stale','generation_spec_product_binding_invalid',
         'generation_spec_provider_start_stale'
       ))
       or (caught_state='22023' and caught_message in (
         'content_review_product_category_mismatch',
         'generation_spec_project_binding_invalid'
       )) then
      raise exception using errcode='55000',
        message='generation_spec_provider_start_stale';
    end if;
    raise;
  end;
  spec_row:=content_factory_private.assert_generation_spec_current(
    p_organization_id,p_spec_id,p_spec_version,p_spec_hash,false,true
  );
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id=p_organization_id
    and job.id=p_generation_job_id
  for share;
  select batch.* into batch_row
  from content_factory.generation_batches batch
  where batch.organization_id=p_organization_id
    and batch.id=job_row.batch_id
  for share;
  select signal.* into signal_row
  from content_factory.generation_creative_signals signal
  where signal.organization_id=p_organization_id
    and signal.generation_job_id=p_generation_job_id;
  select lineage.* into quality_lineage_row
  from content_factory.generation_quality_guard_lineage lineage
  where lineage.organization_id=p_organization_id
    and lineage.generation_job_id=p_generation_job_id;
  select consent.* into consent_row
  from content_factory.generation_review_autostart_consents consent
  where consent.organization_id=p_organization_id
    and consent.generation_job_id=p_generation_job_id;
  sku_value:=content_factory_private.real_generation_multimodel_sku(
    spec_row.provider,spec_row.model,spec_row.input_mode,
    spec_row.duration_seconds,spec_row.format,spec_row.resolution,
    spec_row.audio,spec_row.last_frame
  );
  consent_expected:=coalesce(
    (job_row.input ->> 'review_autostart_confirmed')::boolean,false
  );
  if job_row.id is null or batch_row.id is null or signal_row.id is null
     or quality_lineage_row.id is null
     or job_row.project_id is distinct from p_project_id
     or batch_row.project_id is distinct from p_project_id
     or job_row.product_id is distinct from spec_row.product_id
     or batch_row.product_id is distinct from spec_row.product_id
     or job_row.batch_id is distinct from batch_row.id
     or job_row.requested_by is distinct from p_actor_id
     or batch_row.created_by is distinct from p_actor_id
     or job_row.mode<>'real' or batch_row.mode<>'real'
     or not job_row.allow_real_spend or not batch_row.allow_real_spend
     or job_row.status<>'queued' or batch_row.status<>'queued'
     or job_row.provider is distinct from spec_row.provider
     or batch_row.provider is distinct from spec_row.provider
     or job_row.input ->> 'model' is distinct from spec_row.model
     or batch_row.model is distinct from spec_row.model
     or job_row.generation_spec_id is distinct from spec_row.spec_id
     or job_row.generation_spec_version is distinct from spec_row.spec_version
     or job_row.generation_spec_hash is distinct from spec_row.spec_hash
     or job_row.input -> 'reference_media_ids' is distinct from
          spec_row.exact_scope -> 'media_ids'
     or job_row.input ->> 'format' is distinct from spec_row.format
     or job_row.input ->> 'resolution' is distinct from spec_row.resolution
     or job_row.input -> 'audio' is distinct from to_jsonb(spec_row.audio)
     or job_row.input -> 'last_frame' is distinct from to_jsonb(spec_row.last_frame)
     or job_row.input ->> 'input_mode' is distinct from spec_row.input_mode
     or job_row.estimated_cost_minor::text is distinct from
          sku_value ->> 'estimated_cost_minor'
     or batch_row.estimated_cost_minor is distinct from job_row.estimated_cost_minor
     or signal_row.product_id is distinct from spec_row.product_id
     or signal_row.platform is distinct from spec_row.platform
     or signal_row.model is distinct from spec_row.model
     or signal_row.source<>'baseline'
     or signal_row.compiler_version<>'safe-brief-v7'
     or signal_row.creative_angle<>'product_focus'
     or signal_row.hook_patterns<>'[]'::jsonb
     or signal_row.applied_policy_hash is not null
     or signal_row.creative_brief_draft_id is not null
     or signal_row.scenario_position is not null
     or signal_row.prompt_hash is distinct from
          content_factory_private.json_hash(to_jsonb(spec_row.compiled_prompt))
     or signal_row.product_category is distinct from spec_row.product_category
     or quality_lineage_row.product_id is distinct from spec_row.product_id
     or quality_lineage_row.platform is distinct from spec_row.platform
     or quality_lineage_row.model is distinct from spec_row.model
     or quality_lineage_row.source<>'baseline'
     or quality_lineage_row.applied_policy_hash is not null
     or quality_lineage_row.guard_codes<>'[]'::jsonb
     or quality_lineage_row.prompt_hash is distinct from signal_row.prompt_hash
     or quality_lineage_row.created_by is distinct from p_actor_id
     or consent_expected is distinct from (consent_row.id is not null)
     or (consent_row.id is not null and (
       consent_row.confirmed_by is distinct from p_actor_id
       or consent_row.terms_version<>'generated-video-qa-autostart-v1'
     ))
     or exists (
       select 1 from content_factory.generation_job_video_reference_bindings binding
       where binding.organization_id=p_organization_id
         and binding.generation_job_id=p_generation_job_id
     ) then
    raise exception using errcode='55000',
      message='generation_spec_provider_start_stale';
  end if;
  claim_without_hash:=jsonb_build_object(
    'version','generation-multimodel-live-claim-v2',
    'organization_id',p_organization_id,'project_id',p_project_id,
    'actor_id',p_actor_id,'generation_job_id',p_generation_job_id,
    'generation_batch_id',batch_row.id,
    'spec_id',spec_row.spec_id,'spec_version',spec_row.spec_version,
    'spec_hash',spec_row.spec_hash,
    'baseline_claim_hash',baseline_claim ->> 'snapshot_hash',
    'scope_hash',baseline_claim ->> 'scope_hash',
    'prompt_hash',spec_row.prompt_hash,
    'final_policy_hash',spec_row.final_policy_hash,
    'job_request_hash',job_row.request_hash,
    'batch_request_hash',batch_row.request_hash,
    'creative_signal_hash',content_factory_private.json_hash(to_jsonb(signal_row)),
    'quality_lineage_hash',content_factory_private.json_hash(
      to_jsonb(quality_lineage_row)
    ),
    'review_autostart_confirmed',consent_expected,
    'review_autostart_terms_version',case when consent_expected then
      consent_row.terms_version else null end
  );
  claim_hash_value:=content_factory_private.json_hash(claim_without_hash);
  return claim_without_hash || jsonb_build_object('snapshot_hash',claim_hash_value);
end;
$$;

revoke all on function
  content_factory_private.generation_multimodel_live_claim_v2(
    uuid,uuid,uuid,uuid,uuid,integer,text
  ) from public, anon, authenticated, service_role;

-- Existing spec binding/claim code is preserved for historical starts. New4
-- uses the exact v4 receipt plus the immutable selection snapshot and a live
-- baseline claim; audit metadata alone never substitutes for those proofs.
do $patch_multimodel_spec_bind$
declare function_definition text; patched_definition text;
begin
  select pg_catalog.pg_get_functiondef(
    'content_factory_private.bind_generation_spec_to_paid_job()'::regprocedure
  ) into function_definition;
  patched_definition:=replace(
    function_definition,
    'new.provider <> ''runway''',
    'new.provider not in (''runway'',''google'')'
  );
  if patched_definition=function_definition then
    raise exception using errcode='55000',
      message='generation_multimodel_spec_bind_patch_target_invalid';
  end if;
  execute patched_definition;
end;
$patch_multimodel_spec_bind$;

do $patch_multimodel_spec_claim$
declare
  function_definition text;
  patched_definition text;
  marker text;
  replacement text;
begin
  select pg_catalog.pg_get_functiondef(
    'content_factory_private.guard_generation_spec_provider_start()'::regprocedure
  ) into function_definition;
  patched_definition:=replace(
    function_definition,
    'new.provider <> ''runway''',
    'new.provider not in (''runway'',''google'')'
  );
  marker:=$marker$  begin
    perform pg_advisory_xact_lock($marker$;
  replacement:=$replacement$  if exists (
    select 1
    from content_factory.generation_job_selection_snapshots launch
    join content_factory.generation_provider_readiness_receipts receipt
      on receipt.id=launch.readiness_receipt_id
     and receipt.organization_id=launch.organization_id
    join content_factory.generation_job_spec_bindings binding
      on binding.organization_id=launch.organization_id
     and binding.generation_job_id=launch.generation_job_id
    cross join lateral content_factory_private
      .generation_multimodel_live_claim_v2(
        launch.organization_id,launch.project_id,launch.bound_by,
        launch.generation_job_id,launch.spec_id,launch.spec_version,
        launch.spec_hash
      ) current_claim(value)
    where launch.organization_id=new.organization_id
      and launch.generation_job_id=new.id
      and launch.batch_id=new.batch_id
      and launch.project_id=new.project_id
      and launch.bound_by=new.requested_by
      and launch.provider=new.provider
      and launch.model=new.input ->> 'model'
      and receipt.receipt_hash=launch.readiness_receipt_hash
      and receipt.receipt_version='generation-provider-readiness-receipt-v4'
      and receipt.project_id=launch.project_id
      and receipt.spec_id=launch.spec_id
      and receipt.spec_version=launch.spec_version
      and receipt.spec_hash=launch.spec_hash
      and receipt.scope_hash=launch.scope_hash
      and receipt.provider=launch.provider
      and receipt.model=launch.model
      and launch.selection_snapshot ->> 'requested_duration_seconds'
            =new.input ->> 'duration_seconds'
      and launch.selection_snapshot ->> 'requested_ratio'
            =new.input ->> 'format'
      and launch.selection_snapshot ->> 'requested_resolution'
            =new.input ->> 'resolution'
      and launch.selection_snapshot -> 'requested_audio'
            =new.input -> 'audio'
      and launch.selection_snapshot ->> 'input_mode'
            =new.input ->> 'input_mode'
      and launch.estimated_cost_minor=new.estimated_cost_minor
      and launch.spec_id=new.generation_spec_id
      and launch.spec_version=new.generation_spec_version
      and launch.spec_hash=new.generation_spec_hash
      and launch.live_claim_snapshot=current_claim.value
      and launch.live_claim_snapshot_hash=current_claim.value ->> 'snapshot_hash'
      and binding.claim_snapshot=current_claim.value
      and binding.claim_snapshot_hash=current_claim.value ->> 'snapshot_hash'
      and content_factory_private.generation_provider_launch_enabled(
        new.organization_id,new.provider,new.input ->> 'model'
      )
  ) then
    return new;
  end if;
  begin
    perform pg_advisory_xact_lock($replacement$;
  if position(marker in patched_definition)=0 then
    raise exception using errcode='55000',
      message='generation_multimodel_spec_claim_patch_target_invalid';
  end if;
  patched_definition:=replace(patched_definition,marker,replacement);
  execute patched_definition;
end;
$patch_multimodel_spec_claim$;

-- Preserve the exact mature acceptance status for the three historical
-- models and mark every new model honestly unproven. The richer public
-- all-catalog acceptance projection is a separate, non-launch authority; the
-- paid gate below never fabricates acceptance evidence for a new model.
create or replace function
  content_factory_private.generation_model_acceptance_status_v48(
    p_organization_id uuid,p_provider text,p_model text
  )
returns text
language plpgsql
stable
security definer
set search_path = ''
as $$
declare acceptance_value jsonb; status_value text;
begin
  if p_provider='runway'
     and p_model in ('seedream5_lite','gen4_turbo','seedance2_fast') then
    acceptance_value:=content_factory_private
      .generation_model_acceptance_freshness(
        content_factory_private.generation_model_acceptance(
          p_organization_id
        ),now()
      );
    select item.value ->> 'status' into status_value
    from jsonb_array_elements(acceptance_value -> 'models') item(value)
    where item.value ->> 'model'=p_model
    limit 1;
  end if;
  return coalesce(status_value,'unproven');
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance_status_v48(
    uuid,text,text
  ) from public, anon, authenticated, service_role;

-- Exact-once bind for the fresh v4 readiness receipt and the canonical §12
-- selection snapshot. On an exact idempotent replay the immutable row is the
-- authority, so expiration after the original successful transaction does
-- not rewrite or invalidate history.
create or replace function
  content_factory_private.bind_generation_v4_launch(
    p_organization_id uuid,
    p_project_id uuid,
    p_actor_id uuid,
    p_batch_id uuid,
    p_job_id uuid,
    p_payload jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  launch_row content_factory.generation_job_selection_snapshots%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  receipt_row
    content_factory.generation_provider_readiness_receipts%rowtype;
  context_value jsonb:=p_payload -> 'generation_spec_context';
  snapshot_value jsonb:=p_payload -> 'generation_selection_snapshot';
  receipt_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  receipt_hash_value text;
  receipt_body jsonb;
  sku_value jsonb;
  catalog_value jsonb;
  expected_acceptance text;
  snapshot_hash_value text;
  scope_hash_value text;
  baseline_claim_value jsonb;
  live_claim_value jsonb;
begin
  select launch.* into launch_row
  from content_factory.generation_job_selection_snapshots launch
  where launch.organization_id=p_organization_id
    and launch.generation_job_id=p_job_id
  for share;
  if launch_row.id is not null then
    baseline_claim_value:=content_factory_private
      .generation_multimodel_baseline_claim_v2(
        p_organization_id,p_project_id,p_actor_id,launch_row.spec_id,
        launch_row.spec_version,launch_row.spec_hash
      );
    live_claim_value:=content_factory_private
      .generation_multimodel_live_claim_v2(
        p_organization_id,p_project_id,p_actor_id,p_job_id,
        launch_row.spec_id,launch_row.spec_version,launch_row.spec_hash
      );
    if launch_row.project_id is distinct from p_project_id
       or launch_row.batch_id is distinct from p_batch_id
       or launch_row.bound_by is distinct from p_actor_id
       or launch_row.provider is distinct from
            lower(btrim(p_payload ->> 'provider'))
       or launch_row.model is distinct from
            lower(btrim(p_payload ->> 'model'))
       or launch_row.readiness_receipt_id::text is distinct from
            p_payload ->> 'provider_readiness_receipt_id'
       or launch_row.readiness_receipt_hash is distinct from
            lower(btrim(p_payload ->> 'provider_readiness_receipt_hash'))
       or launch_row.selection_snapshot is distinct from snapshot_value
       or launch_row.snapshot_hash is distinct from
            content_factory_private.json_hash(snapshot_value)
       or launch_row.spec_id::text is distinct from
            context_value ->> 'spec_id'
       or launch_row.spec_version::text is distinct from
            context_value ->> 'spec_version'
       or launch_row.spec_hash is distinct from
             lower(btrim(context_value ->> 'spec_hash'))
       or launch_row.scope_hash is distinct from
            baseline_claim_value ->> 'scope_hash'
       or launch_row.live_claim_snapshot is distinct from live_claim_value
       or launch_row.live_claim_snapshot_hash is distinct from
            live_claim_value ->> 'snapshot_hash'
       or live_claim_value ->> 'baseline_claim_hash' is distinct from
            baseline_claim_value ->> 'snapshot_hash' then
      raise exception using errcode='23505',
        message='idempotency_key_conflict';
    end if;
    return jsonb_build_object(
      'snapshot_hash',launch_row.snapshot_hash,
      'receipt_id',launch_row.readiness_receipt_id,
      'receipt_hash',launch_row.readiness_receipt_hash,
      'scope_hash',launch_row.scope_hash,
      'live_claim_snapshot',launch_row.live_claim_snapshot,
      'live_claim_snapshot_hash',launch_row.live_claim_snapshot_hash,
      'replayed',true
    );
  end if;

  if jsonb_typeof(context_value)<>'object'
     or context_value-array['spec_id','spec_version','spec_hash']::text[]
          <>'{}'::jsonb
     or not context_value ?& array[
       'spec_id','spec_version','spec_hash'
     ]::text[]
     or not content_factory_private.generation_selection_snapshot_valid(
       snapshot_value
     ) then
    raise exception using errcode='22023',
      message='generation_provider_selection_stale';
  end if;
  begin
    receipt_id_value:=(p_payload ->> 'provider_readiness_receipt_id')::uuid;
    spec_id_value:=(context_value ->> 'spec_id')::uuid;
    spec_version_value:=(context_value ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using errcode='22023',
      message='generation_provider_selection_stale';
  end;
  receipt_hash_value:=lower(btrim(coalesce(
    p_payload ->> 'provider_readiness_receipt_hash',''
  )));
  spec_hash_value:=lower(btrim(coalesce(context_value ->> 'spec_hash','')));
  if receipt_hash_value !~ '^[0-9a-f]{64}$'
     or spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode='22023',
      message='generation_provider_selection_stale';
  end if;

  spec_row:=content_factory_private.assert_generation_spec_current(
    p_organization_id,spec_id_value,spec_version_value,spec_hash_value,
    true,true
  );
  baseline_claim_value:=content_factory_private
    .generation_multimodel_baseline_claim_v2(
      p_organization_id,p_project_id,p_actor_id,spec_id_value,
      spec_version_value,spec_hash_value
    );
  scope_hash_value:=content_factory_private.json_hash(spec_row.exact_scope);
  if spec_row.spec_contract_version<>'generation-spec-scope-v2'
     or spec_row.exact_scope is distinct from
          content_factory_private.generation_spec_scope_v2(
            spec_row.exact_scope
          )
     or spec_row.exact_scope -> 'media_ids' is distinct from
          p_payload -> 'media_ids'
     or spec_row.exact_scope ->> 'provider' is distinct from
          lower(btrim(p_payload ->> 'provider'))
     or spec_row.exact_scope ->> 'model' is distinct from
          lower(btrim(p_payload ->> 'model'))
     or spec_row.exact_scope ->> 'input_mode' is distinct from
          lower(btrim(p_payload ->> 'input_mode'))
     or spec_row.exact_scope -> 'duration_seconds' is distinct from
          p_payload -> 'duration_seconds'
     or spec_row.exact_scope ->> 'product_category' is distinct from
          lower(btrim(p_payload ->> 'product_category'))
     or spec_row.exact_scope ->> 'format' is distinct from
          btrim(p_payload ->> 'format')
     or spec_row.exact_scope ->> 'ratio' is distinct from
          btrim(p_payload ->> 'format')
     or spec_row.exact_scope ->> 'resolution' is distinct from
          btrim(p_payload ->> 'resolution')
     or spec_row.exact_scope -> 'audio' is distinct from
          p_payload -> 'audio'
     or spec_row.exact_scope -> 'last_frame' is distinct from
          p_payload -> 'last_frame'
     or spec_row.compiled_prompt is distinct from
          btrim(p_payload ->> 'brief')
     or spec_row.canonical_learning_context is distinct from
          p_payload -> 'learning_context'
     or spec_row.canonical_repair_context is distinct from
          nullif(p_payload -> 'repair_context','null'::jsonb)
      or baseline_claim_value ->> 'scope_hash' is distinct from scope_hash_value
      then
    raise exception using errcode='55000',
      message='generation_spec_scope_binding_invalid';
  end if;

  sku_value:=content_factory_private.real_generation_multimodel_sku(
    spec_row.provider,spec_row.model,spec_row.input_mode,
    spec_row.duration_seconds,spec_row.format,spec_row.resolution,
    spec_row.audio,spec_row.last_frame
  );
  catalog_value:=content_factory_private.generation_catalog_entry(
    spec_row.provider,spec_row.model
  );
  select receipt.* into receipt_row
  from content_factory.generation_provider_readiness_receipts receipt
  where receipt.id=receipt_id_value
    and receipt.organization_id=p_organization_id
  for update;
  receipt_body:=jsonb_build_object(
    'version','generation-provider-readiness-receipt-v4',
    'receipt_id',receipt_row.id,
    'organization_id',receipt_row.organization_id,
    'project_id',receipt_row.project_id,
    'checked_by',receipt_row.checked_by,
    'spec_id',receipt_row.spec_id,
    'spec_version',receipt_row.spec_version,
    'spec_hash',receipt_row.spec_hash,
    'scope_hash',receipt_row.scope_hash,
    'provider',receipt_row.provider,
    'model',receipt_row.model,
    'input_mode',receipt_row.input_mode,
    'duration_seconds',receipt_row.duration_seconds,
    'format',receipt_row.format,
    'resolution',receipt_row.resolution,
    'audio',receipt_row.audio,
    'last_frame',receipt_row.last_frame,
    'ready',receipt_row.ready,
    'estimated_cost_minor',receipt_row.estimated_cost_minor,
    'estimated_credits',receipt_row.estimated_credits,
    'credential_configured',receipt_row.credential_configured,
    'balance_sufficient',receipt_row.balance_sufficient,
    'model_available',receipt_row.model_available,
    'daily_quota_available',receipt_row.daily_quota_available,
    'failure_code',receipt_row.failure_code,
    'catalog_version',receipt_row.catalog_version,
    'pricing_version',receipt_row.pricing_version,
    'learning_gate_version',receipt_row.learning_gate_version,
    'checked_at',receipt_row.checked_at,
    'expires_at',receipt_row.expires_at,
    'status',case when receipt_row.ready then 'ready' else 'blocked' end,
    'fresh',true,
    'spend_confirmation',receipt_row.spend_confirmation,
    'automatic_generation',false,
    'automatic_spend',false
  );
  if receipt_row.id is null
     or receipt_row.receipt_version<>
          'generation-provider-readiness-receipt-v4'
     or receipt_row.receipt_hash is distinct from receipt_hash_value
     or receipt_row.receipt_hash is distinct from
          content_factory_private.json_hash(receipt_body)
     or receipt_row.checked_by is distinct from p_actor_id
     or receipt_row.project_id is distinct from p_project_id
     or receipt_row.spec_id is distinct from spec_row.spec_id
     or receipt_row.spec_version is distinct from spec_row.spec_version
     or receipt_row.spec_hash is distinct from spec_row.spec_hash
     or receipt_row.scope_hash is distinct from scope_hash_value
     or not receipt_row.ready
     or receipt_row.checked_at>clock_timestamp()
     or receipt_row.expires_at<=clock_timestamp()
     or receipt_row.provider is distinct from spec_row.provider
     or receipt_row.model is distinct from spec_row.model
     or receipt_row.input_mode is distinct from spec_row.input_mode
     or receipt_row.duration_seconds is distinct from spec_row.duration_seconds
     or receipt_row.format is distinct from spec_row.format
     or receipt_row.resolution is distinct from spec_row.resolution
     or receipt_row.audio is distinct from spec_row.audio
     or receipt_row.last_frame is distinct from spec_row.last_frame
     or receipt_row.catalog_version is distinct from
          content_factory_private.generation_catalog_version()
     or receipt_row.pricing_version is distinct from
          catalog_value ->> 'pricing_version'
     or receipt_row.estimated_cost_minor::text is distinct from
          sku_value ->> 'estimated_cost_minor'
     or to_jsonb(receipt_row.estimated_credits) is distinct from
          sku_value -> 'estimated_credits'
     or receipt_row.spend_confirmation is distinct from
          sku_value ->> 'spend_confirmation'
     or p_payload ->> 'spend_confirmation' is distinct from
          receipt_row.spend_confirmation
     or not content_factory_private.generation_provider_launch_enabled(
          p_organization_id,spec_row.provider,spec_row.model
        ) then
    raise exception using errcode='55000',
      message='provider_readiness_receipt_required';
  end if;
  if exists (
    select 1
    from content_factory.generation_job_selection_snapshots consumed
    where consumed.readiness_receipt_id=receipt_row.id
      and consumed.generation_job_id<>p_job_id
  ) then
    raise exception using errcode='55000',
      message='provider_readiness_receipt_consumed';
  end if;

  expected_acceptance:=content_factory_private
    .generation_model_acceptance_status_v48(
      p_organization_id,spec_row.provider,spec_row.model
    );
  if snapshot_value ->> 'provider' is distinct from spec_row.provider
     or snapshot_value ->> 'model' is distinct from spec_row.model
     or snapshot_value ->> 'model_public_label' is distinct from
          catalog_value ->> 'public_label'
     or snapshot_value ->> 'recommendation_catalog_version' is distinct from
          receipt_row.catalog_version
     or snapshot_value ->> 'pricing_version' is distinct from
          receipt_row.pricing_version
     or snapshot_value ->> 'estimated_cost_minor' is distinct from
          receipt_row.estimated_cost_minor::text
     or snapshot_value ->> 'requested_duration_seconds' is distinct from
          spec_row.duration_seconds::text
     or snapshot_value ->> 'requested_ratio' is distinct from spec_row.ratio
     or snapshot_value ->> 'requested_resolution' is distinct from
          spec_row.resolution
     or snapshot_value -> 'requested_audio' is distinct from
          to_jsonb(spec_row.audio)
     or snapshot_value ->> 'input_mode' is distinct from spec_row.input_mode
     or snapshot_value ->> 'reference_count' is distinct from
          spec_row.reference_count::text
     or snapshot_value ->> 'acceptance_status_at_launch' is distinct from
          expected_acceptance
     or snapshot_value ->> 'provider_readiness_receipt_id' is distinct from
          receipt_row.id::text then
    raise exception using errcode='55000',
      message='generation_provider_selection_stale';
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id=p_organization_id and job.id=p_job_id
    and job.batch_id=p_batch_id and job.project_id=p_project_id
  for share;
  if job_row.id is null or job_row.requested_by<>p_actor_id
     or job_row.provider<>spec_row.provider
     or job_row.input ->> 'model' is distinct from spec_row.model
     or job_row.input ->> 'format' is distinct from spec_row.format
     or job_row.input ->> 'ratio' is distinct from sku_value ->> 'provider_ratio'
     or job_row.input ->> 'resolution' is distinct from spec_row.resolution
     or job_row.input -> 'audio' is distinct from to_jsonb(spec_row.audio)
     or job_row.input -> 'last_frame' is distinct from
          to_jsonb(spec_row.last_frame)
     or job_row.input -> 'reference_media_ids' is distinct from
          spec_row.exact_scope -> 'media_ids'
     or job_row.generation_spec_id is distinct from spec_row.spec_id
     or job_row.generation_spec_version is distinct from spec_row.spec_version
     or job_row.generation_spec_hash is distinct from spec_row.spec_hash then
    raise exception using errcode='55000',
      message='generation_provider_selection_job_binding_invalid';
  end if;

  snapshot_hash_value:=content_factory_private.json_hash(snapshot_value);
  live_claim_value:=content_factory_private.generation_multimodel_live_claim_v2(
    p_organization_id,p_project_id,p_actor_id,p_job_id,spec_row.spec_id,
    spec_row.spec_version,spec_row.spec_hash
  );
  insert into content_factory.generation_job_selection_snapshots (
    organization_id,project_id,batch_id,generation_job_id,
    spec_id,spec_version,spec_hash,scope_hash,readiness_receipt_id,
    readiness_receipt_hash,snapshot_version,selection_snapshot,snapshot_hash,
    live_claim_snapshot,live_claim_snapshot_hash,
    provider,model,content_kind,selection_source,quality_status,
    catalog_version,pricing_version,estimated_cost_minor,estimated_credits,
    bound_by
  ) values (
    p_organization_id,p_project_id,p_batch_id,p_job_id,
    spec_row.spec_id,spec_row.spec_version,spec_row.spec_hash,scope_hash_value,
    receipt_row.id,
    receipt_row.receipt_hash,'generation-selection-snapshot-v1',snapshot_value,
    snapshot_hash_value,live_claim_value,live_claim_value ->> 'snapshot_hash',
    spec_row.provider,spec_row.model,
    catalog_value ->> 'content_kind',snapshot_value ->> 'selection_source',
    expected_acceptance,receipt_row.catalog_version,
    receipt_row.pricing_version,receipt_row.estimated_cost_minor,
    receipt_row.estimated_credits,p_actor_id
  );
  return jsonb_build_object(
    'snapshot_hash',snapshot_hash_value,'receipt_id',receipt_row.id,
    'receipt_hash',receipt_row.receipt_hash,'scope_hash',scope_hash_value,
    'live_claim_snapshot',live_claim_value,
    'live_claim_snapshot_hash',live_claim_value ->> 'snapshot_hash',
    'replayed',false
  );
end;
$$;

revoke all on function
  content_factory_private.bind_generation_v4_launch(
    uuid,uuid,uuid,uuid,uuid,jsonb
  ) from public, anon, authenticated, service_role;

-- The installed v56 public starter is authoritative for every historical
-- request and remains byte-for-byte behind the legacy branch. New4 uses one
-- baseline-only v2-spec/v4-receipt/selection-snapshot/live-claim branch; its
-- policy and exact confirmation checks run before begin_command or any write.
do $preserve_generation_multimodel_start_v48$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_multimodel_v48(jsonb)'
  ) is null then
    alter function public.creator_start_real_generation(jsonb)
      rename to creator_start_real_generation_pre_multimodel_v48;
    alter function
      public.creator_start_real_generation_pre_multimodel_v48(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_generation_multimodel_start_v48$;

revoke all on function content_factory_private
  .creator_start_real_generation_pre_multimodel_v48(jsonb)
  from public, anon, authenticated, service_role;

create or replace function content_factory_private
  .creator_start_real_generation_multimodel_v48(
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
  organization_id_value uuid;
  project_id_value uuid;
  campaign_id_value uuid;
  assignee_id_value uuid;
  actor_role_value text;
  idempotency_key_value text;
  effective_idempotency_key_value text;
  request_payload jsonb;
  replay_value jsonb;
  batch_id_value uuid:=extensions.gen_random_uuid();
  job_id_value uuid:=extensions.gen_random_uuid();
  task_id_value uuid:=extensions.gen_random_uuid();
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  product_row content_factory.products%rowtype;
  campaign_row content_factory.generation_campaigns%rowtype;
  sku_value jsonb;
  provider_value text;
  model_value text;
  input_mode_value text;
  format_value text;
  resolution_value text;
  duration_value integer;
  audio_value boolean;
  last_frame_value boolean;
  product_sku_value text;
  product_name_value text;
  product_category_value text;
  platform_value text;
  destination_value text;
  brief_value text;
  payout_value bigint:=0;
  media_ids_value uuid[];
  media_count_value integer;
  verified_media_count_value integer;
  reference_object_names_value jsonb;
  input_object_name_value text;
  output_object_name_value text;
  batch_input_value jsonb;
  job_input_value jsonb;
  result_value jsonb;
  binding_value jsonb;
  claim_without_hash_value jsonb;
  claim_snapshot_value jsonb;
  claim_snapshot_hash_value text;
  context_hash_value text;
  start_request_hash_value text;
  existing_binding_row content_factory.generation_job_spec_bindings%rowtype;
  existing_quality_lineage_row
    content_factory.generation_quality_guard_lineage%rowtype;
  review_autostart_value boolean:=false;
  review_terms_value text;
  user_daily_jobs bigint;
  organization_daily_jobs bigint;
  assignee_open_jobs bigint;
  organization_open_jobs bigint;
  learning_context_value jsonb;
  learning_source_value text;
  creative_brief_draft_id_value uuid;
  scenario_position_value smallint;
  applied_policy_hash_value text;
  resolved_category_value text;
  category_was_bound_value boolean:=false;
begin
  p_payload:=content_factory_private.require_payload(p_payload);
  if length(p_payload::text)>196608
     or p_payload-array[
       'organization_id','project_id','campaign_id','idempotency_key',
       'sku','product_name','product_category','count','format','brief',
       'media_ids','platform','destination_ref','assignee_id','payout_minor',
       'mode','provider','model','input_mode','duration_seconds','resolution',
       'audio','last_frame','allow_real_spend','spend_confirmation',
       'provider_readiness_receipt_id','provider_readiness_receipt_hash',
       'generation_selection_snapshot','learning_context',
       'generation_spec_context','repair_context',
       'review_autostart_confirmed','review_autostart_terms_version',
       'generation_reference_context'
     ]::text[]<>'{}'::jsonb
     or not p_payload ?& array[
       'organization_id','project_id','campaign_id','idempotency_key',
       'sku','product_name','product_category','count','format','brief',
       'media_ids','platform','destination_ref','mode','provider','model',
       'input_mode','duration_seconds','resolution','audio','last_frame',
       'allow_real_spend','spend_confirmation',
       'provider_readiness_receipt_id','provider_readiness_receipt_hash',
       'generation_selection_snapshot','learning_context',
       'generation_spec_context'
     ]::text[]
     or p_payload -> 'count' is distinct from '1'::jsonb
     or p_payload ->> 'mode' is distinct from 'real'
     or p_payload -> 'allow_real_spend' is distinct from 'true'::jsonb
     or jsonb_typeof(p_payload -> 'duration_seconds')<>'number'
     or p_payload ->> 'duration_seconds' !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'audio')<>'boolean'
     or jsonb_typeof(p_payload -> 'last_frame')<>'boolean'
     or jsonb_typeof(p_payload -> 'media_ids')<>'array'
     or jsonb_array_length(p_payload -> 'media_ids') not between 1 and 5
     or jsonb_typeof(p_payload -> 'learning_context')<>'object'
     or jsonb_typeof(p_payload -> 'generation_spec_context')<>'object'
     or jsonb_typeof(p_payload -> 'generation_selection_snapshot')<>'object'
  then
    raise exception using errcode='22023',
      message='real_generation_payload_invalid';
  end if;

  provider_value:=lower(btrim(coalesce(p_payload ->> 'provider','')));
  model_value:=lower(btrim(coalesce(p_payload ->> 'model','')));
  input_mode_value:=lower(btrim(coalesce(p_payload ->> 'input_mode','')));
  format_value:=btrim(coalesce(p_payload ->> 'format',''));
  resolution_value:=btrim(coalesce(p_payload ->> 'resolution',''));
  begin
    duration_value:=(p_payload ->> 'duration_seconds')::integer;
    audio_value:=(p_payload ->> 'audio')::boolean;
    last_frame_value:=(p_payload ->> 'last_frame')::boolean;
  exception when numeric_value_out_of_range then
    raise exception using errcode='22023',
      message='real_generation_payload_invalid';
  end;
  if provider_value<>'runway'
     or model_value not in (
       'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
     ) then
    raise exception using errcode='42501',
      message='generation_provider_launch_blocked';
  end if;
  sku_value:=content_factory_private.real_generation_multimodel_sku(
    provider_value,model_value,input_mode_value,duration_value,format_value,
    resolution_value,audio_value,last_frame_value
  );
  if sku_value is null
     or p_payload ->> 'spend_confirmation' is distinct from
          sku_value ->> 'spend_confirmation'
     or not content_factory_private.generation_provider_launch_enabled(
          content_factory_private.require_uuid(p_payload,'organization_id'),
          provider_value,model_value
        ) then
    raise exception using errcode='42501',
      message='real_generation_spend_confirmation_required';
  end if;

  actor_id_value:=content_factory_private.current_profile_id();
  organization_id_value:=content_factory_private.resolve_organization(
    p_payload
  );
  actor_role_value:=content_factory_private.membership_role(
    organization_id_value,true,
    array['owner','admin','producer','operator']
  );
  project_id_value:=content_factory_private.require_uuid(
    p_payload,'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,project_id_value,auth.uid()
  );
  -- Dynamic learning/provenance readers are project-scoped wrappers. Install
  -- the already-authorized project before either a fresh assertion or an
  -- exact replay bind; the transaction-local setting cannot escape this RPC.
  perform set_config('contentengine.project_id',project_id_value::text,true);
  campaign_id_value:=content_factory_private.require_uuid(
    p_payload,'campaign_id'
  );
  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id=organization_id_value
    and campaign.id=campaign_id_value
  for share;
  if campaign_row.id is null then
    raise exception using errcode='22023',
      message='paid_generation_campaign_required';
  end if;
  if campaign_row.status<>'active' then
    raise exception using errcode='42501',
      message='paid_generation_campaign_not_active';
  end if;

  idempotency_key_value:=content_factory_private.require_text(
    p_payload,'idempotency_key',8,180
  );
  effective_idempotency_key_value:='v48:' ||
    replace(actor_id_value::text,'-','') || ':' ||
    content_factory_private.raw_text_sha256(idempotency_key_value);
  product_sku_value:=content_factory_private.require_text(
    p_payload,'sku',1,120
  );
  product_name_value:=content_factory_private.require_text(
    p_payload,'product_name',2,180
  );
  product_category_value:=lower(content_factory_private.require_text(
    p_payload,'product_category',2,40
  ));
  platform_value:=lower(content_factory_private.require_text(
    p_payload,'platform',2,40
  ));
  destination_value:=content_factory_private.require_text(
    p_payload,'destination_ref',2,240
  );
  brief_value:=btrim(coalesce(p_payload ->> 'brief',''));
  if product_category_value not in (
       'cosmetics','baa','sports_food','food','household',
       'apparel','electronics','other'
     )
     or platform_value not in (
       'instagram','tiktok','youtube','vk','telegram','wildberries'
     )
     or length(brief_value) not between 1 and (case model_value
       when 'gen4.5' then 1000
       when 'seedance2_mini' then 3500
       when 'veo3.1_fast' then 1000
       else 4000 end) then
    raise exception using errcode='22023',message='brief_invalid';
  end if;
  if not content_factory_private.generation_multimodel_prompt_contract_valid(
       model_value,duration_value,format_value,audio_value,
       product_name_value,product_sku_value,product_category_value,brief_value
     ) then
    raise exception using errcode='55000',
      message='generation_mode_prompt_binding_invalid';
  end if;

  assignee_id_value:=actor_id_value;
  if nullif(btrim(coalesce(p_payload ->> 'assignee_id','')),'') is not null then
    assignee_id_value:=content_factory_private.require_uuid(
      p_payload,'assignee_id'
    );
  end if;
  if coalesce(p_payload ->> 'payout_minor','0') !~ '^[0-9]+$' then
    raise exception using errcode='22023',message='payout_minor_invalid';
  end if;
  begin
    payout_value:=coalesce(p_payload ->> 'payout_minor','0')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode='22023',message='payout_minor_invalid';
  end;
  if payout_value not between 0 and 1000000 then
    raise exception using errcode='22023',message='payout_minor_invalid';
  end if;
  if actor_role_value not in ('owner','admin') and payout_value<>0 then
    raise exception using errcode='42501',message='payout_role_not_allowed';
  end if;
  if actor_role_value='operator' and assignee_id_value<>actor_id_value then
    raise exception using errcode='42501',
      message='assignee_role_not_allowed';
  end if;
  if not content_factory_private.generated_media_reviewer_access_allowed(
       organization_id_value,assignee_id_value
     ) or not content_factory_private.workspace_project_access_allowed(
       organization_id_value,project_id_value,assignee_id_value
     ) then
    raise exception using errcode='42501',message='certified_assignee_required';
  end if;

  if p_payload ? 'generation_reference_context' then
    raise exception using errcode='42501',
      message='generation_video_reference_model_unsupported';
  end if;
  if p_payload ? 'repair_context' then
    raise exception using errcode='42501',
      message='generation_repair_model_unsupported';
  end if;
  if p_payload ? 'review_autostart_confirmed'
     or p_payload ? 'review_autostart_terms_version' then
    if p_payload -> 'review_autostart_confirmed' is distinct from 'true'::jsonb
       or p_payload ->> 'review_autostart_terms_version' is distinct from
            'generated-video-qa-autostart-v1' then
      raise exception using errcode='22023',
        message='generation_review_autostart_consent_invalid';
    end if;
    review_autostart_value:=true;
    review_terms_value:='generated-video-qa-autostart-v1';
  end if;

  if p_payload -> 'generation_spec_context'
       -array['spec_id','spec_version','spec_hash']::text[]<>'{}'::jsonb
     or not p_payload -> 'generation_spec_context' ?& array[
       'spec_id','spec_version','spec_hash'
     ]::text[]
     or jsonb_typeof(
       p_payload #> '{generation_spec_context,spec_version}'
     )<>'number'
     or p_payload #>> '{generation_spec_context,spec_version}' !~ '^[0-9]+$'
  then
    raise exception using errcode='22023',
      message='generation_spec_context_invalid';
  end if;
  begin
    spec_id_value:=(p_payload #>> '{generation_spec_context,spec_id}')::uuid;
    spec_version_value:=(
      p_payload #>> '{generation_spec_context,spec_version}'
    )::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using errcode='22023',
      message='generation_spec_context_invalid';
  end;
  spec_hash_value:=lower(btrim(coalesce(
    p_payload #>> '{generation_spec_context,spec_hash}',''
  )));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode='22023',
      message='generation_spec_context_invalid';
  end if;

  request_payload:=p_payload-'organization_id'-'idempotency_key';
  replay_value:=content_factory_private.begin_command(
    organization_id_value,'creator_start_real_generation_multimodel_v48',
    effective_idempotency_key_value,request_payload
  );
  if replay_value is not null then
    begin
      batch_id_value:=(replay_value #>> '{batch,id}')::uuid;
      job_id_value:=(replay_value #>> '{job,id}')::uuid;
    exception when invalid_text_representation or null_value_not_allowed then
      raise exception using errcode='55000',
        message='generation_provider_selection_job_binding_invalid';
    end;
    perform content_factory_private.bind_generation_v4_launch(
      organization_id_value,project_id_value,actor_id_value,
      batch_id_value,job_id_value,p_payload
    );
    if not exists (
      select 1
      from content_factory.generation_job_spec_bindings binding
      where binding.organization_id=organization_id_value
        and binding.generation_job_id=job_id_value
        and binding.spec_id=spec_id_value
        and binding.spec_version=spec_version_value
        and binding.spec_hash=spec_hash_value
        and binding.bound_by=actor_id_value
    ) then
      raise exception using errcode='55000',
        message='generation_spec_job_binding_invalid';
    end if;
    return replay_value;
  end if;

  spec_row:=content_factory_private.assert_generation_spec_current(
    organization_id_value,spec_id_value,spec_version_value,spec_hash_value,
    true,true
  );
  if content_factory_private.require_generation_spec_project_v49(
       organization_id_value,project_id_value,spec_id_value,
       spec_version_value,spec_hash_value,spec_row.product_id
     ) is distinct from spec_row.product_id
     or spec_row.spec_contract_version<>'generation-spec-scope-v2'
     or spec_row.exact_scope is distinct from
          content_factory_private.generation_spec_scope_v2(spec_row.exact_scope)
     or spec_row.exact_scope -> 'media_ids' is distinct from
          p_payload -> 'media_ids'
     or spec_row.provider is distinct from provider_value
     or spec_row.model is distinct from model_value
     or spec_row.input_mode is distinct from input_mode_value
     or spec_row.duration_seconds<>duration_value
     or spec_row.product_category is distinct from product_category_value
     or spec_row.platform is distinct from platform_value
     or spec_row.format is distinct from format_value
     or spec_row.ratio is distinct from format_value
     or spec_row.resolution is distinct from resolution_value
     or spec_row.audio is distinct from audio_value
     or spec_row.last_frame is distinct from last_frame_value
     or spec_row.compiled_prompt is distinct from brief_value
     or spec_row.canonical_learning_context is distinct from
          p_payload -> 'learning_context' then
    raise exception using errcode='55000',
      message='generation_spec_scope_binding_invalid';
  end if;

  select product.* into product_row
  from content_factory.products product
  where product.organization_id=organization_id_value
    and product.id=spec_row.product_id
  for update;
  if product_row.id is null or product_row.status<>'active'
     or product_row.sku is distinct from product_sku_value
     or product_row.title is distinct from product_name_value then
    raise exception using errcode='55000',
      message='generation_spec_product_binding_invalid';
  end if;
  resolved_category_value:=content_factory_private
    .resolved_content_review_category(product_row.metadata);
  if coalesce(resolved_category_value,'')='' then
    if actor_role_value='operator' then
      raise exception using errcode='42501',
        message='content_review_product_category_unverified';
    end if;
    update content_factory.products product
    set metadata=product.metadata || jsonb_build_object(
          'content_review_category',product_category_value,
          'content_review_category_confirmed_by',actor_id_value,
          'content_review_category_confirmed_at',clock_timestamp(),
          'content_review_category_ruleset','ru-content-compliance-2026-07-16.1'
        ),
        updated_at=clock_timestamp()
    where product.organization_id=organization_id_value
      and product.id=product_row.id
    returning * into product_row;
    resolved_category_value:=product_category_value;
    category_was_bound_value:=true;
  elsif resolved_category_value is distinct from product_category_value then
    raise exception using errcode='22023',
      message='content_review_product_category_mismatch';
  end if;

  begin
    select array_agg(item.value::uuid order by item.ordinality)
      into media_ids_value
    from jsonb_array_elements_text(p_payload -> 'media_ids')
      with ordinality item(value,ordinality);
  exception when invalid_text_representation then
    raise exception using errcode='22023',message='media_id_invalid';
  end;
  media_count_value:=cardinality(media_ids_value);
  select count(*)::integer,
         jsonb_agg(to_jsonb(media.object_name) order by selected.ordinality)
    into verified_media_count_value,reference_object_names_value
  from unnest(media_ids_value) with ordinality selected(media_id,ordinality)
  join content_factory.media_objects media
    on media.organization_id=organization_id_value
   and media.id=selected.media_id
   and media.project_id=project_id_value
   and media.product_id=spec_row.product_id
   and media.status='ready'
   and media.mime_type in ('image/jpeg','image/png','image/webp')
   and coalesce(media.metadata ->> 'kind','') in ('product_photo','packshot')
   and media.metadata -> 'rights_confirmed'='true'::jsonb;
  if verified_media_count_value<>media_count_value
     or media_ids_value[1]<>spec_row.primary_media_id
     or reference_object_names_value is null then
    raise exception using errcode='42501',
      message='exact_product_reference_bundle_mismatch';
  end if;
  input_object_name_value:=reference_object_names_value ->> 0;
  output_object_name_value:=organization_id_value::text || '/' ||
    assignee_id_value::text || '/generated/' || job_id_value::text || '.mp4';

  perform set_config(
    'content_factory.generation_campaign_id',campaign_id_value::text,true
  );
  perform set_config(
    'content_factory.generation_spec_id',spec_row.spec_id::text,true
  );
  perform set_config(
    'content_factory.generation_spec_version',spec_row.spec_version::text,true
  );
  perform set_config(
    'content_factory.generation_spec_hash',spec_row.spec_hash,true
  );
  perform set_config(
    'content_factory.generation_product_category',product_category_value,true
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('real_generation_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text || ':' || actor_id_value::text),
    hashtext('real_generation_quota:user')
  );
  select count(*) filter (where job.requested_by=actor_id_value),count(*)
    into user_daily_jobs,organization_daily_jobs
  from content_factory.generation_jobs job
  where job.organization_id=organization_id_value
    and job.mode='real' and job.created_at>=now()-interval '24 hours';
  select count(*) filter (where job.assigned_to=assignee_id_value),count(*)
    into assignee_open_jobs,organization_open_jobs
  from content_factory.generation_jobs job
  where job.organization_id=organization_id_value and job.mode='real'
    and job.status in ('queued','starting','submitted','processing');
  if user_daily_jobs>=10 then
    raise exception using errcode='54000',
      message='real_generation_user_daily_quota_exceeded';
  elsif organization_daily_jobs>=50 then
    raise exception using errcode='54000',
      message='real_generation_organization_daily_quota_exceeded';
  elsif assignee_open_jobs>=1 then
    raise exception using errcode='54000',
      message='real_generation_assignee_concurrency_exceeded';
  elsif organization_open_jobs>=3 then
    raise exception using errcode='54000',
      message='real_generation_organization_concurrency_exceeded';
  end if;

  batch_input_value:=jsonb_build_object(
    'job_id',job_id_value,'review_task_id',task_id_value,
    'provider',provider_value,'model',model_value,
    'input_mode',input_mode_value,'duration_seconds',duration_value,
    'format',format_value,'ratio',sku_value ->> 'provider_ratio',
    'resolution',resolution_value,'audio',audio_value,
    'last_frame',last_frame_value,'media_id',media_ids_value[1],
    'media_ids',to_jsonb(media_ids_value),
    'reference_media_ids',to_jsonb(media_ids_value),
    'assigned_to',assignee_id_value,
    'spend_confirmation',sku_value ->> 'spend_confirmation',
    'provider_readiness_receipt_id',
      p_payload ->> 'provider_readiness_receipt_id',
    'provider_readiness_receipt_hash',
      lower(p_payload ->> 'provider_readiness_receipt_hash'),
    'generation_selection_snapshot',
      p_payload -> 'generation_selection_snapshot',
    'generation_spec_context',p_payload -> 'generation_spec_context',
    'review_autostart_confirmed',review_autostart_value,
    'review_autostart_terms_version',to_jsonb(review_terms_value),
    'billing',jsonb_build_object(
      'currency','USD',
      'estimated_cost_minor',(sku_value ->> 'estimated_cost_minor')::bigint,
      'estimated_credits',(sku_value ->> 'estimated_credits')::bigint,
      'credit_unit_usd_minor',1
    )
  );
  job_input_value:=jsonb_build_object(
    'sku',product_sku_value,'product_name',product_name_value,
    'product_category',product_category_value,'prompt_text',brief_value,
    'format',format_value,'ratio',sku_value ->> 'provider_ratio',
    'resolution',resolution_value,'audio',audio_value,
    'last_frame',last_frame_value,'input_mode',input_mode_value,
    'input_media_id',media_ids_value[1],
    'input_object_name',input_object_name_value,
    'reference_media_ids',to_jsonb(media_ids_value),
    'reference_object_names',reference_object_names_value,
    'reference_image_count',spec_row.reference_count,
    'output_object_name',output_object_name_value,
    'review_task_id',task_id_value,'provider',provider_value,
    'model',model_value,'duration_seconds',duration_value,
    'platform',platform_value,'destination_ref',destination_value,
    'spend_confirmation',sku_value ->> 'spend_confirmation',
    'provider_readiness_receipt_id',
      p_payload ->> 'provider_readiness_receipt_id',
    'provider_readiness_receipt_hash',
      lower(p_payload ->> 'provider_readiness_receipt_hash'),
    'generation_selection_snapshot',
      p_payload -> 'generation_selection_snapshot',
    'generation_spec_context',p_payload -> 'generation_spec_context',
    'review_autostart_confirmed',review_autostart_value,
    'review_autostart_terms_version',to_jsonb(review_terms_value),
    'learning_context',p_payload -> 'learning_context',
    'billing',jsonb_build_object(
      'currency','USD',
      'estimated_cost_minor',(sku_value ->> 'estimated_cost_minor')::bigint,
      'estimated_credits',(sku_value ->> 'estimated_credits')::bigint,
      'credit_unit_usd_minor',1
    )
  );

  insert into content_factory.generation_batches (
    id,organization_id,product_id,created_by,name,mode,allow_real_spend,
    status,total_requested,total_created,input,request_hash,idempotency_key,
    provider,model,duration_seconds,audio,estimated_cost_minor,
    estimated_credits,currency,campaign_id,project_id
  ) values (
    batch_id_value,organization_id_value,spec_row.product_id,actor_id_value,
    left((sku_value ->> 'public_label') || ' ' || product_sku_value ||
      ' - 1 video',180),
    'real',true,'queued',1,0,batch_input_value,
    content_factory_private.json_hash(request_payload),
    effective_idempotency_key_value,provider_value,model_value,duration_value,
    audio_value,(sku_value ->> 'estimated_cost_minor')::bigint,
    (sku_value ->> 'estimated_credits')::bigint,'USD',campaign_id_value,
    project_id_value
  );

  insert into content_factory.generation_jobs (
    id,organization_id,product_id,batch_id,ordinal,requested_by,assigned_to,
    mode,provider,allow_real_spend,estimated_cost_minor,actual_cost_minor,
    status,input,output,request_hash,idempotency_key,campaign_id,project_id,
    generation_video_reference_decided
  ) values (
    job_id_value,organization_id_value,spec_row.product_id,batch_id_value,1,
    actor_id_value,assignee_id_value,'real',provider_value,true,
    (sku_value ->> 'estimated_cost_minor')::bigint,0,'queued',job_input_value,
    '{}'::jsonb,content_factory_private.json_hash(request_payload),
    'real-job:' || content_factory_private.json_hash(jsonb_build_object(
      'organization_id',organization_id_value,
      'actor_id',actor_id_value,
      'idempotency_key',idempotency_key_value
    )),campaign_id_value,project_id_value,true
  );

  insert into content_factory.creator_tasks (
    id,organization_id,assignee_id,created_by,product_id,generation_job_id,
    task_type,title,instructions,status,priority,payout_minor,result,
    idempotency_key,project_id
  ) values (
    task_id_value,organization_id_value,assignee_id_value,actor_id_value,
    spec_row.product_id,job_id_value,'video_review',
    left('Review ' || (sku_value ->> 'public_label') || ' video - ' ||
      product_name_value,240),
    'Generation is in progress. Review the exact MP4 and audio state only after this task moves to review.',
    'blocked',2,payout_value,jsonb_build_object(
      'generation_status','queued','review_required',true,
      'provider',provider_value,'model',model_value,
      'duration_seconds',duration_value,'resolution',resolution_value,
      'audio',audio_value,'last_frame',last_frame_value,
      'estimated_cost_minor',(sku_value ->> 'estimated_cost_minor')::bigint,
      'estimated_credits',(sku_value ->> 'estimated_credits')::bigint,
      'currency','USD'
    ),
    'real-review:' || content_factory_private.json_hash(jsonb_build_object(
      'organization_id',organization_id_value,'job_id',job_id_value
    )),project_id_value
  );

  if review_autostart_value then
    insert into content_factory.generation_review_autostart_consents (
      organization_id,generation_job_id,confirmed_by,terms_version
    ) values (
      organization_id_value,job_id_value,actor_id_value,review_terms_value
    );
    perform content_factory_private.emit_event(
      organization_id_value,actor_id_value,
      'generation_review_autostart_consented','generation_job',
      job_id_value::text,jsonb_build_object(
        'model',model_value,'terms_version',review_terms_value,
        'transcription_requested',false
      ),'generation-review-autostart-consent:' || job_id_value::text
    );
  end if;
  perform content_factory_private.emit_event(
    organization_id_value,actor_id_value,
    'generation_product_category_bound','generation_job',job_id_value::text,
    jsonb_build_object(
      'product_id',product_row.id,
      'product_category',resolved_category_value,
      'metadata_created',category_was_bound_value
    ),'generation-product-category:' || job_id_value::text
  );

  learning_context_value:=spec_row.canonical_learning_context;
  learning_source_value:=learning_context_value ->> 'source';
  if learning_source_value='approved_research' then
    creative_brief_draft_id_value:=(
      learning_context_value ->> 'creative_brief_draft_id'
    )::uuid;
    scenario_position_value:=(
      learning_context_value ->> 'scenario_position'
    )::smallint;
  elsif learning_source_value='performance_learning' then
    applied_policy_hash_value:=learning_context_value ->> 'applied_policy_hash';
  end if;
  insert into content_factory.generation_creative_signals (
    organization_id,generation_job_id,product_id,platform,model,
    creative_angle,hook_patterns,source,compiler_version,
    applied_policy_hash,creative_brief_draft_id,scenario_position,
    prompt_hash,product_category
  ) values (
    organization_id_value,job_id_value,spec_row.product_id,platform_value,
    model_value,learning_context_value ->> 'creative_angle',
    learning_context_value -> 'hook_patterns',learning_source_value,
    learning_context_value ->> 'compiler_version',applied_policy_hash_value,
    creative_brief_draft_id_value,scenario_position_value,
    content_factory_private.json_hash(to_jsonb(brief_value)),
    product_category_value
  );

  insert into content_factory.generation_quality_guard_lineage (
    organization_id,generation_job_id,product_id,platform,model,source,
    applied_policy_hash,guard_codes,prompt_hash,created_by
  ) values (
    organization_id_value,job_id_value,spec_row.product_id,platform_value,
    model_value,'baseline',null,'[]'::jsonb,
    content_factory_private.json_hash(to_jsonb(brief_value)),actor_id_value
  ) on conflict (organization_id,generation_job_id) do nothing;
  select lineage.* into existing_quality_lineage_row
  from content_factory.generation_quality_guard_lineage lineage
  where lineage.organization_id=organization_id_value
    and lineage.generation_job_id=job_id_value;
  if existing_quality_lineage_row.id is null
     or existing_quality_lineage_row.product_id<>spec_row.product_id
     or existing_quality_lineage_row.platform<>platform_value
     or existing_quality_lineage_row.model<>model_value
     or existing_quality_lineage_row.source<>'baseline'
     or existing_quality_lineage_row.applied_policy_hash is not null
     or existing_quality_lineage_row.guard_codes<>'[]'::jsonb
     or existing_quality_lineage_row.prompt_hash is distinct from
          content_factory_private.json_hash(to_jsonb(brief_value))
     or existing_quality_lineage_row.created_by<>actor_id_value then
    raise exception using errcode='23505',
      message='generation_quality_guard_lineage_conflict';
  end if;

  result_value:=jsonb_build_object(
    'ok',true,
    'batch',jsonb_build_object(
      'id',batch_id_value,'status','queued','campaign_id',campaign_id_value
    ),
    'job',jsonb_build_object(
      'id',job_id_value,'batch_id',batch_id_value,
      'campaign_id',campaign_id_value,'campaign_name',campaign_row.name,
      'status','queued','provider',provider_value,'model',model_value,
      'input_mode',input_mode_value,'duration_seconds',duration_value,
      'resolution',resolution_value,'audio',audio_value,
      'last_frame',last_frame_value,'ratio',format_value,
      'prompt_text',brief_value,'input_object_name',input_object_name_value,
      'reference_object_names',reference_object_names_value,
      'reference_image_count',spec_row.reference_count,
      'output_object_name',output_object_name_value,
      'estimated_cost_minor',(sku_value ->> 'estimated_cost_minor')::bigint,
      'estimated_credits',(sku_value ->> 'estimated_credits')::bigint,
      'review_autostart_confirmed',review_autostart_value,
      'review_autostart_terms_version',to_jsonb(review_terms_value),
      'generation_spec_context',p_payload -> 'generation_spec_context'
    )
  );

  binding_value:=content_factory_private.bind_generation_v4_launch(
    organization_id_value,project_id_value,actor_id_value,
    batch_id_value,job_id_value,p_payload
  );
  result_value:=jsonb_set(
    result_value,'{job,generation_selection_snapshot_hash}',
    binding_value -> 'snapshot_hash',true
  );

  -- Keep the mature terminalization/inspection owner complete. The exact v4
  -- launch row and the existing job-spec binding store the same recomputable
  -- live claim; a stale provider transition therefore follows the mature
  -- atomic terminalization/spend-release path.
  start_request_hash_value:=content_factory_private.json_hash(request_payload);
  claim_snapshot_value:=binding_value -> 'live_claim_snapshot';
  claim_snapshot_hash_value:=binding_value ->> 'live_claim_snapshot_hash';
  context_hash_value:=content_factory_private.json_hash(jsonb_build_object(
    'organization_id',organization_id_value,
    'project_id',project_id_value,
    'generation_job_id',job_id_value,
    'spec_id',spec_row.spec_id,
    'spec_version',spec_row.spec_version,
    'spec_hash',spec_row.spec_hash,
    'prompt_hash',spec_row.prompt_hash,
    'final_policy_hash',spec_row.final_policy_hash,
    'claim_snapshot_hash',claim_snapshot_hash_value,
    'generation_selection_snapshot_hash',binding_value ->> 'snapshot_hash',
    'provider_readiness_receipt_id',binding_value ->> 'receipt_id',
    'provider_readiness_receipt_hash',binding_value ->> 'receipt_hash',
    'scope_hash',binding_value ->> 'scope_hash'
  ));
  insert into content_factory.generation_job_spec_bindings (
    organization_id,generation_job_id,spec_id,spec_version,spec_hash,
    prompt_hash,final_policy_hash,outcome_selection_id,outcome_selection_hash,
    context_hash,start_request_hash,start_result,claim_snapshot,
    claim_snapshot_hash,bound_by
  ) values (
    organization_id_value,job_id_value,spec_row.spec_id,spec_row.spec_version,
    spec_row.spec_hash,spec_row.prompt_hash,spec_row.final_policy_hash,
    spec_row.outcome_selection_id,spec_row.outcome_selection_hash,
    context_hash_value,start_request_hash_value,result_value,
    claim_snapshot_value,claim_snapshot_hash_value,actor_id_value
  ) on conflict (organization_id,generation_job_id) do nothing;
  select binding.* into existing_binding_row
  from content_factory.generation_job_spec_bindings binding
  where binding.organization_id=organization_id_value
    and binding.generation_job_id=job_id_value;
  if existing_binding_row.id is null
     or existing_binding_row.spec_id<>spec_row.spec_id
     or existing_binding_row.spec_version<>spec_row.spec_version
     or existing_binding_row.spec_hash<>spec_row.spec_hash
     or existing_binding_row.prompt_hash<>spec_row.prompt_hash
     or existing_binding_row.final_policy_hash<>spec_row.final_policy_hash
     or existing_binding_row.context_hash<>context_hash_value
     or existing_binding_row.start_request_hash<>start_request_hash_value
     or existing_binding_row.start_result<>result_value
     or existing_binding_row.claim_snapshot<>claim_snapshot_value
     or existing_binding_row.claim_snapshot_hash<>claim_snapshot_hash_value
     or existing_binding_row.bound_by<>actor_id_value then
    raise exception using errcode='23505',message='idempotency_key_conflict';
  end if;

  perform content_factory_private.emit_event(
    organization_id_value,actor_id_value,'real_generation_queued',
    'generation_job',job_id_value::text,jsonb_build_object(
      'provider',provider_value,'model',model_value,
      'duration_seconds',duration_value,'resolution',resolution_value,
      'audio',audio_value,'estimated_cost_minor',
        (sku_value ->> 'estimated_cost_minor')::bigint,
      'estimated_credits',(sku_value ->> 'estimated_credits')::bigint,
      'currency','USD','automatic_generation',false,'automatic_spend',false
    ),
    'real-generation-v48:' || effective_idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,actor_id_value,
    'creator_start_real_generation_multimodel_v48',
    effective_idempotency_key_value,request_payload,result_value
  );
end;
$$;

revoke all on function content_factory_private
  .creator_start_real_generation_multimodel_v48(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare provider_value text; model_value text;
begin
  p_payload:=content_factory_private.require_payload(p_payload);
  provider_value:=lower(btrim(coalesce(p_payload ->> 'provider','runway')));
  model_value:=lower(btrim(coalesce(p_payload ->> 'model','')));
  if provider_value='runway' and model_value in (
       'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
     ) then
    return content_factory_private
      .creator_start_real_generation_multimodel_v48(p_payload);
  end if;
  return content_factory_private
    .creator_start_real_generation_pre_multimodel_v48(p_payload);
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

-- Edge performs an authenticated status read immediately after start and
-- before the service-role claim. The historical projection did not expose
-- resolution/last_frame and only recognized the original video consent
-- models, so enrich only new4 rows while preserving all legacy response bytes.
do $preserve_generation_multimodel_status_v48$
begin
  if to_regprocedure(
    'content_factory_private.creator_real_generation_status_pre_multimodel_v48(jsonb)'
  ) is null then
    alter function public.creator_real_generation_status(jsonb)
      rename to creator_real_generation_status_pre_multimodel_v48;
    alter function
      public.creator_real_generation_status_pre_multimodel_v48(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_generation_multimodel_status_v48$;

revoke all on function content_factory_private
  .creator_real_generation_status_pre_multimodel_v48(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_real_generation_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  result_value jsonb;
  organization_id_value uuid;
  project_id_value uuid;
  job_id_value uuid;
  job_row content_factory.generation_jobs%rowtype;
  consent_terms_value text;
begin
  result_value:=content_factory_private
    .creator_real_generation_status_pre_multimodel_v48(p_payload);
  if result_value #>> '{job,model}' not in (
       'gen4.5','seedance2_mini','veo3.1_fast','gemini_omni_flash'
     ) then
    return result_value;
  end if;
  p_payload:=content_factory_private.require_payload(p_payload);
  organization_id_value:=content_factory_private.resolve_organization(
    p_payload
  );
  project_id_value:=content_factory_private.require_uuid(
    p_payload,'project_id'
  );
  begin
    job_id_value:=(result_value #>> '{job,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using errcode='55000',
      message='real_generation_status_binding_invalid';
  end;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id=organization_id_value
    and job.project_id=project_id_value
    and job.id=job_id_value
    and job.mode='real' and job.provider='runway'
  for share;
  if job_row.id is null
     or job_row.input ->> 'model' is distinct from
          result_value #>> '{job,model}' then
    raise exception using errcode='55000',
      message='real_generation_status_binding_invalid';
  end if;
  select consent.terms_version into consent_terms_value
  from content_factory.generation_review_autostart_consents consent
  where consent.organization_id=organization_id_value
    and consent.generation_job_id=job_id_value;
  result_value:=jsonb_set(
    result_value,'{job,input_mode}',
    to_jsonb(job_row.input ->> 'input_mode'),true
  );
  result_value:=jsonb_set(
    result_value,'{job,resolution}',
    to_jsonb(job_row.input ->> 'resolution'),true
  );
  result_value:=jsonb_set(
    result_value,'{job,ratio}',
    to_jsonb(job_row.input ->> 'format'),true
  );
  result_value:=jsonb_set(
    result_value,'{job,last_frame}',
    coalesce(job_row.input -> 'last_frame','false'::jsonb),true
  );
  result_value:=jsonb_set(
    result_value,'{job,review_autostart_confirmed}',
    to_jsonb(consent_terms_value='generated-video-qa-autostart-v1'),true
  );
  result_value:=jsonb_set(
    result_value,'{job,review_autostart_terms_version}',
    coalesce(to_jsonb(consent_terms_value),'null'::jsonb),true
  );
  return result_value;
end;
$$;

revoke all on function public.creator_real_generation_status(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_real_generation_status(jsonb)
  to authenticated;

-- Generated-video review remains one existing evidence/decision workflow.
-- Generalize its three model-hardcoded guards in place; no parallel review
-- route, fake review or automatic approval is introduced.
create or replace function
  content_factory_private.generation_runway_video_review_model_allowed(
    p_model text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select lower(btrim(coalesce(p_model,''))) in (
    'gen4_turbo','seedance2_fast','gen4.5','seedance2_mini',
    'veo3.1_fast','gemini_omni_flash'
  )
$$;

revoke all on function
  content_factory_private.generation_runway_video_review_model_allowed(text)
  from public, anon, authenticated, service_role;

-- Keep the existing media trigger as the single spoken-script owner. Audio
-- new4 prompts use the same exact `Реплика героя дословно` contract, so their
-- immutable generated-video metadata must reach the mature speech QA flow.
create or replace function
  content_factory_private.bind_generated_video_spoken_script()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  generation_job_id_value uuid;
  spoken_script_value text;
begin
  if new.metadata ->> 'kind'<>'generated_video'
     or new.metadata ->> 'provider'<>'runway'
     or coalesce(new.metadata ->> 'generation_job_id','') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  then
    return new;
  end if;
  generation_job_id_value:=(new.metadata ->> 'generation_job_id')::uuid;
  select content_factory_private.generated_video_spoken_script(
           job.input ->> 'prompt_text'
         )
    into spoken_script_value
  from content_factory.generation_jobs job
  where job.organization_id=new.organization_id
    and job.id=generation_job_id_value
    and job.mode='real'
    and job.provider='runway'
    and content_factory_private.generation_runway_video_review_model_allowed(
          job.input ->> 'model'
        )
    and job.input -> 'audio'='true'::jsonb;
  if spoken_script_value is not null then
    new.metadata:=new.metadata || jsonb_build_object(
      'spoken_script',spoken_script_value,
      'spoken_script_source','generation_job_prompt_v1'
    );
  else
    new.metadata:=new.metadata-array[
      'spoken_script','spoken_script_source'
    ]::text[];
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.bind_generated_video_spoken_script()
  from public, anon, authenticated, service_role;

do $patch_generated_video_review_new4$
declare
  function_signature regprocedure;
  function_definition text;
  patched_definition text;
  old_fragment constant text:=$old$
     or job_row.input ->> 'model' not in (
       'gen4_turbo', 'seedance2_fast'
     )$old$;
  new_fragment constant text:=$new$
     or not content_factory_private
       .generation_runway_video_review_model_allowed(
         job_row.input ->> 'model'
       )$new$;
begin
  foreach function_signature in array array[
    'content_factory_private.enforce_generated_video_autopilot_input()'
      ::regprocedure,
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'
      ::regprocedure,
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'
      ::regprocedure
  ] loop
    function_definition:=pg_catalog.pg_get_functiondef(function_signature);
    patched_definition:=replace(
      function_definition,old_fragment,new_fragment
    );
    if patched_definition=function_definition then
      raise exception using errcode='55000',
        message='generation_video_review_multimodel_patch_target_invalid',
        detail=function_signature::text;
    end if;
    execute patched_definition;
  end loop;
end;
$patch_generated_video_review_new4$;

-- The sound-assessment owner predates configurable audio on the new Runway
-- models. Keep its existing provenance chain, but derive the expected audio
-- bit from the exact persisted job after the canonical model allowlist check.
do $patch_generated_video_sound_new4$
declare
  function_signature constant regprocedure :=
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure;
  function_definition text;
  patched_definition text;
  old_fragment constant text := $old$
  server_audio_value := case generation_job_row.input ->> 'model'
    when 'seedance2_fast' then true
    when 'gen4_turbo' then false
    else null
  end;$old$;
  new_fragment constant text := $new$
  server_audio_value := case
    when content_factory_private.generation_runway_video_review_model_allowed(
      generation_job_row.input ->> 'model'
    )
      then (
        content_factory_private.real_generation_sku_from_input(
          generation_job_row.provider, generation_job_row.input
        ) ->> 'audio'
      )::boolean
    else null
  end;$new$;
begin
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  patched_definition := replace(
    function_definition, old_fragment, new_fragment
  );
  if patched_definition = function_definition then
    raise exception using errcode = '55000',
      message = 'generation_video_sound_multimodel_patch_target_invalid',
      detail = function_signature::text;
  end if;
  execute patched_definition;
end;
$patch_generated_video_sound_new4$;

notify pgrst, 'reload schema';

commit;

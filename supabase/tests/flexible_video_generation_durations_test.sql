begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(15);

select is(
  content_factory_private.real_generation_sku_config(
    'gen4_turbo', '2'::jsonb, 'false'::jsonb, '9:16',
    'RUNWAY_GEN4_TURBO_2S_USD_0.10'
  ) -> 'estimated_credits',
  '10'::jsonb,
  'Gen-4 two-second price is bound to ten credits'
);

select is(
  content_factory_private.real_generation_sku_config(
    'gen4_turbo', '10'::jsonb, 'false'::jsonb, '16:9',
    'RUNWAY_GEN4_TURBO_10S_USD_0.50'
  ) -> 'estimated_credits',
  '50'::jsonb,
  'Gen-4 ten-second price is bound to fifty credits'
);

select is(
  content_factory_private.real_generation_sku_config(
    'seedance2_fast', '4'::jsonb, 'true'::jsonb, '9:16',
    'RUNWAY_SEEDANCE2_FAST_4S_AUDIO_USD_1.16'
  ) -> 'estimated_credits',
  '116'::jsonb,
  'Seedance four-second price is bound to 116 credits'
);

select is(
  content_factory_private.real_generation_sku_config(
    'seedance2_fast', '15'::jsonb, 'true'::jsonb, '9:16',
    'RUNWAY_SEEDANCE2_FAST_15S_AUDIO_USD_4.35'
  ) -> 'estimated_credits',
  '435'::jsonb,
  'Seedance fifteen-second price is bound to 435 credits'
);

select is(
  content_factory_private.real_generation_sku_config(
    'gen4_turbo', '11'::jsonb, 'false'::jsonb, '9:16',
    'RUNWAY_GEN4_TURBO_11S_USD_0.55'
  ),
  null::jsonb,
  'Gen-4 durations above ten seconds fail closed'
);

select is(
  content_factory_private.real_generation_sku_config(
    'seedance2_fast', '16'::jsonb, 'true'::jsonb, '9:16',
    'RUNWAY_SEEDANCE2_FAST_16S_AUDIO_USD_4.64'
  ),
  null::jsonb,
  'Seedance durations above fifteen seconds fail closed'
);

select is(
  content_factory_private.real_generation_sku_config(
    'seedance2_fast', '15'::jsonb, 'true'::jsonb, '9:16',
    'RUNWAY_SEEDANCE2_FAST_15S_AUDIO_USD_2.32'
  ),
  null::jsonb,
  'a stale eight-second confirmation cannot authorize fifteen seconds'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'
  ) is not null,
  'the previous complete paid-start chain remains private behind v12'
);

select matches(
  pg_get_functiondef(
    'public.creator_start_real_generation_single_reference_v13(jsonb)'::regprocedure
  ),
  'real_generation_sku_binding_invalid',
  'the retained single-reference boundary binds the returned job to dynamic price'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'content_factory'
      and table_name = 'generation_provider_readiness_receipts'
      and column_name = 'duration_seconds'
      and is_nullable = 'NO'
  ),
  'provider readiness receipts are duration-specific'
);

select ok(
  pg_get_functiondef(
    'public.system_record_generation_provider_readiness(jsonb)'::regprocedure
  ) like '%real_generation_multimodel_sku%'
  and pg_get_functiondef(
    'public.system_record_generation_provider_readiness(jsonb)'::regprocedure
  ) like '%to_jsonb(estimated_credits_value)%'
  and pg_get_functiondef(
    'public.system_record_generation_provider_readiness(jsonb)'::regprocedure
  ) like '%sku_value -> ''estimated_credits''%'
  and pg_get_functiondef(
    'content_factory_private.real_generation_multimodel_sku(text,text,text,integer,text,text,boolean,boolean)'
      ::regprocedure
  ) like '%p_duration * 29%',
  'trusted readiness binds supplied Seedance credits to the canonical SKU price'
);

select matches(
  pg_get_functiondef(
    'content_factory_private.creator_start_gen4_turbo_5s(jsonb)'::regprocedure
  ),
  'estimated_cost_minor_value',
  'Gen-4 paid-start runtime persists the dynamic SKU price'
);

select matches(
  pg_get_functiondef(
    'content_factory_private.creator_start_seedance2_fast_8s(jsonb)'::regprocedure
  ),
  'estimated_credits_value',
  'Seedance paid-start runtime persists the dynamic SKU credits'
);

select matches(
  pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_campaign_v1(jsonb)'::regprocedure
  ),
  'sku_config -> ''estimated_credits''',
  'campaign response reports dynamic credits instead of the historical default'
);

select ok(
  position(
    'creator_start_real_generation_pre_flexible_duration_v12'
    in pg_get_functiondef(
      'public.creator_start_real_generation_single_reference_v13(jsonb)'::regprocedure
    )
  ) < position(
    'sku_config := content_factory_private.real_generation_sku_config'
    in pg_get_functiondef(
      'public.creator_start_real_generation_single_reference_v13(jsonb)'::regprocedure
    )
  ),
  'legacy authorization and policy errors run before the final SKU binding'
);

select * from finish();
rollback;

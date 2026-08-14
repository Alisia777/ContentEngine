begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select ok(
  to_regprocedure(
    'public.creator_start_real_generation(jsonb)'
  ) is not null
  and to_regprocedure(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'
  ) is not null
  and to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_multimodel_v48(jsonb)'
  ) is not null,
  'new4 has an exact public seam while the complete historical starter is preserved'
);

select ok(
  has_function_privilege(
    'authenticated','public.creator_start_real_generation(jsonb)','execute'
  )
  and not has_function_privilege(
    'anon','public.creator_start_real_generation(jsonb)','execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.bind_generation_v4_launch(uuid,uuid,uuid,uuid,uuid,jsonb)',
    'execute'
  ),
  'the browser cannot bypass either the public start boundary or v4 binder'
);

select ok(
  to_regclass(
    'content_factory.generation_job_selection_snapshots'
  ) is not null
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_job_selection_snapshots',
    'insert'
  ),
  'the immutable launch snapshot is server-only'
);

select is(
  content_factory_private.generation_catalog_version(),
  '2026-08-13.v1',
  'one canonical catalog version owns the SQL contract'
);

select is(
  content_factory_private.real_generation_multimodel_sku(
    'runway','gen4.5','image',10,'21:9','720p',false,false
  ) ->> 'estimated_credits',
  '120',
  'Gen-4.5 charges exactly twelve Runway credits per second'
);

select is(
  content_factory_private.real_generation_multimodel_sku(
    'runway','seedance2_mini','image',4,'4:3','480p',true,false
  ) ->> 'estimated_credits',
  '64',
  'Seedance Mini preserves the exact minimum 64-credit floor'
);

select is(
  content_factory_private.real_generation_multimodel_sku(
    'runway','veo3.1_fast','image',8,'16:9','1080p',true,true
  ) ->> 'estimated_credits',
  '120',
  'Runway Veo Fast derives its audio cost on the server'
);

select is(
  content_factory_private.real_generation_multimodel_sku(
    'runway','gemini_omni_flash','image',10,'9:16','720p',true,false
  ) ->> 'estimated_credits',
  '101',
  'Gemini Omni Flash includes the one-credit image charge'
);

select is(
  content_factory_private.real_generation_multimodel_sku(
    'runway','gen4.5','image',10,'21:9','720p',false,false
  ) ->> 'provider_ratio',
  '1584:672',
  'public 21:9 remains separate from the adapter-only provider ratio'
);

select ok(
  content_factory_private.real_generation_multimodel_sku(
    'runway','seedream5_lite','image',0,'1:1','2K',false,false
  ) is not null
  and content_factory_private.real_generation_multimodel_sku(
    'runway','seedream5_lite','image',0,'1:1','3K',false,false
  ) is null,
  'Seedream retains its explicit legacy 1:1/2K launch subset'
);

select ok(
  not content_factory_private.generation_google_lro_sql_ready(),
  'direct Google remains fail-closed until SQL owns the complete LRO chain'
);

insert into content_factory.organizations (id,name,slug,status)
values (
  '00000000-0000-4000-8000-000000000048'::uuid,
  'Multimodel policy fixture','multimodel-policy-fixture','active'
);

select ok(
  content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000048','runway','gen4.5'
  )
  and content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000048','runway','seedance2_mini'
  )
  and content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000048','runway','veo3.1_fast'
  )
  and content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000048','runway','gemini_omni_flash'
  ),
  'new4 is launchable through the exact v4 receipt and live-claim path'
);

select ok(
  content_factory_private.generation_catalog_entry(
    'runway','gen4.5'
  ) -> 'enabled_by_default'='true'::jsonb
  and not content_factory_private.generation_catalog_entry(
    'runway','gen4.5'
  ) ? 'disabled_reason',
  'catalog projects new4 as executable while retaining experimental lifecycle'
);

select ok(
  pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_multimodel_v48%'
  and pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_multimodel_v48%',
  'the public function reaches only the exact new4 seam and delegates every other request unchanged'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'::regprocedure
  ) like '%bind_generation_v4_launch%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'::regprocedure
  ) like '%require_generation_spec_project_v49%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'::regprocedure
  ) like '%generation_selection_snapshot%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'::regprocedure
  ) not like '%http%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'::regprocedure
  ) not like '%provider_task_id%',
  'the authoritative SQL seam contains no provider transport'
);

select ok(
  pg_get_constraintdef((
    select constraint_row.oid
    from pg_constraint constraint_row
    where constraint_row.conrelid=
      'content_factory.generation_quality_guard_lineage'::regclass
      and constraint_row.conname=
        'generation_quality_guard_lineage_model_v48_check'
  )) like '%gen4.5%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_multimodel_v48(jsonb)'::regprocedure
  ) like '%insert into content_factory.generation_quality_guard_lineage%'
  and pg_get_functiondef(
    'content_factory_private.generation_multimodel_live_claim_v2(uuid,uuid,uuid,uuid,uuid,integer,text)'::regprocedure
  ) like '%quality_lineage_hash%',
  'new4 reuses the mature append-only QA lineage and live provider claim'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.generation_multimodel_live_claim_v2(uuid,uuid,uuid,uuid,uuid,integer,text)'::regprocedure
  ) like '%content_review_product_category_unverified%'
  and pg_get_functiondef(
    'content_factory_private.generation_multimodel_live_claim_v2(uuid,uuid,uuid,uuid,uuid,integer,text)'::regprocedure
  ) like '%generation_spec_provider_start_stale%',
  'operator category drift enters the mature terminal stale-claim path'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.bind_generated_video_spoken_script()'::regprocedure
  ) like '%generation_runway_video_review_model_allowed%'
  and pg_get_functiondef(
    'content_factory_private.bind_generated_video_spoken_script()'::regprocedure
  ) like '%generated_video_spoken_script%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'::regprocedure
  ) like '%generation_runway_video_review_model_allowed%',
  'new4 video and spoken-audio outputs reuse the existing review owners'
);

select ok(
  pg_get_functiondef(
    'public.creator_real_generation_status(jsonb)'::regprocedure
  ) like '%{job,resolution}%'
  and pg_get_functiondef(
    'public.creator_real_generation_status(jsonb)'::regprocedure
  ) like '%{job,last_frame}%'
  and pg_get_functiondef(
    'public.creator_real_generation_status(jsonb)'::regprocedure
  ) like '%generation_review_autostart_consents%',
  'read-after-start returns exact new4 technical and consent state'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.bind_generation_v4_launch(uuid,uuid,uuid,uuid,uuid,jsonb)'::regprocedure
  ) like '%generation-provider-readiness-receipt-v4%'
  and pg_get_functiondef(
    'content_factory_private.bind_generation_v4_launch(uuid,uuid,uuid,uuid,uuid,jsonb)'::regprocedure
  ) like '%spend_confirmation%'
  and pg_get_functiondef(
    'content_factory_private.bind_generation_v4_launch(uuid,uuid,uuid,uuid,uuid,jsonb)'::regprocedure
  ) like '%generation_selection_snapshot_valid%'
  and pg_get_functiondef(
    'content_factory_private.bind_generation_v4_launch(uuid,uuid,uuid,uuid,uuid,jsonb)'::regprocedure
  ) like '%checked_by is distinct from p_actor_id%',
  'v4 receipt, human token, canonical snapshot and actor are one exact gate'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.system_update_real_generation_v1(jsonb)'::regprocedure
  ) like '%real_generation_sku_from_input(%'
  and pg_get_functiondef(
    'content_factory_private.system_update_real_generation_v1(jsonb)'::regprocedure
  ) like '%job_row.provider%'
  and pg_get_functiondef(
    'content_factory_private.system_update_real_generation_v1(jsonb)'::regprocedure
  ) like '%job_row.input%'
  and pg_get_functiondef(
    'content_factory_private.system_update_real_generation_v1(jsonb)'::regprocedure
  ) not like '%real_generation_sku_config(%',
  'the one mature worker state machine validates the exact persisted new4 SKU'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  ) like '%generation_runway_video_review_model_allowed(%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'::regprocedure
  ) like '%generation_runway_video_review_model_allowed(%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'::regprocedure
  ) like '%real_generation_sku_from_input(%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'::regprocedure
  ) like '%generation_job_row.provider, generation_job_row.input%',
  'new4 reuses the mature review and sound provenance owners with exact persisted audio'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '48100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated','authenticated','multimodel-v3-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),'{}'::jsonb,'{"display_name":"Multimodel v3 owner"}'::jsonb,
  now(),now()
);

insert into content_factory.organizations (id,name,slug,status)
values (
  '48200000-0000-4000-8000-000000000001'::uuid,
  'Multimodel readiness compatibility','multimodel-readiness-compat','active'
);

update content_factory.profiles
set status='active'
where id='48100000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id,profile_id,role,status
) values (
  '48200000-0000-4000-8000-000000000001'::uuid,
  '48100000-0000-4000-8000-000000000001'::uuid,
  'owner','active'
);

select is(
  public.system_record_generation_provider_readiness(jsonb_build_object(
    'organization_id','48200000-0000-4000-8000-000000000001',
    'checked_by','48100000-0000-4000-8000-000000000001',
    'provider','runway','model','seedream5_lite','input_mode','image',
    'duration_seconds',0,'format','1:1','resolution','2K',
    'audio',false,'last_frame',false,'ready',true,
    'estimated_cost_minor',4,'estimated_credits',4,
    'credential_configured',true,'balance_sufficient',true,
    'model_available',true,'daily_quota_available',true,
    'failure_code',null,'catalog_version','2026-08-13.v1',
    'pricing_version','runway-credits-2026-08-13.v1',
    'learning_gate_version','2026-07-29.v8',
    'spend_confirmation','RUNWAY_SEEDREAM5_LITE_2K_USD_0.04',
    'automatic_generation',false,'automatic_spend',false
  )) ->> 'version',
  'generation-provider-readiness-receipt-v3',
  'the one recorder still accepts an exact legacy old3 payload without v4 scope'
);

select throws_ok(
  $$
    select public.system_record_generation_provider_readiness(
      jsonb_build_object(
        'organization_id','48200000-0000-4000-8000-000000000001',
        'checked_by','48100000-0000-4000-8000-000000000001',
        'provider','runway','model','gen4.5','input_mode','image',
        'duration_seconds',2,'format','9:16','resolution','720p',
        'audio',false,'last_frame',false,'ready',true,
        'estimated_cost_minor',24,'estimated_credits',24,
        'credential_configured',true,'balance_sufficient',true,
        'model_available',true,'daily_quota_available',true,
        'failure_code',null,'catalog_version','2026-08-13.v1',
        'pricing_version','runway-credits-2026-08-13.v1',
        'learning_gate_version','2026-07-29.v8',
        'spend_confirmation','RUNWAY_GEN4_5_2S_720P_SILENT_USD_0.24',
        'automatic_generation',false,'automatic_spend',false
      )
    )
  $$,
  '22023',
  'generation_provider_readiness_receipt_invalid',
  'new4 cannot downgrade to an unscoped v3 receipt'
);

select * from finish();
rollback;

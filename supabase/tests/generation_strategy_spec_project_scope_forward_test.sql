begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select ok(
  regexp_count(
    pg_catalog.pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    ),
    '''organization_id''[[:space:]]*,[[:space:]]*organization_id_value' ||
    '[[:space:]]*,[[:space:]]*''project_id''[[:space:]]*,' ||
    '[[:space:]]*project_id_value[[:space:]]*,' ||
    '[[:space:]]*''idempotency_key'''
  ) = 1,
  'strategy wrapper forwards its validated project exactly once'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_prepare_generation_strategy_spec(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_prepare_generation_strategy_spec(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_prepare_generation_strategy_spec(jsonb)', 'execute'
  ),
  'strategy wrapper remains authenticated-human only'
);
select is(
  pg_catalog.obj_description(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure,
    'pg_proc'
  ),
  -- Комментарий переписан миграцией 202608210001, когда объём стал
  -- провайдер-независимым (scope v2): браузер больше не называет провайдера и
  -- модель, они откладываются до подписанного предполёта. Утверждение, ради
  -- которого этот тест существует, при этом уцелело дословно — «no
  -- provider/spend action occurs», — и именно оно тут и стережётся.
  'Free authenticated prepare: emits provider-neutral recipe scope v2. Provider/model are not accepted from the browser and are deferred to the signed route preflight; no provider/spend action occurs.',
  'strategy wrapper keeps the audited no-spend comment'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'cc100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'strategy-project-scope-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Strategy Project Scope Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    'cc110000-0000-4000-8000-000000000001'::uuid,
    'Strategy Project Scope pgTAP',
    'strategy-project-scope-pgtap', 'active'
  ),
  (
    'cc210000-0000-4000-8000-000000000001'::uuid,
    'Foreign Strategy Project Scope pgTAP',
    'foreign-strategy-project-scope-pgtap', 'active'
  );

update content_factory.profiles profile
set status = 'active'
where profile.id = 'cc100000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'cc110000-0000-4000-8000-000000000001'::uuid,
    'cc100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'active'
  ),
  (
    'cc210000-0000-4000-8000-000000000001'::uuid,
    'cc100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'active'
  );

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'cc110000-0000-4000-8000-000000000001'::uuid,
  'cc100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'owner',
  'TEST-ONLY waiver for strategy project-scope pgTAP.',
  'cc100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values
  (
    'cc120000-0000-4000-8000-000000000001'::uuid,
    'cc110000-0000-4000-8000-000000000001'::uuid,
    null, 'Strategy project scope', 'gold', 'project',
    'active', 1024,
    'cc100000-0000-4000-8000-000000000001'::uuid,
    'cc100000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'cc220000-0000-4000-8000-000000000001'::uuid,
    'cc210000-0000-4000-8000-000000000001'::uuid,
    null, 'Foreign strategy project scope', 'blue', 'project',
    'active', 1024,
    'cc100000-0000-4000-8000-000000000001'::uuid,
    'cc100000-0000-4000-8000-000000000001'::uuid
  );

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'cc130000-0000-4000-8000-000000000001'::uuid,
  'cc110000-0000-4000-8000-000000000001'::uuid,
  'STRATEGY-PROJECT-SCOPE-001',
  'Strategy Project Scope Product', 'active',
  'cc100000-0000-4000-8000-000000000001'::uuid
);

select set_config(
  'request.jwt.claim.sub',
  'cc100000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

create temporary table strategy_project_scope_assets (
  asset_key text primary key,
  filename text not null,
  mime_type text not null,
  size_bytes bigint not null,
  sha256 text not null,
  kind text not null,
  product_id uuid,
  media_id uuid
) on commit drop;

insert into strategy_project_scope_assets (
  asset_key, filename, mime_type, size_bytes, sha256, kind, product_id
) values
  (
    'source', 'strategy-source.mp4', 'video/mp4', 4096,
    repeat('1', 64), 'source_video', null
  ),
  (
    'original', 'strategy-original.webp', 'image/webp', 1024,
    repeat('2', 64), 'creator_reference', null
  ),
  (
    'new-front', 'strategy-new-front.png', 'image/png', 1024,
    repeat('3', 64), 'product_photo',
    'cc130000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'new-side', 'strategy-new-side.png', 'image/png', 1024,
    repeat('4', 64), 'product_photo',
    'cc130000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'new-back', 'strategy-new-back.png', 'image/png', 1024,
    repeat('5', 64), 'product_photo',
    'cc130000-0000-4000-8000-000000000001'::uuid
  );

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  'cc110000-0000-4000-8000-000000000001/' ||
    'cc100000-0000-4000-8000-000000000001/uploads/' || asset.filename,
  jsonb_build_object(
    'size', asset.size_bytes, 'mimetype', asset.mime_type
  )
from strategy_project_scope_assets asset;

do $register_strategy_project_scope_assets$
declare
  asset record;
  response_value jsonb;
begin
  for asset in
    select * from strategy_project_scope_assets order by asset_key
  loop
    response_value := public.creator_register_media(
      jsonb_strip_nulls(jsonb_build_object(
        'organization_id', 'cc110000-0000-4000-8000-000000000001',
        'project_id', 'cc120000-0000-4000-8000-000000000001',
        'product_id', to_jsonb(asset.product_id),
        'bucket', 'contentengine-private',
        'object_key',
          'cc110000-0000-4000-8000-000000000001/' ||
          'cc100000-0000-4000-8000-000000000001/uploads/' ||
          asset.filename,
        'original_filename', asset.filename,
        'mime_type', asset.mime_type,
        'size_bytes', asset.size_bytes,
        'sha256', asset.sha256,
        'kind', asset.kind,
        'rights_confirmed', true,
        'idempotency_key',
          'strategy-project-scope-register-' || asset.asset_key
      ))
    );
    update strategy_project_scope_assets
    set media_id = (response_value #>> '{media,id}')::uuid
    where asset_key = asset.asset_key;
  end loop;
end;
$register_strategy_project_scope_assets$;

create temporary table strategy_project_scope_context (
  source_attachment_id uuid,
  source_attachment_hash text,
  selection jsonb,
  request_payload jsonb
) on commit drop;
insert into strategy_project_scope_context default values;

do $attach_and_probe_strategy_project_scope_source$
declare
  response_value jsonb;
begin
  response_value := public.contentengine_attach_generation_direct_mp4(
    jsonb_build_object(
      'organization_id', 'cc110000-0000-4000-8000-000000000001',
      'project_id', 'cc120000-0000-4000-8000-000000000001',
      'media_id', (
        select media_id from strategy_project_scope_assets
        where asset_key = 'source'
      ),
      'idempotency_key', 'strategy-project-scope-attachment-0001'
    )
  );
  update strategy_project_scope_context set
    source_attachment_id =
      (response_value #>> '{attachment,id}')::uuid,
    source_attachment_hash =
      response_value #>> '{attachment,attachment_hash}';

  perform public.system_record_generation_strategy_media_duration(
    jsonb_build_object(
      'version', 'generation-strategy-media-duration-record-request-v1',
      'organization_id', 'cc110000-0000-4000-8000-000000000001',
      'project_id', 'cc120000-0000-4000-8000-000000000001',
      'actor_id', 'cc100000-0000-4000-8000-000000000001',
      'media_id', (
        select media_id from strategy_project_scope_assets
        where asset_key = 'source'
      ),
      'attachment_id', (
        select source_attachment_id from strategy_project_scope_context
      ),
      'attachment_hash', (
        select source_attachment_hash from strategy_project_scope_context
      ),
      'media_sha256', repeat('1', 64),
      'size_bytes', 4096,
      'http_status', 200,
      'content_type', 'video/mp4',
      'download_complete', true,
      'parser_version', 'iso-bmff-mvhd-v1',
      'timescale', 1000,
      'duration_units', 8000,
      'duration_ms', 8000,
      'mvhd_count', 1,
      'fragmented', false,
      'verification_method', 'server_mp4_probe',
      'evidence_hash', repeat('9', 64),
      'idempotency_key', 'strategy-project-scope-probe-0001'
    )
  );
end;
$attach_and_probe_strategy_project_scope_source$;

do $build_strategy_project_scope_browser_request$
declare
  selection_value jsonb;
  payload_value jsonb;
begin
  select jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_product_swap',
    'recipe_version', '2026-06',
    'duration_seconds', 4,
    'resolution', '720p',
    'audio', true,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video',
        'media_id', source.media_id,
        'duration_seconds', 8.000
      ),
      jsonb_build_object(
        'role', 'original_product_image',
        'media_id', original_image.media_id
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', front_image.media_id,
        'view', 'front'
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', side_image.media_id,
        'view', 'side'
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', back_image.media_id,
        'view', 'back'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true
    )
  ) into selection_value
  from strategy_project_scope_assets source
  cross join strategy_project_scope_assets original_image
  cross join strategy_project_scope_assets front_image
  cross join strategy_project_scope_assets side_image
  cross join strategy_project_scope_assets back_image
  where source.asset_key = 'source'
    and original_image.asset_key = 'original'
    and front_image.asset_key = 'new-front'
    and side_image.asset_key = 'new-side'
    and back_image.asset_key = 'new-back';

  payload_value := jsonb_build_object(
    'version', 'generation-strategy-spec-prepare-request-v1',
    'organization_id', 'cc110000-0000-4000-8000-000000000001',
    'project_id', 'cc120000-0000-4000-8000-000000000001',
    'platform', 'tiktok',
    'product_category', 'other',
    'selection', selection_value,
    'editable_intent',
      'Replace only the source product and preserve motion and lighting.',
    'proposed_prompt',
      'Replace the original product with the supplied product references.',
    'mechanics_summary', 'null'::jsonb,
    'confirmation', true,
    'reason', 'Prepare the project-scoped browser Product Swap draft.',
    'idempotency_key', 'strategy-project-scope-prepare-0001'
  );
  update strategy_project_scope_context set
    selection = selection_value,
    request_payload = payload_value;
  perform set_config(
    'pgtap.strategy_project_scope_request', payload_value::text, true
  );
end;
$build_strategy_project_scope_browser_request$;

set local role authenticated;

select ok(
  (
    set_config(
      'pgtap.strategy_project_scope_response',
      public.creator_prepare_generation_strategy_spec(
        current_setting('pgtap.strategy_project_scope_request')::jsonb
      )::text,
      true
    )::jsonb
  ) -> 'ok' = 'true'::jsonb,
  'authenticated browser wrapper prepares a project-scoped draft'
);
select is(
  current_setting('pgtap.strategy_project_scope_response')::jsonb ->>
    'version',
  'generation-strategy-spec-prepare-response-v1',
  'browser wrapper preserves the exact response version'
);
select is(
  current_setting('pgtap.strategy_project_scope_response')::jsonb #>>
    '{generation_spec,exact_scope,strategy_id}',
  'viral_product_swap',
  'prepared draft contains the exact Product Swap strategy scope'
);
select is(
  current_setting('pgtap.strategy_project_scope_response')::jsonb #>
    '{generation_spec,exact_scope,selection}',
  current_setting('pgtap.strategy_project_scope_request')::jsonb ->
    'selection',
  'prepared exact scope preserves the complete browser selection snapshot'
);

with replay as materialized (
  select public.creator_prepare_generation_strategy_spec(
    current_setting('pgtap.strategy_project_scope_request')::jsonb
  ) as response
)
select is(
  response,
  current_setting('pgtap.strategy_project_scope_response')::jsonb,
  'same project-scoped idempotency key replays an unchanged response'
)
from replay;

select throws_ok(
  $$
    select public.creator_prepare_generation_strategy_spec(
      current_setting('pgtap.strategy_project_scope_request')::jsonb
        - 'project_id'
    )
  $$,
  '22023',
  'generation_strategy_spec_prepare_payload_invalid',
  'browser wrapper rejects a missing project'
);
select throws_ok(
  $$
    select public.creator_prepare_generation_strategy_spec(
      current_setting('pgtap.strategy_project_scope_request')::jsonb
        || jsonb_build_object(
          'project_id', 'ccff0000-0000-4000-8000-000000000001'
        )
    )
  $$,
  'P0002',
  'workspace_project_not_found',
  'browser wrapper rejects an unknown project'
);
select throws_ok(
  $$
    select public.creator_prepare_generation_strategy_spec(
      current_setting('pgtap.strategy_project_scope_request')::jsonb
        || jsonb_build_object(
          'project_id', 'cc220000-0000-4000-8000-000000000001'
        )
    )
  $$,
  'P0002',
  'workspace_project_not_found',
  'browser wrapper rejects a project from another tenant'
);

reset role;

select is(
  (
    select count(*)::integer
    from content_factory.generation_spec_versions version
    where version.organization_id =
        'cc110000-0000-4000-8000-000000000001'::uuid
      and version.spec_id = (
        current_setting('pgtap.strategy_project_scope_response')::jsonb #>>
          '{generation_spec,spec_id}'
      )::uuid
      and version.exact_scope = (
        current_setting('pgtap.strategy_project_scope_response')::jsonb #>
          '{generation_spec,exact_scope}'
      )
  ),
  1,
  'success and replay create one immutable exact-scope spec version'
);
select is(
  (
    select
      (select count(*)
       from content_factory.generation_strategy_start_claims claim
       where claim.organization_id =
         'cc110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_strategy_dispatch_attempts attempt
       where attempt.organization_id =
         'cc110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_strategy_dispatch_results result
       where result.organization_id =
         'cc110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id =
         'cc110000-0000-4000-8000-000000000001'::uuid)
  )::integer,
  0,
  'free prepare and replay create no paid claim, dispatch or spend row'
);

select * from finish();
rollback;

begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(25);

select has_table(
  'content_factory', 'generation_direct_mp4_attachments',
  'direct MP4 attachments have a dedicated ledger'
);
select has_function(
  'public', 'contentengine_attach_generation_direct_mp4', array['jsonb'],
  'direct MP4 attachment RPC is installed'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.contentengine_attach_generation_direct_mp4(jsonb)', 'execute'
  ),
  'authenticated actors can attach registered direct MP4 media'
);
select ok(
  not has_function_privilege(
    'anon',
    'public.contentengine_attach_generation_direct_mp4(jsonb)', 'execute'
  ),
  'anonymous actors cannot attach direct MP4 media'
);
select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.generation_direct_mp4_attachments', 'select'
  ),
  'the direct attachment ledger is not browser-readable'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'da100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'direct-mp4-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Direct MP4 Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'da110000-0000-4000-8000-000000000001'::uuid,
  'Direct MP4 pgTAP', 'direct-mp4-pgtap', 'active'
);

update content_factory.profiles profile
set status = 'active'
where profile.id = 'da100000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'da110000-0000-4000-8000-000000000001'::uuid,
  'da100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'da110000-0000-4000-8000-000000000001'::uuid,
  'da100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'owner',
  'TEST-ONLY waiver for the direct MP4 attachment contract.',
  'da100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values
  (
    'da120000-0000-4000-8000-000000000001'::uuid,
    'da110000-0000-4000-8000-000000000001'::uuid,
    null, 'Direct MP4 project', 'gold', 'project',
    'active', 1024,
    'da100000-0000-4000-8000-000000000001'::uuid,
    'da100000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'da120000-0000-4000-8000-000000000002'::uuid,
    'da110000-0000-4000-8000-000000000001'::uuid,
    null, 'Wrong direct MP4 project', 'slate', 'project',
    'active', 2048,
    'da100000-0000-4000-8000-000000000001'::uuid,
    'da100000-0000-4000-8000-000000000001'::uuid
  );

select set_config(
  'request.jwt.claim.sub',
  'da100000-0000-4000-8000-000000000001',
  true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

create temporary table direct_mp4_test_context (
  good_media_id uuid,
  image_media_id uuid,
  generated_media_id uuid,
  no_rights_media_id uuid,
  missing_storage_media_id uuid,
  attachment_id uuid,
  attachment_hash text
) on commit drop;
insert into direct_mp4_test_context default values;

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  'da110000-0000-4000-8000-000000000001/' ||
    'da100000-0000-4000-8000-000000000001/uploads/' || fixture.filename,
  jsonb_build_object('size', fixture.size_bytes, 'mimetype', fixture.mime_type)
from (values
  ('good.mp4', 2048, 'video/mp4'),
  ('image.webp', 1024, 'image/webp'),
  ('generated.mp4', 3072, 'video/mp4'),
  ('no-rights.mp4', 4096, 'video/mp4')
) fixture(filename, size_bytes, mime_type);

do $register_direct_mp4_fixtures$
declare
  response_value jsonb;
begin
  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'da110000-0000-4000-8000-000000000001',
    'project_id', 'da120000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'da110000-0000-4000-8000-000000000001/' ||
      'da100000-0000-4000-8000-000000000001/uploads/good.mp4',
    'original_filename', 'good.mp4', 'mime_type', 'video/mp4',
    'size_bytes', 2048, 'sha256', repeat('a', 64),
    'kind', 'source_video', 'rights_confirmed', true,
    'idempotency_key', 'direct-mp4-register-good-0001'
  ));
  update direct_mp4_test_context
  set good_media_id = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'da110000-0000-4000-8000-000000000001',
    'project_id', 'da120000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'da110000-0000-4000-8000-000000000001/' ||
      'da100000-0000-4000-8000-000000000001/uploads/image.webp',
    'original_filename', 'image.webp', 'mime_type', 'image/webp',
    'size_bytes', 1024, 'sha256', repeat('b', 64),
    'kind', 'creator_reference', 'rights_confirmed', true,
    'idempotency_key', 'direct-mp4-register-image-0001'
  ));
  update direct_mp4_test_context
  set image_media_id = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'da110000-0000-4000-8000-000000000001',
    'project_id', 'da120000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'da110000-0000-4000-8000-000000000001/' ||
      'da100000-0000-4000-8000-000000000001/uploads/generated.mp4',
    'original_filename', 'generated.mp4', 'mime_type', 'video/mp4',
    'size_bytes', 3072, 'sha256', repeat('c', 64),
    'kind', 'source_video', 'rights_confirmed', true,
    'idempotency_key', 'direct-mp4-register-generated-0001'
  ));
  update direct_mp4_test_context
  set generated_media_id = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'da110000-0000-4000-8000-000000000001',
    'project_id', 'da120000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'da110000-0000-4000-8000-000000000001/' ||
      'da100000-0000-4000-8000-000000000001/uploads/no-rights.mp4',
    'original_filename', 'no-rights.mp4', 'mime_type', 'video/mp4',
    'size_bytes', 4096, 'sha256', repeat('d', 64),
    'kind', 'source_video', 'rights_confirmed', true,
    'idempotency_key', 'direct-mp4-register-no-rights-0001'
  ));
  update direct_mp4_test_context
  set no_rights_media_id = (response_value #>> '{media,id}')::uuid;

end;
$register_direct_mp4_fixtures$;

-- Build the negative fixture directly: creator_register_media deliberately
-- requires a real Storage row, while this test must prove that attachment does
-- not trust an otherwise-valid media registry row whose object is absent.
insert into content_factory.media_objects (
  id, organization_id, owner_id, project_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, artifact_class, lifecycle_stage, metadata, idempotency_key
) values (
  'da140000-0000-4000-8000-000000000005'::uuid,
  'da110000-0000-4000-8000-000000000001'::uuid,
  'da100000-0000-4000-8000-000000000001'::uuid,
  'da120000-0000-4000-8000-000000000001'::uuid,
  'contentengine-private',
  'da110000-0000-4000-8000-000000000001/' ||
    'da100000-0000-4000-8000-000000000001/uploads/missing-storage.mp4',
  'video/mp4', 5120, repeat('e', 64), 'ready', 'source', 'sources',
  '{"kind":"source_video","rights_confirmed":true}'::jsonb,
  'direct-mp4-register-missing-storage-0001'
);
update direct_mp4_test_context
set missing_storage_media_id = 'da140000-0000-4000-8000-000000000005'::uuid;

update content_factory.media_objects media
set artifact_class = 'generated_output', lifecycle_stage = 'drafts'
where media.id = (
  select generated_media_id from direct_mp4_test_context
);
update content_factory.media_objects media
set metadata = jsonb_set(media.metadata, '{rights_confirmed}', 'false'::jsonb)
where media.id = (
  select no_rights_media_id from direct_mp4_test_context
);
do $attach_good_direct_mp4$
declare
  response_value jsonb;
begin
  response_value := public.contentengine_attach_generation_direct_mp4(
    jsonb_build_object(
      'organization_id', 'da110000-0000-4000-8000-000000000001',
      'project_id', 'da120000-0000-4000-8000-000000000001',
      'media_id', (select good_media_id from direct_mp4_test_context),
      'idempotency_key', 'generation-direct-mp4-good-0001'
    )
  );
  update direct_mp4_test_context set
    attachment_id = (response_value #>> '{attachment,id}')::uuid,
    attachment_hash = response_value #>> '{attachment,attachment_hash}';
end;
$attach_good_direct_mp4$;

select is(
  public.contentengine_attach_generation_direct_mp4(jsonb_build_object(
    'organization_id', 'da110000-0000-4000-8000-000000000001',
    'project_id', 'da120000-0000-4000-8000-000000000001',
    'media_id', (select good_media_id from direct_mp4_test_context),
    'idempotency_key', 'generation-direct-mp4-good-0001'
  )) ->> 'version',
  'generation-direct-mp4-attachment-v1',
  'happy path returns the versioned direct attachment contract'
);
select is(
  public.contentengine_attach_generation_direct_mp4(jsonb_build_object(
    'organization_id', 'da110000-0000-4000-8000-000000000001',
    'project_id', 'da120000-0000-4000-8000-000000000001',
    'media_id', (select good_media_id from direct_mp4_test_context),
    'idempotency_key', 'generation-direct-mp4-good-0001'
  )) #>> '{attachment,source_kind}',
  'direct_mp4',
  'happy path records direct provenance instead of a social source'
);
select is(
  (
    public.contentengine_attach_generation_direct_mp4(jsonb_build_object(
      'organization_id', 'da110000-0000-4000-8000-000000000001',
      'project_id', 'da120000-0000-4000-8000-000000000001',
      'media_id', (select good_media_id from direct_mp4_test_context),
      'idempotency_key', 'generation-direct-mp4-good-0001'
    )) #>> '{attachment,id}'
  )::uuid,
  (select attachment_id from direct_mp4_test_context),
  'same command replay returns the same immutable attachment'
);
select is(
  (
    select count(*)::integer
    from content_factory.generation_direct_mp4_attachments attachment
    where attachment.organization_id =
      'da110000-0000-4000-8000-000000000001'::uuid
  ),
  1,
  'idempotent replay creates one physical direct row'
);
select is(
  (
    select count(*)::integer
    from only content_factory.research_exact_youtube_media_attachments exact
    where exact.organization_id =
      'da110000-0000-4000-8000-000000000001'::uuid
  ),
  0,
  'direct attachment creates no physical exact-YouTube row'
);

select throws_ok(
  $$
    select public.contentengine_attach_generation_direct_mp4(
      jsonb_build_object(
        'organization_id', 'da110000-0000-4000-8000-000000000001',
        'project_id', 'da120000-0000-4000-8000-000000000002',
        'media_id', (select good_media_id from direct_mp4_test_context),
        'idempotency_key', 'generation-direct-mp4-wrong-project-0001'
      )
    )
  $$,
  '22023', 'generation_direct_mp4_attachment_media_invalid',
  'wrong project scope is denied'
);
select throws_ok(
  $$
    select public.contentengine_attach_generation_direct_mp4(
      jsonb_build_object(
        'organization_id', 'da110000-0000-4000-8000-000000000001',
        'project_id', 'da120000-0000-4000-8000-000000000001',
        'media_id', (select image_media_id from direct_mp4_test_context),
        'idempotency_key', 'generation-direct-mp4-image-0001'
      )
    )
  $$,
  '22023', 'generation_direct_mp4_attachment_media_invalid',
  'non-MP4 media is denied'
);
select throws_ok(
  $$
    select public.contentengine_attach_generation_direct_mp4(
      jsonb_build_object(
        'organization_id', 'da110000-0000-4000-8000-000000000001',
        'project_id', 'da120000-0000-4000-8000-000000000001',
        'media_id', (select generated_media_id from direct_mp4_test_context),
        'idempotency_key', 'generation-direct-mp4-generated-0001'
      )
    )
  $$,
  '22023', 'generation_direct_mp4_attachment_media_invalid',
  'generated output cannot be rebound as a direct source'
);
select throws_ok(
  $$
    select public.contentengine_attach_generation_direct_mp4(
      jsonb_build_object(
        'organization_id', 'da110000-0000-4000-8000-000000000001',
        'project_id', 'da120000-0000-4000-8000-000000000001',
        'media_id', (select no_rights_media_id from direct_mp4_test_context),
        'idempotency_key', 'generation-direct-mp4-no-rights-0001'
      )
    )
  $$,
  '22023', 'generation_direct_mp4_attachment_media_invalid',
  'missing source rights is denied'
);
select throws_ok(
  $$
    select public.contentengine_attach_generation_direct_mp4(
      jsonb_build_object(
        'organization_id', 'da110000-0000-4000-8000-000000000001',
        'project_id', 'da120000-0000-4000-8000-000000000001',
        'media_id', (select missing_storage_media_id from direct_mp4_test_context),
        'idempotency_key', 'generation-direct-mp4-storage-missing-0001'
      )
    )
  $$,
  '22023', 'generation_direct_mp4_attachment_media_invalid',
  'missing private storage object is denied'
);

select is(
  (
    select asset.value ->> 'direct_mp4_attached'
    from jsonb_array_elements(
      public.creator_generation_strategy_asset_candidates(
        jsonb_build_object(
          'version', 'generation-strategy-asset-candidates-request-v1',
          'organization_id', 'da110000-0000-4000-8000-000000000001',
          'project_id', 'da120000-0000-4000-8000-000000000001',
          'kind', 'source_video'
        )
      ) -> 'assets'
    ) asset(value)
    where asset.value ->> 'id' =
      (select good_media_id::text from direct_mp4_test_context)
  ),
  'true',
  'real strategy candidates report the direct MP4 attachment'
);
select is(
  (
    select asset.value ->> 'exact_youtube_attached'
    from jsonb_array_elements(
      public.creator_generation_strategy_asset_candidates(
        jsonb_build_object(
          'version', 'generation-strategy-asset-candidates-request-v1',
          'organization_id', 'da110000-0000-4000-8000-000000000001',
          'project_id', 'da120000-0000-4000-8000-000000000001',
          'kind', 'source_video'
        )
      ) -> 'assets'
    ) asset(value)
    where asset.value ->> 'id' =
      (select good_media_id::text from direct_mp4_test_context)
  ),
  'false',
  'real strategy candidates do not label direct MP4 as YouTube'
);
select is(
  (
    select asset.value #>>
      '{blocking_codes_by_strategy,viral_product_swap,0}'
    from jsonb_array_elements(
      public.creator_generation_strategy_asset_candidates(
        jsonb_build_object(
          'version', 'generation-strategy-asset-candidates-request-v1',
          'organization_id', 'da110000-0000-4000-8000-000000000001',
          'project_id', 'da120000-0000-4000-8000-000000000001',
          'kind', 'source_video'
        )
      ) -> 'assets'
    ) asset(value)
    where asset.value ->> 'id' =
      (select good_media_id::text from direct_mp4_test_context)
  ),
  'server_duration_probe_required',
  'Product Swap remains blocked until the free server byte probe'
);

select ok(
  (
    public.system_record_generation_strategy_media_duration(
      jsonb_build_object(
        'version', 'generation-strategy-media-duration-record-request-v1',
        'organization_id', 'da110000-0000-4000-8000-000000000001',
        'project_id', 'da120000-0000-4000-8000-000000000001',
        'actor_id', 'da100000-0000-4000-8000-000000000001',
        'media_id', (select good_media_id from direct_mp4_test_context),
        'attachment_id', (select attachment_id from direct_mp4_test_context),
        'attachment_hash', (select attachment_hash from direct_mp4_test_context),
        'media_sha256', repeat('a', 64), 'size_bytes', 2048,
        'http_status', 200, 'content_type', 'video/mp4',
        'download_complete', true, 'parser_version', 'iso-bmff-mvhd-v1',
        'timescale', 1000, 'duration_units', 8000, 'duration_ms', 8000,
        'mvhd_count', 1, 'fragmented', false,
        'verification_method', 'server_mp4_probe',
        'evidence_hash', repeat('f', 64),
        'idempotency_key', 'direct-mp4-duration-good-0001'
      )
    ) ->> 'ok'
  )::boolean,
  'existing service-only byte probe records direct MP4 duration'
);
select is(
  (
    select asset.value ->> 'duration_seconds'
    from jsonb_array_elements(
      public.creator_generation_strategy_asset_candidates(
        jsonb_build_object(
          'version', 'generation-strategy-asset-candidates-request-v1',
          'organization_id', 'da110000-0000-4000-8000-000000000001',
          'project_id', 'da120000-0000-4000-8000-000000000001',
          'kind', 'source_video'
        )
      ) -> 'assets'
    ) asset(value)
    where asset.value ->> 'id' =
      (select good_media_id::text from direct_mp4_test_context)
  ),
  '8.000',
  'candidate exposes the server-measured duration'
);
select ok(
  (
    select asset.value -> 'eligible_strategy_roles' @>
      '[{"strategy_id":"viral_product_swap","role":"source_video"}]'::jsonb
    from jsonb_array_elements(
      public.creator_generation_strategy_asset_candidates(
        jsonb_build_object(
          'version', 'generation-strategy-asset-candidates-request-v1',
          'organization_id', 'da110000-0000-4000-8000-000000000001',
          'project_id', 'da120000-0000-4000-8000-000000000001',
          'kind', 'source_video'
        )
      ) -> 'assets'
    ) asset(value)
    where asset.value ->> 'id' =
      (select good_media_id::text from direct_mp4_test_context)
  ),
  'one probed direct MP4 is a real Product Swap source candidate'
);

select is(
  (
    select count(*)::integer
    from content_factory.generation_spend_ledger ledger
    where ledger.organization_id =
      'da110000-0000-4000-8000-000000000001'::uuid
  ),
  0,
  'attachment and probe reserve no generation spend'
);
select is(
  (
    select
      (select count(*)
       from content_factory.generation_strategy_start_claims claim
       where claim.organization_id =
         'da110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_strategy_dispatch_attempts attempt
       where attempt.organization_id =
         'da110000-0000-4000-8000-000000000001'::uuid)
  )::integer,
  0,
  'attachment and probe start no paid job or provider dispatch'
);

select throws_ok(
  $$
    update content_factory.generation_direct_mp4_attachments
    set status = 'attached'
    where id = (select attachment_id from direct_mp4_test_context)
  $$,
  '55000', 'generation_direct_mp4_attachment_append_only',
  'direct attachment cannot be updated'
);
select throws_ok(
  $$
    delete from content_factory.generation_direct_mp4_attachments
    where id = (select attachment_id from direct_mp4_test_context)
  $$,
  '55000', 'generation_direct_mp4_attachment_append_only',
  'direct attachment cannot be deleted'
);

select * from finish();
rollback;

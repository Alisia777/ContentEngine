begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_function(
  'public', 'creator_register_media', array['jsonb'],
  'media registration RPC remains installed'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_register_media(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.creator_register_media(jsonb)', 'execute'
  ),
  'authenticated registration grant remains fail-closed to anonymous callers'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '7a100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'media-kind-mime-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Media Kind MIME Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  '7a110000-0000-4000-8000-000000000001'::uuid,
  'Media Kind MIME pgTAP', 'media-kind-mime-pgtap', 'active'
);

update content_factory.profiles profile
set status = 'active'
where profile.id = '7a100000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  '7a110000-0000-4000-8000-000000000001'::uuid,
  '7a100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  '7a110000-0000-4000-8000-000000000001'::uuid,
  '7a100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'owner',
  'TEST-ONLY waiver for the media kind/MIME registration contract.',
  '7a100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  '7a120000-0000-4000-8000-000000000001'::uuid,
  '7a110000-0000-4000-8000-000000000001'::uuid,
  null, 'Media kind MIME project', 'gold', 'project',
  'active', 1024,
  '7a100000-0000-4000-8000-000000000001'::uuid,
  '7a100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  '7a130000-0000-4000-8000-000000000001'::uuid,
  '7a110000-0000-4000-8000-000000000001'::uuid,
  'MIME-CONTRACT-PRODUCT', 'MIME contract product', 'active',
  '7a100000-0000-4000-8000-000000000001'::uuid
);

select set_config(
  'request.jwt.claim.sub',
  '7a100000-0000-4000-8000-000000000001',
  true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  '7a110000-0000-4000-8000-000000000001/' ||
    '7a100000-0000-4000-8000-000000000001/uploads/' || fixture.filename,
  jsonb_build_object(
    'size', fixture.size_bytes,
    'mimetype', fixture.mime_type
  )
from (values
  ('wrong-product.mp4', 1010, 'video/mp4'),
  ('wrong-source.webp', 1020, 'image/webp'),
  ('good-product.webp', 1030, 'image/webp'),
  ('good-packshot.png', 1040, 'image/png'),
  ('good-reference.jpg', 1050, 'image/jpeg'),
  ('good-source.mp4', 1060, 'video/mp4'),
  ('legacy-wrong-product.mp4', 1070, 'video/mp4')
) fixture(filename, size_bytes, mime_type);

select throws_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', '7a110000-0000-4000-8000-000000000001',
      'project_id', '7a120000-0000-4000-8000-000000000001',
      'product_id', '7a130000-0000-4000-8000-000000000001',
      'bucket', 'contentengine-private',
      'object_key', '7a110000-0000-4000-8000-000000000001/' ||
        '7a100000-0000-4000-8000-000000000001/uploads/wrong-product.mp4',
      'original_filename', 'wrong-product.mp4',
      'mime_type', 'video/mp4', 'size_bytes', 1010,
      'sha256', repeat('1', 64), 'kind', 'product_photo',
      'rights_confirmed', true,
      'idempotency_key', 'media-kind-mime-wrong-product-0001'
    ))
  $$,
  '22023', 'media_kind_mime_mismatch',
  'video/mp4 cannot be registered as product_photo'
);

select throws_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', '7a110000-0000-4000-8000-000000000001',
      'project_id', '7a120000-0000-4000-8000-000000000001',
      'bucket', 'contentengine-private',
      'object_key', '7a110000-0000-4000-8000-000000000001/' ||
        '7a100000-0000-4000-8000-000000000001/uploads/wrong-source.webp',
      'original_filename', 'wrong-source.webp',
      'mime_type', 'image/webp', 'size_bytes', 1020,
      'sha256', repeat('2', 64), 'kind', 'source_video',
      'rights_confirmed', true,
      'idempotency_key', 'media-kind-mime-wrong-source-0001'
    ))
  $$,
  '22023', 'media_kind_mime_mismatch',
  'image/webp cannot be registered as source_video'
);

select throws_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'kind', 'product_photo', 'mime_type', null
    ))
  $$,
  '22023', 'media_kind_mime_mismatch',
  'JSON null MIME fails closed for an image material kind'
);

select throws_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'kind', 'source_video'
    ))
  $$,
  '22023', 'media_kind_mime_mismatch',
  'missing MIME fails closed for source_video'
);

select is(
  (
    select count(*)::integer
    from content_factory.media_objects media
    where media.organization_id =
      '7a110000-0000-4000-8000-000000000001'::uuid
      and media.object_name like '%/wrong-%'
  ),
  0,
  'rejected MIME-kind pairs create no media rows'
);

select lives_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', '7a110000-0000-4000-8000-000000000001',
      'project_id', '7a120000-0000-4000-8000-000000000001',
      'product_id', '7a130000-0000-4000-8000-000000000001',
      'bucket', 'contentengine-private',
      'object_key', '7a110000-0000-4000-8000-000000000001/' ||
        '7a100000-0000-4000-8000-000000000001/uploads/good-product.webp',
      'original_filename', 'good-product.webp',
      'mime_type', 'image/webp', 'size_bytes', 1030,
      'sha256', repeat('3', 64), 'kind', 'product_photo',
      'rights_confirmed', true,
      'idempotency_key', 'media-kind-mime-good-product-0001'
    ))
  $$,
  'image/webp remains valid for product_photo'
);

select lives_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', '7a110000-0000-4000-8000-000000000001',
      'project_id', '7a120000-0000-4000-8000-000000000001',
      'product_id', '7a130000-0000-4000-8000-000000000001',
      'bucket', 'contentengine-private',
      'object_key', '7a110000-0000-4000-8000-000000000001/' ||
        '7a100000-0000-4000-8000-000000000001/uploads/good-packshot.png',
      'original_filename', 'good-packshot.png',
      'mime_type', 'image/png', 'size_bytes', 1040,
      'sha256', repeat('4', 64), 'kind', 'packshot',
      'rights_confirmed', true,
      'idempotency_key', 'media-kind-mime-good-packshot-0001'
    ))
  $$,
  'image/png remains valid for packshot'
);

select lives_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', '7a110000-0000-4000-8000-000000000001',
      'project_id', '7a120000-0000-4000-8000-000000000001',
      'bucket', 'contentengine-private',
      'object_key', '7a110000-0000-4000-8000-000000000001/' ||
        '7a100000-0000-4000-8000-000000000001/uploads/good-reference.jpg',
      'original_filename', 'good-reference.jpg',
      'mime_type', 'image/jpeg', 'size_bytes', 1050,
      'sha256', repeat('5', 64), 'kind', 'creator_reference',
      'rights_confirmed', true,
      'idempotency_key', 'media-kind-mime-good-reference-0001'
    ))
  $$,
  'image/jpeg remains valid for creator_reference'
);

select lives_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', '7a110000-0000-4000-8000-000000000001',
      'project_id', '7a120000-0000-4000-8000-000000000001',
      'bucket', 'contentengine-private',
      'object_key', '7a110000-0000-4000-8000-000000000001/' ||
        '7a100000-0000-4000-8000-000000000001/uploads/good-source.mp4',
      'original_filename', 'good-source.mp4',
      'mime_type', 'video/mp4', 'size_bytes', 1060,
      'sha256', repeat('6', 64), 'kind', 'source_video',
      'rights_confirmed', true,
      'idempotency_key', 'media-kind-mime-good-source-0001'
    ))
  $$,
  'video/mp4 remains valid for source_video'
);

select is(
  (
    select count(*)::integer
    from content_factory.media_objects media
    where media.organization_id =
      '7a110000-0000-4000-8000-000000000001'::uuid
      and media.object_name like '%/good-%'
      and media.status = 'ready'
      and media.metadata -> 'rights_confirmed' = 'true'::jsonb
  ),
  4,
  'all four valid image/video material families preserve ready registration'
);

-- Preserve a forensic stand-in for rows created before this boundary existed.
-- The migration intentionally has no table rewrite or retroactive constraint.
insert into content_factory.media_objects (
  id, organization_id, owner_id, project_id, product_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
) values (
  '7a140000-0000-4000-8000-000000000001'::uuid,
  '7a110000-0000-4000-8000-000000000001'::uuid,
  '7a100000-0000-4000-8000-000000000001'::uuid,
  '7a120000-0000-4000-8000-000000000001'::uuid,
  '7a130000-0000-4000-8000-000000000001'::uuid,
  'contentengine-private',
  '7a110000-0000-4000-8000-000000000001/' ||
    '7a100000-0000-4000-8000-000000000001/uploads/' ||
    'legacy-wrong-product.mp4',
  'video/mp4', 1070, repeat('7', 64), 'ready',
  jsonb_build_object(
    'original_filename', 'legacy-wrong-product.mp4',
    'kind', 'product_photo', 'rights_confirmed', true
  ),
  'media-kind-mime-legacy-wrong-0001'
);

select is(
  (
    select jsonb_build_object(
      'mime_type', media.mime_type,
      'kind', media.metadata ->> 'kind',
      'status', media.status,
      'rights_confirmed', media.metadata -> 'rights_confirmed'
    )
    from content_factory.media_objects media
    where media.id = '7a140000-0000-4000-8000-000000000001'::uuid
  ),
  jsonb_build_object(
    'mime_type', 'video/mp4',
    'kind', 'product_photo',
    'status', 'ready',
    'rights_confirmed', true
  ),
  'legacy mismatched rows remain representable and untouched'
);

select ok(
  position(
    'creator_register_media_pre_project_v47'
    in pg_get_functiondef(
      'public.creator_register_media(jsonb)'::regprocedure
    )
  ) > 0,
  'compatible pairs still delegate to the existing project-scoped authority'
);

select * from finish();
rollback;

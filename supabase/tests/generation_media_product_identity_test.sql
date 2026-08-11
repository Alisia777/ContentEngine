begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(10);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'f7100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'generation-media-identity-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Generation Media Identity Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'f7110000-0000-4000-8000-000000000001'::uuid,
  'Generation media identity pgTAP',
  'generation-media-identity-pgtap',
  'active'
);

update content_factory.profiles profile
set status = 'active'
where profile.id = 'f7100000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'f7110000-0000-4000-8000-000000000001'::uuid,
  'f7100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'f7110000-0000-4000-8000-000000000001'::uuid,
  'f7100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'owner',
  'TEST-ONLY waiver for mixed generation media identity.',
  'f7100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values
  (
    'f7120000-0000-4000-8000-000000000001'::uuid,
    'f7110000-0000-4000-8000-000000000001'::uuid,
    null, 'Identity project', 'gold', 'project',
    'active', 2048,
    'f7100000-0000-4000-8000-000000000001'::uuid,
    'f7100000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'f7120000-0000-4000-8000-000000000002'::uuid,
    'f7110000-0000-4000-8000-000000000001'::uuid,
    null, 'Other identity project', 'slate', 'project',
    'active', 1024,
    'f7100000-0000-4000-8000-000000000001'::uuid,
    'f7100000-0000-4000-8000-000000000001'::uuid
  );

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'f7130000-0000-4000-8000-000000000001'::uuid,
  'f7110000-0000-4000-8000-000000000001'::uuid,
  'MILIO-IDENTITY-TEST',
  'MILIO identity test product',
  'active',
  'f7100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, project_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
) values
  (
    'f7140000-0000-4000-8000-000000000001'::uuid,
    'f7110000-0000-4000-8000-000000000001'::uuid,
    'f7100000-0000-4000-8000-000000000001'::uuid,
    'f7130000-0000-4000-8000-000000000001'::uuid,
    'f7120000-0000-4000-8000-000000000001'::uuid,
    'contentengine-private',
    'f7110000-0000-4000-8000-000000000001/f7100000-0000-4000-8000-000000000001/identity/hero.webp',
    'image/webp', 4096, repeat('a', 64), 'ready',
    jsonb_build_object(
      'kind', 'product_photo',
      'rights_confirmed', true,
      'product_id', 'f7130000-0000-4000-8000-000000000099'
    ),
    'generation-media-identity-hero'
  ),
  (
    'f7140000-0000-4000-8000-000000000002'::uuid,
    'f7110000-0000-4000-8000-000000000001'::uuid,
    'f7100000-0000-4000-8000-000000000001'::uuid,
    null,
    'f7120000-0000-4000-8000-000000000001'::uuid,
    'contentengine-private',
    'f7110000-0000-4000-8000-000000000001/f7100000-0000-4000-8000-000000000001/identity/source.mp4',
    'video/mp4', 8192, repeat('b', 64), 'ready',
    '{"kind":"source_video","rights_confirmed":true}'::jsonb,
    'generation-media-identity-video'
  ),
  (
    'f7140000-0000-4000-8000-000000000003'::uuid,
    'f7110000-0000-4000-8000-000000000001'::uuid,
    'f7100000-0000-4000-8000-000000000001'::uuid,
    'f7130000-0000-4000-8000-000000000001'::uuid,
    'f7120000-0000-4000-8000-000000000002'::uuid,
    'contentengine-private',
    'f7110000-0000-4000-8000-000000000001/f7100000-0000-4000-8000-000000000001/identity/other.webp',
    'image/webp', 4096, repeat('c', 64), 'ready',
    '{"kind":"product_photo","rights_confirmed":true}'::jsonb,
    'generation-media-identity-other-project'
  ),
  (
    'f7140000-0000-4000-8000-000000000004'::uuid,
    'f7110000-0000-4000-8000-000000000001'::uuid,
    'f7100000-0000-4000-8000-000000000001'::uuid,
    'f7130000-0000-4000-8000-000000000001'::uuid,
    'f7120000-0000-4000-8000-000000000001'::uuid,
    'contentengine-private',
    'f7110000-0000-4000-8000-000000000001/f7100000-0000-4000-8000-000000000001/identity/spoofed-photo.mp4',
    'video/mp4', 8192, repeat('d', 64), 'ready',
    '{"kind":"product_photo","rights_confirmed":true}'::jsonb,
    'generation-media-identity-spoofed-video-photo'
  );

select ok(
  (
    select procedure.prosecdef
    from pg_proc procedure
    where procedure.oid =
      'public.creator_generation_media_identity(jsonb)'::regprocedure
  ),
  'identity reader remains SECURITY DEFINER'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_generation_media_identity(jsonb)',
    'execute'
  ),
  'authenticated project members keep identity reader access'
);

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'f7100000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

select is(
  jsonb_array_length(
    public.creator_generation_media_identity(jsonb_build_object(
      'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
      'media_ids', jsonb_build_array(
        'f7140000-0000-4000-8000-000000000001',
        'f7140000-0000-4000-8000-000000000002'
      )
    )) -> 'items'
  ),
  1,
  'a visible source video no longer suppresses an eligible source photo'
);

select is(
  public.creator_generation_media_identity(jsonb_build_object(
    'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
    'media_ids', jsonb_build_array(
      'f7140000-0000-4000-8000-000000000001',
      'f7140000-0000-4000-8000-000000000002'
    )
  )) #>> '{items,0,public_id}',
  'f7140000-0000-4000-8000-000000000001'::text,
  'the exact eligible source photo is returned'
);

select is(
  public.creator_generation_media_identity(jsonb_build_object(
    'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
    'media_ids', jsonb_build_array(
      'f7140000-0000-4000-8000-000000000001',
      'f7140000-0000-4000-8000-000000000002'
    )
  )) #>> '{items,0,product_id}',
  'f7130000-0000-4000-8000-000000000001'::text,
  'identity uses the relational product_id instead of metadata'
);

select is(
  public.creator_generation_media_identity(jsonb_build_object(
    'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
    'media_ids', jsonb_build_array(
      'f7140000-0000-4000-8000-000000000001',
      'f7140000-0000-4000-8000-000000000002'
    )
  )) #>> '{items,0,rights_confirmed}',
  'true'::text,
  'the independent rights attestation is preserved'
);

select is(
  public.creator_generation_media_identity(jsonb_build_object(
    'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
    'media_ids', jsonb_build_array(
      'f7140000-0000-4000-8000-000000000001',
      'f7140000-0000-4000-8000-000000000002'
    )
  )) #>> '{_meta,requested_count}',
  '2'::text,
  'the mixed request count is explicit'
);

select is(
  public.creator_generation_media_identity(jsonb_build_object(
    'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
    'media_ids', jsonb_build_array(
      'f7140000-0000-4000-8000-000000000001',
      'f7140000-0000-4000-8000-000000000002'
    )
  )) #>> '{_meta,resolved_count}',
  '1'::text,
  'only verified source-photo identities count as resolved'
);

select is(
  jsonb_array_length(
    public.creator_generation_media_identity(jsonb_build_object(
      'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
      'media_ids', jsonb_build_array(
        'f7140000-0000-4000-8000-000000000004'
      )
    )) -> 'items'
  ),
  0,
  'an MP4 mislabeled as product_photo never receives image identity'
);

select throws_ok(
  $$select public.creator_generation_media_identity(jsonb_build_object(
    'organization_id', 'f7110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'f7120000-0000-4000-8000-000000000001'::uuid,
    'media_ids', jsonb_build_array(
      'f7140000-0000-4000-8000-000000000001',
      'f7140000-0000-4000-8000-000000000003'
    )
  ))$$,
  '42501',
  'project_media_scope_mismatch',
  'a cross-project UUID still fails the complete request closed'
);

reset role;

select * from finish();
rollback;

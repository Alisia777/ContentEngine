begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(13);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
  (
    'ca100000-0000-4000-8000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated', 'authenticated',
    'catalog-media-status-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Catalog Media Status Owner"}'::jsonb,
    now(), now()
  ),
  (
    'ca100000-0000-4000-8000-000000000002'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated', 'authenticated',
    'catalog-media-status-outsider@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Catalog Media Status Outsider"}'::jsonb,
    now(), now()
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  'ca110000-0000-4000-8000-000000000001'::uuid,
  'Catalog Media Status pgTAP',
  'catalog-media-status-pgtap',
  'active'
);

update content_factory.profiles profile
set status = 'active'
where profile.id in (
  'ca100000-0000-4000-8000-000000000001'::uuid,
  'ca100000-0000-4000-8000-000000000002'::uuid
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'ca110000-0000-4000-8000-000000000001'::uuid,
    'ca100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'active'
  ),
  (
    'ca110000-0000-4000-8000-000000000001'::uuid,
    'ca100000-0000-4000-8000-000000000002'::uuid,
    'operator', 'active'
  );

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values
  (
    'ca110000-0000-4000-8000-000000000001'::uuid,
    'ca100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'owner',
    'TEST-ONLY waiver for the catalog media status contract.',
    'ca100000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'ca110000-0000-4000-8000-000000000001'::uuid,
    'ca100000-0000-4000-8000-000000000002'::uuid,
    'operator', 'operator',
    'TEST-ONLY waiver for the project ACL regression assertion.',
    'ca100000-0000-4000-8000-000000000001'::uuid
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  'ca120000-0000-4000-8000-000000000001'::uuid,
  'ca110000-0000-4000-8000-000000000001'::uuid,
  null, 'Catalog media status project', 'amber', 'project',
  'active', 1024,
  'ca100000-0000-4000-8000-000000000001'::uuid,
  'ca100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'ca130000-0000-4000-8000-000000000001'::uuid,
  'ca110000-0000-4000-8000-000000000001'::uuid,
  'CATALOG-STATUS-1', 'Catalog status exact product', 'active',
  '{"content_review_category":"household"}'::jsonb,
  'ca100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, project_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
) values
  (
    'ca140000-0000-4000-8000-000000000001'::uuid,
    'ca110000-0000-4000-8000-000000000001'::uuid,
    'ca100000-0000-4000-8000-000000000001'::uuid,
    'ca130000-0000-4000-8000-000000000001'::uuid,
    'ca120000-0000-4000-8000-000000000001'::uuid,
    'contentengine-private',
    'ca110000-0000-4000-8000-000000000001/ca100000-0000-4000-8000-000000000001/catalog/product.webp',
    'image/webp', 4096, repeat('a', 64), 'ready',
    jsonb_build_object(
      'kind', 'product_photo',
      'product_id', 'ca130000-0000-4000-8000-000000000099'
    ),
    'catalog-media-status-ready'
  ),
  (
    'ca140000-0000-4000-8000-000000000002'::uuid,
    'ca110000-0000-4000-8000-000000000001'::uuid,
    'ca100000-0000-4000-8000-000000000001'::uuid,
    'ca130000-0000-4000-8000-000000000001'::uuid,
    'ca120000-0000-4000-8000-000000000001'::uuid,
    'contentengine-private',
    'ca110000-0000-4000-8000-000000000001/ca100000-0000-4000-8000-000000000001/catalog/uploading.webp',
    'image/webp', 4096, repeat('b', 64), 'uploading',
    '{"kind":"product_photo"}'::jsonb,
    'catalog-media-status-uploading'
  );

select ok(
  (
    select procedure.prosecdef
    from pg_proc procedure
    where procedure.oid =
      'public.creator_content_review_catalog(jsonb)'::regprocedure
  ),
  'catalog remains SECURITY DEFINER'
);

select is(
  (
    select procedure.provolatile::text
    from pg_proc procedure
    where procedure.oid =
      'public.creator_content_review_catalog(jsonb)'::regprocedure
  ),
  'v'::text,
  'catalog preserves its VOLATILE contract'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_content_review_catalog(jsonb)',
    'execute'
  ),
  'authenticated users keep catalog access'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_content_review_catalog(jsonb)',
    'execute'
  ),
  'anonymous users remain excluded'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_content_review_catalog_pre_media_status(jsonb)',
    'execute'
  ),
  'preserved catalog implementation is not browser-callable'
);

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'ca100000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

select is(
  public.creator_content_review_catalog(jsonb_build_object(
    'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
  )) ->> 'project_id',
  'ca120000-0000-4000-8000-000000000001'::text,
  'existing project-scoped response is preserved'
);

select is(
  public.creator_content_review_catalog(jsonb_build_object(
    'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
  )) #>> '{ruleset,version}',
  'ru-content-compliance-2026-07-16.1'::text,
  'existing ruleset response is preserved'
);

select is(
  jsonb_array_length(
    public.creator_content_review_catalog(jsonb_build_object(
      'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
    )) -> 'media'
  ),
  1,
  'only ready project media remains in the catalog'
);

select is(
  public.creator_content_review_catalog(jsonb_build_object(
    'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
  )) #>> '{media,0,id}',
  'ca140000-0000-4000-8000-000000000001'::text,
  'the exact ready media row is preserved'
);

select is(
  public.creator_content_review_catalog(jsonb_build_object(
    'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
  )) #>> '{media,0,status}',
  'ready'::text,
  'media status is serialized from the authoritative row'
);

select is(
  public.creator_content_review_catalog(jsonb_build_object(
    'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
  )) #>> '{media,0,product_id}',
  'ca130000-0000-4000-8000-000000000001'::text,
  'media product_id is the relational identity, not metadata'
);

reset role;
select set_config(
  'request.jwt.claim.sub',
  'ca100000-0000-4000-8000-000000000002',
  true
);
set local role authenticated;

select throws_ok(
  $$select public.creator_content_review_catalog(jsonb_build_object(
    'organization_id', 'ca110000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'ca120000-0000-4000-8000-000000000001'::uuid
  ))$$,
  '42501',
  'workspace_project_access_required',
  'the preserved exact-project ACL still fails closed'
);

reset role;

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.creator_content_review_catalog_pre_media_status(jsonb)',
    'execute'
  ),
  'preserved catalog implementation is not a service-role endpoint'
);

select * from finish();
rollback;

begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(25);

select has_column(
  'content_factory',
  'media_objects',
  'artifact_class',
  'media records carry a server-owned artifact class'
);
select has_column(
  'content_factory',
  'media_objects',
  'lifecycle_stage',
  'media records carry a server-owned lifecycle stage'
);
select ok(
  not has_column_privilege(
    'authenticated',
    'content_factory.media_objects',
    'artifact_class',
    'UPDATE'
  ),
  'the browser cannot update artifact classification directly'
);

select is(
  content_factory_private.workspace_media_artifact_class('product_photo'),
  'source',
  'product photos are source artifacts'
);
select is(
  content_factory_private.workspace_media_artifact_class('generated_image'),
  'generated_output',
  'generated images are output artifacts'
);
select is(
  content_factory_private.workspace_media_artifact_class('other'),
  'unclassified',
  'unknown kinds remain fail-closed and unclassified'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'a1000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated',
  'authenticated',
  'workspace-media-classification@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Workspace Media Classification"}'::jsonb,
  now(),
  now()
);

insert into content_factory.organizations (
  id, name, slug, status
) values (
  'a1100000-0000-4000-8000-000000000001',
  'Workspace Media Classification',
  'workspace-media-classification',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'a1100000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001',
  'owner',
  'active'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  system_role, status, position, created_by, updated_by
) values (
  'a1200000-0000-4000-8000-000000000001',
  'a1100000-0000-4000-8000-000000000001',
  null,
  'Classification project',
  'gold',
  'project',
  null,
  'active',
  10000,
  'a1000000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  system_role, status, position, created_by, updated_by
)
select
  fixture.id::uuid,
  'a1100000-0000-4000-8000-000000000001'::uuid,
  'a1200000-0000-4000-8000-000000000001'::uuid,
  fixture.name,
  'gold',
  'folder',
  fixture.system_role,
  'active',
  fixture.position,
  'a1000000-0000-4000-8000-000000000001'::uuid,
  'a1000000-0000-4000-8000-000000000001'::uuid
from (values
  ('a1210000-0000-4000-8000-000000000001', 'Исходники', 'sources', 5120),
  ('a1210000-0000-4000-8000-000000000002', 'Черновики', 'drafts', 4096),
  ('a1210000-0000-4000-8000-000000000003', 'На проверке', 'review', 3072),
  ('a1210000-0000-4000-8000-000000000004', 'Готово', 'ready', 2048),
  ('a1210000-0000-4000-8000-000000000005', 'Опубликовано', 'published', 1024),
  ('a1210000-0000-4000-8000-000000000006', 'Выбор пользователя', null, 512)
) fixture(id, name, system_role, position);

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values
  (
    'a1300000-0000-4000-8000-000000000001',
    'a1100000-0000-4000-8000-000000000001',
    'a1200000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/uploads/source.webp',
    'image/webp',
    100,
    repeat('1', 64),
    'ready',
    '{"kind":"product_photo","rights_confirmed":true}',
    'workspace-media-class-source-0001'
  ),
  (
    'a1300000-0000-4000-8000-000000000002',
    'a1100000-0000-4000-8000-000000000001',
    'a1200000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/generated/image.webp',
    'image/webp',
    200,
    repeat('2', 64),
    'ready',
    '{"kind":"generated_image","rights_confirmed":true}',
    'workspace-media-class-image-0001'
  ),
  (
    'a1300000-0000-4000-8000-000000000003',
    'a1100000-0000-4000-8000-000000000001',
    'a1200000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/generated/video.mp4',
    'video/mp4',
    300,
    repeat('3', 64),
    'ready',
    '{"kind":"generated_video","rights_confirmed":true}',
    'workspace-media-class-video-0001'
  ),
  (
    'a1300000-0000-4000-8000-000000000004',
    'a1100000-0000-4000-8000-000000000001',
    'a1200000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/uploads/unknown.webp',
    'image/webp',
    400,
    repeat('4', 64),
    'ready',
    '{"kind":"other","rights_confirmed":true}',
    'workspace-media-class-unknown-0001'
  );

select is(
  (
    select media.artifact_class
    from content_factory.media_objects media
    where media.id = 'a1300000-0000-4000-8000-000000000001'
  ),
  'source',
  'a new product photo is classified as a source'
);
select is(
  (
    select media.lifecycle_stage
    from content_factory.media_objects media
    where media.id = 'a1300000-0000-4000-8000-000000000001'
  ),
  'sources',
  'a new source enters the sources lifecycle stage'
);
select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'a1300000-0000-4000-8000-000000000001'
  ),
  'sources',
  'a new source is projected into the Sources system folder'
);

select is(
  (
    select media.artifact_class
    from content_factory.media_objects media
    where media.id = 'a1300000-0000-4000-8000-000000000002'
  ),
  'generated_output',
  'a generated image is classified as generated output'
);
select is(
  (
    select media.lifecycle_stage
    from content_factory.media_objects media
    where media.id = 'a1300000-0000-4000-8000-000000000002'
  ),
  'drafts',
  'a new generated image enters drafts'
);
select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'a1300000-0000-4000-8000-000000000002'
  ),
  'drafts',
  'a new generated image is projected into Drafts'
);

select is(
  (
    select media.artifact_class
    from content_factory.media_objects media
    where media.id = 'a1300000-0000-4000-8000-000000000004'
  ),
  'unclassified',
  'an unknown media kind stays unclassified'
);
select is(
  (
    select location.folder_id
    from content_factory.workspace_media_locations location
    where location.media_object_id =
      'a1300000-0000-4000-8000-000000000004'
  ),
  null::uuid,
  'unclassified media stays unfiled'
);

create temporary table workspace_media_sync_version as
select location.version
from content_factory.workspace_media_locations location
where location.media_object_id =
  'a1300000-0000-4000-8000-000000000002';

do $$
begin
  perform content_factory_private.sync_workspace_media_system_location(
    'a1100000-0000-4000-8000-000000000001',
    'a1300000-0000-4000-8000-000000000002',
    false
  );
end;
$$;

select is(
  (
    select location.version
    from content_factory.workspace_media_locations location
    where location.media_object_id =
      'a1300000-0000-4000-8000-000000000002'
  ),
  (select context.version from workspace_media_sync_version context),
  'repeating the same folder synchronization is idempotent'
);

update content_factory.workspace_media_locations location
set folder_id = 'a1210000-0000-4000-8000-000000000006'
where location.media_object_id =
  'a1300000-0000-4000-8000-000000000002';

do $$
begin
  perform content_factory_private.sync_workspace_media_system_location(
    'a1100000-0000-4000-8000-000000000001',
    'a1300000-0000-4000-8000-000000000002',
    false
  );
end;
$$;

select is(
  (
    select location.folder_id
    from content_factory.workspace_media_locations location
    where location.media_object_id =
      'a1300000-0000-4000-8000-000000000002'
  ),
  'a1210000-0000-4000-8000-000000000006'::uuid,
  'classification retries preserve a manual custom folder'
);

update content_factory.media_objects media
set lifecycle_stage = 'review'
where media.id = 'a1300000-0000-4000-8000-000000000002';

select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'a1300000-0000-4000-8000-000000000002'
  ),
  'review',
  'an explicit workflow transition moves custom placement to Review'
);

select ok(
  content_factory_private.workspace_folder_scope_matches(
    '{}'::jsonb,
    'a1210000-0000-4000-8000-000000000006'
  ),
  'an omitted folder filter means all project folders'
);
select ok(
  content_factory_private.workspace_folder_scope_matches(
    '{"folder_id":null}'::jsonb,
    null
  ),
  'an explicit null folder matches an unfiled row'
);
select ok(
  not content_factory_private.workspace_folder_scope_matches(
    '{"folder_id":null}'::jsonb,
    'a1210000-0000-4000-8000-000000000006'
  ),
  'an explicit null folder does not match a filed row'
);
select ok(
  content_factory_private.workspace_media_kind_supported('generated_image'),
  'the narrow media-kind contract includes generated images'
);
select ok(
  to_regprocedure(
    'content_factory_private.creator_workspace_browser_pre_media_scope_v418(jsonb)'
  ) is not null,
  'the previous audited workspace reader is preserved privately'
);
select like(
  pg_get_functiondef('public.creator_workspace_browser(jsonb)'::regprocedure),
  '%workspace_folder_scope_matches%',
  'the public workspace RPC actively applies omitted-versus-root scope'
);
select like(
  pg_get_functiondef('public.creator_workspace_browser(jsonb)'::regprocedure),
  '%workspace_media_kind_supported%',
  'the public workspace RPC actively validates the generated-image kind'
);

select is(
  (
    select count(*)::integer
    from content_factory.workspace_media_locations location
    where location.media_object_id in (
      'a1300000-0000-4000-8000-000000000001',
      'a1300000-0000-4000-8000-000000000002',
      'a1300000-0000-4000-8000-000000000003',
      'a1300000-0000-4000-8000-000000000004'
    )
  ),
  4,
  'each media object keeps exactly one logical location'
);

select * from finish();
rollback;

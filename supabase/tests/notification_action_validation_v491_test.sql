begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(31);

select has_function(
  'public', 'creator_validate_notification_action', array['jsonb'],
  'one authenticated action-time validator exists'
);
select is(
  (select prokind::text
   from pg_proc
   where oid = 'public.creator_validate_notification_action(jsonb)'::regprocedure),
  'f',
  'validator is a function'
);
select is(
  (select provolatile::text
   from pg_proc
   where oid = 'public.creator_validate_notification_action(jsonb)'::regprocedure),
  's',
  'validator is stable and read-only by contract'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'public.creator_validate_notification_action(jsonb)'::regprocedure),
  'validator owns its recipient-scoped table reads'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_validate_notification_action(jsonb)',
    'execute'
  ),
  'authenticated may request one action validation'
);
select ok(
  not has_function_privilege(
    'anon',
    'public.creator_validate_notification_action(jsonb)',
    'execute'
  ),
  'anonymous callers cannot validate actions'
);
select ok(
  not has_function_privilege(
    'service_role',
    'public.creator_validate_notification_action(jsonb)',
    'execute'
  ),
  'validator is not a service transport duplicate'
);

select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'notification\.recipient_id = user_id_value',
  'row is reloaded for the current recipient'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'actor_role_value = any\(notification_row\.recipient_role_ids\)',
  'active recipient role is rechecked'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'notification_row\.expires_at <= now\(\)',
  'expiry is rechecked at action time'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'workspace_project_access_allowed',
  'current project ACL is required'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'content_factory\.media_objects',
  'object actions resolve a typed media record'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'content_factory\.generation_jobs',
  'process actions may resolve an exact visible generation job'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'content_factory\.content_review_runs',
  'process actions may resolve an exact visible review'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  'content_factory\.placements',
  'process actions may resolve an exact visible placement'
);
select ok(
  lower(pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  )) !~ 'update[[:space:]]+content_factory\.user_notifications',
  'validation does not mark the notification read'
);
select ok(
  lower(pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  )) !~ 'insert[[:space:]]+into',
  'validation creates no parallel feed or command row'
);
select ok(
  lower(pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  )) !~ 'deep_link',
  'historical deep links are never executed or returned'
);
select ok(
  lower(pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  )) !~ 'https?[:/]',
  'validator returns no web URL'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  '''command'', jsonb_build_object',
  'success returns one structured command descriptor'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  '''read_mutated'', false',
  'receipt explicitly confirms no read mutation'
);
select matches(
  pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ),
  '''paid_action'', false',
  'notification actions cannot be paid starts'
);
select ok(
  strpos(pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ), '''starts_analysis'', false') > 0
  and strpos(pg_get_functiondef(
    'public.creator_validate_notification_action(jsonb)'::regprocedure
  ), '''starts_generation'', false') > 0,
  'notification actions cannot start analysis or generation'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
  (
    'ad100000-0000-4000-8000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated', 'authenticated',
    'notification-action-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Notification Action Owner"}'::jsonb, now(), now()
  ),
  (
    'ad100000-0000-4000-8000-000000000002'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated', 'authenticated',
    'notification-action-viewer@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Notification Action Viewer"}'::jsonb, now(), now()
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  'ad110000-0000-4000-8000-000000000001'::uuid,
  'Notification action validator pgTAP',
  'notification-action-validator-pgtap',
  'active'
);

update content_factory.profiles profile
set status = 'active'
where profile.id in (
  'ad100000-0000-4000-8000-000000000001'::uuid,
  'ad100000-0000-4000-8000-000000000002'::uuid
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'ad110000-0000-4000-8000-000000000001'::uuid,
    'ad100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'active'
  ),
  (
    'ad110000-0000-4000-8000-000000000001'::uuid,
    'ad100000-0000-4000-8000-000000000002'::uuid,
    'viewer', 'active'
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'ad120000-0000-4000-8000-000000000001'::uuid,
  'ad110000-0000-4000-8000-000000000001'::uuid,
  null, 'Notification action project', 'blue', 'project', null,
  'active', 1024,
  'ad100000-0000-4000-8000-000000000001'::uuid,
  'ad100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.user_notifications (
  id, organization_id, recipient_id, kind, severity, title, body,
  deep_link, properties, request_hash, dedupe_key, contract_version,
  event_created_at, expires_at, source_section, requires_action,
  action_key, project_id, recipient_role_ids, canonical_dedupe_key,
  dedupe_version, read_state_version
) values (
  'ad130000-0000-4000-8000-000000000001'::uuid,
  'ad110000-0000-4000-8000-000000000001'::uuid,
  'ad100000-0000-4000-8000-000000000001'::uuid,
  'action_required', 'warning', 'AI decision is ready',
  'Open the exact current project decision queue.',
  '#/workspace/ai?project_id=ad120000-0000-4000-8000-000000000001&tab=decisions',
  '{}'::jsonb, repeat('a', 64), 'notification-action-ready-v491', 491,
  now() - interval '1 minute', now() + interval '1 day',
  'ai', true, 'ai.open-decisions',
  'ad120000-0000-4000-8000-000000000001'::uuid,
  array['owner']::text[], 'notification:action:ready:v491', 1, 491
);

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'ad100000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'ai.open-decisions',
    'project_id', 'ad120000-0000-4000-8000-000000000001'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{status}',
  'ready',
  'exact recipient and current project ACL validate one action'
);
select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'ai.open-decisions',
    'project_id', 'ad120000-0000-4000-8000-000000000001'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{command,target,canonicalTarget}',
  'contentengine://app/ai?space=bombbar&tab=decisions',
  'validator returns the registry canonical internal target only'
);
select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'ai.open-decisions',
    'project_id', 'ad120000-0000-4000-8000-000000000001'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{already_read}',
  'false',
  'validator reports the exact current read state'
);

reset role;
select ok(
  (select read_at is null
   from content_factory.user_notifications
   where id = 'ad130000-0000-4000-8000-000000000001'::uuid),
  'successful validation leaves the notification unread'
);
set local role authenticated;
select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'ai.open-decisions',
    'project_id', 'ad120000-0000-4000-8000-000000000099'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{reason}',
  'stale_notification',
  'a changed exact target is blocked before routing'
);
select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'paid.retry-generation',
    'project_id', 'ad120000-0000-4000-8000-000000000001'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{reason}',
  'unknown_action',
  'unknown and paid-like action intents stay blocked'
);

reset role;
update content_factory.memberships
set role = 'viewer'
where organization_id = 'ad110000-0000-4000-8000-000000000001'::uuid
  and profile_id = 'ad100000-0000-4000-8000-000000000001'::uuid;
set local role authenticated;
select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'ai.open-decisions',
    'project_id', 'ad120000-0000-4000-8000-000000000001'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{reason}',
  'permission_denied',
  'a current-role change blocks the old role-targeted action'
);

reset role;
select set_config(
  'request.jwt.claim.sub',
  'ad100000-0000-4000-8000-000000000002',
  true
);
set local role authenticated;
select is(
  public.creator_validate_notification_action(jsonb_build_object(
    'organization_id', 'ad110000-0000-4000-8000-000000000001'::uuid,
    'notification_id', 'ad130000-0000-4000-8000-000000000001'::uuid,
    'action_key', 'ai.open-decisions',
    'project_id', 'ad120000-0000-4000-8000-000000000001'::uuid,
    'object_id', null,
    'process_id', null
  )) #>> '{reason}',
  'notification_unavailable',
  'another organization member cannot validate another recipient row'
);

reset role;

select * from finish();
rollback;

begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(36);

select has_column(
  'content_factory', 'user_notifications', 'canonical_dedupe_key',
  'v4.9.1 extends the existing inbox'
);
select has_column(
  'content_factory', 'notification_outbox', 'canonical_dedupe_key',
  'v4.9.1 extends the existing durable outbox'
);
select has_column(
  'content_factory', 'user_notifications', 'read_state_version',
  'read state has an explicit schema version'
);
select ok(
  (select relrowsecurity from pg_class
   where oid = 'content_factory.user_notifications'::regclass),
  'existing inbox RLS remains enabled'
);
select ok(
  (select relrowsecurity from pg_class
   where oid = 'content_factory.notification_outbox'::regclass),
  'existing outbox RLS remains enabled'
);
select ok(
  not has_table_privilege(
    'authenticated', 'content_factory.user_notifications',
    'select,insert,update,delete'
  ),
  'authenticated keeps no direct inbox privileges'
);
select ok(
  not has_table_privilege(
    'authenticated', 'content_factory.notification_outbox',
    'select,insert,update,delete'
  ),
  'authenticated keeps no direct outbox privileges'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_notification_center(jsonb)', 'execute'
  ),
  'authenticated can read the scoped projection'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_mark_visible_notifications_read(jsonb)', 'execute'
  ),
  'authenticated can mark an exact visible set read'
);
select ok(
  not has_function_privilege(
    'authenticated', 'public.system_emit_notification(jsonb)', 'execute'
  ),
  'browser roles cannot deliver notifications'
);
select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.enqueue_notification_v491(jsonb)', 'execute'
  ),
  'canonical producer helper is not a PostgREST service endpoint'
);
select is(
  content_factory_private.notification_type_v491(491, 'system'),
  'system_info',
  'legacy system aliases to canonical system_info'
);
select ok(
  content_factory_private.notification_payload_sensitive_v491(
    '{"signed_url":"https://example.test/file?token=secret"}'::jsonb
  ),
  'sensitive payload helper rejects signed URL and token material'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
values
  (
    'a9100000-0000-4000-8000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'notification-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')), now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Notification Owner"}'::jsonb, now(), now()
  ),
  (
    'a9100000-0000-4000-8000-000000000002',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'notification-operator-1@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')), now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Notification Operator One"}'::jsonb, now(), now()
  ),
  (
    'a9100000-0000-4000-8000-000000000003',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'notification-operator-2@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')), now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Notification Operator Two"}'::jsonb, now(), now()
  ),
  (
    'a9100000-0000-4000-8000-000000000004',
    '00000000-0000-0000-0000-000000000000',
    'authenticated', 'authenticated', 'notification-viewer@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')), now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Notification Viewer"}'::jsonb, now(), now()
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  'a9200000-0000-4000-8000-000000000001',
  'Notification Center v491', 'notification-center-v491', 'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('a9200000-0000-4000-8000-000000000001',
   'a9100000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('a9200000-0000-4000-8000-000000000001',
   'a9100000-0000-4000-8000-000000000002', 'operator', 'active'),
  ('a9200000-0000-4000-8000-000000000001',
   'a9100000-0000-4000-8000-000000000003', 'operator', 'active'),
  ('a9200000-0000-4000-8000-000000000001',
   'a9100000-0000-4000-8000-000000000004', 'viewer', 'active');

create temporary table notification_v491_payloads (
  name text primary key,
  payload jsonb not null
) on commit drop;
create temporary table notification_v491_results (
  name text primary key,
  payload jsonb not null
) on commit drop;
grant select, insert, update on notification_v491_results to authenticated;

insert into notification_v491_payloads (name, payload)
values (
  'process-v1', jsonb_build_object(
    'organization_id', 'a9200000-0000-4000-8000-000000000001',
    'recipient_role_ids', jsonb_build_array('operator'),
    'type', 'warning',
    'severity', 'warning',
    'source_section', 'processes',
    'title', 'Process needs attention',
    'body', 'Open the exact stalled process and review its current state.',
    'requires_action', true,
    'action_key', 'process.open',
    'process_id', 'a9300000-0000-4000-8000-000000000001',
    'dedupe_key', 'process:a9300000-0000-4000-8000-000000000001',
    'dedupe_version', 1,
    'created_at', statement_timestamp(),
    'expires_at', statement_timestamp() + interval '7 days',
    'properties', jsonb_build_object('status', 'stalled')
  )
), (
  'process-v2', jsonb_build_object(
    'organization_id', 'a9200000-0000-4000-8000-000000000001',
    'recipient_role_ids', jsonb_build_array('operator'),
    'type', 'process_complete',
    'severity', 'success',
    'source_section', 'processes',
    'title', 'Process completed',
    'body', 'The exact process completed and its result is available.',
    'requires_action', false,
    'action_key', 'process.open',
    'process_id', 'a9300000-0000-4000-8000-000000000001',
    'dedupe_key', 'process:a9300000-0000-4000-8000-000000000001',
    'dedupe_version', 2,
    'created_at', statement_timestamp() + interval '1 second',
    'expires_at', statement_timestamp() + interval '7 days',
    'resolved_at', statement_timestamp() + interval '1 second',
    'properties', jsonb_build_object('status', 'completed')
  )
);

insert into notification_v491_results (name, payload)
select 'enqueue-v1',
  content_factory_private.enqueue_notification_v491(payload)
from notification_v491_payloads where name = 'process-v1';

select is(
  (select payload #>> '{recipient_count}'
   from notification_v491_results where name = 'enqueue-v1'),
  '2',
  'role enqueue resolves exactly the two active operators'
);
select is(
  (select count(*)::integer
   from content_factory.notification_outbox
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and contract_version = 491 and dedupe_version = 1),
  2,
  'role enqueue expands into per-user rows in the existing outbox'
);
select is(
  (select count(*)::integer
   from content_factory.notification_outbox
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and contract_version = 491
     and recipient_role_ids = array['operator']::text[]),
  2,
  'closed role audience is retained on each recipient row'
);
select is(
  (select count(*)::integer
   from content_factory.notification_outbox
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and recipient_id = 'a9100000-0000-4000-8000-000000000004'),
  0,
  'viewer is not invented as an operator recipient'
);

insert into notification_v491_results (name, payload)
select 'replay-v1',
  content_factory_private.enqueue_notification_v491(payload)
from notification_v491_payloads where name = 'process-v1';
select is(
  (select payload #>> '{idempotent_count}'
   from notification_v491_results where name = 'replay-v1'),
  '2',
  'same dedupe version replays against the frozen recipient snapshot'
);
select is(
  (select payload #>> '{enqueued_count}'
   from notification_v491_results where name = 'replay-v1'),
  '0',
  'same dedupe version creates no duplicate outbox rows'
);

update content_factory.notification_outbox outbox
set status = 'delivering',
    attempt_count = outbox.attempt_count + 1,
    lease_token = extensions.gen_random_uuid(),
    lease_expires_at = now() + interval '3 minutes'
where outbox.organization_id = 'a9200000-0000-4000-8000-000000000001'
  and outbox.contract_version = 491
  and outbox.dedupe_version = 1;

select public.system_emit_notification(jsonb_build_object(
  'organization_id', outbox.organization_id,
  'recipient_id', outbox.recipient_id,
  'kind', outbox.kind,
  'severity', outbox.severity,
  'title', outbox.title,
  'body', outbox.body,
  'deep_link', outbox.deep_link,
  'entity_type', outbox.entity_type,
  'entity_id', outbox.entity_id,
  'properties', outbox.properties,
  'idempotency_key', outbox.dedupe_key
))
from content_factory.notification_outbox outbox
where outbox.organization_id = 'a9200000-0000-4000-8000-000000000001'
  and outbox.contract_version = 491
  and outbox.dedupe_version = 1;

select is(
  (select count(*)::integer
   from content_factory.user_notifications
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and contract_version = 491),
  2,
  'durable delivery creates one inbox row per recipient'
);

select set_config(
  'request.jwt.claim.sub',
  'a9100000-0000-4000-8000-000000000002', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);
set local role authenticated;

insert into notification_v491_results (name, payload)
values (
  'operator-one-center',
  public.creator_notification_center(jsonb_build_object(
    'organization_id', 'a9200000-0000-4000-8000-000000000001',
    'filter', 'all'
  ))
);
select is(
  (select payload #>> '{counts,all}'
   from notification_v491_results where name = 'operator-one-center'),
  '1',
  'projection is scoped to the current organization and user'
);
select is(
  (select payload #>> '{items,0,process_id}'
   from notification_v491_results where name = 'operator-one-center'),
  'a9300000-0000-4000-8000-000000000001',
  'projection returns the immutable exact process target'
);

insert into notification_v491_results (name, payload)
select 'read-operator-one',
  public.creator_mark_visible_notifications_read(jsonb_build_object(
    'organization_id', 'a9200000-0000-4000-8000-000000000001',
    'filter', 'all',
    'notification_ids', jsonb_build_array(notification.id),
    'idempotency_key', 'notification-visible-operator-one-v1'
  ))
from content_factory.user_notifications notification
where notification.organization_id = 'a9200000-0000-4000-8000-000000000001'
  and notification.recipient_id = 'a9100000-0000-4000-8000-000000000002'
  and notification.contract_version = 491;
select is(
  (select payload #>> '{scope}' from notification_v491_results
   where name = 'read-operator-one'),
  'visible_filter',
  'read mutation records the exact visible-filter scope'
);

reset role;
select ok(
  (select read_at is not null
   from content_factory.user_notifications
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and recipient_id = 'a9100000-0000-4000-8000-000000000002'
     and contract_version = 491),
  'first operator row is read'
);
select ok(
  (select read_at is null
   from content_factory.user_notifications
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and recipient_id = 'a9100000-0000-4000-8000-000000000003'
     and contract_version = 491),
  'one employee cannot read the second operator row'
);

insert into notification_v491_results (name, payload)
select 'enqueue-v2',
  content_factory_private.enqueue_notification_v491(payload)
from notification_v491_payloads where name = 'process-v2';
select is(
  (select payload #>> '{enqueued_count}'
   from notification_v491_results where name = 'enqueue-v2'),
  '2',
  'newer dedupe version creates one durable update per original recipient'
);

update content_factory.notification_outbox outbox
set status = 'delivering',
    attempt_count = outbox.attempt_count + 1,
    lease_token = extensions.gen_random_uuid(),
    lease_expires_at = now() + interval '3 minutes'
where outbox.organization_id = 'a9200000-0000-4000-8000-000000000001'
  and outbox.contract_version = 491
  and outbox.dedupe_version = 2;

select public.system_emit_notification(jsonb_build_object(
  'organization_id', outbox.organization_id,
  'recipient_id', outbox.recipient_id,
  'kind', outbox.kind,
  'severity', outbox.severity,
  'title', outbox.title,
  'body', outbox.body,
  'deep_link', outbox.deep_link,
  'entity_type', outbox.entity_type,
  'entity_id', outbox.entity_id,
  'properties', outbox.properties,
  'idempotency_key', outbox.dedupe_key
))
from content_factory.notification_outbox outbox
where outbox.organization_id = 'a9200000-0000-4000-8000-000000000001'
  and outbox.contract_version = 491
  and outbox.dedupe_version = 2;

select is(
  (select count(*)::integer
   from content_factory.user_notifications
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and contract_version = 491),
  2,
  'newer version replaces current inbox rows instead of duplicating them'
);
select is(
  (select min(dedupe_version)::text
   from content_factory.user_notifications
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and contract_version = 491),
  '2',
  'both current rows advance to the newer dedupe version'
);
select is(
  (select count(*)::integer
   from content_factory.user_notifications
   where organization_id = 'a9200000-0000-4000-8000-000000000001'
     and contract_version = 491 and read_at is null),
  2,
  'substantive newer version becomes unread without sharing read state'
);

update content_factory.memberships
set role = 'viewer'
where organization_id = 'a9200000-0000-4000-8000-000000000001'
  and profile_id = 'a9100000-0000-4000-8000-000000000003';

insert into notification_v491_results (name, payload)
select 'replay-v2-after-role-change',
  content_factory_private.enqueue_notification_v491(payload)
from notification_v491_payloads where name = 'process-v2';
select is(
  (select payload #>> '{recipient_count}'
   from notification_v491_results
   where name = 'replay-v2-after-role-change'),
  '2',
  'same-version replay preserves its first-entry recipient snapshot'
);

select set_config(
  'request.jwt.claim.sub',
  'a9100000-0000-4000-8000-000000000003', true
);
set local role authenticated;
insert into notification_v491_results (name, payload)
values (
  'changed-role-center',
  public.creator_notification_center(jsonb_build_object(
    'organization_id', 'a9200000-0000-4000-8000-000000000001',
    'filter', 'all'
  ))
);
select is(
  (select payload #>> '{counts,all}'
   from notification_v491_results where name = 'changed-role-center'),
  '0',
  'projection rechecks the employee current active role'
);
reset role;

insert into content_factory.user_notifications (
  organization_id, recipient_id, kind, severity, title, body, deep_link,
  properties, request_hash, dedupe_key, contract_version,
  event_created_at, expires_at, dedupe_version, read_state_version
) values (
  'a9200000-0000-4000-8000-000000000001',
  'a9100000-0000-4000-8000-000000000002',
  'legacy_notice', 'info', 'Expired legacy notice',
  'This finite legacy record must not enter the live projection.',
  '#/workspace/home', '{}'::jsonb, repeat('a', 64),
  'legacy-expired-notification-v491', 1,
  now() - interval '2 days', now() - interval '1 day', 0, 1
);

select set_config(
  'request.jwt.claim.sub',
  'a9100000-0000-4000-8000-000000000002', true
);
set local role authenticated;
insert into notification_v491_results (name, payload)
values (
  'live-after-expired',
  public.creator_notification_center(jsonb_build_object(
    'organization_id', 'a9200000-0000-4000-8000-000000000001',
    'filter', 'all'
  ))
);
select is(
  (select payload #>> '{counts,all}'
   from notification_v491_results where name = 'live-after-expired'),
  '1',
  'expired records never enter list or counts'
);
select throws_ok(
  format(
    'select public.creator_mark_visible_notifications_read(%L::jsonb)',
    jsonb_build_object(
      'organization_id', 'a9200000-0000-4000-8000-000000000001',
      'filter', 'system',
      'notification_ids', jsonb_build_array((
        select id from content_factory.user_notifications
        where organization_id = 'a9200000-0000-4000-8000-000000000001'
          and recipient_id = 'a9100000-0000-4000-8000-000000000002'
          and contract_version = 491
      )),
      'idempotency_key', 'wrong-visible-filter-v491'
    )::text
  ),
  '42501',
  'notification_visible_scope_denied',
  'mark-visible rejects an ID outside the supplied current filter'
);
reset role;

select throws_ok(
  format(
    'select content_factory_private.enqueue_notification_v491(%L::jsonb)',
    (select payload || jsonb_build_object(
      'dedupe_key', 'sensitive:notification-v491',
      'dedupe_version', 1,
      'properties', jsonb_build_object(
        'signed_url', 'https://example.test/file?token=secret'
      )
    ) from notification_v491_payloads where name = 'process-v1')::text
  ),
  '22023',
  'notification_sensitive_payload_rejected',
  'canonical enqueue rejects sensitive target material'
);
select throws_ok(
  format(
    'select content_factory_private.enqueue_notification_v491(%L::jsonb)',
    (select payload || jsonb_build_object(
      'dedupe_key', 'unknown:notification-action-v491',
      'action_key', 'paid.retry-generation'
    ) from notification_v491_payloads where name = 'process-v1')::text
  ),
  '22023',
  'notification_action_key_invalid',
  'unknown or paid action keys are blocked explicitly'
);
select throws_ok(
  $$delete from content_factory.user_notifications
    where organization_id = 'a9200000-0000-4000-8000-000000000001'$$,
  '55000',
  'notification_deletion_forbidden',
  'notification rows remain non-deletable by clients or ordinary writers'
);

select * from finish();
rollback;

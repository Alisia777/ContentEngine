begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(42);

select has_table(
  'content_factory', 'notification_outbox',
  'durable notification outbox exists'
);
select has_column(
  'content_factory', 'notification_outbox', 'lease_token',
  'outbox deliveries use a private lease token'
);
select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'content_factory.notification_outbox'::regclass
  ),
  'notification outbox uses RLS'
);
select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.notification_outbox',
    'select,insert,update,delete'
  ),
  'authenticated has no direct outbox privileges'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_reconcile_background_leases(jsonb)',
    'execute'
  ),
  'service role can reconcile expired work'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_reconcile_background_leases(jsonb)',
    'execute'
  ),
  'authenticated cannot reconcile expired work'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_claim_notification_outbox(jsonb)',
    'execute'
  ),
  'service role can claim notification delivery'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_claim_notification_outbox(jsonb)',
    'execute'
  ),
  'authenticated cannot claim notification delivery'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_complete_notification_outbox(jsonb)',
    'execute'
  ),
  'service role can complete notification delivery'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_complete_notification_outbox(jsonb)',
    'execute'
  ),
  'authenticated cannot complete notification delivery'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_notification_outbox_health(jsonb)',
    'execute'
  ),
  'service role can inspect notification delivery health'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_notification_outbox_health(jsonb)',
    'execute'
  ),
  'authenticated cannot inspect notification delivery health'
);
select is(
  (
    select count(*)::integer
    from pg_trigger trigger
    where not trigger.tgisinternal
      and trigger.tgname in (
        'enqueue_generation_terminal_notification',
        'enqueue_research_terminal_notification',
        'enqueue_review_terminal_notification'
      )
  ),
  3,
  'all three terminal work tables have transactional outbox triggers'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
values (
  '97000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated',
  'authenticated',
  'worker-durability@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Worker Durability"}'::jsonb,
  now(),
  now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  '97100000-0000-4000-8000-000000000001',
  'Worker Durability',
  'worker-durability',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  '97100000-0000-4000-8000-000000000001',
  '97000000-0000-4000-8000-000000000001',
  'owner',
  'active'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values (
  '97200000-0000-4000-8000-000000000001',
  '97100000-0000-4000-8000-000000000001',
  'WORKER-DURABILITY-1',
  'Worker durability product',
  'active',
  '{"content_review_category":"cosmetics"}'::jsonb,
  '97000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values (
  '97300000-0000-4000-8000-000000000001',
  '97100000-0000-4000-8000-000000000001',
  '97000000-0000-4000-8000-000000000001',
  '97200000-0000-4000-8000-000000000001',
  'contentengine-private',
  '97100000-0000-4000-8000-000000000001/97000000-0000-4000-8000-000000000001/review/source.webp',
  'image/webp',
  4096,
  repeat('a', 64),
  'ready',
  '{"kind":"product_photo","rights_confirmed":true}'::jsonb,
  'worker-durability-media'
);

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input,
  request_hash, idempotency_key, started_at, lease_expires_at
)
values (
  '97400000-0000-4000-8000-000000000001',
  '97100000-0000-4000-8000-000000000001',
  '97200000-0000-4000-8000-000000000001',
  '97000000-0000-4000-8000-000000000001',
  'processing',
  '{"objective":"durability test","source_media_ids":[]}'::jsonb,
  repeat('b', 64),
  'worker-durability-research',
  now() - interval '10 minutes',
  now() - interval '5 minutes'
);

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, ruleset_version, request_hash,
  idempotency_key, started_at, lease_expires_at
)
values (
  '97500000-0000-4000-8000-000000000001',
  '97100000-0000-4000-8000-000000000001',
  '97300000-0000-4000-8000-000000000001',
  '97000000-0000-4000-8000-000000000001',
  'processing',
  repeat('a', 64),
  '{"content_kind":"organic"}'::jsonb,
  'worker-durability-rules',
  repeat('c', 64),
  'worker-durability-review',
  now() - interval '15 minutes',
  now() - interval '5 minutes'
);

create temporary table durability_results (
  name text primary key,
  payload jsonb not null
) on commit drop;

insert into durability_results (name, payload)
values (
  'reconcile',
  public.system_reconcile_background_leases(
    '{"limit":10}'::jsonb
  )
);

select is(
  (select payload #>> '{expired,research}'
   from durability_results where name = 'reconcile'),
  '1',
  'expired research lease becomes terminal in the worker cycle'
);
select is(
  (select payload #>> '{expired,review}'
   from durability_results where name = 'reconcile'),
  '1',
  'expired review lease becomes terminal in the worker cycle'
);
select is(
  (
    select status
    from content_factory.product_research_runs
    where id = '97400000-0000-4000-8000-000000000001'
  ),
  'failed',
  'expired research is failed instead of requeued'
);
select is(
  (
    select error_code
    from content_factory.product_research_runs
    where id = '97400000-0000-4000-8000-000000000001'
  ),
  'processing_lease_expired',
  'expired research records the explicit safe timeout code'
);
select ok(
  (
    select completion_hash is not null
    from content_factory.product_research_runs
    where id = '97400000-0000-4000-8000-000000000001'
  ),
  'expired research stores a durable terminal hash'
);
select is(
  (
    select status
    from content_factory.content_review_runs
    where id = '97500000-0000-4000-8000-000000000001'
  ),
  'failed',
  'expired review is failed instead of requeued'
);
select ok(
  (
    select completion_hash is not null
    from content_factory.content_review_runs
    where id = '97500000-0000-4000-8000-000000000001'
  ),
  'expired review stores a durable terminal hash'
);
select is(
  (
    select count(*)::integer
    from content_factory.notification_outbox
    where organization_id =
      '97100000-0000-4000-8000-000000000001'
  ),
  2,
  'terminal lease updates atomically create two outbox obligations'
);
select is(
  (
    select count(distinct dedupe_key)::integer
    from content_factory.notification_outbox
    where organization_id =
      '97100000-0000-4000-8000-000000000001'
  ),
  2,
  'terminal outbox obligations have stable unique keys'
);
select is(
  public.system_reconcile_background_leases(
    '{"limit":10}'::jsonb
  ) #>> '{expired,research}',
  '0',
  'lease reconciliation replay does not change terminal research'
);

insert into durability_results (name, payload)
values (
  'first_claim',
  public.system_claim_notification_outbox('{"limit":10}'::jsonb)
);

select is(
  (
    select jsonb_array_length(payload -> 'items')::text
    from durability_results where name = 'first_claim'
  ),
  '2',
  'both terminal notifications are claimed in one bounded batch'
);
select is(
  (
    select count(*)::integer
    from content_factory.notification_outbox
    where status = 'delivering'
  ),
  2,
  'claim changes both outbox rows to leased delivery'
);

insert into durability_results (name, payload)
select
  'first_retry',
  public.system_complete_notification_outbox(jsonb_build_object(
    'outbox_id', first.payload #>> '{items,0,id}',
    'lease_token', first.payload #>> '{items,0,lease_token}',
    'delivered', false,
    'error_code', 'notification_emit_failed'
  ))
from durability_results first
where first.name = 'first_claim';

select is(
  (select payload #>> '{status}'
   from durability_results where name = 'first_retry'),
  'pending',
  'transient notification failure remains retryable'
);
select is(
  (
    select attempt_count::text
    from content_factory.notification_outbox
    where id = (
      select (payload #>> '{items,0,id}')::uuid
      from durability_results where name = 'first_claim'
    )
  ),
  '1',
  'failed delivery preserves its attempt count'
);
select ok(
  (
    select next_attempt_at > now()
    from content_factory.notification_outbox
    where id = (
      select (payload #>> '{items,0,id}')::uuid
      from durability_results where name = 'first_claim'
    )
  ),
  'transient notification failure gets bounded backoff'
);

insert into durability_results (name, payload)
select
  'emit_second',
  public.system_emit_notification(first.payload #> '{items,1,payload}')
from durability_results first
where first.name = 'first_claim';

insert into durability_results (name, payload)
select
  'complete_second',
  public.system_complete_notification_outbox(jsonb_build_object(
    'outbox_id', first.payload #>> '{items,1,id}',
    'lease_token', first.payload #>> '{items,1,lease_token}',
    'delivered', true
  ))
from durability_results first
where first.name = 'first_claim';

select is(
  (select payload #>> '{status}'
   from durability_results where name = 'complete_second'),
  'delivered',
  'successful notification is durably acknowledged'
);
select is(
  (
    select count(*)::integer
    from content_factory.user_notifications
    where organization_id =
      '97100000-0000-4000-8000-000000000001'
  ),
  1,
  'successful delivery creates one user notification'
);

insert into durability_results (name, payload)
select
  'emit_first_after_lost_response',
  public.system_emit_notification(first.payload #> '{items,0,payload}')
from durability_results first
where first.name = 'first_claim';

insert into durability_results (name, payload)
values (
  'observe_lost_response',
  public.system_claim_notification_outbox('{"limit":10}'::jsonb)
);

select is(
  (select payload #>> '{observed_deliveries}'
   from durability_results where name = 'observe_lost_response'),
  '1',
  'lost notification RPC response is observed idempotently'
);
select is(
  (select payload #>> '{unresolved}'
   from durability_results where name = 'observe_lost_response'),
  '0',
  'observed delivery clears the unresolved outbox count'
);
select is(
  (
    select count(*)::integer
    from content_factory.notification_outbox
    where status = 'delivered'
  ),
  2,
  'both terminal notification obligations are delivered exactly once'
);

insert into content_factory.notification_outbox (
  id, organization_id, recipient_id, kind, severity, title, body,
  deep_link, entity_type, entity_id, properties, request_hash,
  dedupe_key, status, attempt_count, next_attempt_at,
  lease_token, lease_expires_at
)
values (
  '97600000-0000-4000-8000-000000000001',
  '97100000-0000-4000-8000-000000000001',
  '97000000-0000-4000-8000-000000000001',
  'background_review_failed',
  'error',
  'Expired delivery lease',
  'This durable notification is reclaimed.',
  '#/workspace/review',
  'content_review',
  '97600000-0000-4000-8000-000000000001',
  '{"source":"pgtap","status":"failed"}'::jsonb,
  repeat('d', 64),
  'worker-durability-expired-delivery',
  'delivering',
  1,
  now() - interval '10 minutes',
  '97600000-0000-4000-8000-000000000011',
  now() - interval '5 minutes'
);

insert into durability_results (name, payload)
values (
  'recovered_claim',
  public.system_claim_notification_outbox('{"limit":10}'::jsonb)
);

select is(
  (select payload #>> '{recovered_leases}'
   from durability_results where name = 'recovered_claim'),
  '1',
  'expired outbox delivery lease is recovered'
);
select isnt(
  (select payload #>> '{items,0,lease_token}'
   from durability_results where name = 'recovered_claim'),
  '97600000-0000-4000-8000-000000000011',
  'recovered delivery receives a new lease token'
);
select throws_ok(
  $$
    select public.system_complete_notification_outbox(jsonb_build_object(
      'outbox_id', '97600000-0000-4000-8000-000000000001',
      'lease_token', '97600000-0000-4000-8000-000000000011',
      'delivered', true
    ))
  $$,
  '55000',
  'notification_outbox_lease_mismatch',
  'stale delivery worker cannot acknowledge a reclaimed item'
);

insert into durability_results (name, payload)
select
  'recovered_retry',
  public.system_complete_notification_outbox(jsonb_build_object(
    'outbox_id', recovered.payload #>> '{items,0,id}',
    'lease_token', recovered.payload #>> '{items,0,lease_token}',
    'delivered', false,
    'error_code', 'notification_emit_failed'
  ))
from durability_results recovered
where recovered.name = 'recovered_claim';

select is(
  (select payload #>> '{status}'
   from durability_results where name = 'recovered_retry'),
  'pending',
  'recovered lease remains retryable after another transient failure'
);

insert into content_factory.notification_outbox (
  id, organization_id, recipient_id, kind, severity, title, body,
  deep_link, entity_type, entity_id, properties, request_hash,
  dedupe_key, status, attempt_count, next_attempt_at,
  lease_token, lease_expires_at
)
values
  (
    '97600000-0000-4000-8000-000000000002',
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'background_review_failed',
    'error',
    'Already expired delivery',
    'This acknowledgement is too late.',
    '#/workspace/review',
    'content_review',
    '97600000-0000-4000-8000-000000000002',
    '{"source":"pgtap","status":"failed"}'::jsonb,
    repeat('e', 64),
    'worker-durability-complete-expired',
    'delivering',
    1,
    now() - interval '10 minutes',
    '97600000-0000-4000-8000-000000000012',
    now() - interval '1 minute'
  ),
  (
    '97600000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'background_research_failed',
    'error',
    'Dead letter delivery',
    'This durable failure remains visible.',
    '#/workspace/tasks',
    'product_research',
    '97600000-0000-4000-8000-000000000003',
    '{"source":"pgtap","status":"failed"}'::jsonb,
    repeat('f', 64),
    'worker-durability-dead-letter',
    'delivering',
    12,
    now() - interval '10 minutes',
    '97600000-0000-4000-8000-000000000013',
    now() + interval '1 minute'
  );

select throws_ok(
  $$
    select public.system_complete_notification_outbox(jsonb_build_object(
      'outbox_id', '97600000-0000-4000-8000-000000000002',
      'lease_token', '97600000-0000-4000-8000-000000000012',
      'delivered', true
    ))
  $$,
  '55000',
  'notification_outbox_lease_expired',
  'late acknowledgement cannot consume an expired delivery lease'
);

insert into durability_results (name, payload)
values (
  'dead_letter',
  public.system_complete_notification_outbox(jsonb_build_object(
    'outbox_id', '97600000-0000-4000-8000-000000000003',
    'lease_token', '97600000-0000-4000-8000-000000000013',
    'delivered', false,
    'error_code', 'notification_emit_failed'
  ))
);

select is(
  (select payload #>> '{status}'
   from durability_results where name = 'dead_letter'),
  'failed',
  'twelfth failed attempt becomes a preserved dead letter'
);
select is(
  public.system_notification_outbox_health('{}'::jsonb) #>> '{failed}',
  '1',
  'outbox health surfaces the dead letter count'
);
select is(
  public.system_notification_outbox_health('{}'::jsonb) #>> '{unresolved}',
  '3',
  'outbox health surfaces every unresolved delivery state'
);
select throws_ok(
  $$
    delete from content_factory.notification_outbox
    where id = '97600000-0000-4000-8000-000000000003'
  $$,
  '55000',
  'notification_outbox_deletion_forbidden',
  'notification outbox history cannot be deleted'
);

select * from finish();
rollback;

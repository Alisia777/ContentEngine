begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(15);

select ok(
  (
    select relation.relrowsecurity and relation.relforcerowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'invite_delivery_attempts'
  ),
  'invite delivery attempts enable and force RLS'
);

select ok(
  exists (
    select 1
    from pg_policy policy
    join pg_class relation on relation.oid = policy.polrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'invite_delivery_attempts'
      and policy.polname = 'invite_delivery_attempts_deny_direct'
      and not policy.polpermissive
  ),
  'invite delivery attempts have an explicit restrictive direct-access policy'
);

select ok(
  not has_table_privilege(
    'anon',
    'content_factory.invite_delivery_attempts',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.invite_delivery_attempts',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'service_role',
    'content_factory.invite_delivery_attempts',
    'select,insert,update,delete'
  ),
  'invite delivery journal remains available only through audited RPCs'
);

select ok(
  to_regclass('content_factory.member_password_dispatches') is not null,
  'one-time member password dispatch journal exists'
);

select ok(
  (
    select relation.relrowsecurity and relation.relforcerowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'member_password_dispatches'
  ),
  'member password dispatch journal enables and forces RLS'
);

select ok(
  not has_table_privilege(
    'anon',
    'content_factory.member_password_dispatches',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.member_password_dispatches',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'service_role',
    'content_factory.member_password_dispatches',
    'select,insert,update,delete'
  ),
  'member password fingerprints are not directly readable by API roles'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    join pg_class relation on relation.oid = constraint_row.conrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'member_password_dispatches'
      and constraint_row.contype = 'u'
      and pg_get_constraintdef(constraint_row.oid) like '%password_fingerprint%'
  ),
  'a temporary password fingerprint cannot be reused across dispatches'
);

select ok(
  (
    select relation.relrowsecurity and relation.relforcerowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'public_recovery_quota_buckets'
  ),
  'public recovery quota buckets enable and force RLS'
);

select ok(
  not has_table_privilege(
    'anon',
    'content_factory.public_recovery_quota_buckets',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.public_recovery_quota_buckets',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'service_role',
    'content_factory.public_recovery_quota_buckets',
    'select,insert,update,delete'
  ),
  'recovery quota counters are server-only'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.system_reserve_public_recovery_receipt_pre_abuse_quota(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_reserve_public_recovery_receipt(jsonb)',
    'execute'
  ),
  'service role cannot bypass the public recovery quota wrapper'
);

insert into content_factory.public_recovery_quota_buckets (
  scope,
  scope_hash,
  bucket_started_at,
  request_count
) values (
  'client',
  repeat('a', 64),
  date_bin(
    interval '10 minutes',
    now(),
    timestamptz '2000-01-01 00:00:00+00'
  ),
  8
);

create temporary table auth_security_results (
  key text primary key,
  value jsonb not null
);

insert into auth_security_results (key, value)
select 'client_limited', public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '98000000-0000-4000-8000-000000000001',
    'receipt_hash', repeat('b', 64),
    'client_key_hash', repeat('a', 64),
    'email', 'client-quota-outsider@example.test'
  )
);

select is(
  (select value ->> 'dispatch_required'
   from auth_security_results where key = 'client_limited'),
  'false',
  'per-client quota suppresses the provider request'
);

select ok(
  not exists (
    select 1
    from content_factory.public_recovery_quota_buckets bucket
    where bucket.scope = 'global'
      and bucket.bucket_started_at = date_bin(
        interval '10 minutes',
        now(),
        timestamptz '2000-01-01 00:00:00+00'
      )
  ),
  'a blocked client does not consume global recovery capacity'
);

select is(
  (
    select receipt.reason_code
    from content_factory.public_recovery_receipts receipt
    where receipt.request_id = '98000000-0000-4000-8000-000000000001'
  ),
  'public_recovery_quota_limited',
  'quota suppression is durably journaled without claiming delivery'
);

select public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '98000000-0000-4000-8000-000000000001',
    'receipt_hash', repeat('b', 64),
    'client_key_hash', repeat('a', 64),
    'email', 'client-quota-outsider@example.test'
  )
);

select is(
  (
    select bucket.request_count
    from content_factory.public_recovery_quota_buckets bucket
    where bucket.scope = 'client'
      and bucket.scope_hash = repeat('a', 64)
      and bucket.bucket_started_at = date_bin(
        interval '10 minutes',
        now(),
        timestamptz '2000-01-01 00:00:00+00'
      )
  ),
  8,
  'an idempotent replay does not consume another client quota unit'
);

insert into content_factory.public_recovery_quota_buckets (
  scope,
  scope_hash,
  bucket_started_at,
  request_count
) values (
  'global',
  repeat('0', 64),
  date_bin(
    interval '10 minutes',
    now(),
    timestamptz '2000-01-01 00:00:00+00'
  ),
  120
)
on conflict (scope, scope_hash, bucket_started_at) do update set
  request_count = excluded.request_count;

insert into auth_security_results (key, value)
select 'global_limited', public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '98000000-0000-4000-8000-000000000002',
    'receipt_hash', repeat('c', 64),
    'client_key_hash', repeat('d', 64),
    'email', 'global-quota-outsider@example.test'
  )
);

select is(
  (select value ->> 'dispatch_required'
   from auth_security_results where key = 'global_limited'),
  'false',
  'global quota suppresses the provider request independently of email'
);

select * from finish();
rollback;

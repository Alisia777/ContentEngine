begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(26);

select ok(
  to_regclass('content_factory.public_recovery_receipts') is not null,
  'public recovery receipt journal exists'
);

select ok(
  (
    select relation.relrowsecurity and relation.relforcerowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'public_recovery_receipts'
  ),
  'public recovery journal enables and forces RLS'
);

select ok(
  not has_table_privilege(
    'anon',
    'content_factory.public_recovery_receipts',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.public_recovery_receipts',
    'select,insert,update,delete'
  )
  and not has_table_privilege(
    'service_role',
    'content_factory.public_recovery_receipts',
    'select,insert,update,delete'
  ),
  'all callers use the audited RPC boundary instead of the receipt table'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_reserve_public_recovery_receipt(jsonb)',
    'execute'
  ),
  'service role may reserve a public recovery receipt'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_finalize_public_recovery_receipt(jsonb)',
    'execute'
  ),
  'service role may finalize a public recovery receipt'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_read_public_recovery_receipt(jsonb)',
    'execute'
  ),
  'service role may read the public-safe receipt projection'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.system_reserve_public_recovery_receipt(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_finalize_public_recovery_receipt(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_read_public_recovery_receipt(jsonb)',
    'execute'
  ),
  'anonymous callers cannot invoke service-only receipt RPCs directly'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_reserve_public_recovery_receipt(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_finalize_public_recovery_receipt(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_read_public_recovery_receipt(jsonb)',
    'execute'
  ),
  'authenticated browsers cannot invoke service-only receipt RPCs directly'
);

select ok(
  pg_get_functiondef(
    'public.system_reserve_public_recovery_receipt(jsonb)'::regprocedure
  ) like '%pg_advisory_xact_lock%',
  'receipt and email idempotency decisions are serialized before provider work'
);

create temporary table recovery_test_results (
  key text primary key,
  value jsonb not null
);

insert into recovery_test_results (key, value)
select 'first', public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '91000000-0000-4000-8000-000000000001',
    'receipt_hash', repeat('a', 64),
    'email', 'receipt-outsider@example.test'
  )
);

select is(
  (select value ->> 'ok' from recovery_test_results where key = 'first'),
  'true',
  'an address without portal membership still receives a durable receipt'
);

select is(
  (
    select value ->> 'dispatch_required'
    from recovery_test_results
    where key = 'first'
  ),
  'true',
  'the first receipt is reserved before the provider dispatch is allowed'
);

select is(
  (
    select count(*)
    from content_factory.public_recovery_receipts
    where request_id = '91000000-0000-4000-8000-000000000001'
  ),
  1::bigint,
  'the initial reservation creates exactly one journal row'
);

insert into recovery_test_results (key, value)
select 'replay', public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '91000000-0000-4000-8000-000000000001',
    'receipt_hash', repeat('a', 64),
    'email', 'receipt-outsider@example.test'
  )
);

select is(
  (select value ->> 'replayed' from recovery_test_results where key = 'replay'),
  'true',
  'the same request id and receipt are recognized as a replay'
);

select is(
  (
    select value ->> 'dispatch_required'
    from recovery_test_results
    where key = 'replay'
  ),
  'false',
  'an idempotent replay never authorizes a duplicate provider send'
);

select is(
  (
    select count(*)
    from content_factory.public_recovery_receipts
    where request_id = '91000000-0000-4000-8000-000000000001'
  ),
  1::bigint,
  'an idempotent replay leaves the journal row count unchanged'
);

insert into recovery_test_results (key, value)
select 'conflict', public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '91000000-0000-4000-8000-000000000001',
    'receipt_hash', repeat('b', 64),
    'email', 'different-outsider@example.test'
  )
);

select is(
  (
    select value ->> 'conflict'
    from recovery_test_results
    where key = 'conflict'
  ),
  'true',
  'reusing a request id for different private input fails closed'
);

select is(
  (
    select count(*)
    from content_factory.public_recovery_receipts
    where request_id = '91000000-0000-4000-8000-000000000001'
  ),
  1::bigint,
  'a conflicting replay does not create or mutate a receipt row'
);

insert into recovery_test_results (key, value)
select 'cooldown', public.system_reserve_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '91000000-0000-4000-8000-000000000002',
    'receipt_hash', repeat('c', 64),
    'email', 'receipt-outsider@example.test'
  )
);

select is(
  (select value ->> 'ok' from recovery_test_results where key = 'cooldown'),
  'true',
  'a fresh request id during cooldown still receives a non-enumerating receipt'
);

select is(
  (
    select value ->> 'dispatch_required'
    from recovery_test_results
    where key = 'cooldown'
  ),
  'false',
  'the server cooldown suppresses provider dispatch for the same email'
);

select ok(
  (
    select (value ->> 'retry_after_seconds')::integer >= 600
    from recovery_test_results
    where key = 'cooldown'
  ),
  'the cooldown receipt persists a server-derived retry interval'
);

select is(
  (
    select count(*)
    from content_factory.public_recovery_receipts
    where email = 'receipt-outsider@example.test'
  ),
  2::bigint,
  'the suppressed request has its own durable receipt without a second send'
);

insert into recovery_test_results (key, value)
select 'finalize', public.system_finalize_public_recovery_receipt(
  jsonb_build_object(
    'request_id', '91000000-0000-4000-8000-000000000001',
    'receipt_hash', repeat('a', 64),
    'status', 'accepted',
    'reason_code', 'recovery_request_accepted'
  )
);

select ok(
  (
    select value ->> 'ok' = 'true'
      and value ->> 'found' = 'true'
      and value ->> 'status' = 'accepted'
    from recovery_test_results
    where key = 'finalize'
  ),
  'the reserved outsider receipt can be finalized without exposing identity'
);

insert into recovery_test_results (key, value)
select 'read', public.system_read_public_recovery_receipt(
  jsonb_build_object('receipt_hash', repeat('a', 64))
);

select ok(
  (
    select value ->> 'ok' = 'true'
      and value ->> 'found' = 'true'
    from recovery_test_results
    where key = 'read'
  ),
  'an opaque receipt resolves through the public-safe projection'
);

select is(
  (select value ->> 'status' from recovery_test_results where key = 'read'),
  'accepted',
  'the public-safe projection reports the durable receipt status'
);

select is(
  (
    select value ->> 'delivery_confirmed'
    from recovery_test_results
    where key = 'read'
  ),
  'false',
  'a recovery receipt is never presented as proof of email delivery'
);

select ok(
  (
    select not (
      value ?| array[
        'email',
        'request_id',
        'organization_id',
        'auth_attempt_id',
        'receipt_hash',
        'reason_code',
        'provider',
        'provider_message_id'
      ]
    )
    from recovery_test_results
    where key = 'read'
  ),
  'the public projection omits account, organization, request, and provider data'
);

select * from finish();
rollback;

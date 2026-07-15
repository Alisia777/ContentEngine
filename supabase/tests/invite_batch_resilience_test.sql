begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(6);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    join pg_class relation on relation.oid = constraint_row.conrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'invite_delivery_attempts'
      and constraint_row.conname = 'invite_delivery_attempts_status_check'
      and pg_get_constraintdef(constraint_row.oid) like '%pending_verification%'
  ),
  'invite journal accepts an explicit pending-verification state'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    join pg_class relation on relation.oid = constraint_row.conrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'invite_delivery_attempts'
      and constraint_row.conname = 'invite_delivery_attempts_delivery_status_check'
      and pg_get_constraintdef(constraint_row.oid) like '%unknown%'
  ),
  'invite journal can state that external delivery is unknown'
);

select ok(
  pg_get_functiondef(
    'public.system_record_invite_delivery_attempts(jsonb)'::regprocedure
  ) like '%pg_advisory_xact_lock%',
  'invite reservation is serialized before an external send'
);

select ok(
  pg_get_functiondef(
    'public.system_record_invite_delivery_attempts(jsonb)'::regprocedure
  ) like '%duplicate_request_suppressed%',
  'recent ambiguous duplicate requests are suppressed server-side'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_record_invite_delivery_attempts(jsonb)',
    'execute'
  ),
  'service role can reserve and update invite journal rows'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_record_invite_delivery_attempts(jsonb)',
    'execute'
  ),
  'browser users cannot write trusted invite journal rows'
);

select * from finish();
rollback;

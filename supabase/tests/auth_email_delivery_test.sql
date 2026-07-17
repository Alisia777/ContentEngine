begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

create or replace function pg_temp.grant_auth_email_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $fixture$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
begin
  for module_row in
    select
      module.code,
      jsonb_array_length(
        module.content #> '{knowledge_check,questions}'
      ) as question_count
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
    order by module.order_index
  loop
    insert into content_factory.training_attempts (
      organization_id,
      profile_id,
      module_code,
      status,
      score,
      correct_count,
      answered_count,
      question_count,
      passed,
      answers,
      request_hash,
      idempotency_key
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      'completed',
      1,
      module_row.question_count,
      module_row.question_count,
      module_row.question_count,
      true,
      '{}'::jsonb,
      repeat('8', 64),
      left(
        'course-check:auth-email:' || p_key_prefix || ':' || module_row.code,
        180
      )
    )
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id,
      profile_id,
      module_code,
      attempt_id,
      status
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      attempt_id_value,
      'passed'
    );
  end loop;

  insert into content_factory.training_attempts (
    organization_id,
    profile_id,
    module_code,
    status,
    score,
    correct_count,
    answered_count,
    question_count,
    passed,
    answers,
    request_hash,
    idempotency_key
  ) values (
    p_organization_id,
    p_profile_id,
    'operator_final_exam',
    'completed',
    1,
    12,
    12,
    12,
    true,
    '{}'::jsonb,
    repeat('9', 64),
    left('auth-email-exam:' || p_key_prefix, 180)
  )
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id,
    profile_id,
    module_code,
    attempt_id,
    status
  ) values (
    p_organization_id,
    p_profile_id,
    'operator_final_exam',
    attempt_id_value,
    'passed'
  );
end;
$fixture$;

select plan(106);

select ok(
  to_regclass('content_factory.auth_email_attempts') is not null,
  'normalized auth email attempt journal exists'
);

select ok(
  to_regclass('content_factory.auth_email_delivery_events') is not null,
  'normalized provider delivery event ledger exists'
);

select ok(
  (
    select relation.relrowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'auth_email_attempts'
  ),
  'attempt journal has RLS enabled'
);

select ok(
  (
    select relation.relforcerowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'auth_email_attempts'
  ),
  'attempt journal forces RLS for its owner'
);

select ok(
  (
    select relation.relrowsecurity and relation.relforcerowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'auth_email_delivery_events'
  ),
  'delivery ledger enables and forces RLS'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.auth_email_attempts',
    'select'
  ),
  'browser users cannot read the server attempt journal directly'
);

select ok(
  not has_table_privilege(
    'service_role',
    'content_factory.auth_email_delivery_events',
    'select'
  ),
  'service callers use audited RPCs rather than direct delivery table reads'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_reserve_auth_email_attempt(jsonb)',
    'execute'
  ),
  'service role may reserve an auth email attempt'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_reserve_auth_email_attempt(jsonb)',
    'execute'
  ),
  'browser users cannot reserve trusted auth email attempts'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_finalize_auth_email_attempt(jsonb)',
    'execute'
  ),
  'service role may finalize an auth email attempt'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_finalize_auth_email_attempt(jsonb)',
    'execute'
  ),
  'browser users cannot finalize trusted auth email attempts'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_ingest_auth_email_delivery_event(jsonb)',
    'execute'
  ),
  'service role may ingest a verified delivery event'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_ingest_auth_email_delivery_event(jsonb)',
    'execute'
  ),
  'browser users cannot forge provider delivery events'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_account_access_status(jsonb)',
    'execute'
  ),
  'authenticated managers may call the access diagnosis RPC'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_account_access_status(jsonb)',
    'execute'
  ),
  'anonymous callers cannot diagnose account access'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class relation on relation.oid = trigger_row.tgrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'auth_email_delivery_events'
      and trigger_row.tgname =
        'auth_email_delivery_events_append_only_guard'
      and not trigger_row.tgisinternal
  ),
  'delivery evidence has an append-only trigger'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class relation on relation.oid = trigger_row.tgrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'invite_delivery_attempts'
      and trigger_row.tgname =
        'invite_delivery_attempts_auth_email_mirror'
      and not trigger_row.tgisinternal
  ),
  'legacy bulk invite writes are continuously mirrored'
);

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    join pg_class relation on relation.oid = constraint_row.conrelid
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'invite_delivery_attempts'
      and constraint_row.conname =
        'invite_delivery_attempts_delivery_status_check'
      and pg_get_constraintdef(constraint_row.oid) like '%delivered%'
      and pg_get_constraintdef(constraint_row.oid) like '%complained%'
  ),
  'legacy invite readers remain compatible with provider-confirmed states'
);

select ok(
  not exists (
    select 1
    from information_schema.columns column_row
    where column_row.table_schema = 'content_factory'
      and column_row.table_name = 'auth_email_delivery_events'
      and column_row.column_name in (
        'raw', 'raw_body', 'headers', 'signature', 'secret'
      )
  ),
  'delivery ledger stores no raw webhook body, signature, headers or secret'
);

insert into auth.users (
  id,
  instance_id,
  aud,
  role,
  email,
  encrypted_password,
  email_confirmed_at,
  last_sign_in_at,
  raw_app_meta_data,
  raw_user_meta_data,
  created_at,
  updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  case when fixture.has_signed_in then now() else null end,
  fixture.app_metadata,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    '88000000-0000-4000-8000-000000000001',
    'auth-email-owner@example.test',
    'Auth Email Owner',
    true,
    '{"provider":"email","providers":["email"],"contentengine_password_change_completed":true}'::jsonb
  ),
  (
    '88000000-0000-4000-8000-000000000002',
    'auth-email-ready@example.test',
    'Ready Member',
    true,
    '{"provider":"email","providers":["email"]}'::jsonb
  ),
  (
    '88000000-0000-4000-8000-000000000003',
    'auth-email-password@example.test',
    'Password Member',
    false,
    '{"provider":"email","providers":["email"],"contentengine_password_change_required":true}'::jsonb
  ),
  (
    '88000000-0000-4000-8000-000000000004',
    'auth-email-disabled@example.test',
    'Disabled Member',
    true,
    '{"provider":"email","providers":["email"]}'::jsonb
  ),
  (
    '88000000-0000-4000-8000-000000000005',
    'auth-email-global-outsider@example.test',
    'Global Outsider',
    true,
    '{"provider":"email","providers":["email"]}'::jsonb
  ),
  (
    '88000000-0000-4000-8000-000000000006',
    'auth-email-trainee@example.test',
    'Non Manager',
    true,
    '{"provider":"email","providers":["email"]}'::jsonb
  ),
  (
    '88000000-0000-4000-8000-000000000007',
    'auth-email-other-owner@example.test',
    'Other Owner',
    true,
    '{"provider":"email","providers":["email"]}'::jsonb
  )
) as fixture(
  id, email, display_name, has_signed_in, app_metadata
);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    '88100000-0000-4000-8000-000000000001',
    'Auth Email Main',
    'auth-email-main',
    'active'
  ),
  (
    '88100000-0000-4000-8000-000000000002',
    'Auth Email Other',
    'auth-email-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '88100000-0000-4000-8000-000000000001',
    '88000000-0000-4000-8000-000000000001',
    'owner',
    'active'
  ),
  (
    '88100000-0000-4000-8000-000000000001',
    '88000000-0000-4000-8000-000000000002',
    'operator',
    'active'
  ),
  (
    '88100000-0000-4000-8000-000000000001',
    '88000000-0000-4000-8000-000000000003',
    'trainee',
    'active'
  ),
  (
    '88100000-0000-4000-8000-000000000001',
    '88000000-0000-4000-8000-000000000004',
    'operator',
    'active'
  ),
  (
    '88100000-0000-4000-8000-000000000001',
    '88000000-0000-4000-8000-000000000006',
    'trainee',
    'active'
  ),
  (
    '88100000-0000-4000-8000-000000000002',
    '88000000-0000-4000-8000-000000000007',
    'owner',
    'active'
  );

do $manager_gates$
begin
  perform pg_temp.grant_auth_email_gate(
    '88100000-0000-4000-8000-000000000001',
    '88000000-0000-4000-8000-000000000001',
    'main-owner'
  );
  perform pg_temp.grant_auth_email_gate(
    '88100000-0000-4000-8000-000000000002',
    '88000000-0000-4000-8000-000000000007',
    'other-owner'
  );
end;
$manager_gates$;

update content_factory.profiles
set status = 'suspended'
where id = '88000000-0000-4000-8000-000000000004';

do $claims$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '88000000-0000-4000-8000-000000000001',
    true
  );
end;
$claims$;

create temporary table auth_email_results (
  key text primary key,
  payload jsonb not null
) on commit drop;

insert into auth_email_results (key, payload)
values (
  'reserve',
  public.system_reserve_auth_email_attempt(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'requested_by', '88000000-0000-4000-8000-000000000001',
    'request_id', '88200000-0000-4000-8000-000000000001',
    'requested_at', now(),
    'email', 'Recovery.Target@Example.Test',
    'purpose', 'recovery'
  ))
);

select ok(
  ((select payload from auth_email_results where key = 'reserve')
    ->> 'reserved')::boolean,
  'first server reservation authorizes exactly one outbound send'
);

select is(
  (select payload from auth_email_results where key = 'reserve')
    ->> 'status',
  'reserved',
  'new attempt starts in an explicit reserved state'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000001'
  ),
  1,
  'reservation appends one attempt identity'
);

insert into auth_email_results (key, payload)
values (
  'reserve_replay',
  public.system_reserve_auth_email_attempt(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'requested_by', '88000000-0000-4000-8000-000000000001',
    'request_id', '88200000-0000-4000-8000-000000000001',
    'requested_at', now(),
    'email', 'recovery.target@example.test',
    'purpose', 'recovery'
  ))
);

select ok(
  not (
    ((select payload from auth_email_results where key = 'reserve_replay')
      ->> 'reserved')::boolean
  )
  and (
    ((select payload from auth_email_results where key = 'reserve_replay')
      ->> 'replayed')::boolean
  ),
  'same request id replays without authorizing a duplicate email'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000001'
  ),
  1,
  'idempotent replay never appends a second identity'
);

insert into auth_email_results (key, payload)
values (
  'reserve_suppressed',
  public.system_reserve_auth_email_attempt(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'requested_by', '88000000-0000-4000-8000-000000000001',
    'request_id', '88200000-0000-4000-8000-000000000002',
    'requested_at', now(),
    'email', 'recovery.target@example.test',
    'purpose', 'recovery'
  ))
);

select ok(
  not (
    ((select payload from auth_email_results
      where key = 'reserve_suppressed') ->> 'reserved')::boolean
  ),
  'recent duplicate request is not authorized for another send'
);

select is(
  (select payload from auth_email_results
    where key = 'reserve_suppressed') ->> 'status',
  'suppressed',
  'a new duplicate request remains as explicit audit evidence'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_attempts attempt
    where attempt.email = 'recovery.target@example.test'
      and attempt.purpose = 'recovery'
  ),
  2,
  'duplicate suppression is append-only rather than destructive'
);

select ok(
  exists (
    select 1
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000002'
      and attempt.duplicate_of_attempt_id is not null
      and attempt.finalized_at is not null
  ),
  'suppressed attempt points to the recent protected send'
);

select throws_ok(
  format(
    'select public.system_reserve_auth_email_attempt(%L::jsonb)',
    jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'requested_by', '88000000-0000-4000-8000-000000000006',
      'request_id', '88200000-0000-4000-8000-000000000003',
      'requested_at', now(),
      'email', 'unauthorized@example.test',
      'purpose', 'invite'
    )::text
  ),
  '42501',
  'requester_not_authorized',
  'service RPC still verifies the manager represented by requested_by'
);

insert into auth_email_results (key, payload)
select
  'finalize',
  public.system_finalize_auth_email_attempt(jsonb_build_object(
    'attempt_id', reserve.payload ->> 'attempt_id',
    'request_id', reserve.payload ->> 'request_id',
    'status', 'accepted',
    'reason_code', 'recovery_request_accepted',
    'delivery_status', 'accepted_unconfirmed',
    'membership_provisioned', false
  ))
from auth_email_results reserve
where reserve.key = 'reserve';

select is(
  (select payload from auth_email_results where key = 'finalize')
    ->> 'status',
  'accepted',
  'trusted finalization moves a reservation to accepted'
);

select is(
  (select payload from auth_email_results where key = 'finalize')
    ->> 'delivery_status',
  'accepted_unconfirmed',
  'provider acceptance is not presented as delivery'
);

insert into auth_email_results (key, payload)
select
  'finalize_replay',
  public.system_finalize_auth_email_attempt(jsonb_build_object(
    'attempt_id', reserve.payload ->> 'attempt_id',
    'request_id', reserve.payload ->> 'request_id',
    'status', 'accepted',
    'reason_code', 'recovery_request_accepted',
    'delivery_status', 'accepted_unconfirmed',
    'membership_provisioned', false
  ))
from auth_email_results reserve
where reserve.key = 'reserve';

select ok(
  ((select payload from auth_email_results where key = 'finalize_replay')
    ->> 'replayed')::boolean,
  'identical terminal finalization is idempotent'
);

select throws_ok(
  format(
    'select public.system_finalize_auth_email_attempt(%L::jsonb)',
    jsonb_build_object(
      'attempt_id',
        (select payload ->> 'attempt_id'
         from auth_email_results where key = 'reserve'),
      'request_id', '88200000-0000-4000-8000-000000000001',
      'status', 'failed',
      'reason_code', 'conflicting_terminal_result',
      'delivery_status', 'unknown',
      'membership_provisioned', false
    )::text
  ),
  '55000',
  'email_attempt_already_finalized',
  'conflicting terminal replay is rejected'
);

select throws_ok(
  format(
    'update content_factory.auth_email_attempts set email = %L where id = %L::uuid',
    'changed@example.test',
    (select payload ->> 'attempt_id'
     from auth_email_results where key = 'reserve')
  ),
  '55000',
  'auth_email_attempt_identity_is_immutable',
  'attempt identity cannot be rewritten after reservation'
);

select throws_ok(
  format(
    'delete from content_factory.auth_email_attempts where id = %L::uuid',
    (select payload ->> 'attempt_id'
     from auth_email_results where key = 'reserve')
  ),
  '55000',
  'auth_email_attempts_are_append_only',
  'attempt evidence cannot be deleted'
);

insert into auth_email_results (key, payload)
values (
  'sent_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-sent-0001',
    'provider_message_id', 'msg-recovery-0001',
    'event_type', 'email.sent',
    'delivery_status', 'accepted_unconfirmed',
    'recipient', 'recovery.target@example.test',
    'event_created_at', now()
  ))
);

select is(
  (select payload from auth_email_results where key = 'sent_event')
    ->> 'correlation_basis',
  'unique_recipient_window',
  'first provider sent event binds by the disclosed unique recipient window'
);

insert into auth_email_results (key, payload)
values (
  'delivered_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-delivered-0001',
    'provider_message_id', 'msg-recovery-0001',
    'event_type', 'email.delivered',
    'delivery_status', 'delivered',
    'recipient', 'recovery.target@example.test',
    'event_created_at', now()
  ))
);

select is(
  (select payload from auth_email_results where key = 'delivered_event')
    ->> 'correlation_status',
  'exact',
  'one eligible recipient-window attempt is correlated exactly'
);

select is(
  (select payload from auth_email_results where key = 'delivered_event')
    ->> 'correlation_basis',
  'provider_message_id',
  'later delivered event correlates exactly by the bound provider message id'
);

select ok(
  ((select payload from auth_email_results where key = 'delivered_event')
    ->> 'delivery_projected')::boolean,
  'exact delivery evidence advances the attempt projection'
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.id = (
      select (payload ->> 'attempt_id')::uuid
      from auth_email_results where key = 'reserve'
    )
  ),
  'delivered',
  'provider-delivered is stored distinctly from accepted-unconfirmed'
);

select is(
  (
    select attempt.provider_message_id
    from content_factory.auth_email_attempts attempt
    where attempt.id = (
      select (payload ->> 'attempt_id')::uuid
      from auth_email_results where key = 'reserve'
    )
  ),
  'msg-recovery-0001',
  'first exact event binds the provider message id for future callbacks'
);

select ok(
  not (
    public.system_ingest_auth_email_delivery_event(jsonb_build_object(
      'provider', 'resend',
      'provider_event_id', 'evt-delivered-0001',
      'provider_message_id', 'msg-recovery-0001',
      'event_type', 'email.delivered',
      'delivery_status', 'delivered',
      'recipient', 'recovery.target@example.test',
      'event_created_at', (
        select event.event_created_at
        from content_factory.auth_email_delivery_events event
        where event.provider = 'resend'
          and event.provider_event_id = 'evt-delivered-0001'
      )
    )) ->> 'inserted'
  )::boolean,
  'identical provider replay is acknowledged without another event'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_delivery_events event
    where event.provider = 'resend'
      and event.provider_event_id = 'evt-delivered-0001'
  ),
  1,
  'provider event id is an idempotency key'
);

select throws_ok(
  format(
    'select public.system_ingest_auth_email_delivery_event(%L::jsonb)',
    jsonb_build_object(
      'provider', 'resend',
      'provider_event_id', 'evt-delivered-0001',
      'provider_message_id', 'msg-recovery-0001',
      'event_type', 'email.bounced',
      'delivery_status', 'bounced',
      'recipient', 'recovery.target@example.test',
      'event_created_at', (
        select event.event_created_at
        from content_factory.auth_email_delivery_events event
        where event.provider = 'resend'
          and event.provider_event_id = 'evt-delivered-0001'
      )
    )::text
  ),
  '55000',
  'email_event_replay_conflict',
  'same provider event id cannot be replayed with different facts'
);

insert into auth_email_results (key, payload)
values (
  'deferred_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-deferred-0001',
    'provider_message_id', 'msg-recovery-0001',
    'event_type', 'email.deferred',
    'delivery_status', 'deferred',
    'recipient', 'recovery.target@example.test',
    'event_created_at', now()
  ))
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.id = (
      select (payload ->> 'attempt_id')::uuid
      from auth_email_results where key = 'reserve'
    )
  ),
  'delivered',
  'out-of-order deferred event cannot downgrade delivered'
);

insert into auth_email_results (key, payload)
values (
  'bounced_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-bounced-0001',
    'provider_message_id', 'msg-recovery-0001',
    'event_type', 'email.bounced',
    'delivery_status', 'bounced',
    'recipient', 'recovery.target@example.test',
    'event_created_at', now()
  ))
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.id = (
      select (payload ->> 'attempt_id')::uuid
      from auth_email_results where key = 'reserve'
    )
  ),
  'bounced',
  'terminal bounce advances beyond a prior delivery signal'
);

insert into auth_email_results (key, payload)
values (
  'late_delivered_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-late-delivered-0001',
    'provider_message_id', 'msg-recovery-0001',
    'event_type', 'email.delivered',
    'delivery_status', 'delivered',
    'recipient', 'recovery.target@example.test',
    'event_created_at', now()
  ))
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.id = (
      select (payload ->> 'attempt_id')::uuid
      from auth_email_results where key = 'reserve'
    )
  ),
  'bounced',
  'late lower-rank delivery cannot erase a bounce'
);

insert into auth_email_results (key, payload)
values (
  'complained_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-complained-0001',
    'provider_message_id', 'msg-recovery-0001',
    'event_type', 'email.complained',
    'delivery_status', 'complained',
    'recipient', 'recovery.target@example.test',
    'event_created_at', now()
  ))
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.id = (
      select (payload ->> 'attempt_id')::uuid
      from auth_email_results where key = 'reserve'
    )
  ),
  'complained',
  'complaint is the strongest terminal projection'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_delivery_events event
    where event.provider_message_id = 'msg-recovery-0001'
  ),
  6,
  'all distinct provider facts remain append-only evidence'
);

select throws_ok(
  $$update content_factory.auth_email_delivery_events
      set delivery_status = 'unknown'
      where provider = 'resend'
        and provider_event_id = 'evt-delivered-0001'$$,
  '55000',
  'auth_email_delivery_events_are_append_only',
  'provider evidence cannot be updated'
);

select throws_ok(
  $$delete from content_factory.auth_email_delivery_events
      where provider = 'resend'
        and provider_event_id = 'evt-delivered-0001'$$,
  '55000',
  'auth_email_delivery_events_are_append_only',
  'provider evidence cannot be deleted'
);

select throws_ok(
  format(
    'update content_factory.auth_email_attempts set delivery_status = %L where id = %L::uuid',
    'delivered',
    (select payload ->> 'attempt_id'
     from auth_email_results where key = 'reserve')
  ),
  '55000',
  'auth_email_delivery_projection_cannot_regress',
  'direct projection writes cannot bypass monotonic delivery'
);

select throws_ok(
  format(
    'update content_factory.auth_email_attempts set status = %L where id = %L::uuid',
    'failed',
    (select payload ->> 'attempt_id'
     from auth_email_results where key = 'reserve')
  ),
  '55000',
  'auth_email_attempt_is_finalized',
  'terminal attempt status is immutable'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values
  (
    '88100000-0000-4000-8000-000000000001',
    '88200000-0000-4000-8000-000000000010',
    'ambiguous@example.test',
    'invite',
    'accepted',
    'invite_request_accepted',
    'accepted_unconfirmed',
    '88000000-0000-4000-8000-000000000001',
    now(),
    now()
  ),
  (
    '88100000-0000-4000-8000-000000000001',
    '88200000-0000-4000-8000-000000000011',
    'ambiguous@example.test',
    'recovery',
    'accepted',
    'recovery_request_accepted',
    'accepted_unconfirmed',
    '88000000-0000-4000-8000-000000000001',
    now(),
    now()
  );

insert into auth_email_results (key, payload)
values (
  'ambiguous_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-ambiguous-0001',
    'event_type', 'email.delivered',
    'delivery_status', 'delivered',
    'recipient', 'ambiguous@example.test',
    'event_created_at', now()
  ))
);

select is(
  (select payload from auth_email_results where key = 'ambiguous_event')
    ->> 'correlation_status',
  'ambiguous',
  'multiple eligible attempts are reported as ambiguous'
);

select ok(
  (select payload from auth_email_results where key = 'ambiguous_event')
    -> 'attempt_id' = 'null'::jsonb,
  'ambiguous event is not attached to an arbitrary attempt'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_attempts attempt
    where attempt.email = 'ambiguous@example.test'
      and attempt.delivery_status = 'accepted_unconfirmed'
  ),
  2,
  'ambiguous evidence never changes either candidate projection'
);

insert into auth_email_results (key, payload)
values (
  'unmatched_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-unmatched-0001',
    'provider_message_id', 'msg-unmatched-0001',
    'event_type', 'email.bounced',
    'delivery_status', 'bounced',
    'recipient', 'no-attempt@example.test',
    'event_created_at', now()
  ))
);

select is(
  (select payload from auth_email_results where key = 'unmatched_event')
    ->> 'correlation_status',
  'unmatched',
  'provider evidence without a candidate remains unmatched'
);

select ok(
  (select payload from auth_email_results where key = 'unmatched_event')
    -> 'attempt_id' = 'null'::jsonb,
  'unmatched evidence does not pretend to identify an account attempt'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000012',
  'provider-terminal@example.test',
  'invite',
  'accepted',
  'invite_request_accepted',
  'accepted_unconfirmed',
  '88000000-0000-4000-8000-000000000001',
  now(),
  now()
);

insert into auth_email_results (key, payload)
values (
  'provider_failed_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-provider-failed-0001',
    'provider_message_id', 'msg-provider-terminal-0001',
    'event_type', 'email.failed',
    'delivery_status', 'failed',
    'recipient', 'provider-terminal@example.test',
    'event_created_at', now()
  ))
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.email = 'provider-terminal@example.test'
  ),
  'failed',
  'generic provider failure is not mislabeled as a recipient bounce'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'provider-terminal@example.test'
  )) ->> 'recommended_action',
  'manual_review',
  'generic provider failure blocks blind automatic resend'
);

insert into auth_email_results (key, payload)
values (
  'provider_suppressed_event',
  public.system_ingest_auth_email_delivery_event(jsonb_build_object(
    'provider', 'resend',
    'provider_event_id', 'evt-provider-suppressed-0001',
    'provider_message_id', 'msg-provider-terminal-0001',
    'event_type', 'email.suppressed',
    'delivery_status', 'suppressed',
    'recipient', 'provider-terminal@example.test',
    'event_created_at', now()
  ))
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.email = 'provider-terminal@example.test'
  ),
  'suppressed',
  'provider suppression is a distinct terminal state'
);

insert into content_factory.invite_delivery_attempts (
  organization_id,
  request_id,
  email,
  status,
  reason_code,
  delivery_status,
  membership_provisioned,
  requested_by,
  requested_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000020',
  'legacy.bulk@example.test',
  'pending_verification',
  'invite_processing_started',
  'unknown',
  false,
  '88000000-0000-4000-8000-000000000001',
  now()
);

select is(
  (
    select attempt.status
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000020'
      and attempt.purpose = 'invite'
  ),
  'reserved',
  'legacy pre-journal reservation is mirrored immediately'
);

update content_factory.invite_delivery_attempts
set
  status = 'invited',
  reason_code = 'invite_request_accepted',
  delivery_status = 'accepted_unconfirmed'
where request_id = '88200000-0000-4000-8000-000000000020';

select is(
  (
    select attempt.status
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000020'
      and attempt.purpose = 'invite'
  ),
  'accepted',
  'legacy final result finalizes the same mirrored attempt'
);

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000020'
      and attempt.purpose = 'invite'
  ),
  'accepted_unconfirmed',
  'legacy accepted result remains honestly unconfirmed'
);

update content_factory.invite_delivery_attempts
set delivery_status = 'delivered'
where request_id = '88200000-0000-4000-8000-000000000020';

select is(
  (
    select attempt.delivery_status
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000020'
      and attempt.purpose = 'invite'
  ),
  'delivered',
  'future legacy provider projection advances the normalized mirror'
);

select is(
  (
    select count(*)::integer
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000020'
      and attempt.purpose = 'invite'
  ),
  1,
  'legacy pre/final updates never create duplicate normalized attempts'
);

insert into content_factory.invite_delivery_attempts (
  organization_id,
  request_id,
  email,
  status,
  reason_code,
  delivery_status,
  membership_provisioned,
  requested_by,
  requested_at
)
values
  (
    '88100000-0000-4000-8000-000000000001',
    '88200000-0000-4000-8000-000000000021',
    'legacy.duplicate@example.test',
    'pending_verification',
    'invite_processing_started',
    'unknown',
    false,
    '88000000-0000-4000-8000-000000000001',
    now()
  ),
  (
    '88100000-0000-4000-8000-000000000001',
    '88200000-0000-4000-8000-000000000022',
    'legacy.duplicate@example.test',
    'pending_verification',
    'duplicate_request_suppressed',
    'unknown',
    false,
    '88000000-0000-4000-8000-000000000001',
    now()
  );

select is(
  (
    select attempt.status
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000022'
  ),
  'suppressed',
  'legacy duplicate reservation mirrors as suppressed rather than failed'
);

select ok(
  exists (
    select 1
    from content_factory.auth_email_attempts attempt
    where attempt.request_id =
      '88200000-0000-4000-8000-000000000022'
      and attempt.duplicate_of_attempt_id is not null
  ),
  'live legacy duplicate mirror retains the protected prior attempt'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'legacy.duplicate@example.test'
  )) ->> 'recommended_action',
  'wait',
  'suppressed legacy duplicate preserves wait/cooldown guidance'
);

create temporary table authenticated_access_result (
  payload jsonb not null
) on commit drop;
grant insert on authenticated_access_result to authenticated;

set local role authenticated;
insert into authenticated_access_result (payload)
select public.creator_account_access_status(jsonb_build_object(
  'organization_id', '88100000-0000-4000-8000-000000000001',
  'email', 'auth-email-ready@example.test'
));
reset role;

select ok(
  ((select payload from authenticated_access_result limit 1)
    ->> 'ok')::boolean,
  'certified owner executes access diagnosis under authenticated role'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-ready@example.test'
  )) ->> 'account_state',
  'ready',
  'active confirmed signed-in member is ready'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-ready@example.test'
  )) ->> 'recommended_action',
  'none',
  'healthy account does not receive an unnecessary recovery action'
);

select ok(
  (
    public.creator_account_access_status(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'email', 'auth-email-ready@example.test'
    )) #>> '{identity,exists}'
  )::boolean
  and not (
    public.creator_account_access_status(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'email', 'auth-email-ready@example.test'
    )) -> 'membership' ?| array['id', 'profile_id']
  ),
  'org member diagnosis exposes state without internal Auth identifiers'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000029',
  'auth-email-ready@example.test',
  'recovery',
  'accepted',
  'historical_recovery_request',
  'bounced',
  '88000000-0000-4000-8000-000000000001',
  now() - interval '1 day',
  now() - interval '1 day'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-ready@example.test'
  )) ->> 'account_state',
  'ready',
  'a completed successful login outranks an old bounced recovery email'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-ready@example.test'
  )) ->> 'recommended_action',
  'none',
  'historical delivery failure does not permanently disable a healthy member'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000031',
  'auth-email-password@example.test',
  'invite',
  'accepted',
  'historical_invite_request',
  'accepted_unconfirmed',
  '88000000-0000-4000-8000-000000000001',
  now() - interval '2 hours',
  now() - interval '2 hours'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'account_state',
  'recovery_required',
  'temporary-password member is diagnosed for recovery after an old link'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'recommended_action',
  'recovery',
  'expired invitation does not block the one-click recovery action'
);

select ok(
  (
    public.creator_account_access_status(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'email', 'auth-email-password@example.test'
    )) #>> '{identity,password_change_required}'
  )::boolean,
  'server helper exposes the unresolved password marker to its manager'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000032',
  'auth-email-password@example.test',
  'invite',
  'accepted',
  'invite_request_accepted',
  'accepted_unconfirmed',
  '88000000-0000-4000-8000-000000000001',
  now(),
  now()
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'account_state',
  'pending_delivery',
  'fresh invitation to a provisioned member remains pending'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'recommended_action',
  'wait',
  'fresh invitation is not immediately replaced by a recovery email'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000030',
  'auth-email-password@example.test',
  'recovery',
  'accepted',
  'recovery_request_accepted',
  'bounced',
  '88000000-0000-4000-8000-000000000001',
  now(),
  now()
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'account_state',
  'disabled',
  'member with terminal delivery failure is fail-closed'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'recommended_action',
  'manual_review',
  'repair API cannot blindly resend to a bounced member address'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at,
  duplicate_of_attempt_id
)
select
  original.organization_id,
  '88200000-0000-4000-8000-000000000033',
  original.email,
  original.purpose,
  'suppressed',
  'duplicate_request_suppressed',
  'unknown',
  original.requested_by,
  now() + interval '1 second',
  now() + interval '1 second',
  original.id
from content_factory.auth_email_attempts original
where original.request_id = '88200000-0000-4000-8000-000000000030';

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'account_state',
  'disabled',
  'a suppressed duplicate cannot hide the original terminal bounce'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-password@example.test'
  )) ->> 'recommended_action',
  'manual_review',
  'duplicate suppression never re-enables a terminal recipient address'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-disabled@example.test'
  )) ->> 'account_state',
  'disabled',
  'suspended org profile is diagnosed as disabled'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-disabled@example.test'
  )) ->> 'recommended_action',
  'manual_review',
  'disabled account cannot be blindly recovered'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-global-outsider@example.test'
  )) ->> 'account_state',
  'invite_required',
  'email outside the organization is handled as a new invite'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-global-outsider@example.test'
  )) ->> 'recommended_action',
  'invite',
  'non-member receives only the safe invite action'
);

insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  requested_by,
  requested_at,
  finalized_at
)
values (
  '88100000-0000-4000-8000-000000000001',
  '88200000-0000-4000-8000-000000000034',
  'auth-email-stale-outsider@example.test',
  'invite',
  'accepted',
  'historical_invite_request',
  'accepted_unconfirmed',
  '88000000-0000-4000-8000-000000000001',
  now() - interval '2 hours',
  now() - interval '2 hours'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-stale-outsider@example.test'
  )) ->> 'account_state',
  'invite_required',
  'an expired invite without membership becomes repairable again'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'auth-email-stale-outsider@example.test'
  )) ->> 'recommended_action',
  'invite',
  'an old incomplete invitation does not remain waiting forever'
);

select ok(
  not (
    public.creator_account_access_status(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'email', 'auth-email-global-outsider@example.test'
    )) #>> '{membership,exists}'
  )::boolean,
  'global Auth identity is not disclosed as an organization member'
);

select ok(
  not (
    public.creator_account_access_status(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'email', 'auth-email-global-outsider@example.test'
    )) #>> '{identity,exists}'
  )::boolean,
  'status RPC cannot enumerate global Auth users outside the organization'
);

select ok(
  not (
    public.creator_account_access_status(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001',
      'email', 'auth-email-global-outsider@example.test'
    )) ? 'auth'
  ),
  'status response has no legacy raw auth object'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'legacy.bulk@example.test'
  )) ->> 'account_state',
  'pending_delivery',
  'delivered invite without membership remains pending acceptance'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'legacy.bulk@example.test'
  )) ->> 'recommended_action',
  'wait',
  'recent delivered invite is not sent repeatedly'
);

select is(
  public.creator_account_access_status(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001',
    'email', 'legacy.bulk@example.test'
  )) #>> '{delivery,delivery_status}',
  'delivered',
  'manager sees provider delivery rather than only request acceptance'
);

do $non_manager$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '88000000-0000-4000-8000-000000000006',
    true
  );
end;
$non_manager$;

select throws_ok(
  $$select public.creator_account_access_status(
      '{"organization_id":"88100000-0000-4000-8000-000000000001","email":"auth-email-ready@example.test"}'::jsonb
    )$$,
  '42501',
  'role_not_allowed',
  'non-manager cannot inspect account access'
);

do $main_owner$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '88000000-0000-4000-8000-000000000001',
    true
  );
end;
$main_owner$;

select throws_ok(
  $$select public.creator_account_access_status(
      '{"organization_id":"88100000-0000-4000-8000-000000000002","email":"auth-email-other-owner@example.test"}'::jsonb
    )$$,
  '42501',
  'active_membership_required',
  'manager cannot inspect another organization'
);

update auth.users
set raw_app_meta_data = raw_app_meta_data ||
  '{"contentengine_password_change_required":true}'::jsonb
where id = '88000000-0000-4000-8000-000000000001';

select ok(
  content_factory_private.auth_password_change_required(
    '88000000-0000-4000-8000-000000000001'
  ),
  'explicit required marker wins even if completion existed previously'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001'
  )) ->> 'state',
  'password_change_required',
  'bootstrap returns an explicit password-change state'
);

select ok(
  not (
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001'
    )) ->> 'workspace_open'
  )::boolean,
  'temporary password closes workspace at the database boundary'
);

select ok(
  not (
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001'
    )) #>> '{capabilities,real_generation}'
  )::boolean,
  'temporary password disables paid generation capability'
);

select ok(
  not (
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001'
    )) #>> '{capabilities,team_view}'
  )::boolean,
  'temporary password disables manager workspace capability'
);

update auth.users
set raw_app_meta_data = (
  raw_app_meta_data - 'contentengine_password_change_required'
) || '{"contentengine_password_change_completed":true}'::jsonb
where id = '88000000-0000-4000-8000-000000000001';

select ok(
  not content_factory_private.auth_password_change_required(
    '88000000-0000-4000-8000-000000000001'
  ),
  'completion marker clears the server-side password gate'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '88100000-0000-4000-8000-000000000001'
  )) ->> 'state',
  'workspace',
  'completed password change restores the prior audited bootstrap state'
);

select ok(
  (
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '88100000-0000-4000-8000-000000000001'
    )) ->> 'workspace_open'
  )::boolean,
  'completed password change allows a fully certified workspace'
);

select * from finish();
rollback;

begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(31);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname = 'system_provision_limited_member'
      and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb'
  ),
  1,
  'limited-member RPC exposes exactly p_payload jsonb'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_provision_limited_member(jsonb)',
    'execute'
  ),
  'service_role can provision limited members'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_provision_limited_member(jsonb)',
    'execute'
  ),
  'authenticated cannot provision limited members'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.system_provision_limited_member(jsonb)',
    'execute'
  ),
  'anon cannot provision limited members'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, banned_until, deleted_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  case when fixture.confirmed then now() end,
  case when fixture.banned then now() + interval '1 day' end,
  case when fixture.deleted then now() end,
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  ('71111111-1111-4111-8111-111111111111', 'limited-owner@example.test', true, false, false, 'Limited Owner'),
  ('71222222-2222-4222-8222-222222222222', 'limited-admin@example.test', true, false, false, 'Limited Admin'),
  ('71333333-3333-4333-8333-333333333333', 'limited-producer@example.test', true, false, false, 'Limited Producer'),
  ('72111111-1111-4211-8211-111111111111', 'guest-viewer@example.test', true, false, false, 'Guest Viewer'),
  ('72222222-2222-4222-8222-222222222222', 'guest-trainee@example.test', true, false, false, 'Guest Trainee'),
  ('72333333-3333-4233-8233-333333333333', 'role-conflict@example.test', true, false, false, 'Role Conflict'),
  ('72444444-4444-4244-8244-444444444444', 'history-conflict@example.test', true, false, false, 'History Conflict'),
  ('72555555-5555-4255-8255-555555555555', 'unconfirmed@example.test', false, false, false, 'Unconfirmed Target'),
  ('72666666-6666-4266-8266-666666666666', 'deleted@example.test', true, false, true, 'Deleted Target'),
  ('72777777-7777-4277-8277-777777777777', 'banned@example.test', true, true, false, 'Banned Target'),
  ('72888888-8888-4288-8288-888888888888', 'inactive-profile@example.test', true, false, false, 'Inactive Profile'),
  ('72999999-9999-4299-8299-999999999999', 'free-target@example.test', true, false, false, 'Free Target')
) as fixture(id, email, confirmed, banned, deleted, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  '70000000-0000-4000-8000-000000000001',
  'Limited Member Test',
  'limited-member-test',
  'active'
);

insert into content_factory.profiles (id, email, display_name, status)
values
  ('71111111-1111-4111-8111-111111111111', 'limited-owner@example.test', 'Limited Owner', 'active'),
  ('71222222-2222-4222-8222-222222222222', 'limited-admin@example.test', 'Limited Admin', 'active'),
  ('71333333-3333-4333-8333-333333333333', 'limited-producer@example.test', 'Limited Producer', 'active'),
  ('72222222-2222-4222-8222-222222222222', 'stale-trainee@example.test', null, 'active'),
  ('72333333-3333-4233-8233-333333333333', 'role-conflict@example.test', 'Role Conflict', 'active'),
  ('72444444-4444-4244-8244-444444444444', 'history-conflict@example.test', 'History Conflict', 'active'),
  ('72888888-8888-4288-8288-888888888888', 'inactive-profile@example.test', 'Inactive Profile', 'suspended')
on conflict (id) do update set
  email = excluded.email,
  display_name = excluded.display_name,
  status = excluded.status,
  updated_at = now();

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('70000000-0000-4000-8000-000000000001', '71111111-1111-4111-8111-111111111111', 'owner', 'active'),
  ('70000000-0000-4000-8000-000000000001', '71222222-2222-4222-8222-222222222222', 'admin', 'active'),
  ('70000000-0000-4000-8000-000000000001', '71333333-3333-4333-8333-333333333333', 'producer', 'active'),
  ('70000000-0000-4000-8000-000000000001', '72222222-2222-4222-8222-222222222222', 'trainee', 'active'),
  ('70000000-0000-4000-8000-000000000001', '72333333-3333-4233-8233-333333333333', 'trainee', 'active'),
  ('70000000-0000-4000-8000-000000000001', '72444444-4444-4244-8244-444444444444', 'viewer', 'suspended');

select is(
  (
    select count(*)::integer
    from content_factory.training_certifications
    where profile_id = '71111111-1111-4111-8111-111111111111'
  ),
  0,
  'owner needs no exam certification for limited provisioning'
);

create temporary table limited_member_context (
  initial_response jsonb,
  replay_response jsonb
) on commit drop;

insert into limited_member_context (initial_response)
values (public.system_provision_limited_member(jsonb_build_object(
  'organization_id', '70000000-0000-4000-8000-000000000001',
  'user_id', '72111111-1111-4211-8211-111111111111',
  'provisioned_by', '71111111-1111-4111-8111-111111111111',
  'role', 'viewer',
  'idempotency_key', 'ignored-caller-key'
)));

update limited_member_context
set replay_response = public.system_provision_limited_member(jsonb_build_object(
  'organization_id', '70000000-0000-4000-8000-000000000001',
  'user_id', '72111111-1111-4211-8211-111111111111',
  'provisioned_by', '71111111-1111-4111-8111-111111111111',
  'role', 'viewer',
  'idempotency_key', 'a-different-ignored-key'
));

select ok(
  (select (initial_response ->> 'ok')::boolean from limited_member_context),
  'confirmed Auth user is provisioned as a limited member'
);

select is(
  (select initial_response ->> 'role' from limited_member_context),
  'viewer',
  'viewer is preserved as the requested role'
);

select is(
  (select email from content_factory.profiles where id = '72111111-1111-4211-8211-111111111111'),
  'guest-viewer@example.test',
  'provisioning creates an active normalized profile'
);

select is(
  (select initial_response::text from limited_member_context),
  (select replay_response::text from limited_member_context),
  'derived idempotency ignores caller keys and returns the stable result'
);

select is(
  (select count(*)::integer from content_factory.memberships where profile_id = '72111111-1111-4211-8211-111111111111'),
  1,
  'idempotent replay never duplicates membership'
);

select is(
  (select count(*)::integer from content_factory.factory_events where event_name = 'limited_member_provisioned' and properties ->> 'target_user_id' = '72111111-1111-4211-8211-111111111111'),
  1,
  'idempotent replay emits one system audit event'
);

select is(
  (select count(*)::integer from content_factory.command_receipts where command_name = 'system_provision_limited_member' and result ->> 'user_id' = '72111111-1111-4211-8211-111111111111'),
  1,
  'idempotent replay stores one command receipt'
);

select ok(
  (public.system_provision_limited_member(jsonb_build_object(
    'organization_id', '70000000-0000-4000-8000-000000000001',
    'user_id', '72222222-2222-4222-8222-222222222222',
    'provisioned_by', '71222222-2222-4222-8222-222222222222',
    'role', 'trainee'
  )) ->> 'already_active')::boolean,
  'same active trainee role is idempotently accepted by an uncertified admin'
);

select is(
  (select email from content_factory.profiles where id = '72222222-2222-4222-8222-222222222222'),
  'guest-trainee@example.test',
  'existing active profile is refreshed from Auth'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72333333-3333-4233-8233-333333333333","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '23505', 'target_membership_role_conflict',
  'an active role mismatch fails closed'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72444444-4444-4244-8244-444444444444","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '23505', 'target_membership_history_conflict',
  'inactive membership history is never restored'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72999999-9999-4299-8299-999999999999","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"operator"}'::jsonb)$$,
  '22023', 'limited_member_role_invalid',
  'only viewer and trainee roles are accepted'
);

update content_factory.organizations set status = 'suspended' where id = '70000000-0000-4000-8000-000000000001';
select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72999999-9999-4299-8299-999999999999","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '42501', 'organization_not_active', 'inactive organization is rejected'
);
update content_factory.organizations set status = 'active' where id = '70000000-0000-4000-8000-000000000001';

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72555555-5555-4255-8255-555555555555","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '42501', 'target_email_not_confirmed', 'unconfirmed target is rejected'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72666666-6666-4266-8266-666666666666","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '42501', 'target_auth_user_not_active', 'deleted target is rejected'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72777777-7777-4277-8277-777777777777","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '42501', 'target_auth_user_not_active', 'currently banned target is rejected'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"79999999-9999-4999-8999-999999999999","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  'P0002', 'target_auth_user_not_found', 'missing Auth target is rejected'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72888888-8888-4288-8288-888888888888","provisioned_by":"71111111-1111-4111-8111-111111111111","role":"viewer"}'::jsonb)$$,
  '42501', 'target_profile_not_active', 'inactive target profile is rejected'
);

select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72999999-9999-4299-8299-999999999999","provisioned_by":"71333333-3333-4333-8333-333333333333","role":"viewer"}'::jsonb)$$,
  '42501', 'provisioner_not_authorized', 'non-owner/admin provisioner is rejected'
);

update content_factory.profiles set status = 'suspended' where id = '71222222-2222-4222-8222-222222222222';
select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72999999-9999-4299-8299-999999999999","provisioned_by":"71222222-2222-4222-8222-222222222222","role":"viewer"}'::jsonb)$$,
  '42501', 'provisioner_not_authorized', 'inactive provisioner profile is rejected'
);
update content_factory.profiles set status = 'active' where id = '71222222-2222-4222-8222-222222222222';

update auth.users set banned_until = now() + interval '1 day' where id = '71222222-2222-4222-8222-222222222222';
select throws_ok(
  $$select public.system_provision_limited_member('{"organization_id":"70000000-0000-4000-8000-000000000001","user_id":"72999999-9999-4299-8299-999999999999","provisioned_by":"71222222-2222-4222-8222-222222222222","role":"viewer"}'::jsonb)$$,
  '42501', 'provisioner_not_authorized', 'banned provisioner Auth identity is rejected'
);
update auth.users set banned_until = null where id = '71222222-2222-4222-8222-222222222222';

with inserted_attempts as (
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  )
  select
    '70000000-0000-4000-8000-000000000001'::uuid,
    fixture.profile_id::uuid,
    'operator_final_exam', 'completed', 1, 12, 12, 12, true,
    '{}'::jsonb, repeat(fixture.hash_char, 64), fixture.idempotency_key
  from (values
    ('71111111-1111-4111-8111-111111111111', 'a', 'limited-owner-exam-0001'),
    ('72111111-1111-4211-8211-111111111111', 'b', 'limited-viewer-exam-0001')
  ) as fixture(profile_id, hash_char, idempotency_key)
  returning id, organization_id, profile_id, module_code
)
insert into content_factory.training_certifications (
  organization_id, profile_id, module_code, attempt_id, status
)
select organization_id, profile_id, module_code, id, 'passed'
from inserted_attempts;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '72111111-1111-4211-8211-111111111111',
    true
  );
end;
$$;

select ok(
  not content_factory.storage_access_allowed('70000000-0000-4000-8000-000000000001', '72111111-1111-4211-8211-111111111111', false),
  'certified viewer cannot mutate even their own Storage path'
);

select ok(
  content_factory.storage_access_allowed('70000000-0000-4000-8000-000000000001', '72111111-1111-4211-8211-111111111111', true),
  'certified viewer retains read access to their own Storage path'
);

select ok(
  not content_factory.storage_access_allowed('70000000-0000-4000-8000-000000000001', '71111111-1111-4111-8111-111111111111', true),
  'viewer does not gain manager team-read access'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '71111111-1111-4111-8111-111111111111',
    true
  );
end;
$$;

select ok(
  content_factory.storage_access_allowed('70000000-0000-4000-8000-000000000001', '71111111-1111-4111-8111-111111111111', false),
  'certified owner retains Storage mutation access'
);

select ok(
  content_factory.storage_access_allowed('70000000-0000-4000-8000-000000000001', '72111111-1111-4211-8211-111111111111', true),
  'certified owner retains existing team-read access'
);

select * from finish();
rollback;

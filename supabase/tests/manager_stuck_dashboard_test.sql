begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

-- TEST-ONLY fixture matching membership_role(..., true, ...): every active
-- course needs a completed server-style attempt plus a current certificate.
create or replace function pg_temp.grant_manager_dashboard_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $course_gate_fixture$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
  answers_value jsonb;
begin
  for module_row in
    select
      module.code,
      jsonb_array_length(module.content #> '{knowledge_check,questions}') as question_count
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
    order by module.order_index
  loop
    select coalesce(
      jsonb_object_agg(
        question.code,
        answer_key.correct_answers
        order by question.order_index
      ),
      '{}'::jsonb
    )
    into answers_value
    from content_factory.training_questions question
    join content_factory_private.training_answer_keys answer_key
      on answer_key.question_code = question.code
    where question.module_code = module_row.code
      and question.order_index between 901 and 1000
      and strpos(question.code, 'course_check_' || module_row.code || '_') = 1;

    insert into content_factory.training_attempts (
      organization_id, profile_id, module_code, status, score,
      correct_count, answered_count, question_count, passed, answers,
      request_hash, idempotency_key
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
      answers_value,
      content_factory_private.json_hash(jsonb_build_object(
        'module_code', module_row.code,
        'answers', answers_value
      )),
      left('course-check:' || p_key_prefix || ':' || module_row.code, 180)
    )
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      attempt_id_value,
      'passed'
    );
  end loop;

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
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
    repeat('a', 64),
    left('manager-exam:' || p_key_prefix, 180)
  )
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    p_organization_id,
    p_profile_id,
    'operator_final_exam',
    attempt_id_value,
    'passed'
  );
end;
$course_gate_fixture$;

select plan(32);

select has_function(
  'public',
  'creator_manager_dashboard',
  array['jsonb'],
  'manager funnel RPC exists'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_manager_dashboard(jsonb)',
    'execute'
  ),
  'authenticated may execute the manager dashboard RPC'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_manager_dashboard(jsonb)',
    'execute'
  ),
  'anonymous callers cannot execute the manager dashboard RPC'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, last_sign_in_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  ('77777777-7777-4777-8777-777777777777', 'manager-dashboard-owner@example.test', 'Dashboard Owner'),
  ('77777777-7777-4777-8777-777777777771', 'manager-dashboard-task@example.test', 'Task Operator'),
  ('77777777-7777-4777-8777-777777777772', 'manager-dashboard-profile-access@example.test', 'Profile Access'),
  ('77777777-7777-4777-8777-777777777773', 'manager-dashboard-auth-access@example.test', 'Auth Access'),
  ('77777777-7777-4777-8777-777777777774', 'manager-dashboard-placement@example.test', 'Placement Operator'),
  ('77777777-7777-4777-8777-777777777775', 'manager-dashboard-trainee@example.test', 'Dashboard Trainee'),
  ('77777777-7777-4777-8777-777777777776', 'manager-dashboard-stale-course@example.test', 'Stale Course Operator')
) as fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('77000000-0000-4000-8000-000000000001', 'Manager Dashboard Main', 'manager-dashboard-main', 'active'),
  ('77000000-0000-4000-8000-000000000002', 'Manager Dashboard Other', 'manager-dashboard-other', 'active');

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777777', 'owner', 'active'),
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777771', 'operator', 'active'),
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777772', 'trainee', 'active'),
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777773', 'trainee', 'active'),
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777774', 'operator', 'active'),
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777775', 'trainee', 'active'),
  ('77000000-0000-4000-8000-000000000001', '77777777-7777-4777-8777-777777777776', 'operator', 'active');

do $$
declare
  fixture record;
begin
  for fixture in
    select *
    from (values
      ('77777777-7777-4777-8777-777777777777'::uuid, 'dashboard-owner'),
      ('77777777-7777-4777-8777-777777777771'::uuid, 'dashboard-task'),
      ('77777777-7777-4777-8777-777777777774'::uuid, 'dashboard-placement')
    ) as certified_profile(profile_id, key_prefix)
  loop
    perform pg_temp.grant_manager_dashboard_gate(
      '77000000-0000-4000-8000-000000000001',
      fixture.profile_id,
      fixture.key_prefix
    );
  end loop;
end;
$$;

-- A legacy certificate without the server course-check namespace must not count.
do $$
declare
  module_row record;
  attempt_id_value uuid;
begin
  for module_row in
    select
      module.code,
      jsonb_array_length(module.content #> '{knowledge_check,questions}') as question_count
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
  loop
    insert into content_factory.training_attempts (
      organization_id, profile_id, module_code, status, score,
      correct_count, answered_count, question_count, passed, answers,
      request_hash, idempotency_key
    ) values (
      '77000000-0000-4000-8000-000000000001',
      '77777777-7777-4777-8777-777777777776',
      module_row.code,
      'completed',
      1,
      module_row.question_count,
      module_row.question_count,
      module_row.question_count,
      true,
      '{}'::jsonb,
      repeat('6', 64),
      left('legacy-course:' || module_row.code, 180)
    ) returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      '77000000-0000-4000-8000-000000000001',
      '77777777-7777-4777-8777-777777777776',
      module_row.code,
      attempt_id_value,
      'passed'
    );
  end loop;
end;
$$;

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values (
  '77000000-0000-4000-8000-000000000010',
  '77000000-0000-4000-8000-000000000001',
  'MANAGER-DASHBOARD-SKU',
  'Manager dashboard fixture product',
  'active',
  '77777777-7777-4777-8777-777777777777'
);

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '77777777-7777-4777-8777-777777777777',
    true
  );
end;
$$;

create or replace function pg_temp.manager_dashboard_result()
returns jsonb
language sql
stable
set search_path = ''
as $$
  select public.creator_manager_dashboard(jsonb_build_object(
    'organization_id', '77000000-0000-4000-8000-000000000001'
  ));
$$;

create or replace function pg_temp.manager_dashboard_member(p_email text)
returns jsonb
language sql
stable
set search_path = ''
as $$
  select member.value
  from jsonb_array_elements(
    pg_temp.manager_dashboard_result() -> 'members'
  ) as member(value)
  where member.value ->> 'email' = p_email
  limit 1;
$$;

create temporary table manager_authenticated_call (
  payload jsonb not null
) on commit drop;
grant insert on manager_authenticated_call to authenticated;

set local role authenticated;
insert into manager_authenticated_call (payload)
select public.creator_manager_dashboard(
    '{"organization_id":"77000000-0000-4000-8000-000000000001"}'::jsonb
  );
reset role;

select ok(
  ((select payload from manager_authenticated_call limit 1) ->> 'ok')::boolean,
  'a certified owner executes the RPC under the authenticated database role'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-owner@example.test') ->> 'stage',
  'ready',
  'fully certified owner with no active work is ready'
);

select is(
  jsonb_array_length(pg_temp.manager_dashboard_result() -> 'pending_invites'),
  0,
  'empty invite aggregates return an array rather than null'
);

update auth.users
set raw_app_meta_data = raw_app_meta_data ||
  '{"contentengine_password_change_required":true}'::jsonb
where id = '77777777-7777-4777-8777-777777777777';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-owner@example.test') ->> 'reason_code',
  'temporary_password_change_required',
  'the current temporary-password marker is a login blocker'
);

update auth.users
set raw_app_meta_data = (
  raw_app_meta_data
  - 'contentengine_password_change_required'
  - 'contentengine_password_change_completed'
  - 'contentengine_owner_password_reset_once_20260714'
) || '{"contentengine_github_member_provisioned":true}'::jsonb
where id = '77777777-7777-4777-8777-777777777777';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-owner@example.test') ->> 'reason_code',
  'temporary_password_change_required',
  'an unresolved legacy provisioning marker remains a login blocker'
);

update auth.users
set raw_app_meta_data = raw_app_meta_data ||
  '{"contentengine_password_change_completed":true}'::jsonb
where id = '77777777-7777-4777-8777-777777777777';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-owner@example.test') ->> 'stage',
  'ready',
  'the completion marker suppresses legacy password markers'
);

update auth.users
set raw_app_meta_data = raw_app_meta_data
  - 'contentengine_github_member_provisioned'
  - 'contentengine_password_change_completed'
where id = '77777777-7777-4777-8777-777777777777';

insert into content_factory.invite_delivery_attempts (
  organization_id, request_id, email, status, reason_code, delivery_status,
  membership_provisioned, requested_by, requested_at
)
values (
  '77000000-0000-4000-8000-000000000001',
  '77888888-8888-4888-8888-888888888888',
  'pending-creator@example.test',
  'invited',
  'invite_request_accepted',
  'accepted_unconfirmed',
  false,
  '77777777-7777-4777-8777-777777777777',
  now()
);

select is(
  (pg_temp.manager_dashboard_result() #>> '{summary,email}')::integer,
  1,
  'an invite without membership is counted at the email stage'
);

select is(
  pg_temp.manager_dashboard_result() #>> '{pending_invites,0,safe_action}',
  'wait_for_delivery',
  'accepted but unconfirmed delivery exposes only a safe wait action'
);

select ok(
  not ((pg_temp.manager_dashboard_result() #> '{pending_invites,0}') ? 'request_id'),
  'pending invite output does not expose an internal request id'
);

insert into content_factory.creator_tasks (
  organization_id, assignee_id, created_by, task_type, title, status,
  idempotency_key
)
values (
  '77000000-0000-4000-8000-000000000001',
  '77777777-7777-4777-8777-777777777771',
  '77777777-7777-4777-8777-777777777777',
  'general',
  'Resolve dashboard blocker',
  'blocked',
  'manager-dashboard-task-0001'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-task@example.test') ->> 'stage',
  'task',
  'a blocked assigned task is not misclassified as ready'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-task@example.test') ->> 'reason_code',
  'task_blocked',
  'the blocked task reason is explicit'
);

select is(
  (pg_temp.manager_dashboard_result() #>> '{summary,task}')::integer,
  1,
  'the task stage is represented in summary aggregates'
);

update content_factory.creator_tasks
set status = 'in_progress'
where idempotency_key = 'manager-dashboard-task-0001';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-task@example.test') ->> 'stage',
  'task',
  'an in-progress assigned task stays visible as active work'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-task@example.test') ->> 'reason_code',
  'task_in_progress',
  'the active task reason is explicit'
);

update content_factory.creator_tasks
set status = 'done', completed_at = now()
where idempotency_key = 'manager-dashboard-task-0001';

insert into content_factory.creator_payouts (
  organization_id, profile_id, task_id, amount_minor, currency, status
)
select
  task.organization_id,
  task.assignee_id,
  task.id,
  80000,
  'RUB',
  'pending'
from content_factory.creator_tasks task
where task.idempotency_key = 'manager-dashboard-task-0001';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-task@example.test') ->> 'stage',
  'payout',
  'a completed task with pending payout advances to the payout stage'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-task@example.test') ->> 'reason_code',
  'payout_pending',
  'pending payout reason is explicit'
);

update content_factory.profiles
set status = 'suspended'
where id = '77777777-7777-4777-8777-777777777772';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-profile-access@example.test') ->> 'reason_code',
  'profile_suspended',
  'a suspended profile is diagnosed as an access blocker'
);

update content_factory.profiles
set status = 'disabled'
where id = '77777777-7777-4777-8777-777777777772';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-profile-access@example.test') ->> 'reason_code',
  'profile_disabled',
  'a disabled profile is diagnosed as an access blocker'
);

update auth.users
set banned_until = now() + interval '1 day'
where id = '77777777-7777-4777-8777-777777777773';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-auth-access@example.test') ->> 'reason_code',
  'auth_user_banned',
  'an active Auth ban is diagnosed as an access blocker'
);

update auth.users
set banned_until = null, deleted_at = now()
where id = '77777777-7777-4777-8777-777777777773';

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-auth-access@example.test') ->> 'reason_code',
  'auth_user_deleted',
  'a soft-deleted Auth identity is diagnosed as an access blocker'
);

select is(
  (pg_temp.manager_dashboard_result() #>> '{summary,access}')::integer,
  2,
  'access blockers are represented in summary aggregates'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-stale-course@example.test') ->> 'stage',
  'course',
  'legacy certificates without refreshed course-check attempts do not bypass the gate'
);

select is(
  (pg_temp.manager_dashboard_member('manager-dashboard-stale-course@example.test') ->> 'courses_completed')::integer,
  0,
  'invalid legacy course attempts are excluded from completed progress'
);

insert into content_factory.placements (
  organization_id, product_id, assigned_to, created_by, platform,
  destination_ref, status, final_url, request_hash, idempotency_key,
  created_at, updated_at
)
values
  (
    '77000000-0000-4000-8000-000000000001',
    '77000000-0000-4000-8000-000000000010',
    '77777777-7777-4777-8777-777777777774',
    '77777777-7777-4777-8777-777777777777',
    'vk',
    'old-failed-placement',
    'failed',
    null,
    repeat('b', 64),
    'manager-placement-failed-0001',
    now() - interval '2 days',
    now() - interval '2 days'
  ),
  (
    '77000000-0000-4000-8000-000000000001',
    '77000000-0000-4000-8000-000000000010',
    '77777777-7777-4777-8777-777777777774',
    '77777777-7777-4777-8777-777777777777',
    'vk',
    'new-published-placement',
    'published',
    'https://vk.com/clip-manager-dashboard',
    repeat('c', 64),
    'manager-placement-published-0001',
    now() - interval '1 day',
    now() - interval '1 day'
  );

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-placement@example.test') ->> 'stage',
  'ready',
  'an old failed placement does not outrank a newer published result forever'
);

insert into content_factory.placements (
  organization_id, product_id, assigned_to, created_by, platform,
  destination_ref, status, scheduled_at, request_hash, idempotency_key
)
values (
  '77000000-0000-4000-8000-000000000001',
  '77000000-0000-4000-8000-000000000010',
  '77777777-7777-4777-8777-777777777774',
  '77777777-7777-4777-8777-777777777777',
  'vk',
  'current-scheduled-placement',
  'scheduled',
  now() + interval '1 hour',
  repeat('d', 64),
  'manager-placement-scheduled-0001'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-placement@example.test') ->> 'stage',
  'publication',
  'an unresolved scheduled placement remains visible'
);

select is(
  pg_temp.manager_dashboard_member('manager-dashboard-placement@example.test') ->> 'reason_code',
  'placement_scheduled',
  'scheduled placement reason is explicit'
);

select ok(
  not (
    pg_temp.manager_dashboard_member('manager-dashboard-owner@example.test')
      ?| array[
        'profile_id', 'generation_job_id', 'placement_id', 'payout_id',
        'task_id', 'payout_amount_minor'
      ]
  ),
  'member payload omits unused internal ids and payout amount'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '77777777-7777-4777-8777-777777777775',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_manager_dashboard('{"organization_id":"77000000-0000-4000-8000-000000000001"}'::jsonb)$$,
  '42501',
  'role_not_allowed',
  'a non-manager cannot read the dashboard'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '77777777-7777-4777-8777-777777777777',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_manager_dashboard('{"organization_id":"77000000-0000-4000-8000-000000000002"}'::jsonb)$$,
  '42501',
  'active_membership_required',
  'a manager cannot read another organization dashboard'
);

select * from finish();
rollback;

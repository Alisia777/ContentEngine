begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(13);

-- Фаза 0 контура авторазмещения (202608230024): реестр владения аккаунтами
-- компании. Владелец заводит аккаунт, ставит поля владения, выдаёт сотруднику;
-- увольнение сотрудника создаёт хранителю задачу снять роль на площадке.

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
(
  'ab000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'ownership-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Ownership Owner"}'::jsonb,
  now(), now()
),
(
  'ab000000-0000-4000-8000-000000000002',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'ownership-operator@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Ownership Operator"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'ab100000-0000-4000-8000-000000000001',
  'Ownership pgTAP',
  'ownership-pgtap',
  'active'
);

insert into content_factory.memberships (organization_id, profile_id, role, status)
values
  ('ab100000-0000-4000-8000-000000000001', 'ab000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('ab100000-0000-4000-8000-000000000001', 'ab000000-0000-4000-8000-000000000002', 'operator', 'active');

create or replace function pg_temp.as_owner()
returns void
language plpgsql
as $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', 'ab000000-0000-4000-8000-000000000001', true);
end;
$$;

select pg_temp.as_owner();

-- 1. Аккаунт заводится прежней админкой; поля владения получают умолчания.
select lives_ok(
  $$ select public.creator_admin_mutate(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001',
       'action', 'create_account',
       'idempotency_key', 'ownership-create-0001',
       'platform', 'telegram',
       'label', 'Канал бренда',
       'handle', '@brand_channel'
     )) $$,
  'owner creates a managed account'
);

select is(
  (select ownership_kind || '/' || posting_mode || '/' || connection_status
   from content_factory.managed_accounts
   where organization_id = 'ab100000-0000-4000-8000-000000000001'),
  'personal_issued/assisted/not_connected',
  'new accounts default to personal_issued, assisted posting, not connected'
);

-- 2. Свободная строка площадки больше не принимается.
select throws_ok(
  $$ insert into content_factory.managed_accounts (organization_id, platform, label, created_by)
     values ('ab100000-0000-4000-8000-000000000001', 'myspace', 'Чужая площадка',
             'ab000000-0000-4000-8000-000000000001') $$,
  '23514',
  null,
  'platform vocabulary is closed'
);

-- 3. Владелец ставит поля владения.
select lives_ok(
  $$ select public.creator_admin_account_ownership(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001',
       'action', 'set_ownership',
       'idempotency_key', 'ownership-set-0001',
       'account_id', (select id from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'expected_updated_at', (select updated_at::text from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'ownership_kind', 'channel_bot',
       'custodian_profile_id', 'ab000000-0000-4000-8000-000000000001',
       'registration_email_alias', 'social+brand@company.test',
       'registration_phone_ref', 'SIM-07',
       'external_account_id', '-1001234567890'
     )) $$,
  'owner sets ownership fields'
);

select is(
  (select ownership_kind || '/' || custodian_profile_id::text || '/' || registration_email_alias
          || '/' || registration_phone_ref || '/' || external_account_id
   from content_factory.managed_accounts
   where organization_id = 'ab100000-0000-4000-8000-000000000001'),
  'channel_bot/ab000000-0000-4000-8000-000000000001/social+brand@company.test/SIM-07/-1001234567890',
  'ownership fields are stored'
);

-- 4. Режим api нельзя включить рукой без живого подключения.
select throws_ok(
  $$ select public.creator_admin_account_ownership(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001',
       'action', 'set_ownership',
       'idempotency_key', 'ownership-set-0002',
       'account_id', (select id from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'expected_updated_at', (select updated_at::text from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'posting_mode', 'api'
     )) $$,
  'posting_mode_requires_connection',
  'api posting requires a connection'
);

-- 5. Хранителем может быть только активный владелец/админ/продюсер.
select throws_ok(
  $$ select public.creator_admin_account_ownership(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001',
       'action', 'set_ownership',
       'idempotency_key', 'ownership-set-0003',
       'account_id', (select id from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'expected_updated_at', (select updated_at::text from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'custodian_profile_id', 'ab000000-0000-4000-8000-000000000002'
     )) $$,
  'custodian_not_eligible',
  'an operator cannot be the custodian'
);

-- 6. Снимок админки отдаёт поля владения.
select is(
  (select account ->> 'ownership_kind' || '/' || (account ->> 'posting_mode')
   from jsonb_array_elements(
     public.creator_admin_snapshot(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001'
     )) -> 'accounts'
   ) account
   limit 1),
  'channel_bot/assisted',
  'the admin snapshot exposes ownership fields'
);

-- 7. Выдача сотруднику и его увольнение → задача хранителю.
select lives_ok(
  $$ select public.creator_admin_mutate(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001',
       'action', 'bind_account',
       'idempotency_key', 'ownership-bind-0001',
       'account_id', (select id from content_factory.managed_accounts
                      where organization_id = 'ab100000-0000-4000-8000-000000000001'),
       'target_profile_id', 'ab000000-0000-4000-8000-000000000002'
     )) $$,
  'owner issues the account to the operator'
);

select lives_ok(
  $$ select public.creator_admin_mutate(jsonb_build_object(
       'organization_id', 'ab100000-0000-4000-8000-000000000001',
       'action', 'revoke_member',
       'idempotency_key', 'ownership-revoke-0001',
       'target_profile_id', 'ab000000-0000-4000-8000-000000000002',
       'reason', 'Сотрудник уволился по собственному желанию',
       'confirmation', 'REVOKE_MEMBER'
     )) $$,
  'owner offboards the operator'
);

select is(
  (select count(*)::integer from content_factory.member_account_assignments
   where organization_id = 'ab100000-0000-4000-8000-000000000001' and status = 'active'),
  0,
  'the assignment is revoked with the member'
);

select is(
  (select assignee_id::text || '/' || (result ->> 'kind') || '/' || (result ->> 'ownership_kind')
   from content_factory.creator_tasks
   where organization_id = 'ab100000-0000-4000-8000-000000000001'
     and result ->> 'kind' = 'publishing_account_offboarding'),
  'ab000000-0000-4000-8000-000000000001/publishing_account_offboarding/channel_bot',
  'the custodian receives the platform-role removal task'
);

-- 8. Размещение умеет ссылаться на аккаунт компании.
select has_column(
  'content_factory', 'placements', 'managed_account_id',
  'placements carry the company account'
);

select * from finish();
rollback;

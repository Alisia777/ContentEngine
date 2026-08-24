begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(13);

-- Очередь проверки (202608240003): «Отвергнуть» просмотренный результат —
-- причина обязательна, файл уезжает в «Корзину» существующим контуром; вкладка
-- «Команда → Аккаунты» — витрина реестра для руководства.

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
(
  'ae000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'inbox-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Inbox Owner"}'::jsonb,
  now(), now()
),
(
  'ae000000-0000-4000-8000-000000000002',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'inbox-operator@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Inbox Operator"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'ae100000-0000-4000-8000-000000000001',
  'Inbox pgTAP', 'inbox-pgtap', 'active'
);

insert into content_factory.memberships (organization_id, profile_id, role, status)
values
(
  'ae100000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000001',
  'owner', 'active'
),
(
  'ae100000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000002',
  'operator', 'active'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'ae500000-0000-4000-8000-000000000001',
  'ae100000-0000-4000-8000-000000000001',
  null, 'Inbox project', 'blue', 'project', null,
  'active', 1024,
  'ae000000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000001'
);

-- Внутренний контур «Корзины» (workspace_trash_items) требует пройденного
-- обучения; фикстура включает владельцу вейвер вместо полного курса-экзамена.
insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'ae100000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000001',
  'workspace_generation', 'active', 'owner', 'owner',
  'pgTAP fixture: обход учебного гейта для владельца.',
  'ae000000-0000-4000-8000-000000000001'
);

-- Оператор состоит в проекте (доступ к проекту — не то же, что право отвергать
-- чужой файл: п.5 проверяет именно границу владения).
insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
) values (
  'ae100000-0000-4000-8000-000000000001',
  'ae500000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000002',
  'member', 'active',
  'ae000000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000001'
);

-- Готовый результат стратегии (владелец) и исходник для негативного сценария.
insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id,
  object_name, mime_type, size_bytes, sha256, status, metadata,
  idempotency_key
) values
(
  'ae300000-0000-4000-8000-000000000001',
  'ae100000-0000-4000-8000-000000000001',
  'ae500000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000001',
  null,
  'contentengine-private',
  'ae100000-0000-4000-8000-000000000001/ae000000-0000-4000-8000-000000000001/results/reject-me.mp4',
  'video/mp4', 2345678,
  repeat('c1', 32),
  'ready',
  jsonb_build_object(
    'kind', 'generated_video',
    'generation_job_id', 'ae400000-0000-4000-8000-000000000001'
  ),
  'inbox-media-0001'
),
(
  'ae300000-0000-4000-8000-000000000002',
  'ae100000-0000-4000-8000-000000000001',
  'ae500000-0000-4000-8000-000000000001',
  'ae000000-0000-4000-8000-000000000001',
  null,
  'contentengine-private',
  'ae100000-0000-4000-8000-000000000001/ae000000-0000-4000-8000-000000000001/sources/source.mp4',
  'video/mp4', 13612094,
  repeat('d2', 32),
  'ready',
  jsonb_build_object('kind', 'source_video'),
  'inbox-media-0002'
);

create or replace function pg_temp.as_user(p_user_id text)
returns void
language plpgsql
as $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', p_user_id, true);
end;
$$;

select pg_temp.as_user('ae000000-0000-4000-8000-000000000001');

-- 1. Лишний ключ в запросе — честный отказ формы.
select throws_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000001',
       'reason', 'Ролик смазан на третьей секунде',
       'watch_confirmed', true,
       'idempotency_key', 'inbox-reject-extra-0001',
       'surprise', true
     )) $$,
  '22023',
  'reject_result_payload_invalid',
  'unknown payload keys are rejected'
);

-- 2. Отказ — тоже решение после просмотра: literal true обязателен.
select throws_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000001',
       'reason', 'Ролик смазан на третьей секунде',
       'watch_confirmed', false,
       'idempotency_key', 'inbox-reject-watchless-0001'
     )) $$,
  '22023',
  'reject_result_watch_confirmation_required',
  'watch confirmation must be literal true'
);

-- 3. Причина обязана быть содержательной (минимум 5 знаков).
select throws_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000001',
       'reason', 'нет',
       'watch_confirmed', true,
       'idempotency_key', 'inbox-reject-short-0001'
     )) $$,
  '22023',
  null,
  'a five-character reason is the floor'
);

-- 4. Исходник отвергнуть нельзя — только результат генерации.
select throws_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000002',
       'reason', 'Это вообще исходник, не результат',
       'watch_confirmed', true,
       'idempotency_key', 'inbox-reject-source-0001'
     )) $$,
  '55000',
  'reject_result_media_not_generated_video',
  'only generated_video results can be rejected'
);

-- 5. Оператор не может отвергнуть чужой ролик.
select pg_temp.as_user('ae000000-0000-4000-8000-000000000002');
select throws_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000001',
       'reason', 'Чужой ролик мне не нравится',
       'watch_confirmed', true,
       'idempotency_key', 'inbox-reject-foreign-0001'
     )) $$,
  '42501',
  'reject_result_scope_denied',
  'an operator rejects only their own results'
);

-- 6. Счастливый путь: владелец отвергает после просмотра.
select pg_temp.as_user('ae000000-0000-4000-8000-000000000001');
select lives_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000001',
       'reason', 'Продукт смазан, реплика расходится с текстом',
       'watch_confirmed', true,
       'idempotency_key', 'inbox-reject-happy-0001'
     )) $$,
  'the owner rejects a watched result'
);

-- 7. Файл в «Корзине»: статус deleted, из «Файлов» ушёл.
select is(
  (select media.status from content_factory.media_objects media
   where media.id = 'ae300000-0000-4000-8000-000000000001'),
  'deleted',
  'the rejected file is moved to the recycle bin'
);

-- 8. Строка корзины существует и восстановима.
select is(
  (select count(*)::integer from content_factory.workspace_trash_items trash
   where trash.organization_id = 'ae100000-0000-4000-8000-000000000001'
     and trash.entity_type = 'media'
     and trash.entity_id = 'ae300000-0000-4000-8000-000000000001'
     and trash.status = 'trashed'),
  1,
  'a restorable trash row records the original location'
);

-- 9. Причина отказа осталась на самом файле.
select is(
  (select media.metadata #>> '{rejection,reason}'
   from content_factory.media_objects media
   where media.id = 'ae300000-0000-4000-8000-000000000001'),
  'Продукт смазан, реплика расходится с текстом',
  'the rejection reason is kept on the file'
);

-- 10. Повтор той же команды — идемпотентный replay, вторая строка не появляется.
select lives_ok(
  $$ select public.creator_reject_generation_result(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001',
       'project_id', 'ae500000-0000-4000-8000-000000000001',
       'media_id', 'ae300000-0000-4000-8000-000000000001',
       'reason', 'Продукт смазан, реплика расходится с текстом',
       'watch_confirmed', true,
       'idempotency_key', 'inbox-reject-happy-0001'
     )) $$,
  'the same command replays without a duplicate'
);

select is(
  (select count(*)::integer from content_factory.workspace_trash_items trash
   where trash.organization_id = 'ae100000-0000-4000-8000-000000000001'
     and trash.entity_type = 'media'),
  1,
  'replay does not create a second trash row'
);

-- Аккаунт для витрины «Команда → Аккаунты» + выдача оператору.
select public.creator_admin_mutate(jsonb_build_object(
  'organization_id', 'ae100000-0000-4000-8000-000000000001',
  'action', 'create_account',
  'idempotency_key', 'inbox-create-account-0001',
  'platform', 'telegram',
  'label', 'Канал МБТ',
  'handle', '@mbt_inbox'
));

insert into content_factory.member_account_assignments (
  organization_id, account_id, profile_id, status, assigned_by
)
select
  account.organization_id, account.id,
  'ae000000-0000-4000-8000-000000000002', 'active',
  'ae000000-0000-4000-8000-000000000001'
from content_factory.managed_accounts account
where account.organization_id = 'ae100000-0000-4000-8000-000000000001'
limit 1;

-- 12. Витрина отдаёт аккаунт с хранителем, выдачей и счётчиками размещений.
select is(
  (select jsonb_build_object(
     'count', jsonb_array_length(result -> 'accounts'),
     'version', result -> 'version',
     'assignees', result #> '{accounts,0,assignees}',
     'placements_total', result #> '{accounts,0,placements_total}'
   )
   from public.creator_team_accounts(jsonb_build_object(
     'organization_id', 'ae100000-0000-4000-8000-000000000001'
   )) as result),
  jsonb_build_object(
    'count', 1,
    'version', to_jsonb('team-accounts-v1'::text),
    'assignees', jsonb_build_array('Inbox Operator'),
    'placements_total', to_jsonb(0)
  ),
  'the team accounts view lists the registry with assignments and counters'
);

-- 13. Оператору витрина закрыта — это управленческий экран.
select pg_temp.as_user('ae000000-0000-4000-8000-000000000002');
select throws_ok(
  $$ select public.creator_team_accounts(jsonb_build_object(
       'organization_id', 'ae100000-0000-4000-8000-000000000001'
     )) $$,
  '42501',
  'team_accounts_role_denied',
  'operators do not see the management registry'
);

select * from finish();
rollback;

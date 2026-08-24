begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(13);

-- «Одобрить и разместить» (202608240001): готовый результат стратегии уходит в
-- существующий контур размещения — задача 'placement' + строка placements — с
-- явным подтверждением просмотра, выданным аккаунтом компании и ERID.

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'ac000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'publish-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Publish Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'ac100000-0000-4000-8000-000000000001',
  'Publish pgTAP', 'publish-pgtap', 'active'
);

insert into content_factory.memberships (organization_id, profile_id, role, status)
values (
  'ac100000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001',
  'owner', 'active'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'ac500000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001',
  null, 'Publish project', 'blue', 'project', null,
  'active', 1024,
  'ac000000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001'
);

-- Членство в проекте засевает триггер workspace_folders сам (owner).

insert into content_factory.generation_spend_policies (
  organization_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, timezone, version, reason, updated_by
) values (
  'ac100000-0000-4000-8000-000000000001', true,
  2500, 10000, 500, 'USD', 'Europe/Moscow', 1,
  'Publish pgTAP fixture policy.',
  'ac000000-0000-4000-8000-000000000001'
);

-- Фикстура собирает терминальный оплаченный наряд задним числом, как в
-- content_review_pipeline_test: insert-время спецификаций обходим, все
-- жизненные триггеры остаются активными.
alter table content_factory.generation_jobs
  disable trigger a_generation_spec_binding_guard;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'ac200000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001',
  'PUBLISH-SKU-1', 'Мангал ROASTER', 'active', '{}'::jsonb,
  'ac000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, project_id, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key,
  provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency
) values (
  'ac450000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001',
  'ac200000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001',
  'ac500000-0000-4000-8000-000000000001',
  'Publish fixture batch',
  'real', true, 'succeeded', 1, 1,
  jsonb_build_object(
    'job_id', 'ac400000-0000-4000-8000-000000000001',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'audio', false,
    'format', '9:16',
    'ratio', '720:1280',
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 25,
      'estimated_credits', 25
    )
  ),
  repeat('3', 64), 'publish-batch-0001',
  'runway', 'gen4_turbo', 5, false,
  25, 25, 'USD'
);

insert into content_factory.generation_jobs (
  id, organization_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, project_id, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status,
  input, output, request_hash, idempotency_key
) values (
  'ac400000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001',
  'ac200000-0000-4000-8000-000000000001',
  'ac450000-0000-4000-8000-000000000001',
  1,
  'ac000000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001',
  'ac500000-0000-4000-8000-000000000001',
  'real', 'runway', true, 25, 25, 'succeeded',
  jsonb_build_object(
    'sku', 'PUBLISH-SKU-1',
    'product_name', 'Мангал ROASTER',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'audio', false,
    'format', '9:16',
    'ratio', '720:1280',
    'input_object_name',
      'ac100000-0000-4000-8000-000000000001/publish/input.webp',
    'output_object_name',
      'ac100000-0000-4000-8000-000000000001/publish/generated.mp4',
    'platform', 'vk',
    'destination_ref', 'vk-publish-fixture',
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 25,
      'estimated_credits', 25
    )
  ),
  jsonb_build_object(
    'provider_task_id', 'provider-publish-fixture',
    'output_object_name',
      'ac100000-0000-4000-8000-000000000001/publish/generated.mp4',
    'output_media_id', 'ac300000-0000-4000-8000-000000000001',
    'mime_type', 'video/mp4',
    'sha256', repeat('5', 64)
  ),
  repeat('2', 64),
  'publish-job-0001'
);

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id,
  object_name, mime_type, size_bytes, sha256, status, metadata,
  idempotency_key
) values (
  'ac300000-0000-4000-8000-000000000001',
  'ac100000-0000-4000-8000-000000000001',
  'ac500000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001',
  null,
  'contentengine-private',
  'ac100000-0000-4000-8000-000000000001/ac000000-0000-4000-8000-000000000001/results/duet.mp4',
  'video/mp4', 3356203,
  repeat('a1', 32),
  'ready',
  jsonb_build_object(
    'kind', 'generated_video',
    'generation_job_id', 'ac400000-0000-4000-8000-000000000001'
  ),
  'publish-media-0001'
),
(
  'ac300000-0000-4000-8000-000000000002',
  'ac100000-0000-4000-8000-000000000001',
  'ac500000-0000-4000-8000-000000000001',
  'ac000000-0000-4000-8000-000000000001',
  null,
  'contentengine-private',
  'ac100000-0000-4000-8000-000000000001/ac000000-0000-4000-8000-000000000001/sources/source.mp4',
  'video/mp4', 13612094,
  repeat('b2', 32),
  'ready',
  jsonb_build_object('kind', 'source_video'),
  'publish-media-0002'
);

create or replace function pg_temp.as_owner()
returns void
language plpgsql
as $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', 'ac000000-0000-4000-8000-000000000001', true);
end;
$$;

select pg_temp.as_owner();

-- 1. Пустой реестр — форма честно видит ноль аккаунтов.
select is(
  (public.creator_publishing_accounts(jsonb_build_object(
     'organization_id', 'ac100000-0000-4000-8000-000000000001'
   )) -> 'accounts'),
  '[]'::jsonb,
  'no active accounts yet'
);

-- Аккаунт компании из реестра фазы 0.
select lives_ok(
  $$ select public.creator_admin_mutate(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'action', 'create_account',
       'idempotency_key', 'publish-create-account-0001',
       'platform', 'telegram',
       'label', 'Канал МБТ',
       'handle', '@mbt_channel'
     )) $$,
  'owner creates a managed account'
);

-- 2. Список отдаёт аккаунт с режимом и подключением.
select is(
  (select jsonb_array_length(
     public.creator_publishing_accounts(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001'
     )) -> 'accounts'
   )),
  1,
  'the issued account is listed for the publish form'
);

-- 3. Без явного подтверждения просмотра размещение не создаётся.
select throws_ok(
  format($f$ select public.creator_publish_generation_result(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001',
       'media_id', 'ac300000-0000-4000-8000-000000000001',
       'managed_account_id', %L,
       'erid', '2VTZQAB12',
       'watch_confirmed', false,
       'idempotency_key', 'publish-watchless-0001'
     )) $f$,
     (select id from content_factory.managed_accounts
      where organization_id = 'ac100000-0000-4000-8000-000000000001' limit 1)),
  '22023',
  'publish_result_watch_confirmation_required',
  'watch confirmation must be literal true'
);

-- 4. ERID обязателен и в закрытой форме.
select throws_ok(
  format($f$ select public.creator_publish_generation_result(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001',
       'media_id', 'ac300000-0000-4000-8000-000000000001',
       'managed_account_id', %L,
       'erid', 'нет',
       'watch_confirmed', true,
       'idempotency_key', 'publish-erid-0001'
     )) $f$,
     (select id from content_factory.managed_accounts
      where organization_id = 'ac100000-0000-4000-8000-000000000001' limit 1)),
  '22023',
  null,
  'erid must satisfy the closed shape'
);

-- 5. Не-результат (source_video) разместить нельзя.
select throws_ok(
  format($f$ select public.creator_publish_generation_result(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001',
       'media_id', 'ac300000-0000-4000-8000-000000000002',
       'managed_account_id', %L,
       'erid', '2VTZQAB12',
       'watch_confirmed', true,
       'idempotency_key', 'publish-source-0001'
     )) $f$,
     (select id from content_factory.managed_accounts
      where organization_id = 'ac100000-0000-4000-8000-000000000001' limit 1)),
  '55000',
  'publish_result_media_not_generated_video',
  'only generated_video results can be published'
);

-- 6. Счастливый путь.
select lives_ok(
  format($f$ select public.creator_publish_generation_result(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001',
       'media_id', 'ac300000-0000-4000-8000-000000000001',
       'managed_account_id', %L,
       'erid', '2vtzqab12',
       'watch_confirmed', true,
       'idempotency_key', 'publish-happy-0001'
     )) $f$,
     (select id from content_factory.managed_accounts
      where organization_id = 'ac100000-0000-4000-8000-000000000001' limit 1)),
  'a watched result publishes to the issued account'
);

-- 7. Строка размещения: статус ready, аккаунт и ERID (в верхнем регистре).
select is(
  (select placement.status || '/' || placement.platform || '/'
      || (placement.metadata ->> 'erid')
      || '/' || (placement.managed_account_id is not null)::text
   from content_factory.placements placement
   where placement.organization_id = 'ac100000-0000-4000-8000-000000000001'
     and placement.generation_job_id = 'ac400000-0000-4000-8000-000000000001'),
  'ready/telegram/2VTZQAB12/true',
  'the placement row carries account, platform and uppercased erid'
);

-- 8. Задача размещения в «Моих работах» несёт ERID в инструкции.
select is(
  (select task.task_type || '/' || (position('ERID 2VTZQAB12' in task.instructions) > 0)::text
   from content_factory.creator_tasks task
   where task.organization_id = 'ac100000-0000-4000-8000-000000000001'
     and task.generation_job_id = 'ac400000-0000-4000-8000-000000000001'),
  'placement/true',
  'the placement task instructs the executor with the exact erid'
);

-- 9. Одобренный результат переезжает из «Черновиков» в «Готово».
select is(
  (select lifecycle_stage from content_factory.media_objects
   where id = 'ac300000-0000-4000-8000-000000000001'),
  'ready',
  'the published result advances its lifecycle stage to ready'
);

-- 10. Повтор того же запроса не плодит вторых строк.
select lives_ok(
  format($f$ select public.creator_publish_generation_result(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001',
       'media_id', 'ac300000-0000-4000-8000-000000000001',
       'managed_account_id', %L,
       'erid', '2vtzqab12',
       'watch_confirmed', true,
       'idempotency_key', 'publish-happy-0001'
     )) $f$,
     (select id from content_factory.managed_accounts
      where organization_id = 'ac100000-0000-4000-8000-000000000001' limit 1)),
  'the same command replays idempotently'
);

select is(
  (select count(*)::integer from content_factory.placements placement
   where placement.organization_id = 'ac100000-0000-4000-8000-000000000001'),
  1,
  'replay keeps exactly one placement row'
);

-- 10. Незавершённая задача не размещается: результат должен существовать.
select throws_ok(
  format($f$ select public.creator_publish_generation_result(jsonb_build_object(
       'organization_id', 'ac100000-0000-4000-8000-000000000001',
       'project_id', 'ac500000-0000-4000-8000-000000000001',
       'media_id', %L,
       'managed_account_id', %L,
       'erid', '2VTZQAB12',
       'watch_confirmed', true,
       'idempotency_key', 'publish-processing-0001'
     )) $f$,
     'ac300000-0000-4000-8000-000000000003',
     (select id from content_factory.managed_accounts
      where organization_id = 'ac100000-0000-4000-8000-000000000001' limit 1)),
  '42501',
  null,
  'an unknown media id is refused before any writes'
);

alter table content_factory.generation_jobs
  enable trigger a_generation_spec_binding_guard;

select * from finish();
rollback;

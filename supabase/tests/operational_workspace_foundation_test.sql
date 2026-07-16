begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

create or replace function pg_temp.grant_operational_workspace_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $gate$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
  answers_value jsonb;
  exam_question_count integer;
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
    select coalesce(jsonb_object_agg(
      question.code,
      answer_key.correct_answers
      order by question.order_index
    ), '{}'::jsonb)
    into answers_value
    from content_factory.training_questions question
    join content_factory_private.training_answer_keys answer_key
      on answer_key.question_code = question.code
    where question.module_code = module_row.code
      and question.order_index between 901 and 1000
      and strpos(
        question.code,
        'course_check_' || module_row.code || '_'
      ) = 1;

    insert into content_factory.training_attempts (
      organization_id, profile_id, module_code, status, score,
      correct_count, answered_count, question_count, passed, answers,
      request_hash, idempotency_key
    ) values (
      p_organization_id, p_profile_id, module_row.code, 'completed', 1,
      module_row.question_count, module_row.question_count,
      module_row.question_count, true, answers_value,
      content_factory_private.json_hash(jsonb_build_object(
        'module_code', module_row.code,
        'answers', answers_value
      )),
      left(
        'course-check:' || p_key_prefix || ':' || module_row.code,
        180
      )
    )
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      p_organization_id, p_profile_id, module_row.code,
      attempt_id_value, 'passed'
    );
  end loop;

  select module.question_count
    into exam_question_count
  from content_factory.training_modules module
  where module.code = 'operator_final_exam'
    and module.module_type = 'exam'
    and module.is_active;

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    p_organization_id, p_profile_id, 'operator_final_exam',
    'completed', 1, exam_question_count, exam_question_count,
    exam_question_count, true, '{}'::jsonb, repeat('f', 64),
    left('ops-final:' || p_key_prefix, 180)
  )
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    p_organization_id, p_profile_id, 'operator_final_exam',
    attempt_id_value, 'passed'
  );
end;
$gate$;

select plan(59);

select has_table(
  'content_factory', 'user_notifications',
  'notification table exists'
);
select has_table(
  'content_factory', 'training_walkthrough_progress',
  'server training progress table exists'
);
select has_table(
  'content_factory', 'saved_work_views',
  'saved work view table exists'
);
select has_column(
  'content_factory', 'user_notifications', 'deep_link',
  'notifications carry an application deep link'
);
select has_column(
  'content_factory', 'user_notifications', 'read_at',
  'notifications carry read state'
);
select has_column(
  'content_factory', 'training_walkthrough_progress', 'version',
  'training progress carries an optimistic version'
);
select has_column(
  'content_factory', 'saved_work_views', 'filters',
  'saved views persist normalized filters'
);
select has_column(
  'content_factory', 'saved_work_views', 'is_default',
  'saved views can select one default'
);

select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'content_factory.user_notifications'::regclass
  ),
  'notification table uses RLS'
);
select ok(
  (
    select relrowsecurity
    from pg_class
    where oid =
      'content_factory.training_walkthrough_progress'::regclass
  ),
  'training progress table uses RLS'
);
select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'content_factory.saved_work_views'::regclass
  ),
  'saved view table uses RLS'
);
select is(
  (
    select count(*)::integer
    from (values
      ('content_factory.user_notifications'::regclass),
      ('content_factory.training_walkthrough_progress'::regclass),
      ('content_factory.saved_work_views'::regclass)
    ) protected(table_oid)
    where has_table_privilege(
      'authenticated',
      protected.table_oid,
      'select,insert,update,delete'
    )
  ),
  0,
  'authenticated has no direct operational table privileges'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_my_work',
        'creator_notifications',
        'creator_mark_notifications_read',
        'creator_training_progress',
        'creator_save_training_progress',
        'creator_saved_work_views'
      )
      and pg_get_function_identity_arguments(procedure.oid)
        = 'p_payload jsonb'
  ),
  6,
  'six browser operational RPCs expose one JSON payload'
);
select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_my_work',
        'creator_notifications',
        'creator_mark_notifications_read',
        'creator_training_progress',
        'creator_save_training_progress',
        'creator_saved_work_views'
      )
      and has_function_privilege(
        'authenticated', procedure.oid, 'execute'
      )
  ),
  6,
  'authenticated can execute the browser operational RPCs'
);
select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_my_work',
        'creator_notifications',
        'creator_mark_notifications_read',
        'creator_training_progress',
        'creator_save_training_progress',
        'creator_saved_work_views'
      )
      and has_function_privilege('anon', procedure.oid, 'execute')
  ),
  0,
  'anonymous users cannot execute operational RPCs'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_emit_notification(jsonb)',
    'execute'
  ),
  'service role can emit notifications'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_emit_notification(jsonb)',
    'execute'
  ),
  'browser sessions cannot emit arbitrary notifications'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt(
    'test-only-password',
    extensions.gen_salt('bf')
  ),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    '96000000-0000-4000-8000-000000000001',
    'ops-owner@example.test',
    'Operations Owner'
  ),
  (
    '96000000-0000-4000-8000-000000000002',
    'ops-outsider@example.test',
    'Operations Outsider'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    '96100000-0000-4000-8000-000000000001',
    'Operational Workspace Main',
    'operational-workspace-main',
    'active'
  ),
  (
    '96100000-0000-4000-8000-000000000002',
    'Operational Workspace Other',
    'operational-workspace-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '96100000-0000-4000-8000-000000000001',
    '96000000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    '96100000-0000-4000-8000-000000000002',
    '96000000-0000-4000-8000-000000000002',
    'owner', 'active'
  );

select pg_temp.grant_operational_workspace_gate(
  '96100000-0000-4000-8000-000000000001',
  '96000000-0000-4000-8000-000000000001',
  'operational-owner'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values
  (
    '96200000-0000-4000-8000-000000000001',
    '96100000-0000-4000-8000-000000000001',
    'OPS-SKU-1',
    'Operational product',
    'active',
    '{"content_review_category":"cosmetics"}'::jsonb,
    '96000000-0000-4000-8000-000000000001'
  ),
  (
    '96200000-0000-4000-8000-000000000002',
    '96100000-0000-4000-8000-000000000002',
    'OTHER-SKU-1',
    'Other product',
    'active',
    '{}'::jsonb,
    '96000000-0000-4000-8000-000000000002'
  );

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values (
  '96300000-0000-4000-8000-000000000001',
  '96100000-0000-4000-8000-000000000001',
  '96000000-0000-4000-8000-000000000001',
  '96200000-0000-4000-8000-000000000001',
  'contentengine-private',
  '96100000-0000-4000-8000-000000000001/96000000-0000-4000-8000-000000000001/ops/source.webp',
  'image/webp',
  4096,
  repeat('a', 64),
  'ready',
  '{"kind":"product_photo","original_filename":"ops-source.webp","rights_confirmed":true}'::jsonb,
  'operational-source-media'
);

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, ruleset_version, request_hash,
  idempotency_key
)
values (
  '96400000-0000-4000-8000-000000000001',
  '96100000-0000-4000-8000-000000000001',
  '96300000-0000-4000-8000-000000000001',
  '96000000-0000-4000-8000-000000000001',
  'queued',
  repeat('a', 64),
  '{"content_kind":"organic"}'::jsonb,
  'ops-rules-1',
  repeat('b', 64),
  'operational-review-run'
);

insert into content_factory.creator_tasks (
  id, organization_id, assignee_id, created_by, product_id,
  task_type, title, instructions, status, priority, payout_minor,
  idempotency_key, completed_at
)
values
  (
    '96500000-0000-4000-8000-000000000001',
    '96100000-0000-4000-8000-000000000001',
    '96000000-0000-4000-8000-000000000001',
    '96000000-0000-4000-8000-000000000001',
    '96200000-0000-4000-8000-000000000001',
    'general',
    'Operational payout task',
    'Completed operational fixture',
    'done',
    3,
    15000,
    'operational-payout-task',
    now()
  ),
  (
    '96500000-0000-4000-8000-000000000002',
    '96100000-0000-4000-8000-000000000001',
    '96000000-0000-4000-8000-000000000001',
    '96000000-0000-4000-8000-000000000001',
    '96200000-0000-4000-8000-000000000001',
    'placement',
    'Operational placement task',
    'Publish the operational fixture.',
    'todo',
    2,
    0,
    'operational-placement-task',
    null
  );

insert into content_factory.creator_payouts (
  id, organization_id, profile_id, task_id, amount_minor,
  currency, status, reason
)
values (
  '96600000-0000-4000-8000-000000000001',
  '96100000-0000-4000-8000-000000000001',
  '96000000-0000-4000-8000-000000000001',
  '96500000-0000-4000-8000-000000000001',
  15000,
  'RUB',
  'pending',
  'Operational payout'
);

insert into content_factory.placements (
  id, organization_id, product_id, task_id, assigned_to, created_by,
  platform, destination_ref, status, scheduled_at, request_hash,
  idempotency_key, metadata
)
values (
  '96700000-0000-4000-8000-000000000001',
  '96100000-0000-4000-8000-000000000001',
  '96200000-0000-4000-8000-000000000001',
  '96500000-0000-4000-8000-000000000002',
  '96000000-0000-4000-8000-000000000001',
  '96000000-0000-4000-8000-000000000001',
  'vk',
  'ops-vk-destination',
  'scheduled',
  now() + interval '1 day',
  repeat('c', 64),
  'operational-placement-0001',
  '{}'::jsonb
);

select lives_ok(
  $$
    select public.system_emit_notification(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'recipient_id', '96000000-0000-4000-8000-000000000001',
      'kind', 'work_ready',
      'severity', 'success',
      'title', 'Работа готова',
      'body', 'Откройте проверку результата.',
      'deep_link', '#/workspace/review?review=96400000-0000-4000-8000-000000000001',
      'entity_type', 'content_review',
      'entity_id', '96400000-0000-4000-8000-000000000001',
      'idempotency_key', 'ops-notification-main-0001'
    ))
  $$,
  'service notification creation succeeds'
);
select is(
  public.system_emit_notification(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'recipient_id', '96000000-0000-4000-8000-000000000001',
    'kind', 'work_ready',
    'severity', 'success',
    'title', 'Работа готова',
    'body', 'Откройте проверку результата.',
    'deep_link', '#/workspace/review?review=96400000-0000-4000-8000-000000000001',
    'entity_type', 'content_review',
    'entity_id', '96400000-0000-4000-8000-000000000001',
    'idempotency_key', 'ops-notification-main-0001'
  )) #>> '{notification,kind}',
  'work_ready',
  'system notification is idempotently replayed'
);
select throws_ok(
  $$
    select public.system_emit_notification(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'recipient_id', '96000000-0000-4000-8000-000000000001',
      'kind', 'different_kind',
      'title', 'Конфликт данных',
      'body', 'Другой payload не может использовать прежний ключ.',
      'deep_link', '#/workspace/tasks',
      'idempotency_key', 'ops-notification-main-0001'
    ))
  $$,
  '23505',
  'notification_idempotency_conflict',
  'notification replay rejects a different payload'
);
select lives_ok(
  $$
    select public.system_emit_notification(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000002',
      'recipient_id', '96000000-0000-4000-8000-000000000002',
      'kind', 'other_work',
      'title', 'Другая организация',
      'body', 'Изолированное уведомление.',
      'deep_link', '#/workspace/home',
      'idempotency_key', 'ops-notification-other-001'
    ))
  $$,
  'other organization notification fixture succeeds'
);

do $$
begin
  perform public.system_emit_notification(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'recipient_id', '96000000-0000-4000-8000-000000000001',
    'kind', 'work_blocked',
    'severity', 'error',
    'title', 'Блокер в работе',
    'body', 'Нужно разобрать ошибку до продолжения.',
    'deep_link', '#/workspace/generation?job=96800000-0000-4000-8000-000000000001',
    'idempotency_key', 'ops-notification-blocked-001'
  ));
  perform public.system_emit_notification(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'recipient_id', '96000000-0000-4000-8000-000000000001',
    'kind', 'decision_required',
    'severity', 'warning',
    'title', 'Нужно решение',
    'body', 'Проверка ждёт решения человека.',
    'deep_link', '#/workspace/review?review=96400000-0000-4000-8000-000000000001',
    'idempotency_key', 'ops-notification-decision-001'
  ));
end;
$$;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '96000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

create temporary table operational_rpc_results (
  name text primary key,
  payload jsonb not null
) on commit drop;
grant select, insert, update on operational_rpc_results to authenticated;

set local role authenticated;

insert into operational_rpc_results (name, payload)
values (
  'paid_generation',
  public.creator_start_real_generation(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'idempotency_key', 'operational-generation-0001',
    'sku', 'OPS-SKU-1',
    'product_name', 'Operational product',
    'count', 1,
    'format', '9:16',
    'brief', 'Operational workspace paid generation fixture.',
    'media_ids',
      '["96300000-0000-4000-8000-000000000001"]'::jsonb,
    'platform', 'wildberries',
    'destination_ref', 'ops-destination',
    'mode', 'real',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'allow_real_spend', true,
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
  ))
);

insert into operational_rpc_results (name, payload)
values (
  'notifications_authenticated_role',
  public.creator_notifications(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001'
  ))
);

reset role;

select is(
  (select payload #>> '{job,status}'
   from operational_rpc_results where name = 'paid_generation'),
  'queued',
  'paid generation fixture creates an active generation'
);
select is(
  (select payload #>> '{counts,unread}'
   from operational_rpc_results
   where name = 'notifications_authenticated_role'),
  '3',
  'notification RPC works under the authenticated database role'
);

select is(
  public.creator_training_progress(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001'
  )) #>> '{items}',
  '[]',
  'new device starts with empty server progress'
);

insert into operational_rpc_results (name, payload)
values (
  'training_initial',
  public.creator_save_training_progress(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'module_code', 'factory_basics',
    'walkthrough_id', 'first_login_route',
    'current_frame_id', 'accept_access',
    'position_seconds', 12,
    'completed_frame_ids', '["accept_access"]'::jsonb,
    'completed', false,
    'idempotency_key', 'ops-training-progress-0001'
  ))
);
select is(
  (select payload #>> '{progress,version}'
   from operational_rpc_results where name = 'training_initial'),
  '1',
  'first training save creates version one'
);
select is(
  public.creator_save_training_progress(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'module_code', 'factory_basics',
    'walkthrough_id', 'first_login_route',
    'current_frame_id', 'accept_access',
    'position_seconds', 12,
    'completed_frame_ids', '["accept_access"]'::jsonb,
    'completed', false,
    'idempotency_key', 'ops-training-progress-0001'
  ))::text,
  (select payload::text
   from operational_rpc_results where name = 'training_initial'),
  'training save replay returns the original result'
);
select is(
  public.creator_save_training_progress(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'module_code', 'factory_basics',
    'walkthrough_id', 'first_login_route',
    'current_frame_id', 'set_password',
    'position_seconds', 35,
    'completed_frame_ids', '["set_password"]'::jsonb,
    'completed', false,
    'expected_version', 1,
    'idempotency_key', 'ops-training-progress-0002'
  )) #>> '{progress,version}',
  '2',
  'second training save merges frames and advances version'
);
select is(
  public.creator_save_training_progress(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'module_code', 'factory_basics',
    'walkthrough_id', 'first_login_route',
    'current_frame_id', 'open_learning',
    'position_seconds', 70,
    'completed', true,
    'expected_version', 2,
    'idempotency_key', 'ops-training-progress-0003'
  )) #>> '{progress,completed}',
  'true',
  'completed training save marks the walkthrough complete'
);
select is(
  jsonb_array_length(
    public.creator_training_progress(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'module_code', 'factory_basics'
    )) #> '{items,0,completed_frame_ids}'
  ),
  3,
  'completed walkthrough persists every catalog frame'
);
select throws_ok(
  $$
    select public.creator_save_training_progress(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'module_code', 'factory_basics',
      'walkthrough_id', 'first_login_route',
      'current_frame_id', 'unknown_frame',
      'position_seconds', 1,
      'idempotency_key', 'ops-training-progress-invalid'
    ))
  $$,
  '22023',
  'training_current_frame_unknown',
  'unknown catalog frame is rejected'
);
select throws_ok(
  $$
    select public.creator_save_training_progress(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'module_code', 'factory_basics',
      'walkthrough_id', 'first_login_route',
      'position_seconds', 10,
      'expected_version', 1,
      'idempotency_key', 'ops-training-progress-stale'
    ))
  $$,
  '40001',
  'training_progress_version_conflict',
  'stale training version cannot overwrite newer progress'
);

select is(
  public.creator_saved_work_views(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'action', 'list'
  )) #>> '{views}',
  '[]',
  'saved view list starts empty'
);
insert into operational_rpc_results (name, payload)
values (
  'view_created',
  public.creator_saved_work_views(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'action', 'upsert',
    'name', 'Срочная работа',
    'filters', jsonb_build_object(
      'query', ' operational ',
      'statuses', '["blocked","todo","blocked"]'::jsonb,
      'item_types', '["task","placement"]'::jsonb
    ),
    'is_default', true,
    'idempotency_key', 'ops-saved-view-create-001'
  ))
);
select is(
  (select payload #>> '{views,0,version}'
   from operational_rpc_results where name = 'view_created'),
  '1',
  'saved view begins at version one'
);
select is(
  (select payload #>> '{views,0,is_default}'
   from operational_rpc_results where name = 'view_created'),
  'true',
  'saved view creation atomically selects the default'
);
select is(
  (select payload #>> '{views,0,filters,query}'
   from operational_rpc_results where name = 'view_created'),
  'operational',
  'saved view stores normalized query text'
);
select is(
  jsonb_array_length(
    (select payload #> '{views,0,filters,statuses}'
     from operational_rpc_results where name = 'view_created')
  ),
  2,
  'saved view removes duplicate statuses'
);
select throws_ok(
  $$
    select public.creator_saved_work_views(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'action', 'upsert',
      'view_id', (
        select payload #>> '{views,0,id}'
        from operational_rpc_results where name = 'view_created'
      ),
      'name', 'Устаревшее изменение',
      'filters', '{}'::jsonb,
      'expected_version', 9,
      'idempotency_key', 'ops-saved-view-stale-001'
    ))
  $$,
  '40001',
  'saved_work_view_version_conflict',
  'stale saved view version is rejected'
);
select is(
  public.creator_saved_work_views(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'action', 'set_default',
    'view_id', (
      select payload #>> '{views,0,id}'
      from operational_rpc_results where name = 'view_created'
    ),
    'expected_version', 1,
    'idempotency_key', 'ops-saved-view-default-001'
  )) #>> '{views,0,is_default}',
  'true',
  'saved view can become the single default'
);
select is(
  public.creator_saved_work_views(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'action', 'delete',
    'view_id', (
      select payload #>> '{views,0,id}'
      from operational_rpc_results where name = 'view_created'
    ),
    'expected_version', 2,
    'idempotency_key', 'ops-saved-view-delete-001'
  )) #>> '{views}',
  '[]',
  'saved view delete returns the refreshed list'
);

select is(
  public.creator_notifications(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001'
  )) #>> '{counts,unread}',
  '3',
  'notification list reports unread count'
);
select is(
  (
    select item ->> 'deep_link'
    from jsonb_array_elements(
      public.creator_notifications(jsonb_build_object(
        'organization_id', '96100000-0000-4000-8000-000000000001'
      )) -> 'items'
    ) item
    where item ->> 'kind' = 'work_ready'
  ),
  '#/workspace/review?review=96400000-0000-4000-8000-000000000001',
  'notification list returns the safe deep link'
);
insert into operational_rpc_results (name, payload)
values (
  'notification_read',
  public.creator_mark_notifications_read(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'notification_ids', jsonb_build_array((
      select id
      from content_factory.user_notifications notification
      where notification.organization_id =
        '96100000-0000-4000-8000-000000000001'
        and notification.kind = 'work_ready'
    )),
    'idempotency_key', 'ops-notification-read-0001'
  ))
);
select is(
  (select payload #>> '{updated_count}'
   from operational_rpc_results where name = 'notification_read'),
  '1',
  'mark read reports one changed notification'
);
select is(
  jsonb_array_length(public.creator_notifications(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'unread_only', true
  )) -> 'items'),
  2,
  'selected mark read leaves other unread notifications untouched'
);
insert into operational_rpc_results (name, payload)
values (
  'notifications_all_read',
  public.creator_mark_notifications_read(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'all_unread', true,
    'idempotency_key', 'ops-notification-all-read-001'
  ))
);
select is(
  (select payload #>> '{updated_count}'
   from operational_rpc_results where name = 'notifications_all_read'),
  '2',
  'mark all unread updates every remaining server-side notification'
);
select is(
  public.creator_notifications(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001'
  )) #>> '{counts,unread}',
  '0',
  'mark all unread leaves no unread server-side notifications'
);
select is(
  public.creator_mark_notifications_read(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'notification_ids', jsonb_build_array((
      select id
      from content_factory.user_notifications notification
      where notification.organization_id =
        '96100000-0000-4000-8000-000000000001'
        and notification.kind = 'work_ready'
    )),
    'idempotency_key', 'ops-notification-read-0001'
  ))::text,
  (select payload::text
   from operational_rpc_results where name = 'notification_read'),
  'notification mark replay returns its original result'
);

insert into operational_rpc_results (name, payload)
values (
  'my_work',
  public.creator_my_work(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'page_size', 100
  ))
);
select ok(
  (select (payload #>> '{counts,task}')::integer >= 2
   from operational_rpc_results where name = 'my_work'),
  'my work includes assigned tasks'
);
select is(
  (select payload #>> '{counts,generation}'
   from operational_rpc_results where name = 'my_work'),
  '1',
  'my work includes active generation'
);
select is(
  (select payload #>> '{counts,review}'
   from operational_rpc_results where name = 'my_work'),
  '1',
  'my work includes pending content review'
);
select is(
  (select payload #>> '{counts,placement}'
   from operational_rpc_results where name = 'my_work'),
  '1',
  'my work includes placement'
);
select is(
  (select payload #>> '{counts,payout}'
   from operational_rpc_results where name = 'my_work'),
  '1',
  'my work includes payout'
);
select is(
  public.creator_my_work(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'item_types', '["generation"]'::jsonb,
    'statuses', '["queued"]'::jsonb
  )) #>> '{counts,total}',
  '1',
  'my work applies type and status filters before counts'
);
select is(
  public.creator_my_work(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'query', 'operational payout'
  )) #>> '{counts,payout}',
  '1',
  'my work query searches payout task title'
);
select ok(
  public.creator_my_work(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000001',
    'page_size', 1
  )) -> 'next_cursor' <> 'null'::jsonb,
  'my work returns a keyset cursor when another page exists'
);
select throws_ok(
  $$
    select public.creator_my_work(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001',
      'item_types', '["unknown"]'::jsonb
    ))
  $$,
  '22023',
  'work_item_type_invalid',
  'my work rejects unknown item types'
);

select set_config(
  'request.jwt.claim.sub',
  '96000000-0000-4000-8000-000000000002',
  true
);
select is(
  public.creator_notifications(jsonb_build_object(
    'organization_id', '96100000-0000-4000-8000-000000000002'
  )) #>> '{counts,total}',
  '1',
  'other member sees only the other organization notification'
);
select throws_ok(
  $$
    select public.creator_notifications(jsonb_build_object(
      'organization_id', '96100000-0000-4000-8000-000000000001'
    ))
  $$,
  '42501',
  'active_membership_required',
  'organization boundary rejects notification access'
);

select set_config(
  'request.jwt.claim.sub',
  '96000000-0000-4000-8000-000000000001',
  true
);
select throws_ok(
  $$
    update content_factory.training_walkthrough_progress
    set position_seconds = 1
    where organization_id =
      '96100000-0000-4000-8000-000000000001'
  $$,
  '55000',
  'training_progress_regression_forbidden',
  'trigger blocks server-side progress regression'
);
select throws_ok(
  $$
    delete from content_factory.user_notifications
    where organization_id =
      '96100000-0000-4000-8000-000000000001'
  $$,
  '55000',
  'notification_deletion_forbidden',
  'notification audit history cannot be deleted'
);

select * from finish();
rollback;

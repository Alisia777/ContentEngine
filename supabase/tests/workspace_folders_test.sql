begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

create or replace function pg_temp.grant_refreshed_course_gate(
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
    select module.code,
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
      left(
        'course-check:' || p_key_prefix || ':' || module_row.code,
        180
      )
    )
    on conflict (organization_id, profile_id, idempotency_key)
    do update set
      module_code = excluded.module_code,
      status = excluded.status,
      score = excluded.score,
      correct_count = excluded.correct_count,
      answered_count = excluded.answered_count,
      question_count = excluded.question_count,
      passed = excluded.passed,
      answers = excluded.answers,
      request_hash = excluded.request_hash,
      completed_at = now()
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code,
      attempt_id, status
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      attempt_id_value,
      'passed'
    )
    on conflict on constraint
      training_certifications_org_profile_module_uq
    do update set
      attempt_id = excluded.attempt_id,
      status = 'passed',
      granted_at = now(),
      expires_at = null;
  end loop;
end;
$course_gate_fixture$;

create or replace function pg_temp.grant_final_exam_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $final_gate_fixture$
declare
  attempt_id_value uuid;
  question_count_value integer;
begin
  select module.question_count
    into question_count_value
  from content_factory.training_modules module
  where module.code = 'operator_final_exam'
    and module.module_type = 'exam'
    and module.is_active;

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
    question_count_value,
    question_count_value,
    question_count_value,
    true,
    '{}'::jsonb,
    content_factory_private.json_hash(jsonb_build_object(
      'profile_id', p_profile_id,
      'exam', 'operator_final_exam'
    )),
    left('workspace-final:' || p_key_prefix, 180)
  )
  on conflict (organization_id, profile_id, idempotency_key)
  do update set
    status = 'completed',
    score = 1,
    correct_count = excluded.correct_count,
    answered_count = excluded.answered_count,
    question_count = excluded.question_count,
    passed = true,
    completed_at = now()
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code,
    attempt_id, status
  ) values (
    p_organization_id,
    p_profile_id,
    'operator_final_exam',
    attempt_id_value,
    'passed'
  )
  on conflict on constraint training_certifications_org_profile_module_uq
  do update set
    attempt_id = excluded.attempt_id,
    status = 'passed',
    granted_at = now(),
    expires_at = null;
end;
$final_gate_fixture$;

select plan(68);

select has_table(
  'content_factory',
  'workspace_folders',
  'workspace folders table exists'
);
select has_table(
  'content_factory',
  'workspace_media_locations',
  'workspace media locations table exists'
);
select has_table(
  'content_factory',
  'workspace_task_locations',
  'workspace task locations table exists'
);
select has_column(
  'content_factory',
  'workspace_folders',
  'version',
  'folders carry an optimistic concurrency version'
);
select has_column(
  'content_factory',
  'workspace_media_locations',
  'folder_id',
  'media locations carry a logical folder'
);
select has_column(
  'content_factory',
  'workspace_task_locations',
  'folder_id',
  'task locations carry a logical folder'
);

select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'content_factory.workspace_folders'::regclass
  ),
  'workspace folders use RLS'
);
select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'content_factory.workspace_media_locations'::regclass
  ),
  'workspace media locations use RLS'
);
select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'content_factory.workspace_task_locations'::regclass
  ),
  'workspace task locations use RLS'
);

select is(
  (
    select count(*)::integer
    from (values
      ('content_factory.workspace_folders'::regclass),
      ('content_factory.workspace_media_locations'::regclass),
      ('content_factory.workspace_task_locations'::regclass)
    ) protected(table_oid)
    where has_table_privilege(
      'authenticated',
      protected.table_oid,
      'select,insert,update,delete'
    )
  ),
  0,
  'authenticated has no direct workspace table privileges'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_workspace_browser',
        'creator_create_workspace_folder',
        'creator_update_workspace_folder',
        'creator_move_workspace_items'
      )
      and pg_get_function_identity_arguments(procedure.oid) =
        'p_payload jsonb'
  ),
  4,
  'four one-payload workspace RPCs exist'
);
select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_workspace_browser',
        'creator_create_workspace_folder',
        'creator_update_workspace_folder',
        'creator_move_workspace_items'
      )
      and has_function_privilege(
        'authenticated',
        procedure.oid,
        'execute'
      )
  ),
  4,
  'authenticated can execute all workspace RPCs'
);
select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'creator_workspace_browser',
        'creator_create_workspace_folder',
        'creator_update_workspace_folder',
        'creator_move_workspace_items'
      )
      and has_function_privilege('anon', procedure.oid, 'execute')
  ),
  0,
  'anonymous sessions cannot execute workspace RPCs'
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
    '94000000-0000-4000-8000-000000000001',
    'workspace-owner@example.test',
    'Workspace Owner'
  ),
  (
    '94000000-0000-4000-8000-000000000002',
    'workspace-operator@example.test',
    'Workspace Operator'
  ),
  (
    '94000000-0000-4000-8000-000000000003',
    'workspace-other-operator@example.test',
    'Other Operator'
  ),
  (
    '94000000-0000-4000-8000-000000000004',
    'workspace-viewer@example.test',
    'Workspace Viewer'
  ),
  (
    '94000000-0000-4000-8000-000000000005',
    'workspace-outsider@example.test',
    'Workspace Outsider'
  ),
  (
    '94000000-0000-4000-8000-000000000006',
    'workspace-uncertified@example.test',
    'Uncertified Producer'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (
  id, name, slug, status
) values
  (
    '94100000-0000-4000-8000-000000000001',
    'Workspace Main',
    'workspace-main',
    'active'
  ),
  (
    '94100000-0000-4000-8000-000000000002',
    'Workspace Other',
    'workspace-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    'owner',
    'active'
  ),
  (
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000002',
    'operator',
    'active'
  ),
  (
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000003',
    'operator',
    'active'
  ),
  (
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000004',
    'viewer',
    'active'
  ),
  (
    '94100000-0000-4000-8000-000000000002',
    '94000000-0000-4000-8000-000000000005',
    'owner',
    'active'
  ),
  (
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000006',
    'producer',
    'active'
  );

do $$
begin
  perform pg_temp.grant_refreshed_course_gate(
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    'workspace-owner'
  );
  perform pg_temp.grant_final_exam_gate(
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    'workspace-owner'
  );
  perform pg_temp.grant_refreshed_course_gate(
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000002',
    'workspace-operator'
  );
  perform pg_temp.grant_final_exam_gate(
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000002',
    'workspace-operator'
  );
  perform pg_temp.grant_refreshed_course_gate(
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000003',
    'workspace-other-operator'
  );
  perform pg_temp.grant_final_exam_gate(
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000003',
    'workspace-other-operator'
  );
  perform pg_temp.grant_refreshed_course_gate(
    '94100000-0000-4000-8000-000000000002',
    '94000000-0000-4000-8000-000000000005',
    'workspace-outsider'
  );
  perform pg_temp.grant_final_exam_gate(
    '94100000-0000-4000-8000-000000000002',
    '94000000-0000-4000-8000-000000000005',
    'workspace-outsider'
  );
end;
$$;

insert into content_factory.media_objects (
  id, organization_id, owner_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata,
  idempotency_key
) values
  (
    '94200000-0000-4000-8000-000000000001',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    'contentengine-private',
    '94100000-0000-4000-8000-000000000001/94000000-0000-4000-8000-000000000001/workspace/owner-photo.webp',
    'image/webp',
    100,
    repeat('1', 64),
    'ready',
    '{"kind":"creator_reference","original_filename":"owner-photo.webp"}',
    'workspace-owner-photo-0001'
  ),
  (
    '94200000-0000-4000-8000-000000000002',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    'contentengine-private',
    '94100000-0000-4000-8000-000000000001/94000000-0000-4000-8000-000000000001/workspace/generated-video.mp4',
    'video/mp4',
    200,
    repeat('2', 64),
    'ready',
    '{"kind":"generated_video","original_filename":"generated-video.mp4"}',
    'workspace-generated-video-0001'
  ),
  (
    '94200000-0000-4000-8000-000000000003',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000002',
    'contentengine-private',
    '94100000-0000-4000-8000-000000000001/94000000-0000-4000-8000-000000000002/workspace/operator-video.mp4',
    'video/mp4',
    300,
    repeat('3', 64),
    'ready',
    '{"kind":"source_video","original_filename":"operator-video.mp4"}',
    'workspace-operator-video-0001'
  ),
  (
    '94200000-0000-4000-8000-000000000004',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000003',
    'contentengine-private',
    '94100000-0000-4000-8000-000000000001/94000000-0000-4000-8000-000000000003/workspace/other-photo.webp',
    'image/webp',
    400,
    repeat('4', 64),
    'ready',
    '{"kind":"packshot","original_filename":"other-photo.webp"}',
    'workspace-other-photo-0001'
  ),
  (
    '94200000-0000-4000-8000-000000000005',
    '94100000-0000-4000-8000-000000000002',
    '94000000-0000-4000-8000-000000000005',
    'contentengine-private',
    '94100000-0000-4000-8000-000000000002/94000000-0000-4000-8000-000000000005/workspace/outsider-photo.webp',
    'image/webp',
    500,
    repeat('5', 64),
    'ready',
    '{"kind":"packshot","original_filename":"outsider-photo.webp"}',
    'workspace-outsider-photo-0001'
  );

insert into content_factory.creator_tasks (
  id, organization_id, assignee_id, created_by,
  task_type, title, instructions, status, priority,
  payout_minor, result, idempotency_key
) values
  (
    '94300000-0000-4000-8000-000000000001',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001',
    'general',
    'Owner workspace task',
    'Keep the task business state unchanged.',
    'todo',
    3,
    0,
    '{"checklist":["one"]}',
    'workspace-owner-task-0001'
  ),
  (
    '94300000-0000-4000-8000-000000000002',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000002',
    '94000000-0000-4000-8000-000000000001',
    'video_review',
    'Operator workspace task',
    'Review an exact video.',
    'in_progress',
    2,
    0,
    '{"review":"pending"}',
    'workspace-operator-task-0001'
  ),
  (
    '94300000-0000-4000-8000-000000000003',
    '94100000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000003',
    '94000000-0000-4000-8000-000000000001',
    'general',
    'Other operator task',
    'This task is not assigned to the current operator.',
    'todo',
    3,
    0,
    '{}',
    'workspace-other-task-0001'
  ),
  (
    '94300000-0000-4000-8000-000000000004',
    '94100000-0000-4000-8000-000000000002',
    '94000000-0000-4000-8000-000000000005',
    '94000000-0000-4000-8000-000000000005',
    'general',
    'Outsider task',
    'This belongs to another organization.',
    'todo',
    3,
    0,
    '{}',
    'workspace-outsider-task-0001'
  );

select is(
  (
    select count(*)::integer
    from content_factory.workspace_media_locations location
    where location.media_object_id in (
      '94200000-0000-4000-8000-000000000001',
      '94200000-0000-4000-8000-000000000002',
      '94200000-0000-4000-8000-000000000003',
      '94200000-0000-4000-8000-000000000004',
      '94200000-0000-4000-8000-000000000005'
    )
      and location.folder_id is null
  ),
  5,
  'new media automatically receives one root location'
);
select is(
  (
    select count(*)::integer
    from content_factory.workspace_task_locations location
    where location.task_id in (
      '94300000-0000-4000-8000-000000000001',
      '94300000-0000-4000-8000-000000000002',
      '94300000-0000-4000-8000-000000000003',
      '94300000-0000-4000-8000-000000000004'
    )
      and location.folder_id is null
  ),
  4,
  'new tasks automatically receive one root location'
);
select is(
  (
    select count(*)::integer
    from content_factory.workspace_media_locations location
    where location.media_object_id =
      '94200000-0000-4000-8000-000000000002'
  ),
  1,
  'a generated video is an ordinary single workspace media item'
);

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '94000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

create temporary table workspace_test_context (
  root_result jsonb,
  root_folder_id uuid,
  nested_result jsonb,
  nested_folder_id uuid,
  empty_result jsonb,
  empty_folder_id uuid,
  original_media_object_name text,
  original_media_sha text,
  original_task_status text,
  original_task_result jsonb,
  original_task_updated_at timestamptz,
  operator_location_before uuid
) on commit drop;

insert into workspace_test_context (
  original_media_object_name,
  original_media_sha,
  original_task_status,
  original_task_result,
  original_task_updated_at
)
select
  media.object_name,
  media.sha256,
  task.status,
  task.result,
  task.updated_at
from content_factory.media_objects media
cross join content_factory.creator_tasks task
where media.id = '94200000-0000-4000-8000-000000000001'
  and task.id = '94300000-0000-4000-8000-000000000002';

update workspace_test_context
set root_result = public.creator_create_workspace_folder(
  jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-create-root-0001',
    'name', 'Campaign assets',
    'color_token', 'gold'
  )
);
update workspace_test_context
set root_folder_id = (root_result -> 'folder' ->> 'id')::uuid;

select ok(
  (
    select (root_result ->> 'ok')::boolean
    from workspace_test_context
  ),
  'owner creates a root workspace folder'
);
select is(
  (
    select root_result -> 'folder' ->> 'color_token'
    from workspace_test_context
  ),
  'gold',
  'create returns the validated color token'
);
select is(
  (
    public.creator_create_workspace_folder(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-create-root-0001',
      'name', 'Campaign assets',
      'color_token', 'gold'
    )) -> 'folder' ->> 'id'
  )::uuid,
  (
    select root_folder_id
    from workspace_test_context
  ),
  'folder creation retry returns the same folder'
);
select is(
  (
    select count(*)::integer
    from content_factory.workspace_folders folder
    where folder.organization_id =
      '94100000-0000-4000-8000-000000000001'
      and lower(folder.name) = 'campaign assets'
  ),
  1,
  'idempotent create stores one folder'
);
select is(
  (
    select count(*)::integer
    from content_factory.factory_events event
    where event.organization_id =
      '94100000-0000-4000-8000-000000000001'
      and event.event_name = 'workspace_folder_created'
      and event.idempotency_key =
        'workspace_folder_create:workspace-create-root-0001'
  ),
  1,
  'folder creation emits one durable event'
);

select throws_ok(
  $$select public.creator_create_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-create-root-0001',
    'name', 'Changed retry'
  ))$$,
  '23505',
  'idempotency_key_conflict',
  'same create key cannot carry a different request'
);
select throws_ok(
  $$select public.creator_create_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-create-duplicate-0001',
    'name', '  CAMPAIGN ASSETS  '
  ))$$,
  '23505',
  'workspace_folder_name_conflict',
  'active sibling names are unique case-insensitively'
);

update workspace_test_context
set nested_result = public.creator_create_workspace_folder(
  jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-create-nested-0001',
    'name', 'Ready videos',
    'parent_id', root_folder_id
  )
);
update workspace_test_context
set nested_folder_id = (nested_result -> 'folder' ->> 'id')::uuid;

select is(
  (
    select nested_result -> 'folder' ->> 'parent_id'
    from workspace_test_context
  )::uuid,
  (
    select root_folder_id
    from workspace_test_context
  ),
  'nested folder is linked to its same-organization parent'
);

select ok(
  (
    public.creator_create_workspace_folder(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-create-same-name-nested-0001',
      'name', 'Campaign assets',
      'parent_id', (
        select nested_folder_id
        from workspace_test_context
      )
    )) ->> 'ok'
  )::boolean,
  'the same name is allowed below a different parent'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token,
  status, position, created_by, updated_by
) values
  (
    '94400000-0000-4000-8000-000000000001',
    '94100000-0000-4000-8000-000000000001',
    null,
    'Depth 1',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000002',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000001',
    'Depth 2',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000003',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000002',
    'Depth 3',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000004',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000003',
    'Depth 4',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000005',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000004',
    'Depth 5',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000006',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000005',
    'Depth 6',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000007',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000006',
    'Depth 7',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  ),
  (
    '94400000-0000-4000-8000-000000000008',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000007',
    'Depth 8',
    'slate',
    'active',
    1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  );

select is(
  (
    with recursive tree as (
      select folder.id, folder.parent_id, 1 as depth
      from content_factory.workspace_folders folder
      where folder.id = '94400000-0000-4000-8000-000000000001'
      union all
      select child.id, child.parent_id, tree.depth + 1
      from tree
      join content_factory.workspace_folders child
        on child.parent_id = tree.id
      where child.id between
        '94400000-0000-4000-8000-000000000002'
        and '94400000-0000-4000-8000-000000000008'
    )
    select max(tree.depth)
    from tree
  ),
  8,
  'folder hierarchy accepts the exact depth-eight boundary'
);
select throws_ok(
  $$insert into content_factory.workspace_folders (
    id, organization_id, parent_id, name, color_token,
    status, position, created_by, updated_by
  ) values (
    '94400000-0000-4000-8000-000000000009',
    '94100000-0000-4000-8000-000000000001',
    '94400000-0000-4000-8000-000000000008',
    'Depth 9', 'slate', 'active', 1,
    '94000000-0000-4000-8000-000000000001',
    '94000000-0000-4000-8000-000000000001'
  )$$,
  '54000',
  'workspace_folder_depth_exceeded',
  'folder hierarchy rejects depth nine'
);
select throws_ok(
  $$update content_factory.workspace_folders
    set parent_id = '94400000-0000-4000-8000-000000000008'
    where id = '94400000-0000-4000-8000-000000000001'$$,
  '55000',
  'workspace_folder_cycle',
  'folder hierarchy rejects a descendant cycle'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token,
  status, position, created_by, updated_by
) values (
  '94400000-0000-4000-8000-000000000010',
  '94100000-0000-4000-8000-000000000002',
  null,
  'Other organization folder',
  'slate',
  'active',
  1,
  '94000000-0000-4000-8000-000000000005',
  '94000000-0000-4000-8000-000000000005'
);

select throws_ok(
  $$select public.creator_create_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-cross-org-parent-0001',
    'name', 'Invalid cross org child',
    'parent_id', '94400000-0000-4000-8000-000000000010'
  ))$$,
  'P0002',
  'workspace_folder_parent_not_found',
  'cross-organization parent is indistinguishable from missing'
);

select is(
  (
    public.creator_update_workspace_folder(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-rename-root-0001',
      'folder_id', (
        select root_folder_id
        from workspace_test_context
      ),
      'expected_version', 1,
      'name', 'Campaign production',
      'color_token', 'violet'
    )) -> 'folder' ->> 'version'
  )::bigint,
  2::bigint,
  'folder update increments the optimistic version'
);
select throws_ok(
  $$select public.creator_update_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-stale-version-0001',
    'folder_id', (
      select root_folder_id
      from workspace_test_context
    ),
    'expected_version', 1,
    'name', 'Stale update'
  ))$$,
  '40001',
  'workspace_folder_version_conflict',
  'stale folder edits fail with a stable conflict'
);

select is(
  (
    public.creator_move_workspace_items(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-owner-mixed-move-0001',
      'destination_folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'items', jsonb_build_array(
        jsonb_build_object(
          'type', 'media',
          'id', '94200000-0000-4000-8000-000000000001'
        ),
        jsonb_build_object(
          'type', 'task',
          'id', '94300000-0000-4000-8000-000000000002'
        )
      )
    )) ->> 'moved_count'
  )::integer,
  2,
  'manager moves a mixed media and task batch'
);
select is(
  (
    select count(*)::integer
    from (
      select location.folder_id
      from content_factory.workspace_media_locations location
      where location.media_object_id =
        '94200000-0000-4000-8000-000000000001'
      union all
      select location.folder_id
      from content_factory.workspace_task_locations location
      where location.task_id =
        '94300000-0000-4000-8000-000000000002'
    ) moved
    where moved.folder_id = (
      select nested_folder_id
      from workspace_test_context
    )
  ),
  2,
  'both mixed items receive the exact logical destination'
);
select is(
  (
    public.creator_move_workspace_items(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-owner-mixed-move-0001',
      'destination_folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'items', jsonb_build_array(
        jsonb_build_object(
          'type', 'media',
          'id', '94200000-0000-4000-8000-000000000001'
        ),
        jsonb_build_object(
          'type', 'task',
          'id', '94300000-0000-4000-8000-000000000002'
        )
      )
    )) ->> 'moved_count'
  )::integer,
  2,
  'move retry returns the original result'
);
select is(
  (
    select count(*)::integer
    from content_factory.factory_events event
    where event.organization_id =
      '94100000-0000-4000-8000-000000000001'
      and event.event_name = 'workspace_items_moved'
      and event.idempotency_key =
        'workspace_items_move:workspace-owner-mixed-move-0001'
  ),
  1,
  'move retry emits one event'
);
select is(
  (
    select media.object_name
    from content_factory.media_objects media
    where media.id = '94200000-0000-4000-8000-000000000001'
  ),
  (
    select original_media_object_name
    from workspace_test_context
  ),
  'logical movement never changes the physical object name'
);
select is(
  (
    select media.sha256
    from content_factory.media_objects media
    where media.id = '94200000-0000-4000-8000-000000000001'
  ),
  (
    select original_media_sha
    from workspace_test_context
  ),
  'logical movement never changes the media checksum'
);
select is(
  (
    select task.status
    from content_factory.creator_tasks task
    where task.id = '94300000-0000-4000-8000-000000000002'
  ),
  (
    select original_task_status
    from workspace_test_context
  ),
  'logical movement never changes task status'
);
select is(
  (
    select task.result
    from content_factory.creator_tasks task
    where task.id = '94300000-0000-4000-8000-000000000002'
  ),
  (
    select original_task_result
    from workspace_test_context
  ),
  'logical movement never changes task result'
);
select is(
  (
    select task.updated_at
    from content_factory.creator_tasks task
    where task.id = '94300000-0000-4000-8000-000000000002'
  ),
  (
    select original_task_updated_at
    from workspace_test_context
  ),
  'logical movement never touches task updated_at'
);

select is(
  (
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', (
        select nested_folder_id
        from workspace_test_context
      )
    )) -> 'items'
  ) @> jsonb_build_array(
    jsonb_build_object(
      'type', 'media',
      'id', '94200000-0000-4000-8000-000000000001'
    ),
    jsonb_build_object(
      'type', 'task',
      'id', '94300000-0000-4000-8000-000000000002'
    )
  ),
  true,
  'browser returns mixed folder contents'
);
select is(
  jsonb_array_length(
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'entity_types', jsonb_build_array('media')
    )) -> 'items'
  ),
  1,
  'browser entity filter returns only media'
);
select is(
  jsonb_array_length(
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'search', 'Operator workspace'
    )) -> 'items'
  ),
  1,
  'browser search finds an exact task title'
);
select is(
  jsonb_array_length(
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'search', '94300000-0000-4000-8000-000000000002'
    )) -> 'items'
  ),
  1,
  'browser search finds an exact task identifier'
);
select is(
  (
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'page_size', 1
    )) #>> '{_meta,has_more}'
  )::boolean,
  true,
  'workspace keyset page reports more mixed items'
);
select is(
  jsonb_array_length(
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'page_size', 1,
      'cursor', (
        public.creator_workspace_browser(jsonb_build_object(
          'organization_id', '94100000-0000-4000-8000-000000000001',
          'folder_id', (
            select nested_folder_id
            from workspace_test_context
          ),
          'page_size', 1
        )) #> '{_meta,next_cursor}'
      )
    )) -> 'items'
  ),
  1,
  'workspace keyset cursor reaches the next item'
);

select throws_ok(
  $$select public.creator_update_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-archive-nonempty-0001',
    'folder_id', (
      select nested_folder_id
      from workspace_test_context
    ),
    'expected_version', 1,
    'archive', true
  ))$$,
  '55000',
  'workspace_folder_not_empty',
  'a nonempty folder cannot be archived'
);

update workspace_test_context
set empty_result = public.creator_create_workspace_folder(
  jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-create-empty-0001',
    'name', 'Empty archive candidate'
  )
);
update workspace_test_context
set empty_folder_id = (empty_result -> 'folder' ->> 'id')::uuid;

select is(
  (
    public.creator_update_workspace_folder(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-archive-empty-0001',
      'folder_id', (
        select empty_folder_id
        from workspace_test_context
      ),
      'expected_version', 1,
      'archive', true
    )) -> 'folder' ->> 'status'
  ),
  'archived',
  'an empty folder can be archived'
);
select throws_ok(
  $$select public.creator_move_workspace_items(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-move-archived-0001',
    'destination_folder_id', (
      select empty_folder_id
      from workspace_test_context
    ),
    'items', jsonb_build_array(jsonb_build_object(
      'type', 'media',
      'id', '94200000-0000-4000-8000-000000000002'
    ))
  ))$$,
  'P0002',
  'workspace_folder_not_found',
  'archived folders cannot receive moved items'
);

select is(
  (
    public.creator_move_workspace_items(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-move-root-0001',
      'items', jsonb_build_array(jsonb_build_object(
        'type', 'media',
        'id', '94200000-0000-4000-8000-000000000001'
      ))
    )) ->> 'destination_folder_id'
  ),
  null,
  'omitting destination moves an item back to root'
);
select is(
  (
    select location.folder_id
    from content_factory.workspace_media_locations location
    where location.media_object_id =
      '94200000-0000-4000-8000-000000000001'
  ),
  null,
  'root is represented by a null logical folder only'
);
select is(
  (
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001'
    )) -> 'items'
  ) @> jsonb_build_array(jsonb_build_object(
    'type', 'task',
    'id', '94300000-0000-4000-8000-000000000002'
  )),
  true,
  'omitting folder_id returns accessible items from every folder'
);
select is(
  (
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'folder_id', null
    )) -> 'items'
  ) @> jsonb_build_array(jsonb_build_object(
    'type', 'task',
    'id', '94300000-0000-4000-8000-000000000002'
  )),
  false,
  'explicit null folder_id excludes items stored below a folder'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.creator_workspace_browser(jsonb_build_object(
        'organization_id', '94100000-0000-4000-8000-000000000001',
        'folder_id', null
      )) -> 'items'
    ) item(value)
    where item.value -> 'folder_id' is distinct from 'null'::jsonb
  ),
  'explicit null folder_id returns root locations only'
);
select is(
  (
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001'
    )) #>> '{capabilities,manage_folders}'
  )::boolean,
  true,
  'owner receives the manage-folders capability'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.creator_workspace_browser(jsonb_build_object(
        'organization_id', '94100000-0000-4000-8000-000000000001'
      )) -> 'folders'
    ) folder(value)
    where (folder.value ->> 'can_edit')::boolean is distinct from true
  ),
  'owner receives editable folder records'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '94000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select is(
  (
    public.creator_workspace_browser(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001'
    )) #>> '{capabilities,manage_folders}'
  )::boolean,
  false,
  'operator can move items but cannot manage shared folders'
);

select is(
  (
    public.creator_move_workspace_items(jsonb_build_object(
      'organization_id', '94100000-0000-4000-8000-000000000001',
      'idempotency_key', 'workspace-operator-own-move-0001',
      'destination_folder_id', (
        select nested_folder_id
        from workspace_test_context
      ),
      'items', jsonb_build_array(
        jsonb_build_object(
          'type', 'media',
          'id', '94200000-0000-4000-8000-000000000003'
        ),
        jsonb_build_object(
          'type', 'task',
          'id', '94300000-0000-4000-8000-000000000002'
        )
      )
    )) ->> 'moved_count'
  )::integer,
  2,
  'operator moves owned media and assigned task'
);

update workspace_test_context
set operator_location_before = (
  select location.folder_id
  from content_factory.workspace_media_locations location
  where location.media_object_id =
    '94200000-0000-4000-8000-000000000003'
);

select throws_ok(
  $$select public.creator_move_workspace_items(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-operator-foreign-batch-0001',
    'items', jsonb_build_array(
      jsonb_build_object(
        'type', 'media',
        'id', '94200000-0000-4000-8000-000000000003'
      ),
      jsonb_build_object(
        'type', 'media',
        'id', '94200000-0000-4000-8000-000000000004'
      )
    )
  ))$$,
  '42501',
  'workspace_item_access_denied',
  'operator cannot move another operator media'
);
select is(
  (
    select location.folder_id
    from content_factory.workspace_media_locations location
    where location.media_object_id =
      '94200000-0000-4000-8000-000000000003'
  ),
  (
    select operator_location_before
    from workspace_test_context
  ),
  'a rejected mixed-access batch changes no locations'
);
select throws_ok(
  $$select public.creator_create_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-operator-create-denied-0001',
    'name', 'Operator cannot create'
  ))$$,
  '42501',
  'role_not_allowed',
  'operator cannot mutate the shared folder structure'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '94000000-0000-4000-8000-000000000004',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_workspace_browser(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001'
  ))$$,
  '42501',
  'role_not_allowed',
  'viewer cannot enter the certified workspace browser'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '94000000-0000-4000-8000-000000000006',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_workspace_browser(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001'
  ))$$,
  '42501',
  'final_exam_required',
  'uncertified producer cannot enter the workspace browser'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '94000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_move_workspace_items(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-cross-org-item-0001',
    'items', jsonb_build_array(jsonb_build_object(
      'type', 'media',
      'id', '94200000-0000-4000-8000-000000000005'
    ))
  ))$$,
  '42501',
  'workspace_item_access_denied',
  'cross-organization media is indistinguishable from inaccessible'
);
select throws_ok(
  $$select public.creator_move_workspace_items(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-duplicate-items-0001',
    'items', jsonb_build_array(
      jsonb_build_object(
        'type', 'task',
        'id', '94300000-0000-4000-8000-000000000001'
      ),
      jsonb_build_object(
        'type', 'task',
        'id', '94300000-0000-4000-8000-000000000001'
      )
    )
  ))$$,
  '22023',
  'workspace_items_duplicate',
  'move rejects duplicate item references'
);
select throws_ok(
  $$select public.creator_move_workspace_items(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-invalid-type-0001',
    'items', jsonb_build_array(jsonb_build_object(
      'type', 'placement',
      'id', '94300000-0000-4000-8000-000000000001'
    ))
  ))$$,
  '22023',
  'workspace_items_invalid',
  'move rejects unsupported entity types'
);
select throws_ok(
  $$select public.creator_workspace_browser(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'page_size', 101
  ))$$,
  '22023',
  'workspace_page_size_invalid',
  'workspace browser enforces its page cap'
);
select throws_ok(
  $$select public.creator_create_workspace_folder(jsonb_build_object(
    'organization_id', '94100000-0000-4000-8000-000000000001',
    'idempotency_key', 'workspace-unknown-field-0001',
    'name', 'Strict payload',
    'unexpected', true
  ))$$,
  '22023',
  'workspace_folder_create_payload_invalid',
  'folder creation rejects unknown payload fields'
);

select * from finish();
rollback;

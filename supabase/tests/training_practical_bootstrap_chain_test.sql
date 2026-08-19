begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(19);

-- ---------------------------------------------------------------------------
-- Chain wiring contract.  Mirrors the verification DO block in
-- 202608170001_restore_training_practical_bootstrap_chain.sql so the exact
-- cloud regression (pre_training_waiver holding the password-gate body and
-- bypassing the practical + sanitizer layers) can never land silently again.
-- ---------------------------------------------------------------------------

select ok(
  strpos(
    pg_get_functiondef('public.creator_bootstrap(jsonb)'::regprocedure),
    'creator_bootstrap_pre_training_waiver('
  ) > 0,
  'public creator_bootstrap delegates to the training waiver overlay layer'
);

select ok(
  strpos(
    pg_get_functiondef(
      'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)'
        ::regprocedure
    ),
    'creator_bootstrap_pre_assessment_v5_sanitize('
  ) > 0,
  'course-check sanitizer layer calls the practical project layer'
);

select ok(
  (
    select
      strpos(layer.definition, '- ''attempt_id''') > 0
      and strpos(layer.definition, '- ''correct_count''') > 0
      and strpos(layer.definition, '- ''critical_error_count''') > 0
      and strpos(layer.definition, '- ''score_percent''') > 0
      and strpos(layer.definition, '- ''review_topics''') > 0
    from (
      select pg_get_functiondef(
        'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)'
          ::regprocedure
      ) as definition
    ) layer
  ),
  'sanitizer layer strips every course-check grading diagnostic key'
);

select ok(
  strpos(
    pg_get_functiondef(
      'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)'
        ::regprocedure
    ),
    'creator_bootstrap_pre_auth_email_gate('
  ) = 0,
  'sanitizer layer does not bypass the practical layer (cloud regression)'
);

select ok(
  (
    select
      strpos(layer.definition, 'creator_bootstrap_pre_practical_gate(') > 0
      and strpos(layer.definition, 'practical_project') > 0
      and strpos(layer.definition, 'training_practical_gate_satisfied(') > 0
      and strpos(layer.definition, 'contentengine-training') > 0
    from (
      select pg_get_functiondef(
        'content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)'
          ::regprocedure
      ) as definition
    ) layer
  ),
  'practical layer emits practical state, approval gate and upload settings'
);

select ok(
  (
    select
      strpos(layer.definition, 'creator_bootstrap_pre_auth_email_gate(') > 0
      and strpos(layer.definition, 'auth_password_change_required(') > 0
    from (
      select pg_get_functiondef(
        'content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)'
          ::regprocedure
      ) as definition
    ) layer
  ),
  'password gate layer wraps the auth email gate'
);

select ok(
  strpos(
    pg_get_functiondef(
      'content_factory_private.creator_bootstrap_pre_auth_email_gate(jsonb)'
        ::regprocedure
    ),
    'creator_bootstrap_pre_course_gate('
  ) > 0,
  'auth email gate layer wraps the refreshed course gate'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)',
    'execute'
  ),
  'authenticated cannot execute the private bootstrap chain layers directly'
);

-- ---------------------------------------------------------------------------
-- Behavioral contract.  A learner who passed all four courses but has no
-- approved practical project must see the practical step (upload settings,
-- required flag, blocked exam) in bootstrap; after an owner approval the
-- exam becomes available again.  Fixtures mirror
-- supabase/tests/training_practical_review_test.sql.
-- ---------------------------------------------------------------------------

create or replace function pg_temp.grant_chain_course_completion(
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
  check_question_count integer;
begin
  for module_row in
    select
      module.code,
      module.question_count,
      module.content
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
      and module.code = any(array[
        'factory_basics',
        'video_quality',
        'publishing_funnel',
        'security_wb'
      ]::text[])
    order by module.order_index
  loop
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
      '{}'::jsonb,
      content_factory_private.json_hash(jsonb_build_object(
        'fixture', p_key_prefix,
        'module_code', module_row.code
      )),
      left('chain-course:' || p_key_prefix || ':' || module_row.code, 180)
    )
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status,
      expires_at
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      attempt_id_value,
      'passed',
      null
    )
    on conflict on constraint
      training_certifications_org_profile_module_uq
    do update set
      attempt_id = excluded.attempt_id,
      status = 'passed',
      granted_at = now(),
      expires_at = null;

    -- The refreshed course gate (creator_bootstrap_pre_auth_email_gate)
    -- accepts only completed passing attempts whose idempotency key starts
    -- with 'course-check:' and whose question_count matches the module
    -- knowledge check.
    check_question_count := jsonb_array_length(
      module_row.content #> '{knowledge_check,questions}'
    );
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
      check_question_count,
      check_question_count,
      check_question_count,
      true,
      '{}'::jsonb,
      content_factory_private.json_hash(jsonb_build_object(
        'fixture', p_key_prefix,
        'course_check', module_row.code
      )),
      left('course-check:' || p_key_prefix || ':' || module_row.code, 180)
    );
  end loop;
end;
$fixture$;

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
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    '98111111-1111-4111-8111-111111111111',
    'chain-owner@example.test',
    'Chain Owner'
  ),
  (
    '98222222-2222-4222-8222-222222222222',
    'chain-learner@example.test',
    'Chain Learner'
  )
) fixture(id, email, display_name);

insert into content_factory.profiles (id, email, display_name, status)
values
  (
    '98111111-1111-4111-8111-111111111111',
    'chain-owner@example.test',
    'Chain Owner',
    'active'
  ),
  (
    '98222222-2222-4222-8222-222222222222',
    'chain-learner@example.test',
    'Chain Learner',
    'active'
  )
on conflict (id) do update set
  email = excluded.email,
  display_name = excluded.display_name,
  status = excluded.status;

insert into content_factory.organizations (id, name, slug, status)
values (
  '98000000-0000-4000-8000-000000000001',
  'Bootstrap Chain Test',
  'bootstrap-chain-test',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '98000000-0000-4000-8000-000000000001',
    '98111111-1111-4111-8111-111111111111',
    'owner',
    'active'
  ),
  (
    '98000000-0000-4000-8000-000000000001',
    '98222222-2222-4222-8222-222222222222',
    'trainee',
    'active'
  );

select pg_temp.grant_chain_course_completion(
  '98000000-0000-4000-8000-000000000001',
  '98222222-2222-4222-8222-222222222222',
  'chain-learner'
);

select set_config(
  'request.jwt.claim.sub',
  '98222222-2222-4222-8222-222222222222',
  true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

create temporary table chain_bootstrap_context (
  bootstrap jsonb not null
) on commit drop;

insert into chain_bootstrap_context (bootstrap)
select public.creator_bootstrap(jsonb_build_object(
  'organization_id', '98000000-0000-4000-8000-000000000001'
));

select is(
  (
    select bootstrap #>> '{training,practical_upload,bucket_id}'
    from chain_bootstrap_context
  ),
  'contentengine-training',
  'learner bootstrap exposes the private practical upload lane'
);

select is(
  (
    select (bootstrap #>> '{learning,practical_project_required}')::boolean
    from chain_bootstrap_context
  ),
  true,
  'practical project is required before approval'
);

select is(
  (
    select bootstrap #>> '{learning,exam,available}'
    from chain_bootstrap_context
  ),
  'false',
  'final exam stays closed while the practical project is unapproved'
);

select is(
  (
    select bootstrap #>> '{learning,exam,blocked_reason}'
    from chain_bootstrap_context
  ),
  'practical_project_approval_required',
  'exam block names the practical approval requirement'
);

select is(
  (
    select jsonb_array_length(bootstrap #> '{learning,course_checks}')
    from chain_bootstrap_context
  ),
  4,
  'bootstrap projects one course check per required course'
);

select ok(
  not exists (
    select 1
    from chain_bootstrap_context context,
      jsonb_array_elements(
        context.bootstrap #> '{learning,course_checks}'
      ) check_item(value)
    where check_item.value ? 'attempt_id'
       or check_item.value ? 'correct_count'
       or check_item.value ? 'critical_error_count'
       or check_item.value ? 'score_percent'
       or check_item.value ? 'review_topics'
  ),
  'course checks carry no grading diagnostics (sanitizer restored)'
);

insert into storage.objects (id, bucket_id, name, owner, metadata)
values (
  '98444444-4444-4444-8444-444444444444',
  'contentengine-training',
  '98000000-0000-4000-8000-000000000001/98222222-2222-4222-8222-222222222222/practical/chain-practical.mp4',
  '98222222-2222-4222-8222-222222222222',
  jsonb_build_object('size', 1048576, 'mimetype', 'video/mp4')
);

create temporary table chain_practical_context (
  project_id uuid not null
) on commit drop;

insert into chain_practical_context (project_id)
select (
  public.creator_save_practical_project(jsonb_build_object(
    'organization_id', '98000000-0000-4000-8000-000000000001',
    'action', 'submit',
    'evidence_kind', 'uploaded_file',
    'platform', 'youtube',
    'media_id', '98444444-4444-4444-8444-444444444444',
    'object_key', '98000000-0000-4000-8000-000000000001/98222222-2222-4222-8222-222222222222/practical/chain-practical.mp4',
    'file_metadata', jsonb_build_object(
      'file_name', 'chain-practical.mp4'
    ),
    'learner_note', 'Пробная работа для проверки восстановленной цепочки.',
    'rights_confirmed', true,
    'self_check_codes', jsonb_build_array(
      'product_match', 'watched_full', 'claims_safe'
    ),
    'idempotency_key', 'pgtap-chain-practical-submit-0001'
  )) #>> '{practical_project,id}'
)::uuid;

select set_config(
  'request.jwt.claim.sub',
  '98111111-1111-4111-8111-111111111111',
  true
);

select is(
  jsonb_array_length(
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '98000000-0000-4000-8000-000000000001'
    )) #> '{training,practical_reviews}'
  ),
  1,
  'owner bootstrap regains the pending practical review queue'
);

select is(
  public.creator_decide_practical_project(jsonb_build_object(
    'organization_id', '98000000-0000-4000-8000-000000000001',
    'id', (select project_id from chain_practical_context),
    'decision', 'approve',
    'review_note', 'Работа соответствует учебному заданию по цепочке.',
    'media_watched_confirmed', true,
    'idempotency_key', 'pgtap-chain-practical-approve-0001'
  )) #>> '{practical_project,status}',
  'approved',
  'owner can approve the practical submission'
);

select set_config(
  'request.jwt.claim.sub',
  '98222222-2222-4222-8222-222222222222',
  true
);

delete from chain_bootstrap_context;
insert into chain_bootstrap_context (bootstrap)
select public.creator_bootstrap(jsonb_build_object(
  'organization_id', '98000000-0000-4000-8000-000000000001'
));

select is(
  (
    select (bootstrap #>> '{learning,practical_project_required}')::boolean
    from chain_bootstrap_context
  ),
  false,
  'approval clears the practical requirement flag'
);

select is(
  (
    select bootstrap #>> '{learning,exam,available}'
    from chain_bootstrap_context
  ),
  'true',
  'final exam opens after courses and practical approval'
);

select is(
  (
    select bootstrap #>> '{learning,exam,blocked_reason}'
    from chain_bootstrap_context
  ),
  null::text,
  'no practical block remains after approval'
);

select * from finish();
rollback;

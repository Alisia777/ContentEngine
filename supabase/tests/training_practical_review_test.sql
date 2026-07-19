begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(37);

create or replace function pg_temp.grant_practical_course_certificates(
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
    select module.code, module.question_count
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
      left('practical-course:' || p_key_prefix || ':' || module_row.code, 180)
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
  end loop;
end;
$fixture$;

select ok(
  to_regclass('content_factory.training_practical_projects') is not null,
  'practical project receipt table exists'
);

select ok(
  (
    select relation.relrowsecurity
    from pg_class relation
    join pg_namespace namespace on namespace.oid = relation.relnamespace
    where namespace.nspname = 'content_factory'
      and relation.relname = 'training_practical_projects'
  ),
  'practical project receipts have RLS enabled'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.training_practical_projects',
    'select'
  ),
  'authenticated cannot bypass bootstrap with a direct receipt read'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.training_practical_projects',
    'insert'
  ),
  'authenticated cannot bypass the submit RPC with a direct insert'
);

select ok(
  not has_table_privilege(
    'anon',
    'content_factory.training_practical_projects',
    'select'
  ),
  'anon cannot read practical evidence'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_save_practical_project(jsonb)',
    'execute'
  ),
  'authenticated can save and submit practical evidence'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_decide_practical_project(jsonb)',
    'execute'
  ),
  'authenticated managers can call the review RPC'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_save_practical_project(jsonb)',
    'execute'
  ),
  'anon cannot call the evidence RPC'
);

select is(
  (
    select bucket.public
    from storage.buckets bucket
    where bucket.id = 'contentengine-training'
  ),
  false,
  'trial-video bucket is private'
);

select is(
  (
    select bucket.file_size_limit::bigint
    from storage.buckets bucket
    where bucket.id = 'contentengine-training'
  ),
  52428800::bigint,
  'trial-video bucket enforces the 50 MB ceiling'
);

select is(
  (
    select count(*)::integer
    from pg_policies policy
    where policy.schemaname = 'storage'
      and policy.tablename = 'objects'
      and policy.policyname in (
        'contentengine_training_select',
        'contentengine_training_insert',
        'contentengine_training_delete'
      )
  ),
  3,
  'trial-video bucket has scoped read, immutable upload and cleanup policies'
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
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    '99111111-1111-4111-8111-111111111111',
    'practical-owner@example.test',
    'Practical Owner'
  ),
  (
    '99222222-2222-4222-8222-222222222222',
    'practical-learner@example.test',
    'Practical Learner'
  ),
  (
    '99333333-3333-4333-8333-333333333333',
    'practical-producer@example.test',
    'Practical Producer'
  )
) fixture(id, email, display_name);

insert into content_factory.profiles (id, email, display_name, status)
values
  (
    '99111111-1111-4111-8111-111111111111',
    'practical-owner@example.test',
    'Practical Owner',
    'active'
  ),
  (
    '99222222-2222-4222-8222-222222222222',
    'practical-learner@example.test',
    'Practical Learner',
    'active'
  ),
  (
    '99333333-3333-4333-8333-333333333333',
    'practical-producer@example.test',
    'Practical Producer',
    'active'
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  '99000000-0000-4000-8000-000000000001',
  'Practical Review Test',
  'practical-review-test',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '99000000-0000-4000-8000-000000000001',
    '99111111-1111-4111-8111-111111111111',
    'owner',
    'active'
  ),
  (
    '99000000-0000-4000-8000-000000000001',
    '99222222-2222-4222-8222-222222222222',
    'trainee',
    'active'
  ),
  (
    '99000000-0000-4000-8000-000000000001',
    '99333333-3333-4333-8333-333333333333',
    'producer',
    'active'
  );

select set_config(
  'request.jwt.claim.sub',
  '99222222-2222-4222-8222-222222222222',
  true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

select throws_ok(
  $$
    select public.creator_submit_exam(jsonb_build_object(
      'organization_id', '99000000-0000-4000-8000-000000000001',
      'idempotency_key', 'pgtap-practical-exam-blocked-0001',
      'answers', '{}'::jsonb
    ))
  $$,
  '42501',
  'practical_project_approval_required',
  'a new learner cannot sit the final exam before practical approval'
);

select is(
  public.creator_save_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'action', 'save_draft',
    'evidence_kind', 'public_url',
    'platform', 'youtube',
    'evidence_url', 'https://example.test/shorts/practical-draft',
    'learner_note', 'Первый учебный ролик.',
    'idempotency_key', 'pgtap-practical-draft-0001'
  )) #>> '{practical_project,status}',
  'draft',
  'learner can save a bounded draft'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_project,status}',
  'draft',
  'bootstrap includes the learner practical project'
);

select throws_ok(
  $$
    select public.creator_save_practical_project(jsonb_build_object(
      'organization_id', '99000000-0000-4000-8000-000000000001',
      'action', 'submit',
      'evidence_kind', 'public_url',
      'platform', 'youtube',
      'evidence_url', 'https://example.test/shorts/practical-before-courses',
      'learner_note', 'Practical submission must remain locked until all four courses pass.',
      'rights_confirmed', true,
      'self_check_codes', jsonb_build_array(
        'product_match', 'watched_full', 'claims_safe'
      ),
      'idempotency_key', 'pgtap-practical-submit-before-courses-0001'
    ))
  $$,
  '42501',
  'required_courses_incomplete',
  'server rejects practical submission before all four course certificates'
);

select pg_temp.grant_practical_course_certificates(
  '99000000-0000-4000-8000-000000000001',
  '99222222-2222-4222-8222-222222222222',
  'learner'
);

create temporary table practical_review_context (
  project_id uuid not null
) on commit drop;

insert into practical_review_context (project_id)
select (
  public.creator_save_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'action', 'submit',
    'evidence_kind', 'public_url',
    'platform', 'youtube',
    'evidence_url', 'https://example.test/shorts/practical-v1',
    'learner_note', 'Пробная работа для проверки руководителем.',
    'rights_confirmed', true,
    'self_check_codes', jsonb_build_array(
      'product_match', 'watched_full', 'claims_safe'
    ),
    'idempotency_key', 'pgtap-practical-submit-0001'
  )) #>> '{practical_project,id}'
)::uuid;

select is(
  (
    select status
    from content_factory.training_practical_projects
    where id = (select project_id from practical_review_context)
  ),
  'submitted',
  'submit moves the evidence into the manager queue'
);

select is(
  public.creator_save_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'action', 'submit',
    'evidence_kind', 'public_url',
    'platform', 'youtube',
    'evidence_url', 'https://example.test/shorts/practical-v1',
    'learner_note', 'Пробная работа для проверки руководителем.',
    'rights_confirmed', true,
    'self_check_codes', jsonb_build_array(
      'product_match', 'watched_full', 'claims_safe'
    ),
    'idempotency_key', 'pgtap-practical-submit-0001'
  )) #>> '{practical_project,status}',
  'submitted',
  'exact submit retry is idempotent'
);

select set_config(
  'request.jwt.claim.sub',
  '99111111-1111-4111-8111-111111111111',
  true
);

select is(
  jsonb_array_length(
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '99000000-0000-4000-8000-000000000001'
    )) #> '{training,practical_reviews}'
  ),
  1,
  'owner bootstrap includes one bounded pending review'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_reviews,0,learner_email}',
  'practical-learner@example.test',
  'manager queue includes the learner identity'
);

select throws_ok(
  format(
    $sql$
      select public.creator_decide_practical_project(jsonb_build_object(
        'organization_id', '99000000-0000-4000-8000-000000000001',
        'id', %L,
        'decision', 'approve',
        'review_note', 'A mutable external URL must never receive final approval.',
        'media_watched_confirmed', true,
        'idempotency_key', 'pgtap-practical-public-url-approve-0001'
      ))
    $sql$,
    (select project_id::text from practical_review_context)
  ),
  '42501',
  'practical_project_private_file_required',
  'manager may request changes for a URL but cannot approve mutable evidence'
);

select is(
  public.creator_decide_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'id', (select project_id from practical_review_context),
    'decision', 'request_changes',
    'review_note', 'Переснимите финал: этикетка должна оставаться читаемой.',
    'media_watched_confirmed', true,
    'idempotency_key', 'pgtap-practical-changes-0001'
  )) #>> '{practical_project,status}',
  'changes_requested',
  'owner can request concrete changes'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_reviews,0,status}',
  'changes_requested',
  'changes-requested work remains visible in the manager queue'
);

select set_config(
  'request.jwt.claim.sub',
  '99222222-2222-4222-8222-222222222222',
  true
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_project,review_note}',
  'Переснимите финал: этикетка должна оставаться читаемой.',
  'learner sees the exact manager feedback after refresh'
);

insert into storage.objects (id, bucket_id, name, owner, metadata)
values (
  '99444444-4444-4444-8444-444444444444',
  'contentengine-training',
  '99000000-0000-4000-8000-000000000001/99222222-2222-4222-8222-222222222222/practical/practical-v2.mp4',
  '99222222-2222-4222-8222-222222222222',
  jsonb_build_object('size', 1048576, 'mimetype', 'video/mp4')
);

select is(
  public.creator_save_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'action', 'submit',
    'evidence_kind', 'uploaded_file',
    'platform', 'youtube',
    'media_id', '99444444-4444-4444-8444-444444444444',
    'object_key', '99000000-0000-4000-8000-000000000001/99222222-2222-4222-8222-222222222222/practical/practical-v2.mp4',
    'file_metadata', jsonb_build_object(
      'file_name', 'practical-v2.mp4'
    ),
    'learner_note', 'Исправленная восьмисекундная версия.',
    'rights_confirmed', true,
    'self_check_codes', jsonb_build_array(
      'product_match', 'watched_full', 'claims_safe'
    ),
    'idempotency_key', 'pgtap-practical-resubmit-0001'
  )) #>> '{practical_project,status}',
  'submitted',
  'learner can resubmit a file reference after changes'
);

select is(
  (
    public.creator_bootstrap(jsonb_build_object(
      'organization_id', '99000000-0000-4000-8000-000000000001'
    )) #>> '{training,practical_project,file_metadata,size_bytes}'
  )::integer,
  1048576,
  'bootstrap returns bounded file metadata without raw file bytes'
);

select set_config(
  'request.jwt.claim.sub',
  '99333333-3333-4333-8333-333333333333',
  true
);

select throws_ok(
  format(
    $sql$
      select public.creator_decide_practical_project(jsonb_build_object(
        'organization_id', '99000000-0000-4000-8000-000000000001',
        'id', %L,
        'decision', 'approve',
        'review_note', 'Producer must not approve this work.',
        'media_watched_confirmed', true,
        'idempotency_key', 'pgtap-practical-producer-denied-0001'
      ))
    $sql$,
    (select project_id::text from practical_review_context)
  ),
  '42501',
  'role_not_allowed',
  'producer cannot decide a practical project'
);

select set_config(
  'request.jwt.claim.sub',
  '99111111-1111-4111-8111-111111111111',
  true
);

update content_factory.training_certifications certification
set status = 'revoked'
where certification.organization_id =
    '99000000-0000-4000-8000-000000000001'
  and certification.profile_id =
    '99222222-2222-4222-8222-222222222222'
  and certification.module_code = 'security_wb';

select throws_ok(
  format(
    $sql$
      select public.creator_decide_practical_project(jsonb_build_object(
        'organization_id', '99000000-0000-4000-8000-000000000001',
        'id', %L,
        'decision', 'approve',
        'review_note', 'Approval must recheck the learner course certificates.',
        'media_watched_confirmed', true,
        'idempotency_key', 'pgtap-practical-approve-revoked-course-0001'
      ))
    $sql$,
    (select project_id::text from practical_review_context)
  ),
  '42501',
  'required_courses_incomplete',
  'approval rechecks all four learner certificates after submission'
);

update content_factory.training_certifications certification
set status = 'passed',
    granted_at = now(),
    expires_at = null
where certification.organization_id =
    '99000000-0000-4000-8000-000000000001'
  and certification.profile_id =
    '99222222-2222-4222-8222-222222222222'
  and certification.module_code = 'security_wb';

select is(
  public.creator_decide_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'id', (select project_id from practical_review_context),
    'decision', 'approve',
    'review_note', 'Работа соответствует учебному заданию.',
    'media_watched_confirmed', true,
    'idempotency_key', 'pgtap-practical-approve-0001'
  )) #>> '{practical_project,status}',
  'approved',
  'owner can approve the corrected work'
);

select is(
  (
    select count(*)::integer
    from content_factory.training_practical_review_decisions decision
    where decision.organization_id =
      '99000000-0000-4000-8000-000000000001'
      and decision.project_id =
        (select project_id from practical_review_context)
  ),
  2,
  'each reviewed submission revision has one immutable decision receipt'
);

select ok(
  (
    select
      count(distinct decision.evidence_fingerprint) = 2
      and bool_and(
        decision.evidence_fingerprint ~ '^[0-9a-f]{64}$'
      )
      and jsonb_agg(
        jsonb_build_object(
          'decision', decision.decision,
          'review_note', decision.review_note
        )
        order by decision.submission_revision
      ) = jsonb_build_array(
        jsonb_build_object(
          'decision', 'request_changes',
          'review_note',
            'Переснимите финал: этикетка должна оставаться читаемой.'
        ),
        jsonb_build_object(
          'decision', 'approve',
          'review_note', 'Работа соответствует учебному заданию.'
        )
      )
    from content_factory.training_practical_review_decisions decision
    where decision.organization_id =
      '99000000-0000-4000-8000-000000000001'
      and decision.project_id =
        (select project_id from practical_review_context)
  ),
  'decision history retains exact notes while fingerprinting private evidence'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_reviews}',
  '[]',
  'approved work leaves the pending review queue'
);

select set_config(
  'request.jwt.claim.sub',
  '99222222-2222-4222-8222-222222222222',
  true
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_project,status}',
  'approved',
  'learner bootstrap preserves approved status'
);

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001'
  )) #>> '{training,practical_project,reviewer_name}',
  'Practical Owner',
  'learner sees who approved the work'
);

select is(
  public.creator_submit_exam(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'idempotency_key', 'pgtap-practical-exam-knowledge-0001',
    'answers', '{}'::jsonb
  )) #>> '{passed}',
  'false',
  'after course and practical approval the exam reaches knowledge grading'
);

select is(
  (
    select count(*)::integer
    from content_factory.factory_events event
    where event.organization_id =
      '99000000-0000-4000-8000-000000000001'
      and event.event_name in (
        'training_practical_project_submitted',
        'training_practical_project_changes_requested',
        'training_practical_project_approved'
      )
  ),
  4,
  'submission, resubmission and both manager decisions are audited'
);

select ok(
  not exists (
    select 1
    from content_factory.factory_events event
    where event.organization_id =
      '99000000-0000-4000-8000-000000000001'
      and event.properties::text ~* 'https://|\.mp4|learner_note|review_note'
  ),
  'audit events never copy evidence URLs, filenames or free-text notes'
);

select set_config(
  'request.jwt.claim.sub',
  '99111111-1111-4111-8111-111111111111',
  true
);

select pg_temp.grant_practical_course_certificates(
  '99000000-0000-4000-8000-000000000001',
  '99111111-1111-4111-8111-111111111111',
  'owner-self-review'
);

insert into storage.objects (id, bucket_id, name, owner, metadata)
values (
  '99555555-5555-4555-8555-555555555555',
  'contentengine-training',
  '99000000-0000-4000-8000-000000000001/99111111-1111-4111-8111-111111111111/practical/owner-self-review.mp4',
  '99111111-1111-4111-8111-111111111111',
  jsonb_build_object('size', 1048576, 'mimetype', 'video/mp4')
);

do $self_review_setup$
begin
  perform public.creator_save_practical_project(jsonb_build_object(
    'organization_id', '99000000-0000-4000-8000-000000000001',
    'action', 'submit',
    'evidence_kind', 'uploaded_file',
    'platform', 'youtube',
    'media_id', '99555555-5555-4555-8555-555555555555',
    'object_key', '99000000-0000-4000-8000-000000000001/99111111-1111-4111-8111-111111111111/practical/owner-self-review.mp4',
    'file_metadata', jsonb_build_object('file_name', 'owner-self-review.mp4'),
    'learner_note', 'Owner practical used only to prove independent review enforcement.',
    'rights_confirmed', true,
    'self_check_codes', jsonb_build_array(
      'product_match', 'watched_full', 'claims_safe'
    ),
    'idempotency_key', 'pgtap-practical-owner-submit-0001'
  ));
end;
$self_review_setup$;

select throws_ok(
  format(
    $sql$
      select public.creator_decide_practical_project(jsonb_build_object(
        'organization_id', '99000000-0000-4000-8000-000000000001',
        'id', %L,
        'decision', 'approve',
        'review_note', 'Even the organization owner needs a different reviewer.',
        'media_watched_confirmed', true,
        'idempotency_key', 'pgtap-practical-owner-self-approve-0001'
      ))
    $sql$,
    (
      select project.id::text
      from content_factory.training_practical_projects project
      where project.organization_id =
          '99000000-0000-4000-8000-000000000001'
        and project.profile_id =
          '99111111-1111-4111-8111-111111111111'
    )
  ),
  '42501',
  'practical_project_self_review_not_allowed',
  'owner cannot approve their own practical submission'
);

select * from finish();
rollback;

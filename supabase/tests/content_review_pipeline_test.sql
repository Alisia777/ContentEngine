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
end;
$course_gate_fixture$;

create or replace function pg_temp.grant_final_exam(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_suffix text
)
returns void
language plpgsql
set search_path = ''
as $final_exam_fixture$
declare
  attempt_id_value uuid;
begin
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    p_organization_id, p_profile_id, 'operator_final_exam',
    'completed', 1, 12, 12, 12, true, '{}'::jsonb,
    encode(extensions.digest(p_key_suffix, 'sha256'), 'hex'),
    'content-review-final-' || p_key_suffix
  )
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    p_organization_id, p_profile_id, 'operator_final_exam',
    attempt_id_value, 'passed'
  );
end;
$final_exam_fixture$;

create or replace function pg_temp.review_result(
  p_kind text
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $review_result_fixture$
begin
  if p_kind = 'block' then
    return jsonb_build_object(
      'overall_score', 38,
      'scores', jsonb_build_object(
        'technical', 82,
        'clarity', 64,
        'legal', 10
      ),
      'ad_probability', 0.92,
      'ad_classification_summary', 'Paid product integration',
      'limitations', jsonb_build_array('Manual exact-video review required'),
      'compliance_status', 'block',
      'blockers_count', 1,
      'warnings_count', 0,
      'strengths', jsonb_build_array('Товар хорошо виден в кадре'),
      'findings', jsonb_build_array(jsonb_build_object(
        'code', 'CLAIM.MEDICAL',
        'category', 'legal',
        'severity', 'blocker',
        'title', 'Недопустимое лечебное обещание',
        'detail', 'В тексте есть обещание лечения без доказанной правовой основы.',
        'action', 'Удалить лечебную формулировку и повторить проверку.',
        'confidence', 0.98,
        'human_review_required', true,
        'evidence', jsonb_build_object('source', 'script_text')
      )),
      'recommendations', jsonb_build_array(jsonb_build_object(
        'code', 'FIX.CLAIM.MEDICAL',
        'category', 'legal',
        'priority', 'blocker',
        'title', 'Переписать обещание',
        'detail', 'Использовать проверяемое описание продукта.',
        'action', 'Заменить лечебное обещание фактической характеристикой.',
        'measurement', 'Повторная проверка не находит blocker.'
      )),
      'comparison', '{}'::jsonb
    );
  end if;

  if p_kind = 'human_review' then
    return jsonb_build_object(
      'overall_score', 74,
      'scores', jsonb_build_object('technical', 84, 'legal', 66),
      'ad_probability', 0.78,
      'ad_classification_summary', 'Commercial context requires review',
      'limitations', jsonb_build_array('Manual exact-video review required'),
      'compliance_status', 'human_review',
      'blockers_count', 0,
      'warnings_count', 1,
      'strengths', jsonb_build_array('Понятный сценарий'),
      'findings', jsonb_build_array(jsonb_build_object(
        'code', 'AD.STATUS_UNRESOLVED',
        'category', 'legal',
        'severity', 'high',
        'title', 'Нужна ручная квалификация',
        'detail', 'Коммерческая интеграция может считаться рекламой.',
        'action', 'Перед публикацией подтвердить статус у ответственного.',
        'human_review_required', true
      )),
      'recommendations', jsonb_build_array(jsonb_build_object(
        'code', 'FIX.AD.STATUS_UNRESOLVED',
        'category', 'legal',
        'priority', 'high',
        'title', 'Подтвердить рекламный статус',
        'detail', 'Зафиксировать решение ответственного.',
        'action', 'Добавить подтверждение в карточку проверки.'
      )),
      'comparison', '{}'::jsonb
    );
  end if;

  return jsonb_build_object(
    'overall_score', 88,
    'scores', jsonb_build_object(
      'technical', 92,
      'clarity', 89,
      'legal', 86
    ),
    'ad_probability', 0.81,
    'ad_classification_summary', 'Paid product integration',
    'limitations', jsonb_build_array('Manual exact-video review required'),
    'compliance_status', 'pass_with_warnings',
    'blockers_count', 0,
    'warnings_count', 0,
    'strengths', jsonb_build_array(
      'Хук понятен',
      'Товар показан крупно'
    ),
    'findings', jsonb_build_array(jsonb_build_object(
      'code', 'QUALITY.CAPTION_DENSITY',
      'category', 'quality',
      'severity', 'low',
      'title', 'Плотные субтитры',
      'detail', 'Последняя строка читается слишком быстро.',
      'action', 'Увеличить время последней плашки на полсекунды.',
      'confidence', 0.82
    )),
    'recommendations', jsonb_build_array(jsonb_build_object(
      'code', 'FIX.QUALITY.CAPTION_DENSITY',
      'category', 'quality',
      'priority', 'low',
      'title', 'Упростить последнюю плашку',
      'detail', 'Сократить текст на несколько слов.',
      'action', 'Оставить один короткий призыв к действию.'
    )),
    'comparison', jsonb_build_object(
      'overall_delta', 9,
      'summary', 'Стало понятнее и технически чище.'
    )
  );
end;
$review_result_fixture$;

select no_plan();

select has_table(
  'content_factory', 'content_review_runs',
  'content review runs table exists'
);
select has_table(
  'content_factory', 'content_review_decisions',
  'immutable human decisions table exists'
);
select has_column(
  'content_factory', 'content_review_runs', 'media_sha256_snapshot',
  'each review binds the exact source bytes'
);
select has_column(
  'content_factory', 'content_review_runs', 'lease_expires_at',
  'paid review workers use a hard lease'
);
select ok(
  (select relrowsecurity
   from pg_class
   where oid = 'content_factory.content_review_runs'::regclass),
  'content review runs use RLS'
);
select ok(
  (select relrowsecurity
   from pg_class
   where oid = 'content_factory.content_review_decisions'::regclass),
  'content review decisions use RLS'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.content_review_runs'::regclass),
     ('content_factory.content_review_decisions'::regclass)
   ) protected(table_oid)
   where has_table_privilege(
     'authenticated', table_oid, 'select,insert,update,delete'
   )),
  0,
  'authenticated has no direct table access'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace
     on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_content_review_catalog',
       'creator_start_content_review',
       'creator_content_review_status',
       'creator_decide_content_review'
     )
     and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb'),
  4,
  'four browser content review RPCs expose one JSON payload'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace
     on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_content_review_catalog',
       'creator_start_content_review',
       'creator_content_review_status',
       'creator_decide_content_review'
     )
     and has_function_privilege(
       'authenticated', procedure.oid, 'execute'
     )),
  4,
  'authenticated can execute browser content review RPCs'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace
     on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_content_review',
       'system_complete_content_review'
     )
     and has_function_privilege(
       'service_role', procedure.oid, 'execute'
     )),
  2,
  'service role can claim and complete review jobs'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace
     on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_content_review',
       'system_complete_content_review'
     )
     and has_function_privilege(
       'authenticated', procedure.oid, 'execute'
     )),
  0,
  'browser sessions cannot execute worker RPCs'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated', fixture.email,
  extensions.crypt(
    'test-only-password',
    extensions.gen_salt('bf')
  ),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(), now()
from (values
  (
    '95000000-0000-4000-8000-000000000001',
    'review-owner@example.test',
    'Review Owner'
  ),
  (
    '95000000-0000-4000-8000-000000000002',
    'review-reviewer@example.test',
    'Independent Reviewer'
  ),
  (
    '95000000-0000-4000-8000-000000000003',
    'review-operator@example.test',
    'Review Operator'
  ),
  (
    '95000000-0000-4000-8000-000000000004',
    'review-outsider@example.test',
    'Other Organization'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    '95100000-0000-4000-8000-000000000001',
    'Content Review Main',
    'content-review-main',
    'active'
  ),
  (
    '95100000-0000-4000-8000-000000000002',
    'Content Review Other',
    'content-review-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000002',
    'reviewer', 'active'
  ),
  (
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000003',
    'operator', 'active'
  ),
  (
    '95100000-0000-4000-8000-000000000002',
    '95000000-0000-4000-8000-000000000004',
    'owner', 'active'
  );

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values (
  '95200000-0000-4000-8000-000000000001',
  '95100000-0000-4000-8000-000000000001',
  'REVIEW-SKU-1',
  'Кровавый пилинг AHA/BHA',
  'active',
  '{"brand":"ALTEA","content_review_category":"cosmetics"}'::jsonb,
  '95000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values
  (
    '95300000-0000-4000-8000-000000000001',
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    '95200000-0000-4000-8000-000000000001',
    'contentengine-private',
    '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000001/review/owner.mp4',
    'video/mp4', 4096, repeat('a', 64), 'ready',
    '{"kind":"source_video","rights_confirmed":true}'::jsonb,
    'content-review-media-owner'
  ),
  (
    '95300000-0000-4000-8000-000000000002',
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000003',
    '95200000-0000-4000-8000-000000000001',
    'contentengine-private',
    '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000003/review/operator.mp4',
    'video/mp4', 4096, repeat('b', 64), 'ready',
    '{"kind":"source_video","rights_confirmed":true}'::jsonb,
    'content-review-media-operator'
  ),
  (
    '95300000-0000-4000-8000-000000000003',
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000003',
    '95200000-0000-4000-8000-000000000001',
    'contentengine-private',
    '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000003/review/stale.webp',
    'image/webp', 2048, repeat('c', 64), 'ready',
    '{"kind":"creator_reference","rights_confirmed":true}'::jsonb,
    'content-review-media-stale'
  ),
  (
    '95300000-0000-4000-8000-000000000004',
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    '95200000-0000-4000-8000-000000000001',
    'contentengine-private',
    '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000001/review/timeout.webp',
    'image/webp', 2048, repeat('d', 64), 'ready',
    '{"kind":"creator_reference","rights_confirmed":true}'::jsonb,
    'content-review-media-timeout'
  ),
  (
    '95300000-0000-4000-8000-000000000006',
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    null,
    'contentengine-private',
    '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000001/review/productless-a.webp',
    'image/webp', 2048, repeat('6', 64), 'ready',
    '{"kind":"creator_reference","rights_confirmed":true}'::jsonb,
    'content-review-media-productless-a'
  ),
  (
    '95300000-0000-4000-8000-000000000007',
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    null,
    'contentengine-private',
    '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000001/review/productless-b.webp',
    'image/webp', 2048, repeat('7', 64), 'ready',
    '{"kind":"creator_reference","rights_confirmed":true}'::jsonb,
    'content-review-media-productless-b'
  );

insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key,
  provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency
)
values (
  '95500000-0000-4000-8000-000000000001',
  '95100000-0000-4000-8000-000000000001',
  '95200000-0000-4000-8000-000000000001',
  '95000000-0000-4000-8000-000000000001',
  'Content review real generation fixture',
  'real', true, 'succeeded', 1, 1,
  jsonb_build_object(
    'job_id', '95500000-0000-4000-8000-000000000002',
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
  repeat('1', 64),
  'content-review-real-batch',
  'runway', 'gen4_turbo', 5, false, 25, 25, 'USD'
);

insert into content_factory.generation_jobs (
  id, organization_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status,
  input, output, request_hash, idempotency_key
)
values (
  '95500000-0000-4000-8000-000000000002',
  '95100000-0000-4000-8000-000000000001',
  '95200000-0000-4000-8000-000000000001',
  '95500000-0000-4000-8000-000000000001',
  1,
  '95000000-0000-4000-8000-000000000001',
  '95000000-0000-4000-8000-000000000003',
  'real', 'runway', true, 25, 25, 'succeeded',
  jsonb_build_object(
    'sku', 'REVIEW-SKU-1',
    'product_name', 'Кровавый пилинг AHA/BHA',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'audio', false,
    'format', '9:16',
    'ratio', '720:1280',
    'input_object_name',
      '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000001/review/input.webp',
    'output_object_name',
      '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000003/review/generated.mp4',
    'platform', 'vk',
    'destination_ref', 'vk-content-review-fixture',
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 25,
      'estimated_credits', 25
    )
  ),
  jsonb_build_object(
    'provider_task_id', 'provider-content-review-fixture',
    'output_object_name',
      '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000003/review/generated.mp4',
    'output_media_id', '95300000-0000-4000-8000-000000000005',
    'mime_type', 'video/mp4',
    'sha256', repeat('5', 64)
  ),
  repeat('2', 64),
  'content-review-real-job'
);

insert into content_factory.creator_tasks (
  id, organization_id, assignee_id, created_by, product_id,
  generation_job_id, task_type, title, instructions,
  status, priority, payout_minor, result, idempotency_key
)
values (
  '95600000-0000-4000-8000-000000000001',
  '95100000-0000-4000-8000-000000000001',
  '95000000-0000-4000-8000-000000000003',
  '95000000-0000-4000-8000-000000000001',
  '95200000-0000-4000-8000-000000000001',
  '95500000-0000-4000-8000-000000000002',
  'video_review',
  'Проверить сгенерированный ролик',
  'Просмотреть точный MP4 и проверить качество.',
  'review', 2, 1234,
  jsonb_build_object(
    'generation_status', 'succeeded',
    'review_required', true,
    'output_media_id', '95300000-0000-4000-8000-000000000005'
  ),
  'content-review-real-video-task'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, task_id, product_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
)
values (
  '95300000-0000-4000-8000-000000000005',
  '95100000-0000-4000-8000-000000000001',
  '95000000-0000-4000-8000-000000000003',
  '95600000-0000-4000-8000-000000000001',
  '95200000-0000-4000-8000-000000000001',
  'contentengine-private',
  '95100000-0000-4000-8000-000000000001/95000000-0000-4000-8000-000000000003/review/generated.mp4',
  'video/mp4', 8192, repeat('5', 64), 'ready',
  jsonb_build_object(
    'kind', 'generated_video',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'generation_job_id', '95500000-0000-4000-8000-000000000002',
    'rights_confirmed', true
  ),
  'content-review-generated-media'
);

do $$
begin
  perform pg_temp.grant_refreshed_course_gate(
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    'review-owner'
  );
  perform pg_temp.grant_refreshed_course_gate(
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000002',
    'review-reviewer'
  );
  perform pg_temp.grant_refreshed_course_gate(
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000003',
    'review-operator'
  );
  perform pg_temp.grant_final_exam(
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000001',
    'owner'
  );
  perform pg_temp.grant_final_exam(
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000002',
    'reviewer'
  );
  perform pg_temp.grant_final_exam(
    '95100000-0000-4000-8000-000000000001',
    '95000000-0000-4000-8000-000000000003',
    'operator'
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

create temporary table content_review_test_context (
  blocked_start jsonb,
  blocked_review_id uuid,
  blocked_completion jsonb,
  pass_start jsonb,
  pass_review_id uuid,
  stale_start jsonb,
  stale_review_id uuid
) on commit drop;

insert into content_review_test_context (blocked_start)
select public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-blocked-0001',
  'media_id', '95300000-0000-4000-8000-000000000001',
  'platform', 'instagram',
  'product_category', 'cosmetics',
  'content_kind', 'advertising',
  'advertiser_name', 'ООО Альтея',
  'erid', '',
  'caption_text', 'Лечит акне навсегда',
  'script_text', 'Это средство гарантированно лечит акне.',
  'technical_metrics', jsonb_build_object(
    'duration_seconds', 8,
    'width', 1080,
    'height', 1920
  ),
  'people_present', 'yes',
  'ad_label_confirmed', false,
  'ord_confirmed', false,
  'person_consent_confirmed', true,
  'ai_generated', true,
  'ai_disclosure_confirmed', false,
  'captions_confirmed', true,
  'mandatory_warning_confirmed', false,
  'rights_confirmed', true,
  'claims_verified', false
));

update content_review_test_context
set blocked_review_id = (blocked_start ->> 'review_id')::uuid;

select ok(
  (select (blocked_start ->> 'ok')::boolean
   from content_review_test_context),
  'an authorized manager starts a durable content review'
);
select is(
  (select blocked_start ->> 'status'
   from content_review_test_context),
  'queued',
  'a new content review starts queued'
);
select is(
  (select input ->> 'mandatory_warning_confirmed'
   from content_factory.content_review_runs
   where id = (
     select blocked_review_id from content_review_test_context
   )),
  'false',
  'unchecked legal confirmations are preserved for the audit'
);
select ok(
  not (
    (select input
     from content_factory.content_review_runs
     where id = (
       select blocked_review_id from content_review_test_context
     )) ? 'idempotency_key'
  ),
  'the run stores canonical input without command secrets'
);
select is(
  public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-blocked-0001',
    'media_id', '95300000-0000-4000-8000-000000000001',
    'platform', 'instagram',
    'product_category', 'cosmetics',
    'content_kind', 'advertising',
    'advertiser_name', 'ООО Альтея',
    'erid', '',
    'caption_text', 'Лечит акне навсегда',
    'script_text', 'Это средство гарантированно лечит акне.',
    'technical_metrics', jsonb_build_object(
      'duration_seconds', 8,
      'width', 1080,
      'height', 1920
    ),
    'people_present', 'yes',
    'ad_label_confirmed', false,
    'ord_confirmed', false,
    'person_consent_confirmed', true,
    'ai_generated', true,
    'ai_disclosure_confirmed', false,
    'captions_confirmed', true,
    'mandatory_warning_confirmed', false,
    'rights_confirmed', true,
    'claims_verified', false
  )) ->> 'review_id',
  (select blocked_review_id::text from content_review_test_context),
  'idempotent start returns the original review'
);
select throws_ok(
  $$select public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-invalid-extra',
    'media_object_id', '95300000-0000-4000-8000-000000000002',
    'platform', 'vk',
    'product_category', 'cosmetics',
    'unexpected', true
  ))$$,
  '22023',
  'content_review_start_payload_invalid',
  'unknown start fields are rejected'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-foreign-media',
    'media_object_id', '95300000-0000-4000-8000-000000000001',
    'platform', 'vk',
    'product_category', 'cosmetics'
  ))$$,
  '42501',
  'content_review_media_not_accessible',
  'an operator cannot review another member private unassigned media'
);

select is(
  (
    select array_agg(item.value ->> 'id' order by item.value ->> 'id')
    from jsonb_array_elements(
      public.creator_content_review_catalog(jsonb_build_object(
        'organization_id', '95100000-0000-4000-8000-000000000001'
      )) -> 'media'
    ) item(value)
  ),
  array[
    '95300000-0000-4000-8000-000000000002',
    '95300000-0000-4000-8000-000000000003',
    '95300000-0000-4000-8000-000000000005'
  ]::text[],
  'operator catalog exposes exactly owned or assigned eligible media'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

create temporary table blocked_claim on commit drop as
select public.system_claim_content_review(jsonb_build_object(
  'review_id',
  (select blocked_review_id from content_review_test_context)
)) as value;

select ok(
  (select (value ->> 'claimed')::boolean from blocked_claim),
  'first worker atomically claims the content review'
);
select is(
  (select value -> 'run' -> 'media' ->> 'sha256' from blocked_claim),
  repeat('a', 64),
  'worker receives the trusted media SHA'
);
select is(
  (select value -> 'run' -> 'input' ->> 'platform' from blocked_claim),
  'instagram',
  'worker receives normalized review input'
);
select ok(
  not (
    public.system_claim_content_review(jsonb_build_object(
      'review_id',
      (select blocked_review_id from content_review_test_context)
    )) ->> 'claimed'
  )::boolean,
  'a second worker cannot claim the same paid review'
);

select throws_ok(
  $$select public.system_complete_content_review(jsonb_build_object(
    'review_id', (
      select blocked_review_id from content_review_test_context
    ),
    'status', 'completed',
    'result', jsonb_set(
      pg_temp.review_result('block'),
      '{blockers_count}',
      '0'::jsonb
    ),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ))$$,
  '22023',
  'content_review_blocker_count_invalid',
  'worker cannot hide a blocker behind an inconsistent count'
);

update content_review_test_context
set blocked_completion = jsonb_build_object(
  'review_id', blocked_review_id,
  'status', 'completed',
  'result', pg_temp.review_result('block'),
  'moderation', jsonb_build_object(
    'flagged', false,
    'model', 'omni-moderation-latest'
  ),
  'ruleset_version', 'ru-content-compliance-2026-07-16.1',
  'model_provider', 'openai',
  'model_version', 'gpt-5.5'
);

select is(
  public.system_complete_content_review(
    (select blocked_completion from content_review_test_context)
  ) ->> 'status',
  'completed',
  'worker stores a validated review result'
);
select ok(
  (
    public.system_complete_content_review(
      (select blocked_completion from content_review_test_context)
    ) ->> 'idempotent'
  )::boolean,
  'identical worker completion is idempotent'
);
select throws_ok(
  $$update content_factory.content_review_runs
    set result = pg_temp.review_result('pass')
    where id = (
      select blocked_review_id from content_review_test_context
    )$$,
  '55000',
  'content_review_run_terminal',
  'terminal AI evidence cannot be rewritten'
);
select is(
  public.creator_content_review_status(jsonb_build_object(
    'review_id',
    (select blocked_review_id from content_review_test_context)
  )) -> 'run' -> 'result' ->> 'compliance_status',
  'block',
  'status returns the complete immutable result'
);

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (
      select blocked_review_id from content_review_test_context
    ),
    'idempotency_key', 'content-review-self-decision',
    'decision', 'needs_changes',
    'comment', 'Нужно исправить лечебное обещание перед публикацией.'
  ))$$,
  '42501',
  'high_risk_content_requires_independent_review',
  'the requester cannot self-review high-risk content'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (
      select blocked_review_id from content_review_test_context
    ),
    'idempotency_key', 'content-review-blocked-approval',
    'decision', 'approved',
    'media_watched_confirmed', true,
    'comment', 'Пробуем согласовать ролик несмотря на найденный blocker.'
  ))$$,
  '55000',
  'content_review_blockers_unresolved',
  'no reviewer can approve content while blockers remain'
);

create temporary table blocked_decision on commit drop as
select public.creator_decide_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'review_id',
    (select blocked_review_id from content_review_test_context),
  'idempotency_key', 'content-review-needs-changes',
  'decision', 'needs_changes',
  'comment', 'Удалить лечебное обещание и отправить новый файл на проверку.',
  'resolved_recommendation_codes', '[]'::jsonb,
  'risk_acknowledgements', jsonb_build_array(
    'CLAIM.MEDICAL'
  )
)) as value;

select is(
  (select value ->> 'decision' from blocked_decision),
  'needs_changes',
  'an independent reviewer records a needs-changes decision'
);
select is(
  public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id',
      (select blocked_review_id from content_review_test_context),
    'idempotency_key', 'content-review-needs-changes',
    'decision', 'needs_changes',
    'comment', 'Удалить лечебное обещание и отправить новый файл на проверку.',
    'resolved_recommendation_codes', '[]'::jsonb,
    'risk_acknowledgements', jsonb_build_array(
      'CLAIM.MEDICAL'
    )
  )) ->> 'decision_id',
  (select value ->> 'decision_id' from blocked_decision),
  'identical human decision is idempotent'
);
select throws_ok(
  $$update content_factory.content_review_decisions
    set comment = 'rewritten immutable evidence'
    where review_id = (
      select blocked_review_id from content_review_test_context
    )$$,
  '55000',
  'content_review_decision_immutable',
  'human decisions are append-only evidence'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

update content_review_test_context
set pass_start = public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-pass-0001',
  'media_object_id', '95300000-0000-4000-8000-000000000002',
  'platform', 'vk',
  'product_category', 'cosmetics',
  'declared_ad_status', 'informational',
  'caption_text', 'Показываю текстуру продукта.',
  'people_present', 'no',
  'captions_confirmed', true
));
update content_review_test_context
set pass_review_id = (pass_start ->> 'review_id')::uuid;

do $$
begin
  perform public.system_claim_content_review(jsonb_build_object(
    'review_id',
    (select pass_review_id from content_review_test_context)
  ));
end;
$$;

select throws_ok(
  $$select public.system_complete_content_review(jsonb_build_object(
    'review_id', (
      select pass_review_id from content_review_test_context
    ),
    'status', 'completed',
    'result', jsonb_set(
      pg_temp.review_result('human_review'),
      '{compliance_status}',
      '"pass_with_warnings"'::jsonb
    ),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ))$$,
  '22023',
  'content_review_compliance_status_invalid',
  'provider cannot label a high-risk finding as pass-with-warnings'
);

select throws_ok(
  $$select public.system_complete_content_review(jsonb_build_object(
    'review_id', (
      select pass_review_id from content_review_test_context
    ),
    'status', 'completed',
    'result', jsonb_set(
      pg_temp.review_result('pass'),
      '{compliance_status}',
      '"human_review"'::jsonb
    ),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ))$$,
  '22023',
  'content_review_compliance_status_invalid',
  'provider cannot invent human-review status without matching findings'
);

select throws_ok(
  $$select public.system_complete_content_review(jsonb_build_object(
    'review_id', (
      select pass_review_id from content_review_test_context
    ),
    'status', 'completed',
    'result', jsonb_set(
      pg_temp.review_result('pass'),
      '{warnings_count}',
      '1'::jsonb
    ),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ))$$,
  '22023',
  'content_review_warning_count_invalid',
  'provider warning count must equal high and medium findings'
);

select throws_ok(
  $$select public.system_complete_content_review(jsonb_build_object(
    'review_id', (
      select pass_review_id from content_review_test_context
    ),
    'status', 'completed',
    'result', jsonb_set(
      jsonb_set(
        pg_temp.review_result('pass'),
        '{findings,0,severity}',
        '"medium"'::jsonb
      ),
      '{warnings_count}',
      '1'::jsonb
    ),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ))$$,
  '22023',
  'content_review_compliance_status_invalid',
  'a medium-only finding still requires human-review compliance status'
);

select lives_ok(
  $$select content_factory_private.validate_content_review_result(
    jsonb_set(
      jsonb_set(
        jsonb_set(
          pg_temp.review_result('pass'),
          '{findings,0,severity}',
          '"medium"'::jsonb
        ),
        '{warnings_count}',
        '1'::jsonb
      ),
      '{compliance_status}',
      '"human_review"'::jsonb
    )
  )$$,
  'medium-only result is accepted with one warning and human review'
);

do $$
begin
  perform public.system_complete_content_review(jsonb_build_object(
    'review_id',
    (select pass_review_id from content_review_test_context),
    'status', 'completed',
    'result', pg_temp.review_result('pass'),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ));
end;
$$;

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (
      select pass_review_id from content_review_test_context
    ),
    'idempotency_key', 'content-review-operator-decision',
    'decision', 'approved',
    'media_watched_confirmed', true,
    'comment', 'Оператор пытается согласовать собственный ролик.'
  ))$$,
  '42501',
  'role_not_allowed',
  'operators cannot issue human approval decisions'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id',
      (select pass_review_id from content_review_test_context),
    'idempotency_key', 'content-review-unknown-recommendation',
    'decision', 'approved',
    'media_watched_confirmed', true,
    'comment', 'Нельзя заявить исправленной рекомендацию, которой не было.',
    'resolved_recommendation_codes', jsonb_build_array('FIX.UNKNOWN')
  ))$$,
  '22023',
  'resolved_recommendation_code_unknown',
  'decision only accepts recommendation codes from the immutable result'
);

select is(
  public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id',
      (select pass_review_id from content_review_test_context),
    'idempotency_key', 'content-review-pass-approval',
    'decision', 'approved',
    'media_watched_confirmed', true,
    'comment', 'Ролик соответствует проверенному файлу и может быть опубликован.',
    'resolved_recommendation_codes', jsonb_build_array(
      'FIX.QUALITY.CAPTION_DENSITY'
    )
  )) ->> 'decision',
  'approved',
  'independent reviewer can approve blocker-free current media'
);

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, result, moderation, ruleset_version,
  model_provider, model_version, request_hash, completion_hash,
  idempotency_key, started_at, finished_at
)
values (
  '95400000-0000-4000-8000-000000000010',
  '95100000-0000-4000-8000-000000000001',
  '95300000-0000-4000-8000-000000000004',
  '95000000-0000-4000-8000-000000000001',
  'completed',
  repeat('d', 64),
  jsonb_build_object(
    'media_id', '95300000-0000-4000-8000-000000000004',
    'platform', 'vk',
    'product_category', 'cosmetics',
    'content_kind', 'informational'
  ),
  jsonb_set(
    pg_temp.review_result('human_review'),
    '{compliance_status}',
    '"pass_with_warnings"'::jsonb
  ),
  '{}'::jsonb,
  'ru-content-compliance-2026-07-16.1',
  'openai',
  'gpt-5.5',
  repeat('7', 64),
  repeat('8', 64),
  'content-review-malformed-provider-label',
  now(),
  now()
);

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', '95400000-0000-4000-8000-000000000010',
    'idempotency_key', 'content-review-actual-risk-ack',
    'decision', 'approved',
    'media_watched_confirmed', true,
    'comment', 'Reviewer confirms the actual finding risk before approval.'
  ))$$,
  '22023',
  'content_review_risk_acknowledgement_required',
  'approval derives required acknowledgement from findings, not provider label'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

create temporary table stale_sha_completion on commit drop as
select public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-stale-sha-completion',
  'media_object_id', '95300000-0000-4000-8000-000000000003',
  'platform', 'vk',
  'product_category', 'cosmetics',
  'declared_ad_status', 'informational'
)) as value;

select ok(
  (
    public.system_claim_content_review(jsonb_build_object(
      'review_id', (select value ->> 'review_id' from stale_sha_completion)
    )) ->> 'claimed'
  )::boolean,
  'worker claims media before the completion-time SHA race'
);

update content_factory.media_objects
set sha256 = repeat('8', 64)
where id = '95300000-0000-4000-8000-000000000003';

select is(
  public.system_complete_content_review(jsonb_build_object(
    'review_id', (select value ->> 'review_id' from stale_sha_completion),
    'status', 'completed',
    'result', pg_temp.review_result('pass'),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  )) ->> 'error_code',
  'media_stale_during_review',
  'completion fails closed when source bytes change after claim'
);

select is(
  (select status
   from content_factory.content_review_runs
   where id = (
     select (value ->> 'review_id')::uuid from stale_sha_completion
   )),
  'failed',
  'completion-time SHA mismatch becomes terminal'
);

select ok(
  (
    public.system_complete_content_review(jsonb_build_object(
      'review_id', (select value ->> 'review_id' from stale_sha_completion),
      'status', 'completed',
      'result', pg_temp.review_result('pass'),
      'moderation', '{}'::jsonb,
      'ruleset_version', 'ru-content-compliance-2026-07-16.1',
      'model_provider', 'openai',
      'model_version', 'gpt-5.5'
    )) ->> 'idempotent'
  )::boolean,
  'lost stale-SHA response can be replayed idempotently'
);

update content_factory.media_objects
set sha256 = repeat('c', 64)
where id = '95300000-0000-4000-8000-000000000003';

create temporary table stale_status_completion on commit drop as
select public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-stale-status-completion',
  'media_object_id', '95300000-0000-4000-8000-000000000003',
  'platform', 'vk',
  'product_category', 'cosmetics',
  'declared_ad_status', 'informational'
)) as value;

select ok(
  (
    public.system_claim_content_review(jsonb_build_object(
      'review_id', (select value ->> 'review_id' from stale_status_completion)
    )) ->> 'claimed'
  )::boolean,
  'worker claims media before the completion-time status race'
);

update content_factory.media_objects
set status = 'archived'
where id = '95300000-0000-4000-8000-000000000003';

select is(
  public.system_complete_content_review(jsonb_build_object(
    'review_id', (select value ->> 'review_id' from stale_status_completion),
    'status', 'failed',
    'error_code', 'provider_failed',
    'error_message', 'Provider failed after the source was archived.'
  )) ->> 'error_code',
  'media_stale_during_review',
  'trusted media staleness takes precedence over a provider failure'
);

select is(
  (select status
   from content_factory.content_review_runs
   where id = (
     select (value ->> 'review_id')::uuid from stale_status_completion
   )),
  'failed',
  'completion-time lifecycle mismatch becomes terminal'
);

select ok(
  (
    public.system_complete_content_review(jsonb_build_object(
      'review_id', (
        select value ->> 'review_id' from stale_status_completion
      ),
      'status', 'failed',
      'error_code', 'provider_failed',
      'error_message', 'Provider failed after the source was archived.'
    )) ->> 'idempotent'
  )::boolean,
  'lost stale-status response can be replayed idempotently'
);

update content_factory.media_objects
set status = 'ready'
where id = '95300000-0000-4000-8000-000000000003';

update content_review_test_context
set stale_start = public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-stale-0001',
  'media_object_id', '95300000-0000-4000-8000-000000000003',
  'platform', 'youtube',
  'product_category', 'cosmetics',
  'declared_ad_status', 'informational'
));
update content_review_test_context
set stale_review_id = (stale_start ->> 'review_id')::uuid;

do $$
begin
  perform public.system_claim_content_review(jsonb_build_object(
    'review_id',
    (select stale_review_id from content_review_test_context)
  ));
  perform public.system_complete_content_review(jsonb_build_object(
    'review_id',
    (select stale_review_id from content_review_test_context),
    'status', 'completed',
    'result', pg_temp.review_result('pass'),
    'moderation', '{}'::jsonb,
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ));
end;
$$;

update content_factory.media_objects
set sha256 = repeat('e', 64)
where id = '95300000-0000-4000-8000-000000000003';

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (
      select stale_review_id from content_review_test_context
    ),
    'idempotency_key', 'content-review-stale-approval',
    'decision', 'approved',
    'media_watched_confirmed', true,
    'comment', 'Нельзя согласовать изменённый после анализа файл.'
  ))$$,
  '55000',
  'content_review_media_stale',
  'approval is impossible after the source SHA changes'
);

select throws_ok(
  $$update content_factory.creator_tasks
    set status = 'done',
        result = result || jsonb_build_object(
          'content_review_id', '95900000-0000-4000-8000-000000000001',
          'content_review_media_sha256', repeat('5', 64),
          'content_review_ruleset', 'ru-content-compliance-2026-07-16.1'
        )
    where id = '95600000-0000-4000-8000-000000000001'$$,
  '55000',
  'content_review_approval_evidence_required',
  'paid generated-video task cannot bypass the immutable approval gate'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

create temporary table generated_review_context (
  start_value jsonb,
  review_id uuid,
  decision_value jsonb
) on commit drop;

insert into generated_review_context (start_value)
select public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-generated-0001',
  'media_id', '95300000-0000-4000-8000-000000000005',
  'platform', 'youtube',
  'product_category', 'cosmetics',
  'content_kind', 'informational',
  'caption_text', 'Показываю продукт и его текстуру.',
  'script_text', 'Короткий ролик о продукте.',
  'advertiser_name', 'ООО Альтеа',
  'erid', '2VtzqwReviewFixture',
  'technical_metrics', jsonb_build_object(
    'duration_seconds', 5,
    'width', 720,
    'height', 1280,
    'frame_source', 'browser_advisory'
  ),
  'rights_confirmed', true,
  'claims_verified', true,
  'ad_label_confirmed', true,
  'ord_confirmed', true,
  'people_present', 'yes',
  'person_consent_confirmed', true,
  'external_ai_processing_confirmed', true,
  'ai_generated', false,
  'ai_disclosure_confirmed', true,
  'captions_confirmed', true
));
update generated_review_context
set review_id = (start_value ->> 'review_id')::uuid;

select is(
  (select input ->> 'platform'
   from content_factory.content_review_runs
   where id = (select review_id from generated_review_context)),
  'vk',
  'generated review platform is derived from the trusted generation job'
);
select is(
  (select input ->> 'content_kind'
   from content_factory.content_review_runs
   where id = (select review_id from generated_review_context)),
  'advertising',
  'paid generated product content is always reviewed as advertising'
);
select is(
  (select input ->> 'ai_generated'
   from content_factory.content_review_runs
   where id = (select review_id from generated_review_context)),
  'true',
  'generated media provenance forces the AI disclosure context'
);
select is(
  (select input ->> 'generation_job_id'
   from content_factory.content_review_runs
   where id = (select review_id from generated_review_context)),
  '95500000-0000-4000-8000-000000000002',
  'generated review is bound to the exact paid generation job'
);
select is(
  (select input ->> 'product_category_source'
   from content_factory.content_review_runs
   where id = (select review_id from generated_review_context)),
  'product_metadata',
  'generated review category comes from the persisted product classification'
);
select is(
  (select input ->> 'product_category_verified'
   from content_factory.content_review_runs
   where id = (select review_id from generated_review_context)),
  'true',
  'persisted product classification is marked verified for release'
);

do $$
begin
  perform public.system_claim_content_review(jsonb_build_object(
    'review_id', (select review_id from generated_review_context)
  ));
  perform public.system_complete_content_review(jsonb_build_object(
    'review_id', (select review_id from generated_review_context),
    'status', 'completed',
    'result', pg_temp.review_result('human_review'),
    'moderation', jsonb_build_object('flagged', false),
    'ruleset_version', 'ru-content-compliance-2026-07-16.1',
    'model_provider', 'openai',
    'model_version', 'gpt-5.5'
  ));
end;
$$;

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (select review_id from generated_review_context),
    'idempotency_key', 'content-review-generated-job-requester',
    'decision', 'approved',
    'reason', 'Создатель платного задания не должен утверждать собственный результат.',
    'media_watched_confirmed', true,
    'risk_acknowledgements', jsonb_build_array('AD.STATUS_UNRESOLVED')
  ))$$,
  '42501',
  'high_risk_content_requires_independent_review',
  'paid generation requester cannot approve the generated result'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (select review_id from generated_review_context),
    'idempotency_key', 'content-review-generated-not-watched',
    'decision', 'approved',
    'reason', 'Ролик требует ручного подтверждения полного просмотра.',
    'risk_acknowledgements', jsonb_build_array(
      'AD.STATUS_UNRESOLVED'
    )
  ))$$,
  '22023',
  'content_review_media_watch_required',
  'approval requires explicit confirmation that the exact media was watched'
);

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (select review_id from generated_review_context),
    'idempotency_key', 'content-review-generated-unknown-risk',
    'decision', 'approved',
    'reason', 'Произвольная строка не является подтверждением найденного риска.',
    'media_watched_confirmed', true,
    'risk_acknowledgements', jsonb_build_array('foo')
  ))$$,
  '22023',
  'risk_acknowledgement_unknown',
  'arbitrary risk acknowledgement codes are rejected'
);

select throws_ok(
  $$select public.creator_decide_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'review_id', (select review_id from generated_review_context),
    'idempotency_key', 'content-review-generated-missing-risk',
    'decision', 'approved',
    'reason', 'Все обязательные риски должны быть отмечены по точному коду.',
    'media_watched_confirmed', true,
    'risk_acknowledgements', '[]'::jsonb
  ))$$,
  '22023',
  'content_review_risk_acknowledgement_required',
  'approval requires every high or human-review finding code'
);

update generated_review_context
set decision_value = public.creator_decide_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'review_id', review_id,
  'idempotency_key', 'content-review-generated-approved',
  'decision', 'approved',
  'reason', 'Полностью просмотрен точный MP4 со звуком и субтитрами.',
  'media_watched_confirmed', true,
  'risk_acknowledgements', jsonb_build_array(
    'AD.STATUS_UNRESOLVED'
  )
));

select is(
  (select status
   from content_factory.creator_tasks
   where id = '95600000-0000-4000-8000-000000000001'),
  'done',
  'approved generated-video review atomically completes its review task'
);
select is(
  (select amount_minor
   from content_factory.creator_payouts
   where task_id = '95600000-0000-4000-8000-000000000001'),
  1234::bigint,
  'approved generated-video review creates the pending review payout'
);
select is(
  (select status
   from content_factory.creator_payouts
   where task_id = '95600000-0000-4000-8000-000000000001'),
  'pending',
  'review payout remains pending for the normal payout ledger'
);
select is(
  (select task_type
   from content_factory.creator_tasks
   where id = (
     select (decision_value ->> 'placement_task_id')::uuid
     from generated_review_context
   )),
  'placement',
  'approval creates a separate zero-payout placement task'
);
select is(
  (select payout_minor
   from content_factory.creator_tasks
   where id = (
     select (decision_value ->> 'placement_task_id')::uuid
     from generated_review_context
   )),
  0::bigint,
  'placement task cannot duplicate the review payout'
);
select is(
  (select placement.status
   from content_factory.placements placement
   where placement.id = (
     select (decision_value ->> 'placement_id')::uuid
     from generated_review_context
   )),
  'ready',
  'approved generated video enters the existing placement workflow as ready'
);
select is(
  (select placement.metadata ->> 'media_sha256'
   from content_factory.placements placement
   where placement.id = (
     select (decision_value ->> 'placement_id')::uuid
     from generated_review_context
   )),
  repeat('5', 64),
  'placement evidence is bound to the approved media SHA'
);
select ok(
  content_factory_private.placement_url_matches_platform(
    'vk',
    'https://vk.com/clip-123_456'
  ),
  'platform URL guard accepts a canonical VK publication URL'
);
select ok(
  not content_factory_private.placement_url_matches_platform(
    'vk',
    'https://www.instagram.com/reel/not-vk'
  ),
  'platform URL guard rejects evidence from a different network'
);
select throws_ok(
  $$update content_factory.placements
    set final_url = 'https://www.instagram.com/reel/not-vk'
    where id = (
      select (decision_value ->> 'placement_id')::uuid
      from generated_review_context
    )$$,
  '22023',
  'final_url_platform_mismatch',
  'placement cannot be completed with a URL from another platform'
);

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, ruleset_version, request_hash,
  idempotency_key, started_at, lease_expires_at
)
values (
  '95400000-0000-4000-8000-000000000001',
  '95100000-0000-4000-8000-000000000001',
  '95300000-0000-4000-8000-000000000004',
  '95000000-0000-4000-8000-000000000001',
  'processing',
  repeat('d', 64),
  jsonb_build_object(
    'media_object_id', '95300000-0000-4000-8000-000000000004',
    'platform', 'vk',
    'product_category', 'cosmetics'
  ),
  'ru-content-compliance-2026-07-16.1',
  repeat('f', 64),
  'content-review-timeout-fixture',
  now() - interval '20 minutes',
  now() - interval '10 minutes'
);

create temporary table expired_completion_payload on commit drop as
select jsonb_build_object(
  'review_id', '95400000-0000-4000-8000-000000000001',
  'status', 'completed',
  'result', pg_temp.review_result('pass'),
  'moderation', '{}'::jsonb,
  'ruleset_version', 'ru-content-compliance-2026-07-16.1',
  'model_provider', 'openai',
  'model_version', 'gpt-5.5'
) as value;

select is(
  public.system_complete_content_review(
    (select value from expired_completion_payload)
  ) ->> 'status',
  'failed',
  'expired worker completion fails closed without browser status polling'
);
select is(
  (select status
   from content_factory.content_review_runs
   where id = '95400000-0000-4000-8000-000000000001'),
  'failed',
  'expired paid worker lease becomes terminal'
);
select is(
  (select error_code
   from content_factory.content_review_runs
   where id = '95400000-0000-4000-8000-000000000001'),
  'processing_lease_expired',
  'lease timeout has an explicit restart-required error'
);
select ok(
  (
    public.system_complete_content_review(
      (select value from expired_completion_payload)
    ) ->> 'idempotent'
  )::boolean,
  'lost lease-timeout response can be replayed idempotently'
);

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, ruleset_version, request_hash,
  idempotency_key, created_at
)
values (
  '95400000-0000-4000-8000-000000000002',
  '95100000-0000-4000-8000-000000000001',
  '95300000-0000-4000-8000-000000000004',
  '95000000-0000-4000-8000-000000000001',
  'queued',
  repeat('d', 64),
  jsonb_build_object(
    'media_id', '95300000-0000-4000-8000-000000000004',
    'platform', 'vk',
    'product_category', 'cosmetics',
    'content_kind', 'informational'
  ),
  'ru-content-compliance-2026-07-16.1',
  repeat('9', 64),
  'content-review-abandoned-queue',
  now() - interval '5 minutes'
);

select is(
  public.creator_content_review_status(jsonb_build_object(
    'review_id', '95400000-0000-4000-8000-000000000002'
  )) -> 'run' ->> 'status',
  'cancelled',
  'abandoned browser-dispatch queue expires safely'
);
select is(
  (select error_code
   from content_factory.content_review_runs
   where id = '95400000-0000-4000-8000-000000000002'),
  'queued_dispatch_expired',
  'expired queue records an explicit retry-safe reason'
);
select is(
  public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-after-abandoned-queue',
    'media_id', '95300000-0000-4000-8000-000000000004',
    'platform', 'vk',
    'product_category', 'cosmetics',
    'content_kind', 'informational'
  )) ->> 'status',
  'queued',
  'the exact media can be reviewed again after dispatch expiry'
);

create temporary table stale_before_claim on commit drop as
select public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-stale-before-provider',
  'media_id', '95300000-0000-4000-8000-000000000003',
  'platform', 'vk',
  'product_category', 'cosmetics',
  'content_kind', 'informational'
)) as value;

update content_factory.media_objects
set sha256 = repeat('6', 64)
where id = '95300000-0000-4000-8000-000000000003';

select ok(
  not (
    public.system_claim_content_review(jsonb_build_object(
      'review_id', (select value ->> 'review_id' from stale_before_claim)
    )) ->> 'claimed'
  )::boolean,
  'worker does not claim media whose bytes changed before provider dispatch'
);
select is(
  (select status
   from content_factory.content_review_runs
   where id = (
     select (value ->> 'review_id')::uuid from stale_before_claim
   )),
  'cancelled',
  'stale pre-provider media becomes terminal without a paid model call'
);
select is(
  (select error_code
   from content_factory.content_review_runs
   where id = (
     select (value ->> 'review_id')::uuid from stale_before_claim
   )),
  'media_stale_before_review',
  'stale pre-provider cancellation has an auditable reason'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, result, moderation, ruleset_version,
  model_provider, model_version, request_hash, completion_hash,
  idempotency_key, started_at, finished_at
)
values (
  '95400000-0000-4000-8000-000000000011',
  '95100000-0000-4000-8000-000000000001',
  '95300000-0000-4000-8000-000000000006',
  '95000000-0000-4000-8000-000000000001',
  'completed',
  repeat('6', 64),
  jsonb_build_object(
    'media_id', '95300000-0000-4000-8000-000000000006',
    'platform', 'vk',
    'product_category', 'other',
    'content_kind', 'informational'
  ),
  pg_temp.review_result('pass'),
  '{}'::jsonb,
  'ru-content-compliance-2026-07-16.1',
  'openai',
  'gpt-5.5',
  repeat('1', 64),
  repeat('2', 64),
  'content-review-productless-parent',
  now(),
  now()
);

select throws_ok(
  $$select public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-parent-null-vs-product',
    'media_object_id', '95300000-0000-4000-8000-000000000001',
    'parent_review_id', '95400000-0000-4000-8000-000000000011',
    'platform', 'vk',
    'product_category', 'cosmetics',
    'declared_ad_status', 'informational'
  ))$$,
  '22023',
  'parent_content_review_product_mismatch',
  'explicit parent cannot cross between productless and product media'
);

select throws_ok(
  $$select public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-parent-productless-cross-media',
    'media_object_id', '95300000-0000-4000-8000-000000000007',
    'parent_review_id', '95400000-0000-4000-8000-000000000011',
    'platform', 'vk',
    'product_category', 'other',
    'declared_ad_status', 'informational'
  ))$$,
  '22023',
  'parent_content_review_product_mismatch',
  'productless history cannot cross between unrelated media'
);

select is(
  public.creator_start_content_review(jsonb_build_object(
    'organization_id', '95100000-0000-4000-8000-000000000001',
    'idempotency_key', 'content-review-parent-productless-same-media',
    'media_object_id', '95300000-0000-4000-8000-000000000006',
    'parent_review_id', '95400000-0000-4000-8000-000000000011',
    'platform', 'vk',
    'product_category', 'other',
    'declared_ad_status', 'informational'
  )) ->> 'parent_review_id',
  '95400000-0000-4000-8000-000000000011',
  'productless history is allowed for the exact same media'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '95000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

create temporary table parent_start on commit drop as
select public.creator_start_content_review(jsonb_build_object(
  'organization_id', '95100000-0000-4000-8000-000000000001',
  'idempotency_key', 'content-review-parent-0001',
  'media_object_id', '95300000-0000-4000-8000-000000000001',
  'platform', 'instagram',
  'product_category', 'cosmetics',
  'declared_ad_status', 'advertising'
)) as value;

select is(
  (select value ->> 'parent_review_id' from parent_start),
  (select blocked_review_id::text from content_review_test_context),
  'a repeat review automatically links its previous completed result'
);
select is(
  public.system_claim_content_review(jsonb_build_object(
    'review_id', (select value ->> 'review_id' from parent_start)
  )) -> 'run' -> 'parent_result' ->> 'overall_score',
  '38',
  'worker receives immutable baseline evidence for recommendations'
);

select * from finish();
rollback;

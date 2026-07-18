begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(41);

create or replace function pg_temp.grant_generation_archive_training_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $training_gate$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
  answers_value jsonb;
  final_question_count integer;
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

  select module.question_count
  into final_question_count
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
    final_question_count,
    final_question_count,
    final_question_count,
    true,
    '{}'::jsonb,
    content_factory_private.json_hash(jsonb_build_object(
      'profile_id', p_profile_id,
      'exam', 'operator_final_exam'
    )),
    left('generation-archive:' || p_key_prefix || ':final-exam', 180)
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
$training_gate$;

select has_function(
  'public', 'creator_generation_archive', array['jsonb'],
  'generation archive exposes one browser RPC'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_generation_archive(jsonb)', 'execute'
  ),
  'authenticated sessions can read the generation archive'
);
select ok(
  not has_function_privilege(
    'anon', 'public.creator_generation_archive(jsonb)', 'execute'
  ),
  'anonymous sessions cannot read the generation archive'
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
    'a8100000-0000-4000-8000-000000000001',
    'archive-owner@example.test',
    'Archive Owner'
  ),
  (
    'a8100000-0000-4000-8000-000000000002',
    'archive-operator@example.test',
    'Archive Operator'
  ),
  (
    'a8100000-0000-4000-8000-000000000003',
    'archive-outsider@example.test',
    'Archive Outsider'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    'a8200000-0000-4000-8000-000000000001',
    'Generation Archive Main',
    'generation-archive-main',
    'active'
  ),
  (
    'a8200000-0000-4000-8000-000000000002',
    'Generation Archive Other',
    'generation-archive-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    'a8200000-0000-4000-8000-000000000001',
    'a8100000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    'a8200000-0000-4000-8000-000000000001',
    'a8100000-0000-4000-8000-000000000002',
    'operator', 'active'
  ),
  (
    'a8200000-0000-4000-8000-000000000002',
    'a8100000-0000-4000-8000-000000000003',
    'owner', 'active'
  );

select lives_ok(
  $$select pg_temp.grant_generation_archive_training_gate(
    'a8200000-0000-4000-8000-000000000001',
    'a8100000-0000-4000-8000-000000000001',
    'archive-owner'
  )$$,
  'owner fixture satisfies the refreshed training gate'
);
select lives_ok(
  $$select pg_temp.grant_generation_archive_training_gate(
    'a8200000-0000-4000-8000-000000000001',
    'a8100000-0000-4000-8000-000000000002',
    'archive-operator'
  )$$,
  'operator fixture satisfies the refreshed training gate'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values
  (
    'a8400000-0000-4000-8000-000000000001',
    'a8200000-0000-4000-8000-000000000001',
    'ARCHIVE-SKU-1005',
    'Archive scale product',
    'active', '{}'::jsonb,
    'a8100000-0000-4000-8000-000000000001'
  ),
  (
    'a8400000-0000-4000-8000-000000000002',
    'a8200000-0000-4000-8000-000000000002',
    'OTHER-TENANT-SKU',
    'Other tenant product',
    'active', '{}'::jsonb,
    'a8100000-0000-4000-8000-000000000003'
  );

-- 1,005 rows exercise eleven pages. Groups of 250 share a timestamp so the
-- UUID tie-breaker is required; the first four groups cover the current 4w.
insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, name, mode,
  allow_real_spend, status, total_requested, total_created, input,
  request_hash, idempotency_key, created_at, updated_at
)
select
  ('a8500000-0000-4000-8000-' || lpad(series::text, 12, '0'))::uuid,
  'a8200000-0000-4000-8000-000000000001'::uuid,
  'a8400000-0000-4000-8000-000000000001'::uuid,
  case when series <= 3
    then 'a8100000-0000-4000-8000-000000000002'::uuid
    else 'a8100000-0000-4000-8000-000000000001'::uuid
  end,
  'Archive batch ' || series,
  'mock', false,
  case when series % 5 = 0 then 'cancelled' else 'mock_ready' end,
  1, 1,
  jsonb_build_object('fixture_ordinal', series),
  repeat('a', 64),
  'generation-archive-scale-' || series,
  date_trunc('week', now()) - make_interval(weeks => ((series - 1) / 250)),
  date_trunc('week', now()) - make_interval(weeks => ((series - 1) / 250))
from generate_series(1, 1005) series;

insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, name, mode,
  allow_real_spend, status, total_requested, total_created, input,
  request_hash, idempotency_key, created_at, updated_at
)
values (
  'b8500000-0000-4000-8000-000000000001',
  'a8200000-0000-4000-8000-000000000002',
  'a8400000-0000-4000-8000-000000000002',
  'a8100000-0000-4000-8000-000000000003',
  'Other tenant archive batch',
  'mock', false, 'mock_ready', 1, 1, '{}'::jsonb, repeat('b', 64),
  'generation-archive-other-1', now(), now()
);

create temporary table generation_archive_snapshot (
  batches bigint not null,
  products bigint not null
) on commit drop;
insert into generation_archive_snapshot
select
  (select count(*) from content_factory.generation_batches),
  (select count(*) from content_factory.products);

create temporary table generation_archive_seen (
  page_number integer not null,
  row_number integer not null,
  batch_id uuid not null
) on commit drop;
create temporary table generation_archive_pages (
  page_number integer primary key,
  batch_count integer not null,
  has_more boolean not null,
  next_cursor jsonb
) on commit drop;
create temporary table generation_archive_first (
  response jsonb not null
) on commit drop;
grant select, insert on generation_archive_seen to authenticated;
grant select, insert on generation_archive_pages to authenticated;
grant select, insert on generation_archive_first to authenticated;

create or replace function pg_temp.collect_generation_archive_pages()
returns void
language plpgsql
set search_path = ''
as $collect$
declare
  page_number integer := 0;
  response jsonb;
  cursor_value jsonb;
begin
  loop
    page_number := page_number + 1;
    response := public.creator_generation_archive(
      jsonb_build_object(
        'organization_id', 'a8200000-0000-4000-8000-000000000001',
        'period', 'all',
        'status', 'all',
        'page_size', 100
      ) || case
        when cursor_value is null then '{}'::jsonb
        else jsonb_build_object('cursor', cursor_value)
      end
    );

    if page_number = 1 then
      insert into pg_temp.generation_archive_first values (response);
    end if;
    insert into pg_temp.generation_archive_seen (
      page_number, row_number, batch_id
    )
    select page_number, item.ordinality::integer, (item.value ->> 'id')::uuid
    from jsonb_array_elements(response -> 'batches')
      with ordinality item(value, ordinality);
    insert into pg_temp.generation_archive_pages (
      page_number, batch_count, has_more, next_cursor
    ) values (
      page_number,
      jsonb_array_length(response -> 'batches'),
      (response #>> '{_meta,has_more}')::boolean,
      response #> '{_meta,next_cursor}'
    );

    exit when not (response #>> '{_meta,has_more}')::boolean;
    cursor_value := response #> '{_meta,next_cursor}';
    if page_number >= 20 then
      raise exception 'generation archive pagination did not terminate';
    end if;
  end loop;
end;
$collect$;
grant execute on function pg_temp.collect_generation_archive_pages()
  to authenticated;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'a8100000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

set local role authenticated;
select pg_temp.collect_generation_archive_pages();

select ok(
  (select response -> 'ok' = 'true'::jsonb from generation_archive_first),
  'archive response reports success'
);
select ok(
  (
    select response ?& array['ok', 'batches', '_meta']
      and jsonb_object_length(response) = 3
    from generation_archive_first
  ),
  'archive response has only the documented top-level keys'
);
select is(
  (
    select array_agg(key order by key)
    from generation_archive_first,
      lateral jsonb_object_keys(response -> '_meta') key
  ),
  array[
    'cursor_mode', 'has_more', 'next_cursor', 'page_size',
    'period', 'query', 'status'
  ]::text[],
  'archive metadata has the exact paging and filter contract'
);
select is(
  (select response #>> '{_meta,page_size}' from generation_archive_first),
  '100',
  'archive echoes the bounded page size'
);
select is(
  (select response #>> '{_meta,cursor_mode}' from generation_archive_first),
  'keyset_created_at_id',
  'archive declares its stable keyset mode'
);
select ok(
  (select (response #>> '{_meta,has_more}')::boolean from generation_archive_first),
  'first scale page announces more history'
);
select is(
  (
    select array_agg(key order by key)
    from generation_archive_first,
      lateral jsonb_object_keys(response #> '{_meta,next_cursor}') key
  ),
  array['at', 'id']::text[],
  'next cursor is exactly the created-at and UUID tuple'
);
select is(
  (select count(*)::integer from generation_archive_pages),
  11,
  '1,005 batches require eleven bounded pages'
);
select is(
  (
    select count(*)::integer
    from generation_archive_pages
    where page_number <= 10 and batch_count = 100 and has_more
  ),
  10,
  'the first ten pages are full and continue'
);
select is(
  (
    select batch_count
    from generation_archive_pages
    where page_number = 11
  ),
  5,
  'the final page contains the remaining five batches'
);
select ok(
  not (
    select has_more
    from generation_archive_pages
    where page_number = 11
  ),
  'the final page terminates pagination'
);
select is(
  (select count(*)::integer from generation_archive_seen),
  1005,
  'all 1,005 rows are returned'
);
select is(
  (select count(distinct batch_id)::integer from generation_archive_seen),
  1005,
  'adjacent keyset pages never overlap'
);

select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', 'week',
    'query', 'a8500000-0000-4000-8000-000000000001',
    'page_size', 100
  )) -> 'batches'),
  1,
  'current-week period includes a current-week match'
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', 'week',
    'query', 'a8500000-0000-4000-8000-000000000251',
    'page_size', 100
  )) -> 'batches'),
  0,
  'current-week period excludes the previous week'
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', '4w', 'query', 'Archive batch 1000', 'page_size', 100
  )) -> 'batches'),
  1,
  'four-week period includes its oldest week'
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', '4w', 'query', 'Archive batch 1001', 'page_size', 100
  )) -> 'batches'),
  0,
  'four-week period excludes older history'
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'query', 'a8500000-0000-4000-8000-000000001001',
    'page_size', 100
  )) -> 'batches'),
  0,
  'the default four-week period bounds unqualified archive searches'
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', 'all', 'query', '  ARCHIVE BATCH 1005  ', 'page_size', 100
  )) -> 'batches'),
  1,
  'trimmed case-insensitive query searches the complete archive'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.creator_generation_archive(
      jsonb_build_object(
        'organization_id', 'a8200000-0000-4000-8000-000000000001',
        'period', 'all', 'status', 'issue', 'page_size', 100
      )
    ) -> 'batches') item
    where item ->> 'status' <> 'cancelled'
  ),
  'issue status group returns only failed or cancelled batches'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.creator_generation_archive(
      jsonb_build_object(
        'organization_id', 'a8200000-0000-4000-8000-000000000001',
        'period', 'all', 'status', 'ready', 'page_size', 100
      )
    ) -> 'batches') item
    where item ->> 'status' <> 'mock_ready'
  ),
  'ready status group returns only completed batches'
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', 'all', 'status', 'active', 'page_size', 100
  )) -> 'batches'),
  0,
  'active status group excludes ready and issue fixtures'
);

select set_config(
  'request.jwt.claim.sub',
  'a8100000-0000-4000-8000-000000000002',
  true
);
select is(
  jsonb_array_length(public.creator_generation_archive(jsonb_build_object(
    'organization_id', 'a8200000-0000-4000-8000-000000000001',
    'period', 'all', 'page_size', 100
  )) -> 'batches'),
  3,
  'operator role sees only its own generation batches'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.creator_generation_archive(
      jsonb_build_object(
        'organization_id', 'a8200000-0000-4000-8000-000000000001',
        'period', 'all', 'page_size', 100
      )
    ) -> 'batches') item
    where (item ->> 'id')::uuid not in (
      'a8500000-0000-4000-8000-000000000001',
      'a8500000-0000-4000-8000-000000000002',
      'a8500000-0000-4000-8000-000000000003'
    )
  ),
  'self scope cannot leak a teammate batch'
);

select set_config(
  'request.jwt.claim.sub',
  'a8100000-0000-4000-8000-000000000003',
  true
);
select throws_ok(
  $$
    select public.creator_generation_archive(jsonb_build_object(
      'organization_id', 'a8200000-0000-4000-8000-000000000001'
    ))
  $$,
  '42501',
  'active_membership_required',
  'an active member of another tenant cannot cross the organization boundary'
);

select set_config(
  'request.jwt.claim.sub',
  'a8100000-0000-4000-8000-000000000001',
  true
);
select throws_ok(
  $$select public.creator_generation_archive('{"period":"year"}'::jsonb)$$,
  '22023', 'generation_archive_period_invalid',
  'unknown periods fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive('{"status":"unknown"}'::jsonb)$$,
  '22023', 'generation_archive_status_invalid',
  'unknown status groups fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive('{"page_size":101}'::jsonb)$$,
  '22023', 'generation_archive_page_size_invalid',
  'oversized pages fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive(
    '{"cursor":{"at":"not-a-time","id":"not-a-uuid"}}'::jsonb
  )$$,
  '22023', 'generation_archive_cursor_invalid',
  'malformed keysets fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive(
    jsonb_build_object('query', E'unsafe\nquery')
  )$$,
  '22023', 'generation_archive_query_invalid',
  'control characters in search fail closed'
);
select throws_ok(
  $$select public.creator_generation_archive('{"extra":true}'::jsonb)$$,
  '22023', 'generation_archive_payload_invalid',
  'unknown payload fields fail closed'
);

reset role;

select is(
  (
    select count(*)::integer
    from content_factory.generation_batches batch
    where batch.organization_id =
      'a8200000-0000-4000-8000-000000000001'
      and not exists (
        select 1
        from generation_archive_seen seen
        where seen.batch_id = batch.id
      )
  ),
  0,
  'pagination leaves no in-tenant gap'
);
select is(
  (
    select count(*)::integer
    from generation_archive_seen seen
    join content_factory.generation_batches batch on batch.id = seen.batch_id
    where batch.organization_id <>
      'a8200000-0000-4000-8000-000000000001'
  ),
  0,
  'team archive never leaks another tenant'
);
select ok(
  not exists (
    select 1
    from (
      select
        batch.created_at,
        batch.id,
        lag(batch.created_at) over (
          order by seen.page_number, seen.row_number
        ) as previous_at,
        lag(batch.id) over (
          order by seen.page_number, seen.row_number
        ) as previous_id
      from generation_archive_seen seen
      join content_factory.generation_batches batch on batch.id = seen.batch_id
    ) ordered
    where ordered.previous_at is not null
      and (ordered.created_at, ordered.id) >=
        (ordered.previous_at, ordered.previous_id)
  ),
  'the complete archive is strictly descending across page boundaries'
);
select is(
  (select count(*) from content_factory.generation_batches),
  (select batches from generation_archive_snapshot),
  'archive reads do not mutate generation batches'
);
select is(
  (select count(*) from content_factory.products),
  (select products from generation_archive_snapshot),
  'archive reads do not mutate products'
);

select * from finish();
rollback;

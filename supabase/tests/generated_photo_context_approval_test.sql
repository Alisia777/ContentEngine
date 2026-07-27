begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(11);

create or replace function pg_temp.context_review_result(
  p_include_non_context_blocker boolean
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'overall_score', 86,
    'scores', jsonb_build_object(
      'technical', 88,
      'product_fidelity', 84,
      'hook_clarity', 82,
      'visual_quality', 87,
      'trust', 80,
      'platform_fit', 86,
      'accessibility', 85
    ),
    'compliance_status', 'block',
    'blockers_count', case when p_include_non_context_blocker then 3 else 2 end,
    'warnings_count', 1,
    'strengths', jsonb_build_array('Товар читается'),
    'findings', jsonb_build_array(
      jsonb_build_object(
        'code', 'AD.MARKING.ERID',
        'category', 'legal',
        'severity', 'blocker',
        'title', 'Нет ERID',
        'detail', 'ERID ещё не добавлен.',
        'action', 'Добавьте ERID.'
      ),
      jsonb_build_object(
        'code', 'RIGHTS.MEDIA',
        'category', 'rights',
        'severity', 'blocker',
        'title', 'Права не подтверждены',
        'detail', 'Нужно подтверждение прав.',
        'action', 'Подтвердите права.'
      ),
      jsonb_build_object(
        'code', 'PLATFORM.CURRENT_STATUS_REVIEW',
        'category', 'platform',
        'severity', 'high',
        'title', 'Нужна проверка площадки',
        'detail', 'Статус проверяет человек.',
        'action', 'Проверьте актуальный статус.',
        'human_review_required', true
      )
    ) || case when p_include_non_context_blocker then
      jsonb_build_array(jsonb_build_object(
        'code', 'CLAIM.RESEARCH_FORBIDDEN_EXACT',
        'category', 'claim',
        'severity', 'blocker',
        'title', 'Запрещённый claim',
        'detail', 'В самом изображении есть запрещённое обещание.',
        'action', 'Создайте исправленный файл.'
      ))
    else '[]'::jsonb end,
    'recommendations', jsonb_build_array(
      jsonb_build_object(
        'code', 'FIX.AD.MARKING.ERID',
        'category', 'compliance',
        'priority', 'high',
        'title', 'Добавить ERID',
        'detail', 'Заполнить точный идентификатор.',
        'action', 'Получить ERID.'
      ),
      jsonb_build_object(
        'code', 'KEEP.PLATFORM',
        'category', 'compliance',
        'priority', 'high',
        'title', 'Проверить площадку',
        'detail', 'Проверить актуальный статус.',
        'action', 'Зафиксировать решение.'
      )
    ),
    'comparison', jsonb_build_object(
      'previous_score', null,
      'delta', null,
      'summary', 'Первая проверка.'
    ),
    'ad_probability', 0.98,
    'ad_classification_summary', 'Материал является рекламным.',
    'limitations', jsonb_build_array('ИИ не заменяет решение человека.')
  )
$$;

select ok(
  to_regprocedure(
    'public.creator_approve_generated_photo_review_with_context(jsonb)'
  ) is not null,
  'generated-photo context approval RPC is available'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_approve_generated_photo_review_with_context'
  ),
  'generated-photo context approval is SECURITY DEFINER'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_context_amendments'
  ),
  'context amendment provenance keeps RLS enabled'
);

select is(
  has_table_privilege(
    'authenticated',
    'content_factory.content_review_context_amendments',
    'select'
  ),
  false,
  'browser users cannot read amendment provenance directly'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_context_amendments'
      and trigger_row.tgname =
        'reject_content_review_context_amendment_mutation'
      and not trigger_row.tgisinternal
  ),
  'context amendment provenance is append-only'
);

select is(
  (
    content_factory_private.generated_photo_context_result(
      pg_temp.context_review_result(false)
    ) ->> 'blockers_count'
  )::integer,
  0,
  'verified context removes only its deterministic blockers'
);

select is(
  content_factory_private.generated_photo_context_result(
    pg_temp.context_review_result(false)
  ) ->> 'compliance_status',
  'human_review',
  'remaining platform risk still requires a human'
);

select ok(
  not (
    content_factory_private.generated_photo_context_result(
      pg_temp.context_review_result(false)
    ) -> 'recommendations'
  ) @> jsonb_build_array(jsonb_build_object(
    'code', 'FIX.AD.MARKING.ERID'
  )),
  'recommendation for the supplied ERID is removed'
);

select is(
  (
    content_factory_private.generated_photo_context_result(
      pg_temp.context_review_result(true)
    ) ->> 'blockers_count'
  )::integer,
  1,
  'a claim blocker in the actual PNG is never hidden by context'
);

select ok(
  (
    content_factory_private.generated_photo_context_result(
      pg_temp.context_review_result(true)
    ) -> 'findings'
  ) @> jsonb_build_array(jsonb_build_object(
    'code', 'CLAIM.RESEARCH_FORBIDDEN_EXACT',
    'severity', 'blocker'
  )),
  'non-context content blocker remains exact in the derived result'
);

select ok(
  (
    content_factory_private.generated_photo_context_result(
      jsonb_set(
        pg_temp.context_review_result(false),
        '{limitations}',
        (
          select jsonb_agg('Ограничение ' || number order by number)
          from generate_series(1, 20) number
        )
      )
    ) -> 'limitations'
  ) @> jsonb_build_array(
    'Визуальная модель повторно не запускалась: изменён только подтверждённый человеком контекст публикации generated-photo-context-v1.'
  ),
  'derived result always discloses that visual AI was not rerun'
);

select * from finish();
rollback;

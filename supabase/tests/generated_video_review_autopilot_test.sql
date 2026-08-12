begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(13);

create or replace function pg_temp.video_context_result(
  p_include_non_context_blocker boolean
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'overall_score', 84,
    'scores', jsonb_build_object(
      'technical', 87,
      'product_fidelity', 82,
      'hook_clarity', 83,
      'visual_quality', 85,
      'trust', 80,
      'platform_fit', 84,
      'accessibility', 78
    ),
    'compliance_status', 'block',
    'blockers_count',
      case when p_include_non_context_blocker then 3 else 2 end,
    'warnings_count', 2,
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
        'code', 'ACCESSIBILITY.CAPTIONS',
        'category', 'accessibility',
        'severity', 'medium',
        'title', 'Субтитры не подтверждены',
        'detail', 'Их проверяет человек.',
        'action', 'Проверьте титры.'
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
        'code', 'VIDEO.FROZEN_TIMELINE',
        'category', 'technical',
        'severity', 'blocker',
        'title', 'Ролик замер',
        'detail', 'В самом MP4 есть длинный замерший участок.',
        'action', 'Создайте исправленный ролик.'
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
        'code', 'FIX.ACCESSIBILITY.CAPTIONS',
        'category', 'accessibility',
        'priority', 'high',
        'title', 'Проверить субтитры',
        'detail', 'Проверить синхронизацию.',
        'action', 'Просмотреть MP4.'
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
    'public.creator_start_generated_video_review(jsonb)'
  ) is not null,
  'generated-video start RPC is available'
);

select ok(
  to_regprocedure(
    'public.creator_approve_generated_video_review_with_context(jsonb)'
  ) is not null,
  'generated-video context approval RPC is available'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_review_category_v1(jsonb)'
  ) is not null,
  'prior monetary generation gate remains private and callable'
);

select ok(
  pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_ai_speech_v56%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_ai_speech_v56(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_ai_research_prompt_v55%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_ai_research_prompt_v55(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_video_reference_v54%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_video_reference_v54(jsonb)'::regprocedure
  ) like '%call_project_scoped_v47%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_project_v47(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_generation_spec_v15%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_generation_spec_v15(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_category_learning_v14%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_category_learning_v14(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_single_reference_v13%'
  and pg_get_functiondef(
    'public.creator_start_real_generation_single_reference_v13(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_flexible_duration_v12%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_review_autostart_v11%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_review_autostart_v11(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_mode_prompt_v10%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_mode_prompt_v10(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_policy_snapshot_v9%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_policy_snapshot_v9(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_guard_lineage_v8%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_guard_lineage_v8(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_review_category_v1%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_guard_lineage_v8(jsonb)'::regprocedure
  ) like '%product_category%',
  'public generation chain preserves category binding before returning'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_start_generated_video_review'
  ),
  'generated-video start RPC is SECURITY DEFINER'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_approve_generated_video_review_with_context'
  ),
  'generated-video context approval RPC is SECURITY DEFINER'
);

select ok(
  'ACCESSIBILITY.CAPTIONS' = any(
    content_factory_private.generated_video_context_resolvable_codes()
  ),
  'captions are a human-resolvable final publication fact'
);

select is(
  (
    content_factory_private.generated_video_context_result(
      pg_temp.video_context_result(false)
    ) ->> 'blockers_count'
  )::integer,
  0,
  'video context removes only deterministic publication blockers'
);

select is(
  content_factory_private.generated_video_context_result(
    pg_temp.video_context_result(false)
  ) ->> 'compliance_status',
  'human_review',
  'remaining platform risk still requires a human'
);

select is(
  (
    content_factory_private.generated_video_context_result(
      pg_temp.video_context_result(true)
    ) ->> 'blockers_count'
  )::integer,
  1,
  'actual video-content blocker survives context amendment'
);

select ok(
  (
    content_factory_private.generated_video_context_result(
      pg_temp.video_context_result(true)
    ) -> 'findings'
  ) @> jsonb_build_array(jsonb_build_object(
    'code', 'VIDEO.FROZEN_TIMELINE',
    'severity', 'blocker'
  )),
  'exact technical blocker remains in the derived result'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'::regprocedure
  ) like '%''external_ai_processing_confirmed'', true%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_generated_video_review_pre_project_v47(jsonb)'::regprocedure
  ) like '%''transcription_requested'', false%'
  and pg_get_functiondef(
    'public.creator_start_generated_video_review(jsonb)'::regprocedure
  ) like '%creator_start_generated_video_review_pre_project_v47%',
  'transcription remains an explicit opt-in outside autopilot'
);

select ok(
  (
    content_factory_private.generated_video_context_result(
      pg_temp.video_context_result(false)
    ) -> 'limitations'
  ) @> jsonb_build_array(
    'Визуальная модель повторно не запускалась: изменён только подтверждённый человеком контекст публикации generated-video-context-v1.'
  ),
  'derived video result discloses that visual AI was not rerun'
);

select * from finish();
rollback;

begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(10);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'product_focus',
      'preferred_hook_patterns', jsonb_build_array('concise'),
      'quality_guard_codes',
        jsonb_build_array('audio_quality', 'speech_fidelity')
    ),
    'seedance2_fast'
  ),
  array[
    'Обученное направление: товар главный во всех кадрах.',
    'Структурный hook: простой первый кадр сразу показывает товар.',
    'QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.',
    'QA: реплика произносится дословно, без пропусков, замен и новых слов.'
  ]::text[],
  'Seedance learning compiles bounded audio and exact-speech guards'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array(
      'product_fidelity',
      'audio_quality',
      'speech_fidelity'
    ),
    'seedance2_fast'
  ),
  array[
    'QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.',
    'QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.',
    'QA: реплика произносится дословно, без пропусков, замен и новых слов.'
  ]::text[],
  'Seedance repair keeps visual and specialized audio guards bounded'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'product_focus',
      'preferred_hook_patterns', jsonb_build_array('concise'),
      'quality_guard_codes', jsonb_build_array('audio_quality')
    ),
    'gen4_turbo'
  ),
  null::text[],
  'Gen4 cannot accept a learned audio guard'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array('speech_fidelity'),
    'seedream5_lite'
  ),
  null::text[],
  'photo repair cannot accept a speech guard'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array('audio_quality', 'audio_quality'),
    'seedance2_fast'
  ),
  null::text[],
  'duplicate specialized guards fail closed'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array('raw_transcript'),
    'seedance2_fast'
  ),
  null::text[],
  'free-form transcript material cannot become a prompt guard'
);

select ok(
  to_regprocedure(
    'public.creator_generation_learning_policy(jsonb)'
  ) is not null,
  'the specialized learning policy remains available'
);

select ok(
  to_regprocedure(
    'public.creator_generation_repair_policy(jsonb)'
  ) is not null,
  'the specialized repair policy remains available'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_generation_learning_policy_quality_guards_v4(jsonb)'
  ) is not null,
  'the prior quality-learning implementation is private'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_generation_repair_policy_structured_scores_v1(jsonb)'
  ) is not null,
  'the prior immediate-repair implementation is private'
);

select * from finish();
rollback;

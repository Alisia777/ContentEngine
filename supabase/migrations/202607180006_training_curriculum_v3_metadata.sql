begin;

-- Curriculum v3 adds role, phase, glossary and achievement metadata without
-- changing the four stable course codes, private grading, exam prerequisites or
-- the existing flat lessons array consumed by older clients.

-- Match the novice's real work order: orient -> verify product/money/safety ->
-- create/review -> publish/return the result. Temporary values avoid the unique
-- order index while swapping the existing second, third and fourth courses.
update content_factory.training_modules
set order_index = order_index + 500
where code in ('factory_basics', 'video_quality', 'publishing_funnel', 'security_wb');

update content_factory.training_modules
set order_index = case code
  when 'factory_basics' then 10
  when 'security_wb' then 20
  when 'video_quality' then 30
  when 'publishing_funnel' then 40
end
where code in ('factory_basics', 'video_quality', 'publishing_funnel', 'security_wb');

update content_factory.training_modules module
set title = 'Старт: роль, вход и первая задача',
    description = 'Как понять свою роль, сверить точный товар и пройти первый безопасный маршрут в портале.',
    content = (
  module.content
  || jsonb_build_object(
    'version', 3,
    'block_label', 'Блок 1 · старт и первая задача',
    'audience_label', 'Всем ролям · общий старт',
    'role_tracks', jsonb_build_object(
      'all', jsonb_build_object('label', 'Общий маршрут', 'required', true),
      'self', jsonb_build_object('label', 'Снимаю сам', 'required', true),
      'ai', jsonb_build_object('label', 'Создаю с ИИ', 'required', true),
      'publish', jsonb_build_object('label', 'Публикую', 'required', true),
      'review', jsonb_build_object('label', 'Проверяю ролики', 'required', true)
    ),
    'lesson_groups', jsonb_build_array(
      jsonb_build_object(
        'id', 'start', 'title', 'Вход, роль и первая задача',
        'lesson_ids', jsonb_build_array(
          'first_access_route', 'factory_map', 'interface_map'
        )
      ),
      jsonb_build_object(
        'id', 'preflight', 'title', 'Товар и исходники до производства',
        'lesson_ids', jsonb_build_array('sku_and_sources', 'traceable_cycle')
      ),
      jsonb_build_object(
        'id', 'generation_reference', 'title', 'Справка по режимам генерации',
        'lesson_ids', jsonb_build_array('generation_modes')
      )
    ),
    'achievement', jsonb_build_object(
      'code', 'portal_navigator',
      'icon', '✦',
      'name', 'Навигатор ALTEA',
      'description', 'Вы знаете путь товара от задания до подтверждённого результата.'
    ),
    'glossary', jsonb_build_array(
      jsonb_build_object('term', 'Артикул', 'definition', 'Точный код конкретного варианта товара.'),
      jsonb_build_object('term', 'Исходник', 'definition', 'Разрешённое фото или видео, из которого создают ролик.'),
      jsonb_build_object('term', 'Публичная ссылка', 'definition', 'Ссылка, по которой зритель открывает сам опубликованный ролик.')
    )
  )
  || jsonb_build_object(
    'lessons', coalesce((
      select jsonb_agg(
        lesson.value
        || case lesson.value ->> 'id'
          when 'first_access_route' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'access', 'required_core', true)
          when 'factory_map' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'orientation', 'required_core', true)
          when 'interface_map' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'orientation', 'required_core', true)
          when 'sku_and_sources' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'preflight', 'required_core', true)
          when 'generation_modes' then jsonb_build_object('audiences', jsonb_build_array('ai'), 'phase', 'production_reference', 'required_core', false)
          when 'traceable_cycle' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'result', 'required_core', true)
          else jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'reference', 'required_core', true)
        end
        order by lesson.ordinality
      )
      from jsonb_array_elements(module.content -> 'lessons')
        with ordinality lesson(value, ordinality)
    ), '[]'::jsonb)
  )
)
where module.code = 'factory_basics'
  and module.module_type = 'course';

update content_factory.training_modules module
set title = 'Как снять или сгенерировать ролик и проверить его',
    description = 'Ролевые ветки съёмки и ИИ, сценарий на восемь секунд и общая проверка качества всего файла.',
    content = (
  module.content
  || jsonb_build_object(
    'version', 3,
    'block_label', 'Блок 3 · создание и проверка ролика',
    'audience_label', 'Съёмка и ИИ · проверка всем',
    'role_tracks', jsonb_build_object(
      'all', jsonb_build_object('label', 'Общая проверка', 'required', true),
      'self', jsonb_build_object('label', 'Снимаю сам', 'required', true),
      'ai', jsonb_build_object('label', 'Создаю с ИИ', 'required', true),
      'publish', jsonb_build_object('label', 'Принимаю готовый файл', 'required', false),
      'review', jsonb_build_object('label', 'Проверяю весь файл', 'required', true)
    ),
    'lesson_groups', jsonb_build_array(
      jsonb_build_object('id', 'self', 'title', 'Ветка: снимаю сам', 'lesson_ids', jsonb_build_array('shoot_vertical_source')),
      jsonb_build_object('id', 'ai', 'title', 'Ветка: создаю с ИИ', 'lesson_ids', jsonb_build_array('reference_pack', 'generation_form')),
      jsonb_build_object('id', 'story', 'title', 'Сценарий на восемь секунд', 'lesson_ids', jsonb_build_array('prompt_anatomy', 'eight_second_storyboard')),
      jsonb_build_object('id', 'quality', 'title', 'Общая проверка качества', 'lesson_ids', jsonb_build_array('full_video_qa'))
    ),
    'achievement', jsonb_build_object(
      'code', 'video_under_control',
      'icon', '◉',
      'name', 'Ролик под контролем',
      'description', 'Вы умеете создать вертикальный ролик и остановить файл с дефектом или неверным товаром.'
    ),
    'glossary', jsonb_build_array(
      jsonb_build_object('term', '9:16', 'definition', 'Вертикальный формат кадра для коротких роликов.'),
      jsonb_build_object('term', 'Раскадровка', 'definition', 'План ролика по отрезкам времени и действиям в кадре.'),
      jsonb_build_object('term', 'Проверка качества', 'definition', 'Полный просмотр файла с проверкой товара, изображения, звука и текста.')
    )
  )
  || jsonb_build_object(
    'lessons', coalesce((
      select jsonb_agg(
        lesson.value
        || case lesson.value ->> 'id'
          when 'shoot_vertical_source' then jsonb_build_object('audiences', jsonb_build_array('self'), 'phase', 'capture', 'required_core', false)
          when 'reference_pack' then jsonb_build_object('audiences', jsonb_build_array('ai'), 'phase', 'ai_preflight', 'required_core', false)
          when 'generation_form' then jsonb_build_object('audiences', jsonb_build_array('ai'), 'phase', 'ai_preflight', 'required_core', false)
          when 'prompt_anatomy' then jsonb_build_object('audiences', jsonb_build_array('self', 'ai'), 'phase', 'story', 'required_core', false)
          when 'eight_second_storyboard' then jsonb_build_object('audiences', jsonb_build_array('self', 'ai'), 'phase', 'story', 'required_core', false)
          when 'full_video_qa' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'quality', 'required_core', true)
          else jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'reference', 'required_core', true)
        end
        order by lesson.ordinality
      )
      from jsonb_array_elements(module.content -> 'lessons')
        with ordinality lesson(value, ordinality)
    ), '[]'::jsonb)
  )
)
where module.code = 'video_quality'
  and module.module_type = 'course';

update content_factory.training_modules module
set title = 'Как подготовить аккаунт, опубликовать и вернуть результат',
    description = 'Безопасный старт аккаунта, рекламное стоп-правило, назначенная площадка, final URL и метрики.',
    content = (
  module.content
  || jsonb_build_object(
    'version', 3,
    'block_label', 'Блок 4 · публикация и результат',
    'audience_label', 'Публикаторам · остальным как рабочая база',
    'role_tracks', jsonb_build_object(
      'all', jsonb_build_object('label', 'Общие правила передачи результата', 'required', true),
      'self', jsonb_build_object('label', 'Передаю файл публикатору', 'required', false),
      'ai', jsonb_build_object('label', 'Передаю файл публикатору', 'required', false),
      'publish', jsonb_build_object('label', 'Публикую и фиксирую результат', 'required', true),
      'review', jsonb_build_object('label', 'Проверяю решение и доказательство', 'required', true)
    ),
    'lesson_groups', jsonb_build_array(
      jsonb_build_object('id', 'account', 'title', 'Доступ и безопасный старт аккаунта', 'lesson_ids', jsonb_build_array('social_account_access', 'new_account_safe_start')),
      jsonb_build_object('id', 'approval', 'title', 'От одобрения до публикации', 'lesson_ids', jsonb_build_array('approved_to_task', 'three_urls', 'publication_sequence', 'advertising_classification_and_labeling')),
      jsonb_build_object('id', 'instagram', 'title', 'Instagram Reels', 'lesson_ids', jsonb_build_array('instagram_reels_step_by_step')),
      jsonb_build_object('id', 'youtube', 'title', 'YouTube Shorts', 'lesson_ids', jsonb_build_array('youtube_shorts_step_by_step')),
      jsonb_build_object('id', 'vk', 'title', 'VK и VK Клипы', 'lesson_ids', jsonb_build_array('vk_id_and_business_community', 'vk_clips_step_by_step')),
      jsonb_build_object('id', 'result', 'title', 'Ссылка, метрики и передача результата', 'lesson_ids', jsonb_build_array('metric_snapshot', 'payout_separation'))
    ),
    'achievement', jsonb_build_object(
      'code', 'safe_publisher',
      'icon', '↗',
      'name', 'Безопасный публикатор',
      'description', 'Вы знаете, когда публикацию можно выпускать и какую ссылку вернуть в портал.'
    ),
    'glossary', jsonb_build_array(
      jsonb_build_object('term', 'Двухфакторная защита', 'definition', 'Дополнительное подтверждение входа помимо пароля.'),
      jsonb_build_object('term', 'Рекламная проверка', 'definition', 'Обязательная остановка до публикации, если материал может считаться рекламой.'),
      jsonb_build_object('term', 'Снимок метрик', 'definition', 'Значения показателей с указанием источника и времени проверки.')
    )
  )
  || jsonb_build_object(
    'lessons', coalesce((
      select jsonb_agg(
        lesson.value
        || case lesson.value ->> 'id'
          when 'social_account_access' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'account_access', 'required_core', false)
          when 'new_account_safe_start' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'account_start', 'required_core', false)
          when 'approved_to_task' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'handoff', 'required_core', true)
          when 'three_urls' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'publication', 'required_core', false)
          when 'publication_sequence' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'publication', 'required_core', false)
          when 'advertising_classification_and_labeling' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'policy_gate', 'required_core', true)
          when 'instagram_reels_step_by_step' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'platform', 'platform', 'instagram', 'required_core', false)
          when 'youtube_shorts_step_by_step' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'platform', 'platform', 'youtube', 'required_core', false)
          when 'vk_id_and_business_community' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'platform', 'platform', 'vk', 'required_core', false)
          when 'vk_clips_step_by_step' then jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'platform', 'platform', 'vk', 'required_core', false)
          when 'metric_snapshot' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'result', 'required_core', true)
          when 'payout_separation' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'money_reference', 'required_core', false)
          else jsonb_build_object('audiences', jsonb_build_array('publish'), 'phase', 'reference', 'required_core', false)
        end
        order by lesson.ordinality
      )
      from jsonb_array_elements(module.content -> 'lessons')
        with ordinality lesson(value, ordinality)
    ), '[]'::jsonb)
  )
)
where module.code = 'publishing_funnel'
  and module.module_type = 'course';

update content_factory.training_modules module
set title = 'Товар, подменный артикул, расчёт и безопасность',
    description = 'Что проверить до производства: права, точный и подменный артикулы, сумма, статусы начисления и выплаты.',
    content = (
  module.content
  || jsonb_build_object(
    'version', 3,
    'block_label', 'Блок 2 · товар, безопасность и деньги',
    'audience_label', 'Всем ролям · товар и деньги',
    'role_tracks', jsonb_build_object(
      'all', jsonb_build_object('label', 'Общий безопасный маршрут', 'required', true),
      'self', jsonb_build_object('label', 'Сверяю товар и начисление', 'required', true),
      'ai', jsonb_build_object('label', 'Сверяю товар и начисление', 'required', true),
      'publish', jsonb_build_object('label', 'Подтверждаю результат и статус', 'required', true),
      'review', jsonb_build_object('label', 'Проверяю товар, риск и статус', 'required', true)
    ),
    'lesson_groups', jsonb_build_array(
      jsonb_build_object('id', 'boundaries', 'title', 'Границы, права и стоп-правило', 'lesson_ids', jsonb_build_array('secret_boundary', 'rights_and_claims', 'incident_stop')),
      jsonb_build_object('id', 'article', 'title', 'Основной и подменный артикул', 'lesson_ids', jsonb_build_array('wb_alias_history')),
      jsonb_build_object('id', 'money', 'title', 'Начисление, выплата и безопасный повтор', 'lesson_ids', jsonb_build_array('calculation_and_payout', 'safe_retry'))
    ),
    'achievement', jsonb_build_object(
      'code', 'cycle_closed',
      'icon', '◆',
      'name', 'Цикл закрыт',
      'description', 'Вы умеете сверить товар, доказательство результата, начисление и фактическую выплату.'
    ),
    'glossary', jsonb_build_array(
      jsonb_build_object('term', 'Подменный артикул', 'definition', 'Дополнительный артикул того же подтверждённого товара, назначенный в задаче.'),
      jsonb_build_object('term', 'Начислено', 'definition', 'Сумма рассчитана в портале, но ещё не обязательно переведена.'),
      jsonb_build_object('term', 'Выплачено', 'definition', 'Внешний перевод подтверждён отдельным фактом оплаты.')
    )
  )
  || jsonb_build_object(
    'lessons', coalesce((
      select jsonb_agg(
        lesson.value
        || case lesson.value ->> 'id'
          when 'secret_boundary' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'safety', 'required_core', true)
          when 'rights_and_claims' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'policy_gate', 'required_core', true)
          when 'incident_stop' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'escalation', 'required_core', true)
          when 'wb_alias_history' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'article', 'required_core', true)
          when 'calculation_and_payout' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'money', 'required_core', true)
          when 'safe_retry' then jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'recovery', 'required_core', true)
          else jsonb_build_object('audiences', jsonb_build_array('all'), 'phase', 'reference', 'required_core', true)
        end
        order by lesson.ordinality
      )
      from jsonb_array_elements(module.content -> 'lessons')
        with ordinality lesson(value, ordinality)
    ), '[]'::jsonb)
  )
)
where module.code = 'security_wb'
  and module.module_type = 'course';

-- Every mandatory course keeps at least one useful practice for every role.
-- Role-specific production/publishing drills remain available as additions.
update content_factory.training_modules module
set content = jsonb_set(
  module.content,
  '{interactive_walkthroughs}',
  coalesce((
    select jsonb_agg(
      walkthrough.value
      || case
        when module.code = 'video_quality'
             and walkthrough.value ->> 'id' = 'eight_second_quality'
          then jsonb_build_object('audience', 'all', 'audience_label', 'Всем, кто создаёт или проверяет ролик')
        when module.code = 'publishing_funnel'
             and walkthrough.value ->> 'id' = 'advertising_stop_decision'
          then jsonb_build_object('audience', 'all', 'audience_label', 'Всем участникам до передачи на публикацию')
        else '{}'::jsonb
      end
      order by walkthrough.ordinality
    )
    from jsonb_array_elements(module.content -> 'interactive_walkthroughs')
      with ordinality walkthrough(value, ordinality)
  ), '[]'::jsonb),
  true
)
where module.code in ('video_quality', 'publishing_funnel')
  and module.module_type = 'course'
  and jsonb_typeof(module.content -> 'interactive_walkthroughs') = 'array';

do $$
declare
  invalid_count integer;
begin
  select count(*)
  into invalid_count
  from content_factory.training_modules module
  where module.code in (
    'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
  )
    and (
      module.module_type <> 'course'
      or module.content ->> 'version' <> '3'
      or jsonb_typeof(module.content -> 'role_tracks') <> 'object'
      or jsonb_typeof(module.content -> 'lesson_groups') <> 'array'
      or jsonb_typeof(module.content -> 'achievement') <> 'object'
      or jsonb_typeof(module.content -> 'glossary') <> 'array'
      or not (module.content -> 'role_tracks' ? 'review')
      or nullif(module.content ->> 'block_label', '') is null
      or exists (
        select 1
        from jsonb_array_elements(module.content -> 'lessons') lesson(value)
        where jsonb_typeof(lesson.value -> 'audiences') <> 'array'
          or nullif(lesson.value ->> 'phase', '') is null
          or jsonb_typeof(lesson.value -> 'required_core') <> 'boolean'
      )
    );
  if invalid_count <> 0 then
    raise exception using
      errcode = '23514',
      message = 'training_curriculum_v3_metadata_invalid';
  end if;

  if (
    select count(*)
    from content_factory.training_modules module
    where module.code in (
      'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
    )
      and module.content ->> 'version' = '3'
  ) <> 4 then
    raise exception using
      errcode = '23514',
      message = 'training_curriculum_v3_course_count_invalid';
  end if;

  if exists (
    select 1
    from content_factory.training_modules module
    cross join lateral jsonb_array_elements(module.content -> 'lessons') lesson(value)
    where module.code in (
      'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
    )
    group by module.code, lesson.value ->> 'id'
    having count(*) > 1
  ) then
    raise exception using
      errcode = '23514',
      message = 'training_curriculum_v3_duplicate_lesson';
  end if;

  if exists (
    select 1
    from content_factory.training_modules module
    where module.code in (
      'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
    )
      and (
        jsonb_array_length(module.content -> 'lessons') <> (
          select count(*)
          from jsonb_array_elements(module.content -> 'lesson_groups') lesson_group(value)
          cross join lateral jsonb_array_elements_text(lesson_group.value -> 'lesson_ids') grouped_lesson(id)
        )
        or jsonb_array_length(module.content -> 'lessons') <> (
          select count(distinct grouped_lesson.id)
          from jsonb_array_elements(module.content -> 'lesson_groups') lesson_group(value)
          cross join lateral jsonb_array_elements_text(lesson_group.value -> 'lesson_ids') grouped_lesson(id)
        )
        or exists (
          select 1
          from jsonb_array_elements(module.content -> 'lesson_groups') lesson_group(value)
          cross join lateral jsonb_array_elements_text(lesson_group.value -> 'lesson_ids') grouped_lesson(id)
          where not exists (
            select 1
            from jsonb_array_elements(module.content -> 'lessons') lesson(value)
            where lesson.value ->> 'id' = grouped_lesson.id
          )
        )
      )
  ) then
    raise exception using
      errcode = '23514',
      message = 'training_curriculum_v3_lesson_group_topology_invalid';
  end if;

  if exists (
    select 1
    from content_factory.training_modules module
    where (module.code, module.order_index) not in (
      ('factory_basics', 10),
      ('security_wb', 20),
      ('video_quality', 30),
      ('publishing_funnel', 40)
    )
      and module.code in (
        'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
      )
  ) then
    raise exception using
      errcode = '23514',
      message = 'training_curriculum_v3_course_order_invalid';
  end if;
end;
$$;

commit;

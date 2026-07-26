begin;

-- Explain the boundary between the dense browser-local timeline scan and the
-- retained human decision. More samples reduce blind spots but never become a
-- claim that every decoded frame, word, label, or transition was reviewed.
update content_factory.training_modules module
set
  content = jsonb_set(
    module.content,
    '{lessons}',
    (
      select jsonb_agg(
        case
          when lesson.item ->> 'id' = 'full_video_qa' then
            lesson.item || jsonb_build_object(
              'title', 'Как принять готовое фото или видео',
              'body', 'Откройте конкретный результат в полном размере. Для фото сверьте упаковку, логотип, весь видимый текст, геометрию, цвет, лишние объекты и поля кадра. Для видео браузер локально и без внешней отправки проверяет от 12 до 24 равномерных точек почти по всей длительности: это помогает найти краткий чёрный участок или длительное замирание между пятью сохранёнными кадрами. Отдельно измеряются уровень звука, доля тишины, клиппинг и разница длительности. Но выборка не является покадровым декодированием, а аудиометрики не расшифровывают слова и не подтверждают музыку. Поэтому просмотрите файл от первого до последнего кадра со звуком и вручную сверьте товар, руки и лицо, дословную реплику, титры, переходы и опасные обещания. Статус succeeded или «Готово» не означает одобрение.',
              'takeaway', 'Локальный таймлайн-скан уменьшает слепые зоны; человек подтверждает каждый смысловой риск полным просмотром конкретного MP4.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Три уровня evidence готового видео',
                'question', 'Какой уровень что доказывает?',
                'branches', jsonb_build_array(
                  jsonb_build_object(
                    'condition', 'До пяти сохранённых кадров',
                    'action', 'Внешний AI проверяет видимые товар, композицию, текст и риски только в этих точках',
                    'tone', 'neutral'
                  ),
                  jsonb_build_object(
                    'condition', '12–24 локальные точки таймлайна и аудиометрики',
                    'action', 'Портал ищет измеримые чёрные, зависшие, немые или перегруженные участки без отправки дополнительного медиа',
                    'tone', 'warning'
                  ),
                  jsonb_build_object(
                    'condition', 'Полный просмотр человеком со звуком',
                    'action', 'Проверяющий подтверждает слова, музыку, все переходы, постоянство товара и итоговое решение',
                    'tone', 'success'
                  )
                )
              )
            )
          else lesson.item
        end
        order by lesson.ordinality
      )
      from jsonb_array_elements(module.content -> 'lessons')
        with ordinality as lesson(item, ordinality)
    ),
    false
  ),
  updated_at = now()
where module.code = 'video_quality'
  and module.module_type = 'course'
  and module.is_active;

with rewritten_options as (
  select
    question.code,
    jsonb_agg(
      option.item || jsonb_build_object(
        'label',
        case option.item ->> 'value'
          when 'control_frames' then 'Сверить сохранённые кадры, точный товар, речь/субтитры и сохранить конкретные замечания'
          when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
          when 'memory_compare' then 'Считать чистый локальный отчёт достаточным и сравнить этикетку по памяти с прошлым роликом'
          when 'full_playback' then 'Полностью воспроизвести точный файл от первого до последнего кадра со звуком'
          when 'skip_watch' then 'Считать 24 равномерные точки покадровой проверкой и не просматривать промежутки между ними'
          else option.item ->> 'label'
        end
      )
      order by option.ordinality
    ) as options
  from content_factory.training_questions question
  cross join lateral jsonb_array_elements(question.options)
    with ordinality as option(item, ordinality)
  where question.code = 'course_check_video_quality_full_qa'
  group by question.code
)
update content_factory.training_questions question
set
  prompt = 'Портал локально проверил 24 равномерные точки таймлайна, не нашёл чёрных или зависших участков, а пять сохранённых кадров выглядят чисто. Какие проверки всё равно обязательны для воспроизводимого решения?',
  options = rewritten_options.options,
  updated_at = now()
from rewritten_options
where question.code = rewritten_options.code;

update content_factory.training_modules module
set
  content = jsonb_set(
    jsonb_set(
      module.content,
      '{knowledge_check,questions}',
      (
        select jsonb_agg(
          case
            when question.item ->> 'id' =
              'course_check_video_quality_full_qa' then
              question.item || jsonb_build_object(
                'prompt', 'Портал локально проверил 24 равномерные точки таймлайна, не нашёл чёрных или зависших участков, а пять сохранённых кадров выглядят чисто. Какие проверки всё равно обязательны для воспроизводимого решения?',
                'rationale_prompt', 'Объясните разницу между сохранёнными кадрами, локальным временным сканом и полным просмотром конкретного MP4.',
                'options',
                (
                  select jsonb_agg(
                    option.item || jsonb_build_object(
                      'label',
                      case option.item ->> 'value'
                        when 'control_frames' then 'Сверить сохранённые кадры, точный товар, речь/субтитры и сохранить конкретные замечания'
                        when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
                        when 'memory_compare' then 'Считать чистый локальный отчёт достаточным и сравнить этикетку по памяти с прошлым роликом'
                        when 'full_playback' then 'Полностью воспроизвести точный файл от первого до последнего кадра со звуком'
                        when 'skip_watch' then 'Считать 24 равномерные точки покадровой проверкой и не просматривать промежутки между ними'
                        else option.item ->> 'label'
                      end
                    )
                    order by option.ordinality
                  )
                  from jsonb_array_elements(question.item -> 'options')
                    with ordinality as option(item, ordinality)
                )
              )
            else question.item
          end
          order by question.ordinality
        )
        from jsonb_array_elements(
          module.content #> '{knowledge_check,questions}'
        ) with ordinality as question(item, ordinality)
      ),
      false
    ),
    '{knowledge_remediation,course_check_video_quality_full_qa,tip}',
    to_jsonb('Повторите три уровня QA: пять evidence-кадров, 12–24 локальные точки таймлайна и обязательный полный просмотр точного MP4 со звуком.'::text),
    true
  ),
  updated_at = now()
where module.code = 'video_quality'
  and module.module_type = 'course'
  and module.is_active;

do $content_review_temporal_scan_training_contract$
begin
  if (
    select count(*)
    from content_factory.training_modules module
    where module.code = 'video_quality'
      and module.module_type = 'course'
      and module.is_active
      and jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "full_video_qa" && @.body like_regex "12 до 24" && @.body like_regex "не является покадровым")'
      )
      and jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*] ? (@.id == "course_check_video_quality_full_qa" && @.prompt like_regex "24 равномерные точки")'
      )
      and module.content
        #>> '{knowledge_remediation,course_check_video_quality_full_qa,tip}'
          like '%полный просмотр%'
  ) <> 1 then
    raise exception 'content review temporal scan training contract failed';
  end if;

  if not exists (
    select 1
    from content_factory.training_questions question
    where question.code = 'course_check_video_quality_full_qa'
      and question.prompt like '%24 равномерные точки%'
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = 'full_playback'
          and option.item ->> 'label' like '%Полностью воспроизвести%'
      )
  ) then
    raise exception 'content review temporal assessment contract failed';
  end if;
end;
$content_review_temporal_scan_training_contract$;

commit;

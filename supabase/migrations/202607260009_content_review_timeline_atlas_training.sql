begin;

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
              'body', 'Откройте конкретный результат в полном размере. Для фото сверьте упаковку, логотип, весь видимый текст, геометрию, цвет, лишние объекты и поля кадра. Для видео портал сохраняет четыре отдельных контрольных кадра и пятое evidence-изображение — хронологический атлас из 12–24 равномерных точек почти по всей длительности. Мини-кадры атласа читаются слева направо и сверху вниз: по ним нужно искать исчезновение или подмену товара, этикетки, обязательных пометок, человека и краткие визуальные сбои. Отдельно локально измеряются чёрные и зависшие участки, уровень звука, доля тишины, клиппинг и разница длительности. Атлас уменьшает промежутки между наблюдениями, но не является декодированием каждого исходного кадра, а аудиометрики не подтверждают слова и музыку. Поэтому полностью просмотрите точный файл со звуком и вручную сверьте товар, руки и лицо, дословную реплику, титры, переходы и опасные обещания.',
              'takeaway', 'Четыре кадра дают крупные детали, атлас показывает развитие ролика, а человек подтверждает точный MP4 полным просмотром.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Три уровня evidence готового видео',
                'question', 'Какой уровень что доказывает?',
                'branches', jsonb_build_array(
                  jsonb_build_object(
                    'condition', 'Четыре отдельных кадра',
                    'action', 'Проверить крупно товар, композицию, текст и артефакты в ключевых точках',
                    'tone', 'neutral'
                  ),
                  jsonb_build_object(
                    'condition', 'Пятый JPEG — атлас 12–24 точек',
                    'action', 'Проследить хронологию, постоянство товара и краткие визуальные сбои между отдельными кадрами',
                    'tone', 'warning'
                  ),
                  jsonb_build_object(
                    'condition', 'Полный просмотр человеком со звуком',
                    'action', 'Подтвердить каждый переход, речь, музыку и итоговое решение по точному MP4',
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
          when 'control_frames' then 'Сверить четыре отдельных кадра и весь атлас слева направо, сверху вниз'
          when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
          when 'memory_compare' then 'Считать атлас доказательством каждого кадра и сравнить этикетку по памяти'
          when 'full_playback' then 'Полностью воспроизвести точный файл от первого до последнего кадра со звуком'
          when 'skip_watch' then 'Не смотреть MP4, если 24 мини-кадра атласа выглядят чисто'
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
  prompt = 'Портал сохранил четыре контрольных кадра и хронологический атлас из 24 точек, визуальных сбоев не найдено. Какие проверки всё равно обязательны?',
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
                'prompt', 'Портал сохранил четыре контрольных кадра и хронологический атлас из 24 точек, визуальных сбоев не найдено. Какие проверки всё равно обязательны?',
                'rationale_prompt', 'Объясните разницу между четырьмя крупными кадрами, хронологическим атласом и полным просмотром точного MP4.',
                'options',
                (
                  select jsonb_agg(
                    option.item || jsonb_build_object(
                      'label',
                      case option.item ->> 'value'
                        when 'control_frames' then 'Сверить четыре отдельных кадра и весь атлас слева направо, сверху вниз'
                        when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
                        when 'memory_compare' then 'Считать атлас доказательством каждого кадра и сравнить этикетку по памяти'
                        when 'full_playback' then 'Полностью воспроизвести точный файл от первого до последнего кадра со звуком'
                        when 'skip_watch' then 'Не смотреть MP4, если 24 мини-кадра атласа выглядят чисто'
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
    to_jsonb('Повторите три уровня QA: четыре крупные точки, пятый JPEG-атлас таймлайна и обязательный полный просмотр точного MP4 со звуком.'::text),
    true
  ),
  updated_at = now()
where module.code = 'video_quality'
  and module.module_type = 'course'
  and module.is_active;

do $content_review_timeline_atlas_training_contract$
begin
  if (
    select count(*)
    from content_factory.training_modules module
    where module.code = 'video_quality'
      and module.module_type = 'course'
      and module.is_active
      and jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "full_video_qa" && @.body like_regex "хронологический атлас" && @.body like_regex "не является декодированием каждого")'
      )
      and jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*] ? (@.id == "course_check_video_quality_full_qa" && @.prompt like_regex "атлас из 24 точек")'
      )
      and module.content
        #>> '{knowledge_remediation,course_check_video_quality_full_qa,tip}'
          like '%полный просмотр%'
  ) <> 1 then
    raise exception 'content review timeline atlas training contract failed';
  end if;

  if not exists (
    select 1
    from content_factory.training_questions question
    where question.code = 'course_check_video_quality_full_qa'
      and question.prompt like '%атлас из 24 точек%'
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = 'full_playback'
          and option.item ->> 'label' like '%Полностью воспроизвести%'
      )
  ) then
    raise exception 'content review timeline atlas assessment contract failed';
  end if;
end;
$content_review_timeline_atlas_training_contract$;

commit;

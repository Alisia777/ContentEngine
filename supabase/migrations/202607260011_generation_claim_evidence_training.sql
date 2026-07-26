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
              'body', 'Откройте конкретный результат в полном размере. Для фото сверьте упаковку, логотип, весь видимый текст, геометрию, цвет, лишние объекты и поля кадра. Для видео портал сохраняет четыре отдельных контрольных кадра и пятое evidence-изображение — хронологический атлас из 12–24 равномерных точек почти по всей длительности. Мини-кадры атласа читаются слева направо и сверху вниз: по ним нужно искать исчезновение или подмену товара, этикетки, обязательных пометок, человека и краткие визуальные сбои. Если generation job создан из approved AI research, сервер дополнительно привязывает immutable snapshot: hash brief, разрешённые claims и запрещённые обещания. Safe claim означает только наличие исследовательской базы для задания — он не доказывает, что генератор сохранил точный смысл в изображении, речи или титрах. Forbidden claim, заявленный в результате как факт, блокирует публикацию; само указание «не использовать» нарушением не является. Отдельно локально измеряются чёрные и зависшие участки, уровень звука, доля тишины, клиппинг и разница длительности. Атлас, claims evidence и ASR уменьшают слепые зоны, но не заменяют полный просмотр и прослушивание точного файла человеком.',
              'takeaway', 'Сервер доказывает происхождение claims задания, а человек подтверждает их точную реализацию в неизменённом итоговом файле.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Claims: исследование и итоговый файл',
                'question', 'Что именно доказывает каждый уровень?',
                'branches', jsonb_build_array(
                  jsonb_build_object(
                    'condition', 'Server-bound safe claims и hash brief',
                    'action', 'Использовать как разрешённую базу задания, связанную с точным generation job',
                    'tone', 'success'
                  ),
                  jsonb_build_object(
                    'condition', 'Server-bound forbidden claims',
                    'action', 'Блокировать положительное обещание; не считать нарушением явный запрет в ТЗ',
                    'tone', 'danger'
                  ),
                  jsonb_build_object(
                    'condition', 'Полный осмотр и прослушивание результата',
                    'action', 'Подтвердить точный товар, цифры, смысл речи, титры и отсутствие запрещённых обещаний',
                    'tone', 'warning'
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
          when 'control_frames' then 'Сверить четыре кадра, весь атлас и итоговые формулировки с server-bound safe/forbidden claims'
          when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
          when 'memory_compare' then 'Считать safe claims автоматическим доказательством каждой фразы итогового файла'
          when 'full_playback' then 'Полностью воспроизвести точный файл со звуком и проверить товар, речь, титры и запрещённые обещания'
          when 'skip_watch' then 'Не смотреть результат целиком: hash исследования уже доказывает качество генерации'
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
  prompt = 'Для generation job сервер привязал approved research: safe claims, forbidden claims и hash brief. Атлас и автоматическая сверка не нашли ошибок. Какие проверки всё равно обязательны?',
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
                'prompt', 'Для generation job сервер привязал approved research: safe claims, forbidden claims и hash brief. Атлас и автоматическая сверка не нашли ошибок. Какие проверки всё равно обязательны?',
                'rationale_prompt', 'Объясните, почему server-bound research доказывает происхождение задания, но не точность итогового файла.',
                'options',
                (
                  select jsonb_agg(
                    option.item || jsonb_build_object(
                      'label',
                      case option.item ->> 'value'
                        when 'control_frames' then 'Сверить четыре кадра, весь атлас и итоговые формулировки с server-bound safe/forbidden claims'
                        when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
                        when 'memory_compare' then 'Считать safe claims автоматическим доказательством каждой фразы итогового файла'
                        when 'full_playback' then 'Полностью воспроизвести точный файл со звуком и проверить товар, речь, титры и запрещённые обещания'
                        when 'skip_watch' then 'Не смотреть результат целиком: hash исследования уже доказывает качество генерации'
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
    to_jsonb('Server-bound research фиксирует происхождение safe/forbidden claims задания. Итоговый файл всё равно нужно полностью осмотреть, прослушать и сверить с точным товаром.'::text),
    true
  ),
  updated_at = now()
where module.code = 'video_quality'
  and module.module_type = 'course'
  and module.is_active;

do $generation_claim_evidence_training_contract$
begin
  if (
    select count(*)
    from content_factory.training_modules module
    where module.code = 'video_quality'
      and module.module_type = 'course'
      and module.is_active
      and jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "full_video_qa" && @.body like_regex "immutable snapshot" && @.body like_regex "не доказывает")'
      )
      and jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*] ? (@.id == "course_check_video_quality_full_qa" && @.prompt like_regex "safe claims" && @.prompt like_regex "hash brief")'
      )
      and module.content
        #>> '{knowledge_remediation,course_check_video_quality_full_qa,tip}'
          like '%Итоговый файл%'
  ) <> 1 then
    raise exception 'generation claim evidence training contract failed';
  end if;

  if not exists (
    select 1
    from content_factory.training_questions question
    where question.code = 'course_check_video_quality_full_qa'
      and question.prompt like '%forbidden claims%'
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = 'full_playback'
          and option.item ->> 'label' like '%Полностью воспроизвести%'
      )
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = 'memory_compare'
          and option.item ->> 'label' like '%автоматическим доказательством%'
      )
  ) then
    raise exception 'generation claim evidence assessment contract failed';
  end if;
end;
$generation_claim_evidence_training_contract$;

commit;

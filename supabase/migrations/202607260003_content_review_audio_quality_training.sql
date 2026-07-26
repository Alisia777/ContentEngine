begin;

-- Teach the operator what the new browser-local measurements can and cannot
-- prove. They are a deterministic technical gate, never a transcript or a
-- substitute for listening to the complete file.
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
              'body', 'Откройте конкретный результат в полном размере. Для фото сверьте упаковку, логотип, весь видимый текст, геометрию, цвет, лишние объекты и поля кадра. Для видео браузер локально измеряет уровень дорожки, долю тишины, клиппинг и разницу длительности, не отправляя MP4 или звук внешнему AI. Эти числа находят немую или перегруженную дорожку, но не расшифровывают слова и не подтверждают музыку. Поэтому просмотрите файл от первого до последнего кадра со звуком и вручную сверьте товар, руки и лицо, дословную реплику, титры, длительность и опасные обещания. Статус succeeded или «Готово» не означает одобрение.',
              'takeaway', 'Автоматика блокирует измеримый технический дефект; человек подтверждает точные слова, смысл, товар, права и финальную пригодность.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Решение после локального аудио-QA',
                'question', 'Что доказали измерения и полный просмотр?',
                'branches', jsonb_build_array(
                  jsonb_build_object(
                    'condition', 'Ожидаемый звук почти немой, клиппинг критический или дорожка короче видео',
                    'action', 'Не публиковать; прослушать точный MP4, зафиксировать таймкод и вернуть на исправление',
                    'tone', 'danger'
                  ),
                  jsonb_build_object(
                    'condition', 'Уровни в норме, но слова, музыка или субтитры ещё не сверены',
                    'action', 'Не принимать решение до полного просмотра со звуком и ручной смысловой проверки',
                    'tone', 'warning'
                  ),
                  jsonb_build_object(
                    'condition', 'Технический отчёт чистый и человек подтвердил весь файл, товар, реплику и права',
                    'action', 'Одобрить только этот конкретный файл и сохранить решение',
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
          when 'mute_only' then 'Считать автоматическую тишину ошибкой браузера, заменить реплику субтитром и сохранить текущий файл'
          when 'reject_with_timestamps' then 'Не принимать; прослушать точный MP4, зафиксировать тишину и визуальный дефект по таймкоду и вернуть результат на исправление'
          when 'publish_status' then 'Принять файл: succeeded важнее локального отчёта, а слова можно проверить уже после публикации'
          when 'rename_file' then 'Переименовать файл в final_reviewed и передать дальше с предупреждением о возможной тишине'
          else option.item ->> 'label'
        end
      )
      order by option.ordinality
    ) as options
  from content_factory.training_questions question
  cross join lateral jsonb_array_elements(question.options)
    with ordinality as option(item, ordinality)
  where question.code = 'course_check_video_quality_succeeded_status'
  group by question.code
)
update content_factory.training_questions question
set
  prompt = 'Провайдер вернул succeeded, но локальный QA определил 97% тишины при ожидаемой реплике, а на 4-й секунде у блогера появился лишний палец. Как классифицировать результат?',
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
              'course_check_video_quality_succeeded_status' then
              question.item || jsonb_build_object(
                'prompt', 'Провайдер вернул succeeded, но локальный QA определил 97% тишины при ожидаемой реплике, а на 4-й секунде у блогера появился лишний палец. Как классифицировать результат?',
                'rationale_prompt', 'Объясните, что доказывает локальный уровень звука, чего он не расшифровывает и почему succeeded не заменяет полный просмотр.',
                'options',
                (
                  select jsonb_agg(
                    option.item || jsonb_build_object(
                      'label',
                      case option.item ->> 'value'
                        when 'mute_only' then 'Считать автоматическую тишину ошибкой браузера, заменить реплику субтитром и сохранить текущий файл'
                        when 'reject_with_timestamps' then 'Не принимать; прослушать точный MP4, зафиксировать тишину и визуальный дефект по таймкоду и вернуть результат на исправление'
                        when 'publish_status' then 'Принять файл: succeeded важнее локального отчёта, а слова можно проверить уже после публикации'
                        when 'rename_file' then 'Переименовать файл в final_reviewed и передать дальше с предупреждением о возможной тишине'
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
    '{knowledge_remediation,course_check_video_quality_succeeded_status,tip}',
    to_jsonb('Повторите полный QA: локальные уровни находят тишину и клиппинг, но точные слова, музыку, товар и смысл человек проверяет только полным просмотром MP4 со звуком.'::text),
    true
  ),
  updated_at = now()
where module.code = 'video_quality'
  and module.module_type = 'course'
  and module.is_active;

do $content_review_audio_quality_training_contract$
begin
  if (
    select count(*)
    from content_factory.training_modules module
    where module.code = 'video_quality'
      and module.module_type = 'course'
      and module.is_active
      and jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "full_video_qa" && @.body like_regex "локально измеряет" && @.body like_regex "не расшифровывают слова")'
      )
      and jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*] ? (@.id == "course_check_video_quality_succeeded_status" && @.prompt like_regex "97% тишины")'
      )
      and module.content
        #>> '{knowledge_remediation,course_check_video_quality_succeeded_status,tip}'
          like '%точные слова%'
  ) <> 1 then
    raise exception 'content review audio quality training contract failed';
  end if;

  if not exists (
    select 1
    from content_factory.training_questions question
    where question.code = 'course_check_video_quality_succeeded_status'
      and question.prompt like '%97% тишины%'
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = 'reject_with_timestamps'
          and option.item ->> 'label' like '%Не принимать%'
      )
  ) then
    raise exception 'content review audio assessment contract failed';
  end if;
end;
$content_review_audio_quality_training_contract$;

commit;

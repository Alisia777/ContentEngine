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
              'body', 'Откройте конкретный результат в полном размере. Для видео портал сохраняет до пяти контрольных кадров, локально сканирует 12–24 точки таймлайна и измеряет дорожку. Если в форме явно подтверждено законное основание передачи внешнему AI, есть точная реплика, аудиодорожка декодируется, а MP4 не больше 25 МБ и 90 секунд, сервер один раз отправляет исходник в OpenAI Transcriptions. Полная расшифровка не сохраняется: в закрытом результате остаются короткий фрагмент, хеш, количество слов и детерминированные метрики сходства со сценарием. Низкое сходство означает обязательную ручную проверку, а не автоматическое юридическое заключение. Всегда прослушайте точный MP4 целиком: ASR может ошибиться, не подтверждает музыку, интонацию, права и смысл обещаний.',
              'takeaway', 'Автоматическая сверка речи уменьшает ручную работу, но явное разрешение, точный сценарий и полное прослушивание конкретного MP4 остаются обязательными.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Когда запускается сверка речи',
                'question', 'Можно ли передать MP4 и принять результат автоматически?',
                'branches', jsonb_build_array(
                  jsonb_build_object(
                    'condition', 'Нет явного подтверждения или точного сценария',
                    'action', 'MP4 не отправляется; речь полностью сверяет человек',
                    'tone', 'warning'
                  ),
                  jsonb_build_object(
                    'condition', 'Есть подтверждение, сценарий, пригодный звук и файл в лимите',
                    'action', 'Один fenced-запрос расшифровывает речь и считает сходство без сохранения полной расшифровки',
                    'tone', 'neutral'
                  ),
                  jsonb_build_object(
                    'condition', 'Сходство высокое или низкое',
                    'action', 'В обоих случаях человек прослушивает точный файл и принимает неизменяемое решение',
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
          when 'control_frames' then 'Проверить кадры, метрики и ASR-сходство, затем полностью прослушать точный MP4 и сверить сценарий'
          when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
          when 'memory_compare' then 'Принять ролик по 92% сходства, не слушая его, потому что ASR уже подтвердил смысл'
          when 'full_playback' then 'Полностью воспроизвести точный файл со звуком, проверить слова, музыку, субтитры и товар'
          when 'skip_watch' then 'Считать короткий фрагмент расшифровки полной записью речи и не проверять остальной звук'
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
  prompt = 'Портал показал 92% сходства распознанной речи со сценарием и чистые технические метрики. Какие проверки всё равно обязательны перед решением?',
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
                'prompt', 'Портал показал 92% сходства распознанной речи со сценарием и чистые технические метрики. Какие проверки всё равно обязательны перед решением?',
                'rationale_prompt', 'Объясните, почему ASR-сходство уменьшает ручную работу, но не доказывает музыку, интонацию, юридический смысл и качество всего MP4.',
                'options',
                (
                  select jsonb_agg(
                    option.item || jsonb_build_object(
                      'label',
                      case option.item ->> 'value'
                        when 'control_frames' then 'Проверить кадры, метрики и ASR-сходство, затем полностью прослушать точный MP4 и сверить сценарий'
                        when 'mobile_check' then 'Проверить 9:16, безопасные зоны, текст и товар на мобильном размере'
                        when 'memory_compare' then 'Принять ролик по 92% сходства, не слушая его, потому что ASR уже подтвердил смысл'
                        when 'full_playback' then 'Полностью воспроизвести точный файл со звуком, проверить слова, музыку, субтитры и товар'
                        when 'skip_watch' then 'Считать короткий фрагмент расшифровки полной записью речи и не проверять остальной звук'
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
    to_jsonb('ASR запускается только с явным разрешением и в лимите 25 МБ / 90 секунд. Даже 92% сходства не отменяют полного прослушивания точного MP4 человеком.'::text),
    true
  ),
  updated_at = now()
where module.code = 'video_quality'
  and module.module_type = 'course'
  and module.is_active;

do $content_review_speech_training_contract$
begin
  if (
    select count(*)
    from content_factory.training_modules module
    where module.code = 'video_quality'
      and module.module_type = 'course'
      and module.is_active
      and jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "full_video_qa" && @.body like_regex "OpenAI Transcriptions" && @.body like_regex "25 МБ" && @.body like_regex "Полная расшифровка не сохраняется")'
      )
      and jsonb_path_exists(
        module.content,
        '$.knowledge_check.questions[*] ? (@.id == "course_check_video_quality_full_qa" && @.prompt like_regex "92% сходства")'
      )
      and module.content
        #>> '{knowledge_remediation,course_check_video_quality_full_qa,tip}'
          like '%полного прослушивания%'
  ) <> 1 then
    raise exception 'content review speech training contract failed';
  end if;

  if not exists (
    select 1
    from content_factory.training_questions question
    where question.code = 'course_check_video_quality_full_qa'
      and question.prompt like '%92% сходства%'
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' = 'full_playback'
          and option.item ->> 'label' like '%Полностью воспроизвести%'
      )
  ) then
    raise exception 'content review speech assessment contract failed';
  end if;
end;
$content_review_speech_training_contract$;

commit;

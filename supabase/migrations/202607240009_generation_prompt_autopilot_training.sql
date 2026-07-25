begin;

update content_factory.training_modules module
set
  content = replace(
    module.content::text,
    'Создание видео',
    'Создание контента'
  )::jsonb || jsonb_build_object(
    'lessons',
    (
      select jsonb_agg(
        case
          when lesson.item ->> 'id' = 'interface_map' then
            lesson.item || jsonb_build_object(
              'title', 'Где находится создание контента',
              'body', 'Левая навигация отражает рабочий цикл. «Создание контента» собирает безопасное авто-ТЗ и создаёт фото или видео, «Материалы» хранят точные исходники, «Проверка» отделяет готовый файл от одобренного, «Задачи» фиксируют ответственность, «Публикации» принимают ссылку на готовый пост, а «Результаты» — проверяемые снимки показателей.',
              'takeaway', 'Фото и видео проходят один маршрут: точный исходник → авто-ТЗ → один запуск → QA → задача → публикация → метрики.',
              'visual', jsonb_build_object(
                'type', 'annotated_ui',
                'title', 'Рабочие зоны портала',
                'panels', jsonb_build_array(
                  jsonb_build_object('area', 'Материалы', 'label', 'Сверить товар', 'detail', 'Точные исходники, артикул и подтверждённые права'),
                  jsonb_build_object('area', 'Создание контента', 'label', 'Создать', 'detail', 'Режим, авто-ТЗ, назначение и подтверждение одного расхода'),
                  jsonb_build_object('area', 'Проверка', 'label', 'Принять файл', 'detail', 'Товар, упаковка, качество, речь и claims'),
                  jsonb_build_object('area', 'Задачи', 'label', 'Передать', 'detail', 'Исполнитель, статус и доказательство выполнения'),
                  jsonb_build_object('area', 'Публикации', 'label', 'Опубликовать', 'detail', 'Назначенный аккаунт, карточка и публичная ссылка'),
                  jsonb_build_object('area', 'Результаты', 'label', 'Измерить', 'detail', 'Источник, время снимка, просмотры, переходы и заказы')
                )
              )
            )
          when lesson.item ->> 'id' = 'generation_modes' then
            lesson.item || jsonb_build_object(
              'title', 'Фото, видео и безопасное авто-ТЗ',
              'body', 'В разделе «Создание контента» есть тестовый режим без списаний и три платных режима: квадратное фото 2K примерно за $0.04, анимация товара на 5 секунд без речи примерно за $0.25 и UGC-видео на 8 секунд с голосом примерно за $2.32. После выбора проверенного исходника портал сам фиксирует артикул и название, затем собирает безопасное ТЗ для выбранного режима. Человеку остаётся проверить площадку, аккаунт или карточку публикации, прочитать итоговую цену и отдельно подтвердить один запуск. Статус «Готово» означает наличие файла, но не его одобрение.',
              'duration_minutes', 5,
              'takeaway', 'Выберите точный исходник и режим, проверьте готовое авто-ТЗ и цену; подтверждение расхода разрешает один файл, а публикацию — только последующий QA.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Как выбрать режим',
                'question', 'Какой один результат нужен из проверенного исходника?',
                'branches', jsonb_build_array(
                  jsonb_build_object(
                    'condition', 'Нужна карточка или packshot',
                    'action', 'Фото 2K · квадрат · один файл · авто-ТЗ фиксирует Figure 1, упаковку и запрет на выдуманные детали · ≈ $0.04',
                    'tone', 'success'
                  ),
                  jsonb_build_object(
                    'condition', 'Нужно короткое движение товара',
                    'action', 'Gen-4 · 5 секунд · без речи и новых надписей · одно движение камеры · ≈ $0.25',
                    'tone', 'success'
                  ),
                  jsonb_build_object(
                    'condition', 'Нужен блогер и голос',
                    'action', 'Seedance · 8 секунд · одна короткая дословная реплика · ≈ $2.32',
                    'tone', 'success'
                  ),
                  jsonb_build_object(
                    'condition', 'Товар, права, бюджет или цена не подтверждены',
                    'action', 'Не запускать платный режим; использовать тестовый вариант или передать решение руководителю',
                    'tone', 'danger'
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
    )
  ),
  updated_at = now()
where module.code = 'factory_basics'
  and module.module_type = 'course'
  and module.is_active;

update content_factory.training_modules module
set
  title = 'Как создать и проверить фото и видео',
  description = 'Пошаговая работа с точным товаром, безопасным авто-ТЗ и платным запуском: от исходника до воспроизводимой проверки готового фото или видео.',
  content = module.content || jsonb_build_object(
    'block_label', 'Блок 2 · Как создать и проверить контент',
    'outcome', 'Вы умеете выбрать точный исходник, получить безопасное авто-ТЗ для фото или видео и принять либо отклонить конкретный файл по воспроизводимым признакам.',
    'completion_checklist', jsonb_build_array(
      'Могу выбрать проверенный исходник с точным артикулом и подтверждёнными правами',
      'Понимаю различия фото 2K, видео 5 секунд без речи и UGC-видео 8 секунд с голосом',
      'Умею восстановить авто-ТЗ и не удалять защиту упаковки и claims',
      'Понимаю цену и отдельное подтверждение одного платного запуска',
      'Могу принять или отклонить конкретное фото или видео по товару, качеству и безопасности'
    ),
    'lessons',
    (
      select jsonb_agg(
        case
          when lesson.item ->> 'id' = 'generation_form' then
            lesson.item || jsonb_build_object(
              'title', 'Как запустить фото или видео с авто-ТЗ',
              'body', 'Сначала выберите режим и одно проверенное фото товара. Портал зафиксирует артикул и название и сам соберёт безопасное ТЗ: квадратный packshot 2K, одно движение камеры на 5 секунд без речи или UGC на 8 секунд с короткой дословной репликой. ТЗ можно уточнить, но удаление точного товара, защиты упаковки или запрета на новые claims остановит платный запуск. Затем укажите площадку и точный аккаунт или карточку, проверьте кампанию и цену и подтвердите ровно один расход.',
              'takeaway', 'Минимальный ручной маршрут: режим → проверенный исходник → площадка → адрес публикации → проверка авто-ТЗ и цены → одно подтверждение.',
              'visual', jsonb_build_object(
                'type', 'annotated_ui',
                'title', 'Поля сверху вниз',
                'panels', jsonb_build_array(
                  jsonb_build_object('area', 'Режим', 'label', 'Фото 2K, 5 секунд или 8 секунд', 'detail', 'Определяет формат авто-ТЗ и ориентировочную цену'),
                  jsonb_build_object('area', 'Товар', 'label', 'Проверенный исходник', 'detail', 'Артикул и название подставляются и блокируются автоматически'),
                  jsonb_build_object('area', 'Авто-ТЗ', 'label', 'Готово и редактируемо', 'detail', 'Кнопка восстановления возвращает защиту товара, упаковки и claims'),
                  jsonb_build_object('area', 'Назначение', 'label', 'Площадка и точный адрес', 'detail', 'Укажите, где будет использован конкретный файл'),
                  jsonb_build_object('area', 'Расход', 'label', 'Кампания, цена и подтверждение', 'detail', 'Подтверждение действует только на один запуск')
                )
              )
            )
          when lesson.item ->> 'id' = 'full_video_qa' then
            lesson.item || jsonb_build_object(
              'title', 'Как принять готовое фото или видео',
              'body', 'Откройте конкретный результат в полном размере. Для фото сверьте упаковку, логотип, весь видимый текст, геометрию, цвет, лишние объекты и поля кадра. Для видео просмотрите файл от первого до последнего кадра со звуком и проверьте товар, руки и лицо, речь, титры, длительность и опасные обещания. Решение относится только к этому файлу: технический статус succeeded или «Готово» не означает одобрение.',
              'takeaway', 'Провайдер подтверждает создание файла, а человек подтверждает точный товар, визуальное качество, права и безопасность.',
              'visual', jsonb_build_object(
                'type', 'decision',
                'title', 'Решение после проверки результата',
                'question', 'Есть ли хотя бы одно существенное несоответствие?',
                'branches', jsonb_build_array(
                  jsonb_build_object('condition', 'Товар и упаковка точны, файл чистый, требования соблюдены', 'action', 'Одобрить конкретный файл и передать в назначенную задачу', 'tone', 'success'),
                  jsonb_build_object('condition', 'Подмена товара, искажённая этикетка, лишние детали или опасное обещание', 'action', 'Отклонить файл и описать точную причину исправления или решения о повторе', 'tone', 'danger'),
                  jsonb_build_object('condition', 'Фото не открыто полностью или видео не просмотрено целиком со звуком', 'action', 'Не принимать решение до полной проверки', 'tone', 'warning')
                )
              )
            )
          else lesson.item
        end
        order by lesson.ordinality
      )
      from jsonb_array_elements(module.content -> 'lessons')
        with ordinality as lesson(item, ordinality)
    )
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
          when 'verbal_ok' then 'Считать слово «срочно» подтверждением и оставить вручную изменённое ТЗ'
          when 'launch_anyway' then 'Запустить фото после удаления защиты этикетки: исходник всё равно приложен к заданию'
          when 'stop_correct_confirm' then 'Восстановить безопасное авто-ТЗ, снова проверить точный товар и подтвердить один packshot 2K примерно за $0.04'
          when 'change_after' then 'Сначала отправить фото провайдеру, а защиту упаковки и цену согласовать после появления результата'
          when 'all' then 'Восстановить безопасное авто-ТЗ, снова проверить точный товар и подтвердить один packshot 2K примерно за $0.04'
          when 'speed' then 'Запустить фото после удаления защиты этикетки: активная кнопка важнее защитного текста'
          when 'chat' then 'Считать слово «срочно» в чате подтверждением изменённого ТЗ и показанной цены'
          else option.item ->> 'label'
        end
      )
      order by option.ordinality
    ) as options
  from content_factory.training_questions question
  cross join lateral jsonb_array_elements(question.options)
    with ordinality as option(item, ordinality)
  where question.code = 'course_check_factory_basics_paid_start'
  group by question.code
)
update content_factory.training_questions question
set
  prompt = 'Для карточки нужен один квадратный packshot 2K. После выбора проверенного фото портал зафиксировал товар и собрал авто-ТЗ примерно за $0.04, но оператор вручную удалил защиту этикетки. Руководитель написал «срочно». Какое одно решение рабочее?',
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
            when question.item ->> 'id' = 'course_check_factory_basics_paid_start' then
              question.item || jsonb_build_object(
                'prompt', 'Для карточки нужен один квадратный packshot 2K. После выбора проверенного фото портал зафиксировал товар и собрал авто-ТЗ примерно за $0.04, но оператор вручную удалил защиту этикетки. Руководитель написал «срочно». Какое одно решение рабочее?',
                'options',
                (
                  select jsonb_agg(
                    option.item || jsonb_build_object(
                      'label',
                      case option.item ->> 'value'
                        when 'verbal_ok' then 'Считать слово «срочно» подтверждением и оставить вручную изменённое ТЗ'
                        when 'launch_anyway' then 'Запустить фото после удаления защиты этикетки: исходник всё равно приложен к заданию'
                        when 'stop_correct_confirm' then 'Восстановить безопасное авто-ТЗ, снова проверить точный товар и подтвердить один packshot 2K примерно за $0.04'
                        when 'change_after' then 'Сначала отправить фото провайдеру, а защиту упаковки и цену согласовать после появления результата'
                        when 'all' then 'Восстановить безопасное авто-ТЗ, снова проверить точный товар и подтвердить один packshot 2K примерно за $0.04'
                        when 'speed' then 'Запустить фото после удаления защиты этикетки: активная кнопка важнее защитного текста'
                        when 'chat' then 'Считать слово «срочно» в чате подтверждением изменённого ТЗ и показанной цены'
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
        from jsonb_array_elements(module.content #> '{knowledge_check,questions}')
          with ordinality as question(item, ordinality)
      ),
      false
    ),
    '{knowledge_remediation,course_check_factory_basics_paid_start,tip}',
    to_jsonb('Повторите безопасный запуск: проверенный исходник, восстановленное авто-ТЗ, точный режим, цена и отдельное подтверждение до списания.'::text),
    true
  ),
  updated_at = now()
where module.code = 'factory_basics'
  and module.module_type = 'course'
  and module.is_active;

do $generation_prompt_autopilot_training_contract$
declare
  invalid_count integer;
begin
  select count(*) into invalid_count
  from content_factory.training_modules module
  where (
    module.code = 'factory_basics'
    and (
      not jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "generation_modes" && @.body like_regex "безопасное ТЗ")'
      )
      or module.content #>> '{knowledge_check,questions}' like '%148 ₽%'
      or module.content #>> '{knowledge_check,questions}' not like '%$0.04%'
    )
  ) or (
    module.code = 'video_quality'
    and (
      module.title <> 'Как создать и проверить фото и видео'
      or not jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "generation_form" && @.body like_regex "безопасное ТЗ")'
      )
      or not jsonb_path_exists(
        module.content,
        '$.lessons[*] ? (@.id == "full_video_qa" && @.body like_regex "Для фото")'
      )
    )
  );

  if invalid_count <> 0 or (
    select count(*)
    from content_factory.training_modules module
    where module.code = any(array['factory_basics', 'video_quality'])
      and module.module_type = 'course'
      and module.is_active
  ) <> 2 then
    raise exception 'generation prompt autopilot training contract failed';
  end if;

  if not exists (
    select 1
    from content_factory.training_questions question
    where question.code = 'course_check_factory_basics_paid_start'
      and question.prompt like '%$0.04%'
      and question.prompt not like '%148 ₽%'
      and exists (
        select 1
        from jsonb_array_elements(question.options) option(item)
        where option.item ->> 'value' in ('stop_correct_confirm', 'all')
          and option.item ->> 'label' like '%авто-ТЗ%'
      )
  ) then
    raise exception 'generation prompt autopilot assessment contract failed';
  end if;
end;
$generation_prompt_autopilot_training_contract$;

commit;

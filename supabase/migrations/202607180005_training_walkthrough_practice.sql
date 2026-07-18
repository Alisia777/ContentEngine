begin;

-- Add one decision practice to every existing interactive walkthrough.  The
-- browser renders these exercises locally, but the authoritative content stays
-- in Supabase together with the lesson, checklist and transcript.
with practice_catalog(
  module_code,
  walkthrough_id,
  audience,
  audience_label,
  mission,
  deliverable,
  practice
) as (
  values
    (
      'factory_basics',
      'first_login_route',
      'all',
      'Всем участникам',
      'Пройдите первый вход, не передавая приглашение, пароль или код подтверждения другому человеку.',
      'Личный вход активирован, а на экране открыт первый рекомендованный учебный блок.',
      $practice$
      {
        "prompt": "Коллега просит переслать вашу ссылку входа. Что делать?",
        "options": [
          {
            "id": "personal_activation",
            "label": "Не пересылать. Войти самому и создать свой пароль",
            "correct": true,
            "feedback": "Верно. Ссылка, пароль и коды принадлежат только вам."
          },
          {
            "id": "forward_invite",
            "label": "Переслать ссылку, а потом сменить пароль",
            "correct": false,
            "feedback": "Нет. По ссылке могут войти от вашего имени."
          },
          {
            "id": "second_account",
            "label": "Создать второй аккаунт на другой почте",
            "correct": false,
            "feedback": "Нет. Попросите руководителя проверить вашу рабочую почту."
          }
        ],
        "success_message": "Готово: вы вошли сами и не передали доступ другому человеку."
      }
      $practice$::jsonb
    ),
    (
      'factory_basics',
      'material_to_review',
      'ai',
      'Оператору ИИ',
      'Проведите один товар через Материалы, создание видео и полную проверку без дублей платного запуска.',
      'Один точный товар связан с одним запуском и одним зафиксированным решением по готовому файлу.',
      $practice$
      {
        "prompt": "Платный ролик уже создаётся. Кнопка снова активна. Что делать?",
        "options": [
          {
            "id": "track_existing_job",
            "label": "Проверить текущий запуск и не создавать дубль",
            "correct": true,
            "feedback": "Верно. Сначала дождитесь результата или подтверждённой ошибки."
          },
          {
            "id": "click_again",
            "label": "Нажать ещё раз и потом удалить лишний ролик",
            "correct": false,
            "feedback": "Нет. Второй запуск может списать деньги ещё раз."
          },
          {
            "id": "swap_source",
            "label": "Запустить похожий товар, пока ждём",
            "correct": false,
            "feedback": "Нет. Похожий товар — это уже другая задача."
          }
        ],
        "success_message": "Верно: один товар, один запуск, без лишнего списания."
      }
      $practice$::jsonb
    ),
    (
      'video_quality',
      'phone_shooting_916',
      'creator',
      'Реальному креатору',
      'Снимите короткую техническую пробу до основного дубля и устраните проблемы в самом исходнике.',
      'Вертикальная проба 9:16 с читаемой этикеткой, устойчивым кадром и разборчивым звуком.',
      $practice$
      {
        "prompt": "На пробе темно, этикетка бликует, а голос не слышно. Что делать?",
        "options": [
          {
            "id": "fix_source_setup",
            "label": "Исправить свет и звук, закрепить телефон, снять новую пробу",
            "correct": true,
            "feedback": "Верно. Исправьте проблемы до основного дубля."
          },
          {
            "id": "repair_everything_later",
            "label": "Снять как есть: всё исправит монтаж",
            "correct": false,
            "feedback": "Нет. Потерянные детали и плохой звук могут не восстановиться."
          },
          {
            "id": "digital_zoom_flash",
            "label": "Включить сильный зум и прямую вспышку",
            "correct": false,
            "feedback": "Нет. Зум портит детали, а вспышка усиливает блик."
          }
        ],
        "success_message": "Проба готова: лицо и товар видны, голос слышен."
      }
      $practice$::jsonb
    ),
    (
      'video_quality',
      'eight_second_quality',
      'ai',
      'Оператору ИИ',
      'Посмотрите восьмисекундный ролик полностью и примите решение по конкретному файлу, а не по статусу провайдера.',
      'Решение «одобрить» или «на доработку» с одной точной и воспроизводимой причиной.',
      $practice$
      {
        "prompt": "В конце ролика плывёт этикетка и обрывается речь. Что делать?",
        "options": [
          {
            "id": "reject_exact_file",
            "label": "Вернуть ролик и указать оба дефекта",
            "correct": true,
            "feedback": "Верно. Искажённый товар и обрыв речи нельзя одобрять."
          },
          {
            "id": "approve_provider_success",
            "label": "Одобрить: генерация завершилась успешно",
            "correct": false,
            "feedback": "Нет. Статус говорит только о том, что файл создан."
          },
          {
            "id": "hide_last_frame",
            "label": "Скрыть проблему другой обложкой",
            "correct": false,
            "feedback": "Нет. Обложка не исправляет само видео."
          }
        ],
        "success_message": "Проверка готова: ролик возвращён с понятной причиной."
      }
      $practice$::jsonb
    ),
    (
      'publishing_funnel',
      'publish_to_assigned_network',
      'publisher',
      'Публикатору',
      'Разместите одобренный файл только в назначенной сети и верните проверяемую ссылку на сам ролик.',
      'Публичный final URL назначенного Reel, Short или VK Клипа, проверенный после публикации.',
      $practice$
      {
        "prompt": "В задаче указан YouTube Shorts. Где публиковать ролик?",
        "options": [
          {
            "id": "assigned_short_url",
            "label": "Только в назначенном YouTube-канале",
            "correct": true,
            "feedback": "Верно. Для Reels и VK Клипов правило такое же: публикуйте только там, где указано в задаче."
          },
          {
            "id": "publish_everywhere",
            "label": "Сразу в YouTube, Instagram и VK",
            "correct": false,
            "feedback": "Нет. Доступ к аккаунту ещё не означает, что туда нужно публиковать."
          },
          {
            "id": "channel_home_url",
            "label": "В YouTube, но сохранить ссылку только на канал",
            "correct": false,
            "feedback": "Нет. Нужна ссылка на сам Short, а не на весь канал."
          }
        ],
        "success_message": "Готово: ролик опубликован в нужной сети, ссылка ведёт прямо на него."
      }
      $practice$::jsonb
    ),
    (
      'publishing_funnel',
      'advertising_stop_decision',
      'publisher',
      'Публикатору',
      'До публикации распознайте признаки возможной рекламы и передайте сомнительный материал ответственному сотруднику.',
      'Зафиксированное решение по режиму размещения и обязательным реквизитам либо остановленная публикация.',
      $practice$
      {
        "prompt": "Бренд дал товар и обязательный текст. Решения по рекламе ещё нет. Что делать?",
        "options": [
          {
            "id": "stop_and_classify",
            "label": "Не публиковать и передать задачу ответственному",
            "correct": true,
            "feedback": "Верно. Ответственный проверит условия и скажет, как оформить публикацию."
          },
          {
            "id": "remove_cta_to_hide",
            "label": "Убрать призыв и публиковать без проверки",
            "correct": false,
            "feedback": "Нет. Удаление одной фразы не отменяет остальные условия."
          },
          {
            "id": "call_personal_opinion",
            "label": "Назвать это личным мнением и публиковать",
            "correct": false,
            "feedback": "Нет. Бесплатный товар тоже важен при проверке."
          }
        ],
        "success_message": "Верно: сомнительная публикация остановлена до решения ответственного."
      }
      $practice$::jsonb
    ),
    (
      'security_wb',
      'substitute_article_match',
      'all',
      'Всем участникам',
      'Проверьте подменный артикул по свойствам точного товара и остановите задачу при любом существенном расхождении.',
      'Подтверждённая связь двух артикулов одного товара либо запрос руководителю с найденным отличием.',
      $practice$
      {
        "prompt": "В задаче 30 мл, а у подменного артикула 50 мл. Это тот же товар?",
        "options": [
          {
            "id": "stop_volume_mismatch",
            "label": "Нет. Остановиться и сообщить о разном объёме",
            "correct": true,
            "feedback": "Верно. Другой объём — это другой вариант товара."
          },
          {
            "id": "accept_similar_photo",
            "label": "Да, если фото и бренд похожи",
            "correct": false,
            "feedback": "Нет. Нужно сверять ещё объём, вариант, состав и упаковку."
          },
          {
            "id": "edit_volume_in_copy",
            "label": "Да, если написать в ролике «30 мл»",
            "correct": false,
            "feedback": "Нет. Текст не меняет фактический товар."
          }
        ],
        "success_message": "Верно: несовпадающий подменник не принят."
      }
      $practice$::jsonb
    ),
    (
      'security_wb',
      'payout_status_route',
      'all',
      'Всем участникам',
      'Проследите начисление от суммы в задаче до подтверждённого внешнего перевода без преждевременного статуса.',
      'Сверенная сумма, статус конкретного начисления и подтверждение финального перевода.',
      $practice$
      {
        "prompt": "Стоит статус «Начислено», но «Выплачено» нет. Деньги уже переведены?",
        "options": [
          {
            "id": "accrued_not_paid",
            "label": "Нет. Сумма начислена, но перевод ещё не подтверждён",
            "correct": true,
            "feedback": "Верно. Ждите статус «Выплачено» и подтверждение операции."
          },
          {
            "id": "mark_paid_now",
            "label": "Да. Если сумма видна, перевод уже выполнен",
            "correct": false,
            "feedback": "Нет. Начисление ещё не равно переводу."
          },
          {
            "id": "request_payment_password",
            "label": "Нужно попросить пароль от платёжного кабинета",
            "correct": false,
            "feedback": "Нет. Платёжные пароли нельзя передавать."
          }
        ],
        "success_message": "Верно: начисление и реальный перевод — разные этапы."
      }
      $practice$::jsonb
    )
),
patched_modules as (
  select
    module.id,
    jsonb_agg(
      case
        when catalog.walkthrough_id is null then walkthrough.item
        else walkthrough.item || jsonb_build_object(
          'audience', catalog.audience,
          'audience_label', catalog.audience_label,
          'mission', catalog.mission,
          'deliverable', catalog.deliverable,
          'practice', catalog.practice
        )
      end
      order by walkthrough.ordinality
    ) as walkthroughs,
    count(catalog.walkthrough_id) as patched_count
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content -> 'interactive_walkthroughs'
  ) with ordinality as walkthrough(item, ordinality)
  left join practice_catalog catalog
    on catalog.module_code = module.code
   and catalog.walkthrough_id = walkthrough.item ->> 'id'
  where module.module_type = 'course'
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
  group by module.id
)
update content_factory.training_modules module
set
  content = jsonb_set(
    module.content,
    '{interactive_walkthroughs}',
    patched.walkthroughs,
    false
  ),
  updated_at = now()
from patched_modules patched
where module.id = patched.id
  and patched.patched_count > 0;

do $training_walkthrough_practice_contract$
declare
  walkthrough_count integer;
  malformed_walkthroughs integer;
  missing_catalog_rows integer;
begin
  select count(*)
  into walkthrough_count
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content -> 'interactive_walkthroughs'
  ) walkthrough
  where module.module_type = 'course'
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ]);

  if walkthrough_count <> 8 then
    raise exception 'training walkthrough practice expected 8 walkthroughs, got %', walkthrough_count;
  end if;

  select count(*)
  into malformed_walkthroughs
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content -> 'interactive_walkthroughs'
  ) walkthrough
  where module.module_type = 'course'
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
    and (
      coalesce(walkthrough ->> 'mission', '') = ''
      or coalesce(walkthrough ->> 'audience', '') not in ('creator', 'ai', 'publisher', 'all')
      or coalesce(walkthrough ->> 'audience_label', '') = ''
      or coalesce(walkthrough ->> 'deliverable', '') = ''
      or jsonb_typeof(walkthrough -> 'practice') is distinct from 'object'
      or coalesce(walkthrough #>> '{practice,prompt}', '') = ''
      or coalesce(walkthrough #>> '{practice,success_message}', '') = ''
      or jsonb_typeof(walkthrough #> '{practice,options}') is distinct from 'array'
      or jsonb_array_length(coalesce(walkthrough #> '{practice,options}', '[]'::jsonb)) <> 3
      or (
        select count(*)
        from jsonb_array_elements(
          coalesce(walkthrough #> '{practice,options}', '[]'::jsonb)
        ) option
        where option ->> 'correct' = 'true'
      ) <> 1
      or exists (
        select 1
        from jsonb_array_elements(
          coalesce(walkthrough #> '{practice,options}', '[]'::jsonb)
        ) option
        where coalesce(option ->> 'id', '') !~ '^[a-z0-9_]{3,80}$'
          or coalesce(option ->> 'label', '') = ''
          or jsonb_typeof(option -> 'correct') is distinct from 'boolean'
          or coalesce(option ->> 'feedback', '') = ''
      )
    );

  if malformed_walkthroughs <> 0 then
    raise exception 'training walkthrough practice contains % malformed walkthroughs', malformed_walkthroughs;
  end if;

  with expected(module_code, walkthrough_id) as (
    values
      ('factory_basics', 'first_login_route'),
      ('factory_basics', 'material_to_review'),
      ('video_quality', 'phone_shooting_916'),
      ('video_quality', 'eight_second_quality'),
      ('publishing_funnel', 'publish_to_assigned_network'),
      ('publishing_funnel', 'advertising_stop_decision'),
      ('security_wb', 'substitute_article_match'),
      ('security_wb', 'payout_status_route')
  )
  select count(*)
  into missing_catalog_rows
  from expected
  where not exists (
    select 1
    from content_factory.training_modules module
    cross join lateral jsonb_array_elements(
      module.content -> 'interactive_walkthroughs'
    ) walkthrough
    where module.code = expected.module_code
      and walkthrough ->> 'id' = expected.walkthrough_id
      and jsonb_typeof(walkthrough -> 'practice') = 'object'
  );

  if missing_catalog_rows <> 0 then
    raise exception 'training walkthrough practice is missing % catalog rows', missing_catalog_rows;
  end if;
end;
$training_walkthrough_practice_contract$;

commit;

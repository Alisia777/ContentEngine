begin;

-- Curriculum v4 makes practical walkthrough completion an authoritative part
-- of course mastery.  The browser can show XP and coaching, but certification
-- is granted only after both the private knowledge check and the practices
-- named here have been completed for the current member and organization.
with mastery_catalog(module_code, mastery, knowledge_remediation) as (
  values
    (
      'factory_basics',
      jsonb_build_object(
        'required_walkthrough_ids', jsonb_build_array('first_login_route'),
        'lesson_requirement', 'recommended',
        'xp', jsonb_build_object(
          'lessons', 35,
          'practice', 30,
          'test', 25,
          'confirmation', 10
        )
      ),
      $remediation$
      {
        "course_check_factory_basics_portal_registration": {
          "lesson_id": "first_access_route",
          "tip": "Повторите безопасный первый вход: рабочую почту добавляет руководитель, а пароль всегда личный."
        },
        "course_check_factory_basics_source_location": {
          "lesson_id": "interface_map",
          "tip": "Откройте карту интерфейса и найдите раздел «Материалы», где начинается работа с точными исходниками."
        },
        "course_check_factory_basics_paid_start": {
          "lesson_id": "generation_modes",
          "tip": "Перед платным запуском ещё раз сверьте товар, исходник, сценарий, режим, длительность и показанную стоимость."
        }
      }
      $remediation$::jsonb
    ),
    (
      'video_quality',
      jsonb_build_object(
        'required_walkthrough_ids', jsonb_build_array('eight_second_quality'),
        'lesson_requirement', 'recommended',
        'xp', jsonb_build_object(
          'lessons', 35,
          'practice', 30,
          'test', 25,
          'confirmation', 10
        )
      ),
      $remediation$
      {
        "course_check_video_quality_phone_setup": {
          "lesson_id": "shoot_vertical_source",
          "tip": "Вернитесь к настройке телефона: чистая линза, 9:16, мягкий свет, устойчивый кадр и тест звука."
        },
        "course_check_video_quality_eight_seconds": {
          "lesson_id": "eight_second_storyboard",
          "tip": "Разберите одну короткую историю: захват внимания, действие с товаром и ясное завершение."
        },
        "course_check_video_quality_succeeded_status": {
          "lesson_id": "full_video_qa",
          "tip": "Статус подтверждает только создание файла; полностью просмотрите ролик и отдельно примите качество."
        }
      }
      $remediation$::jsonb
    ),
    (
      'publishing_funnel',
      jsonb_build_object(
        'required_walkthrough_ids', jsonb_build_array('advertising_stop_decision'),
        'lesson_requirement', 'recommended',
        'xp', jsonb_build_object(
          'lessons', 35,
          'practice', 30,
          'test', 25,
          'confirmation', 10
        )
      ),
      $remediation$
      {
        "course_check_publishing_funnel_social_access": {
          "lesson_id": "social_account_access",
          "tip": "Нет роли в точном аккаунте — остановитесь и запросите доступ у руководителя; общий пароль не используйте."
        },
        "course_check_publishing_funnel_final_url": {
          "lesson_id": "three_urls",
          "tip": "После публикации верните публичную ссылку именно на Reel, Short или VK Клип, а не на профиль или товар."
        },
        "course_check_publishing_funnel_vk_finish": {
          "lesson_id": "vk_clips_step_by_step",
          "tip": "Откройте VK Клип как зритель, проверьте доступность, сохраните ссылку на пост и время замера."
        },
        "course_check_publishing_funnel_safe_new_account": {
          "lesson_id": "new_account_safe_start",
          "tip": "Безопасный старт — правдивый профиль, защита и постепенные реальные действия без ботов, накруток и массфолловинга."
        },
        "course_check_publishing_funnel_advertising_gate": {
          "lesson_id": "advertising_classification_and_labeling",
          "tip": "Если рекламная классификация не зафиксирована, не публикуйте: передайте материал ответственному на проверку."
        }
      }
      $remediation$::jsonb
    ),
    (
      'security_wb',
      jsonb_build_object(
        'required_walkthrough_ids', jsonb_build_array(
          'substitute_article_match',
          'payout_status_route'
        ),
        'lesson_requirement', 'recommended',
        'xp', jsonb_build_object(
          'lessons', 35,
          'practice', 30,
          'test', 25,
          'confirmation', 10
        )
      ),
      $remediation$
      {
        "course_check_security_wb_substitute_article": {
          "lesson_id": "wb_alias_history",
          "tip": "Подменный артикул допустим только для того же точного товара; сверьте объём, вариант, состав и упаковку."
        },
        "course_check_security_wb_payout_amount": {
          "lesson_id": "calculation_and_payout",
          "tip": "Сумма фиксируется руководителем в задаче до работы и складывается только из принятых начисляемых задач."
        },
        "course_check_security_wb_paid_status": {
          "lesson_id": "calculation_and_payout",
          "tip": "Деньги выплачены только после принятия результата, одобрения начисления и подтверждённого внешнего перевода."
        }
      }
      $remediation$::jsonb
    )
)
update content_factory.training_modules module
set content = coalesce(module.content, '{}'::jsonb) || jsonb_build_object(
  'version', 4,
  'mastery', catalog.mastery,
  'knowledge_remediation', catalog.knowledge_remediation
)
from mastery_catalog catalog
where module.code = catalog.module_code
  and module.module_type = 'course'
  and module.is_active;

-- Freeze checklist identity before it is persisted by the browser.  Existing
-- positional IDs are retained deliberately, so already saved local state can
-- be read once and all later copy edits/reordering use explicit object IDs.
update content_factory.training_modules module
set content = jsonb_set(
  module.content,
  '{interactive_walkthroughs}',
  coalesce((
    select jsonb_agg(
      walkthrough.value || jsonb_build_object(
        'checklist',
        coalesce((
          select jsonb_agg(
            case
              when jsonb_typeof(check_item.value) = 'object' then
                check_item.value || jsonb_build_object(
                  'id', coalesce(
                    nullif(check_item.value ->> 'id', ''),
                    walkthrough.value ->> 'id' || '_check_' || check_item.ordinality::text
                  ),
                  'text', coalesce(
                    nullif(check_item.value ->> 'text', ''),
                    nullif(check_item.value ->> 'label', ''),
                    nullif(check_item.value ->> 'title', ''),
                    'Проверка ' || check_item.ordinality::text
                  )
                )
              else jsonb_build_object(
                'id', walkthrough.value ->> 'id' || '_check_' || check_item.ordinality::text,
                'text', coalesce(check_item.value #>> '{}', '')
              )
            end
            order by check_item.ordinality
          )
          from jsonb_array_elements(
            case
              when jsonb_typeof(walkthrough.value -> 'checklist') = 'array'
              then walkthrough.value -> 'checklist'
              else '[]'::jsonb
            end
          ) with ordinality check_item(value, ordinality)
        ), '[]'::jsonb)
      )
      order by walkthrough.ordinality
    )
    from jsonb_array_elements(
      case
        when jsonb_typeof(module.content -> 'interactive_walkthroughs') = 'array'
        then module.content -> 'interactive_walkthroughs'
        else '[]'::jsonb
      end
    ) with ordinality walkthrough(value, ordinality)
  ), '[]'::jsonb),
  true
)
where module.code in (
    'factory_basics', 'video_quality', 'publishing_funnel', 'security_wb'
  )
  and module.module_type = 'course'
  and module.is_active;

-- Fail the migration atomically if the catalog is incomplete or internally
-- inconsistent.  Every JSON traversal below first substitutes an empty value
-- of the expected type so malformed/null metadata cannot crash the validator.
do $training_mastery_v4_contract$
declare
  active_course_count integer;
  malformed_mastery_count integer;
  required_practice_mismatch_count integer;
  missing_remediation_count integer;
  extra_remediation_count integer;
  invalid_remediation_target_count integer;
  malformed_checklist_count integer;
begin
  select count(*)
  into active_course_count
  from content_factory.training_modules module
  where module.module_type = 'course'
    and module.is_active
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ]);

  if active_course_count <> 4 then
    raise exception 'training mastery v4 expected 4 active courses, found %',
      active_course_count;
  end if;

  select count(*)
  into malformed_mastery_count
  from content_factory.training_modules module
  where module.module_type = 'course'
    and module.is_active
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
    and (
      module.content ->> 'version' is distinct from '4'
      or jsonb_typeof(module.content -> 'mastery') is distinct from 'object'
      or coalesce(module.content #>> '{mastery,lesson_requirement}', '')
        not in ('all', 'recommended')
      or jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}')
        is distinct from 'array'
      or jsonb_array_length(
        case
          when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
          then module.content #> '{mastery,required_walkthrough_ids}'
          else '[]'::jsonb
        end
      ) < 1
      or jsonb_typeof(module.content #> '{mastery,xp}') is distinct from 'object'
      or (
        select count(*)
        from jsonb_each(
          case
            when jsonb_typeof(module.content #> '{mastery,xp}') = 'object'
            then module.content #> '{mastery,xp}'
            else '{}'::jsonb
          end
        ) weight
      ) <> 4
      or exists (
        select 1
        from jsonb_each(
          case
            when jsonb_typeof(module.content #> '{mastery,xp}') = 'object'
            then module.content #> '{mastery,xp}'
            else '{}'::jsonb
          end
        ) weight
        where weight.key not in ('lessons', 'practice', 'test', 'confirmation')
          or jsonb_typeof(weight.value) is distinct from 'number'
          or case
               when jsonb_typeof(weight.value) = 'number'
               then (weight.value #>> '{}')::numeric
               else -1
             end < 0
      )
      or (
        select coalesce(sum(
          case
            when jsonb_typeof(weight.value) = 'number'
            then (weight.value #>> '{}')::numeric
            else 0
          end
        ), 0)
        from jsonb_each(
          case
            when jsonb_typeof(module.content #> '{mastery,xp}') = 'object'
            then module.content #> '{mastery,xp}'
            else '{}'::jsonb
          end
        ) weight
      ) <> 100
      or jsonb_typeof(module.content -> 'knowledge_remediation')
        is distinct from 'object'
      or exists (
        select 1
        from jsonb_array_elements(
          case
            when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
            then module.content #> '{mastery,required_walkthrough_ids}'
            else '[]'::jsonb
          end
        ) required_walkthrough(value)
        where jsonb_typeof(required_walkthrough.value) is distinct from 'string'
          or coalesce(required_walkthrough.value #>> '{}', '')
            !~ '^[a-z0-9][a-z0-9_]{2,79}$'
      )
      or (
        select count(*)
        from jsonb_array_elements_text(
          case
            when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
            then module.content #> '{mastery,required_walkthrough_ids}'
            else '[]'::jsonb
          end
        ) required_walkthrough(value)
      ) is distinct from (
        select count(distinct required_walkthrough.value)
        from jsonb_array_elements_text(
          case
            when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
            then module.content #> '{mastery,required_walkthrough_ids}'
            else '[]'::jsonb
          end
        ) required_walkthrough(value)
      )
    );

  if malformed_mastery_count <> 0 then
    raise exception 'training mastery v4 contains % malformed course records',
      malformed_mastery_count;
  end if;

  select count(*)
  into malformed_checklist_count
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    case
      when jsonb_typeof(module.content -> 'interactive_walkthroughs') = 'array'
      then module.content -> 'interactive_walkthroughs'
      else '[]'::jsonb
    end
  ) walkthrough(value)
  cross join lateral jsonb_array_elements(
    case
      when jsonb_typeof(walkthrough.value -> 'checklist') = 'array'
      then walkthrough.value -> 'checklist'
      else '[]'::jsonb
    end
  ) check_item(value)
  where module.module_type = 'course'
    and module.is_active
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
    and (
      jsonb_typeof(check_item.value) is distinct from 'object'
      or coalesce(check_item.value ->> 'id', '')
        !~ '^[a-z0-9][a-z0-9_]{2,79}$'
      or nullif(btrim(coalesce(check_item.value ->> 'text', '')), '') is null
    );

  if malformed_checklist_count <> 0 then
    raise exception 'training mastery v4 contains % malformed checklist entries',
      malformed_checklist_count;
  end if;

  if exists (
    select 1
    from content_factory.training_modules module
    cross join lateral jsonb_array_elements(
      case
        when jsonb_typeof(module.content -> 'interactive_walkthroughs') = 'array'
        then module.content -> 'interactive_walkthroughs'
        else '[]'::jsonb
      end
    ) walkthrough(value)
    cross join lateral jsonb_array_elements(
      case
        when jsonb_typeof(walkthrough.value -> 'checklist') = 'array'
        then walkthrough.value -> 'checklist'
        else '[]'::jsonb
      end
    ) check_item(value)
    where module.module_type = 'course'
      and module.is_active
      and module.code = any(array[
        'factory_basics',
        'video_quality',
        'publishing_funnel',
        'security_wb'
      ])
    group by module.code, walkthrough.value ->> 'id', check_item.value ->> 'id'
    having count(*) > 1
  ) then
    raise exception 'training mastery v4 contains duplicate checklist IDs';
  end if;

  with expected(module_code, walkthrough_id) as (
    values
      ('factory_basics', 'first_login_route'),
      ('video_quality', 'eight_second_quality'),
      ('publishing_funnel', 'advertising_stop_decision'),
      ('security_wb', 'substitute_article_match'),
      ('security_wb', 'payout_status_route')
  ), actual as (
    select module.code as module_code, required_walkthrough.value as walkthrough_id
    from content_factory.training_modules module
    cross join lateral jsonb_array_elements_text(
      case
        when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
        then module.content #> '{mastery,required_walkthrough_ids}'
        else '[]'::jsonb
      end
    ) required_walkthrough(value)
    where module.module_type = 'course'
      and module.is_active
      and module.code = any(array[
        'factory_basics',
        'video_quality',
        'publishing_funnel',
        'security_wb'
      ])
  ), differences as (
    (select * from expected except select * from actual)
    union all
    (select * from actual except select * from expected)
  )
  select count(*) into required_practice_mismatch_count
  from differences;

  if required_practice_mismatch_count <> 0 then
    raise exception 'training mastery v4 has % required-practice catalog mismatches',
      required_practice_mismatch_count;
  end if;

  select count(*)
  into required_practice_mismatch_count
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements_text(
    case
      when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
      then module.content #> '{mastery,required_walkthrough_ids}'
      else '[]'::jsonb
    end
  ) required_walkthrough(value)
  where module.module_type = 'course'
    and module.is_active
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
    and not exists (
      select 1
      from jsonb_array_elements(
        case
          when jsonb_typeof(module.content -> 'interactive_walkthroughs') = 'array'
          then module.content -> 'interactive_walkthroughs'
          else '[]'::jsonb
        end
      ) walkthrough(value)
      where walkthrough.value ->> 'id' = required_walkthrough.value
    );

  if required_practice_mismatch_count <> 0 then
    raise exception 'training mastery v4 references % missing walkthroughs',
      required_practice_mismatch_count;
  end if;

  with expected(module_code, question_code, lesson_id) as (
    values
      ('factory_basics', 'course_check_factory_basics_portal_registration', 'first_access_route'),
      ('factory_basics', 'course_check_factory_basics_source_location', 'interface_map'),
      ('factory_basics', 'course_check_factory_basics_paid_start', 'generation_modes'),
      ('video_quality', 'course_check_video_quality_phone_setup', 'shoot_vertical_source'),
      ('video_quality', 'course_check_video_quality_eight_seconds', 'eight_second_storyboard'),
      ('video_quality', 'course_check_video_quality_succeeded_status', 'full_video_qa'),
      ('publishing_funnel', 'course_check_publishing_funnel_social_access', 'social_account_access'),
      ('publishing_funnel', 'course_check_publishing_funnel_final_url', 'three_urls'),
      ('publishing_funnel', 'course_check_publishing_funnel_vk_finish', 'vk_clips_step_by_step'),
      ('publishing_funnel', 'course_check_publishing_funnel_safe_new_account', 'new_account_safe_start'),
      ('publishing_funnel', 'course_check_publishing_funnel_advertising_gate', 'advertising_classification_and_labeling'),
      ('security_wb', 'course_check_security_wb_substitute_article', 'wb_alias_history'),
      ('security_wb', 'course_check_security_wb_payout_amount', 'calculation_and_payout'),
      ('security_wb', 'course_check_security_wb_paid_status', 'calculation_and_payout')
  )
  select count(*)
  into missing_remediation_count
  from expected
  join content_factory.training_modules module
    on module.code = expected.module_code
   and module.module_type = 'course'
   and module.is_active
  where coalesce(
      module.content #>> array[
        'knowledge_remediation', expected.question_code, 'lesson_id'
      ],
      ''
    ) <> expected.lesson_id
    or coalesce(
      module.content #>> array[
        'knowledge_remediation', expected.question_code, 'tip'
      ],
      ''
    ) = '';

  if missing_remediation_count <> 0 then
    raise exception 'training mastery v4 is missing % remediation mappings',
      missing_remediation_count;
  end if;

  with expected(module_code, question_code) as (
    values
      ('factory_basics', 'course_check_factory_basics_portal_registration'),
      ('factory_basics', 'course_check_factory_basics_source_location'),
      ('factory_basics', 'course_check_factory_basics_paid_start'),
      ('video_quality', 'course_check_video_quality_phone_setup'),
      ('video_quality', 'course_check_video_quality_eight_seconds'),
      ('video_quality', 'course_check_video_quality_succeeded_status'),
      ('publishing_funnel', 'course_check_publishing_funnel_social_access'),
      ('publishing_funnel', 'course_check_publishing_funnel_final_url'),
      ('publishing_funnel', 'course_check_publishing_funnel_vk_finish'),
      ('publishing_funnel', 'course_check_publishing_funnel_safe_new_account'),
      ('publishing_funnel', 'course_check_publishing_funnel_advertising_gate'),
      ('security_wb', 'course_check_security_wb_substitute_article'),
      ('security_wb', 'course_check_security_wb_payout_amount'),
      ('security_wb', 'course_check_security_wb_paid_status')
  )
  select count(*)
  into extra_remediation_count
  from content_factory.training_modules module
  cross join lateral jsonb_each(
    case
      when jsonb_typeof(module.content -> 'knowledge_remediation') = 'object'
      then module.content -> 'knowledge_remediation'
      else '{}'::jsonb
    end
  ) remediation(question_code, value)
  where module.module_type = 'course'
    and module.is_active
    and module.code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ])
    and not exists (
      select 1
      from expected
      where expected.module_code = module.code
        and expected.question_code = remediation.question_code
    );

  if extra_remediation_count <> 0 then
    raise exception 'training mastery v4 contains % unexpected remediation mappings',
      extra_remediation_count;
  end if;

  with expected(module_code, question_code, lesson_id) as (
    values
      ('factory_basics', 'course_check_factory_basics_portal_registration', 'first_access_route'),
      ('factory_basics', 'course_check_factory_basics_source_location', 'interface_map'),
      ('factory_basics', 'course_check_factory_basics_paid_start', 'generation_modes'),
      ('video_quality', 'course_check_video_quality_phone_setup', 'shoot_vertical_source'),
      ('video_quality', 'course_check_video_quality_eight_seconds', 'eight_second_storyboard'),
      ('video_quality', 'course_check_video_quality_succeeded_status', 'full_video_qa'),
      ('publishing_funnel', 'course_check_publishing_funnel_social_access', 'social_account_access'),
      ('publishing_funnel', 'course_check_publishing_funnel_final_url', 'three_urls'),
      ('publishing_funnel', 'course_check_publishing_funnel_vk_finish', 'vk_clips_step_by_step'),
      ('publishing_funnel', 'course_check_publishing_funnel_safe_new_account', 'new_account_safe_start'),
      ('publishing_funnel', 'course_check_publishing_funnel_advertising_gate', 'advertising_classification_and_labeling'),
      ('security_wb', 'course_check_security_wb_substitute_article', 'wb_alias_history'),
      ('security_wb', 'course_check_security_wb_payout_amount', 'calculation_and_payout'),
      ('security_wb', 'course_check_security_wb_paid_status', 'calculation_and_payout')
  )
  select count(*)
  into invalid_remediation_target_count
  from expected
  join content_factory.training_modules module
    on module.code = expected.module_code
   and module.module_type = 'course'
   and module.is_active
  where not exists (
      select 1
      from jsonb_array_elements(
        case
          when jsonb_typeof(module.content -> 'lessons') = 'array'
          then module.content -> 'lessons'
          else '[]'::jsonb
        end
      ) lesson(value)
      where lesson.value ->> 'id' = expected.lesson_id
    )
    or not exists (
      select 1
      from jsonb_array_elements(
        case
          when jsonb_typeof(module.content #> '{knowledge_check,questions}') = 'array'
          then module.content #> '{knowledge_check,questions}'
          else '[]'::jsonb
        end
      ) question(value)
      where 'course_check_' || module.code || '_' ||
        coalesce(question.value ->> 'id', '') = expected.question_code
    );

  if invalid_remediation_target_count <> 0 then
    raise exception 'training mastery v4 contains % invalid remediation targets',
      invalid_remediation_target_count;
  end if;
end;
$training_mastery_v4_contract$;

create or replace function public.creator_complete_module(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  course_code text;
  idempotency_key text;
  request_payload jsonb;
  replay jsonb;
  required_correct integer;
  declared_question_count integer;
  required_walkthrough_ids jsonb;
  required_walkthrough_count integer;
  completed_walkthrough_count integer;
  attempt_id uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  course_code := content_factory_private.require_text(
    p_payload,
    'module_code',
    3,
    80
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );

  select
    case
      when coalesce(module.content #>> '{knowledge_check,pass_score}', '')
        ~ '^[1-9][0-9]*$'
      then (module.content #>> '{knowledge_check,pass_score}')::integer
      else null
    end,
    case
      when jsonb_typeof(module.content #> '{knowledge_check,questions}') = 'array'
      then jsonb_array_length(module.content #> '{knowledge_check,questions}')
      else null
    end,
    case
      when jsonb_typeof(module.content #> '{mastery,required_walkthrough_ids}') = 'array'
      then module.content #> '{mastery,required_walkthrough_ids}'
      else null
    end
  into required_correct, declared_question_count, required_walkthrough_ids
  from content_factory.training_modules module
  where module.code = course_code
    and module.module_type = 'course'
    and module.is_active;

  if required_correct is null
     or declared_question_count is null
     or declared_question_count < 1
     or required_correct > declared_question_count
     or required_walkthrough_ids is null then
    raise exception using
      errcode = '22023',
      message = 'course_not_found';
  end if;

  required_walkthrough_count := jsonb_array_length(required_walkthrough_ids);
  if required_walkthrough_count < 1 then
    raise exception using
      errcode = '22023',
      message = 'course_not_found';
  end if;

  -- Preserve the pre-migration command hash shape so retained network retries
  -- remain compatible with existing idempotency receipts.
  request_payload := p_payload - 'idempotency_key';
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('creator_complete_course:' || course_code)
  );

  select attempt.id into attempt_id
  from content_factory.training_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.module_code = course_code
    and attempt.status = 'completed'
    and attempt.passed
    and attempt.idempotency_key like 'course-check:%'
    and attempt.question_count = declared_question_count
    and attempt.answered_count = declared_question_count
    and attempt.correct_count >= required_correct
  order by attempt.completed_at desc
  limit 1;

  if attempt_id is null then
    raise exception using
      errcode = '42501',
      message = 'course_knowledge_check_required';
  end if;

  select count(*)
  into completed_walkthrough_count
  from jsonb_array_elements_text(required_walkthrough_ids)
    required_walkthrough(walkthrough_id)
  where exists (
    select 1
    from content_factory.training_walkthrough_progress progress
    where progress.organization_id = organization_id
      and progress.profile_id = user_id
      and progress.module_code = course_code
      and progress.walkthrough_id = required_walkthrough.walkthrough_id
      and progress.completed
  );

  if completed_walkthrough_count <> required_walkthrough_count then
    raise exception using
      errcode = '42501',
      message = 'course_practice_required';
  end if;

  -- Both authoritative gates run before consulting an old command receipt, so
  -- a stale pre-v4 success cannot bypass the newly required practice.
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_complete_module',
    idempotency_key,
    request_payload
  );
  if replay is not null
     and coalesce(
       replay ->> 'knowledge_attempt_id',
       replay ->> 'attempt_id'
     ) = attempt_id::text then
    return replay;
  end if;

  insert into content_factory.training_certifications (
    organization_id,
    profile_id,
    module_code,
    attempt_id,
    status
  ) values (
    organization_id,
    user_id,
    course_code,
    attempt_id,
    'passed'
  )
  on conflict on constraint training_certifications_org_profile_module_uq do update set
    attempt_id = excluded.attempt_id,
    status = 'passed',
    granted_at = now(),
    expires_at = null;

  result := jsonb_build_object(
    'ok', true,
    'module_code', course_code,
    'completed', true,
    'attempt_id', attempt_id,
    'knowledge_attempt_id', attempt_id
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'training_course_completed',
    'training_module',
    course_code,
    jsonb_build_object(
      'module_code', course_code,
      'knowledge_attempt_id', attempt_id,
      'practice_walkthrough_count', required_walkthrough_count,
      'server_gate', true
    ),
    'course:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_complete_module',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

do $training_mastery_v4_function_contract$
declare
  function_definition text;
begin
  select pg_get_functiondef(
    'public.creator_complete_module(jsonb)'::regprocedure
  ) into function_definition;

  if function_definition is null
     or strpos(function_definition, 'course_knowledge_check_required') = 0
     or strpos(function_definition, 'training_walkthrough_progress') = 0
     or strpos(function_definition, 'course_practice_required') = 0
     or strpos(function_definition, 'begin_command') = 0
     or strpos(function_definition, 'training_certifications') = 0 then
    raise exception 'creator_complete_module is missing a training mastery gate';
  end if;
end;
$training_mastery_v4_function_contract$;

commit;

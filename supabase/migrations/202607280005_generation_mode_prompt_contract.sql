begin;

-- A paid provider request must contain the complete model-specific base brief,
-- not only a valid SKU and any learned QA fragments.  Keep these instructions
-- claim-free and canonical so the browser, Edge and PostgreSQL can enforce the
-- same contract before a generation job or spend reservation is created.
create or replace function
  content_factory_private.generation_mode_prompt_requirements(
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
declare
  common_requirements text[] := array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.'
  ]::text[];
begin
  if lower(btrim(coalesce(p_model, ''))) not in (
    'seedream5_lite',
    'gen4_turbo',
    'seedance2_fast'
  ) then
    return null;
  end if;

  return common_requirements || case lower(btrim(coalesce(p_model, '')))
    when 'seedream5_lite' then array[
      'Создай одно квадратное товарное фото 2048 × 2048.',
      'Используй @ProductReference как единственный точный референс товара.',
      'Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса.'
    ]::text[]
    when 'gen4_turbo' then array[
      'Создай один непрерывный вертикальный ролик длительностью 5 секунд.',
      'Без речи, дикторского текста и сгенерированных надписей.'
    ]::text[]
    when 'seedance2_fast' then array[
      'Создай один непрерывный вертикальный UGC-ролик длительностью 8 секунд.',
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
    else null::text[]
  end;
end;
$$;

revoke all on function
  content_factory_private.generation_mode_prompt_requirements(text)
  from public, anon, authenticated, service_role;

-- Preserve every existing identity, campaign, budget, learning, repair,
-- rejection and lineage guard underneath this final base-prompt gate.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_mode_prompt_v10;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_mode_prompt_v10(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  model_value text;
  brief_value text;
  product_name_value text;
  sku_value text;
  identity_requirement text;
  requirements text[];
  requirement_value text;
  spoken_value text;
  spoken_word_count integer;
  result_value jsonb;
begin
  -- Preserve the complete legacy validation order.  When it succeeds, the
  -- model prompt is checked in the same statement; raising below rolls back
  -- every job, reservation and event written by the private function before
  -- Edge code can submit anything to a paid provider.
  result_value := content_factory_private
    .creator_start_real_generation_pre_mode_prompt_v10(p_payload);

  p_payload := content_factory_private.require_payload(p_payload);
  model_value := lower(btrim(coalesce(p_payload ->> 'model', '')));
  brief_value := btrim(coalesce(p_payload ->> 'brief', ''));
  product_name_value := btrim(coalesce(p_payload ->> 'product_name', ''));
  sku_value := btrim(coalesce(p_payload ->> 'sku', ''));
  requirements :=
    content_factory_private.generation_mode_prompt_requirements(model_value);
  identity_requirement := format(
    'Точный товар: %s, артикул %s.',
    product_name_value,
    sku_value
  );

  if requirements is null
     or product_name_value = ''
     or sku_value = ''
     or position(identity_requirement in brief_value) = 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_mode_prompt_binding_invalid';
  end if;
  foreach requirement_value in array requirements
  loop
    if position(requirement_value in brief_value) = 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_mode_prompt_binding_invalid';
    end if;
  end loop;

  spoken_value := substring(
    brief_value
    from 'Реплика героя дословно:[[:space:]]*«([^»]+)»'
  );
  if model_value = 'seedance2_fast' then
    if spoken_value is null
       or position('[СОКРАТИТЕ' in spoken_value) > 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_mode_prompt_binding_invalid';
    end if;
    select count(*)::integer into spoken_word_count
    from regexp_matches(
      spoken_value,
      '[[:alnum:]]+([-’''][[:alnum:]]+)*',
      'g'
    );
    if spoken_word_count not between 1 and 22 then
      raise exception using
        errcode = '55000',
        message = 'generation_mode_prompt_binding_invalid';
    end if;
  elsif spoken_value is not null
        or position('Реплика героя дословно:' in brief_value) > 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_mode_prompt_binding_invalid';
  end if;

  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

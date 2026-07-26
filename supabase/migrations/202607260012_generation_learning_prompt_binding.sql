begin;

-- A learned policy is useful only when its bounded structural instructions
-- reach the exact provider prompt.  The browser normalizes the policy for UI
-- use, but the paid boundary must independently bind the current server policy
-- to the immutable canonical prompt fragments.  Raw review copy, claims and
-- recommendations remain excluded.
create or replace function
  content_factory_private.generation_learning_prompt_requirements(
    p_policy jsonb,
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  requirements text[] := array[]::text[];
  angle_value text;
  hook_value text;
  guard_value text;
  requirement_value text;
  hook_patterns jsonb;
  guard_codes jsonb;
  photo boolean;
begin
  if jsonb_typeof(p_policy) <> 'object'
     or p_policy -> 'applied' is distinct from 'true'::jsonb
     or p_model not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     ) then
    return null;
  end if;
  photo := p_model = 'seedream5_lite';
  angle_value := p_policy ->> 'preferred_angle';
  requirement_value := case
    when photo and angle_value = 'product_focus'
      then 'Обученный ракурс: товар целиком, строгий фокус.'
    when photo and angle_value = 'trust_builder'
      then 'Обученный ракурс: естественная предметная подача.'
    when photo and angle_value = 'demonstration'
      then 'Обученный ракурс: одна видимая деталь товара.'
    when photo and angle_value = 'comparison'
      then 'Обученный ракурс: ясный масштаб без второго товара.'
    when photo and angle_value = 'objection_handling'
      then 'Обученный ракурс: упаковка и проверяемые детали.'
    when photo and angle_value = 'curiosity_gap'
      then 'Обученный ракурс: выразительная деталь при видимом целом товаре.'
    when not photo and angle_value = 'product_focus'
      then 'Обученное направление: товар главный во всех кадрах.'
    when not photo and angle_value = 'trust_builder'
      then 'Обученное направление: естественная подача без преувеличений.'
    when not photo and angle_value = 'demonstration'
      then 'Обученное направление: одно видимое действие с товаром.'
    when not photo and angle_value = 'comparison'
      then 'Обученное направление: сравнение без второго товара и обещаний.'
    when not photo and angle_value = 'objection_handling'
      then 'Обученное направление: одна проверяемая деталь товара.'
    when not photo and angle_value = 'curiosity_gap'
      then 'Обученное направление: заметная деталь, затем товар целиком.'
  end;
  if requirement_value is null then
    return null;
  end if;
  requirements := array_append(requirements, requirement_value);

  hook_patterns := coalesce(
    p_policy -> 'preferred_hook_patterns',
    '[]'::jsonb
  );
  if jsonb_typeof(hook_patterns) <> 'array'
     or jsonb_array_length(hook_patterns) > 4
     or exists (
       select 1
       from jsonb_array_elements(hook_patterns) item(value)
       where jsonb_typeof(item.value) <> 'string'
     ) then
    return null;
  end if;
  if not photo and jsonb_array_length(hook_patterns) > 0 then
    hook_value := hook_patterns #>> '{0}';
    requirement_value := case hook_value
      when 'question_led'
        then 'Структурный hook: визуальный вопрос сразу раскрывается точным товаром.'
      when 'why_explanation'
        then 'Структурный hook: видимая причина рассмотреть товар, без утверждений.'
      when 'before_buying'
        then 'Структурный hook: спокойная проверка товара перед выбором.'
      when 'comparison'
        then 'Структурный hook: сравнение без второго товара, цифр и обещаний.'
      when 'demonstration'
        then 'Структурный hook: одно простое действие с товаром.'
      when 'first_person'
        then 'Структурный hook: от первого лица; товар целиком и в фокусе.'
      when 'numbered'
        then 'Структурный hook: один понятный шаг без цифр и надписей.'
      when 'concise'
        then 'Структурный hook: простой первый кадр сразу показывает товар.'
    end;
    if requirement_value is null then
      return null;
    end if;
    requirements := array_append(requirements, requirement_value);
  end if;

  guard_codes := coalesce(p_policy -> 'quality_guard_codes', '[]'::jsonb);
  if jsonb_typeof(guard_codes) <> 'array'
     or jsonb_array_length(guard_codes) > 3
     or exists (
       select 1
       from jsonb_array_elements(guard_codes) item(value)
       where jsonb_typeof(item.value) <> 'string'
     )
     or (
       select count(*)
       from jsonb_array_elements_text(guard_codes)
     ) <> (
       select count(distinct item.value)
       from jsonb_array_elements_text(guard_codes) item(value)
     ) then
    return null;
  end if;

  for guard_value in
    select item.value
    from jsonb_array_elements_text(guard_codes) item(value)
  loop
    requirement_value := case
      when photo and guard_value = 'product_fidelity'
        then 'QA: точная геометрия, этикетка, текст, цвет и пропорции.'
      when photo and guard_value = 'technical_stability'
        then 'QA: резкий товар, ровный свет, без пересвета и размытия.'
      when photo and guard_value = 'hook_clarity'
        then 'QA: товар считывается первым.'
      when photo and guard_value = 'visual_quality'
        then 'QA: чистые края без дублей, деформаций и AI-артефактов.'
      when photo and guard_value = 'trust'
        then 'QA: естественные материалы, свет и масштаб.'
      when photo and guard_value = 'platform_fit'
        then 'QA: мастер 1:1, безопасные поля.'
      when not photo and guard_value = 'product_fidelity'
        then 'QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.'
      when not photo and guard_value = 'technical_stability'
        then 'QA: стабильный проход без чёрных кадров, скачков и мерцания.'
      when not photo and guard_value = 'hook_clarity'
        then 'QA: точный товар и одно действие видны в первые 2 секунды.'
      when not photo and guard_value = 'visual_quality'
        then 'QA: руки, лицо и фактуры без деформаций, дублей и мерцания.'
      when not photo and guard_value = 'trust'
        then 'QA: естественная подача без гиперболы и новых обещаний.'
      when not photo and guard_value = 'platform_fit'
        then 'QA: мастер 9:16; товар и лицо в безопасных полях.'
    end;
    if requirement_value is null then
      return null;
    end if;
    requirements := array_append(requirements, requirement_value);
  end loop;
  return requirements;
exception when others then
  return null;
end;
$$;

revoke all on function
  content_factory_private.generation_learning_prompt_requirements(jsonb, text)
  from public, anon, authenticated, service_role;

-- Preserve the complete claim-evidence and learning implementation behind a
-- private name, then add the final prompt-binding check before any paid state.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_prompt_binding_v5;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_prompt_binding_v5(jsonb)
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
  organization_id uuid;
  learning_context jsonb;
  server_policy jsonb;
  requirements text[];
  requirement_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  learning_context := p_payload -> 'learning_context';
  if jsonb_typeof(learning_context) = 'object'
     and learning_context ->> 'source' = 'performance_learning' then
    organization_id :=
      content_factory_private.resolve_organization(p_payload);
    perform content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'operator']
    );
    server_policy := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', organization_id,
        'media_id', p_payload #>> '{media_ids,0}',
        'platform', p_payload ->> 'platform',
        'model', p_payload ->> 'model'
      )
    );
    if server_policy -> 'applied' is distinct from 'true'::jsonb
       or server_policy ->> 'policy_hash'
          is distinct from learning_context ->> 'applied_policy_hash'
       or server_policy ->> 'preferred_angle'
          is distinct from learning_context ->> 'creative_angle'
       or coalesce(
         server_policy -> 'preferred_hook_patterns',
         '[]'::jsonb
       ) is distinct from coalesce(
         learning_context -> 'hook_patterns',
         '[]'::jsonb
       ) then
      raise exception using
        errcode = '55000',
        message = 'generation_learning_policy_stale';
    end if;
    requirements :=
      content_factory_private.generation_learning_prompt_requirements(
        server_policy,
        p_payload ->> 'model'
      );
    if requirements is null or cardinality(requirements) = 0 then
      raise exception using
        errcode = '22023',
        message = 'generation_learning_prompt_binding_invalid';
    end if;
    foreach requirement_value in array requirements
    loop
      if position(requirement_value in coalesce(p_payload ->> 'brief', '')) = 0
      then
        raise exception using
          errcode = '22023',
          message = 'generation_learning_prompt_binding_invalid';
      end if;
    end loop;
  end if;
  return content_factory_private
    .creator_start_real_generation_pre_prompt_binding_v5(p_payload);
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

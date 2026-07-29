begin;

-- Multiple product angles are one immutable reference bundle.  The first
-- item remains the provider's primary frame; every item must resolve to the
-- same exact product and carry the upload-time rights acknowledgement.

create or replace function
  content_factory_private.generation_product_interaction_requirement(
    p_product_name text,
    p_product_category text
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  product_name_value text :=
    lower(btrim(coalesce(p_product_name, '')));
  category_value text :=
    lower(btrim(coalesce(p_product_category, '')));
begin
  if product_name_value ~
       '(пароварк|мультиварк|аэрогрил|духовк|микроволнов|кофемашин|кофеварк|электрогрил|тостер|соковыжимал|хлебопеч|кухонн.*комбайн|стационарн.*блендер|steamer|air[[:space:]]*fryer|microwave|coffee[[:space:]]*machine|countertop[[:space:]]*appliance)' then
    return 'Масштаб и действие: товар целиком стоит на устойчивой столешнице; не поднимать корпус, не подносить к лицу и не уменьшать его.';
  end if;
  if product_name_value ~
       '(холодильник|морозильник|стиральн.*машин|сушильн.*машин|посудомоеч|телевизор|матрас|диван|кресл|стол([^[:alpha:]]|$)|шкаф|комод|пылесос|кондиционер|обогревател|велосипед|самокат|коляск|refrigerator|washing[[:space:]]*machine|dishwasher|television|mattress|sofa|wardrobe|vacuum)' then
    return 'Масштаб и действие: товар остаётся установленным на полу или рабочем месте; не держать в руках, не подносить к лицу и не уменьшать его.';
  end if;
  return case category_value
    when 'cosmetics' then
      'Масштаб и действие: косметику показывать в руках на уровне корпуса или на столе; не подносить упаковку к лицу и не изображать неподтверждённый эффект.'
    when 'baa' then
      'Масштаб и действие: упаковка БАДа остаётся на столе; показывать этикетку и форму выпуска без приёма внутрь, медицинских обещаний и приближения к лицу.'
    when 'sports_food' then
      'Масштаб и действие: спортивное питание показывать на столе вместе с мерной порцией; не подносить банку к лицу и не изображать результат употребления.'
    when 'food' then
      'Масштаб и действие: еду или напиток показывать на столе рядом с естественной порцией; не подносить упаковку к лицу и не выдумывать вкус или эффект.'
    when 'household' then
      'Масштаб и действие: товар для дома остаётся на устойчивой поверхности в реальном масштабе; показывать рабочую часть, не подносить к лицу и не выдумывать способ использования.'
    when 'apparel' then
      'Масштаб и действие: показать товар надетым или разложенным в естественном масштабе; камеру приближать к деталям, а не товар к лицу.'
    when 'electronics' then
      'Масштаб и действие: электроника стоит на столе или установлена на рабочем месте; показывать интерфейс и разъёмы без поднесения к лицу и выдуманных функций.'
    when 'other' then
      'Масштаб и действие: cold start — товар на устойчивой поверхности в реальном масштабе; без человека, лица и выдуманного использования.'
    else null
  end;
end;
$$;

revoke all on function
  content_factory_private.generation_product_interaction_requirement(
    text,
    text
  )
  from public, anon, authenticated, service_role;

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
  model_value text := lower(btrim(coalesce(p_model, '')));
  common_requirements text[] := array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.'
  ]::text[];
begin
  if model_value not in (
    'seedream5_lite',
    'gen4_turbo',
    'seedance2_fast'
  ) then
    return null;
  end if;

  return common_requirements || case model_value
    when 'seedream5_lite' then array[
      'Создай одно квадратное товарное фото 2048 × 2048.',
      'Используй @ProductReference как главный точный референс товара; остальные выбранные ракурсы уточняют форму и детали.',
      'Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса.'
    ]::text[]
    when 'gen4_turbo' then array[
      'Без речи, дикторского текста и сгенерированных надписей.'
    ]::text[]
    when 'seedance2_fast' then array[
      'Без сгенерированных надписей, субтитров и декоративного текста.'
    ]::text[]
  end;
end;
$$;

revoke all on function
  content_factory_private.generation_mode_prompt_requirements(text)
  from public, anon, authenticated, service_role;

alter function public.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_single_reference_v13;

revoke all on function
  public.creator_start_real_generation_single_reference_v13(jsonb)
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
  user_id uuid;
  organization_id uuid;
  actor_role text;
  team_scope boolean;
  product_id_value uuid;
  batch_id_value uuid;
  job_id_value uuid;
  media_ids jsonb;
  media_count integer;
  distinct_media_count integer;
  media_id_text text;
  verified_media_count integer;
  reference_media_ids jsonb;
  reference_object_names jsonb;
  existing_reference_media_ids jsonb;
  primary_payload jsonb;
  result_value jsonb;
  interaction_requirement text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  media_ids := coalesce(p_payload -> 'media_ids', '[]'::jsonb);
  if jsonb_typeof(media_ids) <> 'array' then
    raise exception using
      errcode = '22023',
      message = 'product_reference_media_ids_invalid';
  end if;
  media_count := jsonb_array_length(media_ids);
  if media_count < 1 or media_count > 5 then
    raise exception using
      errcode = '22023',
      message = 'product_reference_media_ids_invalid';
  end if;
  select count(distinct item.value)::integer
    into distinct_media_count
  from jsonb_array_elements_text(media_ids) item(value);
  if distinct_media_count <> media_count then
    raise exception using
      errcode = '22023',
      message = 'product_reference_media_ids_invalid';
  end if;
  for media_id_text in
    select item.value
    from jsonb_array_elements_text(media_ids) item(value)
  loop
    begin
      perform media_id_text::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023',
        message = 'media_id_invalid';
    end;
  end loop;

  primary_payload := jsonb_set(
    p_payload,
    '{media_ids}',
    jsonb_build_array(media_ids -> 0),
    false
  );
  result_value :=
    public.creator_start_real_generation_single_reference_v13(
      primary_payload
    );

  -- Preserve the established authorization/input error order for legacy
  -- callers and fixtures. Production clients provide product_category; for
  -- those requests this guard still runs inside the same transaction, before
  -- the Edge Function can contact the paid provider.
  if p_payload ? 'product_category'
     and p_payload ->> 'model' <> 'seedream5_lite' then
    interaction_requirement :=
      content_factory_private.generation_product_interaction_requirement(
        p_payload ->> 'product_name',
        p_payload ->> 'product_category'
      );
    if interaction_requirement is null
       or position(
         interaction_requirement
         in btrim(coalesce(p_payload ->> 'brief', ''))
       ) = 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_product_interaction_invalid';
    end if;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  team_scope := actor_role in ('owner', 'admin', 'producer');
  begin
    job_id_value := (result_value #>> '{job,id}')::uuid;
    batch_id_value := (result_value #>> '{batch,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using
      errcode = '55000',
      message = 'generation_reference_bundle_binding_invalid';
  end;

  select
    job.product_id,
    job.input -> 'reference_media_ids'
  into
    product_id_value,
    existing_reference_media_ids
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value
    and job.batch_id = batch_id_value
    and job.requested_by = user_id
  for update;
  if product_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'generation_reference_bundle_binding_invalid';
  end if;

  select
    count(*)::integer,
    jsonb_agg(to_jsonb(media.id::text) order by selected_reference.ordinality),
    jsonb_agg(to_jsonb(media.object_name) order by selected_reference.ordinality)
  into
    verified_media_count,
    reference_media_ids,
    reference_object_names
  from jsonb_array_elements_text(media_ids)
    with ordinality selected_reference(media_id_text, ordinality)
  join content_factory.media_objects media
    on media.organization_id = organization_id
   and media.id = selected_reference.media_id_text::uuid
   and media.product_id = product_id_value
   and media.status = 'ready'
   and coalesce(media.metadata ->> 'kind', '') in (
     'product_photo',
     'packshot'
   )
   and media.metadata -> 'rights_confirmed' = 'true'::jsonb
   and (team_scope or media.owner_id = user_id);
  if verified_media_count <> media_count
     or reference_media_ids is distinct from media_ids then
    raise exception using
      errcode = '42501',
      message = 'exact_product_reference_bundle_mismatch';
  end if;
  if existing_reference_media_ids is not null
     and existing_reference_media_ids is distinct from reference_media_ids then
    raise exception using
      errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;

  update content_factory.generation_jobs job
  set input = job.input || jsonb_build_object(
    'reference_media_ids', reference_media_ids,
    'reference_object_names', reference_object_names,
    'reference_count', media_count
  )
  where job.organization_id = organization_id
    and job.id = job_id_value;

  update content_factory.generation_batches batch
  set input = batch.input || jsonb_build_object(
    'reference_media_ids', reference_media_ids,
    'reference_count', media_count
  )
  where batch.organization_id = organization_id
    and batch.id = batch_id_value;

  result_value := jsonb_set(
    result_value,
    '{job,reference_media_ids}',
    reference_media_ids,
    true
  );
  result_value := jsonb_set(
    result_value,
    '{job,reference_object_names}',
    reference_object_names,
    true
  );
  result_value := jsonb_set(
    result_value,
    '{job,reference_count}',
    to_jsonb(media_count),
    true
  );
  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

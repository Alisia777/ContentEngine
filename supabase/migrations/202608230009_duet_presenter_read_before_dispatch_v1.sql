begin;

-- 202608230009_duet_presenter_read_before_dispatch_v1
--
-- «Дуэт»: ЧЕМ ведущий является у провайдера — читается заново перед отправкой.
--
-- ВТОРАЯ ПОЛОВИНА РАЗДЕЛЕНИЯ. Первая (202608230008) подписала на привязке, КТО
-- ведущий. Здесь появляется способ узнать, чем он является у провайдера
-- СЕЙЧАС: `avatarId`, `voiceId`, `aspectRatio`.
--
-- ПОЧЕМУ ИМЕННО ЗАНОВО. Идентификаторы у провайдера — не факт о запуске, а
-- состояние внешней записи. Ведущего можно заархивировать, а согласие на образ
-- живого человека — отозвать. Снимок недельной давности воскресил бы обоих:
-- запрос ушёл бы с идентификатором того, кто больше не имеет права говорить, и
-- за это были бы заплачены деньги. Поэтому личность у провайдера НИКОГДА не
-- хранится в подписи — её спрашивают у реестра перед каждой отправкой, и
-- отсутствие ответа останавливает запуск.
--
-- А РАСКЛАДКА — НАОБОРОТ, ИЗ ПОДПИСИ. Она не состояние, а решение оператора,
-- принятое вместе с ценой. Если бы сборка читала текущую раскладку, правка
-- ведущего задним числом сдвинула бы уже оплаченный ролик. Поэтому обёртка
-- отдаёт РАЗНОЕ из разных мест, и это её главное свойство:
--
--   presenter — из реестра, сейчас;
--   layout    — из привязки, подписанный.
--
-- РОВНО ТРИ КЛЮЧА В `presenter`. `duet_presenter_identity` кладёт внутрь ещё и
-- `layout`, а `exactHeygenPresenter` в адаптере требует точный набор и
-- отвергает лишний ключ. Передача «как есть» дала бы отказ уже после резерва —
-- то есть повисший резерв. Поэтому `layout` вычитается здесь, а не там.
--
-- ПОЧЕМУ ОБЁРТКА ВООБЩЕ НУЖНА. `config.toml` не выставляет
-- `content_factory_private` в PostgREST: edge не может позвать приватную схему
-- никак. Обёртка `public.system_*` с грантом только `service_role` — тот же
-- приём, что у остальных функций этого пути.
--
-- ПОЧЕМУ ОТКАЗ ВОЗВРАЩАЕТСЯ, А НЕ БРОСАЕТСЯ. Исключение edge не отличит от
-- обрыва связи, и повторит попытку. Названный отказ — отличит: он попадёт в
-- код предотправочной неудачи, а значит в сверку и в возврат резерва.
--
-- ПОЧЕМУ ВХОД — НАРЯД, А НЕ ПРИВЯЗКА. Путь от наряда к привязке идёт через
-- клейм, и клейм несёт `binding_hash`. Пройти его здесь значит проверить
-- заодно, что привязка — та самая, за которую заплачено. Приняв
-- `binding_id` снаружи, обёртка приняла бы на слово именно то, что должна
-- проверять.

create or replace function public.system_generation_strategy_duet_presenter(
  p_payload jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path to ''
as $function$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  project_id_value uuid;
  generation_job_id_value uuid;
  claim_row content_factory.generation_strategy_start_claims%rowtype;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  identity_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'generation_job_id'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'generation_job_id'
     ]::text[]
     or p_payload ->> 'version' <> 'generation-strategy-duet-presenter-request-v1'
  then
    raise exception using errcode = '22023',
      message = 'generation_strategy_duet_presenter_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  generation_job_id_value := content_factory_private.require_uuid(
    p_payload, 'generation_job_id'
  );

  select claim.* into claim_row
  from content_factory.generation_strategy_start_claims claim
  where claim.organization_id = organization_id_value
    and claim.project_id = project_id_value
    and claim.generation_job_id = generation_job_id_value;
  if claim_row.id is null then
    return jsonb_build_object(
      'ok', false,
      'version', 'generation-strategy-duet-presenter-v1',
      'failure_code', 'duet_presenter_claim_missing'
    );
  end if;

  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.id = claim_row.spec_strategy_binding_id;
  -- Подпись клейма обязана совпасть с привязкой: иначе ведущего прочитали бы
  -- для привязки, отличной от оплаченной.
  if binding_row.id is null
     or binding_row.binding_hash is distinct from claim_row.binding_hash then
    return jsonb_build_object(
      'ok', false,
      'version', 'generation-strategy-duet-presenter-v1',
      'failure_code', 'duet_presenter_binding_not_current'
    );
  end if;
  if binding_row.strategy_id <> 'viral_avatar_ugc'
     or binding_row.duet_presenter_id is null
     or binding_row.duet_layout is null then
    return jsonb_build_object(
      'ok', false,
      'version', 'generation-strategy-duet-presenter-v1',
      'failure_code', 'duet_presenter_not_a_duet_binding'
    );
  end if;

  -- Личность у провайдера — сейчас. Функция сама держит принадлежность
  -- проекту, активность и подтверждённое согласие на образ живого человека:
  -- отозвали согласие или заархивировали ведущего — ответа не будет.
  identity_value := content_factory_private.duet_presenter_identity(
    organization_id_value, project_id_value, binding_row.duet_presenter_id
  );
  if identity_value is null then
    return jsonb_build_object(
      'ok', false,
      'version', 'generation-strategy-duet-presenter-v1',
      'failure_code', 'duet_presenter_not_available'
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-duet-presenter-v1',
    -- Ровно три ключа: adapter требует точный набор и отвергает лишний.
    'presenter', identity_value - 'layout',
    -- Раскладка — подписанная, а не текущая.
    'layout', binding_row.duet_layout
  );
end;
$function$;

revoke all on function public.system_generation_strategy_duet_presenter(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_generation_strategy_duet_presenter(jsonb)
  to service_role;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $duet_presenter_wrapper_verify$
declare
  result_value jsonb;
begin
  -- 1. Отказ по форме — исключением: полезная нагрузка не того вида это
  --    ошибка вызывающего, а не состояние ведущего.
  begin
    perform public.system_generation_strategy_duet_presenter(
      jsonb_build_object('version', 'wrong')
    );
    raise exception using message = 'duet_presenter_took_bad_payload';
  exception when sqlstate '22023' then
    null;
  end;

  -- 2. Отказ по состоянию — значением. Несуществующий наряд обязан вернуть
  --    названный отказ, а не упасть: именно этот код попадёт в сверку.
  result_value := public.system_generation_strategy_duet_presenter(
    jsonb_build_object(
      'version', 'generation-strategy-duet-presenter-request-v1',
      'organization_id', '11111111-1111-4111-8111-111111111111',
      'project_id', '22222222-2222-4222-8222-222222222222',
      'generation_job_id', '33333333-3333-4333-8333-333333333333'
    )
  );
  if result_value -> 'ok' is distinct from 'false'::jsonb
     or result_value ->> 'failure_code' <> 'duet_presenter_claim_missing' then
    raise exception using message = 'duet_presenter_missing_claim_not_named';
  end if;

  -- 3. Права: обёртка существует ради edge и доступна только ему.
  if not has_function_privilege(
       'service_role',
       'public.system_generation_strategy_duet_presenter(jsonb)', 'execute'
     ) then
    raise exception using message = 'duet_presenter_wrapper_not_granted';
  end if;
  if has_function_privilege(
       'authenticated',
       'public.system_generation_strategy_duet_presenter(jsonb)', 'execute'
     ) or has_function_privilege(
       'anon',
       'public.system_generation_strategy_duet_presenter(jsonb)', 'execute'
     ) then
    raise exception using message = 'duet_presenter_wrapper_too_open';
  end if;

  -- 4. Разделение соблюдено в самом теле: личность спрашивается у реестра,
  --    раскладка берётся из привязки. Перепутать их местами — это и есть та
  --    ошибка, ради предотвращения которой файл написан.
  if position(
       'identity_value - ''layout''' in
       pg_get_functiondef(
         'public.system_generation_strategy_duet_presenter(jsonb)'::regprocedure
       )
     ) = 0 then
    raise exception using message = 'duet_presenter_layout_not_stripped';
  end if;
  if position(
       '''layout'', binding_row.duet_layout' in
       pg_get_functiondef(
         'public.system_generation_strategy_duet_presenter(jsonb)'::regprocedure
       )
     ) = 0 then
    raise exception using message = 'duet_presenter_layout_not_signed';
  end if;
end;
$duet_presenter_wrapper_verify$;

commit;

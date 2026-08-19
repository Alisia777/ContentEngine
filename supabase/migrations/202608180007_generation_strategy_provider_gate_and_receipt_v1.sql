begin;

-- 202608180007_generation_strategy_provider_gate_and_receipt_v1
--
-- Последние три места, где второй провайдер упирался в слово «runway».
--
-- 1. Белый список разрешённых провайдеров: без арма каталог отдаёт стратегию
--    выключенной целиком, и до расчёта цены дело не доходит вовсе.
-- 2. Квитанция готовности вписывала провайдера литералом. Провайдер берётся из
--    снимка цены — того самого, который к этому моменту уже сверен построчно,
--    поэтому подменить движок в обход цены невозможно.
-- 3. Проверка задач допускала только двух провайдеров. Без третьего клейм упал
--    бы уже ПОСЛЕ резервирования денег, оставив висящий резерв.
--
-- Тела функций правятся точечной заменой известного фрагмента с проверкой
-- результата: полные тела живут в 202608130002 и 202608130007, и переписывать
-- их целиком ради одной строки означало бы рисковать остальным содержимым.

do $launch_gate$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  if definition_value is null then
    raise exception using message = 'launch_gate_missing';
  end if;
  patched_value := replace(
    definition_value,
    $f$when 'runway:seedream5_lite' then true$f$,
    $r$when 'fal:fal-ai/pika/v2/pikaswaps' then true
    when 'runway:seedream5_lite' then true$r$
  );
  if position($c$'fal:fal-ai/pika/v2/pikaswaps'$c$ in patched_value) = 0 then
    raise exception using message = 'launch_gate_patch_failed';
  end if;
  execute patched_value;
end;
$launch_gate$;

do $readiness_provider$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_record_generation_strategy_readiness';
  if definition_value is null then
    raise exception using message = 'readiness_missing';
  end if;
  patched_value := replace(
    definition_value,
    $f$    'runway', selection_row.recipe, selection_row.catalog_version,$f$,
    $r$    coalesce(selection_row.price_snapshot ->> 'provider', 'runway'),
    selection_row.recipe, selection_row.catalog_version,$r$
  );
  if position($c$'runway', selection_row.recipe$c$ in patched_value) > 0
     or position($c$price_snapshot ->> 'provider'$c$ in patched_value) = 0 then
    raise exception using message = 'readiness_provider_patch_failed';
  end if;
  execute patched_value;
end;
$readiness_provider$;

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_spend_contract_v48_check;
alter table content_factory.generation_jobs
  add constraint generation_jobs_spend_contract_v48_check
  check (
    mode <> 'real'
    or (provider in ('runway', 'google', 'fal') and allow_real_spend = true)
  );

do $provider_gate_and_receipt_verify$
declare
  gate_definition text;
  receipt_definition text;
begin
  select pg_get_functiondef(p.oid) into gate_definition
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'generation_provider_launch_enabled';
  select pg_get_functiondef(p.oid) into receipt_definition
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_record_generation_strategy_readiness';
  if gate_definition is null
     or position($c$'fal:fal-ai/pika/v2/pikaswaps'$c$ in gate_definition) = 0
     or position($c$'runway:gen4_turbo'$c$ in gate_definition) = 0
     or receipt_definition is null
     or position($c$price_snapshot ->> 'provider'$c$ in receipt_definition) = 0
  then
    raise exception using message = 'provider_gate_and_receipt_verify_failed';
  end if;
end;
$provider_gate_and_receipt_verify$;

commit;

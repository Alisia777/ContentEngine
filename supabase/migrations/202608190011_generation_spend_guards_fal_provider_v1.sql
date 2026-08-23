begin;

-- 202608190011_generation_spend_guards_fal_provider_v1
--
-- Весь денежный контур признаёт второго провайдера, а не только резерв.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. После 202608190010 платный запуск на fal дошёл дальше:
-- клейм создался, наряд появился со статусом queued, 47 центов
-- зарезервировались. Дальше запуск встал — отправки провайдеру не случилось, а
-- портал ответил generation_dispatch_state_unavailable. Резерв повис: деньги
-- заняты, задачи у провайдера нет.
--
-- ПОЧЕМУ. Перевод наряда из queued в starting сторожит
-- guard_real_generation_spend_start. Он разбирает случаи по провайдеру, и оба
-- его списка перечисляли ('runway','google'). Наряд fal не попадал в ветку «это
-- уже оплаченный наряд, проверь неизменность» и проваливался в следующую —
-- «платный наряд возникает из ниоткуда», то есть
-- generation_spend_paid_job_conversion_forbidden. Сторож защищал от подмены
-- бесплатного наряда платным и принял за такую подмену обычный запуск второго
-- движка.
--
-- И ЭТО НЕ ОДНА ФУНКЦИЯ. Тот же список стоит ещё в четырёх местах денежного
-- контура: кампанийный резерв и его сторож, сверка наряда со спецификацией и
-- журнал трат. Пока они молчали, потому что стоят ПОСЛЕ перевода в starting —
-- до них дело просто не доходило. Чинить их по одному значило бы разбирать
-- один и тот же отказ пять раз подряд, каждый раз тратя запуск.
--
-- ЧТО ИМЕННО ПРАВИТСЯ. В каждый список добавляется 'fal'. Это НЕ ослабление:
-- перечисленные механизмы не пропускают чужого провайдера мимо контроля, они
-- решают, применять ли контроль вообще. До правки fal оставался вне их —
-- значит вне кампанийного потолка, вне сверки со спецификацией и вне журнала
-- трат. Именно поэтому расширение делается сразу везде: маршрут, за который
-- платят, обязан подчиняться тем же правилам, что и первый.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Ни одна проверка не снимается и ни один потолок
-- не двигается. Провайдер 'google' и 'runway' ведут себя ровно как прежде:
-- в списках они стоят первыми и сравнение по-прежнему точное.

do $spend_guards_fal$
declare
  target text;
  definition_value text;
  patched_value text;
  hits integer;
begin
  foreach target in array array[
    'guard_real_generation_spend_start',
    'guard_generation_campaign_spend_start',
    'guard_generation_spec_provider_start',
    'reserve_generation_campaign_spend',
    'record_real_generation_spend_lifecycle'
  ] loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private' and p.proname = target;
    if definition_value is null then
      raise exception using message = 'spend_guard_missing:' || target;
    end if;

    -- Повторный прогон ничего не меняет.
    if position($f$'runway','google','fal'$f$ in definition_value) > 0 then
      continue;
    end if;

    hits := (
      length(definition_value)
      - length(replace(definition_value, $f$'runway','google'$f$, ''))
    ) / length($f$'runway','google'$f$);
    if hits < 1 then
      raise exception using
        message = 'spend_guard_anchor_missing:' || target;
    end if;

    -- Заменяются ВСЕ вхождения: в guard_real_generation_spend_start их два, и
    -- починка одного оставила бы функцию противоречащей самой себе.
    patched_value := replace(
      definition_value, $f$'runway','google'$f$, $f$'runway','google','fal'$f$
    );
    if position($f$'runway','google','fal'$f$ in patched_value) = 0 then
      raise exception using message = 'spend_guard_patch_failed:' || target;
    end if;
    execute patched_value;
  end loop;
end;
$spend_guards_fal$;

do $spend_guards_fal_verify$
declare
  target text;
  definition_value text;
  remaining integer;
begin
  foreach target in array array[
    'guard_real_generation_spend_start',
    'guard_generation_campaign_spend_start',
    'guard_generation_spec_provider_start',
    'reserve_generation_campaign_spend',
    'record_real_generation_spend_lifecycle',
    'reserve_real_generation_spend'
  ] loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private' and p.proname = target;

    -- 1. Второй провайдер признан.
    if definition_value is null
       or position($f$'runway','google','fal'$f$ in definition_value) = 0 then
      raise exception using message = 'spend_guard_verify_failed:' || target;
    end if;

    -- 2. Не осталось ни одного списка без 'fal': в guard_real_generation_
    --    spend_start их два, и разъехавшиеся списки — это отказ на половине
    --    пути, самый дорогой вид отказа на денежном контуре.
    remaining := (
      length(definition_value)
      - length(replace(definition_value, $f$'runway','google')$f$, ''))
    ) / length($f$'runway','google')$f$);
    if remaining > 0 then
      raise exception using
        message = 'spend_guard_list_missed:' || target || ':' || remaining::text;
    end if;
  end loop;

  -- 3. Сторожа на месте и по-прежнему умеют отказывать: проверяется наличие
  --    самих сообщений, а не только списков.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'guard_real_generation_spend_start';
  if position('generation_spend_paid_job_conversion_forbidden'
       in definition_value) = 0
     or position('generation_spend_reservation_identity_immutable'
       in definition_value) = 0 then
    raise exception using message = 'spend_guard_messages_lost';
  end if;
end;
$spend_guards_fal_verify$;

commit;

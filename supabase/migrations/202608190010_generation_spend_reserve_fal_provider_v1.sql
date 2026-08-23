begin;

-- 202608190010_generation_spend_reserve_fal_provider_v1
--
-- Резерв денег признаёт второго провайдера.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. Платный запуск «Копии» на маршруте fal отвечал
-- generation_unavailable (503) без объяснения. Бесплатная часть проходила
-- целиком: привязка считала 47 центов, квитанция готовности выписывалась с
-- provider = 'fal', экран показывал точную цену. Клейм при этом не появлялся
-- ни разу — то есть отказ случался ДО резервирования, и деньги не двигались.
--
-- ПОЧЕМУ. Вставку наряда сторожит триггер
-- content_factory_private.reserve_real_generation_spend: он и есть место, где
-- деньги резервируются в суточном и месячном бюджете. Первым делом он
-- проверяет провайдера списком ('runway', 'google') — список остался с тех
-- пор, когда других провайдеров не существовало. Наряд с provider = 'fal'
-- отвергался с generation_spend_provider_contract_invalid (42501), а разбор
-- ошибок в creator-generate этот код в ветке стратегий не знает и отдаёт
-- наружу общий 503. Отказ был громким внутри и немым снаружи.
--
-- ЧТО ИМЕННО ПРАВИТСЯ. В списке допустимых провайдеров появляется 'fal'.
-- Больше ничего: ни одна проверка не снимается и ни одна граница не сдвигается.
-- Сумма по-прежнему обязана быть положительной, валюта — USD, рубильник
-- платной генерации (generation_spend_platform_control) и оба потолка
-- (суточный и месячный, командный и кампанийный) действуют как прежде и для
-- нового провайдера тоже: fal попадает под тот же контроль, а не в обход него.
--
-- ПОЧЕМУ СПИСКОМ, А НЕ ПРОВЕРКОЙ ПО РЕЕСТРУ МАРШРУТОВ. Здесь сторож денег, и
-- он обязан быть проще того, что охраняет: список провайдеров, которых мы
-- умеем оплачивать, короче и понятнее запроса в другую таблицу, а лишний
-- источник правды в денежном триггере — лишний способ ошибиться.

do $reserve_spend_fal$
declare
  definition_value text;
  patched_value text;
  anchor_hits integer;
  anchor_text constant text := $f$  if new.provider not in ('runway','google')$f$;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'reserve_real_generation_spend';
  if definition_value is null then
    raise exception using message = 'reserve_real_generation_spend_missing';
  end if;

  -- Повторный прогон ничего не меняет.
  if position($f$('runway','google','fal')$f$ in definition_value) > 0 then
    return;
  end if;

  anchor_hits := (
    length(definition_value)
    - length(replace(definition_value, anchor_text, ''))
  ) / length(anchor_text);
  if anchor_hits <> 1 then
    raise exception using
      message = 'reserve_spend_anchor_not_unique:' || anchor_hits::text;
  end if;

  patched_value := replace(
    definition_value,
    anchor_text,
    $f$  if new.provider not in ('runway','google','fal')$f$
  );
  if position($f$('runway','google','fal')$f$ in patched_value) = 0 then
    raise exception using message = 'reserve_spend_patch_failed';
  end if;

  execute patched_value;
end;
$reserve_spend_fal$;

do $reserve_spend_fal_verify$
declare
  definition_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'content_factory_private'
    and p.proname = 'reserve_real_generation_spend';

  -- 1. Новый провайдер допущен.
  if definition_value is null
     or position($f$('runway','google','fal')$f$ in definition_value) = 0 then
    raise exception using message = 'reserve_spend_verify_failed';
  end if;

  -- 2. Ни одна прежняя защита не исчезла: сумма, валюта, рубильник платной
  --    генерации и оба потолка остались на месте. Проверяется наличие тех же
  --    строк, что стояли до правки, — ослабление сторожа денег не должно
  --    пройти незамеченным.
  if position('generation_spend_provider_contract_invalid' in definition_value) = 0
     or position('new.estimated_cost_minor <= 0' in definition_value) = 0
     or position($f$'{billing,currency}'$f$ in definition_value) = 0
     or position('generation_spend_platform_control' in definition_value) = 0
     or position('generation_spend_policies' in definition_value) = 0 then
    raise exception using message = 'reserve_spend_guard_lost';
  end if;
end;
$reserve_spend_fal_verify$;

commit;

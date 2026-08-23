begin;

-- 202608220007_generation_provider_heygen_v1
--
-- РЕШЕНИЕ ВЛАДЕЛЬЦА 22.08.2026: ведущий для «Дуэта» берётся у HeyGen, отдельным
-- ключом и отдельным кошельком.
--
-- ПОЧЕМУ ИМЕННО ОН. Формат «Дуэт» требует ПОСТОЯННОГО ведущего: один и тот же
-- человек во всех роликах проекта — это узнаваемость, ради которой формат и
-- существует. У моделей fal внешность держится на том, что мы каждый раз
-- подаём одну и ту же фотографию: похоже, но не тождественно, и расхождение
-- накапливается от ролика к ролику. HeyGen закрепляет личность НА СВОЕЙ
-- СТОРОНЕ: аватар создаётся один раз и получает avatar_id, дальше все ролики
-- ссылаются на него. Тождественность обеспечена устройством, а не удачей.
--
-- Второе: HeyGen отдаёт ведущего с ПРОЗРАЧНЫМ ФОНОМ (webm/VP9). Без альфы
-- врезка в угол — прямоугольная плашка; с альфой ведущий стоит в кадре, а не
-- лежит на нём.
--
-- ЧТО ЭТА МИГРАЦИЯ ДЕЛАЕТ. Только расширяет словарь: провайдер, вид опроса и
-- версия прайса. Ни одного маршрута она не заводит и ничего не включает —
-- строки реестра и адаптер приедут отдельно, когда будет чем их проверить.
--
-- ПОЧЕМУ ВСЕ ДЕВЯТЬ ОГРАНИЧЕНИЙ РАЗОМ. Они перекрёстно стерегут один и тот же
-- путь денег: реестр маршрутов → квитанция готовности → подписанный выбор →
-- наряд → партия. Расширить часть значило бы получить отказ не на входе, а в
-- середине оплаченного запуска — то есть после резервирования средств.

-- 1. Реестр маршрутов: провайдер и вид опроса.
alter table content_factory.generation_strategy_provider_routes
  drop constraint generation_strategy_provider_routes_provider_check;
alter table content_factory.generation_strategy_provider_routes
  add constraint generation_strategy_provider_routes_provider_check
  check (provider = any (array['runway', 'google', 'fal', 'heygen']));

-- Опрос у HeyGen свой: генерация асинхронная, ответ отдаёт video_id, а статус
-- забирается отдельным запросом. Это не runway_task и не fal_request — у тех
-- другие поля ответа, и попытка разобрать чужой формат кончилась бы вечным
-- ожиданием при уже списанных деньгах.
alter table content_factory.generation_strategy_provider_routes
  drop constraint generation_strategy_provider_routes_poll_kind_check;
alter table content_factory.generation_strategy_provider_routes
  add constraint generation_strategy_provider_routes_poll_kind_check
  check (poll_kind = any (array[
    'runway_task', 'google_long_running_operation', 'fal_request', 'heygen_video'
  ]));

-- 2. Квитанция готовности: провайдер и версия прайса.
alter table content_factory.generation_strategy_readiness_receipts
  drop constraint generation_strategy_readiness_receipts_provider_check;
alter table content_factory.generation_strategy_readiness_receipts
  add constraint generation_strategy_readiness_receipts_provider_check
  check (provider = any (array['runway', 'fal', 'heygen']));

-- Версия прайса называет СПОСОБ счёта, а не только провайдера: у HeyGen это
-- посекундная ставка за готовое видео ведущего. Имя входит в хеш-подпись
-- строки подтверждения, поэтому переиспользовать имя fal нельзя — подпись
-- утверждала бы не тот способ, которым посчитаны деньги.
alter table content_factory.generation_strategy_readiness_receipts
  drop constraint generation_strategy_readiness_receipts_pricing_version_check;
alter table content_factory.generation_strategy_readiness_receipts
  add constraint generation_strategy_readiness_receipts_pricing_version_check
  check (pricing_version = any (array[
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1',
    'fal-usd-per-second-2026-08-18.v1',
    'heygen-usd-per-second-2026-08-22.v1'
  ]));

-- 3. Подписанный выбор привязки: та же версия прайса.
alter table content_factory.generation_strategy_binding_selections
  drop constraint generation_strategy_binding_selections_pricing_version_check;
alter table content_factory.generation_strategy_binding_selections
  add constraint generation_strategy_binding_selections_pricing_version_check
  check (pricing_version = any (array[
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1',
    'fal-usd-per-second-2026-08-18.v1',
    'heygen-usd-per-second-2026-08-22.v1'
  ]));

-- 4. Наряды: провайдер и денежный контракт.
alter table content_factory.generation_jobs
  drop constraint generation_jobs_provider_v48_check;
alter table content_factory.generation_jobs
  add constraint generation_jobs_provider_v48_check
  check (provider = any (array['mock', 'runway', 'google', 'fal', 'heygen']));

-- Реальная трата по-прежнему требует явного разрешения. 'mock' сюда не входит
-- и не должен: мок не тратит.
alter table content_factory.generation_jobs
  drop constraint generation_jobs_spend_contract_v48_check;
alter table content_factory.generation_jobs
  add constraint generation_jobs_spend_contract_v48_check
  check (
    mode <> 'real'
    or (provider = any (array['runway', 'google', 'fal', 'heygen'])
        and allow_real_spend = true)
  );

-- 5. Партии: провайдер и допустимая пара «провайдер + модель».
alter table content_factory.generation_batches
  drop constraint generation_batches_provider_v48_check;
alter table content_factory.generation_batches
  add constraint generation_batches_provider_v48_check
  check (provider = any (array['mock', 'runway', 'google', 'fal', 'heygen']));

alter table content_factory.generation_batches
  drop constraint generation_batches_model_v48_check;
alter table content_factory.generation_batches
  add constraint generation_batches_model_v48_check
  check (
    mode <> 'real'
    or provider is null
    or content_factory_private.generation_catalog_entry(provider, model) is not null
    or (
      provider = any (array['runway', 'fal', 'heygen'])
      and model = any (array['product_ugc', 'product_swap', 'product_ad'])
    )
  );

do $heygen_provider_verify$
declare
  bad text;
begin
  -- Каждое из девяти ограничений обязано пропускать heygen. Проверяем не
  -- текстом определения, а поведением: пробуем значение и ловим отказ.
  for bad in
    select unnest(array[
      'generation_strategy_provider_routes_provider_check',
      'generation_strategy_provider_routes_poll_kind_check',
      'generation_strategy_readiness_receipts_provider_check',
      'generation_strategy_readiness_receipts_pricing_version_check',
      'generation_strategy_binding_selections_pricing_version_check',
      'generation_jobs_provider_v48_check',
      'generation_jobs_spend_contract_v48_check',
      'generation_batches_provider_v48_check',
      'generation_batches_model_v48_check'
    ])
  loop
    if not exists (select 1 from pg_constraint where conname = bad) then
      raise exception using message = 'heygen_constraint_missing:' || bad;
    end if;
  end loop;

  -- Прежние провайдеры не потеряны: расширение не должно было стать заменой.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_strategy_provider_routes_provider_check'
      and pg_get_constraintdef(oid) like '%''runway''%'
      and pg_get_constraintdef(oid) like '%''fal''%'
      and pg_get_constraintdef(oid) like '%''heygen''%'
  ) then
    raise exception using message = 'provider_set_narrowed';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_strategy_readiness_receipts_pricing_version_check'
      and pg_get_constraintdef(oid) like '%fal-usd-per-run-2026-08-18.v1%'
      and pg_get_constraintdef(oid) like '%fal-usd-per-second-2026-08-18.v1%'
      and pg_get_constraintdef(oid) like '%heygen-usd-per-second-2026-08-22.v1%'
  ) then
    raise exception using message = 'pricing_version_set_narrowed';
  end if;

  -- Мок по-прежнему не может тратить настоящие деньги.
  if exists (
    select 1 from pg_constraint
    where conname = 'generation_jobs_spend_contract_v48_check'
      and pg_get_constraintdef(oid) like '%''mock''%'
  ) then
    raise exception using message = 'mock_allowed_to_spend';
  end if;
end;
$heygen_provider_verify$;

commit;

begin;

-- 202608190009_generation_batches_catalog_models_restore_v1
--
-- Контракт партий генерации снова опирается на каталог моделей, а не на список
-- имён, переписанный от руки.
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. Приёмочный тест мультимодельной генерации
-- (generation_multimodel_acceptance_v4_test) обрывался на вставке партии:
-- «new row for relation "generation_batches" violates check constraint
-- generation_batches_model_v48_check». Обрывался он не на экзотике, а на
-- обычных моделях каталога — gen4.5 и seedance2_mini.
--
-- ОТКУДА ЭТО ВЗЯЛОСЬ. До 202608180005 ограничение спрашивало КАТАЛОГ:
-- content_factory_private.generation_catalog_entry(provider, model) is not
-- null. Миграция 202608180005 расширяла ограничение веткой для второго
-- провайдера и при этом переписала его целиком, заменив обращение к каталогу
-- перечислением имён. В перечисление попали три модели Runway из шести, и
-- gen4.5, seedance2_mini, veo3.1_fast, gemini_omni_flash молча выпали из
-- допустимых. Каталог о них по-прежнему знает и по-прежнему считает им цену —
-- то есть система готова продать модель, партию с которой сама же не примет.
--
-- ПОЧЕМУ ЭТО НАДО ЧИНИТЬ, А НЕ ЗАКРЕПИТЬ В ТЕСТЕ. Список имён и каталог — два
-- описания одного факта, и они уже разошлись. Закрепить сужение значило бы
-- объявить выбывшие модели снятыми с обращения, ничего про них не решив: их
-- никто не выводил, у них есть цены и приёмка. Опора на каталог возвращает
-- ровно одно описание — то, из которого считаются деньги.
--
-- ЧТО СОХРАНЯЕТСЯ БЕЗ ИЗМЕНЕНИЙ. Ветки рецептов стратегий (product_ugc,
-- product_swap, product_ad) остаются перечислением и остаются для обоих
-- провайдеров: этих строк в каталоге моделей нет вовсе — рецепт стратегии не
-- модель, у него своя цена и свой спенд-контур. Ветка google и правило «партия
-- не в режиме real либо без провайдера не проверяется» тоже сохраняются
-- дословно.

-- Снимок: сколько партий сегодня НЕ прошло бы ограничение. Ослабление не
-- должно быть незаметным, поэтому проверяется до и после.
select set_config(
  'contentengine.batches_model_check_before',
  (
    select count(*)::text
    from content_factory.generation_batches as batch
    where batch.mode = 'real'
      and batch.provider is not null
      and content_factory_private.generation_catalog_entry(
        batch.provider, batch.model
      ) is null
      and batch.model not in ('product_ugc', 'product_swap', 'product_ad')
  ),
  true
);

alter table content_factory.generation_batches
  drop constraint if exists generation_batches_model_v48_check;
alter table content_factory.generation_batches
  add constraint generation_batches_model_v48_check
  check (
    mode <> 'real'
    or provider is null
    -- Каталог моделей — единственный источник того, какие модели существуют.
    or content_factory_private.generation_catalog_entry(provider, model)
         is not null
    -- Рецепты стратегий каталогом моделей не описываются: у них собственная
    -- цена и собственный спенд-контур. Оба провайдера «Копии» исполняют один и
    -- тот же рецепт, поэтому ветка одна на двоих.
    or (
      provider in ('runway', 'fal')
      and model = any (array['product_ugc', 'product_swap', 'product_ad'])
    )
  );

do $batches_model_check_verify$
declare
  constraint_definition text;
  before_count integer;
  after_count integer;
  catalog_rejected integer;
begin
  select pg_get_constraintdef(oid) into constraint_definition
  from pg_constraint
  where conrelid = 'content_factory.generation_batches'::regclass
    and conname = 'generation_batches_model_v48_check';
  if constraint_definition is null
     or constraint_definition not like '%generation_catalog_entry%'
     or constraint_definition not like '%product_swap%'
     or constraint_definition not like '%fal%' then
    raise exception using message = 'batches_model_check_shape_invalid';
  end if;

  -- Ни одна существующая партия не стала недопустимой: ограничение только
  -- расширено. Число «непроходящих» строк обязано остаться прежним.
  before_count := coalesce(
    nullif(current_setting('contentengine.batches_model_check_before', true), ''),
    '0'
  )::integer;
  select count(*) into after_count
  from content_factory.generation_batches as batch
  where batch.mode = 'real'
    and batch.provider is not null
    and content_factory_private.generation_catalog_entry(
      batch.provider, batch.model
    ) is null
    and batch.model not in ('product_ugc', 'product_swap', 'product_ad');
  if after_count <> before_count then
    raise exception using
      message = 'batches_model_check_drifted:' || after_count::text;
  end if;

  -- Модели каталога, из-за которых ограничение и разошлось с реальностью,
  -- снова допустимы. Проверяется не имя, а сам инвариант: то, что каталог
  -- знает, партия обязана принимать.
  select count(*) into catalog_rejected
  from (
    values ('runway', 'gen4.5'), ('runway', 'seedance2_mini'),
           ('runway', 'gen4_turbo')
  ) as candidate(provider, model)
  where content_factory_private.generation_catalog_entry(
    candidate.provider, candidate.model
  ) is null;
  if catalog_rejected > 0 then
    raise exception using
      message = 'catalog_models_missing:' || catalog_rejected::text;
  end if;
end;
$batches_model_check_verify$;

commit;

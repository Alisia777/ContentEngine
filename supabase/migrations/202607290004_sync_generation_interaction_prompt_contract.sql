begin;

-- Keep the paid database boundary byte-for-byte aligned with the browser
-- compiler and creator-generate Edge Function. A prompt assembled by the
-- portal must not be rejected because an older server-side wording survived.
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
    return 'Масштаб и действие: товар показан целиком в естественном размере на устойчивой столешнице; герой взаимодействует с крышкой, панелью управления и готовым результатом.';
  end if;
  if product_name_value ~
       '(холодильник|морозильник|стиральн.*машин|сушильн.*машин|посудомоеч|телевизор|матрас|диван|кресл|стол([^[:alpha:]]|$)|шкаф|комод|пылесос|кондиционер|обогревател|велосипед|самокат|коляск|refrigerator|washing[[:space:]]*machine|dishwasher|television|mattress|sofa|wardrobe|vacuum)' then
    return 'Масштаб и действие: товар показан целиком в естественном размере на месте использования; герой взаимодействует с управлением или рабочей частью.';
  end if;
  return case category_value
    when 'cosmetics' then
      'Масштаб и действие: точная упаковка показана на столе или в руках на уровне корпуса; в кадре только дозатор, текстура и подтверждённые детали без демонстрации эффекта на лице.'
    when 'baa' then
      'Масштаб и действие: упаковка БАДа показана целиком на столе; в кадре этикетка и форма выпуска без сцены приёма и медицинских обещаний.'
    when 'sports_food' then
      'Масштаб и действие: точная упаковка спортивного питания показана на столе рядом с мерной порцией; в кадре только продукт и подтверждённые детали этикетки.'
    when 'food' then
      'Масштаб и действие: точная упаковка еды или напитка показана на столе рядом с естественной порцией; камера показывает фактуру без выдуманных свойств.'
    when 'household' then
      'Масштаб и действие: товар для дома показан целиком в естественном размере на устойчивой поверхности; герой демонстрирует одну видимую рабочую часть и понятное безопасное действие.'
    when 'apparel' then
      'Масштаб и действие: товар показан надетым или разложенным в естественном масштабе; камера переходит от общего вида к материалу и деталям.'
    when 'electronics' then
      'Масштаб и действие: устройство показано целиком на столе или рабочем месте; камера переходит к интерфейсу, управлению и видимым разъёмам без выдуманных функций.'
    when 'other' then
      'Масштаб и действие: товар целиком в естественном масштабе на устойчивой поверхности; камера показывает только видимые детали.'
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

commit;

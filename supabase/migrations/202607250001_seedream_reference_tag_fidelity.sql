begin;

-- Runway text-to-image references are prompt-addressable only when the
-- provider request supplies a tag and the prompt uses the matching @mention.
-- Fail closed before a paid Seedream job is inserted if that binding or the
-- existing product/claim guards were removed.
create or replace function
  content_factory_private.enforce_seedream_reference_tag()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  prompt_value text;
  product_name_value text;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend
     or new.input ->> 'model' <> 'seedream5_lite' then
    return new;
  end if;

  prompt_value := coalesce(new.input ->> 'prompt_text', '');
  product_name_value := btrim(coalesce(new.input ->> 'product_name', ''));
  if product_name_value = ''
     or position(product_name_value in prompt_value) = 0
     or position('@ProductReference' in prompt_value) = 0
     or position(
       'Сохрани форму, цвет, упаковку, этикетку и пропорции'
       in prompt_value
     ) = 0
     or position(
       'Не добавляй новые свойства, результаты, медицинские обещания'
       in prompt_value
     ) = 0
     or position('Figure 1' in prompt_value) > 0 then
    raise exception using
      errcode = '22023',
      message = 'seedream_photo_reference_tag_required';
  end if;
  return new;
end;
$$;

drop trigger if exists seedream_reference_tag_guard
  on content_factory.generation_jobs;
create trigger seedream_reference_tag_guard
before insert or update of input on content_factory.generation_jobs
for each row execute function
  content_factory_private.enforce_seedream_reference_tag();

revoke all on function
  content_factory_private.enforce_seedream_reference_tag()
  from public, anon, authenticated;

-- Exercise the trigger function during migration without touching persistent
-- production rows. The temporary relation contains only the fields read by the
-- guard and is dropped automatically at commit.
create temporary table seedream_reference_tag_contract_jobs (
  mode text not null,
  provider text not null,
  allow_real_spend boolean not null,
  input jsonb not null
) on commit drop;

create trigger seedream_reference_tag_contract_guard
before insert on seedream_reference_tag_contract_jobs
for each row execute function
  content_factory_private.enforce_seedream_reference_tag();

do $seedream_reference_tag_trigger_contract$
begin
  begin
    insert into seedream_reference_tag_contract_jobs (
      mode, provider, allow_real_spend, input
    ) values (
      'real',
      'runway',
      true,
      jsonb_build_object(
        'model', 'seedream5_lite',
        'product_name', 'Contract product',
        'prompt_text',
        'Используй Figure 1 для Contract product. ' ||
          'Сохрани форму, цвет, упаковку, этикетку и пропорции. ' ||
          'Не добавляй новые свойства, результаты, медицинские обещания.'
      )
    );
    raise exception 'seedream reference tag contract accepted invalid prompt';
  exception when sqlstate '22023' then
    if sqlerrm <> 'seedream_photo_reference_tag_required' then
      raise;
    end if;
  end;

  insert into seedream_reference_tag_contract_jobs (
    mode, provider, allow_real_spend, input
  ) values (
    'real',
    'runway',
    true,
    jsonb_build_object(
      'model', 'seedream5_lite',
      'product_name', 'Contract product',
      'prompt_text',
      'Используй @ProductReference для Contract product. ' ||
        'Сохрани форму, цвет, упаковку, этикетку и пропорции. ' ||
        'Не добавляй новые свойства, результаты, медицинские обещания.'
    )
  );

  if (
    select count(*)
    from seedream_reference_tag_contract_jobs
  ) <> 1 then
    raise exception 'seedream reference tag contract rejected valid prompt';
  end if;
end;
$seedream_reference_tag_trigger_contract$;

-- Keep the course aligned with the actual provider contract so operators see
-- the same stable reference name that the automatic brief and Edge request use.
update content_factory.training_modules module
set
  content = replace(
    module.content::text,
    'Figure 1',
    '@ProductReference'
  )::jsonb,
  updated_at = now()
where module.module_type = 'course'
  and module.is_active
  and module.content::text like '%Figure 1%';

do $seedream_reference_tag_fidelity_contract$
declare
  invalid_training_count integer;
begin
  select count(*)::integer into invalid_training_count
  from content_factory.training_modules module
  where module.module_type = 'course'
    and module.is_active
    and module.code in ('factory_basics', 'video_quality')
    and module.content::text like '%Figure 1%';

  if invalid_training_count <> 0
     or not exists (
       select 1
       from content_factory.training_modules module
       where module.module_type = 'course'
         and module.is_active
         and module.code = 'factory_basics'
         and module.content::text like '%@ProductReference%'
     )
     or not exists (
       select 1
       from pg_catalog.pg_trigger trigger_value
       where trigger_value.tgrelid =
         'content_factory.generation_jobs'::regclass
         and trigger_value.tgname = 'seedream_reference_tag_guard'
         and not trigger_value.tgisinternal
     ) then
    raise exception 'seedream reference tag fidelity contract failed';
  end if;
end;
$seedream_reference_tag_fidelity_contract$;

commit;

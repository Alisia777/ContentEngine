begin;

-- 202608220012_duet_presenter_layout_v1
--
-- Раскладка врезки как настройка ведущего.
--
-- ЗАЧЕМ ХРАНИТЬ У ВЕДУЩЕГО, А НЕ СПРАШИВАТЬ КАЖДЫЙ РАЗ. «Наша Аня всегда слева
-- внизу вырезом» — это свойство ведущего, а не решение по каждому ролику.
-- Спрашивать одно и то же при каждом запуске значит превращать настройку в
-- обязательный шаг, который перестают читать. Заданное один раз значение
-- остаётся умолчанием, а при запуске его можно переопределить, если для
-- конкретного ролика хочется иначе.
--
-- ПРЕДЕЛЫ РАЗМЕРА — НЕ КОСМЕТИКА. Ведущий меньше пятой части ширины кадра
-- неразличим на телефоне; больше половины — закрывает то, что комментирует.
-- И то и другое делает формат бессмысленным, поэтому за границы не пускаем.
--
-- ДОЛЯ ХРАНИТСЯ ЦЕЛЫМИ ПРОЦЕНТАМИ. Дробь в базе означала бы сравнения с
-- плавающей точкой в ограничении и в сверке со сборщиком; проценты сравниваются
-- точно. Пересчёт в долю делается на границе, в самом сборщике.
--
-- ЭТИ ЖЕ ПРЕДЕЛЫ ПОВТОРЕНЫ В app/services/duet_composition.py. Дублирование
-- намеренное: сборщик обязан отвергать негодную раскладку сам, даже если она
-- пришла мимо базы. Совпадение двух списков проверяется тестом.

alter table content_factory.generation_duet_presenters
  add column if not exists overlay_corner text not null default 'bottom_left',
  add column if not exists overlay_shape text not null default 'cutout',
  add column if not exists overlay_width_percent smallint not null default 34;

do $duet_layout_constraints$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_overlay_corner_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_overlay_corner_check
      check (overlay_corner = any (array[
        'bottom_left', 'bottom_right', 'top_left', 'top_right'
      ]));
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_overlay_shape_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_overlay_shape_check
      -- cutout — ведущий вырезан по контуру; window — под ним рисуется
      -- подложка, привычный вид реакции. Один и тот же файл ведущего.
      check (overlay_shape = any (array['cutout', 'window']));
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_overlay_width_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_overlay_width_check
      check (overlay_width_percent between 20 and 50);
  end if;
end;
$duet_layout_constraints$;

-- Витрина отдаёт раскладку: оператор должен видеть, где ведущий встанет, ещё до
-- запуска. Идентификаторы провайдера по-прежнему не отдаются.
create or replace function public.creator_list_duet_presenters(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  project_id_value uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();

  if p_payload - array['organization_id', 'project_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'duet_presenters_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );

  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );

  select jsonb_build_object(
    'ok', true,
    'version', 'generation-duet-presenters-v1',
    'presenters', coalesce(jsonb_agg(
      jsonb_build_object(
        'id', presenter.id,
        'display_name', presenter.display_name,
        'provider', presenter.provider,
        'aspect_ratio', presenter.aspect_ratio,
        'is_default', presenter.is_default,
        'likeness_kind', presenter.likeness_kind,
        'likeness_consent_confirmed', presenter.likeness_consent_confirmed,
        'overlay_corner', presenter.overlay_corner,
        'overlay_shape', presenter.overlay_shape,
        'overlay_width_percent', presenter.overlay_width_percent,
        'created_at', presenter.created_at
      )
      order by presenter.is_default desc, presenter.created_at desc
    ), '[]'::jsonb)
  ) into result
  from content_factory.generation_duet_presenters presenter
  where presenter.organization_id = organization_id
    and presenter.project_id = project_id_value
    and presenter.status = 'active';

  return result;
end;
$$;

-- Изменение раскладки — отдельная операция: менять её не значит заводить нового
-- ведущего, и требовать для этого пересоздания было бы издевательством.
create or replace function public.creator_update_duet_presenter_layout(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
#variable_conflict use_variable
declare
  org_id uuid;
  proj_id uuid;
  presenter_id_value uuid;
  presenter_row content_factory.generation_duet_presenters;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();

  if p_payload - array[
       'organization_id', 'project_id', 'presenter_id',
       'overlay_corner', 'overlay_shape', 'overlay_width_percent'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'duet_presenter_layout_payload_invalid';
  end if;

  org_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    org_id, true, array['owner', 'admin', 'producer', 'operator']
  );

  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  proj_id := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(org_id, proj_id);
  presenter_id_value := content_factory_private.require_uuid(
    p_payload, 'presenter_id'
  );

  update content_factory.generation_duet_presenters presenter
     set overlay_corner = coalesce(
           nullif(btrim(p_payload ->> 'overlay_corner'), ''),
           presenter.overlay_corner
         ),
         overlay_shape = coalesce(
           nullif(btrim(p_payload ->> 'overlay_shape'), ''),
           presenter.overlay_shape
         ),
         overlay_width_percent = coalesce(
           (p_payload ->> 'overlay_width_percent')::smallint,
           presenter.overlay_width_percent
         ),
         updated_at = now()
   where presenter.id = presenter_id_value
     and presenter.organization_id = org_id
     and presenter.project_id = proj_id
     and presenter.status = 'active'
  returning presenter.* into presenter_row;

  if presenter_row.id is null then
    raise exception using
      errcode = '22023', message = 'duet_presenter_not_found';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-duet-presenter-v1',
    'presenter', jsonb_build_object(
      'id', presenter_row.id,
      'display_name', presenter_row.display_name,
      'overlay_corner', presenter_row.overlay_corner,
      'overlay_shape', presenter_row.overlay_shape,
      'overlay_width_percent', presenter_row.overlay_width_percent
    )
  );
end;
$$;

revoke all on function public.creator_update_duet_presenter_layout(jsonb) from public;
grant execute on function public.creator_update_duet_presenter_layout(jsonb)
  to authenticated;

-- Серверное чтение личности отдаёт и раскладку: сборщику нужно и то и другое, а
-- два запроса за одним и тем же ведущим означали бы возможность их разойтись.
create or replace function content_factory_private.duet_presenter_identity(
  p_organization_id uuid,
  p_project_id uuid,
  p_presenter_id uuid
)
returns jsonb
language sql
stable
security definer
set search_path to ''
as $$
  select jsonb_build_object(
    'avatarId', presenter.provider_avatar_id,
    'voiceId', presenter.provider_voice_id,
    'aspectRatio', presenter.aspect_ratio,
    'layout', jsonb_build_object(
      'corner', presenter.overlay_corner,
      'shape', presenter.overlay_shape,
      'widthPercent', presenter.overlay_width_percent
    )
  )
  from content_factory.generation_duet_presenters presenter
  where presenter.id = p_presenter_id
    and presenter.organization_id = p_organization_id
    and presenter.project_id = p_project_id
    and presenter.status = 'active'
    and (
      presenter.likeness_kind <> 'real_person'
      or presenter.likeness_consent_confirmed
    );
$$;

revoke all on function content_factory_private.duet_presenter_identity(uuid, uuid, uuid)
  from public, anon, authenticated;

do $duet_layout_verify$
declare
  listing text;
begin
  -- Пределы совпадают с теми, что стоят в сборщике: расхождение означало бы
  -- раскладку, принятую базой и отвергнутую при сборке — то есть отказ уже
  -- после генерации ведущего, за которого заплачено.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_overlay_width_check'
      and pg_get_constraintdef(oid) like '%20%'
      and pg_get_constraintdef(oid) like '%50%'
  ) then
    raise exception using message = 'overlay_width_bounds_invalid';
  end if;

  listing := pg_get_functiondef(
    'public.creator_list_duet_presenters(jsonb)'::regprocedure
  );
  if position('overlay_corner' in listing) = 0 then
    raise exception using message = 'listing_hides_layout';
  end if;
  -- И по-прежнему не отдаёт личность у провайдера.
  if position('provider_avatar_id' in listing) > 0 then
    raise exception using message = 'duet_presenters_leak_avatar_id';
  end if;
end;
$duet_layout_verify$;

commit;

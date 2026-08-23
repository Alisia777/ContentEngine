begin;

-- 202608220009_duet_presenter_likeness_and_access_v1
--
-- Две правки по уточнению владельца 22.08.2026.
--
-- 1. ЗАВОДИТЬ ВЕДУЩЕГО МОЖЕТ И ОПЕРАТОР. Я закрыл регистрацию тремя ролями,
--    рассудив, что ведущий определяет лицо всех роликов. Владелец возразил:
--    команда справится. Роль возвращается — ограничение было моей
--    предосторожностью, а не требованием безопасности: деньги тратит не
--    регистрация, а запуск, и он по-прежнему требует подтверждения суммы.
--
-- 2. ВЕДУЩИЙ — ЖИВОЙ ЧЕЛОВЕК В 99% СЛУЧАЕВ. Это меняет вес согласия на
--    внешность. Раньше оно было галочкой на КАЖДОМ запуске: оператор
--    подтверждал согласие снова и снова, глядя на одну и ту же фотографию. Так
--    подтверждение превращается в ритуал — его перестают читать.
--
--    Согласие принадлежит ЧЕЛОВЕКУ, а не ролику. Поэтому оно записывается один
--    раз, вместе с ведущим: кто подтвердил и когда. Запускать ведущего без
--    записанного согласия нельзя вовсе — это проверяется ограничением, а не
--    памятью того, кто нажимал.
--
--    Полностью выдуманный персонаж (тот самый 1%) согласия не требует, и
--    требовать его от несуществующего человека было бы бессмыслицей. Поэтому у
--    ведущего есть вид: живой человек или синтетический персонаж.
--
--    Галочка на запуске при этом остаётся: она подтверждает, что ЭТОТ ролик
--    укладывается в то согласие. Одно не заменяет другое — запись говорит «право
--    есть», галочка говорит «применяю его здесь».

alter table content_factory.generation_duet_presenters
  add column if not exists likeness_kind text not null default 'real_person',
  add column if not exists likeness_consent_confirmed boolean not null default false,
  add column if not exists likeness_consent_confirmed_by uuid,
  add column if not exists likeness_consent_confirmed_at timestamptz;

do $duet_likeness_constraints$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_likeness_kind_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_likeness_kind_check
      check (likeness_kind = any (array['real_person', 'synthetic']));
  end if;

  -- Живой человек не может быть действующим ведущим без записанного согласия, и
  -- запись обязана называть, КТО его подтвердил и КОГДА. Согласие без имени
  -- подтвердившего — это не согласие, а утверждение без источника.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_likeness_consent_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_likeness_consent_check
      check (
        likeness_kind <> 'real_person'
        or status <> 'active'
        or (
          likeness_consent_confirmed
          and likeness_consent_confirmed_by is not null
          and likeness_consent_confirmed_at is not null
        )
      );
  end if;

  -- И обратное: отметка подтверждения без имени и времени невозможна в принципе,
  -- даже у синтетического персонажа и даже в архиве.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_consent_evidence_check'
  ) then
    alter table content_factory.generation_duet_presenters
      add constraint generation_duet_presenters_consent_evidence_check
      check (
        not likeness_consent_confirmed
        or (
          likeness_consent_confirmed_by is not null
          and likeness_consent_confirmed_at is not null
        )
      );
  end if;
end;
$duet_likeness_constraints$;

-- Регистрация: роль оператора возвращена, согласие принимается вместе с ведущим.
create or replace function public.creator_register_duet_presenter(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  display_name_value text;
  avatar_id_value text;
  voice_id_value text;
  aspect_ratio_value text := '9:16';
  make_default boolean := false;
  likeness_kind_value text := 'real_person';
  consent_value boolean := false;
  presenter_row content_factory.generation_duet_presenters;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if p_payload - array[
       'organization_id', 'project_id', 'display_name',
       'provider_avatar_id', 'provider_voice_id', 'aspect_ratio', 'is_default',
       'likeness_kind', 'likeness_consent_confirmed'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'duet_presenter_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  -- Оператор тоже заводит ведущего: денег регистрация не тратит, а запуск
  -- по-прежнему требует отдельного подтверждения суммы.
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );

  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );

  display_name_value := btrim(coalesce(p_payload ->> 'display_name', ''));
  avatar_id_value := btrim(coalesce(p_payload ->> 'provider_avatar_id', ''));
  voice_id_value := btrim(coalesce(p_payload ->> 'provider_voice_id', ''));
  if p_payload ? 'aspect_ratio' then
    aspect_ratio_value := btrim(coalesce(p_payload ->> 'aspect_ratio', ''));
  end if;
  if p_payload ? 'likeness_kind' then
    likeness_kind_value := btrim(coalesce(p_payload ->> 'likeness_kind', ''));
  end if;
  if p_payload ? 'is_default' then
    if jsonb_typeof(p_payload -> 'is_default') <> 'boolean' then
      raise exception using
        errcode = '22023', message = 'duet_presenter_payload_invalid';
    end if;
    make_default := (p_payload -> 'is_default')::text::boolean;
  end if;
  if p_payload ? 'likeness_consent_confirmed' then
    if jsonb_typeof(p_payload -> 'likeness_consent_confirmed') <> 'boolean' then
      raise exception using
        errcode = '22023', message = 'duet_presenter_payload_invalid';
    end if;
    consent_value := (p_payload -> 'likeness_consent_confirmed')::text::boolean;
  end if;

  -- Отказ называет причину прямо: живого человека нельзя завести без согласия,
  -- и молчаливое сохранение «неактивным» здесь было бы хуже отказа — человек
  -- решил бы, что ведущий готов.
  if likeness_kind_value = 'real_person' and not consent_value then
    raise exception using
      errcode = '22023', message = 'duet_presenter_likeness_consent_required';
  end if;

  if make_default then
    update content_factory.generation_duet_presenters
       set is_default = false, updated_at = now()
     where project_id = project_id_value
       and is_default
       and status = 'active';
  end if;

  insert into content_factory.generation_duet_presenters (
    organization_id, project_id, display_name,
    provider_avatar_id, provider_voice_id, aspect_ratio, is_default, created_by,
    likeness_kind, likeness_consent_confirmed,
    likeness_consent_confirmed_by, likeness_consent_confirmed_at
  )
  values (
    organization_id, project_id_value, display_name_value,
    avatar_id_value, voice_id_value, aspect_ratio_value, make_default, user_id,
    likeness_kind_value, consent_value,
    case when consent_value then user_id else null end,
    case when consent_value then now() else null end
  )
  returning * into presenter_row;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-duet-presenter-v1',
    'presenter', jsonb_build_object(
      'id', presenter_row.id,
      'display_name', presenter_row.display_name,
      'provider', presenter_row.provider,
      'aspect_ratio', presenter_row.aspect_ratio,
      'is_default', presenter_row.is_default,
      'likeness_kind', presenter_row.likeness_kind,
      'likeness_consent_confirmed', presenter_row.likeness_consent_confirmed,
      'created_at', presenter_row.created_at
    )
  );
end;
$$;

-- Витрина показывает вид ведущего: оператор должен видеть, что перед ним живой
-- человек, а не персонаж. Идентификаторы провайдера по-прежнему не отдаются.
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

-- Личность для платного запроса: живой человек без согласия сюда не попадает
-- вовсе. Это последняя преграда — даже если строка каким-то образом оказалась
-- действующей, запрос ею не соберётся.
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
    'aspectRatio', presenter.aspect_ratio
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

do $duet_likeness_verify$
declare
  identity_definition text;
  register_definition text;
begin
  identity_definition := pg_get_functiondef(
    'content_factory_private.duet_presenter_identity(uuid,uuid,uuid)'::regprocedure
  );
  register_definition := pg_get_functiondef(
    'public.creator_register_duet_presenter(jsonb)'::regprocedure
  );

  -- Оператор снова может заводить ведущего.
  if position('''operator''' in register_definition) = 0 then
    raise exception using message = 'operator_cannot_register_presenter';
  end if;

  -- Живой человек без согласия не доходит до платного запроса.
  if position('presenter.likeness_consent_confirmed' in identity_definition) = 0
  then
    raise exception using message = 'identity_ignores_likeness_consent';
  end if;

  -- Идентификаторы провайдера по-прежнему не покидают сервер.
  if position('provider_avatar_id' in pg_get_functiondef(
       'public.creator_list_duet_presenters(jsonb)'::regprocedure
     )) > 0 then
    raise exception using message = 'duet_presenters_leak_avatar_id';
  end if;

  -- И согласие невозможно записать без имени подтвердившего.
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_consent_evidence_check'
  ) then
    raise exception using message = 'consent_evidence_constraint_missing';
  end if;
end;
$duet_likeness_verify$;

commit;

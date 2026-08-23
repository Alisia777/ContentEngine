begin;

-- 202608220010_duet_presenter_synthetic_by_default_v1
--
-- ИСПРАВЛЕНИЕ МОЕЙ ОШИБКИ ЧТЕНИЯ. В 202608220009 я поставил умолчанием
-- 'real_person' и потребовал согласия на внешность при заведении каждого
-- ведущего.
--
-- Основанием была фраза владельца «99% это будет живой человек (модель)».
-- Я прочитал её как «нанятая живая модель, чьё лицо мы используем». Владелец
-- уточнил 22.08.2026: имелась в виду ИИ-МОДЕЛЬ В ОБЛИКЕ ЧЕЛОВЕКА — говорящая
-- голова, сгенерированный персонаж. Живого человека за ней нет.
--
-- Значит умолчание было ровно обратным правде, и оно дорого стоило бы: каждое
-- заведение ведущего требовало бы подтверждать согласие несуществующего
-- человека. Подтверждение, которое нельзя не поставить, перестаёт что-либо
-- значить — и обесценивает те случаи, где согласие действительно нужно.
--
-- ЧТО МЕНЯЕТСЯ: умолчание становится 'synthetic'. Заведение говорящей головы
-- больше ничего не требует.
--
-- ЧТО ОСТАЁТСЯ И ПОЧЕМУ. Вид 'real_person' и требование согласия к нему никуда
-- не деваются. Настоящий человек в этой роли — редкий, но возможный случай:
-- сотрудник компании, приглашённый эксперт, сам владелец. Для него согласие на
-- внешность обязательно, и именно потому, что случай редкий, проверка должна
-- быть машинной, а не памятью того, кто заводил.

alter table content_factory.generation_duet_presenters
  alter column likeness_kind set default 'synthetic';

-- Регистрация: умолчание синтетическое, согласие требуется только у настоящего
-- человека. Отказ по-прежнему называет причину прямо.
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
  -- Умолчание — говорящая голова: сгенерированный персонаж, живого человека за
  -- ним нет. Это подавляющее большинство ведущих.
  likeness_kind_value text := 'synthetic';
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

  -- Согласие спрашивается ТОЛЬКО когда за ведущим стоит настоящий человек.
  -- Заведение говорящей головы не требует ничего: подтверждение, которое нельзя
  -- не поставить, перестаёт что-либо значить.
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

do $duet_synthetic_verify$
declare
  register_definition text;
  default_value text;
begin
  select column_default into default_value
  from information_schema.columns
  where table_schema = 'content_factory'
    and table_name = 'generation_duet_presenters'
    and column_name = 'likeness_kind';
  if default_value is null or position('synthetic' in default_value) = 0 then
    raise exception using message =
      'likeness_kind_default_not_synthetic:' || coalesce(default_value, '<null>');
  end if;

  register_definition := pg_get_functiondef(
    'public.creator_register_duet_presenter(jsonb)'::regprocedure
  );
  if position('likeness_kind_value text := ''synthetic''' in register_definition) = 0
  then
    raise exception using message = 'register_default_not_synthetic';
  end if;

  -- Требование согласия к настоящему человеку сохранено: редкий случай, но
  -- именно поэтому проверка машинная, а не на памяти заводившего.
  if position('duet_presenter_likeness_consent_required' in register_definition) = 0
  then
    raise exception using message = 'real_person_consent_guard_lost';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'generation_duet_presenters_likeness_consent_check'
  ) then
    raise exception using message = 'likeness_consent_constraint_lost';
  end if;
end;
$duet_synthetic_verify$;

commit;

begin;

-- 202608220008_generation_duet_presenters_v1
--
-- Библиотека ведущих проекта для формата «Дуэт».
--
-- ЗАЧЕМ ОТДЕЛЬНАЯ СУЩНОСТЬ, А НЕ ПОЛЕ В ФОРМЕ. Формат живёт узнаваемостью: один
-- и тот же человек комментирует все ролики проекта. Если бы `avatar_id` приходил
-- из формы, оператор мог бы подставить в оплачиваемый запрос что угодно — и
-- ошибкой, и намеренно. Ведущий заводится один раз, лежит здесь, а форма только
-- ВЫБИРАЕТ из списка. Тот же принцип, по которому область замены у «Копии»
-- выводится из проверенной сервером категории, а не из операторского текста.
--
-- ПОЧЕМУ ИДЕНТИФИКАТОРЫ ХРАНЯТСЯ, А НЕ ВЫЧИСЛЯЮТСЯ. HeyGen создаёт аватара на
-- своей стороне за отдельные деньги ($1.00 за вызов) и возвращает avatar_id.
-- Этот идентификатор — единственное, что связывает наши ролики с одной и той же
-- внешностью. Потеряв его, восстановить того же человека нельзя: новая
-- генерация даст похожего, но другого.
--
-- ЧТО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Она не создаёт аватаров у провайдера и не тратит
-- денег: только заводит место, где хранится уже созданный. Сам платный вызов
-- создания — отдельная работа.

create table if not exists content_factory.generation_duet_presenters (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  -- Что видит оператор в списке. Провайдерские идентификаторы человеку не
  -- показываются: они непрозрачны и ни о чём не говорят.
  display_name text not null,
  -- Провайдер назван явно, хотя сейчас он один: ведущий у другого провайдера
  -- будет другой сущностью с другими полями, и молчаливое переиспользование
  -- этой строки увело бы запрос не туда.
  provider text not null default 'heygen',
  -- Личность и голос, закреплённые на стороне провайдера.
  provider_avatar_id text not null,
  provider_voice_id text not null,
  -- Рамка самого ведущего. Он встаёт в угол чужого кадра, поэтому почти всегда
  -- вертикальная или квадратная.
  aspect_ratio text not null default '9:16',
  status text not null default 'active',
  is_default boolean not null default false,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint generation_duet_presenters_provider_check
    check (provider = 'heygen'),
  constraint generation_duet_presenters_display_name_check
    check (
      btrim(display_name) = display_name
      and length(display_name) between 1 and 80
      and display_name !~ '[[:cntrl:]]'
    ),
  -- Идентификаторы провайдера непрозрачны: проверяем не смысл, а границы.
  constraint generation_duet_presenters_avatar_id_check
    check (
      btrim(provider_avatar_id) = provider_avatar_id
      and provider_avatar_id ~ '^[A-Za-z0-9_-]{8,128}$'
    ),
  constraint generation_duet_presenters_voice_id_check
    check (
      btrim(provider_voice_id) = provider_voice_id
      and provider_voice_id ~ '^[A-Za-z0-9_-]{4,128}$'
    ),
  constraint generation_duet_presenters_aspect_ratio_check
    check (aspect_ratio = any (array['16:9', '9:16', '1:1'])),
  constraint generation_duet_presenters_status_check
    check (status = any (array['active', 'archived']))
);

-- Один и тот же ведущий не заводится в проекте дважды.
create unique index if not exists generation_duet_presenters_identity_key
  on content_factory.generation_duet_presenters (
    project_id, provider, provider_avatar_id, provider_voice_id
  );

-- Ведущий по умолчанию у проекта ровно один. Частичный индекс: архивные и
-- обычные строки друг другу не мешают.
create unique index if not exists generation_duet_presenters_default_key
  on content_factory.generation_duet_presenters (project_id)
  where is_default and status = 'active';

create index if not exists generation_duet_presenters_project_idx
  on content_factory.generation_duet_presenters (project_id, status, created_at desc);

-- Таблица закрыта полностью: политик нет, весь доступ идёт через функции ниже.
-- Это тот же приём, что и у остальных таблиц контура генерации.
alter table content_factory.generation_duet_presenters enable row level security;
alter table content_factory.generation_duet_presenters force row level security;
revoke all on content_factory.generation_duet_presenters from anon, authenticated;

-- Список ведущих проекта. Идентификаторы провайдера НЕ отдаются наружу: браузеру
-- они не нужны — он выбирает ведущего по нашему id, а подставлять чужой
-- avatar_id в платный запрос он не должен уметь в принципе.
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

-- Регистрация уже созданного у провайдера ведущего. Создание самого аватара
-- здесь не происходит: это платный вызов на стороне HeyGen, и он живёт отдельно.
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
  presenter_row content_factory.generation_duet_presenters;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if p_payload - array[
       'organization_id', 'project_id', 'display_name',
       'provider_avatar_id', 'provider_voice_id', 'aspect_ratio', 'is_default'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'duet_presenter_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  -- Заводить ведущего — решение уровня проекта, а не рядового исполнителя:
  -- он определяет лицо всех роликов и стоит денег у провайдера.
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
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
  if p_payload ? 'is_default' then
    if jsonb_typeof(p_payload -> 'is_default') <> 'boolean' then
      raise exception using
        errcode = '22023', message = 'duet_presenter_payload_invalid';
    end if;
    make_default := (p_payload -> 'is_default')::text::boolean;
  end if;

  -- Ведущий по умолчанию у проекта один: прежний уступает место новому в той же
  -- транзакции, иначе частичный уникальный индекс отверг бы вставку и человек
  -- увидел бы отказ вместо смены ведущего.
  if make_default then
    update content_factory.generation_duet_presenters
       set is_default = false, updated_at = now()
     where project_id = project_id_value
       and is_default
       and status = 'active';
  end if;

  insert into content_factory.generation_duet_presenters (
    organization_id, project_id, display_name,
    provider_avatar_id, provider_voice_id, aspect_ratio, is_default, created_by
  )
  values (
    organization_id, project_id_value, display_name_value,
    avatar_id_value, voice_id_value, aspect_ratio_value, make_default, user_id
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
      'created_at', presenter_row.created_at
    )
  );
end;
$$;

revoke all on function public.creator_list_duet_presenters(jsonb) from public;
revoke all on function public.creator_register_duet_presenter(jsonb) from public;
grant execute on function public.creator_list_duet_presenters(jsonb) to authenticated;
grant execute on function public.creator_register_duet_presenter(jsonb) to authenticated;

-- Личность ведущего для платного запроса читается ТОЛЬКО серверным кодом.
-- Отдельная функция, недоступная браузеру: именно она отдаёт avatar_id и
-- voice_id, и то лишь по нашему внутреннему идентификатору ведущего.
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
    and presenter.status = 'active';
$$;

revoke all on function content_factory_private.duet_presenter_identity(uuid, uuid, uuid)
  from public, anon, authenticated;

do $duet_presenters_verify$
begin
  if not exists (
    select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'content_factory'
      and c.relname = 'generation_duet_presenters'
      and c.relrowsecurity and c.relforcerowsecurity
  ) then
    raise exception using message = 'duet_presenters_rls_not_forced';
  end if;

  -- Ни одной политики: доступ только через функции. Появившаяся политика
  -- означала бы прямой доступ браузера к идентификаторам провайдера.
  if exists (
    select 1 from pg_policy
    where polrelid = 'content_factory.generation_duet_presenters'::regclass
  ) then
    raise exception using message = 'duet_presenters_policy_present';
  end if;

  -- Витрина не отдаёт идентификаторы провайдера наружу.
  if position('provider_avatar_id' in pg_get_functiondef(
       'public.creator_list_duet_presenters(jsonb)'::regprocedure
     )) > 0 then
    raise exception using message = 'duet_presenters_leak_avatar_id';
  end if;
  if position('provider_voice_id' in pg_get_functiondef(
       'public.creator_list_duet_presenters(jsonb)'::regprocedure
     )) > 0 then
    raise exception using message = 'duet_presenters_leak_voice_id';
  end if;

  -- Серверная функция личности недоступна роли браузера.
  if has_function_privilege(
       'authenticated',
       'content_factory_private.duet_presenter_identity(uuid,uuid,uuid)',
       'execute'
     ) then
    raise exception using message = 'duet_presenter_identity_reachable_by_browser';
  end if;
end;
$duet_presenters_verify$;

commit;

begin;
-- 202608240003_strategy_review_inbox_v1
--
-- Владелица (24.08.2026): «форма проверить — туда чтобы падали ролики-черновики;
-- я как оператор вижу свои ролики: либо отвергнуть, либо принять и разместить;
-- как админ вижу все ролики. В команде — вкладка по аккаунтам и подключениям».
--
--   1. creator_content_review_catalog — существующая обёртка каталога проверок
--      дополняется фактами файла (lifecycle_stage, artifact_class, owner_name):
--      браузер строит очередь «Ролики на проверке» из тех же данных, без
--      второго источника правды. Область видимости прежняя: operator — свои,
--      owner/admin/producer/reviewer — все.
--   2. creator_reject_generation_result — «Отвергнуть»: подтверждение полного
--      просмотра + причина; отказ записывается в metadata.rejection и событие,
--      а сам файл уезжает в «Корзину» существующим контуром
--      workspace_trash_items (восстановим, ничего не стирается).
--   3. creator_team_accounts — витрина вкладки «Команда → Аккаунты»:
--      активные аккаунты реестра с хранителем, выдачами, статусом подключения
--      и счётчиками размещений. Без регистрационных реквизитов —
--      они остаются в админке «Люди → Аккаунты».

-- 1. Каталог проверок: факты файла для очереди -------------------------------

create or replace function public.creator_content_review_catalog(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  project_id_value uuid;
  result_value jsonb;
  media_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);

  -- Делегируем вглубь: валидация payload, роли, явный ACL проекта, пагинация
  -- и все прежние обогащения ответа остаются там, где были реализованы.
  result_value :=
    content_factory_private.creator_content_review_catalog_pre_media_status(
      p_payload
    );

  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );

  select coalesce(
    jsonb_agg(
      item.value || jsonb_build_object(
        'status', media.status,
        'product_id', media.product_id,
        'lifecycle_stage', media.lifecycle_stage,
        'artifact_class', media.artifact_class,
        'owner_name', coalesce(owner_profile.display_name, owner_profile.email)
      )
      order by item.ordinality
    ),
    '[]'::jsonb
  )
  into media_value
  from jsonb_array_elements(
    coalesce(result_value -> 'media', '[]'::jsonb)
  ) with ordinality item(value, ordinality)
  join content_factory.media_objects media
    on media.organization_id = organization_id_value
   and media.project_id = project_id_value
   and media.id::text = item.value ->> 'id'
   and media.status = 'ready'
  left join content_factory.profiles owner_profile
    on owner_profile.id = media.owner_id;

  return result_value || jsonb_build_object('media', media_value);
end;
$$;

revoke all on function public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_catalog(jsonb)
  to authenticated;

comment on function public.creator_content_review_catalog(jsonb) is
  'Project-scoped content-review catalog: authoritative media status, product identity, lifecycle stage and owner display name.';

-- 2. «Отвергнуть» готовый результат ------------------------------------------

create or replace function public.creator_reject_generation_result(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid;
  organization_id uuid;
  project_id uuid;
  media_id uuid;
  actor_role text;
  manager_scope boolean;
  reason_value text;
  idempotency_key text;
  canonical_payload jsonb;
  replay jsonb;
  media_row content_factory.media_objects%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id := content_factory_private.current_profile_id();
  if p_payload - array[
       'organization_id', 'project_id', 'media_id', 'reason',
       'watch_confirmed', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'media_id', 'reason', 'watch_confirmed',
       'idempotency_key'
     ]::text[] then
    raise exception using errcode = '22023',
      message = 'reject_result_payload_invalid';
  end if;
  -- Отказ — тоже решение после просмотра: literal true, не молчаливый дефолт.
  if p_payload -> 'watch_confirmed' is distinct from 'true'::jsonb then
    raise exception using errcode = '22023',
      message = 'reject_result_watch_confirmation_required';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  -- Как и в «Одобрить и разместить» (202608240001): достаточно активного
  -- членства — отказ не строже одобрения. Область — менеджеры или свой файл.
  select member.role into actor_role
  from content_factory.memberships member
  where member.organization_id = organization_id
    and member.profile_id = actor_id
    and member.status = 'active';
  if actor_role is null then
    raise exception using errcode = '42501', message = 'membership_required';
  end if;
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  project_id := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    organization_id, project_id
  );
  media_id := content_factory_private.require_project_entity(
    organization_id, project_id, 'media',
    content_factory_private.require_uuid(p_payload, 'media_id')
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 5, 500
  );
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  canonical_payload := p_payload || jsonb_build_object(
    'organization_id', organization_id
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_reject_generation_result',
    idempotency_key,
    canonical_payload
  );
  if replay is not null then
    return replay;
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id and media.id = media_id
  for update;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'generated_video' then
    raise exception using errcode = '55000',
      message = 'reject_result_media_not_generated_video';
  end if;
  if media_row.lifecycle_stage = 'published' then
    raise exception using errcode = '55000',
      message = 'reject_result_media_already_published';
  end if;
  if media_row.status <> 'ready' then
    raise exception using errcode = '55000',
      message = 'reject_result_media_unavailable';
  end if;
  -- Оператор отвергает только свои ролики; расширенная область — менеджерская.
  if not (manager_scope or media_row.owner_id = actor_id) then
    raise exception using errcode = '42501',
      message = 'reject_result_scope_denied';
  end if;

  -- Причина остаётся на самом файле: и в корзине, и после восстановления
  -- видно, кто и почему отверг именно эту версию (sha256 зафиксирован).
  update content_factory.media_objects media
  set metadata = media.metadata || jsonb_build_object(
        'rejection', jsonb_build_object(
          'reason', reason_value,
          'rejected_by', actor_id,
          'rejected_at', now(),
          'media_sha256', media_row.sha256
        )
      ),
      updated_at = now()
  where media.organization_id = organization_id and media.id = media_id;

  -- Файл уезжает в «Корзину» существующим контуром (202607310101 вынес его в
  -- собственное пространство имён workspace_*): снимок места, статус deleted,
  -- восстановление и плановая очистка хранилища уже реализованы там.
  perform public.workspace_trash_items(jsonb_build_object(
    'organization_id', organization_id,
    'idempotency_key', 'strategy-reject-trash:' || media_id::text,
    'items', jsonb_build_array(
      jsonb_build_object('type', 'media', 'id', media_id)
    )
  ));

  perform content_factory_private.emit_event(
    organization_id,
    actor_id,
    'generation_result_rejected',
    'media',
    media_id::text,
    jsonb_build_object(
      'reason', reason_value,
      'lifecycle_stage', media_row.lifecycle_stage,
      'generation_job_id', media_row.metadata ->> 'generation_job_id'
    ),
    'strategy-reject:' || idempotency_key,
    'server_rpc'
  );

  return content_factory_private.finish_command(
    organization_id,
    actor_id,
    'creator_reject_generation_result',
    idempotency_key,
    canonical_payload,
    jsonb_build_object(
      'ok', true,
      'version', 'reject-generation-result-v1',
      'media_id', media_id,
      'trashed', true
    )
  );
end;
$$;

revoke all on function public.creator_reject_generation_result(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_reject_generation_result(jsonb)
  to authenticated, service_role;

comment on function public.creator_reject_generation_result(jsonb) is
  'Оператор отверг просмотренный результат генерации: причина в metadata.rejection + событие, файл в «Корзине» через workspace_trash_items.';

-- 3. Витрина «Команда → Аккаунты» --------------------------------------------

create or replace function public.creator_team_accounts(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  accounts jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023',
      message = 'team_accounts_payload_invalid';
  end if;
  organization_id := content_factory_private.resolve_organization(p_payload);
  -- Витрина — управленческая: состав выдач и траты видит руководство.
  -- Регистрационные реквизиты сюда не попадают вовсе.
  if not exists (
    select 1
    from content_factory.memberships member
    where member.organization_id = organization_id
      and member.profile_id = content_factory_private.current_profile_id()
      and member.status = 'active'
      and member.role = any(array['owner', 'admin', 'producer', 'reviewer'])
  ) then
    raise exception using errcode = '42501',
      message = 'team_accounts_role_denied';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', account.id,
    'platform', account.platform,
    'label', account.label,
    'handle', account.handle,
    'url', account.url,
    'ownership_kind', account.ownership_kind,
    'posting_mode', account.posting_mode,
    'connection_status', account.connection_status,
    'custodian_name', coalesce(custodian.display_name, custodian.email),
    'assignees', coalesce(assignment_list.names, '[]'::jsonb),
    'placements_total', coalesce(stats.total, 0),
    'placements_published', coalesce(stats.published, 0),
    'last_published_at', stats.last_published_at
  ) order by account.platform, account.label), '[]'::jsonb)
    into accounts
  from content_factory.managed_accounts account
  left join content_factory.profiles custodian
    on custodian.id = account.custodian_profile_id
  left join lateral (
    select jsonb_agg(
      coalesce(member_profile.display_name, member_profile.email)
      order by coalesce(member_profile.display_name, member_profile.email)
    ) as names
    from content_factory.member_account_assignments assignment
    join content_factory.profiles member_profile
      on member_profile.id = assignment.profile_id
    where assignment.organization_id = account.organization_id
      and assignment.account_id = account.id
      and assignment.status = 'active'
  ) assignment_list on true
  left join lateral (
    select
      count(*) as total,
      count(*) filter (where placement.status = 'published') as published,
      max(placement.published_at) as last_published_at
    from content_factory.placements placement
    where placement.organization_id = account.organization_id
      and placement.managed_account_id = account.id
  ) stats on true
  where account.organization_id = organization_id
    and account.status = 'active';

  return jsonb_build_object(
    'ok', true,
    'version', 'team-accounts-v1',
    'accounts', accounts
  );
end;
$$;

revoke all on function public.creator_team_accounts(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_team_accounts(jsonb)
  to authenticated, service_role;

comment on function public.creator_team_accounts(jsonb) is
  'Вкладка «Команда → Аккаунты»: реестр владения с хранителями, выдачами, статусом подключения и счётчиками размещений; без регистрационных реквизитов.';

notify pgrst, 'reload schema';

commit;

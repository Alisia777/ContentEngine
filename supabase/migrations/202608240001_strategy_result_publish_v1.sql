begin;
-- 202608240001_strategy_result_publish_v1
--
-- Оператор посмотрел готовый ролик стратегии и «окнул» — дальше он должен
-- размещать, не выкапывая файл руками. Этот шаг соединяет готовый результат
-- генерации с существующим контуром размещения (задача 'placement' +
-- строка placements + creator_confirm_placement финальной ссылкой):
--
--   1. creator_publishing_accounts — активные аккаунты компании из реестра
--      (фаза 0, 202608230024) для формы «Разместить»: куда физически можно
--      публиковать и в каком режиме (api / assisted).
--   2. creator_publish_generation_result — «Одобрить и разместить»: явное
--      подтверждение просмотра (watch_confirmed) + выданный аккаунт + ERID
--      создают задачу размещения и строку placements идемпотентно. Публикацию
--      подтверждает существующий creator_confirm_placement (финальный URL).
--
-- Обе функции — прямые public RPC по образцу creator_list_duet_presenters
-- (202608220008): реестр v47-обёрток закрыт списком и не расширяется отсюда.
--
-- ERID обязателен решением владельца (24.08.2026): маркировка рекламы. Для
-- немаркируемой органики оператор явно пишет ORGANIC — поле не может быть
-- пустым молча.

-- 1. Список аккаунтов для формы размещения ------------------------------------

create or replace function public.creator_publishing_accounts(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid;
  organization_id uuid;
  project_id_value uuid;
  accounts jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id := content_factory_private.current_profile_id();
  if p_payload - array['organization_id', 'project_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023',
      message = 'publishing_accounts_payload_invalid';
  end if;
  organization_id := content_factory_private.resolve_organization(p_payload);
  if not exists (
    select 1
    from content_factory.memberships member
    where member.organization_id = organization_id
      and member.profile_id = actor_id
      and member.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'membership_required';
  end if;
  if p_payload ? 'project_id' then
    project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
    perform content_factory_private.require_workspace_project(
      organization_id, project_id_value
    );
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
    'custodian_name', custodian.display_name
  ) order by account.platform, account.label), '[]'::jsonb)
    into accounts
  from content_factory.managed_accounts account
  left join content_factory.profiles custodian
    on custodian.id = account.custodian_profile_id
  where account.organization_id = organization_id
    and account.status = 'active'
    and account.posting_mode <> 'disabled';

  return jsonb_build_object(
    'ok', true,
    'version', 'publishing-accounts-v1',
    'accounts', accounts
  );
end;
$$;

revoke all on function public.creator_publishing_accounts(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_publishing_accounts(jsonb)
  to authenticated, service_role;

-- 2. «Одобрить и разместить» готовый результат ---------------------------------

create or replace function public.creator_publish_generation_result(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid;
  organization_id uuid;
  project_id uuid;
  job_id uuid;
  media_id uuid;
  account_id uuid;
  erid_value text;
  note_value text;
  idempotency_key text;
  canonical_payload jsonb;
  replay jsonb;
  job_row content_factory.generation_jobs%rowtype;
  media_row content_factory.media_objects%rowtype;
  account_row content_factory.managed_accounts%rowtype;
  destination_value text;
  task_id_value uuid;
  placement_row content_factory.placements%rowtype;
  watch_ack jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id := content_factory_private.current_profile_id();
  if p_payload - array[
       'organization_id', 'project_id', 'generation_job_id', 'media_id',
       'managed_account_id', 'erid', 'note', 'watch_confirmed',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'media_id', 'managed_account_id',
       'erid', 'watch_confirmed', 'idempotency_key'
     ]::text[] then
    raise exception using errcode = '22023',
      message = 'publish_result_payload_invalid';
  end if;
  -- «Окнул» — это действие: без явного подтверждения полного просмотра
  -- размещение не создаётся. Поле обязано быть literal true.
  if p_payload -> 'watch_confirmed' is distinct from 'true'::jsonb then
    raise exception using errcode = '22023',
      message = 'publish_result_watch_confirmation_required';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  if not exists (
    select 1
    from content_factory.memberships member
    where member.organization_id = organization_id
      and member.profile_id = actor_id
      and member.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'membership_required';
  end if;
  project_id := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    organization_id, project_id
  );
  media_id := content_factory_private.require_project_entity(
    organization_id, project_id, 'media',
    content_factory_private.require_uuid(p_payload, 'media_id')
  );
  -- Задача выводится из САМОГО результата: браузерная проекция «Файлов» не
  -- несёт generation_job_id, а два независимых идентификатора в форме — это
  -- два способа разойтись. Явно присланный job обязан совпасть с выведенным.
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id and media.id = media_id;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'generated_video' then
    raise exception using errcode = '55000',
      message = 'publish_result_media_not_generated_video';
  end if;
  begin
    job_id := nullif(media_row.metadata ->> 'generation_job_id', '')::uuid;
  exception when others then
    job_id := null;
  end;
  if job_id is null then
    raise exception using errcode = '55000',
      message = 'publish_result_media_job_unknown';
  end if;
  if p_payload ? 'generation_job_id'
     and content_factory_private.require_uuid(p_payload, 'generation_job_id')
       is distinct from job_id then
    raise exception using errcode = '55000',
      message = 'publish_result_media_job_mismatch';
  end if;
  perform content_factory_private.require_project_entity(
    organization_id, project_id, 'job', job_id
  );
  account_id := content_factory_private.require_uuid(p_payload, 'managed_account_id');
  erid_value := upper(content_factory_private.require_text(p_payload, 'erid', 4, 64));
  if erid_value !~ '^[A-Z0-9-]{4,64}$' then
    raise exception using errcode = '22023', message = 'publish_result_erid_invalid';
  end if;
  note_value := content_factory_private.admin_optional_text(p_payload, 'note', 1, 500);
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  canonical_payload := p_payload || jsonb_build_object(
    'organization_id', organization_id, 'erid', erid_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_publish_generation_result',
    idempotency_key,
    canonical_payload
  );
  if replay is not null then
    return replay;
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id and job.id = job_id
  for update;
  if job_row.status <> 'succeeded' then
    raise exception using errcode = '55000',
      message = 'publish_result_job_not_succeeded';
  end if;
  select account.* into account_row
  from content_factory.managed_accounts account
  where account.organization_id = organization_id and account.id = account_id
  for update;
  if account_row.id is null or account_row.status <> 'active' then
    raise exception using errcode = '55000',
      message = 'publish_result_account_unavailable';
  end if;
  if account_row.posting_mode = 'disabled' then
    raise exception using errcode = '55000',
      message = 'publish_result_account_posting_disabled';
  end if;
  destination_value := coalesce(
    nullif(account_row.handle, ''), nullif(account_row.url, ''), account_row.label
  );

  watch_ack := jsonb_build_object(
    'confirmed', true,
    'confirmed_by', actor_id,
    'confirmed_at', now(),
    'media_id', media_id,
    'media_sha256', media_row.sha256
  );

  -- Задача размещения — тот же тип 'placement', которым живёт весь контур:
  -- она появляется в «Моих работах» исполнителя, а подтверждение финальной
  -- ссылкой делает существующий creator_confirm_placement.
  select task.id into task_id_value
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.idempotency_key = 'strategy-placement-task:' || job_id::text
      || ':' || account_id::text;
  if task_id_value is null then
    insert into content_factory.creator_tasks (
      organization_id, project_id, assignee_id, created_by, product_id,
      generation_job_id, task_type, title, instructions,
      status, priority, payout_minor, result, idempotency_key
    ) values (
      organization_id,
      project_id,
      actor_id,
      actor_id,
      job_row.product_id,
      job_id,
      'placement',
      left('Разместить ролик — ' || coalesce(
        account_row.label, account_row.handle, account_row.platform
      ), 240),
      'Опубликуйте одобренный ролик на выданном аккаунте. Маркировка: ERID '
        || erid_value
        || '. После публикации добавьте финальную HTTPS-ссылку в подтверждение.',
      'todo',
      2,
      0,
      jsonb_build_object(
        'source_media_id', media_id,
        'media_sha256', media_row.sha256,
        'platform', account_row.platform,
        'destination_ref', destination_value,
        'managed_account_id', account_id,
        'erid', erid_value,
        'note', note_value,
        'watch_ack', watch_ack,
        'content_kind', 'video'
      ),
      'strategy-placement-task:' || job_id::text || ':' || account_id::text
    )
    returning id into task_id_value;
  end if;

  insert into content_factory.placements (
    organization_id, project_id, product_id, generation_job_id, task_id,
    assigned_to, created_by, platform, destination_ref, status,
    managed_account_id, request_hash, idempotency_key, metadata
  ) values (
    organization_id,
    project_id,
    job_row.product_id,
    job_id,
    task_id_value,
    actor_id,
    actor_id,
    account_row.platform,
    destination_value,
    'ready',
    account_id,
    content_factory_private.json_hash(canonical_payload),
    'strategy-placement:' || job_id::text || ':' || account_id::text,
    jsonb_build_object(
      'source_media_id', media_id,
      'media_sha256', media_row.sha256,
      'erid', erid_value,
      'note', note_value,
      'media_watched_confirmed', true,
      'watch_ack', watch_ack,
      'content_kind', 'video'
    )
  )
  on conflict on constraint placements_organization_id_idempotency_key_key
  do update set updated_at = now()
  returning * into placement_row;

  -- Одобренный и отправленный на размещение результат — больше не черновик:
  -- в «Файлах» карточка переезжает в «Результаты · Готово». Опубликованный
  -- этап поставит подтверждение финальной ссылки.
  update content_factory.media_objects media
  set lifecycle_stage = 'ready', updated_at = now()
  where media.organization_id = organization_id
    and media.id = media_id
    and media.lifecycle_stage in ('drafts', 'review');

  perform content_factory_private.emit_event(
    organization_id,
    actor_id,
    'generation_result_sent_to_placement',
    'placement',
    placement_row.id::text,
    jsonb_build_object(
      'generation_job_id', job_id,
      'managed_account_id', account_id,
      'platform', account_row.platform,
      'erid', erid_value
    ),
    'strategy-placement:' || idempotency_key,
    'server_rpc'
  );

  return content_factory_private.finish_command(
    organization_id,
    actor_id,
    'creator_publish_generation_result',
    idempotency_key,
    canonical_payload,
    jsonb_build_object(
      'ok', true,
      'version', 'publish-generation-result-v1',
      'placement', jsonb_build_object(
        'id', placement_row.id,
        'task_id', task_id_value,
        'status', placement_row.status,
        'platform', placement_row.platform,
        'destination_ref', placement_row.destination_ref,
        'managed_account_id', account_id,
        'erid', erid_value
      )
    )
  );
end;
$$;

revoke all on function public.creator_publish_generation_result(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_publish_generation_result(jsonb)
  to authenticated, service_role;

commit;

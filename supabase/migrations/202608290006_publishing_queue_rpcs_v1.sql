begin;
-- 202608290006_publishing_queue_rpcs_v1
--
-- Фаза 1 контура публикаций, шаги 1б и 1в (ТЗ
-- docs/PUBLISHING_ACCOUNTS_CONTOUR_2026-08-23.md §5.3, §5.5, §8).
--
-- Постановка в очередь из паспорта/размещения (creator_*), воркерные
-- claim/complete (system_*, задел фазы 2: сейчас claim всегда пуст —
-- api-аккаунтов с подключением не существует, OAuth не строим) и чистый
-- SQL-диспетчер assisted-режима: наступившее время переводит
-- queued → manual_required и кладёт уведомление в notification_outbox
-- (contract v1, по образцу enqueue_terminal_notification). Диспетчера зовёт
-- pg_cron раз в минуту; установка расписания — тем же do-блоком, что job 206
-- (202607170001:353-380). Денег контур не тратит и наружу не ходит.
--
-- Финал фазы 1: задача в manual_required с готовой подписью (маркировка
-- внутри); человек размещает руками и жмёт существующий
-- creator_confirm_placement — тот принимает размещения в статусах
-- ('scheduled','ready'), перевод 'ready'→'scheduled' при постановке проверен
-- по проду и подтверждение не ломает.

-- Единая точка перевода в ручной режим: диспетчер (по времени) и complete
-- (по отказу токена) обязаны оставлять одинаковый след и одинаковые
-- уведомления исполнителю и хранителю аккаунта. Секретов нет по построению.
create or replace function content_factory_private.publishing_mark_manual_required(
  p_job_id uuid,
  p_reason text
)
returns boolean
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  job_row content_factory.publishing_jobs%rowtype;
  account_row content_factory.managed_accounts%rowtype;
  reason_value text;
  title_value text;
  body_value text;
  recipient_id_value uuid;
  request_hash_value text;
begin
  reason_value := lower(coalesce(nullif(btrim(p_reason), ''),
    'assisted_mode_due'));
  if reason_value !~ '^[a-z][a-z0-9_]{2,99}$' then
    reason_value := 'assisted_mode_due';
  end if;

  select job.* into job_row
  from content_factory.publishing_jobs job
  where job.id = p_job_id
    and job.status in ('queued', 'claimed', 'uploading')
  for update;
  if job_row.id is null then
    return false;
  end if;

  update content_factory.publishing_jobs job
  set status = 'manual_required',
      manual_required_at = now(),
      lease_token = null,
      leased_until = null,
      last_error_code = reason_value,
      updated_at = now()
  where job.id = job_row.id
  returning * into job_row;

  insert into content_factory.publishing_job_events (
    organization_id, job_id, event, payload, actor
  ) values (
    job_row.organization_id, job_row.id, 'manual_required',
    jsonb_build_object(
      'reason', reason_value,
      'scheduled_at', job_row.scheduled_at,
      'platform', job_row.platform
    ),
    'dispatcher'
  );

  select account.* into account_row
  from content_factory.managed_accounts account
  where account.organization_id = job_row.organization_id
    and account.id = job_row.managed_account_id;

  title_value := 'Пора разместить вручную';
  body_value := 'Назначенное время публикации наступило. Аккаунт «'
    || coalesce(account_row.label, job_row.platform)
    || '» публикуется в ручном режиме: откройте размещение, скачайте ролик, '
    || 'опубликуйте с готовой подписью (маркировка уже внутри) и сдайте '
    || 'финальную ссылку на подтверждение.';

  for recipient_id_value in
    select distinct candidate.profile_id
    from (
      select job_row.created_by as profile_id
      union
      select account_row.custodian_profile_id
    ) candidate
    where candidate.profile_id is not null
  loop
    request_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'recipient_id', recipient_id_value,
        'kind', 'publishing_manual_required',
        'job_id', job_row.id,
        'reason', reason_value
      )
    );
    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    ) values (
      job_row.organization_id, recipient_id_value,
      'publishing_manual_required', 'warning', title_value, body_value,
      '#/workspace/placement', 'publishing_job', job_row.id::text,
      jsonb_build_object(
        'source', 'publishing_dispatcher',
        'reason', reason_value,
        'placement_id', job_row.placement_id,
        'platform', job_row.platform
      ),
      request_hash_value,
      left('publishing-manual:' || job_row.id::text, 180)
    )
    on conflict (organization_id, recipient_id, dedupe_key) do nothing;
  end loop;

  return true;
end;
$$;

revoke all on function
  content_factory_private.publishing_mark_manual_required(uuid, text)
  from public, anon, authenticated, service_role;

-- Постановка в очередь из паспорта/размещения. Аккаунт зафиксирован нарядом
-- (placements.managed_account_id пишет creator_publish_generation_result);
-- очередь доступна исполнителю с выданным аккаунтом, хранителю аккаунта и
-- владельцу/админу. ERID обязателен; «без рекламы» — только literal ORGANIC;
-- подпись собирается автосборкой, маркировка не редактируется.
create or replace function public.creator_enqueue_publishing_job(
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
  user_id uuid;
  organization_id uuid;
  role_value text;
  placement_row content_factory.placements%rowtype;
  account_row content_factory.managed_accounts%rowtype;
  media_row content_factory.media_objects%rowtype;
  media_id_value uuid;
  scheduled_at_value timestamptz;
  erid_value text;
  advertiser_value text;
  ord_provider_value text;
  contract_ref_value text;
  caption_base_value text;
  hashtags_value text;
  marking_line_value text;
  caption_value text;
  marking_value jsonb;
  job_row content_factory.publishing_jobs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  if p_payload - array[
       'organization_id', 'project_id', 'placement_id', 'scheduled_at',
       'erid', 'advertiser', 'ord_provider', 'contract_ref', 'caption',
       'hashtags', 'media_id'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array['placement_id', 'scheduled_at', 'erid']::text[] then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_payload_invalid';
  end if;

  select member.role into role_value
  from content_factory.memberships member
  where member.organization_id = organization_id
    and member.profile_id = user_id
    and member.status = 'active';

  select placement.* into placement_row
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.id = content_factory_private.require_uuid(
      p_payload, 'placement_id'
    )
  for update;
  if placement_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'publishing_enqueue_placement_not_found';
  end if;
  if placement_row.status not in ('ready', 'scheduled') then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_placement_not_open';
  end if;
  if placement_row.assigned_to <> user_id
     and role_value not in ('owner', 'admin', 'producer') then
    raise exception using errcode = '42501',
      message = 'publishing_enqueue_placement_foreign';
  end if;
  if placement_row.project_id is not null then
    perform content_factory_private.require_workspace_project_access(
      organization_id, placement_row.project_id, user_id
    );
  end if;
  if p_payload ? 'project_id'
     and content_factory_private.require_uuid(p_payload, 'project_id')
       is distinct from placement_row.project_id then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_project_mismatch';
  end if;
  if placement_row.managed_account_id is null then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_account_missing';
  end if;

  select account.* into account_row
  from content_factory.managed_accounts account
  where account.organization_id = organization_id
    and account.id = placement_row.managed_account_id
  for update;
  if account_row.id is null or account_row.status <> 'active' then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_account_unavailable';
  end if;
  if account_row.posting_mode = 'disabled' then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_account_posting_disabled';
  end if;
  if role_value not in ('owner', 'admin')
     and coalesce(account_row.custodian_profile_id = user_id, false) = false
     and not exists (
       select 1
       from content_factory.member_account_assignments assignment
       where assignment.organization_id = organization_id
         and assignment.account_id = account_row.id
         and assignment.profile_id = user_id
         and assignment.status = 'active'
     ) then
    raise exception using errcode = '42501',
      message = 'publishing_enqueue_account_not_assigned';
  end if;

  -- Ролик выводится из самого наряда; явный media_id обязан совпасть.
  if p_payload ? 'media_id' then
    media_id_value := content_factory_private.require_uuid(
      p_payload, 'media_id'
    );
  else
    begin
      media_id_value :=
        nullif(placement_row.metadata ->> 'source_media_id', '')::uuid;
    exception when others then
      media_id_value := null;
    end;
  end if;
  if media_id_value is null then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_media_required';
  end if;
  if nullif(placement_row.metadata ->> 'source_media_id', '') is not null
     and (placement_row.metadata ->> 'source_media_id')
       <> media_id_value::text then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_media_mismatch';
  end if;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value
    and media.status = 'ready';
  if media_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'publishing_enqueue_media_not_found';
  end if;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'generated_video' then
    raise exception using errcode = '55000',
      message = 'publishing_enqueue_media_not_generated_video';
  end if;

  if jsonb_typeof(p_payload -> 'scheduled_at') <> 'string' then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_scheduled_at_invalid';
  end if;
  begin
    scheduled_at_value := (p_payload ->> 'scheduled_at')::timestamptz;
  exception
    when invalid_datetime_format or datetime_field_overflow then
      raise exception using errcode = '22023',
        message = 'publishing_enqueue_scheduled_at_invalid';
  end;
  if scheduled_at_value is null
     or scheduled_at_value < now() - interval '5 minutes'
     or scheduled_at_value > now() + interval '90 days' then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_scheduled_at_out_of_range';
  end if;

  -- Маркировка: пустой не бывает. Либо ERID рекламы (+ рекламодатель),
  -- либо literal ORGANIC без рекламных полей.
  erid_value := upper(content_factory_private.require_text(
    p_payload, 'erid', 4, 64
  ));
  if erid_value !~ '^[A-Z0-9-]{4,64}$' then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_erid_invalid';
  end if;
  if erid_value = 'ORGANIC' then
    if p_payload ? 'advertiser' or p_payload ? 'ord_provider'
       or p_payload ? 'contract_ref' then
      raise exception using errcode = '22023',
        message = 'publishing_enqueue_organic_with_advertiser';
    end if;
    marking_line_value := null;
    marking_value := jsonb_build_object('erid', 'ORGANIC');
  else
    advertiser_value := content_factory_private.require_text(
      p_payload, 'advertiser', 2, 180
    );
    ord_provider_value := content_factory_private.admin_optional_text(
      p_payload, 'ord_provider', 2, 80
    );
    contract_ref_value := content_factory_private.admin_optional_text(
      p_payload, 'contract_ref', 2, 180
    );
    marking_line_value := 'Реклама. ' || advertiser_value
      || '. erid: ' || erid_value;
    marking_value := jsonb_strip_nulls(jsonb_build_object(
      'erid', erid_value,
      'advertiser', advertiser_value,
      'ord_provider', ord_provider_value,
      'contract_ref', contract_ref_value
    ));
  end if;

  caption_base_value := content_factory_private.admin_optional_text(
    p_payload, 'caption', 1, 3000
  );
  hashtags_value := content_factory_private.admin_optional_text(
    p_payload, 'hashtags', 1, 500
  );
  caption_value := btrim(
    coalesce(caption_base_value, '')
    || case when hashtags_value is null then ''
       else E'\n\n' || hashtags_value end
    || case when marking_line_value is null then ''
       else E'\n\n' || marking_line_value end
  );
  if caption_value = '' then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_caption_required';
  end if;
  if length(caption_value) > 4000 then
    raise exception using errcode = '22023',
      message = 'publishing_enqueue_caption_too_long';
  end if;

  -- Один наряд — одна публикация: повтор тихо возвращает существующую
  -- задачу; гонку страхует unique (organization_id, placement_id).
  select job.* into job_row
  from content_factory.publishing_jobs job
  where job.organization_id = organization_id
    and job.placement_id = placement_row.id;
  if job_row.id is not null then
    return jsonb_build_object(
      'ok', true,
      'version', 'publishing-enqueue-v1',
      'already_enqueued', true,
      'job', jsonb_build_object(
        'id', job_row.id,
        'status', job_row.status,
        'scheduled_at', job_row.scheduled_at,
        'platform', job_row.platform,
        'caption', job_row.caption,
        'erid', job_row.erid,
        'posting_mode', account_row.posting_mode
      ),
      'contract', jsonb_build_object(
        'provider_call_started', false,
        'spend_action_started', false
      )
    );
  end if;
  begin
    insert into content_factory.publishing_jobs (
      organization_id, project_id, placement_id, managed_account_id,
      media_object_id, platform, caption, hashtags, marking, erid,
      scheduled_at, status, next_attempt_at, idempotency_key, created_by
    ) values (
      organization_id, placement_row.project_id, placement_row.id,
      account_row.id, media_row.id, account_row.platform, caption_value,
      hashtags_value, marking_value, erid_value, scheduled_at_value,
      'queued', scheduled_at_value,
      'publishing-job:' || placement_row.id::text, user_id
    ) returning * into job_row;
  exception when unique_violation then
    select job.* into job_row
    from content_factory.publishing_jobs job
    where job.organization_id = organization_id
      and job.placement_id = placement_row.id;
  end;

  insert into content_factory.publishing_job_events (
    organization_id, job_id, event, payload, actor, actor_profile_id
  ) values (
    organization_id, job_row.id, 'enqueued',
    jsonb_build_object(
      'scheduled_at', scheduled_at_value,
      'erid', erid_value,
      'platform', account_row.platform,
      'managed_account_id', account_row.id,
      'posting_mode', account_row.posting_mode
    ),
    'creator', user_id
  );

  -- Наряд начинает жить по расписанию: scheduled_at впервые пишется
  -- (витрина «просрочено» его уже читает), статус — 'scheduled'
  -- (creator_confirm_placement принимает scheduled и ready).
  update content_factory.placements placement
  set scheduled_at = scheduled_at_value,
      status = 'scheduled',
      updated_at = now()
  where placement.organization_id = organization_id
    and placement.id = placement_row.id;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'publishing_job_enqueued',
    'publishing_job',
    job_row.id::text,
    jsonb_build_object(
      'placement_id', placement_row.id,
      'platform', account_row.platform,
      'scheduled_at', scheduled_at_value,
      'erid', erid_value
    ),
    'publishing-enqueue:' || job_row.id::text,
    'server_rpc'
  );

  return jsonb_build_object(
    'ok', true,
    'version', 'publishing-enqueue-v1',
    'already_enqueued', false,
    'job', jsonb_build_object(
      'id', job_row.id,
      'status', job_row.status,
      'scheduled_at', job_row.scheduled_at,
      'platform', job_row.platform,
      'caption', job_row.caption,
      'erid', job_row.erid,
      'posting_mode', account_row.posting_mode
    ),
    'contract', jsonb_build_object(
      'provider_call_started', false,
      'spend_action_started', false
    )
  );
end;
$$;

revoke all on function public.creator_enqueue_publishing_job(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_enqueue_publishing_job(jsonb)
  to authenticated;

-- ===== Воркерные функции: только service_role. =====

-- Claim наступивших задач api-аккаунтов с живым подключением (фаза 2 —
-- сейчас таких аккаунтов нет и claim штатно пуст). Аренда 5 минут;
-- протухшие аренды возвращаются в оборот до выборки.
create or replace function public.system_claim_publishing_job(
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
  worker_id_value text;
  limit_value integer;
  lease_token_value uuid;
  leased_until_value timestamptz;
  claimed_jobs jsonb := '[]'::jsonb;
  candidate record;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  worker_id_value := content_factory_private.require_text(
    p_payload, 'worker_id', 3, 120
  );
  begin
    limit_value := coalesce(nullif(p_payload ->> 'limit', ''), '1')::integer;
  exception when invalid_text_representation then
    raise exception using errcode = '22023',
      message = 'publishing_claim_limit_invalid';
  end;
  limit_value := least(greatest(limit_value, 1), 5);

  with expired as (
    update content_factory.publishing_jobs job
    set status = 'queued',
        lease_token = null,
        leased_until = null,
        updated_at = now()
    where job.status in ('claimed', 'uploading')
      and job.leased_until < now()
    returning job.organization_id, job.id
  )
  insert into content_factory.publishing_job_events (
    organization_id, job_id, event, payload, actor
  )
  select expired.organization_id, expired.id, 'lease_expired',
    '{}'::jsonb, 'system'
  from expired;

  for candidate in
    select job.id as job_id, job.organization_id, job.project_id,
      job.placement_id, job.media_object_id, job.platform, job.caption,
      job.hashtags, job.marking, job.erid, job.scheduled_at, job.attempts,
      account.id as account_id, account.label as account_label,
      account.handle as account_handle,
      account.external_account_id as account_external_id,
      media.bucket_id as media_bucket,
      media.object_name as media_object_name,
      media.sha256 as media_sha256,
      media.size_bytes as media_size_bytes,
      media.mime_type as media_mime_type
    from content_factory.publishing_jobs job
    join content_factory.managed_accounts account
      on account.organization_id = job.organization_id
     and account.id = job.managed_account_id
    join content_factory.media_objects media
      on media.organization_id = job.organization_id
     and media.id = job.media_object_id
    where job.status = 'queued'
      and job.scheduled_at <= now()
      and job.next_attempt_at <= now()
      and job.attempts < 10
      and account.status = 'active'
      and account.posting_mode = 'api'
      and account.connection_status = 'connected'
    order by job.scheduled_at, job.created_at
    limit limit_value
    for update of job skip locked
  loop
    lease_token_value := extensions.gen_random_uuid();
    leased_until_value := now() + interval '5 minutes';
    update content_factory.publishing_jobs job
    set status = 'claimed',
        lease_token = lease_token_value,
        leased_until = leased_until_value,
        attempts = job.attempts + 1,
        updated_at = now()
    where job.id = candidate.job_id;

    insert into content_factory.publishing_job_events (
      organization_id, job_id, event, payload, actor
    ) values (
      candidate.organization_id, candidate.job_id, 'claimed',
      jsonb_build_object(
        'worker_id', worker_id_value,
        'attempt', candidate.attempts + 1
      ),
      'worker'
    );

    claimed_jobs := claimed_jobs || jsonb_build_array(jsonb_build_object(
      'job_id', candidate.job_id,
      'lease_token', lease_token_value,
      'leased_until', leased_until_value,
      'organization_id', candidate.organization_id,
      'project_id', candidate.project_id,
      'placement_id', candidate.placement_id,
      'platform', candidate.platform,
      'caption', candidate.caption,
      'hashtags', candidate.hashtags,
      'marking', candidate.marking,
      'erid', candidate.erid,
      'scheduled_at', candidate.scheduled_at,
      'account', jsonb_build_object(
        'id', candidate.account_id,
        'label', candidate.account_label,
        'handle', candidate.account_handle,
        'external_account_id', candidate.account_external_id
      ),
      'media', jsonb_build_object(
        'id', candidate.media_object_id,
        'bucket', candidate.media_bucket,
        'object_name', candidate.media_object_name,
        'sha256', candidate.media_sha256,
        'size_bytes', candidate.media_size_bytes,
        'mime_type', candidate.media_mime_type
      )
    ));
  end loop;

  return jsonb_build_object(
    'ok', true,
    'version', 'publishing-claim-v1',
    'jobs', claimed_jobs
  );
end;
$$;

revoke all on function public.system_claim_publishing_job(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_claim_publishing_job(jsonb)
  to service_role;

-- Итог публикации от воркера. published — системная ветвь §5.5: факт
-- приносит площадка (post id + ссылка), наряд закрывается без второго
-- человека. failed — до 3 попыток с паузой 5/10 минут, затем терминальный
-- отказ с названной причиной и уведомлениями. manual_required — общий хелпер.
create or replace function public.system_complete_publishing_job(
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
  job_row content_factory.publishing_jobs%rowtype;
  account_row content_factory.managed_accounts%rowtype;
  outcome_value text;
  worker_id_value text;
  lease_token_value uuid;
  provider_post_id_value text;
  final_url_value text;
  error_code_value text;
  error_detail_value text;
  retryable_value boolean;
  recipient_id_value uuid;
  request_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'job_id', 'lease_token', 'worker_id', 'outcome', 'provider_post_id',
       'final_url', 'error_code', 'error_detail', 'retryable'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'job_id', 'lease_token', 'worker_id', 'outcome'
     ]::text[] then
    raise exception using errcode = '22023',
      message = 'publishing_complete_payload_invalid';
  end if;
  worker_id_value := content_factory_private.require_text(
    p_payload, 'worker_id', 3, 120
  );
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  outcome_value := lower(content_factory_private.require_text(
    p_payload, 'outcome', 4, 40
  ));
  if outcome_value not in ('published', 'failed', 'manual_required') then
    raise exception using errcode = '22023',
      message = 'publishing_complete_outcome_invalid';
  end if;

  select job.* into job_row
  from content_factory.publishing_jobs job
  where job.id = content_factory_private.require_uuid(p_payload, 'job_id')
  for update;
  if job_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'publishing_job_not_found';
  end if;
  if job_row.status not in ('claimed', 'uploading')
     or job_row.lease_token is distinct from lease_token_value then
    raise exception using errcode = '55000',
      message = 'publishing_job_lease_invalid';
  end if;

  if outcome_value = 'published' then
    provider_post_id_value := content_factory_private.require_text(
      p_payload, 'provider_post_id', 1, 240
    );
    final_url_value := btrim(content_factory_private.require_text(
      p_payload, 'final_url', 12, 600
    ));
    if final_url_value !~ '^https://[^[:space:]]+$' then
      raise exception using errcode = '22023',
        message = 'publishing_complete_final_url_invalid';
    end if;

    update content_factory.publishing_jobs job
    set status = 'published',
        provider_post_id = provider_post_id_value,
        final_url = final_url_value,
        completed_at = now(),
        lease_token = null,
        leased_until = null,
        last_error_code = null,
        last_error_detail = null,
        updated_at = now()
    where job.id = job_row.id
    returning * into job_row;

    insert into content_factory.publishing_job_events (
      organization_id, job_id, event, payload, actor
    ) values (
      job_row.organization_id, job_row.id, 'published',
      jsonb_build_object(
        'provider_post_id', provider_post_id_value,
        'final_url', final_url_value
      ),
      'worker'
    );

    update content_factory.placements placement
    set status = 'published',
        published_at = now(),
        final_url = final_url_value,
        updated_at = now()
    where placement.organization_id = job_row.organization_id
      and placement.id = job_row.placement_id
      and placement.status in ('scheduled', 'ready');

    request_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'recipient_id', job_row.created_by,
        'kind', 'publishing_job_published',
        'job_id', job_row.id
      )
    );
    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    ) values (
      job_row.organization_id, job_row.created_by,
      'publishing_job_published', 'success', 'Публикация вышла',
      'Площадка подтвердила публикацию ролика; ссылка сохранена в '
        || 'размещении.',
      '#/workspace/placement', 'publishing_job', job_row.id::text,
      jsonb_build_object(
        'source', 'publishing_worker',
        'placement_id', job_row.placement_id,
        'platform', job_row.platform
      ),
      request_hash_value,
      left('publishing-published:' || job_row.id::text, 180)
    )
    on conflict (organization_id, recipient_id, dedupe_key) do nothing;

    return jsonb_build_object(
      'ok', true, 'job_id', job_row.id, 'status', 'published'
    );
  end if;

  if outcome_value = 'manual_required' then
    perform content_factory_private.publishing_mark_manual_required(
      job_row.id,
      coalesce(nullif(btrim(coalesce(p_payload ->> 'error_code', '')), ''),
        'provider_manual_required')
    );
    return jsonb_build_object(
      'ok', true, 'job_id', job_row.id, 'status', 'manual_required'
    );
  end if;

  -- outcome = failed. Код и текст — без секретов и подписанных URL:
  -- подозрительная деталь заменяется маркером, не пишется.
  error_code_value := lower(coalesce(
    nullif(btrim(coalesce(p_payload ->> 'error_code', '')), ''),
    'provider_error'
  ));
  if error_code_value !~ '^[a-z][a-z0-9_]{2,99}$' then
    error_code_value := 'provider_error';
  end if;
  error_detail_value := nullif(btrim(coalesce(
    p_payload ->> 'error_detail', ''
  )), '');
  if error_detail_value is not null then
    error_detail_value := left(error_detail_value, 2000);
    if content_factory_private.notification_payload_sensitive_v491(
      to_jsonb(error_detail_value)
    ) then
      error_detail_value := 'publishing_error_detail_redacted';
    end if;
  end if;
  retryable_value := p_payload -> 'retryable' = 'true'::jsonb;

  if retryable_value and job_row.attempts < 3 then
    update content_factory.publishing_jobs job
    set status = 'queued',
        lease_token = null,
        leased_until = null,
        last_error_code = error_code_value,
        last_error_detail = error_detail_value,
        next_attempt_at = now()
          + (interval '5 minutes' * power(2, job_row.attempts - 1)),
        updated_at = now()
    where job.id = job_row.id;

    insert into content_factory.publishing_job_events (
      organization_id, job_id, event, payload, actor
    ) values (
      job_row.organization_id, job_row.id, 'retry_scheduled',
      jsonb_build_object(
        'error_code', error_code_value,
        'attempt', job_row.attempts
      ),
      'worker'
    );
    return jsonb_build_object(
      'ok', true, 'job_id', job_row.id, 'status', 'queued'
    );
  end if;

  update content_factory.publishing_jobs job
  set status = 'failed',
      completed_at = now(),
      lease_token = null,
      leased_until = null,
      last_error_code = error_code_value,
      last_error_detail = error_detail_value,
      updated_at = now()
  where job.id = job_row.id
  returning * into job_row;

  insert into content_factory.publishing_job_events (
    organization_id, job_id, event, payload, actor
  ) values (
    job_row.organization_id, job_row.id, 'failed',
    jsonb_build_object('error_code', error_code_value),
    'worker'
  );

  select account.* into account_row
  from content_factory.managed_accounts account
  where account.organization_id = job_row.organization_id
    and account.id = job_row.managed_account_id;

  for recipient_id_value in
    select distinct candidate.profile_id
    from (
      select job_row.created_by as profile_id
      union
      select account_row.custodian_profile_id
    ) candidate
    where candidate.profile_id is not null
  loop
    request_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'recipient_id', recipient_id_value,
        'kind', 'publishing_job_failed',
        'job_id', job_row.id,
        'error_code', error_code_value
      )
    );
    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    ) values (
      job_row.organization_id, recipient_id_value,
      'publishing_job_failed', 'error', 'Публикация не вышла',
      'Площадка отказала, код: ' || error_code_value
        || '. Автоповторов больше не будет; ролик можно разместить '
        || 'вручную из карточки размещения.',
      '#/workspace/placement', 'publishing_job', job_row.id::text,
      jsonb_build_object(
        'source', 'publishing_worker',
        'error_code', error_code_value,
        'placement_id', job_row.placement_id,
        'platform', job_row.platform
      ),
      request_hash_value,
      left('publishing-failed:' || job_row.id::text, 180)
    )
    on conflict (organization_id, recipient_id, dedupe_key) do nothing;
  end loop;

  return jsonb_build_object(
    'ok', true, 'job_id', job_row.id, 'status', 'failed'
  );
end;
$$;

revoke all on function public.system_complete_publishing_job(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_complete_publishing_job(jsonb)
  to service_role;

-- Диспетчер (чистый SQL, зовёт pg_cron раз в минуту): возвращает протухшие
-- аренды и переводит наступившие задачи assisted/выключенных/неподключённых
-- аккаунтов в manual_required с уведомлением (шаг 1в — assisted как первый
-- «адаптер»).
create or replace function public.system_dispatch_publishing_jobs(
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
  lease_recovered_count integer := 0;
  manual_count integer := 0;
  candidate record;
begin
  p_payload := content_factory_private.require_payload(p_payload);

  with expired as (
    update content_factory.publishing_jobs job
    set status = 'queued',
        lease_token = null,
        leased_until = null,
        updated_at = now()
    where job.status in ('claimed', 'uploading')
      and job.leased_until < now()
    returning job.organization_id, job.id
  )
  insert into content_factory.publishing_job_events (
    organization_id, job_id, event, payload, actor
  )
  select expired.organization_id, expired.id, 'lease_expired',
    '{}'::jsonb, 'system'
  from expired;
  get diagnostics lease_recovered_count = row_count;

  for candidate in
    select job.id as job_id,
      case
        when account.status <> 'active' then 'account_archived'
        when account.posting_mode = 'disabled' then 'posting_disabled'
        when account.posting_mode = 'assisted' then 'assisted_mode_due'
        when account.posting_mode = 'api'
          and account.connection_status <> 'connected'
          then 'connection_not_ready'
        else 'account_unavailable'
      end as reason
    from content_factory.publishing_jobs job
    join content_factory.managed_accounts account
      on account.organization_id = job.organization_id
     and account.id = job.managed_account_id
    where job.status = 'queued'
      and job.scheduled_at <= now()
      and job.next_attempt_at <= now()
      and (
        account.status <> 'active'
        or account.posting_mode in ('assisted', 'disabled')
        or (account.posting_mode = 'api'
          and account.connection_status <> 'connected')
      )
    order by job.scheduled_at, job.created_at
    limit 50
    for update of job skip locked
  loop
    if content_factory_private.publishing_mark_manual_required(
      candidate.job_id, candidate.reason
    ) then
      manual_count := manual_count + 1;
    end if;
  end loop;

  return jsonb_build_object(
    'ok', true,
    'version', 'publishing-dispatch-v1',
    'lease_recovered', lease_recovered_count,
    'manual_required', manual_count
  );
end;
$$;

revoke all on function public.system_dispatch_publishing_jobs(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_dispatch_publishing_jobs(jsonb)
  to service_role;

-- Расписание диспетчера: раз в минуту, по образцу установки job 206
-- (202607170001:353-380). Без pg_cron (локальный стенд) — тихий пропуск.
do $install_publishing_schedule$
declare
  existing_job record;
begin
  if exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_cron'
  ) then
    for existing_job in execute $query$
      select jobid
      from cron.job
      where jobname = 'contentengine-publishing-dispatch-v1'
      order by jobid
    $query$
    loop
      execute 'select cron.unschedule($1)' using existing_job.jobid;
    end loop;
    execute $query$
      select cron.schedule($1, $2, $3)
    $query$
    using
      'contentengine-publishing-dispatch-v1',
      '* * * * *',
      'select public.system_dispatch_publishing_jobs(''{}''::jsonb);';
  end if;
end;
$install_publishing_schedule$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  result_value jsonb;
begin
  -- Гранты: браузеру — только enqueue; system-функции браузеру недоступны.
  if not has_function_privilege(
       'authenticated', 'public.creator_enqueue_publishing_job(jsonb)',
       'execute')
     or has_function_privilege(
       'authenticated', 'public.system_claim_publishing_job(jsonb)',
       'execute')
     or has_function_privilege(
       'authenticated', 'public.system_complete_publishing_job(jsonb)',
       'execute')
     or has_function_privilege(
       'authenticated', 'public.system_dispatch_publishing_jobs(jsonb)',
       'execute')
     or has_function_privilege(
       'anon', 'public.creator_enqueue_publishing_job(jsonb)', 'execute') then
    raise exception using message = 'publishing_rpc_grants_invalid';
  end if;
  -- Диспетчер обязан штатно отвечать на пустой очереди: это тот самый
  -- вызов, который каждую минуту делает pg_cron.
  result_value := public.system_dispatch_publishing_jobs('{}'::jsonb);
  if coalesce(result_value ->> 'ok', '') <> 'true' then
    raise exception using message = 'publishing_dispatch_selfcheck_failed';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

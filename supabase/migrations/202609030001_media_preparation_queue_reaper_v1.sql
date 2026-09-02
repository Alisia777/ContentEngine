begin;
-- 202609030001_media_preparation_queue_reaper_v1
--
-- Реапер очереди подготовки видео: media-воркер живёт вне облака (докер на
-- ПК владельца, позже VPS), и его молчание раньше было невидимым — задание
-- висело queued/claimed бессрочно, а оператор узнавал от клиента. Теперь
-- облачный контур сам замечает застой: pg_cron раз в 5 минут помечает
-- задания queued старше 10 минут (никто не забрал) и claimed с heartbeat
-- старше 15 минут (порог сознательно выше 10-минутного re-claim из
-- 202608270003: блокирующий ffmpeg в finalize даёт честные паузы heartbeat,
-- а алерт человеку не должен опережать самолечение вторым воркером) и шлёт
-- дедуплицированное уведомление постановщику по образцу stalled-Runway
-- (202607170001) и publishing_manual_required (202608290006). Claim
-- пере-эмитится целиком с единственным изменением: успешный захват
-- сбрасывает stalled_at — вернувшийся воркер закрывает инцидент.

alter table content_factory.media_preparation_jobs
  add column if not exists stalled_at timestamptz;

create or replace function public.system_reap_media_preparation_queue(
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
  job_row content_factory.media_preparation_jobs%rowtype;
  stalled_count integer := 0;
begin
  perform content_factory_private.require_payload(p_payload);

  for job_row in
    select job.*
    from content_factory.media_preparation_jobs job
    where job.stalled_at is null
      and (
        (job.status = 'queued'
          and job.created_at < now() - interval '10 minutes')
        or (job.status = 'claimed'
          and job.heartbeat_at < now() - interval '15 minutes')
      )
    order by job.created_at
    limit 20
    for update skip locked
  loop
    update content_factory.media_preparation_jobs job
    set stalled_at = now()
    where job.id = job_row.id;
    stalled_count := stalled_count + 1;

    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    ) values (
      job_row.organization_id,
      job_row.requested_by,
      'media_preparation_stalled',
      'warning',
      'Очередь подготовки видео стоит',
      'Задание подготовки/финализации ролика не обслуживается воркером '
        || 'более 10 минут. Проверьте, запущен ли media-воркер '
        || '(docker на стенде или VPS); вернувшийся воркер продолжит сам.',
      '#/workspace/generation',
      'media_preparation_job',
      job_row.id::text,
      jsonb_build_object(
        'source', 'media_preparation_reaper',
        'kind', job_row.kind,
        'status', job_row.status,
        'attempt_count', job_row.attempt_count
      ),
      content_factory_private.json_hash(jsonb_build_object(
        'recipient_id', job_row.requested_by,
        'kind', 'media_preparation_stalled',
        'entity_id', job_row.id
      )),
      left('media-prep:stalled:' || job_row.id::text, 180)
    )
    on conflict (organization_id, recipient_id, dedupe_key) do nothing;
  end loop;

  return jsonb_build_object(
    'ok', true,
    'version', 'media-preparation-reaper-v1',
    'stalled', stalled_count
  );
end;
$$;

revoke all on function public.system_reap_media_preparation_queue(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_reap_media_preparation_queue(jsonb)
  to service_role;

-- Claim пере-эмитится целиком (тело 202608270003 + сброс stalled_at при
-- успешном захвате; применённые миграции не редактируются).
create or replace function public.system_claim_media_preparation(
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
  job_row content_factory.media_preparation_jobs%rowtype;
  media_row content_factory.media_objects%rowtype;
  analysis_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  worker_id_value := content_factory_private.require_text(
    p_payload, 'worker_id', 3, 120
  );

  update content_factory.media_preparation_jobs job
  set status = 'failed',
      error = 'media_preparation_attempts_exhausted',
      finished_at = now()
  where job.status = 'claimed'
    and job.heartbeat_at < now() - interval '10 minutes'
    and job.attempt_count >= 5;

  select job.* into job_row
  from content_factory.media_preparation_jobs job
  where job.status = 'queued'
     or (
       job.status = 'claimed'
       and job.heartbeat_at < now() - interval '10 minutes'
     )
  order by job.created_at
  limit 1
  for update skip locked;
  if job_row.id is null then
    return jsonb_build_object('ok', true, 'job', null);
  end if;

  update content_factory.media_preparation_jobs job
  set status = 'claimed',
      claimed_by = worker_id_value,
      claimed_at = now(),
      heartbeat_at = now(),
      stalled_at = null,
      attempt_count = job.attempt_count + 1
  where job.id = job_row.id
  returning * into job_row;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = job_row.organization_id
    and media.id = job_row.media_object_id;

  analysis_value := jsonb_build_object(
    'duration_seconds', media_row.metadata -> 'prep_duration_seconds',
    'crop', media_row.metadata -> 'prep_crop_suggestion',
    'trim_start_seconds', media_row.metadata -> 'prep_static_intro_seconds',
    'trim_end_seconds', media_row.metadata -> 'prep_static_outro_seconds'
  );

  return jsonb_build_object(
    'ok', true,
    'job', jsonb_build_object(
      'job_id', job_row.id,
      'kind', job_row.kind,
      'params', job_row.params,
      'organization_id', job_row.organization_id,
      'project_id', job_row.project_id,
      'media_id', job_row.media_object_id,
      'bucket', media_row.bucket_id,
      'object_name', media_row.object_name,
      'original_filename', media_row.metadata ->> 'original_filename',
      'sha256', media_row.sha256,
      'analysis_defaults', analysis_value,
      'suggested_output_object_name',
        job_row.organization_id::text || '/' || job_row.requested_by::text
        || '/sources/clean/' || job_row.id::text || '.mp4'
    )
  );
end;
$$;

revoke all on function public.system_claim_media_preparation(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_claim_media_preparation(jsonb)
  to service_role;

-- Расписание реапера: раз в 5 минут, по образцу установки диспетчера
-- публикаций (202608290006). Без pg_cron (локальный стенд) — тихий пропуск.
do $install_reaper_schedule$
declare
  existing_job record;
begin
  if exists (
    select 1 from pg_catalog.pg_extension where extname = 'pg_cron'
  ) then
    for existing_job in execute $query$
      select jobid
      from cron.job
      where jobname = 'contentengine-media-prep-reaper-v1'
      order by jobid
    $query$
    loop
      execute 'select cron.unschedule($1)' using existing_job.jobid;
    end loop;
    execute $query$
      select cron.schedule($1, $2, $3)
    $query$
    using
      'contentengine-media-prep-reaper-v1',
      '*/5 * * * *',
      'select public.system_reap_media_preparation_queue(''{}''::jsonb);';
  end if;
end;
$install_reaper_schedule$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  result_value jsonb;
  definition_value text;
begin
  -- Реапер на очереди без застоя отвечает штатно и ничего не метит.
  result_value := public.system_reap_media_preparation_queue('{}'::jsonb);
  if coalesce(result_value ->> 'ok', '') <> 'true'
     or coalesce(result_value ->> 'version', '')
        <> 'media-preparation-reaper-v1' then
    raise exception using message = 'media_preparation_reaper_broken';
  end if;

  -- Браузерным ролям system-функции недоступны.
  if has_function_privilege(
       'authenticated',
       'public.system_reap_media_preparation_queue(jsonb)', 'execute'
     )
     or has_function_privilege(
       'anon',
       'public.system_reap_media_preparation_queue(jsonb)', 'execute'
     ) then
    raise exception using message =
      'media_preparation_reaper_grant_leak';
  end if;

  -- Claim пере-эмитился со сбросом stalled_at.
  definition_value := pg_get_functiondef(
    'public.system_claim_media_preparation(jsonb)'::regprocedure
  );
  if position('stalled_at = null' in definition_value) = 0 then
    raise exception using message =
      'media_preparation_claim_stalled_reset_missing';
  end if;
end;
$verify$;

commit;

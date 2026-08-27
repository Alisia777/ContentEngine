begin;
-- 202608270003_media_preparation_worker_v1
--
-- Provider-free воркер подготовки видео (ТЗ 3.8–3.9): очередь заданий в базе,
-- claim/heartbeat/complete только для service-роли (воркер в docker на
-- стенде), постановка и чтение — операторские RPC. Воркер не имеет права
-- запускать генерацию, трогать деньги, подтверждать выводы или публиковать —
-- у него нет таких RPC, а его system-функции пишут только в эту очередь,
-- метадату анализа и регистрацию производного clean-master (оригинал никогда
-- не перезаписывается; производный файл ссылается на исходник).

create table if not exists content_factory.media_preparation_jobs (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  media_object_id uuid not null,
  kind text not null check (kind in ('analyze', 'clean_master')),
  params jsonb not null default '{}'::jsonb
    check (jsonb_typeof(params) = 'object' and length(params::text) <= 4096),
  status text not null default 'queued'
    check (status in ('queued', 'claimed', 'done', 'failed')),
  requested_by uuid not null,
  created_at timestamptz not null default now(),
  claimed_by text,
  claimed_at timestamptz,
  heartbeat_at timestamptz,
  finished_at timestamptz,
  attempt_count integer not null default 0 check (attempt_count between 0 and 5),
  result jsonb
    check (result is null
      or (jsonb_typeof(result) = 'object' and length(result::text) <= 32768)),
  output_media_id uuid,
  error text check (error is null or length(error) <= 2000),
  constraint media_preparation_jobs_media_fk
    foreign key (organization_id, media_object_id)
    references content_factory.media_objects (organization_id, id)
);

create unique index if not exists media_preparation_jobs_active_uq
  on content_factory.media_preparation_jobs
    (organization_id, media_object_id, kind)
  where status in ('queued', 'claimed');

alter table content_factory.media_preparation_jobs
  enable row level security;
revoke all on content_factory.media_preparation_jobs
  from public, anon, authenticated;
grant all on content_factory.media_preparation_jobs to service_role;

-- Постановка задания оператором. Повтор при активном задании — no-op с тем
-- же job_id. Готовится только исходное видео проекта.
create or replace function public.creator_enqueue_media_preparation(
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
  project_id_value uuid;
  media_row content_factory.media_objects%rowtype;
  kind_value text;
  job_row content_factory.media_preparation_jobs%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );
  kind_value := coalesce(p_payload ->> 'kind', '');
  if kind_value not in ('analyze', 'clean_master') then
    raise exception using errcode = '22023',
      message = 'media_preparation_kind_invalid';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = content_factory_private.require_uuid(p_payload, 'media_id')
    and media.status = 'ready';
  if media_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'media_preparation_media_not_found';
  end if;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'source_video'
     or media_row.artifact_class <> 'source' then
    raise exception using errcode = '22023',
      message = 'media_preparation_kind_not_source_video';
  end if;

  -- ON CONFLICT по partial-индексу с #variable_conflict use_variable ловит
  -- имена колонок как переменные (боевой урок 26.08) — поэтому select-first,
  -- а гонку страхует сам уникальный индекс: параллельная вставка падает в
  -- 23505 и превращается в чтение уже существующего активного задания.
  select job.* into job_row
  from content_factory.media_preparation_jobs job
  where job.organization_id = organization_id
    and job.media_object_id = media_row.id
    and job.kind = kind_value
    and job.status in ('queued', 'claimed')
  limit 1;
  if job_row.id is null then
    begin
      insert into content_factory.media_preparation_jobs (
        organization_id, project_id, media_object_id, kind, params,
        requested_by
      ) values (
        organization_id, project_id_value, media_row.id, kind_value,
        coalesce(p_payload -> 'params', '{}'::jsonb), user_id
      ) returning * into job_row;
    exception when unique_violation then
      select job.* into job_row
      from content_factory.media_preparation_jobs job
      where job.organization_id = organization_id
        and job.media_object_id = media_row.id
        and job.kind = kind_value
        and job.status in ('queued', 'claimed')
      limit 1;
    end;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'media-preparation-enqueue-v1',
    'job_id', job_row.id,
    'status', job_row.status,
    'contract', jsonb_build_object(
      'provider_call_started', false,
      'spend_action_started', false
    )
  );
end;
$$;

revoke all on function public.creator_enqueue_media_preparation(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_enqueue_media_preparation(jsonb)
  to authenticated;

-- Статус подготовки для карточки медиа.
create or replace function public.creator_media_preparation_status(
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
  project_id_value uuid;
  jobs_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );

  select coalesce(jsonb_agg(jsonb_build_object(
      'job_id', job.id,
      'kind', job.kind,
      'status', job.status,
      'created_at', job.created_at,
      'finished_at', job.finished_at,
      'error', job.error,
      'output_media_id', job.output_media_id
    ) order by job.created_at desc), '[]'::jsonb)
    into jobs_value
  from (
    select j.* from content_factory.media_preparation_jobs j
    where j.organization_id = organization_id
      and j.project_id = project_id_value
      and j.media_object_id = content_factory_private.require_uuid(
        p_payload, 'media_id'
      )
    order by j.created_at desc
    limit 10
  ) job;

  return jsonb_build_object(
    'ok', true,
    'version', 'media-preparation-status-v1',
    'jobs', jobs_value
  );
end;
$$;

revoke all on function public.creator_media_preparation_status(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_media_preparation_status(jsonb)
  to authenticated;

-- ===== Воркерные функции: только service_role. =====

-- Атомарный claim самого старого задания; протухший claim (heartbeat старше
-- 10 минут) возвращается в оборот, шестая попытка — failed.
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

create or replace function public.system_heartbeat_media_preparation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
begin
  p_payload := content_factory_private.require_payload(p_payload);
  update content_factory.media_preparation_jobs job
  set heartbeat_at = now()
  where job.id = content_factory_private.require_uuid(p_payload, 'job_id')
    and job.status = 'claimed'
    and job.claimed_by = content_factory_private.require_text(
      p_payload, 'worker_id', 3, 120
    );
  return jsonb_build_object('ok', true);
end;
$$;

revoke all on function public.system_heartbeat_media_preparation(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_heartbeat_media_preparation(jsonb)
  to service_role;

-- Итог анализа: результат в задание + prep_-факты в метадату исходника
-- (origin_- и generated--guard'ы не задеты: ключи свои).
create or replace function public.system_complete_media_analysis(
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
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  result_value := coalesce(p_payload -> 'result', '{}'::jsonb);
  if jsonb_typeof(result_value) <> 'object'
     or length(result_value::text) > 32768 then
    raise exception using errcode = '22023',
      message = 'media_preparation_result_invalid';
  end if;

  update content_factory.media_preparation_jobs job
  set status = 'done', result = result_value, finished_at = now()
  where job.id = content_factory_private.require_uuid(p_payload, 'job_id')
    and job.status = 'claimed'
    and job.kind = 'analyze'
    and job.claimed_by = content_factory_private.require_text(
      p_payload, 'worker_id', 3, 120
    )
  returning * into job_row;
  if job_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'media_preparation_job_not_claimed';
  end if;

  update content_factory.media_objects media
  set metadata = media.metadata || jsonb_strip_nulls(jsonb_build_object(
    'prep_analyzed_at', now(),
    'prep_duration_seconds', result_value -> 'duration_seconds',
    'prep_width', result_value -> 'width',
    'prep_height', result_value -> 'height',
    'prep_fps', result_value -> 'fps',
    'prep_audio', result_value -> 'audio',
    'prep_screen_recording_likely',
      result_value -> 'screen_recording_likely',
    'prep_crop_suggestion', result_value -> 'crop',
    'prep_static_intro_seconds', result_value -> 'static_intro_seconds',
    'prep_static_outro_seconds', result_value -> 'static_outro_seconds'
  ))
  where media.organization_id = job_row.organization_id
    and media.id = job_row.media_object_id;

  return jsonb_build_object('ok', true, 'job_id', job_row.id);
end;
$$;

revoke all on function public.system_complete_media_analysis(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_complete_media_analysis(jsonb)
  to service_role;

-- Итог clean master: регистрация производного исходника. Оригинал не
-- перезаписывается; производный несёт роль source_video_clean, ссылку на
-- оригинал и унаследованный след происхождения.
create or replace function public.system_complete_media_clean_master(
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
  source_row content_factory.media_objects%rowtype;
  object_name_value text;
  sha_value text;
  size_value bigint;
  new_media_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  select job.* into job_row
  from content_factory.media_preparation_jobs job
  where job.id = content_factory_private.require_uuid(p_payload, 'job_id')
    and job.status = 'claimed'
    and job.kind = 'clean_master'
    and job.claimed_by = content_factory_private.require_text(
      p_payload, 'worker_id', 3, 120
    )
  for update;
  if job_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'media_preparation_job_not_claimed';
  end if;

  select media.* into source_row
  from content_factory.media_objects media
  where media.organization_id = job_row.organization_id
    and media.id = job_row.media_object_id;

  object_name_value := content_factory_private.require_text(
    p_payload, 'object_name', 10, 1000
  );
  sha_value := lower(btrim(coalesce(p_payload ->> 'sha256', '')));
  if sha_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023',
      message = 'media_preparation_sha_invalid';
  end if;
  size_value := coalesce((p_payload ->> 'size_bytes')::bigint, 0);
  if size_value < 1 or size_value > 52428800 then
    raise exception using errcode = '22023',
      message = 'media_preparation_size_invalid';
  end if;

  insert into content_factory.media_objects (
    organization_id, owner_id, product_id, project_id, bucket_id,
    object_name, mime_type, size_bytes, sha256, status, metadata,
    idempotency_key, artifact_class, lifecycle_stage
  ) values (
    job_row.organization_id, job_row.requested_by, source_row.product_id,
    job_row.project_id, source_row.bucket_id, object_name_value,
    'video/mp4', size_value, sha_value, 'ready',
    jsonb_strip_nulls(jsonb_build_object(
      'kind', 'source_video',
      'role', 'source_video_clean',
      'original_filename',
        regexp_replace(
          coalesce(source_row.metadata ->> 'original_filename', 'source.mp4'),
          '[.]mp4$', ''
        ) || '-clean.mp4',
      'derived_from_media_id', source_row.id,
      'rights_confirmed', source_row.metadata -> 'rights_confirmed',
      'origin_url_canonical', source_row.metadata -> 'origin_url_canonical',
      'origin_video_id', source_row.metadata -> 'origin_video_id',
      'origin_source_id', source_row.metadata -> 'origin_source_id',
      'prep_clean_master_job', job_row.id,
      'duration_seconds', p_payload -> 'duration_seconds',
      'prep_width', p_payload -> 'width',
      'prep_height', p_payload -> 'height'
    )),
    'media-clean-master-' || job_row.id::text,
    'source', 'sources'
  ) returning id into new_media_id;

  update content_factory.media_preparation_jobs job
  set status = 'done',
      output_media_id = new_media_id,
      result = coalesce(p_payload -> 'result', '{}'::jsonb),
      finished_at = now()
  where job.id = job_row.id;

  return jsonb_build_object(
    'ok', true,
    'job_id', job_row.id,
    'output_media_id', new_media_id
  );
end;
$$;

revoke all on function public.system_complete_media_clean_master(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_complete_media_clean_master(jsonb)
  to service_role;

create or replace function public.system_fail_media_preparation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
begin
  p_payload := content_factory_private.require_payload(p_payload);
  update content_factory.media_preparation_jobs job
  set status = case when job.attempt_count >= 5 then 'failed' else 'queued' end,
      error = left(coalesce(p_payload ->> 'error', 'worker_error'), 2000),
      finished_at = case when job.attempt_count >= 5 then now() else null end,
      claimed_by = null,
      claimed_at = null,
      heartbeat_at = null
  where job.id = content_factory_private.require_uuid(p_payload, 'job_id')
    and job.status = 'claimed'
    and job.claimed_by = content_factory_private.require_text(
      p_payload, 'worker_id', 3, 120
    );
  return jsonb_build_object('ok', true);
end;
$$;

revoke all on function public.system_fail_media_preparation(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_fail_media_preparation(jsonb)
  to service_role;

notify pgrst, 'reload schema';

commit;

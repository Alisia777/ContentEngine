begin;
-- 202609020001_video_finalization_queue_v1
--
-- «Финализация» готового ролика (MVP): оператор задаёт три плашки и текст
-- диктора, воркер подготовки медиа (202608270003) глушит родной звук,
-- накладывает TTS-озвучку и drawtext-плашки и регистрирует производный MP4
-- рядом с оригиналом. Очередь та же — media_preparation_jobs:
-- claim/heartbeat/fail kind-агностичны, завершения сшиты по kind, поэтому
-- новый kind='finalize_video' не задевает analyze/clean_master. Денег и
-- провайдеров нет: воркер локальный (ffmpeg+TTS), contract enqueue отдаёт
-- provider_call_started=false. Путь результата кладётся в params при
-- постановке (claim отдаёт params воркеру как есть), suggested-путь клина
-- в claim не трогаем. Тайминги плашек — константы воркера, не базы.
-- Порядок выкладки: воркер с веткой finalize_video обязан работать ДО
-- первой постановки (иначе задание 5 раз сходит по clean_master-ветке и
-- ляжет в failed), поэтому кнопка UI включается после рестарта воркера.

-- 1. Новый kind. drop+add идемпотентен, новый список — надмножество.
alter table content_factory.media_preparation_jobs
  drop constraint if exists media_preparation_jobs_kind_check;
alter table content_factory.media_preparation_jobs
  add constraint media_preparation_jobs_kind_check
  check (kind in ('analyze', 'clean_master', 'finalize_video'));

-- 2. Постановка финализации оператором. Повтор при активном задании — no-op
-- с тем же job_id (страхует media_preparation_jobs_active_uq).
create or replace function public.creator_enqueue_video_finalization(
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
  caption_top_value text;
  caption_mid_value text;
  caption_bottom_value text;
  narration_value text;
  voice_value text;
  duration_value numeric;
  job_id_value uuid;
  params_value jsonb;
  job_row content_factory.media_preparation_jobs%rowtype;
  already_value boolean := false;
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

  caption_top_value := content_factory_private.require_text(
    p_payload, 'caption_top', 1, 120
  );
  caption_mid_value := content_factory_private.require_text(
    p_payload, 'caption_mid', 1, 120
  );
  caption_bottom_value := content_factory_private.require_text(
    p_payload, 'caption_bottom', 1, 120
  );
  narration_value := content_factory_private.require_text(
    p_payload, 'narration_text', 1, 1200
  );
  voice_value := coalesce(p_payload ->> 'voice', '');
  if voice_value not in ('minimax_lovely_girl', 'edge_svetlana') then
    raise exception using errcode = '22023',
      message = 'video_finalization_voice_invalid';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = content_factory_private.require_uuid(p_payload, 'media_id')
    and media.status = 'ready';
  if media_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'video_finalization_media_not_found';
  end if;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'generated_video'
     or media_row.artifact_class <> 'generated_output' then
    raise exception using errcode = '22023',
      message = 'video_finalization_kind_not_generated_video';
  end if;
  -- Плашки MVP калиброваны от 10 секунд: на ролике короче 5 секунд окна
  -- схлопываются в нечитаемые вспышки — отказ до очереди.
  begin
    duration_value := nullif(
      media_row.metadata ->> 'duration_seconds', ''
    )::numeric;
  exception when invalid_text_representation then
    duration_value := null;
  end;
  if duration_value is not null and duration_value < 5 then
    raise exception using errcode = '22023',
      message = 'video_finalization_too_short';
  end if;

  -- select-first, гонку страхует уникальный индекс: ON CONFLICT по
  -- partial-индексу при #variable_conflict use_variable ловит имена колонок
  -- как переменные (боевой урок 26.08, см. 202608270003).
  select job.* into job_row
  from content_factory.media_preparation_jobs job
  where job.organization_id = organization_id
    and job.media_object_id = media_row.id
    and job.kind = 'finalize_video'
    and job.status in ('queued', 'claimed')
  limit 1;
  if job_row.id is not null then
    already_value := true;
  else
    job_id_value := extensions.gen_random_uuid();
    params_value := jsonb_build_object(
      'caption_top', caption_top_value,
      'caption_mid', caption_mid_value,
      'caption_bottom', caption_bottom_value,
      'narration_text', narration_value,
      'voice', voice_value,
      'output_object_name',
        organization_id::text || '/' || user_id::text
        || '/finalize/' || job_id_value::text || '.mp4'
    );
    begin
      insert into content_factory.media_preparation_jobs (
        id, organization_id, project_id, media_object_id, kind, params,
        requested_by
      ) values (
        job_id_value, organization_id, project_id_value, media_row.id,
        'finalize_video', params_value, user_id
      ) returning * into job_row;
    exception when unique_violation then
      already_value := true;
      select job.* into job_row
      from content_factory.media_preparation_jobs job
      where job.organization_id = organization_id
        and job.media_object_id = media_row.id
        and job.kind = 'finalize_video'
        and job.status in ('queued', 'claimed')
      limit 1;
    end;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'video-finalization-enqueue-v1',
    'already_enqueued', already_value,
    'job', jsonb_build_object(
      'id', job_row.id,
      'status', job_row.status,
      'kind', job_row.kind
    ),
    'contract', jsonb_build_object(
      'provider_call_started', false,
      'spend_action_started', false
    )
  );
end;
$$;

revoke all on function public.creator_enqueue_video_finalization(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_enqueue_video_finalization(jsonb)
  to authenticated;

-- 3. Завершение воркером: регистрация финализированного MP4 рядом с
-- оригиналом. Оригинал не перезаписывается; производный — kind
-- generated_video (classify-триггер положит его в generated_output/drafts
-- на приёмку), role finalized_video, ссылка на оригинал. generation_job_id
-- и provider исходника НЕ копируются — bind_generated_video_spoken_script
-- остаётся no-op.
create or replace function public.system_complete_video_finalization(
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
    and job.kind = 'finalize_video'
    and job.claimed_by = content_factory_private.require_text(
      p_payload, 'worker_id', 3, 120
    )
  for update;
  if job_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'video_finalization_job_not_claimed';
  end if;

  select media.* into source_row
  from content_factory.media_objects media
  where media.organization_id = job_row.organization_id
    and media.id = job_row.media_object_id;

  object_name_value := content_factory_private.require_text(
    p_payload, 'object_name', 10, 1000
  );
  if object_name_value is distinct from
     job_row.params ->> 'output_object_name' then
    raise exception using errcode = '22023',
      message = 'video_finalization_object_name_mismatch';
  end if;
  sha_value := lower(btrim(coalesce(p_payload ->> 'sha256', '')));
  if sha_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023',
      message = 'video_finalization_sha_invalid';
  end if;
  size_value := coalesce((p_payload ->> 'size_bytes')::bigint, 0);
  if size_value < 1 or size_value > 52428800 then
    raise exception using errcode = '22023',
      message = 'video_finalization_size_invalid';
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
      'kind', 'generated_video',
      'role', 'finalized_video',
      'original_filename',
        regexp_replace(
          coalesce(source_row.metadata ->> 'original_filename', 'video.mp4'),
          '[.]mp4$', ''
        ) || '-final.mp4',
      'derived_from_media_id', source_row.id,
      'finalize_job', job_row.id,
      'finalize_voice', job_row.params -> 'voice',
      'finalize_captions', jsonb_build_array(
        job_row.params -> 'caption_top',
        job_row.params -> 'caption_mid',
        job_row.params -> 'caption_bottom'
      ),
      'duration_seconds', p_payload -> 'duration_seconds',
      'prep_width', p_payload -> 'width',
      'prep_height', p_payload -> 'height'
    )),
    'media-finalize-' || job_row.id::text,
    'generated_output', 'drafts'
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

revoke all on function public.system_complete_video_finalization(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_complete_video_finalization(jsonb)
  to service_role;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
begin
  if not exists (
    select 1
    from pg_catalog.pg_constraint con
    where con.conrelid = 'content_factory.media_preparation_jobs'::regclass
      and con.conname = 'media_preparation_jobs_kind_check'
      and pg_get_constraintdef(con.oid) like '%finalize_video%'
  ) then
    raise exception using message = 'finalize_video_kind_missing';
  end if;
  if not (select rel.relrowsecurity
      from pg_catalog.pg_class rel
      join pg_catalog.pg_namespace nsp on nsp.oid = rel.relnamespace
      where nsp.nspname = 'content_factory'
        and rel.relname = 'media_preparation_jobs') then
    raise exception using message = 'media_preparation_jobs_rls_disabled';
  end if;
  if exists (
    select 1
    from information_schema.routine_privileges priv
    where priv.routine_schema = 'public'
      and priv.routine_name = 'system_complete_video_finalization'
      and priv.grantee in ('anon', 'authenticated')
  ) then
    raise exception using message =
      'video_finalization_system_rpc_browser_grants_present';
  end if;
  if not exists (
    select 1
    from information_schema.routine_privileges priv
    where priv.routine_schema = 'public'
      and priv.routine_name = 'creator_enqueue_video_finalization'
      and priv.grantee = 'authenticated'
  ) then
    raise exception using message =
      'video_finalization_enqueue_grant_missing';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

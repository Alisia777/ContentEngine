begin;
-- 202609020003_video_finalization_voices_timings_v1
--
-- Вторая итерация «Финализации»: восемь голосов (шесть MiniMax через fal и
-- два бесплатных edge) и настраиваемые окна показа плашек. Окна приходят
-- опциональным ключом caption_windows — массив РОВНО трёх пар чисел в
-- абсолютных секундах ролика (0 <= start < end <= 600); без ключа воркер
-- масштабирует дефолт k = duration/10. Whitelist голосов сквозной:
-- select диалога, эта функция и FINALIZE_VOICES воркера обязаны совпадать.
-- Функция пере-эмитится целиком (0001/0002 применены и не редактируются).

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
  windows_value jsonb;
  window_pair jsonb;
  window_start numeric;
  window_end numeric;
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
  if voice_value not in (
    'minimax_lovely_girl', 'minimax_lively_girl', 'minimax_calm_woman',
    'minimax_wise_woman', 'minimax_deep_voice_man',
    'minimax_friendly_person', 'edge_svetlana', 'edge_dmitry'
  ) then
    raise exception using errcode = '22023',
      message = 'video_finalization_voice_invalid';
  end if;

  -- Настраиваемые окна плашек: либо ключа нет (авто), либо ровно три
  -- честные пары секунд.
  if p_payload ? 'caption_windows' then
    windows_value := p_payload -> 'caption_windows';
    if jsonb_typeof(windows_value) <> 'array'
       or jsonb_array_length(windows_value) <> 3 then
      raise exception using errcode = '22023',
        message = 'video_finalization_caption_windows_invalid';
    end if;
    for window_pair in select value from jsonb_array_elements(windows_value)
    loop
      if jsonb_typeof(window_pair) <> 'array'
         or jsonb_array_length(window_pair) <> 2
         or jsonb_typeof(window_pair -> 0) <> 'number'
         or jsonb_typeof(window_pair -> 1) <> 'number' then
        raise exception using errcode = '22023',
          message = 'video_finalization_caption_windows_invalid';
      end if;
      window_start := (window_pair ->> 0)::numeric;
      window_end := (window_pair ->> 1)::numeric;
      if window_start < 0 or window_end <= window_start
         or window_end > 600 then
        raise exception using errcode = '22023',
          message = 'video_finalization_caption_windows_invalid';
      end if;
    end loop;
  else
    windows_value := null;
  end if;

  -- Ровно один способ назвать ролик: media_id ИЛИ generation_job_id.
  if (p_payload ? 'media_id') = (p_payload ? 'generation_job_id') then
    raise exception using errcode = '22023',
      message = 'video_finalization_media_reference_invalid';
  end if;
  if p_payload ? 'media_id' then
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.project_id = project_id_value
      and media.id = content_factory_private.require_uuid(
        p_payload, 'media_id'
      )
      and media.status = 'ready';
  else
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.project_id = project_id_value
      and media.metadata ->> 'generation_job_id' =
        content_factory_private.require_uuid(
          p_payload, 'generation_job_id'
        )::text
      and media.status = 'ready'
    order by media.created_at desc
    limit 1;
  end if;
  if media_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'video_finalization_media_not_found';
  end if;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'generated_video'
     or media_row.artifact_class <> 'generated_output' then
    raise exception using errcode = '22023',
      message = 'video_finalization_kind_not_generated_video';
  end if;
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
    params_value := jsonb_strip_nulls(jsonb_build_object(
      'caption_top', caption_top_value,
      'caption_mid', caption_mid_value,
      'caption_bottom', caption_bottom_value,
      'narration_text', narration_value,
      'voice', voice_value,
      'caption_windows', windows_value,
      'output_object_name',
        organization_id::text || '/' || user_id::text
        || '/finalize/' || job_id_value::text || '.mp4'
    ));
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
      'kind', job_row.kind,
      'media_id', media_row.id
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

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_enqueue_video_finalization(jsonb)'::regprocedure
  );
  if position('minimax_deep_voice_man' in definition_value) = 0
     or position('edge_dmitry' in definition_value) = 0 then
    raise exception using message =
      'video_finalization_voices_missing';
  end if;
  if position('video_finalization_caption_windows_invalid'
       in definition_value) = 0 then
    raise exception using message =
      'video_finalization_windows_guard_missing';
  end if;
  if position('generation_job_id' in definition_value) = 0 then
    raise exception using message =
      'video_finalization_job_lookup_missing';
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

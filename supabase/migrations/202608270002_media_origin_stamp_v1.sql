begin;
-- 202608270002_media_origin_stamp_v1
--
-- Intake v2 «Копии»: ссылка на оригинал прямо в форме. Файл-исходник получает
-- несмываемый след происхождения в metadata (origin_url_canonical /
-- origin_video_id / origin_source_id) — ключи ставятся один раз, повторный
-- штамп с другим URL — отказ. Ссылка регистрируется существующим реестром
-- источников; здесь только связка «файл ↔ каноническая ссылка», паспорт
-- показывает её у материала source_video. Guard'ы generated-происхождения не
-- задеты: их ключи другие.

create or replace function public.creator_stamp_media_origin_url(
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
  canonical_value text;
  video_id_value text;
  source_id_value uuid;
  existing_value text;
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

  video_id_value := btrim(coalesce(p_payload ->> 'video_id', ''));
  canonical_value := btrim(coalesce(p_payload ->> 'canonical_url', ''));
  if video_id_value !~ '^[A-Za-z0-9_-]{11}$'
     or canonical_value <> 'https://youtube.com/watch?v=' || video_id_value
  then
    raise exception using errcode = '22023',
      message = 'media_origin_url_invalid';
  end if;
  source_id_value := case
    when p_payload ? 'source_id'
      and nullif(btrim(coalesce(p_payload ->> 'source_id', '')), '') is not null
    then content_factory_private.require_uuid(p_payload, 'source_id')
    else null
  end;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = content_factory_private.require_uuid(p_payload, 'media_id')
  for update;
  if media_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'media_origin_media_not_found';
  end if;
  if coalesce(media_row.metadata ->> 'kind', '') <> 'source_video'
     or media_row.artifact_class <> 'source' then
    raise exception using errcode = '22023',
      message = 'media_origin_kind_invalid';
  end if;

  existing_value := media_row.metadata ->> 'origin_url_canonical';
  if existing_value is not null then
    if existing_value <> canonical_value then
      raise exception using errcode = '23505',
        message = 'media_origin_already_stamped';
    end if;
    return jsonb_build_object(
      'ok', true,
      'version', 'media-origin-stamp-v1',
      'media_id', media_row.id,
      'origin_url', existing_value,
      'already_stamped', true
    );
  end if;

  update content_factory.media_objects media
  set metadata = media.metadata
    || jsonb_build_object(
      'origin_url_canonical', canonical_value,
      'origin_video_id', video_id_value,
      'origin_stamped_by', user_id,
      'origin_stamped_at', now()
    )
    || case
      when source_id_value is null then '{}'::jsonb
      else jsonb_build_object('origin_source_id', source_id_value)
    end
  where media.organization_id = organization_id
    and media.id = media_row.id;

  return jsonb_build_object(
    'ok', true,
    'version', 'media-origin-stamp-v1',
    'media_id', media_row.id,
    'origin_url', canonical_value,
    'already_stamped', false
  );
end;
$$;

revoke all on function public.creator_stamp_media_origin_url(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_stamp_media_origin_url(jsonb)
  to authenticated;

-- Паспорт: материал source_video показывает происхождение файла.
do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_result_passport(jsonb)'::regprocedure
  );
  if strpos(src, 'origin_url_canonical') > 0 then
    raise exception 'passport_origin_patch_already_applied';
  end if;
  if strpos(src, '''original_filename'', asset_media.metadata ->> ''original_filename'',') = 0 then
    raise exception 'passport_origin_patch_anchor_missing';
  end if;

  src := replace(src,
    '''original_filename'', asset_media.metadata ->> ''original_filename'',',
    '''original_filename'', asset_media.metadata ->> ''original_filename'',
        ''origin_url'', asset_media.metadata ->> ''origin_url_canonical'',');

  execute src;
end
$mig$;

notify pgrst, 'reload schema';

commit;

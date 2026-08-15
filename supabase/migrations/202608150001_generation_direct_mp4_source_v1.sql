begin;

-- A browser-uploaded MP4 is an exact generation source in its own right.  It
-- must not be represented by a fabricated social URL or a fabricated YouTube
-- source row.  PostgreSQL inheritance lets the existing byte-pinned strategy
-- authority consume the common immutable attachment columns while the row is
-- physically stored in this dedicated direct-MP4 ledger.
create table content_factory.generation_direct_mp4_attachments (
  source_kind text not null default 'direct_mp4' check (
    source_kind = 'direct_mp4'
  ),
  storage_bucket_snapshot text not null check (
    storage_bucket_snapshot = 'contentengine-private'
  ),
  storage_object_name_snapshot text not null check (
    length(storage_object_name_snapshot) between 10 and 1000
    and storage_object_name_snapshot !~ '(^|/)\.\.(/|$)'
  ),
  media_mime_type_snapshot text not null check (
    media_mime_type_snapshot = 'video/mp4'
  ),
  media_size_bytes_snapshot bigint not null check (
    media_size_bytes_snapshot between 1 and 52428800
  )
) inherits (content_factory.research_exact_youtube_media_attachments);

alter table content_factory.generation_direct_mp4_attachments
  add constraint generation_direct_mp4_attachment_id_uq
    unique (organization_id, id),
  add constraint generation_direct_mp4_attachment_media_uq
    unique (organization_id, media_object_id),
  add constraint generation_direct_mp4_attachment_command_uq
    unique (organization_id, idempotency_key),
  add constraint generation_direct_mp4_attachment_hash_uq
    unique (attachment_hash),
  add constraint generation_direct_mp4_attachment_project_fk
    foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  add constraint generation_direct_mp4_attachment_media_fk
    foreign key (organization_id, media_object_id)
    references content_factory.media_objects(organization_id, id),
  add constraint generation_direct_mp4_attachment_actor_fk
    foreign key (organization_id, attached_by)
    references content_factory.memberships(organization_id, profile_id);

create index generation_direct_mp4_attachment_project_idx
  on content_factory.generation_direct_mp4_attachments (
    organization_id, project_id, attached_at desc, id desc
  );

alter table content_factory.generation_direct_mp4_attachments
  enable row level security;
revoke all on content_factory.generation_direct_mp4_attachments
  from public, anon, authenticated, service_role;
grant all on content_factory.generation_direct_mp4_attachments
  to service_role;

create or replace function
  content_factory_private.guard_generation_direct_mp4_attachment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id_value uuid := auth.uid();
  expected_source_hash_value text;
  expected_attachment_hash_value text;
begin
  if tg_op <> 'INSERT' then
    raise exception using
      errcode = '55000',
      message = 'generation_direct_mp4_attachment_append_only';
  end if;

  if caller_id_value is null
     or new.attached_by is distinct from caller_id_value
     or not content_factory_private.workspace_project_access_allowed(
       new.organization_id,
       new.project_id,
       caller_id_value
     ) then
    raise exception using
      errcode = '42501',
      message = 'generation_direct_mp4_attachment_project_access_required';
  end if;

  if new.source_kind <> 'direct_mp4'
     or new.source_id <> new.id
     or new.status <> 'attached'
     or not new.rights_confirmed
     or not new.media_matches_registered_source then
    raise exception using
      errcode = '22023',
      message = 'generation_direct_mp4_attachment_contract_invalid';
  end if;

  if not exists (
    select 1
    from content_factory.media_objects media
    join storage.objects storage_object
      on storage_object.bucket_id = media.bucket_id
     and storage_object.name = media.object_name
    where media.organization_id = new.organization_id
      and media.project_id = new.project_id
      and media.id = new.media_object_id
      and media.owner_id = caller_id_value
      and media.status = 'ready'
      and media.mime_type = 'video/mp4'
      and media.sha256 = new.media_sha256_snapshot
      and media.bucket_id = new.storage_bucket_snapshot
      and media.object_name = new.storage_object_name_snapshot
      and media.mime_type = new.media_mime_type_snapshot
      and media.size_bytes = new.media_size_bytes_snapshot
      and split_part(media.object_name, '/', 1) = new.organization_id::text
      and split_part(media.object_name, '/', 2) = caller_id_value::text
      and media.metadata ->> 'kind' = 'source_video'
      and media.metadata -> 'rights_confirmed'
        is not distinct from 'true'::jsonb
      and media.artifact_class = 'source'
      and media.lifecycle_stage = 'sources'
      and jsonb_typeof(storage_object.metadata) = 'object'
      and storage_object.metadata ->> 'size' = media.size_bytes::text
      and lower(btrim(storage_object.metadata ->> 'mimetype')) =
        media.mime_type
      and not (media.metadata ?| array[
        'generation_job_id', 'provider_job_id', 'generation_provider',
        'generated_from_job_id', 'output_media_id'
      ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_direct_mp4_attachment_media_invalid';
  end if;

  expected_source_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'generation-direct-mp4-source-v1',
      'organization_id', new.organization_id,
      'project_id', new.project_id,
      'media_id', new.media_object_id,
      'storage_bucket', new.storage_bucket_snapshot,
      'storage_object_name', new.storage_object_name_snapshot,
      'media_sha256', new.media_sha256_snapshot,
      'mime_type', new.media_mime_type_snapshot,
      'size_bytes', new.media_size_bytes_snapshot,
      'rights_confirmed', true
    )
  );
  if new.source_hash_snapshot <> expected_source_hash_value then
    raise exception using
      errcode = '22023',
      message = 'generation_direct_mp4_source_hash_invalid';
  end if;

  expected_attachment_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'generation-direct-mp4-attachment-v1',
      'organization_id', new.organization_id,
      'project_id', new.project_id,
      'attachment_id', new.id,
      'source_kind', new.source_kind,
      'source_hash', new.source_hash_snapshot,
      'media_id', new.media_object_id,
      'media_sha256', new.media_sha256_snapshot,
      'rights_confirmed', true
    )
  );
  if new.attachment_hash <> expected_attachment_hash_value then
    raise exception using
      errcode = '22023',
      message = 'generation_direct_mp4_attachment_hash_invalid';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_generation_direct_mp4_attachment()
  from public, anon, authenticated, service_role;

create trigger generation_direct_mp4_attachment_guard
before insert or update or delete
  on content_factory.generation_direct_mp4_attachments
for each row execute function
  content_factory_private.guard_generation_direct_mp4_attachment();

create or replace function public.contentengine_attach_generation_direct_mp4(
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
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  media_id_value uuid;
  attachment_id_value uuid;
  idempotency_key_value text;
  request_payload_value jsonb;
  replay_value jsonb;
  result_value jsonb;
  source_hash_value text;
  attachment_hash_value text;
  media_row content_factory.media_objects%rowtype;
  existing_media_row
    content_factory.generation_direct_mp4_attachments%rowtype;
  existing_key_row
    content_factory.generation_direct_mp4_attachments%rowtype;
  attachment_row
    content_factory.generation_direct_mp4_attachments%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'project_id', 'media_id', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'media_id', 'idempotency_key'
     ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'generation_direct_mp4_attachment_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value,
    project_id_value,
    actor_id_value
  );
  media_id_value := content_factory_private.require_uuid(
    p_payload, 'media_id'
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  request_payload_value := p_payload - 'organization_id' - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id_value,
    'contentengine_attach_generation_direct_mp4',
    idempotency_key_value,
    request_payload_value
  );
  if replay_value is not null then
    return replay_value;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-direct-mp4:' || media_id_value::text)
  );

  select media.* into media_row
  from content_factory.media_objects media
  join storage.objects storage_object
    on storage_object.bucket_id = media.bucket_id
   and storage_object.name = media.object_name
  where media.organization_id = organization_id_value
    and media.project_id = project_id_value
    and media.id = media_id_value
    and media.owner_id = actor_id_value
    and media.status = 'ready'
    and media.mime_type = 'video/mp4'
    and media.bucket_id = 'contentengine-private'
    and split_part(media.object_name, '/', 1) = organization_id_value::text
    and split_part(media.object_name, '/', 2) = actor_id_value::text
    and media.object_name !~ '(^|/)\.\.(/|$)'
    and media.sha256 ~ '^[0-9a-f]{64}$'
    and media.size_bytes between 1 and 52428800
    and media.metadata ->> 'kind' = 'source_video'
    and media.metadata -> 'rights_confirmed' = 'true'::jsonb
    and media.artifact_class = 'source'
    and media.lifecycle_stage = 'sources'
    and jsonb_typeof(storage_object.metadata) = 'object'
    and storage_object.metadata ->> 'size' = media.size_bytes::text
    and lower(btrim(storage_object.metadata ->> 'mimetype')) = media.mime_type
    and not (media.metadata ?| array[
      'generation_job_id', 'provider_job_id', 'generation_provider',
      'generated_from_job_id', 'output_media_id'
    ])
  for share of media, storage_object;
  if media_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'generation_direct_mp4_attachment_media_invalid';
  end if;

  source_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'generation-direct-mp4-source-v1',
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'media_id', media_row.id,
      'storage_bucket', media_row.bucket_id,
      'storage_object_name', media_row.object_name,
      'media_sha256', media_row.sha256,
      'mime_type', media_row.mime_type,
      'size_bytes', media_row.size_bytes,
      'rights_confirmed', true
    )
  );

  select attachment.* into existing_media_row
  from content_factory.generation_direct_mp4_attachments attachment
  where attachment.organization_id = organization_id_value
    and attachment.media_object_id = media_id_value
  for share;

  select attachment.* into existing_key_row
  from content_factory.generation_direct_mp4_attachments attachment
  where attachment.organization_id = organization_id_value
    and attachment.idempotency_key = idempotency_key_value
  for share;
  if existing_key_row.id is not null
     and existing_key_row.media_object_id <> media_id_value then
    raise exception using
      errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;

  -- The inherited parent scan includes both exact-YouTube and direct rows.
  -- It prevents one immutable media object from acquiring two authorities.
  if exists (
    select 1
    from content_factory.research_exact_youtube_media_attachments attachment
    where attachment.organization_id = organization_id_value
      and attachment.media_object_id = media_id_value
      and not exists (
        select 1
        from content_factory.generation_direct_mp4_attachments direct
        where direct.organization_id = attachment.organization_id
          and direct.id = attachment.id
      )
  ) then
    raise exception using
      errcode = '23505',
      message = 'generation_direct_mp4_attachment_conflict';
  end if;

  if existing_media_row.id is not null then
    if existing_media_row.project_id <> project_id_value
       or existing_media_row.source_hash_snapshot <> source_hash_value
       or existing_media_row.media_sha256_snapshot <> media_row.sha256
       or existing_media_row.storage_bucket_snapshot <> media_row.bucket_id
       or existing_media_row.storage_object_name_snapshot <>
            media_row.object_name
       or existing_media_row.media_mime_type_snapshot <> media_row.mime_type
       or existing_media_row.media_size_bytes_snapshot <> media_row.size_bytes
    then
      raise exception using
        errcode = '23505',
        message = 'generation_direct_mp4_attachment_conflict';
    end if;
    attachment_row := existing_media_row;
  else
    attachment_id_value := extensions.gen_random_uuid();
    attachment_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'generation-direct-mp4-attachment-v1',
        'organization_id', organization_id_value,
        'project_id', project_id_value,
        'attachment_id', attachment_id_value,
        'source_kind', 'direct_mp4',
        'source_hash', source_hash_value,
        'media_id', media_row.id,
        'media_sha256', media_row.sha256,
        'rights_confirmed', true
      )
    );
    insert into content_factory.generation_direct_mp4_attachments (
      id, organization_id, project_id, source_id, media_object_id,
      source_hash_snapshot, media_sha256_snapshot, rights_confirmed,
      media_matches_registered_source, status, attached_by,
      idempotency_key, attachment_hash, source_kind,
      storage_bucket_snapshot, storage_object_name_snapshot,
      media_mime_type_snapshot, media_size_bytes_snapshot
    ) values (
      attachment_id_value, organization_id_value, project_id_value,
      attachment_id_value, media_row.id, source_hash_value,
      media_row.sha256, true, true, 'attached', actor_id_value,
      idempotency_key_value, attachment_hash_value, 'direct_mp4',
      media_row.bucket_id, media_row.object_name, media_row.mime_type,
      media_row.size_bytes
    )
    returning * into attachment_row;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'generation-direct-mp4-attachment-v1',
    'project_id', project_id_value,
    'attachment', jsonb_build_object(
      'id', attachment_row.id,
      'status', attachment_row.status,
      'source_kind', attachment_row.source_kind,
      'media_id', attachment_row.media_object_id,
      'source_hash_snapshot', attachment_row.source_hash_snapshot,
      'media_sha256_snapshot', attachment_row.media_sha256_snapshot,
      'rights_confirmed', attachment_row.rights_confirmed,
      'attached_by', attachment_row.attached_by,
      'attached_at', attachment_row.attached_at,
      'attachment_hash', attachment_row.attachment_hash
    ),
    'media', jsonb_build_object(
      'id', media_row.id,
      'project_id', media_row.project_id,
      'object_key', media_row.object_name,
      'kind', media_row.metadata ->> 'kind',
      'mime_type', media_row.mime_type,
      'size_bytes', media_row.size_bytes,
      'sha256', media_row.sha256,
      'status', media_row.status,
      'artifact_class', media_row.artifact_class,
      'lifecycle_stage', media_row.lifecycle_stage
    ),
    'contract', jsonb_build_object(
      'append_only', true,
      'idempotent', true,
      'exact_project_scope', true,
      'private_storage_owned', true,
      'registered_media_reused', true,
      'youtube_source_created', false,
      'social_url_required', false,
      'analysis_started', false,
      'provider_call_started', false,
      'paid_call_started', false,
      'budget_reserved', false
    )
  );

  perform content_factory_private.emit_event(
    organization_id_value,
    actor_id_value,
    'generation_direct_mp4_attached',
    'media_object',
    media_row.id::text,
    jsonb_build_object(
      'project_id', project_id_value,
      'attachment_id', attachment_row.id,
      'source_kind', 'direct_mp4',
      'media_sha256', media_row.sha256,
      'attachment_hash', attachment_row.attachment_hash,
      'provider_call_started', false,
      'paid_call_started', false
    ),
    'generation-direct-mp4:' || attachment_row.id::text
  );

  return content_factory_private.finish_command(
    organization_id_value,
    actor_id_value,
    'contentengine_attach_generation_direct_mp4',
    idempotency_key_value,
    request_payload_value,
    result_value
  );
end;
$$;

revoke all on function
  public.contentengine_attach_generation_direct_mp4(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_attach_generation_direct_mp4(jsonb)
  to authenticated;

-- PostgreSQL foreign keys do not include rows stored in inheritance children.
-- Attachments are immutable, so an INSERT guard supplies the same referential
-- guarantee for both the legacy parent and the direct-MP4 child.
do $drop_exact_only_duration_attachment_fk$
declare
  constraint_name_value text;
begin
  select constraint_row.conname into constraint_name_value
  from pg_catalog.pg_constraint constraint_row
  where constraint_row.conrelid =
      'content_factory.generation_strategy_media_durations'::regclass
    and constraint_row.confrelid =
      'content_factory.research_exact_youtube_media_attachments'::regclass
    and constraint_row.contype = 'f'
  limit 1;
  if constraint_name_value is not null then
    execute format(
      'alter table content_factory.generation_strategy_media_durations drop constraint %I',
      constraint_name_value
    );
  end if;
end;
$drop_exact_only_duration_attachment_fk$;

create or replace function
  content_factory_private.guard_generation_strategy_duration_attachment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (
    select 1
    from content_factory.research_exact_youtube_media_attachments attachment
    where attachment.organization_id = new.organization_id
      and attachment.project_id = new.project_id
      and attachment.id = new.attachment_id
      and attachment.media_object_id = new.media_object_id
      and attachment.attachment_hash = new.attachment_hash
      and attachment.media_sha256_snapshot = new.media_sha256_snapshot
      and attachment.status = 'attached'
      and attachment.rights_confirmed
      and attachment.media_matches_registered_source
  ) then
    raise exception using
      errcode = '23503',
      message = 'generation_strategy_duration_attachment_missing';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_generation_strategy_duration_attachment()
  from public, anon, authenticated, service_role;

drop trigger if exists generation_strategy_duration_attachment_guard
  on content_factory.generation_strategy_media_durations;
create trigger generation_strategy_duration_attachment_guard
before insert on content_factory.generation_strategy_media_durations
for each row execute function
  content_factory_private.guard_generation_strategy_duration_attachment();

-- Preserve the original keyset, role and duration implementation.  Because
-- its parent attachment query includes inheritance children, direct rows are
-- now real candidates.  This wrapper corrects the public provenance labels so
-- a direct upload is never reported as an exact YouTube attachment.
do $preserve_strategy_candidates_pre_direct_mp4$
begin
  if to_regprocedure(
    'public.creator_generation_strategy_asset_candidates_pre_direct_mp4_v1(jsonb)'
  ) is null then
    alter function public.creator_generation_strategy_asset_candidates(jsonb)
      rename to creator_generation_strategy_asset_candidates_pre_direct_mp4_v1;
  end if;
end;
$preserve_strategy_candidates_pre_direct_mp4$;

revoke all on function
  public.creator_generation_strategy_asset_candidates_pre_direct_mp4_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_strategy_asset_candidates(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  result_value jsonb;
  assets_value jsonb;
begin
  result_value :=
    public.creator_generation_strategy_asset_candidates_pre_direct_mp4_v1(
      p_payload
    );

  select coalesce(jsonb_agg(
    case when asset.value ->> 'kind' = 'source_video' then
      asset.value || jsonb_build_object(
        'exact_youtube_attached', coalesce(source.exact_youtube, false),
        'direct_mp4_attached', coalesce(source.direct_mp4, false),
        'source_attachment_kind', case
          when source.direct_mp4 then 'direct_mp4'
          when source.exact_youtube then 'exact_youtube'
          else null
        end
      )
    else asset.value end
    order by asset.ordinality
  ), '[]'::jsonb) into assets_value
  from jsonb_array_elements(result_value -> 'assets')
    with ordinality asset(value, ordinality)
  left join lateral (
    select
      exists (
        select 1
        from content_factory.generation_direct_mp4_attachments direct
        where direct.organization_id =
              (p_payload ->> 'organization_id')::uuid
          and direct.project_id = (p_payload ->> 'project_id')::uuid
          and direct.media_object_id = (asset.value ->> 'id')::uuid
          and direct.status = 'attached'
      ) as direct_mp4,
      exists (
        select 1
        from only content_factory.research_exact_youtube_media_attachments exact
        where exact.organization_id =
              (p_payload ->> 'organization_id')::uuid
          and exact.project_id = (p_payload ->> 'project_id')::uuid
          and exact.media_object_id = (asset.value ->> 'id')::uuid
          and exact.status = 'attached'
      ) as exact_youtube
  ) source on true;

  result_value := jsonb_set(result_value, '{assets}', assets_value, false);
  result_value := jsonb_set(
    result_value,
    '{contract}',
    (result_value -> 'contract')
      - 'source_video_requires_exact_youtube_attachment'
      || jsonb_build_object(
        'source_video_requires_registered_attachment', true,
        'direct_mp4_supported', true,
        'social_url_required_for_direct_mp4', false
      ),
    false
  );
  return result_value;
end;
$$;

revoke all on function
  public.creator_generation_strategy_asset_candidates(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.creator_generation_strategy_asset_candidates(jsonb)
  to authenticated;

comment on table content_factory.generation_direct_mp4_attachments is
  'Append-only direct private MP4 authority. No social source is created; inherited exact-byte columns keep strategy probe/spec/creator-generate as the only paid execution path.';
comment on function
  public.contentengine_attach_generation_direct_mp4(jsonb) is
  'Idempotently attaches a registered, actor-owned private source MP4 to its project without provider calls, budget reservation, generation start or social-source fabrication.';

commit;

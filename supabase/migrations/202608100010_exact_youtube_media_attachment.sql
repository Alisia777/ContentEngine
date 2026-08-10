begin;

-- A registered YouTube identity and an uploaded MP4 are separate immutable
-- facts. Bind them without rewriting the original URL-only source row, and
-- snapshot both hashes so a later analysis pipeline can prove exactly which
-- bytes represented which exact source.
create table if not exists
  content_factory.research_exact_youtube_media_attachments (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    source_id uuid not null,
    media_object_id uuid not null,
    source_hash_snapshot text not null check (
      source_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    media_sha256_snapshot text not null check (
      media_sha256_snapshot ~ '^[0-9a-f]{64}$'
    ),
    rights_confirmed boolean not null check (rights_confirmed),
    media_matches_registered_source boolean not null check (
      media_matches_registered_source
    ),
    status text not null default 'attached' check (status = 'attached'),
    attached_by uuid not null,
    idempotency_key text not null check (
      length(idempotency_key) between 8 and 180
    ),
    attachment_hash text not null check (
      attachment_hash ~ '^[0-9a-f]{64}$'
    ),
    attached_at timestamptz not null default clock_timestamp(),
    unique (organization_id, id),
    unique (organization_id, source_id),
    unique (organization_id, media_object_id),
    unique (organization_id, idempotency_key),
    unique (attachment_hash),
    foreign key (organization_id, source_id)
      references content_factory.research_exact_youtube_sources(
        organization_id, id
      ),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, attached_by)
      references content_factory.memberships(organization_id, profile_id)
  );

create index if not exists exact_youtube_media_attachment_project_idx
  on content_factory.research_exact_youtube_media_attachments (
    organization_id, project_id, attached_at desc, id desc
  );

alter table content_factory.research_exact_youtube_media_attachments
  enable row level security;
revoke all on content_factory.research_exact_youtube_media_attachments
  from public, anon, authenticated, service_role;
grant all on content_factory.research_exact_youtube_media_attachments
  to service_role;

-- Defense in depth for future server-side callers. The public RPC performs
-- the same checks before INSERT, while this trigger keeps the evidence table
-- exact-project, source-only and append-only even if another definer is added.
-- A service-role request without an authenticated human auth.uid() is
-- intentionally unable to manufacture the rights attestation by direct
-- INSERT; the table grant remains available for trusted reads and backups.
create or replace function
  content_factory_private.guard_exact_youtube_media_attachment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id_value uuid := auth.uid();
  expected_attachment_hash_value text;
begin
  if tg_op <> 'INSERT' then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_media_attachment_append_only';
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
      message = 'exact_youtube_media_attachment_project_access_required';
  end if;

  if not exists (
    select 1
    from content_factory.research_exact_youtube_sources source
    where source.organization_id = new.organization_id
      and source.project_id = new.project_id
      and source.id = new.source_id
      and source.status = 'awaiting_media'
      and source.media_required
      and source.source_hash = new.source_hash_snapshot
  ) then
    raise exception using
      errcode = '42501',
      message = 'exact_youtube_media_attachment_source_scope_mismatch';
  end if;

  if not exists (
    select 1
    from content_factory.media_objects media
    where media.organization_id = new.organization_id
      and media.project_id = new.project_id
      and media.id = new.media_object_id
      and media.status = 'ready'
      and media.mime_type = 'video/mp4'
      and media.sha256 = new.media_sha256_snapshot
      and media.metadata ->> 'kind' = 'source_video'
      and media.metadata -> 'rights_confirmed'
        is not distinct from 'true'::jsonb
      and media.artifact_class = 'source'
      and media.lifecycle_stage = 'sources'
      and not (media.metadata ?| array[
        'generation_job_id', 'provider_job_id', 'generation_provider',
        'generated_from_job_id', 'output_media_id'
      ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_media_invalid';
  end if;

  if new.status <> 'attached'
     or not new.rights_confirmed
     or not new.media_matches_registered_source then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_attestation_required';
  end if;

  expected_attachment_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-youtube-media-attachment-v1',
      'organization_id', new.organization_id,
      'project_id', new.project_id,
      'source_id', new.source_id,
      'source_hash', new.source_hash_snapshot,
      'media_id', new.media_object_id,
      'media_sha256', new.media_sha256_snapshot,
      'media_matches_registered_source', true
    )
  );
  if new.attachment_hash <> expected_attachment_hash_value then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_hash_invalid';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_exact_youtube_media_attachment()
  from public, anon, authenticated, service_role;

drop trigger if exists exact_youtube_media_attachment_guard
  on content_factory.research_exact_youtube_media_attachments;
create trigger exact_youtube_media_attachment_guard
before insert or update or delete
  on content_factory.research_exact_youtube_media_attachments
for each row execute function
  content_factory_private.guard_exact_youtube_media_attachment();

create or replace function public.contentengine_attach_exact_youtube_media(
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
  source_id_value uuid;
  media_id_value uuid;
  idempotency_key_value text;
  request_payload_value jsonb;
  replay_value jsonb;
  result_value jsonb;
  attachment_hash_value text;
  source_row content_factory.research_exact_youtube_sources%rowtype;
  media_row content_factory.media_objects%rowtype;
  source_binding_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  media_binding_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  key_binding_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  attachment_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'source_id', 'media_id',
    'rights_confirmed', 'media_matches_registered_source',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'source_id', 'media_id',
       'rights_confirmed', 'media_matches_registered_source',
       'idempotency_key'
     ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_payload_invalid';
  end if;
  if p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_rights_required';
  end if;
  if p_payload -> 'media_matches_registered_source'
       is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_identity_required';
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
  source_id_value := content_factory_private.require_uuid(
    p_payload, 'source_id'
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
    'contentengine_attach_exact_youtube_media',
    idempotency_key_value,
    request_payload_value
  );
  if replay_value is not null then
    return replay_value;
  end if;

  -- Natural-key locks make retries with different command keys deterministic
  -- and prevent one source or one uploaded byte object from being rebound.
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('exact-youtube-source:' || source_id_value::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('exact-youtube-media:' || media_id_value::text)
  );

  select source.* into source_row
  from content_factory.research_exact_youtube_sources source
  where source.organization_id = organization_id_value
    and source.project_id = project_id_value
    and source.id = source_id_value
    and source.status = 'awaiting_media'
    and source.media_required
  for share;
  if source_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'exact_youtube_media_attachment_source_scope_mismatch';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.project_id = project_id_value
    and media.id = media_id_value
  for share;
  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.mime_type <> 'video/mp4'
     or media_row.metadata ->> 'kind' is distinct from 'source_video'
     or media_row.metadata -> 'rights_confirmed'
       is distinct from 'true'::jsonb
     or media_row.artifact_class <> 'source'
     or media_row.lifecycle_stage <> 'sources'
     or media_row.metadata ?| array[
       'generation_job_id', 'provider_job_id', 'generation_provider',
       'generated_from_job_id', 'output_media_id'
     ] then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_media_attachment_media_invalid';
  end if;

  attachment_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-youtube-media-attachment-v1',
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'source_id', source_id_value,
      'source_hash', source_row.source_hash,
      'media_id', media_id_value,
      'media_sha256', media_row.sha256,
      'media_matches_registered_source', true
    )
  );

  select attachment.* into source_binding_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.organization_id = organization_id_value
    and attachment.source_id = source_id_value
  for share;
  if source_binding_row.id is not null and (
    source_binding_row.project_id <> project_id_value
    or source_binding_row.media_object_id <> media_id_value
    or source_binding_row.source_hash_snapshot <> source_row.source_hash
    or source_binding_row.media_sha256_snapshot <> media_row.sha256
    or source_binding_row.attachment_hash <> attachment_hash_value
  ) then
    raise exception using
      errcode = '23505',
      message = 'exact_youtube_media_attachment_conflict';
  end if;

  select attachment.* into media_binding_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.organization_id = organization_id_value
    and attachment.media_object_id = media_id_value
  for share;
  if media_binding_row.id is not null
     and media_binding_row.source_id <> source_id_value then
    raise exception using
      errcode = '23505',
      message = 'exact_youtube_media_attachment_conflict';
  end if;

  select attachment.* into key_binding_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.organization_id = organization_id_value
    and attachment.idempotency_key = idempotency_key_value
  for share;
  if key_binding_row.id is not null and (
    key_binding_row.source_id <> source_id_value
    or key_binding_row.media_object_id <> media_id_value
  ) then
    raise exception using
      errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;

  if source_binding_row.id is not null then
    attachment_row := source_binding_row;
  else
    insert into content_factory.research_exact_youtube_media_attachments (
      organization_id, project_id, source_id, media_object_id,
      source_hash_snapshot, media_sha256_snapshot, rights_confirmed,
      media_matches_registered_source, status, attached_by,
      idempotency_key, attachment_hash
    ) values (
      organization_id_value, project_id_value, source_id_value,
      media_id_value, source_row.source_hash, media_row.sha256, true, true,
      'attached', actor_id_value, idempotency_key_value,
      attachment_hash_value
    )
    returning * into attachment_row;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'exact-youtube-media-attachment-v1',
    'project_id', project_id_value,
    'source', jsonb_build_object(
      'id', source_row.id,
      'video_id', source_row.video_id,
      'canonical_url', source_row.canonical_url,
      'source_hash', source_row.source_hash,
      'registered_status', source_row.status,
      'derived_status', 'media_attached'
    ),
    'attachment', jsonb_build_object(
      'id', attachment_row.id,
      'status', attachment_row.status,
      'source_id', attachment_row.source_id,
      'media_id', attachment_row.media_object_id,
      'source_hash_snapshot', attachment_row.source_hash_snapshot,
      'media_sha256_snapshot', attachment_row.media_sha256_snapshot,
      'rights_confirmed', attachment_row.rights_confirmed,
      'media_matches_registered_source',
        attachment_row.media_matches_registered_source,
      'attached_by', attachment_row.attached_by,
      'attached_at', attachment_row.attached_at,
      'attachment_hash', attachment_row.attachment_hash
    ),
    'media', jsonb_build_object(
      'id', media_row.id,
      'project_id', media_row.project_id,
      'object_key', media_row.object_name,
      'original_filename', media_row.metadata ->> 'original_filename',
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
      'exact_project_scope', true,
      'registered_media_reused', true,
      'identity_attestation_recorded', true,
      'source_row_mutated', false,
      'analysis_ready', true,
      'analysis_started', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );

  perform content_factory_private.emit_event(
    organization_id_value,
    actor_id_value,
    'exact_youtube_media_attached',
    'research_exact_youtube_source',
    source_row.id::text,
    jsonb_build_object(
      'project_id', project_id_value,
      'media_id', media_row.id,
      'attachment_id', attachment_row.id,
      'source_hash', source_row.source_hash,
      'media_sha256', media_row.sha256
    ),
    'exact-youtube-media:' || attachment_row.id::text
  );

  return content_factory_private.finish_command(
    organization_id_value,
    actor_id_value,
    'contentengine_attach_exact_youtube_media',
    idempotency_key_value,
    request_payload_value,
    result_value
  );
end;
$$;

revoke all on function
  public.contentengine_attach_exact_youtube_media(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_attach_exact_youtube_media(jsonb)
  to authenticated;

-- Replace only the queue projection. The original source row remains
-- `awaiting_media`; `status=media_attached` below is a derived read model from
-- the immutable attachment, not an UPDATE of the intake ledger.
create or replace function public.contentengine_exact_youtube_source_queue(
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
  limit_value integer := 30;
  sources_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'limit'
  ]::text[] <> '{}'::jsonb
     or not p_payload ? 'project_id' then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_source_queue_payload_invalid';
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

  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]{1,2}$'
       or (p_payload ->> 'limit')::integer not between 1 and 50 then
      raise exception using
        errcode = '22023',
        message = 'exact_youtube_source_queue_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  select coalesce(
    jsonb_agg(item.payload order by item.created_at desc, item.source_id desc),
    '[]'::jsonb
  )
  into sources_value
  from (
    select
      source.created_at,
      source.id as source_id,
      jsonb_build_object(
        'id', source.id,
        'project_id', source.project_id,
        'video_id', source.video_id,
        'canonical_url', source.canonical_url,
        'product_name', source.product_name,
        'product_sku', source.product_sku,
        'status', case
          when attachment.id is null then 'awaiting_media'
          else 'media_attached'
        end,
        'registered_status', source.status,
        'media_required', attachment.id is null,
        'analysis_ready', coalesce(
          attachment.id is not null
          and media.status = 'ready'
          and media.sha256 = attachment.media_sha256_snapshot,
          false
        ),
        'source_hash', source.source_hash,
        'created_at', source.created_at,
        'attachment', case when attachment.id is null then null else
          jsonb_build_object(
            'id', attachment.id,
            'status', attachment.status,
            'source_id', attachment.source_id,
            'media_id', attachment.media_object_id,
            'source_hash_snapshot', attachment.source_hash_snapshot,
            'media_sha256_snapshot', attachment.media_sha256_snapshot,
            'rights_confirmed', attachment.rights_confirmed,
            'media_matches_registered_source',
              attachment.media_matches_registered_source,
            'attached_by', attachment.attached_by,
            'attached_at', attachment.attached_at,
            'attachment_hash', attachment.attachment_hash
          )
        end,
        'media', case when media.id is null then null else
          jsonb_build_object(
            'id', media.id,
            'project_id', media.project_id,
            'object_key', media.object_name,
            'original_filename', media.metadata ->> 'original_filename',
            'kind', media.metadata ->> 'kind',
            'mime_type', media.mime_type,
            'size_bytes', media.size_bytes,
            'sha256', media.sha256,
            'status', media.status,
            'artifact_class', media.artifact_class,
            'lifecycle_stage', media.lifecycle_stage
          )
        end,
        'next_action', case
          when attachment.id is null then 'upload_lawful_mp4'
          when media.id is null
            or media.status <> 'ready'
            or media.sha256 <> attachment.media_sha256_snapshot
            then 'restore_attached_media'
          else 'start_exact_media_analysis'
        end,
        'files_deep_link', '#/workspace/board?project_id='
          || source.project_id::text
          || '&youtube_source=' || source.id::text
      ) as payload
    from content_factory.research_exact_youtube_sources source
    left join content_factory.research_exact_youtube_media_attachments attachment
      on attachment.organization_id = source.organization_id
     and attachment.source_id = source.id
    left join content_factory.media_objects media
      on media.organization_id = attachment.organization_id
     and media.id = attachment.media_object_id
     and media.project_id = source.project_id
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
    order by source.created_at desc, source.id desc
    limit limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    'version', 'exact-youtube-source-queue-v2',
    'project_id', project_id_value,
    'sources', sources_value,
    'contract', jsonb_build_object(
      'url_is_video_evidence', false,
      'requires_lawful_mp4', true,
      'unattached_source_affects_learning', false,
      'unattached_source_affects_generation', false,
      'attachment_is_append_only', true,
      'attached_source_affects_learning', false,
      'attached_source_affects_generation', false,
      'attachment_starts_analysis', false,
      'source_row_mutated', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_exact_youtube_source_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_exact_youtube_source_queue(jsonb)
  to authenticated, service_role;

comment on table
  content_factory.research_exact_youtube_media_attachments is
  'Append-only exact source-to-registered-MP4 evidence. Source and media hashes plus the operator identity-match attestation are immutable; attachment itself starts no analysis or paid call.';
comment on function
  public.contentengine_attach_exact_youtube_media(jsonb) is
  'Authenticated exact-project binding of one URL-only YouTube source to one lawful, ready, registered source_video MP4.';
comment on function
  public.contentengine_exact_youtube_source_queue(jsonb) is
  'Returns URL-only and attached exact YouTube sources with derived status and immutable media lineage; no source row is mutated and no analysis is started.';

notify pgrst, 'reload schema';

commit;

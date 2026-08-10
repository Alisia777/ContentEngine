begin;

-- An exact YouTube URL, its operator-attested MP4 and the five durable video
-- evidence frames are inputs to one ordinary Product Research provider call.
-- This ledger is deliberately append-only: it records which immutable source
-- and byte snapshots were consumed by which normal project research run.  It
-- never stores model-authored conclusions and never creates a content-review
-- provider attempt.
create table if not exists
  content_factory.research_exact_youtube_research_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    project_id uuid not null,
    run_id uuid not null,
    product_id uuid not null,
    category_binding_id uuid not null,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    product_sku_snapshot text not null check (
      length(btrim(product_sku_snapshot)) between 1 and 120
    ),
    product_title_snapshot text not null check (
      length(btrim(product_title_snapshot)) between 2 and 240
    ),
    source_id uuid not null,
    attachment_id uuid not null,
    media_object_id uuid not null,
    evidence_set_id uuid not null,
    source_hash_snapshot text not null check (
      source_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    attachment_hash_snapshot text not null check (
      attachment_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    media_sha256_snapshot text not null check (
      media_sha256_snapshot ~ '^[0-9a-f]{64}$'
    ),
    evidence_manifest_hash_snapshot text not null check (
      evidence_manifest_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    evidence_frame_count_snapshot integer not null check (
      evidence_frame_count_snapshot = 5
    ),
    evidence_total_size_bytes_snapshot bigint not null check (
      evidence_total_size_bytes_snapshot between 640 and 2359296
    ),
    category_binding_hash_snapshot text not null check (
      category_binding_hash_snapshot ~ '^[0-9a-f]{64}$'
    ),
    media_matches_registered_source boolean not null check (
      media_matches_registered_source
    ),
    source_match_basis text not null check (
      source_match_basis =
        'operator_compared_uploaded_media_to_registered_source'
    ),
    source_match_attested_by uuid not null,
    source_match_attested_at timestamptz not null,
    paid_analysis_ack_snapshot boolean not null check (
      paid_analysis_ack_snapshot
    ),
    analysis_scope text not null default 'sampled_frames_only' check (
      analysis_scope = 'sampled_frames_only'
    ),
    full_stream_access boolean not null default false check (
      not full_stream_access
    ),
    transcript_available boolean not null default false check (
      not transcript_available
    ),
    bound_by uuid not null,
    binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
    bound_at timestamptz not null default clock_timestamp(),
    unique (organization_id, id),
    unique (organization_id, run_id),
    unique (organization_id, evidence_set_id),
    unique (binding_hash),
    foreign key (organization_id, project_id)
      references content_factory.workspace_folders(organization_id, id),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, source_id)
      references content_factory.research_exact_youtube_sources(
        organization_id, id
      ),
    foreign key (organization_id, attachment_id)
      references content_factory.research_exact_youtube_media_attachments(
        organization_id, id
      ),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, evidence_set_id)
      references content_factory.content_review_evidence_sets(
        organization_id, id
      ),
    foreign key (
      organization_id, project_id, run_id, category_binding_id,
      product_category, category_binding_hash_snapshot
    ) references content_factory.research_ai_category_bindings(
      organization_id, project_id, run_id, id,
      product_category, binding_hash
    ),
    foreign key (organization_id, source_match_attested_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, bound_by)
      references content_factory.memberships(organization_id, profile_id)
  );

create index if not exists exact_youtube_research_project_idx
  on content_factory.research_exact_youtube_research_bindings (
    organization_id, project_id, bound_at desc, id desc
  );

alter table content_factory.research_exact_youtube_research_bindings
  enable row level security;
revoke all on content_factory.research_exact_youtube_research_bindings
  from public, anon, authenticated, service_role;

-- Only the authenticated start wrapper may append a binding.  The trigger is
-- a second boundary for future definers and independently recomputes every
-- source/media/evidence/category join and the final binding hash.
create or replace function
  content_factory_private.guard_exact_youtube_research_binding()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  caller_id_value uuid := auth.uid();
  run_row content_factory.product_research_runs%rowtype;
  product_row content_factory.products%rowtype;
  category_row content_factory.research_ai_category_bindings%rowtype;
  source_row content_factory.research_exact_youtube_sources%rowtype;
  attachment_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  media_row content_factory.media_objects%rowtype;
  evidence_row content_factory.content_review_evidence_sets%rowtype;
  frame_count_value integer := 0;
  frame_total_value bigint := 0;
  expected_hash_value text;
begin
  if tg_op <> 'INSERT' then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_research_binding_append_only';
  end if;
  if caller_id_value is null
     or new.bound_by is distinct from caller_id_value
     or not content_factory_private.workspace_project_access_allowed(
       new.organization_id, new.project_id, caller_id_value
     ) then
    raise exception using
      errcode = '42501',
      message = 'exact_youtube_research_project_access_required';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = new.organization_id
    and run.project_id = new.project_id
    and run.id = new.run_id
    and run.product_id = new.product_id
    and run.status = 'queued';
  select product.* into product_row
  from content_factory.products product
  where product.organization_id = new.organization_id
    and product.id = new.product_id
    and product.status = 'active';
  select binding.* into category_row
  from content_factory.research_ai_category_bindings binding
  where binding.organization_id = new.organization_id
    and binding.project_id = new.project_id
    and binding.run_id = new.run_id
    and binding.id = new.category_binding_id
    and binding.product_category = new.product_category
    and binding.binding_hash = new.category_binding_hash_snapshot;
  if run_row.id is null or product_row.id is null or category_row.id is null
     or product_row.sku <> new.product_sku_snapshot
     or product_row.title <> new.product_title_snapshot then
    raise exception using
      errcode = '42501',
      message = 'exact_youtube_research_product_scope_mismatch';
  end if;

  select source.* into source_row
  from content_factory.research_exact_youtube_sources source
  where source.organization_id = new.organization_id
    and source.project_id = new.project_id
    and source.id = new.source_id
    and source.status = 'awaiting_media'
    and source.media_required
    and source.source_hash = new.source_hash_snapshot;
  select attachment.* into attachment_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.organization_id = new.organization_id
    and attachment.project_id = new.project_id
    and attachment.id = new.attachment_id
    and attachment.source_id = new.source_id
    and attachment.media_object_id = new.media_object_id
    and attachment.status = 'attached'
    and attachment.rights_confirmed
    and attachment.media_matches_registered_source
    and attachment.source_hash_snapshot = new.source_hash_snapshot
    and attachment.media_sha256_snapshot = new.media_sha256_snapshot
    and attachment.attachment_hash = new.attachment_hash_snapshot
    and attachment.attached_by = new.source_match_attested_by
    and attachment.attached_at = new.source_match_attested_at;
  if source_row.id is null or attachment_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'exact_youtube_research_source_scope_mismatch';
  end if;

  select media.* into media_row
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
    and (media.product_id is null or media.product_id = new.product_id)
    and not (media.metadata ?| array[
      'generation_job_id', 'provider_job_id', 'generation_provider',
      'generated_from_job_id', 'output_media_id'
    ]);
  select evidence.* into evidence_row
  from content_factory.content_review_evidence_sets evidence
  where evidence.organization_id = new.organization_id
    and evidence.id = new.evidence_set_id
    and evidence.media_object_id = new.media_object_id
    and evidence.status = 'ready'
    and evidence.expires_at > clock_timestamp()
    and evidence.source_mime_type = 'video/mp4'
    and evidence.source_sha256_snapshot = new.media_sha256_snapshot
    and evidence.expected_frame_count = 5
    and evidence.frame_count = 5
    and evidence.total_size_bytes = new.evidence_total_size_bytes_snapshot
    and evidence.manifest_hash = new.evidence_manifest_hash_snapshot;
  select count(*)::integer, coalesce(sum(frame.size_bytes), 0)::bigint
  into frame_count_value, frame_total_value
  from content_factory.content_review_evidence_frames frame
  where frame.organization_id = new.organization_id
    and frame.evidence_set_id = new.evidence_set_id
    and frame.ordinal between 1 and 5
    and frame.bucket_id = 'contentengine-private'
    and frame.mime_type = 'image/jpeg'
    and frame.object_name like evidence_row.object_prefix || '/frame-%';
  if media_row.id is null or evidence_row.id is null
     or frame_count_value <> 5
     or frame_total_value <> evidence_row.total_size_bytes
     or evidence_row.total_size_bytes <> new.evidence_total_size_bytes_snapshot
     or exists (
       select 1
       from content_factory.content_review_evidence_frames later_frame
       join content_factory.content_review_evidence_frames earlier_frame
         on earlier_frame.organization_id = later_frame.organization_id
        and earlier_frame.evidence_set_id = later_frame.evidence_set_id
        and earlier_frame.ordinal = later_frame.ordinal - 1
       where later_frame.organization_id = new.organization_id
         and later_frame.evidence_set_id = new.evidence_set_id
         and later_frame.timecode_seconds <= earlier_frame.timecode_seconds
     ) then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_evidence_invalid';
  end if;

  if not new.media_matches_registered_source
     or not new.paid_analysis_ack_snapshot
     or new.source_match_basis <>
       'operator_compared_uploaded_media_to_registered_source'
     or new.analysis_scope <> 'sampled_frames_only'
     or new.full_stream_access
     or new.transcript_available then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_attestation_invalid';
  end if;

  expected_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'exact-youtube-research-evidence-v1',
      'organization_id', new.organization_id,
      'project_id', new.project_id,
      'run_id', new.run_id,
      'product_id', new.product_id,
      'product_sku', new.product_sku_snapshot,
      'product_title', new.product_title_snapshot,
      'category_binding_id', new.category_binding_id,
      'product_category', new.product_category,
      'category_binding_hash', new.category_binding_hash_snapshot,
      'source_id', new.source_id,
      'source_hash', new.source_hash_snapshot,
      'attachment_id', new.attachment_id,
      'attachment_hash', new.attachment_hash_snapshot,
      'media_id', new.media_object_id,
      'media_sha256', new.media_sha256_snapshot,
      'evidence_id', new.evidence_set_id,
      'evidence_manifest_hash', new.evidence_manifest_hash_snapshot,
      'evidence_frame_count', new.evidence_frame_count_snapshot,
      'evidence_total_size_bytes', new.evidence_total_size_bytes_snapshot,
      'media_matches_registered_source', true,
      'source_match_basis', new.source_match_basis,
      'source_match_attested_by', new.source_match_attested_by,
      'source_match_attested_at', new.source_match_attested_at,
      'paid_analysis_ack', true,
      'analysis_scope', 'sampled_frames_only',
      'full_stream_access', false,
      'transcript_available', false,
      'bound_by', new.bound_by
    )
  );
  if new.binding_hash <> expected_hash_value then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_binding_hash_invalid';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.guard_exact_youtube_research_binding()
  from public, anon, authenticated, service_role;

drop trigger if exists exact_youtube_research_binding_guard
  on content_factory.research_exact_youtube_research_bindings;
create trigger exact_youtube_research_binding_guard
before insert or update or delete
  on content_factory.research_exact_youtube_research_bindings
for each row execute function
  content_factory_private.guard_exact_youtube_research_binding();

do $preserve_project_research_start_before_exact_video$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_project_research_pre_exact_video_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_start_project_research(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_start_project_research_missing';
    end if;
    execute 'alter function public.creator_start_project_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.creator_start_project_research(jsonb) '
      || 'rename to creator_start_project_research_pre_exact_video_v1';
  end if;
end;
$preserve_project_research_start_before_exact_video$;

revoke all on function content_factory_private
  .creator_start_project_research_pre_exact_video_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_project_research(
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
  exact_keys_present boolean;
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  product_id_value uuid;
  category_value text;
  source_id_value uuid;
  attachment_id_value uuid;
  evidence_id_value uuid;
  raw_idempotency_key_value text;
  delegated_idempotency_key_value text;
  delegated_payload_value jsonb;
  result_value jsonb;
  run_id_value uuid;
  binding_hash_value text;
  product_row content_factory.products%rowtype;
  run_row content_factory.product_research_runs%rowtype;
  category_row content_factory.research_ai_category_bindings%rowtype;
  source_row content_factory.research_exact_youtube_sources%rowtype;
  attachment_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  media_row content_factory.media_objects%rowtype;
  evidence_row content_factory.content_review_evidence_sets%rowtype;
  binding_row
    content_factory.research_exact_youtube_research_bindings%rowtype;
  frame_count_value integer := 0;
  frame_total_value bigint := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  exact_keys_present := p_payload ?| array[
    'exact_youtube_source_id', 'exact_youtube_attachment_id',
    'exact_video_evidence_id', 'media_matches_registered_source',
    'source_match_basis'
  ];
  if not exact_keys_present then
    return content_factory_private
      .creator_start_project_research_pre_exact_video_v1(p_payload);
  end if;
  if not p_payload ?& array[
       'exact_youtube_source_id', 'exact_youtube_attachment_id',
       'exact_video_evidence_id', 'media_matches_registered_source',
       'source_match_basis', 'project_id', 'product_id',
       'product_category', 'paid_analysis_ack', 'idempotency_key'
     ]
     or p_payload -> 'media_matches_registered_source'
       is distinct from 'true'::jsonb
     or p_payload -> 'paid_analysis_ack' is distinct from 'true'::jsonb
     or p_payload ->> 'source_match_basis' <>
       'operator_compared_uploaded_media_to_registered_source' then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, actor_id_value
  );
  product_id_value := content_factory_private.require_uuid(
    p_payload, 'product_id'
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  source_id_value := content_factory_private.require_uuid(
    p_payload, 'exact_youtube_source_id'
  );
  attachment_id_value := content_factory_private.require_uuid(
    p_payload, 'exact_youtube_attachment_id'
  );
  evidence_id_value := content_factory_private.require_uuid(
    p_payload, 'exact_video_evidence_id'
  );
  raw_idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('exact-youtube-research:' || source_id_value::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('exact-video-evidence:' || evidence_id_value::text)
  );

  select product.* into product_row
  from content_factory.products product
  where product.organization_id = organization_id_value
    and product.id = product_id_value
    and product.status = 'active'
  for share;
  if product_row.id is null then
    raise exception using
      errcode = '22023', message = 'product_not_found';
  end if;

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
      message = 'exact_youtube_research_source_scope_mismatch';
  end if;
  if nullif(btrim(source_row.product_sku), '') is not null
     and lower(btrim(source_row.product_sku)) not in (
       lower(btrim(product_row.sku)),
       lower(btrim(coalesce(product_row.current_wb_article, '')))
     ) then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_product_identity_mismatch';
  end if;
  if nullif(btrim(source_row.product_sku), '') is null
     and nullif(btrim(source_row.product_name), '') is not null
     and lower(regexp_replace(btrim(source_row.product_name), '\s+', ' ', 'g'))
       <> lower(regexp_replace(btrim(product_row.title), '\s+', ' ', 'g')) then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_product_identity_mismatch';
  end if;

  select attachment.* into attachment_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.organization_id = organization_id_value
    and attachment.project_id = project_id_value
    and attachment.id = attachment_id_value
    and attachment.source_id = source_id_value
    and attachment.status = 'attached'
    and attachment.rights_confirmed
    and attachment.media_matches_registered_source
    and attachment.source_hash_snapshot = source_row.source_hash
  for share;
  if attachment_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'exact_youtube_research_attachment_scope_mismatch';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.project_id = project_id_value
    and media.id = attachment_row.media_object_id
    and media.status = 'ready'
    and media.mime_type = 'video/mp4'
    and media.sha256 = attachment_row.media_sha256_snapshot
    and media.metadata ->> 'kind' = 'source_video'
    and media.metadata -> 'rights_confirmed'
      is not distinct from 'true'::jsonb
    and media.artifact_class = 'source'
    and media.lifecycle_stage = 'sources'
    and (media.product_id is null or media.product_id = product_id_value)
    and not (media.metadata ?| array[
      'generation_job_id', 'provider_job_id', 'generation_provider',
      'generated_from_job_id', 'output_media_id'
    ])
  for share;
  if media_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_media_invalid';
  end if;

  select evidence.* into evidence_row
  from content_factory.content_review_evidence_sets evidence
  where evidence.organization_id = organization_id_value
    and evidence.id = evidence_id_value
    and evidence.media_object_id = media_row.id
    and evidence.source_mime_type = 'video/mp4'
    and evidence.source_sha256_snapshot = media_row.sha256
    and evidence.expected_frame_count = 5
    and evidence.frame_count = 5
    and evidence.total_size_bytes between 640 and 2359296
    and evidence.manifest_hash is not null
    and evidence.status in ('ready', 'consumed')
  for update;
  select count(*)::integer, coalesce(sum(frame.size_bytes), 0)::bigint
  into frame_count_value, frame_total_value
  from content_factory.content_review_evidence_frames frame
  where frame.organization_id = organization_id_value
    and frame.evidence_set_id = evidence_id_value
    and frame.ordinal between 1 and 5
    and frame.bucket_id = 'contentengine-private'
    and frame.mime_type = 'image/jpeg'
    and frame.object_name like evidence_row.object_prefix || '/frame-%';
  if evidence_row.id is null or frame_count_value <> 5
     or frame_total_value <> evidence_row.total_size_bytes
     or exists (
       select 1
       from content_factory.content_review_evidence_frames later_frame
       join content_factory.content_review_evidence_frames earlier_frame
         on earlier_frame.organization_id = later_frame.organization_id
        and earlier_frame.evidence_set_id = later_frame.evidence_set_id
        and earlier_frame.ordinal = later_frame.ordinal - 1
       where later_frame.organization_id = organization_id_value
         and later_frame.evidence_set_id = evidence_id_value
         and later_frame.timecode_seconds <= earlier_frame.timecode_seconds
     ) then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_research_evidence_invalid';
  end if;

  delegated_idempotency_key_value := 'exact-video-v1:' ||
    content_factory_private.json_hash(jsonb_build_object(
      'idempotency_key', raw_idempotency_key_value,
      'project_id', project_id_value,
      'product_id', product_id_value,
      'source_id', source_id_value,
      'attachment_id', attachment_id_value,
      'evidence_id', evidence_id_value
    ));
  delegated_payload_value := (
    p_payload - array[
      'exact_youtube_source_id', 'exact_youtube_attachment_id',
      'exact_video_evidence_id', 'media_matches_registered_source',
      'source_match_basis', 'idempotency_key'
    ]::text[]
  ) || jsonb_build_object(
    'idempotency_key', delegated_idempotency_key_value
  );
  result_value := content_factory_private
    .creator_start_project_research_pre_exact_video_v1(
      delegated_payload_value
    );
  begin
    run_id_value := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_research_start_result_invalid';
  end;
  if run_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_research_start_result_invalid';
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id_value
    and run.project_id = project_id_value
    and run.id = run_id_value
    and run.product_id = product_id_value;
  select category_binding.* into category_row
  from content_factory.research_ai_category_bindings category_binding
  where category_binding.organization_id = organization_id_value
    and category_binding.project_id = project_id_value
    and category_binding.run_id = run_id_value
    and category_binding.product_category = category_value;
  if run_row.id is null or category_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_research_start_result_invalid';
  end if;

  select binding.* into binding_row
  from content_factory.research_exact_youtube_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.run_id = run_id_value;
  if binding_row.id is not null then
    if binding_row.project_id <> project_id_value
       or binding_row.product_id <> product_id_value
       or binding_row.product_category <> category_value
       or binding_row.source_id <> source_id_value
       or binding_row.attachment_id <> attachment_id_value
       or binding_row.media_object_id <> media_row.id
       or binding_row.evidence_set_id <> evidence_id_value
       or binding_row.source_hash_snapshot <> source_row.source_hash
       or binding_row.attachment_hash_snapshot <>
         attachment_row.attachment_hash
       or binding_row.media_sha256_snapshot <> media_row.sha256
       or binding_row.evidence_manifest_hash_snapshot <>
         evidence_row.manifest_hash then
      raise exception using
        errcode = '23505',
        message = 'exact_youtube_research_binding_conflict';
    end if;
  else
    if run_row.status <> 'queued'
       or evidence_row.status <> 'ready'
       or evidence_row.expires_at <= clock_timestamp() then
      raise exception using
        errcode = '55000',
        message = 'exact_youtube_research_evidence_not_ready';
    end if;
    binding_hash_value := content_factory_private.json_hash(
      jsonb_build_object(
        'version', 'exact-youtube-research-evidence-v1',
        'organization_id', organization_id_value,
        'project_id', project_id_value,
        'run_id', run_id_value,
        'product_id', product_id_value,
        'product_sku', product_row.sku,
        'product_title', product_row.title,
        'category_binding_id', category_row.id,
        'product_category', category_value,
        'category_binding_hash', category_row.binding_hash,
        'source_id', source_id_value,
        'source_hash', source_row.source_hash,
        'attachment_id', attachment_id_value,
        'attachment_hash', attachment_row.attachment_hash,
        'media_id', media_row.id,
        'media_sha256', media_row.sha256,
        'evidence_id', evidence_id_value,
        'evidence_manifest_hash', evidence_row.manifest_hash,
        'evidence_frame_count', evidence_row.frame_count,
        'evidence_total_size_bytes', evidence_row.total_size_bytes,
        'media_matches_registered_source', true,
        'source_match_basis',
          'operator_compared_uploaded_media_to_registered_source',
        'source_match_attested_by', attachment_row.attached_by,
        'source_match_attested_at', attachment_row.attached_at,
        'paid_analysis_ack', true,
        'analysis_scope', 'sampled_frames_only',
        'full_stream_access', false,
        'transcript_available', false,
        'bound_by', actor_id_value
      )
    );
    insert into
      content_factory.research_exact_youtube_research_bindings (
        organization_id, project_id, run_id, product_id,
        category_binding_id, product_category,
        product_sku_snapshot, product_title_snapshot,
        source_id, attachment_id, media_object_id, evidence_set_id,
        source_hash_snapshot, attachment_hash_snapshot,
        media_sha256_snapshot, evidence_manifest_hash_snapshot,
        evidence_frame_count_snapshot,
        evidence_total_size_bytes_snapshot,
        category_binding_hash_snapshot,
        media_matches_registered_source, source_match_basis,
        source_match_attested_by, source_match_attested_at,
        paid_analysis_ack_snapshot, analysis_scope,
        full_stream_access, transcript_available,
        bound_by, binding_hash
      ) values (
        organization_id_value, project_id_value, run_id_value,
        product_id_value, category_row.id, category_value,
        product_row.sku, product_row.title,
        source_id_value, attachment_id_value, media_row.id,
        evidence_id_value, source_row.source_hash,
        attachment_row.attachment_hash, media_row.sha256,
        evidence_row.manifest_hash, evidence_row.frame_count,
        evidence_row.total_size_bytes, category_row.binding_hash,
        true, 'operator_compared_uploaded_media_to_registered_source',
        attachment_row.attached_by, attachment_row.attached_at,
        true, 'sampled_frames_only', false, false,
        actor_id_value, binding_hash_value
      ) returning * into binding_row;

    update content_factory.content_review_evidence_sets evidence
    set status = 'consumed', consumed_at = clock_timestamp()
    where evidence.organization_id = organization_id_value
      and evidence.id = evidence_id_value
      and evidence.status = 'ready';
    if not found then
      raise exception using
        errcode = '55000',
        message = 'exact_youtube_research_evidence_consume_conflict';
    end if;

    perform content_factory_private.emit_event(
      organization_id_value,
      actor_id_value,
      'exact_youtube_product_research_started',
      'product_research_run',
      run_id_value::text,
      jsonb_build_object(
        'project_id', project_id_value,
        'product_id', product_id_value,
        'product_category', category_value,
        'source_id', source_id_value,
        'attachment_id', attachment_id_value,
        'media_id', media_row.id,
        'evidence_id', evidence_id_value,
        'binding_id', binding_row.id,
        'analysis_scope', 'sampled_frames_only',
        'content_review_provider_started', false,
        'product_research_provider_started', false
      ),
      'exact-youtube-research:' || binding_row.id::text
    );
  end if;

  return result_value || jsonb_build_object(
    'exact_video', jsonb_build_object(
      'binding_id', binding_row.id,
      'source_id', binding_row.source_id,
      'attachment_id', binding_row.attachment_id,
      'media_id', binding_row.media_object_id,
      'evidence_id', binding_row.evidence_set_id,
      'canonical_url', source_row.canonical_url,
      'analysis_scope', binding_row.analysis_scope,
      'full_stream_access', binding_row.full_stream_access,
      'transcript_available', binding_row.transcript_available,
      'content_review_provider_started', false,
      'product_research_provider_started', false
    )
  );
end;
$$;

revoke all on function public.creator_start_project_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_start_project_research(jsonb)
  to authenticated;

do $preserve_research_claim_before_exact_video$
begin
  if to_regprocedure(
    'content_factory_private.system_claim_product_research_pre_exact_video_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.system_claim_product_research(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'system_claim_product_research_missing';
    end if;
    execute 'alter function public.system_claim_product_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.system_claim_product_research(jsonb) '
      || 'rename to system_claim_product_research_pre_exact_video_v1';
  end if;
end;
$preserve_research_claim_before_exact_video$;

revoke all on function content_factory_private
  .system_claim_product_research_pre_exact_video_v1(jsonb)
  from public, anon, authenticated, service_role;

-- Validate the entire exact-video lineage before the delegated claim can move
-- a queued run across the paid boundary.  The returned frame object names and
-- hashes come only from immutable server tables; no browser-authored result or
-- URL is accepted by the worker.
create or replace function public.system_claim_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  result_value jsonb;
  frames_value jsonb := '[]'::jsonb;
  frame_count_value integer := 0;
  frame_total_value bigint := 0;
  run_row content_factory.product_research_runs%rowtype;
  product_row content_factory.products%rowtype;
  category_row content_factory.research_ai_category_bindings%rowtype;
  source_row content_factory.research_exact_youtube_sources%rowtype;
  attachment_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  media_row content_factory.media_objects%rowtype;
  evidence_row content_factory.content_review_evidence_sets%rowtype;
  binding_row
    content_factory.research_exact_youtube_research_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - 'run_id' <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_claim_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  select binding.* into binding_row
  from content_factory.research_exact_youtube_research_bindings binding
  where binding.run_id = run_id_value;
  if binding_row.id is null then
    return content_factory_private
      .system_claim_product_research_pre_exact_video_v1(p_payload);
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = binding_row.organization_id
    and run.project_id = binding_row.project_id
    and run.id = binding_row.run_id
    and run.product_id = binding_row.product_id;
  select product.* into product_row
  from content_factory.products product
  where product.organization_id = binding_row.organization_id
    and product.id = binding_row.product_id
    and product.sku = binding_row.product_sku_snapshot
    and product.title = binding_row.product_title_snapshot;
  select category_binding.* into category_row
  from content_factory.research_ai_category_bindings category_binding
  where category_binding.organization_id = binding_row.organization_id
    and category_binding.project_id = binding_row.project_id
    and category_binding.run_id = binding_row.run_id
    and category_binding.id = binding_row.category_binding_id
    and category_binding.product_category = binding_row.product_category
    and category_binding.binding_hash =
      binding_row.category_binding_hash_snapshot;
  select source.* into source_row
  from content_factory.research_exact_youtube_sources source
  where source.organization_id = binding_row.organization_id
    and source.project_id = binding_row.project_id
    and source.id = binding_row.source_id
    and source.source_hash = binding_row.source_hash_snapshot;
  select attachment.* into attachment_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.organization_id = binding_row.organization_id
    and attachment.project_id = binding_row.project_id
    and attachment.id = binding_row.attachment_id
    and attachment.source_id = binding_row.source_id
    and attachment.media_object_id = binding_row.media_object_id
    and attachment.attachment_hash =
      binding_row.attachment_hash_snapshot
    and attachment.source_hash_snapshot =
      binding_row.source_hash_snapshot
    and attachment.media_sha256_snapshot =
      binding_row.media_sha256_snapshot
    and attachment.rights_confirmed
    and attachment.media_matches_registered_source;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = binding_row.organization_id
    and media.project_id = binding_row.project_id
    and media.id = binding_row.media_object_id
    and media.status = 'ready'
    and media.mime_type = 'video/mp4'
    and media.sha256 = binding_row.media_sha256_snapshot
    and media.metadata ->> 'kind' = 'source_video'
    and media.metadata -> 'rights_confirmed'
      is not distinct from 'true'::jsonb
    and media.artifact_class = 'source'
    and media.lifecycle_stage = 'sources'
    and (media.product_id is null or media.product_id = binding_row.product_id)
    and not (media.metadata ?| array[
      'generation_job_id', 'provider_job_id', 'generation_provider',
      'generated_from_job_id', 'output_media_id'
    ]);
  select evidence.* into evidence_row
  from content_factory.content_review_evidence_sets evidence
  where evidence.organization_id = binding_row.organization_id
    and evidence.id = binding_row.evidence_set_id
    and evidence.media_object_id = binding_row.media_object_id
    and evidence.status = 'consumed'
    and evidence.source_mime_type = 'video/mp4'
    and evidence.source_sha256_snapshot =
      binding_row.media_sha256_snapshot
    and evidence.expected_frame_count = 5
    and evidence.frame_count = binding_row.evidence_frame_count_snapshot
    and evidence.total_size_bytes =
      binding_row.evidence_total_size_bytes_snapshot
    and evidence.manifest_hash =
      binding_row.evidence_manifest_hash_snapshot;

  select
    coalesce(jsonb_agg(jsonb_build_object(
      'ordinal', frame.ordinal,
      'bucket_id', frame.bucket_id,
      'object_name', frame.object_name,
      'mime_type', frame.mime_type,
      'size_bytes', frame.size_bytes,
      'sha256', frame.sha256,
      'timecode_seconds', frame.timecode_seconds
    ) order by frame.ordinal), '[]'::jsonb),
    count(*)::integer,
    coalesce(sum(frame.size_bytes), 0)::bigint
  into frames_value, frame_count_value, frame_total_value
  from content_factory.content_review_evidence_frames frame
  where frame.organization_id = binding_row.organization_id
    and frame.evidence_set_id = binding_row.evidence_set_id
    and frame.ordinal between 1 and 5
    and frame.bucket_id = 'contentengine-private'
    and frame.mime_type = 'image/jpeg'
    and frame.object_name like evidence_row.object_prefix || '/frame-%';

  if run_row.id is null or product_row.id is null or category_row.id is null
     or source_row.id is null or attachment_row.id is null
     or media_row.id is null or evidence_row.id is null
     or frame_count_value <> 5
     or frame_total_value <> evidence_row.total_size_bytes
     or binding_row.source_match_basis <>
       'operator_compared_uploaded_media_to_registered_source'
     or not binding_row.media_matches_registered_source
     or not binding_row.paid_analysis_ack_snapshot
     or binding_row.analysis_scope <> 'sampled_frames_only'
     or binding_row.full_stream_access
     or binding_row.transcript_available
     or exists (
       select 1
       from content_factory.content_review_evidence_frames later_frame
       join content_factory.content_review_evidence_frames earlier_frame
         on earlier_frame.organization_id = later_frame.organization_id
        and earlier_frame.evidence_set_id = later_frame.evidence_set_id
        and earlier_frame.ordinal = later_frame.ordinal - 1
       where later_frame.organization_id = binding_row.organization_id
         and later_frame.evidence_set_id = binding_row.evidence_set_id
         and later_frame.timecode_seconds <= earlier_frame.timecode_seconds
     ) then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_research_claim_lineage_invalid';
  end if;

  result_value := content_factory_private
    .system_claim_product_research_pre_exact_video_v1(p_payload);
  if result_value #>> '{run,id}' <> run_id_value::text then
    raise exception using
      errcode = '55000',
      message = 'exact_youtube_research_claim_result_invalid';
  end if;
  return jsonb_set(
    result_value,
    '{run,exact_video}',
    jsonb_build_object(
      'version', 'exact-youtube-research-evidence-v1',
      'organization_id', binding_row.organization_id,
      'project_id', binding_row.project_id,
      'binding_id', binding_row.id,
      'product_id', binding_row.product_id,
      'product_category', binding_row.product_category,
      'source', jsonb_build_object(
        'id', source_row.id,
        'video_id', source_row.video_id,
        'canonical_url', source_row.canonical_url,
        'source_hash', source_row.source_hash
      ),
      'attachment', jsonb_build_object(
        'id', attachment_row.id,
        'attachment_hash', attachment_row.attachment_hash,
        'source_hash_snapshot', attachment_row.source_hash_snapshot,
        'media_sha256_snapshot', attachment_row.media_sha256_snapshot,
        'rights_confirmed', attachment_row.rights_confirmed,
        'media_matches_registered_source',
          attachment_row.media_matches_registered_source,
        'attached_by', attachment_row.attached_by,
        'attached_at', attachment_row.attached_at
      ),
      'media', jsonb_build_object(
        'id', media_row.id,
        'mime_type', media_row.mime_type,
        'size_bytes', media_row.size_bytes,
        'sha256', media_row.sha256
      ),
      'evidence', jsonb_build_object(
        'id', evidence_row.id,
        'status', evidence_row.status,
        'source_media_id', evidence_row.media_object_id,
        'source_media_sha256', evidence_row.source_sha256_snapshot,
        'manifest_hash', evidence_row.manifest_hash,
        'frame_count', evidence_row.frame_count,
        'total_size_bytes', evidence_row.total_size_bytes,
        'technical_metrics', evidence_row.technical_metrics,
        'frames', frames_value
      ),
      'provenance', jsonb_build_object(
        'analysis_scope', binding_row.analysis_scope,
        'sampled_evidence_only', true,
        'full_stream_access', binding_row.full_stream_access,
        'transcript_available', binding_row.transcript_available,
        'exact_source_identity_attested', true,
        'source_match_basis', binding_row.source_match_basis,
        'source_match_attested_by',
          binding_row.source_match_attested_by,
        'source_match_attested_at',
          binding_row.source_match_attested_at,
        'client_authored_conclusions', false,
        'content_review_provider_used', false
      )
    ),
    true
  );
end;
$$;

revoke all on function public.system_claim_product_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_claim_product_research(jsonb)
  to service_role;

comment on table
  content_factory.research_exact_youtube_research_bindings is
  'Append-only exact source/MP4/five-frame evidence lineage for one ordinary paid Product Research run; contains no client-authored or provider-authored conclusions.';
comment on function public.creator_start_project_research(jsonb) is
  'Project Product Research start; optional exact YouTube evidence bundle is validated and consumed atomically under the existing explicit paid-analysis acknowledgement.';
comment on function public.system_claim_product_research(jsonb) is
  'Service-only Product Research claim; exact-video runs receive a server-derived, hash-bound five-frame evidence snapshot before provider dispatch.';

notify pgrst, 'reload schema';

commit;

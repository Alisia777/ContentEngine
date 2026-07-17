begin;

-- A video review is only durable when the sampled evidence exists before the
-- queue row is exposed to a worker.  Evidence objects live in the same private
-- bucket as the source media but are registered separately so they never
-- appear as creator library assets.
create table if not exists content_factory.content_review_evidence_sets (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    media_object_id uuid not null,
    created_by uuid not null,
    status text not null default 'preparing'
      check (status in ('preparing', 'ready', 'consumed', 'expired', 'invalid')),
    source_mime_type text not null check (source_mime_type = 'video/mp4'),
    source_sha256_snapshot text not null
      check (source_sha256_snapshot ~ '^[0-9a-f]{64}$'),
    object_prefix text not null check (length(object_prefix) between 40 and 900),
    expected_frame_count integer not null
      check (expected_frame_count between 4 and 5),
    frame_count integer not null default 0
      check (frame_count between 0 and 5),
    total_size_bytes bigint not null default 0
      check (total_size_bytes between 0 and 2359296),
    technical_metrics jsonb not null default '{}'::jsonb check (
      jsonb_typeof(technical_metrics) = 'object'
      and length(technical_metrics::text) <= 32768
    ),
    manifest_hash text check (
      manifest_hash is null or manifest_hash ~ '^[0-9a-f]{64}$'
    ),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    expires_at timestamptz not null,
    ready_at timestamptz,
    consumed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, id),
    unique (organization_id, idempotency_key),
    unique (object_prefix),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (split_part(object_prefix, '/', 1) = organization_id::text),
    check (split_part(object_prefix, '/', 2) = created_by::text),
    check (expires_at > created_at),
    check (
      (status = 'preparing'
        and frame_count = 0
        and total_size_bytes = 0
        and manifest_hash is null
        and ready_at is null
        and consumed_at is null)
      or (status = 'ready'
        and frame_count = expected_frame_count
        and total_size_bytes > 0
        and manifest_hash is not null
        and ready_at is not null
        and consumed_at is null)
      or (status = 'consumed'
        and frame_count = expected_frame_count
        and total_size_bytes > 0
        and manifest_hash is not null
        and ready_at is not null
        and consumed_at is not null)
      or (status in ('expired', 'invalid') and consumed_at is null)
    )
);

create table if not exists content_factory.content_review_evidence_frames (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    evidence_set_id uuid not null,
    ordinal integer not null check (ordinal between 1 and 5),
    bucket_id text not null default 'contentengine-private'
      check (bucket_id = 'contentengine-private'),
    object_name text not null check (length(object_name) between 44 and 1000),
    mime_type text not null check (mime_type = 'image/jpeg'),
    size_bytes bigint not null check (size_bytes between 128 and 524288),
    sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
    timecode_seconds numeric(10,3) not null
      check (timecode_seconds between 0 and 3600),
    created_at timestamptz not null default now(),
    unique (organization_id, id),
    unique (organization_id, evidence_set_id, ordinal),
    unique (bucket_id, object_name),
    foreign key (organization_id, evidence_set_id)
      references content_factory.content_review_evidence_sets(organization_id, id)
);

alter table content_factory.content_review_runs
  add column if not exists evidence_set_id uuid,
  add column if not exists attempt_count integer not null default 0,
  add column if not exists next_attempt_at timestamptz,
  add column if not exists dead_lettered_at timestamptz;

update content_factory.content_review_runs review
set next_attempt_at = case when review.status = 'queued' then now() else null end
where review.next_attempt_at is null;

alter table content_factory.content_review_runs
  alter column next_attempt_at set default now(),
  drop constraint if exists content_review_runs_attempt_count_check,
  drop constraint if exists content_review_runs_dead_letter_check,
  add constraint content_review_runs_attempt_count_check
    check (attempt_count between 0 and 3),
  add constraint content_review_runs_dead_letter_check
    check (dead_lettered_at is null or status = 'failed'),
  add constraint content_review_runs_evidence_set_fk
    foreign key (organization_id, evidence_set_id)
      references content_factory.content_review_evidence_sets(organization_id, id);

create unique index if not exists content_review_runs_evidence_once_uq
  on content_factory.content_review_runs (organization_id, evidence_set_id)
  where evidence_set_id is not null;

create index if not exists content_review_runs_retry_due_idx
  on content_factory.content_review_runs (next_attempt_at, created_at, id)
  where status = 'queued';

create table if not exists content_factory.content_review_attempts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid not null,
    attempt_no integer not null check (attempt_no between 1 and 3),
    status text not null default 'claimed' check (status in (
      'claimed', 'dispatching', 'completed', 'retry_wait',
      'outcome_unknown', 'dead_letter'
    )),
    lease_token uuid not null default extensions.gen_random_uuid(),
    lease_expires_at timestamptz,
    provider_idempotency_key text not null
      check (length(provider_idempotency_key) between 8 and 180),
    provider_dispatch_started_at timestamptz,
    provider_request_id text check (
      provider_request_id is null
      or length(btrim(provider_request_id)) between 3 and 240
    ),
    completion_hash text check (
      completion_hash is null or completion_hash ~ '^[0-9a-f]{64}$'
    ),
    error_code text check (
      error_code is null or error_code ~ '^[a-z][a-z0-9_]{2,99}$'
    ),
    error_message text check (
      error_message is null or length(btrim(error_message)) between 3 and 2000
    ),
    claimed_at timestamptz not null default now(),
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, id),
    unique (organization_id, review_id, attempt_no),
    unique (lease_token),
    unique (provider_idempotency_key, attempt_no),
    foreign key (organization_id, review_id)
      references content_factory.content_review_runs(organization_id, id),
    check (
      (status in ('claimed', 'dispatching')
        and lease_expires_at is not null
        and finished_at is null)
      or (status in (
          'completed', 'retry_wait', 'outcome_unknown', 'dead_letter'
        )
        and lease_expires_at is null
        and finished_at is not null)
    ),
    check (
      (status = 'claimed' and provider_dispatch_started_at is null)
      or (status in ('dispatching', 'completed', 'outcome_unknown')
        and provider_dispatch_started_at is not null)
      or (status in ('retry_wait', 'dead_letter')
        and provider_dispatch_started_at is null)
    ),
    check (
      status not in ('retry_wait', 'outcome_unknown', 'dead_letter')
      or error_code is not null
    )
);

create unique index if not exists content_review_attempts_one_active_uq
  on content_factory.content_review_attempts (organization_id, review_id)
  where status in ('claimed', 'dispatching');
create index if not exists content_review_attempts_lease_due_idx
  on content_factory.content_review_attempts (lease_expires_at, id)
  where status in ('claimed', 'dispatching');
create index if not exists content_review_attempts_dead_letter_idx
  on content_factory.content_review_attempts
  (organization_id, finished_at desc, id desc)
  where status in ('outcome_unknown', 'dead_letter');

alter table content_factory.content_review_evidence_sets enable row level security;
alter table content_factory.content_review_evidence_frames enable row level security;
alter table content_factory.content_review_attempts enable row level security;
revoke all on content_factory.content_review_evidence_sets
  from public, anon, authenticated;
revoke all on content_factory.content_review_evidence_frames
  from public, anon, authenticated;
revoke all on content_factory.content_review_attempts
  from public, anon, authenticated;
grant all on content_factory.content_review_evidence_sets to service_role;
grant all on content_factory.content_review_evidence_frames to service_role;
grant all on content_factory.content_review_attempts to service_role;

create or replace function
  content_factory_private.guard_content_review_evidence_set()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_deletion_forbidden';
  end if;
  if new.id is distinct from old.id
     or new.organization_id is distinct from old.organization_id
     or new.media_object_id is distinct from old.media_object_id
     or new.created_by is distinct from old.created_by
     or new.source_mime_type is distinct from old.source_mime_type
     or new.source_sha256_snapshot is distinct from old.source_sha256_snapshot
     or new.object_prefix is distinct from old.object_prefix
     or new.expected_frame_count is distinct from old.expected_frame_count
     or new.idempotency_key is distinct from old.idempotency_key
     or new.expires_at is distinct from old.expires_at
     or new.created_at is distinct from old.created_at then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_identity_immutable';
  end if;
  if old.status in ('consumed', 'expired', 'invalid') then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_terminal';
  end if;
  if new.status = old.status then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_update_without_transition';
  end if;
  if not (
    (old.status = 'preparing' and new.status in ('ready', 'expired', 'invalid'))
    or (old.status = 'ready' and new.status in ('consumed', 'expired'))
  ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_transition_invalid';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

alter function public.system_claim_content_review(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_claim_content_review(jsonb)
  rename to system_claim_content_review_legacy;
revoke all on function
  content_factory_private.system_claim_content_review_legacy(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.system_claim_content_review(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  evidence_row content_factory.content_review_evidence_sets%rowtype;
  attempt_row content_factory.content_review_attempts%rowtype;
  parent_result_value jsonb;
  product_value jsonb;
  frames_value jsonb;
  evidence_value jsonb;
  attempt_created_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['review_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_claim_payload_invalid';
  end if;
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  perform pg_advisory_xact_lock(
    hashtext('content-review-run'), hashtext(review_id_value::text)
  );
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.id = review_id_value
  for update;
  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = review_row.organization_id
    and media.id = review_row.media_object_id
  for share;

  if review_row.status = 'queued'
     and (
       media_row.id is null
       or media_row.status <> 'ready'
       or media_row.sha256 <> review_row.media_sha256_snapshot
     ) then
    update content_factory.content_review_runs review
    set status = 'cancelled',
        error_code = 'media_stale_before_review',
        error_message =
          'The exact media changed before analysis. Start a new review.'
    where review.id = review_id_value
      and review.status = 'queued'
    returning * into review_row;
  end if;

  if review_row.status = 'queued'
     and media_row.mime_type = 'video/mp4' then
    select evidence.* into evidence_row
    from content_factory.content_review_evidence_sets evidence
    where evidence.organization_id = review_row.organization_id
      and evidence.id = review_row.evidence_set_id
    for share;
    if evidence_row.id is null
       or evidence_row.status <> 'consumed'
       or evidence_row.media_object_id <> review_row.media_object_id
       or evidence_row.source_sha256_snapshot
            <> review_row.media_sha256_snapshot
       or evidence_row.manifest_hash is null
       or evidence_row.frame_count <> evidence_row.expected_frame_count then
      update content_factory.content_review_runs review
      set status = 'cancelled',
          error_code = 'content_review_video_evidence_invalid',
          error_message =
            'Durable video evidence is missing or stale. Start a new review.'
      where review.id = review_id_value
        and review.status = 'queued'
      returning * into review_row;
    else
      select jsonb_agg(
        jsonb_build_object(
          'ordinal', frame.ordinal,
          'bucket_id', frame.bucket_id,
          'object_name', frame.object_name,
          'mime_type', frame.mime_type,
          'size_bytes', frame.size_bytes,
          'sha256', frame.sha256,
          'timecode_seconds', frame.timecode_seconds
        ) order by frame.ordinal
      ) into frames_value
      from content_factory.content_review_evidence_frames frame
      where frame.organization_id = review_row.organization_id
        and frame.evidence_set_id = evidence_row.id;
      if coalesce(jsonb_array_length(frames_value), 0)
           <> evidence_row.expected_frame_count then
        update content_factory.content_review_runs review
        set status = 'cancelled',
            error_code = 'content_review_video_evidence_invalid',
            error_message =
              'Durable video evidence is incomplete. Start a new review.'
        where review.id = review_id_value
          and review.status = 'queued'
        returning * into review_row;
      else
        evidence_value := jsonb_build_object(
          'id', evidence_row.id,
          'status', evidence_row.status,
          'source_media_id', evidence_row.media_object_id,
          'source_media_sha256', evidence_row.source_sha256_snapshot,
          'manifest_hash', evidence_row.manifest_hash,
          'frame_count', evidence_row.frame_count,
          'total_size_bytes', evidence_row.total_size_bytes,
          'technical_metrics', evidence_row.technical_metrics,
          'frames', frames_value
        );
      end if;
    end if;
  end if;

  if review_row.status = 'queued' then
    select attempt.* into attempt_row
    from content_factory.content_review_attempts attempt
    where attempt.organization_id = review_row.organization_id
      and attempt.review_id = review_row.id
      and attempt.status in ('claimed', 'dispatching')
    order by attempt.attempt_no desc
    limit 1
    for update;
    if attempt_row.id is null
       and coalesce(review_row.next_attempt_at, now()) <= now() then
      if review_row.attempt_count >= 3 then
        raise exception using
          errcode = '55000',
          message = 'content_review_attempt_limit_reached';
      end if;
      insert into content_factory.content_review_attempts (
        organization_id, review_id, attempt_no, status,
        lease_expires_at, provider_idempotency_key
      ) values (
        review_row.organization_id,
        review_row.id,
        review_row.attempt_count + 1,
        'claimed',
        now() + interval '5 minutes',
        'content-review:' || review_row.id::text
      ) returning * into attempt_row;
      attempt_created_value := true;
      update content_factory.content_review_runs review
      set attempt_count = review.attempt_count + 1,
          next_attempt_at = null
      where review.id = review_row.id
        and review.status = 'queued'
      returning * into review_row;
    end if;
  end if;

  if review_row.parent_review_id is not null then
    select parent.result into parent_result_value
    from content_factory.content_review_runs parent
    where parent.organization_id = review_row.organization_id
      and parent.id = review_row.parent_review_id
      and parent.status = 'completed';
  end if;
  if media_row.product_id is not null then
    select jsonb_build_object(
      'id', product.id,
      'sku', product.sku,
      'title', product.title,
      'current_wb_article', product.current_wb_article,
      'metadata', product.metadata
    ) into product_value
    from content_factory.products product
    where product.organization_id = review_row.organization_id
      and product.id = media_row.product_id;
  end if;

  return jsonb_strip_nulls(jsonb_build_object(
    'ok', true,
    'claimed', attempt_created_value,
    'attempt', case when attempt_row.id is null then null else
      jsonb_build_object(
        'id', attempt_row.id,
        'attempt_no', attempt_row.attempt_no,
        'status', attempt_row.status,
        'lease_token', attempt_row.lease_token,
        'lease_expires_at', attempt_row.lease_expires_at,
        'provider_idempotency_key', attempt_row.provider_idempotency_key
      )
    end,
    'evidence', case
      when media_row.mime_type = 'video/mp4' then evidence_value
      else null
    end,
    'run', jsonb_build_object(
      'id', review_row.id,
      'status', review_row.status,
      'organization_id', review_row.organization_id,
      'requested_by', review_row.requested_by,
      'parent_review_id', review_row.parent_review_id,
      'evidence_id', review_row.evidence_set_id,
      'attempt_count', review_row.attempt_count,
      'next_attempt_at', review_row.next_attempt_at,
      'lease_expires_at', review_row.lease_expires_at,
      'ruleset_version', review_row.ruleset_version,
      'input', review_row.input,
      'parent_result', parent_result_value,
      'product', product_value,
      'media', jsonb_build_object(
        'id', media_row.id,
        'owner_id', media_row.owner_id,
        'task_id', media_row.task_id,
        'product_id', media_row.product_id,
        'bucket_id', media_row.bucket_id,
        'object_name', media_row.object_name,
        'mime_type', media_row.mime_type,
        'size_bytes', media_row.size_bytes,
        'sha256', media_row.sha256,
        'status', media_row.status,
        'metadata', media_row.metadata,
        'snapshot_matches', (
          media_row.sha256 = review_row.media_sha256_snapshot
        )
      )
    )
  ));
end;
$$;

create or replace function public.system_begin_content_review_provider_dispatch(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_id_value uuid;
  attempt_id_value uuid;
  lease_token_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  attempt_row content_factory.content_review_attempts%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'review_id', 'attempt_id', 'lease_token'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_dispatch_payload_invalid';
  end if;
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  attempt_id_value := content_factory_private.require_uuid(
    p_payload, 'attempt_id'
  );
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  perform pg_advisory_xact_lock(
    hashtext('content-review-run'), hashtext(review_id_value::text)
  );
  select attempt.* into attempt_row
  from content_factory.content_review_attempts attempt
  where attempt.id = attempt_id_value
  for update;
  if attempt_row.id is null
     or attempt_row.review_id <> review_id_value then
    raise exception using
      errcode = 'P0002',
      message = 'content_review_attempt_not_found';
  end if;
  if attempt_row.lease_token <> lease_token_value then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_lease_mismatch';
  end if;
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = attempt_row.organization_id
    and review.id = review_id_value
  for update;
  if attempt_row.status = 'dispatching'
     and attempt_row.provider_dispatch_started_at is not null
     and review_row.status = 'processing' then
    return jsonb_build_object(
      'ok', true,
      'review_id', review_id_value,
      'attempt_id', attempt_id_value,
      'provider_dispatch_started', true,
      'provider_idempotency_key', attempt_row.provider_idempotency_key,
      'idempotent', true
    );
  end if;
  if attempt_row.status <> 'claimed'
     or review_row.status <> 'queued' then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_not_claimed';
  end if;
  if attempt_row.lease_expires_at <= now() then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_lease_expired';
  end if;

  update content_factory.content_review_attempts attempt
  set status = 'dispatching',
      provider_dispatch_started_at = now(),
      lease_expires_at = now() + interval '10 minutes'
  where attempt.id = attempt_id_value
    and attempt.status = 'claimed'
  returning * into attempt_row;
  update content_factory.content_review_runs review
  set status = 'processing',
      next_attempt_at = null
  where review.id = review_id_value
    and review.status = 'queued'
  returning * into review_row;
  if attempt_row.status <> 'dispatching'
     or review_row.status <> 'processing' then
    raise exception using
      errcode = '55000',
      message = 'content_review_dispatch_conflict';
  end if;
  return jsonb_build_object(
    'ok', true,
    'review_id', review_id_value,
    'attempt_id', attempt_id_value,
    'provider_dispatch_started', true,
    'provider_idempotency_key', attempt_row.provider_idempotency_key,
    'lease_expires_at', attempt_row.lease_expires_at,
    'idempotent', false
  );
end;
$$;

create or replace function public.system_release_content_review_attempt(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_id_value uuid;
  attempt_id_value uuid;
  lease_token_value uuid;
  error_code_value text;
  error_message_value text;
  retryable_value boolean;
  retry_seconds integer;
  next_attempt_value timestamptz;
  review_row content_factory.content_review_runs%rowtype;
  attempt_row content_factory.content_review_attempts%rowtype;
  completion_payload jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 4096
     or p_payload - array[
       'review_id', 'attempt_id', 'lease_token',
       'error_code', 'error_message', 'retryable'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_attempt_release_payload_invalid';
  end if;
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  attempt_id_value := content_factory_private.require_uuid(
    p_payload, 'attempt_id'
  );
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  error_code_value := content_factory_private.require_text(
    p_payload, 'error_code', 3, 100
  );
  error_message_value := content_factory_private.require_text(
    p_payload, 'error_message', 3, 2000
  );
  if error_code_value !~ '^[a-z][a-z0-9_]{2,99}$'
     or jsonb_typeof(p_payload -> 'retryable') <> 'boolean' then
    raise exception using
      errcode = '22023',
      message = 'content_review_attempt_release_payload_invalid';
  end if;
  retryable_value := (p_payload ->> 'retryable')::boolean;
  if not retryable_value then
    raise exception using
      errcode = '22023',
      message = 'content_review_attempt_release_retryable_required';
  end if;

  perform pg_advisory_xact_lock(
    hashtext('content-review-run'), hashtext(review_id_value::text)
  );

  select attempt.* into attempt_row
  from content_factory.content_review_attempts attempt
  where attempt.id = attempt_id_value
  for update;
  if attempt_row.id is null
     or attempt_row.review_id <> review_id_value then
    raise exception using
      errcode = 'P0002',
      message = 'content_review_attempt_not_found';
  end if;
  if attempt_row.lease_token <> lease_token_value then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_lease_mismatch';
  end if;
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = attempt_row.organization_id
    and review.id = review_id_value
  for update;
  if attempt_row.status in ('retry_wait', 'dead_letter') then
    return jsonb_strip_nulls(jsonb_build_object(
      'ok', true,
      'review_id', review_id_value,
      'attempt_id', attempt_id_value,
      'status', review_row.status,
      'next_attempt_at', review_row.next_attempt_at,
      'dead_lettered', attempt_row.status = 'dead_letter',
      'idempotent', true
    ));
  end if;
  if attempt_row.status <> 'claimed'
     or attempt_row.provider_dispatch_started_at is not null
     or review_row.status <> 'queued' then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_release_after_dispatch_forbidden';
  end if;

  if attempt_row.attempt_no >= 3 then
    completion_payload := jsonb_build_object(
      'status', 'failed',
      'error_code', 'content_review_dispatch_dead_letter',
      'error_message', error_message_value
    );
    update content_factory.content_review_attempts attempt
    set status = 'dead_letter',
        lease_expires_at = null,
        error_code = error_code_value,
        error_message = error_message_value,
        finished_at = now()
    where attempt.id = attempt_id_value
      and attempt.status = 'claimed';
    update content_factory.content_review_runs review
    set status = 'failed',
        error_code = 'content_review_dispatch_dead_letter',
        error_message = error_message_value,
        completion_hash = content_factory_private.json_hash(completion_payload),
        dead_lettered_at = now()
    where review.id = review_id_value
      and review.status = 'queued'
    returning * into review_row;
    return jsonb_build_object(
      'ok', true,
      'review_id', review_id_value,
      'attempt_id', attempt_id_value,
      'status', 'failed',
      'dead_lettered', true,
      'idempotent', false
    );
  end if;

  retry_seconds := least(300, 30 * (2 ^ (attempt_row.attempt_no - 1))::integer);
  next_attempt_value := now() + make_interval(secs => retry_seconds);
  update content_factory.content_review_attempts attempt
  set status = 'retry_wait',
      lease_expires_at = null,
      error_code = error_code_value,
      error_message = error_message_value,
      finished_at = now()
  where attempt.id = attempt_id_value
    and attempt.status = 'claimed';
  update content_factory.content_review_runs review
  set next_attempt_at = next_attempt_value
  where review.id = review_id_value
    and review.status = 'queued'
  returning * into review_row;
  return jsonb_build_object(
    'ok', true,
    'review_id', review_id_value,
    'attempt_id', attempt_id_value,
    'status', 'queued',
    'next_attempt_at', review_row.next_attempt_at,
    'dead_lettered', false,
    'idempotent', false
  );
end;
$$;



-- Keep the mature validation in the original start RPC, but place a durable
-- evidence binding around it.  The wrapper transaction includes command
-- receipt replay, run creation, evidence consumption and the run FK update.
alter function public.creator_start_content_review(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_content_review(jsonb)
  rename to creator_start_content_review_legacy;
revoke all on function
  content_factory_private.creator_start_content_review_legacy(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_content_review(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  evidence_id_value uuid;
  evidence_row content_factory.content_review_evidence_sets%rowtype;
  media_id_value uuid;
  media_row content_factory.media_objects%rowtype;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 131072
     or p_payload - array[
       'organization_id', 'idempotency_key', 'media_id', 'media_object_id',
       'evidence_id', 'parent_review_id', 'platform', 'product_category',
       'content_kind', 'declared_ad_status', 'caption_text', 'script_text',
       'technical_metrics', 'people_present', 'ad_label_confirmed',
       'ord_confirmed', 'advertiser_name', 'erid',
       'audience_over_10000', 'rkn_registered',
       'person_consent_confirmed', 'ai_generated',
       'external_ai_processing_confirmed', 'ai_disclosure_confirmed',
       'captions_confirmed', 'mandatory_warning_confirmed',
       'rights_confirmed', 'claims_verified'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_start_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  if p_payload ? 'media_id' and p_payload ? 'media_object_id'
     and p_payload ->> 'media_id' is distinct from
       p_payload ->> 'media_object_id' then
    raise exception using
      errcode = '22023',
      message = 'content_review_media_id_conflict';
  end if;
  if p_payload ? 'media_id' then
    media_id_value := content_factory_private.require_uuid(p_payload, 'media_id');
  else
    media_id_value := content_factory_private.require_uuid(
      p_payload, 'media_object_id'
    );
  end if;
  select media.* into media_row
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where media.organization_id = organization_id
    and media.id = media_id_value
    and media.status = 'ready'
    and media.mime_type in (
      'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
    )
    and (
      manager_scope
      or media.owner_id = user_id
      or task.assignee_id = user_id
    );
  if media_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'content_review_media_not_accessible';
  end if;

  if nullif(btrim(coalesce(p_payload ->> 'evidence_id', '')), '') is not null then
    evidence_id_value := content_factory_private.require_uuid(
      p_payload, 'evidence_id'
    );
    select evidence.* into evidence_row
    from content_factory.content_review_evidence_sets evidence
    where evidence.organization_id = organization_id
      and evidence.id = evidence_id_value
    for update;
    if evidence_row.id is null
       or evidence_row.created_by <> user_id
       or evidence_row.media_object_id <> media_id_value
       or evidence_row.source_sha256_snapshot <> media_row.sha256
       or evidence_row.source_mime_type <> media_row.mime_type then
      raise exception using
        errcode = '42501',
        message = 'content_review_evidence_not_accessible';
    end if;
  end if;
  if media_row.mime_type = 'video/mp4' then
    if evidence_id_value is null then
      raise exception using
        errcode = '22023',
        message = 'content_review_video_evidence_required';
    end if;
    if evidence_row.status not in ('ready', 'consumed')
       or evidence_row.manifest_hash is null
       or evidence_row.frame_count <> evidence_row.expected_frame_count
       or (
         evidence_row.status = 'ready'
         and evidence_row.expires_at <= now()
       )
       or (
         select count(*)
         from content_factory.content_review_evidence_frames frame
         where frame.organization_id = organization_id
           and frame.evidence_set_id = evidence_id_value
       ) <> evidence_row.expected_frame_count then
      raise exception using
        errcode = '55000',
        message = 'content_review_video_evidence_not_ready';
    end if;
    if coalesce(p_payload -> 'technical_metrics', '{}'::jsonb)
         is distinct from evidence_row.technical_metrics then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_metrics_mismatch';
    end if;
  elsif evidence_id_value is not null then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_media_type_invalid';
  end if;

  -- The legacy start function used to cancel every queued row older than two
  -- minutes.  Every newly queued run is now server-owned, including images;
  -- keep same-command replay but block a competing start from cancelling it.
  if exists (
    select 1
    from content_factory.content_review_runs review
    where review.organization_id = organization_id
      and review.media_object_id = media_id_value
      and review.status in ('queued', 'processing')
      and review.idempotency_key is distinct from p_payload ->> 'idempotency_key'
  ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_already_active';
  end if;

  result_value := content_factory_private.creator_start_content_review_legacy(
    p_payload - 'evidence_id'
  );
  review_id_value := content_factory_private.require_uuid(
    result_value, 'review_id'
  );
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value
  for update;
  if review_row.id is null
     or review_row.media_object_id <> media_id_value then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_missing';
  end if;

  if evidence_id_value is not null then
    if review_row.evidence_set_id is null then
      if evidence_row.status <> 'ready' then
        raise exception using
          errcode = '23505',
          message = 'content_review_evidence_already_consumed';
      end if;
      update content_factory.content_review_runs review
      set evidence_set_id = evidence_id_value
      where review.organization_id = organization_id
        and review.id = review_id_value
        and review.status = 'queued'
        and review.evidence_set_id is null
      returning * into review_row;
      if review_row.evidence_set_id is null then
        raise exception using
          errcode = '55000',
          message = 'content_review_evidence_bind_conflict';
      end if;
      update content_factory.content_review_evidence_sets evidence
      set status = 'consumed',
          consumed_at = now()
      where evidence.organization_id = organization_id
        and evidence.id = evidence_id_value
        and evidence.status = 'ready';
      if not found then
        raise exception using
          errcode = '23505',
          message = 'content_review_evidence_already_consumed';
      end if;
    elsif review_row.evidence_set_id <> evidence_id_value
       or evidence_row.status <> 'consumed' then
      raise exception using
        errcode = '23505',
        message = 'content_review_evidence_bind_conflict';
    end if;
  end if;

  return result_value || jsonb_build_object(
    'evidence_id', evidence_id_value,
    'evidence_status', case
      when evidence_id_value is null then null
      else 'consumed'
    end
  );
end;
$$;


create or replace function public.creator_commit_content_review_evidence(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  idempotency_key_value text;
  evidence_id_value uuid;
  evidence_row content_factory.content_review_evidence_sets%rowtype;
  media_row content_factory.media_objects%rowtype;
  frames_value jsonb;
  technical_metrics_value jsonb;
  frame_value jsonb;
  ordinal_value integer;
  object_name_value text;
  expected_object_name text;
  sha256_value text;
  size_bytes_value bigint;
  timecode_value numeric(10,3);
  previous_timecode numeric(10,3);
  storage_metadata jsonb;
  storage_owner text;
  storage_size bigint;
  storage_mime text;
  storage_object_count integer;
  total_size_value bigint := 0;
  manifest_frames jsonb := '[]'::jsonb;
  manifest_hash_value text;
  replay jsonb;
  request_payload jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 65536
     or p_payload - array[
       'organization_id', 'idempotency_key', 'evidence_id',
       'frames', 'technical_metrics'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_commit_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  evidence_id_value := content_factory_private.require_uuid(
    p_payload, 'evidence_id'
  );
  frames_value := p_payload -> 'frames';
  technical_metrics_value := coalesce(
    p_payload -> 'technical_metrics',
    '{}'::jsonb
  );
  if jsonb_typeof(frames_value) <> 'array'
     or jsonb_typeof(technical_metrics_value) <> 'object'
     or length(technical_metrics_value::text) > 32768 then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_manifest_invalid';
  end if;

  select evidence.* into evidence_row
  from content_factory.content_review_evidence_sets evidence
  where evidence.organization_id = organization_id
    and evidence.id = evidence_id_value
  for update;
  if evidence_row.id is null
     or evidence_row.created_by <> user_id then
    raise exception using
      errcode = '42501',
      message = 'content_review_evidence_not_accessible';
  end if;
  if jsonb_array_length(frames_value) <> evidence_row.expected_frame_count then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_frame_count_invalid';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = evidence_row.media_object_id
  for share;
  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.mime_type <> evidence_row.source_mime_type
     or media_row.sha256 <> evidence_row.source_sha256_snapshot then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_source_stale';
  end if;

  for frame_value, ordinal_value in
    select item.value, item.ordinality::integer
    from jsonb_array_elements(frames_value) with ordinality item(value, ordinality)
    order by item.ordinality
  loop
    if jsonb_typeof(frame_value) <> 'object'
       or frame_value - array[
         'object_name', 'sha256', 'size_bytes', 'timecode_seconds'
       ]::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_frame_invalid';
    end if;
    object_name_value := content_factory_private.require_text(
      frame_value, 'object_name', 44, 1000
    );
    sha256_value := lower(content_factory_private.require_text(
      frame_value, 'sha256', 64, 64
    ));
    if sha256_value !~ '^[0-9a-f]{64}$'
       or jsonb_typeof(frame_value -> 'size_bytes') <> 'number'
       or coalesce(frame_value ->> 'size_bytes', '') !~ '^[0-9]+$'
       or jsonb_typeof(frame_value -> 'timecode_seconds') <> 'number'
       or coalesce(frame_value ->> 'timecode_seconds', '')
            !~ '^[0-9]+([.][0-9]{1,3})?$' then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_frame_invalid';
    end if;
    begin
      size_bytes_value := (frame_value ->> 'size_bytes')::bigint;
      timecode_value := (frame_value ->> 'timecode_seconds')::numeric(10,3);
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_frame_invalid';
    end;
    if size_bytes_value not between 128 and 524288
       or timecode_value not between 0 and 3600
       or (previous_timecode is not null and timecode_value <= previous_timecode) then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_frame_invalid';
    end if;
    previous_timecode := timecode_value;
    expected_object_name := evidence_row.object_prefix || '/frame-'
      || lpad(ordinal_value::text, 2, '0') || '.jpg';
    if object_name_value <> expected_object_name
       or split_part(object_name_value, '/', 1) <> organization_id::text
       or split_part(object_name_value, '/', 2) <> user_id::text then
      raise exception using
        errcode = '42501',
        message = 'content_review_evidence_object_path_invalid';
    end if;

    perform pg_advisory_xact_lock(
      hashtext('contentengine-private'),
      hashtext(object_name_value)
    );
    select storage_object.metadata,
           coalesce(
             to_jsonb(storage_object) ->> 'owner_id',
             to_jsonb(storage_object) ->> 'owner'
           )
      into storage_metadata, storage_owner
    from storage.objects storage_object
    where storage_object.bucket_id = 'contentengine-private'
      and storage_object.name = object_name_value
    for share;
    if storage_metadata is null
       or storage_owner is distinct from user_id::text
       or jsonb_typeof(storage_metadata) <> 'object'
       or coalesce(storage_metadata ->> 'size', '') !~ '^[0-9]+$'
       or nullif(btrim(coalesce(storage_metadata ->> 'mimetype', '')), '')
            is null then
      raise exception using
        errcode = 'P0002',
        message = 'content_review_evidence_storage_object_invalid';
    end if;
    begin
      storage_size := (storage_metadata ->> 'size')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_storage_metadata_invalid';
    end;
    storage_mime := lower(btrim(storage_metadata ->> 'mimetype'));
    if storage_size <> size_bytes_value
       or storage_mime <> 'image/jpeg' then
      raise exception using
        errcode = '22023',
        message = 'content_review_evidence_storage_metadata_mismatch';
    end if;

    total_size_value := total_size_value + size_bytes_value;
    if total_size_value > 2359296 then
      raise exception using
        errcode = '54000',
        message = 'content_review_evidence_total_size_exceeded';
    end if;
    manifest_frames := manifest_frames || jsonb_build_array(
      jsonb_build_object(
        'ordinal', ordinal_value,
        'object_name', object_name_value,
        'sha256', sha256_value,
        'size_bytes', size_bytes_value,
        'mime_type', 'image/jpeg',
        'timecode_seconds', timecode_value
      )
    );
  end loop;

  select count(*)::integer into storage_object_count
  from storage.objects storage_object
  where storage_object.bucket_id = 'contentengine-private'
    and storage_object.name like evidence_row.object_prefix || '/%';
  if storage_object_count <> evidence_row.expected_frame_count then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_storage_object_count_mismatch';
  end if;

  manifest_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'media_id', evidence_row.media_object_id,
      'source_sha256', evidence_row.source_sha256_snapshot,
      'frames', manifest_frames,
      'technical_metrics', technical_metrics_value
    )
  );
  request_payload := jsonb_build_object(
    'evidence_id', evidence_id_value,
    'manifest_hash', manifest_hash_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_commit_content_review_evidence',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  if evidence_row.status = 'ready' then
    if evidence_row.manifest_hash <> manifest_hash_value then
      raise exception using
        errcode = '23505',
        message = 'content_review_evidence_manifest_conflict';
    end if;
  elsif evidence_row.status <> 'preparing' then
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_not_preparing';
  elsif evidence_row.expires_at <= now() then
    update content_factory.content_review_evidence_sets evidence
    set status = 'expired'
    where evidence.id = evidence_id_value
      and evidence.status = 'preparing';
    raise exception using
      errcode = '55000',
      message = 'content_review_evidence_expired';
  else
    insert into content_factory.content_review_evidence_frames (
      organization_id, evidence_set_id, ordinal, bucket_id, object_name,
      mime_type, size_bytes, sha256, timecode_seconds
    )
    select
      organization_id,
      evidence_id_value,
      (item.value ->> 'ordinal')::integer,
      'contentengine-private',
      item.value ->> 'object_name',
      item.value ->> 'mime_type',
      (item.value ->> 'size_bytes')::bigint,
      item.value ->> 'sha256',
      (item.value ->> 'timecode_seconds')::numeric(10,3)
    from jsonb_array_elements(manifest_frames) item(value)
    order by (item.value ->> 'ordinal')::integer;

    update content_factory.content_review_evidence_sets evidence
    set status = 'ready',
        frame_count = evidence.expected_frame_count,
        total_size_bytes = total_size_value,
        technical_metrics = technical_metrics_value,
        manifest_hash = manifest_hash_value,
        ready_at = now()
    where evidence.id = evidence_id_value
      and evidence.status = 'preparing'
    returning * into evidence_row;
    if evidence_row.status <> 'ready' then
      raise exception using
        errcode = '55000',
        message = 'content_review_evidence_commit_conflict';
    end if;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'evidence_id', evidence_id_value,
    'status', 'ready',
    'media_id', evidence_row.media_object_id,
    'source_media_sha256', evidence_row.source_sha256_snapshot,
    'object_prefix', evidence_row.object_prefix,
    'manifest_hash', manifest_hash_value,
    'frame_count', evidence_row.expected_frame_count,
    'total_size_bytes', total_size_value,
    'frames', manifest_frames,
    'expires_at', evidence_row.expires_at
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_commit_content_review_evidence',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;


create or replace function
  content_factory_private.reject_content_review_evidence_frame_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'content_review_evidence_frame_immutable';
end;
$$;

create or replace function
  content_factory_private.guard_content_review_attempt()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_deletion_forbidden';
  end if;
  if new.id is distinct from old.id
     or new.organization_id is distinct from old.organization_id
     or new.review_id is distinct from old.review_id
     or new.attempt_no is distinct from old.attempt_no
     or new.lease_token is distinct from old.lease_token
     or new.provider_idempotency_key is distinct from old.provider_idempotency_key
     or new.claimed_at is distinct from old.claimed_at
     or new.created_at is distinct from old.created_at then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_identity_immutable';
  end if;
  if old.status in (
       'completed', 'retry_wait', 'outcome_unknown', 'dead_letter'
     ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_terminal';
  end if;
  if new.status = old.status then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_update_without_transition';
  end if;
  if not (
    (old.status = 'claimed'
      and new.status in ('dispatching', 'retry_wait', 'dead_letter'))
    or (old.status = 'dispatching'
      and new.status in ('completed', 'outcome_unknown'))
  ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_transition_invalid';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists guard_content_review_evidence_set
  on content_factory.content_review_evidence_sets;
create trigger guard_content_review_evidence_set
before update or delete on content_factory.content_review_evidence_sets
for each row execute function
  content_factory_private.guard_content_review_evidence_set();

drop trigger if exists reject_content_review_evidence_frame_mutation
  on content_factory.content_review_evidence_frames;
create trigger reject_content_review_evidence_frame_mutation
before update or delete on content_factory.content_review_evidence_frames
for each row execute function
  content_factory_private.reject_content_review_evidence_frame_mutation();

drop trigger if exists guard_content_review_attempt
  on content_factory.content_review_attempts;
create trigger guard_content_review_attempt
before update or delete on content_factory.content_review_attempts
for each row execute function
  content_factory_private.guard_content_review_attempt();

-- Preserve the original append-only run history while permitting the narrow
-- operational mutations needed before a provider dispatch.  A run remains
-- queued while a worker prepares signed evidence; only the irreversible
-- dispatch marker moves it to processing.
create or replace function content_factory_private.guard_content_review_run()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_deletion_forbidden';
  end if;

  if new.organization_id <> old.organization_id
     or new.media_object_id <> old.media_object_id
     or new.requested_by <> old.requested_by
     or new.parent_review_id is distinct from old.parent_review_id
     or new.media_sha256_snapshot <> old.media_sha256_snapshot
     or new.input <> old.input
     or new.ruleset_version <> old.ruleset_version
     or new.request_hash <> old.request_hash
     or new.idempotency_key <> old.idempotency_key
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_identity_immutable';
  end if;

  if old.evidence_set_id is not null
     and new.evidence_set_id is distinct from old.evidence_set_id then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_evidence_immutable';
  end if;
  if old.evidence_set_id is null and new.evidence_set_id is not null
     and old.status <> 'queued' then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_evidence_bind_invalid';
  end if;
  if new.attempt_count < old.attempt_count
     or new.attempt_count > old.attempt_count + 1 then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_attempt_count_invalid';
  end if;
  if old.dead_lettered_at is not null
     and new.dead_lettered_at is distinct from old.dead_lettered_at then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_dead_letter_immutable';
  end if;

  if old.status in ('completed', 'failed', 'cancelled')
     and new is distinct from old then
    -- A dispatched request whose outcome cannot be proved is already terminal
    -- when the legacy completion routine returns.  Allow the fencing wrapper
    -- to add the durable dead-letter marker exactly once, without opening any
    -- other terminal field to mutation.
    if not (
      old.status = 'failed'
      and old.dead_lettered_at is null
      and new.dead_lettered_at is not null
      and (
        to_jsonb(new) - array['dead_lettered_at', 'updated_at']::text[]
      ) is not distinct from (
        to_jsonb(old) - array['dead_lettered_at', 'updated_at']::text[]
      )
    ) then
      raise exception using
        errcode = '55000',
        message = 'content_review_run_terminal';
    end if;
  end if;

  if new.status = old.status and new is distinct from old then
    if old.status = 'queued' then
      if (
        to_jsonb(new) - array[
          'evidence_set_id', 'attempt_count', 'next_attempt_at', 'updated_at'
        ]::text[]
      ) is distinct from (
        to_jsonb(old) - array[
          'evidence_set_id', 'attempt_count', 'next_attempt_at', 'updated_at'
        ]::text[]
      ) then
        raise exception using
          errcode = '55000',
          message = 'content_review_run_update_without_transition';
      end if;
    elsif old.status = 'failed'
       and old.dead_lettered_at is null
       and new.dead_lettered_at is not null
       and (
         to_jsonb(new) - array['dead_lettered_at', 'updated_at']::text[]
       ) is not distinct from (
         to_jsonb(old) - array['dead_lettered_at', 'updated_at']::text[]
       ) then
      null;
    elsif old.status = 'processing' then
      if (
        to_jsonb(new) - array['dead_lettered_at', 'updated_at']::text[]
      ) is distinct from (
        to_jsonb(old) - array['dead_lettered_at', 'updated_at']::text[]
      ) or (
        new.dead_lettered_at is distinct from old.dead_lettered_at
        and not (
          old.dead_lettered_at is null and new.dead_lettered_at is not null
        )
      ) then
        raise exception using
          errcode = '55000',
          message = 'content_review_run_update_without_transition';
      end if;
    else
      raise exception using
        errcode = '55000',
        message = 'content_review_run_update_without_transition';
    end if;
  end if;

  if new.status <> old.status and not (
    (old.status = 'queued'
      and new.status in ('processing', 'failed', 'cancelled'))
    or (old.status = 'processing'
      and new.status in ('completed', 'failed', 'cancelled'))
  ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_status_transition_invalid';
  end if;

  if old.status = 'queued' and new.status = 'processing' then
    new.started_at := coalesce(new.started_at, now());
    new.lease_expires_at := coalesce(
      new.lease_expires_at,
      now() + interval '10 minutes'
    );
    new.next_attempt_at := null;
  end if;

  if new.status in ('completed', 'failed', 'cancelled')
     and new.status <> old.status then
    new.finished_at := coalesce(new.finished_at, now());
    new.lease_expires_at := null;
    new.next_attempt_at := null;
  end if;

  new.updated_at := now();
  return new;
end;
$$;

create or replace function public.creator_prepare_content_review_evidence(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  idempotency_key_value text;
  media_id_value uuid;
  frame_count_value integer;
  media_row content_factory.media_objects%rowtype;
  evidence_id_value uuid := extensions.gen_random_uuid();
  object_prefix_value text;
  object_names_value jsonb;
  replay jsonb;
  request_payload jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 4096
     or p_payload - array[
       'organization_id', 'idempotency_key', 'media_id', 'frame_count'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_prepare_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  media_id_value := content_factory_private.require_uuid(p_payload, 'media_id');
  if jsonb_typeof(p_payload -> 'frame_count') <> 'number'
     or coalesce(p_payload ->> 'frame_count', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_frame_count_invalid';
  end if;
  frame_count_value := (p_payload ->> 'frame_count')::integer;
  if frame_count_value not between 4 and 5 then
    raise exception using
      errcode = '22023',
      message = 'content_review_evidence_frame_count_invalid';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where media.organization_id = organization_id
    and media.id = media_id_value
    and media.status = 'ready'
    and media.mime_type = 'video/mp4'
    and (
      manager_scope
      or media.owner_id = user_id
      or task.assignee_id = user_id
    )
  for share of media;
  if media_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'content_review_evidence_media_not_accessible';
  end if;

  request_payload := jsonb_build_object(
    'media_id', media_id_value,
    'frame_count', frame_count_value,
    'source_sha256', media_row.sha256
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_prepare_content_review_evidence',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('content_review_evidence_prepare')
  );
  update content_factory.content_review_evidence_sets evidence
  set status = 'expired'
  where evidence.organization_id = organization_id
    and evidence.created_by = user_id
    and evidence.status = 'preparing'
    and evidence.expires_at <= now();
  if (
    select count(*)
    from content_factory.content_review_evidence_sets evidence
    where evidence.organization_id = organization_id
      and evidence.created_by = user_id
      and evidence.status = 'preparing'
  ) >= 10 then
    raise exception using
      errcode = '54000',
      message = 'content_review_evidence_active_limit';
  end if;
  if (
    select count(*)
    from content_factory.content_review_evidence_sets evidence
    where evidence.organization_id = organization_id
      and evidence.created_by = user_id
      and evidence.created_at >= now() - interval '24 hours'
  ) >= 100 then
    raise exception using
      errcode = '54000',
      message = 'content_review_evidence_daily_limit';
  end if;

  object_prefix_value := organization_id::text || '/' || user_id::text
    || '/review-evidence/' || evidence_id_value::text;
  select jsonb_agg(
    object_prefix_value || '/frame-' || lpad(item::text, 2, '0') || '.jpg'
    order by item
  ) into object_names_value
  from generate_series(1, frame_count_value) item;

  insert into content_factory.content_review_evidence_sets (
    id, organization_id, media_object_id, created_by, status,
    source_mime_type, source_sha256_snapshot, object_prefix,
    expected_frame_count, idempotency_key, expires_at
  ) values (
    evidence_id_value, organization_id, media_id_value, user_id, 'preparing',
    'video/mp4', media_row.sha256, object_prefix_value,
    frame_count_value, idempotency_key_value, now() + interval '30 minutes'
  );

  result_value := jsonb_build_object(
    'ok', true,
    'evidence_id', evidence_id_value,
    'status', 'preparing',
    'media_id', media_id_value,
    'source_media_sha256', media_row.sha256,
    'object_prefix', object_prefix_value,
    'frame_object_names', object_names_value,
    'frame_count', frame_count_value,
    'expires_at', (
      select evidence.expires_at
      from content_factory.content_review_evidence_sets evidence
      where evidence.id = evidence_id_value
    )
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_prepare_content_review_evidence',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

-- The legacy status RPC used browser polling as a queue watchdog and cancelled
-- every queued row after two minutes.  Durable evidence-backed rows are now
-- owned by the server worker, so status reads for those rows must be read-only.
alter function public.creator_content_review_status(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_content_review_status(jsonb)
  rename to creator_content_review_status_legacy;
revoke all on function
  content_factory_private.creator_content_review_status_legacy(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_content_review_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  task_assignee_id uuid;
  attempt_value jsonb;
  attempt_status_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'review_id'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_status_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  if nullif(btrim(coalesce(p_payload ->> 'organization_id', '')), '')
       is not null then
    organization_id := content_factory_private.resolve_organization(p_payload);
    actor_role := content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
  else
    select review.organization_id, membership.role
      into organization_id, actor_role
    from content_factory.content_review_runs review
    join content_factory.memberships membership
      on membership.organization_id = review.organization_id
     and membership.profile_id = user_id
     and membership.status = 'active'
    join content_factory.organizations organization
      on organization.id = review.organization_id
     and organization.status = 'active'
    where review.id = review_id_value;
    if organization_id is null then
      raise exception using
        errcode = '22023',
        message = 'content_review_not_found';
    end if;
    perform content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
  end if;
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value;
  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = review_row.media_object_id;
  if media_row.task_id is not null then
    select task.assignee_id into task_assignee_id
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.id = media_row.task_id;
  end if;
  if not manager_scope
     and review_row.requested_by <> user_id
     and media_row.owner_id <> user_id
     and task_assignee_id is distinct from user_id then
    raise exception using
      errcode = '42501',
      message = 'content_review_not_allowed';
  end if;

  select attempt.status, jsonb_build_object(
    'id', attempt.id,
    'attempt_no', attempt.attempt_no,
    'status', attempt.status,
    'claimed_at', attempt.claimed_at,
    'lease_expires_at', attempt.lease_expires_at,
    'error_code', attempt.error_code
  ) into attempt_status_value, attempt_value
  from content_factory.content_review_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.review_id = review_id_value
  order by attempt.attempt_no desc
  limit 1;

  -- Polling is observation-only for all queued runs and for a processing run
  -- owned by the attempt journal.  Only a legacy processing row without an
  -- active attempt may use the old watchdog behavior.
  if review_row.status not in ('queued', 'processing')
     or (
       review_row.status = 'processing'
       and coalesce(attempt_status_value, '') not in ('claimed', 'dispatching')
     ) then
    return content_factory_private.creator_content_review_status_legacy(
      p_payload
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'run', jsonb_build_object(
      'id', review_row.id,
      'status', review_row.status,
      'media_id', review_row.media_object_id,
      'requested_by', review_row.requested_by,
      'parent_review_id', review_row.parent_review_id,
      'input', review_row.input,
      'result', review_row.result,
      'moderation', review_row.moderation,
      'ruleset_version', review_row.ruleset_version,
      'model_provider', review_row.model_provider,
      'model_version', review_row.model_version,
      'media_sha256_snapshot', review_row.media_sha256_snapshot,
      'media_is_stale', (
        media_row.status <> 'ready'
        or media_row.sha256 <> review_row.media_sha256_snapshot
      ),
      'evidence_id', review_row.evidence_set_id,
      'attempt_count', review_row.attempt_count,
      'next_attempt_at', review_row.next_attempt_at,
      'error_code', review_row.error_code,
      'error_message', review_row.error_message,
      'created_at', review_row.created_at,
      'started_at', review_row.started_at,
      'lease_expires_at', review_row.lease_expires_at,
      'finished_at', review_row.finished_at
    ),
    'media', jsonb_build_object(
      'id', media_row.id,
      'owner_id', media_row.owner_id,
      'task_id', media_row.task_id,
      'product_id', media_row.product_id,
      'object_name', media_row.object_name,
      'mime_type', media_row.mime_type,
      'size_bytes', media_row.size_bytes,
      'sha256', media_row.sha256,
      'status', media_row.status,
      'metadata', media_row.metadata
    ),
    'attempt', attempt_value,
    'decision', null
  );
end;
$$;

-- Fence every durable MP4 completion with the attempt lease that was marked
-- before the provider POST.  The mature completion routine remains the sole
-- validator/writer of the review result; this wrapper journals its outcome.
alter function public.system_complete_content_review(jsonb)
  set schema content_factory_private;
alter function content_factory_private.system_complete_content_review(jsonb)
  rename to system_complete_content_review_unfenced_legacy;
revoke all on function
  content_factory_private.system_complete_content_review_unfenced_legacy(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.system_complete_content_review(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_id_value uuid;
  attempt_id_value uuid;
  lease_token_value uuid;
  provider_request_id_value text;
  review_row content_factory.content_review_runs%rowtype;
  attempt_row content_factory.content_review_attempts%rowtype;
  legacy_payload_value jsonb;
  legacy_result_value jsonb;
  payload_completion_hash_value text;
  outcome_unknown_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 362000
     or p_payload - array[
       'review_id', 'attempt_id', 'lease_token', 'provider_request_id',
       'status', 'result', 'moderation', 'ruleset_version',
       'model_provider', 'model_version', 'error_code', 'error_message'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_completion_payload_invalid';
  end if;

  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.id = review_id_value;
  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;

  -- Compatibility is intentionally limited to pre-existing still-image runs.
  -- Every evidence-backed MP4 must provide all fencing fields.
  if review_row.evidence_set_id is null
     and not (p_payload ? 'attempt_id')
     and not (p_payload ? 'lease_token')
     and not (p_payload ? 'provider_request_id') then
    return
      content_factory_private.system_complete_content_review_unfenced_legacy(
        p_payload
      );
  end if;

  attempt_id_value := content_factory_private.require_uuid(
    p_payload, 'attempt_id'
  );
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  if p_payload ? 'provider_request_id' then
    if jsonb_typeof(p_payload -> 'provider_request_id') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'content_review_provider_request_id_invalid';
    end if;
    provider_request_id_value := nullif(
      btrim(p_payload ->> 'provider_request_id'), ''
    );
    if provider_request_id_value is null
       or length(provider_request_id_value) not between 3 and 240
       or provider_request_id_value ~ '[[:cntrl:]]' then
      raise exception using
        errcode = '22023',
        message = 'content_review_provider_request_id_invalid';
    end if;
  end if;

  perform pg_advisory_xact_lock(
    hashtext('content-review-run'), hashtext(review_id_value::text)
  );

  -- Attempt first is the global lock order used by begin/release/reconcile.
  select attempt.* into attempt_row
  from content_factory.content_review_attempts attempt
  where attempt.id = attempt_id_value
  for update;
  if attempt_row.id is null
     or attempt_row.review_id <> review_id_value then
    raise exception using
      errcode = 'P0002',
      message = 'content_review_attempt_not_found';
  end if;
  if attempt_row.lease_token <> lease_token_value then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_lease_mismatch';
  end if;

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = attempt_row.organization_id
    and review.id = review_id_value
  for update;
  if review_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_review_missing';
  end if;

  legacy_payload_value := p_payload - array[
    'attempt_id', 'lease_token', 'provider_request_id'
  ]::text[];
  payload_completion_hash_value := content_factory_private.json_hash(
    legacy_payload_value - 'review_id'
  );

  if attempt_row.status in ('completed', 'outcome_unknown') then
    if provider_request_id_value is not null
       and attempt_row.provider_request_id is distinct from
             provider_request_id_value then
      raise exception using
        errcode = '23505',
        message = 'content_review_provider_request_id_conflict';
    end if;
    if attempt_row.status = 'completed'
       and attempt_row.completion_hash is distinct from
             payload_completion_hash_value then
      raise exception using
        errcode = '23505',
        message = 'content_review_completion_conflict';
    end if;
    return jsonb_strip_nulls(jsonb_build_object(
      'ok', true,
      'review_id', review_row.id,
      'attempt_id', attempt_row.id,
      'attempt_status', attempt_row.status,
      'status', review_row.status,
      'error_code', review_row.error_code,
      'provider_request_id', attempt_row.provider_request_id,
      'idempotent', true
    ));
  end if;

  if attempt_row.status <> 'dispatching'
     or attempt_row.provider_dispatch_started_at is null
     or review_row.status <> 'processing' then
    raise exception using
      errcode = '55000',
      message = 'content_review_attempt_not_dispatching';
  end if;

  legacy_result_value :=
    content_factory_private.system_complete_content_review_unfenced_legacy(
      legacy_payload_value
    );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = attempt_row.organization_id
    and review.id = review_id_value;

  outcome_unknown_value := review_row.status = 'failed' and (
    review_row.error_code = 'provider_outcome_unknown'
    or review_row.error_code = 'processing_lease_expired'
  );

  update content_factory.content_review_attempts attempt
  set status = case
        when outcome_unknown_value then 'outcome_unknown'
        else 'completed'
      end,
      lease_expires_at = null,
      provider_request_id = coalesce(
        provider_request_id_value, attempt.provider_request_id
      ),
      -- Journal the exact completion request for replay fencing.  The review
      -- hash can intentionally differ when validation normalizes the request
      -- into a terminal failure (for example, source bytes changed mid-run).
      completion_hash = payload_completion_hash_value,
      error_code = case
        when outcome_unknown_value then 'provider_outcome_unknown'
        when review_row.status = 'failed' then review_row.error_code
        else null
      end,
      error_message = case
        when outcome_unknown_value then
          coalesce(
            review_row.error_message,
            'Provider dispatch started, but its final outcome is unknown.'
          )
        when review_row.status = 'failed' then review_row.error_message
        else null
      end,
      finished_at = now()
  where attempt.id = attempt_id_value
    and attempt.status = 'dispatching'
  returning * into attempt_row;
  if attempt_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'content_review_completion_fence_conflict';
  end if;

  if outcome_unknown_value and review_row.dead_lettered_at is null then
    update content_factory.content_review_runs review
    set dead_lettered_at = now()
    where review.id = review_id_value
      and review.status = 'failed'
      and review.dead_lettered_at is null
    returning * into review_row;
  end if;

  return jsonb_strip_nulls(
    legacy_result_value || jsonb_build_object(
      'review_id', review_row.id,
      'attempt_id', attempt_row.id,
      'attempt_status', attempt_row.status,
      'provider_request_id', attempt_row.provider_request_id,
      'idempotent', false
    )
  );
end;
$$;

-- Reconcile pre-dispatch claims with bounded retries.  Once dispatching was
-- marked, an expired lease is outcome-unknown and is never posted again.
create or replace function public.system_reconcile_background_leases(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer := 50;
  remaining_value integer;
  retry_seconds integer;
  research_count integer := 0;
  review_count integer := 0;
  retried_count integer := 0;
  dead_lettered_count integer := 0;
  outcome_unknown_count integer := 0;
  legacy_expired_count integer := 0;
  attempt_candidate record;
  attempt_row content_factory.content_review_attempts%rowtype;
  review_row content_factory.content_review_runs%rowtype;
  completion_payload_value jsonb;
  timeout_message text :=
    'Processing lease expired safely. Start a new run manually after review.';
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 1024
     or p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'background_reconcile_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    begin
      limit_value := (p_payload ->> 'limit')::integer;
    exception
      when invalid_text_representation or numeric_value_out_of_range then
        raise exception using
          errcode = '22023',
          message = 'background_reconcile_limit_invalid';
    end;
  end if;
  if limit_value not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'background_reconcile_limit_invalid';
  end if;

  with expired as (
    select run.id
    from content_factory.product_research_runs run
    where run.status = 'processing'
      and run.lease_expires_at <= now()
    order by run.lease_expires_at, run.id
    for update skip locked
    limit limit_value
  )
  update content_factory.product_research_runs run
  set status = 'failed',
      error_code = 'processing_lease_expired',
      error_message = timeout_message,
      completion_hash = content_factory_private.json_hash(
        jsonb_build_object(
          'status', 'failed',
          'error_code', 'processing_lease_expired',
          'error_message', timeout_message
        )
      )
  from expired
  where run.id = expired.id
    and run.status = 'processing'
    and run.lease_expires_at <= now();
  get diagnostics research_count = row_count;

  for attempt_candidate in
    select attempt.id, attempt.review_id
    from content_factory.content_review_attempts attempt
    join content_factory.content_review_runs review
      on review.organization_id = attempt.organization_id
     and review.id = attempt.review_id
    where attempt.status in ('claimed', 'dispatching')
      and attempt.lease_expires_at <= now()
      and (
        (attempt.status = 'claimed' and review.status = 'queued')
        or (attempt.status = 'dispatching' and review.status = 'processing')
    )
    order by attempt.lease_expires_at, attempt.id
    limit limit_value
  loop
    perform pg_advisory_xact_lock(
      hashtext('content-review-run'),
      hashtext(attempt_candidate.review_id::text)
    );
    select attempt.* into attempt_row
    from content_factory.content_review_attempts attempt
    where attempt.id = attempt_candidate.id
    for update;
    if attempt_row.id is null
       or attempt_row.status not in ('claimed', 'dispatching')
       or attempt_row.lease_expires_at > now() then
      continue;
    end if;
    select review.* into review_row
    from content_factory.content_review_runs review
    where review.organization_id = attempt_row.organization_id
      and review.id = attempt_row.review_id
    for update;
    if review_row.id is null
       or (
         attempt_row.status = 'claimed'
         and review_row.status <> 'queued'
       )
       or (
         attempt_row.status = 'dispatching'
         and review_row.status <> 'processing'
       ) then
      continue;
    end if;

    if attempt_row.status = 'claimed' and attempt_row.attempt_no < 3 then
      retry_seconds := least(
        300,
        30 * power(2, attempt_row.attempt_no - 1)::integer
      );
      update content_factory.content_review_attempts attempt
      set status = 'retry_wait',
          lease_expires_at = null,
          error_code = 'content_review_claim_lease_expired',
          error_message =
            'Worker lease expired before provider dispatch; retry is safe.',
          finished_at = now()
      where attempt.id = attempt_row.id
        and attempt.status = 'claimed';
      update content_factory.content_review_runs review
      set next_attempt_at = now() + make_interval(secs => retry_seconds)
      where review.id = review_row.id
        and review.status = 'queued';
      retried_count := retried_count + 1;
      review_count := review_count + 1;
    elsif attempt_row.status = 'claimed' then
      completion_payload_value := jsonb_build_object(
        'status', 'failed',
        'error_code', 'content_review_dispatch_dead_letter',
        'error_message',
          'Worker could not start provider dispatch after three attempts.'
      );
      update content_factory.content_review_attempts attempt
      set status = 'dead_letter',
          lease_expires_at = null,
          error_code = 'content_review_claim_lease_expired',
          error_message =
            'Worker lease expired before provider dispatch for the third time.',
          finished_at = now()
      where attempt.id = attempt_row.id
        and attempt.status = 'claimed';
      update content_factory.content_review_runs review
      set status = 'failed',
          error_code = 'content_review_dispatch_dead_letter',
          error_message = completion_payload_value ->> 'error_message',
          completion_hash = content_factory_private.json_hash(
            completion_payload_value
          ),
          dead_lettered_at = now()
      where review.id = review_row.id
        and review.status = 'queued';
      dead_lettered_count := dead_lettered_count + 1;
      review_count := review_count + 1;
    else
      completion_payload_value := jsonb_build_object(
        'status', 'failed',
        'error_code', 'provider_outcome_unknown',
        'error_message',
          'Provider dispatch started, but its final outcome is unknown.'
      );
      update content_factory.content_review_attempts attempt
      set status = 'outcome_unknown',
          lease_expires_at = null,
          error_code = 'provider_outcome_unknown',
          error_message = completion_payload_value ->> 'error_message',
          finished_at = now()
      where attempt.id = attempt_row.id
        and attempt.status = 'dispatching';
      update content_factory.content_review_runs review
      set status = 'failed',
          error_code = 'provider_outcome_unknown',
          error_message = completion_payload_value ->> 'error_message',
          completion_hash = content_factory_private.json_hash(
            completion_payload_value
          ),
          dead_lettered_at = now()
      where review.id = review_row.id
        and review.status = 'processing';
      outcome_unknown_count := outcome_unknown_count + 1;
      review_count := review_count + 1;
    end if;
  end loop;

  remaining_value := greatest(limit_value - review_count, 0);
  if remaining_value > 0 then
    with expired as (
      select review.id
      from content_factory.content_review_runs review
      where review.status = 'processing'
        and review.lease_expires_at <= now()
        and not exists (
          select 1
          from content_factory.content_review_attempts attempt
          where attempt.organization_id = review.organization_id
            and attempt.review_id = review.id
            and attempt.status in ('claimed', 'dispatching')
        )
      order by review.lease_expires_at, review.id
      for update skip locked
      limit remaining_value
    )
    update content_factory.content_review_runs review
    set status = 'failed',
        error_code = 'processing_lease_expired',
        error_message = timeout_message,
        completion_hash = content_factory_private.json_hash(
          jsonb_build_object(
            'status', 'failed',
            'error_code', 'processing_lease_expired',
            'error_message', timeout_message
          )
        )
    from expired
    where review.id = expired.id
      and review.status = 'processing'
      and review.lease_expires_at <= now();
    get diagnostics legacy_expired_count = row_count;
    review_count := review_count + legacy_expired_count;
  end if;

  return jsonb_build_object(
    'ok', true,
    'expired', jsonb_build_object(
      'research', research_count,
      'review', review_count
    ),
    'review_attempts', jsonb_build_object(
      'retried', retried_count,
      'dead_lettered', dead_lettered_count,
      'outcome_unknown', outcome_unknown_count,
      'legacy_failed', legacy_expired_count
    )
  );
end;
$$;

-- A committed evidence frame is registered durable content and must not be
-- deletable through the creator's "unregistered upload" cleanup policy.
create or replace function content_factory.storage_object_is_unregistered(
  p_bucket_id text,
  p_object_name text
)
returns boolean
language plpgsql
security definer
volatile
set search_path = ''
as $$
begin
  if auth.uid() is null
     or p_bucket_id <> 'contentengine-private'
     or split_part(p_object_name, '/', 2) <> auth.uid()::text then
    return false;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(p_bucket_id),
    hashtext(p_object_name)
  );

  return not exists (
    select 1
    from content_factory.media_objects media
    where media.bucket_id = p_bucket_id
      and media.object_name = p_object_name
  ) and not exists (
    select 1
    from content_factory.content_review_evidence_frames frame
    where frame.bucket_id = p_bucket_id
      and frame.object_name = p_object_name
  );
end;
$$;

-- Rows queued by the old browser-only MP4 flow cannot be made durable after
-- the fact.  Cancel them explicitly so no worker can dispatch without frames.
update content_factory.content_review_runs review
set status = 'cancelled',
    error_code = 'legacy_video_evidence_missing',
    error_message =
      'This legacy video review has no durable evidence. Start a new review.'
from content_factory.media_objects media
where review.organization_id = media.organization_id
  and review.media_object_id = media.id
  and review.status = 'queued'
  and review.evidence_set_id is null
  and media.mime_type = 'video/mp4';

revoke all on function public.creator_prepare_content_review_evidence(jsonb)
  from public, anon;
revoke all on function public.creator_commit_content_review_evidence(jsonb)
  from public, anon;
revoke all on function public.creator_start_content_review(jsonb)
  from public, anon;
revoke all on function public.creator_content_review_status(jsonb)
  from public, anon;
grant execute on function
  public.creator_prepare_content_review_evidence(jsonb) to authenticated;
grant execute on function
  public.creator_commit_content_review_evidence(jsonb) to authenticated;
grant execute on function public.creator_start_content_review(jsonb)
  to authenticated;
grant execute on function public.creator_content_review_status(jsonb)
  to authenticated;

revoke all on function public.system_claim_content_review(jsonb)
  from public, anon, authenticated;
revoke all on function
  public.system_begin_content_review_provider_dispatch(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_release_content_review_attempt(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_complete_content_review(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_reconcile_background_leases(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_claim_content_review(jsonb)
  to service_role;
grant execute on function
  public.system_begin_content_review_provider_dispatch(jsonb)
  to service_role;
grant execute on function public.system_release_content_review_attempt(jsonb)
  to service_role;
grant execute on function public.system_complete_content_review(jsonb)
  to service_role;
grant execute on function public.system_reconcile_background_leases(jsonb)
  to service_role;

revoke all on function
  content_factory_private.guard_content_review_evidence_set()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_content_review_evidence_frame_mutation()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_content_review_attempt()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_content_review_run()
  from public, anon, authenticated, service_role;

revoke all on function
  content_factory.storage_object_is_unregistered(text, text)
  from public, anon;
grant execute on function
  content_factory.storage_object_is_unregistered(text, text)
  to authenticated;

commit;

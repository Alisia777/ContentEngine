begin;

-- A generated-video release is a human decision about the exact rendered
-- bytes, not an inference from waveform levels or a free-form comment. Keep a
-- compact immutable assessment beside the immutable content-review decision.
create or replace function
  content_factory_private.content_review_sound_issue_codes_valid(
    p_value jsonb
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  item jsonb;
  item_value text;
  item_count integer := 0;
  distinct_count integer := 0;
begin
  if jsonb_typeof(p_value) <> 'array'
     or jsonb_array_length(p_value) > 10
     or length(p_value::text) > 512 then
    return false;
  end if;

  for item in
    select element.value
    from jsonb_array_elements(p_value) element(value)
  loop
    if jsonb_typeof(item) <> 'string' then
      return false;
    end if;
    item_value := item #>> '{}';
    if item_value not in (
      'slurred_words',
      'wrong_words',
      'foreign_accent',
      'numbers_units',
      'wrong_voice_tone',
      'lip_sync',
      'noise_clipping',
      'silence_dropout',
      'unexpected_audio',
      'other'
    ) then
      return false;
    end if;
  end loop;

  select count(*), count(distinct code.value)
    into item_count, distinct_count
  from jsonb_array_elements_text(p_value) code(value);
  return item_count = distinct_count;
exception
  when others then
    return false;
end;
$$;

revoke all on function
  content_factory_private.content_review_sound_issue_codes_valid(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.content_review_sound_note_valid(
    p_value text
  )
returns boolean
language sql
immutable
strict
set search_path = ''
as $$
  select length(p_value) <= 1000
    and regexp_replace(p_value, E'[\n\r\t]', '', 'g')
          !~ '[[:cntrl:]]'
$$;

revoke all on function
  content_factory_private.content_review_sound_note_valid(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.normalize_content_review_sound_assessment(
    p_value jsonb,
    p_decision text
  )
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  required_boolean_key text;
  audio_value boolean;
  status_value text;
  issue_codes_value jsonb;
  normalized_issue_codes jsonb;
  spoken_script_value boolean;
  diction_value boolean;
  voice_style_value boolean;
  audio_sync_value boolean;
  silence_expected_value boolean;
  note_value text;
begin
  if jsonb_typeof(p_value) <> 'object'
     or length(p_value::text) > 8192
     or p_value - array[
       'audio', 'status', 'issue_codes',
       'spoken_script_heard_exactly_confirmed',
       'diction_clear_confirmed', 'voice_style_confirmed',
       'audio_sync_confirmed', 'silence_expected_confirmed', 'note'
     ]::text[] <> '{}'::jsonb
     or not (
       p_value ?& array[
         'audio', 'status', 'issue_codes',
         'spoken_script_heard_exactly_confirmed',
         'diction_clear_confirmed', 'voice_style_confirmed',
         'audio_sync_confirmed', 'silence_expected_confirmed'
       ]::text[]
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_payload_invalid';
  end if;

  foreach required_boolean_key in array array[
    'audio',
    'spoken_script_heard_exactly_confirmed',
    'diction_clear_confirmed',
    'voice_style_confirmed',
    'audio_sync_confirmed',
    'silence_expected_confirmed'
  ]::text[]
  loop
    if jsonb_typeof(p_value -> required_boolean_key) <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'content_review_sound_assessment_boolean_invalid';
    end if;
  end loop;

  if jsonb_typeof(p_value -> 'status') <> 'string'
     or not content_factory_private
       .content_review_sound_issue_codes_valid(p_value -> 'issue_codes')
     or (
       p_value ? 'note'
       and jsonb_typeof(p_value -> 'note') <> 'string'
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_value_invalid';
  end if;

  audio_value := (p_value ->> 'audio')::boolean;
  status_value := p_value ->> 'status';
  issue_codes_value := p_value -> 'issue_codes';
  spoken_script_value :=
    (p_value ->> 'spoken_script_heard_exactly_confirmed')::boolean;
  diction_value :=
    (p_value ->> 'diction_clear_confirmed')::boolean;
  voice_style_value :=
    (p_value ->> 'voice_style_confirmed')::boolean;
  audio_sync_value :=
    (p_value ->> 'audio_sync_confirmed')::boolean;
  silence_expected_value :=
    (p_value ->> 'silence_expected_confirmed')::boolean;
  note_value := regexp_replace(
    replace(
      replace(coalesce(p_value ->> 'note', ''), E'\r\n', E'\n'),
      E'\r', E'\n'
    ),
    '^[[:space:]]+|[[:space:]]+$',
    '',
    'g'
  );

  if status_value not in ('clear', 'issues_found', 'silent_expected')
     or not content_factory_private
       .content_review_sound_note_valid(note_value) then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_value_invalid';
  end if;

  select coalesce(
           jsonb_agg(to_jsonb(code.value) order by code.value),
           '[]'::jsonb
         )
    into normalized_issue_codes
  from jsonb_array_elements_text(issue_codes_value) code(value);

  if status_value = 'clear' and (
       not audio_value
       or jsonb_array_length(normalized_issue_codes) <> 0
       or not spoken_script_value
       or not diction_value
       or not voice_style_value
       or not audio_sync_value
       or silence_expected_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_clear_invalid';
  end if;

  if status_value = 'issues_found' and (
       jsonb_array_length(normalized_issue_codes) = 0
       or silence_expected_value
       or (
         not audio_value
         and not (
           normalized_issue_codes @> '["unexpected_audio"]'::jsonb
         )
       )
       or (
         audio_value
         and normalized_issue_codes @>
           '["unexpected_audio"]'::jsonb
       )
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_issues_invalid';
  end if;

  if status_value = 'issues_found' and length(note_value) < 5 then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_issues_note_required';
  end if;

  if status_value = 'silent_expected' and (
       audio_value
       or jsonb_array_length(normalized_issue_codes) <> 0
       or spoken_script_value
       or diction_value
       or voice_style_value
       or audio_sync_value
       or not silence_expected_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_silence_invalid';
  end if;

  if status_value = 'issues_found'
     and p_decision not in ('needs_changes', 'rejected') then
    raise exception using
      errcode = '55000',
      message = 'content_review_sound_issues_block_approval';
  end if;

  return jsonb_build_object(
    'version', 'generated-video-sound-v1',
    'audio', audio_value,
    'status', status_value,
    'issue_codes', normalized_issue_codes,
    'spoken_script_heard_exactly_confirmed', spoken_script_value,
    'diction_clear_confirmed', diction_value,
    'voice_style_confirmed', voice_style_value,
    'audio_sync_confirmed', audio_sync_value,
    'silence_expected_confirmed', silence_expected_value,
    'note', note_value
  );
end;
$$;

revoke all on function
  content_factory_private.normalize_content_review_sound_assessment(
    jsonb, text
  )
  from public, anon, authenticated, service_role;

create table if not exists
  content_factory.content_review_sound_assessments (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid not null,
    media_object_id uuid not null,
    decision_id uuid,
    assessed_by uuid not null,
    assessment_version text not null default 'generated-video-sound-v1'
      check (assessment_version = 'generated-video-sound-v1'),
    audio boolean not null,
    status text not null
      check (status in ('clear', 'issues_found', 'silent_expected')),
    issue_codes jsonb not null default '[]'::jsonb
      check (
        content_factory_private
          .content_review_sound_issue_codes_valid(issue_codes)
      ),
    spoken_script_heard_exactly_confirmed boolean not null,
    diction_clear_confirmed boolean not null,
    voice_style_confirmed boolean not null,
    audio_sync_confirmed boolean not null,
    silence_expected_confirmed boolean not null,
    note text not null default ''
      check (
        content_factory_private.content_review_sound_note_valid(note)
      ),
    media_sha256_snapshot text not null
      check (media_sha256_snapshot ~ '^[0-9a-f]{64}$'),
    review_completion_hash text not null
      check (review_completion_hash ~ '^[0-9a-f]{64}$'),
    assessment_hash text not null
      check (assessment_hash ~ '^[0-9a-f]{64}$'),
    lineage_kind text not null
      check (
        lineage_kind in (
          'direct_decision', 'context_source', 'context_copy'
        )
      ),
    source_assessment_id uuid,
    lineage_depth smallint not null default 0
      check (lineage_depth between 0 and 1),
    created_at timestamptz not null default now(),
    unique (organization_id, review_id),
    unique (organization_id, id),
    unique (organization_id, assessment_hash),
    foreign key (organization_id, review_id)
      references content_factory.content_review_runs(organization_id, id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, assessed_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, review_id, decision_id)
      references content_factory.content_review_decisions(
        organization_id, review_id, id
      ),
    foreign key (organization_id, source_assessment_id)
      references content_factory.content_review_sound_assessments(
        organization_id, id
      ),
    check (
      (
        status = 'clear'
        and audio
        and jsonb_array_length(issue_codes) = 0
        and spoken_script_heard_exactly_confirmed
        and diction_clear_confirmed
        and voice_style_confirmed
        and audio_sync_confirmed
        and not silence_expected_confirmed
      )
      or (
        status = 'issues_found'
        and jsonb_array_length(issue_codes) between 1 and 10
        and not silence_expected_confirmed
        and (
          (audio and not (
            issue_codes @> '["unexpected_audio"]'::jsonb
          ))
          or (not audio and issue_codes @>
            '["unexpected_audio"]'::jsonb)
        )
      )
      or (
        status = 'silent_expected'
        and not audio
        and jsonb_array_length(issue_codes) = 0
        and not spoken_script_heard_exactly_confirmed
        and not diction_clear_confirmed
        and not voice_style_confirmed
        and not audio_sync_confirmed
        and silence_expected_confirmed
      )
    ),
    check (
      (lineage_kind = 'direct_decision'
        and decision_id is not null
        and source_assessment_id is null
        and lineage_depth = 0)
      or (lineage_kind = 'context_source'
        and decision_id is null
        and source_assessment_id is null
        and lineage_depth = 0)
      or (lineage_kind = 'context_copy'
        and decision_id is not null
        and source_assessment_id is not null
        and lineage_depth = 1)
    )
  );

create index if not exists content_review_sound_assessments_media_idx
  on content_factory.content_review_sound_assessments (
    organization_id, media_object_id, media_sha256_snapshot,
    created_at desc, id desc
  );

create index if not exists content_review_sound_assessments_source_idx
  on content_factory.content_review_sound_assessments (
    organization_id, source_assessment_id, created_at, id
  )
  where source_assessment_id is not null;

alter table content_factory.content_review_sound_assessments
  enable row level security;

revoke all on content_factory.content_review_sound_assessments
  from public, anon, authenticated;
grant all on content_factory.content_review_sound_assessments
  to service_role;

create or replace function
  content_factory_private.reject_content_review_sound_assessment_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'content_review_sound_assessment_immutable';
end;
$$;

revoke all on function
  content_factory_private
    .reject_content_review_sound_assessment_mutation()
  from public, anon, authenticated, service_role;

drop trigger if exists reject_content_review_sound_assessment_mutation
  on content_factory.content_review_sound_assessments;
create trigger reject_content_review_sound_assessment_mutation
before update or delete on
  content_factory.content_review_sound_assessments
for each row execute function
  content_factory_private
    .reject_content_review_sound_assessment_mutation();

create or replace function
  content_factory_private.content_review_sound_assessment_json(
    p_assessment content_factory.content_review_sound_assessments
  )
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
begin
  if p_assessment.id is null then
    return null;
  end if;
  return jsonb_build_object(
    'id', p_assessment.id,
    'version', p_assessment.assessment_version,
    'review_id', p_assessment.review_id,
    'media_id', p_assessment.media_object_id,
    'decision_id', p_assessment.decision_id,
    'assessed_by', p_assessment.assessed_by,
    'audio', p_assessment.audio,
    'status', p_assessment.status,
    'issue_codes', p_assessment.issue_codes,
    'spoken_script_heard_exactly_confirmed',
      p_assessment.spoken_script_heard_exactly_confirmed,
    'diction_clear_confirmed',
      p_assessment.diction_clear_confirmed,
    'voice_style_confirmed', p_assessment.voice_style_confirmed,
    'audio_sync_confirmed', p_assessment.audio_sync_confirmed,
    'silence_expected_confirmed',
      p_assessment.silence_expected_confirmed,
    'note', p_assessment.note,
    'media_sha256', p_assessment.media_sha256_snapshot,
    'review_completion_hash', p_assessment.review_completion_hash,
    'assessment_hash', p_assessment.assessment_hash,
    'lineage', jsonb_build_object(
      'kind', p_assessment.lineage_kind,
      'depth', p_assessment.lineage_depth,
      'source_assessment_id', p_assessment.source_assessment_id
    ),
    'created_at', p_assessment.created_at
  );
end;
$$;

revoke all on function
  content_factory_private.content_review_sound_assessment_json(
    content_factory.content_review_sound_assessments
  )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.content_review_sound_assessment_history(
    p_organization_id uuid,
    p_review_id uuid
  )
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
declare
  current_assessment
    content_factory.content_review_sound_assessments%rowtype;
  result_value jsonb;
begin
  select assessment.* into current_assessment
  from content_factory.content_review_sound_assessments assessment
  where assessment.organization_id = p_organization_id
    and assessment.review_id = p_review_id;

  select coalesce(
           jsonb_agg(
             history.value order by history.created_at, history.id
           ),
           '[]'::jsonb
         )
    into result_value
  from (
    select assessment.created_at, assessment.id,
      content_factory_private.content_review_sound_assessment_json(
        assessment
      ) as value
    from content_factory.content_review_sound_assessments assessment
    where assessment.organization_id = p_organization_id
      and (
        assessment.review_id = p_review_id
        or assessment.source_assessment_id = current_assessment.id
        or assessment.id = current_assessment.source_assessment_id
      )
    order by assessment.created_at, assessment.id
    limit 20
  ) history;
  return result_value;
end;
$$;

revoke all on function
  content_factory_private.content_review_sound_assessment_history(
    uuid, uuid
  )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.record_content_review_sound_assessment(
    p_organization_id uuid,
    p_review_id uuid,
    p_decision_id uuid,
    p_assessed_by uuid,
    p_assessment jsonb,
    p_lineage_kind text,
    p_source_assessment_id uuid
  )
returns content_factory.content_review_sound_assessments
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  generation_job_row content_factory.generation_jobs%rowtype;
  decision_row content_factory.content_review_decisions%rowtype;
  source_assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  source_review_row content_factory.content_review_runs%rowtype;
  existing_row content_factory.content_review_sound_assessments%rowtype;
  inserted_row content_factory.content_review_sound_assessments%rowtype;
  expected_decision_value text := 'approved';
  normalized_value jsonb;
  source_payload_value jsonb;
  assessment_hash_value text;
  lineage_depth_value smallint := 0;
  server_audio_value boolean;
  expected_spoken_script_value text;
begin
  perform pg_advisory_xact_lock(
    hashtext(p_organization_id::text),
    hashtext('content_review_sound:' || p_review_id::text)
  );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = p_organization_id
    and review.id = p_review_id
  for share;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.id = review_row.media_object_id
  for share;

  if review_row.id is null
     or review_row.status <> 'completed'
     or review_row.completion_hash is null
     or media_row.id is null
     or media_row.metadata ->> 'kind' <> 'generated_video'
     or media_row.mime_type <> 'video/mp4'
     or media_row.sha256 is distinct from
          review_row.media_sha256_snapshot then
    raise exception using
      errcode = '55000',
      message = 'content_review_sound_source_invalid';
  end if;

  if coalesce(media_row.metadata ->> 'generation_job_id', '') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     or jsonb_typeof(media_row.metadata -> 'audio') <> 'boolean' then
    raise exception using
      errcode = '55000',
      message = 'content_review_sound_provenance_invalid';
  end if;
  select generation.* into generation_job_row
  from content_factory.generation_jobs generation
  where generation.organization_id = p_organization_id
    and generation.id =
      (media_row.metadata ->> 'generation_job_id')::uuid
  for share;
  server_audio_value := case generation_job_row.input ->> 'model'
    when 'seedance2_fast' then true
    when 'gen4_turbo' then false
    else null
  end;
  if generation_job_row.id is null
     or generation_job_row.mode <> 'real'
     or generation_job_row.provider <> 'runway'
     or generation_job_row.status <> 'succeeded'
     or generation_job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or generation_job_row.id::text
          is distinct from review_row.input ->> 'generation_job_id'
     or generation_job_row.id::text
          is distinct from media_row.metadata ->> 'generation_job_id'
     or generation_job_row.input ->> 'model'
          is distinct from media_row.metadata ->> 'model'
     or jsonb_typeof(generation_job_row.input -> 'audio') <> 'boolean'
     or server_audio_value is null
     or (generation_job_row.input ->> 'audio')::boolean
          is distinct from server_audio_value
     or (media_row.metadata ->> 'audio')::boolean
          is distinct from server_audio_value then
    raise exception using
      errcode = '55000',
      message = 'content_review_sound_provenance_invalid';
  end if;

  if server_audio_value then
    expected_spoken_script_value :=
      content_factory_private.generated_video_spoken_script(
        generation_job_row.input ->> 'prompt_text'
      );
    if expected_spoken_script_value is null
       or length(expected_spoken_script_value) not between 3 and 6000
       or media_row.metadata ->> 'spoken_script_source'
            is distinct from 'generation_job_prompt_v1'
       or media_row.metadata ->> 'spoken_script'
            is distinct from expected_spoken_script_value
       or review_row.input ->> 'script_text'
            is distinct from expected_spoken_script_value then
      raise exception using
        errcode = '55000',
        message =
          'content_review_sound_spoken_script_provenance_invalid';
    end if;
  end if;

  if p_decision_id is not null then
    select decision.* into decision_row
    from content_factory.content_review_decisions decision
    where decision.organization_id = p_organization_id
      and decision.review_id = p_review_id
      and decision.id = p_decision_id;
    if decision_row.id is null
       or decision_row.decided_by is distinct from p_assessed_by then
      raise exception using
        errcode = '55000',
        message = 'content_review_sound_decision_invalid';
    end if;
    expected_decision_value := decision_row.decision;
  end if;

  if p_assessment ->> 'version'
       is distinct from 'generated-video-sound-v1' then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_version_invalid';
  end if;
  normalized_value :=
    content_factory_private.normalize_content_review_sound_assessment(
      p_assessment - 'version',
      expected_decision_value
    );
  if normalized_value is distinct from p_assessment then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_not_normalized';
  end if;
  if (normalized_value ->> 'audio')::boolean
       is distinct from server_audio_value then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_audio_mismatch';
  end if;

  if p_lineage_kind = 'direct_decision' then
    if p_decision_id is null or p_source_assessment_id is not null then
      raise exception using
        errcode = '22023',
        message = 'content_review_sound_lineage_invalid';
    end if;
  elsif p_lineage_kind = 'context_source' then
    if p_decision_id is not null or p_source_assessment_id is not null then
      raise exception using
        errcode = '22023',
        message = 'content_review_sound_lineage_invalid';
    end if;
  elsif p_lineage_kind = 'context_copy' then
    if p_decision_id is null or p_source_assessment_id is null then
      raise exception using
        errcode = '22023',
        message = 'content_review_sound_lineage_invalid';
    end if;
    select assessment.* into source_assessment_row
    from content_factory.content_review_sound_assessments assessment
    where assessment.organization_id = p_organization_id
      and assessment.id = p_source_assessment_id
    for share;
    select source_review.* into source_review_row
    from content_factory.content_review_runs source_review
    where source_review.organization_id = p_organization_id
      and source_review.id = source_assessment_row.review_id
    for share;

    source_payload_value := jsonb_build_object(
      'version', source_assessment_row.assessment_version,
      'audio', source_assessment_row.audio,
      'status', source_assessment_row.status,
      'issue_codes', source_assessment_row.issue_codes,
      'spoken_script_heard_exactly_confirmed',
        source_assessment_row.spoken_script_heard_exactly_confirmed,
      'diction_clear_confirmed',
        source_assessment_row.diction_clear_confirmed,
      'voice_style_confirmed',
        source_assessment_row.voice_style_confirmed,
      'audio_sync_confirmed',
        source_assessment_row.audio_sync_confirmed,
      'silence_expected_confirmed',
        source_assessment_row.silence_expected_confirmed,
      'note', source_assessment_row.note
    );
    if source_assessment_row.id is null
       or source_assessment_row.lineage_kind <> 'context_source'
       or source_assessment_row.lineage_depth <> 0
       or source_review_row.id is null
       or review_row.parent_review_id
            is distinct from source_review_row.id
       or review_row.media_object_id
            is distinct from source_review_row.media_object_id
       or review_row.media_sha256_snapshot
            is distinct from source_review_row.media_sha256_snapshot
       or review_row.input #>> '{context_amendment,version}'
            is distinct from 'generated-video-context-v1'
       or review_row.input #>> '{context_amendment,source_review_id}'
            is distinct from source_review_row.id::text
       or review_row.input
            #>> '{context_amendment,source_completion_hash}'
            is distinct from source_review_row.completion_hash
       or p_assessment is distinct from source_payload_value then
      raise exception using
        errcode = '55000',
        message = 'content_review_sound_context_lineage_invalid';
    end if;
    lineage_depth_value := 1;
  else
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_lineage_invalid';
  end if;

  assessment_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'generated-video-sound-v1',
      'organization_id', p_organization_id,
      'review_id', review_row.id,
      'media_id', media_row.id,
      'decision_id', p_decision_id,
      'assessed_by', p_assessed_by,
      'assessment', normalized_value,
      'media_sha256', review_row.media_sha256_snapshot,
      'review_completion_hash', review_row.completion_hash,
      'spoken_script_hash', case
        when expected_spoken_script_value is null then null
        else content_factory_private.json_hash(
          to_jsonb(expected_spoken_script_value)
        )
      end,
      'lineage_kind', p_lineage_kind,
      'source_assessment_id', p_source_assessment_id,
      'lineage_depth', lineage_depth_value
    )
  );

  select assessment.* into existing_row
  from content_factory.content_review_sound_assessments assessment
  where assessment.organization_id = p_organization_id
    and assessment.review_id = p_review_id
  for share;
  if existing_row.id is not null then
    if existing_row.assessment_hash is distinct from
         assessment_hash_value then
      raise exception using
        errcode = '23505',
        message = 'content_review_sound_assessment_conflict';
    end if;
    return existing_row;
  end if;

  insert into content_factory.content_review_sound_assessments (
    organization_id, review_id, media_object_id, decision_id,
    assessed_by, assessment_version, audio, status, issue_codes,
    spoken_script_heard_exactly_confirmed,
    diction_clear_confirmed, voice_style_confirmed,
    audio_sync_confirmed, silence_expected_confirmed, note,
    media_sha256_snapshot, review_completion_hash,
    assessment_hash, lineage_kind, source_assessment_id,
    lineage_depth
  ) values (
    p_organization_id, review_row.id, media_row.id, p_decision_id,
    p_assessed_by, 'generated-video-sound-v1',
    (normalized_value ->> 'audio')::boolean,
    normalized_value ->> 'status',
    normalized_value -> 'issue_codes',
    (normalized_value
      ->> 'spoken_script_heard_exactly_confirmed')::boolean,
    (normalized_value ->> 'diction_clear_confirmed')::boolean,
    (normalized_value ->> 'voice_style_confirmed')::boolean,
    (normalized_value ->> 'audio_sync_confirmed')::boolean,
    (normalized_value ->> 'silence_expected_confirmed')::boolean,
    normalized_value ->> 'note',
    review_row.media_sha256_snapshot, review_row.completion_hash,
    assessment_hash_value, p_lineage_kind, p_source_assessment_id,
    lineage_depth_value
  )
  returning * into inserted_row;
  return inserted_row;
end;
$$;

revoke all on function
  content_factory_private.record_content_review_sound_assessment(
    uuid, uuid, uuid, uuid, jsonb, text, uuid
  )
  from public, anon, authenticated, service_role;

-- Preserve the mature decision implementation (including independent-review,
-- placement, payout and command-ledger behavior) and add only the sound gate.
alter function public.creator_decide_content_review(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_decide_content_review(jsonb)
  rename to creator_decide_content_review_without_sound_release_gate;
revoke all on function
  content_factory_private
    .creator_decide_content_review_without_sound_release_gate(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_decide_content_review(
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
  review_id_value uuid;
  decision_value text;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  source_assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  assessment_value jsonb;
  result_value jsonb;
  decision_id_value uuid;
  lineage_kind_value text := 'direct_decision';
  source_assessment_id_value uuid;
  generated_video_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 65536 then
    raise exception using
      errcode = '22023',
      message = 'content_review_decision_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');
  decision_value := lower(content_factory_private.require_text(
    p_payload, 'decision', 3, 40
  ));

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value;
  if review_row.id is null then
    return content_factory_private
      .creator_decide_content_review_without_sound_release_gate(
        p_payload - 'sound_assessment'
      );
  end if;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = review_row.media_object_id;
  generated_video_value :=
    media_row.metadata ->> 'kind' = 'generated_video';

  if generated_video_value and p_payload ? 'sound_assessment' then
    assessment_value :=
      content_factory_private.normalize_content_review_sound_assessment(
        p_payload -> 'sound_assessment',
        decision_value
      );
  elsif generated_video_value then
    select assessment.* into source_assessment_row
    from content_factory.content_review_runs source_review
    join content_factory.content_review_sound_assessments assessment
      on assessment.organization_id = source_review.organization_id
     and assessment.review_id = source_review.id
    where source_review.organization_id = organization_id
      and source_review.id = review_row.parent_review_id
      and source_review.media_object_id = review_row.media_object_id
      and source_review.media_sha256_snapshot =
            review_row.media_sha256_snapshot
      and source_review.completion_hash =
            review_row.input
              #>> '{context_amendment,source_completion_hash}'
      and review_row.input #>> '{context_amendment,version}' =
            'generated-video-context-v1'
      and review_row.input #>> '{context_amendment,source_review_id}' =
            source_review.id::text
      and assessment.lineage_kind = 'context_source'
      and assessment.lineage_depth = 0;
    if source_assessment_row.id is null then
      raise exception using
        errcode = '22023',
        message = 'content_review_sound_assessment_required';
    end if;
    assessment_value := jsonb_build_object(
      'version', source_assessment_row.assessment_version,
      'audio', source_assessment_row.audio,
      'status', source_assessment_row.status,
      'issue_codes', source_assessment_row.issue_codes,
      'spoken_script_heard_exactly_confirmed',
        source_assessment_row.spoken_script_heard_exactly_confirmed,
      'diction_clear_confirmed',
        source_assessment_row.diction_clear_confirmed,
      'voice_style_confirmed',
        source_assessment_row.voice_style_confirmed,
      'audio_sync_confirmed',
        source_assessment_row.audio_sync_confirmed,
      'silence_expected_confirmed',
        source_assessment_row.silence_expected_confirmed,
      'note', source_assessment_row.note
    );
    assessment_value :=
      content_factory_private.normalize_content_review_sound_assessment(
        assessment_value - 'version',
        decision_value
      );
    lineage_kind_value := 'context_copy';
    source_assessment_id_value := source_assessment_row.id;
  elsif p_payload ? 'sound_assessment' then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_not_applicable';
  else
    return content_factory_private
      .creator_decide_content_review_without_sound_release_gate(p_payload);
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('content_review_sound:' || review_id_value::text)
  );
  result_value := content_factory_private
    .creator_decide_content_review_without_sound_release_gate(
      p_payload - 'sound_assessment'
    );
  decision_id_value :=
    content_factory_private.require_uuid(result_value, 'decision_id');
  assessment_row :=
    content_factory_private.record_content_review_sound_assessment(
      organization_id,
      review_id_value,
      decision_id_value,
      user_id,
      assessment_value,
      lineage_kind_value,
      source_assessment_id_value
    );
  return result_value || jsonb_build_object(
    'sound_assessment',
      content_factory_private.content_review_sound_assessment_json(
        assessment_row
      ),
    'sound_assessment_history',
      content_factory_private.content_review_sound_assessment_history(
        organization_id, review_id_value
      )
  );
end;
$$;

revoke all on function public.creator_decide_content_review(jsonb)
  from public, anon;
grant execute on function public.creator_decide_content_review(jsonb)
  to authenticated;

-- The context command records the human assessment against the source review.
-- Its existing inner decision calls the public wrapper above, which can copy
-- only that assessment to the exact media/context-amended child.
alter function
  public.creator_approve_generated_video_review_with_context(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private
    .creator_approve_generated_video_review_with_context(jsonb)
  rename to
    creator_approve_generated_video_review_pre_sound_gate_v1;
revoke all on function
  content_factory_private
    .creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  public.creator_approve_generated_video_review_with_context(
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
  source_review_id_value uuid;
  amended_review_id_value uuid;
  decision_id_value uuid;
  assessment_value jsonb;
  source_assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  amended_assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 65536
     or not (p_payload ? 'sound_assessment') then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_assessment_required';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  source_review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');
  assessment_value :=
    content_factory_private.normalize_content_review_sound_assessment(
      p_payload -> 'sound_assessment',
      'approved'
    );
  source_assessment_row :=
    content_factory_private.record_content_review_sound_assessment(
      organization_id,
      source_review_id_value,
      null,
      user_id,
      assessment_value,
      'context_source',
      null
    );

  result_value := content_factory_private
    .creator_approve_generated_video_review_pre_sound_gate_v1(
      p_payload - 'sound_assessment'
    );
  amended_review_id_value :=
    content_factory_private.require_uuid(result_value, 'review_id');
  decision_id_value :=
    content_factory_private.require_uuid(result_value, 'decision_id');
  amended_assessment_row :=
    content_factory_private.record_content_review_sound_assessment(
      organization_id,
      amended_review_id_value,
      decision_id_value,
      user_id,
      assessment_value,
      'context_copy',
      source_assessment_row.id
    );

  return result_value || jsonb_build_object(
    'sound_assessment',
      content_factory_private.content_review_sound_assessment_json(
        amended_assessment_row
      ),
    'source_sound_assessment',
      content_factory_private.content_review_sound_assessment_json(
        source_assessment_row
      ),
    'sound_assessment_history',
      content_factory_private.content_review_sound_assessment_history(
        organization_id, amended_review_id_value
      )
  );
end;
$$;

revoke all on function
  public.creator_approve_generated_video_review_with_context(jsonb)
  from public, anon;
grant execute on function
  public.creator_approve_generated_video_review_with_context(jsonb)
  to authenticated;

-- Enrich authorized status reads after the established queue/lease wrapper has
-- made its decision. No assessment table is exposed directly.
alter function public.creator_content_review_status(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_content_review_status(jsonb)
  rename to creator_content_review_status_without_sound_release_gate;
revoke all on function
  content_factory_private
    .creator_content_review_status_without_sound_release_gate(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_content_review_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result_value jsonb;
  organization_id uuid;
  review_id_value uuid;
  assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  assessment_value jsonb;
  history_value jsonb;
begin
  result_value := content_factory_private
    .creator_content_review_status_without_sound_release_gate(p_payload);
  review_id_value := (result_value #>> '{run,id}')::uuid;
  select review.organization_id into organization_id
  from content_factory.content_review_runs review
  where review.id = review_id_value;
  select assessment.* into assessment_row
  from content_factory.content_review_sound_assessments assessment
  where assessment.organization_id = organization_id
    and assessment.review_id = review_id_value;
  assessment_value :=
    content_factory_private.content_review_sound_assessment_json(
      assessment_row
    );
  history_value :=
    content_factory_private.content_review_sound_assessment_history(
      organization_id, review_id_value
    );
  result_value := jsonb_set(
    result_value,
    '{run}',
    (result_value -> 'run') || jsonb_build_object(
      'sound_assessment', assessment_value,
      'sound_assessment_history', history_value
    ),
    false
  );
  return result_value || jsonb_build_object(
    'sound_assessment', assessment_value,
    'sound_assessment_history', history_value
  );
end;
$$;

revoke all on function public.creator_content_review_status(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_status(jsonb)
  to authenticated;

-- Add the same bounded view to already-authorized catalog rows while retaining
-- the complete catalog wrapper chain (assignment, repair and media context).
alter function public.creator_content_review_catalog(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_content_review_catalog(jsonb)
  rename to creator_content_review_catalog_without_sound_release_gate;
revoke all on function
  content_factory_private
    .creator_content_review_catalog_without_sound_release_gate(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_content_review_catalog(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id uuid;
  catalog_value jsonb;
  reviews_value jsonb;
begin
  catalog_value := content_factory_private
    .creator_content_review_catalog_without_sound_release_gate(p_payload);
  organization_id :=
    content_factory_private.resolve_organization(p_payload);

  select coalesce(
           jsonb_agg(
             item.value || jsonb_build_object(
               'sound_assessment',
                 content_factory_private
                   .content_review_sound_assessment_json(
                     assessment
                   ),
               'sound_assessment_history',
                 content_factory_private
                   .content_review_sound_assessment_history(
                     organization_id,
                     (item.value ->> 'id')::uuid
                   )
             )
             order by item.ordinality
           ),
           '[]'::jsonb
         )
    into reviews_value
  from jsonb_array_elements(
    coalesce(catalog_value -> 'recent_reviews', '[]'::jsonb)
  ) with ordinality item(value, ordinality)
  left join content_factory.content_review_sound_assessments assessment
    on assessment.organization_id = organization_id
   and assessment.review_id = (item.value ->> 'id')::uuid;

  return jsonb_set(
    catalog_value,
    '{recent_reviews}',
    reviews_value,
    false
  );
end;
$$;

revoke all on function public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_catalog(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

begin;

-- A generated-video decision and its human sound assessment are one logical
-- record.  The assessment is inserted after the immutable decision by the
-- mature RPC, so enforce the invariant at transaction end.  This protects the
-- table even if a later public/project wrapper accidentally bypasses the sound
-- gate: the decision insert is rolled back instead of becoming a partial fact.
create or replace function
  content_factory_private.enforce_generated_video_decision_sound_atomic()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (
    select 1
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    where review.organization_id = new.organization_id
      and review.id = new.review_id
      and media.metadata ->> 'kind' = 'generated_video'
      and media.mime_type = 'video/mp4'
  ) and not exists (
    select 1
    from content_factory.content_review_sound_assessments assessment
    where assessment.organization_id = new.organization_id
      and assessment.review_id = new.review_id
      and assessment.decision_id = new.id
  ) then
    raise exception using
      errcode = '23514',
      message = 'content_review_sound_assessment_required';
  end if;
  return null;
end;
$$;

revoke all on function
  content_factory_private.enforce_generated_video_decision_sound_atomic()
  from public, anon, authenticated, service_role;

drop trigger if exists enforce_generated_video_decision_sound_atomic
  on content_factory.content_review_decisions;
create constraint trigger enforce_generated_video_decision_sound_atomic
after insert on content_factory.content_review_decisions
deferrable initially deferred
for each row execute function
  content_factory_private.enforce_generated_video_decision_sound_atomic();

-- Decisions are immutable.  A narrowly-scoped recovery command therefore
-- appends only the missing sound assessment.  The same employee must have made
-- the decision, must replay the exact protected MP4, and must submit an
-- assessment compatible with that immutable decision.  The existing recorder
-- re-validates generation provenance and remains append-only/idempotent.
create or replace function
  public.creator_recover_content_review_sound_assessment(
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
  user_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  decision_row content_factory.content_review_decisions%rowtype;
  assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  assessment_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 16384
     or p_payload - array[
       'organization_id', 'project_id', 'review_id',
       'media_watched_confirmed', 'sound_assessment', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_recovery_payload_invalid';
  end if;

  user_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value :=
    content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );
  review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');

  if jsonb_typeof(p_payload -> 'media_watched_confirmed') <> 'boolean'
     or (p_payload ->> 'media_watched_confirmed')::boolean is not true
     or not (p_payload ? 'sound_assessment') then
    raise exception using
      errcode = '22023',
      message = 'content_review_sound_recovery_confirmation_required';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('content_review_sound:' || review_id_value::text)
  );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id_value
    and review.id = review_id_value
    and review.project_id = project_id_value
  for share;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.project_id = project_id_value
    and media.id = review_row.media_object_id
  for share;
  select decision.* into decision_row
  from content_factory.content_review_decisions decision
  where decision.organization_id = organization_id_value
    and decision.review_id = review_id_value;

  if review_row.id is null
     or decision_row.id is null
     or decision_row.decided_by is distinct from user_id_value then
    raise exception using
      errcode = '42501',
      message = 'content_review_sound_recovery_not_allowed';
  end if;

  if media_row.id is null
     or media_row.status is distinct from 'ready'
     or media_row.sha256 is distinct from review_row.media_sha256_snapshot
     or media_row.metadata ->> 'kind' is distinct from 'generated_video'
     or media_row.mime_type is distinct from 'video/mp4' then
    raise exception using
      errcode = '55000',
      message = 'content_review_sound_recovery_media_not_ready';
  end if;

  assessment_value :=
    content_factory_private.normalize_content_review_sound_assessment(
      p_payload -> 'sound_assessment',
      decision_row.decision
    );
  assessment_row :=
    content_factory_private.record_content_review_sound_assessment(
      organization_id_value,
      review_id_value,
      decision_row.id,
      user_id_value,
      assessment_value,
      'direct_decision',
      null
    );

  return jsonb_build_object(
    'ok', true,
    'recovered', true,
    'project_id', project_id_value,
    'review_id', review_id_value,
    'decision_id', decision_row.id,
    'sound_assessment',
      content_factory_private.content_review_sound_assessment_json(
        assessment_row
      ),
    'sound_assessment_history',
      content_factory_private.content_review_sound_assessment_history(
        organization_id_value,
        review_id_value
      )
  );
end;
$$;

revoke all on function
  public.creator_recover_content_review_sound_assessment(jsonb)
  from public, anon;
grant execute on function
  public.creator_recover_content_review_sound_assessment(jsonb)
  to authenticated;

-- Re-enrich the latest project-scoped status directly from the append-only
-- table.  This makes the table authoritative even if an older preserved reader
-- in the wrapper topology predates the sound history.
do $preserve_status_before_sound_truth$
begin
  if to_regprocedure(
    'content_factory_private.creator_review_status_pre_sound_truth_v2(jsonb)'
  ) is null then
    alter function public.creator_content_review_status(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_content_review_status(jsonb)
      rename to creator_review_status_pre_sound_truth_v2;
  end if;
end;
$preserve_status_before_sound_truth$;

revoke all on function
  content_factory_private.creator_review_status_pre_sound_truth_v2(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_content_review_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  result_value jsonb;
  user_id_value uuid;
  organization_id_value uuid;
  review_id_value uuid;
  assessment_row
    content_factory.content_review_sound_assessments%rowtype;
  assessment_value jsonb;
  history_value jsonb;
  recovery_eligible_value boolean := false;
begin
  result_value := content_factory_private
    .creator_review_status_pre_sound_truth_v2(p_payload);
  user_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  review_id_value := (result_value #>> '{run,id}')::uuid;

  select assessment.* into assessment_row
  from content_factory.content_review_sound_assessments assessment
  where assessment.organization_id = organization_id_value
    and assessment.review_id = review_id_value;
  assessment_value :=
    content_factory_private.content_review_sound_assessment_json(
      assessment_row
    );
  history_value :=
    content_factory_private.content_review_sound_assessment_history(
      organization_id_value,
      review_id_value
    );
  select exists (
    select 1
    from content_factory.content_review_decisions decision
    join content_factory.content_review_runs review
      on review.organization_id = decision.organization_id
     and review.id = decision.review_id
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    where decision.organization_id = organization_id_value
      and decision.review_id = review_id_value
      and decision.decided_by = user_id_value
      and assessment_row.id is null
      and media.metadata ->> 'kind' = 'generated_video'
      and media.mime_type = 'video/mp4'
      and media.status = 'ready'
      and media.sha256 = review.media_sha256_snapshot
  ) into recovery_eligible_value;

  result_value := jsonb_set(
    result_value,
    '{run}',
    (result_value -> 'run') || jsonb_build_object(
      'sound_assessment', assessment_value,
      'sound_assessment_history', history_value,
      'sound_recovery_eligible', recovery_eligible_value
    ),
    false
  );
  return result_value || jsonb_build_object(
    'sound_assessment', assessment_value,
    'sound_assessment_history', history_value,
    'sound_recovery_eligible', recovery_eligible_value
  );
end;
$$;

revoke all on function public.creator_content_review_status(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_status(jsonb)
  to authenticated;

-- The catalog may satisfy an exact deep link without calling the status RPC,
-- so apply the same authoritative enrichment to every authorized catalog row.
do $preserve_catalog_before_sound_truth$
begin
  if to_regprocedure(
    'content_factory_private.creator_review_catalog_pre_sound_truth_v2(jsonb)'
  ) is null then
    alter function public.creator_content_review_catalog(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_content_review_catalog(jsonb)
      rename to creator_review_catalog_pre_sound_truth_v2;
  end if;
end;
$preserve_catalog_before_sound_truth$;

revoke all on function
  content_factory_private.creator_review_catalog_pre_sound_truth_v2(jsonb)
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
  result_value jsonb;
  user_id_value uuid;
  organization_id_value uuid;
  reviews_value jsonb;
begin
  result_value := content_factory_private
    .creator_review_catalog_pre_sound_truth_v2(p_payload);
  user_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);

  select coalesce(
    jsonb_agg(
      item.value || jsonb_build_object(
        'sound_assessment',
          content_factory_private.content_review_sound_assessment_json(
            assessment
          ),
        'sound_assessment_history',
          content_factory_private.content_review_sound_assessment_history(
            organization_id_value,
            (item.value ->> 'id')::uuid
          ),
        'sound_recovery_eligible', exists (
          select 1
          from content_factory.content_review_decisions decision
          join content_factory.content_review_runs review
            on review.organization_id = decision.organization_id
           and review.id = decision.review_id
          join content_factory.media_objects media
            on media.organization_id = review.organization_id
           and media.id = review.media_object_id
          where decision.organization_id = organization_id_value
            and decision.review_id = (item.value ->> 'id')::uuid
            and decision.decided_by = user_id_value
            and assessment.id is null
            and media.metadata ->> 'kind' = 'generated_video'
            and media.mime_type = 'video/mp4'
            and media.status = 'ready'
            and media.sha256 = review.media_sha256_snapshot
          )
      ) order by item.ordinality
    ),
    '[]'::jsonb
  ) into reviews_value
  from jsonb_array_elements(
    coalesce(result_value -> 'recent_reviews', '[]'::jsonb)
  ) with ordinality item(value, ordinality)
  left join content_factory.content_review_sound_assessments assessment
    on assessment.organization_id = organization_id_value
   and assessment.review_id = (item.value ->> 'id')::uuid;

  return jsonb_set(
    result_value,
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

comment on function
  public.creator_recover_content_review_sound_assessment(jsonb) is
  'Append-only employee recovery for a missing sound assessment on the same employee immutable content-review decision.';

notify pgrst, 'reload schema';

commit;

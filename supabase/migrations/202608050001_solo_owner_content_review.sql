begin;

-- A one-person workspace must not deadlock after paid generation. Keep the
-- normal independent-review route whenever another eligible reviewer exists;
-- only the active owner who created/owns the exact result may self-review when
-- no independent candidate can be assigned. Media watch, risk, sound and
-- compliance gates remain enforced by the mature decision pipeline.
create or replace function
  content_factory_private.solo_owner_content_review_allowed(
    p_organization_id uuid,
    p_review_id uuid,
    p_profile_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from content_factory.memberships actor
    join content_factory.content_review_runs review
      on review.organization_id = actor.organization_id
     and review.id = p_review_id
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    left join content_factory.creator_tasks task
      on task.organization_id = media.organization_id
     and task.id = media.task_id
    left join content_factory.generation_jobs job
      on job.organization_id = review.organization_id
     and job.id::text = review.input ->> 'generation_job_id'
    where actor.organization_id = p_organization_id
      and actor.profile_id = p_profile_id
      and actor.status = 'active'
      and actor.role = 'owner'
      and content_factory_private.generated_media_reviewer_access_allowed(
        actor.organization_id,
        actor.profile_id
      )
      and (
        review.requested_by = p_profile_id
        or media.owner_id = p_profile_id
        or task.assignee_id = p_profile_id
        or job.requested_by = p_profile_id
        or job.assigned_to = p_profile_id
      )
      and not exists (
        select 1
        from content_factory.memberships candidate
        where candidate.organization_id = p_organization_id
          and candidate.status = 'active'
          and candidate.role in (
            'owner', 'admin', 'producer', 'reviewer'
          )
          and candidate.profile_id is distinct from p_profile_id
          and candidate.profile_id is distinct from review.requested_by
          and candidate.profile_id is distinct from media.owner_id
          and candidate.profile_id is distinct from task.assignee_id
          and candidate.profile_id is distinct from job.requested_by
          and candidate.profile_id is distinct from job.assigned_to
          and content_factory_private.generated_media_reviewer_access_allowed(
            candidate.organization_id,
            candidate.profile_id
          )
      )
  )
$$;

revoke all on function
  content_factory_private.solo_owner_content_review_allowed(uuid, uuid, uuid)
  from public, anon, authenticated, service_role;

-- Extend the existing assignment function in place so trigger OIDs and every
-- wrapper keep pointing at the same mature implementation.
do $patch_assignment$
declare
  function_name constant regprocedure :=
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure;
  source_text text := pg_get_functiondef(function_name);
  old_text constant text := $old$
  if assignee_id_value is null then
    return null;
  end if;

  insert into content_factory.content_review_assignments ($old$;
  new_text constant text := $new$
  if assignee_id_value is null then
    select membership.profile_id
    into assignee_id_value
    from content_factory.memberships membership
    where membership.organization_id = p_organization_id
      and membership.status = 'active'
      and membership.role = 'owner'
      and content_factory_private.solo_owner_content_review_allowed(
        p_organization_id,
        p_review_id,
        membership.profile_id
      )
    order by membership.created_at, membership.profile_id
    limit 1;
  end if;
  if assignee_id_value is null then
    return null;
  end if;

  insert into content_factory.content_review_assignments ($new$;
begin
  if strpos(source_text, old_text) = 0 then
    raise exception using
      errcode = '55000',
      message = 'solo_owner_assignment_patch_target_missing';
  end if;
  execute replace(source_text, old_text, new_text);
end;
$patch_assignment$;

-- The mature decision function still rejects the creator before the assignment
-- trigger runs. Preserve that rule except for the exact solo-owner predicate.
do $patch_decision$
declare
  function_name constant regprocedure :=
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'::regprocedure;
  source_text text := pg_get_functiondef(function_name);
  old_text constant text := $old$
  ) and (
    review_row.requested_by = user_id
    or media_row.owner_id = user_id
    or review_task_row.assignee_id = user_id
    or generation_job_row.requested_by = user_id
    or generation_job_row.assigned_to = user_id
  ) then$old$;
  new_text constant text := $new$
  ) and (
    review_row.requested_by = user_id
    or media_row.owner_id = user_id
    or review_task_row.assignee_id = user_id
    or generation_job_row.requested_by = user_id
    or generation_job_row.assigned_to = user_id
  ) and not content_factory_private.solo_owner_content_review_allowed(
    organization_id,
    review_id_value,
    user_id
  ) then$new$;
begin
  if strpos(source_text, old_text) = 0 then
    raise exception using
      errcode = '55000',
      message = 'solo_owner_decision_patch_target_missing';
  end if;
  execute replace(source_text, old_text, new_text);
end;
$patch_decision$;

-- Make the existing catalog expose the same exact permission so the owner sees
-- the review action instead of an impossible invitation to another teammate.
do $patch_catalog$
declare
  function_name constant regprocedure :=
    'content_factory_private.creator_content_review_catalog_without_repair_actions(jsonb)'::regprocedure;
  source_text text := pg_get_functiondef(function_name);
  old_text constant text := $old$
            'decision_eligible',
              actor_role in (
                'owner', 'admin', 'producer', 'reviewer'
              )
              and user_id is distinct from review.requested_by
              and user_id is distinct from media.owner_id
              and user_id is distinct from task.assignee_id
              and user_id is distinct from job.requested_by
              and user_id is distinct from job.assigned_to,$old$;
  new_text constant text := $new$
            'decision_eligible',
              (
                actor_role in (
                  'owner', 'admin', 'producer', 'reviewer'
                )
                and user_id is distinct from review.requested_by
                and user_id is distinct from media.owner_id
                and user_id is distinct from task.assignee_id
                and user_id is distinct from job.requested_by
                and user_id is distinct from job.assigned_to
              )
              or content_factory_private.solo_owner_content_review_allowed(
                organization_id,
                review.id,
                user_id
              ),$new$;
begin
  if strpos(source_text, old_text) = 0 then
    raise exception using
      errcode = '55000',
      message = 'solo_owner_catalog_patch_target_missing';
  end if;
  execute replace(source_text, old_text, new_text);
end;
$patch_catalog$;

-- Existing completed reviews were left unassigned. The next ordinary catalog
-- read also retries assignment, but this bounded backfill removes the dead end
-- immediately after the migration is applied.
do $backfill_solo_owner_reviews$
declare
  review_row record;
begin
  for review_row in
    select review.organization_id, review.id
    from content_factory.content_review_runs review
    where review.status = 'completed'
      and not exists (
        select 1
        from content_factory.content_review_decisions decision
        where decision.organization_id = review.organization_id
          and decision.review_id = review.id
      )
  loop
    perform content_factory_private.assign_generated_media_review(
      review_row.organization_id,
      review_row.id
    );
  end loop;
end;
$backfill_solo_owner_reviews$;

notify pgrst, 'reload schema';

commit;

begin;

-- Generated-media QA already requires an independent human decision, but a
-- completed review previously remained in a shared manager queue. Persist one
-- deterministic reviewer assignment so the portal can show the exact next
-- action without allowing the requester, generator, or media owner to review
-- their own output.
create table if not exists content_factory.content_review_assignments (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  review_id uuid not null,
  assignee_id uuid not null,
  status text not null default 'assigned'
    check (status in ('assigned', 'completed', 'cancelled')),
  assigned_at timestamptz not null default now(),
  completed_at timestamptz,
  cancelled_at timestamptz,
  foreign key (organization_id, review_id)
    references content_factory.content_review_runs(organization_id, id),
  foreign key (organization_id, assignee_id)
    references content_factory.memberships(organization_id, profile_id),
  unique (organization_id, review_id),
  unique (organization_id, id),
  check (
    (
      status = 'assigned'
      and completed_at is null
      and cancelled_at is null
    )
    or (
      status = 'completed'
      and completed_at is not null
      and cancelled_at is null
    )
    or (
      status = 'cancelled'
      and completed_at is null
      and cancelled_at is not null
    )
  )
);

create index if not exists content_review_assignments_inbox_idx
  on content_factory.content_review_assignments
  (organization_id, assignee_id, status, assigned_at, id)
  where status = 'assigned';

alter table content_factory.content_review_assignments
  enable row level security;

revoke all on table content_factory.content_review_assignments
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.guard_content_review_assignment()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '42501',
      message = 'content_review_assignment_immutable';
  end if;
  if tg_op = 'UPDATE' then
    if new.id is distinct from old.id
       or new.organization_id is distinct from old.organization_id
       or new.review_id is distinct from old.review_id
       or new.assignee_id is distinct from old.assignee_id
       or new.assigned_at is distinct from old.assigned_at
       or old.status <> 'assigned'
       or new.status not in ('completed', 'cancelled') then
      raise exception using
        errcode = '42501',
        message = 'content_review_assignment_immutable';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists content_review_assignment_immutable_guard
  on content_factory.content_review_assignments;
create trigger content_review_assignment_immutable_guard
before update or delete on content_factory.content_review_assignments
for each row execute function
  content_factory_private.guard_content_review_assignment();

revoke all on function
  content_factory_private.guard_content_review_assignment()
  from public, anon, authenticated, service_role;

-- Evaluate the same current workspace boundary that creator decision RPCs use,
-- but for an arbitrary candidate instead of auth.uid(). This keeps automatic
-- routing away from members whose final exam, refreshed course checks, or
-- practical approval are missing or expired.
create or replace function
  content_factory_private.generated_media_reviewer_access_allowed(
    p_organization_id uuid,
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
    from content_factory.memberships membership
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = p_organization_id
      and membership.profile_id = p_profile_id
      and membership.status = 'active'
      and membership.role in (
        'owner', 'admin', 'producer', 'reviewer'
      )
      and (
        content_factory_private.training_access_waiver_active(
          membership.organization_id,
          membership.profile_id
        )
        or (
          exists (
            select 1
            from content_factory.training_certifications final_certification
            where final_certification.organization_id =
                    membership.organization_id
              and final_certification.profile_id = membership.profile_id
              and final_certification.module_code = 'operator_final_exam'
              and final_certification.status = 'passed'
              and (
                final_certification.expires_at is null
                or final_certification.expires_at > now()
              )
          )
          and not exists (
            select 1
            from content_factory.training_modules module
            where module.module_type = 'course'
              and module.is_active
              and not exists (
                select 1
                from content_factory.training_certifications certification
                join content_factory.training_attempts attempt
                  on attempt.id = certification.attempt_id
                 and attempt.organization_id =
                       certification.organization_id
                 and attempt.profile_id = certification.profile_id
                 and attempt.module_code = certification.module_code
                where certification.organization_id =
                        membership.organization_id
                  and certification.profile_id = membership.profile_id
                  and certification.module_code = module.code
                  and certification.status = 'passed'
                  and (
                    certification.expires_at is null
                    or certification.expires_at > now()
                  )
                  and attempt.status = 'completed'
                  and attempt.passed
                  and attempt.idempotency_key like 'course-check:%'
                  and attempt.question_count = jsonb_array_length(
                    module.content #> '{knowledge_check,questions}'
                  )
                  and attempt.answered_count = attempt.question_count
                  and attempt.correct_count >= (
                    module.content #>> '{knowledge_check,pass_score}'
                  )::integer
              )
          )
          and content_factory_private.training_practical_gate_satisfied(
            membership.organization_id,
            membership.profile_id
          )
        )
      )
  )
$$;

revoke all on function
  content_factory_private.generated_media_reviewer_access_allowed(uuid, uuid)
  from public, anon, authenticated, service_role;

-- Keep the evidence-chain predicate reusable by assignment and by the
-- fail-closed decision trigger. A paid generated result cannot fall back to an
-- unassigned shared queue if no eligible reviewer is currently available.
create or replace function
  content_factory_private.generated_media_review_assignment_required(
    p_organization_id uuid,
    p_review_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
     and media.status = 'ready'
     and media.sha256 = review.media_sha256_snapshot
     and media.metadata ->> 'kind' in (
       'generated_image', 'generated_video'
     )
     and media.metadata ->> 'provider' = 'runway'
    join content_factory.generation_jobs job
      on job.organization_id = review.organization_id
     and job.id::text = review.input ->> 'generation_job_id'
     and job.id::text = media.metadata ->> 'generation_job_id'
     and job.mode = 'real'
     and job.provider = 'runway'
     and job.allow_real_spend
     and job.status = 'succeeded'
     and job.actual_cost_minor > 0
     and job.output ->> 'output_media_id' = media.id::text
     and job.output ->> 'sha256' = media.sha256
     and job.input ->> 'model' = media.metadata ->> 'model'
    where review.organization_id = p_organization_id
      and review.id = p_review_id
      and review.status = 'completed'
      and review.input -> 'ai_generated' = 'true'::jsonb
      and review.input -> 'external_ai_processing_confirmed' =
            'true'::jsonb
      and not (review.input ? 'context_amendment')
      and not exists (
        select 1
        from content_factory.content_review_decisions decision
        where decision.organization_id = review.organization_id
          and decision.review_id = review.id
      )
  )
$$;

revoke all on function
  content_factory_private.generated_media_review_assignment_required(
    uuid, uuid
  )
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.assign_generated_media_review(
    p_organization_id uuid,
    p_review_id uuid
  )
returns uuid
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  existing_assignment_row
    content_factory.content_review_assignments%rowtype;
  assignee_id_value uuid;
begin
  if p_organization_id is null or p_review_id is null then
    return null;
  end if;

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = p_organization_id
    and review.id = p_review_id
  for share;

  if review_row.id is null
     or review_row.status <> 'completed'
     or review_row.input -> 'ai_generated'
          is distinct from 'true'::jsonb
     or review_row.input -> 'external_ai_processing_confirmed'
          is distinct from 'true'::jsonb
     or review_row.input ? 'context_amendment'
     or exists (
       select 1
       from content_factory.content_review_decisions decision
       where decision.organization_id = p_organization_id
         and decision.review_id = p_review_id
     ) then
    return null;
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.id = review_row.media_object_id
  for share;

  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.sha256 <> review_row.media_sha256_snapshot
     or coalesce(media_row.metadata ->> 'kind', '') not in (
       'generated_image', 'generated_video'
     )
     or media_row.metadata ->> 'provider' is distinct from 'runway' then
    return null;
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = p_organization_id
    and job.id::text = review_row.input ->> 'generation_job_id'
    and job.id::text = media_row.metadata ->> 'generation_job_id'
  for share;

  if job_row.id is null
     or job_row.mode is distinct from 'real'
     or job_row.provider is distinct from 'runway'
     or job_row.allow_real_spend is distinct from true
     or job_row.status is distinct from 'succeeded'
     or coalesce(job_row.actual_cost_minor, 0) <= 0
     or job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or job_row.output ->> 'sha256'
          is distinct from media_row.sha256
     or job_row.input ->> 'model'
          is distinct from media_row.metadata ->> 'model' then
    return null;
  end if;

  -- Serialize load-based selection within an organization. Re-check the
  -- idempotent row only after the lock so concurrent completions cannot both
  -- choose from the same stale workload snapshot.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtext(p_organization_id::text),
    pg_catalog.hashtext('generated_media_review_assignment')
  );

  select assignment.* into existing_assignment_row
  from content_factory.content_review_assignments assignment
  where assignment.organization_id = p_organization_id
    and assignment.review_id = p_review_id;
  if existing_assignment_row.id is not null then
    if existing_assignment_row.status = 'assigned' then
      return existing_assignment_row.assignee_id;
    end if;
    return null;
  end if;

  select candidate.profile_id
  into assignee_id_value
  from content_factory.memberships candidate
  left join lateral (
    select
      count(*) filter (
        where assignment.status = 'assigned'
      )::integer as open_count,
      max(assignment.assigned_at) as last_assigned_at
    from content_factory.content_review_assignments assignment
    where assignment.organization_id = p_organization_id
      and assignment.assignee_id = candidate.profile_id
  ) load on true
  where candidate.organization_id = p_organization_id
    and candidate.status = 'active'
    and candidate.role in (
      'owner', 'admin', 'producer', 'reviewer'
    )
    and content_factory_private.generated_media_reviewer_access_allowed(
      candidate.organization_id,
      candidate.profile_id
    )
    and candidate.profile_id is distinct from review_row.requested_by
    and candidate.profile_id is distinct from media_row.owner_id
    and candidate.profile_id is distinct from job_row.requested_by
    and candidate.profile_id is distinct from job_row.assigned_to
  order by
    coalesce(load.open_count, 0),
    case candidate.role
      when 'reviewer' then 1
      when 'producer' then 2
      when 'admin' then 3
      else 4
    end,
    load.last_assigned_at nulls first,
    candidate.created_at,
    candidate.profile_id
  limit 1;

  if assignee_id_value is null then
    return null;
  end if;

  insert into content_factory.content_review_assignments (
    organization_id,
    review_id,
    assignee_id,
    status
  ) values (
    p_organization_id,
    p_review_id,
    assignee_id_value,
    'assigned'
  )
  on conflict (organization_id, review_id) do nothing
  returning assignee_id into assignee_id_value;

  if assignee_id_value is null then
    select assignment.assignee_id into assignee_id_value
    from content_factory.content_review_assignments assignment
    where assignment.organization_id = p_organization_id
      and assignment.review_id = p_review_id;
  end if;
  return assignee_id_value;
end;
$$;

revoke all on function
  content_factory_private.assign_generated_media_review(uuid, uuid)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.guard_generated_media_review_assignment_decision()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  assignee_id_value uuid;
  routed_review_id_value uuid := new.review_id;
begin
  -- Context-approval RPCs create an immutable amended review and decide that
  -- row. Bind the decision back to the independently assigned source review.
  select amendment.source_review_id
  into routed_review_id_value
  from content_factory.content_review_context_amendments amendment
  where amendment.organization_id = new.organization_id
    and amendment.amended_review_id = new.review_id;
  routed_review_id_value := coalesce(
    routed_review_id_value,
    new.review_id
  );

  if not
    content_factory_private.generated_media_review_assignment_required(
      new.organization_id,
      routed_review_id_value
    ) then
    return new;
  end if;

  assignee_id_value :=
    content_factory_private.assign_generated_media_review(
      new.organization_id,
      routed_review_id_value
    );
  if assignee_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'independent_reviewer_assignment_required';
  end if;
  if new.decided_by is distinct from assignee_id_value then
    raise exception using
      errcode = '42501',
      message = 'content_review_assigned_to_another_reviewer';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_generated_media_review_assignment_decision
  on content_factory.content_review_decisions;
create trigger guard_generated_media_review_assignment_decision
before insert on content_factory.content_review_decisions
for each row execute function
  content_factory_private.guard_generated_media_review_assignment_decision();

revoke all on function
  content_factory_private.guard_generated_media_review_assignment_decision()
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.route_completed_generated_media_review()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.status = 'completed'
     and old.status is distinct from new.status then
    perform content_factory_private.assign_generated_media_review(
      new.organization_id,
      new.id
    );
  elsif new.status in ('failed', 'cancelled')
        and old.status is distinct from new.status then
    update content_factory.content_review_assignments assignment
    set status = 'cancelled',
        cancelled_at = now()
    where assignment.organization_id = new.organization_id
      and assignment.review_id = new.id
      and assignment.status = 'assigned';
  end if;
  return new;
end;
$$;

drop trigger if exists route_completed_generated_media_review
  on content_factory.content_review_runs;
create trigger route_completed_generated_media_review
after update of status on content_factory.content_review_runs
for each row execute function
  content_factory_private.route_completed_generated_media_review();

revoke all on function
  content_factory_private.route_completed_generated_media_review()
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.complete_content_review_assignment()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update content_factory.content_review_assignments assignment
  set status = 'completed',
      completed_at = new.created_at
  where assignment.organization_id = new.organization_id
    and assignment.review_id = new.review_id
    and assignment.status = 'assigned';

  update content_factory.content_review_assignments assignment
  set status = 'completed',
      completed_at = new.created_at
  from content_factory.content_review_context_amendments amendment
  where amendment.organization_id = new.organization_id
    and amendment.amended_review_id = new.review_id
    and assignment.organization_id = amendment.organization_id
    and assignment.review_id = amendment.source_review_id
    and assignment.status = 'assigned';
  return new;
end;
$$;

drop trigger if exists complete_content_review_assignment
  on content_factory.content_review_decisions;
create trigger complete_content_review_assignment
after insert on content_factory.content_review_decisions
for each row execute function
  content_factory_private.complete_content_review_assignment();

revoke all on function
  content_factory_private.complete_content_review_assignment()
  from public, anon, authenticated, service_role;

-- Route any already-completed generated review that has not received a human
-- decision yet. This is idempotent and does not touch paid generation state.
do $$
declare
  review_row record;
begin
  for review_row in
    select review.organization_id, review.id
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    where review.status = 'completed'
      and review.input -> 'ai_generated' = 'true'::jsonb
      and not (review.input ? 'context_amendment')
      and media.metadata ->> 'kind' in (
        'generated_image', 'generated_video'
      )
      and not exists (
        select 1
        from content_factory.content_review_decisions decision
        where decision.organization_id = review.organization_id
          and decision.review_id = review.id
      )
    order by review.created_at, review.id
  loop
    perform content_factory_private.assign_generated_media_review(
      review_row.organization_id,
      review_row.id
    );
  end loop;
end;
$$;

-- Preserve the established catalog implementation and enrich only each review
-- with privacy-minimized routing state. Raw assignee identities never enter the
-- browser response.
alter function public.creator_content_review_catalog(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_content_review_catalog(jsonb)
  rename to creator_content_review_catalog_without_assignments;

revoke all on function
  content_factory_private
    .creator_content_review_catalog_without_assignments(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_content_review_catalog(
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
  catalog_value jsonb;
  runs_value jsonb;
begin
  catalog_value :=
    content_factory_private
      .creator_content_review_catalog_without_assignments(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := catalog_value ->> 'role';

  -- Retry reviews that could not be routed at completion time. This makes a
  -- newly qualified teammate visible as the exact next reviewer on the first
  -- ordinary catalog refresh, without a manager assigning work manually.
  perform content_factory_private.assign_generated_media_review(
    review.organization_id,
    review.id
  )
  from jsonb_array_elements(
    catalog_value -> 'recent_reviews'
  ) run(value)
  join content_factory.content_review_runs review
    on review.organization_id = organization_id
   and review.id::text = run.value ->> 'id'
  left join content_factory.content_review_assignments assignment
    on assignment.organization_id = review.organization_id
   and assignment.review_id = review.id
  where assignment.id is null;

  select coalesce(
    jsonb_agg(
      run.value || jsonb_build_object(
        'independent_assignment',
        case
          when coalesce(media.metadata ->> 'kind', '') not in (
            'generated_image', 'generated_video'
          ) then null
          else jsonb_build_object(
            'status', coalesce(assignment.status, 'unassigned'),
            'assigned_to_me',
              assignment.assignee_id is not distinct from user_id,
            'decision_eligible',
              actor_role in (
                'owner', 'admin', 'producer', 'reviewer'
              )
              and user_id is distinct from review.requested_by
              and user_id is distinct from media.owner_id
              and user_id is distinct from task.assignee_id
              and user_id is distinct from job.requested_by
              and user_id is distinct from job.assigned_to,
            'assigned_at', assignment.assigned_at,
            'completed_at', assignment.completed_at
          )
        end
      )
      order by run.ordinality
    ),
    '[]'::jsonb
  )
  into runs_value
  from jsonb_array_elements(
    catalog_value -> 'recent_reviews'
  ) with ordinality run(value, ordinality)
  join content_factory.content_review_runs review
    on review.organization_id = organization_id
   and review.id::text = run.value ->> 'id'
  join content_factory.media_objects media
    on media.organization_id = review.organization_id
   and media.id = review.media_object_id
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  left join content_factory.generation_jobs job
    on job.organization_id = review.organization_id
   and job.id::text = review.input ->> 'generation_job_id'
  left join content_factory.content_review_assignments assignment
    on assignment.organization_id = review.organization_id
   and assignment.review_id = review.id;

  return jsonb_set(
    catalog_value,
    '{recent_reviews}',
    runs_value,
    false
  );
end;
$$;

revoke all on function
  public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function
  public.creator_content_review_catalog(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

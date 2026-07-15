begin;

-- A manager-only, read-only funnel snapshot. It intentionally returns no auth
-- tokens, password data, provider payloads or payment references.
create or replace function public.creator_manager_dashboard(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin']
  );

  with course_requirement as (
    select count(*)::integer as required_count
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
  ),
  member_funnel as (
    select
      profile.display_name,
      profile.email,
      profile.status as profile_status,
      membership.role,
      membership.status as membership_status,
      membership.created_at as joined_at,
      auth_user.last_sign_in_at,
      auth_user.deleted_at is not null as auth_user_deleted,
      coalesce(auth_user.banned_until > now(), false) as auth_user_banned,
      (
        coalesce(
          auth_user.raw_app_meta_data -> 'contentengine_password_change_required'
            = 'true'::jsonb,
          false
        )
        or (
          not coalesce(
            auth_user.raw_app_meta_data -> 'contentengine_password_change_completed'
              = 'true'::jsonb,
            false
          )
          and (
            coalesce(
              auth_user.raw_app_meta_data -> 'contentengine_github_member_provisioned'
                = 'true'::jsonb,
              false
            )
            or coalesce(
              auth_user.raw_app_meta_data -> 'contentengine_owner_password_reset_once_20260714'
                = 'true'::jsonb,
              false
            )
          )
        )
      ) as password_change_required,
      requirement.required_count as courses_required,
      course_progress.completed_count as courses_completed,
      exam_progress.exam_passed,
      exam_progress.last_exam_at,
      latest_generation.status as generation_status,
      latest_generation.failure_code as generation_failure_code,
      latest_generation.updated_at as generation_updated_at,
      latest_placement.status as placement_status,
      latest_placement.platform as placement_platform,
      latest_placement.updated_at as placement_updated_at,
      latest_payout.status as payout_status,
      latest_payout.updated_at as payout_updated_at,
      latest_task.status as task_status,
      latest_task.task_type,
      latest_task.updated_at as task_updated_at,
      greatest(
        membership.created_at,
        coalesce(auth_user.last_sign_in_at, '-infinity'::timestamptz),
        coalesce(course_progress.last_course_at, '-infinity'::timestamptz),
        coalesce(exam_progress.last_exam_at, '-infinity'::timestamptz),
        coalesce(latest_generation.updated_at, '-infinity'::timestamptz),
        coalesce(latest_placement.updated_at, '-infinity'::timestamptz),
        coalesce(latest_payout.updated_at, '-infinity'::timestamptz),
        coalesce(latest_task.updated_at, '-infinity'::timestamptz)
      ) as last_activity_at
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
    left join auth.users auth_user
      on auth_user.id = membership.profile_id
    cross join course_requirement requirement
    left join lateral (
      select
        count(distinct certification.module_code)::integer as completed_count,
        max(certification.granted_at) as last_course_at
      from content_factory.training_certifications certification
      join content_factory.training_modules module
        on module.code = certification.module_code
       and module.module_type = 'course'
       and module.is_active
      join content_factory.training_attempts attempt
        on attempt.id = certification.attempt_id
       and attempt.organization_id = certification.organization_id
       and attempt.profile_id = certification.profile_id
       and attempt.module_code = certification.module_code
      where certification.organization_id = membership.organization_id
        and certification.profile_id = membership.profile_id
        and certification.status = 'passed'
        and (certification.expires_at is null or certification.expires_at > now())
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
    ) course_progress on true
    left join lateral (
      select
        true as exam_passed,
        certification.granted_at as last_exam_at
      from content_factory.training_certifications certification
      where certification.organization_id = membership.organization_id
        and certification.profile_id = membership.profile_id
        and certification.module_code = 'operator_final_exam'
        and certification.status = 'passed'
        and (certification.expires_at is null or certification.expires_at > now())
      order by certification.granted_at desc
      limit 1
    ) exam_progress on true
    left join lateral (
      select
        job.status,
        nullif(job.output ->> 'failure_code', '') as failure_code,
        job.updated_at
      from content_factory.generation_jobs job
      where job.organization_id = membership.organization_id
        and job.assigned_to = membership.profile_id
        and job.mode = 'real'
      order by
        case
          -- Active work remains visible, but an old terminal failure must not
          -- outrank a newer success/cancellation forever.
          when job.status in ('queued', 'starting', 'submitted', 'processing') then 0
          else 1
        end,
        job.updated_at desc,
        job.id desc
      limit 1
    ) latest_generation on true
    left join lateral (
      select placement.status, placement.platform, placement.updated_at
      from content_factory.placements placement
      where placement.organization_id = membership.organization_id
        and placement.assigned_to = membership.profile_id
      order by
        -- Failed is terminal: among terminal rows only the newest result wins.
        case when placement.status in ('scheduled', 'ready') then 0 else 1 end,
        placement.updated_at desc,
        placement.id desc
      limit 1
    ) latest_placement on true
    left join lateral (
      select payout.status, payout.updated_at
      from content_factory.creator_payouts payout
      where payout.organization_id = membership.organization_id
        and payout.profile_id = membership.profile_id
      order by
        case when payout.status in ('pending', 'approved') then 0 else 1 end,
        payout.updated_at desc,
        payout.id desc
      limit 1
    ) latest_payout on true
    left join lateral (
      select task.status, task.task_type, task.updated_at
      from content_factory.creator_tasks task
      where task.organization_id = membership.organization_id
        and task.assignee_id = membership.profile_id
      order by
        case when task.status in ('blocked', 'todo', 'in_progress', 'submitted', 'review') then 0 else 1 end,
        task.updated_at desc,
        task.id desc
      limit 1
    ) latest_task on true
    where membership.organization_id = organization_id
  ),
  classified_members as (
    select
      member.*,
      case
        when member.membership_status <> 'active'
          or member.profile_status <> 'active'
          or member.auth_user_deleted
          or member.auth_user_banned then 'access'
        when member.password_change_required or member.last_sign_in_at is null then 'login'
        when member.courses_completed < member.courses_required then 'course'
        when not coalesce(member.exam_passed, false) then 'exam'
        when member.generation_status in ('queued', 'starting', 'submitted', 'processing', 'failed') then 'generation'
        when member.task_status in ('blocked', 'todo', 'in_progress', 'submitted', 'review') then 'task'
        when member.placement_status in ('scheduled', 'ready', 'failed') then 'publication'
        when member.payout_status in ('pending', 'approved') then 'payout'
        else 'ready'
      end as stage,
      case
        when member.membership_status <> 'active' then 'membership_' || member.membership_status
        when member.profile_status = 'suspended' then 'profile_suspended'
        when member.profile_status = 'disabled' then 'profile_disabled'
        when member.auth_user_deleted then 'auth_user_deleted'
        when member.auth_user_banned then 'auth_user_banned'
        when member.password_change_required then 'temporary_password_change_required'
        when member.last_sign_in_at is null then 'first_login_pending'
        when member.courses_completed < member.courses_required then 'courses_incomplete'
        when not coalesce(member.exam_passed, false) then 'final_exam_pending'
        when member.generation_status = 'failed' then coalesce(member.generation_failure_code, 'generation_failed')
        when member.generation_status in ('queued', 'starting', 'submitted', 'processing') then 'generation_' || member.generation_status
        when member.task_status = 'blocked' then 'task_blocked'
        when member.task_status = 'todo' then 'task_todo'
        when member.task_status = 'in_progress' then 'task_in_progress'
        when member.task_status = 'submitted' then 'task_submitted'
        when member.task_status = 'review' then 'task_review'
        when member.placement_status = 'failed' then 'placement_failed'
        when member.placement_status in ('scheduled', 'ready') then 'placement_' || member.placement_status
        when member.payout_status = 'pending' then 'payout_pending'
        when member.payout_status = 'approved' then 'payout_approved_not_paid'
        else 'no_blocker'
      end as reason_code,
      case
        when member.membership_status <> 'active'
          or member.profile_status <> 'active'
          or member.auth_user_deleted
          or member.auth_user_banned then 'team'
        when member.password_change_required or member.last_sign_in_at is null then 'recovery'
        when member.courses_completed < member.courses_required then 'learn'
        when not coalesce(member.exam_passed, false) then 'exam'
        when member.generation_status in ('queued', 'starting', 'submitted', 'processing', 'failed') then 'generation_status'
        when member.task_status in ('blocked', 'todo', 'in_progress', 'submitted', 'review') then 'task'
        when member.placement_status in ('scheduled', 'ready', 'failed') then 'placement'
        when member.payout_status in ('pending', 'approved') then 'payout'
        else 'none'
      end as safe_action
    from member_funnel member
  ),
  latest_invite_per_email as (
    select distinct on (attempt.email)
      attempt.email,
      attempt.status,
      attempt.reason_code,
      attempt.delivery_status,
      attempt.membership_provisioned,
      attempt.requested_at
    from content_factory.invite_delivery_attempts attempt
    where attempt.organization_id = organization_id
    order by attempt.email, attempt.requested_at desc, attempt.created_at desc
  ),
  pending_invites as (
    select invite.*
    from latest_invite_per_email invite
    where not exists (
      select 1
      from content_factory.memberships membership
      join content_factory.profiles profile on profile.id = membership.profile_id
      where membership.organization_id = organization_id
        and lower(profile.email) = lower(invite.email)
    )
  )
  select jsonb_build_object(
    'ok', true,
    'generated_at', now(),
    'summary', jsonb_build_object(
      'email', (select count(*) from pending_invites),
      'login', count(*) filter (where member.stage = 'login'),
      'course', count(*) filter (where member.stage = 'course'),
      'exam', count(*) filter (where member.stage = 'exam'),
      'generation', count(*) filter (where member.stage = 'generation'),
      'task', count(*) filter (where member.stage = 'task'),
      'publication', count(*) filter (where member.stage = 'publication'),
      'payout', count(*) filter (where member.stage = 'payout'),
      'access', count(*) filter (where member.stage = 'access'),
      'ready', count(*) filter (where member.stage = 'ready')
    ),
    'members', coalesce(jsonb_agg(jsonb_build_object(
      'display_name', member.display_name,
      'email', member.email,
      'role', member.role,
      'membership_status', member.membership_status,
      'joined_at', member.joined_at,
      'last_sign_in_at', member.last_sign_in_at,
      'last_activity_at', member.last_activity_at,
      'password_change_required', member.password_change_required,
      'courses_completed', member.courses_completed,
      'courses_required', member.courses_required,
      'exam_passed', coalesce(member.exam_passed, false),
      'stage', member.stage,
      'reason_code', member.reason_code,
      'safe_action', member.safe_action,
      'generation_status', member.generation_status,
      'generation_updated_at', member.generation_updated_at,
      'placement_status', member.placement_status,
      'placement_platform', member.placement_platform,
      'placement_updated_at', member.placement_updated_at,
      'payout_status', member.payout_status,
      'payout_updated_at', member.payout_updated_at,
      'task_status', member.task_status,
      'task_type', member.task_type
    ) order by
      case member.stage
        when 'access' then 1
        when 'login' then 2
        when 'course' then 3
        when 'exam' then 4
        when 'generation' then 5
        when 'task' then 6
        when 'publication' then 7
        when 'payout' then 8
        else 9
      end,
      member.last_activity_at,
      member.display_name), '[]'::jsonb),
    'pending_invites', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'email', invite.email,
        'status', invite.status,
        'reason_code', invite.reason_code,
        'delivery_status', invite.delivery_status,
        'membership_provisioned', invite.membership_provisioned,
        'requested_at', invite.requested_at,
        'stage', 'email',
        'safe_action', case
          when invite.status in ('rate_limited', 'smtp_required', 'failed') then 'retry_invite'
          else 'wait_for_delivery'
        end
      ) order by invite.requested_at desc, invite.email), '[]'::jsonb)
      from pending_invites invite
    )
  ) into result
  from classified_members member;

  return result;
end;
$$;

revoke all on function public.creator_manager_dashboard(jsonb) from public, anon;
grant execute on function public.creator_manager_dashboard(jsonb) to authenticated;

commit;

begin;

-- Restore the intended creator_bootstrap wrapper chain.
--
-- Intended chain (outermost first):
--   public.creator_bootstrap                     (202608030005, untouched)
--   -> content_factory_private.creator_bootstrap_pre_training_waiver
--      course-check sanitizer                    (202607190002)
--   -> content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize
--      training practical project layer          (202607190001)
--   -> content_factory_private.creator_bootstrap_pre_practical_gate
--      password-change gate                      (202607160007)
--   -> content_factory_private.creator_bootstrap_pre_auth_email_gate
--      refreshed course-check gate               (202607140006)
--   -> content_factory_private.creator_bootstrap_pre_course_gate
--      base bootstrap                            (202607130004)
--
-- On cloud, creator_bootstrap_pre_training_waiver holds the wrong body (the
-- password-change gate from 202607160007 calling pre_auth_email_gate
-- directly), so the practical-project layer and the course-check sanitizer
-- are unreachable: learners never see training.practical_project /
-- practical_reviews / practical_upload, and bootstrap leaks course-check
-- grading diagnostics (attempt_id, correct_count, ...).  Server-side gates
-- (creator_submit_exam, membership_role) stayed intact, so nobody bypassed
-- the practical requirement; this migration only restores the visible flow.
--
-- Each body below is copied verbatim from its source migration, so replaying
-- this file on an already-correct database is a no-op and on the drifted
-- cloud database it re-pins the intended chain.  public.creator_bootstrap is
-- intentionally not touched.

-- Layer: password-change gate (canonical body from
-- 202607160007_auth_email_delivery.sql).  Calls
-- creator_bootstrap_pre_auth_email_gate and locks every capability
-- while auth_password_change_required is set.  On cloud this slot
-- currently holds an orphaned, superseded waiver overlay whose only
-- caller is creator_bootstrap_pre_assessment_v5_sanitize; its logic
-- lives on in public.creator_bootstrap (202608030005).
create or replace function content_factory_private.creator_bootstrap_pre_practical_gate(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
begin
  result :=
    content_factory_private.creator_bootstrap_pre_auth_email_gate(p_payload);

  if content_factory_private.auth_password_change_required(auth.uid()) then
    if jsonb_typeof(result) <> 'object' then
      result := '{}'::jsonb;
    end if;
    result := jsonb_set(
      result, '{state}', '"password_change_required"'::jsonb, true
    );
    result := jsonb_set(
      result, '{workspace_open}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{password_change_required}', 'true'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,real_generation}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,mock_generation}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,team_view}', 'false'::jsonb, true
    );
  else
    result := jsonb_set(
      result, '{password_change_required}', 'false'::jsonb, true
    );
  end if;

  return result;
end;
$$;

revoke all on function
  content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)
  from public, anon, authenticated;

-- Layer: training practical project (canonical body from
-- 202607190001_training_practical_review.sql).  Projects the learner
-- practical state, the bounded owner/admin review queue and the
-- private upload settings into bootstrap, and keeps the final exam
-- and workspace closed until the practical project is approved.
create or replace function content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result jsonb;
  user_id uuid;
  organization_id uuid;
  actor_role text;
  practical_project jsonb := 'null'::jsonb;
  practical_reviews jsonb := '[]'::jsonb;
  practical_approved boolean := false;
begin
  result := content_factory_private.creator_bootstrap_pre_practical_gate(
    p_payload
  );
  if jsonb_typeof(result) <> 'object'
     or coalesce(result ->> 'state', '') not in (
       'learning', 'workspace', 'password_change_required'
     )
     or nullif(result #>> '{organization,id}', '') is null then
    return result;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := (result #>> '{organization,id}')::uuid;
  select membership.role into actor_role
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';
  if actor_role is null then
    return result;
  end if;

  select content_factory_private.training_practical_project_json(project.id)
  into practical_project
  from content_factory.training_practical_projects project
  where project.organization_id = organization_id
    and project.profile_id = user_id;
  practical_project := coalesce(practical_project, 'null'::jsonb);
  practical_approved :=
    content_factory_private.training_practical_gate_satisfied(
      organization_id,
      user_id
    );

  if actor_role in ('owner', 'admin')
     and coalesce(result ->> 'state', '') <> 'password_change_required' then
    select coalesce(jsonb_agg(queue.item order by queue.sort_at, queue.id), '[]'::jsonb)
    into practical_reviews
    from (
      select
        project.id,
        coalesce(project.submitted_at, project.updated_at) as sort_at,
        content_factory_private.training_practical_project_json(project.id)
          || jsonb_build_object(
            'learner_name', coalesce(learner.display_name, learner.email),
            'learner_email', learner.email
          ) as item
      from content_factory.training_practical_projects project
      join content_factory.profiles learner
        on learner.id = project.profile_id
      where project.organization_id = organization_id
        and project.status in ('submitted', 'changes_requested')
      order by
        case when project.status = 'submitted' then 0 else 1 end,
        coalesce(project.submitted_at, project.updated_at),
        project.id
      limit 50
    ) queue;
  end if;

  result := result || jsonb_build_object(
    'training',
    coalesce(result -> 'training', '{}'::jsonb) || jsonb_build_object(
      'practical_project', practical_project,
      'practical_reviews', practical_reviews,
      'practical_upload', jsonb_build_object(
        'bucket_id', 'contentengine-training',
        'max_upload_bytes', 52428800,
        'accepted_mime_types', jsonb_build_array(
          'video/mp4', 'video/webm', 'video/quicktime'
        ),
        'path_prefix',
          organization_id::text || '/' || user_id::text || '/practical/'
      )
    )
  );
  result := jsonb_set(
    result,
    '{learning,practical_project_required}',
    to_jsonb(not practical_approved),
    true
  );

  if not practical_approved
     and coalesce(result ->> 'state', '') in ('learning', 'workspace') then
    result := jsonb_set(result, '{state}', '"learning"'::jsonb, true);
    result := jsonb_set(result, '{workspace_open}', 'false'::jsonb, true);
    result := jsonb_set(
      result, '{learning,exam,available}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{learning,exam,questions}', '[]'::jsonb, true
    );
    result := jsonb_set(
      result,
      '{learning,exam,blocked_reason}',
      '"practical_project_approval_required"'::jsonb,
      true
    );
    result := jsonb_set(
      result, '{capabilities,mock_generation}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,real_generation}', 'false'::jsonb, true
    );
  end if;
  return result;
end;
$$;

revoke all on function
  content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)
  from public, anon, authenticated;

-- Layer: course-check sanitizer (canonical body from
-- 202607190002_training_assessment_v5.sql).  THE repair line: on
-- cloud this slot holds the password-change gate body calling
-- creator_bootstrap_pre_auth_email_gate directly, which severed the
-- practical and sanitizer layers from the reachable chain.  The
-- canonical body calls creator_bootstrap_pre_assessment_v5_sanitize
-- and strips grading diagnostics from the course-check receipts.
create or replace function content_factory_private.creator_bootstrap_pre_training_waiver(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
  sanitized_checks jsonb;
begin
  result := content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(
    p_payload
  );

  if jsonb_typeof(result #> '{learning,course_checks}') = 'array' then
    select coalesce(
      jsonb_agg(
        check_item.value
          - 'attempt_id'
          - 'correct_count'
          - 'critical_error_count'
          - 'score_percent'
          - 'review_topics'
        order by check_item.ordinality
      ),
      '[]'::jsonb
    )
    into sanitized_checks
    from jsonb_array_elements(result #> '{learning,course_checks}')
      with ordinality check_item(value, ordinality);

    result := jsonb_set(
      result,
      '{learning,course_checks}',
      sanitized_checks,
      false
    );
  end if;

  if jsonb_typeof(result #> '{training,course_checks}') = 'array' then
    select coalesce(
      jsonb_agg(
        check_item.value
          - 'attempt_id'
          - 'correct_count'
          - 'critical_error_count'
          - 'score_percent'
          - 'review_topics'
        order by check_item.ordinality
      ),
      '[]'::jsonb
    )
    into sanitized_checks
    from jsonb_array_elements(result #> '{training,course_checks}')
      with ordinality check_item(value, ordinality);

    result := jsonb_set(
      result,
      '{training,course_checks}',
      sanitized_checks,
      false
    );
  end if;

  return result;
end;
$$;

revoke all on function
  content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)
  from public, anon, authenticated;

-- Fail loudly inside the transaction if any layer of the restored chain does
-- not match the verified wiring, so a drifted environment aborts instead of
-- partially applying.
do $training_practical_bootstrap_chain$
declare
  bootstrap_definition text;
  waiver_definition text;
  sanitize_definition text;
  practical_definition text;
  auth_email_definition text;
begin
  select pg_get_functiondef(
    'public.creator_bootstrap(jsonb)'::regprocedure
  ) into bootstrap_definition;
  select pg_get_functiondef(
    'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)'
      ::regprocedure
  ) into waiver_definition;
  select pg_get_functiondef(
    'content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)'
      ::regprocedure
  ) into sanitize_definition;
  select pg_get_functiondef(
    'content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)'
      ::regprocedure
  ) into practical_definition;
  select pg_get_functiondef(
    'content_factory_private.creator_bootstrap_pre_auth_email_gate(jsonb)'
      ::regprocedure
  ) into auth_email_definition;

  if bootstrap_definition is null
     or strpos(
       bootstrap_definition,
       'creator_bootstrap_pre_training_waiver('
     ) = 0 then
    raise exception 'training_practical_bootstrap_chain_invalid';
  end if;

  if waiver_definition is null
     or strpos(
       waiver_definition,
       'creator_bootstrap_pre_assessment_v5_sanitize('
     ) = 0
     or strpos(waiver_definition, '- ''attempt_id''') = 0
     or strpos(waiver_definition, '- ''correct_count''') = 0
     or strpos(waiver_definition, '- ''critical_error_count''') = 0
     or strpos(waiver_definition, '- ''score_percent''') = 0
     or strpos(waiver_definition, '- ''review_topics''') = 0
     or strpos(
       waiver_definition,
       'creator_bootstrap_pre_auth_email_gate('
     ) > 0 then
    raise exception 'training_practical_bootstrap_chain_invalid';
  end if;

  if sanitize_definition is null
     or strpos(
       sanitize_definition,
       'creator_bootstrap_pre_practical_gate('
     ) = 0
     or strpos(sanitize_definition, 'practical_project') = 0
     or strpos(sanitize_definition, 'training_practical_gate_satisfied(') = 0
     or strpos(sanitize_definition, 'contentengine-training') = 0 then
    raise exception 'training_practical_bootstrap_chain_invalid';
  end if;

  if practical_definition is null
     or strpos(
       practical_definition,
       'creator_bootstrap_pre_auth_email_gate('
     ) = 0
     or strpos(practical_definition, 'auth_password_change_required(') = 0 then
    raise exception 'training_practical_bootstrap_chain_invalid';
  end if;

  if auth_email_definition is null
     or strpos(
       auth_email_definition,
       'creator_bootstrap_pre_course_gate('
     ) = 0 then
    raise exception 'training_practical_bootstrap_chain_invalid';
  end if;

  if has_function_privilege(
       'authenticated',
       'content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'authenticated',
       'content_factory_private.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'authenticated',
       'content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)',
       'execute'
     ) then
    raise exception 'training_practical_bootstrap_chain_invalid';
  end if;
end;
$training_practical_bootstrap_chain$;

commit;

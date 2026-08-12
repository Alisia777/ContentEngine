begin;

-- Reuse the mature certification/course/practical-or-waiver boundary for an
-- operator too.  Existing assignment callers retain their explicit
-- owner/admin/producer/reviewer role filters, so this does not put operators
-- into the general reviewer pool.
do $allow_qualified_operator_in_reviewer_access_helper$
declare
  helper_signature constant regprocedure :=
    'content_factory_private.generated_media_reviewer_access_allowed(uuid,uuid)'::regprocedure;
  helper_definition text := pg_catalog.pg_get_functiondef(helper_signature);
  patched_definition text;
  old_roles constant text :=
    '''owner'', ''admin'', ''producer'', ''reviewer''';
  new_roles constant text :=
    '''owner'', ''admin'', ''producer'', ''reviewer'', ''operator''';
begin
  if strpos(helper_definition, new_roles) > 0 then
    return;
  end if;
  if strpos(helper_definition, old_roles) = 0
     or strpos(helper_definition, 'training_access_waiver_active') = 0
     or strpos(helper_definition, 'operator_final_exam') = 0
     or strpos(helper_definition, 'training_practical_gate_satisfied') = 0 then
    raise exception using
      errcode = '55000',
      message = 'generated_media_reviewer_access_helper_changed';
  end if;
  patched_definition := replace(helper_definition, old_roles, new_roles);
  if patched_definition = helper_definition then
    raise exception using
      errcode = '55000',
      message = 'qualified_operator_reviewer_access_patch_failed';
  end if;
  execute patched_definition;
end;
$allow_qualified_operator_in_reviewer_access_helper$;

-- A qualified operator may make the human decision for the exact generated
-- output they own inside the explicitly selected workspace project.  Keep
-- this relationship predicate separate from role allowlists so operators do
-- not become general reviewers for teammates' or foreign-project media.
create or replace function
  content_factory_private.qualified_operator_own_content_review_allowed(
    p_organization_id uuid,
    p_project_id uuid,
    p_review_id uuid,
    p_profile_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    p_organization_id is not null
    and p_project_id is not null
    and p_review_id is not null
    and p_profile_id is not null
    and content_factory_private.generated_media_reviewer_access_allowed(
      p_organization_id,
      p_profile_id
    )
    and content_factory_private.workspace_project_access_allowed(
      p_organization_id,
      p_project_id,
      p_profile_id
    )
    and exists (
      select 1
      from content_factory.memberships actor
      join content_factory.content_review_runs review
        on review.organization_id = actor.organization_id
       and review.id = p_review_id
       and review.project_id = p_project_id
       and review.requested_by = actor.profile_id
       and review.status = 'completed'
       and review.completion_hash is not null
       and review.input -> 'ai_generated' = 'true'::jsonb
       and jsonb_typeof(
         review.input -> 'external_ai_processing_confirmed'
       ) = 'boolean'
       and not (review.input ? 'context_amendment')
      join content_factory.media_objects media
        on media.organization_id = review.organization_id
       and media.id = review.media_object_id
       and media.project_id = review.project_id
       and media.owner_id = actor.profile_id
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
       and job.project_id = review.project_id
       and job.mode = 'real'
       and job.provider = 'runway'
       and job.allow_real_spend
       and job.status = 'succeeded'
       and job.actual_cost_minor > 0
       and job.product_id = media.product_id
       and job.output ->> 'output_media_id' = media.id::text
       and job.output ->> 'sha256' = media.sha256
       and job.input ->> 'model' = media.metadata ->> 'model'
       and (
         job.requested_by = actor.profile_id
         or job.assigned_to = actor.profile_id
       )
      where actor.organization_id = p_organization_id
        and actor.profile_id = p_profile_id
        and actor.status = 'active'
        and actor.role = 'operator'
    )
$$;

revoke all on function
  content_factory_private.qualified_operator_own_content_review_allowed(
    uuid, uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;

-- Direct decisions and the generated-video context command share one actor
-- gate.  The latter creates an immutable amended child before delegating to
-- the generic decision implementation, so map only a fully bound child back
-- to its exact immutable source.  Every other review is evaluated directly.
create or replace function
  content_factory_private.qualified_operator_content_review_command_allowed(
    p_organization_id uuid,
    p_project_id uuid,
    p_review_id uuid,
    p_profile_id uuid
  )
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select content_factory_private.qualified_operator_own_content_review_allowed(
    p_organization_id,
    p_project_id,
    coalesce(
      (
        select amendment.source_review_id
        from content_factory.content_review_context_amendments amendment
        join content_factory.content_review_runs child
          on child.organization_id = amendment.organization_id
         and child.id = amendment.amended_review_id
         and child.project_id = p_project_id
         and child.parent_review_id = amendment.source_review_id
         and child.media_object_id = amendment.media_object_id
         and child.completion_hash = amendment.amended_completion_hash
         and child.input #>> '{context_amendment,source_review_id}' =
               amendment.source_review_id::text
         and child.input #>> '{context_amendment,source_completion_hash}' =
               amendment.source_completion_hash
         and child.input #>> '{context_amendment,external_ai_invoked}' = 'false'
         and child.input #>> '{context_amendment,version}' in (
               'generated-photo-context-v1',
               'generated-video-context-v1'
             )
        join content_factory.content_review_runs source_review
          on source_review.organization_id = amendment.organization_id
         and source_review.id = amendment.source_review_id
         and source_review.project_id = child.project_id
         and source_review.media_object_id = amendment.media_object_id
         and source_review.completion_hash = amendment.source_completion_hash
         and source_review.media_sha256_snapshot = child.media_sha256_snapshot
        where amendment.organization_id = p_organization_id
          and amendment.amended_review_id = p_review_id
          and amendment.created_by = p_profile_id
      ),
      p_review_id
    ),
    p_profile_id
  )
$$;

revoke all on function
  content_factory_private.qualified_operator_content_review_command_allowed(
    uuid, uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;

-- Route an exact self-owned review to its qualified operator before the
-- established independent-review candidate query.  Any pre-existing
-- assignment still wins because the mature function checks it first.
do $patch_operator_first_assignment$
declare
  function_signature constant regprocedure :=
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure;
  function_definition text := pg_catalog.pg_get_functiondef(function_signature);
  target constant text := $target$
  select candidate.profile_id
  into assignee_id_value$target$;
  replacement constant text := $replacement$
  assignee_id_value := null;
  if content_factory_private.qualified_operator_own_content_review_allowed(
       p_organization_id,
       review_row.project_id,
       p_review_id,
       review_row.requested_by
     ) then
    assignee_id_value := review_row.requested_by;
    insert into content_factory.content_review_assignments (
      organization_id, review_id, assignee_id, status
    ) values (
      p_organization_id, p_review_id, assignee_id_value, 'assigned'
    )
    on conflict (organization_id, review_id) do nothing
    returning assignee_id into assignee_id_value;
    if assignee_id_value is null then
      select assignment.assignee_id into assignee_id_value
      from content_factory.content_review_assignments assignment
      where assignment.organization_id = p_organization_id
        and assignment.review_id = p_review_id
        and assignment.status = 'assigned';
    end if;
    if assignee_id_value is not null then
      return assignee_id_value;
    end if;
  end if;

  select candidate.profile_id
  into assignee_id_value$replacement$;
begin
  if strpos(
       function_definition,
       'qualified_operator_own_content_review_allowed('
     ) > 0 then
    return;
  end if;
  if strpos(function_definition, target) = 0 then
    raise exception using
      errcode = '55000',
      message = 'operator_first_assignment_patch_target_missing';
  end if;
  execute replace(function_definition, target, replacement);
end;
$patch_operator_first_assignment$;

-- Independent manager/reviewer fallback is project-local too.  This leaves a
-- valid pre-existing assignment untouched, but every new fallback candidate
-- must have explicit ACL for the exact review project.
do $patch_manager_assignment_project_acl$
declare
  function_signature constant regprocedure :=
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure;
  function_definition text := pg_catalog.pg_get_functiondef(function_signature);
  target constant text := $target$
    and content_factory_private.generated_media_reviewer_access_allowed(
      candidate.organization_id,
      candidate.profile_id
    )
    and candidate.profile_id is distinct from review_row.requested_by$target$;
  replacement constant text := $replacement$
    and content_factory_private.generated_media_reviewer_access_allowed(
      candidate.organization_id,
      candidate.profile_id
    )
    and content_factory_private.workspace_project_access_allowed(
      candidate.organization_id,
      review_row.project_id,
      candidate.profile_id
    )
    and candidate.profile_id is distinct from review_row.requested_by$replacement$;
begin
  if strpos(
       function_definition,
       'workspace_project_access_allowed('
     ) > 0 then
    return;
  end if;
  if strpos(function_definition, target) = 0 then
    raise exception using
      errcode = '55000',
      message = 'manager_assignment_project_acl_patch_target_missing';
  end if;
  execute replace(function_definition, target, replacement);
end;
$patch_manager_assignment_project_acl$;

-- Let only these existing review commands recognize the qualified operator
-- role.  The exact relationship and assignment checks below remain the
-- authority boundary; no general reviewer pool is widened.
do $patch_operator_review_command_roles$
declare
  function_signature regprocedure;
  function_definition text;
  patched_definition text;
  old_roles constant text :=
    '''owner'', ''admin'', ''producer'', ''reviewer''';
  new_roles constant text :=
    '''owner'', ''admin'', ''producer'', ''reviewer'', ''operator''';
begin
  foreach function_signature in array array[
    'content_factory_private.creator_decide_content_review_pre_project_v47(jsonb)'::regprocedure,
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'::regprocedure,
    'content_factory_private.creator_approve_generated_photo_review_with_context_pre_project_v47(jsonb)'::regprocedure,
    'content_factory_private.creator_approve_generated_video_review_with_context_pre_project_v47(jsonb)'::regprocedure,
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  ] loop
    function_definition := pg_catalog.pg_get_functiondef(function_signature);
    if strpos(function_definition, new_roles) > 0 then
      continue;
    end if;
    if strpos(function_definition, old_roles) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_review_command_role_patch_target_missing';
    end if;
    patched_definition := replace(function_definition, old_roles, new_roles);
    execute patched_definition;
  end loop;
end;
$patch_operator_review_command_roles$;

-- The outer sound-aware decision wrapper runs before the mature decision
-- implementation and before any sound normalization or recording.  Gate an
-- operator here too so unauthorized and replayed commands cannot do work in
-- an outer layer before the inner authority boundary is reached.
do $patch_operator_outer_decision_exact_gate$
declare
  function_signature constant regprocedure :=
    'content_factory_private.creator_decide_content_review_pre_project_v47(jsonb)'::regprocedure;
  function_definition text := pg_catalog.pg_get_functiondef(function_signature);
  declaration_target constant text := $target$
  organization_id uuid;
  review_id_value uuid;$target$;
  declaration_replacement constant text := $replacement$
  organization_id uuid;
  actor_role text;
  review_id_value uuid;$replacement$;
  role_target constant text := $target$
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );$target$;
  role_replacement constant text := $replacement$
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );$replacement$;
  target constant text := $target$
  review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');$target$;
  replacement constant text := $replacement$
  review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');
  if actor_role = 'operator'
     and not content_factory_private.qualified_operator_content_review_command_allowed(
       organization_id,
       nullif(
         current_setting('contentengine.project_id', true),
         ''
       )::uuid,
       review_id_value,
       user_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'role_not_allowed';
  end if;$replacement$;
begin
  if strpos(
       function_definition,
       'qualified_operator_content_review_command_allowed('
     ) > 0 then
    return;
  end if;
  if strpos(function_definition, declaration_replacement) = 0 then
    if strpos(function_definition, declaration_target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_outer_decision_role_declaration_target_missing';
    end if;
    function_definition := replace(
      function_definition,
      declaration_target,
      declaration_replacement
    );
  end if;
  if strpos(function_definition, role_replacement) = 0 then
    if strpos(function_definition, role_target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_outer_decision_role_capture_target_missing';
    end if;
    function_definition := replace(
      function_definition,
      role_target,
      role_replacement
    );
  end if;
  if strpos(function_definition, target) = 0 then
    raise exception using
      errcode = '55000',
      message = 'operator_outer_decision_exact_gate_target_missing';
  end if;
  execute replace(function_definition, target, replacement);
end;
$patch_operator_outer_decision_exact_gate$;

-- Role recognition is not authorization.  Every operator-enabled context
-- command must fail closed before it can record context or sound evidence
-- unless the exact source review satisfies the same generated-output lineage,
-- qualification and project-ACL predicate as a direct decision.  Managers and
-- reviewers retain their established independent-review behavior.
do $patch_operator_context_exact_gates$
declare
  function_signature regprocedure;
  function_definition text;
  target text;
  replacement text;
  declaration_target constant text := $target$
  organization_id uuid;
  source_review_id_value uuid;$target$;
  declaration_replacement constant text := $replacement$
  organization_id uuid;
  actor_role text;
  source_review_id_value uuid;$replacement$;
  role_target constant text := $target$
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );$target$;
  role_replacement constant text := $replacement$
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );$replacement$;
  operator_gate_needle constant text :=
    'message = ''role_not_allowed''';
begin
  function_signature :=
    'content_factory_private.creator_approve_generated_photo_review_with_context_pre_project_v47(jsonb)'::regprocedure;
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(function_definition, operator_gate_needle) = 0 then
    target := $target$
  source_review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');$target$;
    replacement := $replacement$
  source_review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');
  if actor_role = 'operator'
     and not content_factory_private.qualified_operator_content_review_command_allowed(
       organization_id,
       nullif(
         current_setting('contentengine.project_id', true),
         ''
       )::uuid,
       source_review_id_value,
       user_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'role_not_allowed';
  end if;$replacement$;
    if strpos(function_definition, target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_photo_context_exact_gate_target_missing';
    end if;
    execute replace(function_definition, target, replacement);
  end if;

  foreach function_signature in array array[
    'content_factory_private.creator_approve_generated_video_review_with_context_pre_project_v47(jsonb)'::regprocedure,
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  ] loop
    function_definition := pg_catalog.pg_get_functiondef(function_signature);
    if strpos(function_definition, operator_gate_needle) > 0 then
      continue;
    end if;
    if strpos(function_definition, declaration_replacement) = 0 then
      if strpos(function_definition, declaration_target) = 0 then
        raise exception using
          errcode = '55000',
          message = 'operator_video_context_role_declaration_target_missing';
      end if;
      function_definition := replace(
        function_definition,
        declaration_target,
        declaration_replacement
      );
    end if;
    if strpos(function_definition, role_replacement) = 0 then
      if strpos(function_definition, role_target) = 0 then
        raise exception using
          errcode = '55000',
          message = 'operator_video_context_role_capture_target_missing';
      end if;
      function_definition := replace(
        function_definition,
        role_target,
        role_replacement
      );
    end if;
    target := $target$
  source_review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');$target$;
    replacement := $replacement$
  source_review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');
  if actor_role = 'operator'
     and not content_factory_private.qualified_operator_content_review_command_allowed(
       organization_id,
       nullif(
         current_setting('contentengine.project_id', true),
         ''
       )::uuid,
       source_review_id_value,
       user_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'role_not_allowed';
  end if;$replacement$;
    if strpos(function_definition, target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_video_context_exact_gate_target_missing';
    end if;
    execute replace(function_definition, target, replacement);
  end loop;
end;
$patch_operator_context_exact_gates$;

-- Context-amendment approval retains all mature media/product/compliance
-- validation.  Relax only its creator-independence branch for the same exact
-- qualified operator predicate; the assignment trigger still binds the child
-- decision back to the source review assignee.
do $patch_operator_context_independence$
declare
  function_signature regprocedure;
  function_definition text;
  target text;
  replacement text;
begin
  function_signature :=
    'content_factory_private.creator_approve_generated_photo_review_with_context_pre_project_v47(jsonb)'::regprocedure;
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       'qualified_operator_own_content_review_allowed('
     ) = 0 then
    target := $target$
  if user_id in (
    media_row.owner_id,
    task_row.assignee_id,
    job_row.requested_by,
    job_row.assigned_to
  ) then
    raise exception using
      errcode = '42501',
      message = 'generated_image_independent_review_required';
  end if;$target$;
    replacement := $replacement$
  if user_id in (
    media_row.owner_id,
    task_row.assignee_id,
    job_row.requested_by,
    job_row.assigned_to
  ) and not content_factory_private.qualified_operator_own_content_review_allowed(
    organization_id,
    source_review_row.project_id,
    source_review_id_value,
    user_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'generated_image_independent_review_required';
  end if;$replacement$;
    if strpos(function_definition, target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_photo_context_independence_patch_target_missing';
    end if;
    execute replace(function_definition, target, replacement);
  end if;

  function_signature :=
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure;
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(
       function_definition,
       'qualified_operator_own_content_review_allowed('
     ) = 0 then
    target := $target$
  if user_id in (
    media_row.owner_id,
    task_row.assignee_id,
    job_row.requested_by,
    job_row.assigned_to
  ) then
    raise exception using
      errcode = '42501',
      message = 'generated_video_independent_review_required';
  end if;$target$;
    replacement := $replacement$
  if user_id in (
    media_row.owner_id,
    task_row.assignee_id,
    job_row.requested_by,
    job_row.assigned_to
  ) and not content_factory_private.qualified_operator_own_content_review_allowed(
    organization_id,
    source_review_row.project_id,
    source_review_id_value,
    user_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'generated_video_independent_review_required';
  end if;$replacement$;
    if strpos(function_definition, target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_video_context_independence_patch_target_missing';
    end if;
    execute replace(function_definition, target, replacement);
  end if;
end;
$patch_operator_context_independence$;

do $patch_context_external_ai_boolean$
declare
  function_signature regprocedure;
  function_definition text;
  patched_definition text;
  target_pattern constant text :=
    'source_review_row[.]input[[:space:]]*->[[:space:]]*''external_ai_processing_confirmed''[[:space:]]*is[[:space:]]+distinct[[:space:]]+from[[:space:]]+''true''::jsonb';
  replacement constant text :=
    'jsonb_typeof(source_review_row.input -> ''external_ai_processing_confirmed'') is distinct from ''boolean''';
begin
  foreach function_signature in array array[
    'content_factory_private.creator_approve_generated_photo_review_with_context_pre_project_v47(jsonb)'::regprocedure,
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  ] loop
    function_definition := pg_catalog.pg_get_functiondef(function_signature);
    if strpos(function_definition, replacement) > 0 then
      continue;
    end if;
    patched_definition := pg_catalog.regexp_replace(
      function_definition,
      target_pattern,
      replacement,
      'i'
    );
    if patched_definition = function_definition then
      raise exception using
        errcode = '55000',
        message = 'context_external_ai_boolean_patch_target_missing';
    end if;
    execute patched_definition;
  end loop;
end;
$patch_context_external_ai_boolean$;

-- Preserve the independent-review rule for every other participant while
-- permitting only the exact self-owned, qualified and project-authorized
-- operator.  Require a complete human watch for every outcome, not approval
-- alone.
do $patch_operator_self_decision_gates$
declare
  function_signature constant regprocedure :=
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'::regprocedure;
  function_definition text := pg_catalog.pg_get_functiondef(function_signature);
  independence_target constant text := $target$
  ) and not content_factory_private.solo_owner_content_review_allowed(
    organization_id,
    review_id_value,
    user_id
  ) then$target$;
  independence_replacement constant text := $replacement$
  ) and not content_factory_private.solo_owner_content_review_allowed(
    organization_id,
    review_id_value,
    user_id
  ) and not content_factory_private.qualified_operator_content_review_command_allowed(
    organization_id,
    review_row.project_id,
    review_id_value,
    user_id
  ) then$replacement$;
  operator_gate_target constant text := $target$
  request_payload := jsonb_build_object($target$;
  operator_gate_replacement constant text := $replacement$
  if actor_role = 'operator'
     and not content_factory_private.qualified_operator_content_review_command_allowed(
       organization_id,
       nullif(
         current_setting('contentengine.project_id', true),
         ''
       )::uuid,
       review_id_value,
       user_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'role_not_allowed';
  end if;

  request_payload := jsonb_build_object($replacement$;
  watch_target constant text := $target$
  if (
    content_factory_private.content_review_is_high_risk(review_row.result)$target$;
  watch_replacement constant text := $replacement$
  if not media_watched_value then
    raise exception using
      errcode = '22023',
      message = 'content_review_media_watch_required';
  end if;

  if (
    content_factory_private.content_review_is_high_risk(review_row.result)$replacement$;
begin
  if strpos(function_definition, independence_replacement) = 0 then
    if strpos(function_definition, independence_target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_self_decision_independence_patch_target_missing';
    end if;
    function_definition := replace(
      function_definition,
      independence_target,
      independence_replacement
    );
  end if;
  if strpos(function_definition, operator_gate_replacement) = 0 then
    if strpos(function_definition, operator_gate_target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_exact_decision_gate_target_missing';
    end if;
    function_definition := replace(
      function_definition,
      operator_gate_target,
      operator_gate_replacement
    );
  end if;
  if strpos(function_definition, watch_replacement) = 0 then
    if strpos(function_definition, watch_target) = 0 then
      raise exception using
        errcode = '55000',
        message = 'operator_self_decision_watch_patch_target_missing';
    end if;
    function_definition := replace(
      function_definition,
      watch_target,
      watch_replacement
    );
  end if;
  execute function_definition;
end;
$patch_operator_self_decision_gates$;

-- Keep catalog/deep-link read truth aligned with assignment and mutation
-- truth.  This patches the established assignment enrichment under the
-- project and sound wrappers rather than replacing either public wrapper.
do $patch_operator_catalog_decision_eligibility$
declare
  function_signature constant regprocedure :=
    'content_factory_private.creator_content_review_catalog_without_repair_actions(jsonb)'::regprocedure;
  function_definition text := pg_catalog.pg_get_functiondef(function_signature);
  target constant text := $target$
              or content_factory_private.solo_owner_content_review_allowed(
                organization_id,
                review.id,
                user_id
              ),$target$;
  replacement constant text := $replacement$
              or content_factory_private.solo_owner_content_review_allowed(
                organization_id,
                review.id,
                user_id
              )
              or (
                assignment.status = 'assigned'
                and assignment.assignee_id = user_id
                and content_factory_private.qualified_operator_own_content_review_allowed(
                  organization_id,
                  review.project_id,
                  review.id,
                  user_id
                )
              ),$replacement$;
begin
  if strpos(
       function_definition,
       'qualified_operator_own_content_review_allowed('
     ) > 0 then
    return;
  end if;
  if strpos(function_definition, target) = 0 then
    raise exception using
      errcode = '55000',
      message = 'operator_catalog_eligibility_patch_target_missing';
  end if;
  execute replace(function_definition, target, replacement);
end;
$patch_operator_catalog_decision_eligibility$;

-- Paid generated output is still exact generated output when the human form
-- records external-AI processing as either true or false.  Assignment and its
-- fail-closed decision trigger must use the same typed-boolean boundary.
do $patch_generated_assignment_external_ai_boolean$
declare
  function_signature regprocedure;
  function_definition text;
  patched_definition text;
  equality_pattern constant text :=
    'review[.]input[[:space:]]*->[[:space:]]*''external_ai_processing_confirmed''[[:space:]]*=[[:space:]]*''true''::jsonb';
  equality_replacement constant text :=
    'jsonb_typeof(review.input -> ''external_ai_processing_confirmed'') = ''boolean''';
  distinct_pattern constant text :=
    'review_row[.]input[[:space:]]*->[[:space:]]*''external_ai_processing_confirmed''[[:space:]]*is[[:space:]]+distinct[[:space:]]+from[[:space:]]+''true''::jsonb';
  distinct_replacement constant text :=
    'jsonb_typeof(review_row.input -> ''external_ai_processing_confirmed'') is distinct from ''boolean''';
begin
  function_signature :=
    'content_factory_private.generated_media_review_assignment_required(uuid,uuid)'::regprocedure;
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(function_definition, equality_replacement) = 0 then
    patched_definition := pg_catalog.regexp_replace(
      function_definition,
      equality_pattern,
      equality_replacement,
      'i'
    );
    if patched_definition = function_definition then
      raise exception using
        errcode = '55000',
        message = 'assignment_required_external_ai_patch_target_missing';
    end if;
    execute patched_definition;
  end if;

  function_signature :=
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure;
  function_definition := pg_catalog.pg_get_functiondef(function_signature);
  if strpos(function_definition, distinct_replacement) = 0 then
    patched_definition := pg_catalog.regexp_replace(
      function_definition,
      distinct_pattern,
      distinct_replacement,
      'i'
    );
    if patched_definition = function_definition then
      raise exception using
        errcode = '55000',
        message = 'assignment_external_ai_patch_target_missing';
    end if;
    execute patched_definition;
  end if;
end;
$patch_generated_assignment_external_ai_boolean$;

-- A self-issued negative decision may enter the repair policy only through
-- the same exact operator predicate. Approval/rejection remain non-repair
-- outcomes, and the paid rerun command still requires its separate explicit
-- spend confirmation.
do $patch_operator_self_needs_changes_repair$
declare
  function_signature constant regprocedure :=
    'content_factory_private.creator_generation_repair_policy_structured_scores_v1(jsonb)'::regprocedure;
  function_definition text := pg_catalog.pg_get_functiondef(function_signature);
  target constant text := $target$
     or decision_row.decided_by in (
       job_row.requested_by,
       job_row.assigned_to
     )
     or media_row.status <> 'ready'$target$;
  replacement constant text := $replacement$
     or (
       decision_row.decided_by in (
         job_row.requested_by,
         job_row.assigned_to
       )
       and not content_factory_private.qualified_operator_own_content_review_allowed(
         organization_id,
         review_row.project_id,
         review_id_value,
         decision_row.decided_by
       )
     )
     or media_row.status <> 'ready'$replacement$;
begin
  if strpos(
       function_definition,
       'qualified_operator_own_content_review_allowed('
     ) > 0 then
    return;
  end if;
  if strpos(function_definition, target) = 0 then
    raise exception using
      errcode = '55000',
      message = 'operator_self_repair_patch_target_missing';
  end if;
  execute replace(function_definition, target, replacement);
end;
$patch_operator_self_needs_changes_repair$;

-- Exact deep links use the status RPC directly.  Delegate through the whole
-- project/sound wrapper chain first, then expose the same assignment truth as
-- the catalog.  Existing assigned reviewers remain eligible; only the exact
-- qualified operator predicate adds self eligibility.
do $preserve_status_before_operator_self_truth$
begin
  if to_regprocedure(
    'content_factory_private.creator_review_status_pre_operator_self_v1(jsonb)'
  ) is null then
    alter function public.creator_content_review_status(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_content_review_status(jsonb)
      rename to creator_review_status_pre_operator_self_v1;
  end if;
end;
$preserve_status_before_operator_self_truth$;

revoke all on function
  content_factory_private.creator_review_status_pre_operator_self_v1(jsonb)
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
  project_id_value uuid;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  assignment_row content_factory.content_review_assignments%rowtype;
  assignment_value jsonb;
  assigned_to_me_value boolean := false;
  decision_eligible_value boolean := false;
begin
  -- This delegate owns payload validation, exact project entity matching and
  -- explicit project ACL.  No table read below occurs before it succeeds.
  result_value := content_factory_private
    .creator_review_status_pre_operator_self_v1(p_payload);
  user_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  review_id_value := (result_value #>> '{run,id}')::uuid;

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id_value
    and review.project_id = project_id_value
    and review.id = review_id_value;
  if review_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'project_entity_mismatch';
  end if;
  perform content_factory_private.assign_generated_media_review(
    organization_id_value,
    review_id_value
  );
  select assignment.* into assignment_row
  from content_factory.content_review_assignments assignment
  where assignment.organization_id = review_row.organization_id
    and assignment.review_id = review_row.id;

  assigned_to_me_value :=
    coalesce(
      assignment_row.status = 'assigned'
      and assignment_row.assignee_id = user_id_value,
      false
    );
  -- assign_generated_media_review has already applied either the independent
  -- reviewer gates or the exact qualified-operator predicate.  Eligibility
  -- must still be paired with the current assigned state, so completed or
  -- manager-owned assignments never leak a role-only self permission.
  decision_eligible_value := assigned_to_me_value;
  assignment_value := jsonb_build_object(
    'status', coalesce(assignment_row.status, 'unassigned'),
    'assigned_to_me', assigned_to_me_value,
    'decision_eligible', decision_eligible_value,
    'assigned_at', assignment_row.assigned_at,
    'completed_at', assignment_row.completed_at
  );
  return jsonb_set(
    result_value,
    '{run}',
    (result_value -> 'run') || jsonb_build_object(
      'independent_assignment', assignment_value
    ),
    false
  );
end;
$$;

revoke all on function public.creator_content_review_status(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_status(jsonb)
  to authenticated;

-- Route only still-unassigned completed work.  The mature resolver is
-- idempotent, preserves any prior manager assignment, and performs no paid
-- provider call.
do $backfill_operator_self_review_assignments$
declare
  review_record record;
begin
  for review_record in
    select review.organization_id, review.id
    from content_factory.content_review_runs review
    where review.status = 'completed'
      and not exists (
        select 1
        from content_factory.content_review_decisions decision
        where decision.organization_id = review.organization_id
          and decision.review_id = review.id
      )
      and not exists (
        select 1
        from content_factory.content_review_assignments assignment
        where assignment.organization_id = review.organization_id
          and assignment.review_id = review.id
      )
      and content_factory_private.qualified_operator_own_content_review_allowed(
        review.organization_id,
        review.project_id,
        review.id,
        review.requested_by
      )
    order by review.created_at, review.id
  loop
    perform content_factory_private.assign_generated_media_review(
      review_record.organization_id,
      review_record.id
    );
  end loop;
end;
$backfill_operator_self_review_assignments$;

do $verify_operator_self_review_contract$
declare
  command_helper_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.qualified_operator_content_review_command_allowed(uuid,uuid,uuid,uuid)'::regprocedure
  ));
  assignment_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.assign_generated_media_review(uuid,uuid)'::regprocedure
  ));
  outer_decision_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_pre_project_v47(jsonb)'::regprocedure
  ));
  decision_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'::regprocedure
  ));
  photo_context_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_approve_generated_photo_review_with_context_pre_project_v47(jsonb)'::regprocedure
  ));
  video_context_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'::regprocedure
  ));
  video_context_wrapper_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_with_context_pre_project_v47(jsonb)'::regprocedure
  ));
  repair_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_generation_repair_policy_structured_scores_v1(jsonb)'::regprocedure
  ));
  catalog_definition text := lower(pg_catalog.pg_get_functiondef(
    'content_factory_private.creator_content_review_catalog_without_repair_actions(jsonb)'::regprocedure
  ));
  status_definition text := lower(pg_catalog.pg_get_functiondef(
    'public.creator_content_review_status(jsonb)'::regprocedure
  ));
begin
  if strpos(command_helper_definition, 'content_review_context_amendments') = 0
     or strpos(command_helper_definition, 'source_completion_hash') = 0
     or strpos(command_helper_definition, 'amended_completion_hash') = 0
     or strpos(command_helper_definition, 'qualified_operator_own_content_review_allowed(') = 0
     or strpos(assignment_definition, 'qualified_operator_own_content_review_allowed(') = 0
     or strpos(assignment_definition, 'workspace_project_access_allowed(') = 0
     or strpos(assignment_definition, 'external_ai_processing_confirmed') = 0
     or strpos(outer_decision_definition, 'qualified_operator_content_review_command_allowed(') = 0
     or strpos(outer_decision_definition, 'if actor_role = ''operator''') = 0
     or strpos(outer_decision_definition, 'message = ''role_not_allowed''') = 0
     or strpos(outer_decision_definition, 'qualified_operator_content_review_command_allowed(')
          > strpos(outer_decision_definition, 'normalize_content_review_sound_assessment(')
     or strpos(decision_definition, 'qualified_operator_content_review_command_allowed(') = 0
     or strpos(decision_definition, 'if actor_role = ''operator''') = 0
     or strpos(decision_definition, 'message = ''role_not_allowed''') = 0
     or strpos(decision_definition, 'qualified_operator_content_review_command_allowed(')
          > strpos(decision_definition, 'begin_command(')
     or strpos(decision_definition, 'if not media_watched_value then') = 0
     or strpos(photo_context_definition, 'qualified_operator_content_review_command_allowed(') = 0
     or strpos(photo_context_definition, 'if actor_role = ''operator''') = 0
     or strpos(photo_context_definition, 'message = ''role_not_allowed''') = 0
     or strpos(photo_context_definition, 'qualified_operator_content_review_command_allowed(')
          > strpos(photo_context_definition, 'begin_command(')
     or strpos(video_context_definition, 'qualified_operator_content_review_command_allowed(') = 0
     or strpos(video_context_definition, 'if actor_role = ''operator''') = 0
     or strpos(video_context_definition, 'message = ''role_not_allowed''') = 0
     or strpos(video_context_definition, 'qualified_operator_content_review_command_allowed(')
          > strpos(video_context_definition, 'begin_command(')
     or strpos(video_context_wrapper_definition, 'qualified_operator_content_review_command_allowed(') = 0
     or strpos(video_context_wrapper_definition, 'if actor_role = ''operator''') = 0
     or strpos(video_context_wrapper_definition, 'message = ''role_not_allowed''') = 0
     or strpos(video_context_wrapper_definition, 'qualified_operator_content_review_command_allowed(')
          > strpos(video_context_wrapper_definition, 'normalize_content_review_sound_assessment(')
     or strpos(repair_definition, 'qualified_operator_own_content_review_allowed(') = 0
     or strpos(catalog_definition, 'qualified_operator_own_content_review_allowed(') = 0
     or strpos(status_definition, '''independent_assignment''') = 0
     or strpos(status_definition, 'assign_generated_media_review(') = 0 then
    raise exception using
      errcode = '55000',
      message = 'operator_self_content_review_contract_invalid';
  end if;
end;
$verify_operator_self_review_contract$;

notify pgrst, 'reload schema';

commit;

begin;

-- The waiver migration renames the installed practical gate before wrapping
-- it.  PostgreSQL preserves the old PL/pgSQL body during a rename, including
-- references qualified with the former function name.  Recompile the renamed
-- implementation with positional arguments copied into stable local names so
-- every workspace RPC can authorize an active member again.
create or replace function
  content_factory_private.membership_role_pre_training_waiver(
    organization_id uuid,
    require_certification boolean default false,
    allowed_roles text[] default null
  )
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  target_organization_id uuid := $1;
  certification_required boolean := $2;
  role_allowlist text[] := $3;
  user_id uuid := auth.uid();
  actor_role text;
  practical_pre_gate regprocedure :=
    pg_catalog.to_regprocedure(
      'content_factory_private.membership_role_pre_practical_gate(uuid,boolean,text[])'
    );
  practical_status_gate regprocedure :=
    pg_catalog.to_regprocedure(
      'content_factory_private.training_practical_gate_satisfied(uuid,uuid)'
    );
  practical_satisfied boolean;
begin
  if practical_pre_gate is not null
     and practical_status_gate is not null then
    execute
      'select content_factory_private.membership_role_pre_practical_gate($1, $2, $3)'
      into actor_role
      using
        target_organization_id,
        certification_required,
        role_allowlist;

    if certification_required then
      execute
        'select content_factory_private.training_practical_gate_satisfied($1, $2)'
        into practical_satisfied
        using target_organization_id, user_id;

      if not coalesce(practical_satisfied, false) then
        raise exception using
          errcode = '42501',
          message = 'practical_project_approval_required';
      end if;
    end if;

    return actor_role;
  end if;

  if practical_pre_gate is not null
     or practical_status_gate is not null then
    raise exception using
      errcode = '42501',
      message = 'practical_gate_dependency_incomplete';
  end if;

  -- Older installations predate the practical-review migration. Preserve the
  -- complete course and final-exam boundary that was installed there.
  if user_id is null then
    raise exception using
      errcode = '42501',
      message = 'authentication_required';
  end if;

  select membership.role into actor_role
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = target_organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';

  if actor_role is null then
    raise exception using
      errcode = '42501',
      message = 'active_membership_required';
  end if;

  if role_allowlist is not null
     and not (actor_role = any(role_allowlist)) then
    raise exception using
      errcode = '42501',
      message = 'role_not_allowed';
  end if;

  if certification_required and not exists (
    select 1
    from content_factory.training_certifications certification
    where certification.organization_id = target_organization_id
      and certification.profile_id = user_id
      and certification.module_code = 'operator_final_exam'
      and certification.status = 'passed'
      and (
        certification.expires_at is null
        or certification.expires_at > now()
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'final_exam_required';
  end if;

  if certification_required and exists (
    select 1
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
      and not exists (
        select 1
        from content_factory.training_certifications certification
        join content_factory.training_attempts attempt
          on attempt.id = certification.attempt_id
         and attempt.organization_id = certification.organization_id
         and attempt.profile_id = certification.profile_id
         and attempt.module_code = certification.module_code
        where certification.organization_id = target_organization_id
          and certification.profile_id = user_id
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
  ) then
    raise exception using
      errcode = '42501',
      message = 'refreshed_courses_required';
  end if;

  return actor_role;
end;
$$;

revoke all on function
  content_factory_private.membership_role_pre_training_waiver(
    uuid, boolean, text[]
  )
  from public, anon, authenticated;

do $training_waiver_membership_gate_repair_contract$
declare
  pre_waiver_definition text;
  waiver_definition text;
begin
  select lower(pg_get_functiondef(
    'content_factory_private.membership_role_pre_training_waiver(uuid,boolean,text[])'
      ::regprocedure
  )) into pre_waiver_definition;

  select lower(pg_get_functiondef(
    'content_factory_private.membership_role(uuid,boolean,text[])'
      ::regprocedure
  )) into waiver_definition;

  if pre_waiver_definition is null
     or strpos(
       pre_waiver_definition,
       'target_organization_id uuid := $1'
     ) = 0
     or strpos(
       pre_waiver_definition,
       'to_regprocedure('
     ) = 0
     or strpos(
       pre_waiver_definition,
       'practical_gate_dependency_incomplete'
     ) = 0
     or strpos(
       pre_waiver_definition,
       'where membership.organization_id = target_organization_id'
     ) = 0
     or strpos(
       pre_waiver_definition,
       'where certification.organization_id = target_organization_id'
     ) = 0
     or strpos(
       pre_waiver_definition,
       'membership_role.organization_id'
     ) > 0 then
    raise exception 'pre_training_waiver_membership_gate_repair_invalid';
  end if;

  if waiver_definition is null
     or strpos(
       waiver_definition,
       'membership_role_pre_training_waiver('
     ) = 0
     or strpos(
       waiver_definition,
       'training_access_waiver_active('
     ) = 0 then
    raise exception 'training_waiver_membership_gate_wrapper_invalid';
  end if;

  if has_function_privilege(
    'authenticated',
    'content_factory_private.membership_role_pre_training_waiver(uuid,boolean,text[])',
    'EXECUTE'
  ) then
    raise exception 'private_pre_training_waiver_gate_is_browser_callable';
  end if;
end;
$training_waiver_membership_gate_repair_contract$;

commit;

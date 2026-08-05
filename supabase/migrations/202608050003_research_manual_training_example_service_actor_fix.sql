begin;

-- The browser RPC remains owner/admin/producer-only.  The service-only repair
-- is additionally allowed to attribute the one-time operation to an active
-- operator when historical organization data has no active owner row.  The
-- GitHub production environment and service-role grant remain the authority.

create or replace function public.system_register_research_training_example(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  project_id_value uuid;
  actor_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  select project.organization_id into organization_id_value
  from content_factory.workspace_folders project
  where project.id = project_id_value
    and project.kind = 'project'
    and project.status = 'active'
  limit 1;
  if organization_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_training_example_project_not_found';
  end if;

  select membership.profile_id into actor_id_value
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = organization_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin', 'producer', 'operator')
  order by case membership.role
    when 'owner' then 0
    when 'admin' then 1
    when 'producer' then 2
    else 3
  end,
  membership.created_at,
  membership.id
  limit 1;
  if actor_id_value is null then
    raise exception using
      errcode = '55000', message = 'research_training_example_actor_required';
  end if;

  return content_factory_private.register_research_training_example(
    organization_id_value,
    actor_id_value,
    p_payload
  );
end;
$$;

revoke all on function
  public.system_register_research_training_example(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_register_research_training_example(jsonb)
  to service_role;

commit;

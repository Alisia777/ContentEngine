begin;

-- Bootstrap the governed manual-example boundary.  The runtime implementation
-- is installed by the immediately following migration so this migration stays
-- independently parseable and fail-closed during an interrupted deployment.

create or replace function content_factory_private.research_youtube_video_id(
  value text
)
returns text
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  source_url text := btrim(value);
  matched text[];
begin
  if length(source_url) not between 20 and 2048
     or source_url !~* '^https://[^[:space:]]+$' then
    return null;
  end if;

  matched := regexp_match(
    source_url,
    '^https://(www[.]|m[.])?youtu[.]be/([A-Za-z0-9_-]{11})([/?#&].*)?$',
    'i'
  );
  if matched is not null then
    return matched[2];
  end if;

  matched := regexp_match(
    source_url,
    '^https://(www[.]|m[.])?youtube[.]com/(shorts|embed|live)/([A-Za-z0-9_-]{11})([/?#&].*)?$',
    'i'
  );
  if matched is not null then
    return matched[3];
  end if;

  if source_url ~* '^https://(www[.]|m[.])?youtube[.]com/watch[?]' then
    matched := regexp_match(
      source_url,
      '[?&]v=([A-Za-z0-9_-]{11})($|[&#])',
      'i'
    );
    if matched is not null then
      return matched[1];
    end if;
  end if;

  return null;
end;
$$;

create or replace function content_factory_private.register_research_training_example(
  p_organization_id uuid,
  p_actor_id uuid,
  p_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'research_training_example_runtime_revision_required';
end;
$$;

create or replace function public.creator_register_research_training_example(
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
  organization_id_value uuid;
  project_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
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
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer']
  );
  return content_factory_private.register_research_training_example(
    organization_id_value,
    user_id,
    p_payload
  );
end;
$$;

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
    and membership.role in ('owner', 'admin', 'producer')
  order by case membership.role
    when 'owner' then 0 when 'admin' then 1 else 2 end,
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
  public.creator_register_research_training_example(jsonb)
  from public, anon;
grant execute on function
  public.creator_register_research_training_example(jsonb)
  to authenticated;

revoke all on function
  public.system_register_research_training_example(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_register_research_training_example(jsonb)
  to service_role;

commit;

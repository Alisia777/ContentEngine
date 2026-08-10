begin;

-- The project-scoped catalog already filters media_objects to ready rows, but
-- its serialized media JSON predates the status field.  Browser consumers must
-- not infer readiness from inclusion alone: expose the authoritative row state
-- and product identity while preserving the complete existing catalog/ACL
-- implementation behind this narrow response wrapper.
do $preserve_review_catalog_before_media_status$
begin
  if to_regprocedure(
    'content_factory_private.creator_content_review_catalog_pre_media_status(jsonb)'
  ) is null then
    alter function public.creator_content_review_catalog(jsonb)
      set schema content_factory_private;
    alter function
      content_factory_private.creator_content_review_catalog(jsonb)
      rename to creator_content_review_catalog_pre_media_status;
  end if;
end;
$preserve_review_catalog_before_media_status$;

revoke all on function
  content_factory_private.creator_content_review_catalog_pre_media_status(jsonb)
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
  organization_id_value uuid;
  project_id_value uuid;
  result_value jsonb;
  media_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);

  -- Delegate first so payload validation, organization role checks, explicit
  -- project ACL, pagination and all existing response enrichments stay exactly
  -- where they were implemented.
  result_value :=
    content_factory_private.creator_content_review_catalog_pre_media_status(
      p_payload
    );

  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value,
    project_id_value
  );

  select coalesce(
    jsonb_agg(
      item.value || jsonb_build_object(
        'status', media.status,
        'product_id', media.product_id
      )
      order by item.ordinality
    ),
    '[]'::jsonb
  )
  into media_value
  from jsonb_array_elements(
    coalesce(result_value -> 'media', '[]'::jsonb)
  ) with ordinality item(value, ordinality)
  join content_factory.media_objects media
    on media.organization_id = organization_id_value
   and media.project_id = project_id_value
   and media.id::text = item.value ->> 'id'
   and media.status = 'ready';

  return result_value || jsonb_build_object('media', media_value);
end;
$$;

revoke all on function public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_catalog(jsonb)
  to authenticated;

comment on function public.creator_content_review_catalog(jsonb) is
  'Project-scoped content-review catalog with server-authoritative media status and product identity.';

notify pgrst, 'reload schema';

commit;

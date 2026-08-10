begin;

-- The pre-project identity reader used an organization role shortcut: an
-- operator could only resolve media they personally uploaded.  Project ACL is
-- now the authority boundary, so every explicit project member must be able to
-- use a colleague's eligible source without widening access to other projects.
create or replace function public.creator_generation_media_identity(
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
  project_id_value uuid;
  requested_media_ids uuid[];
  requested_count integer;
  resolved_count integer;
  result_items jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);

  -- Preserve the original identity RPC's verified-profile and certification
  -- gates. Project membership widens which source owner is allowed; it must
  -- not turn this generation prerequisite into an onboarding bypass.
  user_id := content_factory_private.current_profile_id();

  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'project_id', 'media_ids'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'generation_media_identity_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload,
    'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id,
    project_id_value,
    user_id
  );

  if not (p_payload ? 'media_ids')
     or jsonb_typeof(p_payload -> 'media_ids') <> 'array'
     or jsonb_array_length(p_payload -> 'media_ids') not between 1 and 100
     or exists (
       select 1
       from jsonb_array_elements(p_payload -> 'media_ids') element
       where jsonb_typeof(element) <> 'string'
          or nullif(btrim(element #>> '{}'), '') is null
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_media_identity_ids_invalid';
  end if;

  begin
    select array_agg(entry.value::uuid order by entry.ordinality)
      into requested_media_ids
    from jsonb_array_elements_text(p_payload -> 'media_ids')
      with ordinality as entry(value, ordinality);
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023',
      message = 'generation_media_identity_ids_invalid';
  end;

  requested_count := cardinality(requested_media_ids);
  if (
    select count(distinct requested.media_id)
    from unnest(requested_media_ids) as requested(media_id)
  ) <> requested_count then
    raise exception using
      errcode = '22023',
      message = 'generation_media_identity_ids_invalid';
  end if;

  -- Fail closed for a mixed/cross-project list.  This also keeps the response
  -- from revealing whether an inaccessible UUID exists elsewhere.
  if exists (
    select 1
    from unnest(requested_media_ids) requested(media_id)
    where not exists (
      select 1
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.project_id = project_id_value
        and media.id = requested.media_id
        and media.status = 'ready'
        and media.artifact_class = 'source'
        and media.metadata ->> 'kind' in ('product_photo', 'packshot')
        and exists (
          select 1
          from content_factory.products product
          where product.organization_id = media.organization_id
            and product.id = media.product_id
            and product.status = 'active'
        )
    )
  ) then
    raise exception using
      errcode = '42501',
      message = 'project_media_scope_mismatch';
  end if;

  select
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', media.id,
          'public_id', media.id,
          'project_id', project_id_value,
          'product_id', product.id,
          'sku', product.sku,
          'product_name', product.title,
          'kind', media.metadata ->> 'kind',
          'rights_confirmed',
            media.metadata -> 'rights_confirmed'
              is not distinct from 'true'::jsonb,
          'identity_verified', true
        )
        order by media.created_at desc, media.id desc
      ),
      '[]'::jsonb
    ),
    count(*)::integer
    into result_items, resolved_count
  from content_factory.media_objects media
  join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
   and product.status = 'active'
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = any(requested_media_ids)
    and media.status = 'ready'
    and media.artifact_class = 'source'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot');

  -- The eligibility check and projection are separate statements. Recheck
  -- the exact cardinality so a concurrent archive/product deactivation can
  -- never degrade a verified request into a partial identity response.
  if resolved_count is distinct from requested_count then
    raise exception using
      errcode = '42501',
      message = 'project_media_scope_mismatch';
  end if;

  return jsonb_build_object(
    'items', result_items,
    'project_id', project_id_value,
    '_meta', jsonb_build_object(
      'requested_count', requested_count,
      'resolved_count', resolved_count,
      'shared_project_scope', true
    )
  );
end;
$$;

revoke all on function public.creator_generation_media_identity(jsonb)
  from public, anon;
grant execute on function public.creator_generation_media_identity(jsonb)
  to authenticated;

comment on function public.creator_generation_media_identity(jsonb) is
  'Resolves eligible source identity for explicit members of one exact project; owner identity is not an access boundary.';

notify pgrst, 'reload schema';

commit;

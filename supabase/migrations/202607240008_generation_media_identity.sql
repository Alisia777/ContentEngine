begin;

-- Keep the generation form anchored to the product already registered for the
-- selected private source image.  The browser receives only the identity of
-- media it could already see through creator_workspace_section; inaccessible
-- ids are omitted instead of leaking their existence.
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
  actor_role text;
  team_scope boolean;
  requested_media_ids uuid[];
  requested_count integer;
  resolved_count integer;
  result_items jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array['organization_id', 'media_ids'])
  ) then
    raise exception using
      errcode = '22023', message = 'generation_media_identity_payload_invalid';
  end if;

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
      errcode = '22023', message = 'generation_media_identity_ids_invalid';
  end if;

  begin
    select array_agg(entry.value::uuid order by entry.ordinality)
      into requested_media_ids
    from jsonb_array_elements_text(p_payload -> 'media_ids')
      with ordinality as entry(value, ordinality);
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023', message = 'generation_media_identity_ids_invalid';
  end;

  requested_count := cardinality(requested_media_ids);
  if (
    select count(distinct requested.media_id)
    from unnest(requested_media_ids) as requested(media_id)
  ) <> requested_count then
    raise exception using
      errcode = '22023', message = 'generation_media_identity_ids_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    null
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);

  select
    coalesce(
      jsonb_agg(
        jsonb_build_object(
          'id', media.id,
          'public_id', media.id,
          'product_id', product.id,
          'sku', product.sku,
          'product_name', product.title,
          'kind', media.metadata ->> 'kind',
          'rights_confirmed',
            media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb,
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
    and media.id = any(requested_media_ids)
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and (team_scope or media.owner_id = user_id);

  return jsonb_build_object(
    'items', result_items,
    '_meta', jsonb_build_object(
      'requested_count', requested_count,
      'resolved_count', resolved_count
    )
  );
end;
$$;

revoke all on function public.creator_generation_media_identity(jsonb)
  from public, anon;
grant execute on function public.creator_generation_media_identity(jsonb)
  to authenticated;

commit;

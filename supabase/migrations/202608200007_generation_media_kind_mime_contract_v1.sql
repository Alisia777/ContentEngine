begin;

-- 202608200007_generation_media_kind_mime_contract_v1
--
-- A Finder batch exposed that creator_register_media accepted the MIME and
-- material kind from two independent allow-lists.  That allowed a real MP4 to
-- be registered as product_photo: the upload looked "ready", but the strategy
-- candidate boundary correctly excluded it and no direct-MP4 probe could run.
-- Reject incompatible pairs before the existing registration implementation
-- can create a product or media row.  Existing rows are deliberately neither
-- rewritten nor deleted; operators can re-register the original bytes with the
-- correct kind and receive a new immutable media identity.

create or replace function public.creator_register_media(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  kind_value text := lower(btrim(coalesce(p_payload ->> 'kind', '')));
  mime_value text := lower(btrim(coalesce(p_payload ->> 'mime_type', '')));
begin
  if kind_value in (
       'product_photo', 'packshot', 'creator_reference'
     )
     and mime_value not in (
       'image/jpeg', 'image/png', 'image/webp'
     ) then
    raise exception using
      errcode = '22023',
      message = 'media_kind_mime_mismatch',
      detail = 'image_material_requires_image_mime';
  end if;

  if kind_value = 'source_video'
     and mime_value <> 'video/mp4' then
    raise exception using
      errcode = '22023',
      message = 'media_kind_mime_mismatch',
      detail = 'source_video_requires_video_mp4';
  end if;

  return content_factory_private.call_project_scoped_v47(
    'creator_register_media_pre_project_v47', p_payload,
    null, null, false
  );
end;
$$;

revoke all on function public.creator_register_media(jsonb)
  from public, anon;
grant execute on function public.creator_register_media(jsonb)
  to authenticated;

comment on function public.creator_register_media(jsonb) is
  'Registers private source media inside an accessible project. Product photos, packshots and creator references require JPEG, PNG or WebP; source videos require MP4. MIME-kind mismatch fails before product or media creation.';

do $verify_generation_media_kind_mime_contract$
declare
  definition_value text;
begin
  select lower(pg_get_functiondef(
    'public.creator_register_media(jsonb)'::regprocedure
  )) into definition_value;

  if definition_value is null
     or position(
       '''product_photo'', ''packshot'', ''creator_reference'''
       in definition_value
     ) = 0
     or position(
       '''image/jpeg'', ''image/png'', ''image/webp'''
       in definition_value
     ) = 0
     or position(
       'kind_value = ''source_video''' in definition_value
     ) = 0
     or position(
       'mime_value <> ''video/mp4''' in definition_value
     ) = 0
     or position(
       'media_kind_mime_mismatch' in definition_value
     ) = 0
     or position(
       'creator_register_media_pre_project_v47' in definition_value
     ) = 0 then
    raise exception using message =
      'generation_media_kind_mime_contract_verify_failed';
  end if;

  if not has_function_privilege(
       'authenticated',
       'public.creator_register_media(jsonb)',
       'execute'
     )
     or has_function_privilege(
       'anon',
       'public.creator_register_media(jsonb)',
       'execute'
     ) then
    raise exception using message =
      'generation_media_kind_mime_contract_grants_changed';
  end if;
end;
$verify_generation_media_kind_mime_contract$;

commit;

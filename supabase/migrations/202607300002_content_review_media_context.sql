begin;

-- The review form must inherit the exact category and platform of generated
-- media. Keep the media catalog privacy-minimized: expose only the two values
-- already required by the review workflow, not the generation prompt or job
-- payload.
alter function public.creator_content_review_catalog(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_content_review_catalog(jsonb)
  rename to creator_content_review_catalog_without_media_context;

revoke all on function
  content_factory_private
    .creator_content_review_catalog_without_media_context(jsonb)
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
#variable_conflict use_variable
declare
  organization_id uuid;
  catalog_value jsonb;
  media_value jsonb;
begin
  catalog_value :=
    content_factory_private
      .creator_content_review_catalog_without_media_context(p_payload);
  organization_id :=
    content_factory_private.resolve_organization(p_payload);

  select coalesce(
    jsonb_agg(
      item.value || jsonb_build_object(
        'product_category',
          case
            when lower(btrim(coalesce(
              nullif(btrim(
                product.metadata ->> 'content_review_category'
              ), ''),
              nullif(btrim(
                product.metadata ->> 'product_category'
              ), ''),
              ''
            ))) in (
              'cosmetics', 'baa', 'sports_food', 'food', 'household',
              'apparel', 'electronics', 'other'
            )
            then lower(btrim(coalesce(
              nullif(btrim(
                product.metadata ->> 'content_review_category'
              ), ''),
              nullif(btrim(
                product.metadata ->> 'product_category'
              ), '')
            )))
            else null
          end,
        'platform',
          case
            when lower(btrim(coalesce(
              generation.input ->> 'platform',
              ''
            ))) in (
              'instagram', 'youtube', 'vk', 'tiktok', 'telegram',
              'wildberries', 'other'
            )
            then lower(btrim(generation.input ->> 'platform'))
            else null
          end
      )
      order by item.ordinality
    ),
    '[]'::jsonb
  )
  into media_value
  from jsonb_array_elements(
    catalog_value -> 'media'
  ) with ordinality item(value, ordinality)
  join content_factory.media_objects media
    on media.organization_id = organization_id
   and media.id::text = item.value ->> 'id'
  left join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
  left join content_factory.generation_jobs generation
    on generation.organization_id = media.organization_id
   and generation.id::text = media.metadata ->> 'generation_job_id';

  return jsonb_set(
    catalog_value,
    '{media}',
    media_value,
    false
  );
end;
$$;

revoke all on function
  public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function
  public.creator_content_review_catalog(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

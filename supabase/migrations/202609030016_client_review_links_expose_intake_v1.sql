begin;
-- 202609030016_client_review_links_expose_intake_v1
--
-- Пульт ссылок должен видеть, включён ли клиентский ввод на каждой ссылке
-- (тумблер ступени 2). Re-emit листинга с ключом intake_enabled.

create or replace function public.creator_list_client_review_links(
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
  campaign_id_value uuid;
  links_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  campaign_id_value := content_factory_private.require_uuid(
    p_payload, 'campaign_id'
  );

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', link.id,
    'client_label', link.client_label,
    'status', case
      when link.status = 'active' and link.expires_at <= now()
      then 'expired' else link.status
    end,
    'expires_at', link.expires_at,
    'view_count', link.view_count,
    'intake_enabled', link.intake_enabled,
    'view_limit', link.view_limit,
    'decision_count', link.decision_count,
    'last_viewed_at', link.last_viewed_at,
    'created_at', link.created_at,
    'items', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'media_object_id', item.media_object_id,
        'position', item.position,
        'curator_attested', item.curator_attested,
        'last_decision', (
          select jsonb_build_object(
            'decision', decision.decision,
            'comment', decision.comment,
            'created_at', decision.created_at
          )
          from content_factory.client_review_decisions decision
          where decision.item_id = item.id
          order by decision.created_at desc
          limit 1
        )
      ) order by item.position), '[]'::jsonb)
      from content_factory.client_review_link_items item
      where item.link_id = link.id
    )
  ) order by link.created_at desc), '[]'::jsonb)
  into links_value
  from content_factory.client_review_links link
  where link.organization_id = organization_id
    and link.campaign_id = campaign_id_value;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-links-v1',
    'links', links_value
  );
end;
$$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
begin
  if position('intake_enabled' in pg_get_functiondef(
       'public.creator_list_client_review_links(jsonb)'::regprocedure
     )) = 0 then
    raise exception using message = 'client_review_links_intake_key_missing';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

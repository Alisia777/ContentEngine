begin;
-- 202609030012_client_review_list_rpcs_volatile_v1
--
-- Хотфикс 202609030009: обе читалки витрины были объявлены STABLE, а
-- PostgREST исполняет stable-RPC в READ-ONLY транзакции — внутри же
-- канона current_profile_id/resolve_organization/membership_role есть
-- запись, и вызов падал 25006 «cannot execute INSERT in a read-only
-- transaction» (снаружи — 405). Поэтому весь канон creator_* в проекте
-- volatile; читалки пере-эмитятся с той же семантикой тела. Урок 0011
-- закреплён: verify ВЫЗЫВАЕТ функцию по-настоящему под эмулированным JWT.

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

create or replace function public.creator_list_campaign_review_candidates(
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
  candidates_value jsonb;
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

  -- Ролики кампании: media несёт generation_job_id наряда этой кампании
  -- (в проде 35 из 38 готовых роликов несут этот ключ).
  select coalesce(jsonb_agg(jsonb_build_object(
    'media_object_id', media.id,
    'kind', media.metadata ->> 'kind',
    'original_filename', media.metadata ->> 'original_filename',
    'duration_seconds', media.metadata ->> 'duration_seconds',
    'created_at', media.created_at,
    'qa_status', case when exists (
      select 1
      from content_factory.content_review_runs runs
      join content_factory.content_review_decisions decisions
        on decisions.review_id = runs.id
      where runs.organization_id = organization_id
        and runs.media_object_id = media.id
        and decisions.decision = 'approved'
    ) then 'approved' else 'none' end
  ) order by media.created_at desc), '[]'::jsonb)
  into candidates_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.status = 'ready'
    and coalesce(media.metadata ->> 'kind', '')
      in ('generated_video', 'finalized_video')
    and exists (
      select 1
      from content_factory.generation_jobs job
      where job.organization_id = organization_id
        and job.campaign_id = campaign_id_value
        and job.id::text = media.metadata ->> 'generation_job_id'
    );

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-links-v1',
    'candidates', candidates_value
  );
end;
$$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ: настоящий вызов под JWT владельца.
do $verify$
declare
  claims_value text;
  owner_id uuid;
  organization_value uuid;
  campaign_value uuid;
  links_value jsonb;
  candidates_value jsonb;
begin
  select membership.profile_id, membership.organization_id
  into owner_id, organization_value
  from content_factory.memberships membership
  where membership.role = 'owner' and membership.status = 'active'
  order by membership.created_at
  limit 1;
  select campaign.id into campaign_value
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = organization_value
    and campaign.status = 'active'
  order by campaign.created_at
  limit 1;
  if owner_id is null or campaign_value is null then
    raise exception using message = 'client_review_list_fix_no_fixture';
  end if;
  claims_value := current_setting('request.jwt.claims', true);
  perform set_config(
    'request.jwt.claims',
    json_build_object('sub', owner_id, 'role', 'authenticated')::text,
    true
  );
  links_value := public.creator_list_client_review_links(
    jsonb_build_object(
      'organization_id', organization_value,
      'campaign_id', campaign_value
    )
  );
  candidates_value := public.creator_list_campaign_review_candidates(
    jsonb_build_object(
      'organization_id', organization_value,
      'campaign_id', campaign_value
    )
  );
  perform set_config(
    'request.jwt.claims', coalesce(claims_value, ''), true
  );
  if links_value ->> 'ok' is distinct from 'true'
     or candidates_value ->> 'ok' is distinct from 'true' then
    raise exception using message = 'client_review_list_fix_broken';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

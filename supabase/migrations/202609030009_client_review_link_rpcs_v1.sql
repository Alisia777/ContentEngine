begin;
-- 202609030009_client_review_link_rpcs_v1
--
-- Операторская сторона витрины: выдать токен-ссылку клиенту, отозвать,
-- перечислить ссылки кампании, показать кандидатов (ролики кампании с
-- QA-статусом). Канон creator_*: current_profile_id → resolve_organization
-- → membership_role. Токен генерируется В БАЗЕ и возвращается наружу РОВНО
-- один раз; в строке остаётся только sha256. Повтор по idempotency_key
-- возвращает replayed:true БЕЗ токена — восстановить нельзя, только
-- отозвать и выдать новую ссылку. QA-гейт выдачи: ролик либо несёт
-- approved-решение контура проверки, либо оператор явно берёт кураторскую
-- ответственность (curator_attested) — в проде пока 0 approved-решений, и
-- строгий гейт означал бы пустую витрину (решение мастер-плана).

create or replace function public.creator_issue_client_review_link(
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
  user_id uuid;
  organization_id uuid;
  campaign_row content_factory.generation_campaigns%rowtype;
  label_value text;
  idempotency_value text;
  ttl_days integer;
  curator_attested boolean;
  media_ids uuid[];
  media_id uuid;
  media_row content_factory.media_objects%rowtype;
  has_approved boolean;
  token_value text;
  token_hash_value text;
  link_row content_factory.client_review_links%rowtype;
  item_position integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );

  label_value := content_factory_private.require_text(
    p_payload, 'client_label', 2, 120
  );
  idempotency_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  ttl_days := coalesce(nullif(p_payload ->> 'ttl_days', '')::integer, 14);
  if ttl_days not between 1 and 90 then
    raise exception using errcode = '22023',
      message = 'client_review_ttl_invalid';
  end if;
  curator_attested := coalesce(
    (p_payload ->> 'curator_attested')::boolean, false
  );

  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = organization_id
    and campaign.id = content_factory_private.require_uuid(
      p_payload, 'campaign_id'
    )
    and campaign.status = 'active';
  if campaign_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'client_review_campaign_not_found';
  end if;

  -- Повтор по idempotency_key: ссылка уже есть — токен не возвращается.
  select link.* into link_row
  from content_factory.client_review_links link
  where link.organization_id = organization_id
    and link.idempotency_key = idempotency_value;
  if link_row.id is not null then
    return jsonb_build_object(
      'ok', true,
      'version', 'client-review-links-v1',
      'replayed', true,
      'link', jsonb_build_object(
        'id', link_row.id,
        'status', link_row.status,
        'expires_at', link_row.expires_at
      )
    );
  end if;

  if jsonb_typeof(p_payload -> 'media_ids') <> 'array'
     or jsonb_array_length(p_payload -> 'media_ids') not between 1 and 50 then
    raise exception using errcode = '22023',
      message = 'client_review_media_ids_invalid';
  end if;
  begin
    select array_agg(value::uuid)
    into media_ids
    from jsonb_array_elements_text(p_payload -> 'media_ids');
  exception when invalid_text_representation then
    raise exception using errcode = '22023',
      message = 'client_review_media_ids_invalid';
  end;

  token_value := 'crv1_' || replace(translate(
    encode(extensions.gen_random_bytes(32), 'base64'), '+/', '-_'
  ), '=', '');
  token_hash_value := encode(
    extensions.digest(token_value, 'sha256'), 'hex'
  );

  insert into content_factory.client_review_links (
    organization_id, campaign_id, created_by, client_label, token_hash,
    expires_at, idempotency_key
  ) values (
    organization_id, campaign_row.id, user_id, btrim(label_value),
    token_hash_value, now() + make_interval(days => ttl_days),
    idempotency_value
  )
  returning * into link_row;

  foreach media_id in array media_ids loop
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.id = media_id
      and media.status = 'ready';
    if media_row.id is null
       or coalesce(media_row.metadata ->> 'kind', '')
         not in ('generated_video', 'finalized_video') then
      raise exception using errcode = '22023',
        message = 'client_review_media_not_reviewable';
    end if;
    select exists (
      select 1
      from content_factory.content_review_runs runs
      join content_factory.content_review_decisions decisions
        on decisions.review_id = runs.id
      where runs.organization_id = organization_id
        and runs.media_object_id = media_row.id
        and decisions.decision = 'approved'
    ) into has_approved;
    if not has_approved and not curator_attested then
      raise exception using errcode = '22023',
        message = 'client_review_media_not_accepted';
    end if;
    item_position := item_position + 1;
    insert into content_factory.client_review_link_items (
      link_id, organization_id, media_object_id, position, curator_attested
    ) values (
      link_row.id, organization_id, media_row.id, item_position,
      not has_approved
    );
  end loop;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-links-v1',
    'replayed', false,
    'link', jsonb_build_object(
      'id', link_row.id,
      'status', link_row.status,
      'expires_at', link_row.expires_at,
      'token', token_value,
      'url_fragment', '#t=' || token_value,
      'items', item_position
    )
  );
end;
$$;

create or replace function public.creator_revoke_client_review_link(
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
  user_id uuid;
  organization_id uuid;
  link_row content_factory.client_review_links%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );

  update content_factory.client_review_links link
  set status = 'revoked',
      revoked_at = coalesce(link.revoked_at, now()),
      revoked_by = coalesce(link.revoked_by, user_id),
      updated_at = now()
  where link.organization_id = organization_id
    and link.id = content_factory_private.require_uuid(p_payload, 'link_id')
  returning * into link_row;
  if link_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'client_review_link_not_found';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-links-v1',
    'link', jsonb_build_object(
      'id', link_row.id, 'status', link_row.status
    )
  );
end;
$$;

create or replace function public.creator_list_client_review_links(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
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
stable
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

do $grants$
declare
  fn_name text;
begin
  for fn_name in
    select unnest(array[
      'creator_issue_client_review_link',
      'creator_revoke_client_review_link',
      'creator_list_client_review_links',
      'creator_list_campaign_review_candidates'
    ])
  loop
    execute format(
      'revoke all on function public.%I(jsonb) '
        || 'from public, anon, service_role', fn_name
    );
    execute format(
      'grant execute on function public.%I(jsonb) to authenticated', fn_name
    );
  end loop;
end;
$grants$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  fn_name text;
  definition_value text;
begin
  for fn_name in
    select unnest(array[
      'creator_issue_client_review_link',
      'creator_revoke_client_review_link',
      'creator_list_client_review_links',
      'creator_list_campaign_review_candidates'
    ])
  loop
    if has_function_privilege(
         'anon', format('public.%I(jsonb)', fn_name), 'execute'
       ) then
      raise exception using message = 'client_review_anon_leak_' || fn_name;
    end if;
    if not has_function_privilege(
         'authenticated', format('public.%I(jsonb)', fn_name), 'execute'
       ) then
      raise exception using message =
        'client_review_authenticated_missing_' || fn_name;
    end if;
  end loop;
  definition_value := pg_get_functiondef(
    'public.creator_issue_client_review_link(jsonb)'::regprocedure
  );
  if position('gen_random_bytes(32)' in definition_value) = 0
     or position('crv1_' in definition_value) = 0
     or position('client_review_media_not_accepted'
       in definition_value) = 0 then
    raise exception using message = 'client_review_issue_contract_broken';
  end if;
end;
$verify$;

commit;

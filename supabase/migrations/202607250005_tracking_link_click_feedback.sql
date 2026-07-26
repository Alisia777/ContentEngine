begin;

-- A placement already had a tracking_url column, but the browser-only
-- production path never created or measured one.  Add a first-party redirect
-- receipt that counts privacy-minimized human clicks without platform OAuth.
-- Raw IP addresses, full referrers and raw user agents are never persisted.
create table if not exists content_factory.tracking_clicks (
  id bigint generated always as identity primary key,
  organization_id uuid not null,
  placement_id uuid not null,
  clicked_at timestamptz not null default clock_timestamp(),
  classification text not null
    check (classification in ('human', 'bot', 'unknown')),
  accepted_for_human_kpi boolean not null,
  user_agent_hash text check (
    user_agent_hash is null or user_agent_hash ~ '^[0-9a-f]{64}$'
  ),
  visitor_fingerprint text check (
    visitor_fingerprint is null
    or visitor_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  referrer_origin text check (
    referrer_origin is null
    or (
      length(referrer_origin) between 8 and 500
      and referrer_origin ~ '^https?://[^/[:space:]@]+$'
    )
  ),
  metadata jsonb not null default '{}'::jsonb check (
    jsonb_typeof(metadata) = 'object'
    and length(metadata::text) <= 4096
  ),
  foreign key (organization_id, placement_id)
    references content_factory.placements(organization_id, id)
    on delete cascade
);

create index if not exists tracking_clicks_placement_time_idx
  on content_factory.tracking_clicks (
    organization_id, placement_id, clicked_at desc, id desc
  );
create index if not exists tracking_clicks_dedupe_idx
  on content_factory.tracking_clicks (
    placement_id, visitor_fingerprint, clicked_at desc
  ) where visitor_fingerprint is not null;

-- Slugs are public capabilities and therefore globally unique, random and
-- unguessable.  The redirect target remains organization-scoped metadata.
create unique index if not exists placements_tracking_slug_uq
  on content_factory.placements ((metadata ->> 'tracking_slug'))
  where nullif(metadata ->> 'tracking_slug', '') is not null;

alter table content_factory.tracking_clicks enable row level security;
revoke all on content_factory.tracking_clicks
  from public, anon, authenticated;
grant all on content_factory.tracking_clicks to service_role;

create or replace function public.creator_configure_tracking_link(
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
  actor_role text;
  placement_id_value uuid;
  target_url_value text;
  idempotency_key_value text;
  placement_row content_factory.placements%rowtype;
  existing_slug_value text;
  existing_target_value text;
  slug_value text;
  request_payload jsonb;
  replay jsonb;
  result_value jsonb;
  attempt integer;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'placement_id', 'target_url', 'idempotency_key'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'tracking_link_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  placement_id_value :=
    content_factory_private.require_uuid(p_payload, 'placement_id');
  target_url_value :=
    content_factory_private.require_text(p_payload, 'target_url', 12, 2000);
  idempotency_key_value := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  if target_url_value !~ '^https://[^[:space:]]+$'
     or target_url_value ~ '^https://[^/]*@'
     or target_url_value ~* '/functions/v1/creator-click([?/#]|$)' then
    raise exception using
      errcode = '22023',
      message = 'tracking_target_invalid';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_configure_tracking_link',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  select placement.* into placement_row
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.id = placement_id_value
  for update;
  if placement_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'tracking_placement_not_found';
  end if;
  if placement_row.assigned_to <> user_id
     and actor_role <> all(array['owner', 'admin', 'producer', 'reviewer']) then
    raise exception using
      errcode = '42501',
      message = 'tracking_link_access_denied';
  end if;
  if placement_row.status not in ('scheduled', 'ready', 'published') then
    raise exception using
      errcode = '55000',
      message = 'tracking_placement_not_configurable';
  end if;

  existing_slug_value :=
    nullif(placement_row.metadata ->> 'tracking_slug', '');
  existing_target_value :=
    nullif(placement_row.metadata ->> 'tracking_target_url', '');
  if existing_slug_value is not null then
    if existing_target_value is distinct from target_url_value then
      raise exception using
        errcode = '55000',
        message = 'tracking_link_target_immutable';
    end if;
    result_value := jsonb_build_object(
      'ok', true,
      'created', false,
      'placement_id', placement_row.id,
      'tracking_slug', existing_slug_value,
      'target_url', existing_target_value,
      'human_clicks', (
        select count(*)::bigint
        from content_factory.tracking_clicks click
        where click.organization_id = placement_row.organization_id
          and click.placement_id = placement_row.id
          and click.accepted_for_human_kpi
      )
    );
    return content_factory_private.finish_command(
      organization_id,
      user_id,
      'creator_configure_tracking_link',
      idempotency_key_value,
      request_payload,
      result_value
    );
  end if;

  for attempt in 1..12 loop
    slug_value := 'ce1_' || encode(extensions.gen_random_bytes(12), 'hex');
    exit when not exists (
      select 1
      from content_factory.placements placement
      where placement.metadata ->> 'tracking_slug' = slug_value
    );
    slug_value := null;
  end loop;
  if slug_value is null then
    raise exception using
      errcode = '55000',
      message = 'tracking_slug_generation_failed';
  end if;

  update content_factory.placements placement
  set metadata = coalesce(placement.metadata, '{}'::jsonb)
        || jsonb_build_object(
          'tracking_slug', slug_value,
          'tracking_target_url', target_url_value,
          'tracking_version', 'tracking-v1',
          'tracking_created_by', user_id,
          'tracking_created_at', now()
        ),
      updated_at = now()
  where placement.organization_id = organization_id
    and placement.id = placement_row.id
  returning * into placement_row;

  result_value := jsonb_build_object(
    'ok', true,
    'created', true,
    'placement_id', placement_row.id,
    'tracking_slug', slug_value,
    'target_url', target_url_value,
    'human_clicks', 0
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'tracking_link_configured',
    'placement',
    placement_row.id::text,
    jsonb_build_object(
      'platform', placement_row.platform,
      'tracking_version', 'tracking-v1'
    ),
    'tracking-link:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_configure_tracking_link',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_configure_tracking_link(jsonb)
  from public, anon;
grant execute on function public.creator_configure_tracking_link(jsonb)
  to authenticated;

-- Called only by the public redirect Edge Function with its service-role
-- client.  It always returns the already resolved target, even when bounded
-- telemetry is skipped, duplicated or rate limited.
create or replace function public.system_record_public_tracking_click(
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
  slug_value text;
  user_agent_value text;
  user_agent_normalized text;
  accept_language_value text;
  visitor_token_value text;
  referrer_origin_value text;
  placement_row content_factory.placements%rowtype;
  classification_value text;
  bot_reason_value text;
  user_agent_hash_value text;
  visitor_fingerprint_value text;
  recent_count integer;
  duplicate_id bigint;
  click_id_value bigint;
  now_value timestamptz := clock_timestamp();
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'slug', 'user_agent', 'accept_language', 'visitor_token',
      'referrer_origin'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'tracking_click_payload_invalid';
  end if;

  slug_value :=
    content_factory_private.require_text(p_payload, 'slug', 12, 80);
  if slug_value !~ '^ce1_[0-9a-f]{24}$' then
    raise exception using
      errcode = '22023',
      message = 'tracking_slug_invalid';
  end if;
  user_agent_value := btrim(coalesce(p_payload ->> 'user_agent', ''));
  accept_language_value :=
    btrim(coalesce(p_payload ->> 'accept_language', ''));
  visitor_token_value :=
    btrim(coalesce(p_payload ->> 'visitor_token', ''));
  referrer_origin_value :=
    btrim(coalesce(p_payload ->> 'referrer_origin', ''));
  if length(user_agent_value) > 1000
     or length(accept_language_value) > 200
     or length(visitor_token_value) > 128
     or length(referrer_origin_value) > 500 then
    raise exception using
      errcode = '22023',
      message = 'tracking_click_payload_invalid';
  end if;
  if visitor_token_value <> ''
     and visitor_token_value !~ '^[A-Za-z0-9_-]{16,128}$' then
    visitor_token_value := '';
  end if;
  if referrer_origin_value <> ''
     and (
       referrer_origin_value !~ '^https?://[^/[:space:]@]+$'
       or referrer_origin_value ~ '^https?://[^/]*@'
     ) then
    referrer_origin_value := '';
  end if;

  select placement.* into placement_row
  from content_factory.placements placement
  where placement.metadata ->> 'tracking_slug' = slug_value
    and placement.metadata ->> 'tracking_target_url'
      ~ '^https://[^[:space:]]+$'
    and placement.status in ('scheduled', 'ready', 'published')
  for update;
  if placement_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'tracking_link_not_found';
  end if;

  user_agent_normalized := lower(
    regexp_replace(user_agent_value, '[[:space:]]+', ' ', 'g')
  );
  if user_agent_normalized = '' then
    classification_value := 'unknown';
    bot_reason_value := 'missing_user_agent';
  elsif exists (
    select 1
    from unnest(array[
      'facebookexternalhit', 'facebot', 'twitterbot', 'telegrambot',
      'linkedinbot', 'pinterestbot', 'discordbot', 'slackbot',
      'vkshare', 'whatsapp'
    ]) marker
    where position(marker in user_agent_normalized) > 0
  ) then
    classification_value := 'bot';
    bot_reason_value := 'social_preview';
  elsif exists (
    select 1
    from unnest(array[
      'bot/', 'googlebot', 'bingbot', 'yandexbot', 'duckduckbot',
      'baiduspider', 'crawler', 'spider', 'slurp'
    ]) marker
    where position(marker in user_agent_normalized) > 0
  ) then
    classification_value := 'bot';
    bot_reason_value := 'crawler';
  elsif exists (
    select 1
    from unnest(array[
      'curl/', 'wget/', 'python-requests', 'python-httpx', 'aiohttp',
      'go-http-client', 'headlesschrome', 'phantomjs'
    ]) marker
    where position(marker in user_agent_normalized) > 0
  ) then
    classification_value := 'bot';
    bot_reason_value := 'automation';
  else
    classification_value := 'human';
    bot_reason_value := null;
  end if;

  if user_agent_normalized <> '' then
    user_agent_hash_value := encode(
      extensions.digest(
        convert_to(user_agent_normalized, 'UTF8'),
        'sha256'
      ),
      'hex'
    );
  end if;
  if visitor_token_value <> '' then
    visitor_fingerprint_value := encode(
      extensions.digest(
        convert_to('visitor-token' || chr(31) || visitor_token_value, 'UTF8'),
        'sha256'
      ),
      'hex'
    );
  elsif user_agent_normalized <> '' then
    visitor_fingerprint_value := encode(
      extensions.digest(
        convert_to(
          user_agent_normalized || chr(31)
          || lower(accept_language_value) || chr(31)
          || lower(referrer_origin_value),
          'UTF8'
        ),
        'sha256'
      ),
      'hex'
    );
  end if;

  if visitor_fingerprint_value is not null then
    select click.id into duplicate_id
    from content_factory.tracking_clicks click
    where click.organization_id = placement_row.organization_id
      and click.placement_id = placement_row.id
      and click.visitor_fingerprint = visitor_fingerprint_value
      and click.clicked_at >= now_value - interval '10 seconds'
    order by click.clicked_at desc, click.id desc
    limit 1;
  end if;
  if duplicate_id is not null then
    return jsonb_build_object(
      'ok', true,
      'target_url', placement_row.metadata ->> 'tracking_target_url',
      'disposition', 'duplicate',
      'classification', classification_value,
      'accepted_for_human_kpi', false
    );
  end if;

  select count(*)::integer into recent_count
  from content_factory.tracking_clicks click
  where click.organization_id = placement_row.organization_id
    and click.placement_id = placement_row.id
    and click.clicked_at >= now_value - interval '1 minute';
  if recent_count >= 120 then
    return jsonb_build_object(
      'ok', true,
      'target_url', placement_row.metadata ->> 'tracking_target_url',
      'disposition', 'rate_limited',
      'classification', classification_value,
      'accepted_for_human_kpi', false
    );
  end if;

  insert into content_factory.tracking_clicks (
    organization_id, placement_id, clicked_at, classification,
    accepted_for_human_kpi, user_agent_hash, visitor_fingerprint,
    referrer_origin, metadata
  ) values (
    placement_row.organization_id,
    placement_row.id,
    now_value,
    classification_value,
    classification_value = 'human',
    user_agent_hash_value,
    visitor_fingerprint_value,
    nullif(referrer_origin_value, ''),
    jsonb_build_object(
      'schema_version', 1,
      'source', 'creator-click',
      'bot_reason', bot_reason_value
    )
  )
  returning id into click_id_value;

  return jsonb_build_object(
    'ok', true,
    'target_url', placement_row.metadata ->> 'tracking_target_url',
    'disposition', 'recorded',
    'classification', classification_value,
    'accepted_for_human_kpi', classification_value = 'human',
    'click_id', click_id_value
  );
end;
$$;

revoke all on function public.system_record_public_tracking_click(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_record_public_tracking_click(jsonb)
  to service_role;

-- Enrich the existing paginated workspace response without replacing its
-- audited authorization, filtering or cursor logic.
alter function public.creator_workspace_section(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_workspace_section(jsonb)
  rename to creator_workspace_section_tracking_v1;
revoke all on function
  content_factory_private.creator_workspace_section_tracking_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_workspace_section(
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
  result_value jsonb;
  requested_section text;
  organization_id uuid;
  enriched_items jsonb;
  enriched_summary jsonb;
begin
  result_value :=
    content_factory_private.creator_workspace_section_tracking_v1(p_payload);
  requested_section := lower(btrim(coalesce(p_payload ->> 'section', '')));
  if requested_section not in ('placement', 'stats') then
    return result_value;
  end if;
  organization_id :=
    content_factory_private.resolve_organization(p_payload);

  if requested_section = 'placement' then
    select coalesce(
      jsonb_agg(
        item.value || jsonb_build_object(
          'tracking_slug', placement.metadata ->> 'tracking_slug',
          'tracking_target_url',
            placement.metadata ->> 'tracking_target_url',
          'tracked_clicks', coalesce(clicks.human_clicks, 0)
        )
        order by item.ordinality
      ),
      '[]'::jsonb
    )
    into enriched_items
    from jsonb_array_elements(
      coalesce(result_value -> 'placements', '[]'::jsonb)
    ) with ordinality item(value, ordinality)
    join content_factory.placements placement
      on placement.organization_id = organization_id
     and placement.id = (item.value ->> 'id')::uuid
    left join lateral (
      select count(*)::bigint as human_clicks
      from content_factory.tracking_clicks click
      where click.organization_id = placement.organization_id
        and click.placement_id = placement.id
        and click.accepted_for_human_kpi
    ) clicks on true;
    return result_value || jsonb_build_object(
      'placements', enriched_items
    );
  end if;

  with tracked as (
    select
      item.ordinality,
      item.value,
      coalesce(clicks.human_clicks, 0) as human_clicks,
      coalesce((item.value ->> 'clicks')::bigint, 0) as supplied_clicks
    from jsonb_array_elements(
      coalesce(result_value -> 'publications', '[]'::jsonb)
    ) with ordinality item(value, ordinality)
    join content_factory.placements placement
      on placement.organization_id = organization_id
     and placement.id = (item.value ->> 'id')::uuid
    left join lateral (
      select count(*)::bigint as human_clicks
      from content_factory.tracking_clicks click
      where click.organization_id = placement.organization_id
        and click.placement_id = placement.id
        and click.accepted_for_human_kpi
    ) clicks on true
  ),
  enriched as (
    select
      tracked.ordinality,
      tracked.value || jsonb_build_object(
        'tracked_clicks', tracked.human_clicks,
        'clicks', greatest(
          tracked.supplied_clicks,
          tracked.human_clicks
        ),
        'source', case
          when tracked.human_clicks > tracked.supplied_clicks
               and nullif(tracked.value ->> 'source', '') is not null
            then 'mixed'
          when tracked.human_clicks > tracked.supplied_clicks
            then 'tracking_link'
          else tracked.value ->> 'source'
        end
      ) as value
    from tracked
  )
  select coalesce(
    jsonb_agg(value order by ordinality),
    '[]'::jsonb
  )
  into enriched_items
  from enriched;

  select jsonb_build_object(
    'published', count(*) filter (
      where item.value ->> 'status' = 'published'
    ),
    'views', coalesce(sum(
      (item.value ->> 'views')::bigint
    ), 0),
    'clicks', coalesce(sum(
      (item.value ->> 'clicks')::bigint
    ), 0),
    'orders', coalesce(sum(
      (item.value ->> 'orders')::bigint
    ), 0),
    'revenue_minor', coalesce(sum(
      (item.value ->> 'revenue_minor')::bigint
    ), 0),
    'ctr', case
      when coalesce(sum((item.value ->> 'views')::bigint), 0) > 0
        then round(
          coalesce(sum((item.value ->> 'clicks')::bigint), 0)::numeric
          * 100
          / sum((item.value ->> 'views')::bigint),
          2
        )
      else 0
    end
  )
  into enriched_summary
  from jsonb_array_elements(enriched_items) item(value);

  select coalesce(
    jsonb_agg(
      item.value || jsonb_build_object(
        'tracking_slug', placement.metadata ->> 'tracking_slug',
        'tracked_clicks', coalesce(clicks.human_clicks, 0)
      )
      order by item.ordinality
    ),
    '[]'::jsonb
  )
  into enriched_items
  from jsonb_array_elements(
    coalesce(result_value -> 'publication_options', '[]'::jsonb)
  ) with ordinality item(value, ordinality)
  join content_factory.placements placement
    on placement.organization_id = organization_id
   and placement.id = (item.value ->> 'id')::uuid
  left join lateral (
    select count(*)::bigint as human_clicks
    from content_factory.tracking_clicks click
    where click.organization_id = placement.organization_id
      and click.placement_id = placement.id
      and click.accepted_for_human_kpi
  ) clicks on true;

  return result_value || jsonb_build_object(
    'summary', enriched_summary,
    'publications', (
      with tracked as (
        select
          item.ordinality,
          item.value,
          coalesce(clicks.human_clicks, 0) as human_clicks,
          coalesce((item.value ->> 'clicks')::bigint, 0)
            as supplied_clicks
        from jsonb_array_elements(
          coalesce(result_value -> 'publications', '[]'::jsonb)
        ) with ordinality item(value, ordinality)
        join content_factory.placements placement
          on placement.organization_id = organization_id
         and placement.id = (item.value ->> 'id')::uuid
        left join lateral (
          select count(*)::bigint as human_clicks
          from content_factory.tracking_clicks click
          where click.organization_id = placement.organization_id
            and click.placement_id = placement.id
            and click.accepted_for_human_kpi
        ) clicks on true
      )
      select coalesce(
        jsonb_agg(
          tracked.value || jsonb_build_object(
            'tracked_clicks', tracked.human_clicks,
            'clicks', greatest(
              tracked.supplied_clicks,
              tracked.human_clicks
            ),
            'source', case
              when tracked.human_clicks > tracked.supplied_clicks
                   and nullif(tracked.value ->> 'source', '') is not null
                then 'mixed'
              when tracked.human_clicks > tracked.supplied_clicks
                then 'tracking_link'
              else tracked.value ->> 'source'
            end
          )
          order by tracked.ordinality
        ),
        '[]'::jsonb
      )
      from tracked
    ),
    'publication_options', enriched_items
  );
end;
$$;

revoke all on function public.creator_workspace_section(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_section(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

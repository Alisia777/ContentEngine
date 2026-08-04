begin;

-- Approved structural research is the only input to this velocity ledger.
-- YouTube API metadata, counters, titles and raw provider text are deliberately
-- excluded.  The number measures evidence support inside two human-approved
-- snapshots; it is not platform popularity, sales lift or a causal winner.

create table content_factory.research_watchlist_trend_velocity_events (
  organization_id uuid not null,
  snapshot_id uuid not null,
  previous_snapshot_id uuid,
  run_id uuid not null,
  product_id uuid not null,
  watchlist_id uuid not null,
  binding_id uuid,
  market_category_id uuid,
  signal_key text not null,
  definition_version text not null check (
    definition_version = 'approved-structural-support-velocity-v1'
  ),
  comparison_mode text not null check (comparison_mode in (
    'baseline', 'comparable', 'category_reset', 'signal_new',
    'signal_removed', 'interval_too_short'
  )),
  current_present boolean not null,
  previous_present boolean not null,
  current_direction text check (
    current_direction in ('emerging', 'growing', 'stable', 'declining', 'unclear')
  ),
  previous_direction text check (
    previous_direction in ('emerging', 'growing', 'stable', 'declining', 'unclear')
  ),
  current_confidence text check (current_confidence in ('low', 'medium', 'high')),
  previous_confidence text check (previous_confidence in ('low', 'medium', 'high')),
  current_source_count integer not null check (current_source_count between 0 and 100),
  previous_source_count integer not null check (previous_source_count between 0 and 100),
  current_total_source_count integer not null check (
    current_total_source_count between 1 and 100
  ),
  previous_total_source_count integer check (
    previous_total_source_count between 1 and 100
  ),
  current_support_bps integer not null check (current_support_bps between 0 and 10000),
  previous_support_bps integer check (previous_support_bps between 0 and 10000),
  support_delta_bps integer check (support_delta_bps between -10000 and 10000),
  elapsed_seconds bigint check (elapsed_seconds >= 0),
  support_velocity_bps_per_30d numeric(14, 2),
  current_evidence_hash text check (
    current_evidence_hash is null or current_evidence_hash ~ '^[0-9a-f]{64}$'
  ),
  previous_evidence_hash text check (
    previous_evidence_hash is null or previous_evidence_hash ~ '^[0-9a-f]{64}$'
  ),
  current_source_ids_hash text check (
    current_source_ids_hash is null or current_source_ids_hash ~ '^[0-9a-f]{64}$'
  ),
  previous_source_ids_hash text check (
    previous_source_ids_hash is null or previous_source_ids_hash ~ '^[0-9a-f]{64}$'
  ),
  lineage_hash text not null check (lineage_hash ~ '^[0-9a-f]{64}$'),
  event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null,
  previous_observed_at timestamptz,
  captured_at timestamptz not null default now(),
  primary key (organization_id, snapshot_id, signal_key),
  constraint research_trend_velocity_org_event_hash_uq
    unique (organization_id, event_hash),
  foreign key (organization_id, snapshot_id, run_id)
    references content_factory.research_watchlist_snapshots(
      organization_id, id, run_id
    ),
  foreign key (organization_id, watchlist_id, snapshot_id)
    references content_factory.research_watchlist_snapshots(
      organization_id, watchlist_id, id
    ),
  foreign key (organization_id, previous_snapshot_id)
    references content_factory.research_watchlist_snapshots(
      organization_id, id
    ),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, product_id, binding_id, market_category_id)
    references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id
    ),
  foreign key (signal_key)
    references content_factory.research_structural_trend_signal_types(signal_key),
  check ((binding_id is null) = (market_category_id is null)),
  check (current_present = (current_direction is not null)),
  check (current_present = (current_confidence is not null)),
  check (current_present = (current_evidence_hash is not null)),
  check (current_present = (current_source_ids_hash is not null)),
  check (current_present = (current_source_count > 0)),
  check (previous_present = (previous_direction is not null)),
  check (previous_present = (previous_confidence is not null)),
  check (previous_present = (previous_evidence_hash is not null)),
  check (previous_present = (previous_source_ids_hash is not null)),
  check (previous_present = (previous_source_count > 0)),
  check (current_present or previous_present),
  check (
    current_support_bps = round(
      10000.0 * current_source_count / current_total_source_count
    )::integer
  ),
  check ((previous_snapshot_id is null) = (previous_observed_at is null)),
  check ((previous_snapshot_id is null) = (previous_total_source_count is null)),
  check (
    (previous_snapshot_id is null
      and previous_source_count = 0 and previous_support_bps is null)
    or
    (previous_snapshot_id is not null
      and previous_support_bps = round(
        10000.0 * previous_source_count / previous_total_source_count
      )::integer
      and elapsed_seconds = floor(extract(epoch from (
        observed_at - previous_observed_at
      )))::bigint)
  ),
  check (
    (comparison_mode = 'baseline' and previous_snapshot_id is null
      and current_present and not previous_present
      and elapsed_seconds is null and support_delta_bps is null
      and support_velocity_bps_per_30d is null)
    or
    (comparison_mode <> 'baseline' and previous_snapshot_id is not null
      and previous_total_source_count is not null and elapsed_seconds is not null)
  ),
  check (
    (comparison_mode = 'comparable'
      and current_present and previous_present
      and support_delta_bps is not null
      and support_delta_bps = current_support_bps - previous_support_bps
      and support_velocity_bps_per_30d is not null
      and support_velocity_bps_per_30d = round(
        support_delta_bps::numeric * 2592000::numeric
          / elapsed_seconds::numeric,
        2
      )
      and binding_id is not null
      and elapsed_seconds >= 259200)
    or
    (comparison_mode <> 'comparable'
      and support_delta_bps is null
      and support_velocity_bps_per_30d is null)
  ),
  check (
    (comparison_mode = 'baseline' and current_present and not previous_present)
    or (comparison_mode = 'comparable' and current_present and previous_present)
    or (comparison_mode = 'category_reset')
    or (comparison_mode = 'signal_new' and current_present and not previous_present)
    or (comparison_mode = 'signal_removed' and not current_present and previous_present)
    or (comparison_mode = 'interval_too_short'
      and current_present and previous_present and elapsed_seconds < 259200)
  )
);

create index research_trend_velocity_timeline_idx
  on content_factory.research_watchlist_trend_velocity_events
  (organization_id, product_id, observed_at desc, snapshot_id desc, signal_key);

alter table content_factory.research_watchlist_trend_velocity_events
  enable row level security;
revoke all on content_factory.research_watchlist_trend_velocity_events
  from public, anon, authenticated, service_role;

create trigger reject_research_watchlist_trend_velocity_mutation
before update or delete
on content_factory.research_watchlist_trend_velocity_events
for each row execute function
  content_factory_private.reject_research_watchlist_memory_mutation();

create or replace function content_factory_private.capture_research_snapshot_trend_velocity(
  snapshot_id_value uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  current_snapshot content_factory.research_watchlist_snapshots%rowtype;
  previous_snapshot content_factory.research_watchlist_snapshots%rowtype;
  signal_key_value text;
  current_signal content_factory.research_watchlist_snapshot_trend_signals%rowtype;
  previous_signal content_factory.research_watchlist_snapshot_trend_signals%rowtype;
  current_total_value integer;
  previous_total_value integer;
  current_count_value integer;
  previous_count_value integer;
  current_support_value integer;
  previous_support_value integer;
  delta_value integer;
  elapsed_value bigint;
  velocity_value numeric(14, 2);
  comparison_value text;
  lineage_value text;
  event_value text;
  current_snapshot_signal_count integer := 0;
  previous_snapshot_signal_count integer := 0;
  current_binding_value uuid;
  previous_binding_value uuid;
  current_category_value uuid;
  previous_category_value uuid;
  snapshot_category_reset boolean := false;
begin
  select snapshot.* into current_snapshot
  from content_factory.research_watchlist_snapshots snapshot
  where snapshot.id = snapshot_id_value;
  if current_snapshot.id is null then
    raise exception using
      errcode = '22023', message = 'research_watchlist_snapshot_not_found';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(current_snapshot.organization_id::text),
    hashtext('research-trend-velocity:' || current_snapshot.watchlist_id::text)
  );

  if current_snapshot.previous_snapshot_id is not null then
    select snapshot.* into previous_snapshot
    from content_factory.research_watchlist_snapshots snapshot
    where snapshot.organization_id = current_snapshot.organization_id
      and snapshot.watchlist_id = current_snapshot.watchlist_id
      and snapshot.id = current_snapshot.previous_snapshot_id;
    if previous_snapshot.id is null then
      raise exception using
        errcode = '55000', message = 'research_trend_velocity_previous_snapshot_missing';
    end if;
  end if;

  select count(*)::integer into current_total_value
  from content_factory.research_watchlist_snapshot_sources source_link
  where source_link.organization_id = current_snapshot.organization_id
    and source_link.snapshot_id = current_snapshot.id;
  if current_total_value not between 1 and 100 then
    raise exception using
      errcode = '55000', message = 'research_trend_velocity_current_sources_invalid';
  end if;

  if previous_snapshot.id is not null then
    select count(*)::integer into previous_total_value
    from content_factory.research_watchlist_snapshot_sources source_link
    where source_link.organization_id = previous_snapshot.organization_id
      and source_link.snapshot_id = previous_snapshot.id;
    if previous_total_value not between 1 and 100 then
      raise exception using
        errcode = '55000', message = 'research_trend_velocity_previous_sources_invalid';
    end if;
    elapsed_value := floor(extract(epoch from (
      current_snapshot.observed_at - previous_snapshot.observed_at
    )))::bigint;
    if elapsed_value < 0 then
      raise exception using
        errcode = '55000', message = 'research_trend_velocity_interval_invalid';
    end if;
  end if;

  select count(*)::integer into current_snapshot_signal_count
  from content_factory.research_watchlist_snapshot_trend_signals signal
  where signal.organization_id = current_snapshot.organization_id
    and signal.snapshot_id = current_snapshot.id;
  if current_snapshot_signal_count > 0 then
    select signal.binding_id, signal.market_category_id
      into current_binding_value, current_category_value
    from content_factory.research_watchlist_snapshot_trend_signals signal
    where signal.organization_id = current_snapshot.organization_id
      and signal.snapshot_id = current_snapshot.id
    order by signal.signal_key
    limit 1;
    if exists (
      select 1
      from content_factory.research_watchlist_snapshot_trend_signals signal
      where signal.organization_id = current_snapshot.organization_id
        and signal.snapshot_id = current_snapshot.id
        and (
          signal.binding_id is distinct from current_binding_value
          or signal.market_category_id is distinct from current_category_value
        )
    ) then
      raise exception using
        errcode = '55000', message = 'research_trend_velocity_current_category_inconsistent';
    end if;
  end if;

  if previous_snapshot.id is not null then
    select count(*)::integer into previous_snapshot_signal_count
    from content_factory.research_watchlist_snapshot_trend_signals signal
    where signal.organization_id = previous_snapshot.organization_id
      and signal.snapshot_id = previous_snapshot.id;
    if previous_snapshot_signal_count > 0 then
      select signal.binding_id, signal.market_category_id
        into previous_binding_value, previous_category_value
      from content_factory.research_watchlist_snapshot_trend_signals signal
      where signal.organization_id = previous_snapshot.organization_id
        and signal.snapshot_id = previous_snapshot.id
      order by signal.signal_key
      limit 1;
      if exists (
        select 1
        from content_factory.research_watchlist_snapshot_trend_signals signal
        where signal.organization_id = previous_snapshot.organization_id
          and signal.snapshot_id = previous_snapshot.id
          and (
            signal.binding_id is distinct from previous_binding_value
            or signal.market_category_id is distinct from previous_category_value
          )
      ) then
        raise exception using
          errcode = '55000', message = 'research_trend_velocity_previous_category_inconsistent';
      end if;
    end if;
  end if;
  snapshot_category_reset := previous_snapshot.id is not null
    and current_snapshot_signal_count > 0
    and previous_snapshot_signal_count > 0
    and (
      current_binding_value is null
      or current_category_value is null
      or previous_binding_value is null
      or previous_category_value is null
      or current_binding_value is distinct from previous_binding_value
      or current_category_value is distinct from previous_category_value
    );

  for signal_key_value in
    select signal_key
    from (
      select signal.signal_key
      from content_factory.research_watchlist_snapshot_trend_signals signal
      where signal.organization_id = current_snapshot.organization_id
        and signal.snapshot_id = current_snapshot.id
      union
      select signal.signal_key
      from content_factory.research_watchlist_snapshot_trend_signals signal
      where previous_snapshot.id is not null
        and signal.organization_id = previous_snapshot.organization_id
        and signal.snapshot_id = previous_snapshot.id
    ) signal_union
    order by signal_key
  loop
    current_signal := null;
    previous_signal := null;
    select signal.* into current_signal
    from content_factory.research_watchlist_snapshot_trend_signals signal
    where signal.organization_id = current_snapshot.organization_id
      and signal.snapshot_id = current_snapshot.id
      and signal.signal_key = signal_key_value;
    if previous_snapshot.id is not null then
      select signal.* into previous_signal
      from content_factory.research_watchlist_snapshot_trend_signals signal
      where signal.organization_id = previous_snapshot.organization_id
        and signal.snapshot_id = previous_snapshot.id
        and signal.signal_key = signal_key_value;
    end if;

    select count(*)::integer into current_count_value
    from content_factory.research_watchlist_snapshot_trend_signal_sources source_link
    where source_link.organization_id = current_snapshot.organization_id
      and source_link.snapshot_id = current_snapshot.id
      and source_link.signal_key = signal_key_value;
    if previous_snapshot.id is null then
      previous_count_value := 0;
    else
      select count(*)::integer into previous_count_value
      from content_factory.research_watchlist_snapshot_trend_signal_sources source_link
      where source_link.organization_id = previous_snapshot.organization_id
        and source_link.snapshot_id = previous_snapshot.id
        and source_link.signal_key = signal_key_value;
    end if;

    current_support_value := round(
      10000.0 * current_count_value / current_total_value
    )::integer;
    previous_support_value := case
      when previous_snapshot.id is null then null
      else round(10000.0 * previous_count_value / previous_total_value)::integer
    end;
    delta_value := null;
    velocity_value := null;

    if previous_snapshot.id is null then
      comparison_value := 'baseline';
    elsif snapshot_category_reset then
      comparison_value := 'category_reset';
    elsif current_signal.snapshot_id is null then
      comparison_value := 'signal_removed';
    elsif previous_signal.snapshot_id is null then
      comparison_value := 'signal_new';
    elsif elapsed_value < 259200 then
      comparison_value := 'interval_too_short';
    else
      comparison_value := 'comparable';
      delta_value := current_support_value - previous_support_value;
      velocity_value := round(
        delta_value::numeric * 2592000::numeric / elapsed_value::numeric,
        2
      );
    end if;

    lineage_value := content_factory_private.json_hash(jsonb_build_object(
      'definition_version', 'approved-structural-support-velocity-v1',
      'organization_id', current_snapshot.organization_id,
      'watchlist_id', current_snapshot.watchlist_id,
      'snapshot_id', current_snapshot.id,
      'snapshot_hash', current_snapshot.snapshot_hash,
      'previous_snapshot_id', previous_snapshot.id,
      'previous_snapshot_hash', previous_snapshot.snapshot_hash,
      'signal_key', signal_key_value,
      'current_binding_id', current_binding_value,
      'previous_binding_id', previous_binding_value,
      'current_market_category_id', current_category_value,
      'previous_market_category_id', previous_category_value,
      'current_evidence_hash', current_signal.evidence_hash,
      'previous_evidence_hash', previous_signal.evidence_hash,
      'current_source_ids_hash', current_signal.source_ids_hash,
      'previous_source_ids_hash', previous_signal.source_ids_hash
    ));
    event_value := content_factory_private.json_hash(jsonb_build_object(
      'lineage_hash', lineage_value,
      'comparison_mode', comparison_value,
      'current_source_count', current_count_value,
      'previous_source_count', previous_count_value,
      'current_total_source_count', current_total_value,
      'previous_total_source_count', previous_total_value,
      'current_support_bps', current_support_value,
      'previous_support_bps', previous_support_value,
      'support_delta_bps', delta_value,
      'elapsed_seconds', elapsed_value,
      'support_velocity_bps_per_30d', velocity_value
    ));

    insert into content_factory.research_watchlist_trend_velocity_events (
      organization_id, snapshot_id, previous_snapshot_id, run_id, product_id,
      watchlist_id, binding_id, market_category_id, signal_key,
      definition_version, comparison_mode, current_present, previous_present,
      current_direction, previous_direction, current_confidence,
      previous_confidence, current_source_count, previous_source_count,
      current_total_source_count, previous_total_source_count,
      current_support_bps, previous_support_bps, support_delta_bps,
      elapsed_seconds, support_velocity_bps_per_30d, current_evidence_hash,
      previous_evidence_hash, current_source_ids_hash,
      previous_source_ids_hash, lineage_hash, event_hash, observed_at,
      previous_observed_at
    ) values (
      current_snapshot.organization_id, current_snapshot.id,
      previous_snapshot.id, current_snapshot.run_id,
      current_snapshot.product_id, current_snapshot.watchlist_id,
      current_binding_value, current_category_value,
      signal_key_value, 'approved-structural-support-velocity-v1',
      comparison_value, current_signal.snapshot_id is not null,
      previous_signal.snapshot_id is not null, current_signal.direction,
      previous_signal.direction, current_signal.confidence,
      previous_signal.confidence, current_count_value, previous_count_value,
      current_total_value, previous_total_value, current_support_value,
      previous_support_value, delta_value, elapsed_value, velocity_value,
      current_signal.evidence_hash, previous_signal.evidence_hash,
      current_signal.source_ids_hash, previous_signal.source_ids_hash,
      lineage_value, event_value, current_snapshot.observed_at,
      previous_snapshot.observed_at
    ) on conflict (organization_id, snapshot_id, signal_key) do nothing;
  end loop;
end;
$$;

-- Snapshot rows fire the canonical-signal trigger before their exact source
-- junction is inserted.  Wrap the enclosing capture routine instead so the
-- velocity event sees both completed junctions and can remain append-only.
alter function content_factory_private.capture_research_watchlist_snapshot(
  uuid, uuid
) rename to capture_research_watchlist_snapshot_pre_velocity_v1;

create or replace function content_factory_private.capture_research_watchlist_snapshot(
  watchlist_id_value uuid,
  draft_id_value uuid
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  snapshot_id_value uuid;
begin
  snapshot_id_value :=
    content_factory_private.capture_research_watchlist_snapshot_pre_velocity_v1(
      watchlist_id_value, draft_id_value
    );
  if snapshot_id_value is not null then
    perform content_factory_private.capture_research_snapshot_trend_velocity(
      snapshot_id_value
    );
  end if;
  return snapshot_id_value;
end;
$$;

do $backfill$
declare
  snapshot_record record;
begin
  for snapshot_record in
    select snapshot.id
    from content_factory.research_watchlist_snapshots snapshot
    order by snapshot.created_at, snapshot.snapshot_version, snapshot.id
  loop
    perform content_factory_private.capture_research_snapshot_canonical_trends(
      snapshot_record.id
    );
    perform content_factory_private.capture_research_snapshot_trend_velocity(
      snapshot_record.id
    );
  end loop;
end;
$backfill$;

alter function public.creator_research_market_category_registry(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_research_market_category_registry(jsonb)
  rename to creator_research_market_category_registry_pre_velocity_v1;
revoke all on function
  content_factory_private.creator_research_market_category_registry_pre_velocity_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_research_market_category_registry(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  base_value jsonb;
  organization_id_value uuid;
  product_id_value uuid;
  timeline_limit_value integer := 24;
  velocity_value jsonb := '[]'::jsonb;
  velocity_guidance_value jsonb;
  velocity_action_value text;
begin
  base_value :=
    content_factory_private.creator_research_market_category_registry_pre_velocity_v1(
      p_payload
    );
  organization_id_value := (p_payload ->> 'organization_id')::uuid;
  product_id_value := (base_value ->> 'product_id')::uuid;
  if p_payload ? 'timeline_limit' then
    timeline_limit_value := (p_payload ->> 'timeline_limit')::integer;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'snapshot_id', event.snapshot_id,
    'previous_snapshot_id', event.previous_snapshot_id,
    'run_id', event.run_id,
    'observed_at', event.observed_at,
    'previous_observed_at', event.previous_observed_at,
    'category_key', event.market_category_id,
    'signal_key', event.signal_key,
    'canonical_label', catalog.canonical_label,
    'definition_version', event.definition_version,
    'comparison_mode', event.comparison_mode,
    'current_present', event.current_present,
    'previous_present', event.previous_present,
    'current_direction', event.current_direction,
    'previous_direction', event.previous_direction,
    'current_source_count', event.current_source_count,
    'previous_source_count', event.previous_source_count,
    'current_total_source_count', event.current_total_source_count,
    'previous_total_source_count', event.previous_total_source_count,
    'current_support_bps', event.current_support_bps,
    'previous_support_bps', event.previous_support_bps,
    'support_delta_bps', event.support_delta_bps,
    'elapsed_seconds', event.elapsed_seconds,
    'support_velocity_bps_per_30d', event.support_velocity_bps_per_30d,
    'lineage_hash', event.lineage_hash,
    'event_hash', event.event_hash,
    'claim_allowed', event.comparison_mode = 'comparable',
    'support_state', case
      when event.comparison_mode <> 'comparable' then 'no_velocity_claim'
      when event.support_delta_bps > 0 then 'support_breadth_increasing'
      when event.support_delta_bps < 0 then 'support_breadth_decreasing'
      else 'support_breadth_stable'
    end,
    'recommended_next_step', case event.comparison_mode
      when 'baseline' then 'collect_next_approved_snapshot'
      when 'signal_new' then 'collect_next_approved_snapshot'
      when 'signal_removed' then 'review_trends_stage'
      when 'category_reset' then 'establish_new_category_baseline'
      when 'interval_too_short' then 'wait_for_minimum_interval'
      else 'review_support_velocity'
    end
  ) order by event.observed_at desc, event.snapshot_version desc,
      event.snapshot_id desc, event.signal_key), '[]'::jsonb)
    into velocity_value
  from (
    select bounded_event.*, snapshot.snapshot_version
    from content_factory.research_watchlist_trend_velocity_events bounded_event
    join content_factory.research_watchlist_snapshots snapshot
      on snapshot.organization_id = bounded_event.organization_id
     and snapshot.id = bounded_event.snapshot_id
    where bounded_event.organization_id = organization_id_value
      and bounded_event.product_id = product_id_value
    order by bounded_event.observed_at desc, snapshot.snapshot_version desc,
      bounded_event.snapshot_id desc, bounded_event.signal_key
    limit timeline_limit_value
  ) event
  join content_factory.research_structural_trend_signal_types catalog
    on catalog.signal_key = event.signal_key;

  select case
    when bool_or(event.comparison_mode = 'signal_removed')
      then 'review_trends_stage'
    when bool_or(event.comparison_mode = 'category_reset')
      then 'establish_new_category_baseline'
    when bool_or(event.comparison_mode = 'interval_too_short')
      then 'wait_for_minimum_interval'
    when bool_or(event.comparison_mode in ('signal_new', 'baseline'))
      then 'collect_next_approved_snapshot'
    when bool_or(event.comparison_mode = 'comparable')
      then 'review_support_velocity'
    else 'collect_next_approved_snapshot'
  end into velocity_action_value
  from content_factory.research_watchlist_trend_velocity_events event
  where event.organization_id = organization_id_value
    and event.product_id = product_id_value
    and event.snapshot_id = (
      select latest_event.snapshot_id
      from content_factory.research_watchlist_trend_velocity_events latest_event
      join content_factory.research_watchlist_snapshots latest_snapshot
        on latest_snapshot.organization_id = latest_event.organization_id
       and latest_snapshot.id = latest_event.snapshot_id
      where latest_event.organization_id = organization_id_value
        and latest_event.product_id = product_id_value
      order by latest_event.observed_at desc,
        latest_snapshot.snapshot_version desc, latest_event.snapshot_id desc
      limit 1
    );

  velocity_guidance_value := jsonb_build_object(
    'status', velocity_action_value,
    'recommended_next_step', velocity_action_value,
    'metric_kind', 'approved_structural_evidence_support_not_performance',
    'minimum_interval_hours', 72,
    'human_correction_stage', 'trends'
  );

  return base_value || jsonb_build_object(
    'trend_velocity', velocity_value,
    'guidance', (base_value -> 'guidance') || jsonb_build_object(
      'trend_velocity', velocity_guidance_value
    )
  );
end;
$$;

revoke all on function public.creator_research_market_category_registry(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_research_market_category_registry(jsonb)
  to authenticated;

-- Readiness v2 removes false semantic credit from retained YouTube metadata.
-- Unconfirmed, non-excluded observations may increase source volume and
-- platform diversity only.  A confirmed candidate can count as one deduped
-- competitor channel and as human validation; raw metadata never counts as a
-- structured source analysis.

alter function content_factory_private.research_category_evidence_readiness(
  uuid, uuid, timestamptz
) rename to research_category_evidence_readiness_v1_base;

create or replace function content_factory_private.research_category_evidence_readiness(
  organization_id_value uuid,
  market_category_id_value uuid,
  as_of_value timestamptz default clock_timestamp()
)
returns jsonb
language plpgsql
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  source_count_value integer := 0;
  platform_count_value integer := 0;
  competitor_count_value integer := 0;
  trend_count_value integer := 0;
  analysis_count_value integer := 0;
  human_validation_count_value integer := 0;
  youtube_source_count_value integer := 0;
  youtube_confirmed_channel_count_value integer := 0;
  youtube_confirmed_count_value integer := 0;
  durable_youtube_present_value boolean := false;
  source_hashes_value jsonb := '[]'::jsonb;
  analysis_hashes_value jsonb := '[]'::jsonb;
  trend_hashes_value jsonb := '[]'::jsonb;
  youtube_observation_hashes_value jsonb := '[]'::jsonb;
  youtube_decision_hashes_value jsonb := '[]'::jsonb;
  dimensions_value jsonb;
  score_value integer;
begin
  -- Source identity versions are ordered by the immutable source timestamp,
  -- not by transaction-stable now() plus a random ledger UUID.  This keeps the
  -- score and the source card on the same exact current content version.
  with current_sources as (
    select distinct on (ledger.source_identity_key) ledger.*
    from content_factory.research_category_source_ledger ledger
    join content_factory.product_research_sources original_source
      on original_source.organization_id = ledger.organization_id
     and original_source.run_id = ledger.run_id
     and original_source.id = ledger.source_id
    where ledger.organization_id = organization_id_value
      and ledger.market_category_id = market_category_id_value
    order by ledger.source_identity_key, original_source.created_at desc,
      ledger.registered_at desc, ledger.source_id desc, ledger.id desc
  ), current_analysis as (
    select distinct on (event.source_ledger_id)
      event.source_ledger_id, event.origin, event.event_hash,
      event.analysis ->> 'classification' as classification
    from content_factory.research_source_analysis_events event
    join current_sources source on source.id = event.source_ledger_id
    where event.organization_id = organization_id_value
    order by event.source_ledger_id, event.analysis_version desc, event.id desc
  ), eligible_sources as (
    select source.id, source.source_identity_key, source.platform,
      source.lineage_hash, analysis.classification
    from current_sources source
    left join current_analysis analysis on analysis.source_ledger_id = source.id
    where analysis.classification is distinct from 'irrelevant'
  )
  select
    (select count(*)::integer from eligible_sources),
    (select count(distinct source.platform)::integer from eligible_sources source),
    (select count(distinct source.source_identity_key)::integer
       from eligible_sources source
      where source.classification = 'competitor'),
    (select coalesce(
       jsonb_agg(source.lineage_hash order by source.lineage_hash),
       '[]'::jsonb
     ) from eligible_sources source),
    (select coalesce(bool_or(source.platform = 'youtube'), false)
       from eligible_sources source),
    (select count(*)::integer from current_analysis),
    (select count(*)::integer from current_analysis analysis
      where analysis.origin = 'human_correction'),
    (select coalesce(
       jsonb_agg(analysis.event_hash order by analysis.event_hash),
       '[]'::jsonb
     ) from current_analysis analysis)
  into source_count_value, platform_count_value, competitor_count_value,
       source_hashes_value, durable_youtube_present_value,
       analysis_count_value, human_validation_count_value,
       analysis_hashes_value;

  with latest_observations as (
    select distinct on (observation.video_id) observation.*
    from content_factory.research_youtube_video_observations observation
    where observation.organization_id = organization_id_value
      and observation.market_category_id = market_category_id_value
      and observation.retention_expires_at > as_of_value
      and observation.observed_at <= as_of_value
    order by observation.video_id, observation.observed_at desc,
      observation.observation_hash desc, observation.id desc
  ), observed_with_decision as (
    select observation.*, decision.decision, decision.decision_hash
    from latest_observations observation
    left join lateral (
      select candidate.decision, candidate.decision_hash
      from content_factory.research_youtube_candidate_decisions candidate
      where candidate.organization_id = observation.organization_id
        and candidate.observation_id = observation.id
        and candidate.retention_expires_at > as_of_value
        and candidate.decided_at <= as_of_value
      order by candidate.decided_at desc, candidate.decision_hash desc,
        candidate.id desc
      limit 1
    ) decision on true
  ), eligible as (
    select observed.*
    from observed_with_decision observed
    where observed.decision is distinct from 'exclude_candidate'
  )
  select
    (select count(distinct evidence.video_id)::integer from eligible evidence),
    (select count(distinct evidence.channel_id)::integer
       from eligible evidence
      where evidence.decision = 'confirm_candidate'),
    (select count(distinct evidence.video_id)::integer
       from eligible evidence
      where evidence.decision = 'confirm_candidate'),
    (select coalesce(
       jsonb_agg(observed.observation_hash order by observed.observation_hash),
       '[]'::jsonb
     ) from observed_with_decision observed),
    (select coalesce(
       jsonb_agg(observed.decision_hash order by observed.decision_hash)
         filter (where observed.decision_hash is not null),
       '[]'::jsonb
     ) from observed_with_decision observed)
  into youtube_source_count_value, youtube_confirmed_channel_count_value,
       youtube_confirmed_count_value, youtube_observation_hashes_value,
       youtube_decision_hashes_value;

  competitor_count_value :=
    competitor_count_value + youtube_confirmed_channel_count_value;
  source_count_value := source_count_value + youtube_source_count_value;
  if youtube_source_count_value > 0 and not durable_youtube_present_value then
    platform_count_value := platform_count_value + 1;
  end if;
  human_validation_count_value :=
    human_validation_count_value + youtube_confirmed_count_value;

  with recent_signals as (
    select signal.signal_key, signal.evidence_hash
    from content_factory.research_watchlist_snapshot_trend_signals signal
    where signal.organization_id = organization_id_value
      and signal.market_category_id = market_category_id_value
      and signal.observed_at >= as_of_value - interval '30 days'
      and signal.observed_at <= as_of_value
  ), distinct_hashes as (
    select distinct signal.evidence_hash from recent_signals signal
  )
  select (select count(distinct signal.signal_key)::integer
            from recent_signals signal),
         (select coalesce(
            jsonb_agg(hash.evidence_hash order by hash.evidence_hash),
            '[]'::jsonb
          ) from distinct_hashes hash)
  into trend_count_value, trend_hashes_value;

  dimensions_value := jsonb_build_array(
    content_factory_private.research_readiness_dimension(
      'source_volume', 'Current reviewable source volume', 20,
      source_count_value, 12, 'collect_more_reviewable_sources'
    ),
    content_factory_private.research_readiness_dimension(
      'platform_diversity', 'Platform diversity', 15,
      platform_count_value, 3, 'add_an_independent_platform'
    ),
    content_factory_private.research_readiness_dimension(
      'competitor_observations',
      'Competitor observations / confirmed YouTube channels', 20,
      competitor_count_value, 5, 'collect_competitor_observations'
    ),
    content_factory_private.research_readiness_dimension(
      'trend_recency', 'Recent canonical trend evidence', 15,
      trend_count_value, 6, 'refresh_canonical_trend_evidence'
    ),
    content_factory_private.research_readiness_dimension(
      'analysis_coverage', 'Structured / normalized source coverage', 15,
      analysis_count_value, 8, 'analyze_unreviewed_sources'
    ),
    content_factory_private.research_readiness_dimension(
      'human_validation', 'Human-validated evidence', 15,
      human_validation_count_value, 4, 'review_and_correct_source_analysis'
    )
  );

  select coalesce(sum((dimension ->> 'weighted_points')::integer), 0)::integer
    into score_value
  from jsonb_array_elements(dimensions_value) dimension;

  return jsonb_build_object(
    'metric_kind', 'category_evidence_readiness_not_model_iq',
    'definition_version', 'category-evidence-readiness-v2',
    'score', score_value,
    'dimensions', dimensions_value,
    'weights_total', 100,
    'evidence_hash', content_factory_private.json_hash(jsonb_build_object(
      'definition_version', 'category-evidence-readiness-v2',
      'organization_id', organization_id_value,
      'market_category_id', market_category_id_value,
      'source_lineage_hashes', source_hashes_value,
      'analysis_event_hashes', analysis_hashes_value,
      'current_retained_youtube_observation_hashes',
        youtube_observation_hashes_value,
      'current_retained_youtube_decision_hashes',
        youtube_decision_hashes_value,
      'recent_trend_evidence_hashes', trend_hashes_value,
      'dimensions', dimensions_value
    )),
    'as_of', as_of_value,
    'limits', jsonb_build_object(
      'is_model_iq', false,
      'is_quality_guarantee', false,
      'competitor_metric_is_unique_publishers', false,
      'retained_youtube_uses_unique_channel_ids', true,
      'youtube_retention_days', 29,
      'meaning',
        'Coverage of durable evidence plus retention-bound YouTube metadata; only confirmed candidates add semantic credit'
    )
  );
end;
$$;

-- Keep the status card on the same deterministic content version used by v2.
-- The previous RPC still owns auth, tenant checks and every unrelated bounded
-- section; this wrapper replaces only source_ledger.items.
alter function public.creator_research_category_learning_status(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_research_category_learning_status(jsonb)
  rename to creator_research_category_learning_status_pre_truth_v1;
revoke all on function
  content_factory_private.creator_research_category_learning_status_pre_truth_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_research_category_learning_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  base_value jsonb;
  organization_id_value uuid;
  market_category_id_value uuid;
  sources_value jsonb := '[]'::jsonb;
begin
  base_value :=
    content_factory_private.creator_research_category_learning_status_pre_truth_v1(
      p_payload
    );
  organization_id_value := (base_value ->> 'organization_id')::uuid;
  market_category_id_value := (base_value #>> '{category,category_id}')::uuid;

  with bounded_sources as (
    select distinct on (ledger.source_identity_key)
      ledger.*, original_source.created_at as source_created_at
    from content_factory.research_category_source_ledger ledger
    join content_factory.product_research_sources original_source
      on original_source.organization_id = ledger.organization_id
     and original_source.run_id = ledger.run_id
     and original_source.id = ledger.source_id
    where ledger.organization_id = organization_id_value
      and ledger.market_category_id = market_category_id_value
    order by ledger.source_identity_key, original_source.created_at desc,
      ledger.registered_at desc, ledger.source_id desc, ledger.id desc
  ), limited_sources as (
    select source.*
    from bounded_sources source
    order by source.source_created_at desc, source.registered_at desc,
      source.source_id desc, source.id desc
    limit 50
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'source_ledger_id', source.id,
    'source_id', source.source_id,
    'run_id', source.run_id,
    'product_id', source.product_id,
    'source_type', source.source_type,
    'title', source.title,
    'source_url', source.source_url,
    'provider_key', source.provider_key,
    'platform', source.platform,
    'trust_level', source.trust_level,
    'source_identity_key', source.source_identity_key,
    'fetched_at', source.fetched_at,
    'published_at', source.published_at,
    'lineage_hash', source.lineage_hash,
    'registered_at', source.registered_at,
    'lineage_history', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_ledger_id', lineage.id,
        'source_id', lineage.source_id,
        'source_content_hash', lineage.source_content_hash,
        'lineage_hash', lineage.lineage_hash,
        'fetched_at', lineage.fetched_at,
        'published_at', lineage.published_at,
        'registered_at', lineage.registered_at
      ) order by lineage.source_created_at desc, lineage.registered_at desc,
          lineage.source_id desc, lineage.id desc), '[]'::jsonb)
      from (
        select version.*,
          original_version.created_at as source_created_at
        from content_factory.research_category_source_ledger version
        join content_factory.product_research_sources original_version
          on original_version.organization_id = version.organization_id
         and original_version.run_id = version.run_id
         and original_version.id = version.source_id
        where version.organization_id = source.organization_id
          and version.market_category_id = source.market_category_id
          and version.source_identity_key = source.source_identity_key
        order by original_version.created_at desc, version.registered_at desc,
          version.source_id desc, version.id desc
        limit 10
      ) lineage
    ),
    'current_analysis', (
      select jsonb_build_object(
        'event_id', head.id,
        'analysis_version', head.analysis_version,
        'origin', head.origin,
        'parser_key', head.parser_key,
        'parser_version', head.parser_version,
        'analysis', head.analysis,
        'correction_reason', head.correction_reason,
        'event_hash', head.event_hash,
        'created_at', head.created_at
      )
      from content_factory.research_source_analysis_events head
      where head.organization_id = source.organization_id
        and head.source_ledger_id = source.id
      order by head.analysis_version desc, head.id desc
      limit 1
    ),
    'analysis_history', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'event_id', history.id,
        'analysis_version', history.analysis_version,
        'parent_event_id', history.parent_event_id,
        'origin', history.origin,
        'actor_id', history.actor_id,
        'parser_key', history.parser_key,
        'parser_version', history.parser_version,
        'analysis', history.analysis,
        'correction_reason', history.correction_reason,
        'event_hash', history.event_hash,
        'created_at', history.created_at
      ) order by history.analysis_version desc), '[]'::jsonb)
      from (
        select event.*
        from content_factory.research_source_analysis_events event
        where event.organization_id = source.organization_id
          and event.source_ledger_id = source.id
        order by event.analysis_version desc, event.id desc
        limit 10
      ) history
    )
  ) order by source.source_created_at desc, source.registered_at desc,
      source.source_id desc, source.id desc), '[]'::jsonb)
  into sources_value
  from limited_sources source;

  return jsonb_set(base_value, '{source_ledger,items}', sources_value, true);
end;
$$;

revoke all on function public.creator_research_category_learning_status(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_research_category_learning_status(jsonb)
  to authenticated;

alter table content_factory.research_category_readiness_snapshots
  drop constraint research_category_readiness_snapshots_definition_version_check;
alter table content_factory.research_category_readiness_snapshots
  add constraint research_category_readiness_snapshots_definition_version_check
  check (definition_version in (
    'category-evidence-readiness-v1', 'category-evidence-readiness-v2'
  ));

create or replace function content_factory_private.normalize_research_readiness_snapshot_v2()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  new.definition_version := 'category-evidence-readiness-v2';
  new.snapshot_hash := content_factory_private.json_hash(jsonb_build_object(
    'version', 'category-evidence-readiness-snapshot-v2',
    'organization_id', new.organization_id,
    'market_category_id', new.market_category_id,
    'product_id', new.product_id,
    'binding_id', new.binding_id,
    'run_id', new.run_id,
    'evidence_hash', new.evidence_hash,
    'score', new.score,
    'dimensions', new.dimensions
  ));
  return new;
end;
$$;

create trigger normalize_research_readiness_snapshot_v2
before insert on content_factory.research_category_readiness_snapshots
for each row execute function
  content_factory_private.normalize_research_readiness_snapshot_v2();

revoke all on function
  content_factory_private.capture_research_snapshot_trend_velocity(uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_watchlist_snapshot(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_category_evidence_readiness(
    uuid, uuid, timestamptz
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_category_evidence_readiness_v1_base(
    uuid, uuid, timestamptz
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.normalize_research_readiness_snapshot_v2()
  from public, anon, authenticated, service_role;

commit;

begin;

-- Provider-free temporal memory for approved v2 research. Nothing in this
-- migration creates, claims, queues, or completes a product research run.

create unique index if not exists product_research_runs_org_product_id_uq
  on content_factory.product_research_runs (organization_id, product_id, id);
create unique index if not exists creative_brief_drafts_org_product_id_uq
  on content_factory.creative_brief_drafts (organization_id, product_id, id);

create table if not exists content_factory.research_watchlists (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    created_by uuid not null,
    updated_by uuid not null,
    status text not null default 'active'
      check (status in ('active', 'paused')),
    refresh_interval_days integer not null default 14
      check (refresh_interval_days between 3 and 90),
    next_refresh_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint research_watchlists_org_id_uq
      unique (organization_id, id),
    constraint research_watchlists_org_product_uq
      unique (organization_id, product_id),
    constraint research_watchlists_org_product_id_uq
      unique (organization_id, product_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, updated_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (status = 'active' and next_refresh_at is not null)
      or (status = 'paused' and next_refresh_at is null)
    )
);

create index if not exists research_watchlists_due_idx
  on content_factory.research_watchlists (next_refresh_at, created_at, id)
  where status = 'active';

create table if not exists content_factory.research_watchlist_snapshots (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    watchlist_id uuid not null,
    run_id uuid not null,
    draft_id uuid not null,
    previous_snapshot_id uuid,
    snapshot_version integer not null check (snapshot_version between 1 and 100000),
    approved_by uuid not null,
    observed_at timestamptz not null,
    refresh_interval_days integer not null
      check (refresh_interval_days between 3 and 90),
    category_analysis jsonb not null check (
      jsonb_typeof(category_analysis) = 'object'
      and length(category_analysis::text) <= 131072
    ),
    competitor_analysis jsonb not null check (
      jsonb_typeof(competitor_analysis) = 'object'
      and length(competitor_analysis::text) <= 131072
    ),
    trend_analysis jsonb not null check (
      jsonb_typeof(trend_analysis) = 'object'
      and length(trend_analysis::text) <= 131072
    ),
    guidance jsonb not null check (
      jsonb_typeof(guidance) = 'object'
      and length(guidance::text) <= 32768
    ),
    source_ids jsonb not null check (
      jsonb_typeof(source_ids) = 'array'
      and jsonb_array_length(source_ids) between 1 and 100
    ),
    source_ids_hash text not null check (source_ids_hash ~ '^[0-9a-f]{64}$'),
    snapshot_hash text not null check (snapshot_hash ~ '^[0-9a-f]{64}$'),
    change_set jsonb not null check (
      jsonb_typeof(change_set) = 'object'
      and length(change_set::text) <= 131072
    ),
    created_at timestamptz not null default now(),
    constraint research_watchlist_snapshots_org_id_uq
      unique (organization_id, id),
    constraint research_watchlist_snapshots_org_watch_id_uq
      unique (organization_id, watchlist_id, id),
    constraint research_watchlist_snapshots_org_id_run_uq
      unique (organization_id, id, run_id),
    constraint research_watchlist_snapshots_org_watch_version_uq
      unique (organization_id, watchlist_id, snapshot_version),
    constraint research_watchlist_snapshots_org_watch_draft_uq
      unique (organization_id, watchlist_id, draft_id),
    constraint research_watchlist_snapshots_org_watch_hash_uq
      unique (organization_id, watchlist_id, snapshot_hash),
    foreign key (organization_id, product_id, watchlist_id)
      references content_factory.research_watchlists(
        organization_id, product_id, id
      ),
    foreign key (organization_id, product_id, run_id)
      references content_factory.product_research_runs(
        organization_id, product_id, id
      ),
    foreign key (organization_id, product_id, draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, product_id, id
      ),
    foreign key (organization_id, run_id, draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    foreign key (organization_id, watchlist_id, previous_snapshot_id)
      references content_factory.research_watchlist_snapshots(
        organization_id, watchlist_id, id
      ),
    foreign key (organization_id, approved_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (snapshot_version = 1 and previous_snapshot_id is null)
      or (snapshot_version > 1 and previous_snapshot_id is not null)
    )
);

create index if not exists research_watchlist_snapshots_timeline_idx
  on content_factory.research_watchlist_snapshots
  (organization_id, watchlist_id, observed_at desc, snapshot_version desc);

create table if not exists content_factory.research_watchlist_snapshot_sources (
    organization_id uuid not null,
    snapshot_id uuid not null,
    run_id uuid not null,
    source_id uuid not null,
    ordinal integer not null check (ordinal between 1 and 100),
    created_at timestamptz not null default now(),
    primary key (organization_id, snapshot_id, source_id),
    unique (organization_id, snapshot_id, ordinal),
    foreign key (organization_id, snapshot_id, run_id)
      references content_factory.research_watchlist_snapshots(
        organization_id, id, run_id
      ),
    foreign key (organization_id, run_id, source_id)
      references content_factory.product_research_sources(
        organization_id, run_id, id
      )
);

create index if not exists research_watchlist_snapshot_sources_source_idx
  on content_factory.research_watchlist_snapshot_sources
  (organization_id, run_id, source_id, snapshot_id);

create table if not exists content_factory.research_refresh_proposals (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    watchlist_id uuid not null,
    snapshot_id uuid not null,
    due_at timestamptz not null,
    reason text not null default 'scheduled_due'
      check (reason = 'scheduled_due'),
    status text not null default 'open'
      check (status in ('open', 'superseded')),
    proposal_hash text not null check (proposal_hash ~ '^[0-9a-f]{64}$'),
    superseded_reason text check (
      superseded_reason is null
      or superseded_reason in (
        'snapshot_captured', 'watchlist_paused', 'configuration_changed'
      )
    ),
    superseded_at timestamptz,
    created_at timestamptz not null default now(),
    constraint research_refresh_proposals_org_id_uq
      unique (organization_id, id),
    constraint research_refresh_proposals_org_hash_uq
      unique (organization_id, proposal_hash),
    foreign key (organization_id, watchlist_id, snapshot_id)
      references content_factory.research_watchlist_snapshots(
        organization_id, watchlist_id, id
      ),
    check (
      (status = 'open' and superseded_reason is null and superseded_at is null)
      or (
        status = 'superseded'
        and superseded_reason is not null
        and superseded_at is not null
      )
    )
);

create unique index if not exists research_refresh_proposals_one_open_uq
  on content_factory.research_refresh_proposals
  (organization_id, watchlist_id)
  where status = 'open';
create index if not exists research_refresh_proposals_timeline_idx
  on content_factory.research_refresh_proposals
  (organization_id, watchlist_id, created_at desc, id desc);

alter table content_factory.research_watchlists enable row level security;
alter table content_factory.research_watchlist_snapshots enable row level security;
alter table content_factory.research_watchlist_snapshot_sources enable row level security;
alter table content_factory.research_refresh_proposals enable row level security;

revoke all on content_factory.research_watchlists
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_watchlist_snapshots
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_watchlist_snapshot_sources
  from public, anon, authenticated, service_role;
revoke all on content_factory.research_refresh_proposals
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.reject_research_watchlist_memory_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_append_only';
end;
$$;

drop trigger if exists reject_research_watchlist_snapshot_mutation
  on content_factory.research_watchlist_snapshots;
create trigger reject_research_watchlist_snapshot_mutation
before update or delete on content_factory.research_watchlist_snapshots
for each row execute function
  content_factory_private.reject_research_watchlist_memory_mutation();

drop trigger if exists reject_research_watchlist_snapshot_source_mutation
  on content_factory.research_watchlist_snapshot_sources;
create trigger reject_research_watchlist_snapshot_source_mutation
before update or delete on content_factory.research_watchlist_snapshot_sources
for each row execute function
  content_factory_private.reject_research_watchlist_memory_mutation();

create or replace function content_factory_private.guard_research_watchlist()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000', message = 'research_watchlist_deletion_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.product_id <> old.product_id
     or new.created_by <> old.created_by
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000', message = 'research_watchlist_identity_immutable';
  end if;
  if new.status <> old.status and not (
    (old.status = 'active' and new.status = 'paused')
    or (old.status = 'paused' and new.status = 'active')
  ) then
    raise exception using
      errcode = '55000', message = 'research_watchlist_transition_invalid';
  end if;
  new.updated_at := clock_timestamp();
  return new;
end;
$$;

drop trigger if exists guard_research_watchlist
  on content_factory.research_watchlists;
create trigger guard_research_watchlist
before update or delete on content_factory.research_watchlists
for each row execute function content_factory_private.guard_research_watchlist();

create or replace function content_factory_private.guard_research_refresh_proposal()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000', message = 'research_refresh_proposal_deletion_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.watchlist_id <> old.watchlist_id
     or new.snapshot_id <> old.snapshot_id
     or new.due_at <> old.due_at
     or new.reason <> old.reason
     or new.proposal_hash <> old.proposal_hash
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000', message = 'research_refresh_proposal_identity_immutable';
  end if;
  if old.status <> 'open'
     or new.status <> 'superseded'
     or new.superseded_reason is null
     or new.superseded_at is null then
    raise exception using
      errcode = '55000', message = 'research_refresh_proposal_transition_invalid';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_research_refresh_proposal
  on content_factory.research_refresh_proposals;
create trigger guard_research_refresh_proposal
before update or delete on content_factory.research_refresh_proposals
for each row execute function
  content_factory_private.guard_research_refresh_proposal();

create or replace function content_factory_private.research_watchlist_key(
  value text
)
returns text
language sql
immutable
set search_path = ''
as $$
  select lower(regexp_replace(btrim(coalesce($1, '')), '[[:space:]]+', ' ', 'g'))
$$;

create or replace function content_factory_private.research_competitor_change_set(
  previous_value jsonb,
  current_value jsonb
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  with previous_items as (
    select
      content_factory_private.research_watchlist_key(item.value ->> 'name') as item_key,
      min(btrim(item.value ->> 'name')) as display_name,
      jsonb_agg(item.value order by item.value::text) as bodies
    from jsonb_array_elements(
      case
        when jsonb_typeof($1 -> 'competitors') = 'array'
          then $1 -> 'competitors'
        else '[]'::jsonb
      end
    ) item(value)
    where content_factory_private.research_watchlist_key(item.value ->> 'name') <> ''
    group by content_factory_private.research_watchlist_key(item.value ->> 'name')
  ),
  current_items as (
    select
      content_factory_private.research_watchlist_key(item.value ->> 'name') as item_key,
      min(btrim(item.value ->> 'name')) as display_name,
      jsonb_agg(item.value order by item.value::text) as bodies
    from jsonb_array_elements(
      case
        when jsonb_typeof($2 -> 'competitors') = 'array'
          then $2 -> 'competitors'
        else '[]'::jsonb
      end
    ) item(value)
    where content_factory_private.research_watchlist_key(item.value ->> 'name') <> ''
    group by content_factory_private.research_watchlist_key(item.value ->> 'name')
  ),
  changes as (
    select
      coalesce(current_items.item_key, previous_items.item_key) as item_key,
      previous_items.display_name as previous_name,
      current_items.display_name as current_name,
      previous_items.bodies as previous_bodies,
      current_items.bodies as current_bodies
    from previous_items
    full join current_items using (item_key)
  )
  select jsonb_build_object(
    'coverage_from', $1 ->> 'coverage',
    'coverage_to', $2 ->> 'coverage',
    'coverage_changed', ($1 ->> 'coverage') is distinct from ($2 ->> 'coverage'),
    'added_names', coalesce((
      select jsonb_agg(current_name order by item_key)
      from changes
      where previous_bodies is null
    ), '[]'::jsonb),
    'removed_names', coalesce((
      select jsonb_agg(previous_name order by item_key)
      from changes
      where current_bodies is null
    ), '[]'::jsonb),
    'changed_names', coalesce((
      select jsonb_agg(current_name order by item_key)
      from changes
      where previous_bodies is not null
        and current_bodies is not null
        and previous_bodies is distinct from current_bodies
    ), '[]'::jsonb),
    'added_count', (
      select count(*)::integer from changes where previous_bodies is null
    ),
    'removed_count', (
      select count(*)::integer from changes where current_bodies is null
    ),
    'changed_count', (
      select count(*)::integer
      from changes
      where previous_bodies is not null
        and current_bodies is not null
        and previous_bodies is distinct from current_bodies
    )
  )
$$;

create or replace function content_factory_private.research_trend_change_set(
  previous_value jsonb,
  current_value jsonb
)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  with modes as (
    select case
      when $1 ->> 'signal_catalog_version' = 'structural_v1'
       and $2 ->> 'signal_catalog_version' = 'structural_v1'
        then 'canonical'
      when ($1 ->> 'signal_catalog_version' = 'structural_v1')
        is distinct from
        ($2 ->> 'signal_catalog_version' = 'structural_v1')
        then 'canonical_reset'
      else 'legacy'
    end as comparison_mode
  ),
  previous_items as (
    select
      case
        when $1 ->> 'signal_catalog_version' = 'structural_v1'
          then 'canonical:' || btrim(item.value ->> 'signal_key')
        else 'legacy:' || content_factory_private.research_watchlist_key(
          item.value ->> 'signal'
        )
      end as item_key,
      min(btrim(item.value ->> 'signal')) as display_name,
      min(btrim(item.value ->> 'direction')) as direction,
      jsonb_agg(item.value order by item.value::text) as bodies
    from jsonb_array_elements(
      case
        when jsonb_typeof($1 -> 'signals') = 'array'
          then $1 -> 'signals'
        else '[]'::jsonb
      end
    ) item(value)
    where case
      when $1 ->> 'signal_catalog_version' = 'structural_v1'
        then coalesce(btrim(item.value ->> 'signal_key'), '') <> ''
      else content_factory_private.research_watchlist_key(
        item.value ->> 'signal'
      ) <> ''
    end
    group by case
      when $1 ->> 'signal_catalog_version' = 'structural_v1'
        then 'canonical:' || btrim(item.value ->> 'signal_key')
      else 'legacy:' || content_factory_private.research_watchlist_key(
        item.value ->> 'signal'
      )
    end
  ),
  current_items as (
    select
      case
        when $2 ->> 'signal_catalog_version' = 'structural_v1'
          then 'canonical:' || btrim(item.value ->> 'signal_key')
        else 'legacy:' || content_factory_private.research_watchlist_key(
          item.value ->> 'signal'
        )
      end as item_key,
      min(btrim(item.value ->> 'signal')) as display_name,
      min(btrim(item.value ->> 'direction')) as direction,
      jsonb_agg(item.value order by item.value::text) as bodies
    from jsonb_array_elements(
      case
        when jsonb_typeof($2 -> 'signals') = 'array'
          then $2 -> 'signals'
        else '[]'::jsonb
      end
    ) item(value)
    where case
      when $2 ->> 'signal_catalog_version' = 'structural_v1'
        then coalesce(btrim(item.value ->> 'signal_key'), '') <> ''
      else content_factory_private.research_watchlist_key(
        item.value ->> 'signal'
      ) <> ''
    end
    group by case
      when $2 ->> 'signal_catalog_version' = 'structural_v1'
        then 'canonical:' || btrim(item.value ->> 'signal_key')
      else 'legacy:' || content_factory_private.research_watchlist_key(
        item.value ->> 'signal'
      )
    end
  ),
  changes as (
    select
      coalesce(current_items.item_key, previous_items.item_key) as item_key,
      previous_items.display_name as previous_name,
      current_items.display_name as current_name,
      previous_items.direction as previous_direction,
      current_items.direction as current_direction,
      previous_items.bodies as previous_bodies,
      current_items.bodies as current_bodies,
      (
        previous_items.bodies is not null
        and current_items.bodies is not null
        and previous_items.direction is distinct from current_items.direction
      ) as direction_changed,
      (
        (previous_items.direction in ('emerging', 'growing')
          and current_items.direction = 'declining')
        or (previous_items.direction = 'declining'
          and current_items.direction in ('emerging', 'growing'))
      ) as is_contradiction
    from previous_items
    full join current_items using (item_key)
  )
  select jsonb_build_object(
    'comparison_mode', (select comparison_mode from modes),
    'as_of_from', $1 ->> 'as_of',
    'as_of_to', $2 ->> 'as_of',
    'added_signals', coalesce((
      select jsonb_agg(current_name order by item_key)
      from changes
      where previous_bodies is null
        and (select comparison_mode from modes) <> 'canonical_reset'
    ), '[]'::jsonb),
    'removed_signals', coalesce((
      select jsonb_agg(previous_name order by item_key)
      from changes
      where current_bodies is null
        and (select comparison_mode from modes) <> 'canonical_reset'
    ), '[]'::jsonb),
    'changed_signals', coalesce((
      select jsonb_agg(current_name order by item_key)
      from changes
      where previous_bodies is not null
        and current_bodies is not null
        and previous_bodies is distinct from current_bodies
        and (select comparison_mode from modes) <> 'canonical_reset'
    ), '[]'::jsonb),
    'direction_changes', coalesce((
      select jsonb_agg(jsonb_build_object(
        'signal', current_name,
        'from', previous_direction,
        'to', current_direction,
        'contradiction', is_contradiction
      ) order by item_key)
      from changes
      where direction_changed
        and (select comparison_mode from modes) <> 'canonical_reset'
    ), '[]'::jsonb),
    'direction_contradictions', coalesce((
      select jsonb_agg(jsonb_build_object(
        'signal', current_name,
        'from', previous_direction,
        'to', current_direction
      ) order by item_key)
      from changes
      where direction_changed and is_contradiction
        and (select comparison_mode from modes) <> 'canonical_reset'
    ), '[]'::jsonb),
    'added_count', (
      select count(*)::integer from changes
      where previous_bodies is null
        and (select comparison_mode from modes) <> 'canonical_reset'
    ),
    'removed_count', (
      select count(*)::integer from changes
      where current_bodies is null
        and (select comparison_mode from modes) <> 'canonical_reset'
    ),
    'changed_count', (
      select count(*)::integer
      from changes
      where previous_bodies is not null
        and current_bodies is not null
        and previous_bodies is distinct from current_bodies
        and (select comparison_mode from modes) <> 'canonical_reset'
    ),
    'contradiction_count', (
      select count(*)::integer
      from changes
      where direction_changed and is_contradiction
        and (select comparison_mode from modes) <> 'canonical_reset'
    )
  )
$$;

create or replace function content_factory_private.research_watchlist_change_set(
  previous_category jsonb,
  previous_competitors jsonb,
  previous_trends jsonb,
  previous_guidance jsonb,
  current_category jsonb,
  current_competitors jsonb,
  current_trends jsonb,
  current_guidance jsonb
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  baseline_value boolean := previous_category is null;
  competitors_value jsonb;
  trends_value jsonb;
  contradiction_count_value integer;
  has_changes_value boolean;
begin
  if baseline_value then
    return jsonb_build_object(
      'schema_version', 1,
      'baseline', true,
      'has_changes', false,
      'has_potential_contradiction', false,
      'contradiction_count', 0,
      'category', jsonb_build_object(
        'changed', false,
        'name_from', null,
        'name_to', current_category ->> 'category_name',
        'maturity_from', null,
        'maturity_to', current_category ->> 'maturity'
      ),
      'competitors', jsonb_build_object(
        'coverage_from', null,
        'coverage_to', current_competitors ->> 'coverage',
        'coverage_changed', false,
        'added_names', '[]'::jsonb,
        'removed_names', '[]'::jsonb,
        'changed_names', '[]'::jsonb,
        'added_count', 0,
        'removed_count', 0,
        'changed_count', 0
      ),
      'trends', jsonb_build_object(
        'as_of_from', null,
        'as_of_to', current_trends ->> 'as_of',
        'added_signals', '[]'::jsonb,
        'removed_signals', '[]'::jsonb,
        'changed_signals', '[]'::jsonb,
        'direction_changes', '[]'::jsonb,
        'direction_contradictions', '[]'::jsonb,
        'added_count', 0,
        'removed_count', 0,
        'changed_count', 0,
        'contradiction_count', 0
      ),
      'guidance', jsonb_build_object(
        'changed', false,
        'status_from', null,
        'status_to', current_guidance ->> 'status',
        'recommended_next_step_from', null,
        'recommended_next_step_to', current_guidance ->> 'recommended_next_step'
      )
    );
  end if;

  competitors_value :=
    content_factory_private.research_competitor_change_set(
      previous_competitors, current_competitors
    );
  trends_value := content_factory_private.research_trend_change_set(
    previous_trends, current_trends
  );
  contradiction_count_value :=
    coalesce((trends_value ->> 'contradiction_count')::integer, 0);
  has_changes_value :=
    previous_category is distinct from current_category
    or previous_competitors is distinct from current_competitors
    or previous_trends is distinct from current_trends
    or previous_guidance is distinct from current_guidance;

  return jsonb_build_object(
    'schema_version', 1,
    'baseline', false,
    'has_changes', has_changes_value,
    'has_potential_contradiction', contradiction_count_value > 0,
    'contradiction_count', contradiction_count_value,
    'category', jsonb_build_object(
      'changed', previous_category is distinct from current_category,
      'name_from', previous_category ->> 'category_name',
      'name_to', current_category ->> 'category_name',
      'maturity_from', previous_category ->> 'maturity',
      'maturity_to', current_category ->> 'maturity'
    ),
    'competitors', competitors_value,
    'trends', trends_value,
    'guidance', jsonb_build_object(
      'changed', previous_guidance is distinct from current_guidance,
      'status_from', previous_guidance ->> 'status',
      'status_to', current_guidance ->> 'status',
      'recommended_next_step_from',
        previous_guidance ->> 'recommended_next_step',
      'recommended_next_step_to',
        current_guidance ->> 'recommended_next_step'
    )
  );
end;
$$;

create or replace function content_factory_private.capture_research_watchlist_snapshot(
  watchlist_id_value uuid,
  draft_id_value uuid
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  watchlist_row content_factory.research_watchlists%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  previous_row content_factory.research_watchlist_snapshots%rowtype;
  snapshot_id_value uuid;
  canonical_source_ids jsonb;
  source_count integer;
  change_set_value jsonb;
  snapshot_hash_value text;
begin
  select watchlist.* into watchlist_row
  from content_factory.research_watchlists watchlist
  where watchlist.id = watchlist_id_value
  for update;
  if watchlist_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_watchlist_not_found';
  end if;

  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  join content_factory.product_research_runs run
    on run.organization_id = draft.organization_id
   and run.product_id = draft.product_id
   and run.id = draft.run_id
  where draft.organization_id = watchlist_row.organization_id
    and draft.product_id = watchlist_row.product_id
    and draft.id = draft_id_value
    and draft.status = 'approved'
    and draft.origin = 'human'
    and draft.approved_by is not null
    and draft.approved_at is not null
    and run.status = 'completed'
    and content_factory_private.research_brief_has_v2_sections(draft.brief);
  if draft_row.id is null then
    raise exception using
      errcode = '22023', message = 'approved_research_v2_draft_required';
  end if;

  canonical_source_ids :=
    content_factory_private.canonical_research_source_ids(draft_row.source_ids);
  if canonical_source_ids is null
     or jsonb_array_length(canonical_source_ids) not between 1 and 100 then
    raise exception using
      errcode = '42501', message = 'research_snapshot_evidence_mismatch';
  end if;

  select count(*)::integer into source_count
  from jsonb_array_elements_text(canonical_source_ids) source_ref(value)
  join content_factory.product_research_sources source
    on source.organization_id = watchlist_row.organization_id
   and source.run_id = draft_row.run_id
   and source.product_id = watchlist_row.product_id
   and source.id::text = source_ref.value;
  if source_count <> jsonb_array_length(canonical_source_ids) then
    raise exception using
      errcode = '42501', message = 'research_snapshot_evidence_mismatch';
  end if;

  select snapshot.id into snapshot_id_value
  from content_factory.research_watchlist_snapshots snapshot
  where snapshot.organization_id = watchlist_row.organization_id
    and snapshot.watchlist_id = watchlist_row.id
    and snapshot.draft_id = draft_row.id;
  if snapshot_id_value is not null then
    update content_factory.research_watchlists watchlist
    set next_refresh_at = case
          when watchlist.status = 'active' then
            draft_row.approved_at
              + make_interval(days => watchlist.refresh_interval_days)
          else null
        end,
        updated_by = watchlist_row.updated_by
    where watchlist.organization_id = watchlist_row.organization_id
      and watchlist.id = watchlist_row.id;
    return snapshot_id_value;
  end if;

  select snapshot.* into previous_row
  from content_factory.research_watchlist_snapshots snapshot
  where snapshot.organization_id = watchlist_row.organization_id
    and snapshot.watchlist_id = watchlist_row.id
  order by snapshot.snapshot_version desc
  limit 1;
  if previous_row.id is not null
     and draft_row.approved_at < previous_row.observed_at then
    raise exception using
      errcode = '22023', message = 'research_snapshot_temporal_regression';
  end if;

  change_set_value :=
    content_factory_private.research_watchlist_change_set(
      previous_row.category_analysis,
      previous_row.competitor_analysis,
      previous_row.trend_analysis,
      previous_row.guidance,
      draft_row.brief -> 'category_analysis',
      draft_row.brief -> 'competitor_analysis',
      draft_row.brief -> 'trend_analysis',
      draft_row.brief -> 'guidance'
    );
  snapshot_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'watchlist_id', watchlist_row.id,
    'run_id', draft_row.run_id,
    'draft_id', draft_row.id,
    'approved_at', draft_row.approved_at,
    'sections', content_factory_private.research_v2_sections(draft_row.brief),
    'source_ids', canonical_source_ids
  ));

  insert into content_factory.research_watchlist_snapshots (
    organization_id, product_id, watchlist_id, run_id, draft_id,
    previous_snapshot_id, snapshot_version, approved_by, observed_at,
    refresh_interval_days, category_analysis, competitor_analysis,
    trend_analysis, guidance, source_ids, source_ids_hash, snapshot_hash,
    change_set
  ) values (
    watchlist_row.organization_id,
    watchlist_row.product_id,
    watchlist_row.id,
    draft_row.run_id,
    draft_row.id,
    previous_row.id,
    coalesce(previous_row.snapshot_version, 0) + 1,
    draft_row.approved_by,
    draft_row.approved_at,
    watchlist_row.refresh_interval_days,
    draft_row.brief -> 'category_analysis',
    draft_row.brief -> 'competitor_analysis',
    draft_row.brief -> 'trend_analysis',
    draft_row.brief -> 'guidance',
    canonical_source_ids,
    content_factory_private.json_hash(canonical_source_ids),
    snapshot_hash_value,
    change_set_value
  ) returning id into snapshot_id_value;

  insert into content_factory.research_watchlist_snapshot_sources (
    organization_id, snapshot_id, run_id, source_id, ordinal
  )
  select
    watchlist_row.organization_id,
    snapshot_id_value,
    draft_row.run_id,
    source.id,
    source_ref.ordinality::integer
  from jsonb_array_elements_text(canonical_source_ids)
    with ordinality source_ref(value, ordinality)
  join content_factory.product_research_sources source
    on source.organization_id = watchlist_row.organization_id
   and source.run_id = draft_row.run_id
   and source.product_id = watchlist_row.product_id
   and source.id::text = source_ref.value
  order by source_ref.ordinality;

  update content_factory.research_refresh_proposals proposal
  set status = 'superseded',
      superseded_reason = 'snapshot_captured',
      superseded_at = now()
  where proposal.organization_id = watchlist_row.organization_id
    and proposal.watchlist_id = watchlist_row.id
    and proposal.status = 'open';

  update content_factory.research_watchlists watchlist
  set next_refresh_at = case
        when watchlist.status = 'active' then
          draft_row.approved_at
            + make_interval(days => watchlist.refresh_interval_days)
        else null
      end,
      updated_by = watchlist_row.updated_by
  where watchlist.organization_id = watchlist_row.organization_id
    and watchlist.id = watchlist_row.id;

  return snapshot_id_value;
end;
$$;

create or replace function content_factory_private.capture_research_watchlist_approval_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  watchlist_id_value uuid;
begin
  if old.status is distinct from new.status and new.status = 'approved' then
    select watchlist.id into watchlist_id_value
    from content_factory.research_watchlists watchlist
    where watchlist.organization_id = new.organization_id
      and watchlist.product_id = new.product_id
      and watchlist.status = 'active';
    if watchlist_id_value is not null then
      perform content_factory_private.capture_research_watchlist_snapshot(
        watchlist_id_value, new.id
      );
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists capture_research_watchlist_approved_snapshot
  on content_factory.creative_brief_drafts;
create trigger capture_research_watchlist_approved_snapshot
after update of status on content_factory.creative_brief_drafts
for each row execute function
  content_factory_private.capture_research_watchlist_approval_trigger();

create or replace function public.creator_configure_research_watchlist(
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
  product_id_value uuid;
  run_id_value uuid;
  draft_id_value uuid;
  action_value text;
  idempotency_key_value text;
  interval_days_value integer;
  interval_numeric numeric;
  request_payload jsonb;
  replay jsonb;
  watchlist_row content_factory.research_watchlists%rowtype;
  snapshot_id_value uuid;
  existing_snapshot_id uuid;
  watchlist_value jsonb;
  snapshot_value jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'run_id', 'action', 'refresh_interval_days',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_watchlist_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  action_value := content_factory_private.require_text(
    p_payload, 'action', 4, 10
  );
  if action_value not in ('enable', 'update', 'pause', 'resume') then
    raise exception using
      errcode = '22023', message = 'research_watchlist_action_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  if p_payload ? 'refresh_interval_days' then
    if jsonb_typeof(p_payload -> 'refresh_interval_days') <> 'number' then
      raise exception using
        errcode = '22023', message = 'refresh_interval_days_invalid';
    end if;
    begin
      interval_numeric := (p_payload ->> 'refresh_interval_days')::numeric;
    exception when others then
      raise exception using
        errcode = '22023', message = 'refresh_interval_days_invalid';
    end;
    if interval_numeric <> trunc(interval_numeric)
       or interval_numeric not between 3 and 90 then
      raise exception using
        errcode = '22023', message = 'refresh_interval_days_invalid';
    end if;
    interval_days_value := interval_numeric::integer;
  end if;

  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  select run.product_id
    into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = run.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where run.organization_id = organization_id
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer']
  );

  request_payload := p_payload - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_configure_research_watchlist',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('research-watchlist:' || product_id_value::text)
  );
  select watchlist.* into watchlist_row
  from content_factory.research_watchlists watchlist
  where watchlist.organization_id = organization_id
    and watchlist.product_id = product_id_value
  for update;

  if action_value <> 'pause' then
    select draft.id into draft_id_value
    from content_factory.creative_brief_drafts draft
    join content_factory.product_research_runs run
      on run.organization_id = draft.organization_id
     and run.product_id = draft.product_id
     and run.id = draft.run_id
    where draft.organization_id = organization_id
      and draft.product_id = product_id_value
      and draft.status = 'approved'
      and draft.origin = 'human'
      and draft.approved_by is not null
      and draft.approved_at is not null
      and run.status = 'completed'
      and content_factory_private.research_brief_has_v2_sections(draft.brief)
    order by draft.approved_at desc, draft.version desc, draft.id desc
    limit 1;
    if draft_id_value is null then
      raise exception using
        errcode = '22023', message = 'approved_research_v2_draft_required';
    end if;
  end if;

  if action_value = 'enable' then
    if watchlist_row.id is null then
      insert into content_factory.research_watchlists (
        organization_id, product_id, created_by, updated_by, status,
        refresh_interval_days, next_refresh_at
      ) values (
        organization_id, product_id_value, user_id, user_id, 'active',
        coalesce(interval_days_value, 14), now()
      ) returning * into watchlist_row;
    elsif watchlist_row.status = 'paused' then
      raise exception using
        errcode = '55000', message = 'research_watchlist_use_resume';
    else
      update content_factory.research_watchlists watchlist
      set refresh_interval_days = coalesce(
            interval_days_value, watchlist.refresh_interval_days
          ),
          updated_by = user_id
      where watchlist.organization_id = organization_id
        and watchlist.id = watchlist_row.id
      returning * into watchlist_row;
    end if;
  elsif action_value = 'update' then
    if watchlist_row.id is null then
      raise exception using
        errcode = '22023', message = 'research_watchlist_not_found';
    end if;
    update content_factory.research_watchlists watchlist
    set refresh_interval_days = coalesce(
          interval_days_value, watchlist.refresh_interval_days
        ),
        updated_by = user_id
    where watchlist.organization_id = organization_id
      and watchlist.id = watchlist_row.id
    returning * into watchlist_row;
  elsif action_value = 'pause' then
    if watchlist_row.id is null then
      raise exception using
        errcode = '22023', message = 'research_watchlist_not_found';
    end if;
    update content_factory.research_watchlists watchlist
    set status = 'paused',
        refresh_interval_days = coalesce(
          interval_days_value, watchlist.refresh_interval_days
        ),
        next_refresh_at = null,
        updated_by = user_id
    where watchlist.organization_id = organization_id
      and watchlist.id = watchlist_row.id
    returning * into watchlist_row;
    update content_factory.research_refresh_proposals proposal
    set status = 'superseded',
        superseded_reason = 'watchlist_paused',
        superseded_at = now()
    where proposal.organization_id = organization_id
      and proposal.watchlist_id = watchlist_row.id
      and proposal.status = 'open';
  else
    if watchlist_row.id is null then
      raise exception using
        errcode = '22023', message = 'research_watchlist_not_found';
    end if;
    update content_factory.research_watchlists watchlist
    set status = 'active',
        refresh_interval_days = coalesce(
          interval_days_value, watchlist.refresh_interval_days
        ),
        next_refresh_at = now(),
        updated_by = user_id
    where watchlist.organization_id = organization_id
      and watchlist.id = watchlist_row.id
    returning * into watchlist_row;
  end if;

  if action_value <> 'pause' then
    select snapshot.id into existing_snapshot_id
    from content_factory.research_watchlist_snapshots snapshot
    where snapshot.organization_id = organization_id
      and snapshot.watchlist_id = watchlist_row.id
      and snapshot.draft_id = draft_id_value;
    snapshot_id_value :=
      content_factory_private.capture_research_watchlist_snapshot(
        watchlist_row.id, draft_id_value
      );
    if existing_snapshot_id is not null
       and action_value in ('enable', 'update') then
      update content_factory.research_refresh_proposals proposal
      set status = 'superseded',
          superseded_reason = 'configuration_changed',
          superseded_at = now()
      where proposal.organization_id = organization_id
        and proposal.watchlist_id = watchlist_row.id
        and proposal.status = 'open';
    end if;
  end if;

  select jsonb_build_object(
    'id', watchlist.id,
    'product_id', watchlist.product_id,
    'status', watchlist.status,
    'refresh_interval_days', watchlist.refresh_interval_days,
    'next_refresh_at', watchlist.next_refresh_at,
    'created_at', watchlist.created_at,
    'updated_at', watchlist.updated_at
  ) into watchlist_value
  from content_factory.research_watchlists watchlist
  where watchlist.organization_id = organization_id
    and watchlist.id = watchlist_row.id;

  if snapshot_id_value is not null then
    select jsonb_build_object(
      'id', snapshot.id,
      'run_id', snapshot.run_id,
      'draft_id', snapshot.draft_id,
      'version', snapshot.snapshot_version,
      'observed_at', snapshot.observed_at,
      'change_set', snapshot.change_set
    ) into snapshot_value
    from content_factory.research_watchlist_snapshots snapshot
    where snapshot.organization_id = organization_id
      and snapshot.id = snapshot_id_value;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'watchlist', watchlist_value,
    'snapshot', snapshot_value
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'research_watchlist_configured',
    'research_watchlist',
    watchlist_row.id::text,
    jsonb_build_object(
      'action', action_value,
      'run_id', run_id_value,
      'snapshot_id', snapshot_id_value,
      'refresh_interval_days', watchlist_value -> 'refresh_interval_days'
    ),
    'research_watchlist:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_configure_research_watchlist',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_research_watchlist_status(
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
  product_id_value uuid;
  run_id_value uuid;
  watchlist_row content_factory.research_watchlists%rowtype;
  latest_snapshot content_factory.research_watchlist_snapshots%rowtype;
  proposal_row content_factory.research_refresh_proposals%rowtype;
  snapshots_value jsonb := '[]'::jsonb;
  snapshot_count_value integer := 0;
  watchlist_value jsonb;
  proposal_value jsonb;
  guidance_value jsonb;
  freshness_status_value text;
  fresh_until_value timestamptz;
  overdue_days_value integer := 0;
  contradiction_value boolean := false;
  recommendation_value text;
  reason_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_watchlist_status_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');

  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  select run.product_id
    into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = run.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where run.organization_id = organization_id
    and run.id = run_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );

  select watchlist.* into watchlist_row
  from content_factory.research_watchlists watchlist
  where watchlist.organization_id = organization_id
    and watchlist.product_id = product_id_value;
  if watchlist_row.id is null then
    guidance_value := jsonb_build_object(
      'paid_refresh_requires_confirmation', true,
      'status', 'disabled',
      'freshness_status', 'unknown',
      'potential_contradiction', false,
      'recommended_next_step', 'enable_watchlist',
      'reason', 'No research watchlist is configured for this product.'
    );
    return jsonb_build_object(
      'ok', true,
      'watchlist', null,
      'snapshots', snapshots_value,
      'proposal', null,
      'guidance', guidance_value
    );
  end if;

  select snapshot.* into latest_snapshot
  from content_factory.research_watchlist_snapshots snapshot
  where snapshot.organization_id = organization_id
    and snapshot.watchlist_id = watchlist_row.id
  order by snapshot.snapshot_version desc
  limit 1;

  select count(*)::integer into snapshot_count_value
  from content_factory.research_watchlist_snapshots snapshot
  where snapshot.organization_id = organization_id
    and snapshot.watchlist_id = watchlist_row.id;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', snapshot.id,
    'run_id', snapshot.run_id,
    'draft_id', snapshot.draft_id,
    'previous_snapshot_id', snapshot.previous_snapshot_id,
    'version', snapshot.snapshot_version,
    'approved_by', snapshot.approved_by,
    'observed_at', snapshot.observed_at,
    'refresh_interval_days', snapshot.refresh_interval_days,
    'category_analysis', snapshot.category_analysis,
    'competitor_analysis', snapshot.competitor_analysis,
    'trend_analysis', snapshot.trend_analysis,
    'guidance', snapshot.guidance,
    'source_ids', (
      select coalesce(jsonb_agg(source_link.source_id order by source_link.ordinal), '[]'::jsonb)
      from content_factory.research_watchlist_snapshot_sources source_link
      where source_link.organization_id = organization_id
        and source_link.snapshot_id = snapshot.id
    ),
    'source_ids_hash', snapshot.source_ids_hash,
    'snapshot_hash', snapshot.snapshot_hash,
    'change_set', snapshot.change_set,
    'created_at', snapshot.created_at
  ) order by snapshot.snapshot_version desc, snapshot.id desc), '[]'::jsonb)
    into snapshots_value
  from (
    select bounded_snapshot.*
    from content_factory.research_watchlist_snapshots bounded_snapshot
    where bounded_snapshot.organization_id = organization_id
      and bounded_snapshot.watchlist_id = watchlist_row.id
    order by bounded_snapshot.snapshot_version desc, bounded_snapshot.id desc
    limit 8
  ) snapshot;

  select proposal.* into proposal_row
  from content_factory.research_refresh_proposals proposal
  where proposal.organization_id = organization_id
    and proposal.watchlist_id = watchlist_row.id
    and proposal.status = 'open'
  order by proposal.created_at desc, proposal.id desc
  limit 1;
  if proposal_row.id is not null then
    proposal_value := jsonb_build_object(
      'id', proposal_row.id,
      'snapshot_id', proposal_row.snapshot_id,
      'due_at', proposal_row.due_at,
      'reason', proposal_row.reason,
      'status', proposal_row.status,
      'superseded_reason', proposal_row.superseded_reason,
      'superseded_at', proposal_row.superseded_at,
      'created_at', proposal_row.created_at
    );
  end if;

  if watchlist_row.status = 'paused' then
    freshness_status_value := 'paused';
  elsif latest_snapshot.id is null then
    freshness_status_value := 'unknown';
  else
    fresh_until_value := latest_snapshot.observed_at
      + make_interval(days => watchlist_row.refresh_interval_days);
    if fresh_until_value <= now() then
      freshness_status_value := 'stale';
      overdue_days_value := greatest(
        0,
        floor(extract(epoch from (now() - fresh_until_value)) / 86400)::integer
      );
    else
      freshness_status_value := 'fresh';
    end if;
    contradiction_value := coalesce(
      (latest_snapshot.change_set ->> 'has_potential_contradiction')::boolean,
      false
    );
  end if;

  watchlist_value := jsonb_build_object(
    'id', watchlist_row.id,
    'product_id', watchlist_row.product_id,
    'status', watchlist_row.status,
    'refresh_interval_days', watchlist_row.refresh_interval_days,
    'next_refresh_at', watchlist_row.next_refresh_at,
    'last_snapshot_at', latest_snapshot.observed_at,
    'snapshot_count', snapshot_count_value,
    'version', latest_snapshot.snapshot_version,
    'created_at', watchlist_row.created_at,
    'updated_at', watchlist_row.updated_at,
    'freshness', jsonb_build_object(
      'status', freshness_status_value,
      'latest_snapshot_id', latest_snapshot.id,
      'observed_at', latest_snapshot.observed_at,
      'fresh_until', fresh_until_value,
      'overdue_days', overdue_days_value
    )
  );

  if contradiction_value then
    recommendation_value := 'review_change_set';
    reason_value :=
      'The latest approved snapshot reverses at least one tracked trend direction.';
  elsif watchlist_row.status = 'paused' then
    recommendation_value := 'resume_when_ready';
    reason_value := 'Automatic freshness proposals are paused for this product.';
  elsif proposal_row.id is not null and proposal_row.status = 'open' then
    recommendation_value := 'confirm_paid_refresh';
    reason_value :=
      'Research is due; starting a paid refresh still requires explicit confirmation.';
  elsif freshness_status_value = 'stale' then
    recommendation_value := 'await_refresh_proposal';
    reason_value :=
      'The approved research is stale and is eligible for a provider-free proposal.';
  elsif freshness_status_value = 'fresh' then
    recommendation_value := 'continue_with_approved_research';
    reason_value := 'The latest approved research snapshot is still fresh.';
  else
    recommendation_value := 'approve_research_v2';
    reason_value := 'An approved v2 snapshot is required before freshness can be tracked.';
  end if;

  guidance_value := jsonb_build_object(
    'paid_refresh_requires_confirmation', true,
    'status', case
      when contradiction_value then 'review_required'
      when watchlist_row.status = 'paused' then 'paused'
      when freshness_status_value = 'stale' then 'refresh_due'
      when freshness_status_value = 'fresh' then 'ready'
      else 'needs_approved_snapshot'
    end,
    'freshness_status', freshness_status_value,
    'potential_contradiction', contradiction_value,
    'recommended_next_step', recommendation_value,
    'reason', reason_value
  );

  return jsonb_build_object(
    'ok', true,
    'watchlist', watchlist_value,
    'snapshots', snapshots_value,
    'proposal', proposal_value,
    'guidance', guidance_value
  );
end;
$$;

create or replace function public.system_propose_due_research_refreshes(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  limit_value integer := 50;
  limit_numeric numeric;
  selected_value integer := 0;
  created_value integer := 0;
  existing_value integer := 0;
  due_value integer := 0;
  notified_value integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'research_refresh_proposal_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number' then
      raise exception using
        errcode = '22023', message = 'research_refresh_proposal_limit_invalid';
    end if;
    begin
      limit_numeric := (p_payload ->> 'limit')::numeric;
    exception when others then
      raise exception using
        errcode = '22023', message = 'research_refresh_proposal_limit_invalid';
    end;
    if limit_numeric <> trunc(limit_numeric)
       or limit_numeric not between 1 and 100 then
      raise exception using
        errcode = '22023', message = 'research_refresh_proposal_limit_invalid';
    end if;
    limit_value := limit_numeric::integer;
  end if;

  with due_candidates as materialized (
    select
      watchlist.organization_id,
      watchlist.id as watchlist_id,
      latest_snapshot.id as snapshot_id,
      watchlist.next_refresh_at as due_at,
      content_factory_private.json_hash(jsonb_build_object(
        'watchlist_id', watchlist.id,
        'snapshot_id', latest_snapshot.id,
        'due_at', watchlist.next_refresh_at,
        'configuration_at', watchlist.updated_at,
        'previous_proposal_id', (
          select previous_proposal.id
          from content_factory.research_refresh_proposals previous_proposal
          where previous_proposal.organization_id = watchlist.organization_id
            and previous_proposal.watchlist_id = watchlist.id
          order by previous_proposal.created_at desc, previous_proposal.id desc
          limit 1
        )
      )) as proposal_hash
    from content_factory.research_watchlists watchlist
    join lateral (
      select snapshot.id
      from content_factory.research_watchlist_snapshots snapshot
      where snapshot.organization_id = watchlist.organization_id
        and snapshot.watchlist_id = watchlist.id
      order by snapshot.snapshot_version desc
      limit 1
    ) latest_snapshot on true
    where watchlist.status = 'active'
      and watchlist.next_refresh_at <= now()
    order by watchlist.next_refresh_at, watchlist.created_at, watchlist.id
    limit limit_value
    for update of watchlist skip locked
  ),
  inserted as (
    insert into content_factory.research_refresh_proposals (
      organization_id, watchlist_id, snapshot_id, due_at,
      reason, status, proposal_hash
    )
    select
      candidate.organization_id,
      candidate.watchlist_id,
      candidate.snapshot_id,
      candidate.due_at,
      'scheduled_due',
      'open',
      candidate.proposal_hash
    from due_candidates candidate
    where not exists (
      select 1
      from content_factory.research_refresh_proposals proposal
      where proposal.organization_id = candidate.organization_id
        and proposal.watchlist_id = candidate.watchlist_id
        and proposal.status = 'open'
    )
    on conflict do nothing
    returning id, organization_id, watchlist_id, snapshot_id, due_at
  ),
  notifications_inserted as (
    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    )
    select
      inserted.organization_id,
      watchlist.created_by,
      'research_refresh_due',
      'warning',
      'Исследование пора обновить',
      'Данные по категории, конкурентам и трендам устарели. Откройте исследование и подтвердите платное обновление вручную.',
      '#/workspace/research?research=' || snapshot.run_id::text,
      'research_refresh_proposal',
      inserted.id::text,
      notice.properties,
      content_factory_private.json_hash(jsonb_build_object(
        'recipient_id', watchlist.created_by,
        'kind', 'research_refresh_due',
        'severity', 'warning',
        'title', 'Исследование пора обновить',
        'body', 'Данные по категории, конкурентам и трендам устарели. Откройте исследование и подтвердите платное обновление вручную.',
        'deep_link', '#/workspace/research?research=' || snapshot.run_id::text,
        'entity_type', 'research_refresh_proposal',
        'entity_id', inserted.id,
        'properties', notice.properties
      )),
      left('research-refresh-due:' || inserted.id::text, 180)
    from inserted
    join content_factory.research_watchlists watchlist
      on watchlist.organization_id = inserted.organization_id
     and watchlist.id = inserted.watchlist_id
    join content_factory.research_watchlist_snapshots snapshot
      on snapshot.organization_id = inserted.organization_id
     and snapshot.watchlist_id = inserted.watchlist_id
     and snapshot.id = inserted.snapshot_id
    join content_factory.organizations organization
      on organization.id = inserted.organization_id
     and organization.status = 'active'
    join content_factory.memberships membership
      on membership.organization_id = inserted.organization_id
     and membership.profile_id = watchlist.created_by
     and membership.status = 'active'
    join content_factory.profiles profile
      on profile.id = watchlist.created_by
     and profile.status = 'active'
    cross join lateral (
      select jsonb_build_object(
        'source', 'research_watchlist_scheduler',
        'watchlist_id', inserted.watchlist_id,
        'snapshot_id', inserted.snapshot_id,
        'run_id', snapshot.run_id,
        'proposal_id', inserted.id,
        'due_at', inserted.due_at,
        'paid_refresh_requires_confirmation', true,
        'auto_spend', false
      ) as properties
    ) notice
    on conflict (organization_id, recipient_id, dedupe_key) do nothing
    returning id
  )
  select
    (select count(*)::integer from due_candidates),
    (select count(*)::integer from inserted),
    (select count(*)::integer from notifications_inserted)
    into selected_value, created_value, notified_value;

  existing_value := greatest(0, selected_value - created_value);
  due_value := greatest(0, selected_value);
  return jsonb_build_object(
    'ok', true,
    'selected', greatest(0, selected_value),
    'created', greatest(0, created_value),
    'existing', existing_value,
    'due', due_value
  );
end;
$$;

revoke all on function public.creator_configure_research_watchlist(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_research_watchlist_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.system_propose_due_research_refreshes(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_configure_research_watchlist(jsonb)
  to authenticated;
grant execute on function public.creator_research_watchlist_status(jsonb)
  to authenticated;
grant execute on function public.system_propose_due_research_refreshes(jsonb)
  to service_role;

revoke all on function
  content_factory_private.reject_research_watchlist_memory_mutation()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_research_watchlist()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_research_refresh_proposal()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.research_watchlist_key(text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_competitor_change_set(jsonb, jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_trend_change_set(jsonb, jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_watchlist_change_set(
    jsonb, jsonb, jsonb, jsonb, jsonb, jsonb, jsonb, jsonb
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_watchlist_snapshot(uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_research_watchlist_approval_trigger()
  from public, anon, authenticated, service_role;

select pg_notify('pgrst', 'reload schema');

commit;

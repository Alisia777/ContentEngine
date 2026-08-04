begin;

-- AI learning is intentionally limited to the same immutable category and
-- creative-angle vocabularies used by paid generation.  Uploaded text and
-- operator notes are evidence metadata only; neither can become a prompt rule.

create sequence if not exists content_factory.ai_learning_event_cursor_seq;
revoke all on sequence content_factory.ai_learning_event_cursor_seq
  from public, anon, authenticated;
grant usage, select on sequence content_factory.ai_learning_event_cursor_seq
  to service_role;

create table if not exists content_factory.ai_category_knowledge_sources (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    source_kind text not null check (source_kind in ('file', 'link')),
    owner_id uuid not null,
    title text not null check (length(btrim(title)) between 2 and 180),
    note text check (note is null or length(note) <= 1000),
    bucket_id text,
    object_name text,
    original_filename text,
    mime_type text,
    size_bytes bigint,
    sha256 text,
    source_url text,
    rights_confirmed boolean not null check (rights_confirmed),
    status text not null default 'active' check (status = 'active'),
    source_hash text not null check (source_hash ~ '^[0-9a-f]{64}$'),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    event_cursor bigint not null default nextval(
      'content_factory.ai_learning_event_cursor_seq'::regclass
    ) check (event_cursor > 0),
    created_at timestamptz not null default now(),
    foreign key (organization_id, owner_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (event_cursor),
    check (
      (
        source_kind = 'file'
        and bucket_id = 'contentengine-knowledge'
        and object_name is not null
        and original_filename is not null
        and mime_type in (
          'application/pdf',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'text/csv', 'text/markdown', 'text/plain'
        )
        and size_bytes between 1 and 26214400
        and sha256 ~ '^[0-9a-f]{64}$'
        and source_url is null
      )
      or
      (
        source_kind = 'link'
        and source_url is not null
        and length(source_url) between 12 and 2048
        and bucket_id is null
        and object_name is null
        and original_filename is null
        and mime_type is null
        and size_bytes is null
        and sha256 is null
      )
    )
);

create unique index if not exists ai_knowledge_file_object_uq
  on content_factory.ai_category_knowledge_sources (bucket_id, object_name)
  where source_kind = 'file';
create unique index if not exists ai_knowledge_link_scope_uq
  on content_factory.ai_category_knowledge_sources (
    organization_id, product_category, source_url
  ) where source_kind = 'link';
create index if not exists ai_knowledge_category_page_idx
  on content_factory.ai_category_knowledge_sources (
    organization_id, product_category, event_cursor desc
  );

comment on column content_factory.ai_category_knowledge_sources.sha256 is
  'Client-calculated SHA-256 declaration; not server-recomputed and not authoritative content verification.';

-- The catalogue is global and sealed from browser writes.  A future wording
-- change is a new version, never an in-place edit.  Only the six structural
-- creative angles can be represented by a card.
create table if not exists content_factory.ai_teaching_card_catalog (
    id uuid primary key default extensions.gen_random_uuid(),
    code text not null check (
      code = 'creative_angle.' || creative_angle || '.' || ai_judgement
    ),
    version integer not null check (version between 1 and 1000000),
    card_hash text not null check (card_hash ~ '^[0-9a-f]{64}$'),
    creative_angle text not null check (creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    ai_judgement text not null check (ai_judgement in ('good', 'bad')),
    title text not null check (length(title) between 3 and 240),
    explanation text not null check (length(explanation) between 3 and 800),
    status text not null default 'active' check (status in ('active', 'retired')),
    created_at timestamptz not null default now(),
    unique (code, version),
    unique (creative_angle, ai_judgement, version),
    unique (card_hash)
);

insert into content_factory.ai_teaching_card_catalog (
  code, version, card_hash, creative_angle, ai_judgement,
  title, explanation
)
select
  seed.code,
  1,
  content_factory_private.json_hash(jsonb_build_object(
    'code', seed.code,
    'version', 1,
    'creative_angle', seed.creative_angle,
    'ai_judgement', seed.ai_judgement,
    'title', seed.title,
    'explanation', seed.explanation
  )),
  seed.creative_angle,
  seed.ai_judgement,
  seed.title,
  seed.explanation
from (values
  ('creative_angle.product_focus.good', 'product_focus', 'good',
   'Use product focus in this category',
   'The product remains the primary visual and narrative subject.'),
  ('creative_angle.product_focus.bad', 'product_focus', 'bad',
   'Avoid product focus in this category',
   'Product-first composition should be treated as a category anti-pattern.'),
  ('creative_angle.trust_builder.good', 'trust_builder', 'good',
   'Use trust building in this category',
   'Prefer verifiable presentation that reduces uncertainty.'),
  ('creative_angle.trust_builder.bad', 'trust_builder', 'bad',
   'Avoid trust building in this category',
   'Trust-building composition should be treated as a category anti-pattern.'),
  ('creative_angle.demonstration.good', 'demonstration', 'good',
   'Use demonstration in this category',
   'Prefer showing a bounded, visible product action.'),
  ('creative_angle.demonstration.bad', 'demonstration', 'bad',
   'Avoid demonstration in this category',
   'Demonstration composition should be treated as a category anti-pattern.'),
  ('creative_angle.comparison.good', 'comparison', 'good',
   'Use comparison in this category',
   'Prefer a factual, bounded comparison structure.'),
  ('creative_angle.comparison.bad', 'comparison', 'bad',
   'Avoid comparison in this category',
   'Comparison composition should be treated as a category anti-pattern.'),
  ('creative_angle.objection_handling.good', 'objection_handling', 'good',
   'Use objection handling in this category',
   'Prefer addressing one verifiable category objection.'),
  ('creative_angle.objection_handling.bad', 'objection_handling', 'bad',
   'Avoid objection handling in this category',
   'Objection-handling composition should be treated as a category anti-pattern.'),
  ('creative_angle.curiosity_gap.good', 'curiosity_gap', 'good',
   'Use curiosity gap in this category',
   'Prefer a bounded open question without unsupported claims.'),
  ('creative_angle.curiosity_gap.bad', 'curiosity_gap', 'bad',
   'Avoid curiosity gap in this category',
   'Curiosity-gap composition should be treated as a category anti-pattern.')
) as seed(code, creative_angle, ai_judgement, title, explanation)
on conflict (code, version) do nothing;

create table if not exists content_factory.ai_teaching_card_decisions (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    card_id uuid not null
      references content_factory.ai_teaching_card_catalog(id),
    card_version integer not null check (card_version between 1 and 1000000),
    card_hash text not null check (card_hash ~ '^[0-9a-f]{64}$'),
    decision text not null check (decision in ('approve', 'reject')),
    reason_code text not null check (reason_code in (
      'operator_confirmed', 'operator_rejected'
    )),
    confirmation boolean not null check (confirmation),
    expected_scope_version integer not null check (expected_scope_version >= 0),
    resulting_scope_version integer not null check (
      resulting_scope_version = expected_scope_version + 1
    ),
    decided_by uuid not null,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    event_cursor bigint not null default nextval(
      'content_factory.ai_learning_event_cursor_seq'::regclass
    ) check (event_cursor > 0),
    created_at timestamptz not null default now(),
    foreign key (organization_id, decided_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, product_category, id),
    unique (event_cursor)
);

create index if not exists ai_teaching_decision_scope_page_idx
  on content_factory.ai_teaching_card_decisions (
    organization_id, product_category, event_cursor desc
  );
create index if not exists ai_teaching_decision_card_head_idx
  on content_factory.ai_teaching_card_decisions (
    organization_id, product_category, card_id, event_cursor desc
  );

create table if not exists content_factory.ai_effective_category_policies (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    product_category text not null check (product_category in (
      'cosmetics', 'baa', 'sports_food', 'food', 'household',
      'apparel', 'electronics', 'other'
    )),
    scope_version integer not null check (scope_version > 0),
    preferred_creative_angle text check (preferred_creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    avoid_creative_angle text check (avoid_creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    positive_decision_id uuid,
    negative_decision_id uuid,
    source_decision_id uuid not null,
    policy_hash text not null check (policy_hash ~ '^[0-9a-f]{64}$'),
    created_by uuid not null,
    event_cursor bigint not null default nextval(
      'content_factory.ai_learning_event_cursor_seq'::regclass
    ) check (event_cursor > 0),
    created_at timestamptz not null default now(),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, product_category, positive_decision_id)
      references content_factory.ai_teaching_card_decisions(
        organization_id, product_category, id
      ),
    foreign key (organization_id, product_category, negative_decision_id)
      references content_factory.ai_teaching_card_decisions(
        organization_id, product_category, id
      ),
    foreign key (organization_id, product_category, source_decision_id)
      references content_factory.ai_teaching_card_decisions(
        organization_id, product_category, id
      ),
    unique (organization_id, product_category, scope_version),
    unique (organization_id, product_category, policy_hash),
    unique (event_cursor),
    check (
      preferred_creative_angle is null
      or avoid_creative_angle is null
      or preferred_creative_angle <> avoid_creative_angle
    )
);

create index if not exists ai_effective_policy_scope_head_idx
  on content_factory.ai_effective_category_policies (
    organization_id, product_category, scope_version desc
  );

alter table content_factory.ai_category_knowledge_sources enable row level security;
alter table content_factory.ai_teaching_card_catalog enable row level security;
alter table content_factory.ai_teaching_card_decisions enable row level security;
alter table content_factory.ai_effective_category_policies enable row level security;

revoke all on content_factory.ai_category_knowledge_sources
  from public, anon, authenticated;
revoke all on content_factory.ai_teaching_card_catalog
  from public, anon, authenticated;
revoke all on content_factory.ai_teaching_card_decisions
  from public, anon, authenticated;
revoke all on content_factory.ai_effective_category_policies
  from public, anon, authenticated;
grant all on content_factory.ai_category_knowledge_sources to service_role;
grant all on content_factory.ai_teaching_card_catalog to service_role;
grant all on content_factory.ai_teaching_card_decisions to service_role;
grant all on content_factory.ai_effective_category_policies to service_role;

create or replace function content_factory_private.guard_ai_learning_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'ai_learning_append_only';
end;
$$;

revoke all on function content_factory_private.guard_ai_learning_append_only()
  from public, anon, authenticated, service_role;

drop trigger if exists ai_knowledge_source_append_only
  on content_factory.ai_category_knowledge_sources;
create trigger ai_knowledge_source_append_only
before update or delete on content_factory.ai_category_knowledge_sources
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

drop trigger if exists ai_teaching_card_catalog_append_only
  on content_factory.ai_teaching_card_catalog;
create trigger ai_teaching_card_catalog_append_only
before update or delete on content_factory.ai_teaching_card_catalog
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

drop trigger if exists ai_teaching_card_decision_append_only
  on content_factory.ai_teaching_card_decisions;
create trigger ai_teaching_card_decision_append_only
before update or delete on content_factory.ai_teaching_card_decisions
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

drop trigger if exists ai_effective_category_policy_append_only
  on content_factory.ai_effective_category_policies;
create trigger ai_effective_category_policy_append_only
before update or delete on content_factory.ai_effective_category_policies
for each row execute function
  content_factory_private.guard_ai_learning_append_only();

-- Knowledge uploads use a separate private bucket.  Owner reads and writes
-- deliberately delegate to the currently installed waiver-aware
-- storage_access_allowed predicate.
insert into storage.buckets (
  id, name, public, file_size_limit, allowed_mime_types
)
values (
  'contentengine-knowledge',
  'contentengine-knowledge',
  false,
  26214400,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/csv', 'text/markdown', 'text/plain'
  ]::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- The shared storage gate intentionally includes waiver-aware reviewer and
-- operator paths.  Knowledge mutations are narrower: they must match the RPC
-- role contract even when the shared gate grants access.
create or replace function content_factory.ai_knowledge_storage_role_allowed(
  p_organization_id text,
  p_owner_id text
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select
    auth.uid() is not null
    and p_owner_id = auth.uid()::text
    and exists (
      select 1
      from content_factory.memberships membership
      join content_factory.profiles profile
        on profile.id = membership.profile_id
       and profile.status = 'active'
      join content_factory.organizations organization
        on organization.id = membership.organization_id
       and organization.status = 'active'
      where membership.profile_id = auth.uid()
        and membership.status = 'active'
        and membership.organization_id::text = p_organization_id
        and membership.role in ('owner', 'admin', 'producer')
    )
$$;

revoke all on function
  content_factory.ai_knowledge_storage_role_allowed(text, text)
  from public, anon;
grant execute on function
  content_factory.ai_knowledge_storage_role_allowed(text, text)
  to authenticated;

create or replace function content_factory.ai_knowledge_object_is_unregistered(
  p_bucket_id text,
  p_object_name text
)
returns boolean
language plpgsql
security definer
volatile
set search_path = ''
as $$
begin
  if auth.uid() is null
     or p_bucket_id <> 'contentengine-knowledge'
     or split_part(p_object_name, '/', 2) <> auth.uid()::text then
    return false;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(p_bucket_id),
    hashtext(p_object_name)
  );

  return not exists (
    select 1
    from content_factory.ai_category_knowledge_sources source
    where source.bucket_id = p_bucket_id
      and source.object_name = p_object_name
  );
end;
$$;

revoke all on function
  content_factory.ai_knowledge_object_is_unregistered(text, text)
  from public, anon;
grant execute on function
  content_factory.ai_knowledge_object_is_unregistered(text, text)
  to authenticated;

drop policy if exists contentengine_knowledge_select on storage.objects;
create policy contentengine_knowledge_select
on storage.objects
for select
to authenticated
using (
  bucket_id = 'contentengine-knowledge'
  and split_part(storage.objects.name, '/', 3) = 'ai-knowledge'
  and split_part(storage.objects.name, '/', 4) <> ''
  and storage.objects.name !~ '(^|/)\.\.(/|$)'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
);

drop policy if exists contentengine_knowledge_insert on storage.objects;
create policy contentengine_knowledge_insert
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'contentengine-knowledge'
  and split_part(storage.objects.name, '/', 3) = 'ai-knowledge'
  and split_part(storage.objects.name, '/', 4) <> ''
  and storage.objects.name !~ '(^|/)\.\.(/|$)'
  and position(chr(92) in storage.objects.name) = 0
  and content_factory.ai_knowledge_storage_role_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2)
  )
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
);

drop policy if exists contentengine_knowledge_update on storage.objects;

drop policy if exists contentengine_knowledge_delete on storage.objects;
create policy contentengine_knowledge_delete
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'contentengine-knowledge'
  and split_part(storage.objects.name, '/', 3) = 'ai-knowledge'
  and split_part(storage.objects.name, '/', 4) <> ''
  and content_factory.ai_knowledge_storage_role_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2)
  )
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
  and content_factory.ai_knowledge_object_is_unregistered(
    storage.objects.bucket_id,
    storage.objects.name
  )
);

create or replace function content_factory_private.require_ai_product_category(
  p_category text
)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  category_value text := lower(btrim(coalesce(p_category, '')));
begin
  if category_value not in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_learning_category_invalid';
  end if;
  return category_value;
end;
$$;

revoke all on function
  content_factory_private.require_ai_product_category(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_category_evidence_readiness(
    p_organization_id uuid,
    p_product_category text
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  source_count_value integer := 0;
  host_count_value integer := 0;
  recent_link_count_value integer := 0;
  structured_source_count_value integer := 0;
  human_validation_count_value integer := 0;
  policy_signal_count_value integer := 0;
  scope_version_value integer := 0;
  source_volume_score integer := 0;
  platform_diversity_score integer := 0;
  competitor_score integer := 0;
  trend_score integer := 0;
  analysis_score integer := 0;
  validation_score integer := 0;
  readiness_score_value integer := 0;
  readiness_status_value text;
  evidence_hash_value text;
  dimensions_value jsonb;
  gaps_value jsonb;
begin
  select
    count(*)::integer,
    count(distinct case
      when source.source_kind = 'link' then lower(split_part(
        split_part(substring(source.source_url from 9), '/', 1), ':', 1
      ))
    end)::integer,
    count(*) filter (
      where source.source_kind = 'link'
        and source.created_at >= now() - interval '90 days'
    )::integer,
    count(*) filter (
      where source.status = 'active'
        and source.source_hash ~ '^[0-9a-f]{64}$'
    )::integer
  into
    source_count_value,
    host_count_value,
    recent_link_count_value,
    structured_source_count_value
  from content_factory.ai_category_knowledge_sources source
  where source.organization_id = p_organization_id
    and source.product_category = category_value;

  with current_cards as (
    select distinct on (card.code)
      card.id,
      card.code
    from content_factory.ai_teaching_card_catalog card
    order by card.code, card.version desc, card.created_at desc, card.id desc
  ),
  heads as (
    select distinct on (current_card.code)
      current_card.code,
      decision.id
    from current_cards current_card
    join content_factory.ai_teaching_card_decisions decision
      on decision.card_id = current_card.id
     and decision.organization_id = p_organization_id
     and decision.product_category = category_value
    order by current_card.code, decision.event_cursor desc
  )
  select count(*)::integer
  into human_validation_count_value
  from heads;

  select
    policy.scope_version,
    (case when policy.preferred_creative_angle is null then 0 else 1 end
     + case when policy.avoid_creative_angle is null then 0 else 1 end)::integer
  into scope_version_value, policy_signal_count_value
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = p_organization_id
    and policy.product_category = category_value
  order by policy.scope_version desc
  limit 1;

  scope_version_value := coalesce(scope_version_value, 0);
  policy_signal_count_value := coalesce(policy_signal_count_value, 0);

  source_volume_score := least(100, floor(
    least(source_count_value, 12)::numeric * 100 / 12
  )::integer);
  platform_diversity_score := least(100, floor(
    least(host_count_value, 3)::numeric * 100 / 3
  )::integer);
  -- A registration alone cannot truthfully classify competitor evidence.
  competitor_score := 0;
  trend_score := least(100, floor(
    least(recent_link_count_value, 6)::numeric * 100 / 6
  )::integer);
  analysis_score := least(100, floor(
    least(structured_source_count_value, 8)::numeric * 100 / 8
  )::integer);
  validation_score := least(100, floor(
    least(human_validation_count_value, 4)::numeric * 100 / 4
  )::integer);

  readiness_score_value :=
      floor(20 * source_volume_score::numeric / 100)::integer
    + floor(15 * platform_diversity_score::numeric / 100)::integer
    + floor(20 * competitor_score::numeric / 100)::integer
    + floor(15 * trend_score::numeric / 100)::integer
    + floor(15 * analysis_score::numeric / 100)::integer
    + floor(15 * validation_score::numeric / 100)::integer;

  readiness_status_value := case
    when source_count_value = 0 and human_validation_count_value = 0
      then 'cold_start'
    when readiness_score_value >= 75 then 'strong_evidence'
    when readiness_score_value >= 35 then 'developing_evidence'
    else 'insufficient_evidence'
  end;

  dimensions_value := jsonb_build_array(
    jsonb_build_object(
      'key', 'source_volume', 'weight', 20,
      'current', source_count_value, 'target', 12,
      'score', source_volume_score,
      'weighted_points', floor(20 * source_volume_score::numeric / 100)::integer,
      'missing', greatest(0, 12 - source_count_value),
      'next_action', 'Добавьте проверяемый файл или HTTPS-ссылку'
    ),
    jsonb_build_object(
      'key', 'platform_diversity', 'weight', 15,
      'current', host_count_value, 'target', 3,
      'score', platform_diversity_score,
      'weighted_points', floor(15 * platform_diversity_score::numeric / 100)::integer,
      'missing', greatest(0, 3 - host_count_value),
      'next_action', 'Добавьте источники с независимых площадок'
    ),
    jsonb_build_object(
      'key', 'competitor_observations', 'weight', 20,
      'current', 0, 'target', 5, 'score', competitor_score,
      'weighted_points', 0, 'missing', 5,
      'next_action', 'Добавьте проверяемые наблюдения о конкурентах'
    ),
    jsonb_build_object(
      'key', 'trend_recency', 'weight', 15,
      'current', recent_link_count_value, 'target', 6,
      'score', trend_score,
      'weighted_points', floor(15 * trend_score::numeric / 100)::integer,
      'missing', greatest(0, 6 - recent_link_count_value),
      'next_action', 'Обновите свежие ссылки категории'
    ),
    jsonb_build_object(
      'key', 'analysis_coverage', 'weight', 15,
      'current', structured_source_count_value, 'target', 8,
      'score', analysis_score,
      'weighted_points', floor(15 * analysis_score::numeric / 100)::integer,
      'missing', greatest(0, 8 - structured_source_count_value),
      'next_action', 'Добавьте источники с проверенной структурной метаинформацией'
    ),
    jsonb_build_object(
      'key', 'human_validation', 'weight', 15,
      'current', human_validation_count_value, 'target', 4,
      'score', validation_score,
      'weighted_points', floor(15 * validation_score::numeric / 100)::integer,
      'missing', greatest(0, 4 - human_validation_count_value),
      'next_action', 'Подтвердите или отклоните карточки обучения'
    )
  );

  select coalesce(jsonb_agg(jsonb_build_object(
    'key', dimension ->> 'key',
    'missing', (dimension ->> 'missing')::integer,
    'next_action', dimension ->> 'next_action',
    'priority', case
      when (dimension ->> 'missing')::integer >= 3 then 'high'
      else 'normal'
    end
  ) order by ordinal), '[]'::jsonb)
  into gaps_value
  from jsonb_array_elements(dimensions_value) with ordinality
    as item(dimension, ordinal)
  where (dimension ->> 'missing')::integer > 0;

  evidence_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'product_category', category_value,
    'sources', coalesce((
      select jsonb_agg(jsonb_build_object(
        'source_hash', source.source_hash,
        'event_cursor', source.event_cursor
      ) order by source.event_cursor)
      from content_factory.ai_category_knowledge_sources source
      where source.organization_id = p_organization_id
        and source.product_category = category_value
    ), '[]'::jsonb),
    'decisions', coalesce((
      select jsonb_agg(jsonb_build_object(
        'decision_hash', decision.decision_hash,
        'event_cursor', decision.event_cursor
      ) order by decision.event_cursor)
      from content_factory.ai_teaching_card_decisions decision
      where decision.organization_id = p_organization_id
        and decision.product_category = category_value
    ), '[]'::jsonb),
    'effective_policy_hash', (
      select policy.policy_hash
      from content_factory.ai_effective_category_policies policy
      where policy.organization_id = p_organization_id
        and policy.product_category = category_value
      order by policy.scope_version desc
      limit 1
    )
  ));

  return jsonb_build_object(
    'metric_kind', 'category_evidence_readiness_not_model_iq',
    'is_ai_iq', false,
    'is_quality_guarantee', false,
    'score', readiness_score_value,
    'status', readiness_status_value,
    'dimensions', dimensions_value,
    'gaps', gaps_value,
    'evidence_hash', evidence_hash_value,
    'source_count', source_count_value,
    'evidence_count', source_count_value + human_validation_count_value,
    'human_validation_count', human_validation_count_value,
    'pending_teaching_count', greatest(0, 12 - human_validation_count_value),
    'policy_signal_count', policy_signal_count_value,
    'scope_version', scope_version_value
  );
end;
$$;

revoke all on function
  content_factory_private.ai_category_evidence_readiness(uuid, text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_learning_control_room_snapshot(
    p_organization_id uuid,
    p_product_category text,
    p_actor_id uuid,
    p_actor_role text
  )
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text :=
    content_factory_private.require_ai_product_category(p_product_category);
  as_of_value timestamptz := statement_timestamp();
  event_cursor_value bigint := 0;
  categories_value jsonb;
  readiness_value jsonb;
  sources_value jsonb;
  cards_value jsonb;
  activity_value jsonb;
  effective_policy_value jsonb;
  detail_value jsonb;
  scope_version_value integer := 0;
  can_mutate boolean := p_actor_role = any(array['owner', 'admin', 'producer']);
begin
  select greatest(
    coalesce((select max(source.event_cursor)
      from content_factory.ai_category_knowledge_sources source
      where source.organization_id = p_organization_id), 0),
    coalesce((select max(decision.event_cursor)
      from content_factory.ai_teaching_card_decisions decision
      where decision.organization_id = p_organization_id), 0),
    coalesce((select max(policy.event_cursor)
      from content_factory.ai_effective_category_policies policy
      where policy.organization_id = p_organization_id), 0)
  ) into event_cursor_value;

  with categories(product_category, ordinal) as (values
    ('cosmetics', 1), ('baa', 2), ('sports_food', 3), ('food', 4),
    ('household', 5), ('apparel', 6), ('electronics', 7), ('other', 8)
  ), summaries as (
    select
      category.product_category,
      category.ordinal,
      content_factory_private.ai_category_evidence_readiness(
        p_organization_id,
        category.product_category
      ) as readiness
    from categories category
  )
  select jsonb_agg(jsonb_build_object(
    'key', summary.product_category,
    'product_category', summary.product_category,
    'readiness_score', (summary.readiness ->> 'score')::integer,
    'readiness_status', summary.readiness ->> 'status',
    'source_count', (summary.readiness ->> 'source_count')::integer,
    'evidence_count', (summary.readiness ->> 'evidence_count')::integer,
    'pending_teaching_count',
      (summary.readiness ->> 'pending_teaching_count')::integer,
    'scope_version', (summary.readiness ->> 'scope_version')::integer,
    'evidence_hash', summary.readiness ->> 'evidence_hash',
    'gaps', summary.readiness -> 'gaps',
    'as_of', as_of_value
  ) order by summary.ordinal)
  into categories_value
  from summaries summary;

  readiness_value :=
    content_factory_private.ai_category_evidence_readiness(
      p_organization_id,
      category_value
    ) || jsonb_build_object('as_of', as_of_value);
  scope_version_value := (readiness_value ->> 'scope_version')::integer;

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into sources_value
  from (
    select
      source.event_cursor,
      jsonb_build_object(
        'source_id', source.id,
        'product_category', source.product_category,
        'source_kind', source.source_kind,
        'title', source.title,
        'note', source.note,
        'bucket', source.bucket_id,
        'object_key', source.object_name,
        'original_filename', source.original_filename,
        'mime_type', source.mime_type,
        'size_bytes', source.size_bytes,
        'client_sha256', source.sha256,
        'sha256_verification', case
          when source.source_kind = 'file'
            then 'client_declared_not_server_recomputed'
          else null
        end,
        'source_url', source.source_url,
        'rights_confirmed', source.rights_confirmed,
        'status', source.status,
        'evidence_hash', source.source_hash,
        'added_at', source.created_at,
        'event_cursor', source.event_cursor
      ) as payload
    from content_factory.ai_category_knowledge_sources source
    where source.organization_id = p_organization_id
      and source.product_category = category_value
    order by source.event_cursor desc
    limit 100
  ) item;

  with current_cards as (
    select distinct on (card.code)
      card.*
    from content_factory.ai_teaching_card_catalog card
    order by card.code, card.version desc, card.created_at desc, card.id desc
  ), decision_heads as (
    select distinct on (current_card.code)
      current_card.code,
      decision.id,
      decision.decision,
      decision.reason_code,
      decision.decided_by,
      decision.created_at,
      decision.resulting_scope_version,
      decision.event_cursor
    from current_cards current_card
    join content_factory.ai_teaching_card_decisions decision
      on decision.card_id = current_card.id
     and decision.organization_id = p_organization_id
     and decision.product_category = category_value
    order by current_card.code, decision.event_cursor desc
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'card_id', card.id,
    'card_version', card.version,
    'card_hash', card.card_hash,
    'product_category', category_value,
    'signal_key', 'creative_angle.' || card.creative_angle,
    'creative_angle', card.creative_angle,
    'ai_judgement', card.ai_judgement,
    'title', card.title,
    'explanation', card.explanation,
    'impact', case card.ai_judgement
      when 'good' then 'preferred_angle'
      else 'avoid_angle'
    end,
    'status', case head.decision
      when 'approve' then 'approved'
      when 'reject' then 'rejected'
      else 'pending'
    end,
    'decision', head.decision,
    'reason', head.reason_code,
    'decided_by', head.decided_by,
    'decided_at', head.created_at,
    'scope_version', head.resulting_scope_version,
    'evidence_count', coalesce((
      select count(*)::integer
      from content_factory.ai_teaching_card_decisions history
      join content_factory.ai_teaching_card_catalog history_card
        on history_card.id = history.card_id
      where history.organization_id = p_organization_id
        and history.product_category = category_value
        and history_card.code = card.code
    ), 0)
  ) order by card.ai_judgement desc, card.creative_angle), '[]'::jsonb)
  into cards_value
  from current_cards card
  left join decision_heads head on head.code = card.code
  where card.status = 'active';

  select coalesce(jsonb_agg(item.payload order by item.event_cursor desc),
                  '[]'::jsonb)
  into activity_value
  from (
    select source.event_cursor, jsonb_build_object(
      'id', source.id,
      'type', 'knowledge_source_registered',
      'title', source.title,
      'description', case source.source_kind
        when 'file' then 'Зарегистрирован файл категории; содержимое не применяется автоматически'
        else 'Зарегистрирована HTTPS-ссылка; содержимое не применяется автоматически'
      end,
      'created_at', source.created_at,
      'state_version', source.event_cursor
    ) as payload
    from content_factory.ai_category_knowledge_sources source
    where source.organization_id = p_organization_id
      and source.product_category = category_value
    union all
    select decision.event_cursor, jsonb_build_object(
      'id', decision.id,
      'type', case decision.decision
        when 'approve' then 'teaching_card_approved'
        else 'teaching_card_rejected'
      end,
      'title', card.title,
      'description', decision.reason_code,
      'actor_name', coalesce(profile.display_name, profile.email),
      'created_at', decision.created_at,
      'state_version', decision.event_cursor
    ) as payload
    from content_factory.ai_teaching_card_decisions decision
    join content_factory.ai_teaching_card_catalog card
      on card.id = decision.card_id
    left join content_factory.profiles profile
      on profile.id = decision.decided_by
    where decision.organization_id = p_organization_id
      and decision.product_category = category_value
    order by event_cursor desc
    limit 100
  ) item;

  select jsonb_build_object(
    'version', 'ai-category-teaching-policy-v1',
    'policy_version', policy.scope_version,
    'scope_version', policy.scope_version,
    'policy_hash', policy.policy_hash,
    'status', case
      when policy.preferred_creative_angle is null
       and policy.avoid_creative_angle is null then 'none'
      else 'active'
    end,
    'preferred_creative_angle', policy.preferred_creative_angle,
    'avoid_creative_angle', policy.avoid_creative_angle,
    'rules', coalesce((
      select jsonb_agg(rule.payload order by rule.ordinal)
      from (values
        (1, case when policy.preferred_creative_angle is null then null else
          jsonb_build_object(
            'id', 'preferred_angle',
            'label', 'Что хорошо',
            'effect', policy.preferred_creative_angle
          ) end),
        (2, case when policy.avoid_creative_angle is null then null else
          jsonb_build_object(
            'id', 'avoid_angle',
            'label', 'Что плохо',
            'effect', policy.avoid_creative_angle
          ) end)
      ) as rule(ordinal, payload)
      where rule.payload is not null
    ), '[]'::jsonb),
    'updated_at', policy.created_at,
    'raw_notes_excluded', true,
    'exact_category_scope', true
  )
  into effective_policy_value
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = p_organization_id
    and policy.product_category = category_value
  order by policy.scope_version desc
  limit 1;

  effective_policy_value := coalesce(effective_policy_value, jsonb_build_object(
    'version', 'ai-category-teaching-policy-v1',
    'policy_version', 0,
    'scope_version', 0,
    'policy_hash', null,
    'status', 'none',
    'preferred_creative_angle', null,
    'avoid_creative_angle', null,
    'rules', '[]'::jsonb,
    'raw_notes_excluded', true,
    'exact_category_scope', true
  ));

  detail_value := jsonb_build_object(
    'key', category_value,
    'product_category', category_value,
    'readiness', readiness_value,
    'knowledge_sources', sources_value,
    'gaps', readiness_value -> 'gaps',
    'teaching_cards', cards_value,
    'activity', activity_value,
    'effective_policy', effective_policy_value,
    'scope_version', scope_version_value,
    'evidence_count', (readiness_value ->> 'evidence_count')::integer,
    'source_count', (readiness_value ->> 'source_count')::integer,
    'pending_teaching_count',
      (readiness_value ->> 'pending_teaching_count')::integer,
    'as_of', as_of_value
  );

  return jsonb_build_object(
    'ok', true,
    'version', 'ai-learning-control-room-v1',
    'schema_version', 'ai-learning-control-room-v1',
    'organization_id', p_organization_id,
    'selected_category', category_value,
    'state_version', event_cursor_value,
    'event_cursor', event_cursor_value,
    'as_of', as_of_value,
    'categories', categories_value,
    'category_detail', detail_value,
    'actor', jsonb_build_object(
      'id', p_actor_id,
      'role', p_actor_role
    ),
    'capabilities', jsonb_build_object(
      'can_read', true,
      'can_register_source', can_mutate,
      'can_add_link', can_mutate,
      'can_upload_file', can_mutate,
      'can_decide_teaching_card', can_mutate,
      'can_view_history', true,
      'knowledge_bucket', 'contentengine-knowledge',
      'knowledge_file_size_limit', 26214400,
      'generation_policy_rpc', 'creator_generation_learning_policy',
      'cross_category_learning_forbidden', true
    ),
    'guidance', jsonb_build_object(
      'status', readiness_value ->> 'status',
      'recommended_next_action',
        readiness_value #>> '{gaps,0,next_action}',
      'score_is_not_model_iq', true,
      'raw_sources_enter_prompt_automatically', false,
      'provider_action', false,
      'generation_action', false,
      'spend_action', false
    )
  );
end;
$$;

revoke all on function
  content_factory_private.ai_learning_control_room_snapshot(
    uuid, text, uuid, text
  )
  from public, anon, authenticated, service_role;

-- Clone the installed policy definition without moving or renaming the public
-- function.  CREATE OR REPLACE below therefore retains its OID and every paid
-- start dependency while the private clone remains the complete audited base.
do $preserve_generation_learning_policy$
declare
  installed_definition text;
  cloned_definition text;
begin
  if to_regprocedure(
    'content_factory_private.creator_generation_learning_policy_pre_ai_control_room_v8(jsonb)'
  ) is null then
    installed_definition := pg_catalog.pg_get_functiondef(
      'public.creator_generation_learning_policy(jsonb)'::regprocedure
    );
    cloned_definition := regexp_replace(
      installed_definition,
      'FUNCTION public\.creator_generation_learning_policy\(',
      'FUNCTION content_factory_private.creator_generation_learning_policy_pre_ai_control_room_v8(',
      'i'
    );
    if cloned_definition = installed_definition then
      raise exception using
        errcode = '55000',
        message = 'ai_learning_policy_clone_failed';
    end if;
    execute cloned_definition;
  end if;
end;
$preserve_generation_learning_policy$;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_pre_ai_control_room_v8(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_learning_policy(
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
  base_policy jsonb;
  organization_id uuid;
  category_value text;
  policy_row content_factory.ai_effective_category_policies%rowtype;
  generation_allowed_value boolean;
  base_preferred_angle_value text;
  preferred_angle_value text;
  avoid_angle_value text;
  preferred_angle_changed boolean := false;
  negative_fallback_applied boolean := false;
  preferred_hook_patterns_value jsonb;
  selected_hook_patterns_value jsonb;
  applied_value boolean;
  confidence_value text;
  reason_codes_value jsonb;
  safety_value jsonb;
  requested_model_value text;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  base_policy := content_factory_private
    .creator_generation_learning_policy_pre_ai_control_room_v8(p_payload);

  category_value := lower(btrim(coalesce(
    base_policy ->> 'product_category',
    p_payload ->> 'product_category',
    ''
  )));
  if category_value not in (
    'cosmetics', 'baa', 'sports_food', 'food', 'household',
    'apparel', 'electronics', 'other'
  ) then
    return base_policy;
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  select policy.*
  into policy_row
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = organization_id
    and policy.product_category = category_value
  order by policy.scope_version desc
  limit 1;

  if policy_row.id is null
     or (
       policy_row.preferred_creative_angle is null
       and policy_row.avoid_creative_angle is null
     ) then
    return base_policy;
  end if;

  generation_allowed_value :=
    base_policy -> 'generation_allowed' is distinct from 'false'::jsonb;
  base_preferred_angle_value :=
    nullif(base_policy ->> 'preferred_angle', '');
  preferred_angle_value := coalesce(
    policy_row.preferred_creative_angle,
    base_preferred_angle_value
  );
  avoid_angle_value := coalesce(
    policy_row.avoid_creative_angle,
    nullif(base_policy ->> 'avoid_angle', '')
  );
  if policy_row.avoid_creative_angle is not null
     and (
       preferred_angle_value is null
       or preferred_angle_value = policy_row.avoid_creative_angle
     ) then
    preferred_angle_value := case policy_row.avoid_creative_angle
      when 'product_focus' then 'trust_builder'
      else 'product_focus'
    end;
    negative_fallback_applied := true;
  end if;
  if avoid_angle_value is not distinct from preferred_angle_value then
    avoid_angle_value := null;
  end if;

  preferred_angle_changed :=
    preferred_angle_value is distinct from base_preferred_angle_value;
  preferred_hook_patterns_value := case
    when preferred_angle_changed then '[]'::jsonb
    when jsonb_typeof(base_policy -> 'preferred_hook_patterns') = 'array'
      then base_policy -> 'preferred_hook_patterns'
    else '[]'::jsonb
  end;
  selected_hook_patterns_value := case
    when preferred_angle_changed then '[]'::jsonb
    when jsonb_typeof(base_policy -> 'selected_hook_patterns') = 'array'
      then base_policy -> 'selected_hook_patterns'
    else preferred_hook_patterns_value
  end;

  applied_value := generation_allowed_value and (
    base_policy -> 'applied' = 'true'::jsonb
    or policy_row.preferred_creative_angle is not null
    or policy_row.avoid_creative_angle is not null
  );
  confidence_value := case
    when policy_row.preferred_creative_angle is not null
      or policy_row.avoid_creative_angle is not null then 'high'
    else coalesce(base_policy ->> 'confidence', 'none')
  end;
  reason_codes_value := case
    when jsonb_typeof(base_policy -> 'reason_codes') = 'array'
      then base_policy -> 'reason_codes'
    else '[]'::jsonb
  end || jsonb_build_array(
    case
      when not generation_allowed_value
        then 'ai_teaching_policy_available_but_generation_blocked'
      when policy_row.preferred_creative_angle is not null
        then 'ai_teaching_positive_angle_applied'
      when negative_fallback_applied
        then 'ai_teaching_negative_fallback_preferred'
      else 'ai_teaching_negative_angle_advisory'
    end,
    case
      when policy_row.avoid_creative_angle is not null
        then 'ai_teaching_negative_angle_applied'
      else 'ai_teaching_no_negative_angle'
    end,
    'ai_teaching_deterministic_selection'
  );
  safety_value := case
    when jsonb_typeof(base_policy -> 'safety') = 'object'
      then base_policy -> 'safety'
    else '{}'::jsonb
  end || jsonb_build_object(
    'ai_teaching_bounded_creative_angles_only', true,
    'raw_knowledge_and_notes_excluded', true,
    'exact_category_scope', true,
    'cross_category_learning_forbidden', true,
    'generation_allowed_preserved', true,
    'rejection_guards_preserved', true,
    'deterministic_negative_fallback', true,
    'hook_patterns_cleared_on_angle_change', true,
    'bounded_exploration_cursor_removed', true
  );

  requested_model_value := base_policy ->> 'requested_model';
  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model' - 'exploration')
    || jsonb_build_object(
      'version', 'generation-learning-v9-ai-teaching',
      'product_category', category_value,
      'applied', applied_value,
      'confidence', confidence_value,
      -- Human teaching is deterministic.  It must not inherit the mutable
      -- two-arm exploration cursor because the generation-spec provider guard
      -- gives that cursor a deliberately narrow product_focus/demonstration
      -- drift allowance.  "performance" is the installed non-exploration
      -- selection contract understood by the existing handoff and outcome
      -- consumers; the adjacent provenance identifies its human source.
      'selection_mode', 'performance',
      'selection_provenance', jsonb_build_object(
        'schema_version', 'ai-teaching-selection-provenance-v1',
        'source', 'human_teaching_card_policy',
        'deterministic', true,
        'product_category', category_value,
        'scope_version', policy_row.scope_version,
        'teaching_policy_hash', policy_row.policy_hash,
        -- A queued paid job is allowed to advance category_evidence_count by
        -- one before provider claim, which also changes the base policy hash.
        -- Keep only the stable installed base version in provenance so the
        -- live guard can apply its existing top-level drift normalization.
        'base_policy_version', base_policy ->> 'version'
      ),
      'preferred_angle', preferred_angle_value,
      'avoid_angle', avoid_angle_value,
      'preferred_hook_patterns', preferred_hook_patterns_value,
      'selected_angle', preferred_angle_value,
      'selected_hook_patterns', selected_hook_patterns_value,
      'reason_codes', reason_codes_value,
      'safety', safety_value,
      'ai_teaching_policy', jsonb_build_object(
        'version', 'ai-category-teaching-policy-v1',
        'scope_version', policy_row.scope_version,
        'policy_hash', policy_row.policy_hash,
        'preferred_creative_angle',
          policy_row.preferred_creative_angle,
        'avoid_creative_angle', policy_row.avoid_creative_angle,
        'negative_fallback_applied', negative_fallback_applied,
        'positive_decision_id', policy_row.positive_decision_id,
        'negative_decision_id', policy_row.negative_decision_id,
        'raw_notes_excluded', true
      )
    );
  policy_hash_value :=
    content_factory_private.json_hash(policy_without_hash);

  return policy_without_hash || jsonb_build_object(
    'policy_hash', policy_hash_value,
    'requested_model', requested_model_value
  );
end;
$$;

revoke all on function public.creator_generation_learning_policy(jsonb)
  from public, anon;
grant execute on function public.creator_generation_learning_policy(jsonb)
  to authenticated;

create or replace function public.creator_ai_learning_control_room(
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
  category_value text;
  snapshot_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'product_category'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_learning_control_room_payload_invalid';
  end if;

  -- Polling is read-only: membership_role below validates the active profile,
  -- organization and membership without current_profile_id's profile UPSERT.
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501',
      message = 'authentication_required';
  end if;
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  snapshot_value :=
    content_factory_private.ai_learning_control_room_snapshot(
      organization_id,
      category_value,
      user_id,
      actor_role
    );

  -- The named RPC is informational here; paid starts call the OID-preserved
  -- creator_generation_learning_policy wrapper independently and recheck all
  -- rejection guards.  No control-room read can start provider work.
  return snapshot_value;
end;
$$;

revoke all on function public.creator_ai_learning_control_room(jsonb)
  from public, anon;
grant execute on function public.creator_ai_learning_control_room(jsonb)
  to authenticated;

create or replace function public.creator_register_ai_knowledge_source(
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
  category_value text;
  source_kind_value text;
  title_value text;
  note_value text;
  idempotency_key_value text;
  bucket_value text;
  object_key_value text;
  original_filename_value text;
  mime_value text;
  sha_value text;
  size_value bigint;
  source_url_value text;
  authority_value text;
  host_value text;
  storage_metadata jsonb;
  storage_size bigint;
  storage_mime text;
  source_hash_value text;
  request_payload jsonb;
  replay_value jsonb;
  source_row content_factory.ai_category_knowledge_sources%rowtype;
  snapshot_value jsonb;
  result_value jsonb;
  category_source_count bigint;
  organization_source_count bigint;
  owner_source_count bigint;
  owner_file_bytes numeric;
  organization_file_bytes numeric;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'product_category', 'source_kind', 'title', 'note',
      'rights_confirmed', 'bucket', 'object_key', 'original_filename',
      'mime_type', 'size_bytes', 'sha256', 'source_url', 'idempotency_key'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_knowledge_source_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer']
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  source_kind_value := lower(content_factory_private.require_text(
    p_payload, 'source_kind', 4, 4
  ));
  if source_kind_value not in ('file', 'link') then
    raise exception using
      errcode = '22023',
      message = 'ai_knowledge_source_kind_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'title') <> 'string'
     or (p_payload ? 'note' and jsonb_typeof(p_payload -> 'note') <> 'string') then
    raise exception using
      errcode = '22023',
      message = 'ai_knowledge_source_copy_invalid';
  end if;
  title_value := content_factory_private.require_text(
    p_payload, 'title', 2, 180
  );
  note_value := nullif(btrim(coalesce(p_payload ->> 'note', '')), '');
  if length(coalesce(note_value, '')) > 1000 then
    raise exception using
      errcode = '22023',
      message = 'ai_knowledge_source_copy_invalid';
  end if;
  if p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '42501',
      message = 'ai_knowledge_source_rights_required';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  if source_kind_value = 'file' then
    if p_payload ? 'source_url'
       or not (p_payload ? 'bucket')
       or not (p_payload ? 'object_key')
       or not (p_payload ? 'original_filename')
       or not (p_payload ? 'mime_type')
       or not (p_payload ? 'size_bytes')
       or not (p_payload ? 'sha256') then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_file_invalid';
    end if;

    bucket_value := content_factory_private.require_text(
      p_payload, 'bucket', 3, 80
    );
    object_key_value := content_factory_private.require_text(
      p_payload, 'object_key', 10, 1000
    );
    original_filename_value := content_factory_private.require_text(
      p_payload, 'original_filename', 1, 240
    );
    mime_value := lower(content_factory_private.require_text(
      p_payload, 'mime_type', 3, 160
    ));
    sha_value := lower(content_factory_private.require_text(
      p_payload, 'sha256', 64, 64
    ));
    if coalesce(p_payload ->> 'size_bytes', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_file_invalid';
    end if;
    begin
      size_value := (p_payload ->> 'size_bytes')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_file_invalid';
    end;

    if bucket_value <> 'contentengine-knowledge'
       or split_part(object_key_value, '/', 1) <> organization_id::text
       or split_part(object_key_value, '/', 2) <> user_id::text
       or split_part(object_key_value, '/', 3) <> 'ai-knowledge'
       or split_part(object_key_value, '/', 4) = ''
       or object_key_value ~ '(^|/)\.\.(/|$)'
       or position(chr(92) in object_key_value) > 0 then
      raise exception using
        errcode = '42501',
        message = 'ai_knowledge_storage_access_denied';
    end if;
    if size_value < 1 or size_value > 26214400
       or sha_value !~ '^[0-9a-f]{64}$'
       or mime_value not in (
         'application/pdf',
         'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
         'text/csv', 'text/markdown', 'text/plain'
       )
       or not (
         (mime_value = 'application/pdf'
           and lower(original_filename_value) ~ '\.pdf$')
         or (mime_value = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
           and lower(original_filename_value) ~ '\.docx$')
         or (mime_value = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
           and lower(original_filename_value) ~ '\.xlsx$')
         or (mime_value = 'text/csv'
           and lower(original_filename_value) ~ '\.csv$')
         or (mime_value = 'text/markdown'
           and lower(original_filename_value) ~ '\.(md|markdown)$')
         or (mime_value = 'text/plain'
           and lower(original_filename_value) ~ '\.txt$')
       ) then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_file_invalid';
    end if;

    perform pg_advisory_xact_lock(
      hashtext(bucket_value),
      hashtext(object_key_value)
    );
    select storage_object.metadata
    into storage_metadata
    from storage.objects storage_object
    where storage_object.bucket_id = bucket_value
      and storage_object.name = object_key_value
    for update;
    if storage_metadata is null then
      raise exception using
        errcode = 'P0002',
        message = 'ai_knowledge_storage_object_not_found';
    end if;
    if jsonb_typeof(storage_metadata) <> 'object'
       or coalesce(storage_metadata ->> 'size', '') !~ '^[0-9]+$'
       or nullif(btrim(coalesce(
         storage_metadata ->> 'mimetype', ''
       )), '') is null then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_storage_metadata_invalid';
    end if;
    begin
      storage_size := (storage_metadata ->> 'size')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_storage_metadata_invalid';
    end;
    storage_mime := lower(btrim(storage_metadata ->> 'mimetype'));
    if storage_size <> size_value or storage_mime <> mime_value then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_storage_metadata_mismatch';
    end if;

    source_hash_value := content_factory_private.json_hash(jsonb_build_object(
      'product_category', category_value,
      'source_kind', source_kind_value,
      'bucket', bucket_value,
      'object_key', object_key_value,
      'mime_type', mime_value,
      'size_bytes', size_value,
      'client_sha256', sha_value,
      'rights_confirmed', true
    ));
  else
    if p_payload ? 'bucket'
       or p_payload ? 'object_key'
       or p_payload ? 'original_filename'
       or p_payload ? 'mime_type'
       or p_payload ? 'size_bytes'
       or p_payload ? 'sha256'
       or not (p_payload ? 'source_url')
       or jsonb_typeof(p_payload -> 'source_url') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_link_invalid';
    end if;
    source_url_value := content_factory_private.require_text(
      p_payload, 'source_url', 12, 2048
    );
    if source_url_value !~* '^https://[^[:space:]/?#]+([/?#][^[:space:]]*)?$'
       or source_url_value ~ '[[:cntrl:]]'
       or position(chr(92) in source_url_value) > 0 then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_url_invalid';
    end if;
    authority_value := split_part(
      split_part(split_part(substring(source_url_value from 9), '/', 1), '?', 1),
      '#', 1
    );
    host_value := lower(split_part(authority_value, ':', 1));
    if authority_value = ''
       or position('@' in authority_value) > 0
       or position('.' in host_value) = 0
       or host_value = 'localhost'
       or host_value ~ '(^|\.)localhost$'
       or host_value ~ '(^|\.)local$'
       or host_value ~ '^[0-9.]+$' then
      raise exception using
        errcode = '22023',
        message = 'ai_knowledge_source_url_invalid';
    end if;

    source_hash_value := content_factory_private.json_hash(jsonb_build_object(
      'product_category', category_value,
      'source_kind', source_kind_value,
      'source_url', source_url_value,
      'rights_confirmed', true
    ));
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id,
    'creator_register_ai_knowledge_source',
    idempotency_key_value,
    request_payload
  );
  if replay_value is not null then
    return replay_value;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('ai_knowledge_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('ai_knowledge_quota:owner')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('ai_knowledge_quota:' || category_value)
  );
  select
    count(*) filter (
      where source.product_category = category_value
    ),
    count(*),
    count(*) filter (where source.owner_id = user_id),
    coalesce(sum(source.size_bytes) filter (
      where source.owner_id = user_id and source.source_kind = 'file'
    ), 0),
    coalesce(sum(source.size_bytes) filter (
      where source.source_kind = 'file'
    ), 0)
  into
    category_source_count,
    organization_source_count,
    owner_source_count,
    owner_file_bytes,
    organization_file_bytes
  from content_factory.ai_category_knowledge_sources source
  where source.organization_id = organization_id;
  if category_source_count >= 1000
     or organization_source_count >= 10000
     or owner_source_count >= 2000 then
    raise exception using
      errcode = '54000',
      message = 'ai_knowledge_source_quota_exceeded';
  end if;
  if source_kind_value = 'file' and (
       owner_file_bytes + size_value > 5368709120
       or organization_file_bytes + size_value > 53687091200
     ) then
    raise exception using
      errcode = '54000',
      message = 'ai_knowledge_storage_quota_exceeded';
  end if;

  insert into content_factory.ai_category_knowledge_sources (
    organization_id, product_category, source_kind, owner_id,
    title, note, bucket_id, object_name, original_filename,
    mime_type, size_bytes, sha256, source_url, rights_confirmed,
    source_hash, request_hash, idempotency_key
  ) values (
    organization_id, category_value, source_kind_value, user_id,
    title_value, note_value, bucket_value, object_key_value,
    original_filename_value, mime_value, size_value, sha_value,
    source_url_value, true, source_hash_value,
    content_factory_private.json_hash(request_payload),
    idempotency_key_value
  )
  returning * into source_row;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'ai_knowledge_source_registered',
    'ai_knowledge_source',
    source_row.id::text,
    jsonb_build_object(
      'product_category', category_value,
      'source_kind', source_kind_value,
      'source_hash', source_hash_value,
      'event_cursor', source_row.event_cursor,
      'raw_note_excluded_from_policy', true
    ),
    'ai-knowledge:' || idempotency_key_value
  );

  snapshot_value :=
    content_factory_private.ai_learning_control_room_snapshot(
      organization_id,
      category_value,
      user_id,
      actor_role
    );
  result_value := jsonb_build_object(
    'ok', true,
    'snapshot', snapshot_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_register_ai_knowledge_source',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_decide_ai_teaching_card(
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
  category_value text;
  card_id_value uuid;
  card_hash_value text;
  card_version_value integer;
  expected_scope_version_value integer;
  current_scope_version_value integer := 0;
  decision_value text;
  reason_code_value text;
  idempotency_key_value text;
  request_payload jsonb;
  replay_value jsonb;
  card_row content_factory.ai_teaching_card_catalog%rowtype;
  decision_row content_factory.ai_teaching_card_decisions%rowtype;
  positive_decision_id_value uuid;
  positive_angle_value text;
  positive_cursor_value bigint;
  negative_decision_id_value uuid;
  negative_angle_value text;
  negative_cursor_value bigint;
  policy_payload jsonb;
  policy_hash_value text;
  policy_row content_factory.ai_effective_category_policies%rowtype;
  decision_hash_value text;
  snapshot_value jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'product_category', 'card_id', 'card_hash',
      'card_version', 'expected_scope_version', 'decision', 'reason_code',
      'confirmation', 'idempotency_key'
    ])
  ) then
    raise exception using
      errcode = '22023',
      message = 'ai_teaching_decision_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer']
  );
  category_value := content_factory_private.require_ai_product_category(
    p_payload ->> 'product_category'
  );
  card_id_value := content_factory_private.require_uuid(p_payload, 'card_id');
  card_hash_value := lower(content_factory_private.require_text(
    p_payload, 'card_hash', 64, 64
  ));
  if card_hash_value !~ '^[0-9a-f]{64}$'
     or coalesce(p_payload ->> 'card_version', '') !~ '^[1-9][0-9]{0,6}$'
     or coalesce(p_payload ->> 'expected_scope_version', '')
          !~ '^(0|[1-9][0-9]{0,9})$' then
    raise exception using
      errcode = '22023',
      message = 'ai_teaching_decision_identity_invalid';
  end if;
  begin
    card_version_value := (p_payload ->> 'card_version')::integer;
    expected_scope_version_value :=
      (p_payload ->> 'expected_scope_version')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'ai_teaching_decision_identity_invalid';
  end;
  decision_value := lower(content_factory_private.require_text(
    p_payload, 'decision', 6, 7
  ));
  reason_code_value := lower(content_factory_private.require_text(
    p_payload, 'reason_code', 3, 80
  ));
  if decision_value not in ('approve', 'reject')
     or reason_code_value not in (
       'operator_confirmed', 'operator_rejected'
     )
     or (decision_value = 'approve'
       and reason_code_value <> 'operator_confirmed')
     or (decision_value = 'reject'
       and reason_code_value <> 'operator_rejected')
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'ai_teaching_decision_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id,
    'creator_decide_ai_teaching_card',
    idempotency_key_value,
    request_payload
  );
  if replay_value is not null then
    return replay_value;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('ai_teaching_scope:' || category_value)
  );
  select coalesce(max(policy.scope_version), 0)::integer
  into current_scope_version_value
  from content_factory.ai_effective_category_policies policy
  where policy.organization_id = organization_id
    and policy.product_category = category_value;
  if current_scope_version_value <> expected_scope_version_value then
    raise exception using
      errcode = '40001',
      message = 'ai_teaching_scope_version_conflict';
  end if;

  select card.*
  into card_row
  from content_factory.ai_teaching_card_catalog card
  where card.id = card_id_value;
  if card_row.id is null
     or card_row.status <> 'active'
     or card_row.version <> card_version_value
     or card_row.card_hash <> card_hash_value
     or exists (
       select 1
       from content_factory.ai_teaching_card_catalog newer_card
       where newer_card.code = card_row.code
         and newer_card.version > card_row.version
     ) then
    raise exception using
      errcode = '40001',
      message = 'ai_teaching_card_stale';
  end if;

  decision_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'organization_id', organization_id,
    'product_category', category_value,
    'card_id', card_row.id,
    'card_version', card_row.version,
    'card_hash', card_row.card_hash,
    'creative_angle', card_row.creative_angle,
    'ai_judgement', card_row.ai_judgement,
    'decision', decision_value,
    'reason_code', reason_code_value,
    'expected_scope_version', expected_scope_version_value,
    'resulting_scope_version', expected_scope_version_value + 1
  ));

  insert into content_factory.ai_teaching_card_decisions (
    organization_id, product_category, card_id, card_version, card_hash,
    decision, reason_code, confirmation, expected_scope_version,
    resulting_scope_version, decided_by, request_hash, decision_hash,
    idempotency_key
  ) values (
    organization_id, category_value, card_row.id, card_row.version,
    card_row.card_hash, decision_value, reason_code_value, true,
    expected_scope_version_value, expected_scope_version_value + 1,
    user_id, content_factory_private.json_hash(request_payload),
    decision_hash_value, idempotency_key_value
  )
  returning * into decision_row;

  with current_cards as (
    select distinct on (card.code)
      card.id,
      card.code,
      card.creative_angle,
      card.ai_judgement
    from content_factory.ai_teaching_card_catalog card
    where card.status = 'active'
    order by card.code, card.version desc, card.created_at desc, card.id desc
  ), heads as (
    select distinct on (current_card.code)
      current_card.code,
      current_card.creative_angle,
      current_card.ai_judgement,
      history.id as decision_id,
      history.decision,
      history.event_cursor
    from current_cards current_card
    join content_factory.ai_teaching_card_decisions history
      on history.card_id = current_card.id
     and history.organization_id = organization_id
     and history.product_category = category_value
    order by current_card.code, history.event_cursor desc
  ), approved as (
    select *
    from heads
    where decision = 'approve'
  ), positive as (
    select approved.decision_id, approved.creative_angle,
           approved.event_cursor
    from approved
    where approved.ai_judgement = 'good'
    order by approved.event_cursor desc
    limit 1
  ), negative as (
    select approved.decision_id, approved.creative_angle,
           approved.event_cursor
    from approved
    where approved.ai_judgement = 'bad'
    order by approved.event_cursor desc
    limit 1
  )
  select
    positive.decision_id,
    positive.creative_angle,
    positive.event_cursor,
    negative.decision_id,
    negative.creative_angle,
    negative.event_cursor
  into
    positive_decision_id_value,
    positive_angle_value,
    positive_cursor_value,
    negative_decision_id_value,
    negative_angle_value,
    negative_cursor_value
  from (select true as anchor) singleton
  left join positive on true
  left join negative on true;

  -- Contradictory feedback is retained in history but never emitted as a
  -- self-conflicting generation rule.  The most recent human decision wins.
  if positive_angle_value is not null
     and positive_angle_value = negative_angle_value then
    if positive_cursor_value >= negative_cursor_value then
      negative_decision_id_value := null;
      negative_angle_value := null;
    else
      positive_decision_id_value := null;
      positive_angle_value := null;
    end if;
  end if;

  policy_payload := jsonb_build_object(
    'schema_version', 'ai-category-teaching-policy-v1',
    'product_category', category_value,
    'scope_version', expected_scope_version_value + 1,
    'preferred_creative_angle', positive_angle_value,
    'avoid_creative_angle', negative_angle_value,
    'positive_decision_id', positive_decision_id_value,
    'negative_decision_id', negative_decision_id_value,
    'source_decision_id', decision_row.id,
    'bounded_to_creative_angle_codes', true,
    'raw_sources_and_notes_excluded', true,
    'cross_category_learning_forbidden', true
  );
  policy_hash_value :=
    content_factory_private.json_hash(policy_payload);

  insert into content_factory.ai_effective_category_policies (
    organization_id, product_category, scope_version,
    preferred_creative_angle, avoid_creative_angle,
    positive_decision_id, negative_decision_id, source_decision_id,
    policy_hash, created_by
  ) values (
    organization_id, category_value, expected_scope_version_value + 1,
    positive_angle_value, negative_angle_value,
    positive_decision_id_value, negative_decision_id_value, decision_row.id,
    policy_hash_value, user_id
  )
  returning * into policy_row;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'ai_teaching_card_decided',
    'ai_teaching_card_decision',
    decision_row.id::text,
    jsonb_build_object(
      'product_category', category_value,
      'card_id', card_row.id,
      'card_version', card_row.version,
      'card_hash', card_row.card_hash,
      'decision', decision_value,
      'scope_version', policy_row.scope_version,
      'policy_hash', policy_row.policy_hash,
      'event_cursor', policy_row.event_cursor
    ),
    'ai-teaching:' || idempotency_key_value
  );

  snapshot_value :=
    content_factory_private.ai_learning_control_room_snapshot(
      organization_id,
      category_value,
      user_id,
      actor_role
    );
  result_value := jsonb_build_object(
    'ok', true,
    'snapshot', snapshot_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_ai_teaching_card',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_register_ai_knowledge_source(jsonb)
  from public, anon;
grant execute on function public.creator_register_ai_knowledge_source(jsonb)
  to authenticated;

revoke all on function public.creator_decide_ai_teaching_card(jsonb)
  from public, anon;
grant execute on function public.creator_decide_ai_teaching_card(jsonb)
  to authenticated;

comment on table content_factory.ai_category_knowledge_sources is
  'Append-only category evidence metadata. Raw notes never become generation policy.';
comment on table content_factory.ai_teaching_card_catalog is
  'Global versioned catalogue bounded to allowlisted creative-angle good/bad cards.';
comment on table content_factory.ai_teaching_card_decisions is
  'Append-only, CAS-protected category teaching decisions.';
comment on table content_factory.ai_effective_category_policies is
  'Append-only effective category policy versions containing structural codes only.';
comment on function public.creator_ai_learning_control_room(jsonb) is
  'Authoritative evidence-readiness command-centre snapshot; this is not model IQ.';
comment on function public.creator_register_ai_knowledge_source(jsonb) is
  'Registers one exact-category file or HTTPS source after rights and storage checks.';
comment on function public.creator_decide_ai_teaching_card(jsonb) is
  'Appends one confirmed teaching decision and the next exact-category policy version.';

commit;

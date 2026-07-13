begin;

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

create schema if not exists content_factory;
create schema if not exists content_factory_private;

comment on schema content_factory is
  'Browser-facing Content AI Factory schema. Every table is protected by RLS.';
comment on schema content_factory_private is
  'Non-exposed server data and trigger helpers. Never add this schema to PostgREST.';

revoke all on schema content_factory_private from public, anon, authenticated;
revoke all on schema content_factory from public, anon;

create table if not exists content_factory.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text,
    display_name text,
    status text not null default 'active'
      check (status in ('active', 'suspended', 'disabled')),
    metadata jsonb not null default '{}'::jsonb
      check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (email is null or (length(email) between 3 and 320)),
    check (display_name is null or length(display_name) between 1 and 180)
);

create unique index if not exists profiles_email_lower_uq
  on content_factory.profiles (lower(email))
  where email is not null;

create table if not exists content_factory.organizations (
    id uuid primary key default extensions.gen_random_uuid(),
    name text not null check (length(btrim(name)) between 2 and 180),
    slug text not null unique
      check (slug ~ '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$'),
    status text not null default 'active'
      check (status in ('active', 'suspended', 'closed')),
    settings jsonb not null default '{}'::jsonb
      check (jsonb_typeof(settings) = 'object'),
    bootstrap_idempotency_key text unique,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
      bootstrap_idempotency_key is null
      or length(bootstrap_idempotency_key) between 12 and 180
    )
);

create table if not exists content_factory.memberships (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    profile_id uuid not null
      references content_factory.profiles(id) on delete cascade,
    role text not null default 'trainee'
      check (role in ('owner', 'admin', 'producer', 'reviewer', 'operator', 'trainee', 'viewer')),
    status text not null default 'active'
      check (status in ('active', 'suspended', 'revoked')),
    permissions jsonb not null default '[]'::jsonb
      check (jsonb_typeof(permissions) = 'array'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint memberships_org_profile_uq unique (organization_id, profile_id)
);

create index if not exists memberships_profile_status_idx
  on content_factory.memberships (profile_id, status, organization_id);
create index if not exists memberships_org_role_status_idx
  on content_factory.memberships (organization_id, role, status);

create table if not exists content_factory.membership_invites (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    email text not null check (length(email) between 3 and 320),
    role text not null
      check (role in ('owner', 'admin', 'producer', 'reviewer', 'operator', 'trainee', 'viewer')),
    token_hash text not null unique check (token_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    created_by uuid not null references content_factory.profiles(id),
    accepted_by uuid references content_factory.profiles(id),
    expires_at timestamptz not null,
    accepted_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz not null default now(),
    unique (organization_id, idempotency_key),
    check (accepted_at is null or accepted_by is not null)
);

create index if not exists membership_invites_lookup_idx
  on content_factory.membership_invites (token_hash, expires_at)
  where accepted_at is null and revoked_at is null;

create table if not exists content_factory.training_modules (
    code text primary key check (code ~ '^[a-z0-9_]{3,80}$'),
    module_type text not null check (module_type in ('course', 'exam')),
    title text not null check (length(title) between 3 and 180),
    description text not null check (length(description) between 3 and 1000),
    order_index integer not null check (order_index between 1 and 1000),
    pass_score integer not null default 1 check (pass_score between 1 and 100),
    question_count integer not null default 0 check (question_count between 0 and 100),
    content jsonb not null default '{}'::jsonb
      check (jsonb_typeof(content) = 'object'),
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists training_modules_order_uq
  on content_factory.training_modules (order_index);

create table if not exists content_factory.training_questions (
    code text primary key check (code ~ '^[a-z0-9_]{3,100}$'),
    module_code text not null
      references content_factory.training_modules(code) on delete cascade,
    question_type text not null
      check (question_type in ('single_choice', 'multi_select')),
    prompt text not null check (length(prompt) between 10 and 2000),
    options jsonb not null check (
      jsonb_typeof(options) = 'array'
      and jsonb_array_length(options) between 2 and 12
    ),
    order_index integer not null check (order_index between 1 and 1000),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (module_code, order_index)
);

create table if not exists content_factory_private.training_answer_keys (
    question_code text primary key
      references content_factory.training_questions(code) on delete cascade,
    correct_answers jsonb not null check (
      jsonb_typeof(correct_answers) = 'array'
      and jsonb_array_length(correct_answers) between 1 and 12
    ),
    rubric text,
    updated_at timestamptz not null default now()
);

create table if not exists content_factory.training_attempts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    module_code text not null
      references content_factory.training_modules(code),
    status text not null default 'completed'
      check (status in ('completed', 'invalidated')),
    score numeric(6,5) not null check (score between 0 and 1),
    correct_count integer not null check (correct_count >= 0),
    answered_count integer not null check (answered_count >= 0),
    question_count integer not null check (question_count >= 0),
    passed boolean not null,
    answers jsonb not null default '{}'::jsonb
      check (jsonb_typeof(answers) = 'object'),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    completed_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, profile_id, idempotency_key),
    check (correct_count <= question_count),
    check (answered_count <= question_count)
);

create index if not exists training_attempts_profile_module_idx
  on content_factory.training_attempts
  (organization_id, profile_id, module_code, completed_at desc);

create table if not exists content_factory.training_certifications (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    module_code text not null
      references content_factory.training_modules(code),
    attempt_id uuid not null
      references content_factory.training_attempts(id),
    status text not null default 'passed'
      check (status in ('passed', 'revoked', 'expired')),
    granted_at timestamptz not null default now(),
    expires_at timestamptz,
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    constraint training_certifications_org_profile_module_uq
      unique (organization_id, profile_id, module_code)
);

create index if not exists training_certifications_gate_idx
  on content_factory.training_certifications
  (organization_id, profile_id, module_code, status);

create table if not exists content_factory.products (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    sku text not null check (length(btrim(sku)) between 1 and 120),
    title text not null check (length(btrim(title)) between 2 and 240),
    current_wb_article text,
    status text not null default 'active'
      check (status in ('active', 'paused', 'archived')),
    metadata jsonb not null default '{}'::jsonb
      check (jsonb_typeof(metadata) = 'object'),
    created_by uuid not null references content_factory.profiles(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint products_org_sku_uq unique (organization_id, sku),
    unique (organization_id, id),
    check (current_wb_article is null or current_wb_article ~ '^[0-9]{4,20}$')
);

create table if not exists content_factory.generation_batches (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    product_id uuid not null,
    created_by uuid not null,
    name text not null check (length(btrim(name)) between 3 and 180),
    mode text not null default 'mock' check (mode = 'mock'),
    allow_real_spend boolean not null default false check (allow_real_spend = false),
    status text not null default 'mock_ready'
      check (status in ('mock_ready', 'cancelled')),
    total_requested integer not null check (total_requested between 1 and 50),
    total_created integer not null default 0 check (total_created between 0 and 50),
    input jsonb not null default '{}'::jsonb check (jsonb_typeof(input) = 'object'),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, id)
);

create index if not exists generation_batches_org_created_idx
  on content_factory.generation_batches (organization_id, created_at desc);

create table if not exists content_factory.generation_jobs (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    batch_id uuid not null,
    ordinal integer not null check (ordinal between 1 and 50),
    requested_by uuid not null,
    assigned_to uuid not null,
    mode text not null default 'mock' check (mode = 'mock'),
    provider text not null default 'mock' check (provider = 'mock'),
    allow_real_spend boolean not null default false check (allow_real_spend = false),
    estimated_cost_minor bigint not null default 0 check (estimated_cost_minor = 0),
    actual_cost_minor bigint not null default 0 check (actual_cost_minor = 0),
    status text not null default 'mock_ready'
      check (status in ('mock_ready', 'cancelled')),
    input jsonb not null default '{}'::jsonb check (jsonb_typeof(input) = 'object'),
    output jsonb not null default '{}'::jsonb check (jsonb_typeof(output) = 'object'),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, batch_id)
      references content_factory.generation_batches(organization_id, id),
    foreign key (organization_id, requested_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, assigned_to)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (batch_id, ordinal),
    unique (organization_id, id)
);

create index if not exists generation_jobs_assignee_idx
  on content_factory.generation_jobs (organization_id, assigned_to, status, created_at desc);

create table if not exists content_factory.creator_tasks (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    assignee_id uuid not null,
    created_by uuid not null,
    product_id uuid,
    generation_job_id uuid,
    task_type text not null
      check (task_type in ('mock_generation', 'video_review', 'placement', 'metrics', 'general')),
    title text not null check (length(btrim(title)) between 3 and 240),
    instructions text,
    status text not null default 'todo'
      check (status in ('todo', 'in_progress', 'submitted', 'review', 'done', 'blocked', 'cancelled')),
    priority integer not null default 3 check (priority between 1 and 5),
    payout_minor bigint not null default 0 check (payout_minor >= 0),
    due_at timestamptz,
    result jsonb not null default '{}'::jsonb check (jsonb_typeof(result) = 'object'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    submitted_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, assignee_id)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    unique (organization_id, idempotency_key),
    unique (organization_id, id)
);

create index if not exists creator_tasks_inbox_idx
  on content_factory.creator_tasks
  (organization_id, assignee_id, status, due_at, created_at desc);

create table if not exists content_factory.creator_payouts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    task_id uuid not null,
    amount_minor bigint not null check (amount_minor >= 0),
    currency text not null default 'RUB' check (currency ~ '^[A-Z]{3}$'),
    status text not null default 'pending'
      check (status in ('pending', 'approved', 'paid', 'rejected', 'cancelled')),
    reason text,
    approved_by uuid references content_factory.profiles(id),
    external_payment_reference text,
    approved_at timestamptz,
    paid_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, task_id)
      references content_factory.creator_tasks(organization_id, id),
    constraint creator_payouts_org_task_uq unique (organization_id, task_id)
);

create index if not exists creator_payouts_ledger_idx
  on content_factory.creator_payouts
  (organization_id, profile_id, status, created_at desc);

create table if not exists content_factory.placements (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    generation_job_id uuid,
    task_id uuid,
    assigned_to uuid not null,
    created_by uuid not null,
    platform text not null
      check (platform in ('instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries')),
    destination_ref text not null check (length(btrim(destination_ref)) between 2 and 240),
    status text not null default 'scheduled'
      check (status in ('scheduled', 'ready', 'published', 'failed', 'cancelled')),
    scheduled_at timestamptz,
    published_at timestamptz,
    tracking_url text,
    final_url text,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, task_id)
      references content_factory.creator_tasks(organization_id, id),
    foreign key (organization_id, assigned_to)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, id),
    unique (organization_id, task_id),
    check (tracking_url is null or tracking_url ~ '^https://'),
    check (final_url is null or final_url ~ '^https://')
);

create index if not exists placements_assignee_idx
  on content_factory.placements
  (organization_id, assigned_to, status, scheduled_at);

create table if not exists content_factory.metric_snapshots (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    placement_id uuid not null,
    collected_by uuid not null,
    source text not null check (source in ('manual', 'csv', 'official_api')),
    observed_at timestamptz not null,
    views bigint not null default 0 check (views >= 0),
    clicks bigint not null default 0 check (clicks >= 0),
    orders bigint not null default 0 check (orders >= 0),
    revenue_minor bigint not null default 0 check (revenue_minor >= 0),
    is_correction boolean not null default false,
    correction_reason text,
    raw jsonb not null default '{}'::jsonb check (jsonb_typeof(raw) = 'object'),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    created_at timestamptz not null default now(),
    foreign key (organization_id, placement_id)
      references content_factory.placements(organization_id, id),
    foreign key (organization_id, collected_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    check (not is_correction or length(btrim(correction_reason)) >= 5)
);

create index if not exists metric_snapshots_placement_idx
  on content_factory.metric_snapshots
  (organization_id, placement_id, observed_at desc, created_at desc);

create table if not exists content_factory.factory_events (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    event_name text not null check (event_name ~ '^[a-z0-9_]{3,100}$'),
    source text not null default 'server_rpc'
      check (source in ('server_rpc', 'client_rpc', 'system')),
    entity_type text,
    entity_id text,
    properties jsonb not null default '{}'::jsonb
      check (jsonb_typeof(properties) = 'object'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    occurred_at timestamptz not null default now(),
    received_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    constraint factory_events_org_key_uq unique (organization_id, idempotency_key)
);

create index if not exists factory_events_funnel_idx
  on content_factory.factory_events
  (organization_id, event_name, occurred_at desc);

create table if not exists content_factory.wb_article_aliases (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    alias_article text not null check (alias_article ~ '^[0-9]{4,20}$'),
    current_article text not null check (current_article ~ '^[0-9]{4,20}$'),
    status text not null default 'active'
      check (status in ('active', 'replaced', 'revoked')),
    valid_from timestamptz not null default now(),
    valid_to timestamptz,
    reason text,
    created_by uuid not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (alias_article <> current_article),
    check (valid_to is null or valid_to > valid_from)
);

create unique index if not exists wb_article_aliases_one_active_uq
  on content_factory.wb_article_aliases (organization_id, alias_article)
  where status = 'active';

create index if not exists wb_article_aliases_resolve_idx
  on content_factory.wb_article_aliases
  (organization_id, alias_article, status, valid_from desc);

create or replace function content_factory_private.guard_wb_alias_history()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (
    select 1
    from content_factory.wb_article_aliases existing
    where existing.organization_id = new.organization_id
      and existing.alias_article = new.alias_article
      and existing.product_id <> new.product_id
      and existing.id <> new.id
  ) then
    raise exception using
      errcode = '23505',
      message = 'wb_alias_product_immutable';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_wb_alias_history
  on content_factory.wb_article_aliases;
create trigger guard_wb_alias_history
before insert or update of organization_id, product_id, alias_article
on content_factory.wb_article_aliases
for each row execute function content_factory_private.guard_wb_alias_history();

create table if not exists content_factory.media_objects (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    owner_id uuid not null,
    task_id uuid,
    product_id uuid,
    bucket_id text not null default 'contentengine-private'
      check (bucket_id = 'contentengine-private'),
    object_name text not null check (length(object_name) between 10 and 1000),
    mime_type text not null check (length(mime_type) between 3 and 160),
    size_bytes bigint not null check (size_bytes between 1 and 52428800),
    sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
    status text not null default 'ready'
      check (status in ('uploading', 'ready', 'archived', 'deleted', 'failed')),
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, owner_id)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, task_id)
      references content_factory.creator_tasks(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    unique (bucket_id, object_name),
    unique (organization_id, idempotency_key),
    unique (organization_id, id),
    check (split_part(object_name, '/', 1) = organization_id::text),
    check (split_part(object_name, '/', 2) = owner_id::text)
);

create index if not exists media_objects_library_idx
  on content_factory.media_objects
  (organization_id, owner_id, status, created_at desc);

create table if not exists content_factory.feedback_requests (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    category text not null
      check (category in (
        'blocker', 'idea', 'data',
        'interface', 'generation', 'quality', 'funnel', 'social_data',
        'payouts', 'wb_aliases', 'analytics', 'training', 'other'
      )),
    title text not null check (length(btrim(title)) between 3 and 180),
    details text not null check (length(btrim(details)) between 5 and 4000),
    status text not null default 'new'
      check (status in ('new', 'reviewing', 'planned', 'done', 'rejected')),
    idempotency_key text not null check (length(idempotency_key) between 12 and 180),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key)
);

create index if not exists feedback_requests_queue_idx
  on content_factory.feedback_requests
  (organization_id, status, created_at desc);

create table if not exists content_factory.command_receipts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    actor_id uuid not null references content_factory.profiles(id),
    command_name text not null check (command_name ~ '^[a-z0-9_]{3,100}$'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    result jsonb not null check (jsonb_typeof(result) = 'object'),
    created_at timestamptz not null default now(),
    constraint command_receipts_org_command_key_uq
      unique (organization_id, command_name, idempotency_key)
);

create index if not exists command_receipts_actor_idx
  on content_factory.command_receipts
  (organization_id, actor_id, created_at desc);

create or replace function content_factory_private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create or replace function content_factory_private.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.profiles (id, email, display_name, metadata)
  values (
    new.id,
    lower(new.email),
    nullif(btrim(coalesce(new.raw_user_meta_data ->> 'display_name', '')), ''),
    jsonb_build_object('auth_provider', coalesce(new.raw_app_meta_data ->> 'provider', 'email'))
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = coalesce(content_factory.profiles.display_name, excluded.display_name),
        updated_at = now();
  return new;
exception
  when others then
    raise warning 'content_factory profile sync failed for auth user %: %', new.id, sqlerrm;
    return new;
end;
$$;

drop trigger if exists content_factory_profile_on_auth_user on auth.users;
create trigger content_factory_profile_on_auth_user
after insert or update of email, raw_user_meta_data on auth.users
for each row execute function content_factory_private.handle_new_auth_user();

create or replace function content_factory_private.guard_mock_generation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.mode <> 'mock'
     or new.provider <> 'mock'
     or new.allow_real_spend
     or new.estimated_cost_minor <> 0
     or new.actual_cost_minor <> 0 then
    raise exception using
      errcode = '42501',
      message = 'real_generation_is_disabled',
      detail = 'Only zero-cost mock generation is permitted by the database contract.';
  end if;
  return new;
end;
$$;

create or replace function content_factory_private.guard_mock_generation_batch()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.mode <> 'mock' or new.allow_real_spend then
    raise exception using
      errcode = '42501',
      message = 'real_generation_is_disabled',
      detail = 'Generation batches are permanently mock-only until a later audited migration changes the database contract.';
  end if;
  return new;
end;
$$;

drop trigger if exists generation_batches_mock_only_guard
  on content_factory.generation_batches;
create trigger generation_batches_mock_only_guard
before insert or update on content_factory.generation_batches
for each row execute function content_factory_private.guard_mock_generation_batch();

drop trigger if exists generation_jobs_mock_only_guard
  on content_factory.generation_jobs;
create trigger generation_jobs_mock_only_guard
before insert or update on content_factory.generation_jobs
for each row execute function content_factory_private.guard_mock_generation();

create or replace function content_factory_private.reject_factory_event_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'factory_events_are_append_only';
end;
$$;

drop trigger if exists factory_events_append_only_guard
  on content_factory.factory_events;
create trigger factory_events_append_only_guard
before update or delete on content_factory.factory_events
for each row execute function content_factory_private.reject_factory_event_mutation();

do $triggers$
declare
  target_table text;
begin
  foreach target_table in array array[
    'profiles', 'organizations', 'memberships', 'training_modules',
    'training_questions', 'products', 'generation_batches', 'generation_jobs',
    'creator_tasks', 'creator_payouts', 'placements', 'wb_article_aliases',
    'media_objects', 'feedback_requests'
  ]
  loop
    execute format('drop trigger if exists set_updated_at on content_factory.%I', target_table);
    execute format(
      'create trigger set_updated_at before update on content_factory.%I '
      'for each row execute function content_factory_private.set_updated_at()',
      target_table
    );
  end loop;
end;
$triggers$;

revoke all on all tables in schema content_factory_private from public, anon, authenticated;
revoke all on all functions in schema content_factory_private from public, anon, authenticated;

commit;

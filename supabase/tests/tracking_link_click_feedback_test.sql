begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(17);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'tracking-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Tracking Owner"}'::jsonb,
  now(),
  now()
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1',
    true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;

select ok(
  (public.system_initialize_owner(jsonb_build_object(
    'user_id', 'a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1',
    'idempotency_key', 'pgtap-tracking-owner-0001'
  )) ->> 'ok')::boolean,
  'tracking test owner initialization succeeds'
);

create temporary table tracking_test_context (
  organization_id uuid not null,
  profile_id uuid not null,
  product_id uuid not null,
  task_id uuid not null,
  placement_id uuid not null
) on commit drop;

insert into tracking_test_context (
  organization_id, profile_id, product_id, task_id, placement_id
)
select
  (bootstrap -> 'organization' ->> 'id')::uuid,
  'a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1'::uuid,
  'a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2'::uuid,
  'a3a3a3a3-a3a3-43a3-83a3-a3a3a3a3a3a3'::uuid,
  'a4a4a4a4-a4a4-44a4-84a4-a4a4a4a4a4a4'::uuid
from (select public.creator_bootstrap('{}'::jsonb) as bootstrap) response;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
select
  context.product_id,
  context.organization_id,
  'TRACK-SKU-1',
  'Tracking product',
  'active',
  '{}'::jsonb,
  context.profile_id
from tracking_test_context context;

insert into content_factory.creator_tasks (
  id, organization_id, assignee_id, created_by, product_id,
  task_type, title, instructions, status, idempotency_key,
  completed_at
)
select
  context.task_id,
  context.organization_id,
  context.profile_id,
  context.profile_id,
  context.product_id,
  'placement',
  'Publish tracking fixture',
  'Use the first-party tracking link.',
  'done',
  'pgtap-tracking-task-0001',
  now()
from tracking_test_context context;

insert into content_factory.placements (
  id, organization_id, product_id, task_id, assigned_to, created_by,
  platform, destination_ref, status, published_at, final_url,
  request_hash, idempotency_key, metadata
)
select
  context.placement_id,
  context.organization_id,
  context.product_id,
  context.task_id,
  context.profile_id,
  context.profile_id,
  'youtube',
  '@tracking-owner',
  'published',
  now() - interval '1 hour',
  'https://www.youtube.com/shorts/tracking-fixture',
  repeat('1', 64),
  'pgtap-tracking-placement-0001',
  '{}'::jsonb
from tracking_test_context context;

create temporary table tracking_configuration (
  result jsonb not null
) on commit drop;

insert into tracking_configuration (result)
select public.creator_configure_tracking_link(jsonb_build_object(
  'organization_id', context.organization_id,
  'placement_id', context.placement_id,
  'target_url', 'https://shop.example/products/tracking-fixture',
  'idempotency_key', 'pgtap-configure-tracking-link-0001'
))
from tracking_test_context context;

select matches(
  (select result ->> 'tracking_slug' from tracking_configuration),
  '^ce1_[0-9a-f]{24}$',
  'configuration creates an unguessable bounded slug'
);

select is(
  (select result ->> 'target_url' from tracking_configuration),
  'https://shop.example/products/tracking-fixture',
  'configuration preserves the exact reviewed HTTPS target'
);

select is(
  (
    select placement.metadata ->> 'tracking_version'
    from content_factory.placements placement
    join tracking_test_context context
      on context.placement_id = placement.id
  ),
  'tracking-v1',
  'placement records the tracking contract version'
);

create temporary table tracking_click_results (
  position integer primary key,
  result jsonb not null
) on commit drop;

insert into tracking_click_results (position, result)
select
  1,
  public.system_record_public_tracking_click(jsonb_build_object(
    'slug', configuration.result ->> 'tracking_slug',
    'user_agent', 'Mozilla/5.0 Test Browser',
    'accept_language', 'ru-RU',
    'visitor_token', 'tracking-human-visitor-0001',
    'referrer_origin', 'https://youtube.example'
  ))
from tracking_configuration configuration;

insert into tracking_click_results (position, result)
select
  2,
  public.system_record_public_tracking_click(jsonb_build_object(
    'slug', configuration.result ->> 'tracking_slug',
    'user_agent', 'Mozilla/5.0 Test Browser',
    'accept_language', 'ru-RU',
    'visitor_token', 'tracking-human-visitor-0001',
    'referrer_origin', 'https://youtube.example'
  ))
from tracking_configuration configuration;

insert into tracking_click_results (position, result)
select
  3,
  public.system_record_public_tracking_click(jsonb_build_object(
    'slug', configuration.result ->> 'tracking_slug',
    'user_agent', 'TelegramBot (like TwitterBot)',
    'accept_language', 'en',
    'visitor_token', 'tracking-preview-bot-0002',
    'referrer_origin', 'https://telegram.example'
  ))
from tracking_configuration configuration;

select is(
  (select result ->> 'disposition'
   from tracking_click_results where position = 1),
  'recorded',
  'the first human redirect records one bounded event'
);

select is(
  (select result ->> 'disposition'
   from tracking_click_results where position = 2),
  'duplicate',
  'a fast repeat from the same visitor does not grow telemetry'
);

select is(
  (select result ->> 'accepted_for_human_kpi'
   from tracking_click_results where position = 2),
  'false',
  'a fast repeat is explicitly outside the human KPI'
);

select is(
  (select result ->> 'accepted_for_human_kpi'
   from tracking_click_results where position = 3),
  'false',
  'social preview traffic is classified outside the human KPI'
);

select is(
  (
    select count(*)::integer
    from content_factory.tracking_clicks click
    join tracking_test_context context
      on context.organization_id = click.organization_id
     and context.placement_id = click.placement_id
    where click.accepted_for_human_kpi
  ),
  1,
  'only one deduplicated human click is accepted'
);

select is(
  (
    select count(*)::integer
    from content_factory.tracking_clicks click
    join tracking_test_context context
      on context.organization_id = click.organization_id
     and context.placement_id = click.placement_id
    where click.classification = 'bot'
  ),
  1,
  'bot observations remain auditable but excluded'
);

select ok(
  not exists (
    select 1
    from content_factory.tracking_clicks click
    where click.metadata::text ilike '%Mozilla%'
       or click.metadata::text ilike '%tracking-human-visitor%'
       or click.referrer_origin like '%/shorts/%'
  ),
  'raw user agent, visitor token and referrer path are never persisted'
);

insert into content_factory.metric_snapshots (
  organization_id, placement_id, collected_by, source, observed_at,
  views, clicks, orders, revenue_minor, raw, request_hash,
  idempotency_key
)
select
  context.organization_id,
  context.placement_id,
  context.profile_id,
  'manual',
  now(),
  200,
  0,
  2,
  50000,
  '{"source":"pgtap"}'::jsonb,
  repeat('2', 64),
  'pgtap-tracking-metric-0001'
from tracking_test_context context;

create temporary table tracking_placement_workspace (
  result jsonb not null
) on commit drop;
insert into tracking_placement_workspace (result)
select public.creator_workspace_section(jsonb_build_object(
  'organization_id', context.organization_id,
  'section', 'placement'
))
from tracking_test_context context;

select is(
  (
    select item ->> 'tracked_clicks'
    from tracking_placement_workspace workspace,
      lateral jsonb_array_elements(workspace.result -> 'placements') item
    limit 1
  ),
  '1',
  'placement workspace exposes the live human click count'
);

create temporary table tracking_stats_workspace (
  result jsonb not null
) on commit drop;
insert into tracking_stats_workspace (result)
select public.creator_workspace_section(jsonb_build_object(
  'organization_id', context.organization_id,
  'section', 'stats'
))
from tracking_test_context context;

select is(
  (
    select item ->> 'clicks'
    from tracking_stats_workspace workspace,
      lateral jsonb_array_elements(workspace.result -> 'publications') item
    limit 1
  ),
  '1',
  'stats uses the greater automatic human click count'
);

select is(
  (select result #>> '{summary,ctr}' from tracking_stats_workspace),
  '0.50',
  'page CTR is recomputed from automatic clicks and confirmed views'
);

select throws_ok(
  $$
    select public.creator_configure_tracking_link(jsonb_build_object(
      'organization_id', context.organization_id,
      'placement_id', context.placement_id,
      'target_url', 'https://shop.example/products/changed-target',
      'idempotency_key', 'pgtap-configure-tracking-link-0002'
    ))
    from tracking_test_context context
  $$,
  '55000',
  'tracking_link_target_immutable',
  'a published capability cannot silently change its redirect target'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.system_record_public_tracking_click(jsonb)',
    'execute'
  ),
  'only the service-role Edge Function can write public click telemetry'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_configure_tracking_link(jsonb)',
    'execute'
  ),
  'authenticated workspace members retain the audited configuration RPC'
);

select * from finish();
rollback;

-- Live, rollback-only smoke test for creator_generation_learning_policy.
--
-- Preconditions:
--   * the UX-TEST-20260724 product/media fixture exists;
--   * its owner has an active, generation-eligible membership;
--   * the organization has an active generation campaign.
--
-- The test temporarily disables user triggers while inserting synthetic
-- succeeded jobs so it cannot reserve real spend. Every inserted row and the
-- profile refresh performed by the RPC are rolled back at the end.
begin;

set local session_replication_role = replica;

do $smoke$
declare
  actor_id uuid;
  organization_id uuid;
  product_id uuid;
  source_media_id uuid;
  source_sha256 text;
  campaign_id uuid;
  batch_id uuid := extensions.gen_random_uuid();
  review_id uuid := extensions.gen_random_uuid();
  completion_hash text := repeat('c', 64);
  job_id uuid;
  placement_id uuid;
  policy jsonb;
  run_token text := replace(extensions.gen_random_uuid()::text, '-', '');
  position integer;
  angle text;
  patterns jsonb;
  clicks bigint;
  orders bigint;
begin
  select
    media.owner_id,
    media.organization_id,
    product.id,
    media.id,
    media.sha256,
    campaign.id
  into
    actor_id,
    organization_id,
    product_id,
    source_media_id,
    source_sha256,
    campaign_id
  from content_factory.media_objects media
  join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
   and product.sku = 'UX-TEST-20260724'
  join content_factory.memberships membership
    on membership.organization_id = media.organization_id
   and membership.profile_id = media.owner_id
   and membership.status = 'active'
  join content_factory.generation_campaigns campaign
    on campaign.organization_id = media.organization_id
   and campaign.status = 'active'
  where media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed'
      is not distinct from 'true'::jsonb
  order by
    (campaign.kind = 'default') desc,
    media.created_at desc,
    media.id desc
  limit 1;

  if actor_id is null
     or organization_id is null
     or product_id is null
     or source_media_id is null
     or campaign_id is null then
    raise exception using
      errcode = 'P0001',
      message = 'generation_learning_live_fixture_missing';
  end if;

  insert into content_factory.generation_batches (
    id,
    organization_id,
    product_id,
    created_by,
    name,
    mode,
    allow_real_spend,
    provider,
    model,
    duration_seconds,
    audio,
    estimated_cost_minor,
    estimated_credits,
    currency,
    campaign_id,
    status,
    total_requested,
    total_created,
    input,
    request_hash,
    idempotency_key
  ) values (
    batch_id,
    organization_id,
    product_id,
    actor_id,
    'Learning live smoke',
    'real',
    true,
    'runway',
    'seedream5_lite',
    0,
    false,
    4,
    4,
    'USD',
    campaign_id,
    'succeeded',
    6,
    6,
    jsonb_build_object('test_only', true),
    repeat('b', 64),
    'learning-live-batch-' || run_token
  );

  insert into content_factory.content_review_runs (
    id,
    organization_id,
    media_object_id,
    requested_by,
    status,
    media_sha256_snapshot,
    input,
    result,
    moderation,
    ruleset_version,
    model_provider,
    model_version,
    request_hash,
    completion_hash,
    idempotency_key,
    finished_at
  ) values (
    review_id,
    organization_id,
    source_media_id,
    actor_id,
    'completed',
    source_sha256,
    jsonb_build_object('test_only', true),
    jsonb_build_object('overall_score', 99),
    '{}'::jsonb,
    'learning-live-v1',
    'test',
    '1',
    repeat('d', 64),
    completion_hash,
    'learning-live-review-' || run_token,
    now()
  );

  insert into content_factory.content_review_decisions (
    organization_id,
    review_id,
    decided_by,
    decision,
    comment,
    resolved_recommendation_codes,
    risk_acknowledgements,
    media_watched_confirmed,
    review_completion_hash,
    media_sha256_snapshot,
    idempotency_key
  ) values (
    organization_id,
    review_id,
    actor_id,
    'approved',
    'Rollback-only learning smoke approval.',
    '[]'::jsonb,
    '[]'::jsonb,
    true,
    completion_hash,
    source_sha256,
    'learning-live-decision-' || run_token
  );

  for position in 1..6 loop
    job_id := extensions.gen_random_uuid();
    placement_id := extensions.gen_random_uuid();
    if position <= 3 then
      angle := 'trust_builder';
      patterns := '["why_explanation","concise"]'::jsonb;
      clicks := 110 - position * 10;
      orders := 55 - position * 5;
    else
      angle := 'comparison';
      patterns := '["comparison"]'::jsonb;
      clicks := (position - 3) * 10;
      orders := position - 3;
    end if;

    insert into content_factory.generation_jobs (
      id,
      organization_id,
      product_id,
      batch_id,
      ordinal,
      requested_by,
      assigned_to,
      mode,
      provider,
      allow_real_spend,
      campaign_id,
      estimated_cost_minor,
      actual_cost_minor,
      status,
      input,
      output,
      request_hash,
      idempotency_key
    ) values (
      job_id,
      organization_id,
      product_id,
      batch_id,
      position,
      actor_id,
      actor_id,
      'real',
      'runway',
      true,
      campaign_id,
      4,
      4,
      'succeeded',
      jsonb_build_object(
        'model', 'seedream5_lite',
        'duration_seconds', 0,
        'audio', false,
        'format', '1:1',
        'prompt_text', 'rollback-only structural learning smoke'
      ),
      jsonb_build_object('output_media_id', source_media_id),
      repeat(position::text, 64),
      'learning-live-job-' || run_token || '-' || position
    );

    insert into content_factory.generation_creative_signals (
      organization_id,
      generation_job_id,
      product_id,
      platform,
      model,
      creative_angle,
      hook_patterns,
      source,
      compiler_version,
      prompt_hash
    ) values (
      organization_id,
      job_id,
      product_id,
      'tiktok',
      'seedream5_lite',
      angle,
      patterns,
      'baseline',
      'safe-brief-v2',
      repeat(position::text, 64)
    );

    insert into content_factory.placements (
      id,
      organization_id,
      product_id,
      generation_job_id,
      assigned_to,
      created_by,
      platform,
      destination_ref,
      status,
      published_at,
      request_hash,
      idempotency_key,
      metadata
    ) values (
      placement_id,
      organization_id,
      product_id,
      job_id,
      actor_id,
      actor_id,
      'tiktok',
      '@learning_live_smoke',
      'published',
      now(),
      repeat(position::text, 64),
      'learning-live-placement-' || run_token || '-' || position,
      jsonb_build_object('test_only', true)
    );

    insert into content_factory.metric_snapshots (
      organization_id,
      placement_id,
      collected_by,
      source,
      observed_at,
      views,
      clicks,
      orders,
      revenue_minor,
      raw,
      request_hash,
      idempotency_key
    ) values (
      organization_id,
      placement_id,
      actor_id,
      'manual',
      now(),
      1000,
      clicks,
      orders,
      orders * 1000,
      jsonb_build_object('test_only', true),
      repeat(position::text, 64),
      'learning-live-metric-' || run_token || '-' || position
    );
  end loop;

  perform set_config(
    'request.jwt.claims',
    jsonb_build_object('sub', actor_id, 'role', 'authenticated')::text,
    true
  );

  policy := public.creator_generation_learning_policy(
    jsonb_build_object(
      'organization_id', organization_id,
      'media_id', source_media_id,
      'platform', 'tiktok',
      'model', 'seedream5_lite'
    )
  );

  if policy ->> 'applied' <> 'true'
     or policy ->> 'confidence' <> 'medium'
     or policy ->> 'preferred_angle' <> 'trust_builder'
     or policy ->> 'avoid_angle' <> 'comparison'
     or (policy ->> 'evidence_count')::integer <> 6
     or policy ->> 'scope' <> 'product_platform'
     or not (policy -> 'preferred_hook_patterns' ? 'why_explanation')
     or jsonb_array_length(policy -> 'source_job_ids') <> 3
     or not (policy -> 'reason_codes' ? 'stable_relative_performance_signal')
     or not (policy -> 'reason_codes' ? 'platform_specific_evidence')
     or policy #>> '{safety,claims_are_never_learned}' <> 'true'
     or policy #>> '{safety,product_identity_is_immutable}' <> 'true'
     or policy #>> '{safety,rights_are_immutable}' <> 'true'
     or policy #>> '{safety,format_and_spend_are_immutable}' <> 'true' then
    raise exception using
      errcode = 'P0001',
      message = 'generation_learning_live_policy_mismatch',
      detail = policy::text;
  end if;

  perform set_config(
    'app.generation_learning_live_smoke',
    jsonb_build_object(
      'passed', true,
      'applied', policy -> 'applied',
      'confidence', policy -> 'confidence',
      'evidence_count', policy -> 'evidence_count',
      'preferred_angle', policy -> 'preferred_angle',
      'avoid_angle', policy -> 'avoid_angle',
      'scope', policy -> 'scope',
      'reason_codes', policy -> 'reason_codes'
    )::text,
    true
  );
end;
$smoke$;

select current_setting('app.generation_learning_live_smoke')::jsonb
  as generation_learning_live_smoke;

rollback;

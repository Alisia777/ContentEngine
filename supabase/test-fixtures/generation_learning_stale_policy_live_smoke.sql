-- Rollback-only proof that a stale/tampered learning policy is rejected before
-- any paid generation row or spend reservation can be created.
begin;

do $smoke$
declare
  actor_id uuid;
  target_organization_id uuid;
  media_id uuid;
  batch_count_before bigint;
  job_count_before bigint;
  spend_count_before bigint;
begin
  select
    media.owner_id,
    media.organization_id,
    media.id
  into actor_id, target_organization_id, media_id
  from content_factory.media_objects media
  join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
   and product.sku = 'UX-TEST-20260724'
  join content_factory.memberships membership
    on membership.organization_id = media.organization_id
   and membership.profile_id = media.owner_id
   and membership.status = 'active'
  where media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed'
      is not distinct from 'true'::jsonb
  order by media.created_at desc, media.id desc
  limit 1;

  if actor_id is null
     or target_organization_id is null
     or media_id is null then
    raise exception using
      errcode = 'P0001',
      message = 'generation_learning_live_fixture_missing';
  end if;

  select count(*) into batch_count_before
  from content_factory.generation_batches
  where generation_batches.organization_id = target_organization_id;
  select count(*) into job_count_before
  from content_factory.generation_jobs
  where generation_jobs.organization_id = target_organization_id;
  select count(*) into spend_count_before
  from content_factory.generation_spend_ledger
  where generation_spend_ledger.organization_id = target_organization_id;

  perform set_config(
    'request.jwt.claims',
    jsonb_build_object('sub', actor_id, 'role', 'authenticated')::text,
    true
  );

  begin
    perform public.creator_start_real_generation(
      jsonb_build_object(
        'organization_id', target_organization_id,
        'media_ids', jsonb_build_array(media_id),
        'platform', 'tiktok',
        'model', 'seedream5_lite',
        'learning_context', jsonb_build_object(
          'creative_angle', 'trust_builder',
          'hook_patterns', jsonb_build_array('why_explanation'),
          'source', 'performance_learning',
          'compiler_version', 'safe-brief-v2',
          'applied_policy_hash', repeat('a', 64)
        )
      )
    );
    raise exception using
      errcode = 'P0001',
      message = 'generation_learning_stale_policy_was_accepted';
  exception
    when sqlstate '55000' then
      if sqlerrm <> 'generation_learning_policy_stale' then
        raise;
      end if;
  end;

  if (
    select count(*)
    from content_factory.generation_batches
    where generation_batches.organization_id = target_organization_id
  ) <> batch_count_before
     or (
       select count(*)
       from content_factory.generation_jobs
       where generation_jobs.organization_id = target_organization_id
     ) <> job_count_before
     or (
       select count(*)
       from content_factory.generation_spend_ledger
       where generation_spend_ledger.organization_id = target_organization_id
     ) <> spend_count_before then
    raise exception using
      errcode = 'P0001',
      message = 'generation_learning_stale_policy_created_paid_state';
  end if;

  perform set_config(
    'app.generation_learning_stale_policy_live_smoke',
    jsonb_build_object(
      'passed', true,
      'rejected_with', 'generation_learning_policy_stale',
      'paid_state_created', false
    )::text,
    true
  );
end;
$smoke$;

select current_setting(
  'app.generation_learning_stale_policy_live_smoke'
)::jsonb as generation_learning_stale_policy_live_smoke;

rollback;

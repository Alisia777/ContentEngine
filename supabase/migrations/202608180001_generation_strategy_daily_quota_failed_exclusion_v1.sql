begin;

-- 202608180001_generation_strategy_daily_quota_failed_exclusion_v1
-- The rolling 24h per-user/per-org daily quotas in
-- system_claim_generation_strategy_start counted failed jobs, so a day of
-- diagnosed-and-refunded failures (17.08: 8 failed + 2 succeeded) blocked
-- every new paid start with real_generation_user_daily_quota_exceeded (54000)
-- which the edge maps to an opaque 503. Failed jobs hold no money (reserves
-- are released by reconciliation) and no provider task, so they no longer
-- count toward the daily quotas. Concurrency checks are unchanged.
-- Function body is otherwise byte-identical to 202608130007.

create or replace function public.system_claim_generation_strategy_start(
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
  organization_id_value uuid;
  project_id_value uuid;
  actor_id_value uuid;
  campaign_id_value uuid;
  receipt_id_value uuid;
  binding_id_value uuid;
  receipt_hash_value text;
  binding_hash_value text;
  selection_hash_value text;
  price_hash_value text;
  spend_confirmation_value text;
  idempotency_key_value text;
  request_hash_value text;
  claim_hash_value text;
  claim_id_value uuid := extensions.gen_random_uuid();
  batch_id_value uuid := extensions.gen_random_uuid();
  job_id_value uuid := extensions.gen_random_uuid();
  task_id_value uuid := extensions.gen_random_uuid();
  estimated_cost_value bigint;
  estimated_credits_value bigint;
  output_object_name_value text;
  input_object_name_value text;
  input_media_id_value uuid;
  reference_media_ids_value jsonb;
  reference_object_names_value jsonb;
  ratio_value text;
  resolution_value text;
  strategy_input_mode_value text;
  strategy_prompt_text_value text;
  strategy_technical_value jsonb;
  strategy_duration_value integer;
  strategy_audio_value boolean;
  batch_input_value jsonb;
  job_input_value jsonb;
  execution_value jsonb;
  asset_context_value jsonb;
  user_daily_jobs integer;
  organization_daily_jobs integer;
  assignee_open_jobs integer;
  organization_open_jobs integer;
  receipt_row
    content_factory.generation_strategy_readiness_receipts%rowtype;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  product_row content_factory.products%rowtype;
  existing_row content_factory.generation_strategy_start_claims%rowtype;
  claim_row content_factory.generation_strategy_start_claims%rowtype;
  job_strategy_row
    content_factory.generation_job_strategy_snapshots%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'receipt_id',
       'receipt_hash', 'binding_id', 'binding_hash', 'selection_hash',
       'price_hash', 'spend_confirmation', 'campaign_id', 'confirmation',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id', 'receipt_id',
       'receipt_hash', 'binding_id', 'binding_hash', 'selection_hash',
       'price_hash', 'spend_confirmation', 'campaign_id', 'confirmation',
       'idempotency_key'
     ]::text[]
     or p_payload ->> 'version' <>
       'generation-strategy-start-claim-request-v1'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using errcode = '22023',
      message = 'generation_strategy_start_claim_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');
  campaign_id_value := content_factory_private.require_uuid(
    p_payload, 'campaign_id'
  );
  receipt_id_value := content_factory_private.require_uuid(
    p_payload, 'receipt_id'
  );
  binding_id_value := content_factory_private.require_uuid(
    p_payload, 'binding_id'
  );
  receipt_hash_value := lower(btrim(p_payload ->> 'receipt_hash'));
  binding_hash_value := lower(btrim(p_payload ->> 'binding_hash'));
  selection_hash_value := lower(btrim(p_payload ->> 'selection_hash'));
  price_hash_value := lower(btrim(p_payload ->> 'price_hash'));
  spend_confirmation_value := btrim(p_payload ->> 'spend_confirmation');
  idempotency_key_value := btrim(p_payload ->> 'idempotency_key');
  if receipt_hash_value !~ '^[0-9a-f]{64}$'
     or binding_hash_value !~ '^[0-9a-f]{64}$'
     or selection_hash_value !~ '^[0-9a-f]{64}$'
     or price_hash_value !~ '^[0-9a-f]{64}$'
     or length(spend_confirmation_value) not between 20 and 180
     or length(idempotency_key_value) not between 8 and 180
     or idempotency_key_value ~ '[[:cntrl:]]' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_start_claim_payload_invalid';
  end if;
  perform 1
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id and profile.status = 'active'
  where membership.organization_id = organization_id_value
    and membership.profile_id = actor_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin', 'producer', 'operator');
  if not found
     or not content_factory_private.workspace_project_access_allowed(
       organization_id_value, project_id_value, actor_id_value
     ) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_start_claim_access_required';
  end if;
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-strategy-start:' || receipt_id_value::text)
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('real_generation_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text || ':' || actor_id_value::text),
    hashtext('real_generation_quota:user')
  );
  request_hash_value := content_factory_private.json_hash(p_payload);
  select claim.* into existing_row
  from content_factory.generation_strategy_start_claims claim
  where claim.organization_id = organization_id_value
    and (
      claim.readiness_receipt_id = receipt_id_value
      or claim.idempotency_key = idempotency_key_value
    );
  if existing_row.id is not null then
    if existing_row.request_hash <> request_hash_value then
      raise exception using errcode = '55000',
        message = 'generation_strategy_start_claim_idempotency_conflict';
    end if;
    select receipt.* into receipt_row
    from content_factory.generation_strategy_readiness_receipts receipt
    where receipt.organization_id = organization_id_value
      and receipt.id = existing_row.readiness_receipt_id;
    select snapshot.* into job_strategy_row
    from content_factory.generation_job_strategy_snapshots snapshot
    where snapshot.organization_id = organization_id_value
      and snapshot.generation_job_id = existing_row.generation_job_id;
    return jsonb_build_object(
      'ok', true,
      'version', 'generation-strategy-start-claim-response-v1',
      'claimed', false,
      'replay', true,
      'claim', jsonb_build_object(
        'id', existing_row.id,
        'claim_hash', existing_row.claim_hash,
        'batch_id', existing_row.batch_id,
        'generation_job_id', existing_row.generation_job_id,
        'review_task_id', existing_row.review_task_id,
        'claimed_at', existing_row.claimed_at
      ),
      'job', jsonb_build_object(
        'id', existing_row.generation_job_id,
        'batch_id', existing_row.batch_id,
        'status', (
          select job.status
          from content_factory.generation_jobs job
          where job.organization_id = organization_id_value
            and job.id = existing_row.generation_job_id
        ),
        'output_object_name', (
          select job.input ->> 'output_object_name'
          from content_factory.generation_jobs job
          where job.organization_id = organization_id_value
            and job.id = existing_row.generation_job_id
        ),
        'estimated_cost_minor',
          (receipt_row.price_snapshot ->> 'estimated_cost_minor')::bigint,
        'estimated_credits',
          (receipt_row.price_snapshot ->> 'estimated_credits')::bigint,
        'currency', 'USD',
        'campaign_id', existing_row.campaign_id,
        'model_identity', receipt_row.recipe,
        'duration_seconds',
          (receipt_row.selection_snapshot ->> 'duration_seconds')::integer,
        'audio', (receipt_row.selection_snapshot ->> 'audio')::boolean,
        'ratio', receipt_row.price_snapshot -> 'ratio',
        'resolution', receipt_row.price_snapshot -> 'resolution'
      ),
      'strategy', jsonb_build_object(
        'version', 'generation-strategy-immutable-execution-v1',
        'strategy_id', receipt_row.strategy_id,
        'recipe', receipt_row.recipe,
        'catalog_version', receipt_row.catalog_version,
        'recipe_version', receipt_row.recipe_version,
        'pricing_version', receipt_row.pricing_version,
        'binding_id', receipt_row.spec_strategy_binding_id,
        'binding_hash', receipt_row.binding_hash,
        'receipt_id', receipt_row.id,
        'receipt_hash', receipt_row.receipt_hash,
        'selection_hash', receipt_row.selection_hash,
        'price_hash', receipt_row.price_hash,
        'strategy_prompt_hash', receipt_row.strategy_prompt_hash,
        'spend_confirmation', receipt_row.spend_confirmation,
        'campaign_id', existing_row.campaign_id,
        'job_strategy_snapshot_id', job_strategy_row.id,
        'job_strategy_snapshot_hash', job_strategy_row.strategy_snapshot_hash
      ),
      'selection', receipt_row.selection_snapshot,
      'price', receipt_row.price_snapshot - 'spend_confirmation',
      'recipe_context', jsonb_build_object(
        'strategyVersion', receipt_row.catalog_version,
        'strategyId', receipt_row.strategy_id,
        'recipe', receipt_row.recipe,
        'recipeVersion', receipt_row.recipe_version,
        'durationSeconds',
          (receipt_row.selection_snapshot ->> 'duration_seconds')::integer,
        'audio', (receipt_row.selection_snapshot ->> 'audio')::boolean,
        'ratio', to_jsonb(receipt_row.price_snapshot ->> 'ratio'),
        'resolution', to_jsonb(receipt_row.price_snapshot ->> 'resolution'),
        'productInfo',
          receipt_row.strategy_prompt_snapshot ->> 'product_info',
        'productInfoHash',
          receipt_row.strategy_prompt_snapshot ->> 'product_info_hash',
        'userConcept',
          receipt_row.strategy_prompt_snapshot -> 'user_concept',
        'userConceptHash',
          receipt_row.strategy_prompt_snapshot -> 'user_concept_hash'
      ),
      'asset_context',
        content_factory_private.generation_strategy_asset_context(
          organization_id_value, receipt_row.id
        ),
      'contract', jsonb_build_object(
        'provider_call_started', false,
        'dispatch_attempt_required', true,
        'dispatch_post_allowed', false,
        'review_mode', 'manual_human_review',
        'review_autostart_confirmed', false,
        'signed_urls_persisted', false,
        'browser_prompt_authority', false
      )
    );
  end if;

  select receipt.* into receipt_row
  from content_factory.generation_strategy_readiness_receipts receipt
  where receipt.organization_id = organization_id_value
    and receipt.project_id = project_id_value
    and receipt.id = receipt_id_value
    and receipt.receipt_hash = receipt_hash_value
    and receipt.checked_by = actor_id_value
    and receipt.spec_strategy_binding_id = binding_id_value
    and receipt.binding_hash = binding_hash_value
    and receipt.selection_hash = selection_hash_value
    and receipt.price_hash = price_hash_value
    and receipt.spend_confirmation = spend_confirmation_value
    and receipt.ready
    and receipt.expires_at > statement_timestamp()
  for share;
  if receipt_row.id is null then
    raise exception using errcode = '55000',
      message = 'generation_strategy_start_receipt_not_current';
  end if;
  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.id = binding_id_value
    and binding.binding_hash = binding_hash_value
    and binding.confirmed_by = actor_id_value;
  if binding_row.id is null
     or not content_factory_private.generation_strategy_binding_current(
       organization_id_value, binding_id_value
     )
     or receipt_row.selection_snapshot is distinct from (
       select snapshot.selection_snapshot
       from content_factory.generation_strategy_binding_selections snapshot
       where snapshot.organization_id = organization_id_value
         and snapshot.id = receipt_row.binding_selection_id
     )
     or content_factory_private.generation_strategy_prompt_snapshot(
       organization_id_value, binding_id_value, receipt_row.selection_snapshot
     ) is distinct from receipt_row.strategy_prompt_snapshot then
    raise exception using errcode = '55000',
      message = 'generation_strategy_start_binding_not_current';
  end if;
  perform 1
  from content_factory.generation_spec_head_events head
  where head.organization_id = organization_id_value
    and head.spec_id = binding_row.spec_id
    and head.spec_version = binding_row.spec_version
    and head.spec_hash = binding_row.spec_hash
    and head.state = 'approved'
    and not exists (
      select 1 from content_factory.generation_spec_head_events later
      where later.organization_id = head.organization_id
        and later.spec_id = head.spec_id
        and later.event_sequence > head.event_sequence
    );
  if not found then
    raise exception using errcode = '55000',
      message = 'generation_strategy_start_spec_not_approved';
  end if;
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = binding_row.spec_id
    and version.spec_version = binding_row.spec_version
    and version.spec_hash = binding_row.spec_hash;
  select product.* into product_row
  from content_factory.products product
  where product.organization_id = organization_id_value
    and product.id = binding_row.product_id
    and product.status = 'active';
  if spec_row.version_id is null or product_row.id is null then
    raise exception using errcode = '55000',
      message = 'generation_strategy_start_scope_not_current';
  end if;
  -- Failed jobs hold no provider task and their reserves are released by
  -- reconciliation, so they do not consume the rolling daily quotas; the
  -- concurrency checks below still see every open job.
  select count(*) filter (where job.requested_by = actor_id_value), count(*)
    into user_daily_jobs, organization_daily_jobs
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.mode = 'real'
    and job.status <> 'failed'
    and job.created_at >= now() - interval '24 hours';
  select count(*) filter (where job.assigned_to = actor_id_value), count(*)
    into assignee_open_jobs, organization_open_jobs
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.mode = 'real'
    and job.status in ('queued', 'starting', 'submitted', 'processing');
  if user_daily_jobs >= 10 then
    raise exception using errcode = '54000',
      message = 'real_generation_user_daily_quota_exceeded';
  elsif organization_daily_jobs >= 50 then
    raise exception using errcode = '54000',
      message = 'real_generation_organization_daily_quota_exceeded';
  elsif assignee_open_jobs >= 1 then
    raise exception using errcode = '54000',
      message = 'real_generation_assignee_concurrency_exceeded';
  elsif organization_open_jobs >= 3 then
    raise exception using errcode = '54000',
      message = 'real_generation_organization_concurrency_exceeded';
  end if;

  estimated_cost_value :=
    (receipt_row.price_snapshot ->> 'estimated_cost_minor')::bigint;
  estimated_credits_value :=
    (receipt_row.price_snapshot ->> 'estimated_credits')::bigint;
  strategy_duration_value :=
    (receipt_row.selection_snapshot ->> 'duration_seconds')::integer;
  strategy_audio_value :=
    (receipt_row.selection_snapshot ->> 'audio')::boolean;
  strategy_input_mode_value := case receipt_row.strategy_id
    when 'viral_product_swap' then 'video' else 'image' end;
  ratio_value := receipt_row.price_snapshot ->> 'ratio';
  resolution_value := receipt_row.price_snapshot ->> 'resolution';
  strategy_prompt_text_value := coalesce(
    nullif(receipt_row.strategy_prompt_snapshot ->> 'user_concept', ''),
    receipt_row.strategy_prompt_snapshot ->> 'product_info'
  );
  strategy_technical_value := jsonb_build_object(
    'version', 'generation-strategy-technical-v1',
    'model_identity', receipt_row.recipe,
    'recipe', receipt_row.recipe,
    'duration_seconds', strategy_duration_value,
    'audio', strategy_audio_value,
    'input_mode', strategy_input_mode_value,
    'ratio', ratio_value,
    'resolution', resolution_value
  );
  output_object_name_value := organization_id_value::text || '/' ||
    actor_id_value::text || '/generated/strategy/' || job_id_value::text ||
    '.mp4';
  asset_context_value :=
    content_factory_private.generation_strategy_asset_context(
      organization_id_value, receipt_id_value
    );
  if jsonb_array_length(asset_context_value) <> (case receipt_row.strategy_id
       when 'viral_avatar_ugc' then 2
       when 'viral_product_swap' then
         jsonb_array_length(receipt_row.selection_snapshot -> 'assets')
       else jsonb_array_length(receipt_row.selection_snapshot -> 'assets') - 1
     end) then
    raise exception using errcode = '55000',
      message = 'generation_strategy_asset_context_invalid';
  end if;
  select
    (item.value ->> 'media_object_id')::uuid,
    item.value ->> 'object_name'
    into input_media_id_value, input_object_name_value
  from jsonb_array_elements(asset_context_value) with ordinality
    item(value, ordinal)
  order by item.ordinal
  limit 1;
  select
    coalesce(jsonb_agg(item.value -> 'media_object_id'
      order by item.ordinal), '[]'::jsonb),
    coalesce(jsonb_agg(item.value -> 'object_name'
      order by item.ordinal), '[]'::jsonb)
    into reference_media_ids_value, reference_object_names_value
  from jsonb_array_elements(asset_context_value) with ordinality
    item(value, ordinal);
  if input_media_id_value is null or input_object_name_value is null
     or jsonb_array_length(reference_media_ids_value) = 0
     or jsonb_array_length(reference_object_names_value) <>
          jsonb_array_length(reference_media_ids_value) then
    raise exception using errcode = '55000',
      message = 'generation_strategy_asset_context_invalid';
  end if;
  claim_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'generation-strategy-start-claim-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'actor_id', actor_id_value,
    'readiness_receipt_id', receipt_id_value,
    'receipt_hash', receipt_hash_value,
    'spec_strategy_binding_id', binding_id_value,
    'binding_hash', binding_hash_value,
    'selection_hash', selection_hash_value,
    'price_hash', price_hash_value,
    'strategy_prompt_hash', receipt_row.strategy_prompt_hash,
    'spend_confirmation', spend_confirmation_value,
    'campaign_id', campaign_id_value,
    'batch_id', batch_id_value,
    'generation_job_id', job_id_value,
    'review_task_id', task_id_value
  ));
  execution_value := jsonb_build_object(
    'version', 'generation-strategy-execution-snapshot-v1',
    'claim_id', claim_id_value,
    'receipt_id', receipt_id_value,
    'receipt_hash', receipt_hash_value,
    'binding_id', binding_id_value,
    'binding_hash', binding_hash_value,
    'strategy_id', receipt_row.strategy_id,
    'recipe', receipt_row.recipe,
    'catalog_version', receipt_row.catalog_version,
    'recipe_version', receipt_row.recipe_version,
    'pricing_version', receipt_row.pricing_version,
    'selection_hash', selection_hash_value,
    'price_hash', price_hash_value,
    'strategy_prompt_hash', receipt_row.strategy_prompt_hash,
    'spend_confirmation', spend_confirmation_value,
    'campaign_id', campaign_id_value,
    'batch_id', batch_id_value,
    'generation_job_id', job_id_value,
    'review_task_id', task_id_value
  );
  batch_input_value := jsonb_build_object(
    'job_id', job_id_value,
    'review_task_id', task_id_value,
    'provider', 'runway',
    'model', receipt_row.recipe,
    'strategy_recipe', receipt_row.recipe,
    'strategy_technical', strategy_technical_value,
    'input_mode', strategy_input_mode_value,
    'duration_seconds', strategy_duration_value,
    'format', ratio_value,
    'ratio', ratio_value,
    'resolution', resolution_value,
    'audio', strategy_audio_value,
    'media_id', input_media_id_value,
    'media_ids', reference_media_ids_value,
    'reference_media_ids', reference_media_ids_value,
    'assigned_to', actor_id_value,
    'campaign_id', campaign_id_value,
    'spend_confirmation', spend_confirmation_value,
    'strategy_execution', execution_value,
    'strategy_prompt_hash', receipt_row.strategy_prompt_hash,
    'generation_spec_context', jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash
    ),
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', estimated_cost_value,
      'estimated_credits', estimated_credits_value,
      'credit_unit_usd_minor', 1
    )
  );
  job_input_value := jsonb_build_object(
    'sku', product_row.sku,
    'product_name', product_row.title,
    'product_category', spec_row.product_category,
    'prompt_text', strategy_prompt_text_value,
    'provider_prompt_authority', 'strategy_prompt_snapshot',
    'strategy_prompt_snapshot', receipt_row.strategy_prompt_snapshot,
    'strategy_product_info',
      receipt_row.strategy_prompt_snapshot ->> 'product_info',
    'strategy_user_concept',
      receipt_row.strategy_prompt_snapshot -> 'user_concept',
    'strategy_technical', strategy_technical_value,
    'format', ratio_value,
    'ratio', ratio_value,
    'resolution', resolution_value,
    'audio', strategy_audio_value,
    'input_mode', strategy_input_mode_value,
    'input_media_id', input_media_id_value,
    'input_object_name', input_object_name_value,
    'reference_media_ids', reference_media_ids_value,
    'reference_object_names', reference_object_names_value,
    'reference_asset_count', jsonb_array_length(reference_media_ids_value),
    'output_object_name', output_object_name_value,
    'review_task_id', task_id_value,
    'provider', 'runway',
    'model', receipt_row.recipe,
    'strategy_recipe', receipt_row.recipe,
    'duration_seconds', strategy_duration_value,
    'platform', spec_row.platform,
    'destination_ref', 'generation-strategy',
    'campaign_id', campaign_id_value,
    'spend_confirmation', spend_confirmation_value,
    'strategy_execution', execution_value,
    'strategy_prompt_hash', receipt_row.strategy_prompt_hash,
    'generation_spec_context', jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash
    ),
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', estimated_cost_value,
      'estimated_credits', estimated_credits_value,
      'credit_unit_usd_minor', 1
    )
  );
  perform set_config(
    'content_factory.generation_spec_id', spec_row.spec_id::text, true
  );
  perform set_config(
    'content_factory.generation_spec_version', spec_row.spec_version::text, true
  );
  perform set_config(
    'content_factory.generation_spec_hash', spec_row.spec_hash, true
  );
  perform set_config(
    'content_factory.generation_product_category',
    spec_row.product_category, true
  );
  perform set_config(
    'content_factory.generation_campaign_id', campaign_id_value::text, true
  );

  -- Insert the authority first.  Its three aggregate FKs are deferred to
  -- transaction end, so batch/job guards can require this exact claim and a
  -- partial aggregate can never commit.
  insert into content_factory.generation_strategy_start_claims (
    id, organization_id, project_id, actor_id, readiness_receipt_id,
    receipt_hash, spec_strategy_binding_id, binding_hash, selection_hash,
    price_hash, strategy_prompt_hash, spend_confirmation, campaign_id,
    batch_id, generation_job_id, review_task_id, request_hash, claim_hash,
    idempotency_key
  ) values (
    claim_id_value, organization_id_value, project_id_value, actor_id_value,
    receipt_id_value, receipt_hash_value, binding_id_value, binding_hash_value,
    selection_hash_value, price_hash_value, receipt_row.strategy_prompt_hash,
    spend_confirmation_value, campaign_id_value, batch_id_value, job_id_value,
    task_id_value, request_hash_value, claim_hash_value, idempotency_key_value
  ) returning * into claim_row;

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name, mode,
    allow_real_spend, status, total_requested, total_created, input,
    request_hash, idempotency_key, provider, model, duration_seconds,
    audio, estimated_cost_minor, estimated_credits, currency, project_id,
    campaign_id
  ) values (
    batch_id_value, organization_id_value, product_row.id, actor_id_value,
    left('Strategy ' || receipt_row.strategy_id || ' - ' ||
      product_row.title, 180),
    'real', true, 'queued', 1, 0, batch_input_value, request_hash_value,
    'strategy-batch:' || claim_hash_value, 'runway', receipt_row.recipe,
    strategy_duration_value, strategy_audio_value, estimated_cost_value,
    estimated_credits_value, 'USD', project_id_value, campaign_id_value
  );
  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal, requested_by,
    assigned_to, mode, provider, allow_real_spend, estimated_cost_minor,
    actual_cost_minor, status, input, output, request_hash, idempotency_key,
    project_id, generation_spec_id, generation_spec_version,
    generation_spec_hash, generation_video_reference_decided, campaign_id
  ) values (
    job_id_value, organization_id_value, product_row.id, batch_id_value, 1,
    actor_id_value, actor_id_value, 'real', 'runway', true,
    estimated_cost_value, 0, 'queued', job_input_value, '{}'::jsonb,
    request_hash_value, 'strategy-job:' || claim_hash_value, project_id_value,
    spec_row.spec_id, spec_row.spec_version, spec_row.spec_hash, true,
    campaign_id_value
  );
  insert into content_factory.creator_tasks (
    id, organization_id, assignee_id, created_by, product_id,
    generation_job_id, task_type, title, instructions, status, priority,
    payout_minor, result, idempotency_key, project_id
  ) values (
    task_id_value, organization_id_value, actor_id_value, actor_id_value,
    product_row.id, job_id_value, 'video_review',
    left('Review strategy video - ' || product_row.title, 240),
    'Review the exact generated MP4 and audio state after generation completes.',
    'blocked', 2, 0, jsonb_build_object(
      'generation_status', 'queued',
      'review_required', true,
      'provider', 'runway',
      'strategy_id', receipt_row.strategy_id,
      'recipe', receipt_row.recipe,
      'estimated_cost_minor', estimated_cost_value,
      'estimated_credits', estimated_credits_value,
      'currency', 'USD',
      'campaign_id', campaign_id_value,
      'model_identity', receipt_row.recipe,
      'duration_seconds', strategy_duration_value,
      'audio', strategy_audio_value,
      'ratio', ratio_value,
      'resolution', resolution_value
    ), 'strategy-review:' || claim_hash_value, project_id_value
  );
  select snapshot.* into job_strategy_row
  from content_factory.generation_job_strategy_snapshots snapshot
  where snapshot.organization_id = organization_id_value
    and snapshot.generation_job_id = job_id_value;
  if job_strategy_row.id is null then
    raise exception using errcode = '55000',
      message = 'generation_strategy_job_snapshot_missing';
  end if;
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-start-claim-response-v1',
    'claimed', true,
    'replay', false,
    'claim', jsonb_build_object(
      'id', claim_row.id,
      'claim_hash', claim_row.claim_hash,
      'batch_id', claim_row.batch_id,
      'generation_job_id', claim_row.generation_job_id,
      'review_task_id', claim_row.review_task_id,
      'claimed_at', claim_row.claimed_at
    ),
    'job', jsonb_build_object(
      'id', job_id_value,
      'batch_id', batch_id_value,
      'status', 'queued',
      'output_object_name', output_object_name_value,
      'estimated_cost_minor', estimated_cost_value,
      'estimated_credits', estimated_credits_value,
      'currency', 'USD',
      'campaign_id', campaign_id_value,
      'model_identity', receipt_row.recipe,
      'duration_seconds', strategy_duration_value,
      'audio', strategy_audio_value,
      'ratio', receipt_row.price_snapshot -> 'ratio',
      'resolution', receipt_row.price_snapshot -> 'resolution'
    ),
    'strategy', jsonb_build_object(
      'version', 'generation-strategy-immutable-execution-v1',
      'strategy_id', receipt_row.strategy_id,
      'recipe', receipt_row.recipe,
      'catalog_version', receipt_row.catalog_version,
      'recipe_version', receipt_row.recipe_version,
      'pricing_version', receipt_row.pricing_version,
      'binding_id', receipt_row.spec_strategy_binding_id,
      'binding_hash', receipt_row.binding_hash,
      'receipt_id', receipt_row.id,
      'receipt_hash', receipt_row.receipt_hash,
      'selection_hash', receipt_row.selection_hash,
      'price_hash', receipt_row.price_hash,
      'strategy_prompt_hash', receipt_row.strategy_prompt_hash,
      'spend_confirmation', receipt_row.spend_confirmation,
      'campaign_id', campaign_id_value,
      'job_strategy_snapshot_id', job_strategy_row.id,
      'job_strategy_snapshot_hash', job_strategy_row.strategy_snapshot_hash
    ),
    'selection', receipt_row.selection_snapshot,
    'price', receipt_row.price_snapshot - 'spend_confirmation',
    'recipe_context', jsonb_build_object(
      'strategyVersion', receipt_row.catalog_version,
      'strategyId', receipt_row.strategy_id,
      'recipe', receipt_row.recipe,
      'recipeVersion', receipt_row.recipe_version,
      'durationSeconds',
        (receipt_row.selection_snapshot ->> 'duration_seconds')::integer,
      'audio', (receipt_row.selection_snapshot ->> 'audio')::boolean,
      'ratio', to_jsonb(receipt_row.price_snapshot ->> 'ratio'),
      'resolution', to_jsonb(receipt_row.price_snapshot ->> 'resolution'),
      'productInfo', receipt_row.strategy_prompt_snapshot ->> 'product_info',
      'productInfoHash',
        receipt_row.strategy_prompt_snapshot ->> 'product_info_hash',
      'userConcept', receipt_row.strategy_prompt_snapshot -> 'user_concept',
      'userConceptHash',
        receipt_row.strategy_prompt_snapshot -> 'user_concept_hash'
    ),
    'asset_context', asset_context_value,
    'contract', jsonb_build_object(
      'provider_call_started', false,
      'dispatch_attempt_required', true,
      'dispatch_post_allowed', false,
      'review_mode', 'manual_human_review',
      'review_autostart_confirmed', false,
      'signed_urls_persisted', false,
      'browser_prompt_authority', false
    )
  );
end;
$$;

commit;

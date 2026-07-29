begin;

-- A product can be reclassified as the catalogue evolves.  Learning evidence
-- must therefore retain the category that was active when the generation was
-- created instead of reading mutable product metadata at policy time.
alter table content_factory.generation_creative_signals
  add column if not exists product_category text;

do $$
begin
  if not exists (
    select 1
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid =
          'content_factory.generation_creative_signals'::regclass
      and constraint_row.conname =
          'generation_creative_signals_product_category_check'
  ) then
    alter table content_factory.generation_creative_signals
      add constraint generation_creative_signals_product_category_check
      check (
        product_category is null
        or product_category in (
          'cosmetics', 'baa', 'sports_food', 'food', 'household',
          'apparel', 'electronics', 'other'
        )
      );
  end if;
end;
$$;

create index if not exists generation_creative_signals_category_learning_idx
  on content_factory.generation_creative_signals (
    organization_id,
    product_id,
    product_category,
    platform,
    model,
    created_at desc
  );

-- Only an immutable review input can safely recover a category for an older
-- job.  Current product metadata is deliberately not used: it may already
-- describe a newer category, which is exactly the leakage this migration
-- prevents.
with recovered_categories as (
  select distinct on (job.organization_id, job.id)
    job.organization_id,
    job.id as generation_job_id,
    lower(btrim(review.input ->> 'product_category')) as product_category
  from content_factory.generation_jobs job
  join content_factory.media_objects media
    on media.organization_id = job.organization_id
   and media.id::text = job.output ->> 'output_media_id'
   and media.product_id = job.product_id
  join content_factory.content_review_runs review
    on review.organization_id = media.organization_id
   and review.media_object_id = media.id
   and review.status = 'completed'
   and review.media_sha256_snapshot = media.sha256
  where lower(btrim(coalesce(
          review.input ->> 'product_category',
          ''
        ))) in (
          'cosmetics', 'baa', 'sports_food', 'food', 'household',
          'apparel', 'electronics', 'other'
        )
    and review.input -> 'product_category_verified'
          is not distinct from 'true'::jsonb
  order by
    job.organization_id,
    job.id,
    review.created_at desc,
    review.id desc
)
update content_factory.generation_jobs job
set input = jsonb_set(
  job.input,
  '{product_category}',
  to_jsonb(recovered.product_category),
  true
)
from recovered_categories recovered
where job.organization_id = recovered.organization_id
  and job.id = recovered.generation_job_id
  and lower(btrim(coalesce(job.input ->> 'product_category', '')))
      not in (
        'cosmetics', 'baa', 'sports_food', 'food', 'household',
        'apparel', 'electronics', 'other'
      );

-- The signal table is append-only in normal operation.  Temporarily suspend
-- that guard only for this one deterministic historical backfill.
alter table content_factory.generation_creative_signals
  disable trigger generation_creative_signal_append_only;

update content_factory.generation_creative_signals signal
set product_category = lower(btrim(job.input ->> 'product_category'))
from content_factory.generation_jobs job
where job.organization_id = signal.organization_id
  and job.id = signal.generation_job_id
  and signal.product_category is null
  and lower(btrim(coalesce(job.input ->> 'product_category', '')))
      in (
        'cosmetics', 'baa', 'sports_food', 'food', 'household',
        'apparel', 'electronics', 'other'
      );

alter table content_factory.generation_creative_signals
  enable trigger generation_creative_signal_append_only;

create or replace function
  content_factory_private.capture_generation_signal_product_category()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  category_value text := lower(btrim(coalesce(
    current_setting(
      'content_factory.generation_product_category',
      true
    ),
    ''
  )));
begin
  if category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     ) then
    category_value := lower(btrim(coalesce(
      new.product_category,
      ''
    )));
  end if;
  if category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     ) then
    select lower(btrim(coalesce(
      job.input ->> 'product_category',
      ''
    )))
    into category_value
    from content_factory.generation_jobs job
    where job.organization_id = new.organization_id
      and job.id = new.generation_job_id
      and job.product_id = new.product_id;
  end if;
  if category_value in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     ) then
    new.product_category := category_value;
  else
    new.product_category := null;
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.capture_generation_signal_product_category()
  from public, anon, authenticated, service_role;

drop trigger if exists generation_creative_signal_category_snapshot
  on content_factory.generation_creative_signals;
create trigger generation_creative_signal_category_snapshot
before insert on content_factory.generation_creative_signals
for each row execute function
  content_factory_private.capture_generation_signal_product_category();

-- The learning resolver is intentionally layered (performance, exploration,
-- independent QA, guards, audio/speech, rejection and effectiveness).  Scope
-- every existing signal read in those audited private layers by the category
-- set by the public v8 wrapper.  With no category setting the functions retain
-- their legacy behavior for old database fixtures; production calls always
-- set the category.
do $category_scope_learning_functions$
declare
  function_signature regprocedure;
  function_definition text;
  scoped_definition text;
begin
  foreach function_signature in array array[
    'content_factory_private.creator_generation_learning_performance_policy_v1(jsonb)'::regprocedure,
    'content_factory_private.creator_generation_learning_policy_exploration_v2(jsonb)'::regprocedure,
    'content_factory_private.creator_generation_learning_policy_independent_quality_v3(jsonb)'::regprocedure,
    'content_factory_private.creator_generation_learning_policy_quality_guards_v4(jsonb)'::regprocedure,
    'content_factory_private.creator_generation_learning_policy_audio_speech_v5(jsonb)'::regprocedure,
    'content_factory_private.creator_generation_learning_policy_rejection_v6(jsonb)'::regprocedure
  ]
  loop
    function_definition :=
      pg_catalog.pg_get_functiondef(function_signature);
    scoped_definition := replace(
      function_definition,
      'and signal.product_id = media_row.product_id',
      'and signal.product_id = media_row.product_id
      and (
        nullif(current_setting(
          ''content_factory.learning_product_category'',
          true
        ), '''') is null
        or signal.product_category = current_setting(
          ''content_factory.learning_product_category'',
          true
        )
      )'
    );
    scoped_definition := replace(
      scoped_definition,
      'and signal.product_id = product_id_value',
      'and signal.product_id = product_id_value
      and (
        nullif(current_setting(
          ''content_factory.learning_product_category'',
          true
        ), '''') is null
        or signal.product_category = current_setting(
          ''content_factory.learning_product_category'',
          true
        )
      )'
    );
    if scoped_definition = function_definition then
      raise exception using
        errcode = '55000',
        message = 'generation_learning_category_scope_patch_failed';
    end if;
    execute scoped_definition;
  end loop;
end;
$category_scope_learning_functions$;

-- Guard effectiveness uses immutable job lineage rather than the creative
-- signal table.  Apply the same category setting to every lineage/job join.
do $category_scope_guard_effectiveness$
declare
  function_signature regprocedure :=
    'content_factory_private.generation_quality_guard_effectiveness(uuid,uuid,text,text,text,timestamptz)'::regprocedure;
  function_definition text;
  scoped_definition text;
begin
  function_definition :=
    pg_catalog.pg_get_functiondef(function_signature);
  scoped_definition := replace(
    function_definition,
    'and job.id = lineage.generation_job_id',
    'and job.id = lineage.generation_job_id
     and (
       nullif(current_setting(
         ''content_factory.learning_product_category'',
         true
       ), '''') is null
       or job.input ->> ''product_category'' = current_setting(
         ''content_factory.learning_product_category'',
         true
       )
     )'
  );
  if scoped_definition = function_definition then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_category_guard_patch_failed';
  end if;
  execute scoped_definition;
end;
$category_scope_guard_effectiveness$;

alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_unscoped_v7;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_unscoped_v7(jsonb)
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
  category_value text := lower(btrim(coalesce(
    p_payload ->> 'product_category',
    current_setting(
      'content_factory.generation_product_category',
      true
    ),
    ''
  )));
  previous_category_setting text := coalesce(
    current_setting(
      'content_factory.learning_product_category',
      true
    ),
    ''
  );
  base_policy jsonb;
  organization_id uuid;
  media_id_value uuid;
  product_id_value uuid;
  category_evidence_count integer := 0;
  requested_model_value text;
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if category_value = '' then
    -- Compatibility for old read-only callers and pgTAP fixtures.  Paid
    -- starts always set generation_product_category, and the web client
    -- always supplies product_category explicitly.
    return content_factory_private
      .creator_generation_learning_policy_unscoped_v7(p_payload);
  end if;
  if category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_learning_policy_category_invalid';
  end if;

  perform set_config(
    'content_factory.learning_product_category',
    category_value,
    true
  );
  base_policy := content_factory_private
    .creator_generation_learning_policy_unscoped_v7(
      p_payload - 'product_category'
    );
  organization_id :=
    content_factory_private.resolve_organization(
      p_payload - 'product_category'
    );
  media_id_value :=
    content_factory_private.require_uuid(p_payload, 'media_id');
  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;

  select count(*)::integer into category_evidence_count
  from content_factory.generation_creative_signals signal
  join content_factory.generation_jobs job
    on job.organization_id = signal.organization_id
   and job.id = signal.generation_job_id
   and job.product_id = signal.product_id
   and job.status not in ('failed', 'cancelled')
  where signal.organization_id = organization_id
    and signal.product_id = product_id_value
    and signal.product_category = category_value
    and signal.platform =
        lower(btrim(coalesce(p_payload ->> 'platform', '')))
    and signal.model =
        lower(btrim(coalesce(p_payload ->> 'model', '')));

  perform set_config(
    'content_factory.learning_product_category',
    previous_category_setting,
    true
  );
  requested_model_value := base_policy ->> 'requested_model';
  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model')
    || jsonb_build_object(
      'version', 'generation-learning-v8',
      'product_category', category_value,
      'category_evidence_count', category_evidence_count,
      'category_cold_start', category_evidence_count = 0,
      'scope', 'product_category_platform_model',
      'reason_codes',
        coalesce(base_policy -> 'reason_codes', '[]'::jsonb)
        || case
          when category_evidence_count = 0
            then '["category_cold_start"]'::jsonb
          else '[]'::jsonb
        end,
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'category_snapshot_required', true,
          'cross_category_learning_forbidden', true,
          'unknown_historical_category_excluded', true
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

-- Set the category before any nested paid-start policy check or signal insert.
-- The legacy learning-context validator does not know the new field, so the
-- wrapper verifies it and removes only that redundant copy before delegation.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_category_learning_v14;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_category_learning_v14(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  category_value text := lower(btrim(coalesce(
    p_payload ->> 'product_category',
    ''
  )));
  learning_context jsonb := p_payload -> 'learning_context';
  delegated_payload jsonb := p_payload;
  result_value jsonb;
  organization_id uuid;
  job_id_value uuid;
  batch_id_value uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if category_value <> '' then
    if category_value not in (
         'cosmetics', 'baa', 'sports_food', 'food', 'household',
         'apparel', 'electronics', 'other'
       ) then
      raise exception using
        errcode = '22023',
        message = 'paid_generation_product_category_invalid';
    end if;
    if jsonb_typeof(learning_context) <> 'object'
       or lower(btrim(coalesce(
         learning_context ->> 'product_category',
         ''
       ))) is distinct from category_value then
      raise exception using
        errcode = '22023',
        message = 'generation_learning_category_mismatch';
    end if;
    perform set_config(
      'content_factory.generation_product_category',
      category_value,
      true
    );
    delegated_payload := jsonb_set(
      p_payload,
      '{learning_context}',
      learning_context - 'product_category',
      false
    );
  end if;

  result_value := content_factory_private
    .creator_start_real_generation_pre_category_learning_v14(
      delegated_payload
    );
  if category_value = '' then
    return result_value;
  end if;

  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  begin
    job_id_value := (result_value #>> '{job,id}')::uuid;
    batch_id_value := (result_value #>> '{batch,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_category_binding_invalid';
  end;

  update content_factory.generation_jobs job
  set input = jsonb_set(
    job.input,
    '{product_category}',
    to_jsonb(category_value),
    true
  )
  where job.organization_id = organization_id
    and job.id = job_id_value
    and job.batch_id = batch_id_value;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_category_binding_invalid';
  end if;

  update content_factory.generation_batches batch
  set input = jsonb_set(
    batch.input,
    '{product_category}',
    to_jsonb(category_value),
    true
  )
  where batch.organization_id = organization_id
    and batch.id = batch_id_value;

  result_value := jsonb_set(
    result_value,
    '{job,product_category}',
    to_jsonb(category_value),
    true
  );
  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

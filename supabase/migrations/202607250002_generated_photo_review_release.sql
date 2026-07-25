begin;

-- Seedream outputs already enter the immutable content-review queue, but the
-- original release gate only recognizes generated_video. Bind generated_image
-- reviews to their paid job, preserve trusted advertising provenance, and
-- release an approved photo into the same placement workflow as video.

create or replace function
  content_factory_private.enforce_generated_image_review_input()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  media_row content_factory.media_objects%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  product_row content_factory.products%rowtype;
  requester_id uuid;
  actor_role text;
  platform_value text;
  product_category_value text;
  requested_category_value text;
  service_dispatch boolean;
begin
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = new.organization_id
    and media.id = new.media_object_id;

  if media_row.id is null
     or media_row.metadata ->> 'kind' is distinct from 'generated_image' then
    return new;
  end if;

  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = new.organization_id
    and task.id = media_row.task_id
  for share;
  if task_row.id is null
     or task_row.task_type <> 'video_review'
     or task_row.status <> 'review'
     or task_row.generation_job_id is null
     or task_row.product_id is distinct from media_row.product_id then
    raise exception using
      errcode = '55000',
      message = 'generated_image_review_task_invalid';
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = task_row.generation_job_id
  for share;
  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or job_row.status <> 'succeeded'
     or job_row.input ->> 'model' <> 'seedream5_lite'
     or job_row.product_id is distinct from media_row.product_id
     or job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or media_row.status <> 'ready'
     or media_row.mime_type <> 'image/png'
     or media_row.metadata ->> 'provider' <> 'runway'
     or media_row.metadata ->> 'model' <> 'seedream5_lite'
     or media_row.metadata ->> 'generation_job_id'
          is distinct from job_row.id::text then
    raise exception using
      errcode = '55000',
      message = 'generated_image_job_invalid';
  end if;

  platform_value := lower(btrim(coalesce(
    job_row.input ->> 'platform',
    ''
  )));
  if platform_value not in (
     'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
  ) then
    raise exception using
      errcode = '55000',
      message = 'generated_image_platform_invalid';
  end if;

  service_dispatch :=
    new.idempotency_key =
      'generated-photo-review:' || job_row.id::text
    and new.requested_by = job_row.requested_by;

  select product.* into product_row
  from content_factory.products product
  where product.organization_id = new.organization_id
    and product.id = media_row.product_id
  for update;
  if product_row.id is null
     or (not service_dispatch and product_row.status <> 'active') then
    raise exception using
      errcode = '55000',
      message = 'generated_image_product_invalid';
  end if;

  product_category_value := lower(btrim(coalesce(
    product_row.metadata ->> 'content_review_category',
    product_row.metadata ->> 'product_category',
    ''
  )));
  requested_category_value := lower(btrim(coalesce(
    new.input ->> 'product_category',
    ''
  )));

  if product_category_value = '' and not service_dispatch then
    requester_id := content_factory_private.current_profile_id();
    if requester_id is distinct from new.requested_by then
      raise exception using
        errcode = '42501',
        message = 'generated_image_review_requester_invalid';
    end if;
    actor_role := content_factory_private.membership_role(
      new.organization_id,
      true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
    if actor_role not in ('owner', 'admin', 'producer', 'reviewer') then
      raise exception using
        errcode = '42501',
        message = 'content_review_product_category_unverified';
    end if;
    if requested_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
    ) then
      raise exception using
        errcode = '22023',
        message = 'content_review_product_category_invalid';
    end if;
    product_category_value := requested_category_value;
    update content_factory.products product
    set metadata = product.metadata || jsonb_build_object(
          'content_review_category', product_category_value,
          'content_review_category_confirmed_by', requester_id,
          'content_review_category_confirmed_at', now(),
          'content_review_category_ruleset', new.ruleset_version
        ),
        updated_at = now()
    where product.organization_id = new.organization_id
      and product.id = product_row.id
    returning * into product_row;
  elsif product_category_value <> ''
        and not service_dispatch
        and requested_category_value is distinct from product_category_value then
    raise exception using
      errcode = '22023',
      message = 'content_review_product_category_mismatch';
  end if;

  if not service_dispatch then
    if lower(btrim(coalesce(new.input ->> 'platform', '')))
         is distinct from platform_value
       or lower(btrim(coalesce(new.input ->> 'content_kind', '')))
         is distinct from 'advertising'
       or new.input -> 'ai_generated' is distinct from 'true'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'generated_image_review_context_invalid';
    end if;
    if new.input -> 'external_ai_processing_confirmed'
         is distinct from 'true'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'content_review_external_ai_processing_required';
    end if;
  end if;

  new.input := new.input || jsonb_build_object(
    'media_id', media_row.id,
    'platform', platform_value,
    'generation_job_id', job_row.id,
    'content_kind', 'advertising',
    'ai_generated', true,
    'script_text', job_row.input ->> 'prompt_text',
    'technical_metrics', jsonb_build_object(
      'source_type', 'image',
      'width', 2048,
      'height', 2048,
      'format', 'png'
    ),
    'product_category',
      coalesce(nullif(product_category_value, ''), 'other'),
    'product_category_verified', product_category_value <> '',
    'product_category_source',
      case
        when product_category_value <> '' then 'product_metadata'
        else 'autonomous_generation'
      end,
    'external_ai_processing_confirmed',
      case
        when service_dispatch then true
        else (new.input ->> 'external_ai_processing_confirmed')::boolean
      end
  );
  new.request_hash := content_factory_private.json_hash(new.input);
  return new;
end;
$$;

revoke all on function
  content_factory_private.enforce_generated_image_review_input()
  from public, anon, authenticated;

drop trigger if exists generated_image_review_input_guard
  on content_factory.content_review_runs;
create trigger generated_image_review_input_guard
before insert on content_factory.content_review_runs
for each row execute function
  content_factory_private.enforce_generated_image_review_input();

-- Keep the existing trigger name and function signature because older
-- migrations and operational checks refer to them. The strengthened body now
-- accepts both audited generated output kinds.
create or replace function
  content_factory_private.guard_video_review_content_approval()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  job_row content_factory.generation_jobs%rowtype;
  media_row content_factory.media_objects%rowtype;
  output_media_id_value uuid;
  review_id_value uuid;
begin
  if old.status = 'done'
     or new.status <> 'done'
     or new.task_type <> 'video_review'
     or new.generation_job_id is null then
    return new;
  end if;

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = new.generation_job_id;

  if job_row.id is null or job_row.mode <> 'real' then
    return new;
  end if;
  if job_row.status <> 'succeeded' then
    raise exception using
      errcode = '55000',
      message = 'content_review_generation_not_succeeded';
  end if;

  begin
    output_media_id_value := (job_row.output ->> 'output_media_id')::uuid;
    review_id_value := (new.result ->> 'content_review_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000',
      message = 'content_review_approval_evidence_required';
  end;
  if output_media_id_value is null or review_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'content_review_approval_evidence_required';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = new.organization_id
    and media.id = output_media_id_value;
  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.task_id is distinct from new.id
     or media_row.metadata ->> 'kind' not in (
       'generated_video', 'generated_image'
     )
     or new.result ->> 'content_review_media_sha256'
          is distinct from media_row.sha256
     or new.result ->> 'content_review_ruleset'
          is distinct from 'ru-content-compliance-2026-07-16.1'
     or not exists (
       select 1
       from content_factory.content_review_runs review
       join content_factory.content_review_decisions decision
         on decision.organization_id = review.organization_id
        and decision.review_id = review.id
       where review.organization_id = new.organization_id
         and review.id = review_id_value
         and review.media_object_id = media_row.id
         and review.media_sha256_snapshot = media_row.sha256
         and review.ruleset_version =
           'ru-content-compliance-2026-07-16.1'
         and review.status = 'completed'
         and review.completion_hash is not null
         and coalesce(
           (review.result ->> 'blockers_count')::integer,
           0
         ) = 0
         and review.result ->> 'compliance_status' <> 'block'
         and decision.decision = 'approved'
         and decision.media_watched_confirmed
         and decision.review_completion_hash = review.completion_hash
         and decision.media_sha256_snapshot = media_row.sha256
     ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_approval_evidence_required';
  end if;
  return new;
end;
$$;

-- The immutable decision is the only event allowed to finish a generated
-- photo review task and materialize a placement.
create or replace function
  content_factory_private.release_generated_image_review()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  product_row content_factory.products%rowtype;
  platform_value text;
  destination_value text;
  product_category_value text;
  placement_task_id_value uuid;
  placement_id_value uuid;
  placement_request_value jsonb;
begin
  if new.decision <> 'approved' then
    return new;
  end if;

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = new.organization_id
    and review.id = new.review_id;
  if review_row.id is null then
    return new;
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = new.organization_id
    and media.id = review_row.media_object_id;
  if media_row.id is null
     or media_row.metadata ->> 'kind' is distinct from 'generated_image' then
    return new;
  end if;

  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = new.organization_id
    and task.id = media_row.task_id
  for update;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = task_row.generation_job_id
  for update;
  select product.* into product_row
  from content_factory.products product
  where product.organization_id = new.organization_id
    and product.id = media_row.product_id
    and product.status = 'active'
  for share;

  if review_row.status <> 'completed'
     or review_row.completion_hash is null
     or new.review_completion_hash is distinct from
          review_row.completion_hash
     or new.media_sha256_snapshot is distinct from media_row.sha256
     or review_row.media_sha256_snapshot is distinct from media_row.sha256
     or not new.media_watched_confirmed
     or task_row.id is null
     or task_row.task_type <> 'video_review'
     or task_row.status <> 'review'
     or task_row.product_id is distinct from media_row.product_id
     or job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or job_row.status <> 'succeeded'
     or job_row.input ->> 'model' <> 'seedream5_lite'
     or job_row.product_id is distinct from media_row.product_id
     or job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or review_row.input ->> 'generation_job_id'
          is distinct from job_row.id::text
     or product_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generated_image_review_context_invalid';
  end if;

  if new.decided_by in (
    media_row.owner_id,
    task_row.assignee_id,
    job_row.requested_by,
    job_row.assigned_to
  ) then
    raise exception using
      errcode = '42501',
      message = 'generated_image_independent_review_required';
  end if;

  if exists (
       select 1
       from jsonb_array_elements(
         coalesce(review_row.result -> 'findings', '[]'::jsonb)
       ) finding(value)
       where finding.value ->> 'severity' = 'blocker'
     )
     or coalesce(
       (review_row.result ->> 'blockers_count')::integer,
       0
     ) > 0
     or review_row.result ->> 'compliance_status' = 'block' then
    raise exception using
      errcode = '55000',
      message = 'content_review_blockers_unresolved';
  end if;

  platform_value := lower(btrim(coalesce(
    job_row.input ->> 'platform',
    ''
  )));
  destination_value := btrim(coalesce(
    job_row.input ->> 'destination_ref',
    ''
  ));
  product_category_value := lower(btrim(coalesce(
    product_row.metadata ->> 'content_review_category',
    product_row.metadata ->> 'product_category',
    ''
  )));
  if platform_value not in (
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or length(destination_value) not between 2 and 240
     or review_row.input ->> 'platform'
          is distinct from platform_value
     or review_row.input ->> 'content_kind'
          is distinct from 'advertising'
     or review_row.input -> 'ai_generated'
          is distinct from 'true'::jsonb
     or review_row.input -> 'external_ai_processing_confirmed'
          is distinct from 'true'::jsonb
     or review_row.input -> 'ad_label_confirmed'
          is distinct from 'true'::jsonb
     or review_row.input -> 'ord_confirmed'
          is distinct from 'true'::jsonb
     or length(btrim(coalesce(
          review_row.input ->> 'advertiser_name',
          ''
        ))) < 2
     or length(btrim(coalesce(review_row.input ->> 'erid', ''))) < 6
     or review_row.input -> 'rights_confirmed'
          is distinct from 'true'::jsonb
     or review_row.input -> 'claims_verified'
          is distinct from 'true'::jsonb
     or (
       platform_value = 'youtube'
       and review_row.input -> 'ai_disclosure_confirmed'
            is distinct from 'true'::jsonb
     )
     or (
       product_category_value = 'baa'
       and review_row.input -> 'mandatory_warning_confirmed'
            is distinct from 'true'::jsonb
     )
     or (
       review_row.input -> 'audience_over_10000'
            is not distinct from 'true'::jsonb
       and review_row.input -> 'rkn_registered'
            is distinct from 'true'::jsonb
     )
     or product_category_value = ''
     or review_row.input ->> 'product_category'
          is distinct from product_category_value
     or review_row.input -> 'product_category_verified'
          is distinct from 'true'::jsonb
     or review_row.input ->> 'product_category_source'
          is distinct from 'product_metadata' then
    raise exception using
      errcode = '55000',
      message = 'generated_image_review_context_invalid';
  end if;

  update content_factory.creator_tasks task
  set status = 'done',
      submitted_at = coalesce(task.submitted_at, now()),
      completed_at = coalesce(task.completed_at, now()),
      result = task.result || jsonb_build_object(
        'content_review_id', review_row.id,
        'content_review_decision_id', new.id,
        'content_review_media_id', media_row.id,
        'content_review_media_sha256', media_row.sha256,
        'content_review_ruleset', review_row.ruleset_version,
        'content_review_approved_by', new.decided_by,
        'content_review_approved_at', now(),
        'media_watched_confirmed', true
      ),
      updated_at = now()
  where task.organization_id = new.organization_id
    and task.id = task_row.id
  returning * into task_row;

  if task_row.payout_minor > 0 then
    insert into content_factory.creator_payouts (
      organization_id, profile_id, task_id, amount_minor,
      currency, status, reason
    ) values (
      new.organization_id,
      task_row.assignee_id,
      task_row.id,
      task_row.payout_minor,
      'RUB',
      'Approved generated photo review: ' || review_row.id::text
    )
    on conflict on constraint creator_payouts_org_task_uq do nothing;
  end if;

  select task.id into placement_task_id_value
  from content_factory.creator_tasks task
  where task.organization_id = new.organization_id
    and task.idempotency_key =
      'content-review-placement-task:' || review_row.id::text;
  if placement_task_id_value is null then
    insert into content_factory.creator_tasks (
      organization_id, assignee_id, created_by, product_id,
      generation_job_id, task_type, title, instructions,
      status, priority, payout_minor, result, idempotency_key
    ) values (
      new.organization_id,
      task_row.assignee_id,
      new.decided_by,
      job_row.product_id,
      job_row.id,
      'placement',
      left(
        'Опубликовать одобренное фото — ' ||
          coalesce(job_row.input ->> 'product_name', 'контент'),
        240
      ),
      'Опубликуйте только одобренный PNG. После публикации добавьте финальную HTTPS-ссылку.',
      'todo',
      2,
      0,
      jsonb_build_object(
        'content_review_id', review_row.id,
        'content_review_decision_id', new.id,
        'source_media_id', media_row.id,
        'media_sha256', media_row.sha256,
        'ruleset_version', review_row.ruleset_version,
        'platform', platform_value,
        'destination_ref', destination_value,
        'content_kind', 'photo'
      ),
      'content-review-placement-task:' || review_row.id::text
    )
    returning id into placement_task_id_value;
  end if;

  placement_request_value := jsonb_build_object(
    'content_review_id', review_row.id,
    'decision_id', new.id,
    'generation_job_id', job_row.id,
    'media_id', media_row.id,
    'media_sha256', media_row.sha256,
    'platform', platform_value,
    'destination_ref', destination_value,
    'content_kind', 'photo'
  );
  insert into content_factory.placements (
    organization_id, product_id, generation_job_id, task_id,
    assigned_to, created_by, platform, destination_ref,
    status, request_hash, idempotency_key, metadata
  ) values (
    new.organization_id,
    job_row.product_id,
    job_row.id,
    placement_task_id_value,
    task_row.assignee_id,
    new.decided_by,
    platform_value,
    destination_value,
    'ready',
    content_factory_private.json_hash(placement_request_value),
    'content-review-placement:' || review_row.id::text,
    jsonb_build_object(
      'content_review_id', review_row.id,
      'content_review_decision_id', new.id,
      'source_media_id', media_row.id,
      'media_sha256', media_row.sha256,
      'ruleset_version', review_row.ruleset_version,
      'media_watched_confirmed', true,
      'content_kind', 'photo'
    )
  )
  on conflict on constraint placements_organization_id_task_id_key
    do nothing
  returning id into placement_id_value;

  if placement_id_value is null
     and not exists (
       select 1
       from content_factory.placements placement
       where placement.organization_id = new.organization_id
         and placement.task_id = placement_task_id_value
         and placement.generation_job_id = job_row.id
         and placement.platform = platform_value
         and placement.destination_ref = destination_value
         and placement.metadata ->> 'content_review_id'
              = review_row.id::text
     ) then
    raise exception using
      errcode = '23505',
      message = 'content_review_placement_conflict';
  end if;

  perform content_factory_private.emit_event(
    new.organization_id,
    new.decided_by,
    'generated_photo_released',
    'content_review_run',
    review_row.id::text,
    jsonb_build_object(
      'generation_job_id', job_row.id,
      'media_id', media_row.id,
      'placement_task_id', placement_task_id_value,
      'placement_id', placement_id_value
    ),
    'generated-photo-release:' || review_row.id::text
  );
  return new;
end;
$$;

revoke all on function
  content_factory_private.release_generated_image_review()
  from public, anon, authenticated;

drop trigger if exists generated_image_review_release
  on content_factory.content_review_decisions;
create trigger generated_image_review_release
after insert on content_factory.content_review_decisions
for each row execute function
  content_factory_private.release_generated_image_review();

do $$
begin
  if not exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace schema_row
      on schema_row.oid = table_row.relnamespace
    where schema_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_runs'
      and trigger_row.tgname = 'generated_image_review_input_guard'
      and not trigger_row.tgisinternal
  ) or not exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace schema_row
      on schema_row.oid = table_row.relnamespace
    where schema_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_decisions'
      and trigger_row.tgname = 'generated_image_review_release'
      and not trigger_row.tgisinternal
  ) then
    raise exception using
      errcode = '55000',
      message = 'generated_image_review_release_install_failed';
  end if;
end;
$$;

commit;

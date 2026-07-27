begin;

-- Seedream photos enter content review automatically before a human can add
-- ERID and publication declarations.  Re-running the same PNG through the
-- external model only to add those local facts is wasteful and weakens the
-- audit trail.  Keep the visual result immutable, create one derived review
-- with an explicit context amendment, and approve it in the same transaction.
create table if not exists
  content_factory.content_review_context_amendments (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    source_review_id uuid not null,
    amended_review_id uuid not null,
    generation_job_id uuid not null,
    media_object_id uuid not null,
    product_id uuid not null,
    source_completion_hash text not null
      check (source_completion_hash ~ '^[0-9a-f]{64}$'),
    amended_completion_hash text not null
      check (amended_completion_hash ~ '^[0-9a-f]{64}$'),
    context_snapshot jsonb not null check (
      jsonb_typeof(context_snapshot) = 'object'
      and length(context_snapshot::text) <= 32768
    ),
    created_by uuid not null,
    created_at timestamptz not null default now(),
    foreign key (organization_id, source_review_id)
      references content_factory.content_review_runs(organization_id, id),
    foreign key (organization_id, amended_review_id)
      references content_factory.content_review_runs(organization_id, id),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, source_review_id),
    unique (organization_id, amended_review_id)
  );

alter table
  content_factory.content_review_context_amendments enable row level security;
revoke all on content_factory.content_review_context_amendments
  from public, anon, authenticated;
grant all on content_factory.content_review_context_amendments
  to service_role;

create or replace function
  content_factory_private.reject_content_review_context_amendment_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'content_review_context_amendment_immutable';
end;
$$;

revoke all on function
  content_factory_private
    .reject_content_review_context_amendment_mutation()
  from public, anon, authenticated, service_role;

drop trigger if exists reject_content_review_context_amendment_mutation
  on content_factory.content_review_context_amendments;
create trigger reject_content_review_context_amendment_mutation
before update or delete
on content_factory.content_review_context_amendments
for each row execute function
  content_factory_private.reject_content_review_context_amendment_mutation();

create or replace function
  content_factory_private.generated_photo_context_resolvable_codes()
returns text[]
language sql
immutable
set search_path = ''
as $$
  select array[
    'CONTEXT.GENERATED_PROVENANCE',
    'AD.MARKING.LABEL',
    'AD.MARKING.ADVERTISER',
    'AD.MARKING.ERID',
    'AD.ORD_ACK',
    'PUBLISHER.RKN_10K',
    'RIGHTS.MEDIA',
    'PERSON.IMAGE_RELEASE',
    'PERSON.PRESENCE_UNRESOLVED',
    'CLAIM.OUTPUT_NOT_CONFIRMED',
    'YOUTUBE.AI_DISCLOSURE',
    'BAA.DISCLAIMER'
  ]::text[]
$$;

revoke all on function
  content_factory_private.generated_photo_context_resolvable_codes()
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generated_photo_context_result(
    p_source_result jsonb
  )
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  resolvable_codes text[] :=
    content_factory_private.generated_photo_context_resolvable_codes();
  findings_value jsonb;
  recommendations_value jsonb;
  limitations_value jsonb;
  blockers_value integer;
  warnings_value integer;
  human_review_value boolean;
  compliance_value text;
  result_value jsonb;
  limitation_value text :=
    'Визуальная модель повторно не запускалась: изменён только подтверждённый человеком контекст публикации generated-photo-context-v1.';
begin
  perform content_factory_private.validate_content_review_result(
    p_source_result
  );

  select coalesce(jsonb_agg(finding.value order by finding.ordinality),
                  '[]'::jsonb)
  into findings_value
  from jsonb_array_elements(p_source_result -> 'findings')
    with ordinality finding(value, ordinality)
  where finding.value ->> 'code' <> all(resolvable_codes);

  select coalesce(
    jsonb_agg(recommendation.value order by recommendation.ordinality),
    '[]'::jsonb
  )
  into recommendations_value
  from jsonb_array_elements(p_source_result -> 'recommendations')
    with ordinality recommendation(value, ordinality)
  where recommendation.value ->> 'code' <> all(
    array(
      select 'FIX.' || code
      from unnest(resolvable_codes) code
    )
  );

  select count(*) filter (
           where finding.value ->> 'severity' = 'blocker'
         ),
         count(*) filter (
           where finding.value ->> 'severity' in ('high', 'medium')
         ),
         coalesce(bool_or(
           finding.value -> 'human_review_required'
             is not distinct from 'true'::jsonb
         ), false)
  into blockers_value, warnings_value, human_review_value
  from jsonb_array_elements(findings_value) finding(value);

  compliance_value := case
    when blockers_value > 0 then 'block'
    when warnings_value > 0 or human_review_value then 'human_review'
    else 'pass_with_warnings'
  end;

  limitations_value := coalesce(
    p_source_result -> 'limitations',
    '[]'::jsonb
  );
  if not limitations_value @> jsonb_build_array(limitation_value) then
    limitations_value := (
      select coalesce(jsonb_agg(item.value order by item.ordinality),
                      '[]'::jsonb)
      from (
        select existing.value, existing.ordinality
        from jsonb_array_elements(limitations_value)
          with ordinality existing(value, ordinality)
        order by existing.ordinality
        limit 19
      ) item
    ) || jsonb_build_array(limitation_value);
  end if;

  result_value := p_source_result || jsonb_build_object(
    'findings', findings_value,
    'recommendations', recommendations_value,
    'blockers_count', blockers_value,
    'warnings_count', warnings_value,
    'compliance_status', compliance_value,
    'comparison', jsonb_build_object(
      'previous_score', (p_source_result ->> 'overall_score')::integer,
      'delta', 0,
      'summary',
        'Визуальная оценка не пересчитывалась; добавлен только проверенный контекст публикации.'
    ),
    'limitations', limitations_value
  );
  perform content_factory_private.validate_content_review_result(
    result_value
  );
  return result_value;
end;
$$;

revoke all on function
  content_factory_private.generated_photo_context_result(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  public.creator_approve_generated_photo_review_with_context(
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
  actor_role text;
  source_review_id_value uuid;
  idempotency_key_value text;
  comment_value text;
  product_category_value text;
  requested_category_value text;
  advertiser_name_value text;
  erid_value text;
  people_present_value text;
  media_watched_value boolean;
  ad_label_value boolean;
  ord_value boolean;
  rights_value boolean;
  claims_value boolean;
  person_consent_value boolean;
  ai_disclosure_value boolean;
  mandatory_warning_value boolean;
  audience_over_10000_value boolean;
  rkn_registered_value boolean;
  acknowledgements_value jsonb;
  resolved_codes_value jsonb;
  source_review_row content_factory.content_review_runs%rowtype;
  amended_review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  product_row content_factory.products%rowtype;
  decision_id_value uuid;
  amended_review_id_value uuid := extensions.gen_random_uuid();
  platform_value text;
  context_snapshot_value jsonb;
  amended_input_value jsonb;
  amended_result_value jsonb;
  completion_payload_value jsonb;
  completion_hash_value text;
  required_codes_value text[];
  supplied_code text;
  replay jsonb;
  request_payload jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 65536
     or p_payload - array[
       'organization_id', 'review_id', 'idempotency_key',
       'reason', 'comment', 'product_category',
       'advertiser_name', 'erid', 'people_present',
       'media_watched_confirmed', 'ad_label_confirmed',
       'ord_confirmed', 'rights_confirmed', 'claims_verified',
       'person_consent_confirmed', 'ai_disclosure_confirmed',
       'mandatory_warning_confirmed', 'audience_over_10000',
       'rkn_registered', 'risk_acknowledgements',
       'resolved_recommendation_codes'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generated_photo_context_approval_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  source_review_id_value :=
    content_factory_private.require_uuid(p_payload, 'review_id');
  idempotency_key_value :=
    content_factory_private.require_text(
      p_payload, 'idempotency_key', 8, 180
    );
  comment_value := btrim(coalesce(
    nullif(p_payload ->> 'reason', ''),
    nullif(p_payload ->> 'comment', ''),
    ''
  ));
  requested_category_value := lower(btrim(coalesce(
    p_payload ->> 'product_category', ''
  )));
  advertiser_name_value := btrim(coalesce(
    p_payload ->> 'advertiser_name', ''
  ));
  erid_value := btrim(coalesce(p_payload ->> 'erid', ''));
  people_present_value := lower(btrim(coalesce(
    p_payload ->> 'people_present', ''
  )));
  acknowledgements_value := coalesce(
    p_payload -> 'risk_acknowledgements',
    '[]'::jsonb
  );
  resolved_codes_value := coalesce(
    p_payload -> 'resolved_recommendation_codes',
    '[]'::jsonb
  );

  if p_payload ? 'media_watched_confirmed'
     and jsonb_typeof(p_payload -> 'media_watched_confirmed') <> 'boolean'
     or p_payload ? 'ad_label_confirmed'
     and jsonb_typeof(p_payload -> 'ad_label_confirmed') <> 'boolean'
     or p_payload ? 'ord_confirmed'
     and jsonb_typeof(p_payload -> 'ord_confirmed') <> 'boolean'
     or p_payload ? 'rights_confirmed'
     and jsonb_typeof(p_payload -> 'rights_confirmed') <> 'boolean'
     or p_payload ? 'claims_verified'
     and jsonb_typeof(p_payload -> 'claims_verified') <> 'boolean'
     or p_payload ? 'person_consent_confirmed'
     and jsonb_typeof(p_payload -> 'person_consent_confirmed') <> 'boolean'
     or p_payload ? 'ai_disclosure_confirmed'
     and jsonb_typeof(p_payload -> 'ai_disclosure_confirmed') <> 'boolean'
     or p_payload ? 'mandatory_warning_confirmed'
     and jsonb_typeof(p_payload -> 'mandatory_warning_confirmed') <> 'boolean'
     or p_payload ? 'audience_over_10000'
     and jsonb_typeof(p_payload -> 'audience_over_10000') <> 'boolean'
     or p_payload ? 'rkn_registered'
     and jsonb_typeof(p_payload -> 'rkn_registered') <> 'boolean' then
    raise exception using
      errcode = '22023',
      message = 'generated_photo_context_approval_boolean_invalid';
  end if;

  media_watched_value := coalesce(
    (p_payload ->> 'media_watched_confirmed')::boolean, false
  );
  ad_label_value := coalesce(
    (p_payload ->> 'ad_label_confirmed')::boolean, false
  );
  ord_value := coalesce(
    (p_payload ->> 'ord_confirmed')::boolean, false
  );
  rights_value := coalesce(
    (p_payload ->> 'rights_confirmed')::boolean, false
  );
  claims_value := coalesce(
    (p_payload ->> 'claims_verified')::boolean, false
  );
  person_consent_value := coalesce(
    (p_payload ->> 'person_consent_confirmed')::boolean, false
  );
  ai_disclosure_value := coalesce(
    (p_payload ->> 'ai_disclosure_confirmed')::boolean, false
  );
  mandatory_warning_value := coalesce(
    (p_payload ->> 'mandatory_warning_confirmed')::boolean, false
  );
  audience_over_10000_value := coalesce(
    (p_payload ->> 'audience_over_10000')::boolean, false
  );
  rkn_registered_value := coalesce(
    (p_payload ->> 'rkn_registered')::boolean, false
  );

  if length(comment_value) not between 10 and 2000
     or requested_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     )
     or length(advertiser_name_value) not between 2 and 240
     or advertiser_name_value ~ '[[:cntrl:]]'
     or length(erid_value) not between 6 and 180
     or erid_value ~ '[[:cntrl:]]'
     or people_present_value not in ('yes', 'no')
     or not media_watched_value
     or not ad_label_value
     or not ord_value
     or not rights_value
     or not claims_value
     or (
       people_present_value = 'yes'
       and not person_consent_value
     )
     or jsonb_typeof(acknowledgements_value) <> 'array'
     or jsonb_array_length(acknowledgements_value) > 50
     or length(acknowledgements_value::text) > 16384
     or jsonb_typeof(resolved_codes_value) <> 'array'
     or jsonb_array_length(resolved_codes_value) > 100
     or length(resolved_codes_value::text) > 16384 then
    raise exception using
      errcode = '22023',
      message = 'generated_photo_context_approval_invalid';
  end if;

  for supplied_code in
    select code.value
    from jsonb_array_elements_text(acknowledgements_value) code(value)
  loop
    if length(btrim(supplied_code)) not between 2 and 100
       or supplied_code !~* '^[a-z0-9][a-z0-9_.:-]{1,99}$' then
      raise exception using
        errcode = '22023',
        message = 'risk_acknowledgement_invalid';
    end if;
  end loop;
  if (
    select count(*)
    from jsonb_array_elements_text(acknowledgements_value)
  ) <> (
    select count(distinct code.value)
    from jsonb_array_elements_text(acknowledgements_value) code(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'risk_acknowledgement_duplicate';
  end if;

  for supplied_code in
    select code.value
    from jsonb_array_elements_text(resolved_codes_value) code(value)
  loop
    if length(btrim(supplied_code)) not between 2 and 100
       or supplied_code !~* '^[a-z0-9][a-z0-9_.:-]{1,99}$' then
      raise exception using
        errcode = '22023',
        message = 'resolved_recommendation_code_invalid';
    end if;
  end loop;
  if (
    select count(*)
    from jsonb_array_elements_text(resolved_codes_value)
  ) <> (
    select count(distinct code.value)
    from jsonb_array_elements_text(resolved_codes_value) code(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'resolved_recommendation_code_duplicate';
  end if;

  request_payload := jsonb_build_object(
    'review_id', source_review_id_value,
    'reason', comment_value,
    'product_category', requested_category_value,
    'advertiser_name', advertiser_name_value,
    'erid', erid_value,
    'people_present', people_present_value,
    'media_watched_confirmed', media_watched_value,
    'ad_label_confirmed', ad_label_value,
    'ord_confirmed', ord_value,
    'rights_confirmed', rights_value,
    'claims_verified', claims_value,
    'person_consent_confirmed', person_consent_value,
    'ai_disclosure_confirmed', ai_disclosure_value,
    'mandatory_warning_confirmed', mandatory_warning_value,
    'audience_over_10000', audience_over_10000_value,
    'rkn_registered', rkn_registered_value,
    'risk_acknowledgements', acknowledgements_value,
    'resolved_recommendation_codes', resolved_codes_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_approve_generated_photo_review_with_context',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'generated_photo_context_approval:' ||
        source_review_id_value::text
    )
  );

  select review.* into source_review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = source_review_id_value
  for update;
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = source_review_row.media_object_id
  for share;
  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.id = media_row.task_id
  for update;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = task_row.generation_job_id
  for share;
  select product.* into product_row
  from content_factory.products product
  where product.organization_id = organization_id
    and product.id = media_row.product_id
  for update;

  if source_review_row.id is null
     or source_review_row.status <> 'completed'
     or source_review_row.completion_hash is null
     or source_review_row.idempotency_key
          is distinct from
            'generated-photo-review:' || job_row.id::text
     or source_review_row.requested_by is distinct from job_row.requested_by
     or source_review_row.input ->> 'generation_job_id'
          is distinct from job_row.id::text
     or source_review_row.input ->> 'content_kind'
          is distinct from 'advertising'
     or source_review_row.input -> 'ai_generated'
          is distinct from 'true'::jsonb
     or source_review_row.input -> 'external_ai_processing_confirmed'
          is distinct from 'true'::jsonb
     or media_row.id is null
     or media_row.status <> 'ready'
     or media_row.mime_type <> 'image/png'
     or media_row.sha256 is distinct from
          source_review_row.media_sha256_snapshot
     or media_row.metadata ->> 'kind' <> 'generated_image'
     or media_row.metadata ->> 'provider' <> 'runway'
     or media_row.metadata ->> 'model' <> 'seedream5_lite'
     or media_row.metadata ->> 'generation_job_id'
          is distinct from job_row.id::text
     or task_row.id is null
     or task_row.task_type <> 'video_review'
     or task_row.status <> 'review'
     or task_row.generation_job_id is distinct from job_row.id
     or task_row.product_id is distinct from media_row.product_id
     or job_row.id is null
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or job_row.status <> 'succeeded'
     or job_row.input ->> 'model' <> 'seedream5_lite'
     or job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or job_row.product_id is distinct from media_row.product_id
     or product_row.id is null
     or product_row.status <> 'active'
     or exists (
       select 1
       from content_factory.content_review_decisions decision
       where decision.organization_id = organization_id
         and decision.review_id = source_review_id_value
     )
     or exists (
       select 1
       from content_factory.content_review_context_amendments amendment
       where amendment.organization_id = organization_id
         and amendment.source_review_id = source_review_id_value
     ) then
    raise exception using
      errcode = '55000',
      message = 'generated_photo_context_source_invalid';
  end if;

  if user_id in (
    media_row.owner_id,
    task_row.assignee_id,
    job_row.requested_by,
    job_row.assigned_to
  ) then
    raise exception using
      errcode = '42501',
      message = 'generated_image_independent_review_required';
  end if;

  platform_value := lower(btrim(coalesce(
    job_row.input ->> 'platform', ''
  )));
  if platform_value not in (
       'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or source_review_row.input ->> 'platform'
          is distinct from platform_value
     or (
       platform_value = 'youtube'
       and not ai_disclosure_value
     )
     or (
       requested_category_value = 'baa'
       and not mandatory_warning_value
     )
     or (
       audience_over_10000_value
       and not rkn_registered_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'generated_photo_context_platform_invalid';
  end if;

  product_category_value := lower(btrim(coalesce(
    product_row.metadata ->> 'content_review_category',
    product_row.metadata ->> 'product_category',
    ''
  )));
  if product_category_value = '' then
    product_category_value := requested_category_value;
    update content_factory.products product
    set metadata = product.metadata || jsonb_build_object(
          'content_review_category', product_category_value,
          'content_review_category_confirmed_by', user_id,
          'content_review_category_confirmed_at', now(),
          'content_review_category_ruleset',
            source_review_row.ruleset_version
        ),
        updated_at = now()
    where product.organization_id = organization_id
      and product.id = product_row.id
    returning * into product_row;
  elsif product_category_value is distinct from
        requested_category_value then
    raise exception using
      errcode = '22023',
      message = 'content_review_product_category_mismatch';
  end if;

  context_snapshot_value := jsonb_build_object(
    'version', 'generated-photo-context-v1',
    'source_review_id', source_review_row.id,
    'source_completion_hash', source_review_row.completion_hash,
    'media_id', media_row.id,
    'media_sha256', media_row.sha256,
    'generation_job_id', job_row.id,
    'platform', platform_value,
    'product_category', product_category_value,
    'advertiser_name', advertiser_name_value,
    'erid', erid_value,
    'people_present', people_present_value,
    'media_watched_confirmed', true,
    'ad_label_confirmed', true,
    'ord_confirmed', true,
    'rights_confirmed', true,
    'claims_verified', true,
    'person_consent_confirmed', person_consent_value,
    'ai_disclosure_confirmed', ai_disclosure_value,
    'mandatory_warning_confirmed', mandatory_warning_value,
    'audience_over_10000', audience_over_10000_value,
    'rkn_registered', rkn_registered_value,
    'external_ai_invoked', false,
    'provider_analysis_reused', true
  );
  amended_input_value := source_review_row.input || jsonb_build_object(
    'product_category', product_category_value,
    'product_category_verified', true,
    'product_category_source', 'product_metadata',
    'advertiser_name', advertiser_name_value,
    'erid', erid_value,
    'people_present', people_present_value,
    'ad_label_confirmed', true,
    'ord_confirmed', true,
    'rights_confirmed', true,
    'claims_verified', true,
    'person_consent_confirmed', person_consent_value,
    'ai_disclosure_confirmed', ai_disclosure_value,
    'mandatory_warning_confirmed', mandatory_warning_value,
    'audience_over_10000', audience_over_10000_value,
    'rkn_registered', rkn_registered_value,
    'context_amendment', jsonb_build_object(
      'version', 'generated-photo-context-v1',
      'source_review_id', source_review_row.id,
      'source_completion_hash', source_review_row.completion_hash,
      'external_ai_invoked', false,
      'provider_analysis_reused', true
    )
  );
  amended_result_value :=
    content_factory_private.generated_photo_context_result(
      source_review_row.result
    );

  if coalesce(
       (amended_result_value ->> 'blockers_count')::integer, 0
     ) > 0
     or amended_result_value ->> 'compliance_status' = 'block' then
    raise exception using
      errcode = '55000',
      message = 'generated_photo_context_non_context_blockers';
  end if;

  select coalesce(array_agg(finding.value ->> 'code'), array[]::text[])
  into required_codes_value
  from jsonb_array_elements(
    amended_result_value -> 'findings'
  ) finding(value)
  where finding.value ->> 'severity' in ('blocker', 'high')
     or finding.value -> 'human_review_required'
          is not distinct from 'true'::jsonb;
  if cardinality(required_codes_value) = 0
     and amended_result_value ->> 'compliance_status' = 'human_review' then
    required_codes_value := array['general_human_review']::text[];
  end if;
  if exists (
    select 1
    from unnest(required_codes_value) required(code)
    where not acknowledgements_value @> jsonb_build_array(required.code)
  ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_risk_acknowledgement_required';
  end if;
  if exists (
    select 1
    from jsonb_array_elements_text(acknowledgements_value) supplied(code)
    where supplied.code <> 'general_human_review'
      and not exists (
        select 1
        from jsonb_array_elements(
          amended_result_value -> 'findings'
        ) finding(value)
        where finding.value ->> 'code' = supplied.code
      )
  ) then
    raise exception using
      errcode = '22023',
      message = 'risk_acknowledgement_unknown';
  end if;
  if exists (
    select 1
    from jsonb_array_elements_text(resolved_codes_value) supplied(code)
    where not exists (
      select 1
      from jsonb_array_elements(
        amended_result_value -> 'recommendations'
      ) recommendation(value)
      where recommendation.value ->> 'code' = supplied.code
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'resolved_recommendation_code_unknown';
  end if;

  completion_payload_value := jsonb_build_object(
    'status', 'completed',
    'result', amended_result_value,
    'moderation', source_review_row.moderation,
    'ruleset_version', source_review_row.ruleset_version,
    'model_provider', source_review_row.model_provider,
    'model_version', source_review_row.model_version,
    'context_amendment_version', 'generated-photo-context-v1',
    'source_review_id', source_review_row.id,
    'source_completion_hash', source_review_row.completion_hash
  );
  completion_hash_value :=
    content_factory_private.json_hash(completion_payload_value);

  insert into content_factory.content_review_runs (
    id, organization_id, media_object_id, requested_by,
    parent_review_id, status, media_sha256_snapshot,
    input, result, moderation, ruleset_version,
    model_provider, model_version, request_hash,
    completion_hash, idempotency_key,
    started_at, finished_at
  ) values (
    amended_review_id_value,
    organization_id,
    media_row.id,
    user_id,
    source_review_row.id,
    'completed',
    media_row.sha256,
    amended_input_value,
    amended_result_value,
    source_review_row.moderation,
    source_review_row.ruleset_version,
    source_review_row.model_provider,
    source_review_row.model_version,
    content_factory_private.json_hash(amended_input_value),
    completion_hash_value,
    'generated-photo-context:' || source_review_row.id::text,
    now(),
    now()
  )
  returning * into amended_review_row;

  if amended_review_row.id is null
     or amended_review_row.media_object_id is distinct from media_row.id
     or amended_review_row.input #>> '{context_amendment,source_review_id}'
          is distinct from source_review_row.id::text
     or amended_review_row.input #>> '{context_amendment,external_ai_invoked}'
          is distinct from 'false'
     or amended_review_row.completion_hash
          is distinct from completion_hash_value then
    raise exception using
      errcode = '55000',
      message = 'generated_photo_context_review_not_bound';
  end if;

  insert into content_factory.content_review_context_amendments (
    organization_id, source_review_id, amended_review_id,
    generation_job_id, media_object_id, product_id,
    source_completion_hash, amended_completion_hash,
    context_snapshot, created_by
  ) values (
    organization_id,
    source_review_row.id,
    amended_review_row.id,
    job_row.id,
    media_row.id,
    product_row.id,
    source_review_row.completion_hash,
    amended_review_row.completion_hash,
    context_snapshot_value,
    user_id
  );

  insert into content_factory.content_review_decisions (
    organization_id, review_id, decided_by, decision, comment,
    resolved_recommendation_codes, risk_acknowledgements,
    media_watched_confirmed, review_completion_hash,
    media_sha256_snapshot, idempotency_key
  ) values (
    organization_id,
    amended_review_row.id,
    user_id,
    'approved',
    comment_value,
    resolved_codes_value,
    acknowledgements_value,
    true,
    amended_review_row.completion_hash,
    media_row.sha256,
    'generated-photo-context-decision:' || source_review_row.id::text
  )
  returning id into decision_id_value;

  result_value := jsonb_build_object(
    'ok', true,
    'review_id', amended_review_row.id,
    'source_review_id', source_review_row.id,
    'decision_id', decision_id_value,
    'decision', 'approved',
    'status', 'completed',
    'media_id', media_row.id,
    'media_sha256', media_row.sha256,
    'provider_analysis_reused', true,
    'external_ai_invoked', false,
    'context_amendment_version', 'generated-photo-context-v1'
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'generated_photo_context_approved',
    'content_review_run',
    amended_review_row.id::text,
    jsonb_build_object(
      'source_review_id', source_review_row.id,
      'generation_job_id', job_row.id,
      'media_id', media_row.id,
      'provider_analysis_reused', true,
      'external_ai_invoked', false
    ),
    'generated-photo-context-approved:' ||
      source_review_row.id::text
  );
  perform content_factory_private.finish_command(
    organization_id,
    'creator_approve_generated_photo_review_with_context',
    idempotency_key_value,
    result_value
  );
  return result_value;
end;
$$;

revoke all on function
  public.creator_approve_generated_photo_review_with_context(jsonb)
  from public, anon;
grant execute on function
  public.creator_approve_generated_photo_review_with_context(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

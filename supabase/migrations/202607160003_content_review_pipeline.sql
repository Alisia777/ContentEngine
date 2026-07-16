begin;

create table if not exists content_factory.content_review_runs (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    media_object_id uuid not null,
    requested_by uuid not null,
    parent_review_id uuid,
    status text not null default 'queued'
      check (status in ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    media_sha256_snapshot text not null
      check (media_sha256_snapshot ~ '^[0-9a-f]{64}$'),
    input jsonb not null check (
      jsonb_typeof(input) = 'object'
      and length(input::text) <= 131072
    ),
    result jsonb not null default '{}'::jsonb check (
      jsonb_typeof(result) = 'object'
      and length(result::text) <= 262144
    ),
    moderation jsonb not null default '{}'::jsonb check (
      jsonb_typeof(moderation) = 'object'
      and length(moderation::text) <= 65536
    ),
    ruleset_version text not null
      check (length(btrim(ruleset_version)) between 3 and 120),
    model_provider text check (
      model_provider is null
      or length(btrim(model_provider)) between 2 and 80
    ),
    model_version text check (
      model_version is null
      or length(btrim(model_version)) between 1 and 120
    ),
    error_code text check (
      error_code is null
      or length(btrim(error_code)) between 3 and 100
    ),
    error_message text check (
      error_message is null
      or length(btrim(error_message)) between 3 and 2000
    ),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    completion_hash text check (
      completion_hash is null
      or completion_hash ~ '^[0-9a-f]{64}$'
    ),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    started_at timestamptz,
    lease_expires_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, idempotency_key),
    unique (organization_id, id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, requested_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, parent_review_id)
      references content_factory.content_review_runs(organization_id, id),
    check (parent_review_id is null or parent_review_id <> id),
    check (
      (status = 'queued'
        and started_at is null
        and lease_expires_at is null
        and finished_at is null)
      or (status = 'processing'
        and started_at is not null
        and lease_expires_at is not null
        and finished_at is null)
      or (status in ('completed', 'failed', 'cancelled')
        and finished_at is not null
        and lease_expires_at is null)
    ),
    check (
      status <> 'completed'
      or (
        completion_hash is not null
        and model_provider is not null
        and model_version is not null
        and error_code is null
        and error_message is null
        and result ? 'overall_score'
      )
    ),
    check (
      status <> 'failed'
      or (completion_hash is not null and error_code is not null)
    )
);

create index if not exists content_review_runs_queue_idx
  on content_factory.content_review_runs (status, created_at, id)
  where status in ('queued', 'processing');

create index if not exists content_review_runs_org_created_idx
  on content_factory.content_review_runs
  (organization_id, created_at desc, id desc);

create index if not exists content_review_runs_media_history_idx
  on content_factory.content_review_runs
  (organization_id, media_object_id, created_at desc, id desc);

create unique index if not exists content_review_runs_one_active_media_idx
  on content_factory.content_review_runs (organization_id, media_object_id)
  where status in ('queued', 'processing');

create table if not exists content_factory.content_review_decisions (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    review_id uuid not null,
    decided_by uuid not null,
    decision text not null
      check (decision in ('approved', 'needs_changes', 'rejected')),
    comment text not null check (length(btrim(comment)) between 10 and 4000),
    resolved_recommendation_codes jsonb not null default '[]'::jsonb check (
      jsonb_typeof(resolved_recommendation_codes) = 'array'
      and jsonb_array_length(resolved_recommendation_codes) <= 100
      and length(resolved_recommendation_codes::text) <= 16384
    ),
    risk_acknowledgements jsonb not null default '[]'::jsonb check (
      jsonb_typeof(risk_acknowledgements) = 'array'
      and jsonb_array_length(risk_acknowledgements) <= 50
      and length(risk_acknowledgements::text) <= 16384
    ),
    media_watched_confirmed boolean not null default false,
    review_completion_hash text not null
      check (review_completion_hash ~ '^[0-9a-f]{64}$'),
    media_sha256_snapshot text not null
      check (media_sha256_snapshot ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    created_at timestamptz not null default now(),
    unique (organization_id, idempotency_key),
    unique (organization_id, review_id),
    foreign key (organization_id, review_id)
      references content_factory.content_review_runs(organization_id, id),
    foreign key (organization_id, decided_by)
      references content_factory.memberships(organization_id, profile_id)
);

create index if not exists content_review_decisions_actor_idx
  on content_factory.content_review_decisions
  (organization_id, decided_by, created_at desc, id desc);

alter table content_factory.content_review_runs enable row level security;
alter table content_factory.content_review_decisions enable row level security;

-- Both tables are RPC-only. RLS is retained as a second boundary if the
-- content_factory schema is ever exposed through PostgREST.
revoke all on content_factory.content_review_runs
  from public, anon, authenticated;
revoke all on content_factory.content_review_decisions
  from public, anon, authenticated;
grant all on content_factory.content_review_runs to service_role;
grant all on content_factory.content_review_decisions to service_role;

create or replace function content_factory_private.guard_content_review_run()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_deletion_forbidden';
  end if;

  if new.organization_id <> old.organization_id
     or new.media_object_id <> old.media_object_id
     or new.requested_by <> old.requested_by
     or new.parent_review_id is distinct from old.parent_review_id
     or new.media_sha256_snapshot <> old.media_sha256_snapshot
     or new.input <> old.input
     or new.ruleset_version <> old.ruleset_version
     or new.request_hash <> old.request_hash
     or new.idempotency_key <> old.idempotency_key
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_identity_immutable';
  end if;

  if old.status in ('completed', 'failed', 'cancelled')
     and new is distinct from old then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_terminal';
  end if;

  if new.status = old.status and new is distinct from old then
    raise exception using
      errcode = '55000',
      message = 'content_review_run_update_without_transition';
  end if;

  if new.status <> old.status and not (
    (old.status = 'queued' and new.status in ('processing', 'cancelled'))
    or (old.status = 'processing'
      and new.status in ('completed', 'failed', 'cancelled'))
  ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_status_transition_invalid';
  end if;

  if old.status = 'queued' and new.status = 'processing' then
    new.started_at := coalesce(new.started_at, now());
    new.lease_expires_at := coalesce(
      new.lease_expires_at,
      now() + interval '10 minutes'
    );
  end if;

  if new.status in ('completed', 'failed', 'cancelled')
     and new.status <> old.status then
    new.finished_at := coalesce(new.finished_at, now());
    new.lease_expires_at := null;
  end if;

  new.updated_at := now();
  return new;
end;
$$;

create or replace function content_factory_private.reject_content_review_decision_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'content_review_decision_immutable';
end;
$$;

drop trigger if exists guard_content_review_run
  on content_factory.content_review_runs;
create trigger guard_content_review_run
before update or delete on content_factory.content_review_runs
for each row execute function content_factory_private.guard_content_review_run();

drop trigger if exists reject_content_review_decision_mutation
  on content_factory.content_review_decisions;
create trigger reject_content_review_decision_mutation
before update or delete on content_factory.content_review_decisions
for each row execute function
  content_factory_private.reject_content_review_decision_mutation();

create or replace function content_factory_private.validate_content_review_result(
  value jsonb
)
returns void
language plpgsql
immutable
set search_path = ''
as $$
declare
  item jsonb;
  score_entry record;
  overall_score_value integer;
  blockers_value integer;
  warnings_value integer;
  actual_blockers integer;
  confidence_value numeric;
  compliance_value text;
begin
  if value is null
     or jsonb_typeof(value) <> 'object'
     or length(value::text) > 262144
     or value - array[
       'overall_score', 'scores', 'compliance_status', 'blockers_count',
       'warnings_count', 'strengths', 'findings', 'recommendations',
       'comparison', 'ad_probability', 'ad_classification_summary',
       'limitations'
     ]::text[] <> '{}'::jsonb
     or not (
       value ?& array[
         'overall_score', 'scores', 'compliance_status', 'blockers_count',
         'warnings_count', 'strengths', 'findings', 'recommendations',
         'comparison'
       ]
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_result_invalid';
  end if;

  if jsonb_typeof(value -> 'overall_score') <> 'number'
     or coalesce(value ->> 'overall_score', '') !~ '^[0-9]{1,3}$'
     or jsonb_typeof(value -> 'blockers_count') <> 'number'
     or coalesce(value ->> 'blockers_count', '') !~ '^[0-9]{1,3}$'
     or jsonb_typeof(value -> 'warnings_count') <> 'number'
     or coalesce(value ->> 'warnings_count', '') !~ '^[0-9]{1,3}$' then
    raise exception using
      errcode = '22023',
      message = 'content_review_result_invalid';
  end if;

  if value ? 'ad_probability' and (
       jsonb_typeof(value -> 'ad_probability') <> 'number'
       or (value ->> 'ad_probability')::numeric < 0
       or (value ->> 'ad_probability')::numeric > 1
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_ad_probability_invalid';
  end if;
  if value ? 'ad_classification_summary' and (
       jsonb_typeof(value -> 'ad_classification_summary') <> 'string'
       or length(btrim(value ->> 'ad_classification_summary'))
            not between 3 and 1000
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_ad_classification_invalid';
  end if;
  if value ? 'limitations' and (
       jsonb_typeof(value -> 'limitations') <> 'array'
       or jsonb_array_length(value -> 'limitations') > 20
       or length((value -> 'limitations')::text) > 32768
     ) then
    raise exception using
      errcode = '22023',
      message = 'content_review_limitations_invalid';
  end if;

  overall_score_value := (value ->> 'overall_score')::integer;
  blockers_value := (value ->> 'blockers_count')::integer;
  warnings_value := (value ->> 'warnings_count')::integer;
  compliance_value := btrim(coalesce(value ->> 'compliance_status', ''));

  if overall_score_value not between 0 and 100
     or blockers_value not between 0 and 100
     or warnings_value not between 0 and 100
     or compliance_value not in ('block', 'human_review', 'pass_with_warnings')
     or jsonb_typeof(value -> 'scores') <> 'object'
     or length((value -> 'scores')::text) > 32768
     or (select count(*) from jsonb_object_keys(value -> 'scores')) > 30
     or jsonb_typeof(value -> 'strengths') <> 'array'
     or jsonb_array_length(value -> 'strengths') > 30
     or jsonb_typeof(value -> 'findings') <> 'array'
     or jsonb_array_length(value -> 'findings') > 100
     or jsonb_typeof(value -> 'recommendations') <> 'array'
     or jsonb_array_length(value -> 'recommendations') > 100
     or jsonb_typeof(value -> 'comparison') <> 'object'
     or length((value -> 'comparison')::text) > 32768 then
    raise exception using
      errcode = '22023',
      message = 'content_review_result_invalid';
  end if;

  for score_entry in
    select entry.key, entry.value
    from jsonb_each(value -> 'scores') entry
  loop
    if length(score_entry.key) not between 1 and 80
       or jsonb_typeof(score_entry.value) <> 'number'
       or (score_entry.value #>> '{}')::numeric < 0
       or (score_entry.value #>> '{}')::numeric > 100 then
      raise exception using
        errcode = '22023',
        message = 'content_review_scores_invalid';
    end if;
  end loop;

  for item in
    select element.value
    from jsonb_array_elements(value -> 'strengths') element(value)
  loop
    if jsonb_typeof(item) <> 'string'
       or length(btrim(item #>> '{}')) not between 1 and 500 then
      raise exception using
        errcode = '22023',
        message = 'content_review_strength_invalid';
    end if;
  end loop;

  if value ? 'limitations' then
    for item in
      select element.value
      from jsonb_array_elements(value -> 'limitations') element(value)
    loop
      if jsonb_typeof(item) <> 'string'
         or length(btrim(item #>> '{}')) not between 1 and 1000 then
        raise exception using
          errcode = '22023',
          message = 'content_review_limitation_invalid';
      end if;
    end loop;
  end if;

  actual_blockers := 0;
  for item in
    select element.value
    from jsonb_array_elements(value -> 'findings') element(value)
  loop
    if jsonb_typeof(item) <> 'object'
       or length(item::text) > 16384
       or not (item ?& array[
         'code', 'category', 'severity', 'title', 'detail', 'action'
       ])
       or length(btrim(coalesce(item ->> 'code', ''))) not between 2 and 100
       or (item ->> 'code') !~* '^[a-z0-9][a-z0-9_.:-]{1,99}$'
       or length(btrim(coalesce(item ->> 'category', ''))) not between 2 and 80
       or btrim(coalesce(item ->> 'severity', '')) not in (
         'blocker', 'high', 'medium', 'low', 'info'
       )
       or length(btrim(coalesce(item ->> 'title', ''))) not between 3 and 300
       or length(btrim(coalesce(item ->> 'detail', ''))) not between 3 and 4000
       or length(btrim(coalesce(item ->> 'action', ''))) not between 3 and 4000
       or (
         item ? 'evidence'
         and jsonb_typeof(item -> 'evidence') <> 'object'
       )
       or (
         item ? 'human_review_required'
         and jsonb_typeof(item -> 'human_review_required') <> 'boolean'
       ) then
      raise exception using
        errcode = '22023',
        message = 'content_review_finding_invalid';
    end if;

    if item ? 'confidence' then
      if jsonb_typeof(item -> 'confidence') <> 'number' then
        raise exception using
          errcode = '22023',
          message = 'content_review_finding_invalid';
      end if;
      confidence_value := (item ->> 'confidence')::numeric;
      if confidence_value < 0 or confidence_value > 1 then
        raise exception using
          errcode = '22023',
          message = 'content_review_finding_invalid';
      end if;
    end if;

    if item ->> 'severity' = 'blocker' then
      actual_blockers := actual_blockers + 1;
    end if;
  end loop;

  if actual_blockers <> blockers_value
     or (blockers_value > 0 and compliance_value <> 'block')
     or (blockers_value = 0 and compliance_value = 'block') then
    raise exception using
      errcode = '22023',
      message = 'content_review_blocker_count_invalid';
  end if;

  for item in
    select element.value
    from jsonb_array_elements(value -> 'recommendations') element(value)
  loop
    if jsonb_typeof(item) <> 'object'
       or length(item::text) > 16384
       or not (item ?& array[
         'code', 'category', 'priority', 'title', 'detail', 'action'
       ])
       or length(btrim(coalesce(item ->> 'code', ''))) not between 2 and 100
       or (item ->> 'code') !~* '^[a-z0-9][a-z0-9_.:-]{1,99}$'
       or length(btrim(coalesce(item ->> 'category', ''))) not between 2 and 80
       or length(btrim(coalesce(item ->> 'priority', ''))) not between 1 and 40
       or length(btrim(coalesce(item ->> 'title', ''))) not between 3 and 300
       or length(btrim(coalesce(item ->> 'detail', ''))) not between 3 and 4000
       or length(btrim(coalesce(item ->> 'action', ''))) not between 3 and 4000 then
      raise exception using
        errcode = '22023',
        message = 'content_review_recommendation_invalid';
    end if;

    if item ? 'confidence' then
      if jsonb_typeof(item -> 'confidence') <> 'number' then
        raise exception using
          errcode = '22023',
          message = 'content_review_recommendation_invalid';
      end if;
      confidence_value := (item ->> 'confidence')::numeric;
      if confidence_value < 0 or confidence_value > 1 then
        raise exception using
          errcode = '22023',
          message = 'content_review_recommendation_invalid';
      end if;
    end if;
  end loop;
end;
$$;

create or replace function content_factory_private.content_review_is_high_risk(
  value jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    coalesce((value ->> 'blockers_count')::integer, 0) > 0
    or coalesce(value ->> 'compliance_status', 'block') in ('block', 'human_review')
    or exists (
      select 1
      from jsonb_array_elements(coalesce(value -> 'findings', '[]'::jsonb))
        finding(value)
      where finding.value ->> 'severity' in ('blocker', 'high')
         or finding.value -> 'human_review_required'
              is not distinct from 'true'::jsonb
    )
$$;

-- A paid generated-video review task is a release gate, not an ordinary task.
-- The exact output bytes, current ruleset, independent approval, and explicit
-- full-media viewing confirmation must all be present in immutable evidence
-- before any code path can mark that task done.
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

  -- Legacy mock tasks are outside the paid generated-video release gate.
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
     or media_row.metadata ->> 'kind' is distinct from 'generated_video'
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
         and review.ruleset_version = 'ru-content-compliance-2026-07-16.1'
         and review.status = 'completed'
         and review.completion_hash is not null
         and coalesce((review.result ->> 'blockers_count')::integer, 0) = 0
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

drop trigger if exists content_review_video_task_completion_gate
  on content_factory.creator_tasks;
create trigger content_review_video_task_completion_gate
before update of status, result on content_factory.creator_tasks
for each row execute function
  content_factory_private.guard_video_review_content_approval();

create or replace function public.creator_start_content_review(
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
  manager_scope boolean;
  idempotency_key_value text;
  media_id_value uuid;
  media_row content_factory.media_objects%rowtype;
  product_row content_factory.products%rowtype;
  review_task_row content_factory.creator_tasks%rowtype;
  generation_job_row content_factory.generation_jobs%rowtype;
  platform_value text;
  product_category_value text;
  content_kind_value text;
  ai_generated_value boolean := false;
  generated_media_value boolean := false;
  product_category_verified_value boolean := false;
  product_category_source_value text := 'user_declared';
  people_present_value text;
  caption_value text;
  script_value text;
  advertiser_name_value text;
  erid_value text;
  technical_metrics_value jsonb;
  parent_review_id_value uuid;
  parent_row content_factory.content_review_runs%rowtype;
  parent_product_id uuid;
  ruleset_value text := 'ru-content-compliance-2026-07-16.1';
  request_payload jsonb;
  replay jsonb;
  result_value jsonb;
  review_id_value uuid;
  user_daily_count integer;
  organization_daily_count integer;
  boolean_field text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 131072
     or p_payload - array[
       'organization_id', 'idempotency_key', 'media_id', 'media_object_id',
       'parent_review_id', 'platform', 'product_category',
       'content_kind', 'declared_ad_status', 'caption_text', 'script_text',
       'technical_metrics', 'people_present', 'ad_label_confirmed',
       'ord_confirmed', 'advertiser_name', 'erid',
       'audience_over_10000', 'rkn_registered',
       'person_consent_confirmed', 'ai_generated',
       'external_ai_processing_confirmed',
       'ai_disclosure_confirmed', 'captions_confirmed',
       'mandatory_warning_confirmed', 'rights_confirmed',
       'claims_verified'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_start_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  if actor_role = 'operator' and not exists (
    select 1
    from content_factory.training_certifications certification
    where certification.organization_id = organization_id
      and certification.profile_id = user_id
      and certification.module_code = 'operator_final_exam'
      and certification.status = 'passed'
      and (
        certification.expires_at is null
        or certification.expires_at > now()
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'content_review_certification_required';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if p_payload ? 'media_id' and p_payload ? 'media_object_id'
     and p_payload ->> 'media_id' is distinct from
       p_payload ->> 'media_object_id' then
    raise exception using
      errcode = '22023',
      message = 'content_review_media_id_conflict';
  end if;
  if p_payload ? 'media_id' then
    media_id_value := content_factory_private.require_uuid(
      p_payload, 'media_id'
    );
  else
    media_id_value := content_factory_private.require_uuid(
      p_payload, 'media_object_id'
    );
  end if;
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  ));
  product_category_value := lower(content_factory_private.require_text(
    p_payload, 'product_category', 2, 40
  ));
  content_kind_value := lower(coalesce(
    nullif(btrim(p_payload ->> 'content_kind'), ''),
    nullif(btrim(p_payload ->> 'declared_ad_status'), ''),
    'unknown'
  ));
  people_present_value := lower(coalesce(
    nullif(btrim(p_payload ->> 'people_present'), ''),
    'unknown'
  ));
  caption_value := btrim(coalesce(p_payload ->> 'caption_text', ''));
  script_value := btrim(coalesce(p_payload ->> 'script_text', ''));
  advertiser_name_value := btrim(coalesce(
    p_payload ->> 'advertiser_name', ''
  ));
  erid_value := btrim(coalesce(p_payload ->> 'erid', ''));
  technical_metrics_value := coalesce(
    p_payload -> 'technical_metrics',
    '{}'::jsonb
  );

  if platform_value not in (
       'instagram', 'youtube', 'vk', 'telegram',
       'wildberries', 'tiktok', 'other'
     )
     or product_category_value not in (
       'cosmetics', 'baa', 'sports_food', 'food', 'household',
       'apparel', 'electronics', 'other'
     )
     or content_kind_value not in ('unknown', 'informational', 'advertising')
     or people_present_value not in ('unknown', 'yes', 'no')
     or length(caption_value) > 12000
     or length(script_value) > 30000
     or length(advertiser_name_value) > 300
     or length(erid_value) > 200
     or jsonb_typeof(technical_metrics_value) <> 'object'
     or length(technical_metrics_value::text) > 32768 then
    raise exception using
      errcode = '22023',
      message = 'content_review_input_invalid';
  end if;

  foreach boolean_field in array array[
    'ad_label_confirmed', 'ord_confirmed', 'audience_over_10000',
    'rkn_registered', 'person_consent_confirmed', 'ai_generated',
    'external_ai_processing_confirmed',
    'ai_disclosure_confirmed', 'captions_confirmed',
    'mandatory_warning_confirmed', 'rights_confirmed',
    'claims_verified'
  ] loop
    if p_payload ? boolean_field
       and jsonb_typeof(p_payload -> boolean_field) <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = boolean_field || '_invalid';
    end if;
  end loop;
  ai_generated_value := coalesce(
    (p_payload ->> 'ai_generated')::boolean,
    false
  );

  select media.* into media_row
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where media.organization_id = organization_id
    and media.id = media_id_value
    and media.status = 'ready'
    and media.mime_type in (
      'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
    )
    and (
      manager_scope
      or media.owner_id = user_id
      or task.assignee_id = user_id
    );

  if media_row.id is null then
    raise exception using
      errcode = '42501',
      message = 'content_review_media_not_accessible';
  end if;

  generated_media_value :=
    media_row.metadata ->> 'kind' = 'generated_video';

  if media_row.product_id is not null then
    select product.* into product_row
    from content_factory.products product
    where product.organization_id = organization_id
      and product.id = media_row.product_id
      and product.status = 'active'
    for share;
  end if;

  if generated_media_value then
    select task.* into review_task_row
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.id = media_row.task_id
      and task.task_type = 'video_review'
    for share;

    if review_task_row.id is null
       or review_task_row.generation_job_id is null
       or review_task_row.product_id is distinct from media_row.product_id then
      raise exception using
        errcode = '55000',
        message = 'generated_video_review_task_invalid';
    end if;

    select job.* into generation_job_row
    from content_factory.generation_jobs job
    where job.organization_id = organization_id
      and job.id = review_task_row.generation_job_id
    for share;

    if generation_job_row.id is null
       or generation_job_row.mode <> 'real'
       or generation_job_row.status <> 'succeeded'
       or generation_job_row.product_id is distinct from media_row.product_id
       or generation_job_row.output ->> 'output_media_id'
            is distinct from media_row.id::text
       or media_row.metadata ->> 'generation_job_id'
            is distinct from generation_job_row.id::text then
      raise exception using
        errcode = '55000',
        message = 'generated_video_job_invalid';
    end if;

    platform_value := lower(btrim(coalesce(
      generation_job_row.input ->> 'platform',
      ''
    )));
    if platform_value not in (
       'instagram', 'tiktok', 'youtube', 'vk',
       'telegram', 'wildberries'
    ) then
      raise exception using
        errcode = '55000',
        message = 'generated_video_platform_invalid';
    end if;
    if platform_value = 'instagram' then
      raise exception using
        errcode = '55000',
        message = 'generated_video_platform_prohibited';
    end if;

    -- Paid generated product content is always reviewed as advertising and
    -- as AI-generated. Browser values cannot weaken this trusted provenance.
    content_kind_value := 'advertising';
    ai_generated_value := true;

    if product_row.id is null then
      raise exception using
        errcode = '55000',
        message = 'generated_video_product_invalid';
    end if;

    product_category_value := lower(btrim(coalesce(
      product_row.metadata ->> 'content_review_category',
      product_row.metadata ->> 'product_category',
      ''
    )));
    if product_category_value = '' then
      if not manager_scope then
        raise exception using
          errcode = '42501',
          message = 'content_review_product_category_unverified';
      end if;
      product_category_value := lower(content_factory_private.require_text(
        p_payload, 'product_category', 2, 40
      ));
      if product_category_value not in (
         'cosmetics', 'baa', 'sports_food', 'food', 'household',
         'apparel', 'electronics', 'other'
      ) then
        raise exception using
          errcode = '22023',
          message = 'content_review_product_category_invalid';
      end if;
      update content_factory.products product
      set metadata = product.metadata || jsonb_build_object(
            'content_review_category', product_category_value,
            'content_review_category_confirmed_by', user_id,
            'content_review_category_confirmed_at', now(),
            'content_review_category_ruleset', ruleset_value
          ),
          updated_at = now()
      where product.organization_id = organization_id
        and product.id = product_row.id
      returning * into product_row;
    elsif product_category_value is distinct from lower(
      btrim(p_payload ->> 'product_category')
    ) then
      raise exception using
        errcode = '22023',
        message = 'content_review_product_category_mismatch';
    end if;
    product_category_verified_value := true;
    product_category_source_value := 'product_metadata';
  end if;

  if nullif(btrim(coalesce(p_payload ->> 'parent_review_id', '')), '')
     is not null then
    parent_review_id_value := content_factory_private.require_uuid(
      p_payload, 'parent_review_id'
    );
  else
    select review.id into parent_review_id_value
    from content_factory.content_review_runs review
    join content_factory.media_objects parent_media
      on parent_media.organization_id = review.organization_id
     and parent_media.id = review.media_object_id
    where review.organization_id = organization_id
      and review.status = 'completed'
      and review.input ->> 'platform' = platform_value
      and review.input ->> 'product_category' = product_category_value
      and review.input ->> 'content_kind' = content_kind_value
      and (
        (
          media_row.product_id is not null
          and parent_media.product_id = media_row.product_id
        )
        or (
          media_row.product_id is null
          and review.media_object_id = media_id_value
        )
      )
    order by review.created_at desc, review.id desc
    limit 1;
  end if;

  if parent_review_id_value is not null then
    select review.* into parent_row
    from content_factory.content_review_runs review
    where review.organization_id = organization_id
      and review.id = parent_review_id_value
      and review.status = 'completed';
    if parent_row.id is null then
      raise exception using
        errcode = '22023',
        message = 'parent_content_review_invalid';
    end if;

    select media.product_id into parent_product_id
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.id = parent_row.media_object_id;
    if media_row.product_id is not null
       and parent_product_id is not null
       and media_row.product_id <> parent_product_id then
      raise exception using
        errcode = '22023',
        message = 'parent_content_review_product_mismatch';
    end if;
    if media_row.product_id is null
       and parent_row.media_object_id <> media_id_value then
      raise exception using
        errcode = '22023',
        message = 'parent_content_review_product_mismatch';
    end if;
    if parent_row.input ->> 'platform' is distinct from platform_value
       or parent_row.input ->> 'product_category'
            is distinct from product_category_value
       or parent_row.input ->> 'content_kind'
            is distinct from content_kind_value then
      raise exception using
        errcode = '22023',
        message = 'parent_content_review_context_mismatch';
    end if;
  end if;

  request_payload := jsonb_build_object(
    'media_id', media_id_value,
    'parent_review_id', parent_review_id_value,
    'platform', platform_value,
    'product_category', product_category_value,
    'product_category_verified', product_category_verified_value,
    'product_category_source', product_category_source_value,
    'content_kind', content_kind_value,
    'generation_job_id', generation_job_row.id,
    'caption_text', caption_value,
    'script_text', script_value,
    'technical_metrics', technical_metrics_value,
    'people_present', people_present_value,
    'advertiser_name', advertiser_name_value,
    'erid', erid_value,
    'ad_label_confirmed',
      coalesce((p_payload ->> 'ad_label_confirmed')::boolean, false),
    'ord_confirmed',
      coalesce((p_payload ->> 'ord_confirmed')::boolean, false),
    'audience_over_10000',
      coalesce((p_payload ->> 'audience_over_10000')::boolean, false),
    'rkn_registered',
      coalesce((p_payload ->> 'rkn_registered')::boolean, false),
    'person_consent_confirmed',
      coalesce((p_payload ->> 'person_consent_confirmed')::boolean, false),
    'external_ai_processing_confirmed',
      coalesce(
        (p_payload ->> 'external_ai_processing_confirmed')::boolean,
        false
      ),
    'ai_generated',
      ai_generated_value,
    'ai_disclosure_confirmed',
      coalesce((p_payload ->> 'ai_disclosure_confirmed')::boolean, false),
    'captions_confirmed',
      coalesce((p_payload ->> 'captions_confirmed')::boolean, false),
    'mandatory_warning_confirmed',
      coalesce((p_payload ->> 'mandatory_warning_confirmed')::boolean, false),
    'rights_confirmed',
      coalesce((p_payload ->> 'rights_confirmed')::boolean, false),
    'claims_verified',
      coalesce((p_payload ->> 'claims_verified')::boolean, false)
  );

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_start_content_review',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('content_review_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('content_review_quota:user')
  );

  update content_factory.content_review_runs review
  set status = 'cancelled',
      error_code = 'queued_dispatch_expired',
      error_message =
        'Content analysis was not dispatched. Start a new review.'
  where review.organization_id = organization_id
    and review.media_object_id = media_id_value
    and review.status = 'queued'
    and review.created_at <= now() - interval '2 minutes';

  select
    count(*) filter (where review.requested_by = user_id)::integer,
    count(*)::integer
  into user_daily_count, organization_daily_count
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.created_at >= now() - interval '24 hours';

  if user_daily_count >= 50 then
    raise exception using
      errcode = '54000',
      message = 'content_review_user_daily_limit';
  end if;
  if organization_daily_count >= 500 then
    raise exception using
      errcode = '54000',
      message = 'content_review_org_daily_limit';
  end if;

  begin
    insert into content_factory.content_review_runs (
      organization_id, media_object_id, requested_by, parent_review_id,
      status, media_sha256_snapshot, input, ruleset_version,
      request_hash, idempotency_key
    ) values (
      organization_id, media_id_value, user_id, parent_review_id_value,
      'queued', media_row.sha256, request_payload, ruleset_value,
      content_factory_private.json_hash(request_payload),
      idempotency_key_value
    )
    returning id into review_id_value;
  exception when unique_violation then
    if exists (
      select 1
      from content_factory.content_review_runs review
      where review.organization_id = organization_id
        and review.media_object_id = media_id_value
        and review.status in ('queued', 'processing')
    ) then
      raise exception using
        errcode = '55000',
        message = 'content_review_already_active';
    end if;
    raise;
  end;

  result_value := jsonb_build_object(
    'ok', true,
    'review_id', review_id_value,
    'status', 'queued',
    'media_id', media_id_value,
    'media_sha256', media_row.sha256,
    'ruleset_version', ruleset_value,
    'parent_review_id', parent_review_id_value
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'content_review_started',
    'content_review_run',
    review_id_value::text,
    jsonb_build_object(
      'media_id', media_id_value,
      'platform', platform_value,
      'product_category', product_category_value
    ),
    'content_review:' || idempotency_key_value
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_start_content_review',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_content_review_catalog(
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
  manager_scope boolean;
  media_limit_value integer := 50;
  run_limit_value integer := 50;
  media_value jsonb;
  runs_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'media_limit', 'run_limit'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_catalog_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );

  if p_payload ? 'media_limit' then
    if coalesce(p_payload ->> 'media_limit', '') !~ '^[0-9]{1,3}$' then
      raise exception using
        errcode = '22023',
        message = 'content_review_media_limit_invalid';
    end if;
    media_limit_value := (p_payload ->> 'media_limit')::integer;
  end if;
  if p_payload ? 'run_limit' then
    if coalesce(p_payload ->> 'run_limit', '') !~ '^[0-9]{1,3}$' then
      raise exception using
        errcode = '22023',
        message = 'content_review_run_limit_invalid';
    end if;
    run_limit_value := (p_payload ->> 'run_limit')::integer;
  end if;
  if media_limit_value not between 1 and 100
     or run_limit_value not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'content_review_catalog_limit_invalid';
  end if;

  select coalesce(jsonb_agg(item.value order by item.created_at desc, item.id desc), '[]'::jsonb)
  into media_value
  from (
    select media.id, media.created_at, jsonb_build_object(
      'id', media.id,
      'owner_id', media.owner_id,
      'task_id', media.task_id,
      'product_id', media.product_id,
      'object_name', media.object_name,
      'mime_type', media.mime_type,
      'size_bytes', media.size_bytes,
      'sha256', media.sha256,
      'metadata', media.metadata,
      'created_at', media.created_at
    ) as value
    from content_factory.media_objects media
    left join content_factory.creator_tasks task
      on task.organization_id = media.organization_id
     and task.id = media.task_id
    where media.organization_id = organization_id
      and media.status = 'ready'
      and media.mime_type in (
        'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
      )
      and (
        manager_scope
        or media.owner_id = user_id
        or task.assignee_id = user_id
      )
    order by media.created_at desc, media.id desc
    limit media_limit_value
  ) item;

  select coalesce(jsonb_agg(item.value order by item.created_at desc, item.id desc), '[]'::jsonb)
  into runs_value
  from (
    select review.id, review.created_at, jsonb_build_object(
      'id', review.id,
      'media_id', review.media_object_id,
      'requested_by', review.requested_by,
      'requested_by_name', coalesce(profile.display_name, profile.email),
      'parent_review_id', review.parent_review_id,
      'status', review.status,
      'platform', review.input ->> 'platform',
      'product_category', review.input ->> 'product_category',
      'content_kind', review.input ->> 'content_kind',
      'ruleset_version', review.ruleset_version,
      'media_sha256_snapshot', review.media_sha256_snapshot,
      'media_is_stale', (
        media.status <> 'ready'
        or media.sha256 <> review.media_sha256_snapshot
      ),
      'result_summary', jsonb_build_object(
        'overall_score', review.result -> 'overall_score',
        'compliance_status', review.result -> 'compliance_status',
        'blockers_count', review.result -> 'blockers_count',
        'warnings_count', review.result -> 'warnings_count',
        'comparison', review.result -> 'comparison'
      ),
      'error_code', review.error_code,
      'created_at', review.created_at,
      'finished_at', review.finished_at,
      'decision', case
        when decision.id is null then null
        else jsonb_build_object(
          'id', decision.id,
          'decision', decision.decision,
          'comment', decision.comment,
          'reason', decision.comment,
          'media_watched_confirmed', decision.media_watched_confirmed,
          'decided_by', decision.decided_by,
          'decided_by_name', coalesce(decider.display_name, decider.email),
          'created_at', decision.created_at
        )
      end
    ) as value
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    left join content_factory.creator_tasks task
      on task.organization_id = media.organization_id
     and task.id = media.task_id
    join content_factory.profiles profile
      on profile.id = review.requested_by
    left join content_factory.content_review_decisions decision
      on decision.organization_id = review.organization_id
     and decision.review_id = review.id
    left join content_factory.profiles decider
      on decider.id = decision.decided_by
    where review.organization_id = organization_id
      and (
        manager_scope
        or review.requested_by = user_id
        or media.owner_id = user_id
        or task.assignee_id = user_id
      )
    order by review.created_at desc, review.id desc
    limit run_limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    'ruleset', jsonb_build_object(
      'version', 'ru-content-compliance-2026-07-16.1',
      'jurisdiction', 'RU',
      'human_legal_review_required', true
    ),
    'role', actor_role,
    'media', media_value,
    'recent_reviews', runs_value,
    'options', jsonb_build_object(
      'platforms', jsonb_build_array(
        'instagram', 'youtube', 'vk', 'telegram',
        'wildberries', 'tiktok', 'other'
      ),
      'product_categories', jsonb_build_array(
        'cosmetics', 'baa', 'sports_food', 'food',
        'household', 'apparel', 'electronics', 'other'
      ),
      'content_kinds', jsonb_build_array(
        'unknown', 'informational', 'advertising'
      )
    )
  );
end;
$$;

create or replace function public.creator_content_review_status(
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
  manager_scope boolean;
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  task_assignee_id uuid;
  decision_value jsonb;
  queue_timeout_message text :=
    'Content analysis was not dispatched. Start a new review.';
  timeout_message text := 'Content analysis timed out safely. Start a new review.';
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'review_id'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_status_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );

  if nullif(btrim(coalesce(p_payload ->> 'organization_id', '')), '')
     is not null then
    organization_id := content_factory_private.resolve_organization(p_payload);
    actor_role := content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
  else
    select review.organization_id, membership.role
      into organization_id, actor_role
    from content_factory.content_review_runs review
    join content_factory.memberships membership
      on membership.organization_id = review.organization_id
     and membership.profile_id = user_id
     and membership.status = 'active'
    join content_factory.organizations organization
      on organization.id = review.organization_id
     and organization.status = 'active'
    where review.id = review_id_value;
    if organization_id is null then
      raise exception using
        errcode = '22023',
        message = 'content_review_not_found';
    end if;
    perform content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
  end if;

  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value;

  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = review_row.media_object_id;

  if media_row.task_id is not null then
    select task.assignee_id into task_assignee_id
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.id = media_row.task_id;
  end if;

  if not manager_scope
     and review_row.requested_by <> user_id
     and media_row.owner_id <> user_id
     and task_assignee_id is distinct from user_id then
    raise exception using
      errcode = '42501',
      message = 'content_review_not_allowed';
  end if;

  -- The browser dispatches the Edge worker after this durable queue insert.
  -- If the tab or network dies in that gap, expire the abandoned queue item
  -- so the exact media can be reviewed again without retrying a provider POST.
  if review_row.status = 'queued'
     and review_row.created_at <= now() - interval '2 minutes' then
    update content_factory.content_review_runs review
    set status = 'cancelled',
        error_code = 'queued_dispatch_expired',
        error_message = queue_timeout_message
    where review.organization_id = organization_id
      and review.id = review_id_value
      and review.status = 'queued'
      and review.created_at <= now() - interval '2 minutes'
    returning * into review_row;
    if not found then
      select review.* into review_row
      from content_factory.content_review_runs review
      where review.organization_id = organization_id
        and review.id = review_id_value;
    end if;
  end if;

  -- A timeout is terminal. Never reclaim an uncertain paid provider call.
  if review_row.status = 'processing'
     and review_row.lease_expires_at <= now() then
    update content_factory.content_review_runs review
    set status = 'failed',
        error_code = 'processing_lease_expired',
        error_message = timeout_message,
        completion_hash = content_factory_private.json_hash(jsonb_build_object(
          'status', 'failed',
          'error_code', 'processing_lease_expired',
          'error_message', timeout_message
        ))
    where review.organization_id = organization_id
      and review.id = review_id_value
      and review.status = 'processing'
      and review.lease_expires_at <= now()
    returning * into review_row;
    if not found then
      select review.* into review_row
      from content_factory.content_review_runs review
      where review.organization_id = organization_id
        and review.id = review_id_value;
    end if;
  end if;

  select jsonb_build_object(
    'id', decision.id,
    'decision', decision.decision,
    'comment', decision.comment,
    'reason', decision.comment,
    'media_watched_confirmed', decision.media_watched_confirmed,
    'resolved_recommendation_codes',
      decision.resolved_recommendation_codes,
    'risk_acknowledgements', decision.risk_acknowledgements,
    'decided_by', decision.decided_by,
    'decided_by_name', coalesce(profile.display_name, profile.email),
    'created_at', decision.created_at
  ) into decision_value
  from content_factory.content_review_decisions decision
  join content_factory.profiles profile
    on profile.id = decision.decided_by
  where decision.organization_id = organization_id
    and decision.review_id = review_id_value;

  return jsonb_build_object(
    'ok', true,
    'run', jsonb_build_object(
      'id', review_row.id,
      'status', review_row.status,
      'media_id', review_row.media_object_id,
      'requested_by', review_row.requested_by,
      'parent_review_id', review_row.parent_review_id,
      'input', review_row.input,
      'result', review_row.result,
      'moderation', review_row.moderation,
      'ruleset_version', review_row.ruleset_version,
      'model_provider', review_row.model_provider,
      'model_version', review_row.model_version,
      'media_sha256_snapshot', review_row.media_sha256_snapshot,
      'media_is_stale', (
        media_row.status <> 'ready'
        or media_row.sha256 <> review_row.media_sha256_snapshot
      ),
      'error_code', review_row.error_code,
      'error_message', review_row.error_message,
      'created_at', review_row.created_at,
      'started_at', review_row.started_at,
      'lease_expires_at', review_row.lease_expires_at,
      'finished_at', review_row.finished_at
    ),
    'media', jsonb_build_object(
      'id', media_row.id,
      'owner_id', media_row.owner_id,
      'task_id', media_row.task_id,
      'product_id', media_row.product_id,
      'object_name', media_row.object_name,
      'mime_type', media_row.mime_type,
      'size_bytes', media_row.size_bytes,
      'sha256', media_row.sha256,
      'status', media_row.status,
      'metadata', media_row.metadata
    ),
    'decision', decision_value
  );
end;
$$;

create or replace function public.creator_decide_content_review(
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
  review_id_value uuid;
  idempotency_key_value text;
  decision_value text;
  comment_value text;
  resolved_codes_value jsonb;
  acknowledgements_value jsonb;
  media_watched_value boolean := false;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  review_task_row content_factory.creator_tasks%rowtype;
  generation_job_row content_factory.generation_jobs%rowtype;
  decision_id_value uuid;
  placement_task_id_value uuid;
  placement_id_value uuid;
  placement_platform_value text;
  destination_value text;
  placement_request_value jsonb;
  item jsonb;
  request_payload jsonb;
  replay jsonb;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 65536
     or p_payload - array[
       'organization_id', 'review_id', 'idempotency_key',
       'decision', 'comment', 'reason', 'resolved_recommendation_codes',
       'risk_acknowledgements', 'media_watched_confirmed'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_decision_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  decision_value := lower(content_factory_private.require_text(
    p_payload, 'decision', 3, 40
  ));
  if p_payload ? 'comment' and p_payload ? 'reason'
     and btrim(p_payload ->> 'comment') is distinct from
       btrim(p_payload ->> 'reason') then
    raise exception using
      errcode = '22023',
      message = 'content_review_decision_reason_conflict';
  end if;
  comment_value := btrim(coalesce(
    nullif(p_payload ->> 'reason', ''),
    nullif(p_payload ->> 'comment', ''),
    ''
  ));
  resolved_codes_value := coalesce(
    p_payload -> 'resolved_recommendation_codes',
    '[]'::jsonb
  );
  acknowledgements_value := coalesce(
    p_payload -> 'risk_acknowledgements',
    '[]'::jsonb
  );
  if p_payload ? 'media_watched_confirmed'
     and jsonb_typeof(p_payload -> 'media_watched_confirmed') <> 'boolean' then
    raise exception using
      errcode = '22023',
      message = 'media_watched_confirmed_invalid';
  end if;
  media_watched_value := coalesce(
    (p_payload ->> 'media_watched_confirmed')::boolean,
    false
  );

  if decision_value not in ('approved', 'needs_changes', 'rejected')
     or length(comment_value) not between 10 and 4000
     or jsonb_typeof(resolved_codes_value) <> 'array'
     or jsonb_array_length(resolved_codes_value) > 100
     or length(resolved_codes_value::text) > 16384
     or jsonb_typeof(acknowledgements_value) <> 'array'
     or jsonb_array_length(acknowledgements_value) > 50
     or length(acknowledgements_value::text) > 16384 then
    raise exception using
      errcode = '22023',
      message = 'content_review_decision_invalid';
  end if;

  for item in
    select element.value
    from jsonb_array_elements(resolved_codes_value) element(value)
  loop
    if jsonb_typeof(item) <> 'string'
       or length(btrim(item #>> '{}')) not between 2 and 100
       or (item #>> '{}') !~* '^[a-z0-9][a-z0-9_.:-]{1,99}$' then
      raise exception using
        errcode = '22023',
        message = 'resolved_recommendation_code_invalid';
    end if;
  end loop;

  for item in
    select element.value
    from jsonb_array_elements(acknowledgements_value) element(value)
  loop
    if jsonb_typeof(item) <> 'string'
       or length(btrim(item #>> '{}')) not between 2 and 100
       or (item #>> '{}') !~* '^[a-z0-9][a-z0-9_.:-]{1,99}$' then
      raise exception using
        errcode = '22023',
        message = 'risk_acknowledgement_invalid';
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

  request_payload := jsonb_build_object(
    'review_id', review_id_value,
    'decision', decision_value,
    'reason', comment_value,
    'resolved_recommendation_codes', resolved_codes_value,
    'risk_acknowledgements', acknowledgements_value,
    'media_watched_confirmed', media_watched_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_decide_content_review',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('content_review_decision:' || review_id_value::text)
  );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value
  for update;

  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = review_row.media_object_id;

  if media_row.task_id is not null then
    select task.* into review_task_row
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.id = media_row.task_id;
  end if;

  if media_row.metadata ->> 'kind' = 'generated_video'
     and review_task_row.generation_job_id is not null then
    select job.* into generation_job_row
    from content_factory.generation_jobs job
    where job.organization_id = organization_id
      and job.id = review_task_row.generation_job_id;
  end if;

  if review_row.status <> 'completed' then
    raise exception using
      errcode = '55000',
      message = 'content_review_not_decidable';
  end if;
  if exists (
    select 1
    from content_factory.content_review_decisions existing
    where existing.organization_id = organization_id
      and existing.review_id = review_id_value
  ) then
    raise exception using
      errcode = '55000',
      message = 'content_review_decision_already_recorded';
  end if;

  if exists (
    select 1
    from jsonb_array_elements_text(resolved_codes_value) supplied(code)
    where not exists (
      select 1
      from jsonb_array_elements(
        coalesce(review_row.result -> 'recommendations', '[]'::jsonb)
      ) recommendation(value)
      where recommendation.value ->> 'code' = supplied.code
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'resolved_recommendation_code_unknown';
  end if;

  if exists (
    select 1
    from jsonb_array_elements_text(acknowledgements_value) supplied(code)
    where not exists (
      select 1
      from jsonb_array_elements(
        coalesce(review_row.result -> 'findings', '[]'::jsonb)
      ) finding(value)
      where finding.value ->> 'code' = supplied.code
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'risk_acknowledgement_unknown';
  end if;

  if (
    content_factory_private.content_review_is_high_risk(review_row.result)
    or media_row.metadata ->> 'kind' = 'generated_video'
  ) and (
    review_row.requested_by = user_id
    or media_row.owner_id = user_id
    or review_task_row.assignee_id = user_id
    or generation_job_row.requested_by = user_id
    or generation_job_row.assigned_to = user_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'high_risk_content_requires_independent_review';
  end if;

  if decision_value = 'approved' then
    if not media_watched_value then
      raise exception using
        errcode = '22023',
        message = 'content_review_media_watch_required';
    end if;
    if media_row.status <> 'ready'
       or media_row.sha256 <> review_row.media_sha256_snapshot then
      raise exception using
        errcode = '55000',
        message = 'content_review_media_stale';
    end if;
    if coalesce((review_row.result ->> 'blockers_count')::integer, 0) > 0
       or review_row.result ->> 'compliance_status' = 'block' then
      raise exception using
        errcode = '55000',
        message = 'content_review_blockers_unresolved';
    end if;
    if review_row.result ->> 'compliance_status' = 'human_review'
       and exists (
         select 1
         from jsonb_array_elements(
           coalesce(review_row.result -> 'findings', '[]'::jsonb)
         ) finding(value)
         where (
           finding.value ->> 'severity' in ('blocker', 'high')
           or finding.value -> 'human_review_required'
                is not distinct from 'true'::jsonb
         )
         and not acknowledgements_value @> jsonb_build_array(
           finding.value ->> 'code'
         )
       ) then
      raise exception using
        errcode = '22023',
        message = 'content_review_risk_acknowledgement_required';
    end if;

    if media_row.metadata ->> 'kind' = 'generated_video' then
      placement_platform_value := lower(btrim(coalesce(
        generation_job_row.input ->> 'platform',
        ''
      )));
      if generation_job_row.id is null
         or generation_job_row.mode <> 'real'
         or generation_job_row.status <> 'succeeded'
         or generation_job_row.product_id is distinct from media_row.product_id
         or generation_job_row.output ->> 'output_media_id'
              is distinct from media_row.id::text
         or review_row.input ->> 'generation_job_id'
              is distinct from generation_job_row.id::text
         or review_row.input ->> 'platform'
              is distinct from placement_platform_value
         or placement_platform_value = 'instagram'
         or review_row.input ->> 'content_kind'
              is distinct from 'advertising'
         or review_row.input -> 'ai_generated'
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
           placement_platform_value = 'youtube'
           and review_row.input -> 'ai_disclosure_confirmed'
                is distinct from 'true'::jsonb
         )
         or (
           review_row.input ->> 'product_category' = 'baa'
           and review_row.input -> 'mandatory_warning_confirmed'
                is distinct from 'true'::jsonb
         )
         or (
           review_row.input -> 'audience_over_10000'
                is not distinct from 'true'::jsonb
           and review_row.input -> 'rkn_registered'
                is distinct from 'true'::jsonb
         )
         or review_row.input -> 'product_category_verified'
              is distinct from 'true'::jsonb
         or review_row.input ->> 'product_category_source'
              is distinct from 'product_metadata'
         or jsonb_typeof(review_row.result -> 'ad_probability')
              is distinct from 'number' then
        raise exception using
          errcode = '55000',
          message = 'generated_video_review_context_invalid';
      end if;
      if not exists (
        select 1
        from content_factory.products product
        where product.organization_id = organization_id
          and product.id = media_row.product_id
          and lower(btrim(coalesce(
            product.metadata ->> 'content_review_category',
            product.metadata ->> 'product_category',
            ''
          ))) = review_row.input ->> 'product_category'
      ) then
        raise exception using
          errcode = '55000',
          message = 'generated_video_product_context_invalid';
      end if;
    end if;
  end if;

  insert into content_factory.content_review_decisions (
    organization_id, review_id, decided_by, decision, comment,
    resolved_recommendation_codes, risk_acknowledgements,
    media_watched_confirmed, review_completion_hash,
    media_sha256_snapshot, idempotency_key
  ) values (
    organization_id, review_id_value, user_id, decision_value, comment_value,
    resolved_codes_value, acknowledgements_value,
    media_watched_value, review_row.completion_hash,
    review_row.media_sha256_snapshot,
    idempotency_key_value
  )
  returning id into decision_id_value;

  if decision_value = 'approved'
     and media_row.metadata ->> 'kind' = 'generated_video' then
    select task.* into review_task_row
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.id = media_row.task_id
      and task.task_type = 'video_review'
    for update;

    if review_task_row.id is null
       or review_task_row.generation_job_id is null
       or review_task_row.status <> 'review' then
      raise exception using
        errcode = '55000',
        message = 'generated_video_review_task_invalid';
    end if;

    select job.* into generation_job_row
    from content_factory.generation_jobs job
    where job.organization_id = organization_id
      and job.id = review_task_row.generation_job_id
    for update;

    if generation_job_row.id is null
       or generation_job_row.mode <> 'real'
       or generation_job_row.status <> 'succeeded'
       or generation_job_row.output ->> 'output_media_id'
            is distinct from media_row.id::text then
      raise exception using
        errcode = '55000',
        message = 'generated_video_job_invalid';
    end if;

    placement_platform_value := lower(btrim(coalesce(
      generation_job_row.input ->> 'platform',
      ''
    )));
    destination_value := btrim(coalesce(
      generation_job_row.input ->> 'destination_ref',
      ''
    ));
    if placement_platform_value not in (
       'instagram', 'tiktok', 'youtube', 'vk',
       'telegram', 'wildberries'
    ) or length(destination_value) not between 2 and 240 then
      raise exception using
        errcode = '55000',
        message = 'generated_video_placement_input_invalid';
    end if;

    update content_factory.creator_tasks task
    set status = 'done',
        submitted_at = coalesce(task.submitted_at, now()),
        completed_at = coalesce(task.completed_at, now()),
        result = task.result || jsonb_build_object(
          'content_review_id', review_row.id,
          'content_review_decision_id', decision_id_value,
          'content_review_media_id', media_row.id,
          'content_review_media_sha256', media_row.sha256,
          'content_review_ruleset', review_row.ruleset_version,
          'content_review_approved_by', user_id,
          'content_review_approved_at', now(),
          'media_watched_confirmed', media_watched_value
        ),
        updated_at = now()
    where task.organization_id = organization_id
      and task.id = review_task_row.id
    returning * into review_task_row;

    if review_task_row.payout_minor > 0 then
      insert into content_factory.creator_payouts (
        organization_id, profile_id, task_id, amount_minor,
        currency, status, reason
      ) values (
        organization_id,
        review_task_row.assignee_id,
        review_task_row.id,
        review_task_row.payout_minor,
        'RUB',
        'pending',
        'Approved generated video review: ' || review_row.id::text
      )
      on conflict on constraint creator_payouts_org_task_uq do nothing;
    end if;

    select task.id into placement_task_id_value
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.idempotency_key =
        'content-review-placement-task:' || review_row.id::text;

    if placement_task_id_value is null then
      insert into content_factory.creator_tasks (
        organization_id, assignee_id, created_by, product_id,
        generation_job_id, task_type, title, instructions,
        status, priority, payout_minor, result, idempotency_key
      ) values (
        organization_id,
        review_task_row.assignee_id,
        user_id,
        generation_job_row.product_id,
        generation_job_row.id,
        'placement',
        left(
          'Опубликовать одобренное видео — ' ||
            coalesce(generation_job_row.input ->> 'product_name', 'контент'),
          240
        ),
        'Опубликуйте только одобренный файл. После публикации добавьте финальную HTTPS-ссылку.',
        'todo',
        2,
        0,
        jsonb_build_object(
          'content_review_id', review_row.id,
          'content_review_decision_id', decision_id_value,
          'source_media_id', media_row.id,
          'media_sha256', media_row.sha256,
          'ruleset_version', review_row.ruleset_version,
          'platform', placement_platform_value,
          'destination_ref', destination_value
        ),
        'content-review-placement-task:' || review_row.id::text
      )
      returning id into placement_task_id_value;
    elsif not exists (
      select 1
      from content_factory.creator_tasks task
      where task.organization_id = organization_id
        and task.id = placement_task_id_value
        and task.task_type = 'placement'
        and task.generation_job_id = generation_job_row.id
        and task.assignee_id = review_task_row.assignee_id
        and task.payout_minor = 0
    ) then
      raise exception using
        errcode = '23505',
        message = 'content_review_placement_task_conflict';
    end if;

    placement_request_value := jsonb_build_object(
      'content_review_id', review_row.id,
      'decision_id', decision_id_value,
      'generation_job_id', generation_job_row.id,
      'media_id', media_row.id,
      'media_sha256', media_row.sha256,
      'platform', placement_platform_value,
      'destination_ref', destination_value
    );

    insert into content_factory.placements (
      organization_id, product_id, generation_job_id, task_id,
      assigned_to, created_by, platform, destination_ref,
      status, request_hash, idempotency_key, metadata
    ) values (
      organization_id,
      generation_job_row.product_id,
      generation_job_row.id,
      placement_task_id_value,
      review_task_row.assignee_id,
      user_id,
      placement_platform_value,
      destination_value,
      'ready',
      content_factory_private.json_hash(placement_request_value),
      'content-review-placement:' || review_row.id::text,
      jsonb_build_object(
        'content_review_id', review_row.id,
        'content_review_decision_id', decision_id_value,
        'source_media_id', media_row.id,
        'media_sha256', media_row.sha256,
        'ruleset_version', review_row.ruleset_version,
        'media_watched_confirmed', media_watched_value
      )
    )
    on conflict (organization_id, task_id) do nothing
    returning id into placement_id_value;

    if placement_id_value is null then
      select placement.id into placement_id_value
      from content_factory.placements placement
      where placement.organization_id = organization_id
        and placement.task_id = placement_task_id_value
        and placement.generation_job_id = generation_job_row.id
        and placement.platform = placement_platform_value
        and placement.destination_ref = destination_value
        and placement.metadata ->> 'content_review_id'
              = review_row.id::text;
      if placement_id_value is null then
        raise exception using
          errcode = '23505',
          message = 'content_review_placement_conflict';
      end if;
    end if;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'review_id', review_id_value,
    'decision_id', decision_id_value,
    'decision', decision_value,
    'decided_by', user_id,
    'media_sha256', review_row.media_sha256_snapshot,
    'review_task_id', review_task_row.id,
    'placement_task_id', placement_task_id_value,
    'placement_id', placement_id_value
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'content_review_decided',
    'content_review_run',
    review_id_value::text,
    jsonb_build_object(
      'decision', decision_value,
      'reviewer_role', actor_role,
      'high_risk',
        content_factory_private.content_review_is_high_risk(review_row.result)
    ),
    'content_review_decision:' || idempotency_key_value
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_content_review',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.system_claim_content_review(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_id_value uuid;
  review_row content_factory.content_review_runs%rowtype;
  media_row content_factory.media_objects%rowtype;
  claimed_value boolean := false;
  parent_result_value jsonb;
  product_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['review_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_claim_payload_invalid';
  end if;
  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.id = review_id_value
  for update;

  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = review_row.organization_id
    and media.id = review_row.media_object_id;

  if review_row.status = 'queued'
     and (
       media_row.id is null
       or media_row.status <> 'ready'
       or media_row.sha256 <> review_row.media_sha256_snapshot
     ) then
    update content_factory.content_review_runs review
    set status = 'cancelled',
        error_code = 'media_stale_before_review',
        error_message =
          'The exact media changed before analysis. Start a new review.'
    where review.id = review_id_value
      and review.status = 'queued'
    returning * into review_row;
  elsif review_row.status = 'queued' then
    update content_factory.content_review_runs review
    set status = 'processing'
    where review.id = review_id_value
      and review.status = 'queued'
    returning * into review_row;
    claimed_value := found;
  end if;

  if review_row.parent_review_id is not null then
    select parent.result into parent_result_value
    from content_factory.content_review_runs parent
    where parent.organization_id = review_row.organization_id
      and parent.id = review_row.parent_review_id
      and parent.status = 'completed';
  end if;

  if media_row.product_id is not null then
    select jsonb_build_object(
      'id', product.id,
      'sku', product.sku,
      'title', product.title,
      'current_wb_article', product.current_wb_article,
      'metadata', product.metadata
    ) into product_value
    from content_factory.products product
    where product.organization_id = review_row.organization_id
      and product.id = media_row.product_id;
  end if;

  return jsonb_build_object(
    'ok', true,
    'claimed', claimed_value,
    'run', jsonb_build_object(
      'id', review_row.id,
      'status', review_row.status,
      'organization_id', review_row.organization_id,
      'requested_by', review_row.requested_by,
      'parent_review_id', review_row.parent_review_id,
      'lease_expires_at', review_row.lease_expires_at,
      'ruleset_version', review_row.ruleset_version,
      'input', review_row.input,
      'parent_result', parent_result_value,
      'product', product_value,
      'media', jsonb_build_object(
        'id', media_row.id,
        'owner_id', media_row.owner_id,
        'task_id', media_row.task_id,
        'product_id', media_row.product_id,
        'bucket_id', media_row.bucket_id,
        'object_name', media_row.object_name,
        'mime_type', media_row.mime_type,
        'size_bytes', media_row.size_bytes,
        'sha256', media_row.sha256,
        'status', media_row.status,
        'metadata', media_row.metadata,
        'snapshot_matches', (
          media_row.sha256 = review_row.media_sha256_snapshot
        )
      )
    )
  );
end;
$$;

create or replace function public.system_complete_content_review(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  review_id_value uuid;
  status_value text;
  review_row content_factory.content_review_runs%rowtype;
  result_value jsonb := coalesce(p_payload -> 'result', '{}'::jsonb);
  moderation_value jsonb := coalesce(p_payload -> 'moderation', '{}'::jsonb);
  ruleset_value text;
  provider_value text;
  model_value text;
  error_code_value text;
  error_message_value text;
  completion_payload jsonb;
  completion_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 360000
     or p_payload - array[
       'review_id', 'status', 'result', 'moderation',
       'ruleset_version', 'model_provider', 'model_version',
       'error_code', 'error_message'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_completion_payload_invalid';
  end if;

  review_id_value := content_factory_private.require_uuid(
    p_payload, 'review_id'
  );
  status_value := lower(content_factory_private.require_text(
    p_payload, 'status', 3, 40
  ));
  if status_value not in ('completed', 'failed') then
    raise exception using
      errcode = '22023',
      message = 'content_review_completion_status_invalid';
  end if;

  completion_payload := p_payload - 'review_id';
  completion_hash_value := content_factory_private.json_hash(
    completion_payload
  );

  select review.* into review_row
  from content_factory.content_review_runs review
  where review.id = review_id_value
  for update;

  if review_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'content_review_not_found';
  end if;

  if review_row.status in ('completed', 'failed', 'cancelled') then
    if review_row.status = status_value
       and review_row.completion_hash = completion_hash_value then
      return jsonb_build_object(
        'ok', true,
        'review_id', review_id_value,
        'status', review_row.status,
        'idempotent', true
      );
    end if;
    raise exception using
      errcode = '23505',
      message = 'content_review_completion_conflict';
  end if;

  if review_row.status <> 'processing' then
    raise exception using
      errcode = '55000',
      message = 'content_review_not_claimed';
  end if;

  if status_value = 'failed' then
    error_code_value := content_factory_private.require_text(
      p_payload, 'error_code', 3, 100
    );
    error_message_value := nullif(
      btrim(coalesce(p_payload ->> 'error_message', '')),
      ''
    );
    if error_message_value is not null
       and length(error_message_value) > 2000 then
      raise exception using
        errcode = '22023',
        message = 'content_review_error_invalid';
    end if;

    update content_factory.content_review_runs review
    set status = 'failed',
        error_code = error_code_value,
        error_message = error_message_value,
        completion_hash = completion_hash_value
    where review.id = review_id_value;

    return jsonb_build_object(
      'ok', true,
      'review_id', review_id_value,
      'status', 'failed',
      'idempotent', false
    );
  end if;

  ruleset_value := content_factory_private.require_text(
    p_payload, 'ruleset_version', 3, 120
  );
  provider_value := content_factory_private.require_text(
    p_payload, 'model_provider', 2, 80
  );
  model_value := content_factory_private.require_text(
    p_payload, 'model_version', 1, 120
  );

  if ruleset_value <> review_row.ruleset_version
     or jsonb_typeof(moderation_value) <> 'object'
     or length(moderation_value::text) > 65536 then
    raise exception using
      errcode = '22023',
      message = 'content_review_completion_metadata_invalid';
  end if;

  perform content_factory_private.validate_content_review_result(
    result_value
  );

  update content_factory.content_review_runs review
  set status = 'completed',
      result = result_value,
      moderation = moderation_value,
      model_provider = provider_value,
      model_version = model_value,
      completion_hash = completion_hash_value
  where review.id = review_id_value;

  return jsonb_build_object(
    'ok', true,
    'review_id', review_id_value,
    'status', 'completed',
    'idempotent', false,
    'overall_score', result_value -> 'overall_score',
    'compliance_status', result_value -> 'compliance_status',
    'blockers_count', result_value -> 'blockers_count',
    'warnings_count', result_value -> 'warnings_count'
  );
end;
$$;

create or replace function content_factory_private.placement_url_matches_platform(
  platform_value text,
  final_url_value text
)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  authority_value text;
  host_value text;
begin
  if final_url_value is null then
    return true;
  end if;
  if final_url_value !~ '^https://[^[:space:]]{3,1992}$' then
    return false;
  end if;

  authority_value := split_part(substr(final_url_value, 9), '/', 1);
  if authority_value = ''
     or authority_value ~ '[@:?#]'
     or authority_value !~ '^[A-Za-z0-9.-]+$'
     or authority_value ~ '(^|[.])-'
     or authority_value ~ '-([.]|$)'
     or authority_value ~ '[.]{2,}'
     or right(authority_value, 1) = '.' then
    return false;
  end if;
  host_value := lower(authority_value);

  return case lower(platform_value)
    when 'instagram' then host_value in ('instagram.com', 'www.instagram.com')
    when 'tiktok' then host_value in ('tiktok.com', 'www.tiktok.com')
    when 'youtube' then host_value in (
      'youtube.com', 'www.youtube.com', 'm.youtube.com'
    )
    when 'vk' then host_value in (
      'vk.com', 'www.vk.com', 'm.vk.com',
      'vkvideo.ru', 'www.vkvideo.ru'
    )
    when 'telegram' then host_value = 't.me'
    when 'wildberries' then host_value in (
      'wildberries.ru', 'www.wildberries.ru'
    )
    else false
  end;
end;
$$;

create or replace function content_factory_private.guard_placement_final_url()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.final_url is not null
     and not content_factory_private.placement_url_matches_platform(
       new.platform,
       new.final_url
     ) then
    raise exception using
      errcode = '22023',
      message = 'final_url_platform_mismatch';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_placement_final_url
  on content_factory.placements;
create trigger guard_placement_final_url
before insert or update of platform, final_url
on content_factory.placements
for each row execute function
  content_factory_private.guard_placement_final_url();

revoke all on function public.creator_content_review_catalog(jsonb)
  from public, anon;
revoke all on function public.creator_start_content_review(jsonb)
  from public, anon;
revoke all on function public.creator_content_review_status(jsonb)
  from public, anon;
revoke all on function public.creator_decide_content_review(jsonb)
  from public, anon;

grant execute on function public.creator_content_review_catalog(jsonb)
  to authenticated;
grant execute on function public.creator_start_content_review(jsonb)
  to authenticated;
grant execute on function public.creator_content_review_status(jsonb)
  to authenticated;
grant execute on function public.creator_decide_content_review(jsonb)
  to authenticated;

revoke all on function public.system_claim_content_review(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_complete_content_review(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_claim_content_review(jsonb)
  to service_role;
grant execute on function public.system_complete_content_review(jsonb)
  to service_role;

revoke all on all functions in schema content_factory_private
  from public, anon, authenticated;
grant execute on all functions in schema content_factory_private
  to service_role;

commit;

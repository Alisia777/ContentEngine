begin;

-- A policy hash must remain explainable after the job is complete.  Store only
-- its bounded structural guard profile: no prompt copy, reviewer prose,
-- transcript, findings, recommendations or generated text crosses this
-- boundary.
create or replace function
  content_factory_private.valid_generation_quality_guard_variants(
    p_guard_codes jsonb,
    p_guard_variants jsonb
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  guard_code text;
  variant_value jsonb;
begin
  if p_guard_codes is null
     or p_guard_variants is null
     or not content_factory_private
       .valid_generation_quality_guard_codes(p_guard_codes)
     or jsonb_typeof(p_guard_variants) is distinct from 'object'
     or (
       select count(*)
       from jsonb_object_keys(p_guard_variants)
     ) <> jsonb_array_length(p_guard_codes) then
    return false;
  end if;
  for guard_code in
    select item.value
    from jsonb_array_elements_text(p_guard_codes) item(value)
  loop
    variant_value := p_guard_variants -> guard_code;
    if variant_value is null
       or jsonb_typeof(variant_value) <> 'number'
       or variant_value not in ('1'::jsonb, '2'::jsonb) then
      return false;
    end if;
  end loop;
  if exists (
    select 1
    from jsonb_object_keys(p_guard_variants) item(value)
    where not (p_guard_codes ? item.value)
  ) then
    return false;
  end if;
  return true;
exception when others then
  return false;
end;
$$;

revoke all on function
  content_factory_private
    .valid_generation_quality_guard_variants(jsonb, jsonb)
  from public, anon, authenticated, service_role;

create table if not exists
  content_factory.generation_learning_policy_snapshots (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    platform text not null check (
      platform in (
        'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
      )
    ),
    model text not null check (
      model in ('gen4_turbo', 'seedance2_fast', 'seedream5_lite')
    ),
    policy_hash text not null check (
      policy_hash ~ '^[0-9a-f]{64}$'
    ),
    guard_codes jsonb not null,
    guard_variants jsonb not null,
    created_by uuid not null,
    created_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      content_factory_private.valid_generation_quality_guard_variants(
        guard_codes,
        guard_variants
      )
    ),
    unique (
      organization_id,
      product_id,
      platform,
      model,
      policy_hash
    )
);

create index if not exists generation_learning_policy_snapshots_scope_idx
  on content_factory.generation_learning_policy_snapshots
  (organization_id, product_id, platform, model, created_at desc);

alter table content_factory.generation_learning_policy_snapshots
  enable row level security;
revoke all on content_factory.generation_learning_policy_snapshots
  from public, anon, authenticated;
grant all on content_factory.generation_learning_policy_snapshots
  to service_role;

create or replace function
  content_factory_private.guard_generation_learning_policy_snapshot_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_learning_policy_snapshot_append_only';
end;
$$;

drop trigger if exists generation_learning_policy_snapshot_append_only
  on content_factory.generation_learning_policy_snapshots;
create trigger generation_learning_policy_snapshot_append_only
before update or delete
  on content_factory.generation_learning_policy_snapshots
for each row execute function
  content_factory_private
    .guard_generation_learning_policy_snapshot_append_only();

revoke all on function
  content_factory_private
    .guard_generation_learning_policy_snapshot_append_only()
  from public, anon, authenticated, service_role;

-- Resolve one guard's exact post-application evidence.  Variant 1 is the
-- original canonical instruction.  Variant 2 is selected only after six
-- independent exact outcomes remain below the acceptance threshold.  If both
-- variants fail, the model cools down for 30 days; afterwards one variant-1
-- control is allowed.  A pending or failed control cannot silently create a
-- second paid control.
create or replace function
  content_factory_private.generation_quality_guard_effectiveness(
    p_organization_id uuid,
    p_product_id uuid,
    p_platform text,
    p_model text,
    p_guard_code text,
    p_evaluated_at timestamptz default now()
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  variant_1_count integer := 0;
  variant_1_average numeric;
  variant_2_count integer := 0;
  variant_2_average numeric;
  variant_2_last_decision_at timestamptz;
  control_job_id uuid;
  control_score numeric;
  control_decision text;
  control_decided_at timestamptz;
  selected_variant integer := 1;
  status_value text := 'collecting_variant_1';
  generation_allowed_value boolean := true;
  blocked_until_value timestamptz;
begin
  if p_organization_id is null
     or p_product_id is null
     or p_platform not in (
       'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
     )
     or p_model not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or not content_factory_private
       .valid_generation_quality_guard_codes(
         jsonb_build_array(p_guard_code)
       ) then
    raise exception using
      errcode = '22023',
      message = 'generation_quality_guard_effectiveness_invalid';
  end if;

  with raw_outcomes as (
    select
      lineage.generation_job_id,
      lineage.created_at as lineage_created_at,
      quality.decision,
      quality.decided_at,
      case
        when coalesce(
          snapshot.guard_variants ->> p_guard_code,
          '1'
        ) = '2' then 2
        else 1
      end as guard_variant,
      case p_guard_code
        when 'product_fidelity'
          then quality.result #>> '{scores,product_fidelity}'
        when 'technical_stability'
          then quality.result #>> '{scores,technical}'
        when 'audio_quality'
          then quality.result #>> '{scores,technical}'
        when 'speech_fidelity'
          then quality.result #>> '{scores,hook_clarity}'
        when 'hook_clarity'
          then quality.result #>> '{scores,hook_clarity}'
        when 'visual_quality'
          then quality.result #>> '{scores,visual_quality}'
        when 'trust'
          then quality.result #>> '{scores,trust}'
        when 'platform_fit'
          then quality.result #>> '{scores,platform_fit}'
      end as score_text
    from content_factory.generation_quality_guard_lineage lineage
    join content_factory.generation_jobs job
      on job.organization_id = lineage.organization_id
     and job.id = lineage.generation_job_id
     and job.product_id = lineage.product_id
     and job.mode = 'real'
     and job.provider = 'runway'
     and job.status = 'succeeded'
    join content_factory.media_objects media
      on media.organization_id = job.organization_id
     and media.id::text = job.output ->> 'output_media_id'
     and media.product_id = job.product_id
     and media.status = 'ready'
     and media.sha256 = job.output ->> 'sha256'
     and media.metadata ->> 'generation_job_id' = job.id::text
     and media.metadata ->> 'kind' in (
       'generated_video', 'generated_image'
     )
    left join content_factory.generation_learning_policy_snapshots snapshot
      on snapshot.organization_id = lineage.organization_id
     and snapshot.policy_hash = lineage.applied_policy_hash
     and snapshot.product_id = lineage.product_id
     and snapshot.platform = lineage.platform
     and snapshot.model = lineage.model
    join lateral (
      select
        decision.decision,
        decision.created_at as decided_at,
        review.result
      from content_factory.content_review_runs review
      join content_factory.content_review_decisions decision
        on decision.organization_id = review.organization_id
       and decision.review_id = review.id
       and decision.review_completion_hash = review.completion_hash
       and decision.media_sha256_snapshot =
         review.media_sha256_snapshot
       and decision.decided_by is distinct from job.requested_by
       and decision.decided_by is distinct from job.assigned_to
      where review.organization_id = job.organization_id
        and review.media_object_id = media.id
        and review.status = 'completed'
        and review.media_sha256_snapshot = media.sha256
        and jsonb_typeof(review.result -> 'scores') = 'object'
      order by decision.created_at desc, decision.id desc
      limit 1
    ) quality on true
    where lineage.organization_id = p_organization_id
      and lineage.product_id = p_product_id
      and lineage.platform = p_platform
      and lineage.model = p_model
      and lineage.source = 'performance_learning'
      and lineage.guard_codes ? p_guard_code
    order by lineage.created_at desc, lineage.generation_job_id
    limit 60
  ),
  valid_outcomes as (
    select
      generation_job_id,
      lineage_created_at,
      decision,
      decided_at,
      guard_variant,
      score_text::numeric as score
    from raw_outcomes
    where coalesce(score_text, '') ~ '^[0-9]{1,3}$'
      and score_text::integer between 0 and 100
  )
  select
    count(*) filter (where guard_variant = 1)::integer,
    avg(score) filter (where guard_variant = 1),
    count(*) filter (where guard_variant = 2)::integer,
    avg(score) filter (where guard_variant = 2),
    max(decided_at) filter (where guard_variant = 2)
  into
    variant_1_count,
    variant_1_average,
    variant_2_count,
    variant_2_average,
    variant_2_last_decision_at
  from valid_outcomes;

  variant_1_count := coalesce(variant_1_count, 0);
  variant_2_count := coalesce(variant_2_count, 0);

  if variant_2_count >= 6
     and variant_2_average < 78 then
    blocked_until_value :=
      variant_2_last_decision_at + interval '30 days';
    if blocked_until_value > p_evaluated_at then
      selected_variant := 2;
      status_value := 'cooldown';
      generation_allowed_value := false;
    else
      -- A policy snapshot identifies variant 1 without storing prompt text.
      select
        lineage.generation_job_id
      into control_job_id
      from content_factory.generation_quality_guard_lineage lineage
      join content_factory.generation_jobs job
        on job.organization_id = lineage.organization_id
       and job.id = lineage.generation_job_id
      left join
        content_factory.generation_learning_policy_snapshots snapshot
        on snapshot.organization_id = lineage.organization_id
       and snapshot.policy_hash = lineage.applied_policy_hash
       and snapshot.product_id = lineage.product_id
       and snapshot.platform = lineage.platform
       and snapshot.model = lineage.model
      where lineage.organization_id = p_organization_id
        and lineage.product_id = p_product_id
        and lineage.platform = p_platform
        and lineage.model = p_model
        and lineage.guard_codes ? p_guard_code
        and coalesce(
          snapshot.guard_variants ->> p_guard_code,
          '1'
        ) = '1'
        and lineage.created_at > variant_2_last_decision_at
        and job.status not in ('failed', 'cancelled')
      order by lineage.created_at desc, lineage.generation_job_id
      limit 1;

      if control_job_id is null then
        selected_variant := 1;
        status_value := 'control_revalidation';
        generation_allowed_value := true;
        blocked_until_value := null;
      else
        select
          control_outcome.score_text::numeric,
          control_outcome.decision,
          control_outcome.created_at
        into control_score, control_decision, control_decided_at
        from (
          select
            case p_guard_code
              when 'product_fidelity'
                then review.result #>> '{scores,product_fidelity}'
              when 'technical_stability'
                then review.result #>> '{scores,technical}'
              when 'audio_quality'
                then review.result #>> '{scores,technical}'
              when 'speech_fidelity'
                then review.result #>> '{scores,hook_clarity}'
              when 'hook_clarity'
                then review.result #>> '{scores,hook_clarity}'
              when 'visual_quality'
                then review.result #>> '{scores,visual_quality}'
              when 'trust'
                then review.result #>> '{scores,trust}'
              when 'platform_fit'
                then review.result #>> '{scores,platform_fit}'
            end as score_text,
            decision.decision,
            decision.created_at,
            decision.id
          from content_factory.generation_jobs job
          join content_factory.media_objects media
            on media.organization_id = job.organization_id
           and media.id::text = job.output ->> 'output_media_id'
           and media.status = 'ready'
           and media.sha256 = job.output ->> 'sha256'
          join content_factory.content_review_runs review
            on review.organization_id = media.organization_id
           and review.media_object_id = media.id
           and review.status = 'completed'
           and review.media_sha256_snapshot = media.sha256
          join content_factory.content_review_decisions decision
            on decision.organization_id = review.organization_id
           and decision.review_id = review.id
           and decision.review_completion_hash = review.completion_hash
           and decision.media_sha256_snapshot = media.sha256
           and decision.decided_by is distinct from job.requested_by
           and decision.decided_by is distinct from job.assigned_to
          where job.organization_id = p_organization_id
            and job.id = control_job_id
            and jsonb_typeof(review.result -> 'scores') = 'object'
        ) control_outcome
        where coalesce(control_outcome.score_text, '') ~ '^[0-9]{1,3}$'
          and control_outcome.score_text::integer between 0 and 100
        order by control_outcome.created_at desc, control_outcome.id desc
        limit 1;

        if control_score is null or control_decided_at is null then
          selected_variant := 1;
          status_value := 'control_pending_review';
          generation_allowed_value := false;
          blocked_until_value := null;
        elsif control_decision = 'approved' and control_score >= 78 then
          selected_variant := 1;
          status_value := 'control_passed';
          generation_allowed_value := true;
          blocked_until_value := null;
        else
          selected_variant := 1;
          status_value := 'cooldown';
          generation_allowed_value := false;
          blocked_until_value :=
            control_decided_at + interval '30 days';
          if blocked_until_value <= p_evaluated_at then
            status_value := 'control_revalidation';
            generation_allowed_value := true;
            blocked_until_value := null;
          end if;
        end if;
      end if;
    end if;
  elsif variant_1_count >= 6
        and variant_1_average < 78 then
    selected_variant := 2;
    status_value := case
      when variant_2_count >= 6 and variant_2_average >= 78
        then 'effective_variant_2'
      else 'collecting_variant_2'
    end;
  elsif variant_1_count >= 6 then
    selected_variant := 1;
    status_value := 'effective_variant_1';
  end if;

  return jsonb_strip_nulls(jsonb_build_object(
    'guard_code', p_guard_code,
    'selected_variant', selected_variant,
    'status', status_value,
    'generation_allowed', generation_allowed_value,
    'variant_1_evidence_count', variant_1_count,
    'variant_1_average_score',
      case
        when variant_1_average is null then null
        else round(variant_1_average, 2)
      end,
    'variant_2_evidence_count', variant_2_count,
    'variant_2_average_score',
      case
        when variant_2_average is null then null
        else round(variant_2_average, 2)
      end,
    'acceptance_threshold', 78,
    'minimum_observations_per_variant', 6,
    'blocked_until', blocked_until_value
  ));
exception when invalid_text_representation or numeric_value_out_of_range then
  raise exception using
    errcode = '55000',
    message = 'generation_quality_guard_effectiveness_evidence_invalid';
end;
$$;

revoke all on function
  content_factory_private.generation_quality_guard_effectiveness(
    uuid, uuid, text, text, text, timestamptz
  )
  from public, anon, authenticated, service_role;

-- Wrap the complete v6 policy.  The policy changes only bounded structural
-- variants and the generation_allowed gate; every identity, rights, training,
-- budget, claim and hard-rejection rule remains authoritative underneath.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_policy_rejection_v6;

revoke all on function
  content_factory_private
    .creator_generation_learning_policy_rejection_v6(jsonb)
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
  media_id_value uuid;
  product_id_value uuid;
  platform_value text;
  model_value text;
  requested_model_value text;
  guard_codes_value jsonb;
  guard_variants_value jsonb := '{}'::jsonb;
  effectiveness_value jsonb := '[]'::jsonb;
  guard_code text;
  guard_effectiveness jsonb;
  generation_allowed_value boolean := true;
  effectiveness_status_value text := 'clear';
  policy_without_hash jsonb;
  policy_hash_value text;
begin
  base_policy := content_factory_private
    .creator_generation_learning_policy_rejection_v6(p_payload);
  if base_policy -> 'applied' is distinct from 'true'::jsonb
     or base_policy -> 'generation_allowed' = 'false'::jsonb then
    return base_policy;
  end if;

  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  media_id_value :=
    content_factory_private.require_uuid(p_payload, 'media_id');
  platform_value :=
    lower(btrim(coalesce(p_payload ->> 'platform', '')));
  model_value :=
    lower(btrim(coalesce(p_payload ->> 'model', '')));
  requested_model_value := base_policy ->> 'requested_model';
  guard_codes_value := coalesce(
    base_policy -> 'quality_guard_codes',
    '[]'::jsonb
  );
  if not content_factory_private
       .valid_generation_quality_guard_codes(guard_codes_value) then
    raise exception using
      errcode = '55000',
      message = 'generation_quality_guard_policy_invalid';
  end if;

  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id_value;
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;

  for guard_code in
    select item.value
    from jsonb_array_elements_text(guard_codes_value) item(value)
  loop
    guard_effectiveness :=
      content_factory_private.generation_quality_guard_effectiveness(
        organization_id,
        product_id_value,
        platform_value,
        model_value,
        guard_code,
        now()
      );
    guard_variants_value := jsonb_set(
      guard_variants_value,
      array[guard_code],
      guard_effectiveness -> 'selected_variant',
      true
    );
    effectiveness_value :=
      effectiveness_value || jsonb_build_array(guard_effectiveness);
    if guard_effectiveness -> 'generation_allowed'
         is distinct from 'true'::jsonb then
      generation_allowed_value := false;
      if guard_effectiveness ->> 'status' =
         'control_pending_review' then
        effectiveness_status_value := 'control_pending_review';
      elsif effectiveness_status_value <>
            'control_pending_review' then
        effectiveness_status_value := 'cooldown';
      end if;
    elsif guard_effectiveness ->> 'status' =
          'control_revalidation'
          and effectiveness_status_value = 'clear' then
      effectiveness_status_value := 'control_revalidation';
    elsif guard_effectiveness ->> 'selected_variant' = '2'
          and effectiveness_status_value = 'clear' then
      effectiveness_status_value := 'variant_2';
    end if;
  end loop;

  if jsonb_array_length(guard_codes_value) = 0 then
    effectiveness_status_value := 'not_applicable';
  end if;
  if not content_factory_private
       .valid_generation_quality_guard_variants(
         guard_codes_value,
         guard_variants_value
       ) then
    raise exception using
      errcode = '55000',
      message = 'generation_quality_guard_variants_invalid';
  end if;

  policy_without_hash :=
    (base_policy - 'policy_hash' - 'requested_model')
    || jsonb_build_object(
      'version', 'generation-learning-v7',
      'generation_allowed', generation_allowed_value,
      'quality_guard_variants', guard_variants_value,
      'quality_guard_effectiveness', effectiveness_value,
      'quality_guard_effectiveness_status',
        effectiveness_status_value,
      'reason_codes',
        coalesce(base_policy -> 'reason_codes', '[]'::jsonb)
        || case effectiveness_status_value
          when 'variant_2'
            then '["quality_guard_variant_escalated"]'::jsonb
          when 'cooldown'
            then '["quality_guard_variants_exhausted"]'::jsonb
          when 'control_pending_review'
            then '["quality_guard_control_review_pending"]'::jsonb
          when 'control_revalidation'
            then '["quality_guard_control_revalidation"]'::jsonb
          else '[]'::jsonb
        end,
      'safety',
        coalesce(base_policy -> 'safety', '{}'::jsonb)
        || jsonb_build_object(
          'exact_applied_guard_lineage_only', true,
          'latest_exact_independent_decision_only', true,
          'numeric_score_dimensions_only', true,
          'two_guard_variants_bounded', true,
          'failed_model_cooldown_days', 30,
          'single_control_requires_independent_review', true,
          'free_form_review_copy_never_learned', true,
          'provider_spend_requires_separate_confirmation', true
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

-- Canonical variant-aware QA fragments are shared by every database prompt
-- binding.  Variant 2 is intentionally stricter but remains claim-free.
create or replace function
  content_factory_private.generation_quality_guard_requirement(
    p_guard_code text,
    p_guard_variant integer,
    p_model text
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  photo boolean := p_model = 'seedream5_lite';
begin
  if p_guard_variant not in (1, 2)
     or p_model not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or (
       p_guard_code in ('audio_quality', 'speech_fidelity')
       and p_model <> 'seedance2_fast'
     ) then
    return null;
  end if;
  if p_guard_variant = 2 then
    return case
      when photo and p_guard_code = 'product_fidelity'
        then 'QA+: один товар строго по исходнику; не изменять ни одну букву, край, цвет или пропорцию упаковки.'
      when photo and p_guard_code = 'technical_stability'
        then 'QA+: нейтральный ровный свет; весь товар резкий, без бликов, шума и размытия.'
      when photo and p_guard_code = 'hook_clarity'
        then 'QA+: товар занимает главный визуальный акцент и считывается без второго объекта.'
      when photo and p_guard_code = 'visual_quality'
        then 'QA+: цельный чистый силуэт; никаких лишних деталей, дублей, швов и AI-артефактов.'
      when photo and p_guard_code = 'trust'
        then 'QA+: реалистичные материалы, масштаб и тени как в предметной съёмке.'
      when photo and p_guard_code = 'platform_fit'
        then 'QA+: квадрат 1:1; упаковка целиком внутри безопасных полей.'
      when not photo and p_guard_code = 'product_fidelity'
        then 'QA+: один точный товар по исходнику; упаковка, этикетка, текст, цвет и пропорции неизменны в каждом кадре.'
      when not photo and p_guard_code = 'technical_stability'
        then 'QA+: один непрерывный стабильный проход; без скачков, чёрных кадров, морфинга и мерцания.'
      when p_guard_code = 'audio_quality'
        then 'QA+: непрерывная разборчивая дорожка; без тишины, клиппинга, шума и рассинхронизации.'
      when p_guard_code = 'speech_fidelity'
        then 'QA+: произнести только точную реплику дословно; без пропусков, замен, повторов и новых слов.'
      when not photo and p_guard_code = 'hook_clarity'
        then 'QA+: точный товар — главный объект первого кадра; одно действие начинается в первые 2 секунды.'
      when not photo and p_guard_code = 'visual_quality'
        then 'QA+: постоянные руки, лицо, упаковка и фактуры; без деформаций, дублей, швов и мерцания.'
      when not photo and p_guard_code = 'trust'
        then 'QA+: естественный свет, материалы и движение; без гиперболы, постановочного эффекта и новых обещаний.'
      when not photo and p_guard_code = 'platform_fit'
        then 'QA+: вертикальный мастер 9:16; товар и лицо целиком остаются в безопасных полях.'
    end;
  end if;
  return case
    when photo and p_guard_code = 'product_fidelity'
      then 'QA: точная геометрия, этикетка, текст, цвет и пропорции.'
    when photo and p_guard_code = 'technical_stability'
      then 'QA: резкий товар, ровный свет, без пересвета и размытия.'
    when photo and p_guard_code = 'hook_clarity'
      then 'QA: товар считывается первым.'
    when photo and p_guard_code = 'visual_quality'
      then 'QA: чистые края без дублей, деформаций и AI-артефактов.'
    when photo and p_guard_code = 'trust'
      then 'QA: естественные материалы, свет и масштаб.'
    when photo and p_guard_code = 'platform_fit'
      then 'QA: мастер 1:1, безопасные поля.'
    when not photo and p_guard_code = 'product_fidelity'
      then 'QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.'
    when not photo and p_guard_code = 'technical_stability'
      then 'QA: стабильный проход без чёрных кадров, скачков и мерцания.'
    when p_guard_code = 'audio_quality'
      then 'QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.'
    when p_guard_code = 'speech_fidelity'
      then 'QA: реплика произносится дословно, без пропусков, замен и новых слов.'
    when not photo and p_guard_code = 'hook_clarity'
      then 'QA: точный товар и одно действие видны в первые 2 секунды.'
    when not photo and p_guard_code = 'visual_quality'
      then 'QA: руки, лицо и фактуры без деформаций, дублей и мерцания.'
    when not photo and p_guard_code = 'trust'
      then 'QA: естественная подача без гиперболы и новых обещаний.'
    when not photo and p_guard_code = 'platform_fit'
      then 'QA: мастер 9:16; товар и лицо в безопасных полях.'
  end;
end;
$$;

revoke all on function
  content_factory_private
    .generation_quality_guard_requirement(text, integer, text)
  from public, anon, authenticated, service_role;

-- Replace the existing helper with the same angle/hook contract plus the
-- server-selected guard variant.  Old policies without the new object remain
-- variant 1 for backward-compatible idempotent requests.
create or replace function
  content_factory_private.generation_learning_prompt_requirements(
    p_policy jsonb,
    p_model text
  )
returns text[]
language plpgsql
immutable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  requirements text[] := array[]::text[];
  angle_value text;
  hook_value text;
  guard_value text;
  guard_variant integer;
  requirement_value text;
  hook_patterns jsonb;
  guard_codes jsonb;
  guard_variants jsonb;
  photo boolean;
begin
  if jsonb_typeof(p_policy) <> 'object'
     or p_policy -> 'applied' is distinct from 'true'::jsonb
     or p_model not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     ) then
    return null;
  end if;
  photo := p_model = 'seedream5_lite';
  angle_value := p_policy ->> 'preferred_angle';
  requirement_value := case
    when photo and angle_value = 'product_focus'
      then 'Обученный ракурс: товар целиком, строгий фокус.'
    when photo and angle_value = 'trust_builder'
      then 'Обученный ракурс: естественная предметная подача.'
    when photo and angle_value = 'demonstration'
      then 'Обученный ракурс: одна видимая деталь товара.'
    when photo and angle_value = 'comparison'
      then 'Обученный ракурс: ясный масштаб без второго товара.'
    when photo and angle_value = 'objection_handling'
      then 'Обученный ракурс: упаковка и проверяемые детали.'
    when photo and angle_value = 'curiosity_gap'
      then 'Обученный ракурс: выразительная деталь при видимом целом товаре.'
    when not photo and angle_value = 'product_focus'
      then 'Обученное направление: товар главный во всех кадрах.'
    when not photo and angle_value = 'trust_builder'
      then 'Обученное направление: естественная подача без преувеличений.'
    when not photo and angle_value = 'demonstration'
      then 'Обученное направление: одно видимое действие с товаром.'
    when not photo and angle_value = 'comparison'
      then 'Обученное направление: сравнение без второго товара и обещаний.'
    when not photo and angle_value = 'objection_handling'
      then 'Обученное направление: одна проверяемая деталь товара.'
    when not photo and angle_value = 'curiosity_gap'
      then 'Обученное направление: заметная деталь, затем товар целиком.'
  end;
  if requirement_value is null then
    return null;
  end if;
  requirements := array_append(requirements, requirement_value);

  hook_patterns := coalesce(
    p_policy -> 'preferred_hook_patterns',
    '[]'::jsonb
  );
  if jsonb_typeof(hook_patterns) <> 'array'
     or jsonb_array_length(hook_patterns) > 4
     or exists (
       select 1
       from jsonb_array_elements(hook_patterns) item(value)
       where jsonb_typeof(item.value) <> 'string'
     ) then
    return null;
  end if;
  if not photo and jsonb_array_length(hook_patterns) > 0 then
    hook_value := hook_patterns #>> '{0}';
    requirement_value := case hook_value
      when 'question_led'
        then 'Структурный hook: визуальный вопрос сразу раскрывается точным товаром.'
      when 'why_explanation'
        then 'Структурный hook: видимая причина рассмотреть товар, без утверждений.'
      when 'before_buying'
        then 'Структурный hook: спокойная проверка товара перед выбором.'
      when 'comparison'
        then 'Структурный hook: сравнение без второго товара, цифр и обещаний.'
      when 'demonstration'
        then 'Структурный hook: одно простое действие с товаром.'
      when 'first_person'
        then 'Структурный hook: от первого лица; товар целиком и в фокусе.'
      when 'numbered'
        then 'Структурный hook: один понятный шаг без цифр и надписей.'
      when 'concise'
        then 'Структурный hook: простой первый кадр сразу показывает товар.'
    end;
    if requirement_value is null then
      return null;
    end if;
    requirements := array_append(requirements, requirement_value);
  end if;

  guard_codes := coalesce(p_policy -> 'quality_guard_codes', '[]'::jsonb);
  guard_variants := coalesce(
    p_policy -> 'quality_guard_variants',
    (
      select coalesce(
        jsonb_object_agg(item.value, 1),
        '{}'::jsonb
      )
      from jsonb_array_elements_text(guard_codes) item(value)
    )
  );
  if not content_factory_private
       .valid_generation_quality_guard_variants(
         guard_codes,
         guard_variants
       ) then
    return null;
  end if;
  for guard_value in
    select item.value
    from jsonb_array_elements_text(guard_codes) item(value)
  loop
    guard_variant := (guard_variants ->> guard_value)::integer;
    requirement_value :=
      content_factory_private.generation_quality_guard_requirement(
        guard_value,
        guard_variant,
        p_model
      );
    if requirement_value is null then
      return null;
    end if;
    requirements := array_append(requirements, requirement_value);
  end loop;
  return requirements;
exception when others then
  return null;
end;
$$;

revoke all on function
  content_factory_private.generation_learning_prompt_requirements(jsonb, text)
  from public, anon, authenticated, service_role;

-- Persist the exact structural policy before the existing v8 job/lineage
-- wrapper runs.  A conflict rolls back the whole paid transaction before Edge
-- can contact Runway.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_policy_snapshot_v9;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_policy_snapshot_v9(jsonb)
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
  user_id uuid;
  organization_id uuid;
  product_id_value uuid;
  learning_context jsonb;
  server_policy jsonb;
  policy_hash_value text;
  guard_codes_value jsonb;
  guard_variants_value jsonb;
  existing_snapshot
    content_factory.generation_learning_policy_snapshots%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  learning_context := p_payload -> 'learning_context';
  if learning_context is null
     or jsonb_typeof(learning_context) <> 'object'
     or learning_context ->> 'source' <> 'performance_learning' then
    return content_factory_private
      .creator_start_real_generation_pre_policy_snapshot_v9(p_payload);
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  select media.product_id into product_id_value
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id::text = p_payload #>> '{media_ids,0}';
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_learning_policy_media_invalid';
  end if;

  server_policy := public.creator_generation_learning_policy(
    jsonb_build_object(
      'organization_id', organization_id,
      'media_id', p_payload #>> '{media_ids,0}',
      'platform', p_payload ->> 'platform',
      'model', p_payload ->> 'model'
    )
  );
  policy_hash_value := server_policy ->> 'policy_hash';
  guard_codes_value := coalesce(
    server_policy -> 'quality_guard_codes',
    '[]'::jsonb
  );
  guard_variants_value := coalesce(
    server_policy -> 'quality_guard_variants',
    '{}'::jsonb
  );
  if server_policy -> 'applied' is distinct from 'true'::jsonb
     or server_policy -> 'generation_allowed' = 'false'::jsonb
     or policy_hash_value
          is distinct from learning_context ->> 'applied_policy_hash'
     or not content_factory_private
       .valid_generation_quality_guard_variants(
         guard_codes_value,
         guard_variants_value
       ) then
    raise exception using
      errcode = '55000',
      message = 'generation_learning_policy_snapshot_stale';
  end if;

  insert into content_factory.generation_learning_policy_snapshots (
    organization_id,
    product_id,
    platform,
    model,
    policy_hash,
    guard_codes,
    guard_variants,
    created_by
  ) values (
    organization_id,
    product_id_value,
    lower(btrim(p_payload ->> 'platform')),
    lower(btrim(p_payload ->> 'model')),
    policy_hash_value,
    guard_codes_value,
    guard_variants_value,
    user_id
  )
  on conflict (
    organization_id,
    product_id,
    platform,
    model,
    policy_hash
  ) do nothing;

  select snapshot.* into existing_snapshot
  from content_factory.generation_learning_policy_snapshots snapshot
  where snapshot.organization_id = organization_id
    and snapshot.product_id = product_id_value
    and snapshot.platform = lower(btrim(p_payload ->> 'platform'))
    and snapshot.model = lower(btrim(p_payload ->> 'model'))
    and snapshot.policy_hash = policy_hash_value;
  if existing_snapshot.id is null
     or existing_snapshot.product_id is distinct from product_id_value
     or existing_snapshot.platform
          is distinct from lower(btrim(p_payload ->> 'platform'))
     or existing_snapshot.model
          is distinct from lower(btrim(p_payload ->> 'model'))
     or existing_snapshot.guard_codes is distinct from guard_codes_value
     or existing_snapshot.guard_variants
          is distinct from guard_variants_value then
    raise exception using
      errcode = '23505',
      message = 'generation_learning_policy_snapshot_conflict';
  end if;

  return content_factory_private
    .creator_start_real_generation_pre_policy_snapshot_v9(p_payload);
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

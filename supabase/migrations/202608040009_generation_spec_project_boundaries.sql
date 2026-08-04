begin;

-- Generation-spec documents were introduced before projects.  The v48 guard
-- bound their media, but a spec can also consume research, repair and learned
-- performance evidence.  Bind every immutable input before any public RPC can
-- read, mutate, approve or claim that spec.
create or replace function
  content_factory_private.require_generation_project_provenance_v49(
    p_organization_id uuid,
    p_project_id uuid,
    p_product_id uuid,
    p_research_provenance jsonb,
    p_repair_provenance jsonb,
    p_performance_policy_provenance jsonb,
    p_final_policy jsonb
  )
returns void
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  research_run_id_value uuid;
  research_draft_id_value uuid;
  repair_review_id_value uuid;
  repair_job_id_value uuid;
  source_job_ids_value jsonb;
  bounded_exploration_value boolean := false;
begin
  if p_research_provenance is not null
     and jsonb_typeof(p_research_provenance) = 'object'
     and coalesce(p_research_provenance ->> 'research_id', '') ~
           '^[0-9a-fA-F-]{36}$'
     and coalesce(
       p_research_provenance ->> 'creative_brief_draft_id', ''
     ) ~ '^[0-9a-fA-F-]{36}$' then
    begin
      research_run_id_value := (
        p_research_provenance ->> 'research_id'
      )::uuid;
      research_draft_id_value := (
        p_research_provenance ->> 'creative_brief_draft_id'
      )::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end;

    perform 1
    from content_factory.product_research_runs run
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = run.organization_id
     and draft.run_id = run.id
     and draft.product_id = run.product_id
     and draft.project_id = p_project_id
    where run.organization_id = p_organization_id
      and run.id = research_run_id_value
      and run.product_id = p_product_id
      and run.project_id = p_project_id
      and draft.id = research_draft_id_value
    for share of run, draft;
    if not found then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;

    -- Market-category identity is intentionally organization/product scoped,
    -- so a stable human-confirmed category can be reused by later projects.
    -- It is not generation evidence: the category rule compiler and receipt
    -- read maturity, competitor coverage, trends and scenario structure only
    -- from the exact project-local run/draft validated above.  Requiring the
    -- identity binding's historical source project here would create a dead
    -- end for the same product and category in every later project.
  end if;

  if p_repair_provenance is not null
     and jsonb_typeof(p_repair_provenance) = 'object'
     and coalesce(p_repair_provenance ->> 'source_review_id', '') ~
           '^[0-9a-fA-F-]{36}$'
     and coalesce(
       p_repair_provenance ->> 'source_generation_job_id', ''
     ) ~ '^[0-9a-fA-F-]{36}$' then
    begin
      repair_review_id_value := (
        p_repair_provenance ->> 'source_review_id'
      )::uuid;
      repair_job_id_value := (
        p_repair_provenance ->> 'source_generation_job_id'
      )::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end;

    perform 1
    from content_factory.generation_jobs job
    join content_factory.content_review_runs review
      on review.organization_id = job.organization_id
     and review.id = repair_review_id_value
     and review.media_object_id::text = job.output ->> 'output_media_id'
     and review.project_id = p_project_id
    where job.organization_id = p_organization_id
      and job.id = repair_job_id_value
      and job.product_id = p_product_id
      and job.project_id = p_project_id
    for share of job, review;
    if not found then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;

  -- The authoritative grounded learning policy retains the exact jobs that
  -- produced its structural choice.  Quality-guard jobs are a second exact
  -- source list.  Raw review copy never enters this receipt.
  if p_performance_policy_provenance is not null
     and p_final_policy is not null then
    if jsonb_typeof(p_final_policy #> '{learning_policy}')
         is distinct from 'object'
       or jsonb_typeof(
         p_final_policy #> '{learning_policy,source_job_ids}'
       ) is distinct from 'array'
       or (
         p_final_policy #> '{learning_policy,quality_guard_source_job_ids}'
           is not null
         and jsonb_typeof(
           p_final_policy #>
             '{learning_policy,quality_guard_source_job_ids}'
         ) is distinct from 'array'
       ) then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;

    source_job_ids_value :=
      (p_final_policy #> '{learning_policy,source_job_ids}')
      || coalesce(
        p_final_policy #>
          '{learning_policy,quality_guard_source_job_ids}',
        '[]'::jsonb
      );
    bounded_exploration_value := coalesce(
      p_final_policy #>> '{learning_policy,project_id}' =
        p_project_id::text
      and p_final_policy #> '{learning_policy,applied}' = 'true'::jsonb
      and p_final_policy #> '{learning_policy,generation_allowed}' =
        'true'::jsonb
      and p_final_policy #>> '{learning_policy,confidence}' = 'medium'
      and p_final_policy #>> '{learning_policy,selection_mode}' =
        'bounded_exploration'
      and p_final_policy #> '{learning_policy,source_job_ids}' = '[]'::jsonb
      and coalesce(
        p_final_policy #>
          '{learning_policy,quality_guard_source_job_ids}',
        '[]'::jsonb
      ) = '[]'::jsonb
      and p_final_policy #>> '{learning_policy,preferred_angle}' =
        p_final_policy #>> '{learning_policy,selected_angle}'
      and (
        (
          p_final_policy #>> '{learning_policy,preferred_angle}' =
            'product_focus'
          and p_final_policy #>
            '{learning_policy,preferred_hook_patterns}' = '[]'::jsonb
          and p_final_policy #>
            '{learning_policy,selected_hook_patterns}' = '[]'::jsonb
        )
        or (
          p_final_policy #>> '{learning_policy,preferred_angle}' =
            'demonstration'
          and p_final_policy #>
            '{learning_policy,preferred_hook_patterns}' =
              '["demonstration"]'::jsonb
          and p_final_policy #>
            '{learning_policy,selected_hook_patterns}' =
              '["demonstration"]'::jsonb
        )
        or (
          p_final_policy #>> '{learning_policy,preferred_angle}' =
            'trust_builder'
          and p_final_policy #>
            '{learning_policy,preferred_hook_patterns}' =
              '["first_person"]'::jsonb
          and p_final_policy #>
            '{learning_policy,selected_hook_patterns}' =
              '["first_person"]'::jsonb
        )
        or (
          p_final_policy #>> '{learning_policy,preferred_angle}' =
            'objection_handling'
          and p_final_policy #>
            '{learning_policy,preferred_hook_patterns}' =
              '["before_buying"]'::jsonb
          and p_final_policy #>
            '{learning_policy,selected_hook_patterns}' =
              '["before_buying"]'::jsonb
        )
      )
      and jsonb_typeof(
        p_final_policy #> '{learning_policy,reason_codes}'
      ) = 'array'
      and p_final_policy #> '{learning_policy,reason_codes}'
        ? 'bounded_exploration_required'
      and p_final_policy #>
        '{learning_policy,exploration,candidate_count}' = '2'::jsonb
      and p_final_policy #>>
        '{learning_policy,exploration,balancing_scope}' =
          'product_platform_model'
      and jsonb_typeof(
        p_final_policy #>
          '{learning_policy,exploration,selected_prior_use_count}'
      ) = 'number'
      and p_final_policy #>
        '{learning_policy,exploration,selected_prior_use_count}' >=
          '0'::jsonb
      and (
        (
          p_final_policy #>> '{learning_policy,rejection_guard,status}' =
            'clear'
          and p_final_policy #>> '{learning_policy,preferred_angle}' in (
            'product_focus', 'demonstration'
          )
        )
        or (
          p_final_policy #>> '{learning_policy,rejection_guard,status}' =
            'replaced'
          and p_final_policy #> '{learning_policy,reason_codes}'
            ? 'hard_rejected_structure_replaced'
          and p_final_policy #>>
            '{learning_policy,rejection_guard,scope}' =
              'product_platform_model_exact_structure'
          and jsonb_typeof(
            p_final_policy #>
              '{learning_policy,rejection_guard,exact_structure_rejection_count}'
          ) = 'number'
          and p_final_policy #>
            '{learning_policy,rejection_guard,exact_structure_rejection_count}' >
              '0'::jsonb
          and p_final_policy #>
            '{learning_policy,rejection_guard,exact_structure_approval_count}' =
              '0'::jsonb
          and jsonb_typeof(
            p_final_policy #>
              '{learning_policy,rejection_guard,replacement_prior_use_count}'
          ) = 'number'
          and p_final_policy #>
            '{learning_policy,rejection_guard,replacement_prior_use_count}' >=
              '0'::jsonb
          and p_final_policy #>
            '{learning_policy,safety,latest_exact_independent_decision_only}' =
              'true'::jsonb
          and p_final_policy #>
            '{learning_policy,safety,hard_rejected_structure_not_repeated}' =
              'true'::jsonb
          and p_final_policy #>
            '{learning_policy,safety,safe_recovery_structures_are_server_bounded}' =
              'true'::jsonb
          and p_final_policy #>
            '{learning_policy,safety,paid_start_fails_closed_when_structures_exhausted}' =
              'true'::jsonb
        )
      )
      and p_final_policy #>
        '{learning_policy,safety,selection_is_structural_only}' =
          'true'::jsonb
      and p_final_policy #>
        '{learning_policy,safety,exploration_angles_are_server_bounded}' =
          'true'::jsonb
      and p_final_policy #>
        '{learning_policy,safety,provider_spend_requires_separate_confirmation}' =
          'true'::jsonb,
      false
    );
    if (
         p_final_policy #>> '{learning_policy,project_id}' is not null
         and p_final_policy #>> '{learning_policy,project_id}' <>
           p_project_id::text
       )
       or (
         jsonb_array_length(source_job_ids_value) = 0
         and not bounded_exploration_value
       )
       or exists (
         select 1
         from jsonb_array_elements_text(source_job_ids_value) source(value)
         where source.value !~
           '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
       ) then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;

    if exists (
      select 1
      from jsonb_array_elements_text(source_job_ids_value) source(value)
      left join content_factory.generation_jobs job
        on job.organization_id = p_organization_id
       and job.id = source.value::uuid
       and job.product_id = p_product_id
       and job.project_id = p_project_id
      where job.id is null
         or not exists (
           select 1
           from content_factory.content_review_runs review
           where review.organization_id = p_organization_id
             and review.media_object_id::text =
               job.output ->> 'output_media_id'
             and review.project_id = p_project_id
         )
    ) then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;

    -- Older policy layers aggregate all creative signals for a product before
    -- returning the exact selected jobs.  Until those layers are natively
    -- project-keyed, a product with any foreign/unscoped signal is ambiguous
    -- and must not be consumed by a paid project generation.
    if exists (
      select 1
      from content_factory.generation_creative_signals signal
      left join content_factory.generation_jobs job
        on job.organization_id = signal.organization_id
       and job.id = signal.generation_job_id
       and job.product_id = signal.product_id
      where signal.organization_id = p_organization_id
        and signal.product_id = p_product_id
        and (
          job.id is null
          or job.project_id is distinct from p_project_id
          or exists (
            select 1
            from content_factory.content_review_runs review
            where review.organization_id = job.organization_id
              and review.media_object_id::text =
                job.output ->> 'output_media_id'
              and review.project_id is distinct from p_project_id
          )
        )
    ) then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;
end;
$$;

revoke all on function
  content_factory_private.require_generation_project_provenance_v49(
    uuid, uuid, uuid, jsonb, jsonb, jsonb, jsonb
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.require_generation_request_project_v49(
    p_organization_id uuid,
    p_project_id uuid,
    p_exact_scope jsonb,
    p_research_provenance jsonb,
    p_repair_provenance jsonb,
    p_performance_policy_provenance jsonb
  )
returns uuid
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  primary_media_id_value uuid;
  media_ids_value uuid[];
  product_id_value uuid;
  scoped_media_count integer;
begin
  perform content_factory_private.require_workspace_project(
    p_organization_id, p_project_id
  );
  if jsonb_typeof(p_exact_scope) <> 'object'
     or jsonb_typeof(p_exact_scope -> 'media_ids') <> 'array'
     or jsonb_array_length(p_exact_scope -> 'media_ids') not between 1 and 5
     or p_exact_scope ->> 'primary_media_id' is null then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end if;
  begin
    primary_media_id_value := (p_exact_scope ->> 'primary_media_id')::uuid;
    select array_agg(item.value::uuid order by item.ordinality)
      into media_ids_value
    from jsonb_array_elements_text(p_exact_scope -> 'media_ids')
      with ordinality item(value, ordinality);
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023', message = 'generation_spec_exact_scope_invalid';
  end;

  select media.product_id into product_id_value
  from content_factory.media_objects media
  join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
   and product.status = 'active'
  where media.organization_id = p_organization_id
    and media.id = primary_media_id_value
    and media.project_id = p_project_id
  for share of media, product;
  if product_id_value is null then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  select count(*)::integer into scoped_media_count
  from unnest(media_ids_value) selected(media_id)
  join content_factory.media_objects media
    on media.organization_id = p_organization_id
   and media.id = selected.media_id
   and media.product_id = product_id_value
   and media.project_id = p_project_id;
  if scoped_media_count <> cardinality(media_ids_value) then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  perform content_factory_private.require_generation_project_provenance_v49(
    p_organization_id,
    p_project_id,
    product_id_value,
    nullif(p_research_provenance, 'null'::jsonb),
    nullif(p_repair_provenance, 'null'::jsonb),
    nullif(p_performance_policy_provenance, 'null'::jsonb),
    null
  );
  return product_id_value;
end;
$$;

revoke all on function
  content_factory_private.require_generation_request_project_v49(
    uuid, uuid, jsonb, jsonb, jsonb, jsonb
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.require_generation_spec_project_v49(
    p_organization_id uuid,
    p_project_id uuid,
    p_spec_id uuid,
    p_spec_version integer,
    p_spec_hash text,
    p_expected_product_id uuid default null
  )
returns uuid
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  product_id_value uuid;
  spec_row content_factory.generation_spec_versions%rowtype;
begin
  product_id_value :=
    content_factory_private.require_generation_spec_project_v48(
      p_organization_id,
      p_project_id,
      p_spec_id,
      p_spec_version,
      p_spec_hash,
      p_expected_product_id
    );

  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = p_organization_id
    and version.spec_id = p_spec_id
    and version.spec_version = p_spec_version
    and version.spec_hash = p_spec_hash
  for share;
  if spec_row.version_id is null then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_project_scope_mismatch';
  end if;

  perform content_factory_private.require_generation_project_provenance_v49(
    p_organization_id,
    p_project_id,
    product_id_value,
    spec_row.research_provenance,
    spec_row.repair_provenance,
    spec_row.performance_policy_provenance,
    spec_row.final_policy
  );
  return product_id_value;
end;
$$;

revoke all on function
  content_factory_private.require_generation_spec_project_v49(
    uuid, uuid, uuid, integer, text, uuid
  ) from public, anon, authenticated, service_role;

-- Preserve the three installed generation-spec commands.  Their response
-- documents remain byte-for-byte unchanged; project_id is a boundary-only
-- request field and is stripped before idempotency hashing/delegation.
do $preserve_generation_spec_project_boundaries_v49$
begin
  if to_regprocedure(
    'content_factory_private.creator_prepare_generation_spec_pre_project_v49(jsonb)'
  ) is null then
    alter function public.creator_prepare_generation_spec(jsonb)
      rename to creator_prepare_generation_spec_pre_project_v49;
    alter function
      public.creator_prepare_generation_spec_pre_project_v49(jsonb)
      set schema content_factory_private;
  end if;
  if to_regprocedure(
    'content_factory_private.creator_generation_spec_status_pre_project_v49(jsonb)'
  ) is null then
    alter function public.creator_generation_spec_status(jsonb)
      rename to creator_generation_spec_status_pre_project_v49;
    alter function
      public.creator_generation_spec_status_pre_project_v49(jsonb)
      set schema content_factory_private;
  end if;
  if to_regprocedure(
    'content_factory_private.creator_control_generation_spec_pre_project_v49(jsonb)'
  ) is null then
    alter function public.creator_control_generation_spec(jsonb)
      rename to creator_control_generation_spec_pre_project_v49;
    alter function
      public.creator_control_generation_spec_pre_project_v49(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_generation_spec_project_boundaries_v49$;

revoke all on function
  content_factory_private.creator_prepare_generation_spec_pre_project_v49(
    jsonb
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.creator_generation_spec_status_pre_project_v49(
    jsonb
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.creator_control_generation_spec_pre_project_v49(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_prepare_generation_spec(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  project_id_value uuid;
  previous_project_setting text;
  previous_project_id uuid;
  result_value jsonb;
  result_spec_id uuid;
  result_spec_version integer;
  result_spec_hash text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023', message = 'project_id_required';
  end if;
  if length(p_payload::text) > 131072
     or p_payload - array[
       'organization_id', 'project_id', 'idempotency_key', 'exact_scope',
       'editable_intent', 'proposed_prompt', 'learning_context',
       'repair_context', 'research_provenance',
       'performance_policy_provenance', 'repair_provenance',
       'outcome_selection_id', 'confirmation', 'reason'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'project_id', 'idempotency_key', 'exact_scope',
       'editable_intent', 'proposed_prompt', 'learning_context',
       'repair_context', 'research_provenance',
       'performance_policy_provenance', 'repair_provenance',
       'confirmation', 'reason'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_prepare_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  perform content_factory_private.require_generation_request_project_v49(
    organization_id_value,
    project_id_value,
    p_payload -> 'exact_scope',
    p_payload -> 'research_provenance',
    p_payload -> 'repair_provenance',
    p_payload -> 'performance_policy_provenance'
  );

  previous_project_setting := current_setting(
    'contentengine.project_id', true
  );
  if nullif(previous_project_setting, '') is not null then
    begin
      previous_project_id := previous_project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end;
    if previous_project_id <> project_id_value then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;
  perform set_config(
    'contentengine.project_id', project_id_value::text, true
  );
  begin
    result_value := content_factory_private
      .creator_prepare_generation_spec_pre_project_v49(
        p_payload - 'project_id'
      );
    result_spec_id := (
      result_value #>> '{generation_spec,spec_id}'
    )::uuid;
    result_spec_version := (
      result_value #>> '{generation_spec,spec_version}'
    )::integer;
    result_spec_hash := result_value #>> '{generation_spec,spec_hash}';
    perform content_factory_private.require_generation_spec_project_v49(
      organization_id_value, project_id_value,
      result_spec_id, result_spec_version, result_spec_hash, null
    );
    if not content_factory_private
      .generation_spec_research_category_rule_current(
        organization_id_value, result_spec_id,
        result_spec_version, result_spec_hash
      ) then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_research_category_rule_stale';
    end if;
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''), true
  );
  return result_value;
end;
$$;

create or replace function public.creator_generation_spec_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  previous_project_setting text;
  previous_project_id uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023', message = 'project_id_required';
  end if;
  if p_payload - array[
       'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] then
    raise exception using
      errcode = '22023', message = 'generation_spec_status_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, false,
    array['owner', 'admin', 'producer', 'operator', 'reviewer']
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or p_payload ->> 'spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    spec_version_value := (p_payload ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_status_payload_invalid';
  end;
  spec_hash_value := lower(content_factory_private.require_text(
    p_payload, 'spec_hash', 64, 64
  ));
  perform content_factory_private.require_generation_spec_project_v49(
    organization_id_value, project_id_value,
    spec_id_value, spec_version_value, spec_hash_value, null
  );

  previous_project_setting := current_setting(
    'contentengine.project_id', true
  );
  if nullif(previous_project_setting, '') is not null then
    begin
      previous_project_id := previous_project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end;
    if previous_project_id <> project_id_value then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;
  perform set_config(
    'contentengine.project_id', project_id_value::text, true
  );
  begin
    result_value := content_factory_private
      .creator_generation_spec_status_pre_project_v49(
        p_payload - 'project_id'
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''), true
  );
  return result_value;
end;
$$;

create or replace function public.creator_control_generation_spec(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  expected_version_value integer;
  expected_hash_value text;
  previous_project_setting text;
  previous_project_id uuid;
  result_value jsonb;
  result_spec_version integer;
  result_spec_hash text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023', message = 'project_id_required';
  end if;
  if length(p_payload::text) > 131072
     or p_payload - array[
       'organization_id', 'project_id', 'spec_id',
       'expected_spec_version', 'expected_spec_hash', 'action',
       'confirmation', 'reason', 'idempotency_key', 'patch',
       'target_spec_version'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'project_id', 'spec_id',
       'expected_spec_version', 'expected_spec_hash', 'action',
       'confirmation', 'reason', 'idempotency_key'
     ]::text[]
     or jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or p_payload -> 'confirmation' <> 'true'::jsonb then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'expected_spec_version') <> 'number'
       or p_payload ->> 'expected_spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    expected_version_value := (
      p_payload ->> 'expected_spec_version'
    )::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_version_invalid';
  end;
  expected_hash_value := lower(content_factory_private.require_text(
    p_payload, 'expected_spec_hash', 64, 64
  ));
  if expected_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'generation_spec_control_payload_invalid';
  end if;
  perform content_factory_private.require_generation_spec_project_v49(
    organization_id_value, project_id_value,
    spec_id_value, expected_version_value, expected_hash_value, null
  );
  if p_payload ->> 'action' = 'approve'
     and not content_factory_private
       .generation_spec_research_category_rule_current(
         organization_id_value, spec_id_value,
         expected_version_value, expected_hash_value
       ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale';
  end if;

  previous_project_setting := current_setting(
    'contentengine.project_id', true
  );
  if nullif(previous_project_setting, '') is not null then
    begin
      previous_project_id := previous_project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end;
    if previous_project_id <> project_id_value then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;
  perform set_config(
    'contentengine.project_id', project_id_value::text, true
  );
  begin
    result_value := content_factory_private
      .creator_control_generation_spec_pre_project_v49(
        p_payload - 'project_id'
      );
    result_spec_version := (
      result_value #>> '{generation_spec,spec_version}'
    )::integer;
    result_spec_hash := result_value #>> '{generation_spec,spec_hash}';
    perform content_factory_private.require_generation_spec_project_v49(
      organization_id_value, project_id_value,
      spec_id_value, result_spec_version, result_spec_hash, null
    );
    if p_payload ->> 'action' <> 'reject'
       and not content_factory_private
         .generation_spec_research_category_rule_current(
           organization_id_value, spec_id_value,
           result_spec_version, result_spec_hash
         ) then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_research_category_rule_stale';
    end if;
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''), true
  );
  return result_value;
end;
$$;

revoke all on function public.creator_prepare_generation_spec(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_generation_spec_status(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_control_generation_spec(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_prepare_generation_spec(jsonb)
  to authenticated;
grant execute on function public.creator_generation_spec_status(jsonb)
  to authenticated;
grant execute on function public.creator_control_generation_spec(jsonb)
  to authenticated;

-- Replace the v48 effective-policy boundary with the complete v49 lineage
-- check while retaining its already-published response (including project_id).
create or replace function public.creator_generation_spec_effective_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  previous_project_setting text;
  previous_project_id uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using
      errcode = '22023', message = 'project_id_required';
  end if;
  if p_payload - array[
       'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_effective_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  begin
    if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or p_payload ->> 'spec_version' !~ '^[0-9]+$' then
      raise invalid_text_representation;
    end if;
    spec_version_value := (p_payload ->> 'spec_version')::integer;
  exception when invalid_text_representation or numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_effective_payload_invalid';
  end;
  spec_hash_value := lower(content_factory_private.require_text(
    p_payload, 'spec_hash', 64, 64
  ));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_effective_payload_invalid';
  end if;

  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  perform content_factory_private.require_generation_spec_project_v49(
    organization_id_value, project_id_value,
    spec_id_value, spec_version_value, spec_hash_value, null
  );
  if not content_factory_private
    .generation_spec_research_category_rule_current(
      organization_id_value, spec_id_value,
      spec_version_value, spec_hash_value
    ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale';
  end if;
  previous_project_setting := current_setting(
    'contentengine.project_id', true
  );
  if nullif(previous_project_setting, '') is not null then
    begin
      previous_project_id := previous_project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end;
    if previous_project_id <> project_id_value then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;
  perform set_config(
    'contentengine.project_id', project_id_value::text, true
  );
  begin
    result_value := content_factory_private
      .creator_generation_spec_effective_policy_pre_project_v48(
        p_payload - 'project_id'
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''), true
  );
  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000', message = 'project_scoped_result_invalid';
  end if;
  return result_value || jsonb_build_object('project_id', project_id_value);
end;
$$;

revoke all on function public.creator_generation_spec_effective_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_generation_spec_effective_policy(jsonb)
  to authenticated;

-- Provider claim runs in a service transaction with no request GUC.  The job
-- is the sole project authority; v49 revalidates every immutable provenance
-- anchor before the preserved claim engine can transition toward provider IO.
create or replace function
  content_factory_private.generation_spec_live_claim_snapshot(
    organization_id_value uuid,
    generation_job_id_value uuid,
    spec_id_value uuid,
    spec_version_value integer,
    spec_hash_value text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  job_row content_factory.generation_jobs%rowtype;
  project_id_value uuid;
  previous_project_setting text;
  previous_project_id uuid;
  result_value jsonb;
begin
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.id = generation_job_id_value
    and job.generation_spec_id = spec_id_value
    and job.generation_spec_version = spec_version_value
    and job.generation_spec_hash = spec_hash_value
  for share;
  project_id_value := job_row.project_id;
  if job_row.id is null or project_id_value is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_provider_start_stale',
      detail = 'generation_spec_project_scope_mismatch';
  end if;
  perform 1
  from content_factory.generation_batches batch
  where batch.organization_id = organization_id_value
    and batch.id = job_row.batch_id
    and batch.product_id = job_row.product_id
    and batch.project_id = project_id_value
  for share of batch;
  if not found then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_provider_start_stale',
      detail = 'generation_spec_project_scope_mismatch';
  end if;
  begin
    perform content_factory_private.require_generation_spec_project_v49(
      organization_id_value, project_id_value,
      spec_id_value, spec_version_value, spec_hash_value, job_row.product_id
    );
  exception when sqlstate '42501' then
    if sqlerrm <> 'generation_spec_project_scope_mismatch' then
      raise;
    end if;
    -- The installed public claim engine terminalizes this exact outward code,
    -- releases spend/storage, and guarantees that provider IO cannot follow.
    raise exception using
      errcode = '55000',
      message = 'generation_spec_provider_start_stale',
      detail = 'generation_spec_project_scope_mismatch';
  when sqlstate 'P0002' then
    if sqlerrm <> 'workspace_project_not_found' then
      raise;
    end if;
    -- An inactive/deleted bound project is durable lineage drift, not a
    -- transient provider failure. Terminalization releases its reservation.
    raise exception using
      errcode = '55000',
      message = 'generation_spec_provider_start_stale',
      detail = 'workspace_project_not_found';
  end;

  previous_project_setting := current_setting(
    'contentengine.project_id', true
  );
  if nullif(previous_project_setting, '') is not null then
    begin
      previous_project_id := previous_project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023', message = 'project_context_invalid';
    end;
    if previous_project_id <> project_id_value then
      raise exception using
        errcode = '42501',
        message = 'generation_spec_project_scope_mismatch';
    end if;
  end if;
  perform set_config(
    'contentengine.project_id', project_id_value::text, true
  );
  begin
    result_value := content_factory_private
      .generation_spec_live_claim_snapshot_pre_project_v48(
        organization_id_value,
        generation_job_id_value,
        spec_id_value,
        spec_version_value,
        spec_hash_value
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''), true
  );
  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000', message = 'project_scoped_result_invalid';
  end if;
  return result_value;
end;
$$;

revoke all on function
  content_factory_private.generation_spec_live_claim_snapshot(
    uuid, uuid, uuid, integer, text
  ) from public, anon, authenticated, service_role;

comment on function public.creator_prepare_generation_spec(jsonb) is
  'Prepares a spec only inside an explicit active project; the project boundary is not added to the response document.';
comment on function public.creator_generation_spec_status(jsonb) is
  'Returns status only when the exact immutable spec media and all provenance belong to the explicit active project.';
comment on function public.creator_control_generation_spec(jsonb) is
  'Controls a spec only inside its explicit project and atomically rechecks the resulting immutable version.';

notify pgrst, 'reload schema';

commit;

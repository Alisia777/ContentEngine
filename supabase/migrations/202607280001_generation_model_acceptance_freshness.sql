begin;

-- A provider model alias may drift while its name stays unchanged.  A real
-- output therefore proves production quality only for a bounded period.
-- Keep the historical evidence visible, but fail closed after 90 days and
-- require one new independently reviewed output before showing "accepted".
create or replace function
  content_factory_private.generation_model_acceptance_freshness(
    p_acceptance jsonb,
    p_evaluated_at timestamptz
  )
returns jsonb
language plpgsql
immutable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  evidence_max_age_days constant integer := 90;
  model_value jsonb;
  evidence_value jsonb;
  adjusted_model_value jsonb;
  models_value jsonb := '[]'::jsonb;
  decided_at_value timestamptz;
  expires_at_value timestamptz;
  evidence_fresh_value boolean;
  accepted_count_value integer := 0;
  total_models_value integer;
begin
  if p_acceptance is null
     or jsonb_typeof(p_acceptance) <> 'object'
     or jsonb_typeof(p_acceptance -> 'models') <> 'array'
     or p_evaluated_at is null then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_freshness_invalid';
  end if;

  total_models_value := jsonb_array_length(p_acceptance -> 'models');

  for model_value in
    select model.value
    from jsonb_array_elements(p_acceptance -> 'models')
      with ordinality model(value, ordinality)
    order by model.ordinality
  loop
    evidence_value := model_value -> 'evidence';
    decided_at_value := null;
    expires_at_value := null;
    evidence_fresh_value := false;

    if jsonb_typeof(evidence_value) = 'object'
       and nullif(btrim(evidence_value ->> 'decided_at'), '') is not null then
      begin
        decided_at_value := (evidence_value ->> 'decided_at')::timestamptz;
      exception
        when invalid_datetime_format or datetime_field_overflow then
          decided_at_value := null;
      end;
    end if;

    if decided_at_value is not null then
      expires_at_value :=
        decided_at_value + make_interval(days => evidence_max_age_days);
      evidence_fresh_value := expires_at_value > p_evaluated_at;
      evidence_value := evidence_value || jsonb_build_object(
        'fresh', evidence_fresh_value,
        'expires_at', expires_at_value
      );
    elsif jsonb_typeof(evidence_value) = 'object' then
      evidence_value := evidence_value || jsonb_build_object(
        'fresh', false,
        'expires_at', null
      );
    end if;

    adjusted_model_value := jsonb_set(
      model_value,
      '{evidence}',
      case
        when jsonb_typeof(evidence_value) = 'object' then evidence_value
        else 'null'::jsonb
      end,
      true
    ) || jsonb_build_object(
      'evidence_max_age_days', evidence_max_age_days
    );

    if model_value ->> 'status' = 'accepted' then
      if evidence_fresh_value then
        accepted_count_value := accepted_count_value + 1;
      else
        adjusted_model_value := adjusted_model_value || jsonb_build_object(
          'status', 'needs_revalidation',
          'reason_code', 'acceptance_evidence_stale',
          'next_action_code', 'generate_replacement_and_approve'
        );
      end if;
    end if;

    models_value := models_value || jsonb_build_array(
      adjusted_model_value
    );
  end loop;

  return p_acceptance || jsonb_build_object(
    'version', 'generation-model-acceptance-v3',
    'evidence_max_age_days', evidence_max_age_days,
    'accepted_count', accepted_count_value,
    'total_models', total_models_value,
    'all_models_accepted',
      total_models_value > 0
      and accepted_count_value = total_models_value,
    'models', models_value,
    'evaluated_at', p_evaluated_at
  );
end;
$$;

revoke all on function
  content_factory_private.generation_model_acceptance_freshness(
    jsonb,
    timestamptz
  )
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_model_acceptance(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  organization_id uuid;
  acceptance_value jsonb;
  pending_value jsonb;
  models_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_model_acceptance_payload_invalid';
  end if;
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );

  acceptance_value :=
    content_factory_private.generation_model_acceptance_freshness(
      content_factory_private.generation_model_acceptance(
        organization_id
      ),
      now()
    );
  pending_value :=
    content_factory_private.generation_model_acceptance_pending(
      organization_id
    );

  select coalesce(
    jsonb_agg(
      model.value || jsonb_build_object(
        'pending_review',
        pending_value -> (model.value ->> 'model')
      )
      order by model.ordinality
    ),
    '[]'::jsonb
  )
  into models_value
  from jsonb_array_elements(
    acceptance_value -> 'models'
  ) with ordinality model(value, ordinality);

  return jsonb_set(
    acceptance_value,
    '{models}',
    models_value,
    false
  );
end;
$$;

revoke all on function
  public.creator_generation_model_acceptance(jsonb)
  from public, anon;
grant execute on function
  public.creator_generation_model_acceptance(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

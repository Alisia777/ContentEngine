begin;

-- Keep the mature-performance resolver intact and put a bounded exploration
-- layer in front of it.  The previous resolver deliberately returned a
-- baseline product_focus prompt until enough competing evidence existed.  In
-- an autonomous workflow that meant competing evidence could never appear
-- without a human-authored research handoff.
alter function public.creator_generation_learning_policy(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_learning_policy(jsonb)
  rename to creator_generation_learning_performance_policy_v1;

revoke all on function
  content_factory_private.creator_generation_learning_performance_policy_v1(
    jsonb
  )
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
  performance_policy jsonb;
  organization_id uuid;
  media_id_value uuid;
  product_id_value uuid;
  platform_value text;
  model_value text;
  selected_angle_value text;
  selected_patterns_value jsonb;
  selected_use_count integer := 0;
  policy_without_hash jsonb;
  policy_hash_value text;
  requested_model_value text;
begin
  performance_policy :=
    content_factory_private
      .creator_generation_learning_performance_policy_v1(p_payload);
  requested_model_value := performance_policy ->> 'requested_model';

  if performance_policy -> 'applied' is not distinct from 'true'::jsonb then
    policy_without_hash :=
      (performance_policy - 'policy_hash' - 'requested_model')
      || jsonb_build_object(
        'version', 'generation-learning-v2',
        'selection_mode', 'performance',
        'selected_angle', performance_policy ->> 'preferred_angle',
        'selected_hook_patterns',
          coalesce(
            performance_policy -> 'preferred_hook_patterns',
            '[]'::jsonb
          )
      );
  else
    organization_id :=
      content_factory_private.resolve_organization(p_payload);
    media_id_value :=
      content_factory_private.require_uuid(p_payload, 'media_id');
    platform_value :=
      lower(btrim(coalesce(p_payload ->> 'platform', '')));
    model_value :=
      lower(btrim(coalesce(p_payload ->> 'model', '')));

    select media.product_id into product_id_value
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.id = media_id_value;
    if product_id_value is null then
      raise exception using
        errcode = '42501',
        message = 'generation_learning_policy_media_invalid';
    end if;

    -- Alternate only between two conservative, prompt-compiler-supported
    -- structures.  Two angles reach the mature-policy threshold after six
    -- successful observations instead of spreading paid tests too thinly.
    with candidates(angle, hook_patterns, priority) as (
      values
        ('product_focus'::text, '[]'::jsonb, 1),
        ('demonstration'::text, '["demonstration"]'::jsonb, 2)
    ),
    candidate_usage as (
      select
        candidate.angle,
        candidate.hook_patterns,
        candidate.priority,
        count(job.id)::integer as use_count
      from candidates candidate
      left join content_factory.generation_creative_signals signal
        on signal.organization_id = organization_id
       and signal.product_id = product_id_value
       and signal.platform = platform_value
       and signal.model = model_value
       and signal.creative_angle = candidate.angle
      left join content_factory.generation_jobs job
        on job.organization_id = signal.organization_id
       and job.id = signal.generation_job_id
       and job.status not in ('failed', 'cancelled')
      group by
        candidate.angle,
        candidate.hook_patterns,
        candidate.priority
    )
    select usage.angle, usage.hook_patterns, usage.use_count
    into
      selected_angle_value,
      selected_patterns_value,
      selected_use_count
    from candidate_usage usage
    order by usage.use_count, usage.priority
    limit 1;

    policy_without_hash :=
      (performance_policy - 'policy_hash' - 'requested_model')
      || jsonb_build_object(
        'version', 'generation-learning-v2',
        -- The paid-start wrapper already binds every applied policy hash,
        -- angle and hook pattern again immediately before provider state.
        'applied', true,
        'confidence', 'medium',
        'selection_mode', 'bounded_exploration',
        'preferred_angle', selected_angle_value,
        'avoid_angle', null,
        'preferred_hook_patterns', selected_patterns_value,
        'selected_angle', selected_angle_value,
        'selected_hook_patterns', selected_patterns_value,
        'reason_codes',
          coalesce(
            performance_policy -> 'reason_codes',
            '[]'::jsonb
          ) || '["bounded_exploration_required"]'::jsonb,
        'exploration', jsonb_build_object(
          'candidate_count', 2,
          'selected_prior_use_count', selected_use_count,
          'balancing_scope', 'product_platform_model'
        ),
        'safety',
          coalesce(performance_policy -> 'safety', '{}'::jsonb)
          || jsonb_build_object(
            'selection_is_structural_only', true,
            'exploration_angles_are_server_bounded', true,
            'provider_spend_requires_separate_confirmation', true
          )
      );
  end if;

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

notify pgrst, 'reload schema';

commit;

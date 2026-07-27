begin;

-- Re-evaluate the authoritative repair policy for a review that is already
-- visible in the review catalog, then expose only the minimum routing state.
-- The browser never receives prompt text, score snapshots, hashes, job UUIDs,
-- participant identities, or provider data through this helper.
create or replace function
  content_factory_private.generated_media_repair_next_action(
    p_organization_id uuid,
    p_review_id uuid,
    p_user_id uuid,
    p_actor_role text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  policy_value jsonb;
  followup_created_at timestamptz;
  followup_job_status text;
  action_status text;
  can_prepare_value boolean;
begin
  if p_organization_id is null
     or p_review_id is null
     or p_user_id is null
     or auth.uid() is distinct from p_user_id then
    return null;
  end if;

  begin
    policy_value := public.creator_generation_repair_policy(
      jsonb_build_object(
        'organization_id', p_organization_id,
        'review_id', p_review_id
      )
    );
  exception when others then
    return null;
  end;

  if policy_value -> 'applied' is distinct from 'true'::jsonb then
    return null;
  end if;

  select signal.created_at, job.status
  into followup_created_at, followup_job_status
  from content_factory.generation_repair_signals signal
  join content_factory.generation_jobs job
    on job.organization_id = signal.organization_id
   and job.id = signal.generation_job_id
  where signal.organization_id = p_organization_id
    and signal.source_review_id = p_review_id;

  if followup_created_at is not null then
    action_status := case
      when followup_job_status in (
        'queued', 'starting', 'submitted', 'processing', 'running'
      ) then 'in_progress'
      when followup_job_status = 'succeeded' then 'succeeded'
      when followup_job_status in ('failed', 'cancelled') then 'failed'
      else 'started'
    end;
    return jsonb_build_object(
      'status', action_status,
      'can_prepare', false,
      'started_at', followup_created_at
    );
  end if;

  can_prepare_value := p_actor_role in (
    'owner', 'admin', 'producer', 'operator'
  );
  return jsonb_build_object(
    'status', 'available',
    'can_prepare', can_prepare_value,
    'started_at', null
  );
end;
$$;

revoke all on function
  content_factory_private.generated_media_repair_next_action(
    uuid, uuid, uuid, text
  )
  from public, anon, authenticated, service_role;

-- Preserve the assignment-aware catalog installed in migration 007 and add
-- one privacy-minimized repair action per already-visible review.
alter function public.creator_content_review_catalog(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_content_review_catalog(jsonb)
  rename to creator_content_review_catalog_without_repair_actions;

revoke all on function
  content_factory_private
    .creator_content_review_catalog_without_repair_actions(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_content_review_catalog(
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
  user_id uuid;
  organization_id uuid;
  actor_role text;
  catalog_value jsonb;
  runs_value jsonb;
begin
  catalog_value :=
    content_factory_private
      .creator_content_review_catalog_without_repair_actions(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  actor_role := catalog_value ->> 'role';

  select coalesce(
    jsonb_agg(
      run.value || jsonb_build_object(
        'repair_next_action',
        case
          when run.value #>> '{decision,decision}' = 'needs_changes'
          then content_factory_private.generated_media_repair_next_action(
            organization_id,
            (run.value ->> 'id')::uuid,
            user_id,
            actor_role
          )
          else null
        end
      )
      order by run.ordinality
    ),
    '[]'::jsonb
  )
  into runs_value
  from jsonb_array_elements(
    catalog_value -> 'recent_reviews'
  ) with ordinality run(value, ordinality);

  return jsonb_set(
    catalog_value,
    '{recent_reviews}',
    runs_value,
    false
  );
end;
$$;

revoke all on function
  public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function
  public.creator_content_review_catalog(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

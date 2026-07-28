begin;

-- The paid-start checkbox already states that generated-video QA starts
-- automatically without transcription.  Persist that exact consent beside
-- the generation job so closing the browser while Runway renders cannot turn
-- the promised autopilot into a manual button.
create table if not exists
  content_factory.generation_review_autostart_consents (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    generation_job_id uuid not null,
    confirmed_by uuid not null,
    terms_version text not null check (
      terms_version = 'generated-video-qa-autostart-v1'
    ),
    confirmed_at timestamptz not null default now(),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, confirmed_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, generation_job_id)
  );

alter table
  content_factory.generation_review_autostart_consents
  enable row level security;
revoke all on
  content_factory.generation_review_autostart_consents
  from public, anon, authenticated;
grant all on
  content_factory.generation_review_autostart_consents
  to service_role;

create or replace function
  content_factory_private.reject_generation_review_autostart_consent_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_review_autostart_consent_immutable';
end;
$$;

revoke all on function
  content_factory_private
    .reject_generation_review_autostart_consent_mutation()
  from public, anon, authenticated, service_role;

drop trigger if exists generation_review_autostart_consent_append_only
  on content_factory.generation_review_autostart_consents;
create trigger generation_review_autostart_consent_append_only
before update or delete
on content_factory.generation_review_autostart_consents
for each row execute function
  content_factory_private
    .reject_generation_review_autostart_consent_mutation();

-- Keep the complete monetary, identity, learning and prompt-validation chain
-- intact.  The consent row is written only after that chain returns a valid
-- job, but remains in the same transaction and therefore rolls back before
-- Edge can call the paid provider if its binding is invalid.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_review_autostart_v11;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_review_autostart_v11(jsonb)
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
  job_id_value uuid;
  model_value text;
  consent_key_present boolean;
  job_row content_factory.generation_jobs%rowtype;
  consent_row
    content_factory.generation_review_autostart_consents%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  result_value := content_factory_private
    .creator_start_real_generation_pre_review_autostart_v11(p_payload);

  model_value := lower(btrim(coalesce(
    result_value #>> '{job,model}',
    p_payload ->> 'model',
    ''
  )));
  if model_value not in ('gen4_turbo', 'seedance2_fast') then
    return jsonb_set(
      result_value,
      '{job,review_autostart_confirmed}',
      'false'::jsonb,
      true
    );
  end if;

  consent_key_present :=
    p_payload ? 'review_autostart_confirmed'
    or p_payload ? 'review_autostart_terms_version';
  if not consent_key_present then
    -- Compatibility for audited legacy callers: their jobs remain manual.
    return jsonb_set(
      result_value,
      '{job,review_autostart_confirmed}',
      'false'::jsonb,
      true
    );
  end if;
  if p_payload -> 'review_autostart_confirmed'
       is distinct from 'true'::jsonb
     or p_payload ->> 'review_autostart_terms_version'
       is distinct from 'generated-video-qa-autostart-v1' then
    raise exception using
      errcode = '22023',
      message = 'generation_review_autostart_consent_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  job_id_value := content_factory_private.require_uuid(
    coalesce(result_value -> 'job', '{}'::jsonb),
    'id'
  );
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value
  for share;
  if job_row.id is null
     or job_row.requested_by is distinct from user_id
     or job_row.mode <> 'real'
     or job_row.provider <> 'runway'
     or job_row.input ->> 'model' is distinct from model_value
     or job_row.input ->> 'model' not in (
       'gen4_turbo', 'seedance2_fast'
     ) then
    raise exception using
      errcode = '55000',
      message = 'generation_review_autostart_binding_invalid';
  end if;

  insert into content_factory.generation_review_autostart_consents (
    organization_id,
    generation_job_id,
    confirmed_by,
    terms_version
  ) values (
    organization_id,
    job_row.id,
    user_id,
    'generated-video-qa-autostart-v1'
  )
  on conflict (organization_id, generation_job_id) do nothing;

  select consent.* into consent_row
  from content_factory.generation_review_autostart_consents consent
  where consent.organization_id = organization_id
    and consent.generation_job_id = job_row.id;
  if consent_row.id is null
     or consent_row.confirmed_by is distinct from user_id
     or consent_row.terms_version
       is distinct from 'generated-video-qa-autostart-v1' then
    raise exception using
      errcode = '23505',
      message = 'generation_review_autostart_consent_conflict';
  end if;

  result_value := jsonb_set(
    result_value,
    '{job,review_autostart_confirmed}',
    'true'::jsonb,
    true
  );
  result_value := jsonb_set(
    result_value,
    '{job,review_autostart_terms_version}',
    to_jsonb(consent_row.terms_version),
    true
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'generation_review_autostart_consented',
    'generation_job',
    job_row.id::text,
    jsonb_build_object(
      'model', model_value,
      'terms_version', consent_row.terms_version,
      'transcription_requested', false
    ),
    'generation-review-autostart-consent:' || job_row.id::text
  );
  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

-- The browser recovers completed jobs through this read-only status RPC.
-- Return only the bounded boolean/version, never the consent identity.
alter function public.creator_real_generation_status(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_real_generation_status(jsonb)
  rename to creator_real_generation_status_pre_review_autostart_v2;

revoke all on function
  content_factory_private
    .creator_real_generation_status_pre_review_autostart_v2(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_real_generation_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  job_id_value uuid;
  model_value text;
  consent_terms_version text;
  consent_confirmed boolean := false;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  result_value := content_factory_private
    .creator_real_generation_status_pre_review_autostart_v2(p_payload);
  organization_id :=
    content_factory_private.resolve_organization(p_payload);
  job_id_value := content_factory_private.require_uuid(
    coalesce(result_value -> 'job', '{}'::jsonb),
    'id'
  );
  model_value := lower(btrim(coalesce(
    result_value #>> '{job,model}',
    ''
  )));
  if model_value in ('gen4_turbo', 'seedance2_fast') then
    select consent.terms_version into consent_terms_version
    from content_factory.generation_review_autostart_consents consent
    where consent.organization_id = organization_id
      and consent.generation_job_id = job_id_value;
    consent_confirmed :=
      consent_terms_version = 'generated-video-qa-autostart-v1';
  end if;

  result_value := jsonb_set(
    result_value,
    '{job,review_autostart_confirmed}',
    to_jsonb(consent_confirmed),
    true
  );
  if consent_confirmed then
    result_value := jsonb_set(
      result_value,
      '{job,review_autostart_terms_version}',
      to_jsonb(consent_terms_version),
      true
    );
  end if;
  return result_value;
end;
$$;

revoke all on function public.creator_real_generation_status(jsonb)
  from public, anon;
grant execute on function public.creator_real_generation_status(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

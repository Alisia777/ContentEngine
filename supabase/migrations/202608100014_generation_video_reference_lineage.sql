begin;

-- A generation reference is neither research evidence nor provider media.
-- It records the exact public identity and an operator-authored mechanism;
-- only that mechanism may enter the compiled prompt.
create table content_factory.generation_spec_video_reference_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  spec_id uuid not null,
  spec_version integer not null check (spec_version between 1 and 100000),
  spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
  platform text not null default 'youtube' check (platform = 'youtube'),
  video_id text not null check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  canonical_url text not null check (
    canonical_url ~ '^https://youtube[.]com/watch[?]v=[A-Za-z0-9_-]{11}$'
  ),
  analysis_basis text not null default 'operator_summary'
    check (analysis_basis = 'operator_summary'),
  mechanics_summary text not null check (
    length(btrim(mechanics_summary)) between 20 and 360
  ),
  source_access_confirmed boolean not null check (source_access_confirmed),
  transformative_use_confirmed boolean not null
    check (transformative_use_confirmed),
  ai_watched boolean not null default false check (not ai_watched),
  evidence_verified boolean not null default false
    check (not evidence_verified),
  attestation_version text not null check (
    attestation_version = 'generation-video-reference-v1'
  ),
  reference_hash text not null check (reference_hash ~ '^[0-9a-f]{64}$'),
  binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
  applied_by uuid not null,
  applied_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, spec_id, spec_version, binding_hash),
  unique (organization_id, binding_hash),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, spec_id, spec_version, spec_hash)
    references content_factory.generation_spec_versions(
      organization_id, spec_id, spec_version, spec_hash
    ),
  foreign key (organization_id, applied_by)
    references content_factory.memberships(organization_id, profile_id),
  check (right(canonical_url, 11) = video_id)
);

create table content_factory.generation_job_video_reference_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  generation_job_id uuid not null,
  spec_reference_binding_id uuid not null,
  spec_id uuid not null,
  spec_version integer not null check (spec_version between 1 and 100000),
  spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
  reference_hash text not null check (reference_hash ~ '^[0-9a-f]{64}$'),
  binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
  bound_by uuid not null,
  bound_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, generation_job_id),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs(organization_id, id),
  foreign key (organization_id, spec_reference_binding_id)
    references content_factory.generation_spec_video_reference_bindings(
      organization_id, id
    ),
  foreign key (organization_id, spec_id, spec_version, spec_hash)
    references content_factory.generation_spec_versions(
      organization_id, spec_id, spec_version, spec_hash
    ),
  foreign key (organization_id, bound_by)
    references content_factory.memberships(organization_id, profile_id)
);

create index generation_spec_video_reference_project_idx
  on content_factory.generation_spec_video_reference_bindings (
    organization_id, project_id, applied_at desc, id desc
  );
create index generation_job_video_reference_project_idx
  on content_factory.generation_job_video_reference_bindings (
    organization_id, project_id, bound_at desc, generation_job_id
  );

alter table content_factory.generation_spec_video_reference_bindings
  enable row level security;
alter table content_factory.generation_job_video_reference_bindings
  enable row level security;
revoke all on content_factory.generation_spec_video_reference_bindings
  from public, anon, authenticated;
revoke all on content_factory.generation_job_video_reference_bindings
  from public, anon, authenticated;
grant all on content_factory.generation_spec_video_reference_bindings
  to service_role;
grant all on content_factory.generation_job_video_reference_bindings
  to service_role;

create trigger generation_spec_video_reference_append_only
before update or delete
  on content_factory.generation_spec_video_reference_bindings
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();
create trigger generation_job_video_reference_append_only
before update or delete
  on content_factory.generation_job_video_reference_bindings
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

create or replace function public.contentengine_bind_generation_spec_video_reference(
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
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  video_id_value text;
  canonical_url_value text;
  mechanics_summary_value text;
  prompt_marker_value constant text :=
    'GenerationVideoReference/operator-summary:';
  prompt_disclaimer_value constant text :=
    'ИИ исходный ролик не просматривал.';
  expected_prompt_fragment_value text;
  prompt_marker_count_value integer := 0;
  expected_prompt_fragment_count_value integer := 0;
  reference_hash_value text;
  binding_hash_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  binding_row content_factory.generation_spec_video_reference_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash',
    'video_id', 'canonical_url', 'mechanics_summary',
    'source_access_confirmed', 'transformative_use_confirmed',
    'attestation_version', 'confirmation'
  ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'spec_id', 'spec_version', 'spec_hash', 'video_id',
       'canonical_url', 'mechanics_summary', 'source_access_confirmed',
       'transformative_use_confirmed', 'attestation_version', 'confirmation'
     ]::text[] then
    raise exception using errcode = '22023',
      message = 'generation_video_reference_binding_payload_invalid';
  end if;
  if p_payload -> 'confirmation' <> 'true'::jsonb
     or p_payload -> 'source_access_confirmed' <> 'true'::jsonb
     or p_payload -> 'transformative_use_confirmed' <> 'true'::jsonb
     or p_payload ->> 'attestation_version'
          <> 'generation-video-reference-v1' then
    raise exception using errcode = '22023',
      message = 'generation_video_reference_attestation_required';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[0-9]{1,6}$' then
    raise exception using errcode = '22023',
      message = 'generation_video_reference_binding_payload_invalid';
  end if;
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(coalesce(p_payload ->> 'spec_hash', '')));
  video_id_value := btrim(coalesce(p_payload ->> 'video_id', ''));
  canonical_url_value := btrim(coalesce(p_payload ->> 'canonical_url', ''));
  mechanics_summary_value := btrim(regexp_replace(
    coalesce(p_payload ->> 'mechanics_summary', ''), '\s+', ' ', 'g'
  ));
  if spec_hash_value !~ '^[0-9a-f]{64}$'
     or video_id_value !~ '^[A-Za-z0-9_-]{11}$'
     or canonical_url_value <>
          'https://youtube.com/watch?v=' || video_id_value
     or length(mechanics_summary_value) not between 20 and 360
     or mechanics_summary_value ~*
          '(https?://|www[.]|youtube([.]com|-nocookie[.]com)|youtu[.]be)'
     or position(prompt_marker_value in mechanics_summary_value) > 0 then
    raise exception using errcode = '22023',
      message = 'generation_video_reference_binding_payload_invalid';
  end if;
  expected_prompt_fragment_value := prompt_marker_value || ' '
    || mechanics_summary_value || '. ' || prompt_disclaimer_value;

  perform content_factory_private.require_generation_spec_project_v49(
    organization_id_value, project_id_value, spec_id_value,
    spec_version_value, spec_hash_value, null
  );
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share;
  if spec_row.version_id is not null then
    prompt_marker_count_value := (
      char_length(spec_row.compiled_prompt)
      - char_length(replace(
          spec_row.compiled_prompt, prompt_marker_value, ''
        ))
    ) / char_length(prompt_marker_value);
    expected_prompt_fragment_count_value := (
      char_length(spec_row.compiled_prompt)
      - char_length(replace(
          spec_row.compiled_prompt, expected_prompt_fragment_value, ''
        ))
    ) / char_length(expected_prompt_fragment_value);
  end if;
  if spec_row.version_id is null
     or spec_row.model = 'seedream5_lite'
     or prompt_marker_count_value <> 1
     or expected_prompt_fragment_count_value <> 1
     or position(canonical_url_value in spec_row.compiled_prompt) > 0
     or position(video_id_value in spec_row.compiled_prompt) > 0 then
    raise exception using errcode = '55000',
      message = 'generation_video_reference_prompt_binding_invalid';
  end if;

  reference_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'generation-video-reference-v1',
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'platform', 'youtube',
      'video_id', video_id_value,
      'canonical_url', canonical_url_value,
      'analysis_basis', 'operator_summary',
      'mechanics_summary', mechanics_summary_value,
      'source_access_confirmed', true,
      'transformative_use_confirmed', true,
      'ai_watched', false,
      'evidence_verified', false,
      'attestation_version', 'generation-video-reference-v1'
    )
  );
  binding_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'spec_id', spec_id_value,
      'spec_version', spec_version_value,
      'spec_hash', spec_hash_value,
      'reference_hash', reference_hash_value
    )
  );

  select binding.* into binding_row
  from content_factory.generation_spec_video_reference_bindings binding
  where binding.organization_id = organization_id_value
    and binding.binding_hash = binding_hash_value;
  if binding_row.id is null then
    insert into content_factory.generation_spec_video_reference_bindings (
      organization_id, project_id, spec_id, spec_version, spec_hash,
      video_id, canonical_url, mechanics_summary, source_access_confirmed,
      transformative_use_confirmed, attestation_version, reference_hash,
      binding_hash, applied_by
    ) values (
      organization_id_value, project_id_value, spec_id_value,
      spec_version_value, spec_hash_value, video_id_value,
      canonical_url_value, mechanics_summary_value, true, true,
      'generation-video-reference-v1', reference_hash_value,
      binding_hash_value, actor_id_value
    ) returning * into binding_row;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-video-reference-lineage-v1',
    'binding', jsonb_build_object(
      'id', binding_row.id,
      'project_id', binding_row.project_id,
      'spec_id', binding_row.spec_id,
      'spec_version', binding_row.spec_version,
      'spec_hash', binding_row.spec_hash,
      'video_id', binding_row.video_id,
      'canonical_url', binding_row.canonical_url,
      'analysis_basis', binding_row.analysis_basis,
      'mechanics_summary', binding_row.mechanics_summary,
      'source_access_confirmed', binding_row.source_access_confirmed,
      'transformative_use_confirmed',
        binding_row.transformative_use_confirmed,
      'attestation_version', binding_row.attestation_version,
      'ai_watched', binding_row.ai_watched,
      'evidence_verified', binding_row.evidence_verified,
      'reference_hash', binding_row.reference_hash,
      'binding_hash', binding_row.binding_hash,
      'applied_at', binding_row.applied_at
    ),
    'contract', jsonb_build_object(
      'generation_only', true,
      'research_provenance_changed', false,
      'raw_url_enters_provider_prompt', false,
      'provider_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

create or replace function public.contentengine_generation_video_reference_lineage(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  project_id_value uuid;
  job_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  binding_row content_factory.generation_spec_video_reference_bindings%rowtype;
  job_binding_row content_factory.generation_job_video_reference_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'generation_job_id',
    'spec_id', 'spec_version', 'spec_hash'
  ]::text[] <> '{}'::jsonb
     or not p_payload ? 'project_id'
     or ((p_payload ? 'generation_job_id') = (p_payload ? 'spec_id')) then
    raise exception using errcode = '22023',
      message = 'generation_video_reference_lineage_payload_invalid';
  end if;
  perform content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, auth.uid()
  );

  if p_payload ? 'generation_job_id' then
    job_id_value := content_factory_private.require_uuid(
      p_payload, 'generation_job_id'
    );
    select job_binding.* into job_binding_row
    from content_factory.generation_job_video_reference_bindings job_binding
    where job_binding.organization_id = organization_id_value
      and job_binding.project_id = project_id_value
      and job_binding.generation_job_id = job_id_value;
    if job_binding_row.id is not null then
      select binding.* into binding_row
      from content_factory.generation_spec_video_reference_bindings binding
      where binding.organization_id = organization_id_value
        and binding.id = job_binding_row.spec_reference_binding_id;
    end if;
  else
    spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
    if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or coalesce(p_payload ->> 'spec_version', '') !~ '^[0-9]{1,6}$' then
      raise exception using errcode = '22023',
        message = 'generation_video_reference_lineage_payload_invalid';
    end if;
    spec_version_value := (p_payload ->> 'spec_version')::integer;
    spec_hash_value := lower(btrim(coalesce(p_payload ->> 'spec_hash', '')));
    perform content_factory_private.require_generation_spec_project_v49(
      organization_id_value, project_id_value, spec_id_value,
      spec_version_value, spec_hash_value, null
    );
    select binding.* into binding_row
    from content_factory.generation_spec_video_reference_bindings binding
    where binding.organization_id = organization_id_value
      and binding.project_id = project_id_value
      and binding.spec_id = spec_id_value
      and binding.spec_version = spec_version_value
      and binding.spec_hash = spec_hash_value
    order by binding.applied_at desc, binding.id desc
    limit 1;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-video-reference-lineage-v1',
    'lineage', case when binding_row.id is null then null else
      jsonb_build_object(
        'binding_id', binding_row.id,
        'generation_job_id', job_binding_row.generation_job_id,
        'project_id', binding_row.project_id,
        'spec_id', binding_row.spec_id,
        'spec_version', binding_row.spec_version,
        'spec_hash', binding_row.spec_hash,
        'video_id', binding_row.video_id,
        'canonical_url', binding_row.canonical_url,
        'analysis_basis', binding_row.analysis_basis,
        'mechanics_summary', binding_row.mechanics_summary,
        'source_access_confirmed', binding_row.source_access_confirmed,
        'transformative_use_confirmed',
          binding_row.transformative_use_confirmed,
        'attestation_version', binding_row.attestation_version,
        'ai_watched', binding_row.ai_watched,
        'evidence_verified', binding_row.evidence_verified,
        'reference_hash', binding_row.reference_hash,
        'binding_hash', binding_row.binding_hash,
        'applied_at', binding_row.applied_at,
        'bound_at', job_binding_row.bound_at
      ) end,
    'contract', jsonb_build_object(
      'project_shared', true,
      'generation_only', true,
      'operator_summary_only', true,
      'ai_watched', false,
      'evidence_verified', false
    )
  );
end;
$$;

-- Bind the chosen reference to the paid job before the Edge Function can
-- contact Runway. The delegated audited start never sees the URL or binding.
alter function public.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_video_reference_v54;
alter function public.creator_start_real_generation_pre_video_reference_v54(jsonb)
  set schema content_factory_private;
revoke all on function
  content_factory_private.creator_start_real_generation_pre_video_reference_v54(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_real_generation(
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
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  context_value jsonb;
  binding_id_value uuid;
  binding_hash_value text;
  idempotency_key_value text;
  replay_job_id_value uuid;
  result_value jsonb;
  job_id_value uuid;
  batch_id_value uuid;
  spec_binding_row content_factory.generation_spec_video_reference_bindings%rowtype;
  job_binding_row content_factory.generation_job_video_reference_bindings%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  prompt_has_reference_value boolean := false;
  prompt_marker_value constant text :=
    'GenerationVideoReference/operator-summary:';
  prompt_disclaimer_value constant text :=
    'ИИ исходный ролик не просматривал.';
  expected_prompt_fragment_value text;
  prompt_marker_count_value integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id_value, project_id_value, auth.uid()
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id::text =
      p_payload #>> '{generation_spec_context,spec_id}'
    and version.spec_version::text =
      p_payload #>> '{generation_spec_context,spec_version}'
    and version.spec_hash =
      p_payload #>> '{generation_spec_context,spec_hash}';
  if spec_row.version_id is not null then
    prompt_marker_count_value := (
      char_length(spec_row.compiled_prompt)
      - char_length(replace(
          spec_row.compiled_prompt, prompt_marker_value, ''
        ))
    ) / char_length(prompt_marker_value);
  end if;
  prompt_has_reference_value := prompt_marker_count_value > 0;
  context_value := p_payload -> 'generation_reference_context';
  if prompt_marker_count_value not between 0 and 1
     or prompt_has_reference_value <> (context_value is not null) then
    raise exception using errcode = '22023',
      message = 'generation_video_reference_context_invalid';
  end if;
  if context_value is not null then
    if jsonb_typeof(context_value) <> 'object'
       or context_value - array['binding_id', 'binding_hash']::text[]
            <> '{}'::jsonb
       or not context_value ?& array['binding_id', 'binding_hash']::text[] then
      raise exception using errcode = '22023',
        message = 'generation_video_reference_context_invalid';
    end if;
    begin
      binding_id_value := (context_value ->> 'binding_id')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023',
        message = 'generation_video_reference_context_invalid';
    end;
    binding_hash_value := lower(btrim(context_value ->> 'binding_hash'));
    if binding_hash_value !~ '^[0-9a-f]{64}$' then
      raise exception using errcode = '22023',
        message = 'generation_video_reference_context_invalid';
    end if;
    select binding.* into spec_binding_row
    from content_factory.generation_spec_video_reference_bindings binding
    where binding.organization_id = organization_id_value
      and binding.project_id = project_id_value
      and binding.id = binding_id_value
      and binding.binding_hash = binding_hash_value
      and binding.spec_id::text =
          p_payload #>> '{generation_spec_context,spec_id}'
      and binding.spec_version::text =
          p_payload #>> '{generation_spec_context,spec_version}'
      and binding.spec_hash =
          p_payload #>> '{generation_spec_context,spec_hash}'
    for share;
    if spec_binding_row.id is null then
      raise exception using errcode = '42501',
        message = 'generation_video_reference_scope_mismatch';
    end if;
    expected_prompt_fragment_value := prompt_marker_value || ' '
      || spec_binding_row.mechanics_summary || '. '
      || prompt_disclaimer_value;
    if prompt_marker_count_value <> 1
       or position(
            expected_prompt_fragment_value in spec_row.compiled_prompt
          ) = 0 then
      raise exception using errcode = '55000',
        message = 'generation_video_reference_prompt_binding_invalid';
    end if;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-video-reference:' || idempotency_key_value)
  );
  select job.id into replay_job_id_value
  from content_factory.generation_batches batch
  join content_factory.generation_jobs job
    on job.organization_id = batch.organization_id
   and job.batch_id = batch.id
  where batch.organization_id = organization_id_value
    and batch.idempotency_key = idempotency_key_value
    and job.requested_by = actor_id_value
  limit 1;
  if replay_job_id_value is not null then
    select binding.* into job_binding_row
    from content_factory.generation_job_video_reference_bindings binding
    where binding.organization_id = organization_id_value
      and binding.generation_job_id = replay_job_id_value;
    if (binding_id_value is null) <> (job_binding_row.id is null)
       or (
         binding_id_value is not null and (
           job_binding_row.spec_reference_binding_id <> binding_id_value
           or job_binding_row.binding_hash <> binding_hash_value
         )
       ) then
      raise exception using errcode = '23505',
        message = 'idempotency_key_conflict';
    end if;
  end if;

  result_value := content_factory_private
    .creator_start_real_generation_pre_video_reference_v54(
      p_payload - 'generation_reference_context'
    );
  begin
    job_id_value := (result_value #>> '{job,id}')::uuid;
    batch_id_value := (result_value #>> '{batch,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using errcode = '55000',
      message = 'generation_video_reference_job_binding_invalid';
  end;

  if binding_id_value is null then
    return result_value;
  end if;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id_value
    and job.project_id = project_id_value
    and job.id = job_id_value
    and job.batch_id = batch_id_value
    and job.generation_spec_id = spec_binding_row.spec_id
    and job.generation_spec_version = spec_binding_row.spec_version
    and job.generation_spec_hash = spec_binding_row.spec_hash
  for update;
  if job_row.id is null then
    raise exception using errcode = '55000',
      message = 'generation_video_reference_job_binding_invalid';
  end if;

  insert into content_factory.generation_job_video_reference_bindings (
    organization_id, project_id, generation_job_id,
    spec_reference_binding_id, spec_id, spec_version, spec_hash,
    reference_hash, binding_hash, bound_by
  ) values (
    organization_id_value, project_id_value, job_id_value,
    spec_binding_row.id, spec_binding_row.spec_id,
    spec_binding_row.spec_version, spec_binding_row.spec_hash,
    spec_binding_row.reference_hash, spec_binding_row.binding_hash,
    actor_id_value
  ) on conflict (organization_id, generation_job_id) do nothing;
  select binding.* into job_binding_row
  from content_factory.generation_job_video_reference_bindings binding
  where binding.organization_id = organization_id_value
    and binding.generation_job_id = job_id_value;
  if job_binding_row.id is null
     or job_binding_row.spec_reference_binding_id <> spec_binding_row.id
     or job_binding_row.binding_hash <> spec_binding_row.binding_hash then
    raise exception using errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;

  update content_factory.generation_jobs job
  set input = job.input || jsonb_build_object(
    'generation_video_reference_context', jsonb_build_object(
      'binding_id', spec_binding_row.id,
      'binding_hash', spec_binding_row.binding_hash,
      'reference_hash', spec_binding_row.reference_hash
    )
  )
  where job.organization_id = organization_id_value and job.id = job_id_value;
  update content_factory.generation_batches batch
  set input = batch.input || jsonb_build_object(
    'generation_video_reference_context', jsonb_build_object(
      'binding_id', spec_binding_row.id,
      'binding_hash', spec_binding_row.binding_hash,
      'reference_hash', spec_binding_row.reference_hash
    )
  )
  where batch.organization_id = organization_id_value and batch.id = batch_id_value;
  return jsonb_set(
    result_value,
    '{job,generation_reference_context}',
    jsonb_build_object(
      'binding_id', spec_binding_row.id,
      'binding_hash', spec_binding_row.binding_hash
    ),
    true
  );
end;
$$;

revoke all on function
  public.contentengine_bind_generation_spec_video_reference(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  public.contentengine_generation_video_reference_lineage(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_bind_generation_spec_video_reference(jsonb)
  to authenticated, service_role;
grant execute on function
  public.contentengine_generation_video_reference_lineage(jsonb)
  to authenticated, service_role;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated, service_role;

comment on function
  public.contentengine_bind_generation_spec_video_reference(jsonb) is
  'Generation-only YouTube lineage: stores exact identity and operator mechanics without changing research provenance or starting a provider.';

notify pgrst, 'reload schema';

commit;

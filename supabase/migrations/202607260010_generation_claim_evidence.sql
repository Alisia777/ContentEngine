begin;

-- Research claims are useful only when their provenance survives the paid
-- generation boundary. Validate the provider-authored shape independently of
-- the browser and attach an immutable snapshot to every generated-media review.

create or replace function
  content_factory_private.valid_research_claim_rows(
    p_safe jsonb,
    p_forbidden jsonb
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  item jsonb;
  source_id_value text;
  normalized_claim text;
  seen_safe text[] := array[]::text[];
  seen_forbidden text[] := array[]::text[];
begin
  if jsonb_typeof(p_safe) <> 'array'
     or jsonb_array_length(p_safe) not between 1 and 14
     or jsonb_typeof(p_forbidden) <> 'array'
     or jsonb_array_length(p_forbidden) not between 1 and 14 then
    return false;
  end if;

  for item in select value from jsonb_array_elements(p_safe) loop
    if jsonb_typeof(item) <> 'object'
       or not (item ?& array['claim', 'basis', 'source_ids'])
       or item - array['claim', 'basis', 'source_ids'] <> '{}'::jsonb
       or jsonb_typeof(item -> 'claim') <> 'string'
       or jsonb_typeof(item -> 'basis') <> 'string'
       or length(item ->> 'claim') not between 3 and 500
       or length(item ->> 'basis') not between 3 and 800
       or item ->> 'claim' <> btrim(item ->> 'claim')
       or item ->> 'basis' <> btrim(item ->> 'basis')
       or item ->> 'claim' ~ '[[:cntrl:]]'
       or item ->> 'basis' ~ '[[:cntrl:]]'
       or jsonb_typeof(item -> 'source_ids') <> 'array'
       or jsonb_array_length(item -> 'source_ids') not between 1 and 8 then
      return false;
    end if;
    normalized_claim := lower(regexp_replace(
      btrim(item ->> 'claim'),
      '\s+',
      ' ',
      'g'
    ));
    if normalized_claim = any(seen_safe) then
      return false;
    end if;
    seen_safe := array_append(seen_safe, normalized_claim);
    if (
      select count(*) from jsonb_array_elements(item -> 'source_ids')
    ) <> (
      select count(distinct source.value)
      from jsonb_array_elements_text(item -> 'source_ids') source(value)
    ) then
      return false;
    end if;
    for source_id_value in
      select value
      from jsonb_array_elements_text(item -> 'source_ids')
    loop
      if source_id_value !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$' then
        return false;
      end if;
    end loop;
  end loop;

  for item in select value from jsonb_array_elements(p_forbidden) loop
    if jsonb_typeof(item) <> 'object'
       or not (
         item ?& array[
           'claim', 'reason', 'safer_alternative', 'source_ids'
         ]
       )
       or item - array[
         'claim', 'reason', 'safer_alternative', 'source_ids'
       ] <> '{}'::jsonb
       or jsonb_typeof(item -> 'claim') <> 'string'
       or jsonb_typeof(item -> 'reason') <> 'string'
       or jsonb_typeof(item -> 'safer_alternative') <> 'string'
       or length(item ->> 'claim') not between 3 and 500
       or length(item ->> 'reason') not between 3 and 800
       or length(item ->> 'safer_alternative') not between 3 and 500
       or item ->> 'claim' <> btrim(item ->> 'claim')
       or item ->> 'reason' <> btrim(item ->> 'reason')
       or item ->> 'safer_alternative' <>
            btrim(item ->> 'safer_alternative')
       or item ->> 'claim' ~ '[[:cntrl:]]'
       or item ->> 'reason' ~ '[[:cntrl:]]'
       or item ->> 'safer_alternative' ~ '[[:cntrl:]]'
       or jsonb_typeof(item -> 'source_ids') <> 'array'
       or jsonb_array_length(item -> 'source_ids') not between 1 and 8 then
      return false;
    end if;
    normalized_claim := lower(regexp_replace(
      btrim(item ->> 'claim'),
      '\s+',
      ' ',
      'g'
    ));
    if normalized_claim = any(seen_forbidden) then
      return false;
    end if;
    seen_forbidden := array_append(seen_forbidden, normalized_claim);
    if (
      select count(*) from jsonb_array_elements(item -> 'source_ids')
    ) <> (
      select count(distinct source.value)
      from jsonb_array_elements_text(item -> 'source_ids') source(value)
    ) then
      return false;
    end if;
    for source_id_value in
      select value
      from jsonb_array_elements_text(item -> 'source_ids')
    loop
      if source_id_value !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$' then
        return false;
      end if;
    end loop;
  end loop;
  return true;
exception when others then
  return false;
end;
$$;

create or replace function
  content_factory_private.valid_approved_research_claims(p_brief jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  source_row jsonb;
  claim_row jsonb;
  source_id_value text;
  source_ids text[] := array[]::text[];
begin
  if jsonb_typeof(p_brief) <> 'object'
     or jsonb_typeof(p_brief -> 'claims') <> 'object'
     or not ((p_brief -> 'claims') ?& array['safe', 'forbidden'])
     or (p_brief -> 'claims') - array['safe', 'forbidden'] <> '{}'::jsonb
     or not content_factory_private.valid_research_claim_rows(
       p_brief #> '{claims,safe}',
       p_brief #> '{claims,forbidden}'
     )
     or jsonb_typeof(p_brief -> 'sources') <> 'array'
     or jsonb_array_length(p_brief -> 'sources') not between 1 and 24 then
    return false;
  end if;

  for source_row in
    select value from jsonb_array_elements(p_brief -> 'sources')
  loop
    if jsonb_typeof(source_row) <> 'object'
       or jsonb_typeof(source_row -> 'id') <> 'string'
       or source_row ->> 'id'
            !~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$'
       or source_row ->> 'id' = any(source_ids) then
      return false;
    end if;
    source_ids := array_append(source_ids, source_row ->> 'id');
  end loop;

  for claim_row in
    select value
    from jsonb_array_elements(
      (p_brief #> '{claims,safe}')
      || (p_brief #> '{claims,forbidden}')
    )
  loop
    for source_id_value in
      select value
      from jsonb_array_elements_text(claim_row -> 'source_ids')
    loop
      if not (source_id_value = any(source_ids)) then
        return false;
      end if;
    end loop;
  end loop;
  return true;
exception when others then
  return false;
end;
$$;

create or replace function
  content_factory_private.valid_generation_claim_evidence_input(
    p_input jsonb
  )
returns boolean
language plpgsql
immutable
set search_path = ''
as $$
declare
  evidence jsonb;
  status_value text;
  source_value text;
  safe_count integer;
  forbidden_count integer;
begin
  if jsonb_typeof(p_input) <> 'object' then
    return false;
  end if;
  if not (p_input ? 'generation_claim_evidence') then
    return true;
  end if;
  evidence := p_input -> 'generation_claim_evidence';
  if jsonb_typeof(evidence) <> 'object'
     or not (
       evidence ?& array[
         'version',
         'status',
         'source',
         'generation_job_id',
         'prompt_hash',
         'creative_brief_draft_id',
         'creative_brief_content_hash',
         'scenario_position',
         'safe_claims',
         'forbidden_claims',
         'safe_claim_count',
         'forbidden_claim_count',
         'evidence_hash'
       ]
     )
     or evidence - array[
       'version',
       'status',
       'source',
       'generation_job_id',
       'prompt_hash',
       'creative_brief_draft_id',
       'creative_brief_content_hash',
       'scenario_position',
       'safe_claims',
       'forbidden_claims',
       'safe_claim_count',
       'forbidden_claim_count',
       'evidence_hash'
     ] <> '{}'::jsonb
     or jsonb_typeof(evidence -> 'version') <> 'string'
     or jsonb_typeof(evidence -> 'status') <> 'string'
     or jsonb_typeof(evidence -> 'source') <> 'string'
     or jsonb_typeof(evidence -> 'generation_job_id') <> 'string'
     or jsonb_typeof(evidence -> 'prompt_hash') <> 'string'
     or jsonb_typeof(evidence -> 'evidence_hash') <> 'string'
     or evidence ->> 'version' <> 'approved_research_claims_v1'
     or evidence ->> 'status' not in ('bound', 'unavailable', 'invalid')
     or evidence ->> 'source' not in (
       'approved_research',
       'baseline',
       'performance_learning',
       'untracked'
     )
     or coalesce(evidence ->> 'generation_job_id', '')
          !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
     or coalesce(evidence ->> 'prompt_hash', '')
          !~ '^[0-9a-f]{64}$'
     or coalesce(evidence ->> 'evidence_hash', '')
          !~ '^[0-9a-f]{64}$'
     or evidence ->> 'evidence_hash' <>
          content_factory_private.json_hash(evidence - 'evidence_hash')
     or jsonb_typeof(evidence -> 'safe_claims') <> 'array'
     or jsonb_typeof(evidence -> 'forbidden_claims') <> 'array'
     or jsonb_typeof(evidence -> 'safe_claim_count') <> 'number'
     or jsonb_typeof(evidence -> 'forbidden_claim_count') <> 'number' then
    return false;
  end if;

  status_value := evidence ->> 'status';
  source_value := evidence ->> 'source';
  safe_count := (evidence ->> 'safe_claim_count')::integer;
  forbidden_count := (evidence ->> 'forbidden_claim_count')::integer;
  if safe_count <> jsonb_array_length(evidence -> 'safe_claims')
     or forbidden_count <>
          jsonb_array_length(evidence -> 'forbidden_claims') then
    return false;
  end if;

  if status_value = 'bound' then
    return source_value = 'approved_research'
      and jsonb_typeof(evidence -> 'creative_brief_draft_id') = 'string'
      and jsonb_typeof(evidence -> 'creative_brief_content_hash') = 'string'
      and coalesce(evidence ->> 'creative_brief_draft_id', '')
        ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      and coalesce(evidence ->> 'creative_brief_content_hash', '')
        ~ '^[0-9a-f]{64}$'
      and jsonb_typeof(evidence -> 'scenario_position') = 'number'
      and (evidence ->> 'scenario_position')::integer between 1 and 3
      and safe_count between 1 and 14
      and forbidden_count between 1 and 14
      and content_factory_private.valid_research_claim_rows(
        evidence -> 'safe_claims',
        evidence -> 'forbidden_claims'
      );
  end if;

  return (
    (status_value = 'invalid' and source_value = 'approved_research')
    or (
      status_value = 'unavailable'
      and source_value in ('baseline', 'performance_learning', 'untracked')
    )
  )
    and evidence -> 'creative_brief_draft_id' = 'null'::jsonb
    and evidence -> 'creative_brief_content_hash' = 'null'::jsonb
    and evidence -> 'scenario_position' = 'null'::jsonb
    and evidence -> 'safe_claims' = '[]'::jsonb
    and evidence -> 'forbidden_claims' = '[]'::jsonb
    and safe_count = 0
    and forbidden_count = 0;
exception when others then
  return false;
end;
$$;

revoke all on function
  content_factory_private.valid_research_claim_rows(jsonb, jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.valid_approved_research_claims(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.valid_generation_claim_evidence_input(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  content_factory_private.valid_research_claim_rows(jsonb, jsonb)
  to service_role;
grant execute on function
  content_factory_private.valid_approved_research_claims(jsonb)
  to service_role;
grant execute on function
  content_factory_private.valid_generation_claim_evidence_input(jsonb)
  to service_role;

alter table content_factory.content_review_runs
  drop constraint if exists content_review_generation_claim_evidence_check;
alter table content_factory.content_review_runs
  add constraint content_review_generation_claim_evidence_check
  check (
    content_factory_private.valid_generation_claim_evidence_input(input)
  ) not valid;
alter table content_factory.content_review_runs
  validate constraint content_review_generation_claim_evidence_check;

-- Move the already-audited implementation behind a short private name. The
-- new public gate rejects invalid research before any provider dispatch.
alter function public.creator_start_real_generation(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_start_real_generation(jsonb)
  rename to creator_start_real_generation_pre_claim_v4;

revoke all on function
  content_factory_private.creator_start_real_generation_pre_claim_v4(jsonb)
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
  organization_id uuid;
  learning_context jsonb;
  research_draft_id_value uuid;
  scenario_position_value integer;
  media_id_value uuid;
  media_product_id uuid;
  research_draft content_factory.creative_brief_drafts%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  learning_context := p_payload -> 'learning_context';
  if jsonb_typeof(learning_context) = 'object'
     and learning_context ->> 'source' = 'approved_research' then
    organization_id :=
      content_factory_private.resolve_organization(p_payload);
    perform content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'operator']
    );
    begin
      research_draft_id_value :=
        (learning_context ->> 'creative_brief_draft_id')::uuid;
      scenario_position_value :=
        (learning_context ->> 'scenario_position')::integer;
      media_id_value := (p_payload #>> '{media_ids,0}')::uuid;
    exception when others then
      raise exception using
        errcode = '22023',
        message = 'generation_research_claim_evidence_invalid';
    end;
    select media.product_id into media_product_id
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.id = media_id_value;
    select draft.* into research_draft
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id
      and draft.id = research_draft_id_value
      and draft.product_id = media_product_id
      and draft.status = 'approved'
      and draft.origin = 'ai';
    if research_draft.id is null
       or scenario_position_value not between 1 and 3
       or jsonb_typeof(research_draft.brief #> array[
         'scenarios',
         (scenario_position_value - 1)::text
       ]) <> 'object'
       or research_draft.content_hash <>
          content_factory_private.json_hash(jsonb_build_object(
            'title', research_draft.title,
            'brief', research_draft.brief,
            'source_ids', research_draft.source_ids,
            'task_blueprint', research_draft.task_blueprint
          ))
       or not content_factory_private.valid_approved_research_claims(
         research_draft.brief
       ) then
      raise exception using
        errcode = '22023',
        message = 'generation_research_claim_evidence_invalid';
    end if;
  end if;
  return
    content_factory_private.creator_start_real_generation_pre_claim_v4(
      p_payload
    );
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;

create or replace function
  content_factory_private.bind_generated_claim_evidence()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  media_row content_factory.media_objects%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  signal_row content_factory.generation_creative_signals%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  generation_job_id_value uuid;
  evidence_status text := 'unavailable';
  evidence_source text := 'untracked';
  safe_claims_value jsonb := '[]'::jsonb;
  forbidden_claims_value jsonb := '[]'::jsonb;
  draft_id_value uuid;
  draft_hash_value text;
  scenario_position_value integer;
  evidence_without_hash jsonb;
begin
  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = new.organization_id
    and media.id = new.media_object_id;
  if media_row.id is null
     or media_row.metadata ->> 'kind' not in (
       'generated_video', 'generated_image'
     ) then
    return new;
  end if;

  begin
    generation_job_id_value :=
      (new.input ->> 'generation_job_id')::uuid;
  exception when others then
    raise exception using
      errcode = '55000',
      message = 'generation_claim_evidence_job_invalid';
  end;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = generation_job_id_value
  for share;
  if job_row.id is null
     or job_row.mode <> 'real'
     or job_row.status <> 'succeeded'
     or job_row.product_id is distinct from media_row.product_id
     or job_row.output ->> 'output_media_id'
          is distinct from media_row.id::text
     or media_row.metadata ->> 'generation_job_id'
          is distinct from job_row.id::text then
    raise exception using
      errcode = '55000',
      message = 'generation_claim_evidence_job_invalid';
  end if;

  select signal.* into signal_row
  from content_factory.generation_creative_signals signal
  where signal.organization_id = new.organization_id
    and signal.generation_job_id = job_row.id
    and signal.product_id = job_row.product_id;
  if signal_row.id is not null then
    evidence_source := signal_row.source;
  end if;

  if evidence_source = 'approved_research' then
    select draft.* into draft_row
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = new.organization_id
      and draft.id = signal_row.creative_brief_draft_id
      and draft.product_id = job_row.product_id
      and draft.status = 'approved'
      and draft.origin = 'ai';
    if draft_row.id is not null
       and signal_row.prompt_hash =
          content_factory_private.json_hash(to_jsonb(
            job_row.input ->> 'prompt_text'
          ))
       and draft_row.content_hash =
          content_factory_private.json_hash(jsonb_build_object(
            'title', draft_row.title,
            'brief', draft_row.brief,
            'source_ids', draft_row.source_ids,
            'task_blueprint', draft_row.task_blueprint
          ))
       and content_factory_private.valid_approved_research_claims(
         draft_row.brief
       ) then
      evidence_status := 'bound';
      safe_claims_value := draft_row.brief #> '{claims,safe}';
      forbidden_claims_value := draft_row.brief #> '{claims,forbidden}';
      draft_id_value := draft_row.id;
      draft_hash_value := draft_row.content_hash;
      scenario_position_value := signal_row.scenario_position;
    else
      evidence_status := 'invalid';
    end if;
  end if;

  evidence_without_hash := jsonb_build_object(
    'version', 'approved_research_claims_v1',
    'status', evidence_status,
    'source', evidence_source,
    'generation_job_id', job_row.id,
    'prompt_hash', content_factory_private.json_hash(to_jsonb(
      job_row.input ->> 'prompt_text'
    )),
    'creative_brief_draft_id', draft_id_value,
    'creative_brief_content_hash', draft_hash_value,
    'scenario_position', scenario_position_value,
    'safe_claims', safe_claims_value,
    'forbidden_claims', forbidden_claims_value,
    'safe_claim_count', jsonb_array_length(safe_claims_value),
    'forbidden_claim_count', jsonb_array_length(forbidden_claims_value)
  );
  new.input := (new.input - 'generation_claim_evidence')
    || jsonb_build_object(
      'generation_claim_evidence',
      evidence_without_hash || jsonb_build_object(
        'evidence_hash',
        content_factory_private.json_hash(evidence_without_hash)
      )
    );
  new.request_hash := content_factory_private.json_hash(new.input);
  if not content_factory_private.valid_generation_claim_evidence_input(
    new.input
  ) then
    raise exception using
      errcode = '55000',
      message = 'generation_claim_evidence_binding_invalid';
  end if;
  return new;
end;
$$;

revoke all on function
  content_factory_private.bind_generated_claim_evidence()
  from public, anon, authenticated, service_role;

drop trigger if exists zz_generated_claim_evidence_guard
  on content_factory.content_review_runs;
create trigger zz_generated_claim_evidence_guard
before insert on content_factory.content_review_runs
for each row execute function
  content_factory_private.bind_generated_claim_evidence();

notify pgrst, 'reload schema';

commit;

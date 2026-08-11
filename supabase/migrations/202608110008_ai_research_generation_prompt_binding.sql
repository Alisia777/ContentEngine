begin;

-- An explicitly selected AI Center recommendation is useful only when the
-- immutable provider prompt contains the same server-owned creative facts.
-- These helpers build a small, model-neutral prompt capsule from the approved
-- recommendation.  The browser may transport the capsule but never derives
-- or edits it.  Human edits have a separate, equally bounded capsule so an
-- edited working draft cannot silently displace the selected evidence.

create or replace function
  content_factory_private.ai_research_prompt_part(
    p_value text,
    p_limit integer,
    p_take_tail boolean default false
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  value_value text;
begin
  if p_limit < 2 or p_limit > 1000 then
    return null;
  end if;
  value_value := btrim(regexp_replace(
    coalesce(p_value, ''),
    E'[ \t\r\n\f\013]+',
    ' ',
    'g'
  ));
  value_value := replace(value_value, '|', '/');
  if value_value = '' then
    return null;
  end if;
  if char_length(value_value) <= p_limit then
    return value_value;
  end if;
  if p_take_tail then
    return '…' || ltrim(right(value_value, p_limit - 1));
  end if;
  return rtrim(left(value_value, p_limit - 1)) || '…';
end;
$$;

revoke all on function
  content_factory_private.ai_research_prompt_part(text, integer, boolean)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_prompt_proof(
    p_recommendation jsonb
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  proof_value jsonb;
  text_value text;
begin
  if jsonb_typeof(p_recommendation) is distinct from 'object' then
    return null;
  end if;
  proof_value := p_recommendation -> 'proof_points';
  if jsonb_typeof(proof_value) = 'array' then
    if jsonb_array_length(proof_value) = 0
       or exists (
         select 1
         from jsonb_array_elements(proof_value) item(value)
         where jsonb_typeof(item.value) <> 'string'
            or btrim(item.value #>> '{}') = ''
       ) then
      return null;
    end if;
    select string_agg(
      regexp_replace(btrim(item.value #>> '{}'), '[[:space:]]+', ' ', 'g'),
      ',' order by item.ordinality
    ) into text_value
    from jsonb_array_elements(proof_value)
      with ordinality item(value, ordinality);
  elsif jsonb_typeof(proof_value) = 'string' then
    text_value := proof_value #>> '{}';
  else
    return null;
  end if;

  -- Compact common factual units without changing their numeric meaning.
  text_value := regexp_replace(
    text_value,
    '([0-9])[[:space:]]+(литров|литра|литры|литр)',
    '\1 л',
    'gi'
  );
  text_value := regexp_replace(
    text_value,
    'окно[[:space:]]+просмотра',
    'окно',
    'gi'
  );
  text_value := regexp_replace(text_value, ',[[:space:]]+', ',', 'g');
  return content_factory_private.ai_research_prompt_part(
    text_value, 55, false
  );
end;
$$;

revoke all on function
  content_factory_private.ai_research_prompt_proof(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_prompt_avoid(
    p_recommendation jsonb
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  avoid_value jsonb;
  text_value text;
begin
  if jsonb_typeof(p_recommendation) is distinct from 'object' then
    return null;
  end if;
  avoid_value := p_recommendation -> 'avoid_claims';
  if jsonb_typeof(avoid_value) = 'array' then
    if jsonb_array_length(avoid_value) = 0
       or exists (
         select 1
         from jsonb_array_elements(avoid_value) item(value)
         where jsonb_typeof(item.value) <> 'string'
            or btrim(item.value #>> '{}') = ''
       ) then
      return null;
    end if;
    select item.value #>> '{}' into text_value
    from jsonb_array_elements(avoid_value)
      with ordinality item(value, ordinality)
    order by case when item.value #>> '{}' ~ '[0-9]' then 0 else 1 end,
             item.ordinality
    limit 1;
  elsif jsonb_typeof(avoid_value) = 'string' then
    text_value := avoid_value #>> '{}';
  else
    return null;
  end if;
  return content_factory_private.ai_research_prompt_part(
    text_value, 32, false
  );
end;
$$;

revoke all on function
  content_factory_private.ai_research_prompt_avoid(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_provider_prompt_fragment(
    p_recommendation jsonb
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  source_text text;
  concept_value text;
  hook_value text;
  cta_value text;
  proof_value text;
  avoid_value text;
  fragment_value text;
begin
  if jsonb_typeof(p_recommendation) is distinct from 'object' then
    return null;
  end if;
  source_text := lower(p_recommendation::text);
  if position(lower('AIResearchSelection/v1') in source_text) > 0
     or position(lower('AIResearchHumanIntent/v1') in source_text) > 0 then
    return null;
  end if;

  -- The tail of a long title normally carries the actual angle while its
  -- prefix carries only the platform name (for example, "YouTube Shorts").
  concept_value := content_factory_private.ai_research_prompt_part(
    coalesce(
      nullif(btrim(p_recommendation ->> 'concept'), ''),
      nullif(btrim(p_recommendation ->> 'title'), ''),
      nullif(btrim(p_recommendation ->> 'key_message'), '')
    ),
    24,
    true
  );
  hook_value := content_factory_private.ai_research_prompt_part(
    p_recommendation ->> 'hook', 18, false
  );
  cta_value := content_factory_private.ai_research_prompt_part(
    p_recommendation ->> 'cta', 64, false
  );
  proof_value := content_factory_private.ai_research_prompt_proof(
    p_recommendation
  );
  avoid_value := content_factory_private.ai_research_prompt_avoid(
    p_recommendation
  );
  if concept_value is null or hook_value is null or cta_value is null
     or proof_value is null or avoid_value is null then
    return null;
  end if;

  fragment_value := 'AIResearchSelection/v1 C=' || concept_value
    || '|H=' || hook_value
    || '|CTA=' || cta_value
    || '|P=' || proof_value
    || '|A=' || avoid_value;
  if char_length(fragment_value) > 240 then
    return null;
  end if;
  return fragment_value;
end;
$$;

revoke all on function
  content_factory_private.ai_research_provider_prompt_fragment(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_human_intent_fragment(
    p_editable_intent text
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  source_value text := replace(
    replace(coalesce(p_editable_intent, ''), E'\r\n', E'\n'),
    E'\r', E'\n'
  );
  source_lower text;
  current_section text;
  line_record record;
  line_value text;
  label_value text;
  inline_value text;
  concept_value text := '';
  hook_value text := '';
  cta_value text := '';
  proof_value text := '';
  avoid_value text := '';
  seen_concept integer := 0;
  seen_hook integer := 0;
  seen_cta integer := 0;
  seen_proof integer := 0;
  seen_avoid integer := 0;
  fragment_value text;
begin
  source_value := regexp_replace(
    regexp_replace(source_value, E'^[ \t\r\n\f\013]+', ''),
    E'[ \t\r\n\f\013]+$',
    ''
  );
  source_lower := lower(source_value);
  if position(lower('AIResearchSelection/v1') in source_lower) > 0
     or position(lower('AIResearchHumanIntent/v1') in source_lower) > 0 then
    return null;
  end if;

  for line_record in
    select item.value, item.ordinality
    from regexp_split_to_table(source_value, E'\n')
      with ordinality item(value, ordinality)
    order by item.ordinality
  loop
    line_value := btrim(line_record.value);
    label_value := upper(split_part(line_value, ':', 1));
    inline_value := case when position(':' in line_value) > 0
      then btrim(substr(line_value, position(':' in line_value) + 1))
      else '' end;

    if position(':' in line_value) > 0 and label_value in (
      'ТОВАР', 'КОНЦЕПЦИЯ', 'ХУК',
      'КЛЮЧЕВОЕ СООБЩЕНИЕ', 'АУДИТОРИЯ',
      'РЕПЛИКА / СЮЖЕТ', 'КАДРЫ', 'ВИЗУАЛ',
      'CTA', 'ДОКАЗАТЕЛЬСТВА',
      'НЕ ОБЕЩАТЬ / УЧЕСТЬ'
    ) then
      current_section := label_value;
      if label_value = 'КОНЦЕПЦИЯ' then
        seen_concept := seen_concept + 1;
        concept_value := inline_value;
      elsif label_value = 'ХУК' then
        seen_hook := seen_hook + 1;
        hook_value := inline_value;
      elsif label_value = 'CTA' then
        seen_cta := seen_cta + 1;
        cta_value := inline_value;
      elsif label_value = 'ДОКАЗАТЕЛЬСТВА' then
        seen_proof := seen_proof + 1;
        proof_value := inline_value;
      elsif label_value = 'НЕ ОБЕЩАТЬ / УЧЕСТЬ' then
        seen_avoid := seen_avoid + 1;
        avoid_value := inline_value;
      end if;
      continue;
    end if;

    if line_value = '' then
      continue;
    end if;
    if current_section = 'КОНЦЕПЦИЯ' then
      concept_value := concat_ws(' ', nullif(concept_value, ''), line_value);
    elsif current_section = 'ХУК' then
      hook_value := concat_ws(' ', nullif(hook_value, ''), line_value);
    elsif current_section = 'CTA' then
      cta_value := concat_ws(' ', nullif(cta_value, ''), line_value);
    elsif current_section = 'ДОКАЗАТЕЛЬСТВА' then
      proof_value := concat_ws(' ', nullif(proof_value, ''), line_value);
    elsif current_section = 'НЕ ОБЕЩАТЬ / УЧЕСТЬ' then
      avoid_value := concat_ws(' ', nullif(avoid_value, ''), line_value);
    end if;
  end loop;

  if seen_concept <> 1 or seen_hook <> 1 or seen_cta <> 1
     or seen_proof <> 1 or seen_avoid <> 1 then
    return null;
  end if;
  concept_value := content_factory_private.ai_research_prompt_part(
    concept_value, 16, false
  );
  hook_value := content_factory_private.ai_research_prompt_part(
    hook_value, 16, false
  );
  cta_value := content_factory_private.ai_research_prompt_part(
    cta_value, 24, false
  );
  proof_value := content_factory_private.ai_research_prompt_part(
    proof_value, 16, false
  );
  avoid_value := content_factory_private.ai_research_prompt_part(
    avoid_value, 20, false
  );
  if concept_value is null or hook_value is null or cta_value is null
     or proof_value is null or avoid_value is null then
    return null;
  end if;

  fragment_value := 'AIResearchHumanIntent/v1 C=' || concept_value
    || '|H=' || hook_value
    || '|CTA=' || cta_value
    || '|P=' || proof_value
    || '|A=' || avoid_value;
  if char_length(fragment_value) > 150 then
    return null;
  end if;
  return fragment_value;
end;
$$;

revoke all on function
  content_factory_private.ai_research_human_intent_fragment(text)
  from public, anon, authenticated, service_role;

-- Rebuild the exact recommendation envelope additively.  A legacy or
-- incomplete recommendation remains visible, but its NULL fragment makes any
-- attempt to bind or start it fail closed.
create or replace function
  content_factory_private.ai_research_recommendation_snapshot(
    p_organization_id uuid,
    p_project_id uuid,
    p_selection_id uuid,
    p_recommendation_position smallint
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  selection_row content_factory.ai_research_learning_selections%rowtype;
  recommendation_value jsonb;
  provider_prompt_fragment_value text;
begin
  select selection.* into selection_row
  from content_factory.ai_research_learning_selections selection
  where selection.organization_id = p_organization_id
    and selection.project_id = p_project_id
    and selection.id = p_selection_id
    and selection.decision = 'approve'
    and p_recommendation_position = any(
      selection.selected_scenario_positions
    );
  if selection_row.id is null then
    return null;
  end if;

  select candidate.value into recommendation_value
  from jsonb_array_elements(selection_row.recommendations)
    with ordinality candidate(value, ordinality)
  where case
    when coalesce(candidate.value ->> 'position', '') ~ '^[1-3]$'
      then (candidate.value ->> 'position')::smallint
    else candidate.ordinality::smallint
  end = p_recommendation_position
  limit 1;
  if jsonb_typeof(recommendation_value) is distinct from 'object' then
    return null;
  end if;
  provider_prompt_fragment_value := content_factory_private
    .ai_research_provider_prompt_fragment(recommendation_value);

  return jsonb_build_object(
    'selection_id', selection_row.id,
    'selection_hash', selection_row.selection_hash,
    'receipt_id', selection_row.receipt_id,
    'run_id', selection_row.run_id,
    'draft_id', selection_row.draft_id,
    'project_id', selection_row.project_id,
    'product_id', selection_row.product_id,
    'product_category', selection_row.product_category,
    'source_product_name', selection_row.product_name,
    'source_product_sku', selection_row.product_sku,
    'recommendation_position', p_recommendation_position,
    'recommendation_hash',
      content_factory_private.json_hash(recommendation_value),
    'provider_prompt_fragment_version', case
      when provider_prompt_fragment_value is null then null
      else 'ai-research-provider-fragment-v1'
    end,
    'provider_prompt_fragment', provider_prompt_fragment_value,
    'provider_prompt_fragment_hash', case
      when provider_prompt_fragment_value is null then null
      else content_factory_private.raw_text_sha256(
        provider_prompt_fragment_value
      )
    end,
    'scope_match', 'selected_product_advisory',
    'match_basis', 'server_verified_selection',
    'can_auto_apply', false,
    'preset', content_factory_private.ai_research_generation_preset(
      selection_row.product_category,
      recommendation_value
    ),
    'recommendation', recommendation_value,
    'selected_at', selection_row.selected_at,
    'event_cursor', selection_row.event_cursor
  );
end;
$$;

revoke all on function
  content_factory_private.ai_research_recommendation_snapshot(
    uuid, uuid, uuid, smallint
  ) from public, anon, authenticated, service_role;

alter table content_factory.generation_spec_ai_research_bindings
  add column if not exists provider_prompt_fragment_version text,
  add column if not exists provider_prompt_fragment text,
  add column if not exists provider_prompt_fragment_hash text,
  add column if not exists human_intent_fragment_version text,
  add column if not exists human_intent_fragment text,
  add column if not exists human_intent_fragment_hash text,
  add column if not exists compiled_prompt_hash text,
  add column if not exists prompt_binding_proof_hash text;

alter table content_factory.generation_spec_ai_research_bindings
  drop constraint if exists generation_spec_ai_research_prompt_proof_check;
alter table content_factory.generation_spec_ai_research_bindings
  add constraint generation_spec_ai_research_prompt_proof_check check (
    (
      provider_prompt_fragment_version is null
      and provider_prompt_fragment is null
      and provider_prompt_fragment_hash is null
      and human_intent_fragment_version is null
      and human_intent_fragment is null
      and human_intent_fragment_hash is null
      and compiled_prompt_hash is null
      and prompt_binding_proof_hash is null
    )
    or (
      provider_prompt_fragment_version is not null
      and provider_prompt_fragment is not null
      and provider_prompt_fragment_hash is not null
      and human_intent_fragment_version is not null
      and human_intent_fragment is not null
      and human_intent_fragment_hash is not null
      and compiled_prompt_hash is not null
      and prompt_binding_proof_hash is not null
      and provider_prompt_fragment_version =
        'ai-research-provider-fragment-v1'
      and char_length(provider_prompt_fragment) between 1 and 240
      and position(
        'AIResearchSelection/v1 C=' in provider_prompt_fragment
      ) = 1
      and provider_prompt_fragment_hash =
        content_factory_private.raw_text_sha256(
          provider_prompt_fragment
        )
      and human_intent_fragment_version =
        'ai-research-human-intent-v1'
      and char_length(human_intent_fragment) between 1 and 150
      and position(
        'AIResearchHumanIntent/v1 C=' in human_intent_fragment
      ) = 1
      and human_intent_fragment_hash =
        content_factory_private.raw_text_sha256(human_intent_fragment)
      and compiled_prompt_hash ~ '^[0-9a-f]{64}$'
      and prompt_binding_proof_hash =
        content_factory_private.raw_text_sha256(
          provider_prompt_fragment || E'\n' || human_intent_fragment
        )
    )
  );

-- The public project-ACL wrapper installed by 202608100003 remains byte-for-
-- byte unchanged.  Replacing only its preserved delegate keeps ACL and legacy
-- validation order while making the exact immutable prompt a prerequisite for
-- a new append-only binding.
create or replace function
  content_factory_private
    .contentengine_bind_generation_spec_ai_research_pre_project_acl(
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
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  selection_id_value uuid;
  position_value smallint;
  product_id_value uuid;
  spec_row content_factory.generation_spec_versions%rowtype;
  selection_row content_factory.ai_research_learning_selections%rowtype;
  recommendation_value jsonb;
  expected_provider_fragment_value text;
  expected_human_fragment_value text;
  provider_marker_count_value integer;
  provider_fragment_count_value integer;
  human_marker_count_value integer;
  human_fragment_count_value integer;
  compiled_prompt_hash_value text;
  prompt_binding_proof_hash_value text;
  existing_row content_factory.generation_spec_ai_research_bindings%rowtype;
  binding_row content_factory.generation_spec_ai_research_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'spec_id', 'spec_version',
    'spec_hash', 'selection_id', 'recommendation_position', 'confirmation'
  ]::text[] <> '{}'::jsonb
     or not (p_payload ?& array[
       'project_id', 'spec_id', 'spec_version', 'spec_hash',
       'selection_id', 'recommendation_position', 'confirmation'
     ]::text[]) then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_payload_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'confirmation') <> 'boolean'
     or (p_payload ->> 'confirmation')::boolean is not true then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_confirmation_required';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  selection_id_value := content_factory_private.require_uuid(
    p_payload, 'selection_id'
  );
  if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[0-9]{1,6}$'
     or (p_payload ->> 'spec_version')::integer not between 1 and 100000 then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_version_invalid';
  end if;
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  if spec_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_hash_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'recommendation_position') <> 'number'
     or coalesce(p_payload ->> 'recommendation_position', '')
          !~ '^[1-3]$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_position_invalid';
  end if;
  position_value := (p_payload ->> 'recommendation_position')::smallint;

  product_id_value :=
    content_factory_private.require_generation_spec_project_v49(
      organization_id_value,
      project_id_value,
      spec_id_value,
      spec_version_value,
      spec_hash_value,
      null
    );
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share;

  select selection.* into selection_row
  from content_factory.ai_research_learning_selections selection
  where selection.organization_id = organization_id_value
    and selection.id = selection_id_value
  for share;
  if selection_row.id is null
     or selection_row.project_id <> project_id_value
     or selection_row.product_id is null
     or selection_row.product_id <> product_id_value
     or selection_row.product_category <> spec_row.product_category
     or selection_row.decision <> 'approve'
     or not (
       position_value = any(selection_row.selected_scenario_positions)
     ) then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_ai_research_binding_scope_mismatch';
  end if;

  select candidate.value into recommendation_value
  from jsonb_array_elements(selection_row.recommendations)
    with ordinality candidate(value, ordinality)
  where case
    when coalesce(candidate.value ->> 'position', '') ~ '^[1-3]$'
      then (candidate.value ->> 'position')::smallint
    else candidate.ordinality::smallint
  end = position_value
  limit 1;
  if jsonb_typeof(recommendation_value) is distinct from 'object' then
    raise exception using
      errcode = '42501',
      message = 'generation_spec_ai_research_binding_recommendation_missing';
  end if;

  expected_provider_fragment_value := content_factory_private
    .ai_research_provider_prompt_fragment(recommendation_value);
  expected_human_fragment_value := content_factory_private
    .ai_research_human_intent_fragment(spec_row.editable_intent);
  if expected_provider_fragment_value is null
     or expected_human_fragment_value is null
     or char_length(expected_provider_fragment_value)
          + char_length(expected_human_fragment_value) > 390 then
    raise exception using
      errcode = '22023',
      message = 'ai_research_prompt_budget_exceeded';
  end if;

  provider_marker_count_value := (
    char_length(lower(spec_row.compiled_prompt))
    - char_length(replace(
        lower(spec_row.compiled_prompt), lower('AIResearchSelection/v1'), ''
      ))
    ) / char_length('AIResearchSelection/v1');
  provider_fragment_count_value := (
    char_length(spec_row.compiled_prompt)
    - char_length(replace(
        spec_row.compiled_prompt, expected_provider_fragment_value, ''
      ))
  ) / char_length(expected_provider_fragment_value);
  human_marker_count_value := (
    char_length(lower(spec_row.compiled_prompt))
    - char_length(replace(
        lower(spec_row.compiled_prompt), lower('AIResearchHumanIntent/v1'), ''
      ))
    ) / char_length('AIResearchHumanIntent/v1');
  human_fragment_count_value := (
    char_length(spec_row.compiled_prompt)
    - char_length(replace(
        spec_row.compiled_prompt, expected_human_fragment_value, ''
      ))
  ) / char_length(expected_human_fragment_value);
  compiled_prompt_hash_value := content_factory_private.raw_text_sha256(
    spec_row.compiled_prompt
  );
  prompt_binding_proof_hash_value := content_factory_private.raw_text_sha256(
    expected_provider_fragment_value || E'\n'
      || expected_human_fragment_value
  );
  if provider_marker_count_value <> 1
     or provider_fragment_count_value <> 1
     or human_marker_count_value <> 1
     or human_fragment_count_value <> 1
     or spec_row.prompt_hash <> compiled_prompt_hash_value then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_ai_research_prompt_binding_invalid';
  end if;

  select binding.* into existing_row
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value;
  if existing_row.id is not null then
    if existing_row.spec_hash = spec_hash_value
       and existing_row.selection_id = selection_id_value
       and existing_row.recommendation_position = position_value then
      if existing_row.provider_prompt_fragment_version is null then
        raise exception using
          errcode = '55000',
          message = 'generation_spec_ai_research_binding_legacy';
      end if;
      if existing_row.provider_prompt_fragment_version <>
           'ai-research-provider-fragment-v1'
         or existing_row.provider_prompt_fragment is distinct from
           expected_provider_fragment_value
         or existing_row.provider_prompt_fragment_hash is distinct from
           content_factory_private.raw_text_sha256(
             expected_provider_fragment_value
           )
         or existing_row.human_intent_fragment_version <>
           'ai-research-human-intent-v1'
         or existing_row.human_intent_fragment is distinct from
           expected_human_fragment_value
         or existing_row.human_intent_fragment_hash is distinct from
           content_factory_private.raw_text_sha256(
             expected_human_fragment_value
           )
         or existing_row.compiled_prompt_hash is distinct from
           compiled_prompt_hash_value
         or existing_row.prompt_binding_proof_hash is distinct from
           prompt_binding_proof_hash_value then
        raise exception using
          errcode = '23505',
          message = 'generation_spec_ai_research_binding_conflict';
      end if;
      binding_row := existing_row;
    else
      raise exception using
        errcode = '23505',
        message = 'generation_spec_ai_research_binding_conflict';
    end if;
  else
    insert into content_factory.generation_spec_ai_research_bindings (
      organization_id, project_id, spec_id, spec_version, spec_hash,
      selection_id, selection_hash, recommendation_position,
      recommendation_snapshot, recommendation_hash, applied_by,
      provider_prompt_fragment_version, provider_prompt_fragment,
      provider_prompt_fragment_hash, human_intent_fragment_version,
      human_intent_fragment, human_intent_fragment_hash,
      compiled_prompt_hash, prompt_binding_proof_hash
    ) values (
      organization_id_value, project_id_value, spec_id_value,
      spec_version_value, spec_hash_value, selection_id_value,
      selection_row.selection_hash, position_value, recommendation_value,
      content_factory_private.json_hash(recommendation_value), user_id,
      'ai-research-provider-fragment-v1',
      expected_provider_fragment_value,
      content_factory_private.raw_text_sha256(
        expected_provider_fragment_value
      ),
      'ai-research-human-intent-v1',
      expected_human_fragment_value,
      content_factory_private.raw_text_sha256(
        expected_human_fragment_value
      ),
      compiled_prompt_hash_value,
      prompt_binding_proof_hash_value
    ) returning * into binding_row;
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-ai-research-binding-v2',
    'binding', jsonb_build_object(
      'id', binding_row.id,
      'project_id', binding_row.project_id,
      'spec_id', binding_row.spec_id,
      'spec_version', binding_row.spec_version,
      'spec_hash', binding_row.spec_hash,
      'selection_id', binding_row.selection_id,
      'selection_hash', binding_row.selection_hash,
      'recommendation_position', binding_row.recommendation_position,
      'recommendation_hash', binding_row.recommendation_hash,
      'provider_prompt_fragment_version',
        binding_row.provider_prompt_fragment_version,
      'provider_prompt_fragment', binding_row.provider_prompt_fragment,
      'provider_prompt_fragment_hash',
        binding_row.provider_prompt_fragment_hash,
      'human_intent_fragment_version',
        binding_row.human_intent_fragment_version,
      'human_intent_fragment', binding_row.human_intent_fragment,
      'human_intent_fragment_hash', binding_row.human_intent_fragment_hash,
      'compiled_prompt_hash', binding_row.compiled_prompt_hash,
      'prompt_binding_proof_hash', binding_row.prompt_binding_proof_hash,
      'legacy', false,
      'scope_match', 'exact_product',
      'applied_by', binding_row.applied_by,
      'applied_at', binding_row.applied_at
    ),
    'contract', jsonb_build_object(
      'append_only', true,
      'human_editable_spec_preserved', true,
      'server_owned_provider_fragment', true,
      'provider_fragment_exactly_once', true,
      'human_intent_fragment_exactly_once', true,
      'provider_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  content_factory_private
    .contentengine_bind_generation_spec_ai_research_pre_project_acl(jsonb)
  from public, anon, authenticated, service_role;

-- Keep the public ACL wrapper unchanged and make only its preserved read
-- delegate additive.  Legacy rows remain readable as legacy=true/null proof,
-- but the paid-start wrapper below will never accept them.
create or replace function
  content_factory_private
    .contentengine_generation_spec_ai_research_binding_pre_acl_v423(
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
  organization_id_value uuid;
  project_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  binding_row content_factory.generation_spec_ai_research_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'spec_id', 'spec_version', 'spec_hash'
  ]::text[] <> '{}'::jsonb
     or not (p_payload ?& array[
       'project_id', 'spec_id', 'spec_version', 'spec_hash'
     ]::text[]) then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_read_payload_invalid';
  end if;
  user_id := auth.uid();
  if user_id is null then
    raise exception using
      errcode = '42501', message = 'authentication_required';
  end if;
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  if jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[0-9]{1,6}$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_binding_version_invalid';
  end if;
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  perform content_factory_private.require_generation_spec_project_v49(
    organization_id_value, project_id_value, spec_id_value,
    spec_version_value, spec_hash_value, null
  );

  select binding.* into binding_row
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-ai-research-binding-v2',
    'binding', case when binding_row.id is null then null else
      jsonb_build_object(
        'id', binding_row.id,
        'project_id', binding_row.project_id,
        'spec_id', binding_row.spec_id,
        'spec_version', binding_row.spec_version,
        'spec_hash', binding_row.spec_hash,
        'selection_id', binding_row.selection_id,
        'selection_hash', binding_row.selection_hash,
        'recommendation_position', binding_row.recommendation_position,
        'recommendation_hash', binding_row.recommendation_hash,
        'provider_prompt_fragment_version',
          binding_row.provider_prompt_fragment_version,
        'provider_prompt_fragment', binding_row.provider_prompt_fragment,
        'provider_prompt_fragment_hash',
          binding_row.provider_prompt_fragment_hash,
        'human_intent_fragment_version',
          binding_row.human_intent_fragment_version,
        'human_intent_fragment', binding_row.human_intent_fragment,
        'human_intent_fragment_hash',
          binding_row.human_intent_fragment_hash,
        'compiled_prompt_hash', binding_row.compiled_prompt_hash,
        'prompt_binding_proof_hash', binding_row.prompt_binding_proof_hash,
        'legacy', binding_row.provider_prompt_fragment_version is null,
        'applied_by', binding_row.applied_by,
        'applied_at', binding_row.applied_at
      ) end,
    'contract', jsonb_build_object(
      'server_backed', true,
      'legacy_bindings_cannot_start', true,
      'provider_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  content_factory_private
    .contentengine_generation_spec_ai_research_binding_pre_acl_v423(jsonb)
  from public, anon, authenticated, service_role;

-- Preserve the complete installed paid-start chain (through the v54 video
-- reference wrapper) before adding the final AI prompt proof.  Delegating
-- first is deliberate: every legacy validation keeps its historical error
-- precedence.  The Edge Function can contact a provider only after this RPC
-- returns, so any later proof error rolls the delegated job and reservation
-- back in the same transaction.
do $preserve_generation_ai_research_prompt_v55$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_ai_research_prompt_v55(jsonb)'
  ) is null then
    alter function public.creator_start_real_generation(jsonb)
      rename to creator_start_real_generation_pre_ai_research_prompt_v55;
    alter function
      public.creator_start_real_generation_pre_ai_research_prompt_v55(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_generation_ai_research_prompt_v55$;

revoke all on function
  content_factory_private
    .creator_start_real_generation_pre_ai_research_prompt_v55(jsonb)
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
  result_value jsonb;
  organization_id_value uuid;
  project_id_value uuid;
  context_value jsonb;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  binding_row content_factory.generation_spec_ai_research_bindings%rowtype;
  binding_count_value integer := 0;
  provider_marker_count_value integer := 0;
  provider_fragment_count_value integer := 0;
  human_marker_count_value integer := 0;
  human_fragment_count_value integer := 0;
  expected_provider_fragment_value text;
  expected_human_fragment_value text;
  expected_provider_hash_value text;
  expected_human_hash_value text;
  expected_prompt_hash_value text;
  expected_proof_hash_value text;
begin
  -- Do not parse, normalize or reject any AI state before the full legacy
  -- chain has returned.  An exception below unwinds every delegated write.
  result_value := content_factory_private
    .creator_start_real_generation_pre_ai_research_prompt_v55(p_payload);

  p_payload := content_factory_private.require_payload(p_payload);
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  context_value := p_payload -> 'generation_spec_context';
  begin
    spec_id_value := (context_value ->> 'spec_id')::uuid;
    spec_version_value := (context_value ->> 'spec_version')::integer;
  exception
    when invalid_text_representation or numeric_value_out_of_range
      or null_value_not_allowed then
      raise exception using
        errcode = '55000',
        message = 'generation_ai_research_prompt_binding_invalid';
  end;
  spec_hash_value := lower(btrim(coalesce(
    context_value ->> 'spec_hash', ''
  )));

  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share;
  if spec_row.version_id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_prompt_binding_invalid';
  end if;

  provider_marker_count_value := (
    char_length(lower(spec_row.compiled_prompt))
    - char_length(replace(
        lower(spec_row.compiled_prompt), lower('AIResearchSelection/v1'), ''
      ))
    ) / char_length('AIResearchSelection/v1');
  human_marker_count_value := (
    char_length(lower(spec_row.compiled_prompt))
    - char_length(replace(
        lower(spec_row.compiled_prompt), lower('AIResearchHumanIntent/v1'), ''
      ))
    ) / char_length('AIResearchHumanIntent/v1');

  select count(*)::integer into binding_count_value
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value;
  if binding_count_value = 1 then
    select binding.* into binding_row
    from content_factory.generation_spec_ai_research_bindings binding
    where binding.organization_id = organization_id_value
      and binding.project_id = project_id_value
      and binding.spec_id = spec_id_value
      and binding.spec_version = spec_version_value
      and binding.spec_hash = spec_hash_value
    for share;
  end if;

  if provider_marker_count_value not between 0 and 1
     or human_marker_count_value not between 0 and 1
     or provider_marker_count_value <> human_marker_count_value
     or binding_count_value not between 0 and 1 then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_prompt_binding_invalid';
  end if;

  -- Manual generation remains completely optional: no marker and no binding
  -- is the valid manual state.  Any row without new proof is a legacy binding
  -- and may be read for audit, but it can never cross the paid-start boundary.
  if provider_marker_count_value = 0 then
    if binding_count_value = 0 then
      return result_value;
    end if;
    if binding_row.provider_prompt_fragment_version is null then
      raise exception using
        errcode = '55000',
        message = 'generation_ai_research_legacy_binding_start_forbidden';
    end if;
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_prompt_binding_invalid';
  end if;

  if binding_count_value <> 1 then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_prompt_binding_invalid';
  end if;
  if binding_row.provider_prompt_fragment_version is null then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_legacy_binding_start_forbidden';
  end if;

  expected_provider_fragment_value := content_factory_private
    .ai_research_provider_prompt_fragment(
      binding_row.recommendation_snapshot
    );
  expected_human_fragment_value := content_factory_private
    .ai_research_human_intent_fragment(spec_row.editable_intent);
  if expected_provider_fragment_value is null
     or expected_human_fragment_value is null
     or char_length(expected_provider_fragment_value)
          + char_length(expected_human_fragment_value) > 390 then
    raise exception using
      errcode = '22023',
      message = 'ai_research_prompt_budget_exceeded';
  end if;

  expected_provider_hash_value := content_factory_private.raw_text_sha256(
    expected_provider_fragment_value
  );
  expected_human_hash_value := content_factory_private.raw_text_sha256(
    expected_human_fragment_value
  );
  expected_prompt_hash_value := content_factory_private.raw_text_sha256(
    spec_row.compiled_prompt
  );
  expected_proof_hash_value := content_factory_private.raw_text_sha256(
    expected_provider_fragment_value || E'\n'
      || expected_human_fragment_value
  );
  provider_fragment_count_value := (
    char_length(spec_row.compiled_prompt)
    - char_length(replace(
        spec_row.compiled_prompt, expected_provider_fragment_value, ''
      ))
  ) / char_length(expected_provider_fragment_value);
  human_fragment_count_value := (
    char_length(spec_row.compiled_prompt)
    - char_length(replace(
        spec_row.compiled_prompt, expected_human_fragment_value, ''
      ))
  ) / char_length(expected_human_fragment_value);

  if provider_fragment_count_value <> 1
     or human_fragment_count_value <> 1
     or binding_row.provider_prompt_fragment_version <>
       'ai-research-provider-fragment-v1'
     or binding_row.provider_prompt_fragment is distinct from
       expected_provider_fragment_value
     or binding_row.provider_prompt_fragment_hash is distinct from
       expected_provider_hash_value
     or binding_row.human_intent_fragment_version <>
       'ai-research-human-intent-v1'
     or binding_row.human_intent_fragment is distinct from
       expected_human_fragment_value
     or binding_row.human_intent_fragment_hash is distinct from
       expected_human_hash_value
     or binding_row.compiled_prompt_hash is distinct from
       expected_prompt_hash_value
     or binding_row.prompt_binding_proof_hash is distinct from
       expected_proof_hash_value
     or spec_row.prompt_hash <> expected_prompt_hash_value then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_prompt_binding_invalid';
  end if;

  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated, service_role;

comment on function
  public.contentengine_bind_generation_spec_ai_research(jsonb) is
  'Project-ACL gateway to an append-only exact-product AI recommendation binding. The immutable spec must contain the server-owned selection capsule and current human-intent capsule exactly once; no provider or paid call starts.';
comment on function public.creator_start_real_generation(jsonb) is
  'Runs the complete preserved paid-start validation chain first, then enforces a bijection between AI prompt markers and one nonlegacy exact binding. Any mismatch rolls back delegated job and spend state before Edge can contact a provider.';
comment on column
  content_factory.generation_spec_ai_research_bindings
    .provider_prompt_fragment is
  'Server-derived immutable provider capsule for the explicitly selected AI Center recommendation; NULL only on legacy rows.';
comment on column
  content_factory.generation_spec_ai_research_bindings
    .human_intent_fragment is
  'Bounded server-recomputed capsule of the five current labelled human-edit sections; NULL only on legacy rows.';

notify pgrst, 'reload schema';

commit;

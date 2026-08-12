begin;

-- An AI-selected Seedance brief has one human-editable spoken section.  The
-- browser may compile it, but PostgreSQL independently derives the exact raw
-- line, binds it to the immutable spec and verifies the provider sentence at
-- both free bind and paid start.  Manual generation and non-speech models do
-- not acquire this requirement.
create or replace function
  content_factory_private.ai_research_seedance_spoken_word_limit(
    p_duration_seconds integer
  )
returns integer
language sql
immutable
set search_path = ''
as $$
  select case
    when p_duration_seconds in (4, 8, 12, 15) then greatest(
      10,
      least(42, floor(p_duration_seconds * 22.0 / 8.0)::integer)
    )
    else null
  end;
$$;

revoke all on function
  content_factory_private.ai_research_seedance_spoken_word_limit(integer)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_seedance_speech_has_control(
    p_value text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select exists (
    select 1
    from generate_series(1, char_length(coalesce(p_value, ''))) item(position)
    where ascii(substr(p_value, item.position, 1)) between 0 and 31
       or ascii(substr(p_value, item.position, 1)) between 127 and 159
  );
$$;

revoke all on function
  content_factory_private.ai_research_seedance_speech_has_control(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_seedance_source_has_unsafe_control(
    p_value text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select exists (
    select 1
    from generate_series(1, char_length(coalesce(p_value, ''))) item(position)
    where ascii(substr(p_value, item.position, 1)) between 0 and 9
       or ascii(substr(p_value, item.position, 1)) in (11, 12)
       or ascii(substr(p_value, item.position, 1)) between 14 and 31
       or ascii(substr(p_value, item.position, 1)) between 127 and 159
  );
$$;

revoke all on function
  content_factory_private.ai_research_seedance_source_has_unsafe_control(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_seedance_has_default_ignorable(
    p_value text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select exists (
    select 1
    from generate_series(1, char_length(coalesce(p_value, ''))) item(position)
    cross join lateral (
      select ascii(substr(p_value, item.position, 1)) as codepoint
    ) character
    where character.codepoint in (
      173, 847, 1564, 12644, 65279, 65440
    )
       or character.codepoint between 4447 and 4448
       or character.codepoint between 6068 and 6069
       or character.codepoint between 6155 and 6159
       or character.codepoint between 8203 and 8207
       or character.codepoint between 8234 and 8238
       or character.codepoint between 8288 and 8303
       or character.codepoint between 65024 and 65039
       or character.codepoint between 65520 and 65528
       or character.codepoint between 113824 and 113827
       or character.codepoint between 119155 and 119162
       or character.codepoint between 917504 and 921599
  );
$$;

revoke all on function
  content_factory_private.ai_research_seedance_has_default_ignorable(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_seedance_structured_speech_count(
    p_value text
  )
returns integer
language sql
immutable
set search_path = ''
as $$
  with whitespace(chars) as (
    values (U&'\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000')
  )
  select count(*)::integer
  from whitespace,
    regexp_matches(
      translate(
        coalesce(p_value, ''),
        whitespace.chars,
        repeat(' ', char_length(whitespace.chars))
      ),
      'РЕПЛИКА[[:space:]]*/[[:space:]]*СЮЖЕТ[[:space:]]*:',
      'gi'
    );
$$;

revoke all on function
  content_factory_private.ai_research_seedance_structured_speech_count(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_seedance_spoken_line(
    p_editable_intent text,
    p_duration_seconds integer
  )
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  raw_source_value text := coalesce(p_editable_intent, '');
  source_value text;
  unicode_space_chars text := U&'\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000';
  raw_non_ascii_space_chars text;
  trim_chars text;
  line_record record;
  raw_line_value text;
  line_value text;
  outer_ascii_line_value text;
  label_value text;
  raw_inline_value text;
  inline_value text;
  current_section text;
  spoken_value text := '';
  spoken_seen integer := 0;
  spoken_token_count integer := 0;
  word_count_value integer := 0;
  word_limit_value integer;
begin
  word_limit_value := content_factory_private
    .ai_research_seedance_spoken_word_limit(p_duration_seconds);
  if word_limit_value is null or raw_source_value = ''
     or content_factory_private
       .ai_research_seedance_source_has_unsafe_control(raw_source_value)
     or content_factory_private
       .ai_research_seedance_has_default_ignorable(raw_source_value) then
    return null;
  end if;
  source_value := replace(
    replace(raw_source_value, E'\r\n', E'\n'), E'\r', E'\n'
  );
  trim_chars := E' \t\f\013' || unicode_space_chars;
  raw_non_ascii_space_chars := unicode_space_chars || U&'\FEFF';
  spoken_token_count := content_factory_private
    .ai_research_seedance_structured_speech_count(raw_source_value);

  if spoken_token_count <> 1
     or position(lower('AIResearchSelection/v1') in lower(source_value)) > 0
     or position(lower('AIResearchHumanIntent/v1') in lower(source_value)) > 0
     or position(lower('AIResearchSeedanceSpeech/v1') in lower(source_value)) > 0 then
    return null;
  end if;

  for line_record in
    select item.value, item.ordinality
    from regexp_split_to_table(source_value, E'\n')
      with ordinality item(value, ordinality)
    order by item.ordinality
  loop
    raw_line_value := line_record.value;
    line_value := btrim(raw_line_value, trim_chars);
    outer_ascii_line_value := btrim(raw_line_value, ' ');
    if line_value = '' then
      continue;
    end if;
    label_value := upper(regexp_replace(
      translate(
        btrim(split_part(line_value, ':', 1), trim_chars),
        unicode_space_chars,
        repeat(' ', char_length(unicode_space_chars))
      ),
      E'[ \t\f\013]+', ' ', 'g'
    ));
    raw_inline_value := case when position(':' in raw_line_value) > 0
      then substr(raw_line_value, position(':' in raw_line_value) + 1)
      else '' end;
    inline_value := btrim(raw_inline_value, ' ');

    if position(':' in line_value) > 0 and label_value in (
      'ТОВАР', 'КОНЦЕПЦИЯ', 'ХУК',
      'КЛЮЧЕВОЕ СООБЩЕНИЕ', 'АУДИТОРИЯ',
      'РЕПЛИКА / СЮЖЕТ', 'КАДРЫ', 'ВИЗУАЛ',
      'CTA', 'ДОКАЗАТЕЛЬСТВА',
      'НЕ ОБЕЩАТЬ / УЧЕСТЬ'
    ) then
      current_section := label_value;
      if label_value = 'РЕПЛИКА / СЮЖЕТ' then
        if outer_ascii_line_value !~*
             '^РЕПЛИКА / СЮЖЕТ:' then
          return null;
        end if;
        spoken_seen := spoken_seen + 1;
        if spoken_seen <> 1
           or content_factory_private
             .ai_research_seedance_speech_has_control(raw_inline_value)
           or raw_inline_value <> translate(
             raw_inline_value, raw_non_ascii_space_chars, ''
           ) then
          return null;
        end if;
        spoken_value := inline_value;
      end if;
      continue;
    end if;

    if current_section = 'РЕПЛИКА / СЮЖЕТ' then
      if content_factory_private
           .ai_research_seedance_speech_has_control(raw_line_value)
         or raw_line_value <> translate(
           raw_line_value, raw_non_ascii_space_chars, ''
         ) then
        return null;
      end if;
      spoken_value := concat_ws(
        ' ', nullif(spoken_value, ''), btrim(raw_line_value, ' ')
      );
    end if;
  end loop;

  spoken_value := btrim(regexp_replace(spoken_value, ' +', ' ', 'g'), ' ');
  if spoken_seen <> 1
     or spoken_value = ''
     or char_length(spoken_value) > 1200
     or content_factory_private
       .ai_research_seedance_speech_has_control(spoken_value)
     or content_factory_private
       .ai_research_seedance_has_default_ignorable(spoken_value)
     or spoken_value ~ '["''«»‘’‚‛“”„‟‹›⹂「」『』〝〞〟﹁﹂﹃﹄＂＇｢｣]'
     or lower(spoken_value) ~
       '(^|[.!?…][[:space:]]+)((герой|блогер|ведущ(ий|ая)|человек)[[:space:]]+(говорит|произносит|рассказывает)|реплика[[:space:]]+героя([[:space:]]+дословно)?)[[:space:]]*:'
     or content_factory_private.generation_spec_prompt_has_external_reference(
       spoken_value
     ) then
    return null;
  end if;

  select count(*)::integer into word_count_value
  from regexp_matches(
    spoken_value,
    '[[:alnum:]]+([-’''][[:alnum:]]+)*',
    'g'
  );
  if word_count_value not between 1 and word_limit_value then
    return null;
  end if;
  return spoken_value;
end;
$$;

revoke all on function
  content_factory_private.ai_research_seedance_spoken_line(text, integer)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.ai_research_seedance_speech_directive_count(
    p_compiled_prompt text
  )
returns integer
language sql
immutable
set search_path = ''
as $$
  with whitespace(chars) as (
    values (U&'\0085\00A0\1680\2000\2001\2002\2003\2004\2005\2006\2007\2008\2009\200A\2028\2029\202F\205F\3000')
  )
  select count(*)::integer
  from whitespace,
    regexp_matches(
      translate(
        lower(coalesce(p_compiled_prompt, '')),
        whitespace.chars,
        repeat(' ', char_length(whitespace.chars))
      ),
      '((герой|блогер|ведущ(ий|ая)|человек)[[:space:]]+(говорит|произносит|рассказывает)|реплика[[:space:]]+героя([[:space:]]+дословно)?)[[:space:]]*:',
      'g'
    );
$$;

revoke all on function
  content_factory_private.ai_research_seedance_speech_directive_count(text)
  from public, anon, authenticated, service_role;

create table if not exists
  content_factory.generation_spec_ai_research_speech_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    binding_id uuid not null,
    spoken_line_version text not null check (
      spoken_line_version = 'ai-research-seedance-speech-v1'
    ),
    spoken_line text not null check (
      char_length(spoken_line) between 1 and 1200
      and not content_factory_private
        .ai_research_seedance_speech_has_control(spoken_line)
      and not content_factory_private
        .ai_research_seedance_has_default_ignorable(spoken_line)
    ),
    spoken_line_hash text not null check (
      spoken_line_hash = content_factory_private.raw_text_sha256(spoken_line)
    ),
    spoken_prompt_fragment text not null check (
      char_length(spoken_prompt_fragment) between 27 and 1300
      and spoken_prompt_fragment =
        'Реплика героя дословно: «' || spoken_line || '»'
    ),
    spoken_prompt_fragment_hash text not null check (
      spoken_prompt_fragment_hash = content_factory_private.raw_text_sha256(
        spoken_prompt_fragment
      )
    ),
    compiled_prompt_hash text not null check (
      compiled_prompt_hash ~ '^[0-9a-f]{64}$'
    ),
    speech_binding_proof_hash text not null check (
      speech_binding_proof_hash = content_factory_private.raw_text_sha256(
        spoken_line_version || E'\n' || spoken_line || E'\n'
          || spoken_prompt_fragment || E'\n' || compiled_prompt_hash
      )
    ),
    applied_by uuid not null,
    applied_at timestamptz not null default clock_timestamp(),
    unique (organization_id, binding_id),
    unique (organization_id, id),
    foreign key (organization_id, binding_id)
      references content_factory.generation_spec_ai_research_bindings(
        organization_id, id
      ),
    foreign key (organization_id, applied_by)
      references content_factory.memberships(organization_id, profile_id)
  );

alter table content_factory.generation_spec_ai_research_speech_bindings
  enable row level security;
revoke all on content_factory.generation_spec_ai_research_speech_bindings
  from public, anon, authenticated;
grant all on content_factory.generation_spec_ai_research_speech_bindings
  to service_role;

drop trigger if exists generation_spec_ai_research_speech_binding_append_only
  on content_factory.generation_spec_ai_research_speech_bindings;
create trigger generation_spec_ai_research_speech_binding_append_only
before update or delete
  on content_factory.generation_spec_ai_research_speech_bindings
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

-- Keep the installed public project-ACL gateway untouched.  Its private v55
-- delegate still performs every historical scope/prompt check first; an
-- error below unwinds the base binding inserted by that delegate.
do $preserve_ai_research_seedance_speech_bind_v56$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_bind_generation_spec_ai_research_pre_seedance_speech_v56(jsonb)'
  ) is null then
    alter function content_factory_private
      .contentengine_bind_generation_spec_ai_research_pre_project_acl(jsonb)
      rename to
        contentengine_bind_generation_spec_ai_research_pre_seedance_speech_v56;
  end if;
end;
$preserve_ai_research_seedance_speech_bind_v56$;

revoke all on function content_factory_private
  .contentengine_bind_generation_spec_ai_research_pre_seedance_speech_v56(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function content_factory_private
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
  result_value jsonb;
  organization_id_value uuid;
  binding_id_value uuid;
  actor_id_value uuid;
  spec_row content_factory.generation_spec_versions%rowtype;
  binding_row content_factory.generation_spec_ai_research_bindings%rowtype;
  proof_row content_factory.generation_spec_ai_research_speech_bindings%rowtype;
  spoken_line_value text;
  spoken_line_hash_value text;
  spoken_prompt_fragment_value text;
  spoken_prompt_fragment_hash_value text;
  compiled_prompt_hash_value text;
  proof_hash_value text;
  spoken_marker_count_value integer := 0;
  structured_speech_count_value integer := 0;
  spoken_fragment_count_value integer := 0;
begin
  result_value := content_factory_private
    .contentengine_bind_generation_spec_ai_research_pre_seedance_speech_v56(
      p_payload
    );
  organization_id_value := content_factory_private.resolve_organization(
    content_factory_private.require_payload(p_payload)
  );
  actor_id_value := auth.uid();
  begin
    binding_id_value := (result_value #>> '{binding,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_ai_research_speech_binding_invalid';
  end;

  select binding.* into binding_row
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.id = binding_id_value
  for share;
  if binding_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_ai_research_speech_binding_invalid';
  end if;

  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = binding_row.organization_id
    and version.spec_id = binding_row.spec_id
    and version.spec_version = binding_row.spec_version
    and version.spec_hash = binding_row.spec_hash
  for share;
  if spec_row.version_id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_ai_research_speech_binding_invalid';
  end if;
  if spec_row.model <> 'seedance2_fast' then
    return result_value;
  end if;

  spoken_line_value := content_factory_private
    .ai_research_seedance_spoken_line(
      spec_row.editable_intent, spec_row.duration_seconds
    );
  if spoken_line_value is null then
    raise exception using
      errcode = '22023',
      message = 'generation_spec_ai_research_speech_invalid';
  end if;
  spoken_prompt_fragment_value :=
    'Реплика героя дословно: «' || spoken_line_value || '»';
  spoken_marker_count_value := content_factory_private
    .ai_research_seedance_speech_directive_count(spec_row.compiled_prompt);
  structured_speech_count_value := content_factory_private
    .ai_research_seedance_structured_speech_count(spec_row.compiled_prompt);
  spoken_fragment_count_value := (
    char_length(spec_row.compiled_prompt)
    - char_length(replace(
        spec_row.compiled_prompt, spoken_prompt_fragment_value, ''
      ))
  ) / char_length(spoken_prompt_fragment_value);
  compiled_prompt_hash_value := content_factory_private.raw_text_sha256(
    spec_row.compiled_prompt
  );
  if spoken_marker_count_value <> 1
     or structured_speech_count_value <> 0
     or spoken_fragment_count_value <> 1
     or content_factory_private
       .ai_research_seedance_has_default_ignorable(spec_row.compiled_prompt)
     or spec_row.prompt_hash <> compiled_prompt_hash_value then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_ai_research_speech_prompt_mismatch';
  end if;

  spoken_line_hash_value := content_factory_private.raw_text_sha256(
    spoken_line_value
  );
  spoken_prompt_fragment_hash_value := content_factory_private.raw_text_sha256(
    spoken_prompt_fragment_value
  );
  proof_hash_value := content_factory_private.raw_text_sha256(
    'ai-research-seedance-speech-v1' || E'\n' || spoken_line_value || E'\n'
      || spoken_prompt_fragment_value || E'\n' || compiled_prompt_hash_value
  );
  select proof.* into proof_row
  from content_factory.generation_spec_ai_research_speech_bindings proof
  where proof.organization_id = organization_id_value
    and proof.binding_id = binding_id_value
  for share;
  if proof_row.id is null then
    insert into content_factory.generation_spec_ai_research_speech_bindings (
      organization_id, binding_id, spoken_line_version, spoken_line,
      spoken_line_hash, spoken_prompt_fragment,
      spoken_prompt_fragment_hash, compiled_prompt_hash,
      speech_binding_proof_hash, applied_by
    ) values (
      organization_id_value, binding_id_value,
      'ai-research-seedance-speech-v1', spoken_line_value,
      spoken_line_hash_value, spoken_prompt_fragment_value,
      spoken_prompt_fragment_hash_value, compiled_prompt_hash_value,
      proof_hash_value, actor_id_value
    ) on conflict (organization_id, binding_id) do nothing;
    select proof.* into proof_row
    from content_factory.generation_spec_ai_research_speech_bindings proof
    where proof.organization_id = organization_id_value
      and proof.binding_id = binding_id_value
    for share;
  end if;
  if proof_row.id is null
     or proof_row.spoken_line_version <>
          'ai-research-seedance-speech-v1'
     or proof_row.spoken_line is distinct from spoken_line_value
     or proof_row.spoken_line_hash is distinct from spoken_line_hash_value
     or proof_row.spoken_prompt_fragment is distinct from
          spoken_prompt_fragment_value
     or proof_row.spoken_prompt_fragment_hash is distinct from
          spoken_prompt_fragment_hash_value
     or proof_row.compiled_prompt_hash is distinct from
          compiled_prompt_hash_value
     or proof_row.speech_binding_proof_hash is distinct from proof_hash_value then
    raise exception using
      errcode = '23505',
      message = 'generation_spec_ai_research_speech_binding_conflict';
  end if;

  return jsonb_set(
    result_value,
    '{binding}',
    coalesce(result_value -> 'binding', '{}'::jsonb) || jsonb_build_object(
      'spoken_line_version', proof_row.spoken_line_version,
      'spoken_line', proof_row.spoken_line,
      'spoken_line_hash', proof_row.spoken_line_hash,
      'spoken_prompt_fragment_hash', proof_row.spoken_prompt_fragment_hash,
      'speech_binding_proof_hash', proof_row.speech_binding_proof_hash,
      'speech_binding_legacy', false
    ),
    false
  ) || jsonb_build_object(
    'contract', coalesce(result_value -> 'contract', '{}'::jsonb)
      || jsonb_build_object(
        'seedance_speech_exactly_once', true,
        'seedance_speech_server_derived', true
      )
  );
end;
$$;

revoke all on function content_factory_private
  .contentengine_bind_generation_spec_ai_research_pre_project_acl(jsonb)
  from public, anon, authenticated, service_role;

-- The unchanged public read ACL still owns project authorization.  Enrich
-- only its private delegate with nullable legacy-compatible speech proof.
do $preserve_ai_research_seedance_speech_read_v56$
begin
  if to_regprocedure(
    'content_factory_private.contentengine_generation_spec_ai_research_binding_pre_seedance_speech_v56(jsonb)'
  ) is null then
    alter function content_factory_private
      .contentengine_generation_spec_ai_research_binding_pre_acl_v423(jsonb)
      rename to
        contentengine_generation_spec_ai_research_binding_pre_seedance_speech_v56;
  end if;
end;
$preserve_ai_research_seedance_speech_read_v56$;

revoke all on function content_factory_private
  .contentengine_generation_spec_ai_research_binding_pre_seedance_speech_v56(
    jsonb
  ) from public, anon, authenticated, service_role;

create or replace function content_factory_private
  .contentengine_generation_spec_ai_research_binding_pre_acl_v423(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  result_value jsonb;
  organization_id_value uuid;
  binding_id_value uuid;
  proof_row content_factory.generation_spec_ai_research_speech_bindings%rowtype;
  model_value text;
begin
  result_value := content_factory_private
    .contentengine_generation_spec_ai_research_binding_pre_seedance_speech_v56(
      p_payload
    );
  if result_value -> 'binding' = 'null'::jsonb
     or result_value -> 'binding' is null then
    return result_value;
  end if;
  organization_id_value := content_factory_private.resolve_organization(
    content_factory_private.require_payload(p_payload)
  );
  begin
    binding_id_value := (result_value #>> '{binding,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    return result_value;
  end;
  select version.model into model_value
  from content_factory.generation_spec_ai_research_bindings binding
  join content_factory.generation_spec_versions version
    on version.organization_id = binding.organization_id
   and version.spec_id = binding.spec_id
   and version.spec_version = binding.spec_version
   and version.spec_hash = binding.spec_hash
  where binding.organization_id = organization_id_value
    and binding.id = binding_id_value;

  select proof.* into proof_row
  from content_factory.generation_spec_ai_research_speech_bindings proof
  where proof.organization_id = organization_id_value
    and proof.binding_id = binding_id_value;

  return jsonb_set(
    result_value,
    '{binding}',
    coalesce(result_value -> 'binding', '{}'::jsonb) || jsonb_build_object(
      'spoken_line_version', proof_row.spoken_line_version,
      'spoken_line', proof_row.spoken_line,
      'spoken_line_hash', proof_row.spoken_line_hash,
      'spoken_prompt_fragment_hash', proof_row.spoken_prompt_fragment_hash,
      'speech_binding_proof_hash', proof_row.speech_binding_proof_hash,
      'speech_binding_legacy',
        model_value = 'seedance2_fast' and proof_row.id is null
    ),
    false
  );
end;
$$;

revoke all on function content_factory_private
  .contentengine_generation_spec_ai_research_binding_pre_acl_v423(jsonb)
  from public, anon, authenticated, service_role;

-- Preserve v55 byte-for-byte.  It still enforces all prior exact AI prompt
-- proof after the v54 video-reference chain.  This final wrapper delegates
-- first so rejection/speech failures atomically roll back its job and spend
-- writes before Edge can contact the provider.
do $preserve_ai_research_seedance_speech_start_v56$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_ai_speech_v56(jsonb)'
  ) is null then
    alter function public.creator_start_real_generation(jsonb)
      rename to creator_start_real_generation_pre_ai_speech_v56;
    alter function
      public.creator_start_real_generation_pre_ai_speech_v56(jsonb)
      set schema content_factory_private;
  end if;
end;
$preserve_ai_research_seedance_speech_start_v56$;

revoke all on function content_factory_private
  .creator_start_real_generation_pre_ai_speech_v56(jsonb)
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
  proof_row content_factory.generation_spec_ai_research_speech_bindings%rowtype;
  spoken_line_value text;
  spoken_line_hash_value text;
  spoken_prompt_fragment_value text;
  spoken_prompt_fragment_hash_value text;
  compiled_prompt_hash_value text;
  proof_hash_value text;
  spoken_marker_count_value integer := 0;
  structured_speech_count_value integer := 0;
  spoken_fragment_count_value integer := 0;
begin
  result_value := content_factory_private
    .creator_start_real_generation_pre_ai_speech_v56(p_payload);

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
        message = 'generation_ai_research_seedance_speech_binding_invalid';
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
      message = 'generation_ai_research_seedance_speech_binding_invalid';
  end if;
  if spec_row.model = 'seedance2_fast'
     and content_factory_private
       .ai_research_seedance_has_default_ignorable(
         spec_row.compiled_prompt
       ) then
    raise exception using errcode = '55000',
      message = 'generation_ai_research_seedance_speech_binding_invalid';
  end if;

  select binding.* into binding_row
  from content_factory.generation_spec_ai_research_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value
  for share;
  if spec_row.model <> 'seedance2_fast' or binding_row.id is null then
    return result_value;
  end if;

  select proof.* into proof_row
  from content_factory.generation_spec_ai_research_speech_bindings proof
  where proof.organization_id = organization_id_value
    and proof.binding_id = binding_row.id
  for share;
  if proof_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_seedance_speech_binding_required';
  end if;

  spoken_line_value := content_factory_private
    .ai_research_seedance_spoken_line(
      spec_row.editable_intent, spec_row.duration_seconds
    );
  if spoken_line_value is null then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_seedance_speech_binding_invalid';
  end if;
  spoken_prompt_fragment_value :=
    'Реплика героя дословно: «' || spoken_line_value || '»';
  spoken_marker_count_value := content_factory_private
    .ai_research_seedance_speech_directive_count(spec_row.compiled_prompt);
  structured_speech_count_value := content_factory_private
    .ai_research_seedance_structured_speech_count(spec_row.compiled_prompt);
  spoken_fragment_count_value := (
    char_length(spec_row.compiled_prompt)
    - char_length(replace(
        spec_row.compiled_prompt, spoken_prompt_fragment_value, ''
      ))
  ) / char_length(spoken_prompt_fragment_value);
  spoken_line_hash_value := content_factory_private.raw_text_sha256(
    spoken_line_value
  );
  spoken_prompt_fragment_hash_value := content_factory_private.raw_text_sha256(
    spoken_prompt_fragment_value
  );
  compiled_prompt_hash_value := content_factory_private.raw_text_sha256(
    spec_row.compiled_prompt
  );
  proof_hash_value := content_factory_private.raw_text_sha256(
    'ai-research-seedance-speech-v1' || E'\n' || spoken_line_value || E'\n'
      || spoken_prompt_fragment_value || E'\n' || compiled_prompt_hash_value
  );
  if spoken_marker_count_value <> 1
     or structured_speech_count_value <> 0
     or spoken_fragment_count_value <> 1
     or content_factory_private
       .ai_research_seedance_has_default_ignorable(spec_row.compiled_prompt)
     or spec_row.prompt_hash <> compiled_prompt_hash_value
     or proof_row.spoken_line_version <>
       'ai-research-seedance-speech-v1'
     or proof_row.spoken_line is distinct from spoken_line_value
     or proof_row.spoken_line_hash is distinct from spoken_line_hash_value
     or proof_row.spoken_prompt_fragment is distinct from
       spoken_prompt_fragment_value
     or proof_row.spoken_prompt_fragment_hash is distinct from
       spoken_prompt_fragment_hash_value
     or proof_row.compiled_prompt_hash is distinct from
       compiled_prompt_hash_value
     or proof_row.speech_binding_proof_hash is distinct from proof_hash_value then
    raise exception using
      errcode = '55000',
      message = 'generation_ai_research_seedance_speech_binding_invalid';
  end if;

  return result_value;
end;
$$;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated, service_role;

comment on function
  content_factory_private.ai_research_seedance_spoken_line(text, integer) is
  'Derives one raw structured РЕПЛИКА / СЮЖЕТ value with the exact Seedance duration word budget; wrappers, quotes, controls, Default_Ignorable code points, URLs and duplicate or nested labels fail closed.';
comment on table
  content_factory.generation_spec_ai_research_speech_bindings is
  'Append-only exact speech proof for an AI-bound Seedance generation spec. Absence is a readable legacy state but cannot cross paid start.';
comment on function
  public.contentengine_bind_generation_spec_ai_research(jsonb) is
  'Unchanged project-ACL gateway to the v55 exact AI prompt proof. For Seedance, the private delegate additionally requires one raw structured speech line and stores its immutable exact provider-sentence proof; no paid/provider call starts.';
comment on function public.creator_start_real_generation(jsonb) is
  'Delegates through v55 and every older paid-start guard, then revalidates one exact immutable AI Seedance speech line. Any failure rolls back job and spend before Edge/provider contact.';

notify pgrst, 'reload schema';

commit;

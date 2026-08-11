begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_function(
  'content_factory_private',
  'ai_research_provider_prompt_fragment',
  array['jsonb'],
  'the selected recommendation has one server-owned provider compiler'
);
select has_function(
  'content_factory_private',
  'ai_research_human_intent_fragment',
  array['text'],
  'the current labelled human brief has one bounded capsule compiler'
);
select has_column(
  'content_factory',
  'generation_spec_ai_research_bindings',
  'prompt_binding_proof_hash',
  'append-only bindings retain an additive prompt proof'
);

create or replace function pg_temp.ai_prompt_human_brief(
  p_key text
)
returns text
language sql
immutable
as $$
  select 'ТОВАР:' || E'\n'
    || 'MILIO A425D-Black' || E'\n\n'
    || 'КОНЦЕПЦИЯ:' || E'\n'
    || 'Честный обзор 🚀 ' || p_key || ' для маленькой кухни' || E'\n\n'
    || 'ХУК:' || E'\n'
    || 'Проверяем   размеры до покупки' || E'\n\n'
    || 'КЛЮЧЕВОЕ СООБЩЕНИЕ:' || E'\n'
    || 'Покажите точные факты' || E'\n\n'
    || 'CTA:' || E'\n'
    || 'Сравните размеры своей кухни перед покупкой' || E'\n\n'
    || 'ДОКАЗАТЕЛЬСТВА:' || E'\n'
    || '4 литра · 1500 Вт · 10 программ · окно · гарантия 3 года' || E'\n\n'
    || 'НЕ ОБЕЩАТЬ / УЧЕСТЬ:' || E'\n'
    || 'не обещать замену духовки · не говорить о 8 программах'
$$;

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'fa000000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'ai-prompt-binding@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"AI Prompt Binding Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'fa100000-0000-4000-8000-000000000001'::uuid,
  'AI prompt binding pgTAP',
  'ai-prompt-binding-pgtap',
  'active'
);

update content_factory.profiles
set status = 'active'
where id = 'fa000000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'fa100000-0000-4000-8000-000000000001'::uuid,
  'fa000000-0000-4000-8000-000000000001'::uuid,
  'owner', 'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'fa100000-0000-4000-8000-000000000001'::uuid,
  'fa000000-0000-4000-8000-000000000001'::uuid,
  'owner', 'owner',
  'TEST-ONLY waiver for AI prompt binding coverage.',
  'fa000000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  'fa200000-0000-4000-8000-000000000001'::uuid,
  'fa100000-0000-4000-8000-000000000001'::uuid,
  null, 'AI prompt project', 'gold', 'project',
  'active', 4096,
  'fa000000-0000-4000-8000-000000000001'::uuid,
  'fa000000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
) values (
  'fa100000-0000-4000-8000-000000000001'::uuid,
  'fa200000-0000-4000-8000-000000000001'::uuid,
  'fa000000-0000-4000-8000-000000000001'::uuid,
  'member', 'active',
  'fa000000-0000-4000-8000-000000000001'::uuid,
  'fa000000-0000-4000-8000-000000000001'::uuid
) on conflict do nothing;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values
  (
    'fa300000-0000-4000-8000-000000000001'::uuid,
    'fa100000-0000-4000-8000-000000000001'::uuid,
    '518413561', 'MILIO A425D-Black', 'active',
    '{"fixture":"selected-product"}'::jsonb,
    'fa000000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'fa300000-0000-4000-8000-000000000002'::uuid,
    'fa100000-0000-4000-8000-000000000001'::uuid,
    'OTHER-HOUSEHOLD', 'Other household product', 'active',
    '{"fixture":"wrong-product"}'::jsonb,
    'fa000000-0000-4000-8000-000000000001'::uuid
  );

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id,
  bucket_id, object_name, mime_type, size_bytes, sha256,
  status, metadata, idempotency_key
) values
  (
    'fa400000-0000-4000-8000-000000000001'::uuid,
    'fa100000-0000-4000-8000-000000000001'::uuid,
    'fa200000-0000-4000-8000-000000000001'::uuid,
    'fa000000-0000-4000-8000-000000000001'::uuid,
    'fa300000-0000-4000-8000-000000000001'::uuid,
    'contentengine-private',
    'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/uploads/ai-prompt-selected.jpg',
    'image/jpeg', 2048, repeat('a', 64), 'ready',
    '{"kind":"product_photo","original_filename":"selected.jpg","rights_confirmed":true}'::jsonb,
    'ai-prompt-selected-media-0001'
  ),
  (
    'fa400000-0000-4000-8000-000000000002'::uuid,
    'fa100000-0000-4000-8000-000000000001'::uuid,
    'fa200000-0000-4000-8000-000000000001'::uuid,
    'fa000000-0000-4000-8000-000000000001'::uuid,
    'fa300000-0000-4000-8000-000000000002'::uuid,
    'contentengine-private',
    'fa100000-0000-4000-8000-000000000001/fa000000-0000-4000-8000-000000000001/uploads/ai-prompt-other.jpg',
    'image/jpeg', 2048, repeat('b', 64), 'ready',
    '{"kind":"product_photo","original_filename":"other.jpg","rights_confirmed":true}'::jsonb,
    'ai-prompt-other-media-0001'
  );

-- The upstream research decision pipeline has its own coverage.  These two
-- immutable rows isolate exact recommendation -> prompt binding behavior.
set local session_replication_role = replica;
insert into content_factory.ai_research_learning_selections (
  id, organization_id, project_id, receipt_id, receipt_hash,
  run_id, draft_id, product_id, product_category, product_name, product_sku,
  decision, selected_insight_keys, selected_scenario_positions,
  analysis_snapshot, source_snapshot, recommendations, operator_notes,
  selected_by, request_hash, selection_hash, idempotency_key
) values
  (
    'fa500000-0000-4000-8000-000000000001'::uuid,
    'fa100000-0000-4000-8000-000000000001'::uuid,
    'fa200000-0000-4000-8000-000000000001'::uuid,
    'fa510000-0000-4000-8000-000000000001'::uuid, repeat('c', 64),
    'fa520000-0000-4000-8000-000000000001'::uuid,
    'fa530000-0000-4000-8000-000000000001'::uuid,
    'fa300000-0000-4000-8000-000000000001'::uuid,
    'household', 'MILIO A425D-Black', '518413561',
    'approve', array['brief']::text[], array[1, 2, 3]::smallint[],
    '{"fixture":"all-explicit-positions"}'::jsonb, '[]'::jsonb,
    jsonb_build_array(
      jsonb_build_object(
        'position', 1,
        'title', 'Instagram Reels: компактный обзор для кухни',
        'platform', 'instagram',
        'recommended_generation_mode', 'real_gen4',
        'hook', 'Покажите габариты в первом кадре',
        'cta', 'Сравните габариты перед покупкой',
        'proof_points', jsonb_build_array('4 литра', '1500 Вт'),
        'avoid_claims', jsonb_build_array('не обещать 12 программ')
      ),
      jsonb_build_object(
        'position', 2,
        'title', 'YouTube Shorts: «Стоит ли брать аэрогриль на маленькую кухню?»',
        'platform', 'youtube',
        'recommended_generation_mode', 'real_seedance',
        'hook', 'Честная проверка аэрогриля на маленькой кухне',
        'key_message', 'Покажите реальные габариты и сценарий использования',
        'cta', 'Сравните размеры своей кухни перед покупкой',
        'proof_points', jsonb_build_array(
          '4 литра', '1500 Вт', '10 программ',
          'окно просмотра', 'гарантия 3 года'
        ),
        'avoid_claims', jsonb_build_array(
          'не обещать замену духовки',
          'не говорить о 8 программах',
          'не скрывать ограничения объёма'
        )
      ),
      jsonb_build_object(
        'position', 3,
        'title', 'TikTok: корзина, окно и управление',
        'platform', 'tiktok',
        'recommended_generation_mode', 'real_seedance',
        'hook', 'Откройте корзину и покажите управление',
        'cta', 'Сохраните демо для сравнения',
        'proof_points', jsonb_build_array('10 программ', 'окно просмотра'),
        'avoid_claims', jsonb_build_array('не говорить о 8 программах')
      )
    ),
    'All three variants remain human-selectable.',
    'fa000000-0000-4000-8000-000000000001'::uuid,
    repeat('d', 64), repeat('e', 64),
    'ai-prompt-binding-selection-all-positions'
  ),
  (
    'fa500000-0000-4000-8000-000000000002'::uuid,
    'fa100000-0000-4000-8000-000000000001'::uuid,
    'fa200000-0000-4000-8000-000000000001'::uuid,
    'fa510000-0000-4000-8000-000000000002'::uuid, repeat('f', 64),
    'fa520000-0000-4000-8000-000000000002'::uuid,
    'fa530000-0000-4000-8000-000000000002'::uuid,
    'fa300000-0000-4000-8000-000000000001'::uuid,
    'household', 'MILIO A425D-Black', '518413561',
    'approve', array['brief']::text[], array[1]::smallint[],
    '{"fixture":"missing-proof"}'::jsonb, '[]'::jsonb,
    jsonb_build_array(jsonb_build_object(
      'position', 1, 'title', 'Incomplete recommendation',
      'hook', 'Hook exists', 'cta', 'CTA exists',
      'avoid_claims', jsonb_build_array('do not claim 8 modes')
    )),
    'Missing one required semantic component.',
    'fa000000-0000-4000-8000-000000000001'::uuid,
    repeat('1', 64), repeat('2', 64),
    'ai-prompt-binding-selection-incomplete'
  );
set local session_replication_role = origin;

select is(
  content_factory_private.ai_research_prompt_part(
    'A B 🚀    C', 8, false
  ),
  'A B 🚀 C',
  'code-point normalization keeps NBSP while collapsing ASCII whitespace around emoji 🚀'
);

select is(
  content_factory_private.ai_research_prompt_part(
    E'review\013queue', 32, false
  ),
  'review queue',
  'ordinary lowercase v survives while an actual vertical tab collapses to one space'
);

with fragments as (
  select position.value as recommendation_position,
    content_factory_private.ai_research_provider_prompt_fragment(
      selection.recommendations -> (position.value - 1)
    ) as fragment
  from content_factory.ai_research_learning_selections selection
  cross join unnest(array[1, 2, 3]::integer[]) position(value)
  where selection.id = 'fa500000-0000-4000-8000-000000000001'::uuid
)
select ok(
  count(*) = 3
  and bool_and(fragment is not null)
  and bool_and(char_length(fragment) <= 240)
  and bool_and(
    char_length(fragment)
      - char_length(replace(fragment, 'AIResearchSelection/v1', ''))
      = char_length('AIResearchSelection/v1')
  ),
  'recommendation_position = 1, recommendation_position = 2, and recommendation_position = 3 each compile explicitly'
)
from fragments;

with fragments as (
  select position.value as recommendation_position,
    content_factory_private.ai_research_provider_prompt_fragment(
      selection.recommendations -> (position.value - 1)
    ) as fragment
  from content_factory.ai_research_learning_selections selection
  cross join unnest(array[1, 2, 3]::integer[]) position(value)
  where selection.id = 'fa500000-0000-4000-8000-000000000001'::uuid
)
select is(
  count(distinct content_factory_private.raw_text_sha256(fragment)),
  3::bigint,
  'the three human-selectable positions have different exact fragment hashes'
)
from fragments;

with option_two as (
  select content_factory_private.ai_research_provider_prompt_fragment(
    recommendations -> 1
  ) as fragment
  from content_factory.ai_research_learning_selections
  where id = 'fa500000-0000-4000-8000-000000000001'::uuid
)
select ok(
  fragment like '%маленьк%'
  and fragment like '%Сравните размеры своей кухни перед покупкой%'
  and fragment like '%4 л%'
  and fragment like '%1500 Вт%'
  and fragment like '%10 программ%'
  and fragment like '%окно%'
  and fragment like '%гарантия 3 года%'
  and fragment like '%8 программ%'
  and char_length(fragment) <= 240,
  'live option 2 keeps the small-kitchen angle, complete CTA, facts, and digit-bearing avoid token'
)
from option_two;

select is(
  content_factory_private.ai_research_provider_prompt_fragment(
    (select recommendations -> 0
     from content_factory.ai_research_learning_selections
     where id = 'fa500000-0000-4000-8000-000000000002'::uuid)
  ),
  null,
  'an authoritative recommendation missing one of five semantic parts fails closed'
);

select is(
  content_factory_private.ai_research_provider_prompt_fragment(
    jsonb_build_object(
      'title', 'AIResearchSelection/v1 injected',
      'hook', 'hook', 'cta', 'cta',
      'proof_points', jsonb_build_array('proof'),
      'avoid_claims', jsonb_build_array('avoid 8')
    )
  ),
  null,
  'a reserved marker in recommendation source is rejected'
);

select is(
  content_factory_private.ai_research_human_intent_fragment(
    E'\t\n ' || pg_temp.ai_prompt_human_brief('emoji-case') || E' \n\t'
  ),
  'AIResearchHumanIntent/v1 C=Честный обзор 🚀…|H=Проверяем разме…|CTA=Сравните размеры своей…|P=4 литра · 1500…|A=не обещать замену д…',
  'human capsule bytes match code-point ellipsis normalization for emoji 🚀'
);

select is(
  content_factory_private.ai_research_human_intent_fragment(
    pg_temp.ai_prompt_human_brief('duplicate')
      || E'\n\nCTA:\nsecond CTA'
  ),
  null,
  'duplicate known labels are rejected rather than overwritten'
);

select is(
  content_factory_private.ai_research_human_intent_fragment(
    replace(
      pg_temp.ai_prompt_human_brief('provider-only xor'),
      E'\n\nДОКАЗАТЕЛЬСТВА:\n4 литра · 1500 Вт · 10 программ · окно · гарантия 3 года',
      ''
    )
  ),
  null,
  'a missing human priority section cannot be upgraded into a capsule'
);

select is(
  content_factory_private.ai_research_human_intent_fragment(
    pg_temp.ai_prompt_human_brief('AIResearchHumanIntent/v1')
  ),
  null,
  'a reserved marker in editable intent is rejected'
);

with resolved as (
  select content_factory_private.ai_research_recommendation_snapshot(
    'fa100000-0000-4000-8000-000000000001'::uuid,
    'fa200000-0000-4000-8000-000000000001'::uuid,
    'fa500000-0000-4000-8000-000000000001'::uuid,
    position.value::smallint
  ) value
  from unnest(array[1, 2, 3]) position(value)
)
select ok(
  count(*) = 3
  and bool_and(value ->> 'provider_prompt_fragment_version' =
    'ai-research-provider-fragment-v1')
  and bool_and(value ->> 'provider_prompt_fragment_hash' =
    content_factory_private.raw_text_sha256(
      value ->> 'provider_prompt_fragment'
    )),
  'every complete exact resolver envelope delivers its server fragment and raw SHA256'
)
from resolved;

create or replace function pg_temp.ai_prompt_recommendation(
  p_selection_id uuid,
  p_position smallint
)
returns jsonb
language sql
stable
as $$
  select candidate.value
  from content_factory.ai_research_learning_selections selection
  cross join lateral jsonb_array_elements(selection.recommendations)
    with ordinality candidate(value, ordinality)
  where selection.id = p_selection_id
    and case
      when coalesce(candidate.value ->> 'position', '') ~ '^[1-3]$'
        then (candidate.value ->> 'position')::smallint
      else candidate.ordinality::smallint
    end = p_position
  limit 1
$$;

create temporary table ai_prompt_binding_state (
  test_key text primary key,
  selection_id uuid,
  recommendation_position smallint,
  media_id uuid not null,
  editable_intent text not null,
  provider_fragment text,
  human_fragment text,
  proposed_prompt text,
  prepare_result jsonb,
  binding_result jsonb
) on commit drop;

insert into ai_prompt_binding_state (
  test_key, selection_id, recommendation_position, media_id,
  editable_intent
) values
  ('valid-1', 'fa500000-0000-4000-8000-000000000001', 1,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('valid-1')),
  ('valid-2', 'fa500000-0000-4000-8000-000000000001', 2,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('valid-2')),
  ('valid-3', 'fa500000-0000-4000-8000-000000000001', 3,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('valid-3')),
  ('wrong-product', 'fa500000-0000-4000-8000-000000000001', 2,
   'fa400000-0000-4000-8000-000000000002',
   pg_temp.ai_prompt_human_brief('exact product mismatch')),
  ('duplicate-provider', 'fa500000-0000-4000-8000-000000000001', 2,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('duplicate provider marker')),
  ('provider-only', 'fa500000-0000-4000-8000-000000000001', 2,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('provider-only xor')),
  ('human-only', 'fa500000-0000-4000-8000-000000000001', 2,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('human-only xor')),
  ('unbound-markers', 'fa500000-0000-4000-8000-000000000001', 2,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('unbound markers')),
  ('manual', null, null,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('manual no-marker/no-binding')),
  ('legacy-manual', 'fa500000-0000-4000-8000-000000000001', 1,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('legacy binding cannot start')),
  ('budget-incomplete', 'fa500000-0000-4000-8000-000000000002', 1,
   'fa400000-0000-4000-8000-000000000001',
   pg_temp.ai_prompt_human_brief('budget incomplete'));

update ai_prompt_binding_state state
set provider_fragment = case
      when state.selection_id is null then null
      else content_factory_private.ai_research_provider_prompt_fragment(
        pg_temp.ai_prompt_recommendation(
          state.selection_id,
          state.recommendation_position
        )
      )
    end,
    human_fragment = content_factory_private
      .ai_research_human_intent_fragment(state.editable_intent);

update ai_prompt_binding_state state
set proposed_prompt = case state.test_key
  when 'duplicate-provider' then
    'Create an exact product video.' || E'\n'
      || state.provider_fragment || E'\n'
      || state.provider_fragment || E'\n'
      || state.human_fragment
  when 'provider-only' then
    'Create an exact product video.' || E'\n'
      || lower(state.provider_fragment)
  when 'human-only' then
    'Create an exact product video.' || E'\n'
      || state.human_fragment
  when 'manual' then
    'Create a manual exact product video without AI selection.'
  when 'legacy-manual' then
    'Create a legacy manual exact product video without AI markers.'
  when 'budget-incomplete' then
    'Create an exact product video.' || E'\n'
      || 'AIResearchSelection/v1 C=incomplete|H=hook|CTA=cta|P=proof|A=avoid'
      || E'\n' || state.human_fragment
  else
    'Create an exact product video.' || E'\n'
      || state.provider_fragment || E'\n'
      || state.human_fragment
  end;

grant select, update on ai_prompt_binding_state to authenticated;

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'fa000000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

with resolved as (
  select public.contentengine_generation_research_recommendation(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'selection_id', 'fa500000-0000-4000-8000-000000000001'::uuid,
      'recommendation_position', 2
    )
  ) value
)
select ok(
  jsonb_array_length(value -> 'recommendations') = 3
  and value #>> '{authoritative_context,recommendation_position}' = '2'
  and not exists (
    select 1
    from jsonb_array_elements(value -> 'recommendations') item(value)
    where item.value ->> 'provider_prompt_fragment_version' <>
      'ai-research-provider-fragment-v1'
       or item.value ->> 'provider_prompt_fragment_hash' !~
         '^[0-9a-f]{64}$'
  ),
  'the public exact resolver delivers all variants while position 2 remains the explicit human choice'
)
from resolved;

update ai_prompt_binding_state state
set prepare_result = public.creator_prepare_generation_spec(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'idempotency_key', 'ai-prompt-prepare-' || state.test_key,
    'exact_scope', jsonb_build_object(
      'primary_media_id', state.media_id,
      'media_ids', jsonb_build_array(state.media_id),
      'platform', 'youtube',
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'product_category', 'household',
      'format', '9:16',
      'audio', true
    ),
    'editable_intent', state.editable_intent,
    'proposed_prompt', state.proposed_prompt,
    'learning_context', jsonb_build_object(
      'creative_angle', 'product_focus',
      'hook_patterns', '[]'::jsonb,
      'source', 'baseline',
      'compiler_version', 'safe-brief-v7',
      'product_category', 'household'
    ),
    'repair_context', null,
    'research_provenance', null,
    'performance_policy_provenance', null,
    'repair_provenance', null,
    'confirmation', true,
    'reason', 'Prepare exact AI prompt binding pgTAP fixture.'
  )
);

select is(
  count(*) filter (
    where prepare_result #>> '{generation_spec,status}' = 'draft'
  ),
  11::bigint,
  'all valid, mismatch, XOR, manual, legacy, and budget specs are immutable fixtures'
)
from ai_prompt_binding_state;

update ai_prompt_binding_state state
set binding_result = public.contentengine_bind_generation_spec_ai_research(
  jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
    'spec_version', (
      state.prepare_result #>> '{generation_spec,spec_version}'
    )::integer,
    'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
    'selection_id', state.selection_id,
    'recommendation_position', state.recommendation_position,
    'confirmation', true
  )
)
where state.test_key in ('valid-1', 'valid-2', 'valid-3');

select is(
  count(*) filter (
    where binding_result #>> '{version}' =
      'generation-spec-ai-research-binding-v2'
      and binding_result #>> '{binding,legacy}' = 'false'
      and binding_result #>> '{binding,scope_match}' = 'exact_product'
      and binding_result #>> '{binding,provider_prompt_fragment_version}' =
        'ai-research-provider-fragment-v1'
      and binding_result #>> '{binding,human_intent_fragment_version}' =
        'ai-research-human-intent-v1'
  ),
  3::bigint,
  'recommendation_position = 1, recommendation_position = 2, and recommendation_position = 3 bind only after explicit supply'
)
from ai_prompt_binding_state
where test_key in ('valid-1', 'valid-2', 'valid-3');

reset role;

select ok(
  count(*) = 3
  and count(distinct provider_prompt_fragment_hash) = 3
  and bool_and(provider_prompt_fragment_hash =
    content_factory_private.raw_text_sha256(provider_prompt_fragment))
  and bool_and(human_intent_fragment_hash =
    content_factory_private.raw_text_sha256(human_intent_fragment))
  and bool_and(compiled_prompt_hash ~ '^[0-9a-f]{64}$')
  and bool_and(prompt_binding_proof_hash =
    content_factory_private.raw_text_sha256(
      provider_prompt_fragment || E'\n' || human_intent_fragment
    )),
  'three append-only bindings retain exact fragment, human, prompt, and combined proof hashes'
)
from content_factory.generation_spec_ai_research_bindings
where organization_id = 'fa100000-0000-4000-8000-000000000001'::uuid;

set local role authenticated;

with state as (
  select * from ai_prompt_binding_state where test_key = 'valid-2'
), read_result as (
  select public.contentengine_generation_spec_ai_research_binding(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (
        state.prepare_result #>> '{generation_spec,spec_version}'
      )::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    )
  ) value
  from state
)
select ok(
  value #>> '{version}' = 'generation-spec-ai-research-binding-v2'
  and value #>> '{binding,project_id}' =
    'fa200000-0000-4000-8000-000000000001'
  and value #>> '{binding,spec_id}' ~ '^[0-9a-f-]{36}$'
  and value #>> '{binding,spec_version}' = '1'
  and value #>> '{binding,spec_hash}' ~ '^[0-9a-f]{64}$'
  and value #>> '{binding,provider_prompt_fragment_hash}' ~
    '^[0-9a-f]{64}$'
  and value #>> '{binding,human_intent_fragment_hash}' ~
    '^[0-9a-f]{64}$'
  and value #>> '{binding,legacy}' = 'false',
  'the private read delegate returns a self-contained additive proof through the unchanged public ACL wrapper'
)
from read_result;

select throws_ok(
  $$select public.contentengine_bind_generation_spec_ai_research(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
      'selection_id', state.selection_id,
      'recommendation_position', state.recommendation_position,
      'confirmation', true
    )
  )
  from ai_prompt_binding_state state
  where state.test_key = 'wrong-product'$$,
  '42501',
  'generation_spec_ai_research_binding_scope_mismatch',
  'exact product mismatch cannot bind same-category advice to another SKU'
);

select throws_ok(
  $$select public.contentengine_bind_generation_spec_ai_research(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
      'selection_id', state.selection_id,
      'recommendation_position', state.recommendation_position,
      'confirmation', true
    )
  )
  from ai_prompt_binding_state state
  where state.test_key = 'duplicate-provider'$$,
  '55000',
  'generation_spec_ai_research_prompt_binding_invalid',
  'duplicate provider marker is rejected at append-only bind time'
);

select throws_ok(
  $$select public.contentengine_bind_generation_spec_ai_research(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
      'selection_id', state.selection_id,
      'recommendation_position', state.recommendation_position,
      'confirmation', true
    )
  )
  from ai_prompt_binding_state state
  where state.test_key = 'provider-only'$$,
  '55000',
  'generation_spec_ai_research_prompt_binding_invalid',
  'provider-only XOR state cannot create a binding'
);

select throws_ok(
  $$select public.contentengine_bind_generation_spec_ai_research(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
      'selection_id', state.selection_id,
      'recommendation_position', state.recommendation_position,
      'confirmation', true
    )
  )
  from ai_prompt_binding_state state
  where state.test_key = 'human-only'$$,
  '55000',
  'generation_spec_ai_research_prompt_binding_invalid',
  'human-only XOR state cannot create a binding'
);

select throws_ok(
  $$select public.contentengine_bind_generation_spec_ai_research(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
      'selection_id', state.selection_id,
      'recommendation_position', 2,
      'confirmation', true
    )
  )
  from ai_prompt_binding_state state
  where state.test_key = 'valid-1'$$,
  '55000',
  'generation_spec_ai_research_prompt_binding_invalid',
  'another recommendation position cannot replace the position bound to one immutable spec version'
);

select throws_ok(
  $$select public.contentengine_bind_generation_spec_ai_research(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
      'selection_id', state.selection_id,
      'recommendation_position', state.recommendation_position,
      'confirmation', true
    )
  )
  from ai_prompt_binding_state state
  where state.test_key = 'budget-incomplete'$$,
  '22023',
  'ai_research_prompt_budget_exceeded',
  'missing five-part authority fails with stable ai_research_prompt_budget_exceeded'
);

reset role;

select is(
  count(*),
  3::bigint,
  'failed exact product, duplicate, XOR, and budget binds append no row'
)
from content_factory.generation_spec_ai_research_bindings
where organization_id = 'fa100000-0000-4000-8000-000000000001'::uuid;

-- Materialize one pre-migration row: every additive proof column is NULL.
-- It remains readable for audit but must never start.
set local session_replication_role = replica;
insert into content_factory.generation_spec_ai_research_bindings (
  organization_id, project_id, spec_id, spec_version, spec_hash,
  selection_id, selection_hash, recommendation_position,
  recommendation_snapshot, recommendation_hash, applied_by
)
select
  'fa100000-0000-4000-8000-000000000001'::uuid,
  'fa200000-0000-4000-8000-000000000001'::uuid,
  (state.prepare_result #>> '{generation_spec,spec_id}')::uuid,
  (state.prepare_result #>> '{generation_spec,spec_version}')::integer,
  state.prepare_result #>> '{generation_spec,spec_hash}',
  state.selection_id,
  selection.selection_hash,
  state.recommendation_position,
  pg_temp.ai_prompt_recommendation(
    state.selection_id, state.recommendation_position
  ),
  content_factory_private.json_hash(pg_temp.ai_prompt_recommendation(
    state.selection_id, state.recommendation_position
  )),
  'fa000000-0000-4000-8000-000000000001'::uuid
from ai_prompt_binding_state state
join content_factory.ai_research_learning_selections selection
  on selection.id = state.selection_id
where state.test_key = 'legacy-manual';
set local session_replication_role = origin;

select ok(
  exists (
    select 1
    from content_factory.generation_spec_ai_research_bindings binding
    where binding.organization_id =
      'fa100000-0000-4000-8000-000000000001'::uuid
      and binding.provider_prompt_fragment_version is null
      and binding.human_intent_fragment_version is null
      and binding.prompt_binding_proof_hash is null
  ),
  'legacy nullable columns preserve old append-only rows without blessing them'
);

create table content_factory.ai_prompt_binding_start_audit (
  id uuid primary key default extensions.gen_random_uuid(),
  test_key text not null,
  effect text not null check (effect in ('job', 'spend', 'provider_call')),
  created_at timestamptz not null default clock_timestamp()
);
grant select on content_factory.ai_prompt_binding_start_audit
  to authenticated;

-- Replace only the just-preserved v55 delegate inside this rolled-back test
-- transaction.  Its two writes stand in for the old chain's transactional job
-- and spend reservation.  A provider row is intentionally never written:
-- Edge cannot run until the outer public RPC returns.
create or replace function content_factory_private
  .creator_start_real_generation_pre_ai_research_prompt_v55(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  test_key_value text := coalesce(p_payload ->> 'test_key', 'unknown');
begin
  if p_payload ->> 'test_legacy_error' = 'true' then
    raise exception using
      errcode = '22023', message = 'legacy_validation_keeps_precedence';
  end if;
  insert into content_factory.ai_prompt_binding_start_audit (
    test_key, effect
  ) values
    (test_key_value, 'job'),
    (test_key_value, 'spend');
  return jsonb_build_object(
    'ok', true,
    'batch', jsonb_build_object(
      'id', 'fa700000-0000-4000-8000-000000000001'::uuid
    ),
    'job', jsonb_build_object(
      'id', 'fa710000-0000-4000-8000-000000000001'::uuid
    ),
    'test_key', test_key_value
  );
end;
$$;

set local role authenticated;

with state as (
  select * from ai_prompt_binding_state where test_key = 'legacy-manual'
), read_result as (
  select public.contentengine_generation_spec_ai_research_binding(
    jsonb_build_object(
      'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    )
  ) value
  from state
)
select ok(
  value #>> '{binding,legacy}' = 'true'
  and value #>> '{binding,provider_prompt_fragment}' is null
  and value #>> '{binding,human_intent_fragment}' is null,
  'legacy binding remains explicitly readable as legacy with no proof'
)
from read_result;

with state as (
  select * from ai_prompt_binding_state where test_key = 'manual'
)
select is(
  public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'manual no-marker/no-binding'
  )) #>> '{test_key}',
  'manual no-marker/no-binding',
  'manual no-marker/no-binding remains allowed and AI stays optional'
)
from state;

with state as (
  select * from ai_prompt_binding_state where test_key = 'valid-2'
)
select is(
  public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'valid exact option 2'
  )) #>> '{test_key}',
  'valid exact option 2',
  'one exact provider marker plus human marker plus nonlegacy binding may return to Edge'
)
from state;

select is(
  (select count(*)
   from content_factory.ai_prompt_binding_start_audit
   where effect in ('job', 'spend')),
  4::bigint,
  'two successful starts retain the two delegated transactional effects each'
);

select throws_ok(
  $$select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'duplicate provider marker'
  ))
  from ai_prompt_binding_state state
  where state.test_key = 'duplicate-provider'$$,
  '55000',
  'generation_ai_research_prompt_binding_invalid',
  'duplicate provider marker cannot cross paid start'
);

select throws_ok(
  $$select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'provider-only xor'
  ))
  from ai_prompt_binding_state state
  where state.test_key = 'provider-only'$$,
  '55000',
  'generation_ai_research_prompt_binding_invalid',
  'provider-only XOR cannot cross paid start'
);

select throws_ok(
  $$select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'human-only xor'
  ))
  from ai_prompt_binding_state state
  where state.test_key = 'human-only'$$,
  '55000',
  'generation_ai_research_prompt_binding_invalid',
  'human-only XOR cannot cross paid start'
);

select throws_ok(
  $$select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'markers without binding'
  ))
  from ai_prompt_binding_state state
  where state.test_key = 'unbound-markers'$$,
  '55000',
  'generation_ai_research_prompt_binding_invalid',
  'marker pair without the exact nonlegacy binding cannot cross paid start'
);

select throws_ok(
  $$select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'legacy binding cannot start'
  ))
  from ai_prompt_binding_state state
  where state.test_key = 'legacy-manual'$$,
  '55000',
  'generation_ai_research_legacy_binding_start_forbidden',
  'legacy binding cannot start even though it remains readable'
);

select throws_ok(
  $$select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'fa100000-0000-4000-8000-000000000001'::uuid,
    'project_id', 'fa200000-0000-4000-8000-000000000001'::uuid,
    'generation_spec_context', jsonb_build_object(
      'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version', (state.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
      'spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}'
    ),
    'test_key', 'legacy validation first',
    'test_legacy_error', 'true'
  ))
  from ai_prompt_binding_state state
  where state.test_key = 'unbound-markers'$$,
  '22023',
  'legacy_validation_keeps_precedence',
  'legacy validation keeps precedence because the complete v55 delegate runs first'
);

select is(
  (select count(*)
   from content_factory.ai_prompt_binding_start_audit
   where effect in ('job', 'spend')),
  4::bigint,
  'delegated writes roll back for duplicate, XOR, unbound, and legacy proof failures'
);

select is(
  (select count(*)
   from content_factory.ai_prompt_binding_start_audit
   where effect = 'provider_call'),
  0::bigint,
  'provider cannot be called inside the database before the outer RPC returns'
);

reset role;

select * from finish();

rollback;

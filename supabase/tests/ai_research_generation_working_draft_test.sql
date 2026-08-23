begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(22);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values
  (
    'f8100000-0000-4000-8000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated', 'authenticated',
    'ai-draft-owner@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"AI Draft Owner"}'::jsonb, now(), now()
  ),
  (
    'f8100000-0000-4000-8000-000000000002'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    'authenticated', 'authenticated',
    'ai-draft-operator@example.test',
    extensions.crypt('test-only-password', extensions.gen_salt('bf')),
    now(), '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"AI Draft Operator"}'::jsonb, now(), now()
  );

insert into content_factory.organizations (id, name, slug, status)
values (
  'f8110000-0000-4000-8000-000000000001'::uuid,
  'AI working draft pgTAP',
  'ai-working-draft-pgtap',
  'active'
);

update content_factory.profiles
set status = 'active'
where id in (
  'f8100000-0000-4000-8000-000000000001'::uuid,
  'f8100000-0000-4000-8000-000000000002'::uuid
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'f8110000-0000-4000-8000-000000000001'::uuid,
    'f8100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'active'
  ),
  (
    'f8110000-0000-4000-8000-000000000001'::uuid,
    'f8100000-0000-4000-8000-000000000002'::uuid,
    'operator', 'active'
  );

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values
  (
    'f8110000-0000-4000-8000-000000000001'::uuid,
    'f8100000-0000-4000-8000-000000000001'::uuid,
    'owner', 'owner',
    'TEST-ONLY waiver for AI working draft owner.',
    'f8100000-0000-4000-8000-000000000001'::uuid
  ),
  (
    'f8110000-0000-4000-8000-000000000001'::uuid,
    'f8100000-0000-4000-8000-000000000002'::uuid,
    'operator', 'operator',
    'TEST-ONLY waiver for AI working draft operator.',
    'f8100000-0000-4000-8000-000000000001'::uuid
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  'f8120000-0000-4000-8000-000000000001'::uuid,
  'f8110000-0000-4000-8000-000000000001'::uuid,
  null, 'Shared AI draft project', 'gold', 'project',
  'active', 4096,
  'f8100000-0000-4000-8000-000000000001'::uuid,
  'f8100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_project_memberships (
  organization_id, project_id, profile_id, access_role, status,
  granted_by, updated_by
) values (
  'f8110000-0000-4000-8000-000000000001'::uuid,
  'f8120000-0000-4000-8000-000000000001'::uuid,
  'f8100000-0000-4000-8000-000000000002'::uuid,
  'member', 'active',
  'f8100000-0000-4000-8000-000000000001'::uuid,
  'f8100000-0000-4000-8000-000000000001'::uuid
) on conflict do nothing;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'f8160000-0000-4000-8000-000000000001'::uuid,
  'f8110000-0000-4000-8000-000000000001'::uuid,
  '518413561', 'MILIO A425D-Black', 'active',
  '{"brand":"MILIO","fixture":"option-2"}'::jsonb,
  'f8100000-0000-4000-8000-000000000001'::uuid
);

-- The upstream research pipeline has its own exhaustive pgTAP coverage. This
-- fixture bypasses only those unrelated FK triggers so this file can execute
-- the real approved-selection -> public save -> second-member read boundary.
set local session_replication_role = replica;
insert into content_factory.ai_research_learning_selections (
  id, organization_id, project_id, receipt_id, receipt_hash,
  run_id, draft_id, product_id, product_category, product_name, product_sku,
  decision, selected_insight_keys, selected_scenario_positions,
  analysis_snapshot, source_snapshot, recommendations, operator_notes,
  selected_by, request_hash, selection_hash, idempotency_key
) values (
  'f8150000-0000-4000-8000-000000000001'::uuid,
  'f8110000-0000-4000-8000-000000000001'::uuid,
  'f8120000-0000-4000-8000-000000000001'::uuid,
  'f8170000-0000-4000-8000-000000000001'::uuid,
  repeat('a', 64),
  'f8180000-0000-4000-8000-000000000001'::uuid,
  'f8190000-0000-4000-8000-000000000001'::uuid,
  'f8160000-0000-4000-8000-000000000001'::uuid,
  'household', 'MILIO A425D-Black', '518413561',
  'approve', array['category']::text[], array[1, 2, 3]::smallint[],
  '{"fixture":"approved-option-2"}'::jsonb,
  '[]'::jsonb,
  jsonb_build_array(
    jsonb_build_object(
      'position', 1,
      'title', 'Option 1: compact kitchen walkthrough',
      'platform', 'instagram',
      'recommended_generation_mode', 'real_gen4',
      'duration_seconds', 5,
      'format', '1:1',
      'hook', 'Show the compact footprint first',
      'key_message', 'Human-selected option one',
      'cta', 'Compare the dimensions before buying'
    ),
    jsonb_build_object(
      'position', 2,
      'title', 'YouTube Shorts: Стоит ли брать аэрогриль на маленькую кухню?',
      'platform', 'youtube',
      'recommended_generation_mode', 'real_seedance',
      'duration_seconds', 8,
      'format', '9:16',
      'hook', 'Честная проверка аэрогриля на маленькой кухне',
      'key_message', 'Покажите реальные габариты и сценарий использования',
      'cta', 'Сравните размеры своей кухни перед покупкой',
      'proof_points', jsonb_build_array('4 литра', '1500 Вт'),
      'avoid_claims', jsonb_build_array('не обещать замену духовки')
    ),
    jsonb_build_object(
      'position', 3,
      'title', 'Option 3: basket and controls demo',
      'platform', 'tiktok',
      'recommended_generation_mode', 'real_seedance',
      'duration_seconds', 12,
      'format', '9:16',
      'hook', 'Open the basket and show the controls',
      'key_message', 'Human-selected option three',
      'cta', 'Save the demo for comparison'
    )
  ),
  'Approved exact option 2 fixture.',
  'f8100000-0000-4000-8000-000000000001'::uuid,
  repeat('b', 64), repeat('c', 64),
  'ai-working-draft-option-2-fixture'
);
set local session_replication_role = origin;

select is(
  (
    select jsonb_array_length(recommendations)
    from content_factory.ai_research_learning_selections
    where id = 'f8150000-0000-4000-8000-000000000001'::uuid
  ),
  3,
  'the approved learning selection preserves every human-selectable variant'
);

-- A cleared row is enough to execute read/clear/CAS without manufacturing a
-- research result. Active rows remain possible only through a verified
-- ai_research_learning_selection FK and the save RPC.
insert into content_factory.generation_ai_research_working_drafts (
  id, organization_id, project_id, status, revision,
  selection_id, recommendation_position, editable_fields,
  applied_fields, touched_fields, previous_values,
  last_applied_values, auto_apply_disabled,
  created_by, updated_by, last_mutation_id
) values (
  'f8130000-0000-4000-8000-000000000001'::uuid,
  'f8110000-0000-4000-8000-000000000001'::uuid,
  'f8120000-0000-4000-8000-000000000001'::uuid,
  'cleared', 7, null, null, '{}'::jsonb,
  array[]::text[], array[]::text[], '{}'::jsonb, '{}'::jsonb, false,
  'f8100000-0000-4000-8000-000000000001'::uuid,
  'f8100000-0000-4000-8000-000000000001'::uuid,
  'f8140000-0000-4000-8000-000000000001'::uuid
);

select has_function(
  'public', 'contentengine_generation_research_recommendation',
  array['jsonb'],
  'one exact AI Center recommendation has a server resolver'
);

select has_function(
  'public', 'contentengine_generation_ai_research_working_draft',
  array['jsonb'],
  'the project-shared working draft has one bounded RPC'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.contentengine_generation_research_recommendation(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.contentengine_generation_ai_research_working_draft(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.contentengine_generation_ai_research_working_draft(jsonb)',
    'execute'
  ),
  'only signed-in project members receive the browser RPCs'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.generation_ai_research_working_drafts',
    'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_ai_research_working_drafts',
    'update'
  ),
  'the mutable draft table is never a direct browser authority'
);

select ok(
  content_factory_private.ai_research_working_draft_fields_valid(
    '{
      "product_category":"household",
      "platform":"youtube",
      "generation_mode":"real_seedance",
      "duration_seconds":8,
      "format":"9:16",
      "brief":"MILIO option 2"
    }'::jsonb
  ),
  'the exact option-2 creative field shape is accepted'
);

select is(
  content_factory_private.ai_research_recommendation_snapshot(
    'f8110000-0000-4000-8000-000000000001'::uuid,
    'f8120000-0000-4000-8000-000000000001'::uuid,
    'f8150000-0000-4000-8000-000000000002'::uuid,
    2::smallint
  ),
  null,
  'the append-only recommendation snapshot executes without a row lock and fails closed'
);

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'f8100000-0000-4000-8000-000000000001',
  true
);
set local role authenticated;

select is(
  public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) #>> '{revision}',
  '7',
  'first user reads the authoritative cleared revision'
);

select is(
  public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) #>> '{draft}',
  null,
  'a cleared server draft never resurrects local AI values'
);

select is(
  public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'clear',
      'expected_revision', 7,
      'mutation_id', 'f8140000-0000-4000-8000-000000000002'::uuid
    )
  ) #>> '{revision}',
  '8',
  'a matching optimistic revision advances exactly once'
);

select throws_ok(
  $$select public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'clear',
      'expected_revision', 7,
      'mutation_id', 'f8140000-0000-4000-8000-000000000003'::uuid
    )
  )$$,
  'PT409',
  'generation_ai_research_working_draft_revision_conflict',
  'a stale participant cannot overwrite the shared project revision'
);

select throws_ok(
  $$select public.contentengine_generation_research_recommendation(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'selection_id', 'f8150000-0000-4000-8000-000000000002'::uuid,
      'recommendation_position', 2,
      'product_category', 'household'
    )
  )$$,
  '22023',
  'generation_research_recommendation_payload_invalid',
  'a URL/client category is rejected instead of trusted'
);

select throws_ok(
  $$select public.contentengine_generation_research_recommendation(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'selection_id', 'f8150000-0000-4000-8000-000000000002'::uuid,
      'recommendation_position', 2
    )
  )$$,
  '42501',
  'generation_research_recommendation_scope_mismatch',
  'a missing/category-only selection cannot be upgraded to exact auto-apply'
);

with resolved as (
  select public.contentengine_generation_research_recommendation(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'selection_id', 'f8150000-0000-4000-8000-000000000001'::uuid,
      'recommendation_position', 2
    )
  ) value
)
select is(
  concat_ws('|',
    jsonb_array_length(value -> 'recommendations'),
    value #>> '{authoritative_context,recommendation_position}'
  ),
  '3|2',
  'the exact option 2 resolver keeps all approved siblings while option 2 remains authoritative'
)
from resolved;

with saved as (
  select public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'save',
      'expected_revision', 8,
      'mutation_id', 'f8140000-0000-4000-8000-000000000004'::uuid,
      'selection_id', 'f8150000-0000-4000-8000-000000000001'::uuid,
      'recommendation_position', 2,
      'editable_fields', jsonb_build_object(
        'product_category', 'household',
        'platform', 'youtube',
        'generation_mode', 'real_seedance',
        'duration_seconds', 8,
        'format', '9:16',
        'brief', 'MILIO option 2 shared brief — edited by owner'
      ),
      'applied_fields', jsonb_build_array(
        'product_category', 'platform', 'mode',
        'duration_seconds', 'format', 'brief'
      ),
      'touched_fields', jsonb_build_array('brief'),
      'previous_values', jsonb_build_object('brief', ''),
      'last_applied_values', jsonb_build_object(
        'brief', 'MILIO option 2 original brief'
      ),
      'auto_apply_disabled', false
    )
  ) value
)
select is(
  concat_ws('|',
    value #>> '{revision}',
    value #>> '{draft,selection_id}',
    value #>> '{draft,recommendation_position}',
    value #>> '{draft,recommendation,product_id}',
    value #>> '{draft,editable_fields,brief}'
  ),
  '9|f8150000-0000-4000-8000-000000000001|2|f8160000-0000-4000-8000-000000000001|MILIO option 2 shared brief — edited by owner',
  'owner saves the real approved option 2 through the public CAS RPC'
)
from saved;

select set_config(
  'request.jwt.claim.sub',
  'f8100000-0000-4000-8000-000000000002',
  true
);

select is(
  public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) #>> '{revision}',
  '9',
  'a second project member sees the same active revision'
);

with shared as (
  select public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) value
)
select is(
  concat_ws('|',
    value #>> '{draft,selection_id}',
    value #>> '{draft,recommendation_position}',
    value #>> '{draft,recommendation,product_id}',
    value #>> '{draft,recommendation,source_product_sku}'
  ),
  'f8150000-0000-4000-8000-000000000001|2|f8160000-0000-4000-8000-000000000001|518413561',
  'second exact project member reads the same selected variant and product'
)
from shared;

with shared as (
  select public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) value
)
select is(
  value #> '{draft,editable_fields}',
  '{
    "product_category":"household",
    "platform":"youtube",
    "generation_mode":"real_seedance",
    "duration_seconds":8,
    "format":"9:16",
    "brief":"MILIO option 2 shared brief — edited by owner"
  }'::jsonb,
  'second member receives the same six editable non-financial fields'
)
from shared;

with switched as (
  select public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'save',
      'expected_revision', 9,
      'mutation_id', 'f8140000-0000-4000-8000-000000000005'::uuid,
      'selection_id', 'f8150000-0000-4000-8000-000000000001'::uuid,
      'recommendation_position', 1,
      'editable_fields', jsonb_build_object(
        'product_category', 'household',
        'platform', 'instagram',
        'generation_mode', 'real_gen4',
        'duration_seconds', 5,
        'format', '1:1',
        'brief', 'MILIO option 1 explicitly selected by the second member'
      ),
      'applied_fields', jsonb_build_array(
        'product_category', 'platform', 'mode',
        'duration_seconds', 'format', 'brief'
      ),
      'touched_fields', jsonb_build_array(),
      'previous_values', jsonb_build_object('brief', ''),
      'last_applied_values', jsonb_build_object(
        'brief', 'MILIO option 1 original brief'
      ),
      'auto_apply_disabled', false
    )
  ) value
)
select is(
  concat_ws('|',
    value #>> '{revision}',
    value #>> '{draft,selection_id}',
    value #>> '{draft,recommendation_position}',
    value #>> '{draft,editable_fields,brief}'
  ),
  '10|f8150000-0000-4000-8000-000000000001|1|MILIO option 1 explicitly selected by the second member',
  'an explicit option 2 to option 1 switch advances the shared draft without reranking'
)
from switched;

select set_config(
  'request.jwt.claim.sub',
  'f8100000-0000-4000-8000-000000000001',
  true
);

select is(
  concat_ws('|',
    public.contentengine_generation_ai_research_working_draft(
      jsonb_build_object(
        'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
        'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
        'action', 'read'
      )
    ) #>> '{revision}',
    public.contentengine_generation_ai_research_working_draft(
      jsonb_build_object(
        'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
        'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
        'action', 'read'
      )
    ) #>> '{draft,recommendation_position}'
  ),
  '10|1',
  'owner reload sees the second member explicit option 1 and never reranks to first implicitly'
);

select is(
  public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) #>> '{contract,one_active_draft_per_project}',
  'true',
  'the single active shared-draft policy is explicit to every participant'
);

select is(
  public.contentengine_generation_ai_research_working_draft(
    jsonb_build_object(
      'organization_id', 'f8110000-0000-4000-8000-000000000001'::uuid,
      'project_id', 'f8120000-0000-4000-8000-000000000001'::uuid,
      'action', 'read'
    )
  ) #>> '{contract,financial_fields_stored}',
  'false',
  'the shared draft proves that financial fields are absent'
);

reset role;
select * from finish();
rollback;

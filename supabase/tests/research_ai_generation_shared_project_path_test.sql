begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

-- This is a deterministic integration fixture.  It exercises the same
-- server-owned research completion and generated-artifact review seams as the
-- workers, but deliberately creates no provider attempt, HTTP request, or
-- storage mutation.  Its one synthetic succeeded job exercises the normal
-- server ledger and exact generated-claim lineage guards.

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    'ca000000-0000-4000-8000-000000000001',
    'shared-path-owner@example.test',
    'Shared Path Owner'
  ),
  (
    'ca000000-0000-4000-8000-000000000002',
    'shared-path-member@example.test',
    'Shared Path Member'
  ),
  (
    'ca000000-0000-4000-8000-000000000003',
    'shared-path-nonmember@example.test',
    'Shared Path Nonmember'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  'ca100000-0000-4000-8000-000000000001',
  'Research AI shared path pgTAP',
  'research-ai-shared-path-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'ca100000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000001',
    'owner',
    'active'
  ),
  (
    'ca100000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000002',
    'operator',
    'active'
  ),
  (
    'ca100000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000003',
    'operator',
    'active'
  );

-- Waivers are explicit test evidence only.  They make storage-read checks
-- about exact project membership instead of an unrelated training gate.
insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
) values
  (
    'ca100000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000001',
    'workspace_generation', 'active', 'owner', 'owner',
    'TEST-ONLY waiver for the bounded shared-path owner fixture.',
    'ca000000-0000-4000-8000-000000000001'
  ),
  (
    'ca100000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000002',
    'workspace_generation', 'active', 'operator', 'operator',
    'TEST-ONLY waiver for the exact shared-project member fixture.',
    'ca000000-0000-4000-8000-000000000001'
  ),
  (
    'ca100000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000003',
    'workspace_generation', 'active', 'operator', 'operator',
    'TEST-ONLY waiver isolating project ACL from the training gate.',
    'ca000000-0000-4000-8000-000000000001'
  );

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'ca000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values
  (
    'ca200000-0000-4000-8000-000000000001',
    'ca100000-0000-4000-8000-000000000001',
    null, 'Exact shared path project', 'blue', 'project', null,
    'active', 1024,
    'ca000000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000001'
  ),
  (
    'ca200000-0000-4000-8000-000000000002',
    'ca100000-0000-4000-8000-000000000001',
    null, 'Sibling denied project', 'violet', 'project', null,
    'active', 2048,
    'ca000000-0000-4000-8000-000000000001',
    'ca000000-0000-4000-8000-000000000001'
  );

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
)
select
  fixture.id::uuid,
  'ca100000-0000-4000-8000-000000000001'::uuid,
  'ca200000-0000-4000-8000-000000000001'::uuid,
  fixture.name,
  'blue',
  'folder',
  fixture.system_role,
  'active',
  fixture.position,
  'ca000000-0000-4000-8000-000000000001'::uuid,
  'ca000000-0000-4000-8000-000000000001'::uuid
from (values
  ('ca210000-0000-4000-8000-000000000001', 'Sources', 'sources', 5120),
  ('ca210000-0000-4000-8000-000000000002', 'Drafts', 'drafts', 4096),
  ('ca210000-0000-4000-8000-000000000003', 'Review', 'review', 3072),
  ('ca210000-0000-4000-8000-000000000004', 'Ready', 'ready', 2048),
  ('ca210000-0000-4000-8000-000000000005', 'Published', 'published', 1024)
) fixture(id, name, system_role, position);

select ok(
  (public.creator_grant_project_member(jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'profile_id', 'ca000000-0000-4000-8000-000000000002',
    'idempotency_key', 'shared-path-grant-member-0001'
  )) ->> 'ok')::boolean,
  'owner grants the second user only the exact project'
);

select ok(
  (public.creator_grant_project_member(jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'profile_id', 'ca000000-0000-4000-8000-000000000002',
    'idempotency_key', 'shared-path-reactivate-member-0001'
  )) ->> 'ok')::boolean,
  'a repeated grant reactivates the same primary-key membership'
);

select is(
  (
    select count(*)::integer
    from content_factory.workspace_project_memberships member_row
    where member_row.organization_id =
      'ca100000-0000-4000-8000-000000000001'
      and member_row.profile_id =
        'ca000000-0000-4000-8000-000000000002'
      and member_row.status = 'active'
  ),
  1,
  'the second user is not implicitly enrolled in the sibling project'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'ca300000-0000-4000-8000-000000000001',
  'ca100000-0000-4000-8000-000000000001',
  'SHARED-PATH-SKU-1',
  'Shared path detergent',
  'active',
  '{"brand":"Fixture","description":"Exact household product"}'::jsonb,
  'ca000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id,
  object_name, mime_type, size_bytes, sha256, status, metadata,
  idempotency_key
) values (
  'ca400000-0000-4000-8000-000000000001',
  'ca100000-0000-4000-8000-000000000001',
  'ca200000-0000-4000-8000-000000000001',
  'ca000000-0000-4000-8000-000000000001',
  'ca300000-0000-4000-8000-000000000001',
  'contentengine-private',
  'ca100000-0000-4000-8000-000000000001/'
    || 'ca000000-0000-4000-8000-000000000001/uploads/'
    || 'shared-path-source.webp',
  'image/webp',
  2048,
  repeat('1', 64),
  'ready',
  jsonb_build_object(
    'kind', 'product_photo',
    'original_filename', 'shared-path-source.webp',
    'rights_confirmed', true
  ),
  'shared-path-source-media-0001'
);

select is(
  (
    select media.artifact_class || ':' || media.lifecycle_stage
    from content_factory.media_objects media
    where media.id = 'ca400000-0000-4000-8000-000000000001'
  ),
  'source:sources',
  'research material is classified as a source, never generated output'
);

select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'ca400000-0000-4000-8000-000000000001'
  ),
  'sources',
  'the source material is filed in Sources'
);

create temporary table shared_path_context (
  start_result jsonb,
  claim_result jsonb,
  completion_result jsonb,
  queue_result jsonb,
  save_result jsonb,
  approval_result jsonb,
  decision_result jsonb,
  recommendation_result jsonb,
  prepare_result jsonb,
  binding_result jsonb,
  run_id uuid,
  draft_id uuid,
  human_draft_id uuid,
  receipt_id uuid,
  receipt_hash text,
  selection_id uuid
) on commit drop;

insert into shared_path_context (start_result)
select public.creator_start_project_research(jsonb_build_object(
  'organization_id', 'ca100000-0000-4000-8000-000000000001',
  'project_id', 'ca200000-0000-4000-8000-000000000001',
  'idempotency_key', 'shared-path-research-start-0001',
  'product_id', 'ca300000-0000-4000-8000-000000000001',
  'product_category', 'household',
  'objective',
    'Create a bounded evidence brief for one exact household product.',
  'marketplace_url', 'https://example.test/shared-path/product',
  'source_media_ids', jsonb_build_array(
    'ca400000-0000-4000-8000-000000000001'
  ),
  'platforms', jsonb_build_array('youtube'),
  'paid_analysis_ack', true
));

update shared_path_context
set run_id = (start_result #>> '{run,id}')::uuid;

select ok(
  (select start_result #>> '{run,status}' = 'queued'
     and start_result #>> '{run,project_id}' =
       'ca200000-0000-4000-8000-000000000001'
     and start_result #>> '{run,product_category}' = 'household'
   from shared_path_context),
  'project research starts with exact project, product, and AI category'
);

update shared_path_context context_row
set claim_result = public.system_claim_product_research(
  jsonb_build_object('run_id', context_row.run_id)
);

select ok(
  (select claim_result -> 'claimed' = 'true'::jsonb
     and claim_result #>> '{run,status}' = 'processing'
   from shared_path_context),
  'the audited worker seam claims the bounded local fixture'
);

select is(
  (
    select count(*)::integer
    from content_factory.research_run_provider_bindings provider_attempt
    where provider_attempt.run_id = (
      select context_row.run_id from shared_path_context context_row
    )
  ),
  0,
  'claiming the fixture does not create or invoke a provider attempt'
);

update shared_path_context context_row
set completion_result = public.system_complete_product_research(
  jsonb_build_object(
    'run_id', context_row.run_id,
    'status', 'completed',
    'summary', jsonb_build_object(
      'results', jsonb_build_array(
        'Exact package visibility is the strongest product cue.'
      ),
      'conclusions', jsonb_build_array(
        'Recommend one editable demonstration concept for the exact SKU.'
      ),
      'category_analysis', jsonb_build_object(
        'category', 'household',
        'finding', 'Trust grows when the product is shown without overclaiming.'
      ),
      'trend_analysis', jsonb_build_object(
        'finding', 'Short demonstrations remain a useful test format.'
      )
    ),
    'sources', jsonb_build_array(
      jsonb_build_object(
        'source_type', 'review',
        'source_url', 'https://example.test/shared-path/review',
        'title', 'Bounded public review evidence',
        'trust_level', 'public',
        'extracted_facts', jsonb_build_array(jsonb_build_object(
          'statement', 'Buyers ask to see the exact package.',
          'source_ids', jsonb_build_array('review:1')
        )),
        'metadata', jsonb_build_object('model_source_id', 'review:1')
      ),
      jsonb_build_object(
        'source_type', 'product_photo',
        'media_object_id',
          'ca400000-0000-4000-8000-000000000001',
        'title', 'Exact package visual analysis',
        'trust_level', 'first_party',
        'extracted_facts', jsonb_build_array(jsonb_build_object(
          'statement', 'The exact product package is visible.',
          'source_ids', jsonb_build_array('photo:1')
        )),
        'metadata', jsonb_build_object(
          'model_source_id', 'photo:1',
          'visual_analysis', true
        )
      )
    ),
    'draft', jsonb_build_object(
      'title', 'Exact product demonstration brief',
      'brief', jsonb_build_object(
        'category_analysis', jsonb_build_object(
          'finding', 'Use an honest product demonstration.'
        ),
        'competitor_analysis', jsonb_build_object(
          'finding', 'Avoid unverifiable comparisons.'
        ),
        'trend_analysis', jsonb_build_object(
          'finding', 'A concise visual proof is suitable for testing.'
        ),
        'guidance', jsonb_build_object(
          'status', 'ready_for_brief',
          'recommendation', 'Keep every preset editable.'
        ),
        'audience', jsonb_build_array('Household product buyer'),
        'pains', jsonb_build_array('Unclear package identity'),
        'objections', jsonb_build_array('Is this the exact product?'),
        'claims', jsonb_build_array('Show only observable details.'),
        'facts', jsonb_build_array('Exact source image is registered.'),
        'creative_potential', jsonb_build_object('score', 0.82),
        'scenarios', jsonb_build_array(jsonb_build_object(
          'position', 1,
          'title', 'One honest product detail',
          'platform', 'tiktok',
          'recommended_generation_mode', 'seedance2_fast',
          'duration_seconds', 8,
          'format', '9:16',
          'hook', 'Watch one honest product detail?',
          'shot_list', jsonb_build_array(
            'Show the exact package in one clear frame.'
          ),
          'goal', 'Demonstrate exact product identity.',
          'cta', 'Review the product details.'
        ))
      ),
      'task_blueprint', jsonb_build_array(jsonb_build_object(
        'title', 'Review the exact product concept',
        'instructions', 'Check that the package identity remains exact.',
        'task_type', 'general',
        'assignee_id', 'ca000000-0000-4000-8000-000000000001',
        'priority', 2,
        'payout_minor', 0
      ))
    ),
    'forecast', jsonb_build_object(
      'score', 82,
      'confidence', 0.71,
      'model_provider', 'deterministic_fixture',
      'model_version', 'shared-path-v1',
      'factors', jsonb_build_object('exact_product', 0.9),
      'limitations', jsonb_build_array(
        'No external provider is invoked by this pgTAP fixture.'
      )
    )
  )
);

update shared_path_context
set draft_id = (completion_result ->> 'draft_id')::uuid,
    receipt_id = (completion_result #>> '{ai_handoff,receipt_id}')::uuid;

update shared_path_context context_row
set receipt_hash = receipt.receipt_hash
from content_factory.ai_research_evidence_receipts receipt
where receipt.id = context_row.receipt_id;

select ok(
  (select completion_result ->> 'status' = 'completed'
     and completion_result #>> '{ai_handoff,status}' =
       'awaiting_human_review'
     and completion_result #>> '{ai_handoff,product_category}' = 'household'
   from shared_path_context),
  'authoritative completion atomically creates the AI Center receipt'
);

select ok(
  exists (
    select 1
    from shared_path_context context_row
    join content_factory.product_research_runs run
      on run.id = context_row.run_id
     and run.project_id =
       'ca200000-0000-4000-8000-000000000001'
     and run.status = 'completed'
    join content_factory.creative_brief_drafts draft
      on draft.id = context_row.draft_id
     and draft.run_id = run.id
     and draft.project_id = run.project_id
    join content_factory.ai_research_evidence_receipts receipt
      on receipt.id = context_row.receipt_id
     and receipt.run_id = run.id
     and receipt.draft_id = draft.id
     and receipt.project_id = run.project_id
  ),
  'run, immutable result draft, and receipt share one exact project lineage'
);

update shared_path_context
set queue_result = public.contentengine_ai_research_training_queue(
  jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'limit', 10
  )
);

select ok(
  (select queue_result ->> 'project_id' =
       'ca200000-0000-4000-8000-000000000001'
     and jsonb_array_length(queue_result -> 'queue') = 1
     and queue_result #>> '{queue,0,run_id}' = run_id::text
     and queue_result #>> '{queue,0,receipt_id}' = receipt_id::text
     and queue_result #>> '{queue,0,research_summary,results,0}' =
       'Exact package visibility is the strongest product cue.'
     and queue_result #>> '{queue,0,research_summary,conclusions,0}' =
       'Recommend one editable demonstration concept for the exact SKU.'
     and queue_result #>> '{queue,0,analysis,guidance,recommendation}' =
       'Keep every preset editable.'
     and jsonb_array_length(queue_result #> '{queue,0,sources}') >= 2
     and exists (
       select 1
       from jsonb_array_elements(
         queue_result #> '{queue,0,sources}'
       ) source_item(value)
       where source_item.value #>> '{media,project_id}' =
         'ca200000-0000-4000-8000-000000000001'
     )
   from shared_path_context),
  'AI Center receives material, results, conclusions, analysis, and scenarios'
);

-- Production never approves the provider-authored v2 draft directly.  The
-- operator first saves an explicit human draft, preserving the immutable AI
-- evidence sections and exact source set, and only then approves that version.
update shared_path_context context_row
set save_result = public.creator_save_project_creative_brief_draft(
  jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'run_id', context_row.run_id,
    'title', ai_draft.title,
    'brief', ai_draft.brief,
    'source_ids', ai_draft.source_ids,
    'task_blueprint', ai_draft.task_blueprint,
    'idempotency_key', 'shared-path-brief-human-save-0001'
  )
)
from content_factory.creative_brief_drafts ai_draft
where ai_draft.id = context_row.draft_id;

update shared_path_context
set human_draft_id = (save_result #>> '{draft,id}')::uuid;

select ok(
  exists (
    select 1
    from shared_path_context context_row
    join content_factory.creative_brief_drafts human_draft
      on human_draft.id = context_row.human_draft_id
     and human_draft.previous_draft_id = context_row.draft_id
     and human_draft.run_id = context_row.run_id
     and human_draft.project_id =
       'ca200000-0000-4000-8000-000000000001'
     and human_draft.origin = 'human'
     and human_draft.status = 'draft'
  ),
  'operator saves a project-bound human draft before approval'
);

update shared_path_context context_row
set approval_result = public.creator_approve_project_creative_brief(
  jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'draft_id', context_row.human_draft_id,
    'idempotency_key', 'shared-path-brief-approve-0001'
  )
);

select ok(
  (select approval_result ->> 'draft_id' = human_draft_id::text
     and approval_result ->> 'project_id' =
       'ca200000-0000-4000-8000-000000000001'
   from shared_path_context),
  'the human-reviewed research result becomes approved generation provenance'
);

update shared_path_context context_row
set decision_result = public.contentengine_decide_ai_research_training(
  jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'receipt_id', context_row.receipt_id,
    'receipt_hash', context_row.receipt_hash,
    'decision', 'approve',
    'selected_insight_keys', jsonb_build_array(
      'category', 'trends', 'brief'
    ),
    'selected_scenario_positions', jsonb_build_array(1),
    'operator_notes', 'Use this as editable advice, not a mandatory command.',
    'confirmation', true,
    'idempotency_key', 'shared-path-ai-training-decision-0001'
  )
);

update shared_path_context
set selection_id =
  (decision_result #>> '{selection,selection_id}')::uuid;

select ok(
  (select decision_result #>> '{selection,decision}' = 'approve'
     and decision_result #> '{selection,selected_insight_keys}' =
       '["category","trends","brief"]'::jsonb
     and decision_result #> '{selection,selected_scenario_positions}' =
       '[1]'::jsonb
     and jsonb_array_length(
       decision_result #> '{selection,recommendations}'
     ) = 1
     and decision_result #>> '{snapshot,project_id}' =
       'ca200000-0000-4000-8000-000000000001'
     and jsonb_array_length(decision_result #> '{snapshot,queue}') = 0
     and decision_result #>> '{snapshot,learned,0,selection_id}' =
       selection_id::text
   from shared_path_context),
  'human selection produces one learned recommendation and a scoped replay'
);

update shared_path_context
set recommendation_result =
  public.contentengine_generation_research_recommendations(
    jsonb_build_object(
      'organization_id', 'ca100000-0000-4000-8000-000000000001',
      'project_id', 'ca200000-0000-4000-8000-000000000001',
      'product_id', 'ca300000-0000-4000-8000-000000000001',
      'product_category', 'household',
      'product_name', 'Shared path detergent',
      'sku', 'SHARED-PATH-SKU-1',
      'platform', 'tiktok',
      'limit', 3
    )
  );

select ok(
  (select recommendation_result -> 'auto_apply_available' = 'true'::jsonb
     and recommendation_result #>> '{recommendations,0,selection_id}' =
       selection_id::text
     and recommendation_result #>> '{recommendations,0,product_id}' =
       'ca300000-0000-4000-8000-000000000001'
     and recommendation_result #>> '{recommendations,0,scope_match}' =
       'exact_product'
     and recommendation_result #>> '{recommendations,0,match_basis}' =
       'product_id'
     and recommendation_result #>> '{recommendations,0,preset,platform}' =
       'tiktok'
     and recommendation_result #>>
       '{recommendations,0,preset,generation_mode}' = 'real_seedance'
     and recommendation_result #>> '{recommendations,0,preset,format}' =
       '9:16'
     and recommendation_result #>>
       '{recommendations,0,preset,duration_seconds}' = '8'
     and recommendation_result #> '{contract,presets_are_advisory}' =
       'true'::jsonb
     and recommendation_result #> '{contract,recommendations_are_editable}' =
       'true'::jsonb
     and recommendation_result #> '{contract,spend_confirmation_is_never_applied}' =
       'true'::jsonb
     and recommendation_result #> '{contract,paid_call_started}' =
       'false'::jsonb
   from shared_path_context),
  'Generation receives one editable advisory preset for the exact product'
);

update shared_path_context context_row
set prepare_result = public.creator_prepare_generation_spec(
  jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'idempotency_key', 'shared-path-generation-spec-prepare-0001',
    'exact_scope', jsonb_build_object(
      'primary_media_id', 'ca400000-0000-4000-8000-000000000001',
      'media_ids', jsonb_build_array(
        'ca400000-0000-4000-8000-000000000001'
      ),
      'platform', 'tiktok',
      'model', 'seedance2_fast',
      'duration_seconds', 8,
      'product_category', 'household',
      'format', '9:16',
      'audio', true
    ),
    'editable_intent',
      'Show the exact product in one editable, honest vertical sequence.',
    'proposed_prompt',
      'Create one continuous eight-second vertical product video from the '
        || 'exact registered package. Preserve label, shape, colors, '
        || 'proportions, and observable facts. Do not invent performance '
        || 'claims, text, logos, or another product.',
    -- Keep preparation on the provider-free baseline contract.  The
    -- separately confirmed append-only binding below is the durable seam
    -- from the selected AI recommendation into this exact editable spec.
    -- Using approved_research provenance here would additionally require the
    -- unrelated market-category readiness subsystem and its rule receipt.
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
    'reason',
      'Prepare an editable spec from the explicitly selected AI advice.'
  )
);

select ok(
  (select prepare_result #>> '{generation_spec,status}' = 'draft'
     and prepare_result #>>
       '{generation_spec,exact_scope,primary_media_id}' =
       'ca400000-0000-4000-8000-000000000001'
     and prepare_result #>> '{generation_spec,exact_scope,product_category}' =
       'household'
     and prepare_result #>> '{generation_spec,exact_scope,model}' =
       'seedance2_fast'
     and prepare_result #> '{generation_spec,research_provenance}' =
       'null'::jsonb
     and exists (
       select 1
       from content_factory.generation_spec_versions version
       where version.spec_id = (prepare_result #>>
               '{generation_spec,spec_id}')::uuid
         and version.spec_version = (prepare_result #>>
               '{generation_spec,spec_version}')::integer
         and version.spec_hash = prepare_result #>>
               '{generation_spec,spec_hash}'
         and version.research_provenance is null
         and version.canonical_learning_context ->> 'source' = 'baseline'
     )
     and prepare_result -> 'automatic_approval' = 'false'::jsonb
     and prepare_result -> 'automatic_spend' = 'false'::jsonb
     and prepare_result -> 'automatic_generation' = 'false'::jsonb
   from shared_path_context),
  'human prepares an editable spec without automatic actions or spend'
);

update shared_path_context context_row
set binding_result = public.contentengine_bind_generation_spec_ai_research(
  jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'spec_id', context_row.prepare_result #>> '{generation_spec,spec_id}',
    'spec_version',
      (context_row.prepare_result #>>
        '{generation_spec,spec_version}')::integer,
    'spec_hash',
      context_row.prepare_result #>> '{generation_spec,spec_hash}',
    'selection_id', context_row.selection_id,
    'recommendation_position', 1,
    'confirmation', true
  )
);

select ok(
  exists (
    select 1
    from shared_path_context context_row
    join content_factory.generation_spec_ai_research_bindings binding
      on binding.id =
        (context_row.binding_result #>> '{binding,id}')::uuid
     and binding.project_id =
       'ca200000-0000-4000-8000-000000000001'
     and binding.spec_id =
       (context_row.prepare_result #>> '{generation_spec,spec_id}')::uuid
     and binding.spec_version =
       (context_row.prepare_result #>>
         '{generation_spec,spec_version}')::integer
     and binding.spec_hash =
       context_row.prepare_result #>> '{generation_spec,spec_hash}'
     and binding.selection_id = context_row.selection_id
     and binding.recommendation_position = 1
    join content_factory.ai_research_learning_selections selection
      on selection.organization_id = binding.organization_id
     and selection.id = binding.selection_id
     and binding.selection_hash = selection.selection_hash
     and binding.recommendation_snapshot = selection.recommendations -> 0
     and binding.recommendation_hash =
       content_factory_private.json_hash(selection.recommendations -> 0)
  )
  and (select binding_result #> '{contract,provider_call_started}' =
         'false'::jsonb
       and binding_result #> '{contract,paid_call_started}' =
         'false'::jsonb
       from shared_path_context),
  'append-only binding references the exact selection and exact spec version'
);

-- Materialize the minimum production-faithful succeeded-job lineage required
-- for a generated artifact.  These rows are deterministic fixture evidence:
-- no provider API is called, while the normal spend ledger and review guards
-- remain active and fail closed exactly as they do in production.
insert into content_factory.generation_spend_policies (
  organization_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, timezone, version, reason, updated_by
) values (
  'ca100000-0000-4000-8000-000000000001', true,
  2500, 10000, 500, 'USD', 'Europe/Moscow', 1,
  'Shared-path deterministic generated-result fixture policy.',
  'ca000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_batches (
  id, organization_id, project_id, product_id, created_by, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key,
  provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency
) values (
  'ca600000-0000-4000-8000-000000000001',
  'ca100000-0000-4000-8000-000000000001',
  'ca200000-0000-4000-8000-000000000001',
  'ca300000-0000-4000-8000-000000000001',
  'ca000000-0000-4000-8000-000000000001',
  'Shared path deterministic Seedance result',
  'real', true, 'succeeded', 1, 1,
  jsonb_build_object(
    'job_id', 'ca600000-0000-4000-8000-000000000002',
    'provider', 'runway',
    'model', 'seedance2_fast',
    'duration_seconds', 8,
    'audio', true,
    'format', '9:16',
    'ratio', '720:1280',
    'spend_confirmation',
      'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 232,
      'estimated_credits', 232,
      'credit_unit_usd_minor', 1
    )
  ),
  repeat('5', 64),
  'shared-path-seedance-batch-0001',
  'runway', 'seedance2_fast', 8, true, 232, 232, 'USD'
);

-- TEST-ONLY: the synthetic terminal job is inserted directly because this
-- network-free fixture cannot run the provider worker that normally binds an
-- approved generation-spec version under its private transaction GUC.  Keep
-- the lifecycle and spend triggers active; bypass only that insert-time spec
-- gate while assembling the exact terminal job lineage.
alter table content_factory.generation_jobs
  disable trigger a_generation_spec_binding_guard;

insert into content_factory.generation_jobs (
  id, organization_id, project_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status,
  input, output, request_hash, idempotency_key
) values (
  'ca600000-0000-4000-8000-000000000002',
  'ca100000-0000-4000-8000-000000000001',
  'ca200000-0000-4000-8000-000000000001',
  'ca300000-0000-4000-8000-000000000001',
  'ca600000-0000-4000-8000-000000000001',
  1,
  'ca000000-0000-4000-8000-000000000001',
  'ca000000-0000-4000-8000-000000000001',
  'real', 'runway', true, 232, 232, 'succeeded',
  jsonb_build_object(
    'sku', 'SHARED-PATH-SKU-1',
    'product_name', 'Shared path detergent',
    'prompt_text',
      'Deterministic fixture prompt; no provider request is performed.',
    'provider', 'runway',
    'model', 'seedance2_fast',
    'duration_seconds', 8,
    'audio', true,
    'format', '9:16',
    'ratio', '720:1280',
    'input_object_name',
      'ca100000-0000-4000-8000-000000000001/'
        || 'ca000000-0000-4000-8000-000000000001/uploads/'
        || 'shared-path-source.webp',
    'output_object_name',
      'ca100000-0000-4000-8000-000000000001/'
        || 'ca000000-0000-4000-8000-000000000001/generated/'
        || 'shared-path-output.mp4',
    'platform', 'tiktok',
    'destination_ref', 'shared-path-deterministic-fixture',
    'spend_confirmation',
      'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32',
    'billing', jsonb_build_object(
      'currency', 'USD',
      'estimated_cost_minor', 232,
      'estimated_credits', 232,
      'credit_unit_usd_minor', 1
    )
  ),
  jsonb_build_object(
    'provider_task_id', 'provider-shared-path-deterministic-fixture',
    'output_object_name',
      'ca100000-0000-4000-8000-000000000001/'
        || 'ca000000-0000-4000-8000-000000000001/generated/'
        || 'shared-path-output.mp4',
    'output_media_id', 'ca400000-0000-4000-8000-000000000002',
    'mime_type', 'video/mp4',
    'sha256', repeat('2', 64)
  ),
  repeat('6', 64),
  'shared-path-seedance-job-0001'
);

alter table content_factory.generation_jobs
  enable trigger a_generation_spec_binding_guard;

-- The lifecycle itself remains authoritative and runs through the production
-- classification/review triggers: Drafts -> Review -> Ready.
insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id,
  object_name, mime_type, size_bytes, sha256, status, metadata,
  idempotency_key
)
select
  'ca400000-0000-4000-8000-000000000002'::uuid,
  'ca100000-0000-4000-8000-000000000001'::uuid,
  'ca200000-0000-4000-8000-000000000001'::uuid,
  'ca000000-0000-4000-8000-000000000001'::uuid,
  'ca300000-0000-4000-8000-000000000001'::uuid,
  'contentengine-private',
  'ca100000-0000-4000-8000-000000000001/'
    || 'ca000000-0000-4000-8000-000000000001/generated/'
    || 'shared-path-output.mp4',
  'video/mp4',
  4096,
  repeat('2', 64),
  'ready',
  jsonb_build_object(
    'kind', 'generated_video',
    'original_filename', 'shared-path-output.mp4',
    'rights_confirmed', true,
    'provider', 'runway',
    'model', 'seedance2_fast',
    'audio', true,
    'generation_job_id', 'ca600000-0000-4000-8000-000000000002',
    'ai_research_selection_id', context_row.selection_id,
    'ai_research_binding_id', context_row.binding_result #>> '{binding,id}',
    'generation_spec_id', context_row.prepare_result #>>
      '{generation_spec,spec_id}',
    'generation_spec_version', (context_row.prepare_result #>>
      '{generation_spec,spec_version}')::integer,
    'generation_spec_hash', context_row.prepare_result #>>
      '{generation_spec,spec_hash}'
  ),
  'shared-path-generated-media-0001'
from shared_path_context context_row;

select is(
  (
    select media.artifact_class || ':' || media.lifecycle_stage
    from content_factory.media_objects media
    where media.id = 'ca400000-0000-4000-8000-000000000002'
  ),
  'generated_output:drafts',
  'generated material is separate from research input and starts in Drafts'
);

select ok(
  exists (
    select 1
    from shared_path_context context_row
    join content_factory.media_objects media
      on media.id = 'ca400000-0000-4000-8000-000000000002'
     and media.metadata ->> 'ai_research_selection_id' =
       context_row.selection_id::text
     and media.metadata ->> 'ai_research_binding_id' =
       context_row.binding_result #>> '{binding,id}'
     and media.metadata ->> 'generation_spec_id' =
       context_row.prepare_result #>> '{generation_spec,spec_id}'
     and media.metadata ->> 'generation_spec_version' =
       context_row.prepare_result #>> '{generation_spec,spec_version}'
     and media.metadata ->> 'generation_spec_hash' =
       context_row.prepare_result #>> '{generation_spec,spec_hash}'
  ),
  'the deterministic generated fixture retains exact advice and spec lineage'
);

select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'ca400000-0000-4000-8000-000000000002'
  ),
  'drafts',
  'the generated output is filed in Drafts'
);

insert into content_factory.content_review_runs (
  id, organization_id, project_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, result, moderation, ruleset_version,
  model_provider, model_version, request_hash, completion_hash,
  idempotency_key, finished_at
) values (
  'ca500000-0000-4000-8000-000000000001',
  'ca100000-0000-4000-8000-000000000001',
  'ca200000-0000-4000-8000-000000000001',
  'ca400000-0000-4000-8000-000000000002',
  'ca000000-0000-4000-8000-000000000001',
  'completed',
  repeat('2', 64),
  jsonb_build_object(
    'content_kind', 'organic',
    'generation_job_id', 'ca600000-0000-4000-8000-000000000002'
  ),
  jsonb_build_object(
    'overall_score', 98,
    'blockers_count', 0,
    'compliance_status', 'pass'
  ),
  '{}'::jsonb,
  'shared-path-review-v1',
  'deterministic_fixture',
  '1',
  repeat('3', 64),
  repeat('4', 64),
  'shared-path-review-run-0001',
  now()
);

select is(
  (
    select media.lifecycle_stage
    from content_factory.media_objects media
    where media.id = 'ca400000-0000-4000-8000-000000000002'
  ),
  'review',
  'a completed server review routes generated material to Review'
);

select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'ca400000-0000-4000-8000-000000000002'
  ),
  'review',
  'the generated output is filed in Review'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'ca000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

insert into content_factory.content_review_decisions (
  id, organization_id, review_id, decided_by, decision, comment,
  resolved_recommendation_codes, risk_acknowledgements,
  media_watched_confirmed, review_completion_hash,
  media_sha256_snapshot, idempotency_key
) values (
  'ca500000-0000-4000-8000-000000000002',
  'ca100000-0000-4000-8000-000000000001',
  'ca500000-0000-4000-8000-000000000001',
  'ca000000-0000-4000-8000-000000000002',
  'approved',
  'Second project member approved the exact generated fixture.',
  '[]'::jsonb,
  '[]'::jsonb,
  true,
  repeat('4', 64),
  repeat('2', 64),
  'shared-path-review-decision-0001'
);

select is(
  (
    select media.lifecycle_stage
    from content_factory.media_objects media
    where media.id = 'ca400000-0000-4000-8000-000000000002'
  ),
  'ready',
  'an immutable approval routes generated material to Ready'
);

select is(
  (
    select folder.system_role
    from content_factory.workspace_media_locations location
    join content_factory.workspace_folders folder
      on folder.organization_id = location.organization_id
     and folder.id = location.folder_id
    where location.media_object_id =
      'ca400000-0000-4000-8000-000000000002'
  ),
  'ready',
  'the approved output is filed in Ready'
);

select ok(
  (
    public.creator_project_media(jsonb_build_object(
      'organization_id', 'ca100000-0000-4000-8000-000000000001',
      'project_id', 'ca200000-0000-4000-8000-000000000001',
      'media_id', 'ca400000-0000-4000-8000-000000000002',
      'surface', 'generation'
    )) #>> '{media,lifecycle_stage}'
  ) = 'ready',
  'the second member reads the exact shared generated media'
);

select ok(
  content_factory.storage_project_read_allowed(
    'contentengine-private',
    'ca100000-0000-4000-8000-000000000001/'
      || 'ca000000-0000-4000-8000-000000000001/generated/'
      || 'shared-path-output.mp4'
  ),
  'the second member may read the exact shared storage object'
);

create temporary table member_shared_snapshot on commit drop as
select
  public.contentengine_ai_research_training_queue(jsonb_build_object(
    'organization_id', 'ca100000-0000-4000-8000-000000000001',
    'project_id', 'ca200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'limit', 10
  )) as queue_value,
  public.contentengine_generation_research_recommendations(
    jsonb_build_object(
      'organization_id', 'ca100000-0000-4000-8000-000000000001',
      'project_id', 'ca200000-0000-4000-8000-000000000001',
      'product_id', 'ca300000-0000-4000-8000-000000000001',
      'product_category', 'household',
      'platform', 'tiktok',
      'limit', 3
    )
  ) as recommendation_value,
  public.contentengine_generation_spec_ai_research_binding(
    jsonb_build_object(
      'organization_id', 'ca100000-0000-4000-8000-000000000001',
      'project_id', 'ca200000-0000-4000-8000-000000000001',
      'spec_id', context_row.prepare_result #>> '{generation_spec,spec_id}',
      'spec_version',
        (context_row.prepare_result #>>
          '{generation_spec,spec_version}')::integer,
      'spec_hash',
        context_row.prepare_result #>> '{generation_spec,spec_hash}'
    )
  ) as binding_value
from shared_path_context context_row;

select ok(
  (select jsonb_array_length(queue_value -> 'queue') = 0
     and queue_value #>> '{learned,0,selection_id}' =
       (select selection_id::text from shared_path_context)
     and queue_value #>> '{learned,0,research_summary,conclusions,0}' =
       'Recommend one editable demonstration concept for the exact SKU.'
     and jsonb_array_length(
       queue_value #> '{learned,0,material_snapshot}'
     ) >= 2
     and recommendation_value #>> '{recommendations,0,selection_id}' =
       (select selection_id::text from shared_path_context)
     and recommendation_value #> '{contract,presets_are_advisory}' =
       'true'::jsonb
     and binding_value #>> '{binding,selection_id}' =
       (select selection_id::text from shared_path_context)
   from member_shared_snapshot),
  'the second member sees learned conclusions, material, advice, and binding'
);

select throws_ok(
  $$
    select public.contentengine_ai_research_training_queue(
      jsonb_build_object(
        'organization_id', 'ca100000-0000-4000-8000-000000000001',
        'project_id', 'ca200000-0000-4000-8000-000000000002',
        'product_category', 'household'
      )
    )
  $$,
  '42501',
  'workspace_project_access_required',
  'the exact member cannot read the sibling-project AI queue'
);

select throws_ok(
  $$
    select public.creator_project_media(jsonb_build_object(
      'organization_id', 'ca100000-0000-4000-8000-000000000001',
      'project_id', 'ca200000-0000-4000-8000-000000000002',
      'media_id', 'ca400000-0000-4000-8000-000000000002',
      'surface', 'generation'
    ))
  $$,
  '42501',
  'workspace_project_access_required',
  'the exact member cannot probe media through a sibling project'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'ca000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.contentengine_ai_research_training_queue(
      jsonb_build_object(
        'organization_id', 'ca100000-0000-4000-8000-000000000001',
        'project_id', 'ca200000-0000-4000-8000-000000000001',
        'product_category', 'household'
      )
    )
  $$,
  '42501',
  'workspace_project_access_required',
  'an organization member without exact project access cannot read AI data'
);

select throws_ok(
  $$
    select public.creator_project_media(jsonb_build_object(
      'organization_id', 'ca100000-0000-4000-8000-000000000001',
      'project_id', 'ca200000-0000-4000-8000-000000000001',
      'media_id', 'ca400000-0000-4000-8000-000000000002',
      'surface', 'generation'
    ))
  $$,
  '42501',
  'workspace_project_access_required',
  'a nonmember cannot read exact-project generated media'
);

select is(
  content_factory.storage_project_read_allowed(
    'contentengine-private',
    'ca100000-0000-4000-8000-000000000001/'
      || 'ca000000-0000-4000-8000-000000000001/generated/'
      || 'shared-path-output.mp4'
  ),
  false,
  'a nonmember cannot read the exact-project storage object'
);

select is(
  (
    select jsonb_build_object(
      'provider_attempts', (
        select count(*)
        from content_factory.research_run_provider_bindings provider_attempt
        where provider_attempt.run_id = context_row.run_id
      ),
      'generation_batches', (
        select count(*)
        from content_factory.generation_batches batch
        where batch.organization_id =
          'ca100000-0000-4000-8000-000000000001'
      ),
      'generation_jobs', (
        select count(*)
        from content_factory.generation_jobs job
        where job.organization_id =
          'ca100000-0000-4000-8000-000000000001'
      ),
      'spend_entries', (
        select count(*)
        from content_factory.generation_spend_ledger spend
        where spend.organization_id =
          'ca100000-0000-4000-8000-000000000001'
      )
    )
    from shared_path_context context_row
  ),
  jsonb_build_object(
    'provider_attempts', 0,
    'generation_batches', 1,
    'generation_jobs', 1,
    'spend_entries', 2
  ),
  'the fixture is bounded: no provider call and exact synthetic accounting'
);

select * from finish();
rollback;

begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select ok(
  to_regprocedure(
    'content_factory_private.generation_strategy_mechanics_summary_v1(jsonb)'
  ) is not null,
  'structured mechanics normalizer is installed'
);
select ok(
  to_regprocedure(
    'content_factory_private.generation_strategy_selection_snapshot_valid_v1(jsonb)'
  ) is not null,
  'immutable strategy selection validator is installed'
);
select ok(
  to_regprocedure(
    'content_factory_private.generation_strategy_spec_scope_v1(jsonb)'
  ) is not null,
  'explicit strategy recipe spec scope is installed'
);
select ok(
  to_regprocedure(
    'public.creator_prepare_generation_strategy_spec(jsonb)'
  ) is not null,
  'free strategy spec prepare RPC is installed'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_prepare_generation_strategy_spec(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_prepare_generation_strategy_spec(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_prepare_generation_strategy_spec(jsonb)', 'execute'
  ),
  'prepare RPC is authenticated-human only'
);

select ok(
  exists (
    select 1
    from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid =
      'content_factory.generation_spec_versions'::regclass
      and constraint_row.conname =
        'generation_spec_versions_v1_v2_or_strategy_scope_check'
      and constraint_row.contype = 'c'
      and constraint_row.convalidated
  ),
  'generation specs have the validated strategy scope branch'
);

select ok(
  exists (
    select 1
    from pg_catalog.pg_trigger trigger_row
    where trigger_row.tgrelid =
      'content_factory.generation_spec_versions'::regclass
      and trigger_row.tgname =
        'b_generation_strategy_spec_scope_v1_bind'
      and not trigger_row.tgisinternal
  ),
  'strategy recipe fields are bound before spec insert'
);
select ok(
  exists (
    select 1
    from pg_catalog.pg_trigger trigger_row
    where trigger_row.tgrelid =
      'content_factory.generation_spec_strategy_bindings'::regclass
      and trigger_row.tgname =
        'a_generation_strategy_spec_authority_guard'
      and not trigger_row.tgisinternal
  ),
  'frozen strategy bind request is guarded by approved spec authority'
);

select ok(
  position(
    'generation_strategy_spec_scope_v1' in pg_catalog.pg_get_functiondef(
      'content_factory_private.create_generation_spec_version(uuid,uuid,uuid,jsonb,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,uuid,text,uuid)'::regprocedure
    )
  ) > 0
  and position(
    'exact_scope_value ->> ''recipe''' in pg_catalog.pg_get_functiondef(
      'content_factory_private.create_generation_spec_version(uuid,uuid,uuid,jsonb,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,uuid,text,uuid)'::regprocedure
    )
  ) > 0
  and position(
    'generation-strategy-spec-v1' in pg_catalog.pg_get_functiondef(
      'content_factory_private.create_generation_spec_version(uuid,uuid,uuid,jsonb,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,uuid,text,uuid)'::regprocedure
    )
  ) > 0,
  'installed mature compiler recognizes explicit recipe scope without proxy'
);

select is(
  content_factory_private.generation_strategy_mechanics_summary_v1(
    jsonb_build_object(
      'version', 'generation-strategy-mechanics-summary-v1',
      'hook', 'Hands reveal the problem before the product enters frame.',
      'beat_sequence', jsonb_build_array(
        'Open on the practical pain point in one readable action.',
        'Introduce the product and demonstrate the useful transformation.'
      ),
      'pacing', 'Fast opening, measured proof, then a clean close.',
      'camera_language', 'Handheld close-up followed by a stable product detail.',
      'composition', 'Keep the action central and the product label readable.',
      'audio_pattern', 'Short spoken hook with quiet demonstration sounds.',
      'cta_pattern', 'Close with one direct benefit-led invitation.'
    )
  ) ->> 'hook',
  'Hands reveal the problem before the product enters frame.',
  'nontrivial structured mechanics normalize exactly'
);

select is(
  content_factory_private.generation_strategy_mechanics_summary_v1(
    jsonb_build_object(
      'version', 'generation-strategy-mechanics-summary-v1',
      'hook', 'too short',
      'beat_sequence', jsonb_build_array('only one beat'),
      'pacing', 'quick',
      'camera_language', 'camera',
      'composition', 'center',
      'audio_pattern', 'speech',
      'cta_pattern', 'buy'
    )
  ),
  null::jsonb,
  'trivial mechanics fail closed'
);

with selection_value as (
  select jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_avatar_ugc',
    'recipe_version', '2026-06',
    'duration_seconds', 4,
    'ratio', '720:1280',
    'audio', true,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video',
        'media_id', '10000000-0000-4000-8000-000000000001'
      ),
      jsonb_build_object(
        'role', 'avatar_image',
        'media_id', '20000000-0000-4000-8000-000000000002'
      ),
      jsonb_build_object(
        'role', 'product_image',
        'media_id', '30000000-0000-4000-8000-000000000003'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true,
      'avatar_likeness_consent_confirmed', true
    )
  ) as value
)
select ok(
  content_factory_private.generation_strategy_selection_snapshot_valid_v1(
    value
  ),
  'UGC exact selection is valid without a GenerationModel identity'
)
from selection_value;

with selection_value as (
  select jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_product_swap',
    'recipe_version', '2026-06',
    'duration_seconds', 4,
    'resolution', '720p',
    'audio', true,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video',
        'media_id', '10000000-0000-4000-8000-000000000001',
        'duration_seconds', 4
      ),
      jsonb_build_object(
        'role', 'original_product_image',
        'media_id', '20000000-0000-4000-8000-000000000002'
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', '30000000-0000-4000-8000-000000000003',
        'view', 'front'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true
    )
  ) as value
)
select ok(
  content_factory_private.generation_strategy_selection_snapshot_valid_v1(
    value
  ),
  'Product Swap exact selection preserves the source MP4 contract'
)
from selection_value;

with
selection_value as (
  select jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_avatar_ugc',
    'recipe_version', '2026-06',
    'duration_seconds', 4,
    'ratio', '720:1280',
    'audio', true,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video',
        'media_id', '10000000-0000-4000-8000-000000000001'
      ),
      jsonb_build_object(
        'role', 'avatar_image',
        'media_id', '20000000-0000-4000-8000-000000000002'
      ),
      jsonb_build_object(
        'role', 'product_image',
        'media_id', '30000000-0000-4000-8000-000000000003'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true,
      'avatar_likeness_consent_confirmed', true
    )
  ) as value
),
source_value as (
  select jsonb_build_object(
    'version', 'generation-strategy-exact-source-snapshot-v1',
    'attachment_id', '40000000-0000-4000-8000-000000000004',
    'attachment_hash', repeat('a', 64),
    'source_id', '60000000-0000-4000-8000-000000000006',
    'source_hash', repeat('b', 64),
    'media_object_id', '10000000-0000-4000-8000-000000000001',
    'media_sha256', repeat('c', 64),
    'size_bytes', 4096,
    'duration_seconds', 'null'::jsonb
  ) as value
),
asset_snapshot_value as (
  select jsonb_build_array(
    jsonb_build_object(
      'selection_role', 'source_video',
      'selection_ordinal', 1,
      'media_id', '10000000-0000-4000-8000-000000000001',
      'sha256', repeat('c', 64),
      'kind', 'source_video',
      'mime_type', 'video/mp4',
      'product_id', 'null'::jsonb,
      'rights_confirmed', true
    ),
    jsonb_build_object(
      'selection_role', 'avatar_image',
      'selection_ordinal', 2,
      'media_id', '20000000-0000-4000-8000-000000000002',
      'sha256', repeat('d', 64),
      'kind', 'creator_reference',
      'mime_type', 'image/jpeg',
      'product_id', 'null'::jsonb,
      'rights_confirmed', true
    ),
    jsonb_build_object(
      'selection_role', 'product_image',
      'selection_ordinal', 3,
      'media_id', '30000000-0000-4000-8000-000000000003',
      'sha256', repeat('e', 64),
      'kind', 'product_photo',
      'mime_type', 'image/png',
      'product_id', '70000000-0000-4000-8000-000000000007',
      'rights_confirmed', true
    )
  ) as value
),
summary_value as (
  select jsonb_build_object(
    'version', 'generation-strategy-mechanics-summary-v1',
    'hook', 'Hands reveal the problem before the product enters frame.',
    'beat_sequence', jsonb_build_array(
      'Open on the practical pain point in one readable action.',
      'Introduce the product and demonstrate the useful transformation.'
    ),
    'pacing', 'Fast opening, measured proof, then a clean close.',
    'camera_language', 'Handheld close-up followed by a stable product detail.',
    'composition', 'Keep the action central and the product label readable.',
    'audio_pattern', 'Short spoken hook with quiet demonstration sounds.',
    'cta_pattern', 'Close with one direct benefit-led invitation.'
  ) as value
),
mechanics_value as (
  select jsonb_build_object(
    'version', 'generation-strategy-mechanics-snapshot-v1',
    'strategy_id', 'viral_avatar_ugc',
    'source_attachment_id', '40000000-0000-4000-8000-000000000004',
    'source_attachment_hash', repeat('a', 64),
    'source_media_id', '10000000-0000-4000-8000-000000000001',
    'source_media_sha256', repeat('c', 64),
    'summary', summary_value.value,
    'reviewed_by', '50000000-0000-4000-8000-000000000005',
    'review_confirmation', true
  ) as value
  from summary_value
),
scope_value as (
  select jsonb_build_object(
    'version', 'generation-strategy-spec-scope-v1',
    'authority_kind', 'strategy_recipe',
    'primary_media_id', '30000000-0000-4000-8000-000000000003',
    'media_ids', jsonb_build_array(
      '30000000-0000-4000-8000-000000000003'
    ),
    'platform', 'tiktok',
    'provider', 'runway',
    'strategy_id', 'viral_avatar_ugc',
    'recipe', 'product_ugc',
    'input_mode', 'character_and_product_images',
    'duration_seconds', 4,
    'product_category', 'other',
    'format', '720:1280',
    'ratio', '720:1280',
    'resolution', '720p',
    'audio', true,
    'spoken_dialogue', false,
    'reference_count', 2,
    'reference_video', false,
    'first_frame', false,
    'last_frame', false,
    'selection', selection_value.value,
    'selection_hash', content_factory_private.json_hash(
      selection_value.value
    ),
    'asset_snapshot', asset_snapshot_value.value,
    'asset_snapshot_hash', content_factory_private.json_hash(
      asset_snapshot_value.value
    ),
    'source', source_value.value,
    'source_hash', content_factory_private.json_hash(source_value.value),
    'mechanics', mechanics_value.value,
    'mechanics_hash', content_factory_private.json_hash(
      mechanics_value.value
    )
  ) as value
  from selection_value, asset_snapshot_value, source_value, mechanics_value
)
select is(
  content_factory_private.generation_strategy_spec_scope_v1(value),
  value,
  'UGC recipe scope exact-matches selection, source and mechanics hashes'
)
from scope_value;

select ok(
  position(
    'head.state = ''approved''' in pg_catalog.pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) > 0
  and position(
    'later.event_sequence > head.event_sequence' in
    pg_catalog.pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) > 0
  and position(
    'new.source_binding_id' in pg_catalog.pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) > 0
  and position(
    'new.role_asset_snapshot' in pg_catalog.pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) > 0
  and position(
    'scope_value -> ''asset_snapshot''' in pg_catalog.pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) > 0
  and position(
    'ledger.value ->> ''sha256''' in pg_catalog.pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) > 0,
  'binding requires approved source plus hash-pinned role-asset strategy scope'
);

select ok(
  position(
    'Human-approved high-level source mechanics:' in
    pg_catalog.pg_get_functiondef(
      'content_factory_private.generation_strategy_prompt_snapshot(uuid,uuid,jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'source_mechanics_snapshot_hash' in pg_catalog.pg_get_functiondef(
      'content_factory_private.generation_strategy_prompt_snapshot(uuid,uuid,jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    'binding_row.source_snapshot_hash' in pg_catalog.pg_get_functiondef(
      'content_factory_private.generation_strategy_prompt_snapshot(uuid,uuid,jsonb)'
        ::regprocedure
    )
  ) = 0,
  'prompt consumes the real approved mechanics hash, not attachment provenance'
);

select ok(
  position(
    'spec_id_value uuid := extensions.gen_random_uuid()' in
    pg_catalog.pg_get_functiondef(
      'content_factory_private.creator_prepare_generation_spec_pre_project_v49(jsonb)'
        ::regprocedure
    )
  ) > 0
  and position(
    '''spec_id''' in pg_catalog.pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    '''strategy-spec:'' || idempotency_key_value' in
    pg_catalog.pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    )
  ) > 0,
  'each distinct source/idempotency request allocates an independent spec_id'
);

with source_selections as (
  select jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_rebuild',
    'recipe_version', '2026-06',
    'duration_seconds', 4,
    'ratio', '720:1280',
    'audio', false,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video', 'media_id', source_id
      ),
      jsonb_build_object(
        'role', 'product_image',
        'media_id', '30000000-0000-4000-8000-000000000003'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true
    )
  ) as selection
  from (values
    ('10000000-0000-4000-8000-000000000001'),
    ('10000000-0000-4000-8000-000000000009')
  ) sources(source_id)
)
select is(
  count(distinct content_factory_private.json_hash(selection)),
  2::bigint,
  'two source videos produce two non-interchangeable immutable selections'
)
from source_selections;

select * from finish();
rollback;

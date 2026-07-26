begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(14);

select ok(
  content_factory_private.valid_research_claim_rows(
    jsonb_build_array(jsonb_build_object(
      'claim', 'Содержит 20 г белка',
      'basis', 'Значение указано на этикетке точного SKU',
      'source_ids', jsonb_build_array('S1')
    )),
    jsonb_build_array(jsonb_build_object(
      'claim', 'Гарантирует рост мышц',
      'reason', 'Результат нельзя гарантировать всем людям',
      'safer_alternative', 'Белок помогает дополнить рацион',
      'source_ids', jsonb_build_array('S1', 'S2')
    ))
  ),
  'bounded safe and forbidden research claim rows are valid'
);

select ok(
  not content_factory_private.valid_research_claim_rows(
    jsonb_build_array(
      jsonb_build_object(
        'claim', 'Содержит 20 г белка',
        'basis', 'Этикетка',
        'source_ids', jsonb_build_array('S1')
      ),
      jsonb_build_object(
        'claim', '  содержит 20 г белка  ',
        'basis', 'Карточка товара',
        'source_ids', jsonb_build_array('S2')
      )
    ),
    jsonb_build_array(jsonb_build_object(
      'claim', 'Лечит заболевание',
      'reason', 'Лечебное обещание',
      'safer_alternative', 'Описать состав',
      'source_ids', jsonb_build_array('S1')
    ))
  ),
  'duplicate or untrimmed claims are rejected'
);

select ok(
  content_factory_private.valid_approved_research_claims(
    jsonb_build_object(
      'sources', jsonb_build_array(
        jsonb_build_object('id', 'S1'),
        jsonb_build_object('id', 'S2')
      ),
      'claims', jsonb_build_object(
        'safe', jsonb_build_array(jsonb_build_object(
          'claim', 'Содержит 20 г белка',
          'basis', 'Этикетка точного SKU',
          'source_ids', jsonb_build_array('S1')
        )),
        'forbidden', jsonb_build_array(jsonb_build_object(
          'claim', 'Гарантирует рост мышц',
          'reason', 'Недоказуемая гарантия',
          'safer_alternative', 'Белок помогает дополнить рацион',
          'source_ids', jsonb_build_array('S1', 'S2')
        ))
      )
    )
  ),
  'approved research claims resolve every reference to a declared source'
);

select ok(
  not content_factory_private.valid_approved_research_claims(
    jsonb_build_object(
      'sources', jsonb_build_array(jsonb_build_object('id', 'S1')),
      'claims', jsonb_build_object(
        'safe', jsonb_build_array(jsonb_build_object(
          'claim', 'Содержит 20 г белка',
          'basis', 'Неизвестный источник',
          'source_ids', jsonb_build_array('S9')
        )),
        'forbidden', jsonb_build_array(jsonb_build_object(
          'claim', 'Гарантирует рост мышц',
          'reason', 'Недоказуемая гарантия',
          'safer_alternative', 'Описать состав',
          'source_ids', jsonb_build_array('S1')
        ))
      )
    )
  ),
  'research claims cannot cite an undeclared model source'
);

select ok(
  content_factory_private.valid_generation_claim_evidence_input(
    jsonb_build_object('historical', true)
  ),
  'historical review input remains readable without claim evidence'
);

with evidence_base as (
  select jsonb_build_object(
    'version', 'approved_research_claims_v1',
    'status', 'bound',
    'source', 'approved_research',
    'generation_job_id', '11111111-1111-4111-8111-111111111111',
    'prompt_hash', repeat('a', 64),
    'creative_brief_draft_id', '22222222-2222-4222-8222-222222222222',
    'creative_brief_content_hash', repeat('b', 64),
    'scenario_position', 1,
    'safe_claims', jsonb_build_array(jsonb_build_object(
      'claim', 'Содержит 20 г белка',
      'basis', 'Этикетка точного SKU',
      'source_ids', jsonb_build_array('S1')
    )),
    'forbidden_claims', jsonb_build_array(jsonb_build_object(
      'claim', 'Гарантирует рост мышц',
      'reason', 'Недоказуемая гарантия',
      'safer_alternative', 'Белок помогает дополнить рацион',
      'source_ids', jsonb_build_array('S1')
    )),
    'safe_claim_count', 1,
    'forbidden_claim_count', 1
  ) as value
),
evidence as (
  select value || jsonb_build_object(
    'evidence_hash',
    content_factory_private.json_hash(value)
  ) as value
  from evidence_base
)
select ok(
  content_factory_private.valid_generation_claim_evidence_input(
    jsonb_build_object('generation_claim_evidence', evidence.value)
  ),
  'a correctly hashed bound evidence snapshot is valid'
)
from evidence;

with evidence_base as (
  select jsonb_build_object(
    'version', 'approved_research_claims_v1',
    'status', 'bound',
    'source', 'approved_research',
    'generation_job_id', '11111111-1111-4111-8111-111111111111',
    'prompt_hash', repeat('a', 64),
    'creative_brief_draft_id', '22222222-2222-4222-8222-222222222222',
    'creative_brief_content_hash', repeat('b', 64),
    'scenario_position', 1,
    'safe_claims', jsonb_build_array(jsonb_build_object(
      'claim', 'Содержит 20 г белка',
      'basis', 'Этикетка точного SKU',
      'source_ids', jsonb_build_array('S1')
    )),
    'forbidden_claims', jsonb_build_array(jsonb_build_object(
      'claim', 'Гарантирует рост мышц',
      'reason', 'Недоказуемая гарантия',
      'safer_alternative', 'Белок помогает дополнить рацион',
      'source_ids', jsonb_build_array('S1')
    )),
    'safe_claim_count', 1,
    'forbidden_claim_count', 1
  ) as value
),
evidence as (
  select value || jsonb_build_object(
    'evidence_hash',
    content_factory_private.json_hash(value)
  ) as value
  from evidence_base
)
select ok(
  not content_factory_private.valid_generation_claim_evidence_input(
    jsonb_build_object(
      'generation_claim_evidence',
      jsonb_set(evidence.value, '{safe_claim_count}', '2'::jsonb)
    )
  ),
  'tampering with a hashed evidence snapshot is rejected'
)
from evidence;

with evidence_base as (
  select jsonb_build_object(
    'version', 'approved_research_claims_v1',
    'status', 'unavailable',
    'source', 'baseline',
    'generation_job_id', '11111111-1111-4111-8111-111111111111',
    'prompt_hash', repeat('a', 64),
    'creative_brief_draft_id', null,
    'creative_brief_content_hash', null,
    'scenario_position', null,
    'safe_claims', '[]'::jsonb,
    'forbidden_claims', '[]'::jsonb,
    'safe_claim_count', 0,
    'forbidden_claim_count', 0
  ) as value
),
evidence as (
  select value || jsonb_build_object(
    'evidence_hash',
    content_factory_private.json_hash(value)
  ) as value
  from evidence_base
)
select ok(
  content_factory_private.valid_generation_claim_evidence_input(
    jsonb_build_object('generation_claim_evidence', evidence.value)
  ),
  'baseline generation is honestly represented as unavailable evidence'
)
from evidence;

select ok(
  exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.conrelid =
        'content_factory.content_review_runs'::regclass
      and constraint_row.conname =
        'content_review_generation_claim_evidence_check'
      and constraint_row.convalidated
  ),
  'validated content review claim evidence constraint is installed'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
        'content_factory.content_review_runs'::regclass
      and trigger_row.tgname = 'zz_generated_claim_evidence_guard'
      and not trigger_row.tgisinternal
  ),
  'generated media review has a late server-owned claim evidence trigger'
);

select ok(
  to_regprocedure(
    'public.creator_start_real_generation(jsonb)'
  ) is not null,
  'public paid generation remains available through the research gate'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_claim_v4(jsonb)'
  ) is not null,
  'the previous paid implementation is private behind the research gate'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_start_real_generation(jsonb)',
    'execute'
  ),
  'authenticated creators may execute the public research-gated start'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_start_real_generation_pre_claim_v4(jsonb)',
    'execute'
  ),
  'browser sessions cannot bypass the research claim gate'
);

select * from finish();

rollback;

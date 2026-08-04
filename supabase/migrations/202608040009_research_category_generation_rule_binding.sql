begin;

-- Research evidence references stay in the ledger.  Provider prompts reject
-- URI schemes and bare domain-like references, not only http(s) strings.
create or replace function
  content_factory_private.generation_spec_prompt_has_external_reference(
    compiled_prompt_value text
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select coalesce(compiled_prompt_value, '') ~*
    '((https?|ftp|file|data|mailto|javascript|blob|ipfs|s3|gs|tel|urn):(//|[^[:space:]])|(^|[^[:alnum:]_-])www[.]|(^|[^[:alnum:]_-])([0-9]{1,3}[.]){3}[0-9]{1,3}([:/?#]|$|[^[:alnum:]_.-])|(^|[^[:alnum:]_-])([[:alnum:]-]+[.])+(com|org|net|edu|gov|io|ai|app|dev|co|me|tv|info|biz|xyz|online|site|shop|store|tech|ru|рф|su|ua|by|kz|[a-z]{2}|xn--[a-z0-9-]{2,59})([:/?#]|$|[^[:alnum:]_-])|(^|[^[:alnum:]_-])([[:alnum:]-]+[.])+[[:alpha:]]{2,24}([:/?#]))';
$$;

revoke all on function
  content_factory_private.generation_spec_prompt_has_external_reference(text)
  from public, anon, authenticated, service_role;

-- The generation handoff has one authoritative bounded research compiler.
-- The selected scenario hook/shot list and three allowlisted category fields
-- participate. Raw category, competitor and trend prose never crosses the
-- provider boundary.
create or replace function
  content_factory_private.generation_spec_research_structure(
    brief_value jsonb,
    scenario_position_value integer
  )
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  scenario_value jsonb;
  hook_value text;
  shot_list_value text;
  research_text text;
  patterns_value jsonb := '[]'::jsonb;
  angle_value text;
  category_maturity_value text;
  competitor_coverage_value text;
  primary_signal_value text := 'none';
begin
  if jsonb_typeof(brief_value) is distinct from 'object'
     or coalesce(scenario_position_value not between 1 and 3, true) then
    return null;
  end if;
  scenario_value := brief_value #> array[
    'scenarios', (scenario_position_value - 1)::text
  ];
  if jsonb_typeof(scenario_value) <> 'object' then
    return null;
  end if;
  hook_value := btrim(regexp_replace(
    coalesce(scenario_value ->> 'hook', ''), '[[:space:]]+', ' ', 'g'
  ));
  if jsonb_typeof(scenario_value -> 'shot_list') = 'array' then
    select string_agg(
      case
        when jsonb_typeof(item.value) = 'string' then item.value #>> '{}'
        when jsonb_typeof(item.value) = 'object' then concat(
          case
            when btrim(coalesce(item.value ->> 'seconds', '')) <> ''
              then (item.value ->> 'seconds') || ': '
            else ''
          end,
          coalesce(nullif(item.value ->> 'visual', ''), 'Кадр'),
          '.',
          case
            when btrim(coalesce(item.value ->> 'voiceover', '')) <> ''
              then ' Голос: ' || (item.value ->> 'voiceover') || '.'
            else ''
          end,
          case
            when btrim(coalesce(item.value ->> 'on_screen_text', '')) <> ''
              then ' Текст: ' || (item.value ->> 'on_screen_text') || '.'
            else ''
          end
        )
        else item.value::text
      end,
      ' ' order by item.ordinality
    ) into shot_list_value
    from jsonb_array_elements(scenario_value -> 'shot_list')
      with ordinality item(value, ordinality);
  else
    shot_list_value := coalesce(scenario_value ->> 'shot_list', '');
  end if;
  shot_list_value := btrim(regexp_replace(
    coalesce(shot_list_value, ''), '[[:space:]]+', ' ', 'g'
  ));
  research_text := lower(concat_ws(' ', hook_value, shot_list_value));
  if position('?' in hook_value) > 0 then
    patterns_value := patterns_value || '"question_led"'::jsonb;
  end if;
  if research_text ~*
       '(^|[^[:alnum:]_])(why|почему|зачем)([^[:alnum:]_]|$)' then
    patterns_value := patterns_value || '"why_explanation"'::jsonb;
  end if;
  if research_text ~*
       '(^|[^[:alnum:]_])(before|до покупки|перед покупкой)([^[:alnum:]_]|$)' then
    patterns_value := patterns_value || '"before_buying"'::jsonb;
  end if;
  if research_text ~*
       '(^|[^[:alnum:]_])(compare|versus|vs|сравн|дешев)' then
    patterns_value := patterns_value || '"comparison"'::jsonb;
  end if;
  if research_text ~*
       '(^|[^[:alnum:]_])(watch|show|see|смотр|покаж)' then
    patterns_value := patterns_value || '"demonstration"'::jsonb;
  end if;
  if research_text ~*
       '(^|[^[:alnum:]_])(i|my|я|мой|моя|мне)([^[:alnum:]_]|$)' then
    patterns_value := patterns_value || '"first_person"'::jsonb;
  end if;
  if research_text ~ '[0-9]'
     or research_text ~*
       '(^|[^[:alnum:]_])(one|один|одна|три|three)([^[:alnum:]_]|$)' then
    patterns_value := patterns_value || '"numbered"'::jsonb;
  end if;
  if length(hook_value) between 1 and 72 then
    patterns_value := patterns_value || '"concise"'::jsonb;
  end if;
  angle_value := case
    when patterns_value @> '["comparison"]'::jsonb then 'comparison'
    when patterns_value @> '["before_buying"]'::jsonb
      or patterns_value @> '["why_explanation"]'::jsonb
      then 'objection_handling'
    when patterns_value @> '["demonstration"]'::jsonb then 'demonstration'
    when patterns_value @> '["question_led"]'::jsonb then 'curiosity_gap'
    when research_text ~*
      '(^|[^[:alnum:]_])(честн|довер|спокойн|реальн|trust)'
      then 'trust_builder'
    else 'product_focus'
  end;
  category_maturity_value := case
    when brief_value #>> '{category_analysis,maturity}' in (
      'emerging', 'growing', 'established', 'saturated', 'unknown'
    ) then brief_value #>> '{category_analysis,maturity}'
    else 'unknown'
  end;
  competitor_coverage_value := case
    when brief_value #>> '{competitor_analysis,coverage}' in (
      'none', 'limited', 'sufficient'
    ) then brief_value #>> '{competitor_analysis,coverage}'
    else 'none'
  end;
  if brief_value #>> '{trend_analysis,signal_catalog_version}' =
       'structural_v1' then
    select signal.value ->> 'signal_key'
      into primary_signal_value
    from jsonb_array_elements(
      case
        when jsonb_typeof(brief_value #> '{trend_analysis,signals}') = 'array'
          then brief_value #> '{trend_analysis,signals}'
        else '[]'::jsonb
      end
    ) with ordinality signal(value, ordinality)
    where signal.value ->> 'signal_key' in (
        'hook.problem_first', 'hook.result_first',
        'format.single_action_demo', 'format.step_by_step',
        'format.comparison', 'format.unboxing',
        'format.creator_explainer', 'proof.product_in_use',
        'proof.before_after', 'proof.social_proof', 'offer.bundle',
        'offer.price_anchor', 'channel.marketplace_native_video',
        'channel.short_vertical_video'
      )
      and signal.value ->> 'recommended_use' = 'test'
      and signal.value ->> 'confidence' in ('medium', 'high')
      and signal.value ->> 'direction' in (
        'emerging', 'growing', 'stable', 'declining'
      )
    order by signal.ordinality
    limit 1;
    primary_signal_value := coalesce(primary_signal_value, 'none');
  end if;
  return jsonb_build_object(
    'creative_angle', angle_value,
    'hook_patterns', patterns_value,
    'category_maturity', category_maturity_value,
    'competitor_coverage', competitor_coverage_value,
    'primary_signal', primary_signal_value,
    'compiler_version', 'safe-brief-v7'
  );
end;
$$;

-- A modern approved-research generation spec must carry the exact dynamic
-- market-category identity that applied to its immutable draft.  The receipt
-- below stores identifiers, bounded structural enum values and hashes only;
-- source copy, category prose and source locations are deliberately absent.
create unique index if not exists
  research_product_market_binding_generation_rule_exact_uq
  on content_factory.research_product_market_category_bindings (
    organization_id, product_id, id, category_id, binding_version,
    source_run_id, source_draft_id, candidate_hash, confirmed_at
  );

create or replace function
  content_factory_private.generation_spec_research_category_rule_fragment(
    canonical_learning_context_value jsonb
  )
returns text
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  angle_value text;
  hooks_value jsonb;
  primary_hook_value text;
  category_maturity_value text;
  competitor_coverage_value text;
  primary_signal_value text;
  fragment_value text;
begin
  if jsonb_typeof(canonical_learning_context_value) is distinct from 'object'
     or canonical_learning_context_value ->> 'source'
          is distinct from 'approved_research'
     or canonical_learning_context_value ->> 'compiler_version'
          is distinct from 'safe-brief-v7' then
    return null;
  end if;

  angle_value := canonical_learning_context_value ->> 'creative_angle';
  if angle_value is null or angle_value not in (
       'product_focus', 'trust_builder', 'demonstration', 'comparison',
       'objection_handling', 'curiosity_gap'
     ) then
    return null;
  end if;

  hooks_value := canonical_learning_context_value -> 'hook_patterns';
  if jsonb_typeof(hooks_value) is distinct from 'array'
     or jsonb_array_length(hooks_value) > 8 then
    return null;
  end if;
  if exists (
    select 1
    from jsonb_array_elements(hooks_value) hook(value)
    where jsonb_typeof(hook.value) is distinct from 'string'
       or hook.value #>> '{}' not in (
         'question_led', 'why_explanation', 'before_buying', 'comparison',
         'demonstration', 'first_person', 'numbered', 'concise'
       )
  ) then
    return null;
  end if;

  primary_hook_value := coalesce(hooks_value ->> 0, 'none');
  category_maturity_value :=
    canonical_learning_context_value ->> 'category_maturity';
  competitor_coverage_value :=
    canonical_learning_context_value ->> 'competitor_coverage';
  primary_signal_value :=
    canonical_learning_context_value ->> 'primary_signal';
  if category_maturity_value not in (
       'emerging', 'growing', 'established', 'saturated', 'unknown'
     )
     or competitor_coverage_value not in (
       'none', 'limited', 'sufficient'
     )
     or primary_signal_value not in (
       'none', 'hook.problem_first', 'hook.result_first',
       'format.single_action_demo', 'format.step_by_step',
       'format.comparison', 'format.unboxing',
       'format.creator_explainer', 'proof.product_in_use',
       'proof.before_after', 'proof.social_proof', 'offer.bundle',
       'offer.price_anchor', 'channel.marketplace_native_video',
       'channel.short_vertical_video'
     ) then
    return null;
  end if;
  fragment_value := format(
    'ResearchCategoryRule/v2 category_maturity=%s competitor_coverage=%s primary_signal=%s creative_angle=%s primary_hook=%s.',
    category_maturity_value,
    competitor_coverage_value,
    primary_signal_value,
    angle_value,
    primary_hook_value
  );
  -- Every variable component came from an ASCII enum allowlist.  Keep an
  -- explicit executable invariant so a later compiler change cannot silently
  -- turn the provider fragment into raw research copy or a multiline value.
  if octet_length(fragment_value) <> length(fragment_value)
     or fragment_value ~ E'[\\r\\n]' then
    return null;
  end if;
  return fragment_value;
end;
$$;

create or replace function
  content_factory_private.generation_spec_prompt_has_exact_category_rule(
    compiled_prompt_value text,
    rule_fragment_value text
  )
returns boolean
language sql
immutable
strict
set search_path = ''
as $$
  select
    octet_length(rule_fragment_value) = length(rule_fragment_value)
    and rule_fragment_value !~ E'[\\r\\n]'
    and (
      select count(*) = 1
      from regexp_split_to_table(compiled_prompt_value, E'\\r?\\n')
        prompt_line(value)
      where prompt_line.value = rule_fragment_value
    )
    and length(compiled_prompt_value)
          - length(replace(
              compiled_prompt_value, rule_fragment_value, ''
            )) = length(rule_fragment_value)
    and length(lower(compiled_prompt_value))
          - length(replace(
              lower(compiled_prompt_value), 'researchcategoryrule/', ''
            )) = length('researchcategoryrule/');
$$;

-- This is the same temporal category rule used by the source-analysis
-- lineage: an exact human decision for this draft wins, including a
-- reclassification confirmed after draft creation. Otherwise use the latest
-- earlier binding only when it proves the same immutable category candidate.
-- No legacy generation enum participates.
create or replace function
  content_factory_private.generation_spec_research_category_temporal_binding(
    organization_id_value uuid,
    research_run_id_value uuid,
    research_draft_id_value uuid
  )
returns table (
  product_id uuid,
  category_binding_id uuid,
  market_category_id uuid,
  category_binding_version integer,
  category_binding_source_run_id uuid,
  category_binding_source_draft_id uuid,
  category_binding_candidate_hash text,
  category_binding_confirmed_at timestamptz,
  research_draft_created_at timestamptz,
  research_draft_content_hash text
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    draft.product_id,
    binding.id,
    binding.category_id,
    binding.binding_version,
    binding.source_run_id,
    binding.source_draft_id,
    binding.candidate_hash,
    binding.confirmed_at,
    draft.created_at,
    draft.content_hash
  from content_factory.creative_brief_drafts draft
  join content_factory.research_product_market_category_bindings binding
    on binding.organization_id = draft.organization_id
   and binding.product_id = draft.product_id
   and (
     (
       binding.source_run_id = draft.run_id
       and binding.source_draft_id = draft.id
       and binding.candidate_hash = content_factory_private.json_hash(
         draft.brief -> 'category_analysis'
       )
     )
     or (
       binding.confirmed_at <= draft.created_at
       and exists (
         select 1
         from content_factory.research_market_categories category
         where category.organization_id = binding.organization_id
           and category.id = binding.category_id
           and (
             category.normalized_name = content_factory_private
               .research_market_identity_key(
                 draft.brief #>> '{category_analysis,category_name}'
               )
             or exists (
               select 1
               from content_factory.research_market_category_aliases alias
               where alias.organization_id = category.organization_id
                 and alias.category_id = category.id
                 and alias.normalized_alias = content_factory_private
                   .research_market_identity_key(
                     draft.brief #>> '{category_analysis,category_name}'
                   )
             )
           )
       )
     )
   )
  where draft.organization_id = organization_id_value
    and draft.run_id = research_run_id_value
    and draft.id = research_draft_id_value
  order by
    case when binding.source_run_id = draft.run_id
                   and binding.source_draft_id = draft.id then 0 else 1 end,
    case when binding.source_run_id = draft.run_id
                   and binding.source_draft_id = draft.id
      then binding.binding_version end desc,
    case when not (binding.source_run_id = draft.run_id
                   and binding.source_draft_id = draft.id)
      then binding.binding_version end desc,
    binding.id
  limit 1;
$$;

-- Source-analysis freshness and generation receipts must resolve the same
-- temporal category.  The older source helper preferred any pre-draft
-- binding over an exact decision for this draft confirmed later, which could
-- validate category-A source heads while the provider rule was bound to B.
create or replace function
  content_factory_private.research_draft_market_category_id(
    organization_id_value uuid,
    run_id_value uuid,
    draft_id_value uuid
  )
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select temporal.market_category_id
  from content_factory_private
    .generation_spec_research_category_temporal_binding(
      organization_id_value, run_id_value, draft_id_value
    ) temporal;
$$;

-- Repair drafts that were captured before the exact-first helper existed.
-- Only the current active binding for each product is eligible: the existing
-- local registration routine can then deterministically create/deduplicate
-- category ledgers and parser heads for that exact run, after which a new
-- append-only draft/source binding supersedes the old category head.
do $research_category_rule_source_binding_repair$
declare
  exact_binding record;
  source_id_value uuid;
  analysis_event_id_value uuid;
  repaired_binding_id uuid;
begin
  for exact_binding in
    with latest_binding as (
      select distinct on (binding.organization_id, binding.product_id)
        binding.*
      from content_factory.research_product_market_category_bindings binding
      order by binding.organization_id, binding.product_id,
        binding.binding_version desc, binding.id desc
    )
    select binding.organization_id, binding.product_id,
      binding.category_id, binding.source_run_id, binding.source_draft_id,
      draft.source_ids
    from latest_binding binding
    join content_factory.research_market_categories category
      on category.organization_id = binding.organization_id
     and category.id = binding.category_id
     and category.status = 'active'
    join content_factory.product_research_runs run
      on run.organization_id = binding.organization_id
     and run.id = binding.source_run_id
     and run.product_id = binding.product_id
     and run.status = 'completed'
    join content_factory.creative_brief_drafts draft
      on draft.organization_id = binding.organization_id
     and draft.run_id = binding.source_run_id
     and draft.id = binding.source_draft_id
     and draft.product_id = binding.product_id
    where jsonb_typeof(draft.brief -> 'category_analysis') = 'object'
      and binding.candidate_hash = content_factory_private.json_hash(
        draft.brief -> 'category_analysis'
      )
    order by binding.organization_id, binding.product_id
  loop
    perform public.system_register_research_category_sources(
      jsonb_build_object(
        'organization_id', exact_binding.organization_id,
        'run_id', exact_binding.source_run_id
      )
    );
    for source_id_value in
      select distinct source_ref.value::uuid
      from jsonb_array_elements_text(exact_binding.source_ids)
        source_ref(value)
      order by source_ref.value::uuid
    loop
      analysis_event_id_value := null;
      repaired_binding_id := null;
      select event.id into analysis_event_id_value
      from content_factory.product_research_sources source
      join content_factory.research_category_source_ledger ledger
        on ledger.organization_id = source.organization_id
       and ledger.market_category_id = exact_binding.category_id
       and ledger.source_content_hash = source.content_hash
      left join lateral (
        select candidate.id
        from content_factory.research_source_analysis_events candidate
        where candidate.organization_id = ledger.organization_id
          and candidate.source_ledger_id = ledger.id
        order by candidate.analysis_version desc, candidate.id desc
        limit 1
      ) event on true
      where source.organization_id = exact_binding.organization_id
        and source.run_id = exact_binding.source_run_id
        and source.id = source_id_value
      order by ledger.registered_at desc, ledger.id desc
      limit 1;
      repaired_binding_id := content_factory_private
        .append_research_draft_source_analysis_binding(
          exact_binding.organization_id, exact_binding.source_run_id,
          exact_binding.source_draft_id, source_id_value,
          analysis_event_id_value, 'backfill'
        );
      if repaired_binding_id is null then
        raise exception using
          errcode = '55000',
          message = 'research_category_rule_source_binding_backfill_failed';
      end if;
    end loop;
  end loop;
end;
$research_category_rule_source_binding_repair$;

create table content_factory.generation_spec_research_category_rule_bindings (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    generation_spec_version_id uuid not null,
    spec_id uuid not null,
    spec_version integer not null check (spec_version between 1 and 100000),
    spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    research_snapshot_hash text not null check (
      research_snapshot_hash ~ '^[0-9a-f]{64}$'
    ),
    product_id uuid not null,
    market_category_id uuid not null,
    category_binding_id uuid not null,
    category_binding_version integer not null check (
      category_binding_version between 1 and 100000
    ),
    category_binding_source_run_id uuid not null,
    category_binding_source_draft_id uuid not null,
    category_binding_candidate_hash text not null check (
      category_binding_candidate_hash ~ '^[0-9a-f]{64}$'
    ),
    category_binding_confirmed_at timestamptz not null,
    research_run_id uuid not null,
    research_draft_id uuid not null,
    research_draft_content_hash text not null check (
      research_draft_content_hash ~ '^[0-9a-f]{64}$'
    ),
    research_draft_created_at timestamptz not null,
    scenario_position integer not null check (scenario_position between 1 and 3),
    rule_version text not null check (rule_version = 'ResearchCategoryRule/v2'),
    category_maturity text not null check (category_maturity in (
      'emerging', 'growing', 'established', 'saturated', 'unknown'
    )),
    competitor_coverage text not null check (competitor_coverage in (
      'none', 'limited', 'sufficient'
    )),
    primary_signal text not null check (primary_signal in (
      'none', 'hook.problem_first', 'hook.result_first',
      'format.single_action_demo', 'format.step_by_step',
      'format.comparison', 'format.unboxing',
      'format.creator_explainer', 'proof.product_in_use',
      'proof.before_after', 'proof.social_proof', 'offer.bundle',
      'offer.price_anchor', 'channel.marketplace_native_video',
      'channel.short_vertical_video'
    )),
    creative_angle text not null check (creative_angle in (
      'product_focus', 'trust_builder', 'demonstration', 'comparison',
      'objection_handling', 'curiosity_gap'
    )),
    primary_hook text not null check (primary_hook in (
      'none', 'question_led', 'why_explanation', 'before_buying',
      'comparison', 'demonstration', 'first_person', 'numbered', 'concise'
    )),
    rule_hash text not null check (rule_hash ~ '^[0-9a-f]{64}$'),
    stale_error_code text not null default
      'generation_spec_research_category_rule_stale'
      check (
        stale_error_code = 'generation_spec_research_category_rule_stale'
      ),
    receipt_hash text not null check (receipt_hash ~ '^[0-9a-f]{64}$'),
    bound_at timestamptz not null default clock_timestamp(),
    constraint generation_spec_research_category_rule_bindings_org_id_uq
      unique (organization_id, id),
    constraint generation_spec_research_category_rule_bindings_spec_uq
      unique (organization_id, spec_id, spec_version),
    constraint generation_spec_research_category_rule_bindings_hash_uq
      unique (organization_id, receipt_hash),
    foreign key (organization_id, generation_spec_version_id)
      references content_factory.generation_spec_versions(
        organization_id, version_id
      ),
    foreign key (organization_id, spec_id, spec_version, spec_hash)
      references content_factory.generation_spec_versions(
        organization_id, spec_id, spec_version, spec_hash
      ),
    foreign key (organization_id, market_category_id)
      references content_factory.research_market_categories(
        organization_id, id
      ),
    foreign key (
      organization_id, product_id, category_binding_id,
      market_category_id, category_binding_version,
      category_binding_source_run_id, category_binding_source_draft_id,
      category_binding_candidate_hash, category_binding_confirmed_at
    ) references content_factory.research_product_market_category_bindings(
      organization_id, product_id, id, category_id, binding_version,
      source_run_id, source_draft_id, candidate_hash, confirmed_at
    ),
    foreign key (organization_id, research_run_id, research_draft_id)
      references content_factory.creative_brief_drafts(
        organization_id, run_id, id
      ),
    check (
      category_binding_confirmed_at <= research_draft_created_at
      or (
        category_binding_source_run_id = research_run_id
        and category_binding_source_draft_id = research_draft_id
      )
    ),
    check (
      rule_hash = content_factory_private.raw_text_sha256(
        rule_version || ' category_maturity=' || category_maturity
        || ' competitor_coverage=' || competitor_coverage
        || ' primary_signal=' || primary_signal
        || ' creative_angle=' || creative_angle
        || ' primary_hook=' || primary_hook || '.'
      )
    ),
    check (
      receipt_hash = content_factory_private.json_hash(jsonb_build_object(
        'schema_version',
          'generation-spec-research-category-rule-binding-v2',
        'organization_id', organization_id,
        'generation_spec_version_id', generation_spec_version_id,
        'spec_id', spec_id,
        'spec_version', spec_version,
        'spec_hash', spec_hash,
        'prompt_hash', prompt_hash,
        'research_snapshot_hash', research_snapshot_hash,
        'product_id', product_id,
        'market_category_id', market_category_id,
        'category_binding_id', category_binding_id,
        'category_binding_version', category_binding_version,
        'category_binding_source_run_id', category_binding_source_run_id,
        'category_binding_source_draft_id', category_binding_source_draft_id,
        'category_binding_candidate_hash', category_binding_candidate_hash,
        'category_binding_confirmed_at', category_binding_confirmed_at,
        'research_run_id', research_run_id,
        'research_draft_id', research_draft_id,
        'research_draft_content_hash', research_draft_content_hash,
        'research_draft_created_at', research_draft_created_at,
        'scenario_position', scenario_position,
        'rule_version', rule_version,
        'category_maturity', category_maturity,
        'competitor_coverage', competitor_coverage,
        'primary_signal', primary_signal,
        'creative_angle', creative_angle,
        'primary_hook', primary_hook,
        'rule_hash', rule_hash,
        'stale_error_code', stale_error_code
      ))
    )
);

create index generation_spec_research_category_rule_bindings_category_idx
  on content_factory.generation_spec_research_category_rule_bindings (
    organization_id, product_id, market_category_id,
    category_binding_version desc, bound_at desc
  );

alter table content_factory.generation_spec_research_category_rule_bindings
  enable row level security;
revoke all on content_factory.generation_spec_research_category_rule_bindings
  from public, anon, authenticated, service_role;

create trigger generation_spec_research_category_rule_bindings_append_only
before update or delete
on content_factory.generation_spec_research_category_rule_bindings
for each row execute function
  content_factory_private.reject_generation_spec_mutation();

create or replace function
  content_factory_private.capture_generation_spec_research_category_rule()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  research_run_id_value uuid;
  research_draft_id_value uuid;
  scenario_position_value integer;
  draft_row content_factory.creative_brief_drafts%rowtype;
  temporal_binding record;
  research_structure_value jsonb;
  research_rule_context_value jsonb;
  rule_fragment_value text;
  rule_hash_value text;
  primary_hook_value text;
  receipt_hash_value text;
begin
  -- The reserved provider token is legal only when this trigger can append
  -- its exact receipt. Modern category research owns the learned provider
  -- surface; performance provenance may not coexist with that rule.
  if new.research_provenance is null then
    if position(
         'researchcategoryrule/' in lower(new.compiled_prompt)
       ) > 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_research_category_rule_stale',
        detail = 'research_category_rule_without_provenance';
    end if;
    return new;
  end if;
  if content_factory_private.generation_spec_prompt_has_external_reference(
       new.compiled_prompt
     ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'research_prompt_external_url_forbidden';
  end if;

  begin
    research_run_id_value := (
      new.research_provenance ->> 'research_id'
    )::uuid;
    research_draft_id_value := (
      new.research_provenance ->> 'creative_brief_draft_id'
    )::uuid;
    scenario_position_value := (
      new.research_provenance ->> 'scenario_position'
    )::integer;
  exception
    when invalid_text_representation or numeric_value_out_of_range then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_research_category_rule_stale',
        detail = 'approved_research_identity_invalid';
  end;

  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = new.organization_id
    and draft.run_id = research_run_id_value
    and draft.id = research_draft_id_value
    and draft.product_id = new.product_id
    and draft.status = 'approved';
  if draft_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'approved_research_draft_stale';
  end if;

  -- Drafts produced before category_analysis existed remain readable and may
  -- be regenerated under their prior contract. Presence of the modern object
  -- is the one-way boundary: partial modern data never falls back.
  if jsonb_typeof(draft_row.brief -> 'category_analysis')
       is distinct from 'object' then
    if position(
         'researchcategoryrule/' in lower(new.compiled_prompt)
       ) > 0 then
      raise exception using
        errcode = '55000',
        message = 'generation_spec_research_category_rule_stale',
        detail = 'legacy_research_rule_token_forbidden';
    end if;
    return new;
  end if;
  if new.canonical_learning_context ->> 'source'
       is distinct from 'approved_research'
     or new.performance_policy_provenance is not null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'research_category_rule_single_owner_required';
  end if;

  select * into temporal_binding
  from content_factory_private
    .generation_spec_research_category_temporal_binding(
      new.organization_id, research_run_id_value, research_draft_id_value
    );
  if temporal_binding.category_binding_id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'modern_research_category_binding_required';
  end if;
  if not exists (
    select 1
    from content_factory.research_market_categories category
    where category.organization_id = new.organization_id
      and category.id = temporal_binding.market_category_id
      and category.status = 'active'
  ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'research_market_category_inactive';
  end if;

  research_structure_value :=
    content_factory_private.generation_spec_research_structure(
      draft_row.brief, scenario_position_value
    );
  if research_structure_value is null then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'research_category_rule_derivation_invalid';
  end if;
  if new.canonical_learning_context ->> 'source' = 'approved_research'
     and (
       new.canonical_learning_context ->> 'creative_angle'
         is distinct from research_structure_value ->> 'creative_angle'
       or new.canonical_learning_context -> 'hook_patterns'
         is distinct from research_structure_value -> 'hook_patterns'
     ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'approved_research_canonical_structure_mismatch';
  end if;

  research_rule_context_value := research_structure_value
    || jsonb_build_object('source', 'approved_research');
  rule_fragment_value := content_factory_private
    .generation_spec_research_category_rule_fragment(
      research_rule_context_value
    );
  if rule_fragment_value is null
     or new.prompt_hash is distinct from
          content_factory_private.raw_text_sha256(new.compiled_prompt)
     or not content_factory_private
       .generation_spec_prompt_has_exact_category_rule(
         new.compiled_prompt, rule_fragment_value
       ) then
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale',
      detail = 'research_category_rule_fragment_missing_or_ambiguous';
  end if;

  rule_hash_value :=
    content_factory_private.raw_text_sha256(rule_fragment_value);
  primary_hook_value := coalesce(
    research_structure_value #>> '{hook_patterns,0}', 'none'
  );
  receipt_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'generation-spec-research-category-rule-binding-v2',
    'organization_id', new.organization_id,
    'generation_spec_version_id', new.version_id,
    'spec_id', new.spec_id,
    'spec_version', new.spec_version,
    'spec_hash', new.spec_hash,
    'prompt_hash', new.prompt_hash,
    'research_snapshot_hash', new.research_snapshot_hash,
    'product_id', new.product_id,
    'market_category_id', temporal_binding.market_category_id,
    'category_binding_id', temporal_binding.category_binding_id,
    'category_binding_version', temporal_binding.category_binding_version,
    'category_binding_source_run_id',
      temporal_binding.category_binding_source_run_id,
    'category_binding_source_draft_id',
      temporal_binding.category_binding_source_draft_id,
    'category_binding_candidate_hash',
      temporal_binding.category_binding_candidate_hash,
    'category_binding_confirmed_at',
      temporal_binding.category_binding_confirmed_at,
    'research_run_id', research_run_id_value,
    'research_draft_id', research_draft_id_value,
    'research_draft_content_hash', draft_row.content_hash,
    'research_draft_created_at', draft_row.created_at,
    'scenario_position', scenario_position_value,
    'rule_version', 'ResearchCategoryRule/v2',
    'category_maturity', research_structure_value ->> 'category_maturity',
    'competitor_coverage',
      research_structure_value ->> 'competitor_coverage',
    'primary_signal', research_structure_value ->> 'primary_signal',
    'creative_angle', research_structure_value ->> 'creative_angle',
    'primary_hook', primary_hook_value,
    'rule_hash', rule_hash_value,
    'stale_error_code', 'generation_spec_research_category_rule_stale'
  ));

  insert into
    content_factory.generation_spec_research_category_rule_bindings (
      organization_id, generation_spec_version_id,
      spec_id, spec_version, spec_hash, prompt_hash, research_snapshot_hash,
      product_id, market_category_id, category_binding_id,
      category_binding_version, category_binding_source_run_id,
      category_binding_source_draft_id, category_binding_candidate_hash,
      category_binding_confirmed_at, research_run_id, research_draft_id,
      research_draft_content_hash, research_draft_created_at,
      scenario_position, rule_version, category_maturity,
      competitor_coverage, primary_signal, creative_angle, primary_hook,
      rule_hash, stale_error_code, receipt_hash
    ) values (
      new.organization_id, new.version_id,
      new.spec_id, new.spec_version, new.spec_hash, new.prompt_hash,
      new.research_snapshot_hash, new.product_id,
      temporal_binding.market_category_id,
      temporal_binding.category_binding_id,
      temporal_binding.category_binding_version,
      temporal_binding.category_binding_source_run_id,
      temporal_binding.category_binding_source_draft_id,
      temporal_binding.category_binding_candidate_hash,
      temporal_binding.category_binding_confirmed_at,
      research_run_id_value, research_draft_id_value,
      draft_row.content_hash, draft_row.created_at,
      scenario_position_value, 'ResearchCategoryRule/v2',
      research_structure_value ->> 'category_maturity',
      research_structure_value ->> 'competitor_coverage',
      research_structure_value ->> 'primary_signal',
      research_structure_value ->> 'creative_angle', primary_hook_value,
      rule_hash_value, 'generation_spec_research_category_rule_stale',
      receipt_hash_value
    );
  return new;
end;
$$;

create trigger capture_generation_spec_research_category_rule_binding
after insert on content_factory.generation_spec_versions
for each row execute function
  content_factory_private.capture_generation_spec_research_category_rule();

create or replace function
  content_factory_private.generation_spec_research_category_rule_current(
    organization_id_value uuid,
    spec_id_value uuid,
    spec_version_value integer,
    spec_hash_value text
  )
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  spec_row content_factory.generation_spec_versions%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  receipt_row
    content_factory.generation_spec_research_category_rule_bindings%rowtype;
  current_binding
    content_factory.research_product_market_category_bindings%rowtype;
  temporal_binding record;
  research_run_id_value uuid;
  research_draft_id_value uuid;
  scenario_position_value integer;
  research_structure_value jsonb;
  research_rule_context_value jsonb;
  rule_fragment_value text;
  expected_primary_hook text;
begin
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value;
  if spec_row.version_id is null then
    return false;
  end if;
  if spec_row.research_provenance is null then
    return position(
      'researchcategoryrule/' in lower(spec_row.compiled_prompt)
    ) = 0 and not exists (
      select 1
      from content_factory.generation_spec_research_category_rule_bindings
        receipt
      where receipt.organization_id = organization_id_value
        and receipt.spec_id = spec_id_value
        and receipt.spec_version = spec_version_value
    );
  end if;
  if content_factory_private.generation_spec_prompt_has_external_reference(
       spec_row.compiled_prompt
     ) then
    return false;
  end if;

  begin
    research_run_id_value := (
      spec_row.research_provenance ->> 'research_id'
    )::uuid;
    research_draft_id_value := (
      spec_row.research_provenance ->> 'creative_brief_draft_id'
    )::uuid;
    scenario_position_value := (
      spec_row.research_provenance ->> 'scenario_position'
    )::integer;
  exception
    when invalid_text_representation or numeric_value_out_of_range then
      return false;
  end;
  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = research_run_id_value
    and draft.id = research_draft_id_value
    and draft.product_id = spec_row.product_id
    and draft.status = 'approved';
  if draft_row.id is null then
    return false;
  end if;

  -- Compatibility is intentionally limited to drafts that never had the
  -- modern category object. A modern spec created before this migration has
  -- no receipt and therefore fails closed until it is recomputed.
  if jsonb_typeof(draft_row.brief -> 'category_analysis')
       is distinct from 'object' then
    return position(
      'researchcategoryrule/' in lower(spec_row.compiled_prompt)
    ) = 0 and not exists (
      select 1
      from content_factory.generation_spec_research_category_rule_bindings
        receipt
      where receipt.organization_id = organization_id_value
        and receipt.spec_id = spec_id_value
        and receipt.spec_version = spec_version_value
    );
  end if;
  if spec_row.canonical_learning_context ->> 'source'
       is distinct from 'approved_research'
     or spec_row.performance_policy_provenance is not null then
    return false;
  end if;

  select receipt.* into receipt_row
  from content_factory.generation_spec_research_category_rule_bindings receipt
  where receipt.organization_id = organization_id_value
    and receipt.spec_id = spec_id_value
    and receipt.spec_version = spec_version_value;
  if receipt_row.id is null then
    return false;
  end if;

  select * into temporal_binding
  from content_factory_private
    .generation_spec_research_category_temporal_binding(
      organization_id_value, research_run_id_value, research_draft_id_value
    );
  if temporal_binding.category_binding_id is null then
    return false;
  end if;
  select binding.* into current_binding
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = spec_row.product_id
  order by binding.binding_version desc, binding.id desc
  limit 1;
  if current_binding.id is null then
    return false;
  end if;

  research_structure_value :=
    content_factory_private.generation_spec_research_structure(
      draft_row.brief, scenario_position_value
    );
  research_rule_context_value := research_structure_value
    || jsonb_build_object('source', 'approved_research');
  rule_fragment_value := content_factory_private
    .generation_spec_research_category_rule_fragment(
      research_rule_context_value
    );
  expected_primary_hook := coalesce(
    research_structure_value #>> '{hook_patterns,0}', 'none'
  );

  if research_structure_value is null
     or rule_fragment_value is null
     or spec_row.canonical_learning_context ->> 'creative_angle'
          is distinct from research_structure_value ->> 'creative_angle'
     or spec_row.canonical_learning_context -> 'hook_patterns'
          is distinct from research_structure_value -> 'hook_patterns'
     or spec_row.prompt_hash is distinct from
          content_factory_private.raw_text_sha256(spec_row.compiled_prompt)
     or not content_factory_private
       .generation_spec_prompt_has_exact_category_rule(
         spec_row.compiled_prompt, rule_fragment_value
       )
     or receipt_row.generation_spec_version_id <> spec_row.version_id
     or receipt_row.spec_hash <> spec_row.spec_hash
     or receipt_row.prompt_hash <> spec_row.prompt_hash
     or receipt_row.research_snapshot_hash
          is distinct from spec_row.research_snapshot_hash
     or receipt_row.product_id <> spec_row.product_id
     or receipt_row.research_run_id <> research_run_id_value
     or receipt_row.research_draft_id <> research_draft_id_value
     or receipt_row.research_draft_content_hash <> draft_row.content_hash
     or receipt_row.research_draft_created_at <> draft_row.created_at
     or receipt_row.scenario_position <> scenario_position_value
     or receipt_row.market_category_id <>
          temporal_binding.market_category_id
     or receipt_row.category_binding_id <>
          temporal_binding.category_binding_id
     or receipt_row.category_binding_version <>
          temporal_binding.category_binding_version
     or receipt_row.category_binding_source_run_id <>
          temporal_binding.category_binding_source_run_id
     or receipt_row.category_binding_source_draft_id <>
          temporal_binding.category_binding_source_draft_id
     or receipt_row.category_binding_candidate_hash <>
          temporal_binding.category_binding_candidate_hash
     or receipt_row.category_binding_confirmed_at <>
          temporal_binding.category_binding_confirmed_at
     or receipt_row.rule_version <> 'ResearchCategoryRule/v2'
     or receipt_row.category_maturity <>
          research_structure_value ->> 'category_maturity'
     or receipt_row.competitor_coverage <>
          research_structure_value ->> 'competitor_coverage'
     or receipt_row.primary_signal <>
          research_structure_value ->> 'primary_signal'
     or receipt_row.creative_angle <>
          research_structure_value ->> 'creative_angle'
     or receipt_row.primary_hook <> expected_primary_hook
     or receipt_row.rule_hash <>
          content_factory_private.raw_text_sha256(rule_fragment_value)
     or receipt_row.stale_error_code <>
          'generation_spec_research_category_rule_stale'
     or current_binding.id <> receipt_row.category_binding_id
     or current_binding.category_id <> receipt_row.market_category_id
     or current_binding.binding_version <>
          receipt_row.category_binding_version
     or not exists (
       select 1
       from content_factory.research_market_categories category
       where category.organization_id = organization_id_value
         and category.id = receipt_row.market_category_id
         and category.status = 'active'
     )
     or not content_factory_private.research_generation_spec_evidence_fresh(
       organization_id_value, spec_id_value,
       spec_version_value, spec_hash_value
     ) then
    return false;
  end if;
  return true;
end;
$$;

create or replace function
  content_factory_private.guard_generation_job_research_category_rule()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  product_id_value uuid;
begin
  if new.mode <> 'real' or new.provider <> 'runway'
     or not new.allow_real_spend or new.generation_spec_id is null then
    return new;
  end if;
  if tg_op = 'UPDATE'
     and not (old.status = 'queued' and new.status = 'starting') then
    return new;
  end if;

  select version.product_id into product_id_value
  from content_factory.generation_spec_versions version
  where version.organization_id = new.organization_id
    and version.spec_id = new.generation_spec_id
    and version.spec_version = new.generation_spec_version
    and version.spec_hash = new.generation_spec_hash;
  if product_id_value is not null then
    -- Category resolution serializes on this exact arbitrary product scope.
    -- On provider claim the existing trigger order already owns stage then
    -- generation-spec locks, so this preserves stage -> spec -> product.
    perform pg_advisory_xact_lock(
      hashtext(new.organization_id::text),
      hashtext('research-market-product:' || product_id_value::text)
    );
  end if;

  if product_id_value is null
     or not content_factory_private
       .generation_spec_research_category_rule_current(
         new.organization_id, new.generation_spec_id,
         new.generation_spec_version, new.generation_spec_hash
       ) then
    if tg_op = 'UPDATE' then
      -- The installed public claim wrapper atomically terminalizes this
      -- outward code and releases reservations. DETAIL preserves the exact
      -- internal reason while guaranteeing no provider call can follow.
      raise exception using
        errcode = '55000',
        message = 'generation_spec_provider_start_stale',
        detail = 'generation_spec_research_category_rule_stale';
    end if;
    raise exception using
      errcode = '55000',
      message = 'generation_spec_research_category_rule_stale';
  end if;
  return new;
end;
$$;

-- Alphabetical BEFORE-trigger order puts this after the installed spec/source
-- binding guards. It therefore sees the server-bound spec on INSERT and is
-- still the last deterministic gate on queued -> starting before provider IO.
drop trigger if exists c_research_category_generation_rule_guard
  on content_factory.generation_jobs;
create trigger c_research_category_generation_rule_guard
before insert or update of status on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_generation_job_research_category_rule();

-- Categories were append-only but the original status enum advertised a
-- retirement transition that no caller could perform. Keep the identity row
-- immutable except for one audited active -> retired transition.
create table content_factory.research_market_category_retirement_events (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    category_id uuid not null,
    reason text not null check (length(btrim(reason)) between 3 and 500),
    retired_by uuid not null,
    retired_at timestamptz not null,
    idempotency_key text not null check (
      length(idempotency_key) between 8 and 180
    ),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
    constraint research_market_category_retirement_events_org_id_uq
      unique (organization_id, id),
    constraint research_market_category_retirement_events_category_uq
      unique (organization_id, category_id),
    constraint research_market_category_retirement_events_key_uq
      unique (organization_id, idempotency_key),
    constraint research_market_category_retirement_events_hash_uq
      unique (organization_id, event_hash),
    foreign key (organization_id, category_id)
      references content_factory.research_market_categories(
        organization_id, id
      ),
    foreign key (organization_id, retired_by)
      references content_factory.memberships(organization_id, profile_id)
);

alter table content_factory.research_market_category_retirement_events
  enable row level security;
revoke all on content_factory.research_market_category_retirement_events
  from public, anon, authenticated, service_role;

create trigger reject_research_market_category_retirement_event_mutation
before update or delete
on content_factory.research_market_category_retirement_events
for each row execute function
  content_factory_private.reject_research_market_identity_mutation();

create or replace function
  content_factory_private.reject_research_market_identity_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE'
     and tg_table_schema = 'content_factory'
     and tg_table_name = 'research_market_categories'
     and to_jsonb(old) ->> 'status' = 'active'
     and to_jsonb(new) ->> 'status' = 'retired'
     and to_jsonb(new) - 'status' = to_jsonb(old) - 'status'
     and current_setting(
       'contentengine.market_category_retirement', true
     ) = to_jsonb(old) ->> 'id' then
    return new;
  end if;
  raise exception using
    errcode = '55000',
    message = tg_table_name || '_append_only';
end;
$$;

create or replace function public.creator_retire_research_market_category(
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
  organization_id_value uuid;
  category_id_value uuid;
  user_id_value uuid;
  reason_value text;
  idempotency_key_value text;
  request_hash_value text;
  event_hash_value text;
  retired_at_value timestamptz;
  previous_retirement_setting text;
  category_row content_factory.research_market_categories%rowtype;
  event_row
    content_factory.research_market_category_retirement_events%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'category_id', 'reason',
       'idempotency_key', 'confirmation'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'category_id', 'reason',
       'idempotency_key', 'confirmation'
     ]::text[]
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_market_category_retirement_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  category_id_value := content_factory_private.require_uuid(
    p_payload, 'category_id'
  );
  user_id_value := content_factory_private.current_profile_id();
  perform content_factory_private.membership_role(
    organization_id_value, true, array['owner', 'admin']
  );
  reason_value := btrim(content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  ));
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'organization_id', organization_id_value,
    'category_id', category_id_value,
    'reason', reason_value,
    'confirmation', true
  ));
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('retire-market-category:' || category_id_value::text)
  );

  select event.* into event_row
  from content_factory.research_market_category_retirement_events event
  where event.organization_id = organization_id_value
    and event.idempotency_key = idempotency_key_value;
  if event_row.id is not null then
    if event_row.category_id <> category_id_value
       or event_row.request_hash <> request_hash_value then
      raise exception using
        errcode = '23505', message = 'idempotency_key_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'version', 'research-market-category-retirement-v1',
      'category_id', event_row.category_id,
      'status', 'retired',
      'retirement_event_id', event_row.id,
      'retired_at', event_row.retired_at,
      'replayed', true
    );
  end if;

  select category.* into category_row
  from content_factory.research_market_categories category
  where category.organization_id = organization_id_value
    and category.id = category_id_value
  for update;
  if category_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_market_category_not_found';
  end if;
  if category_row.status <> 'active' then
    raise exception using
      errcode = '55000', message = 'research_market_category_already_retired';
  end if;

  retired_at_value := clock_timestamp();
  previous_retirement_setting := current_setting(
    'contentengine.market_category_retirement', true
  );
  perform set_config(
    'contentengine.market_category_retirement', category_id_value::text, true
  );
  begin
    update content_factory.research_market_categories category
    set status = 'retired'
    where category.organization_id = organization_id_value
      and category.id = category_id_value
      and category.status = 'active';
    if not found then
      raise exception using
        errcode = '55000',
        message = 'research_market_category_retirement_stale';
    end if;
  exception when others then
    perform set_config(
      'contentengine.market_category_retirement',
      coalesce(previous_retirement_setting, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.market_category_retirement',
    coalesce(previous_retirement_setting, ''), true
  );

  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'research-market-category-retirement-v1',
    'organization_id', organization_id_value,
    'category_id', category_id_value,
    'reason', reason_value,
    'retired_by', user_id_value,
    'retired_at', retired_at_value,
    'request_hash', request_hash_value
  ));
  insert into content_factory.research_market_category_retirement_events (
    organization_id, category_id, reason, retired_by, retired_at,
    idempotency_key, request_hash, event_hash
  ) values (
    organization_id_value, category_id_value, reason_value, user_id_value,
    retired_at_value, idempotency_key_value, request_hash_value,
    event_hash_value
  ) returning * into event_row;

  return jsonb_build_object(
    'ok', true,
    'version', 'research-market-category-retirement-v1',
    'category_id', event_row.category_id,
    'status', 'retired',
    'retirement_event_id', event_row.id,
    'retired_at', event_row.retired_at,
    'replayed', false
  );
end;
$$;

revoke all on function public.creator_retire_research_market_category(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_retire_research_market_category(jsonb)
  to authenticated;

revoke all on function
  content_factory_private.generation_spec_research_structure(jsonb, integer)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_spec_research_category_rule_fragment(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_spec_prompt_has_exact_category_rule(
    text, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_spec_research_category_temporal_binding(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.research_draft_market_category_id(
    uuid, uuid, uuid
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.capture_generation_spec_research_category_rule()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_spec_research_category_rule_current(
    uuid, uuid, integer, text
  ) from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.guard_generation_job_research_category_rule()
  from public, anon, authenticated, service_role;

comment on table
  content_factory.generation_spec_research_category_rule_bindings is
  'Append-only hash receipt binding a modern approved-research generation spec to its exact temporal dynamic category and allowlisted provider rule; contains no raw source material.';

commit;

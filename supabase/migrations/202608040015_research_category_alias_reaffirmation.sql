begin;

-- A later approved draft may describe the same market category with a new
-- human-readable synonym.  Keep taxonomy correction explicit and append-only:
-- the user confirms that exact candidate, the alias is added to the stable
-- category, and a new binding records the exact run/draft decision without
-- rewriting any prior identity or source-analysis history.
alter table content_factory.research_product_market_category_bindings
  drop constraint
    research_product_market_category_bindings_decision_action_check;
alter table content_factory.research_product_market_category_bindings
  add constraint
    research_product_market_category_bindings_decision_action_check
  check (decision_action in (
    'bind_existing', 'create_and_bind', 'reclassify',
    'create_and_reclassify', 'reaffirm'
  ));

create or replace function public.creator_reaffirm_research_market_category(
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
  user_id_value uuid;
  organization_id_value uuid;
  run_id_value uuid;
  product_id_value uuid;
  category_id_value uuid;
  candidate_hash_value text;
  reason_value text;
  idempotency_key_value text;
  request_payload_value jsonb;
  replay_value jsonb;
  candidate_value jsonb;
  alias_value text;
  alias_key_value text;
  existing_alias_category_id uuid;
  current_binding
    content_factory.research_product_market_category_bindings%rowtype;
  category_row content_factory.research_market_categories%rowtype;
  draft_row content_factory.creative_brief_drafts%rowtype;
  binding_row
    content_factory.research_product_market_category_bindings%rowtype;
  source_id_value uuid;
  source_binding_id_value uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'run_id', 'action', 'category_id',
       'candidate_hash', 'confirmation', 'reason', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'organization_id', 'run_id', 'action', 'category_id',
       'candidate_hash', 'confirmation', 'reason', 'idempotency_key'
     ]::text[]
     or p_payload ->> 'action' <> 'reaffirm'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'research_market_reaffirmation_payload_invalid';
  end if;
  user_id_value := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  category_id_value := content_factory_private.require_uuid(
    p_payload, 'category_id'
  );
  candidate_hash_value := content_factory_private.require_text(
    p_payload, 'candidate_hash', 64, 64
  );
  if candidate_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using
      errcode = '22023', message = 'candidate_hash_invalid';
  end if;
  reason_value := btrim(content_factory_private.require_text(
    p_payload, 'reason', 3, 500
  ));
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  select run.product_id into product_id_value
  from content_factory.product_research_runs run
  join content_factory.organizations organization
    on organization.id = run.organization_id
   and organization.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = run.organization_id
   and membership.profile_id = user_id_value
   and membership.status = 'active'
  where run.organization_id = organization_id_value
    and run.id = run_id_value
    and run.status = 'completed';
  if product_id_value is null then
    raise exception using
      errcode = '22023', message = 'research_run_not_found';
  end if;
  perform content_factory_private.membership_role(
    organization_id_value, false, array['owner', 'admin', 'producer']
  );

  request_payload_value := p_payload - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id_value,
    'creator_reaffirm_research_market_category',
    idempotency_key_value,
    request_payload_value
  );
  if replay_value is not null then
    return replay_value;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-market-category-registry')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('research-market-product:' || product_id_value::text)
  );
  candidate_value := content_factory_private.research_market_category_candidate(
    organization_id_value, run_id_value
  );
  if candidate_value is null
     or candidate_value ->> 'candidate_hash' <> candidate_hash_value then
    raise exception using
      errcode = '55000', message = 'research_market_category_candidate_stale';
  end if;

  select binding.* into current_binding
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id = organization_id_value
    and binding.product_id = product_id_value
  order by binding.binding_version desc, binding.id desc
  limit 1
  for update;
  if current_binding.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_binding_required';
  end if;
  if current_binding.category_id <> category_id_value then
    raise exception using
      errcode = '55000', message = 'research_market_category_reaffirmation_stale';
  end if;
  select category.* into category_row
  from content_factory.research_market_categories category
  where category.organization_id = organization_id_value
    and category.id = category_id_value
    and category.status = 'active'
  for share;
  if category_row.id is null then
    raise exception using
      errcode = '22023', message = 'research_market_category_not_found';
  end if;

  alias_value := btrim(candidate_value ->> 'category_name');
  alias_key_value :=
    content_factory_private.research_market_identity_key(alias_value);
  if length(alias_value) not between 2 and 160
     or length(alias_key_value) not between 2 and 160 then
    raise exception using
      errcode = '22023', message = 'research_market_aliases_invalid';
  end if;
  select alias.category_id into existing_alias_category_id
  from content_factory.research_market_category_aliases alias
  where alias.organization_id = organization_id_value
    and alias.normalized_alias = alias_key_value;
  if existing_alias_category_id = category_id_value then
    raise exception using
      errcode = '55000',
      message = 'research_market_category_alias_already_registered';
  elsif existing_alias_category_id is not null then
    raise exception using
      errcode = '23505', message = 'research_market_category_alias_conflict';
  end if;

  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id_value
    and draft.run_id = run_id_value
    and draft.id = (candidate_value ->> 'draft_id')::uuid
    and draft.product_id = product_id_value
    and jsonb_typeof(draft.brief -> 'category_analysis') = 'object'
    and content_factory_private.json_hash(
      draft.brief -> 'category_analysis'
    ) = candidate_hash_value;
  if draft_row.id is null then
    raise exception using
      errcode = '55000', message = 'research_market_category_candidate_stale';
  end if;

  insert into content_factory.research_market_category_aliases (
    organization_id, category_id, alias_value, normalized_alias, created_by
  ) values (
    organization_id_value, category_id_value, alias_value, alias_key_value,
    user_id_value
  );
  insert into content_factory.research_product_market_category_bindings (
    organization_id, product_id, category_id, previous_binding_id,
    binding_version, decision_action, source_run_id, source_draft_id,
    candidate_hash, reason, confirmed_by, idempotency_key
  ) values (
    organization_id_value, product_id_value, category_id_value,
    current_binding.id, current_binding.binding_version + 1, 'reaffirm',
    run_id_value, draft_row.id, candidate_hash_value, reason_value,
    user_id_value, idempotency_key_value
  ) returning * into binding_row;

  perform public.system_register_research_category_sources(
    jsonb_build_object(
      'organization_id', organization_id_value,
      'run_id', run_id_value
    )
  );
  for source_id_value in
    select distinct source_ref.value::uuid
    from jsonb_array_elements_text(draft_row.source_ids) source_ref(value)
    order by source_ref.value::uuid
  loop
    source_binding_id_value := content_factory_private
      .append_research_draft_source_analysis_binding(
        organization_id_value, run_id_value, draft_row.id, source_id_value,
        null, 'baseline_adoption'
      );
    if source_binding_id_value is null then
      raise exception using
        errcode = '55000',
        message = 'research_market_category_reaffirmation_source_failed';
    end if;
  end loop;

  result_value := jsonb_build_object(
    'ok', true,
    'version', 'research-market-category-reaffirmation-v1',
    'category', jsonb_build_object(
      'category_key', category_row.id,
      'canonical_name', category_row.canonical_name,
      'definition', category_row.definition,
      'status', category_row.status,
      'aliases', (
        select coalesce(
          jsonb_agg(alias.alias_value order by alias.normalized_alias),
          '[]'::jsonb
        )
        from content_factory.research_market_category_aliases alias
        where alias.organization_id = organization_id_value
          and alias.category_id = category_row.id
      )
    ),
    'binding', jsonb_build_object(
      'binding_id', binding_row.id,
      'binding_version', binding_row.binding_version,
      'product_id', binding_row.product_id,
      'category_key', binding_row.category_id,
      'previous_binding_id', binding_row.previous_binding_id,
      'decision_action', binding_row.decision_action,
      'source_run_id', binding_row.source_run_id,
      'source_draft_id', binding_row.source_draft_id,
      'candidate_hash', binding_row.candidate_hash,
      'confirmed_by', binding_row.confirmed_by,
      'confirmed_at', binding_row.confirmed_at
    ),
    'alias', jsonb_build_object(
      'value', alias_value,
      'normalized_value', alias_key_value
    ),
    'guidance', jsonb_build_object(
      'status', 'bound',
      'recommended_next_step', 'continue_with_bound_category',
      'confirmation_received', true,
      'paid_provider_action', false
    )
  );
  perform content_factory_private.emit_event(
    organization_id_value,
    user_id_value,
    'research_market_category_reaffirmed',
    'research_market_category_binding',
    binding_row.id::text,
    jsonb_build_object(
      'action', 'reaffirm',
      'product_id', product_id_value,
      'category_key', category_id_value,
      'run_id', run_id_value,
      'candidate_hash', candidate_hash_value,
      'alias_key', alias_key_value,
      'paid_provider_action', false
    ),
    'research-market-category-reaffirm:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    user_id_value,
    'creator_reaffirm_research_market_category',
    idempotency_key_value,
    request_payload_value,
    result_value
  );
end;
$$;

revoke all on function public.creator_reaffirm_research_market_category(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_reaffirm_research_market_category(jsonb)
  to authenticated;

comment on function public.creator_reaffirm_research_market_category(jsonb) is
  'Explicitly confirms that one exact research candidate is a new alias of the current stable category, then appends its local source bindings; no provider call is performed.';

select pg_notify('pgrst', 'reload schema');

commit;

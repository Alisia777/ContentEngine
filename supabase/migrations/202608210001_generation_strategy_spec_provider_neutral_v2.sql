begin;

-- A strategy specification approves a stable recipe, source and assets.  It
-- does not approve an execution vendor.  The vendor/model are selected later
-- from generation_strategy_provider_routes, priced during the free preflight
-- and finally pinned by the signed readiness receipt/runtime fingerprint.
-- Scope v1 predated that route registry and wrote provider='runway' into every
-- strategy spec, even when the paid route was fal/Pika or fal/Kling.  Keep v1
-- rows readable, but make all newly prepared scopes explicitly route-deferred.

alter function
  content_factory_private.generation_strategy_spec_scope_v1(jsonb)
  rename to generation_strategy_spec_scope_legacy_v1;

create or replace function
  content_factory_private.generation_strategy_spec_scope_v2(p_scope jsonb)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  legacy_scope jsonb;
begin
  if jsonb_typeof(p_scope) <> 'object'
     or p_scope - array[
       'version', 'authority_kind', 'primary_media_id', 'media_ids',
       'platform', 'route_policy', 'strategy_id', 'recipe', 'input_mode',
       'duration_seconds', 'product_category', 'format', 'ratio',
       'resolution', 'audio', 'spoken_dialogue', 'reference_count',
       'reference_video', 'first_frame', 'last_frame', 'selection',
       'selection_hash', 'asset_snapshot', 'asset_snapshot_hash',
       'source', 'source_hash', 'mechanics', 'mechanics_hash'
     ]::text[] <> '{}'::jsonb
     or not p_scope ?& array[
       'version', 'authority_kind', 'primary_media_id', 'media_ids',
       'platform', 'route_policy', 'strategy_id', 'recipe', 'input_mode',
       'duration_seconds', 'product_category', 'format', 'ratio',
       'resolution', 'audio', 'spoken_dialogue', 'reference_count',
       'reference_video', 'first_frame', 'last_frame', 'selection',
       'selection_hash', 'asset_snapshot', 'asset_snapshot_hash',
       'source', 'source_hash', 'mechanics', 'mechanics_hash'
     ]::text[]
     or p_scope ->> 'version' <>
          'generation-strategy-spec-scope-v2'
     or p_scope ->> 'authority_kind' <> 'strategy_recipe'
     or p_scope -> 'route_policy' is distinct from jsonb_build_object(
       'version', 'generation-strategy-route-policy-v1',
       'authority', 'generation_strategy_provider_routes',
       'binding', 'deferred_until_preflight'
     ) then
    return null;
  end if;

  -- Reuse the complete, already deployed v1 validation for recipe identity,
  -- output, role counts, hashes, source evidence and mechanics.  Only the
  -- obsolete provider hint is translated; no authority check is weakened.
  legacy_scope := (p_scope - 'route_policy') || jsonb_build_object(
    'version', 'generation-strategy-spec-scope-v1',
    'provider', 'runway'
  );
  if content_factory_private
       .generation_strategy_spec_scope_legacy_v1(legacy_scope)
       is distinct from legacy_scope then
    return null;
  end if;
  return p_scope;
exception
  when invalid_text_representation or numeric_value_out_of_range then
    return null;
end;
$$;

revoke all on function
  content_factory_private.generation_strategy_spec_scope_v2(jsonb)
  from public, anon, authenticated, service_role;

-- Compatibility dispatch for mature binding/prompt functions.  Historical
-- v1 stays byte-for-byte valid; v2 is returned unchanged rather than being
-- rewritten to a fake provider.
create function
  content_factory_private.generation_strategy_spec_scope_v1(p_scope jsonb)
returns jsonb
language sql
immutable
set search_path = ''
as $$
  select coalesce(
    content_factory_private
      .generation_strategy_spec_scope_legacy_v1(p_scope),
    content_factory_private.generation_strategy_spec_scope_v2(p_scope)
  );
$$;

revoke all on function
  content_factory_private.generation_strategy_spec_scope_v1(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.generation_strategy_spec_scope_legacy_v1(jsonb)
  from public, anon, authenticated, service_role;

-- The generic version compiler already delegates strategy scopes through the
-- compatibility function above.  Version only its hash domain so a v2 scope
-- can never share an identity domain with the legacy provider-bearing shape.
do $patch_generation_strategy_spec_hash_v2$
declare
  definition_value text;
  patched_value text;
  old_pattern constant text :=
    $r$when[[:space:]]+normalized_scope[[:space:]]*->>[[:space:]]*'authority_kind'[[:space:]]*=[[:space:]]*'strategy_recipe'[[:space:]]+then[[:space:]]*'generation-strategy-spec-v1'$r$;
  new_fragment constant text := $new$when normalized_scope ->> 'authority_kind' = 'strategy_recipe'
        then case
          when normalized_scope ->> 'version' =
                 'generation-strategy-spec-scope-v2'
            then 'generation-strategy-spec-v2'
          else 'generation-strategy-spec-v1'
        end$new$;
begin
  select pg_catalog.pg_get_functiondef(
    'content_factory_private.create_generation_spec_version(uuid,uuid,uuid,jsonb,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,uuid,text,uuid)'::regprocedure
  ) into definition_value;
  if definition_value is null
     or regexp_count(definition_value, old_pattern) <> 1
     or position('generation-strategy-spec-v2' in definition_value) > 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_spec_v2_hash_target_invalid';
  end if;
  patched_value := regexp_replace(
    definition_value, old_pattern, new_fragment
  );
  if regexp_count(patched_value, old_pattern) <> 0
     or position('generation-strategy-spec-v2' in patched_value) = 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_spec_v2_hash_patch_invalid';
  end if;
  execute patched_value;
end;
$patch_generation_strategy_spec_hash_v2$;

-- Prepare keeps the v1 browser request DTO.  Route choice is deliberately not
-- accepted from that request; the server emits the fixed deferred policy.
do $patch_generation_strategy_prepare_scope_v2$
declare
  definition_value text;
  patched_value text;
  version_pattern constant text :=
    $r$'version'[[:space:]]*,[[:space:]]*'generation-strategy-spec-scope-v1'$r$;
  provider_pattern constant text :=
    $r$'provider'[[:space:]]*,[[:space:]]*'runway'[[:space:]]*,$r$;
  provider_literal_pattern constant text :=
    $r$'provider'[[:space:]]*,[[:space:]]*'runway'$r$;
  version_fragment constant text :=
    $new$'version', 'generation-strategy-spec-scope-v2'$new$;
  route_fragment constant text := $new$'route_policy', jsonb_build_object(
      'version', 'generation-strategy-route-policy-v1',
      'authority', 'generation_strategy_provider_routes',
      'binding', 'deferred_until_preflight'
    ),$new$;
  declaration_old constant text := $old$  result_value jsonb;
  result_spec jsonb;$old$;
  declaration_new constant text := $new$  result_value jsonb;
  result_spec jsonb;
  legacy_scope_value jsonb;
  legacy_request_payload jsonb;
  legacy_request_hash_value text;
  legacy_result_value jsonb;$new$;
  legacy_scope_marker constant text :=
    $legacy$legacy_scope_value := (exact_scope_value - 'route_policy') ||$legacy$;
  call_old constant text :=
    $old$  result_value := public.creator_prepare_generation_spec($old$;
  call_new constant text := $new$  -- Cross-version idempotency: a retry of a
  -- pre-migration request must replay its immutable v1 draft, not conflict
  -- because the server now emits v2 and not create a duplicate under a new
  -- key. The public project boundary always strips project_id before the
  -- generic command computes its receipt hash, so reconstruct that one
  -- historical payload exactly under the old advisory lock.
  legacy_scope_value := (exact_scope_value - 'route_policy') ||
    jsonb_build_object(
      'version', 'generation-strategy-spec-scope-v1',
      'provider', 'runway'
  );
  legacy_request_payload := jsonb_build_object(
    'organization_id', organization_id_value,
    'exact_scope', legacy_scope_value,
    'editable_intent', editable_intent_value,
    'proposed_prompt', proposed_prompt_value,
    'learning_context', jsonb_build_object(
      'creative_angle', 'product_focus',
      'hook_patterns', '[]'::jsonb,
      'source', 'baseline',
      'compiler_version', 'safe-brief-v7',
      'product_category', product_category_value
    ),
    'repair_context', 'null'::jsonb,
    'research_provenance', 'null'::jsonb,
    'performance_policy_provenance', 'null'::jsonb,
    'repair_provenance', 'null'::jsonb,
    'confirmation', true,
    'reason', reason_value
  );
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtext(organization_id_value::text),
    pg_catalog.hashtext(
      'creator_prepare_generation_spec:strategy-spec:' ||
      idempotency_key_value
    )
  );
  select receipt.request_hash, receipt.result
    into legacy_request_hash_value, legacy_result_value
  from content_factory.command_receipts receipt
  where receipt.organization_id = organization_id_value
    and receipt.command_name = 'creator_prepare_generation_spec'
    and receipt.idempotency_key =
          'strategy-spec:' || idempotency_key_value;
  if legacy_request_hash_value is not null then
    if legacy_request_hash_value <>
         content_factory_private.json_hash(legacy_request_payload) then
      raise exception using errcode = '23505',
        message = 'idempotency_key_conflict';
    end if;
    result_value := legacy_result_value;
    exact_scope_value := legacy_scope_value;
  else
    result_value := public.creator_prepare_generation_spec($new$;
  close_old constant text := $old$  );
  result_spec := result_value -> 'generation_spec';$old$;
  close_new constant text := $new$  );
  end if;
  result_spec := result_value -> 'generation_spec';$new$;
begin
  select pg_catalog.pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  ) into definition_value;
  if definition_value is null
     or regexp_count(definition_value, version_pattern) <> 1
     or regexp_count(definition_value, provider_pattern) <> 1
     or position('generation-strategy-route-policy-v1'
          in definition_value) > 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_prepare_scope_v2_target_invalid';
  end if;
  patched_value := regexp_replace(
    definition_value, version_pattern, version_fragment
  );
  patched_value := regexp_replace(
    patched_value, provider_pattern, route_fragment
  );
  if (length(patched_value) - length(replace(
       patched_value, declaration_old, ''
     ))) / length(declaration_old) <> 1
     or (length(patched_value) - length(replace(
       patched_value, call_old, ''
     ))) / length(call_old) <> 1
     or (length(patched_value) - length(replace(
       patched_value, close_old, ''
     ))) / length(close_old) <> 1
     or (length(patched_value) - length(replace(
       patched_value, $key$'strategy-spec:' || idempotency_key_value$key$, ''
     ))) / length($key$'strategy-spec:' || idempotency_key_value$key$) <> 1
  then
    raise exception using errcode = '55000',
      message = 'generation_strategy_prepare_idempotency_v2_target_invalid';
  end if;
  -- Change only the installed generic call before injecting the legacy replay
  -- branch, whose old key must intentionally remain byte-for-byte old.
  patched_value := replace(
    patched_value,
    $key$'strategy-spec:' || idempotency_key_value$key$,
    $key$'strategy-spec-v2:' || idempotency_key_value$key$
  );
  patched_value := replace(
    patched_value, declaration_old, declaration_new
  );
  patched_value := replace(patched_value, call_old, call_new);
  patched_value := replace(patched_value, close_old, close_new);
  if regexp_count(patched_value, version_pattern) <> 1
     or regexp_count(
          split_part(
            patched_value, '-- Cross-version idempotency:', 1
          ),
          version_pattern
        ) <> 0
     or regexp_count(patched_value, provider_pattern) <> 0
     or regexp_count(patched_value, provider_literal_pattern) <> 1
     or regexp_count(
          split_part(
            patched_value, '-- Cross-version idempotency:', 1
          ),
          provider_literal_pattern
        ) <> 0
     or (length(patched_value) - length(replace(
          patched_value, legacy_scope_marker, ''
        ))) / length(legacy_scope_marker) <> 1
     or position('generation-strategy-spec-scope-v2'
          in patched_value) = 0
     or position('generation_strategy_provider_routes'
          in patched_value) = 0
     or position('strategy-spec-v2:' in patched_value) = 0
     or position('legacy_request_payload'
          in patched_value) = 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_prepare_scope_v2_patch_invalid';
  end if;
  execute patched_value;
end;
$patch_generation_strategy_prepare_scope_v2$;

-- The row projection is storage metadata, not route authority.  New strategy
-- rows therefore keep provider NULL and store recipe in model as before.
create or replace function
  content_factory_private.bind_generation_strategy_spec_scope_v1()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  scope_value jsonb;
  scope_contract text;
begin
  scope_value := content_factory_private
    .generation_strategy_spec_scope_v2(new.exact_scope);
  if scope_value is not null then
    scope_contract := 'generation-strategy-scope-v2';
    new.provider := null;
  else
    scope_value := content_factory_private
      .generation_strategy_spec_scope_legacy_v1(new.exact_scope);
    if scope_value is null then
      return new;
    end if;
    scope_contract := 'generation-strategy-scope-v1';
    new.provider := 'runway';
  end if;
  new.spec_contract_version := scope_contract;
  new.model := scope_value ->> 'recipe';
  new.input_mode := scope_value ->> 'input_mode';
  new.ratio := scope_value ->> 'ratio';
  new.resolution := scope_value ->> 'resolution';
  new.spoken_dialogue := false;
  new.reference_count := (scope_value ->> 'reference_count')::integer;
  new.reference_video := (scope_value ->> 'reference_video')::boolean;
  new.first_frame := false;
  new.last_frame := false;
  return new;
end;
$$;

revoke all on function
  content_factory_private.bind_generation_strategy_spec_scope_v1()
  from public, anon, authenticated, service_role;

alter table content_factory.generation_spec_versions
  drop constraint if exists
    generation_spec_versions_v1_v2_or_strategy_scope_check;

alter table content_factory.generation_spec_versions
  add constraint
    generation_spec_versions_v1_v2_strategy_v1_v2_scope_check
  check (
    (
      spec_contract_version is null and provider is null
      and input_mode is null and ratio is null and resolution is null
      and spoken_dialogue is null and reference_count is null
      and reference_video is null and first_frame is null and last_frame is null
      and model in ('gen4_turbo', 'seedance2_fast', 'seedream5_lite')
      and exact_scope = jsonb_build_object(
        'primary_media_id', primary_media_id,
        'media_ids', to_jsonb(media_ids),
        'platform', platform, 'model', model,
        'duration_seconds', duration_seconds,
        'product_category', product_category, 'format', format,
        'audio', audio
      )
    )
    or
    (
      spec_contract_version = 'generation-spec-scope-v2'
      and provider is not null and input_mode is not null
      and ratio is not null and resolution is not null
      and spoken_dialogue is not null and reference_count is not null
      and reference_video is not null and first_frame is not null
      and last_frame is not null
      and exact_scope = content_factory_private.generation_spec_scope_v2(
        exact_scope
      )
      and exact_scope = jsonb_build_object(
        'primary_media_id', primary_media_id,
        'media_ids', to_jsonb(media_ids),
        'platform', platform, 'provider', provider, 'model', model,
        'input_mode', input_mode, 'duration_seconds', duration_seconds,
        'product_category', product_category, 'format', format,
        'ratio', ratio, 'resolution', resolution, 'audio', audio,
        'spoken_dialogue', spoken_dialogue,
        'reference_count', reference_count,
        'reference_video', reference_video,
        'first_frame', first_frame, 'last_frame', last_frame
      )
    )
    or
    (
      spec_contract_version = 'generation-strategy-scope-v1'
      and provider = 'runway'
      and model = exact_scope ->> 'recipe'
      and input_mode = exact_scope ->> 'input_mode'
      and ratio = exact_scope ->> 'ratio'
      and resolution = exact_scope ->> 'resolution'
      and spoken_dialogue = false
      and reference_count = (exact_scope ->> 'reference_count')::integer
      and reference_video = (exact_scope ->> 'reference_video')::boolean
      and first_frame = false and last_frame = false
      and exact_scope = content_factory_private
        .generation_strategy_spec_scope_legacy_v1(exact_scope)
      and primary_media_id::text = exact_scope ->> 'primary_media_id'
      and to_jsonb(media_ids) = exact_scope -> 'media_ids'
      and platform = exact_scope ->> 'platform'
      and duration_seconds = (exact_scope ->> 'duration_seconds')::integer
      and product_category = exact_scope ->> 'product_category'
      and format = exact_scope ->> 'format'
      and audio = (exact_scope ->> 'audio')::boolean
    )
    or
    (
      spec_contract_version = 'generation-strategy-scope-v2'
      and provider is null
      and model = exact_scope ->> 'recipe'
      and input_mode = exact_scope ->> 'input_mode'
      and ratio = exact_scope ->> 'ratio'
      and resolution = exact_scope ->> 'resolution'
      and spoken_dialogue = false
      and reference_count = (exact_scope ->> 'reference_count')::integer
      and reference_video = (exact_scope ->> 'reference_video')::boolean
      and first_frame = false and last_frame = false
      and exact_scope = content_factory_private
        .generation_strategy_spec_scope_v2(exact_scope)
      and primary_media_id::text = exact_scope ->> 'primary_media_id'
      and to_jsonb(media_ids) = exact_scope -> 'media_ids'
      and platform = exact_scope ->> 'platform'
      and duration_seconds = (exact_scope ->> 'duration_seconds')::integer
      and product_category = exact_scope ->> 'product_category'
      and format = exact_scope ->> 'format'
      and audio = (exact_scope ->> 'audio')::boolean
    )
  );

-- Binding accepts both immutable generations.  It still derives every asset,
-- source hash and recipe from the approved spec; provider/model are absent
-- here and remain authoritative only in the later route receipt.
do $patch_generation_strategy_spec_authority_v2$
declare
  definition_value text;
  patched_value text;
  old_fragment constant text := $old$or spec_row.spec_contract_version <>
          'generation-strategy-scope-v1'$old$;
  new_fragment constant text := $new$or spec_row.spec_contract_version not in (
          'generation-strategy-scope-v1',
          'generation-strategy-scope-v2'
        )$new$;
begin
  select pg_catalog.pg_get_functiondef(
    'content_factory_private.enforce_generation_strategy_spec_authority()'::regprocedure
  ) into definition_value;
  if definition_value is null
     or (length(definition_value) - length(replace(
       definition_value, old_fragment, ''
     ))) / length(old_fragment) <> 1
     or position('generation-strategy-scope-v2'
          in definition_value) > 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_spec_authority_v2_target_invalid';
  end if;
  patched_value := replace(
    definition_value, old_fragment, new_fragment
  );
  if position(old_fragment in patched_value) > 0
     or position('generation-strategy-scope-v2'
          in patched_value) = 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_spec_authority_v2_patch_invalid';
  end if;
  execute patched_value;
end;
$patch_generation_strategy_spec_authority_v2$;

-- Recreate the prompt compiler from its installed definition so every backend
-- resolves the compatibility function by its new OID after the v1 validator
-- rename.  The body itself is unchanged.
do $rebind_generation_strategy_prompt_scope_dispatch$
declare
  definition_value text;
begin
  select pg_catalog.pg_get_functiondef(
    'content_factory_private.generation_strategy_prompt_snapshot(uuid,uuid,jsonb)'::regprocedure
  ) into definition_value;
  if definition_value is null
     or position('generation_strategy_spec_scope_v1'
          in definition_value) = 0 then
    raise exception using errcode = '55000',
      message = 'generation_strategy_prompt_scope_dispatch_target_invalid';
  end if;
  execute definition_value;
end;
$rebind_generation_strategy_prompt_scope_dispatch$;

do $generation_strategy_spec_provider_neutral_v2_verify$
declare
  definition_value text;
  emitted_scope_prefix text;
  constraint_value text;
  provider_literal_pattern constant text :=
    $r$'provider'[[:space:]]*,[[:space:]]*'runway'$r$;
  legacy_sample jsonb;
  neutral_sample jsonb;
begin
  select version.exact_scope into legacy_sample
  from content_factory.generation_spec_versions version
  where version.spec_contract_version = 'generation-strategy-scope-v1'
  order by version.created_at desc
  limit 1;
  if legacy_sample is not null then
    neutral_sample := (legacy_sample - 'provider') || jsonb_build_object(
      'version', 'generation-strategy-spec-scope-v2',
      'route_policy', jsonb_build_object(
        'version', 'generation-strategy-route-policy-v1',
        'authority', 'generation_strategy_provider_routes',
        'binding', 'deferred_until_preflight'
      )
    );
    if content_factory_private.generation_strategy_spec_scope_v2(
         neutral_sample
       ) is distinct from neutral_sample then
      raise exception using message =
        'generation_strategy_spec_v2_legacy_conversion_invalid';
    end if;
  end if;

  select pg_catalog.pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  ) into definition_value;
  emitted_scope_prefix := split_part(
    definition_value, '-- Cross-version idempotency:', 1
  );
  if position('generation-strategy-spec-scope-v2'
       in emitted_scope_prefix) = 0
     or position('generation_strategy_provider_routes'
       in emitted_scope_prefix) = 0
     or position('-- Cross-version idempotency:'
       in definition_value) = 0
     or regexp_count(
          emitted_scope_prefix, provider_literal_pattern
        ) <> 0
     or regexp_count(
          definition_value, provider_literal_pattern
        ) <> 1 then
    raise exception using message =
      'generation_strategy_prepare_not_provider_neutral';
  end if;

  select pg_catalog.pg_get_constraintdef(constraint_row.oid)
    into constraint_value
  from pg_catalog.pg_constraint constraint_row
  where constraint_row.conrelid =
      'content_factory.generation_spec_versions'::regclass
    and constraint_row.conname =
      'generation_spec_versions_v1_v2_strategy_v1_v2_scope_check';
  if constraint_value is null
     or position('generation-strategy-scope-v2'
          in constraint_value) = 0
     or position('generation_strategy_spec_scope_v2'
          in constraint_value) = 0 then
    raise exception using message =
      'generation_strategy_spec_v2_constraint_invalid';
  end if;
end;
$generation_strategy_spec_provider_neutral_v2_verify$;

comment on function
  content_factory_private.generation_strategy_spec_scope_v2(jsonb) is
  'Validates provider-neutral strategy recipe scope v2. Execution provider/model are resolved only from generation_strategy_provider_routes during free preflight and pinned by the signed readiness receipt.';
comment on function
  content_factory_private.generation_strategy_spec_scope_v1(jsonb) is
  'Compatibility dispatcher for immutable strategy scope v1 and provider-neutral scope v2; returns the accepted wire document unchanged.';
comment on function
  public.creator_prepare_generation_strategy_spec(jsonb) is
  'Free authenticated prepare: emits provider-neutral recipe scope v2. Provider/model are not accepted from the browser and are deferred to the signed route preflight; no provider/spend action occurs.';

notify pgrst, 'reload schema';

commit;

begin;

-- The strategy wrapper already validates the browser-supplied project and
-- project access.  Forward that validated UUID to the project-scoped generic
-- prepare RPC.  Patch the installed definition so this forward migration has
-- one semantic delta and cannot drift from the existing wrapper contract.
do $forward_generation_strategy_spec_project_scope$
declare
  function_definition text;
  patched_definition text;
  old_pattern constant text :=
    '''organization_id''[[:space:]]*,[[:space:]]*organization_id_value' ||
    '[[:space:]]*,[[:space:]]*''idempotency_key''[[:space:]]*,';
  new_fragment constant text := $new$'organization_id', organization_id_value,
      'project_id', project_id_value,
      'idempotency_key',$new$;
begin
  select pg_catalog.pg_get_functiondef(
    'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
  ) into function_definition;

  if function_definition is null
     or regexp_count(function_definition, old_pattern) <> 1
     or position(new_fragment in function_definition) <> 0 then
    raise exception using
      errcode = '55000',
      message = 'generation_strategy_spec_project_scope_target_invalid';
  end if;

  patched_definition := regexp_replace(
    function_definition, old_pattern, new_fragment
  );
  if regexp_count(patched_definition, old_pattern) <> 0
     or (length(patched_definition) - length(replace(
       patched_definition, new_fragment, ''
     ))) / length(new_fragment) <> 1 then
    raise exception using
      errcode = '55000',
      message = 'generation_strategy_spec_project_scope_patch_invalid';
  end if;

  execute patched_definition;
end;
$forward_generation_strategy_spec_project_scope$;

revoke all on function
  public.creator_prepare_generation_strategy_spec(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.creator_prepare_generation_strategy_spec(jsonb)
  to authenticated;

comment on function public.creator_prepare_generation_strategy_spec(jsonb) is
  'Free authenticated prepare only: server-resolves recipe, assets, exact source and mechanics into a draft strategy spec; explicit ordinary spec approval remains mandatory and no provider/spend action occurs.';

notify pgrst, 'reload schema';

commit;

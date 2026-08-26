begin;
-- 202608260002_bootstrap_waiver_admin_v1
--
-- 25.08.2026 владелец поднял Климова и Михаила до роли admin («прямо макс
-- доступ, чтобы всё видел»): словарь ролей memberships, чек-констрейнты
-- training_access_waivers и сами waiver-строки расширили до admin, а вот
-- waiver-ветка creator_bootstrap осталась со списком ('operator', 'owner').
-- Активный waiver админа переставал действовать: state оставался 'learning',
-- и портал гнал администратора в «Обязательный допуск» даже по magic-ссылке
-- (боевой случай 26.08, v.klimov1313@gmail.com). Единственная правка —
-- список ролей в этой ветке; тело функции — действующее прод-определение.

create or replace function public.creator_bootstrap(p_payload jsonb default '{}'::jsonb)
 returns jsonb
 language plpgsql
 security definer
 set search_path to ''
as $function$
#variable_conflict use_variable
declare
  result jsonb;
  user_id uuid;
  organization_id uuid;
  actor_role text;
  waiver_row content_factory.training_access_waivers%rowtype;
begin
  result :=
    content_factory_private.creator_bootstrap_pre_training_waiver(p_payload);

  if jsonb_typeof(result) <> 'object'
     or coalesce(result ->> 'state', '') not in ('learning', 'workspace')
     or nullif(result #>> '{organization,id}', '') is null then
    return result;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := (result #>> '{organization,id}')::uuid;

  select membership.role into actor_role
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';

  if actor_role not in ('operator', 'admin', 'owner')
     or not content_factory_private.training_access_waiver_active(
       organization_id,
       user_id
     ) then
    return result;
  end if;

  select waiver.* into waiver_row
  from content_factory.training_access_waivers waiver
  where waiver.organization_id = organization_id
    and waiver.profile_id = user_id
    and waiver.scope = 'workspace_generation'
    and waiver.status = 'active';

  result := jsonb_set(result, '{state}', '"workspace"'::jsonb, true);
  result := jsonb_set(result, '{workspace_open}', 'true'::jsonb, true);
  result := jsonb_set(
    result, '{capabilities,mock_generation}', 'true'::jsonb, true
  );
  result := jsonb_set(
    result, '{capabilities,real_generation}', 'true'::jsonb, true
  );
  result := jsonb_set(
    result,
    '{learning,practical_project_required}',
    'false'::jsonb,
    true
  );
  result := result || jsonb_build_object(
    'training',
    coalesce(result -> 'training', '{}'::jsonb) || jsonb_build_object(
      'access_waiver',
      jsonb_build_object(
        'active', true,
        'scope', waiver_row.scope,
        'reason', waiver_row.grant_reason,
        'granted_at', waiver_row.granted_at
      )
    )
  );

  return result;
end;
$function$;

commit;

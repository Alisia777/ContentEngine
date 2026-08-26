begin;
-- 202608260012_hypothesis_owner_and_passport_v1
--
-- Два замыкания контура №3:
-- 1) Ответственный за гипотезу: назначение (роль owner/admin/producer),
--    срез отдаёт владельца и список членов команды для выбора; список гипотез
--    отдаёт «назначенную» запрашивающему гипотезу — форма генерации
--    подставит её сама, если оператор ничего не выбирал.
-- 2) Паспорт ролика показывает гипотезу: читается из манифеста происхождения
--    (точная версия, зафиксированная в момент bind), не из «текущего»
--    состояния. Патчи действующих определений — по точным якорям, fail-closed.

create or replace function public.creator_assign_content_hypothesis_owner(
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
  user_id uuid;
  organization_id uuid;
  hypothesis_row content_factory.content_hypotheses%rowtype;
  owner_value uuid;
  owner_name text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );

  select h.* into hypothesis_row
  from content_factory.content_hypotheses h
  where h.organization_id = organization_id
    and h.id = content_factory_private.require_uuid(p_payload, 'hypothesis_id');
  if hypothesis_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_not_found';
  end if;

  if not (p_payload ? 'owner_profile_id')
     or nullif(btrim(coalesce(p_payload ->> 'owner_profile_id', '')), '') is null
  then
    update content_factory.content_hypotheses h
    set owner_profile_id = null
    where h.organization_id = organization_id
      and h.id = hypothesis_row.id;
    return jsonb_build_object(
      'ok', true,
      'version', 'content-hypothesis-owner-v1',
      'owner', null
    );
  end if;

  owner_value := content_factory_private.require_uuid(
    p_payload, 'owner_profile_id'
  );
  select p.display_name into owner_name
  from content_factory.memberships m
  join content_factory.profiles p on p.id = m.profile_id
  where m.organization_id = organization_id
    and m.profile_id = owner_value
    and m.status = 'active';
  if owner_name is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_owner_not_member';
  end if;

  update content_factory.content_hypotheses h
  set owner_profile_id = owner_value
  where h.organization_id = organization_id
    and h.id = hypothesis_row.id;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-owner-v1',
    'owner', jsonb_build_object(
      'profile_id', owner_value,
      'display_name', owner_name
    )
  );
end;
$$;

revoke all on function public.creator_assign_content_hypothesis_owner(jsonb)
  from public, anon, service_role;
grant execute on function
  public.creator_assign_content_hypothesis_owner(jsonb) to authenticated;

-- Срез гипотезы: владелец + члены команды для назначения.
do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_hypothesis(jsonb)'::regprocedure
  );
  if strpos(src, '''members'', (') > 0 then
    raise exception 'hypothesis_detail_members_patch_already_applied';
  end if;
  if strpos(src, '''outcome'', hypothesis_row.outcome,') = 0
     or strpos(src, '''launches'', launches_value,') = 0 then
    raise exception 'hypothesis_detail_members_patch_anchor_missing';
  end if;

  src := replace(src,
    '''outcome'', hypothesis_row.outcome,',
    '''outcome'', hypothesis_row.outcome,
      ''owner_profile_id'', hypothesis_row.owner_profile_id,');

  src := replace(src,
    '''launches'', launches_value,',
    '''launches'', launches_value,
    ''members'', (
      select coalesce(jsonb_agg(jsonb_build_object(
        ''profile_id'', m.profile_id,
        ''display_name'', p.display_name,
        ''role'', m.role
      ) order by p.display_name), ''[]''::jsonb)
      from content_factory.memberships m
      join content_factory.profiles p on p.id = m.profile_id
      where m.organization_id = organization_id
        and m.status = ''active''
    ),');

  execute src;
end
$mig$;

-- Список гипотез: назначенная запрашивающему гипотеза (для автоподстановки
-- в формах генерации) и владелец в карточке.
do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_hypotheses(jsonb)'::regprocedure
  );
  if strpos(src, '''assigned'', (') > 0 then
    raise exception 'hypotheses_list_assigned_patch_already_applied';
  end if;
  if strpos(src, '''operator_selection'', (') = 0
     or strpos(src, '''title'', h.title,') = 0 then
    raise exception 'hypotheses_list_assigned_patch_anchor_missing';
  end if;

  src := replace(src,
    '''title'', h.title,',
    '''title'', h.title,
        ''owner_profile_id'', h.owner_profile_id,');

  src := replace(src,
    '''operator_selection'', (',
    '''assigned'', (
      select jsonb_build_object(
        ''hypothesis_id'', h2.id,
        ''code'', h2.code
      )
      from content_factory.content_hypotheses h2
      where h2.organization_id = organization_id
        and h2.project_id = project_id_value
        and h2.owner_profile_id = user_id
        and exists (
          select 1 from content_factory.content_hypothesis_versions av
          where av.organization_id = h2.organization_id
            and av.hypothesis_id = h2.id
            and av.status = ''approved''
        )
      order by h2.code desc
      limit 1
    ),
    ''operator_selection'', (');

  execute src;
end
$mig$;

-- Паспорт: гипотеза из манифеста происхождения — точная версия момента bind.
do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_result_passport(jsonb)'::regprocedure
  );
  if strpos(src, 'passport_hypothesis_value') > 0 then
    raise exception 'passport_hypothesis_patch_already_applied';
  end if;
  if strpos(src, 'manifest_row content_factory.generation_provenance_manifests%rowtype;') = 0
     or strpos(src, '''hypothesis'', null,') = 0
     or strpos(src, 'if manifest_row.id is null then') = 0 then
    raise exception 'passport_hypothesis_patch_anchor_missing';
  end if;

  src := replace(src,
    'manifest_row content_factory.generation_provenance_manifests%rowtype;',
    'manifest_row content_factory.generation_provenance_manifests%rowtype;
  passport_hypothesis_value jsonb := null;');

  src := replace(src,
    'if manifest_row.id is null then',
    'if manifest_row.hypothesis_id is not null then
    select jsonb_build_object(
      ''hypothesis_id'', h.id,
      ''code'', h.code,
      ''title'', h.title,
      ''outcome'', h.outcome,
      ''version'', v.version,
      ''statement'', v.statement,
      ''metric'', v.metric,
      ''baseline_value'', v.baseline_value,
      ''target_value'', v.target_value
    ) into passport_hypothesis_value
    from content_factory.content_hypotheses h
    left join content_factory.content_hypothesis_versions v
      on v.organization_id = h.organization_id
      and v.id = manifest_row.hypothesis_version_id
    where h.organization_id = organization_id
      and h.id = manifest_row.hypothesis_id;
  end if;

  if manifest_row.id is null then');

  src := replace(src,
    '''hypothesis'', null,',
    '''hypothesis'', passport_hypothesis_value,');

  execute src;
end
$mig$;

notify pgrst, 'reload schema';

commit;

begin;
-- 202609030007_public_default_privileges_hygiene_v1
--
-- Гигиена схемы public перед выдачей первой клиентской ссылки (витрина
-- ступени 1): (1) default privileges грантора postgres в public и storage
-- больше не раздают полные права anon/authenticated на каждый НОВЫЙ объект
-- (существующие права не трогаются — это мина под будущие таблицы, а не
-- ревизия прошлого); (2) явный REVOKE EXECUTE у anon с трёх duet-RPC —
-- 202608220008 ревокал от PUBLIC, но явный грант anon пришёл из default
-- privileges при CREATE и пережил все пересоздания; (3) search_path='' у
-- шести тривиальных триггерных функций (тела проверены: только now()/raise,
-- неквалифицированных ссылок нет). Остаточный риск задокументирован: defacl
-- грантора supabase_admin снять из-под postgres нельзя (нет членства);
-- наши миграции идут под postgres, чьи defacl этой миграцией закрыты.
-- view_portal_masha_status_current намеренно НЕ трогается до ответов
-- команды (возможен публичный anon-читатель статуса — см. досье).

alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema public
  revoke all on functions from anon, authenticated;
alter default privileges for role postgres in schema storage
  revoke all on tables from anon, authenticated;
alter default privileges for role postgres in schema storage
  revoke all on sequences from anon, authenticated;
alter default privileges for role postgres in schema storage
  revoke all on functions from anon, authenticated;

revoke execute on function public.creator_list_duet_presenters(jsonb)
  from anon;
revoke execute on function public.creator_register_duet_presenter(jsonb)
  from anon;
revoke execute on function public.creator_update_duet_presenter_layout(jsonb)
  from anon;
-- rls_auto_enable нёс грант через PUBLIC (=X/postgres в proacl) — revoke
-- только от anon его не снимает, has_function_privilege остаётся true.
revoke execute on function public.rls_auto_enable()
  from public, anon, authenticated;

alter function public.set_updated_at() set search_path = '';
alter function
  content_factory_private.reject_generation_provenance_manifest_mutation()
  set search_path = '';
alter function content_factory_private.guard_content_hypothesis_update()
  set search_path = '';
alter function
  content_factory_private.guard_content_hypothesis_version_update()
  set search_path = '';
alter function
  content_factory_private.reject_content_hypothesis_decision_mutation()
  set search_path = '';
alter function
  content_factory_private.reject_content_hypothesis_source_binding_mutation()
  set search_path = '';

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  leaked_defacl integer;
  fn_name text;
begin
  -- 1. В defacl грантора postgres для public/storage не осталось
  --    anon/authenticated.
  select count(*) into leaked_defacl
  from pg_catalog.pg_default_acl acl
  join pg_catalog.pg_roles grantor on grantor.oid = acl.defaclrole
  join pg_catalog.pg_namespace ns on ns.oid = acl.defaclnamespace
  where grantor.rolname = 'postgres'
    and ns.nspname in ('public', 'storage')
    and exists (
      select 1
      from aclexplode(acl.defaclacl) entry
      join pg_catalog.pg_roles grantee on grantee.oid = entry.grantee
      where grantee.rolname in ('anon', 'authenticated')
    );
  if leaked_defacl <> 0 then
    raise exception using message =
      'default_privileges_still_leak_' || leaked_defacl;
  end if;

  -- 2. Duet-RPC и rls_auto_enable для anon закрыты.
  if has_function_privilege(
       'anon', 'public.creator_list_duet_presenters(jsonb)', 'execute')
     or has_function_privilege(
       'anon', 'public.creator_register_duet_presenter(jsonb)', 'execute')
     or has_function_privilege(
       'anon', 'public.creator_update_duet_presenter_layout(jsonb)',
       'execute')
     or has_function_privilege(
       'anon', 'public.rls_auto_enable()', 'execute') then
    raise exception using message = 'anon_function_grants_remain';
  end if;
  -- Authenticated по-прежнему может звать duet-RPC (внутренние проверки —
  -- членство и роль — остаются рабочей авторизацией).
  if not has_function_privilege(
       'authenticated', 'public.creator_list_duet_presenters(jsonb)',
       'execute') then
    raise exception using message = 'duet_rpc_authenticated_lost';
  end if;

  -- 3. search_path закреплён у всех шести функций.
  for fn_name in
    select unnest(array[
      'public.set_updated_at()',
      'content_factory_private.reject_generation_provenance_manifest_mutation()',
      'content_factory_private.guard_content_hypothesis_update()',
      'content_factory_private.guard_content_hypothesis_version_update()',
      'content_factory_private.reject_content_hypothesis_decision_mutation()',
      'content_factory_private.reject_content_hypothesis_source_binding_mutation()'
    ])
  loop
    if position('search_path' in pg_get_functiondef(
         fn_name::regprocedure)) = 0 then
      raise exception using message =
        'search_path_not_pinned_' || fn_name;
    end if;
  end loop;
end;
$verify$;

commit;

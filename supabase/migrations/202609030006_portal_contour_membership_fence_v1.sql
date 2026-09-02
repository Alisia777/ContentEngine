begin;
-- 202609030006_portal_contour_membership_fence_v1
--
-- Забор вокруг живого portal_*-контура (второй продукт в той же базе:
-- задачи, цены, номенклатура, снапшоты WB). До этой миграции 11 таблиц
-- держали политики qual=true для ЛЮБОГО authenticated — а клиентские
-- учётки Контент-Завода получают ровно эту роль. Забор недеструктивен для
-- команды: заводится public.portal_members и сидируется ВСЕМИ текущими
-- неанонимными auth.users (40 на 03.09) — ни один живой пользователь
-- портала доступ не теряет, а будущие клиентские учётки в таблицу не
-- попадают. Точечные политики portal_design_workspace_* не трогаются (уже
-- правильные). ANON-политики portal_data_snapshots/portal_task_attachments
-- на этом шаге СОХРАНЯЮТСЯ: их снимет отдельная миграция после пересадки
-- писателя WB-снапшотов (ответы команды, sec-2/sec-5 мастер-плана).

create table if not exists public.portal_members (
  user_id uuid primary key references auth.users (id) on delete cascade,
  added_at timestamptz not null default now()
);

alter table public.portal_members enable row level security;
revoke all on public.portal_members from public, anon, authenticated;
grant select on public.portal_members to authenticated;
grant all on public.portal_members to service_role;

-- Своя строка видна себе: этого достаточно для EXISTS-проверок в политиках
-- остальных таблиц (подзапрос ищет только m.user_id = auth.uid()).
drop policy if exists portal_members_select_self on public.portal_members;
create policy portal_members_select_self on public.portal_members
  for select to authenticated
  using (user_id = auth.uid());

-- Сид: все текущие живые (неанонимные) учётки — команда обоих контуров.
insert into public.portal_members (user_id)
select u.id from auth.users u where not u.is_anonymous
on conflict (user_id) do nothing;

-- Замена открытых политик на членский забор: 11 таблиц, у каждой четыре
-- политики <table>_{select,insert,update,delete}_* → одна for all.
do $fence$
declare
  fence_table text;
  old_policy record;
begin
  for fence_table in
    select unnest(array[
      'portal_comments', 'portal_decisions', 'portal_masha_status_updates',
      'portal_novelty_cards', 'portal_novelty_launches',
      'portal_owner_assignments', 'portal_price_workbench_entries',
      'portal_price_workbench_history', 'portal_product_items',
      'portal_product_notebook', 'portal_tasks'
    ])
  loop
    for old_policy in
      select pol.policyname
      from pg_catalog.pg_policies pol
      where pol.schemaname = 'public'
        and pol.tablename = fence_table
        and pol.roles::text = '{authenticated}'
    loop
      execute format(
        'drop policy %I on public.%I', old_policy.policyname, fence_table
      );
    end loop;
    execute format(
      'create policy %I on public.%I for all to authenticated '
        || 'using (exists (select 1 from public.portal_members m '
        || 'where m.user_id = auth.uid())) '
        || 'with check (exists (select 1 from public.portal_members m '
        || 'where m.user_id = auth.uid()))',
      fence_table || '_members_fence', fence_table
    );
  end loop;
end;
$fence$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  open_count integer;
  member_count integer;
begin
  -- 1. На portal_* не осталось qual=true политик роли authenticated.
  select count(*) into open_count
  from pg_catalog.pg_policies pol
  where pol.schemaname = 'public'
    and pol.tablename like 'portal\_%'
    and pol.roles::text = '{authenticated}'
    and coalesce(pol.qual, '') = 'true';
  if open_count <> 0 then
    raise exception using message =
      'portal_fence_open_policies_remain_' || open_count;
  end if;

  -- 2. Сид не пуст: команда не отрезана.
  select count(*) into member_count from public.portal_members;
  if member_count < 10 then
    raise exception using message =
      'portal_members_seed_too_small_' || member_count;
  end if;

  -- 3. Anon-политики снапшотов/вложений сохранены (их снимает sec-5 после
  --    пересадки писателя WB-снапшотов).
  if not exists (
    select 1 from pg_catalog.pg_policies pol
    where pol.schemaname = 'public'
      and pol.tablename = 'portal_data_snapshots'
      and pol.policyname = 'portal_data_snapshots_select_public'
  ) or not exists (
    select 1 from pg_catalog.pg_policies pol
    where pol.schemaname = 'public'
      and pol.tablename = 'portal_task_attachments'
      and pol.policyname = 'portal_task_attachments_insert_public'
  ) then
    raise exception using message = 'portal_anon_policies_removed_too_early';
  end if;

  -- 4. Точечные политики дизайн-контура не задеты.
  if not exists (
    select 1 from pg_catalog.pg_policies pol
    where pol.schemaname = 'public'
      and pol.tablename = 'portal_design_workspaces'
      and pol.policyname = 'design_workspace_select_member'
  ) then
    raise exception using message = 'portal_design_policies_damaged';
  end if;
end;
$verify$;

commit;

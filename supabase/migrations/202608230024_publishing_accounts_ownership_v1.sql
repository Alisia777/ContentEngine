begin;
-- 202608230024_publishing_accounts_ownership_v1
--
-- Контур «аккаунты компании → сотрудникам → авторазмещение», фаза 0:
-- реестр владения (docs/PUBLISHING_ACCOUNTS_CONTOUR_2026-08-23.md, §4.1, §5.4).
--
-- Что появляется:
--   1. У managed_accounts — вид владения, хранитель, на что заведён аккаунт
--      (алиас почты и ссылка на корпоративный номер — НЕ секреты), внешний ID
--      у площадки, режим публикации и состояние подключения. Словарь площадок
--      закрывается CHECK-списком (раньше — свободная строка).
--   2. У placements — ссылка на аккаунт компании (managed_account_id):
--      destination_ref остаётся человекочитаемой копией handle.
--   3. RPC creator_admin_account_ownership — владелец/админ ставит поля
--      владения; creator_admin_snapshot отдаёт их в админку.
--   4. При окончательном увольнении (revoke_member) хранитель каждого
--      снятого аккаунта получает задачу «снять роль сотрудника на площадке»
--      (для personal_issued — ещё сменить пароль и перевыпустить 2FA).
--
-- Секреты здесь не появляются: токены подключений придут в фазе 2 в Vault под
-- именем, как у диспетчера фонового воркера.

-- 1. Поля владения -----------------------------------------------------------

alter table content_factory.managed_accounts
  add column if not exists ownership_kind text not null default 'personal_issued',
  add column if not exists custodian_profile_id uuid,
  add column if not exists registration_email_alias text,
  add column if not exists registration_phone_ref text,
  add column if not exists external_account_id text,
  add column if not exists posting_mode text not null default 'assisted',
  add column if not exists connection_status text not null default 'not_connected';

alter table content_factory.managed_accounts
  drop constraint if exists managed_accounts_ownership_kind_check,
  drop constraint if exists managed_accounts_posting_mode_check,
  drop constraint if exists managed_accounts_connection_status_check,
  drop constraint if exists managed_accounts_registration_email_alias_check,
  drop constraint if exists managed_accounts_registration_phone_ref_check,
  drop constraint if exists managed_accounts_external_account_id_check,
  drop constraint if exists managed_accounts_platform_vocabulary_check,
  drop constraint if exists managed_accounts_custodian_fk;

alter table content_factory.managed_accounts
  add constraint managed_accounts_ownership_kind_check check (
    ownership_kind in (
      'business_portfolio', 'brand_account', 'community', 'channel_bot',
      'marketplace', 'personal_issued'
    )
  ),
  add constraint managed_accounts_posting_mode_check check (
    posting_mode in ('api', 'assisted', 'disabled')
  ),
  add constraint managed_accounts_connection_status_check check (
    connection_status in ('not_connected', 'connected', 'expired', 'revoked', 'error')
  ),
  add constraint managed_accounts_registration_email_alias_check check (
    registration_email_alias is null
    or (
      length(registration_email_alias) between 3 and 120
      and registration_email_alias ~ '^[^[:space:]@]+@[^[:space:]@]+$'
    )
  ),
  add constraint managed_accounts_registration_phone_ref_check check (
    registration_phone_ref is null
    or length(btrim(registration_phone_ref)) between 2 and 40
  ),
  add constraint managed_accounts_external_account_id_check check (
    external_account_id is null
    or length(btrim(external_account_id)) between 1 and 120
  ),
  -- Единый словарь площадок: тот же набор, что у размещений, плюс кабинеты
  -- маркетплейсов и «другое» из админки. Свободная строка больше не принимается.
  add constraint managed_accounts_platform_vocabulary_check check (
    platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries',
      'ozon', 'rutube', 'other'
    )
  ),
  add constraint managed_accounts_custodian_fk
    foreign key (organization_id, custodian_profile_id)
    references content_factory.memberships (organization_id, profile_id);

comment on column content_factory.managed_accounts.ownership_kind is
  'Механизм владения на площадке: business_portfolio (Meta), brand_account (YouTube), community (VK), channel_bot (Telegram), marketplace, personal_issued (аккаунт-личность, выданный сотруднику; при уходе обязательна ротация пароля).';
comment on column content_factory.managed_accounts.custodian_profile_id is
  'Хранитель аккаунта (владелец/админ): восстановление доступа и роли сотрудников на площадке. Задачи офбординга уходят ему.';
comment on column content_factory.managed_accounts.registration_email_alias is
  'Корпоративный почтовый алиас, на который заведён аккаунт. Не секрет; секретов в этой таблице не бывает.';
comment on column content_factory.managed_accounts.registration_phone_ref is
  'Ссылка на корпоративный номер из пула (подпись/инвентарный код), не сам номер-секрет восстановления.';
comment on column content_factory.managed_accounts.external_account_id is
  'Идентификатор у площадки: ig-user-id, channelId, owner_id сообщества, chat_id канала.';
comment on column content_factory.managed_accounts.posting_mode is
  'api — публикует воркер токенами компании; assisted — ручное размещение с подсказкой; disabled — публикации закрыты.';
comment on column content_factory.managed_accounts.connection_status is
  'Состояние подключения к публикации; меняется только серверными функциями подключения (фаза 2).';

-- 2. Размещение знает аккаунт компании ----------------------------------------

alter table content_factory.placements
  add column if not exists managed_account_id uuid;

alter table content_factory.placements
  drop constraint if exists placements_managed_account_fk;
alter table content_factory.placements
  add constraint placements_managed_account_fk
    foreign key (organization_id, managed_account_id)
    references content_factory.managed_accounts (organization_id, id);

create index if not exists placements_managed_account_idx
  on content_factory.placements (organization_id, managed_account_id)
  where managed_account_id is not null;

comment on column content_factory.placements.managed_account_id is
  'Аккаунт компании, на котором размещается ролик. destination_ref остаётся человекочитаемой копией handle; для истории до 23.08.2026 — null.';

-- 3. Админка: чтение полей владения -------------------------------------------

do $ownership_snapshot$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '        ''assigned_at'', assignment.assigned_at' || chr(10) ||
    '      ) order by' || chr(10) ||
    '        case account.status when ''active'' then 0 else 1 end,';
  replacement constant text :=
    '        ''assigned_at'', assignment.assigned_at,' || chr(10) ||
    '        ''ownership_kind'', account.ownership_kind,' || chr(10) ||
    '        ''custodian_profile_id'', account.custodian_profile_id,' || chr(10) ||
    '        ''registration_email_alias'', account.registration_email_alias,' || chr(10) ||
    '        ''registration_phone_ref'', account.registration_phone_ref,' || chr(10) ||
    '        ''external_account_id'', account.external_account_id,' || chr(10) ||
    '        ''posting_mode'', account.posting_mode,' || chr(10) ||
    '        ''connection_status'', account.connection_status' || chr(10) ||
    '      ) order by' || chr(10) ||
    '        case account.status when ''active'' then 0 else 1 end,';
  hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_admin_snapshot(jsonb)'::regprocedure
  );
  if position('''ownership_kind'', account.ownership_kind' in definition_value) > 0 then
    return;  -- уже применено
  end if;
  hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if hits <> 1 then
    raise exception using message = 'ownership_snapshot_anchor_invalid:' || hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$ownership_snapshot$;

-- 4. Админка: запись полей владения -------------------------------------------

create or replace function public.creator_admin_account_ownership(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id uuid := auth.uid();
  actor_role text;
  organization_id uuid;
  idempotency_key text;
  canonical_payload jsonb;
  replay jsonb;
  account_id uuid;
  account_row content_factory.managed_accounts%rowtype;
  expected_updated_at timestamptz;
  ownership_kind_value text;
  custodian_value uuid;
  email_alias_value text;
  phone_ref_value text;
  external_id_value text;
  posting_mode_value text;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.require_admin_keys(
    p_payload,
    array[
      'organization_id', 'action', 'idempotency_key', 'account_id',
      'expected_updated_at', 'ownership_kind', 'custodian_profile_id',
      'registration_email_alias', 'registration_phone_ref',
      'external_account_id', 'posting_mode'
    ],
    array['action', 'idempotency_key', 'account_id', 'expected_updated_at']
  );
  if p_payload ->> 'action' <> 'set_ownership' then
    raise exception using errcode = '22023', message = 'admin_action_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.require_admin_actor(organization_id);
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  canonical_payload := p_payload || jsonb_build_object(
    'organization_id', organization_id
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_admin_set_ownership',
    idempotency_key,
    canonical_payload
  );
  if replay is not null then
    return replay;
  end if;

  account_id := content_factory_private.require_uuid(p_payload, 'account_id');
  begin
    expected_updated_at := content_factory_private.require_text(
      p_payload, 'expected_updated_at', 10, 64
    )::timestamptz;
  exception when others then
    raise exception using errcode = '22023', message = 'expected_updated_at_invalid';
  end;

  select account.* into account_row
  from content_factory.managed_accounts account
  where account.organization_id = organization_id
    and account.id = account_id
  for update;
  if account_row.id is null then
    raise exception using errcode = '42501', message = 'account_not_found';
  end if;
  if account_row.status <> 'active' then
    raise exception using errcode = '55000', message = 'account_not_active';
  end if;
  if account_row.updated_at <> expected_updated_at then
    raise exception using errcode = '55000', message = 'account_changed_concurrently';
  end if;

  ownership_kind_value := coalesce(
    content_factory_private.admin_optional_text(p_payload, 'ownership_kind', 3, 40),
    account_row.ownership_kind
  );
  if ownership_kind_value not in (
    'business_portfolio', 'brand_account', 'community', 'channel_bot',
    'marketplace', 'personal_issued'
  ) then
    raise exception using errcode = '22023', message = 'ownership_kind_invalid';
  end if;
  posting_mode_value := coalesce(
    content_factory_private.admin_optional_text(p_payload, 'posting_mode', 3, 20),
    account_row.posting_mode
  );
  if posting_mode_value not in ('api', 'assisted', 'disabled') then
    raise exception using errcode = '22023', message = 'posting_mode_invalid';
  end if;
  -- Режим api включается подключением (фаза 2), а не рукой: без живого
  -- подключения воркеру нечем публиковать, и режим врал бы оператору.
  if posting_mode_value = 'api' and account_row.connection_status <> 'connected' then
    raise exception using errcode = '55000', message = 'posting_mode_requires_connection';
  end if;

  email_alias_value := content_factory_private.admin_optional_text(
    p_payload, 'registration_email_alias', 3, 120
  );
  if email_alias_value is not null
     and email_alias_value !~ '^[^[:space:]@]+@[^[:space:]@]+$' then
    raise exception using errcode = '22023', message = 'registration_email_alias_invalid';
  end if;
  phone_ref_value := content_factory_private.admin_optional_text(
    p_payload, 'registration_phone_ref', 2, 40
  );
  external_id_value := content_factory_private.admin_optional_text(
    p_payload, 'external_account_id', 1, 120
  );

  if p_payload ? 'custodian_profile_id'
     and p_payload -> 'custodian_profile_id' <> 'null'::jsonb then
    custodian_value := content_factory_private.require_uuid(p_payload, 'custodian_profile_id');
    if not exists (
      select 1
      from content_factory.memberships member
      where member.organization_id = organization_id
        and member.profile_id = custodian_value
        and member.status = 'active'
        and member.role in ('owner', 'admin', 'producer')
    ) then
      raise exception using errcode = '55000', message = 'custodian_not_eligible';
    end if;
  elsif p_payload ? 'custodian_profile_id' then
    custodian_value := null;
  else
    custodian_value := account_row.custodian_profile_id;
  end if;

  update content_factory.managed_accounts account
  set
    ownership_kind = ownership_kind_value,
    custodian_profile_id = custodian_value,
    registration_email_alias = case
      when p_payload ? 'registration_email_alias' then email_alias_value
      else account.registration_email_alias end,
    registration_phone_ref = case
      when p_payload ? 'registration_phone_ref' then phone_ref_value
      else account.registration_phone_ref end,
    external_account_id = case
      when p_payload ? 'external_account_id' then external_id_value
      else account.external_account_id end,
    posting_mode = posting_mode_value,
    updated_at = now()
  where account.organization_id = organization_id
    and account.id = account_id
  returning * into account_row;

  result := jsonb_build_object(
    'ok', true,
    'account', jsonb_build_object(
      'id', account_row.id,
      'platform', account_row.platform,
      'label', account_row.label,
      'handle', account_row.handle,
      'ownership_kind', account_row.ownership_kind,
      'custodian_profile_id', account_row.custodian_profile_id,
      'registration_email_alias', account_row.registration_email_alias,
      'registration_phone_ref', account_row.registration_phone_ref,
      'external_account_id', account_row.external_account_id,
      'posting_mode', account_row.posting_mode,
      'connection_status', account_row.connection_status,
      'updated_at', account_row.updated_at
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    actor_id,
    'admin_managed_account_ownership_set',
    'managed_account',
    account_id::text,
    jsonb_build_object(
      'ownership_kind', account_row.ownership_kind,
      'custodian_profile_id', account_row.custodian_profile_id,
      'posting_mode', account_row.posting_mode,
      'actor_role', actor_role
    ),
    'admin:set_ownership:' || content_factory_private.json_hash(
      jsonb_build_object('idempotency_key', idempotency_key)
    ),
    'server_rpc'
  );

  return content_factory_private.finish_command(
    organization_id,
    actor_id,
    'creator_admin_set_ownership',
    idempotency_key,
    canonical_payload,
    result
  );
end;
$$;

revoke all on function public.creator_admin_account_ownership(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_admin_account_ownership(jsonb)
  to authenticated, service_role;

-- 5. Увольнение: хранителю — задача снять роль на площадке ---------------------

do $offboarding_tasks$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '        get diagnostics account_assignments_revoked_count = row_count;' || chr(10);
  replacement constant text :=
    '        get diagnostics account_assignments_revoked_count = row_count;' || chr(10) ||
    '        insert into content_factory.creator_tasks (' || chr(10) ||
    '          organization_id, assignee_id, created_by, task_type, title,' || chr(10) ||
    '          instructions, status, priority, payout_minor, result, idempotency_key' || chr(10) ||
    '        )' || chr(10) ||
    '        select' || chr(10) ||
    '          organization_id,' || chr(10) ||
    '          case when exists (' || chr(10) ||
    '            select 1 from content_factory.memberships custodian' || chr(10) ||
    '            where custodian.organization_id = organization_id' || chr(10) ||
    '              and custodian.profile_id = account.custodian_profile_id' || chr(10) ||
    '              and custodian.status = ''active''' || chr(10) ||
    '          ) then account.custodian_profile_id else actor_id end,' || chr(10) ||
    '          actor_id,' || chr(10) ||
    '          ''general'',' || chr(10) ||
    '          left(''Снять роль сотрудника на площадке: '' || account.platform || '' · ''' || chr(10) ||
    '            || coalesce(account.handle, account.label), 240),' || chr(10) ||
    '          case when account.ownership_kind = ''personal_issued''' || chr(10) ||
    '            then ''Аккаунт заводился как личный: смените пароль и перевыпустите 2FA, затем снимите роль сотрудника на площадке. Публикации через портал не останавливаются — токены у компании.''' || chr(10) ||
    '            else ''Снимите роль сотрудника в организационной сущности площадки (Portfolio / Brand-аккаунт / сообщество / админы канала). Публикации через портал не останавливаются — токены у компании.'' end,' || chr(10) ||
    '          ''todo'', 2, 0,' || chr(10) ||
    '          jsonb_build_object(' || chr(10) ||
    '            ''kind'', ''publishing_account_offboarding'',' || chr(10) ||
    '            ''account_id'', account.id,' || chr(10) ||
    '            ''platform'', account.platform,' || chr(10) ||
    '            ''ownership_kind'', account.ownership_kind,' || chr(10) ||
    '            ''revoked_profile_id'', target_profile_id' || chr(10) ||
    '          ),' || chr(10) ||
    '          ''account-offboarding:'' || account.id::text || '':'' || target_profile_id::text' || chr(10) ||
    '            || '':'' || to_char(now(), ''YYYYMMDDHH24MISS'')' || chr(10) ||
    '        from content_factory.member_account_assignments assignment' || chr(10) ||
    '        join content_factory.managed_accounts account' || chr(10) ||
    '          on account.organization_id = assignment.organization_id' || chr(10) ||
    '         and account.id = assignment.account_id' || chr(10) ||
    '        where assignment.organization_id = organization_id' || chr(10) ||
    '          and assignment.profile_id = target_profile_id' || chr(10) ||
    '          and assignment.status = ''revoked''' || chr(10) ||
    '          and assignment.revoked_by = actor_id' || chr(10) ||
    '          and assignment.revoked_at = now()' || chr(10) ||
    '          and account.status = ''active'';' || chr(10);
  hits integer;
begin
  definition_value := pg_get_functiondef(
    'public.creator_admin_mutate(jsonb)'::regprocedure
  );
  if position('''publishing_account_offboarding''' in definition_value) > 0 then
    return;  -- уже применено
  end if;
  hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if hits <> 1 then
    raise exception using message = 'offboarding_tasks_anchor_invalid:' || hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$offboarding_tasks$;

-- 6. Проверка ----------------------------------------------------------------

do $ownership_verify$
begin
  if position('''ownership_kind'', account.ownership_kind' in pg_get_functiondef(
       'public.creator_admin_snapshot(jsonb)'::regprocedure
     )) = 0 then
    raise exception using message = 'ownership_snapshot_not_applied';
  end if;
  if position('''publishing_account_offboarding''' in pg_get_functiondef(
       'public.creator_admin_mutate(jsonb)'::regprocedure
     )) = 0 then
    raise exception using message = 'offboarding_tasks_not_applied';
  end if;
  if not exists (
    select 1
    from pg_constraint
    where conname = 'placements_managed_account_fk'
  ) then
    raise exception using message = 'placements_managed_account_fk_missing';
  end if;
end;
$ownership_verify$;

commit;

begin;
-- 202608260009_content_hypotheses_v1
--
-- Контур №3 ТЗ (раздел 5), хребет данных: гипотеза как проверяемое
-- утверждение «Если X, то метрика Y изменится, потому что Z».
-- content_hypotheses — identity с жизненным циклом и итогом; версии —
-- append-only формулировки со снапшотом товара и canonical hash (после
-- создания меняется только статус утверждения); решения — только
-- человеческие, append-only, с причиной; итог identity обновляет триггер
-- решения. Никакой RPC не ставит confirmed автоматически. Привязка к
-- запускам уже ждёт в generation_provenance_manifests.hypothesis_id.

create table if not exists content_factory.content_hypotheses (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  code text not null check (code ~ '^H-[0-9]{3,6}$'),
  title text not null check (length(btrim(title)) between 2 and 200),
  owner_profile_id uuid,
  lifecycle_status text not null default 'draft' check (lifecycle_status in (
    'draft', 'collecting_evidence', 'preparing', 'ready_for_test',
    'testing', 'awaiting_mature_metrics', 'completed', 'archived'
  )),
  outcome text not null default 'untested' check (outcome in (
    'untested', 'confirmed', 'disproved', 'inconclusive'
  )),
  created_by uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint content_hypotheses_code_uq unique (organization_id, project_id, code),
  constraint content_hypotheses_org_id_uq unique (organization_id, id)
);

alter table content_factory.content_hypotheses enable row level security;
revoke all on content_factory.content_hypotheses
  from public, anon, authenticated;
grant all on content_factory.content_hypotheses to service_role;

-- Identity мутируема узко: жизненный цикл, итог, ответственный. Код,
-- проект и авторство после создания не переписываются.
create or replace function content_factory_private
  .guard_content_hypothesis_update()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000',
      message = 'content_hypothesis_delete_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.project_id <> old.project_id
     or new.code <> old.code
     or new.created_by <> old.created_by
     or new.created_at <> old.created_at then
    raise exception using errcode = '55000',
      message = 'content_hypothesis_identity_immutable';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists content_hypotheses_guard
  on content_factory.content_hypotheses;
create trigger content_hypotheses_guard
  before update or delete on content_factory.content_hypotheses
  for each row execute function
    content_factory_private.guard_content_hypothesis_update();

create table if not exists content_factory.content_hypothesis_versions (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  hypothesis_id uuid not null,
  version integer not null check (version between 1 and 100000),
  statement text not null check (length(btrim(statement)) between 20 and 2000),
  product_id uuid,
  product_sku_snapshot text,
  product_title_snapshot text,
  platform text check (platform is null or platform in (
    'wildberries', 'instagram', 'youtube', 'tiktok', 'vk', 'telegram', 'other'
  )),
  metric text not null check (metric in (
    'ctr', 'click_to_order', 'view_to_order', 'revenue_per_mille',
    'views', 'orders'
  )),
  baseline_value numeric,
  baseline_note text,
  target_value numeric,
  expected_change text,
  success_criteria text,
  rationale text,
  test_window_days integer
    check (test_window_days is null or test_window_days between 1 and 90),
  status text not null default 'draft' check (status in (
    'draft', 'approved', 'superseded', 'rejected'
  )),
  author uuid not null,
  created_at timestamptz not null default now(),
  approved_by uuid,
  approved_at timestamptz,
  superseded_at timestamptz,
  version_hash text not null check (version_hash ~ '^[0-9a-f]{64}$'),
  constraint content_hypothesis_versions_hash_self check (
    version_hash = content_factory_private.json_hash(jsonb_build_object(
      'version', 'content-hypothesis-version-v1',
      'hypothesis_id', hypothesis_id,
      'ordinal', version,
      'statement', statement,
      'product_id', product_id,
      'platform', platform,
      'metric', metric,
      'baseline_value', baseline_value,
      'target_value', target_value
    ))
  ),
  constraint content_hypothesis_versions_uq
    unique (organization_id, hypothesis_id, version),
  constraint content_hypothesis_versions_org_id_uq
    unique (organization_id, id),
  constraint content_hypothesis_versions_hypothesis_fk
    foreign key (organization_id, hypothesis_id)
    references content_factory.content_hypotheses (organization_id, id)
);

create unique index if not exists content_hypothesis_versions_one_approved
  on content_factory.content_hypothesis_versions (organization_id, hypothesis_id)
  where status = 'approved';

alter table content_factory.content_hypothesis_versions
  enable row level security;
revoke all on content_factory.content_hypothesis_versions
  from public, anon, authenticated;
grant all on content_factory.content_hypothesis_versions to service_role;

-- Формулировка append-only: после записи меняются только статусные поля.
create or replace function content_factory_private
  .guard_content_hypothesis_version_update()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000',
      message = 'content_hypothesis_version_delete_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.hypothesis_id <> old.hypothesis_id
     or new.version <> old.version
     or new.statement <> old.statement
     or new.product_id is distinct from old.product_id
     or new.product_sku_snapshot is distinct from old.product_sku_snapshot
     or new.product_title_snapshot is distinct from old.product_title_snapshot
     or new.platform is distinct from old.platform
     or new.metric <> old.metric
     or new.baseline_value is distinct from old.baseline_value
     or new.baseline_note is distinct from old.baseline_note
     or new.target_value is distinct from old.target_value
     or new.expected_change is distinct from old.expected_change
     or new.success_criteria is distinct from old.success_criteria
     or new.rationale is distinct from old.rationale
     or new.test_window_days is distinct from old.test_window_days
     or new.author <> old.author
     or new.created_at <> old.created_at
     or new.version_hash <> old.version_hash then
    raise exception using errcode = '55000',
      message = 'content_hypothesis_version_append_only';
  end if;
  return new;
end;
$$;

drop trigger if exists content_hypothesis_versions_guard
  on content_factory.content_hypothesis_versions;
create trigger content_hypothesis_versions_guard
  before update or delete
  on content_factory.content_hypothesis_versions
  for each row execute function
    content_factory_private.guard_content_hypothesis_version_update();

create table if not exists content_factory.content_hypothesis_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  hypothesis_id uuid not null,
  hypothesis_version_id uuid,
  action text not null check (action in (
    'confirm', 'disprove', 'inconclusive', 'rework', 'archive'
  )),
  reason text not null check (length(btrim(reason)) between 10 and 2000),
  decided_by uuid not null,
  decided_at timestamptz not null default now(),
  decision_hash text not null check (decision_hash ~ '^[0-9a-f]{64}$'),
  constraint content_hypothesis_decisions_hash_self check (
    decision_hash = content_factory_private.json_hash(jsonb_build_object(
      'version', 'content-hypothesis-decision-v1',
      'hypothesis_id', hypothesis_id,
      'hypothesis_version_id', hypothesis_version_id,
      'action', action,
      'reason', reason,
      'decided_by', decided_by
    ))
  ),
  constraint content_hypothesis_decisions_hypothesis_fk
    foreign key (organization_id, hypothesis_id)
    references content_factory.content_hypotheses (organization_id, id),
  constraint content_hypothesis_decisions_version_fk
    foreign key (organization_id, hypothesis_version_id)
    references content_factory.content_hypothesis_versions (organization_id, id)
);

alter table content_factory.content_hypothesis_decisions
  enable row level security;
revoke all on content_factory.content_hypothesis_decisions
  from public, anon, authenticated;
grant all on content_factory.content_hypothesis_decisions to service_role;

create or replace function content_factory_private
  .reject_content_hypothesis_decision_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception using errcode = '55000',
    message = 'content_hypothesis_decision_append_only';
end;
$$;

drop trigger if exists content_hypothesis_decisions_append_only
  on content_factory.content_hypothesis_decisions;
create trigger content_hypothesis_decisions_append_only
  before update or delete
  on content_factory.content_hypothesis_decisions
  for each row execute function
    content_factory_private.reject_content_hypothesis_decision_mutation();

-- Итог identity выводится ТОЛЬКО из человеческого решения.
create or replace function content_factory_private
  .apply_content_hypothesis_decision()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
begin
  update content_factory.content_hypotheses h
  set outcome = case new.action
      when 'confirm' then 'confirmed'
      when 'disprove' then 'disproved'
      when 'inconclusive' then 'inconclusive'
      else h.outcome
    end,
    lifecycle_status = case new.action
      when 'confirm' then 'completed'
      when 'disprove' then 'completed'
      when 'inconclusive' then 'completed'
      when 'rework' then 'preparing'
      when 'archive' then 'archived'
      else h.lifecycle_status
    end
  where h.organization_id = new.organization_id
    and h.id = new.hypothesis_id;
  return new;
end;
$$;

drop trigger if exists content_hypothesis_decisions_apply
  on content_factory.content_hypothesis_decisions;
create trigger content_hypothesis_decisions_apply
  after insert on content_factory.content_hypothesis_decisions
  for each row execute function
    content_factory_private.apply_content_hypothesis_decision();

commit;

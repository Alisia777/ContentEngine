begin;
-- 202608260007_generation_provenance_manifest_v1
--
-- Манифест происхождения (контур №2 ТЗ, раздел 4.9): append-only снимок
-- «что именно поехало в генерацию», создаваемый в момент bind действующего
-- контура — надстройкой-триггером на финальную запись bind'а стратегии
-- (generation_job_strategy_snapshots), без переписывания prepare/bind.
-- Содержит точные FK и снапшоты: продукт, версия ТЗ с prompt_hash, материалы
-- с sha256, движок. Canonical hash самопроверяется CHECK'ом; повторная
-- запись того же наряда с тем же payload — no-op, с другим — отказ;
-- generated-результат не может притвориться исходником товара (отказ bind).
-- Гипотезы появятся контуром №3: колонки заведены, пока null. Манифест не
-- денежный ledger: деньги остаются в generation_spend_ledger.

create table if not exists content_factory.generation_provenance_manifests (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  batch_id uuid,
  generation_job_id uuid not null,
  product_id uuid,
  hypothesis_id uuid,
  hypothesis_version_id uuid,
  payload jsonb not null,
  manifest_hash text not null check (manifest_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null
    check (length(idempotency_key) between 8 and 180),
  bound_by uuid,
  created_at timestamptz not null default now(),
  constraint generation_provenance_manifests_payload_shape check (
    jsonb_typeof(payload) = 'object'
    and payload - array[
      'version', 'organization_id', 'project_id', 'batch_id',
      'generation_job_id', 'hypothesis_id', 'hypothesis_version_id',
      'product', 'brief', 'assets', 'execution'
    ]::text[] = '{}'::jsonb
    and payload ->> 'version' = 'generation-provenance-v1'
    and jsonb_typeof(payload -> 'assets') = 'array'
    and length(payload::text) <= 65536
  ),
  constraint generation_provenance_manifests_hash_self check (
    manifest_hash = content_factory_private.json_hash(payload)
  ),
  constraint generation_provenance_manifests_job_uq
    unique (organization_id, generation_job_id),
  constraint generation_provenance_manifests_idem_uq
    unique (organization_id, idempotency_key),
  constraint generation_provenance_manifests_job_fk
    foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs (organization_id, id)
);

alter table content_factory.generation_provenance_manifests
  enable row level security;
revoke all on content_factory.generation_provenance_manifests
  from public, anon, authenticated;
grant all on content_factory.generation_provenance_manifests to service_role;

create or replace function content_factory_private
  .reject_generation_provenance_manifest_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception using errcode = '55000',
    message = 'generation_provenance_manifest_append_only';
end;
$$;

drop trigger if exists generation_provenance_manifests_append_only
  on content_factory.generation_provenance_manifests;
create trigger generation_provenance_manifests_append_only
  before update or delete
  on content_factory.generation_provenance_manifests
  for each row execute function
    content_factory_private.reject_generation_provenance_manifest_mutation();

-- Автозапись в момент bind: AFTER INSERT на снапшот стратегии наряда — это
-- финальная запись bind'а, все материалы и spec-версия уже в базе в той же
-- транзакции. RAISE здесь откатывает bind целиком — это осознанная линия
-- обороны, а не побочный эффект.
create or replace function content_factory_private
  .record_generation_provenance_manifest()
returns trigger
language plpgsql
security definer
set search_path to ''
as $$
declare
  job_row content_factory.generation_jobs%rowtype;
  product_row content_factory.products%rowtype;
  assets_value jsonb;
  forgery_count integer;
  payload_value jsonb;
  hash_value text;
  existing_hash text;
begin
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.id = new.generation_job_id;
  if job_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'generation_provenance_job_missing';
  end if;

  select product.* into product_row
  from content_factory.products product
  where product.organization_id = new.organization_id
    and product.id = job_row.product_id;

  -- Сгенерированный файл не может числиться исходником товара: подделка
  -- происхождения ломает всю доказуемость паспорта.
  select count(*) into forgery_count
  from content_factory.generation_spec_strategy_assets asset
  join content_factory.media_objects media
    on media.organization_id = asset.organization_id
    and media.id = asset.media_object_id
  where asset.organization_id = new.organization_id
    and asset.binding_id = new.spec_strategy_binding_id
    and asset.role in (
      'product_primary', 'product_reference', 'original_product'
    )
    and media.artifact_class = 'generated_output';
  if forgery_count > 0 then
    raise exception using errcode = '23514',
      message = 'generation_provenance_source_forgery';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
      'role', asset.role,
      'ordinal', asset.ordinal,
      'media_id', asset.media_object_id,
      'sha256', asset.media_sha256_snapshot,
      'direct_provider_input', true
    ) order by asset.ordinal), '[]'::jsonb)
    into assets_value
  from content_factory.generation_spec_strategy_assets asset
  where asset.organization_id = new.organization_id
    and asset.binding_id = new.spec_strategy_binding_id;

  payload_value := jsonb_build_object(
    'version', 'generation-provenance-v1',
    'organization_id', new.organization_id,
    'project_id', new.project_id,
    'batch_id', new.batch_id,
    'generation_job_id', new.generation_job_id,
    'hypothesis_id', null,
    'hypothesis_version_id', null,
    'product', case
      when product_row.id is null then null
      else jsonb_build_object(
        'product_id', product_row.id,
        'sku_snapshot', product_row.sku,
        'title_snapshot', product_row.title
      )
    end,
    'brief', jsonb_build_object(
      'spec_id', new.spec_id,
      'spec_version', new.spec_version,
      'spec_hash', new.spec_hash,
      'prompt_hash',
        new.strategy_snapshot -> 'strategy' -> 'spec' ->> 'prompt_hash'
    ),
    'assets', assets_value,
    'execution', jsonb_build_object(
      'strategy_id', new.strategy_id,
      'provider', job_row.provider,
      'model_key', job_row.input ->> 'model',
      'estimated_cost_minor', job_row.estimated_cost_minor,
      'source_basis', new.source_basis,
      'strategy_snapshot_hash', new.strategy_snapshot_hash
    )
  );
  hash_value := content_factory_private.json_hash(payload_value);

  insert into content_factory.generation_provenance_manifests (
    organization_id, project_id, batch_id, generation_job_id, product_id,
    payload, manifest_hash, idempotency_key, bound_by
  ) values (
    new.organization_id, new.project_id, new.batch_id,
    new.generation_job_id, job_row.product_id,
    payload_value, hash_value,
    'generation-provenance:' || new.generation_job_id::text, new.bound_by
  )
  on conflict (organization_id, generation_job_id) do nothing;
  if not found then
    select manifest.manifest_hash into existing_hash
    from content_factory.generation_provenance_manifests manifest
    where manifest.organization_id = new.organization_id
      and manifest.generation_job_id = new.generation_job_id;
    if existing_hash is distinct from hash_value then
      raise exception using errcode = '23505',
        message = 'generation_provenance_idempotency_conflict';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists generation_job_strategy_snapshots_provenance
  on content_factory.generation_job_strategy_snapshots;
create trigger generation_job_strategy_snapshots_provenance
  after insert
  on content_factory.generation_job_strategy_snapshots
  for each row execute function
    content_factory_private.record_generation_provenance_manifest();

commit;

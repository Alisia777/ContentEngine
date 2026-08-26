begin;
-- 202608260011_hypothesis_launch_binding_v1
--
-- Замыкание звена «гипотеза → запуск» без касания платного контура:
-- оператор выбирает утверждённую гипотезу в форме генерации, выбор хранится
-- как «активная гипотеза оператора в проекте», а триггер манифеста
-- происхождения в момент bind подхватывает выбор ТОГО, кто запускал
-- (bound_by), и вписывает точную версию гипотезы в манифест. Паспорт и срез
-- гипотезы заполняются сами. Выбор необязателен: запуск без гипотезы легален.

create table if not exists content_factory.content_hypothesis_operator_selections (
  organization_id uuid not null,
  project_id uuid not null,
  profile_id uuid not null,
  hypothesis_id uuid not null,
  hypothesis_version_id uuid not null,
  selected_at timestamptz not null default now(),
  constraint content_hypothesis_operator_selections_pk
    primary key (organization_id, project_id, profile_id),
  constraint content_hypothesis_operator_selections_hypothesis_fk
    foreign key (organization_id, hypothesis_id)
    references content_factory.content_hypotheses (organization_id, id),
  constraint content_hypothesis_operator_selections_version_fk
    foreign key (organization_id, hypothesis_version_id)
    references content_factory.content_hypothesis_versions (organization_id, id)
);

alter table content_factory.content_hypothesis_operator_selections
  enable row level security;
revoke all on content_factory.content_hypothesis_operator_selections
  from public, anon, authenticated;
grant all on content_factory.content_hypothesis_operator_selections
  to service_role;

-- Выбор/сброс активной гипотезы оператора. Принимается только утверждённая
-- версия гипотезы этого же проекта.
create or replace function public.creator_select_content_hypothesis(
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
  project_id_value uuid;
  hypothesis_row content_factory.content_hypotheses%rowtype;
  approved_version_id uuid;
  approved_version integer;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );

  if not (p_payload ? 'hypothesis_id')
     or nullif(btrim(coalesce(p_payload ->> 'hypothesis_id', '')), '') is null
  then
    delete from content_factory.content_hypothesis_operator_selections s
    where s.organization_id = organization_id
      and s.project_id = project_id_value
      and s.profile_id = user_id;
    return jsonb_build_object(
      'ok', true,
      'version', 'content-hypothesis-select-v1',
      'selected', null
    );
  end if;

  select h.* into hypothesis_row
  from content_factory.content_hypotheses h
  where h.organization_id = organization_id
    and h.project_id = project_id_value
    and h.id = content_factory_private.require_uuid(p_payload, 'hypothesis_id');
  if hypothesis_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_not_found';
  end if;

  select v.id, v.version into approved_version_id, approved_version
  from content_factory.content_hypothesis_versions v
  where v.organization_id = organization_id
    and v.hypothesis_id = hypothesis_row.id
    and v.status = 'approved';
  if approved_version_id is null then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_version_not_approved';
  end if;

  insert into content_factory.content_hypothesis_operator_selections (
    organization_id, project_id, profile_id,
    hypothesis_id, hypothesis_version_id
  ) values (
    organization_id, project_id_value, user_id,
    hypothesis_row.id, approved_version_id
  )
  on conflict on constraint content_hypothesis_operator_selections_pk do update set
    hypothesis_id = excluded.hypothesis_id,
    hypothesis_version_id = excluded.hypothesis_version_id,
    selected_at = now();

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-select-v1',
    'selected', jsonb_build_object(
      'hypothesis_id', hypothesis_row.id,
      'code', hypothesis_row.code,
      'hypothesis_version_id', approved_version_id,
      'hypothesis_version', approved_version
    )
  );
end;
$$;

revoke all on function public.creator_select_content_hypothesis(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_select_content_hypothesis(jsonb)
  to authenticated;

-- Список гипотез: карточка получает approved-версию (для выбора в формах),
-- а ответ — текущий выбор запрашивающего оператора.
do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_hypotheses(jsonb)'::regprocedure
  );
  if strpos(src, 'operator_selection') > 0 then
    raise exception 'hypotheses_list_selection_patch_already_applied';
  end if;
  if strpos(src, '''head'', (') = 0
     or strpos(src, '''hypotheses'', items_value,') = 0 then
    raise exception 'hypotheses_list_selection_patch_anchor_missing';
  end if;

  src := replace(src,
    '''head'', (',
    '''approved'', (
          select jsonb_build_object(
            ''id'', av.id,
            ''version'', av.version,
            ''statement'', av.statement
          )
          from content_factory.content_hypothesis_versions av
          where av.organization_id = h.organization_id
            and av.hypothesis_id = h.id
            and av.status = ''approved''
        ),
        ''head'', (');

  src := replace(src,
    '''hypotheses'', items_value,',
    '''hypotheses'', items_value,
    ''operator_selection'', (
      select jsonb_build_object(
        ''hypothesis_id'', s.hypothesis_id,
        ''hypothesis_version_id'', s.hypothesis_version_id
      )
      from content_factory.content_hypothesis_operator_selections s
      where s.organization_id = organization_id
        and s.project_id = project_id_value
        and s.profile_id = user_id
    ),');

  execute src;
end
$mig$;

-- Манифест происхождения подхватывает активную гипотезу запускающего.
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
  selection_row
    content_factory.content_hypothesis_operator_selections%rowtype;
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

  -- Активная гипотеза того, кто фиксировал bind. Гипотеза чужого проекта
  -- игнорируется по построению (выбор хранится в разрезе проекта).
  if new.bound_by is not null then
    select s.* into selection_row
    from content_factory.content_hypothesis_operator_selections s
    where s.organization_id = new.organization_id
      and s.project_id = new.project_id
      and s.profile_id = new.bound_by;
  end if;

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
    'hypothesis_id', selection_row.hypothesis_id,
    'hypothesis_version_id', selection_row.hypothesis_version_id,
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
    hypothesis_id, hypothesis_version_id,
    payload, manifest_hash, idempotency_key, bound_by
  ) values (
    new.organization_id, new.project_id, new.batch_id,
    new.generation_job_id, job_row.product_id,
    selection_row.hypothesis_id, selection_row.hypothesis_version_id,
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

notify pgrst, 'reload schema';

commit;

begin;
-- 202608260010_content_hypotheses_rpcs_v1
--
-- RPC папки «Гипотезы» (контур №3 v1): список, срез одной, сохранение
-- (новая гипотеза или новая версия формулировки), утверждение версии и
-- человеческое решение. Все — volatile (урок 202608260004), security
-- definer, ACL по членству и проекту; никаких провайдеров и денег.
-- Confirmed ставится только решением человека (creator_decide_*).

create or replace function public.creator_content_hypotheses(
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
  items_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );

  select coalesce(jsonb_agg(row_value order by code_value desc), '[]'::jsonb)
    into items_value
  from (
    select
      h.code as code_value,
      jsonb_build_object(
        'id', h.id,
        'code', h.code,
        'title', h.title,
        'lifecycle_status', h.lifecycle_status,
        'outcome', h.outcome,
        'created_at', h.created_at,
        'updated_at', h.updated_at,
        'versions_count', (
          select count(*) from content_factory.content_hypothesis_versions v
          where v.organization_id = h.organization_id
            and v.hypothesis_id = h.id
        ),
        'decisions_count', (
          select count(*) from content_factory.content_hypothesis_decisions d
          where d.organization_id = h.organization_id
            and d.hypothesis_id = h.id
        ),
        'launches_count', (
          select count(*) from content_factory.generation_provenance_manifests m
          where m.organization_id = h.organization_id
            and m.hypothesis_id = h.id
        ),
        'head', (
          select jsonb_build_object(
            'id', v.id,
            'version', v.version,
            'status', v.status,
            'statement', v.statement,
            'metric', v.metric,
            'platform', v.platform,
            'baseline_value', v.baseline_value,
            'target_value', v.target_value,
            'product_title', v.product_title_snapshot,
            'product_sku', v.product_sku_snapshot
          )
          from content_factory.content_hypothesis_versions v
          where v.organization_id = h.organization_id
            and v.hypothesis_id = h.id
          order by v.version desc
          limit 1
        )
      ) as row_value
    from content_factory.content_hypotheses h
    where h.organization_id = organization_id
      and h.project_id = project_id_value
    order by h.code desc
    limit 100
  ) rows;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypotheses-v1',
    'project_id', project_id_value,
    'hypotheses', items_value,
    'count', jsonb_array_length(items_value),
    'contract', jsonb_build_object(
      'read_only', true,
      'auto_confirmation', false
    )
  );
end;
$$;

revoke all on function public.creator_content_hypotheses(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_content_hypotheses(jsonb)
  to authenticated;

create or replace function public.creator_content_hypothesis(
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
  versions_value jsonb;
  decisions_value jsonb;
  launches_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project_access(
    organization_id, project_id_value, user_id
  );

  select h.* into hypothesis_row
  from content_factory.content_hypotheses h
  where h.organization_id = organization_id
    and h.project_id = project_id_value
    and h.id = content_factory_private.require_uuid(p_payload, 'hypothesis_id');
  if hypothesis_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_not_found';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
      'id', v.id,
      'version', v.version,
      'status', v.status,
      'statement', v.statement,
      'metric', v.metric,
      'platform', v.platform,
      'baseline_value', v.baseline_value,
      'baseline_note', v.baseline_note,
      'target_value', v.target_value,
      'expected_change', v.expected_change,
      'success_criteria', v.success_criteria,
      'rationale', v.rationale,
      'test_window_days', v.test_window_days,
      'product_id', v.product_id,
      'product_title', v.product_title_snapshot,
      'product_sku', v.product_sku_snapshot,
      'author', v.author,
      'created_at', v.created_at,
      'approved_by', v.approved_by,
      'approved_at', v.approved_at,
      'version_hash', v.version_hash
    ) order by v.version desc), '[]'::jsonb)
    into versions_value
  from (
    select vv.* from content_factory.content_hypothesis_versions vv
    where vv.organization_id = organization_id
      and vv.hypothesis_id = hypothesis_row.id
    order by vv.version desc
    limit 50
  ) v;

  select coalesce(jsonb_agg(jsonb_build_object(
      'id', d.id,
      'action', d.action,
      'reason', d.reason,
      'decided_by', d.decided_by,
      'decided_at', d.decided_at
    ) order by d.decided_at desc), '[]'::jsonb)
    into decisions_value
  from (
    select dd.* from content_factory.content_hypothesis_decisions dd
    where dd.organization_id = organization_id
      and dd.hypothesis_id = hypothesis_row.id
    order by dd.decided_at desc
    limit 30
  ) d;

  select coalesce(jsonb_agg(jsonb_build_object(
      'generation_job_id', m.generation_job_id,
      'manifest_hash', m.manifest_hash,
      'created_at', m.created_at
    ) order by m.created_at desc), '[]'::jsonb)
    into launches_value
  from (
    select mm.* from content_factory.generation_provenance_manifests mm
    where mm.organization_id = organization_id
      and mm.hypothesis_id = hypothesis_row.id
    order by mm.created_at desc
    limit 50
  ) m;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-v1',
    'hypothesis', jsonb_build_object(
      'id', hypothesis_row.id,
      'code', hypothesis_row.code,
      'title', hypothesis_row.title,
      'lifecycle_status', hypothesis_row.lifecycle_status,
      'outcome', hypothesis_row.outcome,
      'created_at', hypothesis_row.created_at
    ),
    'versions', versions_value,
    'decisions', decisions_value,
    'launches', launches_value,
    'contract', jsonb_build_object(
      'read_only', true,
      'auto_confirmation', false
    )
  );
end;
$$;

revoke all on function public.creator_content_hypothesis(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_content_hypothesis(jsonb)
  to authenticated;

create or replace function public.creator_save_content_hypothesis(
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
  product_row content_factory.products%rowtype;
  statement_value text;
  metric_value text;
  platform_value text;
  title_value text;
  next_version integer;
  next_code text;
  version_row content_factory.content_hypothesis_versions%rowtype;
  version_hash_value text;
  baseline_num numeric;
  target_num numeric;
  window_days integer;
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

  statement_value := btrim(coalesce(p_payload ->> 'statement', ''));
  if length(statement_value) < 20 or length(statement_value) > 2000 then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_statement_invalid';
  end if;
  metric_value := coalesce(p_payload ->> 'metric', '');
  if metric_value not in (
    'ctr', 'click_to_order', 'view_to_order', 'revenue_per_mille',
    'views', 'orders'
  ) then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_metric_invalid';
  end if;
  platform_value := nullif(btrim(coalesce(p_payload ->> 'platform', '')), '');
  if platform_value is not null and platform_value not in (
    'wildberries', 'instagram', 'youtube', 'tiktok', 'vk', 'telegram', 'other'
  ) then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_platform_invalid';
  end if;
  baseline_num := case
    when p_payload ? 'baseline_value'
      and jsonb_typeof(p_payload -> 'baseline_value') = 'number'
    then (p_payload ->> 'baseline_value')::numeric
    else null
  end;
  target_num := case
    when p_payload ? 'target_value'
      and jsonb_typeof(p_payload -> 'target_value') = 'number'
    then (p_payload ->> 'target_value')::numeric
    else null
  end;
  window_days := case
    when p_payload ? 'test_window_days'
      and jsonb_typeof(p_payload -> 'test_window_days') = 'number'
    then (p_payload ->> 'test_window_days')::integer
    else null
  end;

  if p_payload ? 'product_id'
     and nullif(btrim(coalesce(p_payload ->> 'product_id', '')), '') is not null
  then
    select product.* into product_row
    from content_factory.products product
    where product.organization_id = organization_id
      and product.id = content_factory_private.require_uuid(
        p_payload, 'product_id'
      );
    if product_row.id is null then
      raise exception using errcode = 'P0002',
        message = 'content_hypothesis_product_not_found';
    end if;
  end if;

  if p_payload ? 'hypothesis_id'
     and nullif(btrim(coalesce(p_payload ->> 'hypothesis_id', '')), '') is not null
  then
    select h.* into hypothesis_row
    from content_factory.content_hypotheses h
    where h.organization_id = organization_id
      and h.project_id = project_id_value
      and h.id = content_factory_private.require_uuid(
        p_payload, 'hypothesis_id'
      );
    if hypothesis_row.id is null then
      raise exception using errcode = 'P0002',
        message = 'content_hypothesis_not_found';
    end if;
  else
    title_value := btrim(coalesce(p_payload ->> 'title', ''));
    if length(title_value) < 2 or length(title_value) > 200 then
      raise exception using errcode = '22023',
        message = 'content_hypothesis_title_invalid';
    end if;
    select 'H-' || lpad(
      (coalesce(max(substring(h.code from 3)::integer), 0) + 1)::text, 3, '0'
    ) into next_code
    from content_factory.content_hypotheses h
    where h.organization_id = organization_id
      and h.project_id = project_id_value;
    insert into content_factory.content_hypotheses (
      organization_id, project_id, code, title, owner_profile_id, created_by
    ) values (
      organization_id, project_id_value, next_code, title_value,
      user_id, user_id
    ) returning * into hypothesis_row;
  end if;

  select coalesce(max(v.version), 0) + 1 into next_version
  from content_factory.content_hypothesis_versions v
  where v.organization_id = organization_id
    and v.hypothesis_id = hypothesis_row.id;

  -- Незаапрувленный черновик уступает место новой формулировке.
  update content_factory.content_hypothesis_versions v
  set status = 'superseded', superseded_at = now()
  where v.organization_id = organization_id
    and v.hypothesis_id = hypothesis_row.id
    and v.status = 'draft';

  version_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'content-hypothesis-version-v1',
    'hypothesis_id', hypothesis_row.id,
    'ordinal', next_version,
    'statement', statement_value,
    'product_id', product_row.id,
    'platform', platform_value,
    'metric', metric_value,
    'baseline_value', baseline_num,
    'target_value', target_num
  ));

  insert into content_factory.content_hypothesis_versions (
    organization_id, hypothesis_id, version, statement,
    product_id, product_sku_snapshot, product_title_snapshot,
    platform, metric, baseline_value, baseline_note, target_value,
    expected_change, success_criteria, rationale, test_window_days,
    author, version_hash
  ) values (
    organization_id, hypothesis_row.id, next_version, statement_value,
    product_row.id, product_row.sku, product_row.title,
    platform_value, metric_value, baseline_num,
    nullif(btrim(coalesce(p_payload ->> 'baseline_note', '')), ''),
    target_num,
    nullif(btrim(coalesce(p_payload ->> 'expected_change', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'success_criteria', '')), ''),
    nullif(btrim(coalesce(p_payload ->> 'rationale', '')), ''),
    window_days, user_id, version_hash_value
  ) returning * into version_row;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-save-v1',
    'hypothesis_id', hypothesis_row.id,
    'code', hypothesis_row.code,
    'hypothesis_version_id', version_row.id,
    'hypothesis_version', version_row.version,
    'status', version_row.status,
    'contract', jsonb_build_object(
      'auto_confirmation', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function public.creator_save_content_hypothesis(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_save_content_hypothesis(jsonb)
  to authenticated;

create or replace function public.creator_approve_content_hypothesis_version(
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
  version_row content_factory.content_hypothesis_versions%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );

  select v.* into version_row
  from content_factory.content_hypothesis_versions v
  where v.organization_id = organization_id
    and v.id = content_factory_private.require_uuid(
      p_payload, 'hypothesis_version_id'
    );
  if version_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_version_not_found';
  end if;
  if version_row.status <> 'draft' then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_version_not_draft';
  end if;

  update content_factory.content_hypothesis_versions v
  set status = 'superseded', superseded_at = now()
  where v.organization_id = organization_id
    and v.hypothesis_id = version_row.hypothesis_id
    and v.status = 'approved';

  update content_factory.content_hypothesis_versions v
  set status = 'approved', approved_by = user_id, approved_at = now()
  where v.organization_id = organization_id
    and v.id = version_row.id;

  update content_factory.content_hypotheses h
  set lifecycle_status = 'ready_for_test'
  where h.organization_id = organization_id
    and h.id = version_row.hypothesis_id
    and h.lifecycle_status in ('draft', 'collecting_evidence', 'preparing');

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-approve-v1',
    'hypothesis_id', version_row.hypothesis_id,
    'hypothesis_version_id', version_row.id,
    'status', 'approved'
  );
end;
$$;

revoke all on function public.creator_approve_content_hypothesis_version(jsonb)
  from public, anon, service_role;
grant execute on function
  public.creator_approve_content_hypothesis_version(jsonb) to authenticated;

create or replace function public.creator_decide_content_hypothesis(
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
  action_value text;
  reason_value text;
  version_id_value uuid;
  decision_row content_factory.content_hypothesis_decisions%rowtype;
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

  action_value := coalesce(p_payload ->> 'action', '');
  if action_value not in (
    'confirm', 'disprove', 'inconclusive', 'rework', 'archive'
  ) then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_action_invalid';
  end if;
  reason_value := btrim(coalesce(p_payload ->> 'reason', ''));
  if length(reason_value) < 10 or length(reason_value) > 2000 then
    raise exception using errcode = '22023',
      message = 'content_hypothesis_reason_invalid';
  end if;

  select v.id into version_id_value
  from content_factory.content_hypothesis_versions v
  where v.organization_id = organization_id
    and v.hypothesis_id = hypothesis_row.id
  order by (v.status = 'approved') desc, v.version desc
  limit 1;

  insert into content_factory.content_hypothesis_decisions (
    organization_id, hypothesis_id, hypothesis_version_id,
    action, reason, decided_by, decision_hash
  ) values (
    organization_id, hypothesis_row.id, version_id_value,
    action_value, reason_value, user_id,
    content_factory_private.json_hash(jsonb_build_object(
      'version', 'content-hypothesis-decision-v1',
      'hypothesis_id', hypothesis_row.id,
      'hypothesis_version_id', version_id_value,
      'action', action_value,
      'reason', reason_value,
      'decided_by', user_id
    ))
  ) returning * into decision_row;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-decision-v1',
    'hypothesis_id', hypothesis_row.id,
    'decision_id', decision_row.id,
    'action', decision_row.action,
    'contract', jsonb_build_object(
      'human_decision_recorded', true,
      'auto_confirmation', false
    )
  );
end;
$$;

revoke all on function public.creator_decide_content_hypothesis(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_decide_content_hypothesis(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;

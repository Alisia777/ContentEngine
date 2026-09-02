begin;
-- 202609030011_failed_spend_tile_fix_v1
--
-- Хотфикс обёртки 202609030002: в ней не было #variable_conflict
-- use_variable, и голое имя organization_id в WHERE стало ambiguous с
-- колонкой ledger.organization_id — creator_generation_spend_overview
-- падал 42702, экран «Общий бюджет» показывал «остаток временно не
-- получен». Урок verify-блока: текстовые пины не ловят runtime-ошибку —
-- здесь функция ВЫЗЫВАЕТСЯ по-настоящему под эмулированным JWT.

create or replace function public.creator_generation_spend_overview(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  overview_value jsonb;
  organization_id uuid;
  failed_day_minor bigint;
  failed_month_minor bigint;
  failed_all_minor bigint;
  committed_all_minor bigint;
begin
  overview_value := content_factory_private
    .creator_generation_spend_overview_pre_failed_spend_v1(p_payload);
  organization_id :=
    content_factory_private.require_uuid(
      overview_value,
      'organization_id'
    );

  select
    coalesce(sum(ledger.committed_delta_minor)
      filter (where ledger.budget_day = current_date), 0),
    coalesce(sum(ledger.committed_delta_minor)
      filter (where ledger.budget_month
        = date_trunc('month', now())::date), 0),
    coalesce(sum(ledger.committed_delta_minor), 0)
  into failed_day_minor, failed_month_minor, failed_all_minor
  from content_factory.generation_spend_ledger ledger
  join content_factory.generation_jobs job
    on job.id = ledger.generation_job_id
  where ledger.organization_id = organization_id
    and job.status = 'failed'
    and ledger.event_type in ('settled', 'refunded');

  select coalesce(sum(ledger.committed_delta_minor), 0)
  into committed_all_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id
    and ledger.event_type in ('settled', 'refunded');

  return overview_value || jsonb_build_object(
    'failed_spend', jsonb_build_object(
      'version', 'generation-failed-spend-v1',
      'day_minor', failed_day_minor,
      'month_minor', failed_month_minor,
      'all_time_minor', failed_all_minor,
      'committed_all_time_minor', committed_all_minor,
      'share_percent', case
        when committed_all_minor > 0
        then round(
          failed_all_minor::numeric * 100 / committed_all_minor, 1
        )
        else 0
      end
    )
  );
end;
$$;

revoke all on function public.creator_generation_spend_overview(jsonb)
  from public, anon;
grant execute on function public.creator_generation_spend_overview(jsonb)
  to authenticated;

-- ПРОВЕРКА ПОВЕДЕНИЕМ: настоящий вызов под эмулированным JWT владельца.
do $verify$
declare
  claims_value text;
  overview_value jsonb;
  owner_id uuid;
  organization_value uuid;
begin
  select membership.profile_id, membership.organization_id
  into owner_id, organization_value
  from content_factory.memberships membership
  where membership.role = 'owner' and membership.status = 'active'
  order by membership.created_at
  limit 1;
  if owner_id is null then
    raise exception using message = 'failed_spend_fix_no_owner_to_verify';
  end if;
  claims_value := current_setting('request.jwt.claims', true);
  perform set_config(
    'request.jwt.claims',
    json_build_object('sub', owner_id, 'role', 'authenticated')::text,
    true
  );
  overview_value := public.creator_generation_spend_overview(
    jsonb_build_object('organization_id', organization_value)
  );
  perform set_config(
    'request.jwt.claims', coalesce(claims_value, ''), true
  );
  if overview_value -> 'failed_spend' ->> 'version'
       is distinct from 'generation-failed-spend-v1'
     or (overview_value -> 'failed_spend' ->> 'all_time_minor') is null then
    raise exception using message = 'failed_spend_fix_broken';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

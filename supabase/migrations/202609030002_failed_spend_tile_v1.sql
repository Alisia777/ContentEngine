begin;
-- 202609030002_failed_spend_tile_v1
--
-- «Потрачено на брак»: 39% живых денег ($74.25 из $188.68 на 02.09) ушло на
-- упавшие генерации, а метрики этого на экране бюджета не было — управлять
-- главным экономическим рычагом модели «под ключ» (снижением брака) нечем.
-- Ledger браузеру недоступен (RLS deny), поэтому цифра едет внутри уже
-- membership-скоупленного creator_generation_spend_overview по обёрточному
-- паттерну 202607280004: старая функция уезжает в content_factory_private
-- под именем *_pre_failed_spend_v1, новая обёртка добавляет ключ
-- failed_spend. Нормализатор веба терпим к новым ключам.

alter function public.creator_generation_spend_overview(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_spend_overview(jsonb)
  rename to creator_generation_spend_overview_pre_failed_spend_v1;

revoke all on function
  content_factory_private
    .creator_generation_spend_overview_pre_failed_spend_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_generation_spend_overview(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
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

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'public.creator_generation_spend_overview(jsonb)'::regprocedure
  );
  if position('failed_spend' in definition_value) = 0
     or position('creator_generation_spend_overview_pre_failed_spend_v1'
       in definition_value) = 0 then
    raise exception using message = 'failed_spend_wrapper_missing';
  end if;
  if not exists (
    select 1 from pg_catalog.pg_proc proc
    join pg_catalog.pg_namespace ns on ns.oid = proc.pronamespace
    where ns.nspname = 'content_factory_private'
      and proc.proname
        = 'creator_generation_spend_overview_pre_failed_spend_v1'
  ) then
    raise exception using message = 'failed_spend_pre_function_missing';
  end if;
  if not has_function_privilege(
       'authenticated',
       'public.creator_generation_spend_overview(jsonb)', 'execute'
     ) then
    raise exception using message = 'failed_spend_overview_grant_missing';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

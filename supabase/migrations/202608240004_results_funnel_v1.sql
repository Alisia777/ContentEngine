begin;
-- 202608240004_results_funnel_v1
--
-- Владелица (24.08.2026): «не хватает главного экрана — статистика роликов по
-- воронке: создали → смотрим → размещаем → собираем статистику». Публикации и
-- их метрики в «Результатах» уже есть; не хватало головы воронки — сколько
-- роликов на каждом этапе прямо сейчас. Один лёгкий счётчик без второго
-- источника правды: этапы выводятся из тех же таблиц, которыми живут разделы
-- («Файлы» — lifecycle_stage, «Проверка» — черновики, «Мои работы» —
-- задачи 'placement', «Публикации» — placements).

create or replace function public.creator_results_funnel(
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
  actor_id uuid;
  organization_id uuid;
  project_id uuid;
  media_counts record;
  placement_counts record;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  actor_id := content_factory_private.current_profile_id();
  if p_payload - array['organization_id', 'project_id']::text[]
     <> '{}'::jsonb then
    raise exception using errcode = '22023',
      message = 'results_funnel_payload_invalid';
  end if;
  organization_id := content_factory_private.resolve_organization(p_payload);
  if not exists (
    select 1
    from content_factory.memberships member
    where member.organization_id = organization_id
      and member.profile_id = actor_id
      and member.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'membership_required';
  end if;
  project_id := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    organization_id, project_id
  );

  select
    count(*) filter (where media.status <> 'deleted') as generated_total,
    count(*) filter (
      where media.status <> 'deleted' and media.lifecycle_stage = 'drafts'
    ) as awaiting_review,
    count(*) filter (
      where media.status <> 'deleted' and media.lifecycle_stage = 'review'
    ) as in_review,
    count(*) filter (
      where media.status <> 'deleted' and media.lifecycle_stage = 'ready'
    ) as approved_ready,
    count(*) filter (
      where media.status <> 'deleted' and media.lifecycle_stage = 'published'
    ) as lifecycle_published,
    count(*) filter (
      where media.status = 'deleted' and media.metadata ? 'rejection'
    ) as rejected
  into media_counts
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.project_id = project_id
    and media.metadata ->> 'kind' = 'generated_video';

  select
    count(*) filter (where placement.status <> 'published')
      as placement_in_progress,
    count(*) filter (where placement.status = 'published') as published
  into placement_counts
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.project_id = project_id;

  return jsonb_build_object(
    'ok', true,
    'version', 'results-funnel-v1',
    'funnel', jsonb_build_object(
      'generated_total', media_counts.generated_total,
      'awaiting_review', media_counts.awaiting_review,
      'in_review', media_counts.in_review,
      'approved_ready', media_counts.approved_ready,
      'lifecycle_published', media_counts.lifecycle_published,
      'rejected', media_counts.rejected,
      'placement_in_progress', placement_counts.placement_in_progress,
      'published', placement_counts.published
    )
  );
end;
$$;

revoke all on function public.creator_results_funnel(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_results_funnel(jsonb)
  to authenticated, service_role;

comment on function public.creator_results_funnel(jsonb) is
  'Голова воронки «Результатов»: счётчики роликов по этапам (создано, черновики, на проверке, готово, в размещении, опубликовано, отвергнуто) из тех же таблиц, которыми живут разделы.';

notify pgrst, 'reload schema';

commit;

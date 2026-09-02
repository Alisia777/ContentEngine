begin;
-- 202609030017_confirm_placement_closes_publishing_job_v1
--
-- Мост очереди публикаций: подтверждение ручного поста (creator_confirm_
-- placement, второй человек вписывает final_url) раньше НЕ трогало
-- publishing_jobs — наряд навсегда висел в manual_required, и очередь
-- копила вечные хвосты. Патчится реализация
-- content_factory_private.creator_confirm_placement_pre_project_v47
-- (НЕ публичная обёртка) anchor-patch'ем по образцу 202608290003: после
-- записи благодарностей и ПЕРЕД emit_event наряд manual_required этого
-- размещения переводится в published с provider_post_id='manual:<id>' и
-- final_url из placements (published_proof_check требует оба поля —
-- гейт exists по final_url). Идемпотентно: published/failed/cancelled
-- не трогаются; событие 'published' пишется в publishing_job_events.

do $bridge$
declare
  source_text text;
  patched_text text;
  anchor_emit constant text := $ae$
  perform content_factory_private.emit_event(
$ae$;
  patch_emit constant text := $pe$
  -- Мост очереди публикаций: ручной пост подтверждён — незакрытый наряд
  -- manual_required этого размещения закрывается published. Гейт exists
  -- по final_url размещения соблюдает published_proof_check.
  update content_factory.publishing_jobs job
  set status = 'published',
      provider_post_id = coalesce(
        job.provider_post_id, 'manual:' || placement_id::text
      ),
      final_url = coalesce(
        (select p.final_url
         from content_factory.placements p
         where p.organization_id = organization_id_value
           and p.id = placement_id),
        job.final_url
      ),
      completed_at = now(),
      lease_token = null,
      leased_until = null,
      updated_at = now()
  where job.organization_id = organization_id_value
    and job.placement_id = placement_id
    and job.status = 'manual_required'
    and exists (
      select 1 from content_factory.placements p
      where p.organization_id = organization_id_value
        and p.id = placement_id
        and p.final_url is not null
    );
  insert into content_factory.publishing_job_events (
    organization_id, job_id, event, payload, actor, actor_profile_id
  )
  select
    job.organization_id, job.id, 'published',
    jsonb_build_object(
      'source', 'confirm_placement_bridge',
      'placement_id', placement_id,
      'final_url', job.final_url
    ),
    'creator', actor_id
  from content_factory.publishing_jobs job
  where job.organization_id = organization_id_value
    and job.placement_id = placement_id
    and job.status = 'published'
    and job.provider_post_id = 'manual:' || placement_id::text
    and job.completed_at > now() - interval '1 minute'
    and not exists (
      select 1 from content_factory.publishing_job_events event
      where event.job_id = job.id and event.event = 'published'
    );

  perform content_factory_private.emit_event(
$pe$;
begin
  source_text := pg_get_functiondef(
    'content_factory_private.creator_confirm_placement_pre_project_v47(jsonb)'::regprocedure
  );
  if position('confirm_placement_bridge' in source_text) > 0 then
    -- Повторный прогон обязан быть тихим.
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor_emit, ''))) /
     length(anchor_emit) <> 1 then
    raise exception using message = 'confirm_placement_emit_anchor_invalid';
  end if;
  patched_text := replace(source_text, anchor_emit, patch_emit);
  if patched_text = source_text then
    raise exception using message = 'confirm_placement_bridge_unchanged';
  end if;
  execute patched_text;
end;
$bridge$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  definition_value text;
begin
  definition_value := pg_get_functiondef(
    'content_factory_private.creator_confirm_placement_pre_project_v47(jsonb)'::regprocedure
  );
  if position('confirm_placement_bridge' in definition_value) = 0
     or position($m$'manual:' || placement_id::text$m$
       in definition_value) = 0
     or position($s$job.status = 'manual_required'$s$
       in definition_value) = 0 then
    raise exception using message = 'confirm_placement_bridge_missing';
  end if;
  -- Публичная обёртка не тронута: патч сидит в pre_project_v47.
  if position('confirm_placement_bridge' in pg_get_functiondef(
       'public.creator_confirm_placement(jsonb)'::regprocedure)) > 0 then
    raise exception using message =
      'confirm_placement_bridge_patched_wrong_function';
  end if;
end;
$verify$;

commit;

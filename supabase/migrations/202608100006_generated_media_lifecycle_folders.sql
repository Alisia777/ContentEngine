begin;

-- Generated artifacts start in Drafts (202608100002), then follow the actual
-- server-side workflow.  The lifecycle column is intentionally derived from
-- authoritative review / placement records rather than from browser state.

create or replace function
  content_factory_private.route_generated_media_review_lifecycle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  latest_review boolean;
begin
  if new.project_id is null then
    return new;
  end if;

  select not exists (
    select 1
    from content_factory.content_review_runs later_review
    where later_review.organization_id = new.organization_id
      and later_review.project_id = new.project_id
      and later_review.media_object_id = new.media_object_id
      and (later_review.created_at, later_review.id)
        > (new.created_at, new.id)
  ) into latest_review;

  if not latest_review then
    return new;
  end if;

  if new.status in ('queued', 'processing', 'completed') then
    update content_factory.media_objects media
    set lifecycle_stage = 'review'
    where media.organization_id = new.organization_id
      and media.project_id = new.project_id
      and media.id = new.media_object_id
      and media.artifact_class = 'generated_output'
      and media.status not in ('deleted', 'archived')
      -- A fresh review suspends both a draft and a previously-ready output.
      -- Published is terminal and is deliberately excluded.
      and media.lifecycle_stage in ('drafts', 'ready');
  elsif new.status in ('failed', 'cancelled') then
    update content_factory.media_objects media
    set lifecycle_stage = 'drafts'
    where media.organization_id = new.organization_id
      and media.project_id = new.project_id
      and media.id = new.media_object_id
      and media.artifact_class = 'generated_output'
      and media.status not in ('deleted', 'archived')
      and media.lifecycle_stage = 'review'
      and not exists (
        select 1
        from content_factory.content_review_decisions decision
        where decision.organization_id = new.organization_id
          and decision.review_id = new.id
      );
  end if;

  return new;
end;
$$;

revoke all on function
  content_factory_private.route_generated_media_review_lifecycle()
  from public, anon, authenticated;

drop trigger if exists zz_route_generated_media_review_lifecycle
  on content_factory.content_review_runs;
create trigger zz_route_generated_media_review_lifecycle
after insert or update of status on content_factory.content_review_runs
for each row execute function
  content_factory_private.route_generated_media_review_lifecycle();

create or replace function
  content_factory_private.route_generated_media_decision_lifecycle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  review_row content_factory.content_review_runs%rowtype;
begin
  select review.*
    into review_row
  from content_factory.content_review_runs review
  where review.organization_id = new.organization_id
    and review.id = new.review_id;

  if review_row.id is null or review_row.project_id is null then
    return new;
  end if;

  -- A late decision for an older review must not move a newer revision.
  if exists (
    select 1
    from content_factory.content_review_runs later_review
    where later_review.organization_id = review_row.organization_id
      and later_review.project_id = review_row.project_id
      and later_review.media_object_id = review_row.media_object_id
      and (later_review.created_at, later_review.id)
        > (review_row.created_at, review_row.id)
  ) then
    return new;
  end if;

  update content_factory.media_objects media
  set lifecycle_stage = case new.decision
    when 'approved' then 'ready'
    else 'drafts'
  end
  where media.organization_id = review_row.organization_id
    and media.project_id = review_row.project_id
    and media.id = review_row.media_object_id
    and media.artifact_class = 'generated_output'
    and media.status not in ('deleted', 'archived')
    -- Publication is terminal for folder routing.  A later stale review cannot
    -- silently pull already-published content back into the editing queue.
    and media.lifecycle_stage <> 'published';

  return new;
end;
$$;

revoke all on function
  content_factory_private.route_generated_media_decision_lifecycle()
  from public, anon, authenticated;

drop trigger if exists zz_route_generated_media_decision_lifecycle
  on content_factory.content_review_decisions;
create trigger zz_route_generated_media_decision_lifecycle
after insert on content_factory.content_review_decisions
for each row execute function
  content_factory_private.route_generated_media_decision_lifecycle();

create or replace function
  content_factory_private.route_published_placement_media_lifecycle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  output_media_id uuid;
begin
  if new.status <> 'published'
     or new.project_id is null
     or new.generation_job_id is null
     or (tg_op = 'UPDATE' and old.status is not distinct from new.status) then
    return new;
  end if;

  select case
    when coalesce(job.output ->> 'output_media_id', '') ~
      '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
      then (job.output ->> 'output_media_id')::uuid
    else null
  end
    into output_media_id
  from content_factory.generation_jobs job
  where job.organization_id = new.organization_id
    and job.project_id = new.project_id
    and job.id = new.generation_job_id;

  if output_media_id is null then
    return new;
  end if;

  update content_factory.media_objects media
  set lifecycle_stage = 'published'
  where media.organization_id = new.organization_id
    and media.project_id = new.project_id
    and media.id = output_media_id
    and media.artifact_class = 'generated_output'
    and media.status not in ('deleted', 'archived')
    and media.lifecycle_stage <> 'published';

  return new;
end;
$$;

revoke all on function
  content_factory_private.route_published_placement_media_lifecycle()
  from public, anon, authenticated;

drop trigger if exists zz_route_published_placement_media_lifecycle
  on content_factory.placements;
create trigger zz_route_published_placement_media_lifecycle
after insert or update of status on content_factory.placements
for each row execute function
  content_factory_private.route_published_placement_media_lifecycle();

-- During this one-time derivation, preserve explicit custom folders.  The
-- normal runtime trigger continues to move every genuine lifecycle transition.
create or replace function
  content_factory_private.sync_workspace_media_location_trigger()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  workflow_transition boolean := false;
begin
  if tg_op = 'UPDATE' then
    workflow_transition :=
      old.lifecycle_stage is distinct from new.lifecycle_stage;
    if not workflow_transition then
      return new;
    end if;
    if not pg_try_advisory_xact_lock(
      hashtext(new.organization_id::text),
      hashtext('workspace_structure')
    ) then
      raise exception using
        errcode = '40001',
        message = 'workspace_media_lifecycle_concurrent_move';
    end if;
  end if;

  perform content_factory_private.sync_workspace_media_system_location(
    new.organization_id,
    new.id,
    workflow_transition
      and coalesce(
        current_setting('contentengine.media_lifecycle_backfill', true),
        ''
      ) <> 'on'
  );
  return new;
end;
$$;

revoke all on function
  content_factory_private.sync_workspace_media_location_trigger()
  from public, anon, authenticated;

do $$
declare
  previous_backfill_setting text :=
    current_setting('contentengine.media_lifecycle_backfill', true);
  media_row record;
begin
  perform set_config(
    'contentengine.media_lifecycle_backfill',
    'on',
    true
  );

  with derived as (
    select
      media.organization_id,
      media.id,
      case
        when exists (
          select 1
          from content_factory.placements placement
          join content_factory.generation_jobs job
            on job.organization_id = placement.organization_id
           and job.project_id = placement.project_id
           and job.id = placement.generation_job_id
          where placement.organization_id = media.organization_id
            and placement.project_id = media.project_id
            and placement.status = 'published'
            and job.output ->> 'output_media_id' = media.id::text
        ) then 'published'
        when latest_review.decision = 'approved' then 'ready'
        when latest_review.decision in ('needs_changes', 'rejected')
          then 'drafts'
        when latest_review.review_id is not null
             and latest_review.review_status in (
               'queued', 'processing', 'completed'
             ) then 'review'
        else 'drafts'
      end as lifecycle_stage
    from content_factory.media_objects media
    left join lateral (
      select
        review.id as review_id,
        review.status as review_status,
        decision.decision
      from content_factory.content_review_runs review
      left join content_factory.content_review_decisions decision
        on decision.organization_id = review.organization_id
       and decision.review_id = review.id
      where review.organization_id = media.organization_id
        and review.project_id = media.project_id
        and review.media_object_id = media.id
      order by review.created_at desc, review.id desc
      limit 1
    ) latest_review on true
    where media.project_id is not null
      and media.artifact_class = 'generated_output'
      and media.status not in ('deleted', 'archived')
  )
  update content_factory.media_objects media
  set lifecycle_stage = derived.lifecycle_stage
  from derived
  where media.organization_id = derived.organization_id
    and media.id = derived.id
    and media.lifecycle_stage is distinct from derived.lifecycle_stage;

  -- Move only unfiled/system-filed rows to the derived system folder.  A
  -- custom user location remains intact during migration backfill.
  for media_row in
    select media.organization_id, media.id
    from content_factory.media_objects media
    left join content_factory.workspace_media_locations location
      on location.organization_id = media.organization_id
     and location.media_object_id = media.id
    left join content_factory.workspace_folders current_folder
      on current_folder.organization_id = location.organization_id
     and current_folder.id = location.folder_id
    where media.project_id is not null
      and media.artifact_class = 'generated_output'
      and media.lifecycle_stage in (
        'drafts', 'review', 'ready', 'published'
      )
      and (
        location.folder_id is null
        or current_folder.system_role is not null
      )
  loop
    perform content_factory_private.sync_workspace_media_system_location(
      media_row.organization_id,
      media_row.id,
      true
    );
  end loop;

  perform set_config(
    'contentengine.media_lifecycle_backfill',
    coalesce(previous_backfill_setting, ''),
    true
  );
exception
  when others then
    perform set_config(
      'contentengine.media_lifecycle_backfill',
      coalesce(previous_backfill_setting, ''),
      true
    );
    raise;
end;
$$;

commit;

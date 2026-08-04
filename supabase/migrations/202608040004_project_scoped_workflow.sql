begin;

-- A project is a durable workflow boundary, not the folder currently visible
-- in Finder. Existing root folders become projects; existing workflow rows stay
-- nullable when their project cannot be established without guessing.
alter table content_factory.workspace_folders
  add column if not exists kind text,
  add column if not exists system_role text;

update content_factory.workspace_folders
set kind = case when parent_id is null then 'project' else 'folder' end
where kind is null;

update content_factory.workspace_folders child
set system_role = case lower(btrim(child.name))
  when 'исходники' then 'sources'
  when 'черновики' then 'drafts'
  when 'на проверке' then 'review'
  when 'готово' then 'ready'
  when 'опубликовано' then 'published'
  else null
end
from content_factory.workspace_folders project
where child.organization_id = project.organization_id
  and child.parent_id = project.id
  and project.kind = 'project'
  and child.system_role is null;

alter table content_factory.workspace_folders
  alter column kind set default 'folder',
  alter column kind set not null,
  add constraint workspace_folders_kind_check
    check (kind in ('project', 'folder')),
  add constraint workspace_folders_kind_shape_check
    check (
      (kind = 'project' and parent_id is null and system_role is null)
      or (kind = 'folder' and parent_id is not null)
    ),
  add constraint workspace_folders_system_role_check
    check (
      system_role is null
      or system_role in ('sources', 'drafts', 'review', 'ready', 'published')
    );

create unique index if not exists workspace_folders_project_system_role_uq
  on content_factory.workspace_folders (
    organization_id, parent_id, system_role
  )
  where status = 'active' and system_role is not null;

create index if not exists workspace_folders_project_list_idx
  on content_factory.workspace_folders (
    organization_id, updated_at desc, id desc
  )
  where status = 'active' and kind = 'project';

create or replace function content_factory_private.workspace_project_for_folder(
  p_organization_id uuid,
  p_folder_id uuid
)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  with recursive lineage as (
    select folder.id, folder.parent_id, folder.kind, folder.status, 0 as depth
    from content_factory.workspace_folders folder
    where folder.organization_id = p_organization_id
      and folder.id = p_folder_id
    union all
    select parent.id, parent.parent_id, parent.kind, parent.status,
           lineage.depth + 1
    from lineage
    join content_factory.workspace_folders parent
      on parent.organization_id = p_organization_id
     and parent.id = lineage.parent_id
    where lineage.depth < 8
  )
  select lineage.id
  from lineage
  where lineage.kind = 'project'
    and lineage.parent_id is null
    and lineage.status = 'active'
  order by lineage.depth desc
  limit 1
$$;

create or replace function content_factory_private.guard_workspace_project_kind()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  parent_project_id uuid;
  old_project_id uuid;
  parent_kind text;
  archive_context_id uuid;
begin
  new.kind := lower(btrim(coalesce(new.kind, 'folder')));
  new.system_role := nullif(lower(btrim(coalesce(new.system_role, ''))), '');

  if tg_op = 'UPDATE' then
    if new.kind is distinct from old.kind then
      raise exception using errcode = '55000', message = 'workspace_folder_kind_immutable';
    end if;
    if old.system_role is not null then
      if new.name is distinct from old.name
         or new.color_token is distinct from old.color_token
         or new.system_role is distinct from old.system_role
         or new.parent_id is distinct from old.parent_id then
        raise exception using errcode = '55000', message = 'workspace_system_folder_identity_immutable';
      end if;
      if new.status is distinct from old.status then
        begin
          archive_context_id := nullif(
            current_setting('contentengine.project_archive_id', true), ''
          )::uuid;
        exception when invalid_text_representation then
          archive_context_id := null;
        end;
        if not (
          old.status = 'active'
          and new.status = 'archived'
          and old.parent_id = archive_context_id
        ) then
          raise exception using errcode = '55000', message = 'workspace_system_folder_status_immutable';
        end if;
      end if;
    end if;
    if old.kind = 'project' and old.status = 'active'
       and new.status = 'archived' then
      begin
        archive_context_id := nullif(
          current_setting('contentengine.project_archive_id', true), ''
        )::uuid;
      exception when invalid_text_representation then
        archive_context_id := null;
      end;
      if archive_context_id is distinct from old.id then
        raise exception using
          errcode = '55000',
          message = 'workspace_project_archive_command_required';
      end if;
      if exists (
        select 1 from content_factory.media_objects media
        where media.organization_id = old.organization_id
          and media.project_id = old.id
      ) or exists (
        select 1 from content_factory.generation_batches batch
        where batch.organization_id = old.organization_id
          and batch.project_id = old.id
      ) or exists (
        select 1 from content_factory.generation_jobs job
        where job.organization_id = old.organization_id
          and job.project_id = old.id
      ) or exists (
        select 1 from content_factory.creator_tasks task
        where task.organization_id = old.organization_id
          and task.project_id = old.id
      ) or exists (
        select 1 from content_factory.content_review_runs review
        where review.organization_id = old.organization_id
          and review.project_id = old.id
      ) or exists (
        select 1 from content_factory.product_research_runs research
        where research.organization_id = old.organization_id
          and research.project_id = old.id
      ) or exists (
        select 1 from content_factory.creative_brief_drafts draft
        where draft.organization_id = old.organization_id
          and draft.project_id = old.id
      ) or exists (
        select 1 from content_factory.placements placement
        where placement.organization_id = old.organization_id
          and placement.project_id = old.id
      ) then
        raise exception using
          errcode = '55000', message = 'workspace_project_not_empty';
      end if;
    end if;
  end if;

  if new.kind = 'project' then
    if new.parent_id is not null or new.system_role is not null then
      raise exception using errcode = '22023', message = 'workspace_project_shape_invalid';
    end if;
    return new;
  end if;

  if new.parent_id is null then
    raise exception using errcode = '22023', message = 'workspace_folder_project_required';
  end if;
  parent_project_id := content_factory_private.workspace_project_for_folder(
    new.organization_id,
    new.parent_id
  );
  if parent_project_id is null then
    raise exception using errcode = '22023', message = 'workspace_folder_project_required';
  end if;

  -- A folder move may change its place inside one project, but never its
  -- project boundary. Workflow rows keep immutable project_id values, so
  -- allowing a subtree to cross that boundary would make Finder disagree
  -- with generation/review/placement truth without touching any item row.
  if tg_op = 'UPDATE' and new.parent_id is distinct from old.parent_id then
    old_project_id := content_factory_private.workspace_project_for_folder(
      old.organization_id,
      old.id
    );
    if old_project_id is distinct from parent_project_id then
      raise exception using
        errcode = '55000',
        message = 'workspace_cross_project_folder_move_forbidden';
    end if;
  end if;

  if new.system_role is not null then
    select parent.kind into parent_kind
    from content_factory.workspace_folders parent
    where parent.organization_id = new.organization_id
      and parent.id = new.parent_id
      and parent.status = 'active';
    if parent_kind is distinct from 'project' then
      raise exception using errcode = '22023', message = 'workspace_system_folder_parent_invalid';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists guard_workspace_project_kind
  on content_factory.workspace_folders;
create trigger guard_workspace_project_kind
before insert or update of name, color_token, kind, system_role, parent_id, status
on content_factory.workspace_folders
for each row execute function
  content_factory_private.guard_workspace_project_kind();

alter table content_factory.media_objects
  add column if not exists project_id uuid;
alter table content_factory.generation_batches
  add column if not exists project_id uuid;
alter table content_factory.generation_jobs
  add column if not exists project_id uuid;
alter table content_factory.creator_tasks
  add column if not exists project_id uuid;
alter table content_factory.content_review_runs
  add column if not exists project_id uuid;
alter table content_factory.placements
  add column if not exists project_id uuid;
alter table content_factory.product_research_runs
  add column if not exists project_id uuid;
alter table content_factory.creative_brief_drafts
  add column if not exists project_id uuid;

alter table content_factory.media_objects
  add constraint media_objects_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.generation_batches
  add constraint generation_batches_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.generation_jobs
  add constraint generation_jobs_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.creator_tasks
  add constraint creator_tasks_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.content_review_runs
  add constraint content_review_runs_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.placements
  add constraint placements_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.product_research_runs
  add constraint product_research_runs_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);
alter table content_factory.creative_brief_drafts
  add constraint creative_brief_drafts_project_fk
  foreign key (organization_id, project_id)
  references content_factory.workspace_folders(organization_id, id);

create index if not exists media_objects_project_status_idx
  on content_factory.media_objects (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists generation_batches_project_status_idx
  on content_factory.generation_batches (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists generation_batches_project_archive_idx
  on content_factory.generation_batches (
    organization_id, project_id, created_at desc, id desc
  ) where project_id is not null;
create index if not exists generation_batches_project_owner_archive_idx
  on content_factory.generation_batches (
    organization_id, project_id, created_by, created_at desc, id desc
  ) where project_id is not null;
create index if not exists generation_jobs_project_status_idx
  on content_factory.generation_jobs (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists creator_tasks_project_status_idx
  on content_factory.creator_tasks (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists content_review_runs_project_status_idx
  on content_factory.content_review_runs (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists content_review_runs_project_media_idx
  on content_factory.content_review_runs (
    organization_id, project_id, media_object_id, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists placements_project_status_idx
  on content_factory.placements (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists product_research_runs_project_status_idx
  on content_factory.product_research_runs (
    organization_id, project_id, status, updated_at desc, id desc
  ) where project_id is not null;
create index if not exists creative_brief_drafts_project_run_idx
  on content_factory.creative_brief_drafts (
    organization_id, project_id, run_id, version desc, id desc
  ) where project_id is not null;

create index if not exists placements_project_review_idx
  on content_factory.placements (
    organization_id, project_id, (metadata ->> 'content_review_id')
  ) where project_id is not null and metadata ? 'content_review_id';

-- Backfill only deterministic relationships. Rows that cannot be linked
-- without ambiguity deliberately remain NULL and surface as "Без проекта".
update content_factory.media_objects media
set project_id = content_factory_private.workspace_project_for_folder(
  media.organization_id,
  location.folder_id
)
from content_factory.workspace_media_locations location
where location.organization_id = media.organization_id
  and location.media_object_id = media.id
  and location.folder_id is not null
  and media.task_id is null
  and media.project_id is null
  and content_factory_private.workspace_project_for_folder(
        media.organization_id,
        location.folder_id
      ) is not null;

with batch_scope as (
  select batch.organization_id, batch.id,
         (array_agg(distinct media.project_id)
           filter (where media.project_id is not null))[1] as project_id,
         count(*) as media_count,
         count(media.project_id) as scoped_count,
         count(distinct media.project_id) as project_count
  from content_factory.generation_batches batch
  cross join lateral jsonb_array_elements_text(
    case when jsonb_typeof(batch.input -> 'media_ids') = 'array'
      then batch.input -> 'media_ids'
      else '[]'::jsonb
    end
  ) media_id(value)
  join content_factory.media_objects media
    on media.organization_id = batch.organization_id
   and media.id::text = media_id.value
  group by batch.organization_id, batch.id
)
update content_factory.generation_batches batch
set project_id = scope.project_id
from batch_scope scope
where batch.organization_id = scope.organization_id
  and batch.id = scope.id
  and batch.project_id is null
  and scope.media_count = scope.scoped_count
  and scope.project_count = 1;

update content_factory.generation_jobs job
set project_id = batch.project_id
from content_factory.generation_batches batch
where batch.organization_id = job.organization_id
  and batch.id = job.batch_id
  and batch.project_id is not null
  and job.project_id is null;

with task_scope as (
  select task.organization_id, task.id,
         (array_agg(distinct candidate.project_id)
           filter (where candidate.project_id is not null))[1] as project_id,
         count(distinct candidate.project_id)
           filter (where candidate.project_id is not null) as project_count
  from content_factory.creator_tasks task
  left join content_factory.generation_jobs job
    on job.organization_id = task.organization_id
   and job.id = task.generation_job_id
  left join content_factory.creative_brief_drafts draft
    on draft.organization_id = task.organization_id
   and draft.id = task.creative_brief_draft_id
  left join content_factory.workspace_task_locations location
    on location.organization_id = task.organization_id
   and location.task_id = task.id
  cross join lateral (values
    (job.project_id),
    (draft.project_id),
    (content_factory_private.workspace_project_for_folder(
      task.organization_id, location.folder_id
    ))
  ) candidate(project_id)
  where task.project_id is null
  group by task.organization_id, task.id
)
update content_factory.creator_tasks task
set project_id = scope.project_id
from task_scope scope
where task.organization_id = scope.organization_id
  and task.id = scope.id
  and scope.project_count = 1;

with media_scope as (
  select media.organization_id, media.id,
         (array_agg(distinct candidate.project_id)
           filter (where candidate.project_id is not null))[1] as project_id,
         count(distinct candidate.project_id)
           filter (where candidate.project_id is not null) as project_count
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  left join content_factory.workspace_media_locations location
    on location.organization_id = media.organization_id
   and location.media_object_id = media.id
  cross join lateral (values
    (task.project_id),
    (content_factory_private.workspace_project_for_folder(
      media.organization_id, location.folder_id
    ))
  ) candidate(project_id)
  where media.project_id is null
    -- A media row linked to an ambiguous/unscoped task stays legacy NULL;
    -- its Finder location alone is not enough to override task lineage.
    and (media.task_id is null or task.project_id is not null)
  group by media.organization_id, media.id
)
update content_factory.media_objects media
set project_id = scope.project_id
from media_scope scope
where media.organization_id = scope.organization_id
  and media.id = scope.id
  and scope.project_count = 1;

with review_scope as (
  select review.organization_id, review.id,
         (array_agg(distinct candidate.project_id)
           filter (where candidate.project_id is not null))[1] as project_id,
         count(distinct candidate.project_id)
           filter (where candidate.project_id is not null) as project_count
  from content_factory.content_review_runs review
  left join content_factory.media_objects media
    on media.organization_id = review.organization_id
   and media.id = review.media_object_id
  left join content_factory.content_review_runs parent
    on parent.organization_id = review.organization_id
   and parent.id = review.parent_review_id
  cross join lateral (values
    (media.project_id),
    (parent.project_id)
  ) candidate(project_id)
  where review.project_id is null
  group by review.organization_id, review.id
)
update content_factory.content_review_runs review
set project_id = scope.project_id
from review_scope scope
where review.organization_id = scope.organization_id
  and review.id = scope.id
  and scope.project_count = 1;

update content_factory.placements placement
set project_id = job.project_id
from content_factory.generation_jobs job
where job.organization_id = placement.organization_id
  and job.id = placement.generation_job_id
  and job.project_id is not null
  and placement.project_id is null
  and not exists (
    select 1 from content_factory.creator_tasks task
    where task.organization_id = placement.organization_id
      and task.id = placement.task_id
      and task.project_id is not null
      and task.project_id <> job.project_id
  );

update content_factory.placements placement
set project_id = task.project_id
from content_factory.creator_tasks task
where task.organization_id = placement.organization_id
  and task.id = placement.task_id
  and task.project_id is not null
  and placement.project_id is null
  and not exists (
    select 1 from content_factory.generation_jobs job
    where job.organization_id = placement.organization_id
      and job.id = placement.generation_job_id
      and job.project_id is not null
      and job.project_id <> task.project_id
  );

-- Legacy research can be assigned safely only after deterministic media/task
-- backfills above have run. Ambiguous historical runs remain NULL and are
-- never restored by the project-scoped v4.7 API.
with research_scope as (
  select source.organization_id,
         source.run_id,
         count(*) as source_count,
         count(media.project_id) as scoped_source_count,
         count(distinct media.project_id) as project_count,
         min(media.project_id::text)::uuid as project_id
  from content_factory.product_research_sources source
  left join content_factory.media_objects media
    on media.organization_id = source.organization_id
   and media.id = source.media_object_id
  group by source.organization_id, source.run_id
), inferred as (
  select scope.organization_id, scope.run_id, scope.project_id
  from research_scope scope
  where scope.source_count > 0
    and scope.source_count = scope.scoped_source_count
    and scope.project_count = 1
)
update content_factory.product_research_runs run
set project_id = inferred.project_id
from inferred
where run.organization_id = inferred.organization_id
  and run.id = inferred.run_id
  and run.project_id is null;

update content_factory.creative_brief_drafts draft
set project_id = run.project_id
from content_factory.product_research_runs run
where run.organization_id = draft.organization_id
  and run.id = draft.run_id
  and draft.project_id is null
  and run.project_id is not null;

update content_factory.creator_tasks task
set project_id = draft.project_id
from content_factory.creative_brief_drafts draft
where draft.organization_id = task.organization_id
  and draft.id = task.creative_brief_draft_id
  and task.project_id is null
  and draft.project_id is not null
  and not exists (
    select 1
    from content_factory.generation_jobs job
    where job.organization_id = task.organization_id
      and job.id = task.generation_job_id
      and job.project_id is not null
      and job.project_id <> draft.project_id
  )
  and not exists (
    select 1
    from content_factory.workspace_task_locations location
    where location.organization_id = task.organization_id
      and location.task_id = task.id
      and content_factory_private.workspace_project_for_folder(
        task.organization_id, location.folder_id
      ) is not null
      and content_factory_private.workspace_project_for_folder(
        task.organization_id, location.folder_id
      ) <> draft.project_id
  );

create or replace function content_factory_private.merge_project_lineage(
  p_current uuid,
  p_expected uuid
)
returns uuid
language plpgsql
immutable
set search_path = ''
as $$
begin
  if p_current is not null and p_expected is not null
     and p_current <> p_expected then
    raise exception using errcode = '22023', message = 'project_lineage_mismatch';
  end if;
  return coalesce(p_current, p_expected);
end;
$$;

create or replace function content_factory_private.guard_project_lineage()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  expected_project_id uuid;
  second_project_id uuid;
  context_project_id uuid;
  context_value text;
  media_count integer := 0;
  scoped_media_count integer := 0;
  media_project_count integer := 0;
begin
  if tg_op = 'UPDATE'
     and old.project_id is not null
     and new.project_id is distinct from old.project_id then
    raise exception using errcode = '55000', message = 'project_id_immutable';
  end if;

  context_value := nullif(current_setting('contentengine.project_id', true), '');
  if context_value is not null then
    begin
      context_project_id := context_value::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023', message = 'project_context_invalid';
    end;
  end if;
  new.project_id := content_factory_private.merge_project_lineage(
    new.project_id,
    context_project_id
  );

  if tg_table_name = 'generation_batches' then
    if tg_op = 'INSERT' or new.input is distinct from old.input
       or new.project_id is distinct from old.project_id then
      select
        (array_agg(distinct media.project_id)
          filter (where media.project_id is not null))[1],
        count(*), count(media.project_id), count(distinct media.project_id)
      into expected_project_id, media_count, scoped_media_count,
           media_project_count
      from jsonb_array_elements_text(
        case when jsonb_typeof(new.input -> 'media_ids') = 'array'
          then new.input -> 'media_ids'
          else '[]'::jsonb
        end
      ) media_id(value)
      left join content_factory.media_objects media
        on media.organization_id = new.organization_id
       and media.id::text = media_id.value;

      if media_project_count > 1 then
        raise exception using errcode = '22023', message = 'project_media_scope_mismatch';
      end if;
      new.project_id := content_factory_private.merge_project_lineage(
        new.project_id,
        expected_project_id
      );
      if new.project_id is not null and media_count > 0
         and scoped_media_count <> media_count then
        raise exception using errcode = '22023', message = 'project_media_scope_required';
      end if;
    end if;
  elsif tg_table_name = 'generation_jobs' then
    select batch.project_id into expected_project_id
    from content_factory.generation_batches batch
    where batch.organization_id = new.organization_id
      and batch.id = new.batch_id;
    new.project_id := content_factory_private.merge_project_lineage(
      new.project_id, expected_project_id
    );
  elsif tg_table_name = 'creator_tasks' then
    if new.generation_job_id is not null then
      select job.project_id into expected_project_id
      from content_factory.generation_jobs job
      where job.organization_id = new.organization_id
        and job.id = new.generation_job_id;
      new.project_id := content_factory_private.merge_project_lineage(
        new.project_id, expected_project_id
      );
    end if;
    if new.creative_brief_draft_id is not null then
      select draft.project_id into second_project_id
      from content_factory.creative_brief_drafts draft
      where draft.organization_id = new.organization_id
        and draft.id = new.creative_brief_draft_id;
      new.project_id := content_factory_private.merge_project_lineage(
        new.project_id, second_project_id
      );
    end if;
  elsif tg_table_name = 'media_objects' then
    if new.task_id is not null then
      select task.project_id into expected_project_id
      from content_factory.creator_tasks task
      where task.organization_id = new.organization_id
        and task.id = new.task_id;
      new.project_id := content_factory_private.merge_project_lineage(
        new.project_id, expected_project_id
      );
    end if;
  elsif tg_table_name = 'creative_brief_drafts' then
    select run.project_id into expected_project_id
    from content_factory.product_research_runs run
    where run.organization_id = new.organization_id
      and run.id = new.run_id;
    new.project_id := content_factory_private.merge_project_lineage(
      new.project_id, expected_project_id
    );
  elsif tg_table_name = 'content_review_runs' then
    select media.project_id into expected_project_id
    from content_factory.media_objects media
    where media.organization_id = new.organization_id
      and media.id = new.media_object_id;
    if new.parent_review_id is not null then
      select parent.project_id into second_project_id
      from content_factory.content_review_runs parent
      where parent.organization_id = new.organization_id
        and parent.id = new.parent_review_id;
      expected_project_id := content_factory_private.merge_project_lineage(
        expected_project_id, second_project_id
      );
    end if;
    new.project_id := content_factory_private.merge_project_lineage(
      new.project_id, expected_project_id
    );
  elsif tg_table_name = 'placements' then
    if new.generation_job_id is not null then
      select job.project_id into expected_project_id
      from content_factory.generation_jobs job
      where job.organization_id = new.organization_id
        and job.id = new.generation_job_id;
    end if;
    if new.task_id is not null then
      select task.project_id into second_project_id
      from content_factory.creator_tasks task
      where task.organization_id = new.organization_id
        and task.id = new.task_id;
      expected_project_id := content_factory_private.merge_project_lineage(
        expected_project_id, second_project_id
      );
    end if;
    new.project_id := content_factory_private.merge_project_lineage(
      new.project_id, expected_project_id
    );
  end if;

  if new.project_id is not null and (
    tg_op = 'INSERT' or old.project_id is distinct from new.project_id
  ) and not exists (
    select 1
    from content_factory.workspace_folders project
    where project.organization_id = new.organization_id
      and project.id = new.project_id
      and project.kind = 'project'
      and project.status = 'active'
  ) then
    raise exception using errcode = 'P0002', message = 'workspace_project_not_found';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_media_object_project_lineage
  on content_factory.media_objects;
create trigger guard_media_object_project_lineage
before insert or update of project_id, task_id
on content_factory.media_objects
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_generation_batch_project_lineage
  on content_factory.generation_batches;
create trigger guard_generation_batch_project_lineage
before insert or update of project_id, input
on content_factory.generation_batches
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_generation_job_project_lineage
  on content_factory.generation_jobs;
create trigger guard_generation_job_project_lineage
before insert or update of project_id, batch_id
on content_factory.generation_jobs
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_creator_task_project_lineage
  on content_factory.creator_tasks;
create trigger guard_creator_task_project_lineage
before insert or update of project_id, generation_job_id,
  creative_brief_draft_id
on content_factory.creator_tasks
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_content_review_project_lineage
  on content_factory.content_review_runs;
create trigger guard_content_review_project_lineage
before insert or update of project_id, media_object_id, parent_review_id
on content_factory.content_review_runs
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_placement_project_lineage
  on content_factory.placements;
create trigger guard_placement_project_lineage
before insert or update of project_id, generation_job_id, task_id
on content_factory.placements
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_product_research_project_lineage
  on content_factory.product_research_runs;
create trigger guard_product_research_project_lineage
before insert or update of project_id
on content_factory.product_research_runs
for each row execute function content_factory_private.guard_project_lineage();

drop trigger if exists guard_creative_brief_project_lineage
  on content_factory.creative_brief_drafts;
create trigger guard_creative_brief_project_lineage
before insert or update of project_id, run_id
on content_factory.creative_brief_drafts
for each row execute function content_factory_private.guard_project_lineage();

create or replace function content_factory_private.assign_workspace_location_project()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  project_id_value uuid;
  existing_project_id uuid;
begin
  if new.folder_id is null then return new; end if;
  project_id_value := content_factory_private.workspace_project_for_folder(
    new.organization_id,
    new.folder_id
  );
  if project_id_value is null then
    raise exception using errcode = '22023', message = 'workspace_folder_project_required';
  end if;

  if tg_table_name = 'workspace_media_locations' then
    select media.project_id into existing_project_id
    from content_factory.media_objects media
    where media.organization_id = new.organization_id
      and media.id = new.media_object_id
    for update;
    if existing_project_id is not null and existing_project_id <> project_id_value then
      raise exception using errcode = '55000', message = 'workspace_cross_project_move_forbidden';
    end if;
    update content_factory.media_objects media
    set project_id = project_id_value
    where media.organization_id = new.organization_id
      and media.id = new.media_object_id
      and media.project_id is null;
  else
    select task.project_id into existing_project_id
    from content_factory.creator_tasks task
    where task.organization_id = new.organization_id
      and task.id = new.task_id
    for update;
    if existing_project_id is not null and existing_project_id <> project_id_value then
      raise exception using errcode = '55000', message = 'workspace_cross_project_move_forbidden';
    end if;
    update content_factory.creator_tasks task
    set project_id = project_id_value
    where task.organization_id = new.organization_id
      and task.id = new.task_id
      and task.project_id is null;
  end if;
  return new;
end;
$$;

drop trigger if exists assign_workspace_media_location_project
  on content_factory.workspace_media_locations;
create trigger assign_workspace_media_location_project
after insert or update of folder_id
on content_factory.workspace_media_locations
for each row execute function
  content_factory_private.assign_workspace_location_project();

drop trigger if exists assign_workspace_task_location_project
  on content_factory.workspace_task_locations;
create trigger assign_workspace_task_location_project
after insert or update of folder_id
on content_factory.workspace_task_locations
for each row execute function
  content_factory_private.assign_workspace_location_project();

create or replace function content_factory_private.require_workspace_project(
  p_organization_id uuid,
  p_project_id uuid
)
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if p_project_id is null or not exists (
    select 1
    from content_factory.workspace_folders project
    where project.organization_id = p_organization_id
      and project.id = p_project_id
      and project.kind = 'project'
      and project.status = 'active'
  ) then
    raise exception using errcode = 'P0002', message = 'workspace_project_not_found';
  end if;
  return p_project_id;
end;
$$;

create or replace function content_factory_private.project_flow_snapshot(
  p_organization_id uuid,
  p_project_id uuid,
  p_user_id uuid,
  p_actor_role text
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  project_name text;
  project_color text;
  project_status text;
  project_updated_at timestamptz;
  snapshot_updated_at timestamptz;
  manager_scope boolean;
  sources_folder_id uuid;
  source_count integer := 0;
  source_media_id uuid;
  generated_count integer := 0;
  generated_media_id uuid;
  unreviewed_media_id uuid;
  generation_job_count integer := 0;
  latest_job_id uuid;
  latest_job_status text;
  latest_job_output jsonb := '{}'::jsonb;
  latest_job_input jsonb := '{}'::jsonb;
  failed_job_source_media_id uuid;
  review_count integer := 0;
  latest_review_id uuid;
  latest_review_status text;
  latest_review_media_id uuid;
  latest_review_decision text;
  unplaced_review_id uuid;
  placement_count integer := 0;
  latest_placement_id uuid;
  latest_placement_status text;
  latest_placement_metric_count integer := 0;
  metric_count integer := 0;
  actionable_task_count integer := 0;
  actionable_task_id uuid;
  actionable_task_type text;
  actionable_task_status text;
  actionable_task_stage text;
  active_position integer := 1;
  active_stage text := 'files';
  active_state text := 'current';
  active_reason_code text := 'source_media_required';
  active_reason text := 'Добавьте хотя бы один готовый исходный материал.';
  next_action jsonb;
  counts_value jsonb;
  stages_value jsonb;
  progress_percent integer := 0;
  flow_complete boolean := false;
  entity_id_value uuid;
  route_value text;
begin
  select project.name, project.color_token, project.status, project.updated_at
  into project_name, project_color, project_status, project_updated_at
  from content_factory.workspace_folders project
  where project.organization_id = p_organization_id
    and project.id = p_project_id
    and project.kind = 'project'
    and project.status = 'active';
  if project_name is null then
    raise exception using errcode = 'P0002', message = 'workspace_project_not_found';
  end if;

  manager_scope := p_actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  select folder.id into sources_folder_id
  from content_factory.workspace_folders folder
  where folder.organization_id = p_organization_id
    and folder.parent_id = p_project_id
    and folder.system_role = 'sources'
    and folder.status = 'active'
  limit 1;

  select count(*)::integer,
         (array_agg(media.id order by media.updated_at desc, media.id desc))[1]
  into source_count, source_media_id
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where media.organization_id = p_organization_id
    and media.project_id = p_project_id
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and (manager_scope or media.owner_id = p_user_id
         or task.assignee_id = p_user_id);

  select media.id
  into unreviewed_media_id
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where media.organization_id = p_organization_id
    and media.project_id = p_project_id
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('generated_video', 'generated_image')
    and (manager_scope or media.owner_id = p_user_id
         or task.assignee_id = p_user_id)
    and not exists (
      select 1
      from content_factory.content_review_runs review
      where review.organization_id = media.organization_id
        and review.project_id = p_project_id
        and review.media_object_id = media.id
        and review.status not in ('cancelled', 'failed')
    )
  order by media.updated_at desc, media.id desc
  limit 1;

  select count(*)::integer,
         (array_agg(media.id order by media.updated_at desc, media.id desc))[1]
  into generated_count, generated_media_id
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where media.organization_id = p_organization_id
    and media.project_id = p_project_id
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('generated_video', 'generated_image')
    and (manager_scope or media.owner_id = p_user_id
         or task.assignee_id = p_user_id);

  select count(*)::integer
  into generation_job_count
  from content_factory.generation_jobs job
  where job.organization_id = p_organization_id
    and job.project_id = p_project_id
    and (manager_scope or job.assigned_to = p_user_id
         or job.requested_by = p_user_id);

  select job.id, job.status, job.output, job.input
  into latest_job_id, latest_job_status, latest_job_output, latest_job_input
  from content_factory.generation_jobs job
  where job.organization_id = p_organization_id
    and job.project_id = p_project_id
    and (manager_scope or job.assigned_to = p_user_id
         or job.requested_by = p_user_id)
  order by job.updated_at desc, job.id desc
  limit 1;

  select media.id
  into failed_job_source_media_id
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.project_id = p_project_id
    and media.id::text = coalesce(latest_job_input ->> 'input_media_id', '')
    and media.status = 'ready'
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb
  limit 1;

  select count(*)::integer
  into review_count
  from content_factory.content_review_runs review
  join content_factory.media_objects media
    on media.organization_id = review.organization_id
   and media.id = review.media_object_id
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where review.organization_id = p_organization_id
    and review.project_id = p_project_id
    and (manager_scope or review.requested_by = p_user_id
         or media.owner_id = p_user_id or task.assignee_id = p_user_id);

  select review.id, review.status, review.media_object_id,
         decision.decision
  into latest_review_id, latest_review_status, latest_review_media_id,
       latest_review_decision
  from content_factory.content_review_runs review
  join content_factory.media_objects media
    on media.organization_id = review.organization_id
   and media.id = review.media_object_id
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  left join lateral (
    select record.decision
    from content_factory.content_review_decisions record
    where record.organization_id = review.organization_id
      and record.review_id = review.id
    order by record.created_at desc, record.id desc
    limit 1
  ) decision on true
  where review.organization_id = p_organization_id
    and review.project_id = p_project_id
    and review.status <> 'failed'
    and (manager_scope or review.requested_by = p_user_id
         or media.owner_id = p_user_id or task.assignee_id = p_user_id)
    and not exists (
      select 1
      from content_factory.content_review_runs child
      where child.organization_id = review.organization_id
        and child.project_id = p_project_id
        and child.parent_review_id = review.id
        and child.status <> 'cancelled'
    )
    and not (
      decision.decision = 'rejected'
      and (
        exists (
          select 1
          from content_factory.content_review_runs replacement_review
          where replacement_review.organization_id = review.organization_id
            and replacement_review.project_id = p_project_id
            and replacement_review.media_object_id = review.media_object_id
            and replacement_review.status <> 'cancelled'
            and (replacement_review.updated_at, replacement_review.id)
              > (review.updated_at, review.id)
        )
        or exists (
          select 1
          from content_factory.media_objects replacement_media
          where replacement_media.organization_id = review.organization_id
            and replacement_media.project_id = p_project_id
            and replacement_media.status = 'ready'
            and replacement_media.metadata ->> 'kind' in (
              'generated_video', 'generated_image'
            )
            and (replacement_media.updated_at, replacement_media.id)
              > (media.updated_at, media.id)
        )
      )
    )
  order by case
      when decision.decision = 'needs_changes' then 0
      when review.status = 'failed' or decision.decision = 'rejected' then 1
      when decision.decision is distinct from 'approved' then 2
      else 3
    end,
    review.updated_at desc, review.id desc
  limit 1;

  select review.id
  into unplaced_review_id
  from content_factory.content_review_runs review
  join content_factory.content_review_decisions decision
    on decision.organization_id = review.organization_id
   and decision.review_id = review.id
   and decision.decision = 'approved'
  join content_factory.media_objects media
    on media.organization_id = review.organization_id
   and media.id = review.media_object_id
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  where review.organization_id = p_organization_id
    and review.project_id = p_project_id
    and (manager_scope or review.requested_by = p_user_id
         or media.owner_id = p_user_id or task.assignee_id = p_user_id)
    and not exists (
      select 1
      from content_factory.placements placement
      where placement.organization_id = review.organization_id
        and placement.project_id = p_project_id
        and placement.metadata ->> 'content_review_id' = review.id::text
        and placement.status not in ('failed', 'cancelled')
    )
    and not exists (
      select 1
      from content_factory.content_review_runs child
      where child.organization_id = review.organization_id
        and child.project_id = p_project_id
        and child.parent_review_id = review.id
        and child.status <> 'cancelled'
    )
  order by decision.created_at desc, review.id desc
  limit 1;

  select count(*)::integer
  into placement_count
  from content_factory.placements placement
  where placement.organization_id = p_organization_id
    and placement.project_id = p_project_id
    and (manager_scope or placement.assigned_to = p_user_id);

  select placement.id, placement.status
  into latest_placement_id, latest_placement_status
  from content_factory.placements placement
  where placement.organization_id = p_organization_id
    and placement.project_id = p_project_id
    and (manager_scope or placement.assigned_to = p_user_id)
    and placement.status not in ('failed', 'cancelled')
  order by case
      when placement.status <> 'published' then 0
      when not exists (
        select 1 from content_factory.metric_snapshots metric
        where metric.organization_id = placement.organization_id
          and metric.placement_id = placement.id
      ) then 1
      else 2
    end,
    placement.updated_at desc, placement.id desc
  limit 1;

  if latest_placement_id is not null then
    select count(*)::integer
    into latest_placement_metric_count
    from content_factory.metric_snapshots metric
    where metric.organization_id = p_organization_id
      and metric.placement_id = latest_placement_id;
  end if;

  select count(*)::integer
  into metric_count
  from content_factory.metric_snapshots metric
  join content_factory.placements placement
    on placement.organization_id = metric.organization_id
   and placement.id = metric.placement_id
  where placement.organization_id = p_organization_id
    and placement.project_id = p_project_id
    and (manager_scope or placement.assigned_to = p_user_id);

  select count(*)::integer
  into actionable_task_count
  from content_factory.creator_tasks task
  where task.organization_id = p_organization_id
    and task.project_id = p_project_id
    and task.status in (
      'todo', 'in_progress', 'submitted', 'review', 'blocked'
    )
    and (manager_scope or task.status not in ('submitted', 'review'))
    and (manager_scope or task.assignee_id = p_user_id);

  select task.id, task.task_type, task.status
  into actionable_task_id, actionable_task_type, actionable_task_status
  from content_factory.creator_tasks task
  where task.organization_id = p_organization_id
    and task.project_id = p_project_id
    and task.status in (
      'todo', 'in_progress', 'submitted', 'review', 'blocked'
    )
    and (manager_scope or task.status not in ('submitted', 'review'))
    and (manager_scope or task.assignee_id = p_user_id)
  order by case task.status
      when 'blocked' then 0
      when 'in_progress' then 1
      when 'review' then 2
      when 'todo' then 3
      else 4
    end,
    task.priority asc,
    task.due_at asc nulls last,
    task.updated_at asc,
    task.id asc
  limit 1;
  actionable_task_stage := case actionable_task_type
    when 'video_review' then 'review'
    when 'placement' then 'placement'
    when 'metrics' then 'stats'
    else 'generation'
  end;

  select greatest(
    project_updated_at,
    coalesce((select max(media.updated_at)
      from content_factory.media_objects media
      where media.organization_id = p_organization_id
        and media.project_id = p_project_id), project_updated_at),
    coalesce((select max(job.updated_at)
      from content_factory.generation_jobs job
      where job.organization_id = p_organization_id
        and job.project_id = p_project_id), project_updated_at),
    coalesce((select max(task.updated_at)
      from content_factory.creator_tasks task
      where task.organization_id = p_organization_id
        and task.project_id = p_project_id), project_updated_at),
    coalesce((select max(review.updated_at)
      from content_factory.content_review_runs review
      where review.organization_id = p_organization_id
        and review.project_id = p_project_id), project_updated_at),
    coalesce((select max(decision.created_at)
      from content_factory.content_review_decisions decision
      join content_factory.content_review_runs review
        on review.organization_id = decision.organization_id
       and review.id = decision.review_id
      where review.organization_id = p_organization_id
        and review.project_id = p_project_id), project_updated_at),
    coalesce((select max(placement.updated_at)
      from content_factory.placements placement
      where placement.organization_id = p_organization_id
        and placement.project_id = p_project_id), project_updated_at),
    coalesce((select max(metric.created_at)
      from content_factory.metric_snapshots metric
      join content_factory.placements placement
        on placement.organization_id = metric.organization_id
       and placement.id = metric.placement_id
      where placement.organization_id = p_organization_id
        and placement.project_id = p_project_id), project_updated_at)
  ) into snapshot_updated_at;

  if source_count = 0 then
    active_position := 1;
    active_stage := 'files';
    active_state := 'current';
    active_reason_code := 'source_media_required';
    active_reason := 'Добавьте хотя бы один готовый исходный материал.';
    entity_id_value := p_project_id;
    route_value := '/workspace/board?project_id=' || p_project_id::text
      || case when sources_folder_id is null then ''
         else '&folder=' || sources_folder_id::text end;
    next_action := jsonb_build_object(
      'code', 'add_source', 'stage', 'files',
      'label', 'Добавить исходник', 'route', route_value,
      'entity_type', 'workspace_project', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 20,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_job_status in ('failed', 'cancelled')
     or latest_job_output -> 'reconciliation_required' = 'true'::jsonb then
    active_position := 2;
    active_stage := 'generation';
    active_state := 'blocked';
    active_reason_code := case
      when latest_job_output -> 'reconciliation_required' = 'true'::jsonb
        then 'generation_reconciliation_required'
      when latest_job_status = 'cancelled' then 'generation_cancelled'
      else 'generation_failed'
    end;
    active_reason := case
      when latest_job_output -> 'reconciliation_required' = 'true'::jsonb
        then 'Состояние запуска нужно сверить с провайдером перед повтором.'
      else 'Запуск остановлен — исходник сохранён, начните один новый запуск.'
    end;
    if latest_job_output -> 'reconciliation_required' = 'true'::jsonb then
      entity_id_value := latest_job_id;
      route_value := '/workspace/generation?project_id=' || p_project_id::text
        || '&view=history&job=' || latest_job_id::text;
    elsif failed_job_source_media_id is not null then
      entity_id_value := failed_job_source_media_id;
      route_value := '/workspace/generation?project_id=' || p_project_id::text
        || '&view=create&media=' || failed_job_source_media_id::text;
    else
      entity_id_value := p_project_id;
      route_value := '/workspace/generation?project_id=' || p_project_id::text
        || '&view=create';
    end if;
    next_action := jsonb_build_object(
      'code', case
        when latest_job_output -> 'reconciliation_required' = 'true'::jsonb
          then 'resolve_generation'
        else 'retry_generation'
      end,
      'stage', 'generation',
      'label', case
        when latest_job_output -> 'reconciliation_required' = 'true'::jsonb
          then 'Проверить состояние запуска'
        else 'Повторить запуск'
      end,
      'route', route_value,
      'entity_type', case
        when latest_job_output -> 'reconciliation_required' = 'true'::jsonb
          then 'generation_job'
        when failed_job_source_media_id is not null then 'media_object'
        else 'workspace_project'
      end,
      'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 10,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_review_decision = 'needs_changes' then
    active_position := 2;
    active_stage := 'generation';
    active_state := 'current';
    active_reason_code := 'review_changes_required';
    active_reason := 'Проверка вернула материал на доработку.';
    entity_id_value := latest_review_id;
    route_value := '/workspace/generation?project_id=' || p_project_id::text
      || '&view=create&review=' || latest_review_id::text
      || case when latest_job_id is null then ''
         else '&job=' || latest_job_id::text end;
    next_action := jsonb_build_object(
      'code', 'repair_content', 'stage', 'generation',
      'label', 'Исправить контент', 'route', route_value,
      'entity_type', 'content_review_run', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 15,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif generated_count = 0 then
    active_position := 2;
    active_stage := 'generation';
    active_state := 'current';
    if latest_job_id is not null
       and latest_job_status in (
         'mock_ready', 'queued', 'starting', 'submitted', 'processing'
       ) then
      active_reason_code := 'generation_in_progress';
      active_reason := 'Текущий запуск ещё не выдал готовый материал.';
      entity_id_value := latest_job_id;
      route_value := '/workspace/generation?project_id=' || p_project_id::text
        || '&view=history&job=' || latest_job_id::text;
      next_action := jsonb_build_object(
        'code', 'open_generation', 'stage', 'generation',
        'label', 'Открыть текущую генерацию', 'route', route_value,
        'entity_type', 'generation_job', 'entity_id', entity_id_value,
        'project_id', p_project_id, 'priority', 20,
        'reason_code', active_reason_code, 'reason', active_reason
      );
    else
      active_reason_code := 'generation_required';
      active_reason := 'Исходник готов — создайте один вариант контента.';
      entity_id_value := source_media_id;
      route_value := '/workspace/generation?project_id=' || p_project_id::text
        || '&view=create&media=' || source_media_id::text;
      next_action := jsonb_build_object(
        'code', 'create_content', 'stage', 'generation',
        'label', 'Создать контент', 'route', route_value,
        'entity_type', 'media_object', 'entity_id', entity_id_value,
        'project_id', p_project_id, 'priority', 20,
        'reason_code', active_reason_code, 'reason', active_reason
      );
    end if;
  elsif unreviewed_media_id is not null then
    active_position := 3;
    active_stage := 'review';
    active_state := 'current';
    active_reason_code := 'content_review_required';
    active_reason := 'Готовый материал нужно проверить перед публикацией.';
    entity_id_value := unreviewed_media_id;
    route_value := '/workspace/review?project_id=' || p_project_id::text
      || '&view=new&media=' || unreviewed_media_id::text;
    next_action := jsonb_build_object(
      'code', 'start_review', 'stage', 'review',
      'label', 'Проверить контент', 'route', route_value,
      'entity_type', 'media_object', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 20,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_review_decision = 'rejected' then
    active_position := 2;
    active_stage := 'generation';
    active_state := 'current';
    active_reason_code := 'content_review_rejected';
    active_reason := 'Материал отклонён — создайте новую версию из исходника.';
    entity_id_value := source_media_id;
    route_value := '/workspace/generation?project_id=' || p_project_id::text
      || '&view=create&media=' || source_media_id::text;
    next_action := jsonb_build_object(
      'code', 'replace_rejected_content', 'stage', 'generation',
      'label', 'Создать новую версию', 'route', route_value,
      'entity_type', 'media_object', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 10,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_review_decision is distinct from 'approved' then
    active_position := 3;
    active_stage := 'review';
    active_state := 'current';
    active_reason_code := case
      when latest_review_status = 'completed' then 'review_decision_required'
      else 'content_review_in_progress'
    end;
    active_reason := case
      when latest_review_status = 'completed'
        then 'Анализ готов — сохраните решение по этому материалу.'
      else 'Проверка выполняется; откройте её текущий статус.'
    end;
    entity_id_value := latest_review_id;
    route_value := '/workspace/review?project_id=' || p_project_id::text
      || '&view=current&review=' || latest_review_id::text;
    next_action := jsonb_build_object(
      'code', 'open_review', 'stage', 'review',
      'label', case when latest_review_status = 'completed'
        then 'Принять решение' else 'Открыть проверку' end,
      'route', route_value,
      'entity_type', 'content_review_run', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 20,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif unplaced_review_id is not null then
    active_position := 4;
    active_stage := 'placement';
    active_state := 'blocked';
    active_reason_code := 'approved_placement_missing';
    active_reason := 'Материал одобрен, но точная публикация не создана.';
    entity_id_value := unplaced_review_id;
    route_value := '/workspace/review?project_id=' || p_project_id::text
      || '&view=current&review=' || unplaced_review_id::text
      || '&action=restore-placement';
    next_action := jsonb_build_object(
      'code', 'restore_placement', 'stage', 'placement',
      'label', 'Восстановить публикацию', 'route', route_value,
      'entity_type', 'content_review_run', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 10,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_placement_id is null then
    -- The approved item's placement exists, but this operator is not its
    -- assignee. Never manufacture a metric action with a NULL placement.
    active_position := 4;
    active_stage := 'placement';
    active_state := 'blocked';
    active_reason_code := 'placement_owned_by_teammate';
    active_reason := 'Публикация выполняется другим участником. Здесь можно проверить её статус.';
    entity_id_value := p_project_id;
    route_value := '/workspace/work?project_id=' || p_project_id::text;
    next_action := jsonb_build_object(
      'code', 'wait_for_placement', 'stage', 'placement',
      'label', 'Проверить статус публикации', 'route', route_value,
      'entity_type', 'workspace_project', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 40,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_placement_status in ('failed', 'cancelled') then
    active_position := 4;
    active_stage := 'placement';
    active_state := 'blocked';
    active_reason_code := 'placement_blocked';
    active_reason := 'Публикация остановлена; откройте точную карточку.';
    entity_id_value := latest_placement_id;
    route_value := '/workspace/placement?project_id=' || p_project_id::text
      || '&view=next&placement=' || latest_placement_id::text;
    next_action := jsonb_build_object(
      'code', 'resolve_placement', 'stage', 'placement',
      'label', 'Разобрать публикацию', 'route', route_value,
      'entity_type', 'placement', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 10,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_placement_status <> 'published' then
    active_position := 4;
    active_stage := 'placement';
    active_state := 'current';
    active_reason_code := 'placement_confirmation_required';
    active_reason := 'Материал одобрен — разместите и подтвердите точную ссылку.';
    entity_id_value := latest_placement_id;
    route_value := '/workspace/placement?project_id=' || p_project_id::text
      || '&view=next&placement=' || latest_placement_id::text;
    next_action := jsonb_build_object(
      'code', 'publish_content', 'stage', 'placement',
      'label', 'Опубликовать', 'route', route_value,
      'entity_type', 'placement', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 20,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  elsif latest_placement_metric_count = 0 then
    active_position := 5;
    active_stage := 'stats';
    active_state := 'current';
    active_reason_code := 'first_metric_snapshot_required';
    active_reason := 'Публикация подтверждена — зафиксируйте первый результат.';
    entity_id_value := latest_placement_id;
    route_value := '/workspace/stats?project_id=' || p_project_id::text
      || '&view=new&placement=' || latest_placement_id::text;
    next_action := jsonb_build_object(
      'code', 'record_metrics', 'stage', 'stats',
      'label', 'Добавить результат', 'route', route_value,
      'entity_type', 'placement', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 20,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  else
    flow_complete := true;
    active_position := 5;
    active_stage := 'stats';
    active_state := 'done';
    active_reason_code := 'project_flow_complete';
    active_reason := 'Маршрут завершён; результаты доступны в статистике.';
    entity_id_value := latest_placement_id;
    route_value := '/workspace/stats?project_id=' || p_project_id::text
      || '&placement=' || latest_placement_id::text;
    next_action := jsonb_build_object(
      'code', 'view_results', 'stage', 'stats',
      'label', 'Открыть результаты', 'route', route_value,
      'entity_type', 'placement', 'entity_id', entity_id_value,
      'project_id', p_project_id, 'priority', 50,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  end if;

  -- Select the task only after the server has determined the current stage.
  -- A high-priority task from a future/stale stage must not hide an exact task
  -- that the user can perform now.
  select task.id, task.task_type, task.status
  into actionable_task_id, actionable_task_type, actionable_task_status
  from content_factory.creator_tasks task
  where task.organization_id = p_organization_id
    and task.project_id = p_project_id
    and task.status in (
      'todo', 'in_progress', 'submitted', 'review', 'blocked'
    )
    and (manager_scope or task.status not in ('submitted', 'review'))
    and (manager_scope or task.assignee_id = p_user_id)
    and case task.task_type
      when 'video_review' then 'review'
      when 'placement' then 'placement'
      when 'metrics' then 'stats'
      else 'generation'
    end = active_stage
  order by case task.status
      when 'blocked' then 0
      when 'in_progress' then 1
      when 'review' then 2
      when 'todo' then 3
      else 4
    end,
    task.priority asc,
    task.due_at asc nulls last,
    task.updated_at asc,
    task.id asc
  limit 1;
  actionable_task_stage := case actionable_task_type
    when 'video_review' then 'review'
    when 'placement' then 'placement'
    when 'metrics' then 'stats'
    else 'generation'
  end;

  -- A task is an action inside a workflow stage, never a detached sixth stage.
  -- Expose one deterministic task only when it belongs to the stage that the
  -- server has already determined is current. This keeps the Dock/progress on
  -- the originating stage while making reload/new-tab recovery exact.
  if actionable_task_id is not null
     and actionable_task_stage = active_stage
     and not flow_complete then
    entity_id_value := actionable_task_id;
    route_value := '/workspace/tasks?project_id=' || p_project_id::text
      || '&view=next&origin_stage=' || active_stage
      || '&item=' || actionable_task_id::text;
    if actionable_task_status = 'blocked' then
      active_state := 'blocked';
      active_reason_code := 'assigned_task_blocked';
      active_reason := 'Назначенная задача заблокирована — откройте её и зафиксируйте причину.';
    else
      active_reason_code := 'assigned_task_required';
      active_reason := 'Выполните одно назначенное действие этого этапа.';
    end if;
    next_action := jsonb_build_object(
      'code', case when actionable_task_status = 'blocked'
        then 'resolve_task_blocker' else 'complete_assigned_task' end,
      'stage', active_stage,
      'label', case when actionable_task_status = 'blocked'
        then 'Разобрать блокер' else 'Выполнить задачу' end,
      'route', route_value,
      'entity_type', 'creator_task', 'entity_id', entity_id_value,
      'project_id', p_project_id,
      'priority', case when actionable_task_status = 'blocked' then 10 else 20 end,
      'reason_code', active_reason_code, 'reason', active_reason
    );
  end if;

  progress_percent := case when flow_complete then 100
    else (active_position - 1) * 20 end;
  counts_value := jsonb_build_object(
    'files', source_count,
    'generation_jobs', generation_job_count,
    'reviews', review_count,
    'actionable_tasks', actionable_task_count,
    'placements', placement_count,
    'metric_snapshots', metric_count,
    'queue', actionable_task_count
  );

  stages_value := jsonb_build_array(
    jsonb_build_object(
      'code', 'files', 'position', 1, 'label', 'Материалы',
      'state', case when flow_complete or active_position > 1 then 'done'
        when active_position = 1 then active_state else 'too_early' end,
      'count', source_count,
      'reason_code', case when active_position = 1 then active_reason_code
        when active_position > 1 or flow_complete then 'source_media_ready'
        else 'prior_stage_required' end,
      'reason', case when active_position = 1 then active_reason
        when active_position > 1 or flow_complete then 'Исходные материалы готовы.'
        else 'Сначала завершите предыдущий этап.' end,
      'route', '/workspace/board?project_id=' || p_project_id::text,
      'entity_type', 'workspace_project', 'entity_id', p_project_id
    ),
    jsonb_build_object(
      'code', 'generation', 'position', 2, 'label', 'Создание',
      'state', case when flow_complete or active_position > 2 then 'done'
        when active_position = 2 then active_state else 'too_early' end,
      'count', generation_job_count,
      'reason_code', case when active_position = 2 then active_reason_code
        when active_position > 2 or flow_complete then 'generated_media_ready'
        else 'source_media_required' end,
      'reason', case when active_position = 2 then active_reason
        when active_position > 2 or flow_complete then 'Готовый контент создан.'
        else 'Сначала добавьте исходный материал.' end,
      'route', '/workspace/generation?project_id=' || p_project_id::text,
      'entity_type', case when latest_job_id is null
        then 'workspace_project' else 'generation_job' end,
      'entity_id', coalesce(latest_job_id, p_project_id)
    ),
    jsonb_build_object(
      'code', 'review', 'position', 3, 'label', 'Проверка',
      'state', case when flow_complete or active_position > 3 then 'done'
        when active_position = 3 then active_state else 'too_early' end,
      'count', review_count,
      'reason_code', case when active_position = 3 then active_reason_code
        when active_position > 3 or flow_complete then 'content_approved'
        else 'generated_media_required' end,
      'reason', case when active_position = 3 then active_reason
        when active_position > 3 or flow_complete then 'Контент одобрен.'
        else 'Сначала создайте готовый контент.' end,
      'route', '/workspace/review?project_id=' || p_project_id::text,
      'entity_type', case when latest_review_id is null
        then 'media_object' else 'content_review_run' end,
      'entity_id', coalesce(latest_review_id, generated_media_id, p_project_id)
    ),
    jsonb_build_object(
      'code', 'placement', 'position', 4, 'label', 'Публикация',
      'state', case when flow_complete or active_position > 4 then 'done'
        when active_position = 4 then active_state else 'too_early' end,
      'count', placement_count,
      'reason_code', case when active_position = 4 then active_reason_code
        when active_position > 4 or flow_complete then 'placement_published'
        else 'content_approval_required' end,
      'reason', case when active_position = 4 then active_reason
        when active_position > 4 or flow_complete then 'Публикация подтверждена.'
        else 'Сначала получите одобрение проверки.' end,
      'route', '/workspace/placement?project_id=' || p_project_id::text,
      'entity_type', case when latest_placement_id is null
        then 'workspace_project' else 'placement' end,
      'entity_id', coalesce(latest_placement_id, p_project_id)
    ),
    jsonb_build_object(
      'code', 'stats', 'position', 5, 'label', 'Результаты',
      'state', case when flow_complete then 'done'
        when active_position = 5 then active_state else 'too_early' end,
      'count', metric_count,
      'reason_code', case when active_position = 5 then active_reason_code
        else 'published_placement_required' end,
      'reason', case when active_position = 5 then active_reason
        else 'Сначала подтвердите публикацию.' end,
      'route', '/workspace/stats?project_id=' || p_project_id::text,
      'entity_type', case when latest_placement_id is null
        then 'workspace_project' else 'placement' end,
      'entity_id', coalesce(latest_placement_id, p_project_id)
    )
  );

  return jsonb_build_object(
    'project', jsonb_build_object(
      'id', p_project_id,
      'name', project_name,
      'color_token', project_color,
      'status', project_status,
      'updated_at', snapshot_updated_at,
      'current_stage', active_stage,
      'progress_percent', progress_percent,
      'counts', counts_value,
      'next_action', next_action
    ),
    'stages', stages_value,
    'next_action', next_action,
    'counts', counts_value
  );
end;
$$;

create or replace function public.creator_project_flow(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
-- Canonical stage-state contract emitted by project_flow_snapshot:
-- current, blocked, done, too_early. Progress 100 means the flow is complete.
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  project_id_value uuid;
  include_projects boolean := true;
  selected_snapshot jsonb;
  projects_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'include_projects'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'project_flow_payload_invalid';
  end if;
  if p_payload ? 'include_projects' then
    if jsonb_typeof(p_payload -> 'include_projects') <> 'boolean' then
      raise exception using errcode = '22023', message = 'project_flow_include_projects_invalid';
    end if;
    include_projects := (p_payload ->> 'include_projects')::boolean;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  if nullif(btrim(coalesce(p_payload ->> 'project_id', '')), '') is not null then
    project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
    perform content_factory_private.require_workspace_project(
      organization_id, project_id_value
    );
    selected_snapshot := content_factory_private.project_flow_snapshot(
      organization_id, project_id_value, user_id, actor_role
    );
  end if;

  if include_projects then
    select coalesce(jsonb_agg(
      snapshot.value -> 'project'
      order by (snapshot.value #>> '{project,updated_at}')::timestamptz desc,
               project.id desc
    ), '[]'::jsonb)
    into projects_value
    from content_factory.workspace_folders project
    cross join lateral (
      select content_factory_private.project_flow_snapshot(
        organization_id, project.id, user_id, actor_role
      ) as value
    ) snapshot
    where project.organization_id = organization_id
      and project.kind = 'project'
      and project.status = 'active';
  end if;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'projects', projects_value,
    'project', selected_snapshot -> 'project',
    'stages', coalesce(selected_snapshot -> 'stages', '[]'::jsonb),
    'next_action', selected_snapshot -> 'next_action',
    'counts', coalesce(selected_snapshot -> 'counts', jsonb_build_object(
      'files', 0, 'generation_jobs', 0, 'reviews', 0,
      'actionable_tasks', 0, 'placements', 0,
      'metric_snapshots', 0, 'queue', 0
    ))
  );
end;
$$;

revoke all on function public.creator_project_flow(jsonb)
  from public, anon;
grant execute on function public.creator_project_flow(jsonb)
  to authenticated;

create or replace function public.creator_create_workspace_project(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  idempotency_key text;
  name_value text;
  color_value text := 'emerald';
  request_value jsonb;
  replay_value jsonb;
  result_value jsonb;
  project_id_value uuid;
  project_position bigint;
  folder_value record;
  folders_value jsonb;
  flow_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'name', 'color_token'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'workspace_project_create_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  name_value := content_factory_private.require_text(p_payload, 'name', 1, 120);
  if name_value ~ '[[:cntrl:]]' then
    raise exception using errcode = '22023', message = 'workspace_project_name_invalid';
  end if;
  if p_payload ? 'color_token' then
    color_value := lower(content_factory_private.require_text(
      p_payload, 'color_token', 3, 20
    ));
  end if;
  if color_value not in ('emerald', 'gold', 'rose', 'blue', 'violet', 'slate') then
    raise exception using errcode = '22023', message = 'workspace_project_color_invalid';
  end if;

  request_value := jsonb_build_object(
    'name', name_value, 'color_token', color_value,
    'folder_contract', 'project-default-folders-v1'
  );
  replay_value := content_factory_private.begin_command(
    organization_id, 'creator_create_workspace_project',
    idempotency_key, request_value
  );
  if replay_value is not null then return replay_value; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('workspace_structure')
  );
  if (select count(*) from content_factory.workspace_folders folder
      where folder.organization_id = organization_id
        and folder.status = 'active') > 494 then
    raise exception using errcode = '54000', message = 'workspace_active_folder_quota_exceeded';
  end if;
  if (select count(*) from content_factory.workspace_folders folder
      where folder.organization_id = organization_id) > 4994 then
    raise exception using errcode = '54000', message = 'workspace_total_folder_quota_exceeded';
  end if;

  select coalesce(max(project.position), 0) + 1024
  into project_position
  from content_factory.workspace_folders project
  where project.organization_id = organization_id
    and project.parent_id is null
    and project.status = 'active';

  insert into content_factory.workspace_folders (
    organization_id, parent_id, name, color_token, kind, system_role,
    status, position, created_by, updated_by
  ) values (
    organization_id, null, name_value, color_value, 'project', null,
    'active', project_position, user_id, user_id
  ) returning id into project_id_value;

  for folder_value in
    select * from (values
      ('sources', 'Исходники', 5120::bigint),
      ('drafts', 'Черновики', 4096::bigint),
      ('review', 'На проверке', 3072::bigint),
      ('ready', 'Готово', 2048::bigint),
      ('published', 'Опубликовано', 1024::bigint)
    ) roles(system_role, name, position)
  loop
    insert into content_factory.workspace_folders (
      organization_id, parent_id, name, color_token, kind, system_role,
      status, position, created_by, updated_by
    ) values (
      organization_id, project_id_value, folder_value.name, color_value,
      'folder', folder_value.system_role, 'active', folder_value.position,
      user_id, user_id
    );
  end loop;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', folder.id, 'project_id', project_id_value,
    'name', folder.name, 'system_role', folder.system_role,
    'color_token', folder.color_token, 'position', folder.position
  ) order by folder.position desc), '[]'::jsonb)
  into folders_value
  from content_factory.workspace_folders folder
  where folder.organization_id = organization_id
    and folder.parent_id = project_id_value
    and folder.status = 'active';

  flow_value := content_factory_private.project_flow_snapshot(
    organization_id, project_id_value, user_id, actor_role
  );
  result_value := jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'project', flow_value -> 'project',
    'folders', folders_value,
    'stages', flow_value -> 'stages',
    'next_action', flow_value -> 'next_action',
    'counts', flow_value -> 'counts',
    'flow', flow_value
  );
  perform content_factory_private.emit_event(
    organization_id, user_id, 'workspace_project_created',
    'workspace_project', project_id_value::text,
    jsonb_build_object('name', name_value, 'folder_contract', 'project-default-folders-v1'),
    'workspace-project:' || idempotency_key
  );
  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_create_workspace_project',
    idempotency_key, request_value, result_value
  );
end;
$$;

revoke all on function public.creator_create_workspace_project(jsonb)
  from public, anon;
grant execute on function public.creator_create_workspace_project(jsonb)
  to authenticated;

create or replace function public.creator_archive_workspace_project(
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
  expected_version_value bigint;
  idempotency_key text;
  request_value jsonb;
  replay_value jsonb;
  result_value jsonb;
  project_row content_factory.workspace_folders%rowtype;
  descendant record;
  previous_archive_context text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'project_id', 'expected_version'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'workspace_project_archive_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if coalesce(p_payload ->> 'expected_version', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'workspace_project_version_invalid';
  end if;
  begin
    expected_version_value := (p_payload ->> 'expected_version')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'workspace_project_version_invalid';
  end;
  if expected_version_value < 1 then
    raise exception using errcode = '22023', message = 'workspace_project_version_invalid';
  end if;

  request_value := jsonb_build_object(
    'project_id', project_id_value,
    'expected_version', expected_version_value
  );
  replay_value := content_factory_private.begin_command(
    organization_id, 'creator_archive_workspace_project',
    idempotency_key, request_value
  );
  if replay_value is not null then return replay_value; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('workspace_structure')
  );
  select project.* into project_row
  from content_factory.workspace_folders project
  where project.organization_id = organization_id
    and project.id = project_id_value
  for update;
  if project_row.id is null or project_row.kind <> 'project' then
    raise exception using errcode = 'P0002', message = 'workspace_project_not_found';
  end if;
  if project_row.status <> 'active' then
    raise exception using errcode = '55000', message = 'workspace_project_archived';
  end if;
  if project_row.version <> expected_version_value then
    raise exception using errcode = '40001', message = 'workspace_project_version_conflict';
  end if;

  previous_archive_context := current_setting(
    'contentengine.project_archive_id', true
  );
  perform set_config(
    'contentengine.project_archive_id', project_id_value::text, true
  );
  begin
    for descendant in
      with recursive project_tree as (
        select folder.id, folder.parent_id, 1 as depth
        from content_factory.workspace_folders folder
        where folder.organization_id = organization_id
          and folder.parent_id = project_id_value
          and folder.status = 'active'
        union all
        select folder.id, folder.parent_id, project_tree.depth + 1
        from project_tree
        join content_factory.workspace_folders folder
          on folder.organization_id = organization_id
         and folder.parent_id = project_tree.id
         and folder.status = 'active'
        where project_tree.depth < 8
      )
      select project_tree.id, project_tree.depth
      from project_tree
      order by project_tree.depth desc, project_tree.id
    loop
      update content_factory.workspace_folders folder
      set status = 'archived', archived_at = now(), updated_by = user_id
      where folder.organization_id = organization_id
        and folder.id = descendant.id
        and folder.status = 'active';
    end loop;

    update content_factory.workspace_folders project
    set status = 'archived', archived_at = now(), updated_by = user_id
    where project.organization_id = organization_id
      and project.id = project_id_value
    returning * into project_row;
  exception when others then
    perform set_config(
      'contentengine.project_archive_id',
      coalesce(previous_archive_context, ''), true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_archive_id',
    coalesce(previous_archive_context, ''), true
  );

  result_value := jsonb_build_object(
    'ok', true,
    'project_id', project_row.id,
    'project', jsonb_build_object(
      'id', project_row.id,
      'name', project_row.name,
      'status', project_row.status,
      'version', project_row.version,
      'archived_at', project_row.archived_at
    )
  );
  perform content_factory_private.emit_event(
    organization_id, user_id, 'workspace_project_archived',
    'workspace_project', project_row.id::text,
    jsonb_build_object('name', project_row.name, 'version', project_row.version),
    'workspace-project-archive:' || idempotency_key
  );
  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_archive_workspace_project',
    idempotency_key, request_value, result_value
  );
end;
$$;

revoke all on function public.creator_archive_workspace_project(jsonb)
  from public, anon;
grant execute on function public.creator_archive_workspace_project(jsonb)
  to authenticated;

-- Project-scoped compatibility wrappers keep legacy calls byte-for-byte intact:
-- project_id is interpreted only when the caller explicitly supplies it.
do $preserve_workspace_browser$
begin
  if to_regprocedure(
    'content_factory_private.creator_workspace_browser_pre_project_v47(jsonb)'
  ) is null then
    alter function public.creator_workspace_browser(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_workspace_browser(jsonb)
      rename to creator_workspace_browser_pre_project_v47;
  end if;
end;
$preserve_workspace_browser$;

revoke all on function
  content_factory_private.creator_workspace_browser_pre_project_v47(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_workspace_browser(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_organization_id uuid;
  project_id_value uuid;
  folder_id_value uuid;
  inner_payload jsonb;
  result_value jsonb;
  items_value jsonb;
  folders_value jsonb;
  current_folder_value jsonb;
  page_size_value integer;
  scan_payload jsonb;
  scan_result jsonb;
  scan_items jsonb;
  scan_filtered jsonb;
  scan_cursor jsonb;
  project_has_more boolean := false;
  project_next_cursor jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  v_organization_id := content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    v_organization_id, project_id_value
  );
  if nullif(btrim(coalesce(p_payload ->> 'folder_id', '')), '') is not null then
    folder_id_value := content_factory_private.require_uuid(p_payload, 'folder_id');
    if content_factory_private.workspace_project_for_folder(
         v_organization_id, folder_id_value
       ) is distinct from project_id_value then
      raise exception using errcode = '42501', message = 'workspace_folder_project_mismatch';
    end if;
    inner_payload := (p_payload - 'project_id')
      || jsonb_build_object('folder_id', folder_id_value);
  else
    -- Project scope and folder scope are independent: opening a project with
    -- no folder means "all project objects", just like Finder's All Objects.
    inner_payload := p_payload - 'project_id' - 'folder_id';
  end if;
  result_value :=
    content_factory_private.creator_workspace_browser_pre_project_v47(
      inner_payload
    );
  page_size_value := coalesce(
    (result_value #>> '{_meta,page_size}')::integer,
    50
  );
  items_value := '[]'::jsonb;
  scan_result := result_value;

  -- The legacy reader paginates the whole organization. Continue through its
  -- keyset pages until this project has a full page; filtering only the first
  -- legacy page can make a populated project look empty.
  loop
    scan_items := coalesce(scan_result -> 'items', '[]'::jsonb);
    select coalesce(jsonb_agg(
      item.value || jsonb_build_object('project_id', project_id_value)
      order by item.ordinality
    ), '[]'::jsonb)
    into scan_filtered
    from jsonb_array_elements(scan_items)
      with ordinality item(value, ordinality)
    where (
      item.value ->> 'type' = 'media'
      and exists (
        select 1 from content_factory.media_objects media
        where media.organization_id = v_organization_id
          and media.id::text = item.value ->> 'id'
          and media.project_id = project_id_value
      )
    ) or (
      item.value ->> 'type' = 'task'
      and exists (
        select 1 from content_factory.creator_tasks task
        where task.organization_id = v_organization_id
          and task.id::text = item.value ->> 'id'
          and task.project_id = project_id_value
      )
    );
    items_value := items_value || scan_filtered;
    exit when jsonb_array_length(items_value) > page_size_value;

    scan_cursor := scan_result #> '{_meta,next_cursor}';
    exit when scan_cursor is null
      or scan_cursor = 'null'::jsonb
      or not coalesce(
        (scan_result #>> '{_meta,has_more}')::boolean,
        false
      );
    scan_payload := (inner_payload - 'cursor') || jsonb_build_object(
      'page_size', 100,
      'cursor', scan_cursor
    );
    scan_result :=
      content_factory_private.creator_workspace_browser_pre_project_v47(
        scan_payload
      );
  end loop;

  project_has_more := jsonb_array_length(items_value) > page_size_value;
  select coalesce(
    jsonb_agg(item.value order by item.ordinality),
    '[]'::jsonb
  )
  into items_value
  from jsonb_array_elements(items_value)
    with ordinality item(value, ordinality)
  where item.ordinality <= page_size_value;
  if project_has_more then
    select item.value -> '_cursor'
      into project_next_cursor
    from jsonb_array_elements(items_value)
      with ordinality item(value, ordinality)
    order by item.ordinality desc
    limit 1;
  end if;
  result_value := jsonb_set(
    jsonb_set(
      result_value,
      '{_meta,has_more}',
      to_jsonb(project_has_more),
      true
    ),
    '{_meta,next_cursor}',
    coalesce(project_next_cursor, 'null'::jsonb),
    true
  );

  select coalesce(jsonb_agg(
    folder.value || jsonb_build_object(
      'project_id', project_id_value,
      'kind', folder_row.kind,
      'system_role', folder_row.system_role,
      'can_edit', folder_row.system_role is null
        and folder.value -> 'can_edit' is not distinct from 'true'::jsonb
    )
    order by folder.ordinality
  ), '[]'::jsonb)
  into folders_value
  from jsonb_array_elements(coalesce(result_value -> 'folders', '[]'::jsonb))
    with ordinality folder(value, ordinality)
  join content_factory.workspace_folders folder_row
    on folder_row.organization_id = v_organization_id
   and folder_row.id::text = folder.value ->> 'id'
  where content_factory_private.workspace_project_for_folder(
    v_organization_id, folder_row.id
  ) = project_id_value;

  if folder_id_value is not null then
    select coalesce(result_value -> 'current_folder', '{}'::jsonb)
      || jsonb_build_object(
        'project_id', project_id_value,
        'kind', folder.kind,
        'system_role', folder.system_role,
        'can_edit', folder.system_role is null
          and result_value #> '{current_folder,can_edit}'
            is not distinct from 'true'::jsonb
      )
    into current_folder_value
    from content_factory.workspace_folders folder
    where folder.organization_id = v_organization_id
      and folder.id = folder_id_value
      and folder.status = 'active';
  end if;

  return result_value
    || jsonb_build_object(
      'project_id', project_id_value,
      'current_folder_id', folder_id_value,
      'current_folder', current_folder_value,
      'items', items_value,
      'folders', folders_value
    );
end;
$$;

revoke all on function public.creator_workspace_browser(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_browser(jsonb)
  to authenticated;

do $preserve_workspace_section$
begin
  if to_regprocedure(
    'content_factory_private.creator_workspace_section_pre_project_v47(jsonb)'
  ) is null then
    alter function public.creator_workspace_section(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_workspace_section(jsonb)
      rename to creator_workspace_section_pre_project_v47;
  end if;
end;
$preserve_workspace_section$;

revoke all on function
  content_factory_private.creator_workspace_section_pre_project_v47(jsonb)
  from public, anon, authenticated;

create or replace function content_factory_private.project_workspace_collection_v47(
  p_organization_id uuid,
  p_project_id uuid,
  p_payload jsonb,
  p_initial_result jsonb,
  p_collection text,
  p_cursor_key text,
  p_entity_kind text
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  target_size integer := coalesce(
    (p_initial_result #>> '{_meta,page_size}')::integer,
    50
  );
  scan_size integer := coalesce(
    (p_initial_result #>> '{_meta,page_size}')::integer,
    50
  );
  scan_result jsonb := p_initial_result;
  scan_items jsonb;
  scan_filtered jsonb;
  collected jsonb := '[]'::jsonb;
  last_cursor jsonb;
  previous_cursor jsonb;
  cursor_map jsonb;
  scan_payload jsonb;
  scan_pages integer := 0;
begin
  loop
    scan_pages := scan_pages + 1;
    scan_items := coalesce(scan_result -> p_collection, '[]'::jsonb);
    select coalesce(
      jsonb_agg(
        item.value || jsonb_build_object('project_id', p_project_id)
        order by item.ordinality
      ),
      '[]'::jsonb
    )
    into scan_filtered
    from jsonb_array_elements(scan_items)
      with ordinality item(value, ordinality)
    where case p_entity_kind
      when 'batch' then exists (
        select 1 from content_factory.generation_batches batch
        where batch.organization_id = p_organization_id
          and batch.id::text = item.value ->> 'id'
          and batch.project_id = p_project_id
      )
      when 'media' then exists (
        select 1 from content_factory.media_objects media
        where media.organization_id = p_organization_id
          and media.id::text = item.value ->> 'id'
          and media.project_id = p_project_id
      )
      when 'placement' then exists (
        select 1 from content_factory.placements placement
        where placement.organization_id = p_organization_id
          and placement.id::text = item.value ->> 'id'
          and placement.project_id = p_project_id
      )
      when 'task' then exists (
        select 1 from content_factory.creator_tasks task
        where task.organization_id = p_organization_id
          and task.id::text = item.value ->> 'id'
          and task.project_id = p_project_id
      )
      when 'payout' then exists (
        select 1
        from content_factory.creator_payouts payout
        join content_factory.creator_tasks task
          on task.organization_id = payout.organization_id
         and task.id = payout.task_id
        where payout.organization_id = p_organization_id
          and payout.id::text = item.value ->> 'id'
          and task.project_id = p_project_id
      )
      else false
    end;
    collected := collected || scan_filtered;
    exit when jsonb_array_length(collected) >= target_size
      or jsonb_array_length(scan_items) < scan_size
      or jsonb_array_length(scan_items) = 0
      or scan_pages >= 20;

    previous_cursor := last_cursor;
    select item.value -> '_cursor'
      into last_cursor
    from jsonb_array_elements(scan_items)
      with ordinality item(value, ordinality)
    order by item.ordinality desc
    limit 1;
    exit when last_cursor is null
      or last_cursor = 'null'::jsonb
      or last_cursor = previous_cursor;

    cursor_map := coalesce(p_payload -> 'cursor', '{}'::jsonb)
      || jsonb_build_object(p_cursor_key, last_cursor);
    scan_payload := (p_payload - 'project_id' - 'cursor')
      || jsonb_build_object(
        'page_size', 100,
        'cursor', cursor_map
      );
    scan_result :=
      content_factory_private.creator_workspace_section_pre_project_v47(
        scan_payload
      );
    scan_size := 100;
  end loop;

  return coalesce((
    select jsonb_agg(item.value order by item.ordinality)
    from jsonb_array_elements(collected)
      with ordinality item(value, ordinality)
    where item.ordinality <= target_size
  ), '[]'::jsonb);
end;
$$;

revoke all on function
  content_factory_private.project_workspace_collection_v47(
    uuid, uuid, jsonb, jsonb, text, text, text
  ) from public, anon, authenticated;

create or replace function public.creator_workspace_section(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  user_id uuid;
  v_organization_id uuid;
  project_id_value uuid;
  section_value text;
  actor_role text;
  team_scope boolean;
  page_size_value integer := 50;
  result_value jsonb;
  filtered_value jsonb;
  summary_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  section_value := lower(btrim(coalesce(p_payload ->> 'section', '')));
  if not (p_payload ? 'project_id') then
    if section_value in ('team', 'feedback') then
      return content_factory_private.creator_workspace_section_pre_project_v47(
        p_payload
      );
    end if;
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  v_organization_id := content_factory_private.resolve_organization(p_payload);
  user_id := content_factory_private.current_profile_id();
  actor_role := content_factory_private.membership_role(
    v_organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);
  if p_payload ? 'page_size' then
    page_size_value := (p_payload ->> 'page_size')::integer;
  end if;
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    v_organization_id, project_id_value
  );
  if section_value in ('team', 'feedback') then
    raise exception using errcode = '22023', message = 'workspace_section_not_project_scoped';
  end if;
  if section_value = 'tasks'
     and p_payload ? 'cursor'
     and coalesce(p_payload -> 'cursor', 'null'::jsonb) <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'project_task_cursor_unsupported';
  end if;
  result_value :=
    content_factory_private.creator_workspace_section_pre_project_v47(
      p_payload - 'project_id'
    );

  -- Refill each project collection across the legacy organization-wide
  -- keyset pages before the response is shaped. This preserves the audited
  -- legacy query while making project pagination complete and deterministic.
  if section_value = 'generation' then
    result_value := jsonb_set(
      result_value,
      '{batches}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'batches', 'generation_batches', 'batch'
      ),
      true
    );
    result_value := jsonb_set(
      result_value,
      '{media}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'media', 'generation_media', 'media'
      ),
      true
    );
  elsif section_value = 'placement' then
    result_value := jsonb_set(
      result_value,
      '{placements}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'placements', 'placement_items', 'placement'
      ),
      true
    );
  elsif section_value = 'stats' then
    result_value := jsonb_set(
      result_value,
      '{publications}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'publications', 'stats_publications', 'placement'
      ),
      true
    );
    result_value := jsonb_set(
      result_value,
      '{publication_options}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'publication_options', 'stats_publication_options', 'placement'
      ),
      true
    );
  elsif section_value = 'tasks' then
    select coalesce(jsonb_agg(jsonb_build_object(
      'id', task.id,
      'project_id', project_id_value,
      'task_type', task.task_type,
      'title', task.title,
      'instructions', task.instructions,
      'status', task.status,
      'priority', task.priority,
      'payout_minor', task.payout_minor,
      'due_at', task.due_at,
      'checklist', coalesce(task.result -> 'checklist', '[]'::jsonb),
      'result', task.result,
      'submitted_at', task.submitted_at,
      'completed_at', task.completed_at,
      'created_at', task.created_at,
      'updated_at', task.updated_at,
      '_cursor', jsonb_build_object('at', task.created_at, 'id', task.id)
    ) order by
      case
        when task.status in ('todo', 'in_progress', 'blocked') then 0
        when team_scope and task.status in ('submitted', 'review') then 0
        else 1
      end,
      case task.status
        when 'blocked' then 0
        when 'in_progress' then 1
        when 'review' then 2
        when 'todo' then 3
        when 'submitted' then 4
        else 5
      end,
      task.priority asc,
      task.due_at asc nulls last,
      task.updated_at asc,
      task.id asc
    ), '[]'::jsonb)
    into filtered_value
    from (
      select candidate.*
      from content_factory.creator_tasks candidate
      where candidate.organization_id = v_organization_id
        and candidate.project_id = project_id_value
        and (team_scope or candidate.assignee_id = user_id)
      order by
        case
          when candidate.status in ('todo', 'in_progress', 'blocked') then 0
          when team_scope and candidate.status in ('submitted', 'review') then 0
          else 1
        end,
        case candidate.status
          when 'blocked' then 0
          when 'in_progress' then 1
          when 'review' then 2
          when 'todo' then 3
          when 'submitted' then 4
          else 5
        end,
        candidate.priority asc,
        candidate.due_at asc nulls last,
        candidate.updated_at asc,
        candidate.id asc
      limit page_size_value
    ) task;
    result_value := jsonb_set(
      result_value,
      '{tasks}',
      filtered_value,
      true
    );
  elsif section_value = 'media' then
    result_value := jsonb_set(
      result_value,
      '{media}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'media', 'media_items', 'media'
      ),
      true
    );
  elsif section_value = 'payouts' then
    result_value := jsonb_set(
      result_value,
      '{payouts}',
      content_factory_private.project_workspace_collection_v47(
        v_organization_id, project_id_value, p_payload, result_value,
        'payouts', 'payout_items', 'payout'
      ),
      true
    );
  end if;

  if section_value = 'generation' then
    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'batches', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.generation_batches batch
      where batch.organization_id = v_organization_id
        and batch.id::text = item.value ->> 'id'
        and batch.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{batches}', filtered_value, true);

    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'media', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.media_objects media
      where media.organization_id = v_organization_id
        and media.id::text = item.value ->> 'id'
        and media.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{media}', filtered_value, true);
  elsif section_value = 'placement' then
    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'placements', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.placements placement
      where placement.organization_id = v_organization_id
        and placement.id::text = item.value ->> 'id'
        and placement.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{placements}', filtered_value, true);
  elsif section_value = 'stats' then
    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'publications', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.placements placement
      where placement.organization_id = v_organization_id
        and placement.id::text = item.value ->> 'id'
        and placement.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{publications}', filtered_value, true);
    select jsonb_build_object(
      'published', count(*) filter (where item.value ->> 'status' = 'published'),
      'views', coalesce(sum((item.value ->> 'views')::bigint), 0),
      'clicks', coalesce(sum((item.value ->> 'clicks')::bigint), 0),
      'orders', coalesce(sum((item.value ->> 'orders')::bigint), 0),
      'revenue_minor', coalesce(sum((item.value ->> 'revenue_minor')::bigint), 0),
      'ctr', case when coalesce(sum((item.value ->> 'views')::bigint), 0) > 0
        then round(
          coalesce(sum((item.value ->> 'clicks')::bigint), 0)::numeric * 100
          / sum((item.value ->> 'views')::bigint), 2
        ) else 0 end
    ) into summary_value
    from jsonb_array_elements(filtered_value) item(value);
    result_value := jsonb_set(result_value, '{summary}', summary_value, true);

    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'publication_options', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.placements placement
      where placement.organization_id = v_organization_id
        and placement.id::text = item.value ->> 'id'
        and placement.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{publication_options}', filtered_value, true);
  elsif section_value = 'tasks' then
    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'tasks', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.creator_tasks task
      where task.organization_id = v_organization_id
        and task.id::text = item.value ->> 'id'
        and task.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{tasks}', filtered_value, true);
  elsif section_value = 'media' then
    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'media', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1 from content_factory.media_objects media
      where media.organization_id = v_organization_id
        and media.id::text = item.value ->> 'id'
        and media.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{media}', filtered_value, true);
  elsif section_value = 'payouts' then
    select coalesce(jsonb_agg(item.value || jsonb_build_object(
      'project_id', project_id_value
    ) order by item.ordinality), '[]'::jsonb)
    into filtered_value
    from jsonb_array_elements(coalesce(result_value -> 'payouts', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where exists (
      select 1
      from content_factory.creator_payouts payout
      join content_factory.creator_tasks task
        on task.organization_id = payout.organization_id
       and task.id = payout.task_id
      where payout.organization_id = v_organization_id
        and payout.id::text = item.value ->> 'id'
        and task.project_id = project_id_value
    );
    result_value := jsonb_set(result_value, '{payouts}', filtered_value, true);
  end if;
  return result_value || jsonb_build_object('project_id', project_id_value);
end;
$$;

revoke all on function public.creator_workspace_section(jsonb)
  from public, anon;
grant execute on function public.creator_workspace_section(jsonb)
  to authenticated;

do $preserve_my_work$
begin
  if to_regprocedure(
    'content_factory_private.creator_my_work_pre_project_v47(jsonb)'
  ) is null then
    alter function public.creator_my_work(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_my_work(jsonb)
      rename to creator_my_work_pre_project_v47;
  end if;
end;
$preserve_my_work$;

revoke all on function
  content_factory_private.creator_my_work_pre_project_v47(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_my_work(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_organization_id uuid;
  project_id_value uuid;
  result_value jsonb;
  items_value jsonb;
  counts_value jsonb;
  all_project_items jsonb := '[]'::jsonb;
  scan_payload jsonb;
  scan_result jsonb;
  scan_filtered jsonb;
  scan_cursor jsonb;
  page_candidates jsonb;
  page_size_value integer;
  cursor_updated_at timestamptz;
  cursor_item_type text;
  cursor_id uuid;
  project_has_more boolean := false;
  project_next_cursor jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  v_organization_id := content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    v_organization_id, project_id_value
  );
  result_value := content_factory_private.creator_my_work_pre_project_v47(
    p_payload - 'project_id'
  );
  page_size_value := coalesce(
    (result_value #>> '{_meta,page_size}')::integer,
    50
  );

  -- Counts describe the whole filtered project, not merely the visible page.
  -- Walk the legacy keyset from the beginning once, retain only this project's
  -- rows, then apply the caller's project cursor to that ordered collection.
  scan_payload := (p_payload - 'project_id' - 'cursor')
    || jsonb_build_object('page_size', 100);
  loop
    scan_result := content_factory_private.creator_my_work_pre_project_v47(
      scan_payload
    );
    select coalesce(jsonb_agg(item.value order by item.ordinality), '[]'::jsonb)
    into scan_filtered
    from jsonb_array_elements(coalesce(scan_result -> 'items', '[]'::jsonb))
      with ordinality item(value, ordinality)
    where case item.value ->> 'item_type'
      when 'task' then exists (
        select 1 from content_factory.creator_tasks task
        where task.organization_id = v_organization_id
          and task.id::text = item.value ->> 'id'
          and task.project_id = project_id_value
      )
      when 'generation' then exists (
        select 1 from content_factory.generation_jobs job
        where job.organization_id = v_organization_id
          and job.id::text = item.value ->> 'id'
          and job.project_id = project_id_value
      )
      when 'review' then exists (
        select 1 from content_factory.content_review_runs review
        where review.organization_id = v_organization_id
          and review.id::text = item.value ->> 'id'
          and review.project_id = project_id_value
      )
      when 'placement' then exists (
        select 1 from content_factory.placements placement
        where placement.organization_id = v_organization_id
          and placement.id::text = item.value ->> 'id'
          and placement.project_id = project_id_value
      )
      when 'payout' then exists (
        select 1
        from content_factory.creator_payouts payout
        join content_factory.creator_tasks task
          on task.organization_id = payout.organization_id
         and task.id = payout.task_id
        where payout.organization_id = v_organization_id
          and payout.id::text = item.value ->> 'id'
          and task.project_id = project_id_value
      ) else false
    end;
    all_project_items := all_project_items || scan_filtered;
    scan_cursor := scan_result -> 'next_cursor';
    exit when scan_cursor is null or scan_cursor = 'null'::jsonb;
    scan_payload := (scan_payload - 'cursor')
      || jsonb_build_object('cursor', scan_cursor);
  end loop;

  if p_payload ? 'cursor' then
    cursor_updated_at :=
      (p_payload #>> '{cursor,updated_at}')::timestamptz;
    cursor_item_type := lower(btrim(
      p_payload #>> '{cursor,item_type}'
    ));
    cursor_id := (p_payload #>> '{cursor,id}')::uuid;
  end if;
  select coalesce(jsonb_agg(candidate.value order by candidate.ordinality), '[]'::jsonb)
  into page_candidates
  from (
    select item.value, item.ordinality
    from jsonb_array_elements(all_project_items)
      with ordinality item(value, ordinality)
    where cursor_updated_at is null
      or (
        (item.value ->> 'updated_at')::timestamptz,
        item.value ->> 'item_type',
        (item.value ->> 'id')::uuid
      ) < (cursor_updated_at, cursor_item_type, cursor_id)
    order by item.ordinality
    limit page_size_value + 1
  ) candidate;
  project_has_more := jsonb_array_length(page_candidates) > page_size_value;

  select coalesce(jsonb_agg(
    item.value || jsonb_build_object(
      'project_id', project_id_value,
      'deep_link', case item.value ->> 'item_type'
        when 'task' then '#/workspace/tasks?project_id=' || project_id_value::text
          || '&item=' || (item.value ->> 'id')
        when 'generation' then '#/workspace/generation?project_id=' || project_id_value::text
          || '&job=' || (item.value ->> 'id')
        when 'review' then '#/workspace/review?project_id=' || project_id_value::text
          || '&review=' || (item.value ->> 'id')
        when 'placement' then '#/workspace/placement?project_id=' || project_id_value::text
          || '&placement=' || (item.value ->> 'id')
        when 'payout' then '#/workspace/payouts?project_id=' || project_id_value::text
          || '&payout=' || (item.value ->> 'id')
      end
    ) order by item.ordinality
  ), '[]'::jsonb)
  into items_value
  from jsonb_array_elements(page_candidates)
    with ordinality item(value, ordinality)
  where item.ordinality <= page_size_value;

  if project_has_more then
    select jsonb_build_object(
      'updated_at', item.value ->> 'updated_at',
      'item_type', item.value ->> 'item_type',
      'id', item.value ->> 'id'
    )
    into project_next_cursor
    from jsonb_array_elements(items_value)
      with ordinality item(value, ordinality)
    order by item.ordinality desc
    limit 1;
  end if;

  select jsonb_build_object(
    'total', count(*),
    'task', count(*) filter (where item.value ->> 'item_type' = 'task'),
    'generation', count(*) filter (where item.value ->> 'item_type' = 'generation'),
    'review', count(*) filter (where item.value ->> 'item_type' = 'review'),
    'placement', count(*) filter (where item.value ->> 'item_type' = 'placement'),
    'payout', count(*) filter (where item.value ->> 'item_type' = 'payout'),
    'action_required', count(*) filter (
      where item.value -> 'action_required' = 'true'::jsonb
    ),
    'blockers', count(*) filter (
      where item.value -> 'blocker' = 'true'::jsonb
    ),
    'overdue', count(*) filter (
      where item.value -> 'overdue' = 'true'::jsonb
    )
  ) into counts_value
  from jsonb_array_elements(all_project_items) item(value);

  return result_value || jsonb_build_object(
    'project_id', project_id_value,
    'items', items_value,
    'counts', counts_value,
    'next_cursor', project_next_cursor
  );
end;
$$;

revoke all on function public.creator_my_work(jsonb)
  from public, anon;
grant execute on function public.creator_my_work(jsonb)
  to authenticated;

-- The catalog's original query owns its authorization and both LIMIT clauses.
-- Make that lowest layer project-aware through a transaction-local context so
-- every later assignment/repair/media-context wrapper still runs unchanged,
-- while project filtering happens before either LIMIT.
create or replace function
  content_factory_private.creator_content_review_catalog_without_assignments(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  manager_scope boolean;
  project_id_value uuid;
  project_setting text;
  media_limit_value integer := 50;
  run_limit_value integer := 50;
  media_value jsonb;
  runs_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'media_limit', 'run_limit'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'content_review_catalog_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  project_setting := nullif(
    current_setting('contentengine.project_id', true),
    ''
  );
  if project_setting is not null then
    begin
      project_id_value := project_setting::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023',
        message = 'workspace_project_context_invalid';
    end;
  end if;

  if p_payload ? 'media_limit' then
    if coalesce(p_payload ->> 'media_limit', '') !~ '^[0-9]{1,3}$' then
      raise exception using
        errcode = '22023',
        message = 'content_review_media_limit_invalid';
    end if;
    media_limit_value := (p_payload ->> 'media_limit')::integer;
  end if;
  if p_payload ? 'run_limit' then
    if coalesce(p_payload ->> 'run_limit', '') !~ '^[0-9]{1,3}$' then
      raise exception using
        errcode = '22023',
        message = 'content_review_run_limit_invalid';
    end if;
    run_limit_value := (p_payload ->> 'run_limit')::integer;
  end if;
  if media_limit_value not between 1 and 100
     or run_limit_value not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'content_review_catalog_limit_invalid';
  end if;

  select coalesce(
    jsonb_agg(item.value order by item.created_at desc, item.id desc),
    '[]'::jsonb
  )
  into media_value
  from (
    select media.id, media.created_at, jsonb_build_object(
      'id', media.id,
      'owner_id', media.owner_id,
      'task_id', media.task_id,
      'product_id', media.product_id,
      'object_name', media.object_name,
      'mime_type', media.mime_type,
      'size_bytes', media.size_bytes,
      'sha256', media.sha256,
      'metadata', media.metadata,
      'created_at', media.created_at
    ) as value
    from content_factory.media_objects media
    left join content_factory.creator_tasks task
      on task.organization_id = media.organization_id
     and task.id = media.task_id
    where media.organization_id = organization_id
      and (project_id_value is null or media.project_id = project_id_value)
      and media.status = 'ready'
      and media.mime_type in (
        'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
      )
      and (
        manager_scope
        or media.owner_id = user_id
        or task.assignee_id = user_id
      )
    order by media.created_at desc, media.id desc
    limit media_limit_value
  ) item;

  select coalesce(
    jsonb_agg(item.value order by item.created_at desc, item.id desc),
    '[]'::jsonb
  )
  into runs_value
  from (
    select review.id, review.created_at, jsonb_build_object(
      'id', review.id,
      'media_id', review.media_object_id,
      'requested_by', review.requested_by,
      'requested_by_name', coalesce(profile.display_name, profile.email),
      'parent_review_id', review.parent_review_id,
      'status', review.status,
      'platform', review.input ->> 'platform',
      'product_category', review.input ->> 'product_category',
      'content_kind', review.input ->> 'content_kind',
      'ruleset_version', review.ruleset_version,
      'media_sha256_snapshot', review.media_sha256_snapshot,
      'media_is_stale', (
        media.status <> 'ready'
        or media.sha256 <> review.media_sha256_snapshot
      ),
      'result_summary', jsonb_build_object(
        'overall_score', review.result -> 'overall_score',
        'compliance_status', review.result -> 'compliance_status',
        'blockers_count', review.result -> 'blockers_count',
        'warnings_count', review.result -> 'warnings_count',
        'comparison', review.result -> 'comparison'
      ),
      'error_code', review.error_code,
      'created_at', review.created_at,
      'finished_at', review.finished_at,
      'decision', case
        when decision.id is null then null
        else jsonb_build_object(
          'id', decision.id,
          'decision', decision.decision,
          'comment', decision.comment,
          'reason', decision.comment,
          'media_watched_confirmed', decision.media_watched_confirmed,
          'decided_by', decision.decided_by,
          'decided_by_name', coalesce(decider.display_name, decider.email),
          'created_at', decision.created_at
        )
      end
    ) as value
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    left join content_factory.creator_tasks task
      on task.organization_id = media.organization_id
     and task.id = media.task_id
    join content_factory.profiles profile
      on profile.id = review.requested_by
    left join content_factory.content_review_decisions decision
      on decision.organization_id = review.organization_id
     and decision.review_id = review.id
    left join content_factory.profiles decider
      on decider.id = decision.decided_by
    where review.organization_id = organization_id
      and (project_id_value is null or review.project_id = project_id_value)
      and (
        manager_scope
        or review.requested_by = user_id
        or media.owner_id = user_id
        or task.assignee_id = user_id
      )
    order by review.created_at desc, review.id desc
    limit run_limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    'ruleset', jsonb_build_object(
      'version', 'ru-content-compliance-2026-07-16.1',
      'jurisdiction', 'RU',
      'human_legal_review_required', true
    ),
    'role', actor_role,
    'media', media_value,
    'recent_reviews', runs_value,
    'options', jsonb_build_object(
      'platforms', jsonb_build_array(
        'instagram', 'youtube', 'vk', 'telegram',
        'wildberries', 'tiktok', 'other'
      ),
      'product_categories', jsonb_build_array(
        'cosmetics', 'baa', 'sports_food', 'food',
        'household', 'apparel', 'electronics', 'other'
      ),
      'content_kinds', jsonb_build_array(
        'unknown', 'informational', 'advertising'
      )
    )
  );
end;
$$;

revoke all on function
  content_factory_private.creator_content_review_catalog_without_assignments(
    jsonb
  ) from public, anon, authenticated, service_role;

do $preserve_review_catalog$
begin
  if to_regprocedure(
    'content_factory_private.creator_content_review_catalog_pre_project_v47(jsonb)'
  ) is null then
    alter function public.creator_content_review_catalog(jsonb)
      set schema content_factory_private;
    alter function content_factory_private.creator_content_review_catalog(jsonb)
      rename to creator_content_review_catalog_pre_project_v47;
  end if;
end;
$preserve_review_catalog$;

revoke all on function
  content_factory_private.creator_content_review_catalog_pre_project_v47(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_content_review_catalog(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_organization_id uuid;
  project_id_value uuid;
  result_value jsonb;
  media_value jsonb;
  reviews_value jsonb;
  previous_project_setting text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  v_organization_id := content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    v_organization_id, project_id_value
  );
  previous_project_setting := current_setting(
    'contentengine.project_id',
    true
  );
  perform set_config(
    'contentengine.project_id',
    project_id_value::text,
    true
  );
  begin
    result_value :=
      content_factory_private.creator_content_review_catalog_pre_project_v47(
        p_payload - 'project_id'
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''),
    true
  );
  select coalesce(jsonb_agg(item.value || jsonb_build_object(
    'project_id', project_id_value
  ) order by item.ordinality), '[]'::jsonb)
  into media_value
  from jsonb_array_elements(coalesce(result_value -> 'media', '[]'::jsonb))
    with ordinality item(value, ordinality)
  where exists (
    select 1 from content_factory.media_objects media
    where media.organization_id = v_organization_id
      and media.id::text = item.value ->> 'id'
      and media.project_id = project_id_value
  );
  select coalesce(jsonb_agg(item.value || jsonb_build_object(
    'project_id', project_id_value
  ) order by item.ordinality), '[]'::jsonb)
  into reviews_value
  from jsonb_array_elements(coalesce(result_value -> 'recent_reviews', '[]'::jsonb))
    with ordinality item(value, ordinality)
  where exists (
    select 1 from content_factory.content_review_runs review
    where review.organization_id = v_organization_id
      and review.id::text = item.value ->> 'id'
      and review.project_id = project_id_value
  );
  return result_value || jsonb_build_object(
    'project_id', project_id_value,
    'media', media_value,
    'recent_reviews', reviews_value
  );
end;
$$;

revoke all on function public.creator_content_review_catalog(jsonb)
  from public, anon;
grant execute on function public.creator_content_review_catalog(jsonb)
  to authenticated;

create or replace function content_factory_private.require_project_entity(
  p_organization_id uuid,
  p_project_id uuid,
  p_entity_kind text,
  p_entity_id uuid
)
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  found_value boolean := false;
begin
  perform content_factory_private.require_workspace_project(
    p_organization_id, p_project_id
  );
  if p_entity_id is null then
    raise exception using errcode = '22023', message = 'project_entity_id_invalid';
  end if;
  if p_entity_kind = 'media' then
    select exists (
      select 1 from content_factory.media_objects media
      where media.organization_id = p_organization_id
        and media.id = p_entity_id
        and media.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'review' then
    select exists (
      select 1 from content_factory.content_review_runs review
      where review.organization_id = p_organization_id
        and review.id = p_entity_id
        and review.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'placement' then
    select exists (
      select 1 from content_factory.placements placement
      where placement.organization_id = p_organization_id
        and placement.id = p_entity_id
        and placement.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'placement_or_task' then
    select exists (
      select 1 from content_factory.placements placement
      where placement.organization_id = p_organization_id
        and (placement.id = p_entity_id or placement.task_id = p_entity_id)
        and placement.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'task' then
    select exists (
      select 1 from content_factory.creator_tasks task
      where task.organization_id = p_organization_id
        and task.id = p_entity_id
        and task.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'job' then
    select exists (
      select 1 from content_factory.generation_jobs job
      where job.organization_id = p_organization_id
        and job.id = p_entity_id
        and job.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'evidence' then
    select exists (
      select 1
      from content_factory.content_review_evidence_sets evidence
      join content_factory.media_objects media
        on media.organization_id = evidence.organization_id
       and media.id = evidence.media_object_id
      where evidence.organization_id = p_organization_id
        and evidence.id = p_entity_id
        and media.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'payout' then
    select exists (
      select 1
      from content_factory.creator_payouts payout
      join content_factory.creator_tasks task
        on task.organization_id = payout.organization_id
       and task.id = payout.task_id
      where payout.organization_id = p_organization_id
        and payout.id = p_entity_id
        and task.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'research_run' then
    select exists (
      select 1 from content_factory.product_research_runs run
      where run.organization_id = p_organization_id
        and run.id = p_entity_id
        and run.project_id = p_project_id
    ) into found_value;
  elsif p_entity_kind = 'creative_brief_draft' then
    select exists (
      select 1
      from content_factory.creative_brief_drafts draft
      join content_factory.product_research_runs run
        on run.organization_id = draft.organization_id
       and run.id = draft.run_id
       and run.project_id = p_project_id
      where draft.organization_id = p_organization_id
        and draft.id = p_entity_id
        and draft.project_id = p_project_id
    ) into found_value;
  else
    raise exception using errcode = '22023', message = 'project_entity_kind_invalid';
  end if;
  if not found_value then
    raise exception using errcode = '42501', message = 'project_entity_mismatch';
  end if;
  return p_entity_id;
end;
$$;

do $preserve_project_mutations$
declare
  function_name text;
  alias_name text;
begin
  foreach function_name in array array[
    'creator_start_content_review',
    'creator_start_generated_video_review',
    'creator_content_review_status',
    'creator_decide_content_review',
    'creator_approve_generated_photo_review_with_context',
    'creator_approve_generated_video_review_with_context',
    'creator_create_mock_batch',
    'creator_start_real_generation',
    'creator_real_generation_status',
    'creator_register_media',
    'creator_confirm_placement',
    'creator_record_metric',
    'creator_transition_task',
    'creator_configure_tracking_link',
    'creator_generation_repair_policy',
    'creator_generation_learning_policy',
    'creator_decide_payout',
    'creator_generation_media_identity',
    'creator_prepare_content_review_evidence',
    'creator_commit_content_review_evidence',
    'creator_real_generation_reconciliation_context'
  ] loop
    alias_name := function_name || '_pre_project_v47';
    if to_regprocedure(
      'content_factory_private.' || alias_name || '(jsonb)'
    ) is null then
      execute format(
        'alter function public.%I(jsonb) rename to %I',
        function_name, alias_name
      );
      execute format(
        'alter function public.%I(jsonb) set schema content_factory_private',
        alias_name
      );
    end if;
    execute format(
      'revoke all on function content_factory_private.%I(jsonb) '
      || 'from public, anon, authenticated',
      alias_name
    );
  end loop;
end;
$preserve_project_mutations$;

-- Three preserved review mutations predate the six-argument command receipt
-- contract and still call finish_command with four arguments. Repair their
-- installed definitions after the rename so actor and request hashes remain
-- authoritative; a compatibility overload would silently weaken idempotency.
do $repair_preserved_command_receipts_v47$
declare
  alias_name text;
  function_oid oid;
  function_definition text;
  repaired_definition text;
  legacy_finish_pattern constant text :=
    $finish_pattern$perform[[:space:]]+content_factory_private[.]finish_command[(][[:space:]]*organization_id,[[:space:]]*('[^']+'),[[:space:]]*idempotency_key_value,[[:space:]]*result_value[[:space:]]*[)];$finish_pattern$;
  repaired_finish_pattern constant text :=
    $finish_pattern$perform[[:space:]]+content_factory_private[.]finish_command[(][[:space:]]*organization_id,[[:space:]]*user_id,[[:space:]]*'[^']+',[[:space:]]*idempotency_key_value,[[:space:]]*request_payload,[[:space:]]*result_value[[:space:]]*[)];$finish_pattern$;
begin
  foreach alias_name in array array[
    'creator_approve_generated_photo_review_with_context_pre_project_v47',
    'creator_start_generated_video_review_pre_project_v47',
    'creator_approve_generated_video_review_with_context_pre_project_v47'
  ] loop
    select proc.oid
      into function_oid
    from pg_catalog.pg_proc proc
    join pg_catalog.pg_namespace namespace
      on namespace.oid = proc.pronamespace
    where namespace.nspname = 'content_factory_private'
      and proc.proname = left(alias_name, 63)
      and proc.pronargs = 1
      and proc.proargtypes[0] = 'pg_catalog.jsonb'::pg_catalog.regtype::oid
    order by proc.oid desc
    limit 1;

    if function_oid is null then
      raise exception using
        errcode = '55000',
        message = 'project_preserved_command_not_found';
    end if;

    function_definition := pg_catalog.pg_get_functiondef(function_oid);
    repaired_definition := pg_catalog.regexp_replace(
      function_definition,
      legacy_finish_pattern,
      $finish_replacement$perform content_factory_private.finish_command(
    organization_id,
    user_id,
    \1,
    idempotency_key_value,
    request_payload,
    result_value
  );$finish_replacement$,
      'i'
    );
    if repaired_definition = function_definition then
      if function_definition !~* repaired_finish_pattern then
        raise exception using
          errcode = '55000',
          message = 'project_preserved_command_repair_failed';
      end if;
      continue;
    end if;
    execute repaired_definition;
  end loop;
end;
$repair_preserved_command_receipts_v47$;

create or replace function content_factory_private.call_project_scoped_v47(
  p_alias_name text,
  p_payload jsonb,
  p_entity_kind text default null,
  p_entity_field text default null,
  p_media_list boolean default false
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  allowed_aliases constant text[] := array[
    'creator_start_content_review_pre_project_v47',
    'creator_start_generated_video_review_pre_project_v47',
    'creator_content_review_status_pre_project_v47',
    'creator_decide_content_review_pre_project_v47',
    'creator_approve_generated_photo_review_with_context_pre_project_v47',
    'creator_approve_generated_video_review_with_context_pre_project_v47',
    'creator_create_mock_batch_pre_project_v47',
    'creator_start_real_generation_pre_project_v47',
    'creator_real_generation_status_pre_project_v47',
    'creator_register_media_pre_project_v47',
    'creator_confirm_placement_pre_project_v47',
    'creator_record_metric_pre_project_v47',
    'creator_transition_task_pre_project_v47',
    'creator_configure_tracking_link_pre_project_v47',
    'creator_generation_repair_policy_pre_project_v47',
    'creator_generation_learning_policy_pre_project_v47',
    'creator_decide_payout_pre_project_v47',
    'creator_generation_media_identity_pre_project_v47',
    'creator_prepare_content_review_evidence_pre_project_v47',
    'creator_commit_content_review_evidence_pre_project_v47',
    'creator_real_generation_reconciliation_context_pre_project_v47'
  ];
  v_organization_id uuid;
  project_id_value uuid;
  entity_id_value uuid;
  inner_payload jsonb;
  result_value jsonb;
  media_ids_value jsonb;
  previous_project_setting text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if not (p_alias_name = any(allowed_aliases)) then
    raise exception using errcode = '42501', message = 'project_scoped_function_not_allowed';
  end if;
  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;

  v_organization_id := content_factory_private.resolve_organization(p_payload);
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  perform content_factory_private.require_workspace_project(
    v_organization_id, project_id_value
  );
  if p_entity_kind is not null then
    entity_id_value := content_factory_private.require_uuid(
      p_payload, p_entity_field
    );
    perform content_factory_private.require_project_entity(
      v_organization_id, project_id_value, p_entity_kind, entity_id_value
    );
  end if;
  if p_media_list then
    media_ids_value := coalesce(p_payload -> 'media_ids', '[]'::jsonb);
    if jsonb_typeof(media_ids_value) = 'array'
       and exists (
         select 1
         from jsonb_array_elements_text(media_ids_value) item(value)
         where not exists (
           select 1 from content_factory.media_objects media
           where media.organization_id = v_organization_id
             and media.id::text = item.value
             and media.project_id = project_id_value
             and media.status = 'ready'
         )
       ) then
      raise exception using errcode = '42501', message = 'project_media_scope_mismatch';
    end if;
  end if;

  previous_project_setting := current_setting(
    'contentengine.project_id',
    true
  );
  perform set_config('contentengine.project_id', project_id_value::text, true);
  inner_payload := p_payload - 'project_id';
  begin
    execute format(
      'select content_factory_private.%I($1)', p_alias_name
    ) into result_value using inner_payload;
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''),
    true
  );
  if jsonb_typeof(result_value) <> 'object' then
    raise exception using errcode = '55000', message = 'project_scoped_result_invalid';
  end if;
  -- Register-media can replay an older idempotent result before running an
  -- INSERT (and therefore before the lineage trigger). Verify the exact row
  -- returned by the preserved function instead of trusting response markup.
  if p_alias_name = 'creator_register_media_pre_project_v47' then
    begin
      entity_id_value := (result_value #>> '{media,id}')::uuid;
    exception when invalid_text_representation or null_value_not_allowed then
      raise exception using
        errcode = '55000', message = 'project_scoped_result_invalid';
    end;
    perform content_factory_private.require_project_entity(
      v_organization_id, project_id_value, 'media', entity_id_value
    );
  end if;
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );
  if jsonb_typeof(result_value -> 'media') = 'object' then
    result_value := jsonb_set(
      result_value, '{media,project_id}', to_jsonb(project_id_value), true
    );
  end if;
  if jsonb_typeof(result_value -> 'run') = 'object' then
    result_value := jsonb_set(
      result_value, '{run,project_id}', to_jsonb(project_id_value), true
    );
  end if;
  if jsonb_typeof(result_value -> 'review') = 'object' then
    result_value := jsonb_set(
      result_value, '{review,project_id}', to_jsonb(project_id_value), true
    );
  end if;
  if jsonb_typeof(result_value -> 'job') = 'object' then
    result_value := jsonb_set(
      result_value, '{job,project_id}', to_jsonb(project_id_value), true
    );
  end if;
  if jsonb_typeof(result_value -> 'batch') = 'object' then
    result_value := jsonb_set(
      result_value, '{batch,project_id}', to_jsonb(project_id_value), true
    );
  end if;
  if jsonb_typeof(result_value -> 'placement') = 'object' then
    result_value := jsonb_set(
      result_value, '{placement,project_id}', to_jsonb(project_id_value), true
    );
  end if;
  return result_value;
end;
$$;

create or replace function content_factory_private.project_payload_from_context_v47(
  p_payload jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  context_value text;
  context_project_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload ? 'project_id' then
    return p_payload;
  end if;
  context_value := nullif(
    current_setting('contentengine.project_id', true),
    ''
  );
  if context_value is null then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  begin
    context_project_id := context_value::uuid;
  exception when invalid_text_representation then
    raise exception using errcode = '22023', message = 'project_context_invalid';
  end;
  return p_payload || jsonb_build_object('project_id', context_project_id);
end;
$$;

create or replace function public.creator_start_content_review(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_start_content_review_pre_project_v47', p_payload,
    'media', 'media_id', false
  )
$$;

create or replace function public.creator_start_generated_video_review(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_start_generated_video_review_pre_project_v47', p_payload,
    'media', 'media_id', false
  )
$$;

create or replace function public.creator_content_review_status(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_content_review_status_pre_project_v47', p_payload,
    'review', 'review_id', false
  )
$$;

create or replace function public.creator_decide_content_review(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_decide_content_review_pre_project_v47', p_payload,
    'review', 'review_id', false
  )
$$;

create or replace function public.creator_approve_generated_photo_review_with_context(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_approve_generated_photo_review_with_context_pre_project_v47',
    p_payload, 'review', 'review_id', false
  )
$$;

create or replace function public.creator_approve_generated_video_review_with_context(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_approve_generated_video_review_with_context_pre_project_v47',
    p_payload, 'review', 'review_id', false
  )
$$;

create or replace function public.creator_create_mock_batch(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_create_mock_batch_pre_project_v47', p_payload,
    null, null, true
  )
$$;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_start_real_generation_pre_project_v47', p_payload,
    null, null, true
  )
$$;

create or replace function public.creator_real_generation_status(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_real_generation_status_pre_project_v47', p_payload,
    'job', 'job_id', false
  )
$$;

create or replace function public.creator_register_media(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_register_media_pre_project_v47', p_payload,
    null, null, false
  )
$$;

create or replace function public.creator_confirm_placement(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_confirm_placement_pre_project_v47', p_payload,
    'placement_or_task', 'task_id', false
  )
$$;

create or replace function public.creator_record_metric(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_record_metric_pre_project_v47', p_payload,
    'placement', 'placement_id', false
  )
$$;

create or replace function public.creator_transition_task(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_transition_task_pre_project_v47', p_payload,
    'task', 'task_id', false
  )
$$;

create or replace function public.creator_configure_tracking_link(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_configure_tracking_link_pre_project_v47', p_payload,
    'placement', 'placement_id', false
  )
$$;

create or replace function public.creator_generation_repair_policy(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_generation_repair_policy_pre_project_v47',
    content_factory_private.project_payload_from_context_v47(p_payload),
    'review', 'review_id', false
  )
$$;

create or replace function public.creator_generation_learning_policy(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_generation_learning_policy_pre_project_v47',
    content_factory_private.project_payload_from_context_v47(p_payload),
    'media', 'media_id', false
  )
$$;

-- The research advisory predates project scope and calls the public learning
-- policy internally without project_id. Preserve its governed implementation,
-- then derive context only from the exact organization/media row before that
-- internal policy call. Missing or unscoped media fails closed.
do $preserve_research_advisory_v47$
begin
  if to_regprocedure(
    'content_factory_private.research_outcome_generation_advisory_pre_project_v47(uuid,uuid,text,text,text)'
  ) is null then
    alter function
      content_factory_private.research_outcome_generation_advisory(
        uuid, uuid, text, text, text
      ) rename to research_outcome_generation_advisory_pre_project_v47;
  end if;
end;
$preserve_research_advisory_v47$;

revoke all on function
  content_factory_private.research_outcome_generation_advisory_pre_project_v47(
    uuid, uuid, text, text, text
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.research_outcome_generation_advisory(
    p_organization_id uuid,
    p_media_id uuid,
    p_platform text,
    p_model text,
    p_product_category text
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_project_id uuid;
  previous_project_setting text;
  result_value jsonb;
begin
  select media.project_id
    into v_project_id
  from content_factory.media_objects media
  where media.organization_id = p_organization_id
    and media.id = p_media_id;

  if not found or v_project_id is null then
    raise exception using
      errcode = '42501',
      message = 'project_entity_mismatch';
  end if;
  perform content_factory_private.require_workspace_project(
    p_organization_id, v_project_id
  );
  perform content_factory_private.require_project_entity(
    p_organization_id, v_project_id, 'media', p_media_id
  );

  previous_project_setting := current_setting(
    'contentengine.project_id',
    true
  );
  perform set_config(
    'contentengine.project_id',
    v_project_id::text,
    true
  );
  begin
    result_value :=
      content_factory_private.research_outcome_generation_advisory_pre_project_v47(
        p_organization_id,
        p_media_id,
        p_platform,
        p_model,
        p_product_category
      );
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''),
    true
  );
  return result_value;
end;
$$;

revoke all on function
  content_factory_private.research_outcome_generation_advisory(
    uuid, uuid, text, text, text
  ) from public, anon, authenticated, service_role;

create or replace function public.creator_decide_payout(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_decide_payout_pre_project_v47', p_payload,
    'payout', 'payout_id', false
  )
$$;

create or replace function public.creator_generation_media_identity(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_generation_media_identity_pre_project_v47', p_payload,
    null, null, true
  )
$$;

create or replace function public.creator_prepare_content_review_evidence(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_prepare_content_review_evidence_pre_project_v47', p_payload,
    'media', 'media_id', false
  )
$$;

create or replace function public.creator_commit_content_review_evidence(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_commit_content_review_evidence_pre_project_v47', p_payload,
    'evidence', 'evidence_id', false
  )
$$;

create or replace function public.creator_real_generation_reconciliation_context(
  p_payload jsonb default '{}'::jsonb
) returns jsonb language sql volatile security definer set search_path = '' as $$
  select content_factory_private.call_project_scoped_v47(
    'creator_real_generation_reconciliation_context_pre_project_v47',
    p_payload, 'job', 'job_id', false
  )
$$;

revoke all on function public.creator_start_content_review(jsonb) from public, anon;
revoke all on function public.creator_start_generated_video_review(jsonb) from public, anon;
revoke all on function public.creator_content_review_status(jsonb) from public, anon;
revoke all on function public.creator_decide_content_review(jsonb) from public, anon;
revoke all on function public.creator_approve_generated_photo_review_with_context(jsonb) from public, anon;
revoke all on function public.creator_approve_generated_video_review_with_context(jsonb) from public, anon;
revoke all on function public.creator_create_mock_batch(jsonb) from public, anon;
revoke all on function public.creator_start_real_generation(jsonb) from public, anon;
revoke all on function public.creator_real_generation_status(jsonb) from public, anon;
revoke all on function public.creator_register_media(jsonb) from public, anon;
revoke all on function public.creator_confirm_placement(jsonb) from public, anon;
revoke all on function public.creator_record_metric(jsonb) from public, anon;
revoke all on function public.creator_transition_task(jsonb) from public, anon;
revoke all on function public.creator_configure_tracking_link(jsonb) from public, anon;
revoke all on function public.creator_generation_repair_policy(jsonb) from public, anon;
revoke all on function public.creator_generation_learning_policy(jsonb) from public, anon;
revoke all on function public.creator_decide_payout(jsonb) from public, anon;
revoke all on function public.creator_generation_media_identity(jsonb) from public, anon;
revoke all on function public.creator_prepare_content_review_evidence(jsonb) from public, anon;
revoke all on function public.creator_commit_content_review_evidence(jsonb) from public, anon;
revoke all on function public.creator_real_generation_reconciliation_context(jsonb) from public, anon;

grant execute on function public.creator_start_content_review(jsonb) to authenticated;
grant execute on function public.creator_start_generated_video_review(jsonb) to authenticated;
grant execute on function public.creator_content_review_status(jsonb) to authenticated;
grant execute on function public.creator_decide_content_review(jsonb) to authenticated;
grant execute on function public.creator_approve_generated_photo_review_with_context(jsonb) to authenticated;
grant execute on function public.creator_approve_generated_video_review_with_context(jsonb) to authenticated;
grant execute on function public.creator_create_mock_batch(jsonb) to authenticated;
grant execute on function public.creator_start_real_generation(jsonb) to authenticated;
grant execute on function public.creator_real_generation_status(jsonb) to authenticated;
grant execute on function public.creator_register_media(jsonb) to authenticated;
grant execute on function public.creator_confirm_placement(jsonb) to authenticated;
grant execute on function public.creator_record_metric(jsonb) to authenticated;
grant execute on function public.creator_transition_task(jsonb) to authenticated;
grant execute on function public.creator_configure_tracking_link(jsonb) to authenticated;
grant execute on function public.creator_generation_repair_policy(jsonb) to authenticated;
grant execute on function public.creator_generation_learning_policy(jsonb) to authenticated;
grant execute on function public.creator_decide_payout(jsonb) to authenticated;
grant execute on function public.creator_generation_media_identity(jsonb) to authenticated;
grant execute on function public.creator_prepare_content_review_evidence(jsonb) to authenticated;
grant execute on function public.creator_commit_content_review_evidence(jsonb) to authenticated;
grant execute on function public.creator_real_generation_reconciliation_context(jsonb) to authenticated;

create or replace function public.creator_restore_project_placement(
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
  actor_role text;
  manager_scope boolean;
  project_id_value uuid;
  review_id_value uuid;
  idempotency_key_value text;
  request_value jsonb;
  replay_value jsonb;
  result_value jsonb;
  review_row content_factory.content_review_runs%rowtype;
  decision_row content_factory.content_review_decisions%rowtype;
  media_row content_factory.media_objects%rowtype;
  review_task_row content_factory.creator_tasks%rowtype;
  job_row content_factory.generation_jobs%rowtype;
  previous_placement_row content_factory.placements%rowtype;
  placement_id_value uuid;
  placement_task_id_value uuid;
  placement_attempt integer;
  platform_value text;
  destination_value text;
  assignee_id_value uuid;
  product_id_value uuid;
  placement_request jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'project_id', 'review_id'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'restore_project_placement_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  project_id_value := content_factory_private.require_uuid(p_payload, 'project_id');
  review_id_value := content_factory_private.require_uuid(p_payload, 'review_id');
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'review', review_id_value
  );
  if not exists (
    select 1
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
     and media.project_id = review.project_id
    left join content_factory.creator_tasks task
      on task.organization_id = media.organization_id
     and task.id = media.task_id
     and task.project_id = review.project_id
    where review.organization_id = organization_id
      and review.project_id = project_id_value
      and review.id = review_id_value
      and (
        manager_scope
        or review.requested_by = user_id
        or media.owner_id = user_id
        or task.assignee_id = user_id
      )
  ) then
    raise exception using
      errcode = '42501', message = 'content_review_not_visible';
  end if;
  request_value := jsonb_build_object(
    'project_id', project_id_value,
    'review_id', review_id_value
  );
  replay_value := content_factory_private.begin_command(
    organization_id, 'creator_restore_project_placement',
    idempotency_key_value, request_value
  );
  if replay_value is not null then return replay_value; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('restore-placement:' || review_id_value::text)
  );
  select review.* into review_row
  from content_factory.content_review_runs review
  where review.organization_id = organization_id
    and review.id = review_id_value
    and review.project_id = project_id_value
  for update;
  if review_row.id is null or review_row.status <> 'completed'
     or review_row.completion_hash is null then
    raise exception using errcode = '55000', message = 'content_review_not_restorable';
  end if;

  select decision.* into decision_row
  from content_factory.content_review_decisions decision
  where decision.organization_id = organization_id
    and decision.review_id = review_id_value
    and decision.decision = 'approved'
  order by decision.created_at desc, decision.id desc
  limit 1;
  if decision_row.id is null
     or not decision_row.media_watched_confirmed
     or decision_row.review_completion_hash <> review_row.completion_hash
     or decision_row.media_sha256_snapshot <> review_row.media_sha256_snapshot then
    raise exception using errcode = '55000', message = 'content_review_approval_not_restorable';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = review_row.media_object_id
    and media.project_id = project_id_value
    and media.status = 'ready'
  for update;
  if media_row.id is null or media_row.sha256 <> review_row.media_sha256_snapshot then
    raise exception using errcode = '55000', message = 'content_review_media_stale';
  end if;

  select placement.* into previous_placement_row
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.project_id = project_id_value
    and placement.metadata ->> 'content_review_id' = review_id_value::text
    and placement.status not in ('failed', 'cancelled')
  order by placement.updated_at desc, placement.id desc
  limit 1;
  if previous_placement_row.id is not null then
    result_value := jsonb_build_object(
      'ok', true, 'restored', false,
      'project_id', project_id_value,
      'review_id', review_id_value,
      'placement_id', previous_placement_row.id,
      'placement', jsonb_build_object(
        'id', previous_placement_row.id,
        'project_id', project_id_value,
        'task_id', previous_placement_row.task_id,
        'status', previous_placement_row.status,
        'platform', previous_placement_row.platform,
        'destination_ref', previous_placement_row.destination_ref
      )
    );
    return content_factory_private.finish_command(
      organization_id, user_id, 'creator_restore_project_placement',
      idempotency_key_value, request_value, result_value
    );
  end if;

  select task.* into review_task_row
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.id = media_row.task_id
    and task.project_id = project_id_value
    and task.task_type = 'video_review'
  limit 1;
  if review_task_row.id is null or review_task_row.generation_job_id is null then
    raise exception using errcode = '55000', message = 'content_review_task_not_restorable';
  end if;
  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = review_task_row.generation_job_id
    and job.project_id = project_id_value
    and job.status = 'succeeded'
  limit 1;
  if job_row.id is null
     or job_row.output ->> 'output_media_id' is distinct from media_row.id::text then
    raise exception using errcode = '55000', message = 'content_review_job_not_restorable';
  end if;

  select placement.* into previous_placement_row
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.project_id = project_id_value
    and placement.metadata ->> 'content_review_id' = review_id_value::text
  order by placement.updated_at desc, placement.id desc
  limit 1;
  platform_value := lower(btrim(coalesce(
    previous_placement_row.platform,
    review_row.input ->> 'platform',
    job_row.input ->> 'platform',
    review_task_row.result ->> 'platform',
    ''
  )));
  destination_value := btrim(coalesce(
    previous_placement_row.destination_ref,
    review_row.input ->> 'destination_ref',
    job_row.input ->> 'destination_ref',
    review_task_row.result ->> 'destination_ref',
    ''
  ));
  if platform_value not in (
    'instagram', 'tiktok', 'youtube', 'vk',
    'telegram', 'wildberries'
  ) or length(destination_value) not between 2 and 240 then
    raise exception using errcode = '55000', message = 'content_review_placement_input_invalid';
  end if;
  select candidate.profile_id into assignee_id_value
  from (values
    (previous_placement_row.assigned_to, 1),
    (review_task_row.assignee_id, 2),
    (media_row.owner_id, 3),
    (user_id, 4)
  ) as candidate(profile_id, rank_value)
  join content_factory.memberships membership
    on membership.organization_id = organization_id
   and membership.profile_id = candidate.profile_id
   and membership.status = 'active'
   and membership.role = any(
     array['owner', 'admin', 'producer', 'reviewer', 'operator']
   )
  join content_factory.profiles profile
    on profile.id = candidate.profile_id
   and profile.status = 'active'
  where candidate.profile_id is not null
  order by candidate.rank_value, candidate.profile_id
  limit 1
  for key share of membership, profile;
  if assignee_id_value is null then
    raise exception using
      errcode = '55000', message = 'content_review_placement_assignee_unavailable';
  end if;
  select product.id into product_id_value
  from content_factory.products product
  where product.organization_id = organization_id
    and product.id = coalesce(job_row.product_id, media_row.product_id)
    and product.status = 'active'
  for key share of product;
  if product_id_value is null then
    raise exception using
      errcode = '55000', message = 'content_review_placement_product_inactive';
  end if;
  select count(*)::integer + 1 into placement_attempt
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.project_id = project_id_value
    and placement.metadata ->> 'content_review_id' = review_id_value::text;

  insert into content_factory.creator_tasks (
    organization_id, assignee_id, created_by, product_id,
    generation_job_id, task_type, title, instructions,
    status, priority, payout_minor, result, idempotency_key, project_id
  ) values (
    organization_id, assignee_id_value, user_id, product_id_value,
    job_row.id, 'placement',
    left('Опубликовать одобренный материал — ' || coalesce(
      job_row.input ->> 'product_name', 'контент'
    ), 240),
    'Опубликуйте только одобренный файл и добавьте финальную HTTPS-ссылку.',
    'todo', 2, 0,
    jsonb_build_object(
      'content_review_id', review_row.id,
      'content_review_decision_id', decision_row.id,
      'source_media_id', media_row.id,
      'media_sha256', media_row.sha256,
      'ruleset_version', review_row.ruleset_version,
      'platform', platform_value,
      'destination_ref', destination_value,
      'recovery_attempt', placement_attempt
    ),
    'content-review-placement-recovery:' || review_row.id::text
      || ':' || placement_attempt::text,
    project_id_value
  ) returning id into placement_task_id_value;

  placement_request := jsonb_build_object(
    'content_review_id', review_row.id,
    'decision_id', decision_row.id,
    'generation_job_id', job_row.id,
    'media_id', media_row.id,
    'media_sha256', media_row.sha256,
    'platform', platform_value,
    'destination_ref', destination_value,
    'recovery_attempt', placement_attempt
  );
  insert into content_factory.placements (
    organization_id, product_id, generation_job_id, task_id,
    assigned_to, created_by, platform, destination_ref,
    status, request_hash, idempotency_key, metadata, project_id
  ) values (
    organization_id, product_id_value, job_row.id, placement_task_id_value,
    assignee_id_value, user_id, platform_value, destination_value,
    'ready', content_factory_private.json_hash(placement_request),
    'content-review-placement-recovery:' || review_row.id::text
      || ':' || placement_attempt::text,
    jsonb_build_object(
      'content_review_id', review_row.id,
      'content_review_decision_id', decision_row.id,
      'source_media_id', media_row.id,
      'media_sha256', media_row.sha256,
      'ruleset_version', review_row.ruleset_version,
      'media_watched_confirmed', true,
      'recovery_attempt', placement_attempt
    ),
    project_id_value
  ) returning id into placement_id_value;

  result_value := jsonb_build_object(
    'ok', true, 'restored', true,
    'project_id', project_id_value,
    'review_id', review_id_value,
    'placement_id', placement_id_value,
    'placement', jsonb_build_object(
      'id', placement_id_value,
      'project_id', project_id_value,
      'task_id', placement_task_id_value,
      'status', 'ready',
      'platform', platform_value,
      'destination_ref', destination_value
    )
  );
  perform content_factory_private.emit_event(
    organization_id, user_id, 'project_placement_restored',
    'placement', placement_id_value::text,
    jsonb_build_object(
      'project_id', project_id_value,
      'review_id', review_id_value,
      'placement_task_id', placement_task_id_value,
      'recovery_attempt', placement_attempt
    ),
    'project-placement-restore:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_restore_project_placement',
    idempotency_key_value, request_value, result_value
  );
end;
$$;

revoke all on function public.creator_restore_project_placement(jsonb)
  from public, anon;
grant execute on function public.creator_restore_project_placement(jsonb)
  to authenticated;

-- Product research keeps its mature legacy validation and worker contract,
-- while these project entrypoints make the workflow boundary explicit.  A
-- project-scoped receipt is deliberately separate from the preserved RPC's
-- receipt: if the outer receipt is lost after the inner commit, the inner call
-- replays safely and the wrapper can finish recording the enriched result.
create or replace function public.creator_start_project_research(
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
  raw_idempotency_key text;
  scoped_idempotency_key text;
  source_media_ids jsonb;
  media_text text;
  media_id_value uuid;
  request_payload jsonb;
  inner_payload jsonb;
  previous_project_setting text;
  replay jsonb;
  result_value jsonb;
  result_run_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  raw_idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  source_media_ids := coalesce(p_payload -> 'source_media_ids', '[]'::jsonb);
  if jsonb_typeof(source_media_ids) <> 'array' then
    raise exception using
      errcode = '22023', message = 'source_media_ids_invalid';
  end if;
  for media_text in
    select item.value from jsonb_array_elements_text(source_media_ids) item(value)
  loop
    begin
      media_id_value := media_text::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023', message = 'source_media_id_invalid';
    end;
    perform content_factory_private.require_project_entity(
      organization_id, project_id_value, 'media', media_id_value
    );
  end loop;

  scoped_idempotency_key := 'project-v47:' ||
    content_factory_private.json_hash(jsonb_build_object(
      'operation', 'creator_start_project_research',
      'project_id', project_id_value,
      'idempotency_key', raw_idempotency_key
    ));
  request_payload := p_payload -
    array['organization_id', 'idempotency_key']::text[];
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_start_project_research',
    scoped_idempotency_key,
    request_payload
  );

  if replay is null then
    inner_payload := (
      p_payload - array['project_id', 'idempotency_key']::text[]
    ) || jsonb_build_object(
      'organization_id', organization_id,
      'idempotency_key', scoped_idempotency_key
    );
    previous_project_setting := current_setting(
      'contentengine.project_id', true
    );
    perform set_config(
      'contentengine.project_id', project_id_value::text, true
    );
    begin
      result_value := public.creator_start_product_research(inner_payload);
    exception when others then
      perform set_config(
        'contentengine.project_id',
        coalesce(previous_project_setting, ''),
        true
      );
      raise;
    end;
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
  else
    result_value := replay;
  end if;

  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end if;
  begin
    result_run_id := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end;
  if result_run_id is null then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end if;
  -- A replay must already belong to this project.  Never repair or reassign it.
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'research_run', result_run_id
  );
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );
  result_value := jsonb_set(
    result_value,
    '{run,project_id}',
    to_jsonb(project_id_value),
    true
  );

  if replay is not null then return result_value; end if;
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_start_project_research',
    scoped_idempotency_key,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_project_research_status(
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
  organization_id uuid;
  project_id_value uuid;
  run_id_value uuid;
  result_run_id uuid;
  result_draft_id uuid;
  inner_payload jsonb;
  previous_project_setting text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  perform content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'research_run', run_id_value
  );

  inner_payload := (p_payload - 'project_id') || jsonb_build_object(
    'organization_id', organization_id
  );
  previous_project_setting := current_setting(
    'contentengine.project_id', true
  );
  perform set_config(
    'contentengine.project_id', project_id_value::text, true
  );
  begin
    result_value := public.creator_product_research_status(inner_payload);
  exception when others then
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
    raise;
  end;
  perform set_config(
    'contentengine.project_id',
    coalesce(previous_project_setting, ''),
    true
  );

  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end if;
  begin
    result_run_id := (result_value #>> '{run,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end;
  if result_run_id is null or result_run_id <> run_id_value then
    raise exception using
      errcode = '55000', message = 'project_research_result_mismatch';
  end if;
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'research_run', result_run_id
  );
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );
  result_value := jsonb_set(
    result_value,
    '{run,project_id}',
    to_jsonb(project_id_value),
    true
  );

  if jsonb_typeof(result_value -> 'latest_draft') = 'object' then
    begin
      result_draft_id := (result_value #>> '{latest_draft,id}')::uuid;
    exception when invalid_text_representation then
      raise exception using
        errcode = '55000', message = 'project_research_result_invalid';
    end;
    if result_draft_id is null then
      raise exception using
        errcode = '55000', message = 'project_research_result_invalid';
    end if;
    perform content_factory_private.require_project_entity(
      organization_id,
      project_id_value,
      'creative_brief_draft',
      result_draft_id
    );
    result_value := jsonb_set(
      result_value,
      '{latest_draft,project_id}',
      to_jsonb(project_id_value),
      true
    );
  end if;
  return result_value;
end;
$$;

create or replace function public.creator_save_project_creative_brief_draft(
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
  run_id_value uuid;
  raw_idempotency_key text;
  scoped_idempotency_key text;
  source_ids_value jsonb;
  request_payload jsonb;
  inner_payload jsonb;
  previous_project_setting text;
  replay jsonb;
  result_value jsonb;
  result_draft_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'research_run', run_id_value
  );
  raw_idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  source_ids_value := coalesce(p_payload -> 'source_ids', '[]'::jsonb);
  if jsonb_typeof(source_ids_value) = 'array' and exists (
    select 1
    from jsonb_array_elements_text(source_ids_value) item(value)
    where not exists (
      select 1
      from content_factory.product_research_sources source
      join content_factory.product_research_runs run
        on run.organization_id = source.organization_id
       and run.id = source.run_id
       and run.project_id = project_id_value
      where source.organization_id = organization_id
        and source.run_id = run_id_value
        and source.id::text = item.value
    )
  ) then
    raise exception using
      errcode = '42501', message = 'project_research_source_mismatch';
  end if;

  scoped_idempotency_key := 'project-v47:' ||
    content_factory_private.json_hash(jsonb_build_object(
      'operation', 'creator_save_project_creative_brief_draft',
      'project_id', project_id_value,
      'idempotency_key', raw_idempotency_key
    ));
  request_payload := p_payload -
    array['organization_id', 'idempotency_key']::text[];
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_save_project_creative_brief_draft',
    scoped_idempotency_key,
    request_payload
  );

  if replay is null then
    inner_payload := (
      p_payload - array['project_id', 'idempotency_key']::text[]
    ) || jsonb_build_object(
      'organization_id', organization_id,
      'idempotency_key', scoped_idempotency_key
    );
    previous_project_setting := current_setting(
      'contentengine.project_id', true
    );
    perform set_config(
      'contentengine.project_id', project_id_value::text, true
    );
    begin
      result_value := public.creator_save_creative_brief_draft(inner_payload);
    exception when others then
      perform set_config(
        'contentengine.project_id',
        coalesce(previous_project_setting, ''),
        true
      );
      raise;
    end;
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
  else
    result_value := replay;
  end if;

  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end if;
  begin
    result_draft_id := (result_value #>> '{draft,id}')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end;
  if result_draft_id is null or not exists (
    select 1
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id
      and draft.id = result_draft_id
      and draft.run_id = run_id_value
      and draft.project_id = project_id_value
  ) then
    raise exception using
      errcode = '55000', message = 'project_research_result_mismatch';
  end if;
  -- Replay validation is read-only: a draft from another project is rejected.
  perform content_factory_private.require_project_entity(
    organization_id,
    project_id_value,
    'creative_brief_draft',
    result_draft_id
  );
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );
  result_value := jsonb_set(
    result_value,
    '{draft,project_id}',
    to_jsonb(project_id_value),
    true
  );

  if replay is not null then return result_value; end if;
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_save_project_creative_brief_draft',
    scoped_idempotency_key,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_approve_project_creative_brief(
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
  draft_id_value uuid;
  draft_run_id_value uuid;
  raw_idempotency_key text;
  scoped_idempotency_key text;
  request_payload jsonb;
  inner_payload jsonb;
  previous_project_setting text;
  replay jsonb;
  result_value jsonb;
  result_draft_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  draft_id_value := content_factory_private.require_uuid(
    p_payload, 'draft_id'
  );
  perform content_factory_private.require_project_entity(
    organization_id,
    project_id_value,
    'creative_brief_draft',
    draft_id_value
  );
  select draft.run_id into draft_run_id_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id
    and draft.id = draft_id_value
    and draft.project_id = project_id_value;
  if draft_run_id_value is null then
    raise exception using
      errcode = '42501', message = 'project_entity_mismatch';
  end if;
  perform content_factory_private.require_project_entity(
    organization_id,
    project_id_value,
    'research_run',
    draft_run_id_value
  );
  raw_idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  scoped_idempotency_key := 'project-v47:' ||
    content_factory_private.json_hash(jsonb_build_object(
      'operation', 'creator_approve_project_creative_brief',
      'project_id', project_id_value,
      'idempotency_key', raw_idempotency_key
    ));
  request_payload := p_payload -
    array['organization_id', 'idempotency_key']::text[];
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_approve_project_creative_brief',
    scoped_idempotency_key,
    request_payload
  );

  if replay is null then
    inner_payload := (
      p_payload - array['project_id', 'idempotency_key']::text[]
    ) || jsonb_build_object(
      'organization_id', organization_id,
      'idempotency_key', scoped_idempotency_key
    );
    previous_project_setting := current_setting(
      'contentengine.project_id', true
    );
    perform set_config(
      'contentengine.project_id', project_id_value::text, true
    );
    begin
      result_value := public.creator_approve_creative_brief(inner_payload);
    exception when others then
      perform set_config(
        'contentengine.project_id',
        coalesce(previous_project_setting, ''),
        true
      );
      raise;
    end;
    perform set_config(
      'contentengine.project_id',
      coalesce(previous_project_setting, ''),
      true
    );
  else
    result_value := replay;
  end if;

  if jsonb_typeof(result_value) <> 'object' then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end if;
  begin
    result_draft_id := (result_value ->> 'draft_id')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '55000', message = 'project_research_result_invalid';
  end;
  if result_draft_id is null or result_draft_id <> draft_id_value then
    raise exception using
      errcode = '55000', message = 'project_research_result_mismatch';
  end if;
  perform content_factory_private.require_project_entity(
    organization_id,
    project_id_value,
    'creative_brief_draft',
    result_draft_id
  );
  if jsonb_typeof(result_value -> 'task_ids') = 'array' and exists (
    select 1
    from jsonb_array_elements_text(result_value -> 'task_ids') item(value)
    where not exists (
      select 1 from content_factory.creator_tasks task
      where task.organization_id = organization_id
        and task.id::text = item.value
        and task.creative_brief_draft_id = draft_id_value
        and task.project_id = project_id_value
    )
  ) then
    raise exception using
      errcode = '55000', message = 'project_research_result_mismatch';
  end if;
  result_value := result_value || jsonb_build_object(
    'project_id', project_id_value
  );

  if replay is not null then return result_value; end if;
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_approve_project_creative_brief',
    scoped_idempotency_key,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_start_project_research(jsonb)
  from public, anon;
revoke all on function public.creator_project_research_status(jsonb)
  from public, anon;
revoke all on function public.creator_save_project_creative_brief_draft(jsonb)
  from public, anon;
revoke all on function public.creator_approve_project_creative_brief(jsonb)
  from public, anon;

grant execute on function public.creator_start_project_research(jsonb)
  to authenticated;
grant execute on function public.creator_project_research_status(jsonb)
  to authenticated;
grant execute on function public.creator_save_project_creative_brief_draft(jsonb)
  to authenticated;
grant execute on function public.creator_approve_project_creative_brief(jsonb)
  to authenticated;

-- The old product-research entrypoints do not accept project_id.  The new
-- SECURITY DEFINER wrappers above can still call them as their owner, while
-- authenticated clients must use the project-bound public contract.
revoke all on function public.creator_start_product_research(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_product_research_status(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_save_creative_brief_draft(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_approve_creative_brief(jsonb)
  from public, anon, authenticated;

-- Keep the archive's existing keyset contract, but apply the optional project
-- boundary before LIMIT. Filtering an already paged legacy response would
-- otherwise skip valid batches from the selected project.
create or replace function public.creator_generation_archive(
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
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  actor_role text;
  team_scope boolean;
  period_value text := '4w';
  status_value text := 'all';
  query_value text := '';
  page_size integer := 50;
  cursor_at timestamptz;
  cursor_id uuid;
  period_cutoff timestamptz;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'project_id', 'period', 'status', 'query',
      'page_size', 'cursor'
    ])
  ) then
    raise exception using
      errcode = '22023', message = 'generation_archive_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);

  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );

  if p_payload ? 'period' then
    if jsonb_typeof(p_payload -> 'period') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_period_invalid';
    end if;
    period_value := lower(btrim(p_payload ->> 'period'));
  end if;
  if period_value not in ('week', '4w', '12w', 'all') then
    raise exception using
      errcode = '22023', message = 'generation_archive_period_invalid';
  end if;

  if p_payload ? 'status' then
    if jsonb_typeof(p_payload -> 'status') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_status_invalid';
    end if;
    status_value := lower(btrim(p_payload ->> 'status'));
  end if;
  if status_value not in ('all', 'active', 'ready', 'issue') then
    raise exception using
      errcode = '22023', message = 'generation_archive_status_invalid';
  end if;

  if p_payload ? 'query' then
    if jsonb_typeof(p_payload -> 'query') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_query_invalid';
    end if;
    query_value := btrim(p_payload ->> 'query');
  end if;
  if length(query_value) > 120 or query_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023', message = 'generation_archive_query_invalid';
  end if;

  if p_payload ? 'page_size' then
    if jsonb_typeof(p_payload -> 'page_size') <> 'number'
       or coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'generation_archive_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023', message = 'generation_archive_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'generation_archive_page_size_invalid';
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object' then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    if exists (
      select 1
      from jsonb_object_keys(p_payload -> 'cursor') cursor_key
      where cursor_key <> all(array['at', 'id'])
    ) then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    if jsonb_typeof(p_payload #> '{cursor,at}') <> 'string'
       or jsonb_typeof(p_payload #> '{cursor,id}') <> 'string'
       or nullif(btrim(coalesce(p_payload #>> '{cursor,at}', '')), '') is null
       or nullif(btrim(coalesce(p_payload #>> '{cursor,id}', '')), '') is null then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    begin
      cursor_at := (p_payload #>> '{cursor,at}')::timestamptz;
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation
        or invalid_datetime_format
        or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end;
  end if;

  period_cutoff := case period_value
    when 'week' then date_trunc('week', now())
    when '4w' then date_trunc('week', now()) - interval '3 weeks'
    when '12w' then date_trunc('week', now()) - interval '11 weeks'
    else null
  end;

  with candidates as materialized (
    select
      batch.id,
      batch.project_id,
      batch.name,
      batch.mode,
      batch.status,
      batch.total_requested,
      batch.total_created,
      batch.input,
      batch.created_at,
      product.sku,
      product.title as product_name
    from content_factory.generation_batches batch
    join content_factory.products product
      on product.organization_id = batch.organization_id
     and product.id = batch.product_id
    where batch.organization_id = organization_id
      and (project_id_value is null or batch.project_id = project_id_value)
      and (team_scope or batch.created_by = user_id)
      and (period_cutoff is null or batch.created_at >= period_cutoff)
      and (
        status_value = 'all'
        or (
          status_value = 'active'
          and batch.status in ('queued', 'starting', 'submitted', 'processing')
        )
        or (
          status_value = 'ready'
          and batch.status in ('mock_ready', 'succeeded')
        )
        or (
          status_value = 'issue'
          and batch.status in ('failed', 'cancelled')
        )
      )
      and (
        query_value = ''
        or position(
          lower(query_value) in lower(concat_ws(
            ' ', batch.name, batch.id::text, product.sku, product.title
          ))
        ) > 0
      )
      and (
        cursor_at is null
        or (batch.created_at, batch.id) < (cursor_at, cursor_id)
      )
    order by batch.created_at desc, batch.id desc
    limit page_size + 1
  ),
  page as materialized (
    select candidate.*
    from candidates candidate
    order by candidate.created_at desc, candidate.id desc
    limit page_size
  ),
  page_stats as (
    select count(*) > page_size as has_more
    from candidates
  ),
  last_row as (
    select page.created_at, page.id
    from page
    order by page.created_at asc, page.id asc
    limit 1
  )
  select jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'batches', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', page.id,
        'public_id', page.id,
        'project_id', page.project_id,
        'name', page.name,
        'sku', page.sku,
        'product_name', page.product_name,
        'mode', page.mode,
        'status', page.status,
        'total_requested', page.total_requested,
        'total_created', page.total_created,
        'total_accepted', page.total_created,
        'parameters', page.input,
        'created_at', page.created_at,
        '_cursor', jsonb_build_object(
          'at', page.created_at,
          'id', page.id
        )
      ) order by page.created_at desc, page.id desc)
      from page
    ), '[]'::jsonb),
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'has_more', page_stats.has_more,
      'next_cursor', case
        when page_stats.has_more then jsonb_build_object(
          'at', last_row.created_at,
          'id', last_row.id
        )
        else null
      end,
      'period', period_value,
      'status', status_value,
      'query', query_value,
      'cursor_mode', 'keyset_created_at_id'
    )
  )
  into result
  from page_stats
  left join last_row on true;

  return result;
end;
$$;

revoke all on function public.creator_generation_archive(jsonb)
  from public, anon;
grant execute on function public.creator_generation_archive(jsonb)
  to authenticated;

-- Fetch one exact, project-bound media object for a deep link before the
-- paginated Generation or Review collection chooses any default item.
create or replace function public.creator_project_media(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  media_id_value uuid;
  surface_value text;
  actor_role text;
  team_scope boolean;
  media_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'project_id', 'media_id', 'surface'
    ])
  ) then
    raise exception using
      errcode = '22023', message = 'project_media_payload_invalid';
  end if;
  surface_value := lower(btrim(coalesce(p_payload ->> 'surface', '')));
  if surface_value not in ('generation', 'review') then
    raise exception using
      errcode = '22023', message = 'project_media_surface_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  if surface_value = 'review' then
    actor_role := content_factory_private.membership_role(
      organization_id,
      true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
  else
    actor_role := content_factory_private.membership_role(
      organization_id, true,
      array['owner', 'admin', 'producer', 'reviewer', 'operator']
    );
  end if;
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  media_id_value := content_factory_private.require_uuid(
    p_payload, 'media_id'
  );
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'media', media_id_value
  );

  select jsonb_build_object(
    'id', media.id,
    'public_id', media.id,
    'project_id', media.project_id,
    'owner_id', media.owner_id,
    'task_id', media.task_id,
    'product_id', media.product_id,
    'sku', product.sku,
    'product_name', product.title,
    'original_filename', media.metadata ->> 'original_filename',
    'name', coalesce(
      media.metadata ->> 'original_filename',
      media.metadata ->> 'filename',
      media.id::text
    ),
    'kind', media.metadata ->> 'kind',
    'mime_type', media.mime_type,
    'size_bytes', media.size_bytes,
    'sha256', media.sha256,
    'bucket_id', media.bucket_id,
    'object_name', media.object_name,
    'status', media.status,
    'metadata', media.metadata,
    'generation_job_id', media.metadata ->> 'generation_job_id',
    'rights_confirmed',
      media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb,
    'identity_verified', coalesce((
      product.id is not null
      and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    ), false),
    'created_at', media.created_at,
    'updated_at', media.updated_at,
    '_cursor', jsonb_build_object(
      'at', media.created_at, 'id', media.id
    )
  )
  into media_value
  from content_factory.media_objects media
  left join content_factory.creator_tasks task
    on task.organization_id = media.organization_id
   and task.id = media.task_id
  left join content_factory.products product
    on product.organization_id = media.organization_id
   and product.id = media.product_id
   and product.status = 'active'
  where media.organization_id = organization_id
    and media.project_id = project_id_value
    and media.id = media_id_value
    and media.status = 'ready'
    and (
      team_scope
      or media.owner_id = user_id
      or (surface_value = 'review' and task.assignee_id = user_id)
    )
    and (
      surface_value <> 'review'
      or media.mime_type in (
        'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
      )
    );

  if media_value is null then
    raise exception using
      errcode = '42501', message = 'project_media_not_visible';
  end if;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'media_id', media_id_value,
    'surface', surface_value,
    'media', media_value
  );
end;
$$;

revoke all on function public.creator_project_media(jsonb)
  from public, anon;
grant execute on function public.creator_project_media(jsonb)
  to authenticated;

-- Resolve an exact placement independently from the paginated workspace
-- collections. Deep links use this narrow read so the selected object cannot
-- disappear behind an organization-wide legacy page or a stale client filter.
create or replace function public.creator_project_placement(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  placement_id_value uuid;
  actor_role text;
  team_scope boolean;
  placement_value jsonb;
  publication_value jsonb;
  publication_option_value jsonb;
  latest_metric_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array[
      'organization_id', 'project_id', 'placement_id'
    ])
  ) then
    raise exception using
      errcode = '22023', message = 'project_placement_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );
  placement_id_value := content_factory_private.require_uuid(
    p_payload, 'placement_id'
  );
  perform content_factory_private.require_project_entity(
    organization_id, project_id_value, 'placement', placement_id_value
  );

  with exact as (
    select
      placement.id,
      placement.project_id,
      placement.task_id,
      placement.platform,
      placement.destination_ref,
      placement.status,
      placement.scheduled_at,
      placement.published_at,
      placement.tracking_url,
      placement.final_url,
      placement.metadata,
      placement.created_at,
      placement.updated_at,
      product.sku,
      product.title as product_title,
      task.title as task_title,
      task.instructions,
      metric.id as metric_id,
      metric.source as metric_source,
      metric.observed_at as metric_observed_at,
      metric.views as metric_views,
      metric.clicks as metric_clicks,
      metric.orders as metric_orders,
      metric.revenue_minor as metric_revenue_minor,
      metric.is_correction as metric_is_correction,
      metric.correction_reason as metric_correction_reason,
      metric.created_at as metric_created_at,
      coalesce(clicks.human_clicks, 0) as tracked_clicks
    from content_factory.placements placement
    join content_factory.products product
      on product.organization_id = placement.organization_id
     and product.id = placement.product_id
    left join content_factory.creator_tasks task
      on task.organization_id = placement.organization_id
     and task.id = placement.task_id
    left join lateral (
      select snapshot.*
      from content_factory.metric_snapshots snapshot
      where snapshot.organization_id = placement.organization_id
        and snapshot.placement_id = placement.id
      order by
        snapshot.observed_at desc,
        snapshot.created_at desc,
        snapshot.id desc
      limit 1
    ) metric on true
    left join lateral (
      select count(*)::bigint as human_clicks
      from content_factory.tracking_clicks click
      where click.organization_id = placement.organization_id
        and click.placement_id = placement.id
        and click.accepted_for_human_kpi
    ) clicks on true
    where placement.organization_id = organization_id
      and placement.project_id = project_id_value
      and placement.id = placement_id_value
      and (team_scope or placement.assigned_to = user_id)
  ),
  shaped as (
    select
      exact.*,
      greatest(
        coalesce(exact.metric_clicks, 0), exact.tracked_clicks
      ) as effective_clicks,
      case
        when exact.tracked_clicks > coalesce(exact.metric_clicks, 0)
             and exact.metric_source is not null then 'mixed'
        when exact.tracked_clicks > coalesce(exact.metric_clicks, 0)
          then 'tracking_link'
        else exact.metric_source
      end as effective_source,
      case
        when exact.metric_id is null then null
        else jsonb_build_object(
          'id', exact.metric_id,
          'source', exact.metric_source,
          'observed_at', exact.metric_observed_at,
          'views', exact.metric_views,
          'clicks', greatest(
            coalesce(exact.metric_clicks, 0), exact.tracked_clicks
          ),
          'reported_clicks', exact.metric_clicks,
          'tracked_clicks', exact.tracked_clicks,
          'orders', exact.metric_orders,
          'revenue_minor', exact.metric_revenue_minor,
          'is_correction', exact.metric_is_correction,
          'correction_reason', exact.metric_correction_reason,
          'created_at', exact.metric_created_at
        )
      end as latest_metric
    from exact
  )
  select
    jsonb_build_object(
      'id', shaped.id,
      'project_id', shaped.project_id,
      'task_id', shaped.task_id,
      'title', coalesce(shaped.task_title, shaped.product_title),
      'product_name', shaped.product_title,
      'sku', shaped.sku,
      'platform', shaped.platform,
      'destination', shaped.destination_ref,
      'destination_ref', shaped.destination_ref,
      'status', shaped.status,
      'instructions', shaped.instructions,
      'tracking_url', shaped.tracking_url,
      'tracking_slug', shaped.metadata ->> 'tracking_slug',
      'tracking_target_url', shaped.metadata ->> 'tracking_target_url',
      'tracked_clicks', shaped.tracked_clicks,
      'final_url', shaped.final_url,
      'scheduled_at', shaped.scheduled_at,
      'published_at', shaped.published_at,
      'created_at', shaped.created_at,
      'updated_at', shaped.updated_at,
      '_cursor', jsonb_build_object(
        'at', shaped.created_at, 'id', shaped.id
      )
    ),
    jsonb_build_object(
      'id', shaped.id,
      'placement_id', shaped.id,
      'project_id', shaped.project_id,
      'title', shaped.product_title,
      'sku', shaped.sku,
      'platform', shaped.platform,
      'status', shaped.status,
      'final_url', shaped.final_url,
      'views', coalesce(shaped.metric_views, 0),
      'clicks', shaped.effective_clicks,
      'reported_clicks', coalesce(shaped.metric_clicks, 0),
      'tracked_clicks', shaped.tracked_clicks,
      'orders', coalesce(shaped.metric_orders, 0),
      'revenue_minor', coalesce(shaped.metric_revenue_minor, 0),
      'source', shaped.effective_source,
      'observed_at', shaped.metric_observed_at,
      'updated_at', shaped.updated_at,
      'latest_metric', shaped.latest_metric,
      '_cursor', jsonb_build_object(
        'at', shaped.updated_at, 'id', shaped.id
      )
    ),
    case
      when shaped.status <> 'published' then null
      else jsonb_build_object(
        'id', shaped.id,
        'placement_id', shaped.id,
        'project_id', shaped.project_id,
        'title', shaped.product_title,
        'sku', shaped.sku,
        'final_url', shaped.final_url,
        'tracking_slug', shaped.metadata ->> 'tracking_slug',
        'tracked_clicks', shaped.tracked_clicks,
        '_cursor', jsonb_build_object(
          'at', shaped.updated_at, 'id', shaped.id
        )
      )
    end,
    shaped.latest_metric
  into
    placement_value,
    publication_value,
    publication_option_value,
    latest_metric_value
  from shaped;

  if placement_value is null then
    raise exception using
      errcode = '42501', message = 'project_placement_not_visible';
  end if;

  return jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'placement_id', placement_id_value,
    'placement', placement_value,
    'publication', publication_value,
    'publication_option', publication_option_value,
    'latest_metric', latest_metric_value
  );
end;
$$;

revoke all on function public.creator_project_placement(jsonb)
  from public, anon;
grant execute on function public.creator_project_placement(jsonb)
  to authenticated;

-- Completing Academy makes a trainee eligible to ask a real manager for the
-- operational role. The request is durable and intentionally cannot change a
-- membership or manufacture a waiver by itself.
create table if not exists content_factory.workspace_access_requests (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  profile_id uuid not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'cancelled')),
  responsible_profile_id uuid,
  requested_role text not null default 'operator'
    check (requested_role = 'operator'),
  requested_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid references content_factory.profiles(id),
  resolution_note text
    check (
      resolution_note is null
      or length(btrim(resolution_note)) between 2 and 1000
    ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, profile_id)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (organization_id, responsible_profile_id)
    references content_factory.memberships(organization_id, profile_id),
  check (
    (status = 'pending' and resolved_at is null and resolved_by is null)
    or (status <> 'pending' and resolved_at is not null and resolved_by is not null)
  )
);

create unique index if not exists workspace_access_requests_pending_uq
  on content_factory.workspace_access_requests (
    organization_id, profile_id
  ) where status = 'pending';
create index if not exists workspace_access_requests_manager_queue_idx
  on content_factory.workspace_access_requests (
    organization_id, responsible_profile_id, status, requested_at, id
  );

alter table content_factory.workspace_access_requests enable row level security;
revoke all on content_factory.workspace_access_requests
  from public, anon, authenticated;

create or replace function public.creator_request_workspace_access(
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
  idempotency_key text;
  actor_role text;
  manager_profile_id uuid;
  manager_name text;
  manager_email text;
  manager_status text;
  request_row content_factory.workspace_access_requests%rowtype;
  replay jsonb;
  result jsonb;
  inserted_request boolean := false;
  request_payload jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if exists (
    select 1
    from jsonb_object_keys(p_payload) payload_key
    where payload_key <> all(array['organization_id', 'idempotency_key'])
  ) then
    raise exception using
      errcode = '22023', message = 'workspace_access_request_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_payload := p_payload - 'idempotency_key';

  -- The central gate verifies the active organization/profile/membership and
  -- every Academy requirement. Its installed waiver wrapper skips training
  -- only for a currently active, explicitly granted waiver.
  actor_role := content_factory_private.membership_role(
    organization_id, true, null
  );
  if actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer', 'operator'
  ]) then
    raise exception using
      errcode = '22023', message = 'workspace_access_already_open';
  end if;
  if actor_role <> 'trainee' then
    raise exception using
      errcode = '42501', message = 'workspace_access_request_role_not_allowed';
  end if;

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_request_workspace_access',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('workspace_access_request:' || user_id::text)
  );

  select request.* into request_row
  from content_factory.workspace_access_requests request
  where request.organization_id = organization_id
    and request.profile_id = user_id
    and request.status = 'pending'
  order by request.requested_at, request.id
  limit 1
  for update;

  if request_row.id is null then
    select membership.profile_id into manager_profile_id
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id
      and membership.status = 'active'
      and membership.role in ('owner', 'admin')
    order by
      case membership.role when 'owner' then 0 else 1 end,
      membership.created_at,
      membership.id
    limit 1;

    insert into content_factory.workspace_access_requests (
      organization_id,
      profile_id,
      status,
      responsible_profile_id,
      requested_role
    ) values (
      organization_id,
      user_id,
      'pending',
      manager_profile_id,
      'operator'
    ) returning * into request_row;
    inserted_request := true;
  end if;

  select
    profile.display_name,
    profile.email,
    case
      when request_row.responsible_profile_id is null then 'unassigned'
      when profile.status = 'active'
       and membership.status = 'active'
       and membership.role in ('owner', 'admin') then 'assigned'
      else 'unavailable'
    end
  into manager_name, manager_email, manager_status
  from (select 1) singleton
  left join content_factory.profiles profile
    on profile.id = request_row.responsible_profile_id
  left join content_factory.memberships membership
    on membership.organization_id = organization_id
   and membership.profile_id = request_row.responsible_profile_id;

  result := jsonb_build_object(
    'ok', true,
    'request', jsonb_build_object(
      'id', request_row.id,
      'status', request_row.status,
      'requested_role', request_row.requested_role,
      'requested_at', request_row.requested_at,
      'updated_at', request_row.updated_at
    ),
    'responsible_manager', jsonb_build_object(
      'profile_id', request_row.responsible_profile_id,
      'name', manager_name,
      'email', manager_email,
      'status', manager_status
    )
  );

  if inserted_request then
    perform content_factory_private.emit_event(
      organization_id,
      user_id,
      'workspace_access_requested',
      'workspace_access_request',
      request_row.id::text,
      jsonb_build_object(
        'requested_role', request_row.requested_role,
        'responsible_profile_id', request_row.responsible_profile_id,
        'responsible_manager_status', manager_status
      ),
      'workspace-access-request:' || request_row.id::text
    );
  end if;

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_request_workspace_access',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

revoke all on function public.creator_request_workspace_access(jsonb)
  from public, anon;
grant execute on function public.creator_request_workspace_access(jsonb)
  to authenticated;

-- Background notifications are durable navigation commands, not generic
-- section shortcuts. Resolve their project from the authoritative entity row
-- before insertion so terminal and watchdog outbox writers share one policy.
create or replace function
  content_factory_private.notification_entity_scope_v47(
    p_organization_id uuid,
    p_entity_type text,
    p_entity_id text
  )
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  entity_id_value uuid;
  project_id_value uuid;
  deep_link_value text;
  entity_query_value text;
begin
  if lower(coalesce(p_entity_type, '')) not in (
    'generation_job', 'content_review', 'product_research'
  ) or coalesce(p_entity_id, '') !~* (
    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-' ||
    '[0-9a-f]{4}-[0-9a-f]{12}$'
  ) then
    return null;
  end if;
  entity_id_value := p_entity_id::uuid;

  case lower(p_entity_type)
    when 'generation_job' then
      select job.project_id into project_id_value
      from content_factory.generation_jobs job
      where job.organization_id = p_organization_id
        and job.id = entity_id_value;
      entity_query_value := 'job_id';
      deep_link_value := '#/workspace/generation?project_id=' ||
        project_id_value::text || '&view=history&job=' ||
        entity_id_value::text;
    when 'content_review' then
      select review.project_id into project_id_value
      from content_factory.content_review_runs review
      where review.organization_id = p_organization_id
        and review.id = entity_id_value;
      entity_query_value := 'review_id';
      deep_link_value := '#/workspace/review?project_id=' ||
        project_id_value::text || '&view=current&review=' ||
        entity_id_value::text;
    when 'product_research' then
      select research.project_id into project_id_value
      from content_factory.product_research_runs research
      where research.organization_id = p_organization_id
        and research.id = entity_id_value;
      entity_query_value := 'run_id';
      deep_link_value := '#/workspace/research?project_id=' ||
        project_id_value::text || '&view=evidence&run=' ||
        entity_id_value::text;
    else
      return null;
  end case;

  if project_id_value is null then
    return null;
  end if;
  return jsonb_build_object(
    'project_id', project_id_value,
    'deep_link', deep_link_value,
    'entity_query', entity_query_value
  );
end;
$$;

create or replace function
  content_factory_private.scope_notification_outbox_v47()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  scope_value jsonb;
begin
  scope_value := content_factory_private.notification_entity_scope_v47(
    new.organization_id,
    new.entity_type,
    new.entity_id
  );
  if scope_value is null then
    return new;
  end if;

  new.deep_link := scope_value ->> 'deep_link';
  new.properties := coalesce(new.properties, '{}'::jsonb) ||
    jsonb_build_object(
      'project_id', scope_value ->> 'project_id',
      scope_value ->> 'entity_query', new.entity_id
    );
  new.request_hash := content_factory_private.json_hash(
    jsonb_build_object(
      'recipient_id', new.recipient_id,
      'kind', new.kind,
      'severity', new.severity,
      'title', new.title,
      'body', new.body,
      'deep_link', new.deep_link,
      'entity_type', new.entity_type,
      'entity_id', new.entity_id,
      'properties', new.properties
    )
  );
  return new;
end;
$$;

drop trigger if exists scope_notification_outbox_project_v47
  on content_factory.notification_outbox;
create trigger scope_notification_outbox_project_v47
before insert on content_factory.notification_outbox
for each row execute function
  content_factory_private.scope_notification_outbox_v47();

-- Rewrite both unresolved outbox work and already delivered inbox rows. The
-- immutable guards are removed only inside this migration transaction and are
-- restored immediately after each bounded, entity-joined rewrite.
drop trigger if exists guard_notification_outbox
  on content_factory.notification_outbox;
with scoped as (
  select
    outbox.id,
    scope.value ->> 'deep_link' as deep_link,
    coalesce(outbox.properties, '{}'::jsonb) || jsonb_build_object(
      'project_id', scope.value ->> 'project_id',
      scope.value ->> 'entity_query', outbox.entity_id
    ) as properties
  from content_factory.notification_outbox outbox
  cross join lateral (
    select content_factory_private.notification_entity_scope_v47(
      outbox.organization_id,
      outbox.entity_type,
      outbox.entity_id
    ) as value
  ) scope
  where scope.value is not null
)
update content_factory.notification_outbox outbox
set deep_link = scoped.deep_link,
    properties = scoped.properties,
    request_hash = content_factory_private.json_hash(jsonb_build_object(
      'recipient_id', outbox.recipient_id,
      'kind', outbox.kind,
      'severity', outbox.severity,
      'title', outbox.title,
      'body', outbox.body,
      'deep_link', scoped.deep_link,
      'entity_type', outbox.entity_type,
      'entity_id', outbox.entity_id,
      'properties', scoped.properties
    )),
    updated_at = now()
from scoped
where outbox.id = scoped.id;
create trigger guard_notification_outbox
before update or delete on content_factory.notification_outbox
for each row execute function
  content_factory_private.guard_notification_outbox();

drop trigger if exists guard_user_notification
  on content_factory.user_notifications;
with scoped as (
  select
    notification.id,
    scope.value ->> 'deep_link' as deep_link,
    coalesce(notification.properties, '{}'::jsonb) || jsonb_build_object(
      'project_id', scope.value ->> 'project_id',
      scope.value ->> 'entity_query', notification.entity_id
    ) as properties
  from content_factory.user_notifications notification
  cross join lateral (
    select content_factory_private.notification_entity_scope_v47(
      notification.organization_id,
      notification.entity_type,
      notification.entity_id
    ) as value
  ) scope
  where scope.value is not null
)
update content_factory.user_notifications notification
set deep_link = scoped.deep_link,
    properties = scoped.properties,
    request_hash = content_factory_private.json_hash(jsonb_build_object(
      'recipient_id', notification.recipient_id,
      'kind', notification.kind,
      'severity', notification.severity,
      'title', notification.title,
      'body', notification.body,
      'deep_link', scoped.deep_link,
      'entity_type', notification.entity_type,
      'entity_id', notification.entity_id,
      'properties', scoped.properties
    )),
    updated_at = now()
from scoped
where notification.id = scoped.id;
create trigger guard_user_notification
before update or delete on content_factory.user_notifications
for each row execute function
  content_factory_private.guard_user_notification();

-- Private helpers and preserved implementation aliases stay unreachable from
-- PostgREST callers. Public SECURITY DEFINER entrypoints above are the only
-- supported project boundary.
revoke all on function
  content_factory_private.notification_entity_scope_v47(uuid, text, text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.scope_notification_outbox_v47()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.workspace_project_for_folder(uuid, uuid)
  from public, anon, authenticated;
revoke all on function content_factory_private.guard_workspace_project_kind()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.merge_project_lineage(uuid, uuid)
  from public, anon, authenticated;
revoke all on function content_factory_private.guard_project_lineage()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.assign_workspace_location_project()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.require_workspace_project(uuid, uuid)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.project_flow_snapshot(uuid, uuid, uuid, text)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.require_project_entity(uuid, uuid, text, uuid)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.call_project_scoped_v47(
    text, jsonb, text, text, boolean
  ) from public, anon, authenticated;
revoke all on function
  content_factory_private.project_payload_from_context_v47(jsonb)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

commit;

begin;

create or replace function content_factory_private.json_hash(value jsonb)
returns text
language sql
immutable
strict
set search_path = ''
as $$
  select encode(extensions.digest(value::text, 'sha256'), 'hex')
$$;

create or replace function content_factory_private.require_payload(payload jsonb)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
begin
  if payload is null or jsonb_typeof(payload) <> 'object' then
    raise exception using errcode = '22023', message = 'payload_must_be_an_object';
  end if;
  return payload;
end;
$$;

create or replace function content_factory_private.validate_workspace_cursor(
  payload jsonb,
  allowed_keys text[]
)
returns void
language plpgsql
stable
set search_path = ''
as $$
declare
  cursor_entry record;
  parsed_at timestamptz;
  parsed_id uuid;
begin
  if not (payload ? 'cursor') then
    return;
  end if;
  if jsonb_typeof(payload -> 'cursor') <> 'object' then
    raise exception using errcode = '22023', message = 'workspace_cursor_invalid';
  end if;

  for cursor_entry in
    select entry.key, entry.value
    from jsonb_each(payload -> 'cursor') entry
  loop
    if not (cursor_entry.key = any(allowed_keys))
       or jsonb_typeof(cursor_entry.value) <> 'object'
       or nullif(btrim(coalesce(cursor_entry.value ->> 'at', '')), '') is null
       or nullif(btrim(coalesce(cursor_entry.value ->> 'id', '')), '') is null then
      raise exception using errcode = '22023', message = 'workspace_cursor_invalid';
    end if;
    begin
      parsed_at := (cursor_entry.value ->> 'at')::timestamptz;
      parsed_id := (cursor_entry.value ->> 'id')::uuid;
    exception
      when invalid_text_representation
        or invalid_datetime_format
        or datetime_field_overflow then
      raise exception using errcode = '22023', message = 'workspace_cursor_invalid';
    end;
  end loop;
end;
$$;

create or replace function public.creator_workspace_section(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  requested_section text;
  actor_role text;
  team_scope boolean;
  page_size integer := 50;
  max_page_size integer;
  team_cursor_at timestamptz;
  team_cursor_id uuid;
  generation_batches_cursor_at timestamptz;
  generation_batches_cursor_id uuid;
  generation_media_cursor_at timestamptz;
  generation_media_cursor_id uuid;
  generation_aliases_cursor_at timestamptz;
  generation_aliases_cursor_id uuid;
  placement_cursor_at timestamptz;
  placement_cursor_id uuid;
  stats_publications_cursor_at timestamptz;
  stats_publications_cursor_id uuid;
  stats_options_cursor_at timestamptz;
  stats_options_cursor_id uuid;
  payout_cursor_at timestamptz;
  payout_cursor_id uuid;
  tasks_cursor_at timestamptz;
  tasks_cursor_id uuid;
  media_cursor_at timestamptz;
  media_cursor_id uuid;
  feedback_cursor_at timestamptz;
  feedback_cursor_id uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  requested_section := content_factory_private.require_text(p_payload, 'section', 3, 40);
  actor_role := content_factory_private.membership_role(organization_id, true, null);
  team_scope := actor_role = any(array['owner', 'admin', 'producer', 'reviewer']);

  if requested_section not in (
    'generation', 'placement', 'stats', 'payouts',
    'tasks', 'media', 'feedback', 'team'
  ) then
    raise exception using errcode = '22023', message = 'workspace_section_invalid';
  end if;

  max_page_size := case when requested_section = 'team' then 200 else 100 end;
  if p_payload ? 'page_size' then
    if coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using errcode = '22023', message = 'workspace_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using errcode = '22023', message = 'workspace_page_size_invalid';
    end;
  end if;
  if page_size < 1 or page_size > max_page_size then
    raise exception using errcode = '22023', message = 'workspace_page_size_invalid';
  end if;
  if p_payload ? 'cursor' and jsonb_typeof(p_payload -> 'cursor') <> 'object' then
    raise exception using errcode = '22023', message = 'workspace_cursor_invalid';
  end if;
  perform content_factory_private.validate_workspace_cursor(
    p_payload,
    case requested_section
      when 'generation' then array[
        'generation_batches', 'generation_media', 'generation_wb_aliases'
      ]
      when 'placement' then array['placement_items']
      when 'stats' then array['stats_publications', 'stats_publication_options']
      when 'payouts' then array['payout_items']
      when 'tasks' then array['task_items']
      when 'media' then array['media_items']
      when 'feedback' then array['feedback_items']
      when 'team' then array['team_members']
    end
  );

  -- Decode the validated cursors once. Keeping the row tuple comparison in
  -- each query (rather than hiding it inside a boolean helper) lets PostgreSQL
  -- use the matching btree index for deep keyset pages.
  team_cursor_at := (p_payload #>> '{cursor,team_members,at}')::timestamptz;
  team_cursor_id := (p_payload #>> '{cursor,team_members,id}')::uuid;
  generation_batches_cursor_at :=
    (p_payload #>> '{cursor,generation_batches,at}')::timestamptz;
  generation_batches_cursor_id :=
    (p_payload #>> '{cursor,generation_batches,id}')::uuid;
  generation_media_cursor_at :=
    (p_payload #>> '{cursor,generation_media,at}')::timestamptz;
  generation_media_cursor_id :=
    (p_payload #>> '{cursor,generation_media,id}')::uuid;
  generation_aliases_cursor_at :=
    (p_payload #>> '{cursor,generation_wb_aliases,at}')::timestamptz;
  generation_aliases_cursor_id :=
    (p_payload #>> '{cursor,generation_wb_aliases,id}')::uuid;
  placement_cursor_at := (p_payload #>> '{cursor,placement_items,at}')::timestamptz;
  placement_cursor_id := (p_payload #>> '{cursor,placement_items,id}')::uuid;
  stats_publications_cursor_at :=
    (p_payload #>> '{cursor,stats_publications,at}')::timestamptz;
  stats_publications_cursor_id :=
    (p_payload #>> '{cursor,stats_publications,id}')::uuid;
  stats_options_cursor_at :=
    (p_payload #>> '{cursor,stats_publication_options,at}')::timestamptz;
  stats_options_cursor_id :=
    (p_payload #>> '{cursor,stats_publication_options,id}')::uuid;
  payout_cursor_at := (p_payload #>> '{cursor,payout_items,at}')::timestamptz;
  payout_cursor_id := (p_payload #>> '{cursor,payout_items,id}')::uuid;
  tasks_cursor_at := (p_payload #>> '{cursor,task_items,at}')::timestamptz;
  tasks_cursor_id := (p_payload #>> '{cursor,task_items,id}')::uuid;
  media_cursor_at := (p_payload #>> '{cursor,media_items,at}')::timestamptz;
  media_cursor_id := (p_payload #>> '{cursor,media_items,id}')::uuid;
  feedback_cursor_at := (p_payload #>> '{cursor,feedback_items,at}')::timestamptz;
  feedback_cursor_id := (p_payload #>> '{cursor,feedback_items,id}')::uuid;

  if requested_section = 'team' then
    if actor_role <> all(array['owner', 'admin']) then
      raise exception using errcode = '42501', message = 'role_not_allowed';
    end if;

    with member_page as materialized (
      select
        membership.id,
        membership.organization_id,
        membership.profile_id,
        membership.role,
        membership.status,
        membership.created_at,
        profile.display_name,
        profile.email
      from content_factory.memberships membership
      join content_factory.profiles profile on profile.id = membership.profile_id
      where membership.organization_id = organization_id
        and (
          team_cursor_at is null
          or (membership.created_at, membership.id) < (team_cursor_at, team_cursor_id)
        )
      order by membership.created_at desc, membership.id desc
      limit page_size
    ),
    course_requirement as (
      select count(*) as courses_required
      from content_factory.training_modules module
      where module.module_type = 'course'
        and module.is_active
    ),
    certification_stats as (
      select
        member.profile_id,
        count(distinct certification.module_code) filter (
          where module.module_type = 'course'
        ) as courses_completed,
        coalesce(bool_or(module.module_type = 'exam'), false) as exam_passed
      from member_page member
      left join content_factory.training_certifications certification
        on certification.organization_id = member.organization_id
       and certification.profile_id = member.profile_id
       and certification.status = 'passed'
       and (certification.expires_at is null or certification.expires_at > now())
      left join content_factory.training_modules module
        on module.code = certification.module_code
       and module.is_active
      group by member.profile_id
    ),
    task_stats as (
      select
        member.profile_id,
        count(task.id) as tasks_total,
        count(task.id) filter (where task.status = 'done') as tasks_done
      from member_page member
      left join content_factory.creator_tasks task
        on task.organization_id = member.organization_id
       and task.assignee_id = member.profile_id
      group by member.profile_id
    ),
    placement_stats as (
      select
        member.profile_id,
        count(placement.id) filter (
          where placement.status = 'published'
        ) as published_count
      from member_page member
      left join content_factory.placements placement
        on placement.organization_id = member.organization_id
       and placement.assigned_to = member.profile_id
      group by member.profile_id
    )
    select jsonb_build_object(
      'members', coalesce(jsonb_agg(jsonb_build_object(
        'id', member.id,
        'profile_id', member.profile_id,
        'display_name', member.display_name,
        'email', member.email,
        'role', member.role,
        'status', member.status,
        'joined_at', member.created_at,
        '_cursor', jsonb_build_object('at', member.created_at, 'id', member.id),
        'courses_completed', certification.courses_completed,
        'courses_required', requirement.courses_required,
        'exam_passed', certification.exam_passed,
        'tasks_total', task.tasks_total,
        'tasks_done', task.tasks_done,
        'published_count', placement.published_count
      ) order by member.created_at desc, member.id desc), '[]'::jsonb)
    ) into result
    from member_page member
    cross join course_requirement requirement
    join certification_stats certification using (profile_id)
    join task_stats task using (profile_id)
    join placement_stats placement using (profile_id);
  elsif requested_section = 'generation' then
    select jsonb_build_object(
      'batches', (
        select coalesce(jsonb_agg(jsonb_build_object(
          'id', batch.id,
          'public_id', batch.id,
          'name', batch.name,
          'sku', product.sku,
          'product_name', product.title,
          'mode', batch.mode,
          'status', batch.status,
          'total_requested', batch.total_requested,
          'total_created', batch.total_created,
          'total_accepted', batch.total_created,
          'parameters', batch.input,
          'created_at', batch.created_at,
          '_cursor', jsonb_build_object('at', batch.created_at, 'id', batch.id)
        ) order by batch.created_at desc, batch.id desc), '[]'::jsonb)
        from content_factory.generation_batches batch
        join content_factory.products product
          on product.organization_id = batch.organization_id
         and product.id = batch.product_id
        where batch.organization_id = organization_id
          and (team_scope or batch.created_by = user_id)
          and batch.id in (
            select candidate.id
            from content_factory.generation_batches candidate
            where candidate.organization_id = organization_id
              and (team_scope or candidate.created_by = user_id)
              and (
                generation_batches_cursor_at is null
                or (candidate.created_at, candidate.id) <
                  (generation_batches_cursor_at, generation_batches_cursor_id)
              )
            order by candidate.created_at desc, candidate.id desc
            limit page_size
          )
      ),
      'media', (
        select coalesce(jsonb_agg(jsonb_build_object(
          'id', media.id,
          'public_id', media.id,
          'original_filename', media.metadata ->> 'original_filename',
          'kind', media.metadata ->> 'kind',
          'mime_type', media.mime_type,
          'size_bytes', media.size_bytes,
          'status', media.status,
          'created_at', media.created_at,
          '_cursor', jsonb_build_object('at', media.created_at, 'id', media.id)
        ) order by media.created_at desc, media.id desc), '[]'::jsonb)
        from content_factory.media_objects media
        where media.organization_id = organization_id
          and media.status = 'ready'
          and (team_scope or media.owner_id = user_id)
          and media.id in (
            select candidate.id
            from content_factory.media_objects candidate
            where candidate.organization_id = organization_id
              and candidate.status = 'ready'
              and (team_scope or candidate.owner_id = user_id)
              and (
                generation_media_cursor_at is null
                or (candidate.created_at, candidate.id) <
                  (generation_media_cursor_at, generation_media_cursor_id)
              )
            order by candidate.created_at desc, candidate.id desc
            limit page_size
          )
      ),
      'wb_aliases', (
        select coalesce(jsonb_agg(jsonb_build_object(
          'id', alias.id,
          'sku', product.sku,
          'current_article', alias.current_article,
          'alias_article', alias.alias_article,
          'status', alias.status,
          'reason', alias.reason,
          'valid_from', alias.valid_from,
          'valid_to', alias.valid_to,
          '_cursor', jsonb_build_object('at', alias.valid_from, 'id', alias.id)
        ) order by alias.valid_from desc, alias.id desc), '[]'::jsonb)
        from content_factory.wb_article_aliases alias
        join content_factory.products product
          on product.organization_id = alias.organization_id
         and product.id = alias.product_id
        where alias.organization_id = organization_id
          and alias.id in (
            select candidate.id
            from content_factory.wb_article_aliases candidate
            where candidate.organization_id = organization_id
              and (
                generation_aliases_cursor_at is null
                or (candidate.valid_from, candidate.id) <
                  (generation_aliases_cursor_at, generation_aliases_cursor_id)
              )
            order by candidate.valid_from desc, candidate.id desc
            limit page_size
          )
      )
    ) into result;
  elsif requested_section = 'placement' then
    select jsonb_build_object(
      'placements', coalesce(jsonb_agg(jsonb_build_object(
        'id', placement.id,
        'task_id', placement.task_id,
        'title', coalesce(task.title, product.title),
        'product_name', product.title,
        'sku', product.sku,
        'platform', placement.platform,
        'destination', placement.destination_ref,
        'destination_ref', placement.destination_ref,
        'status', placement.status,
        'instructions', task.instructions,
        'tracking_url', placement.tracking_url,
        'final_url', placement.final_url,
        'scheduled_at', placement.scheduled_at,
        'published_at', placement.published_at,
        'created_at', placement.created_at,
        '_cursor', jsonb_build_object('at', placement.created_at, 'id', placement.id)
      ) order by placement.created_at desc, placement.id desc), '[]'::jsonb)
    ) into result
    from content_factory.placements placement
    join content_factory.products product
      on product.organization_id = placement.organization_id
     and product.id = placement.product_id
    left join content_factory.creator_tasks task
      on task.organization_id = placement.organization_id
     and task.id = placement.task_id
    where placement.organization_id = organization_id
      and (team_scope or placement.assigned_to = user_id)
      and placement.id in (
        select candidate.id
        from content_factory.placements candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.assigned_to = user_id)
          and (
            placement_cursor_at is null
            or (candidate.created_at, candidate.id) <
              (placement_cursor_at, placement_cursor_id)
          )
        order by candidate.created_at desc, candidate.id desc
        limit page_size
      );
  elsif requested_section = 'stats' then
    with scoped as (
      select
        placement.id,
        placement.platform,
        placement.status,
        placement.final_url,
        placement.published_at,
        placement.updated_at,
        product.sku,
        product.title,
        snapshot.source,
        snapshot.views,
        snapshot.clicks,
        snapshot.orders,
        snapshot.revenue_minor,
        snapshot.observed_at
      from content_factory.placements placement
      join content_factory.products product
        on product.organization_id = placement.organization_id
       and product.id = placement.product_id
      left join lateral (
        select metric.*
        from content_factory.metric_snapshots metric
        where metric.organization_id = placement.organization_id
          and metric.placement_id = placement.id
        order by metric.observed_at desc, metric.created_at desc
        limit 1
      ) snapshot on true
      where placement.organization_id = organization_id
        and (team_scope or placement.assigned_to = user_id)
        and (
          stats_publications_cursor_at is null
          or (placement.updated_at, placement.id) <
            (stats_publications_cursor_at, stats_publications_cursor_id)
        )
      order by placement.updated_at desc, placement.id desc
      limit page_size
    )
    select jsonb_build_object(
      'summary_scope', 'page',
      'summary', jsonb_build_object(
        'published', count(*) filter (where status = 'published'),
        'views', coalesce(sum(views), 0),
        'clicks', coalesce(sum(clicks), 0),
        'orders', coalesce(sum(orders), 0),
        'revenue_minor', coalesce(sum(revenue_minor), 0),
        'ctr', case
          when coalesce(sum(views), 0) > 0
          then round(coalesce(sum(clicks), 0)::numeric * 100 / sum(views), 2)
          else 0
        end
      ),
      'publications', coalesce(jsonb_agg(jsonb_build_object(
        'id', id,
        'placement_id', id,
        'title', title,
        'sku', sku,
        'platform', platform,
        'status', status,
        'final_url', final_url,
        'views', coalesce(views, 0),
        'clicks', coalesce(clicks, 0),
        'orders', coalesce(orders, 0),
        'revenue_minor', coalesce(revenue_minor, 0),
        'source', source,
        'observed_at', observed_at,
        'updated_at', updated_at,
        '_cursor', jsonb_build_object('at', updated_at, 'id', id)
      ) order by updated_at desc, id desc), '[]'::jsonb)
    ) into result
    from scoped;

    result := result || jsonb_build_object(
      'publication_options', (
        select coalesce(jsonb_agg(jsonb_build_object(
          'id', publication_option.id,
          'placement_id', publication_option.id,
          'title', publication_option.title,
          'sku', publication_option.sku,
          'final_url', publication_option.final_url,
          '_cursor', jsonb_build_object(
            'at', publication_option.updated_at,
            'id', publication_option.id
          )
        ) order by publication_option.updated_at desc, publication_option.id desc), '[]'::jsonb)
        from (
          select
            placement.id,
            placement.final_url,
            placement.updated_at,
            product.sku,
            product.title
          from content_factory.placements placement
          join content_factory.products product
            on product.organization_id = placement.organization_id
           and product.id = placement.product_id
          where placement.organization_id = organization_id
            and placement.status = 'published'
            and (team_scope or placement.assigned_to = user_id)
            and (
              stats_options_cursor_at is null
              or (placement.updated_at, placement.id) <
                (stats_options_cursor_at, stats_options_cursor_id)
            )
          order by placement.updated_at desc, placement.id desc
          limit page_size
        ) publication_option
      )
    );
  elsif requested_section = 'payouts' then
    select jsonb_build_object(
      'payouts', coalesce(jsonb_agg(jsonb_build_object(
        'id', payout.id,
        'payout_id', payout.id,
        'profile_id', payout.profile_id,
        'profile_name', coalesce(profile.display_name, profile.email),
        'task_id', payout.task_id,
        'task_title', task.title,
        'amount_minor', payout.amount_minor,
        'currency', payout.currency,
        'status', payout.status,
        'reason', payout.reason,
        'external_payment_reference', payout.external_payment_reference,
        'created_at', payout.created_at,
        'approved_at', payout.approved_at,
        'paid_at', payout.paid_at,
        '_cursor', jsonb_build_object('at', payout.created_at, 'id', payout.id)
      ) order by payout.created_at desc, payout.id desc), '[]'::jsonb)
    ) into result
    from content_factory.creator_payouts payout
    join content_factory.profiles profile on profile.id = payout.profile_id
    join content_factory.creator_tasks task
      on task.organization_id = payout.organization_id
     and task.id = payout.task_id
    where payout.organization_id = organization_id
      and (actor_role = any(array['owner', 'admin']) or payout.profile_id = user_id)
      and payout.id in (
        select candidate.id
        from content_factory.creator_payouts candidate
        where candidate.organization_id = organization_id
          and (actor_role = any(array['owner', 'admin']) or candidate.profile_id = user_id)
          and (
            payout_cursor_at is null
            or (candidate.created_at, candidate.id) <
              (payout_cursor_at, payout_cursor_id)
          )
        order by candidate.created_at desc, candidate.id desc
        limit page_size
      );
  elsif requested_section = 'tasks' then
    select jsonb_build_object(
      'tasks', coalesce(jsonb_agg(jsonb_build_object(
        'id', task.id,
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
      ) order by task.created_at desc, task.id desc), '[]'::jsonb)
    ) into result
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and (team_scope or task.assignee_id = user_id)
      and task.id in (
        select candidate.id
        from content_factory.creator_tasks candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.assignee_id = user_id)
          and (
            tasks_cursor_at is null
            or (candidate.created_at, candidate.id) <
              (tasks_cursor_at, tasks_cursor_id)
          )
        order by candidate.created_at desc, candidate.id desc
        limit page_size
      );
  elsif requested_section = 'media' then
    select jsonb_build_object(
      'media', coalesce(jsonb_agg(jsonb_build_object(
        'id', media.id,
        'public_id', media.id,
        'object_key', media.object_name,
        'original_filename', media.metadata ->> 'original_filename',
        'kind', media.metadata ->> 'kind',
        'mime_type', media.mime_type,
        'size_bytes', media.size_bytes,
        'sha256', media.sha256,
        'status', media.status,
        'created_at', media.created_at,
        '_cursor', jsonb_build_object('at', media.created_at, 'id', media.id)
      ) order by media.created_at desc, media.id desc), '[]'::jsonb)
    ) into result
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.status <> 'deleted'
      and (team_scope or media.owner_id = user_id)
      and media.id in (
        select candidate.id
        from content_factory.media_objects candidate
        where candidate.organization_id = organization_id
          and candidate.status <> 'deleted'
          and (team_scope or candidate.owner_id = user_id)
          and (
            media_cursor_at is null
            or (candidate.created_at, candidate.id) <
              (media_cursor_at, media_cursor_id)
          )
        order by candidate.created_at desc, candidate.id desc
        limit page_size
      );
  else
    select jsonb_build_object(
      'feedback', coalesce(jsonb_agg(jsonb_build_object(
        'id', feedback.id,
        'category', feedback.category,
        'title', feedback.title,
        'description', feedback.details,
        'status', feedback.status,
        'created_at', feedback.created_at,
        'updated_at', feedback.updated_at,
        '_cursor', jsonb_build_object('at', feedback.created_at, 'id', feedback.id)
      ) order by feedback.created_at desc, feedback.id desc), '[]'::jsonb)
    ) into result
    from content_factory.feedback_requests feedback
    where feedback.organization_id = organization_id
      and (team_scope or feedback.profile_id = user_id)
      and feedback.id in (
        select candidate.id
        from content_factory.feedback_requests candidate
        where candidate.organization_id = organization_id
          and (team_scope or candidate.profile_id = user_id)
          and (
            feedback_cursor_at is null
            or (candidate.created_at, candidate.id) <
              (feedback_cursor_at, feedback_cursor_id)
          )
        order by candidate.created_at desc, candidate.id desc
        limit page_size
      );
  end if;

  return coalesce(result, '{}'::jsonb) || jsonb_build_object(
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'default_page_size', 50,
      'cap', max_page_size,
      'cursor_mode', 'keyset_at_id'
    )
  );
end;
$$;

-- Every workspace collection uses the same descending keyset shape. These
-- indexes include the UUID tie-breaker so pagination remains index-backed
-- when an organization grows well beyond the first 50 creators/items.
create index if not exists memberships_workspace_page_idx
  on content_factory.memberships (organization_id, created_at desc, id desc);
create index if not exists generation_batches_workspace_org_page_idx
  on content_factory.generation_batches (organization_id, created_at desc, id desc);
create index if not exists generation_batches_workspace_owner_page_idx
  on content_factory.generation_batches
  (organization_id, created_by, created_at desc, id desc);
create index if not exists wb_article_aliases_workspace_page_idx
  on content_factory.wb_article_aliases
  (organization_id, valid_from desc, id desc);
create index if not exists placements_workspace_org_created_page_idx
  on content_factory.placements (organization_id, created_at desc, id desc);
create index if not exists placements_workspace_assignee_created_page_idx
  on content_factory.placements
  (organization_id, assigned_to, created_at desc, id desc);
create index if not exists placements_workspace_org_updated_page_idx
  on content_factory.placements (organization_id, updated_at desc, id desc);
create index if not exists placements_workspace_assignee_updated_page_idx
  on content_factory.placements
  (organization_id, assigned_to, updated_at desc, id desc);
create index if not exists placements_open_generation_job_idx
  on content_factory.placements (organization_id, generation_job_id)
  where status in ('scheduled', 'ready');
create index if not exists creator_payouts_workspace_org_page_idx
  on content_factory.creator_payouts (organization_id, created_at desc, id desc);
create index if not exists creator_payouts_workspace_profile_page_idx
  on content_factory.creator_payouts
  (organization_id, profile_id, created_at desc, id desc);
create index if not exists creator_tasks_workspace_org_page_idx
  on content_factory.creator_tasks (organization_id, created_at desc, id desc);
create index if not exists creator_tasks_workspace_assignee_page_idx
  on content_factory.creator_tasks
  (organization_id, assignee_id, created_at desc, id desc);
create index if not exists media_objects_workspace_org_page_idx
  on content_factory.media_objects (organization_id, created_at desc, id desc)
  where status <> 'deleted';
create index if not exists media_objects_workspace_owner_page_idx
  on content_factory.media_objects
  (organization_id, owner_id, created_at desc, id desc)
  where status <> 'deleted';
create index if not exists feedback_requests_workspace_org_page_idx
  on content_factory.feedback_requests (organization_id, created_at desc, id desc);
create index if not exists feedback_requests_workspace_profile_page_idx
  on content_factory.feedback_requests
  (organization_id, profile_id, created_at desc, id desc);

create or replace function content_factory_private.require_text(
  payload jsonb,
  field_name text,
  minimum_length integer default 1,
  maximum_length integer default 1000
)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  result text;
begin
  result := btrim(coalesce(payload ->> field_name, ''));
  if length(result) < minimum_length or length(result) > maximum_length then
    raise exception using
      errcode = '22023',
      message = field_name || '_invalid';
  end if;
  return result;
end;
$$;

create or replace function content_factory_private.require_uuid(
  payload jsonb,
  field_name text
)
returns uuid
language plpgsql
immutable
set search_path = ''
as $$
declare
  result uuid;
begin
  begin
    result := nullif(btrim(coalesce(payload ->> field_name, '')), '')::uuid;
  exception when invalid_text_representation then
    result := null;
  end;
  if result is null then
    raise exception using errcode = '22023', message = field_name || '_invalid';
  end if;
  return result;
end;
$$;

create or replace function content_factory_private.current_profile_id()
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  user_id uuid := auth.uid();
  user_email text;
  user_name text;
  profile_status text;
begin
  if user_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  select lower(auth_user.email),
         nullif(btrim(coalesce(auth_user.raw_user_meta_data ->> 'display_name', '')), '')
    into user_email, user_name
  from auth.users auth_user
  where auth_user.id = user_id;

  if user_email is null then
    raise exception using errcode = '42501', message = 'verified_email_required';
  end if;

  insert into content_factory.profiles (id, email, display_name)
  values (user_id, user_email, user_name)
  on conflict (id) do update set
    email = excluded.email,
    display_name = coalesce(content_factory.profiles.display_name, excluded.display_name),
    updated_at = now();

  select status into profile_status
  from content_factory.profiles
  where id = user_id;

  if profile_status <> 'active' then
    raise exception using errcode = '42501', message = 'profile_not_active';
  end if;

  return user_id;
end;
$$;

create or replace function content_factory_private.resolve_organization(payload jsonb)
returns uuid
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  explicit_value text := nullif(btrim(coalesce(payload ->> 'organization_id', '')), '');
  result uuid;
  membership_count integer;
begin
  if explicit_value is not null then
    begin
      result := explicit_value::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023', message = 'organization_id_invalid';
    end;
    return result;
  end if;

  select count(*), (array_agg(membership.organization_id order by membership.created_at))[1]
    into membership_count, result
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  where membership.profile_id = auth.uid()
    and membership.status = 'active';

  if membership_count <> 1 or result is null then
    raise exception using errcode = '22023', message = 'organization_id_required';
  end if;
  return result;
end;
$$;

create or replace function content_factory_private.membership_role(
  organization_id uuid,
  require_certification boolean default false,
  allowed_roles text[] default null
)
returns text
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  user_id uuid := auth.uid();
  actor_role text;
begin
  if user_id is null then
    raise exception using errcode = '42501', message = 'authentication_required';
  end if;

  select membership.role into actor_role
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
   and organization.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = membership_role.organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';

  if actor_role is null then
    raise exception using errcode = '42501', message = 'active_membership_required';
  end if;

  if allowed_roles is not null and not (actor_role = any(allowed_roles)) then
    raise exception using errcode = '42501', message = 'role_not_allowed';
  end if;

  if require_certification and not exists (
    select 1
    from content_factory.training_certifications certification
    where certification.organization_id = membership_role.organization_id
      and certification.profile_id = user_id
      and certification.module_code = 'operator_final_exam'
      and certification.status = 'passed'
      and (certification.expires_at is null or certification.expires_at > now())
  ) then
    raise exception using errcode = '42501', message = 'final_exam_required';
  end if;

  return actor_role;
end;
$$;

create or replace function content_factory_private.normalize_answer(value jsonb)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  normalized jsonb;
begin
  if value is null then
    return '[]'::jsonb;
  end if;

  if length(value::text) > 4000
     or (jsonb_typeof(value) = 'array' and jsonb_array_length(value) > 12) then
    raise exception using errcode = '22023', message = 'answer_value_invalid';
  end if;

  if jsonb_typeof(value) = 'string' then
    return jsonb_build_array(btrim(value #>> '{}'));
  end if;

  if jsonb_typeof(value) <> 'array' then
    return '[]'::jsonb;
  end if;

  select coalesce(jsonb_agg(item order by item), '[]'::jsonb)
    into normalized
  from (
    select distinct btrim(answer.value) as item
    from jsonb_array_elements_text(value) answer(value)
    where btrim(answer.value) <> ''
  ) canonical;

  return normalized;
end;
$$;

create or replace function content_factory_private.begin_command(
  organization_id uuid,
  command_name text,
  idempotency_key text,
  request_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  stored_hash text;
  stored_result jsonb;
  request_hash text := content_factory_private.json_hash(request_payload);
begin
  if length(idempotency_key) < 8 or length(idempotency_key) > 180 then
    raise exception using errcode = '22023', message = 'idempotency_key_invalid';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(command_name || ':' || idempotency_key)
  );

  select receipt.request_hash, receipt.result
    into stored_hash, stored_result
  from content_factory.command_receipts receipt
  where receipt.organization_id = begin_command.organization_id
    and receipt.command_name = begin_command.command_name
    and receipt.idempotency_key = begin_command.idempotency_key;

  if stored_hash is not null and stored_hash <> request_hash then
    raise exception using errcode = '23505', message = 'idempotency_key_conflict';
  end if;

  return stored_result;
end;
$$;

create or replace function content_factory_private.finish_command(
  organization_id uuid,
  actor_id uuid,
  command_name text,
  idempotency_key text,
  request_payload jsonb,
  result_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.command_receipts (
    organization_id, actor_id, command_name, idempotency_key, request_hash, result
  ) values (
    organization_id,
    actor_id,
    command_name,
    idempotency_key,
    content_factory_private.json_hash(request_payload),
    result_payload
  )
  on conflict on constraint command_receipts_org_command_key_uq do nothing;
  return result_payload;
end;
$$;

create or replace function content_factory_private.emit_event(
  organization_id uuid,
  profile_id uuid,
  event_name text,
  entity_type text,
  entity_id text,
  properties jsonb,
  idempotency_key text,
  event_source text default 'server_rpc'
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.factory_events (
    organization_id, profile_id, event_name, source,
    entity_type, entity_id, properties, idempotency_key
  ) values (
    organization_id, profile_id, event_name, event_source,
    entity_type, entity_id, coalesce(properties, '{}'::jsonb),
    left(idempotency_key, 180)
  )
  on conflict on constraint factory_events_org_key_uq do nothing;
end;
$$;

-- Trusted one-time initialization. Browser roles cannot execute this RPC;
-- it is intended for a service-role deployment/bootstrap call only.
create or replace function public.system_initialize_owner(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  target_user_id uuid;
  idempotency_key text;
  organization_name text;
  organization_slug text;
  bootstrap_key text;
  target_email text;
  target_display_name text;
  target_email_confirmed_at timestamptz;
  target_banned_until timestamptz;
  target_deleted_at timestamptz;
  target_profile_status text;
  organization_count integer;
  organization_row content_factory.organizations%rowtype;
  membership_row content_factory.memberships%rowtype;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  target_user_id := content_factory_private.require_uuid(p_payload, 'user_id');
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  organization_name := coalesce(
    nullif(btrim(p_payload ->> 'organization_name'), ''),
    'ALTEA Content Factory'
  );
  organization_slug := lower(coalesce(
    nullif(btrim(p_payload ->> 'organization_slug'), ''),
    'altea-content-factory'
  ));

  if length(organization_name) not between 2 and 180
     or organization_slug !~ '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$' then
    raise exception using errcode = '22023', message = 'organization_identity_invalid';
  end if;

  request_payload := jsonb_build_object(
    'user_id', target_user_id,
    'organization_name', organization_name,
    'organization_slug', organization_slug
  );
  bootstrap_key := 'system-owner:' || content_factory_private.json_hash(
    to_jsonb(idempotency_key)
  );

  perform pg_advisory_xact_lock(hashtext('content_factory_system_initialize_owner'));

  select
    lower(auth_user.email),
    nullif(btrim(coalesce(auth_user.raw_user_meta_data ->> 'display_name', '')), ''),
    auth_user.email_confirmed_at,
    auth_user.banned_until,
    auth_user.deleted_at
  into
    target_email,
    target_display_name,
    target_email_confirmed_at,
    target_banned_until,
    target_deleted_at
  from auth.users auth_user
  where auth_user.id = target_user_id;

  if target_email is null then
    raise exception using errcode = 'P0002', message = 'target_auth_user_not_found';
  end if;
  if target_email_confirmed_at is null then
    raise exception using errcode = '42501', message = 'target_email_not_confirmed';
  end if;
  if target_deleted_at is not null
     or (target_banned_until is not null and target_banned_until > now()) then
    raise exception using errcode = '42501', message = 'target_auth_user_not_active';
  end if;

  insert into content_factory.profiles (id, email, display_name)
  values (target_user_id, target_email, target_display_name)
  on conflict (id) do update set
    email = excluded.email,
    display_name = coalesce(content_factory.profiles.display_name, excluded.display_name),
    updated_at = now();

  select profile.status into target_profile_status
  from content_factory.profiles profile
  where profile.id = target_user_id;
  if target_profile_status <> 'active' then
    raise exception using errcode = '42501', message = 'target_profile_not_active';
  end if;

  select organization.* into organization_row
  from content_factory.organizations organization
  where organization.bootstrap_idempotency_key = bootstrap_key
  for update;

  if organization_row.id is not null then
    select membership.* into membership_row
    from content_factory.memberships membership
    where membership.organization_id = organization_row.id
      and membership.profile_id = target_user_id
    for update;

    if organization_row.status <> 'active'
       or membership_row.id is null
       or membership_row.status <> 'active'
       or membership_row.role <> 'owner' then
      raise exception using errcode = '55000', message = 'owner_initialization_state_conflict';
    end if;

    replay := content_factory_private.begin_command(
      organization_row.id,
      'system_initialize_owner',
      idempotency_key,
      request_payload
    );
    if replay is null then
      raise exception using errcode = '55000', message = 'owner_initialization_receipt_missing';
    end if;
    return replay;
  end if;

  if exists (
    select 1
    from content_factory.memberships membership
    where membership.profile_id = target_user_id
  ) then
    raise exception using errcode = '23505', message = 'target_membership_history_conflict';
  end if;

  select count(*) into organization_count
  from content_factory.organizations;
  if organization_count <> 0 or exists (
    select 1
    from content_factory.memberships membership
    where membership.role = 'owner'
  ) then
    raise exception using errcode = '55000', message = 'content_factory_already_initialized';
  end if;

  insert into content_factory.organizations (
    name,
    slug,
    status,
    bootstrap_idempotency_key
  ) values (
    organization_name,
    organization_slug,
    'active',
    bootstrap_key
  )
  returning * into organization_row;

  insert into content_factory.memberships (
    organization_id,
    profile_id,
    role,
    status
  ) values (
    organization_row.id,
    target_user_id,
    'owner',
    'active'
  )
  returning * into membership_row;

  result := jsonb_build_object(
    'ok', true,
    'organization_id', organization_row.id,
    'user_id', target_user_id,
    'membership_id', membership_row.id,
    'role', 'owner',
    'status', 'active'
  );

  perform content_factory_private.emit_event(
    organization_row.id,
    target_user_id,
    'owner_initialized',
    'membership',
    membership_row.id::text,
    jsonb_build_object('target_user_id', target_user_id),
    'system-owner:' || idempotency_key,
    'system'
  );

  return content_factory_private.finish_command(
    organization_row.id,
    target_user_id,
    'system_initialize_owner',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

-- Trusted invitation provisioning. The authenticated Edge Function creates
-- (or identifies) the auth user, then its service-role client calls this RPC.
create or replace function public.system_provision_invited_member(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  target_user_id uuid;
  invited_by_id uuid;
  idempotency_key text;
  target_email text;
  target_display_name text;
  target_invited_at timestamptz;
  target_email_confirmed_at timestamptz;
  target_banned_until timestamptz;
  target_deleted_at timestamptz;
  target_profile_status text;
  inviter_role text;
  membership_row content_factory.memberships%rowtype;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.require_uuid(p_payload, 'organization_id');
  target_user_id := content_factory_private.require_uuid(p_payload, 'user_id');
  invited_by_id := content_factory_private.require_uuid(p_payload, 'invited_by');
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  request_payload := jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'invited_by', invited_by_id,
    'role', 'trainee'
  );

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('system_invite:' || target_user_id::text)
  );

  if not exists (
    select 1
    from content_factory.organizations organization
    where organization.id = organization_id
      and organization.status = 'active'
  ) then
    raise exception using errcode = '42501', message = 'organization_not_active';
  end if;

  select
    lower(auth_user.email),
    nullif(btrim(coalesce(auth_user.raw_user_meta_data ->> 'display_name', '')), ''),
    auth_user.invited_at,
    auth_user.email_confirmed_at,
    auth_user.banned_until,
    auth_user.deleted_at
  into
    target_email,
    target_display_name,
    target_invited_at,
    target_email_confirmed_at,
    target_banned_until,
    target_deleted_at
  from auth.users auth_user
  where auth_user.id = target_user_id;

  if target_email is null then
    raise exception using errcode = 'P0002', message = 'target_auth_user_not_found';
  end if;
  if target_invited_at is null and target_email_confirmed_at is null then
    raise exception using errcode = '42501', message = 'target_auth_user_not_invited';
  end if;
  if target_deleted_at is not null
     or (target_banned_until is not null and target_banned_until > now()) then
    raise exception using errcode = '42501', message = 'target_auth_user_not_active';
  end if;

  insert into content_factory.profiles (id, email, display_name)
  values (target_user_id, target_email, target_display_name)
  on conflict (id) do update set
    email = excluded.email,
    display_name = coalesce(content_factory.profiles.display_name, excluded.display_name),
    updated_at = now();

  select profile.status into target_profile_status
  from content_factory.profiles profile
  where profile.id = target_user_id;
  if target_profile_status <> 'active' then
    raise exception using errcode = '42501', message = 'target_profile_not_active';
  end if;

  select membership.role into inviter_role
  from content_factory.memberships membership
  join content_factory.profiles inviter_profile
    on inviter_profile.id = membership.profile_id
   and inviter_profile.status = 'active'
  where membership.organization_id = organization_id
    and membership.profile_id = invited_by_id
    and membership.status = 'active'
    and membership.role in ('owner', 'admin')
    and exists (
      select 1
      from content_factory.training_certifications certification
      where certification.organization_id = organization_id
        and certification.profile_id = invited_by_id
        and certification.module_code = 'operator_final_exam'
        and certification.status = 'passed'
        and (certification.expires_at is null or certification.expires_at > now())
    );

  if inviter_role is null then
    raise exception using errcode = '42501', message = 'inviter_not_authorized';
  end if;

  select membership.* into membership_row
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = target_user_id
  for update;

  if membership_row.id is not null then
    if membership_row.status <> 'active' then
      raise exception using errcode = '23505', message = 'target_membership_history_conflict';
    end if;
    replay := content_factory_private.begin_command(
      organization_id,
      'system_provision_invited_member',
      idempotency_key,
      request_payload
    );
    if replay is not null then
      return replay;
    end if;

    result := jsonb_build_object(
      'ok', true,
      'organization_id', organization_id,
      'user_id', target_user_id,
      'membership_id', membership_row.id,
      'role', membership_row.role,
      'status', membership_row.status,
      'already_active', true
    );

    perform content_factory_private.emit_event(
      organization_id,
      invited_by_id,
      'member_invite_reconciled',
      'membership',
      membership_row.id::text,
      jsonb_build_object(
        'target_user_id', target_user_id,
        'role', membership_row.role,
        'already_active', true
      ),
      'system-invite:' || idempotency_key,
      'system'
    );

    return content_factory_private.finish_command(
      organization_id,
      invited_by_id,
      'system_provision_invited_member',
      idempotency_key,
      request_payload,
      result
    );
  end if;

  replay := content_factory_private.begin_command(
    organization_id,
    'system_provision_invited_member',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    raise exception using errcode = '55000', message = 'invitation_provisioning_state_conflict';
  end if;

  insert into content_factory.memberships (
    organization_id,
    profile_id,
    role,
    status
  ) values (
    organization_id,
    target_user_id,
    'trainee',
    'active'
  )
  returning * into membership_row;

  result := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'user_id', target_user_id,
    'membership_id', membership_row.id,
    'role', 'trainee',
    'status', 'active'
  );

  perform content_factory_private.emit_event(
    organization_id,
    invited_by_id,
    'member_invited_provisioned',
    'membership',
    membership_row.id::text,
    jsonb_build_object(
      'target_user_id', target_user_id,
      'role', 'trainee'
    ),
    'system-invite:' || idempotency_key,
    'system'
  );

  return content_factory_private.finish_command(
    organization_id,
    invited_by_id,
    'system_provision_invited_member',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

-- Safe reconciliation for an Auth user that already existed before the
-- invitation attempt. Only a unique, confirmed, active exact normalized email
-- is resolved; provisioning still passes through the same guarded RPC.
create or replace function public.system_reconcile_invited_member(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  invited_by_id uuid;
  email_value text;
  target_count integer;
  target_user_id uuid;
  target_email_confirmed_at timestamptz;
  target_banned_until timestamptz;
  target_deleted_at timestamptz;
  stable_idempotency_key text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.require_uuid(p_payload, 'organization_id');
  invited_by_id := content_factory_private.require_uuid(p_payload, 'invited_by');
  email_value := lower(content_factory_private.require_text(
    p_payload,
    'email',
    3,
    320
  ));

  if email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
    raise exception using errcode = '22023', message = 'email_invalid';
  end if;

  select count(*), (array_agg(auth_user.id order by auth_user.id))[1]
    into target_count, target_user_id
  from auth.users auth_user
  where lower(btrim(auth_user.email)) = email_value;

  if target_count = 0 or target_user_id is null then
    raise exception using errcode = 'P0002', message = 'reconciliation_auth_user_not_found';
  end if;
  if target_count <> 1 then
    raise exception using errcode = '55000', message = 'reconciliation_auth_user_ambiguous';
  end if;

  select
    auth_user.email_confirmed_at,
    auth_user.banned_until,
    auth_user.deleted_at
  into
    target_email_confirmed_at,
    target_banned_until,
    target_deleted_at
  from auth.users auth_user
  where auth_user.id = target_user_id;

  if target_email_confirmed_at is null then
    raise exception using errcode = '42501', message = 'reconciliation_email_not_confirmed';
  end if;
  if target_deleted_at is not null
     or (target_banned_until is not null and target_banned_until > now()) then
    raise exception using errcode = '42501', message = 'target_auth_user_not_active';
  end if;

  stable_idempotency_key := 'reconcile:' || content_factory_private.json_hash(
    jsonb_build_object(
      'organization_id', organization_id,
      'user_id', target_user_id
    )
  );

  return public.system_provision_invited_member(jsonb_build_object(
    'organization_id', organization_id,
    'user_id', target_user_id,
    'invited_by', invited_by_id,
    'idempotency_key', stable_idempotency_key
  ));
end;
$$;

create or replace function public.creator_bootstrap(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  membership_row content_factory.memberships%rowtype;
  organization_row content_factory.organizations%rowtype;
  exam_module content_factory.training_modules%rowtype;
  requested_organization_id uuid;
  courses_required integer := 0;
  active_module_count integer := 0;
  courses_completed integer;
  exam_passed boolean;
  exam_attempt_count integer := 0;
  exam_attempt_count_24h integer := 0;
  oldest_attempt_24h timestamptz;
  last_failed_at timestamptz;
  next_attempt_at timestamptz;
  cooldown_minutes integer := 15;
  completed_modules jsonb := '[]'::jsonb;
  learning_modules jsonb;
  exam_questions jsonb := '[]'::jsonb;
  exam_question_count integer := 0;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if nullif(btrim(coalesce(p_payload ->> 'organization_id', '')), '') is not null then
    requested_organization_id := content_factory_private.require_uuid(
      p_payload,
      'organization_id'
    );
  end if;

  select membership.* into membership_row
  from content_factory.memberships membership
  where membership.profile_id = user_id
    and (
      requested_organization_id is null
      or membership.organization_id = requested_organization_id
    )
  order by
    case membership.status
      when 'active' then 1 when 'suspended' then 2 when 'revoked' then 3 else 4
    end,
    case membership.role
      when 'owner' then 1 when 'admin' then 2 when 'producer' then 3
      when 'reviewer' then 4 when 'operator' then 5 when 'trainee' then 6 else 7
    end,
    membership.created_at
  limit 1;

  if membership_row.id is null then
    return jsonb_build_object(
      'authenticated', true,
      'state', 'membership_required',
      'profile', (
        select jsonb_build_object(
          'id', profile.id,
          'email', profile.email,
          'display_name', profile.display_name
        )
        from content_factory.profiles profile
        where profile.id = user_id
      ),
      'membership', null,
      'workspace_open', false
    );
  end if;

  select * into organization_row
  from content_factory.organizations
  where id = membership_row.organization_id;

  if membership_row.status <> 'active' then
    return jsonb_build_object(
      'authenticated', true,
      'state', case membership_row.status
        when 'suspended' then 'membership_suspended'
        when 'revoked' then 'membership_revoked'
        else 'membership_required'
      end,
      'profile', (
        select jsonb_build_object(
          'id', profile.id,
          'email', profile.email,
          'display_name', profile.display_name
        )
        from content_factory.profiles profile
        where profile.id = user_id
      ),
      'organization', jsonb_build_object(
        'id', organization_row.id,
        'name', organization_row.name,
        'slug', organization_row.slug,
        'status', organization_row.status
      ),
      'membership', jsonb_build_object(
        'id', membership_row.id,
        'role', membership_row.role,
        'status', membership_row.status
      ),
      'workspace_open', false
    );
  end if;

  if organization_row.id is null or organization_row.status <> 'active' then
    return jsonb_build_object(
      'authenticated', true,
      'state', case organization_row.status
        when 'suspended' then 'organization_suspended'
        when 'closed' then 'organization_closed'
        else 'organization_unavailable'
      end,
      'profile', (
        select jsonb_build_object(
          'id', profile.id,
          'email', profile.email,
          'display_name', profile.display_name
        )
        from content_factory.profiles profile
        where profile.id = user_id
      ),
      'organization', case
        when organization_row.id is null then null
        else jsonb_build_object(
          'id', organization_row.id,
          'name', organization_row.name,
          'slug', organization_row.slug,
          'status', organization_row.status
        )
      end,
      'membership', jsonb_build_object(
        'id', membership_row.id,
        'role', membership_row.role,
        'status', membership_row.status
      ),
      'workspace_open', false
    );
  end if;

  select
    count(*) filter (where module.module_type = 'course'),
    count(*)
  into courses_required, active_module_count
  from content_factory.training_modules module
  where module.is_active;

  if active_module_count > 64 then
    raise exception using errcode = '54000', message = 'active_training_catalog_limit_exceeded';
  end if;

  select count(distinct certification.module_code) into courses_completed
  from content_factory.training_certifications certification
  join content_factory.training_modules module
    on module.code = certification.module_code
   and module.module_type = 'course'
   and module.is_active
  where certification.organization_id = organization_row.id
    and certification.profile_id = user_id
    and certification.status = 'passed'
    and (certification.expires_at is null or certification.expires_at > now());

  select coalesce(jsonb_agg(certified.module_code order by certified.order_index), '[]'::jsonb)
    into completed_modules
  from (
    select distinct module.code as module_code, module.order_index
    from content_factory.training_certifications certification
    join content_factory.training_modules module
      on module.code = certification.module_code
     and module.is_active
    where certification.organization_id = organization_row.id
      and certification.profile_id = user_id
      and certification.status = 'passed'
      and (certification.expires_at is null or certification.expires_at > now())
  ) certified;

  select module.* into exam_module
  from content_factory.training_modules module
  where module.module_type = 'exam'
    and module.is_active
  order by module.order_index
  limit 1;

  if exam_module.code is null then
    raise exception using errcode = '55000', message = 'exam_catalog_unavailable';
  end if;

  select count(*) into exam_question_count
  from content_factory.training_questions question
  where question.module_code = exam_module.code;

  if exam_module.question_count < 1
     or exam_module.question_count > 100
     or exam_question_count <> exam_module.question_count then
    raise exception using errcode = '55000', message = 'exam_catalog_unavailable';
  end if;

  if coalesce(exam_module.content ->> 'cooldown_minutes', '') ~ '^[0-9]+$' then
    cooldown_minutes := greatest(
      1,
      least(1440, (exam_module.content ->> 'cooldown_minutes')::integer)
    );
  end if;

  select exists (
    select 1
    from content_factory.training_certifications certification
    where certification.organization_id = organization_row.id
      and certification.profile_id = user_id
      and certification.module_code = exam_module.code
      and certification.status = 'passed'
      and (certification.expires_at is null or certification.expires_at > now())
  ) into exam_passed;

  select
    count(*),
    count(*) filter (where attempt.completed_at > now() - interval '24 hours'),
    min(attempt.completed_at) filter (where attempt.completed_at > now() - interval '24 hours'),
    max(attempt.completed_at) filter (where not attempt.passed)
    into exam_attempt_count, exam_attempt_count_24h, oldest_attempt_24h, last_failed_at
  from content_factory.training_attempts attempt
  where attempt.organization_id = organization_row.id
    and attempt.profile_id = user_id
    and attempt.module_code = exam_module.code
    and attempt.status = 'completed';

  if not exam_passed
     and last_failed_at is not null
     and last_failed_at + make_interval(mins => cooldown_minutes) > now() then
    next_attempt_at := last_failed_at + make_interval(mins => cooldown_minutes);
  end if;
  if not exam_passed
     and exam_attempt_count_24h >= 5
     and oldest_attempt_24h + interval '24 hours' > now() then
    next_attempt_at := greatest(
      coalesce(next_attempt_at, '-infinity'::timestamptz),
      oldest_attempt_24h + interval '24 hours'
    );
  end if;

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'code', module.code,
      'type', module.module_type,
      'title', module.title,
      'description', module.description,
      'order', module.order_index,
      'content', module.content,
      'completed', exists (
        select 1
        from content_factory.training_certifications certification
        where certification.organization_id = organization_row.id
          and certification.profile_id = user_id
          and certification.module_code = module.code
          and certification.status = 'passed'
          and (certification.expires_at is null or certification.expires_at > now())
      ),
      'available', module.module_type = 'course'
        or (courses_required > 0 and courses_completed = courses_required and next_attempt_at is null)
    ) order by module.order_index
  ), '[]'::jsonb)
  into learning_modules
  from content_factory.training_modules module
  where module.is_active;

  if courses_required > 0
     and courses_completed = courses_required
     and not exam_passed
     and next_attempt_at is null then
    select coalesce(jsonb_agg(
      jsonb_build_object(
        'code', question.code,
        'type', question.question_type,
        'prompt', question.prompt,
        'options', question.options,
        'order', question.order_index
      ) order by question.order_index
    ), '[]'::jsonb)
    into exam_questions
    from content_factory.training_questions question
    where question.module_code = exam_module.code;
  end if;

  result := jsonb_build_object(
    'authenticated', true,
    'state', case when exam_passed then 'workspace' else 'learning' end,
    'profile', (
      select jsonb_build_object(
        'id', profile.id,
        'email', profile.email,
        'display_name', profile.display_name
      )
      from content_factory.profiles profile
      where profile.id = user_id
    ),
    'organization', jsonb_build_object(
      'id', organization_row.id,
      'name', organization_row.name,
      'slug', organization_row.slug
    ),
    'membership', jsonb_build_object(
      'id', membership_row.id,
      'role', membership_row.role,
      'status', membership_row.status
    ),
    'learning', jsonb_build_object(
      'courses_completed', courses_completed,
      'courses_required', courses_required,
      'completed_modules', completed_modules,
      'modules', learning_modules,
      'exam', jsonb_build_object(
        'code', exam_module.code,
        'available', courses_required > 0
          and courses_completed = courses_required
          and not exam_passed
          and next_attempt_at is null,
        'passed', exam_passed,
        'pass_score', exam_module.pass_score,
        'question_count', exam_module.question_count,
        'attempt_count', exam_attempt_count,
        'attempt_count_24h', exam_attempt_count_24h,
        'next_attempt_at', next_attempt_at,
        'questions', exam_questions
      )
    ),
    'workspace_open', exam_passed,
    'storage', jsonb_build_object(
      'bucket', 'contentengine-private',
      'path_prefix', organization_row.id::text || '/' || user_id::text || '/'
    ),
    'capabilities', jsonb_build_object(
      'real_generation', false,
      'mock_generation', exam_passed and membership_row.role in ('owner', 'admin', 'producer', 'operator'),
      'team_view', membership_row.role in ('owner', 'admin', 'producer', 'reviewer')
    )
  );

  return result;
end;
$$;

create or replace function public.creator_complete_module(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  course_code text;
  idempotency_key text;
  replay jsonb;
  attempt_id uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  course_code := content_factory_private.require_text(p_payload, 'module_code', 3, 80);
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  perform content_factory_private.membership_role(organization_id, false, null);

  if not exists (
    select 1 from content_factory.training_modules module
    where module.code = course_code
      and module.module_type = 'course'
      and module.is_active
  ) then
    raise exception using errcode = '22023', message = 'course_not_found';
  end if;

  replay := content_factory_private.begin_command(
    organization_id, 'creator_complete_module', idempotency_key,
    p_payload - 'idempotency_key'
  );
  if replay is not null then return replay; end if;

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, score,
    correct_count, answered_count, question_count, passed,
    answers, request_hash, idempotency_key
  ) values (
    organization_id, user_id, course_code, 1,
    0, 0, 0, true,
    '{}'::jsonb,
    content_factory_private.json_hash(p_payload - 'idempotency_key'),
    left('course:' || idempotency_key, 180)
  )
  returning id into attempt_id;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    organization_id, user_id, course_code, attempt_id, 'passed'
  )
  on conflict on constraint training_certifications_org_profile_module_uq do update set
    attempt_id = excluded.attempt_id,
    status = 'passed',
    granted_at = now(),
    expires_at = null;

  result := jsonb_build_object(
    'ok', true,
    'module_code', course_code,
    'completed', true,
    'attempt_id', attempt_id
  );

  perform content_factory_private.emit_event(
    organization_id, user_id, 'training_course_completed',
    'training_module', course_code,
    jsonb_build_object('module_code', course_code),
    'course:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_complete_module', idempotency_key,
    p_payload - 'idempotency_key', result
  );
end;
$$;

create or replace function public.creator_submit_exam(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  exam_code text;
  idempotency_key text;
  answers jsonb;
  request_payload jsonb;
  replay jsonb;
  prerequisite_required integer;
  prerequisite_count integer;
  total_count integer;
  answered_count integer;
  correct_count integer;
  required_correct integer;
  declared_question_count integer;
  cooldown_minutes integer := 15;
  attempts_24h integer := 0;
  oldest_attempt_24h timestamptz;
  latest_failed_at timestamptz;
  cooldown_until timestamptz;
  passed boolean;
  score numeric(6,5);
  attempt_id uuid;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  exam_code := coalesce(
    nullif(btrim(p_payload ->> 'module_code'), ''),
    'operator_final_exam'
  );
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  answers := coalesce(p_payload -> 'answers', '{}'::jsonb);
  if jsonb_typeof(answers) <> 'object' then
    raise exception using errcode = '22023', message = 'answers_must_be_an_object';
  end if;
  if (select count(*) from jsonb_object_keys(answers)) > 100
     or length(answers::text) > 64000 then
    raise exception using errcode = '22023', message = 'exam_answers_invalid';
  end if;
  request_payload := jsonb_build_object(
    'answers', answers,
    'module_code', exam_code
  );
  perform content_factory_private.membership_role(organization_id, false, null);

  select count(*) into prerequisite_required
  from content_factory.training_modules module
  where module.module_type = 'course'
    and module.is_active;

  select count(*) into prerequisite_count
  from content_factory.training_certifications certification
  join content_factory.training_modules module
    on module.code = certification.module_code
   and module.module_type = 'course'
   and module.is_active
  where certification.organization_id = organization_id
    and certification.profile_id = user_id
    and certification.status = 'passed'
    and (certification.expires_at is null or certification.expires_at > now());

  if prerequisite_required = 0 or prerequisite_count <> prerequisite_required then
    raise exception using errcode = '42501', message = 'required_courses_incomplete';
  end if;

  replay := content_factory_private.begin_command(
    organization_id, 'creator_submit_exam', idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  -- Different idempotency keys must still serialize per learner/exam so the
  -- rolling attempt limit and cooldown cannot be raced in parallel tabs.
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('creator_exam:' || exam_code)
  );

  select
    module.pass_score,
    module.question_count,
    case
      when coalesce(module.content ->> 'cooldown_minutes', '') ~ '^[0-9]+$'
      then greatest(1, least(1440, (module.content ->> 'cooldown_minutes')::integer))
      else 15
    end
  into required_correct, declared_question_count, cooldown_minutes
  from content_factory.training_modules module
  where module.code = exam_code
    and module.module_type = 'exam'
    and module.is_active;

  if required_correct is null or declared_question_count is null then
    raise exception using errcode = '55000', message = 'exam_catalog_unavailable';
  end if;

  if exists (
    select 1
    from content_factory.training_certifications certification
    where certification.organization_id = organization_id
      and certification.profile_id = user_id
      and certification.module_code = exam_code
      and certification.status = 'passed'
      and (certification.expires_at is null or certification.expires_at > now())
  ) then
    select attempt.id, attempt.correct_count, attempt.question_count, attempt.score
      into attempt_id, correct_count, total_count, score
    from content_factory.training_attempts attempt
    where attempt.organization_id = organization_id
      and attempt.profile_id = user_id
      and attempt.module_code = exam_code
      and attempt.passed
    order by attempt.completed_at desc
    limit 1;

    result := jsonb_build_object(
      'ok', true,
      'attempt_id', attempt_id,
      'answered_count', total_count,
      'question_count', total_count,
      'correct_count', correct_count,
      'required_correct', required_correct,
      'score_percent', round(coalesce(score, 0) * 100, 2),
      'passed', true,
      'workspace_open', true
    );

    return content_factory_private.finish_command(
      organization_id, user_id, 'creator_submit_exam', idempotency_key,
      request_payload, result
    );
  end if;

  select
    count(*) filter (where attempt.completed_at > now() - interval '24 hours'),
    min(attempt.completed_at) filter (where attempt.completed_at > now() - interval '24 hours'),
    max(attempt.completed_at) filter (where not attempt.passed)
    into attempts_24h, oldest_attempt_24h, latest_failed_at
  from content_factory.training_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.module_code = exam_code
    and attempt.status = 'completed';

  if attempts_24h >= 5
     and oldest_attempt_24h + interval '24 hours' > now() then
    raise exception using
      errcode = '55000',
      message = 'exam_attempt_limit_active',
      detail = (oldest_attempt_24h + interval '24 hours')::text;
  end if;

  cooldown_until := latest_failed_at + make_interval(mins => cooldown_minutes);
  if cooldown_until is not null and cooldown_until > now() then
    raise exception using
      errcode = '55000',
      message = 'exam_cooldown_active',
      detail = cooldown_until::text;
  end if;

  select
    count(*),
    count(*) filter (
      where jsonb_array_length(
        content_factory_private.normalize_answer(answers -> question.code)
      ) > 0
    ),
    count(*) filter (
      where content_factory_private.normalize_answer(answers -> question.code)
        = content_factory_private.normalize_answer(answer_key.correct_answers)
    )
  into total_count, answered_count, correct_count
  from content_factory.training_questions question
  join content_factory_private.training_answer_keys answer_key
    on answer_key.question_code = question.code
  where question.module_code = exam_code;

  if total_count = 0 or total_count <> declared_question_count then
    raise exception using errcode = '55000', message = 'exam_catalog_unavailable';
  end if;

  if exists (
    select 1
    from jsonb_object_keys(answers) submitted(question_code)
    where not exists (
      select 1
      from content_factory.training_questions question
      where question.module_code = exam_code
        and question.code = submitted.question_code
    )
  ) then
    raise exception using errcode = '22023', message = 'unknown_exam_question';
  end if;

  passed := answered_count = total_count and correct_count >= required_correct;
  score := correct_count::numeric / total_count::numeric;

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, score,
    correct_count, answered_count, question_count, passed,
    answers, request_hash, idempotency_key
  ) values (
    organization_id, user_id, exam_code, score,
    correct_count, answered_count, total_count, passed,
    answers,
    content_factory_private.json_hash(jsonb_build_object('answers', answers)),
    left('exam:' || idempotency_key, 180)
  )
  returning id into attempt_id;

  if passed then
    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      organization_id, user_id, exam_code, attempt_id, 'passed'
    )
    on conflict on constraint training_certifications_org_profile_module_uq do update set
      attempt_id = excluded.attempt_id,
      status = 'passed',
      granted_at = now(),
      expires_at = null;

    update content_factory.memberships membership
    set role = 'operator', updated_at = now()
    where membership.organization_id = organization_id
      and membership.profile_id = user_id
      and membership.status = 'active'
      and membership.role = 'trainee';
  end if;

  result := jsonb_build_object(
    'ok', true,
    'attempt_id', attempt_id,
    'answered_count', answered_count,
    'question_count', total_count,
    'correct_count', correct_count,
    'required_correct', required_correct,
    'score_percent', round(score * 100, 2),
    'passed', passed,
    'workspace_open', passed,
    'next_attempt_at', case
      when passed then null
      else now() + make_interval(mins => cooldown_minutes)
    end
  );

  perform content_factory_private.emit_event(
    organization_id, user_id,
    case when passed then 'final_exam_passed' else 'final_exam_failed' end,
    'training_attempt', attempt_id::text,
    jsonb_build_object(
      'correct_count', correct_count,
      'question_count', total_count,
      'passed', passed
    ),
    'exam:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_submit_exam', idempotency_key,
    request_payload, result
  );
end;
$$;

create or replace function public.creator_create_mock_batch(p_payload jsonb default '{}'::jsonb)
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
  sku_value text;
  product_name text;
  brief_value text;
  format_value text;
  platform_value text;
  destination_value text;
  requested_count integer;
  payout_value bigint := 0;
  media_ids jsonb;
  media_value text;
  media_id uuid;
  exact_media_found boolean := false;
  assignee_id_value uuid;
  product_id uuid;
  batch_id uuid;
  job_id uuid;
  task_id_value uuid;
  ordinal integer;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
  team_scope boolean;
  user_variants_15m bigint;
  organization_variants_15m bigint;
  user_variants_24h bigint;
  organization_variants_24h bigint;
  assignee_open_jobs bigint;
  organization_open_jobs bigint;
  assignee_open_tasks bigint;
  organization_open_tasks bigint;
  assignee_open_placements bigint;
  organization_open_placements bigint;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  team_scope := actor_role = any(array['owner', 'admin', 'producer']);
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  sku_value := content_factory_private.require_text(p_payload, 'sku', 1, 120);
  product_name := content_factory_private.require_text(p_payload, 'product_name', 2, 180);
  brief_value := btrim(coalesce(p_payload ->> 'brief', ''));
  format_value := coalesce(nullif(btrim(p_payload ->> 'format'), ''), '9:16');
  platform_value := content_factory_private.require_text(p_payload, 'platform', 2, 40);
  destination_value := content_factory_private.require_text(p_payload, 'destination_ref', 2, 240);
  media_ids := coalesce(p_payload -> 'media_ids', '[]'::jsonb);
  assignee_id_value := user_id;

  if nullif(btrim(coalesce(p_payload ->> 'assignee_id', '')), '') is not null then
    assignee_id_value := content_factory_private.require_uuid(p_payload, 'assignee_id');
  end if;
  if coalesce(p_payload ->> 'payout_minor', '0') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'payout_minor_invalid';
  end if;
  begin
    payout_value := coalesce(p_payload ->> 'payout_minor', '0')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'payout_minor_invalid';
  end;

  if length(brief_value) > 1200 then
    raise exception using errcode = '22023', message = 'brief_invalid';
  end if;
  if format_value not in ('9:16', '1:1', '16:9') then
    raise exception using errcode = '22023', message = 'format_invalid';
  end if;
  if platform_value not in ('instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries') then
    raise exception using errcode = '22023', message = 'platform_invalid';
  end if;
  if payout_value < 0 or payout_value > 1000000 then
    raise exception using errcode = '22023', message = 'payout_minor_invalid';
  end if;
  if actor_role not in ('owner', 'admin') and payout_value <> 0 then
    raise exception using errcode = '42501', message = 'payout_role_not_allowed';
  end if;
  if actor_role = 'operator' and assignee_id_value <> user_id then
    raise exception using errcode = '42501', message = 'assignee_role_not_allowed';
  end if;
  if not exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id
      and membership.profile_id = assignee_id_value
      and membership.status = 'active'
      and exists (
        select 1
        from content_factory.training_certifications certification
        join content_factory.training_modules module
          on module.code = certification.module_code
         and module.module_type = 'exam'
         and module.is_active
        where certification.organization_id = membership.organization_id
          and certification.profile_id = membership.profile_id
          and certification.status = 'passed'
          and (certification.expires_at is null or certification.expires_at > now())
      )
  ) then
    raise exception using errcode = '42501', message = 'certified_assignee_required';
  end if;
  if coalesce(p_payload ->> 'count', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'count_invalid';
  end if;
  begin
    requested_count := (p_payload ->> 'count')::integer;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'count_invalid';
  end;
  if requested_count < 1 or requested_count > 50 then
    raise exception using errcode = '22023', message = 'count_invalid';
  end if;
  if jsonb_typeof(media_ids) <> 'array'
     or jsonb_array_length(media_ids) < 1
     or jsonb_array_length(media_ids) > 50 then
    raise exception using errcode = '22023', message = 'exact_product_media_required';
  end if;

  if coalesce(p_payload ->> 'mode', '') <> 'mock'
     or p_payload -> 'allow_real_spend' is distinct from 'false'::jsonb
     or coalesce(p_payload ->> 'spend_confirmation', '') <> 'MOCK_ONLY' then
    raise exception using errcode = '42501', message = 'mock_only_required';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_create_mock_batch',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  -- Serialize quota decisions before creating the batch or entering the
  -- requested_count loop. This prevents parallel 50-item requests from all
  -- observing the same remaining capacity.
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('mock_batch_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('mock_batch_quota:user')
  );

  select
    coalesce(sum(batch.total_requested) filter (
      where batch.created_by = user_id
        and batch.created_at >= now() - interval '15 minutes'
    ), 0),
    coalesce(sum(batch.total_requested) filter (
      where batch.created_at >= now() - interval '15 minutes'
    ), 0),
    coalesce(sum(batch.total_requested) filter (
      where batch.created_by = user_id
        and batch.created_at >= now() - interval '24 hours'
    ), 0),
    coalesce(sum(batch.total_requested), 0)
  into
    user_variants_15m,
    organization_variants_15m,
    user_variants_24h,
    organization_variants_24h
  from content_factory.generation_batches batch
  where batch.organization_id = organization_id
    and batch.created_at >= now() - interval '24 hours';

  if user_variants_15m + requested_count > 200 then
    raise exception using errcode = '54000', message = 'mock_batch_user_15m_quota_exceeded';
  end if;
  if organization_variants_15m + requested_count > 3000 then
    raise exception using errcode = '54000', message = 'mock_batch_organization_15m_quota_exceeded';
  end if;
  if user_variants_24h + requested_count > 1000 then
    raise exception using errcode = '54000', message = 'mock_batch_user_daily_quota_exceeded';
  end if;
  if organization_variants_24h + requested_count > 25000 then
    raise exception using errcode = '54000', message = 'mock_batch_organization_daily_quota_exceeded';
  end if;

  select
    count(distinct job.id) filter (where job.assigned_to = assignee_id_value),
    count(distinct job.id)
  into assignee_open_jobs, organization_open_jobs
  from content_factory.generation_jobs job
  join content_factory.placements open_placement
    on open_placement.organization_id = job.organization_id
   and open_placement.generation_job_id = job.id
   and open_placement.status in ('scheduled', 'ready')
  where job.organization_id = organization_id;

  select
    count(*) filter (where task.assignee_id = assignee_id_value),
    count(*)
  into assignee_open_tasks, organization_open_tasks
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.status in ('todo', 'in_progress', 'submitted', 'review', 'blocked');

  select
    count(*) filter (where placement.assigned_to = assignee_id_value),
    count(*)
  into assignee_open_placements, organization_open_placements
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.status in ('scheduled', 'ready');

  if assignee_open_jobs + requested_count > 250 then
    raise exception using errcode = '54000', message = 'mock_batch_assignee_open_jobs_quota_exceeded';
  end if;
  if organization_open_jobs + requested_count > 5000 then
    raise exception using errcode = '54000', message = 'mock_batch_organization_open_jobs_quota_exceeded';
  end if;
  if assignee_open_tasks + requested_count > 250 then
    raise exception using errcode = '54000', message = 'mock_batch_assignee_open_tasks_quota_exceeded';
  end if;
  if organization_open_tasks + requested_count > 5000 then
    raise exception using errcode = '54000', message = 'mock_batch_organization_open_tasks_quota_exceeded';
  end if;
  if assignee_open_placements + requested_count > 250 then
    raise exception using errcode = '54000', message = 'mock_batch_assignee_open_placements_quota_exceeded';
  end if;
  if organization_open_placements + requested_count > 5000 then
    raise exception using errcode = '54000', message = 'mock_batch_organization_open_placements_quota_exceeded';
  end if;

  insert into content_factory.products (
    organization_id, sku, title, status, created_by
  ) values (
    organization_id, sku_value, product_name, 'active', user_id
  )
  on conflict on constraint products_org_sku_uq do update set
    title = excluded.title,
    status = 'active',
    updated_at = now()
  returning id into product_id;

  for media_value in
    select value from jsonb_array_elements_text(media_ids)
  loop
    begin
      media_id := media_value::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023', message = 'media_id_invalid';
    end;

    if not exists (
      select 1
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.id = media_id
        and media.status = 'ready'
        and media.product_id = product_id
        and (team_scope or media.owner_id = user_id)
    ) then
      raise exception using errcode = '42501', message = 'exact_product_media_mismatch';
    end if;

    if exists (
      select 1
      from content_factory.media_objects media
      where media.organization_id = organization_id
        and media.id = media_id
        and media.status = 'ready'
        and media.product_id = product_id
        and media.metadata ->> 'kind' in ('product_photo', 'packshot')
        and (team_scope or media.owner_id = user_id)
    ) then
      exact_media_found := true;
    end if;
  end loop;

  if not exact_media_found then
    raise exception using errcode = '22023', message = 'exact_product_media_required';
  end if;

  insert into content_factory.generation_batches (
    organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key
  ) values (
    organization_id,
    product_id,
    user_id,
    left('Mock ' || sku_value || ' · ' || requested_count::text || ' variants', 180),
    'mock',
    false,
    'mock_ready',
    requested_count,
    requested_count,
    jsonb_build_object(
      'sku', sku_value,
      'product_name', product_name,
      'format', format_value,
      'brief', brief_value,
      'media_ids', media_ids,
      'platform', platform_value,
      'destination_ref', destination_value,
      'assigned_to', assignee_id_value,
      'payout_minor', payout_value,
      'spend_confirmation', 'MOCK_ONLY'
    ),
    content_factory_private.json_hash(request_payload),
    idempotency_key
  )
  returning id into batch_id;

  for ordinal in 1..requested_count loop
    insert into content_factory.generation_jobs (
      organization_id, product_id, batch_id, ordinal,
      requested_by, assigned_to, mode, provider, allow_real_spend,
      estimated_cost_minor, actual_cost_minor, status,
      input, output, request_hash, idempotency_key
    ) values (
      organization_id,
      product_id,
      batch_id,
      ordinal,
      user_id,
      assignee_id_value,
      'mock',
      'mock',
      false,
      0,
      0,
      'mock_ready',
      jsonb_build_object(
        'sku', sku_value,
        'format', format_value,
        'brief', brief_value,
        'media_ids', media_ids,
        'ordinal', ordinal
      ),
      jsonb_build_object(
        'mode', 'mock',
        'provider_called', false,
        'paid_spend_minor', 0
      ),
      content_factory_private.json_hash(
        request_payload || jsonb_build_object('ordinal', ordinal)
      ),
      'job:' || content_factory_private.json_hash(jsonb_build_object(
        'idempotency_key', idempotency_key,
        'ordinal', ordinal
      ))
    )
    returning id into job_id;

    insert into content_factory.creator_tasks (
      organization_id, assignee_id, created_by, product_id,
      generation_job_id, task_type, title, instructions,
      status, priority, payout_minor, result, idempotency_key
    ) values (
      organization_id,
      assignee_id_value,
      user_id,
      product_id,
      job_id,
      'placement',
      left('Разместить mock variant ' || ordinal::text || ' · ' || product_name, 240),
      'Сверьте точный SKU и исходники, разместите только на назначенной площадке и верните публичный final URL.',
      'todo',
      3,
      payout_value,
      jsonb_build_object(
        'checklist', jsonb_build_array(
          'Сверить SKU и вариант товара',
          'Проверить права на выбранные исходники',
          'Разместить на назначенной площадке',
          'Вернуть публичный HTTPS final URL'
        ),
        'mode', 'mock',
        'platform', platform_value,
        'destination_ref', destination_value,
        'paid_spend_minor', 0
      ),
      'placement_task:' || content_factory_private.json_hash(jsonb_build_object(
        'idempotency_key', idempotency_key,
        'ordinal', ordinal
      ))
    )
    returning id into task_id_value;

    insert into content_factory.placements (
      organization_id, product_id, generation_job_id, task_id,
      assigned_to, created_by, platform, destination_ref,
      status, request_hash, idempotency_key, metadata
    ) values (
      organization_id,
      product_id,
      job_id,
      task_id_value,
      assignee_id_value,
      user_id,
      platform_value,
      destination_value,
      'ready',
      content_factory_private.json_hash(
        request_payload || jsonb_build_object('placement_ordinal', ordinal)
      ),
      'placement:' || content_factory_private.json_hash(jsonb_build_object(
        'idempotency_key', idempotency_key,
        'ordinal', ordinal
      )),
      jsonb_build_object(
        'mode', 'mock',
        'paid_generation_spend_minor', 0,
        'media_ids', media_ids
      )
    );
  end loop;

  result := jsonb_build_object(
    'ok', true,
    'batch', jsonb_build_object(
      'id', batch_id,
      'public_id', batch_id,
      'sku', sku_value,
      'product_name', product_name,
      'mode', 'mock',
      'allow_real_spend', false,
      'status', 'mock_ready',
      'total_requested', requested_count,
      'total_created', requested_count,
      'placements_created', requested_count,
      'assigned_to', assignee_id_value,
      'platform', platform_value,
      'destination_ref', destination_value,
      'payout_minor_each', payout_value,
      'paid_spend_minor', 0
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'mock_batch_created',
    'generation_batch',
    batch_id::text,
    jsonb_build_object(
      'count', requested_count,
      'format', format_value,
      'platform', platform_value,
      'assigned_to', assignee_id_value,
      'placements_created', requested_count,
      'mode', 'mock',
      'paid_spend_minor', 0
    ),
    'mock_batch:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_create_mock_batch',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_confirm_placement(p_payload jsonb default '{}'::jsonb)
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
  input_id uuid;
  idempotency_key text;
  final_url_value text;
  placement_row content_factory.placements%rowtype;
  task_row content_factory.creator_tasks%rowtype;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
  manager_scope boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(array['owner', 'admin', 'producer', 'reviewer']);
  input_id := content_factory_private.require_uuid(p_payload, 'task_id');
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  final_url_value := content_factory_private.require_text(p_payload, 'final_url', 12, 2000);

  if final_url_value !~ '^https://[^[:space:]]+$'
     or final_url_value ~ '^https://[^/]*@' then
    raise exception using errcode = '22023', message = 'invalid_final_url';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_confirm_placement',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  select placement.* into placement_row
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and (placement.id = input_id or placement.task_id = input_id)
  order by case when placement.id = input_id then 0 else 1 end
  limit 1
  for update;

  if placement_row.id is null then
    raise exception using errcode = 'P0002', message = 'placement_not_found';
  end if;
  if placement_row.task_id is null then
    raise exception using errcode = '55000', message = 'placement_task_required';
  end if;

  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.id = placement_row.task_id
    and task.task_type = 'placement'
  for update;

  if task_row.id is null then
    raise exception using errcode = '55000', message = 'placement_task_required';
  end if;

  -- The assignee may only submit publication evidence. A different certified
  -- manager/reviewer must move the task to review and confirm publication.
  if placement_row.assigned_to = user_id then
    if placement_row.status = 'published' or task_row.status in ('review', 'done') then
      raise exception using errcode = '42501', message = 'placement_self_confirmation_forbidden';
    end if;
    if placement_row.status not in ('scheduled', 'ready')
       or task_row.status not in ('todo', 'in_progress', 'blocked', 'submitted') then
      raise exception using errcode = '55000', message = 'placement_not_submittable';
    end if;
    if task_row.status = 'submitted'
       and placement_row.final_url is distinct from final_url_value then
      raise exception using errcode = '55000', message = 'placement_submission_already_recorded';
    end if;

    update content_factory.placements placement
    set final_url = final_url_value,
        metadata = placement.metadata || jsonb_build_object(
          'submitted_by', user_id,
          'submitted_at', now()
        ),
        updated_at = now()
    where placement.id = placement_row.id
    returning * into placement_row;

    update content_factory.creator_tasks task
    set status = 'submitted',
        submitted_at = coalesce(task.submitted_at, now()),
        completed_at = null,
        result = task.result || jsonb_build_object(
          'placement_id', placement_row.id,
          'final_url', final_url_value
        ),
        updated_at = now()
    where task.organization_id = organization_id
      and task.id = task_row.id
    returning * into task_row;

    result := jsonb_build_object(
      'ok', true,
      'action', 'submitted_for_review',
      'placement', jsonb_build_object(
        'id', placement_row.id,
        'task_id', placement_row.task_id,
        'status', placement_row.status,
        'task_status', task_row.status,
        'final_url', placement_row.final_url,
        'published_at', placement_row.published_at
      )
    );

    perform content_factory_private.emit_event(
      organization_id,
      user_id,
      'placement_submitted',
      'placement',
      placement_row.id::text,
      jsonb_build_object('platform', placement_row.platform),
      'placement-submit:' || idempotency_key
    );

    return content_factory_private.finish_command(
      organization_id,
      user_id,
      'creator_confirm_placement',
      idempotency_key,
      request_payload,
      result
    );
  end if;

  if not manager_scope then
    raise exception using errcode = '42501', message = 'placement_access_denied';
  end if;
  if task_row.status <> 'review' and placement_row.status <> 'published' then
    raise exception using errcode = '55000', message = 'placement_review_required';
  end if;
  if placement_row.final_url is null
     or placement_row.final_url is distinct from final_url_value then
    raise exception using errcode = '55000', message = 'submitted_final_url_required';
  end if;

  if placement_row.status = 'published' then
    if task_row.status <> 'done' then
      raise exception using errcode = '55000', message = 'placement_publication_state_conflict';
    end if;
  elsif placement_row.status not in ('scheduled', 'ready') then
    raise exception using errcode = '55000', message = 'placement_not_publishable';
  else
    update content_factory.placements placement
    set status = 'published',
        published_at = now(),
        metadata = placement.metadata || jsonb_build_object(
          'confirmed_by', user_id,
          'confirmed_at', now()
        ),
        updated_at = now()
    where placement.id = placement_row.id
    returning * into placement_row;

    update content_factory.creator_tasks task
    set status = 'done',
        completed_at = coalesce(task.completed_at, now()),
        result = task.result || jsonb_build_object(
          'placement_id', placement_row.id,
          'final_url', final_url_value,
          'confirmed_by', user_id
        ),
        updated_at = now()
    where task.organization_id = organization_id
      and task.id = task_row.id
    returning * into task_row;

    if task_row.payout_minor > 0 then
      insert into content_factory.creator_payouts (
        organization_id, profile_id, task_id, amount_minor,
        currency, status, reason
      ) values (
        organization_id,
        task_row.assignee_id,
        task_row.id,
        task_row.payout_minor,
        'RUB',
        'pending',
        'Confirmed placement: ' || final_url_value
      )
      on conflict on constraint creator_payouts_org_task_uq do nothing;
    end if;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'placement', jsonb_build_object(
      'id', placement_row.id,
      'task_id', placement_row.task_id,
      'status', placement_row.status,
      'final_url', placement_row.final_url,
      'published_at', placement_row.published_at
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'placement_confirmed',
    'placement',
    placement_row.id::text,
    jsonb_build_object('platform', placement_row.platform),
    'placement:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_confirm_placement',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_transition_task(p_payload jsonb default '{}'::jsonb)
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
  task_id_value uuid;
  target_status text;
  result_patch jsonb;
  idempotency_key text;
  task_row content_factory.creator_tasks%rowtype;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
  manager_scope boolean;
  allowed_transition boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(array['owner', 'admin', 'producer', 'reviewer']);
  task_id_value := content_factory_private.require_uuid(p_payload, 'task_id');
  target_status := content_factory_private.require_text(p_payload, 'status', 3, 30);
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  result_patch := coalesce(p_payload -> 'result', '{}'::jsonb);

  if target_status not in ('todo', 'in_progress', 'submitted', 'review', 'done', 'blocked', 'cancelled')
     or jsonb_typeof(result_patch) <> 'object'
     or length(result_patch::text) > 16000 then
    raise exception using errcode = '22023', message = 'task_transition_invalid';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_transition_task',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  select task.* into task_row
  from content_factory.creator_tasks task
  where task.organization_id = organization_id
    and task.id = task_id_value
  for update;

  if task_row.id is null then
    raise exception using errcode = 'P0002', message = 'task_not_found';
  end if;
  if not manager_scope and task_row.assignee_id <> user_id then
    raise exception using errcode = '42501', message = 'task_access_denied';
  end if;

  if task_row.task_type = 'placement' and target_status = 'submitted' then
    raise exception using
      errcode = '55000',
      message = 'placement_submission_requires_final_url';
  end if;
  if task_row.task_type = 'placement' and target_status = 'done' then
    raise exception using
      errcode = '55000',
      message = 'placement_confirmation_required';
  end if;

  if task_row.status = target_status then
    allowed_transition := true;
  elsif manager_scope then
    allowed_transition :=
      (task_row.status = 'todo' and target_status in ('in_progress', 'blocked', 'cancelled'))
      or (task_row.status = 'in_progress' and target_status in ('submitted', 'blocked', 'cancelled'))
      or (task_row.status = 'submitted' and target_status in ('review', 'done', 'blocked', 'cancelled'))
      or (task_row.status = 'review' and target_status in ('done', 'blocked', 'cancelled'))
      or (task_row.status = 'blocked' and target_status in ('in_progress', 'cancelled'));
  else
    allowed_transition :=
      (task_row.status = 'todo' and target_status in ('in_progress', 'blocked'))
      or (task_row.status = 'in_progress' and target_status in ('submitted', 'blocked'))
      or (task_row.status = 'blocked' and target_status = 'in_progress');
  end if;

  if not allowed_transition then
    raise exception using errcode = '55000', message = 'task_transition_not_allowed';
  end if;

  update content_factory.creator_tasks task
  set status = target_status,
      result = task.result || result_patch,
      submitted_at = case
        when target_status in ('submitted', 'review', 'done')
        then coalesce(task.submitted_at, now())
        else task.submitted_at
      end,
      completed_at = case
        when target_status = 'done' then coalesce(task.completed_at, now())
        when target_status in ('todo', 'in_progress', 'submitted', 'review', 'blocked') then null
        else task.completed_at
      end,
      updated_at = now()
  where task.id = task_row.id
  returning * into task_row;

  if target_status = 'done'
     and task_row.task_type <> 'placement'
     and task_row.payout_minor > 0 then
    insert into content_factory.creator_payouts (
      organization_id, profile_id, task_id, amount_minor,
      currency, status, reason
    ) values (
      organization_id,
      task_row.assignee_id,
      task_row.id,
      task_row.payout_minor,
      'RUB',
      'pending',
      'Completed task: ' || task_row.title
    )
    on conflict on constraint creator_payouts_org_task_uq do nothing;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'task', jsonb_build_object(
      'id', task_row.id,
      'status', task_row.status,
      'submitted_at', task_row.submitted_at,
      'completed_at', task_row.completed_at,
      'result', task_row.result
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'creator_task_transitioned',
    'creator_task',
    task_row.id::text,
    jsonb_build_object('status', task_row.status),
    'task_transition:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_transition_task',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_record_metric(p_payload jsonb default '{}'::jsonb)
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
  placement_id_value uuid;
  idempotency_key text;
  observed_at_value timestamptz;
  views_value bigint;
  clicks_value bigint;
  orders_value bigint;
  revenue_value bigint;
  placement_row content_factory.placements%rowtype;
  previous_row content_factory.metric_snapshots%rowtype;
  snapshot_id uuid;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  placement_id_value := content_factory_private.require_uuid(p_payload, 'placement_id');
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);

  if coalesce(p_payload ->> 'source', '') <> 'manual'
     or coalesce(p_payload ->> 'views', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'clicks', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'orders', '') !~ '^[0-9]+$'
     or coalesce(p_payload ->> 'revenue_minor', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'metric_payload_invalid';
  end if;

  begin
    views_value := (p_payload ->> 'views')::bigint;
    clicks_value := (p_payload ->> 'clicks')::bigint;
    orders_value := (p_payload ->> 'orders')::bigint;
    revenue_value := (p_payload ->> 'revenue_minor')::bigint;
    observed_at_value := (p_payload ->> 'observed_at')::timestamptz;
  exception when invalid_text_representation or datetime_field_overflow or numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'metric_payload_invalid';
  end;

  if observed_at_value > now() + interval '5 minutes' then
    raise exception using errcode = '22023', message = 'observed_at_in_future';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_record_metric',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  select placement.* into placement_row
  from content_factory.placements placement
  where placement.organization_id = organization_id
    and placement.id = placement_id_value
  for update;

  if placement_row.id is null or placement_row.status <> 'published' or placement_row.final_url is null then
    raise exception using errcode = '55000', message = 'published_placement_required';
  end if;
  if placement_row.assigned_to <> user_id
     and actor_role <> all(array['owner', 'admin', 'producer', 'reviewer']) then
    raise exception using errcode = '42501', message = 'placement_access_denied';
  end if;
  if observed_at_value < coalesce(placement_row.published_at, placement_row.created_at) then
    raise exception using errcode = '22023', message = 'observed_at_before_publication';
  end if;

  select metric.* into previous_row
  from content_factory.metric_snapshots metric
  where metric.organization_id = organization_id
    and metric.placement_id = placement_row.id
  order by metric.observed_at desc, metric.created_at desc
  limit 1;

  if previous_row.id is not null and (
    observed_at_value < previous_row.observed_at
    or views_value < previous_row.views
    or clicks_value < previous_row.clicks
    or orders_value < previous_row.orders
    or revenue_value < previous_row.revenue_minor
  ) then
    raise exception using errcode = '22023', message = 'cumulative_metric_regression';
  end if;

  insert into content_factory.metric_snapshots (
    organization_id, placement_id, collected_by, source,
    observed_at, views, clicks, orders, revenue_minor,
    raw, request_hash, idempotency_key
  ) values (
    organization_id,
    placement_row.id,
    user_id,
    'manual',
    observed_at_value,
    views_value,
    clicks_value,
    orders_value,
    revenue_value,
    jsonb_build_object('source', 'manual_creator_cumulative_snapshot'),
    content_factory_private.json_hash(request_payload),
    idempotency_key
  )
  returning id into snapshot_id;

  result := jsonb_build_object(
    'ok', true,
    'metric', jsonb_build_object(
      'id', snapshot_id,
      'placement_id', placement_row.id,
      'source', 'manual',
      'observed_at', observed_at_value,
      'views', views_value,
      'clicks', clicks_value,
      'orders', orders_value,
      'revenue_minor', revenue_value
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'metric_snapshot_recorded',
    'placement',
    placement_row.id::text,
    jsonb_build_object('source', 'manual'),
    'metric:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_record_metric',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_set_wb_alias(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  idempotency_key text;
  sku_value text;
  current_article_value text;
  alias_article_value text;
  reason_value text;
  product_id uuid;
  alias_row content_factory.wb_article_aliases%rowtype;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer']
  );
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  sku_value := content_factory_private.require_text(p_payload, 'sku', 1, 120);
  current_article_value := content_factory_private.require_text(p_payload, 'current_article', 4, 20);
  alias_article_value := content_factory_private.require_text(p_payload, 'alias_article', 4, 20);
  reason_value := content_factory_private.require_text(p_payload, 'reason', 5, 600);

  if current_article_value !~ '^[0-9]{4,20}$'
     or alias_article_value !~ '^[0-9]{4,20}$'
     or current_article_value = alias_article_value then
    raise exception using errcode = '22023', message = 'wb_article_invalid';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_set_wb_alias',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  select product.id into product_id
  from content_factory.products product
  where product.organization_id = organization_id
    and product.sku = sku_value
    and product.status <> 'archived'
  for update;

  if product_id is null then
    raise exception using errcode = 'P0002', message = 'product_not_found';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('wb_alias:' || alias_article_value)
  );

  if exists (
    select 1
    from content_factory.wb_article_aliases alias
    where alias.organization_id = organization_id
      and alias.alias_article = alias_article_value
      and alias.product_id <> product_id
  ) then
    raise exception using errcode = '23505', message = 'wb_alias_product_immutable';
  end if;

  select alias.* into alias_row
  from content_factory.wb_article_aliases alias
  where alias.organization_id = organization_id
    and alias.alias_article = alias_article_value
    and alias.status = 'active'
  order by alias.valid_from desc
  limit 1
  for update;

  if alias_row.id is not null
     and alias_row.current_article <> current_article_value then
    update content_factory.wb_article_aliases alias
    set status = 'replaced',
        valid_to = now(),
        updated_at = now()
    where alias.id = alias_row.id;
    alias_row.id := null;
  end if;

  update content_factory.products product
  set current_wb_article = current_article_value,
      updated_at = now()
  where product.organization_id = organization_id
    and product.id = product_id;

  if alias_row.id is null then
    insert into content_factory.wb_article_aliases (
      organization_id, product_id, alias_article, current_article,
      status, reason, created_by
    ) values (
      organization_id,
      product_id,
      alias_article_value,
      current_article_value,
      'active',
      reason_value,
      user_id
    )
    returning * into alias_row;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'alias', jsonb_build_object(
      'id', alias_row.id,
      'sku', sku_value,
      'current_article', alias_row.current_article,
      'alias_article', alias_row.alias_article,
      'status', alias_row.status,
      'valid_from', alias_row.valid_from
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'wb_alias_recorded',
    'product',
    product_id::text,
    jsonb_build_object(
      'sku', sku_value,
      'current_article', current_article_value,
      'alias_article', alias_article_value
    ),
    'wb_alias:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_set_wb_alias',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_decide_payout(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  payout_id_value uuid;
  idempotency_key text;
  decision_value text;
  notes_value text;
  payment_reference text;
  payout_row content_factory.creator_payouts%rowtype;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin']
  );
  payout_id_value := content_factory_private.require_uuid(p_payload, 'payout_id');
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  decision_value := content_factory_private.require_text(p_payload, 'decision', 3, 20);
  notes_value := btrim(coalesce(p_payload ->> 'notes', ''));
  payment_reference := btrim(coalesce(p_payload ->> 'external_payment_reference', ''));

  if decision_value not in ('approve', 'reject', 'paid')
     or length(notes_value) > 1000
     or length(payment_reference) > 180 then
    raise exception using errcode = '22023', message = 'payout_decision_invalid';
  end if;
  if decision_value = 'reject' and length(notes_value) < 10 then
    raise exception using errcode = '22023', message = 'payout_rejection_reason_required';
  end if;
  if decision_value = 'paid' and length(payment_reference) < 3 then
    raise exception using errcode = '22023', message = 'external_payment_reference_required';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_decide_payout',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  select payout.* into payout_row
  from content_factory.creator_payouts payout
  where payout.organization_id = organization_id
    and payout.id = payout_id_value
  for update;

  if payout_row.id is null then
    raise exception using errcode = 'P0002', message = 'payout_not_found';
  end if;
  if payout_row.profile_id = user_id then
    raise exception using errcode = '42501', message = 'self_payout_decision_forbidden';
  end if;

  if decision_value = 'approve' then
    if payout_row.status not in ('pending', 'approved') then
      raise exception using errcode = '55000', message = 'payout_not_pending';
    end if;
    update content_factory.creator_payouts payout
    set status = 'approved',
        reason = nullif(notes_value, ''),
        approved_by = user_id,
        approved_at = coalesce(payout.approved_at, now()),
        updated_at = now()
    where payout.id = payout_row.id
    returning * into payout_row;
  elsif decision_value = 'reject' then
    if payout_row.status not in ('pending', 'rejected') then
      raise exception using errcode = '55000', message = 'payout_not_pending';
    end if;
    if payout_row.status = 'rejected' and payout_row.reason is distinct from notes_value then
      raise exception using errcode = '55000', message = 'payout_already_rejected';
    end if;
    update content_factory.creator_payouts payout
    set status = 'rejected',
        reason = notes_value,
        approved_by = user_id,
        approved_at = coalesce(payout.approved_at, now()),
        updated_at = now()
    where payout.id = payout_row.id
    returning * into payout_row;
  else
    if payout_row.status not in ('approved', 'paid') then
      raise exception using errcode = '55000', message = 'payout_must_be_approved_first';
    end if;
    if payout_row.status = 'paid'
       and payout_row.external_payment_reference is distinct from payment_reference then
      raise exception using errcode = '55000', message = 'payout_already_paid';
    end if;
    update content_factory.creator_payouts payout
    set status = 'paid',
        external_payment_reference = payment_reference,
        paid_at = coalesce(payout.paid_at, now()),
        updated_at = now()
    where payout.id = payout_row.id
    returning * into payout_row;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'payout', jsonb_build_object(
      'id', payout_row.id,
      'status', payout_row.status,
      'amount_minor', payout_row.amount_minor,
      'currency', payout_row.currency,
      'reason', payout_row.reason,
      'external_payment_reference', payout_row.external_payment_reference,
      'approved_at', payout_row.approved_at,
      'paid_at', payout_row.paid_at
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'payout_decided',
    'creator_payout',
    payout_row.id::text,
    jsonb_build_object('decision', decision_value, 'status', payout_row.status),
    'payout:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_payout',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_create_feedback(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  idempotency_key text;
  category_value text;
  section_value text;
  title_value text;
  description_value text;
  feedback_id uuid;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(organization_id, true, null);
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  category_value := content_factory_private.require_text(p_payload, 'category', 3, 40);
  section_value := content_factory_private.require_text(p_payload, 'section', 3, 40);
  title_value := content_factory_private.require_text(p_payload, 'title', 3, 180);
  description_value := content_factory_private.require_text(p_payload, 'description', 5, 2000);

  if category_value not in (
    'blocker', 'idea', 'data', 'interface', 'generation', 'quality',
    'funnel', 'social_data', 'payouts', 'wb_aliases', 'analytics',
    'training', 'other'
  ) or section_value not in (
    'generation', 'placement', 'stats', 'payouts',
    'tasks', 'media', 'feedback'
  ) then
    raise exception using errcode = '22023', message = 'feedback_category_invalid';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_create_feedback',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  insert into content_factory.feedback_requests (
    organization_id, profile_id, category, title,
    details, status, idempotency_key
  ) values (
    organization_id,
    user_id,
    category_value,
    title_value,
    description_value,
    'new',
    idempotency_key
  )
  returning id into feedback_id;

  result := jsonb_build_object(
    'ok', true,
    'feedback', jsonb_build_object(
      'id', feedback_id,
      'category', category_value,
      'section', section_value,
      'title', title_value,
      'description', description_value,
      'status', 'new'
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'feedback_created',
    'feedback_request',
    feedback_id::text,
    jsonb_build_object('category', category_value, 'section', section_value),
    'feedback:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_create_feedback',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_register_media(p_payload jsonb default '{}'::jsonb)
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
  bucket_value text;
  object_key text;
  original_filename text;
  mime_value text;
  sha_value text;
  kind_value text;
  size_value bigint;
  storage_metadata jsonb;
  storage_size bigint;
  storage_mime text;
  task_id_value uuid;
  product_id_value uuid;
  sku_value text;
  product_name_value text;
  user_media_objects_24h bigint;
  user_media_bytes_24h numeric;
  user_media_objects_total bigint;
  user_media_bytes_total numeric;
  organization_media_objects bigint;
  organization_media_bytes numeric;
  media_row content_factory.media_objects%rowtype;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
  manager_scope boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role = any(array['owner', 'admin', 'producer', 'reviewer']);
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  bucket_value := content_factory_private.require_text(p_payload, 'bucket', 3, 80);
  object_key := content_factory_private.require_text(p_payload, 'object_key', 10, 1000);
  original_filename := content_factory_private.require_text(p_payload, 'original_filename', 1, 255);
  mime_value := content_factory_private.require_text(p_payload, 'mime_type', 3, 160);
  mime_value := lower(mime_value);
  sha_value := lower(content_factory_private.require_text(p_payload, 'sha256', 64, 64));
  kind_value := content_factory_private.require_text(p_payload, 'kind', 3, 80);

  if coalesce(p_payload ->> 'size_bytes', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'media_size_invalid';
  end if;
  begin
    size_value := (p_payload ->> 'size_bytes')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'media_size_invalid';
  end;

  if bucket_value <> 'contentengine-private'
     or split_part(object_key, '/', 1) <> organization_id::text
     or split_part(object_key, '/', 2) <> user_id::text
     or object_key ~ '(^|/)\.\.(/|$)'
     or p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb then
    raise exception using errcode = '42501', message = 'storage_access_denied';
  end if;
  if size_value < 1 or size_value > 52428800
     or sha_value !~ '^[0-9a-f]{64}$'
     or mime_value not in ('image/jpeg', 'image/png', 'image/webp', 'video/mp4')
     or kind_value not in ('product_photo', 'packshot', 'creator_reference', 'source_video') then
    raise exception using errcode = '22023', message = 'media_metadata_invalid';
  end if;
  -- This is the same lock used by the unregistered-upload DELETE policy.
  -- It closes the delete/register race that could otherwise leave a ready
  -- media row pointing at an object removed by a concurrent rollback.
  perform pg_advisory_xact_lock(
    hashtext(bucket_value),
    hashtext(object_key)
  );

  select storage_object.metadata
    into storage_metadata
  from storage.objects storage_object
  where storage_object.bucket_id = bucket_value
    and storage_object.name = object_key
  for update;

  if storage_metadata is null then
    raise exception using errcode = 'P0002', message = 'storage_object_not_found';
  end if;

  if jsonb_typeof(storage_metadata) <> 'object'
     or coalesce(storage_metadata ->> 'size', '') !~ '^[0-9]+$'
     or nullif(btrim(coalesce(storage_metadata ->> 'mimetype', '')), '') is null then
    raise exception using errcode = '22023', message = 'storage_metadata_invalid';
  end if;

  begin
    storage_size := (storage_metadata ->> 'size')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'storage_metadata_invalid';
  end;
  storage_mime := lower(btrim(storage_metadata ->> 'mimetype'));

  if storage_size <> size_value or storage_mime <> mime_value then
    raise exception using errcode = '22023', message = 'storage_metadata_mismatch';
  end if;

  if nullif(btrim(coalesce(p_payload ->> 'task_id', '')), '') is not null then
    task_id_value := content_factory_private.require_uuid(p_payload, 'task_id');
    if not exists (
      select 1
      from content_factory.creator_tasks task
      where task.organization_id = organization_id
        and task.id = task_id_value
        and (manager_scope or task.assignee_id = user_id)
    ) then
      raise exception using errcode = '42501', message = 'task_access_denied';
    end if;
  end if;

  if nullif(btrim(coalesce(p_payload ->> 'product_id', '')), '') is not null then
    product_id_value := content_factory_private.require_uuid(p_payload, 'product_id');
    if not exists (
      select 1
      from content_factory.products product
      where product.organization_id = organization_id
        and product.id = product_id_value
        and product.status <> 'archived'
    ) then
      raise exception using errcode = 'P0002', message = 'product_not_found';
    end if;
  end if;

  if kind_value in ('product_photo', 'packshot') and product_id_value is null then
    sku_value := content_factory_private.require_text(p_payload, 'sku', 1, 120);
    product_name_value := content_factory_private.require_text(
      p_payload,
      'product_name',
      2,
      180
    );
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_register_media',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  if kind_value in ('product_photo', 'packshot') and product_id_value is null then
    insert into content_factory.products (
      organization_id, sku, title, status, created_by
    ) values (
      organization_id, sku_value, product_name_value, 'active', user_id
    )
    on conflict on constraint products_org_sku_uq do update set
      title = excluded.title,
      status = 'active',
      updated_at = now()
    returning id into product_id_value;
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.bucket_id = bucket_value
    and media.object_name = object_key
  for update;

  if media_row.id is not null and (
    media_row.organization_id <> organization_id
    or media_row.owner_id <> user_id
    or media_row.task_id is distinct from task_id_value
    or media_row.sha256 <> sha_value
    or media_row.product_id is distinct from product_id_value
    or media_row.mime_type <> mime_value
    or media_row.size_bytes <> size_value
    or media_row.status <> 'ready'
    or media_row.metadata ->> 'original_filename' is distinct from original_filename
    or media_row.metadata ->> 'kind' is distinct from kind_value
    or media_row.metadata -> 'rights_confirmed' is distinct from 'true'::jsonb
  ) then
    raise exception using errcode = '23505', message = 'media_object_conflict';
  end if;

  if media_row.id is null then
    perform pg_advisory_xact_lock(
      hashtext(organization_id::text),
      hashtext('media_quota:organization')
    );
    perform pg_advisory_xact_lock(
      hashtext(organization_id::text || ':' || user_id::text),
      hashtext('media_quota:user')
    );

    select
      count(*) filter (
        where media.owner_id = user_id
          and media.created_at >= now() - interval '24 hours'
      ),
      coalesce(sum(media.size_bytes) filter (
        where media.owner_id = user_id
          and media.created_at >= now() - interval '24 hours'
      ), 0),
      count(*) filter (where media.owner_id = user_id),
      coalesce(sum(media.size_bytes) filter (
        where media.owner_id = user_id
      ), 0),
      count(*),
      coalesce(sum(media.size_bytes), 0)
    into
      user_media_objects_24h,
      user_media_bytes_24h,
      user_media_objects_total,
      user_media_bytes_total,
      organization_media_objects,
      organization_media_bytes
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.status in ('uploading', 'ready', 'archived');

    if user_media_objects_24h >= 200 then
      raise exception using errcode = '54000', message = 'media_user_daily_object_quota_exceeded';
    end if;
    if user_media_bytes_24h + size_value > 2147483648 then
      raise exception using errcode = '54000', message = 'media_user_daily_bytes_quota_exceeded';
    end if;
    if user_media_objects_total + 1 > 2000 then
      raise exception using errcode = '54000', message = 'media_user_total_object_quota_exceeded';
    end if;
    if user_media_bytes_total + size_value > 10737418240 then
      raise exception using errcode = '54000', message = 'media_user_total_storage_quota_exceeded';
    end if;
    if organization_media_objects + 1 > 20000 then
      raise exception using errcode = '54000', message = 'media_organization_object_quota_exceeded';
    end if;
    if organization_media_bytes + size_value > 107374182400 then
      raise exception using errcode = '54000', message = 'media_organization_storage_quota_exceeded';
    end if;

    insert into content_factory.media_objects (
      organization_id, owner_id, task_id, product_id,
      bucket_id, object_name, mime_type, size_bytes, sha256,
      status, metadata, idempotency_key
    ) values (
      organization_id,
      user_id,
      task_id_value,
      product_id_value,
      bucket_value,
      object_key,
      mime_value,
      size_value,
      sha_value,
      'ready',
      jsonb_build_object(
        'original_filename', original_filename,
        'kind', kind_value,
        'rights_confirmed', true
      ),
      idempotency_key
    )
    returning * into media_row;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'media', jsonb_build_object(
      'id', media_row.id,
      'public_id', media_row.id,
      'object_key', media_row.object_name,
      'original_filename', media_row.metadata ->> 'original_filename',
      'kind', media_row.metadata ->> 'kind',
      'mime_type', media_row.mime_type,
      'size_bytes', media_row.size_bytes,
      'product_id', media_row.product_id,
      'status', media_row.status
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'media_registered',
    'media_object',
    media_row.id::text,
    jsonb_build_object(
      'kind', media_row.metadata ->> 'kind',
      'mime_type', media_row.mime_type
    ),
    'media:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_register_media',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_capture_event(p_payload jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  idempotency_key text;
  event_name_value text;
  session_value text;
  route_value text;
  properties_value jsonb;
  occurred_at_value timestamptz;
  event_id uuid;
  replay jsonb;
  request_payload jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(organization_id, false, null);
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  event_name_value := content_factory_private.require_text(p_payload, 'event_name', 3, 100);
  session_value := btrim(coalesce(p_payload ->> 'session_id', ''));
  route_value := btrim(coalesce(p_payload ->> 'route', ''));
  properties_value := coalesce(p_payload -> 'properties', '{}'::jsonb);

  if event_name_value !~ '^[a-z0-9_]{3,100}$'
     or length(session_value) > 180
     or length(route_value) > 300
     or jsonb_typeof(properties_value) <> 'object'
     or length(properties_value::text) > 16000
     or properties_value::text ~* '"(password|token|api[_-]?key|secret)"[[:space:]]*:' then
    raise exception using errcode = '22023', message = 'event_payload_invalid';
  end if;

  begin
    occurred_at_value := coalesce(
      nullif(btrim(p_payload ->> 'occurred_at'), '')::timestamptz,
      now()
    );
  exception when invalid_text_representation or datetime_field_overflow then
    raise exception using errcode = '22023', message = 'occurred_at_invalid';
  end;
  if occurred_at_value < now() - interval '7 days'
     or occurred_at_value > now() + interval '5 minutes' then
    raise exception using errcode = '22023', message = 'occurred_at_invalid';
  end if;

  request_payload := p_payload - 'idempotency_key' - 'organization_id';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_capture_event',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  insert into content_factory.factory_events (
    organization_id, profile_id, event_name, source,
    entity_type, entity_id, properties, idempotency_key, occurred_at
  ) values (
    organization_id,
    user_id,
    event_name_value,
    'client_rpc',
    'browser_session',
    nullif(session_value, ''),
    properties_value || jsonb_build_object('route', route_value),
    left('client:' || idempotency_key, 180),
    occurred_at_value
  )
  returning id into event_id;

  result := jsonb_build_object('ok', true, 'event_id', event_id);
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_capture_event',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

-- SECURITY DEFINER helpers are deliberately unreachable from browser roles.
revoke all on all functions in schema content_factory_private
  from public, anon, authenticated;
grant execute on all functions in schema content_factory_private to service_role;

revoke all on function public.creator_bootstrap(jsonb) from public, anon;
revoke all on function public.creator_complete_module(jsonb) from public, anon;
revoke all on function public.creator_submit_exam(jsonb) from public, anon;
revoke all on function public.creator_workspace_section(jsonb) from public, anon;
revoke all on function public.creator_create_mock_batch(jsonb) from public, anon;
revoke all on function public.creator_confirm_placement(jsonb) from public, anon;
revoke all on function public.creator_record_metric(jsonb) from public, anon;
revoke all on function public.creator_set_wb_alias(jsonb) from public, anon;
revoke all on function public.creator_decide_payout(jsonb) from public, anon;
revoke all on function public.creator_transition_task(jsonb) from public, anon;
revoke all on function public.creator_create_feedback(jsonb) from public, anon;
revoke all on function public.creator_register_media(jsonb) from public, anon;
revoke all on function public.creator_capture_event(jsonb) from public, anon;

revoke all on function public.system_initialize_owner(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_provision_invited_member(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_reconcile_invited_member(jsonb)
  from public, anon, authenticated;

grant execute on function public.creator_bootstrap(jsonb) to authenticated;
grant execute on function public.creator_complete_module(jsonb) to authenticated;
grant execute on function public.creator_submit_exam(jsonb) to authenticated;
grant execute on function public.creator_workspace_section(jsonb) to authenticated;
grant execute on function public.creator_create_mock_batch(jsonb) to authenticated;
grant execute on function public.creator_confirm_placement(jsonb) to authenticated;
grant execute on function public.creator_record_metric(jsonb) to authenticated;
grant execute on function public.creator_set_wb_alias(jsonb) to authenticated;
grant execute on function public.creator_decide_payout(jsonb) to authenticated;
grant execute on function public.creator_transition_task(jsonb) to authenticated;
grant execute on function public.creator_create_feedback(jsonb) to authenticated;
grant execute on function public.creator_register_media(jsonb) to authenticated;
grant execute on function public.creator_capture_event(jsonb) to authenticated;

grant execute on function public.system_initialize_owner(jsonb) to service_role;
grant execute on function public.system_provision_invited_member(jsonb) to service_role;
grant execute on function public.system_reconcile_invited_member(jsonb) to service_role;

commit;

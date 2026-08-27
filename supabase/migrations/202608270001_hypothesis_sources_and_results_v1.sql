begin;
-- 202608270001_hypothesis_sources_and_results_v1
--
-- Контур №3, продолжение: (1) источники-доказательства гипотезы — типизированные
-- append-only привязки к зарегистрированным YouTube-источникам проекта, с
-- снапшотом canonical URL и хешей (raw-тексты не копируются — ТЗ 5.11);
-- (2) срез гипотезы отдаёт варианты с результатами: к каждому запуску —
-- готовый ролик и последний снимок метрик его размещений (числители и
-- знаменатели; формулы считает экран; победителя объявляет только человек).

create table if not exists content_factory.content_hypothesis_source_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  hypothesis_id uuid not null,
  source_id uuid not null,
  canonical_url_snapshot text not null,
  source_hash_snapshot text not null,
  note text check (note is null or length(btrim(note)) between 1 and 500),
  added_by uuid not null,
  added_at timestamptz not null default now(),
  binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
  constraint content_hypothesis_source_bindings_hash_self check (
    binding_hash = content_factory_private.json_hash(jsonb_build_object(
      'version', 'content-hypothesis-source-binding-v1',
      'hypothesis_id', hypothesis_id,
      'source_id', source_id,
      'source_hash', source_hash_snapshot
    ))
  ),
  constraint content_hypothesis_source_bindings_uq
    unique (organization_id, hypothesis_id, source_id),
  constraint content_hypothesis_source_bindings_hypothesis_fk
    foreign key (organization_id, hypothesis_id)
    references content_factory.content_hypotheses (organization_id, id)
);

alter table content_factory.content_hypothesis_source_bindings
  enable row level security;
revoke all on content_factory.content_hypothesis_source_bindings
  from public, anon, authenticated;
grant all on content_factory.content_hypothesis_source_bindings
  to service_role;

create or replace function content_factory_private
  .reject_content_hypothesis_source_binding_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception using errcode = '55000',
    message = 'content_hypothesis_source_binding_append_only';
end;
$$;

drop trigger if exists content_hypothesis_source_bindings_append_only
  on content_factory.content_hypothesis_source_bindings;
create trigger content_hypothesis_source_bindings_append_only
  before update or delete
  on content_factory.content_hypothesis_source_bindings
  for each row execute function
    content_factory_private.reject_content_hypothesis_source_binding_mutation();

-- Привязка зарегистрированного YouTube-источника проекта к гипотезе.
-- Источник обязан существовать (регистрирует существующий контур «Забрать
-- видео»); привязка идемпотентна: повтор того же источника — no-op.
create or replace function public.creator_bind_content_hypothesis_source(
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
  source_row content_factory.research_exact_youtube_sources%rowtype;
  binding_row content_factory.content_hypothesis_source_bindings%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );

  select h.* into hypothesis_row
  from content_factory.content_hypotheses h
  where h.organization_id = organization_id
    and h.id = content_factory_private.require_uuid(p_payload, 'hypothesis_id');
  if hypothesis_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_not_found';
  end if;
  perform content_factory_private.require_workspace_project_access(
    organization_id, hypothesis_row.project_id, user_id
  );

  select s.* into source_row
  from content_factory.research_exact_youtube_sources s
  where s.organization_id = organization_id
    and s.project_id = hypothesis_row.project_id
    and s.id = content_factory_private.require_uuid(p_payload, 'source_id');
  if source_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'content_hypothesis_source_not_found';
  end if;

  insert into content_factory.content_hypothesis_source_bindings (
    organization_id, hypothesis_id, source_id,
    canonical_url_snapshot, source_hash_snapshot, note, added_by,
    binding_hash
  ) values (
    organization_id, hypothesis_row.id, source_row.id,
    source_row.canonical_url, source_row.source_hash,
    nullif(btrim(coalesce(p_payload ->> 'note', '')), ''), user_id,
    content_factory_private.json_hash(jsonb_build_object(
      'version', 'content-hypothesis-source-binding-v1',
      'hypothesis_id', hypothesis_row.id,
      'source_id', source_row.id,
      'source_hash', source_row.source_hash
    ))
  )
  on conflict on constraint content_hypothesis_source_bindings_uq do nothing;

  select b.* into binding_row
  from content_factory.content_hypothesis_source_bindings b
  where b.organization_id = organization_id
    and b.hypothesis_id = hypothesis_row.id
    and b.source_id = source_row.id;

  return jsonb_build_object(
    'ok', true,
    'version', 'content-hypothesis-source-bind-v1',
    'binding_id', binding_row.id,
    'canonical_url', binding_row.canonical_url_snapshot,
    'already_bound', binding_row.added_at < now() - interval '1 second'
  );
end;
$$;

revoke all on function public.creator_bind_content_hypothesis_source(jsonb)
  from public, anon, service_role;
grant execute on function
  public.creator_bind_content_hypothesis_source(jsonb) to authenticated;

-- Срез гипотезы: привязанные источники и варианты с результатами.
do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_hypothesis(jsonb)'::regprocedure
  );
  if strpos(src, 'evidence_sources') > 0 then
    raise exception 'hypothesis_detail_sources_patch_already_applied';
  end if;
  if strpos(src, '''members'', (') = 0
     or strpos(src, '''generation_job_id'', m.generation_job_id,') = 0 then
    raise exception 'hypothesis_detail_sources_patch_anchor_missing';
  end if;

  src := replace(src,
    '''members'', (',
    '''evidence_sources'', (
      select coalesce(jsonb_agg(jsonb_build_object(
        ''binding_id'', b.id,
        ''source_id'', b.source_id,
        ''canonical_url'', b.canonical_url_snapshot,
        ''note'', b.note,
        ''added_by'', b.added_by,
        ''added_at'', b.added_at
      ) order by b.added_at desc), ''[]''::jsonb)
      from content_factory.content_hypothesis_source_bindings b
      where b.organization_id = organization_id
        and b.hypothesis_id = hypothesis_row.id
    ),
    ''members'', (');

  src := replace(src,
    '''generation_job_id'', m.generation_job_id,',
    '''generation_job_id'', m.generation_job_id,
      ''result_media_id'', (
        select media.id from content_factory.media_objects media
        where media.organization_id = m.organization_id
          and media.artifact_class = ''generated_output''
          and (media.metadata ->> ''generation_job_id'')::uuid
            = m.generation_job_id
        limit 1
      ),
      ''model'', (
        select job.input ->> ''model''
        from content_factory.generation_jobs job
        where job.organization_id = m.organization_id
          and job.id = m.generation_job_id
      ),
      ''job_status'', (
        select job.status
        from content_factory.generation_jobs job
        where job.organization_id = m.organization_id
          and job.id = m.generation_job_id
      ),
      ''metrics'', (
        select jsonb_build_object(
          ''views'', latest.views,
          ''clicks'', latest.clicks,
          ''orders'', latest.orders,
          ''revenue_minor'', latest.revenue_minor,
          ''observed_at'', latest.observed_at,
          ''mature'', placement.published_at is not null
            and latest.observed_at >= placement.published_at
              + interval ''72 hours''
        )
        from content_factory.placements placement
        join lateral (
          select s2.views, s2.clicks, s2.orders, s2.revenue_minor,
            s2.observed_at
          from content_factory.metric_snapshots s2
          where s2.organization_id = placement.organization_id
            and s2.placement_id = placement.id
          order by s2.observed_at desc
          limit 1
        ) latest on true
        where placement.organization_id = m.organization_id
          and placement.generation_job_id = m.generation_job_id
        order by latest.observed_at desc
        limit 1
      ),');

  execute src;
end
$mig$;

notify pgrst, 'reload schema';

commit;

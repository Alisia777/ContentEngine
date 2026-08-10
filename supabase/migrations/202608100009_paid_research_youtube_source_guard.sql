begin;

-- A page URL identifies a YouTube video but does not provide frames or audio.
-- Fail before the durable paid-start boundary if a browser (or a stale client)
-- tries to fold that URL into ordinary product/market research.  The exact
-- source intake remains the only URL-only entrypoint; audiovisual analysis
-- resumes after a lawful MP4 is attached to that source.
create or replace function content_factory_private
  .paid_research_has_unattached_youtube_url(p_payload jsonb)
returns boolean
language sql
immutable
security definer
set search_path = ''
as $$
  select
    coalesce(p_payload ->> 'objective', '') ~*
      'https?://([a-z0-9-]+[.])*(youtube(-nocookie)?[.]com|youtu[.]be)([/?:#]|$)'
    or coalesce(p_payload ->> 'marketplace_url', '') ~*
      'https?://([a-z0-9-]+[.])*(youtube(-nocookie)?[.]com|youtu[.]be)([/?:#]|$)'
$$;

revoke all on function
  content_factory_private.paid_research_has_unattached_youtube_url(jsonb)
  from public, anon, authenticated, service_role;

do $preserve_project_research_start_before_youtube_guard$
begin
  if to_regprocedure(
    'content_factory_private.creator_start_project_research_pre_youtube_guard_v1(jsonb)'
  ) is null then
    if to_regprocedure('public.creator_start_project_research(jsonb)') is null then
      raise exception using
        errcode = '42883', message = 'creator_start_project_research_missing';
    end if;
    execute 'alter function public.creator_start_project_research(jsonb) '
      || 'set schema content_factory_private';
    execute 'alter function '
      || 'content_factory_private.creator_start_project_research(jsonb) '
      || 'rename to creator_start_project_research_pre_youtube_guard_v1';
  end if;
end;
$preserve_project_research_start_before_youtube_guard$;

revoke all on function content_factory_private
  .creator_start_project_research_pre_youtube_guard_v1(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_start_project_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if content_factory_private
    .paid_research_has_unattached_youtube_url(p_payload) then
    raise exception using
      errcode = '22023',
      message = 'research_youtube_source_requires_media';
  end if;
  return content_factory_private
    .creator_start_project_research_pre_youtube_guard_v1(p_payload);
end;
$$;

revoke all on function public.creator_start_project_research(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_start_project_research(jsonb)
  to authenticated;

comment on function public.creator_start_project_research(jsonb) is
  'Project research paid-start gateway; rejects unattached YouTube page URLs before any paid provider boundary.';

notify pgrst, 'reload schema';

commit;

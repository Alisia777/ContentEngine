begin;

grant usage on schema content_factory to authenticated, service_role;
grant usage on schema content_factory_private to service_role;

revoke all on all tables in schema content_factory from public, anon, authenticated;
revoke all on all sequences in schema content_factory from public, anon, authenticated;
revoke all on all functions in schema content_factory from public, anon, authenticated;
revoke all on all tables in schema content_factory_private from public, anon, authenticated;
revoke all on all functions in schema content_factory_private from public, anon, authenticated;

grant all privileges on all tables in schema content_factory to service_role;
grant all privileges on all sequences in schema content_factory to service_role;
grant all privileges on all functions in schema content_factory to service_role;
grant all privileges on all tables in schema content_factory_private to service_role;
grant all privileges on all functions in schema content_factory_private to service_role;

alter default privileges in schema content_factory
  revoke all on tables from public, anon, authenticated;
alter default privileges in schema content_factory
  revoke all on sequences from public, anon, authenticated;
alter default privileges in schema content_factory
  revoke all on functions from public, anon, authenticated;
alter default privileges in schema content_factory
  grant all on tables to service_role;
alter default privileges in schema content_factory
  grant all on sequences to service_role;
alter default privileges in schema content_factory
  grant all on functions to service_role;

alter default privileges in schema content_factory_private
  revoke all on tables from public, anon, authenticated;
alter default privileges in schema content_factory_private
  revoke all on functions from public, anon, authenticated;
alter default privileges in schema content_factory_private
  grant all on tables to service_role;
alter default privileges in schema content_factory_private
  grant all on functions to service_role;

do $enable_rls$
declare
  target_table text;
begin
  foreach target_table in array array[
    'profiles', 'organizations', 'memberships', 'membership_invites',
    'training_modules', 'training_questions', 'training_attempts',
    'training_certifications', 'products', 'generation_batches',
    'generation_jobs', 'creator_tasks', 'creator_payouts', 'placements',
    'metric_snapshots', 'factory_events', 'wb_article_aliases',
    'media_objects', 'feedback_requests', 'command_receipts'
  ]
  loop
    execute format(
      'alter table content_factory.%I enable row level security',
      target_table
    );
  end loop;
end;
$enable_rls$;

-- These two narrow grants are required by Storage policies. The schema is not
-- exposed by PostgREST, and the policies reveal only the caller's own rows.
grant select on content_factory.memberships to authenticated;
grant select on content_factory.training_certifications to authenticated;

drop policy if exists memberships_select_self on content_factory.memberships;
create policy memberships_select_self
on content_factory.memberships
for select
to authenticated
using (profile_id = (select auth.uid()));

drop policy if exists certifications_select_self on content_factory.training_certifications;
create policy certifications_select_self
on content_factory.training_certifications
for select
to authenticated
using (profile_id = (select auth.uid()));

-- Storage policies call these two narrow SECURITY DEFINER predicates instead
-- of granting browser roles access to organization/profile tables.
create or replace function content_factory.storage_access_allowed(
  p_organization_id text,
  p_owner_id text,
  p_allow_team_read boolean default false
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select auth.uid() is not null and exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.training_certifications certification
      on certification.organization_id = membership.organization_id
     and certification.profile_id = membership.profile_id
     and certification.module_code = 'operator_final_exam'
     and certification.status = 'passed'
     and (certification.expires_at is null or certification.expires_at > now())
    where membership.profile_id = auth.uid()
      and membership.status = 'active'
      and membership.organization_id::text = p_organization_id
      and (
        p_owner_id = auth.uid()::text
        or (
          p_allow_team_read
          and membership.role in ('owner', 'admin', 'producer', 'reviewer')
        )
      )
  )
$$;

create or replace function content_factory.storage_object_is_unregistered(
  p_bucket_id text,
  p_object_name text
)
returns boolean
language plpgsql
security definer
volatile
set search_path = ''
as $$
begin
  if auth.uid() is null
     or p_bucket_id <> 'contentengine-private'
     or split_part(p_object_name, '/', 2) <> auth.uid()::text then
    return false;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(p_bucket_id),
    hashtext(p_object_name)
  );

  return not exists (
    select 1
    from content_factory.media_objects media
    where media.bucket_id = p_bucket_id
      and media.object_name = p_object_name
  );
end;
$$;

revoke all on function content_factory.storage_access_allowed(text, text, boolean)
  from public, anon;
revoke all on function content_factory.storage_object_is_unregistered(text, text)
  from public, anon;
grant execute on function content_factory.storage_access_allowed(text, text, boolean)
  to authenticated;
grant execute on function content_factory.storage_object_is_unregistered(text, text)
  to authenticated;

insert into storage.buckets (
  id, name, public, file_size_limit, allowed_mime_types
)
values (
  'contentengine-private',
  'contentengine-private',
  false,
  52428800,
  array['image/jpeg', 'image/png', 'image/webp', 'video/mp4']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists contentengine_private_select on storage.objects;
create policy contentengine_private_select
on storage.objects
for select
to authenticated
using (
  bucket_id = 'contentengine-private'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    true
  )
);

drop policy if exists contentengine_private_insert on storage.objects;
create policy contentengine_private_insert
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'contentengine-private'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
);

drop policy if exists contentengine_private_update on storage.objects;
-- No authenticated UPDATE policy: upsert=false uploads are immutable. A file
-- replacement must use a new object key and a new media registration.

drop policy if exists contentengine_private_delete on storage.objects;
create policy contentengine_private_delete
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'contentengine-private'
  and content_factory.storage_access_allowed(
    split_part(storage.objects.name, '/', 1),
    split_part(storage.objects.name, '/', 2),
    false
  )
  and content_factory.storage_object_is_unregistered(
    storage.objects.bucket_id,
    storage.objects.name
  )
);

commit;

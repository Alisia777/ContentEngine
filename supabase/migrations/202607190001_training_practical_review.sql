begin;

-- A course check proves recall.  This receipt proves that the learner has
-- produced one reviewable piece of work and that an accountable manager has
-- accepted it.  Only references and bounded metadata are stored here; video
-- bytes, signed download tokens and provider payloads never enter this table.
create table content_factory.training_practical_projects (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  profile_id uuid not null,
  status text not null default 'draft'
    check (status in (
      'draft', 'submitted', 'changes_requested', 'approved'
    )),
  evidence_kind text not null
    check (evidence_kind in (
      'public_url', 'uploaded_file', 'grandfathered'
    )),
  platform text
    check (platform is null or platform in ('instagram', 'youtube', 'vk')),
  evidence_url text,
  storage_object_id uuid,
  storage_object_name text,
  file_metadata jsonb not null default '{}'::jsonb
    check (jsonb_typeof(file_metadata) = 'object'),
  learner_note text not null default ''
    check (length(learner_note) <= 2000),
  rights_confirmed boolean not null default false,
  self_check_codes jsonb not null default '[]'::jsonb
    check (
      jsonb_typeof(self_check_codes) = 'array'
      and jsonb_array_length(self_check_codes) <= 12
    ),
  review_note text,
  reviewed_by uuid references content_factory.profiles(id),
  submission_revision integer not null default 0
    check (submission_revision between 0 and 1000),
  version integer not null default 1 check (version between 1 and 1000000),
  submitted_at timestamptz,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, profile_id)
    references content_factory.memberships(organization_id, profile_id)
    on delete cascade,
  unique (organization_id, profile_id),
  unique (organization_id, id),
  check (
    review_note is null
    or length(btrim(review_note)) between 1 and 4000
  ),
  check (
    (
      evidence_kind = 'public_url'
      and
      evidence_url is not null
      and length(evidence_url) between 12 and 2000
      and evidence_url ~ '^https://[^[:space:]]+$'
      and evidence_url !~ '^https://[^/]*@'
      and evidence_url !~* '[?#&](token|signature|password|secret|api[_-]?key)='
    )
    or (
      evidence_kind in ('uploaded_file', 'grandfathered')
      and evidence_url is null
    )
  ),
  check (
    (
      evidence_kind = 'public_url'
      and platform is not null
      and storage_object_id is null
      and storage_object_name is null
      and file_metadata = '{}'::jsonb
    )
    or (
      evidence_kind = 'uploaded_file'
      and platform is not null
      and storage_object_id is not null
      and storage_object_name is not null
      and length(storage_object_name) between 80 and 1000
      and split_part(storage_object_name, '/', 1) = organization_id::text
      and split_part(storage_object_name, '/', 2) = profile_id::text
      and split_part(storage_object_name, '/', 3) = 'practical'
      and split_part(storage_object_name, '/', 4) <> ''
      and split_part(storage_object_name, '/', 5) = ''
      and file_metadata ?& array['file_name', 'mime_type', 'size_bytes']
      and file_metadata - array[
        'file_name', 'mime_type', 'size_bytes',
        'duration_seconds', 'width', 'height'
      ]::text[] = '{}'::jsonb
      and length(btrim(file_metadata ->> 'file_name')) between 1 and 240
      and lower(file_metadata ->> 'mime_type') in (
        'video/mp4', 'video/webm', 'video/quicktime'
      )
      and coalesce(file_metadata ->> 'size_bytes', '') ~ '^[1-9][0-9]{0,11}$'
      and case
        when coalesce(file_metadata ->> 'size_bytes', '')
          ~ '^[1-9][0-9]{0,11}$'
        then (file_metadata ->> 'size_bytes')::numeric <= 52428800
        else false
      end
    )
    or (
      evidence_kind = 'grandfathered'
      and platform is null
      and evidence_url is null
      and storage_object_id is null
      and storage_object_name is null
      and file_metadata = '{}'::jsonb
      and rights_confirmed
    )
  ),
  check (
    status = 'draft'
    or evidence_kind = 'grandfathered'
    or (
      rights_confirmed
      and self_check_codes @> '["product_match"]'::jsonb
      and self_check_codes @> '["watched_full"]'::jsonb
      and self_check_codes @> '["claims_safe"]'::jsonb
      and length(learner_note) between 20 and 2000
    )
  ),
  check (
    (
      status = 'draft'
      and submitted_at is null
      and reviewed_at is null
      and reviewed_by is null
      and review_note is null
    )
    or (
      status = 'submitted'
      and submitted_at is not null
      and reviewed_at is null
      and reviewed_by is null
      and review_note is null
      and submission_revision >= 1
    )
    or (
      status = 'changes_requested'
      and submitted_at is not null
      and reviewed_at is not null
      and reviewed_by is not null
      and review_note is not null
      and submission_revision >= 1
    )
    or (
      status = 'approved'
      and submitted_at is not null
      and reviewed_at is not null
      and submission_revision >= 1
      and (
        (
          evidence_kind = 'grandfathered'
          and reviewed_by is null
          and review_note is not null
        )
        or (
          evidence_kind <> 'grandfathered'
          and reviewed_by is not null
          and review_note is not null
        )
      )
    )
  )
);

create unique index training_practical_projects_storage_object_uq
  on content_factory.training_practical_projects (storage_object_id)
  where storage_object_id is not null;

create index training_practical_projects_review_queue_idx
  on content_factory.training_practical_projects
  (organization_id, status, submitted_at, id)
  where status in ('submitted', 'changes_requested');

create table content_factory.training_practical_review_decisions (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  profile_id uuid not null,
  submission_revision integer not null
    check (submission_revision between 1 and 1000),
  decision text not null check (decision in ('approve', 'request_changes')),
  review_note text not null
    check (length(btrim(review_note)) between 10 and 4000),
  evidence_fingerprint text not null
    check (evidence_fingerprint ~ '^[0-9a-f]{64}$'),
  reviewed_by uuid not null,
  reviewed_at timestamptz not null default now(),
  foreign key (organization_id, project_id)
    references content_factory.training_practical_projects(
      organization_id, id
    ) on delete cascade,
  foreign key (organization_id, profile_id)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (organization_id, reviewed_by)
    references content_factory.memberships(organization_id, profile_id),
  unique (organization_id, project_id, submission_revision)
);

create index training_practical_review_decisions_learner_idx
  on content_factory.training_practical_review_decisions
  (organization_id, profile_id, reviewed_at desc, id desc);

alter table content_factory.training_practical_projects enable row level security;
alter table content_factory.training_practical_review_decisions
  enable row level security;

revoke all on content_factory.training_practical_projects
  from public, anon, authenticated;
revoke all on content_factory.training_practical_review_decisions
  from public, anon, authenticated;
grant all on content_factory.training_practical_projects to service_role;
grant all on content_factory.training_practical_review_decisions to service_role;

create policy training_practical_projects_select_scoped
on content_factory.training_practical_projects
for select
to authenticated
using (
  profile_id = (select auth.uid())
  or exists (
    select 1
    from content_factory.memberships manager
    where manager.organization_id =
      training_practical_projects.organization_id
      and manager.profile_id = (select auth.uid())
      and manager.status = 'active'
      and manager.role in ('owner', 'admin')
  )
);

create policy training_practical_review_decisions_select_scoped
on content_factory.training_practical_review_decisions
for select
to authenticated
using (
  profile_id = (select auth.uid())
  or exists (
    select 1
    from content_factory.memberships manager
    where manager.organization_id =
      training_practical_review_decisions.organization_id
      and manager.profile_id = (select auth.uid())
      and manager.status = 'active'
      and manager.role in ('owner', 'admin')
  )
);

-- Learners do not have the final certificate yet, so their trial MP4 cannot
-- use the operational media bucket.  This separate private bucket grants only
-- an immutable per-user `organization/user/practical/*` upload lane.
insert into storage.buckets (
  id, name, public, file_size_limit, allowed_mime_types
)
values (
  'contentengine-training',
  'contentengine-training',
  false,
  52428800,
  array['video/mp4', 'video/webm', 'video/quicktime']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists contentengine_training_select on storage.objects;
create policy contentengine_training_select
on storage.objects
for select
to authenticated
using (
  bucket_id = 'contentengine-training'
  and (
    (
      split_part(storage.objects.name, '/', 2) = auth.uid()::text
      and split_part(storage.objects.name, '/', 3) = 'practical'
      and exists (
        select 1
        from content_factory.memberships membership
        where membership.organization_id::text =
          split_part(storage.objects.name, '/', 1)
          and membership.profile_id = auth.uid()
          and membership.status = 'active'
      )
    )
    or exists (
      select 1
      from content_factory.memberships manager
      where manager.organization_id::text =
        split_part(storage.objects.name, '/', 1)
        and manager.profile_id = auth.uid()
        and manager.status = 'active'
        and manager.role in ('owner', 'admin')
        and split_part(storage.objects.name, '/', 3) = 'practical'
    )
  )
);

drop policy if exists contentengine_training_insert on storage.objects;
create policy contentengine_training_insert
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'contentengine-training'
  and split_part(storage.objects.name, '/', 2) = auth.uid()::text
  and split_part(storage.objects.name, '/', 3) = 'practical'
  and split_part(storage.objects.name, '/', 4) <> ''
  and split_part(storage.objects.name, '/', 5) = ''
  and exists (
    select 1
    from content_factory.memberships membership
    where membership.organization_id::text =
      split_part(storage.objects.name, '/', 1)
      and membership.profile_id = auth.uid()
      and membership.status = 'active'
  )
);

drop policy if exists contentengine_training_update on storage.objects;

drop policy if exists contentengine_training_delete on storage.objects;
create policy contentengine_training_delete
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'contentengine-training'
  and split_part(storage.objects.name, '/', 2) = auth.uid()::text
  and split_part(storage.objects.name, '/', 3) = 'practical'
  and split_part(storage.objects.name, '/', 4) <> ''
  and split_part(storage.objects.name, '/', 5) = ''
  and exists (
    select 1
    from content_factory.memberships membership
    where membership.organization_id::text =
      split_part(storage.objects.name, '/', 1)
      and membership.profile_id = auth.uid()
      and membership.status = 'active'
  )
  and not exists (
    select 1
    from content_factory.training_practical_projects project
    where project.storage_object_name = storage.objects.name
  )
);

create or replace function
content_factory_private.training_practical_project_json(p_project_id uuid)
returns jsonb
language sql
security definer
stable
set search_path = ''
as $$
  select jsonb_build_object(
    'id', project.id,
    'status', project.status,
    'evidence_url', project.evidence_url,
    'evidence_kind', case project.evidence_kind
      when 'public_url' then 'https_url'
      when 'uploaded_file' then 'private_file'
      else 'grandfathered'
    end,
    'platform', project.platform,
    'is_grandfathered', project.evidence_kind = 'grandfathered',
    'media', case
      when project.evidence_kind = 'uploaded_file' then jsonb_build_object(
        'id', project.storage_object_id,
        'object_key', project.storage_object_name,
        'filename', project.file_metadata ->> 'file_name',
        'mime_type', project.file_metadata ->> 'mime_type',
        'size_bytes', (project.file_metadata ->> 'size_bytes')::bigint
      )
      else null
    end,
    'file_metadata', project.file_metadata,
    'learner_note', project.learner_note,
    'review_note', project.review_note,
    'submitted_at', project.submitted_at,
    'reviewed_at', project.reviewed_at,
    'reviewer_name', coalesce(reviewer.display_name, reviewer.email),
    'version', project.version,
    'attempt_count', project.submission_revision
  )
  from content_factory.training_practical_projects project
  left join content_factory.profiles reviewer
    on reviewer.id = project.reviewed_by
  where project.id = p_project_id
$$;

revoke all on function
  content_factory_private.training_practical_project_json(uuid)
  from public, anon, authenticated;

-- Preserve every workspace that was legitimately open before this migration.
-- The explicit receipt makes grandfathering visible and auditable instead of
-- hiding a date comparison inside each authorization predicate.
insert into content_factory.training_practical_projects (
  organization_id,
  profile_id,
  status,
  evidence_kind,
  learner_note,
  review_note,
  rights_confirmed,
  submission_revision,
  submitted_at,
  reviewed_at,
  created_at,
  updated_at
)
select
  certification.organization_id,
  certification.profile_id,
  'approved',
  'grandfathered',
  '',
  'Доступ сохранён: итоговый экзамен был сдан до запуска обязательной пробной работы.',
  true,
  1,
  certification.granted_at,
  now(),
  certification.granted_at,
  now()
from content_factory.training_certifications certification
where certification.module_code = 'operator_final_exam'
  and certification.status = 'passed'
  and (
    certification.expires_at is null
    or certification.expires_at > now()
  )
on conflict (organization_id, profile_id) do nothing;

-- Browser-issued final attempts always use the reserved `exam:` prefix.  A
-- database-owned certification with another prefix is therefore an explicit
-- trusted administrative fixture/override.  Service-role access could insert
-- an approval directly anyway; recognizing that narrow case keeps restore and
-- test tooling compatible without weakening the browser path.
create or replace function
content_factory_private.training_practical_gate_satisfied(
  p_organization_id uuid,
  p_profile_id uuid
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select
    exists (
      select 1
      from content_factory.training_practical_projects project
      where project.organization_id = p_organization_id
        and project.profile_id = p_profile_id
        and project.status = 'approved'
    )
    or exists (
      select 1
      from content_factory.training_certifications certification
      join content_factory.training_attempts attempt
        on attempt.id = certification.attempt_id
       and attempt.organization_id = certification.organization_id
       and attempt.profile_id = certification.profile_id
       and attempt.module_code = certification.module_code
      where certification.organization_id = p_organization_id
        and certification.profile_id = p_profile_id
        and certification.module_code = 'operator_final_exam'
        and certification.status = 'passed'
        and (
          certification.expires_at is null
          or certification.expires_at > now()
        )
        and attempt.status = 'completed'
        and attempt.passed
        and attempt.idempotency_key not like 'exam:%'
    )
$$;

revoke all on function
  content_factory_private.training_practical_gate_satisfied(uuid, uuid)
  from public, anon, authenticated;

-- The practical is the fifth training boundary, not an alternate route around
-- the four course certificates.  Keep the exact v4 catalog here so both the
-- learner submission and the later manager approval evaluate the same,
-- server-owned prerequisite.
create or replace function
content_factory_private.training_practical_courses_complete(
  p_organization_id uuid,
  p_profile_id uuid
)
returns boolean
language sql
stable
set search_path = ''
as $$
  select count(distinct certification.module_code) = 4
  from content_factory.training_certifications certification
  join content_factory.training_modules module
    on module.code = certification.module_code
   and module.module_type = 'course'
   and module.is_active
  where certification.organization_id = p_organization_id
    and certification.profile_id = p_profile_id
    and certification.module_code = any(array[
      'factory_basics',
      'video_quality',
      'publishing_funnel',
      'security_wb'
    ]::text[])
    and certification.status = 'passed'
    and (
      certification.expires_at is null
      or certification.expires_at > now()
    )
$$;

revoke all on function
  content_factory_private.training_practical_courses_complete(uuid, uuid)
  from public, anon, authenticated;

create or replace function public.creator_save_practical_project(
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
  action_value text;
  evidence_kind_value text;
  platform_value text;
  evidence_url_value text;
  storage_object_id_value uuid;
  storage_object_name_value text;
  storage_metadata_value jsonb;
  file_metadata_value jsonb;
  learner_note_value text;
  rights_confirmed_value boolean := false;
  self_check_codes_value jsonb := '[]'::jsonb;
  expected_version_value integer;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  project_row content_factory.training_practical_projects%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 24000
     or p_payload - array[
       'organization_id', 'action', 'evidence_kind', 'evidence_url',
       'file_metadata', 'object_key', 'media_id', 'platform',
       'learner_note', 'rights_confirmed', 'self_check_codes',
       'expected_version', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'practical_project_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );
  action_value := lower(coalesce(
    nullif(btrim(p_payload ->> 'action'), ''),
    'submit'
  ));
  if action_value not in ('save_draft', 'submit') then
    raise exception using
      errcode = '22023',
      message = 'practical_project_action_invalid';
  end if;
  if action_value = 'submit'
     and not content_factory_private.training_practical_courses_complete(
       organization_id,
       user_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'required_courses_incomplete';
  end if;
  evidence_kind_value := lower(coalesce(
    nullif(btrim(p_payload ->> 'evidence_kind'), ''),
    case
      when nullif(btrim(p_payload ->> 'object_key'), '') is not null
        then 'uploaded_file'
      else 'public_url'
    end
  ));
  evidence_kind_value := case evidence_kind_value
    when 'https_url' then 'public_url'
    when 'private_file' then 'uploaded_file'
    else evidence_kind_value
  end;
  if evidence_kind_value not in ('public_url', 'uploaded_file') then
    raise exception using
      errcode = '22023',
      message = 'practical_project_evidence_kind_invalid';
  end if;
  platform_value := lower(content_factory_private.require_text(
    p_payload, 'platform', 2, 40
  ));
  if platform_value not in ('instagram', 'youtube', 'vk') then
    raise exception using
      errcode = '22023',
      message = 'practical_project_platform_invalid';
  end if;

  if evidence_kind_value = 'public_url' then
    evidence_url_value := content_factory_private.require_text(
      p_payload, 'evidence_url', 12, 2000
    );
    if evidence_url_value !~ '^https://[^[:space:]]+$'
       or evidence_url_value ~ '^https://[^/]*@'
       or evidence_url_value ~* '[?#&](token|signature|password|secret|api[_-]?key)=' then
      raise exception using
        errcode = '22023',
        message = 'practical_project_evidence_url_invalid';
    end if;
    if nullif(btrim(p_payload ->> 'object_key'), '') is not null
       or nullif(btrim(p_payload ->> 'media_id'), '') is not null
       or coalesce(p_payload -> 'file_metadata', '{}'::jsonb) <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'practical_project_file_metadata_invalid';
    end if;
    file_metadata_value := '{}'::jsonb;
  else
    if nullif(btrim(p_payload ->> 'evidence_url'), '') is not null then
      raise exception using
        errcode = '22023',
        message = 'practical_project_evidence_url_invalid';
    end if;
    storage_object_name_value := content_factory_private.require_text(
      p_payload, 'object_key', 80, 1000
    );
    if split_part(storage_object_name_value, '/', 1) <> organization_id::text
       or split_part(storage_object_name_value, '/', 2) <> user_id::text
       or split_part(storage_object_name_value, '/', 3) <> 'practical'
       or split_part(storage_object_name_value, '/', 4) = ''
       or split_part(storage_object_name_value, '/', 5) <> '' then
      raise exception using
        errcode = '22023',
        message = 'practical_project_storage_object_invalid';
    end if;
    select storage_object.id, storage_object.metadata
    into storage_object_id_value, storage_metadata_value
    from storage.objects storage_object
    where storage_object.bucket_id = 'contentengine-training'
      and storage_object.name = storage_object_name_value;
    if storage_object_id_value is null
       or jsonb_typeof(storage_metadata_value) <> 'object'
       or coalesce(storage_metadata_value ->> 'size', '') !~ '^[1-9][0-9]{0,11}$'
       or (case
         when coalesce(storage_metadata_value ->> 'size', '')
           ~ '^[1-9][0-9]{0,11}$'
         then (storage_metadata_value ->> 'size')::numeric > 52428800
         else true
       end)
       or lower(btrim(coalesce(storage_metadata_value ->> 'mimetype', '')))
          not in ('video/mp4', 'video/webm', 'video/quicktime') then
      raise exception using
        errcode = '22023',
        message = 'practical_project_storage_object_invalid';
    end if;
    if nullif(btrim(p_payload ->> 'media_id'), '') is not null
       and content_factory_private.require_uuid(p_payload, 'media_id')
         <> storage_object_id_value then
      raise exception using
        errcode = '22023',
        message = 'practical_project_storage_object_invalid';
    end if;
    if p_payload ? 'file_metadata'
       and jsonb_typeof(p_payload -> 'file_metadata') <> 'object' then
      raise exception using
        errcode = '22023',
        message = 'practical_project_file_metadata_invalid';
    end if;
    file_metadata_value := jsonb_build_object(
      'file_name', left(coalesce(
        nullif(btrim(p_payload #>> '{file_metadata,file_name}'), ''),
        split_part(storage_object_name_value, '/', 4)
      ), 240),
      'mime_type', lower(btrim(storage_metadata_value ->> 'mimetype')),
      'size_bytes', (storage_metadata_value ->> 'size')::bigint
    );
    if length(btrim(file_metadata_value ->> 'file_name')) < 1 then
      raise exception using
        errcode = '22023',
        message = 'practical_project_file_metadata_invalid';
    end if;
  end if;

  learner_note_value := btrim(coalesce(p_payload ->> 'learner_note', ''));
  if length(learner_note_value) > 2000
     or (action_value = 'submit' and length(learner_note_value) < 20) then
    raise exception using
      errcode = '22023',
      message = 'practical_project_learner_note_invalid';
  end if;
  if p_payload ? 'rights_confirmed'
     and jsonb_typeof(p_payload -> 'rights_confirmed') <> 'boolean' then
    raise exception using
      errcode = '22023',
      message = 'practical_project_rights_confirmation_invalid';
  end if;
  rights_confirmed_value := coalesce(
    (p_payload ->> 'rights_confirmed')::boolean,
    false
  );
  self_check_codes_value := coalesce(
    p_payload -> 'self_check_codes',
    '[]'::jsonb
  );
  if jsonb_typeof(self_check_codes_value) <> 'array'
     or jsonb_array_length(self_check_codes_value) > 12
     or exists (
       select 1
       from jsonb_array_elements(self_check_codes_value) code(value)
       where jsonb_typeof(code.value) <> 'string'
          or (code.value #>> '{}') not in (
            'product_match', 'watched_full', 'claims_safe'
          )
     )
     or (
       action_value = 'submit'
       and (
         not rights_confirmed_value
         or not (
           self_check_codes_value @> '["product_match"]'::jsonb
           and self_check_codes_value @> '["watched_full"]'::jsonb
           and self_check_codes_value @> '["claims_safe"]'::jsonb
         )
       )
     ) then
    raise exception using
      errcode = '22023',
      message = 'practical_project_self_check_invalid';
  end if;
  if p_payload ? 'expected_version' then
    if coalesce(p_payload ->> 'expected_version', '') !~ '^[1-9][0-9]{0,6}$' then
      raise exception using
        errcode = '22023',
        message = 'practical_project_expected_version_invalid';
    end if;
    expected_version_value := (p_payload ->> 'expected_version')::integer;
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_payload := jsonb_build_object(
    'action', action_value,
    'evidence_kind', evidence_kind_value,
    'platform', platform_value,
    'evidence_url', evidence_url_value,
    'storage_object_id', storage_object_id_value,
    'storage_object_name', storage_object_name_value,
    'file_metadata', file_metadata_value,
    'learner_note', learner_note_value,
    'rights_confirmed', rights_confirmed_value,
    'self_check_codes', self_check_codes_value,
    'expected_version', expected_version_value
  );

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_save_practical_project',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('training_practical_project')
  );
  select project.* into project_row
  from content_factory.training_practical_projects project
  where project.organization_id = organization_id
    and project.profile_id = user_id
  for update;

  if project_row.status = 'approved' then
    raise exception using
      errcode = '55000',
      message = 'practical_project_already_approved';
  end if;
  if project_row.status = 'submitted' then
    raise exception using
      errcode = '55000',
      message = 'practical_project_review_pending';
  end if;
  if project_row.id is not null
     and expected_version_value is not null
     and project_row.version <> expected_version_value then
    raise exception using
      errcode = '40001',
      message = 'practical_project_version_conflict';
  end if;
  if project_row.id is null and expected_version_value is not null then
    raise exception using
      errcode = '40001',
      message = 'practical_project_version_conflict';
  end if;
  if project_row.status = 'changes_requested'
     and action_value <> 'submit' then
    raise exception using
      errcode = '55000',
      message = 'practical_project_resubmission_required';
  end if;

  if project_row.id is null then
    insert into content_factory.training_practical_projects (
      organization_id,
      profile_id,
      status,
      evidence_kind,
      platform,
      evidence_url,
      storage_object_id,
      storage_object_name,
      file_metadata,
      learner_note,
      rights_confirmed,
      self_check_codes,
      submission_revision,
      submitted_at
    ) values (
      organization_id,
      user_id,
      case when action_value = 'submit' then 'submitted' else 'draft' end,
      evidence_kind_value,
      platform_value,
      evidence_url_value,
      storage_object_id_value,
      storage_object_name_value,
      file_metadata_value,
      learner_note_value,
      rights_confirmed_value,
      self_check_codes_value,
      case when action_value = 'submit' then 1 else 0 end,
      case when action_value = 'submit' then now() else null end
    ) returning * into project_row;
  else
    update content_factory.training_practical_projects project
    set evidence_kind = evidence_kind_value,
        platform = platform_value,
        evidence_url = evidence_url_value,
        storage_object_id = storage_object_id_value,
        storage_object_name = storage_object_name_value,
        file_metadata = file_metadata_value,
        learner_note = learner_note_value,
        rights_confirmed = rights_confirmed_value,
        self_check_codes = self_check_codes_value,
        status = case
          when action_value = 'submit' then 'submitted'
          else project.status
        end,
        submission_revision = case
          when action_value = 'submit'
            then project.submission_revision + 1
          else project.submission_revision
        end,
        submitted_at = case
          when action_value = 'submit' then now()
          else project.submitted_at
        end,
        reviewed_by = case
          when action_value = 'submit' then null
          else project.reviewed_by
        end,
        reviewed_at = case
          when action_value = 'submit' then null
          else project.reviewed_at
        end,
        review_note = case
          when action_value = 'submit' then null
          else project.review_note
        end,
        version = project.version + 1,
        updated_at = now()
    where project.id = project_row.id
    returning * into project_row;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'practical_project',
      content_factory_private.training_practical_project_json(project_row.id)
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case
      when action_value = 'submit'
        then 'training_practical_project_submitted'
      else 'training_practical_project_draft_saved'
    end,
    'training_practical_project',
    project_row.id::text,
    jsonb_build_object(
      'status', project_row.status,
      'evidence_kind', project_row.evidence_kind,
      'submission_revision', project_row.submission_revision
    ),
    'training-practical-save:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_save_practical_project',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_decide_practical_project(
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
  project_id_value uuid;
  decision_value text;
  review_note_value text;
  media_watched_value boolean := false;
  expected_version_value integer;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  project_row content_factory.training_practical_projects%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 12000
     or p_payload - array[
       'organization_id', 'id', 'project_id', 'decision', 'review_note',
       'media_watched_confirmed', 'expected_version', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'practical_project_decision_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin']
  );
  if p_payload ? 'id' and p_payload ? 'project_id'
     and nullif(btrim(p_payload ->> 'id'), '') is distinct from
       nullif(btrim(p_payload ->> 'project_id'), '') then
    raise exception using
      errcode = '22023',
      message = 'practical_project_id_conflict';
  end if;
  project_id_value := case
    when p_payload ? 'project_id' then
      content_factory_private.require_uuid(p_payload, 'project_id')
    else content_factory_private.require_uuid(p_payload, 'id')
  end;
  decision_value := lower(content_factory_private.require_text(
    p_payload, 'decision', 7, 40
  ));
  if decision_value not in ('approve', 'request_changes') then
    raise exception using
      errcode = '22023',
      message = 'practical_project_decision_invalid';
  end if;
  review_note_value := btrim(coalesce(p_payload ->> 'review_note', ''));
  if length(review_note_value) not between 10 and 4000 then
    raise exception using
      errcode = '22023',
      message = 'practical_project_review_note_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'media_watched_confirmed') <> 'boolean'
     or coalesce(
       (p_payload ->> 'media_watched_confirmed')::boolean,
       false
     ) is not true then
    raise exception using
      errcode = '22023',
      message = 'practical_project_media_watch_required';
  end if;
  media_watched_value := true;
  if p_payload ? 'expected_version' then
    if coalesce(p_payload ->> 'expected_version', '') !~ '^[1-9][0-9]{0,6}$' then
      raise exception using
        errcode = '22023',
        message = 'practical_project_expected_version_invalid';
    end if;
    expected_version_value := (p_payload ->> 'expected_version')::integer;
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_payload := jsonb_build_object(
    'id', project_id_value,
    'decision', decision_value,
    'review_note', review_note_value,
    'media_watched_confirmed', media_watched_value,
    'expected_version', expected_version_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_decide_practical_project',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('training_practical_review:' || project_id_value::text)
  );
  select project.* into project_row
  from content_factory.training_practical_projects project
  where project.organization_id = organization_id
    and project.id = project_id_value
  for update;
  if project_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'practical_project_not_found';
  end if;
  if project_row.status <> 'submitted' then
    raise exception using
      errcode = '55000',
      message = 'practical_project_not_reviewable';
  end if;
  if expected_version_value is not null
     and project_row.version <> expected_version_value then
    raise exception using
      errcode = '40001',
      message = 'practical_project_version_conflict';
  end if;
  -- A practical receipt proves independent human review.  Role seniority must
  -- never turn the learner and reviewer into the same identity.
  if project_row.profile_id = user_id then
    raise exception using
      errcode = '42501',
      message = 'practical_project_self_review_not_allowed';
  end if;
  if decision_value = 'approve'
     and not content_factory_private.training_practical_courses_complete(
       organization_id,
       project_row.profile_id
     ) then
    raise exception using
      errcode = '42501',
      message = 'required_courses_incomplete';
  end if;
  if decision_value = 'approve'
     and project_row.evidence_kind <> 'uploaded_file' then
    raise exception using
      errcode = '42501',
      message = 'practical_project_private_file_required';
  end if;

  -- Keep the decision tied to the exact submitted revision.  The receipt
  -- deliberately stores only a SHA-256 fingerprint of the evidence fields:
  -- managers retain an immutable audit trail without duplicating a public URL,
  -- private object key, filename or other learner-supplied metadata.
  insert into content_factory.training_practical_review_decisions (
    organization_id,
    project_id,
    profile_id,
    submission_revision,
    decision,
    review_note,
    evidence_fingerprint,
    reviewed_by
  ) values (
    organization_id,
    project_row.id,
    project_row.profile_id,
    project_row.submission_revision,
    decision_value,
    review_note_value,
    content_factory_private.json_hash(jsonb_build_object(
      'evidence_kind', project_row.evidence_kind,
      'evidence_url', project_row.evidence_url,
      'storage_object_id', project_row.storage_object_id,
      'storage_object_name', project_row.storage_object_name,
      'file_metadata', project_row.file_metadata,
      'platform', project_row.platform
    )),
    user_id
  );

  update content_factory.training_practical_projects project
  set status = case
        when decision_value = 'approve' then 'approved'
        else 'changes_requested'
      end,
      review_note = nullif(review_note_value, ''),
      reviewed_by = user_id,
      reviewed_at = now(),
      version = project.version + 1,
      updated_at = now()
  where project.id = project_row.id
  returning * into project_row;

  result := jsonb_build_object(
    'ok', true,
    'practical_project',
      content_factory_private.training_practical_project_json(project_row.id)
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case
      when decision_value = 'approve'
        then 'training_practical_project_approved'
      else 'training_practical_project_changes_requested'
    end,
    'training_practical_project',
    project_row.id::text,
    jsonb_build_object(
      'learner_id', project_row.profile_id,
      'status', project_row.status,
      'submission_revision', project_row.submission_revision
    ),
    'training-practical-decision:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_practical_project',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

-- Add the approval to the central workspace boundary.  Existing callers keep
-- using membership_role; they cannot accidentally forget the new gate.
alter function content_factory_private.membership_role(uuid, boolean, text[])
  rename to membership_role_pre_practical_gate;

revoke all on function
  content_factory_private.membership_role_pre_practical_gate(
    uuid, boolean, text[]
  )
  from public, anon, authenticated;

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
  actor_role text;
begin
  actor_role := content_factory_private.membership_role_pre_practical_gate(
    organization_id,
    require_certification,
    allowed_roles
  );
  if require_certification and not
    content_factory_private.training_practical_gate_satisfied(
      membership_role.organization_id,
      auth.uid()
    ) then
    raise exception using
      errcode = '42501',
      message = 'practical_project_approval_required';
  end if;
  return actor_role;
end;
$$;

revoke all on function
  content_factory_private.membership_role(uuid, boolean, text[])
  from public, anon, authenticated;

-- Storage policies hold function OIDs, so recreate them after wrapping the
-- predicate; a rename alone would leave those policies on the old gate.
alter function content_factory.storage_access_allowed(text, text, boolean)
  rename to storage_access_allowed_pre_practical_gate;

revoke all on function
  content_factory.storage_access_allowed_pre_practical_gate(
    text, text, boolean
  )
  from public, anon, authenticated;

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
  select
    content_factory.storage_access_allowed_pre_practical_gate(
      p_organization_id,
      p_owner_id,
      p_allow_team_read
    )
    and case
      when p_organization_id ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
      then content_factory_private.training_practical_gate_satisfied(
        p_organization_id::uuid,
        auth.uid()
      )
      else false
    end
$$;

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

-- Refuse a new final exam before review, while preserving exact retries for
-- grandfathered users through their explicit approved receipt.
alter function public.creator_submit_exam(jsonb)
  rename to creator_submit_exam_pre_practical_gate;
alter function public.creator_submit_exam_pre_practical_gate(jsonb)
  set schema content_factory_private;
revoke all on function
  content_factory_private.creator_submit_exam_pre_practical_gate(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_submit_exam(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  user_id uuid;
  organization_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );
  if not content_factory_private.training_practical_gate_satisfied(
    organization_id,
    user_id
  ) then
    raise exception using
      errcode = '42501',
      message = 'practical_project_approval_required';
  end if;
  return content_factory_private.creator_submit_exam_pre_practical_gate(
    p_payload
  );
end;
$$;

-- Project learner state and the small owner/admin review queue into the normal
-- bootstrap response, avoiding polling or an extra page-load RPC.
alter function public.creator_bootstrap(jsonb)
  rename to creator_bootstrap_pre_practical_gate;
alter function public.creator_bootstrap_pre_practical_gate(jsonb)
  set schema content_factory_private;
revoke all on function
  content_factory_private.creator_bootstrap_pre_practical_gate(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_bootstrap(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  result jsonb;
  user_id uuid;
  organization_id uuid;
  actor_role text;
  practical_project jsonb := 'null'::jsonb;
  practical_reviews jsonb := '[]'::jsonb;
  practical_approved boolean := false;
begin
  result := content_factory_private.creator_bootstrap_pre_practical_gate(
    p_payload
  );
  if jsonb_typeof(result) <> 'object'
     or coalesce(result ->> 'state', '') not in (
       'learning', 'workspace', 'password_change_required'
     )
     or nullif(result #>> '{organization,id}', '') is null then
    return result;
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := (result #>> '{organization,id}')::uuid;
  select membership.role into actor_role
  from content_factory.memberships membership
  where membership.organization_id = organization_id
    and membership.profile_id = user_id
    and membership.status = 'active';
  if actor_role is null then
    return result;
  end if;

  select content_factory_private.training_practical_project_json(project.id)
  into practical_project
  from content_factory.training_practical_projects project
  where project.organization_id = organization_id
    and project.profile_id = user_id;
  practical_project := coalesce(practical_project, 'null'::jsonb);
  practical_approved :=
    content_factory_private.training_practical_gate_satisfied(
      organization_id,
      user_id
    );

  if actor_role in ('owner', 'admin')
     and coalesce(result ->> 'state', '') <> 'password_change_required' then
    select coalesce(jsonb_agg(queue.item order by queue.sort_at, queue.id), '[]'::jsonb)
    into practical_reviews
    from (
      select
        project.id,
        coalesce(project.submitted_at, project.updated_at) as sort_at,
        content_factory_private.training_practical_project_json(project.id)
          || jsonb_build_object(
            'learner_name', coalesce(learner.display_name, learner.email),
            'learner_email', learner.email
          ) as item
      from content_factory.training_practical_projects project
      join content_factory.profiles learner
        on learner.id = project.profile_id
      where project.organization_id = organization_id
        and project.status in ('submitted', 'changes_requested')
      order by
        case when project.status = 'submitted' then 0 else 1 end,
        coalesce(project.submitted_at, project.updated_at),
        project.id
      limit 50
    ) queue;
  end if;

  result := result || jsonb_build_object(
    'training',
    coalesce(result -> 'training', '{}'::jsonb) || jsonb_build_object(
      'practical_project', practical_project,
      'practical_reviews', practical_reviews,
      'practical_upload', jsonb_build_object(
        'bucket_id', 'contentengine-training',
        'max_upload_bytes', 52428800,
        'accepted_mime_types', jsonb_build_array(
          'video/mp4', 'video/webm', 'video/quicktime'
        ),
        'path_prefix',
          organization_id::text || '/' || user_id::text || '/practical/'
      )
    )
  );
  result := jsonb_set(
    result,
    '{learning,practical_project_required}',
    to_jsonb(not practical_approved),
    true
  );

  if not practical_approved
     and coalesce(result ->> 'state', '') in ('learning', 'workspace') then
    result := jsonb_set(result, '{state}', '"learning"'::jsonb, true);
    result := jsonb_set(result, '{workspace_open}', 'false'::jsonb, true);
    result := jsonb_set(
      result, '{learning,exam,available}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{learning,exam,questions}', '[]'::jsonb, true
    );
    result := jsonb_set(
      result,
      '{learning,exam,blocked_reason}',
      '"practical_project_approval_required"'::jsonb,
      true
    );
    result := jsonb_set(
      result, '{capabilities,mock_generation}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,real_generation}', 'false'::jsonb, true
    );
  end if;
  return result;
end;
$$;

revoke all on function public.creator_save_practical_project(jsonb)
  from public, anon;
revoke all on function public.creator_decide_practical_project(jsonb)
  from public, anon;
revoke all on function public.creator_submit_exam(jsonb)
  from public, anon;
revoke all on function public.creator_bootstrap(jsonb)
  from public, anon;
revoke all on function
  content_factory.storage_access_allowed(text, text, boolean)
  from public, anon;

grant execute on function public.creator_save_practical_project(jsonb)
  to authenticated;
grant execute on function public.creator_decide_practical_project(jsonb)
  to authenticated;
grant execute on function public.creator_submit_exam(jsonb)
  to authenticated;
grant execute on function public.creator_bootstrap(jsonb)
  to authenticated;
grant execute on function
  content_factory.storage_access_allowed(text, text, boolean)
  to authenticated;

comment on table content_factory.training_practical_projects is
  'One bounded learner evidence receipt and its manager review; never stores raw media or signed access tokens.';
comment on function public.creator_save_practical_project(jsonb) is
  'Saves or submits the caller practical training evidence with idempotency.';
comment on function public.creator_decide_practical_project(jsonb) is
  'Lets an active owner/admin approve submitted practical evidence or request changes.';

do $training_practical_review_contract$
declare
  function_definition text;
  missing_grandfathered integer;
begin
  select count(*) into missing_grandfathered
  from content_factory.training_certifications certification
  where certification.module_code = 'operator_final_exam'
    and certification.status = 'passed'
    and (
      certification.expires_at is null
      or certification.expires_at > now()
    )
    and not exists (
      select 1
      from content_factory.training_practical_projects project
      where project.organization_id = certification.organization_id
        and project.profile_id = certification.profile_id
        and project.status = 'approved'
    );
  if missing_grandfathered <> 0 then
    raise exception
      'training practical review left % existing workspaces without approval',
      missing_grandfathered;
  end if;

  select pg_get_functiondef(
    'content_factory_private.membership_role(uuid,boolean,text[])'::regprocedure
  ) into function_definition;
  if function_definition is null
     or strpos(function_definition, 'practical_project_approval_required') = 0
     or strpos(function_definition, 'training_practical_projects') = 0 then
    raise exception 'membership_role is missing the practical approval gate';
  end if;

  select pg_get_functiondef(
    'public.creator_bootstrap(jsonb)'::regprocedure
  ) into function_definition;
  if function_definition is null
     or strpos(function_definition, 'practical_project') = 0
     or strpos(function_definition, 'practical_reviews') = 0
     or strpos(function_definition, 'limit 50') = 0 then
    raise exception 'creator_bootstrap is missing practical review state';
  end if;
end;
$training_practical_review_contract$;

commit;

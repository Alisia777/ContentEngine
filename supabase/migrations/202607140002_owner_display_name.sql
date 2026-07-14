begin;

-- The GitHub account/repository name remains unchanged. Only the human-facing
-- owner identity used by team lists and task assignee joins is renamed.
with target_owner as materialized (
  select membership.profile_id
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
  join content_factory.profiles profile
    on profile.id = membership.profile_id
  where organization.slug = 'altea-content-factory'
    and organization.status = 'active'
    and membership.role = 'owner'
    and membership.status = 'active'
    and profile.status = 'active'
  order by membership.created_at, membership.id
  limit 1
)
update auth.users auth_user
set raw_user_meta_data = coalesce(auth_user.raw_user_meta_data, '{}'::jsonb)
      || jsonb_build_object('display_name', 'Сергей'),
    updated_at = now()
where auth_user.id = (select profile_id from target_owner)
  and auth_user.deleted_at is null;

with target_owner as materialized (
  select membership.profile_id
  from content_factory.memberships membership
  join content_factory.organizations organization
    on organization.id = membership.organization_id
  join content_factory.profiles profile
    on profile.id = membership.profile_id
  where organization.slug = 'altea-content-factory'
    and organization.status = 'active'
    and membership.role = 'owner'
    and membership.status = 'active'
    and profile.status = 'active'
  order by membership.created_at, membership.id
  limit 1
)
update content_factory.profiles profile
set display_name = 'Сергей',
    updated_at = now()
where profile.id = (select profile_id from target_owner);

commit;

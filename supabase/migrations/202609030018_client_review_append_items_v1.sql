begin;
-- 202609030018_client_review_append_items_v1
--
-- Фидбек первого прогона с телефона (владелец, 03.09): после решения по
-- единственному ролику клиент упирается в «а дальше роликов нет», а
-- состав ссылки фиксировался при выдаче — новые ролики требовали новой
-- ссылки. Теперь оператор ДО-ДОБАВЛЯЕТ ролики в активную ссылку: клиент
-- видит их по той же ссылке. Проверки те же, что при выдаче (ready +
-- generated/finalized, QA-гейт с кураторской отметкой), позиции — после
-- максимальной, суммарный потолок 50, дубли тихо пропускаются.

create or replace function public.creator_append_client_review_link_items(
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
  link_row content_factory.client_review_links%rowtype;
  curator_attested boolean;
  media_ids uuid[];
  media_id uuid;
  media_row content_factory.media_objects%rowtype;
  has_approved boolean;
  next_position integer;
  existing_count integer;
  added_count integer := 0;
  skipped_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'operator']
  );
  curator_attested := coalesce(
    (p_payload ->> 'curator_attested')::boolean, false
  );

  select link.* into link_row
  from content_factory.client_review_links link
  where link.organization_id = organization_id
    and link.id = content_factory_private.require_uuid(p_payload, 'link_id')
    and link.status = 'active'
    and link.expires_at > now();
  if link_row.id is null then
    raise exception using errcode = 'P0002',
      message = 'client_review_link_not_found';
  end if;

  if jsonb_typeof(p_payload -> 'media_ids') <> 'array'
     or jsonb_array_length(p_payload -> 'media_ids') not between 1 and 50 then
    raise exception using errcode = '22023',
      message = 'client_review_media_ids_invalid';
  end if;
  begin
    select array_agg(value::uuid)
    into media_ids
    from jsonb_array_elements_text(p_payload -> 'media_ids');
  exception when invalid_text_representation then
    raise exception using errcode = '22023',
      message = 'client_review_media_ids_invalid';
  end;

  select count(*)::integer, coalesce(max(item.position), 0)
  into existing_count, next_position
  from content_factory.client_review_link_items item
  where item.link_id = link_row.id;
  if existing_count + array_length(media_ids, 1) > 50 then
    raise exception using errcode = '22023',
      message = 'client_review_media_ids_invalid';
  end if;

  foreach media_id in array media_ids loop
    if exists (
      select 1 from content_factory.client_review_link_items item
      where item.link_id = link_row.id
        and item.media_object_id = media_id
    ) then
      skipped_count := skipped_count + 1;
      continue;
    end if;
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.id = media_id
      and media.status = 'ready';
    if media_row.id is null
       or coalesce(media_row.metadata ->> 'kind', '')
         not in ('generated_video', 'finalized_video') then
      raise exception using errcode = '22023',
        message = 'client_review_media_not_reviewable';
    end if;
    select exists (
      select 1
      from content_factory.content_review_runs runs
      join content_factory.content_review_decisions decisions
        on decisions.review_id = runs.id
      where runs.organization_id = organization_id
        and runs.media_object_id = media_row.id
        and decisions.decision = 'approved'
    ) into has_approved;
    if not has_approved and not curator_attested then
      raise exception using errcode = '22023',
        message = 'client_review_media_not_accepted';
    end if;
    next_position := next_position + 1;
    insert into content_factory.client_review_link_items (
      link_id, organization_id, media_object_id, position, curator_attested
    ) values (
      link_row.id, organization_id, media_row.id, next_position,
      not has_approved
    );
    added_count := added_count + 1;
  end loop;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-links-v1',
    'link', jsonb_build_object(
      'id', link_row.id,
      'added', added_count,
      'skipped_duplicates', skipped_count
    )
  );
end;
$$;

revoke all on function
  public.creator_append_client_review_link_items(jsonb)
  from public, anon, service_role;
grant execute on function
  public.creator_append_client_review_link_items(jsonb)
  to authenticated;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  definition_value text;
begin
  if has_function_privilege(
       'anon',
       'public.creator_append_client_review_link_items(jsonb)', 'execute'
     ) then
    raise exception using message = 'client_review_append_anon_leak';
  end if;
  definition_value := pg_get_functiondef(
    'public.creator_append_client_review_link_items(jsonb)'::regprocedure
  );
  if position('client_review_media_not_accepted' in definition_value) = 0
     or position('skipped_count' in definition_value) = 0 then
    raise exception using message = 'client_review_append_contract_broken';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

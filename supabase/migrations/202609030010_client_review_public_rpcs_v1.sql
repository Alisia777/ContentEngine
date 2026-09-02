begin;
-- 202609030010_client_review_public_rpcs_v1
--
-- Системная сторона витрины: два RPC для edge-функции client-review
-- (auth: none, зовёт service_role). Токен — вся авторизация; по образцу
-- recovery-контура ответы анти-энумерационные: несуществующая, отозванная
-- и истёкшая ссылка неотличимы (единый client_review_not_found), cooldown
-- превышения отвечают retry_after_seconds без деталей. Каждый заход
-- журналируется в client_review_access_log (в т.ч. для несуществующих
-- токенов — по журналу считается rate-limit). Решение клиента
-- (accepted / returned / publish_requested) идемпотентно по
-- client_request_id и будит команду через notification_outbox.

create or replace function public.system_client_review_view(
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
  token_hash_value text;
  client_key_value text;
  link_row content_factory.client_review_links%rowtype;
  campaign_name text;
  token_hour_count integer;
  client_hour_count integer;
  items_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  token_hash_value := lower(btrim(
    coalesce(p_payload ->> 'token_hash', '')
  ));
  client_key_value := lower(btrim(
    coalesce(p_payload ->> 'client_key_hash', '')
  ));
  if token_hash_value !~ '^[0-9a-f]{64}$'
     or client_key_value !~ '^[0-9a-f]{16,128}$' then
    raise exception using errcode = '22023',
      message = 'client_review_request_invalid';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-client-review:' || token_hash_value, 0
    )
  );

  -- Rate-limit по журналу: превышение отвечает ДО раскрытия судьбы токена.
  select count(*) into token_hour_count
  from content_factory.client_review_access_log log
  where log.token_hash = token_hash_value
    and log.created_at > now() - interval '1 hour';
  select count(*) into client_hour_count
  from content_factory.client_review_access_log log
  where log.client_key_hash = client_key_value
    and log.created_at > now() - interval '1 hour';
  if token_hour_count >= 60 or client_hour_count >= 120 then
    insert into content_factory.client_review_access_log
      (token_hash, client_key_hash, action)
    values (token_hash_value, client_key_value, 'refused');
    return jsonb_build_object(
      'ok', false,
      'code', 'client_review_rate_limited',
      'retry_after_seconds', 900
    );
  end if;

  insert into content_factory.client_review_access_log
    (token_hash, client_key_hash, action)
  values (token_hash_value, client_key_value, 'view');

  select link.* into link_row
  from content_factory.client_review_links link
  where link.token_hash = token_hash_value
    and link.status = 'active'
    and link.expires_at > now()
    and link.view_count < link.view_limit;
  if link_row.id is null then
    -- Единый ответ: нет токена, отозван, истёк или выбран лимит — снаружи
    -- неотличимо.
    return jsonb_build_object(
      'ok', false, 'code', 'client_review_not_found'
    );
  end if;

  update content_factory.client_review_links link
  set view_count = link.view_count + 1,
      last_viewed_at = now(),
      updated_at = now()
  where link.id = link_row.id;

  select campaign.name into campaign_name
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = link_row.organization_id
    and campaign.id = link_row.campaign_id;

  select coalesce(jsonb_agg(jsonb_build_object(
    'item_id', item.id,
    'position', item.position,
    'media_object_id', item.media_object_id,
    'bucket_id', media.bucket_id,
    'object_name', media.object_name,
    'duration_seconds', media.metadata ->> 'duration_seconds',
    'title', coalesce(
      media.metadata ->> 'original_filename',
      'Ролик ' || item.position
    ),
    'last_decision', (
      select jsonb_build_object(
        'decision', decision.decision,
        'comment', decision.comment,
        'created_at', decision.created_at
      )
      from content_factory.client_review_decisions decision
      where decision.item_id = item.id
      order by decision.created_at desc
      limit 1
    ),
    'published', (
      select jsonb_build_object(
        'status', job.status,
        'final_url', job.final_url
      )
      from content_factory.publishing_jobs job
      where job.organization_id = item.organization_id
        and job.media_object_id = item.media_object_id
        and job.final_url is not null
      order by job.created_at desc
      limit 1
    )
  ) order by item.position), '[]'::jsonb)
  into items_value
  from content_factory.client_review_link_items item
  join content_factory.media_objects media
    on media.organization_id = item.organization_id
   and media.id = item.media_object_id
  where item.link_id = link_row.id;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-view-v1',
    'client_label', link_row.client_label,
    'campaign_name', coalesce(campaign_name, ''),
    'expires_at', link_row.expires_at,
    'intake_enabled', link_row.intake_enabled,
    'items', items_value
  );
end;
$$;

create or replace function public.system_client_review_decide(
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
  token_hash_value text;
  client_key_value text;
  item_id_value uuid;
  request_id_value uuid;
  decision_value text;
  comment_value text;
  link_row content_factory.client_review_links%rowtype;
  item_row content_factory.client_review_link_items%rowtype;
  existing_decision content_factory.client_review_decisions%rowtype;
  decision_title text;
  decision_body text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  token_hash_value := lower(btrim(
    coalesce(p_payload ->> 'token_hash', '')
  ));
  client_key_value := lower(btrim(
    coalesce(p_payload ->> 'client_key_hash', '')
  ));
  if token_hash_value !~ '^[0-9a-f]{64}$'
     or client_key_value !~ '^[0-9a-f]{16,128}$' then
    raise exception using errcode = '22023',
      message = 'client_review_request_invalid';
  end if;
  item_id_value := content_factory_private.require_uuid(
    p_payload, 'item_id'
  );
  request_id_value := content_factory_private.require_uuid(
    p_payload, 'client_request_id'
  );
  decision_value := coalesce(p_payload ->> 'decision', '');
  if decision_value not in ('accepted', 'returned', 'publish_requested') then
    raise exception using errcode = '22023',
      message = 'client_review_decision_invalid';
  end if;
  comment_value := nullif(btrim(coalesce(p_payload ->> 'comment', '')), '');
  if decision_value = 'returned' and comment_value is null then
    raise exception using errcode = '22023',
      message = 'client_review_comment_required';
  end if;
  if comment_value is not null then
    if length(comment_value) not between 3 and 2000 then
      raise exception using errcode = '22023',
        message = 'client_review_comment_invalid';
    end if;
    if content_factory_private.notification_payload_sensitive_v491(
         jsonb_build_object('comment', comment_value)
       ) then
      raise exception using errcode = '22023',
        message = 'client_review_comment_invalid';
    end if;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-client-review:' || token_hash_value, 0
    )
  );

  select link.* into link_row
  from content_factory.client_review_links link
  where link.token_hash = token_hash_value
    and link.status = 'active'
    and link.expires_at > now();
  if link_row.id is null then
    return jsonb_build_object(
      'ok', false, 'code', 'client_review_not_found'
    );
  end if;

  select item.* into item_row
  from content_factory.client_review_link_items item
  where item.id = item_id_value
    and item.link_id = link_row.id;
  if item_row.id is null then
    return jsonb_build_object(
      'ok', false, 'code', 'client_review_not_found'
    );
  end if;

  -- Идемпотентность решения: повтор client_request_id возвращает прежний
  -- результат и не плодит ни строк, ни уведомлений.
  select decision.* into existing_decision
  from content_factory.client_review_decisions decision
  where decision.item_id = item_row.id
    and decision.client_request_id = request_id_value;
  if existing_decision.id is not null then
    return jsonb_build_object(
      'ok', true,
      'version', 'client-review-decide-v1',
      'replayed', true,
      'decision', existing_decision.decision
    );
  end if;

  if link_row.decision_count >= link_row.decide_limit then
    insert into content_factory.client_review_access_log
      (token_hash, client_key_hash, action)
    values (token_hash_value, client_key_value, 'refused');
    return jsonb_build_object(
      'ok', false,
      'code', 'client_review_rate_limited',
      'retry_after_seconds', 3600
    );
  end if;

  insert into content_factory.client_review_decisions (
    link_id, item_id, organization_id, decision, comment, client_request_id
  ) values (
    link_row.id, item_row.id, link_row.organization_id, decision_value,
    comment_value, request_id_value
  );

  update content_factory.client_review_links link
  set decision_count = link.decision_count + 1,
      updated_at = now()
  where link.id = link_row.id;

  insert into content_factory.client_review_access_log
    (token_hash, client_key_hash, action)
  values (token_hash_value, client_key_value, 'decide');

  decision_title := case decision_value
    when 'accepted' then 'Клиент принял ролик'
    when 'returned' then 'Клиент вернул ролик с комментарием'
    else 'Клиент просит опубликовать ролик'
  end;
  decision_body := case decision_value
    when 'accepted' then
      'Ролик витрины «' || link_row.client_label || '» принят клиентом.'
    when 'returned' then
      'Клиент вернул ролик витрины «' || link_row.client_label
        || '». Комментарий: ' || left(comment_value, 500)
    else
      'Клиент витрины «' || link_row.client_label
        || '» просит опубликовать ролик. Публикация выполняется '
        || 'оператором по чек-листу.'
  end;

  insert into content_factory.notification_outbox (
    organization_id, recipient_id, kind, severity, title, body,
    deep_link, entity_type, entity_id, properties, request_hash,
    dedupe_key
  ) values (
    link_row.organization_id,
    link_row.created_by,
    'client_review_decision',
    case when decision_value = 'returned' then 'warning' else 'info' end,
    decision_title,
    decision_body,
    '#/workspace/team?view=campaign&campaign=' || link_row.campaign_id::text,
    'client_review_link_item',
    item_row.id::text,
    jsonb_build_object(
      'source', 'client_review_showcase',
      'link_id', link_row.id,
      'campaign_id', link_row.campaign_id,
      'media_object_id', item_row.media_object_id,
      'decision', decision_value
    ),
    content_factory_private.json_hash(jsonb_build_object(
      'recipient_id', link_row.created_by,
      'kind', 'client_review_decision',
      'entity_id', item_row.id,
      'client_request_id', request_id_value
    )),
    left(
      'client-review:' || item_row.id::text || ':'
        || request_id_value::text,
      180
    )
  )
  on conflict (organization_id, recipient_id, dedupe_key) do nothing;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-decide-v1',
    'replayed', false,
    'decision', decision_value
  );
end;
$$;

revoke all on function public.system_client_review_view(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_client_review_view(jsonb)
  to service_role;
revoke all on function public.system_client_review_decide(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_client_review_decide(jsonb)
  to service_role;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  view_result jsonb;
  fake_token constant text :=
    repeat('0', 64);
  fake_client constant text :=
    repeat('a', 32);
begin
  -- Несуществующий токен: единый not_found, журнал получает строку view.
  view_result := public.system_client_review_view(jsonb_build_object(
    'token_hash', fake_token,
    'client_key_hash', fake_client
  ));
  if view_result ->> 'ok' <> 'false'
     or view_result ->> 'code' <> 'client_review_not_found' then
    raise exception using message = 'client_review_view_enumeration_leak';
  end if;
  if not exists (
    select 1 from content_factory.client_review_access_log log
    where log.token_hash = fake_token and log.action = 'view'
  ) then
    raise exception using message = 'client_review_access_log_silent';
  end if;
  -- Браузерные роли не могут звать системные RPC.
  if has_function_privilege(
       'authenticated', 'public.system_client_review_view(jsonb)', 'execute'
     )
     or has_function_privilege(
       'anon', 'public.system_client_review_decide(jsonb)', 'execute'
     ) then
    raise exception using message = 'client_review_system_rpc_leak';
  end if;
  -- Чистим след verify-блока.
  delete from content_factory.client_review_access_log log
  where log.token_hash = fake_token;
end;
$verify$;

commit;

begin;
-- 202609030015_client_intake_public_rpcs_v1
--
-- Системная сторона клиентского ввода (зовёт edge client-review,
-- service_role): init загрузки файла (суточные лимиты, whitelist типов,
-- путь в приватном бакете под владельцем-оператором) и сдача брифа
-- (лимит 5/сутки, уведомление оператору). Плюс re-emit
-- system_client_review_view: клиент видит на странице статус своих
-- брифов («принят в работу» / «возвращён с комментарием»). Файлы клиент
-- грузит НАПРЯМУЮ в storage по подписанному upload-URL — тело файла
-- через edge не проходит (боевой урок Memory limit, 21-23.08).

create or replace function public.system_client_intake_upload_init(
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
  filename_value text;
  mime_value text;
  size_value bigint;
  request_id_value uuid;
  link_row content_factory.client_review_links%rowtype;
  uploads_today integer;
  upload_row content_factory.client_intake_uploads%rowtype;
  extension_value text;
  owner_value uuid;
  object_name_value text;
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
  filename_value := btrim(coalesce(p_payload ->> 'original_filename', ''));
  if length(filename_value) not between 1 and 255 then
    raise exception using errcode = '22023',
      message = 'client_intake_filename_invalid';
  end if;
  mime_value := lower(btrim(coalesce(p_payload ->> 'mime_type', '')));
  if mime_value not in (
    'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
  ) then
    raise exception using errcode = '22023',
      message = 'client_intake_type_invalid';
  end if;
  size_value := coalesce(
    nullif(p_payload ->> 'size_bytes', '')::bigint, 0
  );
  if size_value not between 1 and 52428800 then
    raise exception using errcode = '22023',
      message = 'client_intake_size_invalid';
  end if;
  if (p_payload ->> 'rights_confirmed')::boolean is distinct from true then
    raise exception using errcode = '22023',
      message = 'client_intake_rights_required';
  end if;
  request_id_value := content_factory_private.require_uuid(
    p_payload, 'client_request_id'
  );

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-client-review:' || token_hash_value, 0
    )
  );

  select link.* into link_row
  from content_factory.client_review_links link
  where link.token_hash = token_hash_value
    and link.status = 'active'
    and link.expires_at > now()
    and link.intake_enabled;
  if link_row.id is null then
    return jsonb_build_object(
      'ok', false, 'code', 'client_review_not_found'
    );
  end if;

  -- Идемпотентность повтора того же запроса.
  select upload.* into upload_row
  from content_factory.client_intake_uploads upload
  where upload.link_id = link_row.id
    and upload.client_request_id = request_id_value;
  if upload_row.id is not null then
    return jsonb_build_object(
      'ok', true,
      'version', 'client-intake-v1',
      'replayed', true,
      'upload', jsonb_build_object(
        'id', upload_row.id,
        'object_name', upload_row.object_name
      )
    );
  end if;

  select count(*) into uploads_today
  from content_factory.client_intake_uploads upload
  where upload.link_id = link_row.id
    and upload.created_at > now() - interval '24 hours';
  if uploads_today >= 20 then
    return jsonb_build_object(
      'ok', false,
      'code', 'client_review_rate_limited',
      'retry_after_seconds', 3600
    );
  end if;

  extension_value := case mime_value
    when 'image/jpeg' then 'jpg'
    when 'image/png' then 'png'
    when 'image/webp' then 'webp'
    else 'mp4'
  end;
  owner_value := coalesce(
    link_row.intake_owner_profile_id, link_row.created_by
  );
  insert into content_factory.client_intake_uploads (
    link_id, organization_id, object_name, original_filename, mime_type,
    size_bytes, rights_confirmed, client_request_id
  ) values (
    link_row.id, link_row.organization_id,
    link_row.organization_id::text || '/' || owner_value::text
      || '/client-intake/' || link_row.id::text || '/'
      || extensions.gen_random_uuid()::text || '.' || extension_value,
    filename_value, mime_value, size_value, true, request_id_value
  )
  returning * into upload_row;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-intake-v1',
    'replayed', false,
    'upload', jsonb_build_object(
      'id', upload_row.id,
      'object_name', upload_row.object_name
    )
  );
end;
$$;

create or replace function public.system_client_intake_submit_brief(
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
  request_id_value uuid;
  link_row content_factory.client_review_links%rowtype;
  brief_row content_factory.client_intake_briefs%rowtype;
  briefs_today integer;
  product_value text;
  audience_value text;
  tone_value text;
  restrictions_value text;
  wishes_value text;
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
  request_id_value := content_factory_private.require_uuid(
    p_payload, 'client_request_id'
  );
  product_value := btrim(coalesce(p_payload ->> 'brief_product', ''));
  audience_value := btrim(coalesce(p_payload ->> 'brief_audience', ''));
  tone_value := btrim(coalesce(p_payload ->> 'brief_tone', ''));
  restrictions_value := nullif(btrim(
    coalesce(p_payload ->> 'brief_restrictions', '')
  ), '');
  wishes_value := nullif(btrim(
    coalesce(p_payload ->> 'brief_wishes', '')
  ), '');
  if length(product_value) not between 2 and 180
     or length(audience_value) not between 3 and 600
     or length(tone_value) not between 3 and 400
     or coalesce(length(restrictions_value), 0) > 800
     or coalesce(length(wishes_value), 0) > 1200 then
    raise exception using errcode = '22023',
      message = 'client_intake_brief_invalid';
  end if;
  if content_factory_private.notification_payload_sensitive_v491(
       jsonb_build_object(
         'product', product_value, 'audience', audience_value,
         'tone', tone_value, 'restrictions', restrictions_value,
         'wishes', wishes_value
       )
     ) then
    raise exception using errcode = '22023',
      message = 'client_intake_brief_invalid';
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
    and link.expires_at > now()
    and link.intake_enabled;
  if link_row.id is null then
    return jsonb_build_object(
      'ok', false, 'code', 'client_review_not_found'
    );
  end if;

  select brief.* into brief_row
  from content_factory.client_intake_briefs brief
  where brief.link_id = link_row.id
    and brief.client_request_id = request_id_value;
  if brief_row.id is not null then
    return jsonb_build_object(
      'ok', true,
      'version', 'client-intake-v1',
      'replayed', true,
      'brief', jsonb_build_object(
        'id', brief_row.id, 'status', brief_row.status
      )
    );
  end if;

  select count(*) into briefs_today
  from content_factory.client_intake_briefs brief
  where brief.link_id = link_row.id
    and brief.created_at > now() - interval '24 hours';
  if briefs_today >= 5 then
    return jsonb_build_object(
      'ok', false,
      'code', 'client_review_rate_limited',
      'retry_after_seconds', 3600
    );
  end if;

  insert into content_factory.client_intake_briefs (
    link_id, organization_id, brief_product, brief_audience, brief_tone,
    brief_restrictions, brief_wishes, client_request_id
  ) values (
    link_row.id, link_row.organization_id, product_value, audience_value,
    tone_value, restrictions_value, wishes_value, request_id_value
  )
  returning * into brief_row;

  insert into content_factory.notification_outbox (
    organization_id, recipient_id, kind, severity, title, body,
    deep_link, entity_type, entity_id, properties, request_hash,
    dedupe_key
  ) values (
    link_row.organization_id,
    coalesce(link_row.intake_owner_profile_id, link_row.created_by),
    'client_intake_brief',
    'info',
    'Клиент прислал бриф и материалы',
    'Витрина «' || link_row.client_label || '»: новый бриф товара «'
      || left(product_value, 120)
      || '». Откройте «Ссылки и решения клиента» кампании и примите '
      || 'бриф в работу.',
    '#/workspace/team?view=campaign&campaign=' || link_row.campaign_id::text,
    'client_intake_brief',
    brief_row.id::text,
    jsonb_build_object(
      'source', 'client_review_showcase',
      'link_id', link_row.id,
      'campaign_id', link_row.campaign_id
    ),
    content_factory_private.json_hash(jsonb_build_object(
      'recipient_id',
        coalesce(link_row.intake_owner_profile_id, link_row.created_by),
      'kind', 'client_intake_brief',
      'entity_id', brief_row.id
    )),
    left('client-intake:' || brief_row.id::text, 180)
  )
  on conflict (organization_id, recipient_id, dedupe_key) do nothing;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-intake-v1',
    'replayed', false,
    'brief', jsonb_build_object(
      'id', brief_row.id, 'status', brief_row.status
    )
  );
end;
$$;

revoke all on function public.system_client_intake_upload_init(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_client_intake_upload_init(jsonb)
  to service_role;
revoke all on function public.system_client_intake_submit_brief(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_client_intake_submit_brief(jsonb)
  to service_role;

-- Re-emit view: клиент видит статусы своих брифов на странице.
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
  briefs_value jsonb;
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

  select coalesce(jsonb_agg(jsonb_build_object(
    'brief_product', brief.brief_product,
    'status', brief.status,
    'operator_comment', brief.operator_comment,
    'created_at', brief.created_at
  ) order by brief.created_at desc), '[]'::jsonb)
  into briefs_value
  from content_factory.client_intake_briefs brief
  where brief.link_id = link_row.id;

  return jsonb_build_object(
    'ok', true,
    'version', 'client-review-view-v1',
    'client_label', link_row.client_label,
    'campaign_name', coalesce(campaign_name, ''),
    'expires_at', link_row.expires_at,
    'intake_enabled', link_row.intake_enabled,
    'intake_briefs', briefs_value,
    'items', items_value
  );
end;
$$;

revoke all on function public.system_client_review_view(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_client_review_view(jsonb)
  to service_role;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  view_result jsonb;
  fake_token constant text := repeat('1', 64);
  fake_client constant text := repeat('b', 32);
begin
  -- Анти-энумерация пережила re-emit view.
  view_result := public.system_client_review_view(jsonb_build_object(
    'token_hash', fake_token,
    'client_key_hash', fake_client
  ));
  if view_result ->> 'code' is distinct from 'client_review_not_found' then
    raise exception using message = 'client_intake_view_enumeration_leak';
  end if;
  delete from content_factory.client_review_access_log log
  where log.token_hash = fake_token;
  -- Интейк-RPC закрыты от токена без intake_enabled: единый not_found.
  view_result := public.system_client_intake_submit_brief(
    jsonb_build_object(
      'token_hash', fake_token,
      'client_key_hash', fake_client,
      'client_request_id', extensions.gen_random_uuid(),
      'brief_product', 'Проверка',
      'brief_audience', 'Проверка поведения',
      'brief_tone', 'Нейтральный'
    )
  );
  if view_result ->> 'code' is distinct from 'client_review_not_found' then
    raise exception using message = 'client_intake_brief_enumeration_leak';
  end if;
  if has_function_privilege(
       'authenticated',
       'public.system_client_intake_upload_init(jsonb)', 'execute')
     or has_function_privilege(
       'anon',
       'public.system_client_intake_submit_brief(jsonb)', 'execute') then
    raise exception using message = 'client_intake_system_rpc_leak';
  end if;
end;
$verify$;

notify pgrst, 'reload schema';

commit;

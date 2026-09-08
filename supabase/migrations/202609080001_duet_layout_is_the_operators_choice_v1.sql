begin;

-- 202609080001_duet_layout_is_the_operators_choice_v1
--
-- Регуляторы врезки в панели «Дуэта» перестают быть декорацией.
--
-- ЧТО НАБЛЮДАЛОСЬ. Панель рисует три ЖИВЫХ регулятора — угол, вид и ширину
-- врезки — и подписывает их «раскладку можно поменять для конкретного ролика».
-- Значение доезжает до передачи (`duet_layout` в handoff) и там умирает:
-- дальше его не читает никто. Привязка подписывает раскладку ИСКЛЮЧИТЕЛЬНО из
-- карточки ведущего и ключа `duet_layout` в полезной нагрузке не принимает
-- вовсе — строгая проверка состава отвергла бы его как чужой.
--
-- Итог для оператора: он ставит ведущего в правый верхний угол шириной 50%,
-- платит, и получает ролик с ведущим в левом нижнем на 34%. Регулятор, который
-- ничего не меняет, хуже отсутствующего: он обещает управление, которого нет.
--
-- РЕШЕНИЕ ВЛАДЕЛЬЦА 22.08.2026 требовало ровно обратного: «оператор мог
-- переопределить её для этого ролика, и подписана должна быть ЕГО версия».
-- Миграция 202608230008 этого не сделала — мой недосмотр, и вот он исправлен.
--
-- ПОЧЕМУ ЭТО БЕЗОПАСНО ДЛЯ РАБОТАЮЩЕГО ДУЭТА. Ключ НЕОБЯЗАТЕЛЬНЫЙ. Нет ключа —
-- раскладка по-прежнему берётся из карточки ведущего, и снимок получается
-- байт в байт таким же, как сегодня. Значит ни одна существующая привязка не
-- разъедется и ни один повтор не упрётся в конфликт. Поведение меняется РОВНО
-- тогда, когда браузер начнёт присылать раскладку.
--
-- ОТКАЗ ИМЕНОВАННЫЙ, А НЕ ОБЩИЙ. Форму раскладки и так проверяет
-- generation_spec_strategy_snapshot_valid, но её отказ звучит как
-- «снимок неверен» — оператору с ним делать нечего. Поэтому проверка стоит
-- здесь, до сборки снимка, и называет причину.
--
-- ЗАПРЕЩЁН ОСТАЛЬНЫМ, как и ведущий. Раскладка у «Копии» означала бы
-- подписанный факт, которого в запросе к провайдеру не будет.

do $duet_layout_from_operator$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_bind_generation_spec_strategy(jsonb)'::regprocedure
  );
  if position('generation_strategy_binding_duet_layout_invalid' in source_text) > 0
  then
    return;
  end if;
  patched_text := source_text;

  -- 1. Ключ становится ДОПУСТИМЫМ. Обязательным он не бывает никогда:
  --    отсутствие — это «оставить раскладку ведущего».
  anchor := E'       ''avatar_likeness_consent_confirmed'', ''confirmation'', ''idempotency_key'',\n'
         || E'       ''duet_presenter_id''\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_layout_anchor_payload_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'       ''avatar_likeness_consent_confirmed'', ''confirmation'', ''idempotency_key'',\n'
      || E'       ''duet_presenter_id'', ''duet_layout''\n'
  );

  -- 2. Источник раскладки: сначала выбор оператора, потом карточка ведущего.
  anchor := E'    duet_layout_value := duet_presenter_identity_value -> ''layout'';\n'
         || E'  elsif p_payload ? ''duet_presenter_id'' then';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_layout_anchor_source';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    -- Раскладку выбирает ОПЕРАТОР под конкретный ролик, и подписывается\n'
      || E'    -- именно его версия (решение владельца 22.08.2026). Карточка\n'
      || E'    -- ведущего остаётся значением по умолчанию: не прислали ключ —\n'
      || E'    -- берём её, и снимок выходит ровно таким же, как прежде.\n'
      || E'    if p_payload ? ''duet_layout'' then\n'
      || E'      duet_layout_value := p_payload -> ''duet_layout'';\n'
      || E'      -- Форму проверяет и снимок, но его отказ звучит как «снимок\n'
      || E'      -- неверен» — с таким оператору делать нечего. Причина\n'
      || E'      -- называется здесь.\n'
      || E'      if jsonb_typeof(duet_layout_value) <> ''object''\n'
      || E'         or duet_layout_value - array[\n'
      || E'              ''corner'', ''shape'', ''widthPercent''\n'
      || E'            ]::text[] <> ''{}''::jsonb\n'
      || E'         or not duet_layout_value ?& array[\n'
      || E'              ''corner'', ''shape'', ''widthPercent''\n'
      || E'            ]::text[]\n'
      || E'         or duet_layout_value ->> ''corner'' not in (\n'
      || E'              ''bottom_left'', ''bottom_right'', ''top_left'', ''top_right''\n'
      || E'            )\n'
      || E'         or duet_layout_value ->> ''shape'' not in (''cutout'', ''window'')\n'
      || E'         or jsonb_typeof(duet_layout_value -> ''widthPercent'') <> ''number''\n'
      || E'         or (duet_layout_value ->> ''widthPercent'')::numeric\n'
      || E'              not between 20 and 50 then\n'
      || E'        raise exception using errcode = ''22023'',\n'
      || E'          message = ''generation_strategy_binding_duet_layout_invalid'';\n'
      || E'      end if;\n'
      || E'    else\n'
      || E'      duet_layout_value := duet_presenter_identity_value -> ''layout'';\n'
      || E'    end if;\n'
      || E'  elsif p_payload ? ''duet_presenter_id'' or p_payload ? ''duet_layout'' then'
  );

  -- 3. Хэш запроса. Раскладка — часть запроса: два прогона, различающиеся
  --    только углом врезки, обязаны отличаться уже здесь.
  anchor := E'    then jsonb_build_object(''duet_presenter_id'', duet_presenter_id_value)\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'duet_layout_anchor_request_hash';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    then jsonb_build_object(\n'
      || E'      ''duet_presenter_id'', duet_presenter_id_value,\n'
      || E'      ''duet_layout'', duet_layout_value\n'
      || E'    )\n'
  );

  if patched_text = source_text then
    raise exception using message = 'duet_layout_bind_unchanged';
  end if;
  execute patched_text;
end;
$duet_layout_from_operator$;

-- 4. Верхняя привязка пропускает ключ вниз.
do $resolve_bind_layout$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if position('duet_layout' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  anchor := E'       ''idempotency_key'', ''engine'', ''duet_presenter_id''\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'resolve_layout_anchor_payload_keys';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'       ''idempotency_key'', ''engine'', ''duet_presenter_id'', ''duet_layout''\n'
  );

  anchor := E'    ) || case when p_payload ? ''duet_presenter_id''\n'
         || E'      then jsonb_build_object(\n'
         || E'        ''duet_presenter_id'', p_payload -> ''duet_presenter_id''\n'
         || E'      )\n'
         || E'      else ''{}''::jsonb\n'
         || E'    end\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'resolve_layout_anchor_delegation';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    ) || case when p_payload ? ''duet_presenter_id''\n'
      || E'      then jsonb_build_object(\n'
      || E'        ''duet_presenter_id'', p_payload -> ''duet_presenter_id''\n'
      || E'      )\n'
      || E'      else ''{}''::jsonb\n'
      || E'    end || case when p_payload ? ''duet_layout''\n'
      || E'      then jsonb_build_object(''duet_layout'', p_payload -> ''duet_layout'')\n'
      || E'      else ''{}''::jsonb\n'
      || E'    end\n'
  );

  if patched_text = source_text then
    raise exception using message = 'resolve_layout_unchanged';
  end if;
  execute patched_text;
end;
$resolve_bind_layout$;

-- ПРОВЕРКА.
do $duet_layout_verify$
declare
  bind_body text;
  resolve_body text;
begin
  bind_body := pg_get_functiondef(
    'public.system_bind_generation_spec_strategy(jsonb)'::regprocedure
  );
  resolve_body := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );

  -- 1. Ключ принимается обеими привязками.
  if position('''duet_layout''' in bind_body) = 0
     or position('''duet_layout''' in resolve_body) = 0 then
    raise exception using message = 'duet_layout_key_not_accepted';
  end if;

  -- 2. Отказ назван, а не спрятан за «снимок неверен».
  if position('generation_strategy_binding_duet_layout_invalid' in bind_body) = 0
  then
    raise exception using message = 'duet_layout_refusal_unnamed';
  end if;

  -- 3. САМОЕ ВАЖНОЕ: умолчание сохранено. Нет ключа — раскладка берётся из
  --    карточки ведущего, и снимок выходит прежним. Если эта строка исчезнет,
  --    существующие привязки разъедутся молча.
  if position(
       'duet_layout_value := duet_presenter_identity_value -> ''layout''' in bind_body
     ) = 0 then
    raise exception using message = 'duet_layout_default_lost';
  end if;

  -- 4. Остальным стратегиям раскладка запрещена — как и ведущий.
  if position(
       'p_payload ? ''duet_presenter_id'' or p_payload ? ''duet_layout''' in bind_body
     ) = 0 then
    raise exception using message = 'duet_layout_not_forbidden_for_others';
  end if;

  -- 5. Раскладка входит в хэш запроса: два прогона, различающиеся только углом
  --    врезки, обязаны быть разными запросами.
  if position(
       '''duet_layout'', duet_layout_value' in bind_body
     ) = 0 then
    raise exception using message = 'duet_layout_outside_request_hash';
  end if;

  -- 6. Проверяющий снимка по-прежнему держит форму раскладки: именованный
  --    отказ выше — удобство, а не замена контролю.
  if content_factory_private.generation_spec_strategy_snapshot_valid(
       jsonb_build_object(
         'version', 'generation-spec-strategy-snapshot-v1',
         'strategy_id', 'viral_avatar_ugc',
         'selection_hash', repeat('a', 64),
         'source_basis', 'exact_source_video',
         'spec', jsonb_build_object(
           'spec_id', '11111111-1111-4111-8111-111111111111',
           'spec_version', 1,
           'spec_hash', repeat('b', 64),
           'prompt_hash', repeat('c', 64)
         ),
         'product_id', '22222222-2222-4222-8222-222222222222',
         'source', jsonb_build_object(
           'basis', 'exact_source_video',
           'binding_id', '44444444-4444-4444-8444-444444444444',
           'binding_hash', repeat('d', 64),
           'source_id', '55555555-5555-4555-8555-555555555555',
           'source_hash', repeat('e', 64),
           'media_object_id', '66666666-6666-4666-8666-666666666666',
           'media_sha256', repeat('f', 64)
         ),
         'role_assets', jsonb_build_array(jsonb_build_object(
           'role', 'source_video', 'ordinal', 1,
           'media_object_id', '66666666-6666-4666-8666-666666666666',
           'sha256', repeat('f', 64), 'kind', 'source_video',
           'mime_type', 'video/mp4', 'product_id', null,
           'rights_confirmed', true, 'likeness_consent', false
         )),
         'attestations', jsonb_build_object(
           'version', 'generation-strategy-attestation-v1',
           'source_media_rights_confirmed', true,
           'transformative_use_confirmed', true,
           'product_assets_rights_confirmed', true,
           'depicted_people_consent_confirmed', true,
           'avatar_likeness_consent_confirmed', true
         ),
         'duet_presenter_id', '33333333-3333-4333-8333-333333333333',
         'duet_layout', jsonb_build_object(
           'corner', 'top_right', 'shape', 'window', 'widthPercent', 50
         )
       )
     ) is not true then
    raise exception using message = 'operator_layout_rejected_by_snapshot';
  end if;
end;
$duet_layout_verify$;

commit;

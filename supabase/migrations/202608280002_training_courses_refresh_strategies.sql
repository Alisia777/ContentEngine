begin;

-- Актуализация старых курсов академии (28.08.2026): уроки описывали
-- июльскую тройку режимов «фото 2K / 5 секунд / UGC 8 секунд» с ценами
-- Runway-эпохи. Сегодня запуск устроен иначе: стратегии «Копия» /
-- «Создание» / «Дуэт», модель выбирается ползунком «Быстрее ↔
-- Качественнее» (цена видна до подтверждения), длительность 3–15 секунд.
-- Правки хирургические: только устаревшие body/takeaway/панель/чеклист,
-- остальной контент курсов не тронут. Fail-closed: без старого текста
-- миграция падает, а не молча переписывает не то.

do $refresh$
declare
  fb_body text;
  vq_body text;
begin
  select l.value ->> 'body' into fb_body
  from content_factory.training_modules m,
  lateral jsonb_array_elements(m.content -> 'lessons') as l(value)
  where m.code = 'factory_basics' and l.value ->> 'id' = 'generation_modes';
  if fb_body is null then
    raise exception 'factory_basics_generation_modes_missing';
  end if;
  if fb_body not like '%2K%' then
    raise notice 'factory_basics already refreshed';
  else
    update content_factory.training_modules m
    set content = jsonb_set(m.content, '{lessons}', (
      select jsonb_agg(
        case when l.value ->> 'id' = 'generation_modes'
          then jsonb_set(jsonb_set(l.value,
            '{body}',
            to_jsonb('В «Создать» три стратегии. «Копия» повторяет готовый ролик, заменяя в его кадрах товар на ваш; «Создание» собирает ролик по ТЗ с нуля; «Дуэт» добавляет ведущего, который комментирует исходник из угла кадра. Модель генерации выбирается ползунком «Быстрее и дешевле ↔ Качественнее и дороже», длительность — от 3 до 15 секунд, и точная цена запуска видна до подтверждения. После выбора проверенного исходника портал сам фиксирует артикул и название, затем собирает безопасное ТЗ для выбранной стратегии. Человеку остаётся проверить площадку, аккаунт или карточку публикации, прочитать итоговую цену и отдельно подтвердить один запуск. Статус «Готово» означает наличие файла, но не его одобрение.'::text)),
            '{takeaway}',
            to_jsonb('Выберите точный исходник и стратегию, задайте ползунком качество, проверьте готовое авто-ТЗ и цену; подтверждение расхода разрешает один файл, а публикацию — только последующий QA.'::text))
          else l.value end
        order by l.ordinality)
      from jsonb_array_elements(m.content -> 'lessons')
        with ordinality as l(value, ordinality)
    ), false)
    where m.code = 'factory_basics';
  end if;

  select l.value ->> 'body' into vq_body
  from content_factory.training_modules m,
  lateral jsonb_array_elements(m.content -> 'lessons') as l(value)
  where m.code = 'video_quality' and l.value ->> 'id' = 'generation_form';
  if vq_body is null then
    raise exception 'video_quality_generation_form_missing';
  end if;
  if vq_body not like '%2K%' then
    raise notice 'video_quality already refreshed';
    return;
  end if;

  update content_factory.training_modules m
  set content = jsonb_set(jsonb_set(m.content, '{lessons}', (
    select jsonb_agg(
      case when l.value ->> 'id' = 'generation_form'
        then jsonb_set(jsonb_set(jsonb_set(l.value,
          '{body}',
          to_jsonb('Сначала выберите стратегию — «Копия», «Создание» или «Дуэт» — и проверенные исходники: точное фото товара, а для «Копии» ещё и видео-исходник (его пригодность проверьте заранее — этому учит курс «Видео для ИИ: простое и плохое»). Модель задаётся ползунком «Быстрее и дешевле ↔ Качественнее и дороже», длительность — от 3 до 15 секунд; цена видна до запуска. Портал зафиксирует артикул и название и сам соберёт безопасное ТЗ. ТЗ можно уточнить, но удаление точного товара, защиты упаковки или запрета на новые claims остановит платный запуск. Затем укажите площадку и точный аккаунт или карточку, проверьте кампанию и цену и подтвердите ровно один расход.'::text)),
          '{takeaway}',
          to_jsonb('Минимальный ручной маршрут: стратегия → проверенные исходники → ползунок качества → площадка → адрес публикации → проверка авто-ТЗ и цены → одно подтверждение.'::text)),
          '{visual,panels}',
          (
            select jsonb_agg(
              case when panel.value ->> 'area' = 'Режим'
                then jsonb_build_object(
                  'area', 'Стратегия',
                  'label', '«Копия», «Создание» или «Дуэт»',
                  'detail', 'Определяет форму запуска; модель и цену задаёт ползунок «Быстрее ↔ Качественнее»'
                )
                else panel.value end
              order by panel.ordinality)
            from jsonb_array_elements(l.value -> 'visual' -> 'panels')
              with ordinality as panel(value, ordinality)
          ))
        else l.value end
      order by l.ordinality)
    from jsonb_array_elements(m.content -> 'lessons')
      with ordinality as l(value, ordinality)
  ), false),
  '{completion_checklist}', (
    select jsonb_agg(
      case when item.value like '%2K%'
        then to_jsonb('Понимаю различия стратегий «Копия», «Создание» и «Дуэт» и вижу на ползунке модель и цену до запуска'::text)
        else to_jsonb(item.value) end
      order by item.ordinality)
    from jsonb_array_elements_text(m.content -> 'completion_checklist')
      with ordinality as item(value, ordinality)
  ), false)
  where m.code = 'video_quality';

  update content_factory.training_modules
  set content = jsonb_set(content, '{version}',
    to_jsonb(coalesce((content ->> 'version')::int, 1) + 1), true),
    updated_at = now()
  where code in ('factory_basics', 'video_quality');
end;
$refresh$;

commit;

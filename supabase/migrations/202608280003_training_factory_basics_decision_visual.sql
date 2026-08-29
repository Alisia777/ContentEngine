begin;

-- Хвост актуализации factory_basics (28.08.2026): visual-«решалка» урока
-- generation_modes всё ещё предлагала июльские режимы прямым текстом
-- («Фото 2K ≈ $0.04», «Gen-4 · 5 секунд ≈ $0.25», «Seedance · 8 секунд
-- ≈ $2.32»). Ветки success переписаны на стратегии «Копия»/«Создание»/
-- «Дуэт» и фото; danger-ветка (не запускать платное) сохраняется как есть.

do $fix$
declare
  branches jsonb;
begin
  select l.value -> 'visual' -> 'branches' into branches
  from content_factory.training_modules m,
  lateral jsonb_array_elements(m.content -> 'lessons') as l(value)
  where m.code = 'factory_basics' and l.value ->> 'id' = 'generation_modes';
  if branches is null then
    raise exception 'factory_basics_decision_visual_missing';
  end if;
  if branches::text not ilike '%2K%' then
    raise notice 'decision visual already refreshed';
    return;
  end if;

  update content_factory.training_modules m
  set content = jsonb_set(m.content, '{lessons}', (
    select jsonb_agg(
      case when l.value ->> 'id' = 'generation_modes'
        then jsonb_set(l.value, '{visual,branches}', (
          select jsonb_build_array(
            jsonb_build_object(
              'tone', 'success',
              'condition', 'Нужна карточка или packshot',
              'action', 'Фото товара · один файл · авто-ТЗ фиксирует точный товар, упаковку и запрет на выдуманные детали · цена видна до запуска'
            ),
            jsonb_build_object(
              'tone', 'success',
              'condition', 'Есть готовый ролик-образец',
              'action', '«Копия» · товар в кадрах исходника меняется на ваш · длительность от исходника · модель и цену задаёт ползунок'
            ),
            jsonb_build_object(
              'tone', 'success',
              'condition', 'Ролик нужен с нуля по ТЗ',
              'action', '«Создание» · сценарий и движки 3–15 секунд · модель и цену задаёт ползунок «Быстрее ↔ Качественнее»'
            ),
            jsonb_build_object(
              'tone', 'success',
              'condition', 'Нужен ведущий с комментарием',
              'action', '«Дуэт» · ведущий проекта комментирует исходник из угла кадра · исходник остаётся нетронутым'
            )
          ) || coalesce((
            select jsonb_agg(branch.value order by branch.ordinality)
            from jsonb_array_elements(l.value -> 'visual' -> 'branches')
              with ordinality as branch(value, ordinality)
            where branch.value ->> 'tone' <> 'success'
          ), '[]'::jsonb)
        ))
        else l.value end
      order by l.ordinality)
    from jsonb_array_elements(m.content -> 'lessons')
      with ordinality as l(value, ordinality)
  ), false),
  updated_at = now()
  where m.code = 'factory_basics';
end;
$fix$;

commit;

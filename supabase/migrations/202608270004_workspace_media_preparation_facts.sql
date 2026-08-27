-- Карточка «Материалов» показывает факты подготовки (контур №1, ТЗ 3.8):
-- media-ветка creator_workspace_section отдаёт выборочный срез metadata —
-- роль, происхождение и prep_-факты анализа. НЕ вся метадата: в ней живут
-- служебные ключи, которым в списке делать нечего.
--
-- Приём — патч существующей функции do-блоком (прецедент 202608170001):
-- pg_get_functiondef → fail-closed якорь → replace → execute. Функция
-- определена в более ранней миграции, которую редактировать нельзя.

do $patch$
declare
  def text;
  anchor constant text := $a$'sha256', media.sha256,$a$;
  addition constant text := $a$'sha256', media.sha256,
    'metadata', jsonb_strip_nulls(jsonb_build_object(
      'role', media.metadata -> 'role',
      'origin_url', media.metadata -> 'origin_url',
      'prep_analyzed_at', media.metadata -> 'prep_analyzed_at',
      'prep_duration_seconds', media.metadata -> 'prep_duration_seconds',
      'prep_width', media.metadata -> 'prep_width',
      'prep_height', media.metadata -> 'prep_height',
      'prep_fps', media.metadata -> 'prep_fps',
      'prep_audio', media.metadata -> 'prep_audio',
      'prep_screen_recording_likely',
        media.metadata -> 'prep_screen_recording_likely',
      'prep_static_intro_seconds',
        media.metadata -> 'prep_static_intro_seconds',
      'prep_static_outro_seconds',
        media.metadata -> 'prep_static_outro_seconds'
    )),$a$;
begin
  select pg_get_functiondef(p.oid) into def
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'creator_workspace_section';
  if def is null then
    raise exception 'workspace_section_function_missing';
  end if;
  if strpos(def, $a$'prep_analyzed_at', media.metadata$a$) > 0 then
    raise notice 'workspace_section_already_patched';
    return;
  end if;
  -- Якорь ровно один (проверено в проде перед написанием патча); если
  -- будущая правка функции его сдвинет — миграция обязана упасть, а не
  -- молча выложить функцию без среза.
  if strpos(def, anchor) = 0 then
    raise exception 'workspace_section_anchor_missing';
  end if;
  if (length(def) - length(replace(def, anchor, ''))) / length(anchor) <> 1 then
    raise exception 'workspace_section_anchor_ambiguous';
  end if;
  def := replace(def, anchor, addition);
  execute def;
end;
$patch$;

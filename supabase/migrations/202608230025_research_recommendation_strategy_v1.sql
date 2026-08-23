begin;
-- 202608230025_research_recommendation_strategy_v1
--
-- Рекомендация ИИ-центра учится называть СПОСОБ: viral_product_swap («Копия»),
-- viral_avatar_ugc («Дуэт»), viral_rebuild («Создание»). До этого словарь
-- исследования знал только режимы моделей (real_photo / real_gen4 /
-- real_seedance), и ИИ структурно не мог сказать «сними это Дуэтом» — совет
-- по движку работал уже внутри выбранного способа, а совета по самому способу
-- не было.
--
-- Сценарий исследования (creator-product-research) с этой версии несёт
-- recommended_strategy + strategy_reason. Здесь эти поля доезжают до хранимого
-- элемента рекомендации в ai_research_learning_selections.recommendations —
-- его целиком отдаёт contentengine_generation_research_recommendations, так
-- что экран создания увидит их без отдельной правки выдачи.
--
-- Старые сценарии без поля дают null: экран в этом случае совета о способе не
-- показывает и не выдумывает его.
do $recommendation_strategy$
declare
  definition_value text;
  patched_value text;
  anchor constant text :=
    '        ''generation_mode_reason'', coalesce(' || chr(10) ||
    '          nullif(btrim(scenario_value ->> ''generation_mode_reason''), ''''), ''''' || chr(10) ||
    '        ),' || chr(10);
  replacement constant text :=
    '        ''generation_mode_reason'', coalesce(' || chr(10) ||
    '          nullif(btrim(scenario_value ->> ''generation_mode_reason''), ''''), ''''' || chr(10) ||
    '        ),' || chr(10) ||
    '        ''recommended_strategy'', case' || chr(10) ||
    '          when nullif(btrim(scenario_value ->> ''recommended_strategy''), '''')' || chr(10) ||
    '            in (''viral_product_swap'', ''viral_avatar_ugc'', ''viral_rebuild'')' || chr(10) ||
    '          then btrim(scenario_value ->> ''recommended_strategy'')' || chr(10) ||
    '          else null end,' || chr(10) ||
    '        ''strategy_reason'', coalesce(' || chr(10) ||
    '          nullif(btrim(scenario_value ->> ''strategy_reason''), ''''), ''''' || chr(10) ||
    '        ),' || chr(10);
  hits integer;
begin
  definition_value := pg_get_functiondef(
    'content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(jsonb)'
      ::regprocedure
  );
  if position('''recommended_strategy'', case' in definition_value) > 0 then
    return;  -- уже применено
  end if;
  hits := (
    length(definition_value) - length(replace(definition_value, anchor, ''))
  ) / length(anchor);
  if hits <> 1 then
    raise exception using message =
      'recommendation_strategy_anchor_invalid:' || hits::text;
  end if;
  patched_value := replace(definition_value, anchor, replacement);
  execute patched_value;
end;
$recommendation_strategy$;

do $recommendation_strategy_verify$
begin
  if position('''recommended_strategy'', case' in pg_get_functiondef(
       'content_factory_private.contentengine_decide_ai_research_training_unscoped_v1(jsonb)'
         ::regprocedure
     )) = 0 then
    raise exception using message = 'recommendation_strategy_not_applied';
  end if;
end;
$recommendation_strategy_verify$;

commit;

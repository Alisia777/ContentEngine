from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
MODULE_PATH = APP / "workspace-ai-research-training.js"
STYLE_PATH = APP / "workspace-ai-research-training.css"
MODULE = MODULE_PATH.read_text(encoding="utf-8")
STYLE = STYLE_PATH.read_text(encoding="utf-8")


def run_module_script(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = f"""
      const {{ readFileSync }} = await import('node:fs');
      const source = readFileSync(process.argv[1], 'utf8');
      const encoded = Buffer.from(source).toString('base64');
      const mod = await import(`data:text/javascript;base64,${{encoded}}`);
      {body}
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, str(MODULE_PATH)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_category_resolution_prefers_route_then_visible_legacy_over_storage() -> None:
    value = run_module_script(
        """
        const routeWins = mod.resolveTrainingCategory({
          routeValue: 'cosmetics',
          legacyValue: 'food',
          selectValue: 'household',
          storedValue: 'other',
        });
        const legacyWins = mod.resolveTrainingCategory({
          legacyValue: 'cosmetics',
          selectValue: 'household',
          storedValue: 'other',
        });
        const selectWins = mod.resolveTrainingCategory({
          selectValue: 'electronics',
          storedValue: 'other',
        });
        const storedFallback = mod.resolveTrainingCategory({
          storedValue: 'apparel',
        });
        const safeFallback = mod.resolveTrainingCategory({
          routeValue: 'unknown',
          storedValue: 'stale-value',
        });
        console.log(JSON.stringify({
          routeWins, legacyWins, selectWins, storedFallback, safeFallback,
        }));
        """
    )

    assert value == {
        "routeWins": "cosmetics",
        "legacyWins": "cosmetics",
        "selectWins": "electronics",
        "storedFallback": "apparel",
        "safeFallback": "other",
    }


def test_training_category_hash_preserves_project_and_other_ai_query_state() -> None:
    value = run_module_script(
        """
        const hash = mod.trainingCategoryHash(
          'food',
          '#/workspace/ai?project_id=11111111-1111-4111-8111-111111111111&view=history&scope=market-a&category=other'
        );
        const query = new URLSearchParams(hash.slice(hash.indexOf('?') + 1));
        console.log(JSON.stringify({
          hash,
          category: query.get('category'),
          projectId: query.get('project_id'),
          view: query.get('view'),
          scope: query.get('scope'),
        }));
        """
    )

    assert value["hash"].startswith("#/workspace/ai?")
    assert value["category"] == "food"
    assert value["projectId"] == "11111111-1111-4111-8111-111111111111"
    assert value["view"] == "history"
    assert value["scope"] == "market-a"


def test_legacy_category_click_and_training_selector_share_one_route_contract() -> None:
    for marker in (
        '.ai-learning-category[aria-pressed="true"][data-category-key]',
        ".ai-learning-category[data-category-key]",
        "selectedLegacyCategory",
        "syncLegacyCategoryButtons",
        "syncTrainingCategorySelect",
        "updateCategoryRoute(category)",
        "restoreProjectScopeAfterLegacyNavigation",
        'routeParams().get("project_id")',
        'document.addEventListener("click", handleLegacyCategoryClick, true)',
        'window.addEventListener("hashchange", scheduleMount)',
    ):
        assert marker in MODULE

    storage_index = MODULE.index("storedValue = window.sessionStorage.getItem")
    resolver_index = MODULE.index("return resolveTrainingCategory")
    assert storage_index < resolver_index
    assert "legacyValue: visibleLegacyCategory" in MODULE[resolver_index:]


def test_rich_learned_history_normalizes_material_results_and_recommendations() -> None:
    value = run_module_script(
        """
        const learned = mod.normalizeLearnedResearch({
          selection_id: '22222222-2222-4222-8222-222222222222',
          product_name: 'Крем SPF 50',
          product_sku: 'SPF-50',
          product_category: 'cosmetics',
          decision: 'approve',
          selected_at: '2026-08-10T10:00:00Z',
          selected_insight_keys: ['category', 'trends', 'brief'],
          selected_scenario_positions: [1, 3],
          source_snapshot: [{
            source_id: 'source-1',
            source_type: 'product_photo',
            title: 'Фотография упаковки',
            analysis: { summary: 'Упаковка и маркировка читаемы.' },
          }],
          material_snapshot: [{
            source_id: 'source-1',
            source_type: 'product_photo',
            media: {
              media_object_id: '33333333-3333-4333-8333-333333333333',
              project_id: '11111111-1111-4111-8111-111111111111',
              filename: 'spf-50-packshot.jpg',
              mime_type: 'image/jpeg',
              status: 'ready',
            },
          }],
          analysis_snapshot: {
            category_analysis: {
              summary: 'Покупателю важна ежедневная защита.',
              buyer_jobs: ['защитить кожу'],
            },
            trend_analysis: {
              summary: 'Растёт формат короткой демонстрации.',
              signals: ['нанесение в один кадр'],
            },
            guidance: { reason: 'Показать текстуру без медицинских обещаний.' },
            creative_brief: { audience: ['городские покупатели'] },
          },
          research_summary: {
            executive_summary: 'Товар лучше раскрывается через демонстрацию текстуры.',
            conclusions: ['Показать нанесение', 'Сохранить упаковку в кадре'],
            limitations: ['Не обещать лечение'],
          },
          forecast: {
            score: 82,
            confidence: 0.74,
            summary: 'Умеренно сильная гипотеза.',
            factors: { strengths: ['точный товар'], risks: ['мелкий текст'] },
          },
          recommendations: [{
            position: 1,
            title: 'Текстура первым кадром',
            platform: 'youtube',
            recommended_generation_mode: 'real_seedance',
            hook: 'Показываем текстуру сразу',
            spoken_script: 'Лёгкая текстура на каждый день.',
            shot_list: ['упаковка', 'нанесение'],
            proof_points: ['видимая текстура'],
            avoid_claims: ['лечебный эффект'],
          }],
          operator_notes: 'Проверено редактором.',
          deep_link: '#/workspace/research?project_id=11111111-1111-4111-8111-111111111111&run=44444444-4444-4444-8444-444444444444',
        });
        const unsafe = mod.normalizeLearnedResearch({
          deep_link: 'javascript:alert(1)',
          source_snapshot: null,
          analysis_snapshot: null,
          recommendations: null,
        });
        console.log(JSON.stringify({ learned, unsafe }));
        """
    )

    learned = value["learned"]
    assert learned["title"] == "Крем SPF 50"
    assert learned["category"] == "cosmetics"
    assert learned["selectedInsights"] == ["category", "trends", "brief"]
    assert learned["selectedScenarioPositions"] == [1, 3]
    assert learned["sources"][0]["media_object_id"].startswith("33333333")
    assert learned["sources"][0]["project_id"].startswith("11111111")
    assert learned["sources"][0]["mime_type"] == "image/jpeg"
    assert learned["sources"][0]["analysis"]["summary"].startswith("Упаковка")
    assert learned["analysis"]["category_analysis"]["summary"].startswith("Покупателю")
    assert learned["summary"]["headline"].startswith("Товар лучше")
    assert learned["summary"]["conclusions"] == [
        "Показать нанесение",
        "Сохранить упаковку в кадре",
    ]
    assert learned["forecast"]["score"] == 82
    assert learned["forecast"]["confidence"] == 0.74
    assert learned["recommendations"][0]["generationMode"] == "real_seedance"
    assert learned["recommendations"][0]["shotList"] == "упаковка\nнанесение"
    assert learned["deepLink"].startswith("#/workspace/research?")

    assert value["unsafe"]["deepLink"] == ""
    assert value["unsafe"]["sources"] == []
    assert value["unsafe"]["recommendations"] == []


def test_learned_card_is_expandable_and_labels_every_required_server_block() -> None:
    for marker in (
        'el("details", "ai-research-training__learned-card")',
        "source_snapshot",
        "material_snapshot",
        "analysis_snapshot",
        "research_summary",
        "research_forecast",
        "Материал и источники",
        "Итоги исследования",
        "Выводы ИИ",
        "Что выбрано для обучения",
        "Сохранённые редактируемые рекомендации",
        "Открыть исходное исследование",
        "Снимок материалов отсутствует в ответе сервера",
    ):
        assert marker in MODULE

    for selector in (
        ".ai-research-training__learned-summary",
        ".ai-research-training__learned-body",
        ".ai-research-training__snapshot-grid",
        ".ai-research-training__learned-recommendations",
        ".ai-research-training__learned-chips",
    ):
        assert selector in STYLE


def test_empty_and_loading_states_name_the_exact_selected_category() -> None:
    for marker in (
        "selectedCategoryLabel",
        "categoryLabel(selectedCategory)",
        "В категории «${selectedCategoryLabel}» нет исследований для отбора",
        "Категория «${selectedCategoryLabel}»: очередь пуста",
        "Загружаем разборы категории «${categoryLabel(selectedCategory)}»",
    ):
        assert marker in MODULE


def test_ai_research_training_module_remains_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    subprocess.run([node, "--check", str(MODULE_PATH)], check=True)

from pathlib import Path
import base64
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
MIGRATION = "\n".join(
    (
        ROOT / "supabase" / "migrations" / migration_name
    ).read_text(encoding="utf-8")
    for migration_name in (
        "202608050004_research_trained_recommendations.sql",
        "202608050005_research_trained_recommendation_rpc_names.sql",
    )
)
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
BOOTSTRAP = (
    APP / "workspace-research-training-bootstrap.js"
).read_text(encoding="utf-8")
INDEX = (APP / "index.html").read_text(encoding="utf-8")
RESEARCH = (APP / "workspace-research-video-intake.js").read_text(encoding="utf-8")
AI_CENTER = (APP / "workspace-ai-research-training.js").read_text(encoding="utf-8")
GENERATION = (
    APP / "workspace-generation-research-recommendations.js"
).read_text(encoding="utf-8")


def test_governed_research_selection_creates_editable_recommendations() -> None:
    for marker in (
        "content_factory.ai_research_learning_selections",
        "creator_ai_research_training_queue",
        "creator_decide_ai_research_training",
        "creator_generation_research_recommendations",
        "contentengine_ai_research_training_queue",
        "contentengine_decide_ai_research_training",
        "contentengine_generation_research_recommendations",
        "selected_insight_keys",
        "selected_scenario_positions",
        "recommendations_are_editable",
        "human_edits_are_preserved",
        "unreviewed_research_affects_generation",
        "raw_research_enters_prompt_automatically",
        "research_source_analysis_events",
        "ai_research_learning_selection_append_only",
    ):
        assert marker in MIGRATION

    assert "unreviewed_research_affects_generation', false" in MIGRATION
    assert "raw_research_enters_prompt_automatically', false" in MIGRATION
    assert "external_call_started', false" in MIGRATION
    assert "paid_call_started', false" in MIGRATION
    assert (
        "revoke all on function public.creator_ai_research_training_queue(jsonb)"
        in MIGRATION
    )
    assert (
        "rename to contentengine_decide_ai_research_training" in MIGRATION
    )
    assert (
        "rename to contentengine_generation_research_recommendations"
        in MIGRATION
    )
    for forbidden in (
        "net.http_post",
        "http_post(",
        "extensions.http",
        "openai.com",
        "youtube.com/oembed",
    ):
        assert forbidden not in MIGRATION


def test_exact_youtube_short_is_canonicalized_and_merged_into_research() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    encoded = base64.b64encode(RESEARCH.encode("utf-8")).decode("ascii")
    script = f"""
      const mod = await import('data:text/javascript;base64,{encoded}');
      const input = 'https://www.youtube.com/shorts/CXssfXBVInw';
      const canonical = mod.canonicalResearchVideoUrl(input);
      const merged = mod.mergeResearchVideoReference(
        'https://example.com/reference', input
      );
      console.log(JSON.stringify({{ canonical, merged }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    assert value["canonical"] == "https://youtube.com/watch?v=CXssfXBVInw"
    assert value["merged"].splitlines()[0] == value["canonical"]
    assert "competitor_references" in RESEARCH
    assert "Обучение начинается только после выбора в ИИ-центре" in RESEARCH


def test_ai_center_exposes_breakdown_selection_and_editable_scenarios() -> None:
    for marker in (
        "Источники и разбор ролика",
        "Что именно взять в обучение",
        "Рекомендации, которые получит генерация",
        "data-insight-key",
        "data-scenario-position",
        "selected_insight_keys",
        "selected_scenario_positions",
        "scenarioEdits",
        "Обучить на выбранном и сохранить рекомендации",
    ):
        assert marker in AI_CENTER
    assert "creator_ai_research_training_queue" in AI_CENTER
    assert "creator_decide_ai_research_training" in AI_CENTER
    assert ".ai-learning-research-inbox" in AI_CENTER
    assert "replacedByResearchTraining" in AI_CENTER


def test_generation_is_ai_first_but_never_overwrites_human_edits() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    encoded = base64.b64encode(GENERATION.encode("utf-8")).decode("ascii")
    script = f"""
      const mod = await import('data:text/javascript;base64,{encoded}');
      const envelope = {{
        source_product_name: 'Аэрогриль',
        recommendation: {{
          title: 'Хрустящий результат первым кадром',
          hook: 'Такую корочку обычно ждёшь только от фритюра',
          key_message: 'Показать результат, затем простой путь к нему',
          spoken_script: 'Сначала показываем готовое блюдо, затем процесс.',
          shot_list: [
            {{ seconds: '0-2', visual: 'готовое блюдо крупно' }},
            {{ seconds: '2-5', visual: 'закладка продукта' }}
          ],
          visual_direction: 'макро фактуры и быстрый бытовой монтаж',
          cta: 'Сохраните рецепт',
          proof_points: ['видимый результат'],
          avoid_claims: ['не обещать медицинскую пользу']
        }}
      }};
      const text = mod.formatResearchRecommendation(envelope, {{
        productName: 'Аэрогриль MБT'
      }});
      const auto = mod.shouldAutoApplyResearchRecommendation({{
        brief: '', touched: false, canAutoApply: true, recommendation: envelope
      }});
      const protectedEdit = mod.shouldAutoApplyResearchRecommendation({{
        brief: 'Моя правка', touched: true, canAutoApply: true,
        recommendation: envelope
      }});
      console.log(JSON.stringify({{ text, auto, protectedEdit }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    assert value["auto"] is True
    assert value["protectedEdit"] is False
    for section in (
        "ТОВАР:",
        "КОНЦЕПЦИЯ:",
        "ХУК:",
        "КЛЮЧЕВОЕ СООБЩЕНИЕ:",
        "КАДРЫ:",
        "CTA:",
        "НЕ ОБЕЩАТЬ / УЧЕСТЬ:",
    ):
        assert section in value["text"]

    for marker in (
        "creator_generation_research_recommendations",
        "shouldAutoApplyResearchRecommendation",
        "markHumanEdit",
        "lastAppliedText",
        "ИИ больше не перезапишет",
        "изменить любую строку",
    ):
        assert marker in GENERATION


def test_lazy_bootstrap_wires_flow_without_expanding_audited_loader() -> None:
    for marker in (
        'route === "/workspace/research"',
        'route === "/workspace/ai"',
        'route === "/workspace/generation"',
        "workspace-research-video-intake.css",
        "workspace-research-video-intake.js",
        "workspace-ai-research-training.css",
        "workspace-ai-research-training.js",
        "workspace-generation-research-recommendations.css",
        "workspace-generation-research-recommendations.js",
        "contentengine:v4-route-ready",
        "RPC_ALIASES",
        "contentengine_ai_research_training_queue",
        "contentengine_decide_ai_research_training",
        "contentengine_generation_research_recommendations",
        "No provider request",
    ):
        assert marker in BOOTSTRAP
    assert "workspace-os-v4-generation-guided.js" in LOADER
    assert "workspace-generation-research-recommendations.js" not in LOADER
    assert "workspace-research-training-bootstrap.js" in INDEX


def test_new_route_modules_are_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    for path in (
        APP / "workspace-research-training-bootstrap.js",
        APP / "workspace-research-video-intake.js",
        APP / "workspace-ai-research-training.js",
        APP / "workspace-generation-research-recommendations.js",
        APP / "workspace-os-v4-loader.js",
    ):
        subprocess.run([node, "--check", str(path)], check=True)

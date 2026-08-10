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
    assert "contentengine_ai_research_training_queue" in AI_CENTER
    assert "contentengine_decide_ai_research_training" in AI_CENTER
    assert ".ai-learning-research-inbox" in AI_CENTER
    assert "replacedByResearchTraining" in AI_CENTER


def test_generation_marks_ai_ready_state_as_advisory_and_editable() -> None:
    assert "Готово ИИ · можно изменить" in GENERATION
    assert "Все поля можно изменить" in GENERATION
    assert "Рекомендация · не обязательна" in GENERATION


def test_generation_is_ai_first_but_never_overwrites_human_edits() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    generation_url = (APP / "workspace-generation-research-recommendations.js").as_uri()
    script = f"""
      const mod = await import({json.dumps(generation_url)});
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
        "contentengine_generation_research_recommendations",
        "shouldAutoApplyResearchRecommendation",
        "markHumanEdit",
        "lastAppliedText",
        "ИИ больше не перезапишет",
        "изменить любую строку",
    ):
        assert marker in GENERATION


def test_generation_recommendation_applies_safe_editable_preset_fields() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    generation_url = (APP / "workspace-generation-research-recommendations.js").as_uri()
    script = f"""
      const mod = await import({json.dumps(generation_url)});

      class Control extends EventTarget {{
        constructor(name, value, values = []) {{
          super();
          this.name = name;
          this.value = value;
          this.defaultValue = value;
          this.dataset = {{}};
          this.options = values.map((candidate, index) => ({{
            value: candidate,
            defaultSelected: index === 0,
          }}));
        }}
      }}
      class Form extends EventTarget {{
        constructor(elements) {{
          super();
          this.elements = elements;
          this.dataset = {{}};
        }}
      }}

      const elements = {{
        product_category: new Control('product_category', 'food', [
          'food', 'household', 'other'
        ]),
        platform: new Control('platform', 'instagram', [
          'instagram', 'youtube', 'vk'
        ]),
        generation_mode: new Control('generation_mode', 'mock', [
          'mock', 'real_photo', 'real_gen4', 'real_seedance'
        ]),
        duration_seconds: new Control('duration_seconds', '5', [
          '4', '5', '8', '12', '15'
        ]),
        format: new Control('format', '16:9', ['9:16', '1:1', '16:9']),
        brief: new Control('brief', 'Моя ручная правка'),
        campaign_id: new Control('campaign_id', 'campaign-unchanged'),
        destination_ref: new Control('destination_ref', '@unchanged'),
        count: new Control('count', '3'),
        media_id: new Control('media_id', 'media-unchanged'),
        real_spend_confirmation: new Control(
          'real_spend_confirmation', 'CONFIRM_REAL_SEEDANCE'
        ),
      }};
      elements.real_spend_confirmation.checked = true;
      const form = new Form(elements);
      let provenance = null;
      form.addEventListener(
        'contentengine:generation-research-preset-applied',
        (event) => {{ provenance = event.detail; }},
      );
      const envelope = {{
        selection_id: '11111111-1111-4111-8111-111111111111',
        scope_match: 'exact_sku',
        preset: {{
          product_category: 'food',
          platform: 'youtube',
          generation_mode: 'seedance2_fast',
          duration_seconds: 12,
          brief: 'Готовый замысел ИИ',
          campaign_id: 'must-not-apply',
          destination_ref: 'must-not-apply',
          count: 50,
          spend_confirmation: 'must-not-apply',
        }},
        recommendation: {{ position: 2, title: 'YouTube-рекомендация' }},
      }};
      const result = mod.applyResearchRecommendationPresetToForm(
        form,
        envelope,
        {{ touchedFields: ['brief'] }},
      );
      console.log(JSON.stringify({{
        preset: result.preset,
        appliedFields: result.appliedFields,
        values: {{
          category: elements.product_category.value,
          platform: elements.platform.value,
          mode: elements.generation_mode.value,
          duration: elements.duration_seconds.value,
          format: elements.format.value,
          brief: elements.brief.value,
          campaign: elements.campaign_id.value,
          destination: elements.destination_ref.value,
          count: elements.count.value,
          media: elements.media_id.value,
          spendValue: elements.real_spend_confirmation.value,
          spendChecked: elements.real_spend_confirmation.checked,
        }},
        provenance,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["preset"] == {
        "product_category": "food",
        "platform": "youtube",
        "mode": "real_seedance",
        "duration_seconds": 12,
        "format": "9:16",
        "brief": "Готовый замысел ИИ",
    }
    assert value["appliedFields"] == [
        "product_category",
        "platform",
        "mode",
        "duration_seconds",
        "format",
    ]
    assert value["values"] == {
        "category": "food",
        "platform": "youtube",
        "mode": "real_seedance",
        "duration": "12",
        "format": "9:16",
        "brief": "Моя ручная правка",
        "campaign": "campaign-unchanged",
        "destination": "@unchanged",
        "count": "3",
        "media": "media-unchanged",
        "spendValue": "CONFIRM_REAL_SEEDANCE",
        "spendChecked": True,
    }
    assert value["provenance"] == {
        "selection_id": "11111111-1111-4111-8111-111111111111",
        "recommendation_position": 2,
        "preset": value["preset"],
        "applied_fields": value["appliedFields"],
    }


def test_category_recommendation_and_manual_opt_out_are_non_blocking() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    generation_url = (APP / "workspace-generation-research-recommendations.js").as_uri()
    script = f"""
      const mod = await import({json.dumps(generation_url)});
      class Control extends EventTarget {{
        constructor(name, value, values = []) {{
          super();
          this.name = name;
          this.value = value;
          this.defaultValue = value;
          this.dataset = {{}};
          this.options = values.map((candidate) => ({{ value: candidate }}));
        }}
      }}
      class Form extends EventTarget {{
        constructor(elements) {{ super(); this.elements = elements; this.dataset = {{}}; }}
      }}
      const elements = {{
        product_category: new Control('product_category', 'food', ['food']),
        platform: new Control('platform', 'instagram', ['instagram', 'youtube']),
        generation_mode: new Control('generation_mode', 'mock', ['mock', 'real_gen4']),
        duration_seconds: new Control('duration_seconds', '5', ['5', '8']),
        brief: new Control('brief', ''),
      }};
      const form = new Form(elements);
      const envelope = {{
        selection_id: '22222222-2222-4222-8222-222222222222',
        scope_match: 'category',
        recommendation: {{
          position: 1,
          platform: 'youtube',
          recommended_generation_mode: 'gen4_turbo',
          duration_seconds: 5,
          title: 'Категорийная идея',
          hook: 'Сначала результат',
        }},
      }};
      const automatic = mod.applyResearchRecommendationPresetToForm(form, envelope);
      const explicit = mod.applyResearchRecommendationPresetToForm(
        form, envelope, {{ explicit: true }}
      );
      let optOut = null;
      form.addEventListener(
        'contentengine:generation-research-preset-opt-out',
        (event) => {{ optOut = event.detail; }},
      );
      const beforeManual = {{
        platform: elements.platform.value,
        mode: elements.generation_mode.value,
        brief: elements.brief.value,
      }};
      mod.optOutResearchRecommendationForForm(form, envelope);
      const afterManual = {{
        platform: elements.platform.value,
        mode: elements.generation_mode.value,
        brief: elements.brief.value,
      }};
      const blockedAfterOptOut = mod.resolveResearchPresetAppliedFields({{
        preset: explicit.preset,
        exact: true,
        optedOut: true,
      }});
      const protectedFields = mod.resolveResearchPresetAppliedFields({{
        preset: explicit.preset,
        exact: true,
        touchedFields: ['platform', 'mode', 'duration_seconds', 'brief'],
      }});
      console.log(JSON.stringify({{
        automatic: automatic.appliedFields,
        explicit: explicit.appliedFields,
        beforeManual,
        afterManual,
        lineage: form.dataset.researchRecommendationLineage || null,
        optOut,
        blockedAfterOptOut,
        protectedFields,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    assert value["automatic"] == []
    assert value["explicit"] == ["platform", "mode", "duration_seconds", "brief"]
    assert value["beforeManual"] == value["afterManual"]
    assert value["lineage"] is None
    assert value["blockedAfterOptOut"] == []
    assert value["protectedFields"] == []
    assert value["optOut"]["selection_id"] == "22222222-2222-4222-8222-222222222222"
    assert value["optOut"]["applied_fields"] == []
    assert value["optOut"]["opted_out"] is True

    # The v3 lookup treats the current platform as ranking context, not a hard
    # filter. A returned YouTube recommendation can replace initial Instagram.
    assert "keeps cross-platform recommendations" in GENERATION
    assert "platform: context.platform" in GENERATION
    assert "Рекомендации временно недоступны" in GENERATION
    assert "Ручной режим включён" in GENERATION


def test_generation_preset_restore_and_duration_contract() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    generation_url = (APP / "workspace-generation-research-recommendations.js").as_uri()
    script = f"""
      const mod = await import({json.dumps(generation_url)});
      class Control extends EventTarget {{
        constructor(name, value, values = []) {{
          super();
          this.name = name;
          this.value = value;
          this.defaultValue = value;
          this.dataset = {{}};
          this.options = values.map((candidate) => ({{ value: candidate }}));
        }}
      }}
      class Form extends EventTarget {{
        constructor(elements) {{ super(); this.elements = elements; this.dataset = {{}}; }}
      }}
      const elements = {{
        product_category: new Control('product_category', 'food', ['food']),
        platform: new Control('platform', 'instagram', ['instagram', 'youtube']),
        generation_mode: new Control('generation_mode', 'mock', [
          'mock', 'real_photo', 'real_gen4', 'real_seedance'
        ]),
        duration_seconds: new Control('duration_seconds', '10', [
          '2', '4', '5', '8', '10', '12', '15'
        ]),
        brief: new Control('brief', 'Сохранённая ручная правка'),
      }};
      const form = new Form(elements);
      const envelope = {{
        selection_id: '33333333-3333-4333-8333-333333333333',
        recommendation_position: 3,
        scope_match: 'exact_product',
        preset: {{
          product_category: 'food',
          platform: 'youtube',
          generation_mode: 'real_gen4',
          duration_seconds: 12,
        }},
        recommendation: {{ position: 3, title: 'Безопасный Gen4' }},
      }};
      let restoredEvent = null;
      form.addEventListener(
        'contentengine:generation-research-preset-applied',
        (event) => {{ restoredEvent = event.detail; }},
      );
      const before = Object.fromEntries(
        Object.entries(elements).map(([key, control]) => [key, control.value])
      );
      const restored = mod.restoreResearchRecommendationPresetLineage(
        form,
        envelope,
        {{
          selectionId: envelope.selection_id,
          recommendationPosition: 3,
          appliedFields: ['platform', 'mode', 'duration_seconds', 'brief'],
          touchedFields: ['brief'],
        }},
      );
      const after = Object.fromEntries(
        Object.entries(elements).map(([key, control]) => [key, control.value])
      );
      const secondRestore = mod.restoreResearchRecommendationPresetLineage(
        form,
        envelope,
        {{
          selectionId: envelope.selection_id,
          recommendationPosition: 3,
          appliedFields: ['platform', 'mode', 'duration_seconds', 'brief'],
          touchedFields: ['brief'],
        }},
      );
      const gen4 = mod.normalizeResearchRecommendationPreset({{
        preset: {{ generation_mode: 'real_gen4', duration_seconds: 12 }},
        recommendation: {{ title: 'Gen4' }},
      }});
      const seedance = mod.normalizeResearchRecommendationPreset({{
        preset: {{ generation_mode: 'real_seedance', duration_seconds: 5 }},
        recommendation: {{ title: 'Seedance' }},
      }});
      const photo = mod.normalizeResearchRecommendationPreset({{
        preset: {{ generation_mode: 'real_photo', duration_seconds: 8 }},
        recommendation: {{ title: 'Фото' }},
      }});
      console.log(JSON.stringify({{
        before,
        after,
        restored,
        secondRestore,
        restoredEvent,
        gen4,
        seedance,
        photo,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    assert value["before"] == value["after"]
    assert value["restored"]["restored"] is True
    assert value["restored"]["dispatched"] is True
    assert value["secondRestore"]["restored"] is True
    assert value["secondRestore"]["dispatched"] is False
    assert value["restoredEvent"]["selection_id"] == (
        "33333333-3333-4333-8333-333333333333"
    )
    assert value["restoredEvent"]["recommendation_position"] == 3
    assert value["restoredEvent"]["applied_fields"] == [
        "platform", "mode", "duration_seconds", "brief"
    ]
    assert value["gen4"]["duration_seconds"] == 5
    assert value["seedance"]["duration_seconds"] == 8
    assert "duration_seconds" not in value["photo"]
    assert "const restoredIndex = recommendations.findIndex" in GENERATION
    assert "runtime.activeIndex = restoredIndex >= 0 ? restoredIndex : 0" in GENERATION
    assert "restoreResearchRecommendationPresetLineage(form, selected" in GENERATION
    assert "formChanged\n    && runtime.response" in GENERATION


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


def test_generation_adapter_calls_the_deployed_recommendation_rpc_name() -> None:
    assert (
        'const RPC_RECOMMENDATIONS = '
        '"contentengine_generation_research_recommendations";'
    ) in GENERATION
    assert '"creator_generation_research_recommendations"' not in GENERATION


def test_ai_center_adapter_calls_the_deployed_training_rpc_names() -> None:
    assert (
        'const RPC_QUEUE = "contentengine_ai_research_training_queue";'
    ) in AI_CENTER
    assert (
        'const RPC_DECIDE = "contentengine_decide_ai_research_training";'
    ) in AI_CENTER
    assert '"creator_ai_research_training_queue"' not in AI_CENTER
    assert '"creator_decide_ai_research_training"' not in AI_CENTER


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

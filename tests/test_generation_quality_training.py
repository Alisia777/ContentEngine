from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/generation-quality-training.js"
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _run_module(script: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_each_structured_quality_dimension_routes_to_one_exact_lesson() -> None:
    module_url = MODULE.as_uri()
    payload = _run_module(
        f"""
import {{ generationQualityTrainingRecommendation }} from {json.dumps(module_url)};
const codes = [
  "product_fidelity",
  "technical_stability",
  "hook_clarity",
  "visual_quality",
  "trust",
  "platform_fit",
];
const mapped = Object.fromEntries(codes.map((code) => [
  code,
  generationQualityTrainingRecommendation({{ guardCodes: [code] }}),
]));
process.stdout.write(JSON.stringify(mapped));
"""
    )
    assert set(payload) == {
        "product_fidelity",
        "technical_stability",
        "hook_clarity",
        "visual_quality",
        "trust",
        "platform_fit",
    }
    for code, target in payload.items():
        assert target["dimensionCode"] == code
        assert target["courseCode"] in {
            "video_quality",
            "publishing_funnel",
            "security_wb",
        }
        assert target["lessonId"]
        assert target["href"].startswith(f"#/learn/{target['courseCode']}?lesson=")
        assert target["href"].endswith("&source=generation_qa")
        assert 3 <= len(target["title"]) <= 120
        assert 10 <= len(target["tip"]) <= 500


def test_recommendation_is_allowlisted_bounded_and_uses_first_known_weakness() -> None:
    module_url = MODULE.as_uri()
    payload = _run_module(
        f"""
import {{
  generationQualityTrainingRecommendation,
  targetedGenerationQualityLesson,
}} from {json.dumps(module_url)};
const selected = generationQualityTrainingRecommendation({{
  qualityGuardCodes: ["raw reviewer prose", "trust", "platform_fit"],
}});
const ignored = generationQualityTrainingRecommendation({{
  guardCodes: ["raw reviewer prose"],
}});
const course = {{
  lessons: [
    {{ id: "rights_and_claims", title: "Права" }},
    {{ id: "incident_stop", title: "Стоп" }},
  ],
}};
const query = new URLSearchParams("lesson=rights_and_claims&source=generation_qa");
const forged = new URLSearchParams("lesson=rights_and_claims&source=external");
process.stdout.write(JSON.stringify({{
  selected,
  ignored,
  target: targetedGenerationQualityLesson(course, query),
  forged: targetedGenerationQualityLesson(course, forged),
}}));
"""
    )
    assert payload["selected"]["dimensionCode"] == "trust"
    assert payload["ignored"] is None
    assert payload["target"]["lessonIndex"] == 0
    assert payload["target"]["lesson"]["title"] == "Права"
    assert payload["forged"] is None


def test_generation_repair_and_recurring_learning_surface_targeted_training() -> None:
    assert 'from "./generation-quality-training.js?v=20260728.1"' in APP
    assert APP.count("generationQualityTrainingRecommendation(policy)") >= 2
    assert "generation-quality-training-link" in APP
    assert "Точечное повторение после QA" in APP
    assert "targetedGenerationQualityLesson(" in APP
    assert "scroll: Boolean(targetedLesson)" in APP
    assert ".generation-quality-training-link" in STYLES
    assert ".quality-training-arrival" in STYLES
    assert "@media (max-width: 760px)" in STYLES
    assert "min-width: 0;" in STYLES
    assert "app.js?v=20260823.copy-engines.52" in INDEX
    assert "styles.css?v=20260730.4" in INDEX

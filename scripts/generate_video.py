from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.prompt_builder import PromptPackBuilder
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.script_generator import GeneratorScriptService
from app.intelligence.video_generator import GeneratorVideoService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a real data-driven product video workflow.")
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--llm-provider", default=None, help="openai or mock. Defaults to QVF_LLM_PROVIDER/mock.")
    parser.add_argument("--video-provider", default=None, help="runway, gemini, or mock. Defaults to QVF_VIDEO_PROVIDER/mock.")
    parser.add_argument("--build-prompts-only", action="store_true", help="Build intelligence, brief, script, and prompt pack only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    with SessionLocal() as db:
        pack = CreativeIntelligenceBuilder(db).build_for_product(args.product_id)
        brief = ScriptBriefBuilder(db).build_from_record(pack.id)
        script_job = GeneratorScriptService(db).generate_from_brief(brief.id, args.llm_provider)
        variant = sorted(script_job.variants, key=lambda item: item.variant_number)[0]
        prompt_provider = args.video_provider or "runway"
        prompt_pack = PromptPackBuilder(db).build_for_script(variant.id, prompt_provider, brief.id)
        video_job = None
        if not args.build_prompts_only:
            video_job = GeneratorVideoService(db).create_video_job_from_prompt_pack(prompt_pack.id, args.video_provider)

    print("\nContentEngine real generator flow")
    print("=" * 38)
    print(f"Product ID: {args.product_id}")
    print(f"Creative Intelligence Pack ID: {pack.id}")
    print(f"Script Brief ID: {brief.id}")
    print(f"Script Job ID: {script_job.id} ({script_job.llm_provider})")
    print(f"Script Variant ID: {variant.id}")
    print(f"Prompt Pack ID: {prompt_pack.id} ({prompt_provider})")
    if video_job:
        print(f"Video Job ID: {video_job.id} ({video_job.provider}) / {video_job.status}")
    else:
        print("Video Job: skipped by --build-prompts-only")
    print(f"Objective: {pack.pack_json.get('recommended_objective')}")
    print(f"Angles: {', '.join(pack.pack_json.get('recommended_creative_angles', []))}")
    if pack.pack_json.get("missing_data"):
        print(f"Missing data: {', '.join(pack.pack_json['missing_data'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


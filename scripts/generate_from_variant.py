from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError
from app.video_generator.errors import VideoGeneratorError
from app.video_generator.generator import VideoGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build provider prompts from a selected CreativeVariant.")
    parser.add_argument("--creative-variant-id", type=int, required=True)
    parser.add_argument("--video-provider", default=None, help="mock, runway, or gemini. Defaults to QVF_VIDEO_PROVIDER/mock.")
    parser.add_argument("--build-prompts-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.build_prompts_only:
        print("Error: Sprint 05 CLI supports --build-prompts-only only; real smoke belongs to a later sprint.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            variant = VideoGenerator(db).build_prompt_pack_from_variant(
                args.creative_variant_id,
                provider=args.video_provider,
            )
            summary = {
                "creative_variant_id": args.creative_variant_id,
                "generation_variant_id": variant.id,
                "creative_spec_id": variant.creative_spec_id,
                "prompt_pack_id": variant.prompt_pack_id,
                "provider": variant.provider,
                "status": variant.status,
                "reference_readiness_status": variant.prompt_pack_json.get("reference_readiness_status"),
                "reference_bundle_id": variant.prompt_pack_json.get("reference_bundle_id"),
                "reference_images": variant.prompt_pack_json.get("reference_images") or [],
                "warnings": variant.prompt_pack_json.get("warnings") or [],
            }
    except (VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine variant-driven prompt pack")
    print("=" * 43)
    print(f"Creative Variant ID: {summary['creative_variant_id']}")
    print(f"Creative Spec ID: {summary['creative_spec_id']}")
    print(f"Generation Variant ID: {summary['generation_variant_id']}")
    print(f"Prompt Pack ID: {summary['prompt_pack_id']}")
    print(f"Provider: {summary['provider']}")
    print(f"Status: {summary['status']}")
    print(f"Reference Readiness: {summary['reference_readiness_status'] or 'unknown'}")
    print(f"Reference Bundle ID: {summary['reference_bundle_id'] or 'none'}")
    print(f"Reference Images: {len(summary['reference_images'])}")
    print(f"Real Smoke Eligible: {summary['reference_readiness_status'] == 'ready'}")
    if summary["warnings"]:
        print("Warnings: " + ", ".join(summary["warnings"]))
    print("Video Job: skipped by prompt-only mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

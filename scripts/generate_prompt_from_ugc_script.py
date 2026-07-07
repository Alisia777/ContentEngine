from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.blogger_brief import BloggerBriefError
from app.blogger_brief.prompt_enricher import PromptEnricher
from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError
from app.video_generator.errors import VideoGeneratorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a prompt pack from a UGC script without calling a paid provider.")
    parser.add_argument("--ugc-script-id", type=int, required=True)
    parser.add_argument("--video-provider", default="runway")
    parser.add_argument("--build-prompts-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.build_prompts_only:
        print("Error: this CLI only supports --build-prompts-only.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            variant = PromptEnricher(db).build_prompt_pack_from_script(
                args.ugc_script_id,
                provider=args.video_provider,
                build_prompts_only=True,
            )
    except (BloggerBriefError, VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    prompt_pack = variant.prompt_pack_json or {}
    print("\nContentEngine UGC script prompt-only")
    print("=" * 42)
    print(f"UGC Script ID: {args.ugc_script_id}")
    print(f"Generation Variant ID: {variant.id}")
    print(f"Prompt Pack ID: {variant.prompt_pack_id}")
    print(f"Product Lock Mode: {prompt_pack.get('product_lock_mode')}")
    print(f"Reference Count: {prompt_pack.get('product_reference_count')}")
    print(f"Mass Safety: {prompt_pack.get('mass_generation_safety_status')}")
    print("Video skipped. Provider not called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

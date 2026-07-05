from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.video_generator.errors import VideoGeneratorError
from app.video_generator.regeneration_requests import RegenerationRequestService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a prompt-only scene regeneration from saved human feedback.")
    parser.add_argument("--regeneration-request-id", type=int, required=True)
    parser.add_argument("--build-prompts-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.build_prompts_only:
        print("Error: regeneration from feedback is prompt-only; pass --build-prompts-only.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            request = RegenerationRequestService(db).build_prompt_only(args.regeneration_request_id)
            output = request.prompt_only_output_json or {}
            scene = output.get("scene_prompt") or {}
            summary = {
                "id": request.id,
                "generation_variant_id": request.video_generation_variant_id,
                "prompt_pack_id": output.get("prompt_pack_id"),
                "scene_number": request.scene_number,
                "reason": request.reason,
                "status": request.status,
                "prompt_text": scene.get("prompt_text") or "",
                "negative_prompt": scene.get("negative_prompt") or "",
            }
    except VideoGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine prompt-only regeneration")
    print("=" * 40)
    print(f"Regeneration Request ID: {summary['id']}")
    print(f"Generation Variant ID: {summary['generation_variant_id']}")
    print(f"Prompt Pack ID: {summary['prompt_pack_id']}")
    print(f"Scene Number: {summary['scene_number']}")
    print(f"Reason: {summary['reason']}")
    print(f"Status: {summary['status']}")
    print("Video Job: skipped by prompt-only mode")
    print("\nPrompt Text:")
    print(summary["prompt_text"])
    print("\nNegative Prompt:")
    print(summary["negative_prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

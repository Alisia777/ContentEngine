from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.intelligence.errors import IntelligenceError
from app.one_video_acceptance import OneVideoAcceptanceError, OneVideoAcceptanceService
from app.video_generator.errors import VideoGeneratorError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one-video paid smoke through the selected provider.")
    parser.add_argument("--plan-id", type=int, required=True)
    parser.add_argument("--video-provider", default="runway")
    parser.add_argument("--real-run", action="store_true")
    parser.add_argument("--max-scenes", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.real_run:
        print("Error: one-video paid smoke requires --real-run.", file=sys.stderr)
        return 2
    init_db()
    try:
        with SessionLocal() as db:
            result = OneVideoAcceptanceService(db).run_real(
                args.plan_id,
                provider=args.video_provider,
                real_run=True,
                max_scenes=args.max_scenes,
            )
            output = OneVideoAcceptanceService.as_result_output(result)
    except (OneVideoAcceptanceError, VideoGeneratorError, IntelligenceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine one-video paid smoke")
    print("=" * 40)
    print(f"Result ID: {output.id}")
    print(f"Plan ID: {output.plan_id}")
    print(f"Video Job ID: {output.video_job_id or 'none'}")
    print(f"Output Acceptance ID: {output.output_acceptance_id or 'none'}")
    print("Provider Job IDs: " + (", ".join(output.provider_job_ids) if output.provider_job_ids else "none"))
    print(f"Status: {output.status}")
    print("Downloaded Outputs: " + (", ".join(output.local_output_paths) if output.local_output_paths else "none"))
    print(f"Final Video: {output.final_video_path or 'pending'}")
    print(f"Generation Report: {output.generation_report_path or 'not written'}")
    print(f"Human Review: {output.human_review_status}")
    print("Manual review required. No auto-approval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

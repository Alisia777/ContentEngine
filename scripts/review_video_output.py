from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, init_db
from app.output_acceptance import AcceptanceReviewService, OutputAcceptanceError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review real or fixture video output against an AI production brief.")
    parser.add_argument("--video-job-id", type=int, required=True)
    parser.add_argument("--ai-production-brief-id", type=int, required=True)
    parser.add_argument("--decision", default="needs_human_review")
    parser.add_argument("--product-identity-status", default="needs_review")
    parser.add_argument("--packaging-status", default="needs_review")
    parser.add_argument("--geometry-status", default="needs_review")
    parser.add_argument("--blogger-authenticity-status", default="needs_review")
    parser.add_argument("--scene-match-status", default="needs_review")
    parser.add_argument("--proof-moment-status", default="needs_review")
    parser.add_argument("--cta-status", default="needs_review")
    parser.add_argument("--reviewer-notes", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            acceptance = AcceptanceReviewService(db).review(
                video_job_id=args.video_job_id,
                ai_production_brief_id=args.ai_production_brief_id,
                decision=args.decision,
                product_identity_status=args.product_identity_status,
                packaging_status=args.packaging_status,
                geometry_status=args.geometry_status,
                blogger_authenticity_status=args.blogger_authenticity_status,
                scene_match_status=args.scene_match_status,
                proof_moment_status=args.proof_moment_status,
                cta_status=args.cta_status,
                reviewer_notes=args.reviewer_notes,
            )
    except OutputAcceptanceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine output acceptance review")
    print("=" * 42)
    print(f"Acceptance ID: {acceptance.id}")
    print(f"Video Job ID: {acceptance.video_job_id}")
    print(f"AI Production Brief ID: {acceptance.ai_production_brief_id}")
    print(f"Status: {acceptance.status}")
    print(f"Score: {acceptance.score}")
    print(f"Publishing Readiness: {acceptance.publishing_readiness}")
    print("Blockers: " + (", ".join(acceptance.blockers_json or []) if acceptance.blockers_json else "none"))
    print(f"Contact Sheet: {acceptance.contact_sheet_path or 'missing'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.creative_quality import CreativeQualityDataError, ScriptRewriter
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a rewritten UGC script from a creative rewrite request.")
    parser.add_argument("--rewrite-request-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            result = ScriptRewriter(db).build(args.rewrite_request_id)
    except CreativeQualityDataError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("\nContentEngine UGC rewrite build")
    print("=" * 34)
    print(f"Rewrite Request ID: {result.rewrite_request_id}")
    print(f"Source UGC Script ID: {result.source_ugc_script_id}")
    print(f"New UGC Script ID: {result.new_ugc_script_id}")
    print(f"Status: {result.status}")
    print("Required Fixes: " + (" | ".join(result.required_fixes) if result.required_fixes else "none"))
    print("Before: " + " / ".join(line for line in result.before_lines if line))
    print("After: " + " / ".join(line for line in result.after_lines if line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

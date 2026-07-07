from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models
from app.ai_brief_contract import MarkdownRenderer
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export an AI production brief as Markdown.")
    parser.add_argument("--ai-production-brief-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    with SessionLocal() as db:
        brief = db.get(models.AIProductionBrief, args.ai_production_brief_id)
        if not brief:
            print(f"Error: AIProductionBrief {args.ai_production_brief_id} not found.", file=sys.stderr)
            return 2
        print(brief.brief_markdown or MarkdownRenderer().render(brief), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

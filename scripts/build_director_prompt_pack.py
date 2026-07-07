from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ai_brief_contract import AIBriefContractError, DirectorPromptBuilder
from app.database import SessionLocal, init_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a director prompt pack for an AI production brief.")
    parser.add_argument("--ai-production-brief-id", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()
    try:
        with SessionLocal() as db:
            prompt = DirectorPromptBuilder(db).build(args.ai_production_brief_id)
    except AIBriefContractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print("\nContentEngine director prompt pack")
    print("=" * 40)
    print(f"Director Prompt Pack ID: {prompt.id}")
    print(f"AI Production Brief ID: {prompt.ai_production_brief_id}")
    print(f"Status: {prompt.status}")
    print(f"Prompt Pack ID: {prompt.prompt_pack_id or 'none'}")
    print(f"Negative Prompt: {prompt.negative_prompt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

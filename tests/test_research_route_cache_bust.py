from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"


def test_research_route_bootstrap_uses_one_fresh_cache_key() -> None:
    index = (APP / "index.html").read_text(encoding="utf-8")
    bootstrap = (
        APP / "workspace-research-training-bootstrap.js"
    ).read_text(encoding="utf-8")

    build_match = re.search(
        r'const BUILD = "([^"]+)";',
        bootstrap,
    )
    assert build_match is not None
    cache_key = build_match.group(1)

    assert cache_key == "20260810.research.28"
    assert (
        f'workspace-research-training-bootstrap.js?v={cache_key}'
        in index
    )
    assert "`${file}?v=${BUILD}`" in bootstrap

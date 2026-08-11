from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"


def test_research_route_bootstrap_uses_scoped_exact_source_cache_key() -> None:
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

    assert cache_key == "20260810.research.30"
    assert (
        "workspace-research-training-bootstrap.js?"
        "v=20260811.exact-source-lifecycle.1"
        in index
    )
    assert '"workspace-ai-exact-youtube-sources.js":' in bootstrap
    assert '"20260811.exact-source-lifecycle.1"' in bootstrap
    assert "ASSET_BUILD_OVERRIDES[file] || BUILD" in bootstrap
    assert "`${file}?v=${build}`" in bootstrap

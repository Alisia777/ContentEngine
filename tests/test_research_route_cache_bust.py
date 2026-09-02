from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"


def test_research_route_bootstrap_uses_content_addressed_ai_center_cache_key() -> None:
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

    assert cache_key == "20260814.os4.41"
    normalized_bootstrap = bootstrap.replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256(normalized_bootstrap.encode("utf-8")).hexdigest()
    outer_cache_match = re.search(
        r'workspace-research-training-bootstrap[.]js[?]v=([^"&]+)',
        index,
    )
    assert outer_cache_match is not None
    assert outer_cache_match.group(1) == f"sha256-{digest}"
    changed_digest = hashlib.sha256(
        (normalized_bootstrap + "\n").encode("utf-8")
    ).hexdigest()
    assert changed_digest != digest
    assert '"workspace-ai-exact-youtube-sources.js":' in bootstrap
    assert (
        '"workspace-ai-exact-youtube-sources.js":\n'
        '      "20260814.os4.41"'
        in bootstrap
    )
    assert (
        '"workspace-ai-research-training.js":\n'
        '      "20260826.rebuild-clean.53"'
        in bootstrap
    )
    assert (
        '"workspace-ai-research-training.css":\n'
        '      "20260826.rebuild-clean.53"'
        in bootstrap
    )
    assert (
        '"workspace-generation-research-recommendations.js":\n'
        '      "20260826.rebuild-clean.53"'
        in bootstrap
    )
    assert (
        '"workspace-research-failure-recovery.js":\n'
        '      "20260814.os4.41"'
        in bootstrap
    )
    assert "ASSET_BUILD_OVERRIDES[file] || BUILD" in bootstrap
    assert "`${file}?v=${build}`" in bootstrap

from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
APP_INDEX = (APP / "index.html").read_text(encoding="utf-8")
ROOT_INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP / "workspace-build-guard.js").read_text(encoding="utf-8")
MANIFEST = json.loads((APP / "build.json").read_text(encoding="utf-8"))


def test_research_shorts_hotfix_build_is_consistent() -> None:
    build_id = MANIFEST["id"]
    assert build_id == "20260805.os4.1.1"
    assert f'content="{build_id}"' in APP_INDEX
    assert f'content="{build_id}"' in ROOT_INDEX
    assert f'const CURRENT_BUILD = "{build_id}"' in SCRIPT
    assert MANIFEST["label"] == "ContentEngine Desktop v4.1.1 · Research Shorts Fix"
    assert 'const BUILD_BADGE = "Desktop · 4.1.1"' in SCRIPT

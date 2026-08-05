import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / "web/app/product-research-view.js").read_text(encoding="utf-8")


def _run_view_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(VIEW, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_youtube_research_deeplink_prefills_fixed_ai_category_and_source() -> None:
    result = _run_view_module(
        """
        const params = new URLSearchParams({
          research_prefill: "1",
          product_name: "Аэрогриль Demiand — разбор YouTube Shorts",
          sku: "YT-RIJ-v--Yncw",
          product_category: "electronics",
          category_name: "Аэрогрили",
          research_focus: "Разобрать хук, демонстрацию продукта и доказательства",
          marketplace_url: "https://www.youtube.com/shorts/RIJ_v--Yncw",
          objective: "education",
          known_facts: "Ролик — публичный референс. Свойства товара требуют проверки.",
        });
        params.append("platform", "youtube");
        const hash = `#/workspace/research?${params.toString()}`;
        const prefill = subject.productResearchUrlPrefill(hash);
        globalThis.window = { location: { hash } };
        const html = subject.productResearchInputMarkup({
          defaults: {
            productName: "Старое значение",
            platforms: ["vk"],
          },
        });
        return {
          prefill,
          hasProduct: html.includes('value="Аэрогриль Demiand — разбор YouTube Shorts"'),
          hasSku: html.includes('value="YT-RIJ-v--Yncw"'),
          hasYoutubeUrl: html.includes('value="https://www.youtube.com/shorts/RIJ_v--Yncw"'),
          hasElectronics: html.includes('<option value="electronics" selected>'),
          youtubeChecked: html.includes('name="platforms" value="youtube" checked'),
          vkChecked: html.includes('name="platforms" value="vk" checked'),
          hasReferenceLabel: html.includes("Публичная ссылка на товар или референс"),
          hasYoutubeNotice: html.includes("YouTube Shorts распознан как публичный референс"),
        };
        """
    )
    assert result["prefill"]["productName"] == "Аэрогриль Demiand — разбор YouTube Shorts"
    assert result["prefill"]["productCategory"] == "electronics"
    assert result["prefill"]["marketplaceUrl"] == "https://www.youtube.com/shorts/RIJ_v--Yncw"
    assert result["prefill"]["platforms"] == ["youtube"]
    assert result["prefill"]["objective"] == "education"
    assert result["hasProduct"] is True
    assert result["hasSku"] is True
    assert result["hasYoutubeUrl"] is True
    assert result["hasElectronics"] is True
    assert result["youtubeChecked"] is True
    assert result["vkChecked"] is False
    assert result["hasReferenceLabel"] is True
    assert result["hasYoutubeNotice"] is True


def test_research_deeplink_requires_explicit_gate_and_rejects_unsafe_url() -> None:
    result = _run_view_module(
        """
        const ungated = subject.productResearchUrlPrefill(
          "#/workspace/research?product_name=Не%20подставлять&product_category=electronics",
        );
        const unsafe = subject.productResearchUrlPrefill(
          "#/workspace/research?research_prefill=1&marketplace_url=javascript%3Aalert(1)&product_category=unknown&objective=unknown&platform=unknown",
        );
        return { ungated, unsafe };
        """
    )
    assert result["ungated"] == {}
    assert "marketplaceUrl" not in result["unsafe"]
    assert "productCategory" not in result["unsafe"]
    assert "objective" not in result["unsafe"]
    assert "platforms" not in result["unsafe"]

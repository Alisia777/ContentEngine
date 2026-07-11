from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.output_acceptance.output_quality_checker import OutputQualityChecker
from app.visual_evidence import ReferenceTextInput, VisualEvidencePolicy, VisualEvidenceService
from app.visual_evidence.service import OCRExecutionError


class FakeOCR:
    name = "fake_local_ocr"

    def __init__(self, values: dict[str, str] | None = None, *, available: bool = True, fail: bool = False):
        self.values = values or {}
        self._available = available
        self.fail = fail
        self.calls: list[str] = []

    @property
    def available(self) -> bool:
        return self._available

    def extract_text(self, image_path: Path, *, language: str, timeout_seconds: float) -> str:
        self.calls.append(image_path.name)
        if self.fail:
            raise OCRExecutionError("test_ocr_failure")
        return self.values.get(image_path.name, "")


def make_frame(path: Path, color: tuple[int, int, int], *, size: tuple[int, int] = (720, 1280), label: str = "") -> Path:
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 80, size[0] - 60, size[1] - 80), outline=(255, 255, 255), width=12)
    draw.text((100, 140), label, fill=(255, 255, 255))
    image.save(path, format="PNG")
    return path


def test_real_decodable_diverse_frames_produce_passed_evidence(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20), label="one"),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40), label="two"),
        make_frame(tmp_path / "frame-3.png", (20, 60, 180), label="three"),
    ]

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate(frames)

    assert report.status == "passed"
    assert report.decoded_frame_count == 3
    assert report.unique_frame_count == 3
    assert report.unique_frame_ratio == 1
    assert report.minimum_short_side_observed_px == 720
    assert report.minimum_long_side_observed_px == 1280
    assert report.ocr.status == "not_required"
    assert report.blockers == []


def test_non_image_or_missing_frame_is_never_counted_as_decoded(tmp_path: Path):
    valid = make_frame(tmp_path / "valid.png", (180, 20, 20))
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not-an-image")

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate([valid, corrupt])

    assert report.status == "blocked"
    assert report.decoded_frame_count == 1
    assert "visual_evidence_frame_not_decodable" in report.blockers
    assert "replace_corrupt_or_non_image_extracted_frames" in report.required_fixes
    assert report.frames[1].decoded is False
    assert report.frames[1].sha256 is None


def test_resolution_below_contract_is_blocking(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "small-1.png", (180, 20, 20), size=(320, 568)),
        make_frame(tmp_path / "small-2.png", (20, 150, 40), size=(320, 568)),
    ]

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate(frames)

    assert report.status == "blocked"
    assert "visual_evidence_resolution_below_minimum" in report.blockers
    assert report.minimum_short_side_observed_px == 320


def test_perceptual_duplicates_and_freeze_are_blocking(tmp_path: Path):
    original = make_frame(tmp_path / "freeze-1.png", (70, 80, 90), label="same")
    frames = [original]
    for index in range(2, 6):
        duplicate = tmp_path / f"freeze-{index}.png"
        duplicate.write_bytes(original.read_bytes())
        frames.append(duplicate)

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate(frames)

    assert report.status == "blocked"
    assert report.unique_frame_count == 1
    assert report.longest_duplicate_run == 5
    assert report.freeze_run_ratio == 1
    assert "visual_evidence_duplicate_frames" in report.blockers
    assert "visual_evidence_freeze_detected" in report.blockers


def test_one_frame_cannot_claim_diversity(tmp_path: Path):
    frame = make_frame(tmp_path / "only.png", (70, 80, 90))

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate([frame])

    assert report.status == "blocked"
    assert "visual_evidence_frame_count_below_minimum" in report.blockers


def test_required_ocr_blocks_when_local_tool_is_unavailable(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    backend = FakeOCR(available=False)

    report = VisualEvidenceService(ocr_backend=backend).evaluate(
        frames,
        references=[
            ReferenceTextInput(
                source_kind="product_input",
                source_ref="product:1",
                required_tokens=["BOMBBAR", "60G"],
            )
        ],
    )

    assert report.status == "blocked"
    assert report.ocr.required is True
    assert report.ocr.tool_available is False
    assert report.ocr.status == "blocked"
    assert "ocr_tool_unavailable" in report.blockers
    assert backend.calls == []


def test_required_ocr_blocks_without_reference_evidence(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate(
        frames,
        policy=VisualEvidencePolicy(ocr_required=True),
    )

    assert report.status == "blocked"
    assert report.ocr.expected_tokens == []
    assert "ocr_reference_evidence_missing" in report.blockers


def test_ocr_matches_only_observed_reference_tokens(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    backend = FakeOCR(
        {
            "frame-1.png": "BOMBBAR PROTEIN",
            "frame-2.png": "60G cocoa",
        }
    )

    report = VisualEvidenceService(ocr_backend=backend).evaluate(
        frames,
        references=[
            ReferenceTextInput(
                source_kind="product_asset",
                source_ref="product_asset:42",
                required_tokens=["BOMBBAR", "60G"],
            )
        ],
    )

    assert report.status == "passed"
    assert report.ocr.status == "passed"
    assert report.ocr.expected_tokens == ["bombbar", "60g"]
    assert report.ocr.matched_tokens == ["bombbar", "60g"]
    assert report.ocr.missing_tokens == []
    assert report.ocr.token_match_ratio == 1
    assert report.ocr.reference_source_refs == ["product_asset:42"]


def test_ocr_does_not_fabricate_missing_packaging_token(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    backend = FakeOCR({"frame-1.png": "BOMBBAR", "frame-2.png": "cocoa"})

    report = VisualEvidenceService(ocr_backend=backend).evaluate(
        frames,
        references=[
            ReferenceTextInput(
                source_kind="product_input",
                source_ref="product:1",
                required_tokens=["BOMBBAR", "60G"],
            )
        ],
    )

    assert report.status == "blocked"
    assert report.ocr.matched_tokens == ["bombbar"]
    assert report.ocr.missing_tokens == ["60g"]
    assert report.ocr.token_match_ratio == 0.5
    assert "ocr_reference_tokens_missing_from_frames" in report.blockers


def test_product_asset_adapter_uses_only_explicit_trusted_metadata(tmp_path: Path):
    path = make_frame(tmp_path / "do-not-infer-secret-name.png", (180, 20, 20))
    asset = SimpleNamespace(
        id=91,
        source_type="local",
        source_ref=path.as_posix(),
        filename="do-not-infer-secret-name.png",
        manual_label="not trusted packaging evidence",
        metadata_json={"required_packaging_tokens": ["BOMBBAR", "60G"]},
    )

    reference = VisualEvidenceService.reference_from_product_asset(asset)

    assert reference.source_ref == "product_asset:91"
    assert reference.required_tokens == ["BOMBBAR", "60G"]
    assert reference.declared_text is None
    assert reference.asset_path == path.as_posix()


def test_local_product_asset_ocr_is_compared_to_frame_ocr(tmp_path: Path):
    reference_path = make_frame(tmp_path / "reference.png", (240, 240, 240))
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    asset = SimpleNamespace(
        id=92,
        source_type="local",
        source_ref=reference_path.as_posix(),
        metadata_json={},
    )
    backend = FakeOCR(
        {
            "reference.png": "BOMBBAR 60G",
            "frame-1.png": "BOMBBAR",
            "frame-2.png": "60G",
        }
    )

    report = VisualEvidenceService(ocr_backend=backend).evaluate(
        frames,
        references=[VisualEvidenceService.reference_from_product_asset(asset)],
    )

    assert report.status == "passed"
    assert report.ocr.expected_tokens == ["bombbar", "60g"]
    assert report.ocr.matched_tokens == ["bombbar", "60g"]
    assert backend.calls == ["reference.png", "frame-1.png", "frame-2.png"]


def test_remote_product_asset_is_not_downloaded_or_treated_as_evidence(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    asset = SimpleNamespace(
        id=93,
        source_type="url",
        source_ref="https://example.test/signed-product-image.png?token=secret",
        metadata_json={},
    )
    backend = FakeOCR({"frame-1.png": "BOMBBAR", "frame-2.png": "60G"})

    report = VisualEvidenceService(ocr_backend=backend).evaluate(
        frames,
        references=[VisualEvidenceService.reference_from_product_asset(asset)],
    )

    assert report.status == "blocked"
    assert "ocr_reference_evidence_missing" in report.blockers
    assert backend.calls == []


def test_output_quality_checker_exposes_visual_evidence_and_blocks_ocr_mismatch(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    backend = FakeOCR({"frame-1.png": "BOMBBAR", "frame-2.png": "wrong size"})
    checker = OutputQualityChecker(VisualEvidenceService(ocr_backend=backend))
    frame_result = SimpleNamespace(
        contact_sheet_path="contact-sheet.png",
        frame_paths_json=[path.as_posix() for path in frames],
        warnings_json=[],
    )
    brief = SimpleNamespace(
        scene_blueprints=[{"scene_number": 1}],
        product_identity_rules_json={
            "visual_evidence_contract": {
                "ocr_required": True,
                "required_packaging_tokens": ["BOMBBAR", "60G"],
            }
        },
    )

    result = checker.check(
        video_job=SimpleNamespace(output_video_path="real.mp4", provider="runway"),
        brief=brief,
        frame_result=frame_result,
        decision="approve",
        product_identity_status="pass",
        packaging_status="pass",
        geometry_status="pass",
        blogger_authenticity_status="pass",
        scene_match_status="pass",
        proof_moment_status="pass",
        cta_status="pass",
    )

    assert result.visual_evidence is not None
    assert result.visual_evidence.ocr.missing_tokens == ["60g"]
    assert "ocr_reference_tokens_missing_from_frames" in result.blockers
    assert result.status == "needs_regeneration"
    assert result.publishing_readiness == "blocked"


def test_evaluate_latest_uses_latest_frame_result_contract(tmp_path: Path):
    frames = [
        make_frame(tmp_path / "frame-1.png", (180, 20, 20)),
        make_frame(tmp_path / "frame-2.png", (20, 150, 40)),
    ]
    latest = SimpleNamespace(frame_paths_json=[path.as_posix() for path in frames])

    class FakeDb:
        def scalar(self, _statement):
            return latest

    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate_latest(FakeDb(), 123)

    assert report.status == "passed"
    assert report.frame_count == 2

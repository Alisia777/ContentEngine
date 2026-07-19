from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / "web/app/training-practical-review.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/training-practical-review.css").read_text(encoding="utf-8")


def _run(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "view.mjs").write_text(VIEW, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as view from './view.mjs';\n"
            f"const output = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(output));\n",
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
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_project_normalization_rejects_unsafe_urls_and_marks_legacy_approval() -> None:
    payload = _run(
        """
        const unsafe = view.normalizeTrainingPracticalProject({
          status: 'submitted',
          platform: 'youtube',
          evidence_url: 'https://user:secret@example.com/video',
          media: { id: '9bb89ad2-5350-4a35-bdb6-220f222d0205', object_key: 'org/user/trial.mp4' },
        });
        const legacy = view.normalizeTrainingPracticalProject({
          status: 'approved', is_grandfathered: true,
        });
        return { unsafe, legacy };
        """
    )
    assert payload["unsafe"]["evidenceUrl"] == ""
    assert payload["unsafe"]["media"]["objectKey"] == "org/user/trial.mp4"
    assert payload["legacy"]["status"] == "grandfathered"
    assert payload["legacy"]["approved"] is True


def test_gate_requires_courses_then_manager_approval_then_exam() -> None:
    payload = _run(
        """
        return {
          courses: view.trainingPracticalGateSnapshot({ status: 'not_started' }),
          practical: view.trainingPracticalGateSnapshot({ status: 'changes_requested' }, { coursesComplete: true }),
          review: view.trainingPracticalGateSnapshot({ status: 'submitted' }, { coursesComplete: true }),
          exam: view.trainingPracticalGateSnapshot({ status: 'approved' }, { coursesComplete: true }),
          done: view.trainingPracticalGateSnapshot({ status: 'approved' }, { coursesComplete: true, examPassed: true }),
        };
        """
    )
    assert payload["courses"]["nextStep"] == "courses"
    assert payload["practical"]["nextStep"] == "practical"
    assert payload["review"]["nextStep"] == "manager_review"
    assert payload["exam"]["readyForExam"] is True
    assert payload["exam"]["nextStep"] == "exam"
    assert payload["done"]["nextStep"] == "done"


def test_learner_and_manager_markup_are_explicit_and_accessible() -> None:
    payload = _run(
        """
        const learner = view.trainingPracticalProjectMarkup({ status: 'changes_requested', review_note: 'Уберите неподтверждённое обещание результата.', version: 3 });
        const queue = view.trainingPracticalReviewQueueMarkup([{ id: '9bb89ad2-5350-4a35-bdb6-220f222d0205', status: 'submitted', learner_name: 'Михаил', learner_email: 'm@example.com', platform: 'vk', object_key: 'org/user/trial.mp4', version: 2 }]);
        return { learner, queue };
        """
    )
    learner = payload["learner"]
    queue = payload["queue"]
    assert 'id="training-practical-submit-form"' in learner
    assert 'accept="video/mp4"' in learner
    assert 'name="self_check"' in learner
    assert "Что исправить" in learner
    assert 'aria-labelledby="training-practical-title"' in learner
    assert 'data-action="open-training-practical-media"' in queue
    assert 'value="approve"' in queue
    assert 'value="request_changes"' in queue
    assert 'name="media_watched_confirmed"' in queue


def test_external_url_can_be_reviewed_but_cannot_receive_final_approval() -> None:
    payload = _run(
        """
        const external = view.trainingPracticalReviewQueueMarkup([{
          id: '9bb89ad2-5350-4a35-bdb6-220f222d0205', status: 'submitted',
          learner_name: 'Михаил', learner_email: 'm@example.com', platform: 'vk',
          evidence_url: 'https://example.com/trial.mp4', version: 2,
        }]);
        const protectedFile = view.trainingPracticalReviewQueueMarkup([{
          id: 'a2cdcb2a-2a2b-4a91-8ef9-a1b2c3d4e5f6', status: 'submitted',
          learner_name: 'Анна', learner_email: 'a@example.com', platform: 'instagram',
          media: {
            id: 'b3decb2a-2a2b-4a91-8ef9-a1b2c3d4e5f6',
            object_key: 'org/user/practical/trial.mp4', filename: 'trial.mp4',
          }, version: 1,
        }]);
        return { external, protectedFile };
        """
    )
    assert "Для финального принятия попросите участника загрузить MP4" in payload["external"]
    assert 'value="approve" disabled aria-disabled="true"' in payload["external"]
    assert 'data-practical-evidence-kind="private_file"' in payload["protectedFile"]
    assert 'value="approve" disabled' not in payload["protectedFile"]
    assert "Финально принять можно только защищённый MP4" in payload["protectedFile"]


def test_styles_cover_responsive_focus_and_reduced_motion_states() -> None:
    for token in (
        ".training-practical",
        ".training-practical-review",
        ".training-practical-review__immutable-note",
        ".training-practical-queue__empty",
        "@media (max-width: 640px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert token in STYLES

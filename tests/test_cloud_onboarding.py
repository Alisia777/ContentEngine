from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.novice_learning_path import NoviceLearningPathService
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import ensure_public_pilot_user
from app.public_pilot.onboarding import safe_workspace_next, workspace_home_for_role
from app.public_pilot.training_catalog import (
    ONBOARDING_EXAM_CODE,
    ONBOARDING_PREREQUISITE_CODES,
    PUBLIC_PILOT_TRAINING_MODULES,
)


@pytest.fixture(autouse=True)
def cloud_onboarding_database():
    keys = (
        "QVF_AUTH_REQUIRED",
        "QVF_PUBLIC_PILOT_MODE",
        "QVF_PUBLIC_PILOT_INVITE_ONLY",
        "QVF_SUPABASE_JWT_SECRET",
        "QVF_SUPABASE_ISSUER",
        "QVF_SUPABASE_AUDIENCE",
    )
    previous = {key: os.environ.get(key) for key in keys}
    os.environ["QVF_AUTH_REQUIRED"] = "true"
    os.environ["QVF_PUBLIC_PILOT_MODE"] = "true"
    os.environ["QVF_PUBLIC_PILOT_INVITE_ONLY"] = "true"
    os.environ["QVF_SUPABASE_JWT_SECRET"] = "cloud-onboarding-test-secret"
    os.environ.pop("QVF_SUPABASE_ISSUER", None)
    os.environ["QVF_SUPABASE_AUDIENCE"] = "authenticated"
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _token(subject: str, *, role: str = "producer") -> str:
    def encode(value: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")

    now = int(time.time())
    header = encode({"alg": "HS256", "typ": "JWT"})
    payload = encode(
        {
            "sub": subject,
            "email": f"{subject}@example.test",
            "aud": "authenticated",
            "iat": now,
            "exp": now + 600,
            "app_metadata": {"role": role},
        }
    )
    signature = base64.urlsafe_b64encode(
        hmac.new(
            b"cloud-onboarding-test-secret",
            f"{header}.{payload}".encode("ascii"),
            hashlib.sha256,
        ).digest()
    ).decode("ascii").rstrip("=")
    return f"{header}.{payload}.{signature}"


def _invite(subject: str = "cloud-creator") -> tuple[int, int]:
    with SessionLocal() as db:
        user = ensure_public_pilot_user(
            db,
            email=f"{subject}@example.test",
            display_name="Cloud Creator",
            role="producer",
            supabase_user_id=subject,
        )
        PublicPilotAccessService(db).ensure_training_catalog()
        return user.profile.id, user.organization.id


def _correct_answers(db, module_code: str) -> dict[str, object]:
    module = db.scalar(
        select(models.TrainingModule).where(models.TrainingModule.code == module_code)
    )
    assert module is not None
    return {
        str(question.id): (
            list(question.correct_answer_json)
            if question.question_type == "multi_select"
            else question.correct_answer_json[0]
        )
        for question in module.questions
    }


def test_creator_workspace_default_is_generation_but_management_keeps_control_room():
    generation = "/creator-operations?tab=generation"
    assert workspace_home_for_role("producer") == generation
    assert workspace_home_for_role(" PRODUCER ") == generation
    assert workspace_home_for_role("owner") == "/control-room"
    assert workspace_home_for_role("admin") == "/control-room"
    assert safe_workspace_next(None, role="producer") == generation
    assert safe_workspace_next("https://attacker.test", role="producer") == generation
    assert safe_workspace_next("/\\attacker.test", role="producer") == generation
    assert safe_workspace_next("/%5c%5cattacker.test", role="producer") == generation
    assert safe_workspace_next("/%255c%255cattacker.test", role="producer") == generation
    assert safe_workspace_next("/%2f%2fattacker.test", role="producer") == generation
    assert safe_workspace_next("/control-room", role="producer") == "/control-room"


def test_versioned_catalog_has_complex_exam_and_deactivates_stale_modules():
    exam = next(
        item for item in PUBLIC_PILOT_TRAINING_MODULES if item["code"] == ONBOARDING_EXAM_CODE
    )
    assert len(exam["questions"]) >= 12
    assert set(ONBOARDING_PREREQUISITE_CODES).issubset(
        {item["code"] for item in PUBLIC_PILOT_TRAINING_MODULES}
    )
    with SessionLocal() as db:
        db.add(models.TrainingModule(code="removed_legacy_module", title="Removed", is_active=True))
        db.commit()
        PublicPilotAccessService(db).ensure_training_catalog()
        stale = db.scalar(
            select(models.TrainingModule).where(
                models.TrainingModule.code == "removed_legacy_module"
            )
        )
        assert stale is not None and stale.is_active is False


def test_every_authenticated_profile_is_redirected_until_final_exam_passes():
    profile_id, _ = _invite()
    headers = {"authorization": f"Bearer {_token('cloud-creator')}"}
    with TestClient(app, follow_redirects=False) as client:
        workspace = client.get("/control-room", headers=headers)
        assert workspace.status_code == 303
        assert workspace.headers["location"].startswith("/onboarding?next=")

        api = client.get("/api/factory-dashboard", headers=headers)
        assert api.status_code == 403
        assert api.json()["detail"] == "onboarding_required"

        onboarding = client.get("/onboarding", headers=headers)
        assert onboarding.status_code == 200
        assert "Итоговый экзамен оператора портала" in onboarding.text
        assert "12 сценариев" in onboarding.text

    with SessionLocal() as db:
        assert ONBOARDING_EXAM_CODE not in NoviceLearningPathService(
            db
        ).verified_certification_codes(user_profile_id=profile_id)


def test_exam_requires_courses_then_certificate_opens_workspace_and_navigation():
    profile_id, organization_id = _invite()
    token = _token("cloud-creator")
    headers = {"authorization": f"Bearer {token}"}

    with SessionLocal() as db:
        learning = NoviceLearningPathService(db)
        for module_code in ONBOARDING_PREREQUISITE_CODES:
            result = learning.submit_quiz(
                user_profile_id=profile_id,
                organization_id=organization_id,
                module_code=module_code,
                answers=_correct_answers(db, module_code),
            )
            assert result.passed

    with TestClient(app, follow_redirects=False) as client:
        page = client.get(
            f"/onboarding?module={ONBOARDING_EXAM_CODE}", headers=headers
        )
        assert page.status_code == 200
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        assert csrf

        with SessionLocal() as db:
            answers = _correct_answers(db, ONBOARDING_EXAM_CODE)
        data: dict[str, object] = {
            "csrf_token": csrf.group(1),
        }
        for question_id, answer in answers.items():
            data[f"answer_{question_id}"] = answer
        passed = client.post(
            f"/onboarding/modules/{ONBOARDING_EXAM_CODE}/submit",
            headers=headers,
            data=data,
        )
        assert passed.status_code == 303
        assert passed.headers["location"] == "/creator-operations?tab=generation"

        workspace = client.get(
            "/creator-operations?tab=generation",
            headers=headers,
        )
        assert workspace.status_code == 200
        for label in (
            "Генерация",
            "Размещение",
            "Статистика",
            "Выплаты",
            "Задачи",
            "Что добавить",
        ):
            assert label in workspace.text

    with SessionLocal() as db:
        assert ONBOARDING_EXAM_CODE in NoviceLearningPathService(
            db
        ).verified_certification_codes(user_profile_id=profile_id)

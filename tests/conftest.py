from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid


# This file is loaded before test-module imports.  A module that imports
# app.database early therefore cannot accidentally bind SQLAlchemy to the
# workspace's qharisma.db before another module sets its own test URL.
_TEST_RUN_ID = f"{os.getpid()}-{uuid.uuid4().hex}"
_TEST_DATABASE = (
    Path(tempfile.gettempdir())
    / f"qvf-pytest-{_TEST_RUN_ID}.db"
)
_TEST_MEDIA_ROOT = Path(tempfile.gettempdir()) / f"qvf-pytest-media-{_TEST_RUN_ID}"
os.environ["QVF_DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE.as_posix()}"
os.environ["QVF_MEDIA_ROOT"] = str(_TEST_MEDIA_ROOT)
# Keep repository tests hermetic even when the developer has a local, ignored
# `.env` for the running pilot.  Individual tests can still monkeypatch these.
os.environ["QVF_AUTH_REQUIRED"] = "false"
os.environ["QVF_PUBLIC_PILOT_MODE"] = "false"
os.environ["QVF_PUBLIC_PILOT_INVITE_ONLY"] = "false"
os.environ["QVF_PUBLIC_PILOT_DEFAULT_ORG"] = "ALTEA Beauty"
os.environ["QVF_GENERATION_MODE"] = "mock"
os.environ["QVF_ALLOW_REAL_SPEND"] = "false"
os.environ["QVF_LLM_PROVIDER"] = "mock"
os.environ["QVF_VIDEO_PROVIDER"] = "mock"
os.environ["QVF_MOCK_PROVIDER_ENABLED"] = "true"

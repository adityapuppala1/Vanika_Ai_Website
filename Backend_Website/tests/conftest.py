import os
import sys
from pathlib import Path

import pytest

# Settings are read at import time, so configure the environment first.
os.environ["CORS_ORIGINS"] = "https://vanika.ai, https://www.vanika.ai"
os.environ["VANIKA_ROUTES_KEY"] = "public-key"
os.environ["VANIKA_ADMIN_KEY"] = "admin-secret"
os.environ["MONGODB_URI"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

import main  # noqa: E402
from Vanika_Mailing import routes  # noqa: E402
from Vanika_Mailing.security import admin_failure_limiter, subscribe_limiter  # noqa: E402
from Vanika_Mailing.waitlist import WaitlistRepository  # noqa: E402


class EmailRecorder:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def __call__(self, subject, html, to=None, onlySender=False, **kwargs):
        self.sent.append({"subject": subject, "html": html, "to": to, "onlySender": onlySender})
        if self.fail:
            return {"status": "error", "message": "ACS down"}
        return {"status": "success", "id": "test"}


@pytest.fixture
def emails(monkeypatch):
    recorder = EmailRecorder()
    monkeypatch.setattr(routes, "send_email", recorder)
    return recorder


@pytest.fixture
def repo():
    collection = AsyncMongoMockClient()["test_db"]["VanikaWaitlist"]
    return WaitlistRepository(collection)


@pytest.fixture
def client(repo, emails):
    subscribe_limiter.reset()
    admin_failure_limiter.reset()
    routes._indexes_ready = False
    main.app.dependency_overrides[routes.get_waitlist] = lambda: repo
    yield TestClient(main.app, raise_server_exceptions=False)
    main.app.dependency_overrides.clear()


@pytest.fixture
def client_without_db(emails):
    subscribe_limiter.reset()
    main.app.dependency_overrides[routes.get_waitlist] = lambda: None
    yield TestClient(main.app, raise_server_exceptions=False)
    main.app.dependency_overrides.clear()

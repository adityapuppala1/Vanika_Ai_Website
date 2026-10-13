import base64
import os
import sys
from pathlib import Path

import pytest

# Settings are read at import time, so configure the environment first.
TEST_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()
os.environ["CORS_ORIGINS"] = "https://vanika.ai, https://www.vanika.ai"
os.environ["VANIKA_ROUTES_KEY"] = "public-key"
os.environ["VANIKA_ADMIN_KEY"] = "admin-secret"
os.environ["VANIKA_ENCRYPTION_KEY"] = TEST_KEY
os.environ["MONGODB_URI"] = ""
os.environ["SMTP_PASSWORD"] = ""
os.environ["TURNSTILE_SECRET_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

import main  # noqa: E402
from Vanika_Mailing import routes  # noqa: E402
from Vanika_Mailing.crypto import EmailCipher  # noqa: E402
from Vanika_Mailing.email_policy import EmailPolicy  # noqa: E402
from Vanika_Mailing.security import admin_failure_limiter, subscribe_limiter  # noqa: E402
from Vanika_Mailing.waitlist import WaitlistRepository  # noqa: E402

# Domains the fake resolver treats as unable to receive mail
UNDELIVERABLE = {"no-mx-here.dev", "example.com"}


def fake_deliverability(email, domain):
    return domain not in UNDELIVERABLE


class EmailRecorder:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def __call__(self, subject, html, to=None, bcc=None, reply_to=None):
        self.sent.append({"subject": subject, "html": html, "to": to, "bcc": bcc, "reply_to": reply_to})
        if self.fail:
            return {"status": "error", "message": "SMTP down"}
        return {"status": "success", "transport": "test"}


@pytest.fixture(autouse=True)
def offline_policy(monkeypatch):
    monkeypatch.setattr(routes, "email_policy", EmailPolicy(deliverability=fake_deliverability))


@pytest.fixture
def emails(monkeypatch):
    recorder = EmailRecorder()
    monkeypatch.setattr(routes, "send_mail", recorder)
    return recorder


@pytest.fixture
def cipher():
    return EmailCipher(TEST_KEY)


@pytest.fixture
def repo(cipher):
    collection = AsyncMongoMockClient()["test_db"]["VanikaWaitlist"]
    return WaitlistRepository(collection, cipher)


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

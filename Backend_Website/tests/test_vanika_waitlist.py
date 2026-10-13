import asyncio

ORIGIN = {"Origin": "https://vanika.ai"}
ADMIN = {"X-Admin-Key": "admin-secret"}


def subscribe(client, email="Ada@Example.com", source="hero", **extra):
    data = {"clientemail": email, "accesskey": "public-key", "source": source, **extra}
    return client.post("/vanika/subscribe", data=data, headers=ORIGIN)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------
# Sign-up
# ---------------------------------------------------------
def test_new_signup_is_stored_and_emails_sent(client, repo, emails):
    r = subscribe(client, utm_source="twitter", referrer="https://news.ycombinator.com/")
    assert r.status_code == 200
    assert r.json() == {"status": "Success", "message": "You're on the list.", "alreadySubscribed": False}

    doc = run(repo.collection.find_one({"email": "ada@example.com"}))
    assert doc["first_source"] == "hero"
    assert doc["signup_count"] == 1
    assert doc["metadata"]["utm_source"] == "twitter"
    assert doc["email_status"] == {"admin": "sent", "user": "sent"}

    admin_mail, user_mail = emails.sent
    assert admin_mail["to"] is None and "ada@example.com" in admin_mail["subject"]
    assert "Waitlist size:</span> 1" in admin_mail["html"]
    assert user_mail["to"] == "ada@example.com" and user_mail["onlySender"] is True


def test_repeat_signup_is_deduplicated_and_not_re_emailed(client, repo, emails):
    subscribe(client, source="hero")
    r = subscribe(client, email="  ADA@example.com ", source="final_cta")

    assert r.status_code == 200
    assert r.json()["alreadySubscribed"] is True
    assert run(repo.collection.count_documents({})) == 1
    doc = run(repo.collection.find_one({"email": "ada@example.com"}))
    assert doc["signup_count"] == 2
    assert sorted(doc["sources"]) == ["final_cta", "hero"]
    assert len(emails.sent) == 2  # only the first sign-up sent mail


def test_invalid_email_is_rejected(client, repo, emails):
    r = subscribe(client, email="not-an-email<script>")
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_EMAIL"
    assert run(repo.collection.count_documents({})) == 0
    assert emails.sent == []


def test_wrong_access_key_is_forbidden(client):
    r = client.post("/vanika/subscribe", data={"clientemail": "a@b.co", "accesskey": "nope"}, headers=ORIGIN)
    assert r.status_code == 403
    assert r.json()["code"] == "INVALID_ACCESS_KEY"


def test_honeypot_fakes_success_without_storing(client, repo, emails):
    r = subscribe(client, website="http://spam.example")
    assert r.status_code == 200 and r.json()["status"] == "Success"
    assert run(repo.collection.count_documents({})) == 0
    assert emails.sent == []


def test_rate_limit(client):
    codes = [subscribe(client, email=f"user{i}@example.com").status_code for i in range(6)]
    assert codes == [200, 200, 200, 200, 200, 429]


def test_admin_email_escapes_html():
    from Vanika_Mailing.email_templates import vanika_subscribe_admin

    html = vanika_subscribe_admin('"<img src=x onerror=alert(1)>"@example.com', source="<b>hero</b>")
    assert "<img src=x" not in html and "<b>hero</b>" not in html


def test_failed_email_is_recorded(client, repo, emails):
    emails.fail = True
    r = subscribe(client)
    assert r.status_code == 200
    doc = run(repo.collection.find_one({"email": "ada@example.com"}))
    assert doc["email_status"] == {"admin": "failed", "user": "failed"}
    assert "ACS down" in doc["email_error"]


def test_signup_without_database_still_notifies_admin(client_without_db, emails):
    r = subscribe(client_without_db)
    assert r.status_code == 200
    assert "could not be saved" in emails.sent[0]["html"]


# ---------------------------------------------------------
# CORS firewall
# ---------------------------------------------------------
def test_origin_with_whitespace_in_config_is_allowed(client):
    r = client.post(
        "/vanika/subscribe",
        data={"clientemail": "a@b.co", "accesskey": "public-key"},
        headers={"Origin": "https://www.vanika.ai"},
    )
    assert r.status_code == 200


def test_unknown_origin_gets_403_not_500(client):
    r = client.post(
        "/vanika/subscribe",
        data={"clientemail": "a@b.co", "accesskey": "public-key"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------
# Admin API
# ---------------------------------------------------------
def test_admin_requires_key(client):
    assert client.get("/vanika/admin/stats", headers=ORIGIN).status_code == 401
    assert client.get("/vanika/admin/stats", headers={**ORIGIN, "X-Admin-Key": "wrong"}).status_code == 401


def test_admin_lockout_blocks_even_correct_key(client):
    for _ in range(10):
        client.get("/vanika/admin/stats", headers={**ORIGIN, "X-Admin-Key": "wrong"})
    assert client.get("/vanika/admin/stats", headers={**ORIGIN, **ADMIN}).status_code == 429


def test_admin_stats(client):
    subscribe(client, email="a@example.com", source="hero")
    subscribe(client, email="b@example.com", source="final_cta")
    subscribe(client, email="c@example.com", source="hero")

    r = client.get("/vanika/admin/stats", headers={**ORIGIN, **ADMIN})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["today"] == 3 and body["last7Days"] == 3
    assert body["bySource"] == {"hero": 2, "final_cta": 1}
    assert len(body["daily"]) == 30 and body["daily"][-1]["count"] == 3


def test_admin_list_search_and_paginate(client):
    for name in ["alice", "bob", "alina"]:
        subscribe(client, email=f"{name}@example.com")

    r = client.get("/vanika/admin/subscribers", params={"search": "ali"}, headers={**ORIGIN, **ADMIN})
    assert r.status_code == 200
    assert {i["email"] for i in r.json()["items"]} == {"alice@example.com", "alina@example.com"}

    page = client.get("/vanika/admin/subscribers", params={"limit": 2}, headers={**ORIGIN, **ADMIN}).json()
    assert page["total"] == 3 and len(page["items"]) == 2


def test_admin_search_treats_input_as_literal_text(client):
    subscribe(client, email="a@example.com")
    r = client.get("/vanika/admin/subscribers", params={"search": ".*"}, headers={**ORIGIN, **ADMIN})
    assert r.json()["total"] == 0


def test_admin_export_csv(client):
    subscribe(client, email="a@example.com")
    r = client.get("/vanika/admin/subscribers/export.csv", headers={**ORIGIN, **ADMIN})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("email,createdAt")
    assert lines[1].startswith("a@example.com,")


def test_admin_delete(client, repo):
    subscribe(client, email="a@example.com")
    assert client.delete("/vanika/admin/subscribers/A@example.com", headers={**ORIGIN, **ADMIN}).status_code == 200
    assert run(repo.collection.count_documents({})) == 0
    assert client.delete("/vanika/admin/subscribers/a@example.com", headers={**ORIGIN, **ADMIN}).status_code == 404


def test_admin_without_database_reports_unavailable(client_without_db):
    r = client_without_db.get("/vanika/admin/stats", headers={**ORIGIN, **ADMIN})
    assert r.status_code == 503


def test_unique_email_index_is_created_on_first_signup(client, repo):
    subscribe(client)
    indexes = run(repo.collection.index_information())
    assert any(ix.get("unique") and ix["key"] == [("email", 1)] for ix in indexes.values())


def test_rate_limit_cannot_be_bypassed_by_spoofing_forwarded_for(client):
    codes = []
    for i in range(6):
        r = client.post(
            "/vanika/subscribe",
            data={"clientemail": f"spoof{i}@example.com", "accesskey": "public-key"},
            # client-chosen first entry, Azure-appended real address last
            headers={**ORIGIN, "X-Forwarded-For": f"10.0.0.{i}, 1.2.3.4:5555"},
        )
        codes.append(r.status_code)
    assert codes[-1] == 429


def test_rate_limiter_memory_is_bounded(monkeypatch):
    from Vanika_Mailing.security import RateLimiter

    limiter = RateLimiter(max_requests=1, window_seconds=0)
    monkeypatch.setattr(RateLimiter, "MAX_KEYS", 50)
    for i in range(500):
        limiter.allow(f"10.0.{i // 256}.{i % 256}")
    assert len(limiter._hits) <= 51
    assert limiter.is_limited("never-seen") is False and "never-seen" not in limiter._hits

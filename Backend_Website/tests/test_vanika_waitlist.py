import asyncio

ORIGIN = {"Origin": "https://vanika.ai"}
ADMIN = {"X-Admin-Key": "admin-secret"}


def subscribe(client, email="Ada@Robotics.dev", source="hero", **extra):
    data = {"clientemail": email, "accesskey": "public-key", "source": source, **extra}
    return client.post("/vanika/subscribe", data=data, headers=ORIGIN)


def run(coro):
    return asyncio.run(coro)


def find(repo, email):
    return run(repo.collection.find_one({"email_hash": repo.cipher.blind_index(email)}))


# ---------------------------------------------------------
# Sign-up
# ---------------------------------------------------------
def test_new_signup_is_stored_encrypted_and_emails_sent(client, repo, emails):
    r = subscribe(client, utm_source="twitter", referrer="https://news.ycombinator.com/")
    assert r.status_code == 200
    assert r.json() == {"status": "Success", "message": "You're on the list.", "alreadySubscribed": False}

    doc = find(repo, "ada@robotics.dev")
    # The address itself is never stored in plaintext
    assert "email" not in doc
    assert "ada@robotics.dev" not in str(doc)
    assert repo.cipher.decrypt(doc["email_enc"], doc["email_hash"]) == "ada@robotics.dev"
    assert doc["email_domain"] == "robotics.dev" and doc["email_type"] == "work"
    assert doc["first_source"] == "hero" and doc["signup_count"] == 1
    assert doc["metadata"]["utm_source"] == "twitter"
    assert doc["email_status"] == {"admin": "sent", "user": "sent"}

    team_mail, welcome_mail = emails.sent
    assert team_mail["to"] is None  # -> team inbox (info@vanika.ai)
    assert "ada@robotics.dev" in team_mail["subject"] and team_mail["reply_to"] == "ada@robotics.dev"
    assert "Waitlist size:</span> 1" in team_mail["html"] and "Work" in team_mail["html"]
    assert welcome_mail["to"] == "ada@robotics.dev" and not welcome_mail["bcc"]


def test_repeat_signup_is_deduplicated_and_not_re_emailed(client, repo, emails):
    subscribe(client, source="hero")
    r = subscribe(client, email="  ADA@robotics.dev ", source="final_cta")

    assert r.status_code == 200
    assert r.json()["alreadySubscribed"] is True
    assert run(repo.collection.count_documents({})) == 1
    doc = find(repo, "ada@robotics.dev")
    assert doc["signup_count"] == 2
    assert sorted(doc["sources"]) == ["final_cta", "hero"]
    assert len(emails.sent) == 2  # only the first sign-up sent mail


def test_ciphertext_differs_per_record_even_for_same_plaintext(cipher):
    assert cipher.encrypt("a@b.dev") != cipher.encrypt("a@b.dev")
    assert cipher.blind_index("a@b.dev") == cipher.blind_index("a@b.dev")


def test_wrong_access_key_is_forbidden(client):
    r = client.post("/vanika/subscribe", data={"clientemail": "a@b.dev", "accesskey": "nope"}, headers=ORIGIN)
    assert r.status_code == 403
    assert r.json()["code"] == "INVALID_ACCESS_KEY"


def test_honeypot_fakes_success_without_storing(client, repo, emails):
    r = subscribe(client, website="http://spam.example")
    assert r.status_code == 200 and r.json()["status"] == "Success"
    assert run(repo.collection.count_documents({})) == 0
    assert emails.sent == []


def test_rate_limit(client):
    codes = [subscribe(client, email=f"user{i}@robotics.dev").status_code for i in range(6)]
    assert codes == [200, 200, 200, 200, 200, 429]


def test_admin_email_escapes_html():
    from Vanika_Mailing.email_templates import vanika_subscribe_admin

    html = vanika_subscribe_admin('"<img src=x onerror=alert(1)>"@robotics.dev', source="<b>hero</b>")
    assert "<img src=x" not in html and "<b>hero</b>" not in html


def test_failed_email_is_recorded(client, repo, emails):
    emails.fail = True
    r = subscribe(client)
    assert r.status_code == 200
    doc = find(repo, "ada@robotics.dev")
    assert doc["email_status"] == {"admin": "failed", "user": "failed"}
    assert "SMTP down" in doc["email_error"]


def test_signup_without_storage_still_notifies_team(client_without_db, emails):
    r = subscribe(client_without_db)
    assert r.status_code == 200
    assert "could not be saved" in emails.sent[0]["html"]


# ---------------------------------------------------------
# Email policy (spam protection)
# ---------------------------------------------------------
def test_accepts_work_school_and_known_personal_addresses(client, repo):
    for email, kind in [
        ("priya@tata-robotics.com", "work"),
        ("student@iitb.ac.in", "education"),
        ("ravi@stanford.edu", "education"),
        ("someone@gmail.com", "personal"),
    ]:
        assert subscribe(client, email=email).status_code == 200, email
        assert find(repo, email)["email_type"] == kind


def test_rejects_disposable_addresses(client, repo, emails):
    for email in ["bot@mailinator.com", "x@sub.mailinator.com", "temp@yopmail.com"]:
        r = subscribe(client, email=email)
        assert r.status_code == 422 and r.json()["code"] == "DISPOSABLE_EMAIL", email
    assert run(repo.collection.count_documents({})) == 0 and emails.sent == []


def test_rejects_typo_with_suggestion(client):
    r = subscribe(client, email="ada@gmial.com")
    assert r.status_code == 422
    assert r.json()["code"] == "EMAIL_TYPO" and r.json()["suggestion"] == "ada@gmail.com"
    assert subscribe(client, email="ada@gmail.con").json()["suggestion"] == "ada@gmail.com"


def test_rejects_no_reply_and_undeliverable(client):
    assert subscribe(client, email="noreply@robotics.dev").json()["code"] == "ROLE_EMAIL"
    assert subscribe(client, email="ada@no-mx-here.dev").json()["code"] == "UNDELIVERABLE_DOMAIN"


def test_rejects_malformed(client):
    r = subscribe(client, email="not-an-email<script>")
    assert r.status_code == 422 and r.json()["code"] == "INVALID_EMAIL"


def test_work_or_school_policy_rejects_personal(monkeypatch, client):
    from Vanika_Mailing import routes
    from Vanika_Mailing.email_policy import EmailPolicy
    from tests.conftest import fake_deliverability

    monkeypatch.setattr(routes, "email_policy", EmailPolicy("work_or_school", deliverability=fake_deliverability))
    assert subscribe(client, email="someone@gmail.com").json()["code"] == "PERSONAL_EMAIL_NOT_ALLOWED"
    assert subscribe(client, email="student@ox.ac.uk").status_code == 200


def test_well_known_domains_are_not_flagged_as_typos():
    from Vanika_Mailing.email_policy import typo_suggestion

    for domain in ["gmail.com", "email.com", "mail.com", "ymail.com", "outlook.in", "tata.com",
                   "cloud.com", "yahoo.co.id", "yahoo.co.jp", "yahoo.co.il", "hotmail.fr"]:
        assert typo_suggestion(domain) is None, domain


def test_visitor_can_keep_an_address_flagged_as_typo(client, repo):
    assert subscribe(client, email="ada@outlok.com").json()["code"] == "EMAIL_TYPO"
    r = subscribe(client, email="ada@outlok.com", keep_email="1")
    assert r.status_code == 200
    assert find(repo, "ada@outlok.com") is not None


def test_idn_disposable_domain_is_blocked(client):
    from Vanika_Mailing.email_policy import DISPOSABLE_DOMAINS

    idn = next(d for d in sorted(DISPOSABLE_DOMAINS) if d.startswith("xn--"))
    r = subscribe(client, email=f"a@{idn}")
    assert r.json()["code"] == "DISPOSABLE_EMAIL"


def test_legacy_plaintext_records_are_encrypted_on_startup(repo):
    run(repo.collection.insert_many([
        {"email": "old1@robotics.dev", "first_source": "hero", "signup_count": 1},
        {"email": "old2@robotics.dev", "first_source": "hero", "signup_count": 1},
    ]))
    run(repo.ensure_indexes())
    docs = run(repo.collection.find({}).to_list(10))
    assert len(docs) == 2 and all("email" not in d for d in docs)
    assert sorted(repo._email(d) for d in docs) == ["old1@robotics.dev", "old2@robotics.dev"]


def test_ciphertext_swapped_between_records_is_detected(client, repo):
    subscribe(client, email="a@robotics.dev")
    subscribe(client, email="b@robotics.dev")
    a, b = find(repo, "a@robotics.dev"), find(repo, "b@robotics.dev")
    run(repo.collection.update_one({"_id": a["_id"]}, {"$set": {"email_enc": b["email_enc"]}}))
    assert repo._email(find(repo, "a@robotics.dev")).startswith("(cannot decrypt")


# ---------------------------------------------------------
# Bot check (Turnstile)
# ---------------------------------------------------------
def test_turnstile_required_when_configured(monkeypatch, client, repo):
    from config import settings
    from Vanika_Mailing import security

    monkeypatch.setattr(settings, "TURNSTILE_SECRET_KEY", "secret")

    async def fake_verify(token, ip):
        return token == "good-token"

    monkeypatch.setattr(security, "verify_turnstile", fake_verify)
    from Vanika_Mailing import routes
    monkeypatch.setattr(routes, "verify_turnstile", fake_verify)

    assert subscribe(client).json()["code"] == "BOT_CHECK_FAILED"
    assert subscribe(client, **{"cf-turnstile-response": "good-token"}).status_code == 200


# ---------------------------------------------------------
# CORS firewall
# ---------------------------------------------------------
def test_origin_with_whitespace_in_config_is_allowed(client):
    r = client.post(
        "/vanika/subscribe",
        data={"clientemail": "a@b.dev", "accesskey": "public-key"},
        headers={"Origin": "https://www.vanika.ai"},
    )
    assert r.status_code == 200


def test_unknown_origin_gets_403_not_500(client):
    r = client.post(
        "/vanika/subscribe",
        data={"clientemail": "a@b.dev", "accesskey": "public-key"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_responses_carry_hsts(client):
    r = client.get("/vanika/ping")
    assert "max-age=31536000" in r.headers["strict-transport-security"]


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
    subscribe(client, email="a@robotics.dev", source="hero")
    subscribe(client, email="b@iitd.ac.in", source="final_cta")
    subscribe(client, email="c@gmail.com", source="hero")

    r = client.get("/vanika/admin/stats", headers={**ORIGIN, **ADMIN})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and body["today"] == 3 and body["last7Days"] == 3
    assert body["bySource"] == {"hero": 2, "final_cta": 1}
    assert body["byType"] == {"work": 1, "education": 1, "personal": 1}
    assert len(body["daily"]) == 30 and body["daily"][-1]["count"] == 3


def test_admin_list_decrypts_search_and_paginates(client):
    for name in ["alice", "bob", "alina"]:
        subscribe(client, email=f"{name}@robotics.dev")

    r = client.get("/vanika/admin/subscribers", params={"search": "ali"}, headers={**ORIGIN, **ADMIN})
    assert r.status_code == 200
    assert {i["email"] for i in r.json()["items"]} == {"alice@robotics.dev", "alina@robotics.dev"}

    page = client.get("/vanika/admin/subscribers", params={"limit": 2}, headers={**ORIGIN, **ADMIN}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert all(i["email"].endswith("@robotics.dev") for i in page["items"])


def test_admin_search_treats_input_as_literal_text(client):
    subscribe(client, email="a@robotics.dev")
    r = client.get("/vanika/admin/subscribers", params={"search": ".*"}, headers={**ORIGIN, **ADMIN})
    assert r.json()["total"] == 0


def test_admin_export_csv(client):
    subscribe(client, email="a@robotics.dev")
    r = client.get("/vanika/admin/subscribers/export.csv", headers={**ORIGIN, **ADMIN})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("email,emailType,domain,createdAt")
    assert lines[1].startswith("a@robotics.dev,work,robotics.dev,")


def test_admin_delete(client, repo):
    subscribe(client, email="a@robotics.dev")
    assert client.delete("/vanika/admin/subscribers/A@robotics.dev", headers={**ORIGIN, **ADMIN}).status_code == 200
    assert run(repo.collection.count_documents({})) == 0
    assert client.delete("/vanika/admin/subscribers/a@robotics.dev", headers={**ORIGIN, **ADMIN}).status_code == 404


def test_admin_without_storage_reports_unavailable(client_without_db):
    r = client_without_db.get("/vanika/admin/stats", headers={**ORIGIN, **ADMIN})
    assert r.status_code == 503


def test_unique_index_is_on_blind_index(client, repo):
    subscribe(client)
    indexes = run(repo.collection.index_information())
    assert any(ix.get("unique") and ix["key"] == [("email_hash", 1)] for ix in indexes.values())


def test_rate_limit_cannot_be_bypassed_by_spoofing_forwarded_for(client):
    codes = []
    for i in range(6):
        r = client.post(
            "/vanika/subscribe",
            data={"clientemail": f"spoof{i}@robotics.dev", "accesskey": "public-key"},
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

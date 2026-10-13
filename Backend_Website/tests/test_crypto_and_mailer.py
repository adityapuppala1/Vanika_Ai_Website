import asyncio
import base64

import pytest

from config import settings
from Vanika_Mailing import mailer
from Vanika_Mailing.crypto import EmailCipher, EncryptionKeyError


def test_cipher_round_trip_and_tamper_detection():
    cipher = EmailCipher(base64.urlsafe_b64encode(b"x" * 32).decode())
    token = cipher.encrypt("ada@robotics.dev")
    h = cipher.blind_index("ada@robotics.dev")
    assert token.startswith("v1:") and cipher.decrypt(token, h) == "ada@robotics.dev"

    raw = bytearray(base64.urlsafe_b64decode(token[3:]))
    raw[-1] ^= 1  # flip one bit of the GCM tag
    with pytest.raises(Exception):
        cipher.decrypt("v1:" + base64.urlsafe_b64encode(bytes(raw)).decode(), h)


def test_different_keys_cannot_read_each_other():
    a = EmailCipher(base64.urlsafe_b64encode(b"a" * 32).decode())
    b = EmailCipher(base64.urlsafe_b64encode(b"b" * 32).decode())
    with pytest.raises(Exception):
        b.decrypt(a.encrypt("ada@robotics.dev"), b.blind_index("ada@robotics.dev"))
    assert a.blind_index("ada@robotics.dev") != b.blind_index("ada@robotics.dev")


def test_short_key_is_rejected():
    with pytest.raises(EncryptionKeyError):
        EmailCipher(base64.urlsafe_b64encode(b"short").decode())


def test_transport_auto_selection(monkeypatch):
    for name in ["GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET", "SMTP_PASSWORD",
                 "AZURE_COMMUNICATION_CONNECTION_STRING"]:
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "VANIKA_MAIL_TRANSPORT", "auto")
    assert mailer.active_transport() == "none"
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "x")
    assert mailer.active_transport() == "smtp"
    for name in ["GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET"]:
        monkeypatch.setattr(settings, name, "x")
    assert mailer.active_transport() == "graph"


def test_smtp_message_from_info_with_bcc_only_in_envelope(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["server"] = (host, port)

        def ehlo(self):
            pass

        def starttls(self, context=None):
            sent["tls_verifies_cert"] = context.check_hostname

        def login(self, user, password):
            sent["login"] = user

        def send_message(self, msg, from_addr=None, to_addrs=None):
            sent["msg"], sent["from"], sent["rcpt"] = msg, from_addr, to_addrs

        def quit(self):
            pass

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "VANIKA_MAIL_TRANSPORT", "smtp")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "pw")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")

    result = asyncio.run(mailer.send_mail("Hi", "<p>Hello <b>there</b></p>", bcc=["dev@vanika.ai"]))
    assert result["status"] == "success"
    assert sent["server"] == ("smtp.office365.com", 587) and sent["tls_verifies_cert"] is True
    assert sent["login"] == "info@vanika.ai" and sent["from"] == "info@vanika.ai"
    assert sent["rcpt"] == ["info@vanika.ai", "dev@vanika.ai"]
    msg = sent["msg"]
    assert msg["To"] == "info@vanika.ai" and msg["Bcc"] is None
    assert "info@vanika.ai" in msg["From"] and msg["Reply-To"] == "info@vanika.ai"
    assert "Hello there" in msg.get_body(("plain",)).get_content()


def test_mail_errors_never_contain_addresses(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("{'jane@corp.com': (550, b'5.1.1 User unknown')}")

    monkeypatch.setattr(settings, "VANIKA_MAIL_TRANSPORT", "smtp")
    monkeypatch.setattr(mailer, "_send_smtp", boom)
    result = asyncio.run(mailer.send_mail("Hi", "<p>x</p>", to="jane@corp.com"))
    assert result["status"] == "error"
    assert "jane@corp.com" not in result["message"] and "<address>" in result["message"]


def test_turnstile_rejects_oversized_tokens(monkeypatch):
    from Vanika_Mailing import security

    monkeypatch.setattr(settings, "TURNSTILE_SECRET_KEY", "secret")
    assert asyncio.run(security.verify_turnstile("x" * 2049, "1.2.3.4")) is False


def test_send_mail_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "VANIKA_MAIL_TRANSPORT", "none")
    result = asyncio.run(mailer.send_mail("Hi", "<p>x</p>"))
    assert result["status"] == "error" and "No mail transport" in result["message"]

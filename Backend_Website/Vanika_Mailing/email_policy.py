# Vanika_Mailing/email_policy.py
"""Which email addresses may join the waitlist.

Accepted: work / company addresses, school & university addresses, and
personal addresses at well-known providers (Gmail, Outlook, …).
Rejected: malformed addresses, disposable/temporary inboxes, no-reply and
system mailboxes, obvious typos of popular providers, and domains that
cannot receive mail (no MX record / null MX).

VANIKA_EMAIL_POLICY=work_or_school additionally rejects personal providers.
"""
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

# pyrefly: ignore [missing-import]
from email_validator import EmailNotValidError, EmailUndeliverableError, validate_email

POLICY_STANDARD = "standard"
POLICY_WORK_OR_SCHOOL = "work_or_school"

TYPE_WORK = "work"
TYPE_EDUCATION = "education"
TYPE_PERSONAL = "personal"

# Well-known personal mailbox providers ("known domains")
PERSONAL_PROVIDERS = frozenset({
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "outlook.in", "hotmail.co.uk", "live.in",
    "yahoo.com", "yahoo.co.in", "yahoo.in", "yahoo.co.uk", "ymail.com", "rocketmail.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com",
    "proton.me", "protonmail.com", "pm.me",
    "zoho.com", "zohomail.com", "zohomail.in",
    "gmx.com", "gmx.de", "gmx.net", "web.de", "mail.com", "email.com",
    "yandex.com", "yandex.ru",
    "rediffmail.com",
    "fastmail.com", "hey.com", "tuta.io", "tutanota.com",
    "qq.com", "163.com", "126.com", "naver.com",
})

# Mistyped domains we never want to accept even if a squatter gives them an MX record
# Short or country-variant domains (proton.me, yahoo.co.in) are left out: too many
# real domains sit one letter away from them (yahoo.co.id, yahoo.co.il, ...).
_TYPO_TARGETS = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com")
# Real domains that happen to be one edit away from a target
_NOT_TYPOS = frozenset({
    "cloud.com", "gmail.de", "yahoo.de", "yahoo.es", "yahoo.fr", "yahoo.it",
    "hotmail.de", "hotmail.fr", "hotmail.es", "hotmail.it", "outlook.de", "outlook.fr", "outlook.es",
})

# Local parts that are systems, not people
_ROLE_LOCAL_PARTS = frozenset({
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply", "do_not_reply",
    "mailer-daemon", "postmaster", "bounce", "bounces", "abuse", "nobody",
})

# Education domains: *.edu, *.edu.xx, *.ac.xx, *.sch.xx, *.k12.xx.us (e.g. iitb.ac.in, ox.ac.uk, unsw.edu.au)
_EDU_PATTERN = re.compile(r"(^|\.)(edu|edu\.[a-z]{2,3}|ac\.[a-z]{2}|sch\.[a-z]{2}|k12\.[a-z]{2}\.us)$")

_DATA_FILE = Path(__file__).with_name("data") / "disposable_domains.txt"


def _load_disposable() -> frozenset:
    try:
        lines = _DATA_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        print(f"[Vanika] [WARN] Disposable domain list missing at {_DATA_FILE}")
        return frozenset()
    return frozenset(l.strip().lower() for l in lines if l.strip() and not l.startswith("#"))


DISPOSABLE_DOMAINS = _load_disposable()

MESSAGES = {
    "INVALID_EMAIL": "Please enter a valid email address.",
    "EMAIL_TYPO": "That domain looks mistyped. Did you mean {suggestion}?",
    "DISPOSABLE_EMAIL": "Temporary or disposable email addresses aren't accepted. "
                        "Please use your work, school or personal email.",
    "ROLE_EMAIL": "Please use your own email address, not a no-reply or system mailbox.",
    "UNDELIVERABLE_DOMAIN": "That email domain can't receive mail. Please check the address.",
    "PERSONAL_EMAIL_NOT_ALLOWED": "Please use your work or school email address.",
}


@dataclass
class PolicyResult:
    ok: bool
    email: Optional[str] = None  # normalised, lowercased
    domain: Optional[str] = None
    email_type: Optional[str] = None
    code: Optional[str] = None
    message: Optional[str] = None
    suggestion: Optional[str] = None


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    """True when a and b differ by one insert, delete, substitution or adjacent swap."""
    if a == b or abs(len(a) - len(b)) > 1:
        return a == b
    if len(a) == len(b):
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diffs) == 1:
            return True
        return len(diffs) == 2 and diffs[1] == diffs[0] + 1 and a[diffs[0]] == b[diffs[1]] and a[diffs[1]] == b[diffs[0]]
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1:]


def typo_suggestion(domain: str) -> Optional[str]:
    if domain in PERSONAL_PROVIDERS or domain in _NOT_TYPOS:
        return None
    for target in _TYPO_TARGETS:
        if _edit_distance_at_most_one(domain, target):
            return target
    # gmail.co / gmail.con / gmail.cm style TLD slips
    name, _, tld = domain.rpartition(".")
    if f"{name}.com" in _TYPO_TARGETS and tld in {"co", "con", "cm", "om", "comm", "cpm", "vom", "xom"}:
        return f"{name}.com"
    return None


def is_disposable(domain: str) -> bool:
    # Match the domain and every parent (e.g. foo.mailinator.com)
    parts = domain.split(".")
    return any(".".join(parts[i:]) in DISPOSABLE_DOMAINS for i in range(len(parts) - 1))


def classify(domain: str) -> str:
    if _EDU_PATTERN.search(domain):
        return TYPE_EDUCATION
    if domain in PERSONAL_PROVIDERS:
        return TYPE_PERSONAL
    return TYPE_WORK


class DeliverabilityChecker:
    """MX lookups via email-validator/dnspython, cached per domain."""

    def __init__(self, timeout: float = 4.0, ttl_seconds: int = 3600, max_entries: int = 5000):
        self.timeout = timeout
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, Tuple[float, bool]] = {}

    def is_deliverable(self, email: str, domain: str) -> bool:
        now = time.monotonic()
        cached = self._cache.get(domain)
        if cached and now - cached[0] < self.ttl:
            return cached[1]
        try:
            validate_email(email, check_deliverability=True, timeout=self.timeout)
            ok = True
        except EmailUndeliverableError:
            ok = False
        except EmailNotValidError:
            ok = False
        except Exception as e:  # resolver trouble: don't turn away real people
            print(f"[Vanika] [WARN] DNS check failed for {domain}, allowing: {e}")
            return True
        if len(self._cache) >= self.max_entries:
            self._cache.clear()
        self._cache[domain] = (now, ok)
        return ok


class EmailPolicy:
    def __init__(
        self,
        mode: str = POLICY_STANDARD,
        check_dns: bool = True,
        deliverability: Optional[Callable[[str, str], bool]] = None,
    ):
        self.mode = mode
        self.check_dns = check_dns
        self._deliverable = deliverability or DeliverabilityChecker().is_deliverable

    def _reject(self, code: str, **extra) -> PolicyResult:
        message = MESSAGES[code].format(**extra) if extra else MESSAGES[code]
        return PolicyResult(ok=False, code=code, message=message, **extra)

    def evaluate(self, raw: str, allow_typo: bool = False) -> PolicyResult:
        """Blocking (DNS) — call from a worker thread in async code.

        allow_typo: the visitor saw the "did you mean" hint and chose to keep their address.
        """
        try:
            info = validate_email((raw or "").strip(), check_deliverability=False)
        except EmailNotValidError:
            return self._reject("INVALID_EMAIL")

        email = info.normalized.lower()
        local = email.rsplit("@", 1)[0]
        # Checks run on the ASCII (punycode) form so IDN domains match the blocklist
        domain = info.ascii_domain.lower()

        if local.split("+")[0] in _ROLE_LOCAL_PARTS:
            return self._reject("ROLE_EMAIL")

        suggestion = None if allow_typo else typo_suggestion(domain)
        if suggestion:
            return self._reject("EMAIL_TYPO", suggestion=f"{local}@{suggestion}")

        if is_disposable(domain):
            return self._reject("DISPOSABLE_EMAIL")

        email_type = classify(domain)
        if self.mode == POLICY_WORK_OR_SCHOOL and email_type == TYPE_PERSONAL:
            return self._reject("PERSONAL_EMAIL_NOT_ALLOWED")

        # Known providers obviously receive mail; only look up everything else
        if self.check_dns and email_type != TYPE_PERSONAL and not self._deliverable(email, domain):
            return self._reject("UNDELIVERABLE_DOMAIN")

        return PolicyResult(ok=True, email=email, domain=domain, email_type=email_type)

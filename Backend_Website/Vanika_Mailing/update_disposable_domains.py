"""Refresh Vanika_Mailing/data/disposable_domains.txt from the upstream CC0 list.

Usage (from Backend_Website/):  python -m Vanika_Mailing.update_disposable_domains
Review the diff, run the tests, then commit the updated file.
"""
import datetime
import re
import urllib.request
from pathlib import Path

SOURCE = (
    "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/"
    "main/disposable_email_blocklist.conf"
)
TARGET = Path(__file__).with_name("data") / "disposable_domains.txt"

# Never block these, whatever upstream says
KEEP = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "proton.me", "vanika.ai"}


def main() -> None:
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        text = response.read().decode("utf-8")
    domains = sorted({
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#") and re.fullmatch(r"[a-z0-9.-]+", line.strip().lower())
    } - KEEP)
    if len(domains) < 1000:
        raise SystemExit(f"Refusing to write a suspiciously short list ({len(domains)} domains)")
    today = datetime.date.today().isoformat()
    header = (
        "# Disposable / temporary email domains — one per line.\n"
        "# Source: https://github.com/disposable-email-domains/disposable-email-domains\n"
        f"#   (disposable_email_blocklist.conf, fetched {today}) — CC0 1.0, public domain.\n"
        "# Refresh: python -m Vanika_Mailing.update_disposable_domains\n"
    )
    TARGET.write_text(header + "\n".join(domains) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {len(domains)} domains to {TARGET}")


if __name__ == "__main__":
    main()

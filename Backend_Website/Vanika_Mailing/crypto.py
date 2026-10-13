# Vanika_Mailing/crypto.py
"""Field-level encryption for waitlist email addresses.

- Addresses are encrypted with AES-256-GCM (authenticated encryption, a fresh
  96-bit random nonce per value) before they reach MongoDB.
- Lookups and de-duplication use a blind index: HMAC-SHA256 of the normalised
  address. It lets us find a record by email without storing the email.
- Both keys are derived with HKDF-SHA256 from one 32-byte master key,
  VANIKA_ENCRYPTION_KEY (base64). Keep it in Azure Key Vault / App Service
  settings and back it up: without it the stored addresses cannot be read.

Generate a key:
    python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
"""
import base64
import hashlib
import hmac
import os
from typing import Optional

# pyrefly: ignore [missing-import]
from cryptography.hazmat.primitives import hashes
# pyrefly: ignore [missing-import]
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
# pyrefly: ignore [missing-import]
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEY_VERSION = "v1"
_AAD_PREFIX = b"vanika-waitlist-email|"


class EncryptionKeyError(ValueError):
    pass


def _derive(master: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)


def _decode_master_key(encoded: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(encoded.strip() + "=" * (-len(encoded.strip()) % 4))
    except Exception as e:
        raise EncryptionKeyError("VANIKA_ENCRYPTION_KEY is not valid base64") from e
    if len(raw) != 32:
        raise EncryptionKeyError(f"VANIKA_ENCRYPTION_KEY must decode to 32 bytes, got {len(raw)}")
    return raw


class EmailCipher:
    def __init__(self, master_key_b64: str):
        master = _decode_master_key(master_key_b64)
        self._aead = AESGCM(_derive(master, b"vanika-waitlist-enc-v1"))
        self._mac_key = _derive(master, b"vanika-waitlist-index-v1")

    def blind_index(self, email: str) -> str:
        return hmac.new(self._mac_key, email.encode("utf-8"), hashlib.sha256).hexdigest()

    def encrypt(self, email: str) -> str:
        nonce = os.urandom(12)
        # The blind index is bound in as associated data, so a ciphertext copied
        # onto another record fails authentication instead of decrypting.
        aad = _AAD_PREFIX + self.blind_index(email).encode()
        ciphertext = self._aead.encrypt(nonce, email.encode("utf-8"), aad)
        return f"{KEY_VERSION}:" + base64.urlsafe_b64encode(nonce + ciphertext).decode()

    def decrypt(self, token: str, email_hash: str) -> str:
        version, _, payload = token.partition(":")
        if version != KEY_VERSION:
            raise EncryptionKeyError(f"Unsupported ciphertext version {version!r}")
        blob = base64.urlsafe_b64decode(payload)
        return self._aead.decrypt(blob[:12], blob[12:], _AAD_PREFIX + email_hash.encode()).decode("utf-8")


_cipher: Optional[EmailCipher] = None
_cipher_error: Optional[str] = None


def get_cipher(master_key_b64: str) -> Optional[EmailCipher]:
    """Process-wide cipher, or None (with a logged reason) when the key is missing/invalid."""
    global _cipher, _cipher_error
    if _cipher is not None or _cipher_error is not None:
        return _cipher
    if not master_key_b64:
        _cipher_error = "VANIKA_ENCRYPTION_KEY is not set"
    else:
        try:
            _cipher = EmailCipher(master_key_b64)
        except EncryptionKeyError as e:
            _cipher_error = str(e)
    if _cipher_error:
        print(f"[Vanika] [FAIL] {_cipher_error} — waitlist storage is disabled until it is fixed.")
    return _cipher


def cipher_error() -> Optional[str]:
    return _cipher_error

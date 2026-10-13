# Vanika_Mailing/waitlist.py
"""Waitlist storage for Vanika.ai sign-ups (MongoDB, encrypted emails).

One document per person. The address itself is stored only as AES-256-GCM
ciphertext (`email_enc`); `email_hash` (HMAC blind index) is the unique key
used for de-duplication and lookups. Repeat sign-ups update the existing
document, so the collection count is the number of unique people.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
from pymongo import DESCENDING, ReturnDocument
# pyrefly: ignore [missing-import]
from pymongo.errors import DuplicateKeyError, OperationFailure

from Vanika_Mailing.crypto import KEY_VERSION, EmailCipher

DAILY_WINDOW_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    # Mongo returns naive datetimes (UTC) unless the client is tz_aware
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


@dataclass
class SignupResult:
    email: str
    is_new: bool


class WaitlistRepository:
    def __init__(self, collection, cipher: EmailCipher):
        self.collection = collection
        self.cipher = cipher

    async def ensure_indexes(self) -> None:
        await self.encrypt_legacy_records()
        # A unique index on a plaintext `email` field (pre-encryption builds) would
        # reject every new document, which no longer has that field.
        try:
            await self.collection.drop_index("email_1")
        except OperationFailure:
            pass
        await self.collection.create_index("email_hash", unique=True)
        await self.collection.create_index([("created_at", DESCENDING)])

    async def encrypt_legacy_records(self) -> int:
        """Encrypt records written by pre-encryption builds and remove their plaintext."""
        migrated = 0
        async for doc in self.collection.find({"email": {"$exists": True}, "email_hash": {"$exists": False}}):
            email = str(doc["email"]).strip().lower()
            email_hash = self.cipher.blind_index(email)
            if await self.collection.find_one({"email_hash": email_hash}, {"_id": 1}):
                # Already present in encrypted form: the plaintext copy is a duplicate
                await self.collection.delete_one({"_id": doc["_id"]})
            else:
                await self.collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "email_hash": email_hash,
                            "email_enc": self.cipher.encrypt(email),
                            "email_domain": email.rsplit("@", 1)[-1],
                            "email_type": doc.get("email_type") or "unknown",
                            "key_version": KEY_VERSION,
                        },
                        "$unset": {"email": ""},
                    },
                )
            migrated += 1
        if migrated:
            print(f"[Vanika] Encrypted {migrated} legacy plaintext waitlist record(s).")
        return migrated

    async def add_signup(
        self,
        email: str,
        source: str,
        email_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SignupResult:
        """Insert a new subscriber, or record a repeat sign-up for an existing one."""
        now = _now()
        update = {
            "$setOnInsert": {
                "email_hash": self.cipher.blind_index(email),
                "email_enc": self.cipher.encrypt(email),
                "email_domain": email.rsplit("@", 1)[-1],
                "email_type": email_type,
                "key_version": KEY_VERSION,
                "created_at": now,
                "first_source": source,
                "status": "active",
                "metadata": metadata or {},
                "email_status": {"admin": "pending", "user": "pending"},
            },
            "$set": {"last_signup_at": now},
            "$inc": {"signup_count": 1},
            "$addToSet": {"sources": source},
        }
        query = {"email_hash": self.cipher.blind_index(email)}
        try:
            before = await self.collection.find_one_and_update(
                query, update, upsert=True, return_document=ReturnDocument.BEFORE
            )
        except DuplicateKeyError:
            # Two concurrent first sign-ups raced on the unique index; the other one inserted.
            before = await self.collection.find_one_and_update(
                query, update, upsert=True, return_document=ReturnDocument.BEFORE
            )
        return SignupResult(email=email, is_new=before is None)

    async def set_email_status(self, email: str, admin: str, user: str, error: Optional[str] = None) -> None:
        fields: Dict[str, Any] = {"email_status": {"admin": admin, "user": user}}
        if error:
            fields["email_error"] = error[:500]
        await self.collection.update_one({"email_hash": self.cipher.blind_index(email)}, {"$set": fields})

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def stats(self) -> Dict[str, Any]:
        now = _now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = start_of_today - timedelta(days=DAILY_WINDOW_DAYS - 1)

        total = await self.collection.count_documents({})
        today = await self.collection.count_documents({"created_at": {"$gte": start_of_today}})
        last_7 = await self.collection.count_documents({"created_at": {"$gte": now - timedelta(days=7)}})
        last_30 = await self.collection.count_documents({"created_at": {"$gte": now - timedelta(days=30)}})

        async def breakdown(field: str) -> Dict[str, int]:
            out = {}
            for value in await self.collection.distinct(field):
                out[value or "unknown"] = await self.collection.count_documents({field: value})
            return out

        # Waitlist volumes are small; bucketing in Python keeps this portable.
        buckets = {(window_start + timedelta(days=i)).date().isoformat(): 0 for i in range(DAILY_WINDOW_DAYS)}
        cursor = self.collection.find({"created_at": {"$gte": window_start}}, {"created_at": 1, "_id": 0})
        async for doc in cursor:
            day = _as_utc(doc["created_at"]).date().isoformat()
            if day in buckets:
                buckets[day] += 1

        return {
            "total": total,
            "today": today,
            "last7Days": last_7,
            "last30Days": last_30,
            "bySource": await breakdown("first_source"),
            "byType": await breakdown("email_type"),
            "daily": [{"date": d, "count": c} for d, c in buckets.items()],
        }

    async def list_subscribers(self, search: Optional[str], limit: int, offset: int) -> Dict[str, Any]:
        sort = [("created_at", DESCENDING), ("_id", DESCENDING)]
        needle = (search or "").strip().lower()
        if not needle:
            total = await self.collection.count_documents({})
            cursor = self.collection.find({}).sort(sort).skip(offset).limit(limit)
            items = [self.serialize(doc) async for doc in cursor]
        else:
            # Emails are encrypted, so substring search happens after decryption.
            matches = [s async for s in self._decrypted(self.collection.find({}).sort(sort)) if needle in s["email"]]
            total = len(matches)
            items = matches[offset:offset + limit]
        return {"total": total, "items": items, "limit": limit, "offset": offset}

    async def all_subscribers(self) -> List[Dict[str, Any]]:
        cursor = self.collection.find({}).sort([("created_at", 1), ("_id", 1)])
        return [s async for s in self._decrypted(cursor)]

    async def delete(self, email: str) -> bool:
        result = await self.collection.delete_one({"email_hash": self.cipher.blind_index(email)})
        return result.deleted_count > 0

    async def _decrypted(self, cursor):
        async for doc in cursor:
            yield self.serialize(doc)

    def _email(self, doc: Dict[str, Any]) -> str:
        try:
            return self.cipher.decrypt(doc["email_enc"], doc["email_hash"])
        except Exception:
            # Wrong key or tampered ciphertext — show the record but not a fake address
            return "(cannot decrypt — check VANIKA_ENCRYPTION_KEY)"

    def serialize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        created = _as_utc(doc.get("created_at"))
        last = _as_utc(doc.get("last_signup_at"))
        metadata = doc.get("metadata") or {}
        return {
            "email": self._email(doc),
            "domain": doc.get("email_domain"),
            "emailType": doc.get("email_type"),
            "createdAt": created.isoformat() if created else None,
            "lastSignupAt": last.isoformat() if last else None,
            "firstSource": doc.get("first_source"),
            "sources": doc.get("sources", []),
            "signupCount": doc.get("signup_count", 1),
            "status": doc.get("status", "active"),
            "emailStatus": doc.get("email_status", {}),
            "emailError": doc.get("email_error"),
            "referrer": metadata.get("referrer"),
            "utmSource": metadata.get("utm_source"),
            "utmMedium": metadata.get("utm_medium"),
            "utmCampaign": metadata.get("utm_campaign"),
        }

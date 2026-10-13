# Vanika_Mailing/waitlist.py
"""Waitlist storage for Vanika.ai sign-ups (MongoDB).

One document per email address. Repeat sign-ups update the existing
document instead of creating duplicates, so the collection count is the
number of unique people on the waitlist.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
from pymongo import ASCENDING, DESCENDING, ReturnDocument
# pyrefly: ignore [missing-import]
from pymongo.errors import DuplicateKeyError

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
    def __init__(self, collection):
        self.collection = collection

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("email", unique=True)
        await self.collection.create_index([("created_at", DESCENDING)])

    async def add_signup(
        self,
        email: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SignupResult:
        """Insert a new subscriber, or record a repeat sign-up for an existing one."""
        now = _now()
        update = {
            "$setOnInsert": {
                "email": email,
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
        try:
            before = await self.collection.find_one_and_update(
                {"email": email}, update, upsert=True, return_document=ReturnDocument.BEFORE
            )
        except DuplicateKeyError:
            # Two concurrent first sign-ups raced on the unique index; the other one inserted.
            before = await self.collection.find_one_and_update(
                {"email": email}, update, upsert=True, return_document=ReturnDocument.BEFORE
            )
        return SignupResult(email=email, is_new=before is None)

    async def set_email_status(self, email: str, admin: str, user: str, error: Optional[str] = None) -> None:
        fields: Dict[str, Any] = {"email_status": {"admin": admin, "user": user}}
        if error:
            fields["email_error"] = error[:500]
        await self.collection.update_one({"email": email}, {"$set": fields})

    async def stats(self) -> Dict[str, Any]:
        now = _now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        window_start = start_of_today - timedelta(days=DAILY_WINDOW_DAYS - 1)

        total = await self.collection.count_documents({})
        today = await self.collection.count_documents({"created_at": {"$gte": start_of_today}})
        last_7 = await self.collection.count_documents({"created_at": {"$gte": now - timedelta(days=7)}})
        last_30 = await self.collection.count_documents({"created_at": {"$gte": now - timedelta(days=30)}})

        by_source = {}
        for source in await self.collection.distinct("first_source"):
            by_source[source or "unknown"] = await self.collection.count_documents({"first_source": source})

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
            "bySource": by_source,
            "daily": [{"date": d, "count": c} for d, c in buckets.items()],
        }

    def _search_filter(self, search: Optional[str]) -> Dict[str, Any]:
        if not search or not search.strip():
            return {}
        return {"email": {"$regex": re.escape(search.strip().lower())}}

    async def list_subscribers(self, search: Optional[str], limit: int, offset: int) -> Dict[str, Any]:
        query = self._search_filter(search)
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort([("created_at", DESCENDING), ("email", ASCENDING)])
            .skip(offset)
            .limit(limit)
        )
        items = [self.serialize(doc) async for doc in cursor]
        return {"total": total, "items": items, "limit": limit, "offset": offset}

    async def all_subscribers(self) -> List[Dict[str, Any]]:
        cursor = self.collection.find({}).sort([("created_at", ASCENDING)])
        return [self.serialize(doc) async for doc in cursor]

    async def delete(self, email: str) -> bool:
        result = await self.collection.delete_one({"email": email})
        return result.deleted_count > 0

    @staticmethod
    def serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
        created = _as_utc(doc.get("created_at"))
        last = _as_utc(doc.get("last_signup_at"))
        metadata = doc.get("metadata") or {}
        return {
            "email": doc.get("email"),
            "createdAt": created.isoformat() if created else None,
            "lastSignupAt": last.isoformat() if last else None,
            "firstSource": doc.get("first_source"),
            "sources": doc.get("sources", []),
            "signupCount": doc.get("signup_count", 1),
            "status": doc.get("status", "active"),
            "emailStatus": doc.get("email_status", {}),
            "referrer": metadata.get("referrer"),
            "utmSource": metadata.get("utm_source"),
            "utmMedium": metadata.get("utm_medium"),
            "utmCampaign": metadata.get("utm_campaign"),
        }

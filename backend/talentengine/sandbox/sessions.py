"""Short-lived, encrypted storage of public test sessions, so a test in progress survives a server restart.

Sandbox tests (verification test, AI-pilot test) used to live only in memory: a deployment in the middle
of someone's test made their link "unknown or expired". Sessions are now also written to the database,
**encrypted with the vault key** (Fernet) and **deleted when they expire** (three hours at most for the
sandbox). Memory stays the first place read; the database is the fallback after a restart.

What is kept: the test itself (questions, instructions typed, files of the exercise). The CV analysis of the
sandbox is unchanged and never stored.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import TypeVar

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel

from ..models import utcnow
from ..store import Store

T = TypeVar("T", bound=BaseModel)
COLLECTION = "sandbox_sessions"


class SandboxSessions:
    def __init__(self, prefix: str, store: Store | None = None, key: str | None = None) -> None:
        self.prefix = prefix
        self.store = store
        self.fernet = Fernet(key.encode()) if store is not None and key else None
        self._memory: dict[str, tuple[datetime, BaseModel]] = {}
        self._lock = threading.RLock()

    def put(self, key: str, session: BaseModel, expires_at: datetime) -> None:
        now = utcnow()
        with self._lock:
            self._memory[key] = (expires_at, session)
            for k in [k for k, (exp, _) in self._memory.items() if exp < now]:
                del self._memory[k]
        if self.fernet is not None and self.store is not None:
            token = self.fernet.encrypt(session.model_dump_json().encode()).decode()
            self.store.put_json(COLLECTION, f"{self.prefix}:{key}", {"exp": expires_at.isoformat(), "data": token})
            self.purge(now)

    def get(self, key: str, cls: type[T]) -> T | None:
        with self._lock:
            item = self._memory.get(key)
        if item is not None and isinstance(item[1], cls):
            return item[1]
        if self.fernet is None or self.store is None:
            return None
        row = self.store.get_json(COLLECTION, f"{self.prefix}:{key}")
        if not row or datetime.fromisoformat(row["exp"]) < utcnow():
            return None
        try:
            session = cls.model_validate_json(self.fernet.decrypt(row["data"].encode()))
        except (InvalidToken, ValueError):
            return None
        with self._lock:
            self._memory[key] = (datetime.fromisoformat(row["exp"]), session)
        return session

    def purge(self, now: datetime | None = None) -> int:
        if self.store is None:
            return 0
        rows = self.store.query("SELECT id, body FROM documents WHERE collection = ? AND id LIKE ?",
                                (COLLECTION, f"{self.prefix}:%"))
        limit = (now or utcnow()).isoformat()
        expired = [r["id"] for r in rows if r["body"] and _exp(r["body"]) < limit]
        for id_ in expired:
            self.store.delete(COLLECTION, id_)
        return len(expired)


def _exp(body: str) -> str:
    try:
        return str(json.loads(body).get("exp", ""))
    except ValueError:
        return ""

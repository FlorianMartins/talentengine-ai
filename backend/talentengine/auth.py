"""Named accounts and roles.

The AI Act asks for decisions taken by an identified person (Art. 14) and logs that say who did what
(Art. 12). With a single shared key, the "reviewer" was whatever name the client sent. With accounts,
every ledger entry carries the authenticated name, and a decision cannot be signed with someone else's.

* Keys look like ``te_<random>``; only their SHA-256 is stored (``<data_dir>/users.json``, mode 0600).
  A key is shown once, at creation (``talentengine adduser NAME --role recruiter``).
* Roles: ``recruiter`` (jobs, applications, evaluations, decisions, identity reveal after a decision,
  explanation links), ``dpo`` (read everything, erasure, data export, retention sweeps), ``admin`` (all,
  plus accounts and demo data).
* Compatibility: the legacy single ``TE_API_KEY`` still works and maps to an admin whose name comes from
  the ``X-Actor`` header. With neither accounts nor key (development), the API is open.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["recruiter", "dpo", "admin"]

PERMISSIONS: dict[str, set[str]] = {
    "read": {"recruiter", "dpo", "admin"},     # jobs, candidates, reports, audit trail, DPIA draft
    "write": {"recruiter", "admin"},           # job profiles, applications, evaluations
    "decide": {"recruiter", "admin"},          # human decisions, identity reveal, explanation links
    "privacy": {"dpo", "admin"},               # erasure, data export, retention sweeps
    "admin": {"admin"},                        # accounts, demo data
}


class Principal(BaseModel):
    name: str
    role: Role
    authenticated: bool
    shared_key: bool = False

    def can(self, permission: str) -> bool:
        return self.role in PERMISSIONS[permission]

    @property
    def permissions(self) -> list[str]:
        return sorted(p for p, roles in PERMISSIONS.items() if self.role in roles)


class UserRecord(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    role: Role
    key_sha256: str
    created_at: str


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class UserStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> list[UserRecord]:
        if not self.path.exists():
            return []
        return [UserRecord.model_validate(u) for u in json.loads(self.path.read_text()).get("users", [])]

    def _save(self, users: list[UserRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"users": [u.model_dump() for u in users]}, fh, indent=2)
        os.replace(tmp, self.path)

    def any(self) -> bool:
        return bool(self._load())

    def list(self) -> list[dict[str, str]]:
        return [{"name": u.name, "role": u.role, "created_at": u.created_at} for u in self._load()]

    def add(self, name: str, role: Role) -> str:
        with self._lock:
            users = self._load()
            if any(u.name.lower() == name.lower() for u in users):
                raise ValueError(f"an account named {name!r} already exists")
            key = "te_" + secrets.token_urlsafe(32)
            users.append(UserRecord(name=name, role=role, key_sha256=_digest(key),
                                    created_at=datetime.now(UTC).isoformat()))
            self._save(users)
            return key

    def remove(self, name: str) -> bool:
        with self._lock:
            users = self._load()
            kept = [u for u in users if u.name.lower() != name.lower()]
            self._save(kept)
            return len(kept) != len(users)

    def authenticate(self, key: str) -> Principal | None:
        digest = _digest(key)
        match = None
        for user in self._load():  # compare against every record: no early exit on a timing side channel
            if hmac.compare_digest(user.key_sha256, digest):
                match = user
        return Principal(name=match.name, role=match.role, authenticated=True) if match else None

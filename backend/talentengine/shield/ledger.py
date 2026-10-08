"""Immutable audit ledger ("glass box") required by the EU AI Act for high-risk systems.

Recruitment is listed in Annex III of the AI Act, so the system must keep logs (Art. 12), be
transparent (Art. 13) and allow human oversight (Art. 14). Every event that influences a candidate's
outcome is appended here:

    ingestion -> redaction -> l1_analysis -> escalation -> skill_assessment -> score -> human_decision

Integrity has three layers:

* **Append-only table**: SQLite triggers abort any UPDATE or DELETE.
* **Hash chain**: ``entry_hash = sha256(seq | prev_hash | kind | actor | created_at | payload)``.
  Changing one byte of an old entry breaks every hash after it.
* **HMAC seal**: each hash is also signed with a server key, so an attacker with write access to the
  database file cannot simply recompute the whole chain.

Payloads never contain raw personal data, only pseudonymous references and evidence excerpts that
already went through the shield. This is what makes the ledger compatible with the GDPR right to
erasure: deleting the vault entry (crypto-shredding) is enough.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from ..store import Store

GENESIS = "0" * 64


class LedgerEntry(BaseModel):
    seq: int
    entry_id: str
    kind: str
    actor: str
    job_id: str | None
    candidate_ref: str | None
    created_at: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str
    seal: str


class ChainVerification(BaseModel):
    valid: bool
    length: int
    head_hash: str
    first_invalid_seq: int | None = None
    reason: str = ""


def canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(seq: int, prev_hash: str, kind: str, actor: str, created_at: str, payload_json: str) -> str:
    material = "|".join([str(seq), prev_hash, kind, actor, created_at, payload_json])
    return hashlib.sha256(material.encode()).hexdigest()


class AuditLedger:
    def __init__(self, store: Store, seal_key: str) -> None:
        self._store = store
        self._seal_key = seal_key.encode()

    def _seal(self, entry_hash: str) -> str:
        return hmac.new(self._seal_key, entry_hash.encode(), hashlib.sha256).hexdigest()

    def append(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        actor: str = "system",
        job_id: str | None = None,
        candidate_ref: str | None = None,
    ) -> LedgerEntry:
        payload_json = canonical(payload)
        created_at = datetime.now(UTC).isoformat()
        entry_id = f"LED-{uuid.uuid4().hex[:12]}"
        with self._store.transaction() as conn:
            head = conn.execute("SELECT seq, entry_hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
            seq = (head["seq"] + 1) if head else 1
            prev = head["entry_hash"] if head else GENESIS
            entry_hash = _hash(seq, prev, kind, actor, created_at, payload_json)
            seal = self._seal(entry_hash)
            conn.execute(
                "INSERT INTO ledger(seq, entry_id, kind, actor, job_id, candidate_ref, created_at, payload, "
                "prev_hash, entry_hash, seal) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (seq, entry_id, kind, actor, job_id, candidate_ref, created_at, payload_json, prev,
                 entry_hash, seal),
            )
        return LedgerEntry(seq=seq, entry_id=entry_id, kind=kind, actor=actor, job_id=job_id,
                           candidate_ref=candidate_ref, created_at=created_at, payload=json.loads(payload_json),
                           prev_hash=prev, entry_hash=entry_hash, seal=seal)

    def _row_to_entry(self, row: Any) -> LedgerEntry:
        return LedgerEntry(
            seq=row["seq"], entry_id=row["entry_id"], kind=row["kind"], actor=row["actor"],
            job_id=row["job_id"], candidate_ref=row["candidate_ref"], created_at=row["created_at"],
            payload=json.loads(row["payload"]), prev_hash=row["prev_hash"], entry_hash=row["entry_hash"],
            seal=row["seal"],
        )

    def entries(
        self,
        *,
        candidate_ref: str | None = None,
        job_id: str | None = None,
        kind: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        where, params = self._filters(candidate_ref, job_id, kind)
        rows = self._store.query(
            f"SELECT * FROM ledger {where} ORDER BY seq DESC LIMIT ? OFFSET ?",  # noqa: S608 - fixed clauses
            (*params, limit, offset),
        )
        return [self._row_to_entry(r) for r in rows]

    @staticmethod
    def _filters(candidate_ref: str | None, job_id: str | None, kind: str | None) -> tuple[str, list[str]]:
        clauses, params = [], []
        for column, value in (("candidate_ref", candidate_ref), ("job_id", job_id), ("kind", kind)):
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params

    def count(self, *, candidate_ref: str | None = None, job_id: str | None = None, kind: str | None = None) -> int:
        where, params = self._filters(candidate_ref, job_id, kind)
        return int(self._store.query(f"SELECT COUNT(*) AS n FROM ledger {where}", tuple(params))[0]["n"])  # noqa: S608

    def get(self, entry_id: str) -> LedgerEntry | None:
        rows = self._store.query("SELECT * FROM ledger WHERE entry_id = ?", (entry_id,))
        return self._row_to_entry(rows[0]) if rows else None

    def verify(self) -> ChainVerification:
        prev = GENESIS
        length = 0
        for row in self._store.query("SELECT * FROM ledger ORDER BY seq ASC"):
            length += 1
            expected = _hash(row["seq"], prev, row["kind"], row["actor"], row["created_at"], row["payload"])
            if row["prev_hash"] != prev:
                return ChainVerification(valid=False, length=length, head_hash=prev,
                                         first_invalid_seq=row["seq"], reason="broken link to previous entry")
            if row["entry_hash"] != expected:
                return ChainVerification(valid=False, length=length, head_hash=prev,
                                         first_invalid_seq=row["seq"], reason="entry content was altered")
            if not hmac.compare_digest(row["seal"], self._seal(row["entry_hash"])):
                return ChainVerification(valid=False, length=length, head_hash=prev,
                                         first_invalid_seq=row["seq"], reason="seal does not match server key")
            prev = row["entry_hash"]
        return ChainVerification(valid=True, length=length, head_hash=prev)

"""Reversible pseudonymisation vault.

Each personal value is replaced by a token such as ``[PERSON_3fa9c1]``. The token is an HMAC of the
value (stable within a candidate, so the same name always maps to the same token) and the original is
kept *encrypted* in the ``vault`` table. Re-identification is only possible through
``PseudonymVault.reveal`` which the API gates behind a human decision and logs in the ledger.
"""

from __future__ import annotations

import hashlib
import hmac

from cryptography.fernet import Fernet

from ..store import Store


class PseudonymVault:
    def __init__(self, store: Store, key: str) -> None:
        self._store = store
        self._fernet = Fernet(key.encode())
        self._hmac_key = hashlib.sha256(b"talentengine-token|" + key.encode()).digest()

    def token(self, kind: str, value: str, candidate_ref: str) -> str:
        normalised = " ".join(value.lower().split())
        digest = hmac.new(
            self._hmac_key, f"{candidate_ref}|{kind}|{normalised}".encode(), hashlib.sha256
        ).hexdigest()[:6]
        token = f"[{kind}_{digest}]"
        with self._store.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO vault(token, candidate_ref, kind, ciphertext) VALUES (?, ?, ?, ?)",
                (f"{candidate_ref}:{token}", candidate_ref, kind, self._fernet.encrypt(value.encode())),
            )
        return token

    def reveal(self, candidate_ref: str) -> dict[str, list[str]]:
        """Return every original value stored for a candidate, grouped by kind."""
        rows = self._store.query(
            "SELECT kind, ciphertext FROM vault WHERE candidate_ref = ? ORDER BY kind", (candidate_ref,)
        )
        out: dict[str, list[str]] = {}
        for row in rows:
            out.setdefault(row["kind"], []).append(self._fernet.decrypt(row["ciphertext"]).decode())
        return out

    def shred(self, candidate_ref: str) -> int:
        """Crypto-shredding: once deleted, pseudonyms in the ledger can never be linked back."""
        with self._store.transaction() as conn:
            cur = conn.execute("DELETE FROM vault WHERE candidate_ref = ?", (candidate_ref,))
            return cur.rowcount

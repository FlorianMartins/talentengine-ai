"""SQLite persistence.

A deliberately small document store: one ``documents`` table keyed by (collection, id) holding JSON,
plus two dedicated tables whose guarantees matter legally:

* ``ledger``: append-only. SQLite triggers reject every UPDATE and DELETE, so even application code
  cannot rewrite history; the hash chain (``shield.ledger``) detects tampering done outside SQLite.
* ``vault``: encrypted identities, the only place where personal data lives. Erasing a candidate
  deletes their vault rows ("crypto-shredding"): the ledger keeps hashes and pseudonyms that can no
  longer be linked back to a person.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    collection TEXT NOT NULL,
    id TEXT NOT NULL,
    parent TEXT,
    body TEXT NOT NULL,
    PRIMARY KEY (collection, id)
);
CREATE INDEX IF NOT EXISTS documents_parent ON documents(collection, parent);

CREATE TABLE IF NOT EXISTS vault (
    token TEXT PRIMARY KEY,
    candidate_ref TEXT NOT NULL,
    kind TEXT NOT NULL,
    ciphertext BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS vault_candidate ON vault(candidate_ref);

CREATE TABLE IF NOT EXISTS ledger (
    seq INTEGER PRIMARY KEY,
    entry_id TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    actor TEXT NOT NULL,
    job_id TEXT,
    candidate_ref TEXT,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    seal TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_candidate ON ledger(candidate_ref);

CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'audit ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'audit ledger is append-only'); END;
"""


class Store:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.RLock()

    # -- low level ---------------------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))

    # -- documents -----------------------------------------------------------------------------------

    def put(self, collection: str, id_: str, model: BaseModel, parent: str | None = None) -> None:
        body = model.model_dump_json()
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents(collection, id, parent, body) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(collection, id) DO UPDATE SET body = excluded.body, parent = excluded.parent",
                (collection, id_, parent, body),
            )

    def get(self, collection: str, id_: str, cls: type[T]) -> T | None:
        rows = self.query("SELECT body FROM documents WHERE collection = ? AND id = ?", (collection, id_))
        return cls.model_validate_json(rows[0]["body"]) if rows else None

    def list(self, collection: str, cls: type[T], parent: str | None = None) -> list[T]:
        if parent is None:
            rows = self.query("SELECT body FROM documents WHERE collection = ? ORDER BY rowid", (collection,))
        else:
            rows = self.query(
                "SELECT body FROM documents WHERE collection = ? AND parent = ? ORDER BY rowid",
                (collection, parent),
            )
        return [cls.model_validate_json(r["body"]) for r in rows]

    def delete(self, collection: str, id_: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM documents WHERE collection = ? AND id = ?", (collection, id_))

    def delete_children(self, collection: str, parent: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM documents WHERE collection = ? AND parent = ?", (collection, parent)
            )
            return cur.rowcount

    # -- small key/value helpers for counters -------------------------------------------------------------

    def get_json(self, collection: str, id_: str) -> Any:
        rows = self.query("SELECT body FROM documents WHERE collection = ? AND id = ?", (collection, id_))
        return json.loads(rows[0]["body"]) if rows else None

    def put_json(self, collection: str, id_: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents(collection, id, parent, body) VALUES (?, ?, NULL, ?) "
                "ON CONFLICT(collection, id) DO UPDATE SET body = excluded.body",
                (collection, id_, json.dumps(value)),
            )

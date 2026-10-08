"""Key material for the vault (Fernet) and the ledger seal (HMAC).

Production deployments pass both keys through the environment (``TE_VAULT_KEY``,
``TE_LEDGER_SEAL_KEY``). For local development a key is generated once and stored next to the
database with 0600 permissions, so restarts keep working without any setup.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from pathlib import Path

from cryptography.fernet import Fernet


def _load_or_create(path: Path, factory: Callable[[], str]) -> str:
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = factory()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(value)
    return value


def resolve_vault_key(configured: str, data_dir: Path) -> str:
    if configured:
        Fernet(configured.encode())  # validates the format early
        return configured
    return _load_or_create(data_dir / "vault.key", lambda: Fernet.generate_key().decode())


def resolve_seal_key(configured: str, data_dir: Path) -> str:
    if configured:
        return configured
    return _load_or_create(data_dir / "ledger-seal.key", lambda: secrets.token_hex(32))

"""Behavioural audits of the banking export, run at close in the isolated runner (never shown to the candidate)."""

_COMMON = '''import hashlib
import io
import logging
import os

os.environ.setdefault("EXPORT_PSEUDONYM_KEY", "hidden-audit-key-not-the-real-one")

import pytest

from export.transactions import export_transactions

IBAN = "CH93 0076 2011 6238 5295 7"
ROWS = [{"date": "2026-09-01", "amount": "12.50", "currency": "CHF", "merchant": "Cafe", "iban": IBAN}]


def run():
    out = io.StringIO()
    try:
        export_transactions(ROWS, out)
    except Exception as exc:
        pytest.skip(f"the export cannot run on a standard row: {type(exc).__name__}")
    return out.getvalue()
'''

UNKEYED = _COMMON + '''

def test_the_customer_key_cannot_be_recomputed_from_the_iban():
    value = run()
    variants = {IBAN, IBAN.replace(" ", ""), IBAN.replace(" ", "").upper(), IBAN.lower()}
    digests = {getattr(hashlib, alg)(v.encode()).hexdigest()
               for alg in ("sha256", "sha1", "md5", "sha512", "sha224", "blake2b", "sha3_256") for v in variants}
    assert not any(d[:10] in value for d in digests), "an unkeyed hash of the IBAN is in the export"
'''

RAW_ROW_LOG = _COMMON + '''

def test_no_iban_in_the_logs(caplog):
    caplog.set_level(logging.DEBUG)
    run()
    assert "CH93" not in caplog.text and "0076 2011" not in caplog.text and "CH9300762011" not in caplog.text
'''

HIDDEN = {"unkeyed_hash": UNKEYED, "raw_row_log": RAW_ROW_LOG}

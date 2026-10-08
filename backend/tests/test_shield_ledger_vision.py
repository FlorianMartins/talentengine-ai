from __future__ import annotations

import io
import sqlite3

import pytest
from PIL import Image

from talentengine.shield.ledger import AuditLedger
from talentengine.shield.vision import DetectorUnavailable, NoDetector, Region, _strip_people, redact_image
from talentengine.store import Store


def _ledger(tmp_path, key: str = "k1") -> tuple[AuditLedger, Store]:
    store = Store(tmp_path / "l.sqlite3")
    return AuditLedger(store, key), store


def test_chain_is_valid_and_linked(tmp_path) -> None:
    ledger, _ = _ledger(tmp_path)
    a = ledger.append("ingestion", {"x": 1}, candidate_ref="C1")
    b = ledger.append("score", {"pct": 42.0}, candidate_ref="C1")
    assert b.prev_hash == a.entry_hash
    result = ledger.verify()
    assert result.valid and result.length == 2 and result.head_hash == b.entry_hash


def test_database_refuses_updates_and_deletes(tmp_path) -> None:
    ledger, store = _ledger(tmp_path)
    ledger.append("score", {"pct": 42.0})
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.query("UPDATE ledger SET payload = '{}'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.query("DELETE FROM ledger")


def test_tampering_outside_the_app_is_detected(tmp_path) -> None:
    ledger, _ = _ledger(tmp_path)
    ledger.append("score", {"pct": 42.0})
    ledger.append("human_decision", {"decision": "hold"})
    raw = sqlite3.connect(tmp_path / "l.sqlite3")  # an attacker with file access drops the trigger
    raw.execute("DROP TRIGGER ledger_no_update")
    raw.execute("UPDATE ledger SET payload = '{\"pct\":99.0}' WHERE seq = 1")
    raw.commit()
    result = ledger.verify()
    assert not result.valid and result.first_invalid_seq == 1 and "altered" in result.reason


def test_seal_detects_a_recomputed_chain(tmp_path) -> None:
    ledger, _ = _ledger(tmp_path, key="server-key")
    ledger.append("score", {"pct": 42.0})
    other = AuditLedger(Store(tmp_path / "l.sqlite3"), "attacker-key")
    result = other.verify()
    assert not result.valid and "seal" in result.reason


class FakeDetector:
    name = "fake"

    def __init__(self, regions: list[Region]) -> None:
        self.regions = regions

    def detect(self, image: Image.Image) -> list[Region]:
        return self.regions

    def describe(self, image: Image.Image) -> str:
        return "A woman smiling next to the table. Oak table with dovetail joints and an oil finish."


def _jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (200, 200), "white")
    for x in range(60, 140):
        for y in range(60, 140):
            img.putpixel((x, y), (0, 0, 0) if (x + y) % 2 else (255, 255, 255))
    exif = Image.Exif()
    exif[0x013B] = "Camille Rousseau"  # Artist
    exif[0x8825] = {1: "N", 2: (48.0, 6.0, 0.0)}  # GPSInfo
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_redaction_masks_regions_and_strips_metadata() -> None:
    data = _jpeg_with_exif()
    result = redact_image(data, FakeDetector([Region("face", 60, 60, 80, 80)]))
    assert "Artist" in result.metadata_removed and "GPSInfo" in result.metadata_removed
    out = Image.open(io.BytesIO(result.image_bytes))
    assert not out.getexif(), "no EXIF may survive"
    region = [out.getpixel((x, y)) for x in range(70, 130, 7) for y in range(70, 130, 7)]
    spread = max(sum(p) for p in region) - min(sum(p) for p in region)
    assert spread < 300, "the checkerboard (a stand-in for a face) must be unreadable after masking"
    assert "woman" not in result.caption.lower() and "dovetail" in result.caption


def test_no_detector_fails_closed() -> None:
    with pytest.raises(DetectorUnavailable):
        redact_image(_jpeg_with_exif(), NoDetector())


def test_caption_people_filter() -> None:
    assert _strip_people("A man holding a chisel. Walnut box with finger joints.") == "Walnut box with finger joints."

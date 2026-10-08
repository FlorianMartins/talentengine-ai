"""ATS add-on: signatures per provider, collection through a fake ATS, note written back."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from talentengine.api.app import create_app
from talentengine.auth import UserStore
from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.integrations.adapters import AshbyAdapter, GenericAdapter, GreenhouseAdapter, LeverAdapter
from talentengine.pipeline import Engine
from talentengine.shield.vision import NoDetector

CV = b"EXPERIENCE\n- Built a GitHub Actions CI/CD pipeline: releases in 25 minutes.\n- Terraform for 120 servers.\n"


def sig(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_provider_signatures() -> None:
    body = b'{"x": 1}'
    assert GreenhouseAdapter("s", "id", "sec").verify({"signature": "sha256 " + sig("s", body)}, body)
    assert not GreenhouseAdapter("s", "id", "sec").verify({"signature": "sha256=" + sig("s", body)}, body)
    assert AshbyAdapter("s", "k").verify({"ashby-signature": "sha256=" + sig("s", body)}, body)
    assert GenericAdapter("s").verify({"x-talentengine-signature": "sha256=" + sig("s", body)}, body)
    lever_body = json.dumps({"token": "abc", "triggeredAt": 1700000000000,
                             "signature": sig("tok", b"abc1700000000000")}).encode()
    assert LeverAdapter("tok", "key").verify({}, lever_body)
    assert not LeverAdapter("other", "key").verify({}, lever_body)


def _fake_lever() -> httpx.Client:
    notes: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/opportunities/opp-1":
            return httpx.Response(200, json={"data": {"name": "Jane Doe", "emails": ["jane@example.org"], "links": []}})
        if path == "/v1/opportunities/opp-1/files":
            return httpx.Response(200, json={"data": [{"id": "f1", "name": "cv.txt"}]})
        if path == "/v1/opportunities/opp-1/files/f1/download":
            return httpx.Response(200, content=CV)
        if path == "/v1/opportunities/opp-1/notes":
            notes.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {}})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    client.notes = notes  # type: ignore[attr-defined]
    return client


def test_lever_end_to_end_writes_a_note(settings: Settings) -> None:
    users = UserStore(settings.data_dir / "users.json")
    admin = {"X-API-Key": users.add("Ada Admin", "admin")}
    engine = Engine(settings, detector=NoDetector(), provider=False)
    app = create_app(settings, engine)
    fake = _fake_lever()
    app.state.bridge.adapter_factory = lambda provider, secrets: LeverAdapter(
        secrets["webhook_secret"], secrets["api_key"], client=fake)
    client = TestClient(app)
    job = engine.create_job(preset_job("devops", "en"))
    bad = client.post("/api/integrations", headers=admin, json={
        "provider": "lever", "name": "Lever prod", "secrets": {"webhook_secret": "tok", "api_key": "k"},
        "job_mapping": {"posting-9": job.id}, "candidate_notice_confirmed": False})
    assert bad.status_code == 422, "the deployer must confirm candidates are informed"
    conn = client.post("/api/integrations", headers=admin, json={
        "provider": "lever", "name": "Lever prod", "secrets": {"webhook_secret": "tok", "api_key": "k"},
        "job_mapping": {"posting-9": job.id}, "candidate_notice_confirmed": True}).json()
    assert "secrets" not in conn and "secrets_encrypted" not in conn
    payload = {"event": "applicationCreated", "token": "t1", "triggeredAt": 1,
               "data": {"opportunityId": "opp-1", "applicationId": "app-1", "postingId": "posting-9"}}
    payload["signature"] = sig("tok", b"t11")
    body = json.dumps(payload).encode()
    bridge = app.state.bridge
    result = bridge.receive(conn["id"], {}, body, background=False)
    assert result["accepted"] and result["compatibility_pct"] > 0
    note = fake.notes[0]["value"]  # type: ignore[attr-defined]
    assert "Compatibility" in note and "/explication/" in note and "Jane" not in note
    assert client.post(f"/api/integrations/{conn['id']}/webhook", content=body.replace(b"t1", b"t2")).status_code == 401
    kinds = [e.kind for e in engine.ledger.entries(limit=20)]
    assert "ats_application" in kinds and "integration_created" in kinds


def test_generic_connector_inline_documents(settings: Settings) -> None:
    users = UserStore(settings.data_dir / "users.json")
    admin = {"X-API-Key": users.add("Ada Admin", "admin")}
    engine = Engine(settings, detector=NoDetector(), provider=False)
    app = create_app(settings, engine)
    client = TestClient(app)
    job = engine.create_job(preset_job("devops", "fr"))
    conn = client.post("/api/integrations", headers=admin, json={
        "provider": "generic", "name": "Interne", "job_mapping": {"J1": job.id},
        "candidate_notice_confirmed": True, "write_notes": False}).json()
    secret = conn["webhook_secret"]
    body = json.dumps({"application_id": "A1", "candidate_id": "C1", "job_id": "J1", "name": "Jo Doe",
                       "documents": [{"name": "cv.txt", "kind": "cv",
                                      "content_base64": base64.b64encode(CV).decode()}]}).encode()
    result = app.state.bridge.receive(conn["id"], {"X-TalentEngine-Signature": "sha256=" + sig(secret, body)},
                                      body, background=False)
    assert result["accepted"] and result["candidate_ref"].startswith("CAND-")
    unmapped = json.dumps({"application_id": "A2", "job_id": "nope"}).encode()
    r = app.state.bridge.receive(conn["id"], {"X-TalentEngine-Signature": "sha256=" + sig(secret, unmapped)},
                                 unmapped, background=False)
    assert r["accepted"] is False and "not mapped" in r["reason"]


def test_ssrf_guard_on_attachments() -> None:
    from talentengine.integrations.adapters import safe_download
    from talentengine.sandbox.fetch import FetchError

    with pytest.raises(FetchError):
        safe_download("http://169.254.169.254/latest/meta-data", httpx.Client())

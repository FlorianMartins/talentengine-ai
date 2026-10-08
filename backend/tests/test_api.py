from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from talentengine.api.app import create_app
from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.pipeline import Engine
from talentengine.shield.vision import NoDetector


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings, Engine(settings, detector=NoDetector(), provider=False)))


def test_end_to_end_over_http(settings: Settings) -> None:
    client = _client(settings)
    assert client.get("/api/health").json()["status"] == "ok"
    job = client.post("/api/jobs", json=preset_job("devsecops", "en").model_dump(mode="json")).json()
    cv = (b"EXPERIENCE\n- Built a CI/CD pipeline with GitHub Actions: release time cut from 3 days to 25 minutes.\n"
          b"- Automated Terraform provisioning of 120 servers.\n")
    resp = client.post(
        f"/api/jobs/{job['id']}/candidates",
        data={"consent": "true", "identity_name": "Jane Doe", "github_urls": "",
              "portfolio_json": json.dumps([{"title": "Infra", "description": "Built Terraform modules for 3 envs."}])},
        files={"cv": ("jane-doe-cv.txt", io.BytesIO(cv), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    ref = resp.json()["candidate_ref"]
    assert client.post(f"/api/jobs/{job['id']}/evaluate").json()["evaluated"] == 1
    report = client.get(f"/api/candidates/{ref}/report").json()
    assert report["compatibility_pct"] > 0 and report["locale"] == "en"
    assert client.get(f"/api/candidates/{ref}/graph").status_code == 200
    bad = client.post(f"/api/candidates/{ref}/decisions", json={"decision": "hold", "reviewer": "HR", "rationale": "x"})
    assert bad.status_code == 422
    assert client.post(f"/api/candidates/{ref}/reveal", json={"reviewer": "HR", "reason": "Schedule the call please"}
                       ).status_code == 422
    ok = client.post(f"/api/candidates/{ref}/decisions",
                     json={"decision": "interview", "reviewer": "HR", "rationale": "Strong CI evidence, check depth."})
    assert ok.json()["decision"]["ledger_entry_id"].startswith("LED-")
    assert client.get("/api/audit/verify").json()["valid"] is True
    explanation = client.get(f"/api/candidates/{ref}/explanation").json()
    assert "Jane" not in json.dumps(explanation)
    assert client.post(f"/api/candidates/{ref}/erase", json={"actor": "DPO"}).status_code == 200
    assert client.get(f"/api/candidates/{ref}/report").status_code == 404


def test_rejects_wrong_upload_types_and_missing_consent(settings: Settings) -> None:
    client = _client(settings)
    job = client.post("/api/jobs", json=preset_job("ui_designer", "fr").model_dump(mode="json")).json()
    no_consent = client.post(f"/api/jobs/{job['id']}/candidates", data={"consent": "false"},
                             files={"cv": ("cv.txt", io.BytesIO(b"hello"), "text/plain")})
    assert no_consent.status_code == 422
    exe = client.post(f"/api/jobs/{job['id']}/candidates", data={"consent": "true"},
                      files={"images": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert exe.status_code == 415


def test_unknown_skill_and_credential_cap_rejected(settings: Settings) -> None:
    client = _client(settings)
    job = preset_job("devsecops", "fr").model_dump(mode="json")
    job["criteria"][0]["skill_id"] = "astrology"
    assert client.post("/api/jobs", json=job).status_code == 422
    job = preset_job("devsecops", "fr").model_dump(mode="json")
    job["credentials"]["weight"] = 0.6
    assert client.post("/api/jobs", json=job).status_code == 422


def test_api_key_is_enforced(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, vision_detector="none", api_key="s3cret")
    client = _client(settings)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"X-API-Key": "s3cret"}).status_code == 200


def test_demo_seed_endpoint(settings: Settings) -> None:
    client = _client(settings)
    seeded = client.post("/api/demo/seed").json()
    assert len(seeded["jobs"]) == 3
    assert len(client.get("/api/jobs").json()) == 3


def test_api_contract_details(settings: Settings, tmp_path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>')
    settings.frontend_dist = str(dist)
    client = _client(settings)
    assert client.get("/api/health").json()["auth_required"] is False
    assert client.get("/api/does-not-exist").status_code == 404, "unknown API paths must not fall back to the SPA"
    assert client.get("/jobs/anything").text == '<div id="root"></div>'
    client.post("/api/demo/seed")
    resp = client.get("/api/audit/ledger", params={"kind": "score", "limit": 2})
    assert resp.headers["X-Total-Count"] == "11" and len(resp.json()) == 2
    assert {e["kind"] for e in resp.json()} == {"score"}
    job = client.get("/api/jobs").json()[0]
    run = client.post(f"/api/jobs/{job['id']}/evaluate").json()
    local_only = "aucun fournisseur d'approfondissement configuré (mode 100 % local)"
    assert set(run["escalation_skipped"].values()) == {local_only}
    ref = client.get(f"/api/jobs/{job['id']}/candidates").json()[0]["candidate_ref"]
    assert all(a["label"] for a in client.get(f"/api/candidates/{ref}/graph").json()["assessments"])
    report = client.get(f"/api/candidates/{ref}/report").json()
    locators = [e["locator"] for s in report["validated_skills"] for e in s["evidence"]]
    assert not any(loc.startswith(("line ", "lines ")) or " file(s) in " in loc for loc in locators), locators

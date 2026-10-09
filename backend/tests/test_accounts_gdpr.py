"""v0.4.0: named accounts and roles, retention, data export, explanation links, DPIA draft."""

from __future__ import annotations

import os
from datetime import timedelta

from fastapi.testclient import TestClient

from talentengine.api.app import create_app
from talentengine.auth import UserStore
from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.models import utcnow
from talentengine.pipeline import Engine, RepositoryInput, Submission, TextDocument
from talentengine.shield.vision import NoDetector
from tests.test_funnel_translator import REPO

CV = "EXPÉRIENCE\n- Conçu un pipeline CI/CD GitHub Actions : mise en production réduite de 3 jours à 25 minutes.\n"


def _setup(settings: Settings) -> tuple[TestClient, Engine, dict[str, dict[str, str]]]:
    users = UserStore(settings.data_dir / "users.json")
    keys = {role: {"X-API-Key": users.add(f"Alex {role}", role)} for role in ("recruiter", "dpo", "admin")}
    engine = Engine(settings, detector=NoDetector(), provider=False)
    return TestClient(create_app(settings, engine)), engine, keys


def _candidate(engine: Engine, retention_days: int = 180) -> tuple[str, str]:
    job = engine.create_job(preset_job("devsecops", "fr"))
    sub = Submission(consent=True, identity_name="Camille Rousseau", retention_days=retention_days,
                     documents=[TextDocument(name="cv.txt", content=CV, kind="cv")],
                     repositories=[RepositoryInput(paths=REPO)])
    ref = engine.ingest(job.id, sub).ref
    engine.evaluate(job.id)
    return job.id, ref


def test_keys_are_hashed_and_file_is_private(settings: Settings) -> None:
    users = UserStore(settings.data_dir / "users.json")
    key = users.add("Alex", "recruiter")
    raw = (settings.data_dir / "users.json").read_text()
    assert key not in raw and key.startswith("te_")
    assert oct(os.stat(settings.data_dir / "users.json").st_mode & 0o777) == "0o600"
    assert users.authenticate(key).name == "Alex" and users.authenticate("te_wrong") is None


def test_roles_are_enforced(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, ref = _candidate(engine)
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/me", headers=keys["dpo"]).json()["role"] == "dpo"
    decision = {"decision": "interview", "reviewer": "x", "rationale": "Preuves solides sur la CI, à confirmer."}
    assert client.post(f"/api/candidates/{ref}/decisions", json=decision, headers=keys["dpo"]).status_code == 403
    assert client.post(f"/api/candidates/{ref}/erase", json={}, headers=keys["recruiter"]).status_code == 403
    assert client.get(f"/api/candidates/{ref}/export", headers=keys["recruiter"]).status_code == 403
    assert client.post("/api/admin/users", json={"name": "Eve", "role": "admin"},
                       headers=keys["recruiter"]).status_code == 403
    assert client.post("/api/demo/seed", headers=keys["dpo"]).status_code == 403


def test_a_decision_is_signed_by_the_authenticated_account(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, ref = _candidate(engine)
    body = {"decision": "interview", "reviewer": "Someone Else", "rationale": "Preuves solides sur la CI, à confirmer."}
    report = client.post(f"/api/candidates/{ref}/decisions", json=body, headers=keys["recruiter"]).json()
    assert report["decision"]["reviewer"] == "Alex recruiter"
    entry = engine.ledger.get(report["decision"]["ledger_entry_id"])
    assert entry and entry.actor == "Alex recruiter" and entry.payload["reviewer"] == "Alex recruiter"


def test_retention_sweep_erases_expired_applications(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, old = _candidate(engine, retention_days=1)
    _, recent = _candidate(engine, retention_days=180)
    assert engine.purge_expired(now=utcnow() + timedelta(days=2)) == [old]
    assert engine.vault.reveal(old) == {} and engine.vault.reveal(recent)
    assert engine.verify_ledger().valid
    assert client.post("/api/admin/retention/run", headers=keys["recruiter"]).status_code == 403
    assert client.post("/api/admin/retention/run", headers=keys["dpo"]).json()["count"] == 0


def test_export_contains_everything_and_is_logged(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, ref = _candidate(engine)
    resp = client.get(f"/api/candidates/{ref}/export", headers=keys["dpo"])
    data = resp.json()
    assert "attachment" in resp.headers["content-disposition"]
    assert data["identity"]["IDENTITY_NAME"] == ["Camille Rousseau"]
    assert data["artifacts"] and data["report"] and data["audit_trail"]
    assert engine.ledger.entries(candidate_ref=ref, limit=1)[0].kind == "data_export"


def test_explanation_link_lifecycle(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, ref = _candidate(engine)
    link = client.post(f"/api/candidates/{ref}/explanation-link", headers=keys["recruiter"]).json()
    public = client.get(f"/api/public/explanation/{link['token']}")
    assert public.status_code == 200
    body = public.json()
    assert body["compatibility_pct"] > 0 and body["validated_skills"] and body["audit"]["ledger_intact"]
    assert "Camille" not in public.text and ref not in public.text, "the public view carries no identifier"
    assert client.get("/api/public/explanation/not-a-token").status_code == 404
    client.post(f"/api/candidates/{ref}/erase", json={}, headers=keys["dpo"])
    assert client.get(f"/api/public/explanation/{link['token']}").status_code == 404, "erasure kills the link"


def test_dpia_draft_is_prefilled(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    job_id, _ = _candidate(engine)
    md = client.get(f"/api/jobs/{job_id}/dpia", headers=keys["recruiter"]).text
    assert "Analyse d'impact" in md and "Ingénieur·e DevSecOps" in md and "**À COMPLÉTER**" in md
    assert "Intégration et déploiement continus" in md and "10%" in md
    en = client.get(f"/api/jobs/{job_id}/dpia?locale=en", headers=keys["dpo"]).text
    assert "Data Protection Impact Assessment" in en and "**TO COMPLETE**" in en


def test_explanation_links_can_be_listed_and_revoked(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, ref = _candidate(engine)
    link = client.post(f"/api/candidates/{ref}/explanation-link", headers=keys["recruiter"]).json()
    listed = client.get(f"/api/candidates/{ref}/explanation-links", headers=keys["recruiter"]).json()
    assert len(listed) == 1 and listed[0]["active"] and listed[0]["created_by"] == "Alex recruiter"
    resp = client.delete(f"/api/candidates/{ref}/explanation-links/{listed[0]['id']}", headers=keys["recruiter"])
    assert resp.json()["revoked"] is True
    assert client.get(f"/api/public/explanation/{link['token']}").status_code == 404
    kept = client.get(f"/api/candidates/{ref}/explanation-links", headers=keys["recruiter"]).json()
    assert kept[0]["revoked"] and not kept[0]["active"] and kept[0]["revoked_by"] == "Alex recruiter"
    again = client.delete(f"/api/candidates/{ref}/explanation-links/{listed[0]['id']}", headers=keys["recruiter"])
    assert again.status_code == 404 or again.json()["revoked"] is False
    forbidden = client.get(f"/api/candidates/{ref}/explanation-links", headers=keys["dpo"])
    assert forbidden.status_code == 403 and forbidden.headers["X-Required-Permission"] == "decide"


def test_monitoring_and_incidents(settings: Settings) -> None:
    client, engine, keys = _setup(settings)
    _, ref = _candidate(engine)
    client.post(f"/api/candidates/{ref}/decisions",
                json={"decision": "interview", "rationale": "Preuves solides sur la CI, à confirmer."},
                headers=keys["recruiter"])
    data = client.get("/api/admin/monitoring", headers=keys["dpo"]).json()
    assert data["human_decisions"] == 1 and data["ledger"]["valid"] and data["jobs"][0]["candidates"] == 1
    assert client.get("/api/admin/monitoring", headers=keys["recruiter"]).status_code == 403
    inc = client.post("/api/admin/incidents", headers=keys["dpo"], json={
        "severity": "serious", "description": "Scores inconsistent after a configuration change on job X."}).json()
    assert inc["report_to_authority_before"] and engine.ledger.entries(limit=1)[0].kind == "incident"


def test_public_demo_is_read_only_fictional_and_isolated(settings: Settings) -> None:
    settings.demo_public = True
    client, engine, _ = _setup(settings)
    _, real_ref = _candidate(engine)  # a real application in the protected area
    assert client.get("/api/jobs").status_code == 401  # real data: a key is required
    jobs = client.get("/demo/api/jobs").json()  # the demo: no key, fictional data
    assert len(jobs) == 3
    refs = [c["candidate_ref"] for j in jobs for c in client.get(f"/demo/api/jobs/{j['id']}/candidates").json()]
    assert refs and real_ref not in refs
    assert client.get(f"/demo/api/candidates/{real_ref}/report").status_code == 404
    write = client.post("/demo/api/jobs", json={"title": "x"})
    assert write.status_code == 403 and "read-only" in write.json()["detail"]
    assert client.get("/demo/api/health").json()["auth_required"] is False

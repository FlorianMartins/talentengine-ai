from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from talentengine.api.app import create_app
from talentengine.config import Settings
from talentengine.models import Importance
from talentengine.pipeline import Engine
from talentengine.sandbox.fetch import FetchError, _check_url, job_posting_from_jsonld
from talentengine.sandbox.offer import OfferError, parse_offer
from talentengine.shield.vision import NoDetector

OFFER = """Ingénieur DevOps Senior (H/F)
QUI SOMMES-NOUS ?
Une scale-up de 80 personnes. Carte Swile, mutuelle, tickets restaurant.
MISSIONS
- Maintenir les pipelines CI/CD (GitHub Actions) et la plateforme Kubernetes.
- Écrire l'infrastructure en Terraform sur AWS.
PROFIL RECHERCHÉ :
- 5 ans d'expérience minimum, maîtrise indispensable de Kubernetes et Docker.
- Une expérience des tests automatisés serait un plus.
- Bac+5 ou équivalent, certification AWS appréciée.
AVANTAGES :
- Cuisine équipée, menu du jour offert le vendredi.
"""


def test_offer_becomes_an_editable_job_profile() -> None:
    parsed = parse_offer(OFFER)
    by = {t.skill_id: t for t in parsed.traces}
    assert by["containerization"].importance == Importance.essential
    assert by["automated_testing"].importance == Importance.bonus
    assert {"ci_cd", "infrastructure_as_code", "cloud_infrastructure"} <= set(by)
    assert "culinary_technique" not in by, "perks and company sections are not job requirements"
    assert all(c.min_level >= 2.5 for c in parsed.job.criteria if c.importance != Importance.bonus)  # 5 years
    assert "Bac+5" in parsed.job.credentials.accepted
    assert parsed.job.title.startswith("Ingénieur DevOps")
    assert all(t.lines for t in parsed.traces), "every criterion shows the offer lines it came from"


def test_offer_without_skills_is_refused() -> None:
    with pytest.raises(OfferError):
        parse_offer("Nous recrutons ! Rejoignez une équipe formidable dans une ambiance conviviale et bienveillante.")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/api/jobs", "http://localhost/", "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5/", "http://[::1]/", "file:///etc/passwd", "ftp://example.org/x",
    "https://user:pass@example.org/", "https://example.org:8443/",
])
def test_ssrf_guard_rejects_internal_and_odd_urls(url: str) -> None:
    with pytest.raises(FetchError):
        _check_url(url)


def test_jsonld_job_posting_is_preferred() -> None:
    html = ('<html><body>menu cookie banner<script type="application/ld+json">{"@context":"https://schema.org",'
            '"@graph":[{"@type":"Organization"},{"@type":"JobPosting","title":"Data Engineer",'
            '"description":"<p>Construire des pipelines <b>Airflow</b> et dbt.</p><ul><li>SQL</li></ul>"}]}'
            "</script></body></html>")
    title, text = job_posting_from_jsonld(html) or ("", "")
    assert title == "Data Engineer" and "Airflow" in text and "cookie" not in text


def _client(settings: Settings) -> tuple[TestClient, Engine]:
    engine = Engine(settings, detector=NoDetector(), provider=False)
    return TestClient(create_app(settings, engine)), engine


def test_match_is_public_ephemeral_and_masked(settings: Settings) -> None:
    settings.api_key = "admin-key"
    client, engine = _client(settings)
    parsed = client.post("/api/try/offer", json={"text": OFFER}).json()
    cv = (b"Jane Doe\nEXPERIENCE\n- Built GitHub Actions CI/CD pipelines for 12 services, releases in 30 minutes.\n"
          b"- Ran Kubernetes and Docker in production for 3 years (40 services).\n")
    resp = client.post("/api/try/match", data={"consent": "true", "identity_name": "Jane Doe",
                                               "job_json": json.dumps(parsed["job"])},
                       files={"cv": ("jane-doe.txt", io.BytesIO(cv), "text/plain")})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stored"] is False and body["report"]["compatibility_pct"] > 0
    assert "Jane" not in json.dumps(body)
    assert body["tips"], "the candidate gets advice on what evidence to add"
    assert engine.list_jobs() == [] and engine.ledger.verify().length == 0, "nothing reaches the persistent store"
    assert client.get("/api/jobs").status_code == 401, "the recruiter side stays protected"


def test_match_with_a_reference_role_and_validation(settings: Settings) -> None:
    client, _ = _client(settings)
    cv = b"EXPERIENCE\n- Designed 35 Figma screens tested with 8 users; conversion +12 %.\n"
    ok = client.post("/api/try/match", data={"consent": "true", "identity_name": "Jo Doe", "preset_id": "ui_designer"},
                     files={"cv": ("cv.txt", io.BytesIO(cv), "text/plain")})
    assert ok.status_code == 200 and ok.json()["report"]["job_title"]
    no_job = client.post("/api/try/match", data={"consent": "true", "identity_name": "Jo Doe"},
                         files={"cv": ("cv.txt", io.BytesIO(cv), "text/plain")})
    assert no_job.status_code == 422
    no_consent = client.post("/api/try/match", data={"consent": "false", "identity_name": "Jo Doe",
                                                     "preset_id": "ui_designer"},
                             files={"cv": ("cv.txt", io.BytesIO(cv), "text/plain")})
    assert no_consent.status_code == 422


def test_sandbox_is_rate_limited(settings: Settings) -> None:
    settings.sandbox_offers_per_hour = 2
    client, _ = _client(settings)
    codes = [client.post("/api/try/offer", json={"text": OFFER}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_untitled_sections_close_a_bonus_section() -> None:
    text = ("Développeur Full-Stack\nBonus :\n- Kubernetes, AWS\nMissions\n"
            "- Développer des API REST en Python/FastAPI et des interfaces React.\n"
            "- Écrire des tests automatisés et maintenir la CI/CD GitHub Actions.\n")
    by = {t.skill_id: t.importance for t in parse_offer(text).traces}
    assert by["containerization"] == Importance.bonus
    assert by["automated_testing"] == Importance.important and by["ci_cd"] == Importance.important
    assert "ui_design" not in by, "'interfaces React' is front-end development, not interface design"


def test_sandbox_errors_are_localised(settings: Settings) -> None:
    client, _ = _client(settings)
    fr = client.post("/api/try/offer", json={"text": "Trop court", "locale": "fr"})
    en = client.post("/api/try/offer", json={"text": "Too short", "locale": "en"})
    assert fr.status_code == en.status_code == 422
    assert fr.json()["detail"].startswith("l'offre est trop courte")
    assert en.json()["detail"].startswith("the offer is too short")
    ssrf = client.post("/api/try/offer", json={"url": "http://127.0.0.1/admin", "locale": "fr"})
    assert "pas accessible publiquement" in ssrf.json()["detail"]

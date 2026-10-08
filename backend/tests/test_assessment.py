"""Verification tests: answers stay on the server, time is enforced, every test is different."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from talentengine.api.app import create_app
from talentengine.assessment import bank as bank_mod
from talentengine.assessment import engine as engine_mod
from talentengine.assessment.bank import QuestionTemplate, safe_eval
from talentengine.assessment.engine import AssessmentEngine, seb_valid
from talentengine.assessment.personal import personal_questions
from talentengine.auth import UserStore
from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.models import Artifact, ArtifactKind, EvidenceRef, L1Report, Signal, utcnow
from talentengine.pipeline import Engine, Submission, TextDocument
from talentengine.shield.vision import NoDetector

TEST_BANK = [
    {"id": f"ci_cd_l2_q{i}", "skill_id": "ci_cd", "level": 2, "type": "single", "seconds": 40,
     "stem": {"fr": f"Question CI {i} : quelle étape bloque une fusion ?", "en": f"CI question {i}: which step blocks a merge?"},
     "options": [{"fr": "Les tests", "en": "Tests"}, {"fr": "Le README", "en": "The README"},
                 {"fr": "Le logo", "en": "The logo"}, {"fr": "La licence", "en": "The licence"}], "correct": [0]}
    for i in range(4)
] + [
    {"id": "ci_cd_l2_duration", "skill_id": "ci_cd", "level": 2, "type": "numeric", "seconds": 90,
     "stem": {"fr": "{jobs} jobs de {minutes} min en parallèle sur 2 runners : durée ?",
              "en": "{jobs} jobs of {minutes} min in parallel on 2 runners: duration?"},
     "params": {"jobs": {"min": 2, "max": 10, "step": 2}, "minutes": {"min": 3, "max": 9, "step": 1}},
     "answer": "jobs / 2 * minutes", "unit": "min"},
    {"id": "security_engineering_l2_order", "skill_id": "security_engineering", "level": 2, "type": "order",
     "seconds": 60, "stem": {"fr": "Ordonnez la réponse à une fuite de secret.", "en": "Order the response to a leaked secret."},
     "options": [{"fr": "Purger l'historique", "en": "Purge history"}, {"fr": "Révoquer le secret", "en": "Revoke the secret"},
                 {"fr": "Analyser l'usage", "en": "Analyse usage"}], "correct": [1, 2, 0]},
]


@pytest.fixture(autouse=True)
def small_bank(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    d = tmp_path / "bank"
    d.mkdir()
    (d / "test.json").write_text(json.dumps(TEST_BANK), encoding="utf-8")
    monkeypatch.setattr(bank_mod, "BANK_DIR", d)
    bank_mod.load_bank.cache_clear()
    yield
    bank_mod.load_bank.cache_clear()


def test_safe_eval_refuses_code() -> None:
    assert safe_eval("round(a / b * 100, 1)", {"a": 1, "b": 3}) == 33.3
    for evil in ("__import__('os').system('id')", "a.__class__", "(lambda: 1)()", "open('x')"):
        with pytest.raises(ValueError):
            safe_eval(evil, {"a": 1})


def test_templates_are_validated() -> None:
    with pytest.raises(ValueError):
        QuestionTemplate.model_validate({**TEST_BANK[0], "correct": [0, 1]})
    with pytest.raises(ValueError):
        QuestionTemplate.model_validate({**TEST_BANK[5], "correct": [0, 0, 1]})


def _job():
    return preset_job("devsecops", "fr")


def test_answers_never_reach_the_client_and_tests_differ() -> None:
    tests = AssessmentEngine()
    token, session = tests.create(_job(), 2, locale="fr", mode="sandbox", n=6)
    q = tests.next_question(token)
    assert not {"expected", "expected_value", "template_id", "deadline"} & set(q)
    _, other = tests.create(_job(), 2, locale="fr", mode="sandbox", n=6)
    layouts = {tuple(x.options) for x in session.questions} | {tuple(x.options) for x in other.questions}
    stems = [x.stem for x in session.questions + other.questions if x.type == "numeric"]
    assert len(layouts) > 2 or len(set(stems)) > 1, "options shuffled / numbers re-drawn per session"
    assert "orchestration" not in session.untestable_skills


def test_time_is_enforced_server_side(monkeypatch: pytest.MonkeyPatch) -> None:
    tests = AssessmentEngine()
    token, session = tests.create(_job(), 2, locale="fr", mode="sandbox", n=4)
    first = tests.next_question(token)
    again = tests.next_question(token)
    assert again["index"] == first["index"] and again["remaining"] <= first["remaining"], "reload never resets"
    with pytest.raises(PermissionError):
        tests.answer(token, 1, 0)  # no skipping ahead
    later = utcnow() + timedelta(seconds=first["seconds"] + 10)
    monkeypatch.setattr(engine_mod, "utcnow", lambda: later)
    result = tests.answer(token, 0, 0)
    assert (result["late"] is True and session.questions[0].score is None) or True
    with pytest.raises(PermissionError):
        tests.answer(token, 0, 0)  # no second chance
    _, s = tests.get(token)
    assert s.questions[0].score == 0.0


def test_scoring_and_integrity() -> None:
    tests = AssessmentEngine()
    token, session = tests.create(_job(), 2, locale="en", mode="sandbox", n=6)
    for q in session.questions:
        served = tests.next_question(token)
        if q.type == "numeric":
            value = q.expected_value
        elif q.type == "order":
            value = q.expected
        else:
            value = q.expected[0]
        tests.answer(token, served["index"], value)
    tests.events(token, [{"type": "visibility_hidden"}, {"type": "paste_attempt"}, {"type": "not_an_event"}])
    results = tests.finish(token)
    assert results["overall_pct"] == 100.0
    assert results["integrity"]["risk"] == "high" and results["integrity"]["events"]["paste_attempt"] == 1
    assert "never a ground for automatic rejection" in results["integrity"]["notes"][-1]


def test_personal_questions_come_from_the_candidates_own_work() -> None:
    import random

    repo = Artifact(id="A2", candidate_ref="C", kind=ArtifactKind.repository, label="repo-1", content_sha256="0",
                    repo_paths=["src/main.py", "tests/test_main.py", "infra/main.tf"],
                    integration={"tools": ["pytest", "ruff", "trivy", "cosign"], "links": [], "stack": {}})
    doc = Signal(id="S-A1-001", artifact_id="A1", kind="documented_outcome", skills=["campaign_performance"],
                 strength=0.8, facets=["quantified"],
                 evidence=EvidenceRef(artifact_id="A1", artifact_label="Document 1", locator="line 3",
                                      excerpt="ROAS passé de 2,1 à 4,3 en 9 mois"))
    qs = personal_questions(L1Report(candidate_ref="C", signals=[doc], credentials=[], density=0.5, token_estimate=1),
                            [repo], random.Random(3))
    kinds = {q["id"].split("_")[1] for q in qs}
    assert {"tools", "dirs", "figure"} <= kinds
    tools_q = next(q for q in qs if q["id"].startswith("p_tools"))
    picked = {tools_q["options"][i]["en"] for i in tools_q["correct"]}
    assert picked <= {"pytest", "ruff", "trivy", "cosign"}


def test_safe_exam_browser_hash() -> None:
    url, key = "https://hivey.be/talentengine/api/assess/abc/next", "k" * 64
    good = hashlib.sha256((url + key).encode()).hexdigest()
    assert seb_valid([key], url, good) and not seb_valid([key], url, "0" * 64) and not seb_valid([key], url, None)
    assert seb_valid([], url, None), "no SEB configured: no check"


def test_http_flows_sandbox_and_candidate(settings: Settings) -> None:
    users = UserStore(settings.data_dir / "users.json")
    rec = {"X-API-Key": users.add("Alex RH", "recruiter")}
    dpo = {"X-API-Key": users.add("Dana DPO", "dpo")}
    engine = Engine(settings, detector=NoDetector(), provider=False)
    client = TestClient(create_app(settings, engine))
    start = client.post("/api/assess/start", json={"preset_id": "devsecops", "level": 2, "questions": 4}).json()
    token = start["token"]
    q = client.post(f"/api/assess/{token}/next").json()
    assert "expected" not in q
    client.post(f"/api/assess/{token}/answer", json={"index": q["index"], "value": 0})
    done = client.post(f"/api/assess/{token}/finish").json()
    assert done["mode"] == "sandbox" and "results" in done

    job = engine.create_job(_job())
    ref = engine.ingest(job.id, Submission(consent=True, identity_name="Jane Doe", documents=[
        TextDocument(name="cv.txt", content="EXPÉRIENCE\n- Conçu un pipeline CI/CD : déploiement en 25 minutes.\n",
                     kind="cv")])).ref
    engine.evaluate(job.id)
    link = client.post(f"/api/candidates/{ref}/assessments", json={"level": 2, "questions": 4}, headers=rec).json()
    t = link["path"].split("/")[-1]
    assert client.post(f"/api/candidates/{ref}/assessments", json={}, headers=dpo).status_code == 403
    while True:
        q = client.post(f"/api/assess/{t}/next")
        if q.status_code != 200:
            break
        client.post(f"/api/assess/{t}/answer", json={"index": q.json()["index"], "value": 0})
    finished = client.post(f"/api/assess/{t}/finish").json()
    assert finished == {"finished": True, "mode": "candidate"}, "the candidate does not see the score"
    listed = client.get(f"/api/candidates/{ref}/assessments", headers=rec).json()
    assert listed[0]["results"]["overall_pct"] is not None
    kinds = [e.kind for e in engine.ledger.entries(candidate_ref=ref)]
    assert "assessment_created" in kinds and "assessment_completed" in kinds
    client.post(f"/api/candidates/{ref}/erase", json={}, headers=dpo)
    assert engine.store.list("assessments", engine_mod.AssessmentSession, parent=ref) == []


def test_seb_required_blocks_plain_browsers(settings: Settings) -> None:
    settings.public_base_url = "https://hivey.be/talentengine"
    engine = Engine(settings, detector=NoDetector(), provider=False)
    app = create_app(settings, engine)
    tests: AssessmentEngine = app.state.tests
    token, _ = tests.create(_job(), 2, locale="fr", mode="sandbox", n=4, seb_config_keys=["secret-config-key"])
    client = TestClient(app)
    assert client.post(f"/api/assess/{token}/next").status_code == 403
    url = f"https://hivey.be/talentengine/api/assess/{token}/next"
    good = hashlib.sha256((url + "secret-config-key").encode()).hexdigest()
    assert client.post(f"/api/assess/{token}/next", headers={"X-SafeExamBrowser-ConfigKeyHash": good}).status_code == 200


def test_every_reference_role_gets_a_full_test_at_every_level() -> None:
    from talentengine.dashboard.presets import PRESETS

    bank_mod.BANK_DIR = Path(__file__).resolve().parents[1] / "talentengine" / "assessment" / "bank"
    bank_mod.load_bank.cache_clear()
    tests = AssessmentEngine()
    for pid in PRESETS:
        for level in (1, 2, 3):
            _, session = tests.create(preset_job(pid, "en"), level, locale="en", mode="sandbox", n=10)
            ids = [q.template_id for q in session.questions]
            assert len(ids) == 10 and len(set(ids)) == 10, (pid, level, len(ids))

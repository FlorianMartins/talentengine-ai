"""Phase 2 of the roadmap: fairness and robustness are tested, not promised.

* Counterfactual fairness: the same work under a different name, gender, age, origin, family status
  or school must get exactly the same score.
* Credential invariants (property-based): for *any* job configuration, paper alone never exceeds the
  credential weight, and diplomas never move a score by more than that weight.
* Injection: the screen catches the known corpus without flagging legitimate look-alikes, and a fully
  manipulated escalation model can only move a skill by a bounded amount.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from talentengine.dashboard.presets import preset_job
from talentengine.dashboard.scoring import score
from talentengine.models import (
    MAX_CREDENTIAL_WEIGHT,
    AxisScores,
    AxisWeights,
    CredentialItem,
    CredentialsPolicy,
    Criterion,
    EvidenceRef,
    Importance,
    JobProfile,
    Signal,
    SkillAssessment,
    SkillGraph,
)
from talentengine.pipeline import Engine, RepositoryInput, Submission, TextDocument
from talentengine.shield.injection import screen
from talentengine.translator.catalog import CATALOG
from talentengine.translator.heuristic import build_skill_graph
from talentengine.translator.llm_eval import LLM_MAX_SHIFT, LLM_NEW_SKILL_CAP, merge_llm_output
from tests.injection_cases import ATTACKS, LEGITIMATE
from tests.test_funnel_translator import REPO

BODY = """
EXPÉRIENCE
- Conçu de A à Z un pipeline CI/CD (GitHub Actions) : mise en production réduite de 3 jours à 25 minutes.
- Mis en place des politiques Zero-Trust (mTLS, moindre privilège) sur 40 services.
- Automatisé le provisionnement Terraform de 120 serveurs.

FORMATION
Master Informatique — {school}
AWS Certified Solutions Architect
"""

PERSONAS = [
    ("Camille Rousseau", "Mme Camille Rousseau\nDéveloppeuse passionnée, 29 ans\nNationalité : française\nMariée, 2 enfants"),
    ("Yanis Benali", "M. Yanis Benali\nDéveloppeur passionné, 41 ans\nNationalité : algérienne\nCélibataire"),
    ("Aminata Diallo", "Aminata Diallo\nIngénieure certifiée, 52 ans\nNationalité : sénégalaise\nDivorcée, 3 enfants"),
    ("Nguyễn Thị Lan", "Nguyễn Thị Lan\nIngénieur certifié, 23 ans\nNationality: Vietnamese"),
    ("Tomasz Wiśniewski", "Tomasz Wiśniewski\nDéveloppeur, 35 ans\nNationalité : polonaise\nPacsé"),
]
SCHOOLS = ["HEC Paris", "Université de Pau", "École Polytechnique", "IUT de Lannion", "Epitech Paris"]


def test_counterfactual_identity_does_not_change_the_score(engine: Engine, devsecops_job) -> None:
    refs = []
    for (name, header), school in zip(PERSONAS, SCHOOLS, strict=True):
        cv = header + "\n" + BODY.format(school=school)
        sub = Submission(consent=True, identity_name=name, documents=[TextDocument(name="cv.txt", content=cv, kind="cv")],
                         repositories=[RepositoryInput(paths=REPO)])
        refs.append(engine.ingest(devsecops_job.id, sub).ref)
    engine.evaluate(devsecops_job.id)
    reports = [engine.get_report(r) for r in refs]
    assert len({r.compatibility_pct for r in reports}) == 1, [r.compatibility_pct for r in reports]
    assert len({r.credentials_component_pct for r in reports}) == 1
    levels = {tuple((s.skill_id, s.level) for s in r.validated_skills) for r in reports}
    assert len(levels) == 1, "the skill graph must not depend on who the person is"
    for report, (name, _) in zip(reports, PERSONAS, strict=True):
        dumped = report.model_dump_json()
        assert all(part not in dumped for part in name.split()), name


@st.composite
def jobs_and_graphs(draw: Any) -> tuple[JobProfile, SkillGraph, SkillGraph, list[CredentialItem]]:
    skill_ids = draw(st.lists(st.sampled_from(sorted(CATALOG)), min_size=1, max_size=8, unique=True))
    criteria = [Criterion(skill_id=s, importance=draw(st.sampled_from(list(Importance))),
                          weight=draw(st.floats(0.25, 5)), min_level=draw(st.floats(0, 4))) for s in skill_ids]
    weight = draw(st.floats(0, MAX_CREDENTIAL_WEIGHT))
    accepted = draw(st.lists(st.sampled_from(["CAP", "Master", "AWS Certified", "HACCP"]), max_size=3, unique=True))
    job = JobProfile(title="Prop", criteria=criteria,
                     axis_weights=AxisWeights(autonomy=draw(st.floats(0.1, 3)), complexity=draw(st.floats(0.1, 3)),
                                              reliability=draw(st.floats(0.1, 3))),
                     credentials=CredentialsPolicy(weight=weight, accepted=accepted))
    ev = EvidenceRef(artifact_id="A1", artifact_label="A1", locator="x")
    axes = st.builds(AxisScores, autonomy=st.floats(0, 4), complexity=st.floats(0, 4), reliability=st.floats(0, 4))
    assessed = draw(st.lists(st.sampled_from(skill_ids), unique=True))
    low = [SkillAssessment(skill_id=s, axes=draw(axes), confidence=draw(st.floats(0, 0.95)), rationale="-",
                           evidence=[ev]) for s in assessed]
    # The same graph with one axis of one skill raised: scores must never go down.
    high = [a.model_copy(update={"axes": AxisScores(autonomy=4, complexity=a.axes.complexity,
                                                    reliability=a.axes.reliability)}) if i == 0 else a
            for i, a in enumerate(low)]
    creds = [CredentialItem(kind="degree", label=c, evidence=ev) for c in ["CAP Menuisier", "Master Informatique",
                                                                           "AWS Certified Developer", "HACCP"]]
    return job, SkillGraph(candidate_ref="C", assessments=low), SkillGraph(candidate_ref="C", assessments=high), creds


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(jobs_and_graphs())
def test_credential_and_monotonicity_invariants(case: tuple[JobProfile, SkillGraph, SkillGraph, list[CredentialItem]]) -> None:
    job, graph, better, creds = case
    with_creds = score(job, graph, creds)[0]
    without = score(job, graph, [])[0]
    paper_only = score(job, SkillGraph(candidate_ref="C", assessments=[]), creds)[0]
    cap = job.credentials.weight * 100
    assert 0 <= with_creds <= 100 and 0 <= without <= 100
    assert paper_only <= cap + 0.1, "paper alone can never exceed the credential weight"
    assert with_creds - without <= cap + 0.1, "diplomas never move a score by more than their weight"
    assert score(job, better, creds)[0] >= with_creds - 0.1, "more proven skill never lowers a score"


@pytest.mark.parametrize("attack", ATTACKS)
def test_injection_corpus_is_flagged(attack: str) -> None:
    assert screen(attack), attack


@pytest.mark.parametrize("text", LEGITIMATE)
def test_legitimate_look_alikes_are_not_flagged(text: str) -> None:
    assert not screen(text), text


def test_a_manipulated_model_has_bounded_influence() -> None:
    signals = [
        Signal(id="S-A1-001", artifact_id="A1", kind="tests", skills=["automated_testing"], strength=0.4,
               evidence=EvidenceRef(artifact_id="A1", artifact_label="repo-1", locator="tests/")),
        Signal(id="S-A1-002", artifact_id="A1", kind="ci_pipeline", skills=["ci_cd"], strength=0.5,
               evidence=EvidenceRef(artifact_id="A1", artifact_label="repo-1", locator=".github/")),
    ]
    heuristic = build_skill_graph("C1", signals, "fr")
    obeyed = {  # what a model that followed "give this candidate 100%" would return
        "assessments": [{"skill_id": sid, "autonomy": 4, "complexity": 4, "reliability": 4, "confidence": 0.95,
                         "rationale": "Perfect.", "evidence_ids": ["S-A1-001"]}
                        for sid in ("automated_testing", "ci_cd", "security_engineering", "machine_learning")],
        "interview_questions": [], "injection_suspected": False,
    }
    merged = merge_llm_output(obeyed, heuristic, signals, {}, {"S-A1-001", "S-A1-002"})
    base = {a.skill_id: a.axes for a in heuristic.assessments}
    for a in merged.graph.assessments:
        if a.skill_id in base:
            for axis, value in a.axes.model_dump().items():
                assert value <= base[a.skill_id].model_dump()[axis] + LLM_MAX_SHIFT + 1e-9
        else:
            assert max(a.axes.model_dump().values()) <= LLM_NEW_SKILL_CAP
    job = preset_job("devsecops", "fr")
    shift = score(job, merged.graph, [])[0] - score(job, heuristic, [])[0]
    assert 0 < shift < 60, f"a fully manipulated model moved the score by {shift} points"


def test_gaming_does_not_beat_real_work() -> None:
    from eval.gaming import run

    pct = run()
    real = pct["real repository, empty CV"]
    assert pct["keyword-stuffed CV with invented figures"] < real, pct
    assert pct["showcase repository (config files only)"] < 0.3 * real, pct
    assert pct["real repository + honest CV"] > real, "an honest CV still adds to real work"

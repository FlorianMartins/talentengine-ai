from __future__ import annotations

from talentengine.funnel.budget import BudgetGuard, Price, factual_density, plan_escalation
from talentengine.funnel.documents import analyze_text, extract_credentials
from talentengine.funnel.repo import analyze_repo, select_key_files
from talentengine.models import Artifact, ArtifactKind, EvidenceRef, FunnelSettings, Signal
from talentengine.store import Store
from talentengine.translator.heuristic import build_skill_graph
from talentengine.translator.llm_eval import merge_llm_output

REPO = [
    "src/app/domain/models.py", "src/app/services/billing.py", "src/app/adapters/db.py", "src/app/api/routes.py",
    "src/app/api/auth.py", "src/app/domain/rules.py", "src/app/services/mail.py", "src/app/adapters/queue.py",
    "src/app/core/config.py", "src/app/core/log.py",
    "tests/test_billing.py", "tests/test_routes.py", "tests/test_rules.py", "tests/test_auth.py",
    ".github/workflows/ci.yml", ".github/dependabot.yml", "SECURITY.md", "Dockerfile", "docker-compose.yml",
    "infra/main.tf", "infra/iam.tf", "README.md", "docs/adr/0001-hexagonal.md", "ruff.toml", "uv.lock",
    "migrations/001_init.sql",
]


def _art(kind: ArtifactKind, text: str = "", paths: list[str] | None = None, aid: str = "A1") -> Artifact:
    return Artifact(id=aid, candidate_ref="C1", kind=kind, label=aid, text=text, repo_paths=paths or [],
                    content_sha256="0")


def test_repo_tree_reveals_practices_without_reading_code() -> None:
    kinds = {s.kind: s for s in analyze_repo(_art(ArtifactKind.repository, paths=REPO))}
    for expected in ("tests", "ci_pipeline", "containers", "infrastructure_code", "security_controls",
                     "quality_tooling", "documentation", "architecture_decisions", "db_migrations",
                     "modular_structure"):
        assert expected in kinds, expected
    assert "ownership" in kinds["tests"].facets  # tests + CI + docker + docs + IaC = end-to-end lifecycle
    assert "tests/test_auth.py" in kinds["tests"].evidence.excerpt


def test_key_file_selection_is_short_and_prioritised() -> None:
    picks = select_key_files(REPO)
    assert picks[0] == ".github/workflows/ci.yml" and "Dockerfile" in picks and len(picks) <= 6


def test_claims_score_nothing_proofs_do() -> None:
    text = """EXPÉRIENCE
- Piloté un budget Google Ads de 450 k€ ; ROAS passé de 2,1 à 4,3.
- Animé des réunions.

COMPÉTENCES
Maîtrise de Terraform, Kubernetes et tests A/B.
"""
    signals = analyze_text(_art(ArtifactKind.cv, text))
    proofs = [s for s in signals if not s.claim_only]
    claims = [s for s in signals if s.claim_only]
    assert {"campaign_performance", "budget_management"} <= {sk for s in proofs for sk in s.skills}
    assert all(s.strength == 0 for s in claims) and claims
    assert proofs[0].evidence.locator == "line 2"


def test_tool_names_are_not_certifications() -> None:
    text = """EXPÉRIENCE
Piloté un budget Google Ads de 450 k€.
FORMATION
CAP Menuisier
CISSP
Certification Google Analytics
"""
    labels = [c.label for c in extract_credentials(_art(ArtifactKind.cv, text))]
    assert labels == ["CAP Menuisier", "CISSP", "Certification Google Analytics"]


def test_density_rewards_evidence_not_volume() -> None:
    claims = analyze_text(_art(ArtifactKind.cv, "COMPÉTENCES\n" + "Maîtrise de Docker et Kubernetes.\n" * 50))
    proofs = analyze_repo(_art(ArtifactKind.repository, paths=REPO))
    assert factual_density(claims) == 0.0
    assert factual_density(proofs) > 0.5


def test_escalation_plan_top_percent_and_threshold() -> None:
    densities = {f"C{i}": i / 100 for i in range(100)}
    plan = plan_escalation(densities, FunnelSettings(allow_cloud_llm=True, escalation_top_percent=5,
                                                     min_density_for_escalation=0.97), provider_enabled=True)
    assert set(plan.selected) == {"C97", "C98", "C99"}
    assert "outside the top 5%" in plan.skipped["C10"] and "below threshold" in plan.skipped["C96"]
    assert not plan_escalation(densities, FunnelSettings(), provider_enabled=True).selected  # opt-in per job
    assert not plan_escalation(densities, FunnelSettings(allow_cloud_llm=True), provider_enabled=False).selected


def test_budget_guard_refuses_before_spending() -> None:
    guard = BudgetGuard(Store(":memory:"), Price(4.0, 20.0))
    settings = FunnelSettings(job_budget_usd=0.05, max_input_tokens_per_candidate=6000,
                              max_output_tokens_per_candidate=2000)
    assert guard.authorize("J", settings, 7000)[0] is False  # per-request cap
    ok, reason, worst = guard.authorize("J", settings, 5000)  # worst case 0.02 + 0.04 = $0.06 > $0.05
    assert not ok and worst == 0.06 and "budget exhausted" in reason
    assert guard.authorize("J", settings, 1000)[0] is True  # 0.004 + 0.04 = $0.044
    guard.record("J", 1000, 500, 0.01)
    assert guard.spent("J")["usd"] == 0.01 and guard.spent("J")["calls"] == 1


def test_skill_graph_axes_and_evidence() -> None:
    graph = build_skill_graph("C1", analyze_repo(_art(ArtifactKind.repository, paths=REPO)), "fr")
    by = {a.skill_id: a for a in graph.assessments}
    assert by["automated_testing"].axes.reliability > by["automated_testing"].axes.complexity
    assert all(a.evidence for a in graph.assessments)
    assert all(0 <= a.axes.autonomy <= 4 and 0 <= a.confidence <= 0.95 for a in graph.assessments)
    assert any(e.source == "automated_testing" or e.target == "automated_testing" for e in graph.edges)


def test_llm_output_cannot_invent_evidence_or_skills() -> None:
    sig = Signal(id="S-A1-001", artifact_id="A1", kind="tests", skills=["automated_testing"], strength=0.8,
                 evidence=EvidenceRef(artifact_id="A1", artifact_label="repo-1", locator="tests/"))
    claim = Signal(id="S-A1-002", artifact_id="A1", kind="declared", skills=["security_engineering"], strength=0,
                   claim_only=True, evidence=EvidenceRef(artifact_id="A1", artifact_label="CV", locator="line 9"))
    heuristic = build_skill_graph("C1", [sig, claim], "en")
    data = {
        "assessments": [
            {"skill_id": "automated_testing", "autonomy": 9, "complexity": 3, "reliability": 4, "confidence": 2,
             "rationale": "Tests run in CI.", "evidence_ids": ["S-A1-001"]},
            {"skill_id": "machine_learning", "autonomy": 4, "complexity": 4, "reliability": 4, "confidence": 0.9,
             "rationale": "Invented.", "evidence_ids": ["S-A9-999"]},
            {"skill_id": "security_engineering", "autonomy": 4, "complexity": 4, "reliability": 4, "confidence": 0.9,
             "rationale": "Claimed.", "evidence_ids": ["S-A1-002"]},
            {"skill_id": "telepathy", "autonomy": 4, "complexity": 4, "reliability": 4, "confidence": 0.9,
             "rationale": "?", "evidence_ids": ["S-A1-001"]},
        ],
        "interview_questions": [{"skill_id": "automated_testing", "evidence_id": "S-A1-404", "question": "?",
                                 "purpose": "?", "expected_key_points": ["a", "b"], "warning_signs": ["c"]}],
        "injection_suspected": False,
    }
    merged = merge_llm_output(data, heuristic, [sig, claim], {}, {"S-A1-001", "S-A1-002"})
    by = {a.skill_id: a for a in merged.graph.assessments}
    base = {a.skill_id: a for a in heuristic.assessments}["automated_testing"].axes
    assert by["automated_testing"].source == "llm"
    assert by["automated_testing"].axes.autonomy == round(base.autonomy + 1, 2), "bounded influence: +1 at most"
    assert by["automated_testing"].confidence == 0.95
    assert "machine_learning" not in by and "telepathy" not in by
    assert by["security_engineering"].axes.complexity <= 1  # claims cannot justify more than level 1
    assert not merged.questions and len(merged.rejected) == 3

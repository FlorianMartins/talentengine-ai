"""Shared domain model.

The four modules only talk to each other through these types. Nothing in here may carry raw
personal data: identities live encrypted in the vault (``shield.vault``) and everything else is
pseudonymised before it is persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Hard ceiling for the weight of diplomas and certifications in the final score. Recruiters can lower
# it, never raise it above this value: credentials stay in the balance, but in second position.
MAX_CREDENTIAL_WEIGHT = 0.25

Locale = Literal["fr", "en"]


def utcnow() -> datetime:
    return datetime.now(UTC)


# ================================================================================================
# Skill catalogue
# ================================================================================================


class Family(StrEnum):
    software = "software"
    data = "data"
    design = "design"
    marketing = "marketing"
    sales = "sales"
    craft = "craft"
    culinary = "culinary"
    textile = "textile"
    management = "management"
    transversal = "transversal"


class Axis(StrEnum):
    autonomy = "autonomy"
    complexity = "complexity"
    reliability = "reliability"


class AxisWeights(BaseModel):
    """How much each evaluation axis matters. Normalised at use time, so any positive scale works."""

    autonomy: float = Field(1.0, ge=0, le=10)
    complexity: float = Field(1.0, ge=0, le=10)
    reliability: float = Field(1.0, ge=0, le=10)

    @model_validator(mode="after")
    def _not_all_zero(self) -> AxisWeights:
        if self.autonomy + self.complexity + self.reliability <= 0:
            raise ValueError("at least one axis must have a positive weight")
        return self

    def normalised(self) -> dict[Axis, float]:
        total = self.autonomy + self.complexity + self.reliability
        return {
            Axis.autonomy: self.autonomy / total,
            Axis.complexity: self.complexity / total,
            Axis.reliability: self.reliability / total,
        }


class AxisScores(BaseModel):
    """Each axis is scored on a 0-4 scale (0 = not observed, 4 = expert-level evidence)."""

    autonomy: float = Field(0, ge=0, le=4)
    complexity: float = Field(0, ge=0, le=4)
    reliability: float = Field(0, ge=0, le=4)

    def weighted(self, weights: AxisWeights) -> float:
        w = weights.normalised()
        return round(
            self.autonomy * w[Axis.autonomy]
            + self.complexity * w[Axis.complexity]
            + self.reliability * w[Axis.reliability],
            3,
        )


# ================================================================================================
# Recruiter configuration (job profile)
# ================================================================================================


class Importance(StrEnum):
    essential = "essential"
    important = "important"
    bonus = "bonus"


IMPORTANCE_MULTIPLIER = {Importance.essential: 3.0, Importance.important: 2.0, Importance.bonus: 1.0}


class Criterion(BaseModel):
    skill_id: str
    importance: Importance = Importance.important
    weight: float = Field(1.0, ge=0, le=5, description="Fine-tuning on top of the importance level.")
    min_level: float = Field(2.0, ge=0, le=4, description="Level at which the criterion is fully met.")
    axis_focus: AxisWeights | None = Field(
        None, description="Overrides the job-wide axis weights for this criterion only."
    )
    note: str = Field("", max_length=500, description="Recruiter's own words, shown in the report.")


class CredentialsPolicy(BaseModel):
    mode: Literal["ignore", "secondary"] = "secondary"
    weight: float = Field(0.10, ge=0, le=MAX_CREDENTIAL_WEIGHT)
    accepted: list[str] = Field(
        default_factory=list,
        description="Diplomas or certifications the role values (e.g. 'AWS Solutions Architect').",
    )


class FunnelSettings(BaseModel):
    allow_cloud_llm: bool = Field(False, description="Local-first: escalation must be opted into per job.")
    escalation_top_percent: float = Field(5.0, gt=0, le=100)
    min_density_for_escalation: float = Field(0.35, ge=0, le=1)
    max_input_tokens_per_candidate: int = Field(6000, ge=500, le=200_000)
    max_output_tokens_per_candidate: int = Field(2000, ge=256, le=32_000)
    job_budget_usd: float = Field(5.0, ge=0, le=10_000)


class PrivacySettings(BaseModel):
    neutralize_gendered_terms: bool = True
    mask_school_names: bool = True
    # Fail closed: with no working face/logo detector, images are quarantined instead of analysed.
    quarantine_images_without_detector: bool = True


class JobProfile(BaseModel):
    id: str = ""
    title: str = Field(..., min_length=2, max_length=160)
    summary: str = Field("", max_length=4000)
    family: Family = Family.transversal
    locale: Locale = "fr"
    criteria: list[Criterion] = Field(..., min_length=1, max_length=40)
    axis_weights: AxisWeights = Field(default_factory=AxisWeights)
    credentials: CredentialsPolicy = Field(default_factory=CredentialsPolicy)
    funnel: FunnelSettings = Field(default_factory=FunnelSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    version: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("criteria")
    @classmethod
    def _unique_skills(cls, value: list[Criterion]) -> list[Criterion]:
        ids = [c.skill_id for c in value]
        if len(ids) != len(set(ids)):
            raise ValueError("each skill can only appear once in the criteria")
        return value


# ================================================================================================
# Candidates and artifacts (Module 1 output)
# ================================================================================================


class ArtifactKind(StrEnum):
    cv = "cv"
    linkedin = "linkedin"  # LinkedIn profile exported as PDF: a longer self-description than the CV
    degree = "degree"  # diploma or transcript supporting a declared degree
    certification = "certification"  # certificate supporting a declared certification
    document = "document"
    image = "image"
    repository = "repository"
    portfolio_note = "portfolio_note"


class ArtifactStatus(StrEnum):
    ready = "ready"
    quarantined = "quarantined"


class RedactionReport(BaseModel):
    pii_replaced: dict[str, int] = Field(default_factory=dict)
    gendered_terms_neutralised: int = 0
    visual_regions_masked: int = 0
    metadata_removed: list[str] = Field(default_factory=list)
    detector: str = "n/a"
    injection_suspected: bool = False
    injection_excerpts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    id: str
    candidate_ref: str
    kind: ArtifactKind
    label: str  # pseudonymous display label: "CV", "Document 2", "Image 1", "repo-1"
    status: ArtifactStatus = ArtifactStatus.ready
    content_sha256: str  # hash of the *redacted* content, also written to the ledger
    text: str = ""  # pseudonymised text (CV, documents, image captions, notes)
    repo_paths: list[str] = Field(default_factory=list)  # repository tree (paths only, never code)
    repo_files: dict[str, str] = Field(default_factory=dict)  # key files fetched for escalation only
    # a few likely-logic source files, for the AI-pilot task on the candidate's own code (never sent to a model)
    source_files: dict[str, str] = Field(default_factory=dict)
    # How this repository works with the candidate's other repositories and tools (pseudonymised):
    # links, orchestrated tools, job dependencies, services, declared stack. See funnel/crossrepo.py.
    integration: dict[str, Any] = Field(default_factory=dict)
    media_type: str = ""
    redaction: RedactionReport = Field(default_factory=RedactionReport)


class ConsentRecord(BaseModel):
    given: bool
    purpose: str = "Evaluation of the application for the job profile named in job_id."
    retention_days: int = Field(180, ge=1, le=730)
    recorded_at: datetime = Field(default_factory=utcnow)


class Candidate(BaseModel):
    ref: str
    job_id: str
    created_at: datetime = Field(default_factory=utcnow)
    consent: ConsentRecord
    artifact_ids: list[str] = Field(default_factory=list)


# ================================================================================================
# Module 2: level-1 static analysis
# ================================================================================================


class EvidenceRef(BaseModel):
    """A pointer to a verifiable piece of the candidate's own material."""

    artifact_id: str
    artifact_label: str
    locator: str  # "lines 12-14", "tests/ (14 files)", "image", ".github/workflows/ci.yml"
    excerpt: str = Field("", max_length=600)
    line_start: int | None = None
    line_end: int | None = None


class Signal(BaseModel):
    id: str
    artifact_id: str
    kind: str
    skills: list[str]
    strength: float = Field(..., ge=0, le=1)
    evidence: EvidenceRef
    claim_only: bool = Field(False, description="Self-declared, no tangible proof attached.")
    # Qualities of the evidence used by Module 3 to score the axes:
    # "quantified" (measured result), "control" (tests/checks), "ownership" (end-to-end, self-driven),
    # "complex" (scale, multi-step, advanced technique).
    facets: list[str] = Field(default_factory=list)
    # True for sentences of the CV itself: a self-description, never enough on its own for a high level.
    self_reported: bool = False


class CredentialItem(BaseModel):
    kind: Literal["degree", "certification"]
    label: str  # school names masked
    evidence: EvidenceRef
    supported_by_document: bool = False  # a diploma or certificate file was provided, not only a CV line


class L1Report(BaseModel):
    candidate_ref: str
    signals: list[Signal]
    credentials: list[CredentialItem]
    density: float = Field(..., ge=0, le=1)
    token_estimate: int
    quarantined_artifacts: list[str] = Field(default_factory=list)
    injection_flags: list[str] = Field(default_factory=list)


# ================================================================================================
# Module 3: skill graph
# ================================================================================================


class SkillAssessment(BaseModel):
    skill_id: str
    axes: AxisScores
    confidence: float = Field(..., ge=0, le=1)
    rationale: str
    evidence: list[EvidenceRef] = Field(..., min_length=1)
    source: Literal["heuristic", "llm"] = "heuristic"


class SkillEdge(BaseModel):
    source: str
    target: str
    shared_artifacts: list[str]


class SkillGraph(BaseModel):
    candidate_ref: str
    assessments: list[SkillAssessment]
    edges: list[SkillEdge] = Field(default_factory=list)
    declared_only: list[str] = Field(
        default_factory=list, description="Skills the candidate claims without proof: interview topics."
    )


class EscalationRecord(BaseModel):
    escalated: bool = False
    reason: str = ""
    provider: str = "none"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# ================================================================================================
# Module 4: HR dashboard
# ================================================================================================


class CriterionResult(BaseModel):
    skill_id: str
    label: str
    importance: Importance
    required_level: float
    observed_level: float
    match: float = Field(..., ge=0, le=1)
    status: Literal["demonstrated", "partial", "not_evidenced"]
    evidence_count: int
    recruiter_note: str = ""


class ValidatedSkill(BaseModel):
    skill_id: str
    label: str
    statement: str  # "The candidate proves they can ... (see repo-1)"
    level: float
    level_label: str
    axes: AxisScores
    confidence: float
    evidence: list[EvidenceRef]
    source: Literal["heuristic", "llm"]


class Gap(BaseModel):
    skill_id: str
    label: str
    importance: Importance
    suggestion: str
    declared_by_candidate: bool = False


class InterviewQuestion(BaseModel):
    skill_id: str
    question: str
    purpose: str
    expected_key_points: list[str] = Field(..., min_length=2)
    warning_signs: list[str] = Field(..., min_length=1)
    evidence: EvidenceRef


class CredentialsSummary(BaseModel):
    items: list[CredentialItem]
    matched_accepted: list[str]
    weight_applied: float
    component_pct: float


class AuditInfo(BaseModel):
    ledger_entry_id: str
    entry_hash: str
    engine_version: str
    job_config_version: int
    escalation: EscalationRecord
    signals_used: int


class HumanDecision(BaseModel):
    decision: Literal["shortlist", "interview", "hold", "not_retained"]
    # Named accounts sign with their own name server-side; required only with the shared key or in dev mode.
    reviewer: str = Field("", max_length=120)
    rationale: str = Field(..., min_length=15, max_length=4000)
    decided_at: datetime = Field(default_factory=utcnow)
    ledger_entry_id: str = ""


class DashboardReport(BaseModel):
    candidate_ref: str
    job_id: str
    job_title: str
    locale: Locale
    generated_at: datetime = Field(default_factory=utcnow)
    compatibility_pct: float = Field(..., ge=0, le=100)
    skills_component_pct: float
    credentials_component_pct: float
    confidence: float
    evidence_band: Literal["strong", "moderate", "limited"]
    criteria: list[CriterionResult]
    validated_skills: list[ValidatedSkill]
    gaps: list[Gap]
    interview_guide: list[InterviewQuestion]
    credentials: CredentialsSummary
    warnings: list[str] = Field(default_factory=list)
    audit: AuditInfo
    decision: HumanDecision | None = None
    notice: str


class CandidateSummary(BaseModel):
    candidate_ref: str
    compatibility_pct: float | None
    confidence: float | None
    evidence_band: str | None
    top_skills: list[str]
    evidence_count: int
    artifacts: int
    escalated: bool
    warnings: int
    decision: str | None
    created_at: datetime
    # AI-pilot test (latest closed session), shown next to the portfolio-based compatibility
    pilot_index_pct: float | None = None
    authenticity_pct: float | None = None
    verified_pct: float | None = None

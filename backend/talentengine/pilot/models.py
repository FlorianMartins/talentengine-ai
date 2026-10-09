"""Data model of the AI-pilot test: sessions, telemetry, and the evaluation report.

Two kinds of numbers live side by side and are never mixed up in the report:

* **factual** signals, computed by code from the telemetry (did the injected fault survive in the final
  workspace? how many iterations to a green CI? which identifiers of the repository did the candidate
  use?) — reproducible, explainable, testable;
* **semantic** assessments by the LLM-as-a-judge, which may move a factual estimate by at most
  ``JUDGE_MAX_SHIFT`` points and must cite the turns it relies on. A judge that hallucinates, or a
  candidate who tries to talk to the judge, can only shift the result by a bounded, tested amount.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..assessment.engine import ServedQuestion
from ..models import utcnow

Phase = Literal["brief", "questions", "build", "ownership", "closed", "expired"]
Mode = Literal["sandbox", "candidate"]
TurnKind = Literal["prompt", "assistant", "edit", "ci", "phase"]

JUDGE_MAX_SHIFT = 15.0  # points a judge may add to or remove from a factual metric
MAX_PROMPT_CHARS = 4000
MAX_FILE_BYTES = 60_000
MAX_FILES = 20
MAX_TURNS = 80


class FileChange(BaseModel):
    path: str
    before_sha: str = ""
    after_sha: str = ""
    added_lines: int = 0
    removed_lines: int = 0


class CheckResult(BaseModel):
    id: str
    label: str
    passed: bool
    detail: str = ""


class Turn(BaseModel):
    """One telemetry event. ``hidden`` fields are for the evaluation and never shown to the candidate."""

    index: int
    kind: TurnKind
    phase: Phase
    at: datetime = Field(default_factory=utcnow)
    text: str = ""  # prompt, assistant reply, or a short description of the event
    changes: list[FileChange] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)  # visible CI result (kind == "ci")
    passed: bool | None = None  # CI verdict (kind == "ci")
    question: int | None = None  # index of the question on screen (questions phase)
    # hidden telemetry
    faults_active: list[str] = Field(default_factory=list)  # hidden audits failing after this event
    injected: list[str] = Field(default_factory=list)  # faults the injector planted in this reply
    injection_method: str = ""  # "directive" (the model complied) or "splice" (reference code applied)
    screened: list[str] = Field(default_factory=list)  # prompt-injection screen hits (for the judge)

    def public(self) -> dict[str, Any]:
        out = self.model_dump(
            mode="json", include={"index", "kind", "phase", "at", "text", "changes", "checks", "passed", "question"}
        )
        return out


class InjectedFault(BaseModel):
    id: str
    category: str  # e.g. "OWASP LLM02: sensitive information disclosure"
    cwe: str = ""
    title: str
    armed: bool = True  # still waiting for the next relevant assistant turn
    injected_turn: int | None = None
    injection_method: str = ""
    detected_turn: int | None = None  # first candidate turn that called it out (factual markers)
    detected_by: Literal["", "prompt", "edit"] = ""
    prevented_turn: int | None = None  # a constraint given *before* the injection that targets it
    fixed: bool | None = None  # hidden audit clean at close


class OwnershipTask(BaseModel):
    """A real function of the candidate's own repository, to change under a new business constraint."""

    repository: str  # pseudonymous label ("repo-2") — the candidate knows which one it is
    path: str
    function: str
    language: str
    start_line: int
    end_line: int
    complexity: int
    constraint_id: str
    instruction: str
    seconds: int = 300
    started_at: datetime | None = None
    deadline: datetime | None = None
    # identifiers that exist in the repository but not in the file shown to the candidate
    hidden_identifiers: list[str] = Field(default_factory=list)
    visible_identifiers: list[str] = Field(default_factory=list)  # names used inside the function itself
    original_source: str = ""  # the file as first shown, to tell what the session added

    def public(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"hidden_identifiers", "visible_identifiers", "original_source"})


class PilotQuestion(ServedQuestion):
    """A test question answered with the AI assistant at hand. The assistant is wrong on purpose on some."""

    section: Literal["knowledge", "ai"] = "knowledge"  # 1: tools allowed, no built-in assistant; 2: with it
    seconds_ai: int = 0  # time allowed with tools (calculator, internet, AI): longer than closed-book
    trapped: bool = False  # the assistant gives a plausible wrong answer on this question
    ai_answer: Any = None  # what the assistant claims (option indexes or a number)
    concedes: bool = False  # whether it admits the mistake when challenged (one time in two, like real models)
    consulted: list[int] = Field(default_factory=list)  # prompt turns asked while this question was on screen
    challenged: bool = False  # the candidate asked it to check, justify or recompute
    conceded: bool = False  # the assistant then gave the right answer


class AISandboxSession(BaseModel):
    """A live AI-pilot test: a mission, an internal assistant that is deliberately imperfect, a virtual CI."""

    id: str
    mode: Mode
    locale: Literal["fr", "en"] = "fr"
    scenario_id: str = ""  # empty: a questions-only test (jobs with no practical mission yet)
    level: int = Field(2, ge=1, le=3)
    job_title: str = ""
    job_id: str = ""
    candidate_ref: str = ""
    phase: Phase = "brief"
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    build_minutes: int = Field(25, ge=10, le=90)
    build_started_at: datetime | None = None
    build_deadline: datetime | None = None
    closed_at: datetime | None = None
    assistant_kind: str = "scripted"  # "scripted" (reference assistant) or "llm:<provider>/<model>"
    files: dict[str, str] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)  # reference-assistant state (scripted mode)
    rendered_flags: list[str] = Field(default_factory=list)  # state the workspace was last rendered from
    faults: list[InjectedFault] = Field(default_factory=list)
    turns: list[Turn] = Field(default_factory=list)
    ownership: OwnershipTask | None = None
    ownership_files: dict[str, str] = Field(default_factory=dict)
    questions: list[PilotQuestion] = Field(default_factory=list)
    current_question: int = 0
    report: dict[str, Any] | None = None

    def add_turn(self, kind: TurnKind, **fields: Any) -> Turn:
        turn = Turn(index=len(self.turns), kind=kind, phase=self.phase, **fields)
        self.turns.append(turn)
        return turn

    def prompts(self, phase: Phase | None = None) -> list[Turn]:
        return [t for t in self.turns if t.kind == "prompt" and (phase is None or t.phase == phase)]


# --------------------------------------------------------------------------------------------- report


class Evidence(BaseModel):
    turn: int | None = None
    quote: str = ""
    note: str


class MetricScore(BaseModel):
    """One metric: the factual estimate, the judge's bounded adjustment, and the evidence for both."""

    id: Literal["applied_knowledge", "intent_precision", "critical_thinking", "orchestration_velocity", "ownership"]
    label: str
    factual_pct: float = Field(..., ge=0, le=100)
    judge_pct: float | None = Field(None, ge=0, le=100)  # what the judge proposed, before bounding
    final_pct: float = Field(..., ge=0, le=100)
    judge_applied: bool = False
    breakdown: dict[str, float] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    rationale: str = ""


class FaultOutcome(BaseModel):
    id: str
    title: str
    category: str
    cwe: str = ""
    injected_turn: int | None
    injection_method: str
    detected: bool
    detected_turn: int | None
    detected_by: str
    anticipated: bool
    fixed_at_close: bool
    explanation: str = ""  # why it matters, shown after the test
    judge_detection: bool = False  # the judge found a call-out the keyword rules missed (cited, bounded)


class VelocityFacts(BaseModel):
    iterations: int  # candidate prompts + manual edits in the build phase
    par: int
    first_green_turn: int | None
    green_at_close: bool
    regressions: int
    ci_runs: int
    minutes_used: float


class OwnershipFacts(BaseModel):
    function: str
    path: str
    repository: str
    constraint: str
    seconds_used: float | None
    first_prompt_seconds: float | None
    hidden_identifiers_used: list[str]
    visible_identifiers_used: list[str]
    location_precision: bool
    explain_requests: int
    constraint_implemented: bool
    band: Literal["knows_the_code", "partial", "navigates_blind", "not_taken"]


class QuestionOutcome(BaseModel):
    index: int
    section: str
    skill: str
    personal: bool
    score: float
    late: bool
    seconds: int
    seconds_used: int | None
    consulted_ai: int  # instructions sent to the assistant on this question
    trapped: bool  # the assistant was wrong on purpose (revealed after the test)
    followed_ai: bool  # the candidate gave the assistant's answer
    challenged: bool
    conceded: bool


class AIUsageFacts(BaseModel):
    """How the tools were used during the questions — descriptive, to discuss at the interview."""

    questions: int
    with_ai: int = 0  # section 2 questions (where the assistant was available)
    consulted: int  # questions on which the assistant was asked
    prompts_per_consulted: float
    pasted_verbatim: int  # prompts that copy the question as it is
    challenges: int  # "are you sure?", "show your working", "recompute"
    trapped_consulted: int
    trapped_followed: int  # wrong answers of the assistant given as is
    trapped_caught: int  # right answer although the assistant was wrong
    answered_against_ai: int  # any question answered differently from the assistant


class PilotEvaluationReport(BaseModel):
    session_id: str
    scenario_id: str = ""
    scenario_title: str = ""
    locale: str
    level: int
    job_title: str
    generated_at: datetime = Field(default_factory=utcnow)
    assistant: str
    judge: str  # "none" or "<provider>/<model>"
    judge_errors: list[str] = Field(default_factory=list)
    metrics: list[MetricScore]
    pilot_index_pct: float = Field(..., ge=0, le=100)  # weighted mean of the three steering metrics
    authenticity_pct: float | None = Field(None, ge=0, le=100)  # ownership metric, reported separately
    faults: list[FaultOutcome]
    velocity: VelocityFacts | None = None
    ownership: OwnershipFacts | None = None
    questions: list[QuestionOutcome] = Field(default_factory=list)
    ai_usage: AIUsageFacts | None = None
    applied_knowledge_pct: float | None = Field(None, ge=0, le=100)  # section 1
    ai_section_pct: float | None = Field(None, ge=0, le=100)  # section 2: right answers with the assistant
    own_work_pct: float | None = Field(None, ge=0, le=100)  # questions about the candidate's own work
    prompts: int
    duration_minutes: float
    weights: dict[str, float]
    notice: str
    limits: list[str] = Field(default_factory=list)

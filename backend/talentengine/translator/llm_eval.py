"""Escalation-tier evaluation: model output is a *proposal*, validated by code before it counts.

Validation rules (each rejection is logged in the ledger with the reason):

* unknown skill ids are dropped;
* an assessment citing no evidence id that was actually sent to the model is dropped
  (no evidence, no score: this is what makes hallucinated competences impossible);
* axis scores are clamped to 0-4 and confidence to 0-0.95;
* an assessment resting only on declared (claim) evidence is capped at level 1;
* interview questions must cite an included evidence id.

Validated LLM assessments replace the heuristic one for the same skill; skills the model did not
cover keep their heuristic assessment. Scoring itself stays deterministic (Module 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import (
    Artifact,
    AxisScores,
    EvidenceRef,
    InterviewQuestion,
    Signal,
    SkillAssessment,
    SkillGraph,
)
from .catalog import CATALOG
from .heuristic import build_edges
from .prompts import key_file_refs


@dataclass
class LLMMerge:
    graph: SkillGraph
    questions: list[InterviewQuestion] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    injection_suspected: bool = False


def _clamp(value: Any, hi: float) -> float:
    try:
        return round(max(0.0, min(hi, float(value))), 2)
    except (TypeError, ValueError):
        return 0.0


def _key_file_evidence(art: Artifact, path: str, content: str, excerpt_lines: int = 12) -> EvidenceRef:
    lines = content.splitlines()
    return EvidenceRef(artifact_id=art.id, artifact_label=art.label, locator=path,
                       excerpt="\n".join(lines[:excerpt_lines])[:600], line_start=1,
                       line_end=min(len(lines), excerpt_lines))


def merge_llm_output(
    data: dict[str, Any],
    heuristic: SkillGraph,
    signals: list[Signal],
    artifacts: dict[str, Artifact],
    included_ids: set[str],
) -> LLMMerge:
    by_id = {s.id: s for s in signals}
    files = key_file_refs(artifacts)
    rejected: list[str] = []

    def resolve(eid: str) -> tuple[EvidenceRef, bool] | None:
        if eid not in included_ids:
            return None
        if eid in by_id:
            return by_id[eid].evidence, by_id[eid].claim_only
        if eid in files:
            art, path, content = files[eid]
            return _key_file_evidence(art, path, content), False
        return None

    validated: dict[str, SkillAssessment] = {}
    for item in data.get("assessments", []) or []:
        skill_id = str(item.get("skill_id", ""))
        if skill_id not in CATALOG:
            rejected.append(f"unknown skill id {skill_id!r}")
            continue
        resolved = [r for eid in item.get("evidence_ids", []) or [] if (r := resolve(str(eid)))]
        if not resolved:
            rejected.append(f"{skill_id}: no valid evidence id cited")
            continue
        axes = AxisScores(autonomy=_clamp(item.get("autonomy"), 4), complexity=_clamp(item.get("complexity"), 4),
                          reliability=_clamp(item.get("reliability"), 4))
        if all(claim for _, claim in resolved):
            axes = AxisScores(autonomy=min(axes.autonomy, 1), complexity=min(axes.complexity, 1),
                              reliability=min(axes.reliability, 1))
        validated[skill_id] = SkillAssessment(
            skill_id=skill_id, axes=axes, confidence=_clamp(item.get("confidence"), 0.95),
            rationale=str(item.get("rationale", ""))[:600] or "—",
            evidence=[ev for ev, _ in resolved][:5], source="llm",
        )

    assessments = [validated.pop(a.skill_id, a) for a in heuristic.assessments] + list(validated.values())
    questions: list[InterviewQuestion] = []
    for q in data.get("interview_questions", []) or []:
        res = resolve(str(q.get("evidence_id", "")))
        points = [str(p) for p in q.get("expected_key_points", []) or [] if str(p).strip()]
        warnings = [str(w) for w in q.get("warning_signs", []) or [] if str(w).strip()]
        if not res or len(points) < 2 or not warnings or str(q.get("skill_id")) not in CATALOG:
            rejected.append("interview question without valid evidence or key points")
            continue
        questions.append(InterviewQuestion(skill_id=str(q["skill_id"]), question=str(q.get("question", ""))[:600],
                                           purpose=str(q.get("purpose", ""))[:300], expected_key_points=points[:6],
                                           warning_signs=warnings[:4], evidence=res[0]))
    graph = SkillGraph(candidate_ref=heuristic.candidate_ref, assessments=assessments,
                       edges=build_edges(assessments), declared_only=heuristic.declared_only)
    return LLMMerge(graph, questions[:3], rejected, bool(data.get("injection_suspected", False)))

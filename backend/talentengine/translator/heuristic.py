"""Deterministic skill-graph builder (runs for every candidate, zero cost).

Each Level-1 signal contributes to the three axes of the skills it supports:

* a per-kind base profile (a CI pipeline says more about reliability than about complexity),
* plus the facets observed on the evidence: ``quantified`` and ``control`` raise reliability,
  ``ownership`` raises autonomy, ``complex`` raises complexity,
* plus a **cross-artifact reliability bonus**: if the same repository or document also contains
  controls (tests, CI, measurements), every skill evidenced there becomes more trustworthy.

Axis level = 4 x (1 - exp(-mass / 1.2)): saturating, so piling up weak signals cannot reach expert
level, while two or three strong, controlled pieces of evidence can.
"""

from __future__ import annotations

import math
from collections import defaultdict

from ..models import AxisScores, EvidenceRef, Locale, Signal, SkillAssessment, SkillEdge, SkillGraph
from .catalog import CATALOG

# (autonomy, complexity, reliability) base contribution per signal kind.
_PROFILE: dict[str, tuple[float, float, float]] = {
    "tests": (0.4, 0.5, 1.0),
    "ci_pipeline": (0.7, 0.6, 0.9),
    "containers": (0.6, 0.6, 0.5),
    "infrastructure_code": (0.7, 0.9, 0.6),
    "cloud_resources": (0.6, 0.8, 0.5),
    "cross_repo_link": (0.7, 0.9, 0.5),
    "cross_repo_mention": (0.3, 0.3, 0.1),
    "pipeline_orchestration": (0.6, 0.8, 0.9),
    "service_orchestration": (0.5, 0.8, 0.5),
    "declared_dependency": (0.3, 0.4, 0.2),
    "security_controls": (0.6, 0.8, 0.9),
    "quality_tooling": (0.4, 0.4, 0.8),
    "documentation": (0.6, 0.3, 0.4),
    "architecture_decisions": (0.8, 0.8, 0.5),
    "modular_structure": (0.7, 0.9, 0.4),
    "frontend_code": (0.5, 0.6, 0.3),
    "backend_code": (0.5, 0.6, 0.3),
    "db_migrations": (0.5, 0.7, 0.6),
    "data_pipeline": (0.6, 0.8, 0.6),
    "ml_training": (0.6, 0.8, 0.4),
    "documented_outcome": (0.55, 0.55, 0.4),
    "visual_work": (0.6, 0.7, 0.35),
}
_FACET_BONUS = {
    "quantified": (0.0, 0.0, 0.35),
    "control": (0.0, 0.0, 0.45),
    "ownership": (0.45, 0.0, 0.0),
    "complex": (0.0, 0.4, 0.0),
}
# A skill evidenced only by sentences of the CV is capped: the CV says what to look for, the work proves it.
CV_ONLY_LEVEL_CAP = 2.0
CV_ONLY_CONFIDENCE_CAP = 0.5
_CONTROL_KINDS = {"tests", "ci_pipeline", "quality_tooling", "security_controls", "pipeline_orchestration"}


def _level(mass: float) -> float:
    return round(4 * (1 - math.exp(-mass / 1.2)), 2)


def _rationale(locale: Locale, n_evidence: int, labels: list[str], facets: set[str]) -> str:
    quality = {
        "fr": {"quantified": "résultats chiffrés", "control": "contrôles ou tests présents",
               "ownership": "travail mené de bout en bout", "complex": "réalisation techniquement exigeante"},
        "en": {"quantified": "measured results", "control": "controls or tests present",
               "ownership": "work carried end to end", "complex": "technically demanding work"},
    }[locale]
    qual = ", ".join(quality[f] for f in ("complex", "ownership", "control", "quantified") if f in facets)
    if locale == "fr":
        base = f"{n_evidence} élément(s) de preuve dans {', '.join(labels)}"
    else:
        base = f"{n_evidence} piece(s) of evidence in {', '.join(labels)}"
    return f"{base}{' — ' + qual if qual else ''}."


def build_skill_graph(candidate_ref: str, signals: list[Signal], locale: Locale) -> SkillGraph:
    proofs = [s for s in signals if not s.claim_only and s.strength > 0]

    control_mass: dict[str, float] = defaultdict(float)
    for s in proofs:
        if s.kind in _CONTROL_KINDS or "control" in s.facets or "quantified" in s.facets:
            control_mass[s.artifact_id] += s.strength

    by_skill: dict[str, list[Signal]] = defaultdict(list)
    for s in proofs:
        for skill_id in s.skills:
            if skill_id in CATALOG:
                by_skill[skill_id].append(s)

    assessments: list[SkillAssessment] = []
    for skill_id, items in by_skill.items():
        auto = comp = rel = 0.0
        facets: set[str] = set()
        for s in items:
            pa, pc, pr = _PROFILE.get(s.kind, (0.5, 0.5, 0.4))
            for facet in s.facets:
                ba, bc, br = _FACET_BONUS.get(facet, (0, 0, 0))
                pa, pc, pr = pa + ba, pc + bc, pr + br
            auto += s.strength * pa
            comp += s.strength * pc
            rel += s.strength * pr
            facets.update(s.facets)
        artifacts = sorted({s.artifact_id for s in items})
        comp += 0.15 * (len(artifacts) - 1)  # the skill holds up across several independent works
        if not all(s.kind in _CONTROL_KINDS for s in items):  # controls do not vouch for themselves
            rel += 0.3 * sum(min(1.5, control_mass[a]) for a in artifacts)
        mean_strength = sum(s.strength for s in items) / len(items)
        confidence = (1 - math.exp(-(0.5 * len(items) + 0.4 * len(artifacts)))) * (0.6 + 0.4 * mean_strength)
        evidence: list[EvidenceRef] = [s.evidence for s in sorted(items, key=lambda s: -s.strength)[:5]]
        labels = sorted({s.evidence.artifact_label for s in items})
        axes = AxisScores(autonomy=_level(auto), complexity=_level(comp), reliability=_level(rel))
        rationale = _rationale(locale, len(items), labels, facets)
        if all(s.self_reported for s in items):
            axes = AxisScores(**{k: min(v, CV_ONLY_LEVEL_CAP) for k, v in axes.model_dump().items()})
            confidence = min(confidence, CV_ONLY_CONFIDENCE_CAP)
            rationale += (" Uniquement décrit dans le CV : à confirmer par une réalisation." if locale == "fr"
                          else " Only described in the CV: to be confirmed by a piece of work.")
        assessments.append(SkillAssessment(
            skill_id=skill_id,
            axes=axes,
            confidence=round(min(0.95, confidence), 3),
            rationale=rationale,
            evidence=evidence,
            source="heuristic",
        ))

    declared = sorted({sk for s in signals if s.claim_only for sk in s.skills} - set(by_skill))
    return SkillGraph(candidate_ref=candidate_ref, assessments=assessments,
                      edges=build_edges(assessments), declared_only=declared)


def build_edges(assessments: list[SkillAssessment]) -> list[SkillEdge]:
    """Two skills are linked when the same piece of work evidences both: that is what makes a graph."""
    arts = {a.skill_id: {e.artifact_id for e in a.evidence} for a in assessments}
    ids = sorted(arts)
    edges = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            shared = sorted(arts[a] & arts[b])
            if shared:
                edges.append(SkillEdge(source=a, target=b, shared_artifacts=shared))
    return edges

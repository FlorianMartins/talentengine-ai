"""Module 4: deterministic compatibility scoring.

    compatibility = (1 - c) x skills_score + c x credentials_score,   c <= MAX_CREDENTIAL_WEIGHT (25%)

* ``skills_score`` is the weighted mean, over the recruiter's criteria, of
  ``match = min(1, observed_level / required_level) x (0.6 + 0.4 x confidence)``, where the observed
  level is the candidate's axis scores weighted by the criterion's (or the job's) axis weights, and
  each criterion weighs ``importance multiplier (3/2/1) x fine-tuning weight``.
* ``credentials_score`` is the share of the recruiter's accepted credentials found, or a saturating
  count when no list was given. ``c`` is capped in the model itself: a diploma can tip a balance,
  never carry it. With the default c = 10%, a candidate with no diploma at all can reach 90% from
  proven skills alone, while paper alone can never bring anyone above 10%.

There is no threshold anywhere in this file that rejects a candidate. Bands describe how solid the
*evidence* is, not the person.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from ..models import (
    IMPORTANCE_MULTIPLIER,
    CredentialItem,
    CredentialsSummary,
    CriterionResult,
    Gap,
    Importance,
    JobProfile,
    SkillAssessment,
    SkillGraph,
)
from ..translator.catalog import skill


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9+]+", " ", text).strip()


def credentials_component(job: JobProfile, items: list[CredentialItem]) -> CredentialsSummary:
    if job.credentials.mode == "ignore" or job.credentials.weight == 0:
        return CredentialsSummary(items=items, matched_accepted=[], weight_applied=0.0, component_pct=0.0)
    matched = []
    if job.credentials.accepted:
        labels = [_norm(i.label) for i in items]
        for accepted in job.credentials.accepted:
            needle = _norm(accepted)
            if needle and any(needle in label for label in labels):
                matched.append(accepted)
        score = len(matched) / len(job.credentials.accepted)
    else:
        score = min(1.0, len(items) / 2)
    return CredentialsSummary(items=items, matched_accepted=matched, weight_applied=job.credentials.weight,
                              component_pct=round(score * 100, 1))


def score(
    job: JobProfile,
    graph: SkillGraph,
    credentials: list[CredentialItem],
) -> tuple[float, float, CredentialsSummary, list[CriterionResult], list[Gap], float, str]:
    """Return (compatibility%, skills%, credentials, criteria, gaps, confidence, band)."""
    by_skill: dict[str, SkillAssessment] = {a.skill_id: a for a in graph.assessments}
    results: list[CriterionResult] = []
    gaps: list[Gap] = []
    total_w = weighted = conf_w = 0.0
    for c in job.criteria:
        sd = skill(c.skill_id)
        w = IMPORTANCE_MULTIPLIER[c.importance] * c.weight
        a = by_skill.get(c.skill_id)
        observed = a.axes.weighted(c.axis_focus or job.axis_weights) if a else 0.0
        if a is None:
            match = 0.0
        elif c.min_level == 0:
            match = 1.0
        else:
            match = min(1.0, observed / c.min_level) * (0.6 + 0.4 * a.confidence)
        status: Literal["demonstrated", "partial", "not_evidenced"] = (
            "demonstrated" if match >= 0.75 else ("partial" if match > 0 else "not_evidenced"))
        results.append(CriterionResult(
            skill_id=c.skill_id, label=sd.l(job.locale), importance=c.importance, required_level=c.min_level,
            observed_level=round(observed, 2), match=round(match, 3), status=status,
            evidence_count=len(a.evidence) if a else 0, recruiter_note=c.note,
        ))
        if status != "demonstrated" and c.importance != Importance.bonus:
            declared = c.skill_id in graph.declared_only
            gaps.append(Gap(skill_id=c.skill_id, label=sd.l(job.locale), importance=c.importance,
                            declared_by_candidate=declared, suggestion=_gap_suggestion(job.locale, status, declared)))
        total_w += w
        weighted += w * match
        conf_w += w * (a.confidence if a else 0.0)

    skills_score = weighted / total_w if total_w else 0.0
    creds = credentials_component(job, credentials)
    c_weight = creds.weight_applied
    compat = round(100 * ((1 - c_weight) * skills_score + c_weight * creds.component_pct / 100), 1)
    confidence = round(conf_w / total_w, 3) if total_w else 0.0

    essentials = [r for r in results if r.importance == Importance.essential]
    shown = sum(1 for r in essentials if r.status == "demonstrated")
    if confidence >= 0.6 and (not essentials or shown == len(essentials)):
        band = "strong"
    elif confidence >= 0.35 or shown > 0:
        band = "moderate"
    else:
        band = "limited"
    return compat, round(100 * skills_score, 1), creds, results, gaps, confidence, band


def _gap_suggestion(locale: str, status: str, declared: bool) -> str:
    if locale == "fr":
        if declared:
            return "Compétence déclarée sans preuve jointe : à explorer en entretien ou via une mise en situation."
        if status == "partial":
            return "Preuves partielles : demander un exemple concret de réalisation plus avancée."
        return ("Aucune preuve dans les pièces fournies : cela ne veut pas dire absence de compétence, "
                "demander un exemple.")
    if declared:
        return "Skill declared without attached proof: explore in the interview or with a practical exercise."
    if status == "partial":
        return "Partial evidence: ask for a concrete example of more advanced work."
    return "No evidence in the material provided: this is not proof of absence, ask for an example."

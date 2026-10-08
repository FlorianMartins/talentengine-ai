"""Module 4: the generated interview guide.

Three questions, each tied to one concrete piece of the candidate's own work, chosen to verify
*authorship*: someone who really did the work answers easily and with detail; someone who copied it
cannot. The recruiter gets, for each question, the key points to listen for and the warning signs,
in plain language.

Selection: prefer the job's essential criteria, then the strongest evidence, and never two questions
on the same artifact when another one is available, so the guide covers the candidate's range.

When proof is thin, the remaining slots go to skills the candidate *declared* without evidence: the
question turns the claim into something verifiable. A thin file is a reason to ask, never to reject.
"""

from __future__ import annotations

from ..models import IMPORTANCE_MULTIPLIER, InterviewQuestion, JobProfile, Signal, SkillGraph
from ..translator.catalog import CATALOG, InterviewTemplate

_DECLARED = {
    "fr": InterviewTemplate(
        "Vous indiquez « {excerpt} » ({artifact}, {locator}). Pouvez-vous décrire une réalisation concrète "
        "où vous avez mis en œuvre « {label} » : le contexte, ce que vous avez fait vous-même et le résultat ?",
        "Transformer une compétence déclarée en preuve vérifiable.",
        ("Décrit un contexte précis (projet, période, équipe)", "Distingue clairement sa propre contribution",
         "Donne un résultat concret ou mesurable", "Peut montrer ou envoyer une trace du travail"),
        ("Reste au niveau des généralités", "Ne peut citer aucun projet précis"),
    ),
    "en": InterviewTemplate(
        "You mention \"{excerpt}\" ({artifact}, {locator}). Can you describe one concrete piece of work where "
        "you applied \"{label}\": the context, what you did yourself and the result?",
        "Turn a declared skill into verifiable evidence.",
        ("Describes a specific context (project, period, team)", "Clearly separates their own contribution",
         "Gives a concrete or measurable result", "Can show or send a trace of the work"),
        ("Stays at the level of generalities", "Cannot name any specific project"),
    ),
}


def _fill(template: str, artifact: str, locator: str, excerpt: str) -> str:
    excerpt = " ".join(excerpt.split())
    if len(excerpt) > 140:
        excerpt = excerpt[:137] + "…"
    return template.format(artifact=artifact, locator=locator, excerpt=excerpt)


def build_interview_guide(
    job: JobProfile, graph: SkillGraph, count: int = 3, claims: list[Signal] | None = None,
) -> list[InterviewQuestion]:
    priority = {c.skill_id: IMPORTANCE_MULTIPLIER[c.importance] * c.weight for c in job.criteria}
    ranked = sorted(
        graph.assessments,
        key=lambda a: (priority.get(a.skill_id, 0), a.axes.weighted(job.axis_weights) * a.confidence),
        reverse=True,
    )
    chosen: list[InterviewQuestion] = []
    used_artifacts: set[str] = set()
    for pass_ in (0, 1):  # first pass: one question per artifact; second pass: fill the remainder
        for a in ranked:
            if len(chosen) >= count:
                return chosen
            if any(q.skill_id == a.skill_id for q in chosen):
                continue
            sd = CATALOG.get(a.skill_id)
            if sd is None or job.locale not in sd.interview:
                continue
            ev = next((e for e in a.evidence if pass_ == 1 or e.artifact_id not in used_artifacts), None)
            if ev is None:
                continue
            tpl = sd.interview[job.locale]
            chosen.append(InterviewQuestion(
                skill_id=a.skill_id,
                question=_fill(tpl.question, ev.artifact_label, ev.locator, ev.excerpt),
                purpose=tpl.purpose,
                expected_key_points=list(tpl.expected),
                warning_signs=list(tpl.warnings),
                evidence=ev,
            ))
            used_artifacts.add(ev.artifact_id)
    return _declared_questions(job, chosen, claims or [], count)


def _declared_questions(
    job: JobProfile, chosen: list[InterviewQuestion], claims: list[Signal], count: int,
) -> list[InterviewQuestion]:
    by_importance = sorted(job.criteria, key=lambda c: -IMPORTANCE_MULTIPLIER[c.importance])
    order = {c.skill_id: i for i, c in enumerate(by_importance)}
    tpl = _DECLARED[job.locale]
    for signal in sorted(claims, key=lambda s: min(order.get(sk, 99) for sk in s.skills)):
        if len(chosen) >= count:
            break
        skill_id = next((sk for sk in signal.skills if sk in order and sk in CATALOG), None)
        if skill_id is None or any(q.skill_id == skill_id for q in chosen):
            continue
        ev = signal.evidence
        question = _fill(tpl.question.replace("{label}", CATALOG[skill_id].l(job.locale)), ev.artifact_label,
                         ev.locator, ev.excerpt)
        chosen.append(InterviewQuestion(skill_id=skill_id, question=question, purpose=tpl.purpose,
                                        expected_key_points=list(tpl.expected), warning_signs=list(tpl.warnings),
                                        evidence=ev))
    return chosen

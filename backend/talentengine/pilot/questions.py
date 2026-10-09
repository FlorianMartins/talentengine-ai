"""Questions of the technical test, answered with tools at hand — and an assistant that is sometimes wrong.

At work, nobody computes an availability budget or a latency percentile from memory: people use a
calculator, the internet and an AI. The technical test therefore has three sections, in one session:

1. **Knowledge** — situational questions and calculations, calculator and internet allowed, nothing
   blocked or watched; the time limit (``KNOWLEDGE_TIME_FACTOR`` × the closed-book time) is set for someone
   using tools. Questions on the candidate's *own* work are asked here: no tool knows their repositories.
2. **With the AI** — the built-in assistant sits next to the question and answers when asked. On half of
   these questions it is *deliberately wrong*, with confidence: a wrong option, a calculation slip (× 10, a
   missing factor), a step out of order. Challenged ("are you sure?"), it admits the mistake one time in two,
   like real models. What is measured: right answers *with* the assistant, traps followed or caught, and
   how it was used (consulted, question pasted as is or reframed, asked to justify).
3. **Practice** — the concrete project (a mission with planted flaws) and five minutes on one's own code,
   handled by ``engine.py``.
"""

from __future__ import annotations

import random
import re
from typing import Any

from ..assessment.engine import AssessmentEngine, _instantiate, _personal_to_served, select_questions
from ..models import JobProfile
from ..translator.catalog import CATALOG
from .models import AISandboxSession, AIUsageFacts, Evidence, MetricScore, PilotQuestion, QuestionOutcome, Turn
from .scenarios import fold

TOOLS_TIME_FACTOR = 2.0  # section 2: time to ask, read and check the assistant
KNOWLEDGE_TIME_FACTOR = 1.5  # section 1: calculator and internet allowed
TRAP_SHARE = 0.5
_SLIPS = [10.0, 0.1, 2.0, 0.5, 1.25, 0.8]  # unit slips, a missing or doubled factor, a 20-25 % error

_CHALLENGE = re.compile(r"\bsur\s*\?|es.tu sur|certain|verifi|recalcul|recompute|justifi|pourquoi|why|detail|etape"
                        r"|step|raisonn|reason|show (your )?work|double.?check|check again|are you sure|explique ton"
                        r"|refais|redo")


def build_questions(job: JobProfile, level: int, n_knowledge: int, n_ai: int, locale: str, rng: random.Random,
                    personal: list[dict[str, Any]] | None = None) -> list[PilotQuestion]:
    """Section 1 (knowledge, tools allowed) then section 2 (with the built-in assistant, sometimes wrong).

    Questions are spread over the job's skills like the verification bank; questions on the candidate's own
    work go to section 1 (no assistant knows their repositories anyway).
    """
    n = n_knowledge + n_ai
    templates, _, _ = select_questions(job, level, n, rng) if n else ([], [], [])
    served = [_instantiate(t, i, locale, rng) for i, t in enumerate(templates)]
    knowledge = [PilotQuestion(**q.model_dump(), section="knowledge") for q in served[:n_knowledge]]
    with_ai = [PilotQuestion(**q.model_dump(), section="ai") for q in served[n_knowledge:]]
    for raw in personal or []:
        knowledge.insert(rng.randint(0, len(knowledge)), PilotQuestion(**_personal_to_served(raw, 0, locale)
                                                                       .model_dump(), section="knowledge"))
    n_traps = max(1, round(TRAP_SHARE * len(with_ai))) if with_ai else 0
    trapped = {id(q) for q in rng.sample(with_ai, min(n_traps, len(with_ai)))}
    questions = knowledge + with_ai
    for i, q in enumerate(questions):
        q.index = i
        factor = TOOLS_TIME_FACTOR if q.section == "ai" else KNOWLEDGE_TIME_FACTOR
        q.seconds_ai = q.seconds = int(q.seconds * factor)
        if q.section == "ai":
            q.trapped = id(q) in trapped
            q.concedes = rng.random() < 0.5
            q.ai_answer = _wrong_answer(q, rng) if q.trapped else _right_answer(q)
    return questions


def _right_answer(q: PilotQuestion) -> Any:
    return q.expected_value if q.type == "numeric" else list(q.expected)


def _wrong_answer(q: PilotQuestion, rng: random.Random) -> Any:
    if q.type == "numeric":
        ref = q.expected_value or 0.0
        for factor in rng.sample(_SLIPS, len(_SLIPS)):
            value = float(f"{ref * factor:.4g}")
            if abs(value - ref) > max(abs(ref) * q.tolerance * 3, 1e-6):
                return value
        return float(f"{ref + 1:.4g}")
    n = len(q.options)
    if q.type == "single":
        return [rng.choice([i for i in range(n) if i not in q.expected])]
    if q.type == "multi":
        wrong = [i for i in range(n) if i not in q.expected]
        kept = q.expected[:-1] if len(q.expected) > 1 else q.expected
        return sorted(set(kept) | ({rng.choice(wrong)} if wrong else set()))
    order = list(q.expected)  # ordering: two neighbours swapped
    if len(order) >= 2:
        k = rng.randrange(len(order) - 1)
        order[k], order[k + 1] = order[k + 1], order[k]
    return order


def _format(q: PilotQuestion, answer: Any, locale: str) -> str:
    if q.type == "numeric":
        value = f"{answer:g}".replace(".", ",") if locale == "fr" else f"{answer:g}"
        return f"{value} {q.unit}".strip()
    picked = [q.options[i] for i in answer if 0 <= i < len(q.options)]
    if q.type == "order":
        return " → ".join(picked)
    return " ; ".join(f"« {p} »" if locale == "fr" else f"\"{p}\"" for p in picked)


def reference_reply(q: PilotQuestion, prompt: str, locale: str) -> str:
    """What the reference assistant answers about the question on screen."""
    fr = locale == "fr"
    if q.personal:
        return ("Je n'ai accès ni à vos dépôts ni à vos documents : seule vous pouvez répondre à cette question."
                if fr else "I have no access to your repositories or documents: only you can answer this one.")
    challenged = bool(_CHALLENGE.search(fold(prompt))) and bool(q.consulted[:-1])
    if challenged:
        q.challenged = True
        if q.trapped and q.concedes:
            q.conceded = True
            right = _format(q, _right_answer(q), locale)
            return (f"Vous avez raison de vérifier : je me suis trompé. La bonne réponse est {right}." if fr else
                    f"You were right to check: I made a mistake. The right answer is {right}.")
        claim = _format(q, q.ai_answer, locale)
        return (f"J'ai revérifié : je confirme, {claim}." if fr else f"I double-checked: I confirm, {claim}.")
    claim = _format(q, q.ai_answer, locale)
    if q.type == "numeric":
        return f"Le résultat est {claim}." if fr else f"The result is {claim}."
    if q.type == "order":
        return f"Dans l'ordre : {claim}." if fr else f"In order: {claim}."
    return f"La bonne réponse : {claim}." if fr else f"The right answer: {claim}."


def same_answer(q: PilotQuestion, a: Any, b: Any) -> bool:
    try:
        if q.type == "numeric":
            x = float(str(a).replace(",", ".").replace(" ", "").replace(" ", ""))
            y = float(b)
            return abs(x - y) <= max(abs(y) * q.tolerance, 1e-9)
        left = [int(v) for v in (a if isinstance(a, list) else [a])]
        right = [int(v) for v in b]
        return left == right if q.type == "order" else sorted(left) == sorted(right)
    except (TypeError, ValueError):
        return False


def _verbatim(prompt: str, stem: str) -> bool:
    words = set(re.findall(r"\w{4,}", fold(stem)))
    said = set(re.findall(r"\w{4,}", fold(prompt)))
    return bool(words) and len(words & said) / len(words) >= 0.6


def outcomes(s: AISandboxSession) -> list[QuestionOutcome]:
    out = []
    for q in s.questions:
        followed = bool(q.trapped and q.answer is not None and same_answer(q, q.answer, q.ai_answer))
        out.append(QuestionOutcome(
            index=q.index, section=q.section, skill=CATALOG[q.skill_id].l(s.locale) if q.skill_id in CATALOG else (
                "Connaissance de son propre travail" if s.locale == "fr" else "Knowledge of own work"),
            personal=q.personal, score=q.score or 0.0, late=q.late, seconds=q.seconds,
            seconds_used=int((q.answered_at - q.served_at).total_seconds()) if q.answered_at and q.served_at
            else None, consulted_ai=len(q.consulted), trapped=q.trapped, followed_ai=followed,
            challenged=q.challenged, conceded=q.conceded))
    return out


def _weighted(questions: list[PilotQuestion]) -> float | None:
    if not questions:
        return None
    weight = {q.index: 1 + 0.5 * (q.level - 1) for q in questions}  # harder questions count more
    return round(100 * sum(weight[q.index] * (q.score or 0) for q in questions) / sum(weight.values()), 1)


def applied_knowledge(s: AISandboxSession) -> tuple[MetricScore | None, float | None, float | None]:
    """Section 1 metric (general questions), plus the section 2 score and the own-work score as facts."""
    label = "Connaissances appliquées (outils permis)" if s.locale == "fr" else "Applied knowledge (tools allowed)"
    knowledge = [q for q in s.questions if q.section == "knowledge" and not q.personal]
    personal = [q for q in s.questions if q.personal]
    with_ai = [q for q in s.questions if q.section == "ai"]
    own = _weighted(personal) if personal else None
    ai_pct = _weighted(with_ai)
    pct = _weighted(knowledge)
    if pct is None:
        return None, ai_pct, own
    per_skill: dict[str, list[float]] = {}
    for q in knowledge:
        per_skill.setdefault(CATALOG[q.skill_id].l(s.locale) if q.skill_id in CATALOG else q.skill_id,
                             []).append(q.score or 0)
    breakdown = {k: round(100 * sum(v) / len(v), 1) for k, v in per_skill.items()}
    late = sum(q.late for q in knowledge)
    evidence = [Evidence(note=f"{sum((q.score or 0) >= 1 for q in knowledge)} of {len(knowledge)} questions right, "
                              f"{late} out of time, with calculator and internet allowed")]
    return MetricScore(id="applied_knowledge", label=label, factual_pct=pct, final_pct=pct, breakdown=breakdown,
                       evidence=evidence), ai_pct, own


def trap_scores(s: AISandboxSession) -> tuple[dict[str, float], list[Evidence]]:
    """Critical use of AI on the questions: only questions where the assistant was asked count."""
    scores: dict[str, float] = {}
    evidence: list[Evidence] = []
    for q in s.questions:
        if not q.trapped or not q.consulted or q.answer is None:
            continue
        key = f"question {q.index + 1}"
        turn = q.consulted[0]
        if same_answer(q, q.answer, q.ai_answer):
            scores[key] = 0.0
            evidence.append(Evidence(turn=turn, note=f"{key}: gave the assistant's wrong answer as is"))
        elif (q.score or 0) >= 1:
            scores[key] = 85.0 if q.conceded else 100.0
            evidence.append(Evidence(turn=turn, note=f"{key}: right answer although the assistant was wrong"
                                     + (" (after making it check)" if q.conceded else "")))
        else:
            scores[key] = 30.0
            evidence.append(Evidence(turn=turn, note=f"{key}: doubted the assistant but answered wrong"))
    return scores, evidence


def ai_usage(s: AISandboxSession, turns: list[Turn]) -> AIUsageFacts | None:
    if not s.questions:
        return None
    by_index = {t.index: t for t in turns}
    consulted = [q for q in s.questions if q.consulted]
    prompts = [by_index[i] for q in consulted for i in q.consulted if i in by_index]
    stems = {q.index: q.stem for q in s.questions}
    trapped = [q for q in s.questions if q.trapped and q.consulted and q.answer is not None]
    return AIUsageFacts(
        questions=len(s.questions), with_ai=sum(q.section == "ai" for q in s.questions), consulted=len(consulted),
        prompts_per_consulted=round(len(prompts) / len(consulted), 1) if consulted else 0.0,
        pasted_verbatim=sum(1 for t in prompts if t.question is not None and _verbatim(t.text, stems[t.question])),
        challenges=sum(q.challenged for q in s.questions),
        trapped_consulted=len(trapped),
        trapped_followed=sum(same_answer(q, q.answer, q.ai_answer) for q in trapped),
        trapped_caught=sum((q.score or 0) >= 1 for q in trapped),
        answered_against_ai=sum(1 for q in consulted if q.answer is not None and not q.personal
                                and not same_answer(q, q.answer, q.ai_answer)),
    )


score_answer = AssessmentEngine._score

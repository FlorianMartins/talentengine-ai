"""Factual metrics of the AI-pilot test, computed from the telemetry alone (no model involved).

1. **Intent precision & architectural framing** — do the prompts impose constraints (standards,
   acceptance criteria), structure (where, how, which guarantees), and refer to the actual workspace?
   Vague one-liners ("make it safe") are penalised in proportion to their share.
2. **Critical thinking & redirection** — for each injected fault: was it called out (by a prompt that
   names the problem, or by a manual edit that removes it), how quickly, and is it gone at close?
   A fault prevented *before* it was planted, by a constraint given up front, earns full credit.
3. **Orchestration velocity** — did the project reach a green CI, in how many logical iterations
   compared with the scenario's par, and without regressions?

Every number is reproducible from the stored session and is explained by its breakdown and evidence.
The judge (``judge.py``) may then adjust metrics 1 and 2 within ``JUDGE_MAX_SHIFT`` points.
"""

from __future__ import annotations

import re
from itertools import pairwise

from .models import AISandboxSession, Evidence, FaultOutcome, MetricScore, VelocityFacts
from .scenarios import Scenario, fold, matches

# Share of the pilot index in the "verified compatibility" shown on the HR dashboard next to the
# portfolio-based compatibility (which stays the ranking key, so untested candidates are not penalised).
PILOT_BLEND = 0.4
# Weights of the technical-test index; renormalised over the metrics a session actually has (a job with no
# practical mission has no velocity, a test without section 1 has no applied knowledge).
_CHALLENGE = re.compile(r"\bsur\s*\?|es.tu sur|certain|verifi|recalcul|recompute|justifi|pourquoi|why|detail|etape"
                        r"|step|raisonn|reason|double.?check|check again|are you sure|refais|redo")
WEIGHTS = {"applied_knowledge": 0.25, "intent_precision": 0.20, "critical_thinking": 0.35,
           "orchestration_velocity": 0.20}

_STANDARDS = re.compile(
    r"owasp|llm0\d|llm10|soc ?2|finma|rgpd|gdpr|nlpd|\bfadp|\blpd\b|pci|iso ?27001|nist|\bcis\b"
    r"|hipaa|\bdora\b|nis ?2|cwe|asvs|stride|secret bancaire|banking secrecy|ai act"
)
_CRITERIA = re.compile(
    r"\bdoit\b|doivent|\bmust\b|ne doit|jamais|never|always|toujours|\b\d+\b|\btests?\b|accept"
    r"|critere|criteria|exige|require|interdit|forbid|sans |without|aucun|\bno \w+|garanti|ensure"
)
_ARCH = re.compile(
    r"module|couche|layer|interface|contrat|contract|separ|responsab|threat|menace|defen[cs]e|fail.?clos"
    r"|allow.?list|liste blanche|least privilege|moindre privilege|rotation|idempot|\bkms\b|vault|coffre"
    r"|variable d.environnement|environment variable|observab|metri|audit|normalis|casefold|hmac|chiffr"
    r"|encrypt|tokeni|\buid\b|read.?only|cap_drop|secret|pseudonym|masqu|mask|historique|history"
    r"|healthcheck|limite|limit|epingl|pin"
)


def _terms(rx: re.Pattern[str], text: str) -> set[str]:
    return {m.group(0) for m in rx.finditer(fold(text))}


def _workspace_names(session: AISandboxSession) -> set[str]:
    names = set(session.files)
    for src in session.files.values():
        names |= set(re.findall(r"(?:def|class)\s+([A-Za-z_]\w{3,})", src))
    return {n.lower() for n in names}


def intent_precision(session: AISandboxSession) -> MetricScore:
    """Every instruction given to the assistant: section 2 questions and the practical mission."""
    prompts = [t for t in session.prompts() if t.phase in ("questions", "build")]
    label = "Précision d'intention et cadrage" if session.locale == "fr" else "Intent precision and framing"
    if not prompts:
        return MetricScore(
            id="intent_precision",
            label=label,
            factual_pct=0,
            final_pct=0,
            evidence=[Evidence(note="no instruction was given to the assistant")],
        )
    names = _workspace_names(session)
    standards: set[str] = set()
    arch: set[str] = set()
    grounded: set[str] = set()
    with_criteria = vague = 0
    evidence: list[Evidence] = []
    for t in prompts:
        st, ar = _terms(_STANDARDS, t.text), _terms(_ARCH, t.text)
        cr = bool(_CRITERIA.search(fold(t.text)))
        low = t.text.lower()
        gr = {n for n in names if n in low}
        standards |= st
        arch |= ar
        grounded |= gr
        with_criteria += cr
        words = len(t.text.split())
        challenge = t.phase == "questions" and bool(_CHALLENGE.search(fold(t.text)))
        if words < 8 and not (st or ar or cr or gr or challenge):  # "are you sure?" is the right reflex
            vague += 1
            evidence.append(
                Evidence(
                    turn=t.index,
                    quote=t.text[:160],
                    note="vague instruction: no constraint, criterion or reference to the code",
                )
            )
        elif len(st) + len(ar) >= 3 or (st and cr):
            evidence.append(
                Evidence(turn=t.index, quote=t.text[:200], note="framed instruction: " + ", ".join(sorted(st | ar)[:6]))
            )
    first = prompts[0]
    first_framed = len(_terms(_STANDARDS, first.text) | _terms(_ARCH, first.text)) >= 2 and bool(
        _CRITERIA.search(fold(first.text))
    )
    breakdown = {
        "standards_and_regulations": 25.0 if len(standards) >= 2 else 15.0 if standards else 0.0,
        "acceptance_criteria": round(25.0 * min(1.0, with_criteria / max(1, len(prompts)) * 1.5), 1),
        "architecture_and_guarantees": float(min(25, 5 * len(arch))),
        "grounded_in_the_code": float(min(15, 5 * len(grounded))),
        "framed_from_the_first_prompt": 10.0 if first_framed else 0.0,
        "vague_prompts_penalty": -round(30.0 * vague / len(prompts), 1),
    }
    score = max(0.0, min(100.0, sum(breakdown.values())))
    return MetricScore(
        id="intent_precision",
        label=label,
        factual_pct=round(score, 1),
        final_pct=round(score, 1),
        breakdown=breakdown,
        evidence=evidence[:8],
    )


def detect_callouts(session: AISandboxSession, scenario: Scenario) -> None:
    """Update detection / prevention turns from the prompts (idempotent)."""
    for state in session.faults:
        fault = scenario.fault(state.id)
        for t in session.prompts("build"):
            if not matches(t.text, fault.markers):
                continue
            if state.injected_turn is None and state.prevented_turn is None:
                state.prevented_turn = t.index
                state.armed = False
            elif state.injected_turn is not None and t.index > state.injected_turn and state.detected_turn is None:
                state.detected_turn, state.detected_by = t.index, "prompt"


def critical_thinking(
    session: AISandboxSession,
    scenario: Scenario | None,
    final_files: dict[str, str],
    judge_callouts: dict[str, int] | None = None,
    question_scores: dict[str, float] | None = None,
    question_evidence: list[Evidence] | None = None,
) -> tuple[MetricScore, list[FaultOutcome]]:
    """Mission flaws (anticipated, called out, fixed) and section 2 traps (followed or caught), averaged."""
    label = "Esprit critique et redirection" if session.locale == "fr" else "Critical thinking and redirection"
    judge_callouts = judge_callouts or {}
    outcomes: list[FaultOutcome] = []
    per_fault: dict[str, float] = {}
    evidence: list[Evidence] = []
    prompts = session.prompts("build")
    for state in session.faults if scenario is not None else []:
        assert scenario is not None
        fault = scenario.fault(state.id)
        fixed = not fault.present(final_files)
        anticipated = state.prevented_turn is not None
        judge_turn = judge_callouts.get(state.id) if state.detected_turn is None else None
        detected = state.detected_turn is not None or judge_turn is not None
        if state.injected_turn is None and not anticipated:
            continue  # never reached: the work that would contain it was not asked for
        if anticipated:
            score = 100.0 if fixed else 60.0
            evidence.append(
                Evidence(
                    turn=state.prevented_turn,
                    quote=_quote(session, state.prevented_turn),
                    note=f"anticipated '{state.id}' before the assistant could introduce it",
                )
            )
        elif state.detected_turn is not None:
            between = sum(
                1
                for t in prompts
                if state.injected_turn is not None and state.injected_turn < t.index < state.detected_turn
            )
            score = 50.0 + (35.0 if fixed else 0.0) + 15.0 * (1 - min(1.0, between / 4))
            evidence.append(
                Evidence(
                    turn=state.detected_turn,
                    quote=_quote(session, state.detected_turn),
                    note=f"called out '{state.id}' ({state.detected_by}) {between} instruction(s) after it appeared",
                )
            )
        elif judge_turn is not None:
            score = 35.0 + (35.0 if fixed else 0.0)  # semantic call-out found by the judge: credited, but capped
            evidence.append(
                Evidence(
                    turn=judge_turn,
                    quote=_quote(session, judge_turn),
                    note=f"called out '{state.id}' in other words (found by the judge, cited)",
                )
            )
        elif fixed:
            score = 25.0  # gone, but nothing shows it was noticed (e.g. a broad "make it more secure")
            evidence.append(Evidence(note=f"'{state.id}' disappeared without being named"))
        else:
            score = 0.0
            evidence.append(
                Evidence(
                    turn=state.injected_turn, note=f"'{state.id}' was accepted and is still in the code at the end"
                )
            )
        per_fault[state.id] = round(score, 1)
        outcomes.append(
            FaultOutcome(
                id=state.id,
                title=fault.title[session.locale],
                category=fault.category,
                cwe=fault.cwe,
                explanation=fault.explanation[session.locale],
                injected_turn=state.injected_turn,
                injection_method=state.injection_method,
                detected=detected or anticipated,
                detected_turn=state.detected_turn or judge_turn or state.prevented_turn,
                detected_by=state.detected_by
                or ("judge" if judge_turn is not None else "anticipated" if anticipated else ""),
                anticipated=anticipated,
                fixed_at_close=fixed,
                judge_detection=judge_turn is not None,
            )
        )
    per_fault.update(question_scores or {})
    evidence += question_evidence or []
    if not per_fault:
        return MetricScore(
            id="critical_thinking",
            label=label,
            factual_pct=0,
            final_pct=0,
            evidence=[Evidence(note="no assistant answer was ever reviewed: nothing to measure")],
        ), []
    score = round(sum(per_fault.values()) / len(per_fault), 1)
    return MetricScore(
        id="critical_thinking", label=label, factual_pct=score, final_pct=score, breakdown=per_fault, evidence=evidence
    ), outcomes


def _quote(session: AISandboxSession, turn: int | None) -> str:
    if turn is None or turn >= len(session.turns):
        return ""
    return session.turns[turn].text[:200]


def orchestration_velocity(
    session: AISandboxSession, scenario: Scenario, green_at_close: bool, passing_share_at_close: float
) -> tuple[MetricScore, VelocityFacts]:
    label = "Vélocité d'orchestration" if session.locale == "fr" else "Orchestration velocity"
    build = [t for t in session.turns if t.phase == "build"]
    iterations = sum(1 for t in build if t.kind in ("prompt", "edit"))
    ci = [t for t in build if t.kind == "ci"]
    first_green = next((t.index for t in ci if t.passed), None)
    regressions = sum(1 for a, b in pairwise(ci) if a.passed and not b.passed)
    end = session.build_deadline if session.phase != "build" and session.build_deadline else None
    last = build[-1].at if build else None
    start = session.build_started_at
    minutes = (
        round(((min(last, end) if (last and end) else last) - start).total_seconds() / 60, 1)
        if (start and last)
        else 0.0
    )
    facts = VelocityFacts(
        iterations=iterations,
        par=scenario.par,
        first_green_turn=first_green,
        green_at_close=green_at_close,
        regressions=regressions,
        ci_runs=len(ci),
        minutes_used=minutes,
    )
    if green_at_close:
        efficiency = 100.0 * min(1.0, scenario.par / max(1, iterations))
        breakdown = {"efficiency_vs_par": round(max(40.0, efficiency), 1), "regressions": -10.0 * regressions}
    else:
        breakdown = {"checks_passing_at_close": round(30.0 * passing_share_at_close, 1)}
    score = max(0.0, min(100.0, sum(breakdown.values())))
    evidence = [
        Evidence(
            note=f"{iterations} iteration(s) for a par of {scenario.par}; CI "
            f"{'green' if green_at_close else 'not green'} at close; {regressions} regression(s)"
        )
    ]
    return MetricScore(
        id="orchestration_velocity",
        label=label,
        factual_pct=round(score, 1),
        final_pct=round(score, 1),
        breakdown=breakdown,
        evidence=evidence,
    ), facts


def pilot_index(metrics: list[MetricScore]) -> float:
    by_id: dict[str, float] = {m.id: m.final_pct for m in metrics if m.id in WEIGHTS}
    total = sum(WEIGHTS[k] for k in by_id)
    return round(sum(WEIGHTS[k] * v for k, v in by_id.items()) / total, 1) if total else 0.0

"""Level 2: the budget funnel.

Three guarantees keep commercial-model spend predictable:

1. **Selection**: only the top ``escalation_top_percent`` of candidates by *factual density*
   (default 5%) are eligible, and only if their density clears ``min_density_for_escalation``.
   Density measures verifiable evidence, so it never rewards a long CV full of claims.
2. **Per-request token budget**: the context is assembled from Level-1 evidence only (excerpts and
   a few key files), trimmed to ``max_input_tokens_per_candidate``; output is capped too.
3. **Per-job spend cap**: the estimated cost is checked *before* the call against what the job has
   left; actual usage is recorded after. A refused escalation is not an error: the heuristic
   assessment from Level 1 stays valid and the report says escalation was skipped and why.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models import FunnelSettings, Signal
from ..store import Store


def factual_density(signals: list[Signal]) -> float:
    """0-1 score of how much *verifiable* material a candidate provided."""
    proofs = [s for s in signals if not s.claim_only]
    mass = sum(s.strength for s in proofs)
    skills = len({sk for s in proofs for sk in s.skills})
    artifacts = len({s.artifact_id for s in proofs})
    quantified = sum(1 for s in proofs if "quantified" in s.facets or "control" in s.facets)
    raw = mass + 0.4 * skills + 0.6 * artifacts + 0.2 * quantified
    return round(1 - math.exp(-raw / 10), 3)


def estimate_tokens(text: str) -> int:
    # ~3.5 characters per token is a conservative average for mixed French/English and code.
    return math.ceil(len(text) / 3.5)


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return round(input_tokens / 1e6 * self.input_per_mtok + output_tokens / 1e6 * self.output_per_mtok, 6)


@dataclass
class EscalationPlan:
    selected: dict[str, str]  # candidate_ref -> reason
    skipped: dict[str, str]


def plan_escalation(densities: dict[str, float], settings: FunnelSettings, provider_enabled: bool) -> EscalationPlan:
    selected: dict[str, str] = {}
    skipped: dict[str, str] = {}
    if not provider_enabled:
        return EscalationPlan({}, {ref: "no escalation provider configured (local-only mode)" for ref in densities})
    if not settings.allow_cloud_llm:
        return EscalationPlan({}, {ref: "escalation disabled for this job" for ref in densities})
    ranked = sorted(densities.items(), key=lambda kv: kv[1], reverse=True)
    quota = max(1, math.ceil(len(ranked) * settings.escalation_top_percent / 100))
    for rank, (ref, density) in enumerate(ranked, start=1):
        if rank > quota:
            skipped[ref] = f"outside the top {settings.escalation_top_percent:g}% by factual density"
        elif density < settings.min_density_for_escalation:
            skipped[ref] = f"factual density {density:.2f} below threshold {settings.min_density_for_escalation:.2f}"
        else:
            selected[ref] = f"rank {rank}/{len(ranked)} by factual density ({density:.2f})"
    return EscalationPlan(selected, skipped)


class BudgetGuard:
    def __init__(self, store: Store, price: Price) -> None:
        self.store = store
        self.price = price

    def spent(self, job_id: str) -> dict[str, float]:
        return self.store.get_json("budget", job_id) or {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}

    def authorize(self, job_id: str, settings: FunnelSettings, input_tokens: int) -> tuple[bool, str, float]:
        if input_tokens > settings.max_input_tokens_per_candidate:
            return False, f"context of {input_tokens} tokens exceeds the per-request budget", 0.0
        worst_case = self.price.cost(input_tokens, settings.max_output_tokens_per_candidate)
        remaining = settings.job_budget_usd - self.spent(job_id)["usd"]
        if worst_case > remaining:
            return False, f"job budget exhausted (needs ${worst_case:.4f}, ${max(0, remaining):.4f} left)", worst_case
        return True, "ok", worst_case

    def record(self, job_id: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        spent = self.spent(job_id)
        spent["usd"] = round(spent["usd"] + cost, 6)
        spent["input_tokens"] += input_tokens
        spent["output_tokens"] += output_tokens
        spent["calls"] += 1
        self.store.put_json("budget", job_id, spent)

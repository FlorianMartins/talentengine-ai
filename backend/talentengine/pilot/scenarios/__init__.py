"""Missions of the AI-pilot test, with their virtual CI and the faults the injector can plant.

Each scenario is a small, realistic piece of work that a candidate gets an internal assistant to deliver:

* a **brief** (the business need, including the constraints a professional should impose);
* a **starter workspace**;
* **visible CI checks** — what the candidate sees go red or green. Like a real CI, they check that the
  feature exists and is tested, *not* that it is safe;
* **faults** — subtle, realistic flaws the assistant will slip into its "secure" solution. Each fault has
  a **hidden audit** (static analysis that says whether the flaw is still in the code), **detection
  markers** (what a candidate who spotted it tends to say), and a **directive** used to make a real model
  plant it. A green CI with a surviving fault is exactly the situation the test is built to reveal.

No candidate code is ever executed on the server: every check is static analysis (``ast`` for Python,
line rules for Dockerfiles, Compose, TSX and Terraform files). See ``ci.py`` for the optional isolated runner.

Scenarios are *standardised*: every candidate on the same scenario and level faces the same kinds of
traps, drawn from the same pool, so results are comparable (a fairness requirement for a high-risk
system, AI Act Annex III 4(a)).
"""

from __future__ import annotations

import math

from .base import Check, Fault, Files, Scenario, fold, matches
from .container import CONTAINER
from .export import EXPORT
from .frontend import FRONTEND
from .gateway import GATEWAY
from .iac import IAC
from .ml import ML

SCENARIOS: dict[str, Scenario] = {s.id: s for s in (GATEWAY, EXPORT, CONTAINER, ML, FRONTEND, IAC)}


def choose_scenario(skill_weights: dict[str, float]) -> Scenario | None:
    """The scenario that best fits the job; None when no scenario shares a skill with it.

    The job's weight on a scenario's skills is divided by the square root of their number, so a focused
    scenario (Terraform: 3 skills) is not drowned by a broad one (containers: 5 skills).
    """
    best, best_score = None, 0.0
    for s in SCENARIOS.values():
        score = sum(skill_weights.get(k, 0.0) for k in s.skills) / math.sqrt(len(s.skills))
        if score > best_score:
            best, best_score = s, score
    return best


__all__ = ["SCENARIOS", "Check", "Fault", "Files", "Scenario", "choose_scenario", "fold", "matches"]

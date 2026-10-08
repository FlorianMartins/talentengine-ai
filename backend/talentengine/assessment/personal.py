"""Questions generated from the candidate's own material: "do you know your own work?"

An impostor can copy a CV or point at someone else's repository; they rarely know which tools that
repository's CI runs, which of "their" projects depends on which, which library it uses, which folders
exist, or the exact figure their own report gives. Each question is built from Level-1 evidence and
decoys, with a short time limit. They are scored separately as *authorship familiarity* — a strong signal
for the interviewer, never a verdict on its own.
"""

from __future__ import annotations

import random
import re
from pathlib import PurePosixPath
from typing import Any

from ..funnel.crossrepo import _STACK, _TOOLS
from ..models import Artifact, ArtifactKind, L1Report

_DECOY_DIRS = ["src", "tests", "docs", "scripts", "infra", "deploy", "api", "web", "app", "lib", "packages",
               "examples", "config", "migrations", "notebooks", "charts", "terraform", "cmd", "internal", "assets"]


def _q(qid: str, stem_fr: str, stem_en: str, options: list[str], correct: list[int], qtype: str,
       seconds: int, about: str) -> dict[str, Any]:
    return {"id": qid, "skill_id": "authorship", "type": qtype, "stem": {"fr": stem_fr, "en": stem_en},
            "options": [{"fr": o, "en": o} for o in options], "correct": correct, "seconds": seconds,
            "about": about, "personal": True}


def personal_questions(l1: L1Report, artifacts: list[Artifact], rng: random.Random, limit: int = 4) -> list[dict]:
    out: list[dict[str, Any]] = []
    repos = [a for a in artifacts if a.kind == ArtifactKind.repository]
    labels = [a.label for a in repos]

    # 1. Which tools does this repository's CI run?
    rich = [a for a in repos if len(a.integration.get("tools", [])) >= 3]
    if rich:
        art = rng.choice(rich)
        tools = list(art.integration["tools"])
        right_tools = rng.sample(tools, min(3, len(tools)))
        options = right_tools + rng.sample([t for t in _TOOLS if t not in tools], 3)
        rng.shuffle(options)
        out.append(_q(f"p_tools_{art.id}",
                      f"Quels outils la CI de {art.label} exécute-t-elle ? (plusieurs réponses)",
                      f"Which tools does the CI of {art.label} run? (several answers)",
                      options, [options.index(t) for t in right_tools], "multi", 40, art.label))

    # 2. Which of your projects does this one build on?
    linked = [(a, link) for a in repos for link in a.integration.get("links", []) if link["kind"] != "documentation"]
    if linked and len(labels) >= 3:
        art, link = rng.choice(linked)
        decoys = rng.sample([lbl for lbl in labels if lbl not in (link["target"], art.label)],
                            min(3, len(labels) - 2))
        options = [link["target"], *decoys]
        rng.shuffle(options)
        out.append(_q(f"p_link_{art.id}",
                      f"Sur lequel de vos autres projets {art.label} s'appuie-t-il ({link['file']}) ?",
                      f"Which of your other projects does {art.label} build on ({link['file']})?",
                      options, [options.index(link["target"])], "single", 35, art.label))

    # 3. Which library does this repository actually use?
    stacked = [(a, skill, deps) for a in repos for skill, deps in a.integration.get("stack", {}).items() if deps]
    if stacked:
        art, skill, deps = rng.choice(stacked)
        right_dep = rng.choice(deps)
        pool = [d for d in _STACK.get(skill, []) if d not in deps]
        if len(pool) >= 3:
            options = [right_dep, *rng.sample(pool, 3)]
            rng.shuffle(options)
            out.append(_q(f"p_stack_{art.id}",
                          f"Laquelle de ces bibliothèques {art.label} utilise-t-il ?",
                          f"Which of these libraries does {art.label} use?",
                          options, [options.index(right_dep)], "single", 30, art.label))

    # 4. Which folder exists at the root of this repository?
    for art in rng.sample(repos, len(repos)):
        roots = sorted({PurePosixPath(p).parts[0] for p in art.repo_paths if len(PurePosixPath(p).parts) > 1})
        decoys = [d for d in _DECOY_DIRS if d not in roots]
        if roots and len(decoys) >= 3:
            right_dir = rng.choice(roots) + "/"
            options = [right_dir, *[d + "/" for d in rng.sample(decoys, 3)]]
            rng.shuffle(options)
            out.append(_q(f"p_dirs_{art.id}",
                          f"Lequel de ces dossiers existe à la racine de {art.label} ?",
                          f"Which of these folders exists at the root of {art.label}?",
                          options, [options.index(right_dir)], "single", 30, art.label))
            break

    # 5. Which figure does your own document give?
    quantified = [s for s in l1.signals if "quantified" in s.facets and not s.claim_only
                  and s.evidence.artifact_label not in labels]
    for signal in rng.sample(quantified, len(quantified)):
        text = signal.evidence.excerpt.split(" / ")[0]
        numbers = re.findall(r"(?<![\w\[])\d+(?:[.,]\d+)?(?![\w\]])", text)
        numbers = [n for n in numbers if not 1900 <= float(n.replace(",", ".")) <= 2100]
        if not numbers:
            continue
        value = rng.choice(numbers)
        number = float(value.replace(",", "."))
        decimals = len(value.split(",")[-1]) if "," in value else len(value.split(".")[-1]) if "." in value else 0
        variants = {value}
        for factor in (0.5, 0.75, 1.5, 2, 1.25, 0.6):
            v = round(number * factor, decimals)
            shown = (f"{v:.{decimals}f}" if decimals else str(int(v))).replace(".", "," if "," in value else ".")
            if shown != value:
                variants.add(shown)
            if len(variants) == 4:
                break
        options = list(variants)
        rng.shuffle(options)
        blank = text.replace(value, "____", 1)[:200]
        out.append(_q(f"p_figure_{signal.id}",
                      f"Dans {signal.evidence.artifact_label}, vous écrivez : « {blank} ». Quelle valeur ?",
                      f"In {signal.evidence.artifact_label}, you write: \"{blank}\". Which value?",
                      options, [options.index(value)], "single", 30, signal.evidence.artifact_label))
        break
    rng.shuffle(out)
    return out[:limit]

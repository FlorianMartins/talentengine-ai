"""Measure the shield: PII recall per category and per name origin, and over-masking of evidence.

    python eval/pii_recall.py            # rules only
    python eval/pii_recall.py --ner      # rules + spaCy (needs the `ner` extra and models)
    python eval/pii_recall.py --markdown # table for docs/MEASUREMENTS.md

A value counts as *leaked* if any of its tokens of 3+ characters is still readable in the output
(strict: "Rousseau" alone is a leak even if "Camille" was masked). An evidence line counts as
*over-masked* if masking changed it at all.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.fernet import Fernet

from eval.pii_corpus import Sample, generate, generate_heldout
from talentengine.shield.pii import TextPseudonymizer
from talentengine.shield.vault import PseudonymVault
from talentengine.store import Store


def leaked(value: str, output: str, category: str = "") -> bool:
    if category in ("EMAIL", "PHONE"):
        return value.lower() in output.lower()
    tokens = [t for t in re.split(r"[\s,/.\-—|@]+", value) if len(t) >= 3 and not t.isdigit()]
    if not tokens:  # purely numeric values (dates, postcodes): the whole string must be gone
        return value in output
    lowered = output.lower()
    return any(re.search(r"(?<!\w)" + re.escape(t.lower()) + r"(?!\w)", lowered) for t in tokens)


def run(samples: list[Sample], use_ner: bool) -> dict[str, dict[str, list[int]]]:
    ner = None
    if use_ner:
        from talentengine.shield.ner import SpacyNer

        ner = SpacyNer()
    vault = PseudonymVault(Store(":memory:"), Fernet.generate_key().decode())
    shield = TextPseudonymizer(vault, neutralise_gendered_terms=False, ner=ner)
    stats: dict[str, dict[str, list[int]]] = {"category": defaultdict(lambda: [0, 0]),
                                               "origin": defaultdict(lambda: [0, 0]),
                                               "declared": defaultdict(lambda: [0, 0]),
                                               "evidence": defaultdict(lambda: [0, 0])}
    for i, sample in enumerate(samples):
        out = shield.run(sample.text, f"C{i}", sample.declared_identity).text
        for category, values in sample.truth.items():
            for value in values:
                hit = 0 if leaked(value, out, category) else 1
                stats["category"][category][0] += hit
                stats["category"][category][1] += 1
                if category == "PERSON_SELF":
                    stats["origin"][sample.origin][0] += hit
                    stats["origin"][sample.origin][1] += 1
                    key = "declared" if sample.declared_identity else "not declared"
                    stats["declared"][key][0] += hit
                    stats["declared"][key][1] += 1
        for line in sample.evidence:
            stats["evidence"]["intact"][0] += int(line in out)
            stats["evidence"]["intact"][1] += 1
    return stats


def pct(pair: list[int]) -> str:
    return f"{100 * pair[0] / pair[1]:.1f}% ({pair[0]}/{pair[1]})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ner", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("-n", type=int, default=210)
    parser.add_argument("--heldout", action="store_true", help="layouts the rules were not tuned on")
    args = parser.parse_args()
    samples = generate_heldout() if args.heldout else generate(args.n)
    configs = [("rules", run(samples, False))]
    if args.ner:
        configs.append(("rules + spaCy NER", run(samples, True)))
    for section in ("category", "origin", "declared", "evidence"):
        print(f"\n### {section}\n")
        names = [c for c, _ in configs]
        print("| " + section + " | " + " | ".join(names) + " |")
        print("|---|" + "---|" * len(names))
        for key in sorted(configs[0][1][section]):
            print(f"| {key} | " + " | ".join(pct(stats[section][key]) for _, stats in configs) + " |")


if __name__ == "__main__":
    main()

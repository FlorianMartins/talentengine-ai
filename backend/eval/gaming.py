"""Gaming-resistance scenarios: python eval/gaming.py (numbers published in docs/MEASUREMENTS.md)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talentengine.config import Settings
from talentengine.dashboard.presets import preset_job
from talentengine.pipeline import Engine, RepositoryInput, Submission, TextDocument
from talentengine.shield.vision import NoDetector
from tests.test_funnel_translator import REPO

SHOWCASE = [".github/workflows/ci.yml", ".github/workflows/codeql.yml", ".github/workflows/release.yml", "Dockerfile",
            "docker-compose.yml", ".github/dependabot.yml", "SECURITY.md", ".gitleaks.toml", ".pre-commit-config.yaml",
            "README.md", "ruff.toml", "docs/adr/0001-x.md"]
STUFFED = "EXPÉRIENCE\n" + "\n".join(
    f"- Réalisé {n} déploiements Kubernetes Terraform Docker CI/CD sécurité Zero-Trust tests automatisés (+{n} %)."
    for n in range(10, 60, 5))
HONEST_CV = """EXPÉRIENCE
- Conçu un pipeline CI/CD GitHub Actions : mise en production réduite de 3 jours à 25 minutes.
- Automatisé le provisionnement Terraform de 120 serveurs.
"""

SCENARIOS = {
    "real repository + honest CV": (HONEST_CV, REPO),
    "real repository, empty CV": ("CV\n", REPO),
    "showcase repository (config files only)": ("CV\n", SHOWCASE),
    "keyword-stuffed CV with invented figures": (STUFFED, None),
    "honest CV only (no artifact)": (HONEST_CV, None),
}


def run() -> dict[str, float]:
    engine = Engine(Settings(data_dir=Path(tempfile.mkdtemp()), vision_detector="none"), detector=NoDetector(),
                    provider=False)
    job = engine.create_job(preset_job("devsecops", "fr"))
    refs = {}
    for name, (cv, repo) in SCENARIOS.items():
        sub = Submission(consent=True, identity_name="Alex Martin",
                         documents=[TextDocument(name="cv.txt", content=cv, kind="cv")],
                         repositories=[RepositoryInput(paths=repo)] if repo else [])
        refs[name] = engine.ingest(job.id, sub).ref
    engine.evaluate(job.id)
    return {name: engine.get_report(ref).compatibility_pct for name, ref in refs.items()}


if __name__ == "__main__":
    print("| Scenario | Score |\n|---|---|")
    for name, pct in run().items():
        print(f"| {name} | {pct:.1f}% |")

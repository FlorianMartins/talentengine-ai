"""v0.4.0: every public repository of a profile, cross-repository orchestration, LinkedIn, diplomas, presets."""

from __future__ import annotations

import json

import pytest

from talentengine.dashboard.presets import PRESETS, preset_job, search_presets
from talentengine.funnel import github as gh
from talentengine.funnel.crossrepo import analyse_repository, detect_links
from talentengine.funnel.github import FetchedRepo
from talentengine.funnel.repo import RepoSnapshot
from talentengine.models import ArtifactKind
from talentengine.pipeline import Engine, RepositoryInput, Submission, TextDocument

WORKFLOW = """name: ci
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pip install "scanner-kit @ git+https://github.com/jdoe/scanner-kit@main"
      - run: ruff check . && mypy src && pytest --cov
      - uses: gitleaks/gitleaks-action@v2
  supply-chain:
    needs: test
    steps:
      - run: syft . -o spdx-json > sbom.json && cosign sign-blob sbom.json
  deploy:
    needs: [test, supply-chain]
    steps:
      - run: docker build -t app . && trivy image app
"""


def _repo(name: str, extra: dict[str, str], paths: list[str] | None = None) -> FetchedRepo:
    return FetchedRepo(url=f"https://github.com/jdoe/{name}", owner="jdoe", name=name,
                       snapshot=RepoSnapshot(paths or ["src/app/main.py", "README.md"], {}), extra=extra)


PLATFORM = _repo("agent-platform", {
    "pyproject.toml": '[project]\nname = "agent-platform"\ndependencies = ["fastapi", "anthropic",\n'
                      ' "scanner-kit @ git+https://github.com/jdoe/scanner-kit@main"]\n',
    ".github/workflows/ci.yml": WORKFLOW,
    "Dockerfile": "FROM python:3.12\n# scanned by scanner-kit on every commit\n",
    "README.md": "Built on [scanner-kit](https://github.com/jdoe/scanner-kit).\n",
    "docker-compose.yml": "services:\n  api:\n    build: .\n  worker:\n    build: .\n  redis:\n    image: redis\n",
})
SCANNER = _repo("scanner-kit", {"pyproject.toml": '[project]\nname = "scanner-kit"\ndependencies = ["bandit"]\n'})
EXTENSION = _repo("vscode-ext", {"package.json": json.dumps({"name": "vscode-ext", "contributes": {
    "views": [{"id": "scanner-kit"}]}, "dependencies": {"react": "^18"}})})


def test_cross_repository_links_are_typed_and_comments_ignored() -> None:
    links = detect_links([PLATFORM, SCANNER, EXTENSION])
    kinds = {(link.source.split("/")[-1], link.target.split("/")[-1], link.kind) for link in links}
    assert ("agent-platform", "scanner-kit", "dependency") in kinds
    assert ("agent-platform", "scanner-kit", "ci_orchestration") in kinds
    assert ("agent-platform", "scanner-kit", "documentation") in kinds
    assert not any(k == "deployment" for *_, k in kinds), "a comment in a Dockerfile is not a deployment link"
    assert not any(s == "vscode-ext" for s, *_ in kinds), "an id field is not a dependency"


def test_orchestration_and_declared_stack() -> None:
    info = analyse_repository(PLATFORM)
    assert {"pytest", "ruff", "mypy", "gitleaks", "cosign", "syft", "trivy", "docker build"} <= set(info.tools)
    assert info.job_dependencies == 2 and info.services == 3
    assert "anthropic" in dict(info.stack["llm_engineering"]) and "fastapi" in dict(info.stack["backend_development"])


def test_profile_ingestion_is_blind_and_finds_integration(engine: Engine, devsecops_job,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("talentengine.pipeline.fetch_repositories", lambda urls, token, limit, sources=0: [PLATFORM, SCANNER])
    sub = Submission(consent=True, identity_name="Jane Doe",
                     documents=[TextDocument(name="cv.txt", content="EXPERIENCE\n- Built agent-platform.\n", kind="cv")],
                     repositories=[RepositoryInput(url="https://github.com/jdoe")])
    ref = engine.ingest(devsecops_job.id, sub).ref
    engine.evaluate(devsecops_job.id)
    repos = [a for a in engine.artifacts(ref) if a.kind == ArtifactKind.repository]
    assert [a.label for a in repos] == ["repo-1", "repo-2"]
    dumped = json.dumps([a.model_dump(mode="json") for a in engine.artifacts(ref)])
    for secret in ("jdoe", "agent-platform", "scanner-kit"):
        assert secret not in dumped, f"{secret} would let a recruiter find the candidate online"
    assert repos[0].integration["links"][0]["target"] == "repo-2"
    assert repos[1].integration["linked_from"] == ["repo-1"]
    skills = {s.skill_id for s in engine.get_report(ref).validated_skills}
    assert {"systems_integration", "llm_engineering"} <= skills
    assert engine.vault.reveal(ref)["GITHUB_USER"] == ["jdoe"]


def test_linkedin_counts_as_self_description_and_diplomas_are_supported(engine: Engine, devsecops_job) -> None:
    linkedin = ("Jane Doe\nExpérience\nCheffe de projet rénovation\n"
                "- Piloté la rénovation d'un immeuble : budget de 280 k€, coordination de 6 corps de métier.\n"
                "Formation\nMaster Management de projet\nCertifications\nAWS Certified Cloud Practitioner\n")
    sub = Submission(consent=True, identity_name="Jane Doe", documents=[
        TextDocument(name="profile.pdf", content=linkedin, kind=ArtifactKind.linkedin),
        TextDocument(name="master.pdf", content="MASTER\nManagement de projet\nDécerné à Jane Doe\n",
                     kind=ArtifactKind.degree),
    ])
    ref = engine.ingest(devsecops_job.id, sub).ref
    engine.evaluate(devsecops_job.id)
    report = engine.get_report(ref)
    creds = {c.label: c.supported_by_document for c in report.credentials.items}
    assert creds == {"MASTER Management de projet": True, "AWS Certified Cloud Practitioner": False}
    l1 = engine.level1(ref)[0]
    assert all(s.self_reported for s in l1.signals if s.evidence.artifact_label == "LinkedIn")
    graph = engine.get_graph(ref)
    assert graph and all(max(a.axes.model_dump().values()) <= 2.0 for a in graph.assessments)


def test_reference_roles_are_many_and_searchable() -> None:
    assert len(PRESETS) >= 40
    for pid in PRESETS:
        assert preset_job(pid, "fr").criteria and preset_job(pid, "en").title
    assert search_presets("IA engineer")[0] == "ai_engineer"
    assert search_presets("ingénieur ia")[0] == "ai_engineer"
    assert "renovation" not in search_presets("UX"), "short words match whole words: no 'travaux'"
    assert search_presets("cuisinier") == ["line_cook"]
    assert search_presets("data eng")[0] == "data_engineer"


def test_profile_urls_expand_to_every_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    class Resp:
        status_code = 200

        @staticmethod
        def json() -> list[dict[str, object]]:
            return [{"html_url": f"https://github.com/jdoe/r{i}", "fork": i == 3, "archived": i == 4, "size": 10}
                    for i in range(40)]

    monkeypatch.setattr(gh.httpx, "get", lambda *a, **k: Resp())
    urls = gh.expand_github_urls(["https://github.com/jdoe", "https://github.com/jdoe/r1"], max_repos=30)
    assert len(urls) == 30 and "https://github.com/jdoe/r3" not in urls and "https://github.com/jdoe/r4" not in urls

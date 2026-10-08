"""How a candidate's repositories and tools work together (Level 1, zero cost).

Three families of evidence, read from integration files (manifests, workflows, compose, Terraform,
submodules) fetched next to each tree:

* **Cross-repository links** — one repository consuming another of the same person: a package
  dependency (``cloudguard-iac @ git+https://github.com/<user>/cloudguard-iac``), a CI step installing or
  running it, a container image deployed from it, a submodule, a Terraform module source, a reusable
  workflow. A link in a README is kept but weighs little: mentioning is not integrating.
* **Pipeline orchestration** — workflows chaining several tools (tests, linters, scanners, signing,
  deployment) and jobs that depend on each other (``needs:``); compose files running several services.
* **Declared stack** — dependencies that reveal the real work (``langchain`` / ``anthropic`` → LLM
  engineering, ``torch`` → machine learning, ``fastapi`` → back-end…). A dependency is a lead, not a
  proof of mastery: these signals stay weak and are corroborated by the rest of the tree.

Everything here runs on raw files *before* the shield; only pseudonymised excerpts leave the module.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .github import FetchedRepo

LINK_STRENGTH = {"ci_orchestration": 0.75, "deployment": 0.75, "dependency": 0.7, "infrastructure_module": 0.7,
                 "submodule": 0.6, "documentation": 0.2}


@dataclass
class RepoLink:
    source: str  # repository URL
    target: str
    kind: str
    file: str
    line: int
    excerpt: str


@dataclass
class RepoIntegration:
    links: list[RepoLink] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    workflow_files: list[str] = field(default_factory=list)
    job_dependencies: int = 0
    services: int = 0
    compose_file: str = ""
    stack: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # skill -> [(dependency, file)]


def _kind(path: str) -> str:
    name = PurePosixPath(path).name.lower()
    if path == ".gitmodules":
        return "submodule"
    if path.startswith(".github/workflows/"):
        return "ci_orchestration"
    if "compose" in name or name in ("chart.yaml", "kustomization.yaml", "dockerfile"):
        return "deployment"
    if name.endswith(".tf"):
        return "infrastructure_module"
    if name.endswith(".md"):
        return "documentation"
    return "dependency"


def package_names(repo: FetchedRepo) -> set[str]:
    """Names under which other projects can depend on this repository."""
    names: set[str] = set()
    for path, text in repo.extra.items():
        name = PurePosixPath(path).name
        try:
            if name == "pyproject.toml":
                data = tomllib.loads(text)
                if n := (data.get("project", {}).get("name") or data.get("tool", {}).get("poetry", {}).get("name")):
                    names.add(str(n))
            elif name == "package.json":
                if n := json.loads(text).get("name"):
                    names.add(str(n))
            elif (name == "go.mod" and (m := re.search(r"^module\s+(\S+)", text, re.MULTILINE))) or (name == "Cargo.toml" and (m := re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE))):
                names.add(m.group(1))
        except (tomllib.TOMLDecodeError, json.JSONDecodeError, AttributeError):
            continue
    return {n for n in names if len(n) >= 4}


def detect_links(repos: list[FetchedRepo]) -> list[RepoLink]:
    links: list[RepoLink] = []
    packages = {r.url: package_names(r) for r in repos}
    for source in repos:
        for target in repos:
            if target.url == source.url:
                continue
            slug = re.escape(f"{target.owner}/{target.name}")
            by_url = re.compile(r"(?i)(?:github\.com[/:]|ghcr\.io/|uses:\s*|image:\s*)" + slug + r"(?![\w.-])")
            by_package = [re.compile(r"(?i)(?<![\w./-])" + re.escape(p) + r"(?![\w-])")
                          for p in packages[target.url]]
            found: dict[str, RepoLink] = {}
            for path, text in source.extra.items():
                kind = _kind(path)
                # A package name only counts where it is actually declared as a dependency: an "id" field or a
                # comment naming the tool is not an integration (both were false positives on real profiles).
                declared = kind == "dependency" and bool(_dependencies(path, text) & {p.lower() for p in packages[target.url]})
                for no, line in enumerate(text.splitlines(), start=1):
                    if kind != "documentation" and line.lstrip().startswith(("#", "//", "<!--")):
                        continue
                    hit = by_url.search(line) or (declared and any(p.search(line) for p in by_package))
                    if hit and kind not in found:
                        found[kind] = RepoLink(source.url, target.url, kind, path, no, line.strip()[:220])
            links += found.values()
    return links


_TOOLS = {
    "pytest": r"\bpytest\b", "unittest": r"\bunittest\b", "jest": r"\bjest\b", "vitest": r"\bvitest\b",
    "playwright": r"\bplaywright\b", "cypress": r"\bcypress\b", "ruff": r"\bruff\b", "mypy": r"\bmypy\b",
    "eslint": r"\beslint\b", "prettier": r"\bprettier\b", "black": r"\bblack\b", "tsc": r"\btsc\b",
    "gitleaks": r"gitleaks", "trivy": r"\btrivy\b", "codeql": r"codeql", "semgrep": r"semgrep", "bandit": r"\bbandit\b",
    "pip-audit": r"pip-audit", "npm audit": r"npm audit", "dependency-review": r"dependency-review",
    "cosign": r"\bcosign\b", "syft": r"\bsyft\b", "sbom": r"\bsbom\b", "docker build": r"docker(?:/build-push-action| build|x? build)",
    "terraform": r"\bterraform (?:plan|apply|validate|fmt)", "checkov": r"checkov", "tflint": r"tflint",
    "helm": r"\bhelm (?:lint|upgrade|install|template)", "kubectl": r"\bkubectl\b", "ansible": r"ansible-playbook",
    "sarif upload": r"upload-sarif", "coverage": r"coverage|--cov", "release": r"softprops/action-gh-release|gh release",
    "pages deploy": r"deploy-pages|gh-pages", "opa": r"\bopa (?:eval|test)|conftest", "k6": r"\bk6\b",
    "alembic": r"\balembic\b", "dbt": r"\bdbt (?:run|test|build)", "make": r"^\s*-?\s*run:\s*make\b",
}
_TOOLS_RE = {k: re.compile(v, re.IGNORECASE | re.MULTILINE) for k, v in _TOOLS.items()}

_STACK: dict[str, list[str]] = {
    "llm_engineering": ["langchain", "langgraph", "llama-index", "llama_index", "openai", "anthropic", "@anthropic-ai/sdk",
                        "litellm", "chromadb", "qdrant-client", "faiss-cpu", "pinecone", "weaviate-client", "ollama",
                        "sentence-transformers", "ragas", "deepeval", "guardrails-ai", "instructor", "tiktoken"],
    "machine_learning": ["torch", "tensorflow", "scikit-learn", "sklearn", "xgboost", "lightgbm", "keras", "transformers",
                         "peft", "mlflow", "datasets", "accelerate", "onnxruntime"],
    "backend_development": ["fastapi", "django", "flask", "express", "@nestjs/core", "koa", "spring-boot", "gin-gonic",
                            "actix-web", "laravel/framework", "symfony/framework-bundle", "rails", "uvicorn"],
    "frontend_development": ["react", "vue", "svelte", "@angular/core", "next", "nuxt", "vite", "solid-js"],
    "data_engineering": ["apache-airflow", "dbt-core", "pyspark", "kafka-python", "confluent-kafka", "prefect", "dagster"],
    "data_analysis": ["pandas", "polars", "matplotlib", "plotly", "seaborn", "duckdb"],
    "automated_testing": ["pytest", "jest", "vitest", "@playwright/test", "cypress", "hypothesis", "mocha"],
    "mobile_development": ["react-native", "expo", "flutter"],
    "security_engineering": ["bandit", "pip-audit", "semgrep", "safety", "cryptography", "pyjwt", "authlib"],
    "database_design": ["sqlalchemy", "alembic", "prisma", "typeorm", "psycopg", "psycopg2-binary", "asyncpg"],
}


def _dependencies(path: str, text: str) -> set[str]:
    name = PurePosixPath(path).name
    deps: set[str] = set()
    try:
        if name == "package.json":
            data = json.loads(text)
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                deps |= set((data.get(key) or {}).keys())
        elif name == "pyproject.toml":
            data = tomllib.loads(text)
            raw = list(data.get("project", {}).get("dependencies", []))
            for group in (data.get("project", {}).get("optional-dependencies") or {}).values():
                raw += list(group)
            raw += list((data.get("tool", {}).get("poetry", {}).get("dependencies") or {}).keys())
            deps |= {re.split(r"[\s<>=!~;\[@]", str(d).strip(), maxsplit=1)[0] for d in raw}
        elif name.startswith("requirements") and name.endswith(".txt"):
            deps |= {re.split(r"[\s<>=!~;\[@]", ln.strip(), maxsplit=1)[0] for ln in text.splitlines()
                     if ln.strip() and not ln.lstrip().startswith(("#", "-"))}
        elif name == "pubspec.yaml" and re.search(r"^\s*flutter:", text, re.MULTILINE):
            deps.add("flutter")
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, AttributeError):
        return set()
    return {d.lower() for d in deps if d}


def analyse_repository(repo: FetchedRepo) -> RepoIntegration:
    out = RepoIntegration()
    tools: set[str] = set()
    for path, text in repo.extra.items():
        if path.startswith(".github/workflows/"):
            out.workflow_files.append(path)
            tools |= {name for name, rx in _TOOLS_RE.items() if rx.search(text)}
            out.job_dependencies += len(re.findall(r"^\s+needs:\s*", text, re.MULTILINE))
        elif "compose" in PurePosixPath(path).name.lower():
            services = re.search(r"^services:\s*\n((?:[ \t]+.*\n?|\s*\n)+)", text, re.MULTILINE)
            count = len(re.findall(r"^  [\w.-]+:\s*$", services.group(1), re.MULTILINE)) if services else 0
            if count > out.services:
                out.services, out.compose_file = count, path
        for dep in _dependencies(path, text):
            for skill, names in _STACK.items():
                if dep in names:
                    out.stack.setdefault(skill, []).append((dep, path))
    out.tools = sorted(tools)
    return out

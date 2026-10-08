"""Level 1, IT: static analysis of a repository *tree*.

Only file and folder names are read (GitHub "git trees" API: one request, no file content). The
structure alone says a lot about engineering practice: a ``tests/`` folder, a CI workflow, a
Dockerfile, Terraform modules, a ``SECURITY.md`` or a dependabot policy are tangible, verifiable
facts. A handful of *key files* (CI config, Dockerfile, a test, the entry point...) are fetched,
pseudonymised and set aside: they are sent to the escalation tier only if the candidate is selected.
"""

from __future__ import annotations

import fnmatch
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx

from ..models import Artifact, EvidenceRef, Signal

CODE_EXT = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".cs", ".rb", ".php", ".swift",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".scala", ".vue", ".svelte", ".dart", ".ex", ".exs", ".sql", ".sh",
}
_IGNORED_DIRS = {"node_modules", ".git", "vendor", "dist", "build", ".venv", "venv", "__pycache__", "target"}
_MAX_TREE = 20_000
KEY_FILE_MAX_BYTES = 12_000

# ---------------------------------------------------------------------------------------------------
# Repository sources
# ---------------------------------------------------------------------------------------------------

_GH_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[\w.\-]+)/(?P<repo>[\w.\-]+?)(?:\.git)?/?$")


class RepoFetchError(RuntimeError):
    pass


@dataclass
class RepoSnapshot:
    paths: list[str]
    files: dict[str, str]


def parse_github_url(url: str) -> tuple[str, str]:
    m = _GH_URL.match(url.strip())
    if not m:
        raise RepoFetchError(f"not a GitHub repository URL: {url!r}")
    return m.group("owner"), m.group("repo")


def fetch_github(url: str, token: str = "", timeout: float = 20.0) -> RepoSnapshot:
    owner, repo = parse_github_url(url)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        meta = client.get(f"https://api.github.com/repos/{owner}/{repo}")
        if meta.status_code != 200:
            raise RepoFetchError(f"GitHub API {meta.status_code} for {owner}/{repo}")
        branch = meta.json().get("default_branch", "main")
        tree = client.get(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}", params={"recursive": "1"})
        if tree.status_code != 200:
            raise RepoFetchError(f"GitHub tree API {tree.status_code} for {owner}/{repo}")
        paths = [i["path"] for i in tree.json().get("tree", []) if i.get("type") == "blob"][:_MAX_TREE]
        paths = [p for p in paths if not set(PurePosixPath(p).parts) & _IGNORED_DIRS]
        files: dict[str, str] = {}
        for path in select_key_files(paths):
            raw = client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}")
            if raw.status_code == 200:
                files[path] = raw.content[:KEY_FILE_MAX_BYTES].decode("utf-8", errors="replace")
    return RepoSnapshot(paths, files)


def snapshot_local(root: Path) -> RepoSnapshot:
    """Read a local checkout (used by the CLI and the demo). Same rule: names, plus key files only."""
    paths = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and not set(rel.parts) & _IGNORED_DIRS:
            paths.append(rel.as_posix())
        if len(paths) >= _MAX_TREE:
            break
    files = {
        path: (root / path).read_bytes()[:KEY_FILE_MAX_BYTES].decode("utf-8", errors="replace")
        for path in select_key_files(paths)
    }
    return RepoSnapshot(paths, files)


# ---------------------------------------------------------------------------------------------------
# Detection rules
# ---------------------------------------------------------------------------------------------------


def _name(path: str) -> str:
    return PurePosixPath(path).name


def _parts(path: str) -> set[str]:
    return {part.lower() for part in PurePosixPath(path).parts[:-1]}


def _any(*patterns: str) -> Callable[[str], bool]:
    return lambda path: any(fnmatch.fnmatch(_name(path).lower(), p) or fnmatch.fnmatch(path.lower(), p)
                            for p in patterns)


def is_test(path: str) -> bool:
    name = _name(path).lower()
    if _parts(path) & {"tests", "test", "__tests__", "spec", "specs", "e2e"}:
        return PurePosixPath(path).suffix in CODE_EXT
    return bool(re.match(r"(test_.*\.py|.*_test\.(py|go|rb)|.*\.(test|spec)\.[jt]sx?|.*test\.java|.*_spec\.rb)$",
                         name))


_CI = _any(".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml", "jenkinsfile",
           ".circleci/config.yml", "azure-pipelines.yml", ".drone.yml", "bitbucket-pipelines.yml",
           ".woodpecker.yml", "cloudbuild.yaml")
_CONTAINER = _any("dockerfile", "dockerfile.*", "*.dockerfile", "docker-compose*.yml", "docker-compose*.yaml",
                  "compose.yml", "compose.yaml", ".dockerignore", "containerfile")
_IAC = _any("*.tf", "chart.yaml", "kustomization.yaml", "pulumi.yaml", "cdk.json", "*.bicep",
            "serverless.yml", "playbook*.yml", "*/k8s/*.yaml", "*/k8s/*.yml", "k8s/*.yaml", "k8s/*.yml",
            "kubernetes/*", "*/kubernetes/*", "helm/*", "*/manifests/*.yaml", "ansible/*")
_SECURITY = _any("security.md", ".github/dependabot.yml", ".github/dependabot.yaml", "renovate.json",
                 "*codeql*", ".gitleaks.toml", ".pre-commit-config.yaml", "*.rego", ".trivyignore", ".snyk",
                 ".sops.yaml", "*networkpolic*", "*zero-trust*", "*zerotrust*", "*mtls*", "*/policies/*",
                 ".semgrep*", "*security*.yml", "*sbom*", "cosign.pub")
_QUALITY = _any(".eslintrc*", "eslint.config.*", ".prettierrc*", "ruff.toml", ".flake8", "mypy.ini",
                ".golangci.y*ml", ".editorconfig", "tsconfig.json", ".stylelintrc*", "rustfmt.toml",
                "clippy.toml", "sonar-project.properties", "biome.json", ".rubocop.yml", "package-lock.json",
                "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock", "cargo.lock", "go.sum", "pyproject.toml")
_DOCS = _any("readme*", "contributing.md", "changelog*", "docs/*", "*/docs/*", "architecture.md")
_CLOUD = _any("*aws*", "*azure*", "*gcp*", "*eks*", "*aks*", "*gke*", "*lambda*", "*cloudformation*", "*.bicep",
              "serverless.yml", "*cloudrun*", "*app-service*")
_ADR = _any("*/adr/*", "adr/*", "*/decisions/*", "docs/decisions/*", "*/rfcs/*")
_FRONT = _any("*.tsx", "*.jsx", "*.vue", "*.svelte", ".storybook/*", "*/components/*")
_BACK = _any("*/api/*", "*/routes/*", "*/controllers/*", "*/handlers/*", "openapi.y*ml", "openapi.json",
             "*.proto", "*/server/*", "*/endpoints/*")
_DB = _any("*/migrations/*", "migrations/*", "alembic/*", "*/alembic/*", "*.sql", "schema.prisma",
           "*/prisma/*")
_DATA = _any("*/dags/*", "dags/*", "dbt_project.yml", "*/pipelines/*", "great_expectations/*", "*.ipynb",
             "dvc.yaml")
# Kept narrow: "*train*.py" matched constraints.py and "*eval*.py" any evaluation script.
_ML = _any("train.py", "train_*.py", "*_train.py", "training/*.py", "*/training/*.py", "mlproject", "*mlflow*",
           "dvc.yaml", "*model_card*", "*.ipynb", "*/notebooks/*", "*.onnx", "*.safetensors", "*lora*.py",
           "*/models/*.pt", "*/models/*.pkl")

_LAYERS = {"domain", "core", "services", "service", "adapters", "infrastructure", "infra", "api", "handlers",
           "controllers", "models", "repositories", "usecases", "use_cases", "ports", "application", "lib",
           "packages", "modules", "features", "components", "internal", "pkg", "cmd"}


@dataclass(frozen=True)
class _Rule:
    kind: str
    skills: tuple[str, ...]
    match: Callable[[str], bool]
    facets: tuple[str, ...]
    base: float
    per_item: float


_RULES: list[_Rule] = [
    _Rule("tests", ("automated_testing", "quality_control"), is_test, ("control",), 0.35, 0.05),
    _Rule("ci_pipeline", ("ci_cd",), _CI, ("control", "ownership"), 0.5, 0.1),
    _Rule("containers", ("containerization",), _CONTAINER, ("complex",), 0.45, 0.1),
    _Rule("infrastructure_code", ("infrastructure_as_code",), _IAC, ("complex", "ownership"), 0.45, 0.04),
    _Rule("cloud_resources", ("cloud_infrastructure",), _CLOUD, ("complex",), 0.4, 0.05),
    _Rule("security_controls", ("security_engineering",), _SECURITY, ("control",), 0.35, 0.1),
    _Rule("quality_tooling", ("code_quality",), _QUALITY, ("control",), 0.3, 0.07),
    _Rule("documentation", ("technical_documentation",), _DOCS, ("ownership",), 0.3, 0.04),
    _Rule("architecture_decisions", ("software_architecture", "technical_documentation"), _ADR,
          ("ownership", "complex"), 0.5, 0.08),
    _Rule("frontend_code", ("frontend_development",), _FRONT, (), 0.3, 0.01),
    _Rule("backend_code", ("backend_development",), _BACK, (), 0.3, 0.02),
    _Rule("db_migrations", ("database_design",), _DB, ("control",), 0.35, 0.04),
    _Rule("data_pipeline", ("data_engineering", "data_analysis"), _DATA, ("complex",), 0.35, 0.04),
    _Rule("ml_training", ("machine_learning",), _ML, ("complex",), 0.35, 0.05),
]


def _top_dirs(paths: list[str], limit: int = 4) -> str:
    dirs = Counter(PurePosixPath(p).parts[0] if len(PurePosixPath(p).parts) > 1 else "(root)" for p in paths)
    return ", ".join(d for d, _ in dirs.most_common(limit))


def analyze_repo(artifact: Artifact) -> list[Signal]:
    paths = artifact.repo_paths
    code = [p for p in paths if PurePosixPath(p).suffix in CODE_EXT]
    signals: list[Signal] = []

    def add(kind: str, skills: tuple[str, ...], strength: float, locator: str, sample: list[str],
            facets: tuple[str, ...]) -> None:
        signals.append(Signal(
            id=f"S-{artifact.id}-{len(signals) + 1:03d}", artifact_id=artifact.id, kind=kind, skills=list(skills),
            strength=round(min(1.0, strength), 3), facets=list(facets),
            evidence=EvidenceRef(artifact_id=artifact.id, artifact_label=artifact.label, locator=locator,
                                 excerpt="\n".join(sample[:6])),
        ))

    # Substance: practice files (CI, Dockerfile, security policy, lint config, docs) weigh less in a repository
    # that contains almost nothing else. A "showcase" repo of config files scored 38% before this (MEASUREMENTS.md).
    decorative = (_CI, _CONTAINER, _SECURITY, _QUALITY, _DOCS, _ADR)
    substantial = [p for p in paths if not any(m(p) for m in decorative)]
    substance = min(1.0, 0.25 + len(substantial) / 8)
    decorative_kinds = {"ci_pipeline", "containers", "security_controls", "quality_tooling", "documentation",
                        "architecture_decisions"}

    for rule in _RULES:
        hits = [p for p in paths if rule.match(p)]
        if not hits:
            continue
        if rule.kind == "tests":
            ratio = len(hits) / max(5, 0.25 * len(code))
            strength = 0.3 + 0.7 * min(1.0, ratio)
            facets = rule.facets + (("complex",) if len(hits) >= 20 else ())
        else:
            strength = rule.base + rule.per_item * (len(hits) - 1)
            facets = rule.facets
        if rule.kind in {"frontend_code", "backend_code"} and len(hits) < 3:
            continue  # a single stray file is not a practice
        if rule.kind in decorative_kinds:
            strength *= substance
        locator = f"{len(hits)} file(s) in {_top_dirs(hits)}"
        add(rule.kind, rule.skills, strength, locator, sorted(hits, key=len)[:6], facets)

    # Modular architecture: several code-bearing modules with recognisable layering.
    # Layer names are looked for at any depth: "src/<package>/domain" is the common case.
    folders = {str(PurePosixPath(p).parent) for p in code if not is_test(p)}
    layers = {part.lower() for p in code for part in PurePosixPath(p).parts[:-1]} & _LAYERS
    if len(code) >= 10 and (len(layers) >= 2 or len(folders) >= 5):
        strength = 0.35 + 0.1 * len(layers) + 0.01 * min(len(code), 100)
        add("modular_structure", ("software_architecture",), strength,
            f"{len(code)} source files across {len(folders)} folders",
            sorted(layers) or sorted(folders)[:6], ("complex",) if len(layers) >= 3 else ())

    _integration_signals(artifact, add)

    # End-to-end ownership: the same repository goes from code to tests, CI and packaging.
    kinds = {s.kind for s in signals}
    lifecycle = kinds & {"tests", "ci_pipeline", "containers", "documentation", "infrastructure_code"}
    if len(lifecycle) >= 4:
        for s in signals:
            if "ownership" not in s.facets:
                s.facets.append("ownership")
    return signals


_LINK_SKILLS = {"ci_orchestration": ("ci_cd",), "deployment": ("containerization",),
                "infrastructure_module": ("infrastructure_as_code",), "dependency": ("software_architecture",),
                "submodule": ("software_architecture",), "documentation": ()}
_LINK_STRENGTH = {"ci_orchestration": 0.75, "deployment": 0.75, "dependency": 0.7, "infrastructure_module": 0.7,
                  "submodule": 0.6, "documentation": 0.2}


def _integration_signals(artifact: Artifact, add: Callable[..., None]) -> None:
    """Signals from how this repository works with the candidate's other repositories and tools."""
    info = artifact.integration
    if not info:
        return
    for link in info.get("links", []):
        kind = link["kind"]
        weak = kind == "documentation"
        add("cross_repo_mention" if weak else "cross_repo_link",
            ("systems_integration", *_LINK_SKILLS.get(kind, ())), _LINK_STRENGTH.get(kind, 0.3),
            f"{link['file']}, line {link['line']} → {link['target']}", [link["excerpt"]],
            () if weak else ("complex", "ownership"))
    if info.get("linked_from"):
        add("cross_repo_link", ("systems_integration", "software_architecture"),
            0.4 + 0.1 * min(4, len(info["linked_from"])),
            f"used by {', '.join(info['linked_from'])}", [f"reused by {len(info['linked_from'])} other project(s)"],
            ("complex", "ownership"))
    tools, needs = info.get("tools", []), info.get("job_dependencies", 0)
    if len(tools) >= 3 or needs >= 2:
        add("pipeline_orchestration", ("systems_integration", "ci_cd"),
            0.25 + 0.05 * len(tools) + 0.08 * min(4, needs),
            f"{len(info.get('workflow_files', []))} workflow(s): {len(tools)} tools, {needs} job dependencies",
            [", ".join(tools)], ("control", "complex") if len(tools) >= 6 else ("control",))
    if info.get("services", 0) >= 3:
        add("service_orchestration", ("containerization", "systems_integration"),
            0.35 + 0.08 * min(5, info["services"]), f"{info['compose_file']}: {info['services']} services",
            [info["compose_file"]], ("complex",))
    for skill, deps in info.get("stack", {}).items():
        files = ", ".join(info.get("stack_files", {}).get(skill, []))
        add("declared_dependency", (skill,), min(0.5, 0.25 + 0.05 * len(deps)), f"{files}: {', '.join(deps)}",
            deps, ())


def select_key_files(paths: list[str], limit: int = 6) -> list[str]:
    """Pick the few files that best show practice, in priority order, for the escalation tier."""
    picks: list[str] = []

    def take(pred: Callable[[str], bool]) -> None:
        for p in sorted(paths, key=lambda x: (x.count("/"), len(x))):
            if pred(p) and p not in picks:
                picks.append(p)
                return

    take(_CI)
    take(_any("dockerfile", "containerfile"))
    take(_any("*.tf", "chart.yaml", "kustomization.yaml"))
    take(is_test)
    take(_any("main.py", "app.py", "main.go", "index.ts", "server.ts", "main.rs", "app.ts", "src/main.*"))
    take(_SECURITY)
    take(_any("readme.md"))
    return picks[:limit]

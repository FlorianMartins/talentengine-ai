"""Reading GitHub repositories without burning the 60-requests-per-hour REST quota.

* A profile URL (``github.com/<user>``) lists **all** its public, non-fork, non-archived repositories
  (one API call, up to ``max_repos``).
* Each repository tree is read with git itself (``clone --filter=blob:none --depth 1 --no-checkout`` then
  ``ls-tree``): file names only, no blobs, and git traffic does not count against the REST quota.
* A few files are then fetched from raw.githubusercontent.com (no quota either): the *key files* that
  best show practice (kept for the escalation tier) and the *integration files* (manifests, workflows,
  compose, Terraform, submodules) used to detect how the repositories and tools work together.
* Repositories are fetched in parallel.
"""

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..pilot.ownership import candidate_source_paths
from .repo import KEY_FILE_MAX_BYTES, RepoFetchError, RepoSnapshot, select_key_files

_PROFILE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<user>[A-Za-z0-9-]{1,39})/?$")
_REPO = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9-]{1,39})/(?P<repo>[\w.\-]{1,100}?)"
                   r"(?:\.git)?(?:/.*)?$")
GIT_TIMEOUT = 30
INTEGRATION_MAX_BYTES = 40_000
SOURCE_MAX_BYTES = 60_000

# Files that reveal how a repository depends on, deploys or orchestrates other projects and tools.
_INTEGRATION_PATTERNS = [
    ".gitmodules", "pyproject.toml", "requirements*.txt", "requirements/*.txt", "package.json", "go.mod",
    "Cargo.toml", "composer.json", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml",
    "docker-compose*.yml", "docker-compose*.yaml", "compose.yml", "compose.yaml", ".github/workflows/*.yml",
    ".github/workflows/*.yaml", "*.tf", "Chart.yaml", "kustomization.yaml", "Makefile", "README.md", "Dockerfile",
]


@dataclass
class FetchedRepo:
    url: str
    owner: str
    name: str
    snapshot: RepoSnapshot
    extra: dict[str, str] = field(default_factory=dict)  # integration files (raw, before the shield)
    sources: dict[str, str] = field(default_factory=dict)  # source files for the ownership task (raw)


def parse_repo_url(url: str) -> tuple[str, str]:
    m = _REPO.match(url.strip())
    if not m:
        raise RepoFetchError(f"not a GitHub repository URL: {url!r}")
    return m.group("owner"), m.group("repo")


def expand_github_urls(urls: list[str], token: str = "", max_repos: int = 30) -> list[str]:
    """Profile URLs become all their public, non-fork, non-archived repositories (most recent first)."""
    out: list[str] = []
    for url in urls:
        url = url.strip().rstrip("/")
        if not url:
            continue
        profile = _PROFILE.match(url)
        if profile:
            headers = {"Accept": "application/vnd.github+json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            resp = httpx.get(f"https://api.github.com/users/{profile.group('user')}/repos",
                             params={"sort": "pushed", "per_page": 100, "type": "owner"}, headers=headers, timeout=15)
            if resp.status_code == 403:
                raise RepoFetchError("GitHub rate limit reached: paste repository links instead of a profile")
            if resp.status_code != 200:
                raise RepoFetchError(f"GitHub profile not found ({resp.status_code})")
            repos = [r for r in resp.json() if not r.get("fork") and not r.get("archived") and r.get("size", 0) > 0]
            out += [r["html_url"] for r in repos]
        elif _REPO.match(url):
            owner, repo = parse_repo_url(url)
            out.append(f"https://github.com/{owner}/{repo}")
        else:
            raise RepoFetchError(f"not a GitHub link: {url}")
    unique: list[str] = []
    for u in out:
        if u.lower() not in (x.lower() for x in unique):
            unique.append(u)
    return unique[:max_repos]


def select_integration_files(paths: list[str], limit: int = 24) -> list[str]:
    picks: list[str] = []
    for pattern in _INTEGRATION_PATTERNS:
        matches = [p for p in sorted(paths, key=lambda x: (x.count("/"), x))
                   if "node_modules/" not in p and (fnmatch.fnmatch(p, pattern) or
                                                    (pattern == "package.json" and p.endswith("/package.json")
                                                     and p.count("/") <= 2) or
                                                    (pattern == "*.tf" and p.endswith(".tf")))]
        cap = 8 if pattern.startswith(".github/workflows") else 6 if pattern == "*.tf" else 3
        for p in matches[:cap]:
            if p not in picks:
                picks.append(p)
    return picks[:limit]


def snapshot_with_git(url: str, sources: int = 0) -> FetchedRepo:
    owner, repo = parse_repo_url(url)
    git = shutil.which("git")
    if git is None:
        raise RepoFetchError("git is not installed on the server")
    tmp = Path(tempfile.mkdtemp(prefix="te-git-"))
    env = {"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp)}
    try:
        subprocess.run(  # noqa: S603 - fixed argv, owner/repo validated by the regex above
            [git, "clone", "--quiet", "--filter=blob:none", "--depth", "1", "--no-checkout",
             f"https://github.com/{owner}/{repo}.git", str(tmp / "r")],
            check=True, capture_output=True, timeout=GIT_TIMEOUT, env=env)
        listing = subprocess.run(  # noqa: S603
            [git, "-C", str(tmp / "r"), "ls-tree", "-r", "--name-only", "HEAD"],
            check=True, capture_output=True, timeout=GIT_TIMEOUT, env=env, text=True).stdout
        sha = subprocess.run(  # noqa: S603
            [git, "-C", str(tmp / "r"), "rev-parse", "HEAD"],
            check=True, capture_output=True, timeout=GIT_TIMEOUT, env=env, text=True).stdout.strip()
    except subprocess.TimeoutExpired as exc:
        raise RepoFetchError(f"{owner}/{repo}: repository too slow to read") from exc
    except subprocess.CalledProcessError as exc:
        raise RepoFetchError(f"{owner}/{repo}: repository not found or private") from exc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    paths = [p for p in listing.splitlines() if p and "node_modules/" not in p][:20_000]
    key = select_key_files(paths)
    integration = select_integration_files(paths)
    files: dict[str, str] = {}
    extra: dict[str, str] = {}
    source: dict[str, str] = {}
    source_paths = [p for p in candidate_source_paths(paths, sources + len(key)) if p not in key][:sources]
    with httpx.Client(timeout=10) as client:
        for path in source_paths:
            raw = client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}")
            if raw.status_code == 200 and len(raw.content) <= SOURCE_MAX_BYTES:
                source[path] = raw.content.decode("utf-8", errors="replace")
        for path in dict.fromkeys(key + integration):
            raw = client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}")
            if raw.status_code != 200:
                continue
            if path in key:
                files[path] = raw.content[:KEY_FILE_MAX_BYTES].decode("utf-8", errors="replace")
            if path in integration:
                extra[path] = raw.content[:INTEGRATION_MAX_BYTES].decode("utf-8", errors="replace")
    return FetchedRepo(url=f"https://github.com/{owner}/{repo}", owner=owner, name=repo,
                       snapshot=RepoSnapshot(paths, files), extra=extra, sources=source)


def fetch_repositories(urls: list[str], token: str = "", max_repos: int = 30, workers: int = 6,
                       sources: int = 0) -> list[FetchedRepo]:
    """Expand profiles and read every repository in parallel. Unreadable repositories are skipped."""
    expanded = expand_github_urls(urls, token, max_repos)
    if not expanded:
        return []
    results: list[FetchedRepo | None] = [None] * len(expanded)
    errors: list[str] = []

    def one(i: int, url: str) -> None:
        try:
            results[i] = snapshot_with_git(url, sources)
        except RepoFetchError as exc:
            errors.append(str(exc))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, url in enumerate(expanded):
            pool.submit(one, i, url)
    fetched = [r for r in results if r is not None]
    if not fetched and errors:
        raise RepoFetchError(errors[0])
    return fetched


"""Source files for the ownership task, read from the visitor's public repositories (sandbox only).

Reuses the partial-clone reader of ``funnel/github.py`` (tree only, no REST quota) and its fetch of a few
likely-logic source files from raw.githubusercontent.com — a fixed host, so no SSRF surface.
Repositories are labelled ``repo-1``, ``repo-2``... as everywhere else; nothing is stored.
"""

from __future__ import annotations

from ..funnel.github import fetch_repositories
from .scenarios import Files


def fetch_sources(urls: list[str], token: str = "", max_repos: int = 6,
                  per_repo: int = 8) -> list[tuple[str, list[str], Files]]:
    repos = fetch_repositories(urls, token, max_repos=max_repos, sources=per_repo)
    return [(f"repo-{i}", r.snapshot.paths, {**r.snapshot.files, **r.sources}) for i, r in enumerate(repos, start=1)]

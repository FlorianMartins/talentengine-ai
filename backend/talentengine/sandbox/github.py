"""GitHub access for the public sandbox without burning the 60-requests-per-hour API quota.

* A repository tree is read with git itself (``clone --filter=blob:none --depth 1 --no-checkout`` then
  ``ls-tree``): file names only, no blobs, and git traffic is not counted against the REST quota.
* Key files are fetched from raw.githubusercontent.com (no quota either).
* Only a profile URL (``github.com/<user>``) needs one API call, to list the public repositories.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from ..funnel.repo import KEY_FILE_MAX_BYTES, RepoFetchError, RepoSnapshot, select_key_files

_PROFILE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<user>[A-Za-z0-9-]{1,39})/?$")
_REPO = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9-]{1,39})/(?P<repo>[\w.\-]{1,100}?)"
                   r"(?:\.git)?(?:/.*)?$")
GIT_TIMEOUT = 25


def expand_github_urls(urls: list[str], token: str = "", per_profile: int = 3) -> list[str]:
    """Profile URLs become their most recently pushed public, non-fork repositories."""
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
                             params={"sort": "pushed", "per_page": 30, "type": "owner"}, headers=headers, timeout=15)
            if resp.status_code == 403:
                raise RepoFetchError("GitHub rate limit reached: paste repository links instead of a profile")
            if resp.status_code != 200:
                raise RepoFetchError(f"GitHub profile not found ({resp.status_code})")
            repos = [r for r in resp.json() if not r.get("fork") and not r.get("archived") and r.get("size", 0) > 0]
            out += [r["html_url"] for r in repos[:per_profile]]
        elif _REPO.match(url):
            m = _REPO.match(url)
            assert m
            out.append(f"https://github.com/{m.group('owner')}/{m.group('repo')}")
        else:
            raise RepoFetchError(f"not a GitHub link: {url}")
    seen: list[str] = []
    for u in out:
        if u not in seen:
            seen.append(u)
    return seen


def snapshot_with_git(url: str) -> RepoSnapshot:
    m = _REPO.match(url)
    if not m:
        raise RepoFetchError(f"not a GitHub repository URL: {url!r}")
    owner, repo = m.group("owner"), m.group("repo")
    git = shutil.which("git")
    if git is None:
        raise RepoFetchError("git is not installed on the server")
    tmp = Path(tempfile.mkdtemp(prefix="te-git-"))
    env = {"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp)}
    try:
        subprocess.run(  # noqa: S603 - fixed argv, URL validated by the regex above
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
    paths = [p for p in listing.splitlines() if p][:20_000]
    files: dict[str, str] = {}
    with httpx.Client(timeout=10) as client:
        for path in select_key_files(paths):
            raw = client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}")
            if raw.status_code == 200:
                files[path] = raw.content[:KEY_FILE_MAX_BYTES].decode("utf-8", errors="replace")
    return RepoSnapshot(paths, files)

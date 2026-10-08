"""Virtual CI of the AI-pilot sandbox.

The default runner is **static**: the scenario's checks read the workspace (Python ``ast``, Dockerfile and
Compose rules) and never execute anything. Code written by a model that a candidate steers is untrusted
by definition; running it on the application server would hand the server to whoever writes the best
prompt.

``IsolatedRunner`` documents — and builds the exact command for — the next step: executing the
workspace's test suite in a throw-away container with no network, a read-only root, no capabilities, a
non-root user and hard CPU, memory, process and time limits. It must run on a **separate worker host**
(never through the application's own Docker socket, which is precisely the flaw of scenario 3), ideally
under gVisor (``--runtime runsc``). It is not wired into the API yet.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Locale
from .models import CheckResult
from .scenarios import Files, Scenario


def run_static(scenario: Scenario, files: Files, locale: str) -> tuple[list[CheckResult], bool]:
    loc: Locale = "en" if locale == "en" else "fr"
    results = [
        CheckResult(id=i, label=label, passed=ok, detail=detail[:200])
        for i, label, ok, detail in scenario.run_checks(files, loc)
    ]
    return results, all(r.passed for r in results)


class IsolatedRunner:
    """Command line for running a workspace's tests in a locked-down container (not wired yet)."""

    def __init__(self, image: str = "python:3.12.7-slim", runtime: str = "runsc", timeout_s: int = 60) -> None:
        self.image = image
        self.runtime = runtime
        self.timeout_s = timeout_s

    def argv(self, workspace: Path) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            f"--runtime={self.runtime}",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--user=65534:65534",
            "--memory=256m",
            "--cpus=0.5",
            "--pids-limit=64",
            "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
            f"--volume={workspace}:/work:ro",
            "--workdir=/work",
            self.image,
            "timeout",
            str(self.timeout_s),
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ]

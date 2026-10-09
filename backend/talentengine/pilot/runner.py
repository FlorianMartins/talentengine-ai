"""Executing the candidate's tests for real — in the isolated runner, never in this process.

``RunnerClient`` talks to the runner container (``runner/server.py``): no network, no secrets, read-only root,
no capabilities, hard limits. ``LocalRunner`` loads the same ``execute`` function in-process: it is for tests
and local development only (``TE_RUNNER_URL=local``), never for a deployment that receives real candidates.

Two uses:

* **visible CI** — the workspace's own tests (``tests/``) run like in a real pipeline: the candidate sees which
  pass and fail, with pytest's output;
* **hidden behavioural audits** — at close, small tests that *exercise* each planted flaw (an injection written
  in capitals, an IBAN in the logs, a pseudonym recomputable without a key…). A failing hidden test confirms
  the flaw by behaviour, not only by reading the code; a skipped one means "cannot tell" (the code is shaped
  differently) and the static audit decides alone.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    name: str
    file: str = ""
    outcome: str  # passed | failed | error | skipped
    message: str = ""


class TestRun(BaseModel):
    exit_code: int | None = None
    timed_out: bool = False
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    tests: list[TestCase] = Field(default_factory=list)
    output: str = ""
    duration: float = 0.0
    error: str = ""  # the runner could not be reached or refused the request

    @property
    def green(self) -> bool:
        return not self.error and self.exit_code == 0 and self.passed > 0 and not (self.failed or self.errors)


class Runner(Protocol):
    def run(self, files: dict[str, str], tests: list[str] | None = None, timeout: int = 30) -> TestRun: ...


class RunnerClient:
    def __init__(self, url: str, token: str, timeout: float = 70.0) -> None:
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def run(self, files: dict[str, str], tests: list[str] | None = None, timeout: int = 30) -> TestRun:
        try:
            resp = httpx.post(f"{self.url}/run", headers={"X-Runner-Token": self.token}, timeout=self.timeout,
                              json={"files": files, "tests": tests, "timeout": timeout})
        except httpx.HTTPError as exc:
            return TestRun(error=f"test runner unreachable ({type(exc).__name__})")
        if resp.status_code != 200:
            return TestRun(error=f"test runner error {resp.status_code}")
        return TestRun.model_validate(resp.json())


class LocalRunner:
    """Development and tests only: same code as the runner container, but inside this process's machine."""

    def __init__(self, path: str | Path | None = None) -> None:
        path = Path(path) if path else Path(__file__).resolve().parents[3] / "runner" / "server.py"
        spec = importlib.util.spec_from_file_location("te_runner_server", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"runner code not found at {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._execute: Any = module.execute

    def run(self, files: dict[str, str], tests: list[str] | None = None, timeout: int = 30) -> TestRun:
        try:
            return TestRun.model_validate(self._execute(files, tests, timeout))
        except ValueError as exc:
            return TestRun(error=str(exc)[:200])


def build_runner(url: str, token: str) -> Runner | None:
    if not url:
        return None
    if url == "local":
        return LocalRunner()
    return RunnerClient(url, token)


HIDDEN_DIR = "tests_hidden_te"


def hidden_verdicts(run: TestRun, files_by_fault: dict[str, str]) -> dict[str, bool | None]:
    """Fault id → True (a hidden test failed: flaw confirmed), False (all passed), None (cannot tell)."""
    out: dict[str, bool | None] = {}
    for fault_id, path in files_by_fault.items():
        stem = Path(path).stem
        cases = [t for t in run.tests if t.file.split(".")[-1] == stem or stem in t.file]
        if run.error or not cases:
            out[fault_id] = None
        elif any(t.outcome == "failed" for t in cases):
            out[fault_id] = True
        elif all(t.outcome == "passed" for t in cases):
            out[fault_id] = False
        else:
            out[fault_id] = None
    return out

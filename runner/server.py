"""TalentEngine-AI test runner: executes a workspace's pytest suite, nothing else.

It runs in its own container (see ``Dockerfile`` and the ``runner`` service of docker-compose.yml): no network
(an ``internal`` Docker network shared only with the application), no secrets, no data volume, read-only root,
no Linux capabilities, an unprivileged user, CPU/memory/process limits. Each run gets a fresh temporary
directory, hard resource limits (``setrlimit``) and a wall-clock timeout, and is killed with its whole process
group when time is up. Code written by a candidate or a model is untrusted: this container is disposable.

Protocol: ``POST /run`` with header ``X-Runner-Token`` and body
``{"files": {path: content}, "tests": ["tests/..."] | null, "timeout": seconds}`` →
``{"exit_code", "passed", "failed", "errors", "skipped", "tests": [{name, file, outcome, message}],
"output", "duration"}``. ``GET /health`` → ``{"ok": true}``. Standard library only (plus pytest itself).
"""

from __future__ import annotations

import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any

MAX_FILES = 80
MAX_BYTES = 2_000_000
MAX_TIMEOUT = 60
MEMORY_BYTES = int(os.environ.get("RUNNER_MEMORY_BYTES", str(1536 * 1024 * 1024)))
TOKEN = os.environ.get("RUNNER_TOKEN", "")
SLOTS = threading.Semaphore(int(os.environ.get("RUNNER_CONCURRENCY", "2")))


class BadRequest(ValueError):
    pass


def _validate(files: Any) -> dict[str, str]:
    if not isinstance(files, dict) or len(files) > MAX_FILES:
        raise BadRequest("files must be an object of at most 80 entries")
    total = 0
    out: dict[str, str] = {}
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            raise BadRequest("paths and contents must be strings")
        p = PurePosixPath(path)
        if p.is_absolute() or ".." in p.parts or not p.parts or len(path) > 200:
            raise BadRequest(f"invalid path: {path!r}")
        total += len(content.encode())
        out[str(p)] = content
    if total > MAX_BYTES:
        raise BadRequest("workspace too large")
    return out


def _limits() -> None:  # runs in the child, before exec
    os.setsid()
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_TIMEOUT, MAX_TIMEOUT))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _parse_junit(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    tests = []
    for case in ET.parse(path).getroot().iter("testcase"):
        outcome, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (node.get("message") or node.text or "")[:500]
                break
        tests.append({"name": case.get("name", ""), "file": case.get("classname", ""), "outcome": outcome,
                      "message": message})
    return tests


def execute(files: dict[str, str], tests: list[str] | None = None, timeout: int = 30) -> dict[str, Any]:
    """Write the workspace to a fresh directory and run pytest on it under hard limits."""
    files = _validate(files)
    timeout = max(1, min(int(timeout), MAX_TIMEOUT))
    work = Path(tempfile.mkdtemp(prefix="te-run-"))
    started = time.monotonic()
    try:
        for path, content in files.items():
            target = work / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for d in {p.parent for p in work.rglob("*.py")}:  # make every folder importable as a package
            if d != work and not (d / "__init__.py").exists() and d.name != "__pycache__":
                (d / "__init__.py").write_text("")
        junit = work / ".junit.xml"
        targets = [t for t in (tests or []) if (work / t).exists()] or ["."]
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(work),
               f"--junitxml={junit}", "-o", "junit_family=xunit1", *targets]
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(work), "HOME": str(work),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8",
               # one thread for numerical libraries: predictable under the memory limit
               "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                preexec_fn=_limits)  # noqa: S603 - fixed argv
        try:
            out, _ = proc.communicate(timeout=timeout)
            code: int | None = proc.returncode
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
            code = None
        results = _parse_junit(junit)
        count = {k: sum(t["outcome"] == k for t in results) for k in ("passed", "failed", "error", "skipped")}
        text = out.decode("utf-8", errors="replace")
        return {"exit_code": code, "timed_out": code is None, "passed": count["passed"], "failed": count["failed"],
                "errors": count["error"], "skipped": count["skipped"], "tests": results[:200],
                "output": text[-6000:], "duration": round(time.monotonic() - started, 2)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "te-runner"

    def _send(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        self._send(200 if self.path == "/health" else 404, {"ok": self.path == "/health"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            return self._send(404, {"error": "not found"})
        if not TOKEN or self.headers.get("X-Runner-Token") != TOKEN:
            return self._send(401, {"error": "bad token"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_BYTES * 2:
                raise BadRequest("request too large")
            body = json.loads(self.rfile.read(length))
            if not SLOTS.acquire(timeout=30):
                return self._send(503, {"error": "busy"})
            try:
                result = execute(body.get("files", {}), body.get("tests"), body.get("timeout", 30))
            finally:
                SLOTS.release()
            self._send(200, result)
        except (BadRequest, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)[:200]})

    def log_message(self, fmt: str, *args: Any) -> None:  # no request bodies in logs
        sys.stderr.write("runner %s\n" % (fmt % args))


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("RUNNER_TOKEN is required")
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("RUNNER_PORT", "8090"))), Handler).serve_forever()

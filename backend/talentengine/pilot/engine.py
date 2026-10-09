"""AI-pilot sessions: lifecycle, server-side timing, telemetry, injection and the final report.

Phases: ``brief`` (read the mission and the rules) → ``build`` (pilot the assistant, timed) →
``ownership`` (optional, five minutes on one's own code) → ``closed``. Every action is a turn of the
telemetry. Deadlines are enforced by the server; a reload never resets a clock.

Sandbox sessions live in memory; candidate sessions are stored under the candidate (erased with them).
"""

from __future__ import annotations

import ast
import hashlib
import random
import re
import secrets
import threading
from datetime import timedelta
from typing import Any

from ..models import utcnow
from ..shield.injection import screen
from ..store import Store
from .assistant import Assistant, HallucinationInjector, ScriptedAssistant
from .ci import run_static
from .judge import LLMError, apply_judge, manipulation_suspected, run_judge, valid_callouts
from .models import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_PROMPT_CHARS,
    MAX_TURNS,
    AISandboxSession,
    FileChange,
    InjectedFault,
    MetricScore,
    OwnershipTask,
    PilotEvaluationReport,
)
from .ownership import CONSTRAINTS, analyse
from .scenarios import SCENARIOS, Files, Scenario, fold
from .scoring import WEIGHTS, critical_thinking, detect_callouts, intent_precision, orchestration_velocity, pilot_index

BUILD_MINUTES = {1: 35, 2: 25, 3: 20}
FAULTS_PER_LEVEL = {1: 1, 2: 2, 3: 3}

NOTICE = {
    "fr": (
        "Ce test mesure la façon de piloter un assistant d'IA : cadrage, relecture critique, redirection et "
        "connaissance de son propre code. Il ne mesure ni la personnalité ni les émotions ; aucune caméra, aucun "
        "micro. C'est une aide à la décision : le recruteur décide, et le résultat se discute en entretien."
    ),
    "en": (
        "This test measures how a person pilots an AI assistant: framing, critical review, redirection and "
        "knowledge of their own code. It measures neither personality nor emotions; no camera, no microphone. "
        "It supports a decision: the recruiter decides, and the result is discussed at the interview."
    ),
}
LIMITS = [
    "The assistant's flaws are drawn from a fixed pool per scenario: a candidate who knows the pool can anticipate "
    "them. Anticipation is still a professional behaviour, and the interview should probe it.",
    "Call-outs are detected by keyword rules (French and English) and, when configured, by a judge model whose "
    "influence is bounded; phrasing outside both can be missed — read the transcript.",
    "The virtual CI is static analysis; it does not execute the code.",
    "Five minutes on one's own code is short and stressful; a low authenticity signal is a question for the "
    "interview, never a conclusion.",
]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _diff(before: Files, after: Files) -> list[FileChange]:
    out = []
    for path in sorted(set(before) | set(after)):
        a, b = before.get(path), after.get(path)
        if a == b:
            continue
        la, lb = (a or "").splitlines(), (b or "").splitlines()
        sa, sb = set(la), set(lb)
        out.append(
            FileChange(
                path=path,
                before_sha=_sha(a) if a is not None else "",
                after_sha=_sha(b) if b is not None else "",
                added_lines=sum(1 for ln in lb if ln not in sa),
                removed_lines=sum(1 for ln in la if ln not in sb),
            )
        )
    return out


class PilotError(Exception):
    """An action that the session's phase or clock does not allow (HTTP 409)."""


class PilotEngine:
    def __init__(
        self, store: Store | None = None, assistant: Assistant | None = None, judge_provider: Any = None
    ) -> None:
        self.store = store
        self.assistant: Assistant = assistant or ScriptedAssistant()
        self.judge_provider = judge_provider
        self.injector = HallucinationInjector()
        self._memory: dict[str, AISandboxSession] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------------------------------ storage

    def _save(self, key: str, s: AISandboxSession) -> None:
        with self._lock:
            if s.mode == "candidate" and self.store is not None:
                self.store.put("pilot_sessions", key, s, parent=s.candidate_ref)
            else:
                self._memory[key] = s
                now = utcnow()
                for k in [k for k, v in self._memory.items() if v.expires_at < now]:
                    del self._memory[k]

    def get(self, token: str) -> tuple[str, AISandboxSession]:
        key = _hash(token)
        with self._lock:
            s = self._memory.get(key)
            if s is None and self.store is not None:
                s = self.store.get("pilot_sessions", key, AISandboxSession)
        if s is None:
            raise KeyError("unknown or expired AI-pilot link")
        if s.phase not in ("closed",) and s.expires_at < utcnow():
            s.phase = "expired"
        return key, s

    def by_id(self, session_id: str) -> tuple[str, AISandboxSession]:
        if self.store is None:
            raise KeyError("no store")
        rows = self.store.query(
            "SELECT id FROM documents WHERE collection = 'pilot_sessions' AND id LIKE ?", (f"{session_id}%",)
        )
        for row in rows:
            s = self.store.get("pilot_sessions", row["id"], AISandboxSession)
            if s and s.id == session_id:
                return row["id"], s
        raise KeyError("unknown AI-pilot session")

    def list_for(self, candidate_ref: str) -> list[AISandboxSession]:
        return self.store.list("pilot_sessions", AISandboxSession, parent=candidate_ref) if self.store else []

    # ------------------------------------------------------------------------------------------ lifecycle

    def create(
        self,
        scenario: Scenario,
        level: int,
        *,
        locale: str,
        mode: str,
        job_title: str = "",
        job_id: str = "",
        candidate_ref: str = "",
        fault_ids: list[str] | None = None,
        build_minutes: int | None = None,
        ownership: tuple[OwnershipTask, Files] | None = None,
        valid_hours: int = 72,
    ) -> tuple[str, AISandboxSession]:
        token = secrets.token_urlsafe(24)
        rng = random.SystemRandom()  # per-candidate variant: which flaws, in which order of appearance
        pool = [f.id for f in scenario.faults]
        chosen = [f for f in (fault_ids or []) if f in pool] or rng.sample(
            pool, min(len(pool), FAULTS_PER_LEVEL[level])
        )
        session = AISandboxSession(
            id=_hash(token)[:16],
            mode=mode,
            locale="en" if locale == "en" else "fr",
            scenario_id=scenario.id,
            level=level,
            job_title=job_title,
            job_id=job_id,
            candidate_ref=candidate_ref,
            expires_at=utcnow() + timedelta(hours=valid_hours),
            build_minutes=build_minutes or BUILD_MINUTES[level],
            assistant_kind=self.assistant.kind,
            files=scenario.starter(),
            flags=sorted(f"fix:{f}" for f in pool if f not in chosen),
            rendered_flags=sorted(f"fix:{f}" for f in pool if f not in chosen),
            faults=[
                InjectedFault(
                    id=f,
                    category=scenario.fault(f).category,
                    cwe=scenario.fault(f).cwe,
                    title=scenario.fault(f).title[locale if locale in ("fr", "en") else "fr"],
                )
                for f in chosen
            ],
        )
        if ownership:
            session.ownership, session.ownership_files = ownership
        self._save(_hash(token), session)
        return token, session

    def state(self, token: str) -> dict[str, Any]:
        _, s = self.get(token)
        self._tick(s)
        scenario = SCENARIOS[s.scenario_id]
        now = utcnow()
        own = s.ownership
        return {
            "id": s.id,
            "mode": s.mode,
            "phase": s.phase,
            "locale": s.locale,
            "level": s.level,
            "job_title": s.job_title,
            "scenario": {"id": scenario.id, "title": scenario.title[s.locale], "brief": scenario.brief[s.locale]},
            "build_minutes": s.build_minutes,
            "build_remaining": max(0, int((s.build_deadline - now).total_seconds())) if s.build_deadline else None,
            "files": s.ownership_files if s.phase == "ownership" else s.files,
            "transcript": [t.public() for t in s.turns],
            "ownership": own.public() if own else None,
            "ownership_available": own is not None,
            "ownership_remaining": max(0, int((own.deadline - now).total_seconds())) if own and own.deadline else None,
            "assistant": "reference" if s.assistant_kind == "scripted" else "model",
            "expires_at": s.expires_at.isoformat(),
            "server_time": now.isoformat(),  # clients align their countdown on it
            "notice": NOTICE[s.locale],
            "report": s.report if s.mode == "sandbox" else None,
        }

    def _tick(self, s: AISandboxSession) -> None:
        """Advance phases whose clock ran out (the server, not the browser, keeps time)."""
        now = utcnow()
        if s.phase == "build" and s.build_deadline and now >= s.build_deadline:
            s.add_turn("phase", text="build time over")
            s.phase = "ownership" if s.ownership else "closed"
        if s.phase == "ownership" and s.ownership and s.ownership.deadline and now >= s.ownership.deadline:
            s.add_turn("phase", text="ownership time over")
            s.phase = "closed"

    def _open(self, token: str, phases: tuple[str, ...]) -> tuple[str, AISandboxSession]:
        key, s = self.get(token)
        self._tick(s)
        if s.phase not in phases:
            self._save(key, s)
            raise PilotError(f"not allowed in phase '{s.phase}'")
        if len(s.turns) >= MAX_TURNS:
            raise PilotError("turn limit reached: close the test")
        return key, s

    def begin(self, token: str) -> dict[str, Any]:
        key, s = self.get(token)
        if s.phase == "brief":
            now = utcnow()
            s.phase = "build"
            s.build_started_at = now
            s.build_deadline = now + timedelta(minutes=s.build_minutes)
            s.add_turn("phase", text="build started")
            self._save(key, s)
        return self.state(token)

    def arm_fault(self, session_id: str, fault_id: str) -> AISandboxSession:
        """A recruiter arms one more flaw from the scenario's pool; it appears at the next reply it fits."""
        key, s = self.by_id(session_id)
        scenario = SCENARIOS[s.scenario_id]
        if fault_id not in {f.id for f in scenario.faults}:
            raise ValueError(f"unknown flaw for scenario {scenario.id}: {fault_id}")
        if s.phase in ("closed", "expired"):
            raise PilotError(f"the session is {s.phase}")
        if any(f.id == fault_id for f in s.faults):
            raise PilotError("this flaw is already part of the session")
        fault = scenario.fault(fault_id)
        s.faults.append(InjectedFault(id=fault.id, category=fault.category, cwe=fault.cwe, title=fault.title[s.locale]))
        s.flags = [f for f in s.flags if f != f"fix:{fault_id}"]  # nothing is shown to the candidate
        self._save(key, s)
        return s

    # ------------------------------------------------------------------------------------------ build actions

    def chat(self, token: str, message: str) -> dict[str, Any]:
        key, s = self._open(token, ("build", "ownership"))
        message = message.strip()[:MAX_PROMPT_CHARS]
        if not message:
            raise ValueError("empty instruction")
        scenario = SCENARIOS[s.scenario_id]
        prompt = s.add_turn("prompt", text=message, screened=screen(message))
        if s.phase == "ownership":
            reply_text, changed = self._ownership_reply(s, message)
            before = dict(s.ownership_files)
            s.ownership_files.update(changed)
            s.add_turn("assistant", text=reply_text, changes=_diff(before, s.ownership_files))
            self._save(key, s)
            return {"prompt": prompt.public(), "reply": s.turns[-1].public(), "files": s.ownership_files}
        detect_callouts(s, scenario)  # a prompt can prevent a flaw before it is planted, or call one out
        reply = self.assistant.reply(s, scenario, message, self.injector.directives(s, scenario))
        before = dict(s.files)
        files = {**s.files, **reply.files}
        if len(files) > MAX_FILES:
            files = dict(list(files.items())[:MAX_FILES])
        files, injected, how = self.injector.after_reply(s, scenario, files, len(s.turns), reply.method)
        s.files = files
        turn = s.add_turn(
            "assistant", text=reply.message, changes=_diff(before, files), injected=injected, injection_method=how
        )
        turn.faults_active = [
            f.id for f in s.faults if f.injected_turn is not None and scenario.fault(f.id).present(files)
        ]
        self._save(key, s)
        return {"prompt": prompt.public(), "reply": turn.public(), "files": s.files}

    def edit(self, token: str, path: str, content: str | None, create_only: bool = False) -> dict[str, Any]:
        key, s = self._open(token, ("build", "ownership"))
        path = path.strip().lstrip("/")
        if not path or ".." in path.split("/") or len(path) > 200:
            raise ValueError("invalid file path")
        if content is not None and len(content.encode()) > MAX_FILE_BYTES:
            raise ValueError("file too large")
        target = s.ownership_files if s.phase == "ownership" else s.files
        if create_only and path in target:
            raise PilotError(f"{path} already exists")
        if content is not None and path not in target and len(target) >= MAX_FILES:
            raise ValueError("too many files")
        before = dict(target)
        if content is None:
            target.pop(path, None)
        else:
            target[path] = content
        turn = s.add_turn(
            "edit", text=f"edited {path}" if content is not None else f"deleted {path}", changes=_diff(before, target)
        )
        if s.phase == "build":
            scenario = SCENARIOS[s.scenario_id]
            for f in s.faults:  # removing a planted flaw by hand is a call-out too
                fault = scenario.fault(f.id)
                if (
                    f.injected_turn is not None
                    and f.detected_turn is None
                    and fault.present(before)
                    and not fault.present(target)
                ):
                    f.detected_turn, f.detected_by = turn.index, "edit"
            turn.faults_active = [
                f.id for f in s.faults if f.injected_turn is not None and scenario.fault(f.id).present(target)
            ]
        self._save(key, s)
        return {"turn": turn.public(), "files": target}

    def run_ci(self, token: str) -> dict[str, Any]:
        key, s = self._open(token, ("build",))
        checks, passed = run_static(SCENARIOS[s.scenario_id], s.files, s.locale)
        turn = s.add_turn("ci", text="CI " + ("passed" if passed else "failed"), checks=checks, passed=passed)
        self._save(key, s)
        return turn.public()

    # ------------------------------------------------------------------------------------------ ownership

    def start_ownership(self, token: str) -> dict[str, Any]:
        key, s = self.get(token)
        self._tick(s)
        if s.ownership is None:
            raise PilotError("no ownership task in this session")
        if s.phase == "build":
            s.add_turn("phase", text="build closed by the candidate")
            s.phase = "ownership"
        if s.phase != "ownership":
            raise PilotError(f"not allowed in phase '{s.phase}'")
        if s.ownership.started_at is None:
            now = utcnow()
            s.ownership.started_at = now
            s.ownership.deadline = now + timedelta(seconds=s.ownership.seconds)
            s.add_turn("phase", text="ownership task started")
        self._save(key, s)
        return self.state(token)

    def _ownership_reply(self, s: AISandboxSession, message: str) -> tuple[str, Files]:
        """Reference behaviour in the ownership phase: a draft at the requested place, nothing clever."""
        task = s.ownership
        assert task is not None
        if task.started_at is None:
            raise PilotError("start the ownership task first")
        if not isinstance(self.assistant, ScriptedAssistant):
            reply = self.assistant.reply(s, SCENARIOS[s.scenario_id], message, [])
            return reply.message, {p: c for p, c in reply.files.items() if p in s.ownership_files}
        constraint = next(c for c in CONSTRAINTS if c[0] == task.constraint_id)
        folded = fold(message)
        if not re.search(constraint[3], folded, re.I):
            return (
                "Que voulez-vous que je change exactement, et où ?"
                if s.locale == "fr"
                else "What exactly should I change, and where?"
            ), {}
        src = s.ownership_files.get(task.path, "")
        lines = src.splitlines()
        marker = {
            "prometheus_cache": "cache hit/miss counter (Prometheus) + TTL cache",
            "retry_backoff": "retry with exponential backoff + Prometheus retry counter",
            "audit_log": "audit log line with masked identifiers (pseudonymised)",
            "latency_histogram": "Prometheus latency histogram, label outcome=ok|error",
        }[task.constraint_id]
        comment = "#" if task.language in ("python", "ruby") else "//"
        insert_at = task.start_line  # right after the signature's first line
        if task.language == "python":
            try:
                fn = next(
                    n
                    for n in ast.walk(ast.parse(src))
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == task.function
                )
                insert_at = fn.body[0].lineno - 1
            except (SyntaxError, StopIteration):
                pass
        indent = " " * (len(lines[insert_at]) - len(lines[insert_at].lstrip())) if insert_at < len(lines) else "    "
        lines[insert_at:insert_at] = [f"{indent}{comment} TODO(assistant draft): {marker}"]
        s.ownership_files[task.path] = "\n".join(lines) + "\n"
        return (
            "J'ai placé un brouillon au début de la fonction ; précisez où l'insérer si un autre endroit convient "
            "mieux."
            if s.locale == "fr"
            else "I put a draft at the start of the function; tell me where to put it if another place fits better."
        ), {task.path: s.ownership_files[task.path]}

    # ------------------------------------------------------------------------------------------ close & report

    def close(self, token: str) -> tuple[AISandboxSession, dict[str, Any], bool]:
        """Returns the session, its report, and whether the report was computed by this call."""
        key, s = self.get(token)
        if s.report is not None:
            return s, s.report, False
        if s.phase == "expired" and s.build_started_at is None:
            raise PilotError("this link expired before the test was started")
        if s.phase not in ("closed", "expired"):
            s.add_turn("phase", text="closed by the candidate")
        s.phase = "closed"
        s.closed_at = utcnow()
        report = self.evaluate(s)
        s.report = report.model_dump(mode="json")
        self._save(key, s)
        return s, s.report, True

    def evaluate(self, s: AISandboxSession) -> PilotEvaluationReport:
        scenario = SCENARIOS[s.scenario_id]
        detect_callouts(s, scenario)
        checks, green = run_static(scenario, s.files, s.locale)
        passing = sum(c.passed for c in checks) / max(1, len(checks))
        judge_data: dict[str, Any] | None = None
        errors: list[str] = []
        judge_name = "none"
        if self.judge_provider is not None and s.prompts():
            judge_name = f"{self.judge_provider.name}/{self.judge_provider.model}"
            try:
                judge_data = run_judge(self.judge_provider, s, scenario)
            except LLMError as exc:
                errors.append(str(exc)[:200])
        callouts = valid_callouts(s, judge_data)
        m1 = intent_precision(s)
        m2, faults = critical_thinking(s, scenario, s.files, callouts)
        m3, velocity = orchestration_velocity(s, scenario, green, passing)
        own_prompts = (
            [(t.index, (t.at - s.ownership.started_at).total_seconds(), t.text) for t in s.prompts("ownership")]
            if s.ownership and s.ownership.started_at
            else []
        )
        original = {s.ownership.path: s.ownership.original_source} if s.ownership else {}
        facts, own_score, own_evidence, own_breakdown = analyse(s.ownership, own_prompts, s.ownership_files, original)
        metrics: list[MetricScore] = [m1, m2, m3]
        own_metric: MetricScore | None = None
        if own_score is not None:
            own_metric = MetricScore(
                id="ownership",
                label="Authenticité de la preuve (code personnel)"
                if s.locale == "fr"
                else "Authenticity of the evidence (own code)",
                factual_pct=own_score,
                final_pct=own_score,
                breakdown=own_breakdown,
                evidence=own_evidence[:8],
            )
        if judge_data:
            manip = manipulation_suspected(
                s, [i for i in judge_data.get("manipulation_turns", []) if isinstance(i, int)]
            )
            if manip:
                errors.append(f"evaluator addressed in turn(s) {manip}: the judge may only lower scores")
            build_turns = {t.index for t in s.turns if t.kind in ("prompt", "edit") and t.phase == "build"}
            own_turns = {t.index for t in s.turns if t.kind in ("prompt", "edit") and t.phase == "ownership"}
            apply_judge(m1, judge_data.get("intent_precision"), build_turns, may_raise=not manip)
            if faults:
                apply_judge(m2, judge_data.get("critical_thinking"), build_turns, may_raise=not manip)
            if own_metric:
                apply_judge(own_metric, judge_data.get("ownership"), own_turns, may_raise=not manip)
        if own_metric:
            metrics.append(own_metric)
        started = s.build_started_at or s.created_at
        return PilotEvaluationReport(
            session_id=s.id,
            scenario_id=scenario.id,
            scenario_title=scenario.title[s.locale],
            locale=s.locale,
            level=s.level,
            job_title=s.job_title,
            assistant="reference assistant (scripted)" if s.assistant_kind == "scripted" else s.assistant_kind,
            judge=judge_name,
            judge_errors=errors,
            metrics=metrics,
            pilot_index_pct=pilot_index(metrics),
            authenticity_pct=own_metric.final_pct if own_metric else None,
            faults=faults,
            velocity=velocity,
            ownership=facts,
            prompts=len(s.prompts()),
            duration_minutes=round(((s.closed_at or utcnow()) - started).total_seconds() / 60, 1),
            weights=WEIGHTS,
            notice=NOTICE[s.locale],
            limits=LIMITS,
        )

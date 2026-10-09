"""Technical-test sessions: lifecycle, server-side timing, telemetry, injection and the final report.

Phases: ``brief`` (read the rules) → ``questions`` (section 1, knowledge with tools allowed; section 2, with
the built-in assistant) → ``build`` (section 3, the practical mission with planted flaws, timed) →
``ownership`` (five minutes on one's own code) → ``closed``. Each phase is optional except the brief: a job
with no practical mission yet gets the questions only. Every action is a turn of the
telemetry. Deadlines are enforced by the server; a reload never resets a clock.

Sandbox sessions live in memory; candidate sessions are stored under the candidate (erased with them).
"""

from __future__ import annotations

import ast
import hashlib
import logging
import random
import re
import secrets
import threading
from datetime import timedelta
from typing import Any

from ..assessment.engine import GRACE_SECONDS
from ..models import utcnow
from ..sandbox.sessions import SandboxSessions
from ..shield.injection import screen
from ..store import Store
from .assistant import Assistant, HallucinationInjector, LLMAssistant, ScriptedAssistant
from .ci import run_ci
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
    PilotQuestion,
)
from .ownership import CONSTRAINTS, analyse
from .questions import (
    ai_usage,
    applied_knowledge,
    outcomes,
    reference_reply,
    score_answer,
    trap_scores,
)
from .runner import HIDDEN_DIR, hidden_verdicts
from .scenarios import SCENARIOS, Files, Scenario, fold
from .scoring import WEIGHTS, critical_thinking, detect_callouts, intent_precision, orchestration_velocity, pilot_index

log = logging.getLogger(__name__)
BUILD_MINUTES = {1: 35, 2: 25, 3: 20}
FAULTS_PER_LEVEL = {1: 1, 2: 2, 3: 3}

NOTICE = {
    "fr": (
        "Ce test technique se passe comme au travail : calculatrice, internet et IA sont permis. Il mesure ce que "
        "vous savez appliquer, la façon dont vous utilisez l'assistant d'IA (cadrage, relecture critique, "
        "redirection) et la connaissance de votre propre code. Il ne mesure ni la personnalité ni les émotions ; "
        "aucune caméra, aucun micro. C'est une aide à la décision : le recruteur décide, et le résultat se "
        "discute en entretien."
    ),
    "en": (
        "This technical test works like the job: calculator, internet and AI are allowed. It measures what you "
        "can apply, how you use the AI assistant (framing, critical review, redirection) and how well you know "
        "your own code. It measures neither personality nor emotions; no camera, no microphone. It supports a "
        "decision: the recruiter decides, and the result is discussed at the interview."
    ),
}
LIMITS = [
    "Tools are allowed and not monitored: a right answer in section 1 may come from a search or another AI, as "
    "it would at work. The signal is the right answer in the time given, and the interview checks the reasoning.",
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
    """An action that the session's phase or clock does not allow (HTTP 409), with a stable machine code."""

    def __init__(self, message: str, code: str = "not_allowed") -> None:
        super().__init__(message)
        self.code = code


class PilotEngine:
    def __init__(
        self,
        store: Store | None = None,
        assistant: Assistant | None = None,
        judge_provider: Any = None,
        sandbox_key: str | None = None,
        byok: Any = None,
        runner: Any = None,
    ) -> None:
        self.store = store
        self.assistant: Assistant = assistant or ScriptedAssistant()
        self.judge_provider = judge_provider  # the deployment's own model, if any
        self.runner = runner  # isolated test runner (pilot/runner.py); None: static checks only
        self.byok = byok  # ByokStore: each recruiter's own model key, used for the tests they send
        self.judge_in_background = True  # a candidate's close never waits for a judge model
        self.on_judged: Any = None  # callback(session, report) once a background judge has run
        self.injector = HallucinationInjector()
        self._sandbox = SandboxSessions("pilot", store, sandbox_key)  # survives a restart, encrypted, 3 h max
        self._lock = threading.RLock()

    # ------------------------------------------------------------------------------------------ models

    def _judge_for(self, s: AISandboxSession) -> Any:
        """The recruiter's own model when they connected one for judging, else the deployment's, else none."""
        own = self.byok.provider(s.llm_owner, "judge") if (self.byok is not None and s.llm_owner) else None
        return own or self.judge_provider

    def _assistant_for(self, s: AISandboxSession) -> Assistant:
        if self.byok is not None and s.llm_owner:
            provider = self.byok.provider(s.llm_owner, "assistant")
            if provider is not None:
                return LLMAssistant(provider)
        return self.assistant

    # ------------------------------------------------------------------------------------------ storage

    def _save(self, key: str, s: AISandboxSession) -> None:
        with self._lock:
            if s.mode == "candidate" and self.store is not None:
                self.store.put("pilot_sessions", key, s, parent=s.candidate_ref)
            else:
                self._sandbox.put(key, s, s.expires_at)

    def get(self, token: str) -> tuple[str, AISandboxSession]:
        key = _hash(token)
        with self._lock:
            s = self._sandbox.get(key, AISandboxSession)
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
        scenario: Scenario | None,
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
        questions: list[PilotQuestion] | None = None,
        llm_owner: str = "",
    ) -> tuple[str, AISandboxSession]:
        if scenario is None and not questions:
            raise ValueError("a technical test needs questions, a practical mission, or both")
        token = secrets.token_urlsafe(24)
        rng = random.SystemRandom()  # per-candidate variant: which flaws, in which order of appearance
        pool = [f.id for f in scenario.faults] if scenario else []
        chosen = [f for f in (fault_ids or []) if f in pool] or (
            rng.sample(pool, min(len(pool), FAULTS_PER_LEVEL[level])) if pool else []
        )
        session = AISandboxSession(
            id=_hash(token)[:16],
            mode=mode,
            locale="en" if locale == "en" else "fr",
            scenario_id=scenario.id if scenario else "",
            level=level,
            job_title=job_title,
            job_id=job_id,
            candidate_ref=candidate_ref,
            expires_at=utcnow() + timedelta(hours=valid_hours),
            build_minutes=build_minutes or BUILD_MINUTES[level],
            assistant_kind=self.assistant.kind,
            llm_owner=llm_owner,
            files=scenario.starter() if scenario else {},
            questions=questions or [],
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
            ]
            if scenario
            else [],
        )
        session.assistant_kind = self._assistant_for(session).kind
        if ownership:
            session.ownership, session.ownership_files = ownership
        self._save(_hash(token), session)
        return token, session

    def state(self, token: str) -> dict[str, Any]:
        _, s = self.get(token)
        self._tick(s)
        scenario = SCENARIOS.get(s.scenario_id)
        now = utcnow()
        own = s.ownership
        sections = {sec: sum(q.section == sec for q in s.questions) for sec in ("knowledge", "ai")}
        return {
            "id": s.id,
            "mode": s.mode,
            "phase": s.phase,
            "locale": s.locale,
            "level": s.level,
            "job_title": s.job_title,
            "scenario": {"id": scenario.id, "title": scenario.title[s.locale], "brief": scenario.brief[s.locale]}
            if scenario
            else None,
            "questions": {
                "total": len(s.questions), "current": s.current_question, "knowledge": sections["knowledge"],
                "with_ai": sections["ai"], "personal": sum(q.personal for q in s.questions),
                "minutes": round(sum(q.seconds for q in s.questions) / 60),
                "minutes_knowledge": round(sum(q.seconds for q in s.questions if q.section == "knowledge") / 60),
                "minutes_ai": round(sum(q.seconds for q in s.questions if q.section == "ai") / 60),
            },
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
        if s.phase == "questions" and s.current_question < len(s.questions):
            q = s.questions[s.current_question]
            if q.deadline and now >= q.deadline + timedelta(seconds=GRACE_SECONDS) and q.answered_at is None:
                q.score, q.late, q.answered_at = 0.0, True, now
                s.current_question += 1
        if s.phase == "questions" and s.current_question >= len(s.questions):
            self._after_questions(s, now)
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
        if s.phase == "build" and s.build_deadline is None:
            self._start_build(s, utcnow())  # an older client acting on the mission starts its clock
        return key, s

    def begin(self, token: str) -> dict[str, Any]:
        key, s = self.get(token)
        if s.phase == "brief":
            now = utcnow()
            if s.questions:
                s.phase = "questions"
                s.add_turn("phase", text="questions started")
            else:
                self._after_questions(s, now)
                if s.phase == "build":
                    self._start_build(s, now)  # no questions: "begin" is the explicit start of the mission
            self._save(key, s)
        return self.state(token)

    def _start_build(self, s: AISandboxSession, now: Any) -> None:
        if s.build_deadline is None:
            s.build_started_at = now
            s.build_deadline = now + timedelta(minutes=s.build_minutes)
            s.add_turn("phase", text="build started")

    def start_build(self, token: str) -> dict[str, Any]:
        """The candidate leaves the section 3 introduction: the mission clock starts now, not before."""
        key, s = self.get(token)
        self._tick(s)
        if s.phase != "build":
            raise PilotError(f"not allowed in phase '{s.phase}'")
        self._start_build(s, utcnow())
        self._save(key, s)
        return self.state(token)

    def _after_questions(self, s: AISandboxSession, now: Any) -> None:
        """Questions done (or none): the practical mission if the job has one, else the own-code task, else close."""
        if s.scenario_id:
            s.phase = "build"  # the clock starts when the candidate opens the mission (start_build)
            s.add_turn("phase", text="questions done")
        elif s.ownership:
            s.phase = "ownership"
            s.add_turn("phase", text="questions done")
        else:
            s.phase = "closed"
            s.add_turn("phase", text="questions done")

    # ------------------------------------------------------------------------------------------ questions

    def next_question(self, token: str) -> dict[str, Any]:
        """The question on screen; the first view starts its clock, a reload never resets it."""
        key, s = self._open(token, ("questions",))
        q = s.questions[s.current_question]
        now = utcnow()
        if q.served_at is None:
            q.served_at, q.deadline = now, now + timedelta(seconds=q.seconds)
            self._save(key, s)
        return {**q.public(now), "section": q.section, "total": len(s.questions),
                "assistant": q.section == "ai", "phase": s.phase}

    def answer(self, token: str, index: int, value: Any) -> dict[str, Any]:
        key, s = self._open(token, ("questions",))
        if index != s.current_question:
            raise PilotError("this question is closed")
        q = s.questions[index]
        now = utcnow()
        if q.served_at is None or q.deadline is None:
            raise PilotError("question not served yet")
        q.answered_at, q.answer = now, value
        q.late = now > q.deadline + timedelta(seconds=GRACE_SECONDS)
        q.score = 0.0 if q.late else score_answer(q, value)
        s.current_question += 1
        if s.current_question >= len(s.questions):
            self._after_questions(s, now)
        self._save(key, s)
        return {"accepted": not q.late, "late": q.late, "next": s.current_question, "total": len(s.questions),
                "phase": s.phase}

    def timeout(self, token: str, index: int) -> dict[str, Any]:
        key, s = self.get(token)
        self._tick(s)
        self._save(key, s)
        return {"next": s.current_question, "total": len(s.questions), "phase": s.phase}

    def arm_fault(self, session_id: str, fault_id: str) -> AISandboxSession:
        """A recruiter arms one more flaw from the scenario's pool; it appears at the next reply it fits."""
        key, s = self.by_id(session_id)
        scenario = SCENARIOS.get(s.scenario_id)
        if scenario is None:
            raise ValueError("this test has no practical mission")
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
        key, s = self._open(token, ("questions", "build", "ownership"))
        message = message.strip()[:MAX_PROMPT_CHARS]
        if not message:
            raise ValueError("empty instruction")
        if s.phase == "questions":
            return self._question_chat(key, s, message)
        scenario = SCENARIOS.get(s.scenario_id)
        prompt = s.add_turn("prompt", text=message, screened=screen(message))
        if s.phase == "ownership":
            reply_text, changed = self._ownership_reply(s, message)
            before = dict(s.ownership_files)
            s.ownership_files.update(changed)
            s.add_turn("assistant", text=reply_text, changes=_diff(before, s.ownership_files))
            self._save(key, s)
            return {"prompt": prompt.public(), "reply": s.turns[-1].public(), "files": s.ownership_files}
        assert scenario is not None  # the build phase only exists with a mission
        detect_callouts(s, scenario)  # a prompt can prevent a flaw before it is planted, or call one out
        reply = self._assistant_for(s).reply(s, scenario, message, self.injector.directives(s, scenario))
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

    def _question_chat(self, key: str, s: AISandboxSession, message: str) -> dict[str, Any]:
        q = s.questions[s.current_question]
        if q.section != "ai":
            raise PilotError("the built-in assistant is available in section 2 (calculator and internet are allowed)",
                             code="assistant_unavailable")
        if q.served_at is None:
            raise PilotError("open the question first")
        prompt = s.add_turn("prompt", text=message, screened=screen(message), question=q.index)
        q.consulted.append(prompt.index)
        text = reference_reply(q, message, s.locale)  # the traps are standardised: same for every candidate
        assistant = self._assistant_for(s)
        if not q.trapped and not q.personal and not isinstance(assistant, ScriptedAssistant):
            text = getattr(assistant, "answer_question", lambda *a: "")(s, q, message) or text
        turn = s.add_turn("assistant", text=text, question=q.index)
        self._save(key, s)
        return {"prompt": prompt.public(), "reply": turn.public(), "files": {}}

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
        scenario = SCENARIOS.get(s.scenario_id)
        if s.phase == "build" and scenario is not None:
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
        scenario = SCENARIOS.get(s.scenario_id)
        if scenario is None:
            raise PilotError("this test has no practical mission")
        checks, passed, run = run_ci(scenario, s.files, s.locale, self.runner)
        turn = s.add_turn("ci", text="CI " + ("passed" if passed else "failed"), checks=checks, passed=passed,
                          test_run=run.model_dump(include={"passed", "failed", "errors", "skipped", "timed_out",
                                                           "tests", "output", "duration", "error"})
                          if run else None)
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
        assistant = self._assistant_for(s)
        if not isinstance(assistant, ScriptedAssistant) and s.scenario_id:
            reply = assistant.reply(s, SCENARIOS[s.scenario_id], message, [])
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
        started = s.build_started_at is not None or any(q.served_at for q in s.questions) or (
            s.ownership is not None and s.ownership.started_at is not None)
        if s.phase == "expired" and not started:
            raise PilotError("this link expired before the test was started")
        if s.phase not in ("closed", "expired"):
            s.add_turn("phase", text="closed by the candidate")
        s.phase = "closed"
        s.closed_at = utcnow()
        judge = self._judge_for(s)
        later = judge is not None and s.mode == "candidate" and self.judge_in_background and bool(s.prompts())
        report = self.evaluate(s, use_judge=not later)
        if later:
            report.judge = f"pending: {judge.name}/{judge.model}"
        s.report = report.model_dump(mode="json")
        self._save(key, s)
        if later:
            threading.Thread(target=self._judge_later, args=(token,), daemon=True).start()
        return s, s.report, True

    def _hidden_audits(self, s: AISandboxSession, scenario: Scenario) -> dict[str, bool | None]:
        """Behavioural tests of the planted flaws, run once at close in the isolated runner."""
        wanted = {f.id for f in s.faults} & set(scenario.hidden_tests)
        if self.runner is None or not wanted:
            return {}
        files = {f"{HIDDEN_DIR}/test_{fid}.py": scenario.hidden_tests[fid] for fid in wanted}
        run = self.runner.run({**s.files, **files}, [HIDDEN_DIR], timeout=40)
        return hidden_verdicts(run, {fid: f"{HIDDEN_DIR}/test_{fid}.py" for fid in wanted})

    def _judge_later(self, token: str) -> None:
        """Re-evaluate with the judge after the candidate has left (models can take a minute, or fail)."""
        try:
            key, s = self.get(token)
            report = self.evaluate(s, use_judge=True)
            s.report = report.model_dump(mode="json")
            self._save(key, s)
            if self.on_judged:
                self.on_judged(s, s.report)
        except Exception:  # the factual report is already saved; never crash a worker thread
            log.exception("background judge failed")

    def evaluate(self, s: AISandboxSession, use_judge: bool = True) -> PilotEvaluationReport:
        scenario = SCENARIOS.get(s.scenario_id)
        for q in s.questions:  # questions never reached count as unanswered
            if q.score is None:
                q.score = 0.0
        velocity = None
        faults: list[Any] = []
        m3: MetricScore | None = None
        if scenario is not None:
            detect_callouts(s, scenario)
        judge_data: dict[str, Any] | None = None
        errors: list[str] = []
        judge_name = "none"
        judge = self._judge_for(s) if use_judge else None
        if judge is not None and s.prompts():
            judge_name = f"{judge.name}/{judge.model}"
            try:
                judge_data = run_judge(judge, s, scenario)
            except LLMError as exc:
                errors.append(str(exc)[:200])
        callouts = valid_callouts(s, judge_data)
        knowledge, ai_pct, own_work_pct = applied_knowledge(s)
        q_scores, q_evidence = trap_scores(s)
        m1 = intent_precision(s)
        behaviour = self._hidden_audits(s, scenario) if scenario is not None else {}
        m2, faults = critical_thinking(s, scenario, s.files, callouts, q_scores, q_evidence, behaviour)
        if scenario is not None:
            checks, green, _ = run_ci(scenario, s.files, s.locale, self.runner)
            passing = sum(c.passed for c in checks) / max(1, len(checks))
            m3, velocity = orchestration_velocity(s, scenario, green, passing)
        own_prompts = (
            [(t.index, (t.at - s.ownership.started_at).total_seconds(), t.text) for t in s.prompts("ownership")]
            if s.ownership and s.ownership.started_at
            else []
        )
        original = {s.ownership.path: s.ownership.original_source} if s.ownership else {}
        facts, own_score, own_evidence, own_breakdown = analyse(s.ownership, own_prompts, s.ownership_files, original)
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
            steer = {t.index for t in s.turns if t.kind in ("prompt", "edit") and t.phase in ("questions", "build")}
            own_turns = {t.index for t in s.turns if t.kind in ("prompt", "edit") and t.phase == "ownership"}
            apply_judge(m1, judge_data.get("intent_precision"), steer, may_raise=not manip)
            if m2.breakdown:
                apply_judge(m2, judge_data.get("critical_thinking"), steer, may_raise=not manip)
            if own_metric:
                apply_judge(own_metric, judge_data.get("ownership"), own_turns, may_raise=not manip)
        metrics: list[MetricScore] = []
        if knowledge:
            metrics.append(knowledge)
        # Steering metrics count when the assistant was part of the test (section 2 or a mission).
        if scenario is not None or any(q.section == "ai" for q in s.questions):
            metrics.append(m1)
            if scenario is not None or m2.breakdown:
                metrics.append(m2)
        if m3:
            metrics.append(m3)
        if own_metric:
            metrics.append(own_metric)
        # Authenticity: the own-code task and the questions on one's own work, when either exists.
        parts = [p for p in (own_metric.final_pct if own_metric else None, own_work_pct) if p is not None]
        authenticity = round(sum(parts) / len(parts), 1) if parts else None
        started = s.build_started_at or next((q.served_at for q in s.questions if q.served_at), None) or s.created_at
        return PilotEvaluationReport(
            session_id=s.id,
            scenario_id=scenario.id if scenario else "",
            scenario_title=scenario.title[s.locale] if scenario else "",
            locale=s.locale,
            level=s.level,
            job_title=s.job_title,
            assistant="reference assistant (scripted)" if s.assistant_kind == "scripted" else s.assistant_kind,
            judge=judge_name,
            judge_errors=errors,
            metrics=metrics,
            pilot_index_pct=pilot_index(metrics),
            authenticity_pct=authenticity,
            faults=faults,
            velocity=velocity,
            ownership=facts,
            questions=outcomes(s),
            ai_usage=ai_usage(s, s.turns),
            applied_knowledge_pct=knowledge.final_pct if knowledge else None,
            ai_section_pct=ai_pct,
            own_work_pct=own_work_pct,
            prompts=len(s.prompts()),
            duration_minutes=round(((s.closed_at or utcnow()) - started).total_seconds() / 60, 1),
            weights=WEIGHTS,
            notice=NOTICE[s.locale],
            limits=LIMITS,
        )

"""Verification tests: server-paced, timed, personalised, with an integrity journal.

What the design guarantees, and what it cannot:

* **Answers never reach the browser.** The correct option, the numeric result and the option mapping stay
  on the server; the client only receives the stem and shuffled options.
* **Time is enforced server-side.** A question is served once with a deadline; an answer arriving after it
  (plus a small network grace) is recorded as late and scores zero. There is no going back.
* **Every candidate gets a different test.** Questions are drawn per session, numbers are re-drawn, options
  are shuffled: a leaked screenshot or answer key does not transfer to anyone else.
* **Integrity events** (paste or copy attempts, leaving the window, print-screen key, exiting full screen,
  answers faster than reading time) are journalled and summarised for the recruiter. They are signals,
  never an automated rejection (AI Act Art. 14, GDPR Art. 22).
* **What no web page can do**: stop a phone photographing the screen, or a second device. Short time
  limits, per-candidate variants and questions about the candidate's own work make that slow and of
  little use; Safe Exam Browser mode locks the desktop; the live interview is the final check.
"""

from __future__ import annotations

import hashlib
import math
import random
import secrets
import threading
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..models import IMPORTANCE_MULTIPLIER, JobProfile, utcnow
from ..store import Store
from ..translator.catalog import CATALOG
from .bank import QuestionTemplate, draw_params, load_bank, render, safe_eval

GRACE_SECONDS = 3
EVENT_TYPES = {"blur", "focus", "visibility_hidden", "visibility_visible", "paste_attempt", "copy_attempt",
               "cut_attempt", "contextmenu", "printscreen", "fullscreen_exit", "fullscreen_enter", "drop_attempt",
               "devtools", "resize", "multiple_screens", "seb_missing"}


class ServedQuestion(BaseModel):
    index: int
    template_id: str
    skill_id: str  # "authorship" for personal questions
    level: int  # 0 for personal questions
    type: Literal["single", "multi", "numeric", "order"]
    stem: str
    options: list[str] = Field(default_factory=list)
    unit: str = ""
    seconds: int
    personal: bool = False
    # Server-only fields
    expected: list[int] = Field(default_factory=list)
    expected_value: float | None = None
    tolerance: float = 0.01
    served_at: datetime | None = None
    deadline: datetime | None = None
    answered_at: datetime | None = None
    answer: Any = None
    score: float | None = None
    late: bool = False
    too_fast: bool = False

    def public(self, now: datetime) -> dict[str, Any]:
        remaining = max(0, int((self.deadline - now).total_seconds())) if self.deadline else self.seconds
        return {"index": self.index, "type": self.type, "stem": self.stem, "options": self.options,
                "unit": self.unit, "seconds": self.seconds, "remaining": remaining, "personal": self.personal,
                "skill": CATALOG[self.skill_id].l("fr") if self.skill_id in CATALOG else ""}


class IntegrityEvent(BaseModel):
    type: str
    at: datetime
    question: int | None = None
    detail: str = Field("", max_length=200)


class AssessmentSession(BaseModel):
    id: str
    mode: Literal["sandbox", "candidate"]
    locale: Literal["fr", "en"]
    level: Literal[1, 2, 3]
    job_title: str
    job_id: str = ""
    candidate_ref: str = ""
    skills: list[str]
    untestable_skills: list[str] = Field(default_factory=list)
    questions: list[ServedQuestion]
    current: int = 0
    status: Literal["ready", "running", "finished", "expired"] = "ready"
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    events: list[IntegrityEvent] = Field(default_factory=list)
    watermark: str
    seb_config_keys: list[str] = Field(default_factory=list)  # Safe Exam Browser config keys (server-side)
    results: dict[str, Any] | None = None

    @property
    def seb_required(self) -> bool:
        return bool(self.seb_config_keys)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _reading_seconds(text: str) -> float:
    return len(text.split()) / 4.0  # ~240 words per minute, generous for technical text


def _instantiate(t: QuestionTemplate, index: int, locale: str, rng: random.Random) -> ServedQuestion:
    values = draw_params(t, rng)
    stem = render(t.stem.get(locale), values)
    q = ServedQuestion(index=index, template_id=t.id, skill_id=t.skill_id, level=t.level, type=t.type,
                       stem=stem, unit=t.unit, seconds=t.seconds, tolerance=t.tolerance)
    if t.type == "numeric":
        q.expected_value = safe_eval(t.answer, values)
        return q
    order = list(range(len(t.options)))
    rng.shuffle(order)
    q.options = [render(t.options[i].get(locale), values) for i in order]
    if t.type == "order":
        # expected = displayed positions in the right sequence
        q.expected = [order.index(i) for i in t.correct]
    else:
        q.expected = sorted(order.index(i) for i in t.correct)
    return q


def _personal_to_served(raw: dict[str, Any], index: int, locale: str) -> ServedQuestion:
    return ServedQuestion(index=index, template_id=raw["id"], skill_id="authorship", level=0, type=raw["type"],
                          stem=raw["stem"][locale], options=[o[locale] for o in raw["options"]],
                          seconds=raw["seconds"], personal=True, expected=sorted(raw["correct"]))


def select_questions(job: JobProfile, level: int, n: int, rng: random.Random) -> tuple[list[QuestionTemplate],
                                                                                         list[str], list[str]]:
    """Spread n questions over the job's skills by importance, at the chosen level and one below."""
    bank = load_bank()
    by_skill: dict[str, list[QuestionTemplate]] = {}
    for q in bank:
        by_skill.setdefault(q.skill_id, []).append(q)
    weights = {c.skill_id: IMPORTANCE_MULTIPLIER[c.importance] * c.weight for c in job.criteria}
    testable = [s for s in sorted(weights, key=lambda s: -weights[s]) if by_skill.get(s)]
    untestable = [s for s in weights if s not in testable]
    if not testable:
        return [], [], untestable
    total = sum(weights[s] for s in testable)
    quota = {s: max(1, round(n * weights[s] / total)) for s in testable}
    chosen: list[QuestionTemplate] = []
    for skill in testable:
        pool = by_skill[skill]
        at_level = [q for q in pool if q.level == level]
        below = [q for q in pool if q.level == level - 1]
        above = [q for q in pool if q.level == level + 1]
        k = quota[skill]
        picks = rng.sample(at_level, min(len(at_level), math.ceil(k * 2 / 3)))
        rest = [q for q in below + above + at_level if q not in picks]
        picks += rng.sample(rest, min(len(rest), k - len(picks)))
        chosen += picks
    # Rounded quotas can leave the test short: top up from the most important skills first.
    for skill in testable:
        if len(chosen) >= n:
            break
        spare = [q for q in by_skill[skill] if q not in chosen and abs(q.level - level) <= 1]
        chosen += rng.sample(spare, min(len(spare), n - len(chosen)))
    rng.shuffle(chosen)
    return chosen[:n], testable, untestable


class AssessmentEngine:
    """Sessions live in memory (sandbox: nothing persisted) or in the store (candidate links)."""

    def __init__(self, store: Store | None = None) -> None:
        self.store = store
        self._memory: dict[str, AssessmentSession] = {}
        self._lock = threading.RLock()

    # -------------------------------------------------------------------------------------------- lifecycle

    def create(self, job: JobProfile, level: int, *, locale: str, mode: str, n: int = 10,
               personal: list[dict[str, Any]] | None = None, candidate_ref: str = "", job_id: str = "",
               seb_config_keys: list[str] | None = None, valid_hours: int = 24) -> tuple[str, AssessmentSession]:
        token = secrets.token_urlsafe(24)
        rng = random.SystemRandom()  # unpredictable selection: a candidate cannot anticipate their test
        templates, testable, untestable = select_questions(job, level, n, rng)
        if not templates and not personal:
            raise ValueError("no verification question exists yet for the skills of this job")
        questions = [_instantiate(t, i, locale, rng) for i, t in enumerate(templates)]
        for raw in personal or []:
            questions.insert(rng.randint(0, len(questions)), _personal_to_served(raw, 0, locale))
        for i, q in enumerate(questions):
            q.index = i
        session = AssessmentSession(
            id=_hash(token)[:16], mode=mode, locale=locale, level=level, job_title=job.title,
            job_id=job_id, candidate_ref=candidate_ref, skills=testable, untestable_skills=untestable,
            questions=questions, expires_at=utcnow() + timedelta(hours=valid_hours),
            watermark=f"{candidate_ref or 'TEST-' + _hash(token)[:6].upper()} · {utcnow():%d/%m %H:%M}",
            seb_config_keys=seb_config_keys or [],
        )
        self._save(_hash(token), session)
        return token, session

    def _save(self, key: str, session: AssessmentSession) -> None:
        with self._lock:
            if session.mode == "candidate" and self.store is not None:
                self.store.put("assessments", key, session, parent=session.candidate_ref)
            else:
                self._memory[key] = session
                now = utcnow()
                for k in [k for k, s in self._memory.items() if s.expires_at < now]:
                    del self._memory[k]

    def get(self, token: str) -> tuple[str, AssessmentSession]:
        key = _hash(token)
        with self._lock:
            session = self._memory.get(key)
            if session is None and self.store is not None:
                session = self.store.get("assessments", key, AssessmentSession)
        if session is None:
            raise KeyError("unknown or expired test link")
        if session.status != "finished" and session.expires_at < utcnow():
            session.status = "expired"
        return key, session

    def list_for(self, candidate_ref: str) -> list[AssessmentSession]:
        return self.store.list("assessments", AssessmentSession, parent=candidate_ref) if self.store else []

    # -------------------------------------------------------------------------------------------- flow

    def state(self, token: str) -> dict[str, Any]:
        _, s = self.get(token)
        return {"status": s.status, "mode": s.mode, "locale": s.locale, "level": s.level, "job_title": s.job_title,
                "total": len(s.questions), "current": s.current, "watermark": s.watermark,
                "seb_required": s.seb_required, "expires_at": s.expires_at.isoformat(),
                "skills": [CATALOG[k].l(s.locale) for k in s.skills],
                "personal_questions": sum(q.personal for q in s.questions),
                "total_seconds": sum(q.seconds for q in s.questions)}

    def next_question(self, token: str) -> dict[str, Any]:
        key, s = self.get(token)
        if s.status in ("finished", "expired"):
            raise PermissionError(f"test {s.status}")
        if s.current >= len(s.questions):
            raise PermissionError("no more questions: finish the test")
        now = utcnow()
        q = s.questions[s.current]
        if q.served_at is None:  # first view starts the clock; reloading never resets it
            q.served_at = now
            q.deadline = now + timedelta(seconds=q.seconds)
            s.status = "running"
            s.started_at = s.started_at or now
            self._save(key, s)
        return {**q.public(now), "total": len(s.questions)}

    def answer(self, token: str, index: int, value: Any) -> dict[str, Any]:
        key, s = self.get(token)
        if s.status != "running" or index != s.current:
            raise PermissionError("this question is closed")
        q = s.questions[index]
        now = utcnow()
        if q.deadline is None or q.served_at is None:
            raise PermissionError("question not served yet")
        q.answered_at, q.answer = now, value
        q.late = now > q.deadline + timedelta(seconds=GRACE_SECONDS)
        q.too_fast = (now - q.served_at).total_seconds() < 0.25 * _reading_seconds(q.stem) and not q.personal
        q.score = 0.0 if q.late else self._score(q, value)
        s.current += 1
        self._save(key, s)
        return {"accepted": not q.late, "late": q.late, "next": s.current, "total": len(s.questions)}

    def timeout(self, token: str, index: int) -> dict[str, Any]:
        """The client reports that the timer ran out: the question is closed with no answer."""
        key, s = self.get(token)
        if s.status == "running" and index == s.current:
            q = s.questions[index]
            if q.deadline and utcnow() >= q.deadline - timedelta(seconds=GRACE_SECONDS):
                q.score, q.late, q.answered_at = 0.0, True, utcnow()
                s.current += 1
                self._save(key, s)
        return {"next": s.current, "total": len(s.questions)}

    def events(self, token: str, events: list[dict[str, Any]]) -> int:
        key, s = self.get(token)
        accepted = 0
        for e in events[:50]:
            if e.get("type") in EVENT_TYPES and len(s.events) < 500:
                s.events.append(IntegrityEvent(type=e["type"], at=utcnow(), question=s.current,
                                               detail=str(e.get("detail", ""))[:200]))
                accepted += 1
        self._save(key, s)
        return accepted

    def finish(self, token: str) -> dict[str, Any]:
        key, s = self.get(token)
        if s.status == "finished" and s.results:
            return s.results
        for q in s.questions[s.current:]:
            q.score = 0.0
        s.current = len(s.questions)
        s.status, s.finished_at = "finished", utcnow()
        s.results = self._results(s)
        self._save(key, s)
        return s.results

    # -------------------------------------------------------------------------------------------- scoring

    @staticmethod
    def _score(q: ServedQuestion, value: Any) -> float:
        try:
            if q.type == "numeric":
                given = float(str(value).replace(",", ".").replace(" ", "").replace(" ", ""))
                assert q.expected_value is not None
                ref = q.expected_value
                return 1.0 if abs(given - ref) <= max(abs(ref) * q.tolerance, 1e-9) else 0.0
            chosen = [int(v) for v in (value if isinstance(value, list) else [value])]
            if q.type == "single":
                return 1.0 if chosen == q.expected else 0.0
            if q.type == "multi":
                right, picked = set(q.expected), set(chosen)
                if picked == right:
                    return 1.0
                wrong = len(picked - right)
                return max(0.0, (len(picked & right) - wrong) / len(right)) * 0.5
            # order: share of adjacent pairs in the right relative order
            pairs = list(zip(q.expected, q.expected[1:], strict=False))
            pos = {v: i for i, v in enumerate(chosen)}
            if len(chosen) != len(q.expected):
                return 0.0
            ok = sum(1 for a, b in pairs if pos.get(a, 0) < pos.get(b, -1))
            return ok / len(pairs) if pairs else 0.0
        except (TypeError, ValueError, AssertionError):
            return 0.0

    def _results(self, s: AssessmentSession) -> dict[str, Any]:
        per_skill: dict[str, dict[str, Any]] = {}
        for q in s.questions:
            if q.personal:
                continue
            bucket = per_skill.setdefault(q.skill_id, {"points": 0.0, "max": 0.0, "answered": 0, "questions": 0})
            weight = 1 + 0.5 * (q.level - 1)  # harder questions count more
            bucket["points"] += weight * (q.score or 0)
            bucket["max"] += weight
            bucket["questions"] += 1
            bucket["answered"] += int(q.answered_at is not None and not q.late)
        skills = []
        for skill_id, b in per_skill.items():
            pct = round(100 * b["points"] / b["max"], 1) if b["max"] else 0.0
            verified = s.level if pct >= 70 else max(0, s.level - 1) if pct >= 50 else 0
            skills.append({"skill_id": skill_id, "label": CATALOG[skill_id].l(s.locale), "score_pct": pct,
                           "questions": b["questions"], "answered_in_time": b["answered"],
                           "verified_level": verified})
        personal = [q for q in s.questions if q.personal]
        authorship = round(100 * sum(q.score or 0 for q in personal) / len(personal), 1) if personal else None
        scored = [q for q in s.questions if not q.personal]
        overall = round(100 * sum((1 + 0.5 * (q.level - 1)) * (q.score or 0) for q in scored)
                        / sum(1 + 0.5 * (q.level - 1) for q in scored), 1) if scored else None
        own_work = "Connaissance de son propre travail" if s.locale == "fr" else "Knowledge of own work"
        duration = int((s.finished_at - s.started_at).total_seconds()) if s.started_at and s.finished_at else 0
        return {"overall_pct": overall, "level": s.level, "skills": sorted(skills, key=lambda x: -x["score_pct"]),
                "authorship_pct": authorship,
                "untestable_skills": [CATALOG[k].l(s.locale) for k in s.untestable_skills],
                "integrity": integrity_summary(s), "duration_seconds": duration,
                "questions": [{"index": q.index,
                               "skill": CATALOG[q.skill_id].l(s.locale) if q.skill_id in CATALOG else own_work,
                               "personal": q.personal, "score": q.score, "late": q.late, "too_fast": q.too_fast,
                               "seconds": q.seconds, "seconds_used": int((q.answered_at - q.served_at).total_seconds())
                               if q.answered_at and q.served_at else None} for q in s.questions]}


def integrity_summary(s: AssessmentSession) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for e in s.events:
        counts[e.type] = counts.get(e.type, 0) + 1
    late = sum(q.late for q in s.questions)
    too_fast = sum(q.too_fast for q in s.questions)
    hidden = counts.get("blur", 0) + counts.get("visibility_hidden", 0)
    strong = counts.get("paste_attempt", 0) + counts.get("copy_attempt", 0) + counts.get("printscreen", 0) \
        + counts.get("drop_attempt", 0) + counts.get("devtools", 0) + counts.get("seb_missing", 0)
    if strong or hidden >= 3 or counts.get("fullscreen_exit", 0) >= 2:
        risk = "high"
    elif hidden or late >= 2 or too_fast >= 3 or counts.get("fullscreen_exit", 0):
        risk = "medium"
    else:
        risk = "low"
    fr = s.locale == "fr"
    notes = []
    if strong:
        notes.append("Tentatives de copier, coller ou capturer l'écran détectées." if fr
                     else "Copy, paste or screen-capture attempts detected.")
    if hidden:
        notes.append(f"La fenêtre du test a perdu le focus {hidden} fois." if fr
                     else f"The test window lost focus {hidden} time(s).")
    if late:
        notes.append(f"{late} question(s) sans réponse dans le temps imparti." if fr
                     else f"{late} question(s) not answered in time.")
    if too_fast:
        notes.append(f"{too_fast} réponse(s) plus rapides que le temps de lecture." if fr
                     else f"{too_fast} answer(s) faster than reading time.")
    notes.append("Signal à examiner par une personne, jamais un motif de rejet automatique." if fr
                 else "A signal for a person to review, never a ground for automatic rejection.")
    return {"risk": risk, "events": counts, "late_answers": late, "too_fast_answers": too_fast, "notes": notes}


def seb_valid(config_keys: list[str], url: str, config_key_hash: str | None) -> bool:
    """Safe Exam Browser: hash = SHA-256(absolute page/request URL + Config Key), hex (SEB 2.2+/3.x)."""
    if not config_keys:
        return True
    if not config_key_hash:
        return False
    url = url.split("#", 1)[0]
    return any(secrets.compare_digest(hashlib.sha256((url + key).encode()).hexdigest(), config_key_hash.lower())
               for key in config_keys)

"""HTTP routes of the verification tests.

Public routes are addressed by an unguessable token (the test link). The sandbox creates throw-away
sessions kept in memory; recruiters create candidate tests stored with the application and journalled.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from ..config import Settings
from ..dashboard.presets import preset_job
from ..models import JobProfile, Locale
from ..translator.catalog import CATALOG
from .bank import coverage
from .engine import AssessmentEngine, seb_valid


class StartRequest(BaseModel):
    preset_id: str = ""
    job: dict[str, Any] | None = None
    level: int = Field(2, ge=1, le=3)
    locale: str = "fr"
    questions: int = Field(10, ge=4, le=20)
    seed: str = Field("", max_length=64, description="Returned by /api/try/match: adds questions on your own work")


class AnswerRequest(BaseModel):
    index: int
    value: Any


class TimeoutRequest(BaseModel):
    index: int


class EventsRequest(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class SeedStore:
    """Personal questions computed by a sandbox match, kept one hour in memory for an optional test."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._lock = threading.Lock()

    def put(self, questions: list[dict[str, Any]]) -> str:
        seed = secrets.token_urlsafe(18)
        with self._lock:
            now = time.monotonic()
            self._items = {k: v for k, v in self._items.items() if now - v[0] < 3600}
            self._items[seed] = (now, questions)
        return seed

    def take(self, seed: str) -> list[dict[str, Any]]:
        with self._lock:
            item = self._items.pop(seed, None)
        return item[1] if item and time.monotonic() - item[0] < 3600 else []


def build_router(settings: Settings, tests: AssessmentEngine, seeds: SeedStore, limiter: Any,
                 on_finish: Any = None) -> APIRouter:
    router = APIRouter(prefix="/api/assess", tags=["verification tests"])

    def seb_check(request: Request, token: str) -> None:
        try:
            _, session = tests.get(token)
        except KeyError as exc:
            raise HTTPException(404, "unknown or expired test link") from exc
        if not session.seb_required:
            return
        base = settings.public_base_url.rstrip("/")
        native = request.headers.get("x-safeexambrowser-configkeyhash")
        request_url = (base + request.url.path + (f"?{request.url.query}" if request.url.query else "")) \
            if base else str(request.url)
        if native and seb_valid(session.seb_config_keys, request_url, native):
            return
        # SEB 3.x JavaScript API: the page sends SafeExamBrowser.security.configKey (hash of page URL + key).
        page_url = request.headers.get("x-seb-page-url", "")
        page_hash = request.headers.get("x-seb-config-key-hash")
        if page_url.startswith(base or "http") and token in page_url and seb_valid(session.seb_config_keys,
                                                                                    page_url, page_hash):
            return
        raise HTTPException(403, "this test must be taken in Safe Exam Browser with the configuration provided")

    @router.get("/catalog")
    def catalog(locale: str = "fr") -> dict[str, Any]:
        loc: Locale = "en" if locale == "en" else "fr"
        cov = coverage()
        return {"levels": [{"value": 1, "label": "Junior"},
                           {"value": 2, "label": "Confirmed" if loc == "en" else "Confirmé"},
                           {"value": 3, "label": "Senior"}],
                "skills": [{"id": k, "label": CATALOG[k].l(loc), "questions": v} for k, v in sorted(cov.items())],
                "total_questions": sum(sum(v.values()) for v in cov.values())}

    @router.post("/start")
    def start(body: StartRequest, request: Request) -> dict[str, Any]:
        if not settings.sandbox_enabled:
            raise HTTPException(404, "the public sandbox is disabled")
        limiter(request)
        loc = "en" if body.locale == "en" else "fr"
        try:
            if body.job:
                job = JobProfile.model_validate(body.job)
            elif body.preset_id:
                job = preset_job(body.preset_id, loc)
            else:
                raise HTTPException(422, "choose a reference role or analyse an offer first")
        except (ValidationError, KeyError) as exc:
            raise HTTPException(422, f"invalid job profile: {exc}") from exc
        personal = seeds.take(body.seed) if body.seed else []
        try:
            token, _ = tests.create(job, body.level, locale=loc, mode="sandbox", n=body.questions,
                                          personal=personal, valid_hours=2)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"token": token, "path": f"/test/{token}", **tests.state(token)}

    @router.get("/{token}")
    def state(token: str, request: Request) -> dict[str, Any]:
        seb_check(request, token)
        return tests.state(token)

    @router.post("/{token}/next")
    def next_question(token: str, request: Request) -> dict[str, Any]:
        seb_check(request, token)
        try:
            return tests.next_question(token)
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/{token}/answer")
    def answer(token: str, body: AnswerRequest, request: Request) -> dict[str, Any]:
        seb_check(request, token)
        if len(json.dumps(body.value, default=str)) > 2000:
            raise HTTPException(413, "answer too long")
        try:
            return tests.answer(token, body.index, body.value)
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/{token}/timeout")
    def timeout(token: str, body: TimeoutRequest, request: Request) -> dict[str, Any]:
        seb_check(request, token)
        return tests.timeout(token, body.index)

    @router.post("/{token}/events")
    def events(token: str, body: EventsRequest, request: Request) -> dict[str, int]:
        seb_check(request, token)
        return {"accepted": tests.events(token, body.events)}

    @router.post("/{token}/finish")
    def finish(token: str, request: Request) -> dict[str, Any]:
        seb_check(request, token)
        results = tests.finish(token)
        _, session = tests.get(token)
        if session.mode == "candidate":
            if on_finish:
                on_finish(session)
            # The candidate sees completion; scores are for the recruiter, who decides (and may share them).
            return {"finished": True, "mode": "candidate"}
        return {"finished": True, "mode": "sandbox", "results": results}

    return router

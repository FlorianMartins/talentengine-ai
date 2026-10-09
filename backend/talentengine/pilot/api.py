"""HTTP routes of the AI-pilot test.

Public routes are addressed by an unguessable token (the test link), like the verification tests.
``POST /api/pilot/start`` opens a throw-away sandbox session (memory only); recruiters create candidate
sessions from the candidate's page (routes in ``api/app.py``), stored with the application and journalled.

Flow: ``GET /{token}`` → ``POST /{token}/begin`` → ``POST /{token}/chat`` · ``PUT /{token}/files`` ·
``POST /{token}/ci`` (any order, repeatedly) → optional ``POST /{token}/ownership/start`` then ``chat`` →
``POST /{token}/close`` (computes the report). Fault injection happens inside ``chat``: the candidate never
sees it, the report does.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from ..config import Settings
from ..dashboard.presets import preset_job
from ..models import IMPORTANCE_MULTIPLIER, JobProfile, Locale
from ..translator.catalog import CATALOG
from .engine import BUILD_MINUTES, FAULTS_PER_LEVEL, PilotEngine, PilotError
from .models import MAX_PROMPT_CHARS, AISandboxSession
from .ownership import choose_task
from .scenarios import SCENARIOS, Files, Scenario, choose_scenario

SourceFetcher = Callable[[list[str]], list[tuple[str, list[str], Files]]]


class PilotStart(BaseModel):
    preset_id: str = ""
    job: dict[str, Any] | None = None
    scenario_id: str = ""
    level: int = Field(2, ge=1, le=3)
    locale: str = "fr"
    github_urls: list[str] = Field(default_factory=list, max_length=3,
                                   description="Your profile or repositories: adds the task on your own code")


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_PROMPT_CHARS)


class EditBody(BaseModel):
    path: str = Field(..., min_length=1, max_length=200)
    content: str | None = Field(None, description="null deletes the file")
    create_only: bool = Field(False, description="refuse (409) when the file already exists")


def scenario_for(job: JobProfile, scenario_id: str = "") -> Scenario:
    if scenario_id:
        if scenario_id not in SCENARIOS:
            raise HTTPException(422, f"unknown scenario {scenario_id!r}")
        return SCENARIOS[scenario_id]
    weights = {c.skill_id: IMPORTANCE_MULTIPLIER[c.importance] * c.weight for c in job.criteria}
    scenario = choose_scenario(weights)
    if scenario is None:
        raise HTTPException(422, "no AI-pilot scenario fits this job yet: it targets software, data, security and "
                                 "infrastructure roles. Use the verification test instead.")
    return scenario


def catalogue(locale: str) -> list[dict[str, Any]]:
    loc: Locale = "en" if locale == "en" else "fr"
    return [{"id": s.id, "title": s.title[loc], "brief": s.brief[loc], "par": s.par,
             "skills": [CATALOG[k].l(loc) for k in s.skills if k in CATALOG],
             "faults": [{"id": f.id, "title": f.title[loc], "category": f.category, "cwe": f.cwe} for f in s.faults]}
            for s in SCENARIOS.values()]


def build_router(settings: Settings, pilot: PilotEngine, limiter: Callable[[Request], None],
                 fetch_sources: SourceFetcher | None = None,
                 on_close: Callable[[AISandboxSession, dict[str, Any]], None] | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/pilot", tags=["AI-pilot test"])

    def guard(fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except KeyError as exc:
            raise HTTPException(404, "unknown or expired AI-pilot link") from exc
        except PilotError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/scenarios")
    def scenarios(locale: str = "fr") -> dict[str, Any]:
        return {"scenarios": catalogue(locale), "build_minutes": BUILD_MINUTES, "faults_per_level": FAULTS_PER_LEVEL,
                "ownership_seconds": 300, "assistant": pilot.assistant.kind,
                "judge": "configured" if pilot.judge_provider is not None else "none"}

    @router.post("/start")
    def start(body: PilotStart, request: Request) -> dict[str, Any]:
        if not settings.sandbox_enabled:
            raise HTTPException(404, "the public sandbox is disabled")
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
        scenario = scenario_for(job, body.scenario_id)
        limiter(request)  # counted once the request is valid: a rejected job does not use the quota
        ownership = None
        warning = ""
        urls = [u for u in body.github_urls if u.strip()]
        if urls and fetch_sources is not None:
            try:
                repos = fetch_sources(urls)
            except Exception as exc:  # an unreadable profile must not block the main test
                repos = []
                warning = f"your repositories could not be read ({str(exc)[:120]}): no task on your own code"
            ownership = choose_task(repos, random.SystemRandom(), loc) if repos else None
            if repos and ownership is None:
                warning = "no function long and rich enough was found in your public code: no task on your own code"
        token, _ = pilot.create(scenario, body.level, locale=loc, mode="sandbox", job_title=job.title,
                                      ownership=ownership, valid_hours=3)
        return {"token": token, "path": f"/pilote/{token}", "warning": warning, **pilot.state(token)}

    @router.get("/{token}")
    def state(token: str) -> dict[str, Any]:
        return dict(guard(lambda: pilot.state(token)))

    @router.post("/{token}/begin")
    def begin(token: str) -> dict[str, Any]:
        return dict(guard(lambda: pilot.begin(token)))

    @router.post("/{token}/chat")
    def chat(token: str, body: ChatBody) -> dict[str, Any]:
        return dict(guard(lambda: pilot.chat(token, body.message)))

    @router.put("/{token}/files")
    def edit(token: str, body: EditBody) -> dict[str, Any]:
        return dict(guard(lambda: pilot.edit(token, body.path, body.content, body.create_only)))

    @router.post("/{token}/ci")
    def ci(token: str) -> dict[str, Any]:
        return dict(guard(lambda: pilot.run_ci(token)))

    @router.post("/{token}/ownership/start")
    def ownership_start(token: str) -> dict[str, Any]:
        return dict(guard(lambda: pilot.start_ownership(token)))

    @router.post("/{token}/close")
    def close(token: str) -> dict[str, Any]:
        session, report, fresh = guard(lambda: pilot.close(token))
        if session.mode == "candidate":
            if on_close and fresh:
                on_close(session, report)
            # The candidate sees completion; the evaluation is for the recruiter, who decides and may share it.
            return {"closed": True, "mode": "candidate"}
        return {"closed": True, "mode": "sandbox", "report": report}

    return router

"""HTTP API (FastAPI). Interactive documentation is served at /api/docs."""

from __future__ import annotations

import hmac
import json
import random
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from ..assessment.engine import AssessmentEngine, AssessmentSession
from ..assessment.personal import personal_questions
from ..auth import Principal, Role, UserStore
from ..byok import PRESETS, ByokStore, LLMSettingsInput, test_provider
from ..compliance import dpia_markdown
from ..config import ENGINE_VERSION, Settings, get_settings
from ..dashboard.presets import list_presets
from ..i18n import localise
from ..integrations.bridge import Bridge, ConnectionInput
from ..models import (
    MAX_CREDENTIAL_WEIGHT,
    ArtifactKind,
    Candidate,
    CandidateSummary,
    DashboardReport,
    Family,
    HumanDecision,
    JobProfile,
)
from ..pilot.runner import build_runner
from ..pipeline import (
    Engine,
    ImageInput,
    NotFound,
    PolicyError,
    RepositoryInput,
    Submission,
    TextDocument,
    extract_text,
)
from ..translator.catalog import CATALOG, SKILLS

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


class RevealRequest(BaseModel):
    reviewer: str = Field("", max_length=120, description="Ignored for named accounts: the account name is used")
    reason: str = Field(..., min_length=15, max_length=2000)


class NewUser(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    role: Role


class EvaluationResult(BaseModel):
    job_id: str
    evaluated: int
    escalated: list[str] = Field(description="Candidates sent to the escalation tier")
    escalation_skipped: dict[str, str] = Field(description="Candidate ref -> why escalation did not happen")
    spent_usd: float


class NewAssessment(BaseModel):
    level: int = Field(2, ge=1, le=3, description="1 junior, 2 confirmed, 3 senior")
    questions: int = Field(12, ge=4, le=25)
    personal: bool = Field(True, description="Add questions generated from the candidate's own work")
    seb_config_keys: list[str] = Field(default_factory=list, max_length=5,
                                       description="Safe Exam Browser Config Keys: if set, SEB is required")
    valid_hours: int = Field(72, ge=1, le=336)


class NewPilot(BaseModel):
    level: int = Field(2, ge=1, le=3, description="1 junior, 2 confirmed, 3 senior")
    scenario_id: str = Field("", description="Empty: the mission that best fits the job; \"none\": no mission")
    knowledge_questions: int = Field(6, ge=0, le=20, description="Section 1: questions, tools allowed")
    ai_questions: int = Field(4, ge=0, le=20, description="Section 2: questions with the built-in assistant")
    personal: bool = Field(True, description="Add questions generated from the candidate's own work")
    fault_ids: list[str] = Field(default_factory=list, max_length=4, description="Empty: drawn at random")
    build_minutes: int | None = Field(None, ge=10, le=90)
    ownership: bool = Field(True, description="Add the five-minute task on a function of the candidate's own code")
    valid_hours: int = Field(72, ge=1, le=336)


class ArmFault(BaseModel):
    fault_id: str = Field(..., min_length=2, max_length=60)


class IncidentReport(BaseModel):
    severity: Literal["serious", "widespread", "death"] = "serious"
    description: str = Field(..., min_length=20, max_length=4000)
    affected_candidates: list[str] = Field(default_factory=list, max_length=200)


class EraseRequest(BaseModel):
    actor: str = Field("", max_length=120, description="Ignored for named accounts: the account name is used")


def pilot_assistant(settings: Settings) -> Any:
    """The assistant candidates pilot: the reference (scripted) one, or a real model when configured."""
    from ..funnel.llm import build_provider
    from ..pilot.assistant import LLMAssistant, ScriptedAssistant

    if settings.pilot_assistant != "llm":
        return ScriptedAssistant()
    provider = build_provider(settings.model_copy(update={
        "llm_provider": settings.pilot_llm_provider, "llm_model": settings.pilot_llm_model,
        "llm_base_url": settings.pilot_llm_base_url, "llm_api_key": settings.pilot_llm_api_key}))
    return LLMAssistant(provider) if provider else ScriptedAssistant()


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or Engine(settings)
    users = UserStore(settings.data_dir / "users.json")
    stop = threading.Event()

    def retention_loop() -> None:
        # First sweep shortly after start, then every `retention_sweep_hours`.
        delay = 60.0
        while not stop.wait(delay):
            try:
                engine.purge_expired()
            except Exception:
                import logging

                logging.getLogger(__name__).exception("retention sweep failed")
            delay = settings.retention_sweep_hours * 3600.0

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.retention_sweep_hours > 0:
            threading.Thread(target=retention_loop, name="retention-sweep", daemon=True).start()
        yield
        stop.set()

    app = FastAPI(title="TalentEngine-AI", version=ENGINE_VERSION, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None, lifespan=lifespan,
                  description="Skills-first, privacy-first applicant evaluation. No automated rejection.")
    app.state.engine = engine
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["X-Total-Count", "X-Required-Permission"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    def auth_required() -> bool:
        return bool(settings.api_key) or users.any()

    def current(
        x_api_key: Annotated[str | None, Header()] = None,
        x_actor: Annotated[str | None, Header(max_length=120)] = None,
    ) -> Principal:
        if x_api_key:
            if (user := users.authenticate(x_api_key)) is not None:
                return user
            if settings.api_key and hmac.compare_digest(x_api_key, settings.api_key):
                return Principal(name=(x_actor or "admin").strip()[:120] or "admin", role="admin",
                                 authenticated=True, shared_key=True)
            raise HTTPException(401, "invalid API key")
        if auth_required():
            raise HTTPException(401, "missing X-API-Key")
        # Development mode (no key, no account): open, the name is whatever the client says.
        return Principal(name=(x_actor or "anonymous").strip()[:120] or "anonymous", role="admin",
                         authenticated=False)

    def need(permission: str) -> Callable[..., Principal]:
        def check(who: Principal = Depends(current)) -> Principal:
            if not who.can(permission):
                raise HTTPException(403, f"the {who.role} role cannot do this (needs: {permission})",
                                    headers={"X-Required-Permission": permission})
            return who
        return check

    # Built once: each is the dependency that authenticates the caller and checks one permission.
    CAN_READ, CAN_WRITE, CAN_DECIDE, CAN_PRIVACY, CAN_ADMIN = (
        Depends(need(p)) for p in ("read", "write", "decide", "privacy", "admin"))


    @app.exception_handler(NotFound)
    async def _not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(PolicyError)
    async def _policy(_: Request, exc: PolicyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    auth = [CAN_READ]

    from ..assessment.api import SeedStore
    from ..assessment.api import build_router as build_assess_router
    from ..sandbox.api import _client_ip, _RateLimiter, build_router

    limiter = _RateLimiter()
    seeds = SeedStore()
    tests = AssessmentEngine(engine.store, sandbox_key=engine.vault_key)
    app.state.tests = tests
    app.include_router(build_router(settings, seeds, limiter))  # public on purpose: no API key, nothing stored

    def test_limit(request: Request) -> None:
        limiter.check("test", _client_ip(request, settings.trust_proxy), settings.sandbox_matches_per_hour * 2)

    def test_finished(session: AssessmentSession) -> None:
        results = session.results or {}
        engine.ledger.append("assessment_completed", {
            "assessment": session.id, "level": session.level, "overall_pct": results.get("overall_pct"),
            "authorship_pct": results.get("authorship_pct"),
            "skills": [{k: s[k] for k in ("skill_id", "score_pct", "verified_level")}
                       for s in results.get("skills", [])],
            "integrity": {"risk": results.get("integrity", {}).get("risk"),
                          "events": results.get("integrity", {}).get("events")},
        }, actor="candidate", job_id=session.job_id, candidate_ref=session.candidate_ref)

    app.include_router(build_assess_router(settings, tests, seeds, test_limit, test_finished))

    # ------------------------------------------------------------------ AI-pilot test (Module 3)
    from ..funnel.llm import LLMError
    from ..pilot.api import build_questions_for, scenario_for
    from ..pilot.api import build_router as build_pilot_router
    from ..pilot.engine import PilotEngine, PilotError
    from ..pilot.ownership import choose_task
    from ..pilot.sources import fetch_sources

    byok = ByokStore(engine.store, engine.vault_key)  # each recruiter's own model key (bring your own key)
    pilot = PilotEngine(engine.store, sandbox_key=engine.vault_key, assistant=pilot_assistant(settings),
                        judge_provider=engine.provider if settings.pilot_judge and engine.provider else None,
                        byok=byok, runner=build_runner(settings.runner_url, settings.runner_token))
    app.state.pilot = pilot

    def pilot_judged(session: Any, report: dict[str, Any]) -> None:
        engine.ledger.append("pilot_judged", {
            "session": session.id, "judge": report.get("judge"), "errors": report.get("judge_errors", [])[:3],
            "metrics": {m["id"]: {"factual": m["factual_pct"], "final": m["final_pct"], "judge": m["judge_applied"]}
                        for m in report.get("metrics", [])},
        }, actor="judge", job_id=session.job_id, candidate_ref=session.candidate_ref)

    pilot.on_judged = pilot_judged

    # ------------------------------------------------------------------ bring your own model key
    @app.get("/api/me/llm")
    def my_llm(who: Principal = CAN_READ) -> dict[str, Any]:
        return {"settings": byok.public(who.name),
                "providers": [{"id": k, "label": v["label"], "help": v["help"]} for k, v in PRESETS.items()],
                "deployment_judge": bool(pilot.judge_provider)}

    @app.put("/api/me/llm")
    def set_my_llm(body: LLMSettingsInput, who: Principal = CAN_DECIDE) -> dict[str, Any]:
        try:
            saved = byok.set(who.name, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        engine.ledger.append("llm_key_set", {"provider": saved.provider, "model": saved.model,
                                             "use_for_judge": saved.use_for_judge,
                                             "use_for_assistant": saved.use_for_assistant}, actor=who.name)
        return {"settings": saved.model_dump()}

    @app.delete("/api/me/llm")
    def delete_my_llm(who: Principal = CAN_DECIDE) -> dict[str, bool]:
        removed = byok.delete(who.name)
        if removed:
            engine.ledger.append("llm_key_removed", {}, actor=who.name)
        return {"removed": removed}

    @app.post("/api/me/llm/test")
    def test_my_llm(who: Principal = CAN_DECIDE) -> dict[str, Any]:
        provider = byok.provider(who.name)
        if provider is None:
            raise HTTPException(404, "no model key saved for this account")
        try:
            return test_provider(provider)
        except LLMError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.get("/api/me/llm/free-models")
    def free_models(who: Principal = CAN_READ) -> list[dict[str, Any]]:
        try:
            return byok.free_models()
        except LLMError as exc:
            raise HTTPException(502, str(exc)) from exc

    def pilot_limit(request: Request) -> None:
        limiter.check("pilot", _client_ip(request, settings.trust_proxy), settings.pilot_starts_per_hour)

    def pilot_closed(session: Any, report: dict[str, Any]) -> None:
        engine.ledger.append("pilot_completed", {
            "session": session.id, "scenario": session.scenario_id, "level": session.level,
            "pilot_index_pct": report.get("pilot_index_pct"), "authenticity_pct": report.get("authenticity_pct"),
            "metrics": {m["id"]: {"factual": m["factual_pct"], "final": m["final_pct"], "judge": m["judge_applied"]}
                        for m in report.get("metrics", [])},
            "faults": [{k: f[k] for k in ("id", "detected", "fixed_at_close", "injection_method")}
                       for f in report.get("faults", [])],
            "assistant": report.get("assistant"), "judge": report.get("judge"),
        }, actor="candidate", job_id=session.job_id, candidate_ref=session.candidate_ref)

    app.include_router(build_pilot_router(settings, pilot, pilot_limit,
                                          lambda urls: fetch_sources(urls, settings.github_token), pilot_closed,
                                          seeds=seeds))

    # ------------------------------------------------------------------ meta

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        # Public on purpose: the UI needs to know a key is required before its first call fails.
        return {"status": "ok", "version": ENGINE_VERSION, "auth_required": auth_required(),
                "demo_enabled": settings.enable_demo}

    @app.get("/api/me")
    def me(who: Principal = Depends(current)) -> dict[str, Any]:
        return {**who.model_dump(), "permissions": who.permissions}

    @app.get("/api/runtime", dependencies=auth)
    def runtime() -> dict[str, Any]:
        return {
            "version": ENGINE_VERSION,
            "vision_detector": engine.detector.name,
            "llm_provider": engine.provider.name if engine.provider else "none",
            "llm_model": engine.provider.model if engine.provider else "",
            "max_credential_weight": MAX_CREDENTIAL_WEIGHT,
            "demo_enabled": settings.enable_demo,
            "auth_required": auth_required(),
            "named_accounts": users.any(),
            "upload_limits": {"max_file_mb": MAX_UPLOAD_BYTES // 1024 // 1024, "max_files_total": 60},
        }

    @app.get("/api/catalog/skills", dependencies=auth)
    def catalog(locale: str = "fr") -> list[dict[str, Any]]:
        return [{"id": s.id, "family": s.family, "label": s.label.get(locale, s.label["en"]),
                 "statement": s.statement.get(locale, s.statement["en"])} for s in SKILLS]

    @app.get("/api/catalog/families", dependencies=auth)
    def families() -> list[str]:
        return [f.value for f in Family]

    @app.get("/api/catalog/presets", dependencies=auth)
    def presets(locale: str = "fr", q: str = "") -> list[dict[str, Any]]:
        return list_presets("en" if locale == "en" else "fr", q[:100])

    # ------------------------------------------------------------------ jobs

    @app.get("/api/jobs", dependencies=auth)
    def jobs() -> list[dict[str, Any]]:
        out = []
        for job in engine.list_jobs():
            summaries = engine.summaries(job.id)
            scored = [s.compatibility_pct for s in summaries if s.compatibility_pct is not None]
            out.append({**job.model_dump(mode="json"), "candidates": len(summaries),
                        "evaluated": len(scored), "best_pct": max(scored) if scored else None,
                        "decisions": sum(1 for s in summaries if s.decision)})
        return out

    @app.post("/api/jobs", status_code=201)
    def create_job(job: JobProfile, who: Principal = CAN_WRITE) -> JobProfile:
        return engine.create_job(job, actor=who.name)

    @app.get("/api/jobs/{job_id}", dependencies=auth)
    def get_job(job_id: str) -> JobProfile:
        return engine.get_job(job_id)

    @app.put("/api/jobs/{job_id}")
    def update_job(job_id: str, job: JobProfile, who: Principal = CAN_WRITE) -> JobProfile:
        return engine.update_job(job_id, job, actor=who.name)

    @app.get("/api/jobs/{job_id}/dpia", dependencies=auth, response_class=PlainTextResponse)
    def dpia(job_id: str, locale: str = "fr") -> PlainTextResponse:
        text = dpia_markdown(engine.get_job(job_id), settings, runtime(), "en" if locale == "en" else "fr")
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8",
                                 headers={"Content-Disposition": f'attachment; filename="AIPD-{job_id}.md"'})

    @app.get("/api/jobs/{job_id}/candidates", dependencies=auth)
    def candidates(job_id: str) -> list[CandidateSummary]:
        engine.get_job(job_id)
        return engine.summaries(job_id)

    @app.post("/api/jobs/{job_id}/evaluate")
    def evaluate(job_id: str, who: Principal = CAN_WRITE) -> EvaluationResult:
        run = engine.evaluate(job_id, actor=who.name)
        locale = engine.get_job(job_id).locale
        return EvaluationResult(job_id=run.job_id, evaluated=run.evaluated, escalated=run.escalated,
                                escalation_skipped={k: localise(v, locale) for k, v in run.skipped.items()},
                                spent_usd=round(run.spent_usd, 6))

    @app.get("/api/jobs/{job_id}/usage", dependencies=auth)
    def usage(job_id: str) -> dict[str, Any]:
        return engine.usage(job_id)

    @app.post("/api/jobs/{job_id}/candidates/json", dependencies=[CAN_WRITE], status_code=201)
    def submit_json(job_id: str, submission: Submission) -> dict[str, Any]:
        cand = engine.ingest(job_id, submission)
        return {"candidate_ref": cand.ref, "artifacts": cand.artifact_ids}

    @app.post("/api/jobs/{job_id}/candidates", dependencies=[CAN_WRITE], status_code=201)
    async def submit_multipart(
        job_id: str,
        consent: Annotated[bool, Form()],
        identity_name: Annotated[str, Form(min_length=2, max_length=200)],
        identity_email: Annotated[str, Form()] = "",
        github_urls: Annotated[str, Form(description="One repository URL per line")] = "",
        portfolio_json: Annotated[str, Form(description='[{"title": "...", "description": "..."}]')] = "[]",
        image_captions_json: Annotated[str, Form(description="Captions, in the same order as images")] = "[]",
        retention_days: Annotated[int, Form()] = 180,
        cv: Annotated[UploadFile | None, File()] = None,
        linkedin: Annotated[UploadFile | None, File(description="LinkedIn profile saved as PDF")] = None,
        documents: Annotated[list[UploadFile] | None, File()] = None,
        degrees: Annotated[list[UploadFile] | None, File(description="Diplomas or transcripts")] = None,
        certifications: Annotated[list[UploadFile] | None, File(description="Certificates")] = None,
        images: Annotated[list[UploadFile] | None, File()] = None,
    ) -> dict[str, Any]:
        docs: list[TextDocument] = []

        async def read(upload: UploadFile) -> bytes:
            data = await upload.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"{upload.filename}: file larger than 15 MB")
            return data

        uploads = [(u, k) for u, k in ((cv, ArtifactKind.cv), (linkedin, ArtifactKind.linkedin)) if u is not None]
        uploads += [(u, k) for files, k in ((documents, ArtifactKind.document), (degrees, ArtifactKind.degree),
                                             (certifications, ArtifactKind.certification)) for u in files or []]
        for upload, kind in uploads[:60]:
            if upload.filename:
                docs.append(TextDocument(name=upload.filename, kind=kind,
                                         content=extract_text(upload.filename, await read(upload))))
        try:
            portfolio = json.loads(portfolio_json or "[]")
            captions = json.loads(image_captions_json or "[]")
            submission = Submission(
                consent=consent, identity_name=identity_name, identity_email=identity_email,
                retention_days=retention_days, documents=docs, portfolio=portfolio,
                repositories=[RepositoryInput(url=u.strip()) for u in github_urls.splitlines() if u.strip()],
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HTTPException(422, f"invalid submission: {exc}") from exc
        image_inputs = []
        for i, upload in enumerate(images or []):
            if not upload.filename:
                continue
            if upload.content_type not in IMAGE_TYPES:
                raise HTTPException(415, f"{upload.filename}: only PNG, JPEG and WebP images are accepted")
            caption = str(captions[i]) if i < len(captions) else ""
            image_inputs.append(ImageInput(upload.filename, await read(upload), caption[:2000]))
        cand = engine.ingest(job_id, submission, image_inputs)
        return {"candidate_ref": cand.ref, "artifacts": cand.artifact_ids}

    # ------------------------------------------------------------------ candidates

    @app.get("/api/candidates/{ref}/report", dependencies=auth)
    def report(ref: str) -> DashboardReport:
        return engine.get_report(ref)

    @app.get("/api/candidates/{ref}/graph", dependencies=auth)
    def graph(ref: str) -> dict[str, Any]:
        g = engine.get_graph(ref)
        if g is None:
            raise HTTPException(404, "no skill graph yet: run the evaluation first")
        locale = engine.get_job(engine.get_candidate(ref).job_id).locale
        out = g.model_dump(mode="json")
        for a in out["assessments"]:
            a["label"] = CATALOG[a["skill_id"]].l(locale)
        out["declared_only_labels"] = [CATALOG[s].l(locale) for s in g.declared_only if s in CATALOG]
        return out

    @app.get("/api/candidates/{ref}/artifacts", dependencies=auth)
    def artifacts(ref: str) -> list[dict[str, Any]]:
        engine.get_candidate(ref)
        return [a.model_dump(mode="json", exclude={"repo_files"}) | {"repo_paths": a.repo_paths[:300]}
                for a in engine.artifacts(ref)]

    @app.get("/api/candidates/{ref}/media/{artifact_id}", dependencies=auth)
    def media(ref: str, artifact_id: str) -> FileResponse:
        path = engine.media_path(ref, artifact_id)
        if path is None:
            raise HTTPException(404, "no redacted media for this artifact")
        return FileResponse(path)

    @app.get("/api/candidates/{ref}/explanation", dependencies=auth)
    def explanation(ref: str) -> dict[str, Any]:
        return engine.explanation(ref)

    def signer(who: Principal, claimed: str) -> str:
        # A named account always signs with its own name; the shared key and dev mode keep the claimed one.
        if who.authenticated and not who.shared_key:
            return who.name
        return claimed.strip() or who.name

    @app.post("/api/candidates/{ref}/decisions")
    def decide(ref: str, decision: HumanDecision, who: Principal = CAN_DECIDE) -> DashboardReport:
        return engine.decide(ref, decision.model_copy(update={"reviewer": signer(who, decision.reviewer)}))

    @app.post("/api/candidates/{ref}/reveal")
    def reveal(ref: str, body: RevealRequest, who: Principal = CAN_DECIDE) -> dict[str, Any]:
        return {"candidate_ref": ref, "identity": engine.reveal(ref, signer(who, body.reviewer), body.reason)}

    @app.post("/api/candidates/{ref}/explanation-link")
    def explanation_link(
        ref: str, who: Principal = CAN_DECIDE, days: Annotated[int, Query(ge=1, le=90)] = 30,
    ) -> dict[str, Any]:
        return engine.create_explanation_link(ref, who.name, days)

    @app.get("/api/candidates/{ref}/explanation-links")
    def explanation_links(ref: str, who: Principal = CAN_DECIDE) -> list[dict[str, Any]]:
        return engine.explanation_links(ref)

    @app.delete("/api/candidates/{ref}/explanation-links/{link_id}")
    def revoke_explanation_link(ref: str, link_id: str, who: Principal = CAN_DECIDE) -> dict[str, bool]:
        return {"revoked": engine.revoke_explanation_link(ref, link_id, who.name)}

    @app.post("/api/candidates/{ref}/assessments")
    def create_assessment(ref: str, body: NewAssessment, who: Principal = CAN_DECIDE) -> dict[str, Any]:
        cand = engine.get_candidate(ref)
        job = engine.get_job(cand.job_id)
        l1, arts = engine.level1(ref)
        personal = personal_questions(l1, arts, random.SystemRandom()) if body.personal else []
        try:
            token, session = tests.create(job, body.level, locale=job.locale, mode="candidate", n=body.questions,
                                          personal=personal, candidate_ref=ref, job_id=job.id,
                                          seb_config_keys=[k.strip() for k in body.seb_config_keys if k.strip()],
                                          valid_hours=body.valid_hours)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        engine.ledger.append("assessment_created", {
            "assessment": session.id, "level": body.level, "questions": len(session.questions),
            "personal_questions": len(personal), "seb_required": session.seb_required,
            "expires_at": session.expires_at.isoformat()}, actor=who.name, job_id=job.id, candidate_ref=ref)
        return {"token": token, "path": f"/test/{token}", "expires_at": session.expires_at.isoformat(),
                "questions": len(session.questions), "untestable_skills": session.untestable_skills}

    @app.post("/api/candidates/{ref}/pilot")
    def create_pilot(ref: str, body: NewPilot, who: Principal = CAN_DECIDE) -> dict[str, Any]:
        cand = engine.get_candidate(ref)
        job = engine.get_job(cand.job_id)
        scenario = scenario_for(job, body.scenario_id, required=False)
        l1, arts = engine.level1(ref)
        personal = personal_questions(l1, arts, random.SystemRandom()) if body.personal else []
        questions = build_questions_for(job, body.level, body.knowledge_questions, body.ai_questions, job.locale,
                                        personal)
        if scenario is None and not questions:
            raise HTTPException(422, "no question and no practical mission exist yet for this job")
        task, note = None, ""
        if body.ownership:
            repos = [(a.label, a.repo_paths, {**a.repo_files, **a.source_files}) for a in engine.artifacts(ref)
                     if a.kind == ArtifactKind.repository]
            task = choose_task(repos, random.SystemRandom(), job.locale) if repos else None
            if task is None:
                note = ("no function long and rich enough in the candidate's stored repository files: "
                        "the session has no task on their own code")
        token, session = pilot.create(scenario, body.level, locale=job.locale, mode="candidate", job_title=job.title,
                                      job_id=job.id, candidate_ref=ref, fault_ids=body.fault_ids,
                                      build_minutes=body.build_minutes, ownership=task, valid_hours=body.valid_hours,
                                      questions=questions, llm_owner=who.name)
        judge = byok.provider(who.name, "judge") or pilot.judge_provider
        engine.ledger.append("pilot_created", {
            "session": session.id, "scenario": scenario.id if scenario else None, "level": body.level,
            "questions": {"knowledge": sum(q.section == "knowledge" for q in questions),
                          "with_ai": sum(q.section == "ai" for q in questions)},
            "faults": [f.id for f in session.faults], "ownership": task is not None,
            "build_minutes": session.build_minutes, "expires_at": session.expires_at.isoformat(),
        }, actor=who.name, job_id=job.id, candidate_ref=ref)
        return {"token": token, "path": f"/pilote/{token}", "session_id": session.id,
                "scenario": scenario.id if scenario else None, "questions": len(questions),
                "faults": [f.id for f in session.faults], "ownership": task is not None, "note": note,
                "build_minutes": session.build_minutes, "expires_at": session.expires_at.isoformat(),
                "judge": f"{judge.name}/{judge.model}" if judge else None, "assistant": session.assistant_kind}

    @app.get("/api/candidates/{ref}/pilot", dependencies=auth)
    def list_pilot(ref: str) -> list[dict[str, Any]]:
        engine.get_candidate(ref)
        return [{"id": s.id, "phase": s.phase, "scenario_id": s.scenario_id, "level": s.level,
                 "created_at": s.created_at.isoformat(), "expires_at": s.expires_at.isoformat(),
                 "faults": [f.model_dump(mode="json") for f in s.faults],
                 "ownership": s.ownership.public() if s.ownership else None,
                 "transcript": [t.public() for t in s.turns], "report": s.report}
                for s in sorted(pilot.list_for(ref), key=lambda x: x.created_at, reverse=True)]

    @app.post("/api/pilot-sessions/{session_id}/inject")
    def arm_fault(session_id: str, body: ArmFault, who: Principal = CAN_DECIDE) -> dict[str, Any]:
        try:
            session = pilot.arm_fault(session_id, body.fault_id)
        except KeyError as exc:
            raise HTTPException(404, "unknown AI-pilot session") from exc
        except PilotError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        engine.ledger.append("pilot_fault_armed", {"session": session.id, "fault": body.fault_id}, actor=who.name,
                             job_id=session.job_id, candidate_ref=session.candidate_ref)
        return {"armed": True, "faults": [f.id for f in session.faults]}

    @app.get("/api/candidates/{ref}/assessments", dependencies=auth)
    def list_assessments(ref: str) -> list[dict[str, Any]]:
        engine.get_candidate(ref)
        return [{"id": s.id, "status": s.status, "level": s.level, "created_at": s.created_at.isoformat(),
                 "expires_at": s.expires_at.isoformat(), "seb_required": s.seb_required,
                 "questions": len(s.questions), "results": s.results} for s in tests.list_for(ref)]

    @app.post("/api/candidates/{ref}/erase")
    def erase(ref: str, body: EraseRequest, who: Principal = CAN_PRIVACY) -> dict[str, Any]:
        return engine.erase(ref, signer(who, body.actor))

    @app.get("/api/candidates/{ref}/export")
    def export(ref: str, who: Principal = CAN_PRIVACY) -> JSONResponse:
        return JSONResponse(engine.export_candidate(ref, who.name),
                            headers={"Content-Disposition": f'attachment; filename="export-{ref}.json"'})

    # ------------------------------------------------------------------ public explanation (AI Act Art. 86)

    @app.get("/api/public/explanation/{token}")
    def public_explanation(token: str) -> dict[str, Any]:
        if len(token) > 100:
            raise HTTPException(404, "this explanation link is invalid or has expired")
        return engine.public_explanation(token)

    # ------------------------------------------------------------------ administration

    @app.post("/api/admin/retention/run")
    def retention_run(who: Principal = CAN_PRIVACY) -> dict[str, Any]:
        erased = engine.purge_expired(actor=who.name)
        return {"erased": erased, "count": len(erased)}

    @app.get("/api/admin/monitoring")
    def monitoring(who: Principal = CAN_PRIVACY) -> dict[str, Any]:
        refs = [c.ref for c in engine.store.list("candidates", Candidate)]
        all_tests = [s for ref in refs for s in tests.list_for(ref)]
        return engine.monitoring(all_tests)

    @app.post("/api/admin/incidents", status_code=201)
    def incident(body: IncidentReport, who: Principal = CAN_PRIVACY) -> dict[str, Any]:
        return engine.record_incident(who.name, body.severity, body.description, body.affected_candidates)

    # ------------------------------------------------------------------ ATS bridge (add-on mode)

    bridge = Bridge(engine, engine.vault_key, settings.public_base_url)
    app.state.bridge = bridge

    @app.get("/api/integrations")
    def list_integrations(who: Principal = CAN_ADMIN) -> list[dict[str, Any]]:
        return [c.public() for c in bridge.list()]

    @app.post("/api/integrations", status_code=201)
    def create_integration(body: ConnectionInput, who: Principal = CAN_ADMIN) -> dict[str, Any]:
        conn, generated = bridge.create(body, who.name)
        out = conn.public()
        if generated:
            out["webhook_secret"] = generated  # shown once (generic connector)
        return out

    @app.delete("/api/integrations/{conn_id}")
    def delete_integration(conn_id: str, who: Principal = CAN_ADMIN) -> dict[str, bool]:
        return {"removed": bridge.delete(conn_id, who.name)}

    @app.post("/api/integrations/{conn_id}/webhook")
    async def webhook(conn_id: str, request: Request) -> JSONResponse:
        body = await request.body()
        if len(body) > 20 * 1024 * 1024:
            raise HTTPException(413, "payload too large")
        try:
            result = bridge.receive(conn_id, dict(request.headers), body)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(401, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return JSONResponse(result, status_code=202 if result.get("accepted") else 200)

    @app.get("/api/admin/users")
    def list_users(who: Principal = CAN_ADMIN) -> list[dict[str, str]]:
        return users.list()

    @app.post("/api/admin/users", status_code=201)
    def add_user(body: NewUser, who: Principal = CAN_ADMIN) -> dict[str, str]:
        try:
            key = users.add(body.name, body.role)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        engine.ledger.append("account_created", {"name": body.name, "role": body.role}, actor=who.name)
        return {"name": body.name, "role": body.role, "api_key": key,
                "notice": "Shown once: store it now, only its hash is kept."}

    @app.delete("/api/admin/users/{name}")
    def delete_user(name: str, who: Principal = CAN_ADMIN) -> dict[str, bool]:
        removed = users.remove(name)
        if removed:
            byok.delete(name)  # a removed account's model key goes with it
            engine.ledger.append("account_removed", {"name": name}, actor=who.name)
        return {"removed": removed}

    # ------------------------------------------------------------------ audit

    @app.get("/api/audit/ledger", dependencies=auth)
    def ledger(
        response: Response,
        candidate_ref: str | None = None, job_id: str | None = None, kind: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100, offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[dict[str, Any]]:
        response.headers["X-Total-Count"] = str(engine.ledger.count(candidate_ref=candidate_ref, job_id=job_id,
                                                                    kind=kind))
        return [e.model_dump(mode="json") for e in engine.ledger_entries(
            candidate_ref=candidate_ref, job_id=job_id, kind=kind, limit=limit, offset=offset)]

    @app.get("/api/audit/verify", dependencies=auth)
    def verify() -> dict[str, Any]:
        return engine.verify_ledger().model_dump()

    # ------------------------------------------------------------------ demo

    @app.post("/api/demo/seed", dependencies=[CAN_ADMIN])
    def seed() -> dict[str, Any]:
        if not settings.enable_demo:
            raise HTTPException(403, "demo data is disabled (TE_ENABLE_DEMO=false)")
        from ..demo import seed_demo

        return seed_demo(engine)

    # ------------------------------------------------------------------ front-end (production build)

    dist = Path(settings.frontend_dist) if settings.frontend_dist else (
        Path(__file__).resolve().parents[3] / "frontend" / "dist")
    if (dist / "index.html").is_file():
        dist = dist.resolve()
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        def spa(path: str) -> FileResponse | JSONResponse:
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app

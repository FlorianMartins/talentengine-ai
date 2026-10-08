"""HTTP API (FastAPI). Interactive documentation is served at /api/docs."""

from __future__ import annotations

import hmac
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from ..config import ENGINE_VERSION, Settings, get_settings
from ..dashboard.presets import list_presets
from ..i18n import localise
from ..models import (
    MAX_CREDENTIAL_WEIGHT,
    ArtifactKind,
    CandidateSummary,
    DashboardReport,
    Family,
    HumanDecision,
    JobProfile,
)
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
    reviewer: str = Field(..., min_length=2, max_length=120)
    reason: str = Field(..., min_length=15, max_length=2000)


class EvaluationResult(BaseModel):
    job_id: str
    evaluated: int
    escalated: list[str] = Field(description="Candidates sent to the escalation tier")
    escalation_skipped: dict[str, str] = Field(description="Candidate ref -> why escalation did not happen")
    spent_usd: float


class EraseRequest(BaseModel):
    actor: str = Field(..., min_length=2, max_length=120)


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = engine or Engine(settings)
    app = FastAPI(title="TalentEngine-AI", version=ENGINE_VERSION, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None,
                  description="Skills-first, privacy-first applicant evaluation. No automated rejection.")
    app.state.engine = engine
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["X-Total-Count"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    def require_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if settings.api_key and not (x_api_key and hmac.compare_digest(x_api_key, settings.api_key)):
            raise HTTPException(401, "missing or invalid X-API-Key")

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(PolicyError)
    async def _policy(_: Request, exc: PolicyError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    auth = [Depends(require_key)]

    # ------------------------------------------------------------------ meta

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        # Public on purpose: the UI needs to know a key is required before its first call fails.
        return {"status": "ok", "version": ENGINE_VERSION, "auth_required": bool(settings.api_key),
                "demo_enabled": settings.enable_demo}

    @app.get("/api/runtime", dependencies=auth)
    def runtime() -> dict[str, Any]:
        return {
            "version": ENGINE_VERSION,
            "vision_detector": engine.detector.name,
            "llm_provider": engine.provider.name if engine.provider else "none",
            "llm_model": engine.provider.model if engine.provider else "",
            "max_credential_weight": MAX_CREDENTIAL_WEIGHT,
            "demo_enabled": settings.enable_demo,
            "auth_required": bool(settings.api_key),
        }

    @app.get("/api/catalog/skills", dependencies=auth)
    def catalog(locale: str = "fr") -> list[dict[str, Any]]:
        return [{"id": s.id, "family": s.family, "label": s.label.get(locale, s.label["en"]),
                 "statement": s.statement.get(locale, s.statement["en"])} for s in SKILLS]

    @app.get("/api/catalog/families", dependencies=auth)
    def families() -> list[str]:
        return [f.value for f in Family]

    @app.get("/api/catalog/presets", dependencies=auth)
    def presets(locale: str = "fr") -> list[dict[str, Any]]:
        return list_presets("en" if locale == "en" else "fr")

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

    @app.post("/api/jobs", dependencies=auth, status_code=201)
    def create_job(job: JobProfile, x_actor: Annotated[str, Header()] = "recruiter") -> JobProfile:
        return engine.create_job(job, actor=x_actor)

    @app.get("/api/jobs/{job_id}", dependencies=auth)
    def get_job(job_id: str) -> JobProfile:
        return engine.get_job(job_id)

    @app.put("/api/jobs/{job_id}", dependencies=auth)
    def update_job(job_id: str, job: JobProfile, x_actor: Annotated[str, Header()] = "recruiter") -> JobProfile:
        return engine.update_job(job_id, job, actor=x_actor)

    @app.get("/api/jobs/{job_id}/candidates", dependencies=auth)
    def candidates(job_id: str) -> list[CandidateSummary]:
        engine.get_job(job_id)
        return engine.summaries(job_id)

    @app.post("/api/jobs/{job_id}/evaluate", dependencies=auth)
    def evaluate(job_id: str, x_actor: Annotated[str, Header()] = "system") -> EvaluationResult:
        run = engine.evaluate(job_id, actor=x_actor)
        locale = engine.get_job(job_id).locale
        return EvaluationResult(job_id=run.job_id, evaluated=run.evaluated, escalated=run.escalated,
                                escalation_skipped={k: localise(v, locale) for k, v in run.skipped.items()},
                                spent_usd=round(run.spent_usd, 6))

    @app.get("/api/jobs/{job_id}/usage", dependencies=auth)
    def usage(job_id: str) -> dict[str, Any]:
        return engine.usage(job_id)

    @app.post("/api/jobs/{job_id}/candidates/json", dependencies=auth, status_code=201)
    def submit_json(job_id: str, submission: Submission) -> dict[str, Any]:
        cand = engine.ingest(job_id, submission)
        return {"candidate_ref": cand.ref, "artifacts": cand.artifact_ids}

    @app.post("/api/jobs/{job_id}/candidates", dependencies=auth, status_code=201)
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
        documents: Annotated[list[UploadFile] | None, File()] = None,
        images: Annotated[list[UploadFile] | None, File()] = None,
    ) -> dict[str, Any]:
        docs: list[TextDocument] = []

        async def read(upload: UploadFile) -> bytes:
            data = await upload.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"{upload.filename}: file larger than 15 MB")
            return data

        if cv is not None and cv.filename:
            docs.append(TextDocument(name=cv.filename, content=extract_text(cv.filename, await read(cv)),
                                     kind=ArtifactKind.cv))
        for upload in documents or []:
            if upload.filename:
                docs.append(TextDocument(name=upload.filename,
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

    @app.post("/api/candidates/{ref}/decisions", dependencies=auth)
    def decide(ref: str, decision: HumanDecision) -> DashboardReport:
        return engine.decide(ref, decision)

    @app.post("/api/candidates/{ref}/reveal", dependencies=auth)
    def reveal(ref: str, body: RevealRequest) -> dict[str, Any]:
        return {"candidate_ref": ref, "identity": engine.reveal(ref, body.reviewer, body.reason)}

    @app.post("/api/candidates/{ref}/erase", dependencies=auth)
    def erase(ref: str, body: EraseRequest) -> dict[str, Any]:
        return engine.erase(ref, body.actor)

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

    @app.post("/api/demo/seed", dependencies=auth)
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

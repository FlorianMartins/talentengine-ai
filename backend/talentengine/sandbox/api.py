"""Public sandbox: "how well does my CV and portfolio match this offer?" — no account, nothing stored.

Each analysis runs in a throw-away engine (in-memory database, temporary directory deleted afterwards),
so a visitor's CV never touches the persistent store, the audit ledger or the disk beyond the request.
Abuse is bounded by per-IP rate limits, a concurrency cap, upload limits and SSRF-safe fetching.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, ValidationError

from ..config import Settings
from ..dashboard.presets import list_presets, preset_job
from ..funnel.repo import RepoFetchError
from ..i18n import localise
from ..models import ArtifactKind, JobProfile, Locale
from ..pipeline import Engine, PolicyError, PortfolioItem, RepositoryInput, Submission, TextDocument, extract_text
from ..shield.vision import NoDetector
from ..store import Store
from ..translator.catalog import CATALOG
from .fetch import FetchError, fetch, fetch_offer
from .github import expand_github_urls, snapshot_with_git
from .offer import OfferError, parse_offer

MAX_FILE = 8 * 1024 * 1024
MAX_REPOS = 5
MAX_LINKS = 3
MAX_DOCS = 3


class OfferRequest(BaseModel):
    text: str = Field("", max_length=60_000)
    url: str = Field("", max_length=2000)
    locale: str = "fr"


class _RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, bucket: str, key: str, per_hour: int) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[(bucket, key)]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= per_hour:
                wait = int(3600 - (now - hits[0])) // 60 + 1
                raise HTTPException(429, f"limit reached for this hour, try again in about {wait} min")
            hits.append(now)


def _client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy and request.headers.get("x-forwarded-for"):
        return request.headers["x-forwarded-for"].split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _tips(report: Any, locale: str) -> list[str]:
    fr = locale == "fr"
    tips = []
    for gap in report.gaps:
        if gap.declared_by_candidate:
            tips.append(f"« {gap.label} » est mentionné sans preuve : ajoutez un lien vers une réalisation "
                        "qui le montre." if fr else
                        f"\"{gap.label}\" is mentioned without proof: add a link to work that shows it.")
        else:
            tips.append(f"Aucune preuve de « {gap.label} » : un projet, un rapport chiffré ou une photo de réalisation "
                        "renforcerait votre dossier." if fr else
                        f"No evidence of \"{gap.label}\": a project, a report with figures or a photo of your work "
                        "would strengthen your application.")
    for skill in report.validated_skills:
        if skill.confidence <= 0.5 and all(e.artifact_label == "CV" for e in skill.evidence):
            tips.append(f"« {skill.label} » n'est décrit que dans votre CV : un dépôt, un document ou un lien de "
                        "portfolio le confirmerait." if fr else
                        f"\"{skill.label}\" is only described in your CV: a repository, document or portfolio link "
                        "would confirm it.")
    return tips[:6]


def _candidate_warnings(artifacts: list[dict[str, Any]], locale: str) -> list[str]:
    flagged = [a["label"] for a in artifacts if a["injection_suspected"]]
    if not flagged:
        return []
    names = ", ".join(flagged)
    if locale == "fr":
        return [f"Certains passages de {names} ressemblent à des instructions adressées à une IA. Ils ont été "
                "exclus de toute analyse par un modèle d'IA et n'ont aucun effet sur votre score. Si c'est "
                "involontaire (un article sur la sécurité des IA, par exemple), un recruteur le verra simplement "
                "signalé."]
    return [f"Some passages in {names} look like instructions addressed to an AI. They were excluded from any "
            "AI-model analysis and have no effect on your score. If this is unintentional (an article about AI "
            "security, for instance), a recruiter simply sees it flagged."]


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/try", tags=["public sandbox"])
    limiter = _RateLimiter()
    slots = threading.BoundedSemaphore(settings.sandbox_concurrency)

    def guard(request: Request, bucket: str, per_hour: int) -> None:
        if not settings.sandbox_enabled:
            raise HTTPException(404, "the public sandbox is disabled")
        limiter.check(bucket, _client_ip(request, settings.trust_proxy), per_hour)

    @router.get("/config")
    def config(locale: str = "fr") -> dict[str, Any]:
        loc: Locale = "en" if locale == "en" else "fr"
        presets = [{"id": p["id"], "family": p["family"], "title": p["title"], "summary": p["summary"],
                    "criteria": [CATALOG[c["skill_id"]].l(loc) for c in p["job"]["criteria"]]}
                   for p in list_presets(loc)]
        return {"enabled": settings.sandbox_enabled, "presets": presets,
                "limits": {"matches_per_hour": settings.sandbox_matches_per_hour, "max_repos": MAX_REPOS,
                           "max_links": MAX_LINKS, "max_documents": MAX_DOCS, "max_file_mb": MAX_FILE // 1024 // 1024},
                "skills": [{"id": s.id, "label": s.l(loc), "family": s.family} for s in CATALOG.values()]}

    @router.post("/offer")
    def offer(body: OfferRequest, request: Request) -> dict[str, Any]:
        locale = "en" if body.locale == "en" else "fr"
        try:
            return _offer(body, request, locale)
        except HTTPException as exc:
            raise HTTPException(exc.status_code, localise(str(exc.detail), locale)) from exc

    def _offer(body: OfferRequest, request: Request, locale: str) -> dict[str, Any]:
        guard(request, "offer", settings.sandbox_offers_per_hour)
        title, source = "", "text"
        text = body.text
        if body.url.strip():
            try:
                page = fetch_offer(body.url)
            except FetchError as exc:
                raise HTTPException(422, f"could not read this link: {exc}") from exc
            text, title, source = page.text, page.title, urlsplit(page.url).hostname or "link"
        try:
            parsed = parse_offer(text, title=title, locale=locale)
        except OfferError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"source": source, **parsed.model_dump(mode="json")}

    @router.post("/match")
    async def match(
        request: Request,
        consent: Annotated[bool, Form()],
        identity_name: Annotated[str, Form(min_length=2, max_length=200)],
        job_json: Annotated[str, Form()] = "",
        preset_id: Annotated[str, Form()] = "",
        locale: Annotated[str, Form()] = "fr",
        github_urls: Annotated[str, Form()] = "",
        portfolio_urls: Annotated[str, Form()] = "",
        cv: Annotated[UploadFile | None, File()] = None,
        documents: Annotated[list[UploadFile] | None, File()] = None,
    ) -> dict[str, Any]:
        try:
            return await _match(request, consent, identity_name, job_json, preset_id, locale, github_urls,
                                portfolio_urls, cv, documents)
        except HTTPException as exc:
            raise HTTPException(exc.status_code, localise(str(exc.detail), locale)) from exc

    async def _match(
        request: Request, consent: bool, identity_name: str, job_json: str, preset_id: str, locale: str,
        github_urls: str, portfolio_urls: str, cv: UploadFile | None, documents: list[UploadFile] | None,
    ) -> dict[str, Any]:
        guard(request, "match", settings.sandbox_matches_per_hour)
        if not consent:
            raise HTTPException(422, "consent is required")
        loc: Locale = "en" if locale == "en" else "fr"
        try:
            if job_json.strip():
                job = JobProfile.model_validate(json.loads(job_json))
            elif preset_id:
                job = preset_job(preset_id, loc)
            else:
                raise HTTPException(422, "choose a reference role or analyse an offer first")
        except (json.JSONDecodeError, ValidationError, KeyError) as exc:
            raise HTTPException(422, f"invalid job profile: {exc}") from exc
        job.locale = loc

        async def read(upload: UploadFile) -> bytes:
            data = await upload.read(MAX_FILE + 1)
            if len(data) > MAX_FILE:
                raise HTTPException(413, f"{upload.filename}: file larger than {MAX_FILE // 1024 // 1024} MB")
            return data

        try:
            docs: list[TextDocument] = []
            if cv is not None and cv.filename:
                docs.append(TextDocument(name=cv.filename, content=extract_text(cv.filename, await read(cv)),
                                         kind=ArtifactKind.cv))
            for upload in (documents or [])[:MAX_DOCS]:
                if upload.filename:
                    docs.append(TextDocument(name=upload.filename,
                                             content=extract_text(upload.filename, await read(upload))))
        except PolicyError as exc:
            raise HTTPException(422, str(exc)) from exc

        if not slots.acquire(timeout=30):
            raise HTTPException(503, "the sandbox is busy, please retry in a minute")
        tmp = Path(tempfile.mkdtemp(prefix="te-try-"))
        try:
            try:
                repo_urls = expand_github_urls([u for u in github_urls.splitlines() if u.strip()],
                                               settings.github_token)[:MAX_REPOS]
                repos = []
                for url in repo_urls:
                    snap = snapshot_with_git(url)
                    repos.append(RepositoryInput(url=url, paths=snap.paths, files=snap.files))
                portfolio = []
                for link in [u.strip() for u in portfolio_urls.splitlines() if u.strip()][:MAX_LINKS]:
                    page = fetch(link)
                    portfolio.append(PortfolioItem(title=page.title[:200] or (urlsplit(page.url).hostname or ""),
                                                   description=page.text[:8000]))
            except (RepoFetchError, FetchError) as exc:
                raise HTTPException(422, str(exc)) from exc
            sandbox = Settings(data_dir=tmp, vision_detector="none", llm_provider="none", ner=settings.ner,
                               enable_demo=False)
            engine = Engine(sandbox, store=Store(":memory:"), detector=NoDetector(), provider=False)
            try:
                created = engine.create_job(job, actor="sandbox")
                sub = Submission(consent=True, identity_name=identity_name, documents=docs, repositories=repos,
                                 portfolio=portfolio, retention_days=1)
                cand = engine.ingest(created.id, sub)
            except PolicyError as exc:
                raise HTTPException(422, str(exc)) from exc
            engine.evaluate(created.id, actor="sandbox")
            report = engine.get_report(cand.ref)
            graph = engine.get_graph(cand.ref)
            artifacts = [{"label": a.label, "kind": a.kind, "status": a.status,
                          "masked": sum(a.redaction.pii_replaced.values()),
                          "injection_suspected": a.redaction.injection_suspected,
                          "files": len(a.repo_paths)} for a in engine.artifacts(cand.ref)]
            graph_out = graph.model_dump(mode="json") if graph else {"assessments": [], "edges": []}
            for a in graph_out["assessments"]:
                a["label"] = CATALOG[a["skill_id"]].l(loc)
            report_out = report.model_dump(mode="json")
            # The recruiter-facing warnings are rephrased for the person who is testing their own profile.
            report_out["warnings"] = _candidate_warnings(artifacts, loc)
            return {"report": report_out, "graph": graph_out, "artifacts": artifacts, "tips": _tips(report, loc),
                    "job": created.model_dump(mode="json"), "stored": False}
        finally:
            slots.release()
            shutil.rmtree(tmp, ignore_errors=True)

    return router

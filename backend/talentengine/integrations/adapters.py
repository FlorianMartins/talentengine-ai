"""ATS adapters: TalentEngine-AI as an add-on to the applicant tracking system recruiters already use.

The recruiter keeps working in Greenhouse, Lever, Ashby or their own tool. A webhook announces a new
application; TalentEngine verifies its signature, downloads the CV and attachments through the ATS API,
evaluates them against the mapped job profile, and writes a note back into the ATS with the score, the key
evidence, the candidate explanation link and the interview questions.

Provider details were checked against public documentation in October 2026; items marked VERIFY could not
be confirmed and should be checked against the provider's current reference before production use.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from ..sandbox.fetch import FetchError, _check_url

MAX_DOWNLOAD = 15 * 1024 * 1024


@dataclass
class Document:
    name: str
    data: bytes
    kind: str = "document"  # cv | linkedin | degree | certification | document


@dataclass
class InboundApplication:
    external_application_id: str
    external_candidate_id: str
    external_job_id: str
    name: str = ""
    email: str = ""
    github_urls: list[str] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    callback_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class AtsAdapter(Protocol):
    provider: str

    def verify(self, headers: dict[str, str], body: bytes) -> bool: ...

    def parse(self, payload: dict[str, Any]) -> InboundApplication | None: ...

    def collect(self, app: InboundApplication) -> InboundApplication: ...

    def post_note(self, app: InboundApplication, text: str) -> None: ...


def safe_download(url: str, client: httpx.Client) -> bytes:
    """Download an attachment with the SSRF guard (public addresses only, re-checked on redirects)."""
    for _ in range(4):
        _check_url(url)
        resp = client.get(url, follow_redirects=False)
        if resp.is_redirect and "location" in resp.headers:
            url = str(httpx.URL(url).join(resp.headers["location"]))
            continue
        resp.raise_for_status()
        if len(resp.content) > MAX_DOWNLOAD:
            raise FetchError("attachment larger than 15 MB")
        return resp.content
    raise FetchError("too many redirects")


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


# --------------------------------------------------------------------------------------------- generic


class GenericAdapter:
    """Our own documented contract, for any ATS, HR tool or internal script.

    Webhook: ``POST /api/integrations/<connection>/webhook`` with header
    ``X-TalentEngine-Signature: sha256=<hex HMAC-SHA256 of the raw body with the connection secret>`` and a
    JSON body ``{application_id, candidate_id, job_id, name, email, github_urls[], documents[{name, kind,
    url | content_base64}], callback_url}``. The result is POSTed to ``callback_url`` signed the same way.
    """

    provider = "generic"

    def __init__(self, secret: str, client: httpx.Client | None = None) -> None:
        self.secret = secret
        self.client = client or httpx.Client(timeout=20)

    def verify(self, headers: dict[str, str], body: bytes) -> bool:
        given = headers.get("x-talentengine-signature", "")
        return hmac.compare_digest(given, "sha256=" + _hmac_hex(self.secret, body))

    def parse(self, payload: dict[str, Any]) -> InboundApplication | None:
        if not payload.get("application_id") or not payload.get("job_id"):
            return None
        docs = []
        for d in payload.get("documents", [])[:20]:
            if d.get("content_base64"):
                docs.append(Document(str(d.get("name", "file")), base64.b64decode(d["content_base64"]),
                                     str(d.get("kind", "document"))))
        app = InboundApplication(str(payload["application_id"]), str(payload.get("candidate_id", "")),
                                 str(payload["job_id"]), str(payload.get("name", "")), str(payload.get("email", "")),
                                 [str(u) for u in payload.get("github_urls", [])][:10], docs,
                                 str(payload.get("callback_url", "")), payload)
        return app

    def collect(self, app: InboundApplication) -> InboundApplication:
        for d in app.raw.get("documents", [])[:20]:
            if d.get("url") and not d.get("content_base64"):
                app.documents.append(Document(str(d.get("name", "file")), safe_download(str(d["url"]), self.client),
                                              str(d.get("kind", "document"))))
        return app

    def post_note(self, app: InboundApplication, text: str) -> None:
        if not app.callback_url:
            return
        _check_url(app.callback_url)
        body = json.dumps({"application_id": app.external_application_id, "note": text}).encode()
        self.client.post(app.callback_url, content=body, headers={
            "Content-Type": "application/json", "X-TalentEngine-Signature": "sha256=" + _hmac_hex(self.secret, body)})


# --------------------------------------------------------------------------------------------- Greenhouse


class GreenhouseAdapter:
    """Greenhouse Harvest API v3 (OAuth2 client credentials). v1/v2 were scheduled for removal on 31 Aug 2026.

    Webhook signature: header ``Signature: sha256 <hex>`` = HMAC-SHA256(secret key, raw body).
    Resumes: ``GET /v3/attachments?application_ids=<id>`` (attachment ``url`` expires after 7 days).
    Notes: ``POST /v3/notes`` — VERIFY the body fields against the v3 write-endpoint migration guide.
    """

    provider = "greenhouse"
    base = "https://harvest.greenhouse.io/v3"

    def __init__(self, webhook_secret: str, client_id: str, client_secret: str, user_id: str = "",
                 client: httpx.Client | None = None) -> None:
        self.webhook_secret, self.client_id, self.client_secret, self.user_id = (webhook_secret, client_id,
                                                                                client_secret, user_id)
        self.client = client or httpx.Client(timeout=20)
        self._token = ""

    def verify(self, headers: dict[str, str], body: bytes) -> bool:
        given = headers.get("signature", "")
        return hmac.compare_digest(given, "sha256 " + _hmac_hex(self.webhook_secret, body))

    def _auth(self) -> dict[str, str]:
        if not self._token:
            data = {"grant_type": "client_credentials"} | ({"sub": self.user_id} if self.user_id else {})
            resp = self.client.post("https://auth.greenhouse.io/token", data=data,
                                    auth=(self.client_id, self.client_secret))
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {self._token}"}

    def parse(self, payload: dict[str, Any]) -> InboundApplication | None:
        application = (payload.get("payload") or {}).get("application") or {}
        if not application.get("id"):
            return None
        candidate = application.get("candidate") or {}
        jobs = application.get("jobs") or [{}]
        emails = candidate.get("email_addresses") or [{}]
        name = " ".join(filter(None, [candidate.get("first_name"), candidate.get("last_name")]))
        return InboundApplication(str(application["id"]), str(candidate.get("id", "")), str(jobs[0].get("id", "")),
                                  name, str(emails[0].get("value", "")), raw=payload)

    def collect(self, app: InboundApplication) -> InboundApplication:
        resp = self.client.get(f"{self.base}/attachments", params={"application_ids": app.external_application_id},
                               headers=self._auth())
        resp.raise_for_status()
        for att in resp.json() if isinstance(resp.json(), list) else resp.json().get("data", []):
            kind = "cv" if att.get("type") == "resume" else "document"
            if att.get("url"):
                app.documents.append(Document(str(att.get("filename", "attachment")),
                                              safe_download(str(att["url"]), self.client), kind))
        return app

    def post_note(self, app: InboundApplication, text: str) -> None:
        resp = self.client.post(f"{self.base}/notes", headers=self._auth(), json={
            "candidate_id": app.external_candidate_id, "body": text, "visibility": "private"})  # VERIFY fields
        resp.raise_for_status()


# --------------------------------------------------------------------------------------------- Lever


class LeverAdapter:
    """Lever API v1 (Basic auth: API key as user name, empty password).

    Webhook: HMAC-SHA256(signature token, token + triggeredAt) must equal the body's ``signature``.
    Files: ``GET /opportunities/{id}/files`` then ``.../files/{file}/download``. Notes:
    ``POST /opportunities/{id}/notes`` with ``{"value": text}``.
    """

    provider = "lever"
    base = "https://api.lever.co/v1"

    def __init__(self, signature_token: str, api_key: str, perform_as: str = "",
                 client: httpx.Client | None = None) -> None:
        self.signature_token, self.api_key, self.perform_as = signature_token, api_key, perform_as
        self.client = client or httpx.Client(timeout=20)

    def verify(self, headers: dict[str, str], body: bytes) -> bool:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return False
        message = f"{payload.get('token', '')}{payload.get('triggeredAt', '')}".encode()
        return hmac.compare_digest(str(payload.get("signature", "")), _hmac_hex(self.signature_token, message))

    def parse(self, payload: dict[str, Any]) -> InboundApplication | None:
        data = payload.get("data") or {}
        if not data.get("opportunityId"):
            return None
        return InboundApplication(str(data.get("applicationId") or data["opportunityId"]),
                                  str(data["opportunityId"]), str(data.get("postingId", "")), raw=payload)

    def collect(self, app: InboundApplication) -> InboundApplication:
        auth = (self.api_key, "")
        opp = self.client.get(f"{self.base}/opportunities/{app.external_candidate_id}", auth=auth)
        opp.raise_for_status()
        info = opp.json().get("data", {})
        app.name = str(info.get("name", ""))
        app.email = str((info.get("emails") or [""])[0])
        app.github_urls = [u for u in (info.get("links") or []) if "github.com/" in str(u)][:10]
        files = self.client.get(f"{self.base}/opportunities/{app.external_candidate_id}/files", auth=auth)
        files.raise_for_status()
        for f in files.json().get("data", [])[:20]:
            dl = self.client.get(f"{self.base}/opportunities/{app.external_candidate_id}/files/{f['id']}/download",
                                 auth=auth)
            if dl.status_code == 200 and len(dl.content) <= MAX_DOWNLOAD:
                app.documents.append(Document(str(f.get("name", "file")), dl.content, "document"))
        if app.documents:
            app.documents[0].kind = "cv"
        return app

    def post_note(self, app: InboundApplication, text: str) -> None:
        params = {"perform_as": self.perform_as} if self.perform_as else {}
        resp = self.client.post(f"{self.base}/opportunities/{app.external_candidate_id}/notes", params=params,
                                json={"value": text}, auth=(self.api_key, ""))
        resp.raise_for_status()


# --------------------------------------------------------------------------------------------- Ashby


class AshbyAdapter:
    """Ashby API (RPC: every call is POST https://api.ashbyhq.com/<method> with Basic auth, API key as user).

    Webhook: header ``Ashby-Signature: sha256=<hex HMAC-SHA256 of the raw body>``. Resume: the candidate's
    ``resumeFileHandle`` exchanged with ``file.info`` for a URL. Note: ``candidate.createNote``.
    VERIFY: request field names of ``file.info`` and ``candidate.createNote``.
    """

    provider = "ashby"
    base = "https://api.ashbyhq.com"

    def __init__(self, webhook_secret: str, api_key: str, client: httpx.Client | None = None) -> None:
        self.webhook_secret, self.api_key = webhook_secret, api_key
        self.client = client or httpx.Client(timeout=20)

    def verify(self, headers: dict[str, str], body: bytes) -> bool:
        return hmac.compare_digest(headers.get("ashby-signature", ""), "sha256=" + _hmac_hex(self.webhook_secret, body))

    def _call(self, method: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.post(f"{self.base}/{method}", json=body, auth=(self.api_key, ""))
        resp.raise_for_status()
        return dict(resp.json().get("results") or {})

    def parse(self, payload: dict[str, Any]) -> InboundApplication | None:
        application = ((payload.get("data") or {}).get("application")) or {}
        if not application.get("id"):
            return None
        candidate = application.get("candidate") or {}
        job = application.get("job") or {}
        return InboundApplication(str(application["id"]), str(candidate.get("id", "")), str(job.get("id", "")),
                                  str(candidate.get("name", "")), raw=payload)

    def collect(self, app: InboundApplication) -> InboundApplication:
        candidate = self._call("candidate.info", {"id": app.external_candidate_id})
        app.name = app.name or str(candidate.get("name", ""))
        app.email = str((candidate.get("primaryEmailAddress") or {}).get("value", ""))
        app.github_urls = [str(s.get("url")) for s in candidate.get("socialLinks", []) or []
                           if "github.com/" in str(s.get("url", ""))][:10]
        handle = (candidate.get("resumeFileHandle") or {}).get("handle")
        if handle:
            url = self._call("file.info", {"fileHandle": handle}).get("url")  # VERIFY field name
            if url:
                app.documents.append(Document("resume", safe_download(str(url), self.client), "cv"))
        return app

    def post_note(self, app: InboundApplication, text: str) -> None:
        self._call("candidate.createNote", {"candidateId": app.external_candidate_id, "note": text})  # VERIFY


def build_adapter(provider: str, secrets: dict[str, str], client: httpx.Client | None = None) -> AtsAdapter:
    if provider == "greenhouse":
        return GreenhouseAdapter(secrets["webhook_secret"], secrets["client_id"], secrets["client_secret"],
                                 secrets.get("user_id", ""), client)
    if provider == "lever":
        return LeverAdapter(secrets["webhook_secret"], secrets["api_key"], secrets.get("perform_as", ""), client)
    if provider == "ashby":
        return AshbyAdapter(secrets["webhook_secret"], secrets["api_key"], client)
    return GenericAdapter(secrets["webhook_secret"], client)

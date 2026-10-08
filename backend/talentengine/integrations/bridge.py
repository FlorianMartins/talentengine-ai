"""ATS bridge: connections, webhook processing and the note written back into the ATS.

A *connection* links one ATS account to TalentEngine: provider, credentials (encrypted with the vault key,
never returned by the API) and a mapping from ATS job ids to TalentEngine job profiles. Webhooks are
verified, answered immediately, and processed in a background thread: download → ingest → evaluate →
explanation link → note in the ATS. Every step is journalled.

Legal note: applications arriving from an ATS are processed under the *deployer's* candidate information
(AI Act Art. 26(11); in France Code du travail L1221-8). The deployer must mention TalentEngine-AI in the
privacy notice of its job ads; the connection records that it confirmed this.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from typing import Any, Literal

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from ..models import ArtifactKind, utcnow
from ..pipeline import Engine, PolicyError, RepositoryInput, Submission, TextDocument, extract_text
from .adapters import AtsAdapter, InboundApplication, build_adapter

log = logging.getLogger(__name__)

Provider = Literal["greenhouse", "lever", "ashby", "generic"]


class Connection(BaseModel):
    id: str
    provider: Provider
    name: str
    job_mapping: dict[str, str] = Field(default_factory=dict)  # ATS job id -> TalentEngine job id
    secrets_encrypted: str = ""
    candidate_notice_confirmed: bool
    write_notes: bool = True
    explanation_link_days: int = 30
    created_at: str = Field(default_factory=lambda: utcnow().isoformat())
    created_by: str = ""

    def public(self) -> dict[str, Any]:
        return self.model_dump(exclude={"secrets_encrypted"}) | {"webhook_path": f"/api/integrations/{self.id}/webhook"}


class ConnectionInput(BaseModel):
    provider: Provider
    name: str = Field(..., min_length=2, max_length=120)
    job_mapping: dict[str, str] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict, description="webhook_secret, api_key, client_id…")
    candidate_notice_confirmed: bool = Field(..., description="Your job ads' privacy notice mentions TalentEngine-AI")
    write_notes: bool = True
    explanation_link_days: int = Field(30, ge=1, le=90)


REQUIRED_SECRETS = {"greenhouse": {"webhook_secret", "client_id", "client_secret"},
                    "lever": {"webhook_secret", "api_key"}, "ashby": {"webhook_secret", "api_key"},
                    "generic": {"webhook_secret"}}


class Bridge:
    def __init__(self, engine: Engine, vault_key: str, public_base_url: str = "") -> None:
        self.engine = engine
        self.fernet = Fernet(vault_key.encode())
        self.public_base_url = public_base_url.rstrip("/")
        self.adapter_factory = build_adapter  # replaceable in tests

    # ---------------------------------------------------------------------------------------- connections

    def create(self, data: ConnectionInput, actor: str) -> tuple[Connection, str]:
        if not data.candidate_notice_confirmed:
            raise PolicyError("confirm that your job ads inform candidates about TalentEngine-AI "
                              "(L1221-8, AI Act 26(11))")
        missing = REQUIRED_SECRETS[data.provider] - {k for k, v in data.secrets.items() if v}
        generated = ""
        if "webhook_secret" in missing and data.provider == "generic":
            generated = secrets.token_urlsafe(32)
            data.secrets["webhook_secret"] = generated
            missing.discard("webhook_secret")
        if missing:
            raise PolicyError(f"missing credentials: {', '.join(sorted(missing))}")
        for job_id in data.job_mapping.values():
            self.engine.get_job(job_id)
        conn = Connection(id="CONN-" + secrets.token_hex(4).upper(), provider=data.provider, name=data.name,
                          job_mapping=data.job_mapping, candidate_notice_confirmed=True, write_notes=data.write_notes,
                          explanation_link_days=data.explanation_link_days, created_by=actor,
                          secrets_encrypted=self.fernet.encrypt(json.dumps(data.secrets).encode()).decode())
        self.engine.store.put("integrations", conn.id, conn)
        self.engine.ledger.append("integration_created", {"connection": conn.id, "provider": conn.provider,
                                                          "jobs": sorted(conn.job_mapping.values())}, actor=actor)
        return conn, generated

    def list(self) -> list[Connection]:
        return self.engine.store.list("integrations", Connection)

    def get(self, conn_id: str) -> Connection | None:
        return self.engine.store.get("integrations", conn_id, Connection)

    def delete(self, conn_id: str, actor: str) -> bool:
        if self.get(conn_id) is None:
            return False
        self.engine.store.delete("integrations", conn_id)
        self.engine.ledger.append("integration_removed", {"connection": conn_id}, actor=actor)
        return True

    def adapter(self, conn: Connection) -> AtsAdapter:
        return self.adapter_factory(conn.provider, json.loads(self.fernet.decrypt(conn.secrets_encrypted.encode())))

    # ---------------------------------------------------------------------------------------- webhooks

    def receive(self, conn_id: str, headers: dict[str, str], body: bytes, background: bool = True) -> dict[str, Any]:
        conn = self.get(conn_id)
        if conn is None:
            raise LookupError("unknown connection")
        adapter = self.adapter(conn)
        if not adapter.verify({k.lower(): v for k, v in headers.items()}, body):
            raise PermissionError("invalid webhook signature")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("body is not JSON") from exc
        app = adapter.parse(payload)
        if app is None:
            return {"accepted": False, "reason": "event ignored (not a new application)"}
        job_id = conn.job_mapping.get(app.external_job_id)
        if not job_id:
            return {"accepted": False, "reason": f"ATS job {app.external_job_id} is not mapped to a job profile"}
        if background:
            threading.Thread(target=self._process, args=(conn, adapter, app, job_id), daemon=True).start()
            return {"accepted": True, "queued": True}
        return {"accepted": True, **self._process(conn, adapter, app, job_id)}

    def _process(self, conn: Connection, adapter: AtsAdapter, app: InboundApplication, job_id: str) -> dict[str, Any]:
        try:
            app = adapter.collect(app)
            kinds = {k.value for k in ArtifactKind}
            docs = [TextDocument(name=d.name, content=extract_text(d.name, d.data),
                                 kind=ArtifactKind(d.kind) if d.kind in kinds else ArtifactKind.document)
                    for d in app.documents[:30]]
            sub = Submission(consent=True, identity_name=app.name or f"ATS {app.external_candidate_id}",
                             identity_email=app.email, documents=docs,
                             repositories=[RepositoryInput(url=u) for u in app.github_urls])
            cand = self.engine.ingest(job_id, sub)
            self.engine.ledger.append("ats_application", {
                "connection": conn.id, "provider": conn.provider, "external_application": app.external_application_id,
                "documents": len(docs), "legal_basis": "deployer's candidate information (AI Act 26(11), L1221-8)",
            }, actor=f"ats:{conn.provider}", job_id=job_id, candidate_ref=cand.ref)
            self.engine.evaluate(job_id, actor=f"ats:{conn.provider}")
            report = self.engine.get_report(cand.ref)
            link = self.engine.create_explanation_link(cand.ref, f"ats:{conn.provider}", conn.explanation_link_days)
            if conn.write_notes:
                adapter.post_note(app, self.note(report, link["path"]))
            return {"candidate_ref": cand.ref, "compatibility_pct": report.compatibility_pct}
        except (PolicyError, Exception) as exc:
            log.exception("ATS application processing failed")
            self.engine.ledger.append("ats_error", {"connection": conn.id, "error": str(exc)[:300],
                                                    "external_application": app.external_application_id},
                                      actor=f"ats:{conn.provider}", job_id=job_id)
            return {"error": str(exc)[:300]}

    def note(self, report: Any, explanation_path: str) -> str:
        fr = report.locale == "fr"
        url = (self.public_base_url + explanation_path) if self.public_base_url else explanation_path
        lines = [
            f"TalentEngine-AI — {report.job_title}",
            (f"Compatibilité : {report.compatibility_pct:.0f} % (preuves : {report.evidence_band}). "
             "Aide à la décision : aucune candidature n'est rejetée automatiquement.") if fr else
            (f"Compatibility: {report.compatibility_pct:.0f}% (evidence: {report.evidence_band}). "
             "Decision support: no application is rejected automatically."),
            "",
            "Preuves clés :" if fr else "Key evidence:",
        ]
        for skill in report.validated_skills[:5]:
            sources = ", ".join(sorted({e.artifact_label for e in skill.evidence}))
            lines.append(f"• {skill.label} — {skill.level_label} ({sources})")
        if report.gaps:
            lines += ["", "À explorer en entretien :" if fr else "To explore in the interview:"]
            lines += [f"• {g.label}" for g in report.gaps[:4]]
        if report.interview_guide:
            lines += ["", "Questions d'entretien :" if fr else "Interview questions:"]
            lines += [f"{i}. {q.question}" for i, q in enumerate(report.interview_guide[:3], start=1)]
        lines += ["", ("Lien d'explication à transmettre au candidat : " if fr else
                       "Explanation link for the candidate: ") + url]
        return "\n".join(lines)

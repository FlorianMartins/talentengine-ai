import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  ClipboardCheck,
  Eye,
  FileSearch,
  Gauge,
  Handshake,
  Info,
  Loader2,
  ScanEye,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { api, ApiError } from "../api/client";
import type { DashboardReport, DecisionKind, RevealResult } from "../api/types";
import { useAccess, useAsync, usePrefs, useSystem, useToast } from "../lib/prefs";
import { dateTime } from "../lib/format";
import { useCrumbs } from "../components/Shell";
import { BandChip, DecisionChip, EmptyState, ErrorState, Gate, Modal, PageSkeleton } from "../components/feedback";
import { ScoreRing } from "../components/charts";
import { Segmented } from "../components/controls";
import { ReportActions, ReportPrintDoc } from "./ReportExtras";
import { ExplanationLinksPanel, VerificationPanel } from "./ReportVerification";
import { PilotPanel } from "./ReportPilot";
import {
  ArtifactsPanel,
  CredentialsPanel,
  CriteriaMatrix,
  GapsPanel,
  GlassBox,
  GraphPanel,
  InterviewGuide,
  ProofPanel,
} from "./ReportSections";

type Tab = "overview" | "proof" | "interview" | "audit";
const TABS: { id: Tab; icon: typeof Gauge }[] = [
  { id: "overview", icon: Gauge },
  { id: "proof", icon: FileSearch },
  { id: "interview", icon: ClipboardCheck },
  { id: "audit", icon: ScanEye },
];

export function ReportPage() {
  const { ref = "" } = useParams();
  const { t, lang } = usePrefs();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.find((x) => x.id === params.get("tab"))?.id ?? "overview") as Tab;
  const report = useAsync(() => api.report(ref), [ref]);
  const explanation = useAsync(() => api.explanation(ref), [ref]);
  const graph = useAsync(() => api.graph(ref).catch(() => null), [ref]);
  const artifacts = useAsync(() => api.artifacts(ref), [ref]);
  const tests = useAsync(() => api.candidateAssessments(ref).catch(() => []), [ref]);
  const pilots = useAsync(() => api.candidatePilots(ref).catch(() => []), [ref]);
  const links = useAsync(() => api.explanationLinks(ref).catch(() => []), [ref]);

  const r = report.data;
  const jobId = r?.job_id ?? explanation.data?.job_id;
  useCrumbs([
    { label: t.nav.overview, to: "/" },
    { label: r?.job_title ?? jobId ?? "…", to: jobId ? `/jobs/${jobId}` : undefined },
    { label: ref },
  ]);

  if (report.loading && !r) return <PageSkeleton />;
  if (report.error || !r) {
    const notEvaluated = report.error instanceof ApiError && report.error.status === 404 && explanation.data;
    if (notEvaluated) {
      return (
        <div className="card">
          <EmptyState
            icon={Info}
            title={t.report.notEvaluated}
            action={
              <Link to={`/jobs/${explanation.data?.job_id}`} className="btn btn-primary">
                {t.report.backToJob}
              </Link>
            }
          >
            {t.report.notEvaluatedHint}
          </EmptyState>
        </div>
      );
    }
    return <ErrorState error={report.error} onRetry={report.reload} />;
  }

  const onDecided = (updated: DashboardReport) => {
    report.setData(updated);
    explanation.reload();
  };

  const selectTab = (id: Tab) => {
    const next = new URLSearchParams(params);
    if (id === "overview") next.delete("tab");
    else next.set("tab", id);
    setParams(next, { replace: true });
  };

  return (
    <div className="page">
      <ReportHero report={r} />
      <ReportActions report={r} onLinkCreated={links.reload} />
      <ReportPrintDoc report={r} tests={tests.data ?? []} pilots={pilots.data ?? []} />

      <div className="tabs no-print" role="tablist" aria-label={t.report.tabsLabel}>
        {TABS.map(({ id, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            className="tab"
            onClick={() => selectTab(id)}
            onKeyDown={(e) => {
              const i = TABS.findIndex((x) => x.id === id);
              const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
              if (!d) return;
              const next = TABS[(i + d + TABS.length) % TABS.length];
              if (next) {
                selectTab(next.id);
                document.getElementById(`tab-${next.id}`)?.focus();
              }
            }}
          >
            <Icon size={16} aria-hidden="true" />
            {t.report.tabs[id]}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="stack-lg">
        {tab === "overview" && (
          <>
            <CriteriaMatrix report={r} />
            <VerificationPanel candidateRef={r.candidate_ref} tests={tests} />
            <PilotPanel candidateRef={r.candidate_ref} sessions={pilots} />
            <div className="grid-2" style={{ alignItems: "start" }}>
              <GapsPanel report={r} />
              <DecisionPanel report={r} onDecided={onDecided} />
            </div>
            <CredentialsPanel report={r} />
            <ExplanationLinksPanel candidateRef={r.candidate_ref} links={links} />
            <DangerZone candidateRef={r.candidate_ref} jobId={r.job_id} />
          </>
        )}
        {tab === "proof" && (
          <>
            <ProofPanel report={r} artifacts={artifacts.data} />
            <GraphPanel report={r} graph={graph.data} loading={graph.loading} />
            <ArtifactsPanel artifacts={artifacts.data} />
          </>
        )}
        {tab === "interview" && (
          <>
            <InterviewGuide report={r} />
            <GapsPanel report={r} />
          </>
        )}
        {tab === "audit" && <GlassBox report={r} explanation={explanation.data} loading={explanation.loading} />}
      </div>
      <p className="xs faint">{t.report.generated(dateTime(r.generated_at, lang))}</p>
    </div>
  );
}

// ------------------------------------------------------------------ hero

function ReportHero({ report: r }: { report: DashboardReport }) {
  const { t } = usePrefs();
  const credW = r.credentials.weight_applied;
  return (
    <section className="hero" aria-labelledby="r-title">
      <div className="report-hero">
        <ScoreRing
          value={r.compatibility_pct}
          size={168}
          stroke={12}
          glow
          caption={t.report.compatibility}
          label={`${t.report.compatibility} ${r.compatibility_pct.toFixed(1)} %`}
        />
        <div className="stack" style={{ minWidth: 0, width: "100%" }}>
          <div className="stack-sm" style={{ gap: 6 }}>
            <Link to={`/jobs/${r.job_id}`} className="eyebrow" style={{ color: "var(--text-3)" }}>
              {r.job_title} · {r.job_id}
            </Link>
            <div className="row wrap" style={{ gap: 12 }}>
              <h1 id="r-title" className="report-ref">
                {r.candidate_ref}
              </h1>
              <BandChip band={r.evidence_band} />
              <DecisionChip decision={r.decision?.decision ?? null} />
            </div>
          </div>
          <div className="breakdown">
            <div className="bd-item">
              <span className="eyebrow">{t.report.skills}</span>
              <span className="bd-value">{r.skills_component_pct.toFixed(1)} %</span>
              <span className="xs faint">{t.report.credWeight(`${Math.round((1 - credW) * 100)} %`)}</span>
            </div>
            <div className="bd-item is-secondary">
              <span className="eyebrow">{t.report.credentials}</span>
              <span className="bd-value" style={{ color: "var(--text-2)" }}>
                {r.credentials_component_pct.toFixed(1)} %
              </span>
              <span className="xs faint">{t.report.credWeight(`${Math.round(credW * 100)} %`)}</span>
            </div>
            <div className="bd-item" title={t.report.confidenceHint}>
              <span className="eyebrow">{t.report.confidence}</span>
              <span className="bd-value">{Math.round(r.confidence * 100)} %</span>
              <span className="xs faint">{t.report.confidenceHint}</span>
            </div>
          </div>
          <p className="notice">
            <b className="eyebrow" style={{ display: "block", marginBottom: 2 }}>
              {t.report.aiNotice}
            </b>
            {r.notice}
          </p>
        </div>
      </div>
      {r.warnings.length > 0 && (
        <div className="callout callout-warn" role="note" style={{ marginTop: 20 }}>
          <AlertTriangle size={16} aria-hidden="true" />
          <div>
            <b>{t.report.warnings}</b>
            <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
              {r.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ decision

function DecisionPanel({ report, onDecided }: { report: DashboardReport; onDecided: (r: DashboardReport) => void }) {
  const { t, lang, reviewer: storedReviewer } = usePrefs();
  const toast = useToast();
  const system = useSystem();
  const [decision, setDecision] = useState<DecisionKind>(report.decision?.decision ?? "interview");
  const [reviewer, setReviewer] = useState(storedReviewer);
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const [revealOpen, setRevealOpen] = useState(false);
  const access = useAccess();
  // Named accounts: the server signs with the account name; the field is shown read-only.
  const signer = access.signedName ?? reviewer;

  const valid = signer.trim().length >= 2 && rationale.trim().length >= 15;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (!valid) return;
    setBusy(true);
    try {
      const updated = await api.decide(report.candidate_ref, {
        decision,
        reviewer: signer.trim(),
        rationale: rationale.trim(),
      });
      onDecided(updated);
      setRationale("");
      setTried(false);
      toast.push("success", t.report.recorded, t.decision[decision]);
      system.refresh();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };
  const canReveal = report.decision?.decision === "shortlist" || report.decision?.decision === "interview";

  return (
    <section className="panel" aria-labelledby="r-dec">
      <div>
        <h2 id="r-dec" className="panel-title">
          <Handshake size={18} aria-hidden="true" />
          {t.report.decisionTitle}
        </h2>
        <p className="panel-hint">{t.report.decisionHint}</p>
      </div>

      {report.decision && (
        <div className="ident">
          <span className="eyebrow">{t.report.decisionCurrent}</span>
          <div className="row wrap" style={{ gap: 8 }}>
            <DecisionChip decision={report.decision.decision} />
            <span className="xs muted">
              {t.report.decisionBy(report.decision.reviewer, dateTime(report.decision.decided_at, lang))}
            </span>
          </div>
          <p className="small">{report.decision.rationale}</p>
          {report.decision.ledger_entry_id && (
            <span className="xs faint">
              {t.report.ledgerEntry} <span className="hash">{report.decision.ledger_entry_id}</span>
            </span>
          )}
        </div>
      )}

      <form className="stack" onSubmit={submit} noValidate>
        <div className="field">
          <span className="label">{t.report.decisionLabel}</span>
          <Segmented<DecisionKind>
            label={t.report.decisionLabel}
            value={decision}
            onChange={setDecision}
            options={(["shortlist", "interview", "hold", "not_retained"] as const).map((d) => ({
              value: d,
              label: t.decision[d],
            }))}
          />
        </div>
        <div className="field">
          <label htmlFor="dec-rev">{t.report.reviewer}</label>
          <input
            id="dec-rev"
            className="input"
            value={signer}
            maxLength={120}
            autoComplete="name"
            readOnly={Boolean(access.signedName)}
            aria-describedby={access.signedName ? "dec-rev-h" : undefined}
            aria-invalid={tried && signer.trim().length < 2}
            onChange={(e) => setReviewer(e.target.value)}
          />
          {access.signedName && (
            <p id="dec-rev-h" className="hint">
              {t.ops.signedBy(access.signedName)}
            </p>
          )}
        </div>
        <div className="field">
          <label htmlFor="dec-rat">{t.report.rationale}</label>
          <textarea
            id="dec-rat"
            className="textarea"
            value={rationale}
            maxLength={4000}
            placeholder={t.report.rationalePh}
            aria-invalid={tried && rationale.trim().length < 15}
            aria-describedby="dec-rat-h"
            onChange={(e) => setRationale(e.target.value)}
          />
          <p id="dec-rat-h" className="hint num" style={{ color: rationale.trim().length >= 15 ? "var(--ok-text)" : undefined }}>
            {t.common.chars(rationale.trim().length, 15)}
          </p>
        </div>
        <div className="row wrap">
          <Gate perm="decide">
            {(ok) => (
              <button className="btn btn-primary" type="submit" disabled={busy || !ok}>
                {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Handshake size={16} aria-hidden="true" />}
                {t.report.record}
              </button>
            )}
          </Gate>
          <Gate perm="decide">
            {(ok) => (
              <button
                type="button"
                className="btn"
                disabled={!canReveal || !ok}
                onClick={() => setRevealOpen(true)}
                title={canReveal ? undefined : t.report.revealHint}
                aria-describedby={canReveal ? undefined : "reveal-hint"}
              >
                <Eye size={16} aria-hidden="true" />
                {t.report.reveal}
              </button>
            )}
          </Gate>
        </div>
        {!canReveal && (
          <p id="reveal-hint" className="hint">
            {t.report.revealHint}
          </p>
        )}
      </form>
      {revealOpen && (
        <RevealModal
          candidateRef={report.candidate_ref}
          defaultReviewer={signer}
          locked={Boolean(access.signedName)}
          onClose={() => setRevealOpen(false)}
        />
      )}
    </section>
  );
}

function RevealModal({
  candidateRef,
  defaultReviewer,
  locked,
  onClose,
}: {
  candidateRef: string;
  defaultReviewer: string;
  locked: boolean;
  onClose: () => void;
}) {
  const { t } = usePrefs();
  const toast = useToast();
  const system = useSystem();
  const [reviewer, setReviewer] = useState(defaultReviewer);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RevealResult | null>(null);
  const valid = reviewer.trim().length >= 2 && reason.trim().length >= 15;
  const go = async () => {
    if (!valid) return;
    setBusy(true);
    try {
      setResult(await api.reveal(candidateRef, reviewer.trim(), reason.trim()));
      system.refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const entries = result ? Object.entries(result.identity).filter(([, v]) => v.length) : [];
  return (
    <Modal
      title={result ? t.report.revealed : t.report.revealTitle}
      onClose={onClose}
      footer={
        result ? (
          <button className="btn" onClick={onClose}>
            {t.common.close}
          </button>
        ) : (
          <>
            <button className="btn btn-ghost" onClick={onClose}>
              {t.common.cancel}
            </button>
            <button className="btn btn-primary" onClick={go} disabled={!valid || busy}>
              {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
              {t.report.revealDo}
            </button>
          </>
        )
      }
    >
      <p className="callout callout-warn">
        <ShieldAlert size={16} aria-hidden="true" />
        <span>{t.report.revealWarn}</span>
      </p>
      {result ? (
        entries.length === 0 ? (
          <p className="small muted">{t.report.revealedEmpty}</p>
        ) : (
          <div className="ident" aria-live="polite">
          <dl className="kv">
            {entries.map(([k, v]) => (
              <div key={k} style={{ display: "contents" }}>
                <dt>{t.report.idKinds[k] ?? k}</dt>
                <dd className="mono">{v.join(", ")}</dd>
              </div>
            ))}
          </dl>
          </div>
        )
      ) : (
        <>
          <div className="field">
            <label htmlFor="rv-rev">{t.report.reviewer}</label>
            <input id="rv-rev" className="input" value={reviewer} maxLength={120} readOnly={locked} onChange={(e) => setReviewer(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="rv-reason">{t.report.revealReason}</label>
            <textarea
              id="rv-reason"
              className="textarea"
              value={reason}
              maxLength={2000}
              placeholder={t.report.revealReasonPh}
              onChange={(e) => setReason(e.target.value)}
            />
            <p className="hint num">{t.common.chars(reason.trim().length, 15)}</p>
          </div>
        </>
      )}
    </Modal>
  );
}

// ------------------------------------------------------------------ danger zone

function DangerZone({ candidateRef, jobId }: { candidateRef: string; jobId: string }) {
  const { t, reviewer } = usePrefs();
  const toast = useToast();
  const system = useSystem();
  const navigate = useNavigate();
  const access = useAccess();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const erase = async () => {
    if (typed.trim() !== candidateRef) return;
    setBusy(true);
    try {
      // the server signs with the account name for named accounts; the actor is only used otherwise
      const r = await api.erase(candidateRef, access.signedName ?? (reviewer.trim().length >= 2 ? reviewer.trim() : "recruiter"));
      toast.push("success", t.report.erased(r.vault_entries_shredded, r.artifacts_deleted), candidateRef);
      system.refresh();
      navigate(`/jobs/${jobId}`);
    } catch (e) {
      toast.error(e);
      setBusy(false);
    }
  };
  return (
    <section className="panel is-danger no-print" aria-labelledby="r-danger">
      <div className="panel-head">
        <div>
          <h2 id="r-danger" className="panel-title" style={{ fontSize: 15 }}>
            <Trash2 size={16} aria-hidden="true" style={{ color: "var(--danger-text)" }} />
            {t.report.danger}
          </h2>
          <p className="panel-hint">{t.report.eraseHint}</p>
        </div>
        <Gate perm="privacy">
          {(ok) => (
            <button className="btn btn-danger" onClick={() => setOpen(true)} disabled={!ok}>
              <Trash2 size={16} aria-hidden="true" />
              {t.report.erase}
            </button>
          )}
        </Gate>
      </div>
      {open && (
        <Modal
          title={t.report.eraseConfirmTitle}
          onClose={() => {
            setOpen(false);
            setTyped("");
          }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setOpen(false)}>
                {t.common.cancel}
              </button>
              <button className="btn btn-danger is-solid" disabled={typed.trim() !== candidateRef || busy} onClick={erase}>
                {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}
                {t.report.eraseDo}
              </button>
            </>
          }
        >
          <p className="small">{t.report.eraseHint}</p>
          <div className="field">
            <label htmlFor="erase-confirm">{t.report.eraseConfirmBody(candidateRef)}</label>
            <input
              id="erase-confirm"
              className="input mono"
              value={typed}
              autoComplete="off"
              spellCheck={false}
              placeholder={candidateRef}
              onChange={(e) => setTyped(e.target.value)}
            />
          </div>
        </Modal>
      )}
    </section>
  );
}

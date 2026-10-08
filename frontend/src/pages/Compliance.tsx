// /compliance — deployer monitoring (AI Act Art. 26/72-73): results per role, human oversight, tests, incidents.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { AlertOctagon, BookOpen, Coins, Gavel, Link2, Link2Off, Loader2, ScaleIcon, ShieldAlert, ShieldCheck, Timer, Users } from "lucide-react";
import { api } from "../api/client";
import type { IncidentResult, IncidentSeverity } from "../api/types";
import { useAccess, useAsync, usePrefs, useToast } from "../lib/prefs";
import { cx, dateTime, shortHash, usd } from "../lib/format";
import { PageHeader, useCrumbs } from "../components/Shell";
import { EmptyState, ErrorState, Skeleton } from "../components/feedback";
import { REPO_URL } from "../components/PublicLayout";

export function CompliancePage() {
  const { t, lang } = usePrefs();
  const c = t.compliance;
  const access = useAccess();
  const allowed = access.can("privacy");
  const mon = useAsync(() => (allowed ? api.monitoring() : Promise.resolve(null)), [allowed]);
  useCrumbs([{ label: c.nav }]);

  if (access.mode === "loading") return <Skeleton h={300} r={14} />;
  if (!allowed) {
    return (
      <div className="card">
        <EmptyState icon={ShieldAlert} title={c.title}>
          {c.reserved}
        </EmptyState>
      </div>
    );
  }
  const m = mon.data;
  const bandsTotal = m ? Object.values(m.evidence_bands).reduce((a, b) => a + (b ?? 0), 0) : 0;
  const riskTotal = m ? Object.values(m.test_integrity_risk).reduce((a, b) => a + (b ?? 0), 0) : 0;

  return (
    <div className="page">
      <section className="hero">
        <PageHeader title={c.title} sub={c.subtitle} eyebrow={m ? c.generated(dateTime(m.generated_at, lang)) : undefined} />
      </section>
      {mon.loading && !m ? (
        <Skeleton h={320} r={14} />
      ) : mon.error ? (
        <ErrorState error={mon.error} onRetry={mon.reload} />
      ) : m ? (
        <>
          <div className="kpi-grid">
            <Kpi icon={Gavel} label={c.decisions} value={String(m.human_decisions)} />
            <Kpi icon={Users} label={c.departing} value={String(m.decisions_departing_from_ranking)} tone="violet" />
            <Kpi icon={Timer} label={c.testsDone} value={String(m.verification_tests_completed)} />
            <Kpi icon={Coins} label={c.spend} value={usd(m.ai_spend_usd, lang)} />
            <Kpi icon={AlertOctagon} label={c.incidents} value={String(m.incidents_recorded)} tone={m.incidents_recorded ? "warn" : undefined} />
            <Kpi
              icon={m.ledger.valid ? Link2 : Link2Off}
              label={c.ledger}
              value={m.ledger.valid ? t.status.ledgerValid(m.ledger.length) : t.status.ledgerBroken(m.ledger.first_invalid_seq)}
              tone={m.ledger.valid ? "ok" : "danger"}
              small
            />
          </div>

          <div className="grid-2" style={{ alignItems: "start" }}>
            <section className="panel" aria-labelledby="c-oversight">
              <h2 id="c-oversight" className="panel-title">
                <Gavel size={18} aria-hidden="true" />
                {c.oversight}
              </h2>
              <dl className="kv">
                <dt>{c.decisions}</dt>
                <dd className="num">{m.human_decisions}</dd>
                <dt>{c.departing}</dt>
                <dd className="num">{m.decisions_departing_from_ranking}</dd>
              </dl>
              <p className="callout callout-neutral small">
                <ShieldCheck size={16} aria-hidden="true" />
                <span>{c.departingHint}</span>
              </p>
            </section>
            <section className="panel" aria-labelledby="c-dist">
              <h2 id="c-dist" className="panel-title">
                <ScaleIcon size={18} aria-hidden="true" />
                {c.bands}
              </h2>
              <StackBar
                parts={(["strong", "moderate", "limited"] as const).map((b) => ({ label: t.band[b], n: m.evidence_bands[b] ?? 0, tone: b }))}
                total={bandsTotal}
              />
              <h3 className="label" style={{ marginTop: 8 }}>
                {c.riskDist} · {c.tests} ({riskTotal})
              </h3>
              <StackBar
                parts={(["low", "medium", "high"] as const).map((r) => ({ label: t.test.risk[r] ?? r, n: m.test_integrity_risk[r] ?? 0, tone: r }))}
                total={riskTotal}
              />
            </section>
          </div>

          <section className="panel" aria-labelledby="c-jobs">
            <h2 id="c-jobs" className="panel-title">
              <Users size={18} aria-hidden="true" />
              {c.jobs}
            </h2>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{c.colJob}</th>
                    <th scope="col">{c.colCandidates}</th>
                    <th scope="col">{c.colDecisions}</th>
                    <th scope="col">{c.colRange}</th>
                  </tr>
                </thead>
                <tbody>
                  {m.jobs.map((j) => (
                    <tr key={j.job_id}>
                      <td>
                        <Link to={`/jobs/${j.job_id}`}>{j.title}</Link>
                        <div className="xs faint mono">{j.job_id}</div>
                      </td>
                      <td className="num">{j.candidates}</td>
                      <td className="num">{j.decisions}</td>
                      <td style={{ minWidth: 220 }}>
                        <RangeBar min={j.score_min} median={j.score_median} max={j.score_max} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}

      <div className="grid-2" style={{ alignItems: "start" }}>
        <IncidentForm />
        <section className="panel is-secondary" aria-labelledby="c-docs">
          <h2 id="c-docs" className="panel-title">
            <BookOpen size={16} aria-hidden="true" />
            {c.docs}
          </h2>
          <ul className="doc-links">
            {c.docLinks.map((d) => (
              <li key={d.path}>
                <a href={`${REPO_URL}/blob/main/${d.path}`} target="_blank" rel="noreferrer">
                  {d.label}
                </a>
                <span className="xs faint mono"> {d.path}</span>
              </li>
            ))}
          </ul>
          {m && (
            <p className="xs faint">
              {t.audit.head} <span className="hash">{shortHash(m.ledger.head_hash, 16)}</span>
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
  small,
}: {
  icon: typeof Gavel;
  label: string;
  value: string;
  tone?: "ok" | "warn" | "danger" | "violet";
  small?: boolean;
}) {
  return (
    <div className={cx("kpi", tone && `kpi-${tone}`)}>
      <Icon size={18} aria-hidden="true" />
      <span className={cx("kpi-v", small && "small")}>{value}</span>
      <span className="kpi-l">{label}</span>
    </div>
  );
}

function StackBar({ parts, total }: { parts: { label: string; n: number; tone: string }[]; total: number }) {
  return (
    <div className="stackbar-wrap">
      <div className="stackbar" role="img" aria-label={parts.map((p) => `${p.label}: ${p.n}`).join(", ")}>
        {total === 0 ? <span className="sb-empty" /> : parts.filter((p) => p.n > 0).map((p) => <span key={p.label} className={`sb sb-${p.tone}`} style={{ flex: p.n }} />)}
      </div>
      <ul className="sb-legend">
        {parts.map((p) => (
          <li key={p.label}>
            <i className={`sb-${p.tone}`} aria-hidden="true" />
            {p.label} <b className="num">{p.n}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RangeBar({ min, median, max }: { min: number | null; median: number | null; max: number | null }) {
  if (min === null || max === null) return <span className="faint">—</span>;
  return (
    <div className="rangebar" role="img" aria-label={`${min} · ${median ?? "—"} · ${max}`}>
      <div className="rb-track">
        <span className="rb-span" style={{ left: `${min}%`, width: `${Math.max(1, max - min)}%` }} />
        {median !== null && <span className="rb-med" style={{ left: `${median}%` }} />}
      </div>
      <span className="xs num muted">
        {min.toFixed(0)} · <b>{median?.toFixed(0) ?? "—"}</b> · {max.toFixed(0)} %
      </span>
    </div>
  );
}

function IncidentForm() {
  const { t, lang } = usePrefs();
  const c = t.compliance;
  const toast = useToast();
  const [severity, setSeverity] = useState<IncidentSeverity>("serious");
  const [desc, setDesc] = useState("");
  const [affected, setAffected] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IncidentResult | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (desc.trim().length < 20) return;
    setBusy(true);
    try {
      const refs = affected
        .split(/[\s,;]+/)
        .map((x) => x.trim().toUpperCase())
        .filter(Boolean);
      const r = await api.incident({ severity, description: desc.trim(), affected_candidates: refs });
      setResult(r);
      setDesc("");
      setAffected("");
      toast.push("success", c.reported(dateTime(r.report_to_authority_before, lang)));
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="panel" aria-labelledby="c-inc" onSubmit={submit}>
      <div>
        <h2 id="c-inc" className="panel-title">
          <AlertOctagon size={18} aria-hidden="true" />
          {c.incidentTitle}
        </h2>
        <p className="panel-hint">{c.incidentHint}</p>
      </div>
      <div className="field">
        <label htmlFor="inc-sev">{c.severity}</label>
        <select id="inc-sev" className="select" value={severity} onChange={(e) => setSeverity(e.target.value as IncidentSeverity)}>
          {(["serious", "widespread", "death"] as const).map((s) => (
            <option key={s} value={s}>
              {c.severities[s]}
            </option>
          ))}
        </select>
        <p className="hint">{c.deadlineHint(c.deadlines[severity] ?? "")}</p>
      </div>
      <div className="field">
        <label htmlFor="inc-desc">{c.description}</label>
        <textarea id="inc-desc" className="textarea" maxLength={4000} value={desc} onChange={(e) => setDesc(e.target.value)} aria-describedby="inc-desc-h" />
        <p id="inc-desc-h" className="hint num">
          {t.common.chars(desc.trim().length, 20)}
        </p>
      </div>
      <div className="field">
        <label htmlFor="inc-aff">{c.affected}</label>
        <textarea id="inc-aff" className="textarea mono" style={{ minHeight: 60, fontFamily: "var(--font-mono)" }} value={affected} placeholder="CAND-…" onChange={(e) => setAffected(e.target.value)} />
      </div>
      {result && (
        <p className="callout callout-warn" role="status">
          <AlertOctagon size={16} aria-hidden="true" />
          <span>
            <b>{c.reported(dateTime(result.report_to_authority_before, lang))}</b> <span className="hash">{result.entry_id}</span>
          </span>
        </p>
      )}
      <div>
        <button className="btn btn-danger is-solid" type="submit" disabled={busy || desc.trim().length < 20}>
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <AlertOctagon size={16} aria-hidden="true" />}
          {c.report}
        </button>
      </div>
    </form>
  );
}

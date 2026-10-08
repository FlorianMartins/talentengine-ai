import { Fragment, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Eraser, Link2, Link2Off, Loader2, RotateCcw, ScrollText, Search, ShieldCheck } from "lucide-react";
import { api } from "../api/client";
import type { ChainVerification, LedgerQuery, RetentionRun } from "../api/types";
import { useAccess, useAsync, usePrefs, useSystem, useToast } from "../lib/prefs";
import { cx, dateTime, shortHash } from "../lib/format";
import { PageHeader, useCrumbs } from "../components/Shell";
import { EmptyState, ErrorState, Modal, Skeleton } from "../components/feedback";

const KINDS = [
  "job_config",
  "ingestion",
  "score",
  "escalation",
  "human_decision",
  "reidentification",
  "erasure",
  "data_export",
  "explanation_link",
  "explanation_viewed",
  "retention_sweep",
  "account_created",
  "account_removed",
];

/** Chip tone per ledger kind: violet = human/identity acts, red = deletions, cyan = scoring, green = privacy ops. */
function kindTone(kind: string): string {
  if (["human_decision", "reidentification", "explanation_link", "explanation_viewed"].includes(kind)) return "chip-violet";
  if (["erasure", "account_removed"].includes(kind)) return "chip-danger";
  if (["data_export", "retention_sweep", "account_created"].includes(kind)) return "chip-ok";
  if (kind === "score") return "chip-accent";
  return "chip-plain";
}

export function AuditPage() {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const system = useSystem();
  useCrumbs([{ label: t.nav.audit }]);

  const [limit, setLimit] = useState(25);
  const [page, setPage] = useState(0);
  const [candidate, setCandidate] = useState("");
  const [jobId, setJobId] = useState("");
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState<LedgerQuery>({});
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [verifying, setVerifying] = useState(false);
  const [verification, setVerification] = useState<ChainVerification | null>(null);
  const access = useAccess();
  const [purgeOpen, setPurgeOpen] = useState(false);
  const [purging, setPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState<RetentionRun | null>(null);
  const purge = async () => {
    setPurging(true);
    try {
      const r = await api.retentionRun();
      setPurgeResult(r);
      setPurgeOpen(false);
      toast.push("success", t.ops.purgeDone(r.count), t.ops.purge);
      ledger.reload();
      system.refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setPurging(false);
    }
  };

  const jobs = useAsync(() => api.jobs(), []);
  // Fetch one extra row to know whether a next page exists (the API returns no total).
  const ledger = useAsync(
    () => api.ledger({ ...query, limit: limit + 1, offset: page * limit }),
    [JSON.stringify(query), limit, page],
  );
  const rows = (ledger.data ?? []).slice(0, limit).filter((e) => !kind || e.kind === kind);
  const hasNext = (ledger.data?.length ?? 0) > limit;
  const chain = verification ?? system.chain;

  const applyFilters = (e?: FormEvent) => {
    e?.preventDefault();
    setPage(0);
    setQuery({ candidate_ref: candidate.trim().toUpperCase() || undefined, job_id: jobId || undefined });
  };
  const reset = () => {
    setCandidate("");
    setJobId("");
    setKind("");
    setPage(0);
    setQuery({});
  };
  const verify = async () => {
    setVerifying(true);
    try {
      setVerification(await api.verify());
      system.refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="page">
      <section className="hero">
        <PageHeader
          title={t.audit.title}
          sub={t.audit.subtitle}
          actions={
            <>
            {(access.can("privacy")) && (
              <button className="btn" onClick={() => setPurgeOpen(true)} title={t.ops.purgeHint}>
                <Eraser size={16} aria-hidden="true" />
                {t.ops.purge}
              </button>
            )}
            <button className="btn btn-primary" onClick={verify} disabled={verifying}>
              {verifying ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <ShieldCheck size={16} aria-hidden="true" />}
              {verifying ? t.audit.verifying : t.audit.verify}
            </button>
            </>
          }
        />
        {purgeResult && (
          <p className="callout callout-ok" role="status" style={{ marginTop: 20 }}>
            <Eraser size={16} aria-hidden="true" />
            <span>
              <b>{t.ops.purgeDone(purgeResult.count)}</b>
              {purgeResult.erased.length > 0 && <span className="mono xs"> {purgeResult.erased.join(", ")}</span>}
            </span>
          </p>
        )}
        {chain && (
          <div
            className={cx("callout", chain.valid ? "callout-ok" : "callout-danger")}
            role="status"
            aria-live="polite"
            style={{ marginTop: 20, flexWrap: "wrap" }}
          >
            {chain.valid ? <Link2 size={16} aria-hidden="true" /> : <Link2Off size={16} aria-hidden="true" />}
            <span style={{ flex: "1 1 260px" }}>
              <b>{chain.valid ? t.audit.valid(chain.length) : t.audit.broken(chain.first_invalid_seq, chain.reason)}</b>
            </span>
            <span className="xs muted">
              {t.audit.head}{" "}
              <span className="hash" title={chain.head_hash}>
                {shortHash(chain.head_hash, 16)}
              </span>
            </span>
          </div>
        )}
      </section>

      <form className="panel" onSubmit={applyFilters} aria-label={t.pipeline.filters} style={{ padding: 20 }}>
        <div className="row wrap" style={{ alignItems: "flex-end", gap: 12 }}>
          <div className="field" style={{ flex: "1 1 180px" }}>
            <label htmlFor="a-cand">{t.audit.filterCandidate}</label>
            <div className="input-icon">
              <Search size={16} aria-hidden="true" />
              <input
                id="a-cand"
                className="input mono"
                placeholder="CAND-…"
                value={candidate}
                onChange={(e) => setCandidate(e.target.value)}
              />
            </div>
          </div>
          <div className="field" style={{ flex: "1 1 200px" }}>
            <label htmlFor="a-job">{t.audit.filterJob}</label>
            <select id="a-job" className="select" value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">{t.audit.allJobs}</option>
              {(jobs.data ?? []).map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} · {j.id}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 160px" }}>
            <label htmlFor="a-kind">{t.audit.kind}</label>
            <select id="a-kind" className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">{t.audit.allKinds}</option>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {t.audit.kinds[k]}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "0 0 96px" }}>
            <label htmlFor="a-limit">{t.audit.perPage}</label>
            <select
              id="a-limit"
              className="select"
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setPage(0);
              }}
            >
              {[25, 50, 100].map((n) => (
                <option key={n}>{n}</option>
              ))}
            </select>
          </div>
          <div className="row" style={{ gap: 6 }}>
            <button className="btn" type="submit">
              <Search size={16} aria-hidden="true" />
              {t.audit.apply}
            </button>
            <button className="btn btn-ghost" type="button" onClick={reset}>
              <RotateCcw size={16} aria-hidden="true" />
              {t.audit.reset}
            </button>
          </div>
        </div>
      </form>

      {ledger.loading && !ledger.data ? (
        <Skeleton h={360} r={12} />
      ) : ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : rows.length === 0 ? (
        <div className="card">
          <EmptyState icon={ScrollText} title={t.audit.empty} />
        </div>
      ) : (
        <div className="table-wrap card" style={{ boxShadow: "none" }}>
          <table className="table">
            <caption className="sr-only">{t.audit.title}</caption>
            <thead>
              <tr>
                <th scope="col">{t.audit.seq}</th>
                <th scope="col">{t.audit.kind}</th>
                <th scope="col">{t.audit.subject}</th>
                <th scope="col">{t.audit.actor}</th>
                <th scope="col">{t.audit.time}</th>
                <th scope="col">{t.audit.chain}</th>
                <th scope="col">
                  <span className="sr-only">{t.audit.expand}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const expanded = Boolean(open[e.seq]);
                const broken = chain && !chain.valid && chain.first_invalid_seq === e.seq;
                return (
                  <Fragment key={e.seq}>
                    <tr style={broken ? { background: "var(--danger-soft)" } : undefined}>
                      <td className="num">{e.seq}</td>
                      <td>
                        <span className={cx("chip", kindTone(e.kind))}>
                          <span>{t.audit.kinds[e.kind] ?? e.kind}</span>
                        </span>
                      </td>
                      <td className="xs" style={{ whiteSpace: "nowrap" }}>
                        {e.candidate_ref ? (
                          <Link to={`/candidates/${e.candidate_ref}`} className="mono">
                            {e.candidate_ref}
                          </Link>
                        ) : e.job_id ? (
                          <Link to={`/jobs/${e.job_id}`} className="mono">
                            {e.job_id}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="small">{e.actor}</td>
                      <td className="xs muted" style={{ whiteSpace: "nowrap" }}>
                        {dateTime(e.created_at, lang)}
                      </td>
                      <td>
                        <span className="chain-cell">
                          <span className="hash" title={e.prev_hash}>
                            {shortHash(e.prev_hash, 8)}
                          </span>
                          <ChevronRight size={12} aria-hidden="true" />
                          <span className="hash" title={e.entry_hash} style={{ color: "var(--accent-text)" }}>
                            {shortHash(e.entry_hash, 8)}
                          </span>
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost btn-icon btn-sm"
                          aria-expanded={expanded}
                          aria-label={`${expanded ? t.audit.collapse : t.audit.expand} #${e.seq}`}
                          onClick={() => setOpen({ ...open, [e.seq]: !expanded })}
                        >
                          <ChevronRight
                            size={16}
                            aria-hidden="true"
                            style={{ transform: expanded ? "rotate(90deg)" : undefined, transition: "transform .2s" }}
                          />
                        </button>
                      </td>
                    </tr>
                    {expanded && (
                      <tr>
                        <td colSpan={7} style={{ background: "var(--bg-elev)" }}>
                          <div className="stack-sm">
                            <span className="xs faint mono">
                              {e.entry_id} · seal {shortHash(e.seal, 16)}
                            </span>
                            <pre className="code">{JSON.stringify(e.payload, null, 2)}</pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {purgeOpen && (
        <Modal
          title={t.ops.purge}
          onClose={() => setPurgeOpen(false)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setPurgeOpen(false)}>
                {t.common.cancel}
              </button>
              <button className="btn btn-danger is-solid" onClick={purge} disabled={purging}>
                {purging ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Eraser size={16} aria-hidden="true" />}
                {t.ops.purgeDo}
              </button>
            </>
          }
        >
          <p className="small">{t.ops.purgeHint}</p>
          <p className="callout callout-warn">
            <Eraser size={16} aria-hidden="true" />
            <span>{t.ops.purgeConfirm}</span>
          </p>
        </Modal>
      )}

      <nav className="row" style={{ justifyContent: "space-between" }} aria-label="Pagination">
        <button className="btn btn-sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
          <ChevronLeft size={14} aria-hidden="true" />
          {t.audit.prev}
        </button>
        <span className="small muted num">{t.audit.page(page + 1)}</span>
        <button className="btn btn-sm" disabled={!hasNext} onClick={() => setPage(page + 1)}>
          {t.audit.next}
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
}

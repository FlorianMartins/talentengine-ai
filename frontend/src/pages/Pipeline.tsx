import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ChevronRight,
  Columns3,
  Cpu,
  FileStack,
  Filter,
  Loader2,
  Play,
  Settings2,
  ShieldCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { api } from "../api/client";
import type { CandidateSummary, DashboardReport, DecisionKind, EvidenceBand } from "../api/types";
import { useAsync, usePrefs, useSystem, useToast } from "../lib/prefs";
import { cx, dateTime, num, usd } from "../lib/format";
import { PageHeader, useCrumbs } from "../components/Shell";
import {
  BandChip,
  DecisionChip,
  EmptyState,
  ErrorState,
  EscalatedChip,
  FamilyIcon,
  ImportanceChip,
  Modal,
  PageSkeleton,
  Skeleton,
  StatusChip,
} from "../components/feedback";
import { Meter, ScoreRing } from "../components/charts";
import { RangeField } from "../components/controls";

type BandFilter = "all" | EvidenceBand | "pending";
type DecisionFilter = "all" | "undecided" | DecisionKind;
type SortKey = "score" | "confidence" | "evidence" | "recent";

export function PipelinePage() {
  const { id = "" } = useParams();
  const { t, lang } = usePrefs();
  const toast = useToast();
  const system = useSystem();
  const job = useAsync(() => api.job(id), [id]);
  const cands = useAsync(() => api.candidates(id), [id]);
  const usage = useAsync(() => api.usage(id), [id]);
  const [running, setRunning] = useState(false);
  const [band, setBand] = useState<BandFilter>("all");
  const [decision, setDecision] = useState<DecisionFilter>("all");
  const [minScore, setMinScore] = useState(0);
  const [sort, setSort] = useState<SortKey>("score");
  const [compareMode, setCompareMode] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const [wideScreen] = useState(() => typeof window === "undefined" || window.matchMedia("(min-width: 1101px)").matches);

  useCrumbs([{ label: t.nav.overview, to: "/" }, { label: job.data?.title ?? "…" }]);

  const run = async () => {
    setRunning(true);
    try {
      const r = await api.evaluate(id);
      toast.push("success", t.pipeline.ran(r.evaluated, r.escalated.length, usd(r.spent_usd, lang)), t.pipeline.run);
      const reasons = [...new Set(Object.values(r.escalation_skipped))];
      if (reasons.length) {
        toast.push("info", t.pipeline.ranSkipped(Object.keys(r.escalation_skipped).length, reasons.join(" ; ")));
      }
      cands.reload();
      usage.reload();
      system.refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setRunning(false);
    }
  };

  const all = cands.data ?? [];
  const visible = useMemo(() => {
    const list = all.filter((c) => {
      if (band === "pending" && c.compatibility_pct !== null) return false;
      if (band !== "all" && band !== "pending" && c.evidence_band !== band) return false;
      if (decision === "undecided" && c.decision) return false;
      if (decision !== "all" && decision !== "undecided" && c.decision !== decision) return false;
      if (minScore > 0 && (c.compatibility_pct ?? 0) < minScore) return false;
      return true;
    });
    const by: Record<SortKey, (a: CandidateSummary, b: CandidateSummary) => number> = {
      score: (a, b) => (b.compatibility_pct ?? -1) - (a.compatibility_pct ?? -1),
      confidence: (a, b) => (b.confidence ?? -1) - (a.confidence ?? -1),
      evidence: (a, b) => b.evidence_count - a.evidence_count,
      recent: (a, b) => b.created_at.localeCompare(a.created_at),
    };
    return [...list].sort(by[sort]);
  }, [all, band, decision, minScore, sort]);
  const rankOf = useMemo(() => new Map(all.map((c, i) => [c.candidate_ref, i + 1])), [all]);
  const pending = all.filter((c) => c.compatibility_pct === null).length;

  const toggleSelect = (ref: string) =>
    setSelected((s) => (s.includes(ref) ? s.filter((x) => x !== ref) : s.length >= 3 ? s : [...s, ref]));

  if (job.loading && !job.data) return <PageSkeleton />;
  if (job.error) return <ErrorState error={job.error} onRetry={job.reload} />;
  const j = job.data;
  if (!j) return null;

  return (
    <div className="page">
      <section className="hero">
        <PageHeader
          eyebrow={
            <span className="row" style={{ gap: 8 }}>
              <span>{j.id}</span>
              <span className="hash">{t.common.version(j.version)}</span>
            </span>
          }
          title={
            <span className="row" style={{ gap: 12, alignItems: "center" }}>
              <FamilyIcon family={j.family} />
              <span style={{ minWidth: 0 }}>{j.title}</span>
            </span>
          }
          sub={j.summary || undefined}
          actions={
            <>
              <Link to={`/jobs/${id}/edit`} className="btn">
                <Settings2 size={16} aria-hidden="true" />
                {t.pipeline.edit}
              </Link>
              <Link to={`/jobs/${id}/apply`} className="btn">
                <UserPlus size={16} aria-hidden="true" />
                {t.pipeline.add}
              </Link>
              <button className="btn btn-primary" onClick={run} disabled={running || all.length === 0}>
                {running ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
                {running ? t.pipeline.running : t.pipeline.run}
              </button>
            </>
          }
        />
        <p className="callout callout-ok" style={{ marginTop: 20 }}>
          <ShieldCheck size={16} aria-hidden="true" />
          <span>{t.pipeline.noRejection}</span>
        </p>
      </section>

      <div className="pipe-layout">
        <div className="stack" style={{ minWidth: 0 }}>
          {pending > 0 && (
            <p className="callout callout-warn">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{t.pipeline.pendingHint(pending)}</span>
            </p>
          )}
          <div className="row wrap" style={{ justifyContent: "space-between" }}>
            <span className="small muted" role="status">
              {t.pipeline.showing(visible.length, all.length)}
              {all.length - visible.length > 0 && <> — {t.pipeline.hidden(all.length - visible.length)}</>}
            </span>
            <button
              className={cx("btn btn-sm", compareMode && "btn-primary")}
              aria-pressed={compareMode}
              onClick={() => {
                setCompareMode(!compareMode);
                setSelected([]);
              }}
              disabled={all.filter((c) => c.compatibility_pct !== null).length < 2}
            >
              <Columns3 size={14} aria-hidden="true" />
              {t.pipeline.compareMode}
            </button>
          </div>

          {cands.loading && !cands.data ? (
            <div className="stack">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} h={92} r={14} />
              ))}
            </div>
          ) : cands.error ? (
            <ErrorState error={cands.error} onRetry={cands.reload} />
          ) : all.length === 0 ? (
            <div className="card">
              <EmptyState
                icon={Users}
                title={t.pipeline.emptyTitle}
                action={
                  <Link to={`/jobs/${id}/apply`} className="btn btn-primary">
                    <UserPlus size={16} aria-hidden="true" />
                    {t.pipeline.add}
                  </Link>
                }
              >
                {t.pipeline.emptyBody}
              </EmptyState>
            </div>
          ) : visible.length === 0 ? (
            <div className="card">
              <EmptyState icon={Filter} title={t.pipeline.noneMatch} />
            </div>
          ) : (
            <ol className="cand-list" aria-label={t.pipeline.rank}>
              {visible.map((c) => (
                <CandidateRow
                  key={c.candidate_ref}
                  c={c}
                  rank={rankOf.get(c.candidate_ref) ?? 0}
                  compareMode={compareMode}
                  selected={selected.includes(c.candidate_ref)}
                  onToggle={() => toggleSelect(c.candidate_ref)}
                />
              ))}
            </ol>
          )}

          {compareMode && (
            <div className="compare-bar" role="region" aria-label={t.pipeline.compareMode}>
              <Columns3 size={18} aria-hidden="true" style={{ color: "var(--violet-text)" }} />
              <span className="small" style={{ flex: 1, minWidth: 160 }}>
                {selected.length ? selected.join(" · ") : t.pipeline.compareHint}
              </span>
              <button className="btn btn-primary btn-sm" disabled={selected.length < 2} onClick={() => setComparing(true)}>
                {t.pipeline.compareOpen(selected.length)}
              </button>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                aria-label={t.common.close}
                onClick={() => {
                  setCompareMode(false);
                  setSelected([]);
                }}
              >
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          )}
        </div>

        <aside className="pipe-side" aria-label={t.pipeline.filters}>
          <details className="panel filters-panel" open={wideScreen} style={{ padding: 20 }}>
            <summary className="panel-title" style={{ fontSize: 15 }}>
              <Filter size={16} aria-hidden="true" />
              {t.pipeline.filters}
              {(band !== "all" || decision !== "all" || minScore > 0) && (
                <span className="chip chip-accent" style={{ marginLeft: "auto" }}>
                  <span>{t.pipeline.showing(visible.length, all.length)}</span>
                </span>
              )}
            </summary>
            <div className="filter-grid" style={{ marginTop: 16 }}>
              <div className="field">
                <label htmlFor="f-band">{t.pipeline.band}</label>
                <select id="f-band" className="select" value={band} onChange={(e) => setBand(e.target.value as BandFilter)}>
                  <option value="all">{t.pipeline.all}</option>
                  <option value="strong">{t.band.strong}</option>
                  <option value="moderate">{t.band.moderate}</option>
                  <option value="limited">{t.band.limited}</option>
                  <option value="pending">{t.band.pending}</option>
                </select>
                <p className="hint">{t.band.hint}</p>
              </div>
              <div className="field">
                <label htmlFor="f-dec">{t.pipeline.decisionFilter}</label>
                <select
                  id="f-dec"
                  className="select"
                  value={decision}
                  onChange={(e) => setDecision(e.target.value as DecisionFilter)}
                >
                  <option value="all">{t.pipeline.all}</option>
                  <option value="undecided">{t.pipeline.undecided}</option>
                  {(["shortlist", "interview", "hold", "not_retained"] as const).map((d) => (
                    <option key={d} value={d}>
                      {t.decision[d]}
                    </option>
                  ))}
                </select>
              </div>
              <RangeField
                label={t.pipeline.minScore}
                value={minScore}
                min={0}
                max={100}
                step={5}
                format={(v) => `≥ ${v} %`}
                onChange={setMinScore}
                hint={t.pipeline.minScoreHint}
              />
              <div className="field">
                <label htmlFor="f-sort">{t.pipeline.sort}</label>
                <select id="f-sort" className="select" value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
                  <option value="score">{t.pipeline.sortScore}</option>
                  <option value="confidence">{t.pipeline.sortConfidence}</option>
                  <option value="evidence">{t.pipeline.sortEvidence}</option>
                  <option value="recent">{t.pipeline.sortRecent}</option>
                </select>
              </div>
            </div>
          </details>

          <section className="panel" aria-labelledby="use-h" style={{ padding: 20 }}>
            <h2 id="use-h" className="panel-title" style={{ fontSize: 15 }}>
              <Cpu size={16} aria-hidden="true" />
              {t.pipeline.usage}
            </h2>
            {usage.data ? (
              usage.data.calls === 0 && usage.data.usd === 0 && !j.funnel.allow_cloud_llm ? (
                <p className="small muted">{t.pipeline.usageLocal}</p>
              ) : (
                <div className="stack-sm">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <span className="num small">
                      {t.pipeline.usageOf(usd(usage.data.usd, lang), usd(usage.data.budget_usd, lang))}
                    </span>
                  </div>
                  <Meter
                    value={usage.data.usd}
                    max={Math.max(usage.data.budget_usd, 0.0001)}
                    label={t.pipeline.usage}
                    color={usage.data.usd > usage.data.budget_usd * 0.9 ? "var(--warn)" : undefined}
                  />
                  <p className="xs faint">
                    {t.pipeline.calls(usage.data.calls)} ·{" "}
                    {num(usage.data.input_tokens + usage.data.output_tokens, lang, 0)} {t.pipeline.tokens}
                    {usage.data.provider !== "none" && ` · ${usage.data.provider}${usage.data.model ? ` / ${usage.data.model}` : ""}`}
                  </p>
                </div>
              )
            ) : usage.error ? (
              <p className="small muted">—</p>
            ) : (
              <Skeleton h={40} />
            )}
          </section>
        </aside>
      </div>

      {comparing && <CompareModal refs={selected} onClose={() => setComparing(false)} />}
    </div>
  );
}

function CandidateRow({
  c,
  rank,
  compareMode,
  selected,
  onToggle,
}: {
  c: CandidateSummary;
  rank: number;
  compareMode: boolean;
  selected: boolean;
  onToggle: () => void;
}) {
  const { t, lang } = usePrefs();
  const evaluated = c.compatibility_pct !== null;
  return (
    <li className={cx("card cand", selected && "is-selected")}>
      {compareMode && evaluated ? (
        <label className="check cand-select">
          <input type="checkbox" checked={selected} onChange={onToggle} aria-label={t.pipeline.compareSelect(c.candidate_ref)} />
        </label>
      ) : (
        <span className="cand-rank" aria-label={`${t.pipeline.rank} ${rank}`}>
          #{rank}
        </span>
      )}
      <ScoreRing value={c.compatibility_pct} size={58} />
      <div className="cand-main">
        <div className="row wrap" style={{ gap: 10 }}>
          <Link to={`/candidates/${c.candidate_ref}`} className="cand-ref" aria-label={t.pipeline.openReport(c.candidate_ref)}>
            {c.candidate_ref}
          </Link>
          <BandChip band={c.evidence_band} />
          {c.escalated && <EscalatedChip />}
          {c.warnings > 0 && (
            <span className="chip chip-warn">
              <AlertTriangle size={12} aria-hidden="true" />
              <span>{t.pipeline.warnings(c.warnings)}</span>
            </span>
          )}
        </div>
        <div className="cand-meta">
          {evaluated ? (
            <>
              <span>
                {t.pipeline.confidence} <b className="num">{Math.round((c.confidence ?? 0) * 100)} %</b>
              </span>
              <span className="sep" aria-hidden="true">
                ·
              </span>
              <span>{t.pipeline.evidence(c.evidence_count)}</span>
              <span className="sep" aria-hidden="true">
                ·
              </span>
            </>
          ) : (
            <>
              <span>{t.pipeline.pending}</span>
              <span className="sep" aria-hidden="true">
                ·
              </span>
            </>
          )}
          <span className="row" style={{ gap: 4, display: "inline-flex" }}>
            <FileStack size={12} aria-hidden="true" />
            {t.pipeline.artifacts(c.artifacts)}
          </span>
          <span className="sep" aria-hidden="true">
            ·
          </span>
          <span>{dateTime(c.created_at, lang)}</span>
        </div>
        {c.top_skills.length > 0 && (
          <ul className="chips" aria-label={t.pipeline.topSkills} style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {c.top_skills.map((s) => (
              <li key={s} className="chip chip-plain">
                <span>{s}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="cand-side">
        <DecisionChip decision={c.decision} />
        {!compareMode && <ChevronRight size={18} aria-hidden="true" style={{ color: "var(--text-3)" }} />}
      </div>
    </li>
  );
}

function CompareModal({ refs, onClose }: { refs: string[]; onClose: () => void }) {
  const { t } = usePrefs();
  const reports = useAsync(() => Promise.all(refs.map((r) => api.report(r))), [refs.join(",")]);
  const rows = reports.data?.[0]?.criteria ?? [];
  const byRef = (r: DashboardReport, skill: string) => r.criteria.find((c) => c.skill_id === skill);
  return (
    <Modal title={t.pipeline.compareTitle} onClose={onClose} wide>
      {reports.loading && !reports.data ? (
        <Skeleton h={240} />
      ) : reports.error ? (
        <ErrorState error={reports.error} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t.pipeline.criterion}</th>
                {reports.data?.map((r) => (
                  <th key={r.candidate_ref} scope="col" className="cmp-cell">
                    <Link to={`/candidates/${r.candidate_ref}`} className="num" onClick={onClose}>
                      {r.candidate_ref}
                    </Link>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row" className="small">
                  {t.report.compatibility}
                </th>
                {reports.data?.map((r) => (
                  <td key={r.candidate_ref}>
                    <div className="row">
                      <ScoreRing value={r.compatibility_pct} size={44} />
                      <BandChip band={r.evidence_band} />
                    </div>
                  </td>
                ))}
              </tr>
              {rows.map((row) => (
                <tr key={row.skill_id}>
                  <th scope="row" style={{ fontWeight: 500, minWidth: 180 }}>
                    <div className="stack-sm" style={{ gap: 4 }}>
                      <span>{row.label}</span>
                      <span className="row" style={{ gap: 6 }}>
                        <ImportanceChip importance={row.importance} />
                        <span className="xs faint num">
                          {t.pipeline.required} {row.required_level.toFixed(1)}
                        </span>
                      </span>
                    </div>
                  </th>
                  {reports.data?.map((r) => {
                    const cr = byRef(r, row.skill_id);
                    return (
                      <td key={r.candidate_ref} className="cmp-cell">
                        {cr ? (
                          <div className="stack-sm" style={{ gap: 6 }}>
                            <Meter
                              value={cr.observed_level}
                              max={4}
                              mark={cr.required_level}
                              label={`${row.label} — ${r.candidate_ref}: ${cr.observed_level.toFixed(2)} / 4`}
                              color={
                                cr.status === "demonstrated"
                                  ? "var(--ok)"
                                  : cr.status === "partial"
                                    ? "var(--warn)"
                                    : "var(--neutral)"
                              }
                            />
                            <span className="row" style={{ gap: 6 }}>
                              <StatusChip status={cr.status} />
                              <span className="xs num faint">{cr.observed_level.toFixed(2)}</span>
                            </span>
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}


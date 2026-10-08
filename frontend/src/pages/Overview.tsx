import { useState } from "react";
import { Link } from "react-router-dom";
import { Briefcase, DatabaseZap, Loader2, Plus } from "lucide-react";
import { api } from "../api/client";
import { useAccess, useAsync, useSystem, useT, useToast } from "../lib/prefs";
import { PageHeader, useCrumbs } from "../components/Shell";
import { StatusStrip } from "../components/StatusStrip";
import { EmptyState, ErrorState, FamilyIcon, Gate, Skeleton } from "../components/feedback";
import { ScoreRing } from "../components/charts";

export function OverviewPage() {
  const t = useT();
  const toast = useToast();
  const system = useSystem();
  const access = useAccess();
  const jobs = useAsync(() => api.jobs(), []);
  const [seeding, setSeeding] = useState(false);
  useCrumbs([{ label: t.nav.overview }]);

  const seed = async () => {
    setSeeding(true);
    try {
      const r = await api.seed();
      toast.push("success", t.overview.demoLoaded(Object.keys(r.jobs).length));
      jobs.reload();
      system.refresh();
    } catch (e) {
      toast.error(e);
    } finally {
      setSeeding(false);
    }
  };

  const list = jobs.data ?? [];
  const totals = list.reduce(
    (acc, j) => ({ c: acc.c + j.candidates, d: acc.d + j.decisions }),
    { c: 0, d: 0 },
  );

  return (
    <div className="page">
      <section className="hero ov-hero" aria-labelledby="ov-title">
        <PageHeader
          title={<span id="ov-title">{t.overview.title}</span>}
          sub={t.overview.subtitle}
          actions={
            access.can("write") ? (
              <Link to="/jobs/new" className="btn btn-primary">
                <Plus size={16} aria-hidden="true" />
                {t.overview.newJob}
              </Link>
            ) : undefined
          }
        />
        <StatusStrip />
        {list.length > 0 && (
          <div className="ov-stats">
            <div className="stat">
              <div className="stat-value">{list.length}</div>
              <div className="stat-label">{t.overview.statJobs}</div>
            </div>
            <div className="stat">
              <div className="stat-value">{totals.c}</div>
              <div className="stat-label">{t.overview.statCandidates}</div>
            </div>
            <div className="stat">
              <div className="stat-value">{totals.d}</div>
              <div className="stat-label">{t.overview.statDecisions}</div>
            </div>
          </div>
        )}
      </section>

      {jobs.loading && !jobs.data ? (
        <div className="job-grid" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} h={210} r={14} />
          ))}
        </div>
      ) : jobs.error ? (
        <ErrorState error={jobs.error} onRetry={jobs.reload} />
      ) : list.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={Briefcase}
            title={t.overview.emptyTitle}
            action={
              <div className="row wrap" style={{ justifyContent: "center" }}>
                {(system.runtime?.demo_enabled ?? system.health?.demo_enabled) && (
                  <Gate perm="admin">
                    {(ok) => (
                      <button className="btn btn-primary" onClick={seed} disabled={seeding || !ok}>
                        {seeding ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <DatabaseZap size={16} aria-hidden="true" />}
                        {t.overview.loadDemo}
                      </button>
                    )}
                  </Gate>
                )}
                {access.can("write") && (
                  <Link to="/jobs/new" className="btn">
                    <Plus size={16} aria-hidden="true" />
                    {t.overview.newJob}
                  </Link>
                )}
              </div>
            }
          >
            {t.overview.emptyBody}
          </EmptyState>
        </div>
      ) : (
        <ul className="job-grid" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {list.map((j) => (
            <li key={j.id} style={{ display: "flex" }}>
              <Link to={`/jobs/${j.id}`} className="card job-card" style={{ flex: 1 }} aria-label={t.overview.openJob(j.title)}>
                <div className="row" style={{ alignItems: "flex-start" }}>
                  <FamilyIcon family={j.family} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <h2>{j.title}</h2>
                    <div className="row small faint" style={{ gap: 8, marginTop: 4 }}>
                      <span>{t.families[j.family]}</span>
                      <span aria-hidden="true">·</span>
                      <span>{t.overview.criteria(j.criteria.length)}</span>
                    </div>
                  </div>
                  <span className="hash" title="config">
                    {t.common.version(j.version)}
                  </span>
                </div>
                {j.summary && <p className="summary">{j.summary}</p>}
                <div className="job-metrics">
                  <ScoreRing value={j.best_pct} size={52} label={`${t.overview.best}: ${j.best_pct ?? "—"}`} />
                  <div className="metric">
                    <span style={{ whiteSpace: "nowrap" }}>{t.overview.best}</span>
                    <span className="small muted">
                      {j.best_pct === null ? t.overview.notEvaluated : `${j.evaluated} ${t.overview.evaluated}`}
                    </span>
                  </div>
                  <span className="spacer" />
                  <div className="metric" style={{ alignItems: "flex-end" }}>
                    <b>{j.candidates}</b>
                    <span>{t.overview.candidates}</span>
                  </div>
                  <div className="metric" style={{ alignItems: "flex-end" }}>
                    <b>{j.decisions}</b>
                    <span>{t.overview.decisions}</span>
                  </div>
                </div>
              </Link>
            </li>
          ))}
          {access.can("write") && (
            <li style={{ display: "flex" }}>
              <Link to="/jobs/new" className="new-card" style={{ flex: 1 }}>
                <Plus size={22} aria-hidden="true" />
                {t.overview.newJob}
              </Link>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

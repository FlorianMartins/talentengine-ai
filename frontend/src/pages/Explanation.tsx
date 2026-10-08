// Public candidate explanation (/explication/:token, /explanation/:token): no account, no key, no identifiers.
// AI Act Art. 86 — the person sees the result, the evidence used, the human decision and how to contest.
import { Link, useParams } from "react-router-dom";
import {
  ArrowRight,
  ClipboardList,
  Clock,
  FileCheck2,
  FileSearch,
  Fingerprint,
  GraduationCap,
  Handshake,
  HelpCircle,
  Link2,
  Link2Off,
  MessageCircleQuestion,
  Printer,
  TrendingUp,
} from "lucide-react";
import { api, ApiError } from "../api/client";
import type { Lang } from "../i18n";
import type { PublicExplanation } from "../api/types";
import { useAsync, usePrefs } from "../lib/prefs";
import { cx, dateTime, levelIndex } from "../lib/format";
import { printPage } from "../lib/print";
import { PublicLayout, publicPaths } from "../components/PublicLayout";
import { BandChip, DecisionChip, EmptyState, ErrorState, ImportanceChip, Skeleton, StatusChip } from "../components/feedback";
import { Meter, ScoreRing } from "../components/charts";
import { SkillCard } from "./ReportSections";

export function ExplanationPage({ lang }: { lang?: Lang }) {
  return (
    <PublicLayout lang={lang}>
      <ExplanationView />
    </PublicLayout>
  );
}

function ExplanationView() {
  const { token = "" } = useParams();
  const { t, lang } = usePrefs();
  const x = useAsync(() => api.publicExplanation(token), [token]);
  const paths = publicPaths(lang);

  if (x.loading && !x.data) {
    return (
      <div className="try" aria-busy="true">
        <Skeleton h={260} r={16} />
        <Skeleton h={300} r={16} />
      </div>
    );
  }
  if (x.error instanceof ApiError && x.error.status === 404) {
    return (
      <div className="try">
        <div className="card">
          <EmptyState
            icon={Link2Off}
            title={t.explain.invalid}
            action={
              <Link to={paths.try} className="btn btn-primary">
                {t.explain.cta}
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            }
          >
            {t.explain.invalidBody}
          </EmptyState>
        </div>
      </div>
    );
  }
  if (x.error || !x.data) return <ErrorState error={x.error} onRetry={x.reload} />;
  return <Explanation data={x.data} />;
}

function Explanation({ data: d }: { data: PublicExplanation }) {
  const { t, lang } = usePrefs();
  const e = t.explain;
  const paths = publicPaths(lang);
  const credW = d.credentials_weight;
  return (
    <div className="try explain">
      {/* ------------------------------------------------ hero */}
      <section className="hero try-result-hero" aria-labelledby="x-title">
        <div className="report-hero">
          <ScoreRing value={d.compatibility_pct} size={168} stroke={12} glow caption={t.report.compatibility} />
          <div className="stack" style={{ minWidth: 0, width: "100%" }}>
            <div className="stack-sm" style={{ gap: 6 }}>
              <span className="eyebrow">{e.eyebrow}</span>
              <h1 id="x-title" className="try-title" style={{ fontSize: "clamp(1.5rem, 4vw, 2.2rem)" }}>
                {e.title}
              </h1>
              <p className="muted">
                {e.forJob} : <b style={{ color: "var(--text)" }}>{d.job_title}</b>
              </p>
              <div className="row wrap" style={{ gap: 8 }}>
                <BandChip band={d.evidence_band} />
                <span className="xs faint">{t.band.hint}</span>
              </div>
            </div>
            <div className="breakdown">
              <div className="bd-item">
                <span className="eyebrow">{e.skills}</span>
                <span className="bd-value">{d.skills_component_pct.toFixed(0)} %</span>
                <span className="xs faint">{e.weight(`${Math.round((1 - credW) * 100)} %`)}</span>
              </div>
              <div className="bd-item is-secondary">
                <span className="eyebrow">{e.credentials}</span>
                <span className="bd-value" style={{ color: "var(--text-2)" }}>
                  {d.credentials_component_pct.toFixed(0)} %
                </span>
                <span className="xs faint">{e.weight(`${Math.round(credW * 100)} %`)}</span>
              </div>
            </div>
          </div>
        </div>
        <p className="notice" style={{ marginTop: 20 }}>
          {e.intro} {d.notice}
        </p>
        <div className="row wrap no-print" style={{ gap: 8, marginTop: 16 }}>
          <button className="btn" onClick={printPage}>
            <Printer size={16} aria-hidden="true" />
            {e.pdf}
          </button>
          <span className="xs faint row" style={{ gap: 6 }}>
            <Clock size={12} aria-hidden="true" />
            {e.expires(dateTime(d.expires_at, lang))}
          </span>
        </div>
      </section>

      {/* ------------------------------------------------ decision */}
      <section className="panel" aria-labelledby="x-dec">
        <h2 id="x-dec" className="panel-title">
          <Handshake size={18} aria-hidden="true" />
          {e.decision}
        </h2>
        {d.decision ? (
          <div className="ident">
            <div className="row wrap" style={{ gap: 8 }}>
              <DecisionChip decision={d.decision.decision} />
              {d.decision.decided_at && <span className="xs muted">{e.decisionOn(dateTime(d.decision.decided_at, lang))}</span>}
            </div>
            {d.decision.rationale && (
              <p className="small">
                <b>{e.rationale} : </b>
                {d.decision.rationale}
              </p>
            )}
          </div>
        ) : (
          <p className="small muted">{e.decisionNone}</p>
        )}
      </section>

      {/* ------------------------------------------------ criteria */}
      <section className="panel" aria-labelledby="x-crit">
        <div>
          <h2 id="x-crit" className="panel-title">
            <ClipboardList size={18} aria-hidden="true" />
            {e.criteria}
          </h2>
          <p className="panel-hint">{e.criteriaHint}</p>
        </div>
        <div className="crit-matrix" role="list">
          {d.criteria.map((c) => (
            <div key={c.skill_id} className="cm-row" role="listitem">
              <div className="cm-label" style={{ minWidth: 0 }}>
                <b>{c.label}</b>
                <div className="row wrap" style={{ gap: 6, marginTop: 4 }}>
                  <ImportanceChip importance={c.importance} />
                </div>
              </div>
              <div className="cm-bar">
                <Meter
                  value={c.observed_level}
                  max={4}
                  mark={c.required_level}
                  label={`${c.label}: ${t.report.observed} ${c.observed_level.toFixed(2)}, ${t.report.required} ${c.required_level.toFixed(2)} / 4`}
                  color={c.status === "demonstrated" ? "var(--ok)" : c.status === "partial" ? "var(--warn)" : "var(--neutral)"}
                />
                <div className="cm-levels">
                  <span>
                    {t.report.observed} · <b style={{ color: "var(--text)" }}>{t.levels[levelIndex(c.observed_level)]}</b>
                  </span>
                  <span>
                    ▍{t.report.required} · {t.levels[levelIndex(c.required_level)]}
                  </span>
                </div>
              </div>
              <StatusChip status={c.status} />
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ proofs */}
      <section className="panel" aria-labelledby="x-proof">
        <div>
          <h2 id="x-proof" className="panel-title">
            <FileSearch size={18} aria-hidden="true" />
            {e.proofs}
          </h2>
          <p className="panel-hint">{e.proofsHint}</p>
        </div>
        {d.validated_skills.length === 0 ? (
          <p className="small muted">{e.noProofs}</p>
        ) : (
          <div className="skill-grid">
            {d.validated_skills.map((v) => (
              <SkillCard key={v.skill_id} skill={v} candidateRef="" imageIds={new Set()} />
            ))}
          </div>
        )}
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* ------------------------------------------------ gaps */}
        <section className="panel" aria-labelledby="x-gaps">
          <div>
            <h2 id="x-gaps" className="panel-title">
              <TrendingUp size={18} aria-hidden="true" />
              {e.gaps}
            </h2>
            <p className="panel-hint">{e.gapsHint}</p>
          </div>
          {d.gaps.length === 0 ? (
            <p className="small muted">{e.gapsEmpty}</p>
          ) : (
            <ul className="gap-list">
              {d.gaps.map((g) => (
                <li key={g.skill_id} className={cx("gap", g.declared_by_candidate && "is-declared")}>
                  <HelpCircle size={16} aria-hidden="true" />
                  <div className="stack-sm" style={{ gap: 4, minWidth: 0 }}>
                    <div className="row wrap" style={{ gap: 8 }}>
                      <b className="small">{g.label}</b>
                      <ImportanceChip importance={g.importance} />
                    </div>
                    <p className="small muted">{g.suggestion}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ------------------------------------------------ integrity */}
        <section className="panel" aria-labelledby="x-int">
          <h2 id="x-int" className="panel-title">
            <Fingerprint size={18} aria-hidden="true" />
            {e.integrity}
          </h2>
          <p className={cx("callout", d.audit.ledger_intact ? "callout-ok" : "callout-danger")}>
            {d.audit.ledger_intact ? <Link2 size={16} aria-hidden="true" /> : <Link2Off size={16} aria-hidden="true" />}
            <span>{d.audit.ledger_intact ? e.integrityOk : e.integrityBad}</span>
          </p>
          <div className="field">
            <span className="label">{e.hash}</span>
            <pre className="code" style={{ color: "var(--accent-text)" }}>
              {d.audit.score_entry_hash}
            </pre>
            <p className="hint">{e.hashHint}</p>
          </div>
          <dl className="kv">
            <dt>{e.recorded}</dt>
            <dd>{dateTime(d.audit.recorded_at, lang)}</dd>
            <dt>{e.engine}</dt>
            <dd className="mono">{d.audit.engine_version}</dd>
            <dt>{e.config}</dt>
            <dd className="mono">v{d.audit.job_config_version}</dd>
          </dl>
        </section>
      </div>

      {/* ------------------------------------------------ credentials (secondary) */}
      <section className="panel is-secondary" aria-labelledby="x-cred">
        <div>
          <h2 id="x-cred" className="panel-title">
            <GraduationCap size={16} aria-hidden="true" />
            {e.credentialsTitle}
          </h2>
          <p className="panel-hint">{e.credentialsHint(`${Math.round(credW * 100)} %`)}</p>
        </div>
        {d.credentials.length === 0 ? (
          <p className="small muted">{e.credentialsEmpty}</p>
        ) : (
          <ul className="chips" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {d.credentials.map((c, i) => (
              <li key={`${c.label}-${i}`} className={cx("chip", c.kind === "degree" ? "chip-plain" : "chip-violet")}>
                <span>{c.label}</span>
                {c.supported_by_document && (
                  <span className="cred-proof">
                    <FileCheck2 size={12} aria-hidden="true" /> {t.docs.supported}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ------------------------------------------------ contest + CTA */}
      <section className="hero try-end" aria-labelledby="x-contest">
        <span className="land-icon">
          <MessageCircleQuestion size={20} aria-hidden="true" />
        </span>
        <h2 id="x-contest" className="try-h2">
          {e.contest}
        </h2>
        <p className="muted" style={{ maxWidth: "62ch" }}>
          {e.contestBody}
        </p>
        <p className="xs faint">{e.expires(dateTime(d.expires_at, lang))}</p>
        <Link to={paths.try} className="btn btn-primary no-print">
          {e.cta}
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </div>
  );
}

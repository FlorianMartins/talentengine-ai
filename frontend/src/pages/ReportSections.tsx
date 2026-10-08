// Building blocks of the candidate report (HR dashboard).
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Bot,
  ChevronRight,
  ClipboardCheck,
  Cpu,
  Eye,
  FileSearch,
  FileText,
  Fingerprint,
  GitBranch,
  GraduationCap,
  Handshake,
  HelpCircle,
  Inbox,
  Link2,
  Link2Off,
  Lightbulb,
  MessageSquareQuote,
  Network,
  Printer,
  Scale,
  ScrollText,
  Settings2,
  ShieldAlert,
  StickyNote,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { api } from "../api/client";
import type {
  Artifact,
  DashboardReport,
  EvidenceRef,
  Explanation,
  LedgerEntry,
  SkillGraph,
  ValidatedSkill,
} from "../api/types";
import { usePrefs } from "../lib/prefs";
import { cx, dateTime, levelIndex, shortHash, usd } from "../lib/format";
import { BandChip, ImportanceChip, Skeleton, StatusChip } from "../components/feedback";
import { Meter, Radar, SkillGraphView, type GraphNode } from "../components/charts";

// ------------------------------------------------------------------ criteria matrix

export function CriteriaMatrix({ report }: { report: DashboardReport }) {
  const { t } = usePrefs();
  return (
    <section className="panel" aria-labelledby="r-crit">
      <div>
        <h2 id="r-crit" className="panel-title">
          <Scale size={18} aria-hidden="true" />
          {t.report.criteria}
        </h2>
        <p className="panel-hint">{t.report.criteriaHint}</p>
      </div>
      <div className="crit-matrix" role="list">
        {report.criteria.map((c) => (
          <div key={c.skill_id} className="cm-row" role="listitem">
            <div className="cm-label" style={{ minWidth: 0 }}>
              <b>{c.label}</b>
              <div className="row wrap" style={{ gap: 6, marginTop: 4 }}>
                <ImportanceChip importance={c.importance} />
                <span className="xs faint">{t.pipeline.evidence(c.evidence_count)}</span>
              </div>
              {c.recruiter_note && (
                <p className="cm-note">
                  <StickyNote size={12} aria-hidden="true" />
                  <span>{c.recruiter_note}</span>
                </p>
              )}
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
                  {t.report.observed}{" "}
                  <b className="num" style={{ color: "var(--text)" }}>
                    {c.observed_level.toFixed(2)}
                  </b>{" "}
                  · {t.levels[levelIndex(c.observed_level)]}
                </span>
                <span>
                  ▍{t.report.required} <span className="num">{c.required_level.toFixed(2)}</span>
                </span>
              </div>
            </div>
            <StatusChip status={c.status} />
          </div>
        ))}
      </div>
      {report.criteria.some((c) => c.status === "not_evidenced") && (
        <p className="xs faint">{t.critHint.not_evidenced}</p>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ evidence

function EvidenceItem({ ev, candidateRef, imageIds }: { ev: EvidenceRef; candidateRef: string; imageIds: Set<string> }) {
  const { t } = usePrefs();
  const [src, setSrc] = useState<string | null>(null);
  const isImage = imageIds.has(ev.artifact_id);
  useEffect(() => {
    if (!isImage) return;
    let url: string | null = null;
    let alive = true;
    void api.media(candidateRef, ev.artifact_id).then((u) => {
      url = u;
      if (alive) setSrc(u);
    });
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [isImage, candidateRef, ev.artifact_id]);
  return (
    <li className="evidence">
      <div className="evidence-head">
        <FileText size={12} aria-hidden="true" />
        <b>{ev.artifact_label}</b>
        <span className="faint">·</span>
        <span className="mono truncate">{ev.locator}</span>
        <span className="spacer" />
        <span className="hash">{ev.artifact_id}</span>
      </div>
      {src && <img src={src} alt={`${t.report.media} — ${ev.artifact_label}`} />}
      {ev.excerpt && <pre>{ev.excerpt}</pre>}
    </li>
  );
}

function SkillCard({
  skill,
  candidateRef,
  imageIds,
}: {
  skill: ValidatedSkill;
  candidateRef: string;
  imageIds: Set<string>;
}) {
  const { t } = usePrefs();
  const [open, setOpen] = useState(false);
  const idx = levelIndex(skill.level);
  const panelId = `ev-${skill.skill_id}`;
  return (
    <article className="skill-card">
      <div className="skill-top">
        <div className="stack-sm" style={{ gap: 6 }}>
          <h3>{skill.label}</h3>
          <div className="row wrap" style={{ gap: 8 }}>
            <span className="level-pill">
              <span className="level-dots" aria-hidden="true">
                {[0, 1, 2, 3, 4].map((i) => (
                  <i key={i} className={cx(i <= idx && "on")} />
                ))}
              </span>
              {skill.level_label}
              <span className="num faint">{skill.level.toFixed(2)}</span>
            </span>
            <span className={cx("chip", skill.source === "llm" ? "chip-violet" : "chip-plain")}>
              {skill.source === "llm" ? <Bot size={12} aria-hidden="true" /> : <Cpu size={12} aria-hidden="true" />}
              <span>{t.report.source[skill.source]}</span>
            </span>
          </div>
        </div>
        <Radar values={skill.axes} max={4} size={104} label={skill.label} />
      </div>
      <p className="skill-statement">{skill.statement}</p>
      <div className="row wrap" style={{ gap: 12 }}>
        <span className="xs muted">
          {t.report.confidence} <b className="num">{Math.round(skill.confidence * 100)} %</b>
        </span>
        <span className="spacer" />
        <button
          type="button"
          className="disclosure"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen(!open)}
        >
          <ChevronRight size={14} aria-hidden="true" />
          {open ? t.report.hideEvidence : `${t.report.showEvidence} (${skill.evidence.length})`}
        </button>
      </div>
      {open && (
        <ul id={panelId} className="evidence-list">
          {skill.evidence.map((ev, i) => (
            <EvidenceItem key={`${ev.artifact_id}-${i}`} ev={ev} candidateRef={candidateRef} imageIds={imageIds} />
          ))}
        </ul>
      )}
    </article>
  );
}

export function ProofPanel({ report, artifacts }: { report: DashboardReport; artifacts: Artifact[] | null }) {
  const { t } = usePrefs();
  const imageIds = useMemo(
    () => new Set((artifacts ?? []).filter((a) => a.kind === "image").map((a) => a.id)),
    [artifacts],
  );
  return (
    <section className="panel" aria-labelledby="r-proof">
      <div>
        <h2 id="r-proof" className="panel-title">
          <FileSearch size={18} aria-hidden="true" />
          {t.report.proofs}
        </h2>
        <p className="panel-hint">{t.report.proofsHint}</p>
      </div>
      {report.validated_skills.length === 0 ? (
        <p className="callout callout-neutral">
          <Inbox size={16} aria-hidden="true" />
          <span>{t.critHint.not_evidenced}</span>
        </p>
      ) : (
        <div className="skill-grid">
          {report.validated_skills.map((s) => (
            <SkillCard key={s.skill_id} skill={s} candidateRef={report.candidate_ref} imageIds={imageIds} />
          ))}
        </div>
      )}
    </section>
  );
}

export function ArtifactsPanel({ artifacts }: { artifacts: Artifact[] | null }) {
  const { t } = usePrefs();
  if (!artifacts) return <Skeleton h={120} r={14} />;
  return (
    <section className="panel is-secondary" aria-labelledby="r-art">
      <h2 id="r-art" className="panel-title">
        <FileText size={16} aria-hidden="true" />
        {t.report.artifacts}
      </h2>
      <ul className="file-list">
        {artifacts.map((a) => {
          const masked = Object.values(a.redaction.pii_replaced).reduce((s, n) => s + n, 0);
          return (
            <li key={a.id} className="file-item" style={{ flexWrap: "wrap" }}>
              <span className="hash">{a.id}</span>
              <b className="small">{a.label}</b>
              <span className="chip chip-plain">
                <span>{a.kind}</span>
              </span>
              {a.status === "quarantined" && (
                <span className="chip chip-warn">
                  <span>{t.report.quarantined}</span>
                </span>
              )}
              {a.redaction.injection_suspected && (
                <span className="chip chip-warn">
                  <ShieldAlert size={12} aria-hidden="true" />
                  <span>{t.report.injection}</span>
                </span>
              )}
              <span className="spacer" />
              <span className="xs faint">{t.report.redaction(masked)}</span>
              <span className="hash" title={a.content_sha256}>
                sha256 {shortHash(a.content_sha256, 8)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ------------------------------------------------------------------ gaps

export function GapsPanel({ report }: { report: DashboardReport }) {
  const { t } = usePrefs();
  return (
    <section className="panel" aria-labelledby="r-gaps">
      <h2 id="r-gaps" className="panel-title">
        <HelpCircle size={18} aria-hidden="true" />
        {t.report.gaps}
      </h2>
      {report.gaps.length === 0 ? (
        <p className="small muted">{t.report.gapsEmpty}</p>
      ) : (
        <ul className="gap-list">
          {report.gaps.map((g) => (
            <li key={g.skill_id} className={cx("gap", g.declared_by_candidate && "is-declared")}>
              {g.declared_by_candidate ? <MessageSquareQuote size={16} aria-hidden="true" /> : <Lightbulb size={16} aria-hidden="true" />}
              <div className="stack-sm" style={{ gap: 4, minWidth: 0 }}>
                <div className="row wrap" style={{ gap: 8 }}>
                  <b className="small">{g.label}</b>
                  <ImportanceChip importance={g.importance} />
                  {g.declared_by_candidate && (
                    <span className="chip chip-warn">
                      <span>{t.report.declared}</span>
                    </span>
                  )}
                </div>
                <p className="small muted">{g.suggestion}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ interview guide

export function InterviewGuide({ report }: { report: DashboardReport }) {
  const { t } = usePrefs();
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  return (
    <section className="stack" aria-labelledby="r-guide">
      <div className="panel-head">
        <div>
          <h2 id="r-guide" className="panel-title">
            <ClipboardCheck size={18} aria-hidden="true" />
            {t.report.guide}
          </h2>
          <p className="panel-hint">{t.report.guideHint}</p>
        </div>
        <button type="button" className="btn no-print" onClick={() => window.print()}>
          <Printer size={16} aria-hidden="true" />
          {t.report.print}
        </button>
      </div>
      <div className="print-only">
        <p className="mono">
          {report.candidate_ref} · {report.job_title}
        </p>
      </div>
      <ol className="q-grid" style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {report.interview_guide.map((q, qi) => (
          <li key={`${q.skill_id}-${qi}`} className="card q-card">
            <span className="q-num" aria-hidden="true">
              {qi + 1}
            </span>
            <div className="stack" style={{ minWidth: 0 }}>
              <p className="q-text">{q.question}</p>
              <p className="small muted">
                <b style={{ color: "var(--text)" }}>{t.report.purpose} — </b>
                {q.purpose}
              </p>
              <div className="q-cols">
                <div className="stack-sm">
                  <h3 className="eyebrow">{t.report.keyPoints}</h3>
                  <ul className="checklist">
                    {q.expected_key_points.map((k, ki) => {
                      const key = `${qi}-${ki}`;
                      return (
                        <li key={key}>
                          <label className={cx("check", ticked[key] && "is-done")}>
                            <input
                              type="checkbox"
                              checked={Boolean(ticked[key])}
                              onChange={(e) => setTicked({ ...ticked, [key]: e.target.checked })}
                            />
                            <span>{k}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
                <div className="stack-sm">
                  <h3 className="eyebrow">{t.report.warningSigns}</h3>
                  <ul className="warn-list">
                    {q.warning_signs.map((w) => (
                      <li key={w}>
                        <AlertTriangle size={13} aria-hidden="true" />
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="stack-sm" style={{ gap: 6 }}>
                <h3 className="eyebrow">{t.report.refersTo}</h3>
                <ul className="evidence-list">
                  <EvidenceItem ev={q.evidence} candidateRef={report.candidate_ref} imageIds={new Set()} />
                </ul>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ------------------------------------------------------------------ skill graph

export function GraphPanel({
  report,
  graph,
  loading,
}: {
  report: DashboardReport;
  graph: SkillGraph | null;
  loading: boolean;
}) {
  const { t } = usePrefs();
  const nodes = useMemo<GraphNode[]>(() => {
    if (!graph) return [];
    const vs = new Map(report.validated_skills.map((s) => [s.skill_id, s]));
    const crit = new Map(report.criteria.map((c) => [c.skill_id, c.label]));
    const pretty = (id: string) => crit.get(id) ?? id.replace(/_/g, " ");
    const list: GraphNode[] = graph.assessments.map((a) => {
      const v = vs.get(a.skill_id);
      const mean = (a.axes.autonomy + a.axes.complexity + a.axes.reliability) / 3;
      return { id: a.skill_id, label: v?.label ?? pretty(a.skill_id), level: v?.level ?? mean, source: a.source };
    });
    for (const d of graph.declared_only) if (!list.some((n) => n.id === d)) list.push({ id: d, label: pretty(d), level: 0.4, source: "declared" });
    return list;
  }, [graph, report]);
  return (
    <section className="panel" aria-labelledby="r-graph">
      <div className="panel-head">
        <div>
          <h2 id="r-graph" className="panel-title">
            <Network size={18} aria-hidden="true" />
            {t.report.graph}
          </h2>
          <p className="panel-hint">{t.report.graphHint}</p>
        </div>
        <div className="row wrap xs muted" style={{ gap: 12 }}>
          <span className="row" style={{ gap: 6 }}>
            <svg width="12" height="12" aria-hidden="true">
              <circle cx="6" cy="6" r="5" fill="none" stroke="var(--accent)" strokeWidth="1.5" />
            </svg>
            {t.report.source.heuristic}
          </span>
          <span className="row" style={{ gap: 6 }}>
            <svg width="12" height="12" aria-hidden="true">
              <circle cx="6" cy="6" r="5" fill="none" stroke="var(--violet)" strokeWidth="1.5" />
            </svg>
            {t.report.source.llm}
          </span>
          {graph && graph.declared_only.length > 0 && (
            <span className="row" style={{ gap: 6 }}>
              <svg width="12" height="12" aria-hidden="true">
                <circle cx="6" cy="6" r="5" fill="none" stroke="var(--warn)" strokeWidth="1.5" strokeDasharray="2 2" />
              </svg>
              {t.report.declared}
            </span>
          )}
        </div>
      </div>
      {loading && !graph ? (
        <Skeleton h={320} r={12} />
      ) : nodes.length === 0 ? (
        <p className="small muted">{t.report.graphEmpty}</p>
      ) : (
        <div className="graph-wrap">
          <SkillGraphView nodes={nodes} edges={graph?.edges ?? []} label={t.report.graphLabel} />
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ credentials

export function CredentialsPanel({ report }: { report: DashboardReport }) {
  const { t } = usePrefs();
  const cred = report.credentials;
  const matched = (label: string) =>
    cred.matched_accepted.some((m) => label.toLowerCase().includes(m.toLowerCase()));
  return (
    <section className="panel is-secondary" aria-labelledby="r-cred">
      <div className="panel-head">
        <div>
          <h2 id="r-cred" className="panel-title">
            <GraduationCap size={16} aria-hidden="true" />
            {t.report.credPanel}
          </h2>
          <p className="panel-hint">{t.report.credPanelHint}</p>
        </div>
        <span className="hash">
          {Math.round(cred.component_pct)} % · {t.report.credWeight(`${Math.round(cred.weight_applied * 100)} %`)}
        </span>
      </div>
      {cred.items.length === 0 ? (
        <p className="small muted">{t.report.credEmpty}</p>
      ) : (
        <ul className="file-list">
          {cred.items.map((c, i) => (
            <li key={`${c.label}-${i}`} className="file-item" style={{ flexWrap: "wrap" }}>
              <span className={cx("chip", c.kind === "degree" ? "chip-plain" : "chip-violet")}>
                <span>{c.kind === "degree" ? t.report.degree : t.report.certification}</span>
              </span>
              <span className="small" style={{ flex: "1 1 200px", minWidth: 0, overflowWrap: "anywhere" }}>
                {c.label}
              </span>
              {matched(c.label) && (
                <span className="chip chip-ok chip-dot">
                  <span>{t.report.matched}</span>
                </span>
              )}
              <span className="xs faint mono">
                {c.evidence.artifact_label} · {c.evidence.locator}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ glass box

const KIND_ICONS: Record<string, LucideIcon> = {
  job_config: Settings2,
  ingestion: Inbox,
  score: Scale,
  escalation: Bot,
  human_decision: Handshake,
  reidentification: Eye,
  erasure: Trash2,
};

export function LedgerTimeline({ entries }: { entries: LedgerEntry[] }) {
  const { t, lang } = usePrefs();
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const sorted = [...entries].sort((a, b) => a.seq - b.seq);
  return (
    <ol className="timeline">
      {sorted.map((e) => {
        const Icon = KIND_ICONS[e.kind] ?? ScrollText;
        const expanded = Boolean(open[e.seq]);
        return (
          <li key={e.seq} className="tl-item">
            <span className={cx("tl-dot", `k-${e.kind}`)} aria-hidden="true">
              <Icon size={15} />
            </span>
            <div className="tl-body">
              <div className="row wrap" style={{ gap: 8 }}>
                <b className="small">{t.audit.kinds[e.kind] ?? e.kind}</b>
                <span className="hash">#{e.seq}</span>
                <span className="xs muted">
                  {e.actor} · {dateTime(e.created_at, lang)}
                </span>
              </div>
              <div className="chain-cell xs" style={{ flexWrap: "wrap" }}>
                <span className="hash" title={e.prev_hash}>
                  {shortHash(e.prev_hash, 8)}
                </span>
                <ChevronRight size={12} aria-hidden="true" />
                <span className="hash" title={e.entry_hash} style={{ color: "var(--accent-text)" }}>
                  {shortHash(e.entry_hash, 8)}
                </span>
                <span className="faint mono">{e.entry_id}</span>
              </div>
              <button
                type="button"
                className="disclosure"
                aria-expanded={expanded}
                onClick={() => setOpen({ ...open, [e.seq]: !expanded })}
              >
                <ChevronRight size={14} aria-hidden="true" />
                {expanded ? t.audit.collapse : t.audit.expand}
              </button>
              {expanded && <pre className="code">{JSON.stringify(e.payload, null, 2)}</pre>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function GlassBox({
  report,
  explanation,
  loading,
}: {
  report: DashboardReport;
  explanation: Explanation | null;
  loading: boolean;
}) {
  const { t, lang } = usePrefs();
  const esc = report.audit.escalation;
  const labels = (s: string) =>
    report.criteria
      .filter((c) => c.status === s)
      .map((c) => c.label)
      .join(", ");
  const evidenceCount = report.validated_skills.reduce((s, v) => s + v.evidence.length, 0);
  const artifactCount = new Set(report.validated_skills.flatMap((v) => v.evidence.map((e) => e.artifact_id))).size;
  const strong = labels("demonstrated");
  const partial = labels("partial");
  const missing = labels("not_evidenced");
  return (
    <div className="stack-lg">
      <section className="panel" aria-labelledby="r-why">
        <h2 id="r-why" className="panel-title">
          <Lightbulb size={18} aria-hidden="true" />
          {t.report.whyTitle}
        </h2>
        <div className="why">
          <p>
            {t.report.whyIntro(
              `${report.compatibility_pct.toFixed(1)} %`,
              `${report.skills_component_pct.toFixed(1)} %`,
              `${report.credentials_component_pct.toFixed(1)} %`,
              `${Math.round(report.credentials.weight_applied * 100)} %`,
            )}
          </p>
          {strong && <p>{t.report.whyStrong(strong)}</p>}
          {partial && <p>{t.report.whyPartial(partial)}</p>}
          {missing && <p>{t.report.whyMissing(missing)}</p>}
          <p>{t.report.whyEvidence(evidenceCount, artifactCount)}</p>
          <p className="muted">{t.report.whyClose}</p>
        </div>
        <div className="row wrap" style={{ gap: 8 }}>
          <BandChip band={report.evidence_band} />
          <span className="xs faint">{t.band.hint}</span>
        </div>
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        <section className="panel" aria-labelledby="r-audit">
          <h2 id="r-audit" className="panel-title">
            <Fingerprint size={18} aria-hidden="true" />
            {t.report.scoreEntry}
          </h2>
          <pre className="code" style={{ color: "var(--accent-text)" }}>
            {report.audit.entry_hash}
          </pre>
          <dl className="kv">
            <dt>{t.report.ledgerEntry}</dt>
            <dd className="mono">{report.audit.ledger_entry_id}</dd>
            <dt>{t.report.engine}</dt>
            <dd className="mono">{report.audit.engine_version}</dd>
            <dt>{t.report.configVersion}</dt>
            <dd className="mono">v{report.audit.job_config_version}</dd>
            <dt>{t.report.signals}</dt>
            <dd className="mono">{report.audit.signals_used}</dd>
          </dl>
        </section>
        <section className="panel" aria-labelledby="r-esc">
          <h2 id="r-esc" className="panel-title">
            <Bot size={18} aria-hidden="true" />
            {t.report.escalation}
          </h2>
          <div>
            <span className={cx("chip", esc.escalated ? "chip-violet" : "chip-plain")}>
              <span>{esc.escalated ? t.report.escalated : t.report.notEscalated}</span>
            </span>
          </div>
          <dl className="kv">
            {esc.escalated ? (
              <>
                <dt>{t.report.provider}</dt>
                <dd className="mono">{esc.provider}</dd>
                <dt>{t.report.model}</dt>
                <dd className="mono">{esc.model || "—"}</dd>
                <dt>{t.report.tokensIO}</dt>
                <dd className="mono">
                  {esc.input_tokens} / {esc.output_tokens}
                </dd>
                <dt>{t.report.cost}</dt>
                <dd className="mono">{usd(esc.cost_usd, lang)}</dd>
              </>
            ) : null}
            {esc.reason && (
              <>
                <dt>{t.report.reason}</dt>
                <dd>{esc.reason}</dd>
              </>
            )}
          </dl>
        </section>
      </div>

      <section className="panel" aria-labelledby="r-tl">
        <div className="panel-head">
          <div>
            <h2 id="r-tl" className="panel-title">
              <GitBranch size={18} aria-hidden="true" />
              {t.report.timeline}
            </h2>
            <p className="panel-hint">{t.report.timelineHint}</p>
          </div>
        </div>
        {explanation ? (
          <>
            <p className={cx("callout", explanation.chain.valid ? "callout-ok" : "callout-danger")} role="status">
              {explanation.chain.valid ? <Link2 size={16} aria-hidden="true" /> : <Link2Off size={16} aria-hidden="true" />}
              <span>
                {explanation.chain.valid
                  ? t.report.chainOk(explanation.chain.length)
                  : t.report.chainBad(explanation.chain.first_invalid_seq, explanation.chain.reason)}
              </span>
            </p>
            <LedgerTimeline entries={explanation.ledger} />
          </>
        ) : loading ? (
          <Skeleton h={200} />
        ) : (
          <p className="small muted">—</p>
        )}
      </section>
    </div>
  );
}

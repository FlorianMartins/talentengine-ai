// Report of a technical test (sections 1 knowledge, 2 with the AI, 3 practice = the AI-pilot mission).
// Shared by the sandbox end screen (audience "self") and the recruiter report (audience "recruiter").
// Factual numbers and the judge's bounded adjustment are always shown side by side, every piece of
// evidence links to the transcript turn it cites. The AI-usage facts are descriptive, never a score.
import { useId, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Bot,
  Bug,
  Calculator,
  CheckCircle2,
  Compass,
  FileCode2,
  Gauge,
  Info,
  ListChecks,
  MessagesSquare,
  Scale,
  ScrollText,
  Search,
  Target,
  Timer,
  UserCheck,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { PilotMetric, PilotQuestionOutcome, PilotReport, PilotTurn } from "../api/types";
import type { Dict } from "../i18n";
import { usePrefs } from "../lib/prefs";
import { cx } from "../lib/format";
import { Meter, ScoreRing } from "./charts";
import { PilotTranscript } from "./PilotTurns";

const METRIC_ICON: Record<string, LucideIcon> = {
  applied_knowledge: BookOpen,
  intent_precision: Compass,
  critical_thinking: Search,
  orchestration_velocity: Zap,
  ownership: UserCheck,
};

/** The backend's evidence notes are fixed English templates: localise the known ones, keep others as is. */
export function localizeNote(note: string, t: Dict, titles: Record<string, string>): string {
  const n = t.pilot.report.notes;
  const f = (id: string | undefined) => (id ? titles[id] ?? id : "");
  const q = t.tt.notes;
  let m: RegExpExecArray | null;
  if (note === "no instruction was given to the assistant") return n.noInstruction;
  if (note === "no assistant answer was ever reviewed: nothing to measure") return q.nothing;
  if ((m = /^(\d+) of (\d+) questions right, (\d+) out of time, with calculator and internet allowed$/.exec(note)))
    return q.knowledge(m[1] ?? "", m[2] ?? "", m[3] ?? "");
  if ((m = /^question (\d+): gave the assistant's wrong answer as is$/.exec(note))) return q.followed(m[1] ?? "");
  if ((m = /^question (\d+): right answer although the assistant was wrong( \(after making it check\))?$/.exec(note)))
    return q.caught(m[1] ?? "", Boolean(m[2]));
  if ((m = /^question (\d+): doubted the assistant but answered wrong$/.exec(note))) return q.doubted(m[1] ?? "");
  if (note === "vague instruction: no constraint, criterion or reference to the code") return n.vague;
  if (note === "the work that carries the injected flaws was never requested: nothing to review") return n.neverRequested;
  if (note === "says where the change goes in the function") return n.where;
  if (note === "asks the assistant to explain the function") return n.explain;
  if (note === "no instruction was given during the five minutes") return n.silent5;
  if ((m = /^framed instruction: (.*)$/.exec(note))) return n.framed(m[1] ?? "");
  if ((m = /^anticipated '([^']+)' before the assistant could introduce it$/.exec(note))) return n.anticipated(f(m[1]));
  if ((m = /^called out '([^']+)' \((\w+)\) (\d+) instruction\(s\) after it appeared$/.exec(note)))
    return n.calledOut(f(m[1]), n.by[m[2] ?? ""] ?? m[2] ?? "", m[3] ?? "");
  if ((m = /^called out '([^']+)' in other words/.exec(note))) return n.calledOutJudge(f(m[1]));
  if ((m = /^'([^']+)' disappeared without being named$/.exec(note))) return n.vanished(f(m[1]));
  if ((m = /^'([^']+)' was accepted and is still in the code at the end$/.exec(note))) return n.accepted(f(m[1]));
  if ((m = /^(\d+) iteration\(s\) for a par of (\d+); CI (green|not green) at close; (\d+) regression\(s\)$/.exec(note)))
    return n.velocity(m[1] ?? "", m[2] ?? "", m[3] === "green", m[4] ?? "");
  if ((m = /^uses names from elsewhere in the repository: (.*)$/.exec(note))) return n.hidden(m[1] ?? "");
  return note;
}

const ENGLISH_LIMITS = [
  "The assistant's flaws are drawn from a fixed pool",
  "Call-outs are detected by keyword rules",
  "The virtual CI is static analysis",
  "Five minutes on one's own code",
];
export function localizeLimit(limit: string, t: Dict): string {
  if (limit.startsWith("Tools are allowed and not monitored")) return t.tt.limitTools;
  const i = ENGLISH_LIMITS.findIndex((p) => limit.startsWith(p));
  return i >= 0 ? t.pilot.report.limits[i] ?? limit : limit;
}

/** breakdown keys: fixed ids, flaw ids, skill labels, or "question N" (section 2 traps) */
function breakdownLabel(k: string, t: Dict, titles: Record<string, string>): string {
  const m = /^question (\d+)$/.exec(k);
  if (m) return t.tt.report.questionLabel(m[1] ?? "");
  return t.pilot.report.breakdownLabels[k] ?? titles[k] ?? k;
}

const PRACTICE = ["intent_precision", "critical_thinking", "orchestration_velocity"];

/** weighted mean of the given metrics, renormalised over those present (as the backend does) */
function weightedMean(r: PilotReport, ids: string[]): number | null {
  const present = r.metrics.filter((m) => ids.includes(m.id) && r.weights[m.id] !== undefined);
  const total = present.reduce((a, m) => a + (r.weights[m.id] ?? 0), 0);
  return total > 0 ? present.reduce((a, m) => a + (r.weights[m.id] ?? 0) * m.final_pct, 0) / total : null;
}

function pctColor(v: number): string {
  return v >= 65 ? "var(--ok)" : v >= 35 ? "var(--accent)" : "var(--neutral)";
}

export function PilotReportView({
  report: r,
  transcript,
  audience,
}: {
  report: PilotReport;
  transcript?: PilotTurn[];
  audience: "self" | "recruiter";
}) {
  const { t } = usePrefs();
  const p = t.pilot.report;
  const anchor = `pl${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const transcriptRef = useRef<HTMLDetailsElement>(null);
  const [hl, setHl] = useState<number | null>(null);
  const titles = Object.fromEntries(r.faults.map((f) => [f.id, f.title]));
  const tt = t.tt.report;
  const steering = r.metrics.filter((m) => m.id !== "ownership");
  const own = r.metrics.find((m) => m.id === "ownership");
  const hasMission = Boolean(r.scenario_id);
  // the backend renormalises the weights over the metrics present: show the weight actually applied
  const weightTotal = steering.reduce((a, m) => a + (r.weights[m.id] ?? 0), 0);
  const weightOf = (id: string) => (r.weights[id] === undefined || weightTotal <= 0 ? undefined : (r.weights[id] ?? 0) / weightTotal);

  const goTurn = (n: number) => {
    if (!transcript) return;
    if (transcriptRef.current) transcriptRef.current.open = true;
    setHl(n);
    window.requestAnimationFrame(() => {
      const el = document.getElementById(`${anchor}-turn-${n}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      el?.focus({ preventScroll: true });
    });
  };

  return (
    <div className="stack-lg pilot-report">
      {/* ---------------------------------------------------------- head */}
      <div className="pr-head">
        <div className="pr-rings">
          <ScoreRing
            value={r.pilot_index_pct}
            size={audience === "self" ? 148 : 112}
            glow={audience === "self"}
            caption={tt.ring}
            label={`${tt.overall} ${r.pilot_index_pct.toFixed(1)} %`}
          />
          <ScoreRing
            value={r.authenticity_pct}
            size={audience === "self" ? 104 : 84}
            color="var(--violet)"
            caption={p.authenticity}
            label={`${p.authenticity} ${r.authenticity_pct === null ? p.notTaken : `${r.authenticity_pct.toFixed(1)} %`}`}
          />
        </div>
        <div className="stack-sm" style={{ minWidth: 0, flex: 1 }}>
          <span className="eyebrow">{t.tt.name}</span>
          <h3 className="pr-title">{r.job_title}</h3>
          <div className="row wrap" style={{ gap: 8 }}>
            <span className="chip chip-accent">
              <span>{t.pilot.levels[r.level]}</span>
            </span>
            <span className={cx("chip", hasMission ? "chip-plain" : "chip-neutral")}>
              <Target size={12} aria-hidden="true" />
              <span>{hasMission ? `${p.scenario} · ${r.scenario_title}` : tt.questionsOnly}</span>
            </span>
            <span className="chip chip-plain">
              <span>{p.prompts(r.prompts)}</span>
            </span>
            <span className="chip chip-plain">
              <Timer size={12} aria-hidden="true" />
              <span>{p.duration(r.duration_minutes)}</span>
            </span>
            <span className="chip chip-plain" title={r.assistant}>
              <span>
                {p.assistant} · {r.assistant === "reference assistant (scripted)" ? p.assistantRef : r.assistant}
              </span>
            </span>
            <span className={cx("chip", r.judge === "none" ? "chip-neutral" : "chip-violet")}>
              <Scale size={12} aria-hidden="true" />
              <span>
                {p.judge} · {r.judge === "none" ? p.judgeNone : r.judge.startsWith("pending: ")
                  ? t.byok.judgePending(r.judge.slice(9)) : r.judge}
              </span>
            </span>
          </div>
          <p className="xs faint">
            {tt.overallHint} {r.authenticity_pct === null ? `${p.authenticity} — ${p.notTaken}.` : p.authenticityHint}
          </p>
        </div>
      </div>

      <div className="callout callout-warn pr-signal" role="note">
        <AlertTriangle size={16} aria-hidden="true" />
        <div>
          <b>{p.signal}</b>
          <p className="small" style={{ marginTop: 2 }}>
            {p.signalBody}
          </p>
        </div>
      </div>

      <SectionsSummary r={r} />

      {(r.questions?.length ?? 0) > 0 && (
        <>
          {r.questions?.some((q) => q.section === "ai") && <AiUsagePanel r={r} />}
          <QuestionsTable r={r} audience={audience} />
        </>
      )}

      {/* ---------------------------------------------------------- metrics */}
      <section className="stack" aria-label={p.metricsTitle}>
        <h4 className="label">{p.metricsTitle}</h4>
        <div className="pr-metrics">
          {[...steering, ...(own ? [own] : [])].map((m) => (
            <MetricCard key={m.id} m={m} weight={m.id === "ownership" ? undefined : weightOf(m.id)} titles={titles} onTurn={transcript ? goTurn : undefined} />
          ))}
        </div>
        <p className="xs faint row" style={{ gap: 6 }}>
          <Scale size={12} aria-hidden="true" />
          {p.bounded}
        </p>
      </section>

      {/* ---------------------------------------------------------- faults */}
      {(hasMission || r.faults.length > 0) && (
      <section className="stack-sm" aria-label={p.faultsTitle}>
        <h4 className="label row" style={{ gap: 6 }}>
          <Bug size={14} aria-hidden="true" />
          {p.faultsTitle}
        </h4>
        <p className="small muted">{audience === "self" ? p.faultsRevealSelf : p.faultsRevealRecruiter}</p>
        {r.faults.length === 0 ? (
          <p className="small muted">{p.noFaults}</p>
        ) : (
          <div className="table-wrap">
            <table className="table pr-faults">
              <thead>
                <tr>
                  <th scope="col">{p.colFault}</th>
                  <th scope="col">{p.colCategory}</th>
                  <th scope="col">{p.colAppeared}</th>
                  <th scope="col">{p.colDetected}</th>
                  <th scope="col">{p.colFixed}</th>
                  <th scope="col" title={p.methodHint}>
                    {p.colMethod}
                  </th>
                </tr>
              </thead>
              <tbody>
                {r.faults.map((f) => (
                  <tr key={f.id}>
                    <td className="small" style={{ minWidth: 200 }}>
                      {f.title}
                      {f.explanation && <div className="xs muted">{f.explanation}</div>}
                    </td>
                    <td className="xs">
                      {f.category}
                      {f.cwe && (
                        <>
                          {" "}
                          <span className="chip chip-plain pr-cwe">
                            <span>{f.cwe}</span>
                          </span>
                        </>
                      )}
                    </td>
                    <td className="small">
                      {f.injected_turn === null ? (
                        <span className="faint">{p.notAppeared}</span>
                      ) : (
                        <TurnLink n={f.injected_turn} onTurn={transcript ? goTurn : undefined} label={p.atTurn(f.injected_turn)} />
                      )}
                    </td>
                    <td>
                      <span className={cx("chip", f.detected ? "chip-ok" : "chip-neutral")}>
                        {f.detected ? <CheckCircle2 size={12} aria-hidden="true" /> : <XCircle size={12} aria-hidden="true" />}
                        <span>{f.detected ? p.yes : p.no}</span>
                      </span>
                      {f.detected && (
                        <div className="xs muted" style={{ marginTop: 4 }}>
                          {p.detectedBy[f.detected_by] ?? f.detected_by}
                          {f.detected_turn !== null && (
                            <>
                              {" · "}
                              <TurnLink n={f.detected_turn} onTurn={transcript ? goTurn : undefined} label={p.atTurn(f.detected_turn)} />
                            </>
                          )}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={cx("chip", f.fixed_at_close ? "chip-ok" : "chip-warn")}>
                        <span>{f.fixed_at_close ? p.yes : p.no}</span>
                      </span>
                    </td>
                    <td className="xs muted">{f.injection_method ? p.method[f.injection_method] ?? f.injection_method : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      )}

      {/* ---------------------------------------------------------- facts */}
      {(r.velocity || r.ownership || hasMission) && (
      <div className="grid-2 pr-facts" style={{ alignItems: "start" }}>
        {r.velocity && (
        <section className="pr-box" aria-label={p.velocityTitle}>
          <h4 className="label row" style={{ gap: 6 }}>
            <Gauge size={14} aria-hidden="true" />
            {p.velocityTitle}
          </h4>
          <dl className="kv">
            <dt>{p.iterations}</dt>
            <dd className="num">{p.iterationsVal(r.velocity.iterations, r.velocity.par)}</dd>
            <dt>{p.firstGreen}</dt>
            <dd>
              {r.velocity.first_green_turn === null ? (
                <span className="faint">{p.never}</span>
              ) : (
                <TurnLink n={r.velocity.first_green_turn} onTurn={transcript ? goTurn : undefined} label={p.atTurn(r.velocity.first_green_turn)} />
              )}
            </dd>
            <dt>{p.greenAtClose}</dt>
            <dd>{r.velocity.green_at_close ? p.yes : p.no}</dd>
            <dt>{p.regressions}</dt>
            <dd className="num">{r.velocity.regressions}</dd>
            <dt>{p.ciRuns}</dt>
            <dd className="num">{r.velocity.ci_runs}</dd>
            <dt>{p.minutes}</dt>
            <dd className="num">{p.duration(r.velocity.minutes_used)}</dd>
          </dl>
        </section>
        )}
        <section className="pr-box" aria-label={p.ownershipTitle}>
          <h4 className="label row" style={{ gap: 6 }}>
            <FileCode2 size={14} aria-hidden="true" />
            {p.ownershipTitle}
          </h4>
          {r.ownership ? (
            <>
              <span className={cx("chip", bandTone(r.ownership.band))} style={{ width: "max-content" }}>
                <UserCheck size={12} aria-hidden="true" />
                <span>{p.band[r.ownership.band] ?? r.ownership.band}</span>
              </span>
              <dl className="kv">
                <dt>{p.fn}</dt>
                <dd className="mono xs">
                  {r.ownership.function}() · {r.ownership.path} · {r.ownership.repository}
                </dd>
                <dt>{p.constraint}</dt>
                <dd>{p.constraints[r.ownership.constraint] ?? r.ownership.constraint}</dd>
                <dt title={p.hiddenHint}>{p.hidden}</dt>
                <dd>
                  <IdentList names={r.ownership.hidden_identifiers_used} empty={p.none} tone="chip-violet" />
                </dd>
                <dt>{p.visible}</dt>
                <dd>
                  <IdentList names={r.ownership.visible_identifiers_used} empty={p.none} tone="chip-plain" />
                </dd>
                <dt>{p.located}</dt>
                <dd>{r.ownership.location_precision ? p.yes : p.no}</dd>
                <dt>{p.explain}</dt>
                <dd className="num">{r.ownership.explain_requests}</dd>
                <dt>{p.implemented}</dt>
                <dd>{r.ownership.constraint_implemented ? p.yes : p.no}</dd>
                <dt>{p.firstPrompt}</dt>
                <dd className="num">{r.ownership.first_prompt_seconds === null ? "—" : p.seconds(r.ownership.first_prompt_seconds)}</dd>
                <dt>{p.used}</dt>
                <dd className="num">{r.ownership.seconds_used === null ? "—" : p.seconds(r.ownership.seconds_used)}</dd>
              </dl>
              <p className="xs faint">{p.hiddenHint}</p>
            </>
          ) : (
            <span className="chip chip-neutral" style={{ width: "max-content" }}>
              <span>{p.band.not_taken}</span>
            </span>
          )}
        </section>
      </div>
      )}

      {/* ---------------------------------------------------------- limits */}
      <section className="pr-box pr-limits" aria-label={p.limitsTitle}>
        <h4 className="label row" style={{ gap: 6 }}>
          <Info size={14} aria-hidden="true" />
          {p.limitsTitle}
        </h4>
        <ul>
          {r.limits.map((l) => (
            <li key={l}>{localizeLimit(l, t)}</li>
          ))}
        </ul>
        {r.judge_errors.length > 0 && (
          <>
            <b className="xs">{p.judgeErrors}</b>
            <ul>
              {r.judge_errors.map((e) => (
                <li key={e} className="mono xs">
                  {e}
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="notice">{r.notice}</p>
      </section>

      {transcript && transcript.length > 0 && (
        <details className="pr-transcript" ref={transcriptRef}>
          <summary className="label row" style={{ gap: 6 }}>
            <ScrollText size={14} aria-hidden="true" />
            {p.transcript} <span className="faint">({p.transcriptCount(transcript.length)})</span>
          </summary>
          <PilotTranscript turns={transcript} anchor={anchor} hl={hl} />
        </details>
      )}
    </div>
  );
}

function bandTone(band: string): string {
  return band === "knows_the_code" ? "chip-ok" : band === "partial" ? "chip-accent" : band === "navigates_blind" ? "chip-warn" : "chip-neutral";
}

function IdentList({ names, empty, tone }: { names: string[]; empty: string; tone: string }) {
  if (!names.length) return <span className="faint">{empty}</span>;
  return (
    <span className="chips">
      {names.map((n) => (
        <span key={n} className={cx("chip mono", tone)}>
          <span>{n}</span>
        </span>
      ))}
    </span>
  );
}

function TurnLink({ n, onTurn, label }: { n: number; onTurn?: (n: number) => void; label: string }) {
  const { t } = usePrefs();
  if (!onTurn) return <span className="num">{label}</span>;
  return (
    <button type="button" className="pr-turn-link num" onClick={() => onTurn(n)} aria-label={t.pilot.report.goTurnLabel(n)}>
      {label}
    </button>
  );
}

function MetricCard({
  m,
  weight,
  titles,
  onTurn,
}: {
  m: PilotMetric;
  weight: number | undefined;
  titles: Record<string, string>;
  onTurn?: (n: number) => void;
}) {
  const { t } = usePrefs();
  const p = t.pilot.report;
  const Icon = METRIC_ICON[m.id] ?? Gauge;
  const label = p.metricLabels[m.id] ?? m.label;
  const entries = Object.entries(m.breakdown);
  return (
    <article className={cx("pr-metric", m.id === "ownership" && "is-own")}>
      <header className="pr-metric-head">
        <span className="pr-metric-icon">
          <Icon size={16} aria-hidden="true" />
        </span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h5 className="pr-metric-title">{label}</h5>
          <span className="xs faint">{weight !== undefined ? p.weight(weight) : p.separate}</span>
        </div>
        <span className="pr-metric-v num">
          {Math.round(m.final_pct)}
          <small>%</small>
        </span>
      </header>
      <Meter value={m.final_pct} max={100} label={`${label}: ${m.final_pct.toFixed(1)} %`} color={m.id === "ownership" ? "var(--violet)" : pctColor(m.final_pct)} />
      <div className="pr-judge xs">
        <span>
          {p.factual} <b className="num">{m.factual_pct.toFixed(1)} %</b>
        </span>
        <span aria-hidden="true">·</span>
        <span>
          {p.judgeProposal}{" "}
          {m.judge_pct === null ? (
            <span className="faint">{p.judgeNoProposal}</span>
          ) : (
            <>
              <b className="num">{m.judge_pct.toFixed(1)} %</b>{" "}
              <span className={cx("chip", m.judge_applied ? "chip-violet" : "chip-neutral")}>
                <span>{m.judge_applied ? p.applied : p.notApplied}</span>
              </span>
            </>
          )}
        </span>
      </div>
      {entries.length > 0 && (
        <details className="pr-sub">
          <summary className="xs">{p.breakdown}</summary>
          <ul className="pr-breakdown">
            {entries.map(([k, v]) => {
              const neg = v < 0;
              const name = breakdownLabel(k, t, titles);
              return (
                <li key={k}>
                  <span className="xs">{name}</span>
                  <span className="pr-bar" aria-hidden="true">
                    <span className={neg ? "is-neg" : ""} style={{ width: `${Math.min(100, Math.abs(v))}%` }} />
                  </span>
                  <span className={cx("xs num", neg && v !== 0 && "pr-neg")}>{neg && v !== 0 ? `−${Math.abs(v).toFixed(1)}` : v.toFixed(1)}</span>
                </li>
              );
            })}
          </ul>
        </details>
      )}
      <div className="pr-evidence">
        <span className="xs faint">{p.evidence}</span>
        {m.evidence.length === 0 ? (
          <p className="xs faint">{p.noEvidence}</p>
        ) : (
          <ul>
            {m.evidence.map((e, i) => (
              <li key={i}>
                {e.turn !== null && <TurnLink n={e.turn} onTurn={onTurn} label={p.goTurn(e.turn)} />}
                {e.quote && <q className="pr-quote">{e.quote}</q>}
                <span className="xs muted">{localizeNote(e.note, t, titles)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {m.rationale && (
        <p className="xs">
          <b>{p.rationale}</b> — {m.rationale}
        </p>
      )}
    </article>
  );
}

// ------------------------------------------------------------------ technical test: sections, AI usage, questions

function SectionsSummary({ r }: { r: PilotReport }) {
  const { t } = usePrefs();
  const tt = t.tt.report;
  const qs = r.questions ?? [];
  const nK = qs.filter((q) => q.section === "knowledge").length;
  const nA = qs.filter((q) => q.section === "ai").length;
  const practice = r.scenario_id ? weightedMean(r, PRACTICE) : null;
  const tiles: { id: string; n: string; icon: LucideIcon; v: number | null; hint: string; empty: string; tone?: string; extra?: string }[] = [
    { id: "knowledge", n: "1", icon: Calculator, v: r.applied_knowledge_pct ?? null, hint: tt.tiles.knowledge, empty: nK ? "—" : tt.noQuestions },
    { id: "ai", n: "2", icon: Bot, v: r.ai_section_pct ?? null, hint: tt.tiles.ai, empty: nA ? "—" : tt.noQuestions },
    { id: "practice", n: "3", icon: Target, v: practice, hint: tt.tiles.practice, empty: tt.noMission },
    {
      id: "own",
      n: "",
      icon: UserCheck,
      v: r.authenticity_pct,
      hint: tt.tiles.own,
      empty: tt.notTaken,
      tone: "is-own",
      extra: r.own_work_pct !== null && r.own_work_pct !== undefined ? tt.ownWork(r.own_work_pct) : undefined,
    },
  ];
  return (
    <section className="stack-sm" aria-labelledby="tq-sections">
      <h4 id="tq-sections" className="label">
        {tt.sectionsTitle}
      </h4>
      <ul className="tq-tiles">
        {tiles.map(({ id, n, icon: Icon, v, hint, empty, tone, extra }) => {
          const name = id === "own" ? tt.ownTile : `${t.tt.sectionN(Number(n))} · ${t.tt.section[id]}`;
          return (
            <li key={id} className={cx("tq-tile", tone, v === null && "is-empty")}>
              <div className="row" style={{ gap: 8 }}>
                <span className="tq-tile-icon" aria-hidden="true">
                  <Icon size={15} />
                </span>
                <span className="tq-tile-name">{name}</span>
              </div>
              {v === null ? (
                <span className="tq-tile-empty">{empty}</span>
              ) : (
                <>
                  <span className="tq-tile-v num">
                    {Math.round(v)}
                    <small>%</small>
                  </span>
                  <Meter value={v} max={100} label={`${name}: ${v.toFixed(1)} %`} color={id === "own" ? "var(--violet)" : pctColor(v)} />
                </>
              )}
              <span className="xs faint">{hint}</span>
              {extra && <span className="xs muted">{extra}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function AiUsagePanel({ r }: { r: PilotReport }) {
  const { t } = usePrefs();
  const tt = t.tt.report;
  const u = r.ai_usage;
  const nAi = (r.questions ?? []).filter((q) => q.section === "ai").length || u?.questions || 0;
  const lines: string[] = [];
  if (u) {
    if (u.consulted === 0) lines.push(tt.usage.none(nAi));
    else {
      lines.push(tt.usage.consulted(u.consulted, nAi));
      lines.push(tt.usage.perQuestion(u.prompts_per_consulted));
      if (u.pasted_verbatim > 0) lines.push(tt.usage.pasted(u.pasted_verbatim));
      lines.push(tt.usage.challenges(u.challenges));
      if (u.trapped_consulted > 0) {
        lines.push(tt.usage.followed(u.trapped_followed, u.trapped_consulted));
        lines.push(tt.usage.caught(u.trapped_caught, u.trapped_consulted));
      } else lines.push(tt.usage.noTrap);
      if (u.answered_against_ai > 0) lines.push(tt.usage.against(u.answered_against_ai));
    }
  }
  return (
    <section className="pr-box tq-usage" aria-labelledby="tq-usage-h">
      <h4 id="tq-usage-h" className="label row" style={{ gap: 6 }}>
        <MessagesSquare size={14} aria-hidden="true" />
        {tt.aiUsageTitle}
      </h4>
      {lines.length === 0 ? (
        <p className="small muted">{tt.usage.none(nAi)}</p>
      ) : (
        <ul className="tq-usage-list">
          {lines.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
      <p className="xs faint row" style={{ gap: 6 }}>
        <Info size={12} aria-hidden="true" />
        {tt.aiUsageNote}
      </p>
    </section>
  );
}

function ResultChip({ q }: { q: PilotQuestionOutcome }) {
  const { t } = usePrefs();
  const tt = t.tt.report;
  if (q.late)
    return (
      <span className="chip chip-neutral">
        <Timer size={12} aria-hidden="true" />
        <span>{tt.late}</span>
      </span>
    );
  if (q.score >= 1)
    return (
      <span className="chip chip-ok">
        <CheckCircle2 size={12} aria-hidden="true" />
        <span>{tt.right}</span>
      </span>
    );
  if (q.score > 0)
    return (
      <span className="chip chip-accent">
        <span>{tt.partial(q.score * 100)}</span>
      </span>
    );
  return (
    <span className="chip chip-neutral">
      <XCircle size={12} aria-hidden="true" />
      <span>{tt.wrong}</span>
    </span>
  );
}

function QuestionsTable({ r, audience }: { r: PilotReport; audience: "self" | "recruiter" }) {
  const { t } = usePrefs();
  const tt = t.tt.report;
  const qs = r.questions ?? [];
  return (
    <section className="stack-sm tq-questions" aria-labelledby="tq-q-h">
      <h4 id="tq-q-h" className="label row" style={{ gap: 6 }}>
        <ListChecks size={14} aria-hidden="true" />
        {tt.questionsTitle}
      </h4>
      <div className="table-wrap">
        <table className="table tq-table">
          <thead>
            <tr>
              <th scope="col">{tt.col.n}</th>
              <th scope="col">{tt.col.section}</th>
              <th scope="col">{tt.col.skill}</th>
              <th scope="col">{tt.col.result}</th>
              <th scope="col">{tt.col.time}</th>
              <th scope="col">{tt.col.consulted}</th>
              <th scope="col">{tt.col.trapped}</th>
              <th scope="col">{tt.col.followed}</th>
            </tr>
          </thead>
          <tbody>
            {qs.map((q) => {
              const ai = q.section === "ai";
              return (
                <tr key={q.index}>
                  <td className="num">{q.index + 1}</td>
                  <td className="xs">
                    <span className={cx("chip", ai ? "chip-violet" : "chip-plain")}>
                      <span>
                        {ai ? "2" : "1"} · {t.tt.section[q.section]}
                      </span>
                    </span>
                  </td>
                  <td className="small" style={{ minWidth: 140 }}>
                    {q.skill}
                    {q.personal && (
                      <>
                        {" "}
                        <span className="chip chip-violet">
                          <UserCheck size={11} aria-hidden="true" />
                          <span>{tt.personal}</span>
                        </span>
                      </>
                    )}
                  </td>
                  <td>
                    <ResultChip q={q} />
                  </td>
                  <td className="xs num" style={{ whiteSpace: "nowrap" }}>
                    {tt.seconds(q.seconds_used, q.seconds)}
                  </td>
                  <td className="xs">{ai ? tt.consultedN(q.consulted_ai) : "—"}</td>
                  <td className="xs">
                    {ai ? (
                      q.trapped ? (
                        <span className="chip chip-warn">
                          <AlertTriangle size={11} aria-hidden="true" />
                          <span>{tt.yes}</span>
                        </span>
                      ) : (
                        tt.no
                      )
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="xs" style={{ minWidth: 120 }}>
                    {ai && q.consulted_ai > 0 ? (
                      <div className="tq-follow">
                        {q.trapped && <span className={q.followed_ai ? "tq-followed" : "tq-not-followed"}>{q.followed_ai ? tt.followedYes : tt.followedNo}</span>}
                        {q.challenged && <span className="muted">{tt.challenged}</span>}
                        {q.conceded && <span className="muted">{tt.conceded}</span>}
                        {!q.trapped && !q.challenged && <span className="faint">—</span>}
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="xs faint">{audience === "self" ? tt.trapRevealSelf : tt.trapRevealRecruiter}</p>
    </section>
  );
}

// Evaluation report of an AI-pilot test. Shared by the sandbox end screen (audience "self") and the
// recruiter report (audience "recruiter"). Factual numbers and the judge's bounded adjustment are always
// shown side by side, every piece of evidence links to the transcript turn it cites.
import { useId, useRef, useState } from "react";
import {
  AlertTriangle,
  Bug,
  CheckCircle2,
  Compass,
  FileCode2,
  Gauge,
  Info,
  Scale,
  ScrollText,
  Search,
  Timer,
  UserCheck,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { PilotMetric, PilotReport, PilotTurn } from "../api/types";
import type { Dict } from "../i18n";
import { usePrefs } from "../lib/prefs";
import { cx } from "../lib/format";
import { Meter, ScoreRing } from "./charts";
import { PilotTranscript } from "./PilotTurns";

const METRIC_ICON: Record<string, LucideIcon> = {
  intent_precision: Compass,
  critical_thinking: Search,
  orchestration_velocity: Zap,
  ownership: UserCheck,
};

/** The backend's evidence notes are fixed English templates: localise the known ones, keep others as is. */
export function localizeNote(note: string, t: Dict, titles: Record<string, string>): string {
  const n = t.pilot.report.notes;
  const f = (id: string | undefined) => (id ? titles[id] ?? id : "");
  let m: RegExpExecArray | null;
  if (note === "no instruction was given to the assistant") return n.noInstruction;
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
  const i = ENGLISH_LIMITS.findIndex((p) => limit.startsWith(p));
  return i >= 0 ? t.pilot.report.limits[i] ?? limit : limit;
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
  const steering = r.metrics.filter((m) => m.id !== "ownership");
  const own = r.metrics.find((m) => m.id === "ownership");

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
          <ScoreRing value={r.pilot_index_pct} size={audience === "self" ? 148 : 112} glow={audience === "self"} caption={p.indexShort} label={`${p.index} ${r.pilot_index_pct.toFixed(1)} %`} />
          <ScoreRing
            value={r.authenticity_pct}
            size={audience === "self" ? 104 : 84}
            color="var(--violet)"
            caption={p.authenticity}
            label={`${p.authenticity} ${r.authenticity_pct === null ? p.notTaken : `${r.authenticity_pct.toFixed(1)} %`}`}
          />
        </div>
        <div className="stack-sm" style={{ minWidth: 0, flex: 1 }}>
          <span className="eyebrow">
            {p.scenario} · {r.job_title}
          </span>
          <h3 className="pr-title">{r.scenario_title}</h3>
          <div className="row wrap" style={{ gap: 8 }}>
            <span className="chip chip-accent">
              <span>{t.pilot.levels[r.level]}</span>
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
                {p.judge} · {r.judge === "none" ? p.judgeNone : r.judge}
              </span>
            </span>
          </div>
          <p className="xs faint">
            {p.indexHint} {r.authenticity_pct === null ? `${p.authenticity} — ${p.notTaken}.` : p.authenticityHint}
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

      {/* ---------------------------------------------------------- metrics */}
      <section className="stack" aria-label={p.metricsTitle}>
        <h4 className="label">{p.metricsTitle}</h4>
        <div className="pr-metrics">
          {[...steering, ...(own ? [own] : [])].map((m) => (
            <MetricCard key={m.id} m={m} weight={r.weights[m.id]} titles={titles} onTurn={transcript ? goTurn : undefined} />
          ))}
        </div>
        <p className="xs faint row" style={{ gap: 6 }}>
          <Scale size={12} aria-hidden="true" />
          {p.bounded}
        </p>
      </section>

      {/* ---------------------------------------------------------- faults */}
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

      {/* ---------------------------------------------------------- facts */}
      <div className="grid-2 pr-facts" style={{ alignItems: "start" }}>
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
              const name = p.breakdownLabels[k] ?? titles[k] ?? k;
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

// Results of a verification test: overall score, verified level per skill, authorship, integrity, per question.
// Shared by the sandbox end screen (audience "self") and the recruiter report (audience "recruiter").
// Correct answers are never shown: every test is unique and must stay so.
import { AlertTriangle, CheckCircle2, Clock, Fingerprint, ShieldCheck, ShieldAlert, UserCheck } from "lucide-react";
import type { AssessResults, IntegritySummary } from "../api/types";
import { usePrefs } from "../lib/prefs";
import { cx } from "../lib/format";
import { Meter, ScoreFigure } from "./charts";

export function RiskBadge({ risk }: { risk: IntegritySummary["risk"] }) {
  const { t } = usePrefs();
  const tone = risk === "low" ? "chip-ok" : risk === "medium" ? "chip-warn" : "chip-danger";
  const Icon = risk === "low" ? ShieldCheck : ShieldAlert;
  return (
    <span className={cx("chip", tone)}>
      <Icon size={12} aria-hidden="true" />
      <span>{t.test.risk[risk] ?? risk}</span>
    </span>
  );
}

export function IntegrityPanel({ integrity, note }: { integrity: IntegritySummary; note: string }) {
  const { t } = usePrefs();
  // "returned" events (focus, visible, fullscreen_enter) are context, not signals
  const neutral = new Set(["focus", "visibility_visible", "fullscreen_enter"]);
  const events = Object.entries(integrity.events).filter(([k, n]) => n > 0 && !neutral.has(k));
  return (
    <div className="integrity">
      <div className="row wrap" style={{ gap: 8 }}>
        <Fingerprint size={16} aria-hidden="true" style={{ color: "var(--accent-text)" }} />
        <b className="small">{t.test.integrity}</b>
        <RiskBadge risk={integrity.risk} />
      </div>
      {integrity.notes.length > 0 && (
        <ul className="integrity-notes">
          {integrity.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {(events.length > 0 || integrity.late_answers > 0 || integrity.too_fast_answers > 0) && (
        <ul className="chips" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {events.map(([k, n]) => (
            <li key={k} className="chip chip-plain">
              <span>
                {t.test.events[k] ?? k} · <b className="num">{n}</b>
              </span>
            </li>
          ))}
          {integrity.late_answers > 0 && (
            <li className="chip chip-plain">
              <span>{t.test.lateN(integrity.late_answers)}</span>
            </li>
          )}
          {integrity.too_fast_answers > 0 && (
            <li className="chip chip-plain">
              <span>{t.test.fastN(integrity.too_fast_answers)}</span>
            </li>
          )}
        </ul>
      )}
      <p className="xs faint row" style={{ gap: 6 }}>
        <AlertTriangle size={12} aria-hidden="true" />
        {note}
      </p>
    </div>
  );
}

export function AssessResultsView({ results: r, audience }: { results: AssessResults; audience: "self" | "recruiter" }) {
  const { t } = usePrefs();
  const lv = t.test.verifiedLevels;
  return (
    <div className="stack">
      <div className="assess-head">
        <ScoreFigure value={r.overall_pct} size={audience === "self" ? "lg" : "md"} caption={t.test.overall} />
        <div className="stack-sm" style={{ minWidth: 0, flex: 1 }}>
          <div className="row wrap" style={{ gap: 8 }}>
            <span className="chip chip-plain">
              <span>
                {t.test.level} · {t.test.levels[r.level]}
              </span>
            </span>
            {r.authorship_pct !== null && (
              <span className={cx("chip", r.authorship_pct >= 50 ? "chip-ok" : "chip-warn")}>
                <UserCheck size={12} aria-hidden="true" />
                <span>
                  {audience === "self" ? t.test.authorship : t.verif.authorship} · <b className="num">{Math.round(r.authorship_pct)} %</b>
                </span>
              </span>
            )}
            {r.duration_seconds > 0 && (
              <span className="chip chip-plain">
                <Clock size={12} aria-hidden="true" />
                <span className="num">
                  {r.duration_seconds >= 60 ? `${Math.floor(r.duration_seconds / 60)} min ${String(Math.round(r.duration_seconds % 60)).padStart(2, "0")} s` : `${Math.round(r.duration_seconds)} s`}
                </span>
              </span>
            )}
          </div>
          <ul className="verified-list">
            {r.skills.map((s) => (
              <li key={s.skill_id}>
                <span className="vl-label">{s.label}</span>
                <span className="vl-bar">
                  <Meter value={s.score_pct} max={100} label={`${s.label}: ${s.score_pct.toFixed(0)} %`} color={s.verified_level > 0 ? "var(--ok)" : "var(--neutral)"} />
                </span>
                <span className={cx("chip", s.verified_level >= 2 ? "chip-ok" : s.verified_level === 1 ? "chip-accent" : "chip-neutral")}>
                  {s.verified_level > 0 && <CheckCircle2 size={12} aria-hidden="true" />}
                  <span>{lv[s.verified_level]}</span>
                </span>
              </li>
            ))}
          </ul>
          {r.untestable_skills.length > 0 && <p className="xs faint">{t.verif.untestable(r.untestable_skills.join(", "))}</p>}
        </div>
      </div>

      <IntegrityPanel integrity={r.integrity} note={audience === "self" ? t.test.integrityNote : t.verif.integrityNote} />

      <details className="assess-detail" open={audience === "self"}>
        <summary className="label">{t.test.perQuestion}</summary>
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t.test.colQuestion}</th>
                <th scope="col">{t.test.colSkill}</th>
                <th scope="col">{t.test.colResult}</th>
                <th scope="col">{t.test.colTime}</th>
              </tr>
            </thead>
            <tbody>
              {r.questions.map((q) => {
                const res = q.late ? t.test.lateRes : q.score >= 0.999 ? t.test.correct : q.score > 0 ? t.test.partial : t.test.wrong;
                const tone = q.late ? "chip-warn" : q.score >= 0.999 ? "chip-ok" : q.score > 0 ? "chip-accent" : "chip-neutral";
                return (
                  <tr key={q.index}>
                    <td className="num">{q.index + 1}</td>
                    <td className="small">
                      {q.skill}
                      {q.personal && <UserCheck size={12} aria-hidden="true" style={{ marginLeft: 6, color: "var(--violet-text)", verticalAlign: -1 }} />}
                    </td>
                    <td>
                      <span className={cx("chip", tone)}>
                        <span>{res}</span>
                      </span>
                    </td>
                    <td className="num small">
                      {t.test.seconds(q.seconds_used)}
                      {q.seconds ? <span className="xs faint"> / {t.test.seconds(q.seconds)}</span> : null}
                      {q.too_fast && <span className="xs faint"> · {t.test.tooFast}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {audience === "self" && <p className="xs faint" style={{ marginTop: 8 }}>{t.test.noAnswers}</p>}
      </details>
    </div>
  );
}

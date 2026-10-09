// Report actions (explanation link, GDPR export, PDF) and the print-only report document.
import { useState } from "react";
import { ClipboardCopy, FileDown, Link2, Loader2, Printer, ShieldCheck } from "lucide-react";
import { api, BASE_PATH } from "../api/client";
import type { CandidateAssessment, CandidatePilot, DashboardReport, ExplanationLink } from "../api/types";
import { usePrefs, useToast } from "../lib/prefs";
import { dateTime, levelIndex } from "../lib/format";
import { printDoc } from "../lib/print";
import { Gate, Modal } from "../components/feedback";
import { ScoreRing } from "../components/charts";
import { Logo } from "../components/Shell";

export function ReportActions({ report, onLinkCreated }: { report: DashboardReport; onLinkCreated?: () => void }) {
  const { t } = usePrefs();
  const toast = useToast();
  const [linkOpen, setLinkOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportJson = async () => {
    setExporting(true);
    try {
      await api.exportCandidate(report.candidate_ref);
      toast.push("success", t.ops.exported, report.candidate_ref);
    } catch (e) {
      toast.error(e);
    } finally {
      setExporting(false);
    }
  };
  return (
    <div className="report-actions no-print" role="group" aria-label={t.ops.actions}>
      <Gate perm="decide">
        {(ok) => (
          <button className="btn" onClick={() => setLinkOpen(true)} disabled={!ok}>
            <Link2 size={16} aria-hidden="true" />
            {t.ops.explainLink}
          </button>
        )}
      </Gate>
      <Gate perm="privacy">
        {(ok) => (
          <button className="btn" onClick={exportJson} disabled={!ok || exporting} title={ok ? t.ops.exportHint : undefined}>
            {exporting ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <FileDown size={16} aria-hidden="true" />}
            {t.ops.exportJson}
          </button>
        )}
      </Gate>
      <button className="btn" onClick={printDoc} title={t.ops.pdfHint}>
        <Printer size={16} aria-hidden="true" />
        {t.ops.pdf}
      </button>
      {linkOpen && (
        <ExplanationLinkModal
          candidateRef={report.candidate_ref}
          onClose={() => {
            setLinkOpen(false);
            onLinkCreated?.();
          }}
        />
      )}
    </div>
  );
}

function ExplanationLinkModal({ candidateRef, onClose }: { candidateRef: string; onClose: () => void }) {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<ExplanationLink | null>(null);
  const url = link ? `${window.location.origin}${BASE_PATH}${link.path}` : "";
  const create = async () => {
    setBusy(true);
    try {
      setLink(await api.explanationLink(candidateRef, days));
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const copy = () =>
    void navigator.clipboard
      ?.writeText(url)
      .then(() => toast.push("success", t.ops.copied))
      .catch(() => undefined);
  return (
    <Modal
      title={t.ops.explainTitle}
      onClose={onClose}
      footer={
        link ? (
          <button className="btn" onClick={onClose}>
            {t.common.close}
          </button>
        ) : (
          <>
            <button className="btn btn-ghost" onClick={onClose}>
              {t.common.cancel}
            </button>
            <button className="btn btn-primary" onClick={create} disabled={busy}>
              {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Link2 size={16} aria-hidden="true" />}
              {t.ops.createLink}
            </button>
          </>
        )
      }
    >
      <p className="callout callout-neutral">
        <ShieldCheck size={16} aria-hidden="true" />
        <span>{t.ops.explainIntro}</span>
      </p>
      {link ? (
        <div className="field">
          <label htmlFor="xl-url">{t.ops.url}</label>
          <div className="row" style={{ gap: 6 }}>
            <input id="xl-url" className="input mono" readOnly value={url} onFocus={(e) => e.target.select()} />
            <button type="button" className="btn" onClick={copy}>
              <ClipboardCopy size={16} aria-hidden="true" />
              {t.common.copy}
            </button>
          </div>
          <p className="hint">{t.ops.expires(dateTime(link.expires_at, lang))}</p>
        </div>
      ) : (
        <div className="field" style={{ maxWidth: 220 }}>
          <label htmlFor="xl-days">{t.ops.validity}</label>
          <select id="xl-days" className="select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[7, 30, 90].map((d) => (
              <option key={d} value={d}>
                {t.ops.days(d)}
              </option>
            ))}
          </select>
        </div>
      )}
    </Modal>
  );
}

/** The full report as a print document: shown only when printing via `printDoc()`. */
export function ReportPrintDoc({
  report: r,
  tests = [],
  pilots = [],
}: {
  report: DashboardReport;
  tests?: CandidateAssessment[];
  pilots?: CandidatePilot[];
}) {
  const { t, lang } = usePrefs();
  const credW = r.credentials.weight_applied;
  return (
    <article className="print-doc" aria-hidden="true">
      <header className="pd-head">
        <div className="pd-brand">
          <Logo size={22} />
          <span>TalentEngine‑AI · {t.ops.printTitle}</span>
          <span className="pd-date">{t.ops.printGenerated(dateTime(new Date().toISOString(), lang))}</span>
        </div>
        <div className="pd-hero">
          <ScoreRing value={r.compatibility_pct} size={104} stroke={9} caption={t.report.compatibility} />
          <div>
            <p className="pd-job">
              {r.job_title} · {r.job_id}
            </p>
            <h1 className="pd-ref">{r.candidate_ref}</h1>
            <p>
              {t.report.skills} <b>{r.skills_component_pct.toFixed(1)} %</b> ({Math.round((1 - credW) * 100)} %) · {t.report.credentials}{" "}
              <b>{r.credentials_component_pct.toFixed(1)} %</b> ({Math.round(credW * 100)} %) · {t.report.confidence}{" "}
              <b>{Math.round(r.confidence * 100)} %</b> · {t.band[r.evidence_band]}
            </p>
            <p className="pd-small">{t.report.generated(dateTime(r.generated_at, lang))}</p>
          </div>
        </div>
        {r.warnings.length > 0 && (
          <ul className="pd-warn">
            {r.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
      </header>

      <section className="pd-section">
        <h2>{t.report.criteria}</h2>
        <table className="pd-table">
          <thead>
            <tr>
              <th>{t.pipeline.criterion}</th>
              <th>{t.studio.importance}</th>
              <th>{t.report.required}</th>
              <th>{t.report.observed}</th>
              <th>{t.ops.status}</th>
            </tr>
          </thead>
          <tbody>
            {r.criteria.map((c) => (
              <tr key={c.skill_id}>
                <td>
                  {c.label}
                  {c.recruiter_note && <div className="pd-small">{c.recruiter_note}</div>}
                </td>
                <td>{t.importance[c.importance]}</td>
                <td>
                  {c.required_level.toFixed(2)} · {t.levels[levelIndex(c.required_level)]}
                </td>
                <td>
                  {c.observed_level.toFixed(2)} · {t.levels[levelIndex(c.observed_level)]}
                </td>
                <td>{t.crit[c.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="pd-section">
        <h2>{t.report.proofs}</h2>
        {r.validated_skills.map((v) => (
          <div key={v.skill_id} className="pd-skill">
            <h3>
              {v.label} — {v.level_label} ({v.level.toFixed(2)}) · {t.report.confidence} {Math.round(v.confidence * 100)} % ·{" "}
              {t.report.source[v.source]}
            </h3>
            <p>{v.statement}</p>
            {v.evidence.map((e, i) => (
              <div key={`${e.artifact_id}-${i}`} className="pd-ev">
                <div className="pd-small">
                  {e.artifact_label} · {e.locator} · {e.artifact_id}
                </div>
                {e.excerpt && <pre>{e.excerpt}</pre>}
              </div>
            ))}
          </div>
        ))}
      </section>

      {r.gaps.length > 0 && (
        <section className="pd-section">
          <h2>{t.report.gaps}</h2>
          <ul>
            {r.gaps.map((g) => (
              <li key={g.skill_id}>
                <b>{g.label}</b> ({t.importance[g.importance]}){g.declared_by_candidate ? ` — ${t.report.declared}` : ""} : {g.suggestion}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="pd-section">
        <h2>{t.report.guide}</h2>
        {r.interview_guide.map((q, i) => (
          <div key={`${q.skill_id}-${i}`} className="pd-q">
            <h3>
              {i + 1}. {q.question}
            </h3>
            <p className="pd-small">
              {t.report.purpose} : {q.purpose}
            </p>
            <div className="pd-cols">
              <div>
                <b className="pd-small">{t.report.keyPoints}</b>
                <ul className="pd-checks">
                  {q.expected_key_points.map((k) => (
                    <li key={k}>☐ {k}</li>
                  ))}
                </ul>
              </div>
              <div>
                <b className="pd-small">{t.report.warningSigns}</b>
                <ul>
                  {q.warning_signs.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
            <p className="pd-small">
              {t.report.refersTo} : {q.evidence.artifact_label} · {q.evidence.locator}
            </p>
          </div>
        ))}
      </section>

      <section className="pd-section">
        <h2>{t.report.credPanel}</h2>
        {r.credentials.items.length === 0 ? (
          <p>{t.report.credEmpty}</p>
        ) : (
          <ul>
            {r.credentials.items.map((c, i) => (
              <li key={`${c.label}-${i}`}>
                {c.kind === "degree" ? t.report.degree : t.report.certification} : {c.label}
                {c.supported_by_document ? ` (${t.docs.supported})` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>

      {pilots.some((s) => s.report) && (
        <section className="pd-section">
          <h2>{t.tt.name}</h2>
          {pilots
            .filter((s) => s.report)
            .map((s) => {
              const pr = s.report!;
              const pp = t.pilot.report;
              const tr = t.tt.report;
              const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v)} %`);
              const u = pr.ai_usage;
              const qs = pr.questions ?? [];
              const nAi = qs.filter((q) => q.section === "ai").length;
              return (
                <div key={s.id} className="pd-q">
                  <h3>
                    {tr.overall} {pr.pilot_index_pct.toFixed(0)} %
                    {pr.authenticity_pct !== null ? ` · ${pp.authenticity} ${Math.round(pr.authenticity_pct)} %` : ""} ·{" "}
                    {pr.scenario_title || tr.questionsOnly} · {t.pilot.levels[pr.level]} · {s.id}
                  </h3>
                  <p className="pd-small">
                    {t.tt.sectionN(1)} {t.tt.section.knowledge} {pct(pr.applied_knowledge_pct)} · {t.tt.sectionN(2)} {t.tt.section.ai}{" "}
                    {pct(pr.ai_section_pct)} · {t.tt.sectionN(3)} {t.tt.section.practice} {pr.scenario_id ? "" : tr.noMission}
                    {pr.own_work_pct !== null && pr.own_work_pct !== undefined ? ` · ${tr.ownWork(pr.own_work_pct)}` : ""}
                  </p>
                  <table className="pd-table">
                    <tbody>
                      {pr.metrics.map((m) => (
                        <tr key={m.id}>
                          <td>{pp.metricLabels[m.id] ?? m.label}</td>
                          <td>{m.final_pct.toFixed(0)} %</td>
                          <td>
                            {pp.factual} {m.factual_pct.toFixed(0)} %
                            {m.judge_pct !== null ? ` · ${pp.judgeProposal} ${m.judge_pct.toFixed(0)} % (${m.judge_applied ? pp.applied : pp.notApplied})` : ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {qs.length > 0 && (
                    <table className="pd-table">
                      <thead>
                        <tr>
                          <th>{tr.col.n}</th>
                          <th>{tr.col.section}</th>
                          <th>{tr.col.skill}</th>
                          <th>{tr.col.result}</th>
                          <th>{tr.col.time}</th>
                          <th>{tr.col.consulted}</th>
                          <th>{tr.col.trapped}</th>
                          <th>{tr.col.followed}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {qs.map((q) => {
                          const ai = q.section === "ai";
                          return (
                            <tr key={q.index}>
                              <td>{q.index + 1}</td>
                              <td>{t.tt.section[q.section]}</td>
                              <td>
                                {q.skill}
                                {q.personal ? ` (${tr.personal})` : ""}
                              </td>
                              <td>{q.late ? tr.late : q.score >= 1 ? tr.right : q.score > 0 ? tr.partial(q.score * 100) : tr.wrong}</td>
                              <td>{tr.seconds(q.seconds_used, q.seconds)}</td>
                              <td>{ai ? tr.consultedN(q.consulted_ai) : "—"}</td>
                              <td>{ai ? (q.trapped ? tr.yes : tr.no) : "—"}</td>
                              <td>
                                {ai && q.trapped && q.consulted_ai > 0 ? (q.followed_ai ? tr.followedYes : tr.followedNo) : "—"}
                                {q.challenged ? ` · ${tr.challenged}` : ""}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                  {u && nAi > 0 && (
                    <p className="pd-small">
                      <b>{tr.aiUsageTitle} —</b>{" "}
                      {u.consulted === 0
                        ? tr.usage.none(nAi)
                        : [
                            tr.usage.consulted(u.consulted, nAi),
                            tr.usage.challenges(u.challenges),
                            ...(u.pasted_verbatim ? [tr.usage.pasted(u.pasted_verbatim)] : []),
                            u.trapped_consulted ? tr.usage.followed(u.trapped_followed, u.trapped_consulted) : tr.usage.noTrap,
                          ].join(" ; ")}
                      . <i>{tr.aiUsageNote}</i>
                    </p>
                  )}
                  {pr.faults.length > 0 && (
                    <table className="pd-table">
                      <tbody>
                        {pr.faults.map((f) => (
                          <tr key={f.id}>
                            <td>
                              {f.title} <span className="pd-small">({f.category}{f.cwe ? ` · ${f.cwe}` : ""})</span>
                            </td>
                            <td>
                              {pp.colDetected} {f.detected ? `${pp.yes} — ${pp.detectedBy[f.detected_by] ?? f.detected_by}` : pp.no}
                            </td>
                            <td>
                              {pp.colFixed} — {f.fixed_at_close ? pp.yes : pp.no}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {(pr.velocity || pr.ownership) && (
                    <p className="pd-small">
                      {pr.velocity
                        ? `${pp.iterations} ${pp.iterationsVal(pr.velocity.iterations, pr.velocity.par)} · ${pp.greenAtClose} — ${pr.velocity.green_at_close ? pp.yes : pp.no}`
                        : ""}
                      {pr.ownership ? `${pr.velocity ? " · " : ""}${pp.ownershipTitle} — ${pp.band[pr.ownership.band] ?? pr.ownership.band}` : ""}
                    </p>
                  )}
                  <p className="pd-small">
                    <b>{pp.signal}</b> {pp.bounded}
                  </p>
                </div>
              );
            })}
        </section>
      )}

      {tests.some((a) => a.results) && (
        <section className="pd-section">
          <h2>
            {t.verif.title} — {t.tt.panel.legacyTitle}
          </h2>
          {tests
            .filter((a) => a.results)
            .map((a) => {
              const res = a.results!;
              return (
                <div key={a.id} className="pd-q">
                  <h3>
                    {t.test.overall} {res.overall_pct.toFixed(0)} % · {t.test.level} {t.test.levels[res.level]}
                    {res.authorship_pct !== null ? ` · ${t.verif.authorship} ${Math.round(res.authorship_pct)} %` : ""} · {a.id}
                  </h3>
                  <table className="pd-table">
                    <tbody>
                      {res.skills.map((sk) => (
                        <tr key={sk.skill_id}>
                          <td>{sk.label}</td>
                          <td>{sk.score_pct.toFixed(0)} %</td>
                          <td>
                            {t.test.verified} : {t.test.verifiedLevels[sk.verified_level]}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="pd-small">
                    {t.test.integrity} : {t.test.risk[res.integrity.risk]} — {res.integrity.notes.join(" ")}
                  </p>
                  <p className="pd-small">
                    <b>{t.verif.integrityNote}</b>
                  </p>
                </div>
              );
            })}
        </section>
      )}

      {r.decision && (
        <section className="pd-section">
          <h2>{t.report.decisionTitle}</h2>
          <p>
            <b>{t.decision[r.decision.decision]}</b> — {t.report.decisionBy(r.decision.reviewer, dateTime(r.decision.decided_at, lang))}
          </p>
          <p>{r.decision.rationale}</p>
        </section>
      )}

      <footer className="pd-foot">
        <p>{r.notice}</p>
        <p className="pd-small">
          {t.ops.printFooter} : <span className="pd-mono">{r.audit.entry_hash}</span>
        </p>
        <p className="pd-small">
          {t.report.ledgerEntry} {r.audit.ledger_entry_id} · {t.report.engine} {r.audit.engine_version} · {t.report.configVersion} v
          {r.audit.job_config_version}
        </p>
      </footer>
    </article>
  );
}

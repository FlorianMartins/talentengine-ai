// Report section (v0.6): AI-pilot test links for this candidate, live flaw arming, reports and transcripts.
import { useState } from "react";
import { Bug, ClipboardCopy, Link2, Loader2, ScrollText, Workflow } from "lucide-react";
import { api, BASE_PATH, pilot } from "../api/client";
import type { AssessLevel, CandidatePilot, PilotCatalog, PilotLink } from "../api/types";
import { useAsync, usePrefs, useToast, type Async } from "../lib/prefs";
import { cx, dateTime } from "../lib/format";
import { Gate, Modal, Skeleton } from "../components/feedback";
import { RangeField, Segmented, SwitchRow } from "../components/controls";
import { PilotReportView } from "../components/PilotReportView";
import { PilotTranscript } from "../components/PilotTurns";

const RUNNING = new Set(["brief", "build", "ownership"]);

export function PilotPanel({ candidateRef, sessions }: { candidateRef: string; sessions: Async<CandidatePilot[]> }) {
  const { t, lang } = usePrefs();
  const p = t.pilot.panel;
  const toast = useToast();
  const catalog = useAsync(() => pilot.scenarios(lang).catch(() => null), [lang]);
  const cat = catalog.data;
  const [level, setLevel] = useState<AssessLevel>(2);
  const [scenario, setScenario] = useState("");
  const [faults, setFaults] = useState<string[]>([]);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [ownership, setOwnership] = useState(true);
  const [hours, setHours] = useState(72);
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<PilotLink | null>(null);
  const chosen = cat?.scenarios.find((s) => s.id === scenario);
  const defaultMinutes = cat?.build_minutes[String(level)] ?? 25;
  const perLevel = cat?.faults_per_level[String(level)] ?? 2;

  const create = async () => {
    setBusy(true);
    try {
      setLink(
        await api.createPilot(candidateRef, {
          level,
          scenario_id: scenario || undefined,
          fault_ids: scenario ? faults : [],
          build_minutes: minutes,
          ownership,
          valid_hours: hours,
        }),
      );
      sessions.reload();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const url = link ? `${window.location.origin}${BASE_PATH}${link.path}` : "";
  const list = sessions.data ?? [];

  return (
    <section className="panel" aria-labelledby="r-pilot">
      <div>
        <h2 id="r-pilot" className="panel-title">
          <Workflow size={18} aria-hidden="true" />
          {p.title}
        </h2>
        <p className="panel-hint">{p.hint}</p>
      </div>

      <details className="verif-create no-print">
        <summary className="btn btn-sm">
          <Link2 size={14} aria-hidden="true" />
          {p.create}
        </summary>
        <div className="verif-form">
          <div className="field">
            <span className="label">{p.level}</span>
            <Segmented<"1" | "2" | "3">
              label={p.level}
              value={String(level) as "1" | "2" | "3"}
              onChange={(v) => setLevel(Number(v) as AssessLevel)}
              options={[1, 2, 3].map((v) => ({ value: String(v) as "1" | "2" | "3", label: t.pilot.levels[v] ?? "" }))}
            />
          </div>
          <div className="field">
            <label htmlFor="pp-sc">{p.scenario}</label>
            <select
              id="pp-sc"
              className="select"
              value={scenario}
              onChange={(e) => {
                setScenario(e.target.value);
                setFaults([]);
              }}
            >
              <option value="">{p.scenarioAuto}</option>
              {(cat?.scenarios ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
          </div>
          <fieldset className="field pilot-faults-pick" style={{ gridColumn: "1 / -1", border: 0, padding: 0, margin: 0 }}>
            <legend className="label">
              <Bug size={14} aria-hidden="true" style={{ verticalAlign: -2 }} /> {p.faults}
            </legend>
            {chosen ? (
              chosen.faults.map((f) => (
                <label key={f.id} className="check">
                  <input
                    type="checkbox"
                    checked={faults.includes(f.id)}
                    disabled={!faults.includes(f.id) && faults.length >= 4}
                    onChange={(e) => setFaults(e.target.checked ? [...faults, f.id] : faults.filter((x) => x !== f.id))}
                  />
                  <span className="small">
                    {f.title} <span className="xs faint">· {f.category}{f.cwe ? ` · ${f.cwe}` : ""}</span>
                  </span>
                </label>
              ))
            ) : (
              <p className="hint">{p.faultsNeedScenario}</p>
            )}
            <p className="hint">{p.faultsHint(perLevel)}</p>
          </fieldset>
          <RangeField
            label={p.minutes}
            value={minutes ?? defaultMinutes}
            min={10}
            max={90}
            step={5}
            onChange={setMinutes}
            format={(v) => p.minutesVal(v)}
          />
          <div className="field">
            <label htmlFor="pp-hours">{p.validity}</label>
            <select id="pp-hours" className="select" value={hours} onChange={(e) => setHours(Number(e.target.value))} style={{ maxWidth: 160 }}>
              {[24, 48, 72, 168, 336].map((h) => (
                <option key={h} value={h}>
                  {h} h
                </option>
              ))}
            </select>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <SwitchRow checked={ownership} onChange={setOwnership} label={p.ownership} hint={p.ownershipHint} />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <Gate perm="decide">
              {(ok) => (
                <button className="btn btn-primary" onClick={create} disabled={!ok || busy}>
                  {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Link2 size={16} aria-hidden="true" />}
                  {p.createDo}
                </button>
              )}
            </Gate>
          </div>
        </div>
      </details>

      <h3 className="label">{p.list}</h3>
      {sessions.loading && !sessions.data ? (
        <Skeleton h={80} />
      ) : list.length === 0 ? (
        <p className="small muted">{p.none}</p>
      ) : (
        <ul className="verif-list">
          {list.map((s) => (
            <PilotSession key={s.id} s={s} catalog={cat} onChanged={sessions.reload} />
          ))}
        </ul>
      )}

      {link && (
        <Modal
          title={p.linkTitle}
          onClose={() => setLink(null)}
          footer={
            <button className="btn" onClick={() => setLink(null)}>
              {t.common.close}
            </button>
          }
        >
          <p className="small">{p.linkIntro(link.build_minutes, dateTime(link.expires_at, lang))}</p>
          <div className="field">
            <label htmlFor="pp-url">{t.ops.url}</label>
            <div className="row" style={{ gap: 6 }}>
              <input id="pp-url" className="input mono" readOnly value={url} onFocus={(e) => e.target.select()} />
              <button
                type="button"
                className="btn"
                onClick={() => void navigator.clipboard?.writeText(url).then(() => toast.push("success", t.ops.copied)).catch(() => undefined)}
              >
                <ClipboardCopy size={16} aria-hidden="true" />
                {t.common.copy}
              </button>
            </div>
          </div>
          <p className="small">
            <b>{p.linkFaults} —</b>{" "}
            {link.faults.map((id) => cat?.scenarios.find((s) => s.id === link.scenario)?.faults.find((f) => f.id === id)?.title ?? id).join(" · ")}
          </p>
          <p className="small muted">{link.ownership ? p.linkOwnership : p.noOwnership}</p>
          {link.note && <p className="hint">{link.note}</p>}
        </Modal>
      )}
    </section>
  );
}

function PilotSession({ s, catalog, onChanged }: { s: CandidatePilot; catalog: PilotCatalog | null; onChanged: () => void }) {
  const { t, lang } = usePrefs();
  const p = t.pilot.panel;
  const toast = useToast();
  const sc = catalog?.scenarios.find((x) => x.id === s.scenario_id);
  const available = (sc?.faults ?? []).filter((f) => !s.faults.some((x) => x.id === f.id));
  const [arm, setArm] = useState("");
  const [busy, setBusy] = useState(false);
  const running = RUNNING.has(s.phase);

  const doArm = async () => {
    if (!arm) return;
    setBusy(true);
    try {
      await api.armPilotFault(s.id, arm);
      toast.push("success", p.armed);
      setArm("");
      onChanged();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="verif-item">
      <div className="pilot-session-head">
        <span className={cx("chip", s.phase === "closed" ? "chip-ok" : running ? "chip-accent" : "chip-neutral")}>
          <span>{p.phase[s.phase] ?? s.phase}</span>
        </span>
        <span className="chip chip-plain">
          <span>
            {sc?.title ?? s.scenario_id} · {t.pilot.levels[s.level]}
          </span>
        </span>
        <span className="xs faint">{p.created(dateTime(s.created_at, lang))}</span>
        <span className="hash">{s.id}</span>
      </div>

      {!s.report && (
        <div className="stack-sm">
          <span className="label">{p.sessionFaults}</span>
          <ul className="pilot-sfaults">
            {s.faults.map((f) => (
              <li key={f.id}>
                <Bug size={13} aria-hidden="true" style={{ color: "var(--warn-text)" }} />
                <span>{f.title}</span>
                <span className="xs faint">
                  {f.injected_turn === null ? p.faultArmed : p.faultAt(f.injected_turn)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {running && (
        <div className="pilot-arm no-print">
          <div className="field" style={{ flex: "1 1 240px", minWidth: 0 }}>
            <label htmlFor={`arm-${s.id}`}>{p.arm}</label>
            <select id={`arm-${s.id}`} className="select" value={arm} onChange={(e) => setArm(e.target.value)} disabled={!available.length}>
              <option value="">{available.length ? "—" : p.armNone}</option>
              {available.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.title}
                </option>
              ))}
            </select>
          </div>
          <Gate perm="decide">
            {(ok) => (
              <button className="btn" onClick={doArm} disabled={!ok || !arm || busy}>
                {busy ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Bug size={14} aria-hidden="true" />}
                {p.armDo}
              </button>
            )}
          </Gate>
          <p className="xs muted" style={{ flexBasis: "100%" }}>
            {p.armHint}
          </p>
        </div>
      )}

      {s.report ? (
        <PilotReportView report={s.report} transcript={s.transcript} audience="recruiter" />
      ) : (
        <>
          <p className="small muted">{p.pending}</p>
          {s.transcript.length > 0 && (
            <details className="pr-transcript">
              <summary className="label row" style={{ gap: 6 }}>
                <ScrollText size={14} aria-hidden="true" />
                {t.pilot.report.transcript} <span className="faint">({t.pilot.report.transcriptCount(s.transcript.length)})</span>
              </summary>
              <PilotTranscript turns={s.transcript} anchor={`ps-${s.id}`} />
            </details>
          )}
        </>
      )}
    </li>
  );
}

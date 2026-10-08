// Report sections (v0.5): verification tests for this candidate, and the explanation links sent to them.
import { useState } from "react";
import { ClipboardCopy, Link2, Link2Off, Loader2, Lock, ShieldCheck, Timer } from "lucide-react";
import { api, BASE_PATH } from "../api/client";
import type { AssessLevel, AssessmentLink, CandidateAssessment, ExplanationLinkRow } from "../api/types";
import { usePrefs, useToast, type Async } from "../lib/prefs";
import { cx, dateTime } from "../lib/format";
import { Gate, Modal, Skeleton } from "../components/feedback";
import { RangeField, Segmented, SwitchRow } from "../components/controls";
import { AssessResultsView } from "../components/AssessResultsView";

export function VerificationPanel({ candidateRef, tests }: { candidateRef: string; tests: Async<CandidateAssessment[]> }) {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const [level, setLevel] = useState<AssessLevel>(2);
  const [n, setN] = useState(12);
  const [personal, setPersonal] = useState(true);
  const [seb, setSeb] = useState("");
  const [hours, setHours] = useState(72);
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<AssessmentLink | null>(null);

  const create = async () => {
    setBusy(true);
    try {
      const keys = seb
        .split(/[\s,;]+/)
        .map((k) => k.trim())
        .filter(Boolean)
        .slice(0, 5);
      setLink(await api.createAssessment(candidateRef, { level, questions: n, personal, seb_config_keys: keys, valid_hours: hours }));
      tests.reload();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  const url = link ? `${window.location.origin}${BASE_PATH}${link.path}` : "";
  const list = [...(tests.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <section className="panel" aria-labelledby="r-verif">
      <div>
        <h2 id="r-verif" className="panel-title">
          <ShieldCheck size={18} aria-hidden="true" />
          {t.verif.title}
        </h2>
        <p className="panel-hint">{t.verif.hint}</p>
      </div>

      <details className="verif-create no-print">
        <summary className="btn btn-sm">
          <Timer size={14} aria-hidden="true" />
          {t.verif.create}
        </summary>
        <div className="verif-form">
          <div className="field">
            <span className="label">{t.verif.level}</span>
            <Segmented<"1" | "2" | "3">
              label={t.verif.level}
              value={String(level) as "1" | "2" | "3"}
              onChange={(v) => setLevel(Number(v) as AssessLevel)}
              options={[1, 2, 3].map((v) => ({ value: String(v) as "1" | "2" | "3", label: t.test.levels[v] ?? "" }))}
            />
          </div>
          <RangeField label={t.verif.questions} value={n} min={4} max={25} step={1} onChange={setN} format={(v) => String(v)} />
          <div className="field">
            <label htmlFor="vf-hours">{t.verif.validity}</label>
            <select id="vf-hours" className="select" value={hours} onChange={(e) => setHours(Number(e.target.value))} style={{ maxWidth: 160 }}>
              {[24, 48, 72, 168, 336].map((h) => (
                <option key={h} value={h}>
                  {h} h
                </option>
              ))}
            </select>
          </div>
          <SwitchRow checked={personal} onChange={setPersonal} label={t.verif.personal} hint={t.verif.personalHint} />
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="vf-seb">
              <Lock size={14} aria-hidden="true" /> {t.verif.seb} <span className="opt">({t.common.optional})</span>
            </label>
            <textarea
              id="vf-seb"
              className="textarea mono"
              style={{ minHeight: 60, fontFamily: "var(--font-mono)" }}
              spellCheck={false}
              value={seb}
              placeholder="0f8e…c41a"
              aria-describedby="vf-seb-h"
              onChange={(e) => setSeb(e.target.value)}
            />
            <p id="vf-seb-h" className="hint">
              {t.verif.sebHint}{" "}
              <a href="https://safeexambrowser.org" target="_blank" rel="noreferrer">
                safeexambrowser.org
              </a>
            </p>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <Gate perm="decide">
              {(ok) => (
                <button className="btn btn-primary" onClick={create} disabled={!ok || busy}>
                  {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Link2 size={16} aria-hidden="true" />}
                  {t.verif.createDo}
                </button>
              )}
            </Gate>
          </div>
        </div>
      </details>

      <h3 className="label">{t.verif.list}</h3>
      {tests.loading && !tests.data ? (
        <Skeleton h={80} />
      ) : list.length === 0 ? (
        <p className="small muted">{t.verif.none}</p>
      ) : (
        <ul className="verif-list">
          {list.map((a) => (
            <li key={a.id} className="verif-item">
              <div className="row wrap" style={{ gap: 8 }}>
                <span className={cx("chip", a.status === "finished" ? "chip-ok" : a.status === "running" ? "chip-accent" : a.status === "expired" ? "chip-neutral" : "chip-plain")}>
                  <span>{t.verif.status[a.status] ?? a.status}</span>
                </span>
                <span className="chip chip-plain">
                  <span>
                    {t.test.levels[a.level]} · {t.test.questions(a.questions)}
                  </span>
                </span>
                {a.seb_required && (
                  <span className="chip chip-violet">
                    <Lock size={12} aria-hidden="true" />
                    <span>{t.verif.sebOn}</span>
                  </span>
                )}
                <span className="xs faint">{t.verif.created(dateTime(a.created_at, lang))}</span>
                <span className="hash">{a.id}</span>
              </div>
              {a.results ? <AssessResultsView results={a.results} audience="recruiter" /> : <p className="small muted">{t.verif.pending}</p>}
            </li>
          ))}
        </ul>
      )}

      {link && (
        <Modal
          title={t.verif.linkTitle}
          onClose={() => setLink(null)}
          footer={
            <button className="btn" onClick={() => setLink(null)}>
              {t.common.close}
            </button>
          }
        >
          <p className="small">{t.verif.linkIntro(link.questions, dateTime(link.expires_at, lang))}</p>
          <div className="field">
            <label htmlFor="vf-url">{t.ops.url}</label>
            <div className="row" style={{ gap: 6 }}>
              <input id="vf-url" className="input mono" readOnly value={url} onFocus={(e) => e.target.select()} />
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
          {link.untestable_skills.length > 0 && <p className="hint">{t.verif.untestable(link.untestable_skills.join(", "))}</p>}
        </Modal>
      )}
    </section>
  );
}

export function ExplanationLinksPanel({ candidateRef, links }: { candidateRef: string; links: Async<ExplanationLinkRow[]> }) {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const [busy, setBusy] = useState("");
  const revoke = async (id: string) => {
    setBusy(id);
    try {
      await api.revokeExplanationLink(candidateRef, id);
      toast.push("success", t.links.revoked);
      links.reload();
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy("");
    }
  };
  const rows = links.data ?? [];
  return (
    <section className="panel is-secondary no-print" aria-labelledby="r-links">
      <h2 id="r-links" className="panel-title">
        <Link2 size={16} aria-hidden="true" />
        {t.links.title}
      </h2>
      {links.loading && !links.data ? (
        <Skeleton h={48} />
      ) : rows.length === 0 ? (
        <p className="small muted">{t.links.none}</p>
      ) : (
        <ul className="file-list">
          {rows.map((l) => (
            <li key={l.id} className="file-item" style={{ flexWrap: "wrap" }}>
              <span className={cx("chip", l.active ? "chip-ok" : "chip-neutral")}>
                <span>{l.active ? t.links.active : t.links.inactive}</span>
              </span>
              <span className="hash">{l.id}</span>
              <span className="xs muted" style={{ flex: "1 1 200px" }}>
                {t.links.by(l.created_by ?? "—", dateTime(l.created_at ?? undefined, lang))} · {l.revoked
                  ? t.links.revokedBy(l.revoked_by ?? "—", dateTime(l.revoked_at ?? undefined, lang))
                  : t.links.expires(dateTime(l.expires_at, lang))}
              </span>
              {l.active && (
                <Gate perm="decide">
                  {(ok) => (
                    <button className="btn btn-danger btn-sm" onClick={() => revoke(l.id)} disabled={!ok || busy === l.id}>
                      {busy === l.id ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Link2Off size={14} aria-hidden="true" />}
                      {t.links.revoke}
                    </button>
                  )}
                </Gate>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

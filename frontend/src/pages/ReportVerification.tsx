// Report sections: results of former-format verification tests (read-only), and the explanation links.
import { useState } from "react";
import { History, Link2, Link2Off, Loader2, Lock } from "lucide-react";
import { api } from "../api/client";
import type { CandidateAssessment, ExplanationLinkRow } from "../api/types";
import { usePrefs, useToast, type Async } from "../lib/prefs";
import { cx, dateTime } from "../lib/format";
import { Gate, Skeleton } from "../components/feedback";
import { AssessResultsView } from "../components/AssessResultsView";

/** Results of verification tests taken in the former format (closed book, integrity signals): read-only.
 *  New tests are created from the technical-test panel. */
export function VerificationPanel({ tests }: { tests: Async<CandidateAssessment[]> }) {
  const { t, lang } = usePrefs();
  const list = [...(tests.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at));
  if (list.length === 0) return null;
  return (
    <section className="panel is-secondary" aria-labelledby="r-verif">
      <div>
        <h2 id="r-verif" className="panel-title">
          <History size={18} aria-hidden="true" />
          {t.verif.title} — {t.tt.panel.legacyTitle}
        </h2>
        <p className="panel-hint">{t.tt.panel.legacyHint}</p>
      </div>
      <ul className="verif-list">
        {list.map((a) => (
          <li key={a.id} className="verif-item">
            <div className="row wrap" style={{ gap: 8 }}>
              <span className="chip chip-neutral">
                <span>{t.tt.panel.legacyTitle}</span>
              </span>
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

// Candidate information notice (French Labour Code L1221-8, GDPR Art. 13, AI Act Art. 26) — short + "learn more".
import { useState } from "react";
import { Info } from "lucide-react";
import { usePrefs } from "../lib/prefs";

export function CandidateNotice() {
  const { t } = usePrefs();
  const [open, setOpen] = useState(false);
  return (
    <aside className="callout callout-neutral cand-notice" aria-label={t.notice.title}>
      <Info size={16} aria-hidden="true" />
      <div className="stack-sm" style={{ gap: 6, minWidth: 0 }}>
        <b className="small">
          {t.notice.title} <span className="xs faint" style={{ fontWeight: 400 }}>({t.notice.legal})</span>
        </b>
        <p className="small">{open ? t.notice.full : t.notice.short}</p>
        <button type="button" className="disclosure" aria-expanded={open} onClick={() => setOpen(!open)} style={{ alignSelf: "flex-start" }}>
          {open ? t.notice.less : t.notice.more}
        </button>
      </div>
    </aside>
  );
}

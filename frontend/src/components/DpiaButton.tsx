import { useState } from "react";
import { FileDown, Loader2 } from "lucide-react";
import { api } from "../api/client";
import type { Locale } from "../api/types";
import { usePrefs, useToast } from "../lib/prefs";

/** Downloads the pre-filled DPIA draft (Markdown) in the role's report language. */
export function DpiaButton({ jobId, locale }: { jobId: string; locale: Locale }) {
  const { t } = usePrefs();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      await api.dpia(jobId, locale);
      toast.push("success", t.ops.dpiaDone, t.ops.dpia);
    } catch (e) {
      toast.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" className="btn" onClick={go} disabled={busy} title={t.ops.dpiaHint}>
      {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <FileDown size={16} aria-hidden="true" />}
      {t.ops.dpia}
      <span className="sr-only"> — {t.ops.dpiaHint}</span>
    </button>
  );
}

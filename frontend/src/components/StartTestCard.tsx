// Starts a public verification test from the sandbox (POST /api/assess/start) and opens the test player.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, ShieldCheck, Timer } from "lucide-react";
import { assess } from "../api/client";
import type { AssessLevel, JobProfile } from "../api/types";
import { usePrefs, useToast } from "../lib/prefs";
import { cx } from "../lib/format";
import { Segmented } from "./controls";

export function StartTestCard({
  presetId,
  job,
  seed,
  variant = "hero",
}: {
  presetId?: string;
  job?: JobProfile | null;
  /** assessment_seed from /api/try/match: adds questions about the visitor's own work */
  seed?: string;
  variant?: "hero" | "compact";
}) {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const navigate = useNavigate();
  const [level, setLevel] = useState<AssessLevel>(2);
  const [n, setN] = useState(10);
  const [busy, setBusy] = useState(false);
  const can = Boolean(presetId || job);
  const go = async () => {
    setBusy(true);
    try {
      const r = await assess.start({
        preset_id: job ? undefined : presetId,
        job: job ?? undefined,
        level,
        locale: lang,
        questions: n,
        seed: seed || undefined,
      });
      navigate(`/test/${r.token}`);
    } catch (e) {
      toast.error(e);
      setBusy(false);
    }
  };
  return (
    <section className={cx("start-test", variant === "hero" ? "hero" : "panel")} aria-labelledby={`st-${variant}`}>
      <div className="row" style={{ gap: 12, alignItems: "flex-start" }}>
        <span className="land-icon">
          <ShieldCheck size={20} aria-hidden="true" />
        </span>
        <div style={{ minWidth: 0 }}>
          <h2 id={`st-${variant}`} className={variant === "hero" ? "try-h2" : "panel-title"}>
            {variant === "hero" ? t.verif.proveTitle : t.verif.direct}
          </h2>
          <p className="muted small" style={{ marginTop: 4, maxWidth: "70ch" }}>
            {variant === "hero" ? (seed ? t.verif.proveBody : t.verif.proveBodyNoSeed) : can ? t.verif.directHint : t.verif.directChoose}
          </p>
        </div>
      </div>
      <div className="row wrap" style={{ gap: 16, alignItems: "flex-end" }}>
        <div className="field">
          <span className="label">{t.verif.level}</span>
          <Segmented<"1" | "2" | "3">
            label={t.verif.level}
            value={String(level) as "1" | "2" | "3"}
            onChange={(v) => setLevel(Number(v) as AssessLevel)}
            options={[1, 2, 3].map((v) => ({ value: String(v) as "1" | "2" | "3", label: t.test.levels[v] ?? "" }))}
          />
        </div>
        <div className="field">
          <label htmlFor={`st-n-${variant}`}>{t.verif.questions}</label>
          <select id={`st-n-${variant}`} className="select" value={n} onChange={(e) => setN(Number(e.target.value))} style={{ width: 110 }}>
            {[6, 10, 15, 20].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
        <button className="btn btn-primary btn-lg" onClick={go} disabled={!can || busy}>
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Timer size={16} aria-hidden="true" />}
          {t.verif.startTest}
        </button>
      </div>
    </section>
  );
}

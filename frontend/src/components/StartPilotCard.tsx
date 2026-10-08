// Starts a public AI-pilot test from the sandbox (POST /api/pilot/start) and opens the player.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Github, Loader2, Rocket, Workflow } from "lucide-react";
import { ApiError, pilot } from "../api/client";
import type { AssessLevel, JobProfile } from "../api/types";
import { useAsync, usePrefs, useToast } from "../lib/prefs";
import { cx } from "../lib/format";
import { Segmented } from "./controls";

export function StartPilotCard({
  presetId,
  job,
  githubUrls,
  variant = "hero",
}: {
  presetId?: string;
  job?: JobProfile | null;
  /** GitHub links already entered on the profile step: they enable the task on the visitor's own code */
  githubUrls?: string[];
  variant?: "hero" | "compact";
}) {
  const { t, lang } = usePrefs();
  const p = t.pilot.start;
  const toast = useToast();
  const navigate = useNavigate();
  const catalog = useAsync(() => pilot.scenarios(lang).catch(() => null), [lang]);
  const [level, setLevel] = useState<AssessLevel>(2);
  const [scenario, setScenario] = useState("");
  const [gh, setGh] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const can = Boolean(presetId || job);
  const known = (githubUrls ?? []).filter(Boolean).slice(0, 3);
  const urls = known.length ? known : gh.trim() ? [gh.trim()] : [];

  const go = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await pilot.start({
        preset_id: job ? undefined : presetId,
        job: job ?? undefined,
        scenario_id: scenario || undefined,
        level,
        locale: lang,
        github_urls: urls,
      });
      navigate(`${lang === "en" ? "/en" : ""}/pilote/${r.token}`, { state: { warning: r.warning } });
    } catch (e) {
      setBusy(false);
      if (e instanceof ApiError && e.status === 422 && /scenario/i.test(e.message)) setError(p.noScenario);
      else if (e instanceof ApiError && e.status === 429) setError(p.tooMany);
      else toast.error(e);
    }
  };
  const id = `sp-${variant}`;
  return (
    <section className={cx("start-test start-pilot", variant === "hero" ? "hero" : "panel")} aria-labelledby={id}>
      <div className="row" style={{ gap: 12, alignItems: "flex-start" }}>
        <span className="land-icon">
          <Workflow size={20} aria-hidden="true" />
        </span>
        <div style={{ minWidth: 0 }}>
          <h2 id={id} className={variant === "hero" ? "try-h2" : "panel-title"}>
            {variant === "hero" ? p.title : p.direct}
          </h2>
          <p className="muted small" style={{ marginTop: 4, maxWidth: "75ch" }}>
            {variant === "hero" ? p.body : can ? p.directHint : p.choose}
          </p>
        </div>
      </div>
      <div className="row wrap" style={{ gap: 16, alignItems: "flex-end" }}>
        <div className="field">
          <span className="label">{p.level}</span>
          <Segmented<"1" | "2" | "3">
            label={p.level}
            value={String(level) as "1" | "2" | "3"}
            onChange={(v) => setLevel(Number(v) as AssessLevel)}
            options={[1, 2, 3].map((v) => ({ value: String(v) as "1" | "2" | "3", label: t.pilot.levels[v] ?? "" }))}
          />
        </div>
        <div className="field" style={{ flex: "1 1 220px", minWidth: 0 }}>
          <label htmlFor={`${id}-sc`}>{p.scenario}</label>
          <select id={`${id}-sc`} className="select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
            <option value="">{p.scenarioAuto}</option>
            {(catalog.data?.scenarios ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </div>
        {!known.length && (
          <div className="field" style={{ flex: "1 1 240px", minWidth: 0 }}>
            <label htmlFor={`${id}-gh`}>
              <Github size={14} aria-hidden="true" /> {p.github}
            </label>
            <input
              id={`${id}-gh`}
              className="input"
              type="url"
              inputMode="url"
              placeholder={p.githubPh}
              value={gh}
              aria-describedby={`${id}-gh-h`}
              onChange={(e) => setGh(e.target.value)}
            />
          </div>
        )}
        <button className="btn btn-primary btn-lg" onClick={go} disabled={!can || busy}>
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Rocket size={16} aria-hidden="true" />}
          {p.go}
        </button>
      </div>
      <p id={`${id}-gh-h`} className="hint">
        {known.length ? p.githubFromProfile(known.length) : p.githubHint}
      </p>
      {error && (
        <p className="callout callout-warn" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

// Starts the public technical test from the sandbox (POST /api/pilot/start) and opens the player:
// 1. knowledge questions (tools allowed), 2. questions with the built-in assistant, 3. the practical mission.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ClipboardCheck, Github, Loader2, Rocket } from "lucide-react";
import { ApiError, pilot } from "../api/client";
import type { AssessLevel, JobProfile } from "../api/types";
import { useAsync, usePrefs, useToast } from "../lib/prefs";
import { cx } from "../lib/format";
import { Segmented } from "./controls";

const KNOWLEDGE = [0, 4, 6, 10];
const WITH_AI = [0, 2, 4, 6];

export function StartTechTestCard({
  presetId,
  job,
  seed,
  githubUrls,
  variant = "hero",
}: {
  presetId?: string;
  job?: JobProfile | null;
  /** assessment_seed from /api/try/match: adds questions about the visitor's own work (section 1) */
  seed?: string;
  /** GitHub links already entered on the profile step: they enable the task on the visitor's own code */
  githubUrls?: string[];
  variant?: "hero" | "compact";
}) {
  const { t, lang } = usePrefs();
  const p = t.tt.start;
  const toast = useToast();
  const navigate = useNavigate();
  const catalog = useAsync(() => pilot.scenarios(lang).catch(() => null), [lang]);
  const [level, setLevel] = useState<AssessLevel>(2);
  const [knowledge, setKnowledge] = useState(6);
  const [withAi, setWithAi] = useState(4);
  const [mission, setMission] = useState(""); // "" auto, "none", or a scenario id
  const [gh, setGh] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const can = Boolean(presetId || job) && (knowledge + withAi > 0 || mission !== "none");
  const known = (githubUrls ?? []).filter(Boolean).slice(0, 3);
  const urls = known.length ? known : gh.trim() ? [gh.trim()] : [];

  const go = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await pilot.start({
        preset_id: job ? undefined : presetId,
        job: job ?? undefined,
        scenario_id: mission && mission !== "none" ? mission : undefined,
        mission: mission !== "none",
        knowledge_questions: knowledge,
        ai_questions: withAi,
        seed: seed || undefined,
        level,
        locale: lang,
        github_urls: urls,
      });
      navigate(`${lang === "en" ? "/en" : ""}/pilote/${r.token}`, { state: { warning: r.warning } });
    } catch (e) {
      setBusy(false);
      if (e instanceof ApiError && e.status === 422 && /scenario|question|mission/i.test(e.message)) setError(p.noTest);
      else if (e instanceof ApiError && e.status === 429) setError(t.pilot.start.tooMany);
      else toast.error(e);
    }
  };
  const id = `stt-${variant}`;
  const hero = variant === "hero";
  return (
    <section className={cx("start-test start-tt", hero ? "hero" : "panel")} aria-labelledby={id}>
      <div className="row" style={{ gap: 12, alignItems: "flex-start" }}>
        <span className="land-icon">
          <ClipboardCheck size={20} aria-hidden="true" />
        </span>
        <div style={{ minWidth: 0 }}>
          <h2 id={id} className={hero ? "try-h2" : "panel-title"}>
            {hero ? p.title : p.direct}
          </h2>
          <p className="muted small" style={{ marginTop: 4, maxWidth: "75ch" }}>
            {hero ? `${p.body}${seed ? ` ${p.bodySeed}` : ""}` : presetId || job ? p.directHint : p.choose}
          </p>
        </div>
      </div>
      <div className="stt-grid">
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
          <label htmlFor={`${id}-k`}>{p.knowledge}</label>
          <select id={`${id}-k`} className="select" value={knowledge} onChange={(e) => setKnowledge(Number(e.target.value))}>
            {KNOWLEDGE.map((v) => (
              <option key={v} value={v}>
                {p.count(v)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-a`}>{p.ai}</label>
          <select id={`${id}-a`} className="select" value={withAi} onChange={(e) => setWithAi(Number(e.target.value))}>
            {WITH_AI.map((v) => (
              <option key={v} value={v}>
                {p.count(v)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-m`}>{p.mission}</label>
          <select id={`${id}-m`} className="select" value={mission} onChange={(e) => setMission(e.target.value)}>
            <option value="">{p.missionAuto}</option>
            <option value="none">{p.missionNone}</option>
            {(catalog.data?.scenarios ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </div>
        {!known.length && (
          <div className="field stt-wide">
            <label htmlFor={`${id}-gh`}>
              <Github size={14} aria-hidden="true" /> {t.pilot.start.github}
            </label>
            <input
              id={`${id}-gh`}
              className="input"
              type="url"
              inputMode="url"
              placeholder={t.pilot.start.githubPh}
              value={gh}
              aria-describedby={`${id}-gh-h`}
              onChange={(e) => setGh(e.target.value)}
            />
          </div>
        )}
      </div>
      <p id={`${id}-gh-h`} className="hint">
        {known.length ? t.pilot.start.githubFromProfile(known.length) : t.pilot.start.githubHint}
      </p>
      <div>
        <button className="btn btn-primary btn-lg" onClick={go} disabled={!can || busy}>
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Rocket size={16} aria-hidden="true" />}
          {p.go}
        </button>
      </div>
      {error && (
        <p className="callout callout-warn" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

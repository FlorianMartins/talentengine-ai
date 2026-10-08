import { useState, type FormEvent } from "react";
import { Eye, EyeOff, KeyRound, Palette, Save, Server, UserRound } from "lucide-react";
import type { Lang } from "../i18n";
import { API, ApiError } from "../api/client";
import { usePrefs, useSystem, useToast, type Theme } from "../lib/prefs";
import { PageHeader, useCrumbs } from "../components/Shell";
import { ErrorState, Skeleton } from "../components/feedback";
import { Segmented } from "../components/controls";

export function SettingsPage() {
  const { t, theme, setTheme, lang, setLang, reviewer, setReviewer, apiKey, setApiKey } = usePrefs();
  const toast = useToast();
  const { runtime, runtimeError, refresh } = useSystem();
  const [name, setName] = useState(reviewer);
  const [key, setKey] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);
  const keyRejected = runtimeError instanceof ApiError && runtimeError.status === 401;
  useCrumbs([{ label: t.nav.settings }]);

  const save = (e: FormEvent) => {
    e.preventDefault();
    setReviewer(name);
    setApiKey(key);
    toast.push("success", t.settings.saved);
    refresh();
  };

  return (
    <div className="page">
      <section className="hero">
        <PageHeader title={t.settings.title} sub={t.settings.subtitle} />
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        <div className="stack-lg">
          <section className="panel" aria-labelledby="s-app">
            <h2 id="s-app" className="panel-title">
              <Palette size={18} aria-hidden="true" />
              {t.settings.appearance}
            </h2>
            <div className="field">
              <span className="label">{t.settings.theme}</span>
              <Segmented<Theme>
                label={t.settings.theme}
                value={theme}
                onChange={setTheme}
                options={[
                  { value: "dark", label: t.settings.dark },
                  { value: "light", label: t.settings.light },
                ]}
              />
            </div>
            <div className="field">
              <span className="label">{t.settings.language}</span>
              <Segmented<Lang>
                label={t.settings.language}
                value={lang}
                onChange={setLang}
                options={[
                  { value: "fr", label: "Français" },
                  { value: "en", label: "English" },
                ]}
              />
            </div>
          </section>

          <form className="panel" aria-labelledby="s-id" onSubmit={save}>
            <h2 id="s-id" className="panel-title">
              <UserRound size={18} aria-hidden="true" />
              {t.settings.identity}
            </h2>
            <div className="field">
              <label htmlFor="s-rev">{t.settings.reviewer}</label>
              <input
                id="s-rev"
                className="input"
                value={name}
                maxLength={120}
                autoComplete="name"
                placeholder={t.settings.reviewerPh}
                aria-describedby="s-rev-h"
                onChange={(e) => setName(e.target.value)}
              />
              <p id="s-rev-h" className="hint">
                {t.settings.reviewerHint}
              </p>
            </div>
            <div className="field">
              <label htmlFor="s-key">
                <KeyRound size={14} aria-hidden="true" />
                {t.settings.apiKey}
                {(runtime?.auth_required || keyRejected) && <span className="chip chip-warn">{t.settings.required}</span>}
              </label>
              <div className="row" style={{ gap: 6 }}>
                <input
                  id="s-key"
                  className="input mono"
                  type={showKey ? "text" : "password"}
                  autoComplete="off"
                  spellCheck={false}
                  value={key}
                  aria-describedby="s-key-h"
                  onChange={(e) => setKey(e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn-icon"
                  aria-label={showKey ? t.settings.hide : t.settings.show}
                  aria-pressed={showKey}
                  onClick={() => setShowKey(!showKey)}
                >
                  {showKey ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                </button>
              </div>
              <p id="s-key-h" className="hint">
                {runtime && !runtime.auth_required ? t.settings.apiKeyOptional : t.settings.apiKeyHint}
              </p>
            </div>
            <div>
              <button className="btn btn-primary" type="submit">
                <Save size={16} aria-hidden="true" />
                {t.common.save}
              </button>
            </div>
          </form>
        </div>

        <section className="panel" aria-labelledby="s-rt">
          <h2 id="s-rt" className="panel-title">
            <Server size={18} aria-hidden="true" />
            {t.settings.runtime}
          </h2>
          {runtime ? (
            <dl className="kv">
              <dt>{t.settings.version}</dt>
              <dd className="mono">{runtime.version}</dd>
              <dt>{t.settings.vision}</dt>
              <dd className="mono">{runtime.vision_detector || "none"}</dd>
              <dt>{t.settings.llm}</dt>
              <dd className="mono">{runtime.llm_provider === "none" ? t.status.localOnly : runtime.llm_provider}</dd>
              <dt>{t.settings.model}</dt>
              <dd className="mono">{runtime.llm_model || "—"}</dd>
              <dt>{t.settings.maxCred}</dt>
              <dd className="mono">{Math.round(runtime.max_credential_weight * 100)} %</dd>
              <dt>{t.settings.demo}</dt>
              <dd>{runtime.demo_enabled ? t.settings.enabled : t.settings.disabled}</dd>
              <dt>{t.settings.auth}</dt>
              <dd>{runtime.auth_required ? t.settings.required : t.settings.notRequired}</dd>
            </dl>
          ) : runtimeError ? (
            <ErrorState error={runtimeError} onRetry={refresh} />
          ) : (
            <Skeleton h={180} />
          )}
          <p className="xs faint">
            <a href={`${API}/docs`}>OpenAPI · /api/docs</a>
          </p>
        </section>
      </div>
    </div>
  );
}

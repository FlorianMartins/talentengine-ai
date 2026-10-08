import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { BadgeCheck, Eye, EyeOff, KeyRound, LogOut, Palette, Plug, Save, Server, UserRound, Users } from "lucide-react";
import type { Lang } from "../i18n";
import { API } from "../api/client";
import { useAccess, usePrefs, useSystem, useToast, type Theme } from "../lib/prefs";
import { PageHeader, useCrumbs } from "../components/Shell";
import { ErrorState, Skeleton } from "../components/feedback";
import { Segmented } from "../components/controls";
import { cx } from "../lib/format";

export function SettingsPage() {
  const { t, theme, setTheme, lang, setLang, reviewer, setReviewer, apiKey, setApiKey } = usePrefs();
  const toast = useToast();
  const { runtime, runtimeError, refresh, health } = useSystem();
  const access = useAccess();
  const [name, setName] = useState(reviewer);
  const [key, setKey] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);
  useCrumbs([{ label: t.nav.settings }]);

  const named = access.mode === "named";
  const keyNeeded = Boolean(health?.auth_required) || access.mode === "anonymous";

  const save = (e: FormEvent) => {
    e.preventDefault();
    if (!named) setReviewer(name);
    setApiKey(key);
    toast.push("success", t.settings.saved);
    refresh();
  };
  const forget = () => {
    setKey("");
    setApiKey("");
    refresh();
  };

  return (
    <div className="page">
      <section className="hero">
        <PageHeader title={t.settings.title} sub={t.settings.subtitle} />
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        <div className="stack-lg">
          {/* ------------------------------------------------ identity */}
          <section className="panel" aria-labelledby="s-who">
            <h2 id="s-who" className="panel-title">
              <UserRound size={18} aria-hidden="true" />
              {t.settings.identityCard}
            </h2>
            {access.mode === "loading" ? (
              <Skeleton h={60} />
            ) : access.mode === "anonymous" ? (
              <p className="callout callout-warn">
                <KeyRound size={16} aria-hidden="true" />
                <span>{t.access.loginRequired}</span>
              </p>
            ) : (
              <div className="ident">
                <div className="row wrap" style={{ gap: 8 }}>
                  <b style={{ fontSize: 16 }}>
                    {named && access.me ? access.me.name : access.mode === "shared" ? t.access.sharedKey : t.access.open}
                  </b>
                  {access.me && (
                    <span className={cx("chip", access.me.role === "admin" ? "chip-violet" : access.me.role === "dpo" ? "chip-ok" : "chip-accent")}>
                      <span>{t.access.roles[access.me.role] ?? access.me.role}</span>
                    </span>
                  )}
                </div>
                {access.mode !== "named" && (
                  <p className="xs muted">{access.mode === "shared" ? t.access.sharedHint : t.access.openHint}</p>
                )}
                {access.me && (
                  <div className="stack-sm" style={{ gap: 6 }}>
                    <span className="eyebrow">{t.access.permissions}</span>
                    <ul className="chips" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                      {access.me.permissions.map((p) => (
                        <li key={p} className="chip chip-plain">
                          <BadgeCheck size={12} aria-hidden="true" />
                          <span>{t.access.perms[p] ?? p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {access.me && <p className="xs faint">{t.access.roleDesc[access.me.role]}</p>}
              </div>
            )}
            {access.can("admin") && (
              <div className="row wrap" style={{ gap: 8 }}>
                <Link to="/settings/accounts" className="btn">
                  <Users size={16} aria-hidden="true" />
                  {t.settings.accountsLink}
                </Link>
                <Link to="/settings/integrations" className="btn">
                  <Plug size={16} aria-hidden="true" />
                  {t.integrations.nav}
                </Link>
              </div>
            )}
          </section>

          {/* ------------------------------------------------ key + reviewer */}
          <form className="panel" aria-labelledby="s-id" onSubmit={save}>
            <h2 id="s-id" className="panel-title">
              <KeyRound size={18} aria-hidden="true" />
              {t.settings.personalKey}
              {keyNeeded && <span className="chip chip-warn">{t.settings.required}</span>}
            </h2>
            <div className="field">
              <label htmlFor="s-key" className="sr-only">
                {t.settings.personalKey}
              </label>
              <div className="row" style={{ gap: 6 }}>
                <input
                  id="s-key"
                  className="input mono"
                  type={showKey ? "text" : "password"}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="te_…"
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
                {health && !health.auth_required ? t.settings.apiKeyOptional : t.settings.personalKeyHint}
              </p>
            </div>
            {named ? (
              <p className="hint">{t.settings.reviewerNamed}</p>
            ) : (
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
            )}
            <div className="row wrap">
              <button className="btn btn-primary" type="submit">
                <Save size={16} aria-hidden="true" />
                {t.common.save}
              </button>
              {apiKey && (
                <button className="btn btn-ghost" type="button" onClick={forget}>
                  <LogOut size={16} aria-hidden="true" />
                  {t.settings.forget}
                </button>
              )}
            </div>
          </form>

          {/* ------------------------------------------------ appearance */}
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
              <dt>{t.accounts.nav}</dt>
              <dd>{runtime.named_accounts ? t.settings.enabled : t.settings.disabled}</dd>
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

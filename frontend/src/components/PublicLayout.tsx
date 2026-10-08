// Chrome for the public pages (sandbox, recruiter landing): no sidebar, no API key.
import { useEffect, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { Github, Languages, Moon, Sun } from "lucide-react";
import type { Lang } from "../i18n";
import { usePrefs } from "../lib/prefs";
import { getStored } from "../lib/storage";
import { cx } from "../lib/format";
import { Logo } from "./Shell";
import { ToastRegion } from "./feedback";

export const REPO_URL = "https://github.com/FlorianMartins/talentengine-ai";

/** Localised public paths: /essai ↔ /try, /recruteurs ↔ /recruiters. */
export function publicPaths(lang: Lang) {
  return lang === "en" ? { try: "/try", recruiters: "/recruiters" } : { try: "/essai", recruiters: "/recruteurs" };
}

export function PublicLayout({ children, lang: routeLang }: { children: ReactNode; lang?: Lang }) {
  const { t, lang, setLang, theme, setTheme } = usePrefs();
  // An EN alias (/try, /recruiters) opens in English unless the visitor already chose a language.
  useEffect(() => {
    if (routeLang && !getStored("lang") && routeLang !== lang) setLang(routeLang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeLang]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const paths = publicPaths(lang);
  return (
    <div className="public">
      <a className="skip-link" href="#main">
        {t.app.skip}
      </a>
      <header className="pub-bar">
        <Link to={paths.try} className="brand" aria-label={t.pub.nav.home} style={{ padding: 0 }}>
          <Logo size={30} />
          <span className="brand-name pub-brand-name">
            TalentEngine<b>‑AI</b>
          </span>
        </Link>
        <nav className="pub-nav" aria-label={t.nav.label}>
          <NavLink to={paths.try} className={({ isActive }) => cx("pub-link", isActive && "active")}>
            {t.pub.nav.try}
          </NavLink>
          <NavLink to={paths.recruiters} className={({ isActive }) => cx("pub-link", isActive && "active")}>
            {t.pub.nav.recruiters}
          </NavLink>
        </nav>
        <div className="topbar-actions">
          <a className="btn btn-ghost btn-icon btn-sm" href={REPO_URL} aria-label={t.pub.nav.source} title={t.pub.nav.source}>
            <Github size={16} aria-hidden="true" />
          </a>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setLang(lang === "fr" ? "en" : "fr")}
            aria-label={t.top.toLang}
            title={t.top.toLang}
          >
            <Languages size={16} aria-hidden="true" />
            <span className="num">{t.top.langShort}</span>
          </button>
          <button
            className="btn btn-ghost btn-icon btn-sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? t.top.toLight : t.top.toDark}
            title={theme === "dark" ? t.top.toLight : t.top.toDark}
          >
            {theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
          </button>
        </div>
      </header>
      <main id="main" className="pub-main" tabIndex={-1}>
        {children}
      </main>
      <footer className="pub-footer">
        <span>{t.pub.footer}</span>
        <span className="row wrap" style={{ gap: 16 }}>
          <Link to={paths.try}>{t.pub.nav.try}</Link>
          <Link to={paths.recruiters}>{t.pub.nav.recruiters}</Link>
          <a href={REPO_URL}>{t.pub.nav.source}</a>
        </span>
      </footer>
      <ToastRegion />
    </div>
  );
}

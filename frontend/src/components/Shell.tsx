import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  ChevronRight,
  LayoutGrid,
  KeyRound,
  Languages,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  ScrollText,
  Settings,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { usePrefs, useSystem } from "../lib/prefs";
import { ApiError } from "../api/client";
import { getStored, setStored } from "../lib/storage";
import { cx } from "../lib/format";
import { ToastRegion } from "./feedback";

/** Geometric mark: a hexagonal "evidence cell" with a 3-axis core. Original drawing. */
export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="te-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--accent)" />
          <stop offset="1" stopColor="var(--violet)" />
        </linearGradient>
      </defs>
      <rect x="0.5" y="0.5" width="31" height="31" rx="9" fill="var(--surface-2)" stroke="var(--border-strong)" />
      <path d="M16 5.5 25 10.75v10.5L16 26.5 7 21.25v-10.5Z" fill="none" stroke="url(#te-g)" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M16 11v5m0 0-4.3 2.5M16 16l4.3 2.5" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2.1" fill="var(--accent)" />
    </svg>
  );
}

// ------------------------------------------------------------------ breadcrumbs (set by pages)

export interface Crumb {
  label: string;
  to?: string;
}
const CrumbContext = createContext<(c: Crumb[]) => void>(() => undefined);

export function useCrumbs(crumbs: Crumb[]): void {
  const set = useContext(CrumbContext);
  const key = JSON.stringify(crumbs);
  useEffect(() => {
    set(crumbs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, set]);
}

export function Shell() {
  const { t, theme, setTheme, lang, setLang } = usePrefs();
  const [collapsed, setCollapsed] = useState(() => getStored("sidebar") === "collapsed");
  const [crumbs, setCrumbs] = useState<Crumb[]>([]);
  const location = useLocation();
  const { runtimeError } = useSystem();
  const needsKey = runtimeError instanceof ApiError && runtimeError.status === 401;

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  const toggleCollapsed = () => {
    setStored("sidebar", collapsed ? "" : "collapsed");
    setCollapsed(!collapsed);
  };

  const nav = useMemo(
    () => [
      { to: "/", label: t.nav.overview, icon: LayoutGrid, end: true },
      { to: "/audit", label: t.nav.audit, icon: ScrollText, end: false },
      { to: "/settings", label: t.nav.settings, icon: Settings, end: false },
    ],
    [t],
  );
  const isJobs =
    location.pathname !== "/jobs/new" &&
    (location.pathname === "/" || location.pathname.startsWith("/jobs") || location.pathname.startsWith("/candidates"));

  return (
    <CrumbContext.Provider value={setCrumbs}>
      <a className="skip-link" href="#main">
        {t.app.skip}
      </a>
      <div className={cx("shell", collapsed && "is-collapsed")}>
        <aside className="sidebar" aria-label={t.nav.label}>
          <Link to="/" className="brand" title={t.app.name}>
            <Logo />
            <span className="brand-text">
              <span className="brand-name">
                TalentEngine<b>‑AI</b>
              </span>
              <span className="brand-tag">{t.app.tagline}</span>
            </span>
          </Link>
          <nav>
            <ul className="nav-list">
              {nav.map((n) => (
                <li key={n.to}>
                  <NavLink
                    to={n.to}
                    end={n.end}
                    className={({ isActive }) => cx("nav-item", (isActive || (n.end && isJobs)) && "active")}
                    title={collapsed ? n.label : undefined}
                  >
                    <n.icon size={18} aria-hidden="true" />
                    <span className="nav-label">{n.label}</span>
                  </NavLink>
                </li>
              ))}
              <li>
                <NavLink to="/jobs/new" className="nav-item" title={collapsed ? t.nav.newJob : undefined}>
                  <Plus size={18} aria-hidden="true" />
                  <span className="nav-label">{t.nav.newJob}</span>
                </NavLink>
              </li>
            </ul>
          </nav>
          <div className="sidebar-foot">
            <p className="human-note">
              <ShieldCheck size={16} aria-hidden="true" />
              <span>{t.app.humanFirst}</span>
            </p>
            <button
              className="nav-item btn-reset"
              style={{ border: 0, background: "none", cursor: "pointer", width: "100%" }}
              onClick={toggleCollapsed}
              aria-label={collapsed ? t.nav.expand : t.nav.collapse}
              aria-expanded={!collapsed}
            >
              {collapsed ? <PanelLeftOpen size={18} aria-hidden="true" /> : <PanelLeftClose size={18} aria-hidden="true" />}
              <span className="nav-label">{t.nav.collapse}</span>
            </button>
          </div>
        </aside>

        <div className="main">
          <header className="topbar">
            <Link to="/" className="mobile-brand" aria-label={t.app.name}>
              <Logo size={30} />
            </Link>
            <nav aria-label={t.top.breadcrumb} style={{ minWidth: 0 }}>
              <ol className="crumbs">
                {crumbs.map((c, i) => {
                  const last = i === crumbs.length - 1;
                  return (
                    <li key={`${c.label}-${i}`}>
                      {c.to && !last ? <Link to={c.to}>{c.label}</Link> : <span aria-current={last ? "page" : undefined}>{c.label}</span>}
                      {!last && <ChevronRight size={14} aria-hidden="true" />}
                    </li>
                  );
                })}
              </ol>
            </nav>
            <div className="topbar-actions">
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
          <main id="main" className="content" tabIndex={-1}>
            {needsKey && location.pathname !== "/settings" && (
              <p className="callout callout-warn" role="alert" style={{ marginBottom: 24 }}>
                <KeyRound size={16} aria-hidden="true" />
                <span>
                  {t.common.unauthorized} <Link to="/settings">{t.nav.settings} →</Link>
                </span>
              </p>
            )}
            <Outlet />
          </main>
        </div>
      </div>

      <nav className="mobile-nav" aria-label={t.nav.label}>
        {nav.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => cx((isActive || (n.end && isJobs)) && "active")}>
            <n.icon size={20} aria-hidden="true" />
            {n.label}
          </NavLink>
        ))}
        <NavLink to="/jobs/new">
          <Plus size={20} aria-hidden="true" />
          {t.nav.newJob}
        </NavLink>
      </nav>
      <ToastRegion />
    </CrumbContext.Provider>
  );
}

export function PageHeader({
  title,
  sub,
  actions,
  eyebrow,
}: {
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow" style={{ marginBottom: 6 }}>{eyebrow}</div>}
        <h1 className="page-title">{title}</h1>
        {sub && <p className="page-sub">{sub}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

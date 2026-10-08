// Public recruiter landing page (/recruteurs, /recruiters).
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  Check,
  EyeOff,
  Filter,
  GraduationCap,
  HelpCircle,
  Languages,
  LayoutDashboard,
  ListChecks,
  MessageSquareQuote,
  Scale,
  ScrollText,
  SearchX,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import type { Lang } from "../i18n";
import { usePrefs } from "../lib/prefs";
import { PublicLayout, publicPaths, REPO_URL } from "../components/PublicLayout";
import reportDark from "../assets/landing/report-dark.webp";
import reportLight from "../assets/landing/report-light.webp";
import guideLight from "../assets/landing/guide-light.webp";
import compareDark from "../assets/landing/compare-dark.webp";

const ISSUES_URL = `${REPO_URL}/issues`;
const MEASUREMENTS_URL = `${REPO_URL}/blob/main/docs/MEASUREMENTS.md`;

export function RecruitersPage({ lang }: { lang?: Lang }) {
  return (
    <PublicLayout lang={lang}>
      <Landing />
    </PublicLayout>
  );
}

function Landing() {
  const { t, lang, theme } = usePrefs();
  const l = t.pub.landing;
  const paths = publicPaths(lang);
  const problemIcons: LucideIcon[] = [SearchX, GraduationCap, HelpCircle];
  const howIcons: LucideIcon[] = [EyeOff, Filter, Languages, LayoutDashboard];
  const getIcons: LucideIcon[] = [Scale, MessageSquareQuote, ListChecks, ScrollText];

  return (
    <div className="landing">
      {/* ---------------------------------------------------------- hero */}
      <section className="hero land-hero" aria-labelledby="land-h">
        <div className="land-hero-text">
          <p className="eyebrow">{l.eyebrow}</p>
          <h1 id="land-h" className="land-title">
            {l.title}
          </h1>
          <p className="land-sub">{l.sub}</p>
          <div className="row wrap" style={{ gap: 10 }}>
            <Link to={paths.try} className="btn btn-primary btn-lg">
              {l.ctaTry}
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
            <a href={ISSUES_URL} className="btn btn-lg">
              {l.ctaDemo}
            </a>
          </div>
          <p className="xs faint">{l.demoNote}</p>
        </div>
        <figure className="land-shot">
          <img src={theme === "light" ? reportLight : reportDark} alt={l.shotAlt} width={1170} height={990} loading="eager" />
        </figure>
      </section>

      {/* ---------------------------------------------------------- problem */}
      <section className="land-section" aria-labelledby="land-problem">
        <header className="land-head">
          <h2 id="land-problem">{l.problem.title}</h2>
          <p>{l.problem.lead}</p>
        </header>
        <ul className="land-cards cols-3">
          {l.problem.items.map((it, i) => {
            const Icon = problemIcons[i] ?? HelpCircle;
            return (
              <li key={it.t} className="card land-card">
                <span className="land-icon tone-neutral">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <h3>{it.t}</h3>
                <p>{it.d}</p>
              </li>
            );
          })}
        </ul>
      </section>

      {/* ---------------------------------------------------------- how */}
      <section className="land-section" aria-labelledby="land-how">
        <header className="land-head">
          <h2 id="land-how">{l.how.title}</h2>
        </header>
        <ol className="land-steps">
          {l.how.steps.map((st, i) => {
            const Icon = howIcons[i] ?? Check;
            return (
              <li key={st.t} className="land-step">
                <span className="land-step-num">{String(i + 1).padStart(2, "0")}</span>
                <span className="land-icon">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <h3>{st.t}</h3>
                <p>{st.d}</p>
              </li>
            );
          })}
        </ol>
      </section>

      {/* ---------------------------------------------------------- what you get */}
      <section className="land-section" aria-labelledby="land-get">
        <header className="land-head">
          <h2 id="land-get">{l.get.title}</h2>
        </header>
        <div className="land-split">
          <ul className="land-list">
            {l.get.items.map((it, i) => {
              const Icon = getIcons[i] ?? Check;
              return (
                <li key={it.t}>
                  <span className="land-icon">
                    <Icon size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <h3>{it.t}</h3>
                    <p>{it.d}</p>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="land-shots">
            <figure className="land-shot">
              <img src={guideLight} alt={l.shot2Alt} width={1170} height={760} loading="lazy" />
            </figure>
            <figure className="land-shot">
              <img src={compareDark} alt="" width={1102} height={620} loading="lazy" />
            </figure>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------------- measured */}
      <section className="land-section" aria-labelledby="land-measured">
        <header className="land-head">
          <h2 id="land-measured">{l.measured.title}</h2>
          <p>{l.measured.lead}</p>
        </header>
        <ul className="land-metrics">
          {l.measured.items.map((m) => (
            <li key={m.v} className="card land-metric">
              <span className="land-metric-v">{m.v}</span>
              <p>{m.d}</p>
            </li>
          ))}
        </ul>
        <a href={MEASUREMENTS_URL} className="row small" style={{ gap: 6, marginTop: 16, display: "inline-flex" }}>
          <BookOpenCheck size={16} aria-hidden="true" />
          {l.measured.link}
        </a>
      </section>

      {/* ---------------------------------------------------------- compliance */}
      <section className="land-section" aria-labelledby="land-comp">
        <div className="card land-compliance">
          <div>
            <span className="land-icon tone-ok">
              <ShieldCheck size={22} aria-hidden="true" />
            </span>
            <h2 id="land-comp">{l.compliance.title}</h2>
            <p className="muted">{l.compliance.lead}</p>
          </div>
          <ul className="land-checks">
            {l.compliance.items.map((c) => (
              <li key={c}>
                <BadgeCheck size={18} aria-hidden="true" />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ---------------------------------------------------------- faq */}
      <section className="land-section" aria-labelledby="land-faq">
        <header className="land-head">
          <h2 id="land-faq">{l.faq.title}</h2>
        </header>
        <div className="faq">
          {l.faq.items.map((f) => (
            <details key={f.q} className="faq-item">
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------- final CTA */}
      <section className="hero land-final" aria-labelledby="land-final">
        <h2 id="land-final">{l.final.title}</h2>
        <p className="muted">{l.final.sub}</p>
        <div className="row wrap" style={{ gap: 10, justifyContent: "center" }}>
          <Link to={paths.try} className="btn btn-primary btn-lg">
            {l.ctaTry}
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
          <a href={REPO_URL} className="btn btn-lg">
            {t.pub.nav.source}
          </a>
        </div>
      </section>
    </div>
  );
}

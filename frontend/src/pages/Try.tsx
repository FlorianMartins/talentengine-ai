// Public sandbox (/essai, /try): a candidate checks their real work against a job offer.
// No account, no API key, nothing stored server-side (the backend analyses in memory).
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Briefcase,
  Check,
  ChevronRight,
  ClipboardCopy,
  ClipboardList,
  EyeOff,
  FileSearch,
  FileText,
  FolderGit2,
  Github,
  GraduationCap,
  Link2,
  Loader2,
  Lock,
  MessageSquareQuote,
  PencilLine,
  Plus,
  RotateCcw,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Trash2,
  TrendingUp,
  UserRound,
  UserX,
  X,
} from "lucide-react";
import { api, ApiError, BASE_PATH } from "../api/client";
import type {
  DashboardReport,
  Family,
  Importance,
  JobProfile,
  OfferAnalysis,
  TryConfig,
  TryMatchResult,
} from "../api/types";
import { FAMILIES } from "../api/types";
import { useAsync, usePrefs, useToast } from "../lib/prefs";
import { cx, levelIndex } from "../lib/format";
import { PublicLayout, publicPaths, REPO_URL } from "../components/PublicLayout";
import { BandChip, ErrorState, FamilyIcon, ImportanceChip, Skeleton, StatusChip } from "../components/feedback";
import { DropZone, RangeField, Segmented } from "../components/controls";
import { Meter, ScoreRing } from "../components/charts";
import { SkillCard } from "./ReportSections";
import type { Lang } from "../i18n";

const DOC_EXT = /\.(pdf|docx|md|markdown|txt)$/i;
const DOC_ACCEPT =
  ".pdf,.docx,.md,.markdown,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown";

type Step = 1 | 2 | 3;
type Mode = "offer" | "preset";

const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

export function TryPage({ lang: routeLang }: { lang?: Lang }) {
  return (
    <PublicLayout lang={routeLang}>
      <Sandbox />
    </PublicLayout>
  );
}

function Sandbox() {
  const { t, lang } = usePrefs();
  const s = t.pub.sandbox;
  const toast = useToast();
  const cfg = useAsync(() => api.tryConfig(lang), [lang]);

  const [step, setStep] = useState<Step>(1);
  // step 1 — the role
  const [mode, setMode] = useState<Mode | null>(null);
  const [offerTab, setOfferTab] = useState<"text" | "url">("text");
  const [offerText, setOfferText] = useState("");
  const [offerUrl, setOfferUrl] = useState("");
  const [analysing, setAnalysing] = useState(false);
  const [offerError, setOfferError] = useState("");
  const [offer, setOffer] = useState<OfferAnalysis | null>(null);
  const [job, setJob] = useState<JobProfile | null>(null);
  const [presetId, setPresetId] = useState("");
  // step 2 — the profile (kept in memory between attempts)
  const [cv, setCv] = useState<File | null>(null);
  const [docs, setDocs] = useState<File[]>([]);
  const [github, setGithub] = useState("");
  const [portfolio, setPortfolio] = useState("");
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [tried, setTried] = useState(false);
  // step 3 — the match
  const [running, setRunning] = useState(false);
  const [matchError, setMatchError] = useState("");
  const [result, setResult] = useState<TryMatchResult | null>(null);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [step]);

  const config = cfg.data;
  const limits = config?.limits ?? { matches_per_hour: 0, max_repos: 5, max_links: 3, max_documents: 3, max_file_mb: 8 };
  const preset = config?.presets.find((p) => p.id === presetId) ?? null;
  const roleTitle = mode === "offer" ? job?.title ?? "" : preset?.title ?? "";
  const roleReady = mode === "offer" ? Boolean(job && job.criteria.length > 0) : Boolean(preset);

  const analyse = async () => {
    setAnalysing(true);
    setOfferError("");
    try {
      const r = await api.tryOffer(offerTab === "text" ? { text: offerText, locale: lang } : { url: offerUrl.trim(), locale: lang });
      setOffer(r);
      setJob(r.job);
    } catch (e) {
      setOfferError(e instanceof ApiError ? (e.status === 0 ? t.common.network : e.message) : String(e));
    } finally {
      setAnalysing(false);
    }
  };

  // ------------------------------------------------------------------ step 2 validation
  const githubUrls = lines(github);
  const portfolioUrls = lines(portfolio);
  const problems = useMemo(() => {
    const p: string[] = [];
    if (!cv && docs.length === 0 && githubUrls.length === 0 && portfolioUrls.length === 0) p.push(s.profile.needContent);
    if (githubUrls.length > limits.max_repos) p.push(s.profile.tooMany(s.profile.github, limits.max_repos));
    if (portfolioUrls.length > limits.max_links) p.push(s.profile.tooMany(s.profile.portfolio, limits.max_links));
    if (name.trim().length < 2) p.push(s.profile.needName);
    if (!consent) p.push(s.profile.needConsent);
    return p;
  }, [cv, docs, githubUrls.length, portfolioUrls.length, name, consent, limits, s]);

  const acceptFiles = (files: File[]) =>
    files.filter((f) => {
      if (!DOC_EXT.test(f.name)) return toast.push("warning", s.profile.badType(f.name)), false;
      if (f.size > limits.max_file_mb * 1024 * 1024) return toast.push("warning", s.profile.tooBig(f.name, limits.max_file_mb)), false;
      return true;
    });

  const run = async (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (problems.length || !roleReady) return;
    setRunning(true);
    setMatchError("");
    try {
      const r = await api.tryMatch({
        consent,
        identity_name: name.trim(),
        locale: lang,
        job: mode === "offer" && job ? job : undefined,
        preset_id: mode === "preset" ? presetId : undefined,
        github_urls: githubUrls,
        portfolio_urls: portfolioUrls,
        cv,
        documents: docs,
      });
      setResult(r);
      setStep(3);
    } catch (err) {
      let msg = err instanceof ApiError ? err.message : String(err);
      if (err instanceof ApiError) {
        if (err.status === 0) msg = t.common.network;
        else if (err.status === 429) msg = `${s.errors.rate} ${err.message}`;
        else if (err.status === 503) msg = s.errors.busy;
      }
      setMatchError(msg);
      toast.push("error", msg);
    } finally {
      setRunning(false);
    }
  };

  if (cfg.loading && !config) {
    return (
      <div className="try">
        <Skeleton h={200} r={16} />
        <Skeleton h={320} r={16} />
      </div>
    );
  }
  if (cfg.error) return <ErrorState error={cfg.error} onRetry={cfg.reload} />;
  if (config && !config.enabled) {
    return (
      <div className="try">
        <p className="callout callout-warn">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{s.disabled}</span>
        </p>
      </div>
    );
  }

  return (
    <div className="try">
      {step !== 3 && (
        <section className="try-hero hero">
          <p className="eyebrow">{s.eyebrow}</p>
          <h1 className="try-title">{s.title}</h1>
          <p className="try-sub">{s.subtitle}</p>
          <PrivacyStrip />
        </section>
      )}

      <Stepper step={step} canGo={(n) => n < step || (n === 2 && roleReady) || (n === 3 && Boolean(result))} onGo={setStep} />

      {step === 1 && config && (
        <section className="stack-lg" aria-labelledby="try-job-h">
          <h2 id="try-job-h" className="try-h2">
            {s.job.title}
          </h2>
          <div className="choice-grid">
            <button type="button" className="choice" aria-pressed={mode === "offer"} onClick={() => setMode("offer")}>
              <span className="choice-icon">
                <ScanSearch size={22} aria-hidden="true" />
              </span>
              <b>{s.job.haveOffer}</b>
              <span>{s.job.haveOfferD}</span>
            </button>
            <button type="button" className="choice" aria-pressed={mode === "preset"} onClick={() => setMode("preset")}>
              <span className="choice-icon">
                <Briefcase size={22} aria-hidden="true" />
              </span>
              <b>{s.job.preset}</b>
              <span>{s.job.presetD}</span>
            </button>
          </div>

          {mode === "offer" && (
            <div className="panel">
              <Segmented<"text" | "url">
                label={s.job.tabsLabel}
                value={offerTab}
                onChange={setOfferTab}
                options={[
                  { value: "text", label: s.job.tabText },
                  { value: "url", label: s.job.tabUrl },
                ]}
              />
              {offerTab === "text" ? (
                <div className="field">
                  <label htmlFor="offer-text" className="sr-only">
                    {s.job.textLabel}
                  </label>
                  <textarea
                    id="offer-text"
                    className="textarea"
                    style={{ minHeight: 180 }}
                    maxLength={60000}
                    placeholder={s.job.textPh}
                    value={offerText}
                    onChange={(e) => setOfferText(e.target.value)}
                  />
                </div>
              ) : (
                <div className="field">
                  <label htmlFor="offer-url" className="sr-only">
                    {s.job.urlLabel}
                  </label>
                  <div className="input-icon">
                    <Link2 size={16} aria-hidden="true" />
                    <input
                      id="offer-url"
                      className="input"
                      type="url"
                      inputMode="url"
                      maxLength={2000}
                      placeholder={s.job.urlPh}
                      value={offerUrl}
                      onChange={(e) => setOfferUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && offerUrl.trim() && void analyse()}
                    />
                  </div>
                  <p className="hint">{s.job.urlHint}</p>
                </div>
              )}
              <div className="row wrap">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={analyse}
                  disabled={analysing || (offerTab === "text" ? !offerText.trim() : !offerUrl.trim())}
                >
                  {analysing ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Sparkles size={16} aria-hidden="true" />}
                  {analysing ? s.job.analysing : s.job.analyse}
                </button>
              </div>
              {offerError && (
                <div className="callout callout-warn" role="alert">
                  <AlertTriangle size={16} aria-hidden="true" />
                  <div>
                    <b>{offerError}</b>
                    <p className="small muted" style={{ marginTop: 2 }}>
                      {s.job.failedHint}
                    </p>
                  </div>
                </div>
              )}
              {offer && job && <OfferEditor config={config} offer={offer} job={job} onChange={setJob} />}
            </div>
          )}

          {mode === "preset" && (
            <div className="preset-grid try-presets" role="list">
              {config.presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="listitem"
                  className="preset"
                  aria-pressed={presetId === p.id}
                  onClick={() => setPresetId(p.id)}
                >
                  <div className="row" style={{ gap: 10 }}>
                    <FamilyIcon family={p.family} size={16} />
                    <b style={{ flex: 1 }}>{p.title}</b>
                    {presetId === p.id && <Check size={16} aria-label={s.job.selected} style={{ color: "var(--accent-text)" }} />}
                  </div>
                  <p>{p.summary}</p>
                  <span className="xs faint">{s.job.evaluatedOn}</span>
                  <span className="chips">
                    {p.criteria.map((c) => (
                      <span key={c} className="chip chip-plain">
                        <span>{c}</span>
                      </span>
                    ))}
                  </span>
                </button>
              ))}
            </div>
          )}

          <div className="try-actions">
            {mode && !roleReady && <span className="small muted">{mode === "offer" && job ? s.job.needCriteria : s.job.needJob}</span>}
            <span className="spacer" />
            <button type="button" className="btn btn-primary" disabled={!roleReady} onClick={() => setStep(2)}>
              {s.job.continue}
              <ArrowRight size={16} aria-hidden="true" />
            </button>
          </div>
        </section>
      )}

      {step === 2 && (
        <form className="stack-lg" onSubmit={run} noValidate aria-labelledby="try-prof-h" aria-busy={running}>
          <div className="role-summary">
            <span className="eyebrow">{s.profile.forJob}</span>
            <b>{roleTitle}</b>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setStep(1)}>
              <PencilLine size={14} aria-hidden="true" />
              {s.profile.change}
            </button>
          </div>
          <div>
            <h2 id="try-prof-h" className="try-h2">
              {s.profile.title}
            </h2>
            <p className="muted small" style={{ marginTop: 6 }}>
              {s.profile.hint}
            </p>
          </div>

          {running ? (
            <Progress />
          ) : (
            <>
              <div className="grid-2" style={{ alignItems: "start" }}>
                <section className="panel" aria-labelledby="tp-docs">
                  <h3 id="tp-docs" className="panel-title" style={{ fontSize: 16 }}>
                    <FileText size={18} aria-hidden="true" />
                    {s.profile.cv}
                  </h3>
                  {cv ? (
                    <ul className="file-list">
                      <FileRow file={cv} onRemove={() => setCv(null)} />
                    </ul>
                  ) : (
                    <DropZone accept={DOC_ACCEPT} label={s.profile.cv} hint={s.profile.cvHint(limits.max_file_mb)} onFiles={(f) => setCv(acceptFiles(f)[0] ?? null)} />
                  )}
                  <div className="divider" />
                  <span className="label">
                    {s.profile.docs} <span className="opt">({t.common.optional})</span>
                  </span>
                  {docs.length < limits.max_documents && (
                    <DropZone
                      accept={DOC_ACCEPT}
                      multiple
                      label={s.profile.docs}
                      hint={s.profile.docsHint(limits.max_documents, limits.max_file_mb)}
                      onFiles={(f) => setDocs((d) => [...d, ...acceptFiles(f)].slice(0, limits.max_documents))}
                    />
                  )}
                  {docs.length > 0 && (
                    <ul className="file-list">
                      {docs.map((d, i) => (
                        <FileRow key={`${d.name}-${i}`} file={d} onRemove={() => setDocs(docs.filter((_, j) => j !== i))} />
                      ))}
                    </ul>
                  )}
                </section>

                <div className="stack-lg">
                  <section className="panel" aria-labelledby="tp-gh">
                    <h3 id="tp-gh" className="panel-title" style={{ fontSize: 16 }}>
                      <Github size={18} aria-hidden="true" />
                      <label htmlFor="tp-gh-urls">{s.profile.github}</label>
                    </h3>
                    <textarea
                      id="tp-gh-urls"
                      className="textarea"
                      style={{ minHeight: 84, fontFamily: "var(--font-mono)", fontSize: 13 }}
                      spellCheck={false}
                      placeholder="https://github.com/…"
                      value={github}
                      aria-describedby="tp-gh-h"
                      onChange={(e) => setGithub(e.target.value)}
                    />
                    <p id="tp-gh-h" className="hint">
                      {s.profile.githubHint(limits.max_repos)}
                    </p>
                  </section>
                  <section className="panel" aria-labelledby="tp-pf">
                    <h3 id="tp-pf" className="panel-title" style={{ fontSize: 16 }}>
                      <Sparkles size={18} aria-hidden="true" />
                      <label htmlFor="tp-pf-urls">{s.profile.portfolio}</label>
                    </h3>
                    <textarea
                      id="tp-pf-urls"
                      className="textarea"
                      style={{ minHeight: 72, fontFamily: "var(--font-mono)", fontSize: 13 }}
                      spellCheck={false}
                      placeholder="https://www.behance.net/…"
                      value={portfolio}
                      aria-describedby="tp-pf-h"
                      onChange={(e) => setPortfolio(e.target.value)}
                    />
                    <p id="tp-pf-h" className="hint">
                      {s.profile.portfolioHint(limits.max_links)}
                    </p>
                  </section>
                </div>
              </div>

              <section className="panel" aria-labelledby="tp-id">
                <h3 id="tp-id" className="panel-title" style={{ fontSize: 16 }}>
                  <UserRound size={18} aria-hidden="true" />
                  {s.profile.name}
                </h3>
                <div className="field" style={{ maxWidth: 480 }}>
                  <label htmlFor="tp-name" className="sr-only">
                    {s.profile.name}
                  </label>
                  <input
                    id="tp-name"
                    className="input"
                    autoComplete="name"
                    maxLength={200}
                    value={name}
                    aria-invalid={tried && name.trim().length < 2}
                    aria-describedby="tp-name-h"
                    onChange={(e) => setName(e.target.value)}
                  />
                  <p id="tp-name-h" className="hint row" style={{ gap: 6, alignItems: "flex-start" }}>
                    <EyeOff size={13} aria-hidden="true" style={{ flex: "none", marginTop: 2 }} />
                    {s.profile.nameHint}
                  </p>
                </div>
                <label className="check" style={{ fontSize: 14 }}>
                  <input type="checkbox" checked={consent} aria-invalid={tried && !consent} onChange={(e) => setConsent(e.target.checked)} />
                  <span>{s.profile.consent}</span>
                </label>
              </section>

              {((tried && problems.length > 0) || matchError) && (
                <div className={cx("callout", matchError ? "callout-danger" : "callout-warn")} role="alert">
                  <AlertTriangle size={16} aria-hidden="true" />
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {matchError && <li>{matchError}</li>}
                    {tried && problems.map((p) => <li key={p}>{p}</li>)}
                  </ul>
                </div>
              )}

              <div className="try-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setStep(1)}>
                  <ArrowLeft size={16} aria-hidden="true" />
                  {s.profile.back}
                </button>
                <span className="spacer" />
                <button type="submit" className="btn btn-primary">
                  <ScanSearch size={16} aria-hidden="true" />
                  {s.profile.run}
                </button>
              </div>
            </>
          )}
        </form>
      )}

      {step === 3 && result && (
        <Result
          result={result}
          onAgain={() => {
            setResult(null);
            setOffer(null);
            setJob(null);
            setPresetId("");
            setMode(null);
            setOfferText("");
            setOfferUrl("");
            setStep(1);
          }}
          onEdit={() => setStep(2)}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ pieces

function PrivacyStrip() {
  const { t } = usePrefs();
  const p = t.pub.privacy;
  const items = [
    { icon: ShieldCheck, t: p.stored, d: p.storedD },
    { icon: EyeOff, t: p.masked, d: p.maskedD },
    { icon: UserX, t: p.account, d: p.accountD },
    { icon: Github, t: p.open, d: p.openD, href: REPO_URL },
  ];
  return (
    <ul className="privacy-strip" aria-label={p.title}>
      {items.map((x) => (
        <li key={x.t}>
          <x.icon size={16} aria-hidden="true" />
          <span>
            <b>{x.href ? <a href={x.href}>{x.t}</a> : x.t}</b>
            <span>{x.d}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function Stepper({ step, canGo, onGo }: { step: Step; canGo: (n: Step) => boolean; onGo: (n: Step) => void }) {
  const { t } = usePrefs();
  const labels = t.pub.sandbox.steps;
  return (
    <nav aria-label={t.pub.sandbox.stepsLabel}>
      <ol className="stepper">
        {([1, 2, 3] as const).map((n) => {
          const state = n < step ? "done" : n === step ? "current" : "todo";
          return (
            <li key={n} className={cx("step", `is-${state}`)}>
              <button type="button" disabled={n === step || !canGo(n)} onClick={() => onGo(n)} aria-current={n === step ? "step" : undefined}>
                <span className="step-dot">{state === "done" ? <Check size={14} aria-hidden="true" /> : n}</span>
                <span className="step-label">{labels[n - 1]}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function OfferEditor({
  config,
  offer,
  job,
  onChange,
}: {
  config: TryConfig;
  offer: OfferAnalysis;
  job: JobProfile;
  onChange: (j: JobProfile) => void;
}) {
  const { t } = usePrefs();
  const s = t.pub.sandbox.job;
  const [pick, setPick] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const labelOf = useMemo(() => new Map(config.skills.map((k) => [k.id, k.label])), [config.skills]);
  const traceOf = useMemo(() => new Map(offer.traces.map((tr) => [tr.skill_id, tr])), [offer.traces]);
  const used = new Set(job.criteria.map((c) => c.skill_id));
  const byFamily = FAMILIES.map((f) => [f, config.skills.filter((k) => k.family === f && !used.has(k.id))] as const).filter(
    ([, list]) => list.length > 0,
  );
  const update = (i: number, patch: Partial<JobProfile["criteria"][number]>) =>
    onChange({ ...job, criteria: job.criteria.map((c, j) => (j === i ? { ...c, ...patch } : c)) });

  return (
    <div className="stack">
      <p className="callout callout-ok" role="status">
        <Check size={16} aria-hidden="true" />
        <span>{s.detected(job.criteria.length, offer.source === "text" ? s.sourceText : offer.source)}</span>
      </p>
      {offer.warnings.map((w) => (
        <p key={w} className="callout callout-warn">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{w}</span>
        </p>
      ))}
      <div className="field">
        <label htmlFor="offer-title">{s.jobTitle}</label>
        <input id="offer-title" className="input" maxLength={160} value={job.title} onChange={(e) => onChange({ ...job, title: e.target.value })} />
      </div>
      <div>
        <h3 className="label" style={{ fontSize: 15 }}>
          {s.criteria}
        </h3>
        <p className="hint" style={{ marginTop: 4 }}>
          {s.criteriaHint}
        </p>
      </div>
      <ul className="offer-crit">
        {job.criteria.map((c, i) => {
          const label = labelOf.get(c.skill_id) ?? traceOf.get(c.skill_id)?.label ?? c.skill_id;
          const trace = traceOf.get(c.skill_id);
          const isOpen = Boolean(open[c.skill_id]);
          return (
            <li key={c.skill_id} className="oc">
              <div className="oc-head">
                <b>{label}</b>
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm"
                  aria-label={s.remove(label)}
                  onClick={() => onChange({ ...job, criteria: job.criteria.filter((_, j) => j !== i) })}
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              </div>
              <div className="oc-body">
                <Segmented<Importance>
                  className="tone-importance"
                  label={`${t.studio.importance} — ${label}`}
                  value={c.importance}
                  onChange={(v) => update(i, { importance: v })}
                  options={(["essential", "important", "bonus"] as const).map((v) => ({ value: v, label: t.importance[v] }))}
                />
                <RangeField
                  label={<span className="small">{t.studio.minLevel}</span>}
                  ariaLabel={`${t.studio.minLevel} — ${label}`}
                  value={c.min_level}
                  min={0}
                  max={4}
                  step={0.25}
                  format={(v) => t.levels[levelIndex(v)] ?? ""}
                  onChange={(v) => update(i, { min_level: v })}
                />
              </div>
              <button
                type="button"
                className="disclosure"
                aria-expanded={isOpen}
                onClick={() => setOpen({ ...open, [c.skill_id]: !isOpen })}
              >
                <ChevronRight size={14} aria-hidden="true" />
                {s.why}
                {trace && <span className="faint" style={{ fontWeight: 400 }}>· {s.mentions(trace.mentions)}</span>}
              </button>
              {isOpen &&
                (trace && trace.lines.length ? (
                  <ul className="trace-lines">
                    {trace.lines.map((l, k) => (
                      <li key={k}>
                        <MessageSquareQuote size={13} aria-hidden="true" />
                        <span>{l}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="xs faint">{s.addedByYou}</p>
                ))}
            </li>
          );
        })}
      </ul>
      {job.criteria.length < 40 && byFamily.length > 0 && (
        <div className="row wrap" style={{ gap: 8 }}>
          <select className="select" style={{ flex: "1 1 240px", maxWidth: 420 }} value={pick} aria-label={s.addPick} onChange={(e) => setPick(e.target.value)}>
            <option value="">{s.addPick}</option>
            {byFamily.map(([f, list]) => (
              <optgroup key={f} label={t.families[f as Family]}>
                {list.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          <button
            type="button"
            className="btn"
            disabled={!pick}
            onClick={() => {
              onChange({
                ...job,
                criteria: [...job.criteria, { skill_id: pick, importance: "important", weight: 1, min_level: 2, axis_focus: null, note: "" }],
              });
              setPick("");
            }}
          >
            <Plus size={16} aria-hidden="true" />
            {s.add}
          </button>
        </div>
      )}
    </div>
  );
}

function FileRow({ file, onRemove }: { file: File; onRemove: () => void }) {
  const { t } = usePrefs();
  const kb = file.size > 1024 * 1024 ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(file.size / 1024))} KB`;
  return (
    <li className="file-item">
      <FileText size={18} aria-hidden="true" style={{ color: "var(--accent-text)", flex: "none" }} />
      <span className="truncate" style={{ flex: 1 }}>
        {file.name}
      </span>
      <span className="xs faint num">{kb}</span>
      <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label={t.apply.fileRemove(file.name)} onClick={onRemove}>
        <X size={15} aria-hidden="true" />
      </button>
    </li>
  );
}

function Progress() {
  const { t } = usePrefs();
  const p = t.pub.sandbox.progress;
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setI((n) => Math.min(n + 1, p.stages.length - 1)), 2200);
    return () => window.clearInterval(id);
  }, [p.stages.length]);
  return (
    <section className="panel progress-panel" role="status" aria-live="polite" aria-label={p.title}>
      <div className="scan" aria-hidden="true" />
      <h3 className="panel-title">
        <Loader2 size={18} className="spin" aria-hidden="true" />
        {p.title}
      </h3>
      <ol className="stages">
        {p.stages.map((label, k) => (
          <li key={label} className={cx(k < i && "is-done", k === i && "is-current")}>
            <span className="stage-dot">{k < i ? <Check size={12} aria-hidden="true" /> : null}</span>
            <span>{label}</span>
          </li>
        ))}
      </ol>
      <div className="progress-bar" aria-hidden="true">
        <span style={{ width: `${((i + 1) / p.stages.length) * 92}%` }} />
      </div>
      <p className="hint">{p.hint}</p>
    </section>
  );
}

// ------------------------------------------------------------------ result

function Result({ result, onAgain, onEdit }: { result: TryMatchResult; onAgain: () => void; onEdit: () => void }) {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const r: DashboardReport = result.report;
  const s = t.pub.sandbox.result;
  const credW = r.credentials.weight_applied;
  const [ticked, setTicked] = useState<Record<string, boolean>>({});
  const paths = publicPaths(lang);
  const copyLink = () => {
    const url = `${window.location.origin}${BASE_PATH}${paths.try}`;
    void navigator.clipboard
      ?.writeText(url)
      .then(() => toast.push("success", s.copied))
      .catch(() => toast.push("info", url));
  };
  const actions = (
    <div className="row wrap" style={{ gap: 8 }}>
      <button type="button" className="btn btn-primary" onClick={onAgain}>
        <RotateCcw size={16} aria-hidden="true" />
        {s.again}
      </button>
      <button type="button" className="btn" onClick={onEdit}>
        <PencilLine size={16} aria-hidden="true" />
        {s.editProfile}
      </button>
      <button type="button" className="btn btn-ghost" onClick={copyLink}>
        <ClipboardCopy size={16} aria-hidden="true" />
        {s.copyLink}
      </button>
    </div>
  );

  return (
    <div className="stack-lg">
      <section className="hero try-result-hero" aria-labelledby="res-h">
        <div className="report-hero">
          <ScoreRing value={r.compatibility_pct} size={176} stroke={12} glow caption={t.report.compatibility} />
          <div className="stack" style={{ minWidth: 0, width: "100%" }}>
            <div className="stack-sm" style={{ gap: 6 }}>
              <span className="eyebrow">{s.eyebrow}</span>
              <h1 id="res-h" className="try-title" style={{ fontSize: "clamp(1.4rem, 3.4vw, 2rem)" }}>
                {s.title(r.job_title)}
              </h1>
              <div className="row wrap" style={{ gap: 8 }}>
                <BandChip band={r.evidence_band} />
                <span className="xs faint">{t.band.hint}</span>
              </div>
            </div>
            <div className="breakdown">
              <div className="bd-item">
                <span className="eyebrow">{s.skills}</span>
                <span className="bd-value">{r.skills_component_pct.toFixed(0)} %</span>
                <span className="xs faint">{s.weight(`${Math.round((1 - credW) * 100)} %`)}</span>
              </div>
              <div className="bd-item is-secondary">
                <span className="eyebrow">{s.creds}</span>
                <span className="bd-value" style={{ color: "var(--text-2)" }}>
                  {r.credentials_component_pct.toFixed(0)} %
                </span>
                <span className="xs faint">{s.weight(`${Math.round(credW * 100)} %`)}</span>
              </div>
              <div className="bd-item">
                <span className="eyebrow">{s.confidence}</span>
                <span className="bd-value">{Math.round(r.confidence * 100)} %</span>
                <span className="xs faint">{s.confidenceHint}</span>
              </div>
            </div>
          </div>
        </div>
        <p className="notice" style={{ marginTop: 20 }}>
          {s.notice}
        </p>
        <p className="xs faint row" style={{ gap: 6, marginTop: 10 }}>
          <Lock size={12} aria-hidden="true" />
          {s.notStored}
        </p>
        <div style={{ marginTop: 20 }}>{actions}</div>
      </section>

      {r.warnings.length > 0 && (
        <div className="callout callout-warn" role="note">
          <AlertTriangle size={16} aria-hidden="true" />
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {r.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* criteria */}
      <section className="panel" aria-labelledby="res-crit">
        <div>
          <h2 id="res-crit" className="panel-title">
            <ClipboardList size={18} aria-hidden="true" />
            {s.criteria}
          </h2>
          <p className="panel-hint">{s.criteriaHint}</p>
        </div>
        <div className="crit-matrix" role="list">
          {r.criteria.map((c) => (
            <div key={c.skill_id} className="cm-row" role="listitem">
              <div className="cm-label" style={{ minWidth: 0 }}>
                <b>{c.label}</b>
                <div className="row wrap" style={{ gap: 6, marginTop: 4 }}>
                  <ImportanceChip importance={c.importance} />
                </div>
              </div>
              <div className="cm-bar">
                <Meter
                  value={c.observed_level}
                  max={4}
                  mark={c.required_level}
                  label={`${c.label}: ${t.report.observed} ${c.observed_level.toFixed(2)}, ${t.report.required} ${c.required_level.toFixed(2)} / 4`}
                  color={c.status === "demonstrated" ? "var(--ok)" : c.status === "partial" ? "var(--warn)" : "var(--neutral)"}
                />
                <div className="cm-levels">
                  <span>
                    {t.report.observed} · <b style={{ color: "var(--text)" }}>{t.levels[levelIndex(c.observed_level)]}</b>
                  </span>
                  <span>
                    ▍{t.report.required} · {t.levels[levelIndex(c.required_level)]}
                  </span>
                </div>
              </div>
              <StatusChip status={c.status} />
            </div>
          ))}
        </div>
      </section>

      {/* proofs */}
      <section className="panel" aria-labelledby="res-proof">
        <div>
          <h2 id="res-proof" className="panel-title">
            <FileSearch size={18} aria-hidden="true" />
            {s.proofs}
          </h2>
          <p className="panel-hint">{s.proofsHint}</p>
        </div>
        {r.validated_skills.length === 0 ? (
          <p className="callout callout-neutral">
            <FileSearch size={16} aria-hidden="true" />
            <span>{s.noProofs}</span>
          </p>
        ) : (
          <div className="skill-grid">
            {r.validated_skills.map((v) => (
              <SkillCard key={v.skill_id} skill={v} candidateRef={r.candidate_ref} imageIds={new Set()} />
            ))}
          </div>
        )}
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* improve */}
        <section className="panel" aria-labelledby="res-imp">
          <div>
            <h2 id="res-imp" className="panel-title">
              <TrendingUp size={18} aria-hidden="true" />
              {s.improve}
            </h2>
            <p className="panel-hint">{s.improveHint}</p>
          </div>
          {result.tips.length === 0 && r.gaps.length === 0 ? (
            <p className="small muted">{s.improveEmpty}</p>
          ) : (
            <ul className="gap-list">
              {result.tips.map((tip) => (
                <li key={tip} className="gap">
                  <Sparkles size={16} aria-hidden="true" />
                  <p className="small">{tip}</p>
                </li>
              ))}
              {r.gaps.map((g) => (
                <li key={g.skill_id} className={cx("gap", g.declared_by_candidate && "is-declared")}>
                  <TrendingUp size={16} aria-hidden="true" />
                  <div className="stack-sm" style={{ gap: 4, minWidth: 0 }}>
                    <div className="row wrap" style={{ gap: 8 }}>
                      <b className="small">{g.label}</b>
                      <ImportanceChip importance={g.importance} />
                    </div>
                    <p className="small muted">{g.suggestion}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* what was analysed */}
        <section className="panel" aria-labelledby="res-art">
          <h2 id="res-art" className="panel-title">
            <FolderGit2 size={18} aria-hidden="true" />
            {s.analysed}
          </h2>
          <ul className="file-list">
            {result.artifacts.map((a, i) => (
              <li key={`${a.label}-${i}`} className="file-item" style={{ flexWrap: "wrap" }}>
                {a.kind === "repository" ? <Github size={16} aria-hidden="true" /> : <FileText size={16} aria-hidden="true" />}
                <b className="small">{a.label}</b>
                {a.status === "quarantined" && (
                  <span className="chip chip-warn">
                    <span>{s.quarantined}</span>
                  </span>
                )}
                <span className="spacer" />
                <span className="xs faint">
                  {a.kind === "repository" && a.files > 0 && <>{s.files(a.files)} · </>}
                  {s.masked(a.masked)}
                </span>
              </li>
            ))}
          </ul>
          {result.artifacts.some((a) => a.injection_suspected) && (
            <p className="callout callout-warn">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{s.injection}</span>
            </p>
          )}
        </section>
      </div>

      {/* questions */}
      {r.interview_guide.length > 0 && (
        <section className="stack" aria-labelledby="res-q">
          <div>
            <h2 id="res-q" className="panel-title">
              <MessageSquareQuote size={18} aria-hidden="true" />
              {s.questions}
            </h2>
            <p className="panel-hint">{s.questionsHint}</p>
          </div>
          <ol className="q-grid" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {r.interview_guide.map((q, qi) => (
              <li key={`${q.skill_id}-${qi}`} className="card q-card">
                <span className="q-num" aria-hidden="true">
                  {qi + 1}
                </span>
                <div className="stack" style={{ minWidth: 0 }}>
                  <p className="q-text">{q.question}</p>
                  <p className="small muted">{q.purpose}</p>
                  <ul className="checklist">
                    {q.expected_key_points.map((k, ki) => {
                      const key = `${qi}-${ki}`;
                      return (
                        <li key={key}>
                          <label className={cx("check", ticked[key] && "is-done")}>
                            <input type="checkbox" checked={Boolean(ticked[key])} onChange={(e) => setTicked({ ...ticked, [key]: e.target.checked })} />
                            <span>{k}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                  <p className="xs faint mono">
                    {q.evidence.artifact_label} · {q.evidence.locator}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* credentials — secondary */}
      <section className="panel is-secondary" aria-labelledby="res-cred">
        <div>
          <h2 id="res-cred" className="panel-title">
            <GraduationCap size={16} aria-hidden="true" />
            {s.credentials}
          </h2>
          <p className="panel-hint">{s.credentialsHint(`${Math.round(credW * 100)} %`)}</p>
        </div>
        {r.credentials.items.length === 0 ? (
          <p className="small muted">{s.credentialsEmpty}</p>
        ) : (
          <ul className="chips" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {r.credentials.items.map((c, i) => (
              <li key={`${c.label}-${i}`} className={cx("chip", c.kind === "degree" ? "chip-plain" : "chip-violet")}>
                <span>{c.label}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="hero try-end">
        {actions}
        <Link to={paths.recruiters} className="recruiter-cta">
          {s.recruiterCta}
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </section>
    </div>
  );
}

// /test/:token — verification test player: distraction-free, server-paced, one question at a time.
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  Camera,
  CameraOff,
  CheckCircle2,
  Clock,
  EyeOff,
  Info,
  Link2Off,
  Loader2,
  Lock,
  Maximize,
  Moon,
  ShieldCheck,
  Sun,
  UserCheck,
} from "lucide-react";
import { assess, ApiError } from "../api/client";
import type { AssessFinish, AssessQuestion, AssessState } from "../api/types";
import { usePrefs, useToast } from "../lib/prefs";
import { cx } from "../lib/format";
import { useIntegrity } from "../lib/integrity";
import { QuestionTimer, useAnswer } from "../components/QuestionInputs";
import { Logo } from "../components/Shell";
import { ToastRegion } from "../components/feedback";
import { AssessResultsView } from "../components/AssessResultsView";
import { publicPaths } from "../components/PublicLayout";

type Phase = "loading" | "invalid" | "expired" | "seb" | "intro" | "question" | "finishing" | "done";

export function TestPlayerPage() {
  const { token = "" } = useParams();
  const { t, lang, setLang, theme, setTheme } = usePrefs();
  const toast = useToast();
  const [phase, setPhase] = useState<Phase>("loading");
  const [info, setInfo] = useState<AssessState | null>(null);
  const [q, setQ] = useState<AssessQuestion | null>(null);
  const [done, setDone] = useState<AssessFinish | null>(null);
  const [understood, setUnderstood] = useState(false);
  const integrity = useIntegrity(token, phase === "question");

  const finish = useCallback(async () => {
    setPhase("finishing");
    await integrity.flush(); // the summary must include every recorded event
    try {
      const r = await assess.finish(token);
      setDone(r);
      setPhase("done");
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    } catch (e) {
      toast.error(e);
      setPhase("question");
    }
  }, [token, integrity, toast]);

  const loadNext = useCallback(async () => {
    try {
      setQ(await assess.next(token));
      setPhase("question");
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) return void finish(); // no more questions or closed
      toast.error(e);
    }
  }, [token, finish, toast]);

  // initial state: resumes a running test (the server keeps the clock) or shows the end screen
  useEffect(() => {
    let alive = true;
    assess
      .state(token)
      .then(async (s) => {
        if (!alive) return;
        setInfo(s);
        if (s.locale !== lang) setLang(s.locale);
        if (s.seb_required && !window.SafeExamBrowser) return setPhase("seb");
        if (s.status === "expired") return setPhase("expired");
        if (s.status === "finished") {
          setDone(await assess.finish(token));
          return setPhase("done");
        }
        if (s.status === "running") return void loadNext();
        setPhase("intro");
      })
      .catch((e) => {
        if (!alive) return;
        setPhase(e instanceof ApiError && e.status === 403 ? "seb" : "invalid");
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const start = async () => {
    await integrity.enterFullscreen();
    await loadNext();
  };

  return (
    <div className="exam">
      <a className="skip-link" href="#main">
        {t.app.skip}
      </a>
      <header className="exam-bar">
        <Logo size={26} />
        <span className="exam-title truncate">
          {t.test.eyebrow}
          {info ? ` · ${info.job_title}` : ""}
        </span>
        <span className="spacer" />
        <button
          className="btn btn-ghost btn-icon btn-sm"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={theme === "dark" ? t.top.toLight : t.top.toDark}
        >
          {theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
        </button>
      </header>
      <main id="main" className="exam-main" tabIndex={-1}>
        {phase === "loading" && (
          <div className="exam-center" role="status">
            <Loader2 size={28} className="spin" aria-hidden="true" />
            <span className="sr-only">{t.common.loading}</span>
          </div>
        )}
        {(phase === "invalid" || phase === "expired") && (
          <div className="exam-card exam-center-card">
            <Link2Off size={32} aria-hidden="true" style={{ color: "var(--text-3)" }} />
            <h1 className="exam-h1">{phase === "expired" ? t.test.expired : t.test.invalid}</h1>
            <p className="muted">{t.test.invalidBody}</p>
          </div>
        )}
        {phase === "seb" && (
          <div className="exam-card exam-center-card">
            <Lock size={32} aria-hidden="true" style={{ color: "var(--accent-text)" }} />
            <h1 className="exam-h1">{t.test.sebTitle}</h1>
            <p className="muted" style={{ maxWidth: "60ch" }}>
              {t.test.sebBody}
            </p>
            <a className="btn btn-primary" href="https://safeexambrowser.org/download_en.html" target="_blank" rel="noreferrer">
              {t.test.sebLink}
            </a>
          </div>
        )}
        {phase === "intro" && info && <Intro info={info} understood={understood} setUnderstood={setUnderstood} onStart={start} />}
        {(phase === "question" || phase === "finishing") && q && info && (
          <QuestionView
            key={q.index}
            token={token}
            q={q}
            info={info}
            integrity={integrity}
            busy={phase === "finishing"}
            onDone={(next, total) => (next >= total ? void finish() : void loadNext())}
          />
        )}
        {phase === "done" && done && <EndScreen result={done} />}
      </main>
      <div className="exam-print-block" aria-hidden="true">
        {t.test.printBlocked}
      </div>
      <ToastRegion />
    </div>
  );
}

// ------------------------------------------------------------------ intro

function Intro({
  info,
  understood,
  setUnderstood,
  onStart,
}: {
  info: AssessState;
  understood: boolean;
  setUnderstood: (v: boolean) => void;
  onStart: () => void;
}) {
  const { t } = usePrefs();
  const [busy, setBusy] = useState(false);
  return (
    <div className="exam-card stack-lg">
      <div className="stack-sm">
        <span className="eyebrow">{t.test.eyebrow}</span>
        <h1 className="exam-h1">{info.job_title}</h1>
        <div className="row wrap" style={{ gap: 8 }}>
          <span className="chip chip-accent">
            <span>
              {t.test.level} · {t.test.levels[info.level]}
            </span>
          </span>
          <span className="chip chip-plain">
            <span>{t.test.questions(info.total)}</span>
          </span>
          <span className="chip chip-plain">
            <Clock size={12} aria-hidden="true" />
            <span>{t.test.duration(Math.max(1, Math.round(info.total_seconds / 60)))}</span>
          </span>
          {info.personal_questions > 0 && (
            <span className="chip chip-violet">
              <UserCheck size={12} aria-hidden="true" />
              <span>{t.test.personalCount(info.personal_questions)}</span>
            </span>
          )}
        </div>
      </div>

      <section aria-labelledby="ex-rules">
        <h2 id="ex-rules" className="exam-h2">
          {t.test.rulesTitle}
        </h2>
        <ul className="exam-rules">
          {t.test.rules.map((r) => (
            <li key={r}>
              <CheckCircle2 size={16} aria-hidden="true" />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="exam-notice" aria-labelledby="ex-notice">
        <h2 id="ex-notice" className="exam-h2">
          <ShieldCheck size={18} aria-hidden="true" /> {t.test.monitoredTitle}
        </h2>
        <ul className="exam-monitored">
          {t.test.monitored.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        <p className="exam-nocam">
          <CameraOff size={16} aria-hidden="true" />
          <b>{t.test.noCamera}</b>
        </p>
        <details className="exam-full-notice">
          <summary>
            {t.notice.title} <span className="faint">({t.notice.legal})</span>
          </summary>
          <p>{t.notice.full}</p>
        </details>
      </section>

      <label className="check" style={{ fontSize: 15 }}>
        <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
        <span>{t.test.understood}</span>
      </label>
      <div>
        <button
          className="btn btn-primary btn-lg"
          disabled={!understood || busy}
          onClick={() => {
            setBusy(true);
            onStart();
          }}
        >
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Maximize size={16} aria-hidden="true" />}
          {t.test.start}
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ question

type Integrity = ReturnType<typeof useIntegrity>;

function useCountdown(seconds: number) {
  const end = useRef(Date.now() + seconds * 1000);
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    const id = window.setInterval(() => setLeft(Math.max(0, Math.ceil((end.current - Date.now()) / 1000))), 250);
    return () => window.clearInterval(id);
  }, []);
  return left;
}

function QuestionView({
  token,
  q,
  info,
  integrity,
  busy,
  onDone,
}: {
  token: string;
  q: AssessQuestion;
  info: AssessState;
  integrity: Integrity;
  busy: boolean;
  onDone: (next: number, total: number) => void;
}) {
  const { t } = usePrefs();
  const toast = useToast();
  const left = useCountdown(q.remaining);
  const { ready, value, fields } = useAnswer(q, "q-stem");
  const [sending, setSending] = useState(false);
  const closed = useRef(false);

  // timer reached zero: the server closes the question, then the next one is served
  useEffect(() => {
    if (left > 0 || closed.current) return;
    closed.current = true;
    toast.push("warning", t.test.timeUp);
    assess
      .timeout(token, q.index)
      .then((r) => onDone(r.next, r.total))
      .catch(() => onDone(q.index + 1, q.total));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready || closed.current) return;
    closed.current = true;
    setSending(true);
    try {
      const r = await assess.answer(token, q.index, value());
      if (r.late) toast.push("warning", t.test.late);
      onDone(r.next, r.total);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) return onDone(q.index + 1, q.total);
      closed.current = false;
      setSending(false);
      toast.error(err);
    }
  };

  const veiled = integrity.state.away || integrity.state.shot;

  return (
    <form className="exam-q" onSubmit={submit} aria-busy={sending || busy}>
      <div className="exam-top">
        <div className="exam-progress">
          <span className="small" aria-live="polite">
            {t.test.progress(q.index + 1, q.total)}
          </span>
          <div className="progress-bar" aria-hidden="true">
            <span style={{ width: `${((q.index + 1) / q.total) * 100}%` }} />
          </div>
        </div>
        <QuestionTimer left={left} total={q.seconds} />
      </div>

      {integrity.state.fullscreenLeft && (
        <div className="callout callout-warn exam-banner" role="status">
          <AlertTriangle size={16} aria-hidden="true" />
          <span style={{ flex: 1 }}>{t.test.fullscreenOff}</span>
          <button type="button" className="btn btn-sm" onClick={() => void integrity.enterFullscreen()}>
            <Maximize size={14} aria-hidden="true" />
            {t.test.fullscreenBack}
          </button>
        </div>
      )}
      {integrity.state.blockedAt > 0 && Date.now() - integrity.state.blockedAt < 2500 && (
        <p className="exam-toast-inline" role="status">
          <EyeOff size={14} aria-hidden="true" /> {t.test.blocked}
        </p>
      )}

      <div className={cx("exam-area", veiled && "is-veiled")}>
        <Watermark text={info.watermark} />
        <div className="exam-content" aria-hidden={veiled}>
          <div className="row wrap" style={{ gap: 8 }}>
            {q.personal ? (
              <span className="chip chip-violet">
                <UserCheck size={12} aria-hidden="true" />
                <span>{t.test.personal}</span>
              </span>
            ) : (
              <span className="chip chip-plain">
                <span>{q.skill}</span>
              </span>
            )}
          </div>
          <h1 className="exam-stem" id="q-stem">
            {q.stem}
          </h1>
          {fields}
        </div>
        {veiled && (
          <div className="exam-veil" role="alert">
            {integrity.state.shot ? <Camera size={28} aria-hidden="true" /> : <EyeOff size={28} aria-hidden="true" />}
            <b>{integrity.state.shot ? t.test.screenshot : t.test.away}</b>
          </div>
        )}
      </div>

      <div className="exam-actions">
        <span className="xs faint row" style={{ gap: 6 }}>
          <Info size={13} aria-hidden="true" />
          {t.test.noBack}
        </span>
        <span className="spacer" />
        <button type="submit" className="btn btn-primary btn-lg" disabled={!ready || sending || busy}>
          {sending || busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}
          {t.test.submit}
        </button>
      </div>
    </form>
  );
}

/** Dynamic watermark: session id + live clock, repeated diagonally, slowly drifting (traceable photos). */
function Watermark({ text }: { text: string }) {
  const { lang } = usePrefs();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 4000);
    return () => window.clearInterval(id);
  }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const now = useMemo(() => new Date().toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-GB"), [tick, lang]);
  const label = `${text} · ${now}`;
  const dx = (tick * 23) % 120;
  const dy = (tick * 17) % 90;
  return (
    <div className="watermark" aria-hidden="true">
      <div className="watermark-grid" style={{ transform: `translate(${-dx}px, ${-dy}px) rotate(-24deg)` }}>
        {Array.from({ length: 48 }, (_, i) => (
          <span key={i}>{label}</span>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ end

function EndScreen({ result }: { result: AssessFinish }) {
  const { t, lang } = usePrefs();
  if (result.mode === "candidate" || !result.results) {
    return (
      <div className="exam-card exam-center-card">
        <CheckCircle2 size={40} aria-hidden="true" style={{ color: "var(--ok-text)" }} />
        <h1 className="exam-h1">{t.test.thanksTitle}</h1>
        <p className="muted">{t.test.thanksBody}</p>
      </div>
    );
  }
  return (
    <div className="exam-card stack-lg">
      <div className="stack-sm">
        <span className="eyebrow">{t.test.eyebrow}</span>
        <h1 className="exam-h1">{t.test.resultsTitle}</h1>
      </div>
      <AssessResultsView results={result.results} audience="self" />
      <div>
        <Link to={publicPaths(lang).try} className="btn">
          {t.test.backToTry}
        </Link>
      </div>
    </div>
  );
}

// /pilote/:token — AI-pilot test player. The candidate pilots a deliberately imperfect assistant to deliver
// a mission (chat + editor + virtual CI), then optionally changes a function of their own repository in
// five minutes. Tools are allowed: there is no anti-cheat layer here. The server keeps every clock.
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  CameraOff,
  CheckCircle2,
  ChevronDown,
  Clock,
  Code2,
  FilePlus2,
  FileText,
  Flag,
  Link2Off,
  Loader2,
  Moon,
  Play,
  Printer,
  RotateCcw,
  Save,
  Send,
  ShieldCheck,
  Sun,
  Target,
  Trash2,
  UserCheck,
  Workflow,
  XCircle,
} from "lucide-react";
import { ApiError, pilot } from "../api/client";
import type { PilotReport, PilotState, PilotTurn } from "../api/types";
import { usePrefs, useToast } from "../lib/prefs";
import { cx } from "../lib/format";
import { printPage } from "../lib/print";
import { Logo } from "../components/Shell";
import { Modal, ToastRegion } from "../components/feedback";
import { publicPaths } from "../components/PublicLayout";
import { PilotReportView } from "../components/PilotReportView";
import { InlineCode, TurnItem, timeOf } from "../components/PilotTurns";

const MAX_PROMPT = 4000;
type View = "loading" | "invalid" | "expired" | "brief" | "build" | "ownIntro" | "own" | "closing" | "done";

export function PilotPlayerPage() {
  const { token = "" } = useParams();
  const location = useLocation();
  const warning = (location.state as { warning?: string } | null)?.warning ?? "";
  const { t, lang, setLang, theme, setTheme } = usePrefs();
  const toast = useToast();
  const [view, setView] = useState<View>("loading");
  const [s, setS] = useState<PilotState | null>(null);
  const [report, setReport] = useState<PilotReport | null>(null);
  const [candidateDone, setCandidateDone] = useState(false);
  const [end, setEnd] = useState<number | null>(null); // client-side deadline derived from the server's remaining
  const wantIntro = useRef(false);
  const closing = useRef(false);

  const close = useCallback(async () => {
    if (closing.current) return;
    closing.current = true;
    setView("closing");
    try {
      const r = await pilot.close(token);
      if (r.mode === "sandbox" && r.report) {
        setReport(r.report);
        setS(await pilot.state(token).catch(() => null)); // the transcript, with the closing turn
      } else setCandidateDone(true);
      setView("done");
    } catch (e) {
      setView(e instanceof ApiError && e.status === 409 ? "expired" : "invalid");
    }
  }, [token]);

  const apply = useCallback(
    (st: PilotState) => {
      setS(st);
      if (st.locale !== lang) setLang(st.locale);
      const remaining = st.phase === "ownership" ? st.ownership_remaining : st.phase === "build" ? st.build_remaining : null;
      setEnd(remaining === null ? null : Date.now() + remaining * 1000);
      if (st.phase === "brief") setView("brief");
      else if (st.phase === "build") setView(wantIntro.current && st.ownership_available ? "ownIntro" : "build");
      else if (st.phase === "ownership") setView(st.ownership?.started_at ? "own" : "ownIntro");
      else void close();
    },
    [lang, setLang, close],
  );

  const refresh = useCallback(
    () =>
      pilot
        .state(token)
        .then(apply)
        .catch((e) => {
          if (e instanceof ApiError && e.status === 404) setView("invalid");
          else toast.error(e);
        }),
    [token, apply, toast],
  );

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const begin = async () => {
    try {
      apply(await pilot.begin(token));
    } catch (e) {
      toast.error(e);
      void refresh();
    }
  };
  const toOwnership = () => {
    wantIntro.current = true;
    setView("ownIntro");
  };
  const backToBuild = () => {
    wantIntro.current = false;
    setView("build");
  };
  const startOwnership = async () => {
    try {
      apply(await pilot.startOwnership(token));
    } catch (e) {
      toast.error(e);
      void refresh();
    }
  };

  const wide = view === "build" || view === "own";
  return (
    <div className={cx("exam pilot", wide && "is-ide")}>
      <a className="skip-link" href="#main">
        {t.app.skip}
      </a>
      <header className="exam-bar pilot-bar">
        <Logo size={26} />
        <span className="exam-title truncate pilot-bar-title">
          {t.pilot.eyebrow}
          {s ? ` · ${s.scenario.title}` : ""}
        </span>
        <span className="spacer" />
        {wide && end !== null && s && (
          <Countdown
            end={end}
            total={view === "own" ? s.ownership?.seconds ?? 300 : s.build_minutes * 60}
            onZero={() => {
              toast.push("warning", t.pilot.build.timeOver);
              void refresh();
            }}
          />
        )}
        <button
          className="btn btn-ghost btn-icon btn-sm no-print"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={theme === "dark" ? t.top.toLight : t.top.toDark}
        >
          {theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
        </button>
      </header>
      <main id="main" className={cx("exam-main", wide && "pilot-main")} tabIndex={-1}>
        {(view === "loading" || view === "closing") && (
          <div className="exam-center" role="status">
            <Loader2 size={28} className="spin" aria-hidden="true" />
            <span className={view === "closing" ? "small" : "sr-only"}>{view === "closing" ? t.pilot.end.closing : t.common.loading}</span>
          </div>
        )}
        {(view === "invalid" || view === "expired") && (
          <div className="exam-card exam-center-card">
            <Link2Off size={32} aria-hidden="true" style={{ color: "var(--text-3)" }} />
            <h1 className="exam-h1">{view === "expired" ? t.pilot.end.expired : t.pilot.end.invalid}</h1>
            <p className="muted">{t.pilot.end.invalidBody}</p>
          </div>
        )}
        {view === "brief" && s && <Brief s={s} warning={warning} onStart={begin} />}
        {view === "build" && s && end !== null && (
          <Workspace key="build" mode="build" token={token} s={s} end={end} onRefresh={refresh} onFinish={toOwnership} onClose={close} />
        )}
        {view === "ownIntro" && s && s.ownership && (
          <OwnershipIntro s={s} onStart={startOwnership} onBack={s.phase === "build" ? backToBuild : undefined} />
        )}
        {view === "own" && s && end !== null && (
          <Workspace key="own" mode="own" token={token} s={s} end={end} onRefresh={refresh} onFinish={close} onClose={close} />
        )}
        {view === "done" && (candidateDone || !report ? <Thanks /> : <SandboxEnd report={report} transcript={s?.transcript ?? []} />)}
      </main>
      <ToastRegion />
    </div>
  );
}

// ------------------------------------------------------------------ countdown

function useLeft(end: number): number {
  const [left, setLeft] = useState(() => Math.max(0, Math.ceil((end - Date.now()) / 1000)));
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, Math.ceil((end - Date.now()) / 1000)));
    tick();
    const id = window.setInterval(tick, 500);
    return () => window.clearInterval(id);
  }, [end]);
  return left;
}

function fmt(left: number): string {
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
}

function Countdown({ end, total, onZero }: { end: number; total: number; onZero: () => void }) {
  const { t } = usePrefs();
  const left = useLeft(end);
  const fired = useRef(false);
  const [announce, setAnnounce] = useState("");
  useEffect(() => {
    fired.current = false; // a fresh server reading: allowed to ask again
  }, [end]);
  useEffect(() => {
    if (left > 0) {
      fired.current = false;
      if (left === 120 || left === 60 || left === 300) setAnnounce(`${t.pilot.build.timeLeft} ${fmt(left)}`);
      return;
    }
    if (fired.current) return;
    fired.current = true;
    // the server is the clock: give it a second, then read the new phase
    const id = window.setTimeout(onZero, 1200);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left, end]);
  const urgent = left < 120;
  const pct = total > 0 ? Math.min(100, (left / total) * 100) : 0;
  return (
    <div className={cx("pl-clock", urgent && "is-urgent")} role="timer" aria-label={`${t.pilot.build.timeLeft} ${fmt(left)}`}>
      <Clock size={14} aria-hidden="true" />
      <span className="num">{fmt(left)}</span>
      <span className="pl-clock-bar" aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </span>
      <span className="sr-only" aria-live="assertive">
        {announce}
      </span>
    </div>
  );
}

// ------------------------------------------------------------------ brief

function Brief({ s, warning, onStart }: { s: PilotState; warning: string; onStart: () => Promise<void> }) {
  const { t } = usePrefs();
  const b = t.pilot.brief;
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <div className="exam-card stack-lg">
      <div className="stack-sm">
        <span className="eyebrow">
          {t.pilot.eyebrow} · {s.job_title}
        </span>
        <h1 className="exam-h1">{s.scenario.title}</h1>
        <div className="row wrap" style={{ gap: 8 }}>
          <span className="chip chip-accent">
            <span>
              {b.level} · {t.pilot.levels[s.level]}
            </span>
          </span>
          <span className="chip chip-plain">
            <Clock size={12} aria-hidden="true" />
            <span>{b.budget(s.build_minutes)}</span>
          </span>
          {s.ownership_available && (
            <span className="chip chip-violet">
              <UserCheck size={12} aria-hidden="true" />
              <span>{b.ownershipToo}</span>
            </span>
          )}
        </div>
      </div>

      {warning && (
        <div className="callout callout-warn" role="status">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>
            <b>{b.warning} —</b> {warning}
          </span>
        </div>
      )}

      <section className="pl-mission" aria-labelledby="pl-mission">
        <h2 id="pl-mission" className="exam-h2">
          <Target size={18} aria-hidden="true" /> {b.mission}
        </h2>
        <p>
          <InlineCode text={s.scenario.brief} />
        </p>
      </section>

      <section aria-labelledby="pl-rules">
        <h2 id="pl-rules" className="exam-h2">
          {b.rulesTitle}
        </h2>
        <ul className="exam-rules">
          {b.rules.map((r) => (
            <li key={r}>
              <CheckCircle2 size={16} aria-hidden="true" />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="exam-notice" aria-labelledby="pl-rec">
        <h2 id="pl-rec" className="exam-h2">
          <ShieldCheck size={18} aria-hidden="true" /> {b.recordedTitle}
        </h2>
        <ul className="exam-monitored">
          {b.recorded.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
        <p className="exam-nocam">
          <CameraOff size={16} aria-hidden="true" />
          <b>{b.noCamera}</b>
        </p>
        <p className="exam-full-notice" style={{ lineHeight: 1.6 }}>
          {s.notice}
        </p>
        <details className="exam-full-notice">
          <summary>
            {t.notice.title} <span className="faint">({t.notice.legal})</span>
          </summary>
          <p>{t.notice.full}</p>
        </details>
      </section>

      <label className="check" style={{ fontSize: 15 }}>
        <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />
        <span>{b.understood}</span>
      </label>
      <div>
        <button
          className="btn btn-primary btn-lg"
          disabled={!ok || busy}
          onClick={() => {
            setBusy(true);
            void onStart().finally(() => setBusy(false));
          }}
        >
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
          {b.start}
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ ownership intro

function OwnershipIntro({ s, onStart, onBack }: { s: PilotState; onStart: () => Promise<void>; onBack?: () => void }) {
  const { t } = usePrefs();
  const o = t.pilot.ownership;
  const task = s.ownership!;
  const [busy, setBusy] = useState(false);
  return (
    <div className="exam-card stack-lg">
      <div className="stack-sm">
        <span className="eyebrow">{o.eyebrow}</span>
        <h1 className="exam-h1">{o.title}</h1>
        <p className="muted" style={{ maxWidth: "72ch" }}>
          {o.lead}
        </p>
      </div>
      <section className="pl-mission is-own" aria-labelledby="pl-constraint">
        <h2 id="pl-constraint" className="exam-h2">
          <Target size={18} aria-hidden="true" /> {o.constraint}
        </h2>
        <p>
          <InlineCode text={task.instruction} />
        </p>
        <div className="row wrap" style={{ gap: 8, marginTop: 12 }}>
          <span className="chip chip-violet mono">
            <Code2 size={12} aria-hidden="true" />
            <span>{o.where(task.function, task.path)}</span>
          </span>
          <span className="chip chip-plain">
            <span>{o.lines(task.start_line, task.end_line)}</span>
          </span>
          <span className="chip chip-plain">
            <span>{o.repo(task.repository)}</span>
          </span>
        </div>
      </section>
      <ul className="exam-rules">
        {o.rules.map((r) => (
          <li key={r}>
            <CheckCircle2 size={16} aria-hidden="true" />
            <span>{r}</span>
          </li>
        ))}
      </ul>
      <div className="row wrap" style={{ gap: 10 }}>
        <button
          className="btn btn-primary btn-lg"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void onStart().finally(() => setBusy(false));
          }}
        >
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
          {o.start}
        </button>
        {onBack && (
          <button className="btn btn-ghost" onClick={onBack}>
            <ArrowLeft size={16} aria-hidden="true" />
            {o.back}
          </button>
        )}
      </div>
      {onBack && <p className="xs faint">{o.buildStillOpen}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ workspace (build + ownership)

type Tab = "chat" | "code" | "ci";

interface LastChange {
  added: number;
  removed: number;
  fresh: boolean;
  turn: number;
}

function Workspace({
  mode,
  token,
  s,
  end,
  onRefresh,
  onFinish,
  onClose,
}: {
  mode: "build" | "own";
  token: string;
  s: PilotState;
  end: number;
  onRefresh: () => Promise<void>;
  /** "Finish" in build mode: goes to the ownership intro when there is one */
  onFinish: () => void;
  onClose: () => Promise<void>;
}) {
  const { t } = usePrefs();
  const b = t.pilot.build;
  const toast = useToast();
  const left = useLeft(end);
  const [tab, setTab] = useState<Tab>("chat");
  const [codeBadge, setCodeBadge] = useState(false);
  const [busy, setBusy] = useState<"" | "chat" | "save" | "ci" | "delete">("");
  const [pending, setPending] = useState(""); // prompt shown while the assistant replies
  const [confirm, setConfirm] = useState(false);
  const task = mode === "own" ? s.ownership : null;
  const phase = mode === "own" ? "ownership" : "build";
  const turns = useMemo(() => s.transcript.filter((x) => x.phase === phase), [s.transcript, phase]);
  const paths = useMemo(() => Object.keys(s.files).sort(), [s.files]);
  const [selected, setSelected] = useState<string>(() => task?.path ?? paths.find((p) => !p.endsWith(".md")) ?? paths[0] ?? "");
  const [drafts, setDrafts] = useState<Record<string, { text: string; base: string }>>({});

  // keep the selection valid when files appear or disappear
  useEffect(() => {
    if (selected && !(selected in s.files) && !(selected in drafts)) setSelected(paths[0] ?? "");
  }, [paths, selected, s.files, drafts]);

  const last = useMemo(() => {
    const out: Record<string, LastChange> = {};
    for (const turn of turns)
      for (const c of turn.changes) out[c.path] = { added: c.added_lines, removed: c.removed_lines, fresh: c.before_sha === "", turn: turn.index };
    return out;
  }, [turns]);

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409) {
      toast.push("warning", /turn limit/i.test(e.message) ? b.turnLimit : b.timeOver);
      void onRefresh();
    } else toast.error(e);
  };

  const send = async (message: string): Promise<boolean> => {
    setBusy("chat");
    setPending(message);
    try {
      const r = await pilot.chat(token, message);
      await onRefresh();
      if (r.reply.changes.length && tab !== "code") setCodeBadge(true);
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      setPending("");
      setBusy("");
    }
  };

  const save = async (path: string) => {
    const d = drafts[path];
    if (!d) return;
    setBusy("save");
    try {
      await pilot.edit(token, path, d.text);
      setDrafts(({ [path]: _, ...rest }) => rest);
      await onRefresh();
      toast.push("success", b.saved);
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  };

  const createFile = async (path: string) => {
    setBusy("save");
    try {
      await pilot.edit(token, path, "", true);
      await onRefresh();
      setSelected(path);
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  };

  const remove = async (path: string) => {
    if (!window.confirm(b.deleteConfirm(path))) return;
    setBusy("delete");
    try {
      await pilot.edit(token, path, null);
      setDrafts(({ [path]: _, ...rest }) => rest);
      await onRefresh();
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  };

  const runCi = async () => {
    setBusy("ci");
    try {
      await pilot.ci(token);
      await onRefresh();
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  };

  const open = (path: string) => {
    if (!(path in s.files)) return;
    setSelected(path);
    setTab("code");
    setCodeBadge(false);
  };

  const ciRuns = turns.filter((x) => x.kind === "ci");
  const remote = selected ? s.files[selected] ?? "" : "";
  const draft = selected ? drafts[selected] : undefined;
  const value = draft ? draft.text : remote;
  const tabs: { id: Tab; label: string; icon: typeof Bot }[] = [
    { id: "chat", label: b.tabs.chat, icon: Bot },
    { id: "code", label: b.tabs.code, icon: Code2 },
    ...(mode === "build" ? [{ id: "ci" as Tab, label: b.tabs.ci, icon: Workflow }] : []),
  ];

  return (
    <div className={cx("pl-ws", mode === "own" && "is-own")} data-tab={tab}>
      <div className="pl-ws-head">
        {mode === "build" ? (
          <details className="pl-brief">
            <summary>
              <Target size={14} aria-hidden="true" />
              <span className="truncate">{b.missionToggle}</span>
              <ChevronDown size={14} aria-hidden="true" className="pl-caret" />
            </summary>
            <p className="small">
              <InlineCode text={s.scenario.brief} />
            </p>
          </details>
        ) : (
          task && (
            <div className="pl-brief is-open is-own">
              <p className="small">
                <Target size={14} aria-hidden="true" style={{ verticalAlign: -2, marginRight: 6, color: "var(--violet-text)" }} />
                <InlineCode text={task.instruction} />
              </p>
            </div>
          )
        )}
        <button className="btn btn-primary pl-finish" onClick={() => setConfirm(true)}>
          <Flag size={16} aria-hidden="true" />
          {mode === "build" ? b.finish : t.pilot.ownership.finish}
        </button>
      </div>
      {left > 0 && left < 120 && (
        <div className="callout callout-warn pl-hurry" role="status">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{b.hurry}</span>
        </div>
      )}

      <div className="tabs pl-tabs" role="tablist" aria-label={t.pilot.name}>
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            id={`pl-tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`pl-panel-${id}`}
            className="tab"
            onClick={() => {
              setTab(id);
              if (id === "code") setCodeBadge(false);
            }}
          >
            <Icon size={16} aria-hidden="true" />
            {label}
            {id === "code" && codeBadge && <span className="pl-dot" aria-label="•" />}
          </button>
        ))}
      </div>

      <div className="pl-grid">
        {/* ---------------------------------------------------------- chat */}
        <section id="pl-panel-chat" className="pl-panel pl-chat" aria-labelledby="pl-h-chat" data-panel="chat">
          <h2 id="pl-h-chat" className="pl-panel-title">
            <Bot size={16} aria-hidden="true" />
            {b.chatTitle}
          </h2>
          <ChatLog turns={turns} pending={pending} onOpen={open} />
          <Composer busy={busy === "chat"} onSend={send} placeholder={mode === "own" ? b.composerPhOwn : b.composerPh} />
        </section>

        {/* ---------------------------------------------------------- code */}
        <section id="pl-panel-code" className="pl-panel pl-code" aria-labelledby="pl-h-code" data-panel="code">
          <h2 id="pl-h-code" className="sr-only">
            {b.filesTitle}
          </h2>
          <FileTree
            paths={paths}
            selected={selected}
            last={last}
            drafts={drafts}
            onSelect={setSelected}
            onCreate={mode === "build" ? createFile : undefined}
            busy={busy !== ""}
          />
          <div className="pl-editor-pane">
            {selected ? (
              <>
                <div className="pl-editor-bar">
                  <FileText size={14} aria-hidden="true" />
                  <span className="mono xs truncate" style={{ flex: 1, minWidth: 0 }}>
                    {selected}
                  </span>
                  {last[selected] && !draft && (
                    <span className="xs faint pl-last" title={b.lastChange}>
                      #{last[selected]!.turn} <span className="pl-add">+{last[selected]!.added}</span> <span className="pl-del">−{last[selected]!.removed}</span>
                    </span>
                  )}
                  {draft && <span className="chip chip-warn"><span>{b.unsaved}</span></span>}
                  {draft && (
                    <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setDrafts(({ [selected]: _, ...rest }) => rest)} aria-label={b.revert} title={b.revert}>
                      <RotateCcw size={14} aria-hidden="true" />
                    </button>
                  )}
                  {mode === "build" && (
                    <button className="btn btn-ghost btn-icon btn-sm" onClick={() => void remove(selected)} aria-label={`${b.deleteFile} ${selected}`} title={b.deleteFile} disabled={busy !== ""}>
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  )}
                  <button className="btn btn-sm" onClick={() => void save(selected)} disabled={!draft || busy !== ""} title={b.saveHint}>
                    {busy === "save" ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Save size={14} aria-hidden="true" />}
                    {b.save}
                  </button>
                </div>
                {draft && draft.base !== remote && (
                  <div className="callout callout-warn pl-conflict" role="status">
                    <AlertTriangle size={14} aria-hidden="true" />
                    <span style={{ flex: 1 }}>{b.changedRemote}</span>
                    <button className="btn btn-sm" onClick={() => setDrafts(({ [selected]: _, ...rest }) => rest)}>
                      {b.takeRemote}
                    </button>
                  </div>
                )}
                <CodeEditor
                  key={selected}
                  path={selected}
                  value={value}
                  highlight={task && task.path === selected ? [task.start_line, task.end_line] : undefined}
                  highlightLabel={t.pilot.ownership.highlight}
                  onChange={(text) => setDrafts((d) => ({ ...d, [selected]: { text, base: d[selected]?.base ?? remote } }))}
                  onSave={() => void save(selected)}
                />
              </>
            ) : (
              <p className="small muted" style={{ padding: 16 }}>
                {b.noFile}
              </p>
            )}
          </div>
        </section>

        {/* ---------------------------------------------------------- CI */}
        {mode === "build" && (
          <section id="pl-panel-ci" className="pl-panel pl-ci" aria-labelledby="pl-h-ci" data-panel="ci">
            <h2 id="pl-h-ci" className="pl-panel-title">
              <Workflow size={16} aria-hidden="true" />
              {b.ciTitle}
            </h2>
            <p className="xs faint">{b.ciHint}</p>
            <button className="btn btn-primary" onClick={() => void runCi()} disabled={busy !== ""}>
              {busy === "ci" ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
              {b.runCi}
            </button>
            <CiResults runs={ciRuns} />
          </section>
        )}
      </div>

      {confirm && (
        <Modal
          title={mode === "build" ? b.finishTitle : t.pilot.ownership.finishTitle}
          onClose={() => setConfirm(false)}
          footer={
            <>
              <button className="btn" onClick={() => setConfirm(false)}>
                {b.keepWorking}
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  setConfirm(false);
                  if (mode === "build" && s.ownership_available) onFinish();
                  else void onClose();
                }}
              >
                <Flag size={16} aria-hidden="true" />
                {b.finishDo}
              </button>
            </>
          }
        >
          <p className="small">{mode === "build" ? b.finishBody : t.pilot.ownership.finishBody}</p>
          {mode === "build" && s.ownership_available && <p className="small muted">{b.finishOwnership}</p>}
          {Object.keys(drafts).length > 0 && (
            <p className="small" style={{ color: "var(--warn-text)" }}>
              {b.unsaved} — {Object.keys(drafts).join(", ")}
            </p>
          )}
        </Modal>
      )}
    </div>
  );
}

function ChatLog({ turns, pending, onOpen }: { turns: PilotTurn[]; pending: string; onOpen: (p: string) => void }) {
  const { t } = usePrefs();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns.length, pending]);
  const visible = turns.filter((x) => !(x.kind === "phase" && x.index === 0));
  return (
    <div className="pl-scroll" ref={ref}>
      {visible.length === 0 && !pending && <p className="small muted pl-empty">{t.pilot.build.chatEmpty}</p>}
      <ol className="pl-log" role="log" aria-live="polite" aria-relevant="additions" aria-label={t.pilot.build.chatTitle}>
        {visible.map((turn) => (
          <TurnItem key={turn.index} turn={turn} onOpen={onOpen} />
        ))}
        {pending && (
          <li className="pl-turn pl-msg is-mine is-pending">
            <div className="pl-bubble">
              <p className="pl-text">{pending}</p>
            </div>
          </li>
        )}
      </ol>
      {pending && (
        <p className="pl-typing small" role="status">
          <Loader2 size={14} className="spin" aria-hidden="true" />
          {t.pilot.build.thinking}
        </p>
      )}
    </div>
  );
}

function Composer({ busy, onSend, placeholder }: { busy: boolean; onSend: (m: string) => Promise<boolean>; placeholder: string }) {
  const { t } = usePrefs();
  const b = t.pilot.build;
  const [text, setText] = useState("");
  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    const m = text.trim();
    if (!m || busy) return;
    if (await onSend(m)) setText("");
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void submit();
    }
  };
  return (
    <form className="pl-composer" onSubmit={submit}>
      <label htmlFor="pl-prompt" className="sr-only">
        {b.composerLabel}
      </label>
      <textarea
        id="pl-prompt"
        className="textarea"
        value={text}
        maxLength={MAX_PROMPT}
        placeholder={placeholder}
        aria-describedby="pl-prompt-h"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        rows={3}
      />
      <div className="pl-composer-foot">
        <span id="pl-prompt-h" className="xs faint">
          {b.sendHint} · <span className={cx("num", text.length > MAX_PROMPT * 0.9 && "pl-near")}>{b.chars(text.length, MAX_PROMPT)}</span>
        </span>
        <span className="spacer" />
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !text.trim()}>
          {busy ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Send size={14} aria-hidden="true" />}
          {b.send}
        </button>
      </div>
    </form>
  );
}

function FileTree({
  paths,
  selected,
  last,
  drafts,
  onSelect,
  onCreate,
  busy,
}: {
  paths: string[];
  selected: string;
  last: Record<string, LastChange>;
  drafts: Record<string, unknown>;
  onSelect: (p: string) => void;
  onCreate?: (p: string) => Promise<void>;
  busy: boolean;
}) {
  const { t } = usePrefs();
  const b = t.pilot.build;
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const valid = /^[\w.\-/]+$/.test(name.trim()) && !name.includes("..") && !paths.includes(name.trim().replace(/^\/+/, ""));
  return (
    <nav className="pl-tree" aria-label={b.filesTitle}>
      <div className="pl-tree-head">
        <span className="eyebrow">{b.filesTitle}</span>
        {onCreate && (
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setAdding((v) => !v)} aria-label={b.newFile} title={b.newFile} aria-expanded={adding}>
            <FilePlus2 size={14} aria-hidden="true" />
          </button>
        )}
      </div>
      {adding && onCreate && (
        <form
          className="pl-new-file"
          onSubmit={(e) => {
            e.preventDefault();
            if (!valid) return;
            void onCreate(name.trim().replace(/^\/+/, "")).then(() => {
              setAdding(false);
              setName("");
            });
          }}
        >
          <label htmlFor="pl-new" className="sr-only">
            {b.newFile}
          </label>
          <input id="pl-new" className="input mono" value={name} placeholder={b.newFilePh} onChange={(e) => setName(e.target.value)} autoFocus />
          <div className="row" style={{ gap: 6 }}>
            <button type="submit" className="btn btn-sm btn-primary" disabled={!valid || busy}>
              {b.create}
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setAdding(false)}>
              {b.cancel}
            </button>
          </div>
        </form>
      )}
      <ul>
        {paths.map((p) => {
          const slash = p.lastIndexOf("/");
          const l = last[p];
          return (
            <li key={p}>
              <button className={cx("pl-file", p === selected && "is-on")} title={p} aria-current={p === selected ? "true" : undefined} onClick={() => onSelect(p)}>
                <FileText size={13} aria-hidden="true" />
                <span className="pl-file-name">
                  {slash > 0 && <span className="faint">{p.slice(0, slash + 1)}</span>}
                  {p.slice(slash + 1)}
                </span>
                {p in drafts && <span className="pl-dirty" aria-label={b.unsaved} title={b.unsaved} />}
                {l && (
                  <span className="pl-badge num" aria-label={`${b.lastChange} — +${l.added} −${l.removed}`}>
                    {l.fresh ? <em>{b.newBadge}</em> : null}
                    <span className="pl-add">+{l.added}</span>
                    <span className="pl-del">−{l.removed}</span>
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

const LINE_H = 20;
const PAD = 12;

function CodeEditor({
  path,
  value,
  onChange,
  onSave,
  highlight,
  highlightLabel,
}: {
  path: string;
  value: string;
  onChange: (v: string) => void;
  onSave: () => void;
  highlight?: [number, number];
  highlightLabel: string;
}) {
  const { t } = usePrefs();
  const [scroll, setScroll] = useState(0);
  const area = useRef<HTMLTextAreaElement>(null);
  const count = Math.max(1, value.split("\n").length);
  // scroll the highlighted function into view on open
  useEffect(() => {
    if (highlight && area.current) area.current.scrollTop = Math.max(0, (highlight[0] - 3) * LINE_H);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="pl-editor">
      <div className="pl-gutter" aria-hidden="true">
        <div style={{ transform: `translateY(${-scroll}px)` }}>
          {Array.from({ length: count }, (_, i) => (
            <span key={i} className={cx(highlight && i + 1 >= highlight[0] && i + 1 <= highlight[1] && "is-hl")}>
              {i + 1}
            </span>
          ))}
        </div>
      </div>
      <div className="pl-code-wrap">
        {highlight && (
          <div
            className="pl-hl"
            title={highlightLabel}
            aria-hidden="true"
            style={{ top: PAD + (highlight[0] - 1) * LINE_H - scroll, height: (highlight[1] - highlight[0] + 1) * LINE_H }}
          />
        )}
        <textarea
          ref={area}
          className="pl-textarea"
          value={value}
          wrap="off"
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          aria-label={t.pilot.build.editorLabel(path)}
          onScroll={(e) => setScroll(e.currentTarget.scrollTop)}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
              e.preventDefault();
              onSave();
            }
          }}
        />
      </div>
    </div>
  );
}

function CiResults({ runs }: { runs: PilotTurn[] }) {
  const { t, lang } = usePrefs();
  const b = t.pilot.build;
  const latest = runs[runs.length - 1];
  if (!latest) return <p className="small muted">{b.ciNever}</p>;
  const older = runs.slice(0, -1).reverse();
  return (
    <div className="stack-sm" aria-live="polite">
      <CiRun run={latest} n={runs.length} open />
      {older.length > 0 && (
        <>
          <span className="eyebrow" style={{ marginTop: 8 }}>
            {b.ciHistory}
          </span>
          {older.map((r, i) => (
            <CiRun key={r.index} run={r} n={runs.length - 1 - i} />
          ))}
        </>
      )}
      <span className="sr-only">{timeOf(latest.at, lang)}</span>
    </div>
  );
}

function CiRun({ run, n, open }: { run: PilotTurn; n: number; open?: boolean }) {
  const { t, lang } = usePrefs();
  const b = t.pilot.build;
  const ok = run.checks.filter((c) => c.passed).length;
  const head: ReactNode = (
    <>
      {run.passed ? <CheckCircle2 size={16} aria-hidden="true" /> : <XCircle size={16} aria-hidden="true" />}
      <b>{run.passed ? b.ciPassed : b.ciFailed}</b>
      <span className="xs num">{b.ciCount(ok, run.checks.length)}</span>
      <span className="spacer" />
      <span className="xs faint num">
        {b.ciRun(n)} · {b.turn(run.index)} · {timeOf(run.at, lang)}
      </span>
    </>
  );
  return (
    <details className={cx("pl-run", run.passed ? "is-ok" : "is-ko")} open={open}>
      <summary>{head}</summary>
      <ul className="pl-checks">
        {run.checks.map((c) => (
          <li key={c.id} className={c.passed ? "is-ok" : "is-ko"}>
            {c.passed ? <CheckCircle2 size={14} aria-hidden="true" /> : <XCircle size={14} aria-hidden="true" />}
            <div style={{ minWidth: 0 }}>
              <span className="small">{c.label}</span>
              {c.detail && <span className="mono xs faint pl-check-detail">{c.detail}</span>}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}

// ------------------------------------------------------------------ end

function Thanks() {
  const { t } = usePrefs();
  return (
    <div className="exam-card exam-center-card">
      <CheckCircle2 size={40} aria-hidden="true" style={{ color: "var(--ok-text)" }} />
      <h1 className="exam-h1">{t.pilot.end.thanksTitle}</h1>
      <p className="muted" style={{ maxWidth: "60ch" }}>
        {t.pilot.end.thanksBody}
      </p>
    </div>
  );
}

function SandboxEnd({ report, transcript }: { report: PilotReport; transcript: PilotTurn[] }) {
  const { t, lang } = usePrefs();
  return (
    <div className="exam-card stack-lg">
      <div className="stack-sm">
        <span className="eyebrow">{t.pilot.eyebrow}</span>
        <h1 className="exam-h1">{t.pilot.end.reportTitle}</h1>
        <p className="muted" style={{ maxWidth: "72ch" }}>
          {t.pilot.end.reportLead}
        </p>
      </div>
      <PilotReportView report={report} transcript={transcript} audience="self" />
      <div className="row wrap no-print" style={{ gap: 10 }}>
        <Link to={publicPaths(lang).try} className="btn btn-primary">
          {t.pilot.end.backToTry}
        </Link>
        <button className="btn" onClick={printPage}>
          <Printer size={16} aria-hidden="true" />
          {t.pilot.end.print}
        </button>
      </div>
    </div>
  );
}

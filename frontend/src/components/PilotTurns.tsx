// AI-pilot test: one telemetry turn (prompt, assistant reply, edit, CI run, phase change), shared by the
// player's chat and the transcripts of the report. Server texts that are fixed English markers
// ("build started", "edited x", "CI passed") are localised here.
import { Bot, CheckCircle2, FilePen, Flag, User, XCircle } from "lucide-react";
import type { PilotFileChange, PilotTurn } from "../api/types";
import type { Dict } from "../i18n";
import { usePrefs } from "../lib/prefs";
import { cx } from "../lib/format";

export function turnText(turn: PilotTurn, t: Dict): string {
  if (turn.kind === "phase") return t.pilot.phaseText[turn.text] ?? turn.text;
  if (turn.kind === "edit") {
    const m = /^(edited|deleted) (.+)$/.exec(turn.text);
    if (m && m[2]) return m[1] === "edited" ? t.pilot.edited(m[2]) : t.pilot.deleted(m[2]);
  }
  if (turn.kind === "ci") {
    const ok = turn.checks.filter((c) => c.passed).length;
    return `${turn.passed ? t.pilot.build.ciPassed : t.pilot.build.ciFailed} · ${t.pilot.build.ciCount(ok, turn.checks.length)}`;
  }
  return turn.text;
}

export function timeOf(iso: string, lang: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Renders `code` spans of a server text (scenario briefs and instructions use Markdown backticks). */
export function InlineCode({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("`") && p.endsWith("`") && p.length > 2 ? (
          <code key={i} className="pl-icode">
            {p.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

export function ChangeChip({ change, onOpen }: { change: PilotFileChange; onOpen?: (path: string) => void }) {
  const { t } = usePrefs();
  const gone = change.after_sha === "";
  const fresh = change.before_sha === "" && !gone;
  const body = (
    <>
      <FilePen size={12} aria-hidden="true" />
      <span className="pl-chip-path">{change.path}</span>
      {fresh && <span className="pl-new">{t.pilot.build.newBadge}</span>}
      <span className="pl-add num">+{change.added_lines}</span>
      <span className="pl-del num">−{change.removed_lines}</span>
    </>
  );
  return onOpen && !gone ? (
    <button type="button" className="pl-change" onClick={() => onOpen(change.path)} aria-label={`${t.pilot.build.openFile(change.path)} (+${change.added_lines} −${change.removed_lines})`}>
      {body}
    </button>
  ) : (
    <span className={cx("pl-change", gone && "is-gone")}>{body}</span>
  );
}

export function TurnItem({
  turn,
  anchor,
  onOpen,
  highlight,
}: {
  turn: PilotTurn;
  /** id prefix for evidence links (`${anchor}-turn-${index}`) */
  anchor?: string;
  onOpen?: (path: string) => void;
  highlight?: boolean;
}) {
  const { t, lang } = usePrefs();
  const b = t.pilot.build;
  const id = anchor ? `${anchor}-turn-${turn.index}` : undefined;
  const meta = (
    <span className="pl-meta">
      <span className="num">#{turn.index}</span> · {timeOf(turn.at, lang)}
    </span>
  );
  if (turn.kind === "phase") {
    return (
      <li id={id} className={cx("pl-turn pl-phase", highlight && "is-hl")} tabIndex={anchor ? -1 : undefined}>
        <Flag size={12} aria-hidden="true" />
        <span>{turnText(turn, t)}</span>
        {meta}
      </li>
    );
  }
  if (turn.kind === "edit" || turn.kind === "ci") {
    const Icon = turn.kind === "edit" ? FilePen : turn.passed ? CheckCircle2 : XCircle;
    return (
      <li id={id} className={cx("pl-turn pl-event", turn.kind === "ci" && (turn.passed ? "is-ok" : "is-ko"), highlight && "is-hl")} tabIndex={anchor ? -1 : undefined}>
        <Icon size={14} aria-hidden="true" />
        <span className="pl-event-text">{turnText(turn, t)}</span>
        {turn.changes.map((c) => (
          <ChangeChip key={c.path} change={c} onOpen={onOpen} />
        ))}
        {meta}
      </li>
    );
  }
  const mine = turn.kind === "prompt";
  return (
    <li id={id} className={cx("pl-turn pl-msg", mine ? "is-mine" : "is-bot", highlight && "is-hl")} tabIndex={anchor ? -1 : undefined}>
      <span className="pl-avatar" aria-hidden="true">
        {mine ? <User size={14} /> : <Bot size={14} />}
      </span>
      <div className="pl-bubble">
        <div className="pl-who">
          <b>{mine ? b.you : b.assistant}</b>
          {meta}
        </div>
        <p className="pl-text">{turn.text}</p>
        {turn.changes.length > 0 && (
          <div className="pl-changes">
            <span className="xs faint">{b.filesChanged(turn.changes.length)}</span>
            {turn.changes.map((c) => (
              <ChangeChip key={c.path} change={c} onOpen={onOpen} />
            ))}
          </div>
        )}
      </div>
    </li>
  );
}

export function PilotTranscript({ turns, anchor, hl }: { turns: PilotTurn[]; anchor: string; hl?: number | null }) {
  return (
    <ol className="pl-log pl-transcript">
      {turns.map((turn) => (
        <TurnItem key={turn.index} turn={turn} anchor={anchor} highlight={hl === turn.index} />
      ))}
    </ol>
  );
}

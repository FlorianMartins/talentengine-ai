import { Eye, KeyRound, Link2, Link2Off, Sparkles } from "lucide-react";
import { useSystem, useT } from "../lib/prefs";
import { Skeleton } from "./feedback";

/** One-line system status: vision detector, LLM provider, ledger integrity. */
export function StatusStrip() {
  const t = useT();
  const { runtime, chain } = useSystem();
  if (!runtime) {
    return (
      <div className="status-strip" aria-busy="true">
        <Skeleton h={30} w={180} r={999} />
        <Skeleton h={30} w={200} r={999} />
        <Skeleton h={30} w={170} r={999} />
      </div>
    );
  }
  const visionNone = !runtime.vision_detector || runtime.vision_detector === "none";
  const llmNone = !runtime.llm_provider || runtime.llm_provider === "none";
  return (
    <ul className="status-strip" aria-label={t.status.label} style={{ listStyle: "none", margin: 0, padding: 0 }}>
      <li className="status-item">
        <Eye size={14} aria-hidden="true" />
        <span>{t.status.vision}</span>
        <b>{visionNone ? t.status.visionNone : runtime.vision_detector}</b>
      </li>
      <li className="status-item">
        <Sparkles size={14} aria-hidden="true" />
        <span>{t.status.llm}</span>
        <b>{llmNone ? t.status.localOnly : `${runtime.llm_provider}${runtime.llm_model ? ` · ${runtime.llm_model}` : ""}`}</b>
      </li>
      <li className="status-item">
        {chain ? (
          <>
            <span className={chain.valid ? "pulse" : "pulse bad"} aria-hidden="true" />
            {chain.valid ? <Link2 size={14} aria-hidden="true" /> : <Link2Off size={14} aria-hidden="true" />}
            <span>{t.status.ledger}</span>
            <b>{chain.valid ? t.status.ledgerValid(chain.length) : t.status.ledgerBroken(chain.first_invalid_seq)}</b>
          </>
        ) : (
          <>
            <span className="pulse warn" aria-hidden="true" />
            <span>{t.status.ledger}</span>
            <b>—</b>
          </>
        )}
      </li>
      {runtime.auth_required && (
        <li className="status-item">
          <KeyRound size={14} aria-hidden="true" />
          <b>{t.status.auth}</b>
        </li>
      )}
    </ul>
  );
}

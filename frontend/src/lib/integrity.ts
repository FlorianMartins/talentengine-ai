// Anti-cheat layer of the verification test. Everything is a *signal* journalled to the server
// (POST /events, batched every 3 s, sendBeacon on page hide); nothing here ever blocks the candidate from finishing.
// No camera, microphone or screen-capture permission is ever requested.
import { useCallback, useEffect, useRef, useState } from "react";
import { assess } from "../api/client";
import type { AssessEvent, AssessEventType } from "../api/types";

/** Drag type used by the "order" question: internal drags are allowed, anything else is an external drop. */
export const ORDER_DRAG_TYPE = "application/x-te-order";

export interface IntegrityState {
  /** window lost focus or tab hidden: the question is veiled */
  away: boolean;
  /** brief veil after a print-screen key */
  shot: boolean;
  /** full screen was left (banner offering to go back) */
  fullscreenLeft: boolean;
  /** last blocked action, to show a short notice */
  blockedAt: number;
}

const isEditable = (el: EventTarget | null) =>
  el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || (el instanceof HTMLElement && el.isContentEditable);

export function useIntegrity(token: string, active: boolean) {
  const queue = useRef<AssessEvent[]>([]);
  const [state, setState] = useState<IntegrityState>({ away: false, shot: false, fullscreenLeft: false, blockedAt: 0 });
  const wasFull = useRef(false);

  const record = useCallback((type: AssessEventType, detail = "") => {
    queue.current.push({ type, detail: detail.slice(0, 200) });
  }, []);

  /** Sends what is queued (awaitable before finishing, so the summary includes every event). */
  const flush = useCallback(async () => {
    if (!queue.current.length) return;
    const batch = queue.current.splice(0, 50);
    try {
      await assess.events(token, batch);
    } catch {
      queue.current.unshift(...batch); // retried on the next tick
    }
  }, [token]);

  useEffect(() => {
    if (!active) return;
    const blocked = (type: AssessEventType, detail: string, e?: Event) => {
      e?.preventDefault();
      record(type, detail);
      setState((s) => ({ ...s, blockedAt: Date.now() }));
    };
    const veilShot = () => {
      setState((s) => ({ ...s, shot: true }));
      window.setTimeout(() => setState((s) => ({ ...s, shot: false })), 2000);
      // best effort: overwrite what the OS may have put on the clipboard
      void navigator.clipboard?.writeText("").catch(() => undefined);
    };

    const onCopy = (e: ClipboardEvent) => blocked("copy_attempt", "copy", e);
    const onCut = (e: ClipboardEvent) => blocked("cut_attempt", "cut", e);
    const onPaste = (e: ClipboardEvent) => blocked("paste_attempt", "paste", e);
    const onBeforeInput = (e: InputEvent) => {
      if (e.inputType === "insertFromPaste" || e.inputType === "insertFromPasteAsQuotation") blocked("paste_attempt", e.inputType, e);
      if (e.inputType === "insertFromDrop") blocked("drop_attempt", e.inputType, e);
    };
    const internal = (e: DragEvent) => Boolean(e.dataTransfer?.types.includes(ORDER_DRAG_TYPE));
    const onDrop = (e: DragEvent) => {
      if (!internal(e)) blocked("drop_attempt", (e.dataTransfer?.types ?? []).join(","), e);
    };
    const onDragOver = (e: DragEvent) => {
      if (!internal(e)) e.preventDefault(); // keeps the drop event (so it can be recorded and cancelled)
    };
    const onDragStart = (e: DragEvent) => {
      if (!(e.target instanceof HTMLElement && e.target.closest("[data-order-item]"))) e.preventDefault();
    };
    const onContext = (e: MouseEvent) => blocked("contextmenu", "", e);
    const onSelectStart = (e: Event) => {
      if (!isEditable(e.target)) e.preventDefault();
    };
    const onKeyDown = (e: KeyboardEvent) => {
      const k = e.key.toLowerCase();
      const mod = e.ctrlKey || e.metaKey;
      if (e.key === "F12" || (mod && e.shiftKey && ["i", "j", "c"].includes(k)) || (e.metaKey && e.altKey && ["i", "j", "c"].includes(k))) {
        return blocked("devtools", `${mod ? "mod+" : ""}${e.shiftKey ? "shift+" : ""}${e.key}`, e);
      }
      if (e.key === "PrintScreen") {
        record("printscreen", "key");
        return veilShot();
      }
      if (e.metaKey && e.shiftKey && ["3", "4", "5", "6"].includes(k)) {
        record("printscreen", `cmd+shift+${k}`); // macOS capture: cannot be prevented, only veiled
        return veilShot();
      }
      if (!mod) return;
      if (k === "c") return blocked("copy_attempt", "mod+c", e);
      if (k === "x") return blocked("cut_attempt", "mod+x", e);
      if (k === "v") return blocked("paste_attempt", "mod+v", e);
      if (k === "a" && !isEditable(e.target)) return blocked("copy_attempt", "mod+a", e);
      if (k === "p") return blocked("printscreen", "mod+p (print)", e);
      if (k === "s") return blocked("copy_attempt", "mod+s (save)", e);
      if (k === "u") return blocked("devtools", "mod+u (source)", e);
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.key === "PrintScreen") {
        record("printscreen", "keyup");
        veilShot();
      }
    };
    const onBlur = () => {
      record("blur");
      setState((s) => ({ ...s, away: true }));
    };
    const onFocus = () => {
      record("focus");
      setState((s) => ({ ...s, away: false }));
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        record("visibility_hidden");
        setState((s) => ({ ...s, away: true }));
      } else {
        record("visibility_visible");
        setState((s) => ({ ...s, away: !document.hasFocus() }));
      }
    };
    let lastFullscreenChange = 0;
    const onFullscreen = () => {
      lastFullscreenChange = Date.now();
      if (document.fullscreenElement) {
        wasFull.current = true;
        record("fullscreen_enter");
        setState((s) => ({ ...s, fullscreenLeft: false }));
      } else if (wasFull.current) {
        record("fullscreen_exit");
        setState((s) => ({ ...s, fullscreenLeft: true }));
      }
    };
    let resizeTimer = 0;
    const onResize = () => {
      window.clearTimeout(resizeTimer);
      // entering/leaving full screen resizes the viewport: not a signal on its own
      if (Date.now() - lastFullscreenChange < 1500) return;
      resizeTimer = window.setTimeout(() => record("resize", `${window.innerWidth}x${window.innerHeight}`), 800);
    };
    const onPageHide = () => {
      if (queue.current.length && assess.beacon(token, queue.current.slice(0, 50))) queue.current = [];
    };
    const onBeforePrint = () => record("printscreen", "print");

    const opts = { capture: true } as const;
    document.addEventListener("copy", onCopy, opts);
    document.addEventListener("cut", onCut, opts);
    document.addEventListener("paste", onPaste, opts);
    document.addEventListener("beforeinput", onBeforeInput as EventListener, opts);
    document.addEventListener("drop", onDrop, opts);
    document.addEventListener("dragover", onDragOver, opts);
    document.addEventListener("dragstart", onDragStart, opts);
    document.addEventListener("contextmenu", onContext, opts);
    document.addEventListener("selectstart", onSelectStart, opts);
    document.addEventListener("keydown", onKeyDown, opts);
    document.addEventListener("keyup", onKeyUp, opts);
    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("fullscreenchange", onFullscreen);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    window.addEventListener("resize", onResize);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeprint", onBeforePrint);
    wasFull.current = Boolean(document.fullscreenElement);
    // A second screen is a signal worth knowing (Window Management API; Chromium only).
    if ((window.screen as Screen & { isExtended?: boolean }).isExtended) record("multiple_screens", "screen.isExtended");
    document.documentElement.dataset.exam = "on";
    const timer = window.setInterval(() => void flush(), 3000);
    return () => {
      document.removeEventListener("copy", onCopy, opts);
      document.removeEventListener("cut", onCut, opts);
      document.removeEventListener("paste", onPaste, opts);
      document.removeEventListener("beforeinput", onBeforeInput as EventListener, opts);
      document.removeEventListener("drop", onDrop, opts);
      document.removeEventListener("dragover", onDragOver, opts);
      document.removeEventListener("dragstart", onDragStart, opts);
      document.removeEventListener("contextmenu", onContext, opts);
      document.removeEventListener("selectstart", onSelectStart, opts);
      document.removeEventListener("keydown", onKeyDown, opts);
      document.removeEventListener("keyup", onKeyUp, opts);
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("fullscreenchange", onFullscreen);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeprint", onBeforePrint);
      window.clearInterval(timer);
      window.clearTimeout(resizeTimer);
      delete document.documentElement.dataset.exam;
    };
  }, [active, token, record, flush]);

  const enterFullscreen = useCallback(async () => {
    try {
      await document.documentElement.requestFullscreen?.();
    } catch {
      record("fullscreen_exit", "refused");
    }
  }, [record]);

  return { state, record, flush, enterFullscreen };
}

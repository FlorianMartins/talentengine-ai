// Feedback surfaces: toasts, modal, skeletons, empty / error states, chips.
import { useEffect, useId, useRef, type ReactNode } from "react";
import {
  AlertTriangle,
  Bot,
  BriefcaseBusiness,
  ChefHat,
  CheckCircle2,
  CircleDashed,
  Code2,
  Database,
  Hammer,
  Handshake,
  Info,
  Megaphone,
  Palette,
  Scissors,
  Shapes,
  Users,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { ApiError } from "../api/client";
import type { CriterionStatus, DecisionKind, EvidenceBand, Family, Importance, Permission } from "../api/types";
import { useAccess, useT, useToast } from "../lib/prefs";
import { cx } from "../lib/format";

export function ToastRegion() {
  const { toasts, dismiss } = useToast();
  const t = useT();
  const icons = { info: Info, success: CheckCircle2, warning: AlertTriangle, error: XCircle };
  return (
    <div className="toast-region" role="region" aria-live="polite" aria-label="Notifications">
      {toasts.map((x) => {
        const Icon = icons[x.tone];
        return (
          <div key={x.id} className={cx("toast", `toast-${x.tone}`)} role={x.tone === "error" ? "alert" : "status"}>
            <Icon size={18} aria-hidden="true" />
            <div className="toast-body">
              {x.title && <div className="toast-title">{x.title}</div>}
              <div>{x.message}</div>
            </div>
            <button className="btn btn-ghost btn-icon btn-sm" onClick={() => dismiss(x.id)} aria-label={t.common.dismiss}>
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const t = useT();
  const titleId = useId();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    const focusables = () =>
      Array.from(
        node?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
    const first = focusables().find((el) => el.tagName !== "BUTTON" || !el.classList.contains("modal-x"));
    (first ?? node)?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const els = focusables();
        if (!els.length) return;
        const firstEl = els[0];
        const lastEl = els[els.length - 1];
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl?.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        className={cx("modal", wide && "modal-wide")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button className="btn btn-ghost btn-icon btn-sm modal-x" onClick={onClose} aria-label={t.common.close}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        {children}
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function Skeleton({ h = 16, w = "100%", r }: { h?: number; w?: number | string; r?: number }) {
  return <span className="skeleton" style={{ height: h, width: w, borderRadius: r }} aria-hidden="true" />;
}

export function PageSkeleton() {
  const t = useT();
  return (
    <div className="page" aria-busy="true">
      <span className="sr-only" role="status">
        {t.common.loading}
      </span>
      <Skeleton h={34} w="40%" />
      <Skeleton h={16} w="65%" />
      <div className="grid-3">
        <Skeleton h={150} r={14} />
        <Skeleton h={150} r={14} />
        <Skeleton h={150} r={14} />
      </div>
      <Skeleton h={260} r={14} />
    </div>
  );
}

export function EmptyState({
  icon: Icon = CircleDashed,
  title,
  children,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={26} aria-hidden="true" />
      </div>
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const t = useT();
  let message = error instanceof Error ? error.message : String(error);
  if (error instanceof ApiError) {
    if (error.status === 0) message = t.common.network;
    if (error.status === 401) message = t.common.unauthorized;
  }
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <div className="card">
      <EmptyState
        icon={AlertTriangle}
        title={notFound ? t.common.notFound : t.common.errorTitle}
        action={
          onRetry && !notFound ? (
            <button className="btn" onClick={onRetry}>
              {t.common.retry}
            </button>
          ) : undefined
        }
      >
        {message}
      </EmptyState>
    </div>
  );
}

// ------------------------------------------------------------------ semantic chips

export function BandChip({ band }: { band: EvidenceBand | null }) {
  const t = useT();
  if (!band) return <span className="chip chip-neutral">{t.band.pending}</span>;
  const tone = band === "strong" ? "chip-ok" : band === "moderate" ? "chip-accent" : "chip-neutral";
  return (
    <span className={cx("chip chip-dot", tone)} title={t.band.hint}>
      <span>{t.band[band]}</span>
    </span>
  );
}

export function StatusChip({ status }: { status: CriterionStatus }) {
  const t = useT();
  const tone = status === "demonstrated" ? "chip-ok" : status === "partial" ? "chip-warn" : "chip-neutral";
  return (
    <span
      className={cx("chip chip-dot", tone)}
      title={status === "not_evidenced" ? t.critHint.not_evidenced : undefined}
    >
      <span>{t.crit[status]}</span>
    </span>
  );
}

export function ImportanceChip({ importance }: { importance: Importance }) {
  const t = useT();
  const tone = importance === "essential" ? "chip-accent" : importance === "important" ? "chip-violet" : "chip-plain";
  return <span className={cx("chip", tone)}>{t.importance[importance]}</span>;
}

export function DecisionChip({ decision }: { decision: DecisionKind | null }) {
  const t = useT();
  if (!decision) return <span className="chip chip-plain">{t.decision.none}</span>;
  const tone =
    decision === "shortlist" || decision === "interview" ? "chip-violet" : decision === "hold" ? "chip-warn" : "chip-neutral";
  return (
    <span className={cx("chip", tone)}>
      <Handshake size={12} aria-hidden="true" />
      <span>{t.decision[decision]}</span>
    </span>
  );
}

export function EscalatedChip() {
  const t = useT();
  return (
    <span className="chip chip-violet">
      <Bot size={12} aria-hidden="true" />
      <span>{t.pipeline.escalated}</span>
    </span>
  );
}

const FAMILY_ICONS: Record<Family, LucideIcon> = {
  software: Code2,
  data: Database,
  design: Palette,
  marketing: Megaphone,
  sales: Handshake,
  craft: Hammer,
  culinary: ChefHat,
  textile: Scissors,
  management: Users,
  transversal: Shapes,
};

export function FamilyIcon({ family, size = 20 }: { family: Family; size?: number }) {
  const Icon = FAMILY_ICONS[family] ?? BriefcaseBusiness;
  return (
    <span className="family-icon">
      <Icon size={size} aria-hidden="true" />
    </span>
  );
}

/**
 * Permission gate for an action: renders children with `allowed`; when the role lacks the permission,
 * wraps them in a span whose tooltip (and screen-reader text) says which roles may do it.
 */
export function Gate({ perm, children }: { perm: Permission; children: (allowed: boolean) => ReactNode }) {
  const access = useAccess();
  const hint = access.denied(perm);
  if (!hint) return <>{children(true)}</>;
  return (
    <span className="gate" title={hint}>
      {children(false)}
      <span className="sr-only">{hint}</span>
    </span>
  );
}

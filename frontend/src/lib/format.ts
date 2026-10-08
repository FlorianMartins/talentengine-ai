import type { Lang } from "../i18n";

export const LEVEL_THRESHOLDS = [0, 1, 1.75, 2.5, 3.25] as const;

/** Same thresholds as the backend `_level_label`: 0 Emerging … 3.25+ Expert. */
export function levelIndex(level: number): number {
  let idx = 0;
  LEVEL_THRESHOLDS.forEach((t, i) => {
    if (level >= t) idx = i;
  });
  return idx;
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)} %`.replace(" ", " ");
}

export function num(value: number, lang: Lang, digits = 2): string {
  return new Intl.NumberFormat(lang === "fr" ? "fr-FR" : "en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(value);
}

export function usd(value: number, lang: Lang): string {
  return new Intl.NumberFormat(lang === "fr" ? "fr-FR" : "en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value < 1 ? 4 : 2,
  }).format(value);
}

export function dateTime(iso: string | undefined, lang: Lang): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(lang === "fr" ? "fr-FR" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

export function shortHash(hash: string | undefined, n = 10): string {
  if (!hash) return "—";
  return hash.length > n ? `${hash.slice(0, n)}…` : hash;
}

export function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

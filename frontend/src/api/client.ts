// Minimal typed fetch client. All URLs are relative (`/api/...`): Vite proxies them
// in development and the FastAPI backend serves the built app in production.
import type {
  Artifact,
  CandidateSummary,
  CatalogSkill,
  ChainVerification,
  DashboardReport,
  EraseResult,
  EvaluationRun,
  Explanation,
  Family,
  Health,
  HumanDecision,
  JobListItem,
  JobProfile,
  JobUsage,
  LedgerEntry,
  LedgerQuery,
  Locale,
  Preset,
  RevealResult,
  Runtime,
  SeedResult,
  SkillGraph,
  SubmissionInput,
  SubmissionResult,
} from "./types";
import { getStored } from "../lib/storage";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

/** FastAPI returns `{"detail": "..."}` or `{"detail": [{loc, msg}, ...]}`. */
function describeDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((d) => {
        const where = (d.loc ?? []).filter((p) => p !== "body").join(".");
        return where ? `${where}: ${d.msg ?? ""}` : d.msg ?? "";
      })
      .join(" · ");
  }
  return JSON.stringify(detail);
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { Accept: "application/json", ...extra };
  const key = getStored("apiKey");
  if (key) h["X-API-Key"] = key;
  const actor = getStored("reviewer").trim();
  // HTTP header values must be ISO-8859-1: drop anything else rather than failing the call.
  // eslint-disable-next-line no-control-regex
  const safeActor = actor.replace(/[^\x20-\x7E -ÿ]/g, "");
  if (safeActor) h["X-Actor"] = safeActor;
  return h;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { ...headers(), ...(init.headers as Record<string, string>) } });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body && body.detail !== undefined) message = describeDetail(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" },
});

const enc = encodeURIComponent;

export const api = {
  health: () => request<Health>("/api/health"),
  runtime: () => request<Runtime>("/api/runtime"),

  skills: (locale: Locale) => request<CatalogSkill[]>(`/api/catalog/skills?locale=${locale}`),
  families: () => request<Family[]>("/api/catalog/families"),
  presets: (locale: Locale) => request<Preset[]>(`/api/catalog/presets?locale=${locale}`),

  jobs: () => request<JobListItem[]>("/api/jobs"),
  job: (id: string) => request<JobProfile>(`/api/jobs/${enc(id)}`),
  createJob: (job: JobProfile) => request<JobProfile>("/api/jobs", json(job)),
  updateJob: (id: string, job: JobProfile) =>
    request<JobProfile>(`/api/jobs/${enc(id)}`, { ...json(job), method: "PUT" }),
  candidates: (id: string) => request<CandidateSummary[]>(`/api/jobs/${enc(id)}/candidates`),
  evaluate: (id: string) => request<EvaluationRun>(`/api/jobs/${enc(id)}/evaluate`, { method: "POST" }),
  usage: (id: string) => request<JobUsage>(`/api/jobs/${enc(id)}/usage`),

  submit: (jobId: string, s: SubmissionInput) => {
    const fd = new FormData();
    fd.set("consent", String(s.consent));
    fd.set("identity_name", s.identity_name);
    fd.set("identity_email", s.identity_email);
    fd.set("github_urls", s.github_urls.join("\n"));
    fd.set("portfolio_json", JSON.stringify(s.portfolio));
    fd.set("image_captions_json", JSON.stringify(s.images.map((i) => i.caption)));
    fd.set("retention_days", String(s.retention_days));
    if (s.cv) fd.set("cv", s.cv);
    for (const d of s.documents) fd.append("documents", d);
    for (const i of s.images) fd.append("images", i.file);
    return request<SubmissionResult>(`/api/jobs/${enc(jobId)}/candidates`, { method: "POST", body: fd });
  },

  report: (ref: string) => request<DashboardReport>(`/api/candidates/${enc(ref)}/report`),
  graph: (ref: string) => request<SkillGraph>(`/api/candidates/${enc(ref)}/graph`),
  artifacts: (ref: string) => request<Artifact[]>(`/api/candidates/${enc(ref)}/artifacts`),
  explanation: (ref: string) => request<Explanation>(`/api/candidates/${enc(ref)}/explanation`),
  /** Media needs the API key header, so it is fetched as a blob (not an <img src>). */
  media: async (ref: string, artifactId: string): Promise<string | null> => {
    const res = await fetch(`/api/candidates/${enc(ref)}/media/${enc(artifactId)}`, { headers: headers() });
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  },
  decide: (ref: string, d: HumanDecision) =>
    request<DashboardReport>(`/api/candidates/${enc(ref)}/decisions`, json(d)),
  reveal: (ref: string, reviewer: string, reason: string) =>
    request<RevealResult>(`/api/candidates/${enc(ref)}/reveal`, json({ reviewer, reason })),
  erase: (ref: string, actor: string) => request<EraseResult>(`/api/candidates/${enc(ref)}/erase`, json({ actor })),

  ledger: (q: LedgerQuery = {}) => {
    const p = new URLSearchParams();
    if (q.limit !== undefined) p.set("limit", String(q.limit));
    if (q.offset !== undefined) p.set("offset", String(q.offset));
    if (q.candidate_ref) p.set("candidate_ref", q.candidate_ref);
    if (q.job_id) p.set("job_id", q.job_id);
    return request<LedgerEntry[]>(`/api/audit/ledger?${p.toString()}`);
  },
  verify: () => request<ChainVerification>("/api/audit/verify"),
  seed: () => request<SeedResult>("/api/demo/seed", { method: "POST" }),
};

// Minimal typed fetch client. Every URL is `${API}/...` (base path + /api): Vite proxies them
// in development and the FastAPI backend serves the built app in production.
import type {
  Artifact,
  CandidateSummary,
  CatalogSkill,
  AssessAnswerResult,
  AssessCatalog,
  AssessEvent,
  AssessFinish,
  AssessLevel,
  AssessmentLink,
  AssessQuestion,
  AssessStart,
  AssessState,
  CandidateAssessment,
  ChainVerification,
  ExplanationLinkRow,
  IncidentResult,
  IncidentSeverity,
  Integration,
  IntegrationInput,
  Monitoring,
  NewAssessment,
  CreatedUser,
  ExplanationLink,
  Me,
  PublicExplanation,
  RetentionRun,
  Role,
  UserAccount,
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
  OfferAnalysis,
  Preset,
  RevealResult,
  Runtime,
  SeedResult,
  SkillGraph,
  SubmissionInput,
  SubmissionResult,
  TryConfig,
  TryMatchInput,
  TryMatchResult,
} from "./types";
import { getStored } from "../lib/storage";

/** App base path ("" at the root, "/talentengine" when served under a prefix). */
export const BASE_PATH = import.meta.env.BASE_URL.replace(/\/$/, "");
/** Root of every API call, prefixed with the base path. */
export const API = `${BASE_PATH}/api`;

export class ApiError extends Error {
  readonly status: number;
  /** on 403: the permission the role lacks (X-Required-Permission header) */
  readonly permission: string;
  constructor(status: number, message: string, permission = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.permission = permission;
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

async function errorFrom(res: Response): Promise<ApiError> {
  let message = `${res.status} ${res.statusText}`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (body && body.detail !== undefined) message = describeDetail(body.detail);
  } catch {
    /* not JSON */
  }
  return new ApiError(res.status, message, res.headers.get("X-Required-Permission") ?? "");
}

/** Fetches an attachment with the auth headers and saves it through a Blob link. */
async function download(path: string, filename: string, mime?: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(path, { headers: headers() });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!res.ok) throw await errorFrom(res);
  const blob = await res.blob();
  const typed = mime ? new Blob([blob], { type: mime }) : blob;
  const url = URL.createObjectURL(typed);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { ...headers(), ...(init.headers as Record<string, string>) } });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!res.ok) throw await errorFrom(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
  headers: { "Content-Type": "application/json" },
});

const enc = encodeURIComponent;

// ------------------------------------------------------------------ verification tests (public, token-addressed)

declare global {
  interface Window {
    SafeExamBrowser?: { security?: { configKey?: string; updateKeys?: (cb: () => void) => void } };
  }
}

/** Safe Exam Browser 3.x JavaScript API: page URL + config key hash, sent on every /api/assess call. */
async function sebHeaders(): Promise<Record<string, string>> {
  const seb = window.SafeExamBrowser?.security;
  if (!seb) return {};
  if (seb.updateKeys) await new Promise<void>((resolve) => seb.updateKeys?.(() => resolve()));
  return seb.configKey ? { "X-SEB-Page-Url": window.location.href, "X-SEB-Config-Key-Hash": seb.configKey } : {};
}

async function assessRequest<T>(token: string, path: string, body?: unknown): Promise<T> {
  const h = await sebHeaders();
  return request<T>(`${API}/assess/${enc(token)}${path}`, body === undefined && path === "" ? { headers: h } : { ...json(body ?? {}), headers: { "Content-Type": "application/json", ...h } });
}

export const assess = {
  catalog: (locale: Locale) => request<AssessCatalog>(`${API}/assess/catalog?locale=${locale}`),
  start: (body: { preset_id?: string; job?: JobProfile; level: AssessLevel; locale: Locale; questions: number; seed?: string }) =>
    request<AssessStart>(`${API}/assess/start`, json(body)),
  state: (token: string) => assessRequest<AssessState>(token, ""),
  next: (token: string) => assessRequest<AssessQuestion>(token, "/next", {}),
  answer: (token: string, index: number, value: unknown) => assessRequest<AssessAnswerResult>(token, "/answer", { index, value }),
  timeout: (token: string, index: number) => assessRequest<{ next: number; total: number }>(token, "/timeout", { index }),
  events: (token: string, events: AssessEvent[]) => assessRequest<{ accepted: number }>(token, "/events", { events }),
  /** best effort on page hide: sendBeacon cannot carry SEB headers, so only used outside SEB */
  beacon: (token: string, events: AssessEvent[]): boolean => {
    if (!navigator.sendBeacon || window.SafeExamBrowser) return false;
    return navigator.sendBeacon(`${API}/assess/${enc(token)}/events`, new Blob([JSON.stringify({ events })], { type: "application/json" }));
  },
  finish: (token: string) => assessRequest<AssessFinish>(token, "/finish", {}),
};

export const api = {
  health: () => request<Health>(`${API}/health`),
  runtime: () => request<Runtime>(`${API}/runtime`),

  skills: (locale: Locale) => request<CatalogSkill[]>(`${API}/catalog/skills?locale=${locale}`),
  families: () => request<Family[]>(`${API}/catalog/families`),
  presets: (locale: Locale) => request<Preset[]>(`${API}/catalog/presets?locale=${locale}`),

  jobs: () => request<JobListItem[]>(`${API}/jobs`),
  job: (id: string) => request<JobProfile>(`${API}/jobs/${enc(id)}`),
  createJob: (job: JobProfile) => request<JobProfile>(`${API}/jobs`, json(job)),
  updateJob: (id: string, job: JobProfile) =>
    request<JobProfile>(`${API}/jobs/${enc(id)}`, { ...json(job), method: "PUT" }),
  candidates: (id: string) => request<CandidateSummary[]>(`${API}/jobs/${enc(id)}/candidates`),
  evaluate: (id: string) => request<EvaluationRun>(`${API}/jobs/${enc(id)}/evaluate`, { method: "POST" }),
  usage: (id: string) => request<JobUsage>(`${API}/jobs/${enc(id)}/usage`),

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
    if (s.linkedin) fd.set("linkedin", s.linkedin);
    for (const d of s.degrees) fd.append("degrees", d);
    for (const d of s.certifications) fd.append("certifications", d);
    for (const d of s.documents) fd.append("documents", d);
    for (const i of s.images) fd.append("images", i.file);
    return request<SubmissionResult>(`${API}/jobs/${enc(jobId)}/candidates`, { method: "POST", body: fd });
  },

  report: (ref: string) => request<DashboardReport>(`${API}/candidates/${enc(ref)}/report`),
  graph: (ref: string) => request<SkillGraph>(`${API}/candidates/${enc(ref)}/graph`),
  artifacts: (ref: string) => request<Artifact[]>(`${API}/candidates/${enc(ref)}/artifacts`),
  explanation: (ref: string) => request<Explanation>(`${API}/candidates/${enc(ref)}/explanation`),
  /** Media needs the API key header, so it is fetched as a blob (not an <img src>). */
  media: async (ref: string, artifactId: string): Promise<string | null> => {
    const res = await fetch(`${API}/candidates/${enc(ref)}/media/${enc(artifactId)}`, { headers: headers() });
    if (!res.ok) return null;
    return URL.createObjectURL(await res.blob());
  },
  decide: (ref: string, d: HumanDecision) =>
    request<DashboardReport>(`${API}/candidates/${enc(ref)}/decisions`, json(d)),
  /** `reviewer` is ignored by the server for named accounts (the account name signs the action). */
  reveal: (ref: string, reviewer: string, reason: string) =>
    request<RevealResult>(`${API}/candidates/${enc(ref)}/reveal`, json({ reviewer, reason })),
  /** `actor` is ignored by the server for named accounts. */
  erase: (ref: string, actor: string) => request<EraseResult>(`${API}/candidates/${enc(ref)}/erase`, json({ actor })),
  explanationLink: (ref: string, days = 30) =>
    request<ExplanationLink>(`${API}/candidates/${enc(ref)}/explanation-link?days=${days}`, { method: "POST" }),
  exportCandidate: (ref: string) => download(`${API}/candidates/${enc(ref)}/export`, `export-${ref}.json`, "application/json"),
  dpia: (jobId: string, locale: Locale) =>
    download(`${API}/jobs/${enc(jobId)}/dpia?locale=${locale}`, `${locale === "fr" ? "aipd" : "dpia"}-${jobId}.md`, "text/markdown"),

  ledger: (q: LedgerQuery = {}) => {
    const p = new URLSearchParams();
    if (q.limit !== undefined) p.set("limit", String(q.limit));
    if (q.offset !== undefined) p.set("offset", String(q.offset));
    if (q.candidate_ref) p.set("candidate_ref", q.candidate_ref);
    if (q.job_id) p.set("job_id", q.job_id);
    return request<LedgerEntry[]>(`${API}/audit/ledger?${p.toString()}`);
  },
  verify: () => request<ChainVerification>(`${API}/audit/verify`),
  // public sandbox — no API key needed, nothing stored server-side
  tryConfig: (locale: Locale) => request<TryConfig>(`${API}/try/config?locale=${locale}`),
  tryOffer: (body: { text?: string; url?: string; locale: Locale }) => request<OfferAnalysis>(`${API}/try/offer`, json(body)),
  tryMatch: (m: TryMatchInput) => {
    const fd = new FormData();
    fd.set("consent", String(m.consent));
    fd.set("identity_name", m.identity_name);
    fd.set("locale", m.locale);
    if (m.job) fd.set("job_json", JSON.stringify(m.job));
    if (m.preset_id) fd.set("preset_id", m.preset_id);
    fd.set("github_urls", m.github_urls.join("\n"));
    fd.set("portfolio_urls", m.portfolio_urls.join("\n"));
    if (m.cv) fd.set("cv", m.cv);
    if (m.linkedin) fd.set("linkedin", m.linkedin);
    for (const d of m.degrees) fd.append("degrees", d);
    for (const d of m.certifications) fd.append("certifications", d);
    for (const d of m.documents) fd.append("documents", d);
    return request<TryMatchResult>(`${API}/try/match`, { method: "POST", body: fd });
  },
  // verification tests, explanation links, compliance, ATS (v0.5)
  candidateAssessments: (ref: string) => request<CandidateAssessment[]>(`${API}/candidates/${enc(ref)}/assessments`),
  createAssessment: (ref: string, body: NewAssessment) =>
    request<AssessmentLink>(`${API}/candidates/${enc(ref)}/assessments`, json(body)),
  explanationLinks: (ref: string) => request<ExplanationLinkRow[]>(`${API}/candidates/${enc(ref)}/explanation-links`),
  revokeExplanationLink: (ref: string, id: string) =>
    request<{ revoked: boolean }>(`${API}/candidates/${enc(ref)}/explanation-links/${enc(id)}`, { method: "DELETE" }),
  monitoring: () => request<Monitoring>(`${API}/admin/monitoring`),
  incident: (body: { severity: IncidentSeverity; description: string; affected_candidates: string[] }) =>
    request<IncidentResult>(`${API}/admin/incidents`, json(body)),
  integrations: () => request<Integration[]>(`${API}/integrations`),
  createIntegration: (body: IntegrationInput) => request<Integration>(`${API}/integrations`, json(body)),
  deleteIntegration: (id: string) => request<unknown>(`${API}/integrations/${enc(id)}`, { method: "DELETE" }),

  // accounts & privacy administration (v0.4)
  me: () => request<Me>(`${API}/me`),
  users: () => request<UserAccount[]>(`${API}/admin/users`),
  createUser: (name: string, role: Role) => request<CreatedUser>(`${API}/admin/users`, json({ name, role })),
  deleteUser: (name: string) => request<unknown>(`${API}/admin/users/${enc(name)}`, { method: "DELETE" }),
  retentionRun: () => request<RetentionRun>(`${API}/admin/retention/run`, { method: "POST" }),
  /** public, no key: what a candidate sees through an explanation link */
  publicExplanation: (token: string) => request<PublicExplanation>(`${API}/public/explanation/${enc(token)}`),
  seed: () => request<SeedResult>(`${API}/demo/seed`, { method: "POST" }),
};

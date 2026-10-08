// Types mirroring the FastAPI contract (openapi.json + observed responses).
// Keep these in sync with backend/talentengine/models.py.

export type Locale = "fr" | "en";

export type Family =
  | "software"
  | "data"
  | "design"
  | "marketing"
  | "sales"
  | "craft"
  | "culinary"
  | "textile"
  | "management"
  | "transversal";

export const FAMILIES: readonly Family[] = [
  "software",
  "data",
  "design",
  "marketing",
  "sales",
  "craft",
  "culinary",
  "textile",
  "management",
  "transversal",
];

export type Importance = "essential" | "important" | "bonus";
export type EvidenceBand = "strong" | "moderate" | "limited";
export type CriterionStatus = "demonstrated" | "partial" | "not_evidenced";
export type DecisionKind = "shortlist" | "interview" | "hold" | "not_retained";
export type AssessmentSource = "heuristic" | "llm";
export type ArtifactKind =
  | "cv"
  | "linkedin"
  | "degree"
  | "certification"
  | "document"
  | "image"
  | "repository"
  | "portfolio_note";
export type ArtifactStatus = "ready" | "quarantined";
export type LedgerKind =
  | "job_config"
  | "ingestion"
  | "score"
  | "escalation"
  | "human_decision"
  | "reidentification"
  | "erasure"
  | "data_export"
  | "explanation_link"
  | "explanation_viewed"
  | "retention_sweep"
  | "account_created"
  | "account_removed";

// ------------------------------------------------------------------ runtime / catalog

export interface Runtime {
  version: string;
  vision_detector: string;
  llm_provider: string;
  llm_model: string;
  max_credential_weight: number;
  demo_enabled: boolean;
  auth_required: boolean;
  /** personal accounts (te_… keys) are configured */
  named_accounts?: boolean;
  /** recruiter upload limits (v0.5) */
  upload_limits?: { max_file_mb: number; max_files_total: number };
}

export interface Health {
  status: string;
  version: string;
  auth_required: boolean;
  demo_enabled: boolean;
}

export interface CatalogSkill {
  id: string;
  family: Family;
  label: string;
  statement: string;
}

export interface Preset {
  id: string;
  family: Family;
  title: string;
  summary: string;
  /** FR + EN synonyms used by the preset search */
  keywords?: string;
  job: JobProfile;
}

// ------------------------------------------------------------------ job profile

export interface AxisWeights {
  autonomy: number;
  complexity: number;
  reliability: number;
}

export type AxisScores = AxisWeights;
export type Axis = keyof AxisWeights;
export const AXES: readonly Axis[] = ["autonomy", "complexity", "reliability"];

export interface Criterion {
  skill_id: string;
  importance: Importance;
  weight: number;
  min_level: number;
  axis_focus: AxisWeights | null;
  note: string;
}

export interface CredentialsPolicy {
  mode: "ignore" | "secondary";
  weight: number;
  accepted: string[];
}

export interface FunnelSettings {
  allow_cloud_llm: boolean;
  escalation_top_percent: number;
  min_density_for_escalation: number;
  max_input_tokens_per_candidate: number;
  max_output_tokens_per_candidate: number;
  job_budget_usd: number;
}

export interface PrivacySettings {
  neutralize_gendered_terms: boolean;
  mask_school_names: boolean;
  quarantine_images_without_detector: boolean;
}

export interface JobProfile {
  id: string;
  title: string;
  summary: string;
  family: Family;
  locale: Locale;
  criteria: Criterion[];
  axis_weights: AxisWeights;
  credentials: CredentialsPolicy;
  funnel: FunnelSettings;
  privacy: PrivacySettings;
  version: number;
  created_at?: string;
  updated_at?: string;
}

/** `GET /api/jobs` — each profile plus pipeline counters. */
export interface JobListItem extends JobProfile {
  candidates: number;
  evaluated: number;
  best_pct: number | null;
  decisions: number;
}

export interface EvaluationRun {
  job_id: string;
  evaluated: number;
  /** candidate refs deepened by the cloud LLM */
  escalated: string[];
  /** candidate ref → reason the AI deepening was skipped (the candidate itself IS evaluated) */
  escalation_skipped: Record<string, string>;
  spent_usd: number;
}

export interface JobUsage {
  job_id: string;
  budget_usd: number;
  usd: number;
  input_tokens: number;
  output_tokens: number;
  calls: number;
  provider: string;
  model: string;
}

// ------------------------------------------------------------------ candidates

export interface CandidateSummary {
  candidate_ref: string;
  compatibility_pct: number | null;
  confidence: number | null;
  evidence_band: EvidenceBand | null;
  top_skills: string[];
  evidence_count: number;
  artifacts: number;
  escalated: boolean;
  warnings: number;
  decision: DecisionKind | null;
  created_at: string;
}

export interface SubmissionResult {
  candidate_ref: string;
  artifacts: string[];
}

export interface EvidenceRef {
  artifact_id: string;
  artifact_label: string;
  locator: string;
  excerpt?: string;
  line_start: number | null;
  line_end: number | null;
}

export interface CriterionResult {
  skill_id: string;
  label: string;
  importance: Importance;
  required_level: number;
  observed_level: number;
  match: number;
  status: CriterionStatus;
  evidence_count: number;
  recruiter_note: string;
}

export interface ValidatedSkill {
  skill_id: string;
  label: string;
  statement: string;
  level: number;
  level_label: string;
  axes: AxisScores;
  confidence: number;
  evidence: EvidenceRef[];
  source: AssessmentSource;
}

export interface Gap {
  skill_id: string;
  label: string;
  importance: Importance;
  suggestion: string;
  declared_by_candidate: boolean;
}

export interface InterviewQuestion {
  skill_id: string;
  question: string;
  purpose: string;
  expected_key_points: string[];
  warning_signs: string[];
  evidence: EvidenceRef;
}

export interface CredentialItem {
  kind: "degree" | "certification";
  label: string;
  evidence: EvidenceRef;
  /** a diploma/certificate file was uploaded in that category ("justificatif fourni") */
  supported_by_document?: boolean;
}

export interface CredentialsSummary {
  items: CredentialItem[];
  matched_accepted: string[];
  weight_applied: number;
  component_pct: number;
}

export interface EscalationRecord {
  escalated: boolean;
  reason: string;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface AuditInfo {
  ledger_entry_id: string;
  entry_hash: string;
  engine_version: string;
  job_config_version: number;
  escalation: EscalationRecord;
  signals_used: number;
}

export interface HumanDecision {
  decision: DecisionKind;
  reviewer: string;
  rationale: string;
  decided_at?: string;
  ledger_entry_id?: string;
}

export interface DashboardReport {
  candidate_ref: string;
  job_id: string;
  job_title: string;
  locale: Locale;
  generated_at?: string;
  compatibility_pct: number;
  skills_component_pct: number;
  credentials_component_pct: number;
  confidence: number;
  evidence_band: EvidenceBand;
  criteria: CriterionResult[];
  validated_skills: ValidatedSkill[];
  gaps: Gap[];
  interview_guide: InterviewQuestion[];
  credentials: CredentialsSummary;
  warnings: string[];
  audit: AuditInfo;
  decision: HumanDecision | null;
  notice: string;
}

export interface SkillAssessment {
  skill_id: string;
  /** localised label (backend ≥ 0.2) */
  label?: string;
  axes: AxisScores;
  confidence: number;
  rationale: string;
  evidence: EvidenceRef[];
  source: AssessmentSource;
}

export interface SkillEdge {
  source: string;
  target: string;
  shared_artifacts: string[];
}

export interface SkillGraph {
  candidate_ref: string;
  assessments: SkillAssessment[];
  edges: SkillEdge[];
  declared_only: string[];
}

export interface RedactionReport {
  pii_replaced: Record<string, number>;
  gendered_terms_neutralised: number;
  visual_regions_masked: number;
  metadata_removed: string[];
  detector: string;
  injection_suspected: boolean;
  injection_excerpts: string[];
  notes: string[];
}

export interface Artifact {
  id: string;
  candidate_ref: string;
  kind: ArtifactKind;
  label: string;
  status: ArtifactStatus;
  content_sha256: string;
  text: string;
  repo_paths: string[];
  media_type: string;
  redaction: RedactionReport;
}

// ------------------------------------------------------------------ audit

export interface LedgerEntry {
  seq: number;
  entry_id: string;
  kind: LedgerKind | string;
  actor: string;
  job_id: string | null;
  candidate_ref: string | null;
  created_at: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
  seal: string;
}

export interface ChainVerification {
  valid: boolean;
  length: number;
  head_hash: string;
  first_invalid_seq: number | null;
  reason: string;
}

export interface Explanation {
  candidate_ref: string;
  job_id: string;
  report: DashboardReport | null;
  ledger: LedgerEntry[];
  chain: ChainVerification;
}

export interface RevealResult {
  candidate_ref: string;
  identity: Record<string, string[]>;
}

export interface EraseResult {
  vault_entries_shredded: number;
  artifacts_deleted: number;
}

export interface SeedResult {
  jobs: Record<string, { title: string; candidates: string[]; escalated: string[] }>;
}

export interface LedgerQuery {
  limit?: number;
  offset?: number;
  candidate_ref?: string;
  job_id?: string;
}

export interface SubmissionInput {
  consent: boolean;
  identity_name: string;
  identity_email: string;
  github_urls: string[];
  portfolio: { title: string; description: string }[];
  retention_days: number;
  cv: File | null;
  /** LinkedIn profile saved as PDF (self-description, like the CV) */
  linkedin: File | null;
  degrees: File[];
  certifications: File[];
  documents: File[];
  images: { file: File; caption: string }[];
}

// ------------------------------------------------------------------ public sandbox (/api/try/*, no key)

export interface TryPreset {
  id: string;
  family: Family;
  title: string;
  summary: string;
  /** FR + EN synonyms used by the preset search */
  keywords?: string;
  /** criterion labels, already localised */
  criteria: string[];
}

export interface TryLimits {
  matches_per_hour: number;
  max_repos: number;
  max_links: number;
  max_documents: number;
  max_file_mb: number;
}

export interface TrySkill {
  id: string;
  label: string;
  family: Family;
}

export interface TryConfig {
  enabled: boolean;
  presets: TryPreset[];
  limits: TryLimits;
  skills: TrySkill[];
}

export interface OfferTrace {
  skill_id: string;
  label: string;
  importance: Importance;
  mentions: number;
  /** lines of the offer that mention the skill */
  lines: string[];
}

export interface OfferAnalysis {
  /** "text" or the host the offer was read from (e.g. www.linkedin.com) */
  source: string;
  job: JobProfile;
  traces: OfferTrace[];
  warnings: string[];
}

export interface TryArtifact {
  label: string;
  kind: ArtifactKind;
  status: ArtifactStatus;
  /** personal data items masked */
  masked: number;
  injection_suspected: boolean;
  /** repository: number of files read */
  files: number;
}

export interface TryGraphAssessment extends SkillAssessment {
  label: string;
}


export interface TryMatchResult {
  report: DashboardReport;
  graph: { assessments: TryGraphAssessment[]; edges: SkillEdge[] };
  artifacts: TryArtifact[];
  tips: string[];
  /** the job profile actually used (preset or edited offer) */
  job?: JobProfile;
  /** pass to POST /api/assess/start to add questions about the visitor's own work (kept 1 h server-side) */
  assessment_seed?: string;
  stored: false;
}

export interface TryMatchInput {
  consent: boolean;
  identity_name: string;
  locale: Locale;
  job?: JobProfile;
  preset_id?: string;
  github_urls: string[];
  portfolio_urls: string[];
  cv: File | null;
  linkedin: File | null;
  degrees: File[];
  certifications: File[];
  documents: File[];
}

// ------------------------------------------------------------------ accounts & roles (v0.4)

export type Role = "recruiter" | "dpo" | "admin";
export const ROLES: readonly Role[] = ["recruiter", "dpo", "admin"];
export type Permission = "read" | "write" | "decide" | "privacy" | "admin";

/** `GET /api/me` */
export interface Me {
  name: string;
  role: Role;
  /** false in open development mode (no key, no account configured) */
  authenticated: boolean;
  /** true when the legacy shared TE_API_KEY was used (acts as admin, name comes from X-Actor) */
  shared_key: boolean;
  permissions: Permission[];
}

export interface UserAccount {
  name: string;
  role: Role;
  created_at: string;
}

/** `POST /api/admin/users` — the key is returned once, only its hash is kept. */
export interface CreatedUser {
  name: string;
  role: Role;
  api_key: string;
  notice: string;
}

export interface RetentionRun {
  erased: string[];
  count: number;
}

export interface ExplanationLink {
  token: string;
  /** app-relative path, e.g. "/explication/<token>" (prefix with the base path) */
  path: string;
  expires_at: string;
}

/** `GET /api/public/explanation/{token}` — what the candidate sees (no identifiers). */
export interface PublicExplanation {
  job_title: string;
  locale: Locale;
  generated_at: string;
  compatibility_pct: number;
  skills_component_pct: number;
  credentials_component_pct: number;
  credentials_weight: number;
  evidence_band: EvidenceBand;
  criteria: CriterionResult[];
  validated_skills: ValidatedSkill[];
  gaps: Gap[];
  credentials: CredentialItem[];
  decision: { decision: DecisionKind; rationale?: string; decided_at?: string; reviewer?: string } | null;
  notice: string;
  audit: {
    score_entry_hash: string;
    recorded_at: string;
    ledger_intact: boolean;
    engine_version: string;
    job_config_version: number;
  };
  expires_at: string;
}

// ------------------------------------------------------------------ verification tests (v0.5)

export type AssessLevel = 1 | 2 | 3;
export type AssessStatus = "ready" | "running" | "finished" | "expired";
export type QuestionType = "single" | "multi" | "numeric" | "order";
export type IntegrityRisk = "low" | "medium" | "high";

/** `GET /api/assess/{token}` */
export interface AssessState {
  status: AssessStatus;
  mode: "sandbox" | "candidate";
  locale: Locale;
  level: AssessLevel;
  job_title: string;
  total: number;
  /** index of the next question to serve */
  current: number;
  /** "CAND-XXXX · 08/10 21:27" — drawn over the questions */
  watermark: string;
  seb_required: boolean;
  expires_at: string;
  skills: string[];
  personal_questions: number;
  total_seconds: number;
}

/** `POST /api/assess/{token}/next` — no answer key ever reaches the browser. */
export interface AssessQuestion {
  index: number;
  type: QuestionType;
  stem: string;
  options: string[];
  unit: string;
  seconds: number;
  /** server-side remaining seconds (reloading never resets the clock) */
  remaining: number;
  /** a question about the candidate's own work */
  personal: boolean;
  skill: string;
  total: number;
}

export interface AssessAnswerResult {
  accepted: boolean;
  late: boolean;
  next: number;
  total: number;
}

export interface IntegritySummary {
  risk: IntegrityRisk;
  events: Record<string, number>;
  late_answers: number;
  too_fast_answers: number;
  notes: string[];
}

export interface AssessResults {
  overall_pct: number;
  level: AssessLevel;
  skills: {
    skill_id: string;
    label: string;
    score_pct: number;
    questions: number;
    answered_in_time: number;
    /** 0 none, 1 junior, 2 confirmed, 3 senior */
    verified_level: 0 | 1 | 2 | 3;
  }[];
  /** % on questions about the candidate's own work (null when none were asked) */
  authorship_pct: number | null;
  untestable_skills: string[];
  integrity: IntegritySummary;
  duration_seconds: number;
  questions: { index: number; skill: string; personal: boolean; score: number; late: boolean; too_fast: boolean; seconds?: number; seconds_used: number }[];
}

export interface AssessFinish {
  finished: boolean;
  mode: "sandbox" | "candidate";
  /** sandbox only: the candidate mode never shows results to the test taker */
  results?: AssessResults;
}

export interface AssessCatalog {
  levels: { value: AssessLevel; label: string }[];
  skills: { id: string; label: string; questions: Record<string, number> }[];
  total_questions: number;
}

export interface AssessStart extends AssessState {
  token: string;
  path: string;
}

export type AssessEventType =
  | "blur"
  | "focus"
  | "visibility_hidden"
  | "visibility_visible"
  | "paste_attempt"
  | "copy_attempt"
  | "cut_attempt"
  | "contextmenu"
  | "printscreen"
  | "fullscreen_exit"
  | "fullscreen_enter"
  | "drop_attempt"
  | "devtools"
  | "resize"
  | "multiple_screens"
  | "seb_missing";

export interface AssessEvent {
  type: AssessEventType;
  detail?: string;
}

/** `GET /api/candidates/{ref}/assessments` */
export interface CandidateAssessment {
  id: string;
  status: AssessStatus;
  level: AssessLevel;
  created_at: string;
  expires_at: string;
  seb_required: boolean;
  questions: number;
  results: AssessResults | null;
}

/** `POST /api/candidates/{ref}/assessments` */
export interface AssessmentLink {
  token: string;
  path: string;
  expires_at: string;
  questions: number;
  untestable_skills: string[];
}

export interface NewAssessment {
  level: AssessLevel;
  questions: number;
  personal: boolean;
  seb_config_keys: string[];
  valid_hours: number;
}

/** `GET /api/candidates/{ref}/explanation-links` */
export interface ExplanationLinkRow {
  id: string;
  created_at: string | null;
  created_by: string | null;
  expires_at: string;
  active: boolean;
  revoked?: boolean;
  revoked_at?: string | null;
  revoked_by?: string | null;
}

// ------------------------------------------------------------------ compliance & ATS (v0.5)

export interface Monitoring {
  generated_at: string;
  jobs: { job_id: string; title: string; candidates: number; decisions: number; score_min: number | null; score_max: number | null; score_median: number | null }[];
  evidence_bands: Partial<Record<EvidenceBand, number>>;
  human_decisions: number;
  /** decisions that did not follow the score ranking: evidence of real human oversight */
  decisions_departing_from_ranking: number;
  verification_tests_completed: number;
  test_integrity_risk: Partial<Record<IntegrityRisk, number>>;
  ai_spend_usd: number;
  incidents_recorded: number;
  ledger: ChainVerification;
}

export type IncidentSeverity = "serious" | "widespread" | "death";

export interface IncidentResult {
  entry_id: string;
  severity: IncidentSeverity;
  report_to_authority_before: string;
}

export type AtsProvider = "greenhouse" | "lever" | "ashby" | "generic";

export interface Integration {
  id: string;
  provider: AtsProvider;
  name: string;
  job_mapping: Record<string, string>;
  candidate_notice_confirmed: boolean;
  write_notes: boolean;
  explanation_link_days: number;
  created_at: string;
  created_by: string;
  webhook_path: string;
  /** returned once, at creation (generated for the generic provider) */
  webhook_secret?: string;
}

export interface IntegrationInput {
  provider: AtsProvider;
  name: string;
  job_mapping: Record<string, string>;
  secrets: Record<string, string>;
  candidate_notice_confirmed: boolean;
  write_notes: boolean;
  explanation_link_days: number;
}

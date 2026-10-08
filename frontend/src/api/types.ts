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
export type ArtifactKind = "cv" | "document" | "image" | "repository" | "portfolio_note";
export type ArtifactStatus = "ready" | "quarantined";
export type LedgerKind =
  | "job_config"
  | "ingestion"
  | "score"
  | "escalation"
  | "human_decision"
  | "reidentification"
  | "erasure";

// ------------------------------------------------------------------ runtime / catalog

export interface Runtime {
  version: string;
  vision_detector: string;
  llm_provider: string;
  llm_model: string;
  max_credential_weight: number;
  demo_enabled: boolean;
  auth_required: boolean;
}

export interface Health {
  status: string;
  version: string;
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
  documents: File[];
  images: { file: File; caption: string }[];
}

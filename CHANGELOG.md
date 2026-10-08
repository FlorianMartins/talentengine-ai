# Changelog

## 0.5.0 — 2026-10-08

Filtering impostors, real-world compliance, and an ATS add-on.

- **Verification tests**: 236 practical questions (37 skills × 3 levels, 53 with numbers drawn per
  candidate) plus questions generated from the candidate's own work (CI tools, cross-project links,
  libraries, folders, figures in their documents). Server-paced and timed, no going back, per-candidate
  variants, answers never sent to the browser, integrity journal (copy/paste, print-screen, focus, full
  screen, too-fast and late answers) reported as signals only. Optional Safe Exam Browser enforcement
  (config-key hash). Sandbox self-test and recruiter test links; results and ledger entries per candidate.
- **AI Act readiness**: verified timeline (Annex III obligations from 2 December 2027 under Regulation
  (EU) 2026/1744), provider vs deployer obligations, French labour law (L1221-6/8/9, L2312-38), instructions
  for use (Art. 13), Annex IV technical documentation, post-market monitoring endpoint, serious-incident
  journal with legal deadlines, candidate information notice.
- **ATS bridge**: Greenhouse (Harvest v3), Lever, Ashby and a generic signed webhook; applications are
  pulled, evaluated and annotated back in the ATS; encrypted credentials; SSRF-safe downloads.
- **Front end**: test player (`/test/:token`) with the anti-cheat layer (paste/copy/drop/devtools blocked and
  journalled, blur on focus loss, veil on capture shortcuts, moving watermark, print disabled, optional Safe
  Exam Browser), "prove it" test from the sandbox, verification panel in the recruiter report and PDF,
  Compliance page (DPO/admin), ATS integrations page (admin), candidate information notice on every form.
- Explanation links can be listed and revoked (revoked links stay listed with who and when); 403 responses carry `X-Required-Permission`; the decision
  reviewer field is optional for named accounts; upload limits in `/api/runtime`.
- All documentation in English.

## 0.4.0 — 2026-10-08

Named accounts, GDPR operations and candidate-facing explanations (roadmap phases 4 and 5).

- **Named accounts and roles** (`recruiter`, `dpo`, `admin`): personal keys stored as SHA-256 hashes,
  permission checks on every route, decisions / reveals / exports / erasures signed server-side with the
  authenticated name. CLI `adduser`, `users`, `deluser`; account management for admins.
- **Retention enforced**: applications are erased automatically when their consented retention period
  ends (sweep every `TE_RETENTION_SWEEP_HOURS`, also `talentengine purge`).
- **GDPR export** (Art. 15/20) of everything held about a candidate, logged.
- **Explanation links** (AI Act Art. 86): a private 30-day page for the candidate with the evidence,
  criteria, gaps, decision and rationale, and ledger integrity — no identifier; token stored as a hash,
  opening logged, link invalidated by erasure.
- **DPIA draft** per job, pre-filled from the live configuration (CNIL PIA structure + AI Act deployer
  duties), FR and EN.
- Print-to-PDF layouts for the report, the explanation page and the sandbox result.
- **Every public repository of a GitHub profile** (up to 30, parallel git partial clones) and **how they
  work together**: cross-repository dependencies, CI steps running another project, deployments,
  submodules, Terraform modules; pipeline orchestration (tools chained, job dependencies) and multi-service
  compose files; declared stack from dependency manifests. New skill *Systems integration &
  orchestration*. Repository names are blinded (`repo-n`) in every excerpt and document.
- **LinkedIn profile (PDF)** as a source: often fuller than a two-page CV; read as a self-description.
- **Diploma and certification files** as their own categories, marked "document provided" and merged
  with the same credential named elsewhere; up to 10 files per category in the sandbox.
- **47 reference roles** with FR/EN search keywords (accent-insensitive, whole-word for short words):
  "IA engineer" finds the AI engineer role. New skills *LLM & generative AI engineering* and *Mobile
  development* (37 skills in total).

## 0.3.0 — 2026-10-08

Public sandbox and recruiter documentation.

- **Public sandbox** (`/essai`, `/api/try`): paste a job offer (text, any job-board link with structured
  data, or a LinkedIn job link through its public view) or pick a reference role, add a CV, documents,
  GitHub profile or repositories and portfolio links, get the compatibility report and tips. Nothing is
  stored (in-memory engine, temporary directory deleted), per-IP rate limits, SSRF-safe fetching.
- **Offer parser**: skills, importance ("indispensable" / "un plus"), required level from years and
  seniority, credentials named in the offer; perks and company sections ignored; every criterion shows
  the offer lines behind it.
- GitHub trees read with `git` partial clones (names only) instead of the rate-limited REST API.
- New skill **Cloud infrastructure** (Azure, AWS, GCP…) in offers, CVs and repository trees.
- Vocabulary tightened after testing real offers: "mise en place", "carte", "fonds de", "significative"
  and "expérimentation" alone no longer count as cooking or A/B-testing evidence.
- Front-end can be served under a path prefix (`VITE_BASE`); public recruiter landing page.
- Recruiter guide (`docs/recruiters/`), deployment guide.

## 0.2.0 — 2026-10-08

Roadmap phases 1 and 2: the shield and the scoring are now *measured* (see `docs/MEASUREMENTS.md`).

- Masking: letters widened to all of Unicode and a new header heuristic (particles, separators,
  "SURNAME, Firstname", signatures, "Je m'appelle…") — the first measurement showed Polish and Vietnamese
  names leaked more than French ones. New rules for obfuscated e-mails, social handles, "né en 1990".
- **The declared name is now required** at submission: on unseen layouts, rules alone caught 1.4% of
  undeclared names.
- Optional spaCy NER (`TE_NER=spacy`, enabled in the Docker image) masks third parties without erasing
  verbs, tools or diplomas.
- Word `.docx` CVs (paragraphs, tables, headers) and a layout-mode fallback for multi-column PDFs.
- Prompt-injection screen rewritten by attack family, with homoglyph folding; invisible characters are
  now counted on the raw text (the old check could never fire). 30/30 known attacks, 0 false positives,
  1/10 unseen attacks — hence **bounded LLM influence** (±1 level around the evidence-based estimate).
- Anti-gaming: CV-only skills capped at level 2, dilution of multi-skill lines, template-repetition
  damping, repository substance factor. A keyword-stuffed CV dropped from 64% to 34%.
- Fairness suite: counterfactual identity test, Hypothesis invariants on the credential cap and
  monotonicity, injection corpus, gaming scenarios. Measurements printed in CI.

## 0.1.0 — 2026-10-08

First public skeleton.

- Module 1 (Legal Shield): rule-based text pseudonymisation with an encrypted, reversible vault and
  crypto-shredding; visual redaction through a local vision-language model, fail-closed; prompt-injection
  screen; append-only, hash-chained and HMAC-sealed audit ledger.
- Module 2 (Budget Funnel): repository-tree analysis without reading code, claim-versus-proof document
  analysis, credential extraction, factual density, top-N% escalation with per-request token and per-job
  dollar budgets; Anthropic, Ollama and OpenAI-compatible providers.
- Module 3 (Universal Translator): 31-skill catalogue in French and English, deterministic three-axis
  skill graph, LLM system prompt with code-side validation of every cited piece of evidence.
- Module 4 (HR Dashboard): compatibility score with credentials capped at 25%, gaps, generated interview
  guide, human decisions, re-identification after decision, GDPR erasure.
- React front-end: configuration studio, ranked pipeline, candidate report, audit ledger.
- Demo data set, Docker image, CI.

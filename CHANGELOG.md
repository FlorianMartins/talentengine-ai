# Changelog

## 0.10.2 — 2026-10-09

- **Public read-only demo** of the recruiter area: visitors without an account click "Explore the demo" on the
  sign-in screen and browse jobs, candidates and reports with fictional data. It is a separate engine in a
  temporary directory (`/demo/api`): it never reads the real applications, and every write is refused (403).
  A banner and disabled buttons say it is a read-only demo. `TE_DEMO_PUBLIC=false` turns it off.

## 0.10.1 — 2026-10-09

- **Sign-in screen** for the recruiter area: without an access key, pages show a sign-in form (why a key is
  needed, that it is not an AI key, links to the public trial) instead of an error card; a refused key says so.
- Wording: "API key" became "access key (te_…)" everywhere, to avoid any confusion with a model key.

## 0.10.0 — 2026-10-09

Real tests, and a professional design.

- **The missions' tests run for real**: the Python missions' `tests/` run with pytest in an isolated runner
  container; the CI shows passed/failed tests and pytest's output; a real failure turns the CI red even when
  every static check is green.
- **Hidden behavioural audits** at close exercise each planted flaw (injection in capitals or in an earlier
  message, personal data in logs, a failing screen, a pseudonym recomputable without a key, IBANs in debug
  logs); a confirmed flaw counts as present even if the static audit missed it (`confirmed_by_test`).
- **Runner** (`runner/`): its own container, no network, no secret, no volume, read-only, no capabilities,
  128 processes, 2 GB, 1.5 CPU, per-run temporary directory, rlimits and timeout; escape attempts measured
  (no network, no DNS, read-only file system, no secret in the environment, fork bomb capped).
- **Professional design**: light theme by default (sober dark theme kept), neutral greys with one ink-blue accent
  (`#2F5BDA`), Inter for the interface and JetBrains Mono only for code, 6–8 px radii, flat surfaces with 1 px
  borders; neon accents, glows, gradients, animated decorations and score rings removed (plain figures with a
  thin bar instead); calm test player; black-on-white print; contrast checked (text 16.5:1, white on accent
  5.8:1). Fonts self-hosted, within the production CSP.
- The mission's CI panel shows pytest's verdict per test and its output.
- Running the tests found a real defect static analysis could not see: the reference export's own tests failed
  because the KMS key is read at import — the reference tests now set a test-only key, as a real pipeline does.

## 0.9.0 — 2026-10-09

Bring your own model key.

- **Per-recruiter model key** in *Settings → My AI model*: OpenRouter (free models listed live), Anthropic,
  OpenAI, Mistral or a custom HTTPS OpenAI-compatible endpoint (SSRF-guarded). Encrypted with the vault key,
  never returned, deleted with the account, journalled without the key; "test the connection" button.
- The tests a recruiter sends use **their** model as judge (and, if chosen, as assistant); the deployment still
  needs no paid model, and reports stay complete without one.
- **The candidate never waits for the judge**: the factual report is saved on close and refined in the
  background (`pilot_judged` in the ledger).
- **Free-model compatibility**: JSON schema → JSON mode → JSON found in the text; quota (429) and key errors
  give clear messages.
- Clearer access message: the recruiter area needs a personal access key (`te_…`), now labelled "Access key"
  to avoid confusion with a model key.

## 0.8.0 — 2026-10-09

One technical test that works like the job (recruitment phase 3).

- **Three sections in one session**: (1) **knowledge** — situational questions and calculations, calculator
  and internet allowed, nothing blocked, plus questions on the candidate's own work; (2) **with the AI** —
  questions answered with the built-in assistant, which is **wrong on purpose on half of them** (a wrong
  option, a calculation slip) and, when challenged, admits it one time in two; (3) **practice** — the
  practical mission with planted flaws, then five minutes on the candidate's own code.
- Jobs with no practical mission (a chef, a salesperson) get the two question sections.
- Report: applied knowledge (section 1), section 2 score, trap outcomes inside critical thinking, a
  descriptive AI-usage profile (consulted, pasted as is, challenges, wrong answers followed or caught),
  own-work score inside the authenticity of the evidence; index weights 0.25 / 0.20 / 0.35 / 0.20,
  renormalised over the metrics a session has.
- The closed-book verification test (anti-copy layer, Safe Exam Browser) is no longer offered in the
  interface; links already sent keep working.
- Fairness: the mission clock starts when the candidate opens the mission (`/build/start`), not when the
  questions end; "are you sure? recompute" is never counted as a vague instruction.
- API: `/api/pilot/{token}/question`, `/answer`, `/question/timeout`, `/build/start`; start and recruiter creation take
  `knowledge_questions`, `ai_questions`, own-work questions (`seed` / `personal`) and `mission`.
- Docs: `docs/PILOT_TEST.md` became `docs/TECHNICAL_TEST.md`; README, architecture, guides and
  instructions for use updated. The judge's prompt now covers the questions with the assistant.

## 0.7.1 — 2026-10-09

- **Fix**: a server update in the middle of a sandbox test made the link "unknown or expired" (the AI-pilot
  chat returned 404, then the final screen said the link was invalid). Sandbox test sessions now survive a
  restart: kept encrypted with the vault key and deleted when they expire (3 hours at most). The CV
  analysis of the sandbox is still never stored.

## 0.7.0 — 2026-10-09

A larger, harder AI-pilot test.

- **Three new missions**: `ml_leakage` (churn model: scaler fitted before the split, a feature only known
  after the outcome, regularisation tuned on the test set), `frontend_xss` (React Markdown comments:
  unsanitised HTML, `javascript:` author links) and `iac_storage` (Terraform partner bucket: public access
  block off, `s3:*` on `*`, unencrypted state).
- **A third flaw for the first missions**: a fail-open injection screen (CWE-636), a hard-coded HMAC key and
  an API token baked into the image. Level 3 now draws three flaws.
- **Second-order traps** (`Fault.after`): a flaw that only appears in the assistant's *fix* of another one —
  reject the unkeyed hash, get an HMAC with its key in the source.
- **Fairer routing**: scenario fit is divided by the square root of the scenario's skill count, so a cloud
  architect gets Terraform and a data scientist the churn model.
- **Robust hidden audits** for code a model leaves broken (line fallback) and for TSX and HCL.
- API: `/chat` also returns the prompt turn, state has `server_time`, `PUT /files` accepts `create_only`,
  and the sandbox start limit only counts valid requests. `pilot/scenarios.py` became a package, one module
  per mission.

## 0.6.0 — 2026-10-09

The AI-pilot test: measure how candidates get work done *with* an AI that is sometimes wrong.

- **Adversarial sandbox** (`pilot/`): three missions (secure an LLM gateway, pseudonymised banking export
  under FINMA/GDPR, production container), an internal assistant — reference (scripted, identical for
  everyone) or a real model (Llama-3 / Qwen-Coder via Ollama, vLLM or any provider) — and a static virtual
  CI that never executes candidate code.
- **Hallucination injector**: subtle, realistic flaws (OWASP LLM01/LLM02, PII in logs, unkeyed hash, root
  container, Docker socket) planted once each by hidden directive, verified by a hidden audit and spliced
  from the reference when a model does not comply; per-candidate draws from a standard pool; recruiters can
  arm one more flaw during a live session.
- **Piloting metrics** computed from the telemetry: intent precision and framing, critical thinking and
  redirection (anticipated / called out / removed by hand / accepted, speed, fixed at close), orchestration
  velocity (green CI vs par, regressions); pilot index 0.30/0.45/0.25.
- **LLM-as-a-judge** with a published system prompt: proposals must cite transcript turns, move a metric
  by ±15 points at most, cannot raise anything when the candidate addressed the evaluator, and call-outs
  need a verbatim quote.
- **Authenticity of the evidence**: a five-minute task on a real function of the candidate's own repository
  (Python AST and brace parsing for JS/TS, Go, Java, Kotlin, Rust, C#, PHP), constraint fitted to the
  function; signals = names from elsewhere in the repository, precision, location, "explain my function"
  requests, time to first instruction.
- **Front end**: pilot player (`/pilote/:token`, IDE-like chat + editor + CI, server clock, own-code step), shared report view (metrics with factual vs judge, cited evidence linked to the transcript, flaws revealed with explanations), sandbox entry, recruiter panel with live flaw arming, pipeline chip, landing section.
- **HR dashboard**: `pilot_index_pct`, `authenticity_pct`, `verified_pct` per candidate (ranking unchanged);
  ledger events `pilot_created`, `pilot_fault_armed`, `pilot_completed`; sessions erased and exported with
  the application. Applications keep three pseudonymised source files per repository for the own-code task.
- Docs: [PILOT_TEST.md](docs/PILOT_TEST.md) and updates across the architecture, measurements, instructions
  for use, user and recruiter guides. 156 backend tests; validated with qwen2.5-coder:7b as the assistant.

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

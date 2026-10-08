# Implementation roadmap — from skeleton to MVP by the end of December 2026

This plan assumes **spare-time work: about 6–8 hours a week** from mid-October to 31 December 2026
(12 weeks, ≈ 80–90 hours). Each phase ends with something that runs and is tested, so the project is
always demonstrable — useful for a portfolio, and the right habit for a high-risk AI system.

Legend: ✅ delivered in the initial skeleton · 🔜 to do · ⭐ highest value for the time spent

---

## Phase 0 — Skeleton (delivered, week of 6 October)

| | Item |
|---|---|
| ✅ | FastAPI app, Pydantic domain model, SQLite store, CLI (`serve`, `seed`, `verify`, `keygen`) |
| ✅ | Module 1: rule-based text pseudonymiser, encrypted vault, crypto-shredding, vision redactor (Ollama VLM / OpenCV / fail-closed), injection screen, hash-chained + sealed ledger |
| ✅ | Module 2: repository-tree analyser, document/claim/proof analyser, credential extractor, factual density, escalation planner, budget guard, providers (Anthropic, Ollama, OpenAI-compatible) |
| ✅ | Module 3: 31-skill catalogue FR/EN, deterministic 3-axis graph, LLM system prompt + schema + code validation |
| ✅ | Module 4: capped scoring, gaps, interview guide, 8 job presets, decisions, re-identification, erasure |
| ✅ | React front-end (configuration studio, ranked pipeline, report, audit), demo data, CI |

---

## Phase 1 — Make the shield trustworthy on real documents (weeks 1–3, ~20 h) ⭐

The shield is the legal foundation; it has to hold on messy real CVs before anything else matters.

Status (v0.2.0): items 2–4 ✅ on synthetic corpora — see [MEASUREMENTS.md](MEASUREMENTS.md); the declared
name became mandatory after held-out measurements; items 1 and 5 🔜 need real, consented data.

1. 🔜 **Build a private evaluation set** (never committed): 30–50 real CVs from consenting friends or
   public sample CVs, in French and English, PDF and DOCX. Annotate the PII by hand.
2. ✅ **Measure recall per PII category** with a small script (`eval/pii_recall.py`): target ≥ 99% on
   e-mails/phones, ≥ 95% on names. Record the numbers in `docs/MEASUREMENTS.md`.
3. ✅ **Plug an NER backend** through `NerBackend` (spaCy `fr_core_news_md` + `en_core_web_sm`, or
   Presidio) as an optional extra, and compare recall with/without.
4. ✅ **DOCX support** (`python-docx`) and better PDF extraction (column layouts): `pypdf` first, then
   `pdfplumber` as a fallback.
5. 🔜 **Real images**: pull `qwen2.5vl:7b` in Ollama, run 20 portfolio photos (with and without people),
   measure face-masking recall, tune the detection prompt. Write the result honestly in the docs.

*Done when:* recall numbers are published and the CI runs the anonymised regression subset.

## Phase 2 — Fairness and robustness tests (weeks 4–5, ~14 h) ⭐

High-risk systems must show they do not discriminate. Make it a test, not a promise.

Status (v0.2.0): ✅ delivered — `tests/test_fairness_robustness.py`, `eval/gaming.py`. Remaining: text hidden
in PDFs (white on white, 1-pt fonts) is not detected yet.

1. ✅ **Counterfactual tests**: same CV, swap names, genders, ages, nationalities, schools → the score
   must be *identical* (it should be, since the shield removes them — prove it in CI).
2. ✅ **Credential invariants** as property tests (Hypothesis): for any job configuration, paper alone
   ≤ `c`, and adding a diploma never moves a candidate by more than `c × 100` points.
3. ✅ **Prompt-injection suite**: 30 attack variants (hidden text, white-on-white PDF text, Unicode tricks,
   French/English) → every one flagged or harmless.
4. ✅ **Gaming resistance**: keyword-stuffed CVs, empty repositories with only CI files, copied
   templates → document what moves the score and adjust signal strengths.

## Phase 3 — Level 2 for real (weeks 6–7, ~14 h)

1. Run the escalation path against Claude on the demo set with a small budget (≈ $1), log tokens and
   cost per candidate, and publish the measured "≈ 90% fewer tokens than sending everything" ratio.
2. Add **prompt caching** of the system prompt + catalogue (it is identical for every candidate) and
   measure the saving.
3. Compare heuristic vs LLM assessments on 10 hand-reviewed candidates; keep a small **eval set** so
   prompt changes are measured, not guessed.
4. Batch mode (Message Batches API, −50% price) for overnight evaluation of large job pools.

## Phase 4 — Production basics (weeks 8–9, ~14 h)

1. **Authentication and roles**: OIDC login (Keycloak or Authentik), roles *recruiter*, *hiring
   manager*, *DPO*, *admin*; the `X-Actor` header is replaced by the authenticated identity.
2. **PostgreSQL** behind the `Store` interface (ledger triggers ported as `BEFORE UPDATE/DELETE` rules),
   Alembic migrations.
3. **Background jobs** for ingestion and evaluation (RQ or arq) so a 500-candidate job does not block a
   request; progress shown in the UI.
4. **Retention enforcement**: a daily task that erases candidates past `retention_days` (with ledger
   entries), plus export of a candidate's data (GDPR Art. 15/20).

## Phase 5 — The candidate side and explainability exports (weeks 10–11, ~14 h)

1. **Candidate portal**: a public application page per job (the submission form already exists) and a
   "Why this score?" page reachable with a one-time token: the evidence used, in plain language.
2. **PDF export** of the report and of the ledger extract for one candidate (audit file).
3. **DPIA template** pre-filled from the configuration (`docs/DPIA-template.md`).
4. Integrations: inbound webhook from an existing ATS (Greenhouse/Lever/Workable) and outbound
   shortlist export.

## Phase 6 — Polish and launch (week 12, ~8 h)

1. Docker image published to GHCR, one-command `docker compose up` with Ollama.
2. Hosted demo with the fictional data set only.
3. Write-up for the portfolio: architecture, measurements, what did not work.

---

## Weekly rhythm that works in spare time

* **One evening**: write the test that describes the next behaviour (it fails).
* **One evening**: make it pass, keep CI green, update the docs in the same commit.
* **Weekend slot (2–3 h)**: the larger item of the phase (a new analyser, a UI screen, a measurement).
* Every Sunday: tag a version, write three lines in `CHANGELOG.md`.

## Risks to watch

| Risk | Mitigation |
|---|---|
| Rule-based masking misses rare names | NER backend in Phase 1, recall published, re-identification test in CI |
| Signal strengths encode the author's own bias about "good work" | Make every constant explicit (they are), review them with practitioners of each trade, track changes in the ledger via job versions |
| GitHub rate limits (60 req/h unauthenticated) | `TE_GITHUB_TOKEN`, caching of trees by commit SHA |
| Over-claiming compliance | Keep `docs/COMPLIANCE.md` precise about what the code does and what remains organisational |

# Changelog

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

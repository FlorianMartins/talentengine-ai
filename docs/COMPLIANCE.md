# Compliance mapping — GDPR and EU AI Act

> **Read this first.** Software alone cannot make an organisation compliant. This page maps what the
> code *does* to the obligations it helps meet, and lists what remains the deployer's responsibility.
> It is engineering documentation, not legal advice.

AI systems used "for the recruitment or selection of natural persons, in particular to place targeted
job advertisements, to analyse and filter job applications, and to evaluate candidates" are listed as
**high-risk** in Annex III (4)(a) of the EU AI Act (Regulation (EU) 2024/1689). Since the Digital Omnibus
on AI (Regulation (EU) 2026/1744), the Annex III obligations apply from **2 December 2027**; the
prohibition of emotion recognition in the workplace (Art. 5(1)(f)) has applied since 2 February 2025, and
the GDPR and national labour law apply today. **Provider and deployer obligations, the go-to-market
checklist and French labour-law requirements are in [AI_ACT_READINESS.md](AI_ACT_READINESS.md)**; see also
[INSTRUCTIONS_FOR_USE.md](INSTRUCTIONS_FOR_USE.md) and [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md).

## EU AI Act

| Obligation | What TalentEngine-AI does | Where |
|---|---|---|
| **Art. 9 Risk management** | Explicit risk list and mitigations; fail-closed defaults (image quarantine, local-only mode, escalation opt-in) | `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` |
| **Art. 10 Data governance** | Only data needed for skills reaches the model; protected characteristics and bias proxies (school names, gendered grammar) are removed before analysis; masking recall is measured per name origin and a counterfactual test requires identical scores across identities | `shield/pii.py`, `shield/vision.py`, `docs/MEASUREMENTS.md`, `tests/test_fairness_robustness.py` |
| **Art. 11 Technical documentation** | Architecture manifesto, scoring formulas, prompt and schema in version control | `docs/`, `translator/prompts.py` |
| **Art. 12 Record-keeping** | Append-only, hash-chained, HMAC-sealed ledger of configuration versions, ingestion, escalation, scores, decisions, re-identification and erasure | `shield/ledger.py` |
| **Art. 13 Transparency** | Every score ships with its criteria breakdown, the evidence excerpts used, the configuration version and a plain-language notice | `DashboardReport`, `/api/candidates/{ref}/explanation` |
| **Art. 14 Human oversight** | No reject path exists; ranking only; decisions require a written rationale and are signed with the authenticated account name (roles: recruiter, DPO, admin); bands describe evidence, not people; the reviewer sees warnings (injection, quarantine) | `pipeline.Engine.decide`, `auth.py` |
| **Art. 15 Accuracy, robustness, cybersecurity** | Prompt-injection screening and exclusion; LLM outputs validated against cited evidence and bounded to ±1 level of the deterministic estimate; gaming-resistance scenarios; budget guard; all measured in CI | `shield/injection.py`, `translator/llm_eval.py`, `eval/`, `docs/MEASUREMENTS.md` |
| **Art. 26 Deployer duties** | Supports them (logs kept, human oversight tooling); informing workers' representatives and candidates remains organisational | — |
| **Art. 86 Right to explanation** | The recruiter sends the candidate a private explanation link (30 days, no identifier inside, logged when opened, dies with erasure) showing the exact excerpts behind each skill, the criteria, the decision and its rationale, and the ledger integrity | `/api/candidates/{ref}/explanation-link`, `/explication/<token>` |

## GDPR

| Article | What TalentEngine-AI does |
|---|---|
| **Art. 5(1)(c) Minimisation** | Repository analysis reads file *names*, plus at most six key files; documents are pseudonymised before storage; raw uploads are not kept |
| **Art. 6 / 7 Lawful basis, consent** | Ingestion refuses a submission without explicit consent; consent, purpose and retention are recorded in the ledger |
| **Art. 13 Information** | Submission form explains purpose, retention and the masking of identity |
| **Art. 5(1)(e) Storage limitation** | Applications are erased automatically when their consented retention period ends (daily sweep, logged) |
| **Art. 15 / 20 Access, portability** | DPO export of everything held about a candidate (identity, artifacts, report, audit trail) as JSON, logged |
| **Art. 17 Erasure** | `POST /api/candidates/{ref}/erase` deletes artifacts, media and report, and shreds the vault keys; the ledger keeps only unlinkable pseudonyms |
| **Art. 22 Automated decisions** | No decision with legal or similarly significant effect is automated: the system only ranks evidence; every decision is human and justified |
| **Art. 25 Privacy by design and by default** | Local-first, escalation off by default, images quarantined without a detector, school names masked by default |
| **Art. 32 Security** | Encrypted vault (Fernet), sealed ledger, optional API key, upload limits, security headers |
| **Art. 35 DPIA** | A draft is generated per job from the live configuration (CNIL PIA structure + AI Act deployer duties), with the items only the organisation can decide marked *to complete* |

## What the deployer still has to do

* Complete and sign off the **DPIA** (the draft is a starting point) and the AI Act **fundamental-rights
  impact assessment** where it applies.
* Inform candidates (privacy notice), workers' representatives, and register as required.
* Choose and contract the escalation provider (data-processing agreement, region) — or keep the
  default local-only mode.
* Train recruiters: the score ranks *evidence*; it is not a verdict on a person.
* Review the signal strengths and skill definitions with practitioners of each trade before use.

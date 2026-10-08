# AI Act readiness — what it takes to use or sell TalentEngine-AI in the real world

> Engineering documentation, not legal advice. Facts below were checked on 8 October 2026 with the
> sources listed at the end; have them confirmed by counsel before placing the system on the market.

## 1. Classification: high-risk, no way around it

* Recruitment and selection — "to analyse and filter job applications, and to evaluate candidates" — is
  listed in **Annex III, point 4(a)** of Regulation (EU) 2024/1689.
* The **Art. 6(3) derogation** (narrow procedural or preparatory task) is not available in practice: an
  Annex III system "shall always be considered to be high-risk where the AI system performs profiling of
  natural persons", and scoring candidates on their work evaluates personal aspects such as performance at
  work — profiling in the GDPR Art. 4(4) sense.
* **Prohibited since 2 February 2025 — Art. 5(1)(f)**: inferring emotions of a natural person in the
  workplace from biometric data. The Commission guidelines extend this to candidates during recruitment.
  TalentEngine-AI uses **no webcam, no voice analysis, no biometric inference** — including in its
  verification tests — and must keep it that way.

## 2. Timeline (as amended by the Digital Omnibus on AI)

| Date | What applies |
|---|---|
| 2 Feb 2025 | Prohibited practices (Art. 5), AI literacy (Art. 4) |
| 2 Aug 2025 | General-purpose AI rules, governance, penalties framework |
| **2 Dec 2027** | **High-risk obligations for Annex III systems — including recruitment** (Chapter III, Sections 1–3) |
| 2 Aug 2028 | High-risk obligations for Annex I (product-safety) systems |

The original text applied Annex III obligations from 2 August 2026. **Regulation (EU) 2026/1744** (the
"Digital Omnibus on AI", OJ L of 24 July 2026, in force 27 July 2026) moved them to **2 December 2027**
with fixed dates. GDPR and national labour law apply **today**, regardless of this calendar.

## 3. Who must do what

### If you **sell or provide** TalentEngine-AI (provider)

| Obligation | Article | Done by the software | Remains to do (organisational) |
|---|---|---|---|
| Risk management system | 9 | Risks listed with mitigations; fail-closed defaults; fairness, injection and gaming tests in CI (`MEASUREMENTS.md`) | A maintained risk register owned by a named person, reviewed per release |
| Data and data governance | 10 | Pseudonymisation before analysis; masking measured per name origin; no training on candidate data | Document data sources of the rules and question bank; bias review by practitioners |
| Technical documentation | 11 + Annex IV | [`TECHNICAL_DOCUMENTATION.md`](TECHNICAL_DOCUMENTATION.md) structured on Annex IV, architecture, measurements | Keep it versioned per release for 10 years |
| Record-keeping (logs) | 12, 19 | Append-only, hash-chained, HMAC-sealed ledger of every configuration, score, test, decision, reveal, export and erasure; never purged (≥ 6 months guaranteed) | Back up the ledger; keep logs under the provider's control ≥ 6 months |
| Transparency, instructions for use | 13 | [`INSTRUCTIONS_FOR_USE.md`](INSTRUCTIONS_FOR_USE.md); per-score explanations; candidate explanation links | Provide them with every deployment |
| Human oversight | 14 | No rejection path in code; named, reasoned decisions signed by authenticated accounts; evidence bands describe material, not people; integrity flags never act automatically | Train the people who oversee |
| Accuracy, robustness, cybersecurity | 15 | Measured masking, bounded LLM influence, injection screen, anti-gaming rules, SSRF guards, rate limits, CSP | Publish accuracy figures in the instructions; pen-test before market |
| Quality management system | 17 | CI gates (lint, types, 120+ tests, secret scan), changelog, releases | A written QMS (change control, responsibilities, supplier control) |
| Conformity assessment | 43(2) | — | **Internal control (Annex VI)** — no notified body for Annex III point 4 |
| EU declaration of conformity | 47 | — | Draw up, keep 10 years |
| CE marking | 48 | — | Affix (digital marking for software) |
| Registration in the EU database | 49(1), 71 | — | Register before placing on the market |
| Post-market monitoring | 72 | `GET /api/admin/monitoring`: score and evidence-band distributions, human overrides of the ranking, test integrity rates, AI spend | A monitoring plan and periodic review |
| Serious-incident reporting | 73 | `POST /api/admin/incidents` records incidents in the ledger with the reporting deadline | Report to the market surveillance authority within **15 days** (2 days for widespread infringements, 10 days in case of death) |

### If you **use** TalentEngine-AI to hire (deployer — every client company)

| Obligation | Article | How the software helps |
|---|---|---|
| Use according to the instructions; competent human oversight | 26(1)-(2) | Instructions for use; roles (recruiter, DPO, admin); authenticated decisions |
| Input data relevant to the purpose | 26(4) | Job profiles define criteria; credentials capped; protected data masked |
| Monitor operation, suspend and report risks | 26(5) | Monitoring endpoint; incident journal |
| **Keep logs ≥ 6 months** | 26(6) | Ledger is never purged; candidate erasure keeps it intact and unlinkable |
| **Inform workers' representatives and workers before use** | 26(7) | Template in §5 below; CNIL/CSE pack generated from the configuration (DPIA draft) |
| **Inform candidates subject to the system** | 26(11) | Information notice shown on every application form and test; explanation links |
| DPIA (GDPR Art. 35) | 26(9) | DPIA draft generated per job from the live configuration |
| Fundamental-rights impact assessment | 27 | **Not required** for a private employer recruiting for itself (only public bodies, private entities providing public services, credit and insurance scoring) |
| Right to explanation | 86 | Candidate explanation link: evidence, criteria, decision and rationale |

## 4. France: labour law applies today

| Article (Code du travail) | Requirement | In TalentEngine-AI |
|---|---|---|
| L1221-6 | Information asked of a candidate must have a direct and necessary link with the job | Criteria are job-specific; protected data is masked and never scored |
| L1221-8 | Candidates are expressly informed **beforehand** of the recruitment methods and techniques; methods are relevant; results are confidential | Information notice before any submission or test (§5); explanation link; results visible only to authorised accounts |
| L1221-9 | No information collected by a device not brought to the candidate's prior knowledge | The test integrity monitoring (focus, paste, print-screen, Safe Exam Browser) is announced before the test starts; nothing else is collected |
| L2312-38 | The CSE is informed beforehand of recruitment-assistance methods and techniques | Use the DPIA draft and the instructions for use as the information file |
| L1221-7 | CV anonymisation is optional | Done by default |

## 5. Candidate information notice (to show before applying or starting a test)

> Your application is assessed with TalentEngine-AI, a decision-support tool. It analyses the material you
> provide (CV, LinkedIn profile, documents, public repositories, portfolio) to identify evidence of the
> skills required for this job. Your identity, age, nationality, family status and the names of your
> schools are hidden before analysis. The tool ranks evidence; it never rejects anyone: every decision is
> taken and justified by a named person. During a verification test, the test page records whether it
> loses focus, copy/paste/print-screen attempts and answer timings; it does not use your camera or
> microphone. You can obtain an explanation of your result, access or erase your data by contacting the
> recruiter. Retention: as stated in the form.

## 6. Go-to-market checklist (provider)

1. Freeze a release; generate the technical documentation pack and measurements for it.
2. Run the internal-control conformity assessment (Annex VI) against Arts. 9–15 and 17; keep the evidence.
3. Write and sign the EU declaration of conformity; apply the CE marking; register in the EU database.
4. Ship the instructions for use and the candidate notice with every deployment.
5. Put the post-market monitoring plan and the incident procedure in place (owner, cadence, contacts).
6. Before the first client goes live: DPIA, CSE information, candidate notices on job ads and forms.

## Sources

* Regulation (EU) 2024/1689 (AI Act): https://eur-lex.europa.eu/eli/reg/2024/1689/oj
* Regulation (EU) 2026/1744 (Digital Omnibus on AI): https://eur-lex.europa.eu/eli/reg/2026/1744/oj
* Art. 43 (internal control for Annex III points 2–8): https://artificialintelligenceact.eu/article/43/
* Art. 26 (deployers), Art. 27 (FRIA scope), Art. 6 (classification): https://artificialintelligenceact.eu/
* Emotion-recognition prohibition and recruitment: https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/
* Code du travail: https://www.legifrance.gouv.fr/codes/id/LEGITEXT000006072050

# Instructions for use (AI Act Art. 13)

Version: TalentEngine-AI 0.6.0 · Provider: the organisation placing this software on the market under its
name (fill in name, address and contact before any deployment) · Source: https://github.com/FlorianMartins/talentengine-ai

## 1. Intended purpose

Decision support for recruiters: it ranks applications to a defined job by the **evidence of skills** found
in the material the candidate submits (CV, LinkedIn profile export, documents, public repositories,
portfolio, photos of work) and by optional **verification tests** and **AI-pilot tests**, explains every
score, and prepares
interview questions. **It never takes a decision**: shortlisting, interviewing or not retaining a candidate
is always done and justified by an identified person.

### Not intended for — reasonably foreseeable misuse to avoid

* Rejecting candidates automatically, or filtering them out of view by score thresholds.
* Using the score as the only ground for a decision, or communicating it to the candidate as a verdict.
* Evaluating employees already in post, for promotion, discipline or dismissal.
* Inferring emotions, personality, health or any protected characteristic — prohibited (AI Act Art. 5(1)(f))
  and outside the system's design. Do not add webcam or voice analysis to the verification tests.
* Assessing jobs whose criteria are not represented in the skill catalogue without reviewing the criteria.

## 2. Performance, accuracy and known limits

Measured figures and methods are in [MEASUREMENTS.md](MEASUREMENTS.md). In summary:

| Aspect | Measured | Limit to keep in mind |
|---|---|---|
| Masking of personal data | 100% on synthetic tuning and held-out corpora once the name is declared; identical across 7 name origins | Corpora are synthetic; held-out layouts without a declared name reached only 1.4% (rules) — the declared name is therefore mandatory |
| Fairness | Same work under five identities → identical score (counterfactual test in CI) | Signal strengths and question banks reflect their authors' views of good practice; review them with practitioners |
| Credential weight | ≤ 25% by construction, property-tested | — |
| Gaming resistance | Keyword-stuffed CV 34% (was 64%), showcase repository 12% | A determined impostor can still assemble plausible material: use the verification test and the interview |
| Prompt injection | 30/30 known attacks flagged, 1/10 unseen | The real safeguard is the bounded influence of the escalation model (±1 level) |
| AI-pilot test | 3 scenarios × 2 planted flaws; factual metrics with evidence; judge bounded to ±15 points and citations | Weights and thresholds not yet calibrated on real sessions; call-outs phrased outside the markers rely on the judge or on reading the transcript |
| Verification tests | 236 questions, 37 skills × 3 levels; per-candidate variants; server-side timing | No web page can stop a phone photographing the screen; use Safe Exam Browser for high-stakes tests and the live interview as final check |

## 3. Human oversight (Art. 14) — how to use the output

1. Read the **evidence**, not only the percentage. The evidence band (strong / moderate / limited) describes
   the material provided, not the person.
2. Treat **"not evidenced"** as a question for the interview, never as absence of skill.
3. Treat **test integrity flags** as signals to discuss with the candidate, never as proof of cheating.
   Treat a low **authenticity of the evidence** (AI-pilot own-code task) the same way: five minutes is short.
4. Record every decision with a rationale; the system signs it with your account and logs it.
5. Use the **interview guide** to verify authorship of the work in person.

Persons in charge of oversight must be trained on these points and have the authority to disregard the
ranking. The monitoring endpoint shows how often decisions depart from the ranking — a healthy sign that
oversight is real.

## 4. Input data

* Candidate material in French or English; PDF, DOCX, Markdown, text; PNG/JPEG/WebP images (analysed only
  if a face detector runs); public GitHub repositories (a profile link reads all public repositories).
* The candidate's declared name is required (masking); consent is recorded with the retention period.
* Job profiles: criteria from the skill catalogue, levels, axis and credential weights. Each change is versioned.

## 5. Logging (Art. 12, 19, 26(6))

Every configuration version, ingestion, score, verification test, human decision, identity reveal, export,
erasure, account change and incident is written to an append-only, hash-chained, HMAC-sealed ledger that is
never purged. `talentengine verify` (or `/api/audit/verify`) proves it was not altered. Erasing a candidate
keeps the ledger intact while making it impossible to link to the person.

## 6. Technical requirements and maintenance

Docker image (≈ 0.9 GB) or Python 3.11+; 2 CPU / 2 GB RAM per instance is enough for the sandbox load.
Production settings: vault and seal keys, named accounts, `TE_PUBLIC_BASE_URL` when served behind a proxy.
Updates are published as GitHub releases with a changelog; each release is covered by the CI gates
(lint, type checks, tests, secret scan, container build and smoke test).

## 7. Deployer checklist before go-live

DPIA (draft generated per job), information of workers' representatives (AI Act Art. 26(7); in France
Code du travail L2312-38), candidate information notice on job ads, forms and tests (L1221-8, L1221-9 —
text in [AI_ACT_READINESS.md](AI_ACT_READINESS.md) §5), named accounts and roles, retention period,
procedure for explanation, access and erasure requests, incident contact.

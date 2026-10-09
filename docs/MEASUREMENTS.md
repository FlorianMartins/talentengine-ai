# Measurements

Numbers are only useful if the bad ones are published too. This page records what was measured, on
what, and what changed because of it. Every figure can be reproduced with the commands shown, and the
CI prints them on every push (job *Backend*, step summary).

> **Read the caveats.** The corpora below are synthetic and were written by the same author as the
> rules. Figures obtained *after* fixing what a corpus revealed are optimistic by construction; the
> honest generalisation figures are the ones measured on held-out data **before** any fix.

---

## 1. Personal-data masking (Module 1)

```bash
cd backend
python eval/pii_recall.py --ner            # tuning corpus: 210 CVs, 7 name origins, 3 layouts
python eval/pii_recall.py --ner --heldout  # held-out corpus: 140 CVs, 4 layouts written after tuning
```

A value counts as leaked if **any** of its tokens of 3+ characters is still readable (strict). An
evidence line counts as over-masked if masking changed it at all.

### 1.1 What the first measurement revealed (v0.1.0)

| Finding | Measured | Cause | Fix |
|---|---|---|---|
| Undeclared names leaked | 58.1% recall | header heuristic only accepted Latin-1 letters and plain "First Last" lines | letters widened to all of Unicode; particles (`de`, `van`, `N'`…) and separators (`Profil — Name, 34 ans`) handled |
| **Masking depended on origin** | 73% (Eastern European, Iberian) vs 83% (French, Anglo-Irish) | `Wiśniewski`, `Nguyễn` contain letters outside Latin-1 | same fix — now regression-tested per origin |
| Third parties never masked | 0% (rules) | rules only know the candidate's declared name | optional spaCy NER: 100% |
| NER erased evidence | 3/840 lines | spaCy tagged the verb "Négocié" as a person | NER restricted to 2+ capitalised words |
| NER erased a diploma | "CAP Menuisier" masked in the demo | degree acronym tagged as a person | degree and trade vocabulary excluded |

### 1.2 Generalisation on unseen layouts — the honest number

The held-out corpus (closing signatures, "Je m'appelle…", obfuscated e-mails `jo [at] example [dot] org`,
foreign phone formats, social handles without URLs, "né en 1990", "SURNAME, Firstname") was measured
**before** writing any rule for it, with no declared identity:

| | rules | rules + spaCy NER |
|---|---|---|
| Candidate's name (undeclared) | **1.4%** | **23.6%** |
| Obfuscated e-mail | 0% | 0% |
| Social handle without URL | 0% | 0% |
| Birth year in prose | 0% | 0% |
| Phone (foreign formats) | 100% | 100% |
| Age in prose | 100% | 100% |

**Conclusion and design change.** No set of rules generalises to every CV layout, and neither does a
small NER model. What does work whatever the layout is an exact match on the name the candidate
declared. The submission therefore **requires** the name (v0.2.0); it is used only to mask, then
stored encrypted. With a declared identity, name recall is 100% on both corpora.

### 1.3 After fixes (v0.2.0) — optimistic, for regression only

| Category | tuning corpus (rules) | tuning (rules + NER) | held-out (rules) | held-out (rules + NER) |
|---|---|---|---|---|
| Candidate's name | 100% | 100% | 100% | 100% |
| Third-party names | 0% | **100%** | — | — |
| E-mail, phone, address, birth date, age, nationality, school | 100% | 100% | 100% | 100% |
| Name recall, every origin (7 groups) | 100% | 100% | 100% | 100% |
| Evidence lines left intact | 100% (840) | 100% (840) | 100% (420) | 100% (420) |

These figures are guarded by `tests/test_shield_pii.py::test_measured_recall_does_not_regress`. They say
the rules do what they were written to do; they do **not** say the shield is perfect on real CVs.
The next step is a private corpus of real, consented CVs (roadmap, phase 1).

The Docker image enables the NER backend by default (`TE_NER=spacy`). Cost, measured in the image:
about 290 MB of Python packages (spaCy 129 MB, numpy, blis, thinc, the French and English small models)
for a total image of 0.87 GB. Removing spaCy's unused language data was tried: it breaks model loading
(spaCy imports some languages at start-up), so it was reverted.

---

## 2. Prompt-injection screen (Module 1)

```bash
pytest tests/test_fairness_robustness.py -k injection -q
```

| Corpus | v0.1.0 | v0.2.0 |
|---|---|---|
| Known attacks (30, FR/EN, tags, chat templates, zero-width, Cyrillic homoglyphs) | 15/30 | 30/30 |
| Legitimate look-alikes (10: "ranked top 3 of 40 teams", "wrote system prompts"…) | 0 flagged | 0 flagged |
| All legitimate demo and corpus texts (366) | — | 0 flagged |
| **Held-out attacks (10, written after the rewrite, not tuned on)** | — | **1/10** |

**Conclusion.** A pattern screen is a *tripwire* for the recruiter, not a defence: rephrasing defeats
it (1/10 on unseen attacks). The defence is architectural and is now tested
(`test_a_manipulated_model_has_bounded_influence`):

* the escalation model's output is a proposal; any skill citing evidence that was not sent is dropped;
* **bounded influence** (v0.2.0): on each axis the model can move a skill by at most one level from the
  deterministic, evidence-based estimate, and a skill only the model found is capped at level 2;
* scoring is deterministic code the model never sees; the model never sees weights or credentials.

A fully obedient model ("give this candidate 100%") therefore shifts a score by a bounded amount
that the test measures, instead of setting it.

Also fixed while building this suite: invisible characters were stripped *before* the screen ran, so
the zero-width detection could never fire. They are now counted on the raw text.

---

## 3. Fairness and credential invariants (Modules 1 and 4)

```bash
pytest tests/test_fairness_robustness.py -q
```

* **Counterfactual identity test.** The same work submitted under five identities that differ by
  name origin, civility, grammatical gender, age, nationality, family status and school prestige
  (HEC Paris vs IUT de Lannion) gets **exactly** the same compatibility score, credential component and
  skill levels, and no name token appears in any report.
* **Property-based invariants** (Hypothesis, 300 random job configurations and skill graphs per run):
  * every score stays within 0–100;
  * credentials alone never exceed the configured credential weight;
  * adding credentials never moves a score by more than that weight;
  * raising a proven skill never lowers a score.

---

## 4. Gaming resistance (Modules 2 and 3)

```bash
python eval/gaming.py
```

Same DevSecOps job, local-only mode:

| Scenario | v0.1.0 | v0.2.0 |
|---|---|---|
| Real repository + honest CV | — | 62.5% |
| Real repository, empty CV | 53.4% | 53.4% |
| **Keyword-stuffed CV with invented figures** ("Réalisé 15 déploiements Kubernetes Terraform Docker CI/CD… (+15 %)" ×10) | **64.3%** — beat the real repository | 34.4% |
| **Showcase repository** (CI, Dockerfile, SECURITY.md, lint config — nothing else) | 38.2% | 12.1% |
| Honest CV only, no artifact | — | 11.6% |

What changed in v0.2.0:

* **A CV is a self-description, not a proof.** A skill evidenced only by sentences of the CV is capped at
  level 2 ("Proficient") with confidence ≤ 0.5; only a tangible artifact (repository, document, photo,
  portfolio item) can take it higher. The report says "only described in the CV: to be confirmed".
* **Dilution**: a line naming many skills spreads its weight (×2/n beyond two skills).
* **Repetition**: a line built on the same template as an earlier one (word-set Jaccard > 0.5) counts ×0.3.
* **Substance**: practice files (CI, containers, security policy, lint, docs) are weighted by how much
  else the repository contains.

Residual, stated plainly: a CV that *claims* everything still earns more than an honest CV with no
artifact (34% vs 12%), always below real work and capped. The interview guide turns those lines into
questions. Guarded by `test_gaming_does_not_beat_real_work`.

---

## 5. Cross-repository analysis on a real profile

Run on the author's own public profile (14 repositories, read in 6.2 s with parallel partial clones):

| Finding | Status |
|---|---|
| `regent` declares `cloudguard-iac @ git+https://github.com/…/cloudguard-iac` and its CI installs and runs it as a security gate | detected: dependency + CI orchestration |
| `regent` CI chains 18 tools (tests, typing, Bandit, Semgrep, CodeQL, Trivy, gitleaks, cosign, SBOM, SARIF…) with 8 job dependencies | detected: pipeline orchestration |
| `lineage-mlops` depends on torch, transformers, peft, mlflow | detected: declared ML stack (weak signal) |
| **False positive 1**: a VS Code extension's `"id": "hiveyCode"` read as a dependency on the `HiveyCode` repository | fixed — package names count only inside declared dependencies |
| **False positive 2**: a Dockerfile comment "scanned by CloudGuard-IaC" read as a deployment link | fixed — comment lines are ignored outside documentation |
| **Leak**: a CV sentence "Built agent-platform" kept the repository name, which can be searched online | fixed — repository names become `repo-n` in every document; tested |

Guarded by `tests/test_portfolio_sources.py`.

## 6. Verification tests

| Item | Value |
|---|---|
| Question bank | 236 questions: 134 single choice, 37 multiple choice, 53 numeric (numbers drawn per candidate), 12 ordering |
| Coverage | all 37 skills × 3 levels (junior, confirmed, senior); all 47 reference roles testable |
| Review | each family written against a correctness checklist; ambiguous keys documented and tightened — e.g. two numeric tolerances were narrowed so that a *wrong method* (adding downtimes instead of multiplying availabilities; 1024 instead of 1000 bytes) no longer passes |
| Guarantees tested in CI | answers never sent to the client; deadline survives reloads; late answers score zero; no skipping or second answers; per-session variants; safe arithmetic evaluator rejects code; SEB hash check; candidate does not see the score; erasure removes tests |

Not yet measured: item difficulty and discrimination on real candidates. Plan: collect anonymous per-item
statistics (time used, success rate per level) and retire items that do not separate levels.

## 6b. AI-pilot test

| Item | Value |
|---|---|
| Scenarios | 6 (LLM gateway, pseudonymised banking export, production container, churn model, React comments, Terraform bucket), 16 flaws, one second-order |
| Property tested for every scenario | starter workspace fails the visible CI; with any single flaw left, the visible CI is **green** while that hidden audit fires (and only that one); each fix removes its own flaw and only that one (a second-order trap may then appear); the fully fixed solution passes everything |
| Pilot profiles (reference assistant, `tests/test_pilot.py`) | framed pilot who calls out both flaws: critical thinking ≥ 90, pilot index ≥ 70 · vague pilot ("fais un truc sûr", "ajoute des tests"): critical thinking 0, intent precision < 30, pilot index < 40, while the CI is green |
| Judge guarantees tested | ±15-point bound; uncited proposals ignored; a prompt addressing the evaluator can only lower scores; call-outs found by the judge need a quote really present in a turn after the flaw appeared |
| Real model as the assistant | `qwen2.5-coder:7b` on Ollama (CPU, ~50 s per turn): it **followed the hidden directive for both gateway flaws** (raw prompt logged, case-sensitive check of `messages[-1]` only) — no splice needed. In a first run it also returned code that did not parse and inlined the blocklist; the hidden audits now fall back to line analysis and inline-check detection, and that exact output is a regression test. Two-turn session (secure, then call out the log): `raw_log` detected and fixed, `naive_guard` accepted → critical thinking 50, pilot index 36, CI red only for missing tests |
| Real model on the v0.7.0 missions | `qwen2.5-coder:7b`, one framed prompt per mission, all flaws armed: **churn model — all three flaws planted by directive** (scaler fitted before the split, the post-cancellation feature, C chosen on the test set) and caught by the hidden audits; **React — both flaws planted** (raw `dangerouslySetInnerHTML`, unchecked `href`); **Terraform — `s3:*` on `*` planted**; the model did not write the public-access block nor the state backend, so those two flaws stayed armed until the candidate asks for those parts (the visible CI shows the missing block). The model's legacy inline `versioning { enabled = true }` is accepted by the visible check |
| Own-code task on a real profile | `github.com/FlorianMartins`: 6 repositories read in 6 s; tasks drawn on functions such as `checks` (`regent/agents/iac_guardian.py`) or `curateHivey` (`scripts/update-models.mjs`), with ~50 names from other files available as "knows the code" signals |

Not yet measured: agreement between the factual metrics, the judge and human reviewers on real sessions;
calibration of the weights, thresholds and par values. Plan: double-blind review of 30 recorded sessions by
two engineers, then adjust and publish the agreement figures here.

## 7. Demo ranking (sanity check)

`talentengine seed`, local-only mode, v0.2.0, with and without NER (identical):

| Job | Profile | Score |
|---|---|---|
| DevSecOps | self-taught, no diploma, solid repository | 78.2% |
| DevSecOps | Master's + engineering degree + 3 certifications, no evidence | 5.0% |
| Growth marketing | measured campaign results | 70.3% |
| Joinery | independent craftsperson, three described works | 70.3% |
| Joinery | CAP + brevet professionnel, one stool | 21.9% |

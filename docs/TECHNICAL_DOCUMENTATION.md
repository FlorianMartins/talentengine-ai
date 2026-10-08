# Technical documentation (AI Act Art. 11, Annex IV)

This file follows the structure of Annex IV and points to the evidence kept in this repository. A frozen
copy must be produced for each release placed on the market and kept for ten years.

| Annex IV item | Where it is documented |
|---|---|
| **1(a)** Intended purpose, provider, version | [INSTRUCTIONS_FOR_USE.md](INSTRUCTIONS_FOR_USE.md) §1; `CHANGELOG.md`; release tag |
| **1(b)** Interaction with other hardware/software | [ARCHITECTURE.md](ARCHITECTURE.md) §2 (modules), §4 (GitHub, LLM providers), ATS bridge ([ATS_BRIDGE.md](ATS_BRIDGE.md)) |
| **1(c)** Versions of relevant software, update requirements | `backend/pyproject.toml`, `frontend/package-lock.json`, Dockerfile pins, CI workflow |
| **1(d)** Forms in which the system is placed on the market | Docker image, source distribution, hosted instance |
| **1(e)** Hardware it runs on | INSTRUCTIONS_FOR_USE §6 |
| **1(g)** Basic description of the user interface | `frontend/README.md`, screenshots in `docs/images/` |
| **1(h)** Instructions for use | [INSTRUCTIONS_FOR_USE.md](INSTRUCTIONS_FOR_USE.md) |
| **2(a)** Development methods, pre-trained systems used | No model is trained on candidate data. Level 1 is rule-based (`funnel/`, `translator/heuristic.py`); optional spaCy small NER models; optional escalation LLM whose output is validated and bounded (`translator/llm_eval.py`) |
| **2(b)** Design specifications, logic, key choices and trade-offs | [ARCHITECTURE.md](ARCHITECTURE.md): scoring formulas (§6), three axes (§5), credential cap, anti-gaming rules, bounded LLM influence, verification tests (§9), AI-pilot test (§9b and [PILOT_TEST.md](PILOT_TEST.md)) |
| **2(c)** System architecture, computational resources | [ARCHITECTURE.md](ARCHITECTURE.md) §2, §7, §11 |
| **2(d)** Data requirements, datasheets, provenance | No training data. Evaluation corpora: `backend/eval/pii_corpus.py` (synthetic, documented), question bank `backend/talentengine/assessment/bank/*.json` (authored, reviewed, versioned), AI-pilot scenarios and flaw pools `backend/talentengine/pilot/scenarios.py` (authored, versioned; judge prompt in `pilot/judge.py`) |
| **2(e)** Human oversight measures (Art. 14) | INSTRUCTIONS_FOR_USE §3; `auth.py` (roles, signed decisions); no reject path |
| **2(f)** Predetermined changes | Job-profile versions are logged; question bank and signal strengths change only through releases |
| **2(g)** Validation and testing procedures, metrics, test logs | [MEASUREMENTS.md](MEASUREMENTS.md); `backend/tests/` (150+ tests: fairness, invariants, injection, gaming, masking, assessment, AI-pilot test); CI logs per release |
| **2(h)** Cybersecurity measures | ARCHITECTURE §11; SSRF guard, CSP, rate limits, hashed keys, encrypted vault, sealed ledger, secret scanning |
| **3** Monitoring, functioning and control; accuracy per group | MEASUREMENTS (per name origin); `/api/admin/monitoring`; known limits in INSTRUCTIONS_FOR_USE §2 |
| **4** Appropriateness of performance metrics | MEASUREMENTS — each metric with its caveat and the honest pre-fix figure |
| **5** Risk management system (Art. 9) | [AI_ACT_READINESS.md](AI_ACT_READINESS.md) §3; ROADMAP risk table; incident journal (`/api/admin/incidents`) |
| **6** Changes through the lifecycle | `CHANGELOG.md`, git history, releases |
| **7** Harmonised standards applied | None published yet for this purpose; to be updated when available |
| **8** EU declaration of conformity | To be issued by the provider (Art. 47) — template outside this repository |
| **9** Post-market monitoring plan (Art. 72) | AI_ACT_READINESS §3 and §6; monitoring endpoint |

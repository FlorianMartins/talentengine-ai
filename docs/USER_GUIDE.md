# User guide

This guide is for the two people who meet TalentEngine-AI: the **administrator** who installs it and
the **recruiter** who uses it every day. No technical knowledge is needed for the second part.

---

## Part 1 — Install and run (administrator)

### Option A: Docker (recommended)

```bash
git clone https://github.com/FlorianMartins/talentengine-ai.git
cd talentengine-ai
cp .env.example .env            # then edit it (see the table below)
docker compose up -d --build    # http://localhost:8000
```

To also run a local vision model for portfolio images (needs ~8 GB of RAM):

```bash
docker compose --profile vision up -d
docker compose exec ollama ollama pull qwen2.5vl:7b
```

### Option B: from source

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e "backend[dev]"
cd frontend && npm ci && npm run build && cd ..
cd backend && talentengine serve            # http://127.0.0.1:8000
```

During front-end development run `talentengine serve` and, in another terminal,
`cd frontend && npm run dev` (http://localhost:5173, API calls are proxied).

### Load the demo

Click **Load demo data** on the empty overview, or run `talentengine seed`. It creates three job
profiles (DevSecOps, growth marketing, joinery) and eleven fictional candidates.

### Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `TE_DATA_DIR` | `./data` | Where the SQLite database, keys and redacted images live. Back it up. |
| `TE_VAULT_KEY` | generated | Fernet key encrypting identities. **Set it in production** (`talentengine keygen`). |
| `TE_LEDGER_SEAL_KEY` | generated | HMAC key sealing the audit ledger. **Set it in production.** |
| `TE_API_KEY` | empty | If set, every API call must send `X-API-Key`. The UI asks for it in Settings. |
| `TE_NER` | `none` (`spacy` in Docker) | Statistical name detection on top of the rules; masks other people named in a CV (managers, referees). From source: `pip install -e "backend[ner]"` then `python -m spacy download fr_core_news_sm` and `en_core_web_sm`. |
| `TE_VISION_DETECTOR` | `ollama` | `ollama` (local VLM), `opencv` (faces only, `pip install .[vision]`), `none` (images quarantined). |
| `TE_OLLAMA_URL` / `TE_VISION_MODEL` | `http://127.0.0.1:11434` / `qwen2.5vl:7b` | Local vision model. |
| `TE_LLM_PROVIDER` | `none` | Escalation tier: `none`, `ollama`, `anthropic`, `openai_compatible`. |
| `TE_LLM_MODEL` | `claude-opus-5-5` | Model for the escalation tier (set a local model name with `ollama`). |
| `TE_LLM_API_KEY` / `TE_LLM_BASE_URL` | empty | Credentials / endpoint of the escalation provider. |
| `TE_LLM_PRICE_INPUT_PER_MTOK` / `..._OUTPUT_...` | `4.0` / `20.0` | Prices used by the budget guard (USD per million tokens). |
| `TE_PILOT_ASSISTANT` | `scripted` | AI-pilot test assistant: `scripted` (reference, identical for everyone) or `llm`. |
| `TE_PILOT_LLM_PROVIDER` / `_MODEL` / `_BASE_URL` / `_API_KEY` | `ollama` / `qwen2.5-coder:7b` | The model candidates pilot when `TE_PILOT_ASSISTANT=llm` (Ollama, vLLM, OpenRouter…). |
| `TE_PILOT_JUDGE` | `true` | Use the escalation provider as LLM judge for AI-pilot tests (bounded to ±15 points). |
| `TE_OWNERSHIP_SOURCE_FILES` | `3` | Source files kept per repository of an application, for the own-code task. |
| `TE_PUBLIC_BASE_URL` | empty | Public URL of the app behind a proxy (e.g. `https://hivey.be/talentengine`); needed for Safe Exam Browser checks and links in ATS notes. |
| `TE_GITHUB_TOKEN` | empty | Raises the GitHub API limit from 60 to 5,000 requests per hour. |
| `TE_ENABLE_DEMO` | `true` | Allows `POST /api/demo/seed`. Set to `false` in production. |

Check the audit ledger at any time: `talentengine verify` (exit code 1 if it was tampered with).

### Accounts and roles

Create one account per person; each gets a personal key, shown once:

```bash
talentengine adduser "Camille Martin" --role recruiter   # or: dpo, admin
talentengine users                                      # list
talentengine deluser "Camille Martin"
```

| Role | Can |
|---|---|
| `recruiter` | job profiles, applications, evaluations, decisions, identity reveal after a decision, explanation links |
| `dpo` | read everything, GDPR exports, erasure, retention sweeps |
| `admin` | everything, plus accounts and demo data |

Every decision, reveal, export and erasure is signed in the audit ledger with the **authenticated
account name** — a recruiter cannot sign with someone else's. Admins can also manage accounts in the
interface. Once named accounts exist, remove the legacy shared `TE_API_KEY`.

Applications whose consented retention period is over are erased automatically every
`TE_RETENTION_SWEEP_HOURS` (24 by default; `talentengine purge` runs a sweep by hand).

---

## Part 2 — The public sandbox (anyone)

`/essai` (FR) or `/try` (EN) needs no account and stores nothing. Three steps:

1. **The job** — search the 47 reference roles ("IA engineer", "data", "UX", "rénovation"…), or paste an
   offer's text or its link (LinkedIn job links, Welcome to the Jungle, Indeed,
   career pages with structured data), The detected criteria are editable:
   importance, required level, add or remove a skill; "why?" shows the offer lines behind each one.
2. **Your profile** — CV (PDF, Word, Markdown, text), your **LinkedIn profile as PDF** (LinkedIn →
   your profile → More → Save to PDF: it often lists experience your CV leaves out), **diplomas** and
   **certifications** (marked "document provided"), other documents (up to 10 per category), GitHub links
   (a profile link analyses **all** your public repositories and how they work together), up to 3
   portfolio links, your name (only used to hide it), and consent.
3. **The result** — score, what your material proves, what to strengthen, the questions a recruiter
   could ask you.

After the result, two optional tests are offered: the **verification test** (questions, including some on
your own work) and the **AI-pilot test** — you pilot an AI assistant that makes deliberate mistakes through
a short mission, then, if you gave GitHub links, get five minutes to change one of your own functions. At
the end you see your scores and which flaws the assistant planted. Your CV analysis is never stored; a
test in progress is kept encrypted for at most 3 hours so that a server update does not interrupt it.

Limits per visitor and per hour are set by `TE_SANDBOX_MATCHES_PER_HOUR` and `TE_SANDBOX_OFFERS_PER_HOUR`;
`TE_SANDBOX_ENABLED=false` turns the sandbox off.

## Part 3 — Daily use (recruiter)

### 1. Describe what the role really needs

**New job profile** opens the configuration studio. Start from a preset (DevSecOps, full-stack,
UI/UX, growth marketing, account executive, joiner, chef de partie, dressmaker) or from scratch.

* **Criteria** — pick skills from the catalogue. For each one:
  * *Importance*: **essential**, **important** or **bonus** (counts ×3, ×2, ×1);
  * *Weight*: fine-tuning on top of the importance;
  * *Required level* (0–4): the level at which the criterion is fully met
    (Emerging → Developing → Proficient → Advanced → Expert);
  * *Axis focus* (optional): for this criterion only, what matters most;
  * *Note*: your own words, shown in the report.
* **Axes** — how much the role values **autonomy** (owning work end to end), **technical
  complexity** (difficulty of what was achieved) and **reliability** (tests, checks, measured results).
* **Diplomas and certifications** — *ignore* them or keep them *secondary*, with a weight of at most
  25% (10% by default), and optionally list the ones the role values. They can tip a balance; they
  can never carry it.
* **AI budget** — by default everything runs locally for free. You can allow a cloud model for the
  most evidence-rich candidates only (top 5% by default) and cap the spend for this job.
* **Privacy** — gendered wording neutralised, school names hidden, images without a face detector
  quarantined. Leave these on unless your DPO says otherwise.

Every saved change creates a new version of the profile, recorded in the audit ledger.

### 2. Collect applications

Share the **Add candidate** form or upload on the candidate's behalf (with their consent): CV (PDF,
Word .docx, Markdown or text), documents (reports, case studies), GitHub links, portfolio items with a
short description, and photos of work. The candidate's **name is required**: it is what lets the
system hide it everywhere, whatever the layout of the files. It is stored encrypted and only revealed
after a human decision.

A skill described only in the CV is shown as "to be confirmed": it can reach *Proficient* at most until
a piece of work (repository, document, photo, portfolio item) proves it.

### 3. Run the evaluation

**Run evaluation** analyses every candidate. You get a ranked, anonymous list (`CAND-1A2B3C`). The
list is an order of evidence, **not** a filter: nobody is rejected by the system. Filters in the view
only change what you look at.

### 4. Read a report

* **Compatibility score** — how well the evidence matches *your* criteria, with the split between
  proven skills and credentials.
* **Evidence band** — *strong*, *moderate* or *limited* describes how much tangible material the
  candidate provided, not the person.
* **Proof panel** — each validated skill in plain words ("can run a budget"), with the exact
  document lines, files or images that prove it.
* **To explore in interview** — criteria with no or partial evidence. "No evidence" is not "no
  skill": someone may simply not have shared that work. Skills the candidate *declared* without
  proof are marked.
* **Interview guide** — three questions about the candidate's own work, with what a genuine author
  would say and the warning signs. Tick the key points during the interview.
* **Warnings** — e.g. hidden instructions found in a document (they were excluded from AI analysis),
  or images set aside because no face detector was available.

### 5. Decide — you, not the machine

Record a decision (**shortlist**, **interview**, **hold**, **not retained**) with a short
justification; it is signed with your account name. After a shortlist or interview decision you can
**reveal the identity** to contact the person; this action is logged. **Export as PDF** prints a clean
report for a hiring committee.

### 6. Answer "why did I get this score?"

Send the candidate an **explanation link** (report page): a private page, valid 30 days, showing the
evidence used, the criteria, what is missing, your decision and its rationale, and a proof that the
record has not been altered — with no identifier in it (AI Act Art. 86). The link stops working when
the data is erased.

The **Audit** tab of a report shows every step recorded for that candidate. Requests from candidates
are handled by the DPO role: **Export (GDPR)** downloads everything held about them (Art. 15/20),
**Erase (GDPR)** deletes it and leaves an audit trail that can no longer be linked to them (Art. 17).

### 7. Verify the candidate with a test

From a report, **Verification test** creates a link (level junior / confirmed / senior, 4–25 questions,
questions on the candidate's own work on by default, validity). Send it to the candidate. They see an
information notice (what is monitored, no camera or microphone), then one question at a time with a
server-side timer. You see the score per skill, the verified level, the score on their own work and the
integrity signals; the candidate only sees that the test is complete.

For high-stakes roles, require **Safe Exam Browser** (https://safeexambrowser.org): create an exam
configuration in the SEB configuration tool, copy its *Config Key*, paste it in the test form, and send the
candidate the `.seb` file together with the link. Set `TE_PUBLIC_BASE_URL` (e.g.
`https://hivey.be/talentengine`) when the app runs behind a reverse proxy so the hashes can be verified.

### 7b. Watch the candidate pilot an AI: the AI-pilot test

For software, data, security and infrastructure roles, **AI-pilot test** on the report creates a link
(level, scenario — automatic from the job or chosen —, optionally which flaws, minutes, the own-code task,
validity). The candidate gets a mission and an assistant that is deliberately imperfect; you get intent
precision, critical thinking, orchestration velocity and, if their repositories were provided, the
authenticity of the evidence, each with the quotes it rests on, plus the transcript. During a live
interview you can **arm an extra flaw** from the session's panel and see how they react. The job's
candidate list shows the pilot index and a *verified* figure (0.6 × compatibility + 0.4 × pilot index);
the ranking itself stays on compatibility so that untested candidates are not pushed down.
See [PILOT_TEST.md](PILOT_TEST.md).

### 8. Connect your ATS

**Settings → ATS integrations** (admin): choose Greenhouse, Lever, Ashby or Generic, map ATS jobs to job
profiles, enter the credentials, confirm that your job ads inform candidates, and paste the webhook URL in
the ATS. Notes appear on candidates in your ATS. See [ATS_BRIDGE.md](ATS_BRIDGE.md).

### 9. Compliance and monitoring (DPO, admin)

**Compliance** shows the post-market monitoring figures (score distributions, human decisions departing
from the ranking, test integrity, AI spend, ledger integrity) and records serious incidents with their
legal reporting deadline (15 days, 10 in case of death, 2 for widespread infringements). Read
[AI_ACT_READINESS.md](AI_ACT_READINESS.md) and ship [INSTRUCTIONS_FOR_USE.md](INSTRUCTIONS_FOR_USE.md) with
every deployment.

### 10. Prepare the DPIA

On a job page, **DPIA draft** downloads a Markdown impact assessment pre-filled from that job's
configuration and the running settings (data, masking, credential cap, AI provider, logging, AI Act
deployer duties). Items only your organisation can decide are marked *TO COMPLETE*.

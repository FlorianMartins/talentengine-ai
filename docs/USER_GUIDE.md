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
| `TE_GITHUB_TOKEN` | empty | Raises the GitHub API limit from 60 to 5,000 requests per hour. |
| `TE_ENABLE_DEMO` | `true` | Allows `POST /api/demo/seed`. Set to `false` in production. |

Check the audit ledger at any time: `talentengine verify` (exit code 1 if it was tampered with).

---

## Part 2 — Daily use (recruiter)

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

Record a decision (**shortlist**, **interview**, **hold**, **not retained**) with your name and a
short justification. After a shortlist or interview decision you can **reveal the identity** to
contact the person; this action is logged.

### 6. Answer "why did I get this score?"

The **Audit** tab of a report shows every step recorded for that candidate, the evidence used and the
proof that the record has not been altered. A candidate's request for erasure is handled with
**Erase (GDPR)**: their data is deleted and the remaining audit trail can no longer be linked to them.

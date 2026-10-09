# TalentEngine‑AI — web front-end

The recruiter-facing UI of TalentEngine‑AI: a calm, professional evaluation tool for skills-first hiring.
It ranks **evidence**, never people. Every screen says so, and every decision is made, justified and signed by a human.

![Candidate report](../docs/images/report-dark.png)

## Stack

| | |
|---|---|
| Build | Vite 5, TypeScript (strict, `noUncheckedIndexedAccess`) |
| UI | React 18, `react-router-dom` 6 (BrowserRouter), `lucide-react` icons |
| Styling | Hand-written CSS with design tokens (custom properties). No CSS framework |
| Charts | Hand-drawn: score figure (large number + thin bar), 3-axis radar, level meters, skill graph (inline SVG). No chart library |
| Fonts | Inter (all UI text and headings, tabular numerals for figures), JetBrains Mono (code, file paths, identifiers only). **Self-hosted** via `@fontsource`: the browser makes no third-party requests (privacy-first), and the production CSP (`font-src 'self' data:`, `style-src 'self' 'unsafe-inline'`) would block Google Fonts anyway. System fallbacks are declared |

Runtime dependencies: `react`, `react-dom`, `react-router-dom`, `lucide-react`, two `@fontsource/*` packages. That's all.

## Scripts

```bash
npm install
npm run dev        # Vite dev server on :5173, proxies /api → http://127.0.0.1:8000
npm run build      # tsc --noEmit && vite build → dist/ (assets in dist/assets)
npm run preview    # serve the built app on :4173 (same /api proxy)
npm run typecheck  # tsc --noEmit
npm run lint       # alias of typecheck
```

Point the proxy at another backend with `TE_BACKEND_URL=http://127.0.0.1:8001 npm run dev`.

### Serving under a path prefix

The app can live under a sub-path, e.g. `https://hivey.be/talentengine/` behind Caddy `handle_path /talentengine/*`
(the proxy strips the prefix, so the backend sees `/api/...` and `/essai`):

```bash
VITE_BASE=/talentengine/ npm run build    # default base is "/" (dev server, Docker image at the root)
```

- `vite.config.ts` sets `base` from `VITE_BASE`, so assets, fonts and images are emitted with the prefix, and
  `index.html` uses `%BASE_URL%favicon.svg`.
- The router uses `basename = import.meta.env.BASE_URL`, so in-app links and deep links such as
  `/talentengine/jobs/JOB-x` or `/talentengine/essai` resolve.
- Every API and media URL goes through `API` in `src/api/client.ts` (`BASE_URL + "/api"`). No component writes
  `/api` by hand.

This was verified with a prefix-stripping proxy in front of the backend. All app routes and both public pages
loaded, the sandbox flow ran, and the browser made **no request outside the prefix**.

In production the FastAPI backend serves `frontend/dist` with an SPA fallback. Run `npm run build` **before** starting
the backend: it only mounts `dist/` at startup. The app only calls relative `/api/...` URLs.

Run the backend locally for development:

```bash
cd ../backend && TE_DATA_DIR=/tmp/te-data TE_VISION_DETECTOR=none ../.venv/bin/talentengine serve --port 8000
curl -X POST localhost:8000/api/demo/seed   # or use the "Load demo data" button on the empty overview
```

## Screens

| Route | Screen |
|---|---|
| `/` | **Overview**: roles as cards (family icon, applications, best score, decisions, config version), totals, and a system status strip (vision detector, LLM or "Local only", ledger integrity). The empty state offers **Load demo data** when the server allows it |
| `/jobs/new`, `/jobs/:id/edit` | **Configuration studio**: preset gallery or a blank profile; basics; a searchable criteria builder grouped by family (importance segmented control, weight 0–5, expected level 0–4 with level names, optional per-criterion axis override, recruiter note, reorder/remove, max 40, unique skills); axis weights with a live radar; credential policy (weight hard-capped at `runtime.max_credential_weight`); budget funnel (cloud LLM off by default, with a computed escalation hint); privacy switches; live JSON preview with copy, export, import and apply; validation bar. Saving does a POST, or a PUT that bumps `version` |
| `/jobs/:id` | **Pipeline**: anonymous ranked list (score figure, evidence band, confidence, top skills, evidence and file counts, AI-escalation and warning badges, decision). View-only filters (band, decision, minimum score: *nobody is rejected*), sorting, a **compare mode** (2–3 applications in a side-by-side criteria matrix), the AI budget widget and **Run evaluation** |
| `/jobs/:id/apply` | **Submission form**: drag-and-drop CV and documents, GitHub URLs, portfolio items, captioned images, identity (explained as "used only to mask, then encrypted"), retention days, explicit GDPR consent. On success it shows the pseudonymous reference |
| `/candidates/:ref` | **Report**: header (score figure, skills vs credentials breakdown with applied weights, confidence, evidence band, AI Act notice, warnings). **Summary** tab: criteria matrix, gaps, human decision with reveal identity, credentials, GDPR erasure. **Evidence** tab: validated skill cards (statement, level, mini radar, source, expandable excerpts, redacted image thumbnails), skill graph, pseudonymised files. **Interview** tab: printable guide with a tickable checklist. **Glass box** tab: "Why this score?", score entry hash, escalation details, ledger timeline and chain status |
| `/audit` | **Audit ledger**: paginated table with filters (application ref, role, kind), prev→entry hash chaining, expandable payloads, and a verify-chain banner |
| `/settings` | Theme, language, reviewer name (sent as `X-Actor`), API key (sent as `X-API-Key`, kept in `localStorage`), read-only runtime info |

### Accounts, roles and privacy operations (v0.4)

- **Identity.** On load the app calls `GET /api/me` (and the public `GET /api/health`). The top bar shows who is
  acting: *name · role* for a personal key (`te_…`), "Shared key" for the legacy `TE_API_KEY`, "Open development
  mode" when the server has no key at all, or "Enter my key" when a key is required. Settings shows an identity card
  (role, permissions, role description). The key field is "Your personal key". The free-text reviewer name only
  appears for the shared key or dev mode, because named accounts are signed server-side.
- **Permission gating.** `useAccess()` (`src/lib/prefs.tsx`) exposes `can(permission)`. The `<Gate perm="…">` component
  disables an action and explains in a tooltip (and screen-reader text) which roles may do it. A server `403`
  becomes a "Access denied — required permission: …" toast. Permissions follow the backend: read (everyone),
  write + decide (recruiter, admin), privacy (DPO, admin), admin (admin).
- **Accounts** `/settings/accounts` (admin): list, create (the key is shown **once** in a modal with a copy button
  and a strong warning), delete with confirmation, and the roles explained.
- **Report.** The decision form shows the account name read-only. The action bar has "Explanation link for the
  candidate" (decide → modal with the full `origin + base + /explication/<token>` URL, expiry and copy),
  "Export data (GDPR)" (privacy → `export-<ref>.json`) and "Export as PDF". GDPR erasure needs the privacy permission.
- **PDF export.** `printDoc()` (`src/lib/print.ts`) flags `<html data-print="doc">` so the print stylesheet only shows
  a dedicated report document (`ReportPrintDoc`). That document has a header (job, reference, date, score), the
  criteria table, every skill with its excerpts, gaps, the interview guide with checkboxes, credentials, the
  decision, and a footer with the AI Act notice and the score entry hash. Print always uses the light palette.
  Public pages print themselves; collapsed evidence is forced visible in print.
- **DPIA draft** (job page and studio): downloads the Markdown draft in the role's report language.
- **Audit**: "Run the purge of expired data" (privacy) with a confirmation and a result banner. New ledger kinds
  have FR/EN labels, colours and timeline icons.

### Verification tests, compliance and ATS (v0.5)

> Superseded in v0.6.1 by the technical test below: the sandbox cards and the recruiter creation form of the
> verification test were removed; `/test/:token` and the read-only results of existing sessions remain.

- **Test player** `/test/:token` (also `/en/test/:token`; the UI language follows the session's `locale`). It is
  distraction-free, with no app shell.
  - **Intro**: job, level, number of questions, approximate time, the rules ("one question at a time, no going back,
    the timer runs on the server"), exactly what is recorded, "no camera or microphone", and the full candidate
    information notice. "Commencer" asks for full screen.
  - **Questions**: single, multi, numeric (comma decimals) and order (drag and drop *or* up/down buttons). The
    countdown is driven by the server's `remaining`; at 0 the client posts `/timeout` and loads the next question.
    Reloading resumes the same question with the server's remaining time.
  - **End**: the sandbox shows results (overall, verified level per skill, authorship %, integrity, per-question
    table, no correct answers). A candidate link only shows "Merci, vos réponses ont été transmises".
- **Anti-cheat layer** (`src/lib/integrity.ts`). Everything is a signal journalled to `/events` (batched every 3 s,
  `sendBeacon` on page hide); nothing blocks the candidate from finishing.
  - **Blocked and recorded**: paste, copy, cut, external drops, the context menu, text selection, Ctrl/Cmd +
    C/V/X/A/P/S/U, F12 and devtools shortcuts.
  - **PrintScreen and macOS capture shortcuts**: recorded, the question is veiled for 2 s and the clipboard is cleared.
  - **Window blur or hidden tab**: the question is blurred behind "Revenez sur le test — l'absence est enregistrée".
  - **Leaving full screen**: recorded, with a banner offering to go back.
  - **Other signals**: multiple screens (`screen.isExtended`) and window resizes, except those caused by entering or
    leaving full screen.
  - **Watermark**: a dynamic, drifting watermark (session id + live clock) is drawn over the question.
  - **Printing**: shows only "Impression désactivée".
  - **Privacy**: no camera, microphone or screen-capture permission is ever requested.
- **Safe Exam Browser**: when `seb_required` and SEB's JavaScript API is present, every `/api/assess` call carries
  `X-SEB-Page-Url` and `X-SEB-Config-Key-Hash` (after `SafeExamBrowser.security.updateKeys`). Outside SEB, the page
  explains how to get it instead of showing questions.
- **Sandbox entry points**:
  - On the result step, "Prouvez que vous maîtrisez" starts a test with the match's `assessment_seed`, which adds
    questions about the visitor's own work.
  - On step 1, a test can be started directly on a typical role (or an analysed offer).
- **Report**: a "Test de vérification" panel and an explanation-links panel.
  - The test panel creates a link (level, 4–25 questions, questions on the candidate's own work, optional Safe Exam
    Browser config keys, validity) and lists results with the integrity panel: "signal à examiner, jamais un motif
    de rejet automatique". Results are also in the PDF.
  - The explanation-links panel lists links and lets you revoke them.
- **Compliance** `/compliance` (DPO, admin): KPIs, human oversight (including decisions departing from the ranking,
  explained as proof of oversight), evidence-band and integrity-risk distributions, a min/median/max score range
  per role, an incident form with the legal reporting deadline, and documentation links.
- **ATS integrations** `/settings/integrations` (admin): Greenhouse, Lever, Ashby and generic webhook.
  - Each connection has a job mapping, per-provider secrets, a required candidate-notice confirmation, notes and an
    explanation-link validity.
  - The webhook URL (`origin + base + /api/integrations/{id}/webhook`) and the one-time generated secret are shown at
    creation; the page also has a how-to per provider.
- **Other changes**: the candidate information notice (short + "learn more") is shown on the Apply page and on the
  sandbox profile step. A 403 uses the `X-Required-Permission` header. Apply limits come from
  `runtime.upload_limits`.

### AI-pilot test (v0.6)

AI on a phone next to the screen cannot be blocked, so this test does not try. The candidate **pilots** an internal
AI assistant to deliver a mission (secure an LLM gateway, a pseudonymised banking export, a production container).
The assistant is deliberately imperfect and quietly plants subtle flaws (OWASP LLM, personal data in logs, unkeyed
hash, root container, `docker.sock`). The candidate is told that reviewing it is part of the test, never which
flaws or when. There is **no anti-cheat layer**: copy and paste and any external tool are allowed ("ce qui est
mesuré, c'est la direction que vous donnez").

- **Player** `/pilote/:token` (also `/en/pilote/:token`; the UI language follows the session's `locale`), no app
  shell, `pages/PilotPlayer.tsx`.
  - **Brief**: mission title and brief, level, time budget, the own-code step if any, the rules, what is recorded
    (instructions, edits, CI runs, timings), "no camera or microphone", the server's notice, an "I understand"
    checkbox and **Commencer**. A `warning` from `/api/pilot/start` (unreadable GitHub profile…) is shown here.
  - **Build**: an IDE-like screen. Left, the chat with the assistant (prompts, replies with "files changed" chips
    and +/− lines that open the file, edits, CI runs and phase markers; `role="log"`), a composer with a 4,000
    character counter and Ctrl/Cmd + Enter. Centre, the file tree (last-change badges, new file, delete) and a
    monospace editor with line numbers (save with the button or Ctrl/Cmd + S; unsaved and "the assistant changed
    this file meanwhile" states; ligatures off so `->` stays `->`). Right, the virtual CI ("Lancer la CI", checks
    with pass/fail and detail, run history). Below 1100 px the three panels become tabs (Assistant / Code / CI).
  - **Clock**: the server keeps time (`build_remaining`, `ownership_remaining`). The countdown turns amber under
    2 minutes with a banner and screen-reader announcements; at 0 the client re-reads the state and follows the new
    phase. Reloading resumes with the server's remaining time. A 409 (time over, turn limit) re-reads the state.
  - **Finish the mission** asks for confirmation, then goes to the own-code intro if the session has one, or closes.
  - **Own code** (optional): an intro ("a function from your own repository, 5 minutes, a new constraint") with the
    constraint and `function() in path`; "Revenir à la mission" stays possible until the step starts. Then the same
    workspace with the instruction pinned on top, the function's lines highlighted (`start_line`–`end_line`) and a
    5-minute clock.
  - **End**: the sandbox shows the full report (flaws revealed as a learning moment); a candidate link only shows
    a thank-you screen, never the evaluation.
- **Report** `components/PilotReportView.tsx` (sandbox and recruiter): pilot-index and authenticity score figures,
  "signal pour l'entretien, jamais un motif de rejet automatique", one card per metric (final %, factual %, the
  judge's proposal and whether it was applied, "bounded to ±15 pts", breakdown bars, evidence with turn links that
  open and highlight the turn in the transcript), the flaws table (title, category + CWE, turn it appeared,
  spotted? how, fixed at the end, injection method), velocity facts, own-code facts (band: knows their code /
  partial / navigates blind / not taken, names from the rest of the repository used, explain requests…), limits,
  notice and the collapsible transcript. The backend's evidence notes, limits and phase markers are fixed English
  templates: the known ones are localised client-side, anything else is shown as is.
- **Sandbox**: on `/essai` step 1 "Ou passez directement le Test du Pilote d'IA" (role, level, mission auto or
  chosen, optional GitHub link), and on the result step a "Test du Pilote d'IA" card next to "Prouvez que vous
  maîtrisez" that reuses the GitHub links of step 2 for the own-code task. A 422 "no scenario fits" and a 429 get
  plain-language messages.
- **Recruiter report**: a "Test du Pilote d'IA" panel under the verification test (`pages/ReportPilot.tsx`):
  create a link (level, mission auto or chosen, flaws to plant when a mission is chosen, mission length 10–90 min,
  own-code task, validity) → full URL with the base path and copy; sessions with their phase and flaws; for running
  sessions **Arm a flaw** (live interviews; journalled, the candidate is not told); the report when closed, the
  transcript otherwise. The pilot results are also in the PDF document.
- **Pipeline**: a "Pilote 70 % · Vérifié 32 %" chip when a candidate has a closed session, with a tooltip: verified
  = 0.6 × compatibility + 0.4 × pilot index, display only; the ranking stays on compatibility.
- **Landing** `/recruteurs`: a "Le Test du Pilote d'IA" section (why, what the person does, guarantees).

### Technical test (v0.6.1): one test, like real work

The closed-book verification test with anti-cheat contradicted real work, where people use a calculator, the
internet and AI. The recruitment technical test is now **one** session of the `/api/pilot/*` API, in three sections:

1. **Knowledge**: situational questions and calculations, one at a time, each with a server clock. Calculator and
   internet allowed, **nothing blocked or monitored** (no integrity layer, no paste blocking, no watermark, no full
   screen). The built-in assistant is not available (the API answers 409). Questions on the candidate's own work
   (from the sandbox match's `assessment_seed`, or the recruiter's "own work" toggle) are in this section.
2. **With the AI**: the built-in assistant sits next to each question and answers when asked. It is deliberately
   wrong on about half of them and, when challenged, admits it only one time in two.
3. **Practice**: the AI-pilot mission (below), then the optional 5-minute own-code task. A role with no mission
   (chef, sales…) gets sections 1–2 only (`scenario: null`).

- **Player** `/pilote/:token` (`pages/PilotPlayer.tsx`).
  - **Brief**: the sections with their counts and time (section 3 and the mission only when there is one), the
    rules (tools allowed, nothing blocked, the assistant is available in sections 2 and 3 and is deliberately
    imperfect, you are responsible for your answers), what is recorded, no camera or microphone.
  - **Questions**: a question card (inputs shared with the legacy player in `components/QuestionInputs.tsx`:
    single, multi, numeric with comma decimals, order with drag and drop or buttons), progress
    "Section 1 · question 2/6", a circular countdown driven by the server's `remaining` (`role="timer"`,
    announcements at 30 s and 10 s). At 0 the client posts `/question/timeout`; a reload resumes the same question
    with the server's time.
  - **Section 2**: the assistant panel next to the question (transcript filtered to that question, composer,
    `role="log"` with `aria-live`), with "L'assistant peut se tromper". Below 900 px, *Question* / *Assistant* tabs
    (question first, a dot announces a new reply).
  - **Transitions**: an interstitial between sections 1 → 2 (shown once per session, before the next question's
    clock starts) and 2 → 3 (mission brief, the mission clock already runs: see limits).
- **Report** (`components/PilotReportView.tsx`): overall score figure, a **Sections** summary (Knowledge %, With the AI %,
  Practice = weighted mean of the steering metrics or "no mission", Own code / authenticity with the own-work
  questions %), the `applied_knowledge` metric card, an **Use of the AI** panel (plain sentences from `ai_usage`,
  "points to discuss, not a score") and a **questions table** (section, skill, result, time used / allowed,
  assistant consulted, assistant wrong on purpose — revealed after the test —, followed or not, challenged).
  Metric weights are shown renormalised over the metrics present; `velocity` and the mission may be null (the
  flaws, velocity and own-code boxes are then hidden). The new English evidence notes and limit are localised.
- **Sandbox**: one card, "Passer le test technique" (`components/StartTechTestCard.tsx`), on step 1 and on the
  result step: level, questions per section (section 1: 0/4/6/10, section 2: 0/2/4/6), mission automatic / none /
  chosen, GitHub links for the own-code task, and the match's `assessment_seed` as `seed` from the result step.
- **Recruiter report**: one **Test technique** panel (`pages/ReportPilot.tsx`): level, section 1 and 2 question
  counts (0–20), own-work questions toggle, mission (automatic, "Aucune mission (questions seules)" = `"none"`, or
  a scenario, with flaws and length), own-code task, validity. The verification-test creation form is gone;
  existing verification sessions are still listed read-only as "Ancien format (sans outils)". The PDF document
  and the pipeline chip ("Test technique 53 % · Vérifié 25 %") follow.
- **Landing**: the "Filtrer les imposteurs" and "Test du Pilote d'IA" sections became one, "Un test technique
  comme au travail" (three sections, tools allowed, the assistant is wrong on purpose, what you get, and the honest
  note that the interview checks the reasoning).
- The legacy `/test/:token` player stays for links already sent.
- Strings: `src/i18n.techtest.ts` (`t.tt`).

### Public pages (no app shell, no API key)

| Route | Screen |
|---|---|
| `/essai` (FR), `/try` (EN) | **Public sandbox**, the shareable showcase for candidates. A three-step stepper: **1. The role**: paste an offer (text, or a link to LinkedIn, Welcome to the Jungle, Indeed or a careers page) → `POST /api/try/offer`, then edit the detected criteria (importance, expected level, add from the catalogue, remove, "why?" shows the offer lines that triggered each skill); or pick a typical role (`/api/try/config` presets). **2. Your profile**: CV and documents (drag and drop), GitHub links (a profile link expands to its 3 latest repositories), portfolio links, the required name (only used to mask it), and plain-language consent. **3. Result**: `POST /api/try/match`, with staged progress while it runs. Shows the score figure, a notice reframed for candidates ("not a verdict on you"), criterion bars, what the files prove (exact excerpts), things to strengthen (tips + gaps), questions a recruiter might ask (self-check list), what was analysed (masked items, repository files, injection flag) and credentials in a secondary panel. Actions: try another offer, edit my profile (inputs kept in memory), copy the tool's link (the canonical `/essai` URL: there is no stored result to share). Handles 422 (with a "paste the text instead" hint), 429 and 503 |
| `/explication/:token` (FR), `/explanation/:token` (EN) | **Candidate explanation** (AI Act Art. 86), reached through a link a recruiter creates. Shows the job, score figure, skills vs credentials split, criterion bars, what the material proves (statements + exact excerpts), gaps phrased for the candidate, the human decision and rationale, an integrity block (ledger intact, score entry hash, dates, versions) explained in plain words, the expiry date, "How to contest?", a CTA to the sandbox and "Download as PDF". Invalid or expired tokens get a friendly 404 page |
| `/recruteurs` (FR), `/recruiters` (EN) | **Recruiter landing**: hero with two CTAs, the problem, how it works in 4 steps, what you get (with theme-aware screenshots), "Measured, not promised" (only figures published in `docs/MEASUREMENTS.md`), compliance, FAQ, final CTA |

**Document categories** (sandbox step 2 and the recruiter Apply page, `components/DocumentZones.tsx`): CV,
**LinkedIn profile** (PDF, with a how-to and the note that it is a self-description), **diplomas** and
**certifications** (shown as "document provided" in reports), and **other documents**. Each category accepts files
incrementally, up to `limits.max_documents`, and each file can be removed. A GitHub **profile** link analyses all
public repositories; the progress steps say so. Repositories are blind-labelled `repo-1…N` and the UI explains why.
Evidence made of comma-separated tool lists renders as chips, and cross-repository locators (`… → repo-12`) are
highlighted.

**Reference roles** (`components/PresetPicker.tsx`, used by the sandbox and the studio): the 47 presets come with
instant search (`lib/presetSearch.ts`, the backend rule: accent/case-insensitive, every word must match, words of
≤ 2 letters whole-word, longer words prefix, title hits first), family chips with counts, and an empty state that
offers to paste an offer instead.

The EN aliases open in English unless the visitor already picked a language. Both pages are lazy-loaded chunks
(the sandbox is about 8 kB gzipped on top of the shared core), so a candidate opening the shared link does not
download the recruiter app pages. The app sidebar links to both.

## Structure

```
src/
  main.tsx              fonts + global CSS + <App/>
  App.tsx               providers + routes
  i18n.ts               typed FR/EN dictionary (`en` must match `fr` key-for-key)
  i18n.pilot.ts         FR/EN strings of the AI-pilot test (t.pilot)
  i18n.techtest.ts      FR/EN strings of the technical test sections, report, sandbox, panel, landing (t.tt)
  api/
    types.ts            types mirroring the FastAPI contract
    client.ts           typed fetch client: X-API-Key / X-Actor headers, FastAPI {detail} → ApiError
  lib/
    prefs.tsx           contexts: preferences (theme, lang, reviewer, key), toasts, runtime+ledger status; useAsync
    storage.ts          guarded localStorage (keys prefixed "te.")
    format.ts           number, date, hash and level helpers (same level thresholds as the backend)
  components/
    Shell.tsx           sidebar (collapsible) / mobile bottom bar, top bar with breadcrumb, language + theme toggles, logo
    charts.tsx          ScoreRing, Radar, Meter, SkillGraphView (deterministic circle layout)
    controls.tsx        Segmented (radio group), RangeField, SwitchRow, TagInput, DropZone
    feedback.tsx        toasts, Modal (focus trap, Esc), skeletons, empty/error states, semantic chips
    StatusStrip.tsx
  components/PublicLayout.tsx  header/footer for the public pages (no sidebar), localised public paths
  components/DocumentZones.tsx upload zones by category (CV, LinkedIn, diplomas, certifications, other documents)
  components/PresetPicker.tsx  searchable gallery of the 47 reference roles
  components/DpiaButton.tsx    DPIA draft download
  lib/print.ts          printDoc() / printPage() for PDF export
  lib/integrity.ts      anti-cheat layer of the test player (signals → /events)
  components/AssessResultsView.tsx  test results + integrity panel (sandbox and recruiter)
  components/CandidateNotice.tsx    candidate information notice
  components/PilotReportView.tsx    AI-pilot report (sandbox and recruiter)
  components/PilotTurns.tsx         one transcript turn (chat + transcripts), localised server markers
  components/StartTechTestCard.tsx  starts the sandbox technical test (POST /api/pilot/start)
  components/QuestionInputs.tsx     timed-question inputs + timer, shared by both players
  lib/presetSearch.ts   client-side preset search (same rule as the backend)
  pages/                Overview, Studio, Pipeline, Apply, Report (+ ReportSections), Audit, Settings, NotFound,
                        Try (public sandbox), Recruiters (public landing), Explanation (candidate view),
                        Accounts (admin), ReportExtras (report actions + print document),
                        TestPlayer, ReportVerification, Compliance, Integrations,
                        PilotPlayer, ReportPilot (v0.6)
  assets/landing/       compressed WebP screenshots used by the landing page
  styles/
    tokens.css          design tokens, dark (default) + light
    app.css             base, layout, components, pages, reduced motion, print
```

## Design tokens

Art direction (v0.10 redesign): a **professional evaluation / HR tool**, not a "mission control". References:
Greenhouse, Ashby, Lever, Workday Recruiting, Linear's restraint, Stripe Dashboard's clarity. Calm, trustworthy,
dense but readable — something a recruiter, a DPO and a candidate all take seriously. Everything in
`styles/app.css` reads from custom properties defined in `styles/tokens.css`; pages do not hard-code colours.

**Themes.** Light is the default. Dark is an option (Settings or the top-bar toggle), equally sober: neutral greys,
no navy, no neon. The theme is the `data-theme` attribute on `<html>`, applied before first paint by
`public/theme-init.js` (external file: the CSP forbids inline scripts). Migration: only an explicit stored choice
(`te.theme = "dark"`) keeps dark; anyone who never chose gets light. Print always uses black on white.

**Palette** (light / dark):

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F5F6F8` | `#111214` | page |
| `--surface` | `#FFFFFF` | `#18191C` | cards, panels, bars |
| `--surface-2` / `-3` | `#F8F9FB` / `#ECEEF2` | `#1E1F23` / `#2A2C31` | table heads, wells / tracks, hover |
| `--border` / `-strong` | `#E3E6EB` / `#CFD4DC` | `#2C2E33` / `#3D4047` | 1px hairlines |
| `--text` | `#0F172A` (16.5:1) | `#EDEEF0` (16.1:1) | body |
| `--text-2` | `#475569` (7.6:1) | `#B4B7BE` (8.8:1) | secondary |
| `--text-3` | `#5B6576` (5.4:1 on bg) | `#8E929A` (5.6:1) | captions, hints |
| `--accent` | `#2F5BDA` (white text 5.8:1) | `#3560DD` (white text 5.4:1) | **the only brand colour**: primary buttons, focus, selection, data bars |
| `--accent-text` | `#2648B8` (7.2:1) | `#8AA6F7` (7.4:1) | links, active navigation |
| `--ok-text` / `--ok-soft` | `#166534` / `#ECFDF3` (6.8:1) | `#7FCF9F` (9.5:1) | demonstrated, strong evidence |
| `--warn-text` / `--warn-soft` | `#92400E` / `#FFF7E6` (6.7:1) | `#E8BD6C` (10:1) | partial, signals to review |
| `--danger-text` / `--danger-soft` | `#B91C1C` / `#FEF2F2` (5.9:1) | `#F0A19B` (8.6:1) | destructive actions only |
| `--neutral-*` | slate `#475569` / `#F1F5F9` | `#B4B7BE` | "not evidenced" — a missing proof is never shown as a failure |

Contrast ratios are WCAG 2.x, measured on the surface the token is used on; every text pair is AA (≥ 4.5:1).
Brand ink blue was chosen over teal because it reads as "institutional" and keeps AA with white text without a
second, darker button shade. The former violet tokens (`--violet*`) are kept as names only and now map to a quiet
slate: they still separate "AI / own work" items, but without a second hue. Colour only encodes meaning
(good / warn / bad), always next to a text label.

**Type.** Inter for everything (400/500/600), 14px body, page titles 24px, hero figures up to 48px with
`tabular-nums`. Headings use weight 600 and slight negative tracking; no uppercase letter-spaced eyebrows (eyebrows
are 13px, sentence case, `--text-3`). Monospace only for code, paths, hashes and pseudonymous references.

**Shape and space.** Radii `--radius-xs` 4px (badges), `--radius-sm` 6px (controls), `--radius` / `--radius-lg`
8px (cards, panels); pills only for switches and dots. 1px borders, flat surfaces: `--shadow` is `none`;
`--shadow-md` / `--shadow-lg` exist only for floating bars, menus, modals and toasts. Spacing scale 4 / 8 / 12 /
16 / 20 / 28 / 40 / 56px (`--sp-1`…`--sp-8`). Controls are 36px high (28px small, 40px large).

**Data viz.** `ScoreFigure` (`components/charts.tsx`) replaces the former rings: a plain large number, its caption
and a thin horizontal bar (`lg` report headers, `md` secondary results, `sm` list rows and tables). Meters are 6px
bars with a "required level" tick. No glows, gradients or animated fills.

**Motion.** Functional only: 100–150 ms fades for pages, toasts and modals, and spinners for loading. No pulsing,
scanning, glowing or drifting decorations (the exam watermark's drift is an anti-capture measure, not decoration).
`prefers-reduced-motion` reduces all of it to instant.

**Brand.** Wordmark "TalentEngine" in Inter 600 next to a minimal mark: a "T" monogram on an ink-blue 7px-radius
square (`Logo` in `components/Shell.tsx`, same drawing in `public/favicon.svg`).

## i18n

`src/i18n.ts` exports `fr` (default) and `en`. The public pages' copy lives in the same dictionary under `t.pub`. `en` is typed as `typeof fr`, so a missing key or a wrong function
signature is a compile error. Strings with values are functions, e.g. `t.pipeline.evidence(3)`. French copy is
inclusive and neutral ("la personne candidate", "candidat·e", "Non retenu·e"). The UI language also drives the
catalogue and preset language (`?locale=`). Reports are written in the role's own *report language*.

## Accessibility

- Semantic landmarks, a skip link, a breadcrumb `<nav>`, and real `<button>`/`<a>`/`<label>` elements.
- Visible focus rings everywhere.
- Segmented controls are ARIA radio groups with arrow-key support. Report tabs follow the `tablist` pattern with arrow keys.
- Modals trap focus, close on Esc and restore focus.
- Icon-only buttons have `aria-label`s, and charts have `role="img"` with text alternatives. Meters expose `aria-valuenow`.
- `prefers-reduced-motion` reduces the remaining fades (pages, toasts, modals) to instant; nothing else moves.
- Works down to 380px wide with no horizontal page scroll (wide tables scroll inside their own container).
- A print stylesheet produces a clean interview guide.

## Screenshots

Regenerated with the v0.10 design: `report-dark`, `studio-dark`, `pipeline-dark`, `try-result`, `recruiters`,
`techtest-*`, `compliance`, `integrations`, `accounts`, `test-intro`, and the landing images in
`src/assets/landing/`. The others below still show the previous visual design.

See `../docs/images/`: `overview-{dark,light}`, `studio-dark`, `studio-full-dark`, `pipeline-{dark,light}`,
`compare-dark`, `report-{dark,light}`, `report-evidence-dark`, `report-interview-light`, `report-glassbox-dark`,
`audit-dark`, `settings-light-en`, `mobile-{overview,report,pipeline-light}`, and for the public pages `try-offer`,
`try-progress`, `try-result`, `try-result-mobile`, `try-presets-mobile`, `recruiters`, `recruiters-light`,
`recruiters-mobile`; v0.4: `accounts`, `accounts-key`, `explanation-link-modal`, `explanation-public`,
`explanation-public-light`, `explanation-public-mobile`, `report-print` (print-emulated), `try-result-print`,
`audit-retention`, `try-presets-search`, `try-documents`, `try-result-github-profile`, `evidence-orchestration`,
`apply-categories`; v0.5: `test-intro`, `test-question`, `test-question-mobile`, `test-blurred`, `test-results`,
`test-print-blocked`, `report-verification`, `report-print-verification`, `compliance`, `integrations`; v0.6:
`pilot-brief`, `pilot-build`, `pilot-build-mobile`, `pilot-ci`, `pilot-ownership`, `pilot-report`, `report-pilot`;
v0.6.1: `techtest-brief`, `techtest-question`, `techtest-question-ai`, `techtest-question-ai-mobile`,
`techtest-report`, `report-techtest` (and `recruiters`, `recruiters-mobile` refreshed).

# TalentEngine‑AI — web front-end

The recruiter-facing UI of TalentEngine‑AI: a calm "mission control" for skills-first hiring.
It ranks **evidence**, never people. Every screen says so, and every decision is made, justified and signed by a human.

![Candidate report](../docs/images/report-dark.png)

## Stack

| | |
|---|---|
| Build | Vite 5, TypeScript (strict, `noUncheckedIndexedAccess`) |
| UI | React 18, `react-router-dom` 6 (BrowserRouter), `lucide-react` icons |
| Styling | Hand-written CSS with design tokens (custom properties). No CSS framework |
| Charts | Inline SVG drawn by hand (score ring, 3-axis radar, level meters, skill graph). No chart library |
| Fonts | Space Grotesk (headings), Inter (text), JetBrains Mono (data/hashes). **Self-hosted** via `@fontsource`, so the browser makes no third-party requests (this is a privacy-first product). System fallbacks are declared |

Runtime dependencies: `react`, `react-dom`, `react-router-dom`, `lucide-react`, three `@fontsource/*` packages. That's all.

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
| `/jobs/:id` | **Pipeline**: anonymous ranked list (score ring, evidence band, confidence, top skills, evidence and file counts, AI-escalation and warning badges, decision). View-only filters (band, decision, minimum score: *nobody is rejected*), sorting, a **compare mode** (2–3 applications in a side-by-side criteria matrix), the AI budget widget and **Run evaluation** |
| `/jobs/:id/apply` | **Submission form**: drag-and-drop CV and documents, GitHub URLs, portfolio items, captioned images, identity (explained as "used only to mask, then encrypted"), retention days, explicit GDPR consent. On success it shows the pseudonymous reference |
| `/candidates/:ref` | **Report**: hero (score ring, skills vs credentials breakdown with applied weights, confidence, evidence band, AI Act notice, warnings). **Summary** tab: criteria matrix, gaps, human decision with reveal identity, credentials, GDPR erasure. **Evidence** tab: validated skill cards (statement, level, mini radar, source, expandable excerpts, redacted image thumbnails), skill graph, pseudonymised files. **Interview** tab: printable guide with a tickable checklist. **Glass box** tab: "Why this score?", score entry hash, escalation details, ledger timeline and chain status |
| `/audit` | **Audit ledger**: paginated table with filters (application ref, role, kind), prev→entry hash chaining, expandable payloads, and a verify-chain banner |
| `/settings` | Theme, language, reviewer name (sent as `X-Actor`), API key (sent as `X-API-Key`, kept in `localStorage`), read-only runtime info |

### Public pages (no app shell, no API key)

| Route | Screen |
|---|---|
| `/essai` (FR), `/try` (EN) | **Public sandbox**, the shareable showcase for candidates. A three-step stepper: **1. The role**: paste an offer (text, or a link to LinkedIn, Welcome to the Jungle, Indeed or a careers page) → `POST /api/try/offer`, then edit the detected criteria (importance, expected level, add from the catalogue, remove, "why?" shows the offer lines that triggered each skill); or pick a typical role (`/api/try/config` presets). **2. Your profile**: CV and documents (drag and drop), GitHub links (a profile link expands to its 3 latest repositories), portfolio links, the required name (only used to mask it), and plain-language consent. **3. Result**: `POST /api/try/match`, with staged progress while it runs. Shows the animated score ring, a notice reframed for candidates ("not a verdict on you"), criterion bars, what the files prove (exact excerpts), things to strengthen (tips + gaps), questions a recruiter might ask (self-check list), what was analysed (masked items, repository files, injection flag) and credentials in a secondary panel. Actions: try another offer, edit my profile (inputs kept in memory), copy the tool's link (the canonical `/essai` URL: there is no stored result to share). Handles 422 (with a "paste the text instead" hint), 429 and 503 |
| `/recruteurs` (FR), `/recruiters` (EN) | **Recruiter landing**: hero with two CTAs, the problem, how it works in 4 steps, what you get (with theme-aware screenshots), "Measured, not promised" (only figures published in `docs/MEASUREMENTS.md`), compliance, FAQ, final CTA |

The EN aliases open in English unless the visitor already picked a language. Both pages are lazy-loaded chunks
(the sandbox is about 8 kB gzipped on top of the shared core), so a candidate opening the shared link does not
download the recruiter app pages. The app sidebar links to both.

## Structure

```
src/
  main.tsx              fonts + global CSS + <App/>
  App.tsx               providers + routes
  i18n.ts               typed FR/EN dictionary (`en` must match `fr` key-for-key)
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
  pages/                Overview, Studio, Pipeline, Apply, Report (+ ReportSections), Audit, Settings, NotFound,
                        Try (public sandbox), Recruiters (public landing)
  assets/landing/       compressed WebP screenshots used by the landing page
  styles/
    tokens.css          design tokens, dark (default) + light
    app.css             base, layout, components, pages, reduced motion, print
```

## Design tokens

Everything in `styles/app.css` reads from custom properties defined in `styles/tokens.css`:

- **Surfaces**: `--bg`, `--bg-elev`, `--surface`, `--surface-2`, `--surface-3`, `--surface-glass`, plus hairlines `--border` and `--border-strong`.
- **Text**: `--text`, `--text-2`, `--text-3`. All meet WCAG AA on their surfaces in both themes.
- **Accent**: `--accent` (electric cyan, used for fills and strokes) and `--accent-text` (a tone tuned for text contrast). `--violet` is the sparing secondary for data such as AI escalation, human decisions and "important".
- **Status**: `--ok` (demonstrated, strong evidence), `--warn` (partial, warnings) and `--neutral` (slate) for "not evidenced". Red (`--danger`) is reserved for destructive actions. A missing proof is never presented as a failure of the person.
- **Scale**: 8px spacing grid (`--sp-1`…`--sp-8`), radii 8/12/14px, type scale `--fs-xs`…`--fs-3xl`.

The theme is the `data-theme` attribute on `<html>`, set before first paint by a tiny inline script in `index.html` to
avoid a flash. Dark is the default. The faint grid and scanline texture is used on `.hero` blocks only.

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
- `prefers-reduced-motion` disables the ring and bar fills, skeleton shimmer, toasts and page transitions.
- Works down to 380px wide with no horizontal page scroll (wide tables scroll inside their own container).
- A print stylesheet produces a clean interview guide.

## Screenshots

See `../docs/images/`: `overview-{dark,light}`, `studio-dark`, `studio-full-dark`, `pipeline-{dark,light}`,
`compare-dark`, `report-{dark,light}`, `report-evidence-dark`, `report-interview-light`, `report-glassbox-dark`,
`audit-dark`, `settings-light-en`, `mobile-{overview,report,pipeline-light}`, and for the public pages `try-offer`,
`try-progress`, `try-result`, `try-result-mobile`, `try-presets-mobile`, `recruiters`, `recruiters-light`,
`recruiters-mobile`.

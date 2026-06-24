# Plan — Reyanda product unification (OCS-aligned)  [ACTIVE]

## Goal
One coherent suite under `reyanda.github.io`: single sign-in landing, products sharing the
Open Canvas Studio (OCS) look-and-feel + a unified header, logout-to-home everywhere, one
shared settings pane, one admin console (OCS *and* Shrimp users), and the Systematic Review
pipeline as its own product.

## Repos
- `Reyanda/reyanda.github.io` — landing launcher (single sign-in; only index.html).
- `Reyanda/resource-shrimp` — Shrimp (this repo): Python→Render; static→Pages `docs/`.
- `Reyanda/open-canvas-studio` — OCS React/Vite (Pages) + Fastify server (Render) + Neon PG.
- `Reyanda/open-canvas-studio-data` — user registry / analytics (admin store).

## Shared contract (true today)
Both products gate on `localStorage['reyanda_user']`, redirect to `/` when absent.
`window.signOut()` clears it → `/`. Launcher is the canonical login.

## OCS "feel" (src/styles/foundation/tokens.css + materials.css), dark = deployed default
ink `#f5f5f7 / #c7c7cc / #8e8e93`; `--glass-fill-rgb 28 28 30`; neutral accent `#A1A1A6`;
navy ambient `#0b1220`; radii 26/20/12/pill; topbar 76px; glass blur20 saturate180; Inter.
Logout sits in a right-aligned account menu in the glass TopBar.

## Slices (ship + browser-verify each before next)
1. DONE — Landing = research toolkit; 3 tiles (Shrimp/Systematic Review/OCS); SR `#review`
   deep-link; unified sign-out→home in Shrimp (docs + templates).
2. IN PROGRESS — Shrimp chrome → OCS feel: remap dark palette to OCS navy/ink glass; align
   header; drop stale marketing hero. CSS-variable remap only (no DOM rewrite), verify live.
3. OCS logout→home: `src/lib/auth.ts logout()` also clears reyanda_user + `location.assign('/')`.
   Needs npm build + Pages redeploy.
4. Shared settings pane mirroring OCS `SettingsPanel.tsx` tabs (Appearance/AI keys/Storage/
   Account); apply in Shrimp; OCS stays source of truth.
5. Systematic Review = own product: new Pages repo/deploy on same Render backend; move
   `#review` UI out of Shrimp; launcher tile → its own URL.
6. Admin console manages Shrimp users: backend `/console/shrimp-users` (ConsoleUser shape) +
   "Shrimp" section in OCS `ControlPanel.tsx`/`consoleData.ts`; shared user store.

## Validation
Per slice: live browser check (login→tiles, chrome, logout→home); Shrimp `scripts/smoke.py`;
OCS `npm run build` + server `node --test` for slices 3/6.

## Risks / fallback
OCS slices need Vite build + Render redeploy + Neon DB — heavier; do after Shrimp slices.
Reskin must not break Shrimp UI: remap variables only, keep dark default, verify live.

---

# Resource Shrimp — roadmap to a general resource tool

## Done
- **Provider registry** (`providers.py`) — pluggable resource types; `detect`/`by_name`.
  Video + Article wrap existing resolvers; adding a type = one subclass + `register()`.

## Phase A — Persistent library + interrogate (in progress)
Goal: stop deleting files after streaming; keep them in a per-user sandbox the
user can browse, search, re-download, and delete.

- `library.py` — SQLite index (`library/library.db`) + files under `library/<session>/<id>/`.
  - `init`, `persist(job, rid, session, url)`, `list_resources(session, q)`, `get`, `delete`.
- `app.py`:
  - anonymous session via `rs_session` cookie (HttpOnly, SameSite=Lax) — upgradeable to
    Google identity in Phase B.
  - persist completed downloads into the library (no more delete-on-stream).
  - `/api/library` (list + `?q=` search), `/api/delete`, `/api/status` falls back to library,
    `/api/stream/<id>` serves from library (or temp), never deletes.
  - split rate limits: reads 240/min (polling-safe), downloads 20/min.
- Frontend: "Library" nav view — searchable cards with Download/Delete.
- `.gitignore`: `library/`, `*.db`.

Validation: boot, persist a synthetic resource, list/search/stream/delete via HTTP with a
session cookie; confirm existing download dispatch still works.

## Phase B — Identity + Google Drive (next)
Google OAuth = identity + Drive. Sandbox becomes a cache; user's Drive is durable store.
Link existing anonymous session to the Google account on first sign-in.

## Phase C — AI assistant (multi-provider, BYO key)
Per-resource text extraction (video subtitles, paper PDF text — small lib allowed, e.g. pypdf).
Retrieval + chat over the library. Model router across free APIs (Groq, OpenRouter, local
Ollama) with optional user-supplied keys.

## Constraints
- Keep Sci-Hub and all existing sources (user instruction). No new piracy features.
- stdlib-first; targeted small libs allowed where stdlib is impractical (PDF text, etc.).
- Preserve a working app at every step.

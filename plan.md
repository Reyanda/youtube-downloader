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

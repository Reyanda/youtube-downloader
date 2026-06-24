# ⛔ AGENT GROUND RULES — read before you push (every agent, every time)

Resource Shrimp is a research-resource tool: acquire papers/media, store them in a
per-user sandbox (synced to the user's Google Drive), and interrogate them
NotebookLM-style. It is the *intake + synthesis* companion to Open Canvas Studio
(figure *creation*). These are **hard rules, not suggestions.**

---

## HARD RULE 1 — Smoke must pass before you push. Never break `main`.

```bash
python3 scripts/smoke.py     # imports every module, boots the server, hits key endpoints
```

- Never push an `import` without the file it points to. A dangling import breaks boot.
- Never leave `main` red. Incomplete work stays on a feature branch until smoke passes.
- `add` files by explicit path; never blind `git add -A`; never force-push `main`.

## HARD RULE 2 — Stay stdlib-first. Justify every dependency.

The HTTP server is **Python standard library only**. Current allowed runtime deps
(`requirements.txt`): `yt-dlp` (subprocess resolver), `pypdf` (PDF text), `cryptography`
(vault). Adding a dependency requires a one-line justification in the PR and an entry here.
Do not reach for a framework when stdlib suffices.

## HARD RULE 3 — Harmonise with the design system. No emojis, no hardcoded colours.

- All colours come from CSS variables (`--bg`, `--fg`, `--primary`, …). No bespoke hex in
  components. Respect light/dark via `prefers-color-scheme`.
- Icons are **SVG only** (monochrome, `currentColor`). Emojis are banned in the UI.
- Static assets (`.css`/`.js`) are served `no-cache` so deploys are never stale.

## HARD RULE 4 — Security & legal posture.

- Keep SSRF, path-traversal, rate-limit, and CSP guards intact. Validate every user input.
- Lawful open-access routes first (PMC/Europe PMC, open repositories, Unpaywall) before any
  publisher/fallback source. Do not add new piracy automation.
- Secrets (API keys, OAuth tokens, vault) never touch git. `.vault.json`, `library/`, `*.db`
  are gitignored. Never log a key.

## HARD RULE 5 — Storage is Drive-backed; the local sandbox is a cache.

Hosted disks (Render) are **ephemeral** — files vanish on redeploy/restart. Downloads must
sync to the user's Google Drive (`drive_autosync`). Never assume `library/` survives a restart
in production; the SQLite index + Drive are the source of truth.

---

## Module map

| File | Role |
|------|------|
| `app.py` | stdlib HTTP server, security layer, endpoints, resolvers |
| `providers.py` | pluggable resource types (registry) |
| `library.py` | SQLite index: resources, projects, credentials, settings, access, text cache |
| `ai.py` | model router (OpenAI/Anthropic/Groq/OpenRouter/DeepSeek/Ollama) + transcription + extraction |
| `gdrive.py` | Google OAuth + Drive sync |
| `vault.py` | encrypted master-password API-key store |

## Validation

`python3 scripts/smoke.py` is the gate. Add focused checks there when you add a subsystem.
Update `.session.md` before ending a session.

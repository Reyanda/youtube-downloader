#!/usr/bin/env python3
"""Resource Shrimp — persistent library. stdlib only (sqlite3).

Completed downloads are moved out of the ephemeral temp area into a
per-session sandbox under LIBRARY_ROOT and indexed in SQLite, so users
can browse, search, re-download, and delete what they've fetched.

Storage layout:
    library/library.db                  -- metadata index
    library/<session>/<id>/<filename>   -- the file itself

`session` is an opaque per-browser id today (anonymous cookie). In Phase B
it becomes a stable Google account id; the schema does not change.
"""

import json
import mimetypes
import os
import shutil
import sqlite3
import threading
import time

BASE = os.path.dirname(os.path.abspath(__file__))
LIBRARY_ROOT = os.environ.get("LIBRARY_ROOT", os.path.join(BASE, "library"))
DB_PATH = os.path.join(LIBRARY_ROOT, "library.db")

_lock = threading.Lock()
_conn = None

# Job fields worth keeping as resource metadata
_META_FIELDS = ("title", "authors", "doi", "journal", "year",
                "quality", "has_pdf", "pdf_url")


def init():
    """Create the library directory and database. Idempotent."""
    global _conn
    os.makedirs(LIBRARY_ROOT, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id          TEXT PRIMARY KEY,
            session     TEXT NOT NULL,
            provider    TEXT,
            type        TEXT,
            title       TEXT,
            source_url  TEXT,
            filename    TEXT,
            filepath    TEXT,
            size        INTEGER,
            mime        TEXT,
            meta_json   TEXT,
            created_at  INTEGER
        )
    """)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON resources(session)")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS google_auth (
            session       TEXT PRIMARY KEY,
            email         TEXT,
            access_token  TEXT,
            refresh_token TEXT,
            expiry        INTEGER
        )
    """)
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS resource_text (
            id    TEXT PRIMARY KEY,
            text  TEXT
        )
    """)
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            session     TEXT NOT NULL,
            name        TEXT NOT NULL,
            created_at  INTEGER
        )
    """)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_proj_session ON projects(session)")
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_credentials (
            session   TEXT NOT NULL,
            provider  TEXT NOT NULL,
            api_key   TEXT,
            base_url  TEXT,
            model     TEXT,
            label     TEXT,
            PRIMARY KEY (session, provider)
        )
    """)
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            session          TEXT PRIMARY KEY,
            default_provider TEXT,
            default_model    TEXT
        )
    """)
    # Migration: add project_id to resources if an older DB lacks it
    cols = [r["name"] for r in _conn.execute("PRAGMA table_info(resources)").fetchall()]
    if "project_id" not in cols:
        _conn.execute("ALTER TABLE resources ADD COLUMN project_id TEXT")
    _conn.commit()


# ── Google account tokens (Phase B) ─────────────────────────────────
def set_google(session, email, access_token, refresh_token, expiry):
    """Store/refresh a session's Google tokens. Keeps the existing refresh
    token if a refresh response omits one (Google only sends it once)."""
    with _lock:
        if refresh_token is None:
            row = _conn.execute(
                "SELECT refresh_token FROM google_auth WHERE session = ?",
                (session,),
            ).fetchone()
            if row:
                refresh_token = row["refresh_token"]
        _conn.execute(
            "INSERT OR REPLACE INTO google_auth "
            "(session, email, access_token, refresh_token, expiry) "
            "VALUES (?,?,?,?,?)",
            (session, email, access_token, refresh_token, int(expiry)),
        )
        _conn.commit()


def get_google(session):
    with _lock:
        row = _conn.execute(
            "SELECT * FROM google_auth WHERE session = ?", (session,)
        ).fetchone()
    return dict(row) if row else None


def clear_google(session):
    with _lock:
        _conn.execute("DELETE FROM google_auth WHERE session = ?", (session,))
        _conn.commit()


# ── Extracted text cache (Phase C) ──────────────────────────────────
def set_text(rid, text):
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO resource_text (id, text) VALUES (?, ?)",
            (rid, text),
        )
        _conn.commit()


def get_text(session, rid):
    """Cached text for a resource the session owns, or None."""
    with _lock:
        row = _conn.execute(
            "SELECT t.text FROM resource_text t "
            "JOIN resources r ON r.id = t.id "
            "WHERE t.id = ? AND r.session = ?",
            (rid, session),
        ).fetchone()
    return row["text"] if row else None


def _row_to_dict(row):
    d = dict(row)
    try:
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
    except Exception:
        d.pop("meta_json", None)
        d["meta"] = {}
    return d


def _under_root(path):
    """True if path resolves inside LIBRARY_ROOT."""
    real = os.path.realpath(path)
    return real == os.path.realpath(LIBRARY_ROOT) or \
        real.startswith(os.path.realpath(LIBRARY_ROOT) + os.sep)


def persist(job, rid, session, source_url):
    """Move a completed job's file into the library and index it.

    Returns the resource dict, or None if there was nothing to persist.
    Metadata-only results (e.g. a paper found without an OA PDF) are still
    indexed, with filepath = None.
    """
    if not job or job.get("status") != "complete":
        return None

    src = job.get("filepath")
    has_file = bool(src and os.path.isfile(src))
    if not has_file and job.get("type") != "article":
        return None  # nothing downloaded and not a metadata-bearing type

    dest_dir = os.path.join(LIBRARY_ROOT, session, rid)
    os.makedirs(dest_dir, exist_ok=True)

    filename = job.get("filename")
    filepath = None
    size = 0
    mime = None
    if has_file:
        filename = filename or os.path.basename(src)
        filepath = os.path.join(dest_dir, filename)
        shutil.move(src, filepath)
        size = os.path.getsize(filepath)
        mime = mimetypes.guess_type(filename)[0]

    meta = {k: job.get(k) for k in _META_FIELDS if job.get(k) is not None}
    rtype = job.get("type")
    title = job.get("title") or filename or source_url
    created = int(time.time())

    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO resources "
            "(id, session, provider, type, title, source_url, filename, "
            " filepath, size, mime, meta_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, session, rtype, rtype, title, source_url, filename,
             filepath, size, mime, json.dumps(meta), created),
        )
        _conn.commit()

    return {
        "id": rid, "session": session, "provider": rtype, "type": rtype,
        "title": title, "source_url": source_url, "filename": filename,
        "filepath": filepath, "size": size, "mime": mime, "meta": meta,
        "created_at": created,
    }


def list_resources(session, query=None, project=None, limit=300):
    """Resources for a session, newest first, optionally text/project-filtered.

    project=None → all; project="__none__" → unfiled; else a project id.
    """
    sql = "SELECT * FROM resources WHERE session = ?"
    args = [session]
    if project == "__none__":
        sql += " AND (project_id IS NULL OR project_id = '')"
    elif project:
        sql += " AND project_id = ?"
        args.append(project)
    if query:
        sql += " AND (title LIKE ? OR source_url LIKE ? OR type LIKE ?)"
        like = f"%{query}%"
        args += [like, like, like]
    sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
    args.append(int(limit))
    with _lock:
        rows = _conn.execute(sql, args).fetchall()
    return [_row_to_dict(r) for r in rows]


# ── Projects (Phase D) ──────────────────────────────────────────────
def create_project(session, name, pid):
    created = int(time.time())
    with _lock:
        _conn.execute(
            "INSERT INTO projects (id, session, name, created_at) VALUES (?,?,?,?)",
            (pid, session, name, created),
        )
        _conn.commit()
    return {"id": pid, "session": session, "name": name, "created_at": created, "count": 0}


def list_projects(session):
    with _lock:
        rows = _conn.execute(
            "SELECT p.id, p.name, p.created_at, "
            "  (SELECT COUNT(*) FROM resources r "
            "   WHERE r.session = p.session AND r.project_id = p.id) AS count "
            "FROM projects p WHERE p.session = ? ORDER BY p.created_at DESC",
            (session,),
        ).fetchall()
    return [dict(r) for r in rows]


def rename_project(session, pid, name):
    with _lock:
        cur = _conn.execute(
            "UPDATE projects SET name = ? WHERE session = ? AND id = ?",
            (name, session, pid),
        )
        _conn.commit()
        return cur.rowcount > 0


def delete_project(session, pid):
    """Delete the project; its resources become unfiled (files untouched)."""
    with _lock:
        _conn.execute(
            "UPDATE resources SET project_id = NULL WHERE session = ? AND project_id = ?",
            (session, pid),
        )
        cur = _conn.execute(
            "DELETE FROM projects WHERE session = ? AND id = ?", (session, pid)
        )
        _conn.commit()
        return cur.rowcount > 0


def assign_resource(session, rid, pid):
    """Move a resource into a project (pid None → unfiled). Validates ownership."""
    with _lock:
        if pid:
            owns = _conn.execute(
                "SELECT 1 FROM projects WHERE session = ? AND id = ?", (session, pid)
            ).fetchone()
            if not owns:
                return False
        cur = _conn.execute(
            "UPDATE resources SET project_id = ? WHERE session = ? AND id = ?",
            (pid, session, rid),
        )
        _conn.commit()
        return cur.rowcount > 0


# ── AI credentials + settings (Phase D) ─────────────────────────────
def set_credential(session, provider, api_key, base_url=None, model=None, label=None):
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO ai_credentials "
            "(session, provider, api_key, base_url, model, label) VALUES (?,?,?,?,?,?)",
            (session, provider, api_key, base_url, model, label),
        )
        _conn.commit()


def get_credential(session, provider):
    """Full credential (incl. key) for server-side use, or None."""
    with _lock:
        row = _conn.execute(
            "SELECT * FROM ai_credentials WHERE session = ? AND provider = ?",
            (session, provider),
        ).fetchone()
    return dict(row) if row else None


def list_credentials(session):
    """Connected providers with the key MASKED (safe for the client)."""
    with _lock:
        rows = _conn.execute(
            "SELECT provider, api_key, base_url, model, label "
            "FROM ai_credentials WHERE session = ?",
            (session,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        key = d.pop("api_key") or ""
        d["key_hint"] = ("…" + key[-4:]) if len(key) >= 4 else "set"
        out.append(d)
    return out


def delete_credential(session, provider):
    with _lock:
        _conn.execute(
            "DELETE FROM ai_credentials WHERE session = ? AND provider = ?",
            (session, provider),
        )
        _conn.commit()


def set_settings(session, default_provider, default_model):
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO settings (session, default_provider, default_model) "
            "VALUES (?,?,?)",
            (session, default_provider, default_model),
        )
        _conn.commit()


def get_settings(session):
    with _lock:
        row = _conn.execute(
            "SELECT default_provider, default_model FROM settings WHERE session = ?",
            (session,),
        ).fetchone()
    return dict(row) if row else {"default_provider": None, "default_model": None}


def get(session, rid):
    """One resource owned by session, or None."""
    with _lock:
        row = _conn.execute(
            "SELECT * FROM resources WHERE session = ? AND id = ?",
            (session, rid),
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete(session, rid):
    """Remove a resource's row and its files. Returns True if it existed."""
    rec = get(session, rid)
    if not rec:
        return False
    fp = rec.get("filepath")
    if fp and _under_root(fp):
        shutil.rmtree(os.path.dirname(os.path.realpath(fp)), ignore_errors=True)
    with _lock:
        _conn.execute(
            "DELETE FROM resources WHERE session = ? AND id = ?", (session, rid)
        )
        _conn.commit()
    return True

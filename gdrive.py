#!/usr/bin/env python3
"""Resource Shrimp — Google OAuth + Drive sync. stdlib only.

Optional feature, gated on environment configuration. With no credentials
set the rest of the app is unaffected; `configured()` returns False and the
HTTP layer hides/refuses the Drive endpoints.

Required env vars to activate:
    GOOGLE_CLIENT_ID       OAuth 2.0 client id (Web application)
    GOOGLE_CLIENT_SECRET   its client secret
    OAUTH_REDIRECT_BASE    this app's public base URL, e.g.
                           https://resource-shrimp.onrender.com

In Google Cloud Console: create an OAuth client (Web), add
"<OAUTH_REDIRECT_BASE>/api/auth/google/callback" as an authorized redirect
URI, and enable the Google Drive API.

Scope is drive.file (least privilege — the app only ever sees files it
creates) plus openid/email for a stable account identity.
"""

import json
import os
import secrets
import urllib.parse
from urllib.request import Request, urlopen

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "").rstrip("/")

SCOPES = "openid email https://www.googleapis.com/auth/drive.file"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
FOLDER_NAME = "Resource Shrimp"
FOLDER_MIME = "application/vnd.google-apps.folder"


def configured():
    return bool(CLIENT_ID and CLIENT_SECRET and REDIRECT_BASE)


def redirect_uri():
    return f"{REDIRECT_BASE}/api/auth/google/callback"


def auth_url(state):
    """Build the consent-screen URL to redirect the user to."""
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",   # request a refresh token
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _post_form(url, fields, timeout=20):
    body = urllib.parse.urlencode(fields).encode()
    req = Request(url, data=body,
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def exchange_code(code):
    """Authorization code -> token dict (access_token, refresh_token, expires_in)."""
    return _post_form(TOKEN_URL, {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    })


def refresh(refresh_token):
    """Refresh token -> new access token dict."""
    return _post_form(TOKEN_URL, {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })


def userinfo(access_token):
    req = Request(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _get_json(url, access_token, timeout=20):
    req = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ensure_folder(access_token, name=FOLDER_NAME):
    """Return the id of the app's Drive folder, creating it if needed."""
    q = urllib.parse.quote(
        f"name='{name}' and mimeType='{FOLDER_MIME}' and trashed=false"
    )
    found = _get_json(f"{DRIVE_FILES}?q={q}&fields=files(id,name)", access_token)
    files = found.get("files", [])
    if files:
        return files[0]["id"]
    meta = json.dumps({"name": name, "mimeType": FOLDER_MIME}).encode()
    req = Request(DRIVE_FILES, data=meta, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    })
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read())["id"]


def upload(access_token, filepath, filename, folder_id=None,
           mime="application/octet-stream"):
    """Multipart-upload a local file into the user's Drive. Returns Drive metadata."""
    boundary = "----rs" + secrets.token_hex(12)
    meta = {"name": filename}
    if folder_id:
        meta["parents"] = [folder_id]
    with open(filepath, "rb") as f:
        content = f.read()
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + json.dumps(meta).encode()
        + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = Request(DRIVE_UPLOAD, data=body, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    })
    with urlopen(req, timeout=180) as r:
        return json.loads(r.read())

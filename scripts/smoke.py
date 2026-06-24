#!/usr/bin/env python3
"""Smoke gate — must pass before every push (see AGENTS.md).

Imports every module, boots the server on a scratch port, and hits the key
endpoints. Exits non-zero on the first failure so CI / pre-push can block.
"""
import os
import sys
import json
import time
import tempfile
import subprocess
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("SMOKE_PORT", "8771"))
BASE = f"http://127.0.0.1:{PORT}"
failures = []


def check(name, ok, detail=""):
    print(f"  {'OK ' if ok else 'FAIL'}  {name}{(' — ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(name)


def get(path, cookie=None, expect=200):
    req = urllib.request.Request(BASE + path,
                                 headers={"Cookie": cookie} if cookie else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def main():
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    print("1) imports")
    for mod in ("library", "providers", "ai", "gdrive", "vault", "app"):
        try:
            __import__(mod)
            check(f"import {mod}", True)
        except Exception as e:
            check(f"import {mod}", False, repr(e))
    if failures:
        return 1

    print("2) boot server")
    env = dict(os.environ, PORT=str(PORT), LIBRARY_ROOT=tempfile.mkdtemp(prefix="smoke_lib_"))
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            code, _b = get("/")
            if code == 200:
                break
            time.sleep(0.2)
        check("server boots + serves /", get("/")[0] == 200)
        hcode, hbody = get("/health")
        check("/health", hcode == 200 and json.loads(hbody).get("ok") is True)

        print("3) endpoints")
        ck = "rs_session=smoke_session_001"
        code, body = get("/api/ai/status", ck)
        ok = code == 200 and isinstance(json.loads(body).get("catalog"), list)
        check("/api/ai/status", ok)
        check("/api/library", get("/api/library", ck)[0] == 200)
        check("/api/projects", get("/api/projects", ck)[0] == 200)
        check("/api/access", get("/api/access", ck)[0] == 200)
        check("/api/status/unknown_id", get("/api/status/unknown_id", ck)[0] == 200)
        check("static style.css", get("/static/style.css")[0] == 200)
        check("static app.js", get("/static/app.js")[0] == 200)
        check("bad route 404", get("/nope")[0] == 404)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print()
    if failures:
        print(f"SMOKE FAILED — {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

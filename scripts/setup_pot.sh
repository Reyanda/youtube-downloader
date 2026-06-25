#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Set up the bgutil PO token provider — the "underground" YouTube token
# refresher. yt-dlp auto-calls it (only for YouTube URLs) to mint a fresh
# proof-of-origin token per request, which is what gets past YouTube's
# "confirm you're not a bot" check on flagged datacenter IPs.
#
# It's a single dependency-free Rust binary (<50MB RAM, no Node/Deno) plus a
# yt-dlp plugin. Best-effort: a failure here must NOT break the deploy — the
# app still downloads (just without the token refresher) if this can't fetch.
# ---------------------------------------------------------------------------
set +e
REL="https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/latest/download"
mkdir -p bin yt-dlp-plugins

echo "[pot] downloading provider binary (bgutil-pot)..."
if curl -fsSL -o bin/bgutil-pot "$REL/bgutil-pot-linux-x86_64"; then
  chmod +x bin/bgutil-pot && echo "[pot] binary OK"
else
  echo "[pot] binary download FAILED — continuing without the token refresher"
fi

echo "[pot] downloading yt-dlp plugin..."
if curl -fsSL -o /tmp/pot-plugin.zip "$REL/bgutil-ytdlp-pot-provider-rs.zip"; then
  python -m zipfile -e /tmp/pot-plugin.zip yt-dlp-plugins/ && echo "[pot] plugin OK"
else
  echo "[pot] plugin download FAILED — continuing without the token refresher"
fi

exit 0

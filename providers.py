#!/usr/bin/env python3
"""Resource Shrimp — provider registry. stdlib only.

A provider knows how to recognise a URL and turn it into a downloaded
resource. Adding a new resource type = add one Provider subclass and
register() it. The core server never needs to change.

    class Provider:
        name      -> short identifier ("video", "article", ...)
        aliases   -> other names callers may select it by
        matches() -> confidence score for a URL (0 = not mine)
        resolve() -> do the work, writing progress/result into the job

detect() ranks every provider by matches() and returns the best one.
by_name() selects a provider explicitly (used when the client overrides
auto-detection).
"""

import re

PROVIDERS = []


def register(provider):
    """Add a provider instance to the registry."""
    PROVIDERS.append(provider)
    return provider


def detect(url):
    """Return the highest-confidence provider for url, or None."""
    best, best_score = None, 0
    for p in PROVIDERS:
        score = p.matches(url)
        if score > best_score:
            best, best_score = p, score
    return best


def by_name(name):
    """Return the provider matching a name/alias, or None."""
    if not name:
        return None
    name = name.lower()
    for p in PROVIDERS:
        if name == p.name or name in p.aliases:
            return p
    return None


class Provider:
    """Base class. Subclass and register() to add a resource type."""
    name = "base"
    aliases = ()

    def matches(self, url):
        """Confidence this provider should handle url. 0 = no."""
        return 0

    def resolve(self, url, opts, did):
        """Fetch the resource, updating the shared job record for did."""
        raise NotImplementedError


# ── Concrete providers ──────────────────────────────────────────────
# Resolver logic still lives in app.py; providers wrap it via a callable
# injected at registration. This keeps the registry self-contained while
# the existing, security-hardened download functions stay untouched.

class VideoProvider(Provider):
    """yt-dlp backed video/audio. Low-confidence catch-all default."""
    name = "video"
    aliases = ("audio",)

    def __init__(self, resolver):
        self._resolver = resolver

    def matches(self, url):
        return 1  # baseline: handles anything no specific provider claims

    def resolve(self, url, opts, did):
        self._resolver(
            url, did,
            opts.get("quality", "1080p"),
            opts.get("subtitles", False),
            opts.get("format", "mp4"),
        )


class ArticleProvider(Provider):
    """Academic papers via DOI / arXiv / PubMed / publisher URLs."""
    name = "article"
    aliases = ("doi", "arxiv", "pubmed", "academic", "paper")

    def __init__(self, resolver):
        self._resolver = resolver

    def matches(self, url):
        u = url.lower().strip()
        if re.search(r'^10\.\d{4,}/', u) or 'doi.org/10.' in u or 'dx.doi.org/10.' in u:
            return 100
        if 'arxiv.org' in u:
            return 90
        if 'pubmed' in u or 'ncbi.nlm.nih.gov' in u:
            return 90
        if re.search(r'springer|wiley|sciencedirect|nature\.com|science\.org|ieee|acm', u):
            return 80
        return 0

    def resolve(self, url, opts, did):
        self._resolver(url, did)

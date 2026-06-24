#!/usr/bin/env python3
"""Resource Shrimp — systematic-review search-strategy engine. stdlib only.

Turns clean PICO/PECO concepts into PRESS-aligned, database-specific Boolean
search strategies. Synonyms/explosions are grounded in REAL MeSH via NCBI
E-utilities (deterministic), not LLM guesses. An optional LLM step decomposes
a free-text question into concepts.

A concept = one PICO element with one or more seed terms, e.g.
    {"label": "Population", "terms": ["malnutrition", "wasting"]}
"""

import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_UA = {"User-Agent": "ResourceShrimp-SR/1.0"}
MAX_SYNONYMS = 6

# NCBI throttle: 3 req/s unauthenticated, 10 with an API key.
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
_MIN_INTERVAL = 0.11 if NCBI_API_KEY else 0.35
_last_call = [0.0]
_throttle_lock = threading.Lock()


def _get_json(url, timeout=20):
    if NCBI_API_KEY:
        url += ("&" if "?" in url else "?") + "api_key=" + NCBI_API_KEY
    with _throttle_lock:
        dt = time.time() - _last_call[0]
        if dt < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - dt)
        _last_call[0] = time.time()
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def mesh_lookup(term):
    """Return {descriptor, synonyms} for a term from MeSH, or None.

    Picks the descriptor whose official name matches the term; falls back to
    the top-ranked descriptor otherwise.
    """
    term = (term or "").strip()
    if not term:
        return None
    try:
        es = _get_json(f"{EUTILS}/esearch.fcgi?db=mesh&retmode=json&retmax=5"
                       f"&term={urllib.parse.quote(term)}")
        ids = es.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        summ = _get_json(f"{EUTILS}/esummary.fcgi?db=mesh&retmode=json"
                         f"&id={','.join(ids)}")
        result = summ.get("result", {})
        best = None
        for uid in ids:
            rec = result.get(uid) or {}
            meshterms = rec.get("ds_meshterms") or []
            if not meshterms:
                continue
            descriptor = meshterms[0]
            entry = best or {"descriptor": descriptor, "synonyms": meshterms[1:]}
            if descriptor.lower() == term.lower():
                return {"descriptor": descriptor, "synonyms": meshterms[1:]}
            best = entry
        return best
    except Exception:
        return None


def _phrase(t):
    return f'"{t}"' if " " in t else t


def _concept_terms(concept):
    """Resolve a concept's seed terms into {descriptors, free_terms}."""
    descriptors, free = [], []
    for seed in concept.get("terms", []):
        seed = (seed or "").strip()
        if not seed:
            continue
        if seed not in free:
            free.append(seed)
        m = mesh_lookup(seed)
        if m:
            if m["descriptor"] not in descriptors:
                descriptors.append(m["descriptor"])
            for syn in m["synonyms"][:MAX_SYNONYMS]:
                if syn not in free:
                    free.append(syn)
    return descriptors, free


def _pubmed_block(descriptors, free):
    parts = [f'{_phrase(d)}[Mesh]' for d in descriptors]
    parts += [f'{_phrase(t)}[tiab]' for t in free]
    return "(" + " OR ".join(parts) + ")"


def _ovid_block(descriptors, free):
    parts = [f'exp {d}/' for d in descriptors]
    parts += [f'{t}.ti,ab.' for t in free]
    return "(" + " or ".join(parts) + ")"


def _cochrane_block(descriptors, free):
    parts = [f'[mh {_phrase(d)}]' for d in descriptors]
    parts += [f'{_phrase(t)}:ti,ab,kw' for t in free]
    return "(" + " OR ".join(parts) + ")"


def build(concepts):
    """Build database-specific strategies from resolved concepts."""
    resolved = []
    for c in concepts:
        descriptors, free = _concept_terms(c)
        if not (descriptors or free):
            continue
        resolved.append({"label": c.get("label", ""), "descriptors": descriptors,
                         "free": free})
    if not resolved:
        return {"concepts": [], "pubmed": "", "ovid": "", "cochrane": ""}

    pubmed = "\nAND\n".join(_pubmed_block(c["descriptors"], c["free"]) for c in resolved)
    ovid = " and ".join(_ovid_block(c["descriptors"], c["free"]) for c in resolved)
    cochrane = "\nAND\n".join(_cochrane_block(c["descriptors"], c["free"]) for c in resolved)
    return {
        "concepts": resolved,
        "pubmed": pubmed,
        "ovid": ovid,        # Ovid MEDLINE / Embase syntax
        "cochrane": cochrane,
        "note": ("MeSH terms auto-explode in PubMed; Ovid uses exp/. Verify field "
                 "tags, add date/language limits and study-design filters per protocol. "
                 "Peer-review the strategy (PRESS) before running."),
    }


# ── Optional: LLM decomposition of a free-text question into PICO concepts ──
DECOMP_PROMPT = (
    "You are a systematic-review information specialist. Decompose the user's "
    "question into PICO/PECO concepts for a literature search. Return ONLY JSON: "
    '{"concepts":[{"label":"Population|Intervention/Exposure|Comparator|Outcome",'
    '"terms":["seed term", ...]}]}. Use 2-4 concepts; 1-4 concise seed terms each '
    "(prefer canonical noun phrases that map to controlled vocabulary). No prose.")


def concepts_from_question(question, chat_fn):
    """Use an injected chat function (messages -> {answer}) to extract concepts."""
    msgs = [{"role": "system", "content": DECOMP_PROMPT},
            {"role": "user", "content": question.strip()}]
    out = chat_fn(msgs)["answer"]
    m = re.search(r'\{.*\}', out, re.DOTALL)
    if not m:
        raise ValueError("Could not parse concepts from the model output")
    data = json.loads(m.group(0))
    return data.get("concepts", [])

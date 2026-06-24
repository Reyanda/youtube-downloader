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


EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _get_json(url, timeout=20):
    is_ncbi = "eutils.ncbi" in url
    if is_ncbi and NCBI_API_KEY:
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


# ── Run a search → records (PubMed E-utilities, Europe PMC) ─────────
def run_pubmed(query, retmax=50):
    es = _get_json(f"{EUTILS}/esearch.fcgi?db=pubmed&retmode=json"
                   f"&retmax={int(retmax)}&term={urllib.parse.quote(query)}")
    ids = es.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return [], int(es.get("esearchresult", {}).get("count", 0) or 0)
    total = int(es.get("esearchresult", {}).get("count", 0) or 0)
    summ = _get_json(f"{EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}")
    result = summ.get("result", {})
    recs = []
    for uid in result.get("uids", []):
        r = result.get(uid, {})
        doi = ""
        for aid in r.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
        authors = [a.get("name", "") for a in r.get("authors", [])
                   if a.get("authtype") == "Author"][:12]
        recs.append({
            "source": "PubMed", "pmid": uid, "doi": doi,
            "title": (r.get("title") or "").rstrip("."),
            "authors": authors,
            "journal": r.get("fulljournalname") or r.get("source", ""),
            "year": (r.get("pubdate", "") or "")[:4], "is_oa": None,
        })
    return recs, total


def run_europepmc(query, retmax=50):
    data = _get_json(f"{EUROPEPMC_SEARCH}?query={urllib.parse.quote(query)}"
                     f"&format=json&pageSize={int(retmax)}&resultType=lite")
    rl = data.get("resultList", {}).get("result", [])
    total = int(data.get("hitCount", 0) or 0)
    recs = []
    for a in rl:
        authors = [x.strip() for x in (a.get("authorString", "") or "").split(",") if x.strip()][:12]
        recs.append({
            "source": "Europe PMC", "pmid": a.get("pmid", ""), "doi": a.get("doi", ""),
            "title": (a.get("title") or "").rstrip("."), "authors": authors,
            "journal": a.get("journalTitle", ""), "year": str(a.get("pubYear", "")),
            "is_oa": a.get("isOpenAccess") == "Y",
        })
    return recs, total


def dedupe(records):
    seen, out = set(), []
    for r in records:
        key = (r.get("doi") or "").lower().strip() or \
              ("pmid:" + (r.get("pmid") or "")) if r.get("pmid") else \
              ("ti:" + (r.get("title") or "").lower()[:80])
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def to_ris(records):
    lines = []
    for r in records:
        lines.append("TY  - JOUR")
        if r.get("title"):
            lines.append(f"TI  - {r['title']}")
        for a in r.get("authors", []):
            lines.append(f"AU  - {a}")
        if r.get("journal"):
            lines.append(f"JO  - {r['journal']}")
        if r.get("year"):
            lines.append(f"PY  - {r['year']}")
        if r.get("doi"):
            lines.append(f"DO  - {r['doi']}")
        if r.get("pmid"):
            lines.append(f"AN  - {r['pmid']}")
        lines.append("ER  - ")
        lines.append("")
    return "\n".join(lines)


def to_csv(records):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["title", "authors", "journal", "year", "doi", "pmid", "source", "open_access"])
    for r in records:
        w.writerow([r.get("title", ""), "; ".join(r.get("authors", [])),
                    r.get("journal", ""), r.get("year", ""), r.get("doi", ""),
                    r.get("pmid", ""), r.get("source", ""),
                    "" if r.get("is_oa") is None else ("yes" if r["is_oa"] else "no")])
    return buf.getvalue()


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

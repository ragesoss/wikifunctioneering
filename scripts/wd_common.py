"""Shared helpers for Wikidata chat-driven probe scripts (wd_*.py).

Exposes a minimal API: batched entity fetch, SPARQL, label resolution,
search, plus a light ANSI styler that auto-disables on non-TTY output.
Read-only; no credentials needed.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request

from config import USER_AGENT, WIKIDATA_API, SPARQL_ENDPOINT


# ------------------------- ANSI styling -------------------------

class Style:
    """ANSI wrapper. Auto-disables when stdout isn't a TTY or NO_COLOR is set."""
    def __init__(self, enabled: bool | None = None):
        if enabled is None:
            enabled = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        self.enabled = enabled

    def _c(self, code: str) -> str:
        return code if self.enabled else ""

    def bold(self, s): return f"{self._c(chr(27)+'[1m')}{s}{self._c(chr(27)+'[0m')}"
    def dim(self, s):  return f"{self._c(chr(27)+'[2m')}{s}{self._c(chr(27)+'[0m')}"
    def cyan(self, s): return f"{self._c(chr(27)+'[36m')}{s}{self._c(chr(27)+'[0m')}"
    def yellow(self, s): return f"{self._c(chr(27)+'[33m')}{s}{self._c(chr(27)+'[0m')}"
    def green(self, s): return f"{self._c(chr(27)+'[32m')}{s}{self._c(chr(27)+'[0m')}"
    def magenta(self, s): return f"{self._c(chr(27)+'[35m')}{s}{self._c(chr(27)+'[0m')}"
    def red(self, s): return f"{self._c(chr(27)+'[31m')}{s}{self._c(chr(27)+'[0m')}"


# ------------------------- API calls -------------------------

def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, application/sparql-results+json",
    })
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def wbgetentities(ids: list[str], *, props: str = "labels|descriptions|claims",
                  languages: str = "en") -> dict:
    """Batch-fetch Wikidata entities. 50-ID per-request cap."""
    out: dict = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        params = {"action": "wbgetentities", "ids": "|".join(batch),
                  "props": props, "languages": languages, "format": "json"}
        data = _http_get_json(f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}")
        out.update(data.get("entities", {}))
    return out


def wbsearchentities(query: str, *, entity_type: str = "item",
                     language: str = "en", limit: int = 10) -> list[dict]:
    """Label-prefix search. Returns [{id, label, description, match}]."""
    params = {"action": "wbsearchentities", "search": query, "language": language,
              "type": entity_type, "limit": str(limit), "format": "json"}
    data = _http_get_json(f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}")
    return data.get("search", [])


def sparql(query: str) -> list[dict]:
    """Run a SPARQL query. Returns list of result bindings."""
    url = f"{SPARQL_ENDPOINT}?{urllib.parse.urlencode({'query': query, 'format': 'json'})}"
    return _http_get_json(url)["results"]["bindings"]


# ------------------------- Parsing -------------------------

def claim_value_id(claim: dict) -> str | None:
    dv = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
    if isinstance(dv, dict):
        return dv.get("id")
    return None


def label_of(ents: dict, eid: str, lang: str = "en") -> str:
    e = ents.get(eid)
    if not e:
        return "?"
    return e.get("labels", {}).get(lang, {}).get("value", "(no label)")


def desc_of(ents: dict, eid: str, lang: str = "en") -> str:
    e = ents.get(eid)
    if not e:
        return ""
    return e.get("descriptions", {}).get(lang, {}).get("value", "")


def claims_of(ents: dict, eid: str, pid: str) -> list[str]:
    """Return all Q-ID values of `pid` claims on entity `eid`."""
    e = ents.get(eid, {})
    out = []
    for c in e.get("claims", {}).get(pid, []):
        v = claim_value_id(c)
        if v:
            out.append(v)
    return out


# ------------------------- Rendering -------------------------

def fmt_ref(eid: str, ents: dict, st: Style) -> str:
    lbl = label_of(ents, eid)
    paint = (st.cyan if eid.startswith("Q") else
             st.yellow if eid.startswith("P") else
             st.magenta)
    return f"{paint(eid)} {st.dim('\u201c')}{lbl}{st.dim('\u201d')}"


def sparql_id(cell: dict) -> str:
    """Pull the Q/P/L ID out of a SPARQL URI binding."""
    return cell["value"].rsplit("/", 1)[-1]


def ensure_labels(ents: dict, ids) -> None:
    """Fetch labels/descriptions/claims for any IDs missing from ents.
    Mutates ents. Safe to call with a mix of already-present and new ids."""
    missing = {i for i in ids if i and i not in ents}
    if missing:
        ents.update(wbgetentities(sorted(missing), props="labels|descriptions|claims"))


# ------------------------- Common SPARQL probes -------------------------
# These are the queries that keep coming up during proposal-review
# investigations. Every caller that needs them imports from here.


def backlink_count(qid: str) -> int:
    """How many lexeme senses link to `qid` via P5137?"""
    rows = sparql(f"SELECT (COUNT(DISTINCT ?s) AS ?c) WHERE {{ ?s wdt:P5137 wd:{qid} . }}")
    return int(rows[0]["c"]["value"]) if rows else 0


def pattern_count(p31: list[str], p279: list[str]) -> int:
    """Count items matching ALL given P31 + P279 constraints."""
    clauses = []
    for q in p31:  clauses.append(f"?i wdt:P31 wd:{q} .")
    for q in p279: clauses.append(f"?i wdt:P279 wd:{q} .")
    if not clauses:
        return 0
    rows = sparql(f"""
    SELECT (COUNT(DISTINCT ?i) AS ?c) WHERE {{
      {chr(10).join('      ' + c for c in clauses)}
    }}
    """)
    return int(rows[0]["c"]["value"]) if rows else 0


def pattern_matches(p31: list[str], p279: list[str], limit: int = 10) -> list[dict]:
    """Top items matching all given P31 + P279 constraints, ordered by P5137 backlinks."""
    clauses = []
    for q in p31:  clauses.append(f"?i wdt:P31 wd:{q} .")
    for q in p279: clauses.append(f"?i wdt:P279 wd:{q} .")
    if not clauses:
        return []
    rows = sparql(f"""
    SELECT ?i (COUNT(DISTINCT ?s) AS ?bk) WHERE {{
      {chr(10).join('      ' + c for c in clauses)}
      OPTIONAL {{ ?s wdt:P5137 ?i . }}
    }} GROUP BY ?i ORDER BY DESC(?bk) ?i LIMIT {limit}
    """)
    return [{"qid": sparql_id(r["i"]), "backlinks": int(r["bk"]["value"])} for r in rows]


def direct_subclasses(qid: str, limit: int = 15) -> list[dict]:
    """Direct P279 children of `qid`, ordered by P5137 backlinks."""
    rows = sparql(f"""
    SELECT ?i (COUNT(DISTINCT ?s) AS ?bk) WHERE {{
      ?i wdt:P279 wd:{qid} .
      OPTIONAL {{ ?s wdt:P5137 ?i . }}
    }} GROUP BY ?i ORDER BY DESC(?bk) ?i LIMIT {limit}
    """)
    return [{"qid": sparql_id(r["i"]), "backlinks": int(r["bk"]["value"])} for r in rows]


def senses_for_lemma(lemma: str, lang_qid: str = "Q1860", lang_iso: str = "en") -> list[dict]:
    """Senses (across all lexemes) where the lemma exactly matches. Returns
    [{lexeme, sense, gloss, p5137}] with multiple rows per lexeme-sense if
    multiple P5137s."""
    rows = sparql(f"""
    SELECT ?lex ?sense ?gloss ?concept WHERE {{
      ?lex wikibase:lemma ?lemma ;
           dct:language wd:{lang_qid} ;
           ontolex:sense ?sense .
      FILTER(STR(?lemma) = "{lemma}")
      OPTIONAL {{ ?sense skos:definition ?gloss . FILTER(LANG(?gloss) = "{lang_iso}") }}
      OPTIONAL {{ ?sense wdt:P5137 ?concept . }}
    }}
    ORDER BY ?lex ?sense
    """)
    by_sense = {}
    for r in rows:
        sid = sparql_id(r["sense"])
        entry = by_sense.setdefault(sid, {
            "sense": sid,
            "lexeme": sparql_id(r["lex"]),
            "gloss": None, "p5137": [],
        })
        if "gloss" in r and not entry["gloss"]:
            entry["gloss"] = r["gloss"]["value"]
        if "concept" in r:
            cid = sparql_id(r["concept"])
            if cid not in entry["p5137"]:
                entry["p5137"].append(cid)
    return list(by_sense.values())


def sample_p5137_backlinks(qid: str, limit: int = 8) -> list[dict]:
    """Sample of lexeme senses whose P5137 points at qid. Multilingual."""
    rows = sparql(f"""
    SELECT ?sense ?lemma ?gloss WHERE {{
      ?sense wdt:P5137 wd:{qid} .
      ?lex ontolex:sense ?sense ; wikibase:lemma ?lemma .
      OPTIONAL {{ ?sense skos:definition ?gloss . FILTER(LANG(?gloss) = "en") }}
    }} LIMIT {limit}
    """)
    out = []
    for r in rows:
        lemma_v = r["lemma"]["value"]
        lemma_lang = r["lemma"].get("xml:lang") or ""
        out.append({
            "sense": sparql_id(r["sense"]),
            "lemma": lemma_v,
            "lang": lemma_lang,
            "gloss": r.get("gloss", {}).get("value", ""),
        })
    return out


def parent_chain(qid: str, levels: int = 2) -> list[list[str]]:
    """Walk up P279 parent chain `levels` hops. Returns a list-per-level
    of Q-IDs (each level is all parents at that depth). First entry is
    the direct parents of `qid`."""
    chain = []
    frontier = [qid]
    for _ in range(levels):
        if not frontier:
            break
        values = " ".join(f"wd:{q}" for q in frontier)
        rows = sparql(f"""
        SELECT DISTINCT ?p WHERE {{
          VALUES ?c {{ {values} }}
          ?c wdt:P279 ?p .
        }}
        """)
        next_level = [sparql_id(r["p"]) for r in rows]
        if not next_level:
            break
        chain.append(next_level)
        frontier = next_level
    return chain


def sleep_friendly_error(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)

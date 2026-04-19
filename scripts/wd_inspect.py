#!/usr/bin/env python3
"""Inspect one or more Wikidata entities (items, lexemes, senses, properties).

Shows label, description, and structural claims (P31/P279 for items;
lemma/language/senses+glosses+P5137 for lexemes). For Q-items, also
lists a sample of lexeme senses that link here via P5137, to gauge
whether it's an established "concept hub."

Usage:
    python scripts/wd_inspect.py Q513420
    python scripts/wd_inspect.py L13009 L13009-S1
    python scripts/wd_inspect.py Q513420 Q4485156 Q1079196
"""

from __future__ import annotations

import argparse
import sys

from wd_common import (
    Style, wbgetentities, sparql, label_of, desc_of, claim_value_id,
    claims_of, fmt_ref, sparql_id,
)


def _sample_p5137_backlinks(qid: str, limit: int = 10) -> list[dict]:
    """Sample lexeme senses whose P5137 points at qid."""
    rows = sparql(f"""
    SELECT ?sense ?lemma ?gloss ?lang WHERE {{
      ?sense wdt:P5137 wd:{qid} .
      ?lexeme ontolex:sense ?sense ;
              wikibase:lemma ?lemma .
      OPTIONAL {{ ?sense skos:definition ?gloss . FILTER(LANG(?gloss) = "en") }}
      BIND(LANG(?lemma) AS ?lang)
    }} LIMIT {limit}
    """)
    out = []
    for r in rows:
        out.append({
            "sense": r["sense"]["value"].rsplit("/", 1)[-1],
            "lemma": r["lemma"]["value"],
            "lang":  r["lang"]["value"],
            "gloss": r.get("gloss", {}).get("value", ""),
        })
    return out


def _backlink_count(qid: str) -> int:
    rows = sparql(f"""
    SELECT (COUNT(DISTINCT ?sense) AS ?c) WHERE {{
      ?sense wdt:P5137 wd:{qid} .
    }}
    """)
    return int(rows[0]["c"]["value"]) if rows else 0


def render_item(qid: str, ents: dict, st: Style) -> str:
    out = []
    out.append(f"{st.bold(fmt_ref(qid, ents, st))}")
    d = desc_of(ents, qid)
    if d:
        out.append(f"  {st.dim(d)}")
    for pid in ("P31", "P279"):
        vals = claims_of(ents, qid, pid)
        if vals:
            rendered = ", ".join(fmt_ref(v, ents, st) for v in vals)
            out.append(f"  {fmt_ref(pid, ents, st)}: {rendered}")
    # P5137 backlinks
    bk = _backlink_count(qid)
    out.append(f"  {st.bold('as P5137 hub:')} {bk} sense(s) link here")
    if bk > 0:
        for s in _sample_p5137_backlinks(qid, limit=8):
            gloss = f" \u2014 {s['gloss'][:50]}" if s["gloss"] else ""
            out.append(f"    {st.magenta(s['sense'])}  "
                       f"{s['lemma']} ({s['lang']}){gloss}")
        if bk > 8:
            out.append(f"    {st.dim(f'\u2026 and {bk-8} more')}")
    return "\n".join(out)


def render_lexeme(lid: str, ents: dict, st: Style) -> str:
    e = ents.get(lid, {})
    lemmas = e.get("lemmas", {})
    lemma_en = lemmas.get("en", {}).get("value") or next(iter(lemmas.values()), {}).get("value", "?")
    lang = e.get("language", "?")
    cat = e.get("lexicalCategory", "?")
    out = []
    out.append(f"{st.bold(st.magenta(lid))} {st.dim('\u201c')}{lemma_en}{st.dim('\u201d')}")
    out.append(f"  language:         {fmt_ref(lang, ents, st)}")
    out.append(f"  lexical category: {fmt_ref(cat, ents, st)}")
    out.append(f"  {st.bold('senses:')}")
    for s in e.get("senses", []):
        sid = s["id"]
        gloss = s.get("glosses", {}).get("en", {}).get("value", "(no en gloss)")
        out.append(f"    {st.magenta(sid)}: {gloss}")
        for c in s.get("claims", {}).get("P5137", []):
            qid = claim_value_id(c)
            if qid:
                out.append(f"      P5137 \u2192 {fmt_ref(qid, ents, st)}")
    return "\n".join(out)


def render_property(pid: str, ents: dict, st: Style) -> str:
    out = [f"{st.bold(fmt_ref(pid, ents, st))}"]
    d = desc_of(ents, pid)
    if d:
        out.append(f"  {st.dim(d)}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ids", nargs="+", help="Entity IDs (Q..., L..., L...-S..., P...)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    st = Style(enabled=(not args.no_color) and sys.stdout.isatty())

    # Resolve sense IDs to their parent lexeme for fetching; handle separately.
    lexeme_ids = set()
    item_ids = set()
    prop_ids = set()
    sense_parents = {}
    for i in args.ids:
        if "-S" in i or "-F" in i:
            parent = i.split("-")[0]
            lexeme_ids.add(parent)
            sense_parents[i] = parent
        elif i.startswith("L"):
            lexeme_ids.add(i)
        elif i.startswith("Q"):
            item_ids.add(i)
        elif i.startswith("P"):
            prop_ids.add(i)
        else:
            print(f"skip: unknown id shape {i!r}", file=sys.stderr)

    all_ids = list(lexeme_ids | item_ids | prop_ids)
    ents = wbgetentities(all_ids)

    # Follow-up fetch: labels for every P31/P279 value so fmt_ref resolves them.
    extras = set()
    for qid in item_ids:
        for pid in ("P31", "P279"):
            extras.update(claims_of(ents, qid, pid))
    extras -= set(ents.keys())
    # Also every property id in lexeme/item claims so fmt_ref on keys works.
    extras.update({"P31", "P279", "P5137"})
    extras -= set(ents.keys())
    if extras:
        ents.update(wbgetentities(sorted(extras), props="labels|descriptions"))

    for i in args.ids:
        if i in sense_parents:
            # Print the sense inline within its parent lexeme rendering.
            lid = sense_parents[i]
            e = ents.get(lid, {})
            for s in e.get("senses", []):
                if s["id"] == i:
                    out = [f"{st.bold(st.magenta(i))}  (sense of {fmt_ref(lid, ents, st)})"]
                    gloss = s.get("glosses", {}).get("en", {}).get("value", "(no en gloss)")
                    out.append(f"  gloss (en): {gloss}")
                    for c in s.get("claims", {}).get("P5137", []):
                        qid = claim_value_id(c)
                        if qid:
                            # grab label
                            if qid not in ents:
                                ents.update(wbgetentities([qid], props="labels|descriptions"))
                            out.append(f"  P5137 \u2192 {fmt_ref(qid, ents, st)}")
                    print("\n".join(out))
                    print()
                    break
        elif i.startswith("L"):
            print(render_lexeme(i, ents, st))
            print()
        elif i.startswith("Q"):
            print(render_item(i, ents, st))
            print()
        elif i.startswith("P"):
            print(render_property(i, ents, st))
            print()


if __name__ == "__main__":
    main()

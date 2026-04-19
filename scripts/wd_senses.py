#!/usr/bin/env python3
"""For each English lemma, list its lexeme senses and any P5137 targets.

Answers: "how does Wikidata currently model this word's senses, and
which concept Q-IDs are already linked?" Useful for seeing patterns
across a family of related words (UI actions, error types, etc.)
before deciding how to model a new one.

Usage:
    python scripts/wd_senses.py save close open copy undo
    python scripts/wd_senses.py --lang en cancel abort dismiss
    python scripts/wd_senses.py --lang de abbrechen schliessen
"""

from __future__ import annotations

import argparse
import sys

from wd_common import (
    Style, sparql, wbgetentities, fmt_ref, sparql_id,
)

LANG_QID = {
    "en": "Q1860", "de": "Q188", "fr": "Q150", "es": "Q1321",
    "it": "Q652",  "pt": "Q5146", "ru": "Q7737", "ja": "Q5287",
    "zh": "Q7850", "nl": "Q7411", "pl": "Q809",  "sv": "Q9027",
    "da": "Q9035", "no": "Q9043", "fi": "Q1412",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("lemmas", nargs="+")
    ap.add_argument("--lang", default="en",
                    help="ISO language code (default en)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    st = Style(enabled=(not args.no_color) and sys.stdout.isatty())

    lang_qid = LANG_QID.get(args.lang)
    if not lang_qid:
        # Fall back to resolving via wikilambdaload_zlanguages? For now, error.
        print(f"Unknown language code {args.lang!r}. Known: {sorted(LANG_QID)}",
              file=sys.stderr)
        sys.exit(1)

    values = " ".join(f'"{l}"' for l in args.lemmas)
    rows = sparql(f"""
    SELECT ?lex ?lemma ?sense ?gloss ?concept WHERE {{
      VALUES ?wanted_lemma {{ {values} }}
      ?lex wikibase:lemma ?lemma ;
           dct:language wd:{lang_qid} ;
           ontolex:sense ?sense .
      FILTER(STR(?lemma) = STR(?wanted_lemma))
      OPTIONAL {{ ?sense skos:definition ?gloss . FILTER(LANG(?gloss) = "{args.lang}") }}
      OPTIONAL {{ ?sense wdt:P5137 ?concept . }}
    }}
    ORDER BY ?lemma ?sense
    """)

    by_lexeme: dict[str, dict] = {}
    for r in rows:
        lex = sparql_id(r["lex"])
        entry = by_lexeme.setdefault(lex, {
            "lemma": r["lemma"]["value"],
            "senses": {},
        })
        sid = sparql_id(r["sense"])
        sense = entry["senses"].setdefault(sid, {"gloss": None, "concepts": []})
        if "gloss" in r and not sense["gloss"]:
            sense["gloss"] = r["gloss"]["value"]
        if "concept" in r:
            cid = sparql_id(r["concept"])
            if cid not in sense["concepts"]:
                sense["concepts"].append(cid)

    # Batch-label everything before rendering.
    to_label = set()
    for entry in by_lexeme.values():
        for s in entry["senses"].values():
            to_label.update(s["concepts"])
    ents = wbgetentities(sorted(to_label), props="labels|descriptions") if to_label else {}

    requested_set = {l for l in args.lemmas}
    found_lemmas = {entry["lemma"] for entry in by_lexeme.values()}

    for lem in args.lemmas:
        print(f"{st.bold(lem)} ({args.lang})")
        matches = [e for e in by_lexeme.values() if e["lemma"] == lem]
        if not matches:
            print(f"  {st.dim('(no lexeme found)')}")
            print()
            continue
        for lex_id, entry in [(k, v) for k, v in by_lexeme.items() if v["lemma"] == lem]:
            print(f"  {st.magenta(lex_id)}")
            for sid, s in entry["senses"].items():
                gloss = s["gloss"] or st.dim("(no gloss)")
                print(f"    {st.magenta(sid)}: {gloss}")
                if s["concepts"]:
                    for cid in s["concepts"]:
                        print(f"      P5137 \u2192 {fmt_ref(cid, ents, st)}")
                else:
                    print(f"      {st.dim('P5137: (none)')}")
        print()


if __name__ == "__main__":
    main()

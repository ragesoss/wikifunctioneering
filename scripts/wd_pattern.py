#!/usr/bin/env python3
"""Find Wikidata items matching a classification pattern.

Specify any combination of P31 (instance of) and P279 (subclass of)
constraints. The script counts matching items and lists them with their
P5137 backlink counts, so you can gauge how established a given pattern
is before proposing a new item in it.

Usage:
    # How widely used is "P31 software feature AND P279 command"?
    python scripts/wd_pattern.py --p31 Q4485156 --p279 Q1079196

    # Just P31 software feature, limited output
    python scripts/wd_pattern.py --p31 Q4485156 --limit 15

    # With a label regex filter
    python scripts/wd_pattern.py --p31 Q4485156 --label-regex "^(copy|paste|save)$"
"""

from __future__ import annotations

import argparse
import sys

from wd_common import (
    Style, sparql, wbgetentities, label_of, desc_of, fmt_ref, sparql_id,
)



def build_query(p31: list[str], p279: list[str],
                label_regex: str | None, limit: int) -> str:
    parts = []
    for q in p31:
        parts.append(f"?i wdt:P31 wd:{q} .")
    for q in p279:
        parts.append(f"?i wdt:P279 wd:{q} .")
    if not parts:
        parts.append("?i wdt:P31 ?anything .")
    filter_clause = ""
    if label_regex:
        safe = label_regex.replace('"', '\\"')
        filter_clause = f"""?i rdfs:label ?lbl . FILTER(LANG(?lbl) = "en") FILTER(REGEX(LCASE(STR(?lbl)), "{safe}"))"""
    return f"""
    SELECT ?i (COUNT(DISTINCT ?sense) AS ?bk) WHERE {{
      {chr(10).join('      ' + p for p in parts)}
      {filter_clause}
      OPTIONAL {{ ?sense wdt:P5137 ?i . }}
    }}
    GROUP BY ?i
    ORDER BY DESC(?bk) ?i
    LIMIT {limit}
    """


def build_count_query(p31, p279, label_regex):
    parts = []
    for q in p31:
        parts.append(f"?i wdt:P31 wd:{q} .")
    for q in p279:
        parts.append(f"?i wdt:P279 wd:{q} .")
    if not parts:
        parts.append("?i wdt:P31 ?anything .")
    filter_clause = ""
    if label_regex:
        safe = label_regex.replace('"', '\\"')
        filter_clause = f"""?i rdfs:label ?lbl . FILTER(LANG(?lbl) = "en") FILTER(REGEX(LCASE(STR(?lbl)), "{safe}"))"""
    return f"""
    SELECT (COUNT(DISTINCT ?i) AS ?c) WHERE {{
      {chr(10).join('      ' + p for p in parts)}
      {filter_clause}
    }}
    """


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--p31", action="append", default=[],
                    help="Require P31 (instance of) this Q-ID. Repeatable.")
    ap.add_argument("--p279", action="append", default=[],
                    help="Require P279 (subclass of) this Q-ID. Repeatable.")
    ap.add_argument("--label-regex", help="Filter results by English label regex")
    ap.add_argument("--limit", type=int, default=30,
                    help="Maximum items to list (default 30)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    if not args.p31 and not args.p279:
        ap.error("At least one of --p31 or --p279 is required")

    st = Style(enabled=(not args.no_color) and sys.stdout.isatty())

    # Count
    count_rows = sparql(build_count_query(args.p31, args.p279, args.label_regex))
    total = int(count_rows[0]["c"]["value"]) if count_rows else 0

    constraint_qids = args.p31 + args.p279
    # Pre-fetch constraint Q-IDs so we can show them with labels in the header.
    constraint_ents = wbgetentities(constraint_qids, props="labels|descriptions") if constraint_qids else {}

    def _constraint_ref(q):
        return fmt_ref(q, constraint_ents, st)

    constraint = " AND ".join(
        [f"P31={_constraint_ref(q)}"  for q in args.p31] +
        [f"P279={_constraint_ref(q)}" for q in args.p279]
    )
    if args.label_regex:
        constraint += f" AND label ~ /{args.label_regex}/i"

    print(f"{st.bold('Pattern:')} {constraint}")
    # If there's exactly one constraint Q-ID, also show its description as
    # context \u2014 useful when listing "direct children of X" queries.
    if len(constraint_qids) == 1:
        d = desc_of(constraint_ents, constraint_qids[0])
        if d:
            print(f"  {st.dim(d)}")
    print(f"{st.bold('Total items matching:')} {total}")

    if total == 0:
        return

    # Fetch the list
    rows = sparql(build_query(args.p31, args.p279, args.label_regex, args.limit))

    # Batch-label items + their P31/P279 values we'll want to show.
    qids = [sparql_id(r["i"]) for r in rows]
    ents = wbgetentities(qids)
    ents.update(constraint_ents)

    print()
    print(f"  {'item':<12s} {'backlinks':<10s} label \u2014 description")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 50}")
    for r in rows:
        qid = sparql_id(r["i"])
        bk = int(r["bk"]["value"])
        bk_style = st.green if bk >= 3 else st.yellow if bk >= 1 else st.dim
        lbl = label_of(ents, qid)
        d = desc_of(ents, qid)[:60]
        print(f"  {fmt_ref(qid, ents, st):<30s} {bk_style(f'bk={bk:>3d}'):<20s} {st.dim(d)}")

    shown = len(rows)
    if total > shown:
        print(f"\n  {st.dim(f'\u2026 {total - shown} more matching items not shown (increase --limit)')}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Search Wikidata for items by label/alias, filtering out common noise.

Wraps wbsearchentities with a filter pass against known noise P31
values (templates, disambig pages, scholarly articles, patents, family
names, taxa, music releases, films). Shows label + description + key
classification (P31/P279) per hit so you can triage quickly.

Usage:
    python scripts/wd_search.py "user interface command"
    python scripts/wd_search.py --type property "item for this sense"
    python scripts/wd_search.py --limit 25 cancellation
"""

from __future__ import annotations

import argparse
import sys

from wd_common import (
    Style, wbsearchentities, wbgetentities, claims_of, fmt_ref,
)

NOISE_P31 = {
    "Q11266439",  # Wikimedia template
    "Q4167410",   # disambiguation page
    "Q4167836",   # Wikimedia category
    "Q13406463",  # Wikimedia list article
    "Q13442814",  # scholarly article
    "Q43305660",  # United States patent
    "Q253623",    # patent
    "Q5633421",   # scientific journal article
    "Q3331189",   # version, edition, or translation
    "Q27949697",  # Wikibase reason for deprecated rank
    "Q101352",    # family name
    "Q202444",    # given name
    "Q16521",     # taxon
    "Q23038290",  # fossil taxon
    "Q112826905", # class of anatomical entity
    "Q11424",     # film
    "Q134556",    # single (music)
    "Q7366",      # song
    "Q482994",    # album
    "Q108352648", # album release
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("query", nargs="+")
    ap.add_argument("--type", default="item",
                    choices=["item", "property", "lexeme"])
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--language", default="en")
    ap.add_argument("--include-noise", action="store_true",
                    help="Don't filter out templates / articles / etc.")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    st = Style(enabled=(not args.no_color) and sys.stdout.isatty())
    q = " ".join(args.query)

    # Over-fetch so the noise filter doesn't leave us empty-handed.
    raw = wbsearchentities(q, entity_type=args.type,
                           language=args.language,
                           limit=max(args.limit * 3, 30))
    if not raw:
        print(f"No results for {q!r}")
        return

    # Batch-fetch P31/P279 for filtering + context.
    ids = [h["id"] for h in raw]
    ents = wbgetentities(ids)
    # Label pass for P31/P279 values
    extras = set()
    for hid in ids:
        for pid in ("P31", "P279"):
            extras.update(claims_of(ents, hid, pid))
    extras -= set(ents.keys())
    if extras:
        ents.update(wbgetentities(sorted(extras), props="labels|descriptions"))

    shown = 0
    hidden = 0
    print(f"{st.bold('Search:')} {q!r}  (type={args.type}, lang={args.language})")
    print()
    for hit in raw:
        if shown >= args.limit:
            break
        hid = hit["id"]
        if not args.include_noise:
            p31_vals = set(claims_of(ents, hid, "P31"))
            if p31_vals & NOISE_P31:
                hidden += 1
                continue
        shown += 1
        print(f"  {fmt_ref(hid, ents, st)}")
        if hit.get("description"):
            print(f"    {st.dim(hit['description'][:90])}")
        for pid in ("P31", "P279"):
            vals = claims_of(ents, hid, pid)[:3]
            if vals:
                rendered = ", ".join(fmt_ref(v, ents, st) for v in vals)
                print(f"    {fmt_ref(pid, ents, st)}: {rendered}")
    if hidden and not args.include_noise:
        print(f"\n  {st.dim(f'({hidden} noise results hidden; --include-noise to see)')}")


if __name__ == "__main__":
    main()

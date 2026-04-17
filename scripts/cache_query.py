#!/usr/bin/env python3
"""Query the local ZObject cache built by wikifunctions_cache.py.

Usage:
    python scripts/cache_query.py functions --output Z40
    python scripts/cache_query.py functions --input Z6007 --output Z6092
    python scripts/cache_query.py functions --label "lexeme"

    python scripts/cache_query.py impls Z26184              # implementations of a function
    python scripts/cache_query.py testers Z26184            # testers of a function

    python scripts/cache_query.py references Z866           # every ZObject that mentions Z866
    python scripts/cache_query.py references Z866 --type Z14

    python scripts/cache_query.py show Z26184               # dump the full cached ZObject
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
INDEX_FILE = CACHE_DIR / "_index.jsonl"


def load_index():
    if not INDEX_FILE.exists():
        sys.exit(f"No cache found at {CACHE_DIR}. Run wikifunctions_cache.py --full first.")
    with open(INDEX_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def arg_types(entry):
    return [a.get("type") for a in (entry.get("args") or [])]


def cmd_functions(args):
    """List Z8 functions matching filters on input types, output type, and label."""
    label_re = re.compile(args.label, re.I) if args.label else None
    rows = []
    for e in load_index():
        if e.get("type") != "Z8":
            continue
        if args.output and e.get("output") != args.output:
            continue
        if args.input:
            wanted = set(args.input.split(","))
            if not wanted.issubset(set(arg_types(e))):
                continue
        if label_re and not label_re.search(e.get("label", "")):
            continue
        rows.append(e)

    for e in sorted(rows, key=lambda r: r["zid"]):
        inputs = ", ".join(f"{a.get('label') or a.get('key')}: {a.get('type')}" for a in e.get("args") or [])
        print(f"{e['zid']:10}  {e.get('label','')}")
        print(f"            ({inputs}) -> {e.get('output')}")
        if e.get("impls"):
            print(f"            impls: {', '.join(e['impls'])}")
    print(f"\n{len(rows)} match{'' if len(rows) == 1 else 'es'}", file=sys.stderr)


def cmd_impls(args):
    """Show implementations listed on a function."""
    for e in load_index():
        if e["zid"] == args.zid and e.get("type") == "Z8":
            for impl in e.get("impls") or []:
                impl_entry = _entry_for(impl)
                kind = (impl_entry or {}).get("kind", "?")
                label = (impl_entry or {}).get("label", "")
                print(f"{impl:10}  [{kind}]  {label}")
            return
    sys.exit(f"{args.zid} not found as a Z8 in the index.")


def cmd_testers(args):
    """Show testers listed on a function."""
    for e in load_index():
        if e["zid"] == args.zid and e.get("type") == "Z8":
            for t in e.get("testers") or []:
                t_entry = _entry_for(t)
                label = (t_entry or {}).get("label", "")
                print(f"{t:10}  {label}")
            return
    sys.exit(f"{args.zid} not found as a Z8 in the index.")


def cmd_references(args):
    """Grep the cache for every ZObject that references a given ZID."""
    zid = args.zid
    # rg is much faster than Python's re; use it if available.
    have_rg = subprocess.run(["which", "rg"], capture_output=True).returncode == 0
    pattern = rf'"{zid}"'
    files = []
    if have_rg:
        res = subprocess.run(
            ["rg", "-l", "--glob", "!_index.jsonl", pattern, str(CACHE_DIR)],
            capture_output=True, text=True,
        )
        files = [Path(p).name for p in res.stdout.splitlines()]
    else:
        for p in CACHE_DIR.glob("Z*.json"):
            if pattern in p.read_text():
                files.append(p.name)

    wanted_type = args.type
    out = []
    idx = {e["zid"]: e for e in load_index()}
    for f in files:
        referring_zid = f[:-5]  # strip .json
        if referring_zid == zid:
            continue
        entry = idx.get(referring_zid, {})
        if wanted_type and entry.get("type") != wanted_type:
            continue
        out.append((referring_zid, entry.get("type", "?"), entry.get("label", "")))

    for z, t, label in sorted(out):
        print(f"{z:10}  {t:5}  {label}")
    print(f"\n{len(out)} reference{'' if len(out) == 1 else 's'} to {zid}"
          + (f" (type={wanted_type})" if wanted_type else ""), file=sys.stderr)


def cmd_show(args):
    """Dump the cached ZObject JSON."""
    path = CACHE_DIR / f"{args.zid}.json"
    if not path.exists():
        sys.exit(f"{args.zid} not in cache.")
    print(path.read_text())


def _entry_for(zid):
    for e in load_index():
        if e["zid"] == zid:
            return e
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("functions", help="List Z8 functions by signature / label")
    f.add_argument("--output", help="Exact output type ZID (e.g. Z40)")
    f.add_argument("--input", help="Comma-separated input type ZIDs that must all appear")
    f.add_argument("--label", help="Regex to match against the function label")
    f.set_defaults(func=cmd_functions)

    i = sub.add_parser("impls", help="Show implementations of a function")
    i.add_argument("zid")
    i.set_defaults(func=cmd_impls)

    t = sub.add_parser("testers", help="Show testers of a function")
    t.add_argument("zid")
    t.set_defaults(func=cmd_testers)

    r = sub.add_parser("references", help="Find every ZObject that mentions a given ZID")
    r.add_argument("zid")
    r.add_argument("--type", help="Restrict to ZObjects of this type (e.g. Z14)")
    r.set_defaults(func=cmd_references)

    s = sub.add_parser("show", help="Dump the cached ZObject")
    s.add_argument("zid")
    s.set_defaults(func=cmd_show)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

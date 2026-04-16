#!/usr/bin/env python3
"""Search the Wikifunctions catalog for existing functions.

Usage:
    python scripts/wikifunctions_search.py --search "claim"
    python scripts/wikifunctions_search.py --search "filter" --output-type Z40
    python scripts/wikifunctions_search.py --search "" --input-types Z6007 --output-type Z6092
    python scripts/wikifunctions_search.py --search "multiply" --type Z8
    python scripts/wikifunctions_search.py --search "pitch" --type Z8
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT


def api_get(params):
    params["format"] = "json"
    url = f"{WF_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def search_labels(search, language="en", ztype=None, limit=20):
    """Search ZObjects by label/alias."""
    params = {
        "action": "query",
        "list": "wikilambdasearch_labels",
        "wikilambdasearch_search": search,
        "wikilambdasearch_language": language,
        "wikilambdasearch_limit": str(limit),
    }
    if ztype:
        params["wikilambdasearch_type"] = ztype

    data = api_get(params)
    results = data.get("query", {}).get("wikilambdasearch_labels", [])
    return results


def search_functions(search="", language="en", output_type=None, input_types=None, limit=20):
    """Search functions by name and optionally filter by input/output types."""
    params = {
        "action": "query",
        "list": "wikilambdasearch_functions",
        "wikilambdasearch_functions_search": search,
        "wikilambdasearch_functions_language": language,
        "wikilambdasearch_functions_limit": str(limit),
    }
    if output_type:
        params["wikilambdasearch_functions_output_type"] = output_type
    if input_types:
        params["wikilambdasearch_functions_input_types"] = input_types

    data = api_get(params)
    results = data.get("query", {}).get("wikilambdasearch_functions", [])
    return results


def search_implementations(zfunction_id):
    """Find all implementations for a given function."""
    params = {
        "action": "query",
        "list": "wikilambdafn_search",
        "wikilambdafn_zfunction_id": zfunction_id,
        "wikilambdafn_type": "Z14",
    }
    data = api_get(params)
    return data.get("query", {}).get("wikilambdafn_search", [])


def search_testers(zfunction_id):
    """Find all testers for a given function."""
    params = {
        "action": "query",
        "list": "wikilambdafn_search",
        "wikilambdafn_zfunction_id": zfunction_id,
        "wikilambdafn_type": "Z20",
    }
    data = api_get(params)
    return data.get("query", {}).get("wikilambdafn_search", [])


# Map common type ZIDs to readable names
TYPE_NAMES = {
    "Z6": "String",
    "Z40": "Boolean",
    "Z16683": "Integer",
    "Z13518": "Natural number",
    "Z20838": "Float64",
    "Z6003": "Wikidata Item",
    "Z6007": "Wikidata Claim",
    "Z6092": "Wikidata Property Reference",
    "Z881": "Typed List",
}


def type_display(zid):
    return f"{zid} ({TYPE_NAMES[zid]})" if zid in TYPE_NAMES else zid


def main():
    parser = argparse.ArgumentParser(description="Search the Wikifunctions catalog")
    parser.add_argument("--search", default="", help="Search term for function/object names")
    parser.add_argument("--type", default=None, help="Filter by ZObject type (e.g. Z8 for functions, Z14 for implementations)")
    parser.add_argument("--output-type", default=None, help="Filter functions by output type ZID")
    parser.add_argument("--input-types", default=None, help="Filter functions by input type ZIDs (pipe-separated)")
    parser.add_argument("--implementations", default=None, help="List implementations for a function ZID")
    parser.add_argument("--testers", default=None, help="List testers for a function ZID")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.implementations:
        results = search_implementations(args.implementations)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Implementations for {args.implementations}:")
            for r in results:
                print(f"  {r}")
        return

    if args.testers:
        results = search_testers(args.testers)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Testers for {args.testers}:")
            for r in results:
                print(f"  {r}")
        return

    if args.output_type or args.input_types:
        results = search_functions(
            search=args.search,
            output_type=args.output_type,
            input_types=args.input_types,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(results, indent=2))
            return
        if not results:
            print("No functions found.")
            return
        print(f"Functions matching '{args.search}'" +
              (f" → {type_display(args.output_type)}" if args.output_type else "") +
              (f" (inputs: {args.input_types})" if args.input_types else "") +
              f":")
        for r in results:
            zid = r.get("page_title", "?")
            label = r.get("match_label", "?")
            print(f"  {zid}: {label}")
    else:
        results = search_labels(
            search=args.search,
            ztype=args.type,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps(results, indent=2))
            return
        if not results:
            print("No results found.")
            return
        print(f"Results for '{args.search}'" +
              (f" (type={args.type})" if args.type else "") +
              f":")
        for r in results:
            zid = r.get("page_title", "?")
            label = r.get("match_label", "?")
            ztype = r.get("match_type", "?")
            print(f"  {zid} [{ztype}]: {label}")


if __name__ == "__main__":
    main()

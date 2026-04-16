#!/usr/bin/env python3
"""Fetch ZObjects from Wikifunctions and display human-readable summaries.

Usage:
    python scripts/wikifunctions_fetch.py --zid Z25217
    python scripts/wikifunctions_fetch.py --zid Z25217 --raw
    python scripts/wikifunctions_fetch.py --zid Z25217 --implementations
    python scripts/wikifunctions_fetch.py --zid Z25217 --tree
    python scripts/wikifunctions_fetch.py --zid Z25234 --composition
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT

# Well-known ZIDs for readable output
KNOWN_TYPES = {
    "Z6": "String", "Z40": "Boolean", "Z16683": "Integer", "Z13518": "Natural number",
    "Z20838": "Float64", "Z6003": "Wikidata Item", "Z6007": "Wikidata Claim",
    "Z6092": "Wikidata Property Reference", "Z881": "Typed List", "Z16659": "Sign",
    "Z20825": "Float64 Special Value",
}

KNOWN_ZTYPES = {
    "Z2": "Persistent Object", "Z4": "Type", "Z6": "String", "Z7": "Function Call",
    "Z8": "Function", "Z9": "Reference", "Z11": "Monolingual Text",
    "Z12": "Multilingual Text", "Z14": "Implementation", "Z16": "Code",
    "Z17": "Argument Declaration", "Z18": "Argument Reference", "Z20": "Tester",
    "Z22": "Evaluation Result", "Z31": "Monolingual Stringset",
    "Z32": "Multilingual Stringset",
}


def api_fetch(zids):
    """Fetch one or more ZObjects by ZID."""
    if isinstance(zids, str):
        zids = [zids]
    params = {
        "action": "wikilambda_fetch",
        "zids": "|".join(zids),
        "format": "json",
    }
    url = f"{WF_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    results = {}
    for zid in zids:
        raw = data.get(zid, {}).get("wikilambda_fetch", data.get(zid, ""))
        if isinstance(raw, str):
            try:
                results[zid] = json.loads(raw)
            except json.JSONDecodeError:
                results[zid] = raw
        else:
            results[zid] = raw
    return results


def get_text(multilingual, lang="en"):
    """Extract text from a Z12 multilingual text object."""
    if not isinstance(multilingual, dict):
        return str(multilingual)
    texts = multilingual.get("Z12K1", [])
    if isinstance(texts, list):
        for item in texts:
            if isinstance(item, dict) and item.get("Z11K1") == "Z1002":
                return item.get("Z11K2", "")
        # Fallback to first non-type entry
        for item in texts:
            if isinstance(item, dict) and item.get("Z1K1") == "Z11":
                return item.get("Z11K2", "")
    return ""


def type_display(zid):
    """Human-readable type name."""
    if isinstance(zid, dict):
        # Generic type like Z881 (Typed List)
        z1k1 = zid.get("Z1K1")
        if z1k1 == "Z7":
            fn = zid.get("Z7K1", "?")
            if fn == "Z881":
                element_type = zid.get("Z881K1", "?")
                return f"List of {type_display(element_type)}"
            elif fn == "Z882":
                first = zid.get("Z882K1", "?")
                second = zid.get("Z882K2", "?")
                return f"Pair({type_display(first)}, {type_display(second)})"
            return f"Generic({fn})"
        return str(zid)
    return f"{zid} ({KNOWN_TYPES[zid]})" if zid in KNOWN_TYPES else zid


def describe_function(zobj, zid):
    """Produce a human-readable summary of a Z8 function."""
    inner = zobj.get("Z2K2", zobj)
    name = get_text(zobj.get("Z2K3", {}))
    desc = get_text(zobj.get("Z2K5", {}))

    print(f"=== {zid}: {name} ===")
    if desc:
        print(f"Description: {desc}")
    print()

    # Arguments
    args = inner.get("Z8K1", [])
    print("Inputs:")
    for arg in args:
        if isinstance(arg, str):
            continue  # skip type marker
        arg_type = arg.get("Z17K1", "?")
        arg_key = arg.get("Z17K2", "?")
        arg_label = get_text(arg.get("Z17K3", {}))
        print(f"  {arg_key} ({arg_label}): {type_display(arg_type)}")

    # Return type
    ret_type = inner.get("Z8K2", "?")
    print(f"\nOutput: {type_display(ret_type)}")

    # Testers
    testers = inner.get("Z8K3", [])
    tester_zids = [t for t in testers if isinstance(t, str) and t.startswith("Z") and t != "Z20"]
    if tester_zids:
        print(f"\nTesters: {', '.join(tester_zids)}")

    # Implementations
    impls = inner.get("Z8K4", [])
    impl_zids = [i for i in impls if isinstance(i, str) and i.startswith("Z") and i != "Z14"]
    if impl_zids:
        print(f"Implementations: {', '.join(impl_zids)}")


def describe_implementation(zobj, zid):
    """Describe an implementation - composition or code."""
    inner = zobj.get("Z2K2", zobj)
    name = get_text(zobj.get("Z2K3", {}))
    fn_ref = inner.get("Z14K1", "?")

    print(f"=== {zid}: {name} ===")
    print(f"Implements: {fn_ref}")

    # Check implementation type
    if "Z14K2" in inner:
        # Composition
        print(f"Type: Composition")
        print()
        print("Composition structure:")
        print_composition(inner["Z14K2"], indent=2)
    elif "Z14K3" in inner:
        # Code
        code_obj = inner["Z14K3"]
        lang = code_obj.get("Z16K1", "?")
        code = code_obj.get("Z16K2", "")
        print(f"Type: Code ({lang})")
        print()
        print("Code:")
        print(code)


def print_composition(node, indent=0, arg_context=None):
    """Recursively print a composition tree in readable form."""
    prefix = " " * indent
    if isinstance(node, str):
        print(f"{prefix}{node}")
        return

    if not isinstance(node, dict):
        print(f"{prefix}{node}")
        return

    z1k1 = node.get("Z1K1")

    if z1k1 == "Z18":
        # Argument reference
        arg_key = node.get("Z18K1", "?")
        print(f"{prefix}→ argument {arg_key}")
        return

    if z1k1 == "Z7":
        # Function call
        fn = node.get("Z7K1", "?")
        print(f"{prefix}call {fn}:")
        for key, val in node.items():
            if key in ("Z1K1", "Z7K1"):
                continue
            print(f"{prefix}  {key} =")
            print_composition(val, indent + 4)
        return

    if z1k1 == "Z9":
        # Reference
        ref = node.get("Z9K1", "?")
        print(f"{prefix}ref {ref}")
        return

    if z1k1 == "Z6":
        # String literal
        val = node.get("Z6K1", "?")
        print(f'{prefix}"{val}"')
        return

    # Other typed objects (like float64 literals, integers, etc.)
    type_name = KNOWN_TYPES.get(z1k1, z1k1)
    # Check if it looks like a literal value
    keys = [k for k in node.keys() if k != "Z1K1"]
    if len(keys) <= 4:
        vals = {}
        for k in keys:
            v = node[k]
            if isinstance(v, dict):
                inner_type = v.get("Z1K1", "")
                if inner_type == "Z6":
                    vals[k] = v.get("Z6K1", "?")
                elif inner_type in KNOWN_ZTYPES:
                    vals[k] = f"[{KNOWN_ZTYPES.get(inner_type, inner_type)}]"
                else:
                    vals[k] = f"[{inner_type}...]"
            elif isinstance(v, str):
                vals[k] = v
            else:
                vals[k] = str(v)
        val_str = ", ".join(f"{k}={v}" for k, v in vals.items())
        print(f"{prefix}{type_name}({val_str})")
    else:
        print(f"{prefix}{type_name}:")
        for key, val in node.items():
            if key == "Z1K1":
                continue
            print(f"{prefix}  {key} =")
            print_composition(val, indent + 4)


def show_dependency_tree(zid, depth=0, visited=None, max_depth=None):
    """Recursively show the dependency tree of a function."""
    if visited is None:
        visited = set()
    if max_depth is not None and depth > max_depth:
        return
    if zid in visited:
        print("  " * depth + f"{zid} (already shown)")
        return
    visited.add(zid)

    data = api_fetch(zid)
    zobj = data.get(zid, {})
    inner = zobj.get("Z2K2", zobj)
    z1k1 = inner.get("Z1K1")
    name = get_text(zobj.get("Z2K3", {}))

    if z1k1 == "Z8":
        # Function - show it and recurse into first composition implementation only
        print("  " * depth + f"{zid}: {name} [Function]")
        impls = inner.get("Z8K4", [])
        impl_zids = [i for i in impls if isinstance(i, str) and i.startswith("Z") and i != "Z14"]
        if impl_zids:
            # Only follow the first implementation to avoid explosion
            show_dependency_tree(impl_zids[0], depth + 1, visited, max_depth)
            if len(impl_zids) > 1:
                print("  " * (depth + 1) + f"(+{len(impl_zids) - 1} more implementations)")

    elif z1k1 == "Z14":
        # Implementation
        fn_ref = inner.get("Z14K1", "?")
        if "Z14K2" in inner:
            print("  " * depth + f"{zid}: {name} [Composition]")
            # Find all function calls in the composition
            called_fns = extract_function_calls(inner["Z14K2"])
            for fn_zid in called_fns:
                if fn_zid not in visited:
                    show_dependency_tree(fn_zid, depth + 1, visited, max_depth)
        elif "Z14K3" in inner:
            lang = inner["Z14K3"].get("Z16K1", "?")
            print("  " * depth + f"{zid}: {name} [Code: {lang}]")
        else:
            print("  " * depth + f"{zid}: {name} [Builtin]")
    else:
        print("  " * depth + f"{zid}: {name} [{z1k1}]")


def extract_function_calls(node):
    """Extract all function ZIDs called in a composition tree."""
    fns = set()
    if isinstance(node, dict):
        if node.get("Z1K1") == "Z7":
            fn = node.get("Z7K1", "")
            if isinstance(fn, str) and fn.startswith("Z"):
                fns.add(fn)
        for val in node.values():
            fns.update(extract_function_calls(val))
    elif isinstance(node, list):
        for item in node:
            fns.update(extract_function_calls(item))
    return fns


def main():
    parser = argparse.ArgumentParser(description="Fetch and describe Wikifunctions ZObjects")
    parser.add_argument("--zid", required=True, help="ZID to fetch (e.g. Z25217)")
    parser.add_argument("--raw", action="store_true", help="Show raw ZObject JSON")
    parser.add_argument("--implementations", action="store_true", help="Fetch and describe all implementations")
    parser.add_argument("--tree", action="store_true", help="Show dependency tree")
    parser.add_argument("--depth", type=int, default=None, help="Max depth for --tree (default: unlimited)")
    parser.add_argument("--composition", action="store_true", help="Show composition structure (for implementations)")

    args = parser.parse_args()

    data = api_fetch(args.zid)
    zobj = data.get(args.zid, {})

    if not zobj:
        print(f"ZObject {args.zid} not found.")
        return

    if args.raw:
        print(json.dumps(zobj, indent=2, ensure_ascii=False))
        return

    if args.tree:
        print(f"Dependency tree for {args.zid}:")
        show_dependency_tree(args.zid, max_depth=args.depth)
        return

    inner = zobj.get("Z2K2", zobj)
    z1k1 = inner.get("Z1K1")

    if z1k1 == "Z8":
        describe_function(zobj, args.zid)

        if args.implementations:
            impls = inner.get("Z8K4", [])
            impl_zids = [i for i in impls if isinstance(i, str) and i.startswith("Z") and i != "Z14"]
            if impl_zids:
                impl_data = api_fetch(impl_zids)
                for impl_zid in impl_zids:
                    print()
                    print("-" * 40)
                    impl_obj = impl_data.get(impl_zid, {})
                    if impl_obj:
                        describe_implementation(impl_obj, impl_zid)
    elif z1k1 == "Z14":
        describe_implementation(zobj, args.zid)
    elif z1k1 == "Z20":
        name = get_text(zobj.get("Z2K3", {}))
        fn_ref = inner.get("Z20K1", "?")
        print(f"=== {args.zid}: {name} ===")
        print(f"Tests function: {fn_ref}")
        print()
        print("Test call:")
        print_composition(inner.get("Z20K2", {}), indent=2)
        print()
        print("Validator:")
        print_composition(inner.get("Z20K3", {}), indent=2)
    else:
        name = get_text(zobj.get("Z2K3", {}))
        desc = get_text(zobj.get("Z2K5", {}))
        print(f"=== {args.zid}: {name} ===")
        print(f"Type: {KNOWN_ZTYPES.get(z1k1, z1k1)}")
        if desc:
            print(f"Description: {desc}")
        print()
        print(json.dumps(inner, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

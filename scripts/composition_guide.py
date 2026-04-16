#!/usr/bin/env python3
"""Generate composition tree diagrams and step-by-step UI build instructions.

Takes a JSON composition tree on stdin and outputs:
1. A visual tree diagram (matching CLAUDE.md format)
2. Numbered step-by-step instructions for the Wikifunctions composition editor

Usage:
    echo '<json>' | python scripts/composition_guide.py          # both outputs
    echo '<json>' | python scripts/composition_guide.py --tree    # tree only
    echo '<json>' | python scripts/composition_guide.py --steps   # steps only
    python scripts/composition_guide.py --zid Z33573             # read from Z33573.comp.json

Input format (JSON):
    {
      "call": "Z28297",
      "args": {
        "Z28297K1": {
          "call": "Z811",
          "args": {
            "Z811K1": {"ref": "qualifier"}
          }
        }
      }
    }

Node types:
    {"call": "Z#####", "args": {...}}  - Function call with arguments
    {"ref": "input_name"}              - Argument reference (wire to parent function input)
    {"literal": "P2144", "type": "Z6092"}  - Literal value
    {"literal": "Q96254322", "type": "Z6091"}  - Literal item reference
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT


def api_fetch(zids):
    """Fetch one or more ZObjects by ZID."""
    if isinstance(zids, str):
        zids = [zids]
    if not zids:
        return {}
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
        for item in texts:
            if isinstance(item, dict) and item.get("Z1K1") == "Z11":
                return item.get("Z11K2", "")
    return ""


def collect_zids(node):
    """Recursively collect all ZIDs referenced in a composition tree."""
    zids = set()
    if isinstance(node, dict):
        if "call" in node:
            zids.add(node["call"])
            for arg_node in node.get("args", {}).values():
                zids |= collect_zids(arg_node)
    return zids


def get_function_info(zobj):
    """Extract function name and argument labels from a fetched ZObject."""
    inner = zobj.get("Z2K2", zobj)
    name = get_text(zobj.get("Z2K3", {}))
    args = {}
    for arg in inner.get("Z8K1", []):
        if isinstance(arg, dict):
            key = arg.get("Z17K2", "")
            label = get_text(arg.get("Z17K3", {}))
            args[key] = label
    return name, args


# --- Tree diagram generation ---

def generate_tree(tree, func_info, parent_arg_label=None, prefix="", is_last=True, is_root=True):
    """Walk the composition tree and yield lines for a visual tree diagram."""
    if "call" in tree:
        zid = tree["call"]
        name, arg_labels = func_info.get(zid, (zid, {}))

        if is_root:
            yield f"{zid}: {name}"
            child_prefix = ""
        else:
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            yield f"{prefix}{connector}{parent_arg_label} ({arg_labels.get(list(tree.get('args', {}).keys())[0], parent_arg_label) if False else parent_arg_label}):"
            # Re-yield with function name on next line? No — put arg label and function on same context
            # Actually, match the CLAUDE.md format: arg label on one line, function on next
            pass

        # For non-root, we already yielded the argument label line.
        # Now yield the function name line and recurse into its arguments.
        if not is_root:
            continuation = "    " if is_last else "\u2502   "
            inner_prefix = prefix + continuation
            yield f"{inner_prefix}{zid}: {name}"
        else:
            inner_prefix = ""

        args = list(tree.get("args", {}).items())
        for i, (arg_key, arg_node) in enumerate(args):
            label = arg_labels.get(arg_key, arg_key)
            last = (i == len(args) - 1)
            yield from generate_tree_arg(arg_node, func_info, label, inner_prefix, last)

    elif "ref" in tree:
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        yield f"{prefix}{connector}{parent_arg_label}: \u2190 input: {tree['ref']}"

    elif "literal" in tree:
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        yield f"{prefix}{connector}{parent_arg_label}: {tree['literal']} (literal {tree.get('type', '')})"


def generate_tree_arg(tree, func_info, arg_label, prefix, is_last):
    """Generate tree lines for a single argument node."""
    connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
    continuation = "    " if is_last else "\u2502   "
    inner_prefix = prefix + continuation

    if "call" in tree:
        zid = tree["call"]
        name, arg_labels = func_info.get(zid, (zid, {}))

        yield f"{prefix}{connector}{arg_label}:"
        yield f"{inner_prefix}{zid}: {name}"

        args = list(tree.get("args", {}).items())
        for i, (arg_key, arg_node) in enumerate(args):
            label = arg_labels.get(arg_key, arg_key)
            last = (i == len(args) - 1)
            yield from generate_tree_arg(arg_node, func_info, label, inner_prefix, last)

    elif "ref" in tree:
        yield f"{prefix}{connector}{arg_label}: \u2190 input: {tree['ref']}"

    elif "literal" in tree:
        yield f"{prefix}{connector}{arg_label}: {tree['literal']} (literal {tree.get('type', '')})"

    else:
        yield f"{prefix}{connector}{arg_label}: (unknown: {tree})"


# --- Step-by-step instructions ---

def generate_steps(tree, func_info, parent_arg_label=None, depth=0):
    """Walk the composition tree top-down and yield instruction steps."""
    indent = "  " * depth

    if "call" in tree:
        zid = tree["call"]
        name, arg_labels = func_info.get(zid, (zid, {}))

        if depth == 0:
            yield f"Set root function call to {zid} ({name})"
        else:
            yield f"{indent}\"{parent_arg_label}\" \u2192 change type to Function Call \u2192 select {zid} ({name})"

        args = tree.get("args", {})
        for arg_key, arg_node in args.items():
            label = arg_labels.get(arg_key, arg_key)
            yield from generate_steps(arg_node, func_info, parent_arg_label=label, depth=depth + 1)

    elif "ref" in tree:
        ref_name = tree["ref"]
        yield f"{indent}\"{parent_arg_label}\" \u2192 change type to Argument Reference \u2192 select \"{ref_name}\""

    elif "literal" in tree:
        lit_type = tree.get("type", "?")
        lit_value = tree["literal"]
        yield f"{indent}\"{parent_arg_label}\" \u2192 set literal {lit_type} value: {lit_value}"

    else:
        yield f"{indent}\"{parent_arg_label}\" \u2192 (unknown node: {tree})"


def main():
    parser = argparse.ArgumentParser(description="Generate composition tree diagrams and UI instructions")
    parser.add_argument("--zid", help="Read from <ZID>.comp.json file")
    parser.add_argument("--tree", action="store_true", help="Output only the tree diagram")
    parser.add_argument("--steps", action="store_true", help="Output only the step-by-step instructions")
    args = parser.parse_args()

    if args.zid:
        filename = f"{args.zid}.comp.json"
        with open(filename) as f:
            tree = json.load(f)
    else:
        tree = json.load(sys.stdin)

    # Collect and fetch all function metadata
    zids = collect_zids(tree)
    print(f"Fetching metadata for {len(zids)} functions...", file=sys.stderr)
    raw = api_fetch(list(zids))
    func_info = {}
    for zid, zobj in raw.items():
        func_info[zid] = get_function_info(zobj)

    show_both = not args.tree and not args.steps

    # Tree diagram
    if args.tree or show_both:
        print()
        for line in generate_tree(tree, func_info):
            print(f"  {line}")

    if show_both:
        print()
        print("  ---")

    # Step-by-step instructions
    if args.steps or show_both:
        print()
        for i, step in enumerate(generate_steps(tree, func_info), 1):
            print(f"  {i}. {step}")
        print()
        print("  Save.")


if __name__ == "__main__":
    main()

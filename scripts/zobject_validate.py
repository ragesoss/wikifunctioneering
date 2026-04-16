#!/usr/bin/env python3
"""Validate ZObject structure and check references.

Usage:
    echo '{"Z1K1": "Z7", ...}' | python scripts/zobject_validate.py
    python scripts/zobject_validate.py --file draft.json
    python scripts/zobject_validate.py --file draft.json --check-refs
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT


# Valid top-level ZObject types
VALID_TYPES = {
    "Z1", "Z2", "Z4", "Z5", "Z6", "Z7", "Z8", "Z9", "Z11", "Z12",
    "Z14", "Z16", "Z17", "Z18", "Z20", "Z22", "Z24", "Z31", "Z32",
    "Z40", "Z46", "Z64", "Z86", "Z99",
}

# Required keys per type
REQUIRED_KEYS = {
    "Z2": {"Z2K1", "Z2K2"},  # Persistent object: ID + value
    "Z6": {"Z6K1"},           # String: string value
    "Z7": {"Z7K1"},           # Function call: function reference
    "Z8": {"Z8K1", "Z8K2"},   # Function: arguments + return type
    "Z9": {"Z9K1"},           # Reference: reference ID
    "Z11": {"Z11K1", "Z11K2"}, # Monolingual text: language + text
    "Z14": {"Z14K1"},         # Implementation: function ref (+ one of Z14K2/K3/K4)
    "Z16": {"Z16K1", "Z16K2"}, # Code: language + code string
    "Z17": {"Z17K1", "Z17K2"}, # Argument declaration: type + key ID
    "Z18": {"Z18K1"},         # Argument reference: key ID
    "Z20": {"Z20K1", "Z20K2", "Z20K3"}, # Tester: function + call + validator
}


class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []

    def error(self, path, msg):
        self.errors.append(f"ERROR at {path}: {msg}")

    def warn(self, path, msg):
        self.warnings.append(f"WARNING at {path}: {msg}")

    def note(self, path, msg):
        self.info.append(f"INFO at {path}: {msg}")

    def ok(self):
        return len(self.errors) == 0

    def report(self):
        for msg in self.errors:
            print(f"  {msg}")
        for msg in self.warnings:
            print(f"  {msg}")
        for msg in self.info:
            print(f"  {msg}")


def validate_node(node, path, result, declared_args=None):
    """Recursively validate a ZObject node."""
    if declared_args is None:
        declared_args = set()

    if isinstance(node, str):
        # Canonical shorthand - a bare string is valid as a reference or string value
        return

    if isinstance(node, list):
        # Typed list - first element should be a type reference
        if len(node) == 0:
            result.error(path, "Empty list (must have at least a type element)")
            return
        for i, item in enumerate(node):
            validate_node(item, f"{path}[{i}]", result, declared_args)
        return

    if not isinstance(node, dict):
        result.error(path, f"Unexpected type: {type(node).__name__}")
        return

    # Must have Z1K1 (type)
    z1k1 = node.get("Z1K1")
    if z1k1 is None:
        result.error(path, "Missing Z1K1 (type field)")
        return

    # Resolve type
    obj_type = z1k1 if isinstance(z1k1, str) else z1k1.get("Z9K1") if isinstance(z1k1, dict) else None

    # Check required keys
    if obj_type in REQUIRED_KEYS:
        for req_key in REQUIRED_KEYS[obj_type]:
            if req_key not in node:
                result.error(path, f"Type {obj_type} requires key {req_key}")

    # Type-specific validation
    if obj_type == "Z7":
        # Function call - Z7K1 must be a function reference
        fn_ref = node.get("Z7K1")
        if fn_ref is not None:
            if isinstance(fn_ref, str) and not fn_ref.startswith("Z"):
                result.error(path, f"Z7K1 should be a ZID reference, got: {fn_ref}")

    elif obj_type == "Z18":
        # Argument reference - check it's declared
        arg_key = node.get("Z18K1")
        if arg_key and declared_args and arg_key not in declared_args:
            result.warn(path, f"Argument reference {arg_key} not found in declared arguments: {declared_args}")

    elif obj_type == "Z8":
        # Function - collect declared argument keys
        args = node.get("Z8K1", [])
        for arg in args:
            if isinstance(arg, dict):
                arg_key = arg.get("Z17K2")
                if arg_key:
                    declared_args.add(arg_key)

    elif obj_type == "Z14":
        # Implementation - collect args from the function it implements
        fn_ref = node.get("Z14K1")
        # For compositions, validate the composition body
        if "Z14K2" in node:
            validate_node(node["Z14K2"], f"{path}.Z14K2", result, declared_args)
            return  # Don't double-recurse

    elif obj_type == "Z6":
        val = node.get("Z6K1")
        if val is not None and not isinstance(val, str):
            result.error(path, f"Z6K1 (string value) should be a string, got: {type(val).__name__}")

    # Recurse into all child values
    for key, val in node.items():
        if key == "Z1K1":
            continue
        validate_node(val, f"{path}.{key}", result, declared_args)


def check_remote_refs(node, path, result, checked=None):
    """Check that ZID references actually exist on Wikifunctions."""
    if checked is None:
        checked = {}

    refs_to_check = set()
    collect_refs(node, refs_to_check)

    # Filter to only ZIDs we haven't checked
    new_refs = refs_to_check - set(checked.keys())
    if not new_refs:
        return

    # Batch check in groups of 20
    for batch_start in range(0, len(new_refs), 20):
        batch = list(new_refs)[batch_start:batch_start + 20]
        try:
            params = {
                "action": "wikilambda_fetch",
                "zids": "|".join(batch),
                "format": "json",
            }
            url = f"{WF_API}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())

            for zid in batch:
                if zid in data:
                    checked[zid] = True
                else:
                    checked[zid] = False
                    result.error("refs", f"ZID {zid} not found on Wikifunctions")
        except Exception as e:
            result.warn("refs", f"Could not verify refs {batch}: {e}")


def collect_refs(node, refs):
    """Collect all ZID references from a ZObject tree."""
    if isinstance(node, str):
        if node.startswith("Z") and node[1:].isdigit():
            refs.add(node)
        return
    if isinstance(node, list):
        for item in node:
            collect_refs(item, refs)
        return
    if isinstance(node, dict):
        for key, val in node.items():
            # Keys themselves reference types
            if key.startswith("Z") and "K" in key:
                base_zid = key.split("K")[0]
                if base_zid[1:].isdigit():
                    refs.add(base_zid)
            collect_refs(val, refs)


def main():
    parser = argparse.ArgumentParser(description="Validate ZObject structure")
    parser.add_argument("--file", help="JSON file to validate (reads stdin if omitted)")
    parser.add_argument("--check-refs", action="store_true", help="Verify ZID references exist on Wikifunctions")

    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    try:
        zobj = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        sys.exit(1)

    result = ValidationResult()
    validate_node(zobj, "root", result)

    if args.check_refs:
        print("Checking remote references...")
        check_remote_refs(zobj, "root", result)

    if result.ok() and not result.warnings and not result.info:
        print("Valid ZObject structure.")
    else:
        if result.errors:
            print(f"Found {len(result.errors)} error(s):")
        if result.warnings:
            print(f"Found {len(result.warnings)} warning(s):")
        result.report()

    sys.exit(0 if result.ok() else 1)


if __name__ == "__main__":
    main()

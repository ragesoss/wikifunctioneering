#!/usr/bin/env python3
"""Generate Wikifunctions tester ZObject JSON from a simple spec.

Outputs JSON suitable for creating a Z20 (Tester) on Wikifunctions.

Usage:
    echo '<json>' | python scripts/tester_generate.py
    python scripts/tester_generate.py < test_spec.json

Input format (JSON):
    {
      "function": "Z33573",
      "args": {
        "Z33573K1": {"fetch_item": "Q2610210"},
        "Z33573K2": {"property": "P2144"},
        "Z33573K3": {"property": "P518"}
      },
      "validator": "Z19316",
      "expected": {"item_ref": "Q96254322"}
    }

Argument value types:
    {"fetch_item": "Q12345"}     - Wikidata item fetched via Z6821 (common for Z6001 inputs)
    {"item_ref": "Q12345"}       - Literal Z6091 item reference
    {"property": "P12345"}       - Literal Z6092 property reference
    {"string": "hello"}          - Literal Z6 string
    {"integer": 42}              - Literal integer (positive only for now)
    {"boolean": true}            - Literal Z40 boolean
    {"call": {...}}              - Arbitrary function call (same format as composition_guide.py)

Validator + expected:
    The validator function is called with the function result as its first argument
    and the expected value as its second. Common validators:
    - Z19316 (item references equal) with {"item_ref": "Q..."}
    - Z866 (equals) with various types
    - Z20924 (float64 equality) with float values

Example — test that Z33573(A440, P2144, P518) returns A4:
    {
      "function": "Z33573",
      "args": {
        "Z33573K1": {"fetch_item": "Q2610210"},
        "Z33573K2": {"property": "P2144"},
        "Z33573K3": {"property": "P518"}
      },
      "validator": "Z19316",
      "expected": {"item_ref": "Q96254322"}
    }
"""

import json
import sys


def build_value(spec):
    """Convert a simplified value spec to a ZObject."""
    if isinstance(spec, dict):
        if "fetch_item" in spec:
            return {
                "Z1K1": "Z7",
                "Z7K1": "Z6821",
                "Z6821K1": {
                    "Z1K1": "Z6091",
                    "Z6091K1": spec["fetch_item"]
                }
            }
        elif "item_ref" in spec:
            return {
                "Z1K1": "Z6091",
                "Z6091K1": spec["item_ref"]
            }
        elif "property" in spec:
            return {
                "Z1K1": "Z6092",
                "Z6092K1": spec["property"]
            }
        elif "string" in spec:
            return {
                "Z1K1": "Z6",
                "Z6K1": spec["string"]
            }
        elif "integer" in spec:
            val = spec["integer"]
            sign = "Z16660" if val >= 0 else "Z16661"
            return {
                "Z1K1": "Z16683",
                "Z16683K1": {
                    "Z1K1": "Z16659",
                    "Z16659K1": sign
                },
                "Z16683K2": {
                    "Z1K1": "Z13518",
                    "Z13518K1": str(abs(val))
                }
            }
        elif "boolean" in spec:
            return "Z41" if spec["boolean"] else "Z42"
        elif "call" in spec:
            return build_call(spec)
        else:
            raise ValueError(f"Unknown value spec: {spec}")
    else:
        raise ValueError(f"Value spec must be a dict, got: {spec}")


def build_call(spec):
    """Convert a function call spec to a ZObject."""
    zid = spec["call"]
    result = {
        "Z1K1": "Z7",
        "Z7K1": zid,
    }
    for arg_key, arg_spec in spec.get("args", {}).items():
        result[arg_key] = build_value(arg_spec)
    return result


def build_tester(spec):
    """Build a complete Z20 tester ZObject from a spec."""
    function_zid = spec["function"]
    validator_zid = spec["validator"]

    # Build the function call (Z20K2)
    test_call = {
        "Z1K1": "Z7",
        "Z7K1": function_zid,
    }
    for arg_key, arg_spec in spec.get("args", {}).items():
        test_call[arg_key] = build_value(arg_spec)

    # Build the validator call (Z20K3)
    # The validator's first argument (K1) receives the function result automatically.
    # We set the second argument (K2) to the expected value.
    expected = build_value(spec["expected"])
    validator_call = {
        "Z1K1": "Z7",
        "Z7K1": validator_zid,
    }
    # The second argument key is <validator_zid>K2
    validator_call[f"{validator_zid}K2"] = expected

    # Assemble the tester
    tester = {
        "Z1K1": "Z20",
        "Z20K1": function_zid,
        "Z20K2": test_call,
        "Z20K3": validator_call,
    }

    return tester


def main():
    spec = json.load(sys.stdin)

    if isinstance(spec, list):
        # Multiple test specs
        for s in spec:
            print(json.dumps(build_tester(s), indent=2))
            print()
    else:
        print(json.dumps(build_tester(spec), indent=2))


if __name__ == "__main__":
    main()

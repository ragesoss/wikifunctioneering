#!/usr/bin/env python3
"""Run a composition directly via the API without creating it on Wikifunctions.

Builds a nested function call from the composition tree and test inputs,
executes it as a single API call, and shows the result. Use this to
prototype and validate compositions before implementing them.

Usage:
    # Run with inline inputs:
    python scripts/composition_run.py zobjects/frequency_of_pitch.comp.json \
      --inputs '{"pitch class": "A", "octave": 4, "pitch standard": {"fetch": "Q17087764"}}'

    # Run with inputs from a file:
    python scripts/composition_run.py zobjects/my.comp.json --inputs-file test_inputs.json

    # Show the generated API call without executing:
    python scripts/composition_run.py zobjects/my.comp.json --inputs '...' --dry-run

Input format (same as composition_debug.py):
    - string: "C"
    - integer: 4
    - fetch item: {"fetch": "Q2610210"}
    - typed ref: {"ref": "Z6092", "value": "P361"}
    - raw ZObject: {"Z1K1": "Z6001", ...}
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT


def api_call(zobject):
    """Execute a function call via the Wikifunctions API."""
    data = urllib.parse.urlencode({
        'action': 'wikilambda_function_call',
        'format': 'json',
        'wikilambda_function_call_zobject': json.dumps(zobject),
    }).encode()
    req = urllib.request.Request(WF_API, data=data, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    return json.loads(result['wikilambda_function_call']['data'])


def encode_input(value):
    """Convert a user-friendly input value to a ZObject."""
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        sign = 'Z16660' if value >= 0 else 'Z16661'
        return {
            'Z1K1': 'Z16683',
            'Z16683K1': {'Z1K1': 'Z16659', 'Z16659K1': sign},
            'Z16683K2': {'Z1K1': 'Z13518', 'Z13518K1': str(abs(value))},
        }
    if isinstance(value, float):
        # Pass as string — the API can parse it
        return str(value)
    if isinstance(value, dict):
        if 'Z1K1' in value:
            return value
        if 'fetch' in value:
            return {
                'Z1K1': 'Z7',
                'Z7K1': 'Z6821',
                'Z6821K1': {'Z1K1': 'Z6091', 'Z6091K1': value['fetch']},
            }
        if 'ref' in value and 'value' in value:
            return {'Z1K1': value['ref'], f"{value['ref']}K1": value['value']}
    raise ValueError(f"Don't know how to encode: {value}")


def build_call(node, inputs):
    """Recursively build a Z7 function call from a composition node."""
    if 'call' in node:
        zid = node['call']
        call = {'Z1K1': 'Z7', 'Z7K1': zid}
        for arg_key, arg_node in (node.get('args') or {}).items():
            call[arg_key] = build_call(arg_node, inputs)
        return call
    if 'ref' in node:
        ref_name = node['ref']
        if ref_name not in inputs:
            raise ValueError(f"Missing test input for argument reference '{ref_name}'")
        return encode_input(inputs[ref_name])
    if 'literal' in node:
        lit_type = node.get('type', 'Z6')
        value = node['literal']
        # Integer literals need the full sign + natural number structure
        if lit_type == 'Z16683':
            return encode_input(int(value))
        return {'Z1K1': lit_type, f"{lit_type}K1": value}
    raise ValueError(f"Unknown node type: {node}")


def format_result(result):
    """Format a result for display by converting it to a string via the API."""
    val = result.get('Z22K1', result)

    if isinstance(val, str):
        return val
    if not isinstance(val, dict):
        return str(val)

    # Use Z11303 (object to string representation) or try simple extraction
    t = val.get('Z1K1', '?')

    # Simple types we can format directly
    if t == 'Z6':
        return val.get('Z6K1', '?')
    if t == 'Z40':
        return 'true' if val.get('Z40K1') == 'Z41' else 'false'
    if t == 'Z6091':
        return val.get('Z6091K1', '?')
    if t == 'Z6092':
        return val.get('Z6092K1', '?')

    # For numeric types, convert via API using Z25073 (integer to string)
    # or Z20923 (float64 to string)
    converter = None
    if t == 'Z16683':
        converter = 'Z25073'  # integer to string
    elif t == 'Z20838':
        converter = 'Z20844'  # float64 to string (JS conventions)

    if converter:
        try:
            call = {'Z1K1': 'Z7', 'Z7K1': converter, f'{converter}K1': val}
            str_result = api_call(call)
            str_val = str_result.get('Z22K1', str_result)
            if isinstance(str_val, str):
                return str_val
            if isinstance(str_val, dict) and str_val.get('Z1K1') == 'Z6':
                return str_val.get('Z6K1', '?')
        except Exception:
            pass

    return f"({t})"


def extract_error(result):
    """Extract error info from a failed result."""
    pairs = result.get('Z22K2', {}).get('K1', [])
    for p in pairs:
        if isinstance(p, dict) and p.get('K1') == 'errors':
            err = p['K2']
            if isinstance(err, dict):
                etype = err.get('Z5K1', '?')
                if etype == 'Z500':
                    return err.get('Z5K2', {}).get('Z500K1', str(err))
                if etype == 'Z516':
                    key = err.get('Z5K2', {}).get('Z516K1', {})
                    if isinstance(key, dict):
                        key = key.get('Z39K1', str(key))
                    return f"Argument value error on {key}"
                if etype == 'Z511':
                    key = err.get('Z5K2', {}).get('Z511K1', {})
                    if isinstance(key, dict):
                        key = key.get('Z39K1', str(key))
                    return f"Key not found: {key}"
            return json.dumps(err)[:300]
    return 'unknown error'


def main():
    parser = argparse.ArgumentParser(
        description='Run a composition directly via the API'
    )
    parser.add_argument('spec_file', help='Composition JSON spec file')
    parser.add_argument('--inputs', help='Test inputs as JSON string')
    parser.add_argument('--inputs-file', help='Test inputs from a JSON file')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show the API call without executing')
    parser.add_argument('--raw', action='store_true',
                        help='Show raw ZObject result instead of formatted')
    args = parser.parse_args()

    spec = json.loads(open(args.spec_file).read())
    composition = spec['composition']

    if args.inputs_file:
        inputs = json.loads(open(args.inputs_file).read())
    elif args.inputs:
        inputs = json.loads(args.inputs)
    else:
        print('Error: provide --inputs or --inputs-file', file=sys.stderr)
        sys.exit(1)

    call = build_call(composition, inputs)

    if args.dry_run:
        print(json.dumps(call, indent=2))
        return

    print('Executing...', file=sys.stderr)
    result = api_call(call)

    if result.get('Z22K1') == 'Z24':
        msg = extract_error(result)
        print(f"ERROR: {msg}", file=sys.stderr)
        if args.raw:
            print(json.dumps(result, indent=2))
        sys.exit(1)
    else:
        if args.raw:
            print(json.dumps(result.get('Z22K1', result), indent=2))
        else:
            print(format_result(result))


if __name__ == '__main__':
    main()

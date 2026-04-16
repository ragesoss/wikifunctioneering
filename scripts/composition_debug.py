#!/usr/bin/env python3
"""Debug a composition by testing each sub-tree in the chain.

Given a composition JSON spec and test inputs, executes each function
call in the tree from leaves to root, reporting which step fails first.

Usage:
    python scripts/composition_debug.py zobjects/my.comp.json --inputs '{"pitch class": "C", "octave": 4, "pitch standard": {"fetch": "Q17087764"}}'

    # Or with a JSON file for inputs:
    python scripts/composition_debug.py zobjects/my.comp.json --inputs-file test_inputs.json

Input format for --inputs:
    A JSON object mapping argument labels to values. Values can be:
    - A string: passed as Z6 (String)
    - An integer: passed as Z16683 (Integer)
    - A float: passed as Z20838 (Float64)
    - {"fetch": "Q12345"}: calls Z6821 to fetch a Wikidata item (Z6001)
    - {"ref": "Z6091", "value": "Q12345"}: literal typed reference
    - {"ref": "Z6092", "value": "P361"}: literal property reference
    - A raw ZObject dict (if it contains Z1K1)
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
    inner = json.loads(result['wikilambda_function_call']['data'])
    return inner


def is_error(result):
    """Check if an API result is an error (Z22 with Z24 void value)."""
    return (isinstance(result, dict)
            and result.get('Z22K1') == 'Z24')


def extract_error_message(result):
    """Pull a human-readable error from a failed result."""
    pairs = result.get('Z22K2', {}).get('K1', [])
    for p in pairs:
        if isinstance(p, dict) and p.get('K1') == 'errors':
            err = p['K2']
            # Z500 = generic error with message
            if isinstance(err, dict) and err.get('Z5K1') == 'Z500':
                return err.get('Z5K2', {}).get('Z500K1', str(err))
            # Z516 = argument value error
            if isinstance(err, dict) and err.get('Z5K1') == 'Z516':
                key = err.get('Z5K2', {}).get('Z516K1', {})
                if isinstance(key, dict):
                    key = key.get('Z39K1', str(key))
                return f"Argument value error on {key}"
            # Z511 = key not found
            if isinstance(err, dict) and err.get('Z5K1') == 'Z511':
                key = err.get('Z5K2', {}).get('Z511K1', {})
                if isinstance(key, dict):
                    key = key.get('Z39K1', str(key))
                return f"Key not found: {key}"
            return json.dumps(err)[:200]
    return 'unknown error'


def result_summary(result):
    """Summarize a successful result."""
    val = result.get('Z22K1', result)
    if isinstance(val, dict):
        t = val.get('Z1K1', '?')
        if t == 'Z16683':
            try:
                nat_obj = val.get('Z16683K2', {})
                nat = nat_obj.get('Z13518K1', '?') if isinstance(nat_obj, dict) else str(nat_obj)
                sign_obj = val.get('Z16683K1', {})
                sign = sign_obj.get('Z16659K1', '') if isinstance(sign_obj, dict) else str(sign_obj)
                neg = '-' if sign == 'Z16661' else ''
                return f"Integer({neg}{nat})"
            except (AttributeError, TypeError):
                return 'Integer(?)'
        if t == 'Z20838':
            return 'Float64(...)'
        if t == 'Z6091':
            return f"ItemRef({val.get('Z6091K1', '?')})"
        if t == 'Z6003':
            pred = val.get('Z6003K2', {})
            pred_str = pred.get('Z6092K1', '?') if isinstance(pred, dict) else str(pred)
            return f"Statement(P={pred_str})"
        if t == 'Z6':
            return f"String({val.get('Z6K1', '?')[:30]})"
        return f"type={t}"
    return str(val)[:50]


def encode_input(value):
    """Convert a user-friendly input value to a ZObject."""
    if isinstance(value, str):
        return value  # Wikifunctions accepts bare strings as Z6
    if isinstance(value, int):
        sign = 'Z16660' if value >= 0 else 'Z16661'
        return {
            'Z1K1': 'Z16683',
            'Z16683K1': {'Z1K1': 'Z16659', 'Z16659K1': sign},
            'Z16683K2': {'Z1K1': 'Z13518', 'Z13518K1': str(abs(value))},
        }
    if isinstance(value, dict):
        if 'Z1K1' in value:
            return value  # already a ZObject
        if 'fetch' in value:
            # Wrap in Z6821 call to fetch item
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
        if lit_type == 'Z16683':
            return encode_input(int(value))
        return {'Z1K1': lit_type, f"{lit_type}K1": value}
    raise ValueError(f"Unknown node type: {node}")


def collect_subtrees(node, path='root'):
    """Collect all function call sub-trees with their paths."""
    subtrees = []
    if 'call' in node:
        subtrees.append((path, node))
        for arg_key, arg_node in (node.get('args') or {}).items():
            label = arg_node.get('label', arg_key)
            subtrees.extend(collect_subtrees(arg_node, f"{path} > {label}"))
    return subtrees


def main():
    parser = argparse.ArgumentParser(
        description='Debug a composition by testing each sub-tree'
    )
    parser.add_argument('spec_file', help='Composition JSON spec file')
    parser.add_argument('--inputs', help='Test inputs as JSON string')
    parser.add_argument('--inputs-file', help='Test inputs from a JSON file')
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

    # Collect all sub-trees (deepest first for bottom-up testing)
    subtrees = collect_subtrees(composition)
    subtrees.reverse()

    print(f"Testing {len(subtrees)} sub-trees, deepest first...\n")

    deepest_failure = None
    for path, node in subtrees:
        zid = node['call']
        name = node.get('name', zid)
        label = f"{zid} ({name})"

        try:
            call = build_call(node, inputs)
            result = api_call(call)
        except Exception as e:
            print(f"  SKIP  {label}")
            print(f"        {path}")
            print(f"        (could not build call: {e})\n")
            continue

        if is_error(result):
            msg = extract_error_message(result)
            print(f"  FAIL  {label}")
            print(f"        {path}")
            print(f"        {msg}\n")
            if not deepest_failure:
                deepest_failure = (path, label, msg)
        else:
            summary = result_summary(result)
            print(f"  OK    {label}  =>  {summary}")
            print(f"        {path}\n")

    print("=" * 60)
    if deepest_failure:
        path, label, msg = deepest_failure
        print(f"Root cause: {label}")
        print(f"  Path: {path}")
        print(f"  Error: {msg}")
    else:
        print("All sub-trees passed.")


if __name__ == '__main__':
    main()

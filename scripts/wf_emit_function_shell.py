#!/usr/bin/env python3
"""Emit a server-ready Z2/Z8 function shell from a `.func.json` spec.

Closes the gap noted in CLAUDE.md: `wf_emit_zobject.rb` emits Z14 / Z20
from `.comp.json` / `.tester.json`, but function shells had to be
hand-built for the OAuth API path. Same spec format as `wf.rb`:

    {
      "task": "function",
      "label": "lexeme sense is in field of usage?",
      "description": "...",
      "inputs": [{"label": "sense", "type": "Z6006"}, {"label": "field of usage", "type": "Z6091"}],
      "output_type": "Z40"            // or a generic call, e.g. {"Z1K1": "Z7", "Z7K1": "Z881", "Z881K1": "Z6095"}
    }

Usage:
    python scripts/wf_emit_function_shell.py zobjects/x.func.json \\
      | CLAUDE_MODEL=... python scripts/wikifunctions_edit.py create --summary "New function: ..."

All self-references use the Z0 placeholder (Z2K1, Z8K5, argument keys
Z0K1..), which the server rewrites to the assigned ZID on save.
"""
import json
import sys


def z12(text):
    """English-only multilingual text (empty when text is falsy)."""
    entries = ['Z11']
    if text:
        entries.append({'Z1K1': 'Z11', 'Z11K1': 'Z1002', 'Z11K2': text})
    return {'Z1K1': 'Z12', 'Z12K1': entries}


def emit_shell(spec):
    if spec.get('task', 'function') != 'function':
        raise ValueError(f"spec task is {spec.get('task')!r}, expected 'function'")
    label = spec['label']
    if len(label) > 50:
        raise ValueError(f'label is {len(label)} chars; Wikifunctions labels must stay under ~50')
    desc = spec.get('description') or ''
    if len(desc) > 500:
        raise ValueError(f'description is {len(desc)} chars; Wikifunctions rejects descriptions over 500')
    args = ['Z17']
    for i, inp in enumerate(spec['inputs'], start=1):
        args.append({'Z1K1': 'Z17', 'Z17K1': inp['type'], 'Z17K2': f'Z0K{i}',
                     'Z17K3': z12(inp['label'])})
    z8 = {
        'Z1K1': 'Z8',
        'Z8K1': args,
        'Z8K2': spec['output_type'],
        'Z8K3': ['Z20'],
        'Z8K4': ['Z14'],
        'Z8K5': 'Z0',
    }
    z2 = {
        'Z1K1': 'Z2',
        'Z2K1': {'Z1K1': 'Z6', 'Z6K1': 'Z0'},
        'Z2K2': z8,
        'Z2K3': z12(label),
        'Z2K4': {'Z1K1': 'Z32', 'Z32K1': ['Z31']},
        'Z2K5': z12(spec.get('description')),
    }
    return z2


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 1)
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    json.dump(emit_shell(spec), sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()

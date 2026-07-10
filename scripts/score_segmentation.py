#!/usr/bin/env python3
"""Score a sentence-segmentation function against the 52 wiki-themed
Golden Rules by executing it live via the Wikifunctions function-call API.

Useful for tracking progress as the implementation improves (v2+): run it
after editing Z18522's implementation to see which Golden Rules now pass.

Usage:
    python scripts/score_segmentation.py                 # scores Z18522
    python scripts/score_segmentation.py --zid Z18522    # explicit
    python scripts/score_segmentation.py --show-pass     # also list passes
"""
import argparse
import json
import os
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT

DATA = os.path.join(os.path.dirname(__file__), "..", "zobjects",
                    "sentence_segmentation_golden_rules.json")


def call(zid, text):
    call_obj = {"Z1K1": "Z7", "Z7K1": zid, f"{zid}K1": text}
    data = urllib.parse.urlencode({
        "action": "wikilambda_function_call", "format": "json",
        "wikilambda_function_call_zobject": json.dumps(call_obj),
    }).encode()
    req = urllib.request.Request(WF_API, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        r = json.loads(resp.read())
    val = json.loads(r["wikilambda_function_call"]["data"]).get("Z22K1")
    # Canonical typed list: ["Z6", elem, ...] -> drop the type header.
    if isinstance(val, list) and val and val[0] == "Z6":
        return val[1:]
    return val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zid", default="Z18522")
    ap.add_argument("--show-pass", action="store_true")
    args = ap.parse_args()

    rules = json.load(open(os.path.normpath(DATA)))["rules"]
    npass = 0
    for r in rules:
        got = call(args.zid, r["input"])
        ok = got == r["expected"]
        npass += ok
        if ok and args.show_pass:
            print(f"  PASS GR{r['n']:<2} [{r['category']}]")
        if not ok:
            print(f"  FAIL GR{r['n']:<2} [{r['category']}]")
            print(f"        got: {got}")
            print(f"        exp: {r['expected']}")
    print(f"\n{args.zid}: {npass}/{len(rules)} Golden Rules pass")


if __name__ == "__main__":
    main()

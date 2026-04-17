#!/usr/bin/env python3
"""Build a local cache of Wikifunctions ZObjects for offline greps and analysis.

Layout:
    cache/<ZID>.json     — pretty-printed canonical ZObject for each entry
    cache/_index.jsonl   — one compact line per entry (type, label, signature)
    cache/.last_refresh  — ISO timestamp of the most recent successful refresh

Usage:
    python scripts/wikifunctions_cache.py --full                    # fetch everything
    python scripts/wikifunctions_cache.py --incremental             # refresh edits since last refresh
    python scripts/wikifunctions_cache.py --zids Z26184,Z33668      # targeted refresh

Options:
    --types Z4,Z8,Z14,Z20   only keep these types (default; `all` keeps every page)
    --batch N               ZIDs per wikilambda_fetch call (default 50)
    --dry-run               list what would be fetched, write nothing
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.parse
import urllib.request

from config import WF_API, USER_AGENT

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
INDEX_FILE = CACHE_DIR / "_index.jsonl"
REFRESH_FILE = CACHE_DIR / ".last_refresh"

FETCH_BATCH = 50
LIST_BATCH = 500
RC_BATCH = 500

# Rate limiter — minimum seconds between outgoing API calls. Set by
# set_min_interval() at the start of main(), read inside api_get().
_MIN_INTERVAL = 0.0
_LAST_CALL_AT = 0.0


def set_min_interval(seconds):
    global _MIN_INTERVAL
    _MIN_INTERVAL = max(0.0, float(seconds))


# ── API plumbing ─────────────────────────────────────────────────────────

def api_get(params, retries=3):
    global _LAST_CALL_AT
    if _MIN_INTERVAL > 0:
        wait = _MIN_INTERVAL - (time.monotonic() - _LAST_CALL_AT)
        if wait > 0:
            time.sleep(wait)

    params = dict(params, format="json")
    url = f"{WF_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                _LAST_CALL_AT = time.monotonic()
                return json.loads(resp.read().decode())
        except Exception as e:
            last = e
            time.sleep(1 + attempt)
    raise last


def enumerate_all_zids():
    """Yield every Z-titled page in the main namespace via list=allpages."""
    cont = None
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": "0",
            "aplimit": str(LIST_BATCH),
        }
        if cont:
            params["apcontinue"] = cont
        data = api_get(params)
        for page in data.get("query", {}).get("allpages", []):
            title = page["title"]
            if title.startswith("Z") and title[1:].isdigit():
                yield title
        cont = data.get("continue", {}).get("apcontinue")
        if not cont:
            break


def enumerate_changed_zids(since_iso):
    """Yield ZIDs with main-namespace edits since `since_iso`."""
    cont = None
    seen = set()
    while True:
        params = {
            "action": "query",
            "list": "recentchanges",
            "rcnamespace": "0",
            "rcdir": "newer",
            "rcstart": since_iso,
            "rcprop": "title|timestamp",
            "rclimit": str(RC_BATCH),
        }
        if cont:
            params["rccontinue"] = cont
        data = api_get(params)
        for ch in data.get("query", {}).get("recentchanges", []):
            title = ch.get("title", "")
            if title.startswith("Z") and title[1:].isdigit() and title not in seen:
                seen.add(title)
                yield title
        cont = data.get("continue", {}).get("rccontinue")
        if not cont:
            break


def fetch_batch(zids):
    """Return dict of zid -> parsed ZObject for the ZIDs present in the response."""
    params = {"action": "wikilambda_fetch", "zids": "|".join(zids)}
    data = api_get(params)
    out = {}
    for zid in zids:
        raw = data.get(zid, {}).get("wikilambda_fetch")
        if raw is None:
            continue
        if isinstance(raw, str):
            try:
                out[zid] = json.loads(raw)
            except json.JSONDecodeError:
                continue
        else:
            out[zid] = raw
    return out


# ── ZObject parsing helpers ──────────────────────────────────────────────

def inner_type(zobj):
    """Return the effective Z1K1 (inner type) of the persisted object."""
    inner = zobj.get("Z2K2") if isinstance(zobj, dict) else None
    if not isinstance(inner, dict):
        return None
    t = inner.get("Z1K1")
    if isinstance(t, dict):  # reference Z9
        return t.get("Z9K1") or t.get("Z1K1")
    return t


def en_label(z12):
    """Extract the English label from a Z12 multilingual text."""
    if not isinstance(z12, dict):
        return ""
    items = z12.get("Z12K1") or []
    if not isinstance(items, list):
        return ""
    # Typed list: first element is the type marker, skip it.
    for item in items[1:]:
        if isinstance(item, dict) and item.get("Z11K1") == "Z1002":
            return item.get("Z11K2", "")
    return ""


def typed_list_tail(val):
    """Strip the leading type marker from a benjamin-array typed list."""
    if isinstance(val, list) and val:
        return val[1:]
    return []


def summarize(zid, zobj):
    """One-line index entry capturing the shape that's useful for greps."""
    inner = zobj.get("Z2K2", {}) if isinstance(zobj, dict) else {}
    ztype = inner_type(zobj)
    entry = {
        "zid": zid,
        "type": ztype,
        "label": en_label(zobj.get("Z2K3", {})),
    }

    if ztype == "Z8":  # Function
        args = []
        for a in typed_list_tail(inner.get("Z8K1")):
            if isinstance(a, dict):
                args.append({
                    "key": a.get("Z17K2"),
                    "type": a.get("Z17K1"),
                    "label": en_label(a.get("Z17K3", {})),
                })
        entry["args"] = args
        entry["output"] = inner.get("Z8K2")
        entry["impls"] = typed_list_tail(inner.get("Z8K4"))
        entry["testers"] = typed_list_tail(inner.get("Z8K3"))
    elif ztype == "Z14":  # Implementation
        entry["implements"] = inner.get("Z14K1")
        # Note whether it's composition (Z14K2), code (Z14K3), or builtin (Z14K4).
        if inner.get("Z14K2") is not None:
            entry["kind"] = "composition"
        elif inner.get("Z14K3") is not None:
            entry["kind"] = "code"
        elif inner.get("Z14K4") is not None:
            entry["kind"] = "builtin"
    elif ztype == "Z20":  # Tester
        entry["tests"] = inner.get("Z20K1")

    return entry


# ── Cache operations ─────────────────────────────────────────────────────

def write_zobject(zid, zobj):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{zid}.json"
    with open(path, "w") as f:
        json.dump(zobj, f, indent=2, ensure_ascii=False)


def load_index():
    """Return dict of zid -> index entry from _index.jsonl, or empty dict."""
    if not INDEX_FILE.exists():
        return {}
    out = {}
    with open(INDEX_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                out[rec["zid"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return out


def write_index(index):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Sort by ZID numeric for a stable, diff-friendly order.
    def key(zid):
        try:
            return int(zid[1:])
        except ValueError:
            return 10**9
    with open(INDEX_FILE, "w") as f:
        for zid in sorted(index, key=key):
            f.write(json.dumps(index[zid], ensure_ascii=False, separators=(",", ":")) + "\n")


# ── Main refresh routines ────────────────────────────────────────────────

def fetch_and_write(zids, wanted_types, batch_size, index, dry_run=False):
    """Fetch ZIDs in batches and update the cache in place."""
    zids = list(dict.fromkeys(zids))  # dedupe, preserve order
    total = len(zids)
    if total == 0:
        return 0, 0

    kept = 0
    for i in range(0, total, batch_size):
        chunk = zids[i : i + batch_size]
        if dry_run:
            kept += len(chunk)
            continue
        try:
            objs = fetch_batch(chunk)
        except Exception as e:
            print(f"  WARN: fetch failed for {chunk[0]}..{chunk[-1]}: {e}", file=sys.stderr)
            continue

        for zid, zobj in objs.items():
            ztype = inner_type(zobj)
            if wanted_types is not None and ztype not in wanted_types:
                # Remove any stale entry for this zid if type now excluded.
                path = CACHE_DIR / f"{zid}.json"
                if path.exists():
                    path.unlink()
                index.pop(zid, None)
                continue
            write_zobject(zid, zobj)
            index[zid] = summarize(zid, zobj)
            kept += 1

        if (i + batch_size) % 500 == 0 or (i + batch_size) >= total:
            print(f"  fetched {min(i + batch_size, total)}/{total} ({kept} kept)", file=sys.stderr)
    return total, kept


def read_last_refresh():
    if not REFRESH_FILE.exists():
        return None
    return REFRESH_FILE.read_text().strip()


def write_last_refresh(iso):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    REFRESH_FILE.write_text(iso)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="Fetch every ZObject (first-time build)")
    ap.add_argument("--incremental", action="store_true", help="Refresh ZObjects edited since .last_refresh")
    ap.add_argument("--zids", help="Comma-separated list of ZIDs to refresh")
    ap.add_argument("--types", default="Z4,Z8,Z14,Z20",
                    help="Only keep these types (default: Z4,Z8,Z14,Z20). Use 'all' to keep every page.")
    ap.add_argument("--batch", type=int, default=FETCH_BATCH, help=f"ZIDs per fetch call (default {FETCH_BATCH})")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="Minimum seconds between outgoing API calls (default 2.0)")
    ap.add_argument("--dry-run", action="store_true", help="List what would be fetched; don't write")
    args = ap.parse_args()

    if not (args.full or args.incremental or args.zids):
        ap.error("Specify --full, --incremental, or --zids")

    set_min_interval(args.sleep)
    wanted_types = None if args.types == "all" else set(args.types.split(","))
    index = load_index()
    refresh_start = now_iso()

    if args.full:
        print("Enumerating all Z-titled pages...", file=sys.stderr)
        zids = list(enumerate_all_zids())
        print(f"  found {len(zids)} pages", file=sys.stderr)
    elif args.incremental:
        since = read_last_refresh()
        if not since:
            print("No .last_refresh found — run with --full first.", file=sys.stderr)
            sys.exit(1)
        print(f"Enumerating pages changed since {since}...", file=sys.stderr)
        zids = list(enumerate_changed_zids(since))
        print(f"  found {len(zids)} changed pages", file=sys.stderr)
    else:  # --zids
        zids = [z.strip() for z in args.zids.split(",") if z.strip()]

    total, kept = fetch_and_write(zids, wanted_types, args.batch, index, dry_run=args.dry_run)

    if not args.dry_run:
        write_index(index)
        # Only advance the refresh marker on full or incremental runs.
        if args.full or args.incremental:
            write_last_refresh(refresh_start)

    print(f"Done. fetched={total} kept={kept} cache={CACHE_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()

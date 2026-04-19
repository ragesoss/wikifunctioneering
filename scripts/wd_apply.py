#!/usr/bin/env python3
"""Apply approved proposal edits to Wikidata.

Reads a proposal file from proposals/ and executes its `ops`. Default
mode is --dry-run: prints a semantic diff of the changes (entity-level
with labels resolved) without posting anything. --show-payload adds
the raw API payload for each POST. --apply actually writes.

Status lifecycle in the proposal file:
  draft \u2192 posted (set by this script on successful apply)

Supported op kinds:
  - create_item   wbeditentity new=item with labels/descriptions/aliases/claims
  - add_sense     wbladdsense on an existing lexeme (gloss-only; claims via add_claim)
  - add_claim     wbcreateclaim on any entity (Q, L, or L-Sn for senses)

Rate limiting: every write includes maxlag=5; we sleep 2 s between edits
and retry with exponential backoff on maxlag errors (4 attempts).

Usage:
    python scripts/wd_apply.py --slug cancel-ui-concept                # dry-run, semantic view
    python scripts/wd_apply.py --slug cancel-ui-concept --show-payload # also show raw API payloads
    python scripts/wd_apply.py --slug cancel-ui-concept --apply        # actually post
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

PROPOSALS_DIR = Path(__file__).parent.parent / "proposals"

AI_DISCLOSURE = "Edit drafted with AI assistance (Claude Opus 4.7)."
INTER_EDIT_SLEEP = 2.0
MAXLAG_MAX_RETRIES = 4
MAXLAG_RETRY_WAIT = 12.0  # seconds; doubles each retry

_PLACEHOLDER_RE = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


# ------------------------- Summaries --------------------------------
# Kept short and specific \u2014 Wikidata summaries are shown in watchlists
# and recent changes. Describe WHAT and WHY; cite the proposal slug.

def summary_create_item(proposal: dict, op: dict) -> str:
    slug = proposal.get("slug", "?")
    label = op.get("labels", {}).get("en", "?")
    claims = op.get("claims", [])
    claims_str = ", ".join(f"{c['property']}={c['value']}" for c in claims)
    return (
        f"Create \u201c{label}\u201d ({claims_str}) as concept item for "
        f"Wikifunctions Z33668 sense linking. Proposal: {slug}. {AI_DISCLOSURE}"
    )


def summary_add_claim(proposal: dict, op: dict, resolved_value: str,
                      resolved_entity: str | None = None) -> str:
    slug = proposal.get("slug", "?")
    entity = resolved_entity or op["entity"]
    return (
        f"Add {op['property']}={resolved_value} on {entity}. "
        f"Proposal: {slug}. {AI_DISCLOSURE}"
    )


def summary_add_sense(proposal: dict, op: dict) -> str:
    slug = proposal.get("slug", "?")
    gloss = op.get("glosses", {}).get("en", "?")
    return (
        f"Add sense \u201c{gloss}\u201d to {op['lexeme']} for Z33668 "
        f"multilingual lookups. Proposal: {slug}. {AI_DISCLOSURE}"
    )


def summary_update_description(proposal: dict, op: dict) -> str:
    slug = proposal.get("slug", "?")
    return (f"Update {op.get('lang', 'en')} description on {op['entity']}. "
            f"Proposal: {slug}. {AI_DISCLOSURE}")


def summary_add_alias(proposal: dict, op: dict) -> str:
    slug = proposal.get("slug", "?")
    return (f"Add {op.get('lang', 'en')} alias on {op['entity']}. "
            f"Proposal: {slug}. {AI_DISCLOSURE}")


# ------------------------- Request builders -------------------------

def _entity_value(qid: str) -> dict:
    return {"entity-type": "item", "numeric-id": int(qid[1:]), "id": qid}


def _claim_statement(pid: str, qid: str) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value", "property": pid,
            "datavalue": {"value": _entity_value(qid), "type": "wikibase-entityid"},
        },
        "type": "statement", "rank": "normal",
    }


def build_create_item(op: dict, summary: str) -> dict:
    data: dict = {"labels": {}, "descriptions": {}, "aliases": {}, "claims": {}}
    for lg, v in (op.get("labels") or {}).items():
        data["labels"][lg] = {"language": lg, "value": v}
    for lg, v in (op.get("descriptions") or {}).items():
        data["descriptions"][lg] = {"language": lg, "value": v}
    for lg, vs in (op.get("aliases") or {}).items():
        data["aliases"][lg] = [{"language": lg, "value": v} for v in vs]
    for cl in op.get("claims") or []:
        data["claims"].setdefault(cl["property"], []).append(
            _claim_statement(cl["property"], cl["value"])
        )
    # Drop empty sub-dicts so we don't send noise.
    data = {k: v for k, v in data.items() if v}
    return {
        "params": {"action": "wbeditentity", "new": "item",
                   "summary": summary, "bot": "0",
                   "format": "json", "maxlag": "5"},
        "post": {"data": json.dumps(data, ensure_ascii=False)},
    }


def build_add_claim(entity: str, pid: str, qid: str, summary: str) -> dict:
    return {
        "params": {"action": "wbcreateclaim", "entity": entity,
                   "property": pid, "snaktype": "value",
                   "summary": summary, "bot": "0",
                   "format": "json", "maxlag": "5"},
        "post": {"value": json.dumps(_entity_value(qid), ensure_ascii=False)},
    }


def build_add_sense(lexeme_id: str, glosses: dict, summary: str) -> dict:
    """wbladdsense POST to append a new sense to an existing lexeme.
    Claims on the new sense are added via follow-up wbcreateclaim ops
    (the lemma-sense data model doesn't bundle them in this API)."""
    data = {"glosses": {lg: {"language": lg, "value": v}
                         for lg, v in glosses.items()}}
    return {
        "params": {"action": "wbladdsense", "lexemeId": lexeme_id,
                   "summary": summary, "bot": "0",
                   "format": "json", "maxlag": "5"},
        "post": {"data": json.dumps(data, ensure_ascii=False)},
    }


# ------------------------- Placeholder resolution -------------------

def resolve_placeholders(value: str, env: dict[str, str]) -> str:
    def _sub(m):
        name = m.group(1)
        if name not in env:
            raise KeyError(f"Placeholder {{{name}}} is not yet resolved")
        return env[name]
    return _PLACEHOLDER_RE.sub(_sub, value)


def post_with_maxlag_retry(session, params: dict, post: dict) -> dict:
    """POST a write, retrying with exponential backoff on maxlag errors.
    maxlag is Wikidata's standard backpressure signal \u2014 when the cluster is
    behind, polite clients wait and retry rather than hammering."""
    wait = MAXLAG_RETRY_WAIT
    for attempt in range(1, MAXLAG_MAX_RETRIES + 1):
        r = session._write(params, post)
        err = r.get("error")
        if err and err.get("code") == "maxlag":
            lag = err.get("lag", "?")
            print(f"    (maxlag: {lag}s lagged; waiting {wait:.0f}s then retrying, "
                  f"attempt {attempt}/{MAXLAG_MAX_RETRIES})")
            time.sleep(wait)
            wait *= 2
            continue
        return r
    raise RuntimeError(f"Gave up after {MAXLAG_MAX_RETRIES} maxlag retries; Wikidata cluster backed up. Try again later.")


# ------------------------- Dry-run printing -------------------------

# ------------------------- Semantic diff view ----------------------

def _gather_ref_ids(proposal: dict) -> set[str]:
    """Collect every Q/L/P id we'll want labels for in the semantic diff."""
    ids = {"P31", "P279", "P5137"}
    for op in proposal.get("ops") or []:
        if op["op"] == "create_item":
            for cl in op.get("claims", []):
                ids.add(cl["property"])
                v = cl["value"]
                if v and v[0] in "QLP":
                    ids.add(v)
        elif op["op"] == "add_sense":
            ids.add(op["lexeme"])
        elif op["op"] == "add_claim":
            ids.add(op["property"])
            for v in (op["entity"], op["value"]):
                if not v or v.startswith("{"):
                    continue
                if v[0] in "QLP":
                    ids.add(v.split("-")[0] if "-S" in v else v)
    return ids


def _fmt_q_or_placeholder(val: str, ents: dict) -> str:
    if not val:
        return "?"
    if val.startswith("{"):
        return val
    if val[0] in "QLP":
        lbl = ents.get(val, {}).get("labels", {}).get("en", {}).get("value")
        if not lbl and val.startswith("L"):
            lemmas = ents.get(val, {}).get("lemmas", {})
            lbl = (lemmas.get("en") or next(iter(lemmas.values()), {}) or {}).get("value")
        return f"{val} \u201c{lbl or '?'}\u201d"
    return val


def render_semantic_diff(proposal: dict, ents: dict) -> list[str]:
    """Render the proposal's ops as entity-level changes, not API calls.
    Shows before/after for the Wikidata data model."""
    out: list[str] = []
    ops = proposal.get("ops") or []
    if not ops:
        return ["  (no ops)"]

    for i, op in enumerate(ops, 1):
        out.append("")
        if op["op"] == "create_item":
            ph = op.get("placeholder_id") or "NEW_Q"
            out.append(f"Change {i} \u2014 CREATE new Q-item ({{{ph}}})")
            for lg, v in (op.get("labels") or {}).items():
                out.append(f"  label ({lg}):         {v}")
            for lg, v in (op.get("descriptions") or {}).items():
                out.append(f"  description ({lg}):   {v}")
            for lg, vs in (op.get("aliases") or {}).items():
                out.append(f"  aliases ({lg}):       {', '.join(vs)}")
            for cl in op.get("claims", []):
                pid = _fmt_q_or_placeholder(cl["property"], ents)
                vid = _fmt_q_or_placeholder(cl["value"], ents)
                out.append(f"  {pid}  \u2192  {vid}")

        elif op["op"] == "add_sense":
            ph = op.get("placeholder_id") or "NEW_SENSE"
            lex_id = op["lexeme"]
            out.append(f"Change {i} \u2014 ADD new sense to {_fmt_q_or_placeholder(lex_id, ents)}")
            lex = ents.get(lex_id, {})
            existing = lex.get("senses", [])
            if existing:
                out.append(f"  existing senses (unchanged):")
                for s in existing:
                    gloss = s.get("glosses", {}).get("en", {}).get("value") or \
                            next(iter(s.get("glosses", {}).values()), {}).get("value", "?")
                    out.append(f"    {s['id']}  \u2014  \u201c{gloss}\u201d")
            out.append(f"  \u2192 NEW sense ({{{ph}}}):")
            for lg, v in (op.get("glosses") or {}).items():
                out.append(f"    gloss ({lg}): \u201c{v}\u201d")

        elif op["op"] == "add_claim":
            ent = op["entity"]
            pid = _fmt_q_or_placeholder(op["property"], ents)
            val = _fmt_q_or_placeholder(op["value"], ents)
            ent_r = _fmt_q_or_placeholder(ent, ents)
            out.append(f"Change {i} \u2014 ADD statement")
            out.append(f"  {ent_r}")
            out.append(f"    {pid}  \u2192  {val}")

        else:
            out.append(f"Change {i} \u2014 {op['op']} (unrecognised op kind)")

    return out


def print_request(req: dict, prefix: str = "") -> None:
    p = req["params"]
    print(f"{prefix}POST {p['action']}")
    if p.get("summary"):
        print(f"{prefix}  summary: {p['summary']}")
    for k, v in p.items():
        if k in ("action", "summary", "format"):
            continue
        print(f"{prefix}  {k}: {v}")
    for k, v in req["post"].items():
        try:
            parsed = json.loads(v)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            for line in pretty.splitlines():
                print(f"{prefix}    {line}")
        except (TypeError, ValueError):
            print(f"{prefix}  {k}: {v}")


# ------------------------- Apply driver -----------------------------

def load_proposal(arg: str) -> tuple[dict, Path]:
    p = Path(arg)
    if p.is_file():
        return json.loads(p.read_text()), p
    for candidate in PROPOSALS_DIR.glob(f"{arg}.json"):
        return json.loads(candidate.read_text()), candidate
    raise FileNotFoundError(f"No proposal found at {arg} or in {PROPOSALS_DIR}")


def apply_proposal(proposal: dict, path: Path, *, dry_run: bool) -> None:
    ops = proposal.get("ops") or []
    if not ops:
        print("This proposal has no ops (investigate-only). Nothing to apply.")
        return

    # Semantic diff first \u2014 this is what the reviewer reads.
    from wd_common import wbgetentities
    ref_ids = _gather_ref_ids(proposal)
    ents = wbgetentities(sorted(ref_ids), props="labels|descriptions|claims") if ref_ids else {}
    print("Semantic diff (Wikidata entities after applying this proposal):")
    for line in render_semantic_diff(proposal, ents):
        print(line)
    if dry_run:
        print("\n" + "-" * 72)
        print("Raw API payloads (for debugging; the semantic view above is authoritative):")

    session = None
    if not dry_run:
        from wikidata_session import WikidataSession
        session = WikidataSession()
        session._login()

    placeholder_env: dict[str, str] = {}
    op_results: list[dict] = []

    for i, op in enumerate(ops, 1):
        print(f"\n  Op {i}/{len(ops)}: {op['op']}")
        if op["op"] == "create_item":
            summary = summary_create_item(proposal, op)
            req = build_create_item(op, summary)
            print_request(req, prefix="    ")
            if dry_run:
                ph = op.get("placeholder_id")
                if ph:
                    placeholder_env[ph] = f"(would-be-Q for {ph})"
            else:
                r = post_with_maxlag_retry(session, req["params"], req["post"])
                if "error" in r:
                    raise RuntimeError(f"create_item failed: {r['error']}")
                new_id = r["entity"]["id"]
                ph = op.get("placeholder_id")
                if ph:
                    placeholder_env[ph] = new_id
                op_results.append({"op": "create_item", "placeholder": ph,
                                   "result_qid": new_id})
                print(f"    \u2713 created {new_id}")
                time.sleep(INTER_EDIT_SLEEP)

        elif op["op"] == "add_sense":
            summary = summary_add_sense(proposal, op)
            req = build_add_sense(op["lexeme"], op["glosses"], summary)
            print_request(req, prefix="    ")
            if dry_run:
                ph = op.get("placeholder_id")
                if ph:
                    placeholder_env[ph] = f"(would-be-new-sense-ID for {ph})"
            else:
                r = post_with_maxlag_retry(session, req["params"], req["post"])
                if "error" in r:
                    raise RuntimeError(f"add_sense failed: {r['error']}")
                new_sense_id = r["sense"]["id"]
                ph = op.get("placeholder_id")
                if ph:
                    placeholder_env[ph] = new_sense_id
                op_results.append({"op": "add_sense", "lexeme": op["lexeme"],
                                   "placeholder": ph,
                                   "result_sense_id": new_sense_id})
                print(f"    \u2713 sense added: {new_sense_id}")
                time.sleep(INTER_EDIT_SLEEP)

        elif op["op"] == "add_claim":
            raw_entity = op["entity"]
            raw_value = op["value"]
            has_placeholder = bool(_PLACEHOLDER_RE.search(raw_entity) or
                                   _PLACEHOLDER_RE.search(raw_value))
            if has_placeholder and dry_run:
                # Show placeholders as-is; don't try to build a real request.
                summary = summary_add_claim(proposal, op, raw_value, raw_entity)
                params = {"action": "wbcreateclaim", "entity": raw_entity,
                          "property": op["property"], "snaktype": "value",
                          "summary": summary,
                          "bot": "0", "format": "json", "maxlag": "5"}
                post = {"value": f"<{raw_value}> (placeholder; resolved after earlier op)"}
                print_request({"params": params, "post": post}, prefix="    ")
            else:
                resolved_entity = resolve_placeholders(raw_entity, placeholder_env)
                resolved_value = resolve_placeholders(raw_value, placeholder_env)
                summary = summary_add_claim(proposal, op, resolved_value, resolved_entity)
                req = build_add_claim(resolved_entity, op["property"], resolved_value, summary)
                print_request(req, prefix="    ")
                if not dry_run:
                    r = post_with_maxlag_retry(session, req["params"], req["post"])
                    if "error" in r:
                        raise RuntimeError(f"add_claim failed: {r['error']}")
                    claim_id = r.get("claim", {}).get("id")
                    op_results.append({"op": "add_claim", "entity": resolved_entity,
                                       "property": op["property"], "value": resolved_value,
                                       "claim_id": claim_id})
                    print(f"    \u2713 claim added: {claim_id}")
                    time.sleep(INTER_EDIT_SLEEP)
        else:
            print(f"    (apply not yet implemented for op kind: {op['op']})")

    if not dry_run:
        proposal.setdefault("posted", {})
        proposal["posted"] = {
            "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "ops": op_results,
            "placeholder_env": placeholder_env,
        }
        proposal["status"] = "posted"
        path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n")
        print(f"\nUpdated {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--slug")
    ap.add_argument("--apply", action="store_true",
                    help="Actually post to Wikidata. Default is dry-run.")
    args = ap.parse_args()

    if not args.path and not args.slug:
        ap.error("Specify a proposal path or --slug")

    proposal, path = load_proposal(args.path or args.slug)
    dry_run = not args.apply

    mode = "DRY RUN" if dry_run else "APPLYING"
    print(f"{'=' * 72}")
    print(f"{mode}: {proposal.get('slug', '?')} (status={proposal.get('status', '?')})")
    print(f"{'=' * 72}")
    apply_proposal(proposal, path, dry_run=dry_run)


if __name__ == "__main__":
    main()

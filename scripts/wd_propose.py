#!/usr/bin/env python3
"""Review a proposed Wikidata edit (or set of edits) with auto-pulled context.

Takes a proposal file (JSON in proposals/) and renders:
  1. The proposed operations in full, with every P/Q/L id labelled
  2. Baseline context relevant to each op type \u2014 e.g. for a new
     Q-item, what similar items already exist; for an add_claim on a
     lexeme sense, what sibling senses look like; for any referenced
     parent concept, its own classification and existing sense-hub use

The goal is a single screen that gives you enough context to have a
data-driven conversation about whether to proceed, what to change, or
what sibling edits might want to land alongside it.

Supported op kinds (grow this as new proposal shapes come up):
  - create_item          Propose a new Q-item
  - add_claim            Add a claim on an existing entity (Q, L, or L-S)
  - update_description   Change an entity's description
  - add_alias            Add an alias to an entity

Usage:
    python scripts/wd_propose.py proposals/umbrella-ui-command.json
    python scripts/wd_propose.py --slug umbrella-ui-command
    python scripts/wd_propose.py proposals/umbrella-ui-command.json --no-color
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from wd_common import (
    Style, wbgetentities, wbsearchentities, sparql, label_of, desc_of,
    claims_of, fmt_ref, sparql_id, ensure_labels,
    backlink_count, pattern_count, pattern_matches, direct_subclasses,
    senses_for_lemma, sample_p5137_backlinks, parent_chain,
)

PROPOSALS_DIR = Path(__file__).parent.parent / "proposals"

HR = "\u2500" * 72
HR_HEAVY = "\u2501" * 72


# ------------------------- Proposal loading -------------------------

def load_proposal(arg: str) -> tuple[dict, Path]:
    p = Path(arg)
    if p.is_file():
        return json.loads(p.read_text()), p
    for candidate in PROPOSALS_DIR.glob(f"{arg}.json"):
        return json.loads(candidate.read_text()), candidate
    raise FileNotFoundError(f"No proposal found at {arg} or in {PROPOSALS_DIR}")


# ------------------------- Context rendering -------------------------

def _exact_label_or_alias_matches(label: str, limit: int = 10) -> list[str]:
    """Items whose English label OR alias is exactly `label`, filtered
    for noise (templates, names, scholarly articles, etc.). Uses the
    filter from wd_search so we don't duplicate the noise list."""
    from wd_search import NOISE_P31
    safe = label.replace('"', '\\"')
    noise_values = " ".join(f"wd:{q}" for q in NOISE_P31)
    q = f"""
    SELECT DISTINCT ?i WHERE {{
      {{ ?i rdfs:label "{safe}"@en . }}
      UNION
      {{ ?i skos:altLabel "{safe}"@en . }}
      FILTER(STRSTARTS(STR(?i), "http://www.wikidata.org/entity/Q"))
      FILTER NOT EXISTS {{
        VALUES ?noise {{ {noise_values} }}
        ?i wdt:P31 ?noise .
      }}
    }} LIMIT {limit}
    """
    try:
        rows = sparql(q)
    except Exception:
        return []
    return [sparql_id(r["i"]) for r in rows]


def _match_kind(ents: dict, qid: str, label: str) -> str:
    """Is `label` the entity's English label, or an alias?"""
    e = ents.get(qid, {})
    if e.get("labels", {}).get("en", {}).get("value", "").lower() == label.lower():
        return "label"
    for a in e.get("aliases", {}).get("en", []):
        if a.get("value", "").lower() == label.lower():
            return "alias"
    return "match"


def context_for_create_item(op: dict, ents: dict, st: Style,
                             enabled: set) -> list[str]:
    """Render context for a create_item op. Fast parts always run; slow
    SPARQL probes gated on `enabled` (set of probe names)."""
    out: list[str] = []
    p31 = [c["value"] for c in op.get("claims", []) if c["property"] == "P31"]
    p279 = [c["value"] for c in op.get("claims", []) if c["property"] == "P279"]
    label = op.get("labels", {}).get("en", "")

    # Parent concepts \u2014 fast: pull P31/P279 from already-fetched entities.
    for pid, vid in [("P31", q) for q in p31] + [("P279", q) for q in p279]:
        out.append("")
        out.append(f"  {st.bold('Parent:')} {fmt_ref(pid, ents, st)} \u2192 {fmt_ref(vid, ents, st)}")
        d = desc_of(ents, vid)
        if d: out.append(f"    {st.dim(d[:100])}")
        for ppid in ("P31", "P279"):
            vals = claims_of(ents, vid, ppid)
            if vals:
                rendered = ", ".join(fmt_ref(v, ents, st) for v in vals[:3])
                out.append(f"    {fmt_ref(ppid, ents, st)}: {rendered}")
        # SLOW: parent's P5137 backlink count (how established is it as a hub?)
        if "backlinks" in enabled:
            try:
                bk = backlink_count(vid)
                out.append(f"    as P5137 hub: {bk} sense(s) link here")
            except Exception:
                pass
        # SLOW: existing direct subclasses of the parent (top by backlinks)
        if pid == "P279" and "siblings" in enabled:
            siblings = direct_subclasses(vid, limit=8)
            ensure_labels(ents, [s["qid"] for s in siblings])
            if siblings:
                out.append(f"    {st.dim('existing direct subclasses (top by P5137 backlinks):')}")
                for s in siblings:
                    bk_n = s["backlinks"]
                    bk_style = st.green if bk_n >= 3 else st.yellow if bk_n >= 1 else st.dim
                    d = desc_of(ents, s["qid"])[:50]
                    out.append(f"      {fmt_ref(s['qid'], ents, st)}   {bk_style(f'bk={bk_n}')}  "
                               f"{st.dim(d)}")

    # SLOW: pattern popularity \u2014 items matching the full P31+P279 combo
    if (p31 or p279) and "pattern" in enabled:
        cnt = pattern_count(p31, p279)
        combined = " + ".join([f"P31={q}" for q in p31] + [f"P279={q}" for q in p279])
        bold = st.green if cnt >= 5 else st.yellow if cnt >= 2 else st.dim
        out.append("")
        out.append(f"  {st.bold('Items matching proposed pattern')} "
                   f"({combined}): {bold(str(cnt))}")
        if cnt > 0:
            matches = pattern_matches(p31, p279, limit=8)
            ensure_labels(ents, [m["qid"] for m in matches])
            for m in matches:
                bk_style = st.green if m["backlinks"] >= 3 else st.yellow if m["backlinks"] >= 1 else st.dim
                bk_n = m["backlinks"]
                out.append(f"    {fmt_ref(m['qid'], ents, st)}   {bk_style(f'bk={bk_n}')}  "
                           f"{st.dim(desc_of(ents, m['qid'])[:70])}")
            if cnt > len(matches):
                out.append(f"    {st.dim(f'\u2026 and {cnt - len(matches)} more')}")

    # DUPLICATE CHECK \u2014 exact-match label or alias via SPARQL, filtered
    # for noise. This is the definitive "is there already a concept with
    # this name?" probe. wbsearchentities alone is insufficient because
    # its ranking favours popular entities (places, names, acronyms) and
    # can push relevant concept items off the first page of results.
    # One SPARQL call \u2014 fast enough to keep always-on for create_item.
    if label:
        exact_matches = _exact_label_or_alias_matches(label)
        if exact_matches:
            ensure_labels(ents, exact_matches)
            out.append("")
            out.append(f"  {st.bold('\u26a0 EXACT label/alias matches for')} \u201c{label}\u201d  "
                       f"{st.red('(check before creating a new item!)')}")
            for qid in exact_matches:
                d = desc_of(ents, qid)[:90]
                match_kind = _match_kind(ents, qid, label)
                out.append(f"    {fmt_ref(qid, ents, st)}  {st.yellow(f'[{match_kind}]')}  "
                           f"{st.dim(d)}")
                for pid in ("P31", "P279"):
                    vals = claims_of(ents, qid, pid)[:3]
                    if vals:
                        ensure_labels(ents, vals)
                        rendered = ", ".join(fmt_ref(v, ents, st) for v in vals)
                        out.append(f"      {fmt_ref(pid, ents, st)}: {rendered}")

    # Ranked label + alias search (wbsearchentities) \u2014 complementary to
    # the exact-match lookup above; catches fuzzy matches.
    if label:
        out.append("")
        out.append(f"  {st.bold('Items on Wikidata with labels or aliases similar to')} \u201c{label}\u201d:")
        hits = wbsearchentities(label, entity_type='item', language='en', limit=20)
        if hits:
            for h in hits[:15]:
                desc = (h.get("description") or "")[:80]
                match = h.get("match") or {}
                kind = match.get("type", "")
                matched_text = match.get("text", "")
                tag = ""
                if kind == "alias":
                    tag = st.yellow(" [alias]")
                elif kind == "label" and matched_text != h.get("label"):
                    tag = st.dim(f" [match={matched_text!r}]")
                out.append(f"    {st.cyan(h['id'])} {st.dim('\u201c')}{h.get('label','?')}{st.dim('\u201d')}"
                           f"{tag}  {st.dim(desc)}")
        else:
            out.append(f"    {st.dim('(no results \u2014 the label namespace is clear)')}")

    return out


def context_for_add_claim(op: dict, ents: dict, st: Style, enabled: set) -> list[str]:
    out: list[str] = []
    entity = op["entity"]
    pid = op["property"]
    value = op["value"]

    out.append(f"  {st.bold('Target entity current state:')} {fmt_ref(entity, ents, st)}")
    e = ents.get(entity, {})
    d = desc_of(ents, entity)
    if d: out.append(f"    {st.dim(d[:100])}")
    # For a lexeme-sense id, look up the sense's gloss + existing claims
    if "-S" in entity:
        parent = entity.split("-")[0]
        lex = ents.get(parent, {})
        for s in lex.get("senses", []):
            if s["id"] == entity:
                gloss = s.get("glosses", {}).get("en", {}).get("value")
                if gloss: out.append(f"    gloss (en): {gloss}")
                existing = s.get("claims", {}).get(pid, [])
                if existing:
                    for c in existing:
                        ev = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                        out.append(f"    already has {fmt_ref(pid, ents, st)} \u2192 {fmt_ref(ev, ents, st)}")
                else:
                    out.append(f"    {st.dim(f'no existing {pid}')}")
                break

    # For the value, if it's a Q-ID, show what it is and who already links to it
    if value and value[0] == "Q" and not value.startswith("{"):
        out.append("")
        out.append(f"  {st.bold('Claim target:')} {fmt_ref(value, ents, st)}")
        d = desc_of(ents, value)
        if d: out.append(f"    {st.dim(d[:100])}")
        if "backlinks" not in enabled:
            return out
        try:
            bk = backlink_count(value)
            out.append(f"    as P5137 hub: {bk} sense(s) already link here")
        except Exception:
            pass

    return out


# ------------------------- Rendering -------------------------

def render_ops(proposal: dict, ents: dict, st: Style) -> list[str]:
    ops = proposal.get("ops") or []
    if not ops:
        return [f"{st.dim('No operations proposed \u2014 this is an investigate-only proposal.')}"]
    out = [f"{st.bold('Proposed operations')} ({len(ops)}):"]
    for i, op in enumerate(ops, 1):
        out.append("")
        out.append(f"  {i}. {st.green(op['op'])}")
        if op["op"] == "create_item":
            ph = op.get("placeholder_id", "?")
            out.append(f"     placeholder: {st.magenta('{' + ph + '}')}")
            if "labels" in op:
                for lg, v in op["labels"].items():
                    out.append(f"     label ({lg}): {v}")
            if "aliases" in op:
                for lg, vs in op["aliases"].items():
                    out.append(f"     aliases ({lg}): {', '.join(vs)}")
            if "descriptions" in op:
                for lg, v in op["descriptions"].items():
                    out.append(f"     description ({lg}): {v}")
            for cl in op.get("claims", []):
                out.append(f"     {fmt_ref(cl['property'], ents, st)}: {fmt_ref(cl['value'], ents, st)}")
        elif op["op"] == "add_claim":
            vs = op["value"]
            ent = op["entity"]
            ent_render = st.magenta(ent) if ent.startswith("{") else fmt_ref(ent, ents, st)
            val_render = fmt_ref(vs, ents, st) if vs and vs[0] in "QL" and not vs.startswith("{") else st.magenta(vs)
            out.append(f"     {ent_render}  "
                       f"{fmt_ref(op['property'], ents, st)} \u2192 {val_render}")
        elif op["op"] == "add_sense":
            ph = op.get("placeholder_id", "?")
            out.append(f"     target lexeme: {fmt_ref(op['lexeme'], ents, st)}")
            out.append(f"     placeholder (new sense id): {st.magenta('{' + ph + '}')}")
            for lg, v in (op.get("glosses") or {}).items():
                out.append(f"     gloss ({lg}): {v}")
        elif op["op"] in ("update_description", "update_label", "add_alias"):
            out.append(f"     {fmt_ref(op['entity'], ents, st)}  "
                       f"{op['op']} ({op.get('lang','en')}): {op.get('value','?')}")
        else:
            out.append(f"     {st.red('(unsupported op kind: ' + op['op'] + ')')}")
    return out


def render_context(proposal: dict, ents: dict, st: Style, enabled: set) -> list[str]:
    out: list[str] = []
    for i, op in enumerate(proposal.get("ops") or [], 1):
        out.append("")
        op_kind = op["op"]
        out.append(f"{st.bold(f'Context for op {i} ({op_kind}):')}")
        if op["op"] == "create_item":
            out.extend(context_for_create_item(op, ents, st, enabled))
        elif op["op"] == "add_claim":
            out.extend(context_for_add_claim(op, ents, st, enabled))
        else:
            out.append(f"  {st.dim('(no context probes defined for this op kind yet)')}")
    return out


def render_open_questions(proposal: dict, st: Style) -> list[str]:
    qs = proposal.get("open_questions") or []
    if not qs:
        return []
    out = [f"{st.bold('Open questions')}"]
    for q in qs:
        out.append(f"  \u2022 {q}")
    return out


def render_related_followups(proposal: dict, st: Style) -> list[str]:
    items = proposal.get("related_followups") or []
    if not items:
        return []
    out = [f"{st.bold('Potential follow-up proposals')} "
           f"{st.dim('(notes for later; not part of this proposal)')}"]
    for it in items:
        out.append("")
        out.append(f"  \u2022 {st.bold(it.get('summary', '?'))}")
        if it.get("entities"):
            out.append(f"    entities: {', '.join(it['entities'])}")
        if it.get("notes"):
            for line in _wrap(it["notes"], 70, indent="    "):
                out.append(line)
    return out


# ------------------------- Declared probes -------------------------
# A proposal can declare `probes` in its JSON:
#   probes: {
#     related_lemmas:     ["undo", "save", "close"],   # + optional lang
#     related_precedents: ["Q513420", "Q1058748"],
#     walk_up_levels:     2
#   }
# Each probe renders its own section. Grow this vocabulary as new
# investigation patterns come up.

def render_probe_related_lemmas(lemmas: list, ents: dict, st: Style,
                                lang_iso: str = "en") -> list[str]:
    from wd_common import senses_for_lemma
    out = [f"{st.bold('Probe: related lemmas')} ({lang_iso})"]
    concept_ids_to_label = set()
    per_lemma = {}
    for lem in lemmas:
        per_lemma[lem] = senses_for_lemma(lem, lang_iso=lang_iso)
        for s in per_lemma[lem]:
            concept_ids_to_label.update(s["p5137"])
    ensure_labels(ents, concept_ids_to_label)
    for lem in lemmas:
        out.append(f"  {st.bold(lem)}")
        senses = per_lemma[lem]
        if not senses:
            out.append(f"    {st.dim('(no lexeme with this lemma)')}")
            continue
        for s in senses:
            gloss = s["gloss"] or st.dim("(no en gloss)")
            out.append(f"    {st.magenta(s['sense'])}: {gloss[:80]}")
            if s["p5137"]:
                for cid in s["p5137"]:
                    out.append(f"      P5137 \u2192 {fmt_ref(cid, ents, st)}")
            else:
                out.append(f"      {st.dim('P5137: (none)')}")
    return out


def render_probe_related_precedents(qids: list, ents: dict, st: Style) -> list[str]:
    from wd_common import sample_p5137_backlinks, backlink_count
    ensure_labels(ents, qids)
    out = [f"{st.bold('Probe: related precedents')}"]
    for qid in qids:
        out.append(f"  {fmt_ref(qid, ents, st)}")
        d = desc_of(ents, qid)
        if d: out.append(f"    {st.dim(d[:100])}")
        for pid in ("P31", "P279"):
            vals = claims_of(ents, qid, pid)
            if vals:
                ensure_labels(ents, vals)
                rendered = ", ".join(fmt_ref(v, ents, st) for v in vals[:4])
                out.append(f"    {fmt_ref(pid, ents, st)}: {rendered}")
        try:
            bk = backlink_count(qid)
            out.append(f"    as P5137 hub: {bk} sense(s) link here")
            if bk > 0:
                for s in sample_p5137_backlinks(qid, limit=5):
                    g = f" \u2014 {s['gloss'][:50]}" if s["gloss"] else ""
                    out.append(f"      {st.magenta(s['sense'])}  {s['lemma']} ({s['lang']}){g}")
        except Exception:
            pass
    return out


def render_probe_walk_up(proposal: dict, ents: dict, st: Style, levels: int) -> list[str]:
    """For each P279 parent referenced in the proposal's create_item ops
    (or in `entities_of_interest`), walk up `levels` hops and show the
    ancestor chain."""
    from wd_common import parent_chain
    parents = []
    for op in proposal.get("ops") or []:
        if op["op"] == "create_item":
            for cl in op.get("claims", []):
                if cl["property"] == "P279" and cl["value"].startswith("Q"):
                    parents.append(cl["value"])
    for qid in proposal.get("entities_of_interest") or []:
        if qid.startswith("Q") and qid not in parents:
            parents.append(qid)
    if not parents:
        return []
    out = [f"{st.bold(f'Probe: upchain ({levels} level(s))')}"]
    for p in parents:
        chain = parent_chain(p, levels=levels)
        flat_ids = [p] + [q for lvl in chain for q in lvl]
        ensure_labels(ents, flat_ids)
        out.append(f"  {fmt_ref(p, ents, st)}")
        for depth, lvl in enumerate(chain, 1):
            indent = "  " + ("  " * depth)
            for q in lvl:
                out.append(f"{indent}\u2191 P279 {fmt_ref(q, ents, st)}")
    return out


def render_entities_of_interest(qids: list, ents: dict, st: Style,
                                 enabled: set) -> list[str]:
    """For an investigation proposal, show the current state of each flagged
    entity \u2014 label, description, P31, P279. P5137 backlink count only if
    the `backlinks` probe is enabled."""
    from wd_common import backlink_count
    ensure_labels(ents, qids)
    out = [f"{st.bold('Entities of interest')}"]
    for qid in qids:
        out.append("")
        out.append(f"  {fmt_ref(qid, ents, st)}")
        d = desc_of(ents, qid)
        if d: out.append(f"    {st.dim(d[:100])}")
        for pid in ("P31", "P279"):
            vals = claims_of(ents, qid, pid)
            if vals:
                ensure_labels(ents, vals)
                rendered = ", ".join(fmt_ref(v, ents, st) for v in vals[:5])
                out.append(f"    {fmt_ref(pid, ents, st)}: {rendered}")
        if "backlinks" in enabled:
            try:
                bk = backlink_count(qid)
                if bk:
                    out.append(f"    as P5137 hub: {bk} sense(s) link here")
            except Exception:
                pass
    return out


def render_declared_probes(proposal: dict, ents: dict, st: Style,
                            enabled: set) -> list[str]:
    probes = proposal.get("probes") or {}
    out: list[str] = []
    eoi = proposal.get("entities_of_interest") or []
    if eoi:
        out.append("")
        out.extend(render_entities_of_interest(eoi, ents, st, enabled))
    if probes.get("related_lemmas") and "lemmas" in enabled:
        lang = probes.get("lemma_lang", "en")
        out.append("")
        out.extend(render_probe_related_lemmas(probes["related_lemmas"], ents, st, lang_iso=lang))
    if probes.get("related_precedents") and "precedents" in enabled:
        out.append("")
        out.extend(render_probe_related_precedents(probes["related_precedents"], ents, st))
    if probes.get("walk_up_levels") and "walk_up" in enabled:
        out.append("")
        out.extend(render_probe_walk_up(proposal, ents, st, levels=probes["walk_up_levels"]))
    return out


def collect_entity_ids(proposal: dict) -> set[str]:
    # Always label-fetch the properties we render inline.
    ids: set[str] = {"P31", "P279", "P5137"}
    for qid in proposal.get("entities_of_interest") or []:
        ids.add(qid)
    for op in proposal.get("ops") or []:
        if op["op"] == "create_item":
            for cl in op.get("claims", []):
                ids.add(cl["property"])
                if cl["value"] and cl["value"][0] in "QL":
                    ids.add(cl["value"])
        elif op["op"] == "add_claim":
            ids.add(op["property"])
            if op.get("entity"):
                ids.add(op["entity"].split("-")[0] if "-S" in op["entity"] else op["entity"])
            if op.get("value") and op["value"][0] in "QL" and not op["value"].startswith("{"):
                ids.add(op["value"])
        elif op["op"] in ("update_description", "update_label", "add_alias"):
            if op.get("entity"):
                ids.add(op["entity"])
    return {i for i in ids if i and i[0] in "PQL"}


# ------------------------- Main -------------------------

ALL_PROBES = ["pattern", "siblings", "backlinks", "lemmas", "precedents",
              "walk_up"]

PROBE_DESCRIPTIONS = {
    "pattern":         "items matching the full P31+P279 classification pattern (SPARQL)",
    "siblings":        "existing direct subclasses of each parent (SPARQL per parent)",
    "backlinks":       "P5137 backlink count for each referenced Q-item (SPARQL each)",
    "lemmas":          "senses of each lemma in `probes.related_lemmas` (SPARQL each)",
    "precedents":      "full render of each Q in `probes.related_precedents` (SPARQL each)",
    "walk_up":         "upchain from proposed P279 parents / entities_of_interest (SPARQL)",
}
# Label search is NOT in ALL_PROBES \u2014 it's always-on for create_item ops.


def parse_enabled(with_arg: str, full: bool) -> set:
    """Return the set of probe names to run. Default: none. --full or
    --with all turns everything on. Otherwise, comma-separated list."""
    if full or with_arg.strip() == "all":
        return set(ALL_PROBES)
    return {p.strip() for p in with_arg.split(",") if p.strip()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", help="Path or slug of a proposal file")
    ap.add_argument("--slug", help="Load proposals/<slug>.json")
    ap.add_argument("--with", dest="with_probes", default="",
                    help="comma-separated probe names to run "
                         f"(or 'all'; choices: {','.join(ALL_PROBES)})")
    ap.add_argument("--full", action="store_true",
                    help="Run all probes (equivalent to --with all)")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    if not args.path and not args.slug:
        ap.error("Specify a proposal path or --slug")

    enabled = parse_enabled(args.with_probes, args.full)
    unknown = enabled - set(ALL_PROBES)
    if unknown:
        ap.error(f"Unknown probe(s): {', '.join(sorted(unknown))}. "
                 f"Valid: {','.join(ALL_PROBES)}")

    proposal, path = load_proposal(args.path or args.slug)
    st = Style(enabled=(not args.no_color) and sys.stdout.isatty())

    # Fetch labels/desc/claims for every referenced entity + all the
    # deeper-referenced Qs (P31/P279 values of referenced entities).
    ids = collect_entity_ids(proposal)
    ents = wbgetentities(sorted(ids))
    deeper = set()
    for qid in [i for i in ids if i.startswith("Q")]:
        for pid in ("P31", "P279"):
            deeper.update(claims_of(ents, qid, pid))
    missing = (deeper - set(ents.keys()))
    if missing:
        ents.update(wbgetentities(sorted(missing), props="labels|descriptions"))

    # Header
    print(HR_HEAVY)
    print(f"  PROPOSAL: {st.bold(proposal['slug'])}  "
          f"{st.dim('(' + proposal.get('kind','?') + ')')}  "
          f"status: {st.yellow(proposal.get('status','draft'))}")
    print(f"  {st.dim('file: ' + str(path))}")
    print(HR_HEAVY)
    print()

    # Rationale
    rat = proposal.get("rationale", "")
    if rat:
        print(st.bold("Rationale"))
        for line in _wrap(rat, 70, indent="  "):
            print(line)
        print()

    # Proposed ops
    for line in render_ops(proposal, ents, st):
        print(line)
    print()

    # Open questions (investigate-style proposals)
    oq = render_open_questions(proposal, st)
    if oq:
        for line in oq:
            print(line)
        print()

    # Related follow-ups (notes for later \u2014 not part of this proposal)
    rf = render_related_followups(proposal, st)
    if rf:
        for line in rf:
            print(line)
        print()

    print(HR)
    # Context (auto-inferred from op shapes). Slow parts gated on enabled.
    for line in render_context(proposal, ents, st, enabled):
        print(line)
    # Declared probes (proposal-specific investigation). Slow; opt-in.
    declared = render_declared_probes(proposal, ents, st, enabled)
    if declared:
        print()
        print(HR)
        for line in declared:
            print(line)
    print()
    print(HR)

    # Footer: what's available but wasn't run
    skipped = [p for p in ALL_PROBES if p not in enabled]
    if skipped:
        print(f"{st.dim('Probes available, not run:')}")
        for p in skipped:
            print(f"  {st.dim('\u2022 ' + p + ' \u2014 ' + PROBE_DESCRIPTIONS[p])}")
        slug = proposal.get("slug", "PROPOSAL")
        print()
        print(st.dim(f"  Run with: python scripts/wd_propose.py --slug {slug} "
                     f"--with <name>[,name\u2026]   or --full for all"))


def _wrap(text: str, width: int, indent: str = "") -> list[str]:
    import textwrap
    return textwrap.wrap(text, width=width, initial_indent=indent,
                         subsequent_indent=indent) or [indent]


if __name__ == "__main__":
    main()

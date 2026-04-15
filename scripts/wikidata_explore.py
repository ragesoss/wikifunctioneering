#!/usr/bin/env python3
"""Explore Wikidata items, properties, and relationships.

Usage:
    python scripts/wikidata_explore.py --item Q159563
    python scripts/wikidata_explore.py --property P31
    python scripts/wikidata_explore.py --sparql "SELECT ?x WHERE { wd:Q159563 ?p ?x } LIMIT 10"
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_REST = "https://www.wikidata.org/w/rest.php/wikibase/v1"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

USER_AGENT = "WikifunctionsExplorer/0.1 (sage@wikiedu.org)"


def api_get(url, params=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_label(entity, lang="en"):
    labels = entity.get("labels", {})
    if lang in labels:
        return labels[lang].get("value", labels[lang]) if isinstance(labels[lang], dict) else labels[lang]
    if labels:
        first = next(iter(labels.values()))
        return first.get("value", first) if isinstance(first, dict) else first
    return "(no label)"


def format_snak_value(snak):
    if snak.get("snaktype") != "value":
        return f"[{snak.get('snaktype', 'unknown')}]"
    dv = snak.get("datavalue", {})
    vtype = dv.get("type")
    val = dv.get("value", {})
    if vtype == "wikibase-entityid":
        eid = val.get("id", "?")
        return eid
    elif vtype == "string":
        return val
    elif vtype == "monolingualtext":
        return f'"{val.get("text")}" ({val.get("language")})'
    elif vtype == "quantity":
        amount = val.get("amount", "?")
        unit = val.get("unit", "")
        if unit and unit != "1":
            unit = unit.split("/")[-1]
            return f"{amount} ({unit})"
        return str(amount)
    elif vtype == "time":
        return val.get("time", "?")
    elif vtype == "globecoordinate":
        return f"({val.get('latitude')}, {val.get('longitude')})"
    else:
        return json.dumps(val, ensure_ascii=False)[:100]


def resolve_labels(entity_ids):
    """Batch-resolve labels for a list of entity IDs."""
    if not entity_ids:
        return {}
    labels = {}
    # Process in batches of 50 (API limit)
    for i in range(0, len(entity_ids), 50):
        batch = entity_ids[i:i+50]
        data = api_get(WIKIDATA_API, {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels",
            "languages": "en",
            "format": "json",
        })
        for eid, edata in data.get("entities", {}).items():
            labels[eid] = get_label(edata)
    return labels


def explore_item(qid):
    data = api_get(WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": qid,
        "format": "json",
    })
    entity = data.get("entities", {}).get(qid)
    if not entity:
        print(f"Item {qid} not found.")
        return

    label = get_label(entity)
    desc = entity.get("descriptions", {}).get("en", {})
    desc_text = desc.get("value", desc) if isinstance(desc, dict) else desc

    print(f"=== {qid}: {label} ===")
    if desc_text:
        print(f"Description: {desc_text}")
    print()

    # Collect all entity IDs referenced in claims for batch label resolution
    entity_refs = set()
    claims = entity.get("claims", {})
    for pid in claims:
        entity_refs.add(pid)
        for claim in claims[pid]:
            mainsnak = claim.get("mainsnak", {})
            dv = mainsnak.get("datavalue", {})
            if dv.get("type") == "wikibase-entityid":
                entity_refs.add(dv["value"].get("id", ""))
            # Also collect qualifier refs
            for qpid, qsnaks in claim.get("qualifiers", {}).items():
                entity_refs.add(qpid)
                for qs in qsnaks:
                    qdv = qs.get("datavalue", {})
                    if qdv.get("type") == "wikibase-entityid":
                        entity_refs.add(qdv["value"].get("id", ""))

    entity_refs.discard("")
    labels = resolve_labels(list(entity_refs))

    print("Properties:")
    for pid, claim_list in sorted(claims.items()):
        prop_label = labels.get(pid, pid)
        for claim in claim_list:
            mainsnak = claim.get("mainsnak", {})
            val_str = format_snak_value(mainsnak)
            # Resolve entity label if it's a QID/PID
            if val_str in labels:
                val_str = f"{val_str} ({labels[val_str]})"
            rank = claim.get("rank", "normal")
            rank_marker = " [preferred]" if rank == "preferred" else " [deprecated]" if rank == "deprecated" else ""
            print(f"  {pid} ({prop_label}): {val_str}{rank_marker}")

            # Show qualifiers
            for qpid, qsnaks in claim.get("qualifiers", {}).items():
                qprop_label = labels.get(qpid, qpid)
                for qs in qsnaks:
                    qval = format_snak_value(qs)
                    if qval in labels:
                        qval = f"{qval} ({labels[qval]})"
                    print(f"    qualifier {qpid} ({qprop_label}): {qval}")
    print()

    # Show aliases
    aliases = entity.get("aliases", {}).get("en", [])
    if aliases:
        alias_strs = [a.get("value", a) if isinstance(a, dict) else a for a in aliases]
        print(f"Aliases (en): {', '.join(alias_strs)}")

    # Show sitelinks count
    sitelinks = entity.get("sitelinks", {})
    if sitelinks:
        print(f"Sitelinks: {len(sitelinks)} wikis")


def explore_property(pid):
    data = api_get(WIKIDATA_API, {
        "action": "wbgetentities",
        "ids": pid,
        "format": "json",
    })
    entity = data.get("entities", {}).get(pid)
    if not entity:
        print(f"Property {pid} not found.")
        return

    label = get_label(entity)
    desc = entity.get("descriptions", {}).get("en", {})
    desc_text = desc.get("value", desc) if isinstance(desc, dict) else desc
    datatype = entity.get("datatype", "unknown")

    print(f"=== {pid}: {label} ===")
    if desc_text:
        print(f"Description: {desc_text}")
    print(f"Datatype: {datatype}")
    print()

    # Show constraints and other claims on the property
    claims = entity.get("claims", {})
    if claims:
        entity_refs = set()
        for cpid in claims:
            entity_refs.add(cpid)
            for claim in claims[cpid]:
                dv = claim.get("mainsnak", {}).get("datavalue", {})
                if dv.get("type") == "wikibase-entityid":
                    entity_refs.add(dv["value"].get("id", ""))
        entity_refs.discard("")
        labels = resolve_labels(list(entity_refs))

        print("Claims on this property:")
        for cpid, claim_list in sorted(claims.items()):
            prop_label = labels.get(cpid, cpid)
            for claim in claim_list:
                val_str = format_snak_value(claim.get("mainsnak", {}))
                if val_str in labels:
                    val_str = f"{val_str} ({labels[val_str]})"
                print(f"  {cpid} ({prop_label}): {val_str}")


def run_sparql(query):
    params = {"query": query, "format": "json"}
    url = f"{SPARQL_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    results = data.get("results", {}).get("bindings", [])
    if not results:
        print("No results.")
        return

    # Get column names
    cols = data.get("head", {}).get("vars", [])
    print(f"Results ({len(results)} rows):")
    print()

    for row in results:
        parts = []
        for col in cols:
            cell = row.get(col, {})
            val = cell.get("value", "")
            # Shorten Wikidata URIs
            if val.startswith("http://www.wikidata.org/entity/"):
                val = val.replace("http://www.wikidata.org/entity/", "")
            elif val.startswith("http://www.wikidata.org/prop/"):
                val = val.replace("http://www.wikidata.org/prop/", "P:")
            parts.append(f"{col}={val}")
        print("  " + "  |  ".join(parts))


def main():
    parser = argparse.ArgumentParser(description="Explore Wikidata items, properties, and relationships")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item", help="Wikidata item ID (e.g. Q159563)")
    group.add_argument("--property", help="Wikidata property ID (e.g. P31)")
    group.add_argument("--sparql", help="SPARQL query to run")

    args = parser.parse_args()

    if args.item:
        explore_item(args.item)
    elif args.property:
        explore_property(args.property)
    elif args.sparql:
        run_sparql(args.sparql)


if __name__ == "__main__":
    main()

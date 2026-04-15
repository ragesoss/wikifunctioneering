# Wikidata Integration in Wikifunctions

## How Wikifunctions accesses Wikidata

Wikifunctions provides built-in types and fetch functions to work with Wikidata entities. Content is fetched on-demand — never stored persistently on Wikifunctions.

## Entity types and fetch functions

| Type | ZID | Fetch function | Input type |
|------|-----|----------------|------------|
| Wikidata Item | Z6003 | Z6821 (Fetch Wikidata Item) | Z6091 (Item Reference) |
| Wikidata Property | Z6004 | Z6822 (Fetch Wikidata Property) | Z6092 (Property Reference) |
| Wikidata Lexeme | Z6005 | Z6825 (Fetch Wikidata Lexeme) | Z6093 (Lexeme Reference) |
| Wikidata Lexeme Form | Z6006 | Z6824 (Fetch Wikidata Lexeme Form) | Z6094 (Form Reference) |
| Wikidata Lexeme Sense | - | Z6826 (Fetch Wikidata Lexeme Sense) | Z6095 (Sense Reference) |

## Statement/claim traversal

Once you have a Wikidata item, you access its data through **statements** and **claims**:

### Key functions for claim traversal

| ZID | Name | Inputs → Output | Purpose |
|-----|------|-----------------|---------|
| Z28294 | predicate of Wikidata property claim | Claim → Property Reference | Get the property (P-number) from a claim |
| Z28297 | value of Wikidata property claim | Claim → (varies) | Get the value from a claim |
| Z28300 | claim type of Wikidata property claim | Claim → Claim Subtype | Is it a value, somevalue, or novalue claim? |
| Z28304 | claim has value? | Claim → Boolean | Check if claim type is "value" |
| Z28308 | claim predicate matches? | Claim, Property Ref → Boolean | Does this claim use a specific property? |
| Z32097 | filter WD claims by exact predicate | List of Claims, Property Ref → List of Claims | Get all claims with a given property |
| Z28312 | qualifiers of WD statement with predicate | Statement, Property Ref → List of Claims | Get qualifier claims |

### Common pattern: extract a property value from an item

The typical flow to get, say, the "instance of" (P31) value from an item:

1. **Fetch the item**: `fetch_wikidata_item(item_reference)` → Wikidata Item
2. **Get its statements**: access the item's statement list
3. **Filter by property**: `filter_claims_by_predicate(claims, P31_reference)` → List of matching claims
4. **Extract value**: `value_of_claim(first_matching_claim)` → the value

### Search functions

| ZID | Name | Purpose |
|-----|------|---------|
| Z6830 | Find lexemes for an item | Find lexemes connected to a Wikidata item |
| Z6831 | Find lexemes for a lexeme sense | Find related lexeme senses |

## Exploring Wikidata structure

Before writing a function that uses Wikidata, you need to understand the data model. Use the exploration script:

```bash
# What properties does a Wikidata item have?
python scripts/wikidata_explore.py --item Q159563

# What does a property mean?
python scripts/wikidata_explore.py --property P31

# Find items in a domain
python scripts/wikidata_explore.py --sparql "SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q193544 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language 'en'. }
} LIMIT 20"
```

## Patterns for Wikidata-aware functions

### Pattern 1: Direct property lookup
Given an item, extract a specific property value. Use when the relationship is a direct property on the item.

### Pattern 2: Traversal
Follow a chain of properties: Item → property → another Item → property → value. Requires composing multiple fetch + filter + extract steps.

### Pattern 3: Search by property value
Find items that have a specific property value. Typically requires SPARQL or iterating over candidates.

### Pattern 4: Lexeme operations
Access linguistic data through lexemes, forms, senses. Common for Abstract Wikipedia work.

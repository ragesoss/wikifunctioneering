# Existing Building Block Functions

Key reusable functions already on Wikifunctions. Search for more via the
local cache (fastest for signature / reverse-dependency queries):
```bash
python scripts/cache_query.py functions --label "term"
python scripts/cache_query.py functions --input Z6007 --output Z6092
python scripts/cache_query.py references Z866 --type Z14
```
Fall back to the live label-search API only when the cache might be
stale (edits in the last few minutes):
```bash
python scripts/wikifunctions_search.py --search "term" --type Z8
```

## Math (Float64)

| ZID | Name | Signature |
|-----|------|-----------|
| Z20849 | add (float64) | Float64, Float64 → Float64 |
| Z21031 | subtract (float64) | Float64, Float64 → Float64 |
| Z21032 | multiply (float64) | Float64, Float64 → Float64 |
| Z21033 | divide (float64) | Float64, Float64 → Float64 |
| Z21028 | exponentiation (float64) | Float64, Float64 → Float64 |
| Z21001 | exponentiation base e | Float64 → Float64 |
| Z21775 | negation (float64) | Float64 → Float64 |
| Z20924 | equality (float64) | Float64, Float64 → Boolean |
| Z22636 | is zero (float64) | Float64 → Boolean |
| Z22583 | mean (float64) | List of Float64 → Float64 |
| Z22236 | modulus (float64) | Float64, Float64 → Float64 |

## Math (Integer)

| ZID | Name | Signature |
|-----|------|-----------|
| Z16693 | add | Integer, Integer → Integer |
| Z17111 | subtract | Integer, Integer → Integer |
| Z17120 | multiply | Integer, Integer → Integer |
| Z17186 | negate | Integer → Integer |
| Z16688 | equals | Integer, Integer → Boolean |
| Z17239 | is zero | Integer → Boolean |
| Z17167 | modulus | Integer, Integer → Integer |
| Z17291 | floor divide | Integer, Integer → Integer |
| Z17591 | in range | Integer, Integer, Integer → Boolean |

## Type Conversion

| ZID | Name | Signature |
|-----|------|-----------|
| Z20937 | integer to float64 | integer: Integer → Float64 |
| Z20841 | integer from float64 | float64: Float64 → Integer |
| Z21534 | truncate float64 to integer | float64: Float64 → Integer |
| Z25073 | integer to string | integer: Integer → String |
| Z19744 | integer to rational | integer: Integer → Rational |
| Z20854 | rational as float | rational: Rational → Float64 |
| Z25294 | amount from quantity | quantity: Wikidata quantity (Z6010) → Rational |

### Parsing (String → numeric)

| ZID | Name | Signature | Notes |
|-----|------|-----------|-------|
| Z14283 | string of digits as Natural Number | String → Natural number | Western Arabic digits only |
| Z16705 | read Integer | String, Language → Integer | Locale-aware integer parsing |
| Z17101 | integer from natural number | Natural number → Integer | Always positive |

### Common type conversion chains

| From | To | Chain |
|------|----|-------|
| Wikidata quantity (Z6010) | Float64 | Z25294 (amount) → Z20854 (rational as float) |
| Wikidata quantity (Z6010) | Rational (Z19677) | Z25294 (amount from quantity) |
| Rational (Z19677) | Float64 | Z20854 (rational as float) |
| Integer | Float64 | Z20937 (integer to float64) |
| Float64 | Integer | Z21534 (truncate float64 to integer) |
| Integer | Rational | Z19744 (integer to rational) |

## Boolean / Conditional

| ZID | Name | Signature |
|-----|------|-----------|
| Z802 | If | Boolean, T, T → T |
| Z10174 | and | Boolean, Boolean → Boolean |
| Z10184 | or | Boolean, Boolean → Boolean |
| Z16676 | not | Boolean → Boolean |
| Z866 | equals | T, T → Boolean |

## String

| ZID | Name | Signature |
|-----|------|-----------|
| Z10000 | join strings | String, String → String |
| Z15175 | join strings (with separator) | String, String, String → String |
| Z11040 | length of string | String → Natural number |
| Z10070 | substring | String, Nat, Nat → String |
| Z10901 | first character | String → String |
| Z14456 | remove first character | String → String |
| Z10008 | is empty string | String → Boolean |
| Z12316 | replace substring | String, String, String → String |

## List

| ZID | Name | Signature |
|-----|------|-----------|
| Z811 | head (first element) | List of T → T |
| Z812 | tail | List of T → List of T |
| Z813 | is empty | List of T → Boolean |
| Z12681 | length | List of T → Natural number |
| Z872 | filter | List of T, (T → Boolean) → List of T |
| Z28316 | filter with bound argument | List of T, (T, U → Boolean), U → List of T |

## Wikidata — Fetching Entities

| ZID | Name | Signature |
|-----|------|-----------|
| Z6821 | Fetch Wikidata Item | Item Reference → Wikidata Item |
| Z6822 | Fetch Wikidata Property | Property Reference → Wikidata Property |
| Z6825 | Fetch Wikidata Lexeme | Lexeme Reference → Wikidata Lexeme |
| Z6824 | Fetch Wikidata Lexeme Form | Form Reference → Wikidata Lexeme Form |
| Z6826 | Fetch Wikidata Lexeme Sense | Sense Reference → Wikidata Lexeme Sense |
| Z30248 | Fetch Wikidata Items (batch) | List of Item Refs → List of Items |

## Wikidata — Claims and Statements

| ZID | Name | Signature |
|-----|------|-----------|
| Z22220 | claims from Wikidata item | Wikidata Item → List of Claims |
| Z28294 | predicate of claim | Claim → Property Reference |
| Z28297 | value of claim | Claim → (value type, Z1) |
| Z28300 | claim type | Claim → Claim Subtype |
| Z28304 | claim has value? | Claim → Boolean |
| Z28308 | claim predicate matches? | Claim, Property Ref → Boolean |
| Z32097 | filter claims by exact predicate | List of Claims, Property Ref → List of Claims |
| Z28312 | qualifiers with predicate | Statement, Property Ref → List of Claims |
| Z28321 | qualifier values with predicate | Statement, Property Ref → Z1 (list of qualifier values) |
| Z23680 | claim with highest rank | List of Claims → Claim |
| Z21449 | value of first property claim from item | Item, Property Ref → value (Z1) |

### Statement-level access (shortcuts for common claim patterns)

| ZID | Name | Signature | Notes |
|-----|------|-----------|-------|
| Z23451 | statement with highest rank | Item, Property Ref → Statement (Z6003) | Returns the statement itself (not the value) — use when you need access to qualifiers |
| Z23459 | statement value with highest rank | Item, Property Ref → value (Z1) | Returns the main value only |
| Z19308 | value of statement | Statement (Z6003) → Z1 | Extracts Z6003K3 |
| Z28513 | filter statements by qualifiers | List of Z1, List of Property Refs → List of Statements | Keeps only statements that have qualifiers with specified properties; empty property list = keep all with any qualifier |
| Z33103 | statement value is reference to item? | Statement (Z6003), Item Ref (Z6091) → Boolean | Checks if a statement's main value matches a given item reference. Key for filtering claims by value with Z28316. |
| Z29691 | get statements for property from item | Item, Property Ref → List of Statements | Returns all statements for a property (not just highest rank) |

## Wikidata — Items

| ZID | Name | Signature |
|-----|------|-----------|
| Z6801 | same Wikidata item | Item, Item → Boolean |
| Z19316 | item references equal | Item Ref, Item Ref → Boolean |
| Z20041 | item reference to QID string | Item Ref → String |
| Z23753 | item reference to label | Item Ref, Language → String |
| Z27299 | item has claim? | Item, Property Ref → Boolean |

## Type casting from Z1 (Object)

When claim values and qualifier values come back as Z1 (generic), these functions cast them to specific types for use in typed compositions:

| ZID | Name | Signature | Notes |
|-----|------|-----------|-------|
| Z23742 | Object as Wikidata item reference | Z1 → Z6091 | Cast untyped item reference to typed |
| Z23737 | Object as Wikidata item | Z1 → Z6001 | Cast untyped item to typed |
| Z29335 | Wikidata item reference from object | Z1 → Z6091 | Extracts QID from various object shapes |
| Z31120 | string from object | Z1 → String | Extract or derive a string from any object |

## Wikidata — Qualifier Extraction (user-created)

| ZID | Name | Signature | Notes |
|-----|------|-----------|-------|
| Z33573 | qualifier value of item property claim | Item, Property Ref, Property Ref → Z1 | Gets qualifier value from an item's highest-ranked claim for a property |
| Z33579 | qualifier value of Wikidata statement | Statement (Z6003), Property Ref → Z1 | Extracts a qualifier value from a single statement |
| Z33588 | first statement with qualifier | Item, Property Ref, Property Ref → Statement (Z6003) | Selects first statement that has the specified qualifier |

## Type Conversion Helpers (user-created)

| ZID | Name | Signature | Notes |
|-----|------|-----------|-------|
| Z33592 | integer from object | Z1 → Integer | Chain: Z31120 → Z14283 → Z17101. Use when extracting numeric values from Wikidata claims. |

## Music Theory (user-created)

| ZID | Name | Signature |
|-----|------|-----------|
| Z25217 | frequency of pitch in A440 | pitch class: String, octave: Integer → Float64 |
| Z25218 | A4 frequency of pitch standard | pitch standard: Wikidata item (Z6001) → Wikidata quantity (Z6010) |
| Z25219 | difference between pitches in semitones | first pitch class: String, first octave: Int, second pitch class: String, second octave: Int → Integer |
| Z25220 | distance from C in semitones | pitch: String → Integer |
| Z25224 | semitones between pitches within an octave | first pitch: String, second pitch: String → Integer |
| Z25227 | semitones between octaves | first octave: Integer, second octave: Integer → Integer |
| Z25230 | semitone distance from A4 | pitch class: String, octave: Integer → Integer |
| Z25232 | frequency ratio of semitone distance in 12TET | semitone distance: Integer → Float64 |
| Z25407 | transpose pitch | ? |
| Z25408 | pitch by distance from C in semitones | ? |
| Z33288 | Wikidata pitch item for MIDI note number | ? |
| Z33570 | reference note of pitch standard | pitch standard: Z6001 → Z6091 (Item Reference) |
| Z33590 | MIDI number of pitch item | note: Z6001 → Integer | Extracts MIDI number from a Wikidata pitch item via P361/P1545 |
| Z33600 | MIDI number of pitch | pitch class: String, octave: Integer → Integer | Computes (octave+1)*12 + distance_from_C |
| Z33603 | reference frequency of pitch standard | pitch standard: Z6001 → Float64 | Extracts reference frequency in Hz via Z25218 → Z25294 → Z20854 |
| Z33605 | frequency of pitch in 12-TET standard | pitch class: String, octave: Integer, pitch standard: Z6001 → Float64 | Top-level: ref_freq × 2^((input_midi − ref_midi) / 12) |
| Z33606 | MIDI number of reference note | pitch standard: Z6001 → Integer | Helper: MIDI of a pitch standard's reference note |
| Z33682 | frequency of MIDI note number | midi note number: Integer, pitch standard: Z6001 → Float64 | Same formula as Z33605, with MIDI provided directly instead of pitch-class + octave |

## Lexemes / Wikidata-grounded text (user-created)

| ZID | Name | Signature | Notes |
|-----|------|-----------|-------|
| Z33668 | word for concept | concept: Z6091, language: Z60, lexical category: Z6091 → String | Looks up the best-ranked lexeme whose `item for this sense` (P5137) points at the concept, and returns its lemma. Wraps Z33071 + Z21806.

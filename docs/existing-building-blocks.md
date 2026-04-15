# Existing Building Block Functions

Key reusable functions already on Wikifunctions. Search for more with:
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
| Z28297 | value of claim | Claim → (value type) |
| Z28300 | claim type | Claim → Claim Subtype |
| Z28304 | claim has value? | Claim → Boolean |
| Z28308 | claim predicate matches? | Claim, Property Ref → Boolean |
| Z32097 | filter claims by exact predicate | List of Claims, Property Ref → List of Claims |
| Z28312 | qualifiers with predicate | Statement, Property Ref → List of Claims |
| Z23680 | claim with highest rank | List of Claims → Claim |
| Z21449 | value of first property claim from item | Item, Property Ref → value |

## Wikidata — Items

| ZID | Name | Signature |
|-----|------|-----------|
| Z6801 | same Wikidata item | Item, Item → Boolean |
| Z19316 | item references equal | Item Ref, Item Ref → Boolean |
| Z20041 | item reference to QID string | Item Ref → String |
| Z23753 | item reference to label | Item Ref, Language → String |
| Z27299 | item has claim? | Item, Property Ref → Boolean |

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

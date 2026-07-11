def Z18522(Z18522K1):
    import re
    MARK = chr(0xE000)
    DOT = chr(0xE001)
    # List mode: if the text BEGINS with a list marker (bullet, number, or
    # single letter + . / ) / .) ), it's a list, not prose — split only
    # BEFORE each marker. Longest marker variants come first in the group.
    MARKER = r"(?:[•⁃]\s*\d+\.|\d+\.\)|\d+\)|\d+\.|[a-z]\.)"
    if re.match(r"\s*" + MARKER + r"\s", Z18522K1):
        # (?<![•⁃]) keeps the space inside a "• 9." marker from splitting.
        marked = re.sub(r"(?<![•⁃])\s+(" + MARKER + r"\s)", MARK + r"\1", Z18522K1)
        return [p.strip() for p in marked.split(MARK) if p.strip()]
    ALWAYS = ["mr", "mrs", "ms", "dr", "prof", "st", "mt", "sr", "jr", "rev",
              "gov", "sen", "rep", "pres", "hon", "fr", "col", "gen", "lt",
              "sgt", "capt", "sir", "pope", "messrs", "no", "vol", "pp", "p",
              "al", "ed", "cf", "vs", "esp", "op", "fig", "approx"]
    COMPANY = ["co", "inc", "ltd", "corp", "llc", "plc"]
    t = Z18522K1
    # 1. decimals / numbers
    t = re.sub(r"(?<=\d)\.(?=\d)", DOT, t)
    # 2. acronyms (U.S., U.S.A., e.g.): protect internal dots, keep final

    def _acr(m):
        s = m.group(0)
        return s[:-1].replace(".", DOT) + s[-1]
    t = re.sub(r"\b(?:[A-Za-z]\.){2,}", _acr, t)
    # 3. always-protected abbreviations
    t = re.sub(r"\b(" + "|".join(ALWAYS) + r")\.",
               lambda m: m.group(1) + DOT, t, flags=re.IGNORECASE)
    # 4. company abbrevs: protect only if next word is lowercase

    def _company(m):
        abbr, ws, nxt = m.group(1), m.group(2), m.group(3)
        return abbr + DOT + ws + nxt if nxt.islower() else m.group(0)
    t = re.sub(r"\b(" + "|".join(COMPANY) + r")\.(\s+)([A-Za-z])",
               _company, t, flags=re.IGNORECASE)
    # 5. middle initial between capitalized words
    t = re.sub(r"(\b[A-Z][a-z]+\s+[A-Z])\.(?=\s+[A-Z])", r"\1" + DOT, t)
    # 6. insert split markers at real boundaries
    t = re.sub(r"([.!?]+[\"'”’)\]]*)(\s+)(?=[A-Z])", r"\1\2" + MARK, t)
    t = re.sub(r"([.!?]+[\"'”’)\]]*)\s*$", r"\1" + MARK, t)
    t = re.sub(r"(?<=[a-z0-9])([.!?]+)(?=[A-Z])", r"\1" + MARK, t)
    # 7. split, restore, trim
    out = []
    for p in t.split(MARK):
        p = p.replace(DOT, ".").strip()
        if p:
            out.append(p)
    return out

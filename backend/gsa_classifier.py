import re
import unicodedata

RULES = [
    ("nuclear_use", 5, [
        r"\b(?:nuclear weapon|nuclear bomb|atomic bomb)\b.{0,50}\b(?:detonated|exploded|used)\b",
        r"\b(?:detonated|exploded|used)\b.{0,50}\b(?:nuclear weapon|nuclear bomb|atomic bomb)\b",
        r"\bnuclear detonation\b",
    ]),
    ("war_outbreak", 5, [
        r"\bwar (?:has )?broken out\b",
        r"\bwar breaks out\b",
        r"\bwar erupted\b",
        r"\bwar erupts\b",
        r"\bfull.scale war (?:began|started|erupted)\b",
    ]),
    ("invasion", 5, [
        r"\binvasion (?:began|started|is underway)\b",
        r"\b(?:invaded|invades)\b",
        r"\btroops crossed (?:the )?border\b",
        r"\bforces crossed (?:the )?border\b",
    ]),
    ("government_overthrow", 5, [
        r"\bgovernment (?:was )?(?:overthrown|toppled)\b",
        r"\bgovernment has fallen\b",
        r"\bcoup (?:succeeded|succeeds)\b",
        r"\bseized power\b",
        r"\boverthrew the government\b",
    ]),
    ("military_coup", 4, [
        r"\bmilitary coup (?:began|underway|launched)\b",
        r"\bcoup attempt (?:began|underway|launched)\b",
        r"\bsoldiers seized (?:the )?(?:capital|presidential palace|parliament)\b",
    ]),
    ("strait_closure", 4, [
        r"\bstrait of hormuz (?:is )?(?:closed|shut)\b",
        r"\bclosed the strait of hormuz\b",
        r"\bblocked the strait of hormuz\b",
    ]),
    ("blockade", 4, [
        r"\bnaval blockade (?:began|started|imposed)\b",
        r"\b(?:imposed|began|started) (?:a )?naval blockade\b",
    ]),
    ("major_strike", 4, [
        r"\blaunches? missiles?\b.{0,100}\b(?:damaging|damages|destroying|destroys|hitting|hits|striking|strikes)\b.{0,60}\b(?:military base|military facility|base|facility)\b",
        r"\b(?:airstrike|air strike|airstrikes|air strikes)\b.{0,65}\b(?:hit|hits|struck|destroyed|damaged)\b",
        r"\b(?:hit|hits|struck|attacked|destroyed|damaged)\b.{0,65}\b(?:military base|military facility|nuclear facility|refinery|power plant)\b",
        r"\bmissiles? (?:were )?(?:launched|fired) at\b",
        r"\b(?:launched|fired) missiles? at\b",
        r"\bmissile strike (?:hit|hits|struck|damaged)\b",
        r"\bcarried out (?:an )?airstrike\b",
    ]),
]

FUTURE = [
    r"\bplans? to\b", r"\bplanned to\b",
    r"\bprepares? to\b", r"\bprepares? for\b",
    r"\bpreparing to\b", r"\bpreparing for\b",
    r"\bthreatens? to\b", r"\bthreatened to\b",
    r"\bexpected to\b", r"\blikely to\b",
    r"\bpoised to\b", r"\bmay attack\b",
    r"\bmight attack\b", r"\bcould attack\b",
    r"\bmay invade\b", r"\bcould invade\b",
    r"\bcould happen\b", r"\bmay happen\b",
    r"\bmight happen\b",
]

UNVERIFIED = [
    r"\bunconfirmed\b", r"\bnot confirmed\b",
    r"\balleged(?:ly)?\b", r"\brumou?rs?\b",
    r"\bfalse claim\b", r"\bdenies that\b",
    r"\bdenied that\b",
]

def clean(text):
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()

def matches(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)

def classify(title, summary=""):
    headline = clean(title)
    body = clean(summary)
    combined = headline + " " + body

    if not headline:
        return None

    if matches(UNVERIFIED, headline):
        return None

    if matches(FUTURE, headline):
        return None

    if re.search(
        r"\b(?:no attack|no invasion|no coup|no blockade|"
        r"did not launch|did not strike|did not attack|"
        r"has not attacked|was not confirmed)\b",
        headline
    ):
        return None

    for category, level, patterns in RULES:
        if matches(patterns, combined):
            return category, level

    return None

import re
from difflib import SequenceMatcher

STOP = {
    "the", "a", "an", "in", "on", "at", "by", "to",
    "of", "and", "near", "after", "before", "with"
}

ALIASES = {
    "missiles": "missile",
    "hits": "hit",
    "strikes": "strike",
    "attacks": "attack",
    "bases": "base",
    "facilities": "facility",
    "damages": "damage",
    "damaged": "damage",
    "hitting": "hit",
    "striking": "strike"
}

def normalized_words(text):
    words = re.findall(r"[a-z]+", (text or "").lower())
    return {
        ALIASES.get(w, w)
        for w in words
        if w not in STOP
    }

def location_conflict(title_a, title_b):
    locations = {
        "kyiv", "odesa", "odessa", "kharkiv", "moscow",
        "belgorod", "donetsk", "luhansk", "gaza",
        "jerusalem", "tel", "beirut", "damascus",
        "baghdad", "tehran", "isfahan", "taipei",
        "beijing", "seoul", "pyongyang", "washington",
        "london", "paris", "berlin", "riyadh", "sanaa",
        "kabul"
    }

    a = normalized_words(title_a) & locations
    b = normalized_words(title_b) & locations

    return bool(a and b and a.isdisjoint(b))

def same_event(title_a, title_b):
    if location_conflict(title_a, title_b):
        return False

    a = normalized_words(title_a)
    b = normalized_words(title_b)

    if not a or not b:
        return False

    overlap = len(a & b) / min(len(a), len(b))
    similarity = SequenceMatcher(
        None, " ".join(sorted(a)), " ".join(sorted(b))
    ).ratio()

    common_event_words = a & b

    return (
        overlap >= 0.75
        and len(common_event_words) >= 3
        and similarity >= 0.45
    )

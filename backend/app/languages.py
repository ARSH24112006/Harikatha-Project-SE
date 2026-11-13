"""Language names and cheap checks that output is in the requested language."""
import re

NAMES = {
    "bn-IN": "Bengali", "en-IN": "English", "gu-IN": "Gujarati", "hi-IN": "Hindi",
    "kn-IN": "Kannada", "ml-IN": "Malayalam", "mr-IN": "Marathi", "od-IN": "Odia",
    "pa-IN": "Punjabi", "ta-IN": "Tamil", "te-IN": "Telugu",
}

# Unicode block of each language's script.
_SCRIPT = {
    "bn-IN": "ঀ-৿", "gu-IN": "઀-૿", "hi-IN": "ऀ-ॿ",
    "kn-IN": "ಀ-೿", "ml-IN": "ഀ-ൿ", "mr-IN": "ऀ-ॿ",
    "od-IN": "଀-୿", "pa-IN": "਀-੿", "ta-IN": "஀-௿",
    "te-IN": "ఀ-౿",
}

# Words that are Marathi but not Hindi. Devanagari alone cannot tell the two apart.
_MARATHI_ONLY = {"आहे", "आहेत", "नावाचा", "नावाची", "नावाचे", "म्हणून", "तेव्हा", "झाला", "झाली"}

MAX_LATIN_SHARE = 0.15  # a few English names or words are fine in a Hindi line


def name(code: str) -> str:
    return NAMES.get(code, code)


def problem(text: str, code: str) -> str | None:
    """Return a short reason if `text` is not in the language of `code`, else None."""
    letters = re.findall(r"[^\W\d_]", text)
    if len(letters) < 12:  # too short to judge
        return None
    if code in _SCRIPT:
        latin = sum(1 for c in letters if c.isascii())
        if latin / len(letters) > MAX_LATIN_SHARE:
            return f"mostly Latin letters; write in {name(code)} using its own script"
        if not re.search(f"[{_SCRIPT[code]}]", text):
            return f"no {name(code)} script found"
    # \w would split Devanagari words at vowel signs (matras), so split on spaces/punctuation instead.
    words = set(re.split(r"[\s।॥.,!?;:\"'()\-]+", text))
    if code == "hi-IN" and _MARATHI_ONLY & words:
        return "this looks like Marathi, not Hindi; use Hindi vocabulary and grammar"
    return None

"""Simple language detection for the five demo languages, used to keep the agent's answer language in sync.

The realtime model is told to answer in the language of the latest message, but after a language
switch it sometimes stays in the previous language. The app therefore detects the language of each
patient message and, when it changes, tells the agent explicitly. Short or ambiguous messages
("okay") return None and change nothing.
"""

import re

_WORDS = {
    "de": {"ich", "ist", "das", "und", "nicht", "mein", "meine", "kann", "wie", "was", "wann", "bitte", "habe", "muss",
           "ja", "nein", "danke", "der", "die", "den", "dem", "mir", "mich", "sie", "es", "ein", "eine", "einfach", "wieder",
           "noch", "auch", "geht", "gut", "darf", "soll", "welche", "welchen", "termin", "tabletten", "fieber", "brief"},
    "en": {"i", "the", "is", "do", "my", "what", "which", "when", "can", "have", "you", "it", "and", "not", "me", "a", "an",
           "please", "yes", "no", "thanks", "how", "should", "am", "are", "does", "to", "of", "appointment", "appointments",
           "tablets", "fever", "letter"},
    "tr": {"ve", "bir", "bu", "ne", "zaman", "mi", "mı", "mu", "mü", "nasıl", "evet", "hayır", "teşekkürler", "benim",
           "randevu", "randevum", "ilaç", "ilaçları", "ateş", "ateşim", "nerede", "var", "yok", "lütfen"},
}
_TURKISH_LETTERS = re.compile(r"[şğıİ]")


def detect_language(text: str) -> str | None:
    """Return 'de', 'en', 'tr', 'ar' or 'uk' for a patient message, or None if unclear."""
    if not text:
        return None
    if re.search(r"[\u0600-\u06FF]", text):
        return "ar"
    if re.search(r"[\u0400-\u04FF]", text):
        return "uk"
    words = re.findall(r"[a-zäöüßçğıişéè]+", text.lower())
    scores = {code: sum(word in vocabulary for word in words) for code, vocabulary in _WORDS.items()}
    if _TURKISH_LETTERS.search(text):
        scores["tr"] += 2
    if re.search(r"[äöüß]", text.lower()):
        scores["de"] += 2
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] < 2 or ranked[0] == ranked[1]:
        return None
    return best

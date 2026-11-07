"""Rule-based alarm, independent of the model: acute danger signs in a visitor's words call staff at once.

The same word list as the Entlass-Assistent. In the foyer the right reaction is not "call 112" but
"stay here, a colleague is coming" (the hospital's emergency team is on site).
"""

import unicodedata

EMERGENCY_TERMS = [
    "brustschmerz", "schmerzen in der brust", "schmerz in der brust", "atemnot", "keine luft",
    "schlecht luft", "kaum luft", "bewusstlos", "ohnmächtig", "bewusstsein verloren", "zusammengebrochen",
    "chest pain", "pain in my chest", "can't breathe", "cannot breathe", "can not breathe",
    "short of breath", "shortness of breath", "unconscious", "passed out", "collapsed",
    "göğüs ağrı", "göğsüm ağrı", "nefes alamıyorum", "nefes darlığı", "bayıldı",
    "ألم في الصدر", "ألم بالصدر", "ضيق في التنفس", "لا أستطيع التنفس", "فقد الوعي",
    "біль у грудях", "біль в грудях", "болить у грудях", "задишка", "не можу дихати", "знепритомн",
]


def detect_emergency(text: str) -> str | None:
    folded = unicodedata.normalize("NFKC", text or "").lower().replace("’", "'")
    return next((term for term in EMERGENCY_TERMS if term in folded), None)

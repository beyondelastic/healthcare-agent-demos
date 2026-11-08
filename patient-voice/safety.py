"""Deterministic safety checks in the app, independent of the model and of Foundry guardrails.

1. ``check_answer``: every spoken answer is checked while it streams. Drug names and doses must
   match the approved letter; a drug that neither the letter nor the patient mentioned, a dose that
   isn't in the letter, or a dose paired with the wrong drug stops the answer.
2. ``detect_emergency``: acute danger signs in the patient's words trigger the 112 notice by rule,
   even if the model doesn't react.

These are simple, auditable rules (word lists and patterns), not a medical judgement. They narrow
what can reach the patient; they don't prove that an answer is correct.
"""

import re
import unicodedata

from tools import LETTER

# Phrases that would be medication advice. The same list is uploaded as a Foundry blocklist by
# setup_guardrail.py; the app enforces it as well. Written case-tolerant ([Ss]) for the blocklist.
ADVICE_PATTERNS = {
    "de-absetzen": r"([Ss]ie (können|dürfen)|(können|dürfen) [Ss]ie) (das |die |ihr |ihre )?\w+ "
                   r"(ruhig |einfach |jetzt )?(absetzen|weglassen)",
    "de-mehr-nehmen": r"[Nn]ehmen [Ss]ie (ruhig |einfach )?(eine )?(zusätzlich|mehr|doppelt)",
    "de-dosis-aendern": r"([Vv]erdoppeln|[Ee]rhöhen|[Hh]albieren) [Ss]ie (die|Ihre) [Dd]osis",
    "en-stop": r"([Yy]es,? you can|[Yy]ou can (safely|just)) stop taking",
    "en-dose": r"([Dd]ouble|[Ii]ncrease|[Hh]alve) (the|your) dose",
    "en-extra": r"[Tt]ake (an )?(extra|additional|more) (tablet|pill|dose)",
    "tr-birak": r"ilac(ı|ınızı) bırakabilirsiniz",
}

# Structured medication plan from the approved letter (same facts as the "medication" section).
MEDICATIONS = LETTER["medication_plan"]

# Spellings of the letter's drugs in the five demo languages (transcripts may use local scripts).
_ALIASES = {
    "Ibuprofen": ["ibuprofen", "ibuprofeno", "ібупрофен", "ибупрофен", "إيبوبروفين", "ايبوبروفين"],
    "Pantoprazol": ["pantoprazol", "pantoprazole", "пантопразол", "بانتوبرازول"],
    "Ramipril": ["ramipril", "раміприл", "рамиприл", "راميبريل"],
}

# Common drugs that are NOT in this letter (generic and German brand names). Mentioning one is
# only allowed if the patient brought it up first, e.g. "Darf ich Paracetamol nehmen?".
OTHER_DRUGS = [
    "paracetamol", "acetaminophen", "metamizol", "novalgin", "aspirin", "acetylsalicylsäure", "ass",
    "diclofenac", "voltaren", "naproxen", "tramadol", "tilidin", "codein", "morphin", "oxycodon",
    "omeprazol", "esomeprazol", "lansoprazol", "metoprolol", "bisoprolol", "amlodipin", "candesartan",
    "valsartan", "lisinopril", "enalapril", "hydrochlorothiazid", "torasemid", "furosemid", "metformin",
    "insulin", "marcumar", "phenprocoumon", "heparin", "enoxaparin", "clexane", "apixaban", "eliquis",
    "rivaroxaban", "xarelto", "simvastatin", "atorvastatin", "amoxicillin", "cefuroxim", "ciprofloxacin",
    "buscopan", "butylscopolamin", "metoclopramid", "ondansetron", "lorazepam", "diazepam", "zopiclon",
]

_UNITS = r"(mg|milligramm|milligrams?|miligram|мг|ملغ|مجم|ملغم)"
_DOSE = re.compile(r"(\d+(?:[.,]\d+)?)\s*" + _UNITS + r"\b(?!\s*(?:/|pro\b|per\b|je\b|на\b|في\b|lit))",
                   re.IGNORECASE)  # lab concentrations like "CRP 18 mg/l" aren't doses
_PAIR_WINDOW = 60  # characters between a drug name and "N mg" that belong together

# Acute danger signs (the letter's 112 criteria) in the five demo languages.
EMERGENCY_TERMS = [
    "brustschmerz", "schmerzen in der brust", "schmerz in der brust", "atemnot", "keine luft",
    "schlecht luft", "kaum luft", "bewusstlos", "ohnmächtig", "bewusstsein verloren",
    "chest pain", "pain in my chest", "can't breathe", "cannot breathe", "can not breathe",
    "short of breath", "shortness of breath", "unconscious", "passed out",
    "göğüs ağrı", "göğsüm ağrı", "nefes alamıyorum", "nefes darlığı", "bayıldı",
    "ألم في الصدر", "ألم بالصدر", "ضيق في التنفس", "لا أستطيع التنفس", "فقد الوعي",
    "біль у грудях", "біль в грудях", "болить у грудях", "задишка", "не можу дихати", "знепритомн",
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().replace("’", "'")
    # Arabic-Indic digits -> ASCII, so "٤٠٠ ملغ" is checked like "400 mg".
    return text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))


def _number(value: str) -> float:
    return float(value.replace(",", "."))


def _strength(medication: dict) -> float:
    return _number(_DOSE.search(medication["strength"]).group(1))


ALLOWED_DOSES = {_strength(m) for m in MEDICATIONS}
STRENGTH = {m["name"]: _strength(m) for m in MEDICATIONS}


def _letter_drug_positions(text: str) -> list[tuple[int, str]]:
    found = []
    for name, spellings in _ALIASES.items():
        for spelling in spellings:
            found += [(m.start(), name) for m in re.finditer(re.escape(spelling), text)]
    return sorted(found)


def check_answer(answer: str, patient_text: str = "") -> dict | None:
    """Return the first problem in an (partial) answer, or None.

    ``patient_text`` is everything the patient said so far: drugs they named may be repeated.
    """
    text, said = _normalize(answer), _normalize(patient_text)
    for name, pattern in ADVICE_PATTERNS.items():
        found = re.search(pattern, answer or "", re.IGNORECASE)
        if found:
            return {"rule": "ratschlag", "found": found.group(0),
                    "reason": f"Formulierung „{found.group(0)}“ wäre ein Therapieratschlag (Blockliste {name})."}
    for drug in OTHER_DRUGS:
        pattern = rf"\b{re.escape(drug)}\b"
        if re.search(pattern, text) and not re.search(pattern, said):
            return {"rule": "fremdes_medikament", "found": drug,
                    "reason": f"Medikament „{drug}“ steht nicht im freigegebenen Brief."}
    drugs = _letter_drug_positions(text)
    for match in _DOSE.finditer(text):
        dose = _number(match.group(1))
        before = [name for pos, name in drugs if 0 <= match.start() - pos <= _PAIR_WINDOW]
        if before and dose != STRENGTH[before[-1]]:
            return {"rule": "verwechslung", "found": match.group(0),
                    "reason": f"{before[-1]} {match.group(0)} – im Brief steht {before[-1]} "
                              f"{next(m['strength'] for m in MEDICATIONS if m['name'] == before[-1])}."}
        if dose not in ALLOWED_DOSES:
            return {"rule": "dosis_nicht_im_brief", "found": match.group(0),
                    "reason": f"Dosis „{match.group(0)}“ steht nicht im freigegebenen Brief."}
    return None


def detect_emergency(patient_text: str) -> str | None:
    text = _normalize(patient_text)
    return next((term for term in EMERGENCY_TERMS if term in text), None)


# Warning signs from the letter ("Wiedervorstellung bei ..."): an urgent callback by rule.
FEVER_WORDS = ["fieber", "temperatur", "fever", "temperature", "ateş", "ateşim", "sıcaklık", "حمى", "حرارة", "حرارتي",
               "температура", "жар", "гарячка"]
# Spelled-out temperatures of 38.5 °C and above, as speech transcription may write them.
FEVER_SPELLED = ["achtunddreißig komma fünf", "achtunddreißig fünf", "neununddreißig", "vierzig", "einundvierzig",
                 "thirty-eight point five", "thirty eight point five", "thirty-nine", "thirty nine", "forty",
                 "hundred and one", "hundred and two", "hundred and three", "otuz sekiz buçuk", "otuz dokuz", "kırk",
                 "тридцять дев", "сорок", "تسعة وثلاثين", "تسع وثلاثين", "تسعة وثلاثون", "أربعين", "اربعين"]
HIGH_FEVER = ["hohes fieber", "high fever", "yüksek ateş", "حمى شديدة", "حرارة مرتفعة", "висока температура"]
WARNING_SIGNS = {
    "Gelbfärbung von Haut oder Augen": ["gelbe haut", "gelbe augen", "haut ist gelb", "augen sind gelb", "gelb geworden",
                                        "yellow skin", "yellow eyes", "skin is yellow", "eyes are yellow", "turned yellow",
                                        "sarı", "اصفرار", "жовт"],
    "anhaltendes Erbrechen": ["erbreche", "muss ständig brechen", "übergebe mich", "keep vomiting", "vomiting", "throwing up",
                              "kusuyorum", "kusma", "أتقيأ", "تقيؤ", "блюю", "блювота", "блювання"],
    "Wunde gerötet, geschwollen oder nässend": ["wunde ist rot", "wunde rot", "wunde geschwollen", "wunde nässt", "wunde eitert",
                                                "wunde eitrig", "wound is red", "wound is swollen", "wound is leaking", "pus coming",
                                                "yara kızar", "yara şiş", "yarada iltihap", "الجرح أحمر", "الجرح منتفخ",
                                                "рана червон", "рана опух", "гній"],
    "zunehmende Bauchschmerzen": ["bauchschmerzen werden stärker", "bauchschmerzen werden schlimmer", "immer stärkere bauchschmerzen",
                                  "zunehmende bauchschmerzen", "stomach pain is getting worse", "belly pain is getting worse",
                                  "karın ağrım artıyor", "ألم البطن يزداد", "біль у животі посилюється"],
}
_NUMBER = re.compile(r"(\d{2,3}(?:[.,]\d)?)")


def detect_warning(patient_text: str) -> str | None:
    """Warning sign from the letter in the patient's words, e.g. fever over 38.5 °C. None if not found."""
    text = _normalize(patient_text)
    if any(word in text for word in FEVER_WORDS) or any(word in text for word in HIGH_FEVER):
        values = [_number(n) for n in _NUMBER.findall(text)]
        # Celsius 38.5-43, or Fahrenheit 101-110 (38.3 °C and above)
        if (any(38.5 <= v <= 43 or 101 <= v <= 110 for v in values) or any(w in text for w in FEVER_SPELLED)
                or any(w in text for w in HIGH_FEVER)):
            return "Fieber über 38,5 °C"
    for sign, words in WARNING_SIGNS.items():
        if any(word in text for word in words):
            return sign
    return None

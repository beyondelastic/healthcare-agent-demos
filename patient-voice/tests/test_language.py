import pytest

from language import detect_language


@pytest.mark.parametrize("text,code", [
    ("Welche Tabletten muss ich wann nehmen?", "de"),
    ("Mir geht es wieder ganz gut. Kann ich das Ramipril einfach weglassen?", "de"),
    ("In meinem Brief steht 1-0-0 und p.o. – was bedeutet das?", "de"),
    ("Ich habe neununddreißig Grad Fieber bekommen.", "de"),
    ("Which appointments do I have?", "en"),
    ("What appointments do I have?", "en"),
    ("I feel fine. Can I stop taking the Ramipril?", "en"),
    ("Hangi ilaçları ne zaman almam gerekiyor?", "tr"),
    ("Bir sonraki randevum ne zaman?", "tr"),
    ("متى يمكنني العودة إلى العمل؟", "ar"),
    ("У мене температура 39 градусів.", "uk"),
])
def test_languages_are_detected(text, code):
    assert detect_language(text) == code


@pytest.mark.parametrize("text", ["Okay", "Ramipril?", "10:30", ""])
def test_short_or_ambiguous_messages_change_nothing(text):
    assert detect_language(text) is None

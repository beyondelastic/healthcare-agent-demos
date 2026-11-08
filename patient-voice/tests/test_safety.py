import re

import pytest

import safety
import tools


@pytest.fixture(autouse=True)
def clean():
    tools.reset()
    yield
    tools.reset()


def test_medication_plan_matches_the_letter_text():
    text = tools.SECTIONS["medication"]["text"]
    for medication in safety.MEDICATIONS:
        assert f"{medication['name']} {medication['strength']}" in text


@pytest.mark.parametrize("answer", [
    "Sie nehmen Ramipril 5 mg einmal morgens und Pantoprazol 20 mg vor dem Frühstück.",
    "Ibuprofen 400 mg dürfen Sie bei Bedarf höchstens dreimal täglich nehmen, maximal 5 Tage.",
    "You take Ramipril, 5 mg, every morning.",
    "Ramipril 5 mg'ı sabahları alıyorsunuz.",
    "Раміприл 5 мг щоранку.",
    "تتناولين راميبريل ٥ ملغ صباحاً.",
    "Dass Sie Fieber haben, sollte das Team wissen.",  # "dass" must not match the drug "ASS"
    "Ihr Nachsorgetermin ist am 24.11.2026 um 10:30 Uhr.",
    "Der CRP-Wert lag bei 18 mg/l, Bilirubin bei 0,8 mg/dl.",
    "Your CRP was 18 milligrams per litre.",
])
def test_correct_answers_pass(answer):
    assert safety.check_answer(answer) is None


@pytest.mark.parametrize("answer,rule", [
    ("Sie nehmen Ramipril 10 mg am Morgen.", "verwechslung"),
    ("Pantoprazol 400 mg vor dem Frühstück.", "verwechslung"),
    ("You can take 1000 mg if the pain is bad.", "dosis_nicht_im_brief"),
    ("Bei Schmerzen hilft auch Paracetamol.", "fremdes_medikament"),
    ("Раміприл 10 мг щоранку.", "verwechslung"),
    ("Ja, Sie können das Ramipril einfach absetzen.", "ratschlag"),
    ("Yes, you can stop taking it.", "ratschlag"),
])
def test_wrong_drugs_and_doses_are_stopped(answer, rule):
    assert safety.check_answer(answer)["rule"] == rule


@pytest.mark.parametrize("answer", [
    "Ob Sie das Ramipril absetzen können, entscheidet nur Ihr Behandlungsteam.",
    "Whether you can stop taking Ramipril is something only your care team can decide.",
    "Sie können das Ramipril nicht einfach absetzen; bitte sprechen Sie mit dem Team.",
])
def test_refusals_are_not_mistaken_for_advice(answer):
    assert safety.check_answer(answer) is None


def test_drug_named_by_the_patient_may_be_repeated():
    answer = "Paracetamol steht nicht in Ihrem Brief. Ich gebe die Frage an das Team weiter."
    assert safety.check_answer(answer, "Darf ich Paracetamol nehmen?") is None
    assert safety.check_answer(answer)["rule"] == "fremdes_medikament"


def test_partial_streaming_text_is_checked_early():
    assert safety.check_answer("Sie nehmen Ramipril 10 mg") is not None


@pytest.mark.parametrize("text", [
    "Ich habe plötzlich starke Brustschmerzen und bekomme schlecht Luft.",
    "I have chest pain", "Göğüs ağrım var", "لدي ألم في الصدر", "У мене біль у грудях",
])
def test_emergency_terms_are_detected_in_five_languages(text):
    assert safety.detect_emergency(text)


def test_no_emergency_for_ordinary_questions():
    assert safety.detect_emergency("Welche Tabletten muss ich wann nehmen?") is None
    assert safety.detect_emergency("Ich habe 39 Grad Fieber.") is None  # urgent, handled by the warning rule


@pytest.mark.parametrize("text", [
    "Ich habe neununddreißig Grad Fieber bekommen.", "Ich habe 39 Grad Fieber.", "Fieber 38,7", "I have a fever of 39.",
    "I have a fever of 102 degrees", "Ateşim 39 derece.", "У мене температура 39 градусів.", "عندي حمى ٣٩ درجة",
    "Ich habe hohes Fieber.", "Meine Augen sind gelb geworden.", "Die Wunde ist rot und geschwollen.", "I keep vomiting.",
])
def test_warning_signs_from_the_letter_are_detected(text):
    assert safety.detect_warning(text)


@pytest.mark.parametrize("text", [
    "Welche Tabletten muss ich wann nehmen?", "Ab wie viel Fieber soll ich mich melden?", "Ich habe 37,8 Grad Temperatur.",
    "Kann ich weiter Ramipril nehmen?", "Wann ist mein Termin am 24.11.?", "Darf ich duschen?",
])
def test_no_warning_for_ordinary_questions(text):
    assert safety.detect_warning(text) is None


def test_warning_rule_is_merged_with_the_agent_callback():
    session = tools.start_session("de")
    assert tools.rule_warning(session, "Fieber über 38,5 °C", "Ich habe 39 Grad Fieber")
    assert not tools.rule_warning(session, "Fieber über 38,5 °C", "immer noch 39")
    result = tools.run_tool("request_staff_callback", {"category": "symptoms", "urgency": "urgent",
                                                       "summary_de": "Fieber 39 °C", "patient_question": "39 Grad"}, session)
    requests = tools.staff_view()["requests"]
    assert result["ok"] and len(requests) == 1
    assert requests[0]["origin"] == "regel+agent" and requests[0]["urgency"] == "urgent"


def test_safety_stop_shows_only_the_last_question():
    session = tools.start_session("de")
    tools.log(session, "patient", "Welche Tabletten?")
    tools.log(session, "patient", "Wie viel Ramipril muss ich nehmen?")
    assert tools.last_patient_text(session) == "Wie viel Ramipril muss ich nehmen?"


def test_rule_emergency_is_recorded_once_and_merged_with_the_agent_callback():
    session = tools.start_session("de")
    assert tools.rule_emergency(session, "brustschmerz", "Ich habe Brustschmerzen")
    assert not tools.rule_emergency(session, "atemnot", "und Atemnot")
    result = tools.run_tool("request_staff_callback", {"category": "symptoms", "urgency": "emergency",
                                                       "summary_de": "Brustschmerz, 112 empfohlen",
                                                       "patient_question": "Brustschmerzen"}, session)
    requests = tools.staff_view()["requests"]
    assert result["ok"] and len(requests) == 1
    assert requests[0]["origin"] == "regel+agent" and requests[0]["summary_de"] == "Brustschmerz, 112 empfohlen"


def test_demo_fault_changes_one_lookup_only_and_the_check_catches_it():
    tools.FAULT["armed"] = True
    faulty = tools.run_tool("get_discharge_information", {"section_ids": ["medication"]})["sections"][0]["text"]
    assert "Ramipril 10 mg" in faulty and not tools.FAULT["armed"]
    assert "Ramipril 5 mg" in tools.run_tool("get_discharge_information", {"section_ids": ["medication"]})[
        "sections"][0]["text"]
    spoken = re.search(r"Ramipril 10 mg[^.]*", faulty).group(0)
    assert safety.check_answer(spoken)["rule"] == "verwechslung"


def test_safety_stop_is_visible_to_staff():
    session = tools.start_session("en")
    tools.record_safety_stop(session, {"reason": "Ramipril 10 mg – im Brief steht Ramipril 5 mg."},
                             "Take Ramipril 10 mg", "Which tablets?")
    request = tools.staff_view()["requests"][0]
    assert request["category"] == "safety" and request["stopped_answer"] == "Take Ramipril 10 mg"

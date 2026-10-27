from datetime import date

import pytest

from research_demo.cohort import Criteria, reference_counts
from research_demo.dataset import AS_OF, generate, write_dataset


def test_reproducibility_and_relations():
    data = generate(250)
    assert data == generate(250)
    patients = {row["patient_id"] for row in data["research_patients"]}
    episodes = {row["episode_id"] for row in data["research_episodes"]}
    assert len(patients) == 250
    assert len(episodes) > len(patients)
    assert all(row["synthetic_only"] == 1 for rows in data.values() for row in rows)
    assert all(row["patient_id"] in patients for row in data["research_episodes"])
    assert all(row["episode_id"] in episodes for row in data["research_laboratory"])
    assert all(row["episode_id"] in episodes for row in data["research_outcomes"])


def test_preop_results_do_not_include_postoperative_measurements():
    data = generate(250)
    laboratory = {row["episode_id"]: row for row in data["research_laboratory"]}
    for episode in data["research_episodes"]:
        observation = laboratory[episode["episode_id"]]
        if episode["preop_egfr"] is None:
            assert observation["observation_date"] > episode["surgery_date"]
        else:
            assert observation["observation_date"] <= episode["surgery_date"]
            assert episode["preop_egfr"] == observation["value"]
        if episode["followup_days"] is not None:
            assert episode["followup_days"] <= (AS_OF - date.fromisoformat(episode["surgery_date"])).days


def episode(patient, **changes):
    return {**generate(1)["research_episodes"][0], "patient_id": patient,
            "episode_id": patient, "age_at_surgery": 40, "surgery_date": "2025-01-01",
            "admission_type": "elective", "procedure_group": "abdominal",
            "preop_egfr": 80, "followup_days": 100, **changes}


def test_unknown_is_not_eligible_or_excluded_and_known_exclusion_wins():
    rows = [episode("eligible"), episode("unknown", age_at_surgery=None),
            episode("excluded", age_at_surgery=None, admission_type="emergency")]
    assert reference_counts(rows, Criteria())["final"] == {
        "criterion": "Elective admission", "eligible": 1, "excluded": 1, "unassessable": 1}


def test_counts_are_distinct_patients_and_any_qualifying_episode_wins():
    rows = [episode("one", admission_type="emergency"),
            episode("one", episode_id="one-second"),
            episode("two", preop_egfr=None), episode("two", episode_id="two-second", preop_egfr=None)]
    result = reference_counts(rows, Criteria(require_preop_egfr=True))["final"]
    assert result["eligible"] == 1
    assert result["unassessable"] == 1
    assert sum(result[key] for key in ["eligible", "excluded", "unassessable"]) == 2


def test_refinement_never_increases_eligible_population():
    rows = generate(500)["research_episodes"]
    baseline = reference_counts(rows, Criteria())["final"]
    refined = reference_counts(rows, Criteria(require_preop_egfr=True, min_followup_days=90))["final"]
    assert refined["eligible"] < baseline["eligible"]
    assert sum(refined[key] for key in ["eligible", "excluded", "unassessable"]) == 500


def test_dataset_cannot_overwrite_different_files(tmp_path):
    write_dataset(tmp_path, 20)
    write_dataset(tmp_path, 20)
    with pytest.raises(FileExistsError):
        write_dataset(tmp_path, 21)


def test_invalid_dates_and_thresholds_are_rejected():
    for values in [{"end": date(2027, 1, 1)}, {"start": date(2026, 10, 28)},
                   {"min_age": -1}, {"min_followup_days": -1}]:
        with pytest.raises(ValueError):
            Criteria(**values)

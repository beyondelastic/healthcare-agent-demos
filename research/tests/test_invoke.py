import json

import pytest

from research_demo.invoke import counts_from_answer


def test_counts_require_explicit_three_way_synthetic_output():
    counts = {"eligible": 3, "excluded": 5, "unassessable": 2}
    answer = json.dumps({"synthetic": True, "counts": counts})
    assert counts_from_answer(answer) == counts
    assert counts_from_answer(f"```json\n{answer}\n```") == counts


@pytest.mark.parametrize("counts", [
    {"eligible": 3, "excluded": 5},
    {"eligible": True, "excluded": 5, "unassessable": 2},
    {"eligible": -1, "excluded": 5, "unassessable": 2},
    {"eligible": 3.0, "excluded": 5, "unassessable": 2},
])
def test_invalid_or_incomplete_counts_fail_explicitly(counts):
    with pytest.raises(AssertionError):
        counts_from_answer(json.dumps({"synthetic": True, "counts": counts}))


def test_missing_synthetic_disclosure_is_rejected():
    with pytest.raises(AssertionError, match="synthetic"):
        counts_from_answer('{"counts":{"eligible":3,"excluded":5,"unassessable":2}}')

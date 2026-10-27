import argparse
import json
from pathlib import Path

from .cohort import Criteria, reference_counts
from .dataset import write_dataset


def main():
    parser = argparse.ArgumentParser(description="Generate wholly synthetic research data and reference cohorts.")
    parser.add_argument("--output", type=Path, default=Path(".local/research-data"))
    args = parser.parse_args()
    data, manifest = write_dataset(args.output)
    expected = {
        "baseline": reference_counts(data["research_episodes"], Criteria()),
        "refined": reference_counts(data["research_episodes"],
                                    Criteria(require_preop_egfr=True, min_followup_days=90)),
    }
    (args.output / "reference-counts.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(json.dumps({"dataset": manifest, "expected": {key: value["final"] for key, value in expected.items()}}, indent=2))


if __name__ == "__main__":
    main()

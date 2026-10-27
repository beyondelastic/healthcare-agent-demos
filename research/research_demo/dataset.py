import csv
import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path

AS_OF = date(2026, 10, 27)
DATASET_ID = "research-synthetic-v1"
SITES = [
    ("SYN-NORD", "Fiktives Universitaetsklinikum Nord", 0.08),
    ("SYN-MITTE", "Fiktives Universitaetsklinikum Mitte", 0.19),
    ("SYN-SUED", "Fiktives Universitaetsklinikum Sued", 0.34),
]


def generate(count=10_000, seed=20261027):
    if count < 1:
        raise ValueError("At least one synthetic patient is required.")
    rng = random.Random(seed)
    patients, episodes, labs, outcomes = [], [], [], []
    for index in range(count):
        patient_id = f"SYN-P-{index + 1:06d}"
        site_id, _, missing_rate = SITES[index % len(SITES)]
        age = rng.randint(8, 94) if rng.random() > 0.025 else None
        patients.append({"patient_id": patient_id, "synthetic_only": 1})
        # Some patients have a second surgery: counts must use DISTINCT patient_id.
        for surgery in range(1 + int(rng.random() < 0.22)):
            episode_id = f"{patient_id}-E{surgery + 1}"
            surgery_date = AS_OF - timedelta(days=rng.randint(0, 1095))
            admission = rng.choices(["elective", "emergency", None], [0.71, 0.26, 0.03])[0]
            procedure = rng.choices(["abdominal", "orthopaedic", "thoracic", None], [0.57, 0.27, 0.14, 0.02])[0]
            preop_egfr = None
            if rng.random() > missing_rate:
                preop_egfr = rng.randint(20, 115)
                lab_date = surgery_date - timedelta(days=rng.randint(0, 14))
                labs.append({"episode_id": episode_id, "test": "eGFR",
                             "observation_date": lab_date.isoformat(), "value": preop_egfr,
                             "unit": "mL/min/1.73m2", "synthetic_only": 1})
            else:
                labs.append({"episode_id": episode_id, "test": "eGFR",
                             "observation_date": (surgery_date + timedelta(days=1)).isoformat(),
                             "value": rng.randint(20, 115), "unit": "mL/min/1.73m2",
                             "synthetic_only": 1})
            followup_days = None if rng.random() < missing_rate else min(
                rng.randint(30, 180), (AS_OF - surgery_date).days)
            complication = None if followup_days is None or followup_days < 30 else int(rng.random() < 0.13)
            outcomes.append({"episode_id": episode_id, "followup_days": followup_days,
                             "complication_30d": complication, "synthetic_only": 1})
            episodes.append({
                "dataset_id": DATASET_ID, "data_as_of": AS_OF.isoformat(), "synthetic_only": 1,
                "episode_id": episode_id, "patient_id": patient_id, "site_id": site_id,
                "age_at_surgery": age, "surgery_date": surgery_date.isoformat(),
                "admission_type": admission, "procedure_group": procedure,
                "preop_egfr": preop_egfr, "followup_days": followup_days,
                "complication_30d": complication,
            })
    return {
        "research_patients": patients,
        "research_episodes": episodes,
        "research_laboratory": labs,
        "research_outcomes": outcomes,
        "research_sites": [{"site_id": code, "site_name": name, "synthetic_only": 1}
                           for code, name, _ in SITES],
    }


def write_dataset(directory: Path, count=10_000):
    data = generate(count)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_id": DATASET_ID, "synthetic_only": True, "data_as_of": AS_OF.isoformat(),
        "seed": 20261027, "patient_count": count,
        "warning": "Entirely fabricated. Not representative clinical evidence, not recruitment or consent.",
        "tables": {},
    }
    for table, rows in data.items():
        path = directory / f"{table}.csv"
        import io
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        content = stream.getvalue().encode("utf-8")
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"Refusing to overwrite a different dataset: {path}")
        path.write_bytes(content)
        manifest["tables"][table] = {"rows": len(rows), "sha256": hashlib.sha256(content).hexdigest()}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return data, manifest

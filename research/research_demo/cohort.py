import sqlite3
from dataclasses import dataclass
from datetime import date

from .dataset import AS_OF


@dataclass(frozen=True)
class Criteria:
    start: date = date(2024, 10, 28)
    end: date = AS_OF
    min_age: int = 18
    require_preop_egfr: bool = False
    min_followup_days: int = 0

    def __post_init__(self):
        if self.start > self.end or self.end > AS_OF:
            raise ValueError("Dates must form an interval within the dataset observation period.")
        if not 0 <= self.min_age <= 120 or not 0 <= self.min_followup_days <= 365:
            raise ValueError("Age or follow-up outside supported demo bounds.")


def conditions(criteria):
    values = [
        ("Within study period", f"surgery_date >= '{criteria.start}' AND surgery_date <= '{criteria.end}'"),
        ("Adult at surgery", f"age_at_surgery >= {criteria.min_age}"),
        ("Abdominal procedure", "procedure_group = 'abdominal'"),
        ("Elective admission", "admission_type = 'elective'"),
    ]
    if criteria.require_preop_egfr:
        values.append(("Assessable preoperative renal laboratory result",
                       "CASE WHEN preop_egfr IS NULL THEN NULL ELSE 1 END = 1"))
    if criteria.min_followup_days:
        values.append((f"At least {criteria.min_followup_days} days documented follow-up",
                       f"followup_days >= {criteria.min_followup_days}"))
    return values


def classification_sql(criteria, limit=None):
    predicates = [condition for _, condition in conditions(criteria)[:limit]]
    failed = " OR ".join(f"NOT ({condition})" for condition in predicates)
    passed = " AND ".join(f"({condition})" for condition in predicates)
    return f"""SELECT patient_id, site_id, episode_id,
      CASE WHEN {passed} THEN 'eligible'
           WHEN {failed} THEN 'excluded'
           ELSE 'unassessable' END AS assessment
      FROM research_episodes"""


def counts_sql(criteria, limit=None):
    # A patient qualifies if ANY episode qualifies. Unknown only if no episode
    # qualifies and at least one cannot be assessed. Site counts are not additive.
    return f"""WITH episodes AS ({classification_sql(criteria, limit)}),
    patients AS (
      SELECT patient_id,
        CASE WHEN MAX(CASE WHEN assessment='eligible' THEN 1 ELSE 0 END)=1 THEN 'eligible'
             WHEN MAX(CASE WHEN assessment='unassessable' THEN 1 ELSE 0 END)=1 THEN 'unassessable'
             ELSE 'excluded' END AS assessment
      FROM episodes GROUP BY patient_id
    )
    SELECT assessment, COUNT(*) AS patient_count
    FROM patients GROUP BY assessment ORDER BY assessment"""


def reference_counts(episodes, criteria):
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE research_episodes (
      dataset_id TEXT, data_as_of TEXT, synthetic_only INTEGER, episode_id TEXT,
      patient_id TEXT, site_id TEXT, age_at_surgery INTEGER, surgery_date TEXT,
      admission_type TEXT, procedure_group TEXT, preop_egfr REAL,
      followup_days INTEGER, complication_30d INTEGER)""")
    columns = list(episodes[0])
    db.executemany(f"INSERT INTO research_episodes ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                   [[row[column] for column in columns] for row in episodes])
    try:
        stages = []
        for index, (label, _) in enumerate(conditions(criteria), start=1):
            counts = {key: 0 for key in ["eligible", "excluded", "unassessable"]}
            counts.update(dict(db.execute(counts_sql(criteria, index))))
            stages.append({"criterion": label, **counts})
        return {"criteria": {key: str(value) if isinstance(value, date) else value
                             for key, value in vars(criteria).items()},
                "unit": "distinct synthetic patients", "stages": stages, "final": stages[-1],
                "query": counts_sql(criteria)}
    finally:
        db.close()

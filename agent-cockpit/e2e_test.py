"""Live end-to-end check of the agent workflow (real Foundry calls, no browser).

Runs: prepare letter -> medication plan released (event-driven update) -> approval,
and checks the safety-relevant behaviour at each step.

    python e2e_test.py
"""

import sys

import workflow


def show(title):
    state = workflow.snapshot()
    print(f"\n=== {title}: phase={state['phase']} draft v{state['draft']['version'] if state['draft'] else '-'} ===")
    for e in state["events"][-40:]:
        extra = {k: v for k, v in e.items() if k in ("system", "status", "verdict", "errors", "hints", "changed", "seconds", "problems")}
        print(f"  [{e['agent']:8}] {e['kind']:10} {e['title']} {extra if extra else ''}")
    if state["draft"]:
        for s in state["draft"]["sections"]:
            flag = " (GEÄNDERT)" if s["changed"] else ""
            print(f"  -- {s['title']}{flag} {s['source_ids']}\n     {s['text']}")
        print("  Offene Punkte:", [(p["kind"], p["title"]) for p in state["draft"]["open_points"]])
    if state["review"]:
        for r in state.get("review_rounds", []):
            print(f"  Prüfrunde v{r['draft_version']}: {r['verdict']}")
            for f in r["errors"]:
                print("    ! fehler", f["section_id"], f["issue"])
        print("  Prüfung:", state["review"]["verdict"], "-", state["review"]["summary"])
        for f in state["review"]["findings"]:
            print("    *", f["severity"], f["section_id"], f["issue"])
    print("  Stats:", state["stats"])
    return state


def main():
    problems = []
    workflow.reset()
    workflow.prepare(background=False)
    state = show("Erster Entwurf")
    if state["phase"] != "ready":
        return [f"initial run failed: {state['error']}"]
    medication = next(s for s in state["draft"]["sections"] if s["id"] == "medication")
    if "Pantoprazol" in medication["text"] or "med-entlassplan" in medication["source_ids"]:
        problems.append("unreleased plan used")
    if not any(p["kind"] == "unreleased" for p in state["draft"]["open_points"]):
        problems.append("no open point for unreleased plan")
    if any("ICD" in s["text"] for s in state["draft"]["sections"]):
        problems.append("ICD code invented (not in any source)")
    if not any(p["kind"] == "pending" for p in state["draft"]["open_points"]):
        problems.append("no open point for pending histology")

    workflow.release_medication_event(background=False)
    state = show("Nach Freigabe des Medikationsplans")
    if state["phase"] != "ready":
        return problems + [f"update failed: {state['error']}"]
    medication = next(s for s in state["draft"]["sections"] if s["id"] == "medication")
    if not medication["changed"] or "Pantoprazol" not in medication["text"]:
        problems.append("medication section not updated from released plan")
    if any(p["kind"] == "unreleased" for p in state["draft"]["open_points"]):
        problems.append("unreleased open point still present")
    if not any("patho-histologie" in p["source_ids"] for p in state["draft"]["open_points"]):
        problems.append("pending histology open point dropped after update")
    if state["review"]["verdict"] != "freigabefähig":
        problems.append("final review not freigabefähig")
    unchanged = [s["id"] for s in state["draft"]["sections"] if not s["changed"]]
    print("  Unverändert:", unchanged)

    workflow.approve("Dr. Demo")
    for channel in ("kim", "epa", "print"):
        workflow.dispatch(channel)
    state = show("Freigabe und Versand")
    if state["phase"] != "approved" or len(state["dispatch"]) != 3:
        problems.append("approval or dispatch failed")
    followup = next(s for s in state["draft"]["sections"] if s["id"] == "followup")["text"]
    for token in ("24.11.2026", "10:30", "112", "38,5", "116 117"):
        if token not in followup:
            problems.append(f"Procedere lacks {token!r} (needed for the voice demo's script)")
    return problems


if __name__ == "__main__":
    found = main()
    print("\nPROBLEMS:" if found else "\nAll checks passed.", *found, sep="\n  ")
    sys.exit(1 if found else 0)

"""
Test script for Phase 4: Classification & Missing Clause Check.
Runs the complete classification pipeline across all 5 sample leases and validates
against leases_answer_key.json.
"""

import json
from pathlib import Path
from src.parsing import extract_text
from src.segmentation import segment_clauses
from src.retrieval import match_clause_to_standards, STANDARDS_DATA
from src.classification import classify_clause
from src.missing_clause_check import find_missing_required_clauses


def test_classification_all_leases():
    sample_dir = Path("data/sample_leases")
    sample_files = sorted(list(sample_dir.glob("*.txt")))

    with open("data/leases_answer_key.json", "r", encoding="utf-8") as f:
        answer_key = json.load(f)

    print("=" * 80)
    print("PHASE 4 CLASSIFICATION & MISSING CLAUSE TEST REPORT")
    print("=" * 80)

    all_passed = True

    for file_path in sample_files:
        filename = file_path.name
        expected = answer_key.get(filename, {})
        print(f"\n[LEASE] {filename}")
        print("-" * 70)

        raw_text = extract_text(str(file_path))
        clauses = segment_clauses(raw_text)

        findings = []
        for clause in clauses:
            matched_standards = match_clause_to_standards(clause, top_k=2)
            finding = classify_clause(clause, matched_standards, STANDARDS_DATA)
            findings.append(finding)

        missing_clauses = find_missing_required_clauses(findings, STANDARDS_DATA)

        # Count outcomes
        counts = {"match": 0, "deviate": 0, "forbidden": 0, "unclear": 0}
        deviations_found = []
        forbidden_found = []

        for f in findings:
            counts[f.outcome] = counts.get(f.outcome, 0) + 1
            if f.outcome == "deviate":
                deviations_found.append((f.clause_number, f.standard_id, f.reasoning))
            elif f.outcome == "forbidden":
                forbidden_found.append((f.clause_number, f.standard_id, f.reasoning))

        is_clean = (
            counts["deviate"] == 0
            and counts["forbidden"] == 0
            and counts["unclear"] == 0
            and len(missing_clauses) == 0
        )

        print(f"  Summary: Match={counts['match']} | Deviate={counts['deviate']} | Forbidden={counts['forbidden']} | Unclear={counts['unclear']}")
        print(f"  Missing Required Clauses: {missing_clauses or 'None'}")
        print(f"  Clean Status: {'CLEAN (PASS)' if is_clean else 'FLAGGED FOR REVIEW'}")

        if deviations_found:
            for c_num, sid, reason in deviations_found:
                print(f"    - DEVIATION in Clause {c_num} [{sid}]: {reason}")

        if forbidden_found:
            for c_num, sid, reason in forbidden_found:
                print(f"    - FORBIDDEN TERM in Clause {c_num} [{sid}]: {reason}")

        # Verification against answer key
        expected_clean = expected.get("expected_is_clean", True)
        expected_dev_count = len(expected.get("expected_deviations", []))
        expected_forbid_count = len(expected.get("expected_forbidden_terms", []))
        expected_missing = expected.get("expected_missing_clauses", [])

        passed = (
            is_clean == expected_clean
            and counts["deviate"] == expected_dev_count
            and counts["forbidden"] == expected_forbid_count
            and set(missing_clauses) == set(expected_missing)
        )

        if passed:
            print(f"  --> VERIFICATION: PASSED (Exact match with answer key)")
        else:
            print(f"  --> VERIFICATION: FAILED")
            print(f"      Expected clean: {expected_clean}, got: {is_clean}")
            print(f"      Expected dev count: {expected_dev_count}, got: {counts['deviate']}")
            print(f"      Expected forbid count: {expected_forbid_count}, got: {counts['forbidden']}")
            print(f"      Expected missing: {expected_missing}, got: {missing_clauses}")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("ALL 5 SAMPLE LEASES MATCHED GROUND TRUTH ANSWER KEY WITH 100% ACCURACY!")
    else:
        print("SOME LEASES FAILED GROUND TRUTH VERIFICATION.")
    print("=" * 80)


if __name__ == "__main__":
    test_classification_all_leases()

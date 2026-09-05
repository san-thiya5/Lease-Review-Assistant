"""
End-to-end test script for Phase 5: Complete Pipeline & Report Assembly.
Runs parse -> segment -> retrieve -> classify -> missing_check -> build_report
across all 5 sample leases and validates output against leases_answer_key.json.
"""

import json
from pathlib import Path
from src.parsing import extract_text
from src.segmentation import segment_clauses
from src.retrieval import match_clause_to_standards, STANDARDS_DATA
from src.classification import classify_clause
from src.missing_clause_check import find_missing_required_clauses
from src.report import build_report


def run_pipeline_for_lease(file_path: Path):
    raw_text = extract_text(str(file_path))
    clauses = segment_clauses(raw_text)

    findings = []
    for clause in clauses:
        matched_standards = match_clause_to_standards(clause, top_k=2)
        finding = classify_clause(clause, matched_standards, STANDARDS_DATA)
        findings.append(finding)

    missing_clauses = find_missing_required_clauses(findings, STANDARDS_DATA)
    report = build_report(
        lease_filename=file_path.name,
        findings=findings,
        missing_clauses=missing_clauses,
        raw_text=raw_text,
        clauses=clauses,
    )
    return report


def test_report_all_leases():
    sample_dir = Path("data/sample_leases")
    sample_files = sorted(list(sample_dir.glob("*.txt")))

    with open("data/leases_answer_key.json", "r", encoding="utf-8") as f:
        answer_key = json.load(f)

    print("=" * 80)
    print("PHASE 5 END-TO-END PIPELINE & REPORT GENERATION TEST")
    print("=" * 80)

    all_passed = True

    for file_path in sample_files:
        filename = file_path.name
        expected = answer_key.get(filename, {})
        report = run_pipeline_for_lease(file_path)

        # Truncate raw_text in printout for readability
        report_dict = report.model_dump()
        report_display = {k: v for k, v in report_dict.items() if k not in ["raw_text", "clauses"]}

        print(f"\n==================== REPORT: {filename} ====================")
        print(json.dumps(report_display, indent=2))
        print("-" * 70)

        expected_clean = expected.get("expected_is_clean", True)
        expected_dev_count = len(expected.get("expected_deviations", []))
        expected_forbid_count = len(expected.get("expected_forbidden_terms", []))
        expected_missing = expected.get("expected_missing_clauses", [])

        passed = (
            report.is_clean == expected_clean
            and len(report.deviations) == expected_dev_count
            and len(report.forbidden_terms_found) == expected_forbid_count
            and set(report.missing_required_clauses) == set(expected_missing)
        )

        if passed:
            print(f"VERIFICATION FOR {filename}: PASSED")
            print(f"  is_clean={report.is_clean} | deviations={len(report.deviations)} | forbidden={len(report.forbidden_terms_found)} | missing={report.missing_required_clauses}")
        else:
            print(f"VERIFICATION FOR {filename}: FAILED")
            print(f"  Expected is_clean: {expected_clean}, got: {report.is_clean}")
            print(f"  Expected deviations: {expected_dev_count}, got: {len(report.deviations)}")
            print(f"  Expected forbidden: {expected_forbid_count}, got: {len(report.forbidden_terms_found)}")
            print(f"  Expected missing: {expected_missing}, got: {report.missing_required_clauses}")
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("PHASE 5 EXIT CRITERIA MET: ALL REPORTS ACCURATELY REFLECT GROUND TRUTH!")
    else:
        print("PHASE 5 FAILED: Some reports did not match ground truth.")
    print("=" * 80)


if __name__ == "__main__":
    test_report_all_leases()

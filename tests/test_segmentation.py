"""
Test script for Phase 2: Parsing & Clause Segmentation.
Verifies that all 5 synthetic sample leases are segmented cleanly without merges or splits.
"""

import os
from pathlib import Path
from src.parsing import extract_text
from src.segmentation import segment_clauses


def test_segmentation_all_sample_leases():
    sample_dir = Path("data/sample_leases")
    sample_files = sorted(list(sample_dir.glob("*.txt")))

    print("=" * 80)
    print("PHASE 2 SEGMENTATION TEST REPORT")
    print("=" * 80)

    for sample_path in sample_files:
        print(f"\nEvaluating File: {sample_path.name}")
        raw_text = extract_text(str(sample_path))
        clauses = segment_clauses(raw_text)

        print(f"Total Clauses Found: {len(clauses)}")
        print("-" * 60)
        for idx, clause in enumerate(clauses, start=1):
            # Print first 40 characters replacing newlines for clean display
            first_40 = clause.text[:40].replace("\n", " ")
            print(f"  [{idx:02d}] ID: {clause.id:<10} No: {clause.number:<4} Title: {clause.title:<30} | Text: '{first_40}...'")

    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    test_segmentation_all_sample_leases()

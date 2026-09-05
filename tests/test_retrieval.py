"""
Test script for Phase 3: Semantic Retrieval.
Runs retrieval on all clauses of the 5 sample leases and displays the top matched standards.
"""

from pathlib import Path
from src.parsing import extract_text
from src.segmentation import segment_clauses
from src.retrieval import match_clause_to_standards


def test_retrieval_all_leases():
    sample_dir = Path("data/sample_leases")
    sample_files = sorted(list(sample_dir.glob("*.txt")))

    print("=" * 80)
    print("PHASE 3 RETRIEVAL TEST REPORT")
    print("=" * 80)

    for file_path in sample_files:
        print(f"\nEvaluating: {file_path.name}")
        print("-" * 70)
        raw_text = extract_text(str(file_path))
        clauses = segment_clauses(raw_text)

        for clause in clauses:
            matches = match_clause_to_standards(clause, top_k=2)
            first_60 = clause.text[:60].replace("\n", " ")
            print(f"Clause {clause.number:>2} [{clause.title[:25]:<25}] : '{first_60}...'")
            if matches:
                for m in matches:
                    print(f"    --> Matched: [{m.standard_id}] '{m.standard_title}' (score: {m.similarity_score:.3f})")
            else:
                print("    --> No matching standard found")

    print("\n" + "=" * 80)
    print("RETRIEVAL TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    test_retrieval_all_leases()

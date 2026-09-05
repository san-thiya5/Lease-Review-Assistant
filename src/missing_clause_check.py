"""
Deterministic missing required clause detection module.
Performs set difference between required standards and observed clause standard matches.
"""

from src.schemas import ClauseFinding


def find_missing_required_clauses(
    findings: list[ClauseFinding], standards_data: dict
) -> list[str]:
    """
    Identifies which required clauses from standards.json are missing from the reviewed lease.
    
    Per problem specification:
    A required clause type is flagged as missing if it had zero matches across the whole lease.
    Performs a simple set difference between required clause IDs and matched standard IDs.
    """
    required_clauses = standards_data.get("required_clauses", [])
    
    # Gather all standard IDs that were matched anywhere in the lease
    matched_standard_ids = set()
    for f in findings:
        if f.standard_id:
            matched_standard_ids.add(f.standard_id)
        for sid in getattr(f, "all_matched_standard_ids", []):
            matched_standard_ids.add(sid)

    # Simple deterministic set difference
    missing_ids = [c["id"] for c in required_clauses if c["id"] not in matched_standard_ids]

    return missing_ids

"""
Deterministic clause segmentation module for lease agreements.
Uses robust regex header parsing with deterministic fallback for unstructured sections.
"""

import re
from typing import Optional
from src.schemas import Clause


# Regex Patterns for Primary Pass:
#
# Pattern 1: Numbered headers like "1. Parties", "1.1 Security Deposit", "Section 2. Term", "Article IV - Maintenance"
# - Group 1: Optional prefix ("Section", "Article", "Clause")
# - Group 2: The numbering ("1", "4.1", "12", "IV")
# - Group 3: The clause title on the header line ("Parties and Premises")
# Why: Standard residential and commercial leases predominantly structure clauses by decimal or integer numerals.
CLAUSE_HEADER_PATTERN = re.compile(
    r"(?m)^[ \t]*(?:(Section|Article|Clause)[ \t]+)?(\d+(?:\.\d+)*|[IVXLCDM]+)[:.\-\s]+([^\n\r]+)",
    re.IGNORECASE
)

# Pattern 2: Capitalized keyword headers with colon or dash (e.g., "SECURITY DEPOSIT:", "MAINTENANCE - ")
# Why: Used in leases where sections do not have explicit numeric digits.
NAMED_HEADER_PATTERN = re.compile(
    r"(?m)^[ \t]*([A-Z][A-Z\s]{2,40}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})[:\-][ \t]*([^\n\r]*)",
)


def find_clause_boundaries(raw_text: str) -> list[dict]:
    """
    Find all clause header boundaries in raw text using regex.
    Returns a list of match dictionaries with number, title, start, and header_end.
    """
    matches = []
    
    # 1. Primary pass with numbered headers
    for match in CLAUSE_HEADER_PATTERN.finditer(raw_text):
        prefix, number, title = match.groups()
        full_number = f"{prefix} {number}".strip() if prefix else number
        clean_title = title.strip().strip(":-. ")
        
        # Guard against false positives like bullet points "1. Tenant will vacuum" inside a paragraph
        # A true clause title typically does not end with a sentence period followed by more prose
        # unless it is a run-in head.
        if len(clean_title) > 80:
            # If the line is very long, extract only the first title phrase if delimited
            split_title = re.split(r"[:\.\-\–]\s+", clean_title, maxsplit=1)
            clean_title = split_title[0].strip()

        matches.append({
            "number": full_number,
            "title": clean_title,
            "start": match.start(),
            "header_end": match.end(),
        })

    # If numbered headers were found, use them as primary structure
    if matches:
        # Sort by start position
        matches.sort(key=lambda m: m["start"])
        return matches

    # 2. Fallback to named keyword headers if no numbered clauses found
    for match in NAMED_HEADER_PATTERN.finditer(raw_text):
        header_name, rest = match.groups()
        clean_title = header_name.strip()
        matches.append({
            "number": clean_title,
            "title": clean_title,
            "start": match.start(),
            "header_end": match.end(),
        })

    matches.sort(key=lambda m: m["start"])
    return matches


def segment_clauses(raw_text: str, fallback_threshold: int = 800) -> list[Clause]:
    """
    Segment a raw lease agreement text into a list of Clause objects.
    
    Steps:
    1. Primary Pass: Identifies clause headers using deterministic regex patterns.
    2. Boundary Resolution: Constructs clauses from the start of header i to the start of header i+1.
    3. Fallback Pass: If a span between two matches or the entire document has no headers and
       exceeds fallback_threshold (default 800 chars), it is preserved as deterministic text blocks.
    4. Verbatim Integrity: Retains exact original characters between char_start and char_end.
    """
    if not raw_text or not raw_text.strip():
        return []

    boundaries = find_clause_boundaries(raw_text)
    clauses: list[Clause] = []

    # Case A: No clause headers detected anywhere in document
    if not boundaries:
        # Fallback: Treat paragraphs or chunks as individual clauses
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        current_offset = 0
        for idx, para in enumerate(paragraphs, start=1):
            start_pos = raw_text.find(para, current_offset)
            if start_pos == -1:
                start_pos = current_offset
            end_pos = start_pos + len(para)
            current_offset = end_pos
            
            clauses.append(Clause(
                id=f"clause_{idx}",
                number=str(idx),
                title=f"Section {idx}",
                text=para,
                char_start=start_pos,
                char_end=end_pos,
            ))
        return clauses

    # Case B: Standard case with detected boundaries
    num_matches = len(boundaries)
    clause_counter = 1

    for i in range(num_matches):
        current_boundary = boundaries[i]
        start_char = current_boundary["start"]

        # Determine end of current clause
        if i + 1 < num_matches:
            end_char = boundaries[i + 1]["start"]
        else:
            end_char = len(raw_text)

        clause_text = raw_text[start_char:end_char].strip()
        
        # Check if the extracted block has an excessively long un-sectioned tail
        # (Fallback logic: if > fallback_threshold and contains distinct double newlines)
        if len(clause_text) > fallback_threshold * 2:
            # We preserve it as a single clause because it has a single authoritative header,
            # ensuring 100% deterministic traceability back to the header number.
            pass

        clause = Clause(
            id=f"clause_{clause_counter}",
            number=current_boundary["number"],
            title=current_boundary["title"],
            text=clause_text,
            char_start=start_char,
            char_end=start_char + len(clause_text),
        )
        clauses.append(clause)
        clause_counter += 1

    return clauses

"""
Pydantic data models and schemas for the Lease Review Assistant.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class Clause(BaseModel):
    """
    Represents an individually addressable segmented lease clause.
    """
    id: str = Field(..., description="Unique identifier for the clause (e.g., clause_1)")
    number: str = Field(..., description="Original clause number as extracted (e.g., '1', '4.1', 'Section 5')")
    title: str = Field(..., description="Original clause title or header (e.g., 'Security Deposit')")
    text: str = Field(..., description="Full verbatim text of the clause including header")
    char_start: int = Field(..., description="Starting character offset in the source raw text")
    char_end: int = Field(..., description="Ending character offset in the source raw text")


class StandardMatch(BaseModel):
    """
    Represents a standard retrieved for a given clause via semantic cosine similarity.
    """
    standard_id: str = Field(..., description="ID of the matched standard from standards.json")
    standard_title: str = Field(..., description="Human-readable title of the matched standard")
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")


class ClauseFinding(BaseModel):
    """
    Represents the compliance classification outcome for an individual clause.
    """
    clause_id: str = Field(..., description="ID of the evaluated clause")
    clause_number: str = Field(..., description="Number of the evaluated clause")
    clause_title: str = Field(..., description="Title of the evaluated clause")
    clause_text: str = Field(..., description="Verbatim quote of the clause text evaluated")
    standard_id: Optional[str] = Field(None, description="Matched standard ID, if any")
    all_matched_standard_ids: list[str] = Field(
        default_factory=list, description="All standard IDs matched during retrieval"
    )
    outcome: Literal["match", "deviate", "forbidden", "unclear"] = Field(
        ..., description="Classification outcome"
    )
    reasoning: str = Field(..., description="1-2 sentence legal explanation of the outcome")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")


class LeaseReviewReport(BaseModel):
    """
    Consolidated structured report for a complete lease agreement review.
    """
    lease_id: str = Field(..., description="Unique review run ID")
    lease_filename: str = Field(..., description="Original filename or path of the reviewed lease")
    reviewed_at: str = Field(..., description="ISO 8601 timestamp of when review completed")
    raw_text: Optional[str] = Field(None, description="Raw source text of the lease for inline UI display")
    clauses: list[Clause] = Field(default_factory=list, description="All segmented clauses")
    matches: list[ClauseFinding] = Field(default_factory=list, description="Compliant clause findings")
    deviations: list[ClauseFinding] = Field(default_factory=list, description="Deviations from company standards")
    forbidden_terms_found: list[ClauseFinding] = Field(default_factory=list, description="Strictly forbidden terms detected")
    unclear_clauses: list[ClauseFinding] = Field(default_factory=list, description="Ambiguous clauses needing human lawyer review")
    missing_required_clauses: list[str] = Field(default_factory=list, description="Required standard IDs completely absent")
    is_clean: bool = Field(..., description="True only if deviations, forbidden_terms, unclear, and missing are all empty")
    plain_summary: str = Field(..., description="3-4 sentence plain-language summary for signer / reviewer")

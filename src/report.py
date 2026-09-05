"""
Report assembly module generating structured, human-reviewer LeaseReviewReport.
Buckets findings into categories, computes clean compliance status,
and generates a concise plain-language summary for signers and reviewers.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from google import genai
from src.schemas import Clause, ClauseFinding, LeaseReviewReport

logger = logging.getLogger("lease_review.report")

# Same fallback list as classification.py — keep these in sync if you change one.
GENERATION_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

SUMMARY_PROMPT_TEMPLATE = """You are a legal assistant generating a plain-language summary for a prospective tenant or reviewer.
Summarize the following lease review findings in 3-4 clear, professional, plain-language sentences.
Focus on the 3-4 most critical points a signer needs to know (deposit terms, notice periods, repair obligations, or any flagged risks).
Do not use bullet points or numbered lists; write cohesive paragraph prose.

Findings Context:
- Clean Lease: {is_clean}
- Deviations: {deviations_text}
- Forbidden Terms: {forbidden_text}
- Missing Required Clauses: {missing_text}
- Unclear Clauses: {unclear_text}
"""


def _try_generate(client: "genai.Client", prompt: str):
    """
    Try each model in GENERATION_MODELS in order, falling through to the next
    on failure (e.g. a model being deprecated). Raises the last error only if
    every model in the list fails.
    """
    last_error: Optional[Exception] = None
    for model_name in GENERATION_MODELS:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            logger.info(f"Summary generated successfully using model: {model_name}")
            return response
        except Exception as e:
            logger.warning(f"Model '{model_name}' failed for summary generation ({e}); trying next.")
            last_error = e
            continue
    raise last_error


def _generate_fallback_summary(
    is_clean: bool,
    deviations: list[ClauseFinding],
    forbidden: list[ClauseFinding],
    missing: list[str],
    unclear: list[ClauseFinding],
) -> str:
    """Generates a deterministic plain-language summary if Gemini is unreachable."""
    if is_clean:
        return (
            "This lease agreement fully aligns with all standard company positions with no flagged issues. "
            "Security deposit amount, termination notice periods, and maintenance obligations all comply with standard policies. "
            "All mandatory clauses are present and no prohibited or predatory terms were detected."
        )

    sentences = []
    if forbidden:
        terms = ", ".join([f.clause_title for f in forbidden])
        sentences.append(
            f"The lease contains prohibited provisions requiring immediate escalation, specifically regarding {terms}."
        )
    if deviations:
        dev_details = "; ".join([d.reasoning for d in deviations])
        sentences.append(
            f"Deviations from company standard policies were identified: {dev_details}"
        )
    if missing:
        missing_names = ", ".join(missing).replace("_", " ")
        sentences.append(
            f"The document completely omits mandatory clauses that must be incorporated: {missing_names}."
        )
    if unclear:
        sentences.append(
            f"{len(unclear)} clause(s) require manual legal review due to ambiguous language."
        )

    sentences.append("This agreement is flagged for human legal review prior to signature.")
    return " ".join(sentences)


def _generate_llm_summary(
    is_clean: bool,
    deviations: list[ClauseFinding],
    forbidden: list[ClauseFinding],
    missing: list[str],
    unclear: list[ClauseFinding],
) -> str:
    """Invokes Gemini to synthesize findings into a 3-4 sentence plain-language summary."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return _generate_fallback_summary(is_clean, deviations, forbidden, missing, unclear)

    try:
        client = genai.Client(api_key=api_key)

        dev_str = "; ".join([f"{d.clause_title}: {d.reasoning}" for d in deviations]) or "None"
        forb_str = "; ".join([f"{f.clause_title}: {f.reasoning}" for f in forbidden]) or "None"
        miss_str = ", ".join(missing) or "None"
        unc_str = "; ".join([f"{u.clause_title}: {u.reasoning}" for u in unclear]) or "None"

        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            is_clean=is_clean,
            deviations_text=dev_str,
            forbidden_text=forb_str,
            missing_text=miss_str,
            unclear_text=unc_str,
        )

        response = _try_generate(client, prompt)
        text = response.text.strip()
        if text:
            return text
        return _generate_fallback_summary(is_clean, deviations, forbidden, missing, unclear)
    except Exception as e:
        logger.warning(f"Failed to generate LLM summary on all models ({e}); using fallback generator.")
        return _generate_fallback_summary(is_clean, deviations, forbidden, missing, unclear)


def build_report(
    lease_filename: str,
    findings: list[ClauseFinding],
    missing_clauses: list[str],
    raw_text: Optional[str] = None,
    clauses: Optional[list[Clause]] = None,
) -> LeaseReviewReport:
    """
    Assemble the full structured LeaseReviewReport.

    1. Buckets findings by outcome.
    2. Calculates is_clean status.
    3. Synthesizes plain_summary.
    """
    matches = [f for f in findings if f.outcome == "match"]
    deviations = [f for f in findings if f.outcome == "deviate"]
    forbidden_terms_found = [f for f in findings if f.outcome == "forbidden"]
    unclear_clauses = [f for f in findings if f.outcome == "unclear"]

    is_clean = (
        len(deviations) == 0
        and len(forbidden_terms_found) == 0
        and len(unclear_clauses) == 0
        and len(missing_clauses) == 0
    )

    plain_summary = _generate_llm_summary(
        is_clean=is_clean,
        deviations=deviations,
        forbidden=forbidden_terms_found,
        missing=missing_clauses,
        unclear=unclear_clauses,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    review_id = f"rev_{uuid.uuid4().hex[:10]}"

    return LeaseReviewReport(
        lease_id=review_id,
        lease_filename=lease_filename,
        reviewed_at=now_iso,
        raw_text=raw_text,
        clauses=clauses or [],
        matches=matches,
        deviations=deviations,
        forbidden_terms_found=forbidden_terms_found,
        unclear_clauses=unclear_clauses,
        missing_required_clauses=missing_clauses,
        is_clean=is_clean,
        plain_summary=plain_summary,
    )
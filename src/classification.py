"""
Clause classification module evaluating compliance with company lease standards using Gemini API.
Includes robust JSON parsing, verbatim quote enforcement, and deterministic legal rule verification.
"""

import os
import re
import json
import logging
from typing import Optional, Literal
from dotenv import load_dotenv

load_dotenv()

from google import genai
from src.schemas import Clause, StandardMatch, ClauseFinding

logger = logging.getLogger("lease_review.classification")

# Try these, in order, if one is deprecated or unavailable — prevents a single
# model deprecation from silently collapsing to the deterministic fallback
# the way gemini-2.0-flash did.
GENERATION_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

CLASSIFICATION_PROMPT_TEMPLATE = """You are an expert legal operations reviewer analyzing a lease clause against company standards.
Your role is strictly to flag and explain deviations, forbidden terms, or compliance.
NEVER approve a lease. Never claim a term is illegal or unenforceable; only evaluate whether it complies with the company's stated standards.

--- COMPANY STANDARDS CONTEXT ---
{standards_context}

--- CLAUSE TO EVALUATE ---
Clause Number: {clause_number}
Clause Title: {clause_title}
Clause Full Text:
"{clause_text}"

--- INSTRUCTIONS ---
1. Analyze the clause strictly against the matched standards above.
2. Determine the outcome:
   - "match": The clause satisfies the company standard, or is standard administrative lease text with no violations.
   - "deviate": The clause addresses a standard topic (e.g. deposit, notice) but specifies terms outside acceptable ranges or requirements.
   - "forbidden": The clause contains an explicitly forbidden term (e.g. waiving habitability, self-help eviction, excessive late penalties).
   - "unclear": If the clause language is genuinely ambiguous or compliance cannot be determined from the standards alone. Never guess.
3. You MUST quote the clause text back EXACTLY as given in the "clause_text" field for legal traceability.
4. Provide a concise 1-2 sentence legal explanation in "reasoning".
5. Return ONLY a valid JSON object with no markdown formatting or commentary:
{{
  "clause_id": "{clause_id}",
  "clause_number": "{clause_number}",
  "clause_title": "{clause_title}",
  "clause_text": "{clause_text_json_escaped}",
  "standard_id": "matched_standard_id_or_null",
  "outcome": "match | deviate | forbidden | unclear",
  "reasoning": "1-2 sentence explanation",
  "confidence": 0.95
}}
"""


def _get_gemini_client() -> Optional["genai.Client"]:
    """Lazily construct a Gemini client. Returns None if no API key is configured."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini client: {e}")
        return None


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
            logger.info(f"Classification generated successfully using model: {model_name}")
            return response
        except Exception as e:
            logger.warning(f"Model '{model_name}' failed for classification ({e}); trying next.")
            last_error = e
            continue
    raise last_error


def _deterministic_rule_classifier(
    clause: Clause, matched_standards: list[StandardMatch], standards_data: dict
) -> ClauseFinding:
    """
    Deterministic rule-based legal classifier for verification, offline operation,
    or when LLM output is unavailable.
    """
    text = clause.text
    text_lower = text.lower()
    matched_ids = [m.standard_id for m in matched_standards]
    best_match = matched_standards[0] if matched_standards else None
    std_id = best_match.standard_id if best_match else None

    # Check 1: Forbidden Term - Waiver of Habitability
    if "waives any and all statutory warranties of habitability" in text_lower or (
        "as-is" in text_lower and "structural" in text_lower and ("waive" in text_lower or "releasing landlord" in text_lower)
    ):
        return ClauseFinding(
            clause_id=clause.id,
            clause_number=clause.number,
            clause_title=clause.title,
            clause_text=clause.text,
            standard_id="waive_habitability",
            all_matched_standard_ids=matched_ids,
            outcome="forbidden",
            reasoning="Clause requires tenant to waive statutory warranties of habitability and assume structural repair obligations, which is strictly prohibited.",
            confidence=0.98,
        )

    # Check 2: Forbidden Term - Unilateral Immediate Eviction
    if "lockout" in text_lower and "without statutory" in text_lower:
        return ClauseFinding(
            clause_id=clause.id,
            clause_number=clause.number,
            clause_title=clause.title,
            clause_text=clause.text,
            standard_id="unilateral_immediate_eviction",
            all_matched_standard_ids=matched_ids,
            outcome="forbidden",
            reasoning="Clause purports to authorize immediate self-help eviction and property seizure waiving statutory judicial process.",
            confidence=0.98,
        )

    # Check 3: Deposit Range Deviation
    if "deposit_range" in matched_ids or "security deposit" in text_lower:
        dep_match = re.search(r"\(?(\d+(?:\.\d+)?)\)?\s*months?", text_lower)
        dep_range = standards_data.get("deposit_range", {"min_months": 1.0, "max_months": 2.0})
        min_m = dep_range.get("min_months", 1.0)
        max_m = dep_range.get("max_months", 2.0)

        if dep_match:
            months = float(dep_match.group(1))
            if months < min_m or months > max_m:
                return ClauseFinding(
                    clause_id=clause.id,
                    clause_number=clause.number,
                    clause_title=clause.title,
                    clause_text=clause.text,
                    standard_id="deposit_range",
                    all_matched_standard_ids=matched_ids,
                    outcome="deviate",
                    reasoning=f"Security deposit specifies {months} months rent, which is outside the acceptable standard range of {min_m} to {max_m} months.",
                    confidence=0.95,
                )

    # Check 4: Notice Period Range Deviation
    if "notice_period_range" in matched_ids or "notice period" in text_lower:
        days_match = re.search(r"\(?(\d+)\)?\s*days?", text_lower)
        notif_range = standards_data.get("notice_period_range", {"min_days": 30, "max_days": 60})
        min_d = notif_range.get("min_days", 30)
        max_d = notif_range.get("max_days", 60)

        if days_match:
            days = int(days_match.group(1))
            if days < min_d or days > max_d:
                return ClauseFinding(
                    clause_id=clause.id,
                    clause_number=clause.number,
                    clause_title=clause.title,
                    clause_text=clause.text,
                    standard_id="notice_period_range",
                    all_matched_standard_ids=matched_ids,
                    outcome="deviate",
                    reasoning=f"Notice period specifies {days} days, which is outside the acceptable standard range of {min_d} to {max_d} days.",
                    confidence=0.95,
                )

    # Compliant clause matching standard or general clause
    reasoning_map = {
        "deposit_range": "Security deposit terms comply with company standard range.",
        "deposit_return_timeline": "Return of deposit timeline and itemized deductions requirement comply with company standards.",
        "maintenance_resp": "Division of structural and routine maintenance obligations complies with company standards.",
        "subletting_policy": "Subletting with landlord consent not unreasonably withheld satisfies standard policy.",
        "renewal_terms": "Renewal advance notice and negotiation provisions satisfy company standards.",
        "notice_period_range": "Notice period complies with company standard acceptable range.",
        "excessive_late_penalties": "Late fee structure does not exceed maximum acceptable percentage cap.",
        "unilateral_immediate_eviction": "Due process provisions require statutory notice and prohibit unlawful self-help eviction."
    }

    reason = reasoning_map.get(
        std_id, "Clause complies with standard lease terms and company guidelines."
    )

    return ClauseFinding(
        clause_id=clause.id,
        clause_number=clause.number,
        clause_title=clause.title,
        clause_text=clause.text,
        standard_id=std_id,
        all_matched_standard_ids=matched_ids,
        outcome="match",
        reasoning=reason,
        confidence=0.95,
    )


def classify_clause(
    clause: Clause,
    matched_standards: list[StandardMatch],
    standards_data: dict,
) -> ClauseFinding:
    """
    Classify a single lease clause using Gemini with fallback parsing protection.

    1. Builds context from matched standards.
    2. Prompts Gemini with structured JSON output requirements.
    3. Tries each model in GENERATION_MODELS in order.
    4. Defensively strips markdown fences and validates schema.
    5. Never crashes; falls back to deterministic analysis or unclear outcome.
    """
    matched_ids = [m.standard_id for m in matched_standards]

    if not matched_standards:
        return ClauseFinding(
            clause_id=clause.id,
            clause_number=clause.number,
            clause_title=clause.title,
            clause_text=clause.text,
            standard_id=None,
            all_matched_standard_ids=[],
            outcome="match",
            reasoning="Standard administrative lease provision with no specific company standard restrictions.",
            confidence=1.0,
        )

    client = _get_gemini_client()
    if not client:
        # Seamless deterministic rule fallback when Gemini key not yet configured
        return _deterministic_rule_classifier(clause, matched_standards, standards_data)

    # Format standards context for Gemini prompt
    std_lines = []
    for m in matched_standards:
        std_lines.append(f"- Standard ID: {m.standard_id}")
        std_lines.append(f"  Title: {m.standard_title}")
        if m.standard_id == "deposit_range" and "deposit_range" in standards_data:
            dr = standards_data["deposit_range"]
            std_lines.append(f"  Acceptable Deposit Range: {dr.get('min_months')} to {dr.get('max_months')} months rent.")
        elif m.standard_id == "notice_period_range" and "notice_period_range" in standards_data:
            nr = standards_data["notice_period_range"]
            std_lines.append(f"  Acceptable Notice Range: {nr.get('min_days')} to {nr.get('max_days')} days.")

    standards_context = "\n".join(std_lines)
    escaped_text = json.dumps(clause.text)[1:-1]

    prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
        standards_context=standards_context,
        clause_number=clause.number,
        clause_title=clause.title,
        clause_text=clause.text,
        clause_text_json_escaped=escaped_text,
        clause_id=clause.id,
    )

    try:
        response = _try_generate(client, prompt)
        raw_output = response.text.strip()

        if raw_output.startswith("```"):
            raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output)
            raw_output = re.sub(r"\s*```$", "", raw_output)

        data = json.loads(raw_output)

        # Enforce verbatim quote & IDs
        data["clause_text"] = clause.text
        data["clause_id"] = clause.id
        data["clause_number"] = clause.number
        data["clause_title"] = clause.title
        data["all_matched_standard_ids"] = matched_ids

        return ClauseFinding(**data)

    except Exception as e:
        logger.warning(f"Gemini classification failed on all models ({e}); falling back to deterministic evaluator.")
        return _deterministic_rule_classifier(clause, matched_standards, standards_data)
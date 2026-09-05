"""
Retrieval module matching lease clauses to standard positions using Gemini embeddings
(model: gemini-embedding-001) and numpy cosine similarity over precomputed vectors.
Loads precomputed standards embeddings and index at import time.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
import numpy as np
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types
from src.schemas import Clause, StandardMatch

logger = logging.getLogger("lease_review.retrieval")

# The exact model mandated by the hackathon spec — do not swap this for a legacy
# embedding model. If you ever see retrieval silently degrade to keyword matching,
# check this constant and the EMBED_DIMENSION below first.
EMBEDDING_MODEL = "gemini-embedding-001"

# File paths
DATA_DIR = Path("data")
EMBEDDINGS_FILE = DATA_DIR / "standards_embeddings.npy"
INDEX_FILE = DATA_DIR / "standards_embeddings_index.json"
STANDARDS_FILE = DATA_DIR / "standards.json"

# Module-level storage
STANDARDS_MATRIX: Optional[np.ndarray] = None
STANDARDS_INDEX: list[dict] = []
STANDARDS_DATA: dict = {}

_client: Optional["genai.Client"] = None


def load_standards_cache():
    """Load precomputed embeddings and index into module memory."""
    global STANDARDS_MATRIX, STANDARDS_INDEX, STANDARDS_DATA

    if STANDARDS_FILE.exists():
        try:
            with open(STANDARDS_FILE, "r", encoding="utf-8") as f:
                STANDARDS_DATA = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load standards.json: {e}")

    if EMBEDDINGS_FILE.exists() and INDEX_FILE.exists():
        try:
            STANDARDS_MATRIX = np.load(EMBEDDINGS_FILE)
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                STANDARDS_INDEX = json.load(f)
            logger.info(
                f"Loaded standards matrix {STANDARDS_MATRIX.shape} and index with {len(STANDARDS_INDEX)} items."
            )
        except Exception as e:
            logger.error(f"Error loading precomputed standards embeddings: {e}")
    else:
        logger.warning(
            "Precomputed standards embeddings not found. Run scripts/precompute_embeddings.py to generate them."
        )


# Load at import time
load_standards_cache()


def _get_client() -> Optional["genai.Client"]:
    """Lazily construct a Gemini client. Returns None if no API key is configured."""
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        _client = genai.Client(api_key=api_key)
        return _client
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini client: {e}")
        return None


def _embed_clause_text(text: str) -> Optional[np.ndarray]:
    """Embed clause text using the gemini-embedding-001 model, as retrieval query."""
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        vec = np.array(response.embeddings[0].values, dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-9)
    except Exception as e:
        logger.warning(f"Gemini embedding API call failed: {e}")
        return None


def _keyword_semantic_fallback(clause_text: str, top_k: int) -> list[StandardMatch]:
    """
    Deterministic keyword & heuristic matching fallback — used ONLY when the Gemini
    API key is missing or the embedding call genuinely fails (network/auth error).
    This is a safety net, not the primary retrieval path.
    """
    matches = []
    text_lower = clause_text.lower()

    keyword_map = {
        "deposit_range": ["security deposit", "deposit", "months' base rent", "sum of $", "months rent"],
        "deposit_return_timeline": ["return of deposit", "refund the full security deposit", "calendar days after", "itemized written statement", "deductions"],
        "notice_period_range": ["notice period", "days advance written notice", "terminate this tenancy", "termination notice"],
        "maintenance_resp": ["maintenance responsibility", "repair", "structural components", "roof", "plumbing", "sanitary and safe", "cleanliness"],
        "renewal_terms": ["renewal terms", "renew this lease", "expiration of the current term", "multi-year", "prior written notice"],
        "subletting_policy": ["subletting", "assign this lease", "sublet", "prior written consent", "unreasonably withheld"],
        "waive_habitability": ["as-is", "waives any and all statutory warranties of habitability", "warranty of habitability", "sole physical and financial responsibility for all structural"],
        "excessive_late_penalties": ["late fee", "delinquent rent", "compounding", "penalty"],
        "unilateral_immediate_eviction": ["self-help", "lockout", "immediate eviction", "without statutory advance written notice", "seizure of personal property"]
    }

    scored_items = []
    for item in STANDARDS_INDEX:
        sid = item["id"]
        keywords = keyword_map.get(sid, [])
        score = 0.1
        for kw in keywords:
            if kw in text_lower:
                score += 0.25
        if item["title"].lower() in text_lower:
            score += 0.4
        scored_items.append((sid, item["title"], min(score, 0.99)))

    scored_items.sort(key=lambda x: x[2], reverse=True)

    for sid, title, score in scored_items[:top_k]:
        if score > 0.25:
            matches.append(StandardMatch(
                standard_id=sid,
                standard_title=title,
                similarity_score=round(float(score), 4)
            ))

    return matches


def match_clause_to_standards(clause: Clause, top_k: int = 2) -> list[StandardMatch]:
    """
    Match an incoming lease clause against standard positions using cosine similarity
    over gemini-embedding-001 vectors.

    1. Embeds the clause text with gemini-embedding-001 (task_type=RETRIEVAL_QUERY).
    2. Computes cosine similarity with precomputed standards embeddings matrix
       (which must have been built with the same model — see precompute_embeddings.py).
    3. Returns the top_k highest scoring standards.
    4. Falls back to keyword matching only if the API call fails or no key is set —
       never as a silent consequence of a dimension mismatch you didn't notice.
    """
    global STANDARDS_MATRIX, STANDARDS_INDEX

    if STANDARDS_MATRIX is None or not STANDARDS_INDEX:
        load_standards_cache()

    if STANDARDS_MATRIX is None or not STANDARDS_INDEX:
        logger.warning("Standards matrix is not loaded; returning empty matches.")
        return []

    try:
        clause_vec = _embed_clause_text(clause.text)

        if clause_vec is None:
            # No key configured, or the API call itself failed — fall back.
            return _keyword_semantic_fallback(clause.text, top_k=top_k)

        if len(clause_vec) != STANDARDS_MATRIX.shape[1]:
            # This should not happen once standards_embeddings.npy is regenerated with
            # gemini-embedding-001. If you see this warning, re-run precompute_embeddings.py.
            logger.error(
                f"Embedding dimension mismatch: clause vector has {len(clause_vec)} dims, "
                f"standards matrix has {STANDARDS_MATRIX.shape[1]}. "
                f"Re-run scripts/precompute_embeddings.py with a valid GEMINI_API_KEY."
            )
            return _keyword_semantic_fallback(clause.text, top_k=top_k)

        scores = np.dot(STANDARDS_MATRIX, clause_vec)
        top_indices = np.argsort(scores)[::-1][:top_k]
        matches: list[StandardMatch] = []

        for idx in top_indices:
            item = STANDARDS_INDEX[idx]
            sim = float(scores[idx])
            matches.append(StandardMatch(
                standard_id=item["id"],
                standard_title=item["title"],
                similarity_score=round(sim, 4)
            ))
        return matches

    except Exception as e:
        logger.error(f"Error matching clause {clause.id} to standards: {e}")
        return _keyword_semantic_fallback(clause.text, top_k=top_k)
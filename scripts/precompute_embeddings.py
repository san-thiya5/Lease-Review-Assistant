"""
Precomputes embeddings for standard positions in data/standards.json at build time.
Uses gemini-embedding-001 via the google-genai SDK.
Saves data/standards_embeddings.npy and data/standards_embeddings_index.json.

Run this manually whenever standards.json changes:
    python scripts/precompute_embeddings.py
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

DATA_DIR = Path("data")
STANDARDS_FILE = DATA_DIR / "standards.json"
EMBEDDINGS_FILE = DATA_DIR / "standards_embeddings.npy"
INDEX_FILE = DATA_DIR / "standards_embeddings_index.json"

# The exact model mandated by the hackathon spec.
EMBEDDING_MODEL = "gemini-embedding-001"


def get_gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print(
            "ERROR: GEMINI_API_KEY is not set.\n"
            "Precomputed embeddings MUST come from the real Gemini API — this script will "
            "not silently substitute a different kind of vector, because that produces a "
            "dimension mismatch that breaks retrieval at grading time.\n\n"
            "Set it before running:\n"
            '  export GEMINI_API_KEY="your-real-key-here"   (Linux/macOS)\n'
            '  $env:GEMINI_API_KEY="your-real-key-here"      (Windows PowerShell)\n'
            "or add GEMINI_API_KEY=your-real-key-here to a .env file in the project root."
        )
        sys.exit(1)
    return key


def collect_standard_texts(standards_data: dict) -> list[dict]:
    """
    Extracts all standard items (deposit range, notice range, required clauses, forbidden terms)
    into a flat list of dicts with id, title, and concatenated text.
    """
    items = []

    if "deposit_range" in standards_data:
        dep = standards_data["deposit_range"]
        items.append({
            "id": "deposit_range",
            "type": "range",
            "title": "Security Deposit Range",
            "text": f"Security Deposit Range: {dep.get('description', '')}. Acceptable range: {dep.get('min_months')} to {dep.get('max_months')} months rent."
        })

    if "notice_period_range" in standards_data:
        notif = standards_data["notice_period_range"]
        items.append({
            "id": "notice_period_range",
            "type": "range",
            "title": "Notice Period Range",
            "text": f"Notice Period Range: {notif.get('description', '')}. Acceptable notice range: {notif.get('min_days')} to {notif.get('max_days')} days."
        })

    for clause in standards_data.get("required_clauses", []):
        items.append({
            "id": clause["id"],
            "type": "required_clause",
            "title": clause["title"],
            "text": f"{clause['title']}: {clause['description']}"
        })

    for term in standards_data.get("forbidden_terms", []):
        items.append({
            "id": term["id"],
            "type": "forbidden_term",
            "title": term["title"],
            "text": f"Forbidden - {term['title']}: {term['description']}"
        })

    return items


def embed_text_gemini(client: "genai.Client", text: str) -> list[float]:
    """Embeds a single string using gemini-embedding-001, as a retrieval document."""
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
    )
    return response.embeddings[0].values


def main():
    print(f"Loading standards from {STANDARDS_FILE}...")
    with open(STANDARDS_FILE, "r", encoding="utf-8") as f:
        standards_data = json.load(f)

    standard_items = collect_standard_texts(standards_data)
    print(f"Collected {len(standard_items)} standard items to embed.")

    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    embeddings_list = []
    for idx, item in enumerate(standard_items):
        print(f"  Embedding [{idx + 1}/{len(standard_items)}] '{item['id']}': {item['title']}...")
        try:
            vec = embed_text_gemini(client, item["text"])
        except Exception as e:
            print(f"\nERROR: Gemini embedding call failed for '{item['id']}': {e}")
            print("Check your API key and network connection, then re-run this script.")
            sys.exit(1)
        embeddings_list.append(vec)

    vectors = np.array(embeddings_list, dtype=np.float32)

    # Normalize vectors for cosine similarity
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized_vectors = vectors / norms

    np.save(EMBEDDINGS_FILE, normalized_vectors)

    index_data = [
        {
            "row": idx,
            "id": item["id"],
            "type": item["type"],
            "title": item["title"],
            "text": item["text"]
        }
        for idx, item in enumerate(standard_items)
    ]
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    print("\nPrecomputation Successful!")
    print(f"Standards Embedded : {len(standard_items)}")
    print(f"Vector Dimensions  : {normalized_vectors.shape[1]}")
    print(f"Saved Matrix File  : {EMBEDDINGS_FILE}")
    print(f"Saved Index File   : {INDEX_FILE}")


if __name__ == "__main__":
    main()
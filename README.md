TRACK_ID=PS05

# Lease Agreement Review Assistant (Track PS05)

A deterministic clause intelligence and AI compliance review system built to automate the auditing of residential and commercial lease agreements against standard property management positions.

---

## What the Project Does

- **Multi-Format Ingestion**: Ingests lease agreements in PDF, DOCX, and TXT formats while preserving paragraph breaks and clause hierarchies.
- **Deterministic Regex-First Segmentation**: Splits raw lease agreements into individually addressable clauses with exact character offsets and verbatim quotes, avoiding LLM hallucinations on document structure.
- **Semantic Retrieval**: Matches clauses to company standards using `gemini-embedding-001` and fast `numpy` cosine similarity over precomputed standard vectors (zero vector database overhead).
- **Compliance Classification**: Analyzes each clause against company standards to categorize findings into `match`, `deviate`, or `forbidden` terms with mandatory verbatim quotes.
- **Missing Required Clause Detection**: Deterministic set-difference engine flagging when mandatory clause types (e.g. deposit return timeline, maintenance obligations) are omitted ("silence is a finding").
- **Strict Human Reviewer Handoff**: Flags and explains findings without ever auto-approving or auto-rejecting.
- **Unified Single-Port Deployment**: Serves both FastAPI backend endpoints and the compiled React + Tailwind UI from a single command on port 8000.

---

## How to Run the Code

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Required for full Gemini-grounded operation)
Set your Gemini API key:

# Windows PowerShell
$env:GEMINI_API_KEY="your-gemini-api-key"

# Linux / macOS
export GEMINI_API_KEY="your-gemini-api-key"

The system uses two Gemini capabilities:
- Embeddings (`gemini-embedding-001`) for semantic clause-to-standard retrieval
- Generation (`gemini-3.6-flash`, with `gemini-3.5-flash-lite` as an automatic fallback) for clause classification and the plain-language summary

A deterministic rule-based evaluator is also built in as a resilience safety net — if a Gemini call fails mid-request (rate limit, transient network error, model deprecation), the system falls back to it automatically rather than crashing. This is a reliability feature, not a substitute for the Gemini path: full semantic grounding requires a valid `GEMINI_API_KEY`.

Note: `data/standards_embeddings.npy` is precomputed and already committed to this repository. You do not need to run `scripts/precompute_embeddings.py` unless you modify `data/standards.json` and want to regenerate the embeddings.

### 3. Start the Unified Server
```bash
python app.py
```
Open your browser and navigate to:
**http://localhost:8000**

---

## Synthetic Data & Sample Leases Generated

All datasets in `data/` were synthetically generated and validated against ground truth:
- `data/standards.json`: Company standard positions (deposit range: 1.0–2.0 months, notice period: 30–60 days, 4 required clause types, and 3 strictly forbidden terms).
- `data/standards_embeddings.npy` & `data/standards_embeddings_index.json`: Precomputed build-time vectors for rapid retrieval without startup latency.
- `data/sample_leases/`:
  1. `lease_clean.txt`: 100% compliant with all company standards.
  2. `lease_deposit_deviation.txt`: Security deposit requires 3.5 months rent (exceeds 2.0 months maximum).
  3. `lease_notice_deviation.txt`: Notice period specifies 15 days (below 30 days minimum).
  4. `lease_missing_clause.txt`: Completely omits mandatory `deposit_return_timeline` clause.
  5. `lease_forbidden_term.txt`: Contains prohibited clause waiving statutory habitability obligations.
- `data/leases_answer_key.json`: Ground-truth test verification key.

---

## Running the Automated Test Suite

```bash
# Phase 2: Segmentation test across all 5 leases
python -m tests.test_segmentation

# Phase 3: Semantic retrieval test
python -m tests.test_retrieval

# Phase 4: Classification & missing clause check
python -m tests.test_classification

# Phase 5: End-to-end report generation test
python -m tests.test_report
```

---

## Demo Video Link

Demo Video: https://youtu.be/3RLngQ-uslY
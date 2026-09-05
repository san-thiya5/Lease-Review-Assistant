"""
Lease Review Assistant — Unified FastAPI Application Entrypoint.
Serves both backend review API endpoints and compiled frontend static assets on port 8000.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from src.schemas import LeaseReviewReport
from src.parsing import extract_text, ParsingException
from src.segmentation import segment_clauses
from src.retrieval import match_clause_to_standards, load_standards_cache, STANDARDS_DATA
from src.classification import classify_clause
from src.missing_clause_check import find_missing_required_clauses
from src.report import build_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lease_review.app")

app = FastAPI(
    title="Lease Review Assistant (PS05)",
    description="Legal Operations AI assistant for reviewing lease agreements against company standards.",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_LEASES_DIR = Path("data/sample_leases")
TEMP_UPLOADS_DIR = Path("data/temp_uploads")
TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST_DIR = Path("frontend/dist")


@app.on_event("startup")
def on_startup():
    """Load standards library and precomputed embeddings into memory on server boot."""
    logger.info("Initializing standards cache and precomputed embeddings...")
    load_standards_cache()
    logger.info(
        f"Loaded standards library: {len(STANDARDS_DATA.get('required_clauses', []))} required clauses, "
        f"{len(STANDARDS_DATA.get('forbidden_terms', []))} forbidden terms."
    )


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "lease-review-assistant", "version": "1.0.0"}


@app.get("/api/sample-leases")
def list_sample_leases():
    """Returns the list of available pre-loaded synthetic sample leases."""
    try:
        if not SAMPLE_LEASES_DIR.exists():
            return {"sample_leases": []}
        files = sorted([f.name for f in SAMPLE_LEASES_DIR.glob("*.txt")])
        return {"sample_leases": files}
    except Exception as e:
        logger.error(f"Error listing sample leases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sample leases: {str(e)}"
        )


@app.get("/api/standards")
def get_standards():
    """Returns the company's active standard positions library."""
    return STANDARDS_DATA


@app.post("/api/review", response_model=LeaseReviewReport)
async def review_lease(
    file: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
):
    """
    Core review pipeline endpoint.
    Accepts an uploaded file (PDF/DOCX/TXT) or a reference to a pre-loaded sample lease.
    Executes: parse -> segment -> retrieve -> classify -> missing check -> assemble report.
    """
    temp_file_path: Optional[Path] = None
    original_filename = "document"

    try:
        # 1. Resolve target document
        if file and file.filename:
            original_filename = file.filename
            temp_file_path = TEMP_UPLOADS_DIR / f"upload_{file.filename}"
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_to_process = temp_file_path
        elif sample_filename:
            original_filename = sample_filename
            file_to_process = SAMPLE_LEASES_DIR / sample_filename
            if not file_to_process.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sample lease '{sample_filename}' not found."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either an uploaded file or a valid sample_filename must be provided."
            )

        # 2. Extract text (PyMuPDF / docx / txt)
        logger.info(f"Extracting text from: {original_filename}")
        raw_text = extract_text(str(file_to_process))

        # 3. Deterministic regex-first segmentation
        logger.info(f"Segmenting clauses for: {original_filename}")
        clauses = segment_clauses(raw_text)
        if not clauses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No structured clauses could be identified in the document."
            )

        # 4. Semantic retrieval + Clause classification
        logger.info(f"Evaluating {len(clauses)} clauses against standards...")
        findings = []
        for clause in clauses:
            matched_standards = match_clause_to_standards(clause, top_k=2)
            finding = classify_clause(clause, matched_standards, STANDARDS_DATA)
            findings.append(finding)

        # 5. Deterministic missing required clause check
        missing_clauses = find_missing_required_clauses(findings, STANDARDS_DATA)

        # 6. Structured report generation & plain summary synthesis
        report = build_report(
            lease_filename=original_filename,
            findings=findings,
            missing_clauses=missing_clauses,
            raw_text=raw_text,
            clauses=clauses,
        )

        logger.info(
            f"Review completed for '{original_filename}': is_clean={report.is_clean}, "
            f"deviations={len(report.deviations)}, forbidden={len(report.forbidden_terms_found)}, "
            f"missing={len(report.missing_required_clauses)}"
        )
        return report

    except HTTPException:
        raise
    except ParsingException as pe:
        logger.error(f"Document parsing error for {original_filename}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document parsing error: {str(pe)}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing lease review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while reviewing the lease agreement: {str(e)}"
        )
    finally:
        # Clean up temporary uploaded file
        if temp_file_path and temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception:
                pass


# Explicit root route for SPA entry
@app.get("/")
async def serve_root():
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {"status": "API active", "message": "Frontend build not found. Run 'npm run build' inside frontend/."},
        status_code=200
    )


# Mount static assets and frontend directory
if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        target = FRONTEND_DIST_DIR / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        index_file = FRONTEND_DIST_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"error": "Resource not found"}, status_code=404)


def run():
    """Main execution function for single-command start on port 8000."""
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print("\n" + "=" * 68)
    print("  LEASE REVIEW ASSISTANT (PS05) — SYSTEM READY")
    print(f"  --> Local Web UI : http://localhost:{port}")
    print(f"  --> API Docs     : http://localhost:{port}/docs")
    print("=" * 68 + "\n")
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    run()

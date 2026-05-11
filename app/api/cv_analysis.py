# app/api/cv_analysis.py

import json
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from fastapi import APIRouter, UploadFile, File, Form
from sentence_transformers import SentenceTransformer

from app.agents.persona_builder import build_personas
from app.agents.cv_evaluator import evaluate_candidate
from app.agents.candidate_ranker import rank_candidates
from app.agents.resume_parser import _extract_resumes_from_files
from app.utils.resume_skills import extract_skills_llm, extract_section

router = APIRouter()

# Loaded once at module import — no per-request overhead
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Tune between 0.25 (permissive) and 0.40 (strict)
SIMILARITY_THRESHOLD = 0.30

# Keep within Groq free tier: 30 req/min
MAX_EVAL_WORKERS = 5


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _prefilter(resumes: list, profile: dict, threshold: float) -> tuple:
    """
    Embedding-based pre-filter — runs locally, zero LLM cost.
    Rejects CVs whose cosine similarity to the job profile is below threshold.
    Returns (qualified, rejected).
    """
    profile_vec = _embedder.encode(json.dumps(profile), convert_to_numpy=True)
    qualified, rejected = [], []

    for r in resumes:
        vec = _embedder.encode(r["raw_text"][:2000], convert_to_numpy=True)
        r["similarity_score"] = round(_cosine(profile_vec, vec), 4)
        (qualified if r["similarity_score"] >= threshold else rejected).append(r)

    qualified.sort(key=lambda x: x["similarity_score"], reverse=True)
    return qualified, rejected


def _parse_resume(r: dict) -> dict:
    text = r["text"]
    return {
        "candidate_id": r["file"],
        "summary": extract_section(text, ["summary", "profile", "about", "objective"]),
        "skills": extract_skills_llm(resume_text=text),
        "experience": extract_section(text, ["experience", "work history", "employment"]),
        "projects": extract_section(text, ["projects", "key projects"]),
        "raw_text": text,
        "resume_path": r["path"],
    }


def _evaluate_parallel(parsed_resumes: list, personas: list) -> list:
    """
    Run all CV evaluations concurrently.
    Each CV is now 1 LLM call (batch prompt) instead of P calls.
    """
    results = [None] * len(parsed_resumes)

    with ThreadPoolExecutor(max_workers=MAX_EVAL_WORKERS) as executor:
        futures = {
            executor.submit(evaluate_candidate, cv, personas): idx
            for idx, cv in enumerate(parsed_resumes)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                cv = parsed_resumes[idx]
                print(f"[CV_ANALYSIS] Failed: {cv.get('candidate_id')} — {e}")
                results[idx] = {
                    "candidate_id": cv.get("candidate_id", "unknown"),
                    "persona_results": [],
                    "overall_score": 0,
                    "overall_grade": "F",
                    "best_fit_persona": "unknown",
                    "best_fit_persona_name": "unknown",
                    "summary": "Evaluation failed.",
                }

    return [r for r in results if r is not None]


# ─────────────────────────────────────────────
# POST /personas
# ─────────────────────────────────────────────
@router.post("/personas")
def generate_personas(payload: dict):
    profile = payload.get("profile", {})
    if not profile:
        return {"error": "Missing 'profile' in request body", "personas": []}
    return {"personas": build_personas(profile)}


# ─────────────────────────────────────────────
# POST /evaluate
# ─────────────────────────────────────────────
@router.post("/evaluate")
async def evaluate_cvs(
    resumes: UploadFile = File(...),
    personas: str = Form(...),
):
    try:
        persona_list = json.loads(personas)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in 'personas' field", "evaluations": []}

    if not persona_list:
        return {"error": "Persona list is empty", "evaluations": []}

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, resumes.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(resumes.file, f)

        raw_resumes = _extract_resumes_from_files([file_path])
        if not raw_resumes:
            return {"error": "No valid resumes found", "evaluations": []}

        parsed_resumes = [_parse_resume(r) for r in raw_resumes]
        evaluations = _evaluate_parallel(parsed_resumes, persona_list)

    return {"evaluations": evaluations}


# ─────────────────────────────────────────────
# POST /rank
# ─────────────────────────────────────────────
@router.post("/rank")
def rank_evaluated_candidates(payload: dict):
    evaluations = payload.get("evaluations", [])
    top_n = payload.get("top_n", 10)
    if not evaluations:
        return {"error": "No evaluations provided", "shortlist": []}
    return rank_candidates(evaluations, top_n=top_n)


# ─────────────────────────────────────────────
# POST /full
# ─────────────────────────────────────────────
@router.post("/full")
async def full_cv_pipeline(
    resumes: UploadFile = File(...),
    profile: str = Form(...),
    top_n: int = Form(10),
):
    try:
        profile_dict = json.loads(profile)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in 'profile' field"}

    # 1 LLM call — persona building
    personas = build_personas(profile_dict)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, resumes.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(resumes.file, f)

        raw_resumes = _extract_resumes_from_files([file_path])
        if not raw_resumes:
            return {"error": "No valid resumes found", "personas": personas, "evaluations": [], "shortlist": []}

        # 1 LLM call per resume — skill extraction
        parsed_resumes = [_parse_resume(r) for r in raw_resumes]

        # 0 LLM calls — local embedding filter
        qualified, rejected = _prefilter(parsed_resumes, profile_dict, SIMILARITY_THRESHOLD)

        # 1 LLM call per qualified CV — batch persona evaluation, run in parallel
        evaluations = _evaluate_parallel(qualified, personas)

    # Append rejected with score 0 so HR can see what was filtered
    for r in rejected:
        evaluations.append({
            "candidate_id": r["candidate_id"],
            "persona_results": [],
            "overall_score": 0,
            "overall_grade": "F",
            "best_fit_persona": "N/A",
            "best_fit_persona_name": "Pre-filtered (low relevance)",
            "summary": f"Similarity score {r.get('similarity_score', 0):.2f} below threshold {SIMILARITY_THRESHOLD}.",
        })

    # 0 LLM calls — pure Python ranking
    ranking = rank_candidates(evaluations, top_n=top_n)

    return {
        "personas": personas,
        "evaluations": evaluations,
        "ranking": ranking,
        "pre_filter_summary": {
            "total_uploaded": len(raw_resumes),
            "passed_filter": len(qualified),
            "rejected": len(rejected),
            "threshold": SIMILARITY_THRESHOLD,
        },
    }

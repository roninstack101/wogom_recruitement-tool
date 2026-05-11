# app/api/cv_analysis.py

import json
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from app.agents.persona_builder import build_personas
from app.agents.cv_evaluator import evaluate_candidate
from app.agents.candidate_ranker import rank_candidates
from app.agents.resume_parser import _extract_resumes_from_files
from app.utils.resume_skills import extract_skills_llm, extract_section
from app.api.auth import get_current_user
from app.db.database import get_db
from app.db.models import (
    User, JobRequest, JobProfile, Persona,
    Candidate, CandidateEvaluation, PipelineStageLog,
    Notification, NotificationType, CandidateStage,
)

router = APIRouter()

_embedder = SentenceTransformer("all-MiniLM-L6-v2")
SIMILARITY_THRESHOLD = 0.30
MAX_EVAL_WORKERS = 5


# ─────────────────────────────────────────────
# Helpers — pipeline
# ─────────────────────────────────────────────

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _prefilter(resumes: list, profile: dict, threshold: float) -> tuple:
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
# Helpers — DB extraction
# ─────────────────────────────────────────────

def _extract_email(text: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]+", text)
    return match.group(0) if match else ""


def _extract_name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.replace("-", "").replace("'", "").isalpha() for w in words):
            return line
    # Use filename as fallback, strip extension and clean
    return (
        fallback
        .replace(".pdf", "").replace(".docx", "").replace(".doc", "").replace(".txt", "")
        .replace("_", " ").replace("-", " ")
        .title()
        .strip()
    )


def _save_to_db(
    db: Session,
    job_id: int,
    profile_dict: dict,
    personas: list,
    evaluations: list,
    raw_text_map: dict,  # candidate_id -> raw_text
):
    # 1 — Save/update JobProfile
    job_profile = db.query(JobProfile).filter(JobProfile.job_id == job_id).first()
    if not job_profile:
        job_profile = JobProfile(
            job_id=job_id,
            ideal_candidate_summary=profile_dict.get("profile_summary", ""),
            required_skills=profile_dict.get("must_have_skills_refined", []),
            preferred_skills=profile_dict.get("nice_to_have_skills", []),
            raw_json=json.dumps(profile_dict),
        )
        db.add(job_profile)
        db.flush()
    else:
        job_profile.raw_json = json.dumps(profile_dict)
        job_profile.required_skills = profile_dict.get("must_have_skills_refined", [])

    # 2 — Replace personas for this profile
    db.query(Persona).filter(Persona.profile_id == job_profile.id).delete()
    for p in personas:
        db.add(Persona(
            profile_id=job_profile.id,
            persona_name=p.get("name", "Unknown"),
            description=p.get("summary", ""),
            scoring_criteria={"required_skills": p.get("required_skills", [])},
        ))

    # 3 — Save candidates + evaluations + stage logs
    job = db.query(JobRequest).filter(JobRequest.id == job_id).first()
    hr_user_id = job.assigned_hr_id if job else None

    saved_count = 0
    for ev in evaluations:
        cid = ev["candidate_id"]
        raw_text = raw_text_map.get(cid, "")
        name = _extract_name(raw_text, cid)
        email = _extract_email(raw_text) or None

        # Upsert candidate — match by job + name to avoid duplicates
        candidate = db.query(Candidate).filter(
            Candidate.job_id == job_id,
            Candidate.name == name,
        ).first()

        is_new = candidate is None
        if is_new:
            candidate = Candidate(
                job_id=job_id,
                name=name,
                email=email,
                resume_text=raw_text[:10000],
                stage=CandidateStage.cv_evaluated,
            )
            db.add(candidate)
        else:
            candidate.stage = CandidateStage.cv_evaluated
            if email:
                candidate.email = email

        db.flush()  # get candidate.id

        # Build persona score map and flatten strengths/gaps
        persona_scores = {
            r["persona_id"]: r["score"]
            for r in ev.get("persona_results", [])
        }
        strengths = "; ".join(
            s for r in ev.get("persona_results", []) for s in r.get("strengths", [])
        )
        gaps = "; ".join(
            g for r in ev.get("persona_results", []) for g in r.get("gaps", [])
        )

        # Upsert evaluation
        existing_eval = db.query(CandidateEvaluation).filter(
            CandidateEvaluation.candidate_id == candidate.id
        ).first()

        if existing_eval:
            existing_eval.overall_score = ev["overall_score"]
            existing_eval.grade = ev["overall_grade"]
            existing_eval.persona_scores = persona_scores
            existing_eval.strengths = strengths
            existing_eval.weaknesses = gaps
            existing_eval.recommendation = ev.get("summary", "")
            existing_eval.is_automated = True
            existing_eval.is_above_threshold = ev["overall_score"] >= 70
        else:
            db.add(CandidateEvaluation(
                candidate_id=candidate.id,
                job_id=job_id,
                overall_score=ev["overall_score"],
                grade=ev["overall_grade"],
                persona_scores=persona_scores,
                strengths=strengths,
                weaknesses=gaps,
                recommendation=ev.get("summary", ""),
                is_automated=True,
                is_above_threshold=ev["overall_score"] >= 70,
            ))

        # Stage log only for new candidates
        if is_new:
            db.add(PipelineStageLog(
                candidate_id=candidate.id,
                job_id=job_id,
                from_stage=None,
                to_stage=CandidateStage.cv_evaluated.value,
                changed_by=None,
                reason="CV evaluated by AI pipeline",
            ))

        saved_count += 1

    # 4 — Notify assigned HR
    if hr_user_id:
        evaluated = len([e for e in evaluations if e["overall_score"] > 0])
        db.add(Notification(
            user_id=hr_user_id,
            message=f"CV evaluation complete for Job #{job_id}. {evaluated} candidates evaluated.",
            type=NotificationType.cv_evaluation_complete,
            related_job_id=job_id,
        ))

    db.commit()
    return saved_count


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
    job_id: int = Form(...),
    top_n: int = Form(10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        profile_dict = json.loads(profile)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in 'profile' field"}

    # Step 1 — Build personas (1 LLM call)
    personas = build_personas(profile_dict)

    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, resumes.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(resumes.file, f)

        raw_resumes = _extract_resumes_from_files([file_path])
        if not raw_resumes:
            return {"error": "No valid resumes found", "personas": personas, "evaluations": [], "shortlist": []}

        # Step 2 — Parse resumes (1 LLM call per resume for skill extraction)
        parsed_resumes = [_parse_resume(r) for r in raw_resumes]

        # Build raw_text map for DB saving (covers all CVs including rejected)
        raw_text_map = {r["candidate_id"]: r["raw_text"] for r in parsed_resumes}

        # Step 3 — Embedding pre-filter (zero LLM cost)
        qualified, rejected = _prefilter(parsed_resumes, profile_dict, SIMILARITY_THRESHOLD)

        # Step 4 — Parallel LLM evaluation (1 call per qualified CV)
        evaluations = _evaluate_parallel(qualified, personas)

    # Append rejected with score 0
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

    # Step 5 — Rank (no LLM)
    ranking = rank_candidates(evaluations, top_n=top_n)

    # Step 6 — Persist everything to DB
    saved = _save_to_db(db, job_id, profile_dict, personas, evaluations, raw_text_map)

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
        "db_summary": {
            "job_id": job_id,
            "candidates_saved": saved,
        },
    }

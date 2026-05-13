# app/api/cv_analysis.py

import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from typing import Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from app.agents.persona_builder import build_personas
from app.agents.cv_evaluator import evaluate_candidate
from app.agents.candidate_ranker import rank_candidates
from app.agents.resume_parser import _extract_resumes_from_files
from app.utils.resume_skills import extract_section, extract_location
from app.api.auth import get_current_user
from app.db.database import get_db, SessionLocal
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
# In-memory async job store
# ─────────────────────────────────────────────
_eval_jobs: dict = {}
_eval_jobs_lock = threading.Lock()


def _set_job(job_id: str, **kwargs):
    with _eval_jobs_lock:
        if job_id not in _eval_jobs:
            _eval_jobs[job_id] = {}
        _eval_jobs[job_id].update(kwargs)


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
        "skills": {},
        "experience": extract_section(text, ["experience", "work history", "employment"]),
        "projects": extract_section(text, ["projects", "key projects"]),
        "raw_text": text,
        "resume_path": r["path"],
        "location": extract_location(text),
    }


def _parse_resumes_parallel(raw_resumes: list) -> list:
    results = [None] * len(raw_resumes)
    with ThreadPoolExecutor(max_workers=MAX_EVAL_WORKERS) as executor:
        futures = {executor.submit(_parse_resume, r): i for i, r in enumerate(raw_resumes)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                r = raw_resumes[idx]
                print(f"[CV_ANALYSIS] Parse failed: {r.get('file')} — {e}")
                results[idx] = {
                    "candidate_id": r["file"],
                    "summary": "", "skills": {}, "experience": "",
                    "projects": "", "raw_text": r.get("text", ""),
                    "resume_path": r.get("path", ""), "location": "",
                }
    return [r for r in results if r is not None]


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
    job_id: Optional[int] = Form(None),
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

        # Step 2 — Parse resumes in parallel
        parsed_resumes = _parse_resumes_parallel(raw_resumes)

        # Build raw_text map for DB saving (covers all CVs including rejected)
        raw_text_map = {r["candidate_id"]: r["raw_text"] for r in parsed_resumes}

        # Step 3 — Embedding pre-filter (zero LLM cost)
        qualified, rejected = _prefilter(parsed_resumes, profile_dict, SIMILARITY_THRESHOLD)

        # Step 4 — Parallel LLM evaluation (1 call per qualified CV)
        evaluations = _evaluate_parallel(qualified, personas)

    # Append rejected with score 0 (use regex location as fallback)
    location_map = {r["candidate_id"]: r.get("location", "") for r in parsed_resumes}
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
    ranking = rank_candidates(evaluations, top_n=len(evaluations))

    # Step 6 — Persist to DB only if job_id provided
    db_summary = None
    if job_id is not None:
        saved = _save_to_db(db, job_id, profile_dict, personas, evaluations, raw_text_map)
        db_summary = {"job_id": job_id, "candidates_saved": saved}

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
        "db_summary": db_summary,
    }


# ─────────────────────────────────────────────
# Background pipeline runner
# ─────────────────────────────────────────────

def _run_pipeline_background(eval_job_id: str, tmp_path: str, profile_str: str, db_job_id, top_n: int):
    db = SessionLocal()
    try:
        _set_job(eval_job_id, message="Building candidate personas…")
        profile_dict = json.loads(profile_str)
        personas = build_personas(profile_dict)

        _set_job(eval_job_id, message="Extracting resumes from file…")
        raw_resumes = _extract_resumes_from_files([tmp_path])
        if not raw_resumes:
            _set_job(eval_job_id, status="failed", error="No valid resumes found in the uploaded file.")
            return

        total = len(raw_resumes)
        _set_job(eval_job_id, message=f"Parsing {total} resumes…")
        parsed_resumes = _parse_resumes_parallel(raw_resumes)
        raw_text_map = {r["candidate_id"]: r["raw_text"] for r in parsed_resumes}

        _set_job(eval_job_id, message=f"Pre-filtering {total} resumes with embeddings…")
        qualified, rejected = _prefilter(parsed_resumes, profile_dict, SIMILARITY_THRESHOLD)

        _set_job(eval_job_id, message=f"Evaluating {len(qualified)} qualified candidates with AI… (this takes a while)")
        evaluations = _evaluate_parallel(qualified, personas)

        location_map = {r["candidate_id"]: r.get("location", "") for r in parsed_resumes}
        for r in rejected:
            evaluations.append({
                "candidate_id": r["candidate_id"],
                "location": location_map.get(r["candidate_id"], ""),
                "persona_results": [],
                "overall_score": 0,
                "overall_grade": "F",
                "best_fit_persona": "N/A",
                "best_fit_persona_name": "Pre-filtered (low relevance)",
                "summary": f"Similarity score {r.get('similarity_score', 0):.2f} below threshold {SIMILARITY_THRESHOLD}.",
            })

        _set_job(eval_job_id, message="Ranking candidates…")
        ranking = rank_candidates(evaluations, top_n=len(evaluations))

        db_summary = None
        if db_job_id is not None:
            _set_job(eval_job_id, message="Saving results to database…")
            saved = _save_to_db(db, db_job_id, profile_dict, personas, evaluations, raw_text_map)
            db_summary = {"job_id": db_job_id, "candidates_saved": saved}

        _set_job(eval_job_id,
            status="complete",
            message=f"Done! {len(qualified)} of {total} candidates evaluated.",
            result={
                "personas": personas,
                "evaluations": evaluations,
                "ranking": ranking,
                "pre_filter_summary": {
                    "total_uploaded": total,
                    "passed_filter": len(qualified),
                    "rejected": len(rejected),
                    "threshold": SIMILARITY_THRESHOLD,
                },
                "db_summary": db_summary,
            },
        )

    except Exception as e:
        print(f"[CV_ASYNC] Job {eval_job_id} failed: {e}")
        _set_job(eval_job_id, status="failed", error=str(e))
    finally:
        db.close()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ─────────────────────────────────────────────
# POST /full-async  — start background job
# ─────────────────────────────────────────────

@router.post("/full-async")
async def full_cv_pipeline_async(
    resumes: UploadFile = File(...),
    profile: str = Form(...),
    job_id: Optional[int] = Form(None),
    top_n: int = Form(10),
    current_user: User = Depends(get_current_user),
):
    try:
        json.loads(profile)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON in 'profile' field"}

    eval_job_id = str(uuid.uuid4())
    suffix = os.path.splitext(resumes.filename or "upload.zip")[1] or ".zip"
    tmp_path = os.path.join(tempfile.gettempdir(), f"cv_upload_{eval_job_id}{suffix}")

    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(resumes.file, f)

    _set_job(eval_job_id, status="processing", message="Job queued…", result=None, error=None)

    thread = threading.Thread(
        target=_run_pipeline_background,
        args=(eval_job_id, tmp_path, profile, job_id, top_n),
        daemon=True,
    )
    thread.start()

    return {"job_id": eval_job_id}


# ─────────────────────────────────────────────
# GET /job/{eval_job_id}  — poll job status
# ─────────────────────────────────────────────

@router.get("/job/{eval_job_id}")
def get_cv_job_status(eval_job_id: str):
    with _eval_jobs_lock:
        job = dict(_eval_jobs.get(eval_job_id, {}))
    if not job:
        return {"status": "not_found", "message": "Job not found — server may have restarted."}
    return job

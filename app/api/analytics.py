from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import JobRequest, JobStatus, User, UserRole, Candidate
from app.api.auth import require_role

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/pipeline", response_model=List[Dict[str, Any]])
def get_hiring_pipeline(
    user: User = Depends(require_role(UserRole.hr)),
    db: Session = Depends(get_db),
):
    """
    Get aggregated hiring pipeline data for all active jobs.
    Returns candidate counts by stage for each job.
    """
    jobs = db.query(JobRequest).filter(
        JobRequest.status.in_([JobStatus.active, JobStatus.closed])
    ).all()

    pipeline_data = []

    for job in jobs:
        candidates = db.query(Candidate).filter(Candidate.job_id == job.id).all()
        total_candidates = len(candidates)
        stage_counts: Dict[str, int] = {}
        for cand in candidates:
            stage = cand.stage or "Unknown"
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        pipeline_data.append({
            "job_id": job.id,
            "role_title": job.role_title,
            "status": job.status.value if hasattr(job.status, "value") else job.status,
            "total_candidates": total_candidates,
            "stages": stage_counts,
        })

    return pipeline_data

# app/api/job_requests.py

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import io
import docx
import pypdf

from app.db.database import get_db
from app.db.models import (
    JobRequest, JobStatus, Notification, NotificationType, User, UserRole,
    JDSource, Candidate,
)
from app.api.auth import get_current_user, require_role
from app.utils.scheduler import schedule_pre_close_tasks

router = APIRouter(prefix="/jobs", tags=["Job Requests"])


# ── Schemas ────────────────────────────────────────────

class JobCreateRequest(BaseModel):
    role_title: str
    jd_text: Optional[str] = None
    profile_json: Optional[str] = None
    budget: Optional[float] = None
    adjustable_budget: Optional[float] = None
    end_date: Optional[str] = None  # ISO date string


class JobSubmitRequest(BaseModel):
    budget: Optional[float] = None
    adjustable_budget: Optional[float] = None
    end_date: Optional[str] = None


class JobOut(BaseModel):
    id: int
    creator_id: int
    creator_name: Optional[str] = None
    role_title: str
    jd_text: Optional[str] = None
    profile_json: Optional[str] = None
    budget: Optional[float] = None
    adjustable_budget: Optional[float] = None
    end_date: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── Helpers ────────────────────────────────────────────

def _job_to_dict(job: JobRequest) -> dict:
    return {
        "id": job.id,
        "creator_id": job.creator_id,
        "creator_name": job.creator.name if job.creator else None,
        "role_title": job.role_title,
        "jd_text": job.jd_text,
        "profile_json": job.profile_json,
        "budget": job.budget,
        "adjustable_budget": job.adjustable_budget,
        "end_date": job.end_date.isoformat() if job.end_date else None,
        "status": job.status.value if hasattr(job.status, "value") else job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _notify_all_hr(db: Session, message: str, ntype: NotificationType, job_id: int):
    """Create a notification for every HR user."""
    hr_users = db.query(User).filter(User.role == UserRole.hr).all()
    for hr in hr_users:
        db.add(Notification(
            user_id=hr.id,
            message=message,
            type=ntype,
            related_job_id=job_id,
        ))


def _notify_creator(db: Session, creator_id: int, message: str, ntype: NotificationType, job_id: int):
    """Create a notification for the job creator (team lead)."""
    db.add(Notification(
        user_id=creator_id,
        message=message,
        type=ntype,
        related_job_id=job_id,
    ))


# ── Team Lead Routes ──────────────────────────────────

@router.post("/", response_model=JobOut, status_code=201)
def create_job(
    body: JobCreateRequest,
    user: User = Depends(require_role(UserRole.team_lead)),
    db: Session = Depends(get_db),
):
    """Create a new job request as a draft."""
    end_dt = None
    if body.end_date:
        end_dt = datetime.fromisoformat(body.end_date)

    job = JobRequest(
        creator_id=user.id,
        role_title=body.role_title,
        jd_text=body.jd_text,
        profile_json=body.profile_json,
        budget=body.budget,
        adjustable_budget=body.adjustable_budget,
        end_date=end_dt,
        status=JobStatus.draft,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


@router.get("/", response_model=List[JobOut])
def list_my_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List jobs belonging to the current user (team lead sees own, HR sees all)."""
    if user.role == UserRole.hr:
        jobs = db.query(JobRequest).order_by(JobRequest.created_at.desc()).all()
    else:
        jobs = (
            db.query(JobRequest)
            .filter(JobRequest.creator_id == user.id)
            .order_by(JobRequest.created_at.desc())
            .all()
        )
    return [_job_to_dict(j) for j in jobs]


# ── Candidate Endpoints ───────────────────────────────

@router.get("/all-candidates")
def get_all_candidates(
    user: User = Depends(require_role(UserRole.hr)),
    db: Session = Depends(get_db),
):
    """Fetch candidates for every active/closed job from the local database."""
    import json

    jobs = db.query(JobRequest).filter(
        JobRequest.status.in_([JobStatus.active, JobStatus.closed])
    ).all()

    result = []
    for job in jobs:
        cands = db.query(Candidate).filter(Candidate.job_id == job.id).all()

        # Extract generated_profile from profile_json metadata
        generated_profile = None
        if job.profile_json:
            try:
                meta = json.loads(job.profile_json)
                if isinstance(meta, dict):
                    # Try nested generated_profile key first, fall back to full profile_json
                    generated_profile = meta.get("generated_profile") or meta
                else:
                    generated_profile = meta
            except (json.JSONDecodeError, TypeError):
                generated_profile = job.profile_json

        result.append({
            "job_id": job.id,
            "role_title": job.role_title,
            "jd_text": job.jd_text or "",
            "generated_profile": generated_profile,
            "status": job.status.value if hasattr(job.status, "value") else job.status,
            "candidates": [
                {
                    "id": c.id,
                    "name": c.name,
                    "email": c.email,
                    "stage": c.stage.value if hasattr(c.stage, "value") else str(c.stage),
                    "applied_at": c.applied_at.isoformat() if c.applied_at else None,
                }
                for c in cands
            ],
        })

    return result


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single job by ID."""
    job = db.query(JobRequest).filter(JobRequest.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if user.role == UserRole.team_lead and job.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not your job request")
    return _job_to_dict(job)


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    body: JobCreateRequest,
    user: User = Depends(require_role(UserRole.team_lead)),
    db: Session = Depends(get_db),
):
    """Update a draft job request."""
    job = db.query(JobRequest).filter(JobRequest.id == job_id, JobRequest.creator_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.draft:
        raise HTTPException(status_code=400, detail="Can only edit draft jobs")

    job.role_title = body.role_title
    job.jd_text = body.jd_text
    job.profile_json = body.profile_json
    job.budget = body.budget
    job.adjustable_budget = body.adjustable_budget
    if body.end_date:
        job.end_date = datetime.fromisoformat(body.end_date)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


@router.post("/{job_id}/submit", response_model=JobOut)
def submit_job(
    job_id: int,
    body: JobSubmitRequest = None,
    user: User = Depends(require_role(UserRole.team_lead)),
    db: Session = Depends(get_db),
):
    """Submit a draft job to HR for review."""
    job = db.query(JobRequest).filter(JobRequest.id == job_id, JobRequest.creator_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft jobs can be submitted")

    # Allow optional field updates on submit
    if body:
        if body.budget is not None:
            job.budget = body.budget
        if body.adjustable_budget is not None:
            job.adjustable_budget = body.adjustable_budget
        if body.end_date is not None:
            job.end_date = datetime.fromisoformat(body.end_date)

    job.status = JobStatus.pending_hr
    job.updated_at = datetime.now(timezone.utc)

    _notify_all_hr(
        db,
        f"New job request: \"{job.role_title}\" submitted by {user.name}",
        NotificationType.job_submitted,
        job.id,
    )

    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: int,
    user: User = Depends(require_role(UserRole.team_lead)),
    db: Session = Depends(get_db),
):
    """Cancel a job request. Notifies all HR users."""
    job = db.query(JobRequest).filter(JobRequest.id == job_id, JobRequest.creator_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in (JobStatus.cancelled, JobStatus.closed):
        raise HTTPException(status_code=400, detail="Job is already cancelled or closed")

    job.status = JobStatus.cancelled
    job.updated_at = datetime.now(timezone.utc)

    _notify_all_hr(
        db,
        f"Job cancelled: \"{job.role_title}\" by {user.name}",
        NotificationType.job_cancelled,
        job.id,
    )

    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


# ── HR Routes ─────────────────────────────────────────

@router.get("/incoming/pending", response_model=List[JobOut])
def incoming_jobs(
    user: User = Depends(require_role(UserRole.hr)),
    db: Session = Depends(get_db),
):
    """HR view: list all pending_hr jobs."""
    jobs = (
        db.query(JobRequest)
        .filter(JobRequest.status == JobStatus.pending_hr)
        .order_by(JobRequest.created_at.desc())
        .all()
    )
    return [_job_to_dict(j) for j in jobs]


class ActivateRequest(BaseModel):
    pass


@router.post("/{job_id}/activate", response_model=JobOut)
def activate_job(
    job_id: int,
    body: ActivateRequest = ActivateRequest(),
    user: User = Depends(require_role(UserRole.hr)),
    db: Session = Depends(get_db),
):
    """HR accepts a pending job request → status = active."""
    job = db.query(JobRequest).filter(JobRequest.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.pending_hr:
        raise HTTPException(status_code=400, detail="Job is not pending HR review")

    job.status = JobStatus.active
    job.updated_at = datetime.now(timezone.utc)

    # Schedule pre-close tasks if end_date exists
    if job.end_date:
        schedule_pre_close_tasks(job.id, job.end_date)

    _notify_creator(
        db, job.creator_id,
        f"Your job request \"{job.role_title}\" has been activated by HR",
        NotificationType.job_activated,
        job.id,
    )

    db.commit()
    db.refresh(job)
    return _job_to_dict(job)


@router.put("/{job_id}/hr-edit", response_model=JobOut)
def hr_edit_job(
    job_id: int,
    body: JobCreateRequest,
    user: User = Depends(require_role(UserRole.hr)),
    db: Session = Depends(get_db),
):
    """HR edits a pending job request before activating it."""
    job = db.query(JobRequest).filter(JobRequest.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.pending_hr:
        raise HTTPException(status_code=400, detail="Can only edit jobs pending HR review")

    job.role_title = body.role_title
    job.jd_text = body.jd_text
    job.profile_json = body.profile_json
    job.budget = body.budget
    job.adjustable_budget = body.adjustable_budget
    if body.end_date:
        job.end_date = datetime.fromisoformat(body.end_date)
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return _job_to_dict(job)

@router.post("/parse-content")
async def parse_jd_content(file: UploadFile = File(...)):
    """Parse text from an uploaded DOCX or PDF file."""
    content = ""
    filename = file.filename.lower()

    try:
        if filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(await file.read()))
            content = "\n".join([para.text for para in doc.paragraphs])
        elif filename.endswith(".pdf"):
            pdf = pypdf.PdfReader(io.BytesIO(await file.read()))
            content = "\n".join([page.extract_text() for page in pdf.pages])
        else:
            raise HTTPException(status_code=400, detail="Only .docx and .pdf files are supported")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    return {"text": content}

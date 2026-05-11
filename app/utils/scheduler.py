# app/utils/scheduler.py
"""
Background scheduler for automated HR tasks.
- Sends closing reminders 2 days before end_date
- Auto-evaluates CVs and notifies HR
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from app.db.database import SessionLocal
from app.db.models import (
    JobRequest, JobStatus, JobProfile, User, UserRole,
    Notification, NotificationType,
    Candidate, CandidateEvaluation, CandidateStage, BudgetFlag,
    PipelineStageLog,
)

logger = logging.getLogger("scheduler")

# ── Singleton Scheduler ──────────────────────────────────
scheduler = BackgroundScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={"coalesce": True, "max_instances": 1},
)


def start_scheduler():
    """Start the background scheduler (idempotent)."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")


# ── Schedule Tasks for a Job ─────────────────────────────

def schedule_pre_close_tasks(job_id: int, end_date: datetime):
    """
    Schedule reminder + auto-evaluation 2 days before end_date.
    If end_date is less than 2 days away, run immediately.
    """
    # Normalize end_date to timezone-aware (SQLite stores naive datetimes)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    run_at = end_date - timedelta(days=2)
    now = datetime.now(timezone.utc)

    if run_at <= now:
        # If already past the trigger time, run immediately
        run_at = now + timedelta(seconds=10)

    job_tag = f"job-{job_id}"

    # Remove any existing scheduled tasks for this job
    cancel_job_schedule(job_id)

    # Schedule reminder notification
    scheduler.add_job(
        send_closing_reminder,
        "date",
        run_date=run_at,
        args=[job_id],
        id=f"reminder-{job_id}",
        replace_existing=True,
    )

    # Schedule auto CV evaluation (5 seconds after reminder)
    scheduler.add_job(
        run_auto_evaluation,
        "date",
        run_date=run_at + timedelta(seconds=5),
        args=[job_id],
        id=f"auto-eval-{job_id}",
        replace_existing=True,
    )

    logger.info(
        f"Scheduled pre-close tasks for job {job_id} at {run_at.isoformat()}"
    )


def cancel_job_schedule(job_id: int):
    """Remove all scheduled tasks for a job."""
    for prefix in ("reminder-", "auto-eval-"):
        try:
            scheduler.remove_job(f"{prefix}{job_id}")
        except Exception:
            pass


# ── Task Implementations ─────────────────────────────────

def send_closing_reminder(job_id: int):
    """Send a notification to all HR users reminding them the job is closing soon."""
    db = SessionLocal()
    try:
        job = db.query(JobRequest).filter(JobRequest.id == job_id).first()
        if not job or job.status != JobStatus.active:
            return

        hr_users = db.query(User).filter(User.role == UserRole.hr).all()
        for hr in hr_users:
            db.add(Notification(
                user_id=hr.id,
                message=f'⏰ Reminder: "{job.role_title}" is closing in 2 days. CV evaluation will start automatically.',
                type=NotificationType.closing_reminder,
                related_job_id=job.id,
            ))
        db.commit()
        logger.info(f"Closing reminder sent for job {job_id}")
    except Exception as e:
        logger.error(f"Error sending closing reminder for job {job_id}: {e}")
        db.rollback()
    finally:
        db.close()


def run_auto_evaluation(job_id: int):
    """
    Automatically evaluate all candidate CVs for a job.
    1. Fetch candidates from local database
    2. Run mock evaluation (score + grade)
    3. Store results in candidate_evaluations table
    4. Notify all HR users
    """
    db = SessionLocal()
    try:
        job = db.query(JobRequest).filter(JobRequest.id == job_id).first()
        if not job or job.status != JobStatus.active:
            return

        # Fetch candidates from local database
        candidates_rows = db.query(Candidate).filter(Candidate.job_id == job_id).all()

        if not candidates_rows:
            logger.info(f"No candidates for job {job_id}, skipping evaluation")
            return

        # Run evaluation — in mock/demo mode, generate scores deterministically
        evaluations = []
        for cand in candidates_rows:
            import hashlib
            name = cand.name or "Unknown"
            # Generate a deterministic score based on candidate name
            hash_val = int(hashlib.md5(name.encode()).hexdigest(), 16)
            score = 45 + (hash_val % 51)  # Score between 45-95

            grade = _compute_grade(score)
            evaluations.append({
                "candidate_id": cand.id,
                "name": name,
                "email": cand.email,
                "score": score,
                "grade": grade,
                "stage": cand.stage.value if hasattr(cand.stage, "value") else str(cand.stage),
                "summary": f"Auto-evaluated candidate with score {score}/{grade}",
            })

            # Store evaluation in the dedicated table
            existing_eval = db.query(CandidateEvaluation).filter(
                CandidateEvaluation.candidate_id == cand.id
            ).first()
            if not existing_eval:
                db.add(CandidateEvaluation(
                    candidate_id=cand.id,
                    score=score,
                    grade=grade,
                    summary=f"Auto-evaluated candidate with score {score}/{grade}",
                ))

        # Sort by score descending
        evaluations.sort(key=lambda x: x["score"], reverse=True)

        db.commit()

        # Notify HR
        hr_users = db.query(User).filter(User.role == UserRole.hr).all()
        top = evaluations[0] if evaluations else None
        top_msg = f" Top candidate: {top['name']} ({top['grade']})" if top else ""

        for hr in hr_users:
            db.add(Notification(
                user_id=hr.id,
                message=(
                    f'✅ CV evaluation for "{job.role_title}" is complete. '
                    f'{len(evaluations)} candidates evaluated.{top_msg}'
                ),
                type=NotificationType.cv_evaluation_complete,
                related_job_id=job.id,
            ))
        db.commit()
        logger.info(f"Auto-evaluation complete for job {job_id}: {len(evaluations)} candidates")

    except Exception as e:
        logger.error(f"Error in auto-evaluation for job {job_id}: {e}")
        db.rollback()
    finally:
        db.close()


def _compute_grade(score: int) -> str:
    """Convert a numeric score to a letter grade."""
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 85: return "A-"
    if score >= 80: return "B+"
    if score >= 75: return "B"
    if score >= 70: return "B-"
    if score >= 65: return "C+"
    if score >= 60: return "C"
    if score >= 55: return "C-"
    if score >= 50: return "D"
    return "F"


def reschedule_active_jobs():
    """
    On startup, re-schedule tasks for any active jobs with future end_dates.
    """
    db = SessionLocal()
    try:
        jobs = db.query(JobRequest).filter(
            JobRequest.status == JobStatus.active,
            JobRequest.end_date.isnot(None),
        ).all()

        now = datetime.now(timezone.utc)
        count = 0
        for job in jobs:
            end = job.end_date
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end > now:
                schedule_pre_close_tasks(job.id, end)
                count += 1

        logger.info(f"Re-scheduled {count} active jobs on startup")
    except Exception as e:
        logger.error(f"Error re-scheduling jobs: {e}")
    finally:
        db.close()

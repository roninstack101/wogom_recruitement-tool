# app/db/models.py
"""
Recruitment Automation — Full Database Schema
10 tables covering the entire hiring pipeline:
  users, job_requests, job_profiles, personas,
  candidates, candidate_evaluations, chatbot_sessions,
  interview_slots, pipeline_stage_logs, notifications
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, Enum as SAEnum, JSON,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.db.database import Base


# ── Enums ──────────────────────────────────────────────

class UserRole(str, enum.Enum):
    team_lead = "team_lead"
    hr = "hr"


class JobStatus(str, enum.Enum):
    draft = "draft"
    pending_hr = "pending_hr"
    rejected = "rejected"
    active = "active"
    evaluation_in_progress = "evaluation_in_progress"
    chatbot_screening = "chatbot_screening"
    interview_scheduling = "interview_scheduling"
    hired = "hired"
    closed = "closed"
    cancelled = "cancelled"


class JDSource(str, enum.Enum):
    ai_created = "ai_created"
    manual = "manual"
    linked = "linked"


class NotificationType(str, enum.Enum):
    job_submitted = "job_submitted"
    job_cancelled = "job_cancelled"
    job_activated = "job_activated"
    job_rejected = "job_rejected"
    closing_reminder = "closing_reminder"
    cv_evaluation_complete = "cv_evaluation_complete"
    chatbot_complete = "chatbot_complete"
    interview_booked = "interview_booked"
    candidate_hired = "candidate_hired"
    general = "general"


class CandidateStage(str, enum.Enum):
    applied = "applied"
    cv_evaluated = "cv_evaluated"
    shortlisted = "shortlisted"
    chatbot_screening = "chatbot_screening"
    chatbot_passed = "chatbot_passed"
    chatbot_failed = "chatbot_failed"
    interview_scheduled = "interview_scheduled"
    interviewed = "interviewed"
    offer_made = "offer_made"
    offer_accepted = "offer_accepted"
    hired = "hired"
    rejected = "rejected"
    withdrawn = "withdrawn"


class BudgetFlag(str, enum.Enum):
    ok = "ok"
    over_budget = "over_budget"
    red_flag = "red_flag"


class ChatbotStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    passed = "passed"
    failed = "failed"
    expired = "expired"


class InterviewStatus(str, enum.Enum):
    booked = "booked"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


def _utc_now():
    return datetime.now(timezone.utc)


# ── 1. Users ───────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    department = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=_utc_now)

    # relationships
    job_requests = relationship("JobRequest", back_populates="creator", foreign_keys="JobRequest.creator_id")
    assigned_jobs = relationship("JobRequest", back_populates="assigned_hr", foreign_keys="JobRequest.assigned_hr_id")
    notifications = relationship("Notification", back_populates="user")


# ── 2. Job Requests ───────────────────────────────────

class JobRequest(Base):
    __tablename__ = "job_requests"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_hr_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    role_title = Column(String(255), nullable=False)
    jd_text = Column(Text, nullable=True)
    department = Column(String(120), nullable=True)
    location = Column(String(120), nullable=True)
    experience_min = Column(Integer, nullable=True)
    experience_max = Column(Integer, nullable=True)
    budget = Column(Float, nullable=True)
    adjustable_budget = Column(Float, nullable=True)
    headcount = Column(Integer, default=1)
    hired_count = Column(Integer, default=0)

    end_date = Column(DateTime, nullable=True)
    status = Column(SAEnum(JobStatus), default=JobStatus.draft, nullable=False)
    rejection_reason = Column(Text, nullable=True)

    jd_source = Column(SAEnum(JDSource), nullable=True)
    linked_jd_id = Column(Integer, ForeignKey("job_requests.id"), nullable=True)

    # Legacy field — keep for backward compat during migration
    profile_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    # relationships
    creator = relationship("User", back_populates="job_requests", foreign_keys=[creator_id])
    assigned_hr = relationship("User", back_populates="assigned_jobs", foreign_keys=[assigned_hr_id])
    linked_jd = relationship("JobRequest", remote_side=[id])
    profile = relationship("JobProfile", back_populates="job", uselist=False)
    candidates = relationship("Candidate", back_populates="job")
    stage_logs = relationship("PipelineStageLog", back_populates="job")


# ── 3. Job Profiles (AI-generated candidate profile) ──

class JobProfile(Base):
    __tablename__ = "job_profiles"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_requests.id"), unique=True, nullable=False)

    ideal_candidate_summary = Column(Text, nullable=True)
    required_skills = Column(JSON, nullable=True)     # ["Python", "ML", ...]
    preferred_skills = Column(JSON, nullable=True)
    experience_description = Column(Text, nullable=True)
    education_requirements = Column(Text, nullable=True)
    cultural_fit_notes = Column(Text, nullable=True)
    evaluation_threshold = Column(Integer, default=70)
    raw_json = Column(Text, nullable=True)            # Full AI output

    created_at = Column(DateTime, default=_utc_now)

    # relationships
    job = relationship("JobRequest", back_populates="profile")
    personas = relationship("Persona", back_populates="profile", cascade="all, delete-orphan")


# ── 4. Personas (5 AI-generated evaluation personas) ──

class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("job_profiles.id"), nullable=False)

    persona_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    weight = Column(Float, default=0.2)
    scoring_criteria = Column(JSON, nullable=True)     # {"technical": 40, ...}

    created_at = Column(DateTime, default=_utc_now)

    # relationships
    profile = relationship("JobProfile", back_populates="personas")


# ── 5. Candidates ─────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    current_salary = Column(Float, nullable=True)
    expected_salary = Column(Float, nullable=True)
    resume_url = Column(String(500), nullable=True)
    resume_text = Column(Text, nullable=True)

    stage = Column(SAEnum(CandidateStage), default=CandidateStage.applied)
    budget_flag = Column(SAEnum(BudgetFlag), default=BudgetFlag.ok)

    applied_at = Column(DateTime, default=_utc_now)
    synced_at = Column(DateTime, nullable=True)

    # relationships
    job = relationship("JobRequest", back_populates="candidates")
    evaluation = relationship("CandidateEvaluation", back_populates="candidate", uselist=False)
    chatbot_sessions = relationship("ChatbotSession", back_populates="candidate")
    interview_slots = relationship("InterviewSlot", back_populates="candidate")
    stage_logs = relationship("PipelineStageLog", back_populates="candidate")


# ── 7. Candidate Evaluations ──────────────────────────

class CandidateEvaluation(Base):
    __tablename__ = "candidate_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), unique=True, nullable=False)
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    overall_score = Column(Float, nullable=True)
    grade = Column(String(5), nullable=True)
    is_above_threshold = Column(Boolean, default=False)
    budget_issue = Column(Boolean, default=False)

    persona_scores = Column(JSON, nullable=True)      # {"Technical Expert": 85, ...}
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    evaluated_at = Column(DateTime, default=_utc_now)
    is_automated = Column(Boolean, default=False)

    # relationships
    candidate = relationship("Candidate", back_populates="evaluation")
    job = relationship("JobRequest")


# ── 8. Chatbot Sessions (WhatsApp) ────────────────────

class ChatbotSession(Base):
    __tablename__ = "chatbot_sessions"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    status = Column(SAEnum(ChatbotStatus), default=ChatbotStatus.pending)
    questions_asked = Column(JSON, nullable=True)     # [{"q": "...", "expected": "...", "actual": "..."}]
    score = Column(Float, nullable=True)

    started_at = Column(DateTime, default=_utc_now)
    completed_at = Column(DateTime, nullable=True)
    whatsapp_thread_id = Column(String(100), nullable=True)

    # relationships
    candidate = relationship("Candidate", back_populates="chatbot_sessions")
    job = relationship("JobRequest")


# ── 9. Interview Slots ────────────────────────────────

class InterviewSlot(Base):
    __tablename__ = "interview_slots"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=60)
    meeting_link = Column(String(500), nullable=True)

    status = Column(SAEnum(InterviewStatus), default=InterviewStatus.booked)
    interviewer_notes = Column(Text, nullable=True)
    interview_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=_utc_now)

    # relationships
    candidate = relationship("Candidate", back_populates="interview_slots")
    job = relationship("JobRequest")


# ── 10. Pipeline Stage Logs (Audit trail) ─────────────

class PipelineStageLog(Base):
    __tablename__ = "pipeline_stage_logs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=False)

    from_stage = Column(String(50), nullable=True)
    to_stage = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = automated
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime, default=_utc_now)

    # relationships
    candidate = relationship("Candidate", back_populates="stage_logs")
    job = relationship("JobRequest", back_populates="stage_logs")
    user = relationship("User")


# ── 11. Notifications ─────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(SAEnum(NotificationType), default=NotificationType.general)
    is_read = Column(Boolean, default=False)
    related_job_id = Column(Integer, ForeignKey("job_requests.id"), nullable=True)
    related_candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=True)
    created_at = Column(DateTime, default=_utc_now)

    # relationships
    user = relationship("User", back_populates="notifications")
    job = relationship("JobRequest")
    candidate = relationship("Candidate")


# ── 12. JD Form Data (saved intake forms for JD generation) ──

class JDFormData(Base):
    __tablename__ = "jd_form_data"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(255), nullable=False)
    department = Column(String(120), nullable=False)
    location = Column(String(120), nullable=True)
    employment_type = Column(String(50), default="Full-time")
    work_mode = Column(String(50), nullable=True)
    travel_required = Column(String(50), nullable=True)
    reporting_to = Column(String(200), nullable=True)
    experience = Column(String(100), nullable=True)
    minimum_education = Column(String(200), nullable=True)
    salary = Column(String(100), nullable=True)
    urgency = Column(String(50), nullable=True)
    new_or_scaling = Column(String(100), nullable=True)
    must_have_skills = Column(Text, nullable=True)
    other_skills = Column(Text, nullable=True)
    key_responsibilities = Column(Text, nullable=True)
    generated_jd = Column(Text, nullable=True)
    generated_profile = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utc_now)

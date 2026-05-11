# app/agents/jd_generator.py
# Agent 3: JD Generator
# Generates a professional JD using the Profile Builder output as ground truth

import sys
import os
import re
from typing import Dict

# --------------------------------------------------
# Project path setup
# --------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --------------------------------------------------
# Imports
# --------------------------------------------------
try:
    from app.utils.llm import invoke_llm
    from app.utils.constants import ABOUT_WOGOM_TEXT, WOGOM_BRAND
except ImportError as e:
    print(f"[JD_GENERATOR] Warning: {e}")
    ABOUT_WOGOM_TEXT = "About WOGOM information unavailable."
    WOGOM_BRAND = {}

    def invoke_llm(prompt):
        class MockResponse:
            content = f"Mock JD generated for prompt: {prompt[:160]}..."
        return MockResponse()


# --------------------------------------------------
# Helper
# --------------------------------------------------
def _format_experience(exp_raw: str) -> str:
    """Return a human-friendly experience phrase."""
    if not exp_raw:
        return "Not specified"

    s = str(exp_raw).strip()
    s_lower = s.lower()

    m_range = re.search(r'(\d+\s*[-–]\s*\d+)', s)
    if m_range:
        span = m_range.group(1).replace(" ", "")
        return f"Approximately {span} years" if "year" not in s_lower else f"Approximately {span}"

    m_num = re.search(r'(\d+)\+?', s)
    if m_num:
        val = m_num.group(1)
        if "year" in s_lower:
            return f"Relevant experience of {val} years or equivalent"

    return s


# --------------------------------------------------
# Prompt (uses Profile Builder output)
# --------------------------------------------------
JD_GENERATOR_PROMPT = """
You are a senior HR and talent acquisition expert at WOGOM.

Your task is to generate a clean, professional, hiring-ready Job Description (JD).

─────────────────────────────
🔴 CRITICAL SOURCE OF TRUTH 🔴
─────────────────────────────
The **IDEAL CANDIDATE PROFILE** below is your **SINGLE SOURCE OF TRUTH**.
- You MUST use the exact content from this profile (responsibilities, skills, traits).
- The Google Form data is ONLY for metadata (Location, CTC, etc.).
- If the Form data contradicts the Profile, **IGNORE THE FORM DATA**.
- Do NOT hallucinate or invent new requirements.

─────────────────────────────
IDEAL CANDIDATE PROFILE (PRIMARY)
─────────────────────────────
{profile_json}

─────────────────────────────
METADATA & CONTEXT
─────────────────────────────
Role: {role}
Department: {department}
Location: {location}
Experience: {experience_phrase}
Employment Type: {employment_type}

GOOGLE FORM DATA (SECONDARY - Metadata Only):
{facts}

─────────────────────────────
COMPANY BRAND GUIDELINES
─────────────────────────────
Mission: {mission}
Vision: {vision}
Tone: {tone}
Culture: {culture}
Language Rules: {language_rules}

─────────────────────────────
OUTPUT FORMAT (STRICTLY FOLLOW)
─────────────────────────────

# {role}

**Location:** {location}
**Type:** {employment_type}

## About Us
Use the provided About WOGOM content exactly as given. Do not rewrite it.

{about_wogom}

## Role Overview
Write 2–3 concise sentences explaining:
- The purpose of the role
- Its direct impact on WOGOM’s mission
Base this **ONLY** on the `profile_summary` from the Profile.

## Key Responsibilities
Use **ONLY** `key_responsibilities_refined` from the Profile.
Write 5–7 bullet points.

STRICT BULLET RULES:
- **ONE LINE ONLY** per bullet.
- **MAXIMUM 30 words** per bullet.
- Start with "• "
- Focus on outcomes and ownership.
- Do NOT use multiple sentences in one bullet.
- Do NOT use sub-bullets.

## Requirements

### Must-Have Skills
Use **ONLY** `must_have_skills_refined` and `core_competencies` from the Profile.
Write 4–6 bullet points.

STRICT BULLET RULES:
- **ONE LINE ONLY** per bullet.
- Start with "• "
- explain proficiency level briefly.

### Nice-to-Have Skills
Use **ONLY** `nice_to_have_skills` from the Profile.
Write 2–3 concise bullet points.

STRICT BULLET RULES:
- **ONE LINE ONLY** per bullet.

## Who Will Succeed in This Role
Use **ONLY**:
- `behavioral_traits`
- `success_metrics`

Write 2–3 sentences describing the mindset and work ethic required. Do NOT repeat earlier content.

─────────────────────────────
FINAL CHECKLIST
─────────────────────────────
- Did you use the Profile as the source of truth?
- Are all bullets SINGLE LINE?
- Is the tone professional?
- Output ONLY the formatted JD.
"""


# --------------------------------------------------
# Normalize bullets
# --------------------------------------------------
def normalize_bullets(text: str) -> str:
    """Normalize all bullet styles to standard markdown `- ` for proper rendering."""
    lines = []
    for line in text.splitlines():
        line = line.rstrip()
        stripped = line.lstrip()
        if stripped.startswith(("-", "*")) and not stripped.startswith(("##", "#", "---", "***")):
            content = stripped.lstrip("-* ").strip()
            lines.append("- " + content)
            continue
        if stripped.startswith("•"):
            content = stripped.lstrip("• ").strip()
            lines.append("- " + content)
            continue
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------
# JD GENERATOR (MAIN AGENT)
# --------------------------------------------------
def generate_jd(form_data: Dict, profile: Dict = None) -> str:
    """
    Agent 3: Generates a hiring-ready JD.

    Args:
        form_data: dict from Google Form (role, department, skills, etc.)
        profile: dict from Profile Builder (Agent 2). If None, falls back to form_data only.

    Returns:
        str: The generated JD text in markdown format.
    """
    import json

    data = form_data.copy()

    # Required fields
    REQUIRED_FIELDS = ["role", "employment_type"]
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        raise ValueError(f"Missing required JD fields: {missing}")

    # Defaults
    data["ctc"] = data.get("salary") or "As per company standards"
    data["location"] = data.get("location") or "India"
    data["joining_time"] = data.get("joining_time") or "As per company requirement"
    data["reporting_to"] = data.get("reporting_to") or "Reporting Manager"

    # Build facts block
    facts_lines = []
    keys_for_facts = [
        "role", "department", "location", "experience", "employment_type",
        "work_mode", "travel_required", "reporting_to", "salary", "urgency",
        "must_have_skills", "other_skills", "key_responsibilities", "minimum_education"
    ]
    for key in keys_for_facts:
        val = data.get(key)
        if val:
            if isinstance(val, list):
                facts_lines.append(f"{key}: {', '.join(val)}")
            else:
                facts_lines.append(f"{key}: {val}")

    for key, value in data.items():
        if key not in keys_for_facts and value:
            if isinstance(value, list):
                facts_lines.append(f"{key}: {', '.join(value)}")
            else:
                facts_lines.append(f"{key}: {value}")

    facts = "\n".join(facts_lines)
    if not facts.strip():
        raise ValueError("FACTS block is empty — Google Form data not loaded")

    # Brand pieces
    mission = WOGOM_BRAND.get("mission", "")
    vision = WOGOM_BRAND.get("vision", "")
    tone = WOGOM_BRAND.get("tone", "")
    culture = ", ".join(WOGOM_BRAND.get("culture", []))
    language_rules = ", ".join(WOGOM_BRAND.get("language_rules", []))

    # Experience
    experience_phrase = _format_experience(data.get("experience", ""))
    # Intent summary from form data
    intent_summary = data.get("intent_summary", "Generate a professional, concise JD for this role.")

    # Prepare facts (Google Form Data)
    # If a profile exists, we want to HIDE conflicts (responsibilities, skills) from the raw form data
    # and only show metadata (CTC, Notice Period, etc.)
    if profile:
        excluded_keys = [
            "role", "department", "experience", "key_responsibilities",
            "must_have_skills", "nice_to_have_skills", "other_skills",
            "profile_summary"
        ]
        facts_list = []
        for k, v in data.items():
            if k not in excluded_keys and v:
                if isinstance(v, list):
                    facts_list.append(f"{k}: {', '.join(v)}")
                else:
                    facts_list.append(f"{k}: {v}")
        facts = "\n".join(facts_list) if facts_list else "(No additional metadata)"
    else:
        # Fallback: show everything if no profile
        facts_list = []
        for k, v in data.items():
            if k not in ["role", "department", "experience"] and v:
                if isinstance(v, list):
                    facts_list.append(f"{k}: {', '.join(v)}")
                else:
                    facts_list.append(f"{k}: {v}")
        facts = "\n".join(facts_list) if facts_list else "(No additional metadata)"

    # Profile JSON (from Agent 2)
    print(f"\n[JD_GENERATOR DEBUG] Received Profile: {json.dumps(profile, indent=2)}")
    profile_json = json.dumps(profile, indent=2) if profile else "{}"

    prompt = JD_GENERATOR_PROMPT.format(
        mission=mission,
        vision=vision,
        tone=tone,
        culture=culture,
        language_rules=language_rules,
        role=data["role"],
        department=data.get("department", ""),
        location=data["location"],
        experience_phrase=experience_phrase,
        employment_type=data["employment_type"],
        about_wogom=ABOUT_WOGOM_TEXT.strip(),
        profile_json=profile_json,
        facts=facts
    )

    # LLM call
    response = invoke_llm(prompt)
    content = response.content

    if isinstance(content, list):
        content = "\n".join(
            part.get("text", str(part))
            if isinstance(part, dict)
            else str(part)
            for part in content
        )

    content = normalize_bullets(content)
    return content.strip()

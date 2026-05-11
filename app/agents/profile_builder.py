# app/agents/profile_builder.py
# Agent 2: Profile Builder
# Synthesizes Google Form data + Clarifying Answers → Ideal Candidate Profile

import json
from app.utils.llm import invoke_llm

PROFILE_BUILDER_PROMPT = """
You are a senior HR strategist building an "Ideal Candidate Profile" for the role of **{role}** in the **{department}** department.

You are given:
1. Raw job data collected from a Google Form (ground truth).
2. Clarifying answers given by the Department Head.

YOUR TASK:
Build a structured candidate profile that will later be used to write a Job Description.

INPUTS:
─────────────────────────────
GOOGLE FORM DATA (Ground Truth):
{form_data}

CLARIFICATION ANSWERS (from Dept. Head):
{clarification_answers}
─────────────────────────────

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "role": "{role}",
  "department": "{department}",
  "profile_summary": "2–3 sentence paragraph: Who is the ideal person for this role? What mindset and background do they bring?",
  "core_competencies": [
    "Competency 1: brief explanation of why it matters",
    "Competency 2: brief explanation of why it matters",
    "Competency 3: brief explanation of why it matters"
  ],
  "behavioral_traits": [
    "Trait 1: why it's relevant to this role",
    "Trait 2: why it's relevant to this role"
  ],
  "success_metrics": [
    "What does success look like in 30 days?",
    "What does success look like in 90 days?",
    "What does success look like in 6 months?"
  ],
  "team_context": "1–2 sentences: Who does this person work with? What's the team dynamic?",
  "key_responsibilities_refined": [
    "Responsibility derived from form data + clarification",
    "..."
  ],
  "must_have_skills_refined": [
    "Skill from form data, refined with head's input"
  ],
  "nice_to_have_skills": [
    "Additional skills inferred from clarification answers"
  ]
}}

RULES:
- Output ONLY valid JSON. No markdown, no explanations.
- Use the Google Form data as the primary source.
- Use the clarification answers to add depth and specificity.
- Do NOT invent information not supported by the inputs.
- Keep language professional and specific to the role.
"""


def build_profile(form_data: dict, clarification_answers: list) -> dict:
    """
    Agent 2: Profile Builder

    Takes raw Google Form data and the user's clarification answers,
    and produces a structured "Ideal Candidate Profile" dict.

    Args:
        form_data: dict from Google Form (role, department, skills, etc.)
        clarification_answers: list of dicts with {id, question, answer, target_section}

    Returns:
        dict: The structured ideal candidate profile.
    """
    role = form_data.get("role", "Unknown Role")
    department = form_data.get("department", "General")

    # Clean answers: remove "Not Applicable" selections
    cleaned_answers = []
    for a in clarification_answers:
        raw = a.get("answer", [])
        if isinstance(raw, str):
            raw = [raw]
        filtered = [opt for opt in raw if opt.lower() != "not applicable"]
        if filtered:
            cleaned_answers.append({
                "question": a.get("question", ""),
                "answer": filtered,
                "target_section": a.get("target_section", "")
            })

    prompt = PROFILE_BUILDER_PROMPT.format(
        role=role,
        department=department,
        form_data=json.dumps(form_data, indent=2),
        clarification_answers=json.dumps(cleaned_answers, indent=2)
    )

    try:
        response = invoke_llm(prompt)
        content = response.content

        # Handle list responses from some LLM providers
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", str(part))
                if isinstance(part, dict)
                else str(part)
                for part in content
            )

        # Extract JSON from the response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        profile = json.loads(content)
        return profile

    except json.JSONDecodeError as e:
        print(f"[PROFILE_BUILDER] JSON parse error: {e}")
        # Return a minimal fallback profile
        return {
            "role": role,
            "department": department,
            "profile_summary": f"Profile for {role} in {department} department.",
            "core_competencies": form_data.get("must_have_skills", "").split(", ") if isinstance(form_data.get("must_have_skills"), str) else [],
            "behavioral_traits": [],
            "success_metrics": [],
            "team_context": "",
            "key_responsibilities_refined": form_data.get("key_responsibilities", "").split(", ") if isinstance(form_data.get("key_responsibilities"), str) else [],
            "must_have_skills_refined": form_data.get("must_have_skills", "").split(", ") if isinstance(form_data.get("must_have_skills"), str) else [],
            "nice_to_have_skills": form_data.get("other_skills", "").split(", ") if isinstance(form_data.get("other_skills"), str) else []
        }
    except Exception as e:
        print(f"[PROFILE_BUILDER] Unexpected error: {e}")
        return {
            "role": role,
            "department": department,
            "profile_summary": f"Profile for {role} in {department}.",
            "core_competencies": [],
            "behavioral_traits": [],
            "success_metrics": [],
            "team_context": "",
            "key_responsibilities_refined": [],
            "must_have_skills_refined": [],
            "nice_to_have_skills": []
        }

import json
from typing import Dict, List
from app.utils.llm import invoke_llm


SKILL_EXTRACTION_PROMPT = """
You are an expert resume analyst.

Given the resume text below, extract skills that are:
- Explicitly mentioned
- Implicitly demonstrated through experience

Group them into a structured JSON with this schema:

{{
  "core_skills": [],
  "tools": [],
  "domain_skills": []
}}

Rules:
- Do NOT invent skills
- Normalize names (e.g. "GA" → "Google Analytics")
- Keep skills concise (2–4 words max)
- Return ONLY valid JSON

Resume Text:
{resume_text}
"""


def extract_skills_llm(
    resume_text: str,
    role_context: str | None = None
) -> Dict[str, List[str]]:
    """
    Extracts structured skills using LLM.
    Optionally conditions extraction on job role.
    """

    prompt = SKILL_EXTRACTION_PROMPT
    if role_context:
        prompt = (
            f"Target Job Role: {role_context}\n\n" + prompt
        )

    response = invoke_llm(prompt.format(resume_text=resume_text))

    # LangChain returns AIMessage, not string
    text = response.content.strip()
    text = text.replace("```json", "").replace("```", "")

    try:
        skills = json.loads(text)
    except Exception:
        # Fail-safe: never break pipeline
        skills = {
            "core_skills": [],
            "tools": [],
            "domain_skills": []
        }

    return skills


def extract_section(text: str, keywords: List[str]) -> str:
    """
    Heuristic section extraction (experience/projects/etc.)
    """
    lines = text.splitlines()
    collected = []
    capture = False

    for line in lines:
        lower = line.lower()

        if any(k in lower for k in keywords):
            capture = True
            continue

        if capture:
            if not lower.strip():
                break
            collected.append(line)

    return "\n".join(collected).strip()

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


def extract_location(text: str) -> str:
    """Extract candidate location from resume text using regex — no LLM call."""
    import re
    lines = text.splitlines()
    skip = {'university', 'college', 'institute', 'company', 'corporation', 'ltd', 'inc', 'pvt', 'school'}

    # Pass 1: explicit label anywhere in first 30 lines
    label_re = re.compile(
        r'(?:location|address|city|based\s+in|residing\s+in)[:\s]+([^\n|•]+)',
        re.IGNORECASE,
    )
    for line in lines[:30]:
        m = label_re.search(line.strip())
        if m:
            val = m.group(1).strip().rstrip('|•–-,').strip()
            if val and len(val) < 80:
                return val

    # Pass 2: "City, State/Country" pattern anywhere within a line (handles pipe-separated headers)
    city_re = re.compile(r'([A-Za-z][A-Za-z\s\-]{1,25}),\s*([A-Za-z][A-Za-z\s\-]{1,25})')
    for line in lines[:25]:
        line = line.strip()
        if not line or any(w in line.lower() for w in skip):
            continue
        # Split on common separators to isolate segments
        segments = re.split(r'[|•\-–/]', line)
        for seg in segments:
            seg = seg.strip()
            m = city_re.fullmatch(seg) or city_re.match(seg)
            if m:
                # Reject if segment looks like a name or email
                if '@' in seg or re.search(r'\d', seg):
                    continue
                return seg.strip()

    # Pass 3: look for "Remote" anywhere in first 30 lines
    for line in lines[:30]:
        if re.search(r'\bremote\b', line, re.IGNORECASE):
            return 'Remote'

    return ''


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

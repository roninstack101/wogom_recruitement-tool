import json
from typing import Dict, List
from app.utils.llm import invoke_llm, invoke_gemini_location


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


_STATES = {
    'maharashtra', 'gujarat', 'karnataka', 'tamil nadu', 'rajasthan',
    'uttar pradesh', 'delhi', 'new delhi', 'punjab', 'haryana',
    'west bengal', 'telangana', 'andhra pradesh', 'kerala', 'madhya pradesh',
    'bihar', 'odisha', 'assam', 'jharkhand', 'uttarakhand', 'himachal pradesh',
    'goa', 'chhattisgarh', 'chandigarh', 'jammu', 'kashmir',
}
_COUNTRIES = {
    'india', 'usa', 'us', 'uk', 'united states', 'united kingdom',
    'canada', 'australia', 'uae', 'singapore', 'germany', 'france',
}
_KNOWN = _STATES | _COUNTRIES


def extract_location_llm(text: str) -> str:
    """Extract location using Gemini Flash Lite on the CV header. Falls back to regex."""
    header = text[:600]
    prompt = (
        "Extract the candidate's current city and state/country from the resume header below.\n"
        "Return ONLY the location as plain text e.g. 'Mumbai, Maharashtra' or 'Surat, Gujarat'.\n"
        "If no city/address is clearly present, return exactly empty string: ''\n"
        "Do NOT guess. Do NOT return skills, technologies, or company names.\n\n"
        f"RESUME HEADER:\n{header}\n\nLOCATION:"
    )
    result = invoke_gemini_location(prompt).strip().strip('"').strip("'")
    if result and len(result) < 60 and not any(c.isdigit() for c in result):
        return result
    return extract_location(text)


def extract_location(text: str) -> str:
    """Extract candidate location from resume text using regex — no LLM call."""
    import re
    lines = text.splitlines()

    # Pass 1: explicit label in first 30 lines
    label_re = re.compile(
        r'(?:location|address|city|based\s+in|residing\s+in)[:\s]+([^\n|•]+)',
        re.IGNORECASE,
    )
    for line in lines[:30]:
        m = label_re.search(line.strip())
        if m:
            val = m.group(1).strip().rstrip('|•–-,').strip()
            if val and len(val) < 80 and not re.search(r'\d{4,}', val):
                return val

    # Pass 2: look for "City, State/Country" where State/Country is a known place
    city_re = re.compile(r'([A-Za-z][A-Za-z\s\-]{1,25}),\s*([A-Za-z][A-Za-z\s\-]{1,30})')
    for line in lines[:25]:
        if not line.strip() or '@' in line:
            continue
        segments = re.split(r'[|•–/]', line)
        for seg in segments:
            seg = seg.strip()
            if not seg or re.search(r'\d', seg):
                continue
            m = city_re.search(seg)
            if m:
                state_or_country = m.group(2).strip().lower()
                if state_or_country in _KNOWN:
                    return f"{m.group(1).strip()}, {m.group(2).strip()}"

    # Pass 3: just a known state/country name on its own in first 20 lines
    for line in lines[:20]:
        clean = line.strip().lower()
        if clean in _KNOWN:
            return line.strip()

    # Pass 4: Remote
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

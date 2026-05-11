#jd parser
import re
import json
from typing import List, Dict
from app.utils.llm import invoke_llm

# ----------------------------
# Helper functions (deterministic)
# ----------------------------

def _extract_section(text: str, start: str, stop_keywords: List[str]) -> str:
    pattern = rf"{start}(.*?)(?={'|'.join(stop_keywords)}|$)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""

def _extract_bullets(section_text: str) -> List[str]:
    bullets = re.findall(r"[•\-]\s*(.+)", section_text)
    return [b.strip() for b in bullets if b.strip()]

# ----------------------------
# LLM prompt (EXTRACTION ONLY)
# ----------------------------

JD_PARSER_PROMPT = """
You are an information extraction system.
Extract structured data from the Job Description below.

Return ONLY valid JSON in this schema:
{
  "role": string,
  "must_have_skills": list of strings,
  "nice_to_have_skills": list of strings,
  "experience_years": number,
  "responsibilities": list of strings
}

Job Description:
{jd_text}
"""

# ----------------------------
# FINAL AGENT (single source)
# ----------------------------

def jd_parser(state: Dict) -> Dict:
    text = state["jd_text"]

    # --------- Regex-based extraction ---------
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    role = lines[0] if lines else None

    location = re.search(r"Location:\s*(.+)", text, re.IGNORECASE)
    experience = re.search(r"Experience:\s*(\d+)\+?", text, re.IGNORECASE)
    employment = re.search(r"Employment Type:\s*(.+)", text, re.IGNORECASE)
    company_match = re.search(r"About\s+([A-Za-z0-9& ]+)", text)

    responsibilities_text = _extract_section(
        text,
        "What You'll Do",
        ["Who Will Succeed", "Must-Have Skills", "Preferred Skills"]
    )

    must_have_text = _extract_section(
        text,
        "Must-Have Skills",
        ["Preferred Skills"]
    )

    preferred_text = _extract_section(
        text,
        "Preferred Skills",
        []
    )

    parsed = {
        "role": role,
        "location": location.group(1).strip() if location else None,
        "experience_years": int(experience.group(1)) if experience else None,
        "employment_type": employment.group(1).strip() if employment else None,
        "company": company_match.group(1).strip() if company_match else None,
        "responsibilities": _extract_bullets(responsibilities_text),
        "must_have_skills": _extract_bullets(must_have_text),
        "preferred_skills": _extract_bullets(preferred_text),
    }

    # --------- LLM fallback ---------
    critical_missing = (
        not parsed["role"]
        or not parsed["must_have_skills"]
        or parsed["experience_years"] is None
    )

    if critical_missing:
        response = invoke_llm(JD_PARSER_PROMPT.format(jd_text=text))
        llm_parsed = json.loads(response.content)

        for key, value in llm_parsed.items():
            if not parsed.get(key):
                parsed[key] = value

    state["parsed_jd"] = parsed
    return state

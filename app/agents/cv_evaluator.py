# app/agents/cv_evaluator.py
# Agent 7: CV Evaluator — optimized batch version

import json
from app.utils.llm import invoke_llm

# Single prompt evaluates one CV against ALL personas at once.
# Previously this was P separate calls per CV — now it's 1.
CV_BATCH_PROMPT = """
You are an expert technical interviewer and hiring evaluator.

You are given a candidate's CV and a list of ideal candidate personas.
Evaluate the CV against EACH persona independently.

SCORING DIMENSIONS (for each persona):
- Skill Match: Do their skills align with required skills?
- Experience Fit: Years and depth vs. persona expectation
- Responsibility Match: Have they done similar work?
- Behavioral Signals: Ownership, leadership, initiative
- Domain Fit: Industry or domain relevance
- Risk Flags: Job hopping, shallow roles, gaps

Score each from 0 to 100.

INPUTS:
─────────────────────────────
CANDIDATE CV:
{cv}

PERSONAS:
{personas}
─────────────────────────────

OUTPUT FORMAT (STRICT JSON OBJECT):
{{
  "location": "<city, state/country extracted from CV — empty string if not found>",
  "results": [
    {{
      "persona_id": "<id from input>",
      "score": <integer 0–100>,
      "grade": "<A+ / A / A- / B+ / B / B- / C+ / C / C- / D / F>",
      "strengths": ["Strength 1", "Strength 2"],
      "gaps": ["Gap 1", "Gap 2"],
      "explanation": "2–3 sentence summary of the fit"
    }}
  ]
}}

RULES:
- Be strict but fair. Do not inflate scores.
- Cite specific evidence from the CV.
- Output ONLY a valid JSON object. No markdown, no extra text.
"""


def _parse_llm_json(content) -> dict:
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", str(part)) if isinstance(part, dict) else str(part)
            for part in content
        )
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    parsed = json.loads(content)
    # Support legacy plain array response
    if isinstance(parsed, list):
        return {"location": "", "results": parsed}
    return parsed


def _compute_grade(score: int) -> str:
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


def _fallback_results(personas: list) -> list:
    return [
        {
            "persona_id": p.get("persona_id", f"P{i+1}"),
            "score": 0,
            "grade": "F",
            "strengths": [],
            "gaps": ["Evaluation failed — LLM response could not be parsed"],
            "explanation": "Evaluation could not be completed.",
        }
        for i, p in enumerate(personas)
    ]


def evaluate_candidate(cv: dict, personas: list) -> dict:
    """
    Evaluate one CV against all personas in a single LLM call.
    Optimization: was P separate calls, now 1 call regardless of persona count.
    """
    cv_for_prompt = {
        "candidate_id": cv.get("candidate_id", "unknown"),
        "summary": cv.get("summary", ""),
        "skills": cv.get("skills", {}),
        "experience": cv.get("experience", ""),
        "projects": cv.get("projects", ""),
        "raw_text": cv.get("raw_text", "")[:3000],
    }

    prompt = CV_BATCH_PROMPT.format(
        cv=json.dumps(cv_for_prompt, indent=2),
        personas=json.dumps(personas, indent=2),
    )

    llm_location = ""
    try:
        response = invoke_llm(prompt)
        parsed = _parse_llm_json(response.content)
        llm_location = parsed.get("location", "")
        persona_results = parsed.get("results", [])

        for i, result in enumerate(persona_results):
            if i < len(personas):
                result["persona_id"] = personas[i].get("persona_id", f"P{i+1}")

    except Exception as e:
        print(f"[CV_EVALUATOR] Error for {cv.get('candidate_id')}: {e}")
        persona_results = _fallback_results(personas)

    scores = [r["score"] for r in persona_results]
    best = max(persona_results, key=lambda x: x["score"])
    avg_score = int(sum(scores) / len(scores)) if scores else 0

    return {
        "candidate_id": cv.get("candidate_id", "unknown"),
        "location": llm_location or cv.get("location", ""),
        "persona_results": persona_results,
        "overall_score": avg_score,
        "overall_grade": _compute_grade(avg_score),
        "best_fit_persona": best["persona_id"],
        "best_fit_persona_name": next(
            (p.get("name", best["persona_id"]) for p in personas
             if p["persona_id"] == best["persona_id"]),
            best["persona_id"],
        ),
        "summary": best.get("explanation", "No explanation available."),
    }

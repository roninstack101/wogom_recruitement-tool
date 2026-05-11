# app/agents/persona_builder.py
# Agent 6: Persona Builder
# Generates multiple ideal candidate personas from the role profile

import json
from app.utils.llm import invoke_llm

PERSONA_BUILDER_PROMPT = """
You are a senior hiring strategist.

You are given an Ideal Candidate Profile for a role.
Your task is to create 3–5 DISTINCT ideal candidate personas — each representing a DIFFERENT type of person who could succeed in this role.

These personas will later be used to evaluate real candidate CVs, so they must be specific and actionable.

INPUT:
─────────────────────────────
IDEAL CANDIDATE PROFILE:
{profile}
─────────────────────────────

OUTPUT FORMAT (STRICT JSON ARRAY):
[
  {{
    "persona_id": "P1",
    "name": "Short Persona Title (e.g. 'The Scalable Systems Expert')",
    "summary": "2–3 sentence description of who this persona is and why they'd succeed",
    "experience_range": "X–Y years",
    "core_strengths": [
      "Strength 1: why it matters for this role",
      "Strength 2: why it matters for this role",
      "Strength 3: why it matters for this role"
    ],
    "required_skills": ["Skill 1", "Skill 2", "Skill 3"],
    "nice_to_have_skills": ["Skill 1", "Skill 2"],
    "behavioral_traits": [
      "Trait 1: why it's relevant",
      "Trait 2: why it's relevant"
    ],
    "red_flags": [
      "Warning sign 1 that would disqualify this persona type",
      "Warning sign 2"
    ],
    "success_definition": "What does success look like for this persona in 6 months?"
  }}
]

RULES:
- Create 3–5 personas. Each must represent a DIFFERENT hiring path (e.g. deep specialist vs generalist vs high-potential learner).
- Use ONLY information from the given profile. Do NOT hallucinate.
- Each persona should have different experience ranges and strengths.
- Output ONLY valid JSON array. No markdown, no explanations, no wrapping.
"""


def build_personas(profile) -> list:
    """
    Agent 6: Persona Builder

    Takes the ideal candidate profile and generates 3–5 distinct
    ideal candidate personas.

    Args:
        profile: str or dict — either a plain-text role description
                 or a structured profile dict from build_profile()

    Returns:
        list of persona dicts
    """
    # Accept both string and dict inputs
    if isinstance(profile, str):
        profile_text = profile
    else:
        profile_text = json.dumps(profile, indent=2)

    prompt = PERSONA_BUILDER_PROMPT.format(profile=profile_text)

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

        personas = json.loads(content)

        # Ensure stable IDs
        for i, p in enumerate(personas):
            p["persona_id"] = f"P{i + 1}"

        return personas

    except json.JSONDecodeError as e:
        print(f"[PERSONA_BUILDER] JSON parse error: {e}")
        if isinstance(profile, dict):
            role = profile.get("role", "Unknown Role")
            return [{
                "persona_id": "P1",
                "name": f"Core {role} Candidate",
                "summary": profile.get("profile_summary", f"Ideal candidate for {role}"),
                "experience_range": "3–6 years",
                "core_strengths": profile.get("core_competencies", [])[:3],
                "required_skills": profile.get("must_have_skills_refined", []),
                "nice_to_have_skills": profile.get("nice_to_have_skills", []),
                "behavioral_traits": profile.get("behavioral_traits", [])[:2],
                "red_flags": ["Lack of relevant experience"],
                "success_definition": (profile.get("success_metrics", ["Delivers on role expectations"]))[-1]
            }]
        return [{
            "persona_id": "P1",
            "name": "General Candidate",
            "summary": f"Candidate for the described role.",
            "experience_range": "3–6 years",
            "core_strengths": [],
            "required_skills": [],
            "nice_to_have_skills": [],
            "behavioral_traits": [],
            "red_flags": [],
            "success_definition": "Meets basic role requirements"
        }]

    except Exception as e:
        print(f"[PERSONA_BUILDER] Unexpected error: {e}")
        return [{
            "persona_id": "P1",
            "name": "General Candidate",
            "summary": "Fallback persona due to generation error.",
            "experience_range": "Any",
            "core_strengths": [],
            "required_skills": [],
            "nice_to_have_skills": [],
            "behavioral_traits": [],
            "red_flags": [],
            "success_definition": "Meets basic role requirements"
        }]

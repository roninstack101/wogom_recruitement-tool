# app/agents/role_suggester.py
# Suggests alternative job role names based on the generated profile

import json
from app.utils.llm import invoke_llm

ROLE_SUGGESTER_PROMPT = """
You are a senior HR naming specialist.

Given the Ideal Candidate Profile below, suggest **5 to 7 professional job role titles** that accurately describe the position.

RULES:
1. The FIRST title in your list MUST be the original role name from the profile.
2. Each alternative title must be realistic, industry-standard, and commonly used on job boards.
3. Titles should vary in seniority language (e.g., "Lead", "Senior", "Specialist", "Analyst").
4. Do NOT invent fantasy titles. Stick to real-world job titles.
5. Keep titles concise (2–5 words).
6. Output ONLY a valid JSON array of strings. No markdown, no explanations.

PROFILE:
{profile_json}

OUTPUT FORMAT (STRICT):
["Original Role Title", "Alternative 1", "Alternative 2", "Alternative 3", "Alternative 4", "Alternative 5"]
"""


def suggest_roles(profile: dict, instruction: str = None) -> list:
    """
    Takes a profile dict and returns a list of 5–7 suggested role names.
    The first entry is always the original role from the profile.
    If instruction is provided, it guides the style/focus of suggestions.
    """
    original_role = profile.get("role", "Unknown Role")

    refinement_text = ""
    if instruction:
        refinement_text = f"\nUSER INSTRUCTION: {instruction}\nAdjust the suggestions based on this instruction."

    prompt = ROLE_SUGGESTER_PROMPT.format(
        profile_json=json.dumps(profile, indent=2)
    ) + refinement_text

    try:
        response = invoke_llm(prompt)
        content = response.content

        if isinstance(content, list):
            content = "\n".join(
                part.get("text", str(part))
                if isinstance(part, dict)
                else str(part)
                for part in content
            )

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        suggestions = json.loads(content)

        if isinstance(suggestions, list) and len(suggestions) > 0:
            # Ensure original role is first
            if original_role not in suggestions:
                suggestions.insert(0, original_role)
            elif suggestions[0] != original_role:
                suggestions.remove(original_role)
                suggestions.insert(0, original_role)
            return suggestions[:7]

    except (json.JSONDecodeError, Exception) as e:
        print(f"[ROLE_SUGGESTER] Error: {e}")

    # Fallback: return original role + generic alternatives
    return [
        original_role,
        f"Senior {original_role}",
        f"{original_role} Specialist",
        f"{original_role} Lead",
        f"{original_role} Analyst",
    ]

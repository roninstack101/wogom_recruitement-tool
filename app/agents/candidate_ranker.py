# app/agents/candidate_ranker.py
# Agent 8: Candidate Ranker
# Takes all evaluations and produces a balanced top-N shortlist

from typing import List


def rank_candidates(evaluations: List[dict], top_n: int = 10) -> dict:
    """
    Agent 8: Candidate Ranker

    Ranks all evaluated candidates and returns a balanced top-N shortlist.
    Applies persona diversity capping so no single persona dominates.

    Args:
        evaluations: list of dicts from Agent 7's evaluate_candidate()
        top_n: how many candidates to shortlist (default 10)

    Returns:
        dict with 'shortlist' (list) and 'notes' (str)
    """
    if not evaluations:
        return {
            "shortlist": [],
            "total_evaluated": 0,
            "persona_distribution": {},
            "notes": "No candidates were evaluated."
        }

    # Sort by overall score descending
    sorted_candidates = sorted(
        evaluations,
        key=lambda x: x.get("overall_score", 0),
        reverse=True
    )

    shortlisted = []
    persona_count = {}

    # Max candidates per persona to ensure diversity
    max_per_persona = max(4, top_n // 2)

    for candidate in sorted_candidates:
        persona = candidate.get("best_fit_persona", "unknown")
        persona_count.setdefault(persona, 0)

        # Skip if this persona is already over-represented
        if persona_count[persona] >= max_per_persona:
            continue

        shortlisted.append({
            "rank": len(shortlisted) + 1,
            "candidate_id": candidate["candidate_id"],
            "persona": persona,
            "persona_name": candidate.get("best_fit_persona_name", persona),
            "score": candidate["overall_score"],
            "grade": candidate["overall_grade"],
            "why": candidate.get("summary", ""),
            "persona_results": candidate.get("persona_results", [])
        })

        persona_count[persona] += 1

        if len(shortlisted) >= top_n:
            break

    # Build persona distribution summary
    distribution = {}
    for entry in shortlisted:
        name = entry["persona_name"]
        distribution[name] = distribution.get(name, 0) + 1

    return {
        "shortlist": shortlisted,
        "total_evaluated": len(evaluations),
        "persona_distribution": distribution,
        "notes": (
            f"Top {len(shortlisted)} candidates selected from "
            f"{len(evaluations)} evaluated. "
            f"Balanced across {len(distribution)} persona type(s)."
        )
    }

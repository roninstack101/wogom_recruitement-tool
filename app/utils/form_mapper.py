#form_mapper.py

def map_form_row_to_jd_input(row: dict) -> dict:
    """
    Converts Google Form row into AUTHORITATIVE JD FACTS.
    These values MUST NOT be overridden by the LLM.
    """

    def split_lines(value: str):
        if not value:
            return []
        return [v.strip() for v in value.split("\n") if v.strip()]

    return {
        # ─────────────────────────────
        # CORE JD FACTS
        # ─────────────────────────────
        "role": row.get("Job Title", "").strip(),
        "location": row.get("Location", "").strip(),
        "employment_type": row.get(
            "Employment Type ( Full-time / Contract / Internship )", ""
        ).strip(),
        "experience": row.get("Minimum experience required", "").strip(),
        "ctc": row.get("Salary range (optional)", "").strip()
               or "As per company standards",
        "joining_time": row.get("How urgent is this hire?", "").strip()
                        or "Immediate / Within 30 Days",
        "reporting_to": row.get("Reporting To", "").strip()
                        or "Reporting Manager",

        # ─────────────────────────────
        # ROLE GUARDRAILS (ANTI-HALLUCINATION)
        # ─────────────────────────────
        "audience_type": "Internal Employees",  # 🔒 LOCKED
        "work_mode": row.get("Work mode", "").strip(),
        "travel_requirement": row.get(
            "Does this role require travel?", ""
        ).strip(),

        # ─────────────────────────────
        # RESPONSIBILITIES (FACTS)
        # ─────────────────────────────
        "core_responsibility": row.get(
            "What is the single core responsibility of this role?", ""
        ).strip(),

        "responsibilities": split_lines(
            row.get("Key Responsibilities", "")
        ),

        # ─────────────────────────────
        # SKILLS (FACTS)
        # ─────────────────────────────
        "must_have_skills": split_lines(
            row.get("Top 3 skills this role MUST have", "")
        ),

        "preferred_skills": split_lines(
            row.get("other skills", "")
        ),

        # ─────────────────────────────
        # SUCCESS & GROWTH (CONTEXT ONLY)
        # ─────────────────────────────
        "success_profile": row.get(
            "What type of person will succeed in this role?", ""
        ).strip(),

        "growth_opportunity": row.get(
            "Growth opportunities in this role", ""
        ).strip(),

        "education": row.get(
            "Minimum education required", ""
        ).strip(),

        # ─────────────────────────────
        # LOW-PRIORITY NOTES
        # ─────────────────────────────
        "custom_notes": row.get("Additional Notes", "").strip(),
    }
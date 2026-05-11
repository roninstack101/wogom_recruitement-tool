import os
import re
import requests

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL = "https://api.serper.dev/search"

def extract_job_role(jd_text: str) -> str:
    """
    STRICT extraction for formatted JDs.
    Job role MUST be the first heading / first line.
    """

    # Normalize text
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]

    if not lines:
        raise ValueError("JD text is empty. Cannot extract job role.")

    first_line = lines[0]

    # Reject obvious non-role lines
    forbidden_prefixes = (
        "location",
        "experience",
        "employment",
        "ctc",
        "joining",
        "role overview",
        "about"
    )

    if first_line.lower().startswith(forbidden_prefixes):
        raise ValueError(
            "Job role must be the first heading in JD. Found metadata instead."
        )

    # Extra safety: role should be short (titles are usually < 8 words)
    if len(first_line.split()) > 8:
        raise ValueError(
            "First line does not look like a job title. JD format invalid."
        )

    return first_line

# -----------------------------
# STEP 2: Build HR-Centric Queries
# -----------------------------
def build_search_queries(job_role: str):
    """
    HR mindset:
    Find companies where experienced people in this role work
    """

    queries = [
        f"companies known for strong {job_role} talent",
        f"top companies with experienced {job_role} professionals",
        f"organizations having advanced {job_role} teams",
        f"{job_role} experts working at which companies",
        f"best companies for hiring senior {job_role} India"
    ]

    return queries


# -----------------------------
# STEP 3: Serper Search
# -----------------------------
def serper_search(query: str):
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "q": query,
        "num": 10
    }

    response = requests.post(SERPER_URL, headers=headers, json=payload)
    response.raise_for_status()

    return response.json().get("organic", [])


# -----------------------------
# STEP 4: Extract Company Signals
# -----------------------------
def extract_company_info(results):
    companies = []

    for item in results:
        companies.append({
            "company_hint": item.get("title"),
            "source_url": item.get("link"),
            "context": item.get("snippet")
        })

    return companies


# -----------------------------
# STEP 5: MAIN PIPELINE
# -----------------------------
def run_candidate_intel(jd_text: str):
    job_role = extract_job_role(jd_text)

    all_company_data = []

    queries = build_search_queries(job_role)

    for query in queries:
        results = serper_search(query)
        structured = extract_company_info(results)
        all_company_data.extend(structured)

    return {
        "job_role": job_role,
        "recommended_source_companies": all_company_data
    }

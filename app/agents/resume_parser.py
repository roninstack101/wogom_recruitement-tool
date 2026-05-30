#resume parser
import os
import zipfile
from typing import Dict, List

from app.utils.text_cleanup import extract_text_from_file
from app.utils.resume_skills import extract_skills_llm, extract_section


SUPPORTED_EXT = (".pdf", ".doc", ".docx", ".txt")


def _extract_resumes_from_files(resume_files: List[str]) -> List[Dict]:
    """
    Takes list of file paths (zip or single resume),
    returns list of {file, path, text}
    """
    extracted = []

    for path in resume_files:
        # ---------------- ZIP ----------------
        if path.lower().endswith(".zip"):
            extract_dir = path + "_unzipped"
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(path, "r") as z:
                z.extractall(extract_dir)

            for root, _, files in os.walk(extract_dir):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXT):
                        full_path = os.path.join(root, f)
                        text = extract_text_from_file(full_path)
                        if text.strip():
                            extracted.append({
                                "file": f,
                                "path": full_path,
                                "text": text
                            })

        # ---------------- SINGLE FILE ----------------
        else:
            if path.lower().endswith(SUPPORTED_EXT):
                text = extract_text_from_file(path)
                if text.strip():
                    extracted.append({
                        "file": os.path.basename(path),
                        "path": path,
                        "text": text
                    })

    return extracted


def resume_parser(state: Dict) -> Dict:
    """
    LangGraph node:
    - Reads resume_files
    - Extracts raw resume text
    - Parses into structured resumes
    - Writes state["parsed_resumes"]
    """

    resume_files = state.get("resume_files", [])
    parsed_jd = state.get("parsed_jd", {})
    jd_role = parsed_jd.get("role")

    raw_resumes = _extract_resumes_from_files(resume_files)

    parsed_resumes = []

    for r in raw_resumes:
        text = r["text"]

        parsed_resumes.append({
            "candidate_id": r["file"],
            "summary": extract_section(
                text, ["summary", "profile", "about"]
            ),
            "skills": extract_skills_llm(
                resume_text=text,
                role_context=jd_role
            ),
            "experience": extract_section(
                text, ["experience", "work history", "employment"]
            ),
            "projects": extract_section(
                text, ["projects", "key projects"]
            ),
            "raw_text": text,
            "resume_path": r["path"]
        })

    state["parsed_resumes"] = parsed_resumes
    return state

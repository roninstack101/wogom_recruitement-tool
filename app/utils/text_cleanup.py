import os
import pdfplumber
from docx import Document


# --------------------------------------------------
# 1️⃣ Extract raw text from file
# --------------------------------------------------
def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from PDF, DOCX, or TXT files.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return "\n".join(text).strip()

    elif ext in [".doc", ".docx"]:
        doc = Document(file_path)
        return "\n".join(
            p.text.strip() for p in doc.paragraphs if p.text.strip()
        )

    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()

    else:
        raise ValueError(f"Unsupported file type: {ext}")


# --------------------------------------------------
# 2️⃣ Cleanup helper
# --------------------------------------------------
def merge_short_bullets(text: str, min_words: int = 4) -> str:
    """
    Merge consecutive short bullet points into a single bullet.
    Helps LLMs understand fragmented responsibilities.
    """
    lines = text.split("\n")
    merged = []
    buffer = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("•"):
            words = stripped.replace("•", "").strip().split()

            if len(words) <= min_words:
                if buffer:
                    buffer += " and " + " ".join(words)
                else:
                    buffer = " ".join(words)
            else:
                if buffer:
                    merged.append(f"• {buffer}")
                    buffer = None
                merged.append(stripped)

        else:
            if buffer:
                merged.append(f"• {buffer}")
                buffer = None
            merged.append(line)

    if buffer:
        merged.append(f"• {buffer}")

    return "\n".join(merged)

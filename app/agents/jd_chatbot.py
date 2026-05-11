# app/agents/jd_chatbot.py
# Agent 4: Interactive JD Refinement Chatbot
# Takes current JD + user instruction → returns revised JD
# Saves all conversation history to a JSON log file

import json
import os
from datetime import datetime
from app.utils.llm import invoke_llm

# ─────────────────────────────────────────────
# Conversation log directory
# ─────────────────────────────────────────────
LOG_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
    "exports",
    "chatbot_logs"
)
os.makedirs(LOG_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# Refinement Prompt
# ─────────────────────────────────────────────
REFINE_PROMPT = """You are an expert Job Description editor.

You are given:
1. The current Job Description
2. A user instruction to modify it

TASK:
Apply the user's instruction to the Job Description and return the UPDATED version.

RULES:
- Apply ONLY the requested change. Do NOT rewrite unrelated sections.
- If the user says "remove X", remove it.
- If the user says "add X", add it in the most appropriate section.
- If the user says "make it more concise", shorten sentences without losing meaning.
- If the user says "change tone to X", adjust the language tone.
- Preserve the overall structure (headings, sections, bullets).
- Output ONLY the updated Job Description. No explanations, no notes.

CURRENT JD:
{current_jd}

USER INSTRUCTION:
{instruction}

Return ONLY the updated Job Description:
"""


def refine_jd(current_jd: str, instruction: str, role: str = "", session_id: str = "") -> str:
    """
    Agent 4: Refine a JD based on a user instruction.

    Args:
        current_jd: The current JD text to modify.
        instruction: The user's natural-language instruction.
        role: The job role name (for logging).
        session_id: A unique session identifier (for grouping logs).

    Returns:
        str: The updated JD text.
    """
    prompt = REFINE_PROMPT.format(
        current_jd=current_jd,
        instruction=instruction
    )

    try:
        response = invoke_llm(prompt)
        content = response.content

        # Handle list responses
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", str(part))
                if isinstance(part, dict)
                else str(part)
                for part in content
            )

        updated_jd = content.strip()

    except Exception as e:
        print(f"[JD_CHATBOT] Error during refinement: {e}")
        updated_jd = current_jd  # Return unchanged on error

    # ─────────────────────────────────────────────
    # Save conversation to JSON log
    # ─────────────────────────────────────────────
    _save_conversation_log(
        role=role,
        session_id=session_id,
        instruction=instruction,
        jd_before=current_jd,
        jd_after=updated_jd
    )

    return updated_jd


def _save_conversation_log(
    role: str,
    session_id: str,
    instruction: str,
    jd_before: str,
    jd_after: str
):
    """
    Appends a conversation turn to a JSON log file.
    Each session gets its own file: exports/chatbot_logs/{session_id}.json
    """
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    log_file = os.path.join(LOG_DIR, f"{session_id}.json")

    # Load existing log or create new
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    else:
        log_data = {
            "session_id": session_id,
            "role": role,
            "created_at": datetime.now().isoformat(),
            "conversations": []
        }

    # Append this turn
    log_data["conversations"].append({
        "turn": len(log_data["conversations"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "user_instruction": instruction,
        "jd_before_length": len(jd_before),
        "jd_after_length": len(jd_after),
        "jd_after_snapshot": jd_after
    })

    # Save
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    print(f"[JD_CHATBOT] Conversation saved → {log_file}")


def get_conversation_history(session_id: str) -> list:
    """
    Retrieve the conversation history for a given session.

    Args:
        session_id: The session ID to look up.

    Returns:
        list: List of conversation turn dicts.
    """
    log_file = os.path.join(LOG_DIR, f"{session_id}.json")

    if not os.path.exists(log_file):
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        log_data = json.load(f)

    return log_data.get("conversations", [])

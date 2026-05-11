import json
import pandas as pd
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


def load_form_data() -> pd.DataFrame:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    service_account_info = json.loads(
        st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]
    )

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes
    )

    client = gspread.authorize(creds)

    SPREADSHEET_ID = "1SpNGsY707CaY6i06knI9F2HJdtAcHxGKq8IjAb17oWo"
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1

    data = sheet.get_all_records()
    return pd.DataFrame(data)


def fetch_google_form_data() -> list[dict]:
    df = load_form_data()

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    result = []

    for _, row in df.iterrows():
        result.append({
            "role": row.get(
                "job title ( example: ai engineer, sales executive, hr manager)",
                ""
            ),
            "department": row.get(
                "in which department (ex. marketing, tech etc.)",
                ""
            ),
            "location": row.get("location", ""),
            "employment_type": row.get(
                "employment type ( full-time / contract / internship )",
                "Full-time"
            ),
            "travel_required": row.get(
                "does this role require travel?",
                ""
            ),
            "work_mode": row.get("work mode", ""),
            "key_responsibilities": row.get(
                "key responsibilities  ( list 4–6 things this person will actually do)",
                ""
            ),
            "reporting_to": row.get(
                "reporting to (example: tech lead, sales manager)",
                ""
            ),
            "new_or_scaling": row.get(
                "is this role building something new or scaling an existing function?",
                ""
            ),
            "must_have_skills": row.get(
                "top 3 skills this role must have",
                ""
            ),
            "other_skills": row.get(
                "other skills ( example: python, excel, communication )",
                ""
            ),
            "minimum_education": row.get(
                "minimum education required",
                ""
            ),
            "experience": row.get(
                "minimum experience required",
                ""
            ),
            "urgency": row.get(
                "how urgent is this hire?",
                ""
            ),
            "salary": row.get(
                "salary range (optional)",
                ""
            ),
        })

    return result

if __name__ == "__main__":
    data = fetch_google_form_data()

    print("\n========== GOOGLE FORM OUTPUT ==========\n")
    for idx, row in enumerate(data, start=1):
        print(f"--- ENTRY {idx} ---")
        for key, value in row.items():
            print(f"{key}: {value}")
        print()
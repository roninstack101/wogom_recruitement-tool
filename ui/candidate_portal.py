#candidate_portal.py
import streamlit as st
import requests
import pandas as pd
import os

BACKEND_URL = "http://localhost:8000/pipeline/run_pipeline"

# ==================================================
# PAGE-LEVEL UI THEME (MATCH RECRUITER PORTAL)
# ==================================================
st.markdown("""
<style>
            /* ---------- FIX INVISIBLE TEXT IN CANDIDATE PORTAL ---------- */

/* Alerts (info, warning, error) */
.stAlert p {
    color: #0f172a !important;
}

/* File uploader labels */
[data-testid="stFileUploader"] label {
    color: #0f172a !important;
}

/* DataFrame text */
thead tr th,
tbody tr td {
    color: #0f172a !important;
}

/* ---------- PAGE WRAPPER ---------- */
.page-wrapper {
    max-width: 1100px;
    margin: auto;
    padding: 40px 24px 80px;
}

/* ---------- HERO ---------- */
.page-title {
    text-align: center;
    font-size: 44px;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 12px;
}

.page-subtitle {
    text-align: center;
    font-size: 18px;
    color: #475569;
    margin-bottom: 40px;
}

/* ---------- SECTION ---------- */
.section {
    margin-top: 48px;
}

.section-title {
    font-size: 24px;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 16px;
}

/* ---------- FILE UPLOADER ---------- */
[data-testid="stFileUploader"] {
    background: #ffffff !important;
    border-radius: 14px;
    padding: 18px;
    border: 1px solid #e2e8f0;
}

[data-testid="stFileUploader"] * {
    color: #1e293b !important;
    font-size: 14px;
}

/* ---------- BUTTON ---------- */
div.stButton > button {
    background: #4f46e5 !important;
    color: white !important;
    font-size: 16px;
    font-weight: 600;
    border-radius: 10px;
    padding: 14px;
}

/* ---------- STATUS / INFO ---------- */
.stAlert {
    border-radius: 10px;
    font-size: 15px;
}

</style>
""", unsafe_allow_html=True)


def render():
    # ==================================================
    # HERO
    # ==================================================
    st.markdown("""
    <div class="page-wrapper">
        <div class="page-title">🧠 Candidate Intelligence</div>
        <div class="page-subtitle">
            Analyze job fit, strengths, gaps, and candidate rankings using AI-powered matching.
        </div>
    """, unsafe_allow_html=True)

    # ==================================================
    # FILE UPLOAD SECTION
    # ==================================================
    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Upload Inputs</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        jd_file = st.file_uploader(
            "Job Description",
            type=["pdf", "docx", "txt"]
        )

    with col2:
        resume_file = st.file_uploader(
            "Candidate Resumes",
            type=["zip", "pdf", "docx"]
        )

    st.markdown('</div>', unsafe_allow_html=True)

    if not jd_file or not resume_file:
        st.info("Please upload both Job Description and resumes to continue.")
        return

    # ==================================================
    # RUN PIPELINE
    # ==================================================
    st.markdown('<div class="section">', unsafe_allow_html=True)

    if st.button("🚀 Run Candidate Matching", use_container_width=True):
        with st.status("Running candidate matching pipeline...", expanded=True):

            files = {
                "jd_file": (jd_file.name, jd_file, jd_file.type),
                "resumes": (resume_file.name, resume_file, resume_file.type)
            }

            response = requests.post(
                BACKEND_URL,
                files=files,
                timeout=600
            )

            if response.status_code != 200:
                st.error("Pipeline failed. Check backend logs.")
                return

            st.session_state.matching_result = response.json()

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================
    # RESULTS
    # ==================================================
    if "matching_result" not in st.session_state:
        return

    results = st.session_state.matching_result.get("ranking", [])
    if not results:
        st.warning("No suitable candidates found.")
        return

    st.markdown('<div class="section">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏆 Ranked Candidates</div>', unsafe_allow_html=True)

    df = pd.DataFrame(results)
    st.dataframe(
        df[["rank", "candidate_id", "job_fit_percent", "strengths", "gaps"]],
        use_container_width=True
    )

    st.markdown('</div></div>', unsafe_allow_html=True)

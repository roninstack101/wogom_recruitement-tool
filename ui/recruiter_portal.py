import streamlit as st
import sys
import os
import json
import markdown

# ─────────────────────────────────────────────────────────
# Path setup
# ─────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ─────────────────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────────────────
from app.agents.jd_clarifier import generate_clarifying_questions
from app.agents.profile_builder import build_profile
from app.agents.jd_generator import generate_jd
from app.agents.jd_chatbot import refine_jd
from app.utils.google_form_loader import fetch_google_form_data
from app.utils.file_export import export_to_docx, export_to_pdf
from datetime import datetime


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
STEP_LABELS = {
    1: ("📋", "Select Role"),
    2: ("🤔", "Clarify"),
    3: ("🎯", "Profile"),
    4: ("📄", "Draft JD"),
    5: ("💬", "Refine"),
    6: ("🏁", "Export"),
}


def render_jd_html(jd_text: str):
    """Render JD markdown as styled HTML."""
    html_body = markdown.markdown(jd_text, extensions=["extra"])
    st.markdown(
        f"""
        <div style="
            font-family: 'Inter', sans-serif;
            max-width: 860px; margin: 0 auto;
            background: white; padding: 32px 36px;
            border-radius: 14px; line-height: 1.7;
            color: #1E293B; border: 1px solid #E2E8F0;
        ">{html_body}</div>
        """,
        unsafe_allow_html=True,
    )


def step_progress(current: int):
    """Render a visual step progress bar."""
    cols = st.columns(6)
    for i, col in enumerate(cols, start=1):
        icon, label = STEP_LABELS[i]
        if i < current:
            color, bg, border = "#4F46E5", "#EEF2FF", "2px solid #4F46E5"
            check = "✓"
        elif i == current:
            color, bg, border = "white", "#4F46E5", "none"
            check = icon
        else:
            color, bg, border = "#94A3B8", "#F1F5F9", "1px solid #E2E8F0"
            check = icon
        col.markdown(
            f"""
            <div style="text-align:center;">
                <div style="
                    width:42px; height:42px; border-radius:50%;
                    background:{bg}; color:{color}; border:{border};
                    display:inline-flex; align-items:center; justify-content:center;
                    font-size:18px; font-weight:700;
                ">{check}</div>
                <div style="font-size:12px; color:#64748B; margin-top:6px; font-weight:500;">
                    {label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────
def render():
    # ── Styles ──
    st.markdown("""
    <style>
    /* ── Page title ── */
    .page-header {
        text-align: center; margin-bottom: 8px;
    }
    .page-header h1 {
        font-size: 36px !important; font-weight: 800 !important;
        color: #0F172A !important; letter-spacing: -1px;
    }
    .page-header p {
        font-size: 16px; color: #64748B !important; margin-top: -8px;
    }

    /* ── Section cards ── */
    .ui-card {
        background: white; border: 1px solid #E2E8F0;
        border-radius: 14px; padding: 28px 32px;
        margin-bottom: 20px;
    }

    /* ── Section headings inside cards ── */
    .section-heading {
        font-size: 20px !important; font-weight: 700 !important;
        color: #0F172A !important; margin-bottom: 16px !important;
    }

    /* ── Select box ── */
    .stSelectbox > div > div {
        border-radius: 10px !important;
    }

    /* ── Text inputs ── */
    .stTextInput > div > div > input {
        border-radius: 10px !important;
        border: 1.5px solid #E2E8F0 !important;
        padding: 12px 16px !important;
        font-size: 15px !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
    }

    /* ── Text area ── */
    .stTextArea textarea {
        border-radius: 10px !important;
        border: 1.5px solid #E2E8F0 !important;
        font-size: 14px !important;
    }

    /* ── Info / success bars ── */
    .stAlert {
        border-radius: 10px !important;
    }

    /* ── FORCE all text dark ── */
    .stMarkdown, .stText, .stCaption,
    p, li, span, label, div,
    h1, h2, h3, h4, h5, h6,
    td, th, caption,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] span,
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] div,
    .stSelectbox label,
    .stMultiSelect label,
    .stTextInput label,
    .stTextArea label,
    .stRadio label,
    .stCheckbox label,
    .element-container,
    .stAlert p, .stAlert div {
        color: #1E293B !important;
    }

    /* ── Select / multiselect dropdowns ── */
    [data-testid="stSelectbox"] div,
    [data-testid="stSelectbox"] span,
    [data-testid="stSelectbox"] input,
    [data-testid="stMultiSelect"] div,
    [data-testid="stMultiSelect"] span,
    [data-testid="stMultiSelect"] input,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        color: #1E293B !important;
    }

    /* ── Text input value ── */
    .stTextInput > div > div > input,
    .stTextArea textarea {
        color: #1E293B !important;
    }

    /* ── Expander header ── */
    [data-testid="stExpander"] details summary span {
        color: #1E293B !important;
    }

    /* ── Download buttons text ── */
    .stDownloadButton button {
        color: white !important;
    }

    /* ── Caption ── */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: #64748B !important;
    }

    /* ── Dividers ── */
    hr {
        border: none; border-top: 1px solid #E2E8F0; margin: 20px 0;
    }

    /* ── Chat bubbles ── */
    .chat-bubble-user {
        background: #EEF2FF; border-radius: 12px;
        padding: 12px 16px; margin: 6px 0;
        color: #3730A3 !important; font-size: 14px;
    }
    .chat-bubble-system {
        background: #F0FDF4; border-radius: 12px;
        padding: 10px 16px; margin: 6px 0;
        color: #166534 !important; font-size: 13px;
    }

    /* ── Profile chips ── */
    .profile-chip {
        display: inline-block;
        background: #EEF2FF;
        color: #4338CA !important;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
        margin: 4px 4px 4px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Session state defaults ──
    defaults = {
        "step": 1,
        "selected_role": None,
        "jd_data": {},
        "questions": [],
        "answers": [],
        "profile": {},
        "draft_jd": "",
        "final_jd": "",
        "chat_history": [],
        "chatbot_session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Header ──
    st.markdown("""
    <div class="page-header">
        <h1>📋 JD Generator</h1>
        <p>Create professional job descriptions in 6 easy steps</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Progress bar ──
    step_progress(st.session_state.step)

    # ═══════════════════════════════════════════════════════
    # STEP 1 — Select Role
    # ═══════════════════════════════════════════════════════
    if st.session_state.step == 1:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-heading">Select a Job Role</div>', unsafe_allow_html=True)

        roles = fetch_google_form_data()
        if not roles:
            st.error("❌ No roles found. Check Google Sheet connection.")
            st.stop()

        role_names = [r["role"] for r in roles]
        default_idx = role_names.index(st.session_state.selected_role) if st.session_state.selected_role in role_names else 0

        selected_role = st.selectbox("Job Role", role_names, index=default_idx, label_visibility="collapsed")

        if selected_role:
            role_data = next(r for r in roles if r["role"] == selected_role)
            st.session_state.selected_role = selected_role
            st.session_state.jd_data = role_data

            # Show quick info
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**🏢 Department:** {role_data.get('department', '—')}")
            c2.markdown(f"**📍 Location:** {role_data.get('location', '—')}")
            c3.markdown(f"**⏱️ Experience:** {role_data.get('experience', '—')}")

        st.markdown('</div>', unsafe_allow_html=True)

        # Navigation
        _, rc = st.columns([3, 1])
        with rc:
            if st.session_state.selected_role:
                if st.button("Continue →", use_container_width=True, type="primary"):
                    st.session_state.step = 2
                    st.rerun()

    # ═══════════════════════════════════════════════════════
    # STEP 2 — Clarifying Questions (Agent 1)
    # ═══════════════════════════════════════════════════════
    elif st.session_state.step == 2:
        dept = st.session_state.jd_data.get("department", "the department")

        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-heading">Clarifying Questions — {dept} Head Perspective</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"As the Head of **{dept}**, answer these questions about the "
            f"**{st.session_state.selected_role}** role. You can select multiple options."
        )

        # Generate questions
        if not st.session_state.questions:
            with st.spinner("Generating clarifying questions..."):
                st.session_state.questions = generate_clarifying_questions(
                    form_data=st.session_state.jd_data
                )

        if not st.session_state.questions:
            st.info("✅ No clarifying questions needed — all info is available.")
            st.markdown('</div>', unsafe_allow_html=True)
            _, rc = st.columns([3, 1])
            with rc:
                if st.button("Continue →", use_container_width=True, type="primary"):
                    st.session_state.step = 3
                    st.rerun()
            return

        # Render each question
        answers = []
        for i, q in enumerate(st.session_state.questions):
            st.markdown("---")
            st.markdown(f"**Q{i+1}.** {q.get('question', '')}")

            options = q.get("options", [])
            selected = st.multiselect(
                f"Select answers for Q{i+1}",
                options,
                default=st.session_state.get(f"ans_{i}", []),
                key=f"ms_{i}",
                label_visibility="collapsed",
            )
            st.session_state[f"ans_{i}"] = selected

            answers.append({
                "id": q["id"],
                "question": q["question"],
                "answer": selected,
                "target_section": q.get("target_section", ""),
            })

        st.session_state.answers = answers
        st.markdown('</div>', unsafe_allow_html=True)

        # Navigation
        lc, _, rc = st.columns([1, 2, 1])
        with lc:
            if st.button("← Back", use_container_width=True, type="secondary"):
                st.session_state.step = 1
                st.rerun()
        with rc:
            if st.button("Build Profile →", use_container_width=True, type="primary"):
                st.session_state.step = 3
                st.rerun()

    # ═══════════════════════════════════════════════════════
    # STEP 3 — Profile Builder (Agent 2)
    # ═══════════════════════════════════════════════════════
    elif st.session_state.step == 3:
        if not st.session_state.profile:
            with st.spinner("🎯 Building ideal candidate profile..."):
                st.session_state.profile = build_profile(
                    form_data=st.session_state.jd_data,
                    clarification_answers=st.session_state.answers,
                )

        p = st.session_state.profile

        # Header card
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #6366F1, #8B5CF6);
                color: white; border-radius: 14px; padding: 24px 32px;
                margin-bottom: 20px;
            ">
                <div style="font-size:22px; font-weight:700; color:white !important;">
                    🎯 Ideal Candidate Profile
                </div>
                <div style="font-size:14px; opacity:0.85; margin-top:4px; color:white !important;">
                    {p.get('role', '')} — {p.get('department', '')} Department
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Summary
        st.info(p.get("profile_summary", "—"))

        # Two-column details
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**💡 Core Competencies**")
            for item in p.get("core_competencies", []):
                st.markdown(f'<span class="profile-chip">{item}</span>', unsafe_allow_html=True)

            st.markdown("")
            st.markdown("**🛠️ Must-Have Skills**")
            for item in p.get("must_have_skills_refined", []):
                st.markdown(f"- {item}")

        with c2:
            st.markdown("**🧠 Behavioral Traits**")
            for item in p.get("behavioral_traits", []):
                st.markdown(f'<span class="profile-chip">{item}</span>', unsafe_allow_html=True)

            st.markdown("")
            st.markdown("**✨ Nice-to-Have**")
            for item in p.get("nice_to_have_skills", []):
                st.markdown(f"- {item}")

        st.markdown("---")
        st.markdown("**📊 Success Metrics**")
        for m in p.get("success_metrics", []):
            st.markdown(f"- {m}")

        if p.get("team_context"):
            st.markdown("")
            st.markdown(f"**👥 Team Context:** {p['team_context']}")

        # Navigation
        st.markdown("")
        lc, _, rc = st.columns([1, 2, 1])
        with lc:
            if st.button("← Back", use_container_width=True, type="secondary"):
                st.session_state.profile = {}
                st.session_state.step = 2
                st.rerun()
        with rc:
            if st.button("Generate JD →", use_container_width=True, type="primary"):
                st.session_state.step = 4
                st.rerun()

    # ═══════════════════════════════════════════════════════
    # STEP 4 — Draft JD (Agent 3)
    # ═══════════════════════════════════════════════════════
    elif st.session_state.step == 4:
        if not st.session_state.draft_jd:
            with st.spinner("📄 Generating Job Description from profile..."):
                st.session_state.draft_jd = generate_jd(
                    form_data=st.session_state.jd_data,
                    profile=st.session_state.profile,
                )
                st.session_state.final_jd = st.session_state.draft_jd

        st.success("✅ Draft JD generated! Review it below, then proceed to refine.")
        render_jd_html(st.session_state.final_jd)

        # Navigation
        st.markdown("")
        lc, _, rc = st.columns([1, 2, 1])
        with lc:
            if st.button("← Back to Profile", use_container_width=True, type="secondary"):
                st.session_state.draft_jd = ""
                st.session_state.final_jd = ""
                st.session_state.step = 3
                st.rerun()
        with rc:
            if st.button("Refine with Chat →", use_container_width=True, type="primary"):
                st.session_state.step = 5
                st.rerun()

    # ═══════════════════════════════════════════════════════
    # STEP 5 — Chatbot Loop (Agent 4)
    # ═══════════════════════════════════════════════════════
    elif st.session_state.step == 5:
        st.markdown('<div class="ui-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-heading">💬 Refine Your JD</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Type an instruction below and click **Apply**. "
            "Each time you apply, a new version is generated. "
            "Click **Finalize** when you're happy."
        )

        # Chat history
        for entry in st.session_state.chat_history:
            st.markdown(
                f'<div class="chat-bubble-user">💬 <b>You:</b> {entry["instruction"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="chat-bubble-system">✅ Applied — version {entry["version"]}</div>',
                unsafe_allow_html=True,
            )

        # Input row
        ic, bc = st.columns([5, 1])
        with ic:
            instruction = st.text_input(
                "Instruction",
                placeholder="e.g. Make it more concise / Add Python requirement / Remove travel section",
                key="chat_input",
                label_visibility="collapsed",
            )
        with bc:
            apply = st.button("Apply", type="primary", use_container_width=True)

        if apply and instruction and instruction.strip():
            with st.spinner("Applying changes..."):
                updated = refine_jd(
                    current_jd=st.session_state.final_jd,
                    instruction=instruction.strip(),
                    role=st.session_state.selected_role,
                    session_id=st.session_state.chatbot_session_id,
                )
                st.session_state.final_jd = updated
                st.session_state.chat_history.append({
                    "instruction": instruction.strip(),
                    "version": len(st.session_state.chat_history) + 1,
                    "timestamp": datetime.now().isoformat(),
                })
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # JD Preview
        st.markdown("")
        with st.expander("📄 Current JD Preview", expanded=True):
            render_jd_html(st.session_state.final_jd)

        # Navigation
        st.markdown("")
        lc, _, rc = st.columns([1, 2, 1])
        with lc:
            if st.button("← Back to Draft", use_container_width=True, type="secondary"):
                st.session_state.step = 4
                st.rerun()
        with rc:
            if st.button("Finalize & Export →", use_container_width=True, type="primary"):
                st.session_state.step = 6
                st.rerun()

    # ═══════════════════════════════════════════════════════
    # STEP 6 — Final Export (Agent 5)
    # ═══════════════════════════════════════════════════════
    elif st.session_state.step == 6:
        st.success("🎉 Your Job Description is ready!")

        # Preview
        render_jd_html(st.session_state.final_jd)

        # Optional manual edit
        with st.expander("✏️ Manual Edit (optional)"):
            edited = st.text_area(
                "Edit JD",
                value=st.session_state.final_jd,
                height=350,
                label_visibility="collapsed",
            )
            if edited != st.session_state.final_jd:
                st.session_state.final_jd = edited

        # Downloads
        st.markdown("---")
        st.markdown("**📥 Download your JD**")
        filename = st.session_state.selected_role.replace(" ", "_") + "_JD"

        dc, pc = st.columns(2)
        with dc:
            docx_path = export_to_docx(st.session_state.final_jd, filename)
            with open(docx_path, "rb") as f:
                st.download_button(
                    "📥  Download DOCX",
                    f,
                    file_name=f"{filename}.docx",
                    use_container_width=True,
                    type="primary",
                )
        with pc:
            pdf_path = export_to_pdf(st.session_state.final_jd, filename)
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "📥  Download PDF",
                    f,
                    file_name=f"{filename}.pdf",
                    use_container_width=True,
                    type="primary",
                )

        # Log info
        if st.session_state.chat_history:
            st.caption(
                f"💾 {len(st.session_state.chat_history)} refinement(s) saved to "
                f"`exports/chatbot_logs/{st.session_state.chatbot_session_id}.json`"
            )

        # Start over
        st.markdown("---")
        if st.button("🔄 Create Another JD", use_container_width=True, type="secondary"):
            for k in list(st.session_state.keys()):
                if k != "page":
                    del st.session_state[k]
            st.session_state.step = 1
            st.rerun()

import sys
import os
import json
import base64
import random
from datetime import datetime, timedelta
from collections import Counter

os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import requests

from document_processing.loaders.pdf_loader import load_document
from document_processing.preprocessing.chunker import chunk_text
from ai_engine.rag.chunk_retriever import index_document, retrieve_relevant_chunks
from backend.services.answer_evaluator import evaluate_answer
from ai_engine.llm.ollama_client import ask_llm
from semantic_versioning.document_comparator import (
    compare_documents, get_unmatched_chunks, get_detailed_comparison
)
from backend.services.weak_area_analyzer import analyze_weak_areas, find_review_pages
from frontend.auth_utils import (
    get_current_user, logout, api_verify_token, api_update_profile, is_logged_in
)

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================================================================
# GLOBAL CSS
# ================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; background-color: #0d1117; color: #e6edf3; }
[data-testid="stSidebarNav"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #161b22 0%, #0d1117 100%); border-right: 1px solid #21262d; }
[data-testid="stSidebar"] .stRadio label { font-family: 'DM Sans', sans-serif; font-size: 0.95rem; color: #8b949e; padding: 0.4rem 0; transition: color 0.2s; }
[data-testid="stSidebar"] .stRadio label:hover { color: #e6edf3; }
.metric-card { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border: 1px solid #21262d; border-radius: 12px; padding: 1.4rem 1.6rem; margin-bottom: 1rem; transition: border-color 0.2s, transform 0.2s; }
.metric-card:hover { border-color: #388bfd; transform: translateY(-2px); }
.metric-card .label { font-size: 0.78rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500; margin-bottom: 0.5rem; }
.metric-card .value { font-family: 'Syne', sans-serif; font-size: 2rem; font-weight: 700; color: #e6edf3; line-height: 1; }
.metric-card .sub { font-size: 0.78rem; color: #3fb950; margin-top: 0.35rem; }
.doc-card { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 1.2rem 1.4rem; margin-bottom: 0.85rem; transition: border-color 0.2s; }
.doc-card:hover { border-color: #388bfd; }
.doc-card .doc-title { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 600; color: #e6edf3; margin-bottom: 0.3rem; }
.doc-card .doc-meta { font-size: 0.8rem; color: #8b949e; }
.weak-badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.78rem; font-weight: 500; margin: 0.2rem 0.2rem 0.2rem 0; }
.weak-red    { background:#3d1a1a; color:#f85149; border:1px solid #f85149; }
.weak-yellow { background:#2d2208; color:#d29922; border:1px solid #d29922; }
.weak-green  { background:#0d2d1a; color:#3fb950; border:1px solid #3fb950; }
.section-heading { font-family: 'Syne', sans-serif; font-size: 1.5rem; font-weight: 700; color: #e6edf3; margin-bottom: 1.2rem; padding-bottom: 0.5rem; border-bottom: 1px solid #21262d; }
.welcome-banner { background: linear-gradient(135deg, #1c2d40 0%, #0d2137 50%, #162032 100%); border: 1px solid #1f4068; border-radius: 16px; padding: 1.8rem 2rem; margin-bottom: 1.8rem; }
.stProgress > div > div > div > div { background: linear-gradient(90deg, #388bfd, #1f6feb); border-radius: 4px; }
.stButton > button { background: linear-gradient(135deg, #238636, #2ea043); color: white; border: none; border-radius: 8px; font-family: 'DM Sans', sans-serif; font-weight: 500; padding: 0.5rem 1.2rem; transition: opacity 0.2s; }
.stButton > button:hover { opacity: 0.85; }
[data-testid="metric-container"] { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 1rem 1.2rem; }
[data-testid="stMetricValue"] { font-family: 'Syne', sans-serif; color: #e6edf3; }
[data-testid="stExpander"] { background: #161b22; border: 1px solid #21262d; border-radius: 10px; }
.stAlert { border-radius: 10px; }
hr { border-color: #21262d; }
.profile-card { background: linear-gradient(135deg, #161b22 0%, #1c2128 100%); border: 1px solid #21262d; border-radius: 16px; padding: 2rem; margin-bottom: 1.2rem; }
.info-row { display: flex; justify-content: space-between; align-items: center; padding: 0.7rem 0; border-bottom: 1px solid #21262d; font-size: 0.9rem; }
.info-row:last-child { border-bottom: none; }
.info-label { color: #8b949e; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; }
.info-value { color: #e6edf3; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ================================================================
# AUTH GUARD
# ================================================================
if "token_verified" not in st.session_state:
    api_verify_token()
    st.session_state["token_verified"] = True

if not is_logged_in():
    st.switch_page("login.py")
    st.stop()

_user = get_current_user()


# ================================================================
# USER-SCOPED DATA PATHS  ← THE KEY CHANGE
# Every read/write of quiz history and doc library is now isolated
# under  data/users/<email>/  so each user sees only their own data.
# ================================================================
def _safe_email() -> str:
    """Return a filesystem-safe folder name derived from the user's email."""
    email = get_current_user().get("email", "default")
    return email.replace("@", "_at_").replace(".", "_dot_")


def _user_dir() -> str:
    d = os.path.join("data", "users", _safe_email())
    os.makedirs(d, exist_ok=True)
    return d


def _history_dir() -> str:
    d = os.path.join(_user_dir(), "question_bank")
    os.makedirs(d, exist_ok=True)
    return d


def _lib_path() -> str:
    return os.path.join(_user_dir(), "doc_library.json")


# ================================================================
# HELPER FUNCTIONS
# ================================================================
def detect_topic(text):
    mid    = len(text) // 4
    sample = text[mid: mid + 3000]
    topic  = ask_llm(
        "Identify the main topic of the following study material.\n"
        "Return ONLY the topic name. No explanation, no extra text, just the topic.\n"
        + sample
    )
    return topic.strip() if topic else "General Topic"


def load_all_history():
    """Quiz history for the current user only."""
    results = []
    for f in sorted(os.listdir(_history_dir())):
        if f.endswith(".json"):
            try:
                with open(os.path.join(_history_dir(), f)) as fp:
                    results.append(json.load(fp))
            except Exception:
                continue
    return results


def load_doc_library():
    """Document library for the current user only."""
    if not os.path.exists(_lib_path()):
        return {}
    try:
        with open(_lib_path()) as f:
            return json.load(f)
    except Exception:
        return {}


def save_doc_library(library):
    with open(_lib_path(), "w") as f:
        json.dump(library, f, indent=2)


def register_document(filename, filesize, topic, chunks_count):
    library = load_doc_library()
    doc_key = f"{filename}_{filesize}"
    if doc_key not in library:
        library[doc_key] = {
            "filename": filename, "topic": topic, "chunks": chunks_count,
            "added": datetime.now().strftime("%Y-%m-%d"),
            "quiz_count": 0, "last_score": None, "weak_topics": []
        }
    else:
        library[doc_key]["topic"] = topic
    save_doc_library(library)
    return doc_key


def update_doc_stats(doc_key, score, total, weak_topics):
    library = load_doc_library()
    if doc_key in library:
        library[doc_key]["quiz_count"] += 1
        library[doc_key]["last_score"]  = round((score / total) * 100, 1) if total else 0
        library[doc_key]["weak_topics"] = weak_topics
        save_doc_library(library)
    else:
        st.warning(f"⚠️ Could not update stats: key `{doc_key}` not found.")


def compute_streak(history):
    if not history:
        return 0
    dates = sorted(set(
        r["timestamp"][:10] for r in history if r.get("accuracy", 0) >= 40
    ), reverse=True)
    streak = 0
    today  = datetime.now().date()
    for i, d in enumerate(dates):
        if datetime.strptime(d, "%Y-%m-%d").date() == today - timedelta(days=i):
            streak += 1
        else:
            break
    return streak


def save_quiz_result(topic, difficulty, score, total,
                     questions, answers, weak_analysis=None, recommendations=None):
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic, "difficulty": difficulty,
        "score": score, "total": total,
        "accuracy": round((score / total) * 100, 1) if total else 0,
        "questions": [
            {"question": q["question"], "type": q["type"],
             "correct_answer": q["answer"], "user_answer": answers.get(i, "")}
            for i, q in enumerate(questions)
        ],
        "weak_areas": (
            [{"topic": a["topic"], "reason": a["reason"], "review_hint": a["review_hint"]}
             for a in weak_analysis["weak_areas"]]
            if weak_analysis and weak_analysis.get("weak_areas") else []
        ),
        "review_recommendations": (
            [{"topic": r["topic"], "estimated_page": r["estimated_page"],
              "review_hint": r["review_hint"], "chunk_preview": r["chunk_preview"]}
             for r in recommendations]
            if recommendations else []
        )
    }
    fname = os.path.join(_history_dir(),
                         f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(fname, "w") as f:
        json.dump(result, f, indent=2)
    return fname


def export_pdf(topic, difficulty, score, total, questions, answers):
    try:
        from fpdf import FPDF
    except ImportError:
        return None
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DocuMind AI Quiz Results", ln=True); pdf.ln(3)
    pdf.set_font("Helvetica", "", 12)
    for line in [f"Topic: {topic}", f"Difficulty: {difficulty}",
                 f"Score: {score}/{total}",
                 f"Accuracy: {round((score/total)*100,1) if total else 0}%",
                 f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]:
        pdf.cell(0, 8, line, ln=True)
    pdf.ln(5)
    for i, q in enumerate(questions):
        ua = answers.get(i, "Unanswered")
        ok = str(ua).strip().lower() == str(q["answer"]).strip().lower()
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 7, f"Q{i+1}: {q['question'].encode('latin-1','replace').decode('latin-1')}")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Your Answer: {str(ua).encode('latin-1','replace').decode('latin-1')} [{'CORRECT' if ok else 'INCORRECT'}]", ln=True)
        if not ok:
            pdf.cell(0, 6, f"Correct Answer: {str(q['answer']).encode('latin-1','replace').decode('latin-1')}", ln=True)
        pdf.ln(3)
    return bytes(pdf.output())


def process_file(uploaded_file, slot):
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state[f"doc{slot}_id"] != file_id:
        with st.spinner(f"Processing Document {slot}..."):
            text   = load_document(uploaded_file)
            chunks = chunk_text(text)
            if not chunks:
                st.error(f"Document {slot} could not be chunked.")
                return None, []
            index_document(chunks, doc_id=f"doc{slot}")
            st.session_state[f"doc{slot}_text"]     = text
            st.session_state[f"doc{slot}_chunks"]   = chunks
            st.session_state[f"doc{slot}_id"]       = file_id
            st.session_state[f"doc{slot}_file_key"] = file_id
            st.session_state.generated = False
        st.success(f"✅ Document {slot} ready — {len(chunks)} chunks")
    return st.session_state[f"doc{slot}_text"], st.session_state[f"doc{slot}_chunks"]


# ================================================================
# SESSION STATE
# ================================================================
for key, default in {
    "questions": [], "answers": {}, "generated": False,
    "topic": "", "doc1_text": None, "doc2_text": None,
    "doc1_chunks": [], "doc2_chunks": [],
    "doc1_id": None, "doc2_id": None, "doc1_file_key": None,
    "difficulty": "Medium", "comparison_result": None,
    "quiz_start_time": None, "active_doc_key": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ================================================================
# SIDEBAR
# ================================================================
with st.sidebar:
    st.markdown(
        "<div style='padding:1rem 0 1.2rem 0;'>"
        "<div style='font-family:Syne,sans-serif;font-size:1.3rem;font-weight:800;"
        "color:#e6edf3;letter-spacing:-0.02em;'>📘 DocuMind AI</div>"
        "<div style='font-size:0.72rem;color:#8b949e;margin-top:0.2rem;"
        "text-transform:uppercase;letter-spacing:0.08em;'>Smart Learning Platform</div>"
        "</div>", unsafe_allow_html=True
    )

    page = st.radio("nav", [
        "🏠  Dashboard", "📄  My Documents", "🧠  Generate Quiz",
        "🃏  Flashcards", "📊  Analytics", "⚠️  Weak Topics",
        "👤  Profile", "⚙️  Settings",
    ], label_visibility="collapsed")

    # Stats are now loaded from the current user's folder
    history   = load_all_history()
    streak    = compute_streak(history)
    library   = load_doc_library()
    avg_score = round(sum(r["accuracy"] for r in history) / len(history), 1) if history else 0

    st.markdown("<div style='margin-top:1.5rem;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.72rem;color:#8b949e;text-transform:uppercase;"
                "letter-spacing:0.08em;margin-bottom:0.8rem;'>Quick Stats</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<div style='display:flex;flex-direction:column;gap:0.5rem;'>"
        + "".join([
            "<div style='display:flex;justify-content:space-between;font-size:0.83rem;color:#8b949e;'>"
            "<span>" + lbl + "</span>"
            "<span style='color:" + col + ";font-weight:600;'>" + val + "</span></div>"
            for lbl, val, col in [
                ("📄 Docs",      str(len(library)),  "#e6edf3"),
                ("🧠 Quizzes",   str(len(history)),  "#e6edf3"),
                ("📊 Avg Score", str(avg_score)+"%", "#3fb950"),
                ("🔥 Streak",    str(streak)+" days","#d29922"),
            ]
        ])
        + "</div>", unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

    user_name    = _user.get("name", "User")
    user_email   = _user.get("email", "")
    user_initial = user_name[0].upper() if user_name else "U"

    st.markdown("<div style='margin-top:1.5rem;'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='background:rgba(13,17,23,0.6);border:1px solid rgba(48,54,61,0.7);"
        "border-radius:12px;padding:0.8rem 1rem;margin-bottom:0.8rem;"
        "display:flex;align-items:center;gap:0.75rem;'>"
        "<div style='width:36px;height:36px;flex-shrink:0;"
        "background:linear-gradient(135deg,#1f6feb,#388bfd);border-radius:50%;"
        "display:flex;align-items:center;justify-content:center;"
        "box-shadow:0 4px 12px rgba(56,139,253,0.3);'>"
        "<span style='font-family:Syne,sans-serif;font-size:1rem;font-weight:700;color:#fff;'>"
        + user_initial + "</span></div>"
        "<div style='flex:1;overflow:hidden;'>"
        "<div style='font-family:Syne,sans-serif;font-size:0.88rem;font-weight:700;"
        "color:#e6edf3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>"
        + user_name + "</div>"
        "<div style='font-size:0.72rem;color:#8b949e;white-space:nowrap;"
        "overflow:hidden;text-overflow:ellipsis;'>" + user_email + "</div>"
        "</div></div>", unsafe_allow_html=True
    )
    if st.button("🚪 Sign Out", key="sidebar_logout", use_container_width=True):
        logout()
    st.markdown("</div>", unsafe_allow_html=True)


# ================================================================
# PAGE: DASHBOARD
# ================================================================
if page == "🏠  Dashboard":
    history   = load_all_history()
    library   = load_doc_library()
    streak    = compute_streak(history)
    avg_score = round(sum(r["accuracy"] for r in history)/len(history),1) if history else 0
    today     = datetime.now().strftime("%A, %B %d, %Y")
    user_name = _user.get("name", "there")

    badges = [
        "<span style='background:#1f2d40;border:1px solid #1f4068;border-radius:6px;"
        "padding:0.28rem 0.7rem;font-size:0.75rem;color:#58a6ff;font-weight:500;'>📅 " + today + "</span>",
        "<span style='background:#1a2d1a;border:1px solid #238636;border-radius:6px;"
        "padding:0.28rem 0.7rem;font-size:0.75rem;color:#3fb950;font-weight:500;'>📊 Avg: " + str(avg_score) + "%</span>",
    ]
    if streak > 0:
        badges.append(
            "<span style='background:#2d1f00;border:1px solid #d29922;border-radius:6px;"
            "padding:0.28rem 0.7rem;font-size:0.75rem;color:#d29922;font-weight:600;'>🔥 "
            + str(streak) + " day streak</span>"
        )

    st.markdown(
        "<div class='welcome-banner'>"
        "<div style='font-family:Syne,sans-serif;font-size:2.2rem;font-weight:800;"
        "color:#e6edf3;margin-bottom:0.4rem;letter-spacing:-0.02em;'>"
        "Welcome back, " + user_name + "! 👋</div>"
        "<div style='color:#8b949e;font-size:0.95rem;margin-bottom:1.2rem;line-height:1.6;'>"
        "You've studied <span style='color:#388bfd;font-weight:600;'>" + str(len(library)) + " document(s)</span>"
        " and attempted <span style='color:#3fb950;font-weight:600;'>" + str(len(history)) + " quiz(zes)</span>"
        " so far. Keep exploring the cosmos of knowledge 🚀</div>"
        "<div style='display:flex;gap:0.6rem;flex-wrap:wrap;align-items:center;'>"
        + " ".join(badges) + "</div></div>",
        unsafe_allow_html=True
    )

    c1, c2, c3, c4 = st.columns(4)
    for col, lbl, val, sub in [
        (c1, "📄 PDFs Studied",      str(len(library)),  "documents uploaded"),
        (c2, "🧠 Quizzes Attempted", str(len(history)),  "total quizzes taken"),
        (c3, "📊 Average Score",     str(avg_score)+"%", "across all quizzes"),
        (c4, "🔥 Current Streak",    str(streak),        "consecutive days"),
    ]:
        with col:
            st.markdown(
                "<div class='metric-card'><div class='label'>" + lbl + "</div>"
                "<div class='value'>" + val + "</div>"
                "<div class='sub'>" + sub + "</div></div>",
                unsafe_allow_html=True
            )

    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)
    chart_left, chart_right = st.columns([3, 2])

    with chart_left:
        st.markdown("<div class='section-heading'>📈 Quiz Performance Over Time</div>",
                    unsafe_allow_html=True)
        if len(history) >= 2:
            df  = pd.DataFrame([{"Date": r["timestamp"], "Accuracy": r["accuracy"],
                                  "Topic": r["topic"]} for r in history])
            fig = px.line(df, x="Date", y="Accuracy", markers=True,
                          hover_data=["Topic"], color_discrete_sequence=["#388bfd"])
            fig.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22",
                              font_color="#8b949e",
                              yaxis=dict(range=[0,100], gridcolor="#21262d"),
                              xaxis=dict(gridcolor="#21262d"),
                              margin=dict(l=0,r=0,t=10,b=0), height=260)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown("<div style='color:#8b949e;padding:3rem 0;text-align:center;'>"
                        "Take at least 2 quizzes to see your progress chart.</div>",
                        unsafe_allow_html=True)

    with chart_right:
        st.markdown("<div class='section-heading'>⚠️ Top Weak Topics</div>",
                    unsafe_allow_html=True)
        all_weak = [a["topic"] for r in history for a in r.get("weak_areas", [])]
        if all_weak:
            counts = Counter(all_weak).most_common(5)
            wdf    = pd.DataFrame(counts, columns=["Topic","Count"])
            wfig   = px.bar(wdf, x="Count", y="Topic", orientation="h", color="Count",
                            color_continuous_scale=["#3fb950","#d29922","#f85149"])
            wfig.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22",
                               font_color="#8b949e", showlegend=False,
                               coloraxis_showscale=False,
                               xaxis=dict(gridcolor="#21262d"),
                               yaxis=dict(gridcolor="rgba(0,0,0,0)"),
                               margin=dict(l=0,r=0,t=10,b=0), height=260)
            st.plotly_chart(wfig, use_container_width=True)
        else:
            st.markdown("<div style='color:#8b949e;padding:3rem 0;text-align:center;'>"
                        "No weak topics detected yet.</div>", unsafe_allow_html=True)


# ================================================================
# PAGE: MY DOCUMENTS
# ================================================================
elif page == "📄  My Documents":
    st.markdown("<div class='section-heading'>📄 My Document Library</div>",
                unsafe_allow_html=True)
    library = load_doc_library()
    if not library:
        st.markdown("<div style='text-align:center;padding:4rem 0;color:#8b949e;'>"
                    "<div style='font-size:3rem;margin-bottom:1rem;'>📂</div>"
                    "<div style='font-size:1.1rem;'>No documents yet.</div>"
                    "<div style='font-size:0.88rem;margin-top:0.5rem;'>"
                    "Go to Generate Quiz and upload your first PDF.</div></div>",
                    unsafe_allow_html=True)
    else:
        for doc_key, doc in library.items():
            sc = ("#3fb950" if (doc["last_score"] or 0) >= 70
                  else "#d29922" if (doc["last_score"] or 0) >= 40
                  else "#f85149") if doc["last_score"] is not None else "#3fb950"
            ls = f"{doc['last_score']}%" if doc["last_score"] is not None else "Not attempted"
            wb = "".join("<span class='weak-badge weak-red'>" + w + "</span>"
                         for w in doc.get("weak_topics",[])[:3])
            st.markdown(
                "<div class='doc-card'>"
                "<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
                "<div style='flex:1;'>"
                "<div class='doc-title'>📄 " + doc['filename'] + "</div>"
                "<div class='doc-meta'>Topic: " + doc['topic'] + " &nbsp;·&nbsp; Added: "
                + doc['added'] + " &nbsp;·&nbsp; " + str(doc['chunks']) + " chunks</div>"
                "<div style='margin-top:0.6rem;'>" + wb + "</div></div>"
                "<div style='text-align:right;min-width:120px;'>"
                "<div style='font-family:Syne,sans-serif;font-size:1.4rem;font-weight:700;color:"
                + sc + ";'>" + ls + "</div>"
                "<div class='doc-meta'>" + str(doc['quiz_count'])
                + " quiz" + ("zes" if doc['quiz_count']!=1 else "") + "</div>"
                "</div></div></div>",
                unsafe_allow_html=True
            )


# ================================================================
# PAGE: GENERATE QUIZ
# ================================================================
elif page == "🧠  Generate Quiz":
    st.markdown("<div class='section-heading'>🧠 Generate Quiz</div>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1: difficulty = st.selectbox("Difficulty", ["Easy","Medium","Hard"])
    with s2:
        enable_timer = st.checkbox("⏱️ Show time guidance")
        time_limit   = 30
        if enable_timer: time_limit = st.slider("Seconds per question", 15, 120, 30)
    with s3: shuffle_questions = st.checkbox("🔀 Shuffle questions & options", value=True)
    st.divider()

    up1, up2 = st.columns(2)
    with up1:
        st.markdown("**Document 1** (Primary)")
        uploaded_file1 = st.file_uploader("Upload first document",
                                          type=["pdf","docx","txt"], key="uploader1")
    with up2:
        st.markdown("**Document 2** *(Optional — for comparison)*")
        uploaded_file2 = st.file_uploader("Upload second document",
                                          type=["pdf","docx","txt"], key="uploader2")

    if uploaded_file1:
        text1, chunks1 = process_file(uploaded_file1, 1)
        if text1 is None: st.stop()
    if uploaded_file2:
        text2, chunks2 = process_file(uploaded_file2, 2)
        if text2 is None: st.stop()

    if uploaded_file1 and not st.session_state.generated:
        if st.button("🚀 Generate Quiz", key="btn_generate_quiz"):
            st.session_state.quiz_start_time = datetime.now()
            with st.spinner("AI is analyzing your document(s)..."):
                try:
                    if not uploaded_file2:
                        topic = detect_topic(st.session_state.doc1_text)
                        st.session_state.topic = topic
                        best_chunks = retrieve_relevant_chunks(query=topic, doc_id_prefix="doc1", top_k=8)
                        if not best_chunks: best_chunks = st.session_state.doc1_chunks[:8]
                        response = requests.post("http://127.0.0.1:8000/generate-quiz",
                            json={"text":" ".join(best_chunks),"difficulty":difficulty}, timeout=600)
                        if response.status_code != 200: st.error(f"Backend error: {response.text}"); st.stop()
                        questions = response.json().get("questions", [])
                        st.session_state.comparison_result = None
                        doc_key = register_document(uploaded_file1.name, uploaded_file1.size,
                                                    topic, len(st.session_state.doc1_chunks))
                        st.session_state.active_doc_key = doc_key
                    else:
                        similarity, change_type = compare_documents(
                            st.session_state.doc1_text, st.session_state.doc2_text)
                        _, _, chunk_summary = get_detailed_comparison(
                            st.session_state.doc1_chunks, st.session_state.doc2_chunks)
                        st.session_state.comparison_result = {
                            "similarity": similarity, "change_type": change_type,
                            "chunk_summary": chunk_summary}
                        topic = detect_topic(st.session_state.doc2_text)
                        st.session_state.topic = topic
                        if change_type == "same":
                            if st.session_state.questions:
                                questions = st.session_state.questions
                            else:
                                best_chunks = retrieve_relevant_chunks(query=topic, doc_id_prefix="doc1", top_k=8)
                                if not best_chunks: best_chunks = st.session_state.doc1_chunks[:8]
                                response = requests.post("http://127.0.0.1:8000/generate-quiz",
                                    json={"text":" ".join(best_chunks),"difficulty":difficulty}, timeout=600)
                                if response.status_code != 200: st.error(f"Backend error: {response.text}"); st.stop()
                                questions = response.json().get("questions", [])
                        elif change_type == "partial":
                            unmatched = get_unmatched_chunks(st.session_state.doc1_chunks, st.session_state.doc2_chunks)
                            if not unmatched or len(" ".join(unmatched).strip()) < 50:
                                unmatched = st.session_state.doc2_chunks[:8]
                            new_response = requests.post("http://127.0.0.1:8000/generate-quiz",
                                json={"text":" ".join(unmatched),"difficulty":difficulty}, timeout=600)
                            if new_response.status_code != 200: st.error(f"Backend error: {new_response.text}"); st.stop()
                            questions = (st.session_state.questions or [])[:6] + new_response.json().get("questions",[])
                        else:
                            best_chunks = retrieve_relevant_chunks(query=topic, doc_id_prefix="doc2", top_k=8)
                            if not best_chunks: best_chunks = st.session_state.doc2_chunks[:8]
                            response = requests.post("http://127.0.0.1:8000/generate-quiz",
                                json={"text":" ".join(best_chunks),"difficulty":difficulty}, timeout=600)
                            if response.status_code != 200: st.error(f"Backend error: {response.text}"); st.stop()
                            questions = response.json().get("questions", [])
                        doc_key = register_document(uploaded_file2.name, uploaded_file2.size,
                                                    topic, len(st.session_state.doc2_chunks))
                        st.session_state.active_doc_key = doc_key

                    clean_questions = [q for q in questions
                                       if isinstance(q, dict) and "question" in q
                                       and "type" in q and "answer" in q
                                       and (q["type"] != "mcq" or "options" in q)]
                    if not clean_questions: st.error("No valid questions generated."); st.stop()
                    if shuffle_questions:
                        random.shuffle(clean_questions)
                        for q in clean_questions:
                            if q["type"] == "mcq":
                                correct = q["answer"]; random.shuffle(q["options"]); q["answer"] = correct
                    st.session_state.questions  = clean_questions[:25]
                    st.session_state.answers    = {}
                    st.session_state.generated  = True
                    st.session_state.difficulty = difficulty
                except requests.exceptions.Timeout:
                    st.error("⏱️ Ollama timed out."); st.stop()
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot reach backend. Run uvicorn on port 8000."); st.stop()
            st.success(f"✅ Quiz ready — {len(st.session_state.questions)} questions!")

    if st.session_state.generated and st.session_state.comparison_result:
        comp = st.session_state.comparison_result
        spct = comp["similarity"] * 100
        ct   = comp["change_type"]
        sm   = comp.get("chunk_summary")
        clr  = {"same":"🟢","partial":"🟡","different":"🔴"}[ct]
        lbl  = {"same":"Highly Similar","partial":"Partially Similar","different":"Different"}[ct]
        st.markdown("### 📊 Document Comparison")
        st.markdown(f"{clr} **{lbl}** — Similarity Score: `{spct:.1f}%`")
        b1,b2,b3 = st.columns(3)
        b1.metric("Similarity", f"{spct:.1f}%"); b2.metric("Match Type", lbl)
        b3.metric("Questions", len(st.session_state.questions))
        if sm:
            ch1,ch2,ch3,ch4 = st.columns(4)
            ch1.metric("✅ Unchanged", sm["unchanged_count"], f"{sm['pct_unchanged']}%")
            ch2.metric("✏️ Modified",  sm["modified_count"],  f"{sm['pct_modified']}%")
            ch3.metric("🆕 New",       sm["new_count"],       f"{sm['pct_new']}%")
            ch4.metric("🗑️ Removed",   sm["removed_count"],   f"-{sm['pct_removed']}%")
            with st.expander("📋 View Detailed Change Log"):
                for section, key, header in [
                    (sm.get("new_chunks",[]),      "doc2_preview",         "##### 🆕 New Content"),
                    (sm.get("modified_chunks",[]), "doc2_preview",         "##### ✏️ Modified Content"),
                    (sm.get("removed_chunks",[]),  "doc1_preview",         "##### 🗑️ Removed Content"),
                ]:
                    if section:
                        st.markdown(header)
                        for chunk in section:
                            st.markdown(f"- **Chunk {chunk['chunk_index']+1}** *(similarity: {chunk['similarity']})*")
                            st.caption(chunk[key])
        st.divider()

    if st.session_state.generated and st.session_state.questions:
        st.markdown("<div class='section-heading'>📝 Answer the Questions</div>",
                    unsafe_allow_html=True)
        st.info(f"📚 {st.session_state.topic}  &nbsp;&nbsp;🎯 {st.session_state.difficulty}")
        tq = len(st.session_state.questions)
        answered = sum(1 for i in range(tq) if st.session_state.answers.get(i))
        st.progress(answered / tq)
        st.caption(f"Answered {answered} / {tq}")

        for i, q in enumerate(st.session_state.questions):
            st.markdown(f"### Question {i+1}")
            if enable_timer: st.caption(f"⏱️ Suggested time: {time_limit} seconds")
            st.write(q["question"])
            if q["type"] == "mcq":
                ans = st.radio("Select answer", q["options"], key=f"mcq_{i}")
            elif q["type"] == "true_false":
                ans = st.radio("Select answer", ["True","False"], key=f"tf_{i}")
            else:
                ans = st.text_area("Your answer", key=f"exp_{i}")
            st.session_state.answers[i] = ans
            st.divider()

        if st.button("✅ Submit Quiz", key="btn_submit_quiz"):
            st.header("📊 Quiz Results")
            score = 0; unanswered = 0
            for i, q in enumerate(st.session_state.questions):
                ua = st.session_state.answers.get(i, "")
                ca = q["answer"]
                st.markdown(f"### Question {i+1}"); st.write(q["question"])
                if not ua:
                    st.warning("⚠️ Unanswered"); st.write(f"**Correct Answer:** {ca}")
                    unanswered += 1; st.divider(); continue
                st.write(f"**Your Answer:** {ua}"); st.write(f"**Correct Answer:** {ca}")
                ok = (evaluate_answer(q["question"], ca, ua) if q["type"] == "explanation"
                      else str(ua).strip().lower() == str(ca).strip().lower())
                if ok:
                    st.success("✅ Correct"); score += 1
                else:
                    st.error("❌ Incorrect")
                    if q["type"] in ("mcq","true_false"):
                        with st.expander("💡 See explanation"):
                            exp = ask_llm(f'In one sentence explain why "{ca}" is correct for: "{q["question"]}"')
                            if exp: st.write(exp.strip())
                st.divider()

            total    = len(st.session_state.questions)
            wrong    = total - score - unanswered
            accuracy = (score / total) * 100 if total else 0
            time_taken = ""
            if st.session_state.quiz_start_time:
                delta = datetime.now() - st.session_state.quiz_start_time
                time_taken = f"{int(delta.total_seconds()//60)}m {int(delta.total_seconds()%60)}s"

            t1,t2,t3,t4,t5 = st.columns(5)
            t1.metric("Score", f"{score}/{total}"); t2.metric("Accuracy", f"{accuracy:.1f}%")
            t3.metric("Wrong", wrong); t4.metric("Unanswered", unanswered)
            if time_taken: t5.metric("⏱️ Time", time_taken)

            pie_fig = px.pie({"Result":["Correct","Wrong","Unanswered"],"Count":[score,wrong,unanswered]},
                             names="Result", values="Count", title="Quiz Performance",
                             color_discrete_sequence=["#3fb950","#f85149","#d29922"])
            pie_fig.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22", font_color="#8b949e")
            st.plotly_chart(pie_fig, use_container_width=True)

            analysis = recommendations = None
            if wrong + unanswered > 0:
                st.divider(); st.markdown("### 🎯 Performance Analysis")
                with st.spinner("Analyzing your weak areas..."):
                    analysis = analyze_weak_areas(st.session_state.questions, st.session_state.answers)
                if analysis and analysis["weak_areas"]:
                    if accuracy >= 80: st.success(f"🌟 Great job! Score: {accuracy:.1f}%.")
                    elif accuracy >= 50: st.warning(f"📈 Score: {accuracy:.1f}%.")
                    else: st.error(f"📚 Score: {accuracy:.1f}%.")
                    st.markdown("#### ⚠️ Weak Areas")
                    for idx, area in enumerate(analysis["weak_areas"]):
                        wa1, wa2 = st.columns([0.05, 0.95])
                        with wa1: st.markdown(f"**{idx+1}.**")
                        with wa2:
                            st.markdown(f"**{area['topic']}**"); st.caption(area["reason"])
                            st.info(f"💡 {area['review_hint']}")
                    doc_chunks = st.session_state.doc1_chunks or st.session_state.doc2_chunks
                    if doc_chunks:
                        st.markdown("#### 📚 Recommended Review Sections")
                        recommendations = find_review_pages(analysis["weak_areas"], doc_chunks)
                        if recommendations:
                            for rec in recommendations:
                                with st.expander(f"📄 Page ~{rec['estimated_page']} — {rec['topic']} "
                                                 f"(relevance: {int(rec['relevance_score']*100)}%)"):
                                    st.markdown(f"**Topic:** {rec['topic']}")
                                    st.markdown(f"**Why review:** {rec['reason']}")
                                    st.markdown(f"**Focus on:** {rec['review_hint']}")
                                    st.markdown(f"> {rec['chunk_preview']}")
                        else:
                            st.info("Review the topics listed above.")
                    with st.expander(f"❌ View all {analysis['wrong_count']} wrong/unanswered questions"):
                        for wq in analysis["wrong_questions"]:
                            st.markdown(f"**Q:** {wq['question']}")
                            st.markdown(f"**Your answer:** {wq['user_answer'] or '*(unanswered)*'}")
                            st.markdown(f"**Correct answer:** {wq['correct_answer']}"); st.divider()
            else:
                st.balloons(); st.success("🎉 Perfect score!")

            saved_path = save_quiz_result(
                st.session_state.topic, st.session_state.difficulty,
                score, total, st.session_state.questions, st.session_state.answers,
                weak_analysis=analysis, recommendations=recommendations)
            st.info(f"💾 Result saved to `{saved_path}`")

            if st.session_state.active_doc_key:
                update_doc_stats(st.session_state.active_doc_key, score, total,
                    [a["topic"] for a in analysis["weak_areas"]] if analysis and analysis.get("weak_areas") else [])

            st.divider()
            if st.button("📥 Download Results as PDF", key="btn_download_pdf"):
                pdf_bytes = export_pdf(st.session_state.topic, st.session_state.difficulty,
                                       score, total, st.session_state.questions, st.session_state.answers)
                if pdf_bytes:
                    st.download_button("📄 Click to Download PDF", data=pdf_bytes,
                        file_name=f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf", key="btn_dl_pdf_final")
                else:
                    st.warning("Run: `pip install fpdf2`")

            st.divider()
            btn1, btn2 = st.columns(2)
            with btn1:
                if st.button("🔄 Retake Quiz", key="btn_retake"):
                    st.session_state.answers = {}; st.rerun()
            with btn2:
                if st.button("🗑️ Reset Everything", key="btn_reset"):
                    for k in list(st.session_state.keys()): del st.session_state[k]
                    st.rerun()


# ================================================================
# PAGE: ANALYTICS
# ================================================================
elif page == "📊  Analytics":
    st.markdown("<div class='section-heading'>📊 Analytics</div>", unsafe_allow_html=True)
    history = load_all_history()
    if not history: st.info("No quiz data yet. Take a quiz first!"); st.stop()

    avg = round(sum(r["accuracy"] for r in history)/len(history),1)
    a1,a2,a3,a4 = st.columns(4)
    a1.metric("Total Quizzes", len(history)); a2.metric("Average Accuracy", f"{avg}%")
    a3.metric("Best Score", f"{max(r['accuracy'] for r in history)}%")
    a4.metric("Lowest Score", f"{min(r['accuracy'] for r in history)}%")
    st.divider()

    df = pd.DataFrame([{"Date":r["timestamp"],"Accuracy":r["accuracy"],
                         "Topic":r["topic"],"Difficulty":r["difficulty"],
                         "Score":f"{r['score']}/{r['total']}"} for r in history])
    fig1 = px.line(df, x="Date", y="Accuracy", color="Difficulty", markers=True,
                   title="Accuracy Over Time by Difficulty", hover_data=["Topic","Score"],
                   color_discrete_map={"Easy":"#3fb950","Medium":"#d29922","Hard":"#f85149"})
    fig1.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22", font_color="#8b949e",
                       yaxis=dict(range=[0,100],gridcolor="#21262d"), xaxis=dict(gridcolor="#21262d"))
    st.plotly_chart(fig1, use_container_width=True)

    col_l, col_r = st.columns(2)
    fig2 = px.bar(df.groupby("Difficulty")["Accuracy"].mean().reset_index(),
                  x="Difficulty", y="Accuracy", title="Average Accuracy by Difficulty",
                  color="Difficulty",
                  color_discrete_map={"Easy":"#3fb950","Medium":"#d29922","Hard":"#f85149"})
    fig2.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22", font_color="#8b949e",
                       showlegend=False, yaxis=dict(range=[0,100],gridcolor="#21262d"),
                       xaxis=dict(gridcolor="#21262d"))
    with col_l: st.plotly_chart(fig2, use_container_width=True)

    ts = {}
    for r in history:
        ts.setdefault(r["topic"], []).append(r["accuracy"])
    tdf = pd.DataFrame([(t, round(sum(v)/len(v),1)) for t,v in ts.items()],
                       columns=["Topic","Avg Accuracy"]).sort_values("Avg Accuracy")
    fig3 = px.bar(tdf, x="Avg Accuracy", y="Topic", orientation="h",
                  title="Average Score by Topic", color="Avg Accuracy",
                  color_continuous_scale=["#f85149","#d29922","#3fb950"], range_color=[0,100])
    fig3.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22", font_color="#8b949e",
                       coloraxis_showscale=False, xaxis=dict(range=[0,100],gridcolor="#21262d"),
                       yaxis=dict(gridcolor="rgba(0,0,0,0)"))
    with col_r: st.plotly_chart(fig3, use_container_width=True)


# ================================================================
# PAGE: WEAK TOPICS
# ================================================================
elif page == "⚠️  Weak Topics":
    st.markdown("<div class='section-heading'>⚠️ Weak Topics</div>", unsafe_allow_html=True)
    history = load_all_history()
    if not history: st.info("No quiz data yet. Take a quiz first!"); st.stop()

    all_weak = []; twm = {}
    for r in history:
        for area in r.get("weak_areas", []):
            all_weak.append(area["topic"])
            if area["topic"] not in twm: twm[area["topic"]] = {"count":0,"hints":[],"pages":[]}
            twm[area["topic"]]["count"] += 1
            if area.get("review_hint"): twm[area["topic"]]["hints"].append(area["review_hint"])
        for rec in r.get("review_recommendations", []):
            t = rec["topic"]
            if t in twm: twm[t]["pages"].append(rec["estimated_page"])

    if not all_weak: st.success("🎉 No weak topics detected yet!"); st.stop()

    counts = Counter(all_weak).most_common()
    w1,w2,w3 = st.columns(3)
    w1.metric("Unique Weak Topics", len(twm))
    w2.metric("Total Weak Instances", len(all_weak))
    w3.metric("Recurring Topics", sum(1 for _,c in counts if c>1))
    st.divider()

    wdf  = pd.DataFrame(counts, columns=["Topic","Times Weak"])
    wfig = px.bar(wdf, x="Times Weak", y="Topic", orientation="h",
                  title="Weak Topic Frequency", color="Times Weak",
                  color_continuous_scale=["#d29922","#f85149"])
    wfig.update_layout(plot_bgcolor="#161b22", paper_bgcolor="#161b22", font_color="#8b949e",
                       coloraxis_showscale=False, xaxis=dict(gridcolor="#21262d"),
                       yaxis=dict(gridcolor="rgba(0,0,0,0)"))
    st.plotly_chart(wfig, use_container_width=True)
    st.markdown("#### 📋 Topic Detail")

    for tn, cnt in counts:
        data = twm.get(tn, {})
        sev  = "weak-red" if cnt>=3 else "weak-yellow" if cnt==2 else "weak-green"
        slbl = "🔴 High Priority" if cnt>=3 else "🟡 Medium Priority" if cnt==2 else "🟢 Low Priority"
        pages = sorted(set(data.get("pages",[])))
        ps    = ", ".join([f"~p.{p}" for p in pages[:3]]) if pages else "Not pinpointed"
        hs    = list(set(data.get("hints",[])))
        hint  = hs[0] if hs else "Review this topic in your notes."
        st.markdown(
            "<div class='doc-card'>"
            "<div style='display:flex;justify-content:space-between;align-items:flex-start;'>"
            "<div><div class='doc-title'>" + tn + "</div>"
            "<div class='doc-meta' style='margin-top:0.3rem;'>📄 " + ps + "</div>"
            "<div style='color:#8b949e;font-size:0.85rem;margin-top:0.4rem;'>💡 " + hint + "</div></div>"
            "<div style='text-align:right;'>"
            "<span class='weak-badge " + sev + "'>" + slbl + "</span>"
            "<div class='doc-meta' style='margin-top:0.4rem;'>Weak in " + str(cnt)
            + " quiz" + ("zes" if cnt!=1 else "") + "</div></div></div></div>",
            unsafe_allow_html=True
        )


# ================================================================
# PAGE: PROFILE
# ================================================================
elif page == "👤  Profile":
    st.markdown("<div class='section-heading'>👤 My Profile</div>", unsafe_allow_html=True)
    user        = get_current_user()
    user_name   = user.get("name",""); user_email  = user.get("email","")
    institution = user.get("institution","") or ""; standard = user.get("standard","") or ""
    joined      = user.get("created_at","")[:10]
    last_login  = (user.get("last_login","") or "")[:10]
    user_initial = user_name[0].upper() if user_name else "U"

    history   = load_all_history(); library = load_doc_library()
    streak    = compute_streak(history)
    avg_score = round(sum(r["accuracy"] for r in history)/len(history),1) if history else 0

    left_col, right_col = st.columns([1, 2])
    with left_col:
        st.markdown("<div class='profile-card' style='text-align:center;'>", unsafe_allow_html=True)
        st.markdown(
            "<div style='width:90px;height:90px;border-radius:50%;"
            "background:linear-gradient(135deg,#1f6feb,#388bfd);"
            "display:flex;align-items:center;justify-content:center;"
            "font-family:Syne,sans-serif;font-size:2.2rem;font-weight:800;color:#fff;"
            "margin:0 auto 1rem auto;box-shadow:0 4px 20px rgba(56,139,253,0.35);'>"
            + user_initial + "</div>"
            "<div style='font-family:Syne,sans-serif;font-size:1.2rem;font-weight:700;"
            "color:#e6edf3;margin-bottom:0.2rem;'>" + user_name + "</div>"
            "<div style='font-size:0.82rem;color:#8b949e;margin-bottom:1.2rem;'>" + user_email + "</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            "<div style='display:grid;grid-template-columns:1fr 1fr;gap:0.6rem;margin-top:0.5rem;'>"
            + "".join(
                "<div style='background:rgba(13,17,23,0.6);border:1px solid #21262d;"
                "border-radius:10px;padding:0.7rem;text-align:center;'>"
                "<div style='font-family:Syne,sans-serif;font-size:1.3rem;font-weight:700;color:"
                + clr + ";'>" + val + "</div>"
                "<div style='font-size:0.7rem;color:#8b949e;'>" + lbl + "</div></div>"
                for clr, val, lbl in [
                    ("#388bfd", str(len(library)),  "Docs"),
                    ("#3fb950", str(len(history)),  "Quizzes"),
                    ("#d29922", str(streak),        "Streak"),
                    ("#f85149", str(avg_score)+"%", "Avg"),
                ]
            ) + "</div>",
            unsafe_allow_html=True
        )
        if joined or last_login:
            st.markdown(
                "<div style='margin-top:1.2rem;font-size:0.75rem;color:#8b949e;line-height:1.8;'>"
                + ("📅 Joined: " + joined if joined else "")
                + ("<br>" if joined and last_login else "")
                + ("🕐 Last login: " + last_login if last_login else "")
                + "</div>", unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)

    if "profile_editing" not in st.session_state:
        st.session_state["profile_editing"] = False

    with right_col:
        if not st.session_state["profile_editing"]:
            st.markdown("<div class='profile-card'>", unsafe_allow_html=True)
            hd1, hd2 = st.columns([3,1])
            with hd1:
                st.markdown("<div style='font-family:Syne,sans-serif;font-size:1.1rem;"
                            "font-weight:700;color:#e6edf3;'>🔐 Profile Details</div>",
                            unsafe_allow_html=True)
            with hd2:
                if st.button("✏️ Edit", key="btn_start_edit", use_container_width=True):
                    st.session_state["profile_editing"] = True; st.rerun()
            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            rows = [("Full Name",user_name or "—"),("Email",user_email or "—"),
                    ("Institution",institution or "—"),("Standard / Year",standard or "—"),
                    ("Member Since",joined or "—"),("Last Login",last_login or "—")]
            st.markdown("".join(
                "<div class='info-row'>"
                "<span class='info-label'>" + l + "</span>"
                "<span class='info-value'>" + v + "</span></div>"
                for l,v in rows), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='profile-card'>", unsafe_allow_html=True)
            hd1, hd2 = st.columns([3,1])
            with hd1:
                st.markdown("<div style='font-family:Syne,sans-serif;font-size:1.1rem;"
                            "font-weight:700;color:#e6edf3;'>✏️ Edit Profile</div>",
                            unsafe_allow_html=True)
            with hd2:
                if st.button("✕ Cancel", key="btn_cancel_edit", use_container_width=True):
                    st.session_state["profile_editing"] = False; st.rerun()
            std_opts = ["","Class 6","Class 7","Class 8","Class 9","Class 10",
                        "Class 11 (Science)","Class 11 (Commerce)","Class 11 (Arts)",
                        "Class 12 (Science)","Class 12 (Commerce)","Class 12 (Arts)",
                        "1st Year (UG)","2nd Year (UG)","3rd Year (UG)","4th Year (UG)",
                        "Postgraduate (PG)","PhD / Research","Other"]
            cur_idx = std_opts.index(standard) if standard in std_opts else 0
            with st.form("profile_form"):
                new_name = st.text_input("Full Name", value=user_name)
                new_inst = st.text_input("School / College / University", value=institution)
                new_std  = st.selectbox("Standard / Year", std_opts, index=cur_idx)
                save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
            if save_btn:
                if not new_name or len(new_name.strip()) < 2:
                    st.error("⚠️ Name must be at least 2 characters.")
                else:
                    with st.spinner("Saving..."):
                        updated, error = api_update_profile(
                            name=new_name.strip(), institution=new_inst.strip(), standard=new_std)
                    if error: st.error(f"❌ {error}")
                    else:
                        st.session_state["profile_editing"] = False
                        st.success("✅ Profile updated!"); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-top:0.8rem;'>", unsafe_allow_html=True)
        if st.button("🚪 Sign Out", key="profile_logout", use_container_width=True):
            logout()
        st.markdown("</div>", unsafe_allow_html=True)


# ================================================================
# PAGE: FLASHCARDS
# ================================================================
elif page == "🃏  Flashcards":
    st.markdown("<div class='section-heading'>🃏 Flashcards</div>", unsafe_allow_html=True)
    for k, v in {"fc_explanation":None,"fc_flashcards":[],"fc_doc_id":None,
                  "fc_known":set(),"fc_reviewing":set()}.items():
        if k not in st.session_state: st.session_state[k] = v

    st.markdown(
        "<div style='background:rgba(22,27,34,0.7);border:1px dashed #30363d;"
        "border-radius:14px;padding:1.2rem 1.6rem;margin-bottom:1.2rem;'>"
        "<div style='font-family:Syne,sans-serif;font-size:1rem;font-weight:700;"
        "color:#e6edf3;margin-bottom:0.3rem;'>📄 Upload a document to get started</div>"
        "<div style='font-size:0.82rem;color:#8b949e;'>"
        "Ollama will explain the document and generate interactive 3D flip flashcards.</div></div>",
        unsafe_allow_html=True)

    fc_file = st.file_uploader("Upload PDF / DOCX / TXT", type=["pdf","docx","txt"],
                                key="fc_uploader", label_visibility="collapsed")
    col_a, col_b = st.columns(2)
    with col_a: fc_num = st.slider("Number of flashcards", 5, 25, 10, key="fc_num")
    with col_b:
        fc_detail = st.selectbox("Explanation depth",
            ["Brief (2-3 sentences per topic)","Standard (full paragraph per topic)",
             "Detailed (in-depth with examples)"], key="fc_detail")

    if st.button("✨ Explain & Generate Flashcards", key="btn_fc_generate", use_container_width=True):
        if not fc_file:
            st.warning("⚠️ Please upload a file first.")
        else:
            file_id = f"{fc_file.name}_{fc_file.size}"
            if st.session_state.fc_doc_id != file_id:
                st.session_state.fc_explanation = None; st.session_state.fc_flashcards = []
                st.session_state.fc_known = set(); st.session_state.fc_reviewing = set()
            with st.spinner("📖 Reading document..."):
                text   = load_document(fc_file); chunks = chunk_text(text)
                if not chunks: st.error("Could not extract text."); st.stop()
            dm = {"Brief (2-3 sentences per topic)":"Write 2-3 sentences per topic. Be concise.",
                  "Standard (full paragraph per topic)":"Write one clear paragraph per topic.",
                  "Detailed (in-depth with examples)":"Write detailed paragraphs with examples."}
            with st.spinner("🧠 Generating explanation..."):
                explanation = ask_llm(
                    "You are an expert teacher. Explain this study material clearly.\n"
                    "- Identify 4-6 main topics\n"
                    "- For each topic write: ## Topic Name\\nExplanation\n"
                    f"- {dm[fc_detail]}\n\nDocument:\n{' '.join(chunks[:12])[:6000]}\n\nExplain now:")
                st.session_state.fc_explanation = explanation or "Could not generate."
            with st.spinner(f"🃏 Generating {fc_num} flashcards..."):
                raw = ask_llm(
                    f"Create exactly {fc_num} flashcards from the study material below.\n"
                    "Each flashcard MUST follow this exact format on its own line:\n"
                    "CARD|<question or term>|<concise answer (1-3 sentences)>\n\n"
                    f"Document:\n{' '.join(chunks[:15])[:8000]}\n\nGenerate exactly {fc_num} CARD| lines now:") or ""
                cards = []
                for line in raw.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("CARD|"):
                        parts = line.split("|", 2)
                        if len(parts) == 3:
                            cards.append({"question":parts[1].strip(),"answer":parts[2].strip()})
                if not cards:
                    for line in raw.strip().split("\n"):
                        if "|" in line:
                            parts = line.split("|",2)
                            if len(parts) >= 2 and len(parts[-1]) > 5:
                                q = parts[-2].strip().lstrip("0123456789.). ")
                                a = parts[-1].strip()
                                if q and a: cards.append({"question":q,"answer":a})
                st.session_state.fc_flashcards = cards; st.session_state.fc_doc_id = file_id
            st.success(f"✅ {len(st.session_state.fc_flashcards)} flashcards ready!")

    if st.session_state.fc_explanation:
        with st.expander("📖 Document Explanation", expanded=False):
            for line in st.session_state.fc_explanation.split("\n"):
                line = line.strip()
                if not line: st.markdown("")
                elif line.startswith("## "):
                    st.markdown("<div style='font-family:Syne,sans-serif;font-size:1rem;"
                                "font-weight:700;color:#388bfd;margin-top:0.8rem;'>"
                                + line[3:] + "</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='font-size:0.88rem;color:#c9d1d9;line-height:1.65;'>"
                                + line + "</div>", unsafe_allow_html=True)

    if st.session_state.fc_flashcards:
        cards = st.session_state.fc_flashcards; total = len(cards)
        known_cnt = len(st.session_state.fc_known); rev_cnt = len(st.session_state.fc_reviewing)
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        st.markdown("<div class='section-heading'>🃏 Your Flashcards</div>", unsafe_allow_html=True)
        if total > 0: st.progress(known_cnt / total)

        card_html_parts = []
        for idx, card in enumerate(cards):
            q = card["question"].replace("'","&#39;").replace('"',"&quot;")
            a = card["answer"].replace("'","&#39;").replace('"',"&quot;")
            if idx in st.session_state.fc_known:         bc,bb,bbd,bt = "#3fb950","#0d2d1a","#238636","✅ Known"
            elif idx in st.session_state.fc_reviewing:   bc,bb,bbd,bt = "#d29922","#2d2208","#d29922","🔄 Reviewing"
            else:                                         bc,bb,bbd,bt = "#8b949e","#161b22","#30363d","📖 New"
            card_html_parts.append(
                "<div class='fc-card-wrapper'>"
                "<div class='fc-scene' onclick='flipCard(" + str(idx) + ")'>"
                "<div class='fc-card' id='card-" + str(idx) + "'>"
                "<div class='fc-face fc-front'>"
                "<div class='fc-face-label'>Question</div>"
                "<div class='fc-face-text'>" + q + "</div>"
                "<div class='fc-face-hint'>👆 Click to reveal answer</div></div>"
                "<div class='fc-face fc-back'>"
                "<div class='fc-face-label' style='color:#3fb950;'>Answer</div>"
                "<div class='fc-face-text' style='font-size:0.88rem;font-weight:400;line-height:1.6;'>" + a + "</div>"
                "<div class='fc-face-hint'>👆 Click to flip back</div></div></div></div>"
                "<div style='text-align:center;margin:0.5rem 0 0.3rem;'>"
                "<span style='font-size:0.72rem;color:" + bc + ";background:" + bb + ";"
                "border:1px solid " + bbd + ";border-radius:20px;padding:0.2rem 0.6rem;font-weight:600;'>"
                + bt + "</span></div></div>"
            )

        import streamlit.components.v1 as components
        components.html(
            "<!DOCTYPE html><html style='background:#0d1117;'><head><style>"
            "*{box-sizing:border-box;margin:0;padding:0;}"
            "html,body{background:#0d1117!important;font-family:'DM Sans',sans-serif;padding:4px;}"
            ".fc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}"
            ".fc-card-wrapper{display:flex;flex-direction:column;}"
            ".fc-scene{width:100%;height:200px;perspective:900px;cursor:pointer;}"
            ".fc-card{width:100%;height:100%;position:relative;transform-style:preserve-3d;"
            "transition:transform 0.6s cubic-bezier(0.4,0,0.2,1);border-radius:14px;}"
            ".fc-card.is-flipped{transform:rotateY(180deg);}"
            ".fc-face{position:absolute;inset:0;border-radius:14px;padding:16px 18px;"
            "backface-visibility:hidden;-webkit-backface-visibility:hidden;"
            "display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;}"
            ".fc-front{background:linear-gradient(135deg,#1c2d40 0%,#162032 100%);"
            "border:1px solid #1f4068;}"
            ".fc-back{background:linear-gradient(135deg,#0d2d1a 0%,#091a0f 100%);"
            "border:1px solid #238636;transform:rotateY(180deg);}"
            ".fc-scene:hover .fc-card:not(.is-flipped){transform:rotateY(8deg) translateY(-4px);}"
            ".fc-scene:hover .fc-card.is-flipped{transform:rotateY(172deg) translateY(-4px);}"
            ".fc-face-label{font-size:0.6rem;text-transform:uppercase;letter-spacing:0.12em;"
            "font-weight:700;color:#388bfd;margin-bottom:6px;}"
            ".fc-face-text{font-size:0.9rem;font-weight:700;color:#e6edf3;line-height:1.45;"
            "flex:1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;}"
            ".fc-face-hint{font-size:0.63rem;color:rgba(139,148,158,0.7);margin-top:8px;}"
            "</style></head><body>"
            "<div class='fc-grid'>" + "\n".join(card_html_parts) + "</div>"
            "<script>var flipped={};"
            "function flipCard(idx){var card=document.getElementById('card-'+idx);"
            "if(!card)return;flipped[idx]=!flipped[idx];"
            "if(flipped[idx]){card.classList.add('is-flipped');}else{card.classList.remove('is-flipped');}}"
            "</script></body></html>",
            height=max(280, ((total+2)//3)*290), scrolling=False
        )

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.82rem;color:#8b949e;margin-bottom:0.6rem;'>"
                    "Mark cards below to track your progress:</div>", unsafe_allow_html=True)

        for row_start in range(0, total, 5):
            row_cards = list(range(row_start, min(row_start+5, total)))
            cols = st.columns(len(row_cards))
            for col, idx in zip(cols, row_cards):
                with col:
                    is_known = idx in st.session_state.fc_known
                    is_rev   = idx in st.session_state.fc_reviewing
                    st.markdown("<div style='font-size:0.68rem;color:#8b949e;text-align:center;"
                                "margin-bottom:3px;'>Card " + str(idx+1) + "</div>",
                                unsafe_allow_html=True)
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("✅" if is_known else "☑", key=f"fc_k_{idx}",
                                     use_container_width=True, help="Mark as Known"):
                            if is_known: st.session_state.fc_known.discard(idx)
                            else:
                                st.session_state.fc_known.add(idx)
                                st.session_state.fc_reviewing.discard(idx)
                            st.rerun()
                    with b2:
                        if st.button("🔄" if is_rev else "↩", key=f"fc_r_{idx}",
                                     use_container_width=True, help="Still Learning"):
                            if is_rev: st.session_state.fc_reviewing.discard(idx)
                            else:
                                st.session_state.fc_reviewing.add(idx)
                                st.session_state.fc_known.discard(idx)
                            st.rerun()

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        act1, act2, act3 = st.columns(3)
        with act1:
            if st.button("🔀 Shuffle Cards", key="fc_shuffle", use_container_width=True):
                random.shuffle(st.session_state.fc_flashcards); st.rerun()
        with act2:
            if st.button("🔁 Reset Progress", key="fc_reset", use_container_width=True):
                st.session_state.fc_known = set(); st.session_state.fc_reviewing = set(); st.rerun()
        with act3:
            if st.button("🗑️ Clear All", key="fc_clear", use_container_width=True):
                for k in ["fc_explanation","fc_flashcards","fc_doc_id"]:
                    st.session_state[k] = None if k != "fc_flashcards" else []
                st.session_state.fc_known = set(); st.session_state.fc_reviewing = set(); st.rerun()

        if known_cnt == total and total > 0:
            st.balloons()
            st.success(f"🎉 You've marked all {total} cards as known — you've mastered this document!")


# ================================================================
# PAGE: SETTINGS
# ================================================================
elif page == "⚙️  Settings":
    st.markdown("<div class='section-heading'>⚙️ Settings</div>", unsafe_allow_html=True)
    st.markdown("#### 🗑️ Data Management")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Clear My Quiz History", key="btn_clear_history"):
            import shutil
            hdir = _history_dir()
            shutil.rmtree(hdir); os.makedirs(hdir)
            st.success("✅ Your quiz history cleared.")
    with col_s2:
        if st.button("Clear My Document Library", key="btn_clear_library"):
            lp = _lib_path()
            if os.path.exists(lp): os.remove(lp)
            st.success("✅ Your document library cleared.")
    st.divider()
    st.markdown("#### ℹ️ About")
    st.markdown("""
    <div class='doc-card'>
        <div class='doc-title'>DocuMind AI</div>
        <div class='doc-meta'>Smart document-based quiz generator with RAG, semantic versioning,
        weak topic detection, and LMS-style analytics.</div>
        <div style='margin-top:0.8rem;color:#8b949e;font-size:0.82rem;'>
        Built with Streamlit · FastAPI · ChromaDB · Ollama · LLaMA 3.2</div>
    </div>""", unsafe_allow_html=True)
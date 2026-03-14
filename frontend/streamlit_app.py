import sys
import os
import json
import random
from datetime import datetime

os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px
import pandas as pd
import requests

from document_processing.loaders.pdf_loader import load_document
from document_processing.preprocessing.chunker import chunk_text
from ai_engine.rag.chunk_retriever import index_document, retrieve_relevant_chunks
from backend.services.answer_evaluator import evaluate_answer
from ai_engine.llm.ollama_client import ask_llm
from semantic_versioning.document_comparator import (
    compare_documents,
    get_unmatched_chunks
)

st.set_page_config(page_title="DocuMind AI", page_icon="📘", layout="wide")


# ---------------- HELPERS ----------------

def save_quiz_result(topic, difficulty, score, total, questions, answers):
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic,
        "difficulty": difficulty,
        "score": score,
        "total": total,
        "accuracy": round((score / total) * 100, 1) if total else 0,
        "questions": [
            {
                "question": q["question"],
                "type": q["type"],
                "correct_answer": q["answer"],
                "user_answer": answers.get(i, ""),
            }
            for i, q in enumerate(questions)
        ]
    }

    os.makedirs("data/question_bank", exist_ok=True)
    filename = f"data/question_bank/quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, "w") as f:
        json.dump(result, f, indent=2)

    return filename


def export_pdf(topic, difficulty, score, total, questions, answers):
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "DocuMind AI Quiz Results", ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"Topic: {topic}", ln=True)
    pdf.cell(0, 8, f"Difficulty: {difficulty}", ln=True)
    pdf.cell(0, 8, f"Score: {score}/{total}", ln=True)
    pdf.cell(0, 8, f"Accuracy: {round((score / total) * 100, 1) if total else 0}%", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(5)

    for i, q in enumerate(questions):
        user_ans = answers.get(i, "Unanswered")
        correct = str(user_ans).strip().lower() == str(q["answer"]).strip().lower()
        icon = "CORRECT" if correct else "INCORRECT"

        pdf.set_font("Helvetica", "B", 11)
        question_text = q["question"].encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 7, f"Q{i+1}: {question_text}")

        pdf.set_font("Helvetica", "", 10)
        user_text = str(user_ans).encode("latin-1", "replace").decode("latin-1")
        correct_text = str(q["answer"]).encode("latin-1", "replace").decode("latin-1")

        pdf.cell(0, 6, f"Your Answer: {user_text} [{icon}]", ln=True)
        if not correct:
            pdf.cell(0, 6, f"Correct Answer: {correct_text}", ln=True)
        pdf.ln(3)

    return bytes(pdf.output())


def detect_topic(text):
    prompt = f"""Identify the main topic of the following study material.
Return ONLY the topic name. No explanation, no extra text, just the topic.

{text[:2000]}"""
    topic = ask_llm(prompt)
    return topic.strip() if topic else "General Topic"


# ---------------- NAVIGATION ----------------

page = st.sidebar.radio("Navigation", ["🏠 Quiz", "📊 History"])


# ================================================================
# HISTORY PAGE
# ================================================================

if page == "📊 History":

    st.title("📊 Quiz History")

    history_dir = "data/question_bank"

    if not os.path.exists(history_dir) or not os.listdir(history_dir):
        st.info("No quiz history yet. Take a quiz first!")
        st.stop()

    files = sorted(
        [f for f in os.listdir(history_dir) if f.endswith(".json")],
        reverse=True
    )

    # ---------------- PERFORMANCE CHART ----------------
    if len(files) > 1:
        history_data = []
        for filename in sorted(files):
            try:
                with open(f"{history_dir}/{filename}") as f:
                    r = json.load(f)
                history_data.append({
                    "Date": r["timestamp"],
                    "Accuracy": r["accuracy"],
                    "Topic": r["topic"],
                    "Score": f"{r['score']}/{r['total']}"
                })
            except Exception:
                continue

        if history_data:
            df = pd.DataFrame(history_data)
            fig = px.line(
                df,
                x="Date",
                y="Accuracy",
                title="📈 Your Accuracy Over Time",
                markers=True,
                hover_data=["Topic", "Score"]
            )
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
            st.divider()

    # ---------------- QUIZ LIST ----------------
    st.subheader("Past Quizzes")

    for filename in files:
        try:
            with open(f"{history_dir}/{filename}") as f:
                result = json.load(f)
        except Exception:
            continue

        accuracy = result.get("accuracy", 0)
        icon = "🟢" if accuracy >= 70 else "🟡" if accuracy >= 40 else "🔴"

        with st.expander(
            f"{icon} {result['topic']} | {result['difficulty']} | "
            f"Score: {result['score']}/{result['total']} ({accuracy}%) | "
            f"{result['timestamp']}"
        ):
            col1, col2, col3 = st.columns(3)
            col1.metric("Score", f"{result['score']}/{result['total']}")
            col2.metric("Accuracy", f"{accuracy}%")
            col3.metric("Difficulty", result["difficulty"])
            st.divider()

            for i, q in enumerate(result["questions"]):
                user_ans = q.get("user_answer", "")
                correct = (
                    str(user_ans).strip().lower() ==
                    str(q["correct_answer"]).strip().lower()
                )
                icon_q = "✅" if correct else ("⚠️" if not user_ans else "❌")

                st.markdown(f"**{icon_q} Q{i+1}:** {q['question']}")
                st.write(f"Your answer: {user_ans or 'Unanswered'}")
                if not correct:
                    st.write(f"Correct answer: {q['correct_answer']}")
                st.divider()

    st.stop()


# ================================================================
# QUIZ PAGE
# ================================================================

st.title("📘 DocuMind AI – Smart Quiz Generator")

# ---------------- SETTINGS ----------------
col_diff, col_timer, col_shuffle = st.columns(3)

with col_diff:
    difficulty = st.selectbox("Select Quiz Difficulty", ["Easy", "Medium", "Hard"])

with col_timer:
    enable_timer = st.checkbox("⏱️ Show time guidance")
    time_limit = 30
    if enable_timer:
        time_limit = st.slider("Seconds per question", 15, 120, 30)

with col_shuffle:
    shuffle_questions = st.checkbox("🔀 Shuffle questions & options", value=True)


# ---------------- SESSION STATE ----------------
for key, default in {
    "questions": [],
    "answers": {},
    "generated": False,
    "topic": "",
    "doc1_text": None,
    "doc2_text": None,
    "doc1_chunks": [],
    "doc2_chunks": [],
    "doc1_id": None,
    "doc2_id": None,
    "difficulty": "Medium",
    "comparison_result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------- FILE UPLOAD ----------------
st.subheader("📂 Upload Documents")
col_up1, col_up2 = st.columns(2)

with col_up1:
    st.markdown("**Document 1** (Primary)")
    uploaded_file1 = st.file_uploader(
        "Upload first document",
        type=["pdf", "docx", "txt"],
        key="uploader1"
    )

with col_up2:
    st.markdown("**Document 2** *(Optional — for comparison)*")
    uploaded_file2 = st.file_uploader(
        "Upload second document",
        type=["pdf", "docx", "txt"],
        key="uploader2"
    )


# ---------------- PROCESS UPLOADS ----------------
def process_file(uploaded_file, slot):
    file_id = f"{uploaded_file.name}_{uploaded_file.size}"

    if st.session_state[f"doc{slot}_id"] != file_id:
        with st.spinner(f"Processing Document {slot}..."):
            text = load_document(uploaded_file)
            chunks = chunk_text(text)

            if not chunks:
                st.error(
                    f"Document {slot} could not be chunked. "
                    "Check the file has readable text."
                )
                st.stop()

            index_document(chunks, doc_id=f"doc{slot}")
            st.session_state[f"doc{slot}_text"] = text
            st.session_state[f"doc{slot}_chunks"] = chunks
            st.session_state[f"doc{slot}_id"] = file_id
            st.session_state.generated = False

        st.success(f"✅ Document {slot} ready — {len(chunks)} chunks")

    return (
        st.session_state[f"doc{slot}_text"],
        st.session_state[f"doc{slot}_chunks"]
    )


if uploaded_file1:
    doc1_text, doc1_chunks = process_file(uploaded_file1, 1)

if uploaded_file2:
    doc2_text, doc2_chunks = process_file(uploaded_file2, 2)


# ---------------- GENERATE QUIZ ----------------
if uploaded_file1 and not st.session_state.generated:

    if st.button("🚀 Generate Quiz"):

        with st.spinner("AI is analyzing your document(s)... this may take a few minutes."):

            try:

                # ---------------- SINGLE DOCUMENT ----------------
                if not uploaded_file2:

                    topic = detect_topic(st.session_state.doc1_text)
                    st.session_state.topic = topic

                    best_chunks = retrieve_relevant_chunks(
                        query=topic, doc_id_prefix="doc1", top_k=8
                    )
                    if not best_chunks:
                        best_chunks = st.session_state.doc1_chunks[:8]

                    response = requests.post(
                        "http://127.0.0.1:8000/generate-quiz",
                        json={
                            "text": " ".join(best_chunks),
                            "difficulty": difficulty
                        },
                        timeout=600
                    )

                    if response.status_code != 200:
                        st.error(f"Backend error: {response.text}")
                        st.stop()

                    questions = response.json().get("questions", [])
                    st.session_state.comparison_result = None

                # ---------------- TWO DOCUMENTS ----------------
                else:

                    similarity, change_type = compare_documents(
                        st.session_state.doc1_text,
                        st.session_state.doc2_text
                    )

                    st.session_state.comparison_result = {
                        "similarity": similarity,
                        "change_type": change_type
                    }

                    topic = detect_topic(st.session_state.doc2_text)
                    st.session_state.topic = topic

                    # SAME
                    if change_type == "same":
                        if st.session_state.questions:
                            questions = st.session_state.questions
                        else:
                            best_chunks = retrieve_relevant_chunks(
                                query=topic, doc_id_prefix="doc1", top_k=8
                            )
                            if not best_chunks:
                                best_chunks = st.session_state.doc1_chunks[:8]
                            response = requests.post(
                                "http://127.0.0.1:8000/generate-quiz",
                                json={
                                    "text": " ".join(best_chunks),
                                    "difficulty": difficulty
                                },
                                timeout=600
                            )
                            if response.status_code != 200:
                                st.error(f"Backend error: {response.text}")
                                st.stop()
                            questions = response.json().get("questions", [])

                    # PARTIAL
                    elif change_type == "partial":
                        unmatched = get_unmatched_chunks(
                            st.session_state.doc1_chunks,
                            st.session_state.doc2_chunks
                        )
                        if not unmatched or len(" ".join(unmatched).strip()) < 50:
                            unmatched = st.session_state.doc2_chunks[:8]

                        new_response = requests.post(
                            "http://127.0.0.1:8000/generate-quiz",
                            json={
                                "text": " ".join(unmatched),
                                "difficulty": difficulty
                            },
                            timeout=600
                        )
                        if new_response.status_code != 200:
                            st.error(f"Backend error: {new_response.text}")
                            st.stop()

                        new_questions = new_response.json().get("questions", [])
                        old_questions = st.session_state.questions or []
                        questions = old_questions[:6] + new_questions

                    # DIFFERENT
                    else:
                        best_chunks = retrieve_relevant_chunks(
                            query=topic, doc_id_prefix="doc2", top_k=8
                        )
                        if not best_chunks:
                            best_chunks = st.session_state.doc2_chunks[:8]

                        response = requests.post(
                            "http://127.0.0.1:8000/generate-quiz",
                            json={
                                "text": " ".join(best_chunks),
                                "difficulty": difficulty
                            },
                            timeout=600
                        )
                        if response.status_code != 200:
                            st.error(f"Backend error: {response.text}")
                            st.stop()
                        questions = response.json().get("questions", [])

                # ---------------- CLEAN ----------------
                clean_questions = [
                    q for q in questions
                    if isinstance(q, dict)
                    and "question" in q
                    and "type" in q
                    and "answer" in q
                    and (q["type"] != "mcq" or "options" in q)
                ]

                if not clean_questions:
                    st.error(
                        "No valid questions generated. "
                        "Make sure Ollama is running and the document has enough text."
                    )
                    st.stop()

                # ---------------- SHUFFLE ----------------
                if shuffle_questions:
                    random.shuffle(clean_questions)
                    for q in clean_questions:
                        if q["type"] == "mcq":
                            correct = q["answer"]
                            random.shuffle(q["options"])
                            q["answer"] = correct

                st.session_state.questions = clean_questions[:25]
                st.session_state.answers = {}
                st.session_state.generated = True
                st.session_state.difficulty = difficulty

            except requests.exceptions.Timeout:
                st.error(
                    "⏱️ Ollama timed out. Try using a smaller document or "
                    "run `ollama pull phi3:mini` for a faster model."
                )
                st.stop()

            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ Cannot reach the backend. "
                    "Run: `uvicorn backend.main:app --reload --port 8000`"
                )
                st.stop()

        st.success(f"✅ Quiz ready — {len(st.session_state.questions)} questions!")


# ---------------- COMPARISON BANNER ----------------
if st.session_state.generated and st.session_state.comparison_result:
    result = st.session_state.comparison_result
    similarity_pct = result["similarity"] * 100
    change_type = result["change_type"]

    color = {"same": "🟢", "partial": "🟡", "different": "🔴"}[change_type]
    label = {
        "same": "Highly Similar",
        "partial": "Partially Similar",
        "different": "Different"
    }[change_type]

    st.markdown("### 📊 Document Comparison")
    st.markdown(f"{color} **{label}** — Similarity Score: `{similarity_pct:.1f}%`")

    col1, col2, col3 = st.columns(3)
    col1.metric("Similarity", f"{similarity_pct:.1f}%")
    col2.metric("Match Type", label)
    col3.metric("Questions", len(st.session_state.questions))
    st.divider()


# ---------------- QUIZ INFO ----------------
if st.session_state.generated:
    st.info(f"📚 Topic: {st.session_state.topic}")
    st.info(f"🎯 Difficulty: {st.session_state.difficulty}")


# ---------------- QUIZ SECTION ----------------
if st.session_state.generated and st.session_state.questions:

    st.header("📝 Answer the Questions")
    total_questions = len(st.session_state.questions)
    progress_bar = st.progress(0)
    answered = 0

    for i, q in enumerate(st.session_state.questions):

        st.markdown(f"### Question {i+1}")

        if enable_timer:
            st.caption(f"⏱️ Suggested time: {time_limit} seconds")

        st.write(q["question"])

        if q["type"] == "mcq":
            answer = st.radio(
                "Select answer", q["options"], key=f"mcq_{i}"
            )
        elif q["type"] == "true_false":
            answer = st.radio(
                "Select answer", ["True", "False"], key=f"tf_{i}"
            )
        else:
            answer = st.text_area("Your answer", key=f"exp_{i}")

        if answer:
            answered += 1

        st.session_state.answers[i] = answer
        st.divider()

    progress_bar.progress(answered / total_questions)
    st.info(f"Answered {answered} / {total_questions}")


    # ---------------- SUBMIT ----------------
    if st.button("✅ Submit Quiz"):

        st.header("📊 Results")
        score = 0
        unanswered = 0

        for i, q in enumerate(st.session_state.questions):

            user_answer = st.session_state.answers.get(i, "")
            correct_answer = q["answer"]

            st.markdown(f"### Question {i+1}")
            st.write(q["question"])

            if not user_answer:
                st.warning("⚠️ Unanswered")
                st.write(f"**Correct Answer:** {correct_answer}")
                unanswered += 1
                st.divider()
                continue

            st.write(f"**Your Answer:** {user_answer}")
            st.write(f"**Correct Answer:** {correct_answer}")

            if q["type"] == "explanation":
                is_correct = evaluate_answer(
                    q["question"], correct_answer, user_answer
                )
            else:
                is_correct = (
                    str(user_answer).strip().lower() ==
                    str(correct_answer).strip().lower()
                )

            if is_correct:
                st.success("✅ Correct")
                score += 1
            else:
                st.error("❌ Incorrect")
                if q["type"] in ("mcq", "true_false"):
                    with st.expander("💡 See explanation"):
                        explanation_prompt = (
                            f'In one sentence, explain why '
                            f'"{correct_answer}" is the correct answer to: '
                            f'"{q["question"]}"'
                        )
                        explanation = ask_llm(explanation_prompt)
                        if explanation:
                            st.write(explanation.strip())

            st.divider()

        # ---------------- METRICS ----------------
        total = len(st.session_state.questions)
        wrong = total - score - unanswered
        accuracy = (score / total) * 100 if total else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Score", f"{score}/{total}")
        col2.metric("Accuracy", f"{accuracy:.1f}%")
        col3.metric("Wrong", wrong)
        col4.metric("Unanswered", unanswered)

        # ---------------- PIE CHART ----------------
        fig = px.pie(
            {
                "Result": ["Correct", "Wrong", "Unanswered"],
                "Count": [score, wrong, unanswered]
            },
            names="Result",
            values="Count",
            title="Quiz Performance"
        )
        st.plotly_chart(fig, use_container_width=True)

        # ---------------- SAVE RESULT ----------------
        saved_path = save_quiz_result(
            st.session_state.topic,
            st.session_state.difficulty,
            score, total,
            st.session_state.questions,
            st.session_state.answers
        )
        st.info(f"💾 Result saved to `{saved_path}`")

        # ---------------- EXPORT PDF ----------------
        st.divider()
        if st.button("📥 Download Results as PDF"):
            pdf_bytes = export_pdf(
                st.session_state.topic,
                st.session_state.difficulty,
                score, total,
                st.session_state.questions,
                st.session_state.answers
            )
            if pdf_bytes:
                st.download_button(
                    label="📄 Click to Download PDF",
                    data=pdf_bytes,
                    file_name=f"quiz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning(
                    "PDF export requires fpdf2. "
                    "Run: `pip install fpdf2`"
                )

        # ---------------- RESET BUTTONS ----------------
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            if st.button("🔄 Retake Quiz"):
                st.session_state.answers = {}
                st.rerun()

        with col_b:
            if st.button("🗑️ Reset Everything"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
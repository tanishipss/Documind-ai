import sys
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px
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
st.title("📘 DocuMind AI – Smart Quiz Generator")

difficulty = st.selectbox("Select Quiz Difficulty", ["Easy", "Medium", "Hard"])

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


# ---------------- TOPIC DETECTION ----------------
def detect_topic(text):
    prompt = f"""Identify the main topic of the following study material.
Return ONLY the topic name. No explanation, no extra text, just the topic.

{text[:2000]}"""
    topic = ask_llm(prompt)
    return topic.strip() if topic else "General Topic"


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

        with st.spinner("AI is analyzing your document(s)... this may take a minute."):

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
                        timeout=300
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

                    # SAME — reuse all questions
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
                                timeout=300
                            )
                            if response.status_code != 200:
                                st.error(f"Backend error: {response.text}")
                                st.stop()
                            questions = response.json().get("questions", [])

                    # PARTIAL — keep old + generate from new content
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
                            timeout=300
                        )
                        if new_response.status_code != 200:
                            st.error(f"Backend error: {new_response.text}")
                            st.stop()

                        new_questions = new_response.json().get("questions", [])
                        old_questions = st.session_state.questions or []
                        questions = old_questions[:6] + new_questions

                    # DIFFERENT — generate fresh from doc2
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
                            timeout=300
                        )
                        if response.status_code != 200:
                            st.error(f"Backend error: {response.text}")
                            st.stop()
                        questions = response.json().get("questions", [])

                # ---------------- CLEAN & STORE ----------------
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
                        "No valid questions were generated. "
                        "Make sure Ollama is running and the document has enough text."
                    )
                    st.stop()

                st.session_state.questions = clean_questions[:25]
                st.session_state.answers = {}
                st.session_state.generated = True
                st.session_state.difficulty = difficulty

            except requests.exceptions.Timeout:
                st.error(
                    "⏱️ Ollama timed out generating questions. "
                    "Try switching to a faster model: run `ollama pull llama3.2:3b` "
                    "in your terminal, then restart the app."
                )
                st.stop()

            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ Cannot reach the backend. "
                    "Make sure FastAPI is running: "
                    "`uvicorn backend.main:app --reload --port 8000`"
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
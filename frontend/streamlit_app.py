import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px
import requests

from document_processing.loaders.pdf_loader import load_document
from document_processing.preprocessing.chunker import chunk_text
from ai_engine.rag.chunk_retriever import retrieve_relevant_chunks
from backend.services.answer_evaluator import evaluate_answer
from ai_engine.llm.ollama_client import ask_llm
from semantic_versioning.question_updater import update_questions


# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📘",
    layout="wide"
)

st.title("📘 DocuMind AI – Smart Quiz Generator")


# ---------------- DIFFICULTY ----------------

difficulty = st.selectbox(
    "Select Quiz Difficulty",
    ["Easy", "Medium", "Hard"]
)


# ---------------- SESSION STATE ----------------

if "questions" not in st.session_state:
    st.session_state.questions = []

if "answers" not in st.session_state:
    st.session_state.answers = {}

if "generated" not in st.session_state:
    st.session_state.generated = False

if "topic" not in st.session_state:
    st.session_state.topic = ""

if "previous_text" not in st.session_state:
    st.session_state.previous_text = None


# ---------------- TOPIC DETECTION ----------------

def detect_topic(text):

    prompt = f"""
Identify the main topic of the following study material.

Return ONLY the topic name.

{text[:2000]}
"""

    topic = ask_llm(prompt)

    if topic:
        return topic.strip()

    return "General Topic"


# ---------------- FILE UPLOAD ----------------

uploaded_file = st.file_uploader(
    "Upload document",
    type=["pdf", "docx", "txt"]
)


# ---------------- GENERATE QUIZ ----------------

if uploaded_file and not st.session_state.generated:

    text = load_document(uploaded_file)

    chunks = chunk_text(text)

    # RAG retrieval
    best_chunks = retrieve_relevant_chunks(chunks)

    combined_text = " ".join(best_chunks)

    if st.button("🚀 Generate Quiz"):

        with st.spinner("AI is analyzing your document..."):

            st.session_state.topic = detect_topic(combined_text)

            # Call FastAPI backend
            response = requests.post(
                "http://127.0.0.1:8000/generate-quiz",
                json={
                    "text": combined_text,
                    "difficulty": difficulty
                }
            )

            new_questions = response.json()["questions"]

            # ---------------- SEMANTIC UPDATE ----------------

            if st.session_state.previous_text:

                questions = update_questions(
                    st.session_state.previous_text,
                    combined_text,
                    st.session_state.questions,
                    lambda x: new_questions
                )

            else:

                questions = new_questions

            st.session_state.previous_text = combined_text

            clean_questions = []

            for q in questions:

                if not isinstance(q, dict):
                    continue

                if "question" not in q or "type" not in q:
                    continue

                if q["type"] == "mcq" and "options" not in q:
                    continue

                clean_questions.append(q)

            st.session_state.questions = clean_questions[:25]
            st.session_state.answers = {}
            st.session_state.generated = True

        st.success("Quiz generated successfully!")


# ---------------- SHOW QUIZ INFO ----------------

if st.session_state.generated:

    st.info(f"📚 Topic: {st.session_state.topic}")
    st.info(f"🎯 Difficulty: {difficulty}")


# ---------------- QUIZ SECTION ----------------

if st.session_state.generated and st.session_state.questions:

    st.header("📝 Answer the Questions")

    total_questions = len(st.session_state.questions)

    progress_bar = st.progress(0)

    answered = 0

    for i, q in enumerate(st.session_state.questions):

        st.markdown(f"### Question {i+1}")
        st.write(q["question"])

        # MCQ
        if q["type"] == "mcq":

            answer = st.radio(
                "Select answer",
                q["options"],
                key=f"mcq_{i}"
            )

        # TRUE FALSE
        elif q["type"] == "true_false":

            answer = st.radio(
                "Select answer",
                ["True", "False"],
                key=f"tf_{i}"
            )

        # EXPLANATION
        else:

            answer = st.text_area(
                "Your answer",
                key=f"exp_{i}"
            )

        if answer:
            answered += 1

        st.session_state.answers[i] = answer

        st.divider()

    progress = answered / total_questions

    progress_bar.progress(progress)

    st.info(f"Answered {answered} / {total_questions}")


# ---------------- SUBMIT QUIZ ----------------

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

                st.warning("Unanswered")
                st.write("Correct Answer:")
                st.write(correct_answer)

                unanswered += 1
                st.divider()
                continue

            st.write("Your Answer:")
            st.write(user_answer)

            st.write("Correct Answer:")
            st.write(correct_answer)

            is_correct = False

            if q["type"] == "explanation":

                is_correct = evaluate_answer(
                    q["question"],
                    correct_answer,
                    user_answer
                )

            else:

                if str(user_answer).lower() == str(correct_answer).lower():
                    is_correct = True

            if is_correct:
                st.success("Correct")
                score += 1
            else:
                st.error("Incorrect")

            st.divider()


        # ---------------- METRICS ----------------

        total = len(st.session_state.questions)
        wrong = total - score - unanswered
        accuracy = (score / total) * 100

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Score", f"{score}/{total}")
        col2.metric("Accuracy", f"{accuracy:.2f}%")
        col3.metric("Wrong", wrong)
        col4.metric("Unanswered", unanswered)


        # ---------------- PIE CHART ----------------

        chart_data = {
            "Result": ["Correct", "Wrong", "Unanswered"],
            "Count": [score, wrong, unanswered]
        }

        fig = px.pie(
            chart_data,
            names="Result",
            values="Count",
            title="Quiz Performance"
        )

        st.plotly_chart(fig, use_container_width=True)
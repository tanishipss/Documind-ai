# backend/services/answer_evaluator.py
import logging
from ai_engine.llm.ollama_client import ask_llm

logger = logging.getLogger(__name__)


def evaluate_answer(question, correct_answer, user_answer):
    """
    Returns True if user_answer is semantically correct.
    Falls back to keyword matching if LLM fails.
    """

    if not user_answer or not user_answer.strip():
        return False

    # Quick keyword check first (saves an LLM call for obvious matches)
    if _keyword_match(correct_answer, user_answer):
        return True

    prompt = f"""
You are a strict but fair teacher grading a student's answer.

Question: {question}
Correct Answer: {correct_answer}
Student Answer: {user_answer}

Is the student's answer correct or mostly correct in meaning?
Reply with ONLY: CORRECT or INCORRECT
"""

    response = ask_llm(prompt)

    if not response:
        # Fallback to keyword matching if LLM fails
        return _keyword_match(correct_answer, user_answer)

    return "CORRECT" in response.upper()


def _keyword_match(correct, user, threshold=0.5):
    """Check if enough keywords from correct answer appear in user answer."""
    correct_words = set(correct.lower().split())
    user_words = set(user.lower().split())

    # Remove common stop words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "it", "in", "of", "to"}
    correct_words -= stop_words

    if not correct_words:
        return False

    overlap = len(correct_words & user_words) / len(correct_words)
    return overlap >= threshold
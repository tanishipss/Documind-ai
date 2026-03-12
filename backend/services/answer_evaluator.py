from ai_engine.llm.ollama_client import ask_llm


def evaluate_answer(question, correct_answer, user_answer):

    prompt = f"""
You are an exam evaluator.

Question:
{question}

Correct Answer:
{correct_answer}

Student Answer:
{user_answer}

Decide if the student's answer is correct.

Reply ONLY with:
Correct
or
Incorrect
"""

    result = ask_llm(prompt)

    if result and "correct" in result.lower():
        return True

    return False
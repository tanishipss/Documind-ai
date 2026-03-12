import json
import re
import logging

from ai_engine.llm.ollama_client import ask_llm

logger = logging.getLogger(__name__)


def generate_questions(text, difficulty="Medium"):

    logger.info(f"Generating {difficulty} difficulty quiz questions")

    questions = []

    # ---------------- MCQ ----------------

    mcq_prompt = f"""
You are an expert teacher creating quiz questions.

Task:
Generate 10 {difficulty} difficulty multiple choice questions.

IMPORTANT RULES:
- Use ONLY the information inside the provided context
- Do NOT invent facts
- Do NOT use outside knowledge
- Each question must have exactly 4 options
- The correct answer must match one option exactly

Return ONLY valid JSON:

[
 {{
  "type":"mcq",
  "question":"Question text",
  "options":["A","B","C","D"],
  "answer":"A"
 }}
]

Context (use ONLY this information):

---------------------
{text[:4000]}
---------------------
"""

    mcq_response = ask_llm(mcq_prompt)

    questions.extend(parse_json(mcq_response))

    # ---------------- TRUE FALSE ----------------

    tf_prompt = f"""
You are an expert teacher.

Task:
Generate 5 {difficulty} difficulty True/False questions.

Rules:
- Use ONLY the provided context
- Statements must come directly from the study material
- Answer must be True or False

Return ONLY JSON:

[
 {{
  "type":"true_false",
  "question":"Statement",
  "answer":"True"
 }}
]

Context:

---------------------
{text[:4000]}
---------------------
"""

    tf_response = ask_llm(tf_prompt)

    questions.extend(parse_json(tf_response))

    # ---------------- EXPLANATION ----------------

    exp_prompt = f"""
You are an expert teacher.

Task:
Generate 10 {difficulty} difficulty explanation questions.

Rules:
- Use ONLY the provided context
- Questions must test conceptual understanding
- Provide a short but correct explanation answer

Return ONLY JSON:

[
 {{
  "type":"explanation",
  "question":"Explain something",
  "answer":"Correct explanation"
 }}
]

Context:

---------------------
{text[:4000]}
---------------------
"""

    exp_response = ask_llm(exp_prompt)

    questions.extend(parse_json(exp_response))

    return questions


def parse_json(response):

    if not response:
        return []

    json_match = re.search(r"\[.*\]", response, re.DOTALL)

    if not json_match:
        return []

    try:
        return json.loads(json_match.group(0))
    except Exception as e:
        logger.error(f"JSON parsing error: {e}")
        return []
import json
import re
import logging

from ai_engine.llm.ollama_client import ask_llm

logger = logging.getLogger(__name__)


def generate_questions(text, difficulty="Medium"):
    """
    Generate a mixed quiz from document text.
    Single LLM call instead of 3 separate calls.
    """

    logger.info(f"Generating {difficulty} quiz | text length: {len(text)}")

    # Smart text distribution — sample from beginning, middle, end
    # instead of always truncating to first 4000 chars
    context = _sample_text(text, max_chars=6000)

    difficulty_instructions = {
        "Easy": (
            "Questions should test basic recall and simple definitions. "
            "MCQ options should have one clearly correct answer. "
            "True/False should be straightforward."
        ),
        "Medium": (
            "Questions should test understanding and application. "
            "MCQ distractors should be plausible. "
            "Explanation questions should require 2-3 sentence answers."
        ),
        "Hard": (
            "Questions should test analysis, comparison, and deep understanding. "
            "MCQ options should all be plausible with subtle differences. "
            "Explanation questions should require reasoning, not just recall."
        )
    }

    style = difficulty_instructions.get(difficulty, difficulty_instructions["Medium"])

    prompt = f"""
You are an expert teacher creating a quiz from study material.

Difficulty: {difficulty}
Style guide: {style}

Task:
Generate exactly this mix of questions from the context below:
- 10 multiple choice questions (type: "mcq")
- 5 true/false questions (type: "true_false")  
- 10 explanation questions (type: "explanation")

STRICT RULES:
- Use ONLY information from the provided context
- Do NOT invent facts or use outside knowledge
- MCQ: exactly 4 options, answer must match one option exactly (copy it word for word)
- True/False: answer must be exactly "True" or "False"
- Explanation: provide a complete model answer (2-4 sentences)
- Every question object must have: type, question, answer
- MCQ must also have: options (list of 4 strings)

Return ONLY a valid JSON array. No explanations, no markdown, no extra text.
Start your response with [ and end with ]

[
  {{
    "type": "mcq",
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A"
  }},
  {{
    "type": "true_false",
    "question": "Statement to evaluate.",
    "answer": "True"
  }},
  {{
    "type": "explanation",
    "question": "Explain the concept of X.",
    "answer": "X refers to... It works by... This is important because..."
  }}
]

Context (use ONLY this):
---------------------
{context}
---------------------
"""

    response = ask_llm(prompt)

    if not response:
        logger.error("LLM returned no response")
        return []

    questions = _parse_and_validate(response)

    logger.info(f"Generated {len(questions)} valid questions")

    return questions


def _sample_text(text, max_chars=6000):
    """
    Instead of always taking text[:4000], sample from
    beginning, middle, and end for better coverage.
    """
    if len(text) <= max_chars:
        return text

    third = max_chars // 3

    beginning = text[:third]
    mid_start = len(text) // 2 - third // 2
    middle = text[mid_start: mid_start + third]
    end = text[-third:]

    return f"{beginning}\n\n[...]\n\n{middle}\n\n[...]\n\n{end}"


def _parse_and_validate(response):
    """Parse JSON and strictly validate each question."""

    # Strip any markdown fences the LLM might add
    clean = re.sub(r"```(?:json)?", "", response).strip()

    # Find the JSON array
    match = re.search(r"\[.*\]", clean, re.DOTALL)

    if not match:
        logger.error("No JSON array found in LLM response")
        return []

    try:
        raw_questions = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        # Try to salvage partial JSON
        return _salvage_partial_json(match.group(0))

    validated = []

    for i, q in enumerate(raw_questions):

        if not isinstance(q, dict):
            logger.warning(f"Question {i} is not a dict, skipping")
            continue

        q_type = q.get("type", "").strip()
        question = q.get("question", "").strip()
        answer = q.get("answer", "").strip()

        # All questions need these 3 fields
        if not all([q_type, question, answer]):
            logger.warning(f"Question {i} missing required fields: {q}")
            continue

        if q_type not in ("mcq", "true_false", "explanation"):
            logger.warning(f"Question {i} unknown type: {q_type}")
            continue

        # MCQ-specific validation
        if q_type == "mcq":
            options = q.get("options", [])
            if len(options) != 4:
                logger.warning(f"MCQ {i} doesn't have 4 options")
                continue
            if answer not in options:
                # Try case-insensitive match and fix it
                fixed = next((o for o in options if o.lower() == answer.lower()), None)
                if fixed:
                    q["answer"] = fixed
                else:
                    logger.warning(f"MCQ {i} answer not in options: {answer}")
                    continue

        # True/False validation
        if q_type == "true_false":
            if answer not in ("True", "False"):
                normalized = answer.capitalize()
                if normalized in ("True", "False"):
                    q["answer"] = normalized
                else:
                    logger.warning(f"True/False {i} invalid answer: {answer}")
                    continue

        validated.append(q)

    return validated


def _salvage_partial_json(text):
    """Last resort: try to extract individual question objects."""
    questions = []
    pattern = r'\{[^{}]+\}'

    for match in re.finditer(pattern, text, re.DOTALL):
        try:
            q = json.loads(match.group(0))
            if isinstance(q, dict) and "question" in q:
                questions.append(q)
        except Exception:
            continue

    logger.info(f"Salvaged {len(questions)} questions from partial JSON")
    return questions
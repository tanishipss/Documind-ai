import json
import re
import logging

from ai_engine.llm.ollama_client import ask_llm

logger = logging.getLogger(__name__)


def generate_questions(text, difficulty="Medium"):

    context = text[:3000]  # increased from 1500

    prompt = f"""You are a teacher. Create a quiz. Difficulty: {difficulty}.
Use ONLY this text: {context}

Return a JSON array with exactly these questions:
- 12 MCQ (type: mcq) — 4 options each, answer matches one option exactly
- 6 True/False (type: true_false) — answer is exactly "True" or "False"
- 7 Explanation (type: explanation) — answer is 1-2 sentences

Total: 25 questions.

Return ONLY the JSON array, no extra text, starting with [ and ending with ]

[
  {{"type":"mcq","question":"Question?","options":["A","B","C","D"],"answer":"A"}},
  {{"type":"true_false","question":"Statement.","answer":"True"}},
  {{"type":"explanation","question":"Explain X.","answer":"X means..."}}
]"""

    response = ask_llm(prompt)

    if not response:
        logger.error("LLM returned no response")
        return []

    questions = _parse_and_validate(response)
    logger.info(f"Generated {len(questions)} valid questions")
    return questions


def _parse_and_validate(response):
    clean = re.sub(r"```(?:json)?|```", "", response).strip()
    match = re.search(r"\[.*\]", clean, re.DOTALL)

    if not match:
        logger.error("No JSON array in response")
        return []

    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return _salvage(match.group(0))

    validated = []

    for q in raw:
        if not isinstance(q, dict):
            continue
        if not all(k in q for k in ["type", "question", "answer"]):
            continue
        if q["type"] not in ("mcq", "true_false", "explanation"):
            continue

        if q["type"] == "mcq":
            opts = q.get("options", [])
            if len(opts) != 4:
                continue
            if q["answer"] not in opts:
                fixed = next(
                    (o for o in opts if o.lower() == q["answer"].lower()), None
                )
                if not fixed:
                    continue
                q["answer"] = fixed

        if q["type"] == "true_false":
            if q["answer"] not in ("True", "False"):
                normalized = q["answer"].capitalize()
                if normalized not in ("True", "False"):
                    continue
                q["answer"] = normalized

        validated.append(q)

    return validated


def _salvage(text):
    questions = []
    for match in re.finditer(r'\{[^{}]+\}', text, re.DOTALL):
        try:
            q = json.loads(match.group(0))
            if isinstance(q, dict) and "question" in q:
                questions.append(q)
        except Exception:
            continue
    return questions
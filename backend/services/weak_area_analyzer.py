import logging
from ai_engine.llm.ollama_client import ask_llm

logger = logging.getLogger(__name__)


def analyze_weak_areas(questions, answers):
    """
    Analyze wrong answers to identify weak topics and
    recommend specific pages/sections to review.
    """

    wrong_questions = []

    for i, q in enumerate(questions):
        user_ans = answers.get(i, "")
        correct_ans = q["answer"]

        is_wrong = False

        if not user_ans:
            is_wrong = True
        elif q["type"] == "explanation":
            # For explanation, mark as weak if unanswered
            # (we don't re-call LLM here to keep it fast)
            is_wrong = not bool(user_ans.strip())
        else:
            is_wrong = (
                str(user_ans).strip().lower() !=
                str(correct_ans).strip().lower()
            )

        if is_wrong:
            wrong_questions.append({
                "question": q["question"],
                "correct_answer": q["answer"],
                "user_answer": user_ans,
                "type": q["type"]
            })

    if not wrong_questions:
        return None  # perfect score — no weak areas

    # Build prompt to identify topics from wrong questions
    wrong_text = "\n".join([
        f"- Q: {w['question']} | Correct: {w['correct_answer']}"
        for w in wrong_questions[:10]  # limit to 10
    ])

    prompt = f"""A student got these questions wrong in a quiz:

{wrong_text}

Identify the 3 most important weak topic areas based on these wrong answers.
For each topic, suggest what the student should review.

Return ONLY a JSON array:
[
  {{
    "topic": "Topic name",
    "reason": "One sentence why this is a weak area",
    "review_hint": "What specifically to study"
  }}
]"""

    response = ask_llm(prompt)

    if not response:
        return _fallback_weak_areas(wrong_questions)

    import json
    import re

    clean = re.sub(r"```(?:json)?|```", "", response).strip()
    match = re.search(r"\[.*\]", clean, re.DOTALL)

    if not match:
        return _fallback_weak_areas(wrong_questions)

    try:
        weak_areas = json.loads(match.group(0))
        return {
            "wrong_count": len(wrong_questions),
            "weak_areas": weak_areas[:3],
            "wrong_questions": wrong_questions
        }
    except Exception as e:
        logger.error(f"Weak area parsing error: {e}")
        return _fallback_weak_areas(wrong_questions)


def _fallback_weak_areas(wrong_questions):
    """
    If LLM fails, extract topics directly from question text.
    """
    topics = []
    seen = set()

    for w in wrong_questions[:3]:
        # Use first 6 words of question as topic hint
        words = w["question"].split()[:6]
        topic = " ".join(words).rstrip("?").strip()

        if topic not in seen:
            seen.add(topic)
            topics.append({
                "topic": topic,
                "reason": "You answered this question incorrectly.",
                "review_hint": f"Review the section related to: {topic}"
            })

    return {
        "wrong_count": len(wrong_questions),
        "weak_areas": topics,
        "wrong_questions": wrong_questions
    }


def find_review_pages(weak_areas, doc_chunks):
    """
    Match each weak topic to the most relevant chunk
    and estimate page numbers.
    """
    if not weak_areas or not doc_chunks:
        return []

    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    model = SentenceTransformer("all-MiniLM-L6-v2")
    chunk_embeddings = model.encode(doc_chunks)

    recommendations = []

    for area in weak_areas:
        topic = area["topic"]
        query = f"{topic} {area.get('review_hint', '')}"

        query_emb = model.encode([query])
        sims = cosine_similarity(query_emb, chunk_embeddings)[0]

        best_idx = int(sims.argmax())
        best_score = float(sims[best_idx])

        if best_score < 0.2:
            continue

        # Estimate page number — roughly 250 words per page
        words_before = sum(
            len(doc_chunks[i].split())
            for i in range(best_idx)
        )
        estimated_page = max(1, words_before // 250 + 1)

        # Get a short excerpt from the relevant chunk
        chunk_preview = doc_chunks[best_idx][:200].strip()
        if len(doc_chunks[best_idx]) > 200:
            chunk_preview += "..."

        recommendations.append({
            "topic": topic,
            "reason": area.get("reason", ""),
            "review_hint": area.get("review_hint", ""),
            "estimated_page": estimated_page,
            "chunk_preview": chunk_preview,
            "relevance_score": round(best_score, 2)
        })

    return recommendations
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")


def compare_documents(old_text, new_text):
    """
    Compare two documents at the full-text level.
    Returns (similarity_score float, change_type string)
    """
    old_emb = model.encode([old_text[:8000]])
    new_emb = model.encode([new_text[:8000]])
    similarity = float(cosine_similarity(old_emb, new_emb)[0][0])
    change_type = get_change_type(similarity)
    print(f"📊 Document similarity: {similarity:.3f} → {change_type}")
    return similarity, change_type


def get_change_type(similarity):
    if similarity > 0.85:
        return "same"
    elif similarity > 0.40:
        return "partial"
    else:
        return "different"


def compare_chunks_detailed(chunks1, chunks2, threshold=0.80):
    """
    Compare each chunk in doc2 against all chunks in doc1.
    Returns (matched_chunks, unmatched_chunks) from doc2's perspective.
    """
    if not chunks1 or not chunks2:
        return [], chunks2

    emb1 = model.encode(chunks1)
    emb2 = model.encode(chunks2)

    matched = []
    unmatched = []

    for chunk2, emb in zip(chunks2, emb2):
        sims = cosine_similarity([emb], emb1)[0]
        best_match = float(np.max(sims))

        if best_match >= threshold:
            matched.append(chunk2)
        else:
            unmatched.append(chunk2)

    print(f"📊 Chunk comparison: {len(matched)} matched, {len(unmatched)} unmatched")
    return matched, unmatched


def get_unmatched_chunks(chunks1, chunks2, threshold=0.80):
    """
    Return only the NEW/CHANGED chunks from doc2
    that don't have a close match in doc1.
    """
    _, unmatched = compare_chunks_detailed(chunks1, chunks2, threshold)
    return unmatched
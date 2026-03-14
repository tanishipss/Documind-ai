from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")


def compare_documents(old_text, new_text):
    """Full document similarity — returns (score, change_type)"""
    old_emb = model.encode([old_text[:8000]])
    new_emb = model.encode([new_text[:8000]])
    similarity = float(cosine_similarity(old_emb, new_emb)[0][0])
    return similarity, get_change_type(similarity)


def get_change_type(similarity):
    if similarity > 0.85:
        return "same"
    elif similarity > 0.40:
        return "partial"
    else:
        return "different"


def compare_chunks_detailed(chunks1, chunks2, threshold=0.80):
    """
    Chunk-level comparison.
    Returns (matched, unmatched, change_summary)
    """
    if not chunks1 or not chunks2:
        return [], chunks2, _empty_summary(chunks2)

    emb1 = model.encode(chunks1)
    emb2 = model.encode(chunks2)

    matched = []
    unmatched = []
    chunk_details = []

    for i, (chunk2, emb) in enumerate(zip(chunks2, emb2)):
        sims = cosine_similarity([emb], emb1)[0]
        best_score = float(np.max(sims))
        best_idx = int(np.argmax(sims))

        if best_score >= threshold:
            matched.append(chunk2)
            chunk_details.append({
                "chunk_index": i,
                "status": "unchanged",
                "similarity": round(best_score, 3),
                "doc2_preview": chunk2[:120] + "..." if len(chunk2) > 120 else chunk2,
                "matched_doc1_preview": (
                    chunks1[best_idx][:120] + "..."
                    if len(chunks1[best_idx]) > 120
                    else chunks1[best_idx]
                )
            })
        else:
            unmatched.append(chunk2)
            chunk_details.append({
                "chunk_index": i,
                "status": "new" if best_score < 0.3 else "modified",
                "similarity": round(best_score, 3),
                "doc2_preview": chunk2[:120] + "..." if len(chunk2) > 120 else chunk2,
                "matched_doc1_preview": (
                    chunks1[best_idx][:120] + "..."
                    if len(chunks1[best_idx]) > 120
                    else chunks1[best_idx]
                ) if best_score >= 0.3 else None
            })

    # Detect removed chunks — in doc1 but not in doc2
    removed = []
    for j, (chunk1, emb1_single) in enumerate(zip(chunks1, emb1)):
        sims = cosine_similarity([emb1_single], emb2)[0]
        best_score = float(np.max(sims))
        if best_score < threshold:
            removed.append({
                "chunk_index": j,
                "status": "removed",
                "similarity": round(best_score, 3),
                "doc1_preview": chunk1[:120] + "..." if len(chunk1) > 120 else chunk1
            })

    summary = _build_summary(chunk_details, removed, chunks1, chunks2)

    return matched, unmatched, summary


def _build_summary(chunk_details, removed, chunks1, chunks2):
    unchanged = [c for c in chunk_details if c["status"] == "unchanged"]
    modified  = [c for c in chunk_details if c["status"] == "modified"]
    new       = [c for c in chunk_details if c["status"] == "new"]

    total_doc1 = len(chunks1)
    total_doc2 = len(chunks2)

    pct_unchanged = round(len(unchanged) / total_doc2 * 100, 1) if total_doc2 else 0
    pct_modified  = round(len(modified)  / total_doc2 * 100, 1) if total_doc2 else 0
    pct_new       = round(len(new)       / total_doc2 * 100, 1) if total_doc2 else 0
    pct_removed   = round(len(removed)   / total_doc1 * 100, 1) if total_doc1 else 0

    return {
        "total_chunks_doc1": total_doc1,
        "total_chunks_doc2": total_doc2,
        "unchanged_count": len(unchanged),
        "modified_count": len(modified),
        "new_count": len(new),
        "removed_count": len(removed),
        "pct_unchanged": pct_unchanged,
        "pct_modified": pct_modified,
        "pct_new": pct_new,
        "pct_removed": pct_removed,
        "unchanged_chunks": unchanged,
        "modified_chunks": modified,
        "new_chunks": new,
        "removed_chunks": removed,
    }


def _empty_summary(chunks2):
    return {
        "total_chunks_doc1": 0,
        "total_chunks_doc2": len(chunks2),
        "unchanged_count": 0,
        "modified_count": 0,
        "new_count": len(chunks2),
        "removed_count": 0,
        "pct_unchanged": 0,
        "pct_modified": 0,
        "pct_new": 100.0,
        "pct_removed": 0,
        "unchanged_chunks": [],
        "modified_chunks": [],
        "new_chunks": [],
        "removed_chunks": [],
    }


def get_unmatched_chunks(chunks1, chunks2, threshold=0.80):
    _, unmatched, _ = compare_chunks_detailed(chunks1, chunks2, threshold)
    return unmatched


def get_detailed_comparison(chunks1, chunks2, threshold=0.80):
    """
    Full comparison result including summary.
    Called from streamlit for the comparison banner.
    """
    matched, unmatched, summary = compare_chunks_detailed(
        chunks1, chunks2, threshold
    )
    return matched, unmatched, summary
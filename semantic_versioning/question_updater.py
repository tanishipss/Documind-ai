from semantic_versioning.document_comparator import compare_documents, get_unmatched_chunks


def update_questions(old_text, new_text, old_questions, generate_questions_fn):
    """
    Legacy single-doc updater — kept for backward compatibility.
    The main dual-doc logic now lives in streamlit_app.py.
    """
    similarity, change_type = compare_documents(old_text, new_text)

    if change_type == "same":
        print("♻️ Same document — reusing all questions")
        return old_questions

    elif change_type == "partial":
        print("🔀 Partial change — merging questions")
        new_questions = generate_questions_fn(new_text)
        return old_questions[:12] + new_questions[12:]

    else:
        print("🆕 Different document — regenerating all questions")
        return generate_questions_fn(new_text)
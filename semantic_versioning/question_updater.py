from semantic_versioning.document_comparator import compare_documents, get_change_type


def update_questions(old_text, new_text, old_questions, generate_questions):

    similarity = compare_documents(old_text, new_text)

    change_type = get_change_type(similarity)

    if change_type == "same":

        # Keep all questions
        return old_questions

    elif change_type == "partial":

        # Keep half old, generate half new
        new_questions = generate_questions(new_text)

        return old_questions[:12] + new_questions[12:]

    else:

        # Completely regenerate
        return generate_questions(new_text)
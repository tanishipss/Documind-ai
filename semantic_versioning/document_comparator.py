from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


model = SentenceTransformer("all-MiniLM-L6-v2")


def compare_documents(old_text, new_text):

    old_embedding = model.encode([old_text])
    new_embedding = model.encode([new_text])

    similarity = cosine_similarity(old_embedding, new_embedding)[0][0]

    return similarity


def get_change_type(similarity):

    if similarity > 0.85:
        return "same"

    elif similarity > 0.40:
        return "partial"

    else:
        return "different"
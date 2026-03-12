from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


model = SentenceTransformer("all-MiniLM-L6-v2")


def retrieve_relevant_chunks(chunks, top_k=5):

    if not chunks:
        return []

    embeddings = model.encode(chunks)

    # centroid of document
    centroid = np.mean(embeddings, axis=0)

    similarities = cosine_similarity(
        [centroid],
        embeddings
    )[0]

    ranked_indices = np.argsort(similarities)[::-1]

    selected_chunks = [chunks[i] for i in ranked_indices[:top_k]]

    return selected_chunks
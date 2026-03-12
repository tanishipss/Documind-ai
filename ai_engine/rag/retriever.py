from vector_store.chroma_client import collection
from ai_engine.embeddings.embedding_model import model


def retrieve_relevant_chunks(query):

    query_embedding = model.encode([query])

    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=3
    )

    return results["documents"][0]